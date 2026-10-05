# -*- coding: utf-8 -*-
"""
BorsTerminal — Calendar Fetcher v3 (کدال — رایگان)
=====================================================================
استخراج رویدادهای بازار سرمایه از کدال (search.codal.ir) و تولید
static/calendar/cache.json — بدون نیاز به احراز هویت.

رویکرد کم‌ترافیک (Low-request):
  به‌جای کوئری به‌ازای هر نماد، چند کوئری کلان در ماه جلالی روی
  «دستهٔ موضوعی» (Category) — که تنها فیلتر مؤثرِ سمت سرور است.

⚠ v9.2 — چرا ساختار کوئری‌ها عوض شد (مهم‌ترین تغییر این نسخه):
  اندازه‌گیری روی API زنده نشان داد پارامتر «جستجوی متن» در این endpoint
  وجود خارجی ندارد:
      Subject=<متن>   → Total=0                 (پارامتر عددی است)
      Title|Text|Q|Keyword|SearchText|… → Total دقیقاً برابرِ بدون فیلتر
      Category=<1..10> → تنها فیلتر موضوعیِ کارآمد
  پنج کوئریِ Subject-based نسخهٔ v2 (پرداخت سود / افزایش سرمایه / عرضه اولیه /
  سررسید / لغو مجمع) بنابراین **همیشه صفر** برمی‌گرداندند؛ تقویم عملاً فقط
  مجامع (Category=6) را نشان می‌داد. راه‌حل v3:
      فیلتر Category سمت سرور  +  شکار کلیدواژهٔ رسمی روی عنوان سمت کلاینت
      (IPO_KEYS / MATURITY_KEYS / DIVIDEND_KEYS — واژگان واقعی کدال)
  شمارش ماهانهٔ دسته‌ها (۱۴۰۵/۰۶): 1=542  2=456  3=1652  4=10  6=878  7=95

کنترل نرخ:
  Polite Delay ۱.۵–۲.۰ ثانیه قبل از **هر** درخواست + Exponential Backoff
  (2→4→8→16→32→64، سقف ۹۰s) با احترام به هدر Retry-After.

هندلینگ بلاک:
  با --adb-rotate بعد از دو بک‌آف پیاپی، حالت پرواز adb روشن/خاموش می‌شود تا IP
  سیم‌کارت عوض شود و چرخهٔ backoff ریست گردد. چرخش روی «یک تابع مرجع» انجام
  می‌شود: codal_fetcher.rotate_ip_via_adb (enable → ۸۰s → disable → ۲۰s + تأیید
  واقعی تغییر IP + گاردهایش). توگل کوتاه (<۶۰s) PDP context را تخریب نمی‌کند و
  IP را پین‌شده نگه می‌دارد (اندازه‌گیری MCI) — برای جزئیات به adb_rotate_ip.

خروجی: همان فرمت cache.json قبلی — فرانت تقویم فقط classify() غنی‌تر شده است.

اجرا:
  venv\\Scripts\\python.exe dev\\calendar_fetcher.py                       # ماه جلالی جاری
  venv\\Scripts\\python.exe dev\\calendar_fetcher.py --jmonth 1405/06 --months 3
  venv\\Scripts\\python.exe dev\\calendar_fetcher.py --db market.db --adb-rotate
  venv\\Scripts\\python.exe dev\\calendar_fetcher.py --cats 6,4            # فقط مجامع + عرضه اولیه
"""
import argparse
import json
import random
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# ویندوز با codepage غیر UTF-8 (مثلاً cp1252) روی هر print فارسی می‌شکند و
# استخراج وسط کار با UnicodeEncodeError می‌افتد. خروجی صریح UTF-8 می‌شود.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "static" / "calendar" / "cache.json"

# v9.3 — چرخش IP روی «یک تابع مرجع» (codal_fetcher.rotate_ip_via_adb) متمرکز شد.
# کپیِ محلیِ قبلی با توگلِ کوتاه (۲s پرواز + ۸s بازیابی) IP را **پین‌شده** نگه
# می‌داشت: تخریب کاملِ PDP context روی MCI حداقل ~۸۰s می‌خواهد، پس چرخش بی‌اثتر
# می‌شد، backoff ریست نمی‌گشت و اسکریپت روی بن می‌ماند. حالا فقط واگذاری می‌کنیم.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import codal_fetcher as _cf  # noqa: E402  (rotate_ip_via_adb — منبع یگانه حقیقت)
BASE = "https://search.codal.ir/api/search/v2/q"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# ---------------------------------------------------------------------- #
#  تبدیل جلالی ↔ میلادی (الگوریتم استاندارد — بدون وابستگی)
# ---------------------------------------------------------------------- #
def g2j(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) \
        + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1]
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd


def j2g(jy, jm, jd):
    jy += 1595
    days = -355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4) + jd
    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += ((jm - 7) * 30) + 186
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    leap = (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)
    sal_a = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    while gm < 12 and gd > sal_a[gm]:
        gd -= sal_a[gm]
        gm += 1
    return gy, gm + 1, gd


def j_month_len(jy, jm):
    if jm <= 6:
        return 31
    if jm <= 11:
        return 30
    # اسفند: تبدیل رفت‌وبرگشت — اگر ۳۰ اسفند پایدار بود، سال کبیسه است
    gy, gm, gd = j2g(jy, 12, 30)
    j2 = g2j(gy, gm, gd)
    return 30 if (j2[1] == 12 and j2[2] == 30) else 29


def next_jmonth(jy, jm):
    return (jy + 1, 1) if jm == 12 else (jy, jm + 1)


FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


# v9.2 — یکسان‌سازی نوشتار عربی/فارسی + حذف نیم‌فاصله، برای تطبیق کلیدواژه‌ها.
# (هم‌رفت با fts_engine.norm_fa؛ اینجا import نمی‌شود تا اسکریپت dev مستقل بماند.)
def norm_fa(text):
    s = str(text if text is not None else "")
    if not s:
        return ""
    s = s.replace("\u064a", "\u06cc").replace("\u0643", "\u06a9").replace("\u0649", "\u06cc")
    return s.replace("\u200c", "")


# ---------------------------------------------------------------------- #
#  استخراج «تاریخ برگزاری رویداد» و ساعت از متن عنوان اطلاعیه
#  (تقویم بورسی باید روی روز برگزاری جلسه بنشیند نه روز انتشار نامه)
# ---------------------------------------------------------------------- #
DATE_RE = re.compile(r"(?:مورخ|مؤرخ|تاریخ)\s*([0-9]{4})/([0-9]{1,2})/([0-9]{1,2})")
TIME_RE = re.compile(r"ساعت\s*([0-9]{1,2}):([0-9]{2})")


def extract_when(title: str, pub_iso: str):
    """تاریخ رویداد از الگوهای عنوان (مورخ ۱۴۰۵/۰۶/۱۵ ...) — fallback: تاریخ انتشار.
    خروجی: (iso_event, time_HH:MM)"""
    norm = title.translate(FA_DIGITS)
    tm = TIME_RE.search(norm)
    ev_time = f"{int(tm.group(1)):02d}:{tm.group(2)}" if tm else (pub_iso[11:16] if len(pub_iso) >= 16 else "00:00")
    m = DATE_RE.search(norm)
    if m:
        try:
            jy, jm, jd = int(m.group(1)), int(m.group(2)), int(m.group(3))
            gy, gm, gd = j2g(jy, jm, jd)
            return f"{gy:04d}-{gm:02d}-{gd:02d}T{ev_time}:00+03:30", ev_time
        except Exception:
            pass
    return pub_iso, ev_time


def letter_url(u):
    u = (u or "").strip()
    if not u:
        return ""
    return u if u.startswith("http") else "https://codal.ir" + (u if u.startswith("/") else "/" + u)


DEFAULT_DB = ROOT / "market.db"

# نرمال‌سازی نماد برای تطبیق: نیم‌فاصله/فاصله حذف، ی/ك عربی → فارسی، ة → ه.
# بدون این، نرخ تطبیق نماد کدال با instruments حدود ۳۲٪ بود؛ با آن ~۶۸٪.
NORM_TRANS = str.maketrans({"ي": "ی", "ك": "ک", "ة": "ه", "ى": "ی",
                            "\u200c": "", " ": "", "\u00a0": ""})


def norm_sym(s):
    return (s or "").strip().translate(NORM_TRANS)


# ---------------------------------------------------------------------- #
#  نگاشت نماد → صنعت  (جدول instruments در market.db محلی)
# ---------------------------------------------------------------------- #
def load_industries(db_path=None):
    """نگاشت «نماد نرمال‌شده → نام صنعت» از جدول instruments.

    TSETMC نام نماد را در دو ستون نگه می‌دارد (l_val18 و l_val30)؛ کدال در
    فیلد Symbol همان نماد کوتاه را می‌دهد، پس هر دو ثبت می‌شوند. کلیدها
    نرمال‌سازی می‌شوند تا اختلاف نیم‌فاصله/ی-ک عربی مانع تطبیق نشود.
    دیتابیس فقط‌خواندنی (mode=ro) باز می‌شود تا قفل هم‌زمان نسازد.
    """
    p = Path(db_path) if db_path else DEFAULT_DB
    if not p.exists():
        print(f"[industries] دیتابیس یافت نشد ({p}) → meta.industries خالی می‌ماند")
        return {}
    uri = "file:%s?mode=ro" % str(p).replace("\\", "/")
    try:
        c = sqlite3.connect(uri, uri=True, timeout=20)
    except Exception as e:
        print(f"[industries] باز کردن دیتابیس ناموفق: {e}")
        return {}
    out = {}
    try:
        rows = c.execute(
            "SELECT l_val18, l_val30, sector_name FROM instruments "
            "WHERE COALESCE(sector_name, '') <> ''").fetchall()
        for s18, s30, sec in rows:
            sec = (sec or "").strip()
            if not sec:
                continue
            for s in (s18, s30):
                k = norm_sym(s)
                if k and k not in out:
                    out[k] = sec
        print(f"[industries] {len(out)} کلید نماد از {len(rows)} رکورد instruments")
    except Exception as e:
        print(f"[industries] کوئری ناموفق: {e}")
    finally:
        c.close()
    return out


