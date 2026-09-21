# -*- coding: utf-8 -*-
"""لاانچر EXE: پیش‌اجرا + uvicorn + باز کردن مرورگر"""
import os, sys, threading, time, webbrowser, socket, subprocess

# در حالت EXE (onefile): کتابخانه‌ها داخل _MEIPASS؛ DB ها کنار exe (از ZIP)
if getattr(sys, 'frozen', False):
    BASE = sys._MEIPASS
    WORK = os.path.dirname(sys.executable)
    os.chdir(WORK)
else:
    WORK = os.path.dirname(os.path.abspath(__file__))

# ── گاردِ سازگاریِ ویندوز (v1.0.12) ───────────────────────────────────────
# ویندوزهایِ قدیمی (۷/۸/۸.۱) کرش‌های نامفهوم می‌دهند: TLSِ مدرن، فونت‌های
# فارسی، و رندرِ GPUِ کرومیوم رویِ درایورهایِ قدیمی. به‌جایِ کرشِ سایلنت،
# یک پیامِ واضح نشان می‌دهیم.
WIN_TOO_OLD = False
WIN_VER_NAME = "unknown"
try:
    _wv = sys.getwindowsversion()          # فقط رویِ ویندوز موجود است
    WIN_VER_NAME = "Windows %d.%d (build %d)" % (_wv.major, _wv.minor, _wv.build)
    if _wv.major < 10:
        WIN_TOO_OLD = True
except AttributeError:
    pass                                   # غیرِ ویندوز → هیچ گاردی لازم نیست


def _warn_old_windows():
    """پیامِ کاربرپسند برای ویندوزِ پشتیبانی‌نشده (به‌جای کرش)."""
    msg = (
        "⚠ این ویندوز برای اجرای کامل BorsTerminal پشتیبانی نمی‌شود.\n\n"
        "نسخهٔ سیستم‌عامل شما: %s\n"
        "حداقل نسخهٔ موردنیاز: Windows 10 (64-bit)\n\n"
        "برنامه اجرا می‌شود اما ممکن است:\n"
        "  • فونت‌های فارسی ناقص نمایش داده شوند\n"
        "  • رابط کاربری کند یا ناپایدار باشد\n"
        "  • برخی صفحات سفید شوند\n\n"
        "پیشنهاد: به Windows 10/11 ارتقا دهید." % WIN_VER_NAME
    )
    print("[WARN] unsupported Windows:", WIN_VER_NAME)
    try:
        # پیامِ نیتیو (نه کنسول) — کاربرِ دسکتاپ کنسول را نمی‌بیند.
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, "BorsTerminal — هشدار سازگاری", 0x30)
    except Exception:
        print(msg)


# ── گاردِ رندرینگ (v1.0.12): GPU ضعیف/نبود GPU → رندرِ نرم‌افزاری ─────────
# رویِ سیستم‌های بدونِ GPU اختصاصی (Intel HD قدیمی، Microsoft Basic Display)
# یا رمِ کم، کرومیوم صفحهٔ سفید یا کرش می‌دهد. SwiftShader (رندرِ
# نرم‌افزاریِ رسمیِ کرومیوم) این حالت را نجات می‌دهد.
def _probe_gpu():
    """(has_dedicated, adapter_names, ram_gb) — از WMI. در صورتِ شکست، محتاطانه.

    wmic رویِ Windows 11 حذف شده (deprecation) و خروجیِ خالی برمی‌گرداند،
    پس powershell را امتحان می‌کنیم و wmic فقط جایگزینِ آخر است.
    """
    adapters, ram_gb = [], 0.0
    ps = None
    try:
        ps = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "$ErrorActionPreference='SilentlyContinue';"
             "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name;"
             "[Environment]::PhysicalMemory"],
            capture_output=True, text=True, timeout=20, shell=True)
    except Exception:
        ps = None
    if ps is not None:
        lines = [ln.strip() for ln in (ps.stdout or "").splitlines() if ln.strip()]
        # خطِ آخر می‌تواند بایتِ کلِ رم باشد (یک عددِ بزرگ)
        for ln in lines:
            if ln.isdigit() and len(ln) >= 9:
                ram_gb = int(ln) / 1073741824.0
            elif ln.lower() not in ("name",):
                adapters.append(ln)
    if not adapters:
        try:                                   # جایگزینِ wmic برای ویندوزهای قدیمی
            out = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name"],
                capture_output=True, text=True, timeout=15, shell=True)
            for ln in (out.stdout or "").splitlines():
                ln = ln.strip()
                if ln and ln.lower() != "name":
                    adapters.append(ln)
        except Exception:
            pass
    if not adapters:
        return None, adapters, ram_gb
    dedicated = False
    for a in adapters:
        low = a.lower()
        # آداپتورهایِ اختصاصی (نه یکپارچهٔ رویِ پردازنده)
        if any(k in low for k in ("nvidia", "geforce", "quadro", "radeon",
                                  "amd radeon", "firepro", "arc a")):
            if not any(k in low for k in ("basic display", "microsoft")):
                dedicated = True
    return dedicated, adapters, ram_gb


