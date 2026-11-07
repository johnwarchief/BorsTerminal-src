# -*- coding: utf-8 -*-
"""tsetmc_p0_schema.py — تک‌منبعِ DDL برایِ جدول‌هایِ canonicalِ P0.

چرا فایلِ جدا: این جدول‌ها را `test_tsetmc.py` می‌نویسد و `api/*` و
`mstat_engine` می‌خوانند. اگر DDL دو جا تعریف شود، بانکِ تازه با بانکِ
ارتقایافته واگرا می‌شود — همان زخمی که `tape_history` خورد (یک DDL در
`test_tsetmc` و یکی در `mstat_engine.TAPE_HIST_DDL`) و گاردِ mstat به‌جایِ
«نویسنده vs جدول»، «کپیِ من vs کپیِ من» را چک می‌کرد.

این فایل هیچ وابستگیِ بیرونی ندارد (نه requests، نه pandas) تا بشود از
مسیرِ سبکِ `mstat_engine.ensure_schema` هم صداش زد.

قراردادِ مشترکِ همهٔ این جدول‌ها (docs/TSETMC-P0-IMPLEMENTATION.md):
  • مبدأ نباشد ⇒ ردیفی نمی‌نشیند. نبودِ ردیف خودش داوری است («بازسازی به‌کار
    رفت»)، پس هیچ‌وقت صفرِ جعلی جای آن نمی‌نشیند.
  • هر ردیف `source` دارد.
"""

CLIENT_TYPE_VALUE = """
CREATE TABLE IF NOT EXISTS client_type_value (
    ins_code TEXT, d_even INTEGER,
    buy_i_val REAL, buy_n_val REAL, sell_i_val REAL, sell_n_val REAL,
    buy_ddd_val REAL,
    -- kind = «چهار ارزش همه بودند» (native) یا «بعضی نبودند» (mixed). یک‌بار
    -- درِ نویسنده حساب می‌شود و همین‌جا می‌نشیند؛ اگر درِ SQL یا UI دوباره
    -- محاسبه شود، دو منبعِ حقیقت برایِ provenance داریم.
    kind TEXT,
    fetched_at TEXT, source TEXT,
    PRIMARY KEY (ins_code, d_even))
"""

CLIENT_TYPE_VALUE_STATE = """
CREATE TABLE IF NOT EXISTS client_type_value_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_attempt TEXT, last_ok TEXT, newest_d_even INTEGER, note TEXT)
"""

PRICE_ADJUST_EVENTS = """
CREATE TABLE IF NOT EXISTS price_adjust_events (
    ins_code TEXT, d_even INTEGER, symbol TEXT,
    p_closing REAL, p_closing_not_adjusted REAL,
    corporate_type_code INTEGER, ratio REAL,
    source TEXT, fetched_at TEXT,
    PRIMARY KEY (ins_code, d_even))
"""

SHARE_CHANGE_EVENTS = """
CREATE TABLE IF NOT EXISTS share_change_events (
    ins_code TEXT, d_even INTEGER, symbol TEXT,
    shares_old REAL, shares_new REAL, ratio REAL,
    source TEXT, fetched_at TEXT,
    PRIMARY KEY (ins_code, d_even))
"""

# توزیع‌هایِ نقدیِ صندوق‌ها که TSETMC در price_adjust_events منتشر نمی‌کند.
# مقدار از پورتالِ رسمیِ مدیرِ صندوق می‌آید؛ `ratio` فقط برایِ بازبینیِ سریع است و
# موتور آن را از reference_price/unit_profit بازمی‌سازد. کلید = (ins_code, d_even).
FUND_PROFIT_EVENTS = """
CREATE TABLE IF NOT EXISTS fund_profit_events (
    ins_code TEXT, d_even INTEGER, symbol TEXT,
    profit_date TEXT, unit_profit REAL, reference_price REAL, ratio REAL,
    source TEXT, source_id TEXT, fetched_at TEXT,
    PRIMARY KEY (ins_code, d_even))
"""

