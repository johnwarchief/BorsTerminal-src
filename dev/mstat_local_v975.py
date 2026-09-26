"""v9.7.5 — گارد فاز ۱: داشبورد «وضعیت بازار» محلی (mstat_engine).

چرا این تست متولد شد: تب وضعیت بازار پیش‌تر پروکسیِ tradersarena.ir بود؛ با
قطعیِ اینترنت یا تغییرِ ساختارِ آن سرویس کل تب می‌مرد و هیچ عددی قابل
بازبینی نبود. فاز ۱ همان پنل‌ها را از market.db می‌سازد — پس باید قفل شود که
۱) ارقام از دادهٔ لوکال و با یکای درست درمی‌آیند، ۲) «بی‌داده» هیچ‌وقت صفرِ
سبز/قرمز نمی‌شود، ۳) ستون‌های مرتب‌شدنی واقعاً مرتب می‌شوند (باگِ کلیدِ سرتیب
همین‌جا گرفته شد)، ۴) رندرِ کل تب به یک اسکنِ بانک می‌ماند نه N کوئری به‌ازای
هر نماد، ۵) همگام‌سازی همان ستون‌هایی را می‌نویسد که موتور می‌خواند.

داده: بانکِ درون‌حافظه‌ای با ارقامِ دست‌چین — همهٔ انتظارها حسابِ دستی‌اند.
اجرا:  python dev/mstat_local_v975.py
"""
import io
import json
import os
import re
import sqlite3
import sys
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

CHECKS = []


def ck(cond, msg):
    CHECKS.append((bool(cond), msg))
    return cond


import mstat_engine as ME

MW_COLS = 32   # تعدادِ ستونِ market_watch — در seed و در INSERT همگام‌سازی قفل می‌شود
# v10: دو ستونِ ارزش بازار (market_cap, market_cap_src) به اسنپ‌شاتِ تابلو
# اضافه شد. «تک‌منبعِ ارزش بازار» یعنی همین جدول؛ پس این گارد باید مطمئن شود
# نوشتنِ همگام‌سازی هنوز تمامِ ستونهایِ جدول را پوشش میدهد.


DDL = """
CREATE TABLE instruments (ins_code TEXT PRIMARY KEY, l_val18 TEXT, l_val30 TEXT,
    sector_code TEXT, sector_name TEXT, total_shares REAL, eps REAL, pe REAL,
    base_vol REAL, updated_at TEXT, paper_type INTEGER);
CREATE TABLE market_watch (ins_code TEXT PRIMARY KEY, d_even INTEGER, h_even INTEGER,
    p_closing REAL, p_last REAL, price_min REAL, price_max REAL, allowed_min REAL,
    allowed_max REAL, price_yesterday REAL, price_first REAL, q_tot_tran REAL,
    q_tot_cap REAL, z_tot_tran REAL, price_change REAL, eps REAL, pe REAL,
    total_shares REAL, sector_code TEXT, fetched_at TEXT,
    buy_q_vol REAL, buy_q_val REAL, buy_q_cnt REAL, sell_q_vol REAL, sell_q_val REAL,
    sell_q_cnt REAL, buy_q1_vol REAL, buy_q1_px REAL, sell_q1_vol REAL, sell_q1_px REAL,
    market_cap REAL, market_cap_src TEXT);

CREATE TABLE client_type (ins_code TEXT, d_even INTEGER, buy_i_vol REAL, buy_n_vol REAL,
    buy_ddd_vol REAL, buy_count_i INTEGER, buy_count_n INTEGER, buy_count_ddd INTEGER,
    sell_i_vol REAL, sell_n_vol REAL, sell_count_i INTEGER, sell_count_n INTEGER,
    fetched_at TEXT, PRIMARY KEY (ins_code, d_even));
CREATE TABLE daily_prices (ins_code TEXT, d_even INTEGER, p_closing REAL, price_min REAL,
    price_max REAL, price_yesterday REAL, price_first REAL, q_tot_tran REAL,
    q_tot_cap REAL, price_change REAL, fetched_at TEXT,
    market_cap REAL, market_cap_src TEXT, z_tot_tran REAL,
    PRIMARY KEY (ins_code, d_even));
CREATE TABLE mstat_snap (d_even INTEGER NOT NULL, h_even INTEGER NOT NULL, ts TEXT,
    agg TEXT, PRIMARY KEY (d_even, h_even));
"""


def new_db():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(DDL)
    return c


def mw(row):
    """ساختِ سطرِ market_watch با ۳۰ ستون — جای‌خالی‌ها صفر تا «ستون جاافتاده»
    بی‌صدا از سرِ فهرست جابه‌جا نشود."""
    vals = list(row) + [0.0] * (MW_COLS - len(row))
    assert len(vals) == MW_COLS, "market_watch row must fill %d cols, got %d" % (MW_COLS, len(vals))
    return vals


# (کد، نماد، نام، paper_type، صنعت)
INS = [
    ("i_st1", "فولاد", "شرکت فولاد", 1, "فلزات اساسي"),
    ("i_st2", "وبملت", "بانك ملي", 1, "بانكها و موسسات اعتباري"),
    ("i_rt1", "حقا", "حق تقدم ا", 4, "سرمایه گذاريها"),
    ("i_fe1", "اوج", "صندوق س.اوج دماوند-س", 8, "صندوق سرمايه گذاري قابل معامله"),
    ("i_fx1", "دينا", "صندوق س.درآمد ثابت دينا-د", 8, "صندوق سرمايه گذاري قابل معامله"),
    ("i_lv1", "اهرم", "صندوق اهرم آگاه-س", 8, "صندوق سرمايه گذاري قابل معامله"),
    ("i_gd1", "گلگشت", "صندوق سرمايه گذاري طلا گلگشت", 8, "صندوق سرمايه گذاري قابل معامله"),
    ("i_sv1", "نقره", "صندوق نقره-س", 8, "صندوق سرمايه گذاري قابل معامله"),
    ("i_op1", "ضهرم1", "اختيارخ اهرم-1", 6, "صندوق سرمايه گذاري قابل معامله"),
]