def _needs_software_rendering():
    """True اگر GPU اختصاصی نیست یا رم کم است → پرچم‌هایِ رندرِ نرم‌افزاری.

    در صورتِ شکستِ تشخیص (پروب خالی برگرداند) «True» برمی‌گرداند: یک صفحهٔ
    سفیدِ غیرقابلِ استفاده بدتر از کمی کندیِ رندرِ نرم‌افزاری است. این
    انتخابِ محتاطانه است، نه یک باگ.
    """
    dedicated, adapters, ram_gb = _probe_gpu()
    if not adapters:
        return True                            # تشخیص ناموفق → محتاطانه
    if dedicated:
        return False                           # GPU اختصاصی هست → GPU بزن
    if ram_gb and ram_gb < 4.0:
        return True                            # رمِ کم → نرم‌افزاری
    if any("basic display" in a.lower() for a in adapters):
        return True                            # درایورِ ویندوزِ پیش‌فرض
    return True                                # فقط Intel HD یکپارچه


def _render_flags():
    """پرچم‌هایِ مرورگر بر اساسِ سخت‌افزار — برای جلوگیری از صفحهٔ سفید."""
    if _needs_software_rendering():
        print("[render] no dedicated GPU / low RAM -> software rendering (SwiftShader)")
        return ["--disable-gpu",
                "--use-angle=swiftshader",      # کرومیوم ۸۶+
                "--use-gl=swiftshader",         # نسخه‌های قدیمی‌تر
                "--disable-software-rasterizer=false"]
    return []

def _preflight():
    """هوشمند: پیش‌اجرا + چک DB ها (مثل run_terminal)"""
    print("=" * 66)
    print("  BorsTerminal_Ultimate - smart preflight")
    print("=" * 66)
    ok = True
    # خود استخراج market.db.lzma → market.db (فقط بار اول؛ کاملاً آفلاین)
    if not os.path.exists("market.db") and os.path.exists("market.db.lzma"):
        print("  [..]  extracting market.db.lzma (one-time, ~40s) ...")
        try:
            import lzma
            with open("market.db.lzma", "rb") as fi, open("market.db", "wb") as fo:
                fo.write(lzma.decompress(fi.read()))
            print("  [OK]  market.db extracted from .lzma")
        except Exception as e:
            print("  [ERR] lzma extraction failed:", e)
            ok = False
    if not os.path.exists("market.db"):
        print("  [ERR] market.db not found next to this EXE.")
        print("        Keep market.db/.lzma in the SAME folder as the EXE")
        print("        (it is inside the release ZIP, extract all files together).")
        ok = False
    else:
        try:
            import sqlite3
            c = sqlite3.connect("market.db")
            n = c.execute("SELECT COUNT(*) FROM instruments").fetchone()[0]
            c.close()
            print(f"  [OK]  market.db: {n:,} instruments (TSETMC + Codal data inside)")
        except Exception as e:
            print("  [WARN] market.db unreadable:", e)
    try:
        import pandas, numpy, fastapi, uvicorn, requests  # noqa
        print("  [OK]  bundled libraries: pandas/numpy/fastapi/uvicorn/requests (self-contained)")
    except ImportError as e:
        print("  [ERR] bundled library missing:", e)
        ok = False
    if ok:
        print("  [OK]  everything ready - starting ...")
    else:
        print("  [!!]  fix the missing files, then run this EXE again")
    print("=" * 66)
    return ok

def port_open(p):
    s = socket.socket(); s.settimeout(0.5)
    try:
        s.connect(('127.0.0.1', p)); return True
    except OSError:
        return False
    finally:
        s.close()

def wait_http(p, timeout=30):
    import urllib.request
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{p}/', timeout=2) as r:
                if r.status == 200: return True
        except Exception:
            pass
        time.sleep(1)
    return False

def find_app_browser():
    """پیدا کردن مرورگرهای کرومیوم (Edge, Chrome, Brave) برای باز کردن پنجره اختصاصی نرم‌افزار"""
    import shutil
    candidates = [
        os.path.expandvars("%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars("%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars("%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars("%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars("%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars("%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars("%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        os.path.expandvars("%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        shutil.which("msedge"),
        shutil.which("chrome"),
        shutil.which("brave"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None

def open_app_window(url):
    """باز کردن ترمینال در یک پنجره مستقل دسکتاپ (App Window Mode) بدون تب و نوار آدرس"""
    browser_exe = find_app_browser()
    if browser_exe:
        profile_dir = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
            "BorsTerminal_Ultimate",
            "app_profile",
        )
        os.makedirs(profile_dir, exist_ok=True)
        cmd = [
            browser_exe,
            f"--app={url}",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--start-maximized",
        ] + _render_flags()
        try:
            subprocess.Popen(cmd)
            print(f"[OK] App window launched using {os.path.basename(browser_exe)}")
            return True
        except Exception as e:
            print(f"[WARN] Failed to launch app window ({e}), falling back...")
    webbrowser.open(url)
    return False

def main():
    # v1.0.12: گاردِ ویندوز — قبل از هر چیز، تا روی ویندوزِ قدیمی کرشِ
    # نامفهوم ندهیم. هشدار نمایش می‌دهیم و ادامه می‌دهیم (نه مسدود).
    if WIN_TOO_OLD:
        _warn_old_windows()
    port = int(os.environ.get('BORS_PORT', '8001'))
    for p in (port,):
        if port_open(p):
            print(f'[OK] Server already running on {p} -> open app window')
            open_app_window(f'http://localhost:{p}')
            return
    if not _preflight():
        input('Press Enter to close...')
        return
    import uvicorn
    def run():
        uvicorn.run('app:app', host='127.0.0.1', port=port, log_level='info')
    th = threading.Thread(target=run, daemon=True)
    th.start()
    if wait_http(port):
        print(f'[OK] http://localhost:{port}')
        open_app_window(f'http://localhost:{port}')
    else:
        print('[ERR] server did not start')
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