# ---------------------------------------------------------------------- #
#  ADB IP Rotate (حالت پرواز سیم‌کارت)
# ---------------------------------------------------------------------- #
# v9.2 رفع باگ کرش: در نسخهٔ قبلی نام این تابع `adb_rotate` بود و هر دو تابع
# polite_get / fetch_month پارامتری bool به همان نام داشتند → پارامتر، تابعِ
# هم‌سطح را می‌پوشاند (shadow) و `adb_rotate()` داخل آن‌ها یعنی
# «فراخوانی یک bool» → TypeError: 'bool' object is not callable.
# یعنی سوییچ --adb-rotate در عمل هرگز کار نمی‌کرد و روی اولین 429 می‌شد
# اسکریپت را می‌ترکاند. نام تابع به adb_rotate_ip تغییر کرد تا تداخل نباشد.
#
# v9.3 — بدنهٔ محلی حذف شد و چرخش کامل به codal_fetcher.rotate_ip_via_adb
# واگذار گردید (دستور کار: «فقط ADB — همان rotate_ip_via_adb موجود (۸۰s+۲۰s)
# همه‌جا استفاده شود»). کپیِ دومِ منطقِ چرخش، یعنی دو منبع حقیقت که با هم
# همگام نمی‌مانند — و نسخهٔ اینجا از قبل هم باگِ توگلِ کوتاه را داشت.
def adb_rotate_ip():
    """چرخش IP سیم‌کارت — واگذارده به codal_fetcher.rotate_ip_via_adb.

    تابع مرجع این‌ها را به عاریت می‌گیرد (چیزی که نسخهٔ محلی نداشت):
      • توگل کامل: airplane enable → ۸۰s → disable → ۲۰s (تخریب PDP؛ توگل
        کوتاه‌تر از ۶۰s IP را پین‌شده نگه می‌دارد — اندازه‌گیری MCI)
      • تأیید واقعی تغییر IP (api.ipify.org) — نه فقط returncode adb
      • خاموش/روشن موقتِ Wi-Fi ویندوز (باگ ۰۹-۰۵: ترافیک از مودم می‌رففت)
      • قفل غیرهم‌بلوک + _ADB_MIN_GAP (چرخش تکراری زدن نمی‌شود)
      • Retry+Re-connect دستگاه روی offline/unauthorized + بازگردانی
        تضمینی Wi-Fi در finally
    بازگشتی: True = IP تازه (یا چرخشِ همین‌ان انجام‌شده)، False = شکست.
    """
    return bool(_cf.rotate_ip_via_adb())


# ---------------------------------------------------------------------- #
#  کنترل نرخ: Polite Delay + Exponential Backoff
# ---------------------------------------------------------------------- #
# v9.2 — سه مشکل در نسخهٔ قبل رفع شد:
#  ۱) پارامتر bool به نام adb_rotate، تابع هم‌نام را می‌پوشاند و
#     `adb_rotate()` داخل این تابع TypeError می‌داد (--adb-rotate عملاً کرش).
#  ۲) هیچ مکثی «قبل» از درخواست اول هر صفحه نبود؛ فقط بین تلاش‌های backoff
#     می‌خوابید → در صفحات بالا (PageNumber>۲۰) پشت‌سرهم و بدون ریتم می‌رفت و 429
#     می‌گرفت. حالا POLITE_DELAY (۱.۵–۲.۰s) قبل از هر درخواست اعمال می‌شود.
#  ۳) پاسخ 429 اگر JSON نباشد (WAF html) با ValueError می‌ترکید؛ و هدر
#     Retry-After نادیده گرفته می‌شد.
POLITE_DELAY = (1.5, 2.0)      # ثانیه — قبل از هر درخواست
BACKOFF_BASE = 2.0             # 2 → 4 → 8 → 16 …
BACKOFF_CAP = 90.0             # سقف یک خواب (ثانیه)
BLOCK_STATUSES = (403, 408, 425, 429, 500, 502, 503, 504)


