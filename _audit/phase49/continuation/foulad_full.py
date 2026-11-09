#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Full-history raw/adjusted parity for فولاد against the committed reference
chain CSV, per chain mode. Read-only.
"""
import csv
import glob
import gzip
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
EVID = os.path.join(ROOT, "_audit", "phase49", "continuation", "evidence")
REF = os.path.join(ROOT, "_audit", "RA365-CHAIN-PARITY-FULL-HISTORY-2026-10-18.csv")
DB = os.path.join(ROOT, "_audit", "phase49", "continuation", "db", "restored-work.db")
SYM = "فولاد"


def load_ref():
    out = {}
    for r in csv.DictReader(open(REF, encoding="utf-8-sig")):
        out[r["date"]] = {"raw": float(r["ref_raw"]), "adj": float(r["ref_adj"]),
                          "factor": float(r["ref_factor"])}
    return out


def load_db():
    con = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)
    out = {}
    for d, o, h, l, c, v, last in con.execute(
            "SELECT date,open,high,low,close,volume,last FROM price_history "
            "WHERE symbol=? ORDER BY date", (SYM,)):
        out[d] = {"open": o, "high": h, "low": l, "close": c, "volume": v, "last": last}
    con.close()
    return out


def load_mode(label):
    fn = os.path.join(EVID, "api-" + label, SYM + ".json.gz")
    if not os.path.exists(fn):
        return None
    with gzip.open(fn, "rt", encoding="utf-8") as fh:
        p = json.load(fh)
    return {str(f["time"])[:10]: float(f["factor"]) for f in p["factors"]}


def round_half(v):
    import math
    return float(math.floor(v + 0.5)) if v >= 0 else float(v)


def evaluate(label, factors, ref, db):
    if factors is None:
        return {"status": "NO_DATA"}
    anchor_date = "2026-10-17"
    anchor = factors.get(anchor_date)
    if anchor is None:
        later = sorted(d for d in factors if d >= anchor_date)
        if not later:
            return {"status": "NO_ANCHOR"}
        anchor_date = later[0]
        anchor = factors[anchor_date]
    dates = sorted(set(ref) & set(factors) & set(db))
    raw_rows, adj_rows = [], []
    for d in dates:
        r = ref[d]
        c = db[d]
        if c["close"] is None:
            continue
        raw_rel = (c["close"] / r["raw"] - 1.0) if r["raw"] else None
        raw_rows.append({"date": d, "rel": raw_rel,
                         "abs": c["close"] - r["raw"]})
        f = factors[d] / anchor
        adj = round_half(c["close"] * f)
        adj_rows.append({"date": d, "factor": f, "adj": adj, "ref_adj": r["adj"],
                         "abs": adj - r["adj"],
                         "rel_factor": f / r["factor"] - 1.0})
    def summary(rows, key):
        rels = [abs(x[key]) for x in rows if x[key] is not None]
        rels.sort()
        return {"n": len(rows), "max_rel": rels[-1] if rels else None,
                "median_rel": rels[len(rels) // 2] if rels else None,
                "le_001": sum(1 for x in rels if x <= 1e-3),
                "le_005": sum(1 for x in rels if x <= 5e-3),
                "le_01": sum(1 for x in rels if x <= 1e-2),
                "le_05": sum(1 for x in rels if x <= 5e-2),
                "gt_05": sum(1 for x in rels if x > 5e-2)}
    adj_abs = [abs(x["abs"]) for x in adj_rows]
    adj_abs.sort()
    return {
        "status": "MEASURED", "anchor": anchor_date, "common": len(dates),
        "raw": summary(raw_rows, "rel"),
        "factor": summary(adj_rows, "rel_factor"),
        "adjusted_abs": {
            "n": len(adj_abs), "max": adj_abs[-1] if adj_abs else None,
            "median": adj_abs[len(adj_abs) // 2] if adj_abs else None,
            "le_05": sum(1 for x in adj_abs if x <= 0.5),
            "le_5": sum(1 for x in adj_abs if x <= 5.0),
            "gt_5": sum(1 for x in adj_abs if x > 5.0),
        },
        "worst_factor": max(adj_rows, key=lambda x: abs(x["rel_factor"])),
        "first_factor_gap": next((x["date"] for x in adj_rows
                                  if abs(x["rel_factor"]) > 1e-9), None),
    }


def main():
    ref = load_ref()
    db = load_db()
    report = {"symbol": SYM, "reference": os.path.relpath(REF, ROOT),
              "modes": {}}
    for label in ("authoritative-base", "overlay-plain", "overlay-dedup",
                  "rebuild-v1", "no-corrections"):
        report["modes"][label] = evaluate(label, load_mode(label), ref, db)
        m = report["modes"][label]
        print(label, json.dumps(m, ensure_ascii=False) if m.get("status") != "MEASURED"
              else json.dumps({"raw": m["raw"], "factor": m["factor"],
                               "adjusted_abs": m["adjusted_abs"],
                               "first_gap": m["first_factor_gap"],
                               "worst": m["worst_factor"]}, ensure_ascii=False))
    out = os.path.join(EVID, "foulad-full-history.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print("out:", out)


if __name__ == "__main__":
    main()
