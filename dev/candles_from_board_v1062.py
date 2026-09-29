#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/candles_from_board_v1062.py — جدولِ کندل باید از خودِ تابلو ساخته شود.

چرا این گارد متولد شد (CANDLES-STALE-1، ۱۴۰۵-۰۷-۰۷؛ پرسشِ مستقیمِ مالک:
«چرا کندل‌ها عقبند؟ خب درستش کن، دور نزن»):

۱) **هیچ حلقۀ خودکاری price_history را نمی‌نوشت.** تنها نویسنده‌اش
   `fetch_price_history` بود — یعنی درخواستِ CSVِ هر نماد، و آن هم یا در
   pack کردنِ baseline یا با `python test_tsetmc.py --update-existing` که دستی
   است. اندازه‌گیری روی کپیِ بانکِ نصبی (۱۴۰۵-۰۷-۰۷، ۱۳:۲۰): `price_history`
   روی ۲۰۲۶-۰۹-۲۱ و **۱۰ ردیف در هر روز** ماند بود، درحالی‌که `daily_prices`
   ۲۴ نشستِ معامله‌شده داشت و هشت تایِ آخرِ آن‌ها (۰۹-۲۲ تا ۰۹-۲۹) در کندل
   نبودند. پس تابلو زنده بود و نمودارِ محلی، `/api/ma`، `/api/patterns` و
   `chart-db` روی جدولی می‌دویدند که خودبه‌خود جلو نمی‌رفت.
   ترمیم: کندل از همان `daily_prices` ساخته می‌شود (first/max/min/closing/vol
   که سینک هر ۹۰ ثانیه می‌نویسد) — بی‌شبکه، بی‌۴۲۹، قابلِ تکرار. روی همان کپی:
   ۵۳٬۰۶۰ کندل از ۲۴ نشست برای ۴٬۰۹۵ نماد در ۰٫۹ ثانیه؛ حالتِ عادی (فقط
   نشستِ تازه) ۲٬۱۷۳ کندل در ۰٫۲۸ ثانیه.

۲) **۳۴٬۸۴۹ کندلِ بی‌هندسه.** `fetch_price_history` ستون `<OPEN>` را می‌خواند
   که «قیمت پایه» است نه اولینِ معامله — همان نقصی که درِ مسیرِ CDN با v8.7
   FIX-1 رَفع شد ولی در این جدول ماند. نمونه: وبملت ۲۰۲۴-۱۰-۲۰ با
   O=H=L=۱٬۸۹۳ در برابر C=۱٬۹۰۱. ترمیم: سایه گِشاد می‌شود، پایانی هرگز
   تکان نمی‌خورد (پایانی به پایهٔ روزِ بعد زنجیر می‌شود، پس معتبر است).

۳) **حذفِ پیش از دریافت.** `DELETE FROM price_history WHERE date < cutoff` پیش
   از درخواستِ CSV اجرا می‌شد و cutoff در حالتِ دلتا با `since` برابر بود؛ یعنی
   هر دلتا تاریخچۀ پیشِ پنجره را بی‌بازگشت می‌زد و اگر درخواست می‌مرد، ردیف‌ها
   از قبل رفته بودند و صفر برمی‌گشت. ترمیم: هرس فقط پس از دریافتِ موفق و فقط در
   حالتِ کامل، تا کفِ ۷۳۰ روزه.

گارد بی‌شبکه و بی‌market.dbِ واقعی می‌دود (جدول‌هایِ موقتِ کوچک).
اجرا:  python dev/candles_from_board_v1062.py
خروج: ۰ اگر همه درست، ۱ در غیر این صورت.
"""
import io
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import test_tsetmc as t  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TS_PY = os.path.join(ROOT, "test_tsetmc.py")

PASS = FAIL = 0


def ck(ok, what, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  ok   %s" % what)
    else:
        FAIL += 1
        print("  FAIL %s%s" % (what, ("  ← " + detail) if detail else ""))


def mini():
    """DBِ موقتِ کوچک با سه جدولِ لازم (فقط ستون‌هایِ خوانده‌شده)."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE instruments (ins_code TEXT, l_val18 TEXT, l_val30 TEXT)")
    c.execute("CREATE TABLE daily_prices (ins_code TEXT, d_even INTEGER, p_closing REAL,"
              " price_min REAL, price_max REAL, price_first REAL, q_tot_tran REAL)")
    c.execute("CREATE TABLE price_history (symbol TEXT, date TEXT, open REAL, high REAL,"
              " low REAL, close REAL, volume REAL, PRIMARY KEY (symbol, date))")
    return c


def seed(c, symbols, sessions):
    """symbols: {ins_code: نام}; sessions: [(d_even, {ins_code: (first,hi,lo,close,vol)})]"""
    for code, name in symbols.items():
        c.execute("INSERT INTO instruments VALUES (?,?,?)", (code, name, name))
    for d_even, rows in sessions:
        for code, (f, h, l, cl, v) in rows.items():
            c.execute("INSERT INTO daily_prices VALUES (?,?,?,?,?,?,?)",
                      (code, d_even, cl, l, h, f, v))
    c.commit()


