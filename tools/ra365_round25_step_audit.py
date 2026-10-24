#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 25 P0: attribute adjusted-parity errors to the step that causes them.

For each symbol, compare the product's factor path with the reference's
(type7/type0) and split every step into:
  * RATIO_DIFF  — both sides step on the same date, ratios differ;
  * REF_ONLY    — the reference steps, the product does not;
  * EXTRA       — the product steps, the reference does not.
Every failing row is attributed to the nearest mismatched step *after* it
(the factor only contains events after the row). DPS rows are additionally
solved for the implied reference DPS, which separates a gross/net definition
from a plain ratio error.

Usage:
  python tools/ra365_round25_step_audit.py \
      --ref D:/BorsTerminal-tmp/r23_live/ra365_r23_ref_50.json \
      --product D:/BorsTerminal-tmp/r24_bench/product_rows2 \
      --out D:/BorsTerminal-tmp/r25_bench/step_audit
"""
import argparse
import csv
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOL = 0.5            # row tolerance: max(0.5, 1e-6*|ref|)
REL = 1e-6


def fnum(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def load_ref(path):
    doc = json.load(open(path, encoding="utf-8"))
    out = {}
    for it in doc["items"]:
        bars = sorted(it.get("bars") or [], key=lambda b: b["utc"][:10])
        out[(str(it["asset_id"]), it["type"], it["res"])] = bars
    return out


def ref_factors(series, aid):
    t0 = series.get((aid, "type0", "D")) or []
    t7 = series.get((aid, "type7", "D")) or []
    raw = {b["utc"][:10]: fnum(b.get("c")) for b in t0}
    adj = {b["utc"][:10]: fnum(b.get("c")) for b in t7}
    out = {}
    for d, r in raw.items():
        a = adj.get(d)
        if r and a:
            out[d] = a / r
    return out, raw, adj


def load_product(path):
    d = json.load(open(path, encoding="utf-8"))
    candles = sorted(d.get("candles") or [], key=lambda c: str(c.get("time"))[:10])
    close = {}
    for c in candles:
        date = str(c.get("time"))[:10]
        v = fnum(c.get("closing"))
        if v is None:
            v = fnum(c.get("close"))
        if date and v is not None:
            close[date] = v
    factors = {str(f.get("time"))[:10]: fnum(f.get("factor"))
               for f in (d.get("factors") or [])}
    factors = {k: v for k, v in factors.items() if v}
    events = [e for e in (d.get("adjustEvents") or []) if e.get("date")]
    return d, close, factors, events


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--product", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    series = load_ref(a.ref)
    assets = sorted({k[0] for k in series if k[2] == "D"})
    symbols = {}
    for fn in os.listdir(a.product):
        if fn.endswith(".json"):
            d = json.load(open(os.path.join(a.product, fn), encoding="utf-8"))
            symbols[str(d["asset_id"])] = d.get("symbol_request") or fn
    steps_csv = open(os.path.join(a.out, "steps.csv"), "w", encoding="utf-8-sig", newline="")
    sw = csv.writer(steps_csv)
    sw.writerow(["symbol", "asset_id", "date", "class", "step_prod", "step_ref",
                 "ratio_err", "implied_dps", "official_dps", "rows_before"])
    rows_csv = open(os.path.join(a.out, "error_rows.csv"), "w", encoding="utf-8-sig", newline="")
    rw = csv.writer(rows_csv)
    rw.writerow(["symbol", "asset_id", "date", "field", "ref", "prod", "rel",
                 "attributed_class", "attributed_date"])
    totals = {"RATIO_DIFF": 0, "REF_ONLY": 0, "EXTRA": 0, "UNATTRIBUTED": 0}
    step_counts = {"RATIO_DIFF": 0, "REF_ONLY": 0, "EXTRA": 0}
    dps_rows = []
    per_symbol = []
    for aid in assets:
        if aid not in symbols:
            continue
        sym = symbols[aid]
        prod_doc, close, fprod, events = load_product(os.path.join(a.product, aid + ".json"))
        fref, raw_ref, adj_ref = ref_factors(series, aid)
        common = sorted(set(fprod) & set(fref) & set(close))
        if len(common) < 10:
            continue
        # steps on consecutive common dates
        steps = []  # (date, class, step_prod, step_ref)
        for prev, cur in zip(common, common[1:]):
            sp = fprod[prev] / fprod[cur]
            sr = fref[prev] / fref[cur]
            p_step = abs(sp - 1) > 1e-7
            r_step = abs(sr - 1) > 1e-7
            if not p_step and not r_step:
                continue
            if p_step and r_step:
                if abs(sr / sp - 1) <= 1e-4:
                    continue
                cls = "RATIO_DIFF"
            elif r_step:
                cls = "REF_ONLY"
            else:
                cls = "EXTRA"
            step_counts[cls] += 1
            dps = None
            for e in events:
                if str(e.get("date"))[:10] == cur and e.get("dividend_per_share") is not None:
                    dps = fnum(e["dividend_per_share"])
                    break
            implied = None
            if dps is not None and sr and sr > 0:
                implied = close[cur] * (1.0 / sr - 1.0) if sr < 1 else None
            steps.append((cur, cls, sp, sr, implied, dps))
            sw.writerow([sym, aid, cur, cls, round(sp, 10), round(sr, 10),
                         round(sr / sp - 1, 8) if sp else "",
                         "" if implied is None else round(implied, 4),
                         "" if dps is None else dps,
                         sum(1 for t in common if t < cur)])
            if implied is not None and dps:
                dps_rows.append((sym, cur, dps, implied, implied / dps, sr / sp - 1))
        # row attribution
        attributed = {"RATIO_DIFF": 0, "REF_ONLY": 0, "EXTRA": 0, "UNATTRIBUTED": 0}
        for d in common:
            rf = raw_ref.get(d)
            if not rf:
                continue
            pf = fprod[d] * close[d]
            ref_adj = adj_ref.get(d, rf * fref[d])
            diff = abs(pf - ref_adj)
            if diff <= max(TOL, REL * abs(ref_adj)):
                continue
            # nearest mismatched step after this row
            nxt = None
            for st in steps:
                if st[0] > d:
                    nxt = st
                    break
            cls = nxt[1] if nxt else "UNATTRIBUTED"
            attributed[cls] += 1
            totals[cls] += 1
            rw.writerow([sym, aid, d, "close", round(ref_adj, 6), round(pf, 6),
                         round(diff / abs(ref_adj), 8) if ref_adj else "",
                         cls, nxt[0] if nxt else ""])
        per_symbol.append({"symbol": sym, "asset_id": aid, "rows": len(common),
                           "errors": sum(attributed.values()), **attributed,
                           "steps": len(steps)})
    steps_csv.close()
    rows_csv.close()
    all_err = sum(totals.values())
    summary = {
        "reference": a.ref,
        "product": a.product,
        "symbols": len(per_symbol),
        "steps": step_counts,
        "error_rows": totals,
        "error_rows_total": all_err,
        "share": {k: round(v / all_err, 6) if all_err else 0 for k, v in totals.items()},
        "dps": {
            "events": len(dps_rows),
            "implied_over_official": sorted(round(r[4], 4) for r in dps_rows),
            "samples": [{"symbol": s, "date": d, "official": o, "implied": round(i, 2),
                         "ratio": round(r, 4), "step_err": round(e, 6)}
                        for s, d, o, i, r, e in dps_rows[:40]],
        },
        "per_symbol": per_symbol,
    }
    json.dump(summary, open(os.path.join(a.out, "summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps({k: summary[k] for k in ("symbols", "steps", "error_rows", "share")},
                     ensure_ascii=False, indent=1))
    print("DPS events:", len(dps_rows))
    if dps_rows:
        import statistics
        rr = [x[4] for x in dps_rows]
        print("implied/official median %.4f min %.4f max %.4f" %
              (statistics.median(rr), min(rr), max(rr)))


if __name__ == "__main__":
    main()
