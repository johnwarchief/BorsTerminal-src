# -*- coding: utf-8 -*-
"""execution_fast_order.py — پیش‌نمایشِ کامل، تأییدِ یک‌بارمصرف، و ارسالِ کوتاه.

چرا این ماژول جدا است: مسیرِ `/api/execution/dispatch` پیش از هر POST دوباره
preflight می‌زند (موجودی و نشست از کارگزاری خوانده می‌شوند) و read-back را
هم درِ همان درخواست انجام می‌دهد. برایِ سرخطی این یعنی دو RTT اضافه بینِ
«تأییدِ کاربر» و «رسیدنِ سفارش». اینجا کارِ کند یک‌بار درِ *پیش‌نمایش* انجام
می‌شود و لحظهٔ تأیید فقط گیت‌هایِ محلی + یک POST است.

سه قید که عمداً نشکسته‌اند:

  • پیش‌نمایش هیچ سفارشی نمی‌فرستد. توکنش یک‌بارمصرف و کوتاه‌عمر است.
  • دورهٔ تأیید (`epoch`) و هویتِ توکنِ نشست درِ توکن قفل می‌شوند؛ تغییرِ
    نشست یعنی «تأییدِ کهنه» و هیچ POSTی ساخته نمی‌شود.
  • نتیجهٔ نامعلوم (timeout/network/5xx) به «ارسالِ دوباره» تبدیل نمی‌شود؛
    توکن سوخته است و تنها راه، reconcile از فهرستِ سفارش است.
"""
from __future__ import annotations

import math
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from execution_contract import OrderDraft, Side

#: عمرِ پیش‌نمایش. کوتاه است چون موجودی/نشست می‌تواند در همین فاصله عوض شود؛
#: ۱۲۰ ثانیه برایِ «دیدم، فکر کردم، تأیید کردم» کافی است و توکنِ کهنه می‌میرد.
DEFAULT_TTL_S = 120.0
MAX_ENTRIES = 64


