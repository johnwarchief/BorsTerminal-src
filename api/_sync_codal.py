"""Codal fetcher supervision: launch, stop, status and diagnosis.

Split verbatim out of app.py (v9.8.1 modularisation).
Every statement is byte-for-byte identical to app.py; only the route
decorators changed from @app.<verb> to @router.<verb>.
Audit map of source line spans: MIGRATED_LINES.txt
"""
from ._core import _count_procs, _kill_procs, _safe_read_json, codal_crawler_available
from bors_config import APP_DIR, CONTROL_PATH, DB_PATH, MARKET_STATUS_PATH, OD_STATUS_PATH, STATUS_PATH, WORK_DIR
from fastapi import APIRouter
from fastapi import Query
from fastapi import Request
import codal_fetcher
import datetime
import json
import lzma
import os
import requests
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path


router = APIRouter()


@router.post("/api/sync/codal")
def sync_codal(mode: str = Query("update")):
    # گارد: اگر اسکنی در حال اجراست، فرایند جدید اجرا نکن (۲ اسکن همزمان = ۴۲۹ دائمی)
    if _codal_running():
        return {"status": "already_running",
                "message": "اسکن کدال در حال اجراست — صبر کنید تا تمام شود.",
                "mode": mode}
    # پاکسازی فرمان stop ماندگار؛ وگرنه نمونهٔ تازهٔ codal_fetcher فوراً خودش را متوقف میکند
    try:
        with open(CONTROL_PATH, "w", encoding="utf-8") as f:
            json.dump({"cmd": "resume", "ts": datetime.datetime.now().isoformat(timespec="seconds")}, f, ensure_ascii=False)
    except Exception:
        pass
    if not codal_crawler_available():
        return {"status": "unavailable", "mode": mode,
                "message": "خزندهٔ کدال فقط رویِ درختِ توسعه اجرا می‌شود؛ درِ نسخۀ "
                           "نصبی زیرپروسه، خودِ برنامه را دوباره بالا می‌آورد. برایِ "
                           "دادهٔ تازه دکمۀ «بروزرسانی دیتابیس کدال» (snapshot گیت‌هاب) "
                           "را بزنید."}
    args = [sys.executable, "codal_fetcher.py"]
    if mode == "new":
        args += ["--backfill"]         # نمادهای قابل معامله با عنوان مالی ولی بدون FS → ۵ شاخص پرشدنی
    elif mode == "update":
        args += ["--feed", "update"]   # فید سراسری افزایشی از آخرین تاریخ DB (نمادهای موجود)
    elif mode == "optimized":
        args += ["--feed", "update", "--optimized"]   # بهینه: فقط FS قدیمی/خالی + نمادهای جدید (حداقل درخواست — بدون بلاک IP)
    elif mode == "backfill":
        args += ["--backfill"]         # Backfill FS/MS برای نمادهای دارای عنوان صورت مالی
    subprocess.Popen(args)
    return {"status": "success", "message": "Codal sync started.", "mode": mode}


@router.post("/api/sync/codal/fts-refresh")
def sync_codal_fts_refresh(mode: str = Query("monthly")):
    """تازه‌سازیِ فقط ۵ شاخصِ FTS از کدال (dev/codal_fts_updater.py) با چرخشِ IP.
    گارد: اجرای هم‌زمان ممنوع (ریسکِ ۴۲۹/بن)."""
    if _codal_running():
        return {"status": "already_running",
                "message": "اسکن کدال در حال اجراست — صبر کنید.", "mode": mode}
    script = os.path.join(APP_DIR, "dev", "codal_fts_updater.py")
    if not os.path.isfile(script):
        # بیلدِ فریزشده پوشهٔ dev/ را ندارد (در نصبِ زنده راستی‌آزمایی شد)، پس
        # خزندهٔ کدال اینجا وجود ندارد و نباید هم باشد: چرخشِ IP با ADB ابزارِ
        # ماشینِ خودِ مالک است، نه کاربر. پیش از این همان‌جا «یافت نشد» برمی‌گشت
        # و فرانت پاسخ را دور می‌ریخت — یعنی دکمهٔ «بروزرسانی» بی‌صدا هیچ‌کار
        # نمی‌کرد. حالا دستِ‌کم کشِ محلی پاک می‌شود تا اسکرینر از همین
        # دیتابیسِ موجود دوباره محاسبه کند و پیام، راهِ گرفتنِ دادهٔ تازه را
        # بگوید (دکمهٔ «بروزرسانی دیتابیس کدال» از snapshot گیت‌هاب).
        from .screener import invalidate_screener_cache
        # fts_results را نمی‌پاک کند: در این بیلد هیچ نویسنده‌ای برایش نیست و
        # پاک‌کردنش اسکرینر را برای همیشه به محاسبهٔ زندهٔ ~۲۷ثانیه‌ای می‌انداخت.
        invalidate_screener_cache(drop_materialized=False)
        return {"status": "local_recompute", "mode": mode,
                "message": "خزندهٔ کدال در این نسخه نیست؛ شاخص‌ها از دیتابیسِ "
                           "محلی دوباره محاسبه می‌شوند. برای دادهٔ تازه دکمهٔ "
                           "«بروزرسانی دیتابیس کدال» را بزنید."}
    try:
        with open(CONTROL_PATH, "w", encoding="utf-8") as f:
            json.dump({"cmd": "resume", "ts": datetime.datetime.now().isoformat(timespec="seconds")}, f, ensure_ascii=False)
    except Exception:
        pass
    subprocess.Popen([sys.executable, script, "--mode", mode, "--adb-rotate", "--resume"], cwd=APP_DIR)
    return {"status": "success", "message": "FTS 5-indicator refresh started.", "mode": mode}


