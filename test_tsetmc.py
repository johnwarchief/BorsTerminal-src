#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TSETMC full market-watch fetcher (optimized).

* one request for whole market: /ClosingPrice/GetMarketWatch
* one request for client-type board: /ClientType/GetClientTypeAll
* one request for industry groups: /StaticData/GetStaticData
* bulk insert/update via executemany into market.db
"""
import os
import re
import sqlite3
import datetime
import json

import candle_contract
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = "https://cdn.tsetmc.com/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://tsetmc.com/",
    "Origin": "https://tsetmc.com",
}
try:
    # حالت EXE: مسیرهای نوشتنی از bors_config (WORK_DIR = %LOCALAPPDATA% در
    # Program Files). __file__ در frozen به _MEIPASS فقط‌خواندنی اشاره می‌کند.
    from bors_config import DB_PATH, STATUS_PATH, MARKET_STATUS_PATH, WORK_DIR
except Exception:  # noqa: BLE001 — dev/standalone
    WORK_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(WORK_DIR, "market.db")
    STATUS_PATH = os.path.join(WORK_DIR, "sync_status.json")
    MARKET_STATUS_PATH = os.path.join(WORK_DIR, "market_sync.json")
_PT = "&".join(f"paperTypes[{i}]={i+1}" for i in range(9))
MW_URL = f"{BASE}/ClosingPrice/GetMarketWatch?market=0&{_PT}&showTraded=false&withBestLimits=true&hEven=0"

# کفِ تاریخِ درخواستِ CSV: همان ۱۹۹۰۰۱۰۱ که `/api/chart` (cdn) استفاده می‌کند — یعنی
# «از اولِ چیزی که منبع منتشر می‌کند». جایگزینِ کفِ ۷۳۰روزه شد (تصمیمِ مالک
# ۱۴۰۵-۰۷-۱۱؛ docs/CANDLE-CONTRACT.md §۲-۴). این «عمقِ خواستنی» است، نه اینکه CDN آن‌قدر
# ردیف دارد: نمادی که ۱۳۹۰ شروع شده فقط همان ۱۳۹۰ به بعد را می‌گیرد، پس ردیفِ ساخته‌شده
# در کار نیست.
CSV_FLOOR = "19900101"

# نقطهٔ تایم‌لاین در پایان هر همگام‌سازی. import در همین‌جا انجام می‌شود تا
# نبودِ mstat_engine (نسخهٔ ناقصِ دیپلوی) همگام‌سازیِ بازار را نکشد — فقط
# تایم‌لاین آپدیت نمی‌شود و یک هشدار چاپ می‌شود.
try:
    from mstat_engine import save_mstat_snapshot
except Exception as _e:      # pragma: no cover - مسیرِ مقاوم در برابر نصف‌شدنِ استقرار
    def save_mstat_snapshot(conn, agg=None):
        print(f"  WARN: mstat snapshot unavailable ({_e})")
        return {"saved": False}


# v9.7.5: با withBestLimits=true خودِ TSETMC آرایهٔ ۵خطِ عمق (blDs) را می‌فرستد.
# پیش‌تر همین درخواست با false زده می‌شد و عمق دور ریخته می‌شد.
PT_MAP = {1: "stock", 2: "stock", 4: "right", 8: "fund"}

# ترتیبِ ستون‌های عمق در market_watch — همان ترتیبی که queue_agg برمی‌گرداند.
# buy_q1_cnt = تعدادِ سفارشِ سطرِ اولِ خرید: درِ ExecFilterِ خودِ tsetmc.com
# همین عدد متغیرِ (zd1) است، و فیلترِ کف‌روبیِ فایلِ مالک با آن داوری می‌کند.
_QUEUE_COLS = ("buy_q_vol", "buy_q_val", "buy_q_cnt",
               "sell_q_vol", "sell_q_val", "sell_q_cnt",
               "buy_q1_vol", "buy_q1_px", "sell_q1_vol", "sell_q1_px",
               "buy_q1_cnt")

# ═══════════════════════════════════════════════════════════════════════════
#  ارزش بازار (Market Cap) — تنها نقطهٔ ساختِ این عدد در کل مخزن
# ═══════════════════════════════════════════════════════════════════════════
# قاعدهٔ v10: هیچ مصرف‌کننده‌ای (API، UI، fts_engine، خروجی) حق ندارد ارزش
# بازار را خودش بسازد. عدد یک‌بار همین‌جا از **ردیفِ خامِ تابلو** خوانده یا ساخته
# و در ستون `market_cap` ذخیره میشود؛ بقیه فقط می‌خوانند.
#   tse_raw               — فیلد خامٔ تابلو به نامٔ marketValue روزی که TSETMC عدد بفرستد
#   tse_board_calc        — نبودِ فیلد خام: دو فیلدِ همان ردیفِ تابلو (pcl × ztd)
#   tse_board_calc_backfill — یک‌بار در مهاجرت، از ستونهایِ همان سطرِ ذخیره‌شده
#   ""                    — هیچ‌کدام معتبر نیست → ستون NULL می‌ماند (صفرِ جعلی نه)
MCAP_SRC_RAW = "tse_raw"
MCAP_SRC_BOARD = "tse_board_calc"
MCAP_SRC_BACKFILL = "tse_board_calc_backfill"
# فقط فیلدی که نامش واقعاً «ارزش بازار» است. qTotCap/qTotValue در پاسخِ تابلو
# «ارزش معاملاتِ روز» است (برای فایرا ۵٫۰۷e۱۱ ریال در برابر ارزش بازارِ
# ۹٫۱e۱۴) — اگر روزی تابلو آن‌ها را با این نام بفرستد، بی‌صدا جای ارزش بازار
# را می‌گیرد و هر دو شاخصِ ۳ و ۴ روی عددِ اشتباه تقسیم می‌کنند.
MCAP_RAW_KEYS = ("marketValue",)

# نوشتن با نامِ ستون — نه جایگاهی. `INSERT ... VALUES(?*30)` با هر ستونِ تازه
# (صف در mstat_engine، ارزش بازار اینجا) بی‌صدا یک ستون جابه‌جا می‌کند و
# «آخرین معامله» با «تاریخِ نشست» قاطی می‌شود — همان طبقهٔ باگی که در v9.8.1
# روی p_last خوردیم. نامِ صریح این اشتباه را غیرممکن می‌کند.
#
# `MW_COLS` تک‌منبعِ این ترتیب است: همان tuple‌ای که `_mw_row` می‌سازد، همان
# ستون‌های INSERT، و همان نگاشتِ «نام → شاخص» که `market_state` برایِ
# زنده‌خوانی لازم دارد. ستونِ تازه = یک ورودِ همین فهرست (INSERT خودکار
# درست می‌شود؛ placeholder از len ساخته می‌شود).
MW_COLS = ("ins_code", "d_even", "h_even", "p_closing", "p_last", "price_min",
           "price_max", "allowed_min", "allowed_max", "price_yesterday",
           "price_first", "q_tot_tran", "q_tot_cap", "z_tot_tran", "price_change",
           "eps", "pe", "total_shares", "sector_code", "fetched_at") + _QUEUE_COLS + \
          ("market_cap", "market_cap_src",
           # سه کلیدِ خامِ همان `GetMarketWatch` که تا این دور دور ریخته می‌شدند
           # (سنژشِ زنده ۱۴۰۵-۰۷-۱۳: هر ۳۸۴۷ ردیف این‌ها را دارد). هیچ‌کدام درِ
           # کوئریِ تابلو و درِ بدنهٔ /api/market نمی‌نشینند — مصرف‌کننده ندارند
           # و بدنۀ سریال‌شدہ باید بایت‌به‌بایت یکی بماند.
           #   flow       = کدِ بازار (۱ بورس / ۲ فرابورس / …) — نه از `boards`
           #   p_red_tran = قیمتِ استردادِ NAV (صندوق/ETF)
           #   buy_op     = قیمتِ صدورِ NAV
           "flow", "p_red_tran", "buy_op")
# instruments با نامِ ستون نوشته می‌شود، نه موقعیتی: `paper_type` را
# mstat_engine.MIGRATIONS با ALTER می‌افزاید، پس ترتیبِ ستون‌ها درِ بانکِ تازه
# (DDL) با بانکِ ارتقایافته فرق می‌کند و INSERT موقعیتی رویِ یکی از دو مسیر
# ستون‌ها را جابه‌جا می‌نشاند.
_INST_COLS = ("ins_code", "l_val18", "l_val30", "sector_code", "sector_name",
              "total_shares", "eps", "pe", "base_vol", "updated_at", "paper_type",
              "isin", "c_gr_val_cot")
_INST_INSERT = ("INSERT OR REPLACE INTO instruments (" + ", ".join(_INST_COLS)
                + ") VALUES (" + ",".join("?" * len(_INST_COLS)) + ")")
_MW_INSERT = ("INSERT OR REPLACE INTO market_watch ("
              + ", ".join(MW_COLS) + ") VALUES ("
              + ",".join("?" * len(MW_COLS)) + ")")
_DP_INSERT = ("INSERT OR REPLACE INTO daily_prices ("
              "ins_code, d_even, p_closing, price_min, price_max, price_yesterday,"
              " price_first, q_tot_tran, q_tot_cap, price_change, fetched_at,"
              " market_cap, market_cap_src, z_tot_tran, p_last) VALUES ("
              + ",".join("?" * 15) + ")")


def session_day_of(watch_rows, fallback=0):
    """روزِ نشستی که واقعاً در آن معامله شده است.

    TSETMC پیش از بازگشایی هم ردیف می‌فرستد — با `dEven`ِ همان روزِ جدید و
    حجمِ صفر. اگر همان روز را نشستِ واقعی بگیریم، دادهٔ «کدهای حقیقی/حقوقی»
    که مربوطِ آخرین نشست است زیرِ تاریخِ امروز نوشته می‌شود و نبض بازار یک
    ردیفِ دوروژه می‌سازد: حجمِ امروز صفر، ولی جریانِ پول از نشستِ پیش.
    اندازه‌گیری‌شده ۱۴۰۵-۰۷-۰۴: client_type برایِ ۲۳/۲۴/۲۵/۲۶ سپتمبر یک
    ردیفِ بایت‌به‌بایت یکسان داشت.
    """
    days = [w[1] for w in watch_rows if w[1] and (w[11] or 0) > 0]
    return max(days) if days else int(fallback or 0)


def ensure_daily_tran_column(conn):
    """ستونِ «تعدادِ معاملات» را رویِ daily_prices می‌سازد (idempotent).

    qd1 — قیدِ چهارمِ فیلترِ کف‌روبی در فایلِ مالک — تنها از همین ستاد خوانده
    می‌شود. CREATE TABLE IF NOT EXISTS بانکِ موجود را به‌روز نمی‌کند، پس ALTER
    لازم است؛ فقط افزودنِ ستون، بدونِ حذف یا بازنویسیِ هیچ ردیفی.
    """
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(daily_prices)")}
        if cols and "z_tot_tran" not in cols:
            conn.execute("ALTER TABLE daily_prices ADD COLUMN z_tot_tran REAL")
    except sqlite3.Error:
        pass




def board_market_cap(row, price=None, shares=None):
    """(ارزش_بازار_ریال, منبع) از یک ردیفِ خامِ GetMarketWatch.

    محافظها: صفر/منفی/NaN/تهی «ارزش بازار» نیست؛ نتیجه None می‌ماند تا
    مصرف‌کننده آن را «داده نبود» بداند، نه «شرکت بی‌ارزش» — و شاخص ۴ روی
    صفر تقسیم نکند.
    """
    for k in MCAP_RAW_KEYS:
        v = num(row.get(k)) if isinstance(row, dict) else None
        if v is not None and v == v and v > 0:
            return v, MCAP_SRC_RAW
    if not isinstance(row, dict):
        row = {}
    p = price if price is not None else num(row.get("pcl"))
    s = shares if shares is not None else num(row.get("ztd"))
    if p and s and p == p and s == s and p > 0 and s > 0:
        return p * s, MCAP_SRC_BOARD
    return None, ""


# ═══════════════════════════════════════════════════════════════════════════
#  کل ارزش بازار — تنها نقطهٔ ساختِ این عدد در کل مخزن
# ═══════════════════════════════════════════════════════════════════════════
# «کل ارزش بازار» را **نمی‌توان** از جمعِ ردیف‌های تابلو ساخت. دو دلیلِ اندازه‌گیری‌شده:
#   ۱) یک شرکت به ازای هر بازارِ معاملاتی‌اش ردیف جدا دارد — «فولاد» و «فولاد3»
#      دو ردیف با دو insCode ولی یک ISIN (IRO1FOLD0009) و یک تعداد سهام‌اند؛
#   ۲) ردیفِ نشست‌های قدیمی از market_watch حذف نمی‌شود (۵٬۲۰ ردیف در برابر
#      ۳٬۷۸ ردیفِ زندهٔ تابلو).
# جمعِ دستی پس ۷۰۳۸۶ همت شد؛ عددِ رسمیِ خودِ TSETMC ۲۴٬۸۵۷ همت. پس عدد از
# MarketData/GetMarketOverview خوانده و یک‌بار اینجا ذخیره می‌شود؛ بقیه فقط
# می‌خوانند (mstat_engine.market_total_rials).
MARKET_TOTALS_TABLE = "market_totals"
# ۱=بورس، ۲=فرابورس؛ «بازار پایهٔ فرابورس» در marketValueBase همان پاسخ است.
MARKET_TOTAL_MARKETS = (1, 2)


def ensure_market_totals_schema(conn):
    """جدولِ کل ارزش بازار را idempotent می‌سازد (پایگاه‌دادهٔ کهنه ستون ندارد)."""
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {MARKET_TOTALS_TABLE} ("
        " d_even INTEGER PRIMARY KEY, market_value REAL, source TEXT, updated_at TEXT)")


def fetch_market_total(s):
    """(ارزش_بازار_ریال, d_even, پاسخِ بورس) از خودِ TSETMC — یا (0.0, 0, None).

    صفرِ جعلی نمی‌سازد: اگر هر دو بازار پاسخ ندادند (۴۲۹/قطعی) همان (0.0, 0, None)
    برمی‌گردد و مصرف‌کننده روی مسیرِ پشتیبان می‌نشیند. سومین عضو تاپل همان
    دیکشنریِ بورس است تا شاخصِ کل/هموزنِ همان درخواستِ رایگان دور ریخته نشود.

    نصفه هم نمی‌نویسد: هر دو بازار (بورس و فرابورس) همیشه ارزشِ مثبت دارند، پس
    اگر یکی پاسخ نداد یا صفر داد، کلِ عدد رد می‌شود. اندازه‌گیریِ ۱۴۰۵-۰۷-۰۶ روی
    بانکِ نصبی: سینکِ ۰۶:۰۷ صبح فقط یک بازار را گرفت و ۸٬۰۰۹ همت نوشت در برابر
    ۲۵۶٬۱۳۱ همتِ همان روزِ بانکِ توسعه — ۳٪. نسخهٔ پیشین هر جمعِ ناصفری را
    می‌پذیرفت و همان ردیفِ غلط تا ابد در جدول می‌ماند.
    """
    total, d_even, bourse_ov, answered = 0.0, 0, None, 0
    for m in MARKET_TOTAL_MARKETS:
        ov = polite_get(s, f"{BASE}/MarketData/GetMarketOverview/{m}", "marketOverview")
        if isinstance(ov, list):
            ov = ov[0] if ov else {}
        if not isinstance(ov, dict):
            continue
        v = num(ov.get("marketValue")) or 0.0
        v += num(ov.get("marketValueBase")) or 0.0
        if v > 0:
            total += v
            answered += 1
        # بورس (marketType ۱) تنها بازاری است که indexEqualWeightedLastValue دارد.
        if bourse_ov is None and (num(ov.get("indexLastValue")) or 0) > 0:
            bourse_ov = ov
        d_even = max(d_even, int(num(ov.get("marketActivityDEven")) or 0))
    if answered < len(MARKET_TOTAL_MARKETS):
        return 0.0, d_even, bourse_ov
    return (total if total > 0 else 0.0, d_even, bourse_ov)


MARKET_INDEX_TABLE = "market_index"


def ensure_market_index_schema(conn):
    """جدولِ شاخصِ رسمی را idempotent می‌سازد.

    همان GetMarketOverview که market_totals را می‌سازد indexLastValue و
    indexEqualWeightedLastValue را هم می‌فرستد؛ تا پیش از این آن دو دور ریخته
    می‌شدند و برنامه هیچ‌جایِ خودِ «شاخص کل» نداشت (تریدرز آرنا و ره‌آورد هر دو
    این دو عدد را در بالای صفحه نشان می‌دهند). درصد اینجا ساخته می‌شود تا لایهٔ
    نمایش هیچ حسابی نکند.
    """
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {MARKET_INDEX_TABLE} ("
        " d_even INTEGER PRIMARY KEY, idx_last REAL, idx_change REAL, idx_pct REAL,"
        " ew_last REAL, ew_change REAL, ew_pct REAL,"
        " z_tot_tran REAL, q_tot_cap REAL, q_tot_tran REAL, updated_at TEXT)")


def _idx_pct(last, change):
    """درصدِ تغییر از «آخرین» و «تغییر» — مبنای عددِ پیش از نشست."""
    if not last or not change:
        return None
    base = float(last) - float(change)
    if base <= 0:
        return None
    return round(float(change) / base * 100.0, 2)


def save_market_index(conn, ov, d_even, now=None):
    """شاخصِ کل و هموزنِ همان نشست را از پاسخِ رسمیِ بورس ذخیره می‌کند.

    ov None یا بی‌شاخص باشد هیچ نمی‌نویسد — صفرِ جعلی بهتر است هیچ نباشد.
    """
    if not isinstance(ov, dict) or not d_even:
        return False
    last = num(ov.get("indexLastValue")) or 0.0
    ew_last = num(ov.get("indexEqualWeightedLastValue")) or 0.0
    if last <= 0 and ew_last <= 0:
        return False
    ensure_market_index_schema(conn)
    conn.execute(
        f"INSERT OR REPLACE INTO {MARKET_INDEX_TABLE} VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (int(d_even),
         last or None, num(ov.get("indexChange")) or None,
         _idx_pct(last, num(ov.get("indexChange"))),
         ew_last or None, num(ov.get("indexEqualWeightedChange")) or None,
         _idx_pct(ew_last, num(ov.get("indexEqualWeightedChange"))),
         num(ov.get("marketActivityZTotTran")), num(ov.get("marketActivityQTotCap")),
         num(ov.get("marketActivityQTotTran")),
         now or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    return True


MARKET_LIQ_TABLE = "market_liquidity"


def ensure_market_liquidity_schema(conn):
    """جدولِ «ارزشِ معاملاتِ خردِ هر نشست» را idempotent می‌سازد."""
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {MARKET_LIQ_TABLE} ("
        " d_even INTEGER PRIMARY KEY, value_hemat REAL, basis TEXT, updated_at TEXT)")


def save_market_liquidity(conn, d_even, now=None):
    """همتِ همان نشست را به همان مبنایِ نبض بازار ذخیره می‌کند (تاریخچۀ تداوم).

    جزوه ص۱۳ می‌گوید نقدینگی را «برایِ حرانتِ ۳ الی ۴ روزِ متوالی» ببین؛ عددِ
    امروز از تابلویِ زنده ساخته می‌شد ولی هیچ‌جا نمی‌ماند، پس آن در هرگز
    بسته نمی‌شد. مبنایش عمداً از خودِ mstat_engine.macro_health گرفته می‌شود
    (سهام + حق‌تقدم + ص.سهامی) تا تاریخچه با عددِ امروز سیب‌به‌سیب مقایسه
    شود — جمعِ دستیِ z_tot_tran در تابلو مبنای دیگری است و بازارِ کل با
    شمارشِ صندوق‌های درآمد ثابت آستانهٔ ۲۰ همت را همیشه سبز می‌کند.
    بی‌داده هیچ نمی‌نویسد؛ صفرِ باورپذیر بدتر از هیچ است.
    """
    if not d_even:
        return False
    try:
        import mstat_engine as _me
        macro = _me.macro_health(conn)
    except Exception:
        return False
    hemat = macro.get("value_hemat")
    if not hemat or hemat <= 0:
        return False
    ensure_market_liquidity_schema(conn)
    conn.execute(
        f"INSERT OR REPLACE INTO {MARKET_LIQ_TABLE} VALUES (?,?,?,?)",
        (int(d_even), float(hemat), macro.get("basis") or "eq_all",
         now or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    return True


def save_market_total(conn, total_rials, d_even, now=None):
    """عددِ رسمی را برای همان نشست ذخیره می‌کند؛ True اگر واقعاً نوشته شد.

    commit درونِ همین تابع است، نه در فراخوان. دو فراخوان دارد (main و
    _save_market_snapshot) و نسخهٔ اول در یکی commit نداشت؛ روی EXE نصب‌شده
    تست شد و لاگ می‌گفت «نوشته شد» ولی sqlite هنگام بستنِ اتصال rollback
    می‌کرد و جدول تا ابد بی‌عددِ رسمی می‌ماند.
    """
    if not total_rials or total_rials <= 0 or not d_even:
        return False
    ensure_market_totals_schema(conn)
    conn.execute(
        f"INSERT OR REPLACE INTO {MARKET_TOTALS_TABLE}"
        " (d_even, market_value, source, updated_at) VALUES (?, ?, 'tse_market_overview', ?)",
        (int(d_even), float(total_rials),
         now or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    return True


def ensure_market_cap_schema(conn):
    """ستونهایِ market_cap را idempotent می‌سازد و سطرهایِ کهنه را پر می‌کند.

    ALTER داخل try/except — روی DB تازةساخته‌شده (که CREATE TABLE خودش ستون را
    دارد) خطای «duplicate column» انتظار می‌رود و بی‌صدا رد می‌شود.
    """
    for tbl in ("market_watch", "daily_prices"):
        for col, decl in (("market_cap", "REAL"), ("market_cap_src", "TEXT")):
            try:
                conn.execute("ALTER TABLE %s ADD COLUMN %s %s" % (tbl, col, decl))
            except sqlite3.OperationalError:
                pass                          # از قبل هست، یا جدول ساخته نشده
            except sqlite3.Error:
                pass
    # یک‌بار پرکردنِ سطرهایِ موجود، از دو فیلدِ **همان سطرِ تابلو**.
    # daily_prices ستونِ سهام ندارد؛ همان سطرِ instruments با subquery هم‌سطح
    # می‌خوانده میشود (correlated subquery روی همهٔ نسخه‌های sqlite کار میکند،
    # برخلاف UPDATE ... FROM که به ۳٫۳۳+ نیاز دارد).
    try:
        conn.execute(
            "UPDATE market_watch SET market_cap = p_closing * total_shares, "
            "market_cap_src = ? WHERE market_cap IS NULL "
            "AND COALESCE(p_closing, 0) > 0 AND COALESCE(total_shares, 0) > 0",
            (MCAP_SRC_BACKFILL,))
    except sqlite3.Error:
        pass
    try:
        conn.execute(
            "UPDATE daily_prices SET "
            "  market_cap = p_closing * ("
            "      SELECT i.total_shares FROM instruments i"
            "      WHERE i.ins_code = daily_prices.ins_code),"
            "  market_cap_src = ? "
            "WHERE market_cap IS NULL AND COALESCE(p_closing, 0) > 0 AND ("
            "      SELECT i.total_shares FROM instruments i"
            "      WHERE i.ins_code = daily_prices.ins_code) > 0",
            (MCAP_SRC_BACKFILL,))
    except sqlite3.Error:
        pass
    return True



def queue_agg(row):
    """blDs → جمع ۵ خط اول و بعد خطِ اول به‌تنهایی.

    خروجی ۱۱تایی: (b_vol,b_val,b_cnt, s_vol,s_val,s_cnt, b1_vol,b1_px, s1_vol,s_px, b1_cnt)
    ارزش = حجم × قیمتِ همان خط (ریال) — همان یکای q_tot_cap، پس واحدها در
    داشبورد قاطی نمی‌شوند. نبودِ blDs یعنی None (ستون NULL می‌ماند) نه صفر:
    «عمق نبود» با «عمق تهی بود» یکی نیست و UI باید فرقشان بداند.
    b1_cnt (= blDs[0].zmd) تنها چیزی است که متغیرِ (zd1) درِ فیلترنویسِ TSETMC
    به آن نگاه می‌کند؛ بی‌ستونش قیدِ «تعدادِ خریدارِ سطرِ اول > ۱» سنجیدنی نیست.
    """
    lines = row.get("blDs")
    if not isinstance(lines, list) or not lines:
        return None
    bq = bqv = bc = sq = sqv = sc = 0.0
    for ln in lines:
        b_vol, b_px = num(ln.get("qmd")), num(ln.get("pmd"))
        s_vol, s_px = num(ln.get("qmo")), num(ln.get("pmo"))
        bq += b_vol
        bqv += b_vol * b_px
        bc += num(ln.get("zmd"))
        sq += s_vol
        sqv += s_vol * s_px
        sc += num(ln.get("zmo"))
    first = lines[0] if lines and isinstance(lines[0], dict) else {}
    return (bq, bqv, bc, sq, sqv, sc,
            num(first.get("qmd")), num(first.get("pmd")),
            num(first.get("qmo")), num(first.get("pmo")),
            num(first.get("zmd")))


# ═══════════════════════════════════════════════════════════════════════════
#  پنل «۵ مظنه» — پنج خطِ کاملِ عمق، که تا پیش از این دور ریخته می‌شد
# ═══════════════════════════════════════════════════════════════════════════
# queue_agg عمق را به «جمعِ پنج خط» و «خطِ اول» می‌شکند، چون ستون‌هایِ تابلو و
# فیلترهایِ جزوه همین دو را می‌خواهند. ولی نمایشِ صفِ خرید و فروش به تک‌تکِ
# سطرها نیاز دارد و blDs از همیشه هر پنج خط را می‌فرستاد. جدولِ جدا نوشته می‌
# شود نه ستونِ اضافه روی market_watch: آن INSERT سی‌ودو ستونه و چند گارد به
# ترتیبش قفل‌اند، و عمق هیچ‌وقت در هیچ کوئریِ تابلو خوانده نمی‌شود.
ORDER_BOOK_TABLE = "order_book"

_OB_INSERT = ("INSERT OR REPLACE INTO order_book"
              " (ins_code, d_even, h_even, book_txt, updated_at)"
              " VALUES (?,?,?,?,?)")


def ensure_order_book_schema(conn):
    """جدولِ عمقِ پنج‌سطحی را idempotent می‌سازد."""
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {ORDER_BOOK_TABLE} ("
        " ins_code TEXT PRIMARY KEY, d_even INTEGER, h_even INTEGER,"
        " book_txt TEXT, updated_at TEXT)")


def book_lines(row):
    """blDs → JSONِ فشردهٔ پنج خط: [[قیمت، حجم، تعدادِ سفارش] برایِ خرید و فروش].

    هر سطر [bpx, bvol, bcnt, spx, svol, scnt] است. سطری که هیچ‌یک از دو طرفِش
    قیمت ندارد نوشته نمی‌شود؛ نبودِ کلِ blDs برابرِ None است، نه «صفِ خالی» —
    همان قاعده‌ای که queue_agg برایِ ستونِ NULL گذاشته بود.
    """
    lines = row.get("blDs")
    if not isinstance(lines, list) or not lines:
        return None
    out = []
    for ln in lines[:5]:
        if not isinstance(ln, dict):
            continue
        bpx, bvol, bcnt = num(ln.get("pmd")), num(ln.get("qmd")), num(ln.get("zmd"))
        spx, svol, scnt = num(ln.get("pmo")), num(ln.get("qmo")), num(ln.get("zmo"))
        if not bpx and not spx:
            continue
        out.append([bpx or 0.0, bvol or 0.0, bcnt or 0.0,
                    spx or 0.0, svol or 0.0, scnt or 0.0])
    return json.dumps(out, separators=(",", ":")) if out else None


def save_order_book(conn, rows):
    """سطرهایِ (ins_code, d_even, h_even, book_txt, updated_at) را می‌نویسد.

    نمادی که در این پاسخ عمق ندارد در `rows` نیست و سطرِ کهنه‌اش دست‌نخورده
    می‌ماند؛ قضاوتِ «عمقِ این نشست است یا نشستِ پیش» با d_even/h_evenِ خودِ سطر
    است، نه با حدسِ مصرف‌کننده.
    """
    if not rows:
        return 0
    ensure_order_book_schema(conn)
    conn.executemany(_OB_INSERT, rows)
    return len(rows)


# ── پنجرۀ [ih]، عینِ منابعِ فیلترنویسِ سایت ─────────────────────────────────
# فیلترنویسِ خودِ tsetmc.com آرایۀِ [ih] را از یک درخواست می‌سازد: شصت نشستِ
# آخرِ **هر نماد**، با ردیفِ صفر برایِ نشستِ بی‌معامله. بانکِ ما تنها روزهایی را
# دارد که نماد در آن معامله کرده، پس «۱۸ ردیف» با «۱۸ نشست عمر» اشتباه می‌شود و
# درِ «کمتر از ۳۰ نشست» برایِ نمادِ کهنۀِ کم‌معامله بسته می‌ماند (خگلپا: ۶۰ نشست
# درِ سایت، ۱۸ ردیفِ ما — دو فیلترِ حجمی بی‌دلیل خاموش).
TAPE_HIST_URL = f"{BASE}/ClosingPrice/GetClosingPriceDailyAllInst"
TAPE_HIST_KEY = "closingPriceDailyAllInst"
TAPE_HIST_TABLE = "tape_history"
TAPE_HIST_STATE = "tape_history_state"
# پنجره کهنه باشد یک تلاشِ دیگر؛ بیشتر از این نه، که پاسخ ۵۱ مگابایت است و
# همگام‌سازی در ساعتِ بازار هر چند دقیقه یک‌بار صدا می‌شود.
TAPE_HIST_RETRY_S = 6 * 3600
# پنجره باید نمادهایِ امروز را بپوشاند، نه فقط روزِ درست را داشته باشد. پاسخِ
# سایت گاه کوتاه می‌آید (اندازۀ ۱۴۰۵-۰۷-۰۷: ۷۴٪ پوشش) و نمادی که ردیفِ [ih]
# ندارد درِ پنج فیلتر بی‌صدا مردود می‌ماند. ۹۵٪ سقفِ محافظه‌کارانه‌ای است که با
# پوششِ کاملِ سایت (۹۹+٪) فرقِ روشن دارد و بی‌دلیل هر سینک ۵۱ مگابایت نمی‌گیرد.
TAPE_COVER_MIN = 0.95
# نوشتن با نامِ ستون: بانکِ ارتقایافته این جدول را با پنج ستون ساخته و
# `q_tot_cap` را `mstat_engine.MIGRATIONS` با ALTER به **آخر** افزوده است، پس
# ترتیبِ ستون‌هایش (…، fetched_at، q_tot_cap) با بانکِ تازه (…، q_tot_cap،
# fetched_at) یکی نیست. INSERT موقعیتی رویِ بانکِ ارتقایافته زمان را درِ
# `q_tot_cap` و عدد را درِ `fetched_at` می‌نشاند — همان طبقهٔ باگی که رویِ
# `client_type_value.kind` خوردیم. `recs` هم همین ترتیب را دارد.
_TAPE_HIST_COLS = ("ins_code", "d_even", "price_min", "price_max",
                   "q_tot_tran5j", "q_tot_cap", "fetched_at")
_TAPE_HIST_INSERT = (f"INSERT OR REPLACE INTO {TAPE_HIST_TABLE} ("
                     + ", ".join(_TAPE_HIST_COLS) + ") VALUES ("
                     + ",".join("?" * len(_TAPE_HIST_COLS)) + ")")


def ensure_tape_history_schema(conn):
    conn.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS {TAPE_HIST_TABLE} (
            ins_code TEXT NOT NULL, d_even INTEGER NOT NULL,
            price_min REAL, price_max REAL, q_tot_tran5j REAL,
            -- q_tot_cap = ارزشِ معاملاتِ همان نشست (کلیدِ خامِ qTotCap). درِ همان
            -- پاسخِ 24MB هست (سنجشِ زنده: 184911 ردیف، ردیفِ نمونه این کلید را
            -- دارد) و پیش از این دور ریخته می‌شد؛ هر فیلترِ «میانگینِ ارزشِ ۳۰
            -- روز» بی‌این مجبور است ارزش را از حجم×قیمت بسازد.
            q_tot_cap REAL,
            fetched_at TEXT, PRIMARY KEY (ins_code, d_even));
        CREATE TABLE IF NOT EXISTS {TAPE_HIST_STATE} (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_attempt TEXT, last_ok TEXT, newest_d_even INTEGER, note TEXT);
        """)
    # ستونِ تازهٔ q_tot_cap را mstat_engine.MIGRATIONS می‌افزاید (تک‌منبعِ
    # مهاجرتِ ستون)؛ این‌جا ALTER دوم نمی‌نویسیم.


