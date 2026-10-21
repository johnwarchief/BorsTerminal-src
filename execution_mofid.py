# -*- coding: utf-8 -*-
"""execution_mofid.py — آداپتورِ مستقلِ مفید/Titan.

Round 15.5 فقط `Order/send` را از کدِ شخصِ ثالث می‌شناخت. Round 16 مسیرهای
**فقط‌خواندنی** را از بستهٔ منتشرشدهٔ خودِ کارگزاری گرفت: `tg.mofidonline.com`
یک Next.js export است و چانکِ `_next/static/chunks/3rfv56m3yme3b.js` تعریفِ
همان API client را دارد (gateway = `https://mofidonline.com/apigateway/api/v1`).
این شاهد «کدِ اول‌طرف» است، نه سند رسمی؛ پاسخِ واقعی هنوز در این ماشین دیده
نشده و همه‌جا همین را می‌گوییم.

قفل‌ها:
  • هیچ شبکه‌ای درِ import یا تست باز نمی‌شود؛ ترافیک تزریقی است.
  • مسیرهایِ GET (وضعیتِ مشتری، پرتفوی، سفارش‌ها) هیچ وضعیتی را تغییر نمی‌دهند.
  • `Order/send` همچنان اگر 2xx بدهد «نتیجه نامعلوم» است؛ read-back ادعا نمی‌شود.
  • `get_sellable_quantity` یک کرانِ محافظه‌کارانه از فیلدهایِ پرتفوی است و
    برچسبِ `CLIENT_DERIVED_UNVERIFIED` دارد؛ عددِ کارگزاری جا زده نمی‌شود.
  • توکن/کوکی در repr، لاگ یا پیامِ خطا نمی‌آید.
"""
from __future__ import annotations

import json
import math
import re
import time
from typing import Any, Mapping, Optional

from execution_contract import (
    BrokerAdapter, BrokerError, Capabilities, ErrorCode, ExecutionRecord,
    ExecutionStatus, OrderDraft, OrderMode, OrderState, SessionState,
    SessionStatus, Side,
)
from execution_easytrader import (
    RefusingTransport, Transport, TransportNetwork, TransportRefused,
    TransportTimeout, WireResponse,
)

ADAPTER_NAME = "mofid"
WIRE_BASE_URL = "https://mofidonline.com"
WIRE_GATEWAY_V1 = WIRE_BASE_URL + "/apigateway/api/v1"
WIRE_GATEWAY_V2 = WIRE_BASE_URL + "/apigateway/api/v2"
WIRE_WEB_V4 = "https://api.mofidonline.com/Web/V4"
WIRE_PATH_ORDER_CREATE = "/apigateway/api/v1/Order/send"
WIRE_URL = WIRE_BASE_URL + WIRE_PATH_ORDER_CREATE
WIRE_ORIGIN = "https://tg.mofidonline.com"
#: ورودیِ رسمیِ اپِ Titan؛ مسیرِ /login هم در buildManifest همان بسته هست، ولی
#: ریشهٔ همان origin را باز می‌کنیم تا خودِ کلاینت مسیرِ ورود را انتخاب کند.
MOFID_LOGIN_URL = WIRE_ORIGIN + "/"
WIRE_APP_NAME = "titan"
WIRE_ORDER_FROM = "Titan"
WIRE_VALIDITY_DAY = 0

#: مسیرهایِ فقط‌خواندنی، عیناً از چانکِ منتشرشدهٔ Titan.
WIRE_PATH_CUSTOMER_STATUS = "/Order/customer/status"
WIRE_PATH_PORTFOLIO_DAILY = "/Portfolio/Daily"
WIRE_PATH_OPEN_ORDERS = "/Order/open-orders"
WIRE_PATH_TODAY_ORDER = "/Order/today-order"
WIRE_PATH_ORDER_STATE = "/Order/state/"
WIRE_PATH_ORDER_DETAIL = "/Order/detail/"
WIRE_PATH_ACCOUNTING_REMAIN = "/Accounting/Remain"

URL_CUSTOMER_STATUS = WIRE_GATEWAY_V1 + WIRE_PATH_CUSTOMER_STATUS
URL_PORTFOLIO_DAILY = WIRE_GATEWAY_V1 + WIRE_PATH_PORTFOLIO_DAILY
URL_OPEN_ORDERS = WIRE_GATEWAY_V1 + WIRE_PATH_OPEN_ORDERS
URL_TODAY_ORDER = WIRE_GATEWAY_V1 + WIRE_PATH_TODAY_ORDER
URL_ACCOUNTING_REMAIN = WIRE_WEB_V4 + WIRE_PATH_ACCOUNTING_REMAIN

