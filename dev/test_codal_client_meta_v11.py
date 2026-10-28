# -*- coding: utf-8 -*-
"""dev/test_codal_client_meta_v11.py — Task 8a: data-tag meta compare + auto-check.

Proves, with no network / CODAL / GitHub / ADB and no operational market.db:

  1) the data-tag URLs: ``CODAL_DB_URL`` / ``CODAL_META_URL`` / ``CODAL_CAL_URL``
     all live under ``.../releases/download/data-codal`` and the manual button
     therefore receives the same signed snapshot as the auto-check;
  2) ``should_update`` — advancing FS, advancing MS, equal, older remote,
     missing local and malformed/empty values, none of which may raise;
  3) ``_local_meta`` prefers ``codal_auto_status.json`` periods and otherwise
     reads the real DB ``MAX(period_end)`` read-only (no journal, no byte or
     mtime change on the throwaway DB);
  4) ``should_auto_check`` — the pure startup gate (source opt-in, frozen,
     ``_fetch_loops_enabled``);
  5) source checks: the worker keeps minisign + integrity + three-table
     verification before the merge, downloads the calendar best-effort after a
     successful merge, ``auto_check`` only fetches the meta URL (no CODAL/ADB),
     ``db-status`` carries ``meta``/``freshness`` and app.py starts the check in
     a guarded daemon thread.

Run:  python dev/test_codal_client_meta_v11.py  ->  OK client meta compare
"""
import json
import os
import re
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

import api._sync_codal as S          # noqa: E402

CHECKS = []


def ck(cond, msg):
    CHECKS.append((bool(cond), msg))
    print("  %s %s" % ("PASS" if cond else "FAIL", msg))
    return bool(cond)


def safe(name, *args, **kwargs):
    """Call a module helper without dying when it is missing (red run) or raises."""
    fn = getattr(S, name, None)
    if fn is None:
        return "MISSING"
    try:
        return fn(*args, **kwargs)
    except Exception as exc:                       # noqa: BLE001
        return "raised %s: %s" % (type(exc).__name__, exc)


def ck_update(local, remote, expected, label):
    got = safe("should_update", local, remote)
    ck(got is expected, "%s -> %r (%r)" % (label, expected, got))