def seed(c, day=14040601, hour=123000):
    """ارقام طوری‌اند که هر ستون با دست قابلِ حساب باشد."""
    for ic, sym, nm, pt, sec in INS:
        c.execute("INSERT INTO instruments VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (ic, sym, nm, "68" if pt == 8 else "01", sec, 1e9, 100.0, 5.0,
                   1.0, "now", pt))
    # فولاد: پایانی ۱۰۰۰ / دیروز ۹۰۰ → +۱۱٫۱٪ ؛ آخرین ۹۵۰ → ساعت −۵٪؛ صف خرید خالص
    c.execute("INSERT INTO market_watch VALUES (?" + ",?" * (MW_COLS - 1) + ")", mw((
        "i_st1", day, hour, 1000.0, 950.0, 900.0, 1050.0, 900.0, 1100.0, 900.0, 900.0,
        1e9, 1e13, 500.0, 100.0, None, None, 1e9, "01", "f",
        2e6, 2e9, 3.0, 0.0, 0.0, 0.0, 2e6, 1000.0)))
    # وبملت: صفرِ واقعی، عمق دوطرفه ⇒ هیچ‌کدام صف نیست
    c.execute("INSERT INTO market_watch VALUES (?" + ",?" * (MW_COLS - 1) + ")", mw((
        "i_st2", day, hour, 500.0, 505.0, 490.0, 510.0, 450.0, 550.0, 500.0, 500.0,
        2e9, 1e12, 100.0, 5.0, None, None, 5e8, "01", "f",
        1e6, 5e8, 2.0, None, 5e8, 1.0, 1e6, 495.0)))
    # حق تقدم: −۳٪ با صف فروش
    c.execute("INSERT INTO market_watch VALUES (?" + ",?" * (MW_COLS - 1) + ")", mw((
        "i_rt1", day, hour, 970.0, 960.0, 930.0, 1030.0, 900.0, 1030.0, 1000.0, 1000.0,
        1e8, 1e11, 10.0, -30.0, None, None, 1e8, "01", "f",
        0.0, 0.0, 0.0, 5e7, 5e10, 4.0)))
    # صندوق‌ها و اختیار: بازدهی صفرِ کامل (p_closing = price_yesterday) تا شمارش
    # دماسنج دقیق باشد؛ k زوج ⇒ صف خرید، فرد ⇒ صف فروش. سمتِ خالی ۰.۰ است نه
    # None — در همگام‌سازیِ واقعی هم blDs عدد می‌دهد و تهی فقط وقتی است که کلید
    # نباشد؛ None در تست یعنی «عمق نیست» و نماد از شمارش بیرون می‌افتد.
    for k, ic in enumerate(("i_fe1", "i_fx1", "i_lv1", "i_gd1", "i_sv1", "i_op1")):
        c.execute("INSERT INTO market_watch VALUES (?" + ",?" * (MW_COLS - 1) + ")", mw((
            ic, day, hour, 1000.0, 1000.0, 1000.0, 1000.0, 900.0, 1100.0,
            1000.0, 1000.0, 1e8, 1e11, 5.0, 0.0, None, None, 1e8, "68", "f",
            (1e6 if k % 2 == 0 else 0.0), (1e9 if k % 2 == 0 else 0.0), 1.0,
            (0.0 if k % 2 == 0 else 1e6), (0.0 if k % 2 == 0 else 1e9), 1.0,
            1e6, 1000.0)))
    # client_type: (buy_i, buy_n, sell_i, sell_n, عددی, عددن, عدسی, عددن)
    for ic, bi, bn, cs, cn, cbi, cbn, csi, csn in [
            ("i_st1", 2e8, 5e7, 1e8, 2e7, 1000, 4, 1000, 3),
            ("i_st2", 1e8, 1e8, 2e8, 1e8, 200, 5, 400, 6),
            ("i_rt1", 5e6, 0.0, 1e6, 0.0, 10, 0, 5, 0),
            ("i_fe1", 4e6, 1e6, 2e6, 1e6, 20, 1, 10, 1),
            ("i_fx1", 1e7, 9e7, 5e6, 8e7, 30, 2, 15, 2),
            ("i_lv1", 3e6, 1e6, 4e6, 1e6, 12, 1, 8, 1),
            ("i_gd1", 2e6, 2e6, 1e6, 1e6, 8, 1, 4, 1),
            ("i_sv1", 1e6, 1e6, 1e6, 1e6, 5, 1, 5, 1),
            ("i_op1", 0.0, 0.0, 0.0, 0.0, 0, 0, 0, 0)]:
        c.execute("INSERT INTO client_type VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (ic, day, bi, bn, 0.0, cbi, cbn, 0, cs, cn, csi, csn, "f"))
    # مبنا: فقط وبملت پیشینه دارد → برآوردِ ۴ نشست؛ فولاد base_vol=1 یعنی نامعلوم
    # نام‌دار، نه جایگاهی: daily_prices دو ستونِ ارزش بازار گرفت و INSERT
    # جایگاهی با هر ستونِ تازه بی‌صدا یک ستون جابه‌جا میکند.
    for d in (14040525, 14040526, 14040527, 14040528):
        c.execute("INSERT INTO daily_prices (ins_code, d_even, p_closing, price_min,"
                  " price_max, price_yesterday, price_first, q_tot_tran, q_tot_cap,"
                  " price_change, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  ("i_st2", d, 500.0, 490.0, 510.0, 500.0, 500.0, 1.5e9, 7.5e11, 0.0, "f"))
    c.commit()
    return day


DB = new_db()
DAY = seed(DB)

# ==================== گارد ۱: طبقه‌بندی ابزار (پایهٔ هر نه سطر) ================
ck(ME.classify(1, "x", "y")[0] == "stock", "paperType 1 → stock")
ck(ME.classify(2, "x", "y")[0] == "stock", "paperType 2 هم سهام است (بازار دوم)")
ck(ME.classify(4, "x", "y")[0] == "right", "paperType 4 → حق تقدم")
ck(ME.classify(6, "اختيارخ", "z")[0] == "other",
   "paperType 6 (اختیار) وارد سطرات سهام/صندوق نمی‌شود")
ck(ME.classify(None, "a", "b")[0] == "other", "paperType گم‌شده = other، نه سهام")
ck(ME.fund_kind("صندوق س.درآمد ثابت دينا-د", "دينا") == "fixed", "صندوق درآمد ثابت")
ck(ME.fund_kind("صندوق اهرم آگاه-س", "اهرم") == "lev", "صندوق اهرمی (اهرم بر ثابت می‌چربد)")
ck(ME.fund_kind("صندوق سرمايه گذاري طلا گلگشت", "گلگشت") == "gold", "صندوق طلا")
ck(ME.fund_kind("صندوق نقره-س", "نقره") == "silver", "صندوق نقره")
ck(ME.fund_kind("صندوق س.بخشي صنايع دانايان1-ب", "نبات") == "equity",
   "«بخشی/-ب» صندوق سهامی است — ۱۴۵ صندوقِ بی‌طبقهٔ نسخهٔ نخست")
ck(ME.fund_kind("صندوق سرمايه گذاري برليان-سهام", "برليان") == "equity", "«سهام» در نام")
ck(ME.fund_kind("صندوق نامشخص-و", "ايكس") == "etf",
   "بی‌کلیدواژه = etf (در هیچ سطر تخصصی نمی‌نشیند، نه اینکه سهامی فرض شود)")

# ==================== گارد ۲: یکاها — همان‌چه کاربر در سربرگ می‌خواند =========
# فولاد: q_tot_cap = 1e13 ریال = ۱۰۰۰ میلیارد تومان = ۱ همت
TOTAL_RIAL = 1e13 + 1e12 + 1e11 + 6 * 1e11      # فولاد + وبملت + حق تقدم + شش صندوق/اختیار
s = ME.summary(DB)
by = {r["key"]: r for r in s["rows"]}
ck(abs(by["all"]["value_b_toman"] - TOTAL_RIAL / 1e10) < 0.5,
   "ارزش کل = مجموعِ ریال ÷ 1e10 (میلیارد تومان)")
ck(s["health"]["trade_value_all_market_hemat"] > 0, "گردشِ کل بازار گزارش می‌شود")
ck(s["health"]["market_value_hemat"] is None,
   "ارزشِ بازار بی‌دادِ رسمی صفر نمی‌شود (market_totals هنوز نیست → null)")
ck("value_hemat_all_market" not in s["health"],
   "کلِ کهنهٔ «ارزش کل بازار = گردشِ روز» برگشته نیست")
ck(abs(ME.B_TUMAN_FROM_RIAL - 1e10) == 0, "یکای ریال→میلیارد تومان قفل است")
ck(abs(ME.M_TUMAN_FROM_RIAL - 1e7) == 0, "یکای ریال→میلیون تومان قفل است")
ck(abs(ME.HEMAT_IN_B_TUMAN - 1e3) == 0, "۱ همت = ۱۰۰۰ میلیارد تومان")
ck(s["rows"][0]["key"] == "all" and len(s["rows"]) == 9,
   "جدول خلاصه دقیقاً ۹ سطر دارد (تصویر ۱)")
labels = [r["label"] for r in s["rows"]]
for need in ("کل بازار", "سهام، حق تقدم و ص.سهامی", "سهام و حق تقدم",
             "صندوق‌های سهامی و مختلط", "صندوق درآمد ثابت", "صندوق‌های اهرمی",
             "صندوق‌های طلا", "صندوق‌های نقره"):
    ck(any(need in x for x in labels), "سطر «%s» در جدول هست" % need)
st1 = [r for r in ME.enrich(DB)[0] if r["ins_code"] == "i_st1"][0]
m1 = st1["_m"]
ck(abs(m1["vwap"] - 1e4) < 1e-6, "VWAP = ارزش÷حجم = 1e13/1e9 = ۱۰٬۰۰۰ ریال")
ck(abs(m1["pc_buy"] / ME.M_TUMAN_FROM_RIAL - 200.0) < 1e-6,
   "سرانه خرید فولاد = (2e8×1e4)÷1000 = ۲۰۰ میلیون تومان")
ck(abs(m1["pc_sell"] / ME.M_TUMAN_FROM_RIAL - 100.0) < 1e-6,
   "سرانه فروش فولاد = (1e8×1e4)÷1000 = ۱۰۰ میلیون تومان")
ck(abs(m1["power"] - 2.0) < 1e-9, "قدرت خرید = ۲۰۰÷۱۰۰ = ۲٫۰")
ck(abs(m1["flow"] / ME.B_TUMAN_FROM_RIAL - 100.0) < 1e-6,
   "ورود پول = (2e12−1e12)÷1e10 = ۱۰۰ میلیارد تومان")
ck(by["stock_right"]["buy_power"] is not None and by["stock_right"]["buy_power"] > 1,
   "سطر «سهام و حق تقدم» قدرت خریدِ بالای ۱ می‌دهد")
# ==================== گارد ۳: هیستوگرام — مرزها و جمعِ درست =================
h = ME.histogram(DB, "all")
ck(len(h["histo12"]) == 12, "دقیقاً ۱۲ میله (ساختار ثابت، حتی میلهٔ صفر)")
ck(len(h["histo7"]) == 7, "توزیعِ محدودهٔ قیمتی دقیقاً ۷ میله دارد (گام ۳.۳)")
ck(sum(b["count"] for b in h["histo12"]) == h["known"],
   "جمعِ میله‌ها = تعدادِ دارای بازدهی (نه بیشتر، نه کمتر)")
ck(h["basis"] == "closing_vs_yesterday", "مبنای بازدهی در پاسخ نوشته شده")
ck(h["known"] + h["nodata"] == h["total"], "known + nodata = total")
# مرزها: یک مقدار دقیقاً در یک سطل
ck(ME._hit(-5.0, -1e9, -5.0) and not ME._hit(-5.0, -5.0, -4.0),
   "مرزِ ۵- فقط در یک سطل می‌نشیند")
ck(ME._hit(0.0, -1.0, 0.0) and not ME._hit(0.0, 0.0, 1.0),
   "صفر دقیقاً یک بار شمرده می‌شود")
ck(ME._hit(1.0, 0.0, 1.0) and not ME._hit(1.0, 1.0, 2.0), "مرزِ ۱+ یک‌باری")
neg12 = [b for b in h["histo12"] if b["color"] == "neg"]
pos12 = [b for b in h["histo12"] if b["color"] == "pos"]
ck(len(neg12) == 5 and len(pos12) == 5 and len(h["histo12"]) == 12,
   "۵ سطل قرمز + ۵ سبز + ۲ خاکستریِ میانی")
# نمادِ بدون معامله نباید در توزیعِ «بازدهی آخرین معاملات» باشد
c2 = new_db(); seed(c2)
c2.execute("UPDATE market_watch SET q_tot_tran=0, q_tot_cap=0 WHERE ins_code='i_st2'")
c2.commit()
h2 = ME.histogram(c2, "all")
ck(h2["not_traded"] >= 1 and h2["total"] == h["total"] - 1,
   "نمادِ بدون معامله از توزیع بیرون می‌ماند و جدا گزارش می‌شود")

# ==================== گارد ۴: دماسنج و قانون فرصت ورود ======================
th = ME.thermometer(DB, "all")
ck(th["positive"] == 1 and th["negative"] == 1 and th["zero"] == 7,
   "فولاد مثبت / حق تقدم منفی / هفت نماد صفر (دست‌چین، قابل شمارش)")
ck(th["entry_opportunity"] is False, "با بازارِ مثبت، «فرصت ورود» دروغ نمی‌گوید")
n_traded = sum(1 for r in ME.enrich(DB)[0] if r["_m"]["vol"] > 0)
ck(th["positive"] + th["negative"] + th["zero"] + th["nodata"] == n_traded,
   "اجزای دماسنج = تعداد نمادهای معامله‌شده (چیزی گم یا دوباره شمرده نمی‌شود)")
c3 = new_db(); seed(c3)
c3.execute("UPDATE market_watch SET p_closing = price_yesterday * 0.9 WHERE "
           "price_yesterday > 0 AND p_closing > 0")
c3.commit()
th2 = ME.thermometer(c3, "all")
ck(th2["entry_opportunity"] is True and th2["negative_pct"] >= 80,
   "اگر ≥۸۰٪ منفی شدند، قانون FTS فعال می‌شود")

# ==================== گارد ۵: عمق — بی‌داده هیچ‌وقت صفرِ سبز نیست ============
d = ME.depth(DB, "all")
ck(d["depth_available"] is True, "با ستون‌های عمق، پنل فعال است")
ck(d["buy_queue_count"] >= 1 and d["sell_queue_count"] >= 1, "هر دو نوع صف شمرده می‌شود")
ck(d["ratio"] is not None and d["ratio"] > 0, "نسبت خرید/فروش ۵ خط ساخته می‌شود")
# همان بانک بدون ستون‌های عمق ⇒ باید «بی‌داده» بگوید نه صفر
c4 = new_db(); seed(c4)
c4.execute("UPDATE market_watch SET buy_q_val=NULL, sell_q_val=NULL, buy_q_vol=NULL, sell_q_vol=NULL")
c4.commit()
d2 = ME.depth(c4, "all")
ck(d2["depth_available"] is False,
   "عمقِ NULL = depth_available:False (صفرِ گمراه‌کننده ساخته نمی‌شود)")
ck(d2["buy"]["normal"] == 0 and d2["buy"]["below_base"] == 0,
   "بی‌داده به‌عنوان «هیچ صفی نیست» جا نمی‌زند")
# تفکیک «کمتر از حجم مبنا» باید مبنای برآوردی را ببیند
ck("base_unknown" in d["buy"], "سطلِ «مبنا نامعلوم» جداست (بی‌داده ≠ عادی)")

# ==================== گارد ۶: سرتیب جدول — باگِ نسخهٔ نخست ==================
mwv = ME.mainwatch(DB, group="all", sort="val", desc=True, limit=9)
vals = [r["val_b_toman"] for r in mwv["rows"]]
ck(vals == sorted(vals, reverse=True),
   "سرتیب نزولیِ «ارزش» واقعاً نزولی است (باگِ کلیدِ نگاشت‌شدهٔ v9.7.5)")
ck(mwv["rows"][0]["val_b_toman"] > 900, "بیشترین ارزش = فولاد (۱۰۰۰ میلیارد تومان)")
mwp = ME.mainwatch(DB, group="all", sort="pct", desc=False, limit=9)
pv = [r["pct_close"] for r in mwp["rows"] if r["pct_close"] is not None]
ck(pv == sorted(pv), "سرتیب صعودیِ «٪پایانی» صعودی است")
ck(mwv["sort_col"] == "val_b_toman", "ستونِ سرتیب در پاسخ اعلام می‌شود")
# الگوی ساعت: بی‌مبادلهٔ کم‌تراکم نباید نامزد شود
c5 = new_db(); seed(c5)
c5.execute("UPDATE market_watch SET z_tot_tran=2, allowed_min=1, allowed_max=1e8 "
           "WHERE ins_code='i_st1'")
c5.execute("UPDATE market_watch SET p_last=1400.0 WHERE ins_code='i_st1'")  # +40٪ با ۲ معامله
c5.commit()
g = ME.mainwatch(c5, group="all", sort="clock", desc=True, limit=9)
tgt = [r for r in g["rows"] if r["symbol"] == "فولاد"][0]
ck(tgt["clock_pct"] is not None and tgt["clock_ok"] is False,
   "اختلافِ ۴۰٪ فقط با ۲ معامله شمرده می‌شود ولی نامزدِ الگوی ساعت نیست")
ck(g["rows"][0]["clock_ok"] is True,
   "صدرِ جدول به نامزدِ قابل‌اتکا می‌رسد، نه به بزرگ‌ترین عددِ خام")
ck(g["clock_hits"] == sum(1 for r in g["rows"] if r["clock_ok"]),
   "شمارِ نامزدها با خودِ ستونِ clock_ok می‌خواند")
# ================ گارد ۷: ترمزِ دادهٔ نامعقول (تاریخِ جا‌زدده در قیمت) ========
# باگِ واقعیِ همگام‌سازیِ پیشین: prev[1] که d_even بود داخل p_last می‌ریخت و
# «آخرین معامله» ۲۰٬۲۶۰٬۹۰۸ ریال می‌شد؛ الگوی ساعتِ کل داشبورد آلوده بود.
row_fake = {"allowed_min": 1.0, "allowed_max": 99999999.0}   # باندِ بی‌فایدهٔ صندوق
ck(ME.px_in_band(row_fake, 20260908.0, 1586958.0) is False,
   "p_lastِ تاریخ‌مانند حتی با باندِ باز رد می‌شود")
ck(ME.px_in_band({"allowed_min": 900.0, "allowed_max": 1100.0}, 950.0, 1000.0) is True,
   "آخرینِ داخلِ باند قبول می‌شود")
ck(ME.px_in_band({"allowed_min": 900.0, "allowed_max": 1100.0}, 1200.0, 1000.0) is False,
   "آخرینِ بیرونِ باند رد می‌شود")
ck(ME.px_near(900.0, 1000.0) and not ME.px_near(20260907.0, 1000.0),
   "قیمتِ دیروز باید هم‌مرتبهٔ پایانی باشد")
c6 = new_db(); seed(c6)
c6.execute("UPDATE market_watch SET p_last=20260908.0 WHERE ins_code='i_st1'")
c6.commit()
r6 = [r for r in ME.enrich(c6)[0] if r["ins_code"] == "i_st1"][0]
ck(r6["clock_pct"] is None, "الگوی ساعتِ آلوده None می‌شود، نه ۲۰ میلیون درصد")
r6b = [r for r in ME.mainwatch(c6, group="all", sort="val", limit=9)["rows"]
       if r["symbol"] == "فولاد"][0]
ck(r6b["p_last"] is None and r6b["pct_last"] is None,
   "در جدول هم «آخرین» آلوده نمایش داده نمی‌شود")

# ==================== گارد ۸: تایم‌لاین — نقطه‌سازیِ جعلی ممنوع ===============
tl0 = ME.timeline(new_db())
ck(tl0["ready"] is False and tl0["points"] == 0,
   "بی‌نقطه ⇒ ready:False (خطِ صافِ دروغین روی چارت نمی‌نشیند)")
c7 = new_db(); seed(c7)
# v9.8.1: save_mstat_snapshot گاردِ پنجرهٔ بازار دارد (۰۹:۰۰–۱۳:۰۰ + روزِ
# کاری)؛ تست باید مستقل از روزِ اجرا باشد ⇒ `when` تزریقی (شنبه ۱۰:۰۰).
_SAT = datetime.datetime(2026, 9, 12, 10, 0)
ME.save_mstat_snapshot(c7, dict(ME.snapshot_agg(c7), h_even=100000), when=_SAT)
ME.save_mstat_snapshot(c7, dict(ME.snapshot_agg(c7), h_even=110000, pos=50, neg=10),
                       when=_SAT)
ME.save_mstat_snapshot(c7, dict(ME.snapshot_agg(c7), h_even=120000, pos=50, neg=10),
                       when=_SAT)
ME._CTX.clear()
tl = ME.timeline(c7)
ck(tl["ready"] is True and tl["points"] == 3, "سه همگام‌سازی ⇒ سه نقطه")
ck(tl["series"]["t"][0].startswith("10:") and tl["series"]["t"][2].startswith("12:"),
   "برچسبِ ساعت از h_evenِ همان نقطه ساخته می‌شود")
tli = ME.timeline(c7, mode="inst")
ck(tli["series"]["pos"][0] == tl["series"]["pos"][0],
   "نخستین نقطه در حالت لحظه‌ای همون مقدارِ تجمعی است")
cum_pos = [v for v in tl["series"]["pos"] if v is not None]
inst_pos = [v for v in tli["series"]["pos"] if v is not None]
ck(abs(sum(inst_pos) - cum_pos[-1]) < 1e-6,
   "مجموعِ تغییراتِ لحظه‌ای = آخرین مقدارِ تجمعی (%s vs %s)"
   % (sum(inst_pos), cum_pos[-1]))
ck(len(tl["series"]["pos"]) == len(tl["series"]["t"]), "طولِ سری‌ها با محورِ زمان یکی است")
# چرخش وضعیت: دو نقطه با تغییرِ b→s باید شمرده شود
ph = ME.phases(c7)
ck(ph["ready"] is True, "شمارندهٔ چرخش با ≥۲ نقطه فعال می‌شود")
c8 = new_db(); seed(c8)
a1 = ME.snapshot_agg(c8)
a1["st"] = ME._enc_states({"i_st1": "b", "i_rt1": "s"})
ME.save_mstat_snapshot(c8, dict(a1, h_even=100000), when=_SAT)
a2 = ME.snapshot_agg(c8)
a2["st"] = ME._enc_states({"i_st1": "s", "i_rt1": "b"})
ME.save_mstat_snapshot(c8, dict(a2, h_even=110000), when=_SAT)
ME._CTX.clear()
ph2 = ME.phases(c8)
red = {x["key"]: x["count"] for x in ph2["red"]}
grn = {x["key"]: x["count"] for x in ph2["green"]}
ck(red.get("b>s") == 1, "چرخشِ صف خرید→صف فروش شمرده شد")
ck(grn.get("s>b") == 1, "چرخشِ صف فروش→صف خرید شمرده شد")
ck(sum(x["count"] for x in ph2["red"]) == 1 and sum(x["count"] for x in ph2["green"]) == 1,
   "هر جفتِ متوالی یک‌بار شمرده می‌شود")

# ==================== گارد ۹: ضدِ N+1 — یک اسکن، نه به‌ازای هر نماد ===========
# آستانهٔ ثابت بی‌معناست؛ آنچه باید قفل شود «عدمِ رشدِ کوئری با تعداد نماد» است.
def count_queries(fn, conn):
    ME._CTX.clear()
    seen = []
    conn.set_trace_callback(lambda q: seen.append(q))
    try:
        fn(conn)
    finally:
        conn.set_trace_callback(None)
    return len([q for q in seen if q.strip().upper().startswith("SELECT")])


small = new_db(); seed(small)                                  # ۹ نماد
big = new_db(); seed(big)
for k in range(600):                                           # ۶۰۹ نماد
    ic = "big%04d" % k
    big.execute("INSERT INTO instruments VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (ic, "s" + ic, "name" + ic, "01", "فلزات اساسي", 1e6, 1.0, 1.0,
                 1.0, "now", 1))
    big.execute("INSERT INTO market_watch VALUES (?" + ",?" * (MW_COLS - 1) + ")", mw((
        ic, 14040601, 123000, 1000.0, 1000.0, 900.0, 1100.0, 900.0, 1100.0,
        1000.0, 1000.0, 1e5, 1e8, 3.0, 0.0, None, None, 1e6, "01", "f")))
big.commit()
q_small = count_queries(lambda c: ME.mainwatch(c, group="all", limit=9999), small)
q_big = count_queries(lambda c: ME.mainwatch(c, group="all", limit=9999), big)
ck(q_small == q_big,
   "تعداد کوئری با نماد رشد نمی‌کند: ۹ نماد=%d، ۶۰۹ نماد=%d" % (q_small, q_big))
q7_small = sum(count_queries(fn, small) for fn in (
    lambda c: ME.summary(c), lambda c: ME.thermometer(c), lambda c: ME.histogram(c),
    lambda c: ME.depth(c), lambda c: ME.client_split(c), lambda c: ME.industries(c),
    lambda c: ME.mainwatch(c)))
q7_big = sum(count_queries(fn, big) for fn in (
    lambda c: ME.summary(c), lambda c: ME.thermometer(c), lambda c: ME.histogram(c),
    lambda c: ME.depth(c), lambda c: ME.client_split(c), lambda c: ME.industries(c),
    lambda c: ME.mainwatch(c)))
ck(q7_small == q7_big, "هفت پنل هم مقیاسِ کوئریِ ثابت دارند (%d vs %d)"
   % (q7_small, q7_big))
ME._CTX.clear()
import time as _t
t0 = _t.time()
ME.mainwatch(big, group="all", limit=200)
dt_ms = (_t.time() - t0) * 1000
ck(dt_ms < 1500, "تابلوی ۶۰۹ نماد در %.0fms (کشِ ctx)" % dt_ms)


# ============ گارد ۱۰: همگام‌سازی همان ستون‌ها را می‌نویسد که موتور می‌خواند ===
src = io.open("test_tsetmc.py", encoding="utf-8").read()
tmp = new_db()
real_mw = [r[1] for r in tmp.execute("PRAGMA table_info(market_watch)")]
real_ins = [r[1] for r in tmp.execute("PRAGMA table_info(instruments)")]
# v10: نوشتنِ market_watch/daily_prices از «۳۰ ؟ جایگاهی» به «INSERT نام‌دار»
# تغییر کرد، چون ارزش بازار دو ستون تازه آورد و جابه‌جاییِ بی‌صداِ یک ستون
# (همان باگِ p_last در v9.8.1) دقیقاً همان‌جا اتفاق می‌افتد که این گارد نگهبان است.
# پس گارد حالا نامِ ستونها را می‌سنجد، نه فقط تعدادشان را.
import test_tsetmc as TT


def _named_insert(sql):
    """'INSERT … INTO t (a, b, …) VALUES (?, ?, …)' → ([ستون‌ها], تعدادِ ؟)."""
    head, _, tail = sql.partition(") VALUES (")
    cols = [c.strip() for c in head.split("(", 1)[1].split(",") if c.strip()]
    return cols, tail.rstrip("); ").count("?")


for _tbl, _sql in (("market_watch", TT._MW_INSERT), ("daily_prices", TT._DP_INSERT)):
    _cols, _ph = _named_insert(_sql)
    _real = [r[1] for r in tmp.execute("PRAGMA table_info(%s)" % _tbl)]
    ck(_ph == len(_cols), "%s: %d نامِ ستون = %d placeholder" % (_tbl, len(_cols), _ph))
    ck(set(_cols) == set(_real),
       "%s: نوشتن دقیقاً همان ستونهایِ جدول است (جاافتاده=%r اضافه=%r)"
       % (_tbl, sorted(set(_real) - set(_cols)), sorted(set(_cols) - set(_real))))
    ck("market_cap" in _cols and "market_cap_src" in _cols,
       "%s: ستونِ ارزش بازار در مسیرِ نوشتن هست (تک‌منبعِ TSETMC)" % _tbl)
    if _tbl == "market_watch":
        ck(_cols[0] == "ins_code",
           "%s: کلیدِ اصلی نخستین ستون است (INSERT OR REPLACE سُر نمی‌خورد)" % _tbl)
        ck(all(c in real_mw for c in _cols),
           "%s: هیچ ستونِ جعلی در INSERT نیست" % _tbl)


ph_ = re.findall(r'market_watch VALUES \(" \+ ","\.join\("\?" \* (\d+)\)', src)
ck(not ph_, "هیچ نوشتنِ جایگاهیِ market_watch بازشده نمانده (فقط نام‌دار)")
phi_ = re.findall(r'instruments VALUES \(" \+ ","\.join\("\?" \* (\d+)\)', src)
ck(phi_ and all(int(x) == len(real_ins) for x in phi_),
   "placeholderهای instruments (%s) = %d ستون" % (phi_, len(real_ins)))
mig = [n for t, cols in ME.MIGRATIONS.items() if t == "market_watch" for n, _ty in cols]
ck(len(mig) == 10 and set(mig) <= set(real_mw), "همهٔ ۱۰ ستونِ عمق در ساختار هست")
ck("withBestLimits=true" in src,
   "MW_URL باید withBestLimits=true بفرستد، وگرنه blDs نمی‌آید و کل پنلِ عمق تهی می‌ماند")
ck("save_mstat_snapshot(conn)" in src,
   "هر همگام‌سازی یک نقطهٔ تایم‌لاین ثبت می‌کند (بی‌آنکه گام ۴ هیچ‌وقت پر نشود)")
# خودِ تابعِ واقعیِ همگام‌سازی را صدا می‌زنیم (نه یک کپیِ regex‌شده): اگر
# روزی queue_agg عوض شود، همین گارد باید بفهمد — نه اینکه از روی متن بسازمش.
import test_tsetmc as TS
got = TS.queue_agg({"blDs": [{"n": 1, "qmd": 100, "pmd": 500.0, "zmd": 3,
                              "qmo": 0, "pmo": 0.0, "zmo": 0},
                             {"n": 2, "qmd": 50, "pmd": 490.0, "zmd": 1,
                              "qmo": 0, "pmo": 0.0, "zmo": 0}]})
ck(len(got) == 10, "queue_agg ده مقدار برمی‌گرداند (جمعِ ۵خط + خطِ اول)")
ck(got[0] == 150 and abs(got[1] - 74500.0) < 1e-6,
   "حجم ۵ خط = ۱۵۰ و ارزش = 100×500 + 50×490 = ۷۴٬۵۰۰ ریال")
ck(got[2] == 4, "تعداد سفارش‌های تقاضا از zmd جمع می‌شود")
ck(got[6] == 100 and got[7] == 500.0, "حجم/قیمت «خطِ اول» جدا نگه داشته می‌شود")
ck(TS.queue_agg({"blDs": []}) is None, "blDs تهی = None (بی‌داده، نه صفر)")
ck(list(TS._QUEUE_COLS) == mig,
   "ترتیبِ _QUEUE_COLS با ترتیبِ بازگشتیِ queue_agg و ستون‌های مهاجرت یکی است")


# ==================== گارد ۱۱: سیم‌کشیِ UI (پروکسی بیرونی حذف شود) ============
html = io.open("archive/legacy_static/index.html", encoding="utf-8").read()
js = io.open("archive/legacy_static/mstat.js", encoding="utf-8").read()
apps = io.open("archive/legacy_static/app.js", encoding="utf-8").read()
for pid in ("msSummary", "msHisto12", "msThermo", "msDepth", "msQueueSplit", "msPhases",
            "msHisto7", "msTlFlow", "msTlPosNeg", "msTlOrders", "msTlPerCap",
            "msTlQueues", "msClTabs", "msClTable", "msInd", "msGrid", "msHealth",
            "msGridHead", "msGroup", "msPoll", "msStatus", "msModeCum", "msModeInst"):
    ck('id="%s"' % pid in html, "عنصر #%s در سکشن mstat هست" % pid)
ck("/api/mstat/board" in js, "تب از endpoint محلی تغذیه می‌شود")
# «پروکسیِ بیرونی» یعنی fetch به آدرسِ مطلق؛ اشاره به tradersarena در کامنتِ
# توضیحی مشکلی نیست و نباید گارد را بشکند (گاردِ کلمه‌ای، خودِ کامنت را می‌گرفت).
ck(not re.search(r"""fetch\(\s*['"][a-z]+://""", js),
   "mstat.js هیچ fetchِ آدرسِ خارجی (http…) ندارد")
ck("/data/market" not in js and "ir/data/" not in js,
   "هیچ مسیرِ داده‌ایِ تریدرزآرنا در mstat.js فراخوانی نمی‌شود")
ck("async function msRefresh" not in apps,
   "app.js دیگر msRefresh تعریف نمی‌کند (دو نسخه در یک اسکوپ جهانی)")
ck("msToggleWatch" in js and "POST" in js and "/api/watchlist" in js,
   "دکمهٔ سبد به /api/watchlist وصل است (گام ۵.۲)")
ck("msSortBy" in js and "اختلاف آخرین/پایانی" in js,
   "ستونِ الگوی ساعت در جدول هست و مرتب‌شدنی است")
_ms_vers = {tuple(int(x) for x in v.split('.'))
            for v in re.findall(r'mstat\.js\?v=([\d.]+)', html)}
ck(len(_ms_vers) == 1 and next(iter(_ms_vers)) >= (9, 7, 7),
   "نسخهٔ کش بالا رفته و mstat.js واقعاً لود می‌شود")
ck("mstatView" in html and "switchView('mstat'" in html, "تب mstat در ناوبری هست")
missing = [m for m in set(re.findall(r"msEl\('([A-Za-z0-9]+)'\)", js))
           if ('id="%s"' % m) not in html]
ck(not missing, "هر id که JS می‌خواند در HTML هست (مفقود: %s)" % missing)

# ========== گاردِ روز: client_type باید هم‌نشستِ تابلو باشد (تریدرز آرنا) =====
# «وضعیت بازار» با تریدرز آرنا نمی‌خواند، چون client_type با todayِ دیواری
# stamped می‌شد و market_watch با روزِ نشست. رویِ همگام‌سازیِ آخرِ هفته دو
# روز از هم می‌افتادند (تابلو ۲۰۲۶۰۹۲۳ / client ۲۰۲۶۰۹۲۶، آن‌طور که در
# market.db اندازه گرفته شد) و قدرت خریدار/فروشنده از نشستِ دیگری می‌آمد.
# ترمیم سه‌جاست: نوشتنِ d_even در test_tsetmc.py، و کرانِ d_even<=در
# mstat_engine و api/market.py. هر سه همین‌جا قفل می‌شوند.
_sync = io.open(os.path.join(ROOT, "test_tsetmc.py"), encoding="utf-8").read()
_stamp_sites = re.findall(r"client = \[\(x\.get\(\"insCode\"\),\s*([^,]+),", _sync)
ck(len(_stamp_sites) >= 2 and all("session_day_of(watch" in s for s in _stamp_sites),
   "همهٔ مسیرهای همگام‌سازی، client_type را با روزِ *معامله‌شده* می‌زنند "
   "(session_day_of)، نه todayِ دیواری و نه d_evenِ خام (%s)"
   % _stamp_sites)
_mk = io.open(os.path.join(ROOT, "api", "market.py"), encoding="utf-8").read()
ck("WHERE d_even <= (SELECT" in _mk or "d_even <= (SELECT d FROM iso)" in _mk,
   "کوئریِ تابلو client_type را به d_even<=روزِ تابلو کران کرده")

# ── شاخصِ رسمی (market_index): نوشتنِ سینک ⇔ خواندنِ موتور ────────────────
# همان GetMarketOverview که «کل ارزش بازار» را می‌سازد indexLastValue و
# indexEqualWeightedLastValue را هم می‌فرستاد و دور ریخته می‌شد — برای همین
# برنامه هیچ‌جا شاخص نداشت. ارقام زیر نشستِ واقعیِ ۱۴۰۵-۰۷-۰۴‌اند و با
# iw/ia تریدرزآرنا و با پاسخِ خودِ TSETMC مو‌افقات‌اند.
_ixc = new_db()
_ov = {"indexLastValue": 7153088.29, "indexChange": -103955.13,
       "indexEqualWeightedLastValue": 1929823.43, "indexEqualWeightedChange": -9196.9}
ck(TT.save_market_index(_ixc, _ov, 20260926, now="x") is True,
   "save_market_index شاخصِ رسمیِ همان نشست را می‌نویسد")
_ix = ME.market_index(_ixc)
ck(_ix and abs(_ix["last"] - 7153088.29) < 1e-6 and abs(_ix["ew_last"] - 1929823.43) < 1e-6,
   "موتور هر دو شاخص را دقیقاً همان‌طور که سینک نوشته می‌خواند")
ck(_ix and abs(_ix["pct"] + 1.43) < 0.005 and abs(_ix["ew_pct"] + 0.47) < 0.005,
   "درصد از (آخرین − تغییر) ساخته می‌شود: کل ۱.۴۳- / هموزن ۰.۴۷-")
ck(TT.save_market_index(_ixc, {}, 20260926) is False,
   "پاسخِ بی‌شاخص هیچ نمی‌نویسد — نه سطرِ صفر")
ck(ME.market_index(new_db()) is None, "بی‌جدولِ شاخص یعنی None، نه صفر")
ck("index" in ME.smart_money(_ixc)["macro"],
   "نبض بازار شاخص را در همان macroِ پول هوشمند می‌برد (یک fetch، نه دو)")
ck(ME.smart_money(_ixc)["macro"]["index"]["pct"] is not None,
   "مقدارِ ذخیره‌شده تا UI بدونِ محاسبهٔ جدید می‌رسد")
ck(_sync.count("save_market_index(conn, bourse_ov") == 2,
   "هر دو مسیرِ همگام‌سازی (main و اسنپ‌شات) شاخص را می‌نویسند")

# ── حکمِ امروز (نبض بازار): نوشتنِ همتِ روز ⇔ خواندنِ درِ تداوم ⇔ رأیِ سه‌گانه ──
# جزوه ص۱۳ زیرِ تیترِ «وضعیتِ کلیِ بازار را چگونه بررسی کنم؟» سه قدم می‌شمارد
# (ارزشِ معاملات با تداومِ ۳–۴ روز، درصدِ منفی‌ها، روندِ پولِ حقیقی) و ص۱۴ دو
# پنجرهٔ ساعتی می‌دهد. این‌ها همان‌ها هستند — و مهم‌تر از آن: نبودِ داده هرگز
# رأیِ «وارد نشو» نمی‌سازد.
_vc = new_db()
_vday = seed(_vc)
_mac = ME.macro_health(_vc)
ck(_mac["value_hemat"], "نمونهٔ دستیِ mstat همتِ قابل‌داوری دارد")
ck(TT.save_market_liquidity(_vc, _vday, now="x") is True,
   "سینک، همتِ همان نشست را در market_liquidity ثبت می‌کند")
_hist = ME.liquidity_history(_vc)
ck(len(_hist) == 1 and abs(_hist[0]["value_hemat"] - _mac["value_hemat"]) < 1e-9,
   "تاریخچه از همان مبنایِ عددِ امروز نوشته می‌شود (eq_all)، نه جمعِ دستیِ تابلو")
ck(TT.save_market_liquidity(_vc, 0, now="x") is False,
   "بی‌روزِ نشست هیچ سطری نوشته نمی‌شود")
ck(ME.liquidity_history(new_db()) == [],
   "بی‌جدولِ تاریخچه یعنی [] و درِ تداوم «بدون داده» — نه صفرِ تأییدشده")
ck(_sync.count("if save_market_liquidity(conn,") == 2,
   "هر دو مسیرِ همگام‌سازی همتِ روز را می‌نویسند (وگرنه تاریخچه قطع می‌شود)")
ck("verdict" in ME.smart_money(_vc),
   "حکم در همان یک fetchِ پولِ هوشمند می‌آید، نه در درخواستِ دومی")


def _vd(**sm):
    """day_verdict روی یک پول‌هوشمندِ ساختگی — درها جدا آزمایش شوند."""
    base = {"macro": {}, "watch_entry": {}, "flow": {}, "asof": {}}
    base.update(sm)
    return ME.day_verdict(_vc, base)


_empty = _vd()
ck(_empty["verdict"] == "nodata",
   "هیچ‌چیز ندیده‌ایم ⇒ حکم صادر نمی‌شود (نه «وارد نشو»، نه «ورود»)")
ck(all(g["vote"] == 0 for g in _empty["gates"]),
   "نبودِ داده در هیچ دری رأیِ منفی نیست")
_dry = _vd(macro={"value_hemat": None, "state": "nodata"})
_liq_dry = [g for g in _dry["gates"] if g["key"] == "liquidity"][0]
ck(_liq_dry["label_state"] == "بدون داده" and _liq_dry["state"] == "nodata",
   "درِ نقدینگی روی بی‌داده «بدون داده» است، نه «نامساعد»")
_bad = _vd(macro={"value_hemat": 6.2, "state": "bad", "label": "نامساعد", "bad_max": 10.0})
ck(_bad["verdict"] == "avoid", "همتِ ۶.۲ (زیرِ ۱۰) ⇒ «امروز وارد نشو»")
_hi = _vd(macro={"value_hemat": 63.0, "state": "good", "label": "مساعد",
                 "excellent": True, "good_min": 20.0})
ck("عالی" in _hi["gates"][0]["label_state"], "بالایِ ۵۰ همت «عالی» است، نه فقط «مساعد»")
_opp = _vd(watch_entry={"active": True, "bearish_pct": 88.0, "rule_pct": 80.0})
_breadth = [g for g in _opp["gates"] if g["key"] == "breadth"][0]
ck(_breadth["vote"] == 1 and "فرصت" in _breadth["label_state"],
   "۸۰٪ منفی طبقِ جزوه «فرصتِ ورود» است — رأیِ مثبت، نه هشدار")
ck("هشدار" not in _breadth["label_state"] and _breadth["state"] == "ok",
   "برچسبِ دیدنیِ درِ پهنای بازار «هشدار» نیست — در جزوه «فرصت» است")
_ideal = _vd(macro={"value_hemat": 27.0, "state": "good", "label": "مساعد"},
             flow={"eq_inflow": True, "fixed_outflow": True, "eq_flow_b_toman": 120.0,
                   "fixed_flow_b_toman": -80.0, "gold_flow_b_toman": -12.0})
ck([g for g in _ideal["gates"] if g["key"] == "flow"][0]["vote"] == 1,
   "سه‌گانهٔ پول (ورودِ سهام + خروجِ درآمد ثابت + خروجِ طلا) رأیِ مثبت دارد")
_nogold = _vd(flow={"eq_inflow": True, "fixed_outflow": True, "eq_flow_b_toman": 120.0,
                    "fixed_flow_b_toman": -80.0, "gold_flow_b_toman": None})
ck([g for g in _nogold["gates"] if g["key"] == "flow"][0]["vote"] == 1,
   "نبودِ دادهٔ طلا لغوِ الزام است، نه ردِّ شرط")
_out = _vd(flow={"eq_inflow": False, "fixed_outflow": False, "eq_flow_b_toman": -300.0,
                 "fixed_flow_b_toman": 90.0, "gold_flow_b_toman": 40.0})
ck([g for g in _out["gates"] if g["key"] == "flow"][0]["vote"] == -1,
   "خروجِ صریحِ پول از سهام رأیِ منفی است (نه فقط «حالتِ آرمانی ندارد»")
_w1 = ME._clock_window(91500)
_w2 = ME._clock_window(122200)
_w3 = ME._clock_window(125900)
ck(_w1["state"] == "ok" and "درآمد ثابت" in _w1["label"], "۰۹:۱۵ پنجرهٔ درآمد ثابت است")
ck(_w2["state"] == "ok" and "طلا" in _w2["label"], "۱۲:۲۲ پنجرهٔ شفافیتِ طلا است")
ck(_w3["state"] == "mid", "۱۲:۵۹ خارجِ هر دو پنجره است")


def _human(v):
    """همۀ متنِ دیدنیِ حکم — تیتر، علت، برچسبِ هر در و جملهٔ رنگش."""
    return "".join([v["label"], v["reason"]] +
                   [g["label"] + g["label_state"] + str(g["detail"]) + str(g.get("why"))
                    for g in v["gates"]])


ck(not any(c.isascii() and c.isdigit() for c in _human(_ideal)),
   "همۀ متنِ حکم با رقمِ فارسی نوشته می‌شود (قالبِ عددی در بک‌اند است)")
ck(not any(c.isascii() and c.isdigit() for c in _human(_opp)),
   "متنِ «فرصتِ ورود» هم رقمِ لاتین ندارد")
ck(_ideal["gates"][4]["key"] == "window" and len(_ideal["gates"]) == 5,
   "پنج در: نقدینگی، تداوم، پهنای بازار، پولِ حقیقی، پنجرهٔ ساعت")
# #170: شمارهٔ «قدم» از متن بیرون رفت (ترتیبی در داوری نیست) و هر در یک جملهٔ
# «این رنگ یعنی چی» دارد — سؤالِ مالک دقیقاً همین بود.
ck("قدمِ" not in _human(_ideal) and "قدمِ" not in _human(_opp) and "قدمِ" not in _human(_bad),
   "هیچ «قدمِ …»ی در متنِ دیدنیِ حکم نمانده («حق تقدم» کلمه‌اش جداست)")
ck(all(str(g.get("why") or "").strip() for g in _ideal["gates"]),
   "هر پنج در جملهٔ توضیحِ رنگ دارند")
ck(all(ME._gate_why(k, st, {}, {}).strip() for k in
       ("liquidity", "continuity", "breadth", "flow", "window")
       for st in ("ok", "mid", "bad", "nodata")),
   "برای هر در و هر رنگ جمله هست — هیچ حالتی بی‌توضیح یا بی‌«None» نمی‌ماند")
ck(not any("None" in ME._gate_why(k, st, {}, {}) for k in
           ("liquidity", "continuity", "breadth", "flow", "window")
           for st in ("ok", "mid", "bad", "nodata")),
   "هیچ جمله‌ای «None»ی خام از پایتون ندارد")
# ساده‌سازیِ متن (#165): دلیلِ حکم باید بگوید کدام در، نه فقط فهرستِ وضعیت‌ها.
ck(all(g.get("short") for g in _ideal["gates"]), "هر پنج در نامِ کوتاه دارد")
ck(all(g["short"] in _ideal["reason"] for g in _ideal["gates"] if g["vote"]),
   "نامِ هر درِ قاطع در جملهٔ دلیل می‌آید")
ck(_bad["reason"].startswith("نقدینگی:"),
   "دلیلِ «امروز وارد نشو» با نامِ در شروع می‌شود، نه متنِ برهنه")

conn = new_db()
day = seed(conn)
# یک ردیفِ «آینده» برای i_st1 می‌گذاریم: اگر کرانِ روز کار نکند، سرانهٔ خریدِ
# حقیقی این نماد به‌طورِ فاحشی عوض می‌شود و آزمون می‌گیرد.
conn.execute("INSERT INTO client_type VALUES ('i_st1', ?, 9e15, 9e15, 0.0, 1, 1, 0,"
             " 9e15, 9e15, 1, 1, 'future')", (day + 3,))
conn.commit()
snap = ME.load_snapshot(conn, force=True)
ck(str(snap["asof"]["client_d_even"]) <= str(snap["asof"]["d_even"]),
   "روزِ client_type هیچ‌وقت بعد از روزِ تابلو نیست (%s vs %s)"
   % (snap["asof"]["client_d_even"], snap["asof"]["d_even"]))
st1 = [r for r in snap["rows"] if r["ins_code"] == "i_st1"]
ck(len(st1) == 1 and st1[0]["ct"][ME._CT_FIELDS["buy_i_vol"]] != 9e15,
   "ردیفِ آینده‌دار در اسنپ‌شات انتخاب نمی‌شود")
# تایم‌لاینِ کهنه باید خودش را کهنه اعلام کند، نه ready خاموش
conn.execute("CREATE TABLE IF NOT EXISTS mstat_snap (d_even INTEGER, h_even INTEGER,"
             " ts TEXT, agg TEXT)")
conn.execute("DELETE FROM mstat_snap")
conn.execute("INSERT INTO mstat_snap VALUES (?,?,?,?)",
             (day - 4, 100000, "t1", json.dumps({"d_even": day - 4, "val_bt": 1.0})))
conn.execute("INSERT INTO mstat_snap VALUES (?,?,?,?)",
             (day - 4, 110000, "t2", json.dumps({"d_even": day - 4, "val_bt": 2.0})))
conn.commit()
ltl = ME.timeline(conn)
ck(ltl["ready"] is True and ltl["stale"] is True and ltl["note"],
   "تایم‌لاینِ دو-نقطه‌ای از نشستِ دیگر، stale=true و توضیح می‌دهد")
ck(ltl["board_day"] == day, "تایم‌لاین روزِ تابلو را هم گزارش می‌کند")
conn.close()

# ==================== گارد ۱۲: صحت روی دادهٔ واقعی (market.db) ===============
if os.path.exists("market.db"):
    conn = sqlite3.connect("file:market.db?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    ME._CTX.clear()
    ls = ME.summary(conn)
    ck(len(ls["rows"]) == 9, "روی دادهٔ واقعی هم ۹ سطر")
    ck(ls["rows"][0]["value_b_toman"] > 1000, "ارزشِ کلِ بازارِ واقعی معنادار است")
    ck(ls["health"]["state"] in ("good", "mid", "bad"), "برچسب سلامت ساخته می‌شود")
    ld = ME.depth(conn)
    ck(ld["depth_available"] is True,
       "همگام‌سازیِ تازه عمق را ذخیره کرده (%d نماد با عمق)" % ld["symbols_with_depth"])
    lm = ME.mainwatch(conn, group="eq_all", sort="clock", desc=True, limit=40)
    ck(lm["total"] > 100, "تابلوی واقعی پر است (%d نماد)" % lm["total"])
    polluted = [r for r in lm["rows"] if r["p_last"] and r["p_closing"]
                and not (0.5 <= r["p_last"] / r["p_closing"] <= 2.0)]
    ck(not polluted, "هیچ «آخرین» تاریخ‌مانندی نمانده (%d مورد)" % len(polluted))
    clk = [r for r in lm["rows"] if r["clock_ok"]]
    ck(all(r["clock_pct"] >= ME.CLOCK_PCT for r in clk),
       "نامزدهای الگوی ساعت همه بالای آستانه‌اند (%d)" % len(clk))
    # «بی‌معامله» یعنی صفرِ معامله، نه صفرِ نمایشِ حجم: سهامِ گران‌قیمت با
    # حجمِ کم (مثل سپامهر: ۹۹۵۹ سهم در ۶۵ معامله) حجمشان در یکای «میلیارد سهم»
    # گرد می‌شود، ولی معامله داشته‌اند — گارد روی تعدادِ معامله است.
    ck(all(r["trades"] and r["trades"] > 0 for r in clk),
       "نامزدِ بی‌معامله نداریم (همه معامله داشته‌اند، %d نماد)" % len(clk))
    lh = ME.histogram(conn)
    ck(sum(b["count"] for b in lh["histo12"]) == lh["known"],
       "روی دادهٔ واقعی هم جمعِ میله‌ها = known (%d)" % lh["known"])
    lcs = ME.client_split(conn, "stock")
    tb_ = lcs["retail"]["buy_pct"] + lcs["institutional"]["buy_pct"]
    ck(abs(tb_ - 100.0) < 0.2, "درصد خرید حقیقی+حقوقی ≈ ۱۰۰ (was %s)" % tb_)
    lt = ME.timeline(conn)
    ck(lt["points"] >= 1, "حداقل یک نقطهٔ تایم‌لاین از همگام‌سازی ثبت شده")
    # ---- #170: درِ «تداوم» باید روی دادهٔ واقعی نشست داشته باشد --------------
    hist = ME.liquidity_history(conn)
    hk = [h for h in hist if h["value_hemat"]]
    ck(len(hk) >= ME.LIQ_CONTINUITY_MIN,
       "تداوم روی دادهٔ واقعی %d نشست دارد (بک‌فیلد از daily_prices)، نه «بدون داده»" % len(hk))
    saved = conn.execute("SELECT d_even, value_hemat FROM market_liquidity"
                         " ORDER BY d_even DESC LIMIT 1").fetchone()
    if saved:
        bf = ME._liquidity_from_price_history(conn, [int(saved[0])])
        ck(bool(bf) and abs(bf[0]["value_hemat"] - float(saved[1])) < 0.05,
           "مبنای بک‌فیلد = مبنای سینک (%s همت در برابر %s)"
           % (bf[0]["value_hemat"] if bf else None, float(saved[1])))
        ck(ME._liquidity_from_price_history(conn, [int(saved[0])], min_symbols=10 ** 9) == [],
           "روزی که نمادِ گردش‌دارش زیرِ کران باشد عدد نمی‌سازد (نصفه‌سینک)")
    ck(ME._liquidity_from_price_history(conn, [19990101]) == [],
       "روزی که در تاریخچۀ قیمت نیست عدد نمی‌سازد")
    conn.close()
else:
    print("SKIP: market.db not found — گاردهای دادهٔ واقعی کنار گذاشته شد")

# ==================== گارد ۱۳: صنایع داغ — «درصد» = میانگینِ تغییرِ قیمت =======
# «صنعت داغ» روی سَرجُای «بیشترین درصد» باید مبنایش میانگینِ تغییرِ قیمتِ پایانی
# نسبت به دیروز باشد (همان چیزی که کاربر پشتِ علامت ٪ می‌بیند) نه پراکندگیِ
# شمارِ مثبت‌ها؛ مخرج فقط نمادهای دارای درصد. صنعتِ بی‌معامله جریان=null
# می‌گیرد، نه صفرِ سبز. ارقامِ seed با دست قابلِ حساب‌اند.
ind_conn = new_db(); seed(ind_conn)
ind = ME.industries(ind_conn)
byind = {x["industry"]: x for x in ind["rows"]}
# فولاد تنها عضو «فلزات اساسي»: پایانی ۱۰۰۰ / دیروز ۹۰۰ ⇒ +۱۱.۱۱٪
ck(abs(byind["فلزات اساسي"]["avg_pct"] - 11.11) < 0.05,
   "درصدِ صنعت = میانگینِ تغییرِ قیمت (فولاد ≈ +۱۱.۱٪)، نه پراکندگیِ مثبت")
# وبملت صفرِ واقعی (پایانی = دیروز) ⇒ ۰.۰ و هنوز «داده» است، نه بی‌داده
ck(byind["بانكها و موسسات اعتباري"]["avg_pct"] == 0.0,
   "درصدِ صفرِ واقعی حفظ می‌شود (۰.۰ ≠ نبودِ داده)")
# حقا تنها عضو «سرمایه گذاريها» با −۳٪ ⇒ تک‌نمادیِ منفیِ واقعی، نه صفرِ گمراه‌کننده
ck(abs(byind["سرمایه گذاريها"]["avg_pct"] + 3.0) < 0.05,
   "تک‌نمادیِ −۳٪ عددِ واقعی نشان می‌دهد نه صفرِ breadth")
# هیچ میانگینی نباید از ±۵۰ عبور کند (نشانهٔ نشتِ breadth ۰..۱۰۰ به‌جای درصد)
leak = [x["industry"] for x in ind["rows"] if x["avg_pct"] is not None and abs(x["avg_pct"]) > 50]
ck(not leak, "هیچ «درصد» صنعتی شبیه پراکندگی (۰..۱۰۰) نیست (%s)" % leak)
# جریانِ عددی فقط برای صنعتِ دارای ارزشِ معامله؛ بی‌معامله ⇒ None
ck(all(x["flow_b_toman"] is None or x["value_b_toman"] > 0 for x in ind["rows"]),
   "جریانِ عددی فقط برای صنعتِ دارای ارزشِ معامله (بی‌داده=null)")
ind_conn.close()

BAD = [m for ok, m in CHECKS if not ok]
for m in BAD:
    print("  FAIL", m)
for ok, m in CHECKS:
    if ok:
        print("  PASS", m)
print("\n%d checks, %d failed" % (len(CHECKS), len(BAD)))
sys.exit(1 if BAD else 0)