def _retry_after(resp):
    """هدر Retry-After (ثانیه یا HTTP-date) → ثانیه، یا None."""
    v = (resp.headers.get("Retry-After") or "").strip()
    if not v:
        return None
    try:
        return max(0.0, float(v))
    except ValueError:
        pass
    try:
        from email.utils import parsedate_to_datetime
        from datetime import datetime, timezone
        dt = parsedate_to_datetime(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (dt - datetime.now(timezone.utc)).total_seconds())
    except Exception:
        return None


def polite_get(session, params, rotate=False, max_backoffs=5, stats=None):
    """GET با ریتم محترمانه و backoff نمایی.

    rotate=True → بعد از دو تلاش ناموفق، حالت پرواز adb برای گرفتن IP جدید.
    stats → اگر dict داده شود، شمارش‌های پایش (req / backoff / rotate / fail)
            ثبت می‌شود تا در لاگ پایانی گزارش شود.
    """
    if stats is not None:
        stats["req"] = stats.get("req", 0) + 1
    backoffs = 0
    last_code = None
    for attempt in range(max_backoffs + 1):
        time.sleep(random.uniform(*POLITE_DELAY))     # Polite Delay
        try:
            r = session.get(BASE, params=params, timeout=30)
        except Exception as e:
            last_code = "EXC"
            print(f"  [net] {type(e).__name__}: {e}")
            r = None
        if r is not None and r.status_code == 200:
            try:
                return r.json()
            except ValueError:
                # بدنهٔ HTML = صفحهٔ چالش WAF، نه JSON → مثل بلاک رفتار کن
                last_code = "WAF"
            except Exception:
                last_code = "BAD"
        else:
            last_code = r.status_code if r is not None else "NOCONN"
        if attempt == max_backoffs:
            break
        wait = min(BACKOFF_CAP, BACKOFF_BASE * (2 ** backoffs))
        ra = _retry_after(r) if r is not None else None
        if ra:
            wait = max(wait, min(ra, BACKOFF_CAP))
        backoffs += 1
        if stats is not None:
            stats["backoff"] = stats.get("backoff", 0) + 1
        print(f"  [{last_code}] backoff {wait:.0f}s (تلاش {attempt + 1}/{max_backoffs + 1})")
        time.sleep(wait)
        if rotate and backoffs >= 2:
            if adb_rotate_ip():
                if stats is not None:
                    stats["rotate"] = stats.get("rotate", 0) + 1
                backoffs = 0        # IP تازه → چرخهٔ backoff از نو
    if stats is not None:
        stats["fail"] = stats.get("fail", 0) + 1
    raise RuntimeError(f"بعد از {max_backoffs + 1} تلاش ناموفق ({last_code})")


# ---------------------------------------------------------------------- #
#  کوئری‌های کلان ماه جلالی — v9.2 (بازطراحی داده‌محور)
# ---------------------------------------------------------------------- #
# راستی‌آزمایی روی API زنده (search.codal.ir/api/search/v2/q، ماه ۱۴۰۵/۰۶):
#   Subject=<متن فارسی>                 → Total=0   (پارامتر عددی است، متن رد می‌شود)
#   Title|Text|Keyword|Q|SearchText|…   → Total دقیقاً برابرِ بدونِ فیلتر
#                                         (جستجوی متن سمت سرور اصلاً وجود ندارد)
#   Category=<1..10>                    → تنها فیلتر موضوعیِ مؤثرِ سمت سرور
#   شمارش ماهانهٔ دسته‌ها: 1=542  2=456  3=1652  4=10  6=878  7=95
#
# پس «کوئری‌های صفر» یک باگ ساختاری بود: پنج کوئریِ Subject-based (پرداخت سود /
# افزایش سرمایه / عرضه اولیه / سررسید / لغو مجمع) همگی Total=0 می‌دادند و تنها
# Category=6 (مجامع) واقعاً نامه می‌آورد. راه‌حل v9.2:
#   فیلتر موضوعی سمت سرور با Category  +  شکار کلیدواژهٔ رسمی روی عنوان سمت کلاینت.
#
# ساختار: (برچسب، پارامترهای سرورساید، کلیدواژه‌های عنوان، event_type_id ثابت)
#   title_any=None → همهٔ نامه‌های دسته برداشت و فقط بر پایهٔ عنوان طبقه‌بندی می‌شوند
CAT_ASSEMBLY, CAT_IPO, CAT_DISCLOSURE = "6", "4", "2"

