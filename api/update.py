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
POST /api/update/download        شروعِ دانلودِ بستهٔ امضاشده (پچ دلتا در صورتِ وجود)
GET  /api/update/progress        نظرسنجیِ وضعیتِ دانلود/راستی‌آزمایی
POST /api/update/install         راستی‌آزمایی → اعمالِ پچ/نصبِ سایلنت → بازنگری
POST /api/update/install-local   مثلِ بالا، با فایلِ نصب‌کننده + امضای دستی کاربر

مدلِ اعتماد
----------
تنها ریشهٔ اعتماد، کلیدِ عمومیِ minisign زیر است (.tauri/updater.key.pub).
هیچ‌چیز نصب نمی‌شود مگر اینکه نصب‌کننده تحت این کلید تأیید شود؛ پس یک
setup.exe دستکاری‌شده یا جعلی همیشه رد می‌شود - قبل از اینکه اصلاً لایهٔ
رمزِ خودِ Inno اجرا شود.

به‌روزرسانیِ دلتا (v1.0.10)
---------------------------
latest.json می‌تواند یک آرایهٔ اختیاریِ ``patches`` داشته باشد که هر ورودی‌اش
یک پچِ امضاشدهٔ «رویهمگذاری» را معرفی می‌کند. آپدیتِر فقط زمانی پچ را
برمی‌گزیند که ``from`` با نسخهٔ فعلیِ برنامه برابر باشد؛ در غیر این صورت، یا
اگر امضا یا قابلیتِ نوشتن در مسیرِ نصب شکست بخورد، به نصبِ کاملِ Inno
برمی‌گردد. پچ‌ها هم با همین کلیدِ minisign امضا می‌شوند، پس مرزِ امنیتی
تغییری نکرده است.
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
    "is_patch": False,       # v1.0.10: بستهٔ آماده، پچِ دلتاست یا نصبِ کامل؟
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


