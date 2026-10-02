"""app.py -- BorsAgent Modern Terminal (FastAPI application).

v9.8.1: the route handlers and their helpers were split verbatim into
api/_*.py / api/<domain>.py. This file now only:
  * builds the FastAPI app + GZip + no-cache middleware
  * mounts /static (فقط calendar -- داده رویدادهای نماد)
  * serves the React SPA (frontend/dist) at "/" with a catch-all fallback
    (فاز 7: UI قدیمی static بازنشسته شد؛ archive/legacy_static)
  * keeps @app.on_event("startup") so the market board is refreshed exactly
    once per process (a handler on a sub-router would fire once per
    include_router level -- FastAPI merges every nested router lifespan)
  * include_router()s api.api_router() BEFORE the SPA catch-all so /api/* wins
  * re-exports load_fts_config for dev/codal_fts_updater.py

Audit map of the verbatim line spans: MIGRATED_LINES.txt
"""
import importlib.util
import os
import subprocess
import sys
import threading

# کدپیجِ خروجیِ ویندوز: روی یک ویندوزِ انگلیسی، stdout پیش‌فرض cp1252 است و
# هیچ printِ فارسی‌ای قابلِ انکد نیست. اولین printِ فارسی کلِ درخواست را
# با UnicodeEncodeError می‌کشد (دیده‌شده: api/screener.py:227 → /api/screener
# 500). bors_entry همین کار را برایِ EXE می‌کند؛ اینجا برایِ اجرایِ dev.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError, OSError):
    pass

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from urllib.parse import urlsplit
from fastapi.middleware.gzip import GZipMiddleware

from bors_config import (APP_DIR, DB_PATH, FTS_CONFIG_PATH, MARKET_STATUS_PATH,
                         STATUS_PATH)
from bors_flags import ORJSONResponse, _ORJ
from api.market import load_fts_config            # re-export (dev/ consumer)
from api._sync_market import _sync_market_on_start
from api import api_router

# اگر orjson نصب نباشد ORJSONResponse=None است؛ هیچ‌وقت None را به
# default_response_class نده — وگرنه هر مسیر با «TypeError: NoneType is not
# callable» → 500 می‌شود. در نبودِ orjson به JSONResponse استاندارد برگرد.
app = FastAPI(title="BorsAgent Modern Terminal",
              default_response_class=(ORJSONResponse or JSONResponse))
# GZip: responses >1KB are compressed -- /api/market 4.2MB -> ~450KB
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)


# میزبان‌هایی که «همین ماشین» شمرده می‌شوند. '::1' در برخی مسیرها با کروشه
# می‌آید، پس کروشه‌ها قبلِ مقایسه کنارجدا می‌شوند.
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


@app.middleware("http")
async def loopback_guard(request, call_next):
    """دروازهٔ حلقهٔ محروی روی /api/* — لاگینِ محلی مرزِ امنیتی نیست.

    صفحهٔ ورود فقط UI است (authStore در مرورگر) و هیچ مسیری در API هیچ
    کوکی/توکنی نمی‌خواهد؛ پس هر وب‌پیجی که کاربر باز می‌کند می‌تواند با یک
    POST ساده به http://127.0.0.1:8001/api/... درخواست بفرستد (CORS جلوی
    *خواندن* پاسخ را می‌گیرد، نه *انجام* اثر جانبیِ آن). آن مسیرها اثر
    جانبیِ واقعی دارند: بازنویسی market.db، رانِ نصاب، و انداختنِ IP با ADB.
    راه‌حلِ کوچکِ همان‌جا: هر درخواستی که میزبان یا Originش حلقهٔ محلی نیست
    رد شود. «Origin: null» هم رد می‌شود: کروم/ادج آن را برای سندِ file://
    می‌فرستند، یعنی یک HTMLِ دانلودشدهٔ محلی هم می‌توانست به API درخواست بزند.
    درخواستِ بیِ Origin (کالِ درونِ فرآیند، curl، خودِ اپ) رد نمی‌شود — مرزِ
    ما «مرورگرِ بیرونی» است، نه «هر کلاینتی».
    """
    if request.url.path.startswith("/api/"):
        host = (request.headers.get("host") or "").split(":")[0].strip("[]")
        if host not in _LOOPBACK_HOSTS:
            return JSONResponse({"status": "error",
                                 "message": "دسترسی از میزبانِ محلی مجاز است"},
                                status_code=403)
        origin = (request.headers.get("origin") or "").strip()
        if origin:
            oh = (urlsplit(origin).hostname or "").lower()
            if not oh or oh not in _LOOPBACK_HOSTS:
                # oh خالی = «null» یا مقدارِ غیرآدرسی → بیرونی شمرده می‌شود
                return JSONResponse({"status": "error",
                                     "message": "Originِ غیرمحلی رد شد"},
                                    status_code=403)
    return await call_next(request)


