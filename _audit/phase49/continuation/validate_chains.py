#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Validate chain modes against committed reference factor evidence.

Evidence used:
  _audit/ADJUSTED-FACTOR-STEPS.csv  (127 reference steps, 28 symbols, ref_factor
  cumulative anchored at the last step date; ref_ratio = step multiplier).

For each boundary date we compare our normalized cumulative factor
f(d)/f(anchor) with the reference ref_factor(d). Two views:
  * at_boundary: exact date (catches date shifts as well as ratio errors)
  * plus3: the 3rd trading day at/after the boundary (isolates ratio errors)
"""
import argparse
import csv
import glob
import gzip
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
EVID = os.path.join(ROOT, "_audit", "phase49", "continuation", "evidence")
REF_CSV = os.path.join(ROOT, "_audit", "ADJUSTED-FACTOR-STEPS.csv")


def load_ref():
    by = {}
    for r in csv.DictReader(open(REF_CSV, encoding="utf-8-sig")):
        if not r.get("date") or not r.get("ref_factor"):
            continue
        if r.get("kind") != "reference_step" or not r.get("ref_ratio"):
            continue
        by.setdefault(r["symbol"], []).append({
            "date": r["date"], "ref_ratio": float(r["ref_ratio"]),
            "ref_factor": float(r["ref_factor"]), "kind": r.get("kind")})
    for s in by:
        by[s].sort(key=lambda x: x["date"])
    return by


def load_mode(label):
    out = {}
    for fn in glob.glob(os.path.join(EVID, "api-" + label, "*.json.gz")):
        sym = os.path.basename(fn)[:-8]
        with gzip.open(fn, "rt", encoding="utf-8") as fh:
            p = json.load(fh)
        fac = {}
        for f in p.get("factors") or []:
            fac[str(f["time"])[:10]] = float(f["factor"])
        dates = sorted(fac)
        out[sym] = {"factors": fac, "dates": dates,
                    "events": p.get("adjustEvents") or [],
                    "rejected": p.get("adjustRejected") or [],
                    "source": p.get("adjustSource"),
                    "count": p.get("count")}
    return out


def plus_n(dates, d, n):
    after = [x for x in dates if x >= d]
    if not after:
        return None
    i = dates.index(after[0])
    j = min(len(dates) - 1, i + n)
    return dates[j]


def bucket(rel):
    a = abs(rel)
    if a <= 1e-9:
        return "exact"
    if a <= 1e-3:
        return "le_001"
    if a <= 1e-2:
        return "le_01"
    if a <= 5e-2:
        return "le_05"
    return "gt_05"


def summarize(rows):
    out = {"n": len(rows), "exact": 0, "le_001": 0, "le_01": 0, "le_05": 0,
           "gt_05": 0, "max_rel": 0.0, "median_rel": None}
    rels = []
    for r in rows:
        out[bucket(r["rel"])] += 1
        rels.append(abs(r["rel"]))
    if rels:
        rels.sort()
        out["max_rel"] = rels[-1]
        out["median_rel"] = rels[len(rels) // 2]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default="authoritative-base,overlay-plain")
    ap.add_argument("--out", default=os.path.join(EVID, "chain-validation.json"))
    args = ap.parse_args()
    ref = load_ref()
    report = {"reference": os.path.relpath(REF_CSV, ROOT).replace("\\", "/"),
              "reference_steps": sum(len(v) for v in ref.values()),
              "reference_symbols": len(ref), "modes": {}}
    for label in args.labels.split(","):
        label = label.strip()
        data = load_mode(label)
        rows_boundary, rows_plus3 = [], []
        per_symbol = []
        for sym, refrows in sorted(ref.items()):
            d = data.get(sym)
            if not d:
                per_symbol.append({"symbol": sym, "status": "NO_DATA"})
                continue
            dates, fac = d["dates"], d["factors"]
            anchor_date = refrows[-1]["date"]
            # anchor factor: exact date, else nearest later (report if missing)
            if anchor_date in fac:
                anchor = fac[anchor_date]
            else:
                later = [x for x in dates if x >= anchor_date]
                if not later:
                    per_symbol.append({"symbol": sym, "status": "NO_ANCHOR"})
                    continue
                anchor = fac[later[0]]
            sym_rows_b, sym_rows_p = [], []
            for r in refrows:
                d0 = r["date"]
                if d0 in fac and anchor:
                    rel = (fac[d0] / anchor) / r["ref_factor"] - 1.0
                    sym_rows_b.append({"symbol": sym, "date": d0, "rel": rel})
                dp = plus_n(dates, d0, 3)
                if dp and anchor and r["ref_factor"]:
                    rel = (fac[dp] / anchor) / r["ref_factor"] - 1.0
                    sym_rows_p.append({"symbol": sym, "date": d0, "ref_date": dp,
                                       "rel": rel})
            rows_boundary.extend(sym_rows_b)
            rows_plus3.extend(sym_rows_p)
            per_symbol.append({
                "symbol": sym, "status": "MEASURED",
                "steps": len(refrows),
                "at_boundary": summarize(sym_rows_b),
                "plus3": summarize(sym_rows_p),
                "events": len(d["events"]), "rejected": len(d["rejected"]),
                "source": d["source"],
            })
        report["modes"][label] = {
            "at_boundary": summarize(rows_boundary),
            "plus3": summarize(rows_plus3),
            "per_symbol": per_symbol,
            "detail_plus3": rows_plus3,
        }
        m = report["modes"][label]
        print(label, "boundary", json.dumps(m["at_boundary"]))
        print(label, "plus3   ", json.dumps(m["plus3"]))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print("out:", args.out)


if __name__ == "__main__":
    main()
