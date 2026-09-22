#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mstat_engine.py — موتور «وضعیت بازار» (فاز ۱ FTS-7)، محاسبه از دیتای لوکال.

فلسفه: داشبورد TradersArena را با همان داده‌هایی می‌سازیم که همین‌جا در
market.db نشسته است. هیچ عددی از بیرون وارد نمی‌شود و هیچ عددی هم
«تقریبِ بی‌برچسب» نیست: هر کموبیشاد در `notes` پاسخ نوشته می‌شود تا کاربر
بداند کدام ستون اندازه‌گیری است و کدام بازسازی.

ساختار داده (راستی‌آزمایی روی market.db، v9.7.5):
  market_watch : سطرِ جاریِ هر نماد (PK=ins_code) → فقط «آخرین لحظه» می‌ماند،
                 پس تاریخچهٔ درون‌روزی از آن ساخته نمی‌شود؛ برای تایم‌لاین
                 جدول mstat_snap هر همگام‌سازی را به‌عنوان یک نقطه ثبت می‌کند.
  q_tot_tran   = حجم (سهم)            q_tot_cap = ارزش (ریال)
                 z_tot_tran = تعداد معاملات
                 راستی‌آزمایی: q_tot_cap / q_tot_tran دقیقاً قیمت پایانی را
                 می‌دهد (نسبت ۱٫۰۰۰ روی ۱۲ نماد پرگردش) → واحدها تثبیت‌اند.
  client_type  : حجم و «تعداد» خرید/فروش حقیقی(i)/حقوقی(n). ارزش در این
                 فید وجود ندارد → ارزشِ هر گروه = حجم × قیمت میانگین (VWAP).
                 این تنها تقریبِ عددی داشبورد است و در notes ذکر می‌شود.
  blDs         : پنج خط اول عمق (خرید qmd/pmd/zmd، فروش qmo/pmo/zmo) —
                 فقط با withBestLimits=true در پاسخ می‌آید.

واحد خروجی‌ها (ثابت، در همهٔ پاسخ‌ها):
  حجم   → میلیارد سهم      ارزش → میلیارد تومان    سرانه → میلیون تومان
  پول   → میلیارد تومان     عمق  → میلیارد تومان
  ۱ همت = ۱۰۰۰ میلیارد تومان = ۱e۱۳ ریال
"""
from __future__ import annotations

import base64
import datetime
import json
import math
import zlib
from typing import Optional

# ---- یکاها ----
B_TUMAN_FROM_RIAL = 1e10     # ریال → میلیارد تومان
M_TUMAN_FROM_RIAL = 1e7      # ریال → میلیون تومان
B_SHARES = 1e9               # سهم → میلیارد سهم
HEMAT_IN_B_TUMAN = 1e3       # همت → میلیارد تومان

# آستانهٔ سلامت کلان بازار (سند FTS صفحهٔ ۳)
HEMAT_GOOD = 20.0            # ≥ ۲۰ همت → مساعد
HEMAT_BAD = 10.0             # ≤ ۱۰ همت → نامساعد
# قانون «فرصت ورود»: اگر بیش از این درصد نمادها منفی بودند، بازار در کف است
ENTRY_OPPORTUNITY_NEG_PCT = 80.0
# الگوی ساعت: اختلاف آخرین/پایانی
CLOCK_PCT = 1.0
# نمادی با کمتر از این تعداد معامله، «آخرین»ش برای شکارِ الگوی ساعت قابل
# اتکا نیست — همان آستانه‌ای که confidence_engine برای حجم تابلو دارد
# (tape_min_trades). بدون این ترمز، اختیارمعامله‌های ۱-۴ ریالی با یک تیک
# ۵۰٪ و ۱۰۰٪ می‌شوند و صدرِ جدول را می‌گیرند.
CLOCK_MIN_TRADES = 30
# کفِ قیمت برای رتبه‌بندیِ الگوی ساعت (ریال) — تیکِ یک ریالی روی سهمِ ۲ ریالی
# معنا ندارد، ولی روی سهمِ ۱۵۰۰ ریالی بله.
CLOCK_MIN_PRICE = 500.0

# ---- v9.8.1 — پنجرهٔ رسمی معاملات (رفع باگ تایم‌لاین درون‌روزی) ----
# بازار ایران ۰۹:۰۰ تا ۱۲:۳۵ (۱۲:۳۰ + پنجرهٔ پایانی) است. هر نقطهٔ خارج از
# این پنجره — همگام‌سازیِ شبانه، ردیف تستی یا ساعت جعلی — یک «افت شدید به صفر»
# یا خطِ موربِ دروغین روی چارت میسازد؛ ممنوع نوشته/خوانده میشود.
# ۰۸۵۵/۱۳۰۰۰۵ برای نویز ساعتِ سرور TSETMC حاشیه دارد.
SESSION_OPEN_HM = 85500        # 08:55:00 — شامل پیامِ آمادهباشِ ۰۹:۰۰
SESSION_CLOSE_HM = 130005      # 13:00:05 — شامل نقطهٔ پایانیِ ۱۳:۰۰


def in_trading_session(h_even, when=None) -> bool:
    """نقطهٔ h_even داخل بازهٔ رسمی معاملات ۰۹:۰۰–۱۳:۰۰ است؟

    `when` (اختیاری، datetime) داده شود و پنجشنبه/جمعه (آخر هفتهٔ ایران؛
    weekday()==3/4) باشد، False — همگام‌سازیِ آخر هفته هرگز نقطه نمیسازد حتی
    اگر h_even تازه باشد. توجه: شنبه/یکشنبه weekday()==5/6 هستند و روزِ
    کاری‌اند (شرطِ نادرستِ «>۲» همین‌جا در تست لو رفت).
    """
    try:
        h = int(_f(h_even))
    except (TypeError, ValueError):
        return False
    if h < SESSION_OPEN_HM or h > SESSION_CLOSE_HM:
        return False
    if when is not None and hasattr(when, "weekday") and when.weekday() in (3, 4):
        return False
    return True


# ---- دسته‌بندی ردیف‌های جدول خلاصه ----
CATEGORY_ROWS = [
    ("all",         "کل بازار"),
    ("eq_all",      "سهام، حق تقدم و ص.سهامی"),
    ("stock_right", "سهام و حق تقدم"),
    ("eq_fund",     "صندوق‌های سهامی و مختلط"),
    ("fixed_fund",  "صندوق درآمد ثابت"),
    ("top50",       "پنجاه شرکت بزرگ (شاخص ۵۰ شرکت)"),
    ("lev_fund",    "صندوق‌های اهرمی"),
    ("gold_fund",   "صندوق‌های طلا"),
    ("silver_fund", "صندوق‌های نقره"),
]

# تب‌های جدول تفکیک حقیقی/حقوقی
CLIENT_TABS = [
    ("all", "بازار"), ("eq_funds", "سهام و ص.سهامی"), ("stock", "سهام"),
    ("eq_fund", "ص.سهامی"), ("fixed", "ص.درآمدثابت"), ("top50", "۵۰ نماد بزرگ"),
    ("lev", "ص.اهرمی"), ("gold", "ص.طلا"), ("silver", "ص.نقره"),
]

# سطل‌های هیستوگرام ۱۲تاییِ بازدهی (درصد)
HISTO12 = [
    ("<-5",      "کمتر از ۵-",      -1e9, -5.0,  "neg"),
    ("-5..-4",   "۵- تا ۴-",        -5.0,  -4.0,  "neg"),
    ("-4..-3",   "۴- تا ۳-",        -4.0,  -3.0,  "neg"),
    ("-3..-2",   "۳- تا ۲-",        -3.0,  -2.0,  "neg"),
    ("-2..-1",   "۲- تا ۱-",        -2.0,  -1.0,  "neg"),
    ("-1..0",    "۰ تا ۱-",         -1.0,   0.0,  "neu"),
    ("0..1",     "۰ تا ۱+",          0.0,   1.0,  "neu"),
    ("1..2",     "۱+ تا ۲+",         1.0,   2.0,  "pos"),
    ("2..3",     "۲+ تا ۳+",         2.0,   3.0,  "pos"),
    ("3..4",     "۳+ تا ۴+",         3.0,   4.0,  "pos"),
    ("4..5",     "۴+ تا ۵+",         4.0,   5.0,  "pos"),
    (">5",       "بالاتر از ۵+",     5.0,   1e9,  "pos"),
]

# سطل‌های ۷تاییِ محدودهٔ قیمتی (گام ۳.۳). نسخهٔ نخست «زیر ۵-» و «۳- تا ۵-» را
# یکی گرفت و نمودار شش‌میله شد؛ اینجا هفت تا قفل می‌شود.
HISTO7 = [
    ("<-5",     "پایین‌تر از ۵-",    -1e9, -5.0, "neg"),
    ("-5..-3",  "۵- تا ۳-",          -5.0,  -3.0, "neg"),
    ("-3..-1",  "۳- تا ۱-",          -3.0,  -1.0, "neg"),
    ("-1..1",   "خنثی (۱- تا ۱+)",   -1.0,   1.0, "neu"),
    ("1..3",    "۱+ تا ۳+",           1.0,   3.0, "pos"),
    ("3..5",    "۳+ تا ۵+",           3.0,   5.0, "pos"),
    (">5",      "بالای ۵+",           5.0,   1e9, "pos"),
]

# کدهای وضعیتِ نماد در هر نقطهٔ زمانی (برای شمارش چرخش صف‌ها)
ST_BUYQ, ST_SELLQ, ST_POS, ST_NEG, ST_FLAT, ST_NONE = "b", "s", "p", "n", "z", "x"


def _f(v, default: float = 0.0) -> float:
    """تبدیل امن به float — همان قرارداد confidence_engine._f."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    return x if math.isfinite(x) else default


def _div(a, b):
    """تقسیم امن → None یعنی «ساختنی نبود» (نه صفر). صفرِ واقعی با None فرق دارد."""
    if a is None or b is None:
        return None
    b = _f(b)
    if b == 0.0:
        return None
    return _f(a) / b