def fetch_tape_history(timeout=120, attempts=3, gap=20):
    """([ih] rows | None, خطا). None یعنی «نگرفتم» — با «خالی گرفت» یکی نیست.

    بی‌stream تنها راهِ آزموده‌شده است: با stream=True همین پاسخ ۱۸۰ ثانیه
    بی‌پاسخ ماند و ترکید، و درخواستِ معمولی در ۳ ثانیه تمام می‌شود. کشِ CDN
    گاه سرد است، پس چند تلاشِ فاصله‌دار.
    """
    import time as _t
    err = "empty-response"
    for i in range(attempts):
        try:
            r = requests.get(TAPE_HIST_URL, headers=HEADERS, timeout=timeout)
            r.raise_for_status()
            rows = r.json().get(TAPE_HIST_KEY) or []
        except (requests.exceptions.RequestException, ValueError, OSError,
                PermissionError) as e:
            err = type(e).__name__
            rows = []
        if rows:
            return rows, None
        if i + 1 < attempts:
            _t.sleep(gap)
    return None, err


def tape_window_coverage(conn):
    """چه کسری از نمادهایِ **معامله‌شدهٔ امروز** پنجرۀ [ih] را دارند.

    پنج فیلتر بی‌این پنجره هیچ‌وقت روشن نمی‌شوند (`prior30_vol` تهی = نسنج)، پس
    پنجره‌ای که نمادی را ندارد آن نماد را **بی‌صدا مردود** می‌کند — و درِ خودِ
    سایت همان نماد را فیلتر می‌کند. اندازه‌گیریِ ۱۴۰۵-۰۷-۰۷: پنجرۀِ ۰۸:۵۵
    ۳٬۲۳۸ نماد داشت و از ۲٬۲۷۰ نمادِ معاملۀِ امروز فقط ۱٬۶۸۲ تایش ردیفِ [ih]
    داشتند (۷۴٪)؛ ۵۸۸ نمادِ بی‌پنجره هیچ‌وقت نمی‌توانستند «حجم مشکوک» بگیرند و
    جدولِ ما ۸۱ ردیف می‌داد در برابرِ ۱۰۲ ردیفِ خودِ سایت (سنجشِ یک‌لحظه‌ایِ
    _audit/tse_live_filter_parity.py — گوهر، سيستم۳، پتروپاداش، بمپنا۳، …).

    (تعدادِ ردیفِ جدول معیار نیست: پاسخِ سایت گاه کوتاه‌تر می‌آید ولی همان
    نمادها را دارد؛ آنچه می‌سوزد نبودنِ خودِ نماد است.)
    """
    traded = conn.execute(
        "SELECT COUNT(*) FROM market_watch WHERE d_even = ?"
        " AND COALESCE(q_tot_tran, 0) > 0",
        (board_session_day(conn),)).fetchone()[0] or 0
    if not traded:
        return 1.0, 0, 0
    covered = conn.execute(
        "SELECT COUNT(*) FROM market_watch m WHERE m.d_even = ?"
        " AND COALESCE(m.q_tot_tran, 0) > 0"
        f" AND EXISTS (SELECT 1 FROM {TAPE_HIST_TABLE} h WHERE h.ins_code = m.ins_code)",
        (board_session_day(conn),)).fetchone()[0] or 0
    return (covered / traded), traded, covered


def board_session_day(conn):
    """نشستِ جاریِ تابلو — همان روزی که پنجره باید او را بپوشاند."""
    return conn.execute("SELECT MAX(d_even) FROM market_watch").fetchone()[0] or 0


