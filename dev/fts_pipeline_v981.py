"""dev/fts_pipeline_v981.py — گارد پایپ‌لاین کدال FTS + چرخش IP با ADB + پنجرهٔ بازار.

سه رفتارِ v9.8.1 را قفل میکند؛ هیچ adb/گوشی/شبکه‌ای لازم نیست — همه مرزها جعل می‌شوند:

  الف) ۵ شاخص بنیادی FTS روی دادهٔ نمونه (in-memory SQLite):
      ۱. رشد فروش تجمیعی YTD نسبت به دورهٔ مشابه سال قبل — شرط > ۴۰٪
      ۲. روند EPS ۳ ساله + ثبت «سود خالص و EPS برای ۳ سال اخیر»
      ۳. حاشیه سود ناخالص (دوره‌ای/سالانه) — شرط > ۳۰٪ (optimal)
      ۴. فروش به ارزش بازار — فرمول «تجمیعی × ۱۲÷ماه ÷ مارکت‌کپ»
      ۵. برچسب «صنعت برتر FTS» (فلزات/سیمان/پتروشیمی/دارو/غذا/…)
  ب) مکانیزم فال‌بک ADB: fetch_page روی 403/429 چرخش IP میزند و با IP
      تازه retry میکند؛ روی Timeout/قطع نشست همان کارت را بازی میکند.
  ج) پنجرهٔ رسمی بازار: نقطهٔ خارج از ۰۹:۰۰–۱۳:۰۰ نوشته و خوانده نمیشود؛
      timeline خروجیِ تمیز میدهد و نقاط شبانه فیلتر میشوند.

اجرا:  python dev/fts_pipeline_v981.py
سوئیت:  در dev/run_all_tests.py ثبت شده است.
"""
import datetime
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "dev"))

CHECKS = []


def ck(cond, msg):
    CHECKS.append((bool(cond), msg))
    return cond


import fts_engine as F  # noqa: E402

DDL = """
CREATE TABLE financial_statements (
    tracing_no INTEGER PRIMARY KEY, symbol TEXT, company_name TEXT, title TEXT,
    report_kind TEXT, period_months INTEGER, period_end TEXT, publish_date TEXT,
    revenue REAL, gross_profit REAL, operating_profit REAL, net_profit REAL,
    total_assets REAL, total_liabilities REAL, total_equity REAL, capital REAL,
    retained_earnings REAL, basic_eps REAL, unit TEXT, url TEXT, fetched_at TEXT);
CREATE TABLE monthly_sales (
    tracing_no INTEGER PRIMARY KEY, symbol TEXT, title TEXT, period_end TEXT,
    year INTEGER, month INTEGER, monthly_revenue REAL, ytd_revenue REAL,
    monthly_revenue_prev REAL, ytd_revenue_prev REAL, pdf_url TEXT, excel_url TEXT);
CREATE TABLE instruments (
    ins_code TEXT PRIMARY KEY, l_val18 TEXT, l_val30 TEXT, sector_code TEXT,
    sector_name TEXT, total_shares REAL, eps REAL, pe REAL, base_vol REAL,
    updated_at TEXT, paper_type INTEGER);
CREATE TABLE market_watch (
    ins_code TEXT PRIMARY KEY, d_even INTEGER, h_even INTEGER, p_closing REAL,
    p_last REAL, price_min REAL, price_max REAL, allowed_min REAL, allowed_max REAL,
    price_yesterday REAL, price_first REAL, q_tot_tran REAL, q_tot_cap REAL,
    z_tot_tran REAL, price_change REAL, eps REAL, pe REAL, total_shares REAL,
    sector_code TEXT, fetched_at TEXT, buy_q_vol REAL, buy_q_val REAL,
    buy_q_cnt REAL, sell_q_vol REAL, sell_q_val REAL, sell_q_cnt REAL,
    buy_q1_vol REAL, buy_q1_px REAL, sell_q1_vol REAL, sell_q1_px REAL,
    market_cap REAL, market_cap_src TEXT);
CREATE TABLE daily_prices (
    ins_code TEXT, d_even INTEGER, p_closing REAL, price_min REAL, price_max REAL,
    price_yesterday REAL, price_first REAL, q_tot_tran REAL, q_tot_cap REAL,
    price_change REAL, fetched_at TEXT, PRIMARY KEY (ins_code, d_even));
"""

AUDITED_ANNUAL = "صورت‌های مالی سال مالی منتهی به %s (حسابرسی شده)"


