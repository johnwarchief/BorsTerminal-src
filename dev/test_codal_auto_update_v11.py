# -*- coding: utf-8 -*-
"""dev/test_codal_auto_update_v11.py — Task 3: staging-first daily orchestrator.

Proves, with temp DBs only (no network, no CODAL, no gh, no signing):

  1) ``run(dry_run=True)`` copies main → staging, lets ``_fetch`` write one
     valid FS row into staging, validates it, returns ``ok True`` /
     ``published False``, leaves main's row count untouched, and writes the
     status fields (stage/mode/started_at/last_success/last_error/
     latest_periods/validation/published);
  2) a fetched negative revenue fails validation → ``ok False``,
     ``published False``, no merge into main, and the error names
     ``negative_revenue``;
  3) a pause file short-circuits the run before any staging copy;
  4) a second concurrent run (pre-existing lock) returns ``ok False`` without
     crashing and without deleting the other owner's lock;
  5) CLI exit codes: success -> 0, paused -> 0, locked -> 0 (benign skips so
     Task Scheduler's RestartCount does not re-run a full job), validation
     failure -> 1; ``run()``'s result contract is unchanged;
  6) no production step (publish/build_snapshot/updater/sign) is reached in
     the dry-run or validation-failure paths — each is patched to raise.

Run:  python dev/test_codal_auto_update_v11.py
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile

try:                       # Persian/UTF-8 output on a cp1252 Windows console
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "dev"))

import codal_fetcher as cf          # noqa: E402
import codal_auto_update as A       # noqa: E402

CHECKS = []


def ck(cond, msg):
    CHECKS.append((bool(cond), msg))
    print("  %s %s" % ("PASS" if cond else "FAIL", msg))
    return bool(cond)


TMP = tempfile.mkdtemp(prefix="codal_auto_update_v11_")

FS_COLS = ("tracing_no", "symbol", "title", "period_end", "revenue",
           "gross_profit", "url", "publish_date")


def insert_fs(path, row):
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO financial_statements (%s) VALUES (%s)"
                 % (",".join(FS_COLS), ",".join("?" * len(FS_COLS))),
                 [row[c] for c in FS_COLS])
    conn.commit()
    conn.close()


def fs_count(path):
    conn = sqlite3.connect(path)
    try:
        return conn.execute("SELECT COUNT(*) FROM financial_statements").fetchone()[0]
    finally:
        conn.close()


def make_main(path):
    conn = sqlite3.connect(path)
    cf.create_schema(conn)
    cf.migrate_schema(conn)
    conn.close()
    insert_fs(path, {"tracing_no": 1, "symbol": "BASE", "title": "base",
                     "period_end": "1405/06/31", "revenue": 100.0,
                     "gross_profit": 50.0, "url": "https://codal.ir/fs/1",
                     "publish_date": "1405/07/01"})


def make_fetch(revenue=200.0, gross_profit=90.0):
    """Fake ``_fetch``: writes one new FS row into the staging DB it is given."""
    def fake_fetch(db_path):
        insert_fs(db_path, {"tracing_no": 9001, "symbol": "NEW", "title": "new",
                            "period_end": "1405/06/31", "revenue": revenue,
                            "gross_profit": gross_profit,
                            "url": "https://codal.ir/fs/9001",
                            "publish_date": "1405/07/02"})
    return fake_fetch


def boom(*_a, **_k):
    raise AssertionError("production step must not run in this path")


def fresh_env(name):
    d = os.path.join(TMP, name)
    os.makedirs(d)
    main = os.path.join(d, "market.db")
    make_main(main)
    A.STATUS = os.path.join(d, "codal_auto_status.json")
    A.LOCK = os.path.join(d, "codal_auto.lock")
    A.PAUSE = os.path.join(d, "codal_auto_pause")
    A.SNAPSHOT_LZMA = os.path.join(d, "codal.db.lzma")
    A.SNAPSHOT_META = os.path.join(d, "codal.meta.json")
    A.publish = boom
    A.build_snapshot = boom
    A._run_cmd = boom
    return d, main, os.path.join(d, "market.db.staging")


def load_status(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


try:
    # ── ۱) dry-run: staging-only, validated, main untouched ─────────────────
    d, main, staging = fresh_env("dry_run")
    A._fetch = make_fetch()
    r = A.run(dry_run=True, db_path=main, staging_dir=staging)
    ck(r["ok"] is True, "dry-run: ok is True (%r)" % (r["errors"],))
    ck(r["published"] is False, "dry-run: published is False")
    ck(r["staged"] is True, "dry-run: staged is True")
    ck(r["errors"] == [], "dry-run: errors empty (%r)" % (r["errors"],))
    ck(fs_count(main) == 1, "dry-run: main DB row count unchanged (%d)" % fs_count(main))
    ck(os.path.isfile(os.path.join(staging, "market.db")),
       "dry-run: staging DB exists")
    ck(fs_count(os.path.join(staging, "market.db")) == 2,
       "dry-run: staging holds the fetched row")
    ck(not os.path.exists(A.LOCK), "dry-run: lock removed after the run")
    st = load_status(A.STATUS)
    for field in ("stage", "mode", "started_at", "last_success", "last_error",
                  "latest_periods", "validation", "published"):
        ck(field in st, "dry-run: status has %s" % field)
    ck(st["stage"] == "dry_run_ok", "dry-run: stage is dry_run_ok (%r)" % st["stage"])
    ck(st["mode"] == "daily", "dry-run: mode is daily")
    ck(st["published"] is False, "dry-run: status published is False")
    ck(st["validation"]["ok"] is True, "dry-run: status validation ok")
    ck((st.get("latest_periods") or {}).get("financial") == "1405/06/31",
       "dry-run: latest financial period recorded (%r)" % st.get("latest_periods"))
    ck(st["last_success"] is None,
       "dry-run: does not claim a production last_success")

    # ── ۲) validation failure: no merge, no publish ─────────────────────────
    d, main, staging = fresh_env("negative")
    A._fetch = make_fetch(revenue=-5.0, gross_profit=-10.0)
    r = A.run(dry_run=False, db_path=main, staging_dir=staging)
    ck(r["ok"] is False, "negative: ok is False")
    ck(r["published"] is False, "negative: published is False")
    ck(r["staged"] is True, "negative: staged is True (copy happened)")
    ck(any("negative_revenue" in e for e in r["errors"]),
       "negative: error names negative_revenue (%r)" % (r["errors"],))
    ck(fs_count(main) == 1,
       "negative: main DB row count unchanged / no merge (%d)" % fs_count(main))
    ck(not os.path.exists(A.LOCK), "negative: lock removed after the run")
    st = load_status(A.STATUS)
    ck(st["stage"] == "validation_failed",
       "negative: status stage is validation_failed (%r)" % st["stage"])
    ck("negative_revenue" in (st.get("last_error") or ""),
       "negative: status last_error names negative_revenue")
    ck(st["published"] is False, "negative: status published is False")
    ck(st["last_success"] is None,
       "negative: previous last_success kept (None, never promoted)")

    # ── ۳) pause switch: nothing is copied ──────────────────────────────────
    d, main, staging = fresh_env("paused")
    A._fetch = boom
    with open(A.PAUSE, "w", encoding="utf-8") as fh:
        fh.write("pause")
    r = A.run(dry_run=True, db_path=main, staging_dir=staging)
    ck(r["ok"] is False, "paused: ok is False")
    ck(r["errors"] == ["paused"], "paused: errors == ['paused'] (%r)" % (r["errors"],))
    ck(r["staged"] is False, "paused: staged is False")
    ck(not os.path.exists(staging), "paused: no staging directory created")
    ck(not os.path.exists(A.LOCK), "paused: no lock left behind")

    # ── ۴) concurrent run: existing lock refuses without crashing ───────────
    d, main, staging = fresh_env("locked")
    A._fetch = boom
    with open(A.LOCK, "w", encoding="utf-8") as fh:
        fh.write("other-owner")
    r = A.run(dry_run=True, db_path=main, staging_dir=staging)
    ck(r["ok"] is False, "locked: ok is False")
    ck("locked" in r["errors"], "locked: errors name the lock (%r)" % (r["errors"],))
    ck(r["staged"] is False, "locked: staged is False")
    ck(os.path.isfile(A.LOCK), "locked: other owner's lock is left intact")
    ck(fs_count(main) == 1, "locked: main DB untouched")

    # ── ۵) CLI exit codes: locked/paused are benign, failures are not ───────
    ck(A._exit_code({"ok": True, "errors": []}) == 0,
       "exit: success -> 0")
    ck(A._exit_code({"ok": False, "errors": ["paused"]}) == 0,
       "exit: paused -> 0 (benign skip, no Task Scheduler retry)")
    ck(A._exit_code({"ok": False, "errors": ["locked"]}) == 0,
       "exit: locked -> 0 (benign skip, no Task Scheduler retry)")
    ck(A._exit_code({"ok": False, "errors": ["negative_revenue: -5"]}) == 1,
       "exit: validation failure -> 1")
    ck(A._exit_code({"ok": False, "errors": ["locked", "fetch: boom"]}) == 1,
       "exit: locked plus a real error -> 1")
    ck(A._exit_code({}) == 1, "exit: malformed result -> 1")
    ck(A._exit_code(None) == 1, "exit: None result -> 1")
    ck(A.LOCK_STALE_SECONDS == 6 * 3600,
       "stale lock window stays 6h (documented; mirrored by the app cooldown)")

    # run()'s result contract is unchanged: locked/paused stay ok False with
    # their errors; only the CLI mapping makes them exit 0.
    d, main, staging = fresh_env("exit_codes")
    A._fetch = boom
    with open(A.PAUSE, "w", encoding="utf-8") as fh:
        fh.write("pause")
    code = A.main(["--dry-run", "--db", main, "--staging-dir", staging])
    ck(code == 0, "main: paused run exits 0 (%r)" % (code,))

    d, main, staging = fresh_env("exit_codes_locked")
    A._fetch = boom
    with open(A.LOCK, "w", encoding="utf-8") as fh:
        fh.write("other-owner")
    code = A.main(["--dry-run", "--db", main, "--staging-dir", staging])
    ck(code == 0, "main: locked run exits 0 (%r)" % (code,))

    d, main, staging = fresh_env("exit_codes_validation")
    A._fetch = make_fetch(revenue=-5.0, gross_profit=-10.0)
    code = A.main(["--dry-run", "--db", main, "--staging-dir", staging])
    ck(code == 1, "main: validation failure exits 1 (%r)" % (code,))

    d, main, staging = fresh_env("exit_codes_success")
    A._fetch = make_fetch()
    code = A.main(["--dry-run", "--db", main, "--staging-dir", staging])
    ck(code == 0, "main: successful dry-run exits 0 (%r)" % (code,))

    failed = [m for ok, m in CHECKS if not ok]
    if failed:
        print("\nFAILED %d/%d" % (len(failed), len(CHECKS)))
        raise SystemExit(1)
    print("\nOK orchestrator dry-run (%d checks)" % len(CHECKS))
finally:
    shutil.rmtree(TMP, ignore_errors=True)
