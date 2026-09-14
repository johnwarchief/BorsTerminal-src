# -*- coding: utf-8 -*-
"""dev/test_fts_market_cap.py — ارزش بازار: تک‌منبعِ TSETMC + فیلترهای ریسک v10

قفل‌ها (چرا این فایل متولد شد):
  * ارزش بازار بیرون از موتور همگام‌سازی هیچ‌جا حساب نمیشود؛ API فقط ستونِ
    `market_watch.market_cap` را می‌خواند — نه p_closing*total_shares.
  * فیلدِ خامِ تابلو (qTotCap) بر هر محاسبه‌ای اولویت دارد؛ محاسبه فقط از دو
    فیلدِ **همان ردیفِ تابلو** است و منبعش در market_cap_src ثبت میشود.
  * صفر/منفی/NULL/NaN هرگز «ارزش بازارِ صفر» نیست؛ None + پرچمِ خطاست، تا
    شاخص ۴ بر صفر تقسیم نکند و «رد» با «قابل محاسبه نبود» قاطی نشود.
  * fallback = آخرین مقدارِ معتبرِ ذخیره‌شده (daily_prices)، نه صفرِ امروز.
  * یکا: ۱ همت = ۱۰^۱۳ ریال (همان قاعده‌ای که UI در fmtMcap مصرف میکند).
  * ماده ۱۴۱ و Include/Excludeِ صنایع روی نوشتارِ عربی/فارسی حساس نباشند.

اجرا:  python dev/test_fts_market_cap.py     (بدون سرور، روی DB ساختگی)
"""
import os, shutil, sqlite3, sys, tempfile

try:                       # پیامهایِ فارسی روی کنسولِ cp1252 ویندوز
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

import test_tsetmc as T
import fts_engine
from api import fundamental as FD

CHECKS = []


def ck(cond, msg):
    CHECKS.append((bool(cond), msg))
    return cond


# DDL «پیش از مهاجرت» — ستونِ market_cap عمداً نیست تا خود-ترمیمیِ
# مسیرِ خواندن هم آزموده شود.
DDL = """
CREATE TABLE instruments (
    ins_code TEXT PRIMARY KEY, l_val18 TEXT, l_val30 TEXT, sector_code TEXT,
    sector_name TEXT, total_shares REAL, eps REAL, pe REAL, base_vol REAL,
    updated_at TEXT, paper_type INTEGER);
CREATE TABLE market_watch (
    ins_code TEXT PRIMARY KEY, d_even INTEGER, h_even INTEGER, p_closing REAL,
    p_last REAL, price_min REAL, price_max REAL, allowed_min REAL, allowed_max REAL,
    price_yesterday REAL, price_first REAL, q_tot_tran REAL, q_tot_cap REAL,
    z_tot_tran REAL, price_change REAL, eps REAL, pe REAL, total_shares REAL,
    sector_code TEXT, fetched_at TEXT);
CREATE TABLE daily_prices (
    ins_code TEXT, d_even INTEGER, p_closing REAL, price_min REAL, price_max REAL,
    price_yesterday REAL, price_first REAL, q_tot_tran REAL, q_tot_cap REAL,
    price_change REAL, fetched_at TEXT, PRIMARY KEY (ins_code, d_even));
CREATE TABLE financial_statements (
    tracing_no INTEGER PRIMARY KEY, symbol TEXT, company_name TEXT, title TEXT,
    report_kind TEXT, period_months INTEGER, period_end TEXT, publish_date TEXT,
    revenue REAL, gross_profit REAL, operating_profit REAL, net_profit REAL,
    total_assets REAL, total_liabilities REAL, total_equity REAL, capital REAL,
    retained_earnings REAL, basic_eps REAL, unit TEXT, url TEXT, fetched_at TEXT);
"""


