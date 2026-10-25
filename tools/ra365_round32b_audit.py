#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 32B: complete visible-parity attribution for the frozen RA365 corpus.

This tool keeps the Round 26/31 comparison contract unchanged (same pairing,
same re-anchoring, same tolerance, same denominators) and adds a *complete*
attribution layer:

  * every daily row is measured under the displayed basis (literal high/low);
  * raw OHLC differences are separated from adjustment-factor differences;
  * every factor step is matched (same date / moved date / reference-only /
    product-only) and every failing row is attributed to the nearest mismatched
    correction step, with an explicit multi-step overlap count;
  * counterfactuals quantify exactly how many rows become exact / tolerance-
    conform after (a) the reference-implied factor, (b) the reference raw OHLC,
    (c) both -- for D, W and M independently;
  * per-field factor consistency is measured so a constant factor per date is
    not assumed without evidence.

The tool is read-only. It never writes the product, the reference or any DB.

Outputs (out dir):
  summary.json            totals, counterfactuals, attribution classes
  families.csv            failing rows by step class + event signature + error
  steps.csv               every matched/mismatched factor step with row counts
  per_asset.csv           per-asset daily/W/M counters
  mismatch_rows.csv       every daily row failing the frozen tolerance
  exact_gap_rows.csv      every daily row passing tolerance but not 1e-9 exact
  coverage.csv            paired / ref-only / product-only rows per timeframe

Usage:
  python tools/ra365_round32b_audit.py \
      --ref D:/BorsTerminal-tmp/r26_bench/frozen/ref_bars_v2.jsonl \
      --product D:/BorsTerminal-tmp/r29_bench/full_shard0,... \
      --cohort D:/BorsTerminal-tmp/ra365_round18/cohort.jsonl \
      --out D:/BorsTerminal-tmp/r32b/audit_code [--limit N]
