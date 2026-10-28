#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/codal_auto_update.py — هماهنگ‌کنندهٔ شبانهٔ کدال، staging-first و بدونِ ADB.

خطِ لولهٔ روزانه (Phase 2، Task 3):

    main market.db
      → کپیِ امن در market.db.staging/
      → feed_sync رویِ همان staging (POLITE: بدونِ ADB)
      → validate_staging (گیت‌ها؛ شکست = main دست‌نخورده و publish رد می‌شود)
      → merge افزایشی در main
      → materialize با dev/codal_fts_updater.py --mode local --materialize --db <main>
      → build snapshot + sign + publish

قیدهایِ ثابت:
  * هیچ مرحلهٔ تولیدی در تست اجرا نمی‌شود (``_fetch``/``publish``/… جایگزین‌شدنی‌اند).
  * ``--db`` همیشه به subprocessِ updater داده می‌شود؛ اجرایِ تستی هرگز در
    ``market.db`` عملیاتی نمی‌نویسد.
  * خطا/شکستِ اعتبارسنجی هرگز «موفق» گزارش نمی‌شود: ``ok False`` + ``errors``
    و ``last_error`` در ``codal_auto_status.json``؛ ``last_success`` قبلی حفظ می‌شود.
  * تقویم (Task 7) هنوز وصل نیست؛ جایِ قلاب در ``run`` مشخص است.

استفاده:
    python dev/codal_auto_update.py --dry-run
    python dev/codal_auto_update.py --mode daily
