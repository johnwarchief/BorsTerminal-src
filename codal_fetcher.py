#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch Codal notices + deep-extract financial statements into market.db (offline).

Tables:
  * codal_notices       - notice list (symbol, company, title, publish date, url)
  * financial_statements - extracted fundamentals (operating revenue, gross profit, ...)

Extraction: the Codal report page carries a JS var `datasource = {...}` holding
table cells; if absent, inner sheets (sheetId) are crawled.
"""
import os
import re
import shutil
import subprocess
import sys
import json
import time
import random
import sqlite3
import datetime
from collections import defaultdict
from urllib.parse import urlencode, quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API = "https://search.codal.ir/api/search/v2/q"

# Stealth: real, modern desktop browser fingerprints — one is picked at random
# per run (i.e., per session), so consecutive fetches look like different users.
# YAGNI: hardcoded list, no third-party fake-useragent package.
UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
]
HEADERS = {
    "User-Agent": random.choice(UA_LIST),
    # JSON-first: the Codal search API must return JSON, not an HTML page.
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8",
    # no "br": standard requests/urllib3 cannot decode Brotli natively
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Referer": "https://codal.ir/",
    "Origin": "https://codal.ir",
}
try:
    # حالت EXE: مسیرهای نوشتنی از bors_config (WORK_DIR = %LOCALAPPDATA% در
    # Program Files). __file__ در frozen به _MEIPASS فقط‌خواندنی اشاره می‌کند.
    from bors_config import DB_PATH, STATUS_PATH, OD_STATUS_PATH
except Exception:  # noqa: BLE001 — dev/standalone
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "market.db")
    STATUS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sync_status.json")
    OD_STATUS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sync_ondemand.json")

TARGET = 1000        # target notice count
PER_PAGE = 20        # fixed Codal page size
DEEP_LIMIT = 500     # max deep-analyzed reports per run (maximum historical coverage)
MAX_PAGES = 50       # safety cap on a fresh DB (max_saved==0) to avoid infinite fetch
# Global scan: فقط اطلاعیههای قابل استفاده (صورت مالی / فعالیت ماهانه) در
# codal_notices ذخیره شوند؛ «پورتفوی صندوق»، «مجمع»، «توقف/بازگشایی»، «تغییر مدیران»
# و… فقط صرفاً حجم DB را بالا میبرند و هیچوقت scrape نمیشوند.
SAVE_USEFUL_ONLY = True

# Industries EXCLUDED from the discovery scan (5-step playbook: رد
# خودرو/بیمه/دارو/غذایی/نیروگاه/لاستیک). Their notices never feed the 5-step
# score, so fetching them only costs WAF budget. ~622 symbols (~26%) skipped.
REJECTED_SECTORS = (
    "خودرو و ساخت قطعات",
    "بيمه وصندوق بازنشستگي به جزتامين اجتماعي",
    "مواد و محصولات دارويي",
    "محصولات غذايي و آشاميدني به جز قند و شكر",
    "عرضه برق، گاز، بخاروآب گرم",
    "لاستيك و پلاستيك",
)

_LAST_429 = False
_CONSEC_429 = 0          # consecutive final-429 symbols (WAF gate)
POLITE = False           # پروفایل بدون-IP-روتاریشن: بین هر درخواست مکث امن (میانگین ~1.7s)
# --no-tether از CLI ست میشود؛ پیش‌فرضِ ماژول لازم است تا make_session برای
# فراخوانِ کتابخانه‌ای (api/, dev/, probeها) NameError ندهد.
_NO_TETHER = False

# الگوی burst-rest (اندازهگیری 09-01): WAF کدال ویندوزی است نه نرخ لحظهای
# (429 در ~35-50 درخواست در تستهای امروز؛ rest 180s بعد از 50 هم هنوز 429 آمد).
# بُرست 35 درخواست → استراحت 240s (محافظهکار؛ بدون ADB).
_POLITE_BURST_MAX = 35
_POLITE_REST = 240
_POLITE_BURST_COUNT = 0


def polite_pause(base_lo=1.2, base_hi=2.2):
    """مکث بین درخواستها وقتی POLITE فعال است (برای IP ثابت بدون ADB) + بُرست-رست."""
    global _POLITE_BURST_COUNT
    if POLITE:
        time.sleep(random.uniform(base_lo, base_hi))
        _POLITE_BURST_COUNT += 1
        if _POLITE_BURST_COUNT >= _POLITE_BURST_MAX:
            _POLITE_BURST_COUNT = 0
            print(f"  [polite] burst of {_POLITE_BURST_MAX} requests — resting {_POLITE_REST}s "
                  f"(WAF window-safe)", flush=True)
            time.sleep(_POLITE_REST)


def set_polite(v):
    """فعالسازی پروفایل polite از CLI (بدون نیاز به global در __main__)."""
    global POLITE
    POLITE = bool(v)
_DISCOVERY_ABORTED = False  # set by discovery_scan on WAF-stall abort


def write_status(stage, detail=""):
    """Lightweight progress channel for the live sync indicator in dashboard.py.

    Writes a tiny JSON atomically; the dashboard polls this file without blocking."""
    try:
        tmp = STATUS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"stage": stage, "detail": detail,
                       "ts": datetime.datetime.now().isoformat(timespec="seconds")},
                      f, ensure_ascii=False)
        os.replace(tmp, STATUS_PATH)
    except Exception:
        pass


_CODAL_START = None


def _fmt_ban_until():
    """HH:MM of the shared 429 cooldown end, if a (long) backoff is armed."""
    try:
        u = globals().get("_BACKOFF_UNTIL", 0) or 0
        if u > time.time() + 30:
            return time.strftime("%H:%M", time.localtime(u))
    except Exception:
        pass
    return ""


try:
    from bors_config import CONTROL_PATH  # WORK_DIR (writable) در حالت EXE
except Exception:  # noqa: BLE001
    CONTROL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "codal_control.json")
_USER_STOPPED = False  # set when the user hits توقف in the dashboard


def _control_cmd():
    """Poll the user control file (codal_control.json): pause / resume / stop.

    Written by the dashboard (app.py /api/codal/control); read here at every
    symbol boundary so the UI buttons take effect within one symbol (~14 s).
    """
    global _USER_STOPPED
    try:
        with open(CONTROL_PATH, encoding="utf-8") as f:
            cmd = (json.load(f).get("cmd") or "").strip().lower()
    except Exception:
        cmd = ""
    if cmd == "stop":
        _USER_STOPPED = True
    return cmd


def _control_sleep(total_seconds, slice_=5.0):
    """Sleep in 5 s slices so the user's 'stop' lands within ~5 s even during
    long WAF rests (1800 s). Returns 'stop' if the user stopped, else ''."""
    end = time.time() + total_seconds
    while time.time() < end:
        if _control_cmd() == "stop":
            return "stop"
        time.sleep(slice_)
    return ""


def write_progress(phase, detail, total=0, current=0, symbol="", extra=None):
    """Granular, real-time progress channel for the Codal background sync.

    Mirrors test_tsetmc.write_progress and writes the shared sync_status.json so
    the dashboard sidebar can render a live progress bar, ETA, and current action
    (phases: codal_sync = notices+extraction, codal_backoff = 429 pause)."""
    global _CODAL_START
    try:
        if _CODAL_START is None:
            _CODAL_START = datetime.datetime.now()
        elapsed = (datetime.datetime.now() - _CODAL_START).total_seconds()
        percent = round(100.0 * current / total, 1) if total else 0.0
        tmp = STATUS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({
                "stage": "codal", "phase": phase, "detail": detail,
                "total": int(total), "current": int(current), "symbol": symbol,
                "elapsed": round(elapsed, 1), "percent": percent,
                "ban_until": _fmt_ban_until(),
                "extra": extra or {},
                "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            }, f, ensure_ascii=False)
        os.replace(tmp, STATUS_PATH)
    except Exception:
        pass


def write_od_status(symbol, stage, detail=""):
    """Per-symbol status channel for ON-DEMAND fetches. Isolated from the general
    sync_status.json so its loading state never collides with the auto background sync."""
    try:
        tmp = OD_STATUS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"symbol": symbol, "stage": stage, "detail": detail,
                       "ts": datetime.datetime.now().isoformat(timespec="seconds")},
                      f, ensure_ascii=False)
        os.replace(tmp, OD_STATUS_PATH)
    except Exception:
        pass


def write_summary(update):
    """Merge a run's results into sync_summary.json (read-modify-write, atomic).

    Each background worker writes only its own keys so the two processes never
    clobber each other's results."""
    try:
        path = _SUMMARY_PATH
        data = {}
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
        data.update(update)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        pass


# ---------------------------------------------- sync summary (merged run results)
try:
    from bors_config import WORK_DIR as _SUMMARY_DIR
except Exception:  # noqa: BLE001
    _SUMMARY_DIR = os.path.dirname(os.path.abspath(__file__))
_SUMMARY_PATH = os.path.join(_SUMMARY_DIR, "sync_summary.json")


# ---------------------------------------------- smart resume (backlog progress)
try:
    from bors_config import WORK_DIR as _STATE_DIR
except Exception:  # noqa: BLE001
    _STATE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(_STATE_DIR, "codal_state.json")


def load_state():
    """farthest_page_reached — the deepest backlog page successfully fetched."""
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return int(json.load(f).get("farthest_page_reached", 0) or 0)
    except Exception:
        return 0


def save_state(page):
    """Monotonic, atomic write of the farthest page reached (never regresses)."""
    try:
        if page <= load_state():
            return
        tmp = STATE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"farthest_page_reached": page,
                       "updated_at": datetime.datetime.now().isoformat(timespec="seconds")},
                      f, ensure_ascii=False, indent=2)
        os.replace(tmp, STATE_PATH)
    except Exception:
        pass


NOTICE_UPSERT = """INSERT OR REPLACE INTO codal_notices
    (tracing_no, symbol, company_name, title, letter_code, publish_date,
     sent_date, url, fetched_at, pdf_url, excel_url)
    VALUES (?,?,?,?,?,?,?,?,?,?,?)"""


QUERY = {
    "Audited": "true", "AuditorRef": "-1", "Category": "-1", "Childs": "false",
    "CompanyState": "-1", "CompanyType": "-1", "Consolidatable": "true",
    "IsNotAudited": "false", "Length": "-1", "LetterType": "-1", "Mains": "true",
    "NotAudited": "true", "NotConsolidatable": "true", "Publisher": "false",
    "TracingNo": "-1", "Symbol": "", "Title": "", "Type": "-1", "search": "true",
}

# Arabic/Farsi normalization + remove ZWNJ for reliable label matching
_NORM = str.maketrans({"ي": "ی", "ك": "ک", "\u200c": "", "\u200f": "", "\u064a": "ی"})

# Persian/Arabic digits -> ASCII. کدال از ~۱۳۹۸ به بعد برای PublishDateTime /
# SentDateTime ارقامِ فارسی می‌فرستد؛ بدونِ این نرمال‌سازی، ستونِ publish_date
# مخلوطِ فارسی/لاتین می‌شود و ORDER BY / MAX روی رشته‌ها می‌شکند (۸۰۰۷ ردیفِ
# FS + ۲۰۶۱۱ ردیفِ notice در market.db همین الان آسیب‌دیده‌اند).
_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _norm_date(s):
    """ارقامِ فارسی/عربیِ یک تاریخِ کدال را به لاتین تبدیل میکند.

    روی هر چیزی که رشته نیست هم امن است (None → ''). فقط ارقام را عوض
    میکند تا ساختارِ 'YYYY/MM/DD HH:MM:SS' دست‌نخورده بماند."""
    return str(s or "").strip().translate(_FA_DIGITS)

# Row-label patterns (after normalization: spaces + ZWNJ stripped, ي/ك unified)
PATTERNS = {
    # NOTE: patterns are RANK-ORDERED — index 0 is the most authoritative. The
    # rank-based parse_tables picks the lowest-rank match across the whole sheet,
    # so the total row «جمع درآمدهای عملیاتی» (rank 0) always beats a component
    # line like «درآمدهای سود سهام». The final catch-all now excludes ANY label
    # containing سودسهام/سرمایهگذاری (dividend / investment-sale components),
    # which previously leaked into `revenue` for holdings and understated it.
    "revenue": [r"^جمعدرآمدهایعملیاتی", r"^درآمدهایعملیاتی$", r"^درآمدعملیاتی",
                r"^فروشخالص", r"^مبلغفروش", r"^بهایفروش", r"^جمعفروش",
                r"^درآمدهعملیاتی", r"^فروش$",
                r"^درآمد(?!.*سودسهام)(?!.*سرمایهگذاری)"],
    "gross_profit": [r"سود\(?زیان\)?ناخالص", r"سودناخالص", r"سودوزيانناخالص"],
    "operating_profit": [r"سود\(?زیان\)?عملیات", r"سودعملیاتی", r"سودوزيانعملياتي"],
    # Exact-anchored «سود(زیان) خالص» first so the final net-profit row wins over
    # «سود خالص عملیات در حال تداوم» / «سود خالص هر سهم» (both looser matches).
    "net_profit": [r"^سود\(?زیان\)?خالص$", r"^سودخالص$", r"^زیانخالص$",
                   r"سود\(?زیان\)?قابلتخصیصبهصاحبان",
                   r"سود\(?زیان\)?خالص", r"سودخالص", r"سودوزيانخالص", r"^زیانخالص"],
    "total_assets": [r"^جمعداراییها$", r"^جمع داراییها$", r"^جمع داراییها", r"کل داراییها", r"مجموع داراییها",
                     r"^جمعدارایی(?!های)", r"^مجموعدارایی(?!های)"],
    "total_liabilities": [r"^جمعبدهیها$", r"^جمع بدهیها$", r"^جمعبدیها", r"کل بدهیها", r"مجموع بدهیها",
                          r"^جمعبدهی(?!های)", r"^مجموعبدهی(?!های)"],
    "total_equity": [r"^جمعحقوقصاحبانسهام$", r"^جمع حقوق صاحبان سهام$", r"حقوقصاحبانسهام", r"کل حقوقصاحبانسهام",
                     r"^جمعحقوقمالکانه", r"^حقوقمالکانه$"],
    "capital": [r"^سرمایه$", r"سرمایهپرداخته", r"محل تامینسرمایه", r"سرمایهثبتشده"],
    "retained_earnings": [r"سود\(?زیان\)?انباشته", r"سودانباشته", r"سودوزيانانباشته", r"اندوختهسرمایه",
                          r"زیانانباشته"],
    "basic_eps": [r"سود\(?زیان\)?خالصهرسهم", r"سود\(?زیان\)?خالصهرسهمپایه",
                  r"epsخالصهرسهم", r"سودخالصهرسهم", r"درآمدهرسهم"],
}

# Column order for the financial_statements row tuple
FS_KEYS = ["revenue", "gross_profit", "operating_profit", "net_profit",
           "total_assets", "total_liabilities", "total_equity",
           "capital", "retained_earnings", "basic_eps"]

# ستون‌هایِ ترتیبِ ردیف (۸ سرستون + FS_KEYS + unit/url/fetched_at
# + ۴ ستونِ مشتق).
# **صریح در نام ستون**: INSERT موقعیتی روی جدولی که ALTER TABLE ADD COLUMN
# دیده (۴ ستونِ مشتقِ FTS v2.2 در انتهای آن می‌نشینند) می‌شکند —
# «table has 25 columns but 21 values were supplied». با لیستِ ستون،
# SQLite مقادیر را به ستونِ درست می‌چسباند و ستون‌های جدید DEFAULT می‌گیرند.
#
# Data-Lifecycle گام ۳۴ — اتوماسیونِ ستون‌های مشتق:
# این ۴ ستون قبلاً در INSERT نبودند، پس هر ردیفِ تازه با is_consolidated=0
# و unit_norm=NULL می‌نشست و فقط یک اسکریپتِ بک‌فیلِ جداگانه (که روی یک کپیِ
# تازه‌استخراج‌شده فراموش شده بود) آن‌ها را پر می‌کرد. حالا موقعِ درجِ خودشان
# محاسبه می‌شوند تا هیچ ردیف جدیدی با مقدارِ خام/غلط ذخیره نشود.
_FS_HEAD = ["tracing_no", "symbol", "company_name", "title", "report_kind",
            "period_months", "period_end", "publish_date"]
_FS_TAIL = ["unit", "url", "fetched_at"]
_FS_DERIVED = ["is_audited", "is_consolidated", "fiscal_year", "unit_norm"]
FS_COLS = _FS_HEAD + FS_KEYS + _FS_TAIL + _FS_DERIVED
FS_UPSERT = ("INSERT OR REPLACE INTO financial_statements ("
             + ",".join(FS_COLS) + ") VALUES ("
             + ",".join("?" * len(FS_COLS)) + ")")


def fs_derived(title: str, period_end: str, unit, consol_override=None):
    """۴ ستونِ مشتقِ یک صورتِ مالی — همان منطقی که db_backfill_derived می‌زد،
    اما حالا موقعِ درج. برمی‌گرداند: (is_audited, is_consolidated,
    fiscal_year, unit_norm).

    قراردادِ یکسان با backfill: NULL یعنی «نامعلوم»، نه ۰ و نه 'unknown'.
    طبقه‌بندیِ عنوان/واحد دقیقاً از همان توابعِ یگانه می‌آید
    (_is_audited/_is_consolidated/_classify_unit) تا مسیرِ درج و مسیرِ
    بک‌فیل هرگز از هم جدا نشوند.

    consol_override: وقتی scrape_report برگردانده، مبنایِ واقعیِ شیتِ
    استخراج‌شده است (۰=غیرتلفیقی/standalone، ۱=تلفیقی). این بر عنوانِ نامه
    اولویت دارد — چون یک نامهٔ «تلفیقی» می‌تواند شیتِ سودوزیانِ غیرتلفیقی
    (sheetId=1) را هم در خود داشته باشد و جزوه مبنایِ غیرتلفیقی را می‌خواهد.
    """
    import fts_engine as _fe
    t = title or ""
    audited = 1 if _fe._is_audited(t) else 0
    if consol_override is not None:
        consol = 1 if consol_override else 0
    else:
        consol = 1 if _fe._is_consolidated(t) else 0
    year = None
    pe = (period_end or "").strip()
    if len(pe) >= 4 and pe[:4].isdigit():
        year = pe[:4]
    return audited, consol, year, _classify_unit(unit)


def _fs_has_derived(conn) -> bool:
    """آیا جدولِ financial_statements ستون‌های مشتقِ v2.2 را دارد؟"""
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(financial_statements)")}
    except Exception:
        return False
    return all(c in cols for c in _FS_DERIVED)


def nfmt(n):
    try:
        return f"{n:,}"
    except (TypeError, ValueError):
        return str(n)


def norm(s):
    """Normalize Farsi label: unify chars and drop spaces."""
    return re.sub(r"\s+", "", str(s or "").translate(_NORM))