def seed_fts(conn):
    c = conn.cursor()
    # سه سال EPS صعودی + سود خالص؛ درآمد/حاشیه سال ۱۴۰۴: ۳۵٪ (optimal > 30)
    for i, (yr, eps, np_) in enumerate(((1404, 410.0, 5000.0),
                                        (1403, 300.0, 3800.0),
                                        (1402, 180.0, 2400.0))):
        c.execute("INSERT INTO financial_statements VALUES ("
                  + ",".join("?" * 21) + ")",
                  (9100 + i, "تستF", "شرکت آزمون فلزات",
                   AUDITED_ANNUAL % (str(yr) + "/12/29"),
                   "Financial Statements", 12, f"{yr}/12/29", f"{yr+1}/03/01",
                   120000.0, 42000.0, 38000.0, np_, 80000.0, 30000.0, 50000.0,
                   10000.0, 5000.0, eps, "میلیون ریال", "http://x", "2026"))
    # گزارش‌های ماهانهٔ سال جاری ۱۴۰۵: سه ماه متوالی (۳،۴،۵) با YTD و سال قبل
    for tn, y, m, mr, ytd, mrp, ytdp in (
            (9201, 1405, 3, 14000.0, 14000.0, 9000.0, 9000.0),
            (9202, 1405, 4, 15000.0, 29000.0, 9500.0, 18500.0),
            (9203, 1405, 5, 16000.0, 45000.0, 10000.0, 28500.0)):
        c.execute("INSERT INTO monthly_sales VALUES ("
                  + ",".join("?" * 12) + ")",
                  (tn, "تستF", "گزارش فعالیت ماهانه", f"{y}/{m:02d}/30",
                   y, m, mr, ytd, mrp, ytdp, "http://p", "http://e"))
    c.execute("INSERT INTO instruments VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              ("i_test", "تستF", "شرکت آزمون فلزات", "30", "فلزات اساسي",
               1000.0, 410.0, 10.0, 0.0, "2026", 1))
    # مارکت‌کپ = ۱۰۰۰ سهم × ۵۰۰ ریال = ۵۰۰٬۰۰۰ ریال (p_closing=500)
    # ستونِ رسمیِ `market_cap` (مهاجرت v10) هم پر میشود، چون تک‌منبعِ ارزش بازارِ
    # کارت و موتور همان ستون است — «قیمت × سهام» دیگر هیچ‌جا ساخته نمیشود.
    c.execute("INSERT INTO market_watch VALUES (" + ",".join("?" * 32) + ")",
              ("i_test", 20260910, 101500, 500.0, 500.0, 480.0, 520.0, 400.0, 600.0,
               490.0, 500.0, 1e6, 5e8, 1000.0, 0.0, 410.0, 10.0, 1000.0, "30",
               "2026") + (0.0,) * 10 + (500000.0, "tsetmc_board"))
    c.execute("INSERT INTO daily_prices VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              ("i_test", 20260910, 500.0, 480.0, 520.0, 490.0, 500.0, 1e6, 5e8,
               0.0, "2026"))
    conn.commit()


def mk_fts_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(DDL)
    seed_fts(conn)
    return conn


# ── شاخص ۱: رشد فروش تجمیعی YoY > ۴۰٪ ──
conn = mk_fts_db()
g = F.revenue_growth_yoy(conn, "تستF", min_growth=40.0, sector="فلزات اساسي")
ck(g is not None and g["growth_pct"] == 57.9,
   "شاخص ۱ — رشد YTD 57.9٪ (45000/28500) با مخرجِ دورهٔ مشابه سال قبل (گرفتیم %s)"
   % (g or {}).get("growth_pct"))
ck(bool(g and g["pass"]), "شاخص ۱ — رشد > ۴۰٪ پاس میشود")
ck(bool(g and not g.get("data_gap")),
   "شاخص ۱ — بدون data_gap (ردیف تجمیعی سال قبل موجود است)")

# ── شاخص ۲: EPS ۳ ساله + سود خالص ──
e = F.eps_trend_3y(conn, "تستF", sector="فلزات اساسي")
ck(e is not None and e["eps_series"] == [180.0, 300.0, 410.0],
   "شاخص ۲ — سری EPS ۳ ساله صعودی (180→300→410)")
