"""Spawns test_tsetmc to refresh market.db and reports whether it is alive.

Split verbatim out of app.py (v9.8.1 modularisation).
Every statement is byte-for-byte identical to app.py; only the route
decorators changed from @app.<verb> to @router.<verb>.
Audit map of source line spans: MIGRATED_LINES.txt
"""
from .market import warm_market_cache
from fastapi import APIRouter
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
    except Exception as e:
        print(f"[market-sync] FAILED: {e}")
    finally:
        _MARKET_SYNC_LOCK.release()

def _market_sync_alive() -> bool:
    """True اگر همگام‌سازی بازار در حال اجراست.

    منبعِ یکتا خودِ `_MARKET_SYNC_LOCK` است. تا v1.0.65 اینجا اول یک
    `Get-CimInstance Win32_Process` با PowerShell اجرا می‌شد تا پروسهٔ جدای
    `test_tsetmc` را پیدا کند — ولی همان بالا در `_run_market_sync` نوشته
    شده که سینک دیگر پروسهٔ جدا نیست و درونِ همین فرآیند (thread + قفل)
    می‌دود، چون `Popen([sys.executable, ...])` در EXE خودِ EXE را دوباره
    بالا می‌آورد. پس آن پروسه هیچ‌وقت وجود ندارد و آن فراخوان فقط
    ۰٫۵ تا ۳ ثانیه به هر استارتِ ویندوزی اضافه می‌کرد (CIM روی Win32_Process
    کند است) تا صفر برگرداند.
    """
    if _MARKET_SYNC_LOCK.acquire(blocking=False):
        _MARKET_SYNC_LOCK.release()
        return False
    return True

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
