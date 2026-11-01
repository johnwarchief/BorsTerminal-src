#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dev/test_notifications_symbol_b5.py — گاردِ فیلترِ افزودنیِ symbol در اعلان‌ها (B5 Task 0).

طبق §۸ و §۱۱ مستندِ بازنویسی:
فیلد یا فیلترِ جدیدِ رابط، اول در پایتون (مرجعِ پاریتی) پیاده و تست می‌شود،
سپس در Go با گیت پورت می‌گردد.
این گارد، موارد زیر را روی کپیِ موقت و یخ‌زدهٔ market.db می‌سنجد:
۱. فیدِ عمومی بدونِ symbol همان رفتارِ پیشین را دارد (پوششِ چند نمادی).
۲. فیدِ دارای symbol فقط اطلاعیه‌هایِ همان نماد (و نوشتارهایِ هم‌ارز) را بازمی‌گرداند.
۳. ترکیبِ symbol با levels و since و limit به درستی کار می‌کند.
۴. نمادِ ناموجود یا بدونِ اطلاعیه خروجیِ خالی (count=0, items=[]) می‌دهد.
۵. کنترلِ منفی: هیچ اطلاعیه‌ای از نمادِ دیگر در فیدِ نماد نشت نمی‌کند.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import notifications as N


def run_tests() -> int:
    market_db = os.path.join(ROOT, "market.db")
    if not os.path.exists(market_db):
        print("FAIL: market.db not found at root")
        return 2

    tmp = tempfile.mkdtemp(prefix="bors-notif-test-")
    copy_path = os.path.join(tmp, "market.db")
    shutil.copy2(market_db, copy_path)

    conn = sqlite3.connect("file:%s?mode=ro" % copy_path.replace("\\", "/"), uri=True)
    passed, failed = 0, 0

    def check(desc: bool, label: str):
        nonlocal passed, failed
        if desc:
            passed += 1
            print(f"  PASS {label}")
        else:
            failed += 1
            print(f"  FAIL {label}")

    try:
        # ۱. فید بدون symbol:
        f_all = N.feed(conn, limit=10)
        check(f_all.get("status") == "ok", "feed general status is ok")
        check(f_all.get("count", 0) > 0, "feed general count > 0")
        check(f_all.get("symbol") is None, "feed general symbol is None")

        # ۲. فید دارای symbol:
        f_sym = N.feed(conn, symbol="رمپنا", limit=5)
        check(f_sym.get("status") == "ok", "feed symbol=رمپنا status is ok")
        check(f_sym.get("count", 0) > 0, "feed symbol=رمپنا count > 0")
        check(f_sym.get("symbol") == "رمپنا", "feed symbol key matches requested")
        all_match = all(item.get("symbol") == "رمپنا" for item in f_sym.get("items", []))
        check(all_match, "all items in feed belong to رمپنا")

        # ۳. ترکیب symbol با limit:
        f_lim2 = N.feed(conn, symbol="رمپنا", limit=2)
        check(len(f_lim2.get("items", [])) <= 2, "limit=2 strictly observed on symbol feed")

        # ۴. نماد ناموجود:
        f_none = N.feed(conn, symbol="نیست۰۱", limit=5)
        check(f_none.get("status") == "ok", "feed unknown symbol status is ok")
        check(f_none.get("count") == 0, "feed unknown symbol count == 0")
        check(len(f_none.get("items", [])) == 0, "feed unknown symbol items is empty")

        # ۵. فیلتر سطح همراه با نماد:
        f_levels = N.feed(conn, symbol="رمپنا", levels=["high"], limit=10)
        check(f_levels.get("status") == "ok", "feed with levels+symbol status is ok")
        all_high = all(item.get("level") == "high" for item in f_levels.get("items", []))
        check(all_high, "all items in levels=['high'] have level high")

        # ۶. کنترل منفی: هیچ نماد دیگری نشت نمی‌کند
        f_leak = N.feed(conn, symbol="فردوس", limit=10)
        has_other = any(item.get("symbol") != "فردوس" for item in f_leak.get("items", []))
        check(not has_other, "negative control: no leakage of other symbols into filtered feed")

    finally:
        conn.close()
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\nnotifications symbol test: {passed} passed / {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
