#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 28: aligned factor-chain debugger for one symbol.

Prints every step from either side (product factor or reference type7/type0),
aligned by date, with the product events on that date, the step ratios, the
running product/reference factor offset and the adjusted-row status. This is
the P2 evidence table; it does not change anything.

Usage:
  python tools/ra365_round28_chain_debug.py --payload <json> --ref <ref.jsonl> \
      --out <dir>
"""
import argparse
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOL = 0.5
REL = 1e-6


def fnum(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--payload", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    p = json.load(open(a.payload, encoding="utf-8"))
    aid = str(p.get("asset_id"))
    ref = {}
    for line in open(a.ref, encoding="utf-8"):
        d = json.loads(line)
        if str(d.get("asset_id")) != aid or d.get("res") != "D":
            continue
        bars = {}
        for b in d.get("bars") or []:
            if isinstance(b, dict):
                dt = str(b.get("utc"))[:10]
                vals = (b.get("open"), b.get("high"), b.get("low"),
                        b.get("close"), b.get("volume"))
            else:
                dt = str(b[0])[:10]
                vals = (b[1], b[2], b[3], b[4], b[5])
            if dt:
                bars[dt] = tuple(fnum(x) for x in vals)
        ref[d["type"]] = bars
    t0, t7 = ref.get("type0") or {}, ref.get("type7") or {}
    candles = {str(c.get("time"))[:10]: c for c in (p.get("candles") or [])}
    pf = {str(f.get("time"))[:10]: fnum(f.get("factor"))
          for f in (p.get("factors") or [])}
    pf = {k: v for k, v in pf.items() if v}
    events = {}
    for e in p.get("adjustEvents") or []:
        events.setdefault(str(e.get("date"))[:10], []).append(e)
    dates = sorted(set(pf) & set(t0) & set(t7))
    rows = []
    fprod0 = pf[dates[0]] if dates else 1
    fref0 = (t7[dates[0]][3] / t0[dates[0]][3]) if dates else 1
    for prev, cur in zip(dates, dates[1:]):
        sp = pf[prev] / pf[cur]
        sr = (t7[prev][3] / t0[prev][3]) / (t7[cur][3] / t0[cur][3])
        p_step = abs(sp - 1) > 1e-7
        r_step = abs(sr - 1) > 1e-7
        if not p_step and not r_step:
            continue
        cls = ("RATIO_DIFF" if p_step and r_step else
               "REF_ONLY" if r_step else "EXTRA")
        if cls == "RATIO_DIFF" and abs(sr / sp - 1) <= 1e-4:
            continue
        close = candles.get(cur, {}).get("close")
        ref_close = t0[cur][3] if cur in t0 else None
        implied = (ref_close * (1.0 / sr - 1.0)) if (sr and sr < 1 and ref_close) else None
        offset = (t7[cur][3] / t0[cur][3]) / pf[cur] if pf.get(cur) and t0.get(cur) else None
        rows.append({
            "date": cur, "class": cls, "prod_ratio": round(sp, 10),
            "ref_ratio": round(sr, 10), "err": round(sr / sp - 1, 8),
            "prod_factor": round(pf[cur], 10),
            "ref_factor": round(t7[cur][3] / t0[cur][3], 10) if cur in t0 and cur in t7 else "",
            "offset": round(offset, 8) if offset else "",
            "product_close": close, "ref_close": ref_close,
            "implied_ref_dps": round(implied, 4) if implied is not None else "",
            "events": [(e.get("source"), e.get("ratio"), e.get("dividend_per_share"))
                       for e in events.get(cur, [])],
        })
    out = os.path.join(a.out, "chain-%s.csv" % aid)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print(json.dumps({"symbol": p.get("symbol"), "asset_id": aid,
                      "steps": len(rows),
                      "extras": sum(1 for r in rows if r["class"] == "EXTRA"),
                      "ref_only": sum(1 for r in rows if r["class"] == "REF_ONLY"),
                      "ratio_diff": sum(1 for r in rows if r["class"] == "RATIO_DIFF"),
                      "first_offset": rows[0]["offset"] if rows else None,
                      "last_offset": rows[-1]["offset"] if rows else None,
                      "out": out}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
