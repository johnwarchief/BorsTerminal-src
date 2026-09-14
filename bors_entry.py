# -*- coding: utf-8 -*-
"""لاانچر EXE: پیش‌اجرا + uvicorn + باز کردن مرورگر"""
import os, sys, threading, time, webbrowser, socket, subprocess

# در حالت EXE (frozen): کتابخانه‌ها/دیتاها داخل _MEIPASS (onedir: _internal)؛
# DB ها کنار exe (از ZIP یا market.db.lzma) -- cwd همان پوشه exe می‌شود.
if getattr(sys, 'frozen', False):
    BASE = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    WORK = os.path.dirname(sys.executable)
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

def main():
    port = int(os.environ.get('BORS_PORT', '8001'))
    for p in (port,):
        if port_open(p):
            print(f'[OK] Server already running on {p} -> open browser')
            webbrowser.open(f'http://localhost:{p}')
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
        webbrowser.open(f'http://localhost:{port}')
    else:
        print('[ERR] server did not start')
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
