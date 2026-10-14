"""api -- router modules split verbatim out of app.py.

app.py builds the FastAPI application, mounts /static, installs the
no-cache middleware and include_router()s every module below in the same
order the routes originally appeared in app.py.
"""
from fastapi import APIRouter


def api_router() -> APIRouter:
    """Aggregate every module router into one APIRouter."""
    from . import (market, chart, selection, watchlist, fundamental, market_status, screener, funnel, _sync_market, _export, _sync_codal, adb, notify, notifications, update, _pipeline, engine, market_index, diagnostics, execution)
    import codal_fetcher

    agg = APIRouter()
    mods = [market, chart, selection, watchlist, fundamental, market_status, screener, funnel,
            _sync_market, _export, _sync_codal, adb, notify, notifications, update, _pipeline, engine,
            market_index, diagnostics, execution]
    # دروازۀ اجرای سفارش در *همهٔ* بیلدها ثبت می‌شود، برخلافِ adb. دلیلِ این
    # تفاوتِ رفتار درِ خودِ دو ماژول است: adb کنترلِ واقعیِ دستگاهِ کاربر است
    # (خاموش‌کردنِ Wi-Fi او) و درِ EXE هیچ مصرف‌کننده‌ای ندارد؛ اما
    # /api/execution/* تنها adapterِ mock را پشتِ `DRY_RUN = True` ثابت
    # (api/execution.py:39) می‌بیند و رابطِ کاربر از پیش او را صدا می‌زند
    # (features/portfolio/lib/orderClient.ts:147). بی‌ثبت‌کردن، همان درِ
    # panelِ سبد همیشه 404 است — که درِ نسخهٔ ۱٫۰٫۸۷ و پیش‌تر همین‌طور بود.
    # /api/adb/* کنترل ADB است (خاموش‌کردن Wi-Fi کاربر، حالت پرواز گوشیِ او) —
    # مخصوصِ ماشینِ توسعه‌دهنده. در EXE ثبت نمی‌شود تا هیچ درِ ورودیِ محلی
    # روی پورت ۸۰۰۱ باقی نماند.
    if not codal_fetcher.ADB_CONTROL_AVAILABLE:
        mods = [m for m in mods if m is not adb]
    for mod in mods:
        agg.include_router(mod.router)
    return agg
