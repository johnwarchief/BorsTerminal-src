# -*- coding: utf-8 -*-
"""Round 22: pair reference and product factor steps over the expanded cohort."""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import importlib.util
spec = importlib.util.spec_from_file_location(
    "p21", os.path.join(ROOT, "tools", "ra365_round21_live_parity.py"))
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)

REF = "D:/BorsTerminal-tmp/r22_live/ra365_r22_ref_31.json"
PROD = "D:/BorsTerminal-tmp/r22_live/product_live"
OUT = os.path.join(ROOT, "artifacts", "ra365", "r22")


def steps(m, thresh=1e-4):
    ds = sorted(m)
    out = []
    for i in range(1, len(ds)):
        a, b = m[ds[i - 1]], m[ds[i]]
        if a and b and abs(b / a - 1.0) > thresh:
            out.append({"date": ds[i], "ratio": b / a})
    return out


def d(s):
    return dt.date.fromisoformat(s)


def main():
    ref = json.load(open(REF, encoding="utf-8"))
    series = {}
    for it in ref["items"]:
        series[(str(it["asset_id"]), it["type"], it["res"])] = {
            b["utc"][:10]: b for b in (it.get("bars") or [])}
    rows = []
    summary = {}
    for aid, sym in P.ASSETS.items():
        p = os.path.join(PROD, aid + ".json")
        if not os.path.exists(p):
            continue
        prod = json.load(open(p, encoding="utf-8"))
        r0 = series.get((aid, "type0", "D")) or {}
        r7 = series.get((aid, "type7", "D")) or {}
        if not r0 or not r7:
            continue
        rf = {k: r7[k]["c"] / r0[k]["c"] for k in set(r0) & set(r7) if r0[k].get("c")}
        pf = {str(f["time"])[:10]: float(f["factor"]) for f in (prod.get("factors") or [])}
        rs, ps = steps(rf), steps(pf)
        used, counts = set(), Counter()
        for st in rs:
            cand = []
            for i, pt in enumerate(ps):
                if i in used:
                    continue
                diff = abs((d(pt["date"]) - d(st["date"])).days)
                if diff <= 7:
                    cand.append((diff, i, pt))
            if cand:
                diff, i, pt = min(cand)
                used.add(i)
                rel = abs(pt["ratio"] / st["ratio"] - 1.0)
                cls = "MATCH" if rel <= 0.005 else "CLOSE" if rel <= 0.02 else "RATIO_DIFF"
                counts[cls] += 1
                rows.append([aid, sym, "REF", st["date"], round(st["ratio"], 8),
                             pt["date"], round(pt["ratio"], 8), diff, f"{rel:.8f}", cls])
            else:
                counts["REF_ONLY"] += 1
                rows.append([aid, sym, "REF", st["date"], round(st["ratio"], 8),
                             "", "", "", "", "REF_ONLY"])
        for i, pt in enumerate(ps):
            if i not in used:
                counts["PRODUCT_ONLY"] += 1
                rows.append([aid, sym, "PROD", "", "", pt["date"],
                             round(pt["ratio"], 8), "", "", "PRODUCT_ONLY"])
        summary[aid] = {"symbol": sym, "ref_steps": len(rs), "product_steps": len(ps),
                        "counts": dict(counts)}
    with open(os.path.join(OUT, "factor31.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["asset_id", "symbol", "side", "ref_date", "ref_ratio",
                    "product_date", "product_ratio", "date_gap_days", "ratio_rel", "class"])
        w.writerows(rows)
    json.dump(summary, open(os.path.join(OUT, "factor31-summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    tot = Counter()
    for v in summary.values():
        for k, n in v["counts"].items():
            tot[k] += n
    print("TOTAL", dict(tot))
    for aid, v in summary.items():
        if v["counts"].get("RATIO_DIFF") or v["counts"].get("REF_ONLY"):
            print(v["symbol"], v["counts"])


if __name__ == "__main__":
    main()