CONTRACT_STATE = "FIRST_PARTY_CLIENT_OBSERVED"
CONTRACT_PROVENANCE = (
    "tg.mofidonline.com deployed Next.js bundle "
    "(_next/static/chunks/3rfv56m3yme3b.js, read 2026-10-21): gateway base, "
    "Authorization/x-appname, customer/status, Portfolio/Daily, open-orders, "
    "Order/state|detail; order send also estakhri/Sarkhati@b63f55b src/mofid.rs"
)
SELLABLE_FORMULA = ("max(0, min(currentAsset, currentAsset + todaySoldAsset - "
                    "todayBoughtAsset) - openSellOrders)")
SELLABLE_STATE = "CLIENT_DERIVED_UNVERIFIED"
WRITE_STATE = "UNVERIFIED"
_ORDER_ID_RE = re.compile(r"[A-Za-z0-9._-]{1,64}")

#: Round 18: دو شاهدِ مستقل برایِ واحد/معنا/دقت. مقدارِ حساب در کد نیست.
UNIT = "IRR"
UNIT_VERIFICATION = {
    "state": "VERIFIED",
    "unit": UNIT,
    "precision": 0,
    "server_unit_field": False,
    "evidence": (
        "official Mofid UI displayed «قدرت خرید» equal to /Accounting/Remain "
        "purchasingPower exactly (amount masked here) and «بلوکه شده» equal to "
        "blockedBalance=0; the same page labels monetary amounts as ریال (the "
        "power widget itself has no unit suffix); the deployed Titan client "
        "formats purchasingPower with the shared digit formatter (also used for "
        "price/volume, no /10) and toFixed(0)"
    ),
    "observed_at": "2026-10-22",
}
UNIT_EVIDENCE = UNIT_VERIFICATION["evidence"]
POSITION_FIELD_MAP = {
    "current_asset": "currentAsset",
    "today_bought": "todayBoughtAsset",
    "today_sold": "todaySoldAsset",
    "open_sell": "openSellOrders",
    "settled": "currentAsset + todaySoldAsset - todayBoughtAsset",
    "sellable": "max(0, min(currentAsset, settled) - openSellOrders)",
}
ORDER_CONTRACT = {
    "open_orders": {"path": WIRE_PATH_OPEN_ORDERS, "method": "GET",
                    "id_field": "orderId", "state_field": "orderState",
                    "fields": ["orderId", "symbol", "symbolIsin", "orderPrice",
                               "quantity", "executedQuantity", "orderSide",
                               "validityType", "validityDateTime", "orderState"]},
    "today_order": {"path": WIRE_PATH_TODAY_ORDER, "method": "GET",
                    "id_field": "orderId", "state_field": "orderState",
                    "fields": ["orderId", "symbol", "symbolIsin", "orderPrice",
                               "quantity", "executedQuantity", "orderSide",
                               "validityType", "validityDateTime", "orderState"]},
    "state": {"path": WIRE_PATH_ORDER_STATE + "{orderId}", "method": "GET",
              "state_field": "orderState|state", "id_source": "real list only"},
    "detail": {"path": WIRE_PATH_ORDER_DETAIL + "{orderId}", "method": "GET",
               "id_source": "real list only"},
    "semantics": {
        "send_2xx": "REQUEST_RECORDED_NOT_ACCEPTED",
        "acceptance": "not proven",
        "read_back": "only for an orderId obtained from a real open/today list",
    },
}
_TS_KEYS = ("serverTime", "server_time", "serverTimestamp", "lastUpdate",
            "lastUpdateTime", "updateTime", "updatedAt", "timestamp",
            "dateTime", "datetime")


def _find_timestamp(data: Any) -> dict[str, Any] | None:
    """اگر پاسخ خودش یک فیلدِ زمانِ نام‌دار داشت، همان را خام گزارش می‌دهد.

    هیچ حدسی دربارهٔ منطقهٔ زمانی/معنا نمی‌زنیم؛ صرفِ وجودِ فیلد کافی نیست.
    """
    if not isinstance(data, Mapping):
        return None
    for key in _TS_KEYS:
        if key in data and data.get(key) not in (None, ""):
            return {"key": key, "raw": str(data.get(key))[:80],
                    "interpretation": "UNVERIFIED"}
    return None
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


def _positive(value: Any) -> Any:
    f = float(value or 0)
    if f <= 0:
        raise ValueError("positive value required")
    return int(f) if f.is_integer() else f