# ── واژگان رسمی کدال (تطبیق روی عنوان نرمال‌شده: بدون نیم‌فاصله، ی/ک عربی → فارسی)
IPO_KEYS = ("عرضه اولیه", "عرضه اوليه", "عرضه در بازار", "پذیره نویسی", "پذیرهنویسی",
            "آگهی پذیرهنویسی", "نشریه عرضه", "امیدنامه پذیرش", "پذیرش در بورس",
            "پذیرش در فرابورس", "پذيرش در بورس", "پذيرش در فابورس")
# «سررسید» برای برچسب‌زدن دقیق؛ «مرابحه/اجاره/اوراق» تنها برای *شکار* در دستهٔ ۲
# (واژگان درخواستی دستور کار) — چون به‌تنهایی برای دسته‌بندی بیش از حد عام‌اند
# («نشریه عرضه اوراق بهادار…» یک عرضهٔ اولیه است نه سررسید).
MATURITY_KEYS = ("سررسید", "سررسيد", "اخزا", "صکوک", "صكوك",
                 "اوراق مرابحه", "اوراق اجاره", "اوراق بدهی", "اوراق مشارکت",
                 "اوراق مشتقه", "اوراق گامپ", "اوراق سلف", "اوراق اجارهداری")
MATURITY_HUNT_KEYS = MATURITY_KEYS + ("مرابحه", "اجاره", "اوراق")
ASSEMBLY_KEYS = ("مجمع", "دعوت به مجمع", "تصمیمات مجمع", "لغو مجمع", "عدم برگزاری مجمع",
                 "تغییر زمان مجمع", "به تعویق", "تقسیم سود", "تخصیص سود", "سود نقدی",
                 "افزایش سرمایه")

QUERIES = [
    # مجامع: «آگهی دعوت» و «تصمیمات مجمع». افزایش سرمایه و تقسیم سود هم از دلِ
    # همین دسته درمی‌آید — در Category=1 (صورت‌های مالی) هرگز پیدا نمی‌شوند
    # (۵۴۲ نامهٔ یک ماه کامل اسکن شد: صفر برخورد).
    ("assembly",     {"Category": CAT_ASSEMBLY},   None,               None),
    # عرضه اولیه: دستهٔ «پذیرش / امیدنامه». ارزان‌ترین و دقیق‌ترین منبع (~۱۰ نامه/ماه).
    ("ipo",          {"Category": CAT_IPO},        IPO_KEYS,           None),
    # افشای اطلاعات بااهمیت: سررسید اوراق/صکوک و قراردادها (مرابحه/اجاره).
    ("bondMaturity", {"Category": CAT_DISCLOSURE}, MATURITY_HUNT_KEYS, None),
]


def title_has(title, keys):
    """آیا عنوان، هیچ‌یک/یکی از کلیدواژه‌ها را دارد؟

    هر دو نگارش سنجیده می‌شود: «عنوانِ نرمال‌شده» و «عنوانِ نرمال‌شدهٔ بدون فاصله»،
    تا «پذیره نویسی» / «پذیرهنویسی» / «پذیره‌نویسی» هر سه بخورد.
    (نکته: کلیدواژهٔ جستجو هم باید فاصله‌زدایی شود — وگرنه «افزایش سرمایه» هرگز
    در رشتهٔ فاصله‌زدایی‌شده پیدا نمی‌شود؛ باگی که تست v9.2 گرفت.)
    """
    if not keys:
        return True
    t = norm_fa(title)
    ts = t.replace(" ", "")
    for k in keys:
        k_n = norm_fa(k)
        if k_n in t or k_n.replace(" ", "") in ts:
            return True
    return False


DIVIDEND_KEYS = ("تقسیم سود", "تخصیص سود", "سود نقدی", "سود نقدي", "نقدینگی سود",
                 "تقسیم نقدی")
EXTRA_KEYS = ("فوق العاده", "فوق‌العاده", "فوقالعاده")
CANCEL_KEYS = ("لغو", "عدم برگزاری", "به تعویق", "تغییر زمان", "انتقال مجمع",
               "موافقت با تغییر")


