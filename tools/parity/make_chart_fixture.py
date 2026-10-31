#!/usr/bin/env python
"""فیکسچرِ چارت/FTS برایِ پورتِ Go — رویِ فیکسچرِ تابلو ساخته می‌شود.

چرا رویِ فیکسچرِ تابلو: نمادها و `market_watch`/`instruments` همان B1 است، پس
هر عددِ این فیکسچر در دو مرحله یک معنا دارد. چیزهایی که چارت اضافه می‌کند:

* `price_history`ِ ده‌ستونی (open/last/value/src) با تاریخچهٔ عمیق: پنج نمادِ
  کانونی ۳۲۰ نشست، یک نماد ۴۰ نشست (کوتاه‌تاریخ)، یک نماد بی‌ردیف (بی‌داده)،
  و یک نوشتارِ دومِ همان نماد (فاصله‌دار) رویِ ده روزِ آخر تا «حذفِ تکرارِ روز»
  و «نامزدهایِ هویت» واقعاً سنجیده شوند.
* `adjust_events`/`adjust_verdict` و `price_adjust_events`/`share_change_events`.
* `order_book` با پنج سطح (و یک نمادِ `book_txt=NULL`).
* تقویمِ کوچک با رویدادهایِ نزدیک به «امروزِ» قفل‌شده (۲۰۲۶-۱۰-۲۸)، شاملِ لغوِ
  مجمع (برندهٔ تساوی)، افزایشِ سرمایه، تاریخِ نامعلوم (publication_fallback) و
  نوشتارِ عربی.
* `user.db` با سه ردیفِ `selection_decisions` (accept/price>0، reject، accept/0).

خروجی: backend-go/internal/chart/testdata/fixture/{market.db,user.db,calendar/cache.json}
هیچ دادهٔ واقعی در آن نیست و همهٔ اعداد با فرمولِ بی‌تصادف ساخته می‌شوند.
"""
import datetime as dt
import json
import math
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "parity"))
OUT = os.path.join(ROOT, "backend-go", "internal", "chart", "testdata", "fixture")

LIVE_D_EVEN = 20261028
LIVE_H_EVEN = 103000
LAST_HIST = dt.date(2026, 10, 27)
TODAY = dt.date(2026, 10, 28)

UPTREND = "عادی01"
DOWNTREND = "پایین02"
FUND = "اهرم‌ب"
SHORT = "کم‌سابقه11"
NODATA = "بی‌معامله04"
FOCUS = (UPTREND, DOWNTREND, FUND, SHORT)

SERIES_DEPTH = {UPTREND: 320, DOWNTREND: 320, FUND: 320, SHORT: 40}

USER_ROWS = [
    (UPTREND, "accept", 1500.0),
    (DOWNTREND, "reject", 400.0),
    (SHORT, "accept", 0.0),
]

EVENTS = [
    # (symbol, title, event_type_id, date_time, published_at)
    (UPTREND, "مجمع عمومی عادی سالیانه شرکت فولاد دوم مورخ 1405/08/11", 1,
     "2026-11-02T10:00:00", "2026-10-20T08:00:00"),
    (UPTREND, "مجمع عمومی عادی سالیانه شرکت فولاد دوم مورخ 1405/08/11", 1,
     "2026-11-02T10:00:00", "2026-10-19T08:00:00"),          # تکرارِ عینِ همان روز/عنوان
    (UPTREND, "افزایش سرمایه از محل آورده نقدی", 0,
     "2026-11-05T09:00:00", "2026-10-21T08:00:00"),
    (UPTREND, "دعوت به مجمع فوق‌العاده", 1,
     "2026-11-03T10:00:00", "2026-10-24T08:00:00"),          # عنوان بی‌تاریخ
    (UPTREND, "مجمع سالیانه بعدی", 1,
     "2027-01-15T10:00:00", "2026-10-25T08:00:00"),          # بیرون از افقِ ۱۴روزه
    ("عادي01", "مجمع با نوشتارِ عربی", 1,
     "2026-11-09T10:00:00", "2026-10-25T09:00:00"),          # ي عربی ⇒ همان نماد
    (DOWNTREND, "مجمع عمومی عادی سالیانه", 1,
     "2026-10-30T10:00:00", "2026-10-10T08:00:00"),
    (DOWNTREND, "لغو مجمع عمومی عادی سالیانه", 1,
     "2026-10-30T10:00:00", "2026-10-22T08:00:00"),          # تساویِ تاریخ: لغو برنده
    ("پول‌هوشمند06", "افزایش سرمایه شرکت پول هوشمند", 0,
     "2026-11-05T09:00:00", "2026-10-23T08:00:00"),
    ("غایب", "مجمع عمومی عادی سالیانه غایب", 1,
     "2026-11-01T10:00:00", "2026-10-18T08:00:00"),          # نمادِ بی‌ردیف در بانک
]

