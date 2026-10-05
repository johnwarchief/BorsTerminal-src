# -*- coding: utf-8 -*-
"""execution_mock.py — یک کارگزاریِ بدل، برایِ آزمونِ قراردادِ اجرا.

چرا این فایل هست: بندِ ۲۸ دستورِ کار می‌گوید پیش از هر سفارشِ واقعی، همۀِ
مسیرِ اجرا باید بدونِ کارگزاریِ واقعی طی شود. پس این بدل «موفقیت» نیست که
مسیرهایِ سخت را رد کند — دقیقاً برایِ همان مسیرهایِ سخت ساخته شده است:
timeout با نتیجهٔ نامعلوم، 5xx، خطایِ احراز، خطایِ اعتبارسنجی، و تکراری‌بودن.

سه چیزی که بدل *صادقانه* شبیه‌سازی می‌کند (و اگر دروغ بگوید، آزمون بی‌فایده است):

۱) `timeout` یعنی «سرور شاید پذیرفت و ما ندیدیم» — پس سفارش درِ دفترِ سرور
   ثبت می‌شود ولی فراخوان `BrokerError(TIMEOUT)` می‌گیرد. این تنها راهی است که
   می‌توان ثابت کرد مسیرِ `UNKNOWN_RESULT → RECONCILE` کار می‌کند و اینکه
   retryِ کور چه فاجعه‌ای می‌سازد (دو سفارشِ واقعی).

۲) `http5xx` یعنی «سرور پاسخ نداد و نپذیرفت» — با timeout یک رفتارِ فراخوان
   دارد (reconcile) ولی نتیجۀِ reconcile فرق می‌کند؛ پس کد نمی‌تواند هر دو را
   با «retry» قاطی کند.

۳) `NOT_ORDERABLE` اصلاً به سرور نمی‌رسد: شمارندۀِ `wire_calls` ثابت می‌کند
   هیچ درخواستی بیرون نرفته. (§۷-ب: fallback به ISINِ «زر» ممنوع.)

هیچ نشانیِ واقعی، هیچ کلاینتِ HTTP و هیچ کارگزاریِ واقعی درِ این فایل نیست.
"""
from __future__ import annotations

from typing import Callable, Iterable

from execution_contract import (
    BrokerAdapter, BrokerError, Capabilities, ExecutionRecord, ExecutionStatus,
    InstrumentRef, OrderDraft, OrderState, QueueSnapshot, Resolution,
    SessionState, SessionStatus, Side, ErrorCode, redact,
)

#: پیامدهایِ ممکنِ یک ارسال
OUTCOMES = ("ok", "timeout", "http5xx", "reject_price", "reject_quantity",
            "reject_broker", "auth", "expired", "rate_limited", "market_closed")


