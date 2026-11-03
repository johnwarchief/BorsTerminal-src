#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/bors_fixture_db.py — درگاهِ یگانۀ گاردها به `market.db`ِ گیت‌ایگنور.

چرا لازم شد (رأیِ مالک ۲۰۲۶-۱۰-۱۷، بند B): درِ worktree‌ای که `market.db` ندارد،
دوازده گارد به‌جای SKIP **می‌ترکند** (`no such table: financial_statements`).
سازوکارِ بازتولیدشده: `sqlite3.connect(path)` اگر فایل نباشد آن را **صفر‌بایت
می‌سازد**؛ بعد درِ `os.path.exists(ROOT/"market.db")` رد می‌شود و شاخۀ SKIP هرگز
اجرا نمی‌شود. یعنی یکِ اتصالِ بی‌بررسی، هم بانکِ دروغین می‌سازد هم پانزده گارد
را قرمز می‌کند.

سه قاعدهٔ همین ماژول همان رأی است:
  ۱) هیچ‌وقت نمی‌سازد — کوئریِ سلامت رویِ `file:…?mode=ro` است؛
  ۲) «هست» یعنی **جداولِ لازم را دارد**، نه «فایل هست»؛
  ۳) SKIP بی‌صدا ممنوع: یا بانکِ کامل هست، یا فراخوان باید صریح بگوید کدامِ
     بند، با کدامِ علت، و چند تا.

اجرایِ مستقیم = خودِ آزمون: رویِ یکِ بانکِ صفر‌بایتِ ساختگی باید `None` بدهد و
هیچ فایلی نسازد.
"""
from __future__ import annotations

import os
import sqlite3

#: جدول‌هایی که «بانکِ کاریِ واقعی» باید داشته باشد تا بندهایِ رویِ داده معنا
#: داشته باشند (کمبودِ یکی = بانکِ نیمه‌ساز یا صفر‌بایت).
REQUIRED_TABLES = ("instruments", "financial_statements", "monthly_sales")


def _candidate(root: str | None = None) -> str:
    if root:
        return os.path.join(root, "market.db")
    return "market.db"


def market_db_ro(root: str | None = None,
                 required: tuple = REQUIRED_TABLES) -> sqlite3.Connection | None:
    """اتصال **فقط‌خواندنی** به بانکِ کاری، یا None. هیچ فایلی نمی‌سازد.

    None یعنی «این بندها رویِ این ماشین اجرا نشد» — و فراخوان موظف است همان را
    با نامِ بند و علت چاپ کند، نه اینکه بی‌صدا بگذرد یا با `connect`ِ خام،
    بانکِ خالی بسازد و بعد بترکد.
    """
    path = _candidate(root)
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        return None
    try:
        conn = sqlite3.connect("file:%s?mode=ro" % path.replace("\\", "/"), uri=True)
    except sqlite3.Error:
        return None
    try:
        have = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    except sqlite3.Error:
        conn.close()
        return None
    if not set(required) <= have:
        conn.close()
        return None
    conn.row_factory = sqlite3.Row
    return conn


def note_skip(section: str, reason: str) -> int:
    """یک SKIPِ شمارش‌شونده و صریح. عددِ برگشتی را با `SKIP %d` جمع ببندید."""
    print("  SKIP  %s — %s" % (section, reason))
    return 1


def selftest(tmp: str | None = None) -> int:
    """ثابت می‌کند سنسور کور نیست: بانکِ صفر‌بایت ⇒ None، و هیچ فایلِ تازه‌ای ساخته
    نمی‌شود. بی‌این، خودِ همین ماژول می‌توانست ادعای دروغ بزند."""
    import tempfile
    root = tmp or tempfile.mkdtemp(prefix="bors_fx_selftest_")
    empty = os.path.join(root, "market.db")
    open(empty, "wb").close()
    assert market_db_ro(root) is None, "بانکِ صفر‌بایت باید None بدهد"
    os.remove(empty)
    assert market_db_ro(root) is None, "بانکِ نبود باید None بدهد"
    assert not os.path.exists(empty), "ماژول حقِ ساختنِ market.db ندارد"
    print("bors_fixture_db selftest OK (صفر‌بایت ⇒ None، نبود ⇒ None، بی‌ساختنِ فایل)")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest())
