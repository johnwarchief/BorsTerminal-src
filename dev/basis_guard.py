# -*- coding: utf-8 -*-
"""dev/basis_guard.py — نگهبانِ «تنظیمِ مبنایِ قیمت دستِ هیچ سوئیتی نرود»

`price_basis.set_basis()` تنها نویسندهٔ `price_basis.json` است. اگر سوئیتی آن را
بی‌`dev/basis_sandbox.py` صدا بزند، فایل رویِ آخرین مقدار می‌ماند و چارتِ هر اجرایِ
بعدی بی‌صدا با مبنایِ دیگری عدد می‌دهد. سنجشِ ۱۴۰-۰۷-۲۷: پس ازِ گیت `closing`
مانده بود وِ درِ فولاد ۵۰۲ از ۶۰۱ بستۀِ خام با منبعِ رسمی فرق داشت — یعنی همهٔ
سنجش‌هایِ بعدی رویِ تنظیمِ خرابِ یک تستِ دیگر خوانده می‌شد.

`run_all_tests.py` پیش و پس ازِ هر سوئیت `check()` را صدا می‌زند: تغییر = قرمزکردنِ
همان سوئیت به‌نام + بازگرداندنِ فایل.
"""
from __future__ import annotations

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "price_basis.json")


def snapshot():
    """متنِ تنظیمِ فعلی؛ None یعنی فایل نیست (پیش‌فرضِ قرارداد جاری است)"""
    try:
        with open(PATH, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def check(label: str, before, word: str = "FAIL") -> bool:
    """True اگر تنظیم دست‌نخورده مانده باشد؛ وگرنه قرمز + بازگردانی.

    `word` برایِ خودآزمون «caught» می‌شود: آن تغییرِ عمدی است و اگر همان «FAIL»
    چاپ شود، شمارشگرِ گیت (`dev/guard_counts.py`) آن را خطایِ سوئیت می‌شمارد، در
    حالی که خطا را گرفتنِ نگهبان درست همین است.
    """
    after = snapshot()
    if after == before:
        return True
    print("  %s %-40s (تنظیمِ price_basis.json را عوض کرد: %r → %r)"
          % (word, label, (before or "").strip()[:40], (after or "").strip()[:40]))
    try:
        if before is None:
            if os.path.exists(PATH):
                os.remove(PATH)
        else:
            with open(PATH, "w", encoding="utf-8", newline="") as f:
                f.write(before)
        print("       ↳ بازگردانده شد")
    except OSError as ex:
        print("       ↳ بازگردانی نشد: %s" % ex)
    return False


def selftest() -> int:
    """سنجشِ خودِ سنسور: اگر تغییر را نبیند، نگهبان کور است"""
    before = snapshot()
    try:
        with open(PATH, "w", encoding="utf-8", newline="") as f:
            f.write('{\n  "basis": "closing"\n}\n')
        caught = not check("selftest mutator", before, word="caught")
        restored = snapshot() == before
        n_fail = 0 if (caught and restored) else 1
        print("basis_guard: %d_pass / %d_fail  "
              "(تغییرِ تنظیم دیده شد=%s، فایل بازگردانده شد=%s)"
              % (2 - n_fail, n_fail, caught, restored))
        return 0 if n_fail == 0 else 1
    finally:
        if before is None:
            if os.path.exists(PATH):
                os.remove(PATH)
        else:
            with open(PATH, "w", encoding="utf-8", newline="") as f:
                f.write(before)


if __name__ == "__main__":
    raise SystemExit(selftest())
