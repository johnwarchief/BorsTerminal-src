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
     `BORS_EXECUTION_CONNECT_HOSTS` خوانده می‌شود؛ بی‌آن، حالت `BLOCKED` با
     علتِ روشن اعلام می‌شود و هیچ مرورگری باز نمی‌شود.
  ۲) **رمز/CAPTCHA/MFA را این برنامه نمی‌شکند.** پنجره فقط باز می‌شود؛ ورودِ
     واقعی باِ خودِ کاربر است. هیچ خواندنِ فرم، هیچ کلیکِ خودکار، هیچ
     دورزدنی نیست.
  ۳) **هیچ رازی نوشته نمی‌شود.** پروفایلِ مرورگر درِ یکِ پوشۀ موقت است و هنگام
     بستن پاک می‌شود؛ کوکی/توکن هرگز درِ DB، لاگ، پاسخ API یا فایلِ تنظیمات
     نمی‌نشیند. نشانیِ نشست همان مسیرِ موجودِ درِ حافظه می‌رود.
  ۴) **HTMLِ صفحۀ ورود، «اتصال موفق» نیست.** حالت *فقط* از پرسیدنیِ واقعیِ
     آداپتر (`authenticate()`) می‌آید: ۴۰۱ ⇒ EXPIRED، ۴۰۳ ⇒ DISCONNECTED،
     timeout/شبکه ⇒ UNKNOWN، پاسخِ معنادار ⇒ CONNECTED. بی‌ترافیکِ مجاز
     (کلیدهایِ زنده) حالت `UNKNOWN` + `blocked_reason` می‌ماند، نه `CONNECTED`.