def _num(value: Any) -> float | None:
    """عددِ واقعی یا None؛ صفرِ جعلی از «نیامد» ساخته نمی‌شود."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        f = float(value)
        return f if math.isfinite(f) else None
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _data_envelope(payload: Any) -> Any:
    """پاکتِ `{data: ...}` که کلاینتِ Titan با `e.data` می‌خواند."""
    if isinstance(payload, Mapping) and "data" in payload:
        return payload.get("data")
    return payload


def authorization_value(token: Any) -> str:
    """قاعدهٔ خودِ کلاینتِ Titan: طولِ > 36 ⇒ Bearer، وگرنه Basic."""
    tok = str(token or "").strip()
    if not tok:
        return ""
    if tok.lower().startswith(("bearer ", "basic ")):
        return tok
    return ("Bearer " if len(tok) > 36 else "Basic ") + tok


#: نام‌هایِ enumِ Titan (چانکِ 3rfv56m): Open/Cancel/DeleteByNsc/... .
#: هر نامِ ناشناخته UNKNOWN می‌ماند؛ «شاید پر شده» حدس نیست.
_STATE_MAP: dict[str, OrderState] = {
    "open": OrderState.OPEN,
    "senttonsc": OrderState.OPEN,
    "inomqueue": OrderState.PENDING,
    "onboard": OrderState.PENDING,
    "onsending": OrderState.PENDING,
    "modify": OrderState.PENDING,
    "onmodifying": OrderState.PENDING,
    "onmodified": OrderState.PENDING,
    "onmodifyboard": OrderState.PENDING,
    "partiallyexecution": OrderState.PARTIAL,
    "partiallyexecutedandmodified": OrderState.PARTIAL,
    "partiallyexecutedandexpired": OrderState.PARTIAL,
    "partiallyexecutedanderror": OrderState.PARTIAL,
    "partiallyexecutedandcanceled": OrderState.PARTIAL,
    "orderexecuted": OrderState.FILLED,
    "done": OrderState.FILLED,
    "cancel": OrderState.CANCELLED,
    "cancelbybroker": OrderState.CANCELLED,
    "cancelbysurveillance": OrderState.CANCELLED,
    "deletebynsc": OrderState.CANCELLED,
    "deletebysupervisor": OrderState.CANCELLED,
    "deletebybroker": OrderState.CANCELLED,
    "expired": OrderState.CANCELLED,
    "reject": OrderState.REJECTED,
    "error": OrderState.REJECTED,
}


def map_order_state(raw: Any, *, quantity: float | None = None,
                    executed: float | None = None) -> OrderState:
    """وضعیتِ Titan ← OrderStateِ خودی؛ متنِ ناشناخته ⇒ UNKNOWN."""
    txt = _text(raw)
    if txt:
        hit = _STATE_MAP.get(txt.lower())
        if hit is not None:
            return hit
    if quantity is not None and quantity > 0 and executed is not None:
        if executed >= quantity:
            return OrderState.FILLED
        if executed > 0:
            return OrderState.PARTIAL
    return OrderState.UNKNOWN


def build_payload(draft: OrderDraft, *, validity_type: int = WIRE_VALIDITY_DAY,
                  validity_date: Optional[str] = None,
                  order_from: str = WIRE_ORDER_FROM) -> dict[str, Any]:
    """فیلدهایِ مشاهده‌شده در مرجع؛ هیچ فیلدِ EasyTrader اینجا وارد نمی‌شود."""
    side = "Buy" if draft.side is Side.BUY else "Sell"
    body: dict[str, Any] = {
        "orderSide": side,
        "price": _positive(draft.price),
        "quantity": _positive(draft.quantity),
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
    """مسیرِ APIِ جدا؛ خواندن فقط با شاهدِ اول‌طرف، نوشتن هنوز fail-closed."""

    name = ADAPTER_NAME

    def __init__(self, *, transport: Optional[Transport] = None,
                 token: Any = None, cookie: Any = None,
                 order_url: str = WIRE_URL, writes_allowed: bool = True,
                 read_only: bool | None = None, timeout_s: float = 7.0) -> None:
        self._transport = transport or RefusingTransport()
        self._token = _Secret(token)
        self._cookie = _Secret(cookie)
        self.order_url = str(order_url or WIRE_URL)
        self._writes_allowed = bool(writes_allowed)
        # حالتِ تستِ این راند: هر درخواست باید GET و درِ allowlist باشد. این
        # قفل درِ خودِ `_call` است، نه فقط درِ UI.
        self._read_only = (bool(read_only) if read_only is not None
                           else not self._writes_allowed)
        self.timeout_s = float(timeout_s)
        self.wire_calls: list[str] = []
        self.redacted_log: list[dict[str, Any]] = []
        self.session_proof: dict[str, Any] = {}
        self._verified_token: Optional[_Secret] = None
        self._status_cache: tuple[float, Any] | None = None
        self._known_order_ids: set[str] = set()
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
        return bool(self._writes_allowed and self.live and not self._read_only)

    @property
    def read_only(self) -> bool:
        return bool(self._read_only)

    def set_token(self, value: Any) -> None:
        self._token = _Secret(value)
        self._verified_token = None
        self.session_proof = {}
        self._status_cache = None
        self._known_order_ids.clear()
        self._session = SessionStatus(SessionState.UNKNOWN if self._token
                                      else SessionState.DISCONNECTED)

    def has_token(self) -> bool:
        return bool(self._token or self._cookie)

    def clear_token(self) -> None:
        self._token = _Secret(None)
        self._cookie = _Secret(None)
        self._verified_token = None
        self.session_proof = {}
        self._status_cache = None
        self._known_order_ids.clear()
        self._session = SessionStatus(SessionState.DISCONNECTED)

    def capabilities(self) -> Capabilities:
        if not self.live:
            return Capabilities(place=False, balances=False)
        return Capabilities(place=bool(self._writes_allowed and not self._read_only),
                            list_orders=True, order_state=True, balances=True)

    # ---- ترافیک -----------------------------------------------------------
    def _headers(self, extra: Optional[Mapping[str, str]] = None) -> dict[str, str]:
        h = {"Accept": "application/json, text/plain, */*",
             "x-appname": WIRE_APP_NAME}
        auth = authorization_value(self._token.expose())
        if auth:
            h["Authorization"] = auth
        elif self._cookie:
            h["Cookie"] = self._cookie.expose()
        if extra:
            h.update({str(k): str(v) for k, v in extra.items()})
        return h

    @staticmethod
    def _read_url_allowed(method: str, url: str) -> bool:
        if str(method).upper() != "GET":
            return False
        if url in (URL_CUSTOMER_STATUS, URL_PORTFOLIO_DAILY,
                   URL_OPEN_ORDERS, URL_TODAY_ORDER, URL_ACCOUNTING_REMAIN):
            return True
        for prefix in (WIRE_GATEWAY_V1 + WIRE_PATH_ORDER_DETAIL,
                       WIRE_GATEWAY_V1 + WIRE_PATH_ORDER_STATE):
            if url.startswith(prefix):
                return bool(_ORDER_ID_RE.fullmatch(url[len(prefix):]))
        return False

    def _call(self, method: str, url: str, *, tag: str, timeout_s: float | None = None,
              payload: Any = None, extra_headers: Optional[Mapping[str, str]] = None,
              log_body: bool = False) -> WireResponse:
        if self._read_only and not self._read_url_allowed(method, url):
            raise BrokerError(ErrorCode.UNSUPPORTED,
                              "Mofid read_only: فقط GETِ allowlist مجاز است — "
                              "هیچ درخواستی ساخته نشد")
        if not self.live:
            raise BrokerError(ErrorCode.UNSUPPORTED,
                              "Mofid: ترافیک/نشست وصل نیست — هیچ درخواستی ساخته نشد")
        self.wire_calls.append("%s:%s" % (tag, method))
        hdrs = self._headers(extra_headers)
        if payload is not None:
            hdrs["Content-Type"] = "application/json"
        t0 = time.monotonic()
        try:
            resp = self._transport.request(method=method, url=url, headers=hdrs,
                                           payload=payload,
                                           timeout_s=self.timeout_s if timeout_s is None
                                           else timeout_s)
        except (TransportTimeout, TransportNetwork, TransportRefused) as e:
            self.redacted_log.append({"tag": tag, "method": method, "url": url,
                                      "error": type(e).__name__})
            raise BrokerError(ErrorCode.UNKNOWN_RESULT,
                              "Mofid: پاسخ نیامد/شبکه — نتیجه نامعلوم؛ retry ممنوع") from None
        entry: dict[str, Any] = {"tag": tag, "method": method, "url": url,
                                 "status": resp.status,
                                 "elapsed_ms": round((time.monotonic() - t0) * 1000, 1)}
        if log_body:
            entry["body_head"] = (resp.body or "")[:120]
        self.redacted_log.append(entry)
        return resp

    def _read(self, url: str, *, tag: str) -> tuple[int, Any]:
        """GETِ فقط‌خواندنی؛ 401/403 نشست را جدا می‌کند و بدنه در لاگ نمی‌نشیند."""
        resp = self._call("GET", url, tag=tag)
        if resp.status in (401, 403):
            state = (SessionState.EXPIRED if resp.status == 401
                     else SessionState.AUTH_FAILED)
            self._verified_token = None
            self.session_proof = {}
            self._status_cache = None
            self._session = SessionStatus(state, checked_at=self._iso())
            raise BrokerError(
                ErrorCode.SESSION_EXPIRED if resp.status == 401
                else ErrorCode.AUTH_FAILED,
                "Mofid: HTTP %d — نشست پذیرفته نشد" % resp.status)
        if not (200 <= resp.status < 300):
            return resp.status, None
        try:
            return resp.status, json.loads(resp.body or "")
        except (TypeError, ValueError):
            raise BrokerError(ErrorCode.UNKNOWN_RESULT,
                              "Mofid %s: پاسخ JSON نبود" % tag) from None

    def _mark_connected(self, path: str) -> None:
        self._verified_token = self._token
        self.session_proof = {"path": path, "status": 200,
                              "kind": "first-party-read-only",
                              "note": "پاسخ 2xx از مسیرِ مشاهده‌شده در بستهٔ Titan"}
        self._session = SessionStatus(SessionState.CONNECTED, "mofid", self._iso())

    def session_status(self) -> SessionStatus:
        return self._session

    def session_proven(self) -> bool:
        """حضورِ رشته کافی نیست؛ همان token باید با یک GET تأیید شده باشد."""
        return bool(self._verified_token is not None
                    and self._token is self._verified_token)

    def _customer_status(self, *, fresh: bool = True) -> Mapping[str, Any]:
        if not fresh and self._status_cache is not None:
            age = time.monotonic() - self._status_cache[0]
            if age <= 5.0 and isinstance(self._status_cache[1], Mapping):
                return self._status_cache[1]
        status, payload = self._read(URL_CUSTOMER_STATUS, tag="customer_status")
        if not (200 <= status < 300):
            self._status_cache = None
            if status >= 500:
                self._session = SessionStatus(SessionState.ERROR, checked_at=self._iso())
            raise BrokerError(ErrorCode.UNKNOWN_RESULT,
                              "Mofid customer/status: HTTP %d" % status)
        data = _data_envelope(payload)
        if not isinstance(data, Mapping):
            self._status_cache = None
            self._session = SessionStatus(SessionState.ERROR, checked_at=self._iso())
            raise BrokerError(ErrorCode.UNKNOWN_RESULT,
                              "Mofid customer/status: پاسخ شیء نبود — چیزی ثابت نمی‌کند")
        self._mark_connected(WIRE_PATH_CUSTOMER_STATUS)
        self._status_cache = (time.monotonic(), dict(data))
        return data

    def authenticate(self) -> SessionStatus:
        """نشست با GETِ وضعیتِ مشتری تأیید می‌شود؛ هیچ سفارشی ping نیست."""
        if not self.live:
            self._session = SessionStatus(SessionState.DISCONNECTED,
                                          checked_at=self._iso())
            raise BrokerError(ErrorCode.UNSUPPORTED,
                              "Mofid: transport یا دسترسی در حافظه نیست")
        try:
            self._customer_status(fresh=True)
        except BrokerError:
            if self._session.state is SessionState.UNKNOWN:
                self._session = SessionStatus(SessionState.ERROR,
                                              checked_at=self._iso())
            raise
        return self._session

    # ---- حساب -------------------------------------------------------------
    def get_money(self) -> dict[str, Any]:
        """قدرتِ خرید/مانده؛ فقط فیلدهایِ نام‌دارِ همان پاسخ، بی‌فرمولِ اختراعی.

        درِ Round 17 واقعی: `customer/status` این حساب `purchasingPower` نداشت.
        بستهٔ اول‌طرف همان فیلد را در `/Accounting/Remain` (web V4) می‌خواند؛
        این fallback فقط GET و همان توکن است. اگر هیچ‌کدام فیلد را نداشتند،
        فقط **نامِ کلیدها** (نه مقدار) برایِ تشخیص گزارش می‌شود.
        """
        data = self._customer_status(fresh=False)
        source_path = WIRE_PATH_CUSTOMER_STATUS
        fields = ("purchasingPower", "accountBalanceT2", "accountBalanceT1",
                  "blockedBalance", "credit", "marginBlock")
        raw = {k: _num(data.get(k)) for k in fields if data.get(k) is not None}
        buying = raw.get("purchasingPower")
        if buying is None:
            try:
                status, payload = self._read(URL_ACCOUNTING_REMAIN,
                                             tag="accounting_remain")
            except BrokerError:
                raise
            if 200 <= status < 300:
                alt = _data_envelope(payload)
                if isinstance(alt, Mapping):
                    alt_raw = {k: _num(alt.get(k)) for k in fields
                               if alt.get(k) is not None}
                    if alt_raw.get("purchasingPower") is not None:
                        data, raw = alt, alt_raw
                        buying = raw["purchasingPower"]
                        source_path = WIRE_PATH_ACCOUNTING_REMAIN
        if buying is None:
            keys = ",".join(sorted(str(k) for k in data.keys())[:40])
            raise BrokerError(
                ErrorCode.UNKNOWN_RESULT,
                "Mofid: purchasingPower در customer/status و Accounting/Remain "
                "نبود — کلیدها: %s" % (keys or "—"))
        server_ts = _find_timestamp(data)
        return {"raw": raw, "buying_power": buying,
                "cash": raw.get("accountBalanceT2"),
                "blocked": raw.get("blockedBalance"),
                "credit": raw.get("credit"),
                "margin_block": raw.get("marginBlock"),
                "unit": UNIT, "unit_evidence": UNIT_EVIDENCE,
                "unit_state": UNIT_VERIFICATION["state"],
                "precision": UNIT_VERIFICATION["precision"],
                "unit_server_field": UNIT_VERIFICATION["server_unit_field"],
                "formula": "purchasingPower",
                "source": "mofid:%s (first-party Titan client)" % source_path,
                "response_keys": sorted(str(k) for k in data.keys()),
                "server_timestamp": server_ts,
                "freshness": ("SERVER_FIELD_RAW_UNVERIFIED" if server_ts
                              else "LOCAL_FETCH_ONLY"),
                "contract": CONTRACT_STATE, "fetched_at": self._iso()}

    def get_balances(self) -> Mapping[str, Any]:
        money = self.get_money()
        return {"cash": money["cash"], "settled_cash_t2": money["cash"],
                "buying_power": money["buying_power"],
                "blocked": money["blocked"], "credit": money["credit"],
                "margin_block": money["margin_block"],
                "unit": money["unit"], "source": money["source"],
                "formula": money["formula"], "verified": True,
                "contract": CONTRACT_STATE, "fetched_at": money["fetched_at"]}

    def get_positions(self) -> list[dict[str, Any]]:
        """پرتفویِ روزانه؛ sellable یک کرانِ محافظه‌کارانه است، نه عددِ کارگزار."""
        status, payload = self._read(URL_PORTFOLIO_DAILY, tag="portfolio")
        if not (200 <= status < 300):
            raise BrokerError(ErrorCode.UNKNOWN_RESULT,
                              "Mofid Portfolio/Daily: HTTP %d" % status)
        data = _data_envelope(payload)
        if not isinstance(data, list):
            raise BrokerError(ErrorCode.UNKNOWN_RESULT,
                              "Mofid Portfolio/Daily: پاسخ فهرست نبود")
        rows: list[dict[str, Any]] = []
        for it in data:
            if not isinstance(it, Mapping):
                continue
            isin = _text(it.get("symbolIsin"))
            current = _num(it.get("currentAsset"))
            bought = _num(it.get("todayBoughtAsset"))
            sold = _num(it.get("todaySoldAsset"))
            open_sell = _num(it.get("openSellOrders"))
            settled = (current + sold - bought if None not in (current, bought, sold)
                       else None)
            sellable = None
            if None not in (current, settled, open_sell):
                sellable = max(0.0, min(current, settled) - open_sell)
            rows.append({
                "isin": isin,
                "symbol": _text(it.get("symbolName")),
                "current_asset": current,
                "today_bought": bought,
                "today_sold": sold,
                "open_buy": _num(it.get("openBuyOrders")),
                "open_sell": open_sell,
                "settled": settled,
                "sellable": sellable,
                "sellable_state": (SELLABLE_STATE if sellable is not None
                                   else "UNAVAILABLE_FIELDS"),
                "average_buy": _num(it.get("averageBuyPrice")),
                "average_sell": _num(it.get("averageSellPrice")),
                "break_even": _num(it.get("breakEvenPrice")),
                "today_buy_average": _num(it.get("todayBuyAveragePrice")),
                "today_sell_average": _num(it.get("todaySellAveragePrice")),
                "server_timestamp": _find_timestamp(it),
                "source": "mofid:%s" % WIRE_PATH_PORTFOLIO_DAILY,
            })
        return rows

    def sellable_provenance(self) -> dict[str, Any]:
        return {"state": SELLABLE_STATE, "formula": SELLABLE_FORMULA,
                "source": "mofid:%s" % WIRE_PATH_PORTFOLIO_DAILY,
                "note": "کرانِ محافظه‌کارانه از فیلدهایِ پرتفوی؛ عددِ اعلامیِ کارگزار نیست"}

    def get_sellable_quantity(self, isin: str | None = None) -> float | None:
        want = str(isin or "").strip().upper()
        if not want:
            return None
        rows = [r for r in self.get_positions()
                if str(r.get("isin") or "").strip().upper() == want]
        if not rows:
            return 0.0
        values = {float(r["sellable"]) for r in rows if r.get("sellable") is not None}
        if len(values) > 1:
            raise BrokerError(ErrorCode.UNKNOWN_RESULT,
                              "Mofid: چند ردیفِ ناهمخوان برایِ یک ISIN — sellable مبهم")
        if not values:
            raise BrokerError(ErrorCode.UNKNOWN_RESULT,
                              "Mofid: فیلدهایِ پرتفوی برایِ sellable کامل نبود")
        return values.pop()

    # ---- سفارش‌ها ----------------------------------------------------------
    def _record_from_row(self, row: Mapping[str, Any],
                         *, execution_id: str = "") -> ExecutionRecord:
        qty = _num(row.get("quantity"))
        filled = _num(row.get("executedQuantity"))
        raw_side = _text(row.get("orderSide"))
        side = (Side.SELL if str(raw_side or "").lower() == "sell"
                else Side.BUY if str(raw_side or "").lower() == "buy"
                else Side.BUY)
        rec = ExecutionRecord(
            execution_id=execution_id, broker=ADAPTER_NAME, account=None,
            symbol=_text(row.get("symbol")) or (_text(row.get("symbolIsin")) or ""),
            isin=_text(row.get("symbolIsin")), side=side,
            price=_num(row.get("orderPrice")), quantity=qty,
            mode=OrderMode.SAFE, status=ExecutionStatus.UNKNOWN_RESULT,
            broker_order_id=_text(row.get("orderId")),
            order_state=map_order_state(
                row.get("orderState") or row.get("state") or row.get("orderStateName"),
                quantity=qty, executed=filled),
            filled_quantity=filled)
        if raw_side is None:
            rec.note("orderSide در ردیف نبود — جهتِ نمایشی تأیید نشده")
        if not execution_id:
            rec.note("ردیفِ کارگزار به قصدِ محلی وصل نشد — بی‌execution_id")
        # زمان‌ها خام می‌مانند: منطقهٔ زمانی/قالبِ عددی در پاسخِ واقعی دیده نشده.
        for key in ("orderDateTime", "validityDateTime", "tradeDateTime", "errorCodeId"):
            if row.get(key) not in (None, ""):
                rec.note("%s=%s" % (key, row.get(key)))
        return rec

    def _read_order_rows(self, url: str, *, tag: str) -> list[Mapping[str, Any]]:
        status, payload = self._read(url, tag=tag)
        if not (200 <= status < 300):
            raise BrokerError(ErrorCode.UNKNOWN_RESULT,
                              "Mofid %s: HTTP %d" % (tag, status))
        data = _data_envelope(payload)
        if isinstance(data, Mapping):
            data = data.get("records") if isinstance(data.get("records"), list) else None
        if not isinstance(data, list):
            raise BrokerError(ErrorCode.UNKNOWN_RESULT,
                              "Mofid %s: پاسخ فهرست نبود" % tag)
        return [r for r in data if isinstance(r, Mapping)]

    def _remember_ids(self, records: list[ExecutionRecord]) -> list[ExecutionRecord]:
        for rec in records:
            if rec.broker_order_id:
                self._known_order_ids.add(str(rec.broker_order_id))
        return records

    def get_orders(self) -> list[ExecutionRecord]:
        """سفارش‌هایِ باز؛ ردیفِ بی‌قصد با UNKNOWN می‌آید، نه «مالِ ما»."""
        return self._remember_ids([self._record_from_row(r)
                                   for r in self._read_order_rows(
                                       URL_OPEN_ORDERS, tag="open_orders")])

    def get_today_orders(self) -> list[ExecutionRecord]:
        return self._remember_ids([self._record_from_row(r)
                                   for r in self._read_order_rows(
                                       URL_TODAY_ORDER, tag="today_orders")])

    def get_order(self, broker_order_id: str) -> Optional[ExecutionRecord]:
        """state/detail فقط با شناسهٔ صریح؛ 404 یعنی «دیده شد و نبود»، 5xx یعنی نامعلوم."""
        oid = str(broker_order_id or "").strip()
        if not oid:
            return None
        if not _ORDER_ID_RE.fullmatch(oid):
            raise BrokerError(ErrorCode.UNSUPPORTED,
                              "Mofid: شناسهٔ سفارش نامعتبر است — درخواستی ساخته نشد")
        if self._read_only and oid not in self._known_order_ids:
            raise BrokerError(ErrorCode.UNSUPPORTED,
                              "Mofid read_only: شناسه از فهرستِ واقعیِ باز/امروز نیامده "
                              "— درخواستِ حدسی ممنوع")
        status, payload = self._read(
            WIRE_GATEWAY_V1 + WIRE_PATH_ORDER_DETAIL + oid, tag="order_detail")
        if status == 404:
            status, payload = self._read(
                WIRE_GATEWAY_V1 + WIRE_PATH_ORDER_STATE + oid, tag="order_state")
            if status == 404:
                return None
        if not (200 <= status < 300):
            raise BrokerError(ErrorCode.UNKNOWN_RESULT,
                              "Mofid order %s: HTTP %d" % (oid, status))
        data = _data_envelope(payload)
        if isinstance(data, str):
            row: Mapping[str, Any] = {"orderId": oid, "orderState": data}
        elif isinstance(data, Mapping):
            row = data
        else:
            return None
        rec = self._record_from_row(row)
        rec.broker_order_id = _text(row.get("orderId")) or oid
        return rec

    def get_queue_position(self, broker_order_id: str) -> None:
        # مسیرِ صف در بستهٔ Titan دیده نشد؛ None یعنی UNKNOWN، نه «اولِ صف».
        return None

    def cancel(self, broker_order_id: str) -> None:
        raise BrokerError(ErrorCode.UNSUPPORTED,
                          "لغو در این آداپتور پیاده نشده؛ هیچ درخواستی ساخته نشد")

    # ---- نوشتن ------------------------------------------------------------
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
        if self._read_only:
            self.wire_calls.append("submit:REFUSED_READ_ONLY")
            raise BrokerError(ErrorCode.UNSUPPORTED,
                              "Mofid read_only: ارسالِ سفارش در این حالت ممنوع است")
        if not self.writes_allowed:
            self.wire_calls.append("submit:REFUSED")
            raise BrokerError(ErrorCode.UNSUPPORTED,
                              "Mofid: live/writes gate بسته است؛ هیچ درخواستی ساخته نشد")
        payload = build_payload(draft)
        resp: WireResponse = self._call(
            "POST", self.order_url, tag="send", payload=payload,
            extra_headers={"Referer": WIRE_ORIGIN + "/", "Origin": WIRE_ORIGIN})
        if resp.status in (401, 403):
            self._verified_token = None
            self.session_proof = {}
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

    # ---- شاهد --------------------------------------------------------------
    def readiness_evidence(self) -> dict[str, Any]:
        """آنچه ثابت شده و آنچه نشده — UI بی‌این، mock را واقعی می‌خواند."""
        return {
            "contract": CONTRACT_STATE,
            "provenance": CONTRACT_PROVENANCE,
            "session": {"proven": self.session_proven(),
                        "state": self._session.state.value,
                        "checked_at": self._session.checked_at,
                        "verified_by": dict(self.session_proof)},
            "read_only": {"status": CONTRACT_STATE,
                          "paths": [WIRE_PATH_CUSTOMER_STATUS,
                                    WIRE_PATH_ACCOUNTING_REMAIN,
                                    WIRE_PATH_PORTFOLIO_DAILY,
                                    WIRE_PATH_OPEN_ORDERS,
                                    WIRE_PATH_ORDER_STATE + "{orderId}",
                                    WIRE_PATH_ORDER_DETAIL + "{orderId}"]},
            "read_only": {"status": "ENFORCED" if self._read_only else "OFF",
                          "allowlist": [WIRE_PATH_CUSTOMER_STATUS,
                                        WIRE_PATH_PORTFOLIO_DAILY,
                                        WIRE_PATH_OPEN_ORDERS,
                                        WIRE_PATH_TODAY_ORDER,
                                        WIRE_PATH_ORDER_STATE + "{orderId}",
                                        WIRE_PATH_ORDER_DETAIL + "{orderId}"]},
            "write": {"status": WRITE_STATE,
                      "detail": "پاسخِ واقعیِ ثبت/read-back در این ماشین دیده نشده"},
            "sellable": self.sellable_provenance(),
            "unit": {"value": UNIT, "state": UNIT_VERIFICATION["state"],
                     "precision": UNIT_VERIFICATION["precision"],
                     "server_unit_field": UNIT_VERIFICATION["server_unit_field"],
                     "evidence": UNIT_EVIDENCE},
            "position_fields": dict(POSITION_FIELD_MAP),
            "order_contract": dict(ORDER_CONTRACT),
            "freshness_policy": "only a named server timestamp is reported; "
                                "fetched_at is local and never becomes server time",
            "live_verified": False,
        }

    def _iso(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S")


__all__ = [
    "ADAPTER_NAME", "WIRE_URL", "WIRE_BASE_URL", "WIRE_ORIGIN", "MOFID_LOGIN_URL",
    "WIRE_GATEWAY_V1", "WIRE_GATEWAY_V2", "WIRE_WEB_V4", "WIRE_PATH_ORDER_CREATE",
    "WIRE_PATH_CUSTOMER_STATUS", "WIRE_PATH_PORTFOLIO_DAILY",
    "WIRE_PATH_OPEN_ORDERS", "WIRE_PATH_TODAY_ORDER", "WIRE_PATH_ORDER_STATE",
    "WIRE_PATH_ORDER_DETAIL", "WIRE_PATH_ACCOUNTING_REMAIN",
    "CONTRACT_STATE", "CONTRACT_PROVENANCE", "SELLABLE_FORMULA", "SELLABLE_STATE",
    "UNIT", "UNIT_VERIFICATION", "POSITION_FIELD_MAP", "ORDER_CONTRACT",
    "MofidAdapter", "build_payload", "authorization_value", "map_order_state",
]