def refresh_tape_history(conn, force=False, fetch=None):
    """پنجرۀ [ih] را نو می‌کند. شکستِ شبکه هرگز جدول را پاک نمی‌کند.

    پنجرۀِ دیروز (یک نشست کهنه) هنوز سنجش را درست می‌گذارد — همان‌طور که درِ
    سایت هم درِ ساعتِ بازار پنجره را تا نهایۀِ دیروز می‌گیرد — ولی جدولِ خالی
    پنج فیلتر را یک‌باره خاموش می‌کند. پس بدترین انتخاب پاک‌کردن است.
    """
    ensure_tape_history_schema(conn)
    conn.execute("PRAGMA busy_timeout=30000")
    now = datetime.datetime.now()
    now_txt = now.strftime("%Y-%m-%d %H:%M:%S")
    have, newest = conn.execute(
        f"SELECT COUNT(*), MAX(d_even) FROM {TAPE_HIST_TABLE}").fetchone()
    board_day = board_session_day(conn)
    st = conn.execute(f"SELECT * FROM {TAPE_HIST_STATE} WHERE id = 1").fetchone()
    last_attempt, last_ok, last_note = (st[1], st[2], st[4]) if st else (None, None, None)
    # «تازه» یعنی هم روزش همان نشست است هم نمادهایش. بی‌شرطِ دوم، پنجرۀِ
    # کوتاه‌آمدهٔ صبح تا نهایهٔ شب «تازه» می‌ماند و صدها نماد بی‌دلیل مردود
    # می‌شوند (tape_window_coverage).
    ratio, traded, covered = tape_window_coverage(conn)
    if (not force and have and board_day and (newest or 0) >= board_day
            and ratio >= TAPE_COVER_MIN):
        return {"skipped": "fresh"}
    if not force and have and board_day and (newest or 0) >= board_day:
        print(f"  [tape-history] پنجره روزش درست است ولی پوشش کم است: "
              f"{covered:,} از {traded:,} ({ratio * 100:.1f}٪) — دوباره گرفته می‌شود")
    # قفلِ ۶ ساعته فقط برایِ تلاشی است که «تمام» شده باشد (موفق یا خطای قطعی).
    # تلاشِ نیمه‌کاره — app وسطِ fetchِ چنددقیقه‌ای بسته شد و note همان
    # «attempt» ماند — نباید پشتِ تایمر بنشیند. بی‌این، نخستین fetchِ پس از
    # نصب که یک‌بار abort شد، پنجرۀ [ih] را خالی می‌گذاشت و هر restart تا
    # ۶ ساعت «throttled» می‌خورد؛ ستونِ «الگو» برای همیشه بی‌بج می‌ماند.
    # (اندازۀ ۱۴۰۵-۰۷-۰۶: همین سناریو رویِ ماشینِ نصب‌شده تکرار شد — یک
    # HTTPErrorِ گذرا از CDN در ۱۰:۰۶، و پنج فیلتر تا بعدازظهر صفر ماندند.
    # وقتی جدول خالی است، «پنجرۀ کهنه»ای برای محفوظ‌داشتن وجود ندارد؛
    # تایمر بی‌موضوع است و باید هر دورِ سینک دوباره tried شود.)
    if not force and have and last_attempt and last_note != "attempt":
        try:
            age = (now - datetime.datetime.strptime(last_attempt,
                                                    "%Y-%m-%d %H:%M:%S")).total_seconds()
        except ValueError:
            age = TAPE_HIST_RETRY_S + 1.0
        if age < TAPE_HIST_RETRY_S:
            return {"skipped": "throttled"}
    conn.execute(f"INSERT OR REPLACE INTO {TAPE_HIST_STATE} VALUES (1, ?, ?, ?, ?)",
                 (now_txt, last_ok, newest, "attempt"))
    conn.commit()
    rows, err = (fetch or fetch_tape_history)()
    if not rows:
        conn.execute(f"UPDATE {TAPE_HIST_STATE} SET note = ? WHERE id = 1", (err,))
        conn.commit()
        print(f"  [tape-history] نگرفت ({err}) — پنجرۀِ کهنه دست‌نخورده ماند")
        return {"error": err}
    recs = []
    for x in rows:
        ins, d = x.get("insCode"), x.get("dEven")
        if not ins or not d:
            continue
        recs.append((ins, int(d), num(x.get("priceMin")) or 0.0,
                     num(x.get("priceMax")) or 0.0,
                     num(x.get("qTotTran5J")) or 0.0,
                     num(x.get("qTotCap")), now_txt))
    if not recs:
        conn.execute(f"UPDATE {TAPE_HIST_STATE} SET note = 'no-rows' WHERE id = 1")
        conn.commit()
        return {"error": "no-rows"}
    top = max(r[1] for r in recs)
    # پنجره را بی‌سرنوشت عوض نکن: پاسخِ سایت گاه **کوتاه** می‌آید (اندازۀ
    # ۱۴۰۵-۰۷-۰۷: همان endpoint یک دور ۳٬۲۳۸ نماد داد و دور بعد ۳٬۹۴۱). بی‌این
    # بند، همان پاسخِ کوتاهِ ۰۸:۵۵ جای پنجرۀ کامل را می‌گرفت و ۵۸۸ نمادِ
    # معامله‌شده از پنج فیلتر بیرون می‌ماندند — جدول ۸۱ بج می‌داد در برابرِ
    # ۱۰۲ بجِ خودِ سایت. دو حالت رد:
    #   ۱) همان نشست با پوششِ کمتر → دادهٔ ناقص دادهٔ کهنه را نمی‌بَرَد؛
    #   ۲) نشستِ تازه‌تر ولی زیرِ کفِ پوشش، در حالی که پنجرۀ فعلی بالای کف است
    #      → تازگیِ یک نشست ارزشِ خاموش‌کردنِ صدها نماد را ندارد.
    if have:
        cur = conn.cursor()
        cur.execute("CREATE TEMP TABLE _new_window (ins_code TEXT PRIMARY KEY)")
        cur.executemany("INSERT OR IGNORE INTO _new_window VALUES (?)",
                        [(r[0],) for r in recs])
        traded_n, covered_new, covered_cur = cur.execute(
            "SELECT COUNT(*),"
            " SUM(CASE WHEN EXISTS (SELECT 1 FROM _new_window w WHERE w.ins_code = m.ins_code)"
            "          THEN 1 ELSE 0 END),"
            f" SUM(CASE WHEN EXISTS (SELECT 1 FROM {TAPE_HIST_TABLE} h WHERE h.ins_code = m.ins_code)"
            "          THEN 1 ELSE 0 END)"
            " FROM market_watch m WHERE m.d_even = ? AND COALESCE(m.q_tot_tran, 0) > 0",
            (board_day,)).fetchone()
        cur.execute("DROP TABLE _new_window")
        traded_n = traded_n or 0
        if traded_n:
            ratio_new = (covered_new or 0) / traded_n
            ratio_cur = (covered_cur or 0) / traded_n
            if top <= (newest or 0) and (covered_new or 0) < (covered_cur or 0):
                lost = (covered_cur or 0) - (covered_new or 0)
                conn.execute("UPDATE tape_history_state SET note = ? WHERE id = 1",
                             (f"partial-payload:{lost}",))
                conn.commit()
                print(f"  [tape-history] پاسخِ سایت {lost:,} نمادِ معامله‌شده را ندارد که "
                      f"پنجرۀ فعلی دارد — پنجره دست‌نخورده ماند")
                return {"skipped": "partial-payload", "lost": lost}
            if (top > (newest or 0) and ratio_new < TAPE_COVER_MIN
                    and ratio_cur >= TAPE_COVER_MIN):
                conn.execute("UPDATE tape_history_state SET note = ? WHERE id = 1",
                             ("partial-payload:collapse",))
                conn.commit()
                print(f"  [tape-history] نشستِ تازه آمد ولی پوشش به "
                      f"{ratio_new * 100:.1f}٪ افتاد (پنجرۀ فعلی {ratio_cur * 100:.1f}٪) — "
                      f"پنجرۀ کاملِ فعلی ماند")
                return {"skipped": "partial-payload", "lost": covered_cur}
    c = conn.cursor()
    c.execute(f"DELETE FROM {TAPE_HIST_TABLE}")
    c.executemany(_TAPE_HIST_INSERT, recs)
    c.execute(f"INSERT OR REPLACE INTO {TAPE_HIST_STATE} VALUES (1, ?, ?, ?, ?)",
              (now_txt, now_txt, top, ""))
    conn.commit()
    print(f"  [tape-history] {len(recs):,} ردیفِ [ih] از سایت (نشست تا {top})")
    return {"rows": len(recs), "newest": top}


def fetch_paper_types(getter, label="paperTypes"):
    """نقشهٔ ins_code → paperType. طبقهٔ ابزار از نام/سکتور ساخته نمی‌شود:
    اختیارجِ یک صندوق همان sector_code=68 صندوق را دارد، پس بدون این نقشه
    ردیف‌های «ص.اهرمی/طلا/نقره» و «سهام و حق تقدم» درست درنمی‌آیند.
    فقط ۴ طبقهٔ لازم گرفته می‌شود (۱،۲ سهام / ۴ حق تقدم / ۸ صندوق)؛ بقیه
    (اختیار، صکوک، سلف، آتی) در هیچ سطرِ جدول خلاصه نیستند و لازم نیست.

    getter(url) خودش کلید JSON («marketwatch») را می‌داند؛ پیش‌تر همین برچسب
    به‌جای کلید رد می‌شد و نقشه همیشه خالی برمی‌گشت (Paper-type map: 0).
    """
    out = {}
    # v9.10.2 — TSETMC یک ابزار را می‌تواند زیرِ چندین paperType برگرداند:
    # بسیاری از صندوق‌ها (و برخی اوراق) در پاسخِ pt=1، همان فهرستِ سهام، هم
    # می‌آیند. نسخهٔ پیشین نخستینِ طبقه‌ای را که می‌دید پیاده می‌کرد و چون
    # pt=1 اول می‌آمد، آن‌ها برای همیشه سهام می‌ماندند — در نتیجه سطرهای
    # «ص.سهامی/درآمد ثابت/اهرمی/طلا» همگی صفر می‌شدند و «سهام و حق تقدم»
    # سه برابرِ واقعی. اکنون خاص‌ترین طبقه برنده می‌شود: ۸ (صندوق) > ۴
    # (حق تقدم) > ۲/۱ (سهام). خواندن هم‌چنان از pt=1 شروع می‌شود تا اگر
    # ابزاری فقط آن‌جاست، سهامِ ساده بماند.
    rank = {8: 3, 4: 2, 2: 1, 1: 1}
    for pt in (1, 2, 4, 8):
        try:
            rows = getter(f"{BASE}/ClosingPrice/GetMarketWatch?market=0"
                          f"&paperTypes[0]={pt}&showTraded=false"
                          "&withBestLimits=false&hEven=0") or []
        except Exception as e:
            print(f"  WARN: paperType {pt} failed ({e})")
            rows = []
        for x in rows:
            ic = x.get("insCode")
            if not ic:
                continue
            # v9.8.2 — TSETMC قراردادهای اختیار را در پاسخِ paperType=1 (همان
            # فهرستِ سهام) هم می‌فرستد. آن‌ها را ثبت نمی‌کنیم تا paper_type شان
            # NULL بماند و در mstat_engine.classify به‌جای سهام، «other» شوند
            # (همانند mstat_engine.is_option). وگرنه حجمِ خردِ اختیارها جدولِ
            # الگوی ساعت و تجمیعِ حجمِ سهام را آلوده می‌کرد.
            nm = (x.get("lvc") or "") + " " + (x.get("lva") or "")
            if "اختيار" in nm or "اختیار" in nm:
                continue
            cur = out.get(ic)
            if cur is None or rank[pt] > rank[cur]:
                out[ic] = pt
    return out



def nfmt(n):
    """Latin digits with thousands separators."""
    try:
        return f"{n:,}"
    except (TypeError, ValueError):
        return str(n)


def write_status(stage, detail=""):
    """Lightweight progress channel for the live sync indicator in dashboard.py.
    FIX: فقط به market_sync.json بنویس — نه sync_status.json مشترک (کدال هم آنجا مینویسد؛
    تداخل باعث میشد بازار آخرین نوشته را پاک کند و UI فکر کند کدال تمام شد!)."""
    try:
        import json as _json
        tmp = MARKET_STATUS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            _json.dump({"stage": stage, "detail": detail,
                        "ts": datetime.datetime.now().isoformat(timespec="seconds")},
                       f, ensure_ascii=False)
        os.replace(tmp, MARKET_STATUS_PATH)
    except Exception:
        pass


_TSETMC_START = None


