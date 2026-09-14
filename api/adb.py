"""ADB / v2ray device state and configuration.

Split verbatim out of app.py (v9.8.1 modularisation).
Every statement is byte-for-byte identical to app.py; only the route
decorators changed from @app.<verb> to @router.<verb>.
Audit map of source line spans: MIGRATED_LINES.txt
"""
from bors_config import _ADB_CFG
from fastapi import APIRouter
from fastapi import Request
import json
import os
import subprocess


router = APIRouter()


@router.get("/api/adb/state")
def adb_state():
    """وضعیت راهنمای اینترنت/چرخش IP: adb + گوشی + تنظیم کاربر."""
    try:
        with open(_ADB_CFG, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    adb_path = None
    for p in (r"C:\adb\platform-tools\adb.exe", r"C:\adb\adb.exe",
              os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")):
        if os.path.exists(p):
            adb_path = p
            break
    phone = False
    if adb_path:
        try:
            out = subprocess.run([adb_path, "devices"], capture_output=True,
                                 text=True, timeout=10)
            phone = bool(out.stdout) and "device" in (out.stdout or "")
        except Exception:
            pass
    return {"status": "success",
            "enabled": bool(cfg.get("enabled", True)),
            "seen": bool(cfg.get("seen", False)),
            "adb_found": bool(adb_path),
            "phone": phone}

@router.post("/api/adb/set")
async def adb_set(request: Request):
    """تنظیم toggle چرخش IP + فلگ دیدهشدن راهنما."""
    try:
        body = await request.json()
    except Exception:
        return {"status": "error", "message": "invalid JSON body"}
    cfg = {}
    try:
        with open(_ADB_CFG, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        pass
    if "enabled" in body:
        cfg["enabled"] = bool(body["enabled"])
    if "seen" in body:
        cfg["seen"] = bool(body["seen"])
    try:
        tmp = _ADB_CFG + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False)
        os.replace(tmp, _ADB_CFG)
    except Exception:
        pass
    return {"status": "success", "config": cfg}
