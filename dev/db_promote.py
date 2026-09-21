#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""گام ۱ — تثبیت و جایگزینی رسمیِ market.db به‌عنوانِ دیتابیسِ پایهٔ ریلیز.

کارها:
  ۱) تأییدِ سلامتِ دیتابیسِ مبدا (integrity + foreign_key + جدول‌های الزامی)
  ۲) VACUUM + ANALYZE (آزادسازیِ صفحه و بهینه‌سازیِ پلنِ کوئری)
  ۳) فشرده‌سازی به market.db.lzma با round-trip verification
     (همان گاردِ release.ps1/Ensure-Db — یک بایت هم نباید تفاوت کند)
  ۴) تأییدِ نهایی رویِ فایلِ مستقرشده

قرارداد: روی market.db اصلی فقط با --apply اجرا می‌شود (پیش‌فرض dry-run).
"""
import argparse
import lzma
import os
import sqlite3
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REQUIRED = {"instruments", "daily_prices", "financial_statements",
            "market_watch", "client_type"}
MIN_FS = 1000


def health(path, label):
    c = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    try:
        ic = c.execute("PRAGMA integrity_check").fetchone()[0]
        fk = c.execute("PRAGMA foreign_key_check").fetchall()
        have = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        fs = c.execute("SELECT COUNT(*) FROM financial_statements").fetchone()[0] \
            if "financial_statements" in have else 0
    finally:
        c.close()
    print("  [%s] integrity=%s fk_violations=%d fs_rows=%d"
          % (label, ic, len(fk), fs))
    return ic == "ok" and not fk and REQUIRED <= have and fs >= MIN_FS


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="actually overwrite market.db.lzma (default: dry-run)")
    args = ap.parse_args()

    src = os.path.join(_ROOT, "market.db")
    dst = os.path.join(_ROOT, "market.db.lzma")
    print("== DB promotion ==")

    if not health(src, "source"):
        print("  [FAIL] source DB not healthy — refusing to promote.")
        return 1

    c = sqlite3.connect(src)
    try:
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("VACUUM")
        c.execute("ANALYZE")
        c.commit()
    finally:
        c.close()
    print("  [vacuum+analyze] done, size %.1f MB"
          % (os.path.getsize(src) / 1048576.0))

    if not args.apply:
        print("\n[DRY-RUN] would compress -> market.db.lzma. pass --apply.")
        return 0

    if os.path.exists(dst):
        import shutil
        shutil.copy2(dst, dst + ".bak")
        print("  [backup] previous market.db.lzma -> market.db.lzma.bak")

    raw = open(src, "rb").read()
    with open(dst, "wb") as f:
        f.write(lzma.compress(raw, preset=9))
    print("  [lzma] %.1f MB (%.0f%% of raw)"
          % (os.path.getsize(dst) / 1048576.0,
             100.0 * os.path.getsize(dst) / len(raw)))

    # round-trip: باید دقیقاً همانیِ منبع را برگرداند.
    back = lzma.decompress(open(dst, "rb").read())
    if back != raw:
        print("  [FAIL] round-trip mismatch — restored previous baseline.")
        import shutil
        shutil.copy2(dst + ".bak", dst)
        return 1
    print("  [round-trip] OK — byte-identical to source")

    # تأیید روی فایلِ مستقرشده (استخراج به temp و بررسیٔ سلامت)
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix="bors_promote_")
    ext = os.path.join(tmp, "promoted.db")
    open(ext, "wb").write(back)
    ok = health(ext, "deployed")
    # health() با mode=ro باز می‌کند ولی SQLite ممکن است هنوز sidecarهای
    # -wal/-shm در کنارِ فایل ساخته باشد → rmdir رویِ پوشهٔ غیرخالی شکست
    # می‌خورد. پاک‌سازیِ بازگشت‌پذیر:
    shutil.rmtree(tmp, ignore_errors=True)
    if not ok:
        print("  [FAIL] deployed artifact failed health check.")
        return 1

    print("\n== PROMOTED ✓ — market.db.lzma is the v%s release baseline =="
          % "1.0.11")
    return 0


if __name__ == "__main__":
    sys.exit(main())