class MockBrokerAdapter(BrokerAdapter):
    """کارگزاریِ بدلِ قابلِ برنامه‌ریزی.

    `script`: نگاشتِ `execution_id → [outcome, …]`؛ هر `submit_order` یکی از
    فهرست را مصرف می‌کند و تکرارشده‌ها آخرین را نگه می‌دارند. چیزی که فهرستش
    نباشد `ok` می‌گیرد.
    `clock`: تابعِ زمانِ یکنوا (monotonic)ِ تزریق‌شده — تا آزمونِ زمان‌بندی
    بی‌خوابِ واقعی اجرا شود.
    """

    name = "mock"

    def __init__(self, *,
                 instruments: Iterable[InstrumentRef] = (),
                 capabilities: Capabilities | None = None,
                 script: dict[str, list[str]] | None = None,
                 session: SessionStatus | None = None,
                 clock: Callable[[], float] | None = None,
                 latency_ms: float = 0.0,
                 duplicate_policy: str = "guard",
                 order_states: dict[str, OrderState] | None = None) -> None:
        self._caps = capabilities or Capabilities(list_orders=True, order_state=True,
                                                  queue_position=True)
        self._by_symbol = {i.symbol: i for i in instruments}
        self._script: dict[str, list[str]] = {k: list(v) for k, v in (script or {}).items()}
        self._session = session or SessionStatus(SessionState.CONNECTED, "mock-acct-1")
        self._clock = clock or _default_clock()
        self._latency_ms = latency_ms
        self._duplicate_policy = duplicate_policy
        #: وضعیتِ سفارشِ هر execution_id از دیدِ سرور؛ نبودش یعنی UNKNOWN.
        self.order_states: dict[str, OrderState] = dict(order_states or {})

        #: هر درخواستِ *واقعاً ارسالی* به سرور (برایِ اثباتِ «بیرون نرفت»)
        self.wire_calls: list[str] = []
        #: آنچه سرور پذیرفته — حتی وقتی کلاینت ندیده (حالتِ timeout)
        self.server_orders: dict[str, ExecutionRecord] = {}
        #: جایِ صفِ هر سفارشِ پذیرفته‌شده؛ `set_queue` پر می‌کندش. نبودش یعنی
        #: سرور چیزی نمی‌گوید ⇒ UNKNOWN، نه صفر.
        self.queue_by_order: dict[str, tuple[int | None, float | None]] = {}
        self._by_execution: dict[str, ExecutionRecord] = {}
        self._next_id = 1
        self.redacted_log: list[dict] = []
        #: فقط وقتی خوانده می‌شود که capability `balances` روشن باشد
        self.balances: dict[str, float] = {"cash": 0.0, "positions": {}}

    # ---- توانایی / نشست ---------------------------------------------------
    def capabilities(self) -> Capabilities:
        return self._caps

    def authenticate(self) -> SessionStatus:
        self.wire_calls.append("authenticate")
        if self._session.state is SessionState.EXPIRED:
            raise BrokerError(ErrorCode.SESSION_EXPIRED, "mock: session expired")
        return self._session

    def session_status(self) -> SessionStatus:
        return self._session

    def set_session(self, status: SessionStatus) -> None:
        self._session = status

    # ---- ابزار ------------------------------------------------------------
    def add_instrument(self, ref: InstrumentRef) -> None:
        self._by_symbol[ref.symbol] = ref

    def resolve_instrument(self, symbol: str) -> InstrumentRef:
        self.wire_calls.append(f"resolve:{symbol}")
        ref = self._by_symbol.get(symbol)
        if ref is None:
            # هیچ «نزدیک‌ترین» اینجا نیست؛ برگشتِ یک ISINِ حدسی §۷-ب است.
            return InstrumentRef(symbol=symbol, resolution=Resolution.UNRESOLVED)
        return ref

    # ---- اعتبارسنجی -------------------------------------------------------
    def validate_order(self, draft: OrderDraft) -> str | None:
        structural = draft.sanity()
        if structural:
            return structural
        ok, reason = draft.instrument.orderable()
        if not ok:
            return reason
        if not self._caps.place:
            return "UNSUPPORTED:place"
        return None

    # ---- ارسال ------------------------------------------------------------
    def submit_order(self, draft: OrderDraft) -> ExecutionRecord:
        existing = self._by_execution.get(draft.execution_id)
        if existing is not None:
            if self._duplicate_policy == "guard":
                raise BrokerError(ErrorCode.DUPLICATE_GUARD,
                                  f"{draft.execution_id} پیش‌تر ارسال شده")
            return existing

        bad = self.validate_order(draft)
        if bad:
            # NOT_ORDERABLE: نه سرور صدا زده می‌شود، نه سفارشی ثبت می‌شود
            raise BrokerError(_code_from_reason(bad), bad)

        self.wire_calls.append(f"submit:{draft.execution_id}")
        record = self._new_record(draft)
        outcome = self._pop_outcome(draft.execution_id)
        sent_at = self._clock()
        record.scheduled_at = sent_at
        record.actual_send_at = sent_at
        record.status = ExecutionStatus.DISPATCHED
        record.attempts += 1

        if self._latency_ms:
            record.rtt_ms = self._latency_ms
            record.response_at = sent_at + self._latency_ms / 1000.0

        self.redacted_log.append(redact({
            "execution_id": draft.execution_id,
            "authorization": "Bearer super-secret-token-value",
            "cookie": "session=abcdef",
        }))

        handler: Callable[[ExecutionRecord], ExecutionRecord] = _HANDLERS[outcome]
        return handler(self, record)

    # ---- خواندنِ نتیجه / reconcile ----------------------------------------
    def get_orders(self) -> list[ExecutionRecord]:
        if not self._caps.list_orders:
            raise BrokerError(ErrorCode.UNSUPPORTED, "mock: list_orders unsupported")
        self.wire_calls.append("get_orders")
        return list(self.server_orders.values())

    def get_order(self, broker_order_id: str) -> ExecutionRecord | None:
        if not self._caps.order_state:
            raise BrokerError(ErrorCode.UNSUPPORTED, "mock: order_state unsupported")
        self.wire_calls.append(f"get_order:{broker_order_id}")
        return self.server_orders.get(broker_order_id)

    def get_queue_position(self, broker_order_id: str) -> QueueSnapshot | None:
        if not self._caps.queue_position:
            # None یعنی UNKNOWN؛ صفرِ جعلی «اولِ صف شدید» است (§۱۸ دستورِ کار)
            return None
        self.wire_calls.append(f"queue:{broker_order_id}")
        if broker_order_id not in self.server_orders:
            return None
        pos, vol = self.queue_by_order.get(broker_order_id, (None, None))
        return QueueSnapshot(position=pos, volume_ahead=vol,
                             as_of=self._iso(), source="mock")

    def get_balances(self):
        if not self._caps.balances:
            return None            # «نمی‌دانیم» ≠ «صفر»
        self.wire_calls.append("balances")
        return dict(self.balances)

    def cancel_order(self, broker_order_id: str) -> bool:
        if not self._caps.cancel:
            raise BrokerError(ErrorCode.UNSUPPORTED,
                              "mock: cancel unsupported (هیچ مرجعِ بازبینی‌شده‌ای "
                              "لغو را پیاده نکرده — §۷-الف)")
        self.wire_calls.append(f"cancel:{broker_order_id}")
        return broker_order_id in self.server_orders

    # ---- کمکی -------------------------------------------------------------
    def _new_record(self, draft: OrderDraft) -> ExecutionRecord:
        rec = ExecutionRecord(
            execution_id=draft.execution_id, broker=self.name,
            account=self._session.account_label, symbol=draft.instrument.symbol,
            isin=draft.instrument.isin, side=draft.side, price=draft.price,
            quantity=draft.quantity, mode=draft.mode, clock_offset_ms=0.0)
        self._by_execution[draft.execution_id] = rec
        return rec

    def set_queue(self, broker_order_id: str, position: int | None,
                  volume_ahead: float | None = None) -> None:
        self.queue_by_order[broker_order_id] = (position, volume_ahead)

    def set_order_state(self, execution_id: str, state: OrderState,
                        filled: float | None = None) -> None:
        """تغییرِ وضعیتِ سفارش رویِ سرور — برایِ آزمونِ مسیرِ read-back."""
        self.order_states[execution_id] = state
        rec = self._by_execution.get(execution_id)
        if rec is not None:
            rec.order_state = state
            if filled is not None:
                rec.filled_quantity = filled

    def _accept(self, rec: ExecutionRecord) -> ExecutionRecord:
        rec.broker_order_id = f"MOCK-{self._next_id:05d}"
        self._next_id += 1
        rec.status = ExecutionStatus.ACKNOWLEDGED
        #: کارگزاریِ واقعی همواره وضعیتِ سفارش را نمی‌گوید؛ `order_states`
        #: خالی یعنی UNKNOWN بماند (§۱۸: نبودِ اطلاعات ≠ «اولِ صف»).
        rec.order_state = self.order_states.get(rec.execution_id, OrderState.UNKNOWN)
        rec.note("server accepted")
        self.server_orders[rec.broker_order_id] = rec
        return rec

    def _pop_outcome(self, execution_id: str) -> str:
        seq = self._script.get(execution_id)
        if not seq:
            return "ok"
        return seq.pop(0) if len(seq) > 1 else seq[0]

    def _iso(self) -> str:
        return f"mock-t{int(self._clock() * 1000)}"