def classify_tid(title):
    """event_type_id را از عنوان می‌سازد — همان تفسیری که calendarService.classify
    سمت فرانت از این عدد می‌خواند (tid=1 عادی، 2 فوق‌العاده، 3 تقسیم سود).

    v9.2:
      • «پرداخت سود» حالا از دل تصمیمات مجمع شکار می‌شود؛ قبلاً از یک کوئریِ
        Subject می‌آمد که هرگز جواب نمی‌داد → شاخهٔ dividend مرده بود.
      • «لغو/تغییر زمان مجمع» اول سنجیده می‌شود و tid=0 می‌گیرد؛ وگرنه چنین
        نامه‌ای که «مجمع فوق‌العاده» در عنوانش هست به‌اشتباه tid=2 می‌گرفت.
      • مقایسهٔ «افزایش سرمایه» روی نسخهٔ فاصله‌زدایی‌شده انجام می‌شود
        (باگ v9.2: کلید با فاصله در رشتهٔ بدون فاصله جستجو می‌شد).
    """
    t = norm_fa(title)
    ts = t.replace(" ", "")
    if any(k.replace(" ", "") in ts for k in CANCEL_KEYS):
        return 0                       # لغو/تغییر زمان — فرانت عنوان‌محور می‌زند
    if title_has(t, DIVIDEND_KEYS):
        return 3                       # پرداخت سود نقدی
    if "افزایشسرمایه" in ts:
        return 0                       # افزایش سرمایه (فرانت عنوان‌محور تشخیص می‌دهد)
    if any(k in ts for k in ("فوقالعاده",)):
        return 2                       # مجمع فوق‌العاده
    if "مجمع" in ts:
        return 1                       # مجمع عادی
    return 0


# کلیدواژه‌های «عرضه اولیه» برای فرانت — فرانت فقط /عرضه\s*اولیه/ را می‌شناخت،
# ولی نامه‌های رسمی دستهٔ ۴ با عنوان «امیدنامه پذیرش در بورس…» می‌آیند.
IPO_ACCEPT_KEYS = IPO_KEYS


def category_of(title, tid=0):
    """برچسب دسته (هم‌نام با CATS در static/calendar/calendarService.js).

    v9.2 — ترتیب سنجش عمداً مو به مو با classify() فرانت یکی شده است؛ قبلاً این
    زنجیرهٔ if در پایتون نسخهٔ خودش را داشت و با نسخهٔ JS هم‌خوان نبود (مثلاً
    «لغو» را بدون نرمال‌سازی می‌جست و «فوقالعاده» بدون نیم‌فاصله رد می‌شد).
    """
    t = norm_fa(title)
    ts = t.replace(" ", "")
    if any(k.replace(" ", "") in ts for k in CANCEL_KEYS):
        return "assemblyChange"
    if tid == 1:
        return "assembly"
    if tid == 2:
        return "assemblyExtra"
    if tid == 3:
        return "dividend"
    if title_has(t, MATURITY_KEYS):
        return "bondMaturity"
    if title_has(t, IPO_ACCEPT_KEYS):
        return "ipo"
    if "افزایشسرمایه" in ts:
        return "capitalIncrease"
    return "other"


def fetch_month(session, jy, jm, rotate=False, req_counter=None, max_pages=60,
                stats=None, cats=None, adb_every=0):
    """یک ماه جلالی را بر اساس QUERIES (فیلتر Category سمت سرور) برمی‌دارد.

    v9.2:
      • ساختار QUERIES چهارتایی شد → (برچسب، پارامتر، کلیدواژه‌های عنوان، tid ثابت)
      • فیلتر کلیدواژه سمت کلاینت اعمال می‌شود (چون API جستجوی متن ندارد)
      • مکث محترمانه داخل polite_get است؛ sleep تکراری اینجا حذف شد
      • `adb_rotate()` معیوب (فراخوانی bool) حذف شد؛ چرخش فقط روی شکست، یا
        هر `adb_every` درخواست اگر کاربر صریحاً بخواهد
    """
    fd, td = f"{jy}/{jm:02d}/01", f"{jy}/{jm:02d}/{j_month_len(jy, jm):02d}"
    events, seen = [], set()
    queries = [q for q in QUERIES if (not cats) or (q[1].get("Category") in cats)]
    for (cat, params, title_any, fixed_tid) in queries:
        letters, page, total = [], 1, None
        while True:
            q = {"PageNumber": page, "PageSize": 20, "search": True,
                 "FromDate": fd, "ToDate": td, **params}
            j = polite_get(session, q, rotate=rotate, stats=stats)
            total = j.get("Total", 0)
            batch = j.get("Letters", [])
            letters.extend(batch)
            page += 1
            if req_counter is not None:
                req_counter[0] += 1
                if rotate and adb_every and req_counter[0] % adb_every == 0:
                    adb_rotate_ip()
            # کدال حداکثر ۲۰ آیتم در صفحه برمیگرداند
            if not batch or len(letters) >= total or page > max_pages:
                break
        kept = sum(1 for L in letters if title_has(L.get("Title") or "", title_any))
        gate = "" if not title_any else f" → {kept} مطابق کلیدواژه"
        print(f"  {cat:16} [{fd} .. {td}] → {len(letters)} نامه "
              f"(total {total}, pages {page - 1}){gate}")
        # v2.2 — اگر سقف صفحات زودتر از پایان نتایج بخورد، بخش بزرگی از ماه
        # بی‌صدا دور ریخته می‌شود (در اجراى واقعی: ۳۰۰ از ۸۷۸ نامهٔ مجامع).
        if total and len(letters) < total:
            print(f"  ⚠ {cat}: سقف --max-pages={max_pages} زودهنگام خورد — "
                  f"{total - len(letters)} نامه گرفته نشد! (با --max-pages بیشتر اجرا کنید)")
        for L in letters:
            title = (L.get("Title") or "").strip()
            # شکار کلیدواژه سمت کلاینت (جایگزین Subject= که سمت سرور بی‌اثر بود)
            if title_any and not title_has(title, title_any):
                continue
            tid = str(L.get("TracingNo") or "")
            if not tid or tid in seen:
                continue
            seen.add(tid)
            pub = str(L.get("PublishDateTime") or "").translate(FA_DIGITS)
            try:
                date_part, time_part = pub.split(" ")
                jy2, jm2, jd2 = [int(x) for x in date_part.split("/")]
                hh, mm, _ = (time_part.split(":") + ["0", "0"])[:3]
                gy, gm, gd = j2g(jy2, jm2, jd2)
                pub_iso = f"{gy:04d}-{gm:02d}-{gd:02d}T{int(hh):02d}:{int(mm):02d}:00+03:30"
            except Exception:
                pub_iso = None
            if not pub_iso:
                continue
            # v2.1: تاریخ برگزاری رویداد از عنوان (مورخ ...) — نه تاریخ انتشار
            iso, ev_time = extract_when(title, pub_iso)
            # v9.2: طبقه‌بندی عنوان‌محور (classify_tid) — همان تفسیری که فرانت از
            # event_type_id می‌خواند؛ «پرداخت سود» حالا از دل تصمیمات مجمع درمی‌آید.
            etid = fixed_tid if fixed_tid is not None else classify_tid(title)
            events.append({
                "asset_id": "",
                "asset_symbol_trade": (L.get("Symbol") or "").strip(),
                "date_time": iso,
                "description": title,
                "report_id": tid,
                "event_title": title,
                "event_type_id": etid,
                "event_time": ev_time,
                "link": letter_url(L.get("Url"))
            })
    return events


