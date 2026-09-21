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


def _writable(path):
    """آیا می‌توان در این مسیر فایل نوشت؟ (Program Files برای کاربر عادی: خیر)"""
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".wtprobe")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False


def _user_data_dir():
    """%LOCALAPPDATA%\\BorsTerminal_Ultimate — داده‌های قابل‌نوشتنِ هر کاربر."""
    return os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
        "BorsTerminal_Ultimate", "data")


def _work_dir():
    """مسیر نوشتن فایل‌های وضعیت/تنظیمات.

    در حالت EXE اولویت با پوشهٔ کنار باینری است (حالت پرتابیل: وقتی ZIP را
    در یک پوشهٔ نوشتنی باز می‌کنید همان‌جا کار می‌کند)، اما اگر آن پوشه
    نوشتنی نباشد (نصب در Program Files با PrivilegesRequired=admin) تمام
    داده‌های کاربر به %LOCALAPPDATA%\\BorsTerminal_Ultimate منتقل می‌شوند؛
    در غیر این صورت استخراج market.db.lzma و سینک بازار با «Permission
    denied» گیر می‌کنند. در حالت dev همان ریشهٔ ریپو است.
    """
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        if _writable(exe_dir):
            return exe_dir
        return _user_data_dir()
    return _SRC_DIR


APP_DIR = _app_dir()
WORK_DIR = _work_dir()

def _resolve_market_db():
    """مسیر market.db: فایل موجود، وگرنه مسیر برنامه‌ریزی‌شده برای استخراج.

    خودِ استخراج (حدود ۴۰ ثانیه) به ensure_market_db() موکول شده تا
    bors_entry در preflight پیشرفت را به کاربر نشان دهد؛ اینجا فقط مسیر
    نهایی را تعیین می‌کنیم. جستجو شامل کنار EXE (محل نصب)، WORK_DIR و
    مسیرهای نسبی (dev) می‌شود. کنارِ EXE فقط در صورتی انتخاب می‌شود که
    پوشهٔ نصب نوشتنی باشد؛ در غیر این صورت WAL نمی‌تواند -wal/-shm بسازد.
    """
    exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else _SRC_DIR
    # ۱) market.db از قبل موجود (پرتابیل کنار EXE / دادهٔ کاربر / dev).
    # exe_dir فقط وقتی در نظر گرفته می‌شود که نوشتنی باشد: در نصبِ
    # all-users پوشهٔ نصب فقط‌خواندنی است و sqlite برای WAL باید -wal/-shm
    # را کنارِ db بسازد که ممکن نیست → «unable to open database file» روی
    # هر اتصال. مثلِ _work_dir() از exe_dirِ غیرنوشتنی صرف‌نظر می‌کنیم.
    dirs = [exe_dir, WORK_DIR] if _writable(exe_dir) else [WORK_DIR]
    for d in dirs:
        p = os.path.join(d, "market.db")
        if os.path.exists(p):
            return p
    if not getattr(sys, "frozen", False):
        for p in ("market.db", "../market.db"):
            if os.path.exists(p):
                return p
    # ۲) مسیر برنامه‌ریزی‌شده برای استخراج (همیشه در WORK_DIR نوشتنی)
    return os.path.join(WORK_DIR, "market.db")


DB_PATH = _resolve_market_db()