# ---- پیامدها ---------------------------------------------------------------
def _ok(mock: MockBrokerAdapter, rec: ExecutionRecord) -> ExecutionRecord:
    return mock._accept(rec)


def _timeout(mock: MockBrokerAdapter, rec: ExecutionRecord) -> ExecutionRecord:
    """سرور پذیرفت، کلاینت ندید ⇒ نتیجه نامعلوم. سفارش درِ دفترِ سرور هست."""
    mock._accept(rec)
    rec.status = ExecutionStatus.UNKNOWN_RESULT
    rec.note("accepted server-side, ack lost")
    raise BrokerError(ErrorCode.TIMEOUT, f"{rec.execution_id}: ack lost")


def _http5xx(mock: MockBrokerAdapter, rec: ExecutionRecord) -> ExecutionRecord:
    """سرور پاسخ نداد و نپذیرفت ⇒ باز هم نامعلوم، ولی reconcile چیزی نمی‌یابد."""
    rec.status = ExecutionStatus.UNKNOWN_RESULT
    rec.note("server 500, not accepted")
    raise BrokerError(ErrorCode.NETWORK_ERROR, "mock: 500 internal error")


def _reject_price(mock: MockBrokerAdapter, rec: ExecutionRecord) -> ExecutionRecord:
    rec.status = ExecutionStatus.FAILED
    rec.error_code = ErrorCode.INVALID_PRICE
    raise BrokerError(ErrorCode.INVALID_PRICE, "price outside allowed range",
                      broker_message="خارج از مجاز")