کشتنِ پروسه فقط رویِ PIDی که *خودِ این ماژول* بالا آورده است؛ هر PID دیگری
دست‌نخورده می‌ماند.
"""
from __future__ import annotations

import dataclasses
import os
import shutil
import subprocess
import tempfile
import time
from typing import Any, Mapping
from urllib.parse import urlparse

import execution_contract as EC
import execution_easytrader as ET

CONNECT_ENV = "BORS_EXECUTION_CONNECT_HOSTS"
BROWSER_ENV = "BORS_CONNECT_BROWSER"

#: تنها نشانی‌ای که درِ این مخزن *مشاهده* شده (سرِ `execution_easytrader.py`).
#: این دامنۀ API است؛ برایِ بازِ کردنِ پنجره هم مجاز است، ولی جایِ ورودِ کاربر
#: نیست و ادعایی بابتش ساخته نمی‌شود.
KNOWN_WIRE_HOST = urlparse(ET.WIRE_BASE_URL).hostname or ""

STATE_CONNECTED = "CONNECTED"
STATE_DISCONNECTED = "DISCONNECTED"
STATE_EXPIRED = "EXPIRED"
STATE_UNKNOWN = "UNKNOWN"
STATES = (STATE_CONNECTED, STATE_DISCONNECTED, STATE_EXPIRED, STATE_UNKNOWN)


def allowed_hosts() -> tuple[str, ...]:
    """دامنه‌هایِ تأییدشده. پیش‌فرضِ امن: فقطِ همان یکِ میزبانِ دیدہ‌شدہ."""
    raw = (os.environ.get(CONNECT_ENV) or "").strip()
    extra = tuple(h.strip().lower() for h in raw.split(",") if h.strip())
    out = list(dict.fromkeys(list(extra) + ([KNOWN_WIRE_HOST] if KNOWN_WIRE_HOST else [])))
    return tuple(out)


def login_hosts() -> tuple[str, ...]:
    """دامنه‌هایی که *ورودِ کاربر* رویِ آن‌ها مجاز است.

    این فهرست عمداً ازِ `allowed_hosts()` جداست: دیدنِ یکِ میزبانِ API دلیل
    نمی‌شود که صفحۀ ورود همان‌جا باشد. بی‌`BORS_EXECUTION_CONNECT_HOSTS` این
    خالی است ⇒ `BLOCKED`.
    """
    raw = (os.environ.get(CONNECT_ENV) or "").strip()
    return tuple(h.strip().lower() for h in raw.split(",") if h.strip())


def validate_url(url: str) -> tuple[bool, str]:
    """https + میزبانِ درِ فهرستِ مجاز. بقیه رد، بی‌درخواست."""
    u = (url or "").strip()
    if not u:
        return False, "نشانی داده نشد"
    try:
        p = urlparse(u)
    except ValueError as e:
        return False, "نشانیِ تجزیه‌ناپذیر: %s" % type(e).__name__
    if p.scheme != "https":
        return False, "فقط https مجاز است (طرح: %r)" % (p.scheme or "-")
    host = (p.hostname or "").lower()
    if not host:
        return False, "میزبانِ نشانی خالی است"
    if host not in allowed_hosts():
        return False, "میزبان درِ فهرستِ مجاز نیست: %s" % host
    return True, ""


# ── پنجرۀ مرورگریِ کاربر ─────────────────────────────────────────────────────
@dataclasses.dataclass
class BrowserHandle:
    pid: int
    profile_dir: str
    url: str
    opened_at: float

    def alive(self) -> bool:
        if self.pid <= 0:
            return False
        try:
            import ctypes
            STILL_ACTIVE = 259
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, self.pid)  # QUERY_LIMITED
            if not h:
                return False
            code = ctypes.c_ulong()
            ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
            ctypes.windll.kernel32.CloseHandle(h)
            return bool(ok) and code.value == STILL_ACTIVE
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


_SESSION: dict[str, Any] = {"browser": None}


def open_login_window(url: str) -> tuple[BrowserHandle | None, str]:
    """یکِ پنجرۀ جدا باِ پروفایلِ موقتِ ایزوله. ورود باِ خودِ کاربر است."""
    ok, why = validate_url(url)
    if not ok:
        return None, why
    hosts = login_hosts()
    host = (urlparse(url).hostname or "").lower()
    if hosts and host not in hosts:
        return None, "این میزبان برایِ ورودِ کاربر ثبت نشده: %s" % host
    exe, _src = _browser_binary()
    if not exe:
        return None, "مرورگری برایِ بازِ کردن پیدا نشد (BORS_CONNECT_BROWSER را بگذارید)"
    prev = _SESSION.get("browser")
    if isinstance(prev, BrowserHandle) and prev.alive():
        return prev, "already-open"
    profile = tempfile.mkdtemp(prefix="bors_broker_profile_")
    args = [exe, "--user-data-dir=%s" % profile, "--no-first-run",
            "--no-default-browser-check", "--new-window", url]
    try:
        proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        shutil.rmtree(profile, ignore_errors=True)
        return None, "بازِ نشد: %s" % type(e).__name__
    h = BrowserHandle(pid=int(proc.pid), profile_dir=profile, url=url, opened_at=time.time())
    _SESSION["browser"] = h
    return h, ""


def close_login_window() -> tuple[bool, str]:
    """فقطِ PIDی که خودمان بالا آوردیم کشته می‌شود؛ پروفایلِ موقت پاک می‌شود."""
    h = _SESSION.get("browser")
    _SESSION["browser"] = None
    if not isinstance(h, BrowserHandle):
        return True, "nothing-open"
    try:
        if h.alive():
            subprocess.run(["taskkill", "/PID", str(h.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=15)
    except Exception:
        pass
    shutil.rmtree(h.profile_dir, ignore_errors=True)
    return True, "closed"


def browser_state() -> dict[str, Any]:
    h = _SESSION.get("browser")
    if not isinstance(h, BrowserHandle):
        return {"open": False, "pid": None, "url": None, "profile_kept": False}
    return {"open": h.alive(), "pid": h.pid, "url": h.url,
            "profile_kept": False,          # پاک می‌شود؛ ادعایِ صادق
            "opened_seconds_ago": round(time.time() - h.opened_at)}


# ── داوریِ حالتِ نشست ────────────────────────────────────────────────────────
def _from_error_code(code: Any) -> str | None:
    v = getattr(code, "value", code)
    s = str(v or "").upper()
    if "SESSION_EXPIRED" in s or "TOKEN" in s or "AUTH_FAILED" in s:
        # احرازِ ناموفق = نشستِ درِ دست نیست؛ نه «متصل»، نه «خطایِ عمومی»
        return STATE_EXPIRED
    if "UNAUTHORIZED" in s or "FORBIDDEN" in s or "PERMISSION" in s:
        return STATE_DISCONNECTED
    if "TIMEOUT" in s or "NETWORK" in s or "UNKNOWN" in s:
        return STATE_UNKNOWN
    return None


def verify(adapter: Any) -> dict[str, Any]:
    """حالت را ازِ پرسیدنیِ واقعی می‌گیرد — نه ازِ حضورِ یکِ رشته، نه ازِ HTML."""
    checked_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    live = bool(getattr(adapter, "live", False))
    has_token = bool(adapter.has_token()) if hasattr(adapter, "has_token") else False
    out: dict[str, Any] = {"state": STATE_UNKNOWN, "reason": "", "blocked_reason": "",
                           "checked_at": checked_at, "live": live,
                           "token_present": has_token,
                           "adapter": type(adapter).__name__}
    if not live:
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
        out["reason"] = str(getattr(e, "detail", None) or e)[:160]
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
              EC.SessionState.AUTH_FAILED: STATE_EXPIRED,
              EC.SessionState.ERROR: STATE_UNKNOWN}.get(raw)
    out["state"] = mapped or STATE_UNKNOWN
    if mapped is None:
        out["reason"] = "آداپتور حالتِ ناشناخته‌ای داد (%s)" % getattr(raw, "value", raw)
    else:
        out["reason"] = "از پرسشِ صریحِ کارگزاری"
    return out


def status_dict(adapter: Any, last: Mapping[str, Any] | None) -> dict[str, Any]:
    hosts = list(login_hosts())
    return {"status": "success",
            "states_supported": list(STATES),
            "browser": browser_state(),
            "allowed_hosts": list(allowed_hosts()),
            "login_hosts_configured": hosts,
            "login_host_blocked_reason": ("" if hosts else
                                          "هیچ دامنه‌ای برایِ ورودِ کاربر تأیید نشده — "
                                          "BORS_EXECUTION_CONNECT_HOSTS را بگذارید"),
            "last_verify": dict(last or {}),
            "secrets_stored": False,
            "detail": ("رمز/CAPTCHA/MFA باِ خودِ کاربر است؛ این لایه فقط پنجره را "
                       "باز می‌کند و حالت را از پرسشِ واقعی می‌خواند")}