BOOK5 = json.dumps([
    [2010.0, 120000.0, 14.0, 2020.0, 90000.0, 11.0],
    [2005.0, 300000.0, 22.0, 2025.0, 150000.0, 19.0],
    [2000.0, 500000.0, 31.0, 2030.0, 260000.0, 24.0],
    [1995.0, 450000.0, 27.0, 2035.0, 340000.0, 29.0],
    [1990.0, 700000.0, 40.0, 2040.0, 410000.0, 33.0],
])


def sessions(n, end=LAST_HIST):
    """n نشستِ کاریِ پیش از `end` (پنجشنبه/جمعه تعطیل)، صعودی."""
    out, d = [], end
    while len(out) < n:
        if d.weekday() not in (3, 4):
            out.append(d)
        d -= dt.timedelta(days=1)
    return list(reversed(out))


def series(sym, dates, start, drift, wave, last_missing_from=None):
    """سریِ قطعی: روندِ خطی + موجِ سینوسی، با چند ردیفِ معیوبِ سایه (H<بدنه)."""
    rows, prev = [], start
    for i, d in enumerate(dates):
        base = start * (1.0 + drift * i)
        close = round(base + wave * math.sin(i / 7.0)
                      + wave * 0.35 * math.sin(i / 2.1), 2)
        op = round(prev * (1.0 + 0.0015 * math.sin(i / 1.7)), 2)
        hi = round(max(op, close) + start * 0.004
                   * (1.0 + 0.25 * math.sin(i / 3.3)), 2)
        lo = round(min(op, close) - start * 0.004
                   * (1.0 + 0.25 * math.cos(i / 4.1)), 2)
        if i % 37 == 0:
            hi = round(min(op, close) - 1.0, 2)       # نقصِ سایه، نه قیمت
        if i % 53 == 0:
            lo = round(max(op, close) + 1.0, 2)
        vol = float(100000 + (i * 7919) % 90000)
        last = (None if (last_missing_from is not None and i >= last_missing_from)
                else round(close * (1.0 + 0.0008 * math.sin(i / 2.7)), 2))
        rows.append((sym, d.isoformat(), op, hi, lo, close, vol, last,
                     round(vol * close), "published" if i % 13 else "board"))
        prev = close
    return rows


def add_columns(con, table, cols):
    have = {r[1] for r in con.execute("PRAGMA table_info(%s)" % table)}
    for name, typ in cols:
        if name not in have:
            con.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, name, typ))


def clone_watch_row(con, src_ins, new_ins):
    cols = [r[1] for r in con.execute("PRAGMA table_info(market_watch)")]
    row = list(con.execute("SELECT * FROM market_watch WHERE ins_code=?",
                           (src_ins,)).fetchone())
    row[cols.index("ins_code")] = new_ins
    con.execute("INSERT INTO market_watch VALUES(%s)" % ",".join("?" * len(cols)),
                row)