def _sync_display_version():
    """DisplayVersionِ کلیدِ Uninstall را با APP_VERSION همگام می‌کند.

    نصب‌کنندهٔ Inno این مقدار را می‌نویسد، ولی یک پَچ فقط فایل‌ها را
    جایگزین می‌کند؛ پس Add/Remove Programs بدون این همگام‌سازی همچنان
    نسخهٔ قبلی را نشان می‌دهد. این تابع خودش را رویِ هر استارتاپ تعمیر
    می‌کند، تا حتی یک پَچ که apply_update.batِ قدیمی دارد هم درست می‌شود.
    """
    try:
        import winreg
    except ImportError:
        return False
    key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\\" + APP_ID + "_is1"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, key_path, 0, winreg.KEY_SET_VALUE) as key:
                cur, _ = winreg.QueryValueEx(key, "DisplayVersion")
                if cur == APP_VERSION:
                    return True
                winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
                return True
        except OSError:
            continue
    return False


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
        with open(local, encoding="utf-8-sig") as f:
            return json.load(f)
    resp = requests.get(LATEST_JSON_URL, timeout=(10, 30),
                        headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    return resp.json()


def _select_patch(manifest):
    """پچِ دلتای مناسب را برمی‌گزیند یا None برمی‌گرداند.

    شرایط (هر چهار باید برقرار باشند، وگرنه به نصبِ کامل برمی‌گردیم):
      1) مانیفست آرایهٔ patches دارد
      2) patch.from == نسخهٔ فعلیِ برنامه (پچِ 1.0.9→1.0.10 روی 1.0.8 اعمال نمی‌شود)
      3) patch.to == نسخهٔ هدفِ مانیفست (پچِ قدیمی روی مانیفستِ جدید شکار نمی‌شود)
      4) url + signature موجود است
    """
    patches = manifest.get("patches") or []
    if not isinstance(patches, list):
        return None
    target = str(manifest.get("version") or "")
    for p in patches:
        if not isinstance(p, dict):
            continue
        if str(p.get("from") or "") != APP_VERSION:
            continue
        if str(p.get("to") or "") != target:
            continue
        if not (p.get("url") and p.get("signature")):
            continue
        return p
    return None


def _install_dir_writable():
    """آیا پوشهٔ نصب نوشتنی است؟ (پرتابیل/ per-user: بله. Program Files: خیر)

    پچِ overlay باید در محل extract شود؛ اگر مسیر فقط‌خواندنی باشد (نصبِ
    all-users) بدونِ elevation نمی‌توان فایلها را جایگزین کرد، پس به نصبِ
    کاملِ Inno برمی‌گردیم که خودش UAC را مدیریت می‌کند.
    """
    d = _install_dir()
    if not d:
        return False
    try:
        probe = os.path.join(d, ".wtprobe")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False


def _extract_applier_from_patch(patch_zip, dest_bat):
    """apply_update.bat را از داخلِ خودِ پچِ امضاشده استخراج می‌کند.

    نصب‌های قدیمی‌تر از 1.0.10 این فایل را در محلِ نصب ندارند (قبل از آن به
    [Files] نصب‌کننده اضافه نشده بود). پچ آن را همراهِ خود می‌آورد و چون پچ
    پیش از این توسطِ minisign راستی‌آزمایی شده، استخراجِ اعمال‌کننده از آن
    درونِ مرزِ اعتماد است.
    """
    import zipfile
    try:
        with zipfile.ZipFile(patch_zip) as zf:
            names = zf.namelist()
            if "apply_update.bat" not in names:
                return False
            with zf.open("apply_update.bat") as src, \
                    open(dest_bat, "wb") as dst:
                dst.write(src.read())
        return os.path.isfile(dest_bat)
    except (OSError, zipfile.BadZipFile, KeyError):
        return False


def _spawn_patch_apply(patch_zip):
    """اعمال‌کنندهٔ پچِ shipped را spawn می‌کند و بعد از آن خارج می‌شود.

    scripts/apply_update.bat در محلِ نصب وجود دارد (توسطِ [Files] نصب‌کننده
    کپی شده) و جریانِ اثبات‌شده را دارد: کپیِ خودش به %TEMP% → توقفِ نرمِ
    برنامه → extract درجا → مهرِ Version.txt → اجرای دوباره. ما فقط zip را
    کنارش می‌گذاریم و BORS_UPDATE_NORELAUNCH را set نمی‌کنیم تا همان مسیر
    استانداردِ relaunch طی شود.

    اگر اعمال‌کننده در محلِ نصب نباشد (نصبِ قدیمی‌تر از 1.0.10)، از داخلِ
    خودِ پچِ امضاشده استخراج می‌شود تا دلتا حتی برایِ نسخه‌ای که آن را
    نمی‌شناسد هم کار کند.
    """
    d = _install_dir()
    if not d:
        return None
    applier = os.path.join(d, "apply_update.bat")
    if not os.path.isfile(applier):
        if not _extract_applier_from_patch(patch_zip, applier):
            return None
    # apply_update.bat انتظار دارد BorsTerminal_Update.zip کنارش باشد.
    target_zip = os.path.join(d, "BorsTerminal_Update.zip")
    try:
        import shutil
        shutil.copyfile(patch_zip, target_zip)
    except OSError as exc:
        raise RuntimeError("کپیِ پچ به مسیرِ نصب ناموفق: %s" % exc)
    kw = {"cwd": d, "close_fds": True}
    if sys.platform == "win32":
        kw["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(["cmd.exe", "/c", applier], **kw)
    _STATE.update(status="installing",
                  message="در حال اعمالِ پچِ به‌روزرسانی")
    # درِ مسیرِ نصبِ کامل: مرگِ پروسه در یک رشتهِٔ بعدی. قبلاً همین‌جا
    # _delayed_exit(2.0) صدا زده می‌شد و handler هیچ‌وقت return نمی‌شد، پس
    # POSTِ /install با connection reset می‌مرد و فرانت‌اند آن را «اتصال به
    # سرور برقرار نشد، اینترنت‌ات را چک کن» نشان می‌داد — یعنی یک آپدیتِ
    # موفق در چِشمِ کاربر «اعمال نشد» خوانده می‌شد (گزارشِ مالک، و بازسازیِ
    # زنده روی ۱٫۰٫۶۵→۱٫۰٫۶۸ که با همان reset جواب داد ولی پچ را درست گذاشت).
    threading.Thread(target=_delayed_exit, args=(2.0,), daemon=True).start()
    return applier



# ---------------------------------------------------------------------------
# مسیرها
# ---------------------------------------------------------------------------
@router.get("/api/update/version")
def update_version():
    """نسخهٔ فعلیِ برنامه (منبعِ واحد: bors_config.APP_VERSION)."""
    # یک پَچ فقط فایل‌ها را جایگزین می‌کند، پس DisplayVersionِ رجیستری
    # می‌تواند پشت بماند. اینجا خودش را تعمیر می‌کنیم تا Add/Remove
    # Programs همیشه با نسخهٔ واقعیِ در حالِ اجرا موافق باشد.
    try:
        _sync_display_version()
    except Exception:
        pass
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
    # v1.0.10: اگر پچِ دلتایی برای همین نسخه موجود باشد، مرورگر آن را به جای
    # نصبِ کامل نشان می‌دهد (حجمِ بسیار کمتر). انتخابِ نهایی در download انجام
    # می‌شود تا بینِ check و download تغییرِ نسخه رخ ندهد.
    patch = _select_patch(manifest) if available else None
    return {
        "status": "success",
        "current_version": APP_VERSION,
        "latest_version": latest,
        "available": available,
        "notes": manifest.get("notes") or "",
        "date": manifest.get("pub_date") or "",
        "url": (patch or platform).get("url") or "",
        "signature": (patch or platform).get("signature") or "",
        "updater": "python",
        "delta": bool(patch),
        "size": int((patch or platform).get("size") or 0),
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
        # v1.0.10: پچِ دلتا اولویت دارد. مرورگر url/signature را از /check برمی‌گرداند
        # که در صورتِ وجودِ پچ، خودِ urlِ پچ است؛ پس تطبیقِ url را به جایِ
        # «خالی‌بودنِ پارامتر» می‌سنجیم تا نصبِ کاملِ صریح هم پچ را دور نزند.
        patch = _select_patch(manifest)
        patch_url = (patch or {}).get("url") or ""
        if patch and (not req.url or req.url == patch_url):
            url = patch_url
            signature = patch.get("signature") or ""
            is_patch = True
        else:
            # نشانی و امضا تنها از مانیفستِ رسمی گرفته می‌شوند. اگر کلاینت
            # نشانیِ دیگری بفرستد که با مانیفست نمی‌خواند، درخواست رد می‌شود —
            # وگرنه هر صفحهٔ وبی می‌تواند یک باینریِ دلخواه (حتی نسخهٔ قدیمیِ
            # امضاشدهٔ خودش) را به مسیرِ نصبِ بی‌صدای Inno بفرستد.
            expected = platform.get("url") or ""
            if req.url and expected and req.url != expected:
                return {"status": "error",
                        "message": "نشانیِ داده‌شده با مانیفستِ به‌روزرسانی "
                                   "هم‌خوان نیست؛ اول /api/update/check را بزنید."}
            url = expected
            signature = platform.get("signature") or ""
            is_patch = False
        version = req.version or str(manifest.get("version") or "")
    if not url or not signature:
        return {"status": "error",
                "message": "ابتدا /api/update/check را صدا بزنید."}
    name = os.path.basename(urlsplit(url).path) or "setup.exe"
    dest = os.path.join(CACHE_DIR, name)
    _STATE.update(status="downloading", downloaded=0, total=0, version=version,
                  path="", signature="", message="", is_patch=is_patch)
    threading.Thread(target=_download_worker,
                     args=(url, signature, version, dest), daemon=True).start()
    return {"status": "started", "path": dest, "delta": is_patch}


@router.get("/api/update/progress")
def update_progress():
    return dict(_STATE)


def _run_install(installer, signature, is_patch=False):
    """مرحلهٔ نهایی: تأییدِ دوبارهٔ امضا → اعمالِ پچ یا نصبِ سایلنت → خروج.

    اگر ``is_patch`` باشد و مسیرِ نصب نوشتنی باشد، پچِ overlay از طریقِ
    apply_update.batِ shipped اعمال می‌شود (حجمِ بسیار کمتر). در هر شکستِ
    منطقیِ آن مسیر، شفافاً به نصبِ کاملِ Inno برمی‌گردیم تا به‌روزرسانی هرگز
    به‌خاطرِ وجودِ پچ انجام‌نشده باقی نماند.
    """
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

        if is_patch:
            # پیش‌نیازهای پچ: مسیرِ نصبِ مشخص + نوشتنی + اعمال‌کنندهٔ shipped.
            # هر کدام نبود → نصبِ کامل بدونِ سوال (fallback خودکار).
            if _install_dir_writable():
                _STATE.update(status="installing", message="در حال اعمالِ پچ")
                try:
                    applier = _spawn_patch_apply(installer)
                except Exception as exc:           # noqa: BLE001
                    applier = None
                    _STATE.update(status="error",
                                  message="اعمالِ پچ ناموفق: %s" % exc)
                if applier:
                    return {"status": "installing", "delta": True,
                            "applier": applier}
                # اعمال‌کننده نه در محلِ نصب بود و نه از داخلِ پچ استخراج شد
                # (مثلاً پچِ ناقص یا خطای دیسک) → fallback به نصبِ کامل.
            _STATE.update(status="installing",
                          message="در حال نصبِ کامل (fallback)")

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
    return _run_install(_STATE["path"], _STATE.get("signature") or "",
                        bool(_STATE.get("is_patch")))


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
    lower = safe.lower()
    # v1.0.10: پچِ دلتا (.zip) هم مثلِ نصب‌کنندهٔ کامل پذیرفته می‌شود؛ هر دو
    # زیرِ همان کلیدِ minisign امضا شده‌اند، پس مرزِ امنیتی یکسان است.
    is_patch = lower.endswith(".zip")
    if not (lower.endswith(".exe") or is_patch):
        return {"status": "error",
                "message": "فقط نصب‌کنندهٔ .exe یا پچِ .zip پذیرفته می‌شود."}
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
    return _run_install(dest, sig_text, is_patch)

def _platform_of(manifest):
    return (manifest.get("platforms") or {}).get(PLATFORM_KEY) or {}