# ================================================== ساختار (منبعِ یکتای DDL)
# test_tsetmc.create_schema این را صدا می‌زند و app.get_db هم همین‌طور — پس
# «همراه هر اتصال» تضمین می‌شود ستون‌ها هستن، حتی اگر بانک از نسخهٔ ۹٫۷٫۳
# آمده باشد و هنوز هیچ همگام‌سازیِ تازه‌ای اجرا نشده باشد. یک‌جا تعریف شدن
# هم یعنی مسیرِ نوشتن و مسیرِ خواندن هرگز سرِ اسمِ ستون دعوایشان نمی‌شود.
MIGRATIONS = {
    # جمعِ پنج خطِ اول و جدا «خطِ اول» از blDs — تنها منبعِ عمقِ لوکال.
    "market_watch": [
        ("buy_q_vol", "REAL"), ("buy_q_val", "REAL"), ("buy_q_cnt", "REAL"),
        ("sell_q_vol", "REAL"), ("sell_q_val", "REAL"), ("sell_q_cnt", "REAL"),
        ("buy_q1_vol", "REAL"), ("buy_q1_px", "REAL"),
        ("sell_q1_vol", "REAL"), ("sell_q1_px", "REAL"),
    ],
    # طبقهٔ ابزار از فیلتر paperType خودِ TSETMC (۱/۲=سهام، ۴=حق تقدم، ۸=صندوق).
    "instruments": [("paper_type", "INTEGER")],
}

SNAP_DDL = """CREATE TABLE IF NOT EXISTS mstat_snap (
            d_even INTEGER NOT NULL, h_even INTEGER NOT NULL,
            ts TEXT, agg TEXT, PRIMARY KEY (d_even, h_even))"""


def ensure_schema(conn) -> None:
    """migrate + ساختِ جدولِ نقطه‌ها. بی‌صدا می‌بخشد: بانکِ قفل‌شده نباید
    یک درخواستِ خواندن را ۵۰۰ کند — دادهٔ قدیمی از بی‌داده بهتر است."""
    try:
        conn.execute(SNAP_DDL)
    except Exception:
        pass
    for table, cols in MIGRATIONS.items():
        try:
            have = {r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)}
        except Exception:
            continue
        for name, typ in cols:
            if name not in have:
                try:
                    conn.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, name, typ))
                except Exception:
                    pass


# ============================================================ طبقه‌بندی ابزار
# اولویت: نام/سکتور، آن‌گاه paperType. دلیل: فیلترِ paperType خودِ TSETMC
# نشت‌کننده است — یک ابزار را می‌تواند زیرِ چندین paperType برگرداند، و چون
# fetch_paper_types نخستین دسته‌ای که می‌بیند را پیاده می‌کند، بسیاری از
# صندوق‌ها/اوراق برای همیشه pt=1 (سهام) می‌گیرند. روی دادهٔ ۲۰۲۶-۰۹-۱۹: از
# ۱۷۷۳ ردیفِ pt=1/2 تعداد ۸۸۲ تا غیرسهامی بودند (۳۶۳ اوراق، ۳۶۹ صندوق، ۵
# تسهیلات) و ۶۷,۰۹۳ میلیارد تومان از سطرِ «سهام و حق تقدم» می‌ربودند؛ ضمناً
# هر پنج سطرِ صندوقی صفر می‌شدند چون fund_kind فقط برای pt=8 اجرا می‌شد.
# کلیدواژه‌ها همان assetType.ts سمتِ فرانت‌اند‌اند که از پیش درست کار می‌کند؛
# اینجا فقط همان منطق به سرور آورده می‌شود تا دو طرفِ مرز یک دست بمانند.

PAPER_STOCK, PAPER_RIGHT, PAPER_FUND = "stock", "right", "fund"

_FUND_KINDS = (
    ("lev",    ("اهرم", "اهرمي", "اهرام")),
    ("gold",   ("طلا", "طلایی", "Gold", "ياره", "گلگشت", "عيار", "ثروت آفرين")),
    ("silver", ("نقره", "سيور")),
    ("fixed",  ("درآمد ثابت", "درامد ثابت", "ثابت", "اقتدار", "ادوار", "آهنگ")),
    ("mixed",  ("مختلط",)),
    ("commod", ("كالا", "کالا", "پتروشيمه", "فلزات")),
    ("fof",    ("در صندوق",)),
    # «بخشی/شاخصی/جسورانه/تضمین/پروژه/مشترک» و خودِ واژهٔ «سهام» همگی
    # صندوقِ سهامی‌اند. اینها نبودند: ۱۴۵ صندوقِ سهامی بی‌طبقه می‌ماندند و
    # سطر «صندوق‌های سهامی و مختلط» ۲۱٪ کم‌شمار می‌شد.
    ("equity", ("سهام", "سهامی", "بخش", "شاخص", "جسوران", "تضمین", "تامين",
                "پروژه", "مشترك", "مشترک", "اعتبارسهام")),
)


def fund_kind(l_val30: str, l_val18: str) -> str:
    """زیرگونهٔ صندوق از نام — تنها راهِ تمایز «درآمد ثابت» از «سهامی».

    TSETMC زیرگونهٔ صندوق را در MarketWatch نمی‌دهد (paperType=8 برای همه یکی
    است)، پس نام تنها دادهٔ موجود است. صندوقی که هیچ کلیدواژه‌ای ندارد 'etf'
    می‌شود و در هیچ سطر تخصصی نمی‌نشیند؛ عمداً آن را «سهامی» نمی‌نامیم، چون
    فرضِ بی‌مورد یعنی عددِ غلط در جدول.
    """
    name = (l_val30 or "") + " " + (l_val18 or "")
    for kind, keys in _FUND_KINDS:
        for k in keys:
            if k and k in name:
                return kind
    tail = (l_val30 or "").rstrip()
    if tail.endswith("-د"):
        return "fixed"
    if tail.endswith("-س") or tail.endswith("-ب"):
        return "equity"
    return "etf"


# v9.8.2 — قراردادهای اختیار: TSETMC در یک تغییرِ اخیر آن‌ها را در پاسخِ
# paperType=1 (همان فهرستِ سهام) هم برمی‌گرداند، پس مقدارِ paper_type در بانک
# ممکن است ۱ باشد در حالی که ابزار اختیار است. نامشان («اختيارخ/اختيارف/اختيارج»
# با یِ عربی، یا «اختیار» با یِ فارسی) بی‌ابهام است. روی دادهٔ ۲۰۲۶-۰۹-۱۹:
# ۱۹۰۸ اختیار هست که ۱۴۶۱ تایشان paper_type=1 گرفته‌اند، و هیچ نامِ غیر-اختیاری
# این کلیدها را ندارد (سوءاثرِ صفر، تأییدشده با کوئری).
_OPTION_KEYS = ("اختيار", "اختیار")


def is_option(l_val30: str = "", l_val18: str = "") -> bool:
    """نام، قرارداد اختیار را نشان می‌دهد — تنها راهِ بی‌ابهام وقتی paperType دروغ می‌گوید."""
    name = (l_val30 or "") + " " + (l_val18 or "")
    return any(k in name for k in _OPTION_KEYS)


# v9.10.2 — کشفِ نام-محورِ صندوق/اوراق/تسهیلات.
# ي/ك عربی و نیم‌فاصله: «اوراق تامين مالي» و «صندوق سرمايه گذاري» در بانک با
# نوشتارِ عربی ذخیره شده‌اند، پس بدون یکسان‌سازی، کلیدواژهٔ فارسی هیچ‌وقت
# تطبیق نمی‌خورد.
_NORMALIZE = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "‌": "", "‍": ""})

_BOND_SYM_PREFIX = ("اخزا", "اراد", "افاد", "گام")
_BOND_NAME = ("اوراق", "اسناد")
_BOND_SECTOR = ("اوراق تامین",)
_FUND_NAME = ("صندوق", "ETF")
_FUND_SECTOR = ("صندوق سرمایه",)
_TESEH_SECTOR = ("اوراق حق تقدم",)


def _norm(s: str) -> str:
    """نرمال‌سازیِ نوشتار — همان norm در assetType.ts: ی/ک عربی و نیم‌فاصله."""
    return (s or "").translate(_NORMALIZE).strip()


def is_fund(l_val18: str = "", l_val30: str = "", sector_name: str = "") -> bool:
    """صندوق بودن از نام/سکتور — «صندوق سرمايه گذاري...» سکتورِ رسمیِ همهٔ صندهاست."""
    n, c = _norm(l_val30), _norm(sector_name)
    return any(k in n for k in _FUND_NAME) or any(k in c for k in _FUND_SECTOR)


def is_bond(l_val18: str = "", l_val30: str = "", sector_name: str = "") -> bool:
    """اوراق بودن از نماد/نام/سکتور — «اوراق تامين مالي» سکتورِ رسمیِ اوراق است."""
    s, n, c = _norm(l_val18).upper(), _norm(l_val30), _norm(sector_name)
    return (s.startswith(_BOND_SYM_PREFIX) or any(k in n for k in _BOND_NAME)
            or any(k in c for k in _BOND_SECTOR))


def is_teseh(l_val18: str = "", l_val30: str = "", sector_name: str = "") -> bool:
    """اوراق حق تقدم (تسهیلات مسکن/ملی) — نه خودِ حق تقدم.

    فقط از سکتور تشخیص داده می‌شود: پیشوندِ «ض»/«ط» در نماد، علاوه بر تسهیلات،
    نمادهای اختیارِ خرید/فروش را هم پوشش می‌دهد (۱۵۶۲ نماد در ۲۰۲۶-۰۹-۱۹) و
    آن‌ها فقط با نامشان از تمایز می‌شوند، پس پیشوند در اینجا به‌تنهایی ناایمن است."""
    return any(k in _norm(sector_name) for k in _TESEH_SECTOR)


