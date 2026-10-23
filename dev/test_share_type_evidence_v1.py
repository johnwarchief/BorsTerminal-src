#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Share-type evidence ingest: deterministic, idempotent, no-cash only."""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "share_type_evidence_ingest.py")
P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   ← %s" % (detail,)) if detail else ""))


def main():
    d = tempfile.mkdtemp(prefix="r12_share_type_")
    db = os.path.join(d, "t.db")
    ev = os.path.join(d, "ev.jsonl")
    sqlite3.connect(db).close()
    rows = [
        {"ins_code": "1", "step_date": "2024-05-06", "share_date": "2024-05-01",
         "event_type": "RESERVE_ONLY", "composition": {"paid_cash": 0},
         "letter": {"tracing_no": 11}},
        {"ins_code": "2", "step_date": "2024-06-01", "share_date": "2024-06-01",
         "event_type": "PAID_IN", "composition": {"paid_cash": 500},
         "letter": {"tracing_no": 22}},
        {"ins_code": "3", "step_date": "2024-07-01", "share_date": "2024-06-30",
         "event_type": "COMBINED_CLAIMS", "composition": {"paid_cash": 0},
         "letter": {"tracing_no": 33}},
        {"ins_code": "4", "step_date": "2024-08-01", "share_date": "2024-08-01",
         "event_type": "UNPARSED", "composition": {},
         "letter": {"tracing_no": 44}},
    ]
    with open(ev, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    cmd = [sys.executable, TOOL, "--db", db, "--evidence", ev,
           "--fetched-at", "2026-10-21"]
    out = subprocess.run(cmd, capture_output=True, text=True)
    ck(out.returncode == 0, "ingest exits zero", out.stderr[-200:])
    con = sqlite3.connect(db)
    got = con.execute("SELECT ins_code,d_even,no_cash FROM share_type_evidence"
                      " ORDER BY ins_code").fetchall()
    ck(got == [("1", 20240501, 1), ("3", 20240630, 1)],
       "only no-cash reserve/claims rows are written", got)
    out2 = subprocess.run(cmd, capture_output=True, text=True)
    got2 = con.execute("SELECT ins_code,d_even,no_cash FROM share_type_evidence"
                       " ORDER BY ins_code").fetchall()
    ck(out2.returncode == 0 and got2 == got, "second run is idempotent", got2)
    con.close()
    print()
    print("result: %d pass, %d fail" % (P, F))
    print("%d/%d" % (P, P + F))
    return 0 if F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
