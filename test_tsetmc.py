#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TSETMC full market-watch fetcher (optimized).

* one request for whole market: /ClosingPrice/GetMarketWatch
* one request for client-type board: /ClientType/GetClientTypeAll
* one request for industry groups: /StaticData/GetStaticData
* bulk insert/update via executemany into market.db
"""
import os
import sqlite3
import datetime

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
_QUEUE_COLS = ("buy_q_vol", "buy_q_val", "buy_q_cnt",
               "sell_q_vol", "sell_q_val", "sell_q_cnt",
               "buy_q1_vol", "buy_q1_px", "sell_q1_vol", "sell_q1_px")

# ═══════════════════════════════════════════════════════════════════════════
#  ارزش بازار (Market Cap) — تنها نقطهٔ ساختِ این عدد در کل مخزن
# ═══════════════════════════════════════════════════════════════════════════
# قاعدهٔ v10: هیچ مصرف‌کننده‌ای (API، UI، fts_engine، خروجی) حق ندارد ارزش
# بازار را خودش بسازد. عدد یک‌بار همین‌جا از **ردیفِ خامِ تابلو** خوانده یا ساخته
# و در ستون `market_cap` ذخیره میشود؛ بقیه فقط می‌خوانند.
#   tse_raw               — فیلد رسمیِ تابلو (qTotCap) وقتی TSETMC عدد می‌دهد
#   tse_board_calc        — نبودِ فیلد خام: دو فیلدِ همان ردیفِ تابلو (pcl × ztd)
#   tse_board_calc_backfill — یک‌بار در مهاجرت، از ستونهایِ همان سطرِ ذخیره‌شده
#   ""                    — هیچ‌کدام معتبر نیست → ستون NULL می‌ماند (صفرِ جعلی نه)
MCAP_SRC_RAW = "tse_raw"
MCAP_SRC_BOARD = "tse_board_calc"
MCAP_SRC_BACKFILL = "tse_board_calc_backfill"
# چند املا از همان فیلدِ تابلو — روزی که TSETMC عدد بفرستد بی‌قیدوشرط همان مصرف میشود
MCAP_RAW_KEYS = ("qTotCap", "qtotcap", "qTotcap", "qTotValue", "marketValue")

# نوشتن با نامِ ستون — نه جایگاهی. `INSERT ... VALUES(?*30)` با هر ستونِ تازه
# (صف در mstat_engine، ارزش بازار اینجا) بی‌صدا یک ستون جابه‌جا می‌کند و
# «آخرین معامله» با «تاریخِ نشست» قاطی می‌شود — همان طبقهٔ باگی که در v9.8.1
# روی p_last خوردیم. نامِ صریح این اشتباه را غیرممکن می‌کند.
_MW_INSERT = ("INSERT OR REPLACE INTO market_watch ("
              "ins_code, d_even, h_even, p_closing, p_last, price_min, price_max,"
              " allowed_min, allowed_max, price_yesterday, price_first, q_tot_tran,"
              " q_tot_cap, z_tot_tran, price_change, eps, pe, total_shares,"
              " sector_code, fetched_at, " + ", ".join(_QUEUE_COLS) +
              ", market_cap, market_cap_src) VALUES (" + ",".join("?" * 32) + ")")
_DP_INSERT = ("INSERT OR REPLACE INTO daily_prices ("
              "ins_code, d_even, p_closing, price_min, price_max, price_yesterday,"
              " price_first, q_tot_tran, q_tot_cap, price_change, fetched_at,"
              " market_cap, market_cap_src) VALUES (" + ",".join("?" * 13) + ")")



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

    خروجی ۱۰تایی: (b_vol,b_val,b_cnt, s_vol,s_val,s_cnt, b1_vol,b1_px, s1_vol,s_px)
    ارزش = حجم × قیمتِ همان خط (ریال) — همان یکای q_tot_cap، پس واحدها در
    داشبورد قاطی نمی‌شوند. نبودِ blDs یعنی None (ستون NULL می‌ماند) نه صفر:
    «عمق نبود» با «عمق تهی بود» یکی نیست و UI باید فرقشان بداند.
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
            num(first.get("qmo")), num(first.get("pmo")))


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


def create_schema(conn):
    conn.executescript(
        """
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS instruments (
            ins_code TEXT PRIMARY KEY, l_val18 TEXT, l_val30 TEXT,
            sector_code TEXT, sector_name TEXT, total_shares REAL,
            eps REAL, pe REAL, base_vol REAL, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS market_watch (
            ins_code TEXT PRIMARY KEY, d_even INTEGER, h_even INTEGER,
            p_closing REAL, p_last REAL, price_min REAL, price_max REAL,
            allowed_min REAL, allowed_max REAL, price_yesterday REAL,
            price_first REAL, q_tot_tran REAL, q_tot_cap REAL,
            z_tot_tran REAL, price_change REAL, eps REAL, pe REAL,
            total_shares REAL, sector_code TEXT, fetched_at TEXT,
            market_cap REAL, market_cap_src TEXT);
        CREATE TABLE IF NOT EXISTS daily_prices (
            ins_code TEXT, d_even INTEGER, p_closing REAL, price_min REAL,
            price_max REAL, price_yesterday REAL, price_first REAL,
            q_tot_tran REAL, q_tot_cap REAL, price_change REAL,
            fetched_at TEXT, market_cap REAL, market_cap_src TEXT,
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
            close REAL, volume REAL, PRIMARY KEY (symbol, date));
        CREATE INDEX IF NOT EXISTS ix_daily_ins ON daily_prices(ins_code);
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


def fetch_price_history(symbol, s=None, since=None):
    """دریافت سابقهٔ قیمت (OHLCV) از TSETMC برای نمودار شمعی (cdn، ~0.16s/نماد).

    legacy CSV (old.tsetmc) جایگزین شد: cdn سریعتر و بدون rate-limit.
    since: 'YYYY-MM-DD' → فقط ردیفهای بعد از آن (دلتا).
    Returns the number of rows upserted (0 on failure)."""
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
    # فقط ۲ سال اخیر (دادههای قدیمیتر از TSETMC کیفیت ناهماهنگی دارند)
    cutoff = (datetime.date.today() - datetime.timedelta(days=730)).strftime("%Y-%m-%d")
    if since:
        cutoff = max(cutoff, since)
    try:
        conn.execute("DELETE FROM price_history WHERE symbol = ? AND date < ?", (symbol, cutoff))
        conn.commit()
    except Exception:
        pass
    try:
        s = s or make_session()
        _rate_wait(s)
        from_ = since.replace("-", "") if since else cutoff.replace("-", "")
        r = s.get(f"{BASE}/ClosingPrice/GetClosingPriceDailyListCSV/{ins_code}/{from_}",
                  headers=HEADERS, timeout=90, stream=True)
        r.raise_for_status()
        import csv as _csv, io as _io
        reader = _csv.reader(_io.StringIO(r.text))
        next(reader, None)   # header
        for fields in reader:
            if len(fields) < 11:
                continue
            d_even = fields[1].strip()          # DTYYYYMMDD
            if len(d_even) != 8 or not d_even.isdigit():
                continue
            dt = f"{d_even[:4]}-{d_even[4:6]}-{d_even[6:]}"
            if dt < cutoff:
                continue
            try:
                o = float(fields[10])   # OPEN
                h = float(fields[3])    # HIGH
                l = float(fields[4])    # LOW
                c = float(fields[5])    # CLOSE
                v = float(fields[7])    # VOL
            except (ValueError, IndexError):
                continue
            conn.execute("INSERT OR REPLACE INTO price_history VALUES (?,?,?,?,?,?,?)",
                         (symbol, dt, o, h, l, c, v))
            rows += 1
        conn.commit()
        print(f"  [history] {symbol}: {rows} OHLCV rows saved")
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
    finally:
        conn.close()
    return stats


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
    inst, watch, daily = [], [], []
    for r in mw_raw:
        ins = r.get("insCode")
        if not ins:
            continue
        sec = str(r.get("csv") or "").strip()
        d = int(r.get("dEven") or 0) or last_d_even or today
        eps, pe, shares = num(r.get("eps")), num(r.get("pe")), num(r.get("ztd"))
        pcl, pdv = num(r.get("pcl")), num(r.get("pdv"))
        py, pf = num(r.get("py")), num(r.get("pf"))
        vol, val, trd = num(r.get("qtj")), num(r.get("qtc")), num(r.get("ztt"))
        chg = num(r.get("pc"))
        p_last = (py + chg) if (pcl and py) else None
        inst.append((ins, r.get("lva"), r.get("lvc"), sec, sectors.get(sec, ""),
                     shares, eps, pe, num(r.get("bv")), now, ptypes.get(ins)))
        mcap, mcap_src = board_market_cap(r, price=pcl, shares=shares)
        watch.append((ins, d, num(r.get("hEven")), pcl, p_last, num(r.get("pmn")), num(r.get("pmx")),
                      num(r.get("pMin")), num(r.get("pMax")), py, pf, vol, val, trd, chg, eps, pe,
                      shares, sec, now) + (queue_agg(r) or (None,) * 10) + (mcap, mcap_src))
        daily.append((ins, d, pcl, num(r.get("pmn")), num(r.get("pmx")), py, pf, vol, val, chg,
                     now, mcap, mcap_src))

    client = [(x.get("insCode"), today, x.get("buy_I_Volume"), x.get("buy_N_Volume"),
               x.get("buy_DDD_Volume"), x.get("buy_CountI"), x.get("buy_CountN"),
               x.get("buy_CountDDD"), x.get("sell_I_Volume"), x.get("sell_N_Volume"),
               x.get("sell_CountI"), x.get("sell_CountN"), now)
              for x in ct if x.get("insCode")]
    c = conn.cursor()
    c.executemany("INSERT OR REPLACE INTO instruments VALUES (" + ",".join("?" * 11) + ")", inst)
    c.executemany(_MW_INSERT, watch)
    c.executemany(_DP_INSERT, daily)
    c.executemany("INSERT OR REPLACE INTO client_type VALUES (" + ",".join("?" * 13) + ")", client)
    c.executemany("INSERT OR REPLACE INTO boards VALUES (?, ?)", [(k, v) for k, v in boards.items()])
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
        prev = {r["ins_code"]: r for r in _probe.execute(
            "SELECT ins_code, p_last, q_tot_tran, q_tot_cap, z_tot_tran, price_change, "
            "buy_q_vol, buy_q_val, buy_q_cnt, sell_q_vol, sell_q_val, sell_q_cnt, "
            "buy_q1_vol, buy_q1_px, sell_q1_vol, sell_q1_px FROM market_watch")}
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
        # API جدید (2026): pLast/pClosing قدیمی حذف شدند؛ pcl=پایانی، pc=تغییر،
        # py=دیروز → آخرین معامله ≈ دیروز + تغییر
        p_last = (py + chg) if (pcl and py) else None
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
            q = (None,) * 10
        elif closed and ins in prev and not any(q):
            # بازار بسته و پاسخِ این نماد بی‌عمق بود → صف‌های آخرین نشست را نگه دار
            _p = prev[ins]
            q = tuple(_p[k] for k in _QUEUE_COLS)
        inst.append((ins, r.get("lva"), r.get("lvc"), sec, sectors.get(sec, ""),
                     shares, eps, pe, num(r.get("bv")), now, ptypes.get(ins)))
        mcap, mcap_src = board_market_cap(r, price=pcl, shares=shares)
        watch.append((ins, d_even, num(r.get("hEven")), pcl, p_last, pmn, pmx,
                      amin, amax, py, pf, vol, val, trd, chg, eps, pe,
                      shares, sec, now) + tuple(q) + (mcap, mcap_src))
        daily.append((ins, d_even, pcl, pmn, pmx, py, pf, vol, val, chg, now,
                      mcap, mcap_src))
        if i % 250 == 0 or i == total:
            sym = (r.get("lva") or "").strip()
            write_progress("parse", f"در حال پردازش تابلوخوانی: نماد {sym} ...",
                           total, i, sym)

    client = [(x.get("insCode"), today, x.get("buy_I_Volume"), x.get("buy_N_Volume"),
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
    c.executemany("INSERT OR REPLACE INTO instruments VALUES (" + ",".join("?" * 11) + ")", inst)
    c.executemany(_MW_INSERT, watch)
    c.executemany(_DP_INSERT, daily)
    c.executemany("INSERT OR REPLACE INTO client_type VALUES (" + ",".join("?" * 13) + ")", client)
    c.executemany("INSERT OR REPLACE INTO boards VALUES (?, ?)",
                  [(k, v) for k, v in boards.items()])
    conn.commit()
    # v9.8.1 — گارد پنجرهٔ بازار (۰۹:۰۰–۱۲:۳۵): بعد از بسته شدن بازار نقطهٔ
    # جدیدی در mstat_snap نمی‌نشیند تا دادهٔ خالی شبانه به‌عنوان «افت شدید
    # به صفر» در تایم‌لاین درون‌روزی ثبت نشود. (پنجشنبه/جمعه همه‌روز بسته؛
    # شنبه/یکشنبه weekday()==5/6 روز کاری‌اند)
    _now_dt = datetime.datetime.now()
    if _now_dt.weekday() in (3, 4) or _now_dt.strftime("%H%M") > "1235":
        print("  [snapshot] skipped — outside 09:00-12:35 trading window (timeline stays clean)")
    else:
        save_mstat_snapshot(conn)

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
    a = ap.parse_args()
    if a.update_existing:
        update_existing(symbols_limit=a.limit, max_429=a.max_429, min_interval=a.min_interval)
    else:
        main()
