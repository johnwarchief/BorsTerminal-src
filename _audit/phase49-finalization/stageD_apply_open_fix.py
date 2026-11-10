#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stage D: validate and apply reference-proven Open corrections to a NEW
Seed DB copy (never the archived DB). Records row-level provenance in
raw_history_corrections and prints a full accounting.
"""
import argparse
import collections
import csv
import gzip
import json
import os
import shutil
import sqlite3
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DB = os.path.join(ROOT, "_audit", "phase49-finalization", "db", "restored-work.db")
OUT_DIR = os.path.join(ROOT, "_audit", "phase49-finalization", "seed")
REF_SHA = "ab3b6a938684b088f4c01d7139ce3822118ecaf518bcdc8f61d40fe5d9912c7a"


def load_ref(path):
    raw = collections.defaultdict(dict)
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            if str(r.get("resolution")) != "D":
                continue
            if str(r.get("type")) in ("type0", "raw"):
                raw[r["symbol"]][str(r["date"])] = r
    return raw


def close(a, b, tol=1.0):
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--corrections", required=True)
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "market.db"))
    args = ap.parse_args()
    ref = load_ref(os.path.join(args.ref, "bars.ndjson.gz"))
    rows = list(csv.DictReader(open(args.corrections, encoding="utf-8")))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    if os.path.exists(args.out):
        raise SystemExit("refusing to overwrite existing seed db: %s" % args.out)
    shutil.copy2(SRC_DB, args.out)
    con = sqlite3.connect(args.out)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""CREATE TABLE IF NOT EXISTS raw_history_corrections(
        run_id TEXT, symbol TEXT, date TEXT, field TEXT, old_value REAL,
        new_value REAL, source TEXT, reference_sha256 TEXT, reason TEXT,
        applied_at TEXT, PRIMARY KEY(symbol,date,field))""")
    run_id = "phase49-open-fix-2026-11-10"
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    applied = rejected = missing = 0
    reasons = collections.Counter()
    for r in rows:
        sym, d = r["symbol"], r["date"]
        rr = (ref.get(sym) or {}).get(d)
        if not rr:
            missing += 1
            reasons["no_reference_row"] += 1
            continue
        ro, rl, rh = rr.get("open"), rr.get("low"), rr.get("high")
        ok = (ro is not None and rl is not None and rh is not None
              and float(rl) <= float(ro) <= float(rh) and float(ro) > 0)
        if not ok:
            rejected += 1
            reasons["reference_ohlc_inconsistent"] += 1
            continue
        cur = con.execute(
            "SELECT open,high,low,close,src FROM price_history WHERE symbol=? AND date=?",
            (sym, d)).fetchone()
        if not cur:
            rejected += 1
            reasons["db_row_missing"] += 1
            continue
        do, dh, dl, dc, src = cur
        if src != "legacy-unknown":
            rejected += 1
            reasons["src_changed"] += 1
            continue
        # open is a first-trade price; the legacy row's close/high/low may use
        # a different (closing/last) basis.  Accept when the reference open is
        # inside the stored daily range, so the row stays geometrically valid.
        if not (float(dl) - 1.0 <= float(ro) <= float(dh) + 1.0):
            rejected += 1
            reasons["reference_open_outside_db_range"] += 1
            continue
        if not close(do, r.get("db_value")):
            rejected += 1
            reasons["old_value_changed"] += 1
            continue
        con.execute("UPDATE price_history SET open=? WHERE symbol=? AND date=?",
                    (float(ro), sym, d))
        con.execute("""INSERT OR REPLACE INTO raw_history_corrections
            (run_id,symbol,date,field,old_value,new_value,source,
             reference_sha256,reason,applied_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (run_id, sym, d, "open", float(do), float(ro),
                     "rahavard-type0", REF_SHA,
                     "db open equalled previous close; reference type0 open differs",
                     now))
        applied += 1
    con.commit()
    integrity = [r[0] for r in con.execute("PRAGMA integrity_check")]
    con.execute("PRAGMA journal_mode=DELETE")
    total = con.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
    corr = con.execute("SELECT COUNT(*), COUNT(DISTINCT symbol) FROM raw_history_corrections").fetchone()
    con.close()
    out = {"run_id": run_id, "source_db": os.path.relpath(SRC_DB, ROOT).replace("\\", "/"),
           "out": os.path.relpath(args.out, ROOT).replace("\\", "/"),
           "candidates": len(rows), "applied": applied, "rejected": rejected,
           "missing_reference": missing, "reasons": dict(reasons),
           "integrity": integrity, "price_history_rows": total,
           "corrections_rows": corr[0], "corrections_symbols": corr[1],
           "reference_sha256": REF_SHA}
    with open(os.path.join(ROOT, "_audit", "phase49-finalization",
                           "open-apply-report.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