def num(v):
    """Convert Codal numeric string to number."""
    s = str(v).replace(",", "").replace("\u200c", "").strip()
    if not s or s in {"-", "—"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _headers():
    """Fresh headers with a ROTATED User-Agent per request.

    The module-level HEADERS dict is built ONCE at import, so every request in
    a long run shares one UA — WAF fingerprints that instantly and 429-blocks
    the whole session. Rotating per request makes us look like many browsers."""
    h = dict(HEADERS)
    h["User-Agent"] = random.choice(UA_LIST)
    return h


def make_session():
    s = requests.Session()
    # Strict SSL interception in the region blocks plain (VPN-less) Codal access:
    # disable certificate verification and silence InsecureRequestWarning so the
    # console stays clean.
    s.verify = False
    # Browser UA as a SESSION DEFAULT (not just per-request): Codal's WAF silently
    # DROPs the connection after TLS for the default "python-requests/x.y" UA —
    # the socket connects, then the read times out with no status code at all.
    # Measured A/B on the same IP: python-requests UA → read timeout; browser UA
    # → 200 OK + 18 KB JSON. Callers that pass headers=_headers() still override
    # this per request (rotation), but this default means a call that forgets to
    # pass headers can never be silently black-holed again.
    s.headers.update(_headers())
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass
    # اگر USB tethering فعال باشد، ترافیک را از IP تترینگ بفرست (تا چرخش IP
    # گوشی مؤثر باشد حتی وقتی Wi-Fi کامپیوتر روشن است).
    # --no-tether: از Wi-Fi خانه برو — کدال IP تترینگ را زودتر 429 میکند
    _tether_ip = _detect_tether_ip() if not _NO_TETHER else None
    if _tether_ip:
        try:
            import socket
            s.mount("https://", _SourceAddressAdapter(_tether_ip))
            s.mount("http://", _SourceAddressAdapter(_tether_ip))
            if not quiet_print_global():
                print(f"  [net] traffic bound to tether IP {_tether_ip}", flush=True)
            return s
        except Exception as e:
            if not quiet_print_global():
                print(f"  [net] tether bind failed ({e}) — using default route", flush=True)
    retry = Retry(
        connect=4, read=4, status=3,
        backoff_factor=1.0,
        # 429 is NOT retried by urllib3 — it must return to our code so the
        # shared _BACKOFF gate pauses ALL workers together instead of this
        # session hammering the WAF with 4 hidden retries.
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def _detect_tether_ip():
    """Returns the local IP of an active USB tether adapter (Windows SAMSUNG
    Remote NDIS), or None if no tethering is up."""
    try:
        import subprocess as _sp
        out = _sp.run(
            ["powershell.exe", "-NoProfile", "-Command",
             "Get-NetAdapter -ErrorAction SilentlyContinue "
             "| Where-Object { $_.InterfaceDescription -match 'SAMSUNG|Remote NDIS|RNDIS|Android|USB Tether' -and $_.Status -eq 'Up' } "
             "| ForEach-Object { Get-NetIPAddress -InterfaceIndex $_.ifIndex -AddressFamily IPv4 "
             "-ErrorAction SilentlyContinue | Select-Object -ExpandProperty IPAddress }"],
            capture_output=True, text=True, timeout=10)
        for line in (out.stdout or "").splitlines():
            line = line.strip()
            if line and line != "127.0.0.1" and line.startswith("172."):
                return line
    except Exception:
        pass
    return None


class _SourceAddressAdapter(HTTPAdapter):
    """HTTPAdapter that binds every connection to a specific source IP so
    traffic egresses via the USB-tethered phone instead of the default Wi-Fi."""

    def __init__(self, source_address, *args, **kwargs):
        self._source_address = source_address
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, *args, **kwargs):
        import urllib3
        kwargs["source_address"] = (self._source_address, 0)
        return super().init_poolmanager(*args, **kwargs)


def quiet_print_global():
    return False


import threading


def _jitter(lo=4.0, hi=7.0):
    """Between-page conservative delay (plain requests path — the WAF is watching)."""
    time.sleep(random.uniform(lo, hi))


def create_schema(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS codal_notices (
            tracing_no INTEGER PRIMARY KEY, symbol TEXT, company_name TEXT,
            title TEXT, letter_code TEXT, publish_date TEXT, sent_date TEXT,
            url TEXT, fetched_at TEXT,
            pdf_url TEXT, excel_url TEXT);
        CREATE INDEX IF NOT EXISTS ix_codal_symbol ON codal_notices(symbol);
        CREATE INDEX IF NOT EXISTS ix_codal_date ON codal_notices(publish_date DESC);

        CREATE TABLE IF NOT EXISTS financial_statements (
            tracing_no       INTEGER PRIMARY KEY,
            symbol           TEXT,
            company_name     TEXT,
            title            TEXT,
            report_kind      TEXT,
            period_months    INTEGER,
            period_end       TEXT,
            publish_date     TEXT,
            revenue          REAL,
            gross_profit     REAL,
            operating_profit REAL,
            net_profit       REAL,
            total_assets     REAL,
            total_liabilities REAL,
            total_equity     REAL,
            capital          REAL,
            retained_earnings REAL,
            basic_eps        REAL,
            unit             TEXT,
            url              TEXT,
            fetched_at       TEXT);
        CREATE INDEX IF NOT EXISTS ix_fs_symbol ON financial_statements(symbol);

        CREATE TABLE IF NOT EXISTS monthly_sales (
            tracing_no INTEGER PRIMARY KEY,
            symbol TEXT, title TEXT, period_end TEXT,
            year INTEGER, month INTEGER,
            monthly_revenue REAL, ytd_revenue REAL,
            monthly_revenue_prev REAL, ytd_revenue_prev REAL,
            pdf_url TEXT, excel_url TEXT);
        CREATE INDEX IF NOT EXISTS ix_ms_symbol ON monthly_sales(symbol);

        CREATE TABLE IF NOT EXISTS price_history (
            symbol TEXT, date TEXT, open REAL, high REAL, low REAL,
            close REAL, volume REAL, PRIMARY KEY (symbol, date));
        """
    )
    conn.commit()


# Migrate existing DBs to add new financial columns (safe if already present)
_FS_NEW_COLS = ["total_assets", "total_liabilities", "total_equity",
                "capital", "retained_earnings", "basic_eps"]

# FTS v2.2 — ستون‌های مشتقِ صورتِ مالی (به جای پارس کردنِ عنوان در هر کوئری).
# is_audited/is_consolidated: ۰/۱ (NOT NULL DEFAULT 0 تا کوئری‌های قدیمی سالم بمانند).
# fiscal_year: '۱۴۰۴' از period_end؛ unit_norm: 'mrl'|'btl'|'unknown'.
_FS_DERIVED_COLS = [("is_audited", "INTEGER NOT NULL DEFAULT 0"),
                    ("is_consolidated", "INTEGER NOT NULL DEFAULT 0"),
                    ("fiscal_year", "TEXT"),
                    ("unit_norm", "TEXT")]

# FTS v2.2 — حجم فروش از گزارش فعالیت ماهانهٔ کدال (ستون «مقدار فروش»).
# شرطِ رشد حجمِ تولیدیِ F-01 بدون این ستون‌ها هرگز ارزیابی نمی‌شود.
_MS_VOLUME_COLS = [("monthly_volume", "REAL"), ("ytd_volume", "REAL"),
                   ("volume_unit", "TEXT")]

# FTS v2.2 — ستون‌های افزودنیِ جدولِ نتیجه (تسک ۱۹). جدولِ پایه در
# _FTS_NEW_TABLES ساخته میشود؛ این ستون‌ها بعداً با ALTER اضافه میشوند تا
# DB هایی که جدولِ نسخهٔ اول را دارند هم بدون بازنویسی ارتقا یابند.
_FTS_RESULTS_NEW_COLS = [
    ("cfg_hash", "TEXT"),
    ("f05_pass", "INTEGER"),
    ("excluded", "INTEGER"),
    ("exclusion_reasons", "TEXT"),
    ("i1a_pass", "INTEGER"), ("i1b_pass", "INTEGER"),
    ("i4a_pass", "INTEGER"), ("i4b_pass", "INTEGER"),
    ("rev_growth", "REAL"), ("gross_margin", "REAL"),
    ("sales_to_mcap", "REAL"), ("profit_potential_pct", "REAL"),
    ("annual_sales_bt", "REAL"), ("annualize_months", "INTEGER"),
]

# FTS v2.2 — جداولِ نتیجه و کمکی. همهٔ ADDITIVE: هیچ جدول/ستونِ موجود را
# تغییر نمی‌دهند، دیتای ۱۰۹ مگابایتی کاربر دست‌نخورده می‌ماند.
_FTS_NEW_TABLES = """
CREATE TABLE IF NOT EXISTS symbol_sectors (
    symbol        TEXT PRIMARY KEY,
    sector_name   TEXT NOT NULL,
    sector_code   TEXT,
    pricing_mode  TEXT NOT NULL,
    source        TEXT NOT NULL,
    confidence    INTEGER NOT NULL DEFAULT 0,
    updated_at    TEXT);
CREATE INDEX IF NOT EXISTS ix_ss_symbol ON symbol_sectors(symbol);

CREATE TABLE IF NOT EXISTS market_cap_snapshots (
    symbol       TEXT,
    date         TEXT,
    market_cap   REAL NOT NULL,
    close_price  REAL,
    total_shares REAL,
    PRIMARY KEY (symbol, date));
CREATE INDEX IF NOT EXISTS ix_mcs_sym_date ON market_cap_snapshots(symbol, date DESC);

CREATE TABLE IF NOT EXISTS fts_results (
    symbol         TEXT PRIMARY KEY,
    f01_growth_pct REAL, f01_pass INTEGER,
    f02_eps_series TEXT, f02_pass INTEGER,
    f03_margin_pct REAL, f03_pass INTEGER,
    f04_ratio      REAL, f04_pass INTEGER,
    f05_verdict    TEXT,
    score          INTEGER NOT NULL,
    verdict        TEXT NOT NULL,
    computed_at    TEXT NOT NULL);
"""


def migrate_schema(conn):
    """مهاجرتِ افزودنیِ اسکیما — کاملاً یدم‌پذیر (idempotent).

    هیچ‌گاه جدول/ستونی را حذف یا بازنویسی نمی‌کند؛ فقط با ALTER TABLE ...
    ADD COLUMN و CREATE TABLE IF NOT EXISTS ستون/جدولِ تازه می‌افزاید،
    پس دیتای موجود محفوظ می‌ماند. اجرای مکرر آن بی‌خطر است (در هر استارتاپ
    صدا زده می‌شود) چون پیش از هر ALTER با PRAGMA table_info وجود ستون را
    بررسی می‌کند.
    """
    # مقایسه سال قبل (جزوه ۱۴۰۵: ستون «مقایسه با دوره مشابه سال قبل»)
    mcols = {r[1] for r in conn.execute("PRAGMA table_info(monthly_sales)")}
    for c in ("monthly_revenue_prev", "ytd_revenue_prev"):
        if c not in mcols:
            try:
                conn.execute(f"ALTER TABLE monthly_sales ADD COLUMN {c} REAL")
            except Exception:
                pass
    # توجه: روی یک DB جوان/جزئی (یا ابزارِ تستی) ممکن است financial_statements
    # هنوز وجود نداشته باشد؛ PRAGMA table_info در آن حالت تهی برمی‌گرداند و
    # ALTER مستقیم با «no such table» می‌کشد. همین‌طور که سایرین try/except دارند.
    cols = {r[1] for r in conn.execute("PRAGMA table_info(financial_statements)")}
    for c in _FS_NEW_COLS:
        if c not in cols:
            try:
                conn.execute(f"ALTER TABLE financial_statements ADD COLUMN {c} REAL")
            except Exception:
                pass
    # «آیا این صورتِ مالی سطرِ درآمدِ عملیاتی دارد؟» — سه‌مقدار و از شواهدِ
    # خودِ اسکرپ (نه از نامِ صنعت): 1 = «جمع درآمدهای عملیاتی» مچ شد؛
    # 0 = شیتِ سود و زیان خوانده شد ولی چنین سطری نداشت (صندوق/سبدگردان که
    # «جمع درآمدها»ی سرمایه‌گذاری دارد)؛ NULL = هنوز با پارسرِ جدید بازخوانی
    # نشده. ستون جدا چون اَفینیتیِ INTEGER لازم است، نه REAL.
    if "has_operating_sales" not in cols:
        try:
            conn.execute("ALTER TABLE financial_statements "
                         "ADD COLUMN has_operating_sales INTEGER")
        except Exception:
            pass
    # لینکهای مستقیم PDF/اکسل روی اطلاعیهها (ارتقای امن DB های قدیمی)
    ncols = {r[1] for r in conn.execute("PRAGMA table_info(codal_notices)")}
    for c in ("pdf_url", "excel_url"):
        if c not in ncols:
            try:
                conn.execute(f"ALTER TABLE codal_notices ADD COLUMN {c} TEXT")
            except Exception:
                pass

    # ── FTS v2.2: ستون‌های مشتقِ صورتِ مالی ──────────────────────────────
    cols = {r[1] for r in conn.execute("PRAGMA table_info(financial_statements)")}
    for name, decl in _FS_DERIVED_COLS:
        if name not in cols:
            try:
                conn.execute(f"ALTER TABLE financial_statements ADD COLUMN {name} {decl}")
            except Exception:
                pass

    # ── FTS v2.2: حجم فروشِ ماهانه (شرطِ رشد حجمِ F-01) ───────────────────
    mcols = {r[1] for r in conn.execute("PRAGMA table_info(monthly_sales)")}
    for name, decl in _MS_VOLUME_COLS:
        if name not in mcols:
            try:
                conn.execute(f"ALTER TABLE monthly_sales ADD COLUMN {name} {decl}")
            except Exception:
                pass

    # ── FTS v2.2: ایندکسِ مرکزیِ F-02/F-03 (نماد + پایان دوره + حسابرسی) ──
    have_fs_ix = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='financial_statements'")}
    if "ix_fs_sym_pe_aud" not in have_fs_ix:
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS ix_fs_sym_pe_aud ON "
                         "financial_statements(symbol, period_end DESC, is_audited, is_consolidated)")
        except Exception:
            pass

    have_ms_ix = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='monthly_sales'")}
    if "ix_ms_sym_ym" not in have_ms_ix:
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS ix_ms_sym_ym ON "
                         "monthly_sales(symbol, year DESC, month DESC)")
        except Exception:
            pass

    # ── FTS v2.2: جداولِ نتیجه و کمکی (symbol_sectors / market_cap_snapshots
    #    / fts_results) — همه IF NOT EXISTS ────────────────────────────────
    conn.executescript(_FTS_NEW_TABLES)
    conn.commit()
    # ستون‌های افزودنیِ fts_results (تسک ۱۹): جدولِ پایه را نسخهٔ اولِ مهاجرت
    # ساخته؛ این ستون‌ها را دیرتر اضافه کردیم. ALTER با PRAGMA table_info
    # گارد میشود تا روی DBِ تازه همانند DBِ قدیمی یدم‌پذیر بماند.
    fcols = {r[1] for r in conn.execute("PRAGMA table_info(fts_results)")}
    for _c, _t in _FTS_RESULTS_NEW_COLS:
        if _c not in fcols:
            try:
                conn.execute("ALTER TABLE fts_results ADD COLUMN %s %s" % (_c, _t))
            except Exception:
                pass
    conn.commit()


# ── FTS v2.2: پر کردنِ ستون‌های مشتق (آفلاین، بدون شبکه) ─────────────────────
# طبقِ تصمیم: حجمِ F-01 از ستون «مقدار فروش» گزارش ماهانه. اینجا فقط
# ستون‌های مشتقِ صورتِ مالی + year/month ماهانه را پر می‌کنیم (حجم نیازمندِ
# اسکنِ زنده است → در scrape_monthly_report).
#
# قراردادِ NULL: ستونِ مشتق NULL یعنی «نامعلوم»، نه «صفر». is_audited=0 یعنی
    # «حسابرسی‌نشده» (یک verdict واقعی)؛ NULL یعنی عنوان نبود/غیرقابل‌طبقه‌بندی.
# fts_engine در کوئری باید NULL را به پارسِ عنوان برگرداند، نه به‌جای ۰.
def _classify_unit(unit):
    """ستون unit کدال → 'mrl' | 'btl' | None.

    دادهٔ واقعی market.db: ۹ نوشتارِ متفاوتِ عربی/فارسی/ZWNJ همگی «میلیون
    ریال» می‌گویند (۳۲۸۶+۱۴۹۶+۱۰۵۱+۸۵۵+۱۰۴+۱۰۰+۶۳+۷ = ۶۹۶۲ ردیف) و ۱۰۴۷ ردیف
    NULL. هیچ ردیفی «میلیارد تومان» نیست، ولی برای امنیتِ آینده هر دو را
    می‌شناسیم. NULL → None (نامعلوم؛ موتور به عنوانِ unknown رفتار می‌کند).

    از norm() خودِ همین ماژول استفاده می‌کند (یونیکدِ عربی/فارسی + حذفِ
    فاصله)؛ norm_fa مالِ fts_engine است و اینجا import نمی‌کنیم.
    """
    if unit is None:
        return None
    t = norm(unit)                       # ي→ی ، ك→ک ، حذفِ فاصله/نیم‌فاصله
    if "میلیارد" in t and "تومان" in t:
        return "btl"
    if "میلیون" in t and "ریال" in t:    # norm() «ريال» عربی را هم «ریال» می‌کند
        return "mrl"
    return None


def backfill_derived(conn, verbose=True):
    """پر کردنِ ستون‌های مشتقِ FTS v2.2 روی ردیف‌های موجود — کاملاً آفلاین.

    یدم‌پذیر است: فقط ردیف‌هایی را به‌روز می‌کند که هنوز NULL هستند
    (WHERE unit_norm IS NULL)، پس اجرای مکرر آن تغییری ایجاد نمی‌کند و
    ردیف‌های تازه‌ fetch‌شده را دست‌نخورده می‌گذارد (آن‌ها در زمانِ insert
    مقدار می‌گیرند).

    منبعِ طبقه‌بندی fts_engine است (همان توابعی که در زمانِ کوئری استفاده
    می‌شوند) تا منطقِ موازی و متناقض نسازیم. برمی‌گرداند: dict آمار.
    """
    import fts_engine as fe  # noqa: WPS433 — همان مسیرِ app.py (leaf-safe)

    stats = {"fs_total": 0, "fs_filled": 0, "fs_unit_mrl": 0, "fs_unit_btl": 0,
             "fs_unit_none": 0, "fs_year": 0, "ms_total": 0, "ms_ym_filled": 0}

    cols = {r[1] for r in conn.execute("PRAGMA table_info(financial_statements)")}
    if "unit_norm" not in cols:
        return stats  # هنوز مهاجرت نکرده — چیزی برای پر کردن نیست

    # WHERE unit_norm IS NULL ردیف‌های «هنوز پرنشده» را پیدا می‌کند. توجه:
    # ردیفی که unit آن NULL است به‌حق unit_norm=NULL می‌گیرد و برای همیشه
    # match می‌ماند؛ پس UPDATE فقط وقتی اجرا می‌شود که مقدارِ جدید واقعاً
    # متفاوت باشد (تفاوتِ واقعی، نه فقط match شدنِ WHERE).
    rows = conn.execute(
        "SELECT tracing_no, title, period_end, unit, is_audited, is_consolidated, "
        "fiscal_year FROM financial_statements WHERE unit_norm IS NULL").fetchall()
    stats["fs_total"] = len(rows)
    upd, mrl = [], 0
    for tn, title, period_end, unit, aud_old, con_old, yr_old in rows:
        audited = 1 if fe._is_audited(title or "") else 0
        consol = 1 if fe._is_consolidated(title or "") else 0
        year = None
        pe = str(period_end or "")
        if len(pe) >= 4 and pe[:4].isdigit():
            year = pe[:4]
        un = _classify_unit(unit)
        if un == "mrl":
            mrl += 1
        # فقط هنگامِ تغییرِ واقعی بنویس → اجرای دوم کاملاً no-op می‌شود.
        if (audited, consol, year, un) != (aud_old, con_old, yr_old, None):
            upd.append((audited, consol, year, un, tn))
    if upd:
        conn.executemany(
            "UPDATE financial_statements SET is_audited=?, is_consolidated=?, "
            "fiscal_year=?, unit_norm=? WHERE tracing_no=?", upd)
        stats["fs_filled"] = len(upd)
        stats["fs_unit_mrl"] = mrl
        stats["fs_unit_btl"] = sum(1 for u in upd if u[3] == "btl")
        stats["fs_unit_none"] = sum(1 for u in upd if u[3] is None)
        stats["fs_year"] = sum(1 for u in upd if u[2] is not None)
    else:
        stats["fs_unit_mrl"] = mrl
        stats["fs_unit_none"] = sum(1 for r in rows if _classify_unit(r[3]) is None)
        stats["fs_year"] = sum(1 for r in rows if str(r[2] or "")[:4].isdigit())

    # monthly_sales: year/month روی ردیف‌های قدیمی NULL است (ix_ms_sym_ym
    # بدون آن‌ها بی‌فایده است). منبعِ اصلی period_end است ('1404/06/31')، ولی
    # ۳۰ ردیفِ قدیمی period_end را NULL ذخیره کرده‌اند و تاریخ فقط در عنوانِ
    # گزارش دیده می‌شود → fallback به _ym_from_title.
    mcols = {r[1] for r in conn.execute("PRAGMA table_info(monthly_sales)")}
    if "year" in mcols:
        mrows = conn.execute(
            "SELECT tracing_no, period_end, title FROM monthly_sales "
            "WHERE year IS NULL OR month IS NULL").fetchall()
        stats["ms_total"] = len(mrows)
        mupd = []
        for tn, period_end, title in mrows:
            y, mo = _parse_year_month(period_end)
            if y is None:
                y, mo = _ym_from_title(title)
            if y is not None:
                mupd.append((y, mo, tn))
        if mupd:
            conn.executemany(
                "UPDATE monthly_sales SET year=?, month=? WHERE tracing_no=?", mupd)
            stats["ms_ym_filled"] = len(mupd)

    conn.commit()
    if verbose:
        print(f"[backfill] fs rows filled: {stats['fs_filled']}/{stats['fs_total']} "
              f"(unit mrl={stats['fs_unit_mrl']} btl={stats['fs_unit_btl']} "
              f"unknown={stats['fs_unit_none']}, fiscal_year={stats['fs_year']})")
        print(f"[backfill] monthly_sales year/month filled: {stats['ms_ym_filled']}/"
              f"{stats['ms_total']}")
    return stats


# Module-level progress context so fetch_page's 429 backoff can report progress.
_CB_TOTAL, _CB_DONE, _CB_SYM = 0, 0, ""

# ---------------------------------------------------------------- notice list
def fetch_page(s, page, query=None, max_429_retries=4, quiet=False):
    global _CONSEC_429
    """Fetch one page with robust exponential backoff on rate-limit (429).
    On 429 sleeps 30s, then 60s, then 120s (up to `max_429_retries` retries),
    then gives up and returns None (the caller stops the run gracefully).
    A human-like random delay is applied on transient request errors.
    quiet=True skips the global sync_status.json progress writes (on-demand
    runs must stay invisible to the global market-status UI)."""
    url = f"{API}?{urlencode(dict(query or QUERY, PageNumber=page))}"
    polite_pause()      # بدون ADB: مکث ~1.7s قبل از هر درخواست
    for attempt in range(max_429_retries + 1):
        try:
            r = s.get(url, headers=_headers(), timeout=60)
        except Exception as e:
            # v9.8.1 — قطع نشست/Timeout (requests.exceptions.Timeout، ConnectionError،
            # ProxyError، ...) رویِ متوالی = تترینگ/مودم افتاده؛ کارتِ بعدی همان
            # مسیرِ 429 است: چرخش IP با ADB (قطع/وصل حالت پرواز) و retry.
            # پیش‌تر این شاخه فقط sleep جیتری میخورد و هیچ چرخشی رخ نمیداد.
            if attempt == max_429_retries:
                print(f"  page {page}: request failed - {e}")
                return []
            _tmo = type(e).__name__
            if attempt >= 1 and not POLITE and rotate_ip_via_adb():
                print(f"  page {page}: network stall ({_tmo}) -> ADB airplane "
                      "toggle gave fresh IP - retrying", flush=True)
                _trigger_backoff(10)
                _control_sleep(10)
                continue
            time.sleep(random.uniform(2.5, 5.0))
            continue
        if r.status_code in (429, 403):
            # v9.8.1 — 403 (بن/WAF قطعی) هم مثل 429 با چرخش IP برخورد میکند؛
            # پیش‌تر 403 بی‌صدا به raise_for_status می‌افتاد و کل صفحه دور
            # ریخته میشد بدون هیچ تلاشی برای IP تازه.
            if attempt < max_429_retries:
                if not POLITE and rotate_ip_via_adb():
                    # تازه IP سلولی عوض شده — retry تقریباً فوری
                    wait = 5
                    print(f"  page {page}: {r.status_code} -> ADB rotate, retrying in {wait}s ...",
                          flush=True)
                else:
                    wait = 30 * (2 ** attempt)   # 30s, 60s, 120s
                    print(f"  page {page}: {r.status_code} rate-limit - sleeping {wait}s "
                          f"(retry {attempt + 1}/{max_429_retries}) ...", flush=True)
                # surface the pause to the dashboard (Codal phase stays codal_sync);
                # on-demand runs (quiet) never touch the global status channel
                if not quiet:
                    write_progress("codal_backoff",
                                   f"وقفه {wait} ثانیهای برای جلوگیری از مسدودی "
                                   f"({r.status_code}) — صفحه {page} ...",
                                   _CB_TOTAL, _CB_DONE, _CB_SYM)
                _trigger_backoff(wait)   # pause the WHOLE pool too
                _control_sleep(wait)
                continue
            print(f"  page {page}: {r.status_code} rate-limit - giving up after "
                  f"{max_429_retries} retries.")
            global _LAST_429, _CONSEC_429
            _LAST_429 = True
            _CONSEC_429 += 1
            if _CONSEC_429 >= 3 and not POLITE and rotate_ip_via_adb():
                # ADB IP تازه داد — لازم نیست ۳۰ دقیقه بخوابیم؛ خنکسازی کوتاه
                print(f"  page {page}: WAF ban persists ({_CONSEC_429}) - "
                      "ADB rotated fresh IP, short 20s cooldown", flush=True)
                _trigger_backoff(20)
                _CONSEC_429 = 0
                return None
            _trigger_backoff(1800)       # whole pool goes silent 30 min — probing extends bans
            if _CONSEC_429 >= 3:
                # WAF بن پایدار — توقف كامل ترافيك (بدون probe) تا بن كهنه شود؛
                # probe در حين بن آن را تمديد ميكند (اثباتشده 2026-08-25).
                print(f"  page {page}: WAF ban persists ({_CONSEC_429}) - "
                      f"silent 1800s rest (no traffic, resume after)", flush=True)
                try:
                    write_progress("codal_backoff",
                                   "بن WAF كدال - توقف ترافيك 30 دقيقه (بازگشت خودكار)",
                                   globals().get("_CB_TOTAL", 0),
                                   globals().get("_CB_DONE", 0),
                                   globals().get("_CB_SYM", ""))
                except Exception:
                    pass
                _CONSEC_429 = 0
                _control_sleep(1800)  # sliced sleep - user stop lands within ~5 s
            return None
        _CONSEC_429 = 0  # پاسخ غير-429 → WAF لحظهای مشکلی ندارد
        try:
            r.raise_for_status()
        except Exception as e:
            print(f"  page {page}: HTTP error - {e}")
            return []
        try:
            return r.json().get("Letters") or []
        except ValueError:
            # non-JSON body (HTML fallback / Cloudflare challenge / firewall page)
            # — log what the server actually returned so it is never silent
            print(f"  JSON Error (Status {r.status_code}): {r.text[:150]}")
            return []
    return None  # rate-limited sentinel


def fetch_notices(s, now, max_saved_tn=0, resume_from=0):
    """Two-phase Codal fetch with Smart Resume (codal_state.json).

    Phase A (incremental): pages 1..K — fresh notices only; stops the moment a
    tracing_no already in the DB appears, so old backlog pages are never
    re-fetched as part of the news pass.
    Phase B (historical resume): continues from max(resume_from, K) + 1 down to
    MAX_PAGES; codal_state.json is updated after every successful page, so a
    crash / persistent-429 exit resumes exactly where it left off next run.

    Returns (rows, n_new): all fetched rows for insertion + how many of them are
    genuinely NEW notices (Phase A delta)."""
    global _CB_TOTAL, _CB_DONE, _CB_SYM
    _CB_TOTAL, _CB_DONE, _CB_SYM = TARGET, 0, ""
    rows, seen = [], set()
    max_pages = MAX_PAGES
    write_progress("codal_sync",
                   f"فاز A: دریافت اطلاعیههای جدید کدال (ادامه از بایگانی صفحه {resume_from}) ...",
                   max_pages, 0)

    def _get(page, light=False):
        """Fetch one page (anti-ban delay + 429 backoff); None = must stop.
        light=True skips the long cooldown — used to re-try the page that just
        failed in Phase A without burning another 3x120s on a persistent block."""
        if page > 1:
            _jitter(4.5, 7.5)
        try:
            letters = fetch_page(s, page)
        except Exception as e:
            print(f"  error on page {page}: {e}")
            return None
        if letters is None:  # persistent 429 — ride out the cooldown, else stop
            if light:
                print(f"  page {page}: still rate-limited after Phase A - stopping.")
                return None
            print(f"  page {page}: rate-limited - riding out cooldown ...")
            for _ in range(3):
                if _control_sleep(120) == "stop":
                    return None
                # previous time.sleep(120)
                write_progress("codal_backoff",
                               f"وقفه ۱۲۰ ثانیهای برای رفع مسدودی (۴۲۹) — صفحه {page} ...",
                               _CB_TOTAL, _CB_DONE, _CB_SYM)
                letters = fetch_page(s, page)
                if letters is not None:
                    break
            if letters is None:
                print(f"  page {page}: still blocked after cooldown - stopping.")
                return None
        return letters

    def _collect(letters, stop_at_existing):
        """Add unseen notices; stop_at_existing=True (Phase A) returns (n, hit)
        where hit = first already-saved tracing_no encountered (backlog reached)."""
        n = 0
        for x in letters:
            t = x.get("TracingNo")
            if t is None or t in seen:
                continue
            if stop_at_existing and max_saved_tn and t <= max_saved_tn:
                return n, True
            # whitelist خودآموز: فقط عنوانی که با الگوهای موفق تاریخ کدال
            # مطابقت دارد ذخیره شود (strict positive؛ بدون باز کردن URL).
            if SAVE_USEFUL_ONLY and not _positive_title(x.get("Title") or ""):
                continue
            seen.add(t)
            rows.append((
                t, (x.get("Symbol") or "").strip(), (x.get("CompanyName") or "").strip(),
                (x.get("Title") or "").strip(), (x.get("LetterCode") or "").strip(),
                _norm_date(x.get("PublishDateTime")), _norm_date(x.get("SentDateTime")),
                "https://codal.ir" + (x.get("Url") or ""), now,
                (x.get("PdfUrl") or ""), (x.get("ExcelUrl") or ""),
            ))
            _CB_DONE = len(rows)
            n += 1
        return n, False

    # ---- Phase A: fresh news (stop at the first already-saved tracing_no) ----
    n_new = 0
    phase_a_last = 0
    phase_a_failed = 0  # page that forced Phase A to stop (429/error); 0 = none
    for page in range(1, max_pages + 1):
        letters = _get(page)
        if letters is None:
            phase_a_failed = page
            break
        if not letters:  # empty page (end of results)
            save_state(page)
            break
        n, hit = _collect(letters, True)
        n_new += n
        if hit:
            save_state(page - 1)  # page K fetched but only partially new
            break
        phase_a_last = page
        if page % 10 == 0 or len(rows) >= TARGET:
            print(f"  page {page} - total {nfmt(len(rows))} notices")
            write_progress("codal_sync",
                           f"فاز A: صفحه {page} از {max_pages}", max_pages, page)
        if len(rows) >= TARGET:
            break
    if phase_a_last:
        save_state(phase_a_last)  # remember progress if Phase A ended early

    # ---- Phase B: historical backlog resume (persist after every page) ----
    start = max(resume_from, phase_a_last) + 1
    if start <= max_pages:
        print(f"  Phase B: resuming backlog from page {start} (state={resume_from})")
        write_progress("codal_sync", f"فاز B: ادامهٔ بایگانی از صفحه {start} ...",
                       max_pages, start - 1)
        for page in range(start, max_pages + 1):
            # light=True: page was JUST tried (and blocked) in Phase A — a single
            # retry without another 3x120s cooldown; if still blocked, stop and
            # let the NEXT run resume from state (farthest_page_reached).
            letters = _get(page, light=(page == phase_a_failed))
            if letters is None:
                break
            if not letters:
                save_state(page)
                break
            _collect(letters, False)  # backlog pages: add everything unseen
            save_state(page)          # persisted after EVERY successful page
            if page % 10 == 0 or len(rows) >= TARGET:
                print(f"  page {page} - total {nfmt(len(rows))} notices")
                write_progress("codal_sync",
                               f"فاز B: صفحه {page} از {max_pages}", max_pages, page)
            if len(rows) >= TARGET:
                break
    else:
        print(f"  backlog complete (state={resume_from} >= {max_pages}): Phase B skipped")

    write_progress("codal_sync",
                   f"دریافت فهرست اطلاعیهها: {nfmt(len(rows))} مورد ({n_new} جدید)",
                   len(rows) or 1, len(rows))
    return rows, n_new


# ------------------------------------------------------------ deep extraction
def datasource(html):
    """Pull the datasource object out of the report HTML."""
    m = re.search(r"var\s+datasource\s*=\s*(\{.*?\});\s*\n", html, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


_BS_SIDE_KEYS = {"total_liabilities", "total_equity", "capital",
                 "retained_earnings"}


def parse_tables(ds, out, rank=None):
    """Walk table cells and pick key items using RANK-BASED selection.

    Each PATTERNS list is rank-ordered (index 0 = most authoritative). For every
    key we keep the value from the LOWEST-rank matching row across the whole
    datasource, so a definitive total row («جمع درآمدهای عملیاتی») always wins
    over a component line («درآمدهای سود سهام») regardless of sheet order.

    `rank` is an optional dict {key: best_rank_seen} that persists ACROSS calls
    (scrape_report parses several sheets into one `out`); passing it lets a later
    sheet's better-ranked row overwrite an earlier sheet's weaker one. When None,
    a fresh dict is used (single-call/back-compat behaviour).

    Handles BOTH classic vertical tables (label in col 1, values col 2+) AND
    Codal's side-by-side balance sheets (assets label in col 1, liabilities/
    equity label in col 5 with values col 6+)."""
    if rank is None:
        rank = {}
    unit = None
    for sheet in ds.get("sheets", []):
        for tbl in sheet.get("tables", []):
            unit = unit or (tbl.get("description") or "").strip() or None
            grid = defaultdict(dict)
            for c in tbl.get("cells", []):
                grid[c.get("rowSequence")][c.get("columnSequence")] = c.get("value")
            for r in sorted(k for k in grid if k is not None):
                label = norm(grid[r].get(1))
                rlabel = norm(grid[r].get(5)) if grid[r].get(5) else None
                if not label and not rlabel:
                    continue
                for key, pats in PATTERNS.items():
                    # find the best (lowest-index) pattern this row matches
                    best, side = None, False
                    if label:
                        for i, p in enumerate(pats):
                            if re.search(p, label):
                                best = i
                                break
                    if best is None and rlabel and key in _BS_SIDE_KEYS:
                        for i, p in enumerate(pats):
                            if re.search(p, rlabel):
                                best, side = i, True
                                break
                    if best is None:
                        continue
                    # already have an equal-or-better candidate for this key?
                    if out.get(key) is not None and rank.get(key, 1 << 30) <= best:
                        continue
                    cols = sorted(k for k in grid[r] if k)
                    cols = [ci for ci in cols if ci > 5] if side else cols[1:]
                    val = None
                    for ci in cols:
                        v = num(grid[r][ci])
                        if v not in (None, 0.0):
                            val = v
                            break
                    if val is None:
                        continue
                    out[key] = val
                    rank[key] = best
    return unit


def _sheet_options(html):
    """Parse the report's sheet dropdown into [(sheetId, name), ...].

    Codal's <option> tags are NOT closed with </option> (they run into the next
    <option>), so we capture the value plus the text up to the following
    option/select. Returns [] when the page carries no dropdown."""
    out = []
    for m in re.finditer(
            r'<option[^>]*value="(\d+)"[^>]*>(.*?)(?=<option|</select>)',
            html, re.S):
        name = re.sub(r"<[^>]+>", "", m.group(2))
        name = re.sub(r"\s+", " ", name.replace("\u200c", " ")).strip()
        if name:
            out.append((m.group(1), name))
    return out


def _pick_sheets(opts):
    """Choose the sheetIds we need, honouring the FTS jozve's STANDALONE basis.

    Returns (income_sid, income_is_consolidated, balance_sid). Standalone
    («صورت سود و زیان» / «صورت وضعیت مالی», no «تلفیقی») is preferred; we fall
    back to the consolidated sheet only when no standalone one exists. The
    «جامع» (comprehensive-income) variants are ignored."""
    inc_s = inc_c = bs_s = bs_c = None
    for val, name in opts:
        n = name.replace("\u200c", " ")
        consol = "تلفیقی" in n
        if ("سود و زیان" in n) and ("جامع" not in n):
            if consol:
                inc_c = inc_c or val
            else:
                inc_s = inc_s or val
        elif ("وضعیت مالی" in n) or ("ترازنامه" in n):
            if consol:
                bs_c = bs_c or val
            else:
                bs_s = bs_s or val
    income = inc_s or inc_c
    income_consol = bool(income and inc_s is None and inc_c is not None)
    balance = bs_s or bs_c
    return income, income_consol, balance


def _resilient_get(s, url, tries=4, timeout=60, quiet=False):
    """GET `url` with the same block-recovery path fetch_page uses.

    scrape_report/rebuild_fs previously called s.get() directly, so a 429/403
    WAF ban during the long crawl aborted the letter instead of rotating the
    cellular IP. Here a genuine block (429/403) or a network stall rotates via
    ADB (when enabled and not POLITE) and retries with a short cooldown; other
    HTTP errors just retry with jitter. Returns a Response, or None when the
    block persists after `tries` attempts."""
    for attempt in range(tries):
        try:
            r = s.get(url, headers=_headers(), timeout=timeout)
        except Exception as e:
            if attempt == tries - 1:
                if not quiet:
                    print(f"  [get] failed {url[-40:]} - {type(e).__name__}: {e}",
                          flush=True)
                return None
            if not POLITE and rotate_ip_via_adb():
                _control_sleep(8)
            else:
                time.sleep(random.uniform(2.5, 5.0))
            continue
        if r.status_code in (429, 403):
            if attempt < tries - 1:
                if not POLITE and rotate_ip_via_adb():
                    wait = 6
                else:
                    wait = 20 * (2 ** attempt)
                if not quiet:
                    print(f"  [get] {r.status_code} on {url[-40:]} - retry in {wait}s",
                          flush=True)
                _control_sleep(wait)
                continue
            if not quiet:
                print(f"  [get] {r.status_code} persists on {url[-40:]} - giving up",
                      flush=True)
            return None
        return r
    return None


def scrape_report(s, url):
    """Fetch report page and extract numbers from the correct sheets.

    Codal renders the base Decision.aspx page WITHOUT the embedded datasource;
    the numbers live on per-sheet pages reached via `&sheetId=N`. We read the
    sheet dropdown, then fetch the STANDALONE income statement and STANDALONE
    balance sheet (falling back to consolidated only when standalone is absent).
    The parsed basis is reported back in meta['is_consolidated'] so downstream
    rows carry the true basis rather than the (often misleading) letter title."""
    out, meta, unit = {}, {}, None
    rank = {}
    r = _resilient_get(s, url)
    if r is None:
        return out, meta, unit
    r.raise_for_status()
    html = r.text

    income_sid, income_consol, balance_sid = _pick_sheets(_sheet_options(html))
    targets = []
    if income_sid is not None:
        targets.append(("income", income_sid, income_consol))
    if balance_sid is not None:
        targets.append(("balance", balance_sid, None))

    basis_consol = None
    if targets:
        for role, sid, consol in targets:
            try:
                sr = _resilient_get(s, f"{url}&sheetId={sid}")
                ds = datasource(sr.text) if sr is not None else None
            except Exception:
                ds = None
            if not ds:
                continue
            unit = parse_tables(ds, out, rank) or unit
            meta.setdefault("period", ds.get("period"))
            meta.setdefault("end", ds.get("periodEndToDate"))
            if role == "income":
                meta["has_income"] = True
                if consol is not None:
                    basis_consol = consol
            elif role == "balance":
                meta["has_balance"] = True
    else:
        # Legacy single-sheet page: datasource embedded in the base HTML.
        ds = datasource(html)
        if ds:
            unit = parse_tables(ds, out, rank) or unit
            meta = {"period": ds.get("period"), "end": ds.get("periodEndToDate")}

    meta["is_consolidated"] = 1 if basis_consol else 0
    return out, meta, unit



def kind_of(title):
    """Detect report kind with strict Negative Filtering to prevent useless deep-crawls."""
    t = norm(title)

    # BLACKLIST: If the title contains any of these, it's NOT a raw data table.
    bad_words = ["توضیحات", "تصمیمات", "آگهی", "زمانبندی", "تمدید", "لغو", "تعلیق", "تغییر",
                     "دعوت", "تکمیلی", "پیوست", "دلایل", "شفافسازی", "افشای", "مهلت"]
    if any(b in t for b in bad_words):
        return None

    if "فعالیتماهانه" in t:
        return "Monthly Activity Report"

    if "صورتهایمالی" in t or "صورتمالی" in t:
        # WHITELIST: Must be a periodic report
        if any(x in t for x in ["میان", "دوره", "سالمالی", "تلفیقی", "حسابرسی"]):
            return "Financial Statements"

    return None


# ─────────────────── self-learned title whitelist (pattern mining) ──────────
# بهجای regexهای دستنویس: الگوها از عناوین «موفق» تاریخ کدال یاد گرفته
# میشوند — هر عنوانی که تاکنون با موفقیت به financial_statements یا
# monthly_sales استخراج شده، یک قالب regex میسازد (تاریخ/عدد → wildcard).
# عنوان ورودی که با هیچ قالب شناختهشدهای مطابقت نکند همان لحظه رد میشود —
# بدون حتی باز کردن URL (صرفهجویی در scrape و شبکه).
_TITLE_PATTERNS = None          # list[re.Pattern]؛ lazy، یکبار در هر run


def _title_norm(s):
    """Persian/Arabic digits → ASCII + ZWNJ/ي/ك unify + strip whitespace."""
    t = str(s or "").translate(_NORM)
    t = t.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    return re.sub(r"\s+", "", t)


def _title_regexes(force=False):
    """Mine strict positive-whitelist regexes from historically successful titles.

    A template = one successful title with date runs and digit runs generalized
    to wildcards (e.g. 'صورتهایمالیسالمالیمنتهیبه۱۴۰۴/۱۲/۲۹' →
    'صورتهایمالیسالمالیمنتهیبه<DATE>' → regex with \\d{4}[-/]\\d{1,2}[-/]\\d{1,2}).
    Every compiled pattern is anchored (^...$) so matching is exact."""

    global _TITLE_PATTERNS
    if _TITLE_PATTERNS is not None and not force:
        return _TITLE_PATTERNS
    templates, n_success = set(), 0
    try:
        conn = sqlite3.connect(DB_PATH, timeout=60, isolation_level=None)
        try:
            rows = conn.execute(
                "SELECT DISTINCT title FROM financial_statements "
                "UNION SELECT DISTINCT title FROM monthly_sales").fetchall()
        finally:
            conn.close()
        n_success = len(rows)
        for (title,) in rows:
            t = _title_norm(title)
            if not t:
                continue
            t = re.sub(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", "<DATE>", t)
            t = re.sub(r"\d{4}[-/]\d{1,2}", "<DATE>", t)   # تاریخ بدون روز: ۱۴۰۱/۱۲
            t = re.sub(r"\d+", "<N>", t)
            # هر پسوند پرانتزی (حسابرسی‌شده، اصلاحیه، شرکت X، ...) → اختیاری
            t = re.sub(r"\([^)]*\)", "<SUF>", t)
            templates.add(t)
    except Exception as e:
        print(f"  [patterns] mining failed: {e} — falling back to kind_of")
        templates = set()
    if not templates:
        _TITLE_PATTERNS = []       # DB نوپا → خزانهٔ ذهنی خالی → kind_of قدیمی
        return _TITLE_PATTERNS
    pats = []
    for t in templates:
        had_suf = "<SUF>" in t
        pat = (re.escape(t)
               .replace("<DATE>", r"\d{4}[-/]\d{1,2}(?:[-/]\d{1,2})?")
               .replace("<N>", r"\d+")
               .replace("<SUF>", r"(?:\([^)]*\))*"))
        # "میاندورهایتلفیقی" ≠ "تلفیقی" — الگوی تلفیقی باید بدون «میاندورهای» هم بپذیرد
        pat = pat.replace("میاندورهایتلفیقی", r"(?:میاندورهای)?تلفیقی")
        if not had_suf:
            pat = pat.rstrip("$") + r"(?:\([^)]*\))*$"
        pats.append(re.compile("^" + pat + "$"))
    print(f"  [patterns] learned {len(pats)} title patterns "
          f"from {n_success} successful titles", flush=True)
    _TITLE_PATTERNS = pats
    return _TITLE_PATTERNS


def _positive_title(title):
    """Strict positive whitelist: True only if a learned pattern matches.

    Empty whitelist (fresh DB, nothing learned yet) → fall back to kind_of so
    nothing is silently lost on the very first run."""

    pats = _title_regexes()
    if not pats:
        return kind_of(title) is not None
    t = _title_norm(title)
    return any(p.match(t) for p in pats)


MS_UPSERT = """INSERT OR REPLACE INTO monthly_sales
    (tracing_no, symbol, title, period_end, year, month,
     monthly_revenue, ytd_revenue, monthly_revenue_prev, ytd_revenue_prev,
     monthly_volume, ytd_volume, volume_unit,
     pdf_url, excel_url)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""