def make_db(migrate=True):
    """C1 عددِ امروز دارد · C2 امروز NULL و دیروزِ معتبر · C3 صفرِ جعلی · C4 عربی."""
    path = os.path.join(tempfile.mkdtemp(prefix="ftsmcap_"), "market.db")
    con = sqlite3.connect(path)
    con.executescript(DDL)
    con.execute("INSERT INTO instruments VALUES ('C1','فولاد','فولاد مبارکه','1','فلزات اساسی',"
                "1000000.0,500,10,1,'2026-09-09',1)")
    con.execute("INSERT INTO instruments VALUES ('C2','شبندر','پتروشیمی بندر','2','شیمیایی',"
                "2000000.0,300,8,1,'2026-09-09',1)")
    con.execute("INSERT INTO instruments VALUES ('C3','خودرو','ایران خودرو','3','خودروها',"
                "3000000.0,-40,0,1,'2026-09-09',1)")
    con.execute("INSERT INTO instruments VALUES ('C4','داریک','دارویی داریک','4','دارو',"
                "4000000.0,900,12,1,'2026-09-09',1)")
    for ins, d, px, sh, sec in (("C1", 20260909, 2881.0, 1000000.0, "1"),
                                ("C2", 20260909, 13920.0, 2000000.0, "2"),
                                ("C3", 20260909, 747.0, 3000000.0, "3"),
                                ("C4", 20260909, 9100.0, 4000000.0, "4")):
        con.execute("INSERT INTO market_watch (ins_code,d_even,p_closing,total_shares,sector_code)"
                    " VALUES (?,?,?,?,?)", (ins, d, px, sh, sec))
    con.execute("INSERT INTO daily_prices VALUES ('C2',20260908,13900,1,1,1,1,1,1,1,'t')")
    if migrate:
        T.ensure_market_cap_schema(con)
    con.commit()
    return path, con


def seed_caps(con, values):
    con.executemany("UPDATE market_watch SET market_cap=?, market_cap_src=? WHERE ins_code=?",
                    values)
    con.commit()



# ═══════════════════════════════════════════════════════════════════════════
#  ۱) writer: board_market_cap — فیلدِ خام بر محاسبه ترجیح دارد
# ═══════════════════════════════════════════════════════════════════════════
v, s = T.board_market_cap({"qTotCap": 5.57e15, "pcl": 2881.0, "ztd": 1.935e12})
ck(v == 5.57e15 and s == T.MCAP_SRC_RAW, "raw qTotCap wins over any calculation (%s/%s)" % (v, s))

v, s = T.board_market_cap({"pcl": 2881.0, "ztd": 1.0e9})
ck(v is not None and abs(v - 2.881e12) < 1 and s == T.MCAP_SRC_BOARD,
   "no raw field → pcl*ztd from the SAME board row (%s/%s)" % (v, s))

for bad, label in (({"pcl": 0.0, "ztd": 1e9}, "price=0"),
                   ({"pcl": -5.0, "ztd": 1e9}, "price<0"),
                   ({"pcl": 100.0, "ztd": 0.0}, "shares=0"),
                   ({"pcl": None, "ztd": None}, "both null"),
                   ({}, "empty row")):
    v, s = T.board_market_cap(bad)
    ck(v is None and s == "", "%s → None (never a fake zero)" % label)

v, s = T.board_market_cap({"qTotCap": 0.0, "pcl": 1000.0, "ztd": 10.0})
ck(v == 10000.0 and s == T.MCAP_SRC_BOARD, "qTotCap=0 is not a value → falls back to board row")

# مهاجرت idempotent است و منبعِ backfill را از مقدارِ زنده جدا علامت می‌زند
path, con = make_db(migrate=False)
T.ensure_market_cap_schema(con)
cols = [r[1] for r in con.execute("PRAGMA table_info(market_watch)")]
T.ensure_market_cap_schema(con)
cols2 = [r[1] for r in con.execute("PRAGMA table_info(market_watch)")]
ck("market_cap" in cols and cols.count("market_cap") == 1,
   "ensure_market_cap_schema adds the column exactly once")
ck(cols == cols2, "ensure_market_cap_schema is idempotent")
row = con.execute("SELECT market_cap, market_cap_src FROM market_watch "
                  "WHERE ins_code='C1'").fetchone()
ck(row[0] == 2881.0 * 1000000.0 and row[1] == T.MCAP_SRC_BACKFILL,
   "migration backfills from the SAME stored row, tagged as backfill (%r)" % (row,))
