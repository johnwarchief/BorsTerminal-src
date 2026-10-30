#!/usr/bin/env python
"""فیکسچرِ «وضعیت بازار» برایِ پورتِ Go — رویِ فیکسچرِ تابلو ساخته می‌شود.

چرا رویِ فیکسچرِ تابلو: `mainwatch` پرچم‌هایِ هفت‌گانه را از ردیف‌هایِ
`/api/market` می‌گیرد؛ اگر آن مسیر رویِ این بانک کار نکند، پرچم‌ها «unavailable»
می‌شود و پاریتیِ واقعی سنجیده نمی‌شود. پس همان DDL و seedِ B1 پایه است و فقط
ستون‌هایِ گم‌شده و جدول‌هایِ mstat رویش می‌نشیند.

خروجی: backend-go/internal/mstat/testdata/fixture/{market.db,user.db}
هیچ دادهٔ واقعی در آن نیست.
"""
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "parity"))
OUT = os.path.join(ROOT, "backend-go", "internal", "mstat", "testdata", "fixture")
DAY = 20261014

# ستون‌هایِ market_watch که کوئریِ mstat می‌خواند و فیکسچرِ تابلو ندارد.
MW_ADD = [("total_shares", "REAL")]
INS_ADD = [("sector_code", "TEXT"), ("total_shares", "REAL"),
           ("base_vol", "REAL"), ("paper_type", "INTEGER"),
           # ستونِ `updated_at` را همین فایل در INSERT نام می‌برد و فیکسچرِ
           # تابلو ندارد؛ بی‌آن، ساختِ فیکسچر در همان ردیفِ اول می‌شکند.
           ("updated_at", "TEXT")]
CT_ADD = [("buy_ddd_vol", "REAL"), ("buy_count_n", "REAL"), ("sell_count_n", "REAL")]
DP_ADD = [("q_tot_cap", "REAL")]

