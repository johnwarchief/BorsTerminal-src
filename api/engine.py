"""codal_engine sync/ADB bridge -- the routes with no UI consumer yet.

Split verbatim out of app.py (v9.8.1 modularisation).
Every statement is byte-for-byte identical to app.py; only the route
decorators changed from @app.<verb> to @router.<verb>.
Audit map of source line spans: MIGRATED_LINES.txt
"""
from ._pipeline import _PIPELINE_JOBS
from codal_engine import run_sync_job, _adb_rotate, adb_status
from fastapi import APIRouter


router = APIRouter()


def _adb_control_available() -> bool:
    """ADB فقط روی ماشینِ توسعه‌دهنده؛ در EXE باندل‌شده همیشه False."""
    import codal_fetcher
    return bool(codal_fetcher.ADB_CONTROL_AVAILABLE)


@router.post("/api/sync/delta")
def api_delta_sync(payload: dict = None):
    """دلتای کدال؛ بدنهٔ اختیاری JSON: {"symbols": ["خودرو", ...]}"""
    try:
        return run_sync_job("delta", symbols=(payload or {}).get("symbols"))
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/api/sync/backfill")
def api_backfill_missing(days: int = 30):
    try:
        return run_sync_job("backfill", days=days)
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/api/sync/watchlist")
def api_watchlist_sync(user_id: int = 1):
    try:
        return run_sync_job("watchlist", user_id=user_id)
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/api/sync/full")
def api_full_sync():
    try:
        return run_sync_job("full")
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/api/adb/status")
def api_adb_status():
    if not _adb_control_available():
        return {"status": "unavailable", "enabled": False, "reason": "dev_only"}
    return adb_status()

@router.post("/api/adb/rotate")
def api_adb_rotate():
    if not _adb_control_available():
        return {"status": "unavailable", "new_ip": None, "reason": "dev_only"}
    new_ip = _adb_rotate()
    return {"status": "success" if new_ip else "error", "new_ip": new_ip}

@router.get("/api/sync/pipeline")
def api_pipeline_status():
    """Poll وضعیت job های pipeline (update/discover)."""
    return {"status": "success", "jobs": _PIPELINE_JOBS}
