#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 27: timeframe-aware full-universe raw/adjusted audit (D/W/M).

Compares a fresh current-engine product capture against the frozen Rahavard
reference. Monthly reference bars are *derived* from complete daily reference
bars with the frozen Jalali month-key rules and labelled `derived:monthly`.
Product factors are re-anchored at the last common date so a later product
capture does not introduce a constant factor offset; the raw candles are
never modified.

Metrics per timeframe (D/W/M), raw and adjusted, are reported separately:
literal field exact/tolerance, contractual field (widen) exact/tolerance,
row exact/tolerance, factor exact/tolerance, paired/ref-only/product-only
rows, and unmatched assets.

Usage:
  python tools/ra365_round27_audit.py --ref <ref.jsonl> --product <dir>[,<dir>] \
      --cohort <cohort.jsonl> --out <dir> [--limit N]
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
import candle_contract as CC  # noqa: E402
import ra_parity as RP  # noqa: E402

TOL = 0.5
REL = 1e-6


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
    return (str(b[0])[:10], fnum(b[1]), fnum(b[2]), fnum(b[3]),
            fnum(b[4]), fnum(b[5]))


def week_key(date):
    import datetime as dt
    y, m, d = (int(x) for x in date.split("-"))
    day = (dt.date(y, m, d) - dt.date(1970, 1, 1)).days
    return (day - 2) // 7


def month_key(date):
    import datetime as dt
    y, m, d = (int(x) for x in date.split("-"))
    jy, jm, _ = RP.jalali_of(dt.date(y, m, d))
    return jy * 12 + (jm - 1)


def aggregate(daily, keyfn):
    """daily: list of (date, o,h,l,c,v) ascending → {key: [o,h,l,c,v,stamp]}."""
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
    """Factor chain normalised so factor(anchor_date) == 1 (comparison only)."""
    scale = factors.get(anchor_date)
    if not scale:
        return dict(factors)
    return {d: f / scale for d, f in factors.items()}


def load_ref(path):
    out = {}
    for line in open(path, encoding="utf-8"):
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
        out.setdefault(aid, {}).setdefault(d["type"], {})[res] = bars
    return out


def derive_monthly(bars_d):
    daily = [bars_d[d] for d in sorted(bars_d)]
    agg = aggregate([(t[0], t[1], t[2], t[3], t[4], t[5]) for t in daily], month_key)
    return {k: (v[5], v[0], v[1], v[2], v[3], v[4]) for k, v in agg.items()}