# DPSِ **اعلامیِ مجمع** برایِ سهام — منبعِ درستِ D در فرمولِ
# close_ex/(close_ex+dps) (R32H: ۲۰ از ۳۲ گامِ دور دقیق شد). مقدار از صفحهٔ
# Decision.aspxِ کدال می‌آید، نه از اختلافِ pna−pclِ دفترِ تعدیل؛ `d_even` همان
# روزِ مؤثرِ ردیفِ PA است و `reference_price` پایانیِ رسمیِ همان روز.
# نبودِ ردیف یعنی «اعلامی پیدا نشد» — نه DPSِ صفر.
STOCK_DIVIDEND_EVENTS = """
CREATE TABLE IF NOT EXISTS stock_dividend_events (
    ins_code TEXT, d_even INTEGER, symbol TEXT,
    dps REAL, reference_price REAL, ratio REAL,
    publish_date TEXT, source TEXT, source_id TEXT, fetched_at TEXT,
    PRIMARY KEY (ins_code, d_even))
"""

# ردیف‌هایی که CDN در CSV تاریخی جا انداخته ولی `/ClosingPrice/GetClosingPriceDaily`
# همان روز را دارد. فقط ردیفِ رسمیِ همان روز؛ هیچ ساختن/کپیِ روزِ مجاور.
SESSION_BACKFILL = """
CREATE TABLE IF NOT EXISTS session_backfill (
    ins_code TEXT, d_even INTEGER, symbol TEXT,
    open REAL, high REAL, low REAL, close REAL, last REAL,
    base REAL, volume REAL,
    source TEXT, source_id TEXT, fetched_at TEXT,
    PRIMARY KEY (ins_code, d_even))
"""

# تاریخ‌هایی که یک گسستِ پایهٔ بازار-گسترده (نه اقدام شرکتی) داشته‌اند.
# توسط `tools/session_anomaly_scan.py` از شواهد cross-sectional پر می‌شود؛
# هیچ تاریخی در کد hard-code نیست.
SESSION_ANOMALIES = """
CREATE TABLE IF NOT EXISTS session_anomalies (
    d_even INTEGER PRIMARY KEY, gap_symbols INTEGER, official_symbols INTEGER,
    product_only_steps INTEGER, median_abs_ratio_deviation REAL,
    cause TEXT, evidence TEXT, built_at TEXT)
"""

# کلید سه‌تایی: GetInstrumentStateTop «تغییراتِ وضعیت» می‌دهد نه وضعیتِ روزانه،
# و یک نماد در یک روز چند بار جابه‌جا می‌شود (سنجشِ زنده: 500 رکورد با کلیدِ
# دوتایی فقط 225 ردیف می‌گذاشت).
INSTRUMENT_STATE = """
CREATE TABLE IF NOT EXISTS instrument_state (
    ins_code TEXT, d_even INTEGER,
    c_etaval TEXT, c_etaval_title TEXT, under_supervision INTEGER,
    last_h_even INTEGER NOT NULL DEFAULT 0, real_heven INTEGER,
    source TEXT, fetched_at TEXT,
    PRIMARY KEY (ins_code, d_even, last_h_even))
"""

# webgw فقط «علتِ توقف» را دارد و کلیدش `nam` است — رشتهٔ «نماد(نامِ کامل)»،
# نه insCode و نه ISIN. پیوند با instruments.l_val18 با fold_persian انجام
# می‌شود؛ نمادِ بی‌همتا ذخیره نمی‌شود.
STOP_REASONS = """
CREATE TABLE IF NOT EXISTS stop_reasons (
    symbol TEXT PRIMARY KEY, status_code INTEGER,
    vaziyat_desc TEXT, last_date_change TEXT, dalils TEXT,
    source TEXT, fetched_at TEXT)
"""

# این فهرست «وضعیتِ فعلیِ نظارت» است، نه تاریخچه: id=0، userName=null و
# insertionDateTime=0001-01-01 ⇒ کلِ جدول هر اجرا جایگزین می‌شود.
SUPERVISION_STATE = """
CREATE TABLE IF NOT EXISTS supervision_state (
    ins_code TEXT PRIMARY KEY, source_id INTEGER, list_index INTEGER,
    under_supervision INTEGER, under_supervision_title TEXT,
    reasons TEXT, reason_count INTEGER,
    source TEXT, fetched_at TEXT)
"""

