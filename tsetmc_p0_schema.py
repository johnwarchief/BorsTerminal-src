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
P0_STATE = """
CREATE TABLE IF NOT EXISTS tsetmc_p0_state (
    name TEXT PRIMARY KEY, last_run TEXT)
"""

ALL = (CLIENT_TYPE_VALUE, CLIENT_TYPE_VALUE_STATE, PRICE_ADJUST_EVENTS,
       SHARE_CHANGE_EVENTS, INSTRUMENT_STATE, STOP_REASONS, SUPERVISION_STATE,
       TSETMC_MESSAGES, P0_STATE)

TABLES = ("client_type_value", "client_type_value_state", "price_adjust_events",
          "share_change_events", "instrument_state", "stop_reasons",
          "supervision_state", "tsetmc_messages", "tsetmc_p0_state")


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
    return made