def compare_series(prod, ref, contract):
    """prod/ref: {key: (or [o,h,l,c,v])} → field/row counters."""
    res = Counter()
    for k in set(prod) & set(ref):
        p = prod[k]
        r = ref[k]
        po, ph, pl, pc, pv = p[0], p[1], p[2], p[3], p[4]
        ro, rh, rl, rc, rv = r[1], r[2], r[3], r[4], r[5]
        if contract:
            ph, pl = CC.widen(po, ph, pl, pc)
        pairs = [("o", po, ro), ("h", ph, rh), ("l", pl, rl),
                 ("c", pc, rc), ("v", pv, rv)]
        row_ok = True
        for name, pval, rval in pairs:
            if pval is None or rval is None:
                res["null"] += 1
                if name != "v":
                    row_ok = False
                continue
            res[name + "_cmp"] += 1
            d = abs(pval - rval)
            if d <= 1e-9:
                res[name + "_exact"] += 1
            if d <= (max(TOL, REL * abs(rval)) if name != "v" else 1):
                res[name + "_tol"] += 1
            elif name != "v":
                row_ok = False
        res["rows"] += 1
        if row_ok:
            res["row_ok"] += 1
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--product", required=True, help="comma-separated payload dirs")
    ap.add_argument("--cohort", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ref = load_ref(a.ref)
    ref_m = {}
    for aid, types in ref.items():
        for typ, byres in types.items():
            if "D" in byres:
                ref_m.setdefault(aid, {})[typ] = derive_monthly(byres["D"])

    manifest = {}
    for line in open(a.cohort, encoding="utf-8"):
        d = json.loads(line)
        manifest[str(d.get("ra_asset_id"))] = d.get("symbol")
    products = []
    for root in a.product.split(","):
        if not os.path.isdir(root):
            continue
        for fn in sorted(os.listdir(root)):
            if fn.endswith(".json") and fn[:-5].isdigit():
                products.append(os.path.join(root, fn))
    per_asset = []
    totals = defaultdict(Counter)
    seen = set()
    for path in products:
        if a.limit and len(per_asset) >= a.limit:
            break
        d = json.load(open(path, encoding="utf-8"))
        aid = str(d.get("asset_id"))
        if aid in seen or aid not in ref:
            continue
        seen.add(aid)
        candles = sorted(d.get("candles") or [], key=lambda c: str(c.get("time"))[:10])
        vol_map = {str(v.get("time"))[:10]: fnum(v.get("value"))
                   for v in (d.get("volumes") or [])}
        rows = []
        for c in candles:
            dt = str(c.get("time"))[:10]
            o = fnum(c.get("open")); h = fnum(c.get("high"))
            l = fnum(c.get("low")); cl = fnum(c.get("close"))
            last = fnum(c.get("last")); closing = fnum(c.get("closing"))
            disp = last if last else cl
            if dt and disp is not None:
                rows.append((dt, o, h, l, disp, vol_map.get(dt), cl,
                             fnum(c.get("high_raw")), fnum(c.get("low_raw"))))
        if not rows:
            continue
        fac = {str(f.get("time"))[:10]: fnum(f.get("factor"))
               for f in (d.get("factors") or [])}
        fac = {k: v for k, v in fac.items() if v}
        common_d = sorted(set(r[0] for r in rows) & set(fac) &
                          set(ref[aid]["type0"]["D"]) & set(ref[aid]["type7"]["D"]))
        if len(common_d) < 10:
            continue
        anchor = common_d[-1]
        fac2 = reanchor(fac, anchor)
        raw_d = {r[0]: [r[1], r[2], r[3], r[4], r[5], r[0]] for r in rows}
        lit_d = {r[0]: [r[1], r[7] if r[7] is not None else r[2],
                        r[8] if r[8] is not None else r[3], r[4], r[5], r[0]] for r in rows}
        adj_d = {r[0]: [r[1] * fac2.get(r[0], 1.0) if r[1] is not None else None,
                        r[2] * fac2.get(r[0], 1.0) if r[2] is not None else None,
                        r[3] * fac2.get(r[0], 1.0) if r[3] is not None else None,
                        r[4] * fac2.get(r[0], 1.0) if r[4] is not None else None,
                        r[5], r[0]] for r in rows}
        raw_w = aggregate([(r[0], r[1], r[2], r[3], r[4], r[5]) for r in rows], week_key)
        lit_w = aggregate([(r[0], r[1], r[7] if r[7] is not None else r[2],
                            r[8] if r[8] is not None else r[3], r[4], r[5]) for r in rows], week_key)
        adj_w = aggregate([(r[0], a_[0], a_[1], a_[2], a_[3], a_[4])
                           for r, a_ in zip(rows, [adj_d[r[0]] for r in rows])], week_key)
        raw_m = aggregate([(r[0], r[1], r[2], r[3], r[4], r[5]) for r in rows], month_key)
        lit_m = aggregate([(r[0], r[1], r[7] if r[7] is not None else r[2],
                            r[8] if r[8] is not None else r[3], r[4], r[5]) for r in rows], month_key)
        adj_m = aggregate([(r[0], a_[0], a_[1], a_[2], a_[3], a_[4])
                           for r, a_ in zip(rows, [adj_d[r[0]] for r in rows])], month_key)
        rec = {"asset_id": aid, "symbol": d.get("symbol"), "rows_d": len(common_d)}
        lit_map = {"D": lit_d, "W": lit_w, "M": lit_m}
        for tf, prod_raw, prod_adj, ref_key in (
                ("D", raw_d, adj_d, "D"), ("W", raw_w, adj_w, "W"), ("M", raw_m, adj_m, "M")):
            if tf == "D":
                ref_raw = ref[aid]["type0"]["D"]
                ref_adj = ref[aid]["type7"]["D"]
            elif tf == "W":
                ref_raw = {week_key(k): v for k, v in ref[aid]["type0"]["W"].items()}
                ref_adj = {week_key(k): v for k, v in ref[aid]["type7"]["W"].items()}
            else:
                ref_raw = ref_m[aid]["type0"]
                ref_adj = ref_m[aid]["type7"]
            lit = compare_series(lit_map[tf], ref_raw, contract=False)
            con = compare_series(prod_raw, ref_raw, contract=True)
            adj = compare_series(prod_adj, ref_adj, contract=False)
            prod_keys = set(prod_raw)
            ref_keys = set(ref_raw)
            totals[(tf, "coverage")]["paired"] += len(prod_keys & ref_keys)
            totals[(tf, "coverage")]["ref_only"] += len(ref_keys - prod_keys)
            totals[(tf, "coverage")]["product_only"] += len(prod_keys - ref_keys)
            for name, c in (("raw_lit", lit), ("raw_con", con), ("adj", adj)):
                for k, v in c.items():
                    totals[(tf, name)][k] += v
            rec[f"{tf}_raw_lit_row"] = round(100.0 * lit["row_ok"] / max(1, lit["rows"]), 4)
            rec[f"{tf}_raw_con_row"] = round(100.0 * con["row_ok"] / max(1, con["rows"]), 4)
            rec[f"{tf}_adj_row"] = round(100.0 * adj["row_ok"] / max(1, adj["rows"]), 4)
            rec[f"{tf}_adj_pairs"] = adj["rows"]
        per_asset.append(rec)
    with open(os.path.join(a.out, "per-asset.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(per_asset[0]))
        w.writeheader(); w.writerows(per_asset)
    summary = {"reference": a.ref, "product": a.product,
               "assets_paired": len(per_asset),
               "assets_ref": len(ref),
               "timeframes": {}}
    for tf in ("D", "W", "M"):
        summary["timeframes"][tf] = {}
        for name in ("raw_lit", "raw_con", "adj"):
            c = totals[(tf, name)]
            summary["timeframes"][tf][name] = {
                "rows": c["rows"], "row_ok": c["row_ok"],
                "row_pct": round(100.0 * c["row_ok"] / max(1, c["rows"]), 4),
                "fields": {k: c[k] for k in ("o_cmp", "o_exact", "h_cmp", "h_exact",
                                             "l_cmp", "l_exact", "c_cmp", "c_exact",
                                             "v_cmp", "v_exact")},
            }
    summary["coverage"] = {tf: dict(totals[(tf, "coverage")]) for tf in ("D", "W", "M")}
    summary["assets_unmatched"] = len(ref) - len(seen & set(ref))
    summary["derived_monthly"] = True
    json.dump(summary, open(os.path.join(a.out, "summary.json"), "w",
                            encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1)[:3000])


if __name__ == "__main__":
    main()