ck(bool(e and e["pass"]), "شاخص ۲ — سه سال صعودی و سودده پاس میشود")
ck(e is not None and e.get("net_profit_series") == [2400.0, 3800.0, 5000.0],
   "شاخص ۲ — سود خالص ۳ سال هم ثبت میشود (2400→3800→5000)")

# ── شاخص ۳: حاشیه ناخالص ۳۵٪ (سالانهٔ حسابرسی‌شدهٔ غیرتلفیقی) ──
gm = F.gross_margin(conn, "تستF", min_margin=20.0, optimal=30.0)
ck(gm is not None and abs(gm["margin_pct"] - 35.0) < 0.01,
   "شاخص ۳ — حاشیه ناخالص = 42000/120000 = 35٪")
ck(bool(gm and gm["pass"]) and bool(gm and gm["optimal"]),
   "شاخص ۳ — 35٪ هم پاس است هم optimal (> ۳۰٪)")

# ── متنِ «مبنا» که کاربر می‌بیند: برچسب از پرچم‌ها، نه از بریدنِ عنوانِ کدال ──
_raw_title = ("صورت‌های مالی تلفیقی سال مالی منتهی به ۱۴۰۴/۱۲/۲۹ (حسابرسی شده)"
              " — شرکت سهامی عام فولاد مبارکهٔ اصفهان")
gm_ref = {"period_end": "1404-12-29", "fiscal_year": "1404", "title": _raw_title,
          "audited": True, "consolidated": True, "revenue": 120000.0, "gross_profit": 42000.0}
gm_c = F.gross_margin(conn, "تستF", ref=gm_ref)
ck(gm_c is not None and gm_c["basis"] == "تنزل منبع: تلفیقیِ حسابرسی‌شده — سال مالی 1404",
   "شاخص ۳ — تنزل منبع با عنوانِ کاملِ سال و نوعِ صورت: %s" % (gm_c or {}).get("basis"))
ck(gm_c is not None and "حسابرسی ش" not in gm_c["basis"] and "۱۴۰۴/۱۲/۲۹" not in gm_c["basis"],
   "شاخص ۳ — هیچ‌وقت نیمه‌بریدهٔ عنوان کدال نمی‌شود: %s" % (gm_c or {}).get("basis"))
gm_p = F.gross_margin(conn, "تستF", ref=dict(gm_ref, audited=True, consolidated=False))
ck(gm_p is not None and gm_p["basis"].startswith("سالانهٔ حسابرسی‌شدهٔ شرکت اصلی"),
   "شاخص ۳ — مبنای اصلی «حسابرسی‌شدهٔ شرکت اصلی» است: %s" % (gm_p or {}).get("basis"))
gm_u = F.gross_margin(conn, "تستF", ref=dict(gm_ref, audited=False))
ck(gm_u is not None and "حسابرسی‌نشده" in gm_u["basis"],
   "شاخص ۳ — حسابرسی‌نشده صریح برچسب می‌گیرد: %s" % (gm_u or {}).get("basis"))


# ── شاخص ۴: فرمول «تجمیعی × ۱۲÷ماه ÷ مارکت‌کپ» (تصمیمِ مالک: ضریب ثابت ۳×۴ ممنوع) ──
a = F.annualized_sales(conn, "تستF")
ck(a is not None and a["months_used"] == 5,
   "شاخص ۴ — مبنای YTD×۱۲÷ماه انتخاب میشود، نه پنجرهٔ ۳ ماهه (months_used=5، گرفتیم %s)"
   % (a or {}).get("months_used"))
ck(a is not None and abs(a["annual_sales_mrl"] - 108000.0) < 1.0,
   "شاخص ۴ — Annualized = YTD(45٬000) × ۱۲÷۵ = 108٬000 (گرفتیم %s)"
   % (a or {}).get("annual_sales_mrl"))
ck(a is not None and "× ۱۲÷5" in (a.get("basis") or ""),
   "شاخص ۴ — basis برچسبِ مبنا را توضیح میدهد: %s" % (a or {}).get("basis"))
s2m = F.sales_to_marketcap(conn, "تستF", 500_000.0, min_ratio=1.0, annual=a)
ck(s2m is not None and abs(s2m["sales_to_mcap"] - 216000.0) < 0.5,
   "شاخص ۴ — نسبت = 108000×1e6÷500000 = 216٬000 (گرفتیم %s)"
   % (s2m or {}).get("sales_to_mcap"))
