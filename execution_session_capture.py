# -*- coding: utf-8 -*-
"""execution_session_capture.py — نشستِ OIDC را از مرورگرِ مدیریت‌شده به حافظه می‌آورد.

این ماژول فقط با اقدامِ صریحِ مالک اجرا می‌شود. مالک خودش در پنجرهٔ host وارد
می‌شود؛ اینجا هیچ رمز/CAPTCHA/MFA پرسیده یا دور زده نمی‌شود. access_token از
sessionStorage همان صفحه‌ای خوانده می‌شود که مالک وارد شده و **فقط** به
آداپتورِ درونِ حافظه داده می‌شود:

  • هیچ token/cookieای روی دیسک، در log یا در پاسخِ HTTP نوشته نمی‌شود.
  • پاسخ فقط متادیتا برمی‌گرداند (expiery/scope/host)؛ مقدارِ توکن هرگز.
  • صفحهٔ login.emofid.com مجاز نیست؛ باید صفحهٔ واردشدهٔ d.easytrader.ir باشد.
  • خطاها متنِ ثابت دارند و مقدارِ خوانده‌شده را در پیام نمی‌گذارند.

CDP از Playwright و همان hostِ محلیِ برنامه استفاده می‌کند؛ هیچ مرورگرِ تازه‌ای
باز نمی‌شود و پروفایل/نشستِ مالک دست‌کاری نمی‌شود.
"""
from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import urlparse

OIDC_PREFIX = "oidc.user:"
ALLOWED_HOSTS = ("d.easytrader.ir", "easytrader.ir")
REQUIRED_SCOPES = ("easy2_api", "mts_api")
MAX_SESSION_JSON = 64 * 1024


class CaptureError(Exception):
    """خطایِ قابلِ نمایش؛ `detail` هرگز مقدارِ نشست را در خود ندارد."""

    def __init__(self, code: str, detail: str = ""):
        self.code = str(code)
        self.detail = str(detail)[:200]
        super().__init__(self.detail or self.code)


def _allowed_host(host: str) -> bool:
    h = (host or "").lower()
    return any(h == a or h.endswith("." + a) for a in ALLOWED_HOSTS)


def parse_oidc_user(raw: str, now: float | None = None) -> tuple[str, dict[str, Any]]:
    """(token, metadata) — token فقط برایِ set_token؛ در پاسخ برنمی‌گردد."""
    if not isinstance(raw, str) or not raw.strip():
        raise CaptureError("NO_SESSION", "نشستِ OIDC در صفحه پیدا نشد")
    if len(raw) > MAX_SESSION_JSON:
        raise CaptureError("SESSION_TOO_LARGE", "ساختارِ نشست بزرگ‌تر از حدِ انتظار است")
    try:
        obj = json.loads(raw)
    except Exception:                            # noqa: BLE001
        raise CaptureError("BAD_SESSION_JSON", "ساختارِ نشست خوانا نبود")
    if not isinstance(obj, dict):
        raise CaptureError("BAD_SESSION_JSON", "ساختارِ نشست خوانا نبود")
    token = obj.get("access_token")
    if not isinstance(token, str) or not token.strip():
        raise CaptureError("NO_ACCESS_TOKEN", "access_token در نشست نیست")
    token_type = str(obj.get("token_type") or "")
    if token_type and token_type.lower() != "bearer":
        raise CaptureError("NOT_BEARER", "نوعِ توکن Bearer نیست")
    scope = str(obj.get("scope") or "")
    if not any(s in scope.split() for s in REQUIRED_SCOPES):
        raise CaptureError("SCOPE_MISSING", "توکن اسکوپِ API کارگزاری را ندارد")
    exp_raw = obj.get("expires_at")
    try:
        exp = int(exp_raw) if exp_raw not in (None, "") else 0
    except (TypeError, ValueError):
        raise CaptureError("BAD_EXPIRY", "زمانِ انقضایِ نشست خوانا نبود")
    now_s = time.time() if now is None else float(now)
    if exp and exp <= now_s:
        raise CaptureError("EXPIRED", "نشست منقضی شده است؛ دوباره وارد شوید")
    meta = {"token_type": token_type or "Bearer",
            "expires_at": exp or None,
            "scope": scope[:200],
            "has_access_token": True,
            "has_refresh_token": bool(obj.get("refresh_token"))}
    return token.strip(), meta


def capture_from_host(cdp_url: str, timeout_s: float = 20.0) -> tuple[str, dict[str, Any]]:
    """از hostِ محلی و صفحهٔ واردشدهٔ EasyTrader، نشست را می‌خواند."""
    parsed = urlparse(str(cdp_url or ""))
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost"):
        raise CaptureError("CDP_NOT_LOOPBACK", "نشانیِ CDP محلی نیست")
    try:
        from playwright.sync_api import sync_playwright
    except Exception:                            # noqa: BLE001
        raise CaptureError("PLAYWRIGHT_MISSING", "Playwright در این بیلد در دسترس نیست")
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(
                str(cdp_url).rstrip("/"), timeout=max(3.0, float(timeout_s)) * 1000)
            pages = [pg for ctx in browser.contexts for pg in ctx.pages]
            allowed = []
            for pg in pages:
                host = urlparse(str(pg.url or "")).hostname or ""
                if _allowed_host(host):
                    allowed.append((pg, host))
            if not allowed:
                raise CaptureError("LOGIN_REQUIRED",
                                   "صفحهٔ واردشدهٔ EasyTrader در host پیدا نشد")
            for pg, host in allowed:
                keys = pg.evaluate("() => Object.keys(window.sessionStorage)")
                key = next((str(k) for k in (keys or [])
                            if str(k).startswith(OIDC_PREFIX)), "")
                if not key:
                    continue
                raw = pg.evaluate("(k) => window.sessionStorage.getItem(k)", key)
                token, meta = parse_oidc_user(raw)
                meta["page_host"] = host
                # context manager فقط اتصالِ Playwright را می‌بندد؛ مرورگرِ host
                # و نشستِ مالک دست‌نخورده می‌مانند.
                return token, meta
            raise CaptureError("NO_SESSION", "کلیدِ نشستِ OIDC در صفحه پیدا نشد")
    except CaptureError:
        raise
    except Exception as e:                       # noqa: BLE001
        # متنِ خطایِ Playwright ممکن است شاملِ URL باشد؛ فقط نوعِ خطا برمی‌گردد.
        raise CaptureError("CAPTURE_FAILED", "خواندنِ نشست از مرورگر ممکن نشد (%s)"
                           % type(e).__name__)


__all__ = ["ALLOWED_HOSTS", "OIDC_PREFIX", "CaptureError",
           "capture_from_host", "parse_oidc_user"]
