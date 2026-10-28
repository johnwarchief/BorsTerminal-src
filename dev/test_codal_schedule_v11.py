# -*- coding: utf-8 -*-
"""dev/test_codal_schedule_v11.py — Task 6: daily schedule + startup catch-up.

Proves, with no network / CODAL / GitHub / ADB and no subprocess spawn:

  1) ``should_auto_update``: None/invalid/empty -> True; <24h -> False;
     >=24h -> True; aware+aware, naive+naive and mixed aware/naive inputs
     never raise; ``max_age_hours`` is honoured;
  2) ``read_auto_status`` returns ``{}`` for a missing/malformed/non-dict
     file and the parsed dict for a valid ``WORK_DIR/codal_auto_status.json``;
  3) the PowerShell scheduler carries every required Task Scheduler token
     (``BorsCodalAutoUpdate``, 18:30 daily, StartWhenAvailable, IgnoreNew,
     ExecutionTimeLimit 2h, RestartCount 2, the daily script and ``-Remove``);
  4) app.py guards the catch-up thread with ``_fetch_loops_enabled()`` and
     spawns ``dev/codal_auto_update.py --mode daily`` via a non-blocking
     daemon thread (Popen, never wait/run);
  5) ``codal_auto_pause`` is gitignored.

Run:  python dev/test_codal_schedule_v11.py  ->  OK schedule/catch-up
"""
import datetime as dt
import json
import os
import shutil
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

import api._sync_codal as S          # noqa: E402

CHECKS = []


def ck(cond, msg):
    CHECKS.append((bool(cond), msg))
    print("  %s %s" % ("PASS" if cond else "FAIL", msg))
    return bool(cond)


