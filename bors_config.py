"""bors_config.py -- paths and FTS threshold defaults shared by api/*.

Split verbatim out of app.py so the router modules no longer need the app
object just to reach a constant. Resolved relative to APP_DIR (repo root,
which is also where the packaged EXE expects market.db / *.json).
"""
import os
import sys


_SRC_DIR = os.path.dirname(os.path.abspath(__file__))


def _app_dir():
    """در حالت EXE: دیتاهای فقط‌خواندنی باندل در _MEIPASS (onedir: _internal)."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", None)
        if base and os.path.isdir(base):
            return base
    return _SRC_DIR


def _work_dir():
    """مسیر نوشتن فایل‌های وضعیت/تنظیمات: در EXE کنار باینری، وگرنه ریشه ریپو."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return _SRC_DIR


APP_DIR = _app_dir()
WORK_DIR = _work_dir()

DB_PATH = "../market.db" if os.path.exists("../market.db") else "market.db"
# فایل‌های چندنویسنده کنار EXE می‌مانند (در حالت frozen نه داخل _internal)
STATUS_PATH = os.path.join(WORK_DIR, "sync_status.json")
OD_STATUS_PATH = os.path.join(WORK_DIR, "sync_ondemand.json")
MARKET_STATUS_PATH = os.path.join(WORK_DIR, "market_sync.json")
CONTROL_PATH = os.path.join(WORK_DIR, "codal_control.json")
FTS_CONFIG_PATH = os.path.join(WORK_DIR, "fts_thresholds.json")
_ADB_CFG = os.path.join(WORK_DIR, "adb_config.json")

FTS_DEFAULTS = {
    # ۱) رشد فروش تجمیعی ÷ همان دورهٔ سال قبل
    "growth_min": 40.0,            # Min_Sales_Growth = ۴۰٪
    "inflation_min": 58.0,         # بنچ‌مارک تورم سالانه = ۵۸٪ (بالای آن = عالی)
    # ۲) روند EPS — صورت مالی ۱۲ماههٔ حسابرسی‌شدهٔ شرکت اصلی
    "eps_years": 3,                # EPS_Consecutive_Growth_Years = ۳
    # ۳) حاشیه سود ناخالص = سود ناخالص ÷ درآمدهای عملیاتی × ۱۰۰
    "margin_min": 20.0,            # Min_Gross_Margin = ۲۰٪
    "margin_optimal": 30.0,        # ایده‌آل = ۳۰٪
    # ۴) فروش سالانهٔ Annualized به ارزش بازار + پتانسیل سود ناخالص
    "sales_to_mcap_min": 1.0,      # Min_Annualized_Sales_To_MarketCap = ۱.۰
    "profit_potential_min": 30.0,  # Min_Profit_Potential_To_MarketCap = ۳۰٪
    # ۵) فیلتر صنعت — تفکیک قیمت‌گذاری آزاد/بورس کالا از دستوری
    "industry_mode": "Exclude_Mandatory_Pricing",
    "mandatory_sectors": ["خودرو", "دارو", "نیروگاه", "غذا", "لاستیک", "شوینده", "بیمه"],
    "free_sectors": ["سیمان", "پتروشیمی", "شیمیایی", "فلزات", "کانی", "کاشی", "سرامیک",
                     "کانه", "معادن", "نفت", "محصولات فلزی"],
    # غربالگری نهایی
    "watchlist_max": 50,           # سقف واچ‌لیست (جزوه: نهایتاً ۵۰ سهم)
    "mcap_min_hmt": 0.0,           # پیش‌شرط: حداقل ارزش بازار (همت)
    "suspended_max_stale_sessions": 3,   # نماد با ≥ این تعداد نشست عقب‌مانده = تعلیق
    # v9.7 — دو پارامتر کمکی بنیادی/تابلوخوانی
    # ماده ۱۴۱ قانون تجارت: زیان انباشته > نصف سرمایه → حذف از واچ‌لیست.
    # تشخیص از آخرین صورت مالی ۱۲ماهه: total_equity <= 0.5 * capital
    "filter_m141": False,
    # نقدشوندگی: حداقل میانگین ارزش معاملات روزانه (همت); ۰ = بدون فیلتر
    "min_trade_val": 0.0,
    # v10 — آستانه‌های «حکمِ جزوه» برای کارتِ بنیادی. این کلیدها عمداً از
    # کلیدهای اسکرینر (growth_min/margin_min/…) جدا‌اند: تغییرِ عددِ اسکرینر
    # نباید بی‌صدا چکِ ۱الفِ کارت (۶۰٪) یا کفِ نسبتِ فروش÷ارزش را شل کند.
    # پنلِ تنظیمات همین‌ها را می‌نویسد و v10_thresholds() می‌خواند.
    "v10_monetary_growth_min": 60.0,
    "v10_volume_growth_min": 0.0,
    "v10_volume_breadth_min": 0.60,
    "v10_eps_years": 3,
    "v10_margin_min": 20.0,
    "v10_margin_ideal": 30.0,
    "v10_sales_to_mcap_min": 0.33,     # جزوهٔ جدید: فروش سالانه ÷ ارزش بازار ≥ ۳۳٪
    "v10_potential_min": 33.0,
    # v10 — فیلترِ دستیِ صنایع از پنل (جدا از رژیم قیمت‌گذاری).
    # industry_mode = Include_Industries → فقط فهرستِ include می‌ماند
    # industry_mode = Exclude_Industries  → فهرستِ exclude حذف میشود
    # فهرست‌ها با «,» یا «،» نوشته میشوند و با norm_fa نرمال‌سازی می‌شوند.
    "include_industries": [],
    "exclude_industries": [],
}

FTS_LEGACY_SCALARS = {
    "streak_periods": "eps_years",
    "ps_good": "sales_to_mcap_min",       # P/S ≤ 1  ⇔  Sales/Mcap ≥ 1.0
    "potential_min": "profit_potential_min",
}
FTS_LEGACY_LISTS = {"bad_sectors": "mandatory_sectors", "good_sectors": "free_sectors"}
FTS_LIST_KEYS = ("mandatory_sectors", "free_sectors", "include_industries",
                 "exclude_industries")
FTS_STR_KEYS = ("industry_mode",)

_CAL_CACHE_PATH = os.path.join(APP_DIR, "static", "calendar", "cache.json")
_cal_cache = {"mtime": 0.0, "events": []}

MA_WINDOWS = [5, 20, 50, 120]
