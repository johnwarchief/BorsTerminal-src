# -*- coding: utf-8 -*-
"""Round 21: pair Rahavard type7/type0 factor steps with the product factor steps.

A "step" is a date where the back-adjustment factor changes by more than 1e-4.
Reference step date = first bar whose factor differs from the previous bar.
Product step date = first bar whose factor differs from the previous bar.

Pairs are matched by date within --window days (nearest wins). Unmatched steps
are classified REF_ONLY / PRODUCT_ONLY. Paired steps are compared by ratio.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE = os.environ.get("RA365_R21_LIVE", "D:/BorsTerminal-tmp/r21_live")
PROD = os.environ.get("RA365_R21_PRODUCT", os.path.join(LIVE, "product_live_after"))
OUT = os.path.join(ROOT, "artifacts", "ra365", "r21")
ASSETS = {
    "595": "حخزر", "48315": "آکو", "207": "لخزر", "325": "هجرت",
    "291": "ومعادن", "599": "ولانا", "2672": "طلا", "453": "فولاد",
    "149": "فنوال", "167": "خودرو", "182": "شنفت", "696": "شراز",
    "183": "شبهرن", "703": "فارس",
}


def d(s):
    return dt.date.fromisoformat(s)


def factor_map(bars):
    return {b["utc"][:10]: (b["c"] / b["o"]) if False else None for b in bars}


def ref_factors(r0, r7):
    m = {}
    for date, b7 in r7.items():
        b0 = r0.get(date)
        if not b0 or not b0.get("c"):
            continue
        m[date] = b7["c"] / b0["c"]
    return m


def steps(m, thresh=1e-4):
    ds = sorted(m)
    out = []
    for i in range(1, len(ds)):
        a, b = m[ds[i - 1]], m[ds[i]]
        if a and b and abs(b / a - 1.0) > thresh:
            out.append({"date": ds[i], "ratio": b / a, "prev_factor": a, "factor": b})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=7)
    ap.add_argument("--threshold", type=float, default=0.005, help="ratio match band")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ref = json.load(open(os.path.join(LIVE, "ra365_r21_ref_live.json"), encoding="utf-8"))
    series = {}
    for it in ref["items"]:
        series[(str(it["asset_id"]), it["type"], it["res"])] = {
            b["utc"][:10]: b for b in (it.get("bars") or [])}
    rows = []
    summary = {}
    for aid, sym in ASSETS.items():
        p = os.path.join(PROD, aid + ".json")
        if not os.path.exists(p):
            continue
        prod = json.load(open(p, encoding="utf-8"))
        pf = {str(f["time"])[:10]: float(f["factor"]) for f in (prod.get("factors") or [])}
        r0 = series.get((aid, "type0", "D")) or {}
        r7 = series.get((aid, "type7", "D")) or {}
        if not r0 or not r7:
            continue
        rf = ref_factors(r0, r7)
        rs = steps(rf)
        ps = steps(pf)
        used = set()
        counts = Counter()
        for st in rs:
            cand = []
            for i, pt in enumerate(ps):
                if i in used:
                    continue
                diff = abs((d(pt["date"]) - d(st["date"])).days)
                if diff <= a.window:
                    cand.append((diff, i, pt))
            if cand:
                diff, i, pt = min(cand)
                used.add(i)
                rel = abs(pt["ratio"] / st["ratio"] - 1.0)
                if rel <= a.threshold:
                    cls = "MATCH"
                elif rel <= 0.02:
                    cls = "CLOSE"
                else:
                    cls = "RATIO_DIFF"
                counts[cls] += 1
                rows.append([aid, sym, "REF", st["date"], round(st["ratio"], 8),
                             pt["date"], round(pt["ratio"], 8), diff, f"{rel:.8f}", cls, ""])
            else:
                counts["REF_ONLY"] += 1
                rows.append([aid, sym, "REF", st["date"], round(st["ratio"], 8),
                             "", "", "", "", "REF_ONLY", ""])
        for i, pt in enumerate(ps):
            if i in used:
                continue
            counts["PRODUCT_ONLY"] += 1
            rows.append([aid, sym, "PROD", "", "", pt["date"], round(pt["ratio"], 8),
                         "", "", "PRODUCT_ONLY", ""])
        summary[aid] = {"symbol": sym, "ref_steps": len(rs), "product_steps": len(ps),
                        "counts": dict(counts), "product_source": prod.get("adjustSource"),
                        "product_basis": prod.get("priceBasis")}
    path = os.path.join(a.out, "live-factor-steps.csv")
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["asset_id", "symbol", "side", "ref_date", "ref_ratio", "product_date",
                    "product_ratio", "date_gap_days", "ratio_rel", "class", "note"])
        w.writerows(rows)
    with open(os.path.join(a.out, "live-factor-steps-summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
