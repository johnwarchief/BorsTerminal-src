# -*- coding: utf-8 -*-
"""make_patch.py — سازندهٔ پچ بهروزشوندهٔ ماژولار BorsTerminal_Ultimate (v10)

خروجی: dist/BorsTerminal_Update.zip — یک پچ «رویهمگذاری» flat که باید
دقیقاً روی پوشهٔ نصب فعلی extract شود (ریشهٔ zip == ریشهٔ نصب).

قاعدهٔ طلایی: وضعیت کاربر هرگز داخل پچ سفر نمیکند — market.db/market.db.lzma،
adb_config.json، codal_control.json، codal_state.json، sync*.json، لاگها و کشها
حذف میشوند تا اعمال بهروزرسانی هیچوقت دیتابیس/تنظیمات تترینگ کاربر را له نکند.

apply_update.bat هم در ریشهٔ zip قرار میگیرد؛ کافیست کاربر آن را کنار zip
اجرا کند: توقف نرم برنامه → extract درجا → مهر Version.txt → اجرای دوباره.

اجرا:  python scripts/make_patch.py          (بعد از scripts/build_exe.py)
"""
import datetime
import os
import re
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
DIST = os.path.join(ROOT, "dist", "BorsTerminal_Ultimate")
OUT = os.path.join(ROOT, "dist", "BorsTerminal_Update.zip")
BAT = os.path.join(ROOT, "scripts", "apply_update.bat")

# وضعیت/تنظیمات کاربر: هرگز داخل پچ نمیآیند
EXCLUDE_FILES = {
    "market.db", "market.db.lzma", "adb_config.json", "codal_control.json",
    "codal_state.json", "market_sync.json", "sync_status.json",
    "sync_ondemand.json", "sync_summary.json", "fts_update_state.json",
}
EXCLUDE_EXT = {".db", ".db-shm", ".db-wal", ".lzma", ".log", ".pyc", ".pyo",
               ".tmp", ".bak", ".err", ".out"}
EXCLUDE_DIRS = {"__pycache__", "logs", ".pytest_cache", "WT"}


def app_version():
    src = open(os.path.join(ROOT, "static", "index.html"), encoding="utf-8").read()
    m = re.findall(r"v=(\d+\.\d+\.\d+)", src)
    return m[-1] if m else "0.0.0"


def git_short():
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8")
        return (r.stdout or "").strip() or "unknown"
    except OSError:
        return "unknown"


def main():
    exe = os.path.join(DIST, "BorsTerminal_Ultimate.exe")
    if not os.path.exists(exe):
        print("[ERR] %s missing - run scripts/build_exe.py first" % exe)
        sys.exit(1)
    bat = open(BAT, "rb").read()
    if b"\r\n" not in bat:
        print("[ERR] apply_update.bat must keep CRLF line endings")
        sys.exit(1)

    version, sha = app_version(), git_short()
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    version_txt = "app_version=%s\ngit_commit=%s\nbuilt=%s\n" % (version, sha, stamp)

    if os.path.exists(OUT):
        os.remove(OUT)
    kept = skipped = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for dirpath, dirnames, filenames in os.walk(DIST):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            for fn in filenames:
                if fn in EXCLUDE_FILES or os.path.splitext(fn)[1].lower() in EXCLUDE_EXT:
                    skipped += 1
                    continue
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, DIST).replace("\\", "/")
                zf.write(full, rel)
                kept += 1
        zf.writestr("Version.txt", version_txt)
        zf.writestr("apply_update.bat", bat)

    print("patch  : %s" % OUT)
    print("version=%s commit=%s files=%d skipped_user_state=%d size=%.1f MB"
          % (version, sha, kept + 2, skipped, os.path.getsize(OUT) / 1048576))


if __name__ == "__main__":
    main()
