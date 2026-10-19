# execution_har.py — خواندنِ یکِ HAR که خودِ مالک ذخیره کرده، بدونِ برداشتنِ هیچ رازی
#
# چرا این ماژول هست (بندِ ۷ مأموریتِ ۲۰۲۶-۱۰-۱۹): تنها درِ موجودِ نشست
# (`POST /api/execution/session`) یکِ رشته می‌پذیرد که مستقیماً هدرِ
# `Authorization: Bearer …` می‌شود. یعنی مالک باید توکنِ نشستِ خودش را باِ دست
# ازِ DevTools بردارد و درِ یکِ فیلدِ متنی بگذارد — نشانیِ حاویِ توکن درِ DOM،
# درِ کلیپ‌بورد و درِ تاریخچۀِ آن. این ماژول همان نشانی را ازِ پروندۀِ خودش
# بیرون می‌آورد تا رشته هیچ‌وقت درِ رابطِ کاربری دیده نشود، و درِ ضمنِ آن
# ساختارِ مسیرهایِ کارگزاری را نشان می‌دهد — چیزی که `docs/trading/
# PORTFOLIO-READ-CONTRACT-2026-10-18.md` §۵ تنها راهِ تغییرِ رأیِ «بی‌منبع» می‌دانست:
# یکِ شاهدِ بیرونی ازِ نشستِ واقعیِ مالک.
#
# چهار قاعده‌ای که این فایل می‌شکند اگر برایشان کدِ دیگری بنویسم:
#  • ورودی فقط **بدنۀِ خامِ HAR** است، نه مسیرِ دیسک. اندپوینتِ «فایلِ X را بخوان»
#    رویِ یکِ سرورِ بی‌احرازِ 127.0.0.1 یعنی خواندنِ دلخواهِ فایل‌هایِ ماشین.
#    پرونده را خودِ مرورگر باِ گفت‌وگویِ استانداردِ ویندوز انتخاب می‌کند.
#  • هیچ مقدارِ هدر و هیچ مقدارِ بدنۀِ پاسخ بیرون نمی‌رود. گزارش ازِ صفر و باِ
#    نامِ کلیدها ساخته می‌شود، و درِ پایان یک‌بار ازِ `redact()` هم می‌گذرد.
#  • توکن فقط درِ حافظه می‌نشیند (همان `set_token`ِ آداپتور) و هیچ پاسخِ دیگری
#    آن را برنمی‌گرداند. `repr`ِ این ماژول هم مقدار ندارد.
#  • میزبانِ برداشتِ توکن باید درِ `wire_hosts()` باشد؛ توکنِ یکِ میزبانِ بیگانه
#    حتی اگر درِ HAR باشد برداشته نمی‌شود.
from __future__ import annotations

import base64
import binascii
import json
import re
from typing import Any, Iterable, Mapping

import execution_easytrader as ET
from execution_contract import redact

#: سقفِ اندازهٔ بدنه. HARِ یکِ نشستِ کاملِ SPA معمولاً ۲ تا ۴۰ مگابایت است؛
#: بالاتر از این یا پروندۀِ دیگری است یا بدنه‌هایِ بی‌ربط.
MAX_HAR_BYTES = 96 * 1024 * 1024
#: بدنه‌ای بزرگ‌تر از این برایِ «نامِ کلیدها» باز نمی‌شود — هزینه بی‌فایده.
MAX_BODY_FOR_KEYS = 4 * 1024 * 1024
MAX_KEYS_PER_OBJECT = 14
MAX_PATH_ROWS = 60


