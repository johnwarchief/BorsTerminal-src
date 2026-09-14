# -*- coding: utf-8 -*-
"""
BorsTerminal_Ultimate - First-run bootstrap (status only)

Checks prerequisites and REPORTS status only. It NEVER downloads data,
never starts scans. Use the dashboard buttons for that.
All output is ASCII English (terminal-safe).
"""
import importlib.util
import os
import subprocess
import sys

# ensure UTF-8 output regardless of console code page
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
if sys.platform == "win32":
    try:
        os.system("chcp 65001 >nul")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(ROOT, "market.db")
REQS = ["fastapi", "uvicorn", "pandas", "numpy", "requests"]
# numpy < 2.1: روی CPU های قدیمی (بدون X86_V2/SSE4.2) هم کار میکند
# — از numpy 2.1+ به بعد baseline X86_V2 اجباری است و اینجا کرش میدهد
PIN_NUMPY = "numpy==2.0.2"
PIN_PANDAS = "pandas==2.2.3"

ADB_CANDIDATES = (
    r"C:\adb\platform-tools\adb.exe",
    r"C:\adb\adb.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
)

CAMOUFOX_VENV = os.path.expandvars(
    r"%LOCALAPPDATA%\hermes\venvs\camoufox\Scripts\python.exe"
)


def _box(lines, ch="="):
    print("  " + ch * 70)
    for ln in lines:
        print("  " + ln)
    print("  " + ch * 70)


