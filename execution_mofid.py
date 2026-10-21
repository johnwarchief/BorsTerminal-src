# -*- coding: utf-8 -*-
"""execution_mofid.py — آداپتورِ مستقلِ مفید/Titan برایِ Round 15.5.

قرارداد از `estakhri/Sarkhati@b63f55b` (`src/mofid.rs`, `config_mofid.example.json`)
گرفته شده است؛ این یک پروتکلِ **دیگر** است و با EasyTrader/Orbis قاطی نمی‌شود.
هیچ شبکه‌ای درِ import یا تستِ dry-run باز نمی‌شود؛ ترافیک تزریقی است. 2xx فقط
«ثبتِ درخواست» است و read-back/acceptance ادعا نمی‌شود.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from execution_contract import (
    BrokerAdapter, BrokerError, Capabilities, ErrorCode, ExecutionRecord,
    ExecutionStatus, OrderDraft, OrderState, SessionState, SessionStatus, Side,
)
from execution_easytrader import (
    RefusingTransport, Transport, TransportNetwork, TransportRefused,
    TransportTimeout, WireResponse,
)

ADAPTER_NAME = "mofid"
WIRE_BASE_URL = "https://mofidonline.com"
WIRE_PATH_ORDER_CREATE = "/apigateway/api/v1/Order/send"
WIRE_URL = WIRE_BASE_URL + WIRE_PATH_ORDER_CREATE
WIRE_ORIGIN = "https://tg.mofidonline.com"
WIRE_APP_NAME = "titan"
WIRE_ORDER_FROM = "Titan"
WIRE_VALIDITY_DAY = 0
CONTRACT_STATE = "THIRD_PARTY_CLIENT_OBSERVED"
CONTRACT_PROVENANCE = ("estakhri/Sarkhati@b63f55b src/mofid.rs + "
                       "config_mofid.example.json; no first-party docs")


class _Secret:
    __slots__ = ("_v",)

    def __init__(self, value: Any = None) -> None:
        self._v = str(value or "")

    def expose(self) -> str:
        return self._v

    def __bool__(self) -> bool:
        return bool(self._v)

    def __repr__(self) -> str:
        return "<mofid-secret>"


@dataclass(frozen=True)
class MofidPayload:
    order: dict[str, Any]


def _num(value: Any) -> Any:
    f = float(value or 0)
    if f <= 0:
        raise ValueError("positive value required")
    return int(f) if f.is_integer() else f


def build_payload(draft: OrderDraft, *, validity_type: int = WIRE_VALIDITY_DAY,
                  validity_date: Optional[str] = None,
                  order_from: str = WIRE_ORDER_FROM) -> dict[str, Any]:
    """فیلدهایِ مشاهده‌شده در مرجع؛ هیچ فیلدِ EasyTrader اینجا وارد نمی‌شود."""
    side = "Buy" if draft.side is Side.BUY else "Sell"
    body: dict[str, Any] = {
        "orderSide": side,
        "price": _num(draft.price),
        "quantity": _num(draft.quantity),
        "symbolIsin": str(getattr(draft.instrument, "isin", "") or "").strip(),
        "validityType": int(validity_type),
        "validityDate": validity_date,
        "orderFrom": str(order_from),
    }
    if not body["symbolIsin"]:
        raise ValueError("symbolIsin required")
    # برخلافِ EasyTrader، Mofid/Titan بدنهٔ تخت می‌خواهد (mofid.rs:51-52).
    return body


class MofidAdapter(BrokerAdapter):
    """یک مسیرِ APIِ جدا؛ تا وقتی balance/read-back واقعی نداریم live آن fail-closed است."""
    name = ADAPTER_NAME

    def __init__(self, *, transport: Optional[Transport] = None,
                 token: Any = None, cookie: Any = None,
                 order_url: str = WIRE_URL, writes_allowed: bool = True,
                 timeout_s: float = 7.0) -> None:
        self._transport = transport or RefusingTransport()
        self._token = _Secret(token)
        self._cookie = _Secret(cookie)
        self.order_url = str(order_url or WIRE_URL)
        self._writes_allowed = bool(writes_allowed)
        self.timeout_s = float(timeout_s)
        self.wire_calls: list[str] = []
        self.redacted_log: list[dict[str, Any]] = []
        self._session = SessionStatus(
            SessionState.UNKNOWN if (self._token or self._cookie)
            else SessionState.DISCONNECTED)

    def __repr__(self) -> str:
        return "<MofidAdapter live=%s transport=%s>" % (
            self.live, getattr(self._transport, "name", "?"))

    @property
    def live(self) -> bool:
        return bool(getattr(self._transport, "is_live", False)
                    and (self._token or self._cookie))

    @property
    def writes_allowed(self) -> bool:
        return bool(self._writes_allowed and self.live)

    def set_token(self, value: Any) -> None:
        self._token = _Secret(value)
        self._session = SessionStatus(SessionState.UNKNOWN if self._token
                                      else SessionState.DISCONNECTED)

    def has_token(self) -> bool:
        return bool(self._token or self._cookie)

    def clear_token(self) -> None:
        self._token = _Secret(None)
        self._cookie = _Secret(None)
        self._session = SessionStatus(SessionState.DISCONNECTED)

    def capabilities(self) -> Capabilities:
        if not self.live:
            return Capabilities(place=False, balances=False)
        # balances=True یعنی preflight باید پاسخِ حساب را بخواهد؛ پاسخِ ما فعلاً
        # خالی است ⇒ UNKNOWNِ مسدودکننده، نه «مجاز».
        return Capabilities(place=True, balances=True)

    def authenticate(self) -> SessionStatus:
        # هیچ GETِ تأییدشده‌ای برایِ Mofid نداریم؛ حضورِ توکن «متصل» نیست.
        self._session = SessionStatus(
            SessionState.UNKNOWN if self.has_token() else SessionState.DISCONNECTED,
            checked_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
        return self._session

    def session_status(self) -> SessionStatus:
        return self._session

    def session_proven(self) -> bool:
        return False

    def get_balances(self) -> dict[str, Any]:
        # مسیرِ حسابِ Mofid در مرجع بررسی نشده؛ خالی ⇒ preflight می‌بندد.
        return {}

    def get_orders(self) -> list[ExecutionRecord]:
        raise BrokerError(ErrorCode.UNSUPPORTED,
                          "Mofid read-back/order list در این آداپتور پشتیبانی نمی‌شود")

    def get_order(self, broker_order_id: str) -> Optional[ExecutionRecord]:
        return None

    def get_queue_position(self, broker_order_id: str) -> None:
        return None

    def cancel(self, broker_order_id: str) -> None:
        raise BrokerError(ErrorCode.UNSUPPORTED,
                          "لغو در قراردادِ بررسی‌شدهٔ Mofid پشتیبانی نمی‌شود")

    def _record(self, draft: OrderDraft, status: ExecutionStatus,
                *, detail: str = "", error: Optional[ErrorCode] = None,
                broker_order_id: Optional[str] = None) -> ExecutionRecord:
        rec = ExecutionRecord(
            execution_id=draft.execution_id, broker=ADAPTER_NAME, account=None,
            symbol=draft.instrument.symbol, isin=draft.instrument.isin,
            side=draft.side, price=draft.price, quantity=draft.quantity,
            mode=draft.mode, status=status, order_state=OrderState.UNKNOWN,
            broker_order_id=broker_order_id, error_code=error,
            error_detail=detail[:200], attempts=1)
        rec.note("mofid: %s" % CONTRACT_STATE)
        return rec

    def submit_order(self, draft: OrderDraft) -> ExecutionRecord:
        if not self.writes_allowed:
            self.wire_calls.append("submit:REFUSED")
            raise BrokerError(ErrorCode.UNSUPPORTED,
                              "Mofid: live/writes gate بسته است؛ هیچ درخواستی ساخته نشد")
        payload = build_payload(draft)
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Referer": WIRE_ORIGIN + "/",
            "Origin": WIRE_ORIGIN,
            "x-appname": WIRE_APP_NAME,
        }
        tok = self._token.expose()
        if tok:
            headers["Authorization"] = (tok if tok.lower().startswith("bearer ")
                                        else "Bearer " + tok)
        if self._cookie:
            headers["Cookie"] = self._cookie.expose()
        self.wire_calls.append("send:POST")
        try:
            resp: WireResponse = self._transport.request(
                method="POST", url=self.order_url, headers=headers,
                payload=payload, timeout_s=self.timeout_s)
        except (TransportTimeout, TransportNetwork, TransportRefused) as e:
            self.redacted_log.append({"tag": "mofid.send", "error": type(e).__name__})
            raise BrokerError(ErrorCode.UNKNOWN_RESULT,
                              "Mofid: پاسخ نیامد/شبکه — نتیجه نامعلوم؛ retry ممنوع") from None
        # هیچ توکن/بدنه‌ای در ردِّپا نوشته نمی‌شود.
        self.redacted_log.append({"tag": "mofid.send", "status": resp.status,
                                  "url": self.order_url})
        if resp.status in (401, 403):
            self._session = SessionStatus(SessionState.EXPIRED)
            raise BrokerError(ErrorCode.SESSION_EXPIRED,
                              "Mofid: HTTP %d — نشست پذیرفته نشد" % resp.status)
        if 200 <= resp.status < 300:
            # 2xx به‌تنهایی پذیرش نیست؛ read-back قابل‌اتکا نداریم.
            return self._record(
                draft, ExecutionStatus.UNKNOWN_RESULT,
                detail="Mofid 2xx فقط ثبتِ درخواست است؛ read-back/acceptance تأیید نشد")
        if 400 <= resp.status < 500:
            return self._record(draft, ExecutionStatus.FAILED,
                                detail="Mofid HTTP %d" % resp.status,
                                error=ErrorCode.BROKER_REJECTED)
        return self._record(draft, ExecutionStatus.UNKNOWN_RESULT,
                            detail="Mofid HTTP %d — نتیجه نامعلوم" % resp.status)


__all__ = ["ADAPTER_NAME", "WIRE_URL", "CONTRACT_STATE", "CONTRACT_PROVENANCE",
           "MofidAdapter", "build_payload"]