# ستونِ فروشِ ماهانهٔ جاافتاده: YTD دست‌نخورده می‌ماند، پس مبنا هم همان است.
conn.execute("UPDATE monthly_sales SET monthly_revenue=NULL WHERE month=4")
conn.commit()
a2 = F.annualized_sales(conn, "تستF")
ck(a2 is not None and a2["months_used"] == 5
   and abs(a2["annual_sales_mrl"] - 108000.0) < 1.0,
   "شاخص ۴ — ماهِ پرش‌دار بی‌اعتبار، YTD سالم (months=5، گرفتیم %s / %s)"
   % ((a2 or {}).get("months_used"), (a2 or {}).get("annual_sales_mrl")))
# آخرین ماهِ دارای گزارش حذف شود → م از همان‌جا ۴ read میشود، نه از تقویم.
conn.execute("DELETE FROM monthly_sales WHERE month=5")
conn.commit()
a3 = F.annualized_sales(conn, "تستF")
ck(a3 is not None and a3["months_used"] == 4
   and abs(a3["annual_sales_mrl"] - 87000.0) < 1.0,
   "شاخص ۴ — م = بزرگ‌ترین ماهِ دارای گزارش (۴ ⇒ YTD 29٬000×۳ = 87٬000، گرفتیم %s / %s)"
   % ((a3 or {}).get("months_used"), (a3 or {}).get("annual_sales_mrl")))
conn.close()

# ── شاخص ۵: برچسب صنعت برتر FTS ──
for sector, want_verdict, want_top in (("فلزات اساسي", "free", True),
                                        ("سیمان، آهک و گچ", "free", True),
                                        ("مواد و محصولات دارویی", "neutral", False),
                                        ("بانك", "neutral", False)):
    r = F.sector_filter(sector)
    ck(r["verdict"] == want_verdict,
       "شاخص ۵ — «%s» ⇒ %s" % (sector, want_verdict))
    ck(bool(r.get("fts_top_industry")) == want_top,
       "شاخص ۵ — برچسب صنعت برتر FTS برای «%s» = %s" % (sector, want_top))
ck(F.sector_filter("فلزات اساسي")["pass"],
   "شاخص ۵ — فلزات (قیمت‌گذاری آزاد) پاس است")
ck(F.sector_filter("مواد و محصولات دارویی")["pass"],
   "شاخص ۵ — دارو استثنای مجازِ v2.1 است (نه ردِ مطلق؛ دروازهٔ GPM>۵۰٪ در F-03 اعمال می‌شود)")

# ── هم‌ارزی مسیر تک‌نمادی ⇄ دسته‌ای (پاریتی شاخص ۴) ──
conn = mk_fts_db()
single = F.scan_symbol(conn, "تستF", 500_000.0, 500_000.0, "فلزات اساسي", cfg={})
bulk = [r for r in F.bulk_scan(conn, cfg={}) if r["symbol_norm"] == F.norm_fa("تستF")]
ck(len(bulk) == 1, "bulk_scan دقیقاً یک ردیف برای نماد آزمون میدهد")
ck(bool(bulk) and bulk[0]["sales_to_mcap"]
   == single["detail"]["sales_to_mcap"]["sales_to_mcap"],
   "پاریتی شاخص ۴: scan_symbol (%s) == bulk_scan (%s)"
   % (single["detail"]["sales_to_mcap"]["sales_to_mcap"],
      bulk[0]["sales_to_mcap"] if bulk else None))
ck(bool(bulk) and bulk[0]["annualize_months"] == 5,
   "bulk_scan هم همان مبنای YTD×۱۲÷ماه را برمی‌دارد (months=5)")
conn.close()


# ─────────────────────── ب) فال‌بک ADB روی 403/429/Timeout ───────────────────────
import codal_fetcher as cf  # noqa: E402

_ORIG_FIND_ADB = cf._find_adb
_ORIG_ROTATE = cf.rotate_ip_via_adb
_ORIG_POLITE = cf.POLITE
_ORIG_POLITE_PAUSE = cf.polite_pause
_ORIG_CONTROL_SLEEP = cf._control_sleep


