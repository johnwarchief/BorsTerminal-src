# -*- coding: utf-8 -*-
"""Round 23: monthly parity against Rahavard's Jalali-month bars.

Contract: Rahavard monthly bars are Jalali months (e.g. 2014-03-21 = 1
Farvardin).  The product daily series is bucketed by the Jalali month of the
candle date; open=first, high=max, low=min, close=last, volume=sum.  The
comparison pairs by (Jalali year, month), not by the bar stamp.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys_path = None
spec = importlib.util.spec_from_file_location(
    "p21", os.path.join(ROOT, "tools", "ra365_round21_live_parity.py"))
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)
spec2 = importlib.util.spec_from_file_location(
    "rp", os.path.join(ROOT, "tools", "ra_parity.py"))
R = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(R)

FIXED = {"595", "48315", "207", "325", "291", "599", "2672", "453", "149",
         "167", "182", "696", "183", "703", "462", "484", "287", "384",
         "6274", "109", "485", "7836", "16449", "17495", "569", "458",
         "159", "252", "498", "661", "302"}
HOLD = {"711", "16272", "15239", "637", "490", "500", "24691", "1771",
        "724", "60", "32", "2967", "1585", "65", "273", "7831", "20817",
        "6273", "540"}


def mkey(date_str):
    d = dt.date.fromisoformat(str(date_str)[:10])
    jy, jm, _jd = R.jalali_of(d)
    return (jy, jm)


def aggregate(rows, adjusted):
    out = {}
    for r in rows:
        k = mkey(r["date"])
        fields = (("a_open", "a_high", "a_low", "a_close") if adjusted
                  else ("open", "high", "low", "close"))
        o, h, l, c = (r.get(f) for f in fields)
        v = r.get("volume")
        if None in (o, h, l, c):
            continue
        if k not in out:
            out[k] = {"o": o, "h": h, "l": l, "c": c, "v": v or 0, "date": r["date"]}
        else:
            b = out[k]
            b["h"] = max(b["h"], h)
            b["l"] = min(b["l"], l)
            b["c"] = c
            b["v"] += v or 0
            b["date"] = r["date"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="D:/BorsTerminal-tmp/r23_live/ra365_r23_ref_50.json")
    ap.add_argument("--product", default="D:/BorsTerminal-tmp/r23_live/product_live")
    ap.add_argument("--out", default=os.path.join(ROOT, "artifacts", "ra365", "r23", "monthly.json"))
    a = ap.parse_args()
    ref_doc = json.load(open(a.ref, encoding="utf-8"))
    refm = {}
    for it in ref_doc["items"]:
        if it.get("res") != "M":
            continue
        m = {}
        for b in it.get("bars") or []:
            m[mkey(b["utc"])] = b
        refm[(str(it["asset_id"]), it["type"])] = m
    results = []
    for aid, sym in P.ASSETS.items():
        try:
            prod, meta = P.load_product(aid, a.product)
        except FileNotFoundError:
            continue
        if meta.get("priceBasis") != "last":
            continue
        for mode, rtype in (("raw", "type0"), ("adjusted", "type7")):
            rm = refm.get((aid, rtype)) or {}
            if not rm:
                continue
            pm = aggregate(prod, mode == "adjusted")
            pairs = sorted(set(pm) & set(rm))
            counts = Counter()
            errs = []
            per_field = {f: Counter() for f in "ohlcv"}
            for k in pairs:
                pv = pm[k]
                rb = rm[k]
                rv = {"o": rb["o"], "h": rb["h"], "l": rb["l"], "c": rb["c"], "v": rb["v"]}
                pvv = {"o": pv["o"], "h": pv["h"], "l": pv["l"], "c": pv["c"], "v": pv["v"]}
                for f in "ohlcv":
                    st = (P.volume_status if f == "v" else P.price_status)(rv[f], pvv[f])
                    per_field[f][st] += 1
                    if f == "c":
                        e = P.rel_err(rv[f], pvv[f])
                        if e is not None:
                            errs.append(e)
                counts["rows"] += 1
            row_ok = 0
            for k in pairs:
                pv = pm[k]; rb = rm[k]
                rv = {"o": rb["o"], "h": rb["h"], "l": rb["l"], "c": rb["c"], "v": rb["v"]}
                pvv = {"o": pv["o"], "h": pv["h"], "l": pv["l"], "c": pv["c"], "v": pv["v"]}
                if all((P.volume_status if f == "v" else P.price_status)(rv[f], pvv[f])
                       in ("EXACT", "TOLERANCE") for f in "ohlcv"):
                    row_ok += 1
            n = len(pairs)
            results.append({
                "asset_id": aid, "symbol": sym, "mode": mode,
                "paired": n, "ref_months": len(rm), "product_months": len(pm),
                "ref_only": len(set(rm) - set(pm)), "product_only": len(set(pm) - set(rm)),
                "row_tolerance": row_ok,
                "row_tolerance_pct": round(100.0 * row_ok / n, 4) if n else None,
                "close_median": P.quantile(errs, 0.5), "close_p90": P.quantile(errs, 0.9),
                "close_p95": P.quantile(errs, 0.95), "close_p99": P.quantile(errs, 0.99),
                "fields": {f: dict(per_field[f]) for f in "ohlcv"},
            })
    agg = {}
    for mode in ("raw", "adjusted"):
        rs = [r for r in results if r["mode"] == mode]
        n = sum(r["paired"] for r in rs); ok = sum(r["row_tolerance"] for r in rs)
        agg[mode] = {"series": len(rs), "paired": n,
                     "row_tolerance_pct": round(100.0 * ok / n, 4) if n else None}
    out = {"contract": "Jalali month; open=first, high=max, low=min, close=last, volume=sum",
           "reference": a.ref, "aggregate": agg, "series": results}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(agg, ensure_ascii=False, indent=1))
    for mode in ("raw", "adjusted"):
        rs = sorted([r for r in results if r["mode"] == mode], key=lambda x: -(x["row_tolerance_pct"] or 0))
        print(mode, "worst", [(r["symbol"], r["row_tolerance_pct"]) for r in rs[-5:]])


if __name__ == "__main__":
    main()
