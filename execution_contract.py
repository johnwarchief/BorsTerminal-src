# -*- coding: utf-8 -*-
"""execution_contract.py — یک قرارداد، یک مالکیت: مدلِ دامنهٔ «ثبتِ سفارش».

مرجعِ طراحی: docs/execution/SARKHATI-ARCHITECTURE.md §۹ (مدلِ دامنهٔ Stage C).
همان‌جا نوشته شد که هیچ مفهومی بی‌شواهد وارد این فایل نمی‌شود؛ هر نوعِ زیر
یا از §۱ (وضعیتِ خودِ ریپو) می‌آید یا از §۷ (کدِ واقعیِ مراجع) — و آن‌که از
هیچ‌کدام نیاید `UNVERIFIED` علامت دارد.

چهار حکمی که این فایل نگهبانش است، نه کامنتشان:

۱) **شناسهٔ نماد بی‌fallback.** `InstrumentRef.orderable()` برایِ نمادی که ISIN
   ندارد `NOT_ORDERABLE` می‌دهد، نه «نزدیک‌ترین». دلیلش درِ §۷-ب: مرجعِ
   TypeScript برایِ نمادِ ناشناخته بی‌صدا به ISINِ «زر» برمی‌گردد
   (`symbolHelper.ts:18`) و ما همان را رویِ پولِ واقعی ممنوع می‌کنیم. هزینه‌اش
   صریح است: 1820 نمادِ بی‌ISIN از 5674 درِ بانکِ امروز قابلِ سفارش نیستند.

۲) **timeout هرگز retry نیست.** `BrokerError.is_unknown_result` تنها پاسخِ
   مجازِ TIMEOUT/NETWORK_ERROR را می‌گوید: *اول reconcile، بعد تصمیم*.
   مرجعِ اول بعدِ 408/5xx دو بارِ backoffِ نمایی retry می‌کند رویِ
   `POST /order` (§۷-الف) — یعنی سفارشِ تکراریِ واقعی.

۳) **unavailable با reject قاطی نمی‌شود.** `QueueSnapshot` و `SessionStatus`
   هیچ‌وقت صفرِ جعلی نمی‌سازند؛ `None` یعنی UNKNOWN. (§۱-د: بهترینِ خرید/فروش
   درِ پاسخِ تابلو نیست؛ §۷-الف: `cancel` درِ هیچ مرجعی پیاده نشده.)

۴) **هیچ secret درِ متنِ قابلِ لاگ.** `redact()` تنها راهِ نوشتنِ هرچه از
   پاسخ/درخواستِ کارگزاری درِ لاگ است؛ دلیلش §۱-ط: access log رویِ دیسک
   می‌نشیند و `GET /api/diagnostics/log` همان فایل را برمی‌گرداند.

این فایل هیچ شبکه‌ای نمی‌زند و هیچ کارگزاریِ واقعی را نمی‌شناسد.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


# ── ۱) شناسهٔ ابزار ──────────────────────────────────────────────────────────
class Resolution(str, Enum):
    """چگونه به شناسهٔ کارگزاری رسیدیم. «نزدیک‌ترین» درِ این فهرست نیست."""
    EXACT = "exact"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class InstrumentRef:
    """ارجاعِ ابزار، آن‌طور که برایِ *سفارش* لازم است — نه برایِ نمایش."""
    symbol: str
    ins_code: str | None = None
    isin: str | None = None
    broker_instrument: str | None = None
    resolution: Resolution = Resolution.UNRESOLVED

    def orderable(self) -> tuple[bool, str]:
        """(قابلِ سفارش؟، دلیلِ رد). تنها دلیلِ مجازِ رد، نبودِ شناسه است."""
        if self.resolution is not Resolution.EXACT:
            return False, "NOT_ORDERABLE:resolution"
        if not (self.isin or "").strip():
            return False, "NOT_ORDERABLE:isin"
        if not (self.broker_instrument or "").strip():
            return False, "NOT_ORDERABLE:broker_instrument"
        return True, ""


# ── ۲) سفارش ────────────────────────────────────────────────────────────────
class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderMode(str, Enum):
    """سه حالتِ بندِ ۱۴ دستورِ کار. ULTRA هیچ retry ضمنی اضافه نمی‌کند."""
    SAFE = "safe"
    FAST = "fast"
    ULTRA = "ultra"


@dataclass(frozen=True)
class OrderDraft:
    execution_id: str
    instrument: InstrumentRef
    side: Side
    price: float | None
    quantity: float | None
    mode: OrderMode = OrderMode.SAFE
    price_source: str = "unspecified"
    price_as_of: str | None = None

    def sanity(self) -> str | None:
        """خطایِ ساختاری — قبلِ آنکه هیچ پرسیدنی از کارگزاری بشود."""
        if not (self.execution_id or "").strip():
            return "INVALID_EXECUTION_ID"
        if self.quantity is None or self.quantity <= 0:
            return "INVALID_QUANTITY"
        if self.price is None or self.price <= 0:
            return "INVALID_PRICE"
        return None


# ── ۳) taxonomyِ خطا (بندِ ۲۰) ──────────────────────────────────────────────
class ErrorCode(str, Enum):
    AUTH_FAILED = "AUTH_FAILED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT = "TIMEOUT"
    BROKER_REJECTED = "BROKER_REJECTED"
    INVALID_PRICE = "INVALID_PRICE"
    INVALID_QUANTITY = "INVALID_QUANTITY"
    MARKET_CLOSED = "MARKET_CLOSED"
    DUPLICATE_GUARD = "DUPLICATE_GUARD"
    UNKNOWN_RESULT = "UNKNOWN_RESULT"
    QUEUE_UNAVAILABLE = "QUEUE_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    NOT_ORDERABLE = "NOT_ORDERABLE"
    UNSUPPORTED = "UNSUPPORTED"
    #: خطایِ ساختاریِ سمتِ خودِ اپ (نه کارگزاری) — بی‌درخواستِ بیرونی
    INVALID_EXECUTION_ID = "INVALID_EXECUTION_ID"


#: کدهایی که معنایشان «نمی‌دانیم چه شد» است، نه «نشَد». تنها راهِ مجاز،
#: reconcile است — نه ارسالِ دوباره. (§۲۱ دستورِ کار: STOP/RECONCILE نه RETRY)
UNRESOLVED_CODES = frozenset((ErrorCode.NETWORK_ERROR, ErrorCode.TIMEOUT,
                              ErrorCode.UNKNOWN_RESULT))

#: کدهایی که ارسالِ دوباره‌شان بی‌reconcile ممنوع است، حتی بی‌خطای شبکه.
RETRY_FORBIDDEN_CODES = UNRESOLVED_CODES | {ErrorCode.BROKER_REJECTED,
                                            ErrorCode.DUPLICATE_GUARD}


class BrokerError(Exception):
    """خطایِ کارگزاری با معنایِ عملیاتی. `detail` هرگز secret ندارد (redact شود)."""

    def __init__(self, code: ErrorCode, detail: str = "", *,
                 broker_message: str = "", retry_after_ms: int | None = None):
        super().__init__(f"{code.value}: {detail}" if detail else code.value)
        self.code = code
        self.detail = detail
        self.broker_message = broker_message
        self.retry_after_ms = retry_after_ms

    @property
    def is_unknown_result(self) -> bool:
        return self.code in UNRESOLVED_CODES

    @property
    def retry_forbidden(self) -> bool:
        return self.code in RETRY_FORBIDDEN_CODES


# ── ۴) توانایی و حالتِ نشست ──────────────────────────────────────────────────
@dataclass(frozen=True)
class Capabilities:
    """هر adapter صریح می‌گوید چه می‌تواند بکند. False یعنی «نیست»، نه «صفر»."""
    place: bool = True
    list_orders: bool = False
    order_state: bool = False
    queue_position: bool = False
    cancel: bool = False
    best_bid_ask: bool = False
    #: آیا کارگزاری نقدینگی/موقعیت می‌دهد؟ نبودش یعنی UNKNOWN، نه صفر (§۱۶).
    balances: bool = False


class SessionState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SessionStatus:
    state: SessionState = SessionState.UNKNOWN
    account_label: str | None = None
    checked_at: str | None = None


@dataclass(frozen=True)
class QueueSnapshot:
    """جایِ صف. `None` یعنی UNKNOWN — صفرِ جعلی ساختنِ «اولِ صف شدید» است."""
    position: int | None = None
    volume_ahead: float | None = None
    as_of: str | None = None
    source: str = "unknown"

    @property
    def known(self) -> bool:
        return self.position is not None or self.volume_ahead is not None


# ── ۵) رکوردِ اجرا ──────────────────────────────────────────────────────────
class ExecutionStatus(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    PREPARED = "prepared"
    SCHEDULED = "scheduled"
    DISPATCHED = "dispatched"
    ACKNOWLEDGED = "acknowledged"
    UNKNOWN_RESULT = "unknown_result"
    RECONCILED = "reconciled"
    FAILED = "failed"


@dataclass
class ExecutionRecord:
    """ستونِ فقراتِ ردِّپا. target/actual/drift ماندگارند، نه فقط لاگ (§۷-ج)."""
    execution_id: str
    broker: str
    account: str | None
    symbol: str
    isin: str | None
    side: Side
    price: float | None
    quantity: float | None
    mode: OrderMode
    status: ExecutionStatus = ExecutionStatus.DRAFT
    scheduled_at: float | None = None
    actual_send_at: float | None = None
    response_at: float | None = None
    rtt_ms: float | None = None
    drift_us: float | None = None
    clock_offset_ms: float | None = None
    broker_order_id: str | None = None
    error_code: ErrorCode | None = None
    error_detail: str = ""
    attempts: int = 0
    events: list[str] = field(default_factory=list)

    def note(self, what: str) -> None:
        self.events.append(what)

    @property
    def needs_reconcile(self) -> bool:
        return self.status is ExecutionStatus.UNKNOWN_RESULT


# ── ۶) redaction — تنها راهِ نوشتنِ هرچه از کارگزاری درِ لاگ ─────────────────
_SECRET_KEYS = ("authorization", "proxy-authorization", "cookie", "set-cookie",
                "x-csrf-token", "csrftoken", "access_token", "refreshtoken",
                "token", "password", "pass", "secret", "api_key", "apikey")
_BEARER_RE = re.compile(r"(?i)\b(bearer\s+)[a-z0-9._~+/=-]{6,}")
_KV_RE = re.compile(r"(?i)\b(" + "|".join(re.escape(k) for k in _SECRET_KEYS) + r")\b(\s*[=:]\s*)(\S+)")


def redact(value: Any) -> Any:
    """مقدارِ هر کلیدِ رازدار را به `<redacted>` بدل می‌کند؛ بی‌تغییرِ ساختار."""
    if isinstance(value, Mapping):
        return {k: ("<redacted>" if str(k).lower() in _SECRET_KEYS else redact(v))
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, str):
        s = _BEARER_RE.sub(lambda m: m.group(1) + "<redacted>", value)
        return _KV_RE.sub(lambda m: m.group(1) + m.group(2) + "<redacted>", s)
    return value


# ── ۷) قراردادِ adapter ──────────────────────────────────────────────────────
class BrokerAdapter:
    """رابطِ اجراییِ هر کارگزاری. پیاده‌سازیِ واقعی باید contract testِ
    `dev/execution_contract_v1.py` را رد کند — همان آزمونِ MockBrokerAdapter.

    چهار قاعده‌ای که امضایِ متدها بیانگرشان است (و گارد می‌سنجد، نه کامنت):

    • `submit_order` هرگز درونِ خودش retry نمی‌کند. اگر نتیجه نامعلوم شد،
      `BrokerError(TIMEOUT|NETWORK_ERROR)` می‌دهد و فراخوان *مکلف* به reconcile است.
    • `submit_order` رویِ `execution_id` تکراری سفارشِ دوم نمی‌سازد
      (`DUPLICATE_GUARD` یا همان رکوردِ اول).
    • هیچ متدی برایِ ابزاری که `orderable()` false است به کارگزاری درخواست
      نمی‌فرستد — `NOT_ORDERABLE` محلی داده می‌شود.
    • متدهایی که capability شان false است `BrokerError(UNSUPPORTED)` می‌دهند
      یا `None`/UNKNOWN برمی‌گردانند — هرگز صفرِ جعلی.
    """

    name = "abstract"

    def capabilities(self) -> Capabilities:                            # pragma: no cover
        raise NotImplementedError

    def authenticate(self) -> SessionStatus:                           # pragma: no cover
        raise NotImplementedError

    def session_status(self) -> SessionStatus:                         # pragma: no cover
        raise NotImplementedError

    def resolve_instrument(self, symbol: str) -> InstrumentRef:        # pragma: no cover
        raise NotImplementedError

    def validate_order(self, draft: OrderDraft) -> str | None:         # pragma: no cover
        raise NotImplementedError

    def submit_order(self, draft: OrderDraft) -> ExecutionRecord:      # pragma: no cover
        raise NotImplementedError

    def get_orders(self) -> list[ExecutionRecord]:                     # pragma: no cover
        raise NotImplementedError

    def get_order(self, broker_order_id: str) -> ExecutionRecord | None:  # pragma: no cover
        raise NotImplementedError

    def get_queue_position(self, broker_order_id: str) -> QueueSnapshot | None:  # pragma: no cover
        raise NotImplementedError

    def cancel_order(self, broker_order_id: str) -> bool:              # pragma: no cover
        raise NotImplementedError

    def get_balances(self) -> Mapping[str, float] | None:              # pragma: no cover
        """نقدینگی/موقعیت. None یعنی «کارگزاری نمی‌دهد» — پیش‌فرضِ ایمن."""
        return None
