#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BorsTerminal — Codal FTS Updater v1.0  (dev/codal_fts_updater.py)
=====================================================================
اسکریپت سبک و **اختصاصی** برای تازه‌سازی دادهٔ خامِ ۵ شاخص FTS.

فلسفهٔ طراحی
-----------
کدال‌فچر اصلی (codal_fetcher.py، ~۳۱۰۰ خط) یک خطِ لولهٔ عمومی است: هر اطلاعیهٔ
«مفید» را برمی‌دارد و استخراج می‌کند. این اسکریپت برعکس، **منحصراً** حول ۵ شاخص
FTS تعریف شده و ورودی را به دو نوع اطلاعیه ایزوله می‌کند. ماشین‌افزار HTTP و
تجزیهٔ جدول (scrape_monthly_report / scrape_report / datasource / PATTERNS) از
codal_fetcher import می‌شود — کد تکراری نوشته نمی‌شود؛ فقط «محدودهٔ داده» و
«سیاست نرخ» جدید است.

الف) ایزولاسیون کامل دیتای ورودی — فقط ۲ نوع اطلاعیه از search.codal.ir
------------------------------------------------------------------------
  ۱. «گزارش فعالیت ماهانه»                (Category=3)
        → فروش تجمیعی دورهٔ جاری و دورهٔ مشابه سال قبل
          (ytd_revenue / ytd_revenue_prev)  →  شاخص ۱ (رشد فروش) و شاخص ۴
  ۲. «اطلاعات و صورت‌های مالی سالانه ۱۲ ماهه حسابرسی‌شده غیرتلفیقی» (Category=1)
        → سود خالص ۳ سال متوالی (basic_eps) → شاخص ۲
        → سود ناخالص ÷ درآمد عملیاتی        → شاخص ۳
  هر عنوان دیگری (مجمع، افشای بااهمیت، توقف، تغییر مدیران، صندوق، تلفیقی،
  حسابرسی‌نشده، میان‌دوره…) **قبل از هر درخواست شبکه** رد می‌شود.

  شاخص ۴ (فروش÷ارزش بازار) و شاخص ۵ (فیلتر صنعت) هیچ درخواست شبکه‌ای ندارند:
  مستقیماً از جداول لوکال market_watch و instruments همگام می‌شوند.

ب) مکانیزم ADB IP-Rotate  (`--adb-rotate`)
-------------------------------------------
روی 429 / بلاک WAF / بدنهٔ غیرJSON — چرخش **تطبیقی** با پایش پویا:
    ۱. Old_IP کش می‌شود (api.ipify.org → ifconfig.me/ip → icanhazip، تایم‌اوت ۳s)
    ۲. Wi-Fi ویندوز موقتاً خاموش (متریک ۵۵ < ۷۵ — وگرنه ترافیک از مودم می‌رود
       و توگل گوشی بی‌اثر است؛ باگ ۰۹-۰۵)
    ۳. سه متد به ترتیب امتحان می‌شوند:
         adb shell svc data disable/enable
         adb shell cmd connectivity airplane-mode enable/disable
         adb shell settings put global airplane_mode_on 1/0  (+ broadcast)
    ۴. بعد از هر توگل، حلقهٔ پایش هر ۳ ثانیه IP را می‌پرسد (سقف ۹۰ ثانیه) و
       به‌محض Old_IP != New_IP بیرون می‌آید و «IP changed in 42.1s» چاپ می‌کند
    ۵. Wi-Fi در همهٔ مسیرها (try/finally) برمی‌گردد
توجه: True **فقط** با دیدن IP تازه برگ می‌گردد؛ نسخهٔ قدیمی با «adb خطا نداد»
خود را موفق جا می‌زد. اگر هر سه متد تا سقف ۹۰s همان IP را دادند، اپراتور IP را
پین کرده و `--adb-long` (چرخهٔ ۸۰s+۲۰s کدال‌فچر) لازم است.
راستی‌آزمایی مستقل: `--rotate-test` (بدون هیچ درخواستی به کدال).
سپس واکشی **از همان نقطهٔ توقف** ادامه می‌یابد (resume — حالت در
dev/fts_update_state.json).

ج) دو مود کاری
--------------
    --mode monthly   واکشی سریع آخرین گزارش‌های ماهانه (تازه‌سازی شاخص فروش)
    --mode full      واکشی عمیق صورت‌های مالی سالانهٔ ۳ سال اخیر
    --mode local     بدون شبکه: فقط همگام‌سازی ارزش بازار/صنعت + بازخوانی کش

اجرا
----
    venv\\Scripts\\python.exe dev\\codal_fts_updater.py --mode monthly --symbols فولاد,خساپا,وپارس,وتجارة,شپنا
    venv\\Scripts\\python.exe dev\\codal_fts_updater.py --mode full --limit 5 --adb-rotate
    venv\\Scripts\\python.exe dev\\codal_fts_updater.py --mode local --verify