def _bank_fallback(grid, rows):
    """Generic monthly table fallback (banks, services, etc.).

    جزوه (وبملت): بانک «فروش» ندارد؛ جدول «درآمد محقق‌شده» چند ردیف دارد
    (تسهیلات اعطایی/سپرده‌گذاری/اوراق بدهی/سرمایه‌گذاری‌ها/کارمزد) و ردیف
    «جمع» ندارد — مجموع ردیف‌ها خودِ کل درآمدهاست. ابتدا این حالت special-case
    می‌شود؛ اگر جدول «درآمد محقق شده» نبود، رفتار عمومی (ردیف جمع) می‌ماند.
    Returns (m, y) or (None, None)."""
    # --- حالت بانک: هدر «درآمد محقق شده طی دوره یک ماهه» + «...از ابتدای سال مالی» ---
    hdr = None
    mcol = ycol = None
    for hr in rows[:3]:
        hv = {ci: norm(grid[hr][ci]) for ci in grid[hr]}
        mc = [ci for ci, v in hv.items() if "درآمد" in v and "محقق" in v and "طیدوره" in v.replace(" ", "")]
        yc = [ci for ci, v in hv.items() if "جمعدرآمد" in v.replace(" ", "") and "ابتدای" in v]
        if mc and yc:
            hdr, mcol, ycol = hr, min(mc), min(yc)
            break
    if hdr is not None:
        sm = sy = 0.0
        got = False
        for r2 in rows:
            if r2 <= hdr:
                continue
            lab = norm(grid[r2].get(1)) or ""
            if lab.startswith("سرفصل") or lab.startswith("جمع") or lab.startswith("مجموع"):
                break
            mv = num(grid[r2].get(mcol))
            yv = num(grid[r2].get(ycol))
            if mv is None and yv is None:
                continue
            sm += mv or 0.0
            sy += yv or 0.0
            got = True
        if got:
            return (sm if sm else None, sy if sy else None)
    # --- رفتار عمومی: ردیف «جمع» ---
    mcol = ycol = None
    for hr in (rows[0], rows[1] if len(rows) > 1 else rows[0]):
        hv = {ci: norm(grid[hr][ci]) for ci in grid[hr]}
        for ci, v in hv.items():
            if re.search(r"دوره\s*(یک|[0-9۰-۹]+)\s*ماهه", v) and "ازابتدای" not in v:
                mcol = ci
            elif "ازابتدایسالمالی" in v or ("دوره" in v and "سالمالی" in v):
                ycol = ci
    if mcol is None and ycol is None:
        return None, None
    total_row = None
    for r2 in rows:
        lab = norm(grid[r2].get(1))
        if lab in ("جمع", "جمعکل"):
            total_row = r2
            break
    if total_row is None:
        return None, None   # بدون ردیف جمع، ردیف آخر یادداشت است نه جمع (باگ وبملت)
    m = num(grid[total_row].get(mcol)) if mcol is not None else None
    y = num(grid[total_row].get(ycol)) if ycol is not None else None
    return (m, y) if (m is not None or y is not None) else (None, None)