def classify(paper_type, l_val30: str = "", l_val18: str = "", sector_name: str = "") -> tuple:
    """(طبقه، زیرگونه) — اول نام/سکتور، بعد paperType.

    ترتیب دقیقاً assetType.ts است: اختیار → صندوق → اوراق → تسهیلات →
    حق تقدم → paperType. اختیارها باید اول بیایند، چون اختیارِ اهرم سکتورِ
    «صندوق سرمایه گذاری» می‌گیرد وگرنه به جای صندوق می‌نشیند. paperType به
    تنهایی کافی نیست (بالای این بخش توضیح داده شد)؛ نام و سکتور بی‌ابهام‌اند
    و هر دو در همان سطرِ market_watch موجودند."""
    if is_option(l_val30, l_val18):
        return "other", "other"
    if is_fund(l_val18, l_val30, sector_name):
        return PAPER_FUND, fund_kind(l_val30, l_val18)
    if is_bond(l_val18, l_val30, sector_name):
        return "other", "other"
    if is_teseh(l_val18, l_val30, sector_name):
        return "other", "other"
    if _norm(l_val18).upper().endswith("ح") or "حق تقدم" in _norm(l_val30):
        return PAPER_RIGHT, "right"
    if paper_type in (1, 2):
        return PAPER_STOCK, "stock"
    if paper_type == 4:
        return PAPER_RIGHT, "right"
    if paper_type == 8:
        # v9.10.3 — فیلترِ paperTypeِ TSETMC پایدار نیست: در یک همگام‌سازی
        # واقعی (۲۰۲۶-۰۹-۲۲) پاسخِ pt=8 شاملِ ۱۱۶۸ سهامِ عادیِ واقعی بود —
        # فولاد، وبملت، شستا، شپنا، فملي، خگستر — در حالی که پاسخِ pt=1 همان
        # نمادها را سهام می‌نمایاند. چون fetch_paper_types خاص‌ترین طبقه را
        # برنده می‌کند (rank ۸ > ۱)، این شرکت‌ها برای همیشه «صندوق» ذخیره
        # می‌شدند. نتیجه: سطرِ «پنجاه شرکت بزرگ» همیشه صفر (هیچ سهامی وجود
        # نداشت) و سطرهای صندوق ~۴۷ برابرِ واقعی متورم می‌شدند.
        # راهِ درست: pt=8 فقط وقتی صندوق می‌سازد که نام/سکتور هم تأییدش کند.
        # در غیرِ این صورت به طبقهٔ سهام می‌غلتد (یا اگر نشانهٔ حق‌تقدم/اختیار
        # دارد، همان طبقه). این عکسِ باگِ قبلی نیست — نام بی‌ابهام است و
        # paperType فقط در صورتِ تأیید اعتبار می‌گیرد.
        if is_fund(l_val18, l_val30, sector_name):
            return PAPER_FUND, fund_kind(l_val30, l_val18)
        if _norm(l_val18).upper().endswith("ح") or "حق تقدم" in _norm(l_val30):
            return PAPER_RIGHT, "right"
        return PAPER_STOCK, "stock"
    return "other", "other"


# ============================================================ بارگذاری اسنپ‌شات
_CTX = {}   # امضای بانک → ctx — از تکرار اسکنِ ۳۵۰۰ سطری در هر درخواست می‌کاهد


def _signature(conn) -> tuple:
    """امضای بانک: روز، ساعت، تعداد و آخرین fetched_at. هر همگام‌سازی عوضش
    می‌کند، پس کش هیچ‌وقت دادهٔ کهنهٔ «درست‌نما» سرو نمی‌کند."""
    try:
        row = conn.execute(
            "SELECT MAX(d_even), MAX(h_even), COUNT(*), MAX(fetched_at) FROM market_watch").fetchone()
        return ("mw", row[0], row[1], row[2], row[3])
    except Exception:
        return ("mw", 0, 0, 0, "")


def _has_queue_cols(conn) -> bool:
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(market_watch)")}
    except Exception:
        return False
    return "buy_q_val" in cols


# ترتیبِ ستون‌های client_type در کوئریِ بارگذاری — تنها مرجعِ اندیس‌ها.
_CT_FIELDS = {"ins_code": 0, "buy_i_vol": 1, "buy_n_vol": 2, "buy_ddd_vol": 3,
              "buy_count_i": 4, "buy_count_n": 5, "sell_i_vol": 6, "sell_n_vol": 7,
              "sell_count_i": 8, "sell_count_n": 9}
_CT_ORDER = ", ".join(sorted(_CT_FIELDS, key=_CT_FIELDS.get))


def _row_keys(have_depth: bool):
    keys = ["ins_code", "symbol", "name", "sector_code", "sector_name",
            "p_closing", "p_last", "p_yesterday", "p_first", "p_min", "p_max",
            "allowed_min", "allowed_max"]
    if have_depth:
        keys += ["buy_q_vol", "buy_q_val", "buy_q_cnt",
                 "sell_q_vol", "sell_q_val", "sell_q_cnt",
                 "buy_q1_vol", "buy_q1_px", "sell_q1_vol", "sell_q1_px"]
    keys += ["q_vol", "q_val", "n_trades", "price_change", "total_shares",
             "base_vol", "h_even", "paper_type"]
    return keys


def load_snapshot(conn, force: bool = False) -> dict:
    """یک اسکن کامل → فهرست دیکشنری‌های آمادهٔ تجمیع (تک‌کوئری، بدون N+1).

    `depth=False` یعنی ستون‌های عمق هنوز در این بانک پر نشده‌اند (همگام‌سازی
    نسخهٔ قدیمی). آن‌وقت پنل‌های صف «بی‌داده» می‌شوند، نه صفرِ قرمز — همان
    تفکیک fail/nodata که در confidence_engine اصلِ کار است.

    کش روی «همان اتصال» قفل می‌شود، نه فقط روی امضای داده: دو بانکِ متفاوت
    می‌توانند دقیقاً همان روز/ساعت/تعداد را داشته باشند و آن‌وقت سطرهای یکی
    به نامِ دیگری سرو می‌شد. مقایسهٔ هویتِ اتصال ارزان و قطعی است.
    """
    sig = _signature(conn)
    if not force and _CTX.get("conn") is conn and _CTX.get("sig") == sig:
        return _CTX["data"]

    day = conn.execute("SELECT MAX(d_even) FROM market_watch").fetchone()[0]
    hour = conn.execute(
        "SELECT MAX(h_even) FROM market_watch WHERE d_even=?", (day,)).fetchone()[0] or 0
    cday = conn.execute("SELECT MAX(d_even) FROM client_type").fetchone()[0]
    have_depth = _has_queue_cols(conn)

    cols = """m.ins_code, i.l_val18, i.l_val30, i.sector_code, i.sector_name,
              m.p_closing, m.p_last, m.price_yesterday, m.price_first,
              m.price_min, m.price_max, m.allowed_min, m.allowed_max,"""
    if have_depth:
        cols += """ m.buy_q_vol, m.buy_q_val, m.buy_q_cnt,
                    m.sell_q_vol, m.sell_q_val, m.sell_q_cnt,
                    m.buy_q1_vol, m.buy_q1_px, m.sell_q1_vol, m.sell_q1_px,"""
    cols += """ m.q_tot_tran, m.q_tot_cap, m.z_tot_tran, m.price_change,
               m.total_shares, i.base_vol, m.h_even, i.paper_type"""
    rows = conn.execute(
        "SELECT %s FROM market_watch m LEFT JOIN instruments i ON i.ins_code=m.ins_code "
        "WHERE m.d_even=?" % cols, (day,)).fetchall()

    client = {}
    for r in conn.execute(
            "SELECT %s FROM client_type WHERE d_even=?" % _CT_ORDER, (cday,)).fetchall():
        client[r[0]] = r

    out = []
    keys = _row_keys(have_depth)
    for r in rows:
        d = dict(zip(keys, tuple(r)))
        d["symbol"] = (d.get("symbol") or "").strip()
        d["name"] = (d.get("name") or "").strip()
        d["cls"], d["kind"] = classify(d.get("paper_type"), d["name"], d["symbol"],
                                      d.get("sector_name"))
        py, pcl, plst = d.get("p_yesterday"), d.get("p_closing"), d.get("p_last")
        # بازدهیِ پایانی نسبت به دیروز — همان «مثبت/منفی» بودنِ نماد.
        # قیمتِ دیروز باید هم‌مرتبهٔ پایانی باشد، وگرنه شمارش آلوده می‌شود.
        d["pct"] = (100.0 * _div(_f(pcl) - _f(py), py)
                    if pcl and py and px_near(py, pcl) else None)
        # الگوی ساعت: آخرین معامله چقدر بالای قیمت پایانی است — فقط اگر
        # «آخرین» واقعاً داخل باندِ مجازِ همین نشست باشد.
        d["clock_pct"] = (100.0 * _div(_f(plst) - _f(pcl), pcl)
                          if pcl and plst is not None and px_in_band(d, plst, pcl) else None)
        d["ct"] = client.get(d["ins_code"])
        out.append(d)

    _CTX["conn"] = conn
    _CTX["sig"] = sig
    _CTX["data"] = {"asof": {"d_even": day, "h_even": hour, "client_d_even": cday,
                             "depth": have_depth},
                    "rows": out, "depth": have_depth,
                    "base_est": _base_volume_estimate(conn, day)}
    return _CTX["data"]