def count_badge(c):
    return c.execute("SELECT COUNT(*) FROM price_history WHERE open > 0 AND close > 0 AND ("
                     "COALESCE(high,0) < MAX(open, close) OR COALESCE(low,0) = 0 OR "
                     "COALESCE(low,99999999999) > MIN(open, close) OR COALESCE(high,0) <= 0)"
                     ).fetchone()[0]


def main():
    print("candles_from_board_v1062")

    # ── ۱) تبدیلِ تاریخ و ساختِ یک کندل ─────────────────────────────────────
    print("\n[۱] کندل از ردیفِ تابلو")
    ck(t._iso_from_deven(20260929) == "2026-09-29", "d_even → ISO")
    ck(t._iso_from_deven(0) is None and t._iso_from_deven(None) is None,
       "a missing d_even is no date")

    bar = t.candle_from_row("فولاد", 20260929, 3520.0, 3520.0, 3450.0, 3520.0, 2.49e9)
    ck(bar == ("فولاد", "2026-09-29", 3520.0, 3520.0, 3450.0, 3520.0, 2.49e9),
       "a traded session becomes a candle of the board's own OHLC", str(bar))
    ck(t.candle_from_row("فولاد", 20260929, 3520.0, 3520.0, 3450.0, 3520.0, 0.0) is None,
       "NEGATIVE CONTROL: pre-open row with zero volume never becomes a candle")
    ck(t.candle_from_row("فولاد", 20260929, 3520.0, 3520.0, 3450.0, 0.0, 1000.0) is None,
       "no closing price → no candle")
    ck(t.candle_from_row("", 20260929, 1.0, 2.0, 0.5, 1.5, 10.0) is None,
       "an instrument without a symbol string is skipped")
    bad = t.candle_from_row("شپنا", 20260929, 1900.0, 1893.0, 1893.0, 1901.0, 10.0)
    ck(bad and bad[3] == 1901.0 and bad[4] == 1893.0,
       "the shadow widens instead of moving the close", str(bad))
    ck(all(x[3] >= x[4] and x[3] >= max(x[2], x[5]) and x[4] <= min(x[2], x[5])
           for x in [bar, bad]), "every produced candle is geometrically possible")

    # ── ۲) ساختنِ جدولِ کندل از تابلو ───────────────────────────────────────
    print("\n[۲] ساختنِ price_history از daily_prices")
    c = mini()
    seed(c, {"A": "فولاد", "B": "خساپا", "C": "بی‌نام"}, [
        (20260928, {"A": (3410.0, 3420.0, 3380.0, 3420.0, 1.8e9),
                    "B": (690.0, 700.0, 680.0, 695.0, 2.0e9)}),
        (20260929, {"A": (3430.0, 3520.0, 3430.0, 3520.0, 2.5e9),
                    "B": (695.0, 699.0, 675.0, 685.0, 2.6e9),
                    "C": (100.0, 100.0, 100.0, 100.0, 5.0)}),
        # ردیفِ پیش از بازگشایی: امروز هست، معامله نیست
        (20260930, {"A": (3520.0, 0.0, 0.0, 3520.0, 0.0)}),
    ])
    c.execute("INSERT INTO instruments VALUES ('D','درجه‌دو','درجه‌دو')")  # بی‌ردیفِ تابلو
    c.commit()
    r = t.sync_price_history_from_daily(c)
    ck(r["mode"] == "catch-up" and r["rows"] == 5,
       "a stale candle table is filled from every session the board holds", str(r))
    got = dict(c.execute("SELECT symbol, date FROM price_history").fetchall())
    ck(("فولاد", "2026-09-29") in [tuple(x) for x in c.execute(
        "SELECT symbol, date FROM price_history")], "the newest session lands")
    ck(c.execute("SELECT COUNT(*) FROM price_history WHERE date='2026-09-30'").fetchone()[0] == 0,
       "NEGATIVE CONTROL: the untouched session of tomorrow is not in the candle table")
    ck(c.execute("SELECT COUNT(*) FROM price_history WHERE symbol='درجه‌دو'").fetchone()[0] == 0,
       "a symbol the board never quoted stays out")
    r2 = t.sync_price_history_from_daily(c)
    ck(r2["mode"] == "latest" and r2["rows"] == 3,
       "once the table is current only the newest traded session is rewritten — "
       "and the untouched pre-open row does not force a catch-up every 90s", str(r2))
    n_all = c.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
    t.sync_price_history_from_daily(c)
    ck(c.execute("SELECT COUNT(*) FROM price_history").fetchone()[0] == n_all,
       "re-running the sync never duplicates a (symbol,date) row")
    row = c.execute("SELECT open,high,low,close,volume FROM price_history "
                    "WHERE symbol='شپنا' OR symbol='فولاد' AND date='2026-09-28' "
                    "ORDER BY date LIMIT 1").fetchone()
    ck(row == (3410.0, 3420.0, 3380.0, 3420.0, 1.8e9), "values are verbatim from the board",
       str(row))
    empty = mini()
    ck(t.sync_price_history_from_daily(empty)["mode"] == "no-board",
       "an empty board table is reported, not guessed")
    c.close(); empty.close()

    # ── ۳) اصلاحِ هندسهٔ ردیف‌هایِ کهنه ─────────────────────────────────────
    print("\n[۳] سایه‌هایِ بیرونِ بدنه")
    c = mini()
    c.executemany("INSERT INTO price_history VALUES (?,?,?,?,?,?,?)", [
        ("وبملت", "2024-10-20", 1893.0, 1893.0, 1893.0, 1901.0, 1.0),   # close بالای high
        ("خساپا", "2024-10-21", 1000.0, 0.0, 0.0, 990.0, 1.0),          # سایه‌های صفر
        ("فولاد", "2024-10-22", 10.0, 20.0, 5.0, 15.0, 1.0),            # سالم
        ("پالایش", "2024-10-23", 1200.0, 1100.0, 0.0, 1150.0, 1.0),     # low صفر و high پایین
    ])
    c.commit()
    ck(count_badge(c) == 3, "the fixture really holds three impossible candles",
       str(count_badge(c)))
    n = t.normalize_price_history_geometry(c)
    ck(n == 3, "exactly the impossible rows are repaired, the sound one is untouched", str(n))
    ck(count_badge(c) == 0, "no candle keeps its body outside its wicks afterwards")
    ck(dict(c.execute("SELECT symbol, close FROM price_history")).get("وبملت") == 1901.0,
       "the closing price never moved — only the shadow widened")
    wb = c.execute("SELECT high, low FROM price_history WHERE symbol='وبملت'").fetchone()
    ck(wb == (1901.0, 1893.0), "وبملت ۲۰۲۴-۱۰-۲۰ → high باز شد، low همان بدنه", str(wb))
    pl = c.execute("SELECT high, low FROM price_history WHERE symbol='پالایش'").fetchone()
    # lowِ تابلو صفر رسیده (هنوز پر نشده)؛ چیزی که می‌دانیم O=۱۲۰۰ و C=۱۱۵۰ است،
    # پس کمینهٔ *ممکن* همان ۱۱۵۰ است — عددِ ۱۱۰۰ را هیچ‌جا نمی‌سازیم.
    ck(pl == (1200.0, 1150.0), "missing shadows collapse to what the body proves", str(pl))
    ck(t.normalize_price_history_geometry(c) == 0, "NEGATIVE CONTROL: a clean table is a no-op")
    sound = c.execute("SELECT open,high,low,close FROM price_history WHERE symbol='فولاد'").fetchone()
    ck(sound == (10.0, 20.0, 5.0, 15.0), "the sound candle was not rewritten", str(sound))
    c.close()

    # ── ۴) خطرِ «حذف پیش از دریافت» باید رفته باشد ──────────────────────────
    print("\n[۴] هرسِ بی‌بازگشت")
    src = io.open(TS_PY, encoding="utf-8").read()
    fetch_body = src[src.index("def fetch_price_history"):src.index("def update_existing")]
    ck("DELETE FROM price_history" in fetch_body,
       "the prune still exists (depth is still bounded)")
    ck(fetch_body.index("if rows and not since") < fetch_body.index("DELETE FROM price_history"),
       "it runs only after a successful FULL fetch — never before the request")
    ck('datetime.timedelta(days=730)).strftime("%Y-%m-%d")\n            conn.execute'
       in fetch_body or "floor = " in fetch_body,
       "the prune is bounded to the 730-day floor, not to the delta window")

    print("\n[۵] سیم‌کشی")
    main_body = src[src.index("def main()"):]
    ck("sync_price_history_from_daily(conn)" in main_body,
       "the ordinary board sync writes the candles — that is the whole point")
    ck("normalize_price_history_geometry(conn)" in main_body,
       "and the geometry repair rides the same pass")
    ck("candles-from-board" in main_body or "candles-from-board" in src,
       "the pass says what it did in the log")
    # حلقۀ سینک فقط درِ پنجرۀ ۰۹–۱۳ می‌دود؛ اگر برنامه پس از بستنِ بازار بالا
    # بیاید، بدونِ این قفلِ جدولِ کندل هرگز به نشستِ آخر نمی‌رسد.
    app_py = io.open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
    ck("def _candle_projection_at_boot():" in app_py,
       "app.py defines a boot pass over the candle projection")
    _b0 = app_py.index("def _candle_projection_at_boot")
    boot = app_py[_b0:app_py.index("threading.Thread(target=_candle_projection_at_boot")]
    ck("sync_price_history_from_daily(_c)" in boot,
       "the boot pass writes the candles from the board")
    ck("normalize_price_history_geometry(_c)" in boot,
       "and repairs the shadows")
    ck("threading.Thread(target=_candle_projection_at_boot" in
       app_py[_b0:_b0 + 1600],
       "the pass is started on its own thread — boot is not blocked on it")
    ck("import test_tsetmc" in boot and "requests" not in boot and "http" not in boot,
       "it reads only the local database (no network at boot)")

    print("\ncandles_from_board_v1062: %d passed, %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