def build(tmp):
    import make_board_fixture as MBF
    MBF.OUT = tmp
    assert MBF.main() == 0
    db = os.path.join(tmp, "market.db")
    con = sqlite3.connect(db)
    add_columns(con, "price_history", [("open", "REAL"), ("last", "REAL"),
                                       ("value", "REAL"), ("src", "TEXT")])
    # `updated_at` را همین سه مسیر (order-book، corporateEvents، CDN) در ORDER BY
    # می‌خوانند؛ فیکسچرِ تابلو ندارد و نبودش هر سه را «error/no row» می‌کرد.
    add_columns(con, "instruments", [("isin", "TEXT"), ("updated_at", "TEXT")])
    con.execute("UPDATE instruments SET updated_at='2026-10-27 12:00:00'")
    con.execute("CREATE TABLE order_book(ins_code TEXT PRIMARY KEY, book_txt TEXT,"
                " d_even INTEGER, h_even INTEGER, updated_at TEXT)")
    con.execute("CREATE TABLE adjust_events(symbol TEXT, date TEXT, ratio REAL,"
                " source TEXT, PRIMARY KEY(symbol, date))")
    con.execute("CREATE TABLE adjust_verdict(symbol TEXT PRIMARY KEY, source TEXT,"
                " checked_at TEXT)")
    con.execute("CREATE TABLE price_adjust_events(ins_code TEXT, d_even INTEGER,"
                " p_closing_not_adjusted REAL, p_closing REAL, source TEXT)")
    con.execute("CREATE TABLE share_change_events(ins_code TEXT, d_even INTEGER,"
                " shares_old REAL, shares_new REAL, source TEXT)")

    # ---- نمادِ صندوقِ اهرمی: کپیِ ردیفِ تابلو با کد/نامِ تازه ----
    clone_watch_row(con, "INS-" + UPTREND, "INS-" + FUND)
    con.execute("INSERT INTO instruments(ins_code,l_val18,l_val30,sector_name) "
                "VALUES(?,?,?,?)", ("INS-" + FUND, FUND, "صندوق اهرمی ب",
                                    "صندوق سرمايه گذاري قابل معامله"))
    con.execute("INSERT INTO boards VALUES(?,?)", ("INS-" + FUND, "بازار"))
    con.execute("UPDATE instruments SET isin=? WHERE ins_code=?",
                ("IRO7FUND0001", "INS-" + FUND))
    con.execute("UPDATE instruments SET isin=? WHERE ins_code=?",
                ("IRO1FOLD0001", "INS-" + UPTREND))

    # ---- تاریخچهٔ عمیقِ پنج نمادِ کانونی ----
    con.execute("DELETE FROM price_history WHERE symbol IN (%s)"
                % ",".join("?" * len(FOCUS)), FOCUS)
    spec = {
        UPTREND: (1000.0, 0.0035, 25.0, 290),      # روندِ صعودی، last در ۳۰ ردیفِ آخر نیست
        DOWNTREND: (5000.0, -0.0008, 60.0, None),  # نزولی، last کامل
        FUND: (8000.0, -0.0010, 120.0, None),      # صندوقِ اهرمی، پرنوسان
        SHORT: (900.0, 0.0010, 15.0, None),        # کوتاه‌تاریخ (۴۰ نشست)
    }
    last_close = {}
    for sym, (start, drift, wave, missing) in spec.items():
        rows = series(sym, sessions(SERIES_DEPTH[sym]), start, drift, wave, missing)
        last_close[sym] = rows[-1][5]
        for r in rows:
            con.execute("INSERT INTO price_history(symbol,date,open,high,low,close,"
                        "volume,last,value,src) VALUES(?,?,?,?,?,?,?,?,?,?)", r)

    # نوشتارِ دومِ همان نماد (فاصله‌دار): ده روزِ آخر، حجمِ ده‌برابر ⇒ در حذفِ
    # تکرارِ روز برنده است. اگر هویت/نامزدها گم شوند، این ردیف‌ها دیده نمی‌شوند.
    base = [r for r in series(UPTREND, sessions(320), 1000.0, 0.0035, 25.0, 290)][-10:]
    for sym, d, op, hi, lo, close, vol, last, value, src in base:
        con.execute("INSERT INTO price_history(symbol,date,open,high,low,close,"
                    "volume,last,value,src) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("عادی 01", d, op, round(hi * 1.01, 2), round(lo * 1.01, 2),
                     round(close * 1.01, 2), vol * 10.0,
                     round(last * 1.01, 2) if last else None,
                     round(value * 10.1), "published"))

    # بی‌داده: ردیف‌هایِ ۶۰روزهٔ فیکسچرِ تابلو حذف می‌شوند تا «بی‌ردیف» واقعی باشد.
    con.execute("DELETE FROM price_history WHERE symbol=?", (NODATA,))

    # ---- نشستِ زنده برایِ کندلِ امروز (پنجشنبه‌ها تعطیل، ۲۰۲۶-۱۰-۲۸ چهارشنبه) ----
    # قیمتِ نشستِ زنده از آخرین پایانیِ همان سری می‌آید تا «کندلِ امروز» یک جهشِ
    # ساختگی نسازد و روندِ طبقه‌بندی‌شده را جابه‌جا نکند.
    live_px = last_close
    for sym, px in live_px.items():
        con.execute("UPDATE market_watch SET d_even=?, h_even=?, price_first=?,"
                    " price_max=?, price_min=?, p_closing=?, p_last=?, q_tot_tran=?"
                    " WHERE ins_code=?", (LIVE_D_EVEN, LIVE_H_EVEN, round(px * 0.998, 2),
                                          round(px * 1.02, 2), round(px * 0.975, 2),
                                          px, round(px * 1.005, 2), 250000.0,
                                          "INS-" + sym))
    con.execute("UPDATE market_watch SET d_even=?, h_even=?, price_first=?,"
                " price_max=?, price_min=?, p_closing=?, p_last=?, q_tot_tran=?"
                " WHERE ins_code=?", (LIVE_D_EVEN, LIVE_H_EVEN, 1500.0, 1500.0,
                                      1500.0, 1500.0, 1500.0, 0.0, "INS-" + NODATA))

    # ---- عمقِ پنج‌سطحی ----
    con.execute("INSERT INTO order_book VALUES(?,?,?,?,?)",
                ("INS-" + UPTREND, BOOK5, LIVE_D_EVEN, LIVE_H_EVEN,
                 "2026-10-28 10:29:00"))
    con.execute("INSERT INTO order_book VALUES(?,?,?,?,?)",
                ("INS-" + DOWNTREND, None, LIVE_D_EVEN, LIVE_H_EVEN,
                 "2026-10-28 10:29:00"))

    # ---- رویدادهایِ تعدیل و شرکتی (مبدأ، نه محاسبه) ----
    con.executemany("INSERT INTO adjust_events VALUES(?,?,?,?)",
                    [(UPTREND, "2026-06-15", 0.90, "base-price-discontinuity"),
                     (UPTREND, "2026-09-10", 0.95, "base-price-discontinuity")])
    con.executemany("INSERT INTO adjust_verdict VALUES(?,?,?)",
                    [(UPTREND, "base-price-discontinuity", "2026-10-27"),
                     (DOWNTREND, "no-adjustment-event", "2026-10-27")])
    con.execute("INSERT INTO price_adjust_events VALUES(?,?,?,?,?)",
                ("INS-" + UPTREND, 20260910, 1800.0, 1710.0, "tsetmc"))
    con.execute("INSERT INTO share_change_events VALUES(?,?,?,?,?)",
                ("INS-" + UPTREND, 20260615, 1.0e9, 1.2e9, "tsetmc"))
    con.commit()
    con.close()

    user_db = os.path.join(tmp, "user.db")
    u = sqlite3.connect(user_db)
    u.execute("""CREATE TABLE IF NOT EXISTS selection_decisions (
            symbol TEXT PRIMARY KEY, name TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending', reason TEXT DEFAULT '',
            note TEXT DEFAULT '', stop_loss TEXT DEFAULT '',
            asset_kind TEXT DEFAULT '', weight_pct REAL DEFAULT 0,
            price REAL DEFAULT 0, qty REAL DEFAULT 0, score INTEGER DEFAULT 0,
            pricing_mode TEXT DEFAULT '', sector TEXT DEFAULT '',
            updated_at TEXT DEFAULT '')""")
    for sym, status, price in USER_ROWS:
        u.execute("INSERT INTO selection_decisions(symbol,status,price,updated_at)"
                  " VALUES(?,?,?,?)", (sym, status, price, "2026-10-27"))
    u.commit()
    u.close()

    cal_dir = os.path.join(tmp, "calendar")
    os.makedirs(cal_dir, exist_ok=True)
    events = [{"asset_symbol_trade": sym, "event_title": title,
               "event_type_id": tid, "date_time": dtm, "published_at": pub}
              for sym, title, tid, dtm, pub in EVENTS]
    with open(os.path.join(cal_dir, "cache.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": {"fixture": "B3"}, "events": events}, f,
                  ensure_ascii=False, separators=(",", ":"))


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    for name in ("market.db", "user.db"):
        path = os.path.join(OUT, name)
        if os.path.exists(path):
            os.remove(path)
    build(OUT)
    print("chart fixture -> %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
