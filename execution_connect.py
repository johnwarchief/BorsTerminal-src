#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""execution_connect.py — نشستِ مرورگریِ «اتصال به EasyTrader» و داوریِ حالتِ آن.

چرا لایۀ جدا: `api/execution.py` وِ `execution_easytrader.py` *قراردادِ اجرا* را
می‌دانند (token درِ حافظه، probe، preflight، prepare، dispatch gate، reconcile).
چیزی که درِ مخزن وجود نداشت، مسیرِ «کاربر چگونه وارد می‌شود» بود: پنجرۀ
مرورگریِ مختصِ کاربر، و سپس تبدیلِ «آنچه کاربر دید» به یکِ حالتِ صریحِ نشست.

چهار قاعده‌ای که این فایل برایش نوشته شده و بی‌آن‌ها ارزشی ندارد:

  ۱) **هیچ نشانی ازِ حدس ساخته نمی‌شود.** دامنۀ ورود درِ این مخزن مشاهده نشده
     است (سنجش: `grep` رویِ کد فقط `WIRE_BASE_URL = api-mts.orbis.easytrader.ir`
     را می‌دهد — نشانیِ API، نه صفحۀ ورود). پس دامنۀ ورود ازِ
     `BORS_EXECUTION_CONNECT_HOSTS` جایِ پیش‌فرضِ *مشاهده‌شده* را می‌گیرد (سه
     مبدأِ راستی‌آزمایی‌شده: account.emofid.com، login.emofid.com، d.easytrader.ir)
     و `none` درِ پنجره را کلاً می‌بندد. میزبانِ API به‌تنهایی جایِ ورود نیست.
  ۲) **رمز/CAPTCHA/MFA را این برنامه نمی‌شکند.** پنجره فقط باز می‌شود؛ ورودِ
     واقعی باِ خودِ کاربر است. هیچ خواندنِ فرم، هیچ کلیکِ خودکار، هیچ
     دورزدنی نیست.
  ۳) **هیچ رازی نوشته نمی‌شود.** کوکی/توکن هرگز درِ DB، لاگ، پاسخ API یا
     فایلِ تنظیمات نمی‌نشیند. پروفایلِ مرورگر پوشۀ موقت است و سه راه پاک می‌شود:
     بستنِ پنجره، جایگزین‌شدنِ پروفایلِ مُرده، و پایانِ فرایند؛ پوشه‌هایِ بی‌صاحبِ
     کهنه هم درِ همان لحظه جارو می‌شوند.
  ۴) **HTMLِ صفحۀ ورود، «اتصال موفق» نیست.** حالت *فقط* از پرسیدنیِ واقعیِ
     آداپتر (`authenticate()`) می‌آید: ۴۰۱ ⇒ EXPIRED، احرازِ ناموفق (۴۰۳) ⇒
     DISCONNECTED، timeout/شبکه/پاسخِ بی‌قالب ⇒ UNKNOWN، پاکتِ معتبرِ API ⇒
     CONNECTED. بی‌ترافیکِ مجاز (کلیدهایِ زنده) حالت `UNKNOWN` + `blocked_reason`
     می‌ماند، نه `CONNECTED`.

