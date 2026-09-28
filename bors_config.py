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

def _db_has_codal(path):
    """True اگر این market.db دادهٔ کدال دارد (financial_statements/monthly_sales).

    v1.0.16: همگام‌سازیِ زندهٔ تابلو یک market.db کوچک می‌سازد که فقط
    instruments/market_watch دارد و صورت‌های مالی درش نیستند. بدون این
    بررسی، آن فایلِ تهی از کدال بر فایلِ ۹۵ مگابایتیِ باندل‌شده ترجیح
    داده می‌شود و کلِ تب بنیادی «بدون داده» می‌ماند.
    """
    try:
        import sqlite3 as _sq
        con = _sq.connect(f"file:{path}?mode=ro", uri=True)
        try:
            n = con.execute("SELECT COUNT(*) FROM financial_statements").fetchone()[0]
            return int(n or 0) > 0
        finally:
            con.close()
    except Exception:
        return False


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
    # v1.0.16: در بیلدِ onedir، PyInstaller داده‌ها را در _internal می‌گذارد.
    # اگر آنجا market.db با دادهٔ کدال هست، باید بر فایلِ کوچکِ کنارِ EXE
    # (که همگام‌سازیِ زندهٔ تابلو می‌سازد) ارجح باشد.
    if getattr(sys, "frozen", False):
        internal = os.path.join(exe_dir, "_internal")
        if os.path.isdir(internal):
            dirs.append(internal)
    for d in dirs:
        p = os.path.join(d, "market.db")
        if os.path.exists(p) and _db_has_codal(p):
            return p
    # هیچ کدام دادهٔ کدال نداشتند: فایلِ موجود را برگردان (همگام‌سازیِ زنده
    # هنوز در حال نوشتنش است) تا ensure_market_db() بعداً استخراج کند.
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

# جدول‌هایی از market.db که نوشتهٔ خودِ کاربرند، نه دادهٔ بازار. هنگامِ
# جایگزینیِ baseline این‌ها از فایلِ قدیمی به فایلِ تازه منتقل می‌شوند؛ در غیر
# این صورت یک ارتقای ساده، واچ‌لیست و تصمیماتِ کاربر را پاک می‌کرد.
MARKET_DB_USER_TABLES = ("user_watchlists", "selection_decisions")

_REQUIRED_MARKET_TABLES = {"instruments", "daily_prices", "financial_statements"}