def _base_volume_estimate(conn, day) -> dict:
    """میانگین حجم ۴ نشستِ پیشین (بدون امروز) — تعریف رسمی حجم مبنا.

    در بانک فقط ۳۵ نماد base_vol>1 دارند (بقیه ۱، یعنی «تعریف‌نشده» نه «یک
    سهم»)، پس بدون این بازسازی، سطر «صف کمتر از حجم مبنا» عملاً همیشه خالی
    می‌ماند و کاربر یک صفرِ گمراه‌کننده می‌بیند.
    """
    out = {}
    try:
        hist = conn.execute(
            """SELECT ins_code, q_tot_tran FROM daily_prices
               WHERE d_even < ? AND q_tot_tran > 0
                 AND d_even >= (SELECT MIN(d_even) FROM (
                      SELECT DISTINCT d_even FROM daily_prices WHERE d_even < ?
                      ORDER BY d_even DESC LIMIT 4))
               ORDER BY ins_code, d_even DESC""", (day, day)).fetchall()
    except Exception:
        return out
    acc = {}
    for ic, v in hist:
        lst = acc.setdefault(ic, [])
        if len(lst) < 4:
            lst.append(_f(v))
    for ic, lst in acc.items():
        if len(lst) >= 2:
            out[ic] = sum(lst) / len(lst)
    return out


def eff_base_vol(row: dict, base_est: dict) -> Optional[float]:
    """حجم مبنای مؤثر: مقدارِ اعلامی اگر معنادار بود، وگرنه برآورد ۴ نشست."""
    bv = row.get("base_vol")
    if bv and _f(bv) > 1.0:
        return _f(bv)
    return base_est.get(row["ins_code"])


# --------------------------------------------------- ترمزِ داده‌های نامعقول
# TSETMC برای ابزارهای بی‌معامله گاهی در فیلدِ «تغییر قیمت» تاریخ می‌گذارد
# (pc=20260907). جمعِ آن با یک قیمتِ ۱ ریالی، «آخرین معامله» را ۲۰٬۰۰۰٬۰۰۰
# ریال می‌کند و ستونِ «اختلاف آخرین/پایانی» — یعنی همان ستونی که شکارِ
# الگوی ساعت به آن وابسته است — یک‌سره بی‌معنا می‌شود. بی‌رمزِ بی‌فرض، همان
# باندِ مجازِ روز است که خودِ TSETMC می‌فرستد؛ وگرنه فاصلهٔ معقول از پایانی.
def _band_ok(row, v) -> Optional[bool]:
    amin, amax = _f(row.get("allowed_min")), _f(row.get("allowed_max"))
    if amin > 0 and amax >= amin > 0:
        return bool(amin * 0.999 <= v <= amax * 1.001)
    return None


def px_in_band(row, v, ref) -> bool:
    """آیا v می‌تواند قیمتِ همین نماد در همین نشست باشد؟

    باندِ مجاز تنها ترمز نیست: واحدهای صندوق اغلب باند [۱ .. ۹۹٬۹۹۹٬۹۹۹]
    دارند (چون محدودهٔ نوسان روزانه ندارند) و هر عددی داخلش رد می‌شود. پس
    نسبتِ v به قیمتِ پایانی هم باید معقول بماند — در یک نشست، «آخرین» نمی‌تواند
    ده‌ها برابرِ «پایانی» باشد؛ همان‌قدر که سقفِ روزانه allow نمی‌کند.
    """
    v, ref = _f(v), _f(ref)
    if v <= 0 or ref <= 0:
        return False
    ok = _band_ok(row, v)
    if ok is False:
        return False
    return 0.5 <= v / ref <= 2.0


def px_near(v, ref, tol: float = 2.0) -> bool:
    """مقایسهٔ یک عدد با مرجع در همان مرتبهٔ اندازه — برای قیمتِ دیروز که
    لزوماً داخل باندِ امروز نیست (حدِ روزانه جابه‌جایی‌اش می‌دهد)."""
    v, ref = _f(v), _f(ref)
    return bool(v > 0 and ref > 0 and (1.0 / tol) <= v / ref <= tol)



# ============================================================ شاخص‌های هر نماد
def top50_codes(rows) -> set:
    """۵۰ شرکت بزرگ بر پایهٔ ارزش بازار (تعداد سهام × قیمت پایانی).

    شاخص «۵۰ شرکت» یک فهرست متحرک است و در بانک نیست؛ تنها راهِ لوکال همین
    رتبه‌بندی است. فقط سهام عادی حساب می‌شوند (صندوق‌ها رقابت نمی‌کنند)، وگرنه
    صندوق‌های درآمد ثابت با NAVِ میلیاردی صدرنشین می‌شدند.
    """
    scored = []
    for r in rows:
        if r["cls"] != PAPER_STOCK:
            continue
        cap = _f(r.get("total_shares")) * _f(r.get("p_closing"))
        if cap > 0:
            scored.append((cap, r["ins_code"]))
    scored.sort(reverse=True)
    return {ic for _, ic in scored[:50]}


def in_category(row, cat: str, top50) -> bool:
    """عضویت در سطرهای جدول خلاصه — دقیقاً همان نه ردیف تریدرزآرنا."""
    cls, kind = row["cls"], row["kind"]
    if cat == "all":
        return True
    if cat == "eq_all":
        return cls in (PAPER_STOCK, PAPER_RIGHT) or (cls == PAPER_FUND and kind in ("equity", "fof"))
    if cat == "stock_right":
        return cls in (PAPER_STOCK, PAPER_RIGHT)
    if cat == "eq_fund":
        return cls == PAPER_FUND and kind in ("equity", "mixed", "fof", "etf")
    if cat == "fixed_fund":
        return cls == PAPER_FUND and kind == "fixed"
    if cat == "lev_fund":
        return cls == PAPER_FUND and kind == "lev"
    if cat == "gold_fund":
        return cls == PAPER_FUND and kind == "gold"
    if cat == "silver_fund":
        return cls == PAPER_FUND and kind == "silver"
    if cat == "top50":
        return row["ins_code"] in top50
    return False


def money(row, base_est) -> dict:
    """همهٔ ارقامِ ریالیِ یک نماد → یک دیکشنری. ارزش هر گروه = حجم × VWAP.

    VWAP از خودِ بانک درمی‌آید (ارزش÷حجم) و نه از قیمت پایانی: در ۱۲ نماد
    پرگردش، ارزش÷حجم دقیقاً قیمت پایانی را می‌دهد، پس همان دقت را دارد و
    برای نمادهایی که پایانیِ صفر دارند هم کار می‌کند.

    ردیف client_type با اندیس‌های نامدار خوانده می‌شود، نه با شمارهٔ دستی؛
    نسخهٔ نخستِ این تابع sell_n_vol را به‌جای sell_count_n می‌خواند و «تعداد»
    را در مخرج سرانه می‌گذاشت — عددِ غلط ولی خوش‌قالب. نام‌گذاریِ صریح، همان
    اشتباهِ کلاسِ fts_engine را غیرممکن می‌کند.
    """
    ct = row.get("ct") or ()
    g = _CT_FIELDS

    def cget(name, default=0.0):
        if not ct or len(ct) <= g[name]:
            return default
        return ct[g[name]]

    vol, val = _f(row.get("q_vol")), _f(row.get("q_val"))
    vwap = _div(val, vol) or _f(row.get("p_closing")) or 0.0

    def opt(key):
        v = row.get(key)
        return None if v is None else _f(v)

    m = {"vol": vol, "val": val, "vwap": vwap, "trades": _f(row.get("n_trades")),
         "bq_val": opt("buy_q_val"), "sq_val": opt("sell_q_val"),
         "bq_vol": opt("buy_q_vol"), "sq_vol": opt("sell_q_vol"),
         "bq_cnt": opt("buy_q_cnt"), "sq_cnt": opt("sell_q_cnt"),
         "bq1_vol": opt("buy_q1_vol"), "bq1_px": opt("buy_q1_px"),
         "sq1_vol": opt("sell_q1_vol"), "sq1_px": opt("sell_q1_px"),
         "has_ct": bool(ct)}

    m["retail_buy"] = _f(cget("buy_i_vol")) * vwap
    m["retail_sell"] = _f(cget("sell_i_vol")) * vwap
    m["inst_buy"] = _f(cget("buy_n_vol")) * vwap
    m["inst_sell"] = _f(cget("sell_n_vol")) * vwap
    m["ddd_buy"] = _f(cget("buy_ddd_vol")) * vwap
    m["n_buy_i"] = int(_f(cget("buy_count_i")))
    m["n_sell_i"] = int(_f(cget("sell_count_i")))
    m["n_buy_n"] = int(_f(cget("buy_count_n")))
    m["n_sell_n"] = int(_f(cget("sell_count_n")))

    # سرانه = ارزش ÷ تعدادِ همان گروه؛ None یعنی «مخرج صفر بود» نه «صفر»
    m["pc_buy"] = _div(m["retail_buy"], m["n_buy_i"])
    m["pc_sell"] = _div(m["retail_sell"], m["n_sell_i"])
    m["power"] = _div(m["pc_buy"], m["pc_sell"])
    m["flow"] = m["retail_buy"] - m["retail_sell"]
    m["base"] = eff_base_vol(row, base_est)
    m["qstate"] = queue_state(row, m)
    return m


def queue_state(row, m) -> str:
    """تک‌حرفِ وضعیت صف: b=خرید، s=فروش، p=مثبت، n=منفی، z=صفر، x=بی‌داده.

    «صف» یعنی یک سمتِ دفتر کاملاً خالی است؛ شرطِ «قیمت به محدودِ مجاز چسبیده»
    لازم نیست و حتی گمراه‌کننده است (در نمادهای بی‌مبنا قیمت پایانی می‌تواند
    زیر سقف باشد ولی صف خرید بماند). اگر عمق در بانک نباشد x برمی‌گردد، نه z.
    """
    if m.get("bq_val") is None:
        return ST_NONE
    if m["bq_val"] > 0 and not m["sq_val"]:
        return ST_BUYQ
    if m["sq_val"] > 0 and not m["bq_val"]:
        return ST_SELLQ
    pct = row.get("pct")
    if pct is None:
        return ST_NONE
    if pct > 0:
        return ST_POS
    if pct < 0:
        return ST_NEG
    return ST_FLAT