@app.middleware("http")
async def no_cache_middleware(request, call_next):
    response = await call_next(request)
    path = request.url.path
    # performance: باندل‌های هش‌دارِ فرانت (assets/vendor) تغییرناپذیرند؛ no-store
    # روی آن‌ها یعنی هر بار دانلودِ دوبارهٔ ~۵۰۰KB JS و مصرف CPU/شبکه. برای این
    # مسیرها کش طولانی می‌گذاریم؛ برای API و index.html همان no-store می‌ماند.
    if path.startswith("/assets/") or path.startswith("/vendor/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        if "Pragma" in response.headers:
            del response.headers["Pragma"]
        return response
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response


# Mount Static UI
def _static_dir():
    """در حالت EXE: static داخل _MEIPASS است؛ وگرنه کنار اسکریپت"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        p = os.path.join(sys._MEIPASS, "static")
        if os.path.isdir(p):
            return p
    return "static"


def _frontend_dist():
    """مسیر خروجی build فرانت React (frontend/dist)؛ در EXE داخل _MEIPASS."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        p = os.path.join(sys._MEIPASS, "frontend", "dist")
        if os.path.isdir(p):
            return p
    return os.path.join(APP_DIR, "frontend", "dist")


app.mount("/static", StaticFiles(directory=_static_dir()), name="static")

# ─── سرو SPA React از ریشه (فاز 7) ─────────────────────────────────────
# ساختار: /assets و /vendor مستقیم از dist؛ مسیرهای گمشده (هش‌روتر) به
# index.html برمی‌گردند تا رفرش مسیرهای کلاینت 404 ندهد؛ /api/* چون قبل
# از catch-all ثبت می‌شود اولویت دارد.
_FRONTEND_DIST = _frontend_dist()


# پچِ دلتا هیچ فایلی را حذف نمی‌کند و Vite هر build نامِ chunkها را عوض می‌کند،
# پس آپدیتِ درجا انباشته می‌شود: رویِ نصبیِ ۱٫۰٫۶۸ ~۸۳۰ فایلِ js/css مرده شمرده
# شد. یک‌بار به‌ازایِ هر نسخه پاک می‌شود؛ شکستِ آن هرگز نبایدِ برنامه را بیندازد.
if os.path.isdir(_FRONTEND_DIST):
    try:
        from bors_config import APP_VERSION as _AV, prune_stale_frontend_assets
        prune_stale_frontend_assets(_FRONTEND_DIST, _AV)
    except Exception as _exc:                                  # noqa: BLE001
        print("[warn] stale-asset prune skipped:", _exc)

def _get_index_html():
    if not os.path.isdir(_FRONTEND_DIST):
        return None
    idx = os.path.join(_FRONTEND_DIST, "index.html")
    return idx if os.path.isfile(idx) else None

_assets_dir = os.path.join(_FRONTEND_DIST, "assets")
app.mount("/assets", StaticFiles(directory=_assets_dir, check_dir=False), name="frontend-assets")
_vendor_dir = os.path.join(_FRONTEND_DIST, "vendor")
app.mount("/vendor", StaticFiles(directory=_vendor_dir, check_dir=False), name="frontend-vendor")

def _spa_index():
    """index.html یا 404 رسا اگر dist ساخته نشده."""
    idx = _get_index_html()
    if not idx:
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "frontend dist ساخته نشده؛ در frontend دستور npm run build را اجرا کن"}, status_code=200)
    return FileResponse(idx)


