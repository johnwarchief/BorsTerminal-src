# -*- coding: utf-8 -*-
"""execution_write_contract.py — قراردادِ *بازسازی‌شدهٔ* ثبت سفارشِ EasyTrader.

منبعِ اصلی، کدِ خودِ وب‌اپِ اول‌طرفی است (bundle `main-XW5OZAYT.js`، نشستِ
مشاهده‌شدهٔ ۲۰۲۶-۱۰-۲۱):

  ``createOrder(e)``
      ``httpService.post(this.orderUrl + 'v2/order', {body: {order: e}})``
  ``orderUrl = mtsPath + apiUrls.oms`` و ``apiUrls.oms = 'core/api/'``

و سازندهٔ بدنه در همان کلاینت، ``generateOrderForSubmission`` و سپس
``prepareSendingOrder`` است. این فایل فقط همان شواهد را کد می‌کند؛ هیچ درخواستِ
واقعی نمی‌زند و ادعایِ «تأییدِ عملیاتی» ندارد.

سطحِ قطعیت: ``WRITE_CONTRACT_STATICALLY_RECONSTRUCTED``. پاسخِ موفقِ HTTP
یعنی «درخواست ثبت شد»، نه «سفارش پذیرفته/اجرا شد»؛ وضعیتِ واقعی فقط از
``GET /core/api/order`` و رویدادهایِ OMS می‌آید.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from execution_contract import OrderDraft, Side

ENDPOINT = "/core/api/v2/order"
METHOD = "POST"
ENVELOPE_KEY = "order"
CONTRACT_STATE = "WRITE_CONTRACT_STATICALLY_RECONSTRUCTED"
PROVENANCE = ("first-party web app: main-XW5OZAYT.js → createOrder() → "
              "POST core/api/v2/order with {order}; observed 2026-10-21")

SIDE_BUY = 0
SIDE_SELL = 1
SIDE_NONE = 3
ORDER_MODEL_OMS = 1
ORDER_FROM_STOCK_DESKTOP = 34
ORDER_FROM_STOCK_MOBILE = 33
VALIDITY_DAY = 0
VALIDITY_VALID_TO_DATE = 1
VALIDITY_VALID_TO_CANCELLATION = 2
VALIDITY_EXECUTE_AND_REMOVE = 3
VALIDITY_WEEK = 5
VALIDITY_MONTH = 6
VALIDITY_SHARED_DUE_DATE = 99

#: فیلدهایی که کلاینتِ اول‌طرفی هم می‌فرستد، ولی معنایِ سرورشان برایِ ما
#: اثبات نشده است. عمداً تا وقتی مقدارِ قابل‌دفاع نداریم فرستاده نمی‌شوند.
OPTIONAL_CLIENT_SUMMARY = ("commission", "totalValue")

FIELDS: tuple[dict[str, Any], ...] = (
    {"name": "symbolIsin", "type": "string", "required": True,
     "confidence": "first-party client + observed read-only ISIN mapping",
     "note": "ISINِ ابزار؛ نه ins_code و نه نمادِ نمایشی"},
    {"name": "symbolName", "type": "string", "required": True,
     "confidence": "first-party client", "note": "برچسبِ نمایشیِ سفارش"},
    {"name": "price", "type": "number", "required": True,
     "confidence": "first-party client", "note": "قیمتِ واحدِ نمایشی (ریال)"},
    {"name": "quantity", "type": "number", "required": True,
     "confidence": "first-party client", "note": "تعدادِ سهم؛ عددِ مثبت"},
    {"name": "side", "type": "integer", "required": True,
     "confidence": "first-party client enum", "note": "0=خرید، 1=فروش"},
    {"name": "validityType", "type": "integer", "required": True,
     "confidence": "first-party client enum", "note": "0=روز؛ مقادیرِ دیگر 5/6/1/2/3/99"},
    {"name": "validityDate", "type": "string", "required": False,
     "confidence": "first-party client conditional", "note": "برایِ اعتبارِ تاریخ‌دار"},
    {"name": "orderModelType", "type": "integer", "required": True,
     "confidence": "first-party client enum", "note": "1=oms"},
    {"name": "orderFrom", "type": "integer", "required": True,
     "confidence": "first-party client enum", "note": "34=OrbisDesktop برایِ سهام"},
    {"name": "createDateTime", "type": "string", "required": True,
     "confidence": "first-party client; locale format", "note": "برچسبِ محلیِ کلاینت"},
    {"name": "commission", "type": "number", "required": False,
     "confidence": "client summary; server semantics UNVERIFIED",
     "note": "فرستاده می‌شود اگر منبعِ تأییدشده بدهد؛ وگرنه حذف"},
    {"name": "totalValue", "type": "number", "required": False,
     "confidence": "client summary; server semantics UNVERIFIED",
     "note": "جمعِ نمایشی؛ با نبودِ کارمزدِ تأییدشده حذف می‌شود"},
    {"name": "id", "type": "string", "required": False,
     "confidence": "create: omitted; edit: form id",
     "note": "برایِ سفارشِ تازه شناخته‌شده نیست؛ عمداً حذف می‌شود"},
)

RESPONSE_FIELDS = (
    {"name": "isSuccessful", "type": "boolean", "note": "true = درخواست ثبت شد"},
    {"name": "id", "type": "string", "note": "شناسهٔ سفارش"},
    {"name": "message", "type": "string", "note": "پیامِ خطا/وضعیت"},
    {"name": "omsError", "type": "array", "note": "خطاهایِ OMS در رد"},
)


def _side_value(side: Side) -> int:
    return SIDE_BUY if side is Side.BUY else SIDE_SELL


def build_order(draft: OrderDraft, *, created_at: str,
                validity_type: int = VALIDITY_DAY,
                validity_date: str | None = None,
                order_from: int = ORDER_FROM_STOCK_DESKTOP,
                commission: float | None = None,
                total_value: float | None = None) -> dict[str, Any]:
    """بدنهٔ *داخلیِ* درخواست؛ فیلدهایِ نامعلوم حذف می‌شوند، نه صفر."""
    inner: dict[str, Any] = {
        "symbolIsin": (draft.instrument.isin or "").strip(),
        "symbolName": draft.instrument.symbol,
        "price": draft.price,
        "quantity": draft.quantity,
        "side": _side_value(draft.side),
        "validityType": int(validity_type),
        "orderModelType": ORDER_MODEL_OMS,
        "orderFrom": int(order_from),
        "createDateTime": created_at,
    }
    if validity_date is not None:
        inner["validityDate"] = str(validity_date)
    if commission is not None:
        inner["commission"] = float(commission)
    if total_value is not None:
        inner["totalValue"] = float(total_value)
    return inner


def build_payload(draft: OrderDraft, **kw: Any) -> dict[str, Any]:
    return {ENVELOPE_KEY: build_order(draft, **kw)}


def structural_errors(payload: Mapping[str, Any]) -> list[str]:
    """خطاهایِ ساختاری — قبل از هر ارسال؛ دقیقاً همان فیلدها را نام می‌برد."""
    errs: list[str] = []
    inner = payload.get(ENVELOPE_KEY)
    if not isinstance(inner, Mapping):
        return ["ENVELOPE"]
    if not str(inner.get("symbolIsin") or "").strip():
        errs.append("symbolIsin")
    if not str(inner.get("symbolName") or "").strip():
        errs.append("symbolName")
    try:
        if float(inner.get("price") or 0) <= 0:
            errs.append("price")
    except (TypeError, ValueError):
        errs.append("price")
    try:
        if float(inner.get("quantity") or 0) <= 0:
            errs.append("quantity")
    except (TypeError, ValueError):
        errs.append("quantity")
    if inner.get("side") not in (SIDE_BUY, SIDE_SELL):
        errs.append("side")
    if inner.get("orderModelType") != ORDER_MODEL_OMS:
        errs.append("orderModelType")
    if inner.get("orderFrom") not in (ORDER_FROM_STOCK_DESKTOP,
                                      ORDER_FROM_STOCK_MOBILE,
                                      110, 111):
        errs.append("orderFrom")
    if not isinstance(inner.get("validityType"), int):
        errs.append("validityType")
    if not str(inner.get("createDateTime") or "").strip():
        errs.append("createDateTime")
    return errs


def contract_report() -> dict[str, Any]:
    """گزارشِ قابلِ‌نمایش؛ بی‌هیچ secret و بی‌ادعایِ تأییدِ عملیاتی."""
    return {
        "state": CONTRACT_STATE,
        "method": METHOD,
        "endpoint": ENDPOINT,
        "envelope": ENVELOPE_KEY,
        "provenance": PROVENANCE,
        "operationally_verified": False,
        "response_semantics": {
            "http_2xx_is_not_acceptance": True,
            "success_means": "request registered; order state must be read back",
            "read_back": "GET /core/api/order",
            "fields": [dict(x) for x in RESPONSE_FIELDS],
        },
        "fields": [dict(x) for x in FIELDS],
        "optional_client_summary": list(OPTIONAL_CLIENT_SUMMARY),
        "limitations": [
            "commission/totalValue client-side semantics unverified; omitted without a proven source",
            "validityDate for Day omitted; other validity types not executed",
            "server acceptance/fill/cancel semantics need an owner-approved live test",
        ],
    }


__all__ = [
    "CONTRACT_STATE", "ENDPOINT", "METHOD", "ENVELOPE_KEY", "PROVENANCE",
    "SIDE_BUY", "SIDE_SELL", "ORDER_MODEL_OMS", "ORDER_FROM_STOCK_DESKTOP",
    "VALIDITY_DAY", "VALIDITY_VALID_TO_DATE", "VALIDITY_WEEK", "VALIDITY_MONTH",
    "VALIDITY_SHARED_DUE_DATE", "FIELDS", "RESPONSE_FIELDS",
    "build_order", "build_payload", "structural_errors", "contract_report",
]
