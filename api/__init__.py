"""api -- router modules split verbatim out of app.py.

app.py builds the FastAPI application, mounts /static, installs the
no-cache middleware and include_router()s every module below in the same
order the routes originally appeared in app.py.
"""
from fastapi import APIRouter


def api_router() -> APIRouter:
    """Aggregate every module router into one APIRouter."""
    from . import (market, chart, selection, watchlist, fundamental, market_status, screener, funnel, _sync_market, _export, _sync_codal, adb, notify, notifications, update, _pipeline, engine, market_index, diagnostics, structure3, execution)
    import codal_fetcher

    agg = APIRouter()
    mods = [market, chart, selection, watchlist, fundamental, market_status, screener, funnel,
            _sync_market, _export, _sync_codal, adb, notify, notifications, update, _pipeline, engine,
            market_index, diagnostics, structure3, execution]
    # دروازۀ اجرای سرخطی در *همهٔ* بیلدها ثبت می‌شود، برخلافِ adb. دلیلِ اینِ
    # تفاوتِ رفتار درِ خودِ دو ماژول است: adb کنترلِ واقعیِ دستگاهِ کاربر است
    # (خاموش‌کردنِ Wi-Fi او) وِ درِ EXE هیچ مصرف‌کننده‌ای ندارد؛ اما
    # /api/execution/* رابطِ کاربر ازِ پیش او را صدا می‌زند
    # (`features/portfolio/lib/orderClient.ts`). بی‌ثبت‌کردن، همانِ درِ پنلِ
    # سبد همیشه 404 (یا بدتر: ۲۰۰+HTMLِ fallback) است — سنجشِ ۱۴۰۵-۰۷-۲۴ رویِ
    # همینِ شاخه دقیقاً همین را نشان داد: status/session/bot هر سه ۲۰۰ باِ
    # `text/html` برمی‌گرداندند، یعنی «هست» ولیِ هیچِ قراردادی پشتش نیست.
    # پیش‌فرضِ همانِ در: adapter=mock وِ dry-run قفل. آداپتورِ واقعیِ EasyTrader
    # (`execution_easytrader.py`) ازِ مأموریتِ ۱۴۰۵-۰۷-۲۴ درِ کد هست، ولیِ بیِ دو
    # متغیرِ محیطیِ صریح (BORS_EXECUTION_ADAPTER وِ BORS_EXECUTION_LIVE) وِ بیِ
    # نشستِ مالک هیچِ درخواستی بهِ بیرون نمی‌فرستد. قفلش را کامنت نمی‌خواند:
    # `dev/easytrader_adapter_v1113.py` وِ بندِ ۳ `dev/execution_ledger_v1108.py`.
    # /api/adb/* کنترل ADB است (خاموش‌کردن Wi-Fi کاربر، حالت پرواز گوشیِ او) —
    # مخصوصِ ماشینِ توسعه‌دهنده. در EXE ثبت نمی‌شود تا هیچ درِ ورودیِ محلی
    # روی پورت ۸۰۰۱ باقی نماند.
    if not codal_fetcher.ADB_CONTROL_AVAILABLE:
        mods = [m for m in mods if m is not adb]
    for mod in mods:
        agg.include_router(mod.router)
    return agg