کشتنِ پروسه فقط رویِ فرزندِ خودِ این ماژول، و فقط تا زمانی که `poll()` می‌گوید
زنده است؛ شمارهٔ PIDِ بازچرخانده‌شده نمی‌تواند مجوزِ کشتنِ غریبه بدهد. هر PID
دیگری دست‌نخورده می‌ماند.
"""
from __future__ import annotations

import atexit
import dataclasses
import os
import shutil
import subprocess
import tempfile
import threading
import time
from typing import Any, Mapping
from urllib.parse import urlparse

import execution_contract as EC
import execution_easytrader as ET

CONNECT_ENV = "BORS_EXECUTION_CONNECT_HOSTS"
BROWSER_ENV = "BORS_CONNECT_BROWSER"

#: پوشۀ موقتِ مرورگر نباید بیشترِ این عمر رویِ دیسک بماند (کوکیِ بی‌صاحب).
#: با فاصلۀ زیاد از عمرِ معمولِ یکِ پنجرۀ ورود انتخاب شده تا پنجرۀ بازِ کاربر
#: پاک نشود؛ اگر هنوز درِ استفاده باشد، ویندوز نگهش می‌دارد و پاک نمی‌شود.
STALE_PROFILE_S = 12 * 3600.0
PROFILE_PREFIX = "bors_broker_profile_"

#: تنها نشانیِای که درِ این مخزن *مشاهده* شده (سرِ `execution_easytrader.py`).
#: این دامنۀ API است؛ پرسشِ نشست رویِ آن مجاز است، ولی جایِ ورودِ کاربر **نیست**.
KNOWN_WIRE_HOST = urlparse(ET.WIRE_BASE_URL).hostname or ""

STATE_CONNECTED = "CONNECTED"
STATE_DISCONNECTED = "DISCONNECTED"
STATE_EXPIRED = "EXPIRED"
STATE_UNKNOWN = "UNKNOWN"

#: یکِ «متصل» تا کی می‌ارزد؟ بی‌این سقف، چیپِ سبزِ رابط می‌تواند ساعت‌ها بی‌هیچ
#: پاسخِ تازه‌ای سبز بماند (the only writer of `last_verify` is POST /connect/verify).
#: باِ BORS_EXECUTION_VERIFY_MAX_AGE_S تنظیم می‌شود؛ پیش‌فرض ۱۵ دقیقه.
VERIFY_MAX_AGE_S = float(os.environ.get("BORS_EXECUTION_VERIFY_MAX_AGE_S") or 900.0)


def verify_age_s(last: Mapping[str, Any] | None) -> float | None:
    """چند ثانیه ازِ آخرینِ پرسشِ واقعی می‌گذرد؟ بی‌زمان ⇒ None، نه صفر."""
    raw = str((last or {}).get("checked_at") or "").strip()
    if not raw:
        return None
    try:
        stamp = time.strptime(raw, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
    return max(0.0, time.time() - time.mktime(stamp))


def effective_verify(last: Mapping[str, Any] | None) -> dict[str, Any]:
    """نتیجە پرسش + قاعدۀ تازگی، یک‌جا و درِ همین لایه (نه درِ رابط).

    «متصل»ی که زمانش نیامده یا ازِ سقف گذشته است، «متصل» گزارش نمی‌شود؛ حالتِ
    اصلی درِ `verified_state` و علت درِ `reason` می‌ماند — چیزی پاک نمی‌شود،
    فقط بی‌اعتبار علامت می‌خورد.
    """
    out = dict(last or {})
    if not out:
        return out
    age = verify_age_s(out)
    out["age_s"] = None if age is None else round(age, 1)
    out["verify_max_age_s"] = VERIFY_MAX_AGE_S
    stale = age is None or age > VERIFY_MAX_AGE_S
    out["stale"] = bool(stale)
    if stale and out.get("state") == STATE_CONNECTED:
        out["verified_state"] = STATE_CONNECTED
        out["state"] = STATE_UNKNOWN
        out["reason"] = ("پرسشِ اتصال زمانش مشخص نیست یا ازِ "
                         f"{int(VERIFY_MAX_AGE_S // 60)} دقیقه گذشته است — "
                         "«بررسی اتصال» را دوباره بزنید")
    return out
STATES = (STATE_CONNECTED, STATE_DISCONNECTED, STATE_EXPIRED, STATE_UNKNOWN)

#: چرا پنجره باز نشده — رشته‌ای ثابت که UI و گارد رویِ آن می‌خوانند، نه بر اساسِ متن.
NO_LOGIN_HOST = "NO_LOGIN_HOST"


def allowed_hosts() -> tuple[str, ...]:
    """دامنه‌هایی که *پنجرۀ مرورگر/پرسیدنیِ لایۀ اتصال* رویِ آن‌ها مجاز است.

    دو فهرست، دو نقش: این یکی از `login_hosts()` می‌آید (محیط یا پیش‌فرضِ
    مشاهده‌شده). میزبانِ API اینجا **نیست** — دیدنِ میزبانِ API دلیل نیست که صفحۀ
    ورود آنجاست، و «پنجره‌ای که نشانیِ API باز می‌کند» همان اشتباهی است که لایه
    برایِ جلوگیری از آن نوشته شده. پرسشِ نشستیِ که `Authorization` حمل می‌کند هم
    این فهرست را نمی‌خواند؛ آن `wire_hosts()` در `execution_easytrader.py` است با
    محیطِ جدا (`BORS_EXECUTION_WIRE_HOSTS`)، پس گذاشتنِ دامنهٔ ورود درِ API را
    باز نمی‌کند و برعکس.
    """
    return tuple(dict.fromkeys(h for h in login_hosts() if h))


#: مبدأهای *مشاهده‌شده*. هر سه در نشستِ 2026-10-17 با درخواستِ فقط‌خواندنی
#: راستی‌آزمایی شدند (صفر POST، صفر سفارش، صفر رمز) و سه نقشِ جدا دارند، چون سه
#: میزبانِ جدا‌اند:
#:   ورود  `account.emofid.com` ⇒ 302 به `login.emofid.com`؛ و
#:         `login.emofid.com/.well-known/openid-configuration` ⇒ 200 با
#:         "issuer":"https://login.emofid.com" و <title>ورود - کارگزاری مفید</title>
#:   UI    `d.easytrader.ir` ⇒ 200 با <title>EasyTrader</title>؛ پیوندِ رسمی در
#:         `emofid.com/easytrader/` به همین نشانی می‌رود و باندلِ first-partyِ
#:         `d.orbis.easytrader.ir` خودش `window.location.href` را همین می‌دهد
#:   API   `api-mts.orbis.easytrader.ir` از `d.easytrader.ir/app-version.json`
#:         خودِ UI («apiPath») — پس این را «تنها نشانیِ دیدۀِ کدِ شخصِ ثالث»
#:         نیست، پیکربندیِ انتشاریافتهٔ خودِ کارگزاری است
#: هیچ wildcard در هیچ‌کدام. `BORS_EXECUTION_CONNECT_HOSTS` این فهرست را *جایگزین*
#: می‌کند (تصمیمِ صریحِ مالک)، نه گشاده‌تر؛ و میزبانِ API هرگز جایِ ورود نیست.
PROVEN_AUTH_HOSTS = ("account.emofid.com", "login.emofid.com")
PROVEN_UI_HOSTS = ("d.easytrader.ir",)
DEFAULT_LOGIN_HOSTS = PROVEN_AUTH_HOSTS + PROVEN_UI_HOSTS


def auth_hosts() -> tuple[str, ...]:
    """میزبان‌های *احراز هویت* — برایِ برچسبِ درست درِ رابط."""
    return PROVEN_AUTH_HOSTS


def ui_hosts() -> tuple[str, ...]:
    """میزبانِ رابطِ معاملاتی؛ ورود از همین‌جا هم ممکن است ولی احرازِ هویت آنجاست."""
    return PROVEN_UI_HOSTS


def login_hosts() -> tuple[str, ...]:
    """دامنه‌هایی که *ورودِ کاربر* رویِ آن‌ها مجاز است.

    این فهرست عمداً ازِ `allowed_hosts()` جداست: دیدنِ یکِ میزبانِ API دلیل
    نمی‌شود که صفحۀ ورود همان‌جا باشد. بی‌`BORS_EXECUTION_CONNECT_HOSTS` این
    خالی است ⇒ پنجره باز نمی‌شود.
    """
    raw = (os.environ.get(CONNECT_ENV) or "").strip()
    # درِ بستنِ صریح: «هیچ میزبانی» با «بی‌تنظیم» یکی نیست. اگر مالک بخواهد
    # پنجرۀ مرورگر را کلاً ببندد، `none` درست است؛ بی‌این، پیش‌فرضِ مشاهده‌شده
    # فعال می‌ماند و راهِ بستن فقط پاک‌کردنِ محیط بود.
    if raw.lower() in ("none", "off", "disable", "0"):
        return ()
    got = tuple(h.strip().lower() for h in raw.split(",") if h.strip())
    return got or DEFAULT_LOGIN_HOSTS


def validate_url(url: str) -> tuple[bool, str]:
    """https + میزبانِ درِ فهرستِ مجاز + بندرِ ۴۴۳. بقیه رد، بی‌درخواست.

    دو تله که با «فقط hostname را ببین» ازِ درِ می‌گذرند: «بک‌اسلش» درِ نشانی (مرورگر
    آن را پایانِ Authority می‌داند، urlparseِ پایتون نه) و userinfo به شکلِ
    «اول میزبانِ مخرب، سپس جداکننده، سپس میزبانِ مجاز». سنجشِ نهایی این است که
    چیزی که درِ نشانی بود دقیقاً یکی باشد.
    """
    u = (url or "").strip()
    if not u:
        return False, "نشانی داده نشد"
    try:
        p = urlparse(u)
        port = p.port                       # ممکن است ValueError بدهد
    except ValueError as e:
        return False, "نشانیِ تجزیه‌ناپذیر: %s" % type(e).__name__
    if "\\" in u:
        return False, "«\\» درِ نشانی مجاز نیست (مرورگر و تجزیه‌گر یکی نمی‌خوانندش)"
    if p.scheme != "https":
        return False, "فقط https مجاز است (طرح: %r)" % (p.scheme or "-")
    host = (p.hostname or "").lower()
    if not host:
        return False, "میزبانِ نشانی خالی است"
    if host != host.strip("."):
        return False, "میزبانِ نقطه‌دارِ انتهایی پذیرفته نمی‌شود"
    expect = host + (":%d" % port if port else "")
    if p.netloc.lower() != expect:
        return False, "ساختارِ نشانی با میزبانِ ساده‌شده نمی‌خواند: %r" % (p.netloc[:60],)
    if port not in (None, 443):
        return False, "فقط بندرِ ۴۴۳ مجاز است: %r" % (port,)
    if host not in allowed_hosts():
        return False, "میزبان درِ فهرستِ مجاز نیست: %s" % host
    return True, ""


# ── پنجرۀ مرورگریِ کاربر ─────────────────────────────────────────────────────
@dataclasses.dataclass
class BrowserHandle:
    proc: Any
    profile_dir: str
    url: str
    opened_at: float

    @property
    def pid(self) -> int:
        return int(getattr(self.proc, "pid", 0) or 0)

    def alive(self) -> bool:
        """فقط دربارهٔ فرزندِ خودِ ما. PIDِ بازچرخانده‌شده اینجا سبز نمی‌شود،
        چون تا نگه‌داشتنِ این شیء،_handle_ِ فرایندِ ما بسته نمی‌شود."""
        try:
            return self.proc.poll() is None
        except Exception:
            return False


def _browser_binary() -> tuple[str | None, str]:
    """مرورگرِ کاربر، باِ ترجیحِ همان چیزی که درِ این ماشین هست."""
    env = (os.environ.get(BROWSER_ENV) or "").strip()
    cands = ([env] if env else []) + [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for c in cands:
        if c and os.path.isfile(c):
            return c, ("env" if c == env else "known-path")
    return None, "no-browser-binary"


def _remove_profile(path: str) -> bool:
    """پوشۀ موقت را پاک کن؛ True یعنی واقعاً ازِ دیسک رفته است."""
    if not path:
        return True
    shutil.rmtree(path, ignore_errors=True)
    return not os.path.isdir(path)


def _sweep_stale_profiles() -> int:
    """پوشه‌هایِ بی‌صاحبِ کهنهٔ خودِ این ماژول (پسِ مرگ/بازِ‌راه‌اندازیِ بک‌اند)."""
    root = tempfile.gettempdir()
    now = time.time()
    n = 0
    try:
        names = os.listdir(root)
    except OSError:
        return 0
    for name in names:
        if not name.startswith(PROFILE_PREFIX):
            continue
        full = os.path.join(root, name)
        try:
            if now - os.path.getmtime(full) < STALE_PROFILE_S:
                continue
            if _SESSION.get("browser") is not None and \
                    os.path.abspath(str(getattr(_SESSION["browser"], "profile_dir", ""))) == \
                    os.path.abspath(full):
                continue                      # پنجرۀ بازِ خودِ ما
            if _remove_profile(full):
                n += 1
        except OSError:
            continue
    return n


_SESSION: dict[str, Any] = {"browser": None}
_LOCK = threading.RLock()


def open_login_window(url: str) -> tuple[BrowserHandle | None, str]:
    """یکِ پنجرۀ جدا باِ پروفایلِ موقتِ ایزوله. ورود باِ خودِ کاربر است."""
    ok, why = validate_url(url)
    if not ok:
        return None, why
    hosts = login_hosts()
    host = (urlparse(url).hostname or "").lower()
    if not hosts:
        return None, "%s: هیچ دامنه‌ای برایِ ورودِ کاربر تأیید نشده (%s)" % (
            NO_LOGIN_HOST, CONNECT_ENV)
    if host not in hosts:
        return None, "این میزبان برایِ ورودِ کاربر ثبت نشده: %s" % host
    exe, _src = _browser_binary()
    if not exe:
        return None, "مرورگری برایِ بازِ کردن پیدا نشد (BORS_CONNECT_BROWSER را بگذارید)"
    with _LOCK:
        prev = _SESSION.get("browser")
        if isinstance(prev, BrowserHandle):
            if prev.alive():
                return prev, "already-open"
            _remove_profile(prev.profile_dir)   # پروفایلِ مُرده نباید بماند
        _sweep_stale_profiles()
        profile = tempfile.mkdtemp(prefix=PROFILE_PREFIX)
        args = [exe, "--user-data-dir=%s" % profile, "--no-first-run",
                "--no-default-browser-check", "--new-window", url]
        try:
            proc = subprocess.Popen(args, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
        except OSError as e:
            _remove_profile(profile)
            return None, "بازِ نشد: %s" % type(e).__name__
        h = BrowserHandle(proc=proc, profile_dir=profile, url=url, opened_at=time.time())
        _SESSION["browser"] = h
        return h, ""


def close_login_window() -> tuple[bool, str]:
    """فرزندِ خودِمان را می‌بندیم و پروفایلش را پاک می‌کنیم؛ ادعا نه، سنجش."""
    with _LOCK:
        h = _SESSION.get("browser")
        _SESSION["browser"] = None
        if not isinstance(h, BrowserHandle):
            return True, "nothing-open"
        if h.alive():
            try:
                subprocess.run(["taskkill", "/PID", str(h.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=15)
            except Exception:
                pass
            try:
                h.proc.wait(timeout=10)
            except Exception:
                pass
        return True, ("closed" if _remove_profile(h.profile_dir)
                      else "profile-still-on-disk")


def browser_state() -> dict[str, Any]:
    """وضعیتِ پنجره — هیچ‌گاه نشانیِ پوشۀ موقت را بیرون نمی‌فرستد."""
    with _LOCK:
        h = _SESSION.get("browser")
    if not isinstance(h, BrowserHandle):
        return {"open": False, "pid": None, "url": None, "profile_kept": False}
    return {"open": h.alive(), "pid": h.pid, "url": h.url,
            "profile_kept": os.path.isdir(h.profile_dir),
            "opened_seconds_ago": round(time.time() - h.opened_at)}


def _atexit_cleanup() -> None:
    """پایانِ فرایند: پنجره را نمی‌کُشیم (کاربر شاید درِ میانهٔ ورود است)، ولی
    پروفایلِ متعلقِ به خودِمان را ازِ دیسک برمی‌داریم اگر فرایندش رفته باشد."""
    try:
        with _LOCK:
            h = _SESSION.get("browser")
            if isinstance(h, BrowserHandle) and not h.alive():
                _remove_profile(h.profile_dir)
                _SESSION["browser"] = None
    except Exception:
        pass


atexit.register(_atexit_cleanup)


# ── داوریِ حالتِ نشست ────────────────────────────────────────────────────────
def _from_error_code(code: Any) -> str | None:
    """کدِ خطایِ قرارداد ← حالتِ نشست. نام‌هایِ مرده اینجا نرفته‌اند: هر شاخه
    باید کدی را ببیند که `execution_contract.ErrorCode` واقعاً می‌دهد."""
    v = getattr(code, "value", code)
    s = str(v or "").upper()
    if s == EC.ErrorCode.SESSION_EXPIRED.value:
        return STATE_EXPIRED                      # ۴۰۱: نشست باطل شد
    if s == EC.ErrorCode.AUTH_FAILED.value:
        # ۴۰۳: نشانی هست ولی اجازه‌ای نیست — «منقضی» ادعا نمی‌شود، «متصل» هم نه.
        return STATE_DISCONNECTED
    if s in (EC.ErrorCode.TIMEOUT.value, EC.ErrorCode.NETWORK_ERROR.value,
             EC.ErrorCode.UNKNOWN_RESULT.value, EC.ErrorCode.RATE_LIMITED.value):
        return STATE_UNKNOWN
    return None


def verify(adapter: Any) -> dict[str, Any]:
    """حالت را ازِ پرسیدنیِ واقعی می‌گیرد — نه ازِ حضورِ یکِ رشته، نه ازِ HTML."""
    checked_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    live = bool(getattr(adapter, "live", False))
    traffic_live = bool(getattr(adapter, "live", False)
                        or getattr(getattr(adapter, "transport", None), "is_live", False))
    has_token = bool(adapter.has_token()) if hasattr(adapter, "has_token") else False
    out: dict[str, Any] = {"state": STATE_UNKNOWN, "reason": "", "blocked_reason": "",
                           "checked_at": checked_at, "live": live,
                           "token_present": has_token,
                           "adapter": type(adapter).__name__}
    if not traffic_live:
        out["blocked_reason"] = ("ترافیکِ زنده خاموش است (BORS_EXECUTION_LIVE=1 لازم "
                                 "است) — بی‌پرسش ازِ کارگزاری هیچ حالتی تأیید نمی‌شود")
        out["reason"] = "ناشناخته؛ پرسش انجام نشد"
        return out
    if not has_token:
        out["state"] = STATE_DISCONNECTED
        out["reason"] = "نشستی درِ حافظه نیست — اول درِ پنجرۀ مرورگر وارد شوید"
        return out
    try:
        st = adapter.authenticate()
    except EC.BrokerError as e:
        out["state"] = _from_error_code(getattr(e, "code", None)) or STATE_UNKNOWN
        out["reason"] = str(EC.redact(getattr(e, "detail", None) or str(e)))[:160]
        return out
    except Exception as e:                       # هیچ خطایی «متصل» تفسیر نمی‌شود
        out["state"] = STATE_UNKNOWN
        out["reason"] = "پرسش شکست خورد: %s" % type(e).__name__
        return out
    raw = getattr(st, "state", None)
    mapped = {EC.SessionState.CONNECTED: STATE_CONNECTED,
              EC.SessionState.EXPIRED: STATE_EXPIRED,
              EC.SessionState.DISCONNECTED: STATE_DISCONNECTED,
              # دو حالتِ اضافیِ قرارداد: «رمز/نشانی رد شد» نشستِ باز نیست، و
              # «خطایِ عمومی» را نمی‌شود متصل خواند.
              EC.SessionState.AUTH_FAILED: STATE_DISCONNECTED,
              EC.SessionState.ERROR: STATE_UNKNOWN}.get(raw)
    out["state"] = mapped or STATE_UNKNOWN
    if mapped is None:
        out["reason"] = "آداپتور حالتِ ناشناخته‌ای داد (%s)" % getattr(raw, "value", raw)
    else:
        out["reason"] = "از پرسشِ صریحِ کارگزاری"
    proof = getattr(adapter, "session_proof", None) or {}
    if proof:
        # «متصل» باید بگوید کدام مسیر ثابتش کرد و آن مسیر چه‌قدر شاهد است؛
        # بی‌این، یکِ پاسخِ ۲xx ازِ مسیرِ حدسی با ۲xx ازِ مسیرِ دیده‌شده یکی می‌شود.
        out["proof"] = {"path": str(proof.get("path") or ""),
                        "status": proof.get("status"),
                        "kind": str(proof.get("kind") or ""),
                        "hypothesis": bool(proof.get("hypothesis")),
                        "note": str(proof.get("note") or "")[:160]}
    out["read_only"] = bool(getattr(adapter, "read_only_mode", False))
    return out


def status_dict(adapter: Any, last: Mapping[str, Any] | None) -> dict[str, Any]:
    hosts = list(login_hosts())
    return {"status": "success",
            "states_supported": list(STATES),
            "browser": browser_state(),
            "allowed_hosts": list(allowed_hosts()),
            "login_hosts_configured": hosts,
            # سه نقش، سه فهرست: چه‌کسی نباید با چه‌کسی اشتباه شود.
            "host_roles": {"auth": list(auth_hosts()), "ui": list(ui_hosts()),
                           "api": list(ET.wire_hosts()),
                           "evidence": ("هر سه مبدأ با درخواستِ فقط‌خواندنی در "
                                        "2026-10-17 دیده شده‌اند؛ سندِ رسمیِ API "
                                        "(swagger/openapi) منتشر نشده — ۴۰۳ — پس "
                                        "سیمِ سفارش همچنان فرضیه است")},
            "login_host_blocked_reason": ("" if hosts else
                                          NO_LOGIN_HOST + " — هیچ دامنه‌ای برایِ "
                                          "ورودِ کاربر تأیید نشده؛ "
                                          "BORS_EXECUTION_CONNECT_HOSTS را بگذارید"),
            "last_verify": effective_verify(last),
            # ترافیکِ فقط‌خواندنی با «ارسالِ سفارش آزاد» یکی نیست؛ UI باید بداند
            # کدام حالت روشن است، نه اینکه از رویِ رنگِ دکمه حدس بزند.
            # «فقط‌خواندنی» به *ترانسپورت* نگاه می‌کند نه به نشست: سنجشِ زندهٔ
            # 2026-10-18 نشان داد گره‌زدنش به `live` (که توکن می‌خواهد) همان
            # تناقض را می‌سازد — `/status` می‌گوید ترافیک مجاز و اینجا «مسدود».
            "traffic_mode": ("writes" if bool(getattr(adapter, "writes_allowed", False))
                              else "read_only"
                              if bool(getattr(getattr(adapter, "transport", None),
                                              "is_live", False))
                              else "blocked"),
            "session_proven": bool(getattr(adapter, "session_proven", lambda: False)()),
            "secrets_stored": False,
            "detail": ("رمز/CAPTCHA/MFA باِ خودِ کاربر است؛ این لایه فقط پنجره را "
                       "باز می‌کند و حالت را از پرسشِ واقعی می‌خواند")}