def scrape_monthly_report(s, url):
    """Scenario 1 — monthly activity report (گزارش فعالیت ماهانه).

    The sales table has a TWO-row header (group row «از ابتدای سال مالی تا» /
    «دوره یک ماهه منتهی به» + sub-column row «مبلغ فروش …») and a final
    «جمع» (Total) row. Returns (values dict, period_end)."""
    out = {}
    try:
        r = s.get(url, headers=_headers(), timeout=60)
        r.raise_for_status()
    except Exception as e:
        print(f"  monthly report error: {e}")
        return out, None
    ds = datasource(r.text)
    if not ds:
        return out, None
    period_end = ds.get("periodEndToDate")
    best = None  # fallback (monthly, ytd) without header match
    for sheet in ds.get("sheets", []):
        for tbl in sheet.get("tables", []):
            grid = defaultdict(dict)
            for c in tbl.get("cells", []):
                grid[c.get("rowSequence")][c.get("columnSequence")] = c.get("value")
            rows = sorted(k for k in grid if k is not None)
            if len(rows) < 2:
                continue
            # two-row header: one row carries the group titles, the other the
            # sub-column titles («مبلغ فروش …»). Order may swap between reports.
            sub_row = grp_row = None
            for hr in (rows[0], rows[1]):
                hv = {ci: norm(grid[hr][ci]) for ci in grid[hr]}
                if any("مبلغفروش" in v for v in hv.values()):
                    sub_row = hr
                if any("دورهیکماهه" in v or "ازابتدایسالمالی" in v for v in hv.values()):
                    grp_row = hr
            if sub_row is None or grp_row is None:
                continue  # not a sales table; bank fallback runs after the loop
            sub = {ci: norm(grid[sub_row][ci]) for ci in grid[sub_row]}
            grp = {ci: norm(grid[grp_row][ci]) for ci in grid[grp_row]}
            gcols = sorted(ci for ci in grp if grp[ci])

            def _group_of(ci):
                g = ""
                for gc in gcols:
                    if gc <= ci:
                        g = grp[gc]
                    else:
                        break
                return g

            mcols = [ci for ci in sub if "مبلغفروش" in sub[ci]
                     and "دورهیکماهه" in _group_of(ci)]
            ycols = [ci for ci in sub if "مبلغفروش" in sub[ci]
                     and "ازابتدایسالمالی" in _group_of(ci)
                     and (not mcols or ci > min(mcols))]
            mcol = min(mcols) if mcols else None
            ycol = min(ycols) if ycols else None
            # جزوه ۱۴۰۵: گزارش ماهانه ستون «مقایسه با دوره مشابه سال قبل» هم دارد
            # (تکرار گروه‌های «دورهیکماهه»/«ازابتدایسالمالی» = سال قبل)
            _ms = sorted(mcols); _ys = sorted(ycols)
            mcol_prev = _ms[1] if len(_ms) > 1 else None
            ycol_prev = _ys[1] if len(_ys) > 1 else None
            # --- حجمِ فروش (تعداد فروش) + واحدِ آن — تصمیمِ تصویب‌شدهٔ F-01:
            # حجم از همین جدولِ «شرح محصول» و ستونِ «تعداد فروش» گرفته میشود.
            # ستون‌های «تعداد فروش» دقیقاً موازیِ «مبلغ فروش» در همان گروه‌های
            # زمانی می‌ایستند (تولید/فروش/نرخ/مبلغ در یک گروهِ ۴تایی).
            _VOL_HDR = ("تعدادفروش", "مقدارفروش")
            vmcols = [ci for ci in sub if any(h in sub[ci] for h in _VOL_HDR)
                      and "دورهیکماهه" in _group_of(ci)]
            vycols = [ci for ci in sub if any(h in sub[ci] for h in _VOL_HDR)
                      and "ازابتدایسالمالی" in _group_of(ci)
                      and (not vmcols or ci > min(vmcols))]
            vmcol = min(vmcols) if vmcols else None
            vycol = min(vycols) if vycols else None
            vunit_col = next((ci for ci in sub if sub[ci] == "واحد"), None)
            # Total row: prefer the exact «جمع»/«جمع کل», then any «جمع…»
            total_row = None
            for r2 in rows:
                lab = norm(grid[r2].get(1))
                if lab in ("جمع", "جمعکل"):
                    total_row = r2
                    break
            if total_row is None:
                for r2 in rows:
                    lab = norm(grid[r2].get(1))
                    if lab.startswith("جمع"):
                        total_row = r2
                        break
            if total_row is None:
                continue
            m = num(grid[total_row].get(mcol)) if mcol is not None else None
            y = num(grid[total_row].get(ycol)) if ycol is not None else None
            mp = num(grid[total_row].get(mcol_prev)) if mcol_prev is not None else None
            yp = num(grid[total_row].get(ycol_prev)) if ycol_prev is not None else None

            def _vol_from(col):
                """تعدادِ فروشِ ردیفِ «جمع»؛ اگر آن خالی است، جمعِ ردیف‌هایِ
                جزئی. برخی گزارش‌ها تعدادِ فروش را فقط رویِ ردیف‌هایِ محصول
                میدهند و ردیفِ جمع فقط مبلغ فروش دارد (و برعکس)."""
                if col is None:
                    return None
                v = num(grid[total_row].get(col))
                if v is not None:
                    return v
                tot = 0.0
                for r2 in rows:
                    if r2 == total_row:
                        continue
                    lab = norm(grid[r2].get(1))
                    if not lab or lab.startswith(("جمع", "مجموع", "سرفصل")) \
                            or lab.endswith(":"):
                        continue
                    d = num(grid[r2].get(col))
                    if d is not None:
                        tot += d
                return tot if tot else None

            # واحدِ حجم از اولین ردیفِ جزئی که واحدِ غیرخالی دارد (مثلاً «تن»)
            vunit = None
            if vunit_col is not None:
                for r2 in rows:
                    if r2 == total_row:
                        continue
                    u = norm(grid[r2].get(vunit_col))
                    if u and u != "واحد":
                        vunit = u
                        break
            if m is None and y is None:
                continue
            if mcol is not None or ycol is not None:
                return {"monthly_revenue": m, "ytd_revenue": y,
                        "monthly_revenue_prev": mp, "ytd_revenue_prev": yp,
                        "monthly_volume": _vol_from(vmcol),
                        "ytd_volume": _vol_from(vycol),
                        "volume_unit": vunit}, period_end
            if best is None:
                best = (m, y)
    if best:
        out["monthly_revenue"], out["ytd_revenue"] = best
    # ---- Bank/insurance fallback: no «فروش» table matched anywhere — try the
    # income-style table (شستا, وبملت, …) on every sheet once, take the first hit.
    if "monthly_revenue" not in out and "ytd_revenue" not in out:
        for sheet in ds.get("sheets", []):
            for tbl in sheet.get("tables", []):
                grid = defaultdict(dict)
                for c in tbl.get("cells", []):
                    grid[c.get("rowSequence")][c.get("columnSequence")] = c.get("value")
                rows = sorted(k for k in grid if k is not None)
                if len(rows) < 2:
                    continue
                m, y = _bank_fallback(grid, rows)
                if m is not None or y is not None:
                    out["monthly_revenue"], out["ytd_revenue"] = m, y
                    return out, period_end
    return out, period_end


# ---------------------------------------------------------------------------
# Concurrent bulk sync state (shared across ThreadPoolExecutor workers)
# ---------------------------------------------------------------------------
import threading
import concurrent.futures

_BACKOFF_LOCK = threading.Lock()
_BACKOFF_UNTIL = 0.0          # epoch seconds until which ALL workers must pause
_BACKOFF_EVENTS = 0
# search API فقط سریال: WAF همان ۲ درخواست همزمان از یک IP را بن میکند (درخواست
# تکی → 200؛ ۲ کارگر موازی → 429 فوری، حتی با جیتر ۲.۵-۴ ثانیه). فاز ۱ (scrape از
# codal.ir/Reports) WAF ندارد و میتواند موازی بماند.
_SEARCH_LOCK = threading.Lock()


def _wait_if_backing_off():
    """Block the calling worker until any shared 429 cooldown has elapsed."""
    global _BACKOFF_UNTIL
    while True:
        with _BACKOFF_LOCK:
            remaining = _BACKOFF_UNTIL - time.time()
        if remaining <= 0:
            return ""
        if _control_cmd() == "stop":
            return "stop"
        write_progress("codal_backoff",
                       f"وقفه همگانی {int(remaining)} ثانیه به دلیل محدودیت (۴۲۹) — همه کارگرها متوقفاند ...",
                       globals().get("_CB_TOTAL", 0),
                       globals().get("_CB_DONE", 0),
                       globals().get("_CB_SYM", ""))
        time.sleep(min(remaining, 5))


# ───────────────── Android ADB IP rotation (cellular recharge) ───────────────
# کدال (search.codal.ir) روی IP نرخگیری میکند؛ لیست پروکسیهای رایگان به آن
# نمیرسند. با اتصال گوشی اندروید از طریق adb، بههمزدن حالت پرواز مودم را
# مجبور به رجیستر مجدد میکند → IP سلولی تازه. شرط: ترافیک کامپیوتر از دیتای
# گوشی عبور کند (تترینگ/هاتاسپات). در نبود adb یا دستگاه، همهٔ مسیرها به
# sleep-backoff قبلی برمیگردند (هیچ رگرسیونی).
_ADB_CMD = None            # مسیر adb.exe کش شده؛ None = دوباره بگرد
_ADB_LOCK = threading.Lock()
_ADB_ROTATED_AT = 0.0      # monotonic ts آخرین چرخش موفق
_ADB_MIN_GAP = 120.0      # کل چرخه چرخش (enable+80s+disable+20s) — جلوگیری از توگل تکراری

_ADB_CANDIDATES = (
    r"C:\adb\platform-tools\adb.exe",
    r"C:\adb\adb.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
    os.path.expandvars(r"%ANDROID_HOME%\platform-tools\adb.exe"),
)

try:
    from bors_config import WORK_DIR as _ADB_CFG_DIR
except Exception:  # noqa: BLE001
    _ADB_CFG_DIR = os.path.dirname(os.path.abspath(__file__))
_ADB_CFG_PATH = os.path.join(_ADB_CFG_DIR, "adb_config.json")
_ADB_CFG_TS = 0.0
_ADB_CFG_CACHED = True


def _adb_enabled():
    """تنظیم کاربر از راهنمای UI (adb_config.json): خاموش = چرخش IP ممنوع."""
    global _ADB_CFG_TS, _ADB_CFG_CACHED
    if time.monotonic() - _ADB_CFG_TS < 5.0:
        return _ADB_CFG_CACHED
    v = True
    try:
        with open(_ADB_CFG_PATH, encoding="utf-8") as f:
            v = bool(json.load(f).get("enabled", True))
    except Exception:
        pass
    _ADB_CFG_TS = time.monotonic()
    _ADB_CFG_CACHED = v
    return v


def _find_adb():
    """adb.exe: اول PATH، بعد محلهای رایج SDK."""
    global _ADB_CMD
    if _ADB_CMD and not os.path.isfile(_ADB_CMD):
        _ADB_CMD = None            # v9.7.2 — مسیر کش‌شده حذف/منتقل شده: دوباره بگرد
    if _ADB_CMD:
        return _ADB_CMD
    p = shutil.which("adb")
    if not p:
        for cand in _ADB_CANDIDATES:
            if cand and os.path.isfile(cand):
                p = cand
                break
    if p:
        _ADB_CMD = p
    return p


# ─────────────── v9.7.2 — لایهٔ تاب‌آوری ADB (Retry + Re-connect) ───────────────
# سه عیب عملی در مسیر پیشین:
#  ۱) «offline» و «unauthorized» دقیقاً مثل «دستگاه نیست» رفتار می‌کردند و
#     False برمی‌گرداندند؛ در حالی که کابل وصل است و با kill-server/start-server
#     (یا تأیید دستی پنجرهٔ RSA روی گوشی) احیا شدنی است.
#  ۲) یک نوسان کوتاه کابل کل چرخش را بی‌درود شکست می‌داد و اسکن به خواب
#     طولانی می‌رفت، بدون اینکه دوباره دیوایس را پینگ کند.
#  ۳) «adb devices» یک‌بار و بدون تلاش مجدد زده می‌شد؛ خطای گذرای USB هم
#     قطعی تلقی می‌شد.
_ADB_TRIES = 3             # دورهای پینگ تا دیدن دستگاه «device»
_ADB_RETRY_DELAY = 4.0     # فاصلهٔ پینگ مجدد پس از نوسان کابل


def _adb_run(adb, args, timeout=10, tries=1):
    """یک فرمان adb با تلاش مجدد؛ نوسان گذرای USB را می‌خورد.

    آخرین CompletedProcess را برمی‌گرداند و None اگر همهٔ تلاش‌ها استثنا دادند.
    """
    last = None
    for i in range(max(1, tries)):
        try:
            kw = dict(capture_output=True, text=True, timeout=timeout)
            if os.name == "nt":
                kw["creationflags"] = subprocess.CREATE_NO_WINDOW
            last = subprocess.run([adb] + list(args), **kw)
            if last.returncode == 0:
                return last
        except Exception:
            last = None
        if i + 1 < tries:
            time.sleep(_ADB_RETRY_DELAY)
    return last


def _adb_devices(adb):
    """دستگاه‌ها را بر پایهٔ وضعیت واقعی دسته‌بندی می‌کند.

    برمی‌گرداند (ready, unauthorized, offline). تفکیک لازم است چون «دیوان بالا
    است ولی گواهی RSA تأیید نشده» با «هیچ کابلی نیست» راه‌حل متفاوتی دارد.
    """
    ready, unauth, off = [], [], []
    r = _adb_run(adb, ["devices"], timeout=8, tries=2)
    if r is None:
        return ready, unauth, off
    for ln in (r.stdout or "").splitlines():
        parts = ln.split("\t")
        if len(parts) < 2:
            continue                       # سرصفحه و خطوط خلا
        serial, st = parts[0].strip(), parts[-1].strip()
        if st == "device":
            ready.append(serial)
        elif st == "unauthorized":
            unauth.append(serial)
        elif st in ("offline", "no permissions"):
            off.append(serial)
    return ready, unauth, off


def _adb_restart_server(adb, quiet=False):
    """دیوان adb را از قفل/آفلاینی در می‌آورد (کاهشِ رایج پس از کابل‌کشی)."""
    for cmd in (["kill-server"], ["start-server"]):
        try:
            kw = dict(capture_output=True, text=True, timeout=20)
            if os.name == "nt":
                kw["creationflags"] = subprocess.CREATE_NO_WINDOW
            subprocess.run([adb] + cmd, **kw)
        except Exception as e:
            if not quiet:
                print(f"  [adb] {' '.join(cmd)} failed ({e})", flush=True)
    time.sleep(2.5)


def _adb_wait_ready(adb, quiet=False, tries=_ADB_TRIES):
    """حلقهٔ Retry + Re-connect: تا دستگاه واقعاً آماده نشده، دست‌بردار نمی‌کند.

    هر دور که دیوایس offline/unauthorized بود، سرور adb بازراه‌اندازی و دوباره
    پینگ می‌شود؛ اگر هیچ دیوایسی نبود، پس از مکث کوتاه مجدد تلاش می‌کند تا نوسان
    کابل برنامه را فریز نکند. serial آماده یا None.
    """
    for attempt in range(1, tries + 1):
        ready, unauth, off = _adb_devices(adb)
        if ready:
            if attempt > 1 and not quiet:
                print(f"  [adb] device recovered on attempt {attempt} "
                      f"→ {ready[0]}", flush=True)
            return ready[0]
        stalled = unauth or off
        if attempt == tries:
            break
        if stalled:
            why = ("unauthorized — accept the RSA prompt on the phone"
                   if unauth else "offline")
            if not quiet:
                print(f"  [adb] device {why}; restarting adb server and "
                      f"re-pinging ({attempt}/{tries})", flush=True)
            _adb_restart_server(adb, quiet=quiet)
        else:
            if not quiet:
                print(f"  [adb] no device yet — re-pinging in "
                      f"{_ADB_RETRY_DELAY:.0f}s ({attempt}/{tries})", flush=True)
            time.sleep(_ADB_RETRY_DELAY)
    return None


def rotate_ip_via_adb(quiet=False):
    """چرخش IP سلولی: airplane-mode enable → 80s → disable → 20s (اندازهگیری
    2026-08-26 روی MCI: توگل کوتاه (<60s) IP را پین شده نگه میدارد؛ تخریب
    کامل PDP context (~80-90s) → آدرس/NAT تازه. گوشی RFCT30KRY6D متصل است).

    True = یک دستگاه متصل بود و توگل موفق شد (یا کمتر از _ADB_MIN_GAP گذشته و
    IP تازه است). False = adb نیست / دستگاه نیست / توگل رد شد → sleep backoff."""
    global _ADB_ROTATED_AT
    if time.monotonic() - _ADB_ROTATED_AT < _ADB_MIN_GAP:
        return True                      # همین الان چرخیده — دوباره نزن
    if not _adb_enabled():
        if not quiet:
            print("  [adb] disabled by user (toggle off) — falling back to sleep "
                  "backoff", flush=True)
        return False
    adb = _find_adb()
    if not adb:
        if not quiet:
            print("  [adb] not found — falling back to sleep backoff", flush=True)
        return False
    # v9.7.2 — قفل غیرهمبلوک: یک دور کامل توگل ~۲ دقیقه طول می‌کشد و در نسخهٔ
    # پیشین کارگرِ دوم روی همان قفل می‌خوابید و ترد اسکن فریز می‌شد.
    if not _ADB_LOCK.acquire(blocking=False):
        if not quiet:
            print("  [adb] rotation already running in another worker — skipping",
                  flush=True)
        return True                      # IP تازه در راه است؛ خوابیدن لازم نیست
    wifi_off = False
    try:
        def _pub_ip():
            try:
                return requests.get("https://api.ipify.org", timeout=8).text.strip()
            except Exception:
                return None

        # باگ 09-05: ترافیک از Wi-Fi (metric 55) میرود نه گوشی (75) → توگل ایرپلین
        # IP را عوض نمیکرد ولی True برمیگشت. راه‌حل: حین روتیشن Wi-Fi موقتاً خاموش.
        def _wifi(on):
            nonlocal wifi_off
            try:
                subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                    (["Disable", "Enable"][bool(on)]) + "-NetAdapter -Name 'Wi-Fi' -Confirm:$false"],
                    capture_output=True, timeout=25,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                wifi_off = not on
            except Exception:
                pass

        # v9.7.2 — حلقهٔ Retry + Re-connect: نوسان کابل دیگر چرخش را نمی‌شکند و
        # دستگاهِ offline/unauthorized با بازراه‌اندازی دیوان احیا می‌شود.
        if not _adb_wait_ready(adb, quiet=quiet):
            if not quiet:
                print("  [adb] no usable device after retries — falling back to "
                      "sleep backoff", flush=True)
            return False

        _wifi(False)
        time.sleep(3)
        ip_before = _pub_ip()   # baseline قبل از توگل — تأیید واقعی تغییر IP
        # نکته: «svc usb tethering enable» فرمان معتبری نیست (usage error) —
        # tethering باید از قبل روشن باشد؛ اگر نبود، مرحلهٔ تأیید IP پایین
        # False برمیگرداند و به sleep-backoff می‌افتیم.
        a = _adb_run(adb, ["shell", "cmd", "connectivity", "airplane-mode", "enable"],
                     tries=2)
        time.sleep(80)   # تخریب کامل PDP — توگل کوتاه IP را پین نگه میدارد (MCI)
        b = _adb_run(adb, ["shell", "cmd", "connectivity", "airplane-mode", "disable"],
                     tries=2)
        time.sleep(20)
        if a is None or b is None or a.returncode != 0 or b.returncode != 0:
            if not quiet:
                print("  [adb] airplane-mode command rejected — falling back "
                      "to sleep backoff", flush=True)
            return False
        # --- تأیید واقعی تغییر IP (باگ 09-05: بدون این، وقتی ترافیک از WiFi
        # خانگی میرود نه گوشی، IP عوض نمیشد ولی True برمیگشت و اسکن روی بن ادامه میداد) ---
        ip_now = None
        for _ in range(4):                      # شبکه گوشی تا ~۳۰s بعد از airplane-off بالا می‌آید
            time.sleep(6)
            ip_now = _pub_ip()
            if ip_now:
                break
        if ip_now and ip_before and ip_now == ip_before:
            if not quiet:
                print(f"  [adb] IP UNCHANGED ({ip_now}) — NAT reused; falling back "
                      "to sleep backoff", flush=True)
            return False
        globals()["_ADB_LAST_IP"] = ip_now
        _ADB_ROTATED_AT = time.monotonic()
        print(f"  [adb] IP rotated via airplane-mode toggle → {ip_now or '?'}",
              flush=True)
        return True
    except Exception as e:
        # v9.7.2 — هر خطای غیرمنتظره به backoff می‌رود نه به بالا؛ در نسخهٔ پیشین
        # فقط دو مسیرِ خاص try/except داشتند و بقیه می‌توانست ترد کارگر را بکشد.
        if not quiet:
            print(f"  [adb] rotation aborted ({e}) — falling back to sleep backoff",
                  flush=True)
        return False
    finally:
        # v9.7.2 — حیاتی: پیش‌تر _wifi(True) فقط در مسیرهای خطای شناخته‌شده زده
        # می‌شد؛ استثنا یا کشته‌شدن پروسه میانِ توگل، Wi-Fi میزبان را خاموش
        # نگه می‌داشت (قطع اینترنت). اینجا تضمینی برگردانده می‌شود.
        if wifi_off:
            try:
                subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                    "Enable-NetAdapter -Name 'Wi-Fi' -Confirm:$false"],
                    capture_output=True, timeout=25,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            except Exception:
                pass
        _ADB_LOCK.release()


def _trigger_backoff(seconds=60):
    """Called by any worker that hit a 429: pauses the WHOLE pool safely.
    Escalates on repeated hits (60 -> 120 -> 240) so a hot WAF ban can reset.
    With ADB available, a fresh cell IP replaces the long cooldown (10s)."""
    global _BACKOFF_UNTIL, _BACKOFF_EVENTS
    rotated = rotate_ip_via_adb(quiet=True)
    with _BACKOFF_LOCK:
        _BACKOFF_EVENTS += 1
        if rotated:
            seconds = 10               # IP تازه سلولی — خنکسازی کوتاه و ادامه
        elif _BACKOFF_EVENTS > 2:
            seconds = min(240, 60 * (2 ** min(_BACKOFF_EVENTS - 2, 2)))
        new_until = time.time() + seconds
        if new_until > _BACKOFF_UNTIL:
            _BACKOFF_UNTIL = new_until
    print(f"  [backoff] 429 detected — global pause {seconds}s (event #{_BACKOFF_EVENTS})"
          + (" via ADB rotate" if rotated else ""), flush=True)


_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _parse_year_month(period_end):
    """'1404/06/31' -> (1404, 6) or (None, None).

    ارقامِ فارسی/عربی را هم می‌پذیرد: برخی گزارش‌های ماهانهٔ قدیمی period_end
    را با «۱۳۹۴/۰۹/۳۰» ذخیره کرده‌اند و int() خام روی آن شکست می‌خورد →
    year/month NULL می‌ماند و ix_ms_sym_ym برایشان بی‌فایده می‌شود.
    """
    try:
        s = str(period_end or "").translate(_FA_DIGITS)
        parts = s.split("/")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return None, None


# «گزارش فعالیت ماهانه دوره ۱ ماهه منتهی به ۱۳۹۴/۰۹/۳۰» — برخی ردیف‌های قدیمی
# period_end را NULL ذخیره کرده‌اند و تاریخ فقط در عنوان دیده می‌شود (گاهی با
# دو فاصله قبل از تاریخ). بدون این fallback، year/month برایشان NULL می‌ماند و
# ix_ms_sym_ym آن‌ها را پوشش نمی‌دهد.
_YM_IN_TITLE = re.compile(r"(\d{4})\s*/\s*(\d{1,2})")


def _ym_from_title(title):
    """سال/ماه را از عنوانِ گزارش ماهانه استخراج می‌کند یا (None, None)."""
    m = _YM_IN_TITLE.search(str(title or "").translate(_FA_DIGITS))
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def _period_from_title(title):
    """Extract period-end '1405/03/31' from a notice title, or None.

    Titles always carry the period: '...منتهی به ۱۴۰۴/۱۲/۲۹...' — parsing it
    lets us skip duplicate periods BEFORE any HTTP request."""
    t = norm(title)
    # Persian/Arabic digits -> ASCII (norm() keeps them native)
    t = t.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", t)
    if m:
        return f"{m.group(1)}/{int(m.group(2)):02d}/{int(m.group(3)):02d}"
    return None


def _deep_extract(rows, known_pe, known_ms_pe, fs_done, ms_done, conn):
    """Upsert notice rows + deep-extract FS/MS در new reports.
    scrape از codal.ir/Reports است که 429 نمیخورد (فقط search API) →
    گزارشهای هر نماد به صورت موازی scrape میشوند تا سرعت چند برابر شود.
    Returns (n_fs, n_ms)."""
    n_fs = n_ms = 0
    conn.executemany(NOTICE_UPSERT, rows)
    conn.commit()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _scrape_one(n):
        kind = kind_of(n[3])
        if kind == "Monthly Activity Report":
            pe_title = _period_from_title(n[3])
            if pe_title and pe_title in known_ms_pe:
                return None
            sess2 = make_session()
            try:
                vals, period_end = scrape_monthly_report(sess2, n[7])
            except Exception as e:
                print(f"  [worker] monthly failed {n[1]}: {e}")
                vals, period_end = {}, None
            if vals.get("monthly_revenue") is not None or vals.get("ytd_revenue") is not None:
                year = month = None
                if period_end:
                    mm = re.match(r"(\d{4})[-/](\d{1,2})", str(period_end))
                    if mm:
                        year, month = int(mm.group(1)), int(mm.group(2))
                return ("ms", (n[0], n[1], n[3], period_end, year, month,
                               vals.get("monthly_revenue"),
                               vals.get("ytd_revenue"),
                               vals.get("monthly_revenue_prev"),
                               vals.get("ytd_revenue_prev"),
                               vals.get("monthly_volume"),
                               vals.get("ytd_volume"),
                               vals.get("volume_unit"), n[9], n[10]))
            return None
        elif kind == "Financial Statements":
            pe_title = _period_from_title(n[3])
            if pe_title and pe_title in known_pe:
                print(f"  [worker] {n[1]}: skip FS dup {pe_title}")
                return None
            sess2 = make_session()
            try:
                vals, meta, unit = scrape_report(sess2, n[7])
            except Exception as e:
                print(f"  [worker] FS scrape failed {n[1]}: {e}")
                vals, meta, unit = {}, {}, None
            if vals.get("revenue") is not None:
                pe = meta.get("end")
                if pe and pe in known_pe:
                    print(f"  [worker] {n[1]}: skip duplicate period {pe}")
                    return None
                return ("fs", (n[0], n[1], n[2], n[3], kind, meta.get("period"),
                               meta.get("end"), n[5])
                        + tuple(vals.get(k) for k in FS_KEYS)
                        + (unit, n[7], now)
                        + fs_derived(n[3], meta.get("end"), unit,
                                     meta.get("is_consolidated")))
            return None
        return None

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as _ex:
        for res in _ex.map(_scrape_one, rows):
            if res:
                results.append(res)
    for kind, row in results:
        if kind == "ms":
            conn.execute(MS_UPSERT, row)
            n_ms += 1
        else:
            conn.execute(FS_UPSERT, row)
            n_fs += 1
    conn.commit()
    return n_fs, n_ms


def dedupe_symbol(sym):
    """Task 2 — النشاف (ابتکار قرابة پس از next scrape): هر period_end فقط آخرین tracing_no
    (اصلاحیه) بماند. خروجی: (n_fs_removed, n_ms_removed) — بدون آسیب به حاشیه."""
    conn = sqlite3.connect(DB_PATH, timeout=60, isolation_level=None)
    try:
        removed = removed_ms = 0
        # FTS jozve basis = STANDALONE (غیرتلفیقی). Per period_end keep the
        # standalone row when one exists, else the consolidated; tie-break on the
        # latest tracing_no (اصلاحیه). Previously this kept MAX(tracing_no)
        # blindly, which could delete the standalone row and keep a consolidated
        # one — the opposite of the required basis.
        keep = {}
        for pe, tno, consol in conn.execute(
                "SELECT period_end, tracing_no, COALESCE(is_consolidated,0) "
                "FROM financial_statements WHERE symbol=? AND period_end IS NOT NULL",
                (sym,)).fetchall():
            cur = keep.get(pe)
            # prefer lower is_consolidated (0=standalone), then higher tracing_no
            if cur is None or (consol, -tno) < (cur[1], -cur[0]):
                keep[pe] = (tno, consol)
        for pe, (tno, _c) in keep.items():
            cur = conn.execute(
                "DELETE FROM financial_statements WHERE symbol=? AND period_end=? AND tracing_no<>?",
                (sym, pe, tno))
            removed += cur.rowcount
        latest_ms = dict(conn.execute(
            "SELECT period_end, MAX(tracing_no) FROM monthly_sales "
            "WHERE symbol=? AND period_end IS NOT NULL GROUP BY period_end", (sym,)).fetchall())
        for pe, mx in latest_ms.items():
            cur = conn.execute(
                "DELETE FROM monthly_sales WHERE symbol=? AND period_end=? AND tracing_no<>?",
                (sym, pe, mx))
            removed_ms += cur.rowcount
        conn.commit()
        return removed, removed_ms
    finally:
        conn.close()


def update_symbol_incremental(sym, sess):
    """Task 2 — Dynamic Updater (per-symbol delta):
    FromDate = آخرین publish_date DB (نرمالشده) → فقط اسناد پس از آن (اصلاحیهها/جدیدها).
    بعد از شستشو: dedupe → تثبیت 5-index (با بازیابی در app.py)."""
    conn = sqlite3.connect(DB_PATH, timeout=60)
    r = conn.execute("SELECT MAX(publish_date) FROM codal_notices WHERE symbol=?", (sym,)).fetchone()
    has_fs = conn.execute("SELECT 1 FROM financial_statements WHERE symbol=? LIMIT 1", (sym,)).fetchone()
    has_ms = conn.execute("SELECT 1 FROM monthly_sales WHERE symbol=? LIMIT 1", (sym,)).fetchone()
    conn.close()
    if not (has_fs or has_ms):
        return _process_symbol(sym, sess)   # تازهکار → full discovery via _process_symbol
    from_date = None
    if r and r[0]:
        v = str(r[0]).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
        from_date = v[:10]
    n_notices = 0
    for cat in ("1", "3"):
        q = dict(QUERY, Symbol=sym, Category=cat, LetterType="-1")
        if from_date:
            q["FromDate"] = from_date
        rows = fetch_page(sess, 1, q, quiet=True, max_429_retries=2)
        if rows is None:
            continue
        new_rows = []
        for x in rows:
            t = x.get("TracingNo")
            if t is None:
                continue
            title = (x.get("Title") or "").strip()
            if SAVE_USEFUL_ONLY and not _positive_title(title):
                continue
            pdf_raw = (x.get("PdfUrl") or "").strip()
            excel_raw = (x.get("ExcelUrl") or "").strip()
            if pdf_raw and not pdf_raw.startswith("http"):
                pdf_raw = "https://codal.ir/" + pdf_raw
            if excel_raw and not excel_raw.startswith("http"):
                excel_raw = "https://codal.ir/" + excel_raw
            new_rows.append((t, (x.get("Symbol") or "").strip(),
                             (x.get("CompanyName") or "").strip(), title,
                             (x.get("LetterCode") or "").strip(),
                             _norm_date(x.get("PublishDateTime")),
                             _norm_date(x.get("SentDateTime")),
                             "https://codal.ir" + (x.get("Url") or ""),
                             datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                             pdf_raw, excel_raw))
        if new_rows:
            c2 = sqlite3.connect(DB_PATH, timeout=60, isolation_level=None)
            try:
                known_pe = {r0[0] for r0 in c2.execute(
                    "SELECT DISTINCT period_end FROM financial_statements WHERE symbol=?", (sym,))}
                known_ms_pe = {r0[0] for r0 in c2.execute(
                    "SELECT DISTINCT period_end FROM monthly_sales WHERE symbol=?", (sym,))}
                nf, nm = _deep_extract(new_rows, known_pe, known_ms_pe, set(), set(), c2)
                n_notices += nf + nm
            finally:
                c2.close()
    # بعد از هر موجة جدید: dedupe تا 5-index پایدار بماند
    try:
        removed, removed_ms = dedupe_symbol(sym)
        n_notices += removed + removed_ms
    except Exception:
        pass
    return n_notices, 0, 0


def _process_symbol(sym, sess):
    """Per-symbol targeted scan (Laser-Scan).

    PROBE-VERIFIED (خساپا, real Codal API): page 1 of Category=1 returns 20
    notices of which ~15 are real financial statements covering 8 unique
    periods — far more than the 3 recent periods the playbook needs. Page 1 of
    Category=3 returns 20 monthly reports (~1.7 years). So ONE page per
    category is sufficient; fetching page 2+ only re-fetches old duplicates.

    Returns (n_notices, n_fs, n_ms): new notices upserted, financial statements
    extracted, monthly-sales rows extracted for this symbol."""
    n_notices = n_fs = n_ms = 0
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Every symbol gets an independent vote: whether THIS symbol hit a hard 429
    # (not some earlier worker) decides the shared gate in main().
    global _LAST_429
    _LAST_429 = False

    # Already-known tracing numbers + period_ends (skip duplicate HTTP requests)
    conn = sqlite3.connect(DB_PATH, timeout=60, isolation_level=None)
    try:
        known = {r[0] for r in conn.execute(
            "SELECT tracing_no FROM codal_notices WHERE symbol=?", (sym,))}
        known_pe = {r[0] for r in conn.execute(
            "SELECT DISTINCT period_end FROM financial_statements WHERE symbol=?", (sym,))}
        known_ms_pe = {r[0] for r in conn.execute(
            "SELECT DISTINCT period_end FROM monthly_sales WHERE symbol=?", (sym,))}
        fs_done = {r[0] for r in conn.execute(
            "SELECT tracing_no FROM financial_statements WHERE symbol=?", (sym,))}
        ms_done = {r[0] for r in conn.execute(
            "SELECT tracing_no FROM monthly_sales WHERE symbol=?", (sym,))}
    finally:
        conn.close()

    # اگر همه اطلاعیههای شناختهشده قبلاً استخراج شدهاند، search لازم نیست
    # (سریع رد شو — صفر درخواست HTTP به search API)
    pool_all = []
    try:
        c2 = sqlite3.connect(DB_PATH, timeout=60, isolation_level=None)
        pool_all = [tuple(r) for r in c2.execute(
            "SELECT tracing_no, symbol, company_name, title, letter_code,"
            " publish_date, sent_date, url, fetched_at, pdf_url, excel_url"
            " FROM codal_notices WHERE symbol=? ORDER BY publish_date DESC", (sym,))]
        c2.close()
    except Exception:
        pass
    if pool_all:
        need_fs = any(kind_of(n[3]) == "Financial Statements" and n[0] not in fs_done for n in pool_all)
        need_ms = any(kind_of(n[3]) == "Monthly Activity Report" and n[0] not in ms_done for n in pool_all)
        if not need_fs and not need_ms:
            return 0, 0, 0, "done"  # کاملاً استخراجشده — بدون هیچ درخواستی

    categories = {"1": "Financial Statements", "3": "Monthly Activity Report"}
    cat1_empty = False  # skip cat3 when cat1 has no letters (DB-proven 0 monthly-without-FS)
    rows = []
    sym_blocked = False  # 429 در همین نماد؟ — وضعیت محلی، بدون پرچم سراسری
    # اگر نماد اطلاعیه دارد، search API نمیزنیم (همیشه 429 میخورد) —
    # مستقیم از notices موجود scrape میکنیم که 429 نمیخورد.
    if known:
        rows = pool_all  # fallback scrape مستقیم، بدون search
    else:
        for cat, cat_name in categories.items():
            if cat == "3" and cat1_empty:
                break  # DB-verified: no symbol has monthly reports without FS notices
            q = dict(QUERY, Symbol=sym, Category=cat, LetterType="-1")
            for page in (1,):  # فقط صفحه ۱ — ثابتشده کافی است (probe واقعی)
                _jitter()  # جیتر محافظهکارانه — WAF آرام
                letters = fetch_page(sess, page, q, quiet=True, max_429_retries=2)
                # در بن، نماد را فوراً رها نکن (اینطوری ~۱۷۵۰ نماد بدون اطلاعیه
                # برای همیشه میمانند): تا ۵ دور صبر+retry — بن کدال ~۲۰-۳۰
                # دقیقه است و بعد از lift شدن، سریال جواب میدهد.
                r_try = 0
                while letters is None and r_try < 5:
                    r_try += 1
                    if _wait_if_backing_off() == "stop":   # کاربر توقف زده
                        break
                    _jitter()
                    letters = fetch_page(sess, page, q, quiet=True, max_429_retries=2)
                if letters is None:  # 429 ماندگار — پس از ۵ دور، رها کن
                    sym_blocked = True
                    break
                if not letters:
                    if cat == "1":
                        cat1_empty = True
                    break
                for x in letters:
                    t = x.get("TracingNo")
                    if t is None or t in known:
                        continue
                    # whitelist خودآموز: عنوان نامطبوع → همانجا رد (بدون scrape)
                    if SAVE_USEFUL_ONLY and not _positive_title(x.get("Title") or ""):
                        continue
                    known.add(t)
                    pdf_raw = (x.get("PdfUrl") or "").strip()
                    excel_raw = (x.get("ExcelUrl") or "").strip()
                    if pdf_raw and not pdf_raw.startswith("http"):
                        pdf_raw = "https://codal.ir/" + pdf_raw
                    if excel_raw and not excel_raw.startswith("http"):
                        excel_raw = "https://codal.ir/" + excel_raw
                    rows.append((t, sym, (x.get("CompanyName") or "").strip(),
                                 (x.get("Title") or "").strip(),
                                 (x.get("LetterCode") or "").strip(),
                                 _norm_date(x.get("PublishDateTime")),
                                 _norm_date(x.get("SentDateTime")),
                                 "https://codal.ir" + (x.get("Url") or ""), now,
                                 pdf_raw, excel_raw))
    if not rows:
        # Fallback: no new notices via API — scrape existing notices that
        # still lack extracted data (search API 429-blocked, scrape still OK).
        conn = sqlite3.connect(DB_PATH, timeout=60, isolation_level=None)
        try:
            pool = [tuple(r) for r in conn.execute(
                "SELECT tracing_no, symbol, company_name, title, letter_code,"
                " publish_date, sent_date, url, fetched_at, pdf_url, excel_url"
                " FROM codal_notices WHERE symbol=? ORDER BY publish_date DESC", (sym,))]
            fs_done = {r[0] for r in conn.execute(
                "SELECT tracing_no FROM financial_statements WHERE symbol=?", (sym,))}
            ms_done = {r[0] for r in conn.execute(
                "SELECT tracing_no FROM monthly_sales WHERE symbol=?", (sym,))}
        finally:
            conn.close()
        fs_targets = [n for n in pool if kind_of(n[3]) == "Financial Statements" and n[0] not in fs_done]
        ms_targets = [n for n in pool if kind_of(n[3]) == "Monthly Activity Report" and n[0] not in ms_done]
        if fs_targets or ms_targets:
            rows = pool  # inject into the extraction loop below (dedup by kind skips done)
            print(f"  [worker] {sym}: API blocked — scraping {len(fs_targets)} FS + {len(ms_targets)} monthly from {len(pool)} existing notices", flush=True)
    if not rows:
        return 0, 0, 0, ("blocked" if sym_blocked else "empty")

    # Smart-report: چه نسبتی از اطلاعیهها واقعاً مفید است (بدون باز کردن URL)
    useful = sum(1 for r in rows if kind_of(r[3]))
    print(f"  [worker] {sym}: {len(rows)} notices, {useful} useful "
          f"({useful * 100 // max(len(rows), 1)}%) — extracting ...")

    conn = sqlite3.connect(DB_PATH, timeout=60, isolation_level=None)
    try:
        n_fs, n_ms = _deep_extract(rows, known_pe, known_ms_pe, fs_done, ms_done, conn)
    finally:
        conn.close()
    return len(rows), n_fs, n_ms, (("new" if (n_fs or n_ms)
                                    else ("blocked" if sym_blocked else "empty")))


def _is_derivative(sym, name):
    """مشتقهها (اختیار معامله / حق تقدم / ضهرم) در کدال نماد شرکتی ندارند —
    جستجویشان فقط درخواست بیفایده به WAF است. ملحقات کنار گذاشته میشوند."""
    x = norm(str(sym or ""))
    n = norm(str(name or ""))
    if re.search(r"اختيار|اختیار|ضهرم", x):
        return True
    # ض+نام پایه+سررسید (ضهمن5025) — مشتقههای سهام پایه
    if re.match(r"^ض[آ-ی]{2,6}\d{4}$", x):
        return True
    if re.search(r"حق تقدم|حق خرید|حق پذیره|پذیره نویسی", n):
        return True
    if "-" in x:
        return True
    if x.startswith("حق") or x.startswith("ح ") or x.startswith("ت ع"):
        return True
    return False


def _is_fund(sym, name):
    """صندوقهای سرمایهگذاری/مشتقههای صندوقمحور: صورت مالی دورهای (Category 1)
    ندارند — فقط «پورتفوی»/«گزارش عملکرد» که برای تحلیل مالی استفاده نمیشود."""
    n = norm(str(name or ""))
    if "صندوق" in n or "مشترک" in n:
        return True
    # صندوقهای «بخشی» و «بازارگردانی» (نام شرکت «بخشی صنایع…»، «اختصاصی بازارگردانی…»)
    if re.search(r"بخشی|بازارگردانی|گواهی.?سپرده|تأمین سرمایه", n):
        return True
    return False


def feed_sync(mode="update", optimized=False):
    """Smart GLOBAL-FEED sync — جایگزین جستجوی نماد-به-نماد.

    کشف 2026-08-27 (browser-verified): search.codal.ir/api/search/v2/q با
    Category=1 بدون فیلتر نماد، ALL صورتهای مالی کل بازار را برمیگرداند
    (Total=196,029؛ صفحهبندی 20 تایی، جدیدترین اول، بدون 429 در مرورگر) و
    FromDate=1404/01/01 (شمسی با /) بازه را محدود میکند (Category=3: 138k).

    mode="update":   FromDate = max(publish_date) دیتابیس → هر اطلاعیهٔ جدید
                     بازار-wide (هر دو دسته 1+3) با چند صفحه گرفته میشود —
                     جایگزین ~۷۵۰ کوئری نماد-به-نماد حالت --update قدیم.
    mode="discover": FromDate=1400/01/01 (پنج سال اخیر) → همهٔ اطلاعیههای
                     مالی که نداریم مستقیم دانلود/استخراج میشوند — جایگزین
                     چرخهٔ ۲۱۳۲ پراب خالی discovery قدیم (96.6% empty).
    """
    global _BACKOFF_UNTIL, _BACKOFF_EVENTS
    _BACKOFF_UNTIL, _BACKOFF_EVENTS = 0.0, 0
    _FA = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

    print(f"=== Global-feed Codal sync (mode={mode}) ===")
    conn = sqlite3.connect(DB_PATH, timeout=60, isolation_level=None)
    create_schema(conn)
    migrate_schema(conn)
    known = {r[0] for r in conn.execute("SELECT tracing_no FROM codal_notices")}
    known_pe = {r[0] for r in conn.execute("SELECT DISTINCT period_end FROM financial_statements")}
    known_ms_pe = {r[0] for r in conn.execute("SELECT DISTINCT period_end FROM monthly_sales")}
    fs_done = {r[0] for r in conn.execute("SELECT tracing_no FROM financial_statements")}
    ms_done = {r[0] for r in conn.execute("SELECT tracing_no FROM monthly_sales")}
    if mode == "update":
        max_dt = conn.execute("SELECT MAX(publish_date) FROM codal_notices").fetchone()[0]
        from_date = ((max_dt or "")[:10]).translate(_FA) or "1400/01/01"
        cats = ["1", "3"]
        page_budget = 50
        if optimized:
            page_budget = 8   # بهینه: فقط آخرین صفحه‌های فید (تغییرپذیر) — ۶ برابر درخواست کمتر
        # تعداد نمادهای موجود که بروزرسانی می‌شوند (پوشش ۵ شاخصی)
        n_syms = conn.execute(
            "SELECT COUNT(DISTINCT symbol) FROM financial_statements").fetchone()[0]
        label = f"بروزرسانی نمادهای موجود ({n_syms} نماد) از {from_date}"
        if optimized:
            label += " [حالت بهینه: فقط داده‌های تغییرپذیر]"
    else:
        from_date = "1400/01/01"
        cats = ["1", "3"]
        page_budget = 120
        n_syms = conn.execute(
            "SELECT COUNT(DISTINCT symbol) FROM financial_statements").fetchone()[0]
        label = f"کشف از فید سراسری (۵ سال اخیر) — {n_syms} نماد موجود"
    conn.close()

    sess = make_session()
    counters = {"notices": 0, "fs": 0, "ms": 0, "pages": 0}
    total_pages = page_budget * len(cats)
    write_progress("codal_sync", f"{label} — شروع...", total_pages, 0, "")
    for cat in cats:
        page = 1
        cat_notices = 0
        while page <= page_budget:
            c = _control_cmd()
            if c == "stop":
                write_progress("codal_stopped", "اسکن توسط کاربر متوقف شد", 100, page, "")
                print("=== Feed sync stopped by user ===", flush=True)
                return
            while c == "pause":
                write_progress("codal_paused",
                               f"اسکن در حال مکث است (دسته {cat}، صفحه {page}) — برای ادامه دکمه ادامه را بزنید",
                               100, page, "")
                time.sleep(5)
                c = _control_cmd()
                if c == "stop":
                    write_progress("codal_stopped", "اسکن توسط کاربر متوقف شد", 100, page, "")
                    return
            q = {"Audited": "true", "AuditorRef": "-1", "Category": cat,
                 "Childs": "true", "CompanyState": "-1", "CompanyType": "-1",
                 "Consolidatable": "true", "IsNotAudited": "false", "Length": "-1",
                 "LetterType": "-1", "Mains": "true", "NotAudited": "true",
                 "NotConsolidatable": "true", "PageNumber": str(page),
                 "Publisher": "false", "ReportingType": "-1", "TracingNo": "-1",
                 "search": "false", "FromDate": from_date}
            _jitter()
            letters = fetch_page(sess, page, q, quiet=False, max_429_retries=2)
            if letters is None:
                print(f"  [feed] cat{cat} page {page}: blocked — pausing feed scan", flush=True)
                # FIX: بدون این، sync_status.json در state «codal_sync» میماند و UI
                # تا ابد «در حال بروزرسانی» را نشان میدهد (اسکن مرده از صبح)
                write_progress("codal_stopped",
                               f"اسکن متوقف شد: محدودیت موقت Codal (429) — بعداً دوباره امتحان کنید",
                               100, page, "")
                break
            if not letters:
                print(f"  [feed] cat{cat} page {page}: empty — end of feed", flush=True)
                break
            new_rows = []
            for x in letters:
                t = x.get("TracingNo")
                if t is None or t in known:
                    continue
                title = (x.get("Title") or "").strip()
                if SAVE_USEFUL_ONLY and not _positive_title(title):
                    continue
                known.add(t)
                pdf_raw = (x.get("PdfUrl") or "").strip()
                excel_raw = (x.get("ExcelUrl") or "").strip()
                if pdf_raw and not pdf_raw.startswith("http"):
                    pdf_raw = "https://codal.ir/" + pdf_raw
                if excel_raw and not excel_raw.startswith("http"):
                    excel_raw = "https://codal.ir/" + excel_raw
                new_rows.append((t, (x.get("Symbol") or "").strip(),
                                 (x.get("CompanyName") or "").strip(), title,
                                 (x.get("LetterCode") or "").strip(),
                                 _norm_date(x.get("PublishDateTime")),
                                 _norm_date(x.get("SentDateTime")),
                                 "https://codal.ir" + (x.get("Url") or ""),
                                 datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                 pdf_raw, excel_raw))
            counters["pages"] += 1
            if new_rows:
                counters["notices"] += len(new_rows)
                conn2 = sqlite3.connect(DB_PATH, timeout=60, isolation_level=None)
                try:
                    nf, nm = _deep_extract(new_rows, known_pe, known_ms_pe,
                                           fs_done, ms_done, conn2)
                    counters["fs"] += nf
                    counters["ms"] += nm
                finally:
                    conn2.close()
            cat_notices += len(new_rows)
            print(f"  [feed] cat{cat} page {page}: +{len(new_rows)} new "
                  f"(fs={counters['fs']} ms={counters['ms']} new={counters['notices']})",
                  flush=True)
            write_progress("codal_sync",
                           f"{label} — دسته {cat} صفحه {page}/{page_budget} | {counters['notices']} اطلاعیهٔ جدید، "
                           f"FS: {counters['fs']}، ماهانه: {counters['ms']}",
                           total_pages, counters["pages"] + page, "")
            # مرز دادههای شناختهشده: فقط اگر این صفحه کاملاً تکراری باشد (هر ۲۵ رکورد known)
            if len(new_rows) == 0 and page >= 2:
                print(f"  [feed] cat{cat} boundary reached at page {page}", flush=True)
                break
            page += 1
    print(f"=== Feed sync done: {counters['notices']} new notices, "
          f"{counters['fs']} FS, {counters['ms']} monthly "
          f"({counters['pages']} pages) ===", flush=True)


def repair_broken_rows(limit=None):
    """حالت ترمیم کیفیت: ردیف‌های MS/FS که وجود دارند ولی مبالغ کلیدی‌شان NULL است
    را دوباره scrape میکند (پارسرهای جدید، بانک/جمع‌ردیفی را میفهمند).
    این باگ «ردیف هست ولی خالی» را که feed عادی هرگز ترمیم نمیکند، صاف میکند."""
    conn = sqlite3.connect(DB_PATH, timeout=60, isolation_level=None)
    s = make_session()
    ms = conn.execute(
        "SELECT ms.tracing_no, cn.url FROM monthly_sales ms "
        "JOIN codal_notices cn ON cn.tracing_no = ms.tracing_no "
        "WHERE ms.monthly_revenue IS NULL AND ms.ytd_revenue IS NULL"
        + (f" LIMIT {int(limit)}" if limit else "")).fetchall()
    print(f"[repair] MS بدون مبلغ: {len(ms)}", flush=True)
    ok = 0
    for t, url in ms:
        try:
            vals, _pe = scrape_monthly_report(s, url)
        except Exception:
            continue
        mv, yv = vals.get("monthly_revenue"), vals.get("ytd_revenue")
        if mv is not None or yv is not None:
            conn.execute(
                "UPDATE monthly_sales SET monthly_revenue=?, ytd_revenue=?, "
                "monthly_revenue_prev=?, ytd_revenue_prev=? WHERE tracing_no=?",
                (mv, yv, vals.get("monthly_revenue_prev"), vals.get("ytd_revenue_prev"), t))
            ok += 1
        time.sleep(0.4)
    print(f"[repair] MS ترمیم شد: {ok}", flush=True)
    fs = conn.execute(
        "SELECT f.tracing_no, cn.url FROM financial_statements f "
        "JOIN codal_notices cn ON cn.tracing_no = f.tracing_no "
        "WHERE f.revenue IS NULL AND f.net_profit IS NULL AND f.basic_eps IS NULL"
        + (f" LIMIT {int(limit)}" if limit else "")).fetchall()
    print(f"[repair] FS بدون هیچ فیلد کلیدی: {len(fs)}", flush=True)
    ok2 = 0
    for t, url in fs:
        try:
            out, _meta, _unit = scrape_report(s, url)
        except Exception:
            continue
        if out and (out.get("revenue") or out.get("net_profit") or out.get("basic_eps")):
            conn.execute(
                "UPDATE financial_statements SET revenue=?, gross_profit=?, operating_profit=?, "
                "net_profit=?, total_assets=?, total_liabilities=?, total_equity=?, capital=?, "
                "retained_earnings=?, basic_eps=? WHERE tracing_no=?",
                (out.get("revenue"), out.get("gross_profit"), out.get("operating_profit"),
                 out.get("net_profit"), out.get("total_assets"), out.get("total_liabilities"),
                 out.get("total_equity"), out.get("capital"), out.get("retained_earnings"),
                 out.get("basic_eps"), t))
            ok2 += 1
        time.sleep(0.4)
    print(f"[repair] FS ترمیم شد: {ok2}", flush=True)
    conn.close()
    return ok, ok2


