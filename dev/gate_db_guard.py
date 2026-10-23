#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the full gate on an isolated DB copy and prove the source DB unchanged.

Why this wrapper exists: the Round-5 gate wrote 14 published rows into the
worktree's market.db through the live chart history-repair path. The gate now
runs with:
  * a private WORK_DIR and a private market.db copy (`BORS_WORK_DIR`/`BORS_DB`),
  * `BORS_NO_FETCH_LOOPS=1` so no chart request can fetch from the network,
  * a logical fingerprint of the protected source DB before and after.

The logical fingerprint is independent of SQLite page order (see
dev/db_fingerprint.py). A content change fails the gate even if the tests pass.

Usage:
  python dev/gate_db_guard.py --db <protected market.db> [--run_all_tests args]
"""
import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

DEV = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(DEV)
if DEV not in sys.path:
    sys.path.insert(0, DEV)

import db_fingerprint as FP  # noqa: E402

SIDE_CARS = ("user.db", ".screener_cache.json", "price_basis.json",
             "fts_thresholds.json", "codal_control.json", "market.db.lzma")


def copy_db(src, dst):
    s = sqlite3.connect("file:%s?mode=ro" % src.replace("\\", "/"), uri=True,
                        timeout=30)
    try:
        d = sqlite3.connect(dst, timeout=30)
        try:
            s.backup(d)
        finally:
            d.close()
    finally:
        s.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("BORS_GATE_DB")
                    or os.path.join(ROOT, "market.db"))
    ap.add_argument("--workdir", default=os.environ.get("BORS_GATE_WORKDIR"))
    ap.add_argument("gate_args", nargs=argparse.REMAINDER)
    a = ap.parse_args()

    src = os.path.abspath(a.db)
    if not os.path.isfile(src):
        print("GATE_REFUSED: protected DB not found: %s" % src)
        return 2
    try:
        conn = sqlite3.connect("file:%s?mode=ro" % src.replace("\\", "/"),
                               uri=True, timeout=30)
        try:
            present = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            conn.close()
    except Exception as e:
        print("GATE_REFUSED_UNREADABLE_DB: %s (%s)" % (src, e))
        return 2
    required = {"instruments", "price_history", "financial_statements"}
    missing = sorted(required - present)
    if missing:
        print("GATE_REFUSED_INCOMPLETE_DB: %s missing %s"
              % (src, ", ".join(missing)))
        return 2

    work = a.workdir or tempfile.mkdtemp(prefix="bors_gate_")
    os.makedirs(work, exist_ok=True)
    tmp_db = os.path.join(work, "market.db")
    copy_db(src, tmp_db)
    for name in SIDE_CARS:
        s = os.path.join(os.path.dirname(src), name)
        if os.path.isfile(s):
            shutil.copy2(s, os.path.join(work, name))

    before = FP.fingerprint(src)
    before_path = os.path.join(work, "protected_before.json")
    with open(before_path, "w", encoding="utf-8") as fh:
        json.dump(before, fh, ensure_ascii=False, indent=1, sort_keys=True)

    env = dict(os.environ,
               BORS_WORK_DIR=work,
               BORS_DB=tmp_db,
               BORS_NO_FETCH_LOOPS="1",
               BORS_GATE_ISOLATED="1",
               BORS_PROTECT_DB=src,
               PYTHONIOENCODING="utf-8",
               PYTHONUNBUFFERED="1")

    args = list(a.gate_args)
    if args and args[0] == "--":
        args = args[1:]
    cmd = [sys.executable, os.path.join(DEV, "run_all_tests.py")] + args
    print("[gate-isolation] protected_db=%s" % src)
    print("[gate-isolation] workdir=%s" % work)
    print("[gate-isolation] logical_before=%s" %
          before.get("logical_total"))
    rc = subprocess.run(cmd, cwd=ROOT, env=env).returncode

    after = FP.fingerprint(src)
    after_path = os.path.join(work, "protected_after.json")
    with open(after_path, "w", encoding="utf-8") as fh:
        json.dump(after, fh, ensure_ascii=False, indent=1, sort_keys=True)
    diffs = FP.compare(before, after)
    print("[gate-isolation] logical_after=%s" % after.get("logical_total"))
    if diffs:
        print("PROTECTED_DB_CHANGED: %d logical difference(s)" % len(diffs))
        for name, old, new in diffs[:30]:
            print("  %s\n    before=%s\n    after =%s" % (name, old, new))
        print("[gate-isolation] evidence kept in %s" % work)
        return 3

    print("PROTECTED_DB_UNCHANGED logical_total=%s" % after.get("logical_total"))
    print("[gate-isolation] workdir kept for evidence: %s" % work)
    return rc


if __name__ == "__main__":
    sys.exit(main())
