# -*- coding: utf-8 -*-
"""execution_panel.py — تبِ جداگانهٔ پنل AutoClicker در همان پنجره و پروفایلِ مرورگر.

بند ۱ و ۴ مأموریت: پس از ورودِ دستیِ مالک در پنجرهٔ اختصاصی EasyTrader، پنلِ
تنظیمات باید در یک *تبِ واقعیِ دیگر در همان پنجره و همان پروفایل* باز شود و به
همان نشست متصل باشد؛ نه لینک/راهنمایی، و نه تزریق فیلد به فرمِ کارگزاری.

ساختار:
  • پنل یک صفحۀ محلی است که خودِ بک‌اند BorsTerminal از `/static/autoclicker/panel.html`
    سرو می‌کند (همین فایل در بستۀ onedir کنار EXE است؛ در `static/` datas).
  • پنجرهٔ host (Playwright → CDP) یک تبِ تازه در *همان context* باز می‌کند و به
    آن نشانی می‌دهد: `…/panel.html#ticket=<یک‌بارمصرف>`. نشانه در fragment است؛
    در لاگِ درخواست/Referer نمی‌نشیند.
  • هر فراخوانِ کنترلیِ پنل سرآمدۀ `X-Bors-Panel` را می‌برد. نشانه در حافظه است،
    کوتاه‌عمر، به همان host bound، و با توقفِ host باطل می‌شود.

قفل‌ها:
  - هیچ مقدارِ sessionStorage/token/کوکی از این ماژول بیرون نمی‌رود؛ `session_presence`
    فقط «هست/نیست + میزبان + کلیدِ بی‌محتوا» برمی‌گرداند.
  - CDP فقط 127.0.0.1. هر نشانیِ دیگر مردود است.
  - تبِ پنل هرگز صفحهٔ کارگزاری نیست و DOM کارگزاری را دست نمی‌دهد.
"""
from __future__ import annotations

import os
import re
import sys
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse

PANEL_PATH = "/static/autoclicker/panel.html"
TICKET_HEADER = "X-Bors-Panel"
TICKET_TTL_S = 900.0
MAX_TICKETS = 16
ALLOWED_CDP_HOSTS = ("127.0.0.1", "localhost", "[::1]")
EASYTRADER_HOSTS = ("d.easytrader.ir", "easytrader.ir")
OIDC_PREFIX = "oidc.user:"
LOGIN_HOSTS = ("login.emofid.com",)


def _loopback(cdp_url: str) -> bool:
    p = urlparse(str(cdp_url or ""))
    return p.scheme == "http" and (p.hostname or "") in ALLOWED_CDP_HOSTS


@dataclass
class Ticket:
    value: str
    cdp_url: str
    host_pid: int
    created_mono: float
    expires_mono: float
    used: int = 0
    scopes: tuple[str, ...] = ("panel",)


class PanelTicketStore:
    """نشانه‌هایِ درِ حافظه؛ بی‌دیسک، بی‌لاگ، با باطل‌شدنِ نشستِ host."""

    def __init__(self, *, ttl_s: float = TICKET_TTL_S,
                 max_tickets: int = MAX_TICKETS,
                 clock: Any = time.monotonic) -> None:
        self.ttl_s = float(ttl_s)
        self.max_tickets = int(max_tickets)
        self._clock = clock
        self._items: dict[str, Ticket] = {}
        self._lock = threading.Lock()

    def mint(self, *, cdp_url: str, host_pid: int = 0) -> Ticket:
        if not _loopback(cdp_url):
            raise ValueError("CDP must be loopback")
        now = self._clock()
        with self._lock:
            self._prune(now)
            while len(self._items) >= self.max_tickets:
                oldest = sorted(self._items.values(), key=lambda t: t.created_mono)[0]
                self._items.pop(oldest.value, None)
            value = secrets.token_urlsafe(24)
            while value in self._items:
                value = secrets.token_urlsafe(24)
            tk = Ticket(value=value, cdp_url=str(cdp_url), host_pid=int(host_pid or 0),
                        created_mono=now, expires_mono=now + self.ttl_s)
            self._items[value] = tk
            return tk

    def verify(self, value: str, *, cdp_url: str = "") -> tuple[bool, str]:
        got = str(value or "")
        if not got:
            return False, "NO_TICKET"
        now = self._clock()
        with self._lock:
            tk = self._items.get(got)
            if tk is None:
                return False, "UNKNOWN_TICKET"
            if now >= tk.expires_mono:
                self._items.pop(got, None)
                return False, "EXPIRED_TICKET"
            if cdp_url and tk.cdp_url and tk.cdp_url != str(cdp_url):
                return False, "TICKET_BINDING_CHANGED"
            tk.used += 1
            return True, "OK"

    def revoke(self, value: str) -> bool:
        with self._lock:
            return self._items.pop(str(value or ""), None) is not None

    def revoke_for_host(self, cdp_url: str) -> int:
        with self._lock:
            dead = [k for k, t in self._items.items() if t.cdp_url == str(cdp_url)]
            for k in dead:
                self._items.pop(k, None)
            return len(dead)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._items)

    def _prune(self, now: float) -> None:
        dead = [k for k, t in self._items.items() if now >= t.expires_mono]
        for k in dead:
            self._items.pop(k, None)


