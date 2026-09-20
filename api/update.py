# -*- coding: utf-8 -*-
"""api/update.py -- به‌روزرسانِ درون‌برنامه‌ای واقعی برای نسخهٔ PyInstaller.

جایگزینِ شبیه‌سازیِ قدیمیِ فرانت‌اند: مرورگر این مسیرها را صدا می‌زند و
هستهٔ پایتون کارِ واقعی را انجام می‌دهد - دریافت مانیفست Tauri، دانلودِ
نصب‌کنندهٔ Inno، راستی‌آزماییِ امضای minisign و اجرای نصبِ سایلتی که نسخهٔ
جدید را دوباره بالامی‌آورد.

مسیرها
------
GET  /api/update/version         نسخهٔ فعلیِ برنامه
GET  /api/update/check           دریافت + پردازش latest.json و مقایسهٔ semver
POST /api/update/download        شروعِ دانلودِ نصب‌کنندهٔ امضاشده
GET  /api/update/progress        نظرسنجیِ وضعیتِ دانلود/راستی‌آزمایی
POST /api/update/install         راستی‌آزمایی → نصبِ سایلنت → بازنگریِ برنامه
POST /api/update/install-local   مثلِ بالا، با فایلِ نصب‌کننده + امضای دستی کاربر

مدلِ اعتماد
----------
تنها ریشهٔ اعتماد، کلیدِ عمومیِ minisign زیر است (.tauri/updater.key.pub).
هیچ‌چیز نصب نمی‌شود مگر اینکه نصب‌کننده تحت این کلید تأیید شود؛ پس یک
setup.exe دستکاری‌شده یا جعلی همیشه رد می‌شود - قبل از اینکه اصلاً لایهٔ
رمزِ خودِ Inno اجرا شود.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit

import requests
from fastapi import APIRouter, Request
from pydantic import BaseModel

from bors_config import APP_VERSION
from bors_minisign import verify_minisign

router = APIRouter()

# ---------------------------------------------------------------------------
# ریشهٔ اعتماد + محلِ مانیفست
# ---------------------------------------------------------------------------
# .tauri/updater.key.pub -- کلیدِ عمومیِ امضای minisign. عمومی است و فقط برای
# *اعتبارسنجی* استفاده می‌شود؛ هیچ کلید خصوصی‌ای در برنامه نیست.
UPDATE_PUBKEY = (
    "dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IDgzMEJGNzUyRUYxMDA3Ng"
    "pSV1IyQVBFdWRiOHdDRllFSTQrRUZwV0ZDYWJ6eTdiVWlQNlNJckk0dldnb294aVlkTy9oSFRHQwo="
)
# مانیفستِ Tauri - دقیقاً همان فایلی که scripts/publish_github_release.py
# می‌سازد و به ریلیز آپلود می‌کند.
LATEST_JSON_URL = ("https://github.com/johnwarchief/BorsTerminal"
                   "/releases/latest/download/latest.json")
PLATFORM_KEY = "windows-x86_64"
USER_AGENT = "BorsTerminal-Updater/" + APP_VERSION
# AppId در installer/bors_setup.iss (کروشه‌های بیرونی توسط Inno حذف می‌شوند)
APP_ID = "{8F3A2E7C-1B44-4C2E-9A77-0B0B5C0DE001}"
APP_EXE = "BorsTerminal_Ultimate.exe"

CACHE_DIR = os.path.join(tempfile.gettempdir(), "bors_update")
os.makedirs(CACHE_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# وضعیتِ مشترک با مرورگر (از طریق /api/update/progress نظرسنجی می‌شود)
# ---------------------------------------------------------------------------
_LOCK = threading.Lock()
_STATE = {
    "status": "idle",        # idle | downloading | verifying | ready | installing | error
    "downloaded": 0,
    "total": 0,
    "version": "",
    "path": "",
    "signature": "",
    "message": "",
}
_LAST_MANIFEST = None        # آخرین مانیفستِ موفق (برای download بدون پارامتر)
_INSTALL_LOCK = threading.Lock()


def _vkey(version):
    """کلیدِ مقایسهٔ semver: (major, minor, patch) — کمبودها با صفر پر می‌شوند."""
    nums = [int(n) for n in re.findall(r"\d+", str(version or ""))[:3]]
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums)


# ---------------------------------------------------------------------------
# رمزِ نصب‌کننده
# ---------------------------------------------------------------------------
_PW_RE = re.compile(r'#define\s+SetupPassword\s+"([^"]*)"')


def _resource_bases():
    """مسیرهایی که فایلِ رمزِ نصب‌کننده ممکن است در آنها باشد."""
    bases = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bases.append(meipass)                       # فایلِ datasِ PyInstaller
    if getattr(sys, "frozen", False):
        bases.append(os.path.dirname(os.path.abspath(sys.executable)))
    here = os.path.dirname(os.path.abspath(__file__))
    bases.append(here)                              # حالتِ dev: پکیجِ api/
    if not getattr(sys, "frozen", False):
        # در dev، رمز در ریشهٔ ریپو است (installer/.setup_password.iss) نه کنارِ
        # پکیجِ api — پس ریشهٔ ریپو را هم می‌گردیم.
        parent = os.path.dirname(here)
        if parent and parent != here:
            bases.append(parent)
    return [b for b in bases if b]


def _setup_password():
    """رمزِ نصب‌کنندهٔ Inno (installer/.setup_password که gitignored است).

    نصب‌کننده با Encryption=yes ساخته می‌شود، پس /VERYSILENT بدون رمز شکست
    می‌خورد. اولویت: متغیرِ محیطی → فایلِ باندل‌شده در زمانِ ساخت. اگر پیدا
    نشد، نصب به /SILENT تنزل می‌کند تا کاربر یک‌بار رمز را وارد کند.

    توجه: رمز هرگز نباید در ریپو commit شود؛ کدِ پایین‌دست فقط فایلِ
    gitignored را می‌خواند. باندل کردنِ آن در EXE نهایی به‌معنایِ
    قابلِ استخراج‌بودنِ رمز از سمتِ کاربر است - این بهایِ نصبِ کاملاً سایلنت
    است و کنترلِ یکپارگیِ واقعی، تأییدِ امضای minisign بالاتر است.
    """
    pw = (os.environ.get("BORS_SETUP_PASSWORD") or "").strip()
    if pw:
        return pw
    for base in _resource_bases():
        for name in ("setup.pw", ".setup_password.iss", "installer/.setup_password.iss",
                     ".setup_password", "installer/.setup_password"):
            path = os.path.join(base, name)
            if not os.path.isfile(path):
                continue
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError:
                continue
            m = _PW_RE.search(text)
            if m and m.group(1):
                return m.group(1)
            line = text.strip()
            if line and "\n" not in line and "#" not in line:
                return line                                # فرمتِ سادهٔ setup.pw
    return None


# ---------------------------------------------------------------------------
# محلِ نصب
# ---------------------------------------------------------------------------
def _registry_install_dir():
    """مسیرِ نصب از کلیدِ Uninstallِ Inno (HKCU سپس HKLM)."""
    try:
        import winreg
    except ImportError:
        return None
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(
                hive,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\\"
                + APP_ID + "_is1",
                0,
                winreg.KEY_READ,
            ) as key:
                loc, _ = winreg.QueryValueEx(key, "InstallLocation")
                if loc and os.path.isdir(loc):
                    return loc
        except OSError:
            continue
    return None


def _install_dir():
    """مسیرِ نصبِ فعلی - نصبِ سایلنت باید دقیقاً همان‌جا برود."""
    if getattr(sys, "frozen", False):
        # نسخهٔ onefile: کنارِ EXE، مسیرِ نصب است (sys._MEIPASS فقط استخراج است).
        d = os.path.dirname(os.path.abspath(sys.executable))
        if os.path.isfile(os.path.join(d, APP_EXE)):
            return d
    return _registry_install_dir()


# ---------------------------------------------------------------------------
# ساختِ آرگومانها + اجرای نصب
# ---------------------------------------------------------------------------
def _install_flags(log_path):
    """آرگومانهای نصبِ سایلنت Inno (به فرمتِ مستندِ Inno، با کوتیشن)."""
    password = _setup_password()
    flags = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"]
    if password:
        flags.append("/PASSWORD=" + password)
    else:
        # نصب‌کننده رمزگذاری‌شده است؛ در حالتِ کاملاً سایلنت نمی‌توان رمز را
        # پرسید، پس یک پنجرهٔ پیشرفت + باکسِ رمز به کاربر نشان داده می‌شود.
        flags[0] = "/SILENT"

    install_dir = _install_dir()
    mode = "/CURRENTUSER"          # per-user: بدون نیاز به UAC
    if install_dir:
        flags.append('/DIR="' + install_dir + '"')
        program_files = [os.environ.get(k, "") for k in
                         ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432")]
        if any(p and os.path.normcase(install_dir).startswith(os.path.normcase(p))
               for p in program_files if p):
            mode = "/ALLUSERS"     # نصبِ قبلی admin بوده؛ ارتقا ضروری (UAC ظاهر می‌شود)
    flags.append(mode)
    flags.append('/LOG="' + log_path + '"')
    return flags


def _delayed_exit(delay_seconds):
    """پروسهٔ فعلی را می‌بندد تا Inno بتواند فایلهای قفل‌شده را جایگزین کند."""
    time.sleep(delay_seconds)
    os._exit(0)


def _app_exe_path():
    """مسیرِ EXEٔ نصب‌شده - برای اجرای دوبارهٔ برنامه پس از نصبِ سایلنت."""
    d = _install_dir()
    if d:
        p = os.path.join(d, APP_EXE)
        if os.path.isfile(p):
            return p
    return None


def _spawn_install(installer, flags):
    """نصب‌کننده را طوری اجرا می‌کند که اول این پروسه تمام شود.

    ویندوز EXEِ در حال اجرا را قفل می‌کند و Inno نمی‌تواند آن را جایگزین
    کند (در حالتِ سایلنت، درگیری به‌طور پیش‌فرض abort است). راه‌حل: یک فایل
    دستور می‌نویسیم که منتظرِ مرگِ این پروسه بماند، بعد setup.exe را با
    /WAIT اجرا کند تا نصب تمام شود، و در آخر نسخهٔ جدید را دوباره باز
    کند؛ بخشِ [Run] در bors_setup.iss فقط در نصبِ تعاملی کار می‌کند و در
    /VERYSILENT اجرا نمی‌شود، پس اجرای دوبارهٔ اینجا انجام می‌شود.
    """
    pid = os.getpid()
    bat_path = os.path.join(CACHE_DIR, "bors_install.cmd")
    app_exe = _app_exe_path()
    lines = [
        "@echo off",
        "chcp 65001 >nul",
        ":wait",
        'tasklist /fi "PID eq %d" 2>nul | find "%d" >nul' % (pid, pid),
        "if errorlevel 1 goto run",
        "ping -n 2 127.0.0.1 >nul",
        "goto wait",
        ":run",
        # /WAIT: تا نصبِ کامل منتظر می‌مانیم تا فایلها جایگزین شوند و بعد
        # نسخهٔ جدید را اجرا کنیم. اگر کاربر UAC را رد کند، نصب نمی‌شود ولی
        # نسخهٔ قدیمی هنوز سالم است و دوباره باز می‌شود.
        'start /WAIT "" "%s" %s' % (installer, " ".join(flags)),
    ]
    if app_exe:
        lines += [
            'if not exist "%s" goto end' % app_exe,
            # start "" (بدون /WAIT): برنامه باز می‌شود و چوپان تمام می‌شود.
            # چوپان با اعتبارِ کاربرِ عادی اجرا شده، پس برنامه هم بدون
            # elevation بالا می‌آید — مثلِ اجرای دستی از منوی استارت.
            'start "" "%s"' % app_exe,
        ]
    lines += [":end", 'del "%~f0"']
    # chcp 65001 در خطِ اول (ASCII خالص) خطوطِ بعدی را UTF-8 می‌کند تا مسیرهای
    # غیرلاتین (مثل پروفایلِ کاربر) درست بمانند.
    with open(bat_path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\r\n".join(lines) + "\r\n")
    creationflags = 0x00000008 | 0x08000000        # DETACHED_PROCESS | CREATE_NO_WINDOW
    subprocess.Popen(["cmd", "/c", bat_path],
                     creationflags=creationflags, close_fds=True)
    threading.Thread(target=_delayed_exit, args=(2.0,), daemon=True).start()


# ---------------------------------------------------------------------------
# دانلود + راستی‌آزمایی
# ---------------------------------------------------------------------------
def _verify_file(path, signature):
    """فایل را روی دیسک می‌خواند و امضای minisign آن را تأیید می‌کند."""
    with open(path, "rb") as f:
        return verify_minisign(f.read(), signature, UPDATE_PUBKEY)


def _download_worker(url, signature, version, dest):
    try:
        tmp = dest + ".part"
        if os.path.isfile(url):
            # میان‌برِ dev: کپیِ محلی (برای تست بدون نیاز به اینترنت)
            _STATE.update(status="downloading", total=os.path.getsize(url),
                          downloaded=0, message="")
            n = 0
            with open(url, "rb") as src, open(tmp, "wb") as dst:
                while True:
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    dst.write(chunk)
                    n += len(chunk)
                    _STATE["downloaded"] = n
        else:
            with requests.get(url, stream=True, timeout=(10, 60),
                              headers={"User-Agent": USER_AGENT}) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("Content-Length") or 0)
                _STATE.update(status="downloading", total=total,
                              downloaded=0, message="")
                n = 0
                with open(tmp, "wb") as dst:
                    for chunk in resp.iter_content(1 << 20):
                        dst.write(chunk)
                        n += len(chunk)
                        _STATE["downloaded"] = n
        os.replace(tmp, dest)
        _STATE.update(status="verifying",
                      message="راستی‌آزمایی امضای دیجیتال بسته")
        _verify_file(dest, signature)
        _STATE.update(status="ready", path=dest, signature=signature,
                      version=version, message="")
    except Exception as exc:                                   # noqa: BLE001
        _STATE.update(status="error",
                      message="%s: %s" % (type(exc).__name__, exc))


def _fetch_manifest():
    """latest.json را از ریلیزِ آخرِ گیت‌هاب می‌گیرد (یا از مسیرِ محلیِ dev)."""
    local = (os.environ.get("BORS_UPDATE_MANIFEST") or "").strip()
    if local and os.path.isfile(local):
        with open(local, encoding="utf-8") as f:
            return json.load(f)
    resp = requests.get(LATEST_JSON_URL, timeout=(10, 30),
                        headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    return resp.json()



# ---------------------------------------------------------------------------
# مسیرها
# ---------------------------------------------------------------------------
@router.get("/api/update/version")
def update_version():
    """نسخهٔ فعلیِ برنامه (منبعِ واحد: bors_config.APP_VERSION)."""
    return {"version": APP_VERSION, "tauri": False}


@router.get("/api/update/check")
def update_check():
    try:
        manifest = _fetch_manifest()
    except Exception as exc:                                   # noqa: BLE001
        return {"status": "error", "current_version": APP_VERSION,
                "message": "دریافت مانیفست به‌روزرسانی ناموفق: %s" % exc}
    global _LAST_MANIFEST
    with _LOCK:
        _LAST_MANIFEST = manifest
    platform = _platform_of(manifest)
    latest = str(manifest.get("version") or "")
    available = bool(latest) and _vkey(latest) > _vkey(APP_VERSION)
    return {
        "status": "success",
        "current_version": APP_VERSION,
        "latest_version": latest,
        "available": available,
        "notes": manifest.get("notes") or "",
        "date": manifest.get("pub_date") or "",
        "url": platform.get("url") or "",
        "signature": platform.get("signature") or "",
        "updater": "python",
    }


class DownloadRequest(BaseModel):
    url: str | None = None
    signature: str | None = None
    version: str | None = None


@router.post("/api/update/download")
def update_download(req: DownloadRequest = DownloadRequest()):
    with _LOCK:
        manifest = _LAST_MANIFEST or {}
        platform = _platform_of(manifest)
        url = req.url or platform.get("url") or ""
        signature = req.signature or platform.get("signature") or ""
        version = req.version or str(manifest.get("version") or "")
    if not url or not signature:
        return {"status": "error",
                "message": "ابتدا /api/update/check را صدا بزنید."}
    name = os.path.basename(urlsplit(url).path) or "setup.exe"
    dest = os.path.join(CACHE_DIR, name)
    _STATE.update(status="downloading", downloaded=0, total=0, version=version,
                  path="", signature="", message="")
    threading.Thread(target=_download_worker,
                     args=(url, signature, version, dest), daemon=True).start()
    return {"status": "started", "path": dest}


@router.get("/api/update/progress")
def update_progress():
    return dict(_STATE)


def _run_install(installer, signature):
    """مرحلهٔ نهایی: تأییدِ دوبارهٔ امضا → اجرای نصبِ سایلنت → خروج."""
    with _INSTALL_LOCK:
        if not (os.path.isfile(installer) and signature):
            return {"status": "error", "message": "بسته یا امضا موجود نیست."}
        try:
            _verify_file(installer, signature)     # حیاتی: جلوگیری از نصبِ دستکاری‌شده
        except Exception as exc:                   # noqa: BLE001
            _STATE.update(status="error",
                          message="راستی‌آزمایی امضا ناموفق: %s" % exc)
            return {"status": "error",
                    "message": "راستی‌آزمایی امضا ناموفق: %s" % exc}
        log_path = os.path.join(CACHE_DIR, "install.log")
        flags = _install_flags(log_path)
        _STATE.update(status="installing", message="در حال نصبِ سایلنت")
        try:
            _spawn_install(installer, flags)
        except Exception as exc:                   # noqa: BLE001
            _STATE.update(status="error",
                          message="اجرای نصب‌کننده ناموفق: %s" % exc)
            return {"status": "error",
                    "message": "اجرای نصب‌کننده ناموفق: %s" % exc}
        # رمز هرگز در پاسخ به مرورگر لو نمی‌رود.
        safe_flags = [f for f in flags if not f.startswith("/PASSWORD")]
        return {"status": "installing", "log": log_path, "flags": safe_flags}


@router.post("/api/update/install")
def update_install():
    if _STATE.get("status") != "ready" or not _STATE.get("path"):
        return {"status": "error",
                "message": "بسته‌ای آماده نیست؛ اول /api/update/download را اجرا کنید."}
    return _run_install(_STATE["path"], _STATE.get("signature") or "")


@router.post("/api/update/install-local")
async def update_install_local(request: Request, signature: str = "",
                               name: str = "setup.exe"):
    """نصبِ آفلاین: بدنهٔ درخواست = بایت‌های setup.exe، پارامتر sig = امضا.

    بدونِ امضای معتبر چیزی نصب نمی‌شود - این همان ضمانتِ مسیرِ آنلاین است.
    از multipart استفاده نمی‌کنیم تا نیازی به python-multipart نباشد؛
    بدنهٔ خام با application/octet-stream مستقیماً روی دیسک استریم می‌شود.
    """
    sig_text = (signature or "").strip()
    if not sig_text:
        return {"status": "error", "message": "فایل امضا (.sig) را هم انتخاب کنید."}
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(name or "setup.exe"))
    if not safe.lower().endswith(".exe"):
        return {"status": "error", "message": "فقط نصب‌کنندهٔ .exe پذیرفته می‌شود."}
    dest = os.path.join(CACHE_DIR, "local_" + safe)
    received = 0
    try:
        with open(dest + ".part", "wb") as f:
            async for chunk in request.stream():
                f.write(chunk)
                received += len(chunk)
    except Exception as exc:                                   # noqa: BLE001
        return {"status": "error", "message": "دریافتِ فایل ناموفق: %s" % exc}
    if received < 1024:
        return {"status": "error", "message": "فایلِ دریافت‌شده کامل نیست."}
    os.replace(dest + ".part", dest)
    return _run_install(dest, sig_text)

def _platform_of(manifest):
    return (manifest.get("platforms") or {}).get(PLATFORM_KEY) or {}