class FakeResp:
    def __init__(self, status):
        self.status_code = status
        self.text = ""
        self.headers = {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return {"Letters": [{"TracingNo": 1, "Title": "گزارش فعالیت ماهانه",
                             "Symbol": "تستF", "Url": "/x"}], "Total": 1}


def mock_fetch_page(status_seq, rotate_results, max_retries=2):
    """fetch_page با مرزهای جعلی؛ خروجی (letters, n_rotations, sleeps).

    status_seq: هر عضو یا int (کد HTTP) یا Exception (قطع نشست/Timeout).
    rotate_results: خروجی‌های متوالی rotate_ip_via_adb (True/False).
    """
    state = {"i": 0, "rot": 0, "sleeps": []}

    cf.POLITE = False
    cf._find_adb = lambda: "C:\\adb\\platform-tools\\adb.exe"

    def fake_rotate(quiet=False):
        res = rotate_results[min(state["rot"], len(rotate_results) - 1)]
        state["rot"] += 1
        return res

    cf.rotate_ip_via_adb = fake_rotate
    cf.polite_pause = lambda *a, **k: None
    cf._control_sleep = lambda s: state["sleeps"].append(s)

    class FakeSession:
        def get(self, url, headers=None, timeout=60):
            i = min(state["i"], len(status_seq) - 1)
            state["i"] += 1
            item = status_seq[i]
            if isinstance(item, Exception):
                raise item
            return FakeResp(item)

    s = FakeSession()
    try:
        letters = cf.fetch_page(s, 1, max_429_retries=max_retries, quiet=True)
        return letters, state["rot"], state["sleeps"]
    finally:
        cf._find_adb = _ORIG_FIND_ADB
        cf.rotate_ip_via_adb = _ORIG_ROTATE
        cf.POLITE = _ORIG_POLITE
        cf.polite_pause = _ORIG_POLITE_PAUSE
        cf._control_sleep = _ORIG_CONTROL_SLEEP


# 403 → چرخش ADB → retry موفق با IP تازه
letters, rot, _ = mock_fetch_page([403, 200], [True])
ck(rot >= 1 and isinstance(letters, list) and letters,
   "403 ⇒ چرخش IP با ADB و retry موفق (%d چرخش، %d نامه)" % (rot, len(letters or [])))


# ─────────────────────── ج) پنجرهٔ رسمی بازار ۰۹:۰۰–۱۳:۰۰ ───────────────────────
import mstat_engine as ME  # noqa: E402

for h, want in ((90000, True), (85500, True), (130000, True), (130005, True),
                (85499, False), (130006, False), (205919, False), (180000, False),
                (None, False), (0, False)):
    got = ME.in_trading_session(h)
    ck(got == want, "in_trading_session(%s) = %s" % (h, want))

import test_tsetmc as TS  # noqa: E402
ck(TS.save_mstat_snapshot is not None,
   "test_tsetmc هنوز save_mstat_snapshot را import میکند (فال‌بک resilience)")

ME_DDL = """
CREATE TABLE mstat_snap (d_even INTEGER NOT NULL, h_even INTEGER NOT NULL,
ts TEXT, agg TEXT, PRIMARY KEY (d_even, h_even));
"""
BASE_AGG = {"d_even": 20260910, "h_even": 100000, "val_bt": 1.0,
            "flow_eq_bt": 0.0, "flow_fixed_bt": 0.0, "pc_buy": None,
            "pc_sell": None, "pos": 1, "neg": 0, "zero": 0, "bq_bt": 0.0,
            "sq_bt": 0.0, "bq_n": 0, "sq_n": 0, "st": ""}

sat = datetime.datetime(2026, 9, 12, 10, 0)    # شنبه — روز کاریِ درون پنجره
thu = datetime.datetime(2026, 9, 10, 22, 30)    # پنجشنبه شب — خارج از هر دو شرط

ck(ME.in_trading_session(100000, sat) is True,
   "شنبه ۱۰:۰۰ درون پنجره است")
ck(ME.in_trading_session(100000, thu) is False,
   "پنجشنبه شب — حتی با h_even معتبر — نقطه نوشته نمیشود")


def snap_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(ME_DDL)
    return conn


# شب ⇒ ذخیره رد (زمانِ تزریقی — الگوی m141_hit برای تست)
c2 = snap_db()
rj = ME.save_mstat_snapshot(c2, dict(BASE_AGG, h_even=100000), when=thu)
n_rows = c2.execute("SELECT COUNT(*) FROM mstat_snap").fetchone()[0]
ck(rj.get("saved") is False and rj.get("reason") == "outside_trading_session"
   and n_rows == 0,
   "save_mstat_snapshot در شب ⇒ saved=False و هیچ ردیفی نوشته نمیشود")

# روز کاری + ساعت کاری ⇒ ذخیره میشود
c3 = snap_db()
rok = ME.save_mstat_snapshot(c3, dict(BASE_AGG, h_even=100000), when=sat)
n_rows3 = c3.execute("SELECT COUNT(*) FROM mstat_snap").fetchone()[0]
ck(rok.get("saved") is True and n_rows3 == 1,
   "save_mstat_snapshot شنبه ۱۰:۰۰ ⇒ نقطه مینشیند")

# _points نقاط خارج از بازار را فیلتر میکند (شبیه‌سازیِ دادهٔ آلودهٔ فعلی)
c4 = snap_db()
for h in (90000, 100000, 110000, 120000, 125808):
    c4.execute("INSERT INTO mstat_snap VALUES (?,?,?,?)",
               (20260910, h, "x", json.dumps(dict(BASE_AGG, h_even=h))))
# دو ردیف آلودهٔ شبانه — همان‌هایی که در market.db واقعی دیده شد
c4.execute("INSERT INTO mstat_snap VALUES (?,?,?,?)",
           (20260910, 180000, "x", json.dumps(dict(BASE_AGG, h_even=180000))))
c4.execute("INSERT INTO mstat_snap VALUES (?,?,?,?)",
           (20260910, 205919, "x", json.dumps(dict(BASE_AGG, h_even=205919))))
c4.commit()
tl = ME.timeline(c4)
hs = list(tl["series"]["t"])
ck(all("08:55" <= t <= "13:00" for t in hs),
   "timeline فقط نقاط درون پنجره را برمی‌گرداند (%s)" % hs)
ck(len(hs) == 5,
   "پنج نقطهٔ معتبر حفظ و دو نقطهٔ شبانه حذف شدند (گرفتیم %d)" % len(hs))
ck(tl["points"] == 5, "points=5 پس از فیلتر پنجره")
ph = ME.phases(c4)
ck(ph["ready"] is True, "phases هم از نقاط فیلترشده تغذیه میشود")
ck(tl.get("session_open") == "08:55" and tl.get("session_close") == "13:00",
   "timeline پنجرهٔ بازار را برای UI اعلام میکند (%s-%s)"
   % (tl.get("session_open"), tl.get("session_close")))

# اسکیمای ساخت: سناریوی «درون پنجره ولی ساعتِ DB قدیمی» — فیلتر SQL مستقل از now
c5 = snap_db()
c5.execute("INSERT INTO mstat_snap VALUES (?,?,?,?)",
           (20260908, 180000, "x", json.dumps(dict(BASE_AGG, d_even=20260908,
                                                   h_even=180000))))
c5.commit()
tl5 = ME.timeline(c5)
ck(tl5["points"] == 0,
   "روزِ فقط-شبانه در تایم‌لاین خالی میماند (نقاط=%d)" % tl5["points"])

# ─────────────────────── گزارش ───────────────────────
n_bad = sum(1 for ok, _ in CHECKS if not ok)
for ok, msg in CHECKS:
    print("  %s %s" % ("PASS" if ok else "FAIL", msg))
print("\n%d checks, %d failed" % (len(CHECKS), n_bad))
print("FTS PIPELINE v9.8.1 OK" if not n_bad else "FTS PIPELINE v9.8.1 FAILED")
sys.exit(1 if n_bad else 0)

# 429 → چرخش ADB → retry موفق
letters, rot, _ = mock_fetch_page([429, 200], [True])
ck(rot >= 1 and isinstance(letters, list) and letters,
   "429 ⇒ چرخش IP با ADB و retry موفق (%d چرخش)" % rot)

# Timeout/قطع نشست → چرخش ADB → retry موفق
import requests as _rq  # noqa: E402
letters, rot, _ = mock_fetch_page(
    [_rq.exceptions.Timeout("read timed out"), 200], [True], max_retries=2)
ck(rot >= 1 and isinstance(letters, list) and letters,
   "Timeout/قطع نشست ⇒ چرخش IP با ADB و retry موفق (%d چرخش)" % rot)

# ADB چرخش نداد (گوشی نیست) → backoff نمایی، بدون رگرسیون
letters, rot, sleeps = mock_fetch_page([403, 403, 403, 403], [False], max_retries=3)
ck(letters in (None, []),
   "403 پایدار بدون ADB ⇒ خروجی None/[] و توقف تمیز (چرخش=%d)" % rot)
ck(len(sleeps) >= 2, "بدون ADB ⇒ backoff نمایی زده میشود (%d خواب)" % len(sleeps))