def panel_url_for(base_url: str, ticket: str) -> str:
    """پنل + نشانه در fragment (بی‌نشاندنِ راز در لاگ/Referer)."""
    base = str(base_url or "").rstrip("/")
    if not base:
        raise ValueError("base url required")
    return "%s%s#ticket=%s" % (base, PANEL_PATH, str(ticket))


def _pages(browser: Any) -> list[Any]:
    out: list[Any] = []
    for ctx in list(getattr(browser, "contexts", []) or []):
        for pg in list(getattr(ctx, "pages", []) or []):
            out.append(pg)
    return out


def _first_context(browser: Any) -> Any:
    ctxs = list(getattr(browser, "contexts", []) or [])
    return ctxs[0] if ctxs else None


def _host_match(host: str, allowed: tuple[str, ...]) -> bool:
    h = (host or "").lower()
    return any(h == a or h.endswith("." + a) for a in allowed)


def list_tabs(cdp_url: str, *, timeout_s: float = 8.0,
              broker_hosts: tuple[str, ...] = EASYTRADER_HOSTS,
              panel_paths: tuple[str, ...] = (PANEL_PATH,)) -> dict[str, Any]:
    """فقط‌خواندنی: فهرستِ تب‌ها با میزبان و مسیر (بی‌کوکی/بی‌نشانیِ کامل)."""
    if not _loopback(cdp_url):
        return {"status": "error", "code": "CDP_NOT_LOOPBACK", "tabs": []}
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:                           # noqa: BLE001
        return {"status": "error", "code": "PLAYWRIGHT_MISSING",
                "detail": type(e).__name__, "tabs": []}
    out: list[dict[str, Any]] = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(cdp_url.rstrip("/"),
                                                   timeout=max(2.0, timeout_s) * 1000)
            for pg in _pages(browser):
                u = urlparse(str(getattr(pg, "url", "") or ""))
                out.append({"host": (u.hostname or ""), "path": (u.path or "/")[:120],
                            "is_panel": (u.path or "") in panel_paths,
                            "is_broker": _host_match(u.hostname or "", broker_hosts),
                            "is_login": _host_match(u.hostname or "", LOGIN_HOSTS)})
    except Exception as e:                           # noqa: BLE001
        return {"status": "error", "code": "TABS_UNREADABLE",
                "detail": type(e).__name__, "tabs": out}
    return {"status": "success", "tabs": out, "count": len(out)}


def open_panel_tab(cdp_url: str, panel_url: str, *, timeout_s: float = 20.0) -> dict[str, Any]:
    """در همان contextِ مالک یک تبِ تازه می‌سازد و به پنلِ محلی می‌برد."""
    if not _loopback(cdp_url):
        return {"status": "error", "code": "CDP_NOT_LOOPBACK"}
    target = urlparse(str(panel_url or ""))
    if target.scheme != "http" or (target.hostname or "") not in ALLOWED_CDP_HOSTS:
        return {"status": "error", "code": "PANEL_URL_NOT_LOOPBACK"}
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:                           # noqa: BLE001
        return {"status": "error", "code": "PLAYWRIGHT_MISSING",
                "detail": type(e).__name__}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(cdp_url.rstrip("/"),
                                                   timeout=max(2.0, timeout_s) * 1000)
            ctx = _first_context(browser)
            if ctx is None:
                return {"status": "error", "code": "NO_CONTEXT"}
            existing = [pg for pg in _pages(browser)
                        if urlparse(str(getattr(pg, "url", "") or "")).path == PANEL_PATH]
            if existing:
                # تبِ پنل از قبل باز است؛ دو پنل هم‌زمان دو کنترل‌کننده می‌سازد،
                # پس همان تب را می‌آوریم و دیگرى نمی‌سازیم.
                try:
                    existing[0].bring_to_front()
                except Exception:
                    pass
                return {"status": "success", "opened": False, "tabs": len(_pages(browser)),
                        "already_open": True}
            page = ctx.new_page()
            page.goto(str(panel_url), wait_until="domcontentloaded",
                      timeout=max(2.0, timeout_s) * 1000)
            return {"status": "success", "opened": True, "tabs": len(_pages(browser)),
                    "panel_path": PANEL_PATH}
    except Exception as e:                           # noqa: BLE001
        return {"status": "error", "code": "PANEL_TAB_FAILED",
                "detail": "%s" % type(e).__name__}


def close_panel_tab(cdp_url: str, *, timeout_s: float = 10.0) -> dict[str, Any]:
    if not _loopback(cdp_url):
        return {"status": "error", "code": "CDP_NOT_LOOPBACK"}
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:                           # noqa: BLE001
        return {"status": "error", "code": "PLAYWRIGHT_MISSING",
                "detail": type(e).__name__}
    closed = 0
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(cdp_url.rstrip("/"),
                                                   timeout=max(2.0, timeout_s) * 1000)
            for pg in _pages(browser):
                if urlparse(str(getattr(pg, "url", "") or "")).path == PANEL_PATH:
                    try:
                        pg.close()
                        closed += 1
                    except Exception:
                        pass
    except Exception as e:                           # noqa: BLE001
        return {"status": "error", "code": "PANEL_CLOSE_FAILED",
                "detail": type(e).__name__, "closed": closed}
    return {"status": "success", "closed": closed}