def read_text(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


TMP = tempfile.mkdtemp(prefix="codal_schedule_v11_")
_ORIG_POPEN = S.subprocess.Popen
_ORIG_WORK_DIR = S.WORK_DIR


def no_spawn(*_a, **_k):
    raise AssertionError("subprocess spawn is forbidden in this test")


try:
    # ── ۱) should_auto_update: missing / fresh / stale ──────────────────────
    S.subprocess.Popen = no_spawn          # any spawn attempt fails loudly
    NOW = dt.datetime(2026, 10, 21, 18, 0, 0)

    ck(S.should_auto_update(None, now=NOW) is True,
       "None last_success -> True")
    ck(S.should_auto_update(
        (NOW - dt.timedelta(hours=25)).isoformat(timespec="seconds"),
        now=NOW) is True, "25h old -> True")
    ck(S.should_auto_update(
        (NOW - dt.timedelta(hours=2)).isoformat(timespec="seconds"),
        now=NOW) is False, "2h old -> False")

    # ── ۲) aware / naive / mixed ISO inputs never raise ─────────────────────
    aware_now = dt.datetime(2026, 10, 21, 18, 0, 0, tzinfo=dt.timezone.utc)
    ck(S.should_auto_update("2026-10-20T19:00:00+00:00",
                            now=aware_now) is False,
       "aware ISO 23h old with aware now -> False")
    ck(S.should_auto_update("2026-10-19T19:00:00+00:00",
                            now=aware_now) is True,
       "aware ISO 47h old with aware now -> True")

    ck(S.should_auto_update(
        (NOW - dt.timedelta(hours=25)).isoformat(timespec="seconds"),
        now=NOW) is True, "naive ISO 25h old with naive now -> True")
    ck(S.should_auto_update(
        (NOW - dt.timedelta(hours=2)).isoformat(timespec="seconds"),
        now=NOW) is False, "naive ISO 2h old with naive now -> False")

    # mixed forms: the aware side's zone is attached to the naive side
    ck(S.should_auto_update(
        (aware_now - dt.timedelta(hours=25)).replace(tzinfo=None)
        .isoformat(timespec="seconds"), now=aware_now) is True,
       "naive ISO stale with aware now -> True (no raise)")
    ck(S.should_auto_update("2026-10-19T19:00:00+00:00", now=NOW) is True,
       "aware ISO stale with naive now -> True (no raise)")
    ck(S.should_auto_update("2026-10-20T19:00:00Z", now=aware_now) is False,
       "ISO-Z 23h old with aware now -> False (no raise)")

    # ── ۳) malformed / empty / non-string -> True, no exception ─────────────
    for bad in ("not-a-date", "", "   ", "2026-13-45T99:99:99",
                "2026-10-21", None, 123):
        try:
            got = S.should_auto_update(bad, now=NOW)
        except Exception as exc:                       # noqa: BLE001
            got = "raised %s: %s" % (type(exc).__name__, exc)
        ck(got is True, "invalid %r -> True (%r)" % (bad, got))
    ck(S.should_auto_update("garbage") is True,
       "invalid value with default now -> True (no raise)")

    # ── ۴) max_age_hours is honoured ────────────────────────────────────────
    two_h = (NOW - dt.timedelta(hours=2)).isoformat(timespec="seconds")
    ck(S.should_auto_update(two_h, now=NOW, max_age_hours=1) is True,
       "2h old with max_age_hours=1 -> True")
    ck(S.should_auto_update(two_h, now=NOW, max_age_hours=3) is False,
       "2h old with max_age_hours=3 -> False")

    # ── ۵) read_auto_status: missing / valid / malformed ────────────────────
    status_dir = os.path.join(TMP, "status")
    os.makedirs(status_dir)
    S.WORK_DIR = status_dir
    ck(S.read_auto_status() == {},
       "missing codal_auto_status.json -> {}")
    status_path = os.path.join(status_dir, "codal_auto_status.json")
    payload = {"last_success": "2026-10-21T18:00:00",
               "stage": "done", "published": True}
    with open(status_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    ck(S.read_auto_status() == payload,
       "valid status file -> parsed dict")
    with open(status_path, "w", encoding="utf-8") as fh:
        fh.write("{not valid json")
    ck(S.read_auto_status() == {}, "malformed JSON -> {}")
    with open(status_path, "w", encoding="utf-8") as fh:
        json.dump(["not", "a", "dict"], fh)
    ck(S.read_auto_status() == {}, "non-dict JSON -> {}")

    # ── ۶) PS1 scheduler: every required token ──────────────────────────────
    ps1_path = os.path.join(ROOT, "scripts", "schedule_codal_auto_update.ps1")
    ck(os.path.isfile(ps1_path), "scheduler script exists")
    ps1 = read_text(ps1_path)
    for token in ("BorsCodalAutoUpdate", "18:30", "-Daily",
                  "StartWhenAvailable", "MultipleInstances IgnoreNew",
                  "ExecutionTimeLimit", "RestartCount", "codal_auto_update.py",
                  "python dev/codal_auto_update.py --mode daily", "-Remove",
                  "Unregister-ScheduledTask"):
        ck(token in ps1, "PS1 contains %r" % token)
    ck("-Hours 2" in ps1, "PS1 caps execution at 2 hours")
    ck("-RestartCount 2" in ps1, "PS1 restarts twice")

    # ── ۷) app.py startup catch-up: guarded, daemon, non-blocking ───────────
    app_src = read_text(os.path.join(ROOT, "app.py"))
    ck("def _codal_auto_catchup" in app_src,
       "app.py defines the catch-up worker")
    start = app_src.find("def _codal_auto_catchup")
    end = app_src.find('@app.get("/", include_in_schema=False)', start)
    ck(start != -1 and end > start, "catch-up block is locatable")
    block = app_src[start:end]
    ck("read_auto_status" in block and "should_auto_update" in block,
       "catch-up consults read_auto_status + should_auto_update")
    ck("subprocess.Popen" in block, "catch-up spawns via subprocess.Popen")
    ck("subprocess.run" not in block and ".wait(" not in block,
       "catch-up never blocks on the child (no run/wait)")
    ck("dev/codal_auto_update.py" in block, "catch-up targets dev/codal_auto_update.py")
    ck('"--mode", "daily"' in block, "catch-up passes --mode daily")
    ck("daemon=True" in block, "catch-up thread is daemon")
    ck("time.sleep" not in block, "catch-up does no startup sleep")
    lines = block.splitlines()
    guard_idx = next((i for i, ln in enumerate(lines)
                      if "if _fetch_loops_enabled():" in ln), -1)
    thread_idx = next((i for i, ln in enumerate(lines)
                       if "threading.Thread(" in ln), -1)
    guard_indent = (len(lines[guard_idx]) - len(lines[guard_idx].lstrip())
                    if guard_idx != -1 else -1)
    thread_indent = (len(lines[thread_idx]) - len(lines[thread_idx].lstrip())
                     if thread_idx != -1 else -1)
    ck(guard_idx != -1, "catch-up thread start is guarded by _fetch_loops_enabled()")
    ck(thread_idx > guard_idx and thread_indent > guard_indent,
       "thread start sits inside the _fetch_loops_enabled() guard")
    ck("except Exception" in block,
       "catch-up failures are caught and logged, not raised")

    # ── ۸) pause switch is gitignored ───────────────────────────────────────
    gitignore = read_text(os.path.join(ROOT, ".gitignore"))
    ck("codal_auto_pause" in gitignore, ".gitignore contains codal_auto_pause")

    failed = [m for ok, m in CHECKS if not ok]
    if failed:
        print("\nFAILED %d/%d" % (len(failed), len(CHECKS)))
        raise SystemExit(1)
    print("\nOK schedule/catch-up (%d checks)" % len(CHECKS))
finally:
    S.subprocess.Popen = _ORIG_POPEN
    S.WORK_DIR = _ORIG_WORK_DIR
    shutil.rmtree(TMP, ignore_errors=True)