def rebuild_fs(limit=None, symbols=None, polite=None, latest_only=False, workers=None,
               resume_since=None):
    """بازسازیِ از نوِ financial_statements با پارسرِ اصلاح‌شدهٔ «نام‌محور /
    مبنای غیرتلفیقی».

    چرا این لازم است: پارسرِ قدیمی فقط ۶ شیتِ اولِ کرک‌شونده را می‌خواند و
    «اولین ردیفِ درآمدی» را برمی‌داشت؛ برای هلدینگ‌ها این یعنی «درآمد سود
    سهام» به‌جای «جمع درآمدهای عملیاتی»، و چون شیتِ غیرتلفیقی (sheetId=1) هرگز
    در ۶ گزینهٔ اول نبود، مبنای تلفیقی ذخیره می‌شد. حالا هر نامهٔ در دسترس
    دوباره scrape می‌شود و هم مبالغ و هم مبنای واقعی (is_consolidated) جایگزین
    می‌گردد.

    قراردادِ ایمنی: نامه‌هایی که «خطای سیستمی» می‌دهند یا datasource ندارند
    SKIP می‌شوند و ردیفِ موجود دست‌نخورده می‌ماند (فقط مُهرِ زمانیِ fetched_at
    تازه می‌شود، که معنایش «این نامه خوانده شد» است نه «داده تغییر کرد») —
    هرگز عدد جعلی نمی‌سازیم و
    هرگز مقدار را به صفر/NULL برگردانده «تمیز» نمی‌کنیم. فقط ردیفی به‌روز
    می‌شود که revenue واقعاً parse شده باشد. idempotent و قابلِ ازسرگیری.

    workers: تعدادِ درخواست‌های همزمان (پیش‌فرض ۴؛ با --polite ۱؛ سقف ۶).
    resume_since: «%Y-%m-%d %H:%M:%S» — نامه‌هایی که بعد از آن لحظه خوانده شده‌اند
    (fetched_at تازه) رد می‌شوند؛ برای ادامه‌دادنِ اجرای قطع‌شده بدون تکرارِ شبکه.
    """
    if polite is None:
        polite = 1.7 if POLITE else 0.4
    # ستونِ fetched_at در این جدول «آخرین خواندنِ واقعی از کدال» است؛ قالبش با
    # بقیهٔ مسیرها (%Y-%m-%d %H:%M:%S) یکی می‌ماند تا مقایسهٔ متنیِ --resume-since
    # درست بماند.
    refetch_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if resume_since:
        resume_since = resume_since.replace("T", " ")
    conn = sqlite3.connect(DB_PATH, timeout=60, isolation_level=None)
    if latest_only:
        # Only the NEWEST FS letter per symbol — the row the FTS screen and the
        # fundamental table actually display. Codal is currently degraded
        # (~45-90s per Decision.aspx, proven server-side not IP-throttle), so a
        # full 8324-letter historical rebuild cannot finish in one night; this
        # maximises corrected symbol coverage within the latency budget.
        q = ("SELECT f.tracing_no, f.symbol, cn.url, f.revenue, f.is_consolidated "
             "FROM financial_statements f "
             "JOIN codal_notices cn ON cn.tracing_no = f.tracing_no "
             "JOIN (SELECT symbol, MAX(tracing_no) AS mt FROM financial_statements "
             "      GROUP BY symbol) m ON m.mt = f.tracing_no "
             "WHERE cn.url IS NOT NULL")
    else:
        q = ("SELECT f.tracing_no, f.symbol, cn.url, f.revenue, f.is_consolidated "
             "FROM financial_statements f "
             "JOIN codal_notices cn ON cn.tracing_no = f.tracing_no "
             "WHERE cn.url IS NOT NULL")
    params = []
    if symbols:
        q += f" AND f.symbol IN ({','.join('?' * len(symbols))})"
        params += list(symbols)
    if resume_since:
        # هر نامه‌ای که بعد از این لحظه دوباره scrape شده، fetched_at‌اش تازه شده؛
        # پس از‌سرگیریِ اجراهای قطع‌شده بدون تکرارِ درخواست‌های بی‌فایده.
        q += " AND (f.fetched_at IS NULL OR f.fetched_at < ?)"
        params.append(resume_since)
    q += " ORDER BY f.tracing_no DESC" if latest_only else " ORDER BY f.tracing_no"
    if limit:
        q += f" LIMIT {int(limit)}"
    rows = conn.execute(q, params).fetchall()
    print(f"[rebuild-fs] candidates: {len(rows)} "
          f"({len(symbols) if symbols else 'all'} symbol scope"
          f"{', latest-per-symbol' if latest_only else ''})", flush=True)
    if workers is None:
        workers = 1 if POLITE else 4
    workers = max(1, min(int(workers), 6))
    print(f"[rebuild-fs] workers: {workers}", flush=True)

    _tls = threading.local()

    def _fetch(item):
        """شبکه فقط. یک session به‌ازایِ ترد (نه session مشترکِ چندتردی)."""
        t, sym, url, old_rev, old_consol = item
        # حالتِ --polite (IP ثابتِ بدون ADB) همان مکثِ بین‌نامه‌ای را نگه می‌دارد؛
        # در حالتِ عادی ریتمِ کارگر خودش خودش را تنظیم می‌کند.
        if POLITE:
            time.sleep(polite)
        s = getattr(_tls, "s", None)
        if s is None:
            s = _tls.s = make_session()
        try:
            return item, scrape_report(s, url)
        except Exception:
            return item, None

    def _stamp(t, has_os):
        # fetched_at = «آخرین خواندنِ واقعیِ این نامه از کدال». حتی نامه‌ای که
        # دیتاسورس ندارد یا درآمدش منفی است خوانده شده، پس مُهر می‌خورد و در
        # از‌سرگیریِ --resume-since دوباره بارگذاری نمی‌شود؛ فقط استثنا/خطای
        # شبکه مُهر نمی‌خورد تا حتماً دوباره امتحان شود.
        # has_os=None یعنی «نمی‌دانیم» → مقدارِ شناخته‌شدهٔ قبلی پاک نمی‌شود.
        conn.execute("UPDATE financial_statements SET fetched_at=?, "
                     "has_operating_sales=COALESCE(?,has_operating_sales) "
                     "WHERE tracing_no=?", (refetch_ts, has_os, t))

    def _apply(item, res):
        """همهٔ نوشتن‌ها رویِ تردِ اصلی (تک‌نویسنده) + همان قراردادِ ایمنیِ قبلی.
        بازگشت: 'changed' | 'skipped' | 'neg' | 'error'"""
        t, sym, url, old_rev, old_consol = item
        if res is None:
            return "error"
        out, meta, unit = res
        if out.get("revenue") is not None:
            has_os = 1
        elif meta.get("has_income"):
            # شیتِ سود و زیان خوانده شد ولی هیچ الگوی «درآمد عملیاتی» مچ نشد:
            # این «نبودِ مفهومِ فروش» است، نه «نبودِ داده».
            has_os = 0
        else:
            has_os = None
        _stamp(t, has_os)
        # system-error page / no datasource -> out empty or no revenue: SKIP
        if not out or out.get("revenue") is None:
            return "skipped"
        # SAFEGUARD: a negative «جمع درآمدهای عملیاتی» means a bank / financial
        # institution, whose operating-revenue total is net of interest expense
        # and can legitimately go negative. That is NOT the jozve's industrial
        # «فروش / درآمد عملیاتی» concept, so we must not overwrite the row with
        # it — skip and leave the existing value intact (never corrupt, never
        # fabricate). Banks lack a «سود ناخالص» row anyway, so the FTS margin
        # screen already excludes them via gross_profit = NULL.
        if out.get("revenue") < 0:
            return "neg"
        consol = 1 if meta.get("is_consolidated") else 0
        # Income-statement fields are replaced WHOLESALE so a basis switch
        # (consolidated -> standalone) never leaves a mixed-basis row (e.g. a
        # stale consolidated gross_profit sitting beside a standalone revenue).
        # Balance-sheet fields use COALESCE(new, old) so a letter whose standalone
        # balance sheet is missing/unreachable can never null out good existing
        # data — we only ever improve them.
        conn.execute(
            "UPDATE financial_statements SET revenue=?, gross_profit=?, operating_profit=?, "
            "net_profit=?, basic_eps=?, "
            "total_assets=COALESCE(?,total_assets), "
            "total_liabilities=COALESCE(?,total_liabilities), "
            "total_equity=COALESCE(?,total_equity), capital=COALESCE(?,capital), "
            "retained_earnings=COALESCE(?,retained_earnings), "
            "is_consolidated=?, unit_norm=COALESCE(?,unit_norm) WHERE tracing_no=?",
            (out.get("revenue"), out.get("gross_profit"), out.get("operating_profit"),
             out.get("net_profit"), out.get("basic_eps"),
             out.get("total_assets"), out.get("total_liabilities"),
             out.get("total_equity"), out.get("capital"), out.get("retained_earnings"),
             consol, _classify_unit(unit), t))
        if old_rev != out.get("revenue") or (old_consol or 0) != consol:
            print(f"  [{sym}] {t}: revenue {old_rev} -> {out.get('revenue')} | "
                  f"consol {old_consol}->{consol} | gross={out.get('gross_profit')}", flush=True)
            return "changed"
        return "same"

    changed = skipped = errors = skipped_neg = same = done = 0
    total = len(rows)
    t0 = time.monotonic()
    stopped = False
    # چرا همزمانی: تأخیرِ کدال per-request و سمتِ سرور است (۱۷-۱۲۳ ثانیه روی
    # Decision.aspx؛ چرخشِ IP با ADB هیچ‌کدام را کم نکرد، پس گلوگاه لوکال نیست).
    # تنها اهرمِ باقی‌مانده روی‌هم‌انداختنِ همان انتظارهاست. ورکرها فقط I/O
    # می‌کنند و تک‌نویسندهٔ SQLite حفظ می‌شود، بنابراین idempotency و قراردادِ
    # skip هیچ‌کدام تغییر نمی‌کنند.
    #
    # shutdown(cancel_futures=True) لازم است چون فهرست ~۱۰۰۰ نامه یک‌جا submit
    # می‌شود؛ بدون آن، «توقف» یا هر استثنا روی صفِ ~۹۵۰ درخواستِ در انتظار می‌ماند
    # و فرآیند ساعت‌ها تمام نمی‌شود.
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=workers)
    futs = []
    try:
        futs = [ex.submit(_fetch, r) for r in rows]
        for fut in concurrent.futures.as_completed(futs):
            item, res = fut.result()
            done += 1
            state = _apply(item, res)
            if state == "changed":
                changed += 1
            elif state == "skipped":
                skipped += 1
            elif state == "neg":
                skipped_neg += 1
            elif state == "error":
                errors += 1
            else:
                same += 1
            if done % 10 == 0 or done == total:
                hr = done / max(time.monotonic() - t0, 1e-9) * 3600
                eta = (total - done) / max(hr, 1e-9)
                print(f"[rebuild-fs] {done}/{total} | {hr:.0f}/h | ETA {eta:.1f}h | "
                      f"changed={changed} same={same} skipped={skipped} "
                      f"neg={skipped_neg} errors={errors}", flush=True)
            if _control_cmd() == "stop":
                stopped = True
                break
    finally:
        ex.shutdown(wait=False, cancel_futures=True)
    tag = " stopped by user" if stopped else ""
    print(f"[rebuild-fs]{tag} changed={changed} same={same} "
          f"skipped(no-data/system-error)={skipped} "
          f"skipped(neg-revenue/bank)={skipped_neg} exceptions={errors}", flush=True)
    conn.close()
    return changed


def backfill_missing_fs(limit=None):
    """Backfill صورتهای مالی برای نمادهایی که در codal_notices عنوان
    'صورت مالی' دارند ولی هنوز در financial_statements استخراج نشدهاند.
    هدف: رساندن پوشش ۵-شاخصی از ~۳۷۴ نماد به ~۷۷۹ نماد (۹.۷% → ۲۰% بازار).
    فقط کوئری نماد-به-نماد روی Category=1/3 (با requests — بن نمیخورد)."""
    global _BACKOFF_UNTIL, _BACKOFF_EVENTS
    _BACKOFF_UNTIL, _BACKOFF_EVENTS = 0.0, 0
    print("=== Backfill FS/MS for symbols with codal financial-statement titles ===", flush=True)
    conn = sqlite3.connect(DB_PATH, timeout=60, isolation_level=None)
    create_schema(conn)
    migrate_schema(conn)
    # نمادهایی که عنوان صورت مالی دارند ولی FS ندارند — هر دو: داخل بازار + جدید (خارج بازار)
    # (قبلاً فقط IN instruments بود → ۱۳۷ نماد جدیدِ خارج از بازار هرگز پردازش نمیشدند)
    targets = []
    for r in conn.execute("""
        SELECT DISTINCT n.symbol, n.company_name FROM codal_notices n
        WHERE (n.title LIKE '%صورت%مالی%' OR n.title LIKE '%صورتهای مالی%')
          AND n.symbol NOT IN (SELECT symbol FROM financial_statements)
    """):
        sym, comp = r[0], r[1] or ""
        # استاندارد قبلی: صندوق/مشتقهها/اوراق رد میشوند (فقط نمادهای شرکتی)
        if _is_fund(sym, comp) or _is_derivative(sym, comp):
            continue
        targets.append(sym)
    targets = list(dict.fromkeys(targets))  # dedupe + حفظ ترتیب
    known = {r[0] for r in conn.execute("SELECT tracing_no FROM codal_notices")}
    # period_end های FS/MS موجود — در backfill باید PER-SYMBOL باشد، وگرنه
    # دورههای عمومی (مثل ۱۴۰۳/۱۲/۳۰) که در نمادهای دیگر موجودند، برای این
    # نماد هم skip میشوند و هیچ FS ای استخراج نمیشود
    fs_done_sym = {}
    ms_done_sym = {}
    for sym in targets:
        fs_done_sym[sym] = {r[0] for r in conn.execute(
            "SELECT DISTINCT period_end FROM financial_statements WHERE symbol=?", (sym,))}
        ms_done_sym[sym] = {r[0] for r in conn.execute(
            "SELECT DISTINCT period_end FROM monthly_sales WHERE symbol=?", (sym,))}
    conn.close()
    total = len(targets)
    if limit:
        targets = targets[:limit]
        total = len(targets)
    print(f"  targets: {total} symbols", flush=True)
    sess = make_session()
    seen = set()  # dedupe در همین اجرا — رکوردهای قدیمی DB باید دوباره پردازش شوند
    done = 0
    for sym in targets:
        c = _control_cmd()
        if c == "stop":
            print("=== Backfill stopped by user ===", flush=True)
            return
        while c == "pause":
            time.sleep(5)
            c = _control_cmd()
        for cat in ("1", "3"):
            page = 1
            while page <= 5:  # هر نماد حداکثر ۵ صفحه (۱۲۵ اطلاعیه)
                _jitter()
                q = {"Audited": "true", "AuditorRef": "-1", "Category": cat,
                     "Childs": "true", "CompanyState": "-1", "CompanyType": "-1",
                     "Consolidatable": "true", "IsNotAudited": "false", "Length": "-1",
                     "LetterType": "-1", "Mains": "true", "NotAudited": "true",
                     "NotConsolidatable": "true", "PageNumber": str(page),
                     "Publisher": "false", "ReportingType": "-1", "TracingNo": "-1",
                     "search": "false", "Symbol": sym, "FromDate": "1395/01/01"}
                letters = fetch_page(sess, page, q, quiet=True, max_429_retries=4)
                if letters is None:
                    break
                if not letters:
                    break
                new_rows = []
                for x in letters:
                    t = x.get("TracingNo")
                    if t is None or t in seen:
                        continue
                    title = (x.get("Title") or "").strip()
                    if SAVE_USEFUL_ONLY and not _positive_title(title):
                        continue
                    # فیلتر صندوق/مشتقه: عناوین «صورت وضعیت پورتفوی» یا «صندوق»
                    # صورت مالی شرکتی نیستند — فقط نمادهای واقعی را نگه دار
                    if any(k in title for k in ("صورت وضعیت پورتفوی", "صندوق سرمایه", "افزایش سرمایه")):
                        continue
                    seen.add(t)
                    pdf_raw = (x.get("PdfUrl") or "").strip()
                    excel_raw = (x.get("ExcelUrl") or "").strip()
                    if pdf_raw and not pdf_raw.startswith("http"):
                        pdf_raw = "https://codal.ir/" + pdf_raw
                    if excel_raw and not excel_raw.startswith("http"):
                        excel_raw = "https://codal.ir/" + excel_raw
                    new_rows.append((t, sym, (x.get("CompanyName") or "").strip(), title,
                                     (x.get("LetterCode") or "").strip(),
                                     _norm_date(x.get("PublishDateTime")),
                                     _norm_date(x.get("SentDateTime")),
                                     "https://codal.ir" + (x.get("Url") or ""),
                                     datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                     pdf_raw, excel_raw))
                if new_rows:
                    conn2 = sqlite3.connect(DB_PATH, timeout=60, isolation_level=None)
                    try:
                        nf, nm = _deep_extract(new_rows, fs_done_sym[sym],
                                               ms_done_sym[sym],
                                               fs_done_sym[sym], ms_done_sym[sym], conn2)
                        fs_done_sym[sym].update({r[0] for r in conn2.execute(
                            "SELECT DISTINCT period_end FROM financial_statements WHERE symbol=?", (sym,))})
                        ms_done_sym[sym].update({r[0] for r in conn2.execute(
                            "SELECT DISTINCT period_end FROM monthly_sales WHERE symbol=?", (sym,))})
                    finally:
                        conn2.close()
                if len(new_rows) < 25:
                    break
                page += 1
        done += 1
        write_progress("codal_sync",
                       f"Backfill FS — {done}/{total} نماد پردازش شد",
                       total, done, sym)
        print(f"  [{done}/{total}] {sym} done", flush=True)
    try:
        tmp = STATUS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"stage": "done", "phase": "codal_done",
                       "detail": f"Backfill FS کامل شد — {done}/{total} نماد پردازش شد",
                       "total": total, "current": done, "symbol": "",
                       "percent": 100.0,
                       "ts": datetime.datetime.now().isoformat(timespec="seconds")},
                      f, ensure_ascii=False)
        os.replace(tmp, STATUS_PATH)
    except Exception:
        pass
    print(f"=== Backfill done: {done}/{total} symbols processed ===", flush=True)


def main(mode="missing"):
    """Bulk Codal sync — PER-SYMBOL targeted scan (Laser-Scan).
    mode="missing": نمادهای ناقص (اطلاعیه دارد ولی FS/MS استخراج نشده + بدون اطلاعیه)
    mode="update":  فقط نمادهایی که قبلاً استخراج شدهاند (FS/MS دارند) — بروزرسانی همانها

    The global feed pagination (PageNumber=1,2,...) gets permanently blocked
    (429) by the WAF. Instead we iterate EVERY symbol in the database and query
    Category=1 (financials) + Category=3 (monthly activity) directly — 2 pages
    each — with a 3-worker thread pool, per-request jitter (1-3s) and a shared
    429-backoff gate. Progress is written to sync_status.json so the UI overlay
    shows which symbol is being scanned and the running percentage.
    """
    global _BACKOFF_UNTIL, _BACKOFF_EVENTS
    _BACKOFF_UNTIL, _BACKOFF_EVENTS = 0.0, 0

    print(f"=== Bulk Codal sync (per-symbol targeted scan | mode={mode}) ===")
    conn = sqlite3.connect(DB_PATH, timeout=60, isolation_level=None)
    create_schema(conn)
    migrate_schema(conn)

    if mode == "update":
        # فقط نمادهایی که قبلاً کامل استخراج شدهاند (داخل جدول هستند):
        symbol_rows = conn.execute("""
            SELECT DISTINCT i.l_val18, i.l_val30 FROM instruments i
            WHERE i.l_val18 IS NOT NULL
              AND (
                EXISTS (SELECT 1 FROM financial_statements f WHERE f.symbol = i.l_val18)
                OR EXISTS (SELECT 1 FROM monthly_sales m WHERE m.symbol = i.l_val18)
              )
        """).fetchall()
    else:
        # فقط نمادهایی که واقعاً کار دارند اسکن میشوند:
        #   (a) نماد با اطلاعیهای که هنوز FS/MS ناقص دارد (fallback از notices)
        #   (b) نماد بدون هیچ اطلاعیهای (نیاز به search API)
        # نمادهای کاملاً استخراجشده اصلاً در لیست نیستند → اجرای مجدد = چند دقیقه.
        symbol_rows = conn.execute("""
        SELECT DISTINCT i.l_val18, i.l_val30 FROM instruments i
        WHERE i.l_val18 IS NOT NULL
          AND (
            -- (b) بدون هیچ اطلاعیه
            NOT EXISTS (SELECT 1 FROM codal_notices c WHERE c.symbol = i.l_val18)
            OR
            -- (a) اطلاعیه دارد ولی برخی FS/MS هنوز استخراج نشده
            EXISTS (
                SELECT 1 FROM codal_notices c
                WHERE c.symbol = i.l_val18
                  AND (
                    (c.title LIKE '%صورت%مالی%' AND NOT EXISTS
                        (SELECT 1 FROM financial_statements f WHERE f.symbol = i.l_val18 AND f.tracing_no = c.tracing_no))
                    OR
                    (c.title LIKE '%فعالیت%ماهانه%' AND NOT EXISTS
                        (SELECT 1 FROM monthly_sales m WHERE m.symbol = i.l_val18 AND m.tracing_no = c.tracing_no))
                  )
            )
          )
    """).fetchall()
    # مشتقهها (اختیار/حق تقدم/ضهرم) در کدال نماد شرکتی ندارند → بیفایدهاند و
    # قبلاً بهخاطر (0,0,0) گیت سراسری را قفل میکردند؛ صندوقها هم Category 1
    # ندارند (فقط پورتفوی ماهانه) → هر دو کنار گذاشته میشوند تا scan فقط شرکتها.
    symbols = [s for s, n in symbol_rows
               if not _is_derivative(s, n) and not _is_fund(s, n)]
    with_notices = {r[0] for r in conn.execute(
        "SELECT DISTINCT symbol FROM codal_notices")}
    conn.close()
    # فاز ۱: نمادهای با اطلاعیه (fallback scrape مؤثر) — اول
    # فاز ۲: نمادهای بدون اطلاعیه (فقط search API که 429 میخورد) — آخر
    symbols.sort(key=lambda s: 0 if s in with_notices else 1)
    total = len(symbols)
    if mode == "update":
        print(f"Scanning {total} EXISTING symbols (already extracted; refresh mode)")
        _mode_label = "بروزرسانی نمادهای موجود"
    else:
        print(f"Scanning {total} symbols that actually need work (rest already extracted)")
        _mode_label = "در حال اسکن نمادها"
    counters = {"notices": 0, "fs": 0, "ms": 0}
    write_progress("codal_sync",
                   f"{_mode_label} (0 از {total})... نماد فعلی: -",
                   total, 0, "")

    search_blocked = False  # (حذف شد — نمادهای بدون اطلاعیه با _SEARCH_LOCK سریال میروند)

    def _worker(sym):
        sess = make_session()  # requests.Session is not thread-safe -> one per worker
        try:
            if sym not in with_notices:
                # نماد بدون اطلاعیه → search API (فقط سریال؛ موازی = بن فوری)
                with _SEARCH_LOCK:
                    res = _process_symbol(sym, sess)
            else:
                # نماد با اطلاعیه → scrape از codal.ir/Reports (بدون WAF) — موازی OK
                res = _process_symbol(sym, sess)
            return sym, res
        except Exception as e:
            print(f"  [worker] {sym}: {type(e).__name__}: {e}")
            return sym, (0, 0, 0, "blocked")

    # ۲ کارگر + جیتر ۱.۲-۲.۴ ثانیه — ۳ کارگر همزمان دوباره 429 گرفت،
    # ۲ کارگر با بکآف مشترک امن است (WAF کدال حساس)
    w = 2
    st_counts = {"new": 0, "done": 0, "empty": 0, "blocked": 0}
    with concurrent.futures.ThreadPoolExecutor(max_workers=w) as ex:
        for i, (sym, (nn, nf, nm, st4)) in enumerate(ex.map(_worker, symbols), 1):
            counters["notices"] += nn
            counters["fs"] += nf
            counters["ms"] += nm
            st_counts[st4] = st_counts.get(st4, 0) + 1
            write_progress("codal_sync",
                           f"در حال اسکن نمادها ({i} از {total})... نماد فعلی: {sym}",
                           total, i, sym, extra=dict(st_counts))
            if i % 100 == 0 or i == total:
                print(f"  [{i}/{total}] notices={counters['notices']} "
                      f"fs={counters['fs']} monthly={counters['ms']}")

    write_progress("codal_sync",
                   f"پایان اسکن {total} نماد: {counters['fs']} صورت مالی + "
                   f"{counters['ms']} گزارش ماهانه جدید.",
                   total, total, "")
    print(f"=== Per-symbol sync complete: {counters['notices']} notices, "
          f"fs={counters['fs']}, monthly={counters['ms']} ===")



