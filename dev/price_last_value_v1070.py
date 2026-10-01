#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/price_last_value_v1070.py — «آخرین» و «پایانی» دو ستون‌اند؛ جعلِ یکی جای دیگر ممنوع.

چرا این گارد متولد شد (کارِ #73 قدمِ ۲، ۱۴۰۵-۰۷-۱۰):
قراردادِ `docs/CANDLE-CONTRACT.md` §۱-ث Price Source را settingِ محصول کرد (last|closing،
پیش‌فرض last) و شرطِ بقایش را این گذاشت که **لنگرِ زنجیرِ تعدیل همیشه CLOSING** بماند.
سنجشِ ۸۰۰نمادی (§۱-پ) نشان داد اگر لنگر هم به «آخرین» برود، لنگر درِ ۷۳۹ از ۸۰۰ نماد
(۹۲٪) می‌شکند. پس بانک باید *هر دو* عدد را داشته باشد — و `price_history` نداشت:
`api/chart.py:907` مجبور بود `last := close` بسازد و inventory (§۲) صریح نوشته بود
«ستونِ last وجود ندارد».

این گارد بی‌شبکه و بی‌market.dbِ واقعی می‌دود (دیتایِ CSV و تابلو فیکسچرند).
اجرا:  python dev/price_last_value_v1070.py
خروج: ۰ اگر همه درست، ۱ در غیر این صورت.
"""
import io
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import test_tsetmc as t  # noqa: E402

HEAD = ("<TICKER>,<DTYYYYMMDD>,<FIRST>,<HIGH>,<LOW>,<CLOSE>,<VALUE>,<VOL>,"
        "<OPENINT>,<PER>,<OPEN>,<LAST>")
PASS = FAIL = 0


def ck(ok, what, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  ok   " + what)
    else:
        FAIL += 1
        print(f"  FAIL {what}" + (f"  ← {detail}" if detail else ""))


class FakeResp:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class FakeSession:
    """فقط چیزی که fetch_price_history از session می‌خواهد: .get() بی‌شبکه."""

    def __init__(self, text):
        self.text = text
        self.urls = []

    def get(self, url, headers=None, timeout=None, stream=None):
        self.urls.append(url)
        return FakeResp(self.text)


def db_with_instruments(symbol="فولاد", ins="46348559193224090"):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    c = sqlite3.connect(path)
    t.create_schema(c)
    c.execute("INSERT OR REPLACE INTO instruments (ins_code, l_val18, l_val30) "
              "VALUES (?,?,?)", (ins, symbol, symbol))
    c.commit()
    return c, path


def main():
    print("price_last_value_v1070")

    # ── ۱) ستون‌ها درِ هر دو مسیرِ ساختِ بانک ────────────────────────────────
    print("\n[۱] schema")
    c, p = db_with_instruments()
    cols = [r[1] for r in c.execute("PRAGMA table_info(price_history)")]
    ck("last" in cols and "value" in cols,
       "بانکِ تازه price_history را با last/value می‌سازد", str(cols))
    dcols = [r[1] for r in c.execute("PRAGMA table_info(daily_prices)")]
    ck("p_last" in dcols, "بانکِ تازه daily_prices را با p_last می‌سازد", str(dcols[-2:]))
    # بانکِ *قدیمی* (بدونِ ستون‌ها) باید با ensure_schema بالا بیاید، نه با DROP/CREATE
    old = sqlite3.connect(":memory:")
    old.execute("CREATE TABLE price_history (symbol TEXT, date TEXT, open REAL, high REAL,"
                " low REAL, close REAL, volume REAL, PRIMARY KEY (symbol, date))")
    old.execute("CREATE TABLE daily_prices (ins_code TEXT, d_even INTEGER, p_closing REAL)")
    old.execute("INSERT INTO price_history VALUES ('فولاد','2024-01-01',1,2,0.5,1.5,10)")
    old.commit()
    import mstat_engine  # noqa: E402
    mstat_engine.ensure_schema(old)
    got = old.execute("SELECT close, last FROM price_history WHERE date='2024-09-30' OR 1=1"
                      " LIMIT 1").fetchone()
    ck(got[1] is None,
       "ردیفِ مهاجرت‌کرده last را NULL می‌گیرد، نه کپیِ close", str(got))
    ck("last" in [r[1] for r in old.execute("PRAGMA table_info(price_history)")],
       "مهاجرتِ idempotent رویِ بانکِ قدیمی ستون‌ها را اضافه می‌کند")
    c.close(); old.close(); os.unlink(p)

    # ── ۲) مسیرِ CSV: FIRST برایِ open، LAST برایِ last، VALUE برایِ value ────
    print("\n[۲] fetch_price_history از ردیفِ CSV")
    # روزِ ۱: FIRST(۳۴۳۰) ≠ OPEN/پایه(۳۴۱۰) و LAST(۳۵۲۰) ≠ CLOSE(۳۴۹۵) ⇒ هر اشتباهی
    # درِ نگاشت دیده می‌شود. روزِ ۲: همه یکی — کنترلِ اینکه «جعل» نمی‌کند.
    rows = [
        "<FOOLAD>,20260920,3430,3560,3400,3495,7.4e12,2.5e9,0,100.0,3410,3520",
        "<FOOLAD>,20260921,3500,3520,3480,3500,8.1e12,1.9e9,0,100.0,3500,3500",
    ]
    s = FakeSession(HEAD + "\n" + "\n".join(rows) + "\n")
    c, p = db_with_instruments()
    t.DB_PATH = p
    n = t.fetch_price_history("فولاد", s=s, since="2026-09-01")
    ck(n == 2, "هر دو ردیف نوشته می‌شود", str(n))
    r1 = c.execute("SELECT open, high, low, close, volume, last, value FROM price_history "
                   "WHERE date='2026-09-20'").fetchone()
    ck(r1 == (3430.0, 3560.0, 3400.0, 3495.0, 2.5e9, 3520.0, 7.4e12),
       "open=FIRST، close=CLOSE، last=LAST، value=VALUE — هر چهار نگاشت درست", str(r1))
    ck(r1[0] != 3410.0, "NEGATIVE CONTROL: open دیگر قیمتِ پایه (fields[10]) نیست", str(r1[0]))
    ck(r1[5] != r1[3], "NEGATIVE CONTROL: last عددِ خودش است، نه کپیِ close", str(r1[5]) + " vs close " + str(r1[3]))
    r2 = c.execute("SELECT last, close FROM price_history WHERE date='2026-09-21'").fetchone()
    ck(r2 == (3500.0, 3500.0), "روزی که مرجع دو عدد را یکسان زده، دو ستون یکسان می‌شوند", str(r2))
    c.close(); os.unlink(p)

    # ── ۳) مسیرِ تابلو: کندل با last و value، و بی‌جعل ───────────────────────
    print("\n[۳] candle_from_row")
    bar = t.candle_from_row("فولاد", 20260920, 3430.0, 3560.0, 3400.0, 3495.0, 2.5e9,
                            3520.0, 7.4e12)
    ck(bar[5] == 3495.0 and bar[7] == 3520.0 and bar[8] == 7.4e12,
       "پایانی لنگر می‌ماند و آخرین/گردش کنارش می‌نشینند", str(bar))
    nobar = t.candle_from_row("فولاد", 20260920, 3430.0, 3560.0, 3400.0, 3495.0, 2.5e9)
    ck(nobar[7] is None and nobar[8] is None,
       "NEGATIVE CONTROL: بدونِ «آخرین» درِ منبع، ستون null است نه close", str(nobar[7:]))

    # ── ۴) خواننده دیگر دروغ نمی‌فروشد ───────────────────────────────────────
    print("\n[۴] /api/chart-db")
    src = io.open(os.path.join(ROOT, "api", "chart.py"), encoding="utf-8").read()
    body = src[src.index("def get_chart_db"):src.index("@router.get(\"/api/patterns")]
    ck('"last": float(r[6]) if r[6] is not None else None' in body.replace("\n            ", " "),
       "last از ستونِ خودش خوانده می‌شود", "")
    ck("last\": float(r[4])" not in body and '"last": float(r[4])' not in body,
       "NEGATIVE CONTROL: جعلِ last := close حذف شد", "")
    ck("SELECT date, open, high, low, close, volume, last, value FROM price_history"
       in body.replace("\n                ", " "),
       "کوئریِ خواننده هر دو ستون را می‌آورد", "")

    # ── ۵) لنگرِ تعدیل به last وصل نمی‌شود (§۱-پ: B1 فاجعه است) ───────────────
    print("\n[۵] لنگرِ تعدیل")
    adj = src[src.index("def _adjust_events_from_rows"):src.index("def _d_even_to_date")]
    ck("last" not in adj.replace("last_d_even", ""),
       "NEGATIVE CONTROL: زنجیرِ کشفِ لنگر هیچ «last» نمی‌خواند", "")
    ck("base" in adj and "close" in adj, "لنگر همان pairِ پایه/پایانی است", "")

    # ── ۶) هیچ نویسدۀ جایگاهیِ ۷تایی نمانده ─────────────────────────────────
    print("\n[۶] نویسندگان")
    for f in ("test_tsetmc.py", os.path.join("tools", "backfill_daily_history.py")):
        s2 = io.open(os.path.join(ROOT, f), encoding="utf-8").read()
        bad = [ln for ln in s2.splitlines()
               if "INTO price_history VALUES" in ln.replace("  ", " ")]
        ck(not bad, f"{f}: INSERTِ جایگاهیِ price_history نمانده (ستون‌ها نام‌دارند)", str(bad)[:120])
    dp = io.open(os.path.join(ROOT, "test_tsetmc.py"), encoding="utf-8").read()
    ck(dp.count("p_last") >= 5,
       "p_last درِ هر دو نگاشتِ تابلو (سینک و تیکِ زنده) و INSERT هست", str(dp.count("p_last")))

    print(f"\nprice_last_value_v1070: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