def main():
    ap = argparse.ArgumentParser(description="BorsTerminal calendar fetcher (codal)")
    ap.add_argument("--jmonth", default=None, help="ماه جلالی شروع به‌صورت 1405/06 (پیشفرض: ماه جاری)")
    ap.add_argument("--months", type=int, default=1, help="تعداد ماه‌های پیوسته (پیشفرض ۱)")
    ap.add_argument("--db", default=None, help="مسیر market.db برای ذخیره SQLite (اختیاری)")
    ap.add_argument("--map-db", default=None,
                    help="مسیر دیتابیس برای نگاشت نماد→صنعت (پیش‌فرض: market.db کنار پروژه)")
    ap.add_argument("--adb-rotate", action="store_true",
                    help="روی 429/بلاک WAF حالت پرواز adb → IP جدید "
                         "(airplane enable → 80s → disable → 20s؛ "
                         "codal_fetcher.rotate_ip_via_adb)")
    ap.add_argument("--adb-every", type=int, default=0,
                    help="چرخش IP پیش‌دستانه هر N درخواست (۰ = فقط هنگام شکست؛ پیش‌فرض ۰)")
    ap.add_argument("--cats", default=None,
                    help="فقط دسته‌های مشخص را کوئری کن، جداشده با ویرگول "
                         "(۱=صورت‌های مالی ۲=افشای بااهمیت ۳=فعالیت ماهانه ۴=پذیرش/عرضه ۶=مجامع). "
                         "پیش‌فرض: دسته‌های تعریف‌شده در QUERIES")
    ap.add_argument("--max-pages", type=int, default=60,
                    help="حداکثر صفحات در هر کوئری کلان (هر صفحه ۲۰ نامه؛ پیش‌فرض ۶۰ = ۱۲۰۰ نامه)")
    args = ap.parse_args()

    now = datetime.now()
    jy, jm, _ = g2j(now.year, now.month, now.day)
    if args.jmonth:
        y, m = args.jmonth.split("/")
        jy, jm = int(y), int(m)

    months = [(jy, jm)]
    for _ in range(args.months - 1):
        months.append(next_jmonth(*months[-1]))
    print(f"[plan] ماه‌های جلالی: {', '.join(f'{y}/{m:02d}' for y, m in months)}")
    cats = None
    if args.cats:
        cats = {c.strip() for c in args.cats.split(",") if c.strip()}
        print(f"[plan] دسته‌ها: {sorted(cats)}")
    if args.adb_rotate:
        print("[plan] ADB IP-rotate روشن — codal_fetcher.rotate_ip_via_adb "
              "(airplane enable → 80s → disable → 20s + تأیید IP)")

    sess = requests.Session()
    sess.headers.update({"User-Agent": UA, "accept": "application/json"})

    all_events, seen = [], set()
    req_counter = [0]
    stats = {"req": 0, "backoff": 0, "rotate": 0, "fail": 0}
    for (yy, mm) in months:
        print(f"[month] {yy}/{mm:02d}")
        for e in fetch_month(sess, yy, mm, rotate=args.adb_rotate,
                             req_counter=req_counter, max_pages=args.max_pages,
                             stats=stats, cats=cats, adb_every=args.adb_every):
            if e["report_id"] not in seen:
                seen.add(e["report_id"])
                all_events.append(e)

    all_events.sort(key=lambda e: e["date_time"])

    # v9.2 — گزارش پایش نرخ: بی‌این آمار، «۴۲9 خوردن» و «صفحه ناقص» قابل تشخیص نبود
    by_cat = {}
    for e in all_events:
        by_cat[e["event_type_id"]] = by_cat.get(e["event_type_id"], 0) + 1
    print("[stats] درخواست‌ها=%d | backoff=%d | چرخش IP=%d | شکست=%d"
          % (stats["req"], stats["backoff"], stats["rotate"], stats["fail"]))
    print("[stats] رویدادها به تفکیک tid: عادی=%d فوق‌العاده=%d سود=%d سایر/عرضه/سررسید=%d"
          % (by_cat.get(1, 0), by_cat.get(2, 0), by_cat.get(3, 0),
             sum(v for k, v in by_cat.items() if k not in (1, 2, 3))))

    # v2.2 — meta.industries: نگاشت نماد→صنعت تا فیلتر «صنعت» در تقویم فعال شود.
    # فقط نمادهای حاضر در رویدادها درج می‌شوند تا حجم کش بی‌جهت بالا نرود و
    # دراپ‌داون صنایع پرتکرار بماند (CalService.industries از همین می‌سازد).
    all_ind = load_industries(args.map_db)
    ev_syms = sorted({e["asset_symbol_trade"] for e in all_events if e["asset_symbol_trade"]})
    industries = {}
    for s in ev_syms:
        sec = all_ind.get(norm_sym(s))
        if sec:
            industries[s] = sec          # کلید خروجی = نماد خام کدال تا فیلتر فرانت بخورد
    print(f"[industries] {len(industries)} از {len(ev_syms)} نمادِ رویدادها صنعت دارند")

    payload = {
        "meta": {
            "source": "search.codal.ir/api/search/v2/q",
            "fetchedAt": datetime.utcnow().isoformat() + "Z",
            "jmonths": [f"{y}/{m:02d}" for y, m in months],
            "count": len(all_events),
            "industries": industries
        },
        "token": None,
        "events": all_events
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(OUT)
    print(f"[write] {OUT} → {len(all_events)} رویداد")

    if args.db:
        db = sqlite3.connect(args.db)
        db.execute("""CREATE TABLE IF NOT EXISTS calendar_events (
            report_id TEXT PRIMARY KEY, asset_id TEXT, symbol TEXT,
            event_type_id INTEGER, category TEXT, event_time TEXT,
            title TEXT, description TEXT, fetched_at TEXT)""")
        now_iso = datetime.utcnow().isoformat() + "Z"
        KEY2FA = {"assembly": "مجامع عادی", "assemblyExtra": "مجامع فوق‌العاده",
                  "assemblyChange": "لغو/تغییر زمان مجمع",
                  "dividend": "پرداخت سود نقدی", "capitalIncrease": "افزایش سرمایه",
                  "ipo": "عرضه اولیه", "bondMaturity": "سررسید اوراق/اخزا", "other": "سایر"}
        for e in all_events:
            # v9.2 — به‌جای زنجیرهٔ if موازیِ نسخهٔ JS، از category_of() استفاده می‌شود
            # که صراحتاً آینهٔ classify() فرانت است (تک‌منبع حقیقت).
            cat = category_of(e["event_title"], e["event_type_id"])
            db.execute("INSERT OR REPLACE INTO calendar_events VALUES (?,?,?,?,?,?,?,?,?)",
                       (e["report_id"], e["asset_id"], e["asset_symbol_trade"],
                        e["event_type_id"], KEY2FA[cat], e["date_time"],
                        e["event_title"], e["description"], now_iso))
        db.commit()
        db.close()
        dist = {}
        for e in all_events:
            c = category_of(e["event_title"], e["event_type_id"])
            dist[c] = dist.get(c, 0) + 1
        print(f"[db] {args.db} → calendar_events")
        print("[dist] " + " | ".join(f"{KEY2FA[k]}={n}" for k, n in sorted(
            dist.items(), key=lambda kv: -kv[1])))


if __name__ == "__main__":
    main()
