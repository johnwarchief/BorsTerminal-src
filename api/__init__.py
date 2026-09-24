"""api -- router modules split verbatim out of app.py.

app.py builds the FastAPI application, mounts /static, installs the
no-cache middleware and include_router()s every module below in the same
order the routes originally appeared in app.py.
"""
from fastapi import APIRouter


def api_router() -> APIRouter:
    """Aggregate every module router into one APIRouter."""
    from . import (market, chart, selection, watchlist, fundamental, market_status, screener, _sync_market, _export, _sync_codal, adb, notify, update, _pipeline, engine, market_index, diagnostics)
    import codal_fetcher

    agg = APIRouter()
    mods = [market, chart, selection, watchlist, fundamental, market_status, screener,
            _sync_market, _export, _sync_codal, adb, notify, update, _pipeline, engine,
            market_index, diagnostics]
    # /api/adb/* کنترل ADB است (خاموش‌کردن Wi-Fi کاربر، حالت پرواز گوشیِ او) —
    # مخصوصِ ماشینِ توسعه‌دهنده. در EXE ثبت نمی‌شود تا هیچ درِ ورودیِ محلی
    # روی پورت ۸۰۰۱ باقی نماند.
    if not codal_fetcher.ADB_CONTROL_AVAILABLE:
        mods = [m for m in mods if m is not adb]
    for mod in mods:
        agg.include_router(mod.router)
    return agg