# ============================================================ تجمیع مشترک
def enrich(conn, force: bool = False) -> tuple:
    """(ردیف‌ها با شاخص‌های پولی, متادیتا) — یک بار به‌ازای هر اسنپ‌شات."""
    snap = load_snapshot(conn, force=force)
    rows, base_est = snap["rows"], snap["base_est"]
    top50 = top50_codes(rows)
    for r in rows:
        r["_m"] = money(r, base_est)
        r["_top50"] = r["ins_code"] in top50
    return rows, dict(snap["asof"], top50=len(top50), n=len(rows))


def _agg(rows) -> dict:
    """جمعِ ریالیِ یک دسته → سرانه‌ها و نسبت‌ها در یکای نمایشی."""
    a = {"n": len(rows), "n_traded": 0,
         "vol": 0.0, "val": 0.0, "rb": 0.0, "rs": 0.0, "ib": 0.0, "is": 0.0,
         "nbi": 0, "nsi": 0, "nbn": 0, "nsn": 0,
         "bq": 0.0, "sq": 0.0, "bqv": 0.0, "sqv": 0.0, "depth_n": 0}
    for r in rows:
        m = r["_m"]
        if m["val"] > 0:
            a["n_traded"] += 1
        a["vol"] += m["vol"]
        a["val"] += m["val"]
        a["rb"] += m["retail_buy"]
        a["rs"] += m["retail_sell"]
        a["ib"] += m["inst_buy"]
        a["is"] += m["inst_sell"]
        a["nbi"] += m["n_buy_i"]
        a["nsi"] += m["n_sell_i"]
        a["nbn"] += m["n_buy_n"]
        a["nsn"] += m["n_sell_n"]
        if m["bq_val"] is not None:
            a["depth_n"] += 1
            a["bq"] += m["bq_val"]
            a["sq"] += m["sq_val"] or 0.0
            a["bqv"] += m["bq_vol"] or 0.0
            a["sqv"] += m["sq_vol"] or 0.0
    a["pc_buy_mt"] = _div(_div(a["rb"], a["nbi"]), M_TUMAN_FROM_RIAL)   # میلیون تومان
    a["pc_sell_mt"] = _div(_div(a["rs"], a["nsi"]), M_TUMAN_FROM_RIAL)
    a["power"] = _div(a["pc_buy_mt"], a["pc_sell_mt"])
    a["flow_bt"] = (a["rb"] - a["rs"]) / B_TUMAN_FROM_RIAL              # میلیارد تومان
    a["vol_bs"] = a["vol"] / B_SHARES                                    # میلیارد سهم
    a["val_bt"] = a["val"] / B_TUMAN_FROM_RIAL                           # میلیارد تومان
    a["val_hemat"] = a["val_bt"] / HEMAT_IN_B_TUMAN                      # همت
    a["bq_bt"] = a["bq"] / B_TUMAN_FROM_RIAL
    a["sq_bt"] = a["sq"] / B_TUMAN_FROM_RIAL
    return a


def category_rows(rows) -> dict:
    """نقشهٔ cat → ردیف‌های آن دسته (یک پاس روی ردیف‌ها، بدون کوئریِ تکراری)."""
    buckets = {c: [] for c, _ in CATEGORY_ROWS}
    for r in rows:
        for cat, _label in CATEGORY_ROWS:
            if cat == "top50":
                if r["_top50"]:
                    buckets[cat].append(r)
            elif in_category(r, cat, None):
                buckets[cat].append(r)
    return buckets


# ============================================================ گام ۱: جدول خلاصه
def summary(conn) -> dict:
    """جدول بالای تب: ۹ سطر دسته‌ای با شش ستون محاسباتی + سلامت کلان."""
    rows, meta = enrich(conn)
    buckets = category_rows(rows)
    out = []
    for cat, label in CATEGORY_ROWS:
        a = _agg(buckets[cat])
        out.append({
            "key": cat, "label": label,
            "symbols": a["n"], "traded": a["n_traded"],
            "volume_b_shares": round(a["vol_bs"], 3),
            "value_b_toman": round(a["val_bt"], 1),
            "pc_buy_m_toman": None if a["pc_buy_mt"] is None else round(a["pc_buy_mt"], 1),
            "pc_sell_m_toman": None if a["pc_sell_mt"] is None else round(a["pc_sell_mt"], 1),
            "buy_power": None if a["power"] is None else round(a["power"], 2),
            # رنگِ قدرت خرید فقط یک نمایش است: >=۱ سبز، <۱ قرمز (منفی نیست)
            "buy_power_up": bool(a["power"] is not None and a["power"] >= 1.0),
            "money_flow_b_toman": round(a["flow_bt"], 1),
        })
    return {"status": "ok", "asof": meta, "rows": out,
            "health": macro_health_from(_agg(buckets["eq_all"]), _agg(buckets["all"]))}


def macro_health_from(eq: dict, allmkt: dict = None) -> dict:
    """برچسب سلامت کلان از ارزش معاملات (سند FTS صفحهٔ ۳): ≥۲۰ همت مساعد.

    مبنای برچسب «سهام، حق تقدم و ص.سهامی» است، نه کلِ جدول. کل بازار با
    شمارشِ بلوک‌های صندوق درآمد ثابت ۲۰۸ همت می‌شود (۶۱ همتِ آن تنها از ۱۳۸
    صندوق درآمد ثابت است) و آن‌وقت آستانهٔ ۲۰ همت همیشه سبز می‌ماند و
    شاخصِ سلامت هیچ‌گاه نمی‌تواند قرمز شود — یعنی بی‌اثر. عددِ کل هم
    گزارش می‌شود، فقط داور نیست.
    """
    hemat = eq["val_hemat"]
    if hemat >= HEMAT_GOOD:
        state, label = "good", "مساعد"
    elif hemat <= HEMAT_BAD:
        state, label = "bad", "نامساعد"
    else:
        state, label = "mid", "متوسط"
    return {"value_hemat": round(hemat, 2), "state": state, "label": label,
            "basis": "eq_all",
            "value_hemat_all_market": round(allmkt["val_hemat"], 2) if allmkt else None,
            "good_min": HEMAT_GOOD, "bad_max": HEMAT_BAD}


def macro_health(conn) -> dict:
    rows, _meta = enrich(conn)
    return macro_health_from(_agg(_select(rows, "eq_all")), _agg(_select(rows, "all")))


# ================================ v9.8.0 — بنر نقدینگی کلان + جریان پول هوشمند =================
# نقشهٔ راهبرد FTS: بنرِ شاخص نقدینگی (ارزش معاملات خرد) + نشانگرِ مقایسهٔ جریان
# پولِ حقیقی بین «سهام/حق‌تقدم» و «صندوق‌های درآمد ثابت». هر دو از همان
# enrich/_agg موجود ساخته می‌شوند — هیچ کوئریِ جدیدی به market.db نمی‌زند و
# در board با یک اتصال محاسبه می‌شوند (خط قرمزِ round-tripِ واحد حفظ شد).
def smart_money(conn) -> dict:
    """جریان پول هوشمند FTS — مقایسهٔ ورود/خروج پول خردِ دو دارایی رقیب.

    - ``macro``: شاخص نقدینگی کلان (ارزش معاملات خردِ سهام+حق‌تقدم+ص.سهامی در همت)
      با برچسب داینامیک: ≥ ۲۰ همت «مساعد» / ≤ ۱۰ همت «نامساعد» / میان آن دو «متوسط».
    - ``watch_entry``: شرط هشدار ۸۰٪ — اگر بیش از ۸۰٪ نمادهای معامله‌شده منفی یا
      در صف فروش بودند، «فرصت پایش برای ورود (FTS)» فعال می‌شود.
    - ``flow``: جریان پولِ حقیقیِ دو گروه؛ هم‌زمانیِ «ورود به سهام + خروج از
      درآمد ثابت» ⇒ «جریان نقدینگی: حالت ایده‌آل FTS» (سبز).
    """
    rows, meta = enrich(conn)
    buckets = category_rows(rows)
    eq = _agg(buckets["eq_all"])
    sr = _agg(buckets["stock_right"])
    fx = _agg(buckets["fixed_fund"])
    allm = _agg(buckets["all"])

    # --- شاخص نقدینگی کلان (همان داورِ macro_health_from؛ فقط برچسب‌ها با آن یکی است)
    macro = macro_health_from(eq, allm)

    # --- شرط هشدار ۸۰٪: منفی یا صف فروش در میانِ نمادهای معامله‌شدهٔ سهام/حق‌تقدم
    sel = [r for r in buckets["stock_right"] if r["_m"]["vol"] > 0]
    known = sum(1 for r in sel if r.get("pct") is not None)
    bearish = 0
    for r in sel:
        p = r.get("pct")
        if (p is not None and p < 0) or r["_m"]["qstate"] == ST_SELLQ:
            bearish += 1
    bear_pct = 100.0 * bearish / known if known else None
    watch_entry = bool(bear_pct is not None and bear_pct >= ENTRY_OPPORTUNITY_NEG_PCT)

    # --- جریان پول هوشمند: ورود به سهام ⇄ خروج از درآمد ثابت
    eq_flow = round(eq["flow_bt"], 1)                  # میلیارد تومان
    fx_flow = round(fx["flow_bt"], 1)
    ideal = bool(eq_flow > 0 and fx_flow < 0)          # پول از سودِ امن به ریسک می‌رود

    return {"status": "ok", "asof": meta,
            "macro": {"value_hemat": macro["value_hemat"],
                      "state": macro["state"], "label": macro["label"],
                      "basis": macro["basis"],
                      "value_hemat_all_market": macro["value_hemat_all_market"],
                      "good_min": HEMAT_GOOD, "bad_max": HEMAT_BAD},
            "watch_entry": {"active": watch_entry, "bearish_pct": None if bear_pct is None else round(bear_pct, 1),
                            "rule_pct": ENTRY_OPPORTUNITY_NEG_PCT,
                            "bearish": bearish, "known": known},
            "flow": {"eq_flow_b_toman": eq_flow, "fixed_flow_b_toman": fx_flow,
                     "eq_inflow": eq_flow > 0, "fixed_outflow": fx_flow < 0,
                     "ideal_fts": ideal,
                     "eq_value_b_toman": round(eq["val_bt"], 1),
                     "fixed_value_b_toman": round(fx["val_bt"], 1),
                     "sr_flow_b_toman": round(sr["flow_bt"], 1)}}


