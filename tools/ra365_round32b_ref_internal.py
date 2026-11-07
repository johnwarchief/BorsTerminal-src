#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Find strict-comparable W keys where the reference contradicts itself.

A key is strictly comparable when the product's daily date set equals the
reference daily date set.  On such a key the product's corrected daily series
is exactly the reference type7 daily series (measured separately), so the
weekly aggregate must equal the aggregation of reference type7 D.  When the
reference W bar differs from that aggregation, the reference is internally
inconsistent; the key is not a product defect and is declared, never counted
as a match.

Reads the final measurement per-asset ledger to locate failing assets, then
recomputes only those assets.  Read-only.
"""
import csv
import datetime as dt
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "artifacts", "ra365", "r32b")
REF = "D:/BorsTerminal-tmp/r26_bench/frozen/ref_bars_v2.jsonl"
PRODUCT = "D:/BorsTerminal-tmp/r32b/product_v2"
OUT = os.path.join(ART, "measure", "reference-internal-wm.csv")


def week_key(date):
    y, m, d = (int(x) for x in date.split("-"))
    day = (dt.date(y, m, d) - dt.date(1970, 1, 1)).days
    return (day - 2) // 7


def tup(b):
    if isinstance(b, dict):
        return (str(b.get("utc"))[:10], b.get("open"), b.get("high"),
                b.get("low"), b.get("close"), b.get("volume"))
    return (str(b[0])[:10], b[1], b[2], b[3], b[4], b[5] if len(b) > 5 else None)


def agg(rows):
    out = {}
    for date, o, h, l, c, v in sorted(rows):
        k = week_key(date)
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


def ok(p, r):
    return all(abs((p[i] or 0) - (r[1 + i] or 0)) <= max(0.5, 1e-6 * abs(r[1 + i] or 0))
               for i in range(4))


def main():
    failing = set()
    ledger = os.path.join(ART, "measure", "per_asset.csv")
    with open(ledger, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            if int(r["W_comp_pass"]) < int(r["W_comp_rows"]):
                failing.add(r["asset_id"])
    if not failing:
        print("no comparable W failure")
        return 0
    ref = {}
    with open(REF, encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            aid = str(d.get("asset_id"))
            if aid not in failing or d.get("res") not in ("D", "W") or d.get("type") != "type7":
                continue
            bars = {t[0]: t for t in (tup(b) for b in d.get("bars") or []) if t[0]}
            ref.setdefault(aid, {})[d["res"]] = bars
    prod = {}
    for path in glob.glob(os.path.join(PRODUCT, "shard*", "*.json")):
        d = json.load(open(path, encoding="utf-8"))
        aid = str(d.get("asset_id"))
        if aid in failing:
            prod[aid] = d
    out = []
    for aid in sorted(failing):
        d, r = prod.get(aid), ref.get(aid, {})
        if not d or "D" not in r or "W" not in r:
            continue
        fac = {str(f.get("time"))[:10]: f.get("factor") for f in d.get("factors") or []}
        rows = []
        for c in d.get("candles") or []:
            date = str(c.get("time"))[:10]
            f = fac.get(date)
            if f is None:
                continue
            raw = [c.get("open"),
                   c.get("high_raw") if c.get("high_raw") is not None else c.get("high"),
                   c.get("low_raw") if c.get("low_raw") is not None else c.get("low"),
                   c.get("last") if c.get("last") is not None else c.get("close")]
            rows.append((date, *[(x * f if x is not None else None) for x in raw],
                         c.get("volume")))
        pagg = agg(rows)
        ragg = agg([(k, v[1], v[2], v[3], v[4], v[5]) for k, v in r["D"].items()])
        w7 = {week_key(k): v for k, v in r["W"].items()}
        for k in sorted(set(pagg) & set(w7)):
            p, w, ra = pagg[k], w7[k], ragg.get(k)
            if ok(p, w):
                continue
            ref_internal = bool(ra) and not ok(ra, w)
            if not ref_internal:
                continue
            pset = sorted(x[0] for x in rows if week_key(x[0]) == k)
            rset = sorted(x for x in r["D"] if week_key(x) == k)
            if pset != rset:
                continue
            out.append({
                "asset_id": aid, "symbol": d.get("symbol"), "timeframe": "W",
                "key": k, "date_start": pset[0], "date_end": pset[-1],
                "product_ohlc": json.dumps(p[:4]),
                "reference_w_ohlc": json.dumps(w[1:5]),
                "reference_d_aggregate_ohlc": json.dumps(ra[:4] if ra else None),
                "cause": "reference_w_vs_d_contradiction",
            })
    with open(OUT, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]) if out else
                           ["asset_id", "symbol", "timeframe", "key", "date_start",
                            "date_end", "product_ohlc", "reference_w_ohlc",
                            "reference_d_aggregate_ohlc", "cause"])
        w.writeheader()
        w.writerows(out)
    print("wrote", OUT, "rows", len(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