def read_text(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def def_block(src, header):
    """(text, start) of a top-level def, up to the next top-level def/@router."""
    start = src.find(header)
    if start == -1:
        return "", -1
    ends = [p for p in (src.find("\ndef ", start + len(header)),
                        src.find("\n@router", start + len(header)))
            if p != -1]
    end = min(ends) if ends else len(src)
    return src[start:end], start


TMP = tempfile.mkdtemp(prefix="codal_client_meta_v11_")
_ORIG_WORK_DIR = S.WORK_DIR
_ORIG_DB_PATH = S.DB_PATH
_ORIG_CACHE = dict(getattr(S, "_db_period_cache", {}) or {})


def make_db(path, fs_period="1405/06/31", ms_period="1405/07/30",
            tables=True):
    con = sqlite3.connect(path)
    try:
        if tables:
            con.execute("CREATE TABLE financial_statements ("
                        "tracing_no INTEGER PRIMARY KEY, symbol TEXT, "
                        "period_end TEXT)")
            con.execute("CREATE TABLE monthly_sales ("
                        "tracing_no INTEGER PRIMARY KEY, symbol TEXT, "
                        "period_end TEXT)")
            if fs_period:
                con.execute("INSERT INTO financial_statements "
                            "(tracing_no, symbol, period_end) VALUES (1,'AAA',?)",
                            (fs_period,))
            if ms_period:
                con.execute("INSERT INTO monthly_sales "
                            "(tracing_no, symbol, period_end) VALUES (2,'AAA',?)",
                            (ms_period,))
        con.commit()
    finally:
        con.close()


def write_status(work_dir, payload):
    with open(os.path.join(work_dir, "codal_auto_status.json"), "w",
              encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)


try:
    # ── ۱) data-tag URLs ────────────────────────────────────────────────────
    ck(getattr(S, "CODAL_DATA_TAG", None) == "data-codal",
       "CODAL_DATA_TAG == data-codal")
    base = "https://github.com/johnwarchief/BorsTerminal/releases/download/data-codal"
    ck(getattr(S, "CODAL_BASE", None) == base, "CODAL_BASE is the data tag (%r)"
       % (getattr(S, "CODAL_BASE", None),))
    ck(getattr(S, "CODAL_DB_URL", None) == base + "/codal.db.lzma",
       "CODAL_DB_URL points at the data tag (%r)"
       % (getattr(S, "CODAL_DB_URL", None),))
    ck(getattr(S, "CODAL_META_URL", None) == base + "/codal.meta.json",
       "CODAL_META_URL points at the data tag (%r)"
       % (getattr(S, "CODAL_META_URL", None),))
    ck(getattr(S, "CODAL_CAL_URL", None) == base + "/calendar.json",
       "CODAL_CAL_URL points at the data tag (%r)"
       % (getattr(S, "CODAL_CAL_URL", None),))
    ck("latest/download" not in (getattr(S, "CODAL_DB_URL", "") or ""),
       "manual button no longer reads the app release 'latest'")
    ck(isinstance(getattr(S, "CODAL_DB_STATUS_PATH", None), str),
       "CODAL_DB_STATUS_PATH name is kept")

    # ── ۲) should_update: advancing / equal / older ─────────────────────────
    local = {"latest_financial_period": "1405/06/31",
             "latest_monthly_period": "1405/06/31"}
    ck_update(local, {"latest_financial_period": "1405/07/31",
                      "latest_monthly_period": "1405/06/31"}, True,
              "advancing FS")
    ck_update(local, {"latest_financial_period": "1405/06/31",
                      "latest_monthly_period": "1405/07/30"}, True,
              "advancing MS")
    ck_update(local, dict(local), False, "equal periods")
    ck_update(local, {"latest_financial_period": "1405/05/31",
                      "latest_monthly_period": "1405/05/31"}, False,
              "older remote")
    ck_update(local, {"latest_financial_period": "1405/06/31"}, False,
              "remote missing MS while local has it")
    ck_update({"latest_financial_period": "1405/06/31"},
              {"latest_financial_period": "1405/06/31",
               "latest_monthly_period": "1405/07/30"}, True,
              "local missing MS, remote has it")

    # no local at all -> update
    ck_update(None, {"latest_financial_period": "1405/06/31"}, True,
              "no local (None)")
    ck_update({}, {"latest_financial_period": "1405/06/31"}, True,
              "no local (empty dict)")
    ck_update({"latest_financial_period": None, "latest_monthly_period": None},
              {"latest_financial_period": "1405/06/31"}, True,
              "local periods None")
    ck_update("not-a-dict", {"latest_financial_period": "1405/06/31"}, True,
              "local not a dict (treated as no local)")

    # remote missing/useless -> never update, never raise
    ck_update(local, None, False, "remote None")
    ck_update(local, {}, False, "remote empty dict")
    ck_update(local, "not-a-dict", False, "remote not a dict")
    ck_update(local, {"latest_financial_period": "", "latest_monthly_period": ""},
              False, "remote empty periods")
    ck_update(local, {"latest_financial_period": "garbage"}, False,
              "remote malformed period")
    ck_update(local, {"latest_financial_period": 14050731,
                      "latest_monthly_period": ["1405", "07", "30"]}, False,
              "remote non-string periods")

    # malformed local -> conservative update when the remote is usable
    ck_update({"latest_financial_period": "garbage",
               "latest_monthly_period": "also bad"},
              {"latest_financial_period": "1405/06/31"}, True,
              "local malformed + usable remote")
    for bad_local in ({"latest_financial_period": 123},
                      {"latest_monthly_period": {"x": 1}},
                      {"latest_financial_period": "1405/13/99"}):
        got = safe("should_update", bad_local,
                   {"latest_financial_period": "1405/01/01"})
        ck(got != "MISSING" and not str(got).startswith("raised"),
           "malformed local %r does not raise (%r)" % (bad_local, got))
    for bad_remote in ({"latest_financial_period": "x"},
                       {"latest_financial_period": []},
                       {"latest_monthly_period": 0}):
        got = safe("should_update", local, bad_remote)
        ck(got != "MISSING" and not str(got).startswith("raised"),
           "malformed remote %r does not raise (%r)" % (bad_remote, got))

    # non-padded / dash-separated periods compare by value, not by string
    ck_update({"latest_financial_period": "1405/06/31"},
              {"latest_financial_period": "1405-6-31"}, False,
              "same date with a different separator")
    ck_update({"latest_financial_period": "1405/6/31"},
              {"latest_financial_period": "1405/10/01"}, True,
              "month 10 beats month 6 (not string order)")

    # ── ۳) _local_meta: status first, DB fallback read-only ─────────────────
    work = os.path.join(TMP, "work_db")
    os.makedirs(work)
    S.WORK_DIR = work
    db = os.path.join(TMP, "market_copy.db")
    make_db(db, "1405/06/31", "1405/07/30")
    S.DB_PATH = db

    got = safe("_local_meta")
    ck(isinstance(got, dict), "_local_meta returns a dict (%r)" % (got,))
    if isinstance(got, dict):
        ck(got.get("latest_financial_period") == "1405/06/31",
           "status missing -> DB MAX(period_end) for FS (%r)"
           % (got.get("latest_financial_period"),))
        ck(got.get("latest_monthly_period") == "1405/07/30",
           "status missing -> DB MAX(period_end) for MS (%r)"
           % (got.get("latest_monthly_period"),))
        ck(got.get("source") == "db", "source is db when only the DB answered")

    # read-only: no journal/wal, no byte or mtime change
    before = os.stat(db)
    ck(not os.path.exists(db + "-journal") and not os.path.exists(db + "-wal"),
       "read-only DB read leaves no journal/wal behind")
    safe("_local_meta")
    after = os.stat(db)
    ck(before.st_size == after.st_size and before.st_mtime_ns == after.st_mtime_ns,
       "read-only DB read does not modify the database")

    # status periods win over the DB
    write_status(work, {"latest_periods": {"financial": "1405/09/31",
                                           "monthly": "1405/08/30"},
                        "last_success": "2026-10-25T18:30:00"})
    got = safe("_local_meta")
    ck(isinstance(got, dict)
       and got.get("latest_financial_period") == "1405/09/31"
       and got.get("latest_monthly_period") == "1405/08/30",
       "codal_auto_status latest_periods win over the DB (%r)" % (got,))
    ck(isinstance(got, dict) and got.get("source") == "status",
       "source is status when the status file answered")

    # top-level periods (plan shape) are honoured too
    write_status(work, {"latest_financial_period": "1405/10/31",
                        "latest_monthly_period": "1405/10/30"})
    got = safe("_local_meta")
    ck(isinstance(got, dict)
       and got.get("latest_financial_period") == "1405/10/31"
       and got.get("latest_monthly_period") == "1405/10/30",
       "top-level status periods are honoured (%r)" % (got,))

    # malformed status periods fall back to the DB instead of raising
    write_status(work, {"latest_periods": {"financial": "garbage",
                                           "monthly": ""}})
    got = safe("_local_meta")
    ck(isinstance(got, dict)
       and got.get("latest_financial_period") == "1405/06/31"
       and got.get("latest_monthly_period") == "1405/07/30",
       "malformed status periods -> DB fallback (%r)" % (got,))

    # db missing / tableless: honest empty, no raise
    write_status(work, {})
    S.DB_PATH = os.path.join(TMP, "does-not-exist.db")
    got = safe("_local_meta")
    ck(isinstance(got, dict)
       and not got.get("latest_financial_period")
       and not got.get("latest_monthly_period"),
       "missing DB + empty status -> empty meta (%r)" % (got,))

    empty_db = os.path.join(TMP, "empty.db")
    make_db(empty_db, tables=False)
    S.DB_PATH = empty_db
    got = safe("_local_meta")
    ck(isinstance(got, dict)
       and not got.get("latest_financial_period")
       and not got.get("latest_monthly_period"),
       "DB without the CODAL tables -> empty meta, no raise (%r)" % (got,))

    # empty periods in DB rows -> honest None
    null_db = os.path.join(TMP, "null.db")
    make_db(null_db, "", "")
    S.DB_PATH = null_db
    got = safe("_local_meta")
    ck(isinstance(got, dict)
       and not got.get("latest_financial_period")
       and not got.get("latest_monthly_period"),
       "NULL MAX(period_end) -> None, no raise (%r)" % (got,))

    # ── ۴) should_auto_check: the pure startup gate ─────────────────────────
    ck(safe("should_auto_check", frozen=False, env={}) is False,
       "dev/source without BORS_CODAL_AUTOUPDATE -> no auto-check")
    ck(safe("should_auto_check", frozen=False,
            env={"BORS_CODAL_AUTOUPDATE": "1"}) is True,
       "dev + BORS_CODAL_AUTOUPDATE=1 -> auto-check")
    ck(safe("should_auto_check", frozen=False,
            env={"BORS_CODAL_AUTOUPDATE": "true"}) is True,
       "dev + BORS_CODAL_AUTOUPDATE=true -> auto-check")
    ck(safe("should_auto_check", frozen=False,
            env={"BORS_CODAL_AUTOUPDATE": "0"}) is False,
       "explicit BORS_CODAL_AUTOUPDATE=0 -> no auto-check")
    ck(safe("should_auto_check", frozen=True, env={}) is True,
       "frozen/installed -> auto-check")
    ck(safe("should_auto_check", frozen=True, env={},
            fetch_loops_enabled=False) is False,
       "BORS_NO_FETCH_LOOPS=1 -> no auto-check")
    ck(safe("should_auto_check", frozen=False,
            env={"BORS_CODAL_AUTOUPDATE": "1"},
            fetch_loops_enabled=False) is False,
       "opt-in cannot override BORS_NO_FETCH_LOOPS=1")

    # ── ۵) source: worker keeps the safety chain, calendar is best-effort ───
    src = read_text(os.path.join(ROOT, "api", "_sync_codal.py"))
    worker, w_start = def_block(src, "def _codal_db_worker(")
    ck(w_start != -1, "worker block is locatable")
    ck("verify_minisign(" in worker and "UPDATE_PUBKEY" in worker,
       "worker still verifies the minisign signature with the app pubkey")
    ck("integrity_check" in worker,
       "worker still runs PRAGMA integrity_check before merging")
    ck("_CODAL_TABLES" in worker,
       "worker still verifies the three CODAL tables")
    ck("_apply_codal_merge(" in worker,
       "worker still merges through _apply_codal_merge")
    ck('CODAL_DB_URL + ".sig"' in worker,
       "signature is fetched from the same data-tag URL")
    i_verify = worker.find("verify_minisign(")
    i_integrity = worker.find("integrity_check")
    i_merge = worker.find("_apply_codal_merge(")
    i_cal = worker.find("_download_calendar(")
    i_done = worker.find('_write_db_status("done"')
    ck(-1 < i_verify < i_integrity < i_merge,
       "signature -> integrity -> merge order is kept")
    ck(-1 < i_merge < i_cal < i_done,
       "calendar download happens after a successful merge (%r,%r,%r)"
       % (i_merge, i_cal, i_done))
    ck(re.search(r"try:\s*\n\s*_download_calendar\(", worker) is not None,
       "calendar download is wrapped in its own try/except (no rollback)")
    ck("calendar" in worker.lower(), "worker names the calendar asset")

    cal, c_start = def_block(src, "def _download_calendar(")
    ck(c_start != -1, "_download_calendar exists")
    ck("CODAL_CAL_URL" in cal, "_download_calendar reads CODAL_CAL_URL")
    ck("calendar.json" in cal,
       "_download_calendar writes WORK_DIR/calendar.json")
    ck(".part" in cal, "_download_calendar downloads to a temp file first")
    ck('"events"' in cal,
       "_download_calendar validates the events payload before replacing")
    ck("except Exception" in cal and "return False" in cal,
       "_download_calendar never raises (returns False on failure)")

    # ── ۶) auto_check: meta URL only, never CODAL/ADB ──────────────────────
    auto, a_start = def_block(src, "def auto_check(")
    ck(a_start != -1, "auto_check exists")
    ck("CODAL_META_URL" in auto and "requests.get(" in auto,
       "auto_check fetches the meta URL")
    ck("should_update(" in auto and "_local_meta()" in auto,
       "auto_check compares remote meta with _local_meta")
    ck("_start_db_worker(" in auto,
       "auto_check starts the existing download/merge worker")
    ck("codal_fetcher" not in auto and "rotate_ip_via_adb" not in auto
       and "search.codal" not in auto and "adb" not in auto.lower(),
       "auto_check never touches CODAL/search/ADB")
    ck("except Exception" in auto and '"checked": False' in auto,
       "auto_check reports checked False on any network error")

    # ── ۷) db-status carries meta + freshness, old fields kept ─────────────
    status, s_start = def_block(src, "def sync_codal_db_status(")
    ck(s_start != -1, "db-status handler exists")
    for token in ('"running"', '"stage"', '"percent"', '"detail"', '"error"',
                  '"ts"'):
        ck(token in status, "db-status keeps %s" % token)
    ck('"meta"' in status, "db-status includes meta")
    ck('"freshness"' in status, "db-status includes freshness")
    ck("read_meta_cache(" in status, "db-status meta comes from the meta cache")
    fresh, f_start = def_block(src, "def _freshness(")
    ck("last_success" in fresh and "_local_meta(" in fresh,
       "freshness reports the local periods + last_success")

    # ── ۸) app.py: guarded, daemon, non-blocking startup auto-check ────────
    app_src = read_text(os.path.join(ROOT, "app.py"))
    ap_start = app_src.find("def _codal_auto_check")
    ap_end = app_src.find('@app.get("/", include_in_schema=False)', ap_start)
    ck(ap_start != -1 and ap_end > ap_start,
       "app.py defines the auto-check startup worker")
    block = app_src[ap_start:ap_end] if ap_end > ap_start else ""
    ck("should_auto_check(" in block and "auto_check()" in block,
       "startup worker consults the pure gate then auto_check")
    ck("_fetch_loops_enabled()" in block,
       "startup worker checks _fetch_loops_enabled()")
    ck("_FROZEN" in block, "startup worker passes bors_config._FROZEN")
    ck("threading.Thread(" in block and "daemon=True" in block,
       "startup worker runs in a daemon thread")
    ck("subprocess" not in block and ".wait(" not in block,
       "startup worker never spawns or blocks")
    ck("time.sleep" not in block, "startup worker does no startup sleep")
    ck("except Exception" in block, "startup failures are caught and logged")

    lines = block.splitlines()
    guard_idx = next((i for i, ln in enumerate(lines)
                      if "if _fetch_loops_enabled():" in ln), -1)
    thread_idx = next((i for i, ln in enumerate(lines)
                       if "threading.Thread(" in ln), -1)
    guard_indent = (len(lines[guard_idx]) - len(lines[guard_idx].lstrip())
                    if guard_idx != -1 else -1)
    thread_indent = (len(lines[thread_idx]) - len(lines[thread_idx].lstrip())
                     if thread_idx != -1 else -1)
    ck(guard_idx != -1, "auto-check thread start is guarded")
    ck(thread_idx > guard_idx and thread_indent > guard_indent,
       "thread start sits inside the _fetch_loops_enabled() guard")

    failed = [m for ok, m in CHECKS if not ok]
    if failed:
        print("\nFAILED %d/%d" % (len(failed), len(CHECKS)))
        for m in failed:
            print("  FAIL: %s" % m)
        raise SystemExit(1)
    print("\nOK client meta compare (%d checks)" % len(CHECKS))
finally:
    S.WORK_DIR = _ORIG_WORK_DIR
    S.DB_PATH = _ORIG_DB_PATH
    try:
        if hasattr(S, "_db_period_cache"):
            S._db_period_cache.clear()
            S._db_period_cache.update(_ORIG_CACHE)
    except Exception:
        pass
    shutil.rmtree(TMP, ignore_errors=True)
