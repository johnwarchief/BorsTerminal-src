"""Spawns test_tsetmc to refresh market.db and reports whether it is alive.

Split verbatim out of app.py (v9.8.1 modularisation).
Every statement is byte-for-byte identical to app.py; only the route
decorators changed from @app.<verb> to @router.<verb>.
Audit map of source line spans: MIGRATED_LINES.txt
"""
from .market import warm_market_cache
from fastapi import APIRouter
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
            capture_output=True, text=True, timeout=15)
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

def _sync_market_on_start():
    """بروزرسانی زنده تابلو هنگام هر اجرای برنامه (هوک استارت).
    dedup: اگر سینک بازار از قبل در حال اجراست صبر کن — اجرای درون‌پروسه‌ای (EXE-safe)."""
    if _market_sync_alive():
        print("[startup] market sync already running — skip")
        return
    try:
        threading.Thread(target=_run_market_sync, daemon=True).start()
        print("[startup] market sync thread spawned")
    except Exception as e:
        print(f"[startup] market sync failed to start: {e}")

_MARKET_SYNC_LOCK = threading.Lock()