def check_all():
    print()
    _box([
        "[PRE] BorsTerminal_Ultimate - prerequisites check",
        "",
        "  Everything below is STATUS ONLY.",
        "  No scanning / downloading happens in this window.",
        "  Use the dashboard buttons for data updates.",
    ], ch="=")
    print()

    problems = 0

    # 1) Python
    py_ok = sys.version_info >= (3, 9)
    print("  [OK]  Python: %s %s" % (sys.version.split()[0],
          "" if py_ok else "- 3.9+ required"))
    if not py_ok:
        problems += 1
    # پایتون 3.13+: فقط یادآوری آرام (نه [!!]) — EXE پایتون 3.11 خودش را دارد
    if sys.version_info >= (3, 13):
        print("  [i]  Python 3.13+ — note: for the EXE path nothing is needed;")
        print("        for the code path (zip) the portable way is Python 3.11/3.12.")

    # 2) pip packages — اگر غایب بود و اینترنت هست، خودکار نصب کن
    missing = [m for m in REQS if importlib.util.find_spec(m) is None]
    # numpy — تصمیم واقعی با تست اجرا، نه با شمارهٔ نسخه:
    # numpy 2.1+ baseline X86_V2 دارد؛ اگر CPU قدیمی (بدون SSE4.2) باشد import کرش میکند
    # (Illegal instruction). پس: import موفق = CPU سازگار = مشکل نیست.
    np_ok = True
    try:
        import numpy as _np
        _npv = _np.__version__
        _maj = int(_npv.split(".")[0])
        _min = int(_npv.split(".")[1]) if len(_npv.split(".")) > 1 else 0
        if _maj > 2 or (_maj == 2 and _min >= 1):
            # import موفق شد → CPU این ماشین X86_V2 دارد → حالت کاملاً عادی
            print("  [OK]  numpy %s (X86_V2 baseline) imported — CPU is X86_V2-capable." % _npv)
        else:
            print("  [OK]  numpy %s (SSE2 baseline) — works on any CPU." % _npv)
    except Exception as _e:
        # import شکست — یا نصب نیست یا CPU بدون SSE4.2 (Illegal instruction)
        np_ok = False
        print("  [WARN] numpy import failed (%s)" % type(_e).__name__)
        print("        -> old CPU (no SSE4.2)? then: run the EXE release (bundles numpy 2.0.2)")
    if missing or not np_ok:
        problems += 1
        print("  [MISS] pip packages: %s%s" % (", ".join(missing), " + downgrade numpy" if not np_ok else ""))
        print("         trying to install automatically (needs internet)...")
        # با pin نصب کن: numpy 2.0.2 (خودکار X86_V2 نمیخواهد) — در حالت EXE این لازم نیست
        install_args = [PIN_NUMPY, PIN_PANDAS] if (not np_ok or "numpy" in missing or "pandas" in missing) else []
        install_args += [m for m in missing if m not in ("numpy", "pandas")]
        try:
            r = subprocess.run([sys.executable, "-m", "pip", "install",
                                "--disable-pip-version-check", "-q"] + install_args,
                               capture_output=True, text=True, timeout=600)
            if r.returncode == 0:
                print("  [OK]  automatically installed: %s" % ", ".join(install_args))
                problems -= 1
            else:
                print("  [FAIL] auto-install failed (no internet?)")
                print("         fix: pip install -r requirements.txt")
                # سناریوی py3.14: numpy 2.0.2/pandas 2.2.3 wheel برای 3.14 ندارند
                if sys.version_info >= (3, 14) and ("numpy" in install_args or "pandas" in install_args):
                    print("  [!!]  Python %d.%d detected: numpy 2.0.2/pandas 2.2.3 have NO wheels "
                          "for this Python." % sys.version_info[:2])
                    print("        -> Best fix: run the EXE release (bundles Python 3.11).")
                    print("        -> Or: install Python 3.11/3.12 from python.org, then run this again.")
                    print("        -> Or: pip install numpy==2.0.2 pandas==2.2.3 with that Python.")
        except Exception as e:
            print("  [FAIL] auto-install error: %s" % e)
    else:
        print("  [OK]  pip packages: " + ", ".join(REQS))

    # 3) market.db
    if os.path.isfile(DB):
        db_ok = os.path.getsize(DB) > 10_000_000
        print("  [%s]  market.db: %.1f MB %s" % (
            "OK" if db_ok else "WARN", os.path.getsize(DB) / 1e6,
            "" if db_ok else "(small - history incomplete)"))
        if not db_ok:
            problems += 1
    else:
        problems += 1
        print("  [MISS] market.db NOT FOUND")
        print("         download via dashboard: http://localhost:8001")
        print("         or: python test_tsetmc.py")

    # 4) ports
    import socket
    for port in (8001, 8000):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            busy = s.connect_ex(("127.0.0.1", port)) == 0
        if busy:
            print("  [WARN] port %d busy (another instance running?)" % port)

    # 5) ADB (optional)
    adb = next((p for p in ADB_CANDIDATES if os.path.isfile(p)), None)
    if adb:
        try:
            out = subprocess.run([adb, "devices"], capture_output=True,
                                 text=True, timeout=10)
            devs = [l for l in out.stdout.splitlines()
                    if "\tdevice" in l and not l.startswith("List")]
            if devs:
                print("  [OK]  ADB: %d device(s) connected" % len(devs))
            else:
                print("  [WARN] ADB installed but phone NOT connected")
                print("         (optional) phone + USB debugging + tethering")
        except Exception as e:
            print("  [WARN] ADB error: %s" % e)
    else:
        print("  [WARN] ADB not installed - no IP rotation")
        print("         (optional) C:\\adb\\platform-tools, or Android platform-tools")

    # 6) Camoufox (optional)
    if os.path.isfile(CAMOUFOX_VENV):
        print("  [OK]  Camoufox venv found - browser-based Codal scan")
    else:
        print("  [WARN] Camoufox not installed - Codal scan via requests (slower)")

    print()
    if problems:
        _box([
            "[FIX] %d problem(s) to resolve before full use" % problems,
            "  After fixing, run this launcher again.",
            "  Data download is done from the dashboard buttons,",
            "  not from this terminal window.",
        ], ch="-")
        return 1
    _box([
        "[READY] All prerequisites OK.",
        "",
        "  Starting dashboard ...",
        "  URL: http://localhost:8001",
        "  (browser opens automatically)",
    ], ch="=")
    return 0


if __name__ == "__main__":
    sys.exit(check_all())