# ---------------------------------------------------------------------------
# بروزرسانی دیتابیس کدال از snapshot گیت‌هاب (بدون خزندهٔ زنده)
#
# چرا از گیت‌هاب: search.codal.ir پشت WAF/فیلتر است و خزندهٔ زنده روی بنِ IP
# گیر می‌کند؛ snapshot امضانشدهٔ ریلیز تنها منبعِ قابل اتکا برای کاربر است.
# اگر دانلود بلاک شود، همان مکانیزم چرخش IP سلولی codal_fetcher (ADB
# airplane-mode toggle) فعال می‌شود — گوشیِ tether شده IP تازه می‌گیرد.
#
# Task 8a: منبع، تگِ دادهٔ پایدارِ ``data-codal`` است نه ``latest`` ریلیزِ
# برنامه — snapshot نباید به نسخهٔ اپ Coupling شود و دکمهٔ دستی هم باید همان
# فایلِ امضاشدهٔ auto-check را بگیرد، پس نامِ ``CODAL_DB_URL`` حفظ شده و فقط
# مقصدش عوض شده است. ``.sig`` کنارش روی همان تگ است.
# ---------------------------------------------------------------------------
CODAL_DATA_TAG = "data-codal"
CODAL_BASE = ("https://github.com/johnwarchief/BorsTerminal/releases/download/"
              + CODAL_DATA_TAG)
CODAL_DB_URL = CODAL_BASE + "/codal.db.lzma"
CODAL_META_URL = CODAL_BASE + "/codal.meta.json"
CODAL_CAL_URL = CODAL_BASE + "/calendar.json"
CODAL_DB_STATUS_PATH = os.path.join(WORK_DIR, "codal_db_status.json")
_CODAL_TABLES = ("codal_notices", "financial_statements", "monthly_sales")
_dbdl_lock = threading.Lock()
_dbdl_running = False


CATCHUP_OPT_IN_ENV = "BORS_CODAL_AUTOUPDATE"
CATCHUP_COOLDOWN_HOURS = 6.0
_FUTURE_SKEW_SECONDS = 300          # timestampِ آیندهٔ دور = خراب/اختلافِ ساعت
_TRUTHY = ("1", "true", "yes", "on")