def session_presence(cdp_url: str, *, timeout_s: float = 8.0,
                     broker_hosts: tuple[str, ...] = EASYTRADER_HOSTS) -> dict[str, Any]:
    """شاهدِ قابلِ مشاهدهٔ «کاربر وارد شده است» — بی‌خواندنِ مقدارِ نشست.

    دو شاهدِ مستقل: کلیدِ `oidc.user:` در sessionStorage (مقدار هرگز خوانده
    نمی‌شود) و نبودِ فیلدِ رمزِ نمایان روی همان میزبان. نتیجه فقط bool/میزبان.
    """
    if not _loopback(cdp_url):
        return {"state": "UNKNOWN", "code": "CDP_NOT_LOOPBACK"}
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:                           # noqa: BLE001
        return {"state": "UNKNOWN", "code": "PLAYWRIGHT_MISSING",
                "detail": type(e).__name__}
    js_keys = "() => Object.keys(window.sessionStorage || {})"
    js_login = ("() => Array.from(document.querySelectorAll('input[type=password]'))"
                ".some(el => { try { const r = el.getBoundingClientRect();"
                " return r.width > 0 && r.height > 0; } catch (e) { return false; } })")
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(cdp_url.rstrip("/"),
                                                   timeout=max(2.0, timeout_s) * 1000)
            pages = _pages(browser)
            broker = [pg for pg in pages
                      if _host_match(urlparse(str(getattr(pg, "url", "") or "")).hostname
                                     or "", broker_hosts)]
            if not broker:
                return {"state": "NO_BROKER_PAGE", "code": "NO_BROKER_PAGE",
                        "hosts": sorted({urlparse(str(getattr(pg, "url", "") or "")).hostname
                                         or "" for pg in pages})[:6]}
            saw_key = False
            saw_password_field = False
            for pg in broker:
                try:
                    keys = pg.evaluate(js_keys) or []
                    saw_key = saw_key or any(str(k).startswith(OIDC_PREFIX) for k in keys)
                except Exception:
                    continue
                try:
                    saw_password_field = saw_password_field or bool(pg.evaluate(js_login))
                except Exception:
                    pass
            if saw_key and not saw_password_field:
                return {"state": "LOGGED_IN", "evidence": "oidc-key-present-and-no-login-form",
                        "broker_pages": len(broker)}
            if saw_key:
                return {"state": "PARTIAL", "evidence": "oidc-key-present-but-login-visible"}
            return {"state": "LOGIN_REQUIRED", "evidence": "no-oidc-key-on-broker-page",
                    "broker_pages": len(broker)}
    except Exception as e:                           # noqa: BLE001
        return {"state": "UNKNOWN", "code": "PROBE_FAILED", "detail": type(e).__name__}


def static_candidates() -> list[str]:
    """همان مسیری که app.py برایِ /static می‌شناسد + جایِ امنِ حالتِ توسعه."""
    import bors_config
    out: list[str] = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        out.append(os.path.join(str(sys._MEIPASS), "static"))
    out.append(os.path.join(str(bors_config.WORK_DIR), "static"))
    out.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static"))
    out.append(os.path.join(os.getcwd(), "static"))
    seen, uniq = set(), []
    for d in out:
        key = os.path.normcase(os.path.abspath(d))
        if key not in seen:
            seen.add(key)
            uniq.append(d)
    return uniq


def panel_file_path() -> str:
    """اولین نسخۀ موجودِ panel.html؛ نبودش یعنی پنل باز نمی‌شود، نه سروِ فایلِ دیگر."""
    rel = os.path.join("autoclicker", "panel.html")
    for d in static_candidates():
        cand = os.path.join(d, rel)
        if os.path.isfile(cand):
            return cand
    return os.path.join(static_candidates()[0], rel)


def panel_asset_present() -> tuple[bool, str]:
    p = panel_file_path()
    return (os.path.isfile(p), p)


def ticket_from_request(headers: Any) -> str:
    for key in (TICKET_HEADER, "x-bors-panel", "HTTP_X_BORS_PANEL"):
        try:
            got = headers.get(key) if hasattr(headers, "get") else None
        except Exception:
            got = None
        if got:
            return re.sub(r"[^A-Za-z0-9_\-]", "", str(got))[:64]
    return ""


__all__ = ["PANEL_PATH", "TICKET_HEADER", "Ticket", "PanelTicketStore",
           "panel_url_for", "open_panel_tab", "close_panel_tab", "list_tabs",
           "session_presence", "panel_file_path", "panel_asset_present",
           "ticket_from_request", "EASYTRADER_HOSTS", "LOGIN_HOSTS"]
