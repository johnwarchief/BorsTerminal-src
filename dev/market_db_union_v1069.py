#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/market_db_union_v1069.py — یک «نصبِ کامل» هرگز دادهٔ بازارِ کاربر را له نمی‌کند.

چرا (UPDATE-ROLLBACK-1): شمارشِ واقعی روی ماشینِ مالک نشان داد market.db او
daily_prices تا ۲۰۲۶۰۹۳۰ با ۹۱٫۶۸۶ ردیف و price_history با ۳۷۵٫۱۵۴ ردیف و
tape_history با ۱۵۱٫۳۵۶ ردیف دارد، در حالی که baselineِ داخلِ نصاب ۸۷٫۱۴۶ /
۳۲۱٫۳۸۹ ردیف و تا ۲۰۲۶۰۹۲۹ است. مسیرِ قدیمیِ ensure_market_db هر بار که هشِ
market.db.lzma عوض می‌شد کل market.db را با baseline جایگزین می‌کرد و فقط
user_watchlists و selection_decisions را منتقل می‌نمود — یعنی هر «نصبِ کامل»
(که سهمِ کاربرِ نسخهٔ گذشته‌همان است، چون دلتا پچ فقط با from == نسخهٔ فعلی
خوراک می‌شود) کندل‌ها و نبضِ روزهایی را که خودِ برنامه سینک کرده بود پاک می‌کرد
و چارت به عقب برمی‌گشت. مالک این را «چیزی که نصب می‌شود خراب است» گزارش کرد.

راهِ رفع: دیتابیسِ سالم هرگز جایگزین نمی‌شود؛ ردیف‌هایِ baseline «رو‌به‌جلو»
ادغام می‌شوند (INSERT OR IGNORE رویِ کلیدِ اصلی) و جدولی که نصبِ کاربر ندارد و
baseline دارد ساخته و پر می‌شود. دیتابیسِ ناقص همچنان از نو استخراج می‌شود.

این گارد همه‌چیز را با دیتابیس‌هایِ کوچکِ ساختگی می‌سنجد و به bank نیاز ندارد.
نکتهٔ کنترلیِ منفی که حتماً قفل می‌شود: ادغامِ دوبار باید صفر ردیفِ تازه بدهد
(بی‌تکراری) و هیچ ردیفِ زنده‌ای نباید کم شود.