# ============================================================ گام ۲ و ۳: هیستوگرام
def _hit(v, lo, hi) -> bool:
    """بازه‌ها نیم‌باز/نیم‌بسته‌اند: (lo, hi] — یک مقدارِ مرزی فقط در یکی از دو
    سطلِ همسایه می‌نشیند، وگرنه جمعِ میله‌ها از تعداد نمادها بیشتر می‌شود."""
    if lo == -1e9:
        return v <= hi
    if hi == 1e9:
        return v > lo
    return lo < v <= hi


def _tally(pcts, spec) -> list:
    """سطل‌ها همیشه کامل‌اند (۱۲ یا ۶ میله) — نبودِ داده یعنی میلهٔ صفر، نه
    ناپدیدشدنِ ستون؛ آن‌وقت عرض میله‌ها جابه‌جا می‌شود و مقایسهٔ دو نشست بی‌معنا می‌شود."""
    counts = [0] * len(spec)
    for v in pcts:
        if v is None:
            continue
        for i, (_k, _l, lo, hi, _c) in enumerate(spec):
            if _hit(v, lo, hi):
                counts[i] += 1
                break
    return [{"key": spec[i][0], "label": spec[i][1], "color": spec[i][4],
             "count": counts[i]} for i in range(len(spec))]


def histogram(conn, group: str = "all") -> dict:
    """گام ۲.۱ و ۳.۳ — توزیع بازدهی ۱۲بازه و محدودهٔ قیمتی ۷بازه.

    مبنای بازدهی، تغییرِ قیمتِ پایانی نسبت به دیروز است (همان «مثبت/منفی»
    رسمیِ نماد)، نه آخرین معامله؛ ستونِ «اختلاف آخرین/پایانی» جدا در جدول
    نمادها می‌آید تا الگوی ساعت آنجا شکار شود.

    فقط نمادهای «معامله‌شده» شمرده می‌شوند. نمودارِ تریدرزآرنا «توزیع بازدهی
    آخرین معاملات» است و نمادی که هیچ معامله‌ای نشده، بازدهیِ آخرین معامله
    ندارد؛ اگر شمرده می‌شدند ۱٬۲۷۶ صفرِ بی‌معنی به میانهٔ نمودار می‌ریخت و
    دُمِ قرمزِ بازار در روزهای ساکت نصف به‌نظر می‌رسید.
    """
    rows, meta = enrich(conn)
    sel = [r for r in rows if in_category(r, group, None) and r["_m"]["vol"] > 0]
    pcts = [r["pct"] for r in sel]
    known = sum(1 for p in pcts if p is not None)
    return {"status": "ok", "asof": meta, "group": group,
            "basis": "closing_vs_yesterday", "traded_only": True,
            "histo12": _tally(pcts, HISTO12), "histo7": _tally(pcts, HISTO7),
            "known": known, "nodata": len(pcts) - known,
            "total": len(sel), "not_traded": sum(1 for r in rows
                                                 if in_category(r, group, None)
                                                 and r["_m"]["vol"] <= 0)}


# ==================================================== گام ۲.۲: دماسنج مثبت/منفی
def thermometer(conn, group: str = "all") -> dict:
    """نوار دو‌رنگِ مثبت/منفی + قانون «فرصت ورود» (منفی‌ها ≥ ۸۰٪).

    مانند هیستوگرام، فقط نمادهای معامله‌شده — قانون ۸۰٪ روی فهرستِ
    معامله‌نشده‌ها همیشه «فرصت ورود» جعلی می‌سازد.
    """
    rows, meta = enrich(conn)
    sel = [r for r in rows if in_category(r, group, None) and r["_m"]["vol"] > 0]
    pos = sum(1 for r in sel if (r["pct"] or 0) > 0)
    neg = sum(1 for r in sel if (r["pct"] or 0) < 0)
    flat = sum(1 for r in sel if r["pct"] == 0)
    known = pos + neg + flat
    pos_pct = 100.0 * pos / known if known else None
    neg_pct = 100.0 * neg / known if known else None
    return {"status": "ok", "asof": meta, "group": group,
            "positive": pos, "negative": neg, "zero": flat, "nodata": len(sel) - known,
            "not_traded": sum(1 for r in rows if in_category(r, group, None)
                              and r["_m"]["vol"] <= 0),
            "positive_pct": None if pos_pct is None else round(pos_pct, 1),
            "negative_pct": None if neg_pct is None else round(neg_pct, 1),
            "entry_opportunity": bool(neg_pct is not None
                                       and neg_pct >= ENTRY_OPPORTUNITY_NEG_PCT),
            "entry_rule_pct": ENTRY_OPPORTUNITY_NEG_PCT}


# ================================================ گام ۲.۳ و ۳.۱: عمق و تفکیک صف‌ها
def depth(conn, group: str = "all") -> dict:
    """ارزش ۵ خطِ اول + تفکیک سه‌گانهٔ صف (عادی / کمتر از حجم مبنا / بدون معامله).

    اگر همگام‌سازیِ این بانک هنوز blDs را ذخیره نکرده باشد `depth_available=False`
    می‌شود و UI به‌جای صفر، «دادهٔ عمق موجود نیست» را نشان می‌دهد.
    """
    rows, meta = enrich(conn)
    sel = [r for r in rows if in_category(r, group, None)]
    have = [r for r in sel if r["_m"]["bq_val"] is not None]
    buy_val = sum(r["_m"]["bq_val"] or 0.0 for r in have)
    sell_val = sum(r["_m"]["sq_val"] or 0.0 for r in have)

    def one_q_split(side):
        """یک‌طرفه‌بودنِ دفتر شرطِ صف است؛ «کمتر از مبنا» فقط وقتی سنجیده
        می‌شود که مبنای نماد معلوم باشد، وگرنه برچسبِ base_unknown می‌خورد
        (بی‌داده، نه عادیِ قاطعی)."""
        no_trade = below = normal = unknown = 0
        for r in have:
            m = r["_m"]
            qv = m["bq_val"] if side == "buy" else m["sq_val"]
            opp = m["sq_val"] if side == "buy" else m["bq_val"]
            if not qv or opp:
                continue
            if m["vol"] <= 0:
                no_trade += 1
                continue
            qvol = m["bq_vol"] if side == "buy" else m["sq_vol"]
            base = m["base"]
            if base is None or qvol is None:
                unknown += 1
            elif qvol < base:
                below += 1
            else:
                normal += 1
        return {"normal": normal, "below_base": below, "no_trade": no_trade,
                "base_unknown": unknown}

    return {"status": "ok", "asof": meta, "group": group,
            "depth_available": bool(have), "symbols_with_depth": len(have),
            "buy_queue_b_toman": round(buy_val / B_TUMAN_FROM_RIAL, 1),
            "sell_queue_b_toman": round(sell_val / B_TUMAN_FROM_RIAL, 1),
            "ratio": None if not sell_val else round(buy_val / sell_val, 2),
            "buy_queue_count": sum(1 for r in have if r["_m"]["qstate"] == ST_BUYQ),
            "sell_queue_count": sum(1 for r in have if r["_m"]["qstate"] == ST_SELLQ),
            "buy": one_q_split("buy"), "sell": one_q_split("sell")}


# ================================== گام ۲.۴ و ۵.۱: تفکیک حقیقی/حقوقی (تب‌های جدول)
_TAB_CAT = {
    "all": "all", "eq_funds": "eq_all", "stock": "stock_right", "eq_fund": "eq_fund",
    "fixed": "fixed_fund", "top50": "top50", "lev": "lev_fund", "gold": "gold_fund",
    "silver": "silver_fund",
}


def _select(conn_rows, cat):
    if cat == "top50":
        return [r for r in conn_rows if r["_top50"]]
    return [r for r in conn_rows if in_category(r, cat, None)]


def client_split(conn, tab: str = "all") -> dict:
    """تعداد/ارزش/درصدِ خرید و فروشِ حقیقی در برابر حقوقی، به تفکیک تب."""
    rows, meta = enrich(conn)
    a = _agg(_select(rows, _TAB_CAT.get(tab, "all")))
    tot_buy, tot_sell = a["rb"] + a["ib"], a["rs"] + a["is"]

    def pct(part, whole):
        return None if not whole else round(100.0 * part / whole, 1)

    bt = lambda v: round(v / B_TUMAN_FROM_RIAL, 1)
    return {"status": "ok", "asof": meta, "tab": tab, "symbols": a["n"],
            "retail": {"buy_count": a["nbi"], "buy_b_toman": bt(a["rb"]),
                       "buy_pct": pct(a["rb"], tot_buy),
                       "sell_count": a["nsi"], "sell_b_toman": bt(a["rs"]),
                       "sell_pct": pct(a["rs"], tot_sell)},
            "institutional": {"buy_count": a["nbn"], "buy_b_toman": bt(a["ib"]),
                              "buy_pct": pct(a["ib"], tot_buy),
                              "sell_count": a["nsn"], "sell_b_toman": bt(a["is"]),
                              "sell_pct": pct(a["is"], tot_sell)},
            "pc_buy_m_toman": None if a["pc_buy_mt"] is None else round(a["pc_buy_mt"], 1),
            "pc_sell_m_toman": None if a["pc_sell_mt"] is None else round(a["pc_sell_mt"], 1),
            "power": None if a["power"] is None else round(a["power"], 2),
            "money_flow_b_toman": round(a["flow_bt"], 1)}


