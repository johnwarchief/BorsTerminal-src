#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DB isolation contract: test runs never write the operational market.db.

Checks:
  1. `BORS_WORK_DIR`/`BORS_DB` redirect WORK_DIR, DB_PATH and USER_DB_PATH.
  2. A write through the redirected DB lands in the temp copy, not the source.
  3. The logical fingerprint matches identical rows in a different physical
     order and detects one inserted row (positive and negative control).
  4. `BORS_NO_FETCH_LOOPS=1` closes the fetch-loop gate.
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV = os.path.join(ROOT, "dev")
PY = sys.executable
P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   ← %s" % detail) if detail else ""))


def run(args, env=None):
    return subprocess.run(args, cwd=ROOT, env=env, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def count(path):
    con = sqlite3.connect('file:%s?mode=ro' % path.replace("\\", "/"), uri=True)
    try:
        return con.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
    finally:
        con.close()


work = tempfile.mkdtemp(prefix="bors_db_isolation_")
try:
    protected = os.path.join(work, "protected.db")
    con = sqlite3.connect(protected)
    con.execute("CREATE TABLE price_history(symbol TEXT, date TEXT, close REAL)")
    con.execute("INSERT INTO price_history VALUES('X','2026-01-01',1.0)")
    con.commit()
    con.close()

    iso = os.path.join(work, "isolated")
    os.makedirs(iso, exist_ok=True)
    iso_db = os.path.join(iso, "market.db")
    probe = r'''
import json, sqlite3
import bors_config
out = {"WORK_DIR": bors_config.WORK_DIR, "DB_PATH": bors_config.DB_PATH,
       "USER_DB_PATH": bors_config.USER_DB_PATH}
con = sqlite3.connect(bors_config.DB_PATH)
con.execute("CREATE TABLE IF NOT EXISTS price_history(symbol TEXT, date TEXT, close REAL)")
con.execute("INSERT INTO price_history VALUES('Y','2026-01-01',2.0)")
con.commit()
con.close()
print(json.dumps(out))
'''
    env = dict(os.environ, BORS_WORK_DIR=iso, BORS_DB=iso_db,
               PYTHONIOENCODING="utf-8")
    r = run([PY, "-c", probe], env=env)
    ck(r.returncode == 0, "env-override probe runs", r.stderr[-300:])
    paths = {}
    if r.returncode == 0:
        paths = json.loads(r.stdout.strip().splitlines()[-1])
    ck(os.path.abspath(paths.get("WORK_DIR", "")) == os.path.abspath(iso),
       "BORS_WORK_DIR redirects WORK_DIR", paths.get("WORK_DIR"))
    ck(os.path.abspath(paths.get("DB_PATH", "")) == os.path.abspath(iso_db),
       "BORS_DB redirects DB_PATH", paths.get("DB_PATH"))
    ck(os.path.abspath(paths.get("USER_DB_PATH", "")).startswith(
        os.path.abspath(iso) + os.sep), "USER_DB_PATH follows WORK_DIR",
       paths.get("USER_DB_PATH"))
    ck(count(protected) == 1, "protected DB still has exactly its one row")
    ck(os.path.isfile(iso_db) and count(iso_db) == 1,
       "redirected DB received the write, source did not")

    if os.path.isfile(os.path.join(ROOT, "market.db")):
        env0 = dict(os.environ, BORS_WORK_DIR="", BORS_DB="",
                    PYTHONIOENCODING="utf-8")
        r0 = run([PY, "-c", "import bors_config; print(bors_config.DB_PATH)"], env=env0)
        ck(r0.returncode == 0 and os.path.abspath(r0.stdout.strip())
           == os.path.abspath(os.path.join(ROOT, "market.db")),
           "without overrides DB_PATH is the repo market.db", r0.stdout.strip())

    a = os.path.join(work, "a.db")
    b = os.path.join(work, "b.db")
    for path, rows in ((a, [(1, "x"), (2, "y")]), (b, [(2, "y"), (1, "x")])):
        con = sqlite3.connect(path)
        con.execute("CREATE TABLE t(k INTEGER, v TEXT)")
        con.executemany("INSERT INTO t VALUES(?,?)", rows)
        con.commit()
        con.close()
    fa = os.path.join(work, "a.json")
    r = run([PY, os.path.join(DEV, "db_fingerprint.py"), "--db", a,
             "--out", fa, "--quiet"])
    ck(r.returncode == 0 and os.path.isfile(fa), "fingerprint written", r.stderr[-300:])
    r = run([PY, os.path.join(DEV, "db_fingerprint.py"), "--db", b,
             "--compare", fa, "--quiet"])
    ck(r.returncode == 0 and "FINGERPRINT_MATCH" in r.stdout,
       "same rows in a different order => same logical fingerprint", r.stdout)
    con = sqlite3.connect(b)
    con.execute("INSERT INTO t VALUES(3,'z')")
    con.commit()
    con.close()
    r = run([PY, os.path.join(DEV, "db_fingerprint.py"), "--db", b,
             "--compare", fa, "--quiet"])
    ck(r.returncode == 2 and "FINGERPRINT_DIFFERENCE" in r.stdout,
       "one inserted row => fingerprint difference detected", r.stdout)

    env_on = dict(os.environ, BORS_NO_FETCH_LOOPS="1")
    r = run([PY, "-c", "import bors_flags; print(bors_flags.fetch_loops_enabled())"],
            env=env_on)
    ck(r.stdout.strip() == "False", "BORS_NO_FETCH_LOOPS=1 closes the fetch gate", r.stdout)
    env_off = dict(os.environ)
    env_off.pop("BORS_NO_FETCH_LOOPS", None)
    r = run([PY, "-c", "import bors_flags; print(bors_flags.fetch_loops_enabled())"],
            env=env_off)
    ck(r.stdout.strip() == "True", "unset BORS_NO_FETCH_LOOPS leaves the gate open", r.stdout)
finally:
    shutil.rmtree(work, ignore_errors=True)

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
