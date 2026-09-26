#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/fund_kind_boundary_probe.py — چه تعداد صندوق با قاعدهٔ «کلید = کلمه» عوض می‌شوند؟

پیش از این `fund_kind` با `k in name` می‌گشت؛ «معيار» شامل «عيار» بود، پس
«صندوق س.كالاي ديباي معيار» (کالا) و «آواي معيار-س» (سهامی) «طلا» می‌شدند.
این اسکریپت همان مقایسهٔ قبل/بعد را روی بانکِ واقعی می‌شمارد و ردیف‌های
تغییر‌یافته را چاپ می‌کند تا «درست‌شدن» با «خراب‌شدنِ چیز دیگر» اشتباه نشود.

اجرا:  python tools/fund_kind_boundary_probe.py [--db market.db]
"""
import argparse
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mstat_engine as ME  # noqa: E402

# کلیدواژه‌هایِ دقیقِ نسخهٔ پیش از این تغییر (زیررشتهٔ خام، بی‌قاعدهٔ کلمه).
# این‌جا دستِ‌نویس نگه داشته شده تا «قبل» واقعاً همان کدِ قبلی باشد، نه
# برگشتِ `ME._FUND_KINDS` که حالا عوض شده است.
_OLD_KINDS = (
    ("lev",    ("اهرم", "اهرمي", "اهرام")),
    ("gold",   ("طلا", "طلایی", "Gold", "ياره", "گلگشت", "عيار", "ثروت آفرين")),
    ("silver", ("نقره", "سيور")),
    ("fixed",  ("درآمد ثابت", "درامد ثابت", "ثابت", "اقتدار", "ادوار", "آهنگ")),
    ("mixed",  ("مختلط",)),
    ("commod", ("كالا", "کالا", "پتروشيمه", "فلزات")),
    ("fof",    ("در صندوق",)),
    ("equity", ("سهام", "سهامی", "بخش", "شاخص", "جسوران", "تضمین", "تامين",
                "پروژه", "مشترك", "مشترک", "اعتبارسهام")),
)


def _old_kind(l_val30, l_val18):
    """همان fund_kindِ پیش از قاعدهٔ کلمه (زیررشتهٔ خام)."""
    name = (l_val30 or "") + " " + (l_val18 or "")
    for kind, keys in _OLD_KINDS:
        for k in keys:
            if k and k in name:
                return kind
    tail = (l_val30 or "").rstrip()
    if tail.endswith("-د"):
        return "fixed"
    if tail.endswith("-س") or tail.endswith("-ب"):
        return "equity"
    return "etf"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="market.db")
    ap.add_argument("--limit", type=int, default=25)
    a = ap.parse_args()
    conn = sqlite3.connect(a.db)
    rows = conn.execute(
        "SELECT l_val18, l_val30, sector_name, paper_type FROM instruments").fetchall()
    funds = []
    for sym, name, sector, pt in rows:
        cls, _k = ME.classify(pt, name or "", sym or "", sector or "")
        if cls == ME.PAPER_FUND:
            funds.append((sym, name or ""))
    changed = [(s, n, _old_kind(n, s), ME.fund_kind(n, s)) for s, n in funds
               if _old_kind(n, s) != ME.fund_kind(n, s)]
    from collections import Counter
    print(f"صندوق‌ها: {len(funds)}   تغییرطبقه: {len(changed)}")
    print("توزیعِ تازه: " + str(Counter(ME.fund_kind(n, s) for s, n in funds).most_common()))
    print("توزیعِ قبلی: " + str(Counter(_old_kind(n, s) for s, n in funds).most_common()))
    for s, n, before, after in changed[:a.limit]:
        print(f"  {s:10s} {before:7s} → {after:7s}  {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