# (کد، نماد، نام، paper_type، صنعت، پایانی، دیروز، آخرین، حجم، ارزش، معاملات،
#  مبنا، تعدادِ سهام، کمینه/بیشینه/مجاز، عمقِ خرید(حجم،ارزش,تعداد)، عمقِ فروش)
# هر ردیف یک قاعدهٔ mstat را قفل می‌کند:
#  m1 فولاد   → +۱۱٫۱۱٪، صفِ خریدِ خالص، clock_pct منفی
#  m2 وبملت   → صفرِ واقعی، عمقِ دوطرفه
#  m3 حق‌تقدم → −۳٪ با صفِ فروش
#  m4 ص.سهامی → صفر، صفِ خرید
#  m5 ص.ثابت  → صفر، صفِ فروش
#  m6 اهرمی   → صفر، صفِ خرید
#  m7 طلا     → صفر، صفِ فروش
#  m8 نقره    → صفر، صفِ خرید
#  m9 اختیار  → کلاسِ other، حجمِ صفر (معامله‌نشده)
EXTRA = [
    ("m1", "فولاد۲", "شرکت فولاد دوم", 1, "فلزات اساسي", 1000.0, 900.0, 950.0,
     1e9, 1e13, 500.0, 1.0, 1e9, 900.0, 1100.0, 2e6, 2e9, 3.0, 0.0, 0.0, 0.0),
    ("m2", "وبملت۲", "بانك ملي دوم", 1, "بانكها و موسسات اعتباري", 500.0, 500.0, 505.0,
     2e9, 1e12, 100.0, 1.0, 5e8, 450.0, 550.0, 1e6, 5e8, 2.0, 1e6, 5e8, 1.0),
    ("m3", "حقا۲", "حق تقدم دوم", 4, "سرمایه گذاريها", 970.0, 1000.0, 960.0,
     1e8, 1e11, 10.0, 1.0, 1e8, 900.0, 1030.0, 0.0, 0.0, 0.0, 5e7, 5e10, 4.0),
    ("m4", "اوج۲", "صندوق س.اوج دماوند-س", 8, "صندوق سرمايه گذاري قابل معامله",
     1000.0, 1000.0, 1000.0, 1e8, 1e11, 5.0, 1.0, 1e8, 900.0, 1100.0,
     1e6, 1e9, 1.0, 0.0, 0.0, 0.0),
    ("m5", "دينا۲", "صندوق س.درآمد ثابت دينا-د", 8, "صندوق سرمايه گذاري قابل معامله",
     1000.0, 1000.0, 1000.0, 1e8, 1e11, 5.0, 1.0, 1e8, 900.0, 1100.0,
     0.0, 0.0, 0.0, 1e6, 1e9, 1.0),
    ("m6", "اهرم۲", "صندوق اهرم آگاه-س", 8, "صندوق سرمايه گذاري قابل معامله",
     1000.0, 1000.0, 1000.0, 1e8, 1e11, 5.0, 1.0, 1e8, 900.0, 1100.0,
     1e6, 1e9, 1.0, 0.0, 0.0, 0.0),
    ("m7", "گلگشت۲", "صندوق سرمايه گذاري طلا گلگشت", 8,
     "صندوق سرمايه گذاري قابل معامله", 1000.0, 1000.0, 1000.0, 1e8, 1e11, 5.0,
     1.0, 1e8, 900.0, 1100.0, 0.0, 0.0, 0.0, 1e6, 1e9, 1.0),
    ("m8", "نقره۲", "صندوق نقره-س", 8, "صندوق سرمايه گذاري قابل معامله",
     1000.0, 1000.0, 1000.0, 1e8, 1e11, 5.0, 1.0, 1e8, 900.0, 1100.0,
     1e6, 1e9, 1.0, 0.0, 0.0, 0.0),
    ("m9", "ضهرم۲", "اختيارخ اهرم-۲", 6, "صندوق سرمايه گذاري قابل معامله",
     0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1e8, 0.0, 0.0,
     0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
]

# ارزشِ ریالیِ مبدأ (client_type_value) — فقط m1 و m3 «native» دارند تا هر سه
# حالتِ value_source پوشش بگیرد: m1 کامل native، m3 نیمه (mixed)، m2 هیچ.
CTV = [("m1", DAY, "native", 2e12, 5e11, 1e12, 2e11),
       ("m3", DAY, "native", 5e10, None, None, None)]

# (buy_i, buy_n, sell_i, sell_n, count_i, count_n, sell_count_i, sell_count_n)
CT = [("m1", 2e8, 5e7, 1e8, 2e7, 1000, 4, 1000, 3),
      ("m2", 1e8, 1e8, 2e8, 1e8, 200, 5, 400, 6),
      ("m3", 5e6, 0.0, 1e6, 0.0, 10, 0, 5, 0),
      ("m4", 4e6, 1e6, 2e6, 1e6, 20, 1, 10, 1),
      ("m5", 1e7, 9e7, 5e6, 8e7, 30, 2, 15, 2),
      ("m6", 3e6, 1e6, 4e6, 1e6, 12, 1, 8, 1),
      ("m7", 2e6, 2e6, 1e6, 1e6, 8, 1, 4, 1),
      ("m8", 1e6, 1e6, 1e6, 1e6, 5, 1, 5, 1),
      ("m9", 0.0, 0.0, 0.0, 0.0, 0, 0, 0, 0)]

# ارزشِ بازارِ رسمی: روزِ جاری زیرِ نصفِ تخمینِ تابلو است تا «رد شدن» آزموده شود؛
# روزِ قبل باورپذیر است. (ر.ک. market_total_rials)
TOTALS = [(DAY, 1e12), (20261013, 6.9e13)]

# ارزشِ معاملاتِ چند نشستِ اخیر (همت) — مبنایِ تداومِ سه‌نشستی.
LIQ = [(20261012, 9.5), (20261013, 12.0), (DAY, 18.0)]


def build_board_fixture(tmp):
    """فیکسچرِ B1 را در پوشۀ موقت می‌سازد و مسیرش را برمی‌گرداند."""
    import make_board_fixture as MBF
    MBF.OUT = tmp
    assert MBF.main() == 0
    return os.path.join(tmp, "market.db")


def add_columns(con, table, cols):
    have = {r[1] for r in con.execute("PRAGMA table_info(%s)" % table)}
    for name, typ in cols:
        if name not in have:
            con.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, name, typ))


