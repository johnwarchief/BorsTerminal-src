#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/execution_write_contract_v1147.py — قرارداد بازسازی‌شده + دروازهٔ آمادگی.

هیچ شبکه‌ای زده نمی‌شود و هیچ سفارشی به کارگزاری نمی‌رود. این گارد:
  • بدنۀ `{order:{…}}` را با فیلدهایِ کدِ اول‌طرفی می‌سنجد (نه حدس)،
  • 2xx را فقط «ثبتِ درخواست» می‌داند و retryِ کور را ممنوع می‌سنجد،
  • read-only را پیش از هر POST رد می‌کند،
  • تفکیکِ «داده/ریسک آماده» از «نوشتن مسدود» را در readiness می‌سنجد.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import execution_easytrader as ET  # noqa: E402
import execution_readiness as RD  # noqa: E402
import execution_write_contract as WC  # noqa: E402
from execution_contract import (  # noqa: E402
    BrokerError, Capabilities, ErrorCode, ExecutionStatus, InstrumentRef,
    OrderDraft, OrderState, Resolution, Side,
)

PASS = FAIL = 0
FAILED: list[str] = []
TOKEN = "round11-contract-token-never-printed"


def ck(ok, label, extra=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  ok   %s" % label)
    else:
        FAIL += 1
        FAILED.append(label)
        print("  FAIL %s -> %r" % (label, extra))


def ref() -> InstrumentRef:
    return InstrumentRef(symbol="فولاد", ins_code="1", isin="IRO1FOLD0001",
                         broker_instrument="IRO1FOLD0001",
                         resolution=Resolution.EXACT)


def draft(side=Side.BUY, price=1000.0, qty=10.0) -> OrderDraft:
    return OrderDraft(execution_id="r11-%s-%s" % (side.value, price),
                      instrument=ref(), side=side, price=price, quantity=qty,
                      price_source="readiness-test")


class Fake:
    name = "r11-scripted"
    is_live = True

    def __init__(self, *, post=None, auth=200):
        self.calls = []
        self.post = post if post is not None else {
            "status": 200, "body": json.dumps({"isSuccessful": True, "id": "R11-ORD"})}
        self.auth = auth

    def request(self, *, method, url, headers, payload=None, timeout_s=7.0):
        import execution_easytrader as E
        path = url.replace(E.WIRE_BASE_URL, "")
        self.calls.append((method, path, payload))
        if method == "GET":
            if self.auth != 200:
                return E.WireResponse(self.auth, {}, json.dumps({"isSuccessful": False}))
            return E.WireResponse(200, {}, json.dumps({
                "orders": [], "algoSuffixCharacters": "!@^()-+="}))
        return E.WireResponse(int(self.post["status"]), {}, self.post["body"])


def test_payload():
    print("\n── ۱) بدنۀِ قرارداد: فیلدها، enumها، فیلدهایِ حذف‌شده ──")
    p = ET.easytrader_payload(draft())
    inner = p.get("order") or {}
    ck(list(p.keys()) == [WC.ENVELOPE_KEY], "پاکت فقط {order}", list(p))
    ck(inner.get("symbolIsin") == "IRO1FOLD0001", "ISIN است، نه ins_code")
    ck(inner.get("side") == WC.SIDE_BUY and
       ET.easytrader_payload(draft(Side.SELL))["order"]["side"] == WC.SIDE_SELL,
       "جهت: ۰=خرید، ۱=فروش")
    ck(inner.get("orderModelType") == WC.ORDER_MODEL_OMS and
       inner.get("orderFrom") == WC.ORDER_FROM_STOCK_DESKTOP and
       inner.get("validityType") == WC.VALIDITY_DAY,
       "orderModelType/orderFrom/validityType ازِ enumِ اول‌طرفی")
    ck("commission" not in inner and "totalValue" not in inner,
       "فیلدهایِ client-summaryِ بی‌منبع حذف شده‌اند، نه صفر")
    ck(inner.get("validityDate") is None, "validityDate برایِ Day حذف شده")
    ck(not WC.structural_errors(p), "بدنۀِ معتبر خطایِ ساختاری ندارد")
    ck(set(WC.structural_errors({"order": {"side": 0}})) >=
       {"symbolIsin", "price", "quantity", "createDateTime"},
       "بدنۀِ ناقص، دقیقاً فیلدهایِ غایب را نام می‌برد")
    p2 = ET.easytrader_payload(draft(), validity_type=WC.VALIDITY_VALID_TO_DATE,
                               validity_date="2026-10-22", commission=0.0,
                               total_value=10000.0)
    ck(p2["order"].get("validityDate") == "2026-10-22"
       and p2["order"].get("commission") == 0.0
       and p2["order"].get("totalValue") == 10000.0,
       "فیلدهایِ اختیاری فقط با مقدارِ صریح اضافه می‌شوند")
    rep = WC.contract_report()
    ck(rep["state"] == WC.CONTRACT_STATE and rep["operationally_verified"] is False
       and rep["endpoint"] == "/core/api/v2/order",
       "گزارشِ قرارداد: بازسازی‌شده، نه عملیاتی")
    ck(any(f["name"] == "side" and "enum" in f["confidence"] for f in rep["fields"]),
       "فیلد side با منبع/قطعیت ثبت شده")
    # مقایسهٔ متنی با دو مرجعِ اول‌طرفی‌نزدیک (فقط فیلدهایِ الزامی؛ کپیِ کد نشده)
    mfazel = {"price", "quantity", "side", "validityType", "symbolIsin",
              "orderModelType", "orderFrom"}
    reza = mfazel | {"symbolName", "createDateTime"}
    ck(mfazel <= set(inner), "همهٔ فیلدهایِ الزامیِ m-fazel در بدنۀ ما هست", mfazel - set(inner))
    ck(reza <= set(inner), "همهٔ فیلدهایِ الزامیِ Reza در بدنۀ ما هست", reza - set(inner))
    ck("commission" not in inner and "totalValue" not in inner,
       "اختلافِ آگاهانه: client-summaryها تا شاهدِ سرور حذف‌اند")


def test_semantics():
    print("\n── ۲) 2xx = ثبتِ درخواست، نه پذیرش؛ بی‌retry کور ──")
    tr = Fake()
    ad = ET.EasyTraderAdapter(transport=tr, token=TOKEN,
                              instruments=(ref(),), writes_allowed=True)
    rec = ad.submit_order(draft())
    ck(tr.calls[-1][0] == "POST" and tr.calls[-1][1] == WC.ENDPOINT,
       "POST فقط به مسیرِ قرارداد می‌رود", tr.calls[-1][:2])
    sent = tr.calls[-1][2]
    ck(isinstance(sent, dict) and sent.get("order", {}).get("symbolIsin") == "IRO1FOLD0001",
       "بدنۀِ همان {order:{…}} رویِ سیم است", sent)
    ck(rec.status is ExecutionStatus.ACKNOWLEDGED and rec.broker_order_id == "R11-ORD"
       and any("request registered" in n for n in rec.events),
       "رکورد: ACKNOWLEDGED + شناسه، با یادداشتِ «فقط ثبت شد»", rec.status)
    ck(getattr(ad.last_verdict, "request_registered", False) is True
       and ad.last_verdict.accepted is True,
       "verdict: request_registered=true؛ acceptance ادعا نمی‌شود")
    ck(rec.order_state is OrderState.UNKNOWN,
       "وضعیتِ سفارش از پاسخِ create ساخته نمی‌شود", rec.order_state)
    ck(TOKEN not in json.dumps(ad.redacted_log, ensure_ascii=False),
       "توکن در log نیست")

    b = Fake(post={"status": 200, "body": json.dumps({"id": "AMB-1"})})
    ad2 = ET.EasyTraderAdapter(transport=b, token=TOKEN,
                               instruments=(ref(),), writes_allowed=True)
    try:
        ad2.submit_order(draft())
        ck(False, "۲۰۰ بدون isSuccessful باید نامعلوم بماند")
    except BrokerError as e:
        ck(e.code is ErrorCode.UNKNOWN_RESULT and
           any(m == "POST" for m, _, _ in b.calls),
           "۲۰۰ بی‌flag ⇒ UNKNOWN_RESULT", e.code.value)
    try:
        ad2.submit_order(draft())
        ck(False, "تکرارِ همان execution_id باید رد شود")
    except BrokerError as e:
        ck(e.code is ErrorCode.DUPLICATE_GUARD and
           sum(1 for m, _, _ in b.calls if m == "POST") == 1,
           "تکرارِ قصد، POSTِ دوم نمی‌سازد", e.code.value)

    c = Fake(post={"status": 200, "body": json.dumps({
        "isSuccessful": False, "id": "REJ-1", "message": "Mx5:bad price"})})
    ad3 = ET.EasyTraderAdapter(transport=c, token=TOKEN,
                               instruments=(ref(),), writes_allowed=True)
    try:
        ad3.submit_order(draft())
        ck(False, "isSuccessful=false باید رد شود")
    except BrokerError as e:
        ck(e.code in (ErrorCode.BROKER_REJECTED, ErrorCode.INVALID_PRICE)
           and sum(1 for m, _, _ in c.calls if m == "POST") == 1,
           "ردِ صریح، یک POST و بی‌retry", e.code.value)

    rd_tr = Fake()
    ro = ET.EasyTraderAdapter(transport=rd_tr, token=TOKEN,
                              instruments=(ref(),), writes_allowed=False)
    try:
        ro.submit_order(draft())
        ck(False, "read-only نباید POST بسازد")
    except BrokerError as e:
        ck(e.code is ErrorCode.UNSUPPORTED and
           not any(m == "POST" for m, _, _ in rd_tr.calls),
           "read-only پیش از ترافیکِ نوشتن می‌ایستد", e.code.value)


def test_readiness():
    print("\n── ۳) readiness: داده/ریسک از نوشتن جدا ──")
    checks = {"instrument": "PASS", "side": "PASS", "price": "PASS",
              "quantity": "PASS", "session": "PASS", "balance": "PASS",
              "duplicate": "PASS", "kill_switch": "PASS", "place": "FAIL"}
    bp = {"state": "BUYING_POWER_VERIFIED", "value": 10_000_000, "unit": "IRR",
          "source": "fixture"}
    r = RD.build_readiness(session_proven=True, read_only=True, buying_power=bp,
                           symbol_ready=True, preflight_checks=checks)
    ck(r["data_risk_ready"] is True and r["live_ready"] is False,
       "داده/ریسک آماده، live_ready=false (نوشتن/قرارداد باز)", r)
    ck(any(g["id"] == "data_risk" and g["status"] == "PASS" for g in r["gates"]),
       "gate داده/ریسک بدونِ place سبز است")
    ck(any(g["id"] == "write_contract" and g["status"] == "UNVERIFIED"
           for g in r["gates"]), "قرارداد نوشتن UNVERIFIED است")
    ck(any(g["id"] == "owner_approval" and g["status"] == "REQUIRED"
           for g in r["gates"]), "مجوزِ مالک REQUIRED است")
    r2 = RD.build_readiness(session_proven=False, read_only=True, buying_power=None,
                            symbol_ready=None, preflight_checks=None)
    ck(r2["data_risk_ready"] is False and r2["live_ready"] is False,
       "بی‌نشست/بی‌قدرت‌خرید هیچ‌چیز سبز نیست", r2["next_action"])
    r3 = RD.build_readiness(session_proven=True, read_only=True, buying_power=bp,
                            symbol_ready=True, preflight_checks=checks,
                            contract_operational=True, owner_approved=True,
                            lifecycle_tests=True, full_gate=True)
    ck(r3["live_ready"] is True, "همهٔ شروطِ منطقی + مجوز ⇒ true (سنجشِ دروازه)")
    ck(r3["contract"]["operationally_verified"] is False,
       "پرچمِ readiness ادعایِ قرارداد را جعل نمی‌کند؛ ورودی صریح است")
    ck(not json.dumps(r, ensure_ascii=False).lower().count("bearer"),
       "گزارشِ readiness هیچ bearer ندارد")


def test_api():
    print("── ۴) درِ HTTP readiness: فقط‌خواندنی و بی‌ادعایِ live ──")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import api.execution as EX

    class ApiFake(Fake):
        def request(self, *, method, url, headers, payload=None, timeout_s=7.0):
            import execution_easytrader as E
            path = url.replace(E.WIRE_BASE_URL, "")
            self.calls.append((method, path, payload))
            if path == E.WIRE_PATH_MONEY:
                return E.WireResponse(200, {}, json.dumps({
                    "t0": 1000, "t2": 2000, "buyPowerT2": 5000,
                    "credit": 0, "avandCredit": 0}))
            if method == "GET":
                return E.WireResponse(200, {}, json.dumps({"orders": []}))
            return E.WireResponse(500, {}, "{}")

    old = (EX.ADAPTER_KIND, EX.TRAFFIC_ALLOWED, EX.READ_ONLY_REQUESTED,
           EX._ACTIVE_ADAPTER, EX._SERVICE)
    ad = ET.EasyTraderAdapter(transport=ApiFake(), token=TOKEN,
                              writes_allowed=False)
    ad.session_proven = lambda: True
    EX.ADAPTER_KIND = "easytrader"
    EX.TRAFFIC_ALLOWED = True
    EX.READ_ONLY_REQUESTED = True
    EX._ACTIVE_ADAPTER = ad
    from execution_service import ExecutionService
    EX._SERVICE = ExecutionService(ad, dry_run=True)
    try:
        app = FastAPI()
        app.include_router(EX.router)
        r = TestClient(app, base_url="http://127.0.0.1:8001").get(
            "/api/execution/readiness")
        d = r.json()
        ck(r.status_code == 200 and d.get("live_ready") is False
           and d.get("live_enabled") is False,
           "readiness: live_ready/live_enabled false", {k: d.get(k) for k in
                                                       ("status", "live_ready")})
        bp = next((g for g in d.get("gates", []) if g.get("id") == "buying_power"), {})
        ck(bp.get("status") == "PASS", "قدرت خرید از منبعِ فقط‌خواندنی درِ پاسخ سبز شد", bp)
        ck(d.get("contract", {}).get("operationally_verified") is False
           and d.get("contract", {}).get("endpoint") == WC.ENDPOINT,
           "قرارداد بازسازی‌شده درِ پاسخ است، نه ادعایِ عملیاتی")
        ck(not any(m == "POST" for m, _, _ in ad.transport.calls),
           "هیچ POST درِ این سنجش نرفت", ad.transport.calls)
    finally:
        (EX.ADAPTER_KIND, EX.TRAFFIC_ALLOWED, EX.READ_ONLY_REQUESTED,
         EX._ACTIVE_ADAPTER, EX._SERVICE) = old


def main() -> int:
    test_payload()
    test_semantics()
    test_readiness()
    test_api()
    print("\n%d passed / %d failed" % (PASS, FAIL))
    if FAILED:
        print("FAILED: " + ", ".join(FAILED))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