def fetch_symbol(symbol):
    """On-demand: fetch ALL missing historical Codal reports for one symbol.

    Targets only `symbol`, bypasses the general queue and DEEP_LIMIT, and writes
    progress to a dedicated on-demand status file so the dashboard can show an
    isolated, non-blocking loading state. Runs as a background subprocess from
    the UI (invoked via `codal_fetcher.py --symbol SYM`)."""
    symbol = (symbol or "").strip()
    if not symbol:
        return
    print(f"On-demand fetch for symbol: {symbol}")
    write_od_status(symbol, "codal", f"آمادهسازی و دریافت اطلاعیههای {symbol} ...")
    s = make_session()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DB_PATH, timeout=60, isolation_level=None)
    create_schema(conn)
    migrate_schema(conn)

    # 1) pull targeted notices for this symbol (only the categories we need)
    #    Category 1 = صورتهای مالی, Category 3 = گزارش فعالیت ماهانه
    #    (discovered empirically via www.codal.ir/ReportList.aspx + JS analysis)
    categories = {"1": "Financial Statements", "3": "Monthly Activity Report"}
    sym_rows, seen, extra = [], set(), {}  # extra[t] = (pdf_url, excel_url)
    for cat, cat_name in categories.items():
        q = dict(QUERY, Symbol=symbol, Category=cat, LetterType="-1")
        for page in range(1, 3):  # on-demand: حداکثر ۲ صفحه در هر دسته (صرفهجویی)
            if page > 1:
                _jitter(4.5, 7.5)
            letters = fetch_page(s, page, q, quiet=True)
            if letters is None:  # persistent 429 — ride out the cooldown
                print(f"  cat={cat} page {page}: rate-limited, riding out cooldown ...")
                for _ in range(3):
                    if _control_sleep(120) == "stop":
                        write_od_status(symbol, "done", "متوقف شد")
                        return
                    letters = fetch_page(s, page, q, quiet=True)
                    if letters is not None:
                        break
                if letters is None:
                    print(f"  cat={cat} page {page}: still blocked, skipping.")
                    continue
            if not letters:
                break
            for x in letters:
                t = x.get("TracingNo")
                if t is None or t in seen:
                    continue
                # whitelist خودآموز: عنوان نامطبوع → همانجا رد (بدون scrape)
                if SAVE_USEFUL_ONLY and not _positive_title(x.get("Title") or ""):
                    continue
                seen.add(t)
                pdf_raw = (x.get("PdfUrl") or "").strip()
                excel_raw = (x.get("ExcelUrl") or "").strip()
                # Codal's PdfUrl/ExcelUrl are often relative → make them absolute
                if pdf_raw and not pdf_raw.startswith("http"):
                    pdf_raw = "https://codal.ir/" + pdf_raw
                if excel_raw and not excel_raw.startswith("http"):
                    excel_raw = "https://codal.ir/" + excel_raw
                extra[t] = (pdf_raw, excel_raw)
                sym_rows.append((
                    t, (x.get("Symbol") or "").strip(), (x.get("CompanyName") or "").strip(),
                    (x.get("Title") or "").strip(), (x.get("LetterCode") or "").strip(),
                    _norm_date(x.get("PublishDateTime")),
                    _norm_date(x.get("SentDateTime")),
                    "https://codal.ir" + (x.get("Url") or ""), now,
                    extra[t][0], extra[t][1],
                ))
            write_od_status(symbol, "codal",
                            f"دریافت فهرست اطلاعیهها ({cat_name}) — "
                            f"{nfmt(len(sym_rows))} مورد ({symbol})")
            if len(sym_rows) >= TARGET:
                break
    conn.executemany(NOTICE_UPSERT, sym_rows)
    conn.commit()

    # Self-healing: حذف ردیفهای صورت مالیِ دارای ترازنامهٔ ناقص (total_assets
    # IS NULL) تا با واژگان جدید (IFRS: حقوق مالکانه و…) دوباره استخراج شوند
    try:
        conn.execute("DELETE FROM financial_statements "
                     "WHERE symbol = ? AND total_assets IS NULL", (symbol,))
        conn.commit()
    except Exception:
        pass

    # 2) Targeted extraction: ONLY monthly-activity + financial-statement reports
    #    (board-assignment / assembly notices are stored as notices but never
    #    deep-extracted — keeps bandwidth low and avoids IP bans)
    ms_done = {r[0] for r in conn.execute(
        "SELECT tracing_no FROM monthly_sales "
        "WHERE (monthly_revenue IS NOT NULL AND monthly_revenue != 0) "
        "OR (ytd_revenue IS NOT NULL AND ytd_revenue != 0)")}
    fs_done = {r[0] for r in conn.execute(
        "SELECT tracing_no FROM financial_statements "
        "WHERE revenue IS NOT NULL OR total_assets IS NOT NULL")}
    pool = sym_rows or [tuple(r) for r in conn.execute(
        """SELECT tracing_no, symbol, company_name, title, letter_code,
                  publish_date, sent_date, url, fetched_at, pdf_url, excel_url
           FROM codal_notices WHERE symbol=? ORDER BY publish_date DESC""", (symbol,))]
    ms_targets = [n for n in pool
                  if kind_of(n[3]) == "Monthly Activity Report" and n[0] not in ms_done]
    fs_targets = [n for n in pool
                  if kind_of(n[3]) == "Financial Statements" and n[0] not in fs_done]
    print(f"On-demand extraction for {symbol}: {nfmt(len(ms_targets))} monthly + "
          f"{nfmt(len(fs_targets))} financial reports ...")

    # ---- Scenario 1: monthly activity sales ----
    total = len(ms_targets)
    ms, ok_ms = [], 0
    for i, n in enumerate(ms_targets, 1):
        t, sym = n[0], n[1]
        title, url = n[3], n[7]
        write_od_status(symbol, "codal",
                        f"گزارش فعالیت ماهانه {nfmt(i)}/{nfmt(total)} — {sym}")
        vals, period_end = scrape_monthly_report(s, url)
        if vals.get("monthly_revenue") is not None or vals.get("ytd_revenue") is not None:
            ok_ms += 1
        year = month = None
        if period_end:
            mm = re.match(r"(\d{4})[-/](\d{1,2})", str(period_end))
            if mm:
                year, month = int(mm.group(1)), int(mm.group(2))
        pdf, excel = extra.get(t, ("", ""))
        ms.append((t, sym, title, period_end, year, month,
                   vals.get("monthly_revenue"), vals.get("ytd_revenue"),
                   vals.get("monthly_revenue_prev"), vals.get("ytd_revenue_prev"),
                   vals.get("monthly_volume"), vals.get("ytd_volume"),
                   vals.get("volume_unit"),
                   pdf, excel))
    if ms:
        conn.executemany(MS_UPSERT, ms)

    # ---- Scenario 2: financial statements (profile ratios) ----
    total = len(fs_targets)
    fs, ok_fs = [], 0
    for i, n in enumerate(fs_targets, 1):
        t, sym, comp, title = n[0], n[1], n[2], n[3]
        pub, url = n[5], n[7]
        write_od_status(symbol, "codal",
                        f"صورت مالی {nfmt(i)}/{nfmt(total)} — {sym}")
        try:
            vals, meta, unit = scrape_report(s, url)
        except Exception as e:
            print(f"  [{i}] {sym}: error - {e}")
            vals, meta, unit = {}, {}, None
        if vals.get("revenue") is not None:
            ok_fs += 1
        row = (t, sym, comp, title, kind_of(title), meta.get("period"),
               meta.get("end"), pub) + tuple(vals.get(k) for k in FS_KEYS) \
            + (unit, url, now) + fs_derived(title, meta.get("end"), unit,
                                            meta.get("is_consolidated"))
        fs.append(row)
    if fs:
        conn.executemany(FS_UPSERT, fs)

    conn.commit()
    conn.close()

    # ---- Phase 3: سابقهٔ قیمت (OHLCV) برای نمودار تکنیکال ----
    write_od_status(symbol, "codal", f"دریافت سابقهٔ قیمتی {symbol} ...")
    try:
        import test_tsetmc
        test_tsetmc.fetch_price_history(symbol)
    except Exception as e:
        print(f"  [history] {symbol}: {type(e).__name__}: {e}")

    write_od_status(symbol, "done",
                    f"{symbol}: {nfmt(len(fs))} صورت مالی + "
                    f"{nfmt(len(ms))} گزارش فعالیت ماهانه")
    print(f"On-demand done for {symbol}: {nfmt(len(fs))} financial + "
          f"{nfmt(len(ms))} monthly-sales rows added/updated.")


def discovery_scan(limit=None):
    """Active Discovery Scan: every instrument NOT in financial_statements.

    Iterates ALL such symbols through the self-learned positive-whitelist:
    non-matching letters are rejected at title level (URL never opened), so a
    data-less symbol costs ONE search request (~3-4s) and a matched symbol a
    second request + extraction. Runs SERIAL (single thread): the WAF bans
    parallel search requests instantly.

    Returns (scanned, fs_rows, ms_rows, new_fs_symbols)."""

    t0 = time.time()
    conn = sqlite3.connect(DB_PATH, timeout=60, isolation_level=None)
    create_schema(conn)
    migrate_schema(conn)
    # Candidate: symbols without financial statements, minus the playbook's
    # rejected industries (only when sector is known — unknown stays included,
    # so 'سایر' symbols are still scanned).
    pre = conn.execute("""
        SELECT COUNT(DISTINCT i.l_val18) FROM instruments i
        WHERE i.l_val18 IS NOT NULL AND i.l_val18 != ''
          AND i.l_val18 NOT IN (SELECT DISTINCT symbol FROM financial_statements)"""
        ).fetchone()[0]
    rows = conn.execute("""
        SELECT DISTINCT i.l_val18, i.l_val30 FROM instruments i
        WHERE i.l_val18 IS NOT NULL AND i.l_val18 != ''
          AND i.l_val18 NOT IN (SELECT DISTINCT symbol FROM financial_statements)
          AND COALESCE(NULLIF(i.sector_name, ''), '')
              NOT IN (%s)""" % ",".join("?" * len(REJECTED_SECTORS)),
        list(REJECTED_SECTORS)).fetchall()
    # Cumulative progress basis (survives WAF-abort + relaunch): the scan
    # universe = all instruments minus rejected sectors. Symbols that no longer
    # need scanning (already have FS / are deriv-fund excluded) = done_base,
    # derived from the DB on every start → the % never resets to 0.
    tot_all = conn.execute("""
        SELECT COUNT(DISTINCT i.l_val18) FROM instruments i
        WHERE i.l_val18 IS NOT NULL AND i.l_val18 != ''
          AND COALESCE(NULLIF(i.sector_name, ''), '')
              NOT IN (%s)""" % ",".join("?" * len(REJECTED_SECTORS)),
        list(REJECTED_SECTORS)).fetchone()[0]
    conn.close()
    symbols = [s for s, n in rows
               if not _is_derivative(s, n) and not _is_fund(s, n)]
    if limit:
        symbols = symbols[:limit]
    total = len(symbols)
    done_base = max(tot_all - len(symbols), 0)
    print(f"Discovery scan: {total} symbols not in financial_statements "
          f"(of {len(rows)} candidates; deriv/fund excluded; "
          f"{pre - total} skipped: rejected industries of the 5-step playbook)")
    global _CONSEC_429, _DISCOVERY_ABORTED, _CB_TOTAL, _CB_DONE, _CB_SYM
    _CONSEC_429 = 0
    _DISCOVERY_ABORTED = False
    _CB_TOTAL, _CB_DONE, _CB_SYM = tot_all, done_base, ""
    write_progress("codal_sync", f"کشف فعال: 0 از {total} ...", tot_all, done_base, "")

    fs_rows = ms_rows = 0
    new_fs_syms = []
    st_counts = {"done": 0, "new": 0, "empty": 0, "blocked": 0}
    # --- parallel discovery: 2 workers share the global 429 gate. The
    # per-request jitter floor stays (2.5-4s); the overlap is the win.
    N_WORKERS = 2
    _ctx_i = [0]
    _p_lock = threading.Lock()

    def _worker():
        global _USER_STOPPED, _DISCOVERY_ABORTED, _CB_TOTAL, _CB_DONE, _CB_SYM
        nonlocal fs_rows, ms_rows, new_fs_syms
        wsess = make_session()
        try:
            while True:
                c = _control_cmd()
                if c == "stop":
                    with _p_lock:
                        _USER_STOPPED = True
                    return
                while c == "pause":
                    with _p_lock:
                        i_p = _ctx_i[0]
                    sym_p = symbols[i_p] if i_p < len(symbols) else ""
                    write_progress("codal_paused",
                                   f"اسکن در حال مکث است ({i_p + 1} از {total}) - نماد بعدی: {sym_p}؛ برای ادامه دکمه ادامه را بزنید",
                                   tot_all, done_base + i_p, sym_p, extra=dict(st_counts))
                    time.sleep(5)
                    c = _control_cmd()
                    if c == "stop":
                        with _p_lock:
                            _USER_STOPPED = True
                        return
                with _p_lock:
                    if _USER_STOPPED:
                        return
                    if _CONSEC_429 >= 8:
                        if not _DISCOVERY_ABORTED:
                            _DISCOVERY_ABORTED = True
                            write_progress("codal_backoff",
                                           "مسدودی WAF همچنان فعال — توقف اسكن (قابل ادامه)",
                                           tot_all, done_base + _ctx_i[0], _CB_SYM,
                                           extra=dict(st_counts))
                        return
                    _ctx_i[0] += 1
                    i = _ctx_i[0] - 1
                    if i >= total:
                        return
                    sym = symbols[i]
                try:
                    _nn, nf, nm, st4 = _process_symbol(sym, wsess)
                except Exception as e:
                    print(f"  [discover] {sym}: {type(e).__name__}: {e}")
                    nf = nm = 0
                    st4 = "blocked"
                with _p_lock:
                    fs_rows += nf
                    ms_rows += nm
                    st_counts[st4] = st_counts.get(st4, 0) + 1
                    if nf:
                        new_fs_syms.append(sym)
                    _CB_TOTAL, _CB_DONE, _CB_SYM = tot_all, done_base + i, sym
                    if i % 100 == 0 or i == total - 1:
                        print(f"  [{i + 1}/{total}] fs_rows={fs_rows} ms_rows={ms_rows} "
                              f"new_fs_symbols={len(new_fs_syms)} st={st_counts}", flush=True)
                    write_progress("codal_sync",
                                   f"کشف فعال: {i + 1} از {total} ... نماد فعلی: {sym}",
                                   tot_all, done_base + i, sym, extra=dict(st_counts))
        finally:
            try:
                wsess.close()
            except Exception:
                pass

    _thr = [threading.Thread(target=_worker, daemon=True) for _ in range(N_WORKERS)]
    for _t in _thr:
        _t.start()
    for _t in _thr:
        _t.join()

    if _USER_STOPPED:
        write_progress("codal_stopped", "اسکن اكتشافی توسط کاربر متوقف شد",
                       tot_all, _CB_DONE, _CB_SYM, extra=dict(st_counts))
        print("=== Discovery stopped by user ===", flush=True)
        return total, fs_rows, ms_rows, new_fs_syms
    mins = round((time.time() - t0) / 60, 1)
    print(f"=== Discovery done in {mins} min: fs_rows={fs_rows} "
          f"(+{len(new_fs_syms)} symbols: {', '.join(new_fs_syms[:15])}"
          f"{'...' if len(new_fs_syms) > 15 else ''}), ms_rows={ms_rows} ===")
    return total, fs_rows, ms_rows, new_fs_syms


if __name__ == "__main__":
    # تعمیر قطعی: stdout/stderr پایپ ویندوز cp1252 است و نام فارسی نمادها
    # (طتاص7007 و ...) در print کرش UnicodeEncodeError میداد → کارگر قبل از
    # ذخیرهسازی داده میمرد و نمادِ با-داده از دست میرفت (fs_rows همیشه صفر).
    # reconfigure با errors="replace" یعنی چاپ هرگز کرش نمیکند.
    import sys as _sys
    try:
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default=None, help="On-demand fetch for one symbol")
    ap.add_argument("--discover", action="store_true",
                    help="Active Discovery Scan (symbols missing from financial_statements)")
    ap.add_argument("--update", action="store_true",
                    help="Refresh only symbols already extracted (FS/MS in the table)")
    ap.add_argument("--feed", choices=["update", "discover"], default=None,
                    help="Smart global-feed sync (no per-symbol search; browser-verified 2026-08-27)")
    ap.add_argument("--repair", action="store_true",
                    help="ترمیم ردیف‌های MS/FS موجود ولی خالی (re-scrape با پارسر جدید)")
    ap.add_argument("--rebuild-fs", action="store_true",
                    help="بازسازی financial_statements با پارسرِ نام‌محور/مبنای غیرتلفیقی "
                         "(re-scrape همهٔ نامه‌های در دسترس؛ جایگزینی مبالغ+مبنا؛ skip روی خطای کدال)")
    ap.add_argument("--symbols", default=None,
                    help="لیست نمادها (جدا با کاما) برای محدودکردن --rebuild-fs")
    ap.add_argument("--latest-only", action="store_true",
                    help="فقط جدیدترین نامهٔ صورتمالی هر نماد (ردیفی که صفحهٔ FTS نشان میدهد) — "
                         "برای بازسازی شبانه وقتی کدال کند است")
    ap.add_argument("--backfill", action="store_true",
                    help="Backfill FS/MS for symbols with codal financial-statement titles but no FS row")
    ap.add_argument("--update-symbols", type=int, default=0,
                    help="Task 2: incremental update on N existing symbols (FromDate delta + dedupe)")
    ap.add_argument("--polite", action="store_true",
                    help="بدون ADB/IP-روتاریشن: مکث ~1.7s بین هر درخواست + تک-کارگر")
    ap.add_argument("--limit", type=int, default=None,
                    help="Stop after N symbols (testing only)")
    ap.add_argument("--workers", type=int, default=None,
                    help="تعدادِ همزمانِ اسکرپ در --rebuild-fs (پیش‌فرض ۴؛ با --polite ۱). "
                         "ورکرها فقط شبکه می‌خوانند، نوشتن در SQLite همیشه تک‌نویسنده است.")
    ap.add_argument("--resume-since", default=None, metavar="TS",
                    help="در --rebuild-fs: نامه‌هایی که بعد از این زمان دوباره scrape شده‌اند "
                         "(fetched_at تازه) را رد کن — برای ازسرگیریِ اجرای قطع‌شده")
    ap.add_argument("--no-tether", action="store_true",
                    help="از Wi-Fi خانه بهجای IP تترینگ استفاده کن (کدال IP تترینگ را سریعتر 429 میکند)")
    ap.add_argument("--optimized", action="store_true",
                    help="فقط داده‌های تغییرپذیر از Codal: новые اطلاعیه‌ها + FS های قدیمی/فاسد + نمادهای جدید (حداقل درخواست — برای IP های بدون ADB)")
    args = ap.parse_args()
    _NO_TETHER = bool(args.no_tether)
    set_polite(getattr(args, "polite", False))
    if args.symbol:
        fetch_symbol(args.symbol)
    elif args.repair:
        repair_broken_rows(limit=args.limit)
    elif args.rebuild_fs:
        syms = [x.strip() for x in args.symbols.split(",")] if args.symbols else None
        rebuild_fs(limit=args.limit, symbols=syms, latest_only=args.latest_only,
                   workers=args.workers, resume_since=args.resume_since)
    elif args.update_symbols:
        conn = sqlite3.connect(DB_PATH, timeout=60)
        syms = [r[0] for r in conn.execute(
            "SELECT DISTINCT symbol FROM financial_statements ORDER BY symbol LIMIT ?",
            (args.update_symbols,))]
        conn.close()
        sess = make_session()
        import concurrent.futures
        # بدون مودب: 3 کارگر (کندتر) — با --polite: تک-کارگر (بدون ADB امن)
        _w = 1 if POLITE else 3
        with concurrent.futures.ThreadPoolExecutor(max_workers=_w) as _ex:
            for s, res in _ex.map(lambda s_: (s_, update_symbol_incremental(s_, sess)), syms):
                print(f"=== {s} update: {res}", flush=True)
    elif args.discover:
        try:
            discovery_scan(limit=args.limit)
            raise SystemExit(2 if _DISCOVERY_ABORTED else 0)
        except SystemExit:
            raise
        except Exception as e:
            # NEVER die silently: log it, surface the abort to the UI status
            # channel, and exit 1 so the cron relauncher picks it back up.
            print(f"  [discover] FATAL: {type(e).__name__}: {e}", flush=True)
            try:
                write_progress("codal_backoff",
                               f"پایان غيرمنتظره اسكن ({type(e).__name__}) - قابل ادامه",
                               globals().get("_CB_TOTAL", 0),
                               globals().get("_CB_DONE", 0),
                               globals().get("_CB_SYM", ""))
            except Exception:
                pass
            raise SystemExit(1)

    elif args.update:
        main("update")

    elif args.feed:
        feed_sync(args.feed, optimized=bool(args.optimized))

    elif args.optimized:
        feed_sync("update", optimized=True)

    elif args.backfill:
        backfill_missing_fs(limit=args.limit)

    else:
        main()