def extend(con):
    for table, cols in (("market_watch", MW_ADD), ("instruments", INS_ADD),
                        ("client_type", CT_ADD), ("daily_prices", DP_ADD)):
        add_columns(con, table, cols)
    con.execute("CREATE TABLE market_index (d_even INTEGER PRIMARY KEY, idx_last REAL,"
                " idx_change REAL, idx_pct REAL, ew_last REAL, ew_change REAL,"
                " ew_pct REAL, z_tot_tran REAL, q_tot_cap REAL, q_tot_tran REAL,"
                " updated_at TEXT, market_state TEXT, market_state_title TEXT,"
                " activity_h_even INTEGER)")
    con.execute("CREATE TABLE market_totals (d_even INTEGER PRIMARY KEY,"
                " market_value REAL)")
    con.execute("CREATE TABLE market_liquidity (d_even INTEGER PRIMARY KEY,"
                " value_hemat REAL)")
    con.execute("CREATE TABLE mstat_snap (d_even INTEGER NOT NULL,"
                " h_even INTEGER NOT NULL, ts TEXT, agg TEXT,"
                " PRIMARY KEY (d_even, h_even))")
    # شاخصِ رسمی: نشستِ بستهٔ دیروز (۲۰۲۶۱۰۱۴ چهارشنبه است)؛ وضعیت F = بسته.
    con.execute("INSERT INTO market_index VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (DAY, 7153088.29, -103912.4, -1.43, 1929823.43, -9112.1, -0.47,
                 1.2e5, 6.4e13, 3.1e9, "2026-10-14 12:30:00", "F", "بسته",
                 123000))
    for d, v in TOTALS:
        con.execute("INSERT INTO market_totals VALUES (?,?)", (d, v))
    for d, v in LIQ:
        con.execute("INSERT INTO market_liquidity VALUES (?,?)", (d, v))
    # یک زیرساخت برایِ هر ردیفِ mstat، تا هر جفت‌کردن/پنجره سطر داشته باشد.
    for i, (ic, sym, nm, pt, sec, pcl, py, plst, vol, val, nt, bv, ts,
            amin, amax, bqv, bqval, bqcnt, sqv, sqval, sqcnt) in enumerate(EXTRA):
        con.execute("INSERT INTO instruments (ins_code, l_val18, l_val30, sector_code,"
                    " sector_name, total_shares, base_vol, paper_type, updated_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (ic, sym, nm, "01" if pt != 8 else "68", sec, ts, bv, pt, "f"))
        con.execute("INSERT INTO market_watch (ins_code, d_even, h_even, p_closing,"
                    " p_last, price_yesterday, price_min, price_max, allowed_min,"
                    " allowed_max, price_first, q_tot_tran, q_tot_cap, z_tot_tran,"
                    " price_change, total_shares, buy_q_vol, buy_q_val, buy_q_cnt,"
                    " sell_q_vol, sell_q_val, sell_q_cnt, buy_q1_vol, buy_q1_px,"
                    " sell_q1_vol, sell_q1_px, buy_q1_cnt, fetched_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (ic, DAY, 123000, pcl, plst, py, amin, amax, amin, amax, py,
                     vol, val, nt, pcl - py, ts, bqv, bqval, bqcnt, sqv, sqval,
                     sqcnt, 1e6, pcl, 1e6, pcl, 1.0, "f"))
        # ستون‌ها نام‌برده می‌شوند، نه موقعیتی: DDLِ تابلو ستون‌هایِ صف/تعداد را
        # به ترتیبِ دیگری دارد و این سه ستون با ALTER به آخر می‌چسبند.
        con.execute("INSERT INTO client_type (ins_code, d_even, buy_i_vol, buy_n_vol,"
                    " sell_i_vol, sell_n_vol, buy_ddd_vol, buy_count_i, buy_count_n,"
                    " sell_count_i, sell_count_n) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (ic, DAY, *CT[i][1:5], 0.0, *CT[i][5:]))
        # پیشینهٔ چهار نشست برایِ برآوردِ حجمِ مبنا (فقط m2 مبنا دارد).
        if ic == "m2":
            for d in (20261010, 20261011, 20261012, 20261013):
                con.execute("INSERT INTO daily_prices (ins_code, d_even, p_closing,"
                            " q_tot_tran, q_tot_cap) VALUES (?,?,?,?,?)",
                            (ic, d, 500.0, 1.5e9, 7.5e11))
    for ic, d, kind, *vals in CTV:
        con.execute("INSERT INTO client_type_value (ins_code, d_even, kind, buy_i_val,"
                    " buy_n_val, sell_i_val, sell_n_val) VALUES (?,?,?,?,?,?,?)",
                    (ic, d, kind, *vals))
    con.commit()


def seed_snaps(con, day=DAY, stale=False):
    """سه نقطۀ تایم‌لاین با وضعیتِ تک‌حرفی؛ دو نقطۀ آخر یک چرخش دارند."""
    import base64
    import json
    import zlib

    def blob(states):
        raw = json.dumps(states, separators=(",", ":")).encode()
        return base64.b64encode(zlib.compress(raw, 6)).decode()

    snap_day = day - 1 if stale else day
    pts = [
        (100000, {"val_bt": 10.0, "flow_eq_bt": 1.0, "flow_fixed_bt": -0.5, "pos": 4,
                  "neg": 3, "bq_bt": 2.0, "sq_bt": 1.0, "pc_buy": 120.0,
                  "pc_sell": 100.0, "bq_n": 2, "sq_n": 1, "st": blob({"m1": "b", "m2": "p"})}),
        (110000, {"val_bt": 20.0, "flow_eq_bt": 2.0, "flow_fixed_bt": -0.8, "pos": 5,
                  "neg": 2, "bq_bt": 3.0, "sq_bt": 1.5, "pc_buy": 130.0,
                  "pc_sell": 105.0, "bq_n": 3, "sq_n": 1, "st": blob({"m1": "s", "m2": "p"})}),
        (120000, {"val_bt": 30.0, "flow_eq_bt": 3.0, "flow_fixed_bt": -1.0, "pos": 6,
                  "neg": 1, "bq_bt": 4.0, "sq_bt": 2.0, "pc_buy": 140.0,
                  "pc_sell": 110.0, "bq_n": 4, "sq_n": 1, "st": blob({"m1": "s", "m2": "b"})}),
    ]
    for h, agg in pts:
        agg = dict(agg, d_even=snap_day, h_even=h)
        con.execute("INSERT INTO mstat_snap VALUES (?,?,?,?)",
                    (snap_day, h, "2026-10-14 %02d:%02d:00" % (h // 10000, (h // 100) % 100),
                     json.dumps(agg, separators=(",", ":"), ensure_ascii=False)))
    con.commit()


def main() -> int:
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix="bors-mstat-fix-")
    try:
        build_board_fixture(tmp)
        con = sqlite3.connect(os.path.join(tmp, "market.db"))
        try:
            extend(con)
            seed_snaps(con)
        finally:
            con.close()
        os.makedirs(OUT, exist_ok=True)
        for name in ("market.db", "user.db"):
            shutil.copy2(os.path.join(tmp, name), os.path.join(OUT, name))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("mstat fixture ->", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
