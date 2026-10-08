# -*- coding: utf-8 -*-
"""dev/user_watchlist_v1.py — گاردِ CRUDِ واچ‌لیستِ کاربر (رویِ بانکِ موقت)

چرا این گارد هست: `POST /api/watchlist` برایِ هر نمادِ **نو** با خطایِ
`'NoneType' object has no attribute 'keys'` برمی‌گشت — `watchlist_store.get()`
ردیفِ نبودن را به `_row(None)` می‌داد. هیچ‌کس نفهمیده بود چون رابطِ React هرگز
این endpoint را صدا نمی‌زد (ممیزیِ ۱۴۰۵-۰۷-۱۶) و مصرف‌کنندۀ قدیمی
(`archive/legacy_static/selection.js`) از بیلد بیرون است. یعنی «CRUD کامل» بودنِ
یک endpoint با خواندنِ کدش ثابت نمی‌شود؛ با زدنش ثابت می‌شود.

اجرا:  python dev/user_watchlist_v1.py
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import fts_engine  # noqa: E402
import watchlist_store as WS  # noqa: E402

FAILED: list[str] = []


def ck(cond: bool, msg: str) -> None:
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILED.append(msg)


def main() -> int:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        WS.ensure_table(conn)

        ck(WS.get(conn, "نیست") is None,
           "۱) پرسیدنِ نمادِ نبود باید None بدهد، نه AttributeError (ریشۀ باگِ POST)")

        rec = WS.add(conn, "فولاد", name="فولاد مبارکه")
        conn.commit()
        ck(rec is not None and rec["symbol"] == "فولاد", "۲) افزودنِ نمادِ نو ردیف می‌سازد")

        again = WS.add(conn, "فولاد", name="")
        conn.commit()
        ck(again["name"] == "فولاد مبارکه",
           "۳) افزودنِ دوباره با نامِ خالی نامِ پیشین را پاک نمی‌کند")
        ck(WS.count(conn) == 1, "۴) upsert با کلیدِ نرمال، ردیفِ تکراری نمی‌سازد")

        WS.add(conn, "داريك", name="")
        conn.commit()
        ck(WS.count(conn) == 2, "۵) املایِ عربی/فارسی همان دو ردیف است (ي عربی ≠ ی فارسی نیست)")
        ck(WS.get(conn, fts_engine.norm_fa("داریک")) is not None,
           "۶) کلیدِ lookup نرمال است، پس نوشتارِ دیگر همان ردیف را پیدا می‌کند")

        rows = WS.list_rows(conn)
        ck(len(rows) == 2 and all({"symbol", "name", "note", "added_at", "norm"} <= set(r) for r in rows),
           "۷) list_rows همان پنج ستانی را می‌دهد که رابط می‌خواند (کلید: norm)")

        n = WS.remove(conn, "داريك")
        conn.commit()
        ck(n == 1 and WS.count(conn) == 1,
           "۸) حذف با نوشتارِ عربی، ردیفِ فارسی را برمی‌دارد (یکی بودنِ هویت درِ حذف)")

        # توقعِ اولِ من این بود که خودِ store تا USER_WATCHLIST_MAX نگهش می‌دارد.
        # نداشتنِ آن درِ store واقعیت است و عمدی: سیاستِ سقف درِ route نشسته
        # (`api/watchlist.py:51-56` — `watchlist_max` پنل کدال، clamp شده با
        # USER_WATCHLIST_MAX). اینجا همان تفکیکِ لایه قفل می‌شود:
        # store بی‌سقف است، پس هر فراخوانِ مستقیمِ add (legacy/test) سقف را
        # نمی‌بیند — و دقیقاً به همین دلیل سقفِ route باید گارد شود، نه فرض.
        before = WS.count(conn)
        for i in range(WS.USER_WATCHLIST_MAX):
            WS.add(conn, "نماد" + str(i))
        conn.commit()
        ck(WS.count(conn) == before + WS.USER_WATCHLIST_MAX,
           "۹) store خودش سقف ندارد (سقف درِ route است) ⇒ عددِ بی‌گاردهایِ لایۀ دیگر")
    finally:
        conn.close()
        os.unlink(path)

    src = open(os.path.join(ROOT, "api", "watchlist.py"), encoding="utf-8").read()
    ck("USER_WATCHLIST_MAX" in src and "watchlist_max" in src,
       "۹-ب) سقفِ واقعی درِ route هر دو را می‌خواند: کلیدِ پنل + گاردِ سختِ store")

    # ۱۰/۱۱) ظرفیتِ کاربر هرگز نباید دامنۀ غربالگری را ببرد (§۱۰ task)
    forbidden = []
    for rel in ("funnel_engine.py", "api/funnel.py", "funnel_tech_scan.py",
                "funnel_registry.py", "api/screener.py"):
        body = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        if "USER_WATCHLIST_MAX" in body or "user_watchlists" in body:
            forbidden.append(rel)
    ck(not forbidden,
       "۱۰) هیچ مسیرِ غربالگری به سقف/جدولِ واچ‌لیستِ کاربر دست نمی‌زند"
       + ("" if not forbidden else " — نشتی: " + ", ".join(forbidden)))
    src = open(os.path.join(ROOT, "api", "watchlist.py"), encoding="utf-8").read()
    ck("watchlist_max" in src,
       "۱۱) کلیدِ پنلِ «watchlist_max» (سیمِ تنظیماتِ کدال) دست‌نخورده مانده — چیزی که "
       "بند ۹/۱۰ خواستش تفکیکِ *نامِ کد* بود، نه شکستنِ قراردادِ فرانت/اندروید")
    # ۱۱-ب) تفکیکِ واقعاً انجام‌شده: سه مفهوم، سه نام. قبلاً این‌جا یک پینِ
    # «باز است» نشسته بود؛ پینِ باگ‌ِ شناخته‌شده درِ همان تغییر باید برگردد
    # (قاعدۀ کار)، پس این بند حالا *اثباتِ* تفکیک است نه ثبتِ کمبود.
    ws_src = open(os.path.join(ROOT, "watchlist_store.py"), encoding="utf-8").read()
    ck("USER_WATCHLIST_MAX" in ws_src and "MATRIX_PROBE_MAX" in ws_src,
       "۱۱-ب) ظرفیتِ کاربر و سقفِ ماتریس دو ثابتِ جدا اند (USER_WATCHLIST_MAX / MATRIX_PROBE_MAX)")
    stale = [rel for rel in ("watchlist_store.py", "api/watchlist.py", "api/screener.py",
                             "funnel_engine.py")
             if "MAX_WATCHLIST" in open(os.path.join(ROOT, rel), encoding="utf-8").read()]
    ck(not stale, "۱۱-پ) هیچ نامِ دوپهلوِ «MAX_WATCHLIST» درِ این چهار فایل نمانده"
       + ("" if not stale else " — نشتی: " + ", ".join(stale)))
    # ۱۲) ماتریس دادهٔ بازار را از market.db می‌خواند، نه از connِ کاربر (باگِ
    # `no such table: instruments` — همین سبب شد `/api/watchlist/matrix?symbols=` بشکند).
    body = ws_src.split("def matrix(", 1)[1]
    body = body.split("\ndef ", 1)[0]
    ck("bors_config.DB_PATH" in body and "build_ctx(conn)" not in body,
       "۱۲) ماتریس برایِ محاسبهٔ بازار connectionِ خودش (market.db) را می‌سازد؛ "
       "connِ کاربر فقط برایِ ردیف/یادداشت است")
    print()
    if FAILED:
        print(f"user_watchlist guard: {len(FAILED)} FAILED")
        return 1
    print(f"user_watchlist guard OK — 13 band")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