@app.on_event("startup")
def _startup_sync_market():
    """هوک استارت FastAPI: اجرای uvicorn (باش با bat) → تابلو در هر اجرا آپدیت می‌شود.
    (قبلاً فقط در __main__ بود و start_dashboard.py هرگز فراخوانی‌اش نمی‌کرد.)"""
    # ۱) مهاجرتِ افزودنیِ اسکیما — باید قبل از هر کوئریِ fts_engine/screener
    # اجرا شود. market.db.lzmaیِ فریزشده ستون‌های FTS v2.2 را ندارد و
    # ensure_market_db() فقط وجودِ جداول را بررسی می‌کند، پس بدون این مرحله
    # موتور با «no such column» (یا اسکرینر ۵۰۰) پاسخ می‌دهد. migrate_schema
    # کاملاً یدم‌پذیر است و در صورت وجود ستون کاری نمی‌کند.
    # import محلی: bors_config یک leaf module است و codal_fetcher از آن import
    # می‌کند، پس نمی‌توانیم این کار را در ensure_market_db() انجام دهیم.
    try:
        import codal_fetcher as _cf
        import sqlite3 as _sq
        _db = _cf.DB_PATH
        if _db and os.path.exists(_db):
            _c = _sq.connect(_db, timeout=60)
            try:
                _cf.create_schema(_c)
                _cf.migrate_schema(_c)
            finally:
                _c.close()
            print("[startup] codal schema migrated (additive, idempotent)")
    except Exception as e:
        # شکستِ مهاجرت نباید سرور را پایین بیاورد؛ مسیرهای fetch خودشان دوباره
        # migrate_schema را صدا می‌زنند.
        print(f"[startup] codal schema migrate failed (non-fatal): {e}")

    try:
        threading.Thread(target=_sync_market_on_start, daemon=True).start()
        print("[startup] market sync thread spawned")
    except Exception as e:
        print(f"[startup] market sync thread failed: {e}")

    # گرم‌کردنِ بلادرنگ کشِ اسکنر در پس‌زمینه تا اولین بارگذاریِ تبِ بنیادی معطل نماند.
    def _warm_screener():
        try:
            import time as _t
            _t.sleep(1)          # شروع سریع در ترد پس‌زمینه
            from api.screener import warm_screener_cache
            warm_screener_cache()
        except Exception as _e:
            print(f"[startup] screener warm failed: {_e}")
    try:
        threading.Thread(target=_warm_screener, daemon=True).start()
        print("[startup] screener warm thread spawned")
    except Exception as _e:
        print(f"[startup] screener warm thread failed: {_e}")

    # ── تازۀ‌سازیِ خودکارِ تابلو در ساعتِ بازار ──────────────────────────
    # اندازه‌گیری ۱۴۰۵-۰۷-۰۴: برنامه ۰۷:۲۱ (پیش از بازگشایی) اجرا شده بود و تا
    # ۱۰:۲۱ — وسطِ نشست — هیچ سینکِ دیگری نزد. TSETMC همان لحظه ۵۱ میلیارد سهم
    # معامله‌شده داشت، ولی جدولِ ما ردیف‌هایِ صفرِ پیش‌ازگشایی را نشان می‌داد و
    # نبض بازار «نامساعد» می‌گفت. تنها راهِ سینک، هوکِ استارت و دکمه‌ای بود که
    # هیچ جایِ UI فراخوانی‌اش نمی‌شد. این حلقه در پنجرۀِ رسمیِ بازار هر ۹۰ ثانیه
    # یک سینک می‌زند؛ بیرونِ آن پنجره هیچ درخواستی نمی‌فرستد.
    def _market_in_session(now_dt=None) -> bool:
        import datetime as _dt
        # پنجره یک جا تعریف می‌شود: mstat_engine.in_trading_session (۰۹:۰۰–۱۳:۰۰
        # و تعطیلی پنجشنبه/جمعه). نسخهٔ دومی از همین شرط اینجا نپزید.
        from mstat_engine import in_trading_session
        n = now_dt or _dt.datetime.now()
        return in_trading_session(n.hour * 10000 + n.minute * 100 + n.second, n)

    def _board_refresh_loop():
        import time as _t
        from api._sync_market import _run_market_sync
        while True:
            try:
                if _market_in_session():
                    _run_market_sync()     # قفلِ خودش: اگر سینکی در کار است، رد می‌کند
            except Exception as _e:
                print(f"[startup] board refresh loop: {_e}")
            _t.sleep(90)
    try:
        threading.Thread(target=_board_refresh_loop, daemon=True).start()
        print("[startup] board refresh loop spawned (90s, session-windowed)")
    except Exception as _e:
        print(f"[startup] board refresh loop failed: {_e}")

    # ── تیکِ زندۀ تابلو (#120 ریشۀ باگِ «تازه‌نشدنِ اعداد») ────────────────
    # اندازه‌گیریِ زنده: خودِ API تابلوی TSETMC هر ۱۵ ثانیه صدها نماد را عوض
    # می‌کند، ولی سینکِ کاملِ ۹۰ ثانیه‌ای تنها منبعِ نوشتن بود — تا بین دو
    # سینک هیچ عددی در بانک عوض نمی‌شد و پولینگِ پنج‌ثانیه‌ایِ فرانت درست
    # همان ۳۰۴ می‌گرفت. این حلقه هر ۵ ثانیه یکِ درخواستِ تابلو می‌زند، همان
    # ستون‌هایِ ثانیه‌ای را می‌نویسد و بازسازیِ کشِ /api/market را محرک
    # می‌کند؛ دربِ ۱۲:۳۰ داخلِ خودِ tick_live است (صف‌هایِ بستۀ بازار
    # محفوظ می‌مانند). نخِ جدا: اگر TSETMC خنک کند (۴۲۹)، حلقۀ سینکِ
    # ۹۰ ثانیه‌ای نمی‌خوابد.
    def _board_tick_loop():
        import time as _t
        import market_state as _MS
        from api.market import _kick_market_rebuild
        # محرکِ rebuild «تغییرِ داده» است، نه «پایانِ یک سیکل». تا پیش از این
        # هر تیکِ پنج‌ثانیه‌ای کش را بازسازی می‌خواست — یعنی درِ سکوتِ بازار
        # هم ۲۵۰ میلی‌ثانیه CPU و یک بدنهٔ ۷ مگابایتی که بایتی از آن فرق
        # نداشت. revision فقط درِ market_state بالا می‌رود، آن‌هم پس از
        # commitِ موفق، پس «بازسازی‌شده» همیشه یعنی «چیزی رویِ دیسک عوض شده».
        last_rev = _MS.revision()
        while True:
            try:
                # درِ ساعت داخلِ خودِ tick_live: تا ۱۲:۳۰ نوشتنِ کامل، ۱۲:۳۰ تا
                # ۱۵:۳۰ فقط ستون‌هایِ عددی (تابلوی TSETMC پس از بستن هم می‌چرخد).
                import test_tsetmc as _ts
                _ts.tick_live()
                rev = _MS.revision()
                if rev != last_rev:
                    last_rev = rev
                    _kick_market_rebuild()
            except Exception as _e:
                print(f"[startup] board tick loop: {_e}")
            _t.sleep(5)
    try:
        threading.Thread(target=_board_tick_loop, daemon=True).start()
        print("[startup] board tick loop spawned (5s, session-windowed)")
    except Exception as _e:
        print(f"[startup] board tick loop failed: {_e}")

    # ── اسنپ‌شاتِ دوره‌ایِ نبض بازار ─────────────────────────────────────
    # مstat_snap قبلاً فقط پراکنده پر می‌شد (چند نقطه) و به‌همین‌دلیل «روند ۳-۴
    # روزه» و نمودار درون‌روز «بدون داده» بود. این حلقه هر ۵ دقیقه یک نقطه
    # می‌سازد؛ خودِ save_mstat_snapshot خارجِ ساعت بازار چیزی نمی‌نویسد.
    def _pulse_snapshot_loop():
        import time as _t
        while True:
            try:
                # رأیِ مالک (کار #73): «همهٔ pollingها فقط درِ نشستِ معاملاتی فعال
                # باشند». save_mstat_snapshot خودش بیرونِ پنجره چیزی نمی‌نویسد،
                # ولی این حلقه باز هر ۳۰۰ ثانیه بیدار می‌شد، یکِ اتصالِ SQLite و
                # یکِ ensure_schema (کوئریِ PRAGMA) می‌ساخت — یعنی شبِ پنجشنبه
                # هم برنامه بیدار است. دربِ ساعت حالا درِ خودِ حلقه است؛ اگر
                # برنامه بیرونِ نشست بالا بیاید، اولین نقطه درِ ۰۸:۵۵ نوشته می‌شود.
                if _market_in_session():
                    import sqlite3 as _sq, mstat_engine as _ME
                    from bors_config import DB_PATH as _DB
                    # `close()` باید درِ finally باشد: هر raise داخلِ save_mstat_snapshot
                    # یکِ اتصال + هندلِ WAL را برایِ عمرِ کلِ برنامه باز می‌گذاشت
                    # (این حلقه هر ۳۰۰ ثانیه اجرا می‌شود).
                    _c = _sq.connect(_DB, timeout=30)
                    try:
                        _ME.save_mstat_snapshot(_c)
                    finally:
                        _c.close()
            except Exception as _e:
                print(f"[startup] pulse snapshot loop: {_e}")
            _t.sleep(300)
    try:
        threading.Thread(target=_pulse_snapshot_loop, daemon=True).start()
        print("[startup] pulse snapshot loop spawned (300s, session-windowed)")
    except Exception as _e:
        print(f"[startup] pulse snapshot loop failed: {_e}")

    # ── کندل از تابلو، یک بار درِ بوت (۱٫۰٫۶۲) ─────────────────────────────
    # حلقۀ سینک بیرونِ پنجرۀ ۰۹–۱۳ نمی‌دود، پس اگر برنامه پس از بستنِ بازار
    # بالا بیاید (یا شبکه درِ نشست نرسیده باشد) جدولِ کندل روی آخرینِ نشستِ
    # موفق می‌ماند. سنجشِ ۱۴۰۵-۰۷-۰۷ روی کپیِ بانکِ نصبی: کندل‌ها روی
    # ۲۰۲۶-۰۹-۲۱ و فقط ۱۰ نماد در هر روز، درحالی‌که تابلو ۲۴ نشستِ
    # معامله‌شده داشت. این دو تابع فقط از خودِ بانک می‌خوانند (بی‌شبکه،
    # بی‌۴۲۹، ۰٫۹ ثانیه برایِ جبرانِ کامل و ۰٫۲۸ برایِ حالتِ عادی) و
    # قابلِ تکرارند، پس درِ بوت هم اجرا می‌شوند. نخِ جدا: بوت را نبندد.
    def _candle_projection_at_boot():
        try:
            import sqlite3 as _sq
            import test_tsetmc as _T
            from bors_config import DB_PATH as _DB
            _c = _sq.connect(_DB, timeout=60)
            try:
                _T.sync_price_history_from_daily(_c)
                _T.normalize_price_history_geometry(_c)
            finally:
                _c.close()
            # این دو جدول پنجره‌هایِ نمایشِ تابلو را می‌سازند (میانگین حجم،
            # کفِ ۲۹ نشست، پلکانِ [ih]) و تیکِ زنده هرگز نمی‌نویسدشان؛ نخِ بوت
            # ممکن است *پس از* اولین ساختنِ تابلو تمام کند، پس خودمان خبر می‌دهیم
            # که قابِ ایستا سوخته است. بی‌این، سقفِ ۶۰ ثانیه در `api.market`
            # جبران می‌کرد — یعنی تا یک دقیقه عددِ دیروز زیرِ تاریخِ امروز.
            import market_state as _MS
            _MS.note_static_change()
        except Exception as _e:
            print(f"[startup] candle projection at boot: {_e}")
    try:
        threading.Thread(target=_candle_projection_at_boot, daemon=True).start()
        print("[startup] candle projection spawned (local-only, one pass)")
    except Exception as _e:
        print(f"[startup] candle projection failed: {_e}")