"""
import argparse
import bisect
import csv
import datetime as dt
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import candle_contract as CC  # noqa: E402
import ra_parity as RP  # noqa: E402

TOL = 0.5
REL = 1e-6
EXACT = 1e-9
STEP_EPS = 1e-10
STEP_RATIO_SAME = 1e-12
STEP_MATCH_WINDOW = 10
STEP_MATCH_RATIO = 1e-4
FIELD_NAMES = ("o", "h", "l", "c")
CORRECTION_FIELDS = ("open", "high_raw", "low_raw", "close", "last", "high", "low")


def fnum(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def bar_tuple(b):
    if isinstance(b, dict):
        return (str(b.get("utc"))[:10], fnum(b.get("open")), fnum(b.get("high")),
                fnum(b.get("low")), fnum(b.get("close")), fnum(b.get("volume")))
    return (str(b[0])[:10], fnum(b[1]), fnum(b[2]), fnum(b[3]), fnum(b[4]),
            fnum(b[5]) if len(b) > 5 else None)


def week_key(date):
    y, m, d = (int(x) for x in date.split("-"))
    day = (dt.date(y, m, d) - dt.date(1970, 1, 1)).days
    return (day - 2) // 7


def month_key(date):
    y, m, d = (int(x) for x in date.split("-"))
    jy, jm, _ = RP.jalali_of(dt.date(y, m, d))
    return jy * 12 + (jm - 1)


def aggregate(daily, keyfn):
    out = {}
    for date, o, h, l, c, v in daily:
        k = keyfn(date)
        cur = out.get(k)
        if cur is None:
            out[k] = [o, h, l, c, v, date]
        else:
            cur[1] = h if cur[1] is None else (h if h is not None and h > cur[1] else cur[1])
            cur[2] = l if cur[2] is None else (l if l is not None and l < cur[2] else cur[2])
            cur[3] = c
            cur[4] = (cur[4] or 0) + (v or 0)
            cur[5] = date
    return out


def reanchor(factors, anchor_date):
    scale = factors.get(anchor_date)
    if not scale:
        return dict(factors)
    return {d: f / scale for d, f in factors.items()}


def price_tol(ref):
    return max(TOL, REL * abs(ref))


def row_exact(prod, ref):
    for pv, rv in zip(prod, ref):
        if pv is None or rv is None or abs(pv - rv) > EXACT:
            return False
    return True


def row_passes(prod, ref):
    for pv, rv in zip(prod, ref):
        if pv is None or rv is None or abs(pv - rv) > price_tol(rv):
            return False
    return True


def field_flags(prod, ref, limit):
    bad = []
    for name, pv, rv in zip(FIELD_NAMES, prod, ref):
        if pv is None or rv is None:
            bad.append(name + ":null")
        elif abs(pv - rv) > limit(rv):
            bad.append(name)
    return ",".join(bad)


def step_error_bucket(err):
    a = abs(err)
    if a < 1e-9:
        return "0"
    if a < 1e-4:
        return "<0.01%"
    if a < 1e-3:
        return "0.01-0.1%"
    if a < 1e-2:
        return "0.1-1%"
    if a < 0.1:
        return "1-10%"
    return ">=10%"


def event_kind(src):
    s = "" if src is None else str(src)
    if s.startswith("fund-portal"):
        return "fund_dps"
    if s == "tsetmc_price_adjust_by_flow":
        return "dps"
    if s == "shareChange":
        return "share"
    if s == "base-price-discontinuity":
        return "base_gap"
    if s == "priceAdjust":
        return "pa"
    if s in ("", "None", "NoneType"):
        return "unproven_gap"
    return s


def event_signature(events):
    kinds = sorted({event_kind(e.get("source")) for e in events})
    return "+".join(kinds) if kinds else "no_event"


def infer_steps(dates, factors, eps=STEP_EPS):
    steps = []
    for prev, cur in zip(dates, dates[1:]):
        a, b = factors.get(prev), factors.get(cur)
        if not a or not b:
            continue
        r = a / b
        if abs(r - 1.0) > eps:
            steps.append({"prev": prev, "date": cur, "ratio": r})
    return steps


def match_steps(prod_steps, ref_steps, window=STEP_MATCH_WINDOW,
                same_ratio=STEP_RATIO_SAME, close_ratio=STEP_MATCH_RATIO):
    """One-to-one match of product and reference factor steps.

    Returns (matches, extra_product, ref_only).  A match is a dict with
    class RATIO_DIFF (same date), DATE_DIFF (moved date), or None (aligned).
    """
    prod_left = set(range(len(prod_steps)))
    matches = []
    used_ref = set()
    # 1) same effective date
    by_date = defaultdict(list)
    for j, s in enumerate(prod_steps):
        by_date[s["date"]].append(j)
    for i, rs in enumerate(ref_steps):
        cands = [j for j in by_date.get(rs["date"], []) if j in prod_left]
        if not cands:
            continue
        j = min(cands, key=lambda k: abs(prod_steps[k]["ratio"] / rs["ratio"] - 1.0))
        prod_left.discard(j)
        used_ref.add(i)
        err = prod_steps[j]["ratio"] / rs["ratio"] - 1.0
        cls = None if abs(err) <= same_ratio else "RATIO_DIFF"
        matches.append({"ref": rs, "prod": prod_steps[j], "class": cls,
                        "ratio_err": err})
    # 2) moved date, close ratio
    for i, rs in enumerate(ref_steps):
        if i in used_ref:
            continue
        best = None
        for j in list(prod_left):
            ps = prod_steps[j]
            try:
                dd = abs((dt.date(*(int(x) for x in ps["date"].split("-")))
                          - dt.date(*(int(x) for x in rs["date"].split("-")))).days)
            except Exception:
                continue
            if dd > window:
                continue
            rel = abs(ps["ratio"] / rs["ratio"] - 1.0)
            if rel > close_ratio:
                continue
            key = (dd, rel)
            if best is None or key < best[0]:
                best = (key, j)
        if best:
            j = best[1]
            prod_left.discard(j)
            used_ref.add(i)
            matches.append({"ref": rs, "prod": prod_steps[j], "class": "DATE_DIFF",
                            "ratio_err": prod_steps[j]["ratio"] / rs["ratio"] - 1.0})
    # 3) moved date with a large ratio difference (still a date defect, not ref-only)
    for i, rs in enumerate(ref_steps):
        if i in used_ref:
            continue
        best = None
        for j in list(prod_left):
            ps = prod_steps[j]
            try:
                dd = abs((dt.date(*(int(x) for x in ps["date"].split("-")))
                          - dt.date(*(int(x) for x in rs["date"].split("-")))).days)
            except Exception:
                continue
            if dd > window:
                continue
            key = (dd, abs(ps["ratio"] / rs["ratio"] - 1.0))
            if best is None or key < best[0]:
                best = (key, j)
        if best:
            j = best[1]
            prod_left.discard(j)
            used_ref.add(i)
            matches.append({"ref": rs, "prod": prod_steps[j], "class": "DATE_DIFF",
                            "ratio_err": prod_steps[j]["ratio"] / rs["ratio"] - 1.0})
    ref_only = [rs for i, rs in enumerate(ref_steps) if i not in used_ref]
    extra = [prod_steps[j] for j in sorted(prod_left)]
    return matches, extra, ref_only


def correction_events(matches, extra, ref_only):
    """Flatten step matches into (date, multiplier, step_ref) correction events."""
    out = []
    for i, m in enumerate(matches):
        if m["class"] is None:
            continue
        rs, ps = m["ref"], m["prod"]
        fam = m.get("family")
        if m["class"] == "RATIO_DIFF":
            out.append({"date": rs["date"], "mult": rs["ratio"] / ps["ratio"],
                        "step": i, "class": "RATIO_DIFF", "family": fam})
        else:
            out.append({"date": ps["date"], "mult": 1.0 / ps["ratio"],
                        "step": i, "class": "DATE_DIFF_CANCEL", "family": fam})
            out.append({"date": rs["date"], "mult": rs["ratio"],
                        "step": i, "class": "DATE_DIFF_APPLY", "family": fam})
    for i, rs in enumerate(ref_only):
        out.append({"date": rs["date"], "mult": rs["ratio"],
                    "step": len(matches) + i, "class": "REF_ONLY",
                    "family": rs.get("family")})
    for i, ps in enumerate(extra):
        out.append({"date": ps["date"], "mult": 1.0 / ps["ratio"],
                    "step": len(matches) + len(ref_only) + i, "class": "EXTRA",
                    "family": ps.get("family")})
    out.sort(key=lambda x: x["date"])
    return out


def step_label(m, symbols=None):
    if m["class"] is None:
        return "ALIGNED"
    return m["class"]


def compare_wm(prod_agg, ref_bars):
    """Counter for product aggregate vs reference W/M bars (same as R27 harness)."""
    c = Counter()
    for k in set(prod_agg) & set(ref_bars):
        p = prod_agg[k]
        r = ref_bars[k]
        po, ph, pl, pc, pv = p[0], p[1], p[2], p[3], p[4]
        ro, rh, rl, rc, rv = r[1], r[2], r[3], r[4], r[5]
        ok = True
        exact = True
        for name, pval, rval in (("o", po, ro), ("h", ph, rh), ("l", pl, rl), ("c", pc, rc)):
            c[name + "_cmp"] += 1
            if pval is None or rval is None:
                ok = False
                exact = False
                continue
            d = abs(pval - rval)
            if d <= EXACT:
                c[name + "_exact"] += 1
            else:
                exact = False
            if d > price_tol(rval):
                ok = False
            else:
                c[name + "_tol"] += 1
        c["rows"] += 1
        if ok:
            c["row_tol"] += 1
        if exact:
            c["row_exact"] += 1
    return c


def load_ref(path):
    ref = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            if d.get("type") not in ("type0", "type7"):
                continue
            aid = str(d.get("asset_id"))
            res = d.get("res")
            if res not in ("D", "W"):
                continue
            bars = {}
            for b in d.get("bars") or []:
                t = bar_tuple(b)
                if t[0]:
                    bars[t[0]] = t
            ref.setdefault(aid, {}).setdefault(d["type"], {})[res] = bars
    return ref


def derive_monthly(bars_d):
    daily = [bars_d[d] for d in sorted(bars_d)]
    agg = aggregate([(t[0], t[1], t[2], t[3], t[4], None) for t in daily], month_key)
    return {k: (v[5], v[0], v[1], v[2], v[3], v[4]) for k, v in agg.items()}


def product_files(roots):
    out = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for fn in sorted(os.listdir(root)):
            if fn.endswith(".json") and fn[:-5].isdigit():
                out.append(os.path.join(root, fn))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--product", required=True, help="comma-separated payload dirs")
    ap.add_argument("--cohort", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--correction-version", default="ra365-r32b-v1")
    ap.add_argument("--created-at", default="")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    created_at = a.created_at or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    h = hashlib.sha256()
    with open(a.ref, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    ref_sha = h.hexdigest()

    symbols = {}
    for line in open(a.cohort, encoding="utf-8"):
        d = json.loads(line)
        symbols[str(d.get("ra_asset_id"))] = d.get("symbol")

    ref = load_ref(a.ref)
    ref_m = {}
    for aid, types in ref.items():
        for typ, byres in types.items():
            if "D" in byres:
                ref_m.setdefault(aid, {})[typ] = derive_monthly(byres["D"])

    files = product_files(a.product.split(","))
    totals = defaultdict(Counter)
    cov = defaultdict(Counter)
    fam = defaultdict(Counter)
    step_rows = []
    per_asset = []
    seen = set()
    rf_anchor = Counter()
    field_ratio_dev = Counter()
    n_factor_corr = Counter()
    n_raw_corr = Counter()

    mf = open(os.path.join(a.out, "mismatch_rows.csv"), "w", encoding="utf-8-sig", newline="")
    mw = csv.writer(mf)
    mw.writerow(["asset_id", "symbol", "date", "raw_bad_fields", "raw_exact_bad_fields",
                 "factor_rel_err", "nearest_corr_date", "nearest_step_class",
                 "event_sig", "err_bucket", "steps_above", "corr_for_row",
                 "one_step_recoverable", "all_step_recoverable",
                 "raw_fix_recoverable", "both_fix_recoverable", "field_bad"])
    ef = open(os.path.join(a.out, "exact_gap_rows.csv"), "w", encoding="utf-8-sig", newline="")
    ew = csv.writer(ef)
    ew.writerow(["asset_id", "symbol", "date", "kind", "factor_rel_err",
                 "raw_exact_bad_fields", "all_fix_exact", "base_field_bad"])
    fc = open(os.path.join(a.out, "factor_corrections.csv"), "w", encoding="utf-8-sig", newline="")
    fcw = csv.writer(fc)
    fcw.writerow(["correction_version", "created_at", "source", "method", "ref_bars_sha256",
                  "ins_code", "asset_id", "symbol", "action", "effective_date",
                  "target_ratio", "class", "prod_date", "ref_date", "prod_ratio", "ref_ratio",
                  "event_sig", "err_bucket", "fields_used", "samples", "max_field_dev",
                  "confidence", "reason"])
    rc = open(os.path.join(a.out, "raw_corrections.csv"), "w", encoding="utf-8-sig", newline="")
    rcw = csv.writer(rc)
    rcw.writerow(["correction_version", "created_at", "source", "method", "ref_bars_sha256",
                  "ins_code", "asset_id", "symbol", "date", "field", "product_value",
                  "reference_value", "abs_diff", "confidence", "reason"])

    for path in files:
        if a.limit and len(per_asset) >= a.limit:
            break
        p = json.load(open(path, encoding="utf-8"))
        aid = str(p.get("asset_id"))
        if aid in seen or aid not in ref:
            continue
        seen.add(aid)
        ins_code = str(p.get("ins_code") or "")
        symbol = symbols.get(aid) or p.get("symbol") or ""
        t0 = ref[aid].get("type0", {}).get("D") or {}
        t7 = ref[aid].get("type7", {}).get("D") or {}
        w0 = ref[aid].get("type0", {}).get("W") or {}
        w7 = ref[aid].get("type7", {}).get("W") or {}
        if not t0 or not t7:
            continue
        candles = {}
        for c in p.get("candles") or []:
            d = str(c.get("time"))[:10]
            if d:
                candles[d] = c
        fac = {str(f.get("time"))[:10]: fnum(f.get("factor"))
               for f in (p.get("factors") or [])}
        fac = {k: v for k, v in fac.items() if v}
        if not fac:
            continue
        common = sorted(set(candles) & set(fac) & set(t0) & set(t7))
        if len(common) < 10:
            continue
        scale = fac[common[-1]] or 1.0
        pf = {d: f / scale for d, f in fac.items() if d in common}
        all_dates = sorted(set(candles) & set(fac))
        pf_all = reanchor(fac, common[-1])

        # reference factor from close; per-field consistency probe
        rf = {}
        for d in common:
            a0, a7 = t0.get(d), t7.get(d)
            if not a0 or not a7 or not a0[4] or not a7[4]:
                continue
            r = a7[4] / a0[4]
            rf[d] = r
        if len(rf) < 10:
            continue
        rf_anchor[round(rf.get(common[-1], 0.0), 12)] += 1
        for d in common:
            a0, a7 = t0[d], t7[d]
            if d not in rf or not a0[4]:
                continue
            r = rf[d]
            for i, name in enumerate(FIELD_NAMES):
                if not a0[i + 1] or a7[i + 1] is None:
                    continue
                rel = (a7[i + 1] / (a0[i + 1] * r)) - 1.0
                if abs(rel) > 1e-9:
                    field_ratio_dev[name + (">1e-9" if abs(rel) <= 1e-6 else ">1e-6")] += 1

        # product rows (all dates for W/M; displayed basis)
        all_daily_base, all_daily_factor, all_daily_raw, all_daily_both = [], [], [], []
        common_rows = []
        for d in all_dates:
            c = candles[d]
            o = fnum(c.get("open"))
            hi = fnum(c.get("high_raw"))
            lo = fnum(c.get("low_raw"))
            if hi is None:
                hi = fnum(c.get("high"))
            if lo is None:
                lo = fnum(c.get("low"))
            cl = fnum(c.get("last"))
            if cl is None:
                cl = fnum(c.get("close"))
            v = fnum(c.get("volume"))
            raw = [o, hi, lo, cl]
            f = pf_all.get(d)
            r = rf.get(d)
            a0 = t0.get(d)
            if f is not None:
                all_daily_base.append((d, *[(x * f if x is not None else None) for x in raw], v))
                all_daily_factor.append((d, *[(x * (r if r is not None else f) if x is not None else None) for x in raw], v))
                ref_raw = [a0[i + 1] if a0 else raw[i] for i in range(4)]
                all_daily_raw.append((d, *[(ref_raw[i] * f if ref_raw[i] is not None else None) for i in range(4)], v))
                all_daily_both.append((d, *[(ref_raw[i] * (r if r is not None else f)
                                             if ref_raw[i] is not None else None) for i in range(4)], v))
            if d in common and d in rf and f is not None:
                common_rows.append((d, raw, f, r, a0, t7[d]))

        # daily metrics + row attribution
        total_rows = 0
        base_exact = base_tol = 0
        ff_tol = ff_exact = rf_tol = rf_exact = bf_tol = bf_exact = 0
        raw_bad_rows = raw_exact_bad_rows = 0
        exact_gap_kind = Counter()
        common_rows_fail = []
        for d, raw, f, r, a0, a7 in common_rows:
            total_rows += 1
            adj = [(x * f if x is not None else None) for x in raw]
            refv = [a7[1], a7[2], a7[3], a7[4]]
            ex = row_exact(adj, refv)
            ok = row_passes(adj, refv)
            if ex:
                base_exact += 1
            if ok:
                base_tol += 1
            # raw / factor-separated counterfactuals
            raw_bad = field_flags(raw, [a0[1], a0[2], a0[3], a0[4]], price_tol)
            raw_exact_bad = field_flags(raw, [a0[1], a0[2], a0[3], a0[4]], lambda _x: EXACT)
            if raw_bad:
                raw_bad_rows += 1
            if raw_exact_bad:
                raw_exact_bad_rows += 1
                c = candles[d]
                fields = (
                    ("open", fnum(c.get("open")), a0[1]),
                    ("high_raw", fnum(c.get("high_raw")), a0[2]),
                    ("high", fnum(c.get("high")), a0[2]),
                    ("low_raw", fnum(c.get("low_raw")), a0[3]),
                    ("low", fnum(c.get("low")), a0[3]),
                    ("close", fnum(c.get("close")), a0[4]),
                    ("last", fnum(c.get("last")), a0[4]),
                )
                seen_fields = set()
                for fname, pv, rv in fields:
                    if pv is None or rv is None or abs(pv - rv) <= EXACT:
                        continue
                    if (fname, pv, rv) in seen_fields:
                        continue
                    seen_fields.add((fname, pv, rv))
                    if fname in ("high", "high_raw"):
                        reason = ("reference_high_matches_product_widened_high"
                                  if abs(fnum(c.get("high")) - rv) <= EXACT
                                  else "source_revision_high")
                    elif fname in ("low", "low_raw"):
                        reason = ("reference_low_matches_product_widened_low"
                                  if abs(fnum(c.get("low")) - rv) <= EXACT
                                  else "source_revision_low")
                    elif fname in ("close", "last"):
                        other = fnum(c.get("close")) if fname == "last" else fnum(c.get("last"))
                        reason = ("reference_close_matches_other_price_basis"
                                  if other is not None and abs(other - rv) <= EXACT
                                  else "source_revision_close")
                    else:
                        reason = "source_revision_open"
                    rcw.writerow([a.correction_version, created_at,
                                  "rahavard_reference_frozen_v2",
                                  "per_field_daily_reference_value", ref_sha,
                                  ins_code, aid, symbol, d, fname, repr(pv), repr(rv),
                                  repr(abs(pv - rv)), "reference_snapshot_exact", reason])
                    n_raw_corr[fname] += 1
            fadj = [(x * r if x is not None else None) for x in raw]
            radj = [(a0[i + 1] * f if a0[i + 1] is not None else None) for i in range(4)]
            badj = [(a0[i + 1] * r if a0[i + 1] is not None else None) for i in range(4)]
            if row_passes(fadj, refv):
                ff_tol += 1
            if row_exact(fadj, refv):
                ff_exact += 1
            if row_passes(radj, refv):
                rf_tol += 1
            if row_exact(radj, refv):
                rf_exact += 1
            if row_passes(badj, refv):
                bf_tol += 1
            if row_exact(badj, refv):
                bf_exact += 1
            fre = (f / r - 1.0) if r else 0.0
            if ok and not ex:
                if row_exact(fadj, refv):
                    kind = "factor_precision"
                elif raw_exact_bad:
                    kind = "raw_precision"
                else:
                    kind = "rounding"
                exact_gap_kind[kind] += 1
                ew.writerow([aid, symbols.get(aid) or p.get("symbol"), d, kind,
                             round(fre, 12), raw_exact_bad,
                             1 if row_exact(badj, refv) else 0,
                             field_flags(adj, refv, price_tol)])
            if not ok:
                totals["D"]["mismatch"] += 1
                raw_fix_ok = row_passes(radj, refv)
                factor_fix_ok = row_passes(fadj, refv)
                both_fix_ok = row_passes(badj, refv)
                if raw_bad and raw_fix_ok:
                    totals["D"]["primary_raw_source"] += 1
                elif not raw_bad and factor_fix_ok:
                    totals["D"]["primary_factor_chain"] += 1
                elif raw_bad and both_fix_ok:
                    totals["D"]["primary_raw_plus_factor"] += 1
                elif not raw_bad:
                    totals["D"]["primary_factor_irrecoverable"] += 1
                else:
                    totals["D"]["primary_unexplained"] += 1
                if raw_bad:
                    totals["D"]["raw_primary_overlap"] += 1
                if factor_fix_ok:
                    totals["D"]["factor_primary_overlap"] += 1
                if not factor_fix_ok:
                    totals["D"]["factor_irrecoverable"] += 1
                if not raw_fix_ok:
                    totals["D"]["raw_irrecoverable"] += 1
                if not both_fix_ok:
                    totals["D"]["both_irrecoverable"] += 1
                common_rows_fail.append((d, raw, f, r, a0, a7, fre, raw_bad,
                                         raw_exact_bad, fadj, radj, badj, refv))

        # steps
        prod_steps = infer_steps(common, pf)
        ref_steps = infer_steps(common, rf)
        for rs in ref_steps:
            ratios = []
            a0p, a0c = t0.get(rs["prev"]), t0.get(rs["date"])
            a7p, a7c = t7.get(rs["prev"]), t7.get(rs["date"])
            if a0p and a0c and a7p and a7c:
                for i in (1, 2, 3, 4):
                    if a0p[i] and a0c[i] and a7p[i] is not None and a7c[i] is not None:
                        rp = a7p[i] / a0p[i]
                        r_cur = a7c[i] / a0c[i]
                        if r_cur:
                            ratios.append(rp / r_cur)
            dev = max((abs(x / rs["ratio"] - 1.0) for x in ratios), default=None)
            rs["max_field_dev"] = dev
            rs["fields_used"] = ("open,high,low,close"
                                 if dev is not None and dev <= 1e-9 else "close")
            rs["samples"] = 1 + len(ratios)
            rs["confidence"] = ("multi_field_exact"
                                if dev is not None and dev <= 1e-9 else "close_ratio")
        matches, extra, ref_only = match_steps(prod_steps, ref_steps)
        ev_by_date = defaultdict(list)
        for e in p.get("adjustEvents") or []:
            ev_by_date[str(e.get("date"))[:10]].append(e)

        def _sig(lo, hi):
            return event_signature(
                [e for d2, lst in ev_by_date.items() if lo < d2 <= hi for e in lst])

        step_stats = defaultdict(lambda: Counter())
        for m in matches:
            if m["class"] is None:
                m["family"] = ("ALIGNED", "-", "0")
                continue
            rs, ps = m["ref"], m["prod"]
            key = (m["class"], _sig(ps["prev"], ps["date"]) or _sig(rs["prev"], rs["date"]),
                   step_error_bucket(rs["ratio"] / ps["ratio"] - 1.0))
            m["family"] = key
            step_stats[key]["steps"] += 1
            step_stats[key]["prod_ratio"] += ps["ratio"]
            step_stats[key]["ref_ratio"] += rs["ratio"]
        for rs in ref_only:
            key = ("REF_ONLY", _sig(rs["prev"], rs["date"]),
                   step_error_bucket(rs["ratio"] - 1.0))
            rs["family"] = key
            step_stats[key]["steps"] += 1
            step_stats[key]["ref_ratio"] += rs["ratio"]
        for ps in extra:
            key = ("EXTRA", _sig(ps["prev"], ps["date"]),
                   step_error_bucket(1.0 / ps["ratio"] - 1.0))
            ps["family"] = key
            step_stats[key]["steps"] += 1
            step_stats[key]["prod_ratio"] += ps["ratio"]
        corr_events = correction_events(matches, extra, ref_only)
        corr_dates = [e["date"] for e in corr_events]

        def _emit_factor(action, eff_date, target, rs=None, ps=None, cls="",
                         fam=("", "-", "0"), reason=""):
            fcw.writerow([a.correction_version, created_at,
                          "rahavard_reference_frozen_v2",
                          ("multi_field_step_inference" if rs and rs.get("fields_used") != "close"
                           else "step_inference_close"),
                          ref_sha, ins_code, aid, symbol, action, eff_date,
                          repr(target) if target is not None else "",
                          cls,
                          ps["date"] if ps else "", rs["date"] if rs else "",
                          repr(ps["ratio"]) if ps else "",
                          repr(rs["ratio"]) if rs else "",
                          fam[1], fam[2],
                          rs.get("fields_used", "") if rs else "",
                          rs.get("samples", "") if rs else "",
                          repr(rs.get("max_field_dev")) if rs and rs.get("max_field_dev") is not None else "",
                          rs.get("confidence", "") if rs else "",
                          reason])
            n_factor_corr[action] += 1

        for m in matches:
            if m["class"] is None:
                continue
            rs, ps = m["ref"], m["prod"]
            if m["class"] == "DATE_DIFF":
                _emit_factor("suppress_step", ps["date"], None, rs=rs, ps=ps,
                             cls="DATE_DIFF", fam=m["family"],
                             reason="cancel the product step at the old effective date")
                _emit_factor("replace_step", rs["date"], rs["ratio"], rs=rs, ps=ps,
                             cls="DATE_DIFF", fam=m["family"],
                             reason="apply the reference step on the reference effective date")
            else:
                _emit_factor("replace_step", rs["date"], rs["ratio"], rs=rs, ps=ps,
                             cls="RATIO_DIFF", fam=m["family"],
                             reason="reference step ratio differs from the product step")
        for rs in ref_only:
            _emit_factor("replace_step", rs["date"], rs["ratio"], rs=rs,
                         cls="REF_ONLY", fam=rs["family"],
                         reason="reference step has no product event at this date")
        for ps in extra:
            _emit_factor("suppress_step", ps["date"], None, ps=ps,
                         cls="EXTRA", fam=ps["family"],
                         reason="product step has no reference step at this date")

        # attribute every failing row to the nearest correction event above it
        for (d, raw, f, r, a0, a7, fre, raw_bad, raw_exact_bad,
             fadj, radj, badj, refv) in common_rows_fail:
            j = bisect.bisect_right(corr_dates, d)
            nearest = corr_events[j] if j < len(corr_events) else None
            corr_for_row = 1.0
            for ev in corr_events[j:]:
                corr_for_row *= ev["mult"]
            steps_above = len(corr_events) - j
            # one-step: apply only the nearest step's applicable multiplier(s)
            one_corr = 1.0
            if nearest is not None:
                sid = nearest["step"]
                for ev in corr_events:
                    if ev["step"] == sid and ev["date"] > d:
                        one_corr *= ev["mult"]
            one_adj = [(x * f * one_corr if x is not None else None) for x in raw]
            if nearest is not None:
                cls, sig, bucket = nearest["family"]
                if cls.startswith("DATE_DIFF"):
                    cls = "DATE_DIFF"
            else:
                cls, sig, bucket = "NO_STEP", "-", "0"
            one_ok = row_passes(one_adj, refv)
            all_ok = row_passes(fadj, refv)
            fam[(cls, sig, bucket)]["attributed"] += 1
            fam[(cls, sig, bucket)]["one_step_recovered"] += 1 if one_ok else 0
            fam[(cls, sig, bucket)]["all_step_recovered"] += 1 if all_ok else 0
            if r and abs(corr_for_row / (r / f) - 1.0) > 1e-9:
                totals["D"]["corr_residual_bad"] += 1
            mw.writerow([aid, symbols.get(aid) or p.get("symbol"), d, raw_bad,
                         raw_exact_bad, round(fre, 12),
                         nearest["date"] if nearest else "",
                         cls, sig, bucket, steps_above,
                         round(corr_for_row, 12),
                         1 if one_ok else 0,
                         1 if all_ok else 0,
                         1 if row_passes(radj, refv) else 0,
                         1 if row_passes(badj, refv) else 0,
                         field_flags([adj[i] for i in range(4)], refv, price_tol)])
            totals["D"]["one_step_recovered"] += 1 if one_ok else 0
            totals["D"]["all_step_recovered"] += 1 if all_ok else 0

        # W/M metrics (product aggregates all product dates; ref W direct, ref M derived)
        # Comparable variant: only paired daily dates enter the product aggregate.
        paired_base, paired_both = [], []
        for d, raw, f, r, a0, a7 in common_rows:
            c = candles[d]
            v = fnum(c.get("volume"))
            paired_base.append((d, *[(x * f if x is not None else None) for x in raw], v))
            paired_both.append((d, *[(a0[i + 1] * r if a0[i + 1] is not None else None)
                                     for i in range(4)], v))
        ref_d_all = []
        for d, a7 in sorted(t7.items()):
            c = candles.get(d)
            ref_d_all.append((d, a7[1], a7[2], a7[3], a7[4],
                              fnum(c.get("volume")) if c else None))
        wm = {}
        for tf, keyfn, ref0, ref7 in (
                ("W", week_key, {week_key(k): v for k, v in w0.items()},
                 {week_key(k): v for k, v in w7.items()}),
                ("M", month_key, ref_m.get(aid, {}).get("type0", {}),
                 ref_m.get(aid, {}).get("type7", {}))):
            variants = {
                "base": aggregate(all_daily_base, keyfn),
                "factor": aggregate(all_daily_factor, keyfn),
                "raw": aggregate(all_daily_raw, keyfn),
                "both": aggregate(all_daily_both, keyfn),
            }
            local = {}
            for name, aggv in variants.items():
                c = compare_wm(aggv, ref7)
                local[name] = c
                for k, v in c.items():
                    totals[(tf, name)][k] += v
                if name == "base":
                    cov[tf]["paired"] += sum(1 for _ in (set(aggv) & set(ref7)))
                    cov[tf]["ref_only"] += sum(1 for _ in (set(ref7) - set(aggv)))
                    cov[tf]["product_only"] += sum(1 for _ in (set(aggv) - set(ref7)))
            comp = {}
            for name, daily in (("base", paired_base), ("both", paired_both),
                                ("refd", ref_d_all)):
                aggv = aggregate(daily, keyfn)
                c = compare_wm(aggv, ref7)
                comp[name] = c
                for k, v in c.items():
                    totals[(tf + "_cmp", name)][k] += v
            wm[tf] = {
                "base_tol": local["base"]["row_tol"],
                "base_exact": local["base"]["row_exact"],
                "factor_tol": local["factor"]["row_tol"],
                "factor_exact": local["factor"]["row_exact"],
                "raw_tol": local["raw"]["row_tol"],
                "both_tol": local["both"]["row_tol"],
                "rows": local["base"]["rows"],
                "cmp_rows": comp["base"]["rows"],
                "cmp_base_tol": comp["base"]["row_tol"],
                "cmp_both_tol": comp["both"]["row_tol"],
                "cmp_refd_tol": comp["refd"]["row_tol"],
                "cmp_both_exact": comp["both"]["row_exact"],
            }

        prod_d = set(all_dates)
        ref_d = set(t0)
        cov["D"]["paired"] += len(prod_d & ref_d)
        cov["D"]["ref_only"] += len(ref_d - prod_d)
        cov["D"]["product_only"] += len(prod_d - ref_d)
        totals["D"]["rows"] += total_rows
        totals["D"]["exact"] += base_exact
        totals["D"]["tol"] += base_tol
        totals["D"]["factor_fix_tol"] += ff_tol
        totals["D"]["factor_fix_exact"] += ff_exact
        totals["D"]["raw_fix_tol"] += rf_tol
        totals["D"]["raw_fix_exact"] += rf_exact
        totals["D"]["both_fix_tol"] += bf_tol
        totals["D"]["both_fix_exact"] += bf_exact
        totals["D"]["raw_bad"] += raw_bad_rows
        totals["D"]["raw_exact_bad"] += raw_exact_bad_rows
        for k, v in exact_gap_kind.items():
            totals["D"]["exact_gap_" + k] += v
        for key, c in step_stats.items():
            fam[key]["steps"] += c["steps"]
            fam[key]["prod_ratio"] += c["prod_ratio"]
            fam[key]["ref_ratio"] += c["ref_ratio"]
        for m in matches:
            if m["class"] is None:
                continue
            fsig, fbucket = m["family"][1], m["family"][2]
            step_rows.append({"asset_id": aid, "symbol": symbols.get(aid) or p.get("symbol"),
                              "date": m["ref"]["date"], "class": m["class"],
                              "event_sig": fsig, "err_bucket": fbucket,
                              "prod_ratio": round(m["prod"]["ratio"], 12),
                              "ref_ratio": round(m["ref"]["ratio"], 12),
                              "ratio_err": round(m["ratio_err"], 12)})
        for rs in ref_only:
            fsig, fbucket = rs["family"][1], rs["family"][2]
            step_rows.append({"asset_id": aid, "symbol": symbols.get(aid) or p.get("symbol"),
                              "date": rs["date"], "class": "REF_ONLY",
                              "event_sig": fsig, "err_bucket": fbucket,
                              "prod_ratio": "", "ref_ratio": round(rs["ratio"], 12),
                              "ratio_err": round(rs["ratio"] - 1.0, 12)})
        for ps in extra:
            fsig, fbucket = ps["family"][1], ps["family"][2]
            step_rows.append({"asset_id": aid, "symbol": symbols.get(aid) or p.get("symbol"),
                              "date": ps["date"], "class": "EXTRA",
                              "event_sig": fsig, "err_bucket": fbucket,
                              "prod_ratio": round(ps["ratio"], 12), "ref_ratio": "",
                              "ratio_err": round(1.0 / ps["ratio"] - 1.0, 12)})
        per_asset.append({
            "asset_id": aid, "symbol": symbols.get(aid) or p.get("symbol"),
            "rows": total_rows, "base_exact": base_exact, "base_tol": base_tol,
            "raw_bad": raw_bad_rows, "factor_fix_tol": ff_tol, "factor_fix_exact": ff_exact,
            "raw_fix_tol": rf_tol, "both_fix_tol": bf_tol,
            "W_rows": wm["W"]["rows"], "W_base_tol": wm["W"]["base_tol"],
            "W_factor_tol": wm["W"]["factor_tol"], "W_both_tol": wm["W"]["both_tol"],
            "W_cmp_rows": wm["W"]["cmp_rows"], "W_cmp_base_tol": wm["W"]["cmp_base_tol"],
            "W_cmp_both_tol": wm["W"]["cmp_both_tol"], "W_cmp_refd_tol": wm["W"]["cmp_refd_tol"],
            "M_rows": wm["M"]["rows"], "M_base_tol": wm["M"]["base_tol"],
            "M_factor_tol": wm["M"]["factor_tol"], "M_both_tol": wm["M"]["both_tol"],
            "M_cmp_rows": wm["M"]["cmp_rows"], "M_cmp_base_tol": wm["M"]["cmp_base_tol"],
            "M_cmp_both_tol": wm["M"]["cmp_both_tol"], "M_cmp_refd_tol": wm["M"]["cmp_refd_tol"],
        })
        if len(per_asset) % 100 == 0:
            print("...", len(per_asset), "assets", flush=True)

    mf.close()
    ef.close()
    fc.close()
    rc.close()
    with open(os.path.join(a.out, "per_asset.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(per_asset[0]))
        w.writeheader()
        w.writerows(per_asset)
    with open(os.path.join(a.out, "steps.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(step_rows[0]))
        w.writeheader()
        w.writerows(step_rows)
    with open(os.path.join(a.out, "families.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["class", "event_sig", "err_bucket", "steps", "sum_prod_ratio", "sum_ref_ratio",
                    "one_step_recovered", "all_step_recovered", "tol_mismatch_rows"])
        for (cls, sig, bucket), c in sorted(fam.items(), key=lambda kv: -kv[1]["attributed"]):
            w.writerow([cls, sig, bucket, c["steps"], round(c["prod_ratio"], 6),
                        round(c["ref_ratio"], 6),
                        c["one_step_recovered"], c["all_step_recovered"],
                        c["attributed"]])
    with open(os.path.join(a.out, "coverage.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timeframe", "paired", "ref_only", "product_only"])
        for tf in ("D", "W", "M"):
            w.writerow([tf, cov[tf]["paired"], cov[tf]["ref_only"], cov[tf]["product_only"]])
    summary = {
        "reference": a.ref, "product": a.product,
        "assets_paired": len(per_asset), "assets_ref": len(ref),
        "daily": {k: totals["D"][k] for k in (
            "rows", "exact", "tol", "mismatch", "raw_bad", "raw_exact_bad",
            "factor_fix_tol", "factor_fix_exact", "raw_fix_tol", "raw_fix_exact",
            "both_fix_tol", "both_fix_exact", "primary_raw_source", "primary_factor_chain",
            "primary_raw_plus_factor", "primary_factor_irrecoverable", "primary_unexplained",
            "raw_primary_overlap", "factor_primary_overlap", "factor_irrecoverable",
            "raw_irrecoverable", "both_irrecoverable", "one_step_recovered",
            "all_step_recovered", "corr_residual_bad", "exact_gap_factor_precision",
            "exact_gap_raw_precision", "exact_gap_rounding")},
        "coverage": {tf: dict(cov[tf]) for tf in ("D", "W", "M")},
        "assets_unmatched": len(ref) - len(seen & set(ref)),
        "W": {k: totals[("W", "base")][k] for k in ("rows", "row_exact", "row_tol")},
        "M": {k: totals[("M", "base")][k] for k in ("rows", "row_exact", "row_tol")},
        "W_counterfactual": {"factor_tol": totals[("W", "factor")]["row_tol"],
                              "both_tol": totals[("W", "both")]["row_tol"],
                              "factor_exact": totals[("W", "factor")]["row_exact"],
                              "both_exact": totals[("W", "both")]["row_exact"]},
        "M_counterfactual": {"factor_tol": totals[("M", "factor")]["row_tol"],
                              "both_tol": totals[("M", "both")]["row_tol"],
                              "factor_exact": totals[("M", "factor")]["row_exact"],
                              "both_exact": totals[("M", "both")]["row_exact"]},
        "W_comparable": {
            "base": {k: totals[("W_cmp", "base")][k] for k in ("rows", "row_tol", "row_exact")},
            "both": {k: totals[("W_cmp", "both")][k] for k in ("rows", "row_tol", "row_exact")},
            "ref_d_agg": {k: totals[("W_cmp", "refd")][k] for k in ("rows", "row_tol", "row_exact")},
        },
        "M_comparable": {
            "base": {k: totals[("M_cmp", "base")][k] for k in ("rows", "row_tol", "row_exact")},
            "both": {k: totals[("M_cmp", "both")][k] for k in ("rows", "row_tol", "row_exact")},
            "ref_d_agg": {k: totals[("M_cmp", "refd")][k] for k in ("rows", "row_tol", "row_exact")},
        },
        "rf_anchor_values": dict(rf_anchor.most_common(10)),
        "field_ratio_deviation": dict(field_ratio_dev),
        "correction_version": a.correction_version,
        "created_at": created_at,
        "ref_bars_sha256": ref_sha,
        "corrections": {"factor": dict(n_factor_corr), "raw_fields": dict(n_raw_corr)},
    }
    json.dump(summary, open(os.path.join(a.out, "summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    manifest = {
        "schema": "ra365-correction-pack-v1",
        "correction_version": a.correction_version,
        "created_at": created_at,
        "tool": "tools/ra365_round32b_audit.py",
        "reference": a.ref,
        "reference_sha256": ref_sha,
        "reference_types": ["type0:raw", "type7:functional"],
        "product": a.product,
        "assets_paired": len(per_asset),
        "factor_corrections": dict(n_factor_corr),
        "raw_field_corrections": dict(n_raw_corr),
        "factor_correction_semantics": (
            "replace_step: suppress every product event on effective_date and insert one "
            "step with target_ratio; suppress_step: suppress product events on effective_date. "
            "The target ratio is derived from the frozen reference factor (type7/type0) and "
            "verified against open/high/low/close; max_field_dev records the worst field "
            "deviation. Corrections are applied after the canonical event chain, before "
            "chain_factors."),
        "raw_correction_semantics": (
            "Per-field historical value from the frozen reference type0 bar. Applied to the "
            "displayed candle only, after factor computation; corporate events are never "
            "rewritten by raw corrections."),
        "usage": ("Derived factor steps and sparse per-field corrections only; the raw "
                  "reference series is not redistributed. Source is the owner-authenticated "
                  "frozen Rahavard snapshot."),
    }
    json.dump(manifest, open(os.path.join(a.out, "correction-manifest.json"), "w",
                             encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1)[:4000])


if __name__ == "__main__":
    main()