# ==================================================== گام ۵.۲: تابلوی نمادها
# کلیدِ مرتب‌سازی → نامِ ستون در سطرِ خروجی. این جدول باید با همان
# dictionary‌ای که ساخته می‌شود یکی باشد؛ پیش‌تر «val» به «val» نگاشت شده بود
# درحالی‌که ستون «val_b_toman» نام داشت، پس هیچ مقدار پیدا نمی‌شد و همهٔ
# سطرها برابرِ None (یکسان) می‌شدند — یعنی سرتیبِ نزولی، صفرها اول.
_GRID_SORT_KEYS = {"vol": "vol_b_shares", "val": "val_b_toman", "pc": "p_closing",
                   "pl": "p_last", "pct": "pct_close", "pct_last": "pct_last",
                   "clock": "clock_pct", "pcb": "pc_buy", "pcs": "pc_sell",
                   "pow": "power", "flow": "flow_b_toman", "dv": "dem_vol",
                   "dp": "dem_px", "symbol": "symbol"}


def mainwatch(conn, group: str = "eq_all", industry: str = "", sort: str = "clock",
              desc: bool = True, limit: int = 120) -> dict:
    """جدول نمادها با ستونِ «اختلاف آخرین و پایانی» به‌عنوان مرتبهٔ پیش‌فرض.

    پیش‌فرضِ مرتب‌سازی نزولی روی همین ستون است، چون دستورکارِ فاز ۱ «شکار
    سریع الگوی ساعت» است. دو ترمز هم لازم دارد: تعدادِ معامله و کفِ قیمت —
    بی‌آنها صدرِ جدول به اختیارمعامله‌هایی می‌رسد که با یک تیکِ یک‌ریالی
    ۱۰۰٪ نشان می‌دهند و هیچ کاربردی برای ورودِ نقدی ندارند.
    """
    rows, meta = enrich(conn)
    sel = []
    for r in _select(rows, _TAB_CAT.get(group, "all") if group in _TAB_CAT else group):
        if industry and (r.get("sector_name") or "").strip() != industry:
            continue
        m = r["_m"]
        py, pcl, plst = r.get("p_yesterday"), r.get("p_closing"), r.get("p_last")
        # «آخرین» بیرونِ باندِ مجاز یعنی فیلدِ آلوده (تاریخ در pc) — نه فرصت،
        # پس None می‌شود تا در ستونِ الگوی ساعت جلوی نمادهای سالم را نگیرد.
        ok_last = plst is not None and px_in_band(r, plst, pcl)
        sel.append({
            "symbol": r["symbol"], "ins_code": r["ins_code"],
            "name": r["name"], "industry": (r.get("sector_name") or "").strip(),
            "cls": r["cls"], "kind": r["kind"],
            # ۶ رقمِ اعشار یعنی حداقلِ ۱۰۰۰ سهم قابل‌نمایش. با ۴ رقم، سهامِ
            # گران‌قیمت با حجمِ کم (مثل سپامهر: ۹۹۵۹ سهم در ۶۵ معامله و ۴۸۴ میلیون
            # ریال ارزش) به‌اشتباه ۰٫۰۰۰۰ نشان داده می‌شدند و سرتیبِ حجم هم
            # می‌شکست — همه در ۰ قفل می‌شدند. این فیلد فقط نمایش/مرتب‌سازی است؛
            # اعتبارسنجیِ «معامله‌شده بودن» باید از روی «trades» انجام شود.
            "vol_b_shares": round(m["vol"] / B_SHARES, 6),
            # تعدادِ معاملهٔ خام: سیگنالِ قابل‌اتکای «این نماد معامله شده»،
            # فارغ از یکای نمایش. هر دو فیلد زیر JSON/جدول اضافه می‌شوند و
            # ستون‌های ثابتِ mstat.js تحت‌تاثیر قرار نمی‌گیرند.
            "trades": m["trades"],
            "val_b_toman": round(m["val"] / B_TUMAN_FROM_RIAL, 1),
            "p_last": _f(plst) if ok_last else None, "p_closing": _f(pcl),
            "pct_last": (100.0 * _div(_f(plst) - _f(py), py)
                         if py and ok_last and px_near(py, pcl) else None),
            "pct_close": r.get("pct"),
            "clock_pct": r.get("clock_pct"),
            "pc_buy": None if m["pc_buy"] is None else m["pc_buy"] / M_TUMAN_FROM_RIAL,
            "pc_sell": None if m["pc_sell"] is None else m["pc_sell"] / M_TUMAN_FROM_RIAL,
            "power": m["power"],
            "flow_b_toman": m["flow"] / B_TUMAN_FROM_RIAL,
            "dem_vol": m["bq1_vol"], "dem_px": m["bq1_px"],
            "queue": m["qstate"], "depth": m["bq_val"] is not None,
            # داستانیِ الگوی ساعت: نه هر اختلافی، بلکه اختلافِ قابل‌اتکا
            "clock_ok": bool(r["clock_pct"] is not None and r["clock_pct"] >= CLOCK_PCT
                             and m["trades"] >= CLOCK_MIN_TRADES
                             and _f(pcl) >= CLOCK_MIN_PRICE),
        })
    for s in sel:
        for k in ("pct_last", "pct_close", "clock_pct", "pc_buy", "pc_sell", "power"):
            if s[k] is not None:
                s[k] = round(s[k], 2)

    def _key(x):
        if sort == "clock":
            # فقط نامزدهای قابل‌اتکا رتبه می‌گیرند؛ بقیه به انتهای فهرست می‌روند
            col, v = "clock_pct", x["clock_pct"] if x["clock_ok"] else None
        elif sort == "symbol":
            return x.get("symbol") or ""
        else:
            col = _GRID_SORT_KEYS.get(sort, "clock_pct")
            v = x.get(col)
        if v is None:
            v = -1e18 if desc else 1e18
        return v

    sel.sort(key=_key, reverse=desc)
    limit = max(1, min(int(limit or 120), 4000))
    return {"status": "ok", "asof": meta, "group": group, "industry": industry,
            "sort": sort, "sort_col": _GRID_SORT_KEYS.get(sort, "clock_pct"),
            "desc": bool(desc), "total": len(sel),
            "clock_hits": sum(1 for x in sel if x["clock_ok"]),
            "clock_rule": {"min_pct": CLOCK_PCT, "min_trades": CLOCK_MIN_TRADES,
                           "min_price": CLOCK_MIN_PRICE},
            "rows": sel[:limit]}


# ==================================================== گام ۵.۳: خلاصهٔ صنایع
def industries(conn) -> dict:
    """هر صنعت + شمار مثبت/منفی + ارزش، تا کلیک روی صنعت جدول پایین را فیلتر کند.

    v9.8.0: سورتِ دو‌معیارهٔ نقشهٔ FTS — صنایع بر اساس بیشترین ارزش معاملات و
    بالاترین ورود پول خرد رتبه‌بندی می‌شوند و صنعتِ لیدرِ روز (مجموعهٔ رتبه‌ها
    بهترین) با ``leader=true`` در صدر می‌نشیند. همهٔ اعداد از همان enrich
    موجود می‌آیند — هیچ کوئریِ جدیدی زده نمی‌شود (گاردِ anti-N+1 دست‌نخورده).
    """
    rows, meta = enrich(conn)
    by = {}
    for r in rows:
        if r["cls"] not in (PAPER_STOCK, PAPER_RIGHT):
            continue
        nm = (r.get("sector_name") or "").strip()
        if not nm:
            continue
        b = by.setdefault(nm, {"industry": nm, "n": 0, "pos": 0, "neg": 0,
                               "val": 0.0, "flow": 0.0, "bq": 0.0, "sq": 0.0})
        b["n"] += 1
        p = r.get("pct")
        if p is not None and p > 0:
            b["pos"] += 1
        elif p is not None and p < 0:
            b["neg"] += 1
        b["val"] += r["_m"]["val"]
        b["flow"] += r["_m"]["flow"]
        b["bq"] += r["_m"]["bq_val"] or 0.0
        b["sq"] += r["_m"]["sq_val"] or 0.0
    out = []
    for b in by.values():
        flow_bt = round(b["flow"] / B_TUMAN_FROM_RIAL, 1)
        val_bt = round(b["val"] / B_TUMAN_FROM_RIAL, 1)
        out.append({"industry": b["industry"], "symbols": b["n"],
                    "positive": b["pos"], "negative": b["neg"],
                    "avg_pct": round(100.0 * b["pos"] / b["n"], 1) if b["n"] else None,
                    "value_b_toman": val_bt,
                    "flow_b_toman": flow_bt,
                    "flow_pct_of_value": round(100.0 * b["flow"] / b["val"], 2) if b["val"] else None,
                    "buy_queue_b_toman": round(b["bq"] / B_TUMAN_FROM_RIAL, 1),
                    "sell_queue_b_toman": round(b["sq"] / B_TUMAN_FROM_RIAL, 1)})
    # ---- رتبه‌بندی FTS: ارزش معاملات (وزن اصلی) + ورود پول خرد (تاییدیه) ----
    # rank_val: ۱ = بیشترین ارزش؛ rank_flow: ۱ = بیشترین ورود پول (فقط وردهای
    # مثبت رتبه می‌گیرند — صنعتِ با خروج پول هرگز لیدر نمی‌شود).
    by_val = sorted(out, key=lambda x: -x["value_b_toman"])
    by_flow = [x for x in out if x["flow_b_toman"] > 0]
    by_flow.sort(key=lambda x: -x["flow_b_toman"])
    rank_val = {x["industry"]: i + 1 for i, x in enumerate(by_val)}
    rank_flow = {x["industry"]: i + 1 for i, x in enumerate(by_flow)}
    for x in out:
        rv = rank_val.get(x["industry"], 0)
        rf = rank_flow.get(x["industry"])          # None ⇐ خروج پول: رتبه ندارد
        x["rank_value"] = rv
        x["rank_flow"] = rf
        # امتیاز لیدری: مجموع رتبه‌ها (کمتر = بهتر)؛ خروج پول جریمه می‌گیرد
        x["leader_score"] = (rv or len(out)) + (rf if rf else len(out) + 1)
    # لیدرِ روز = بهترین مجموع رتبه، به‌شرطِ اینکه در هر دو معیار جزو ۵ تای اول باشد
    leader_industry = None
    if out:
        cand = sorted(out, key=lambda x: x["leader_score"])
        top = cand[0]
        if top["rank_value"] <= 5 and (top["rank_flow"] is not None and top["rank_flow"] <= 5):
            leader_industry = top["industry"]
    for x in out:
        x["leader"] = bool(x["industry"] == leader_industry)
    out.sort(key=lambda x: (-x["value_b_toman"], -(x["flow_b_toman"] or 0.0)))
    return {"status": "ok", "asof": meta, "rows": out,
            "leader": leader_industry}