def _parse_iso(raw):
    """ISO timestamp → datetime؛ خالی/date-only/نامعتبر → None.

    date-only (``2026-10-21``) عمداً timestamp شمرده نمی‌شود: fromisoformat
    آن را نیمه‌شب می‌فهمد و «امروزِ نیمه‌شب» می‌تواند یک اجرایِ کهنه را تازه
    جا بزند. نویسندهٔ وضعیت همیشه ساعت را می‌نویسد.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    raw = raw.strip()
    if "T" not in raw and " " not in raw:
        return None
    if raw.endswith(("Z", "z")):       # ISO-Z → offset؛ fromisoformat پیش از 3.11 نه
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None


def _age_seconds(raw, now=None):
    """سنِ raw نسبت به now (ثانیه)؛ None یعنی خالی/نامعتبر/غیرقابلِ‌مقایسه.

    aware/naive مخلوط هم پذیرفته می‌شود: اگر یک طرف tzinfo داشته باشد و طرفِ
    دیگر نه، منطقۀ طرفِ aware به طرفِ naive چسبانده می‌شود تا مقایسه هرگز
    ``TypeError: can't subtract offset-naive and offset-aware`` ندهد.
    """
    stamp = _parse_iso(raw)
    if stamp is None:
        return None
    if now is None:
        now = (datetime.datetime.now(stamp.tzinfo) if stamp.tzinfo is not None
               else datetime.datetime.now())
    if stamp.tzinfo is not None and now.tzinfo is None:
        now = now.replace(tzinfo=stamp.tzinfo)
    elif stamp.tzinfo is None and now.tzinfo is not None:
        stamp = stamp.replace(tzinfo=now.tzinfo)
    try:
        return (now - stamp).total_seconds()
    except (TypeError, ValueError, OverflowError):
        return None


def should_auto_update(last_success_iso, now=None, max_age_hours=24):
    """آیا اجرایِ خودکارِ کدال کهنه است؟ (خالص، stdlib، بدونِ شبکه)

    None/خالی/تاریخِ نامعتبر/date-only → True (محافظه‌کارانه: یک اجرایِ اضافی
    بهتر از دادهٔ کهنه است). تازۀ کمتر از max_age_hours → False؛ کهنه‌تر →
    True. timestampِ آیندهٔ دور (بیش از ۵ دقیقه اختلافِ ساعت/فایلِ خراب) هم
    قابلِ اتکا نیست → True. timestampهایِ aware و naive (و مخلوطِ آن‌ها) بدونِ
    استثنا مقایسه می‌شوند.
    """
    age = _age_seconds(last_success_iso, now)
    if age is None:
        return True
    if age < -_FUTURE_SKEW_SECONDS:
        return True
    try:
        return bool(age > float(max_age_hours) * 3600.0)
    except (TypeError, ValueError, OverflowError):
        return True


def recently_attempted(status, now=None, cooldown_hours=CATCHUP_COOLDOWN_HOURS):
    """آیا آخرین تلاش در پنجرهٔ cooldown است؟ (خالص، بدونِ I/O)

    ``started_at`` در هر تلاش — موفق یا ناموفق — نوشته می‌شود؛ در نبودش
    ``updated_at`` همان نقش را دارد. اگر last_success کهنه باشد ولی تلاشِ
    تازه‌ای شکست خورده باشد، اجرایِ دوباره فقط درخواستِ تکراری به کدال
    می‌فرستد (سقفِ درخواست). timestampهایِ aware/naive/نامعتبر نباید استثنا
    بدهند: نامعتبر → cooldown ندارد (اجازهٔ تلاش)؛ آیندهٔ دور (اختلافِ ساعت یا
    فایلِ خراب) هم قابلِ اتکا نیست.
    """
    if not isinstance(status, dict):
        return False
    raw = status.get("started_at") or status.get("updated_at")
    age = _age_seconds(raw, now)
    if age is None or age < -_FUTURE_SKEW_SECONDS:
        return False
    try:
        return bool(age <= float(cooldown_hours) * 3600.0)
    except (TypeError, ValueError, OverflowError):
        return False


def _env_enabled(env, name):
    """آیا env[name] یکی از مقادیرِ صریحِ 1/true/yes/on است؟"""
    try:
        value = (env or {}).get(name)
    except AttributeError:
        return False
    return str(value or "").strip().lower() in _TRUTHY


def should_start_catchup(status, frozen, env=None, fetch_loops_enabled=True,
                         paused=False, script_exists=True, now=None,
                         max_age_hours=24,
                         cooldown_hours=CATCHUP_COOLDOWN_HOURS):
    """آیا نخِ استارت مجاز است ``dev/codal_auto_update.py`` را بالا بیاورد؟ (خالص)

    همهٔ درها باید باز باشند:
      ۱) حالتِ سورس فقط با opt-inِ صریحِ ``BORS_CODAL_AUTOUPDATE=1``؛ نصبِ
         frozen/portable خودش opt-in است. این در هارنس‌هایِ تستی/توسعه‌ای که
         app را بدونِ ``BORS_NO_FETCH_LOOPS`` بالا می‌آورند، واکشیِ واقعی
         نمی‌سازد.
      ۲) ``_fetch_loops_enabled()`` (``BORS_NO_FETCH_LOOPS=1`` خاموشش می‌کند).
      ۳) نه paused (فایلِ ``codal_auto_pause``).
      ۴) ``last_success`` کهنه (``should_auto_update``) و آخرین تلاش بیرون از
         cooldownِ ۶ساعته (``recently_attempted``) — تلاشِ ناموفقِ تازه دوباره
         کلِ خطِ لوله را اجرا نمی‌کند.
      ۵) اسکریپت موجود باشد؛ بیلدِ frozen پوشهٔ ``dev/`` را همراه ندارد.

    تابع هیچ I/O ندارد: status/env/زمان/وجودِ اسکریپت همه ورودی‌اند.
    """
    if not fetch_loops_enabled or paused or not script_exists:
        return False
    if not frozen and not _env_enabled(env, CATCHUP_OPT_IN_ENV):
        return False
    if recently_attempted(status, now=now, cooldown_hours=cooldown_hours):
        return False
    last_success = status.get("last_success") if isinstance(status, dict) else None
    return bool(should_auto_update(last_success, now=now,
                                   max_age_hours=max_age_hours))


def should_auto_check(frozen, env=None, fetch_loops_enabled=True):
    """آیا نخِ استارت مجاز است یک‌بار ``auto_check`` را صدا بزند؟ (خالص)

    همان درِ Task 6: در حالتِ سورس فقط با opt-inِ صریحِ
    ``BORS_CODAL_AUTOUPDATE=1``؛ نصبِ frozen/portable خودش opt-in است؛ و
    ``_fetch_loops_enabled()`` (``BORS_NO_FETCH_LOOPS=1``) همیشه و بر هر
    opt-in مقدم است. هیچ I/O ندارد، پس هارنس‌هایِ تست/توسعه بدونِ هیچ
    درخواستی همین تابع را می‌سنجند.
    """
    if not fetch_loops_enabled:
        return False
    return bool(frozen) or _env_enabled(env, CATCHUP_OPT_IN_ENV)


def read_auto_status():
    """خواندنِ WORK_DIR/codal_auto_status.json؛ هر خطا → {}.

    مسیر درِ هر فراخوانی از WORK_DIR ساخته می‌شود (نه یک ثابتِ import-time)،
    تا تست بتواند WORK_DIR را به پوشۀِ موقت بچسباند و مسیرِ واقعی لمس نشود.
    """
    try:
        with open(os.path.join(WORK_DIR, "codal_auto_status.json"),
                  "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:                                      # noqa: BLE001
        return {}
    return data if isinstance(data, dict) else {}


def _period_key(value):
    """'1405/06/31' → (1405, 6, 31)؛ هر چیزِ دیگر → None (بدونِ استثنا).

    دوره‌ها در هر سه سازنده به شکلِ ``YYYY/MM/DD`` نوشته می‌شوند ولی ورودیِ
    این مقایسه از فایلِ وضعیت و متایِ گیت‌هاب می‌آید — هر دو بیرونی‌اند.
    مقایسه رویِ تاپلِ عددی است نه رشته، وگرنه '1405/6/31' و '1405/06/31'
    دو دورهٔ متفاوت شمرده می‌شدند و '1405/10/01' کوچک‌تر از '1405/6/31'.
    """
    if not isinstance(value, str):
        return None
    parts = value.strip().replace("-", "/").split("/")
    if len(parts) != 3:
        return None
    try:
        year, month, day = (int(p) for p in parts)
    except (TypeError, ValueError):
        return None
    if year < 1000 or not 1 <= month <= 12 or not 1 <= day <= 31:
        return None
    return (year, month, day)


def should_update(local, remote):
    """آیا snapshotِ tag داده از دادهٔ محلی تازه‌تر است؟ (خالص، بدونِ شبکه)

    فقط دوره‌هایِ FS/MS مقایسه می‌شوند (رأیِ مالک: معیارِ تازگی، دوره است نه
    published_at). قواعد:
      * ``local`` نبود/دیکشنری نبود → True؛
      * مقدارِ remote نامعتبر/خالی برایِ یک کلید → همان کلید نادیده گرفته
        می‌شود (دادهٔ بی‌معنا هرگز دانلود را قلقلک نمی‌دهد)؛
      * مقدارِ local نامعتبر ولی remote معتبر → True (محافظه‌کارانه).
    هیچ ورودی‌ای استثنا نمی‌دهد.
    """
    if not isinstance(remote, dict):
        return False
    if not isinstance(local, dict) or not local:
        return True
    for key in ("latest_financial_period", "latest_monthly_period"):
        remote_key = _period_key(remote.get(key))
        if remote_key is None:
            continue
        local_key = _period_key(local.get(key))
        if local_key is None or remote_key > local_key:
            return True
    return False


# جدول → کلیدِ متا. همان دو جدولی که دوره‌شان در متایِ snapshot می‌آید.
_DB_MAX_TABLES = (("financial_statements", "latest_financial_period"),
                  ("monthly_sales", "latest_monthly_period"))
# کشِ MAX(period_end) با کلیدِ (path, mtime, size): db-status هر ۲ ثانیه
# پولینگ می‌شود و هر بار اسکنِ جدول‌هایِ صدها-هزار-ردیفی پذیرفتنی نیست.
_db_period_cache = {"hit": (None, {})}


def _db_max_periods(db_path):
    """MAX(period_end) جدول‌هایِ FS/MS از خودِ بانک — فقط-خواندنی.

    ``mode=ro`` عمداً انتخاب شده: این تابع درِ نخِ استارت و درِ GET وضعیت
    اجرا می‌شود و هرگز نباید journal/lock یا mtime رویِ بانکِ عملیاتی بگذارد.
    نبودِ فایل/جدول/ستون → همان کلید غایب، بدونِ استثنا.
    """
    path = str(db_path or "")
    try:
        stat = os.stat(path)
        key = (os.path.abspath(path), stat.st_mtime_ns, stat.st_size)
    except OSError:
        return {}
    cached = _db_period_cache.get("hit") or (None, {})
    if cached[0] == key:
        return dict(cached[1])
    out = {}
    con = None
    try:
        con = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro",
                              uri=True, timeout=10)
        for table, field in _DB_MAX_TABLES:
            try:
                row = con.execute(
                    'SELECT MAX(period_end) FROM "%s"' % table).fetchone()
            except sqlite3.Error:
                continue
            if row and row[0]:
                out[field] = row[0]
    except (sqlite3.Error, OSError, ValueError):
        return {}
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:
                pass
    _db_period_cache["hit"] = (key, dict(out))
    return out


def _local_meta():
    """دوره‌هایِ محلی برایِ مقایسه با متایِ tag داده (بدونِ شبکه).

    اولویت با ``codal_auto_status.json`` است (نتیجهٔ آخرین اجرایِ خودکار:
    ``latest_periods`` یا کلیدهایِ هم‌نام). اگر آن نبود/ناقص بود، خودِ
    ``market.db`` فقط-خواندنی خوانده می‌شود — بدونِ این fallback، محلی همیشه
    «خالی» می‌ماند و هر بوت دوباره کلِ snapshot را می‌کشید (رأیِ مالک).
    """
    st = read_auto_status()
    periods = st.get("latest_periods")
    if not isinstance(periods, dict):
        periods = {}
    fs = st.get("latest_financial_period") or periods.get("financial")
    ms = st.get("latest_monthly_period") or periods.get("monthly")
    source = "status" if (fs or ms) else ""
    if _period_key(fs) is None or _period_key(ms) is None:
        db = _db_max_periods(DB_PATH)
        if _period_key(fs) is None and _period_key(
                db.get("latest_financial_period")) is not None:
            fs = db.get("latest_financial_period")
            source = (source + "+db") if source == "status" else "db"
        if _period_key(ms) is None and _period_key(
                db.get("latest_monthly_period")) is not None:
            ms = db.get("latest_monthly_period")
            source = (source + "+db") if source == "status" else "db"
    return {"latest_financial_period": fs or None,
            "latest_monthly_period": ms or None,
            "source": source}


def _meta_cache_path():
    """مسیرِ کشِ متایِ snapshot؛ مثل read_auto_status درِ هر فراخوانی از WORK_DIR."""
    return os.path.join(WORK_DIR, "codal_meta.json")


def _write_meta_cache(meta):
    """آخرین متایِ دیدهٔ گیت‌هاب را ذخیره کن تا db-status بی‌شبکه هم نشانش دهد."""
    try:
        payload = dict(meta)
        payload["checked_at"] = datetime.datetime.now().isoformat(
            timespec="seconds")
        path = _meta_cache_path()
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:                                      # noqa: BLE001
        pass


def read_meta_cache():
    """آخرین متایِ snapshot که auto_check دیده؛ نبود/خرابی → {}."""
    try:
        with open(_meta_cache_path(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:                                      # noqa: BLE001
        return {}
    return data if isinstance(data, dict) else {}


def _freshness():
    """تازگیِ دادهٔ محلی برایِ db-status: دوره‌ها + آخرین اجرایِ موفقِ خودکار."""
    local = _local_meta()
    status = read_auto_status()
    return {"latest_financial_period": local.get("latest_financial_period"),
            "latest_monthly_period": local.get("latest_monthly_period"),
            "source": local.get("source", ""),
            "last_success": status.get("last_success") or ""}


def _write_db_status(stage, percent=0.0, detail="", error=""):
    try:
        tmp = CODAL_DB_STATUS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"stage": stage, "percent": percent, "detail": detail,
                       "error": error,
                       "ts": datetime.datetime.now().isoformat(timespec="seconds")},
                      f, ensure_ascii=False)
        os.replace(tmp, CODAL_DB_STATUS_PATH)
    except Exception:
        pass


def _merge_codal_snapshot(main, tmp_db):
    """ادغامِ افزایشیِ snapshot کدال در market.db. برمی‌گرداند: (stats, stale).

    stats[جدول] = (به‌سازی‌شده، درج‌شده، ردیفِ محلیِ تازه‌تر که دست‌نخورده ماند)
    stale = ستون‌هایی که در snapshot نیستند و więc حفظ شدند.

    دو محافظِ داده، هر دو تصادفی نبودند:
      ۱) فقط ستون‌های مشترک لمس می‌شوند. INSERT OR REPLACE ردیف را حذف و دوباره
         درج می‌کند، پس هر ستونی که snapshot نمی‌شناسد (مثل has_operating_sales)
         بی‌صدا NULL می‌شد و کاربر پیام «موفق» می‌دید. UPDATE...FROM این کار را
         نمی‌کند و UPSERT هم در SQLite با SELECT قابلِ پارس نیست.
      ۲) ردیفی که در DB محلی *تازه‌تر* از snapshot است بازنویسی نمی‌شود
         (CODAL-MERGE-1): تا پیش از این، فشردنِ «بروزرسانی دیتابیس کدال» رویِ
         اسنپ‌شاتِ کهنهٔ گیت‌هاب صورت‌مالیِ اصلاحیهٔ همان هفتهٔ کاربر را با عددِ
         قدیمی جایگزین می‌کرد — یعنی خودِ دکمه داده را عقب می‌برد.
         مقایسه رویِ رشتهٔ 'YYYY-MM-DD HH:MM:SS' است که هر دو مسیر با همان قالب
         می‌نویسند، پس ترتیبِ لغت‌نگاشتی == ترتیبِ زمانی. اگر یکی از دو طرف
         stamped نباشد، داوری محافظه‌کارانه است: محلیِ بی‌تاریخ جای خود را
         می‌دهد، ولی snapshotِ بی‌تاریخ محلیِ تاریخ‌دار را نمی‌بلعد.
         جدولِ بی‌fetched_at (monthly_sales) دقیقاً همان رفتارِ قبلی دارد.
    """
    main.execute("ATTACH DATABASE ? AS src", (tmp_db,))
    stats, stale = {}, []
    try:
        for t in _CODAL_TABLES:
            src_cols = {r[1] for r in main.execute('PRAGMA src.table_info("%s")' % t)}
            dst_cols = [r[1] for r in main.execute('PRAGMA main.table_info("%s")' % t)]
            common = [c for c in dst_cols if c in src_cols]
            if not common:
                raise ValueError("no common columns for table %s" % t)
            dropped = [c for c in dst_cols if c not in src_cols]
            if dropped:
                stale.append("%s: %s" % (t, ",".join(dropped)))
            collist = ",".join('"%s"' % c.replace('"', '""') for c in common)
            upd = ",".join('"%s"=sr."%s"' % (c, c.replace('"', '""')) for c in common)
            recency = ""
            if "fetched_at" in common:
                recency = (' AND (main."%s".fetched_at IS NULL OR main."%s".fetched_at = ""'
                           ' OR sr.fetched_at >= main."%s".fetched_at)' % (t, t, t))
            overlap = int(main.execute(
                'SELECT COUNT(*) FROM src."%s" sr JOIN main."%s" m'
                ' ON sr."tracing_no" = m."tracing_no"' % (t, t)).fetchone()[0])
            cur_upd = main.execute(
                'UPDATE main."%s" SET %s FROM src."%s" AS sr '
                'WHERE sr."tracing_no" = main."%s"."tracing_no"%s'
                % (t, upd, t, t, recency))
            cur_ins = main.execute(
                'INSERT INTO main."%s" (%s) SELECT %s FROM src."%s" '
                'WHERE "tracing_no" NOT IN '
                '(SELECT "tracing_no" FROM main."%s")'
                % (t, collist, collist, t, t))
            upd_n = cur_upd.rowcount or 0
            stats[t] = (upd_n, cur_ins.rowcount or 0, max(0, overlap - upd_n))
    finally:
        main.commit()
        try:
            main.execute("DETACH DATABASE src")
        except sqlite3.Error:
            pass
    return stats, stale


def _apply_codal_merge(db_path, tmp_db):
    """ادغامِ کاملِ snapshot در market.db — از اتصال تا commit.

    این لایه عمداً تابعِ واحد است: تستِ آفلاین فقط `_merge_codal_snapshot` را
    صدا می‌زد، پس DETACHِ دوباره در سمتِ فراخوان (که ادغامِ موفق را error
    می‌کرد) هیچ‌وقت سنجیده نشد و به نسخهٔ منتشرشده رفت.
    """
    main = sqlite3.connect(db_path, timeout=60)
    try:
        main.execute("PRAGMA busy_timeout=60000")
        stats, stale = _merge_codal_snapshot(main, tmp_db)
        main.commit()
        # fts_results کش‌شده با دادهٔ تازه کهنه شد — اسکرینر زنده بازمحاسبه کند
        try:
            import fts_engine
            fts_engine.invalidate_fts_results(main)
            main.commit()
        except Exception:
            pass
        return stats, stale
    finally:
        main.close()


def _download_calendar(dest_path=None):
    """کشِ تقویم را از tag داده می‌گیرد؛ True = جایگزین شد. هرگز raise نمی‌کند.

    ``WORK_DIR/calendar.json`` اولین ورودیِ ``api.chart`` است، پس محتوایِ
    دانلودشده ورودیِ بیرونی/نامعتمد است: فقط dictی که ``events``ش لیست باشد
    پذیرفته می‌شود؛ بعد در فایلِ ``.part`` نوشته و اتمیک جایگزین می‌شود تا
    پاسخِ نیمه‌کاره/HTML هرگز تقویمِ موجود را خالی نکند. شکست بی‌صداست و
    اجرایِ موفقِ بعدی دوباره تلاش می‌کند — تقویم هرگز merge را برنمی‌گرداند.
    """
    path = dest_path or os.path.join(WORK_DIR, "calendar.json")
    part = path + ".part"
    try:
        resp = requests.get(CODAL_CAL_URL, timeout=(10, 30),
                            headers={"User-Agent": "BorsTerminal-CodalDB"})
        resp.raise_for_status()
        payload = resp.json()
        if not isinstance(payload, dict) or not isinstance(
                payload.get("events"), list):
            return False
        with open(part, "wb") as fh:
            fh.write(resp.content)
        os.replace(part, path)
        return True
    except Exception:                                      # noqa: BLE001
        try:
            os.remove(part)
        except OSError:
            pass
        return False


def _codal_db_worker(dest_lzma, tmp_db, auto=False):
    global _dbdl_running
    try:
        # ۱) دانلود با retry + چرخش IP (rotate_ip_via_adb خودش gate دارد:
        #    adb_config.json enabled + دستگاه متصل + حداقل فاصلهٔ ۱۲۰ ثانیه)
        attempt = 0
        sig_text = ""
        while True:
            attempt += 1
            try:
                _write_db_status(
                    "downloading", 0.0,
                    ("دریافت خودکار codal.db.lzma (تلاش %d)" if auto
                     else "دریافت codal.db.lzma از گیت‌هاب (تلاش %d)") % attempt)
                with requests.get(CODAL_DB_URL, stream=True, timeout=(10, 60),
                                  headers={"User-Agent": "BorsTerminal-CodalDB"}) as resp:
                    resp.raise_for_status()
                    total = int(resp.headers.get("Content-Length") or 0)
                    n = 0
                    part = dest_lzma + ".part"
                    with open(part, "wb") as dst:
                        for chunk in resp.iter_content(1 << 20):
                            dst.write(chunk)
                            n += len(chunk)
                            if total:
                                _write_db_status(
                                    "downloading", round(100.0 * n / total, 1),
                                    "دریافت %d از %d مگابایت" % (n >> 20, total >> 20))
                    os.replace(part, dest_lzma)
                sig_resp = requests.get(CODAL_DB_URL + ".sig", timeout=(10, 60),
                                        headers={"User-Agent": "BorsTerminal-CodalDB"})
                sig_resp.raise_for_status()
                sig_text = sig_resp.text.strip()
                break
            except Exception as exc:
                if attempt >= 3:
                    raise
                _write_db_status("rotating", 0.0,
                                 "دانلود ناموفق (%s) — چرخش IP با ADB"
                                 % type(exc).__name__)
                try:
                    codal_fetcher.rotate_ip_via_adb(quiet=True)
                except Exception:
                    pass
                time.sleep(5)

        # ۱٫۵) راستی‌آزمایی امضای minisign — همان قراردادِ آپدیتِرِ درون‌برنامه‌ای
        #      (api/update.py): snapshot بی‌امضا یا دستکاری‌شده هرگز merge نمی‌شود.
        #      خطای امضا retry/rotate نمی‌گیرد — مستقیم به وضعیت error می‌رود.
        _write_db_status("verifying", 0.0, "راستی‌آزمایی امضای دیجیتال snapshot")
        from bors_minisign import verify_minisign
        from .update import UPDATE_PUBKEY
        with open(dest_lzma, "rb") as f:
            verify_minisign(f.read(), sig_text, UPDATE_PUBKEY)

        # ۲) بازکردن lzma + راستی‌آزمایی snapshot قبل از هر نوشتن روی market.db
        _write_db_status("decompressing", 0.0, "بازکردن فشرده‌سازی lzma")
        with lzma.open(dest_lzma, "rb") as src, open(tmp_db, "wb") as out:
            shutil.copyfileobj(src, out, 1 << 20)
        snap = sqlite3.connect(tmp_db, timeout=30)
        try:
            ic = snap.execute("PRAGMA integrity_check").fetchone()
            if not ic or ic[0] != "ok":
                raise ValueError("snapshot integrity_check failed: %r" % (ic,))
            have = {r[0] for r in snap.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            missing = [t for t in _CODAL_TABLES if t not in have]
            if missing:
                raise ValueError("snapshot lacks tables: %s" % ",".join(missing))
        finally:
            snap.close()

        # ۳) merge افزایشی در market.db — هر سه جدول PK=tracing_no دارند.
        #    از UPSERT استفاده می‌شود نه INSERT OR REPLACE: آن دستور ردیفِ
        #    موجود را حذف و دوباره درج می‌کند، پس هر ستونی که در snapshot نباشد
        #    (مثلاً has_operating_sales که بعد از ساخته‌شدن snapshot اضافه شده)
        #    بی‌صدا به NULL برمی‌گردد و کاربر پیام «موفق» می‌بیند. UPSERT فقط
        #    ستون‌های مشترک را لمس می‌کند و بقیه را دست‌نخورده می‌گذارد.
        _write_db_status("merging", 0.0, "ادغام در market.db")
        stats, stale = _apply_codal_merge(DB_PATH, tmp_db)
        # payloadِ اسکرینر از همین جدول‌ها ساخته می‌شود و TTL‑ش ۱۲ ساعت است (به‌علاوه
        # کشِ رویِ دیسک، پس با restart هم نمی‌رود). بدونِ این، کاربر بعد از
        # «بروزرسانی دیتابیس کدال» تا ۱۲ ساعت همان اعدادِ قدیمیِ تبِ بنیادی را
        # می‌دید. گرم‌کردن درِ همین نخ انجام می‌شود تا اولین درخواست ~۲۷ ثانیه
        # پایِ محاسبه نپردازد.
        try:
            from .screener import invalidate_screener_cache, warm_screener_cache
            invalidate_screener_cache(drop_materialized=False)
            warm_screener_cache()
        except Exception as _e:      # noqa: BLE001 — گرم‌کردنِ مجدد هرگز ادغام را عقب نمی‌زند
            print(f"[codal-db] screener re-warm failed: {_e}")
        if stale:
            # snapshot قدیمی‌تر از DB محلی است؛ دادهٔ از‌دست‌رفته خبر می‌خواهد
            _write_db_status(
                "merging", 0.5,
                "snapshot قدیمی است؛ ستون‌های تازه حفظ شدند: " + " | ".join(stale))

        # ۳٫۵) تقویمِ tag داده — best-effort و فقط بعد از mergeِ موفق. شکستِ
        #      تقویم نه ردیفی را برمی‌گرداند نه stage را error می‌کند؛ try/exceptِ
        #      خودش لازم است چون این بلوک داخلِ tryِ بزرگِ worker است و هر
        #      استثنا آن را «خطا در بروزرسانی» نشان می‌داد.
        try:
            _download_calendar()
        except Exception as _ce:      # noqa: BLE001 — هرگز merge را عقب نمی‌زند
            print(f"[codal-db] calendar refresh failed: {_ce}")

        # پیامِ پایان باید صادقانه باشد. پیش‌تر فقط ردیف‌های *درج‌شده* شمرده
        # می‌شدند، پس هر حالتی که ردیفِ تازه‌ای نداشت (از جمله به‌روزرسانیِ درجا)
        # «codal_notices: 0 ردیف · …» نشان می‌داد در حالی که سرِ کاربر
        # «بروزرسانی شد» می‌خواند — کاربر نمی‌فهمید داده‌اش عوض شده یا نه.
        # SQLite ردیف‌های UPDATE...FROM را حتی وقتی مقدار عوض نشود می‌شمارد، پس
        # «به‌سازی» به معنی «تازه‌ای اضافه نشد» است، نه «داده تغییر کرد».
        ins_n = sum(i for _, i, _k in stats.values())
        upd_n = sum(u for u, _, _k in stats.values())
        keep_n = sum(k for _, _, k in stats.values())
        if ins_n:
            detail = ("دیتابیس کدال به‌روز شد — %d ردیف تازه، %d ردیف به‌سازی"
                      % (ins_n, upd_n))
        elif upd_n:
            detail = ("دیتابیس کدال به‌روز است — %d ردیف بررسی شد و دادهٔ تازه‌ای "
                      "اضافه نشد" % upd_n)
        else:
            detail = "دیتابیس کدال به‌روز است — ردیف مشترکی برای به‌روزرسانی نبود"
        if stale:
            detail += " · snapshot کهنه بود؛ ستون‌های تازهٔ محلی حفظ شدند"
        if keep_n:
            detail += (" · %d ردیفِ محلی تازه‌تر از snapshot بود و دست‌نخورده ماند" % keep_n)
        _write_db_status("done", 100.0, detail)
    except Exception as exc:                                   # noqa: BLE001
        _write_db_status("error", 0.0, "",
                         "خطا در بروزرسانی دیتابیس کدال — %s: %s"
                         % (type(exc).__name__, exc))
    finally:
        for p in (dest_lzma, tmp_db, dest_lzma + ".part"):
            try:
                os.remove(p)
            except OSError:
                pass
        with _dbdl_lock:
            _dbdl_running = False


def _start_db_worker(auto=False):
    """نخِ دانلود/ادغام را یک‌بار بالا بیاورد؛ "" = شروع شد، وگرنه دلیل.

    همان درهایِ مسیرِ دستی: دانلودِ دوم ممنوع، و merge هم‌زمان با اسکنِ زندهٔ
    کدال (دو نویسنده رویِ همان جدول‌ها = ۴۲۹ دائمی) ممنوع. پرچمِ ``auto`` فقط
    متنِ وضعیت را «دریافت خودکار» می‌کند؛ ایمنیِ مسیر یکی است.
    """
    global _dbdl_running
    with _dbdl_lock:
        if _dbdl_running:
            return "running"
        if _codal_running():
            return "scanning"
        _dbdl_running = True
    dest = os.path.join(WORK_DIR, "codal_snapshot.db.lzma")
    tmp = os.path.join(WORK_DIR, "codal_snapshot.db")
    try:
        threading.Thread(target=_codal_db_worker, args=(dest, tmp),
                         kwargs={"auto": auto}, daemon=True).start()
    except Exception:                                      # noqa: BLE001
        with _dbdl_lock:
            _dbdl_running = False
        return "thread_failed"
    return ""


def auto_check(timeout=(10, 30)):
    """یک‌بار متایِ tag داده را بخوان و در صورتِ نیاز دریافت را شروع کن.

    فقط ``CODAL_META_URL`` خوانده می‌شود؛ دانلودِ امضاشده/merge همان
    ``_codal_db_worker`` است. هر خطایِ شبکه/JSON → ``checked: False`` بدونِ
    استثنا: بالا آمدنِ برنامه هرگز نباید به دسترس‌پذیریِ گیت‌هاب گره بخورد.
    خزندهٔ زنده/جستجو در این مسیر صدا زده نمی‌شود.
    """
    try:
        resp = requests.get(CODAL_META_URL, timeout=timeout,
                            headers={"User-Agent": "BorsTerminal-CodalDB"})
        resp.raise_for_status()
        remote = resp.json()
    except Exception:                                      # noqa: BLE001
        return {"checked": False, "update": False, "meta": None}
    if not isinstance(remote, dict) or not remote:
        return {"checked": False, "update": False, "meta": None}
    _write_meta_cache(remote)
    local = _local_meta()
    update = should_update(local, remote)
    started = False
    if update:
        started = _start_db_worker(auto=True) == ""
    return {"checked": True, "update": update, "meta": remote,
            "local": local, "started": started}


@router.post("/api/sync/codal/db-download")
def sync_codal_db_download():
    """بروزرسانی دیتابیس کدال فقط از snapshot گیت‌هاب (بدون خزندهٔ زندهٔ codal.ir)."""
    reason = _start_db_worker()
    if reason == "running":
        return {"status": "already_running",
                "message": "دانلود دیتابیس کدال در حال اجراست — صبر کنید."}
    if reason == "scanning":
        # merge همزمان با اسکن زنده = دو نویسنده روی جدول‌های کدال؛ ممنوع
        return {"status": "already_running",
                "message": "اسکن کدال در حال اجراست — صبر کنید تا تمام شود."}
    if reason:
        return {"status": "error",
                "message": "شروع دانلود دیتابیس کدال ممکن نشد."}
    return {"status": "success",
            "message": "دانلود دیتابیس کدال از گیت‌هاب آغاز شد.",
            "url": CODAL_DB_URL}


@router.get("/api/sync/codal/db-status")
def sync_codal_db_status():
    """وضعیت زندهٔ دانلود/ادغام + متایِ آخرین snapshot + تازگیِ دادهٔ محلی."""
    st = _safe_read_json(CODAL_DB_STATUS_PATH) or {}
    with _dbdl_lock:
        running = _dbdl_running
    return {"status": "success",
            "db": {"running": running,
                   "stage": st.get("stage", "idle"),
                   "percent": st.get("percent", 0.0),
                   "detail": st.get("detail", ""),
                   "error": st.get("error", ""),
                   "ts": st.get("ts", ""),
                   "meta": read_meta_cache(),
                   "freshness": _freshness()}}


@router.get("/api/sync/status")
def get_sync_status():
    """Live status for the Codal/Market sync progress overlay."""
    od = _safe_read_json(OD_STATUS_PATH) or {}
    st = _safe_read_json(STATUS_PATH) or {}
    ms = _safe_read_json(MARKET_STATUS_PATH) or {}   # کانال اختصاصی بازار
    # On-demand channel (sync_ondemand.json) wins ONLY while a manual sync is
    # actively running; once it ends in "done", fall back to the global channel
    # so background scans (discovery/codal) stay visible in the UI.
    # FIX: اگر فایل یک-روزه/قدیمی باشد (باقیماندهٔ اجرای قبلی بدون "done")،
    # od_active نباید true شود — با timestamp تصمیم میگیریم نه فقط stage.
    od_active = od.get("stage") not in (None, "done")
    if od_active and od.get("ts"):
        try:
            age = (datetime.datetime.now() - datetime.datetime.fromisoformat(od["ts"])).total_seconds()
            if age > 600:  # ۱۰ دقیقه — خیلی قدیمی؛ ignore
                od_active = False
        except Exception:
            od_active = False
    # بازار: اگر market_sync.json در ۱۰ دقیقهٔ اخیر تازه است (sync فعال)، گزارشش کن
    ms_active = False
    try:
        if ms.get("stage") not in (None, "done") and ms.get("ts"):
            age = (datetime.datetime.now() - datetime.datetime.fromisoformat(ms["ts"])).total_seconds()
            ms_active = age <= 600
    except Exception:
        ms_active = False
    if od_active:
        active = True
        merged = {
            "source": "od",
            "active": active,
            "symbol": od.get("symbol", ""),
            "stage": od.get("stage", "idle"),
            "detail": od.get("detail", ""),
            "phase": st.get("phase", ""),
            "total": st.get("total", 0),
            "current": st.get("current", 0),
            "percent": st.get("percent", 0.0),
            "elapsed": st.get("elapsed", 0.0),
            "ts": od.get("ts", ""),
        }
    else:
        # No active on-demand sync -> reflect the background/global channel
        # FIX: با timestamp تصمیم میگیریم — اگر پروسهٔ اسکن مرده و فایل
        # sync_status.json قدیمی (فریز > ~1 دقیقه) باشد، active=false نشان بده
        # وگرنه UI تا ابد «در حال بروزرسانی» را نشان میدهد.
        st_alive = False
        try:
            if st.get("stage") not in (None, "done", "idle") and st.get("phase") not in (None, "codal_stopped"):
                age = (datetime.datetime.now() - datetime.datetime.fromisoformat(st["ts"])).total_seconds()
                st_alive = age <= 60  # هر tick اسکن در <۱ دقیقه آپدیت میکند
        except Exception:
            st_alive = False
        active = st_alive
        merged = {
            "source": "global",
            "active": active,
            "symbol": st.get("symbol", ""),
            "stage": st.get("stage", "idle"),
            "detail": st.get("detail", ""),
            "phase": st.get("phase", ""),
            "total": st.get("total", 0),
            "current": st.get("current", 0),
            "percent": st.get("percent", 0.0),
            "elapsed": st.get("elapsed", 0.0),
            "ts": st.get("ts", ""),
        }
        # اگر بازار در حال sync است (market_sync.json تازه)، آن را ضمیمه کن
        if ms_active and not active:
            active = True
            merged.update({
                "source": "market",
                "symbol": ms.get("symbol", ""),
                "stage": ms.get("stage", "tsetmc"),
                "detail": ms.get("detail", ""),
                "phase": ms.get("phase", ""),
                "total": ms.get("total", 0),
                "current": ms.get("current", 0),
                "percent": ms.get("percent", 0.0),
                "elapsed": ms.get("elapsed", 0.0),
                "ts": ms.get("ts", ""),
            })
    merged["ban_until"] = st.get("ban_until", "")
    return {"status": "success", "sync": merged}

@router.get("/api/sync/diagnose")
def diagnose_sync():
    """تشخیص باگ: آیا codal_fetcher واقعاً اجرا میشود؟ آیا sync_status.json
    فریز شده؟ وضعیت ADB؟ — UI این را برای نمایش هشدار استفاده میکند."""
    import time as _t
    info = {"codal_process_running": bool(_count_procs("codal_fetcher")),
            "app_processes": _count_procs("app.py"),
            "adb_found": bool(codal_fetcher._find_adb()),
            "adb_device": False, "adb_enabled": codal_fetcher._adb_enabled()}
    # چک دستگاه ADB
    try:
        adb = codal_fetcher._find_adb()
        if adb:
            import subprocess
            r = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=8)
            info["adb_device"] = any(ln.split("\t")[-1].strip() == "device"
                                     for ln in (r.stdout or "").splitlines())
    except Exception:
        pass
    # سن sync_status.json
    try:
        mtime = os.path.getmtime(STATUS_PATH)
        age = _t.time() - mtime
        info["status_file_age_sec"] = round(age, 1)
        info["status_frozen"] = age > 60 and bool(_count_procs("codal_fetcher"))
    except Exception:
        info["status_file_age_sec"] = -1
        info["status_frozen"] = False
    # وضعیت تترینگ: آیا adapter ویندوز IP واقعی از تلفن گرفته؟
    info["adb_tether_up"] = bool(codal_fetcher._detect_tether_ip())
    # مرحله فعلی
    st = _safe_read_json(STATUS_PATH) or {}
    info["phase"] = st.get("phase", "")
    info["detail"] = st.get("detail", "")
    info["symbol"] = st.get("symbol", "")
    info["ts"] = st.get("ts", "")
    return {"status": "success", "diag": info}

def _write_control(cmd):
    """Write the user's pause/resume/stop intent for codal_fetcher.py to poll."""
    try:
        tmp = CONTROL_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"cmd": cmd,
                       "ts": datetime.datetime.now().isoformat(timespec="seconds")},
                      f, ensure_ascii=False)
        os.replace(tmp, CONTROL_PATH)
    except Exception:
        pass