class FastOrderError(RuntimeError):
    """خطایِ گیت/توکن؛ `code` پایدار و قابلِ نمایش است."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = str(code)
        self.detail = str(detail)[:240]
        super().__init__(self.detail or self.code)


class FastOrderInputError(FastOrderError):
    """ورودیِ سفارش پیش از هر تماسِ بیرونی رد شد."""

    def __init__(self, field: str, code: str, detail: str) -> None:
        self.field = str(field)
        super().__init__(code, detail)


@dataclass
class FastPreview:
    """آنچه پیش‌نمایش به تأیید می‌سپارد. `prepared` هرگز به بیرون نمی‌رود."""
    token: str
    execution_id: str
    prepared: Any
    payload: Mapping[str, Any]
    epoch: int
    token_ref: Any
    created_mono: float
    created_wall_ms: int
    expires_mono: float
    summary: dict[str, Any]
    phase: str = "previewed"
    result_code: str = ""
    result_detail: str = ""

    def public(self) -> dict[str, Any]:
        return {
            "prepared_token": self.token,
            "execution_id": self.execution_id,
            "expires_in_ms": max(0, int((self.expires_mono - time.monotonic()) * 1000)),
            "phase": self.phase,
            "summary": dict(self.summary),
            "wire_preview": dict(self.payload),
            "result_code": self.result_code or None,
            "result_detail": self.result_detail or None,
        }


class FastOrderGateway:
    """مخزنِ درِ حافظهٔ پیش‌نمایش‌ها. thread-safe و بی‌هیچ I/O."""

    def __init__(self, *, ttl_s: float = DEFAULT_TTL_S,
                 clock: Callable[[], float] = time.monotonic,
                 wall_ms: Callable[[], int] = lambda: int(time.time() * 1000),
                 token_factory: Callable[[], str] | None = None,
                 max_entries: int = MAX_ENTRIES) -> None:
        self.ttl_s = float(ttl_s)
        self._clock = clock
        self._wall_ms = wall_ms
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(18))
        self._max_entries = int(max_entries)
        self._items: dict[str, FastPreview] = {}
        self._lock = threading.Lock()

    # ---- کمینهٔ مدیریت -----------------------------------------------------
    def reset(self) -> None:
        with self._lock:
            self._items.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._items)

    def _prune_locked(self, now: float) -> None:
        expired = [k for k, v in self._items.items()
                   if v.phase != "previewed" and v.expires_mono + 60.0 < now]
        for k in expired:
            self._items.pop(k, None)
        if len(self._items) <= self._max_entries:
            return
        ordered = sorted(self._items.values(),
                         key=lambda v: (v.phase not in ("previewed",),
                                        v.created_mono))
        for v in ordered[:max(0, len(self._items) - self._max_entries)]:
            self._items.pop(v.token, None)

    # ---- ساخت -------------------------------------------------------------
    def create(self, *, prepared: Any, payload: Mapping[str, Any], epoch: int,
               token_ref: Any, summary: dict[str, Any]) -> FastPreview:
        now = self._clock()
        token = self._token_factory()
        snap = FastPreview(
            token=token,
            execution_id=str(getattr(getattr(prepared, "draft", None),
                                     "execution_id", "") or ""),
            prepared=prepared,
            payload=dict(payload),
            epoch=int(epoch),
            token_ref=token_ref,
            created_mono=now,
            created_wall_ms=int(self._wall_ms()),
            expires_mono=now + self.ttl_s,
            summary=dict(summary))
        with self._lock:
            self._prune_locked(now)
            while token in self._items:
                token = self._token_factory()
                snap.token = token
            self._items[token] = snap
        return snap

    # ---- مصرف -------------------------------------------------------------
    def get(self, token: str) -> FastPreview | None:
        with self._lock:
            return self._items.get(str(token))

    def claim(self, token: str, *, epoch: int, token_ref: Any,
              halted: bool) -> FastPreview:
        """توکن را اتمی مصرف می‌کند. هر خطا پیش از مصرف، توکن را زنده می‌گذارد."""
        key = str(token or "")
        with self._lock:
            snap = self._items.get(key)
            if snap is None:
                raise FastOrderError("NOT_FOUND",
                                     "این پیش‌نمایش پیدا نشد؛ سفارش تازه‌ای بسازید")
            if snap.phase in ("sending", "sent", "unknown", "failed"):
                raise FastOrderError("ALREADY_USED",
                                     "این پیش‌نمایش پیش‌تر تأیید شده — دوباره ارسال "
                                     "نمی‌شود؛ وضعیت را از تاریخچه بررسی کنید")
            if snap.phase == "expired" or self._clock() >= snap.expires_mono:
                snap.phase = "expired"
                raise FastOrderError("EXPIRED",
                                     "اعتبارِ پیش‌نمایش تمام شد؛ دوباره «بررسی و خلاصه» "
                                     "را بزنید")
            if int(epoch) != snap.epoch or token_ref is not snap.token_ref:
                snap.phase = "stale"
                raise FastOrderError("STALE_CONFIRMATION",
                                     "نشست یا دسترسیِ حساب بینِ پیش‌نمایش و تأیید عوض "
                                     "شد؛ تأییدِ تازه لازم است")
            if halted:
                raise FastOrderError("HALTED",
                                     "توقفِ اضطراری باز است؛ ارسال ممکن نیست")
            snap.phase = "sending"
            return snap

    def finish(self, token: str, *, phase: str, code: str = "",
               detail: str = "") -> None:
        with self._lock:
            snap = self._items.get(str(token))
            if snap is None:
                return
            snap.phase = str(phase)
            snap.result_code = str(code or "")
            snap.result_detail = str(detail or "")


# ── اعتبارسنجیِ ورودی ────────────────────────────────────────────────────────
def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        v = float(value)
    else:
        s = str(value).strip().translate(str.maketrans(
            "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
        s = s.replace(",", "").replace("٬", "").replace(" ", "")
        if not s:
            return None
        try:
            v = float(s)
        except (TypeError, ValueError):
            return None
    return v if math.isfinite(v) else None


def parse_order_inputs(body: Mapping[str, Any]) -> dict[str, Any]:
    """(symbol, side, price, quantity) — یا FastOrderInputError با فیلدِ مشخص."""
    symbol = str(body.get("symbol") or "").strip()
    if not symbol:
        raise FastOrderInputError("symbol", "INVALID_SYMBOL", "نماد را انتخاب کنید")
    if len(symbol) > 64:
        raise FastOrderInputError("symbol", "INVALID_SYMBOL", "نمادِ نامعتبر")
    raw_side = str(body.get("side") or "").strip().lower()
    if raw_side not in (Side.BUY.value, Side.SELL.value):
        raise FastOrderInputError("side", "INVALID_SIDE", "جهتِ سفارش خرید یا فروش است")
    price = _num(body.get("price"))
    if price is None or price <= 0:
        raise FastOrderInputError("price", "INVALID_PRICE",
                                  "قیمت باید عددیِ بزرگ‌تر از صفر باشد")
    qty = _num(body.get("quantity"))
    if qty is None or qty <= 0:
        raise FastOrderInputError("quantity", "INVALID_QUANTITY",
                                  "تعداد باید عددیِ بزرگ‌تر از صفر باشد")
    if abs(qty - round(qty)) > 1e-9:
        raise FastOrderInputError("quantity_integer", "INVALID_QUANTITY",
                                  "تعدادِ سهم باید عددِ صحیح باشد")
    return {"symbol": symbol, "side": Side(raw_side), "price": float(price),
            "quantity": float(round(qty)),
            "price_source": str(body.get("price_source") or "unspecified")[:80],
            "price_as_of": (str(body.get("price_as_of"))[:40]
                            if body.get("price_as_of") else None)}


def summary_of(draft: OrderDraft, prepared: Any, *, live: bool, dry_run: bool,
               session: Mapping[str, Any], risk_ok: bool,
               risk_reason: str = "", send_ready: bool) -> dict[str, Any]:
    checks = dict(getattr(getattr(prepared, "preflight", None), "checks", {}) or {})
    reasons = dict(getattr(getattr(prepared, "preflight", None), "reasons", {}) or {})
    warnings = [{"id": k, "status": v, "reason": reasons.get(k, "")}
                for k, v in checks.items() if v != "PASS"]
    value = None
    if draft.price is not None and draft.quantity is not None:
        value = round(float(draft.price) * float(draft.quantity), 2)
    return {
        "symbol": draft.instrument.symbol,
        "isin": draft.instrument.isin,
        "side": draft.side.value,
        "price": draft.price,
        "quantity": draft.quantity,
        "value": value,
        "price_source": draft.price_source,
        "price_as_of": draft.price_as_of,
        "validity": "day",
        "order_model": "oms",
        "checks": checks,
        "warnings": warnings[:8],
        "live": bool(live),
        "dry_run": bool(dry_run),
        "session": dict(session),
        "risk_ok": bool(risk_ok),
        "risk_reason": str(risk_reason or "")[:200],
        "send_ready": bool(send_ready),
    }


__all__ = [
    "DEFAULT_TTL_S", "FastOrderError", "FastOrderInputError", "FastPreview",
    "FastOrderGateway", "parse_order_inputs", "summary_of",
]
