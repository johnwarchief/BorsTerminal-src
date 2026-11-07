#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 30: independent cross-sectional base-gap scan (no reference).

Reads the current-engine capture payloads and the official ledger only.  For
each session it counts symbols with a base/unproven gap, how many of those
symbols have an official price-adjust/share/fund row, and the median absolute
deviation of the gap ratios.  The output is the input expected by
`tools/session_anomaly_scan.py`; qualification stays entirely in that tool's
existing rule (official_symbols==0, product_only_steps>=10, mad<=2%).

Usage:
  python tools/ra365_round30_gap_scan.py --product <dirs> --db <db> --out <csv>
"""
import argparse
import csv
import json
import os
import sqlite3
import statistics
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    con = sqlite3.connect(a.db, timeout=60)
    official = defaultdict(set)
    for q in ("SELECT ins_code, d_even FROM price_adjust_events",
              "SELECT ins_code, d_even FROM share_change_events",
              "SELECT ins_code, d_even FROM fund_profit_events"):
        try:
            for ins, d in con.execute(q):
                official[str(ins)].add(str(d)[:8])
        except sqlite3.OperationalError:
            continue
    con.close()

    by_date = defaultdict(lambda: {"syms": set(), "official": set(),
                                   "dev": [], "steps": 0})
    seen = set()
    for root in a.product.split(","):
        if not os.path.isdir(root):
            continue
        for fn in sorted(os.listdir(root)):
            if not (fn.endswith(".json") and fn[:-5].isdigit()):
                continue
            p = json.load(open(os.path.join(root, fn), encoding="utf-8"))
            aid = str(p.get("asset_id"))
            if aid in seen:
                continue
            seen.add(aid)
            ins = str(p.get("ins_code"))
            for e in p.get("adjustEvents") or []:
                src = e.get("source")
                if src not in (None, "base-price-discontinuity"):
                    continue
                try:
                    r = float(e.get("ratio") or 0)
                except (TypeError, ValueError):
                    continue
                d = str(e.get("date") or "")[:10]
                if not d or r <= 0 or abs(r - 1.0) < 1e-7:
                    continue
                rec = by_date[d]
                rec["syms"].add(aid)
                rec["steps"] += 1
                rec["dev"].append(abs(r - 1.0))
                if str(d.replace("-", "")) in official.get(ins, set()):
                    rec["official"].add(aid)
    rows = []
    for d in sorted(by_date):
        rec = by_date[d]
        rows.append({
            "date": d,
            "gap_symbols": len(rec["syms"]),
            "official_symbols": len(rec["official"]),
            "product_only_steps": rec["steps"],
            "median_abs_ratio_deviation": round(statistics.median(rec["dev"]), 6)
            if rec["dev"] else 1.0,
        })
    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else
                           ["date", "gap_symbols", "official_symbols",
                            "product_only_steps", "median_abs_ratio_deviation"])
        w.writeheader(); w.writerows(rows)
    print(json.dumps({"dates": len(rows), "assets": len(seen),
                      "top": sorted(rows, key=lambda r: -r["product_only_steps"])[:8]},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
