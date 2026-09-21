"""api/diagnostics.py — ابزارهای دیاگنوستیکِ سمتِ کلاینت.

v1.0.13: برنامه دیگر پنجرهٔ کنسولی باز نمی‌کند (console=False در spec)،
په لاگ‌ها به جایِ صفحه در WORK/logs/bors.log می‌روند. این ماژول دو چیز
می‌دهد:
  * GET  /api/diagnostics/log      — آخرینِ لاگ را برمی‌گرداند (مرور در UI)
  * POST /api/diagnostics/log/open — فایلِ لاگ را با ادیتورِ پیش‌فرض باز می‌کند
  * GET  /api/diagnostics/info     — مسیرها/نسخه/وضعیتِ کنسول

هیچ اطلاعاتِ حساسی نشت نمی‌کند: فقط مسیرهای محلی و متنِ لاگ.
"""
import os
import sys

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from bors_config import APP_VERSION

router = APIRouter()


def _work_dir() -> str:
    """پوشهٔ قابلِ نوشتنِ کنارِ EXE (frozen) یا ریشهٔ ریپو (dev)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _log_path() -> str:
    return os.path.join(_work_dir(), "logs", "bors.log")


def _console_enabled() -> bool:
    """True اگر این پروسه با کنسولِ واقعی اجرا شده (دیباگِ دستی)."""
    return os.environ.get("BORS_SHOW_CONSOLE") == "1"


@router.get("/api/diagnostics/info")
def diagnostics_info():
    return {
        "status": "success",
        "version": APP_VERSION,
        "frozen": bool(getattr(sys, "frozen", False)),
        "work_dir": _work_dir(),
        "log_path": _log_path(),
        "log_exists": os.path.isfile(_log_path()),
        "log_size": (os.path.getsize(_log_path()) if os.path.isfile(_log_path()) else 0),
        "console_visible": _console_enabled(),
    }


@router.get("/api/diagnostics/log")
def diagnostics_log(tail: int = 200):
    """آخرینِ خطوطِ لاگ (پیش‌فرض ۲۰۰). مرور در UI بدونِ باز کردنِ پنجره."""
    path = _log_path()
    if not os.path.isfile(path):
        return PlainTextResponse(
            "(no log file yet — console is hidden and nothing has been logged)",
            media_type="text/plain; charset=utf-8")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        n = max(0, int(tail))
        body = "".join(lines[-n:]) if n else "".join(lines)
        return PlainTextResponse(body, media_type="text/plain; charset=utf-8")
    except OSError as exc:
        return PlainTextResponse(f"(cannot read log: {exc})",
                                 media_type="text/plain; charset=utf-8")


@router.post("/api/diagnostics/log/open")
def diagnostics_log_open():
    """فایلِ لاگ را با ادیتورِ پیش‌فرضِ ویندوز باز می‌کند (درخواستِ دستی)."""
    path = _log_path()
    if not os.path.isfile(path):
        return {"status": "error", "message": "log file does not exist yet"}
    try:
        import subprocess  # noqa: PLC0415  (importِ محلی: فقط ویندوز)
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa: S606  (ادیتورِ پیش‌فرضِ کاربر)
        else:
            subprocess.Popen(["xdg-open", path])  # noqa: S603,S607
        return {"status": "success", "path": path}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "message": f"{type(exc).__name__}: {exc}"}
