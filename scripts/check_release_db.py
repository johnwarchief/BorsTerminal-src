#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اعتبارسنجی و فشرده‌سازیِ market.db به‌عنوانِ baseline ریلیز.

قرارداد: اگر این اسکریپت با کدِ غیرِ صفر خارج شود، release.ps1 باید
متوقف شود و market.db.lzmaیِ commit‌شده دست‌نخورده بماند.

چرا یک فایلِ جدا: release.ps1 این منطق را به‌صورتِ اسکریپتِ درون‌خطی با
کوتیشنِ دوتایی اجرا می‌کرد، و PowerShell 5.1 کوتیشنهایِ جاسازی‌شده را
هنگامِ فراخوانیِ EXE بومی می‌بلعد:
    d=open(market.db.lzma,rb).read()   ← NameError: name 'market' is not defined
    print(                              ← SyntaxError: '(' was never closed
یعنی هر سه مرحلهٔ اعتبارسنجی/فشرده‌سازی/round-trip در عمل هرگز کار
نمی‌کردند و فقط بهخاطرِ همان خطایِ نحوی، ریلیز با یک پیامِ گمراه‌کننده
متوقف می‌شد. انتقال به فایل، این طبقهٔ باگ را کلاً حذف می‌کند.

حالت‌ها:
    python scripts/check_release_db.py             # فقط اعتبارسنجی
    python scripts/check_release_db.py --pack      # اعتبارسنجی + فشرده‌سازی
"""
import argparse
import lzma
import os
import shutil
import sqlite3
import sys

REQUIRED = {"instruments", "daily_prices", "financial_statements"}
MIN_FS = 1000


def validate():
    """کدِ غیرِ صفر اگر دیتابیسِ منبع برایِ ریلیز مناسب نیست."""
    try:
        cur = sqlite3.connect("file:market.db?mode=ro", uri=True)
        have = {r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        fs = cur.execute(
            "SELECT COUNT(*) FROM financial_statements").fetchone()[0] \
            if "financial_statements" in have else 0
        cur.close()
    except Exception as e:
        print("SRC_BAD: %r" % e)
        return 1

    miss = sorted(REQUIRED - have)
    if miss:
        print("SRC_INCOMPLETE missing=%s" % ",".join(miss))
        return 1
    if fs < MIN_FS:
        print("SRC_TOO_SMALL financial_statements rows=%d" % fs)
        return 1
    print("SRC_OK financial_statements rows=%d" % fs)
    return 0


def pack():
    """فشرده‌سازی + round-trip verification. baseline قبلی حفظ می‌شود."""
    src = "market.db"
    dst = "market.db.lzma"
    if not os.path.exists(src):
        print("[pack] market.db not found (skip)")
        return 0

    if os.path.exists(dst):
        shutil.copy2(dst, dst + ".bak")
        print("[pack] backed up previous market.db.lzma -> market.db.lzma.bak")

    raw = open(src, "rb").read()
    # اتمی: رویِ .new فشرده می‌کنیم، round-trip را همان‌جا می‌سنجیم و فقط بعد
    # جای baseline می‌گذاریم. پیش از این، باز کردنِ dst با "wb" فایلِ
    # commit‌شده را همان اولِ کار صفر بایت می‌کرد؛ یک Ctrl+C (یا کرش) وسطِ
    # فشرده‌سازی، بیس‌لاینِ ریلیز را نابود می‌کرد — و در run بعدی همان فایلِ
    # صفر‌بایتی رویِ .bakِ سالم کپی می‌شد، یعنی مسیرِ از‌دست‌رفتنِ کامل.
    tmp = dst + ".new"
    with open(tmp, "wb") as f:
        f.write(lzma.compress(raw, preset=9))
    print("  lzma MB %.1f" % (os.path.getsize(tmp) / 1048576.0))

    # round-trip: باید دقیقاً همانیِ منبع را برگرداند؛ وگرنه baselineیِ
    # قبلی دست‌نخورده می‌ماند.
    ok = lzma.decompress(open(tmp, "rb").read()) == raw
    if not ok:
        os.remove(tmp)
        print("[pack] round-trip mismatch — baseline left untouched")
        return 1
    os.replace(tmp, dst)
    print("  round-trip OK")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pack", action="store_true",
                    help="also compress market.db -> market.db.lzma")
    args = ap.parse_args()
    rc = validate()
    if rc:
        return rc
    return pack() if args.pack else 0


if __name__ == "__main__":
    sys.exit(main())
