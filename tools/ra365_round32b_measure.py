#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 32B: before/after measurement of the frozen RA365 corpus.

The baseline side is the Round 31 contract unchanged (same pairing, same
re-anchoring, same 0.5-rial / 1e-6 tolerance, same 1e-9 exact test).  The
corrected side applies the versioned correction pack in memory:

  * factor steps: replace/suppress by effective date, then rebuild the chain;
  * raw OHLC: per-field historical values on the display candle.

W/M are reported twice:

  * canonical: product aggregate over every product daily date (the R31 sensor);
  * strictly comparable: keys whose product daily date set equals the
    reference daily date set.  On those keys the reference W/M is exactly the
    aggregation of its own daily bars (measured as a control), so a 100%
    result is meaningful.  Keys with missing or extra product days are listed
    separately and never counted as matches.

Usage:
  python tools/ra365_round32b_measure.py \
      --ref D:/BorsTerminal-tmp/r26_bench/frozen/ref_bars_v2.jsonl \
      --product D:/.../full_shard0,... \
      --cohort D:/BorsTerminal-tmp/ra365_round18/cohort.jsonl \
      --pack data/ra365_corrections/ra365-r32b-v1 \
      --out D:/BorsTerminal-tmp/r32b/measure [--limit N]
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import adjustment_corrections as AC  # noqa: E402
from ra365_round32b_audit import (  # noqa: E402
    EXACT, TOL, REL, aggregate, derive_monthly, fnum, load_ref, month_key,
    product_files, reanchor, row_exact, row_passes, week_key,
)


def chain_factors(times, events):
    """factor(t) = product(ratio for event.date > t); deterministic, no DB."""
    evs = []
    for e in events or []:
        d = str(e.get("date") or "")[:10]
        r = fnum(e.get("ratio"))
        if d and r is not None and r > 0:
            evs.append((d, r))
    evs.sort()
    out = {}
    f, j = 1.0, len(evs) - 1
    for t in sorted(set(times), reverse=True):
        while j >= 0 and evs[j][0] > t:
            f *= evs[j][1]
            j -= 1
        out[t] = f
    return out


def raw_row(c):
    if not c:
        return [None, None, None, None], None
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
    return [o, hi, lo, cl], fnum(c.get("volume"))


def key_pass(p, r):
    for i in range(4):
        pv, rv = p[i], r[i + 1]
        if pv is None or rv is None:
            return False
        if abs(pv - rv) > max(TOL, REL * abs(rv)):
            return False
    return True


def key_exact(p, r):
    for i in range(4):
        pv, rv = p[i], r[i + 1]
        if pv is None or rv is None or abs(pv - rv) > EXACT:
            return False
    return True


def wm_split(prod_agg, ref_bars, comp_keys, missing_map, extra_map):
    c = Counter()
    for k in set(prod_agg) & set(ref_bars):
        p, r = prod_agg[k], ref_bars[k]
        ok = key_pass(p, r)
        ex = key_exact(p, r)
        c["rows"] += 1
        if k in comp_keys:
            c["comp_rows"] += 1
            c["comp_pass"] += 1 if ok else 0
            c["comp_exact"] += 1 if ex else 0
        else:
            c["noncomp_rows"] += 1
            c["noncomp_pass"] += 1 if ok else 0
    return c