def write_progress(phase, detail, total=0, current=0, symbol=""):
    """Granular, real-time progress channel for the bootstrap loading screen.

    Writes the same sync_status.json file Codal-style readers consume, but with
    rich fields (phase / total / current / symbol / elapsed / percent) so the
    dashboard can render a live progress bar, ETA, and current-symbol text."""
    global _TSETMC_START
    try:
        import json as _json
        if _TSETMC_START is None:
            _TSETMC_START = datetime.datetime.now()
        elapsed = (datetime.datetime.now() - _TSETMC_START).total_seconds()
        percent = round(100.0 * current / total, 1) if total else 0.0
        tmp = MARKET_STATUS_PATH + ".tmp"
        payload = {
            "stage": "tsetmc", "phase": phase, "detail": detail,
            "total": int(total), "current": int(current), "symbol": symbol,
            "elapsed": round(elapsed, 1), "percent": percent,
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        with open(tmp, "w", encoding="utf-8") as f:
            _json.dump(payload, f, ensure_ascii=False)
        os.replace(tmp, MARKET_STATUS_PATH)
        # (فقط market_sync.json — نه sync_status.json مشترک با کدال)
    except Exception:
        pass


def num(v):
    """Safe float conversion."""
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def make_session(min_interval=0.05, cooldown_fn=None):
    """Polite TSETMC session — for users WITHOUT ADB/IP rotation.

    - min_interval: حداقل فاصلهٔ بین درخواستها (پیشفرض 0.05s = تا 20 req/s؛ پروب 09-01: 22/s بدون 429)
    - 429 → cooldown escalation: 60s → 300s → 600s (با خواندن Retry-After)
    - جیتر کوچک برای طبیعی شدن burst
    - cooldown_fn(seconds) اختیاری: هشدار/لاگ خارجی (UI)
    """
    s = requests.Session()
    retry = Retry(
        connect=3, read=3, status=3,
        backoff_factor=1.5,
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s._polite = {
        "min_interval": float(min_interval),
        "last": 0.0,
        "lock": None,
        "cooldown": 0.0,
        "cooldown_level": 0,
        "cooldown_fn": cooldown_fn,
    }
    try:
        import threading
        s._polite["lock"] = threading.Lock()
    except Exception:
        s._polite["lock"] = None
    return s


def _rate_wait(s):
    """قفل + فاصلهٔ زندهٔ بین درخواستها (بدون پیچیدگی JSON — برای هر endpoint)."""
    p = s._polite if hasattr(s, "_polite") else None
    if not p:
        return
    import random
    import time as _t
    p["min_interval"] = max(0.0, float(p.get("min_interval", 0.25)))
    now = _t.monotonic()
    if p["lock"]:
        with p["lock"]:
            wait = p["last"] + p["min_interval"] - now + random.uniform(0, p["min_interval"] * 0.4)
            if wait > 0:
                _t.sleep(wait)
            p["last"] = _t.monotonic()


def polite_get(s, url, key=None, timeout=90):
    """Rate-limited GET با محافظ 429. استثنا در 429 پس از ۳ تلاش/۳ پله: با retry سقف کند اما بدون 429 پشتسرهم."""
    import random
    import time as _t
    p = s._polite if hasattr(s, "_polite") else None
    if p:
        _rate_wait(s)
        attempt = 0
        while True:
            if p["cooldown"] > _t.monotonic():
                _t.sleep(min(p["cooldown"] - _t.monotonic(), 600))
            try:
                r = s.get(url, headers=HEADERS, timeout=timeout, stream=True)
            except (requests.exceptions.RequestException, OSError, PermissionError) as e:
                print(f"  [warning] TSETMC fetch failed ({type(e).__name__}): {e}")
                return [] if key else None
            if r.status_code != 429:
                p["cooldown_level"] = 0
                if r.status_code >= 500:
                    print(f"  [warning] TSETMC {r.status_code} — تلاش مجدد …")
                    _t.sleep(2)
                    attempt += 1
                    if attempt >= 3:
                        return [] if key else None
                    continue
                try:
                    r.raise_for_status()
                except Exception:
                    return [] if key else None
                return r.json().get(key) if key else r.json()
            # 429:
            p["cooldown_level"] = min(p["cooldown_level"] + 1, 3)
            ra = r.headers.get("Retry-After")
            levels = (60, 300, 600)
            cd = float(ra) if ra and ra.isdigit() else levels[p["cooldown_level"] - 1]
            p["cooldown"] = _t.monotonic() + cd
            if p.get("cooldown_fn"):
                try:
                    p["cooldown_fn"](cd)
                except Exception:
                    pass
            print(f"  [cooldown] 429 — {int(cd)}s (level {p['cooldown_level']}) …")
            if p["cooldown_level"] >= 3:
                return [] if key else None
            _t.sleep(cd)
    # بدون _polite (session قدیمی)
    return get_json(s, url, key)


def get_json(s, url, key):
    """پایهٔ قدیمی (بدون rate limit) — برای سازگار retry فکنیک قبلی؛ اصلی هم _polite_get است."""
    try:
        r = s.get(url, headers=HEADERS, timeout=90)
        r.raise_for_status()
        return r.json().get(key) or []
    except (requests.exceptions.RequestException, OSError, PermissionError) as e:
        # WinError 10013 / ConnectTimeoutError / DNS — fail gracefully: console
        # warning + empty result so the worker exits cleanly, never a traceback.
        print(f"  [warning] TSETMC fetch failed ({type(e).__name__}): {e}")
        return []


# ════════════════════════════════════════════════════════════════════════════
# P0 — سه خانوادۀ داده که تا این دور canonical نبودند
#   P0-1  ارزشِ ریالیِ حقیقی/حقوقی (مبدأ، نه حجم×VWAP)
#   P0-2  رویدادهایِ شرکتیِ منتشرشده (تعدیلِ قیمت / تغییرِ تعدادِ سهام)
#   P0-3  وضعیتِ نماد / علتِ توقف / نظارت / پیامِ ناظر
# سه حکمِ مشترک:
#   ۱) مبدأ نباشد ⇒ **هیچ چیز نمی‌نویسیم**. نبودِ ردیف خودش داوری است
#      («بازسازی به‌کار رفت») و جای آن صفرِ جعلی نمی‌نشیند.
#   ۲) هر ردیف `source` دارد؛ مصرف‌کننده از همان می‌فهمد عدد مبدأ است یا مشتق.
#   ۳) هیچ‌کدام در حلقۀ ۹۰ ثانیه‌ای نیستند: با throttle و بودجهٔ درخواست
#      اجرا می‌شوند (الگوی refresh_tape_history).
# ════════════════════════════════════════════════════════════════════════════
CTV_SOURCE = "tsetmc_clienttype_history"
CTV_RETRY_S = 6 * 3600      # سقفِ تلاش برایِ یک نشست (الگوی TAPE_HIST_RETRY_S)
CTV_BUDGET = 600            # حداکثرِ درخواست در هر اجرا

# DDL درِ tsetmc_p0_schema است؛ این نام فقط برایِ سازگاریِ فراخوانی‌هایِ موجود
import tsetmc_p0_schema as _P0
CTV_TABLE_DDL = _P0.CLIENT_TYPE_VALUE


def ensure_client_type_value_schema(conn):
    """میزِ ارزشِ مبدأ و حالتِ آن (DDL از tsetmc_p0_schema — تک‌منبع)."""
    import tsetmc_p0_schema as P0
    conn.execute(P0.CLIENT_TYPE_VALUE)
    conn.execute(P0.CLIENT_TYPE_VALUE_STATE)
    conn.execute("INSERT OR IGNORE INTO client_type_value_state"
                 " (id, last_attempt, last_ok, newest_d_even, note) VALUES (1, NULL, NULL, 0, NULL)")


def ct_universe_sql():
    """دامنهٔ بودجه‌دار: نمادهایی که مبدأ برایِ آن نشست «جریان» گزارش کرده.

    این انتخابِ دامنهٔ فیلتر نیست — همان مجموعه‌ای که `client_type` برایِ همان
    نشست ذخیره کرده، فقط به ترتیبِ نزولیِ مجموعِ حجم و با سقفِ درخواست. نمادی
    که بیرونِ بودجه می‌ماند ردیفی در `client_type_value` ندارد و مصرف‌کننده
    همان بازسازیِ پیشین را با `value_source='reconstructed'` می‌خواند.
    """
    return ("SELECT ins_code FROM client_type WHERE d_even = ? "
            "AND (COALESCE(buy_i_vol,0)+COALESCE(buy_n_vol,0)"
            "     +COALESCE(sell_i_vol,0)+COALESCE(sell_n_vol,0)) > 0 "
            "ORDER BY (COALESCE(buy_i_vol,0)+COALESCE(buy_n_vol,0)"
            "         +COALESCE(sell_i_vol,0)+COALESCE(sell_n_vol,0)) DESC, ins_code "
            "LIMIT ?")


def parse_client_type_value(payload, ins_code, d_even, now=None):
    """پاسخِ GetClientTypeHistory → یک ردیفِ canonical، یا None.

    `clientType` یک **شیء** است نه آرایه (سنجشِ زنده؛ fima هم با
    `[resp['clientType']]` همین را می‌پیچد). سه شکلِ ورودی پذیرفته می‌شود:
    `{"clientType": {...}}`، خودِ `{...}`ِ بی‌wrapper، و `[{...}]`.
    هیچ‌وقت صفر نمی‌سازیم: اگر هیچ‌کدام از چهار ارزشِ ریالی عدد نبود، None
    برمی‌گردد و نویسنده ردیفی نمی‌نویسد — نبودِ ردیف خودش داوری است.
    """
    if isinstance(payload, list):
        payload = payload[0] if payload and isinstance(payload[0], dict) else None
    if not isinstance(payload, dict):
        return None
    row = payload.get("clientType", payload)
    if isinstance(row, list):
        row = row[0] if row and isinstance(row[0], dict) else None
    if not isinstance(row, dict):
        return None
    vals = [num(row.get(k)) for k in ("buy_I_Value", "buy_N_Value",
                                      "sell_I_Value", "sell_N_Value")]
    if all(v is None for v in vals):
        return None
    # «native» فقط وقتی هر چهار ارزش آمده‌اند؛ وگرنه «mixed» (بعضی خانۀ خالی).
    # «reconstructed» اینجا نوشته نمی‌شود چون ردیفی وجود ندارد که برچسب بگیرد —
    # نبودِ ردیف خودش همان داوری است. یک‌بار درِ نویسنده حساب می‌شود تا
    # مصرف‌کننده‌ها (SQL/UI) provenance را دوباره نسازند.
    kind = "native" if all(v is not None for v in vals) else "mixed"
    rec_date = num(row.get("recDate"))
    return (ins_code, int(rec_date or d_even), vals[0], vals[1], vals[2], vals[3],
            num(row.get("buy_DDD_Value")), kind, now or "", CTV_SOURCE)


def refresh_client_type_values(conn, day=None, limit=CTV_BUDGET, force=False,
                               session=None, fetch=None, now=None):
    """ارزشِ مبدأ را برایِ یک نشستِ بسته پر می‌کند. برمی‌گرداند dictِ آمار.

    رفتارِ دیدہ‌شده (۱۴۵-۰-۱۳): نشستِ جاری HTTP 500 می‌دهد، نشست‌هایِ بسته تا
    `20260701` برمی‌گردند. پس ۵۰۰ «خطا» نیست و بوقِ خطا هم نمی‌زند؛ فقط ردیفی
    نوشته نمی‌شود و provenance مصرف‌کننده رویِ `reconstructed` می‌ماند.
    """
    now = now or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ensure_client_type_value_schema(conn)
    st = conn.execute("SELECT last_attempt, newest_d_even FROM client_type_value_state"
                      " WHERE id=1").fetchone()
    if day is None:
        day = conn.execute("SELECT MAX(d_even) FROM client_type").fetchone()[0] or 0
    if not day:
        return {"skipped": "no-session", "written": 0}
    have = conn.execute("SELECT COUNT(*) FROM client_type_value WHERE d_even=?",
                        (day,)).fetchone()[0]
    want = conn.execute("SELECT COUNT(*) FROM client_type WHERE d_even=?",
                        (day,)).fetchone()[0]
    if want and have >= want:
        return {"skipped": "complete", "day": day, "written": have}
    if not force and st and st[0]:
        try:
            age = (datetime.datetime.now()
                   - datetime.datetime.strptime(st[0], "%Y-%m-%d %H:%M:%S")).total_seconds()
        except ValueError:
            age = CTV_RETRY_S + 1.0
        if age < CTV_RETRY_S:
            return {"skipped": "throttled", "day": day, "written": have}
    conn.execute("UPDATE client_type_value_state SET last_attempt=? WHERE id=1", (now,))
    conn.commit()
    done = {r[0] for r in conn.execute(
        "SELECT ins_code FROM client_type_value WHERE d_even=?", (day,)).fetchall()}
    todo = [r[0] for r in conn.execute(ct_universe_sql(), (day, int(limit))).fetchall()
            if r[0] not in done]
    if fetch is None:
        s = session or make_session()

        def fetch(c, _s=s, _day=day):
            # `clientType` شیء است؛ polite_get با key همان شیء را بی‌change می‌دهد
            return polite_get(_s, f"{BASE}/ClientType/GetClientTypeHistory/{c}/{_day}",
                              "clientType")
    rows, errs = [], 0
    for c in todo:
        try:
            payload = fetch(c)
        except Exception:
            payload, errs = None, errs + 1
            continue
        rec = parse_client_type_value(payload, c, day, now)
        if rec:
            rows.append(rec)
    if rows:
        # نوشتنِ نام‌دار: `kind` بعداً با ALTER اضافه شد و به انتهای
        # جدول چسبید، پس ترتیبِ tupleِ ما با ترتیبِ ستون‌هایِ بانک یکی
        # نیست (نوشتنِ جایگاهی kind را درِ source می‌نشاند).
        conn.executemany(
            "INSERT OR REPLACE INTO client_type_value (ins_code, d_even,"
            " buy_i_val, buy_n_val, sell_i_val, sell_n_val, buy_ddd_val,"
            " kind, fetched_at, source) VALUES ("
            + ",".join("?" * 10) + ")", rows)
    total = conn.execute("SELECT COUNT(*) FROM client_type_value WHERE d_even=?",
                         (day,)).fetchone()[0]
    conn.execute("UPDATE client_type_value_state SET last_ok=?, newest_d_even=?,"
                 " note=? WHERE id=1",
                 (now if rows else st[1] if st else None, day,
                  f"day={day} written={len(rows)} total={total} errors={errs}"))
    conn.commit()
    market_state_touch()
    return {"day": day, "written": len(rows), "total": total, "errors": errs,
            "attempted": len(todo)}


def market_state_touch():
    """به لایۀ داغ خبر می‌دهد که «یک نویسندۀ ایستا چیزی عوض کرد».

    بی‌این، تابلو از RAMِ بی‌تغییر می‌خواند و ردیف‌هایِ تازه بی‌صدا دیده
    نمی‌شوند — همان شکلی که `refresh_tape_history` با `note_static_change`
    جلوی‌اش را می‌گیرد.
    """
    try:
        import market_state
        market_state.note_static_change()
    except Exception:
        pass


P0_STATE_DDL = ("CREATE TABLE IF NOT EXISTS tsetmc_p0_state ("
                " name TEXT PRIMARY KEY, last_run TEXT)")


def p0_due(conn, name, every_s, now=None):
    """آیا این خانوادۀ P0 باید حالا اجرا شود؟ (throttleٔ مشترک، state در بانک).

    بانکِ بی‌ردیف = «هرگز اجرا نشده» = وقتش رسیده. بی‌this، اولین اجرای بعد از
    ارتقا هیچ‌وقت رخ نمی‌داد.
    """
    conn.execute(P0_STATE_DDL)
    row = conn.execute("SELECT last_run FROM tsetmc_p0_state WHERE name=?",
                       (name,)).fetchone()
    if not row or not row[0]:
        return True
    try:
        age = (datetime.datetime.now()
               - datetime.datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")).total_seconds()
    except ValueError:
        return True
    return age >= every_s


def p0_mark(conn, name, now=None):
    conn.execute(P0_STATE_DDL)
    conn.execute("INSERT OR REPLACE INTO tsetmc_p0_state(name, last_run) VALUES (?,?)",
                 (name, now or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))


def p0_summarize(name, stats):
    """خلاصۀ یک‌سطری برایِ لاگ — هیچ عددی را از خود نمی‌سازد، فقط echo."""
    if not isinstance(stats, dict):
        return ""
    keys = {"corporate-events": ("adjust", "share", "failed"),
            "state-notices": ("state", "messages", "supervision", "stops", "failed"),
            "client-values": ("written", "total", "errors", "skipped")}.get(name, ())
    return " ".join(f"{k}={stats[k]}" for k in keys if k in stats)


CORP_ADJ_SOURCE = "tsetmc_price_adjust_by_flow"
CORP_SHARE_SOURCE = "tsetmc_share_change_by_flow"
CORP_SIZE = 500        # سقفِ ردیفِ هر flow در هر اجرا (عددِ خودِ مبدأ بزرگ است)
CORP_DAYS = 14         # پنجرۀ تغییرِ سهام: روز


def parse_price_adjust(rows, now=None):
    """`priceAdjust[]` → ردیف‌هایِ price_adjust_events.

    دو عددِ مبدأ که تا پیش از این «درِ فید نیست» خوانده می‌شدند:
    `pClosing` (پایانیِ تعدیل‌شده) و `pClosingNotAdjusted` (پایانیِ خام).
    `ratio` مشتق است و درِ همان ستون با `source`ِ جداگانه می‌نشیند.
    `corporateTypeCode` را **decode نمی‌کنیم** — هیچ منبعی معنایش را نگفته؛
    فقط همان عددِ خام ذخیره می‌شود.
    """
    out = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        ins = r.get("insCode") or (r.get("instrument") or {}).get("insCode")
        d = num(r.get("dEven"))
        adj, raw = num(r.get("pClosing")), num(r.get("pClosingNotAdjusted"))
        if not ins or not d:
            continue
        ratio = round(adj / raw, 8) if (adj and raw) else None
        inst = r.get("instrument") or {}
        out.append((str(ins), int(d), inst.get("lVal18AFC") or r.get("lVal18AFC"),
                    adj, raw, r.get("corporateTypeCode"), ratio,
                    CORP_ADJ_SOURCE, now or ""))
    return out


def parse_share_change(rows, now=None):
    """`instrumentShareChange[]` → ردیف‌هایِ share_change_events.

    `numberOfShareOld/New` مبدأ‌اند؛ `ratio = old/new` همان قاعدۀ همیشگیِ
    ضریبِ سهام است (ORBO: `factor_share = numberOfShareOld / numberOfShareNew`)
    و مشتق شمرده می‌شود.
    """
    out = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        ins, d = r.get("insCode"), num(r.get("dEven"))
        old, new = num(r.get("numberOfShareOld")), num(r.get("numberOfShareNew"))
        if not ins or not d:
            continue
        ratio = round(old / new, 8) if (old and new) else None
        out.append((str(ins), int(d), r.get("lVal18AFC"), old, new, ratio,
                    CORP_SHARE_SOURCE, now or ""))
    return out


def ensure_corporate_schema(conn):
    import tsetmc_p0_schema as P0
    conn.execute(P0.PRICE_ADJUST_EVENTS)
    conn.execute(P0.SHARE_CHANGE_EVENTS)


def fetch_corporate_events(s, conn, now=None, get=None):
    """هر دو خانوادۀ رویداد، بازارِ کامل، در چهار درخواست.

    `GetPriceAdjustByFlow/{flow}/{size}` و
    `GetInstrumentShareChangeByFlow/{flow}/{days}` با flow=1 (بورس) و flow=2
    (فرابورس) — همان الگویِ fan-out که fima هم دارد. بی‌پاسخ = بی‌نوشتن؛
    نوشتنِ «رویدادی نبود» برایِ رویدادی که فقط پاسخ نگرفته، جعلِ داوری است.
    """
    now = now or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ensure_corporate_schema(conn)
    get = get or (lambda u, k: polite_get(s, u, k))
    stats = {"adjust": 0, "share": 0, "failed": 0}
    adj, shr = [], []
    for flow in (1, 2):
        try:
            adj += parse_price_adjust(
                get(f"{BASE}/ClosingPrice/GetPriceAdjustByFlow/{flow}/{CORP_SIZE}",
                    "priceAdjust"), now) or []
        except Exception:
            stats["failed"] += 1
        try:
            shr += parse_share_change(
                get(f"{BASE}/Instrument/GetInstrumentShareChangeByFlow/{flow}/{CORP_DAYS}",
                    "instrumentShareChange"), now) or []
        except Exception:
            stats["failed"] += 1
    # کلیدِ هر دو جدول (ins_code, d_even) است؛ اگر مبدأ یک رویداد را درِ هر دو
    # flow نشان بدهد، بی‌dedupe شمارشِ لاگ دو‌برابرِ ردیفِ بانک می‌شد.
    adj = list({(r[0], r[1]): r for r in adj}.values())
    shr = list({(r[0], r[1]): r for r in shr}.values())
    if adj:
        conn.executemany("INSERT OR REPLACE INTO price_adjust_events VALUES ("
                         + ",".join("?" * 9) + ")", adj)
    if shr:
        conn.executemany("INSERT OR REPLACE INTO share_change_events VALUES ("
                         + ",".join("?" * 8) + ")", shr)
    conn.commit()
    stats.update(adjust=len(adj), share=len(shr))
    if adj or shr:
        market_state_touch()
    return stats


STATE_SOURCE = "tsetmc_instrument_state_top"
MSG_SOURCE = "tsetmc_msg_by_flow"
SUPERVISION_SOURCE = "tsetmc_supervision_list"
STOP_SOURCE = "webgw_company_state"
STATE_TOP_N = 500
MSG_TOP_N = 300
SUPERVISION_SOURCES = ((1, (1, 2, 3)), (2, (1, 2, 3)))


def parse_instrument_state(rows, now=None):
    out = []
    for r in rows or []:
        if not isinstance(r, dict) or not r.get("insCode"):
            continue
        d, h = num(r.get("dEven")), num(r.get("hEven"))
        out.append((str(r["insCode"]), int(d or 0),
                    (r.get("cEtaval") or "").strip() or None, r.get("cEtavalTitle"),
                    num(r.get("underSupervision")), int(h or 0),
                    num(r.get("realHeven")), STATE_SOURCE, now or ""))
    return out


def parse_messages(rows, flow, now=None):
    out = []
    for r in rows or []:
        if not isinstance(r, dict) or r.get("tseMsgIdn") is None:
            continue
        out.append((int(r["tseMsgIdn"]), num(r.get("dEven")), num(r.get("hEven")),
                    num(r.get("flow")) if r.get("flow") is not None else flow,
                    (r.get("tseTitle") or "").strip() or None,
                    (r.get("tseDesc") or "").strip() or None,
                    MSG_SOURCE, now or ""))
    return out


def split_supervision_reasons(reasons):
    """`reasons` رشته‌ای است با جداکنندۀ `<br>` (همان که fima explode می‌کند).

    بی‌decode نمی‌گذاریم که `<br>` درِ UI دیده شود؛ به فهرستِ متنی تبدیل و با
    `\n` ذخیره می‌شود، و `reason_count` هم می‌نشیند.
    """
    parts = [p.strip() for p in re.split(r"<br\s*/?>", reasons or "") if p.strip()]
    return "\n".join(parts), len(parts)


def parse_supervision(payloads, now=None):
    """`{source_id: {list_index: supervision[]}}` → ردیف‌هایِ supervision_state.

    سنجشِ زنده: `id=0`، `userName=null`، `insertionDateTime=0001-01-01` — پس
    این فهرست تاریخچه نیست، وضعیتِ فعلی است و کلِ جدول هر اجرا عوض می‌شود.
    """
    out = {}
    for sid, lists in (payloads or {}).items():
        for idx, rows in (lists or {}).items():
            for r in rows or []:
                if not isinstance(r, dict) or not r.get("insCode"):
                    continue
                ins = str(r["insCode"])
                text, n = split_supervision_reasons(r.get("reasons"))
                title = r.get("underSupervisionTitle")
                cur = out.get(ins)
                # یک نماد می‌تواند در چند فهرست بیاید؛ دلیل‌ها را یکی می‌کنیم
                if cur and cur[5]:
                    merged = cur[5] + ("\n" + text if text and text not in cur[5] else "")
                    n = len([x for x in merged.split("\n") if x])
                    out[ins] = (ins, sid, idx, num(r.get("underSupervision")),
                                title or cur[4], merged, n, SUPERVISION_SOURCE, now or "")
                else:
                    out[ins] = (ins, sid, idx, num(r.get("underSupervision")),
                                title, text, n, SUPERVISION_SOURCE, now or "")
    return list(out.values())


def fold_persian(s):
    """عربى/فارسی را یکی می‌کند تا پیوندِ نماد بی‌صدا نشکند.

    سنجشِ زنده: `instruments.l_val18` برخی نمادها را با ي/ک عربی نگه می‌دارد
    («وامید»، «شبریز») و پاسخِ webgw همان نماد را با ی/ک فارسی می‌فرستد. بی‌این
    تا، ۳۷ ردیف از ۵۲ ردیفِ «علت توقف» بی‌صدا دور ریخته می‌شد.
    """
    return (s or "").replace("\u064a", "\u06cc").replace("\u0643", "\u06a9").strip()


def parse_stop_reasons(items, now=None):
    """webgw `CompanyState/fa` → علتِ توقف.

    کلیدِ این پاسخ `nam` است و شکلش «نماد(نامِ کامل)» — نه insCode و نه ISIN
    (سنجشِ زنده: ۵۲ ردیف، `kodenamaddarsamane` همیشه null). پس پیشوندِ قبل از
    «(» همان `l_val18` است؛ نمادی که درِ `instruments` نباشد ذخیره **نمی‌شود**،
    چون بی‌کلیدِ پایدار، اتصالِ بعدی حدسی می‌شود.
    """
    out = []
    for r in items or []:
        if not isinstance(r, dict):
            continue
        raw = (r.get("nam") or "").strip()
        sym = re.split(r"[（(]", raw)[0].strip()
        if not sym:
            continue
        dalils = r.get("dalils")
        if isinstance(dalils, (list, tuple)):
            dalils = "\n".join(str(x).strip() for x in dalils if str(x).strip())
        out.append((sym, num(r.get("statusCode")), (r.get("vaziyatdesc") or "").strip() or None,
                    (r.get("lastdatechange") or "").strip() or None,
                    (dalils or "").strip() or None, STOP_SOURCE, now or ""))
    return out


def ensure_state_schema(conn):
    import tsetmc_p0_schema as P0
    for ddl in (P0.INSTRUMENT_STATE, P0.STOP_REASONS, P0.SUPERVISION_STATE,
                P0.TSETMC_MESSAGES):
        conn.execute(ddl)


def fetch_state_and_notices(s, conn, now=None, get=None, webgw=None):
    """وضعیتِ نماد + پیام‌هایِ ناظر + نظارت + (اختیاری) علتِ توقف.

    `webgw` تابعی است که فراخوانی‌اش اختیاری است: از IPِ غیرایرانی بلاک است و
    اگر نبود، فقط «علتِ توقف» نمی‌آید — بقیه از CDN می‌آیند. هیچ‌کدام از این‌ها
    منبعِ FTS نیستند و هیچ داوری را عوض نمی‌کنند.
    """
    now = now or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ensure_state_schema(conn)
    get = get or (lambda u, k: polite_get(s, u, k))
    stats = {"state": 0, "messages": 0, "supervision": 0, "stops": 0, "failed": 0}
    try:
        rows = parse_instrument_state(
            get(f"{BASE}/MarketData/GetInstrumentStateTop/{STATE_TOP_N}",
                "instrumentState"), now)
        conn.executemany("INSERT OR REPLACE INTO instrument_state VALUES ("
                         + ",".join("?" * 9) + ")", rows)
        stats["state"] = len(rows)
    except Exception:
        stats["failed"] += 1
    msgs = []
    for flow in (1, 2):
        try:
            msgs += parse_messages(get(f"{BASE}/Msg/GetMsgByFlow/{flow}/{MSG_TOP_N}",
                                       "msg"), flow, now) or []
        except Exception:
            stats["failed"] += 1
    # یک پیام ممکن است درِ هر دو flow بیاید (flow=0 درِ خودِ پاسخ)؛ کلیدِ واقعی
    # tseMsgIdn است، پس بی‌dedupe شمارشِ ما بیشتر ازِ ردیفِ بانک می‌شد.
    uniq = {m[0]: m for m in msgs}
    msgs = list(uniq.values())
    if msgs:
        conn.executemany("INSERT OR REPLACE INTO tsetmc_messages VALUES ("
                         + ",".join("?" * 8) + ")", msgs)
        stats["messages"] = len(msgs)
    sup = {}
    for sid, idxs in SUPERVISION_SOURCES:
        for idx in idxs:
            try:
                sup.setdefault(sid, {})[idx] = get(
                    f"{BASE}/Supervision/GetSupervisionListBySourceID/{sid}/{idx}",
                    "supervision")
            except Exception:
                stats["failed"] += 1
    srows = parse_supervision(sup, now)
    if srows:
        conn.execute("DELETE FROM supervision_state")   # snapshot، نه تاریخچه
        conn.executemany("INSERT OR REPLACE INTO supervision_state VALUES ("
                         + ",".join("?" * 9) + ")", srows)
        stats["supervision"] = len(srows)
    if webgw is not None:
        try:
            stops = parse_stop_reasons(webgw(), now)
            # پیوند با l_val18 روی هر دو طرف تا-خورده می‌خورد: بانک بعضی نمادها
            # را با ي/ک عربی نگه داشته و webgw همان‌ها را با ی/ک فارسی می‌فرستد.
            known = {fold_persian(r[0]): r[0] for r in
                     conn.execute("SELECT l_val18 FROM instruments")}
            stops = [(known[fold_persian(t[0])],) + t[1:] for t in stops
                     if fold_persian(t[0]) in known]
            if stops:
                conn.execute("DELETE FROM stop_reasons")   # snapshotِ وضعیتِ فعلی
                conn.executemany("INSERT OR REPLACE INTO stop_reasons VALUES ("
                                 + ",".join("?" * 7) + ")", stops)
                stats["stops"] = len(stops)
        except Exception:
            stats["failed"] += 1
    conn.commit()
    if any(stats[k] for k in ("state", "messages", "supervision", "stops")):
        market_state_touch()
    return stats


def create_schema(conn):
    conn.executescript(
        """
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS instruments (
            ins_code TEXT PRIMARY KEY, l_val18 TEXT, l_val30 TEXT,
            sector_code TEXT, sector_name TEXT, total_shares REAL,
            eps REAL, pe REAL, base_vol REAL, updated_at TEXT,
            -- isin = کلیدِ خامِ `insID` درِ همان پاسخِ تابلو (سنژشِ زنده: هر ۳۸۴۷
            -- ردیف آن کلید را دارد). بی‌این هیچ مسیری به webgw (که با ISIN کلید
            -- می‌خورد) بسته نمی‌شود. c_gr_val_cot = گروهِ کالاییِ همان ردیف.
            -- paper_type اینجا نیست: آن را mstat_engine.MIGRATIONS می‌افزاید و
            -- تکرارش درِ DDL یعنی نوعِ ستون درِ بانکِ تازه با بانکِ ارتقایافته
            -- فرق کند (TEXT در برابرِ INTEGER).
            isin TEXT, c_gr_val_cot TEXT);
        -- l_val18 کلیدِ پیوندِ هر نماد است (financial_statements/monthly_sales/
        -- price_history همگی با آن join می‌شوند) ولی PK روی ins_code است؛ بدون
        -- این ایندکس، resolve() و bulk_scan مجبور به اسکنِ کاملِ ۵۱۲۹ ردیفی
        -- می‌شوند. Data-Lifecycle گام ۳۳.
        CREATE INDEX IF NOT EXISTS ix_instruments_lval18 ON instruments(l_val18);
        CREATE INDEX IF NOT EXISTS ix_instruments_lval30 ON instruments(l_val30);
        CREATE TABLE IF NOT EXISTS market_watch (
            ins_code TEXT PRIMARY KEY, d_even INTEGER, h_even INTEGER,
            p_closing REAL, p_last REAL, price_min REAL, price_max REAL,
            allowed_min REAL, allowed_max REAL, price_yesterday REAL,
            price_first REAL, q_tot_tran REAL, q_tot_cap REAL,
            z_tot_tran REAL, price_change REAL, eps REAL, pe REAL,
            total_shares REAL, sector_code TEXT, fetched_at TEXT,
            market_cap REAL, market_cap_src TEXT,
            flow INTEGER, p_red_tran REAL, buy_op REAL);
        CREATE TABLE IF NOT EXISTS daily_prices (
            ins_code TEXT, d_even INTEGER, p_closing REAL, price_min REAL,
            price_max REAL, price_yesterday REAL, price_first REAL,
            q_tot_tran REAL, q_tot_cap REAL, price_change REAL,
            fetched_at TEXT, market_cap REAL, market_cap_src TEXT,
            -- z_tot_tran = تعدادِ معاملات؛ قیدِ چهارمِ کف‌روبی (qd1) تنها از این
            -- خوانده می‌شود. درِ DDL هست تا بانکِ تازه با _DP_INSERT یکی بماند،
            -- و درِ ensure_daily_tran_column برایِ بانکِ قدیمی ALTER می‌زند.
            z_tot_tran REAL,
            -- p_last = «آخرین قیمت» (کلیدِ خامِ pdv درِ تابلو)؛ از «قیمت پایانی» جدا
            -- نگه داشته می‌شود تا کندلِ روزِ جاری هم هر دو مبنایِ نام‌دار را داشته باشد.
            p_last REAL,
            PRIMARY KEY (ins_code, d_even));
        CREATE TABLE IF NOT EXISTS client_type (
            ins_code TEXT, d_even INTEGER, buy_i_vol REAL, buy_n_vol REAL,
            buy_ddd_vol REAL, buy_count_i INTEGER, buy_count_n INTEGER,
            buy_count_ddd INTEGER, sell_i_vol REAL, sell_n_vol REAL,
            sell_count_i INTEGER, sell_count_n INTEGER, fetched_at TEXT,
            PRIMARY KEY (ins_code, d_even));
        CREATE TABLE IF NOT EXISTS boards (
            ins_code TEXT PRIMARY KEY, board INTEGER);
        CREATE TABLE IF NOT EXISTS price_history (
            symbol TEXT, date TEXT, open REAL, high REAL, low REAL,
            close REAL, volume REAL,
            -- close = «قیمت پایانی» (لنگرِ تعدیل)؛ last = «آخرین قیمت» (مبنایِ نمایش/محاسبه)
            -- value = گردشِ ریالیِ همان روز. هر دو nullable — ببینید mstat_engine.MIGRATIONS
            -- src = سازندۀ سطر (published | board | index-synthetic)؛ مالکیتِ نوشتن با
            -- همین ستون تعیین می‌شود (candle_contract.UPSERT_SQL).
            last REAL, value REAL, src TEXT, PRIMARY KEY (symbol, date));
        CREATE INDEX IF NOT EXISTS ix_daily_ins ON daily_prices(ins_code);
        -- پنج خطِ عمق، از blDsِ همان نشست. sathهای تابلو جمع و خطِ اول را در
        -- market_watch نگه می‌دارند؛ این جدولِ جدا تک‌تکِ سطرها را برایِ پنلِ
        -- «۵ مظنه» نگه می‌دارد. در create_schema هم ساخته می‌شود تا خواننده
        -- با «جدول نیست» روبه‌رو نشود، بلکه با «سطری هنوز ذخیره نشده».
        CREATE TABLE IF NOT EXISTS order_book (
            ins_code TEXT PRIMARY KEY, d_even INTEGER, h_even INTEGER,
            book_txt TEXT, updated_at TEXT);
        -- v9.7.5 فاز ۱ — تایم‌لاین درون‌روزی. market_watch کلید ins_code دارد و
        -- هر همگام‌سازی روی همان سطر می‌نویسد، پس «تاریخچهٔ لحظه‌ای» در آن ساختنی
        -- نیست. این جدول به‌ازای هر همگام‌سازی یک نقطهٔ تجمیعی نگه می‌دارد.
        CREATE TABLE IF NOT EXISTS mstat_snap (
            d_even INTEGER NOT NULL, h_even INTEGER NOT NULL,
            ts TEXT, agg TEXT, PRIMARY KEY (d_even, h_even));
        """
    )
    _migrate(conn)
    # v10: ستون ارزش بازار (بعد از _migrate، چون queue_cols این‌جا اضافه می‌شود)
    ensure_market_cap_schema(conn)
    ensure_tape_history_schema(conn)
    # DDL جدول‌های P0 درِ tsetmc_p0_schema است (تک‌منبع؛ همان را
    # mstat_engine.ensure_schema هم اجرا می‌کند)
    import tsetmc_p0_schema
    tsetmc_p0_schema.create_all(conn)
    conn.commit()


def _migrate(conn):
    """مهاجرتِ ستون‌ها — بدنه در mstat_engine است تا مسیرِ نوشتن و خواندن یک
    تعریف داشته باشند (تک‌منبع). این پوسته فقط برای سازگاریِ فراخوانی‌های موجود است."""
    import mstat_engine
    mstat_engine.ensure_schema(conn)


def write_summary(update):
    """Merge a run's results into sync_summary.json (read-modify-write, atomic).

    Each background worker writes only its own keys (e.g. symbols_updated) so the
    two processes never clobber each other's results."""
    try:
        import json as _json
        path = os.path.join(WORK_DIR, "sync_summary.json")
        data = {}
        try:
            with open(path, encoding="utf-8") as f:
                data = _json.load(f)
        except Exception:
            pass
        data.update(update)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            _json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        pass


def get_json(s, url, key):
    try:
        r = s.get(url, headers=HEADERS, timeout=90)
        r.raise_for_status()
        return r.json().get(key) or []
    except (requests.exceptions.RequestException, OSError, PermissionError) as e:
        # WinError 10013 / ConnectTimeoutError / DNS — fail gracefully: console
        # warning + empty result so the worker exits cleanly, never a traceback.
        print(f"  [warning] TSETMC fetch failed ({type(e).__name__}): {e}")
        return []


def _iso_from_deven(d_even):
    """20260929 (int/str) → '2026-09-29'؛ بی‌اعتبار → None."""
    s = str(d_even or "").strip()
    if len(s) != 8 or not s.isdigit():
        return None
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"


def candle_from_row(l_val18, d_even, first, high, low, close, vol, last=None, value=None):
    """یک ردیفِ تابلو → کندلِ price_history، یا None.

    از Step 4 این دیگر سازندۀ *دوم* نیست: همان `candle_contract.candle` صدا زده می‌شود
    (هندسه از `widen`، بدنه از «اولین»، پایانی خُرد نمی‌شود، روزِ بی‌معامله کندل نمی‌شود)
    و `src="board"` رویِ سطر می‌خورد تا مالکیتِ نوشتن معلوم باشد — پیش از این این
    مسیر با `INSERT OR REPLACE` بی‌اولویت، ردیفِ **منتشرشدهٔ** CSV را هم له می‌کرد
    (سنجیده: ۴ نشست از ۷۲ نشستِ مشترک، همه رویِ ۲۰۲۶-۰۹-۰۱؛
    `_audit/candle_source_priority_probe.py`).

    `close` = «قیمت پایانی» و `last` = «آخرین قیمت»؛ این دو هرگز قاطی نمی‌شوند
    (docs/CANDLE-CONTRACT.md §۱-ث). اگر ردیفی «آخرین» نداشت، `last` صریح None
    می‌ماند نه close.
    """
    return candle_contract.from_board_row(l_val18, d_even, first, high, low,
                                          close, vol, last, value)


def sync_price_history_from_daily(conn, full=False):
    """کندل‌ها را از خودِ daily_prices می‌سازد — بی‌شبکه، بی‌۴۲۹، قابلِ تکرار.

    ریشۀ «کندل‌ها عقب‌اند»: `price_history` تنها از راهِ `fetch_price_history`
    پر می‌شد؛ آن هم یا در pack کردنِ baseline یا با `python test_tsetmc.py
    --update-existing` که دستی است. هیچ حلقۀ خودکاری در برنامه آن را نمی‌نویسد،
    پس در بانکِ نصبی (اندازه‌گیری ۱۴۰۵-۰۷-۰۷ روی کپی) جدولِ کندل روی
    ۲۰۲۶-۰۹-۲۱ و فقط ۱۰ نماد در هر روز بود، درحالی‌که `daily_prices` همان
    روزها را کامل داشت: هشت نشستِ معامله‌شده (۰۸-۲۰، ۰۸-۲۱ و ۰۹-۲۲ تا ۰۹-۲۹)
    در تابلو بود و در کندل نبود؛ جبران ۵۳٬۰۶۰ کندل شد.
    تابلو خودش first/max/min/closing/vol هر نشست را نگه می‌دارد، پس کپی‌کردنشان
    به price_history دقیقاً همان چیزی است که لازم است — بدونِ هیچ درخواستِ تازه.
    تنها پوششی که از آنِ خودِ تابلو نیست: `daily_prices` خودش فقط ۲۴ نشستِ آخر
    را دارد (۲۰۲۶-۰۸-۲۰ به بعد)، پس تاریخچۀ کهنه‌تر همان‌جا می‌ماند و نشستِ
    ۲۰۲۶-۰۹-۲۰ که در تابلو ردیفی ندارد، تنها از CSV پر می‌شود.

    حالتِ عادی فقط تازه‌ترین نشست را می‌نویسد (چند هزار ردیف، هر ۹۰ ثانیه بی‌هزینه
    است); اگر جدولِ کندل به نشستِ امروز نرسیده باشد، کلِ نشست‌های موجود در
    daily_prices یک‌بار جبران می‌شود.
    """
    try:
        # تنها نشستی که واقعاً معامله شده مبناست: ردیفِ پیش از بازگشایی (حجمِ صفر)
        # هیچ‌وقت کندل نمی‌شود، پس اگر آن را مبنای «به امروز رسیدم» می‌گذاشتیم،
        # هر ۹۰ ثانیه یک‌بار کلِ جبران اجرا می‌شد.
        traded = "d.q_tot_tran > 0 AND d.p_closing > 0"
        row = conn.execute(
            "SELECT MAX(d.d_even) FROM daily_prices d JOIN instruments i "
            "ON i.ins_code = d.ins_code WHERE " + traded).fetchone()
        newest = row[0] if row else None
        if not newest:
            return {"sessions": 0, "rows": 0, "mode": "no-board"}
        newest_iso = _iso_from_deven(newest)
        have = conn.execute("SELECT MAX(date) FROM price_history").fetchone()[0]
        catch_up = full or have != newest_iso
        if catch_up:
            want = [r[0] for r in conn.execute(
                "SELECT DISTINCT d.d_even FROM daily_prices d JOIN instruments i "
                "ON i.ins_code = d.ins_code WHERE " + traded + " ORDER BY d.d_even")]
            mode = "catch-up"
        else:
            want, mode = [newest], "latest"
        if not want:
            return {"sessions": 0, "rows": 0, "mode": mode}
        rows = conn.execute(
            "SELECT i.l_val18, d.d_even, d.price_first, d.price_max, d.price_min,"
            "       d.p_closing, d.q_tot_tran, d.p_last, d.q_tot_cap "
            "FROM daily_prices d JOIN instruments i ON i.ins_code = d.ins_code "
            "WHERE d.d_even IN (%s) AND %s"
            % (",".join("?" * len(want)), traded), tuple(want)).fetchall()
        out, seen = [], set()
        for r in rows:
            bar = candle_from_row(*r)
            if not bar:
                continue
            key = (bar["symbol"], bar["time"])
            if key in seen:          # دو ins_code با یک نماد: آخرینِ فهرست می‌ماند
                continue
            seen.add(key)
            out.append(candle_contract.upsert_row(bar))
        written = 0
        if out:
            # upsert با قیدِ اولویت: اگر سطر از پیش `published` باشد، این نوشتن
            # انجام نمی‌شود — پس شمارِ «noop» را هم نگه می‌داریم تا گزارشِ
            # [candles-from-board] ادعایِ بی‌اساس نکند.
            before = conn.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
            conn.executemany(candle_contract.UPSERT_SQL, out)
            conn.commit()
            after = conn.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
            written = after - before
        n_syms = len({x[0] for x in out})
        print(f"  [candles-from-board] {mode}: {len(out)} کندل از {len(want)} نشست "
              f"برایِ {n_syms:,} نماد (نوشتۀ تازه/بازنشانی‌شده: {written})".replace(",", "٬"))
        return {"sessions": len(want), "rows": len(out), "mode": mode,
                "skipped_published": len(out) - written}
    except Exception as e:      # noqa: BLE001 — کندل هرگز نباید همگام‌سازی را بشکند
        print(f"  [candles-from-board] خطا: {type(e).__name__}: {e}")
        return {"sessions": 0, "rows": 0, "mode": "error", "error": str(e)}


def normalize_price_history_geometry(conn):
    """سایه‌هایِ بیرونِ بدنه را در price_history گِشاد می‌کند (یک‌بار، idempotent).

    اندازه‌گیری روی کپیِ بانکِ نصبی ۱۴۰۵-۰۷-۰۷: ۳۴٬۸۴۹ ردیف از ۳۲۱٬۳۸۹ ردیف
    بدنه‌شان بیرونِ [low, high] بود (نمونه: وبملت ۲۰۲۴-۱۰-۲۰ با
    O=H=L=۱٬۸۹۳ و C=۱٬۹۰۱). علتش همین مسیرِ قدیمی است: `fetch_price_history`
    ستون `<OPEN>` را می‌خواند که «قیمت پایه» است نه اولینِ معامله — همان چیزی که
    برایِ مسیرِ CDN در v8.7 FIX-1 اصلاح شد ولی در این جدول ماند.
    پایانی دست‌نخورده می‌ماند (به پایهٔ روزِ بعد زنجیر می‌شود)، فقط سایه گِشاد
    می‌شود — دقیقاً همان قاعده‌ای که `_parse_tsetmc_csv` رعایت می‌کند.
    """
    try:
        bad = conn.execute(
            "SELECT rowid, open, high, low, close FROM price_history "
            "WHERE open > 0 AND close > 0 AND ("
            "  COALESCE(high,0) < MAX(open, close) OR COALESCE(low,0) = 0"
            "  OR COALESCE(low,999999999999) > MIN(open, close) OR COALESCE(high,0) <= 0"
            ")").fetchall()
        if not bad:
            return 0
        upd = []
        for rid, o, h, l, c in bad:
            # تنها قاعدۀ هندسه: candle_contract.widen — پیش از این این سطر چهارمین
            # پیادۀ «نزدیک‌به‌همان» بود (max/minِ دستی)، و همان تفاوت‌هایِ ریزِ
            # high/low را تولید می‌کرد که درِ `_audit/candle_builder_divergence.py`
            # شمرده شد (۷۶ روز high، ۱۰۹ روز low واگرایی رویِ ۱٬۱۹۵ روزِ مشترک).
            hi, lo = candle_contract.widen(float(o), h, l, float(c))
            upd.append((hi, lo, rid))
        conn.executemany("UPDATE price_history SET high = ?, low = ? WHERE rowid = ?", upd)
        conn.commit()
        print(f"  [candles-geometry] {len(upd):,} سایه اصلاح شد".replace(",", "٬"))
        return len(upd)
    except Exception as e:      # noqa: BLE001 — اصلاحِ هندسه هرگز سینک را نمی‌شکند
        print(f"  [candles-geometry] خطا: {type(e).__name__}: {e}")
        return 0


def _history_start(conn, symbol, backfill=False):
    """از کجا درخواست کنیم؟ — پاسخِ بی‌cutoff.

    پیش از این اینجا `today - 730 روز` بود و بعد از دریافت یک DELETE هم همان کف را
    می‌زد (§۱-پِ قرارداد و کارِ #73). مالک درِ ۱۴۰۵-۰۷-۱۱ هرس را لغو کرد: بانکِ محلی
    باید هر تاریخچۀ معتبری که منبع دارد را نگه دارد، چون FTS/الگو/بک‌تست به عمق نیاز
    دارد. پس:

      • نماد تازه (هیچ ردیفی نیست) → از اولِ تاریخِ منبع (`CSV_FLOOR`)؛ فقط آنچه
        واقعاً منتشر شده ذخیره می‌شود، هیچ ردیفی ساخته نمی‌شود.
      • نماد موجود → روزِ بعد از **MAX(date)ِ خودِ همان نماد**؛ یعنی increment، پس
        اجرای دوم چیزی بازنویسی نمی‌کند و «full download» تصادفی رخ نمی‌دهد.
      • `backfill=True` (صریح، فقط با فرمانِ مالک) → از اولِ تاریخ، برایِ نمادی که
        ردیف دارد. این تنها راهِ رساندنِ عمقِ جدید به ردیف‌هایِ قدیمی است و بی‌اجرای
        --backfill-history هیچ‌وقت خودبه‌خود اتفاق نمی‌افتد.

    MAX(date) با هر دو نوشتارِ نماد خوانده می‌شود (ك/ي عربی ↔ ک/ی فارسی)، وگرنه
    «اندازه‌گیریِ سقف» صفر می‌شود و مسیر increment بی‌صدا به fullِ هر اجرا تبدیل می‌شد.
    """
    if backfill:
        return CSV_FLOOR
    names = [symbol]
    try:
        for a, b in conn.execute(
                "SELECT l_val18, l_val30 FROM instruments WHERE l_val18 = ? OR l_val30 = ? LIMIT 2",
                (symbol, symbol)).fetchall():
            for n in (a, b):
                if n and n not in names:
                    names.append(n)
    except Exception:
        pass
    ph = conn.execute(
        "SELECT MAX(date) FROM price_history WHERE symbol IN (%s)"
        % ",".join("?" * len(names)), tuple(names)).fetchone()[0]
    if not ph:
        return CSV_FLOOR
    try:
        nxt = datetime.date(int(ph[0:4]), int(ph[5:7]), int(ph[8:10])) + datetime.timedelta(days=1)
    except (ValueError, IndexError):
        return CSV_FLOOR
    return nxt.strftime("%Y%m%d")


def fetch_price_history(symbol, s=None, since=None, backfill=False):
    """دریافت سابقهٔ قیمت (OHLCV) از TSETMC برای نمودار شمعی (cdn، ~0.16s/نماد).

    legacy CSV (old.tsetmc) جایگزین شد: cdn سریعتر و بدون rate-limit.
    since: 'YYYY-MM-DD' → فقط ردیفهای بعد از آن (دلتا).
    backfill: صریحاً از اولِ تاریخِ منبع بخوان (پیش‌فرض False — ببینید _history_start).
    Returns the number of rows upserted (0 on failure). هیچ ردیفی حذف نمی‌شود."""
    conn = sqlite3.connect(DB_PATH)
    try:
        ins = conn.execute(
            "SELECT ins_code FROM instruments WHERE l_val30 = ? OR l_val18 = ? LIMIT 1",
            (symbol, symbol)).fetchone()
    except Exception:
        ins = None
    if not ins:
        conn.close()
        print(f"  [history] {symbol}: ins_code not found in instruments")
        return 0
    ins_code = ins[0]
    rows = 0
    from_ = (since.replace("-", "") if since else _history_start(conn, symbol, backfill))
    try:
        s = s or make_session()
        _rate_wait(s)
        r = s.get(f"{BASE}/ClosingPrice/GetClosingPriceDailyListCSV/{ins_code}/{from_}",
                  headers=HEADERS, timeout=90, stream=True)
        r.raise_for_status()
        import csv as _csv, io as _io
        reader = _csv.reader(_io.StringIO(r.text))
        next(reader, None)   # header
        for fields in reader:
            # تنها نقطۀ ساختِ کندل از ردیفِ CSV: `candle_contract.from_csv_row`
            # (open=FIRST، close=CLOSE، last=LAST، value=VALUE، هندسه از widen).
            # فیلترِ زمانی فقط «پیشِ پنجرۀ خواستۀ ما» را رد می‌کند؛ دیگر کفِ ۷۳۰روزه
            # و دیگر حذفی در کار نیست.
            dt = candle_contract.iso_from_csv(fields)
            if not dt or dt.replace("-", "") < from_:
                continue
            bar = candle_contract.from_csv_row(symbol, fields)
            if not bar:
                continue
            conn.execute(candle_contract.UPSERT_SQL, candle_contract.upsert_row(bar))
            rows += 1
        conn.commit()
        print(f"  [history] {symbol}: {rows} OHLCV rows saved")
        # هیچ حذفی اینجا نیست. پیش از این یک DELETE پس از هر fetchِ کامل تاریخچۀ
        # پیشِ کفِ ۷۳۰روزه را می‌زد؛ با لغوِ آن کف (تصمیمِ مالک ۱۴۰۵-۰۷-۱۱: عمق برایِ
        # FTS/الگو/بک‌تست) دیگر چیزی برایِ حذف نیست و «هرس» هم دیگر نمی‌تواند
        # تاریخچۀ منتشرشده را بی‌بازگشت ببَرَد. increment در _history_start تضمین
        # می‌کند اجرای دوم همان ردیف‌ها را دوباره نزند.
    except Exception as e:
        print(f"  [history] {symbol}: error - {type(e).__name__}: {e}")
    finally:
        conn.close()
    return rows


def update_existing(symbols_limit=None, max_429=3, min_interval=0.05, cooldown_fn=None):
    """بروزرسانی نمادهای موجود DB — بهینه برای بدون ADB (کم 429).

    Phase A: ۶ درخواست کل-بازار (صفها، مصرفکنندهها، بازارها، صنایع) — هر چه یکبار.
    Phase B: نمودار OHLCV دلتا — فقط نمادهایی که آخرین قیمتشان < آخرین روز معاملاتی؛
             با polite_get (min_interval)، هر 429 → cooldown 60s→300s→600s، بعد از max_429 → توقف.
    Returns (stats dict)."""
    s = make_session(min_interval=min_interval, cooldown_fn=cooldown_fn)
    conn = sqlite3.connect(DB_PATH)
    stats = {"phase_a": 0, "phase_b_done": 0, "phase_b_rows": 0, "429_count": 0, "skipped": 0}
    try:
        # ---------- Phase A: کل بازار (یکجا) ----------
        stats_daily = _save_market_snapshot(s, conn)
        stats["phase_a"] = stats_daily.get("saved", 0)
        now_date = datetime.date.today().strftime("%Y-%m-%d")
        # ---------- Phase B: دلتای نمودار ----------
        # آخرین روز معاملاتی در DB:
        last_day = conn.execute("SELECT MAX(date) FROM price_history").fetchone()[0]
        # اولویت: نمادهایی که در آخرین جلسه معامله شدهاند (فعال) و تاریخ نمودارشان عقب است
        need = conn.execute("""
            SELECT ph.symbol, MAX(ph.date) AS last, i.ins_code
            FROM price_history ph
            JOIN instruments i ON (i.l_val18 = ph.symbol OR i.l_val30 = ph.symbol)
            WHERE i.ins_code IN (SELECT ins_code FROM daily_prices
                                 WHERE d_even = (SELECT MAX(d_even) FROM daily_prices))
            GROUP BY ph.symbol
            ORDER BY last ASC
        """).fetchall()
        # اگر کمتر از رقم موردنظر بود، باقی را از کل تاریخ (بدون فیلتر فعال) واریز کن
        if symbols_limit and len(need) < symbols_limit:
            extra = conn.execute("""
                SELECT ph.symbol, MAX(ph.date) AS last, i.ins_code
                FROM price_history ph
                JOIN instruments i ON (i.l_val18 = ph.symbol OR i.l_val30 = ph.symbol)
                WHERE i.ins_code NOT IN (SELECT ins_code FROM daily_prices
                                         WHERE d_even = (SELECT MAX(d_even) FROM daily_prices))
                GROUP BY ph.symbol ORDER BY last ASC LIMIT ?
            """, (symbols_limit - len(need),)).fetchall()
            need = need + extra
        if symbols_limit:
            need = need[:symbols_limit]
        print(f"  [update] symbols needing history delta: {len(need)}")
        # since هر نماد پیشمحاسبه: دلتا از روز بعد از آخرین تاریخ DB
        prep = []
        for sym, last, ins in need:
            since = None
            if last:
                from datetime import date as _d
                try:
                    y, m, dd = [int(x) for x in str(last)[:10].split("-")]
                    since = (_d(y, m, dd) + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                except Exception:
                    since = None
            prep.append((sym, since))
        # موازی: TSETMC 429 ندارد (پروب) و min_interval=0.05 → 4 کارگر امن
        import concurrent.futures
        done = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            futures = {ex.submit(fetch_price_history, sym, s, since): (sym,)
                       for sym, since in prep}
            for fut in concurrent.futures.as_completed(futures):
                try:
                    rows = fut.result()
                except Exception:
                    rows = 0
                done += 1
                stats["phase_b_rows"] += rows
                if rows:
                    stats["phase_b_done"] += 1
                if done % 25 == 0:
                    print(f"  [update] {done}/{len(need)} …")
                p = s._polite
                if p and p["cooldown_level"] >= max_429:
                    stats["429_count"] = p["cooldown_level"]
                    stats["skipped"] = len(need) - done
                    print(f"  [update] STOP — 429 level {p['cooldown_level']}")
                    break
        print(f"  [update] done {done} symbols | +{stats['phase_b_rows']} rows | {stats['skipped']} skipped")
        # پنجرۀ [ih] آخرین کارِ سینک است، نه نخستین: پاسخِ سایت گاه چند دقیقه
        # دیر می‌آید (کشِ سردِ CDN) و نباید نوشتنِ تابلو را پشتِ خودش بیندازد.
        stats["tape_history"] = refresh_tape_history(conn)
    finally:
        conn.close()
    return stats


def backfill_history(symbols=None, limit=None):
    """عمق‌دادنِ صریحِ تاریخچه — تنها راهی که یک نمادِ موجود به پیشِ پنجرۀ قدیمی می‌رسد.

    چرا تابعِ جدا: سینکِ عادی (`update_existing`) increment است و از همین‌جا
    «فقط ردیفِ جدید یا missing» را می‌نویسد. عمقِ جدید (لغوِ هرسِ ۷۳۰روزه، تصمیمِ
    مالک ۱۴۰۵-۰۷-۱۱) باید **با فرمان** اتفاق بیفتد، نه به‌عنوانِ اثرِ جانبیِ هر اجرا؛
    وگرنه هر بوت یکِ دانلودِ کاملِ ۸۰۰نمادی می‌شد.

    پیشرفت درِ sync_summary.json ثبت می‌شود تا اجرای قطعه‌قطعه (`--limit`) ممکن باشد؛
    نوشتن ردیف‌به‌ردیف اتمیک است (INSERT OR REPLACE)، پس تکرارِ یکِ نماد بی‌ضرر است و
    ردیفِ تازهای ساخته نمی‌شود.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        if symbols:
            todo = [(s,) for s in symbols]
        else:
            # همهٔ نمادهایِ دارایِ ins_code — از جمله آن‌هایی که هنوز هیچ کندلی ندارند
            # (حلقۀ update_existing فقط نمادهایِ دارایِ ردیف را انتخاب می‌کند، پس
            # نمادِ نوزاد از آن طریق هرگز عمق نمی‌گیرد).
            todo = [(n,) for (n,) in conn.execute(
                "SELECT l_val18 FROM instruments WHERE l_val18 IS NOT NULL AND ins_code IS NOT NULL"
                " ORDER BY l_val18").fetchall()]
        if limit:
            todo = todo[:limit]
        done = 0
        added = 0
        for (sym,) in todo:
            if not sym:
                continue
            try:
                added += fetch_price_history(sym, backfill=True)
            except Exception as e:  # noqa: BLE001 — عمق‌دادن هرگز نباید سینک را بکُشد
                print(f"  [backfill] {sym}: {type(e).__name__}: {e}")
            done += 1
            if done % 25 == 0:
                print(f"  [backfill] {done}/{len(todo)} نماد | +{added} ردیف")
                write_summary({"backfill_symbols": done, "backfill_rows": added})
        write_summary({"backfill_symbols": done, "backfill_rows": added,
                       "backfill_last_run": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        print(f"  [backfill] done {done} symbols | +{added} ردیف")
        return {"symbols": done, "rows": added}
    finally:
        conn.close()


def _mw_row(r, last_d_even, today, now, sectors=None, ptypes=None):
    """یک ردیف خامِ تابلو → سه tuple (instruments, market_watch, daily_prices).

    تنها نقطۀ ساختِ این tupleها: سینکِ کامل و تیکِ زنده هر دو از همین‌جا
    می‌خوانند تا هیچ‌وقت دو نگاشتِ متفاوت رویِ بانک ننشیند. سطرِ instruments
    تنها وقتی ساخته می‌شود که sectors و ptypes داده شوند — تیکِ زنده این‌ها را
    از شبکه نمی‌گیرد و جدولِ instruments را نمی‌نویسد.
    """
    ins = r.get("insCode")
    if not ins:
        return None, None, None
    sec = str(r.get("csv") or "").strip()
    d = int(r.get("dEven") or 0) or last_d_even or today
    eps, pe, shares = num(r.get("eps")), num(r.get("pe")), num(r.get("ztd"))
    pcl, pdv = num(r.get("pcl")), num(r.get("pdv"))
    py, pf = num(r.get("py")), num(r.get("pf"))
    vol, val, trd = num(r.get("qtj")), num(r.get("qtc")), num(r.get("ztt"))
    chg = num(r.get("pc"))
    # «آخرین» کلیدِ خامِ خودش را درِ تابلو دارد: `pdv`. سنجشِ لحظه‌ای رویِ شش نماد
    # (_audit/mw_key_to_csv_column.json → mw_last_key_probe.py): pdv == ستونِ LASTِ
    # فایلِ رسمیِ خودِ TSETMC درِ ۶/۶، و pcl == CLOSE درِ ۶/۶. پیش از این `p_last` از
    # `py + pc` ساخته می‌شد (که رویِ همان نمونه‌ها باز هم LAST داد، ولی مشتق است و درِ
    # ردیفِ بی‌معامله/کدهایِ شکسته می‌شکند)؛ حالا عددِ خام و fallbackِ مشتق.
    p_last = pdv or ((py + chg) if (pcl and py) else None)
    it = None
    if sectors is not None and ptypes is not None:
        it = (ins, r.get("lva"), r.get("lvc"), sec, sectors.get(sec, ""),
              shares, eps, pe, num(r.get("bv")), now, ptypes.get(ins),
              r.get("insID"), r.get("cGrValCot"))
    mcap, mcap_src = board_market_cap(r, price=pcl, shares=shares)
    w = (ins, d, num(r.get("hEven")), pcl, p_last, num(r.get("pmn")), num(r.get("pmx")),
    num(r.get("pMin")), num(r.get("pMax")), py, pf, vol, val, trd, chg, eps, pe,
    shares, sec, now) + (queue_agg(r) or (None,) * len(_QUEUE_COLS)) + \
        (mcap, mcap_src, num(r.get("flow")), num(r.get("pRedTran")),
         num(r.get("buyOP")))
    dy = (ins, d, pcl, num(r.get("pmn")), num(r.get("pmx")), py, pf, vol, val, chg,
    now, mcap, mcap_src, trd, p_last)
    return it, w, dy


def _save_market_snapshot(s, conn):
    """Phase A — کل بازار در ۶ درخواست: MarketWatch(0/1/2) + ClientTypeAll + StaticData + Overview."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today = int(datetime.date.today().strftime("%Y%m%d"))
    _PT_ = "&".join(f"paperTypes[{i}]={i+1}" for i in range(9))
    sectors = {str(x.get("code", "")).strip(): (x.get("name") or "").strip()
               for x in polite_get(s, f"{BASE}/StaticData/GetStaticData", "staticData")
               if x.get("type") == "IndustrialGroup"}
    mw_raw = polite_get(s, MW_URL, "marketwatch") or []
    boards = {}
    for mv, b in ((1, 1), (2, 2)):
        for x in polite_get(s, f"{BASE}/ClosingPrice/GetMarketWatch?market={mv}&{_PT_}"
                                 "&showTraded=false&withBestLimits=false&hEven=0", "marketwatch") or []:
            ic = x.get("insCode")
            if ic and ic not in boards:
                boards[ic] = b
    ct = polite_get(s, f"{BASE}/ClientType/GetClientTypeAll", "clientTypeAllDto") or []
    ptypes = fetch_paper_types(lambda u: polite_get(s, u, "marketwatch") or [])
    last_d_even = 0
    try:
        last_d_even = conn.execute("SELECT MAX(d_even) FROM market_watch").fetchone()[0] or 0
    except Exception:
        pass
    d_even = last_d_even
    try:
        mo = polite_get(s, f"{BASE}/MarketData/GetMarketOverview/0", "marketOverview") or []
        if mo:
            mo = mo[0] if isinstance(mo, list) else mo
            d_even = int(mo.get("marketActivityDEven") or 0) or int(mo.get("lastDataDEven") or 0) or last_d_even
    except Exception:
        pass
    # کل ارزش بازار — عددِ رسمیِ خودِ TSETMC، نه جمعِ تابلو (بخشِ MARKET TOTALS بالا)
    total_value, total_deven, bourse_ov = fetch_market_total(s)
    inst, watch, daily = [], [], []
    for r in mw_raw:
        _it, _w, _dy = _mw_row(r, last_d_even, today, now, sectors, ptypes)
        if _w is None:
            continue
        inst.append(_it)
        watch.append(_w)
        daily.append(_dy)

    # روزِ client_type باید همان روزِ نشستِ market_watch باشد، نه «today».
    # در تعطیلی، تابلو به آخرین نشستِ واقعی می‌خورد و ClientType به امروزِ
    # ساعتی — پس قدرت خریدار/فروشِ «نبض بازار» از روزِ دیگری می‌آمد.
    client = [(x.get("insCode"), session_day_of(watch, d_even or today),
               x.get("buy_I_Volume"), x.get("buy_N_Volume"),
               x.get("buy_DDD_Volume"), x.get("buy_CountI"), x.get("buy_CountN"),
               x.get("buy_CountDDD"), x.get("sell_I_Volume"), x.get("sell_N_Volume"),
               x.get("sell_CountI"), x.get("sell_CountN"), now)
              for x in ct if x.get("insCode")]
    c = conn.cursor()
    c.executemany(_INST_INSERT, inst)
    c.executemany(_MW_INSERT, watch)
    ensure_daily_tran_column(conn)
    c.executemany(_DP_INSERT, daily)
    c.executemany("INSERT OR REPLACE INTO client_type VALUES (" + ",".join("?" * 13) + ")", client)
    c.executemany("INSERT OR REPLACE INTO boards VALUES (?, ?)", [(k, v) for k, v in boards.items()])
    conn.commit()
    # حالتِ داغ: سینکِ کامل هرچه در تابلو بود نوشت، پس امضاها از نو نشستن و
    # لایۀ ایستایِ تابلو (instruments/boards/client_type) سوخت؛ تیکِ بعدی
    # باید فقط آنچه از این لحظه عوض می‌شود را بنویسد، نه کلِ ۳٬۹۵۹ ردیف.
    import market_state
    market_state.prime(watch)
    if save_market_total(conn, total_value, total_deven or d_even, now):
        print(f"  [market-total] {total_value / 1e13:,.1f} همت (TSETMC GetMarketOverview, d_even {total_deven or d_even})")
    else:
        print("  [market-total] TSETMC عددی نفرستاد — مصرف‌کننده روی جمعِ تابلو می‌نشیند")
    if save_market_index(conn, bourse_ov, total_deven or d_even, now):
        print(f"  [market-index] {bourse_ov.get('indexLastValue')} / هموزن "
              f"{bourse_ov.get('indexEqualWeightedLastValue')} (d_even {total_deven or d_even})")
    if save_market_liquidity(conn, total_deven or d_even, now):
        print("  [market-liquidity] همتِ همین نشست در market_liquidity ثبت شد")
    conn.commit()
    # v9.8.1 — گارد پنجرهٔ بازار (۰۹:۰۰–۱۲:۳۵): اسنپ‌شاتِ عمق/صف/سرانه فقط
    # داخل ساعات رسمی ثبت میشود؛ بعد از بسته شدن بازار، دادهٔ خالی «افت به
    # صفر» روی تایم‌لاین میکشید و بعدازظهرها چارت را خراب میکرد.
    now_dt = datetime.datetime.now()
    if now_dt.weekday() in (3, 4) or now_dt.strftime("%H%M") > "1235":
        print("  [snapshot] skipped — outside 09:00-12:35 trading window (timeline stays clean)")
    else:
        save_mstat_snapshot(conn)
    print(f"  [snapshot] saved {len(watch)} symbols | client {len(client)} | date {d_even}")
    return {"saved": len(watch), "date": d_even}


_TICK_SESSION = None
_TICK_SESSION_LOCK = __import__("threading").Lock()
# رأیِ داورِ زنده (۱۴۰۵-۰۷-۰۶، سنجۀ ۱۵:۴۶–۱۵:۵۷): تابلوی سایت تا بعد از ۱۶
# هم می‌چرخد؛ پنجرۀ ثابتِ ساعتی زود است. سیاست: تا وقتی داده عوض می‌شود
# بتاز، ده دقیقه بی‌تغییری ⇒ «گوش‌دادن» (هر ۶۰ ثانیه یک پروب، نه هر ۵);
# همان‌که تغييري ديد از نو پنج‌ثانیه‌ای. درب‌های ایمنی: صبح زود (پیش از ۰۸:۵۵)
# هرگز نوشتنی نیست — ردیف‌های صفرِ پیش‌ازگشاییِ فردا همان بلاگِ #120 را
# می‌سازند — و سقفِ ۲۰:۰۰ برای پاتولوژیک؛ آخرینِ واقعیِ hEven سایت ~۱۶ است.
TICK_QUIET_S = 600.0
TICK_LISTEN_POLL_S = 60.0
_TICK_PREV_SIG = None
_TICK_LAST_CHANGE = 0.0
_TICK_LAST_PROBE = 0.0


def _tick_session():
    global _TICK_SESSION
    with _TICK_SESSION_LOCK:
        if _TICK_SESSION is None:
            _TICK_SESSION = make_session()
        return _TICK_SESSION


def _tick_observe(mw_raw, mono, was_listening):
    """امضایِ زندهٔ بدنه: عوض شد ⇒ ساعتِ سکوت صفر و بازگشت به تیکِ پنج‌ثانیه؛
    دست‌نخورده و پس از دَه دقیقه ⇒ حالتِ گوش‌دادن (پروبِ شصت‌ثانیه‌ای)."""
    global _TICK_PREV_SIG, _TICK_LAST_CHANGE, _TICK_LAST_PROBE
    import hashlib
    h = hashlib.md5()
    for r in mw_raw:
        h.update(str(r.get("insCode")).encode())
        h.update(repr((r.get("pcl"), r.get("qtj"), r.get("pc"), r.get("hEven"))).encode())
    sig = h.hexdigest()
    _TICK_LAST_PROBE = mono
    if sig != _TICK_PREV_SIG:
        _TICK_PREV_SIG = sig
        _TICK_LAST_CHANGE = mono
    elif was_listening:
        pass                       # بی‌تغييريِ دیگر — همان ریتمِ شصت‌ثانیه می‌ماند
    if _TICK_LAST_CHANGE == 0.0:
        _TICK_LAST_CHANGE = mono


def tick_live(conn=None):
    """تیکِ زنده: یک درخواستِ تابلو، نوشتنِ ستون‌هایِ ثانیه‌ای، بدونِ دست‌زدن به بقیه.

    چرا هست: مالک تابلو را ثانیه‌به‌ثانیه رویِ سایت می‌بیند؛ سینکِ کاملِ ۹۰
    ثانیه‌ای یعنی عددِ «آخرین/حجم/تغییر٪» بین دو سینک هیچ‌وقت عوض نمی‌شد و
    پولینگِ پنج‌ثانیه‌ای فرانت عیناً همان بدنه را ۳۰۴ می‌گرفت. این تابع همین
    آرایۀ تابلو (MW_URL، همان یک درخواستِ بازارِ سهام) را می‌گیرد و فقط
    market_watch و daily_pricesِ همان نشست را با همان _mw_rowِ سینک بازنویسی
    می‌کند؛ instruments/boards/client_type/تالارهایِ دیگر کارِ سینکِ کامل‌اند.

    درِ نوشتن (اندازۀ زندۀ ۱۴۰۵-۰۷-۰۶ ۱۵:۰۶): خودِ تابلوی TSETMC پس از بستنِ
    رسمی هم می‌چرخد — معاملۀ بلوکی/سوداگر و نهایه‌سازی تا ~۱۵:۳۰ در همان
    GetMarketWatch دیدۀ می‌شود و hEvenِ سایت روی ۱۵:۰۶ بود، در حالی که
    برنامۀ ما از ۱۲:۵۹ خواب بود. پس دو نوبت:
      • پیش از ۱۲:۳۰ — بازنویسیِ کاملِ سطر (همان مسیرِ سینک، صف‌ها هم زنده‌اند).
      • ۱۲:۳۰ تا ۱۵:۳۰ — فقط ستون‌هایِ عددی (آخرین/پایانی/حجم/تعداد/ارزش/
        تغییر٪/hEven/ارزشِ بازار)؛ صف‌هایِ حفظ‌شدۀ بستۀ بازار دست نمی‌خورند،
        وگرنه همان طبقۀ باگی که main() برایش «preserving queues» دارد.
    پنجشنبه/جمعه یا پس از ۱۵:۳۰: هیچ درخواستی. polite_get در ۴۲۹ خودش خنک
    می‌شود و آرایۀ خالی برمی‌گرداند؛ اینجا یعنی «این تیک رد، بانک دست‌نخورده».
    """
    wd = datetime.date.today().weekday()          # 3=پنجشنبه, 4=جمعه
    now_dt = datetime.datetime.now()
    hhmm = now_dt.strftime("%H%M")
    if wd in (3, 4) or hhmm < "0855" or hhmm >= "2000":
        return 0
    after_hours = hhmm >= "1230"
    import time as _t
    mono = _t.monotonic()
    listen = (_TICK_PREV_SIG is not None and after_hours
              and mono - _TICK_LAST_CHANGE > TICK_QUIET_S)
    if listen and mono - _TICK_LAST_PROBE < TICK_LISTEN_POLL_S:
        return 0
    s = _tick_session()
    mw_raw = polite_get(s, MW_URL, "marketwatch")
    if not mw_raw:
        return 0
    _tick_observe(mw_raw, mono, listen)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today = int(datetime.date.today().strftime("%Y%m%d"))
    own = conn is None
    if own:
        conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        import mstat_engine
        mstat_engine.ensure_schema(conn)
        try:
            last_d_even = conn.execute("SELECT MAX(d_even) FROM market_watch").fetchone()[0] or 0
        except sqlite3.Error:
            last_d_even = 0
        watch, daily = [], []
        for r in mw_raw:
            _it, _w, _dy = _mw_row(r, last_d_even, today, now)
            if _w is not None:
                watch.append(_w)
                daily.append(_dy)
        if not watch:
            return 0
        # ── دِلتا (حالتِ داغ) ──────────────────────────────────────────────
        # پیش‌ازین کلِ ~۵٬۴۵۱ ردیف هر پنج ثانیه با INSERT OR REPLACE می‌رفت، حتی
        # آن‌که هیچ فیلدی عوض نشده باشد، و بی‌تغییری هم کش را بازسازی می‌کرد.
        # امضا **رویِ همان ستون‌هایی** است که این نوبت واقعاً می‌نویسد: درِ پس از
        # بستن صف‌ها UPDATE نمی‌شوند، پس تغییرِ صف نباید «تغییر» حساب شود (وگرنه
        # هر سیکل یک UPDATE بی‌اثر + یک rebuildِ ۴ مگابایتی می‌ساخت).
        import market_state
        fields = market_state.AFTER_HOURS_FIELDS if after_hours else None
        changed_codes = {w[0] for w in market_state.diff(watch, fields)}
        wch = [w for w in watch if w[0] in changed_codes]
        dch = [d for d in daily if d[0] in changed_codes]
        if not wch:
            market_state.note_cycle(len(watch), 0, _t.monotonic() - mono)
            return 0
        c = conn.cursor()
        if after_hours:
            # نوبتِ پس از بستن: فقط اعدادِ زنده، بی‌دست‌زدن به ستون‌هایِ صف —
            # همان چیزی که سایت هم تا ~۱۵:۳۰ نشان می‌دهد.
            c.executemany("UPDATE market_watch SET h_even=?, p_closing=?, p_last=?,"
                          " price_min=?, price_max=?, q_tot_tran=?, q_tot_cap=?,"
                          " z_tot_tran=?, price_change=?, market_cap=?, market_cap_src=?,"
                          " fetched_at=? WHERE ins_code=?",
                          [(w[2], w[3], w[4], w[5], w[6], w[11], w[12], w[13], w[14],
                            w[-2], w[-1], w[19], w[0]) for w in wch])
            c.executemany("UPDATE daily_prices SET p_closing=?, price_min=?, price_max=?,"
                          " q_tot_tran=?, q_tot_cap=?, price_change=?, fetched_at=?,"
                          " market_cap=?, market_cap_src=?, z_tot_tran=?, p_last=?"
                          " WHERE ins_code=? AND d_even=?",
                          [(d[2], d[3], d[4], d[7], d[8], d[9], d[10], d[11], d[12],
                            d[13], d[14], d[0], d[1]) for d in dch])
        else:
            c.executemany(_MW_INSERT, wch)
            ensure_daily_tran_column(conn)
            c.executemany(_DP_INSERT, dch)
        conn.commit()
        # امضاها **پس از** commit جا می‌افتند: اگر نوشتن شکست، آن ردیف در سیکلِ
        # بعدی دوباره «تغییر» حساب می‌شود و رویِ دیسک کهنه نمی‌ماند. `fields`
        # هم همین‌جا معنا دارد: RAM فقط ستون‌هایی را نگه می‌دارد که واقعاً
        # نوشته شده‌اند، پس تابلویِ RAM هرگز جلوتر از بانک نمی‌رود.
        market_state.commit(wch, fields)
        market_state.note_cycle(len(watch), len(wch), _t.monotonic() - mono)
        return len(wch)
    finally:
        if own:
            conn.close()


def main():
    global _TSETMC_START
    _TSETMC_START = datetime.datetime.now()
    print("Starting full market-watch fetch ...")
    write_progress("start", "راهاندازی همگامسازی بازار ...", 0, 0)
    s = make_session()
    today = int(datetime.date.today().strftime("%Y%m%d"))
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ---- بازار بسته؟ (آخر هفتهٔ ایران: پنجشنبه/جمعه یا بعد از ۱۲:۳۰) ----
    # v9.8.1: weekday() پایتون: شنبه=۵، یکشنبه=۶ روزِ کاری ایران‌اند؛ آخر
    # هفته فقط پنجشنبه(۳)/جمعه(۴) است. شرط قبلی `wd < 3` فقط دوشنبه تا
    # چهارشنبه را میگرفت و بعدازظهرِ شنبه/یکشنبه همگام‌سازی فعال میماند و
    # دادهٔ خالی شبانه مینوشت. درست: پنجشنبه/جمعه همه‌روز بسته، بقیه بعد از
    # ۱۲:۳۰ بسته.
    wd = datetime.date.today().weekday()          # 3=پنجشنبه, 4=جمعه
    hhmm = datetime.datetime.now().strftime("%H%M")
    closed = wd in (3, 4) or hhmm > "1230"
    if closed:
        print("  Market CLOSED (weekend/after-hours) — preserving last known queues & date.")
    # آخرین روز معاملاتی ذخیرهشده + مقادیر قبلی صفها (برای حالت بسته)
    last_d_even, prev = 0, {}
    _probe = None
    try:
        _probe = sqlite3.connect(DB_PATH)
        # Row_factory: این بلوک قبلاً با اندیس کار می‌کرد و prev[1] — که d_even
        # است — را داخل p_last می‌ریخت؛ یعنی هر همگام‌سازیِ بعد از تعطیلی،
        # «آخرین معامله» را ۲۰٬۲۶۰٬۹۰۸ ریال می‌کرد و ستونِ الگوی ساعتِ کل
        # داشبورد آلوده می‌شد. نام‌محور خواندن، همین طبقهٔ خطا را غیرممکن می‌کند.
        _probe.row_factory = sqlite3.Row
        _probe.execute("SELECT 1 FROM market_watch LIMIT 1")
        last_d_even = _probe.execute(
            "SELECT MAX(d_even) FROM market_watch").fetchone()[0] or 0
        _want = ["ins_code", "p_last", "q_tot_tran", "q_tot_cap", "z_tot_tran",
                 "price_change"] + list(_QUEUE_COLS)
        _have = {r[1] for r in _probe.execute("PRAGMA table_info(market_watch)")}
        # بانکِ مهاجرت‌نشدۀِ قدیمی ستونِ تازه را ندارد؛ کلِ «حفظِ صفِ آخرین نشست»
        # نباید به‌خاطرِ یک ستون دور ریخته شود، پس فقط ستون‌هایِ موجود را می‌خواهیم.
        prev = {r["ins_code"]: r for r in _probe.execute(
            "SELECT %s FROM market_watch" % ", ".join(c for c in _want if c in _have))}
    except Exception:
        pass
    finally:
        try:
            _probe.close()
        except Exception:
            pass

    try:
        write_progress("fetch_sectors", "دریافت گروههای صنعتی بازار ...", 0, 0)
        sectors = {
            str(x.get("code")).strip(): (x.get("name") or "").strip()
            for x in get_json(s, f"{BASE}/StaticData/GetStaticData", "staticData")
            if x.get("type") == "IndustrialGroup"
        }
    except Exception as e:
        print(f"  WARN: could not fetch industry groups ({e}); sectors left blank.")
        sectors = {}

    try:
        write_progress("fetch_marketwatch", "دریافت اطلاعات تابلوخوانی کل بازار ...", 0, 0)
        mw = get_json(s, MW_URL, "marketwatch")
        if not mw:
            # network/firewall (10013, timeout, ...) — get_json already warned;
            # fail gracefully: error status + clean exit, keep last good data
            write_progress("error", "خطای شبکه یا فایروال (10013) در دریافت تابلوخوانی")
            write_summary({"status": "⚠️ خطای شبکه / فایروال (10013)",
                           "last_update": now, "symbols_updated": 0})
            print("  FATAL: market-watch fetch failed (network/firewall) - exiting cleanly.")
            return
    except RuntimeError as e:
        # Network/firewall (10013) — log a clean warning and exit the worker
        # gracefully without crashing (the dashboard keeps its last good data).
        write_progress("error", str(e))
        write_summary({"status": "⚠️ خطای شبکه / فایروال (10013)",
                       "last_update": now, "symbols_updated": 0})
        print(f"  FATAL: {e}")
        return
    except Exception as e:
        write_progress("error", f"خطا در دریافت تابلوخوانی: {e}")
        write_summary({"status": "⚠️ خطا در دریافت تابلوخوانی",
                       "last_update": now, "symbols_updated": 0})
        return
    print(f"Symbols fetched: {nfmt(len(mw))}")

    # تاریخ معاملات: API جدید dEven=0 برمی‌گرداند — از GetMarketOverview بگیر
    d_even_today = 0
    try:
        mo = get_json(s, f"{BASE}/MarketData/GetMarketOverview/0", "marketOverview")
        if mo:
            d_even_today = int(mo.get("marketActivityDEven") or 0) or int(mo.get("lastDataDEven") or 0) or 0
    except Exception:
        pass
    # کل ارزش بازار — عددِ رسمیِ خودِ TSETMC، نه جمعِ تابلو (بخشِ MARKET TOTALS بالا)
    total_value, total_deven, bourse_ov = fetch_market_total(s)
    if d_even_today:
        last_d_even = d_even_today
        print(f"  market date: {d_even_today} (from GetMarketOverview)")

    try:
        write_progress("fetch_clienttype", "دریافت صفحهٔ خرید/فروش حقیقی و حقوقی ...", 0, 0)
        ct = get_json(s, f"{BASE}/ClientType/GetClientTypeAll", "clientTypeAllDto")
    except Exception as e:
        print(f"  WARN: could not fetch client-type ({e}); left empty.")
        ct = []
    print(f"Client-type records: {nfmt(len(ct))}")

    boards = {}
    try:
        write_progress("fetch_boards", "دریافت بازار بورس/فرابورس ...", 0, 0)
        for mv, b in ((1, 1), (2, 2)):
            rows = get_json(s, f"{BASE}/ClosingPrice/GetMarketWatch?market={mv}&{_PT}"
                               "&showTraded=false&withBestLimits=false&hEven=0", "marketwatch")
            for x in rows or []:
                ic = x.get("insCode")
                if ic and ic not in boards:
                    boards[ic] = b
    except Exception as e:
        print(f"  WARN: could not fetch market boards ({e}); boards empty.")
    print(f"Boards map: {nfmt(len(boards))}")

    write_progress("fetch_paper", "دریافت طبقهٔ ابزار (سهام/حق تقدم/صندوق) ...", 0, 0)
    ptypes = fetch_paper_types(lambda u: get_json(s, u, "marketwatch"))
    print(f"Paper-type map: {nfmt(len(ptypes))}")

    inst, watch, daily = [], [], []
    book = []                          # پنج خطِ عمق → جدولِ جدا (order_book)
    total = len(mw)
    for i, r in enumerate(mw, 1):
        ins = r.get("insCode")
        if not ins:
            continue
        sec = str(r.get("csv") or "").strip()
        d_even = int(r.get("dEven") or 0)
        if not d_even:
            # تعطیلی/آخر هفته: بهجای تاریخ امروز، آخرین روز معاملاتی را نگه دار
            d_even = last_d_even or today
        eps, pe, shares = num(r.get("eps")), num(r.get("pe")), num(r.get("ztd"))
        pcl, pdv = num(r.get("pcl")), num(r.get("pdv"))
        pmn, pmx = num(r.get("pmn")), num(r.get("pmx"))
        amin, amax = num(r.get("pMin")), num(r.get("pMax"))
        py, pf = num(r.get("py")), num(r.get("pf"))
        vol, val, trd = num(r.get("qtj")), num(r.get("qtc")), num(r.get("ztt"))
        chg = num(r.get("pc"))
        # «آخرین» کلیدِ خامِ خودش را دارد (`pdv` — سنجشِ ۶/۶ نماد درِ
        # _audit/mw_key_to_csv_column.json؛ `pcl` هم == CLOSE). قاعدهٔ قدیمی
        # «pLast حذف شده، پس py+pc» رویِ همان نمونه‌ها عددِ درست می‌داد ولی مشتق
        # بود؛ اینجا عددِ خام و fallbackِ مشتق، تا ردیفِ پیش از بازگشایی.
        p_last = pdv or ((py + chg) if (pcl and py) else None)
        # حفاظت صف: وقتی بازار بسته است و ارقام جدید صفرند، دادهٔ آخرین روز
        # معاملاتی (صفهای بستهشدن) را نگه دار — صفرها جایگزین نشوند
        if closed and not (vol or val or trd) and ins in prev:
            _p = prev[ins]
            vol, val, trd, chg = (_p["q_tot_tran"], _p["q_tot_cap"],
                                  _p["z_tot_tran"], _p["price_change"])
            # کورکورانه برگرداندنِ p_lastِ کهنه، خرابیِ نسخهٔ پیشین را جاودانه
            # می‌کرد؛ فقط اگر معقول بود (هم‌مرتبهٔ پایانی) نگه داشته می‌شود.
            _pl = _p["p_last"]
            if _pl and pcl and 0.5 <= num(_pl) / pcl <= 2.0:
                p_last = _pl
        q = queue_agg(r)
        if q is None:
            q = (None,) * len(_QUEUE_COLS)
        elif closed and ins in prev and not any(q):
            # بازار بسته و پاسخِ این نماد بی‌عمق بود → صف‌های آخرین نشست را نگه دار
            _p = prev[ins]
            _have = _p.keys()
            q = tuple(_p[k] if k in _have else None for k in _QUEUE_COLS)
        bk = book_lines(r)
        if bk:
            book.append((ins, d_even, num(r.get("hEven")), bk, now))
        inst.append((ins, r.get("lva"), r.get("lvc"), sec, sectors.get(sec, ""),
                     shares, eps, pe, num(r.get("bv")), now, ptypes.get(ins),
                     r.get("insID"), r.get("cGrValCot")))
        mcap, mcap_src = board_market_cap(r, price=pcl, shares=shares)
        watch.append((ins, d_even, num(r.get("hEven")), pcl, p_last, pmn, pmx,
                      amin, amax, py, pf, vol, val, trd, chg, eps, pe,
                      shares, sec, now) + tuple(q)
                     + (mcap, mcap_src, num(r.get("flow")),
                        num(r.get("pRedTran")), num(r.get("buyOP"))))
        daily.append((ins, d_even, pcl, pmn, pmx, py, pf, vol, val, chg, now,
                      mcap, mcap_src, trd, p_last))
        if i % 250 == 0 or i == total:
            sym = (r.get("lva") or "").strip()
            write_progress("parse", f"در حال پردازش تابلوخوانی: نماد {sym} ...",
                           total, i, sym)

    # همان قاعدهٔ _save_market_snapshot: روزِ client_type باید روزِ نشستِ
    # market_watch باشد، نه امروزِ ساعتی؛ وگرنه تابلو و قدرت خریدار/فروش از
    # دو روزِ مختلف می‌آیند (مهرِ today در تعطیلی این اختلاف را می‌ساخت).
    client = [(x.get("insCode"), session_day_of(watch, d_even or today),
               x.get("buy_I_Volume"), x.get("buy_N_Volume"),
               x.get("buy_DDD_Volume"), x.get("buy_CountI"), x.get("buy_CountN"),
               x.get("buy_CountDDD"), x.get("sell_I_Volume"), x.get("sell_N_Volume"),
               x.get("sell_CountI"), x.get("sell_CountN"), now)
              for x in ct if x.get("insCode")]
    # حفاظت صفهای حقیقی/حقوقی: در حالت بسته، ردیفهای صفر مشتریان را بهجای
    # آخرین روز معاملاتی ننویس (وگرنه UI ورود پول را صفر نشان میدهد)
    if closed and client and all(
            not ((x[2] or 0) + (x[3] or 0) + (x[8] or 0) + (x[9] or 0)) for x in client):
        print("  Market closed — zero client-type queues skipped (last trading day kept).")
        client = []

    conn = sqlite3.connect(DB_PATH)
    create_schema(conn)
    c = conn.cursor()
    write_progress("save", f"ذخیرهٔ {nfmt(len(watch))} نماد در پایگاه محلی ...", total, total)
    c.executemany(_INST_INSERT, inst)
    c.executemany(_MW_INSERT, watch)
    ensure_daily_tran_column(conn)
    c.executemany(_DP_INSERT, daily)
    c.executemany("INSERT OR REPLACE INTO client_type VALUES (" + ",".join("?" * 13) + ")", client)
    c.executemany("INSERT OR REPLACE INTO boards VALUES (?, ?)",
                  [(k, v) for k, v in boards.items()])
    n_book = save_order_book(conn, book)
    conn.commit()
    import market_state
    market_state.prime(watch)
    if n_book:
        print(f"  [order-book] پنج خطِ عمق برایِ {nfmt(n_book)} نماد در order_book")
    else:
        print("  [order-book] این پاسخ blDs نداشت؛ سطرهایِ قبلی دست‌نخورده ماند")
    if save_market_total(conn, total_value, total_deven or d_even_today, now):
        print(f"  [market-total] {total_value / 1e13:,.1f} همت (TSETMC GetMarketOverview)")
    else:
        print("  [market-total] TSETMC عددی نفرستاد — مصرف‌کننده روی جمعِ تابلو می‌نشیند")
    if save_market_index(conn, bourse_ov, total_deven or d_even_today, now):
        print(f"  [market-index] {bourse_ov.get('indexLastValue')} / هموزن "
              f"{bourse_ov.get('indexEqualWeightedLastValue')}")
    if save_market_liquidity(conn, total_deven or d_even_today, now):
        print("  [market-liquidity] همتِ همین نشست در market_liquidity ثبت شد")
    # v9.8.1 — گارد پنجرهٔ بازار (۰۹:۰۰–۱۲:۳۵): بعد از بسته شدن بازار نقطهٔ
    # جدیدی در mstat_snap نمی‌نشیند تا دادهٔ خالی شبانه به‌عنوان «افت شدید
    # به صفر» در تایم‌لاین درون‌روزی ثبت نشود. (پنجشنبه/جمعه همه‌روز بسته؛
    # شنبه/یکشنبه weekday()==5/6 روز کاری‌اند)
    _now_dt = datetime.datetime.now()
    if _now_dt.weekday() in (3, 4) or _now_dt.strftime("%H%M") > "1235":
        print("  [snapshot] skipped — outside 09:00-12:35 trading window (timeline stays clean)")
    else:
        save_mstat_snapshot(conn)

    try:
        refresh_tape_history(conn)
    except Exception as e:      # noqa: BLE001 — پنجره نو نشد، همگام‌سازی نمی‌شکند
        print(f"  [tape-history] خطای غیرمنتظره: {type(e).__name__}: {e}")

    # ── P0 — سه خانوادۀ دادهٔ canonical، هیچ‌کدام در حلقۀ ۹۰ ثانیه‌ای نیستند ──
    # `main()` هر ۹۰ ثانیه از app.py:232-246 صدا زده می‌شود، پس هر سه با
    # throttleِ روزانه‌شان می‌دوند: یک بار در روز برایِ رویدادها و وضعیت‌ها، و
    # برایِ ارزشِ مبدأ هر CTV_RETRY_S. خطای هر کدام جدا می‌خورد و همگام‌سازیِ
    # تابلو را نمی‌شکند — این داده‌ها ورودیِ هیچ فیلتر یا گیتِ FTS نیستند.
    for _name, _fn, _every in (
            ("corporate-events", lambda: fetch_corporate_events(s, conn, now=now), 86400),
            ("state-notices", lambda: fetch_state_and_notices(s, conn, now=now), 86400),
            ("client-values", lambda: refresh_client_type_values(conn, now=now),
             CTV_RETRY_S)):
        try:
            if p0_due(conn, _name, _every):
                print(f"  [{_name}] {p0_summarize(_name, _fn())}")
                p0_mark(conn, _name, now)
        except Exception as e:      # noqa: BLE001
            print(f"  [{_name}] خطای غیرمنتظره: {type(e).__name__}: {e}")
    conn.commit()

    # کندل‌ها از خودِ تابلو — این تنها راهی است که price_history را در برنامه‌ای
    # که فقط «بروزرسانی تابلو» می‌زند، جلو می‌برد (پیش‌تر هیچ حلقه‌ای نمی‌نوشتش).
    try:
        sync_price_history_from_daily(conn)
    except Exception as e:      # noqa: BLE001
        print(f"  [candles-from-board] خطای غیرمنتظره: {type(e).__name__}: {e}")
    try:
        normalize_price_history_geometry(conn)
    except Exception as e:      # noqa: BLE001
        print(f"  [candles-geometry] خطای غیرمنتظره: {type(e).__name__}: {e}")

    print("=" * 60)
    print(f"Saved symbols: {nfmt(len(watch))} | client-type records: {nfmt(len(client))}")
    print(f"Total trade value: {nfmt(sum(w[12] or 0 for w in watch))} Rials")
    print(f"Total volume: {nfmt(sum(w[11] or 0 for w in watch))} shares")
    print(f"Updated: {now}")
    print("=" * 60)
    conn.close()
    write_status("done", f"بازار: {nfmt(len(watch))} نماد ذخیره شد")
    write_summary({"symbols_updated": len(watch), "last_update": now,
                   "status": "✅ موفق (تابلو)"})


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="TSETMC fetcher (Polite)")
    ap.add_argument("--update-existing", action="store_true",
                    help="دلتای روزانه: Phase A (کل بازار ۶ درخواست) + نمودار نمادهای عقبمانده (Polite)")
    ap.add_argument("--limit", type=int, default=None, help="حداکثر نماد برای Phase B")
    ap.add_argument("--min-interval", type=float, default=0.25, help="حداقل فاصلهٔ درخواستها (ثانیه)")
    ap.add_argument("--max-429", type=int, default=3, help="توقف بعد از چند 429 (پلههای همیشه که بیشتر نشود)")
    ap.add_argument("--backfill-history", action="store_true",
                    help="عمق‌دادنِ صریحِ تاریخچه از اولِ انتشارِ منبع (بدونِ این پرچم هیچ اجرایِ "
                         "خودکاری عمق نمی‌دهد؛ incremental می‌ماند)")
    a = ap.parse_args()
    if a.backfill_history:
        backfill_history(limit=a.limit)
    elif a.update_existing:
        update_existing(symbols_limit=a.limit, max_429=a.max_429, min_interval=a.min_interval)
    else:
        main()
