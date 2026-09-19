"""Codal fetcher supervision: launch, stop, status and diagnosis.

Split verbatim out of app.py (v9.8.1 modularisation).
Every statement is byte-for-byte identical to app.py; only the route
decorators changed from @app.<verb> to @router.<verb>.
Audit map of source line spans: MIGRATED_LINES.txt
"""
from ._core import _count_procs, _kill_procs, _safe_read_json
from bors_config import APP_DIR, CONTROL_PATH, MARKET_STATUS_PATH, OD_STATUS_PATH, STATUS_PATH, WORK_DIR
from fastapi import APIRouter
from fastapi import Query
from fastapi import Request
import codal_fetcher
import datetime
import json
import os
import subprocess
import sys


router = APIRouter()


@router.post("/api/sync/codal")
def sync_codal(mode: str = Query("update")):
    # گارد: اگر اسکنی در حال اجراست، فرایند جدید اجرا نکن (۲ اسکن همزمان = ۴۲۹ دائمی)
    if _codal_running():
        return {"status": "already_running",
                "message": "اسکن کدال در حال اجراست — صبر کنید تا تمام شود.",
                "mode": mode}
    # پاکسازی فرمان stop ماندگار؛ وگرنه نمونهٔ تازهٔ codal_fetcher فوراً خودش را متوقف میکند
    try:
        with open(CONTROL_PATH, "w", encoding="utf-8") as f:
            json.dump({"cmd": "resume", "ts": datetime.datetime.now().isoformat(timespec="seconds")}, f, ensure_ascii=False)
    except Exception:
        pass
    args = [sys.executable, "codal_fetcher.py"]
    if mode == "new":
        args += ["--backfill"]         # نمادهای قابل معامله با عنوان مالی ولی بدون FS → ۵ شاخص پرشدنی
    elif mode == "update":
        args += ["--feed", "update"]   # فید سراسری افزایشی از آخرین تاریخ DB (نمادهای موجود)
    elif mode == "optimized":
        args += ["--feed", "update", "--optimized"]   # بهینه: فقط FS قدیمی/خالی + نمادهای جدید (حداقل درخواست — بدون بلاک IP)
    elif mode == "backfill":
        args += ["--backfill"]         # Backfill FS/MS برای نمادهای دارای عنوان صورت مالی
    subprocess.Popen(args)
    return {"status": "success", "message": "Codal sync started.", "mode": mode}


@router.post("/api/sync/codal/fts-refresh")
def sync_codal_fts_refresh(mode: str = Query("monthly")):
    """تازه‌سازیِ فقط ۵ شاخصِ FTS از کدال (dev/codal_fts_updater.py) با چرخشِ IP.
    گارد: اجرای هم‌زمان ممنوع (ریسکِ ۴۲۹/بن)."""
    if _codal_running():
        return {"status": "already_running",
                "message": "اسکن کدال در حال اجراست — صبر کنید.", "mode": mode}
    try:
        with open(CONTROL_PATH, "w", encoding="utf-8") as f:
            json.dump({"cmd": "resume", "ts": datetime.datetime.now().isoformat(timespec="seconds")}, f, ensure_ascii=False)
    except Exception:
        pass
    script = os.path.join(APP_DIR, "dev", "codal_fts_updater.py")
    if not os.path.isfile(script):
        return {"status": "error", "message": "dev/codal_fts_updater.py یافت نشد."}
    subprocess.Popen([sys.executable, script, "--mode", mode, "--adb-rotate", "--resume"], cwd=APP_DIR)
    return {"status": "success", "message": "FTS 5-indicator refresh started.", "mode": mode}