con.close()
shutil.rmtree(os.path.dirname(path), ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════════
#  ۲) reader: get_tsetmc_market_cap_info — فقط خواندن، با پرچمِ خطا
# ═══════════════════════════════════════════════════════════════════════════
path, con = make_db()
seed_caps(con, [(5.57e15, "tse_raw", "C1"), (None, None, "C2"),
                (0.0, "tse_board_calc", "C3"), (4.0e13, "tse_board_calc", "C4")])
con.execute("UPDATE daily_prices SET market_cap=4.0e15, market_cap_src='tse_board_calc' "
            "WHERE ins_code='C2' AND d_even=20260908")
con.commit()

i1 = FD.get_tsetmc_market_cap_info("فولاد", db=con)
ck(i1["rials"] == 5.57e15 and i1["error"] is None and i1["source"] == "tse_raw",
   "today's stored cap is read verbatim, with provenance (%r)" % (i1["source"],))
ck(i1["hmt"] is not None and abs(i1["hmt"] - 557.0) < 0.01, "hmt = rials / 1e13 (%s)" % i1["hmt"])

i2 = FD.get_tsetmc_market_cap_info("شبندر", db=con)
ck(i2["rials"] == 4.0e15 and i2["stale"] is True and i2["error"] is None,
   "null today → latest recorded valid from daily_prices, flagged stale (asof=%r)" % (i2["asof"],))

i3 = FD.get_tsetmc_market_cap_info("خودرو", db=con)
ck(i3["rials"] is None and i3["error"] == FD.MCAP_ERR_NO_VALUE,
   "stored 0 is NO DATA, not a real market cap (%r)" % (i3["error"],))

i4 = FD.get_tsetmc_market_cap_info("ناموجود", db=con)
ck(i4["rials"] is None and i4["error"] == FD.MCAP_ERR_NO_ROW,
   "unknown symbol → symbol_not_on_board, never 0 (%r)" % (i4["error"],))

ck(FD.get_tsetmc_market_cap("فولاد", db=con) == 5.57e15,
   "thin accessor returns the number for consumers that only want it")
ck(FD.get_tsetmc_market_cap("خودرو", db=con) is None,
   "thin accessor returns None (not 0.0) when the board has no valid cap")

tot, src = FD.board_total_market_cap(con)
ck(abs(tot - (5.57e15 + 4.0e13)) < 1 and src == "market_watch.market_cap",
   "total market cap is the SUM of the stored column only (%r, %r)" % (tot, src))

# نوشتارِ عربیِ همان نماد باید به همان سطر برسد (تلهٔ کلاسیکِ norm_fa)
ck(FD.get_tsetmc_market_cap("داریک", db=con) == 4.0e13, "Persian spelling resolves")
con.execute("UPDATE instruments SET l_val18='داريك' WHERE ins_code='C4'")   # ي عربی
con.commit()
ck(FD.get_tsetmc_market_cap("داریک", db=con) == 4.0e13,
   "Arabic-script row is still found by the Persian query")

# DB کهنه (بی‌ستون) → خود-ترمیم، نه crash و نه صفر
pathL, conL = make_db(migrate=False)
infoL = FD.get_tsetmc_market_cap_info("فولاد", db=conL)
ck(infoL["rials"] is not None and infoL["rials"] > 0,
   "reader migrates a pre-v10 market.db on the fly instead of returning 0 (%r)" % (infoL["rials"],))
ck(FD._MCAP_COLS.get((id(conL), "market_watch")) is True,
   "column probe cache is refreshed after the self-heal migration")
con.close()
conL.close()
for p in (path, pathL):
    shutil.rmtree(os.path.dirname(p), ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════════
#  ۳) یکاها: ۱ همت = ۱۰^۱۳ ریال
# ═══════════════════════════════════════════════════════════════════════════
ck(FD.HEMMAT_RIAL == 1e13, "HEMMAT_RIAL is locked to 10^13 Rials")
ck(abs(FD.hmt_to_rials(2.0) - 2e13) < 1, "hmt_to_rials(2) = 2e13 Rials")
ck(FD.hmt_to_rials("") == 0.0 and FD.hmt_to_rials(None) == 0.0,
   "empty hmt input → 0 (filter stays off), never a spurious floor")
ck(FD.hmt_to_rials("abc") == 0.0, "garbage hmt input → 0.0, no exception")


# ═══════════════════════════════════════════════════════════════════════════
#  ۴) فیلتر صنعت Include/Exclude — نرمال‌سازیِ فارسی/عربی و ویرگولِ فارسی
# ═══════════════════════════════════════════════════════════════════════════
lst = FD.norm_industry_list("پتروشیمی، سیمان,Folad , خودرو")
ck(len(lst) == 4 and "پتروشیمی" in lst,
   "comma parser accepts both ',' and '،' and trims (%r)" % (lst,))
ck(FD.norm_industry_list("بیمه،بيمه") == FD.norm_industry_list("بيمه،بیمه"),
   "arabic/persian spellings normalise the same way")
ck(FD.norm_industry_list(None) == [] and FD.norm_industry_list("") == []
   and FD.norm_industry_list([]) == [], "empty industry list → [] (no crash)")
ck(FD.norm_industry_list([" سیمان ", "سیمان", ""]) == [fts_engine.norm_fa("سیمان")],
   "list input is accepted too and duplicates collapse")

g = FD.industry_gate("گروه پتروشیمی ها", {"industry_mode": "Include_Industries",
                                          "include_industries": "سیمان، فلزات"})
ck(g["active"] and not g["pass"] and g["reason"],
   "Include_Industries drops a petrochemical when the list only allows سیمان/فلزات")
g = FD.industry_gate("گروه پتروشیمی ها", {"industry_mode": "Include_Industries",
                                          "include_industries": "پتروشیمی، سیمان"})
ck(g["active"] and g["pass"], "Include_Industries keeps a listed industry (substring match)")
g = FD.industry_gate("گروه خودروسازی", {"industry_mode": "Include_Industries",
                                        "include_industries": "خودرو"})
ck(g["pass"], "include matches by substring, not equality (خودروسازی ⊃ خودرو)")
g = FD.industry_gate("گروه خودروسازی", {"industry_mode": "Exclude_Industries",
                                        "exclude_industries": "خودرو، دارو"})
ck(g["active"] and not g["pass"], "Exclude_Industries drops the excluded industry")
g = FD.industry_gate("گروه خودروسازی", {"industry_mode": "Rank_Only",
                                        "exclude_industries": "خودرو"})
ck(not g["active"] and g["pass"], "Rank_Only leaves the manual industry list inert")
g = FD.industry_gate("گروه فلزات", {"industry_mode": "Include_Industries",
                                    "include_industries": ""})
ck(g["active"] and not g["pass"],
   "Include mode with an EMPTY list drops everything (explicit, not accidental)")



# ═══════════════════════════════════════════════════════════════════════════
#  ۵) ماده ۱۴۱ — زیان انباشته > نصفِ سرمایه
# ═══════════════════════════════════════════════════════════════════════════
path5, con5 = make_db()
con5.execute("INSERT INTO financial_statements (tracing_no,symbol,company_name,title,"
             "period_months,period_end,publish_date,total_equity,capital) VALUES "
             "(1,'خودرو','ایران خودرو','صورت مالی 12 ماهه حسابرسی شده',12,'1404-12-29',"
             "'2025-04-01',40000000,100000000)")     # خالصِ ۴۰٪ سرمایه → مشمول
con5.execute("INSERT INTO financial_statements (tracing_no,symbol,company_name,title,"
             "period_months,period_end,publish_date,total_equity,capital) VALUES "
             "(2,'فولاد','فولاد مبارکه','صورت مالی 12 ماهه حسابرسی شده',12,'1404-12-29',"
             "'2025-04-01',90000000,100000000)")     # ۹۰٪ → سالم
con5.commit()
m = fts_engine.m141_map(con5)
ck(m.get(fts_engine.norm_fa("خودرو")) is True and m.get(fts_engine.norm_fa("فولاد")) is False,
   "m141 map flags the loss-making symbol only (%r)" % (m,))
r_on = FD.risk_gates(con5, "خودرو", "خودروها", 1e15, cfg={"filter_m141": True}, m141_map=m)
ck(any("ماده ۱۴۱" in x for x in r_on),
   "filter_m141 ON → dropped immediately, with a Persian reason")
r_off = FD.risk_gates(con5, "خودرو", "خودروها", 1e15, cfg={"filter_m141": False}, m141_map=m)
ck(not any("ماده ۱۴۱" in x for x in r_off), "filter_m141 OFF → no m141 exclusion")
r_ok = FD.risk_gates(con5, "فولاد", "فلزات اساسی", 1e15, cfg={"filter_m141": True}, m141_map=m)
ck(not any("ماده ۱۴۱" in x for x in r_ok), "healthy equity/capital is never dropped")
r_no = FD.risk_gates(con5, "شبندر", "شیمیایی", 1e15, cfg={"filter_m141": True}, m141_map=m)
ck(not any("ماده ۱۴۱" in x for x in r_no),
   "no annual statement → NOT flagged by m141 (missing data is not accumulated loss)")

# کف ارزش بازار (همت → ریال)
ck(any("زیرِ کف" in x for x in
       FD.risk_gates(con5, "فولاد", "فلزات", 5.0e12, cfg={"mcap_min_hmt": 1.0})),
   "0.5-همت symbol under a 1-همت floor is dropped")
ck(not FD.risk_gates(con5, "فولاد", "فلزات", 5.0e13, cfg={"mcap_min_hmt": 1.0}),
   "5-همت symbol clears a 1-همت floor")
ck(any("نامشخص" in x for x in
       FD.risk_gates(con5, "فولاد", "فلزات", None, cfg={"mcap_min_hmt": 1.0})),
   "missing mcap + floor set → honest 'cannot check', never a silent pass")
con5.close()
shutil.rmtree(os.path.dirname(path5), ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════════
#  ۶) شاخص ۴ روی ارزش بازارِ نامعتبر نمی‌شکند
# ═══════════════════════════════════════════════════════════════════════════
annual = {"annual_sales_mrl": 1e7, "annual_sales_bt": 100.0, "months_used": 12,
          "scale_factor": 1.0, "basis": "test", "reconciled": True}
gm = {"margin_pct": 40.0, "na": False}
v0 = FD.ind4_valuation(annual, gm, None)
ck(v0["available"] is False and v0["pass"] is False,
   "ind4 with market_cap=None → not available, no ZeroDivisionError")
v1 = FD.ind4_valuation(annual, gm, 2.0e13)
ck(v1["available"] and abs(v1["sales_to_mcap"] - 0.5) < 1e-9,
   "ind4 math unchanged for a valid cap (1e7 MRL = 1e13 Rial / 2e13 = %s)" % v1["sales_to_mcap"])
th_lo = FD.v10_thresholds({"v10_sales_to_mcap_min": 0.33})
ck(th_lo["sales_to_mcap_min"] == 0.33, "sales/mcap floor is user-settable from the panel")
ck(FD.ind4_valuation(annual, gm, 2.5e13, th=th_lo)["sales_pass"] is True,
   "at the 0.33 setting a 0.4 ratio passes")
ck(FD.v10_thresholds()["sales_to_mcap_min"] == 0.33,
   "the جزوه default for فروش÷ارزش is 0.33 (not the old 1.0×)")
th_hi = FD.v10_thresholds({"v10_sales_to_mcap_min": 0.5})
ck(FD.ind4_valuation(annual, gm, 2.5e13, th=th_hi)["sales_pass"] is False,
   "a stricter 0.5 setting still fails the same 0.4 ratio — the knob really bites")
ck(FD.ind4_valuation(annual, gm, 2.5e13)["potential_pct"] == 16.0,
   "profit potential = 0.4 × 40%% = 16%% under a 1.0× cap (%s)"
   % FD.ind4_valuation(annual, gm, 2.5e13)["potential_pct"])

print("\n".join("%s %s" % ("PASS" if ok else "FAIL", msg) for ok, msg in CHECKS))
bad = [msg for ok, msg in CHECKS if not ok]
print("%d/%d passed" % (len(CHECKS) - len(bad), len(CHECKS)))
sys.exit(1 if bad else 0)