def ensure_market_db(verbose=False):
    """(idempotent) اگر market.db نبود از market.db.lzma بازسازی می‌کند.

    bors_entry در preflight با verbose=True صدا می‌زند تا کاربر پیشرفت ~۴۰
    ثانیه‌ای استخراج را ببیند. بقیهٔ مسیرها از DB_PATH استفاده می‌کنند.
    """
    if os.path.exists(DB_PATH):
        # فایل هست ولی ممکن است «خالی/ناقص» باشد — یعنی یک مسیر (مثل
        # --codal-worker که preflight را دور می‌زند) با sqlite3.connect خالی
        # آن را ساخته باشد. در آن صورت market.db واقعی هرگز استخراج نمیشد و
        # برنامه بدون هیچ دادهٔ قیمتی بالا می‌آمد. بهبودها را حفظ کنیم.
        try:
            import sqlite3 as _sq
            _probe = _sq.connect(f"file:{DB_PATH}?mode=ro", uri=True)
            _have = {r[0] for r in _probe.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            _probe.close()
        except Exception:
            _have = set()
        # حداقل جداول موردنیاز برای داشتن دیتای بازار معتبر. financial_statements
        # حتماً لازم است: اسکرینر بدون آن ۵۰۰ می‌دهد. در market.db.lzmaیِ ناقصِ
        # v1.0.7/8 این جدول غایب بود ولی instruments+daily_prices موجود بودند،
        # پس این نگهبان دیتای ناقص را می‌پذیرفت — و چون فایلِ قدیمی روی دیسک
        # محفوظ می‌ماند، حتی ارتقا هم آن را اصلاح نمی‌کرد.
        if {"instruments", "daily_prices", "financial_statements"} <= _have:
            return DB_PATH
        # ناقص است: کنار بگذار و دوباره از market.db.lzma بازسازی کن.
        try:
            os.replace(DB_PATH, DB_PATH + ".incomplete")
        except OSError:
            pass
    exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else _SRC_DIR
    for candidate in [os.path.join(exe_dir, "market.db.lzma"),
                      os.path.join(WORK_DIR, "market.db.lzma"),
                      "market.db.lzma", "../market.db.lzma"]:
        if not os.path.exists(candidate):
            continue
        try:
            import lzma
            os.makedirs(WORK_DIR, exist_ok=True)
            target_db = os.path.join(WORK_DIR, "market.db")
            if verbose:
                print("  [..]  extracting market.db.lzma (one-time, ~40s) ...")
            with open(candidate, "rb") as fi, open(target_db, "wb") as fo:
                fo.write(lzma.decompress(fi.read()))
            if verbose:
                print("  [OK]  market.db extracted from .lzma")
            return target_db
        except Exception as e:
            if verbose:
                print("  [ERR] lzma extraction failed:", e)
            return None
    return None

# دیتابیس اختصاصی کاربر — هیچ‌وقت با آپدیت بازار جایگزین نمی‌شود.
# محل ذخیره: WORK_DIR (کنار EXE در حالت پرتابیل، وگرنه %LOCALAPPDATA%) یا
# ریشه ریپو (در حالت dev). این فایل در .gitignore است تا داده شخصی
# توسعه‌دهنده push نشود.
USER_DB_PATH = os.path.join(WORK_DIR, "user.db")

# فایل‌های چندنویسنده در WORK_DIR می‌مانند (نوشتنی؛ نه داخل _internal)
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
    "profit_potential_min": 40.0,  # Min_Profit_Potential_To_MarketCap = ۳۰٪
    # ۵) فیلتر صنعت — تفکیک قیمت‌گذاری آزاد/بورس کالا از دستوری
    "industry_mode": "Exclude_Mandatory_Pricing",
    "mandatory_sectors": ["خودرو", "نیروگاه", "قند و شکر", "لاستیک", "شوینده", "بیمه"],
    "free_sectors": ["سیمان", "پتروشیمی", "شیمیایی", "فلزات", "کانی", "کاشی", "سرامیک", "شیشه",
                     "کانه", "معادن", "نفت", "محصولات فلزی"],
    # غربالگری نهایی
    "watchlist_max": 50,           # سقف واچ‌لیست (جزوه: نهایتاً ۵۰ سهم)
    "mcap_min_hmt": 0.0,           # پیش‌شرط: حداقل ارزش بازار (همت)
    # سند v2.1 / فرم تنظیمات: کلیدهای دروازهٔ سخت و استثنائات
    "holdings_sales_na": True,          # عدم اعمال نسبت فروش بر هلدینگ/سرمایه‌گذاری (N/A)
    "pharma_margin_exempt_min": 50.0,   # آستانهٔ استثنای دارویی (٪ حاشیهٔ ناخالص)؛ ۰ = غیرفعال
    "exclude_base_market": True,
    "exclude_rejected_indicators": [],   # کدهای شاخصی که نماد مردود/ناقص‌شان از جدول حذف شود        # حذف نمادهای بازار پایهٔ فرابورس
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
    "v10_sales_to_mcap_min": 1.0,      # پیشفرضِ جزوه: فروش سالانه ÷ ارزش بازار ≥ ۱× (۱۰۰٪)
    "v10_potential_min": 40.0,
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
                 "exclude_industries", "exclude_rejected_indicators")
FTS_STR_KEYS = ("industry_mode",)

_CAL_CACHE_PATH = os.path.join(APP_DIR, "static", "calendar", "cache.json")
_cal_cache = {"mtime": 0.0, "events": []}

MA_WINDOWS = [5, 20, 50, 120]

# v1.0.10 — نسخهٔ برنامه؛ منبعِ واحد برای api/update.py (مقایسهٔ semver).
# هر بار که نسخه در installer/bors_setup.iss و tauri.conf.json بالا می‌رود،
# اینجا هم باید به‌روز شود (scripts/publish_github_release.py هم همین نسخه را
# در latest.json می‌نویسد).
APP_VERSION = "1.0.13"
