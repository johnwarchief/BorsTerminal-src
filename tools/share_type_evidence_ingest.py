# -*- coding: utf-8 -*-
"""Ingest official no-cash share-type evidence (CODAL letters) into a DB copy.

The chart path never fetches CODAL; it only reads `share_type_evidence` when
that table exists and uses `no_cash=1` rows to sharpen an approximate base gap
to the official share ratio.  This tool is the write door and is deterministic:
the same evidence and `--fetched-at` produce the same rows.

Evidence JSONL fields (one record per step):
  ins_code, step_date, share_date, event_type, composition{paid_cash,...},
  letter{tracing_no,title,publish,url}
Only RESERVE_ONLY / COMBINED_CLAIMS with paid_cash == 0 are accepted; every
other type is counted as rejected, never written.
"""
import argparse
import json
import os
import sqlite3
import sys

DDL = """CREATE TABLE IF NOT EXISTS share_type_evidence (
 ins_code TEXT NOT NULL,
 d_even INTEGER NOT NULL,
 no_cash INTEGER NOT NULL,
 source TEXT,
 source_id TEXT,
 fetched_at TEXT NOT NULL,
 PRIMARY KEY (ins_code, d_even))"""

ACCEPTED = ("RESERVE_ONLY", "COMBINED_CLAIMS")


def rows_from_evidence(path):
    accepted, rejected = [], []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                j = json.loads(line)
            except Exception:
                rejected.append(("BAD_JSON", "", ""))
                continue
            et = j.get("event_type")
            comp = j.get("composition") or {}
            paid = comp.get("paid_cash") or 0
            sd = j.get("share_date") or ""
            ins = j.get("ins_code") or ""
            if et not in ACCEPTED or float(paid) > 0 or not sd or not ins:
                rejected.append((et or "NO_TYPE", ins, sd))
                continue
            try:
                d_even = int(str(sd)[:10].replace("-", ""))
            except Exception:
                rejected.append(("BAD_DATE", ins, sd))
                continue
            letter = j.get("letter") or {}
            accepted.append((ins, d_even, 1, "codal-letter",
                             str(letter.get("tracing_no") or "")))
    return accepted, rejected


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--fetched-at", default="2026-10-21")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not os.path.exists(a.db):
        print("DB not found: %s" % a.db)
        return 2
    accepted, rejected = rows_from_evidence(a.evidence)
    print("accepted %d, rejected %d" % (len(accepted), len(rejected)))
    for r in rejected:
        print("  reject", r)
    if a.dry_run:
        return 0
    con = sqlite3.connect(a.db)
    try:
        con.execute(DDL)
        con.executemany(
            "INSERT OR REPLACE INTO share_type_evidence"
            " (ins_code,d_even,no_cash,source,source_id,fetched_at)"
            " VALUES (?,?,?,?,?,?)",
            [r + (a.fetched_at,) for r in accepted])
        con.commit()
        n = con.execute("SELECT COUNT(*) FROM share_type_evidence").fetchone()[0]
        print("table rows: %d" % n)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
