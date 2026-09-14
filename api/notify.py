"""Telegram + Bale notification dispatcher endpoints.

Split verbatim out of app.py (v9.8.1 modularisation).
Every statement is byte-for-byte identical to app.py; only the route
decorators changed from @app.<verb> to @router.<verb>.
Audit map of source line spans: MIGRATED_LINES.txt
"""
from bors_flags import NOTIFIER_AVAILABLE
from fastapi import APIRouter
import notifier


router = APIRouter()


@router.get("/api/notify/status")
def notify_status():
    """وضعیت پیکربندی کانالها — بدون توکن (وضعیت امن)."""
    if not NOTIFIER_AVAILABLE:
        return {"status": "error", "message": "notifier module unavailable (httpx?)"}
    return {"status": "success", "channels": notifier.status()}

def _msg_ok(res, channel: str):
    """خلاصهٔ ارسال (dict از notifier) → پاسخ API گزارشهای عددی."""
    if isinstance(res, dict):
        return {"status": "success" if res.get("ok") else "error",
                "channel": channel,
                "success": int(res.get("success", 0)),
                "failed": int(res.get("failed", 0)),
                "detail": res.get("detail", "")}
    return {"status": "success" if res else "error",
            "channel": channel,
            "detail": ("پیام ارسال شد" if res else f"ارسال ناموفق — logهای [{channel}] را ببینید")}

@router.post("/api/notify/test-telegram")
async def notify_test_telegram():
    if not NOTIFIER_AVAILABLE:
        return {"status": "error", "message": "notifier unavailable"}
    ok = await notifier.send_telegram_msg("🚀 BorsTerminal Notification Test Successful.")
    return _msg_ok(ok, "notifier-telegram")

@router.post("/api/notify/test-bale")
async def notify_test_bale():
    if not NOTIFIER_AVAILABLE:
        return {"status": "error", "message": "notifier unavailable"}
    ok = await notifier.send_bale_msg("🚀 BorsTerminal Notification Test Successful.")
    return _msg_ok(ok, "notifier-bale")

@router.post("/api/notify/test-all")
async def notify_test_all():
    """ارسال نمونه به همهٔ کانالهای فعال (همزمان)."""
    if not NOTIFIER_AVAILABLE:
        return {"status": "error", "message": "notifier unavailable"}
    res = await notifier.dispatch_alert("🚀 BorsTerminal Notification Test Successful.")
    return res