def _reject_quantity(mock: MockBrokerAdapter, rec: ExecutionRecord) -> ExecutionRecord:
    rec.status = ExecutionStatus.FAILED
    rec.error_code = ErrorCode.INVALID_QUANTITY
    raise BrokerError(ErrorCode.INVALID_QUANTITY, "quantity below minimum")


def _reject_broker(mock: MockBrokerAdapter, rec: ExecutionRecord) -> ExecutionRecord:
    rec.status = ExecutionStatus.FAILED
    rec.error_code = ErrorCode.BROKER_REJECTED
    raise BrokerError(ErrorCode.BROKER_REJECTED, "omsError",
                      broker_message="سفارش درِ وضعیتِ فعلی پذیرفته نشد")


def _auth(mock: MockBrokerAdapter, rec: ExecutionRecord) -> ExecutionRecord:
    rec.status = ExecutionStatus.FAILED
    raise BrokerError(ErrorCode.AUTH_FAILED, "bad credentials")


def _expired(mock: MockBrokerAdapter, rec: ExecutionRecord) -> ExecutionRecord:
    mock.set_session(SessionStatus(SessionState.EXPIRED, mock._session.account_label))
    rec.status = ExecutionStatus.FAILED
    raise BrokerError(ErrorCode.SESSION_EXPIRED, "token cache stale")


def _rate_limited(mock: MockBrokerAdapter, rec: ExecutionRecord) -> ExecutionRecord:
    rec.status = ExecutionStatus.FAILED
    raise BrokerError(ErrorCode.RATE_LIMITED, "too many requests", retry_after_ms=500)


def _market_closed(mock: MockBrokerAdapter, rec: ExecutionRecord) -> ExecutionRecord:
    rec.status = ExecutionStatus.FAILED
    raise BrokerError(ErrorCode.MARKET_CLOSED, "outside session window")


_HANDLERS: dict[str, Callable[[MockBrokerAdapter, ExecutionRecord], ExecutionRecord]] = {
    "ok": _ok, "timeout": _timeout, "http5xx": _http5xx,
    "reject_price": _reject_price, "reject_quantity": _reject_quantity,
    "reject_broker": _reject_broker, "auth": _auth, "expired": _expired,
    "rate_limited": _rate_limited, "market_closed": _market_closed,
}


def _code_from_reason(reason: str) -> ErrorCode:
    head = reason.split(":")[-1].upper()
    mapping = {
        "INVALID_PRICE": ErrorCode.INVALID_PRICE,
        "INVALID_QUANTITY": ErrorCode.INVALID_QUANTITY,
        "INVALID_EXECUTION_ID": ErrorCode.INVALID_EXECUTION_ID,
        "PLACE": ErrorCode.UNSUPPORTED,
    }
    return mapping.get(head, ErrorCode.NOT_ORDERABLE)


def _default_clock() -> Callable[[], float]:
    import time
    return time.monotonic


__all__ = ["MockBrokerAdapter", "OUTCOMES", "Side"]