@router.get("/api/sync/status")
def get_sync_status():
    """Live status for the Codal/Market sync progress overlay."""
    od = _safe_read_json(OD_STATUS_PATH) or {}
    st = _safe_read_json(STATUS_PATH) or {}
    ms = _safe_read_json(MARKET_STATUS_PATH) or {}   # کانال اختصاصی بازار
    # On-demand channel (sync_ondemand.json) wins ONLY while a manual sync is
    # actively running; once it ends in "done", fall back to the global channel
    # so background scans (discovery/codal) stay visible in the UI.
    # FIX: اگر فایل یک-روزه/قدیمی باشد (باقیماندهٔ اجرای قبلی بدون "done")،
    # od_active نباید true شود — با timestamp تصمیم میگیریم نه فقط stage.
    od_active = od.get("stage") not in (None, "done")
    if od_active and od.get("ts"):
        try:
            age = (datetime.datetime.now() - datetime.datetime.fromisoformat(od["ts"])).total_seconds()
            if age > 600:  # ۱۰ دقیقه — خیلی قدیمی؛ ignore
                od_active = False
        except Exception:
            od_active = False
    # بازار: اگر market_sync.json در ۱۰ دقیقهٔ اخیر تازه است (sync فعال)، گزارشش کن
    ms_active = False
    try:
        if ms.get("stage") not in (None, "done") and ms.get("ts"):
            age = (datetime.datetime.now() - datetime.datetime.fromisoformat(ms["ts"])).total_seconds()
            ms_active = age <= 600
    except Exception:
        ms_active = False
    if od_active:
        active = True
        merged = {
            "source": "od",
            "active": active,
            "symbol": od.get("symbol", ""),
            "stage": od.get("stage", "idle"),
            "detail": od.get("detail", ""),
            "phase": st.get("phase", ""),
            "total": st.get("total", 0),
            "current": st.get("current", 0),
            "percent": st.get("percent", 0.0),
            "elapsed": st.get("elapsed", 0.0),
            "ts": od.get("ts", ""),
        }
    else:
        # No active on-demand sync -> reflect the background/global channel
        # FIX: با timestamp تصمیم میگیریم — اگر پروسهٔ اسکن مرده و فایل
        # sync_status.json قدیمی (فریز > ~1 دقیقه) باشد، active=false نشان بده
        # وگرنه UI تا ابد «در حال بروزرسانی» را نشان میدهد.
        st_alive = False
        try:
            if st.get("stage") not in (None, "done", "idle") and st.get("phase") not in (None, "codal_stopped"):
                age = (datetime.datetime.now() - datetime.datetime.fromisoformat(st["ts"])).total_seconds()
                st_alive = age <= 60  # هر tick اسکن در <۱ دقیقه آپدیت میکند
        except Exception:
            st_alive = False
        active = st_alive
        merged = {
            "source": "global",
            "active": active,
            "symbol": st.get("symbol", ""),
            "stage": st.get("stage", "idle"),
            "detail": st.get("detail", ""),
            "phase": st.get("phase", ""),
            "total": st.get("total", 0),
            "current": st.get("current", 0),
            "percent": st.get("percent", 0.0),
            "elapsed": st.get("elapsed", 0.0),
            "ts": st.get("ts", ""),
        }
        # اگر بازار در حال sync است (market_sync.json تازه)، آن را ضمیمه کن
        if ms_active and not active:
            active = True
            merged.update({
                "source": "market",
                "symbol": ms.get("symbol", ""),
                "stage": ms.get("stage", "tsetmc"),
                "detail": ms.get("detail", ""),
                "phase": ms.get("phase", ""),
                "total": ms.get("total", 0),
                "current": ms.get("current", 0),
                "percent": ms.get("percent", 0.0),
                "elapsed": ms.get("elapsed", 0.0),
                "ts": ms.get("ts", ""),
            })
    merged["ban_until"] = st.get("ban_until", "")
    return {"status": "success", "sync": merged}

@router.get("/api/sync/diagnose")
def diagnose_sync():
    """تشخیص باگ: آیا codal_fetcher واقعاً اجرا میشود؟ آیا sync_status.json
    فریز شده؟ وضعیت ADB؟ — UI این را برای نمایش هشدار استفاده میکند."""
    import time as _t
    info = {"codal_process_running": bool(_count_procs("codal_fetcher")),
            "app_processes": _count_procs("app.py"),
            "adb_found": bool(codal_fetcher._find_adb()),
            "adb_device": False, "adb_enabled": codal_fetcher._adb_enabled()}
    # چک دستگاه ADB
    try:
        adb = codal_fetcher._find_adb()
        if adb:
            import subprocess
            r = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=8)
            info["adb_device"] = any(ln.split("\t")[-1].strip() == "device"
                                     for ln in (r.stdout or "").splitlines())
    except Exception:
        pass
    # سن sync_status.json
    try:
        mtime = os.path.getmtime(STATUS_PATH)
        age = _t.time() - mtime
        info["status_file_age_sec"] = round(age, 1)
        info["status_frozen"] = age > 60 and bool(_count_procs("codal_fetcher"))
    except Exception:
        info["status_file_age_sec"] = -1
        info["status_frozen"] = False
    # وضعیت تترینگ: آیا adapter ویندوز IP واقعی از تلفن گرفته؟
    info["adb_tether_up"] = bool(codal_fetcher._detect_tether_ip())
    # مرحله فعلی
    st = _safe_read_json(STATUS_PATH) or {}
    info["phase"] = st.get("phase", "")
    info["detail"] = st.get("detail", "")
    info["symbol"] = st.get("symbol", "")
    info["ts"] = st.get("ts", "")
    return {"status": "success", "diag": info}