"""
from __future__ import annotations

import argparse
import io
import json
import os
import random
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime

# ---- UTF-8 روی کنسول ویندوز (cp1252 با هر print فارسی می‌شکند) -------------
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import codal_fetcher as cf          # noqa: E402  (ماشین‌افزار HTTP + تجزیه)
import fts_engine                    # noqa: E402  (۵ شاخص — منبع یگانه حقیقت)

DB_PATH = os.path.join(ROOT, "market.db")
STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "fts_update_state.json")
API = cf.API

# ── کدهای دستهٔ اطلاعیه در search.codal.ir ──
# این دو ثابت در نسخهٔ ۱٫۰ هیچ‌جا تعریف نشده بودند و باعث می‌شدند هر اجرای
# واقعیِ «--mode monthly/full» بلافاصله با NameError بمیرد (py_compile و
# تست‌های آفلاین ایزولاسیون این مسیر را نمی‌پیمودند؛ فقط تست زنده لو می‌دهد).
# مقدارها از منبع یگانهٔ حقیقت (codal_fetcher.py:2755 و PROBE-VERIFIED 2108):
#   Category 1 = صورتهای مالی   |   Category 3 = گزارش فعالیت ماهانه
CAT_MONTHLY = "3"
CAT_FS = "1"

# اندازهٔ صفحهٔ search API. این ثابت هم تعریف نشده بود (باگ هم‌خانوادهٔ
# CAT_MONTHLY). مقدار از شواهد آزمایشیِ خودِ کدال‌فچر (نزدیک خط ۲۱۰۸:
# «page 1 of Category=1 returns 20 letters … Category=3 returns 20 monthly
# reports») گرفته شده، نه حدس: API به‌صورت پیش‌فرض ۲۰ نامه در هر صفحه می‌دهد.
# به همین عدد، پایان صفحه‌بندی هم گره خورده است: (page-1)*PAGE_SIZE >= total.
PAGE_SIZE = 20

# ─────────────────────────────── تنظیمات نرخ ─────────────────────────────── #
POLITE_DELAY = (1.5, 2.0)     # ثانیه قبل از هر درخواست (دستور کار: ۱.۵–۲)
BACKOFF_BASE = 2.0            # 2 → 4 → 8 → 16 → 32 …
BACKOFF_CAP = 90.0
MAX_BACKOFFS = 5

# ───────────────── چرخش تطبیقی IP — ثابت‌های پایش پویا ───────────────── #
# چرا حلقهٔ پایش و نه تایمر هاردکد: زمان واکنش گوشی و برقراری مجدد سشن دیتا
# روی شبکهٔ همراه نوسان دارد (روی MCI بین ~۱۵ تا ~۹۰ ثانیه اندازه‌گیری شده).
# خوابِ ثابت یا کوتاه است (IP هنوز عوض نشده و درخواست بعدی هم بلاک می‌شود) یا
# بلند (زمان دور ریخته می‌شود). حلقه به‌محض دیدن IP تازه خارج می‌شود.
IP_ECHOES = ("https://api.ipify.org", "https://ifconfig.me/ip",
             "https://icanhazip.com")
IP_TIMEOUT = 3.0                  # هر echo: حداکثر ۳ ثانیه (دستور کار)
ROTATE_POLL = 3.0                 # گام پایش (دستور کار: هر ۳ ثانیه)
ROTATE_DEADLINE = 90.0            # سقف پایش برای هر متد (دستور کار: ۹۰ ثانیه)
DATA_DWELL = 5.0                  # مکث در حالت قطع تا سشن PDP واقعاً تخریب شود
ROTATE_MIN_GAP = 60.0             # حداقل فاصله بین دو چرخش (ضد چرخش بی‌فایده)
ADB_SERIAL = "RFCT30KRY6D"        # گوشی مرجع — اگر متصل باشد اولویت می‌گیرد
ADB_PATH = r"C:\adb\platform-tools\adb.exe"   # مسیر دستور کار

# requests از طریق codal_fetcher در دسترس است؛ import مستقیم فقط fallback.
try:
    _requests = cf.requests
except Exception:                                  # pragma: no cover
    import requests as _requests                   # noqa: F401,E402



# ─────────────────── الف) دروازهٔ ایزولاسیون عنوان ─────────────────── #
# cf.norm() فاصله‌ها و نیم‌فاصله را حذف و ي/ك عربی را فارسی می‌کند.
#
# چرا کلیدها اینجا با خودِ cf.norm ساخته می‌شوند: نوشتن دستیِ نسخهٔ «چسبیده»
# منبع باگ است (مثلاً «داده‌های» → «دادههای» با ی، نه «دادهها»). با این روش
# عبارت‌ها به نوشتار خوانای اصلی نوشته می‌شوند و نرمال‌سازی تضمینی است.
def _n(*phrases):
    return tuple(cf.norm(p) for p in phrases)


# هر دو نوعِ مجازِ دستور کار، چند عنوان رسمیِ متفاوت در کدال دارند — پذیرفتن
# فقط یکی‌شان یعنی از دست دادن بخش عمدهٔ دیتا (این باگ در تست پیدا شد):
#   گزارش فعالیت ماهانه  ↔  گزارش اطلاعات و داده‌های فروش محصولات
MONTHLY_ANY = _n("فعالیت ماهانه", "فعاليت ماهانه",
                 "اطلاعات و داده‌های فروش", "اطلاعات و داده‌هاي فروش")

# «تلفیقی» و «نشده» صراحتاً مردودند (شرط جزوه برای شاخص ۲ و ۳).
# نکتهٔ مهم: «غیرتلفیقی» هم «تلفیقی» را زیررشته دارد، پس قبل از بررسیِ رد،
# موارد «غیرتلفیقی» باید از متن پاک شوند — وگرنه دقیقاً همان گزارشی که می‌خواهیم
# رد می‌شود (باگ v1.0 که در تست ایزولاسیون گرفته شد).
NONCONSOL = _n("غیرتلفیقی", "غيرتلفيقي", "تلفیقی نیست")
ANNUAL_FORBID = _n("تلفیقی", "تلفيقي", "نشده", "میاندوره", "میان دوره", "مياندوره",
                   "3 ماهه", "6 ماهه", "9 ماهه", "اصلاحیه", "اصلاحيه", "افشای", "افشاي")
# «سالانه» در عنوان رسمی کدال به شکل‌های مختلفی می‌آید؛ «اسفند» هم نشانهٔ
# پایان سال مالی است (گزارش‌های میاندوره به تیر/شهریور/دی ختم می‌شوند).
ANNUAL_ANY = _n("سالانه", "سال مالی", "12 ماهه", "۱۲ ماهه", "دوره 12 ماهه", "اسفند")
# «ممیزی شده» نوشتار رایج عنوان کدال است، «حسابرسی شده» نوشتار جزوه — هر دو لازم.
AUDITED_ANY = _n("ممیزی شده", "حسابرسی شده", "حسابرسي شده", "ممیزی‌شده", "حسابرسی‌شده")


def is_monthly_activity(title: str) -> bool:
    """فقط گزارش‌های فعالیت/فروش ماهانه — منبع شاخص ۱ و ۴."""
    t = cf.norm(title)
    return any(k in t for k in MONTHLY_ANY)


FS_ANY = _n("صورت‌های مالی", "صورتهای مالی", "صورتمالی", "صورتمالي")


def is_audited_annual_nonconsolidated(title: str) -> bool:
    """فقط «صورت‌های مالی سالانهٔ ۱۲ ماههٔ ممیزی‌شدهٔ غیرتلفیقی».

    منبع شاخص ۲ (EPS سه سال متوالی) و شاخص ۳ (سود ناخالص ÷ درآمد عملیاتی).
    """
    t = cf.norm(title)
    bare = t
    for g in NONCONSOL:                       # «غیرتلفیقی» را بی‌اثر کن
        bare = bare.replace(g, "")
    if any(k in bare for k in ANNUAL_FORBID):
        return False
    has_fs = any(k in t for k in FS_ANY)
    has_12 = any(k in t for k in ANNUAL_ANY)
    has_audit = any(k in t for k in AUDITED_ANY)
    return bool(has_fs and has_12 and has_audit)


def notice_kind(title: str):
    """'monthly' | 'annual' | None — تنها این دو نوع اطلاعیه مجازند."""
    if is_monthly_activity(title):
        return "monthly"
    if is_audited_annual_nonconsolidated(title):
        return "annual"
    return None


# ──────────────── ب) چرخش IP + کنترل نرخ (با Resume) ──────────────── #
STATS = {"req": 0, "backoff": 0, "rotate": 0, "rotate_fail": 0, "blocked": 0,
         "letters": 0, "in_scope": 0, "scraped": 0, "saved_ms": 0,
         "saved_fs": 0, "rejected_title": 0, "skipped_known": 0,
         "rotate_unverified": 0, "rotate_secs": 0.0, "rotate_methods_tried": 0}


class Blocked(Exception):
    """429/WAF پایدار — فراخوان باید وضعیت را ذخیره و از همان‌جا ادامه دهد."""


def _wait_net_back(deadline=120.0, poll=3.0):
    """v9.8.1 — بعد از توگل حالت پرواز: تا برقراری اینترنت صبر کن.

    هر `poll` ثانیه یکی از echoهای IP عمومی را میپرسد؛ تا وقتی هیچ پاسخی
    نیامده گوشی/مسیر هنوز پایین است. سقفِ `deadline` ثانیه؛ خروجی True یعنی
    «اینترنت برگشت»، False یعنی «تا سقف مهلت برنگشت» (فراخوان به backoff
    نمایی برمی‌گردد). مکثِ اول ۵s برای بالا آمدن رابط دادهٔ گوشی است.
    """
    t0 = time.monotonic()
    time.sleep(5.0)
    while time.monotonic() - t0 <= deadline:
        if _public_ip(timeout=IP_TIMEOUT) is not None:
            return True
        time.sleep(poll)
    return False


def _adb_bin():
    """adb.exe: اول PATH، بعد مسیر دستور کار، بعد کاندیدهای کدال‌فچر."""
    w = shutil.which("adb")
    if w:
        return w
    if os.path.isfile(ADB_PATH):
        return ADB_PATH
    return cf._find_adb() if hasattr(cf, "_find_adb") else None


def _adb_exec(adb, args, timeout=15, serial=None):
    """یک فراخوانی adb (بدون پنجرهٔ اضافی، با سریال اختیاری)."""
    cmd = [adb] + (["-s", serial] if serial else []) + list(args)
    kw = dict(capture_output=True, text=True, timeout=timeout)
    if os.name == "nt":
        kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(cmd, **kw)


def _adb_serials(adb):
    """سریال دستگاه‌هایی که واقعاً در حالت 'device'‌اند (unauthorized/offline نه)."""
    try:
        r = _adb_exec(adb, ["devices"], timeout=8)
    except Exception:
        return []
    out = []
    for ln in (r.stdout or "").splitlines()[1:]:
        parts = ln.split()
        if len(parts) >= 2 and parts[1] == "device":
            out.append(parts[0])
    if ADB_SERIAL in out:                       # گوشی مرجع اول
        out.remove(ADB_SERIAL)
        out.insert(0, ADB_SERIAL)
    return out


def _looks_like_ip(s):
    """اعتبارسنجی سطحی پاسخ echo — از بلعیدن صفحهٔ خطا/HTML جلوگیری می‌کند."""
    s = (s or "").strip()
    if not s or len(s) > 64:
        return False
    if ":" in s:
        return all(c.isalnum() or c in ":." for c in s)
    return s.count(".") == 3 and all(c.isdigit() or c == "." for c in s)


def _public_ip(timeout=IP_TIMEOUT):
    """IP عمومی از اولین echo معتبر؛ None = شبکه در دسترس نیست."""
    for url in IP_ECHOES:
        try:
            r = _requests.get(url, timeout=timeout)
        except Exception:
            continue
        try:
            if getattr(r, "status_code", 0) == 200:
                ip = (r.text or "").strip()
                if _looks_like_ip(ip):
                    return ip
        except Exception:
            continue
        finally:
            try:
                r.close()
            except Exception:
                pass
    return None


def _wifi(on):
    """Wi-Fi ویندوز را خاموش/روشن می‌کند تا ترافیک از مسیر گوشی برود.

    چرا لازم است (باگ ۰۹-۰۵ کدال‌فچر): متریک Wi-Fi (55) از گوشی (75) بهتر است،
    پس ترافیک از مودم خانگی می‌رفت، توگل ایرپلین IP را عوض نمی‌کرد ولی تابع
    True برمی‌گرداند. بدون این، کل حلقهٔ پایش بی‌معنی است.
    """
    verb = "Enable" if on else "Disable"
    for name in ("Wi-Fi", "WLAN", "WiFi"):
        try:
            r = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command",
                 "%s-NetAdapter -Name '%s' -Confirm:$false" % (verb, name)],
                capture_output=True, timeout=25,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                if os.name == "nt" else 0)
            if r.returncode == 0:
                return True
        except Exception:
            continue
    return False



# ── حافظهٔ متد برنده (بخش «تطبیقی») ──
# در تست زنده ۰۹-۰۶: متد «svc data» ۹۴ ثانیه پایش بی‌نتیجه سوخت و متد
# «airplane-mode» در ۳.۰ ثانیه IP را عوض کرد. پس ترتیب ثابتِ دستور کار روی این
# اپراتور ~۹۰ ثانیه ضرر دارد. متدِ برنده در فایل memo ذخیره می‌شود و دور بعد
# از همان‌جا شروع می‌شود (اگر آن متد از کار افتاد، بقیه هم امتحان می‌شوند).
ROTATE_MEMO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "fts_rotate_memo.json")


def _load_method_pref():
    try:
        with io.open(ROTATE_MEMO_PATH, encoding="utf-8") as f:
            return (json.load(f) or {}).get("method") or ""
    except Exception:
        return ""


def _save_method_pref(name, secs):
    try:
        tmp = ROTATE_MEMO_PATH + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump({"method": name, "last_secs": round(secs, 1),
                       "at": datetime.now().isoformat(timespec="seconds")},
                      f, ensure_ascii=False, indent=1)
        os.replace(tmp, ROTATE_MEMO_PATH)
    except Exception:
        pass


def _ordered_methods():
    """متدها با اولویتِ آخرین متد موفق."""
    pref = _load_method_pref()
    ms = list(ROTATE_METHODS)
    if pref:
        for i, m in enumerate(ms):
            if m[0] == pref:
                if i:
                    ms.insert(0, ms.pop(i))
                    print("    [adb] متد «%s» قبلاً موفق بود → اول امتحان می‌شود"
                          % pref)
                break
    return ms


# ── متدهای تغییر وضعیت شبکه (دستور کار) ──
# هر متد یک «توگل کامل» است: قطع → مکث برای تخریب سشن → وصل. دلیلش این است که
# پایشِ IP باید در حالت متصل انجام شود؛ اگر گوشی در ایرپلین بماند هیچ echo ای
# پاسخ نمی‌دهد و تغییر هرگز تشخیص داده نمی‌شود. «revert» فقط بیمهٔ safety است.
ROTATE_METHODS = (
    ("svc data disable/enable",
     (("cmd", ("shell", "svc", "data", "disable")),
      ("sleep", DATA_DWELL),
      ("cmd", ("shell", "svc", "data", "enable"))),
     (("cmd", ("shell", "svc", "data", "enable")),)),
    ("cmd connectivity airplane-mode",
     (("cmd", ("shell", "cmd", "connectivity", "airplane-mode", "enable")),
      ("sleep", DATA_DWELL),
      ("cmd", ("shell", "cmd", "connectivity", "airplane-mode", "disable"))),
     (("cmd", ("shell", "cmd", "connectivity", "airplane-mode", "disable")),)),
    ("settings put global airplane_mode_on",
     (("cmd", ("shell", "settings", "put", "global", "airplane_mode_on", "1")),
      ("cmd", ("shell", "am", "broadcast", "-a",
               "android.intent.action.AIRPLANE_MODE", "--ez", "state", "true")),
      ("sleep", DATA_DWELL),
      ("cmd", ("shell", "settings", "put", "global", "airplane_mode_on", "0")),
      ("cmd", ("shell", "am", "broadcast", "-a",
               "android.intent.action.AIRPLANE_MODE", "--ez", "state", "false"))),
     (("cmd", ("shell", "settings", "put", "global", "airplane_mode_on", "0")),
      ("cmd", ("shell", "am", "broadcast", "-a",
               "android.intent.action.AIRPLANE_MODE", "--ez", "state", "false")))),
)


def _run_steps(adb, serial, steps):
    """مراحل یک متد را اجرا می‌کند. False = حداقل یک فرمان رد شد/خطا داد."""
    for kind, payload in steps:
        if kind == "sleep":
            time.sleep(payload)
            continue
        try:
            r = _adb_exec(adb, payload, timeout=15, serial=serial)
        except Exception as e:
            print("    [adb]   x %s -> %s: %s"
                  % (" ".join(payload), type(e).__name__, e))
            return False
        if r.returncode != 0:
            err = " ".join((r.stderr or r.stdout or "").split())[:110]
            print("    [adb]   x %s -> rc=%s %s"
                  % (" ".join(payload), r.returncode, err or "(بدون پیام)"))
            return False
    return True


def _poll_for_new_ip(old_ip, deadline=ROTATE_DEADLINE, label=""):
    """حلقهٔ پایش پویا — هر ROTATE_POLL ثانیه IP را می‌پرسد.

    بازگشت (status, ip, elapsed):
      changed    → Old_IP != New_IP (موفقیت؛ زمان دقیق چاپ می‌شود)
      unverified → baseline نداشتیم ولی حالا IP هست (اتصال تازه، تغییر اثبات‌نشده)
      same       → تا سقف مهلت همان IP قبلی ماند
      down       → تا سقف مهلت هیچ IP ای خوانده نشد
    """
    t0 = time.monotonic()
    tick = 0
    ip = None
    while True:
        time.sleep(ROTATE_POLL)
        el = time.monotonic() - t0
        ip = _public_ip()
        tick += 1
        if ip and old_ip and ip != old_ip:
            print("    [adb] IP changed in %.1fs  (%s -> %s)  [%s]"
                  % (el, old_ip, ip, label))
            return "changed", ip, el
        if ip and not old_ip:
            print("    [adb] اتصال تازه برقرار شد ولی baseline نبود — IP=%s (%.1fs)"
                  % (ip, el))
            return "unverified", ip, el
        if el >= deadline:
            return ("same" if old_ip else "down"), ip, el
        if tick % 5 == 0:                 # زنده بودن کار را به اپراتور نشان بده
            print("    [adb]   ... %-14s پس از %.0fs  [%s]"
                  % (ip or "بدون اتصال", el, label))


_LAST_ROTATE_AT = 0.0
_LAST_ROTATION = None


def adb_rotate(long_cycle=False, deadline=ROTATE_DEADLINE):
    """چرخش تطبیقی IP سیم‌کارت با پایش پویا (بدون تایمر هاردکد).

    الف) Old_IP کش می‌شود (api.ipify.org → ifconfig.me → icanhazip، تايم‌اوت ۳s)
    ب) سه متد شبکه به ترتیب روی دستگاه متصل امتحان می‌شوند
    ج) بعد از هر توگل، حلقهٔ پایش هر ۳ ثانیه (سقف deadline ثانیه) IP را می‌پرسد
       و به‌محض دیدن IP تازه بیرون می‌آید و زمان دقیق را چاپ می‌کند
    د) True فقط وقتی برگ می‌گردد که تغییر IP واقعاً دیده شود (یا اتصال تازه
       بدون baseline) — برخلاف نسخهٔ قدیمی که صرفاً «adb خطا نداد» را موفقیت
       می‌شمرد و روی بن همان IP را ادامه می‌داد.

    long_cycle=True → چرخهٔ ۸۰s+۲۰s کدال‌فچر؛ روی اپراتورهایی که توگل کوتاه
    IP را پین نگه می‌دارند (MCI) لازم است.
    """
    global _LAST_ROTATE_AT
    if long_cycle:
        ok = bool(cf.rotate_ip_via_adb(quiet=False))
        STATS["rotate" if ok else "rotate_fail"] += 1
        return ok
    if time.monotonic() - _LAST_ROTATE_AT < ROTATE_MIN_GAP:
        print("    [adb] %.0fs پیش چرخیده — برای جلوگیری از چرخش بی‌فایده رد شد"
              % (time.monotonic() - _LAST_ROTATE_AT))
        return False

    adb = _adb_bin()
    if not adb:
        print("    [adb] adb.exe پیدا نشد (PATH یا %s) — چرخش IP ممکن نیست" % ADB_PATH)
        STATS["rotate_fail"] += 1
        return False
    serials = _adb_serials(adb)
    if not serials:
        print("    [adb] دستگاه متصلی در حالت 'device' نیست — چرخش ممکن نیست")
        STATS["rotate_fail"] += 1
        return False
    serial = serials[0]
    down_seen = False          # هیچ IP ای خوانده نشد ⇒ مسیرِ اینترنتِ PC از گوشی نیست

    old_ip = _public_ip()
    print("    [adb] device=%s  old IP=%s" % (serial, old_ip or "نامعلوم"))

    wifi_off = False
    if _wifi(False):
        wifi_off = True
        time.sleep(2.0)
        old_ip = _public_ip() or old_ip          # baseline از مسیر گوشی

    try:
        for name, act, revert in _ordered_methods():
            STATS["rotate_methods_tried"] += 1
            print("    [adb] متد «%s» …" % name)
            if not _run_steps(adb, serial, act):
                _run_steps(adb, serial, revert)   # بیمهٔ بازگردش
                continue
            st, ip, el = _poll_for_new_ip(old_ip, deadline, name)
            if st == "down":
                down_seen = True
            _run_steps(adb, serial, revert)       # همیشه حالت پرواز خاموش شود
            if st in ("changed", "unverified"):
                STATS["rotate"] += 1
                STATS["rotate_secs"] += el
                if st == "unverified":
                    STATS["rotate_unverified"] += 1
                _LAST_ROTATE_AT = time.monotonic()
                globals()["_LAST_ROTATION"] = (ip, el, name, st)
                if st == "changed":
                    _save_method_pref(name, el)
                return True
            print("    [adb] «%s» نتیجه نداد (%s, %.0fs) → متد بعدی" % (name, st, el))
        STATS["rotate_fail"] += 1
        if down_seen:
            print("    [adb] با خاموش‌کردن Wi-Fi هیچ اینترنتی نیامد ⇒ مسیرِ اینترنتِ PC "
                  "از گوشی نیست. روی گوشی «USB tethering» را روشن کن (Mobile hotspot & "
                  "tethering → USB tethering) و دیتای موبایل فعال باشد، بعد دوباره اجرا کن.")
        else:
            print("    [adb] هر %d متد امتحان شد ولی IP عوض نشد — احتمالاً اپراتور IP را "
                  "پین کرده؛ «--adb-long» را امتحان کنید." % len(ROTATE_METHODS))
        return False
    finally:
        if wifi_off:
            _wifi(True)



def api_get(session, params, rotate=False, long_cycle=False):
    """یک درخواست از search API با polite delay + exponential backoff + rotate.

    v9.8.1 — سه خطا هر کدام مسیر خودشان را دارند:
      * 429/403/WAF-HTML → backoff نمایی + چرخش IP با ADB (از تلاش دوم)
      * Timeout/قطع نشست (requests.exceptions.*) → چرخش فوری با پایش اینترنت؛
        تترینگ افتاده و sleep محض فقط وقت را میسوزاند — توگل حالت پرواز
        زده میشود و تا برقراری اینترنت (echo IP) صبر میشود، بعد ادامه.
    """
    r = None
    last = None
    for attempt in range(MAX_BACKOFFS + 1):
        time.sleep(random.uniform(*POLITE_DELAY))
        STATS["req"] += 1
        r = None
        try:
            r = session.get(API, params=params, timeout=30)
            last = r.status_code
            if r.status_code == 200:
                try:
                    return r.json()
                except ValueError:
                    last = "WAF(html)"       # بدنهٔ HTML = صفحهٔ چالش، نه JSON
            elif r.status_code in (429, 403):
                STATS["blocked"] += 1
        except Exception as e:
            last = type(e).__name__
            # v9.8.1 — قطع نشست/Timeout: چرخش فوری + پایش برقراری اینترنت.
            # برگشتنِ echo یعنی گوشی/مودم بالاست؛ ادامهٔ fetch با IP جدید.
            if rotate and attempt < MAX_BACKOFFS:
                print(f"    [net] نشست قطع شد ({last}) — تلاش برای چرخش IP سیم‌کارت…")
                if adb_rotate(long_cycle=long_cycle):
                    _wait_net_back(120.0)    # تا سقف ۱۲۰s برای برقراری اینترنت
                    continue
        if attempt == MAX_BACKOFFS:
            break
        wait = min(BACKOFF_CAP, BACKOFF_BASE * (2 ** attempt))
        try:
            ra = (r.headers.get("Retry-After") or "").strip() if r is not None else ""
        except Exception:
            ra = ""
        if ra.isdigit():
            wait = max(wait, min(float(ra), BACKOFF_CAP))
        print(f"    [{last}] backoff {wait:.0f}s (تلاش {attempt + 1}/{MAX_BACKOFFS + 1})")
        STATS["backoff"] += 1
        time.sleep(wait)
        if rotate and attempt >= 1:
            print("    → تلاش برای چرخش IP سیم‌کارت…")
            adb_rotate(long_cycle=long_cycle)

    # همهٔ تلاش‌ها تمام شد و هیچ JSON معتبری گرفته نشد.
    # باگ v1.0: تابع تا اینجا None برمی‌گرداند و فراخوان (fetch_symbol) روی
    # j.get("Total") با AttributeError می‌مرد — آن‌وقت st هرگز ذخیره نمی‌شد و
    # «ادامه از نقطهٔ توقف» عملاً کار نمی‌کرد. Blocked درستِ همین است:
    # صفحهٔ جاری در state می‌ماند و اجرای بعدی از همان‌جا شروع می‌کند.
    STATS["blocked"] += 1
    raise Blocked("همهٔ %d تلاش ناموفق (آخرین خطا: %s)" % (MAX_BACKOFFS + 1, last))

# ───────────────────────── Resume (ادامه از نقطهٔ توقف) ───────────────────────── #
def load_state():
    try:
        with io.open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(st):
    st["updated_at"] = datetime.now().isoformat(timespec="seconds")
    tmp = STATE_PATH + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE_PATH)


def letter_url(u):
    u = (u or "").strip()
    if not u:
        return ""
    return u if u.startswith("http") else "https://codal.ir" + (u if u.startswith("/") else "/" + u)


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ───────────────────────── دیتابیس ───────────────────────── #
def known_periods(conn, sym):
    """period_end های از‌پیش‌استخراج‌شده + tracing_no های ثبت‌شده.

    بی‌این، هر اجرا دوباره همان گزارش‌ها را scrape می‌کرد (هر scrape = ۱ تا ۷
    درخواست HTTP به codal.ir — گران‌ترین بخش کار).
    """
    fs_pe = {r[0] for r in conn.execute(
        "SELECT DISTINCT period_end FROM financial_statements WHERE symbol=?", (sym,))}
    ms_pe = {r[0] for r in conn.execute(
        "SELECT DISTINCT period_end FROM monthly_sales WHERE symbol=?", (sym,))}
    done = {r[0] for r in conn.execute(
        "SELECT tracing_no FROM financial_statements WHERE symbol=?", (sym,))}
    done |= {r[0] for r in conn.execute(
        "SELECT tracing_no FROM monthly_sales WHERE symbol=?", (sym,))}
    return fs_pe, ms_pe, done


def save_monthly(conn, L, vals, period_end):
    year, month = cf._parse_year_month(period_end)
    conn.execute(cf.MS_UPSERT, (
        int(L["TracingNo"]), (L.get("Symbol") or "").strip(),
        (L.get("Title") or "").strip(), period_end, year, month,
        vals.get("monthly_revenue"), vals.get("ytd_revenue"),
        vals.get("monthly_revenue_prev"), vals.get("ytd_revenue_prev"),
        letter_url(L.get("PdfUrl")), letter_url(L.get("ExcelUrl"))))
    return year, month


def save_annual(conn, L, vals, meta, unit):
    conn.execute("INSERT OR REPLACE INTO financial_statements VALUES ("
                 + ",".join("?" * (8 + len(cf.FS_KEYS) + 3)) + ")",
                 (int(L["TracingNo"]), (L.get("Symbol") or "").strip(),
                  (L.get("CompanyName") or "").strip(), (L.get("Title") or "").strip(),
                  "Financial Statements", meta.get("period"), meta.get("end"),
                  (L.get("PublishDateTime") or "").strip())
                 + tuple(vals.get(k) for k in cf.FS_KEYS)
                 + (unit, letter_url(L.get("Url")), now_str()))


# ─────────────────────── واکشی یک نماد ─────────────────────── #
def fetch_symbol(session, conn, sym, mode, rotate=False, long_cycle=False,
                 max_pages=6, st=None, resume=False):
    """نامه‌های یک نماد را از search API می‌گیرد و فقط دو نوع مجاز را استخراج می‌کند.

    resume=True → از صفحهٔ ثبت‌شده در state ادامه می‌دهد (نه از صفحهٔ ۱).
    در صورت Blocked، همان (symbol, page) در state می‌ماند تا اجرای بعدی از
    همان نقطه شروع کند.
    """
    want_cat = CAT_MONTHLY if mode == "monthly" else CAT_FS
    fs_pe, ms_pe, done = known_periods(conn, sym)
    page = int((st or {}).get("page", 1)) if resume else 1
    total, saved = None, 0
    while page <= max_pages:
        q = dict(cf.QUERY, Symbol=sym, Category=want_cat, LetterType="-1",
                 PageNumber=page, PageSize=PAGE_SIZE)
        try:
            j = api_get(session, q, rotate=rotate, long_cycle=long_cycle)
        except Blocked as e:
            if st is not None:
                st.update({"symbol": sym, "page": page, "mode": mode, "blocked": True})
                save_state(st)
            print(f"  ⛔ {sym}: {e}")
            print("     → وضعیت ذخیره شد؛ اجرای بعدی از همان صفحه ادامه می‌دهد.")
            raise
        total = j.get("Total", 0)
        letters = j.get("Letters") or []
        if not letters:
            break
        for L in letters:
            tn = L.get("TracingNo")
            if tn is None:
                continue
            STATS["letters"] += 1
            title = (L.get("Title") or "").strip()
            kind = notice_kind(title)
            if kind != mode:                       # ایزولاسیون: بدون درخواست شبکه رد
                STATS["rejected_title"] += 1
                continue
            if int(tn) in done:
                STATS["skipped_known"] += 1
                continue
            url = letter_url(L.get("Url"))
            if not url:
                continue
            STATS["in_scope"] += 1
            try:
                if kind == "monthly":
                    vals, pe = cf.scrape_monthly_report(session, url)
                    if not vals.get("monthly_revenue"):
                        continue
                    pe = pe or cf._period_from_title(title)
                    if pe and pe in ms_pe:
                        STATS["skipped_known"] += 1
                        continue
                    year, month = save_monthly(conn, L, vals, pe)
                    ms_pe.add(pe); done.add(int(tn))
                    STATS["saved_ms"] += 1; STATS["scraped"] += 1; saved += 1
                    ytd = vals.get("ytd_revenue") or 0
                    prev = vals.get("ytd_revenue_prev") or 0
                    gr = (ytd / prev - 1) * 100 if prev else None
                    ym = ("%s/%02d" % (year, month)) if (year and month) else "—"
                    print(f"    ✓ ماهانه {pe or '—'} ({ym})  تجمیعی={ytd:,.0f}  "
                          f"سال‌قبل={prev:,.0f}  "
                          f"رشد={('—' if gr is None else '%+.1f%%' % gr)}")
                else:
                    vals, meta, unit = cf.scrape_report(session, url)
                    if vals.get("revenue") is None:
                        continue
                    pe = (meta or {}).get("end")
                    if pe and pe in fs_pe:
                        STATS["skipped_known"] += 1
                        continue
                    save_annual(conn, L, vals, meta or {}, unit)
                    fs_pe.add(pe); done.add(int(tn))
                    STATS["saved_fs"] += 1; STATS["scraped"] += 1; saved += 1
                    rev = vals.get("revenue") or 0
                    gp, eps = vals.get("gross_profit"), vals.get("basic_eps")
                    gm = (gp / rev * 100) if (gp and rev) else None
                    print(f"    ✓ سالانه {pe}  درآمد={rev:,.0f}  "
                          f"ناخالص={('—' if gp is None else format(gp, ',.0f'))}  "
                          f"حاشیه={('—' if gm is None else '%.1f%%' % gm)}  "
                          f"EPS={('—' if eps is None else format(eps, ',.0f'))}")
                conn.commit()
            except Exception as e:
                print(f"    ✗ استخراج ناموفق {sym} tn={tn}: {type(e).__name__}: {e}")
            time.sleep(random.uniform(*POLITE_DELAY))
        page += 1
        if st is not None:
            st.update({"symbol": sym, "page": page, "mode": mode, "blocked": False})
            save_state(st)
        if total and (page - 1) * PAGE_SIZE >= total:
            break
    return saved


# ─── همگام‌سازی لوکال شاخص ۴ و ۵ (بدون هیچ درخواست شبکه) ─── #
def local_market_ctx(conn):
    """ارزش بازار روز + صنعت هر نماد از market_watch × instruments.

    fts_engine این دو را به‌صورت پارامتر می‌گیرد (شاخص ۴ = فروش ÷ ارزش بازار،
    شاخص ۵ = فیلتر صنعت) — پس برای تازه‌سازی‌شان هیچ درخواستی به کدال لازم
    نیست؛ فقط جداول TSETMC لوکال خوانده می‌شوند.
    """
    rows = conn.execute("""
        SELECT i.l_val18, i.sector_name, i.total_shares, m.p_closing
        FROM instruments i
        LEFT JOIN market_watch m ON m.ins_code = i.ins_code
        WHERE COALESCE(i.l_val18, '') <> ''""").fetchall()
    ctx, total_mcap = {}, 0.0
    for l18, sector, shares, price in rows:
        mcap = float(price or 0) * float(shares or 0)
        total_mcap += mcap
        k = fts_engine.norm_fa(l18)
        if k not in ctx:
            ctx[k] = (mcap, (sector or "").strip())
    return ctx, total_mcap


def load_fts_cfg():
    """آستانه‌های کاربر از fts_thresholds.json (از طریق app.load_fts_config)."""
    try:
        import app as _app
        return _app.load_fts_config()
    except Exception as e:
        print(f"  [cfg] بارگذاری آستانه‌ها ناموفق ({type(e).__name__}) → پیش‌فرض fts_engine")
        return None


# (برچسب، کلید detail، کلید passes — None یعنی شاخص ۵گانه نیست و فقط اطلاعیه)
INDICATORS = (
    ("۱ رشد فروش تجمیعی",   "growth",           "1_growth",        "growth_pct"),
    ("۲ روند EPS ۳ ساله",   "eps_trend",        "2_eps_trend",     "consecutive_years"),
    ("۳ حاشیه سود ناخالص",  "gross_margin",     "3_gross_margin",  "margin_pct"),
    ("۴ فروش ÷ ارزش بازار", "sales_to_mcap",    "4_sales_to_mcap", "sales_to_mcap"),
    ("۵ فیلتر صنعت",        "sector",           "5_industry",      "verdict"),
    ("   پتانسیل سود*",     "profit_potential", None,              "potential_pct"),
)


def verify(conn, symbols, ctx, total_mcap, cfg):
    """۵ شاخص را از fts_engine بازخوانی می‌کند — اثبات تازه بودن کش FTS.

    ساختار خروجی scan_symbol: passes (۵ بولین) + detail (دیکشنری جزئیات) +
    verdict + exclusion_reasons. هیچ‌کدام حدسی نیست؛ از fts_engine خوانده شد.
    * پتانسیل سود جزو ۵ شاخص نیست (شاخص ۵ = فیلتر صنعت) ولی در کارت بنیادی
      نمایش داده می‌شود، پس اینجا هم چاپ می‌شود.
    """
    print("\n" + "═" * 78)
    print("راستی‌آزمایی شاخص‌ها (fts_engine.scan_symbol روی دیتای تازه)")
    print("═" * 78)
    for sym in symbols:
        mcap, sector = ctx.get(fts_engine.norm_fa(sym), (0.0, ""))
        try:
            r = fts_engine.scan_symbol(conn, sym, mcap, total_mcap, sector, cfg=cfg)
        except Exception as e:
            print(f"  {sym}: خطا — {type(e).__name__}: {e}")
            continue
        det, passes = r.get("detail") or {}, r.get("passes") or {}
        print(f"\n  {sym}  score={r.get('score')}/5  verdict={r.get('verdict')}  "
              f"صنعت={sector or '—'}  ارزش‌بازار={mcap / 1e13:,.0f}h ریال")
        if r.get("excluded"):
            print("    ⛔ حذف خودکار: " + " | ".join(r.get("exclusion_reasons") or []))
        for label, key, pass_key, field in INDICATORS:
            v = det.get(key)
            if not isinstance(v, dict):
                print(f"    · {label:<22} —   (دیتای کافی نیست)")
                continue
            ok = v.get("pass") if pass_key is None else passes.get(pass_key)
            val = v.get(field)
            if isinstance(val, float):
                val = f"{val:,.1f}"
            extra = " (data_gap)" if v.get("data_gap") else ""
            print(f"    · {label:<22} {'✓' if ok else '✗'}  {field}={val}{extra}")


def pick_symbols(conn, n):
    """نمادهای منتخب تست: بیشترین تعداد گزارش ماهانه (داده‌دار و قابل‌سنجش)."""
    rows = conn.execute("""
        SELECT symbol, COUNT(*) c FROM monthly_sales
        GROUP BY symbol HAVING c >= 6 ORDER BY c DESC LIMIT ?""", (n,)).fetchall()
    return [r[0] for r in rows]


def main():
    ap = argparse.ArgumentParser(
        description="BorsTerminal — Codal FTS updater (۵ شاخص، ۲ نوع اطلاعیه)")
    ap.add_argument("--mode", choices=("monthly", "full", "local"), default="monthly",
                    help="monthly=گزارش فعالیت ماهانه | full=صورت مالی سالانه ۳ سال | "
                         "local=بدون شبکه، فقط ارزش بازار/صنعت")
    ap.add_argument("--symbols", default="", help="لیست نمادها با ویرگول (پیش‌فرض: --limit)")
    ap.add_argument("--limit", type=int, default=5, help="تعداد نماد در صورت ندادن --symbols")
    ap.add_argument("--max-pages", type=int, default=6, help="سقف صفحه برای هر نماد")
    ap.add_argument("--adb-rotate", action="store_true",
                    help="روی 429/WAF: چرخش تطبیقی IP با پایش پویا (سقف ۹۰s/متد)")
    ap.add_argument("--adb-long", action="store_true",
                    help="چرخهٔ بلند 80s+20s + تأیید واقعی تغییر IP (اپراتورهای پین‌IP)")
    ap.add_argument("--rotate-test", action="store_true",
                    help="فقط چرخش IP را اجرا کن و زمان کشف را گزارش بده (بدون واکشی)")
    ap.add_argument("--resume", action="store_true", help="ادامه از نقطهٔ توقفِ state")
    ap.add_argument("--verify", action="store_true", help="در پایان ۵ شاخص را چاپ کن")
    ap.add_argument("--db", default=DB_PATH)
    args = ap.parse_args()

    conn = sqlite3.connect(args.db, timeout=60)
    print("═" * 78)
    print("Codal FTS Updater v1.0 — مود: %s" % args.mode)
    print("═" * 78)

    if args.rotate_test:
        # چرخش را مستقل از کدال می‌سنجد: echo ها (api.ipify.org) میزبان کدال
        # نیستند، پس حتی وقتی search.codal.ir بلاک/خارج از دسترس است، خودِ
        # مکانیزم چرخش و زمان کشف قابل راستی‌آزمایی است.
        base = _public_ip()
        print("[rotate-test] Old IP = %s" % (base or "نامعلوم (شبکه پاسخ نداد)"))
        t0 = time.monotonic()
        ok = adb_rotate(long_cycle=args.adb_long)
        el = time.monotonic() - t0
        lr = _LAST_ROTATION
        print("[rotate-test] result=%s  total=%.1fs" % (ok, el))
        if lr:
            print("[rotate-test] new IP=%s  detected in %.1fs  method=%s  (%s)"
                  % (lr[0], lr[1], lr[2], lr[3]))
        print("[rotate-test] " + " | ".join(
            "%s=%s" % (k, v) for k, v in STATS.items()
            if v and str(k).startswith("rotate")))
        conn.close()
        return 0 if ok else 1

    ctx, total_mcap = local_market_ctx(conn)
    print(f"[local] ارزش بازار/صنعت از market_watch×instruments: {len(ctx)} نماد، "
          f"کل بازار {total_mcap / 1e13:.0f}h تومان (شاخص ۴ و ۵ — صفر درخواست شبکه)")

    syms = [s.strip() for s in args.symbols.split(",") if s.strip()]
    if not syms:
        syms = pick_symbols(conn, args.limit)
        print(f"[plan] نمادهای منتخب خودکار: {', '.join(syms)}")

    if args.mode == "local":
        verify(conn, syms, ctx, total_mcap, load_fts_cfg())
        conn.close()
        return 0

    mode = "monthly" if args.mode == "monthly" else "annual"
    st = load_state()
    if st.get("mode") != mode:
        st = {"mode": mode}
    session = cf.make_session()
    interrupted = False
    for sym in syms:
        label = "گزارش فعالیت ماهانه" if mode == "monthly" else "صورت مالی سالانه"
        print(f"\n▶ {sym}  ({label})")
        try:
            n = fetch_symbol(session, conn, sym, mode, rotate=args.adb_rotate,
                             long_cycle=args.adb_long, max_pages=args.max_pages,
                             st=st, resume=args.resume)
            print(f"  → {n} گزارش تازه ذخیره شد")
        except Blocked:
            interrupted = True
            break
        except KeyboardInterrupt:
            interrupted = True
            break
        st["page"] = 1                     # نماد بعدی از صفحهٔ ۱ شروع کند

    print("\n" + "─" * 78)
    print("آمار اجرا: " + " | ".join(f"{k}={v}" for k, v in STATS.items() if v))
    print("─" * 78)
    if interrupted:
        print("⚠ اجرا ناتمام ماند. وضعیت در dev/fts_update_state.json ذخیره است؛ "
              "با همان فرمان + --resume ادامه می‌یابد.")

    if args.verify or not interrupted:
        verify(conn, syms, ctx, total_mcap, load_fts_cfg())
    conn.close()
    return 1 if interrupted else 0


if __name__ == "__main__":
    sys.exit(main() or 0)