"""Spawns test_tsetmc to refresh market.db and reports whether it is alive.

Split verbatim out of app.py (v9.8.1 modularisation).
Every statement is byte-for-byte identical to app.py; only the route
decorators changed from @app.<verb> to @router.<verb>.
Audit map of source line spans: MIGRATED_LINES.txt
"""
from .market import warm_market_cache
from fastapi import APIRouter
import os
import subprocess
import test_tsetmc as _tsetmc_mod
import threading


router = APIRouter()


def _run_market_sync():
    """اجرای همگام‌سازی بازار درون همین پروسه (thread).
    نکته: Popen([sys.executable, ...]) در EXE شکست می‌خورد (EXE دوباره اجرا می‌شود)
    — بنابراین main() را مستقیم import و در thread صدا می‌زنیم."""
    if not _MARKET_SYNC_LOCK.acquire(blocking=False):
        print("[market-sync] already running — skip")
        return
    try:
        print("[market-sync] thread started")
        _tsetmc_mod.main()
        print("[market-sync] done")
        # داده تازه شد؛ کشِ پیشین بی‌ارزش است. «خالی‌کردن» تنها کافی نبود:
        # اندازه‌گیری شد که نخستین درخواستِ پس از هر سینک ۱٫۴ ثانیه پایِ
        # ساختنِ تابلو می‌ایستاد. اینجا همان ساختن در همین نخ انجام می‌شود،
        # پس کاربر هرگز آن تأخیر را نمی‌بیند. (خودِ warm_market_cache اگر
        # ساختن شکست کش را خالی می‌کند.)
        warm_market_cache()
        # کشِ اسکرینر از همان `market_watch` (market_cap/قیمت) ساخته می‌شود و
        # TTL‑ش ۱۲ ساعت + کشِ دیسک است — یعنی تا پیش از این پس از هر سینک،
        # ستون‌هایِ وابسته‌به‌قیمتِ تبِ بنیادی تا ۱۲ ساعت کهنه می‌ماندند در
        # حالی که `/api/fundamental` زنده جواب می‌داد (همان شکلِ «عددِ اسکرینر
        # با عددِ کارت می‌جنگد» که برایِ #66 ثبت شد). بی‌`drop_materialized`،
        # چون درِ بیلدِ فریزشده هیچ نویسدۀ دیگری برایِ fts_results نیست.
        from .screener import invalidate_screener_cache, warm_screener_cache
        invalidate_screener_cache(drop_materialized=False)
        warm_screener_cache()
    except Exception as e:
        print(f"[market-sync] FAILED: {e}")
    finally:
        _MARKET_SYNC_LOCK.release()

def _market_sync_alive():
    """True اگر همگام‌سازی بازار در حال اجراست (thread زنده یا پروسهٔ قدیمی)."""
    # پروسهٔ تست (برای نسخهٔ قدیمی/کد — اگر بررسی powershell در دسترس بود)
    try:
        out = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'test_tsetmc' -and $_.Name -ne 'pythonw.exe' }).Count"],
            capture_output=True, text=True, timeout=15,
            # درِ بیلدِ console=False این صدا زدنِ powershell یک کنسولِ سیاهِ
            # چشمک‌زن باز می‌کرد (شکایتِ مالک 1405-07-20) و تا ۱۵ ثانیه هم
            # مسیرِ بوت را بلوکه می‌کرد.
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        n = int(out.stdout.strip()) if out.returncode == 0 and out.stdout.strip().isdigit() else 0
        if n:
            return True
    except Exception:
        pass
    return not _MARKET_SYNC_LOCK.acquire(blocking=False) or (_MARKET_SYNC_LOCK.release() or False)

@router.post("/api/sync/market")
def sync_market():
    threading.Thread(target=_run_market_sync, daemon=True).start()
    return {"status": "success", "message": "Market sync started."}

def _board_session_day():
    """آخرینِ روزِ نشستِ موجودِ در بانک (Gregorian YYYYMMDD) یا None."""
    try:
        import sqlite3

        from bors_config import DB_PATH
        if not os.path.exists(DB_PATH):
            return None
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=5)
        try:
            r = conn.execute("SELECT MAX(d_even) FROM market_watch").fetchone()
        finally:
            conn.close()
        return int(r[0]) if r and r[0] else None
    except Exception:
        return None


def _sync_market_on_start():
    """بروزرسانی زنده تابلو هنگام هر اجرای برنامه (هوک استارت).
    dedup: اگر سینک بازار از قبل در حال اجراست صبر کن — اجرای درون‌پروسه‌ای (EXE-safe).

    گیتِ نشست (رأیِ مالک 1405-07-20: «هر بار اجرا همهٔ تب‌ها طول می‌کشد رویِ
    «در حال دریافت»»): پیش از این هر بوت یک اسکرپِ کاملِ TSETMC راه می‌انداخت،
    حتی سه‌ساعتِ پس از بستنِ بازار. آن اسکرپ بانک را قفلِ نوشتن می‌گذارد و کشِ
    تابلو/اسکرینر را بازمی‌سازد، پس نخستین درخواستِ هر تب پشتِ همان کار می‌ماند.
    بیرونِ پنجرۀ رسمی، اگر بانک *همینِ روزِ نشست* را دارد، داده چیزی عوض
    نمی‌کند — پس سرو می‌شود و شبکه صدا زده نمی‌شود. بی‌داده‌ی امروز یا درِ
    نشستِ باز، رفتارِ پیشین دست‌نخورده است.

    `_SYNC_DECIDED` + `_SYNC_WILL_RUN` برایِ زمان‌بندیِ گرم‌کردنِ اسکرینر است،
    نه برایِ داوریِ داده: `_run_market_sync` درِ پایانِ خودش اسکرینر را دوباره
    گرم می‌کند، پس اگر سینک در کار باشد، گرم‌کردنِ هم‌زمانِ بوت دور ریخته
    می‌شود (سنجش ۱۴۰۵-۰۷-۲۳: دوِ بیلدِ کاملِ اسکرینر درِ یکِ بوت، و اولین
    درخواستِ تب بنیادی ۹۹ ثانیه پشتِ بازسازیِ سنگین).
    """
    if _market_sync_alive():
        print("[startup] market sync already running — skip")
        _SYNC_WILL_RUN[0] = True          # نخِ دیگری در کار است؛ او گرم می‌کند
        _SYNC_DECIDED.set()
        return
    try:
        import datetime as _dt

        from mstat_engine import in_trading_session
        now = _dt.datetime.now()
        open_now = in_trading_session(now.hour * 10000 + now.minute * 100 + now.second, now)
        if not open_now:
            today = int(now.strftime("%Y%m%d"))
            have = _board_session_day()
            if have and have >= today:
                print(f"[startup] market closed and board is from {have} — "
                      "serving the stored session, no network sync")
                _SYNC_WILL_RUN[0] = False
                _SYNC_DECIDED.set()
                return
        threading.Thread(target=_run_market_sync, daemon=True).start()
        _SYNC_WILL_RUN[0] = True
        _SYNC_DECIDED.set()
        print("[startup] market sync thread spawned")
    except Exception as e:
        _SYNC_WILL_RUN[0] = False
        _SYNC_DECIDED.set()
        print(f"[startup] market sync failed to start: {e}")

_MARKET_SYNC_LOCK = threading.Lock()


# ---- زمان‌بندیِ گرم‌کردنِ اسکرینر درِ بوت (PERF-S6) --------------------
# `_run_market_sync` درِ پایانِ خودش `invalidate_screener_cache()` و
# `warm_screener_cache()` می‌زند. اگر hookِ بوت *هم‌زمان* اسکرینر را گرم کند،
# آن بیلد دور ریخته می‌شود و بیلدِ دوم شروع می‌شود — سنجشِ ۱۴۰۵-۰۷-۲۳ رویِ
# لپ‌تاپِ ۴هسته‌ای: دوِ بیلدِ کاملِ `bulk_scan` درِ یکِ بوت و ۹۹ ثانیه ماندنِ
# اولین درخواستِ `/api/screener` (تب بنیادی) پشتِ بازسازی. این دو نشانه فقط
# زمان‌بندی را می‌گویند، هیچ داوریِ داده‌ای را عوض نمی‌کنند.
_SYNC_DECIDED = threading.Event()
_SYNC_WILL_RUN = [False]


def mark_sync_not_scheduled() -> None:
    """وقتی حلقه‌هایِ شبکه آگاهانه خاموش‌اند: سینکی در کار نیست، گرم‌کردنِ
    اسکرینر نباید منتظرِ داوریِ آن بماند."""
    _SYNC_WILL_RUN[0] = False
    _SYNC_DECIDED.set()


def screener_warm_should_skip(wait_s: float = 25.0) -> bool:
    """True ⇒ سینکِ بوت در کار است و خودش اسکرینر را گرم می‌کند.

    بی‌صبر تا `wait_s` برایِ *داوریِ* سینک؛ اگر داوری نرسید (بررسیِ پروسهٔ
    بیرونی با PowerShell لنگ بزند) False می‌دهد تا گرم‌کردنِ بوت همان کارِ
    همیشگی را بکند — پس هیچ‌وقت «تب بنیادی بی‌کشِ گرم» از این مسیر نمی‌سازیم.
    """
    if not _SYNC_DECIDED.wait(wait_s):
        return False
    return bool(_SYNC_WILL_RUN[0])
