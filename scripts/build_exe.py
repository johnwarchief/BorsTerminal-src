# -*- coding: utf-8 -*-
"""build_exe.py — ساخت EXE آفلاین BorsTerminal_Ultimate (PyInstaller one-file)"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repo root (this file lives in scripts/)

def main():
    os.chdir(ROOT)
    print("==> PyInstaller:", subprocess.run([sys.executable, "-m", "PyInstaller", "--version"], capture_output=True, text=True).stdout.strip())

    # فایل launcher (جای __main__)
    launcher = "bors_entry.py"
    with open(launcher, "w", encoding="utf-8") as f:
        f.write('''# -*- coding: utf-8 -*-
"""لاانچر EXE: پیش‌اجرا + uvicorn + باز کردن مرورگر"""
import os, sys, threading, time, webbrowser, socket, subprocess

# در حالت EXE (onefile): کتابخانه‌ها داخل _MEIPASS؛ DB ها کنار exe (از ZIP)
if getattr(sys, 'frozen', False):
    BASE = sys._MEIPASS
    WORK = os.path.dirname(sys.executable)
    os.chdir(WORK)
else:
    WORK = os.path.dirname(os.path.abspath(__file__))

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
        os.path.expandvars("%ProgramFiles(x86)%\\Microsoft\\Edge\\Application\\msedge.exe"),
        os.path.expandvars("%ProgramFiles%\\Microsoft\\Edge\\Application\\msedge.exe"),
        os.path.expandvars("%LOCALAPPDATA%\\Microsoft\\Edge\\Application\\msedge.exe"),
        os.path.expandvars("%ProgramFiles%\\Google\\Chrome\\Application\\chrome.exe"),
        os.path.expandvars("%ProgramFiles(x86)%\\Google\\Chrome\\Application\\chrome.exe"),
        os.path.expandvars("%LOCALAPPDATA%\\Google\\Chrome\\Application\\chrome.exe"),
        os.path.expandvars("%ProgramFiles%\\BraveSoftware\\Brave-Browser\\Application\\brave.exe"),
        os.path.expandvars("%LOCALAPPDATA%\\BraveSoftware\\Brave-Browser\\Application\\brave.exe"),
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
        ]
        try:
            subprocess.Popen(cmd)
            print(f"[OK] App window launched using {os.path.basename(browser_exe)}")
            return True
        except Exception as e:
            print(f"[WARN] Failed to launch app window ({e}), falling back...")
    webbrowser.open(url)
    return False

def main():
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
''')
    print("==> launcher written")

    # مشخصات PyInstaller (ONEDIR بهینه برای ZIP — مرتبه کمتر از onefile)
    spec = "bors_exe_onedir.spec"
    root_f = ROOT.replace("\\", "/")
    with open(spec, "w", encoding="utf-8") as f:
        f.write(f'''# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ['{"bors_entry.py"}'],
    pathex=['{root_f}'],
    binaries=[],
    datas=[
        ('static', 'static'),
        ('app.py', '.'),
        ('bootstrap_first_run.py', '.'),
        ('codal_fetcher.py', '.'),
        ('fts_engine.py', '.'),
        ('fts_thresholds.json', '.'),
        ('test_tsetmc.py', '.'),
    ] + [t for t in (('adb_config.json', '.'), ('codal_control.json', '.'))
         if os.path.exists(t[0])],
    hiddenimports=['uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.protocols.http.auto',
                   'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan.on',
                   'codal_fetcher', 'app', 'test_tsetmc', 'fts_engine', 'orjson', 'pandas', 'numpy',
                   # v9.8.1: app.py was split verbatim into the api/ package; the
                   # frozen build MUST bundle these or the EXE dies with
                   # ModuleNotFoundError on the first request. api_router()
                   # imports them inside the function body, so PyInstaller's
                   # static import scan cannot see them.
                   'bors_config', 'bors_flags', 'api',
                   'api._core', 'api.market', 'api.chart', 'api.selection',
                   'api.watchlist', 'api.fundamental', 'api.market_status',
                   'api.screener', 'api._sync_market', 'api._export',
                   'api._sync_codal', 'api.adb', 'api.notify',
                   'api._pipeline', 'api.engine',
                   'pandas._libs.tslibs.np_datetime', 'pandas._libs.tslibs.offsets', 'docx', 'openpyxl', 'reportlab',
                   'lxml', 'lxml.etree', 'click', 'cryptography', 'dateutil', 'websockets', 'packaging',
                   'PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont', 'PIL._imaging'],
    excludes=['tkinter', 'matplotlib', 'pytest', 'scipy', 'sympy', 'selenium',
              'setuptools', 'pip',
              'boto3', 'botocore', 's3transfer',
              'watchfiles', 'httptools'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name='BorsTerminal_Ultimate', debug=False, bootloader_ignore_signals=False,
          strip=False, upx=False,
          console=True, icon=None)
col = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='BorsTerminal_Ultimate')
''' + '')
    print("==> spec written")

    # اجرای build (onefile برای خروجی تکفایل) — برای نسخه zip از onedir استفاده کن (فشرده‌تر)
    cmd = [sys.executable, "-m", "PyInstaller", spec, "--clean", "--noconfirm", "--log-level", "WARN"]
    print("==> running:", " ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print("BUILD FAILED")
        sys.exit(1)
    # bors_exe_onedir.spec builds a COLLECT (onedir) target, so the EXE lives
    # inside dist/BorsTerminal_Ultimate/, not next to it. Accept both layouts so
    # this script reports the size instead of dying on getsize().
    exe = os.path.join(ROOT, "dist", "BorsTerminal_Ultimate",
                       "BorsTerminal_Ultimate.exe")
    if not os.path.exists(exe):
        exe = os.path.join(ROOT, "dist", "BorsTerminal_Ultimate.exe")
    out_dir = os.path.dirname(exe)
    print("==> OK:", exe)
    print("==> size MB:", round(os.path.getsize(exe) / 1048576, 1))
    print("==> dist dir:", out_dir)

if __name__ == "__main__":
    main()