خروج: ۰ اگر همه درست، ۱ در غیر این صورت.
اجرا:  python dev/market_db_union_v1069.py
"""
import os
import re
import re
import shutil
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bors_config  # noqa: E402

PASS = FAIL = 0


def ck(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("  FAIL  %s   %s" % (label, extra))


def conn(path):
    return sqlite3.connect(path)


def make_live(path, tape=True):
    """دیتابیسِ «سالمِ کاربر»: تا ۲۰۲۶۰۹۳۰ سینک شده و tape_history را دارد."""
    c = conn(path)
    c.executescript(
        """
        CREATE TABLE instruments(ins_code TEXT PRIMARY KEY, sector_name TEXT);
        CREATE TABLE daily_prices(ins_code TEXT, d_even INT, p_closing REAL,
                                  fetched_at TEXT, extra_col TEXT,
                                  PRIMARY KEY(ins_code, d_even));
        CREATE TABLE price_history(symbol TEXT, date TEXT, open REAL, close REAL,
                                  PRIMARY KEY(symbol, date));
        CREATE TABLE financial_statements(tracing_no INTEGER PRIMARY KEY, symbol TEXT);
        CREATE TABLE user_watchlists(symbol_norm TEXT PRIMARY KEY, symbol TEXT);
        CREATE TABLE board_hist_v(symbol TEXT, month_avg_vol REAL);   /* بی‌کلید */
        """
    )
    if tape:
        c.executescript(
            """
            CREATE TABLE tape_history(ins_code TEXT NOT NULL, d_even INT NOT NULL,
                                      q_tot REAL, PRIMARY KEY(ins_code, d_even));
            """
        )
        c.executemany("INSERT INTO tape_history VALUES(?,?,?)",
                      [("x", 20260929, 5.0), ("y", 20260930, 6.0)])
    c.executemany("INSERT INTO instruments VALUES(?,?)", [("a", "سیمان"), ("b", "پتروشیمی")])
    # دو روزِ محلی که baseline آن‌ها را ندارد + یک ردیفِ تکراری برایِ ادغام
    c.executemany("INSERT INTO daily_prices VALUES(?,?,?,?,?)", [
        ("a", 20260928, 100.0, "t1", "z"),
        ("a", 20260929, 110.0, "t2", "z"),
        ("a", 20260930, 120.0, "t3", "z"),
    ])
    c.executemany("INSERT INTO price_history VALUES(?,?,?,?)", [
        ("a", "2026-09-30", 1.0, 120.0),
        ("b", "2026-09-29", 2.0, 3.0),
    ])
    c.executemany("INSERT INTO board_hist_v VALUES(?,?)", [("a", 1.0)])
    c.execute("INSERT INTO user_watchlists VALUES(?,?)", ("خودرو", "خودرو"))
    c.commit()
    c.close()


def make_baseline(path):
    """baselineِ نصاب: روزهایِ قدیمی‌ترِ بیشتر، ستونِ کمتر، بدونِ tape."""
    c = conn(path)
    c.executescript(
        """
        CREATE TABLE instruments(ins_code TEXT PRIMARY KEY, sector_name TEXT);
        CREATE TABLE daily_prices(ins_code TEXT, d_even INT, p_closing REAL,
                                  fetched_at TEXT, PRIMARY KEY(ins_code, d_even));
        CREATE TABLE price_history(symbol TEXT, date TEXT, open REAL, close REAL,
                                  PRIMARY KEY(symbol, date));
        CREATE TABLE financial_statements(tracing_no INTEGER PRIMARY KEY, symbol TEXT);
        CREATE TABLE user_watchlists(symbol_norm TEXT PRIMARY KEY, symbol TEXT);
        CREATE TABLE tape_history(ins_code TEXT NOT NULL, d_even INT NOT NULL,
                                  q_tot REAL, PRIMARY KEY(ins_code, d_even));
        CREATE TABLE board_hist_v(symbol TEXT, month_avg_vol REAL);
        """
    )
    c.executemany("INSERT INTO instruments VALUES(?,?)", [("a", "سیمان"), ("c", "کانی")])
    c.executemany("INSERT INTO daily_prices VALUES(?,?,?,?)", [
        ("a", 20260926, 80.0, "b1"),      # تازه برایِ کاربر — باید اضافه شود
        ("a", 20260929, 999.0, "b2"),     # تکراری — مقدارِ کاربر باید بماند
        ("a", 20260930, 998.0, "b3"),     # تکراری — مقدارِ کاربر باید بماند
    ])
    c.executemany("INSERT INTO price_history VALUES(?,?,?,?)", [
        ("a", "2026-09-26", 5.0, 6.0),    # candle از گذشته، کاربر ندارد
        ("a", "2026-09-30", 9.0, 9.0),    # تکراری
    ])
    c.executemany("INSERT INTO tape_history VALUES(?,?,?)", [("c", 20260926, 1.0)])
    c.executemany("INSERT INTO board_hist_v VALUES(?,?)", [("a", 1.0), ("z", 2.0)])
    c.execute("INSERT INTO user_watchlists VALUES(?,?)", ("oldersym", "x"))
    c.commit()
    c.close()


def rows(c, q):
    return c.execute(q).fetchall()


# ---------------------------------------------------------------- ۱) رفتارِ ادغام
def test_union(tmp):
    live = os.path.join(tmp, "live.db")
    base = os.path.join(tmp, "base.db")
    make_live(live)
    make_baseline(base)

    added = bors_config._union_forward(live, base)
    c = conn(live)
    ck(len(added) > 0, "union reports what it added", str(added))

    # هیچ ردیفِ زنده‌ای پاک نشد
    dp = rows(c, "SELECT d_even, p_closing FROM daily_prices ORDER BY d_even")
    ck([r[0] for r in dp] == [20260926, 20260928, 20260929, 20260930],
       "union is forward-only: local days kept, baseline days added", str(dp))
    ck((20260929, 110.0) in dp and (20260930, 120.0) in dp,
       "the live row wins over the baseline's rewrite of the same key", str(dp))
    ck(added.get("daily_prices") == 1, "only the missing day was inserted", str(added))

    ph = rows(c, "SELECT date FROM price_history ORDER BY date")
    ck([r[0] for r in ph] == ["2026-09-26", "2026-09-29", "2026-09-30"],
       "candles survive and the baseline's older candles are added", str(ph))

    # جدولی که کاربر ندارد و baseline دارد ساخته می‌شود
    t = rows(c, "SELECT name FROM sqlite_master WHERE type='table' AND name='tape_history'")
    ck(bool(t), "a table only the baseline has is created in the live db")
    th = rows(c, "SELECT ins_code, d_even FROM tape_history ORDER BY d_even")
    ck(len(th) == 3, "its rows are copied too", str(th))

    # بی‌کلیدها هرگز ادغام نمی‌شوند (وگرنه ردیفِ تکراری)
    bv = rows(c, "SELECT count(*) FROM board_hist_v")[0][0]
    ck(bv == 1, "a table with no primary key is never unioned (no silent duplicates)", bv)

    # واچ‌لیستِ کاربر نباید دست بخورد
    uw = rows(c, "SELECT symbol_norm FROM user_watchlists")
    ck(uw == [("خودرو",)], "the user's watchlist is untouched by the merge", str(uw))

    # ستونِ اضافه‌شده باید پر بماند و ادغام ستونِ غایب را نشکند
    ex = rows(c, "SELECT extra_col FROM daily_prices WHERE d_even=20260926")
    ck(ex == [(None,)], "shared-column list handles the baseline having fewer columns", str(ex))
    c.close()

    # idempotent: ادغامِ دوباره نباید ردیفی اضافه کند. (instruments با
    # INSERT OR REPLACE می‌سوزد، پس changes() دوباره عدد می‌دهد؛ چیزی که
    # تضمینِ بی‌تکراری است «شمارِ ردیف» است نه شمارِ سوزش.)
    def census(path):
        con = conn(path)
        try:
            return {t: con.execute('SELECT count(*) FROM "%s"' % t).fetchone()[0]
                    for t in ("daily_prices", "price_history", "instruments",
                              "tape_history", "board_hist_v", "user_watchlists")}
        finally:
            con.close()
    before = census(live)
    bors_config._union_forward(live, base)
    after = census(live)
    ck(before == after, "merging twice changes no row count", (before, after))
    return live


# ---------------------------------------------------------------- ۲) ensure_market_db
def _fake_lzma(tmp, payload_db):
    """market.db.lzma ساختگی از روی یک دیتابیسِ کوچک."""
    import lzma
    p = os.path.join(tmp, "market.db.lzma")
    with open(payload_db, "rb") as f, lzma.open(p, "wb") as out:
        out.write(f.read())
    return p


def test_ensure(tmp):
    work = os.path.join(tmp, "work")
    os.makedirs(work, exist_ok=True)
    live = os.path.join(work, "market.db")
    make_live(live)
    base_payload = os.path.join(tmp, "payload.db")
    shutil.copyfile(os.path.join(tmp, "base.db"), base_payload)
    lz = _fake_lzma(work, base_payload)

    real_work, real_db = bors_config.WORK_DIR, bors_config.DB_PATH
    real_find = bors_config._find_bundled_db_lzma
    try:
        bors_config.WORK_DIR = work
        bors_config.DB_PATH = live
        bors_config._find_bundled_db_lzma = lambda: lz

        # baseline هنوز مهر نشده ⇒ مسیرِ «کهنه» فعال می‌شود
        out = bors_config.ensure_market_db(verbose=False)
        ck(out == live, "ensure_market_db keeps pointing at the user's file", out)
        c = conn(live)
        n = c.execute("SELECT count(*) FROM daily_prices").fetchone()[0]
        mx = c.execute("SELECT max(d_even) FROM daily_prices").fetchone()[0]
        c.close()
        ck(n == 4 and mx == 20260930,
           "a healthy db is merged, not replaced (the user's last day survives)", (n, mx))
        stamp = open(bors_config._baseline_stamp_path()).read().strip()
        ck(stamp == bors_config._sha256_file(lz),
           "the baseline stamp is written so this runs once", stamp[:12])

        # بارِ دوم: هیچ کاری نکند
        before = open(live, "rb").read()
        bors_config.ensure_market_db(verbose=False)
        ck(open(live, "rb").read() == before, "second run is a no-op")

        # دیتابیسِ ناقص ⇒ استخراجِ کامل (کنترلِ منفی). DB_PATH باید همان
        # WORK_DIR/market.db باشد، وگرنه خودِ استخراج را رویِ فایلِ دیگری می‌نویسد.
        work2 = os.path.join(tmp, "work_broken")
        os.makedirs(work2, exist_ok=True)
        broken = os.path.join(work2, "market.db")
        cb = conn(broken)
        cb.execute("CREATE TABLE instruments(ins_code TEXT PRIMARY KEY)")
        cb.commit()
        cb.close()
        lz2 = _fake_lzma(work2, base_payload)
        bors_config.WORK_DIR = work2
        bors_config.DB_PATH = broken
        bors_config._find_bundled_db_lzma = lambda: lz2
        bors_config.ensure_market_db(verbose=False)
        tables = bors_config._market_db_tables(broken)
        ck({"instruments", "daily_prices", "financial_statements"} <= tables,
           "an incomplete db still gets extracted from the bundle", sorted(tables))
    finally:
        bors_config.WORK_DIR, bors_config.DB_PATH = real_work, real_db
        bors_config._find_bundled_db_lzma = real_find


# ---------------------------------------------------------------- ۳) سیم‌کشی
def test_wiring():
    src = open(os.path.join(ROOT, "bors_config.py"), encoding="utf-8").read()
    ck("def _union_forward(" in src, "the forward union exists in bors_config")
    # مسیرِ جایگزینیِ کور باید فقط برایِ دیتابیسِ ناقص بماند
    body = src[src.index("def ensure_market_db"):]
    body = body[:body.index("\n\n\n")]
    ck(body.index("_union_forward(") < body.index("stale_path"),
       "the healthy path merges before any re-extraction")
    ck("_REQUIRED_MARKET_TABLES <= tables" in body,
       "the completeness gate still decides which path runs")
    # ردیف‌هایِ بازار نباید درِ مسیرِ ادغام DELETE بخورند (کامنتِ فارسی
    # «DELETE» را نبايد با statement اشتباه گرفت)
    seg = src[src.index("def _union_forward"):src.index("def ensure_market_db")]
    ck(not re.search(r"execute\([^)]*DELETE", seg, re.I), "the merge issues no DELETE")
    ck(not re.search(r"execute\([^)]*UPDATE", seg, re.I), "the merge rewrites no live row")
    ck("INSERT OR IGNORE" in seg, "the merge is idempotent by primary key")


def main():
    tmp = tempfile.mkdtemp(prefix="bors_union_")
    try:
        test_union(tmp)
        test_ensure(tmp)
        test_wiring()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("market_db_union_v1069: %d passed, %d failed" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