def build_date_sets(dates, keyfn):
    out = defaultdict(set)
    for d in dates:
        out[keyfn(d)].add(d)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--product", required=True)
    ap.add_argument("--cohort", required=True)
    ap.add_argument("--pack", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    if a.pack:
        os.environ["BORS_CORRECTIONS_DIR"] = a.pack
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

    totals = defaultdict(Counter)
    noncomp_rows = []
    factor_residual_rows = []
    raw_residual_rows = []
    daily_residual_rows = []
    per_asset = []
    seen = set()

    for path in product_files(a.product.split(",")):
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
        w7 = ref[aid].get("type7", {}).get("W") or {}
        if not t0 or not t7:
            continue
        candles = {str(c.get("time"))[:10]: c for c in p.get("candles") or []}
        fac = {str(f.get("time"))[:10]: fnum(f.get("factor"))
               for f in (p.get("factors") or [])}
        fac = {k: v for k, v in fac.items() if v}
        events = p.get("adjustEvents") or []
        common = sorted(set(candles) & set(fac) & set(t0) & set(t7))
        if len(common) < 10:
            continue
        all_dates = sorted(set(candles) & set(fac))
        if not all_dates:
            continue
        # baseline
        pf_base = reanchor(fac, common[-1])
        # corrected
        events_corr, suppressed, cm = AC.apply_factor_events(symbol, events, ins_code)
        fac_corr = chain_factors(all_dates, events_corr)
        pf_corr = reanchor(fac_corr, common[-1])
        candles_corr = {d: dict(c) for d, c in candles.items()}
        raw_applied, raw_meta = AC.apply_raw_candles(symbol, [candles_corr[d] for d in all_dates], ins_code)
        # reference factor
        rf = {}
        for d in common:
            a0, a7 = t0.get(d), t7.get(d)
            if a0 and a7 and a0[4] and a7[4]:
                rf[d] = a7[4] / a0[4]
        # factor residual (corrected chain vs reference factor)
        asset_factor_residual = 0
        for d in common:
            if d in rf and (not pf_corr.get(d) or abs(pf_corr[d] / rf[d] - 1.0) > 1e-9):
                asset_factor_residual += 1
                factor_residual_rows.append([aid, symbol, d, pf_corr.get(d), rf[d]])
        # daily baseline / corrected, raw residual
        base_daily = []
        corr_daily = []
        paired_base = []
        paired_corr = []
        base_exact = base_tol = corr_exact = corr_tol = 0
        raw_bad = 0
        for d in all_dates:
            raw, v = raw_row(candles[d])
            raw_c, _ = raw_row(candles_corr[d])
            f = pf_base.get(d)
            fc = pf_corr.get(d)
            if f is not None:
                base_daily.append((d, *[(x * f if x is not None else None) for x in raw], v))
            if fc is not None:
                corr_daily.append((d, *[(x * fc if x is not None else None) for x in raw_c], v))
            if d in common:
                a0, a7 = t0[d], t7[d]
                ref_raw = [a0[1], a0[2], a0[3], a0[4]]
                refv = [a7[1], a7[2], a7[3], a7[4]]
                b_adj = [(raw[i] * f if raw[i] is not None and f else None) for i in range(4)]
                c_adj = [(raw_c[i] * fc if raw_c[i] is not None and fc else None) for i in range(4)]
                if row_exact(b_adj, refv):
                    base_exact += 1
                if row_passes(b_adj, refv):
                    base_tol += 1
                if row_exact(c_adj, refv):
                    corr_exact += 1
                if row_passes(c_adj, refv):
                    corr_tol += 1
                if any(raw_c[i] is not None and ref_raw[i] is not None
                       and abs(raw_c[i] - ref_raw[i]) > EXACT for i in range(4)):
                    raw_bad += 1
                    raw_residual_rows.append([aid, symbol, d, raw_c, ref_raw])
                if not row_passes(c_adj, refv):
                    daily_residual_rows.append([aid, symbol, d, c_adj, refv])
                paired_base.append((d, *b_adj, v))
                paired_corr.append((d, *c_adj, v))
        # W/M
        wm = {}
        for tf, keyfn, ref7 in (
                ("W", week_key, {week_key(k): v for k, v in w7.items()}),
                ("M", month_key, ref_m.get(aid, {}).get("type7", {}))):
            prod_keys = build_date_sets(all_dates, keyfn)
            ref_keys = build_date_sets(t0, keyfn)
            comp_keys = {k for k in prod_keys if prod_keys[k] == ref_keys.get(k, set())}
            missing = {k: sorted(ref_keys.get(k, set()) - prod_keys.get(k, set()))
                       for k in ref_keys if not ref_keys[k] <= prod_keys.get(k, set())}
            extra = {k: sorted(prod_keys.get(k, set()) - ref_keys.get(k, set()))
                     for k in prod_keys if not prod_keys[k] <= ref_keys.get(k, set())}
            base_agg = aggregate(base_daily, keyfn)
            corr_agg = aggregate(corr_daily, keyfn)
            paired_agg = aggregate(paired_corr, keyfn)
            c_base = wm_split(base_agg, ref7, comp_keys, missing, extra)
            c_corr = wm_split(corr_agg, ref7, comp_keys, missing, extra)
            c_pair = wm_split(paired_agg, ref7, comp_keys, missing, extra)
            for pref, c in (("base", c_base), ("corr", c_corr), ("pair", c_pair)):
                for k2, v in c.items():
                    totals[(tf, pref)][k2] += v
            # non-comparable key details (sample all keys for the CSV)
            for k in sorted(set(ref7) & set(corr_agg)):
                if k in comp_keys:
                    continue
                pp, rr = corr_agg[k], ref7[k]
                noncomp_rows.append({
                    "asset_id": aid, "symbol": symbol, "timeframe": tf, "key": k,
                    "prod_days": len(prod_keys.get(k, ())),
                    "ref_days": len(ref_keys.get(k, ())),
                    "missing_days": len(missing.get(k, ())),
                    "extra_days": len(extra.get(k, ())),
                    "corrected_pass": 1 if key_pass(pp, rr) else 0,
                    "reason": ("both" if missing.get(k) and extra.get(k) else
                               "missing_product_days" if missing.get(k) else "extra_product_days"),
                })
            wm[tf] = {
                "base_comp_pass": c_base["comp_pass"], "base_comp_rows": c_base["comp_rows"],
                "corr_canonical_pass": c_corr["comp_pass"] + c_corr["noncomp_pass"],
                "corr_canonical_rows": c_corr["rows"],
                "corr_comp_pass": c_corr["comp_pass"], "corr_comp_rows": c_corr["comp_rows"],
                "corr_comp_exact": c_corr["comp_exact"],
                "corr_noncomp_rows": c_corr["noncomp_rows"],
                "corr_noncomp_pass": c_corr["noncomp_pass"],
                "pair_comp_pass": c_pair["comp_pass"], "pair_comp_rows": c_pair["comp_rows"],
                "pair_noncomp_pass": c_pair["noncomp_pass"],
                "pair_rows": c_pair["rows"],
            }
        totals["D"]["rows"] += len(common)
        totals["D"]["base_exact"] += base_exact
        totals["D"]["base_tol"] += base_tol
        totals["D"]["corr_exact"] += corr_exact
        totals["D"]["corr_tol"] += corr_tol
        totals["D"]["raw_bad"] += raw_bad
        totals["D"]["raw_applied"] += raw_applied
        totals["D"]["factor_residual"] += asset_factor_residual
        per_asset.append({
            "asset_id": aid, "symbol": symbol, "rows": len(common),
            "base_exact": base_exact, "base_tol": base_tol,
            "corr_exact": corr_exact, "corr_tol": corr_tol, "raw_bad": raw_bad,
            "W_comp_rows": wm["W"]["corr_comp_rows"],
            "W_comp_pass": wm["W"]["corr_comp_pass"],
            "W_noncomp_rows": wm["W"]["corr_noncomp_rows"],
            "W_noncomp_pass": wm["W"]["corr_noncomp_pass"],
            "M_comp_rows": wm["M"]["corr_comp_rows"],
            "M_comp_pass": wm["M"]["corr_comp_pass"],
            "M_noncomp_rows": wm["M"]["corr_noncomp_rows"],
            "M_noncomp_pass": wm["M"]["corr_noncomp_pass"],
            "factor_corr": cm.get("replace_steps", 0) if cm.get("covered") else 0,
            "factor_suppress": cm.get("suppress_steps", 0) if cm.get("covered") else 0,
            "raw_corr": raw_applied,
        })
        if len(per_asset) % 100 == 0:
            print("...", len(per_asset), "assets", flush=True)

    with open(os.path.join(a.out, "per_asset.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(per_asset[0]))
        w.writeheader()
        w.writerows(per_asset)
    with open(os.path.join(a.out, "noncomparable_wm.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(noncomp_rows[0]) if noncomp_rows else
                           ["asset_id", "symbol", "timeframe", "key", "prod_days",
                            "ref_days", "missing_days", "extra_days",
                            "corrected_pass", "reason"])
        w.writeheader()
        w.writerows(noncomp_rows)
    with open(os.path.join(a.out, "daily_residual.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["asset_id", "symbol", "date", "corrected", "reference"])
        w.writerows(daily_residual_rows)
    with open(os.path.join(a.out, "factor_residual.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["asset_id", "symbol", "date", "corrected_factor", "reference_factor"])
        w.writerows(factor_residual_rows)
    with open(os.path.join(a.out, "raw_residual.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["asset_id", "symbol", "date", "corrected_raw", "reference_raw"])
        w.writerows(raw_residual_rows)
    summary = {
        "reference": a.ref, "product": a.product, "pack": a.pack,
        "assets_paired": len(per_asset),
        "daily": {
            "rows": totals["D"]["rows"],
            "base_exact": totals["D"]["base_exact"],
            "base_tol": totals["D"]["base_tol"],
            "base_exact_pct": round(100.0 * totals["D"]["base_exact"] / max(1, totals["D"]["rows"]), 4),
            "base_tol_pct": round(100.0 * totals["D"]["base_tol"] / max(1, totals["D"]["rows"]), 4),
            "corrected_exact": totals["D"]["corr_exact"],
            "corrected_tol": totals["D"]["corr_tol"],
            "corrected_exact_pct": round(100.0 * totals["D"]["corr_exact"] / max(1, totals["D"]["rows"]), 4),
            "corrected_tol_pct": round(100.0 * totals["D"]["corr_tol"] / max(1, totals["D"]["rows"]), 4),
            "raw_bad_after": totals["D"]["raw_bad"],
            "raw_applied": totals["D"]["raw_applied"],
            "factor_residual": totals["D"]["factor_residual"],
            "daily_residual": len(daily_residual_rows),
        },
        "W": {k: totals[("W", "corr")][k] for k in (
            "rows", "comp_rows", "comp_pass", "comp_exact", "noncomp_rows", "noncomp_pass")},
        "M": {k: totals[("M", "corr")][k] for k in (
            "rows", "comp_rows", "comp_pass", "comp_exact", "noncomp_rows", "noncomp_pass")},
        "W_baseline": {k: totals[("W", "base")][k] for k in ("rows", "comp_rows", "comp_pass")},
        "M_baseline": {k: totals[("M", "base")][k] for k in ("rows", "comp_rows", "comp_pass")},
        "noncomparable": {
            "W": {"rows": len([r for r in noncomp_rows if r["timeframe"] == "W"]),
                  "missing": len([r for r in noncomp_rows if r["timeframe"] == "W" and r["missing_days"]]),
                  "extra": len([r for r in noncomp_rows if r["timeframe"] == "W" and r["extra_days"]])},
            "M": {"rows": len([r for r in noncomp_rows if r["timeframe"] == "M"]),
                  "missing": len([r for r in noncomp_rows if r["timeframe"] == "M" and r["missing_days"]]),
                  "extra": len([r for r in noncomp_rows if r["timeframe"] == "M" and r["extra_days"]])},
        },
    }
    json.dump(summary, open(os.path.join(a.out, "summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1)[:5000])


if __name__ == "__main__":
    main()