def _codal_running():
    """True when at least one codal_fetcher python process is alive."""
    return _count_procs("codal_fetcher")

def _launch_codal_scan():
    """Launch run_discovery.sh through pinned Git Bash (WSL bash cannot cd to C:/).
    On POSIX (Linux/macOS) falls back to the system bash on PATH."""
    try:
        bash = None
        for p in ("C:/Program Files/Git/usr/bin/bash.exe",
                  "C:/Program Files/Git/bin/bash.exe",
                  "C:/Program Files (x86)/Git/usr/bin/bash.exe"):
            if os.path.isfile(p):
                bash = p
                break
        if not bash:
            import shutil
            bash = shutil.which("bash")
        if not bash:
            return False
        proj = APP_DIR
        # logs باید در WORK_DIR نوشته‌شونده باشند (APP_DIR در نصب Program Files
        # فقط‌خواندنی است)؛ cwd پروسه همچنان proj است تا run_discovery.sh پیدا شود.
        logs_dir = os.path.join(WORK_DIR, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        with open(os.path.join(logs_dir, "relauncher.log"), "a", encoding="utf-8") as lf:
            lf.write("[app] %s - resume: launching discovery scan\n"
                     % datetime.datetime.now().isoformat(timespec="seconds"))
        out = open(os.path.join(logs_dir, "relauncher.log"), "ab", buffering=0)
        subprocess.Popen([bash, "run_discovery.sh"], cwd=proj,
                         stdin=subprocess.DEVNULL, stdout=out,
                         stderr=subprocess.STDOUT,
                         creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                         | getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return True
    except Exception:
        return False

def _kill_codal_fetchers():
    """Force-stop every codal_fetcher process — کراس-پلتفرم."""
    _kill_procs("codal_fetcher")

def _mark_codal_stopped():
    """Write the stopped phase into sync_status.json so the UI shows
    ⏹️ کدال: متوقفشده and active=false even for a force-killed scan."""
    try:
        st = _safe_read_json(STATUS_PATH) or {}
        st["phase"] = "codal_stopped"
        st["detail"] = "اسکن توسط کاربر متوقف شد"
        st["ts"] = datetime.datetime.now().isoformat(timespec="seconds")
        tmp = STATUS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False)
        os.replace(tmp, STATUS_PATH)
    except Exception:
        pass

@router.post("/api/codal/control")
async def codal_control(request: Request):
    """Pause / resume / stop the Codal discovery scan from the dashboard."""
    try:
        body = await request.json()
    except Exception:
        return {"status": "error", "message": "invalid JSON body"}
    cmd = str((body or {}).get("cmd", "")).strip().lower()
    if cmd not in ("pause", "resume", "stop"):
        return {"status": "error", "message": "unknown cmd: %s" % cmd}
    _write_control(cmd)
    if cmd == "stop":
        _kill_codal_fetchers()
        _mark_codal_stopped()
    elif cmd == "resume" and not _codal_running():
        _launch_codal_scan()
    return {"status": "success", "cmd": cmd, "running": _codal_running()}