def _write_control(cmd):
    """Write the user's pause/resume/stop intent for codal_fetcher.py to poll."""
    try:
        tmp = CONTROL_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"cmd": cmd,
                       "ts": datetime.datetime.now().isoformat(timespec="seconds")},
                      f, ensure_ascii=False)
        os.replace(tmp, CONTROL_PATH)
    except Exception:
        pass

def _codal_running():
    """True when at least one codal_fetcher python process is alive."""
    return _count_procs("codal_fetcher")

def _launch_codal_scan():
    """Launch run_discovery.sh through pinned Git Bash (WSL bash cannot cd to C:/).
    On POSIX (Linux/macOS) falls back to the system bash on PATH."""
    try:
        bash = None
        for p in ("C:/Program Files/Git/usr/bin/bash.exe",
                  "C:/Program Files/Git/bin/bash.exe",
                  "C:/Program Files (x86)/Git/usr/bin/bash.exe"):
            if os.path.isfile(p):
                bash = p
                break
        if not bash:
            import shutil
            bash = shutil.which("bash")
        if not bash:
            return False
        proj = APP_DIR
        # logs باید در WORK_DIR نوشته‌شونده باشند (APP_DIR در نصب Program Files
        # فقط‌خواندنی است)؛ cwd پروسه همچنان proj است تا run_discovery.sh پیدا شود.
        logs_dir = os.path.join(WORK_DIR, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        with open(os.path.join(logs_dir, "relauncher.log"), "a", encoding="utf-8") as lf:
            lf.write("[app] %s - resume: launching discovery scan\n"
                     % datetime.datetime.now().isoformat(timespec="seconds"))
        out = open(os.path.join(logs_dir, "relauncher.log"), "ab", buffering=0)
        subprocess.Popen([bash, "run_discovery.sh"], cwd=proj,
                         stdin=subprocess.DEVNULL, stdout=out,
                         stderr=subprocess.STDOUT,
                         creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                         | getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return True
    except Exception:
        return False

def _kill_codal_fetchers():
    """Force-stop every codal_fetcher process — کراس-پلتفرم."""
    _kill_procs("codal_fetcher")

def _mark_codal_stopped():
    """Write the stopped phase into sync_status.json so the UI shows
    ⏹️ کدال: متوقفشده and active=false even for a force-killed scan."""
    try:
        st = _safe_read_json(STATUS_PATH) or {}
        st["phase"] = "codal_stopped"
        st["detail"] = "اسکن توسط کاربر متوقف شد"
        st["ts"] = datetime.datetime.now().isoformat(timespec="seconds")
        tmp = STATUS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False)
        os.replace(tmp, STATUS_PATH)
    except Exception:
        pass

@router.post("/api/codal/control")
async def codal_control(request: Request):
    """Pause / resume / stop the Codal discovery scan from the dashboard."""
    try:
        body = await request.json()
    except Exception:
        return {"status": "error", "message": "invalid JSON body"}
    cmd = str((body or {}).get("cmd", "")).strip().lower()
    if cmd not in ("pause", "resume", "stop"):
        return {"status": "error", "message": "unknown cmd: %s" % cmd}
    _write_control(cmd)
    if cmd == "stop":
        _kill_codal_fetchers()
        _mark_codal_stopped()
    elif cmd == "resume" and not _codal_running():
        _launch_codal_scan()
    return {"status": "success", "cmd": cmd, "running": _codal_running()}