class HarError(ValueError):
    """خطایِ ساختاریِ HAR. `detail` هرگز مقداری ازِ پرونده نیست، فقط علت."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


# ── ۱) تجزیه ────────────────────────────────────────────────────────────────
def load_entries(raw: bytes | str) -> list[dict[str, Any]]:
    """HAR را می‌خواند و فقط `entries` را بیرون می‌دهد. بی‌`log.entries` ⇒ خطا."""
    if isinstance(raw, (bytes, bytearray)):
        if len(raw) > MAX_HAR_BYTES:
            raise HarError("TOO_LARGE", "پروندۀ بزرگ‌تر از سقفِ مجاز است")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise HarError("NOT_UTF8", "پروندۀ باِ رمزنگیِ UTF-8 خوانده نشد") from None
    else:
        if len(raw.encode("utf-8", "ignore")) > MAX_HAR_BYTES:
            raise HarError("TOO_LARGE", "پروندۀ بزرگ‌تر از سقفِ مجاز است")
        text = raw
    try:
        doc = json.loads(text)
    except ValueError:
        raise HarError("NOT_JSON", "پروندۀ HAR تجزیه نشد (JSONِ معتبر نیست)") from None
    if not isinstance(doc, dict):
        raise HarError("SHAPE", "ساختارِ HAR ندارد: ریشۀِ پروندۀ شیء نیست")
    log = doc.get("log")
    entries = log.get("entries") if isinstance(log, dict) else None
    if not isinstance(entries, list):
        raise HarError("SHAPE", "ساختارِ HAR ندارد: `log.entries` فهرست نیست")
    return [e for e in entries if isinstance(e, dict)]


def url_parts(url: Any) -> tuple[str, str, str]:
    """(scheme, host, path) — کوئری و fragment دور ریخته می‌شوند.

    چرا حذفِ کوئری: درِ این APIها شناسه‌ها و گاهی نشانه‌ها درِ querystring
    می‌نشینند؛ «مسیر» برایِ ما همان مسیر است، نه آرگومان‌هایش.
    """
    s = str(url or "")
    m = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*)://([^/?#]+)([^?#]*)", s)
    if not m:
        return "", "", ""
    scheme = m.group(1).lower()
    netloc = m.group(2).lower()
    host = netloc.rsplit("@", 1)[-1]
    return scheme, host, m.group(3) or "/"


def _header(entries: Iterable[dict[str, Any]], name: str) -> str:
    want = name.lower()
    for h in entries:
        if isinstance(h, dict) and str(h.get("name") or "").lower() == want:
            return str(h.get("value") or "")
    return ""


def _header_names(entries: Iterable[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for h in entries:
        if isinstance(h, dict):
            n = str(h.get("name") or "").lower().strip()
            if n and n not in out:
                out.append(n)
    return out


def _json_keys(body: Any) -> list[str]:
    """نامِ کلیدهایِ سطحِ ۱ و ۲، بدونِ هیچ مقداری. بی‌JSON ⇒ فهرستِ خالی."""
    text = str(body or "")
    if not text or len(text) > MAX_BODY_FOR_KEYS:
        return []
    try:
        doc = json.loads(text)
    except ValueError:
        return []
    if isinstance(doc, list):
        doc = doc[0] if doc and isinstance(doc[0], dict) else None
    if not isinstance(doc, dict):
        return []
    names = sorted(str(k) for k in doc.keys())[:MAX_KEYS_PER_OBJECT]
    out = list(names)
    for k in names:
        v = doc.get(k)
        if isinstance(v, dict):
            sub = sorted(str(x) for x in v.keys())[:6]
            out.extend("%s.%s" % (k, x) for x in sub)
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            sub = sorted(str(x) for x in v[0].keys())[:6]
            out.extend("%s[].%s" % (k, x) for x in sub)
    return out


def _response_body(entry: Mapping[str, Any]) -> tuple[Any, bool]:
    """(متنِ بدنۀ JSON-نمای پاسخ, آیا base64 بود). غیرِ JSON ⇒ (None, False)."""
    resp = entry.get("response")
    content = resp.get("content") if isinstance(resp, dict) else None
    if not isinstance(content, dict):
        return None, False
    mime = str(content.get("mimeType") or "").lower()
    if "json" not in mime and "text" not in mime:
        return None, False
    enc = str(content.get("encoding") or "").lower()
    text = content.get("text")
    if enc == "base64" and isinstance(text, str):
        try:
            return base64.b64decode(text).decode("utf-8", "replace"), True
        except (binascii.Error, ValueError):
            return None, True
    return (text if isinstance(text, str) else None), False


# ── ۲) گزارشِ فقط‌ساختار ─────────────────────────────────────────────────────
def inspect(raw: bytes | str, *, hosts: tuple[str, ...] | None = None) -> dict[str, Any]:
    """چه میزبان‌هایی، چه مسیرهایی، با چه کلیدهایی پاسخ دادند. هیچ مقدار نه."""
    hosts = tuple(h.lower() for h in (hosts if hosts is not None else ET.wire_hosts()))
    entries = load_entries(raw)
    rows: dict[tuple[str, str, str, int], dict[str, Any]] = {}
    host_seen: dict[str, dict[str, Any]] = {}
    for e in entries:
        req = e.get("request") if isinstance(e.get("request"), dict) else {}
        resp = e.get("response") if isinstance(e.get("response"), dict) else {}
        scheme, host, path = url_parts(req.get("url"))
        if not host:
            continue
        req_hdrs = _header_names(req.get("headers") or [])
        req_cookies = req.get("cookies") if isinstance(req.get("cookies"), list) else []
        method = str(req.get("method") or "").upper() or "?"
        try:
            status = int(resp.get("status"))
        except (TypeError, ValueError):
            status = 0
        h = host_seen.setdefault(host, {"host": host, "entries": 0, "secure": 0,
                                        "auth_bearing": 0, "cookie_bearing": 0,
                                        "request_header_names": []})
        h["entries"] += 1
        if scheme == "https":
            h["secure"] += 1
        if "authorization" in req_hdrs:
            h["auth_bearing"] += 1
        if "cookie" in req_hdrs or req_cookies:
            h["cookie_bearing"] += 1
        for n in req_hdrs:
            if n not in h["request_header_names"] and len(h["request_header_names"]) < 24:
                h["request_header_names"].append(n)
        if host not in hosts:
            continue
        key = (host, method, path, status)
        if key not in rows and len(rows) < MAX_PATH_ROWS:
            body, was_b64 = _response_body(e)
            keys = _json_keys(body) if (body is not None and not was_b64) else []
            rows[key] = {"host": host, "method": method, "path": path, "status": status,
                         "response_keys": keys, "encoded_body": bool(was_b64),
                         "auth": "authorization" in req_hdrs,
                         "cookie": ("cookie" in req_hdrs) or bool(req_cookies)}
    on_wire = list(rows.values())
    on_wire.sort(key=lambda r: (r["host"], r["path"], r["method"]))
    return redact({
        "status": "success",
        "entries_total": len(entries),
        "wire_hosts": list(hosts),
        "hosts": sorted(host_seen.values(), key=lambda x: -int(x["entries"]))[:20],
        "api_paths": on_wire,
        "api_paths_capped": len(rows) >= MAX_PATH_ROWS,
        "off_wire_hosts": sum(1 for k in host_seen if k not in hosts),
        "detail": ("فقط نامِ میزبان، متد، مسیر و نامِ کلیدهایِ پاسخ ثبت شد؛ هیچ "
                   "مقدارِ هدر یا بدنه‌ای بازنگردانده نشد"),
        # صریح: این تحلیل است، نه سفارش، نه نشست
        "is_order": False,
        "session_touched": False,
    })


# ── ۳) برداشتِ نشانی ────────────────────────────────────────────────────────
def _jwt_exp(value: str) -> int | None:
    """`exp` ازِ یکِ JWTِ سه‌بخشی، بدونِ اعتبارِ امضا. غیرِ JWT ⇒ None."""
    parts = (value or "").strip().split(".")
    if len(parts) != 3:
        return None
    pad = "=" * (-len(parts[1]) % 4)
    try:
        blob = base64.urlsafe_b64decode(parts[1] + pad)
        claims = json.loads(blob.decode("utf-8", "replace"))
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None
    if not isinstance(claims, dict):
        return None
    try:
        return int(claims.get("exp"))           # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def find_bearer(entries: list[dict[str, Any]],
                hosts: tuple[str, ...] | None = None) -> tuple[str | None, dict[str, Any]]:
    """آخرین `Authorization` رویِ میزبانِ مجازِ wire. رشته را برمی‌گرداند و
     هیچ‌جا درِ گزارش نمی‌گذارد؛ `meta` فقط مبدأ و نوعِ نشانی است."""
    hosts = tuple(h.lower() for h in (hosts if hosts is not None else ET.wire_hosts()))
    meta: dict[str, Any] = {"scanned": len(entries), "on_wire": 0, "with_authorization": 0,
                            "with_cookie_only": 0, "host": None, "path": None,
                            "kind": None, "exp": None}
    best: str | None = None
    for e in entries:
        req = e.get("request") if isinstance(e.get("request"), dict) else {}
        _scheme, host, path = url_parts(req.get("url"))
        if host not in hosts:
            continue
        meta["on_wire"] += 1
        hdrs = req.get("headers") or []
        cookies = req.get("cookies") if isinstance(req.get("cookies"), list) else []
        auth = _header(hdrs, "authorization")
        if not auth:
            if _header(hdrs, "cookie") or cookies:
                meta["with_cookie_only"] += 1
            continue
        meta["with_authorization"] += 1
        best = auth.strip()
        meta["host"] = host
        meta["path"] = path
    if best is None:
        meta["kind"] = "none"
        return None, meta
    low = best.lower()
    meta["kind"] = ("bearer" if low.startswith("bearer ") else
                    "basic" if low.startswith("basic ") else
                    "jwt" if best.count(".") == 2 else "raw")
    meta["exp"] = _jwt_exp(best[len("bearer "):] if low.startswith("bearer ") else best)
    return best, meta


def import_session(raw: bytes | str, adapter: Any,
                   *, hosts: tuple[str, ...] | None = None) -> dict[str, Any]:
    """نشست را ازِ HAR درِ حافظۀِ آداپتور می‌گذارد. بی‌یافت ⇒ هیچ تغییری نمی‌کند."""
    hosts_t = tuple(h.lower() for h in (hosts if hosts is not None else ET.wire_hosts()))
    entries = load_entries(raw)
    token, meta = find_bearer(entries, hosts_t)
    out: dict[str, Any] = {"status": "success", "imported": False, **meta,
                           "wire_hosts": list(hosts_t),
                           "is_order": False, "token_in_response": False}
    if token is None:
        if meta["on_wire"] == 0:
            out["detail"] = ("هیچ پرسشی رویِ میزبانِ APIِ ثبت‌شدۀ این آداپتور درِ "
                             "پروندۀ نیست — نشستِ این برنامه باِ این HAR ساخته نمی‌شود")
            out["code"] = "NO_WIRE_HOST"
        elif meta["with_cookie_only"] > 0 and meta["with_authorization"] == 0:
            out["detail"] = ("پرسش‌ها رویِ میزبانِ API فقط باِ کوکی رفته‌اند و این "
                             "آداپتور کوکی نمی‌فرستَد؛ برداشت انجام نشد")
            out["code"] = "COOKIE_ONLY"
        else:
            out["detail"] = ("هیچ هدرِ `authorization` رویِ میزبانِ API پیدا نشد؛ "
                             "برداشت انجام نشد")
            out["code"] = "NO_AUTH_HEADER"
        return out
    setter = getattr(adapter, "set_token", None)
    if not callable(setter):
        out["detail"] = "آداپتورِ فعال نشانی نمی‌پذیرد — چیزی نوشته نشد"
        out["code"] = "UNSUPPORTED"
        return out
    setter(token)
    out.update({"imported": True, "detail":
                "نشست فقط درِ حافظه نشست؛ درِ هیچ پاسخی برنگشت و هیچ‌جا نوشته نشد"})
    return out
