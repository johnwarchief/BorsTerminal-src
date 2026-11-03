# -*- coding: utf-8 -*-
"""dev/test_codal_schedule_v11.py — Task 6: daily schedule + startup catch-up.

Proves, with no network / CODAL / GitHub / ADB and no subprocess spawn:

  1) ``should_auto_update``: None/invalid/empty/date-only -> True; <24h -> False;
     >24h -> True; aware+aware, naive+naive and mixed aware/naive inputs never
     raise; ``max_age_hours`` is honoured;
  2) ``should_start_catchup`` (pure): dev/source without
     ``BORS_CODAL_AUTOUPDATE=1`` -> False; frozen -> allowed only when the
     script exists; fresh status, pause, ``BORS_NO_FETCH_LOOPS=1`` and a recent
     attempt all -> False; aware/naive/malformed/date-only/future ``started_at``
     never raise and do not fake a cooldown;
  3) ``read_auto_status`` returns ``{}`` for a missing/malformed/non-dict
     file and the parsed dict for a valid ``WORK_DIR/codal_auto_status.json``;
  4) the PowerShell scheduler carries every required Task Scheduler token
     (``BorsCodalAutoUpdate``, 18:30 daily, StartWhenAvailable, IgnoreNew,
     ExecutionTimeLimit 2h, RestartCount 0 (no ban-hammering), the daily script and ``-Remove``);
  5) app.py routes the catch-up decision through ``should_start_catchup`` and
     spawns ``dev/codal_auto_update.py --mode daily`` via a non-blocking
     daemon thread (Popen, never wait/run); in dev defaults the decision is
     False and Popen is not called at all;
  6) ``codal_auto_pause`` is gitignored.

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

    # ── ۴٫۵) date-only ISO is stale, even just after midnight ───────────────
    ck(S.should_auto_update("2026-10-21",
                            now=dt.datetime(2026, 10, 21, 1, 0, 0)) is True,
       "date-only ISO -> True (stale; never parsed as today's midnight)")

    # exact 24h boundary: code uses >, so 24h exactly is still fresh
    ck(S.should_auto_update(NOW.isoformat(timespec="seconds"),
                            now=NOW + dt.timedelta(hours=24)) is False,
       "exactly 24h old -> False (boundary is >24h)")
    ck(S.should_auto_update(NOW.isoformat(timespec="seconds"),
                            now=NOW + dt.timedelta(hours=24, seconds=1)) is True,
       "24h+1s old -> True")

    # a corrupt/clock-skewed future timestamp is untrusted -> stale
    ck(S.should_auto_update((NOW + dt.timedelta(hours=25))
                            .isoformat(timespec="seconds"), now=NOW) is True,
       "future last_success (+25h) -> True (untrusted, not fresh forever)")
    ck(S.should_auto_update((NOW + dt.timedelta(seconds=60))
                            .isoformat(timespec="seconds"), now=NOW) is False,
       "future last_success (+60s skew) -> False (within tolerance)")

    # ── ۵) should_start_catchup: every gate (pure, no I/O, no spawn) ────────
    stale_status = {"last_success": (NOW - dt.timedelta(hours=25))
                    .isoformat(timespec="seconds")}
    fresh_status = {"last_success": (NOW - dt.timedelta(hours=2))
                    .isoformat(timespec="seconds")}

    ck(S.should_start_catchup(stale_status, frozen=False, env={}, now=NOW)
       is False, "dev/source without BORS_CODAL_AUTOUPDATE -> no catch-up")
    ck(S.should_start_catchup(stale_status, frozen=False,
                              env={"BORS_CODAL_AUTOUPDATE": "0"},
                              now=NOW) is False,
       "explicit BORS_CODAL_AUTOUPDATE=0 -> no catch-up")
    ck(S.should_start_catchup(stale_status, frozen=False,
                              env={"BORS_CODAL_AUTOUPDATE": "1"},
                              now=NOW) is True,
       "dev + BORS_CODAL_AUTOUPDATE=1 + stale -> catch-up")
    ck(S.should_start_catchup(stale_status, frozen=True, env={}, now=NOW)
       is True, "frozen/installed + stale -> catch-up allowed")
    ck(S.should_start_catchup(stale_status, frozen=True, env={},
                              script_exists=False, now=NOW) is False,
       "frozen install without dev/ script -> no catch-up (skips)")
    ck(S.should_start_catchup(fresh_status, frozen=True, env={}, now=NOW)
       is False, "fresh last_success -> no catch-up")
    ck(S.should_start_catchup({}, frozen=True, env={}, now=NOW) is True,
       "missing status -> catch-up (conservative stale)")
    ck(S.should_start_catchup(None, frozen=True, env={}, now=NOW) is True,
       "non-dict status -> catch-up (conservative stale)")
    ck(S.should_start_catchup(stale_status, frozen=True, env={},
                              paused=True, now=NOW) is False,
       "codal_auto_pause -> no catch-up")
    ck(S.should_start_catchup(stale_status, frozen=True, env={},
                              fetch_loops_enabled=False, now=NOW) is False,
       "BORS_NO_FETCH_LOOPS=1 -> no catch-up")

    # ── ۶) failure cooldown: last attempt within 6h suppresses the run ──────
    def attempt_status(hours, **extra):
        status = dict(stale_status)
        status["started_at"] = (NOW - dt.timedelta(hours=hours)).isoformat(
            timespec="seconds")
        status["last_error"] = "fetch: boom"
        status.update(extra)
        return status

    ck(S.should_start_catchup(attempt_status(2), frozen=True, env={}, now=NOW)
       is False,
       "failed attempt 2h ago + stale last_success -> no catch-up (6h cooldown)")
    ck(S.should_start_catchup(attempt_status(6), frozen=True, env={}, now=NOW)
       is False, "attempt exactly 6h ago -> still in cooldown")
    ck(S.should_start_catchup(attempt_status(7), frozen=True, env={}, now=NOW)
       is True, "failed attempt 7h ago -> catch-up allowed")
    ck(S.should_start_catchup(
        attempt_status(6 + 1 / 3600.0), frozen=True, env={}, now=NOW) is True,
       "attempt 6h+1s ago -> catch-up allowed")

    # aware/naive/malformed timestamps never raise and never fake a cooldown
    aware_now = dt.datetime(2026, 10, 21, 18, 0, 0, tzinfo=dt.timezone.utc)
    aware_status = {"last_success": "2026-10-19T19:00:00+00:00",
                    "started_at": "2026-10-21T16:00:00+00:00"}   # 2h ago
    ck(S.should_start_catchup(aware_status, frozen=True, env={},
                              now=aware_now) is False,
       "aware started_at + aware now 2h -> cooldown (no raise)")
    mixed_status = {
        "last_success": "2026-10-19T19:00:00+00:00",
        "started_at": (aware_now - dt.timedelta(hours=2))
        .replace(tzinfo=None).isoformat(timespec="seconds")}
    ck(S.should_start_catchup(mixed_status, frozen=True, env={},
                              now=aware_now) is False,
       "naive started_at + aware now 2h -> cooldown (no raise)")
    naive_aware_status = {
        "last_success": stale_status["last_success"],
        "started_at": "2026-10-21T16:00:00+00:00"}              # 2h before NOW
    ck(S.should_start_catchup(naive_aware_status, frozen=True, env={},
                              now=NOW) is False,
       "aware started_at + naive now 2h -> cooldown (no raise)")

    for bad_started in ("garbage", "", "   ", "2026-13-45T99:99:99",
                        "2026-10-21", 123, None):
        status = dict(stale_status, started_at=bad_started)
        try:
            got = S.should_start_catchup(status, frozen=True, env={}, now=NOW)
        except Exception as exc:                       # noqa: BLE001
            got = "raised %s: %s" % (type(exc).__name__, exc)
        ck(got is True,
           "bad started_at %r -> cooldown ignored, catch-up (%r)"
           % (bad_started, got))

    future_status = dict(
        stale_status,
        started_at=(NOW + dt.timedelta(hours=25)).isoformat(timespec="seconds"))
    ck(S.should_start_catchup(future_status, frozen=True, env={}, now=NOW)
       is True, "future started_at (clock skew) -> ignored, catch-up allowed")

    updated_status = dict(stale_status,
                          updated_at=(NOW - dt.timedelta(hours=1)).isoformat(
                              timespec="seconds"))
    ck(S.should_start_catchup(updated_status, frozen=True, env={}, now=NOW)
       is False,
       "updated_at fallback keeps the cooldown when started_at is absent")

    # ── ۷) read_auto_status: missing / valid / malformed ────────────────────
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

    # ── ۸) PS1 scheduler: every required token ──────────────────────────────
    ps1_path = os.path.join(ROOT, "scripts", "schedule_codal_auto_update.ps1")
    ck(os.path.isfile(ps1_path), "scheduler script exists")
    ps1 = read_text(ps1_path)
    for token in ("BorsCodalAutoUpdate", "18:30", "-Daily",
                  "StartWhenAvailable", "MultipleInstances IgnoreNew",
                  "ExecutionTimeLimit", "RestartCount", "codal_auto_update.py",
                  "-Remove", "Unregister-ScheduledTask"):
        ck(token in ps1, "PS1 contains %r" % token)
    ck('$Script = "dev/codal_auto_update.py"' in ps1,
       "PS1 builds the action from the daily script path")
    ck("$Argument" in ps1 and "--mode daily" in ps1,
       "PS1 action argument carries --mode daily")
    ck("-Hours 2" in ps1, "PS1 caps execution at 2 hours")
    ck("-RestartCount 0" in ps1, "PS1 never auto-retries a banned fetch")
    ck("-RestartInterval" not in ps1, "PS1 has no retry interval")

    # ── ۹) startup catch-up decision: dev defaults never spawn ──────────────
    # The test's WORK_DIR currently holds a non-dict status -> read_auto_status
    # returns {} (stale). Even so, source mode without BORS_CODAL_AUTOUPDATE
    # must decide False and Popen must not be called.
    spawn_calls = []

    def record_spawn(*args, **kwargs):
        spawn_calls.append((args, kwargs))

    S.subprocess.Popen = record_spawn
    decision = S.should_start_catchup(
        S.read_auto_status(), frozen=False, env={},
        fetch_loops_enabled=True, paused=False, script_exists=True, now=NOW)
    ck(decision is False,
       "startup decision in dev without opt-in -> False")
    ck(spawn_calls == [],
       "startup decision False -> subprocess.Popen never called")
    S.subprocess.Popen = no_spawn

    # ── ۱۰) app.py startup catch-up: guarded, daemon, non-blocking ──────────
    app_src = read_text(os.path.join(ROOT, "app.py"))
    ck("def _codal_auto_catchup" in app_src,
       "app.py defines the catch-up worker")
    start = app_src.find("def _codal_auto_catchup")
    end = app_src.find('@app.get("/", include_in_schema=False)', start)
    ck(start != -1 and end > start, "catch-up block is locatable")
    block = app_src[start:end]
    ck("should_start_catchup(" in block and "read_auto_status" in block,
       "catch-up consults read_auto_status + should_start_catchup")
    ck("should_auto_update" not in block,
       "catch-up does not call should_auto_update directly")
    for kw in ("frozen=", "env=", "fetch_loops_enabled=", "paused=",
               "script_exists="):
        ck(kw in block, "catch-up passes %s to the helper" % kw)
    ck("script not found" in block,
       "frozen install without dev/ logs the skip")
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

    # ── ۱۱) pause switch is gitignored ──────────────────────────────────────
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
