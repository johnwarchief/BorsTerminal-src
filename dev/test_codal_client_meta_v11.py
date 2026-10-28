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
     a guarded daemon thread;
  6) I1 boot race: ``boot_sync`` runs exactly one of catch-up/auto-check,
     ``_orchestrator_busy`` honours a fresh Task 6 lock/status (6h stale rule),
     ``_start_db_worker``/``auto_check`` refuse to start while it is busy, and
     the worker re-checks immediately before the merge (with a fake requests
     layer, so an orchestrator that starts mid-download aborts without merging
     and leaves a non-error ``skipped`` stage).

Run:  python dev/test_codal_client_meta_v11.py  ->  OK client meta compare
"""
import datetime
import json
import lzma
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time

try:                       # Persian/UTF-8 output on a cp1252 Windows console
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

import api._sync_codal as S          # noqa: E402
import bors_minisign                 # noqa: E402

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
_ORIG_STATUS_PATH = S.CODAL_DB_STATUS_PATH
_ORIG_REQUESTS = S.requests
_ORIG_START_WORKER = S._start_db_worker
_ORIG_APPLY_MERGE = S._apply_codal_merge
_ORIG_VERIFY = bors_minisign.verify_minisign
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


def now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")


def make_snapshot_lzma(path):
    """A minimal, integrity-checkable CODAL snapshot (three tables) as .lzma."""
    raw = path + ".raw"
    con = sqlite3.connect(raw)
    try:
        for table in S._CODAL_TABLES:
            con.execute('CREATE TABLE "%s" (tracing_no INTEGER PRIMARY KEY)'
                        % table)
        con.commit()
    finally:
        con.close()
    with open(raw, "rb") as src, lzma.open(path, "wb") as dst:
        shutil.copyfileobj(src, dst)
    os.remove(raw)


def stream_response(payload):
    """Minimal context-manager response for the worker's streamed download."""
    class _Stream:
        headers = {"Content-Length": str(len(payload))}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def raise_for_status(self):
            pass

        def iter_content(self, _size):
            yield payload

    return _Stream()


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

    # ── ۶٫۵) I1: one boot decision + orchestrator mutual exclusion ──────────
    # Pure decision: when the catch-up spawns, auto-check is never started (the
    # gate is not even evaluated). A failed spawn may fall through; fresh state
    # (catch-up false) runs auto-check.
    calls = []
    got = safe("boot_sync",
               lambda: True,
               lambda: calls.append("gate") or True,
               lambda: calls.append("spawn") or True,
               lambda: calls.append("auto"))
    ck(got == "catchup", "boot_sync: catch-up decision wins (%r)" % (got,))
    ck(calls == ["spawn"],
       "catch-up spawned -> auto-check gate/call never runs (%r)" % (calls,))

    calls.clear()
    got = safe("boot_sync", lambda: False, lambda: True,
               lambda: calls.append("spawn") or True,
               lambda: calls.append("auto"))
    ck(got == "auto_check" and calls == ["auto"],
       "fresh catch-up -> auto-check runs (%r, %r)" % (got, calls))

    def _raise_spawn():
        raise RuntimeError("popen failed")

    calls.clear()
    got = safe("boot_sync", lambda: True, lambda: True, _raise_spawn,
               lambda: calls.append("auto"))
    ck(got == "auto_check" and calls == ["auto"],
       "failed spawn falls through to auto-check, no exception (%r, %r)"
       % (got, calls))

    calls.clear()
    got = safe("boot_sync", lambda: False, lambda: False,
               lambda: calls.append("spawn") or True,
               lambda: calls.append("auto"))
    ck(got == "" and calls == [],
       "both gates closed -> no action, no exception (%r, %r)" % (got, calls))

    # Client side: a fresh Task 6 lock/status makes the download path busy.
    race = os.path.join(TMP, "race")
    os.makedirs(race)
    S.WORK_DIR = race
    S.CODAL_DB_STATUS_PATH = os.path.join(race, "codal_db_status.json")
    race_db = os.path.join(TMP, "race_market.db")
    make_db(race_db, "1405/06/31", "1405/06/30")
    S.DB_PATH = race_db
    lock = os.path.join(race, "codal_auto.lock")

    ck(safe("_orchestrator_busy") is False,
       "idle: no lock/status -> orchestrator not busy")
    with open(lock, "w", encoding="utf-8") as fh:
        fh.write("other-owner")
    ck(safe("_orchestrator_busy") is True,
       "fresh codal_auto.lock -> orchestrator busy")
    old = time.time() - (S.ORCHESTRATOR_LOCK_STALE_SECONDS + 60)
    os.utime(lock, (old, old))
    ck(safe("_orchestrator_busy") is False,
       "stale lock (>6h) -> orchestrator not busy (crash-safe)")
    os.remove(lock)
    write_status(race, {"stage": "merging", "updated_at": now_iso()})
    ck(safe("_orchestrator_busy") is True,
       "fresh non-terminal status (merging) -> orchestrator busy")
    write_status(race, {"stage": "done", "updated_at": now_iso()})
    ck(safe("_orchestrator_busy") is False,
       "terminal status (done) -> orchestrator not busy")
    write_status(race, {"stage": "merging",
                        "updated_at": (datetime.datetime.now()
                                       - datetime.timedelta(hours=7))
                        .isoformat(timespec="seconds")})
    ck(safe("_orchestrator_busy") is False,
       "stale non-terminal status (>6h) -> orchestrator not busy")

    write_status(race, {"stage": "done", "updated_at": now_iso()})
    with open(lock, "w", encoding="utf-8") as fh:
        fh.write("other-owner")
    reason = safe("_start_db_worker")
    ck(reason == "orchestrator",
       "_start_db_worker returns 'orchestrator' instead of starting (%r)"
       % (reason,))
    ck(S._dbdl_running is False,
       "no download thread is started while the orchestrator holds the lock")
    os.remove(lock)

    write_status(race, {"stage": "merging", "updated_at": now_iso()})
    reason = safe("_start_db_worker")
    ck(reason == "orchestrator",
       "_start_db_worker also honours a fresh non-terminal status (%r)"
       % (reason,))
    ck(S._dbdl_running is False,
       "no download thread is started while the orchestrator status is active")
    write_status(race, {"stage": "done", "updated_at": now_iso()})

    # auto_check checks the same gate before starting the worker (no network).
    class _MetaResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"latest_financial_period": "1405/08/31",
                    "latest_monthly_period": "1405/07/30"}

    class _MetaRequests:
        @staticmethod
        def get(url, **_kwargs):
            return _MetaResp()

    S.requests = _MetaRequests
    starts = []
    S._start_db_worker = lambda auto=False: (starts.append(auto) or "")
    with open(lock, "w", encoding="utf-8") as fh:
        fh.write("other-owner")
    res = safe("auto_check")
    ck(isinstance(res, dict) and res.get("update") is True
       and res.get("started") is False
       and res.get("skipped") == "orchestrator",
       "auto_check skips the download while the orchestrator is busy (%r)"
       % (res,))
    ck(starts == [],
       "auto_check never calls _start_db_worker while orchestrator is busy")
    os.remove(lock)
    starts.clear()
    res = safe("auto_check")
    ck(isinstance(res, dict) and res.get("update") is True
       and res.get("started") is True and starts == [True],
       "auto_check starts the shared worker when no orchestrator runs (%r)"
       % (res,))

    # Worker re-check immediately before merge: an orchestrator that starts
    # mid-download must abort the merge, keep the DB, and record "skipped".
    snap_lzma = os.path.join(race, "snapshot_src.db.lzma")
    make_snapshot_lzma(snap_lzma)
    with open(snap_lzma, "rb") as fh:
        snap_payload = fh.read()
    write_status(race, {"stage": "done", "updated_at": now_iso()})
    merge_calls = []

    def _forbidden_merge(*_a, **_k):
        merge_calls.append(True)
        raise AssertionError("merge must not run while orchestrator is busy")

    S._apply_codal_merge = _forbidden_merge
    bors_minisign.verify_minisign = lambda *_a, **_k: None

    class _WorkerRequests:
        @staticmethod
        def get(url, **_kwargs):
            if url == S.CODAL_DB_URL + ".sig":
                class _Sig:
                    text = "fake-sig"

                    def raise_for_status(self):
                        pass

                return _Sig()
            # The orchestrator starts while the download is in flight.
            write_status(race, {"stage": "merging", "updated_at": now_iso()})
            return stream_response(snap_payload)

    S.requests = _WorkerRequests
    dest = os.path.join(race, "snapshot_dl.db.lzma")
    tmpdb = os.path.join(race, "snapshot_dl.db")
    got = safe("_codal_db_worker", dest, tmpdb, True)
    ck(not str(got).startswith("raised"),
       "worker aborts benignly when the orchestrator starts mid-download (%r)"
       % (got,))
    ck(merge_calls == [],
       "worker does not call _apply_codal_merge while orchestrator is busy")
    ck(not os.path.exists(dest) and not os.path.exists(tmpdb),
       "worker removes its temp snapshot files after the skip")
    with open(S.CODAL_DB_STATUS_PATH, "r", encoding="utf-8") as fh:
        db_st = json.load(fh)
    ck(db_st.get("stage") == "skipped" and not db_st.get("error"),
       "worker records a non-error 'skipped' stage (%r)" % (db_st,))

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

    # exactly one codal startup thread, and it owns the single boot decision
    ck("def _codal_boot_sync" in app_src,
       "app.py has one boot-decision function for both codal paths")
    ck("boot_sync(" in app_src,
       "app.py routes catch-up/auto-check through the shared boot_sync helper")
    ck("threading.Thread(target=_codal_boot_sync" in app_src,
       "app.py starts exactly one codal startup thread")
    ck("threading.Thread(target=_codal_auto_catchup" not in app_src
       and "threading.Thread(target=_codal_auto_check" not in app_src,
       "no independent catch-up/auto-check threads exist anymore")

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
    S.CODAL_DB_STATUS_PATH = _ORIG_STATUS_PATH
    S.requests = _ORIG_REQUESTS
    S._start_db_worker = _ORIG_START_WORKER
    S._apply_codal_merge = _ORIG_APPLY_MERGE
    bors_minisign.verify_minisign = _ORIG_VERIFY
    try:
        if hasattr(S, "_db_period_cache"):
            S._db_period_cache.clear()
            S._db_period_cache.update(_ORIG_CACHE)
    except Exception:
        pass
    shutil.rmtree(TMP, ignore_errors=True)
