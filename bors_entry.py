# -*- coding: utf-8 -*-
"""لاانچر EXE: پیش‌اجرا + uvicorn + باز کردن مرورگر"""
import os, sys, threading, time, webbrowser, socket, subprocess

# در حالت EXE (frozen): کتابخانه‌ها/دیتاها داخل _MEIPASS (onedir: _internal)؛
# DB ها و فایل‌های وضعیت در WORK_DIR (نوشتنی) — کنار exe اگر نوشتنی باشد،
# وگرنه %LOCALAPPDATA%\BorsTerminal_Ultimate (نصب در Program Files).
if getattr(sys, 'frozen', False):
    BASE = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    import bors_config
    WORK = bors_config.WORK_DIR
    os.makedirs(WORK, exist_ok=True)
    os.chdir(WORK)
    if WORK not in sys.path:
        sys.path.insert(0, WORK)
else:
    WORK = os.path.dirname(os.path.abspath(__file__))

def _preflight():
    """هوشمند: پیش‌اجرا + چک DB ها (مثل run_terminal)"""
    print("=" * 66)
    print("  BorsTerminal_Ultimate - smart preflight")
    print("=" * 66)
    ok = True
    # خود استخراج market.db.lzma → market.db (فقط بار اول؛ کاملاً آفلاین).
    # ensure_market_db در صورتِ نیاز market.db را در WORK_DIR نوشتنی
    # می‌سازد. اکنون DB_PATH هم فقط به محل‌های نوشتنی اشاره می‌کند
    # (_resolve_market_db از exe_dirِ فقط‌خواندنی صرف‌نظر می‌کند) تا WAL
    # بتواند -wal/-shm را بسازد و هیچ endpointای با Permission denied گیر
    # نکند.
    import bors_config
    db_path = bors_config.ensure_market_db(verbose=True)
    if not db_path or not os.path.exists(db_path):
        print("  [ERR] market.db not found and could not be extracted.")
        print("        market.db.lzma is shipped in the install folder (next to")
        print("        the EXE). Reinstall or copy it there, then run again.")
        ok = False
    else:
        try:
            import sqlite3
            c = sqlite3.connect(db_path)
            n = c.execute("SELECT COUNT(*) FROM instruments").fetchone()[0]
            c.close()
            where = "next to EXE" if os.path.dirname(db_path) == os.path.dirname(sys.executable) else os.path.dirname(db_path)
            print(f"  [OK]  market.db: {n:,} instruments ({where})")
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
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
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

def _codal_worker(base):
    """حالت کارگر: در حالت EXE، خودِ EXE نقش python را بازی میکند
    (sys.executable = مسیر همین EXE، نه python.exe).

      BorsTerminal_Ultimate.exe --codal-worker <mode>     → CLI واقعی codal_fetcher
      BorsTerminal_Ultimate.exe --codal-worker watchlist → fetch_symbol برای واچ‌لیست

    این شاخه باید قبل از uvicorn اجرا شود و سریع خارج شود. هیچ منطقی
    کپی نمیشود: حالت sync از runpy.run_path روی همان codal_fetcher.py که
    به‌صورت دیتا در _MEIPASS همراه میشود، با run_name="__main__" اجرا
    میکند تا بلوک CLI واقعی همان فایل کار کند."""
    import runpy
    # ویندوز stdout/stderr را cp1252 میکند؛ نام فارسی نمادها در print کرش
    # UnicodeEncodeError میداد → reconfigure با errors="replace".
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    kind = sys.argv[2] if len(sys.argv) > 2 else ""
    # قبل از هر اتصال به دیتابیس، market.db باید از market.db.lzma استخراج
    # شده باشد؛ وگرنه sqlite3.connect خودش یک فایل خالی میسازد و بعد
    # ensure_market_db آن را «قبلاً موجود» فرض میکند → برنامه بدون داده.
    import bors_config
    bors_config.ensure_market_db(verbose=False)
    if kind == "watchlist":
        import sqlite3, codal_fetcher, watchlist_store
        conn = sqlite3.connect(codal_fetcher.DB_PATH, timeout=30)
        try:
            watchlist_store.ensure_table(conn)
            syms = [r["symbol"] for r in watchlist_store.list_rows(conn) if r.get("symbol")]
        finally:
            conn.close()
        print("watchlist sync:", len(syms), "symbols", flush=True)
        for s in syms:
            codal_fetcher.fetch_symbol(s)
        return
    # نگاشت mode → آرگومانهای CLI واقعی codal_fetcher.py (یک منبع واحد).
    from codal_engine import _SYNC_MODES
    argv = _SYNC_MODES.get(kind)
    if not argv:
        print("[codal-worker] unknown mode:", kind, file=sys.stderr)
        raise SystemExit(2)
    script = os.path.join(base, "codal_fetcher.py")
    if not os.path.exists(script):
        print("[codal-worker] codal_fetcher.py not found:", script, file=sys.stderr)
        raise SystemExit(3)
    sys.argv = ["codal_fetcher.py"] + argv
    runpy.run_path(script, run_name="__main__")

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
    # حالت کارگر: EXE خودش به‌عنوان جایگزین python برای subprocessهای codal
    # استفاده میشود (در حالت frozen، sys.executable همین EXE است).
    # قبل از هر چیز دیگری بررسی میشود تا uvicorn اجرا نشود.
    if len(sys.argv) > 1 and sys.argv[1] == '--codal-worker':
        _base = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(__file__))
        _codal_worker(_base)
        raise SystemExit(0)
    main()