"""
import argparse
import datetime
import json
import os
import pathlib
import sqlite3
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, "dev")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bors_config                        # noqa: E402
import codal_fetcher                      # noqa: E402
from codal_validation import validate_staging  # noqa: E402
from scripts.build_codal_snapshot import build_snapshot  # noqa: E402
import scripts.publish_codal_snapshot as publish_mod     # noqa: E402

publish = publish_mod.publish             # monkeypatchable seam for tests

DB_PATH = bors_config.DB_PATH
STAGING_DIR = os.path.join(ROOT, "market.db.staging")
STATUS = os.path.join(ROOT, "codal_auto_status.json")
LOCK = os.path.join(ROOT, "codal_auto.lock")
PAUSE = os.path.join(ROOT, "codal_auto_pause")
SNAPSHOT_LZMA = os.path.join(ROOT, "codal.db.lzma")
SNAPSHOT_META = os.path.join(ROOT, "codal.meta.json")
UPDATER = os.path.join(ROOT, "dev", "codal_fts_updater.py")
SIGN = os.path.join(ROOT, "scripts", "sign_setup.py")

# قفلِ جامانده از اجرایِ مرده بعد از ۶h آزاد می‌شود. تا آن لحظه هر اجرایِ
# دیگری «locked» می‌بیند؛ Task Scheduler نباید این را شکست بشمارد و دوباره
# اجرا کند (خروجِ ۰ برای locked/paused در _exit_code) و app.py هم در همین
# پنجره با cooldown از اسپاونِ دوباره خودداری می‌کند.
LOCK_STALE_SECONDS = 6 * 3600
MATERIALIZE_TIMEOUT = 3600
SIGN_TIMEOUT = 300

STATUS_DEFAULTS = {
    "stage": None,
    "mode": None,
    "started_at": None,
    "last_success": None,
    "last_error": None,
    "latest_periods": None,
    "validation": None,
    "published": False,
}


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _read_status():
    data = {}
    try:
        with open(STATUS, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    merged = dict(STATUS_DEFAULTS)
    merged.update(data)
    return merged


def _write_status(**fields):
    """به‌روزرسانیِ اتمیکِ فایلِ وضعیت؛ فیلدهایِ قبلی (از جمله last_success) می‌مانند."""
    st = _read_status()
    st.update(fields)
    st["updated_at"] = _now()
    tmp = STATUS + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(st, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, STATUS)
    except OSError as exc:
        print("[codal-auto] status write failed: %s" % exc,
              file=sys.stderr, flush=True)
        try:
            os.remove(tmp)
        except OSError:
            pass
    return st


def _acquire_lock(path=None):
    """قفلِ O_EXCL؛ None یعنی اجرایِ دیگری صاحبِ قفل است."""
    path = path or LOCK
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        try:
            age = time.time() - os.path.getmtime(path)
        except OSError:
            return None
        if age <= LOCK_STALE_SECONDS:
            return None
        try:
            os.remove(path)                 # قفلِ جامانده (کرش/قطع برق)
        except OSError:
            return None
        return _acquire_lock(path)
    except OSError:
        return None
    try:
        os.write(fd, ("%d %s" % (os.getpid(), _now())).encode("ascii", "replace"))
    finally:
        os.close(fd)
    return path


def _release_lock(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _backup_db(src_path, dst_path):
    """کپیِ سازگارِ main در staging با SQLite backup API (بی‌خواندنِ فایلِ زنده)."""
    if not os.path.isfile(src_path):
        raise FileNotFoundError("main db not found: %s" % src_path)
    for suffix in ("", "-wal", "-shm", "-journal"):
        try:
            os.remove(dst_path + suffix)
        except FileNotFoundError:
            pass
    src = sqlite3.connect(pathlib.Path(src_path).resolve().as_uri() + "?mode=ro",
                          uri=True, timeout=60)
    dst = sqlite3.connect(dst_path, timeout=60)
    try:
        src.backup(dst)
        dst.commit()
    finally:
        dst.close()
        src.close()


def _fetch(db_path):
    """واکشیِ فید در همان DBِ staging — POLITE (بدونِ ADB) و با بازگردانیِ globals."""
    prev_db = codal_fetcher.DB_PATH
    prev_polite = codal_fetcher.POLITE
    codal_fetcher.DB_PATH = db_path
    codal_fetcher.set_polite(True)
    try:
        return codal_fetcher.feed_sync(mode="update", optimized=True)
    finally:
        codal_fetcher.DB_PATH = prev_db
        codal_fetcher.set_polite(prev_polite)


def _run_cmd(argv, timeout):
    """مرحلهٔ subprocess؛ خروجِ غیرصفر استثنا می‌شود (نه موفقیتِ جعلی)."""
    proc = subprocess.run(
        argv, cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise RuntimeError("exit=%d%s" % (
            proc.returncode, (": " + tail[-1]) if tail else ""))
    return proc


def _load_last_good():
    """متادیتایِ آخرین snapshotِ سالم (اگر باشد) برایِ هشدارهایِ گیتِ last_good."""
    candidates = [SNAPSHOT_META, os.path.join(publish_mod.LAST, "codal.meta.json")]
    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and data:
                return data
        except (OSError, ValueError):
            continue
    return None


def _validation_summary(validation):
    if not isinstance(validation, dict):
        return None
    return {
        "ok": bool(validation.get("ok")),
        "errors": list(validation.get("errors") or []),
        "warnings": list(validation.get("warnings") or []),
    }


def _latest_periods(validation):
    stats = (validation or {}).get("stats") or {}
    return {"financial": stats.get("fs_latest"),
            "monthly": stats.get("ms_latest")}


def _fail(result, stage, message):
    result["ok"] = False
    result["errors"].append(message)
    _write_status(stage=stage, last_error="; ".join(result["errors"]))
    return result


def run(mode="daily", dry_run=False, db_path=None, staging_dir=None):
    """یک اجرایِ کامل؛ dictِ نتیجه طبقِ قراردادِ Task 3 برمی‌گرداند.

    ``staged`` یعنی staging ساخته و واکشی شد (نه این‌که merge/publish شد).
    در ``dry_run`` فقط تا اعتبارسنجی می‌رود و هیچ نوشتنی در main انجام نمی‌شود.
    """
    main_db = os.path.abspath(db_path or DB_PATH)
    staging_dir = os.path.abspath(staging_dir or STAGING_DIR)
    staging_db = os.path.join(staging_dir, "market.db")
    result = {"ok": False, "mode": mode, "staged": False, "validation": None,
              "snapshot": None, "published": False, "errors": []}
    started_at = _now()

    # ۱) کلیدِ توقف: پیش از هر کپی/شبکه.
    if os.path.exists(PAUSE):
        result["errors"].append("paused")
        _write_status(stage="paused", mode=mode, started_at=started_at,
                      last_error="paused", published=False)
        return result

    # ۲) قفلِ اجرایِ هم‌زمان.
    lock = _acquire_lock()
    if lock is None:
        result["errors"].append("locked")
        _write_status(stage="locked", mode=mode, started_at=started_at,
                      last_error="locked", published=False)
        return result

    try:
        _write_status(stage="backing_up", mode=mode, started_at=started_at,
                      last_error=None, published=False)

        # ۳) staging = کپیِ main؛ هیچ نوشتنی رویِ main تا پایانِ گیت‌ها.
        try:
            os.makedirs(staging_dir, exist_ok=True)
            _backup_db(main_db, staging_db)
        except Exception as exc:                       # noqa: BLE001
            return _fail(result, "backup_failed",
                         "backup: %s: %s" % (type(exc).__name__, exc))
        result["staged"] = True

        # ۴) واکشی فقط در staging.
        _write_status(stage="fetching")
        try:
            fetch_info = _fetch(staging_db)
        except Exception as exc:                       # noqa: BLE001
            return _fail(result, "fetch_failed",
                         "fetch: %s: %s" % (type(exc).__name__, exc))
        if isinstance(fetch_info, dict) and (
                fetch_info.get("blocked") or fetch_info.get("stopped")):
            reason = "blocked" if fetch_info.get("blocked") else "stopped"
            return _fail(result, "fetch_failed", "fetch:%s" % reason)

        # ۵) گیت‌هایِ staging؛ شکست = main دست‌نخورده.
        _write_status(stage="validating")
        try:
            validation = validate_staging(main_db, staging_db, _load_last_good())
        except Exception as exc:                       # noqa: BLE001
            return _fail(result, "validation_failed",
                         "validation: %s: %s" % (type(exc).__name__, exc))
        result["validation"] = validation
        periods = _latest_periods(validation)
        if not validation.get("ok"):
            result["errors"].extend(validation.get("errors") or [])
            if not result["errors"]:
                result["errors"].append("validation_failed")
            _write_status(stage="validation_failed",
                          validation=_validation_summary(validation),
                          latest_periods=periods, published=False,
                          last_error="; ".join(result["errors"]))
            return result

        if dry_run:
            result["ok"] = True
            _write_status(stage="dry_run_ok",
                          validation=_validation_summary(validation),
                          latest_periods=periods, published=False,
                          last_error=None)
            return result

        # TODO(Task 7): calendar_merge اینجا اجرا می‌شود (واکشیِ تقویم، بدونِ
        # وابستگی به این خطِ لوله). عمداً import نمی‌شود.
        _write_status(stage="merging", validation=_validation_summary(validation),
                      latest_periods=periods)

        # ۶) ادغام در main — فقط بعد از گیت‌هایِ موفق.
        try:
            from api._sync_codal import _apply_codal_merge
            _apply_codal_merge(main_db, staging_db)
        except Exception as exc:                       # noqa: BLE001
            return _fail(result, "merge_failed",
                         "merge: %s: %s" % (type(exc).__name__, exc))

        # ۷) materialize رویِ همان main (--db صریح؛ هرگز پیش‌فرضِ updater).
        _write_status(stage="materializing")
        try:
            _run_cmd([sys.executable, UPDATER, "--mode", "local",
                      "--materialize", "--db", main_db], MATERIALIZE_TIMEOUT)
        except Exception as exc:                       # noqa: BLE001
            return _fail(result, "materialize_failed",
                         "materialize: %s: %s" % (type(exc).__name__, exc))

        # ۸) snapshot + امضا + انتشار.
        _write_status(stage="snapshot")
        try:
            meta = build_snapshot(main_db, SNAPSHOT_LZMA, SNAPSHOT_META)
        except Exception as exc:                       # noqa: BLE001
            return _fail(result, "snapshot_failed",
                         "snapshot: %s: %s" % (type(exc).__name__, exc))
        result["snapshot"] = {"lzma": SNAPSHOT_LZMA, "meta": SNAPSHOT_META,
                              "latest_financial_period":
                                  (meta or {}).get("latest_financial_period"),
                              "latest_monthly_period":
                                  (meta or {}).get("latest_monthly_period")}

        _write_status(stage="signing")
        sig = SNAPSHOT_LZMA + ".sig"
        try:
            _run_cmd([sys.executable, SIGN, SNAPSHOT_LZMA], SIGN_TIMEOUT)
            if not os.path.isfile(sig):
                raise RuntimeError("signer produced no .sig")
        except Exception as exc:                       # noqa: BLE001
            return _fail(result, "sign_failed",
                         "sign: %s: %s" % (type(exc).__name__, exc))

        _write_status(stage="publishing")
        try:
            pub = publish(SNAPSHOT_LZMA, sig, SNAPSHOT_META)
        except Exception as exc:                       # noqa: BLE001
            return _fail(result, "publish_failed",
                         "publish: %s: %s" % (type(exc).__name__, exc))
        result["published"] = bool(isinstance(pub, dict) and pub.get("uploaded"))
        if not result["published"]:
            err = (pub or {}).get("error") if isinstance(pub, dict) else None
            return _fail(result, "publish_failed",
                         "publish: %s" % (err or "not uploaded"))

        result["ok"] = True
        _write_status(stage="done", last_success=_now(), last_error=None,
                      validation=_validation_summary(validation),
                      latest_periods=periods, published=True)
        return result
    except Exception as exc:                           # noqa: BLE001 - never fake success
        return _fail(result, "failed", "run: %s: %s" % (type(exc).__name__, exc))
    finally:
        _release_lock(lock)


_BENIGN_SKIPS = ("locked", "paused")


def _exit_code(result):
    """کدِ خروجِ CLI؛ قفل/توقف «رد شدنِ بی‌خطر» است، نه شکست.

    Task Scheduler با ``-RestartCount 2`` هر خروجِ غیرصفر را شکست می‌شمارد و
    ۱۵ دقیقه بعد دوباره اجرا می‌کند. اگر اجرایِ روزانه قفل را به اجرایِ
    زندهٔ دیگری (مثلاً catch-up) ببازد، تلاشِ دوباره پس از پایانِ آن اجرا
    کلِ واکشی/merge/publish را تکرار می‌کند. پس locked/paused → 0 و هر خطایِ
    واقعی (از جمله validation) → 1. قراردادِ ``run()`` دست نمی‌خورد؛ فقط
    نگاشتِ نتیجه به کدِ خروج اینجاست.
    """
    if not isinstance(result, dict):
        return 1
    if result.get("ok"):
        return 0
    errors = result.get("errors") or []
    if errors and all(isinstance(e, str) and e in _BENIGN_SKIPS for e in errors):
        return 0
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="CODAL staging-first daily auto-update (no ADB)")
    ap.add_argument("--mode", default="daily", choices=("daily", "manual"))
    ap.add_argument("--dry-run", action="store_true",
                    help="staging + validation only; main is not written")
    ap.add_argument("--db", default=None,
                    help="main DB path (default: bors_config.DB_PATH)")
    ap.add_argument("--staging-dir", default=None,
                    help="staging directory (default: <repo>/market.db.staging)")
    args = ap.parse_args(argv)
    res = run(mode=args.mode, dry_run=args.dry_run,
              db_path=args.db, staging_dir=args.staging_dir)
    if res["errors"]:
        for item in res["errors"]:
            print("ERROR " + item)
    print("ok=%s staged=%s published=%s" % (
        res["ok"], res["staged"], res["published"]))
    return _exit_code(res)


if __name__ == "__main__":
    sys.exit(main())
