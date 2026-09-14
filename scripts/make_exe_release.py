# -*- coding: utf-8 -*-
"""
make_exe_release.py — ریلیز EXE هوشمند: EXE + DB ها + فایل‌های جانبی در یک ZIP فشرده
    releases/BorsTerminal_Ultimate_v<ver>_exe.zip
    ├── BorsTerminal_Ultimate.exe     (EXE هوشمند: پیش‌اجرا + کتابخانه‌ها — بدون DB)
    ├── market.db                     (66MB → در ZIP ~25MB)
    ├── codal.db
    ├── adb_config.json / codal_control.json
    └── README.txt (راهنمای کوتاه: unzip همه کنار هم → اجرای EXE)
"""
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repo root
RELEASES = os.path.join(ROOT, "releases")

def cur_version():
    src = open(os.path.join(ROOT, "static", "index.html"), encoding="utf-8").read()
    m = re.findall(r"v=(\d+\.\d+\.\d+)", src)
    return m[-1] if m else "0.0.0"

def main():
    ver = cur_version()
    out = os.path.join(RELEASES, f"BorsTerminal_Ultimate_v{ver}_exe.zip")
    # ONEDIR build: پوشهٔ dist/BorsTerminal_Ultimate (برخلاف onefile — با ZIP خیلی فشرده‌تر)
    exe_dir = os.path.join(ROOT, "dist", "BorsTerminal_Ultimate")
    exe = os.path.join(exe_dir, "BorsTerminal_Ultimate.exe")
    if not os.path.exists(exe):
        print("[ERR] dist/BorsTerminal_Ultimate/BorsTerminal_Ultimate.exe missing - run build_exe.py first")
        sys.exit(1)

    readme = """BorsTerminal_Ultimate v{ver} - EXE smart release
=================================================
HOW TO RUN (one time):
  1. Extract THIS ZIP to ANY folder (keep ALL files together in one folder).
     (folder contains BorsTerminal_Ultimate.exe + _internal/ libs)
  2. Double-click BorsTerminal_Ultimate.exe
     > It checks prerequisites itself (libraries are INSIDE the exe folder).
     > It reads market.db from the SAME folder.
     > Opens your browser at http://localhost:8001 automatically.

WHAT IS INSIDE:
  - BorsTerminal_Ultimate/    -> Python runtime + all libraries (self-contained, offline)
  - market.db.lzma            -> TSETMC + Codal data (EXE decompress it on first run)
  - adb_config.json / codal_control.json -> runtime config

TIP: don't delete market.db next to the exe - that's your data.

COMPAT NOTE (Amir PC): works WITHOUT any installed Python. numpy is pinned to
2.0.2 (baseline SSE2) so old CPUs without SSE4.2/X86_V2 run it fine.
""".format(ver=ver)

    files = [
        (exe_dir, "BorsTerminal_Ultimate"),      # کل پوشه onedir (exe + _internal)
        ("market.db", "BorsTerminal_Ultimate/market.db.lzma"),   # DB کنار EXE که bors_entry می‌گردد
        ("adb_config.json", "BorsTerminal_Ultimate/adb_config.json"),
        ("codal_control.json", "BorsTerminal_Ultimate/codal_control.json"),
        ("bootstrap_first_run.py", "BorsTerminal_Ultimate/bootstrap_first_run.py"),
    ]
    if os.path.exists(out):
        os.remove(out)
    # market.db.lzma پایه دادهٔ ریلیز — سیاست v10: بازسازی فقط با تغییر اسکیما
    # (رفرش‌های صرفاً دیتایی/سینک روزانه lzma را نوشتن نمیکنند)
    import hashlib
    import lzma
    import sqlite3
    db = os.path.join(ROOT, "market.db")
    lzma_path = os.path.join(ROOT, "market.db.lzma")
    marker = os.path.join(RELEASES, "market_db_schema.sha")

    def _schema_fingerprint(path):
        # انگشت ساختار: DDL جدولها/نمایهوا + user_version (بدون دیتا)
        con = sqlite3.connect(path)
        try:
            rows = con.execute(
                "SELECT type, name, sql FROM sqlite_master "
                "ORDER BY type, name, sql").fetchall()
            uv = con.execute("PRAGMA user_version").fetchone()[0]
        finally:
            con.close()
        return hashlib.sha256(repr((rows, uv)).encode("utf-8")).hexdigest()

    if os.path.exists(db):
        fp = _schema_fingerprint(db)
        prev = ""
        if os.path.exists(marker):
            prev = open(marker, encoding="utf-8").read().strip()
        if not os.path.exists(lzma_path):
            reason = "lzma missing"
        elif fp != prev:
            reason = "schema change (%s -> %s)" % (prev[:8] or "none", fp[:8])
        else:
            reason = ""
        if reason:
            print("  [..]  (re)building market.db.lzma from CURRENT market.db [%s]" % reason)
            os.makedirs(RELEASES, exist_ok=True)
            with open(db, "rb") as fi, open(lzma_path, "wb") as fo:
                fo.write(lzma.compress(fi.read(), preset=lzma.PRESET_EXTREME))
            open(marker, "w", encoding="utf-8").write(fp + "\n")
        else:
            print("  [=]   market.db.lzma unchanged (schema fingerprint matched)")

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for src, dst in files:
            if os.path.isdir(src):
                # کل پوشه را recursiv بنویس (ریشهٔ ZIP صاف)
                for dirpath, dirnames, filenames in os.walk(src):
                    for fn in filenames:
                        full = os.path.join(dirpath, fn)
                        rel = os.path.relpath(full, os.path.dirname(src))
                        zf.write(full, rel)
                print(f"  + {dst}/  ({round(sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(src) for f in fs)/1048576,1)} MB)")
                continue
            full = os.path.join(ROOT, src if src != "market.db" else "market.db.lzma")
            if os.path.exists(full):
                zf.write(full, dst)
                print(f"  + {dst}  ({round(os.path.getsize(full)/1048576,1)} MB)")
        zf.writestr("README.txt", readme)
        print("  + README.txt")
    print()
    print(f"✅ {out}")
    print(f"   size: {round(os.path.getsize(out)/1048576,1)} MB  (EXE inside: {round(os.path.getsize(exe)/1048576,1)} MB)")

if __name__ == "__main__":
    main()
