"""Generic background-pipeline spawner (/api/sync/discover, update-existing).

Split verbatim out of app.py (v9.8.1 modularisation).
Every statement is byte-for-byte identical to app.py; only the route
decorators changed from @app.<verb> to @router.<verb>.
Audit map of source line spans: MIGRATED_LINES.txt
"""
from ._sync_codal import _codal_running
from bors_config import APP_DIR, CONTROL_PATH
from fastapi import APIRouter
from fastapi import Query
import datetime
import json
import subprocess
import sys


router = APIRouter()


def _spawn_pipeline(kind, limit, args):
    """اجرای پسزمینهٔ pipeline (subprocess.Popen) + ثبت job برای poll."""
    import subprocess, sys, os
    pid = None
    try:
        proc = subprocess.Popen(
            [sys.executable, "codal_fetcher.py", *args],
            cwd=APP_DIR,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        pid = proc.pid
    except Exception as e:
        _PIPELINE_JOBS[kind] = {"status": "error", "message": str(e)[:160],
                                "started": datetime.datetime.now().isoformat()}
        return _PIPELINE_JOBS[kind]
    _PIPELINE_JOBS[kind] = {"status": "running", "pid": pid, "limit": limit,
                            "started": datetime.datetime.now().isoformat()}
    return _PIPELINE_JOBS[kind]

@router.post("/api/sync/update-existing")
def api_update_existing(limit: int = Query(50, ge=1, le=500)):
    """v6 — update افزایشی در پسزمینه؛ فوراً برمیگردد (poll: /api/sync/pipeline)."""
    return _spawn_pipeline("update", limit, ["--update-symbols", str(limit)])

@router.post("/api/sync/discover")
def api_discover(limit: int = Query(25, ge=1, le=200)):
    """v7.4 — دریافت نمادهای جدید = فید سراسری discover (بهینه‌ترین روش:
    یک فید بازار-wide به‌جای ~۲۰۰۰ پراب نماد-به-نماد؛ ۹۶٪ پراب‌های قدیمی خالی بود).
    گارد ۲-اسکن همزمان + پاکسازی stop ماندگار مثل sync_codal."""
    if _codal_running():
        return {"status": "already_running",
                "message": "اسکن کدال در حال اجراست — صبر کنید تا تمام شود."}
    try:
        with open(CONTROL_PATH, "w", encoding="utf-8") as f:
            json.dump({"cmd": "resume", "ts": datetime.datetime.now().isoformat(timespec="seconds")}, f, ensure_ascii=False)
    except Exception:
        pass
    try:
        proc = subprocess.Popen([sys.executable, "codal_fetcher.py", "--feed", "discover"],
                                cwd=APP_DIR,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _PIPELINE_JOBS["discover"] = {"status": "running", "pid": proc.pid, "limit": limit,
                                      "started": datetime.datetime.now().isoformat()}
        return _PIPELINE_JOBS["discover"]
    except Exception as e:
        return {"status": "error", "message": str(e)[:160]}

_PIPELINE_JOBS = {}