# tseMsgIdn کلیدِ خودِ پیام است؛ این پیام‌ها insCode ندارند (فقط flow و تاریخ)
# پس سرنشۀِ بازارند، نه ستونِ نماد.
TSETMC_MESSAGES = """
CREATE TABLE IF NOT EXISTS tsetmc_messages (
    msg_idn INTEGER PRIMARY KEY, d_even INTEGER, h_even INTEGER,
    flow INTEGER, title TEXT, descr TEXT, source TEXT, fetched_at TEXT)
"""

# throttle/بودجهٔ سه خانوادۀ P0 (هیچ‌کدام در حلقۀ ۹۰ ثانیه‌ای نمی‌دوند)
#   last_status / last_result / last_success: «چه شد» را از «کی دویدیم» جدا می‌کنند.
#   پیش ازِ این سه ستون، یکِ روزِ کاملِ بی‌پاسخ (۴ از ۴ flow شکست) دقیقاً مثلِ یکِ روزِ
#   موفق `last_run` می‌گرفت و تا ۲۴ ساعتِ بعدی هیچِ تلاشی نمی‌شد — یعنی شکست با سکوت
#   به‌عنوانِ موفقیت ثبت می‌شد (قیدِ مأموریت: «failure با سکوت به‌عنوان موفقیت ثبت نمی‌شود»).
P0_STATE = """
CREATE TABLE IF NOT EXISTS tsetmc_p0_state (
    name TEXT PRIMARY KEY, last_run TEXT,
    last_status TEXT, last_result TEXT, last_success TEXT)
"""
P0_STATE_EXTRA_COLUMNS = ("last_status", "last_result", "last_success")

ALL = (CLIENT_TYPE_VALUE, CLIENT_TYPE_VALUE_STATE, PRICE_ADJUST_EVENTS,
       SHARE_CHANGE_EVENTS, FUND_PROFIT_EVENTS, STOCK_DIVIDEND_EVENTS,
       SESSION_BACKFILL,
       SESSION_ANOMALIES, INSTRUMENT_STATE, STOP_REASONS, SUPERVISION_STATE,
       TSETMC_MESSAGES, P0_STATE)

TABLES = ("client_type_value", "client_type_value_state", "price_adjust_events",
          "share_change_events", "fund_profit_events", "stock_dividend_events",
          "session_backfill",
          "session_anomalies", "instrument_state", "stop_reasons",
          "supervision_state", "tsetmc_messages", "tsetmc_p0_state")


def migrate_p0_state(conn) -> int:
    """افزودنِ بی‌خطرِ ستون‌هایِ جدید برِ بانک‌هایِ ساخته‌شده با DDLِ قدیمی (idempotent).

    `CREATE TABLE IF NOT EXISTS` هرگز جدولِ موجود را عوض نمی‌کند، پس بدونِ این،
    SELECTِ ستونِ تازه رویِ بانکِ کاربر خطا می‌داد و حلقۀِ تابلو را می‌شکست.
    """
    try:
        have = {r[1] for r in conn.execute("PRAGMA table_info(tsetmc_p0_state)")}
    except Exception:
        return 0
    added = 0
    for col in P0_STATE_EXTRA_COLUMNS:
        if col not in have:
            try:
                conn.execute(f"ALTER TABLE tsetmc_p0_state ADD COLUMN {col} TEXT")
                added += 1
            except Exception:
                pass    # بانکِ قفل‌شده نباید یکِ درخواستِ خواندن را ۵۰۰ کند
    return added


def create_all(conn):
    """همۀ جدول‌ها، idempotent. بی‌صدا می‌بخشد: بانکِ قفل‌شده نباید یک
    درخواستِ خواندن را ۵۰۰ کند — دادهٔ قدیمی از بی‌داده بهتر است."""
    made = 0
    for ddl in ALL:
        try:
            conn.execute(ddl)
            made += 1
        except Exception:
            pass
    migrate_p0_state(conn)      # افزودنیِ بی‌خطر؛ بانکِ قدیمی هم ستون‌هایِ وضعیت را ببیند
    return made
