#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 16: an empty/incomplete gate DB must be refused, not copied.

Round 15's gate copied a 4 KB empty market.db and failed later with
`no such table: financial_statements`.  The guard now checks the core
tables before copying anything.
"""
import os
import sqlite3
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD = os.path.join(ROOT, "dev", "gate_db_guard.py")
P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   ← %s" % (detail,)) if detail else ""))


def run_guard(path):
    p = subprocess.run([sys.executable, GUARD, "--db", path],
                       cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


tmp = tempfile.mkdtemp(prefix="r16_gate_")
empty = os.path.join(tmp, "empty.db")
sqlite3.connect(empty).close()
rc, out = run_guard(empty)
ck(rc == 2 and "GATE_REFUSED_INCOMPLETE_DB" in out,
   "empty DB is refused before the gate copies it", (rc, out[-300:]))

partial = os.path.join(tmp, "partial.db")
con = sqlite3.connect(partial)
con.execute("CREATE TABLE instruments (ins_code TEXT, l_val18 TEXT)")
con.execute("CREATE TABLE price_history (symbol TEXT, date TEXT, close REAL)")
con.commit()
con.close()
rc, out = run_guard(partial)
ck(rc == 2 and "financial_statements" in out,
   "partial DB names the missing core table", (rc, out[-300:]))

missing = os.path.join(tmp, "absent.db")
rc, out = run_guard(missing)
ck(rc == 2 and "protected DB not found" in out,
   "missing DB is still refused", (rc, out[-200:]))

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
