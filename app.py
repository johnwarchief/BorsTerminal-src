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

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
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


@app.middleware("http")
async def no_cache_middleware(request, call_next):
    response = await call_next(request)
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
_INDEX_HTML = os.path.join(_FRONTEND_DIST, "index.html") if os.path.isdir(_FRONTEND_DIST) else None

if _INDEX_HTML and os.path.isfile(_INDEX_HTML):
    _assets_dir = os.path.join(_FRONTEND_DIST, "assets")
    if os.path.isdir(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="frontend-assets")
    _vendor_dir = os.path.join(_FRONTEND_DIST, "vendor")
    if os.path.isdir(_vendor_dir):
        app.mount("/vendor", StaticFiles(directory=_vendor_dir), name="frontend-vendor")


def _spa_index():
    """index.html یا 404 رسا اگر dist ساخته نشده."""
    if not _INDEX_HTML or not os.path.isfile(_INDEX_HTML):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "frontend dist ساخته نشده؛ در frontend دستور npm run build را اجرا کن"}, status_code=404)
    return FileResponse(_INDEX_HTML)


@app.on_event("startup")
def _startup_sync_market():
    """هوک استارت FastAPI: اجرای uvicorn (باش با bat) → تابلو در هر اجرا آپدیت می‌شود.
    (قبلاً فقط در __main__ بود و start_dashboard.py هرگز فراخوانی‌اش نمی‌کرد.)"""
    try:
        threading.Thread(target=_sync_market_on_start, daemon=True).start()
        print("[startup] market sync thread spawned")
    except Exception as e:
        print(f"[startup] market sync thread failed: {e}")


@app.get("/", include_in_schema=False)
def serve_home():
    """صفحه اصلی = SPA React (فاز 7)."""
    return _spa_index()


# نکته ترتیب: APIها باید قبل از catch-all ثبت شوند تا اولویت بگیرند.
app.include_router(api_router())


@app.get("/{full_path:path}", include_in_schema=False)
def spa_catch_all(full_path: str):
    """فایل موجود در dist سرو می‌شود؛ هر مسیر دیگر -> index.html (رفرش SPA سالم)."""
    if _INDEX_HTML and full_path:
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
