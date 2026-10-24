# -*- coding: utf-8 -*-
"""execution_mofid_capture.py — فقط‌خواندنِ نشستِ مرورگرِ اختصاصیِ Mofid.

مالک خودش در پنجرهٔ hostِ **نام‌دار mofid** وارد می‌شود. این ماژول هیچ رمز،
OTP یا CAPTCHA نمی‌پرسد و هیچ صفحه‌ای را هدایت/بازنشانی نمی‌کند؛ فقط با اقدامِ
صریحِ مالک (دکمهٔ «بررسی اتصال») از همان CDPِ محلی، کلیدِ `token` را از
localStorage صفحهٔ `tg.mofidonline.com` می‌خواند و به آداپتورِ درونِ حافظه
می‌دهد.

قفل‌ها:
  • فقط hostهایِ allowlist؛ صفحهٔ ورودِ سایر سرویس‌ها خوانده نمی‌شود.
  • token در پاسخ، meta، repr، log یا پیامِ خطا نمی‌آید؛ فقط طول/نوع/exp.
  • صفحه بسته یا navigate نمی‌شود؛ فقط اتصالِ Playwright بسته می‌شود.
  • token منقضی/خالی/بیش‌ازحد بلند پذیرفته نمی‌شود.
"""
from __future__ import annotations

import base64
import json
import time
from typing import Any, Iterable
from urllib.parse import urlparse

ALLOWED_HOSTS = ("tg.mofidonline.com",)
TOKEN_KEY = "token"
MIN_TOKEN = 8
MAX_TOKEN = 8192


class CaptureError(Exception):
    """خطایِ قابلِ نمایش؛ `detail` هرگز مقدارِ نشست را در خود ندارد."""

    def __init__(self, code: str, detail: str = ""):
        self.code = str(code)
        self.detail = str(detail)[:200]
        super().__init__(self.detail or self.code)


def _allowed_host(host: str, allowed: Iterable[str]) -> bool:
    h = (host or "").lower()
    return any(h == a or h.endswith("." + a) for a in allowed)


def _jwt_times(raw: str) -> tuple[int | None, int | None]:
    """exp/iat از payloadِ JWT؛ بی‌اعتبار ⇒ (None, None) — توکن را چاپ نمی‌کنیم."""
    parts = raw.split(".")
    if len(parts) != 3:
        return None, None
    try:
        pad = "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + pad).decode("utf-8"))
    except Exception:                            # noqa: BLE001 - توکنِ غیرJWT
        return None, None
    if not isinstance(payload, dict):
        return None, None
    out = []
    for key in ("exp", "iat"):
        try:
            value = int(payload.get(key))
            out.append(value if value > 0 else None)
        except (TypeError, ValueError):
            out.append(None)
    return out[0], out[1]


def parse_mofid_token(raw: Any, *, page_host: str = "",
                      page_path: str = "", now: float | None = None
                      ) -> tuple[str, dict[str, Any]]:
    """(token, metadata) — token فقط برایِ set_token؛ در meta برنمی‌گردد."""
    if not isinstance(raw, str) or not raw.strip():
        raise CaptureError("NO_SESSION", "کلیدِ نشست در صفحه پیدا نشد")
    token = raw.strip()
    if len(token) < MIN_TOKEN:
        raise CaptureError("BAD_TOKEN", "مقدارِ نشست کوتاه‌تر از حدِ انتظار است")
    if len(token) > MAX_TOKEN:
        raise CaptureError("SESSION_TOO_LARGE", "مقدارِ نشست بزرگ‌تر از حدِ انتظار است")
    if any(ch.isspace() for ch in token):
        raise CaptureError("BAD_TOKEN", "مقدارِ نشست فاصله دارد")
    expires_at, issued_at = _jwt_times(token)
    now_s = time.time() if now is None else float(now)
    if expires_at is not None and expires_at <= now_s:
        raise CaptureError("EXPIRED", "نشست منقضی شده است؛ دوباره وارد شوید")
    meta = {
        "token_present": True,
        "token_length": len(token),
        # همان قاعدهٔ خودِ کلاینتِ Titan: طول > 36 ⇒ Bearer، وگرنه Basic.
        "token_type": "Bearer" if len(token) > 36 else "Basic",
        "expires_at": expires_at,
        "issued_at": issued_at,
        "expired": False,
        "page_host": page_host,
        "page_path": page_path,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    return token, meta


def capture_from_host(cdp_url: str, timeout_s: float = 20.0,
                      allowed_hosts: Iterable[str] = ALLOWED_HOSTS
                      ) -> tuple[str, dict[str, Any]]:
    """از hostِ محلی و صفحهٔ واردشدهٔ Mofid، token را فقط در حافظه می‌خواند.

    `allowed_hosts` فقط برایِ آزمونِ محلی قابلِ override است؛ مسیرِ API هرگز
    آن را تغییر نمی‌دهد.
    """
    parsed = urlparse(str(cdp_url or ""))
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost"):
        raise CaptureError("CDP_NOT_LOOPBACK", "نشانیِ CDP محلی نیست")
    allowed = tuple(a for a in allowed_hosts if a)
    if not allowed:
        raise CaptureError("NO_ALLOWED_HOST", "فهرستِ hostهایِ مجاز خالی است")
    try:
        from playwright.sync_api import sync_playwright
    except Exception:                            # noqa: BLE001
        raise CaptureError("PLAYWRIGHT_MISSING", "Playwright در این بیلد در دسترس نیست")
    last: CaptureError | None = None
    saw_page = False
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(
                str(cdp_url).rstrip("/"), timeout=max(3.0, float(timeout_s)) * 1000)
            pages = [pg for ctx in browser.contexts for pg in ctx.pages]
            for pg in pages:
                try:
                    url = str(pg.url or "")
                    host = urlparse(url).hostname or ""
                    if not _allowed_host(host, allowed):
                        continue
                    saw_page = True
                    path = urlparse(url).path or "/"
                    keys = pg.evaluate("() => Object.keys(window.localStorage)")
                    if TOKEN_KEY not in (keys or []):
                        continue
                    raw = pg.evaluate("(k) => window.localStorage.getItem(k)", TOKEN_KEY)
                    if not raw:
                        continue
                    return parse_mofid_token(raw, page_host=host, page_path=path)
                except CaptureError as e:
                    last = e
                    if e.code == "EXPIRED":
                        continue
                    raise
                except Exception:                # noqa: BLE001 - مرزِ صفحه
                    continue
    except CaptureError:
        raise
    except Exception as e:                       # noqa: BLE001
        raise CaptureError("CAPTURE_FAILED", "خواندنِ نشست از مرورگر ممکن نشد (%s)"
                           % type(e).__name__)
    if last is not None:
        raise last
    if not saw_page:
        raise CaptureError("LOGIN_REQUIRED", "صفحهٔ مجازِ Mofid در host پیدا نشد")
    raise CaptureError("NO_SESSION", "کلیدِ نشست در صفحهٔ Mofid نیست؛ وارد شوید")


__all__ = ["ALLOWED_HOSTS", "TOKEN_KEY", "CaptureError",
           "capture_from_host", "parse_mofid_token"]