@app.get("/", include_in_schema=False)
def serve_home():
    """صفحه اصلی = SPA React (فاز 7)."""
    return _spa_index()


# نکته ترتیب: APIها باید قبل از catch-all ثبت شوند تا اولویت بگیرند.
app.include_router(api_router())


@app.get("/{full_path:path}", include_in_schema=False)
def spa_catch_all(full_path: str):
    """فایل موجود در dist سرو می‌شود؛ هر مسیر دیگر -> index.html (رفرش SPA سالم)."""
    idx = _get_index_html()
    if idx and full_path:
        candidate = os.path.normpath(os.path.join(_FRONTEND_DIST, full_path))
        base = os.path.abspath(_FRONTEND_DIST)
        if candidate.startswith(base) and os.path.isfile(candidate):
            return FileResponse(candidate)
    return _spa_index()


if __name__ == "__main__":
    # فقط وضعیت پیش‌نیازها را نشان بده (نه اسکن، نه دانلود) — خروجی/دانلود با دکمه‌های UI
    try:
        _need_check = (not os.path.exists(DB_PATH)
                       or os.path.getsize(DB_PATH) < 10_000_000
                       or any(importlib.util.find_spec(m) is None
                              for m in ("fastapi", "uvicorn", "pandas", "numpy", "requests")))
        if _need_check:
            _rc = subprocess.run([sys.executable, "bootstrap_first_run.py"],
                                 cwd=APP_DIR)
    except Exception:
        pass
    # تابلو: هر بار اجرا، تازه‌سازی بازار در ترد جدا (شروع بلافاصله، بدون مسدود کردن UI)
    try:
        threading.Thread(target=_sync_market_on_start, daemon=True).start()
    except Exception as e:
        print(f"[startup] market sync thread failed: {e}")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