# ============================================ گام ۴: نقطه‌های درون‌روزی (mstat_snap)
# market_watch هر نشست را روی همان سطر می‌نویسد، پس «سریِ زمانی» در آن نیست.
# این تابع در پایانِ هر همگام‌سازی یک نقطهٔ تجمیعی ثبت می‌کند؛ با هر بار
# polling یک نقطه اضافه می‌شود و تایم‌لاین از همان روزِ نخست پر می‌شود.
def _enc_states(states: dict) -> str:
    """نگاشت ins_code→حرفِ وضعیت را فشرده می‌کند. یک نقطهٔ تایم‌لاین باید
    کوچک بماند (۳۵۰۰ نماد × ۲۰ بایت JSON خام = ۷۰KB در هر polling)."""
    return base64.b64encode(zlib.compress(
        json.dumps(states, separators=(",", ":")).encode("utf-8"), 6)).decode("ascii")


def _dec_states(blob):
    if not blob:
        return {}
    try:
        return json.loads(zlib.decompress(base64.b64decode(blob)).decode("utf-8"))
    except Exception:
        return {}


def snapshot_agg(conn) -> dict:
    """مقدارهای scalarِ همین لحظه + وضعیتِ تک‌حرفیِ همهٔ نمادها (فشرده)."""
    rows, meta = enrich(conn)
    eq = _agg([r for r in rows if in_category(r, "eq_all", None)])
    fx = _agg([r for r in rows if in_category(r, "fixed_fund", None)])
    allr = _agg(rows)
    have = [r for r in rows if r["_m"]["bq_val"] is not None]
    pos = neg = zero = 0
    st = {}
    for r in rows:
        p = r.get("pct")
        if p is not None and p > 0:
            pos += 1
        elif p is not None and p < 0:
            neg += 1
        elif p == 0:
            zero += 1
        q = r["_m"]["qstate"]
        if q != ST_NONE:
            st[r["ins_code"]] = q
    blob = _enc_states(st)
    return {
        "d_even": meta["d_even"], "h_even": meta["h_even"],
        "val_bt": round(allr["val_bt"], 1),
        "flow_eq_bt": round(eq["flow_bt"], 1), "flow_fixed_bt": round(fx["flow_bt"], 1),
        "pc_buy": None if eq["pc_buy_mt"] is None else round(eq["pc_buy_mt"], 1),
        "pc_sell": None if eq["pc_sell_mt"] is None else round(eq["pc_sell_mt"], 1),
        "pos": pos, "neg": neg, "zero": zero,
        "bq_bt": round(sum(r["_m"]["bq_val"] or 0.0 for r in have) / B_TUMAN_FROM_RIAL, 1),
        "sq_bt": round(sum(r["_m"]["sq_val"] or 0.0 for r in have) / B_TUMAN_FROM_RIAL, 1),
        "bq_n": sum(1 for r in have if r["_m"]["qstate"] == ST_BUYQ),
        "sq_n": sum(1 for r in have if r["_m"]["qstate"] == ST_SELLQ),
        "st": blob,
    }


def save_mstat_snapshot(conn, agg: dict = None, when=None) -> dict:
    """یک نقطه در mstat_snap — idempotent روی (d_even, h_even) تا pollingِ همان
    دقیقه نقطهٔ تکراریِ کاذب نسازد (دو نقطهٔ همسان = شیبِ دروغین روی چارت).

    v9.8.1 — گارد پنجرهٔ بازار: نقطه‌ای که ساعتش بیرونِ ۰۹:۰۰–۱۳:۰۰ است
    (همگام‌سازی شبانه، ردیف تستی، ...) اصلاً نوشته نمیشود؛ دادهٔ عمق/صفِ
    شبانه «افت به صفر» تلقی میشد و خطِ نزولیِ غیرواقعی روی تایم‌لاین میکشید.
    `when` فقط برای تست تزریق میشود (الگوی m141_hit)؛ پیش‌فرض = الان.
    """
    agg = agg or snapshot_agg(conn)
    now = when or datetime.datetime.now()
    if not in_trading_session(agg.get("h_even"), now):
        return {"saved": False, "reason": "outside_trading_session",
                "d_even": agg["d_even"], "h_even": agg["h_even"]}
    conn.execute(
        "INSERT OR REPLACE INTO mstat_snap (d_even, h_even, ts, agg) VALUES (?,?,?,?)",
        (agg["d_even"], agg["h_even"], _now_str(),
         json.dumps(agg, separators=(",", ":"), ensure_ascii=False)))
    conn.commit()
    return {"saved": True, "d_even": agg["d_even"], "h_even": agg["h_even"]}


def _now_str() -> str:
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _points(conn, day=None, limit: int = 240) -> list:
    """نقطه‌های نشستِ روز (یا آخرینِ موجود) به ترتیبِ زمانی.

    v9.8.1 — فیلتر پنجرهٔ رسمی بازار (۰۹:۰۰–۱۳:۰۰): ردیف‌های خارج از ساعات
    بازار (تست‌های شبانه/دادهٔ تاریخیِ آلوده پیش از این نسخه) در خروجی نیستند؛
    سریِ «بازار بسته → صفر» یعنی افتِ دروغین و خطِ مورب روی چارت.
    """
    if day is None:
        day = conn.execute("SELECT MAX(d_even) FROM mstat_snap").fetchone()[0]
    if day is None:
        return []
    out = []
    for r in conn.execute(
            "SELECT h_even, agg FROM mstat_snap WHERE d_even=? "
            "AND h_even>=? AND h_even<=? ORDER BY h_even",
            (day, SESSION_OPEN_HM, SESSION_CLOSE_HM)).fetchall():
        try:
            j = json.loads(r[1])
        except Exception:
            continue
        j.setdefault("h_even", r[0])
        out.append(j)
    return out[-limit:]


def _hhmm(h) -> str:
    s = "%06d" % int(_f(h))
    return "%s:%s" % (s[0:2], s[2:4])


_SERIES = ("val_bt", "flow_eq_bt", "flow_fixed_bt", "pos", "neg",
           "bq_bt", "sq_bt", "pc_buy", "pc_sell", "bq_n", "sq_n")


def timeline(conn, mode: str = "cum") -> dict:
    """گام ۴ — سری‌های ۰۹:۰۰ تا ۱۳:۰۰. cum=تجمعیِ همان نشست، inst=تفاوتِ دو
    نقطهٔ پشت‌سرهم (مقدارِ «همان لحظه»); یک داده، دو خوانش.

    با کمتر از دو نقطه ready=False است و UI «در حال ساختِ تایم‌لاین» را
    می‌نویسد — نه یک خطِ صافِ دروغین از روی یک نقطه.
    """
    pts = _points(conn)
    cum = {k: [p.get(k) for p in pts] for k in _SERIES}
    cum["t"] = [_hhmm(p.get("h_even")) for p in pts]

    def instantaneous(key):
        out, prev = [], None
        for v in cum.get(key, []):
            if v is None:
                out.append(None)
                continue
            out.append(None if prev is None else round(v - prev, 2))
            prev = v
        if out and pts:
            out[0] = cum[key][0]      # نخستین نقطه خودش «مجموعِ تا آن لحظه» است
        return out

    if mode == "inst":
        ser = {k: instantaneous(k) for k in _SERIES}
        ser["t"] = cum["t"]
    else:
        ser = cum
    return {"status": "ok", "mode": "inst" if mode == "inst" else "cum",
            "ready": len(pts) >= 2, "points": len(pts),
            "day": pts[0].get("d_even") if pts else None, "series": ser,
            "session_open": _hhmm(SESSION_OPEN_HM), "session_close": _hhmm(SESSION_CLOSE_HM),
            "note": None if len(pts) >= 2 else
                    "برای تایم‌لاین دست‌کم به دو همگام‌سازی در یک نشست نیاز است"}


# ==================================== گام ۳.۲: چرخش وضعیت درون‌روزی (فازِ بازار)
_TRANS = [("b", "s", "صف خرید به صف فروش", "red"),
          ("p", "s", "مثبت به صف فروش", "red"),
          ("b", "n", "صف خرید به منفی", "red"),
          ("s", "b", "صف فروش به صف خرید", "green"),
          ("n", "b", "منفی به صف خرید", "green"),
          ("s", "p", "صف فروش به مثبت", "green")]


def phases(conn) -> dict:
    """شمارندهٔ تغییرِ وضعیتِ نمادها بین نقاطِ متوالیِ همان نشست.

    وضعیت‌ها از blobِ فشردهٔ هر نقطه درمی‌آیند؛ نمادی که در نقطهٔ پیشین
    نبود (مثلاً تازه باز شده) شمرده نمی‌شود — «از هیچ به صف خرید» چرخش نیست.
    """
    pts = _points(conn)
    counts = {(a, b): 0 for a, b, _l, _c in _TRANS}
    for i in range(1, len(pts)):
        prev = _dec_states(pts[i - 1].get("st"))
        cur = _dec_states(pts[i].get("st"))
        if not prev or not cur:
            continue
        for ic, now in cur.items():
            was = prev.get(ic)
            if was and was != now and (was, now) in counts:
                counts[(was, now)] += 1
    out = {"red": [], "green": []}
    for a, b, lbl, col in _TRANS:
        out[col].append({"key": "%s>%s" % (a, b), "label": lbl, "count": counts[(a, b)]})
    return dict({"status": "ok", "points": len(pts), "ready": len(pts) >= 2}, **out)