def _market_db_tables(path):
    """مجموعهٔ جدول‌های یک فایل DB (بدون نوشتن). خطا ⇒ مجموعهٔ خالی."""
    try:
        import sqlite3 as _sq
        probe = _sq.connect("file:%s?mode=ro" % path, uri=True)
        try:
            return {r[0] for r in probe.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            probe.close()
    except Exception:
        return set()


def _sha256_file(path, chunk=1 << 20):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _find_bundled_db_lzma():
    exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else _SRC_DIR
    for candidate in (os.path.join(exe_dir, "market.db.lzma"),
                      os.path.join(WORK_DIR, "market.db.lzma"),
                      "market.db.lzma", "../market.db.lzma"):
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def _baseline_stamp_path():
    return os.path.join(os.path.dirname(DB_PATH) or ".", "market.db.baseline")


def _read_baseline_stamp():
    try:
        with open(_baseline_stamp_path(), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def _write_baseline_stamp(value):
    try:
        with open(_baseline_stamp_path(), "w", encoding="utf-8") as f:
            f.write(value)
    except OSError:
        pass


def _carry_user_tables(old_db, new_db, verbose=False):
    """جدول‌های کاربر را از baselineِ قدیمی به تازه کپی می‌کند. بی‌صدا رد می‌شود
    اگر جدولی در هیچ‌کدام نبود — نبودنش شکافِ داده نیست، فقط بی‌اهمیت است."""
    import sqlite3 as _sq
    try:
        # عمدیِ read-only نیست: فایلِ .stale ممکن است WALِ خودش را داشته باشد و
        # بازکردنِ ro بدونِ ability to build -shm شکست می‌خورد و نقلِ دادهٔ کاربر
        # بی‌صدا رد می‌شد.
        src = _sq.connect(old_db)
    except Exception:
        return
    try:
        have = {r[0] for r in src.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        dst_have = _market_db_tables(new_db)
        dst = _sq.connect(new_db)
        try:
            for t in MARKET_DB_USER_TABLES:
                if t not in have or t not in dst_have:
                    continue
                cols = [r[1] for r in dst.execute('PRAGMA table_info("%s")' % t)]
                collist = ",".join('"%s"' % c for c in cols)
                rows = src.execute('SELECT %s FROM "%s"' % (collist, t)).fetchall()
                if not rows:
                    continue
                dst.execute('DELETE FROM "%s"' % t)
                dst.executemany(
                    'INSERT INTO "%s" (%s) VALUES (%s)'
                    % (t, collist, ",".join("?" * len(cols))), rows)
                if verbose:
                    print("  [OK]  carried %s: %d rows" % (t, len(rows)))
            dst.commit()
        finally:
            dst.close()
    except Exception as e:
        if verbose:
            print("  [WARN] could not carry user tables:", e)
    finally:
        src.close()


def ensure_market_db(verbose=False):
    """(idempotent) market.db را از market.db.lzma می‌سازد یا تازه می‌کند.

    دو شرطِ جدا گلوگاه بودند:
      ۱) ناقص‌بودن — یک مسیرِ فرعی (مثل --codal-worker) با connect خالی فایل
         می‌ساخت و اسکرینر تا ابد «داده نیست» می‌داد.
      ۲) کهنه‌بودن — استخراج فقط با «وجود نداشتن فایل» فعال می‌شد، پس baselineِ
         تازهٔ یک نسخهٔ جدید هرگز جای فایلِ استخراج‌شدهٔ قدیمی را نمی‌گرفت و
         «ارتقای انباشته» برای دادهٔ بازار عملاً دروغ بود.
    راهِ دوم: اثرِ انگشتی (sha256) از .lzma کنارِ فایل نگه می‌داریم؛ اگر عوض شد،
    baselineِ تازه استخراج و جدول‌هایِ کاربر از نسخهٔ قدیمی منتقل می‌شود. فایلِ
    قدیمی با پسوندِ .stale-<ts> نگه داشته می‌شود، نه حذف.
    """
    src_lzma = _find_bundled_db_lzma()
    want = None
    if src_lzma:
        try:
            want = _sha256_file(src_lzma)
        except OSError:
            want = None

    if os.path.exists(DB_PATH):
        tables = _market_db_tables(DB_PATH)
        complete = _REQUIRED_MARKET_TABLES <= tables
        current = bool(want) and _read_baseline_stamp() == want
        if complete and current:
            return DB_PATH
        reason = "incomplete" if not complete else "stale baseline"
        if verbose:
            print("  [..]  market.db is %s — re-extracting from market.db.lzma" % reason)
        stale_path = DB_PATH + ".stale"
        try:
            os.replace(DB_PATH, stale_path)
        except OSError:
            return DB_PATH
        # sidecar‌های WAL حتماً باید با فایلِ اصلی جابه‌جا شوند. اگر بمانند،
        # SQLite آن‌ها را به baselineِ تازه می‌چسباند و محتوای قدیمی دوباره
        # بازپخش می‌شود — یعنی جایگزینیِ تازه بی‌صدا به همان دادهٔ کهنه برمی‌گردد.
        for suffix in ("-wal", "-shm"):
            try:
                if os.path.exists(DB_PATH + suffix):
                    os.replace(DB_PATH + suffix, stale_path + suffix)
            except OSError:
                pass
        # baselineِ تازه را استخراج کن، بعد دادهٔ کاربر را از نسخهٔ قدیمی برگردان
        new_db = _extract_market_db(src_lzma, verbose=verbose)
        if new_db:
            _carry_user_tables(stale_path, new_db, verbose=verbose)
            _write_baseline_stamp(want or "")
        return new_db or DB_PATH

    new_db = _extract_market_db(src_lzma, verbose=verbose)
    if new_db:
        _write_baseline_stamp(want or "")
    return new_db or DB_PATH


def _extract_market_db(src_lzma, verbose=False):
    """market.db.lzma را به WORK_DIR/market.db باز می‌کند. None یعنی نشد."""
    if not src_lzma:
        return None
    try:
        import lzma
        os.makedirs(WORK_DIR, exist_ok=True)
        target_db = os.path.join(WORK_DIR, "market.db")
        tmp = target_db + ".part"
        if verbose:
            print("  [..]  extracting market.db.lzma (one-time, ~40s) ...")
        with open(src_lzma, "rb") as fi, open(tmp, "wb") as fo:
            fo.write(lzma.decompress(fi.read()))
        if not _REQUIRED_MARKET_TABLES <= _market_db_tables(tmp):
            if verbose:
                print("  [ERR] extracted market.db is missing required tables")
            os.remove(tmp)
            return None
        os.replace(tmp, target_db)
        if verbose:
            print("  [OK]  market.db extracted from .lzma")
        return target_db
    except Exception as e:
        if verbose:
            print("  [ERR] lzma extraction failed:", e)
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
    # ۲) روند EPS — صورت مالی ۱۲ماههٔ حسابرسی‌شدهٔ شرکت اصلی
    "eps_years": 3,                # EPS_Consecutive_Growth_Years = ۳
    # ۳) حاشیه سود ناخالص = سود ناخالص ÷ درآمدهای عملیاتی × ۱۰۰
    "margin_min": 20.0,            # Min_Gross_Margin = ۲۰٪
    "margin_optimal": 30.0,        # ایده‌آل = ۳۰٪
    # ۴) فروش سالانهٔ Annualized به ارزش بازار + پتانسیل سود ناخالص
    # حکمِ مالک جزوه (ص ۶): کفِ قبولی «حداقل ۱/۳ ارزش بازار» = ۰٫۳۳ است و
    # ۱٫۰ حالتِ ایده‌آل — نه آستانهٔ رد. پیش از این هر دو جا ۱٫۰ به‌عنوان
    # «پیش‌فرضِ جزوه» نوشته شده بود و نمادهای سالمِ ۰٫۳۳ تا  رد می‌شدند.
    "sales_to_mcap_min": 0.33,     # Min_Annualized_Sales_To_MarketCap = ⅓× (کف قبولی)
    "sales_to_mcap_ideal": 1.0,    # ایده‌آل = ۱× — نمایشی، نه گیتِ رد
    "profit_potential_min": 40.0,  # Min_Profit_Potential_To_MarketCap = ۴۰٪ (سند v2.1)
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
    # ۱ب — مبنای تورمی که از رشدِ اسمی کسر می‌شود تا «رشد تولیدی» بیرون بیاید.
    # حکمِ مالک 2026-09-26: این عدد کلیدِ خودش را دارد و از هدفِ ۶۰٪ِ بالا جداست؛
    # ۰ یعنی «بدون تعدیلِ تورم» و باید همان‌طور بماند.
    "v10_inflation_basis": 60.0,
    "v10_volume_growth_min": 0.0,
    "v10_volume_breadth_min": 0.60,
    "v10_eps_years": 3,
    "v10_margin_min": 20.0,
    "v10_margin_ideal": 30.0,
    "v10_sales_to_mcap_min": 0.33,      # ص ۶ جزوه: کف قبولی ⅓× ارزش بازار (ایده‌آل ۱× در سطر بعد)
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
    "ps_good": "sales_to_mcap_ideal",       # P/S ≤ 1  ⇔  Sales/Mcap ≥ 1.0
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
APP_VERSION = "1.0.44"
