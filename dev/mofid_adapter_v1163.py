#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mofid_adapter_v1163 — قراردادِ مستقلِ Mofid/Titan (بدونِ شبکه).

رفتارِ مرجع (`estakhri/Sarkhati@b63f55b src/mofid.rs`) فقط به‌عنوانِ شاهدِ شکلِ
سیم استفاده شد؛ منطقِ 2xx=acceptance و retry عمداً جایگزین شده‌اند.
"""
from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
PASS = FAIL = 0


def ck(cond, label, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("ok   " + label)
    else:
        FAIL += 1
        print("FAIL " + label + "  -> " + str(detail)[:260])


class ScriptTransport:
    name = "script"
    is_live = True

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, *, method, url, headers, payload=None, timeout_s=7.0):
        self.calls.append({"method": method, "url": url, "headers": dict(headers),
                           "payload": payload})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class RouteTransport:
    """پاسخ بر اساسِ زیررشتهٔ URL؛ ترتیبِ فراخوانی اهمیتی ندارد."""
    name = "route"
    is_live = True

    def __init__(self, routes):
        self.routes = dict(routes)
        self.calls = []

    def request(self, *, method, url, headers, payload=None, timeout_s=7.0):
        self.calls.append({"method": method, "url": url, "headers": dict(headers),
                           "payload": payload})
        for part, item in self.routes.items():
            if part in url:
                if isinstance(item, Exception):
                    raise item
                if callable(item):
                    return item(method, url, headers, payload)
                return item
        raise AssertionError("unrouted URL: %s" % url)


def main() -> int:
    from execution_contract import (
        ErrorCode, ExecutionStatus, InstrumentRef, OrderDraft, OrderMode,
        OrderState, Resolution, Side,
    )
    from execution_easytrader import TransportTimeout, WireResponse
    from execution_mofid import (
        SELLABLE_STATE, MofidAdapter, authorization_value, build_payload,
        map_order_state,
    )
    from execution_service import ExecutionService, Limits

    instr = InstrumentRef(symbol="TEST", ins_code="1", isin="IRO1TEST0001",
                          broker_instrument="IRO1TEST0001",
                          resolution=Resolution.EXACT)
    draft = OrderDraft(execution_id="M-1", instrument=instr, side=Side.BUY,
                       price=2474.0, quantity=1.0, mode=OrderMode.SAFE)
    payload = build_payload(draft)
    ck(payload == {"orderSide": "Buy", "price": 2474, "quantity": 1,
                   "symbolIsin": "IRO1TEST0001", "validityType": 0,
                   "validityDate": None, "orderFrom": "Titan"},
       "payloadِ تختِ Mofid مطابقِ قراردادِ مرجع است", payload)
    sell = OrderDraft("M-2", instr, Side.SELL, 1000.0, 2.0, OrderMode.SAFE)
    ck(build_payload(sell)["orderSide"] == "Sell", "فروش به Sell نگاشت می‌شود")

    tr = ScriptTransport(WireResponse(200, {}, '{"ok":true}'))
    ad = MofidAdapter(transport=tr, token="SECRET-TOKEN")
    ck(ad.live and ad.writes_allowed, "با ترافیک و token، live/writes روشن است")
    rec = ad.submit_order(draft)
    ck(rec.status is ExecutionStatus.UNKNOWN_RESULT
       and rec.order_state.value == "unknown"
       and rec.broker_order_id is None and len(tr.calls) == 1,
       "2xx ⇒ UNKNOWN، نه acceptance/order-id", rec)
    call = tr.calls[0]
    ck(call["method"] == "POST" and call["url"].endswith("/apigateway/api/v1/Order/send")
       and call["headers"].get("x-appname") == "titan"
       and call["payload"]["symbolIsin"] == "IRO1TEST0001",
       "متد/مسیر/هدر/ISIN درست است", call)
    ck("SECRET-TOKEN" not in repr(ad)
       and all("SECRET-TOKEN" not in str(x) for x in ad.redacted_log),
       "token در repr/لاگ نیست", ad.redacted_log)

    tr401 = ScriptTransport(WireResponse(401, {}, "{}"))
    try:
        MofidAdapter(transport=tr401, token="x").submit_order(draft)
        code = None
    except Exception as e:                       # noqa: BLE001
        code = getattr(e, "code", None)
    ck(code is ErrorCode.SESSION_EXPIRED, "401 ⇒ SESSION_EXPIRED", code)

    tr5 = ScriptTransport(WireResponse(503, {}, "{}"))
    r5 = MofidAdapter(transport=tr5, token="x").submit_order(draft)
    ck(r5.status is ExecutionStatus.UNKNOWN_RESULT, "5xx ⇒ UNKNOWN")

    trto = ScriptTransport(TransportTimeout("no answer"))
    try:
        MofidAdapter(transport=trto, token="x").submit_order(draft)
        to_code = None
    except Exception as e:                       # noqa: BLE001
        to_code = getattr(e, "code", None)
    ck(to_code is ErrorCode.UNKNOWN_RESULT and len(trto.calls) == 1,
       "timeout ⇒ UNKNOWN و بدونِ retry", {"code": to_code, "calls": len(trto.calls)})

    ad_off = MofidAdapter()
    ck(ad_off.capabilities().place is False and ad_off.capabilities().balances is False,
       "بی‌ترافیک ⇒ هیچ capability ادعا نمی‌شود")
    try:
        ad_off.submit_order(draft)
        refused = False
    except Exception:                            # noqa: BLE001
        refused = True
    ck(refused and not any(c.startswith("send:") for c in ad_off.wire_calls),
       "بی‌ترافیک ⇒ هیچ درخواستی ساخته نمی‌شود", ad_off.wire_calls)

    svc = ExecutionService(MofidAdapter(transport=ScriptTransport(), token="x"),
                           dry_run=False, limits=Limits())
    pf = svc.preflight(draft)
    ck(pf.ok is False and "balance" in pf.blocking,
       "preflightِ Mofid بی‌دادهٔ حساب fail-closed است", pf.checks.get("balance"))

    # ── Round 16: مسیرهایِ فقط‌خواندنیِ برگرفته از بستهٔ خودِ Titan ─────────
    long_tok = "T" * 48
    ck(authorization_value(long_tok) == "Bearer " + long_tok
       and authorization_value("short") == "Basic short"
       and authorization_value("Bearer x") == "Bearer x",
       "هدرِ Authorization مطابقِ قاعدهٔ کلاینتِ Titan است")

    status_body = ('{"data":{"purchasingPower":500000000,'
                   '"accountBalanceT2":400000000,"blockedBalance":10000000,'
                   '"credit":0,"marginBlock":0}}')
    rt = RouteTransport({
        "/Order/customer/status": WireResponse(200, {}, status_body),
        "/Portfolio/Daily": WireResponse(200, {}, (
            '{"data":[{"symbolIsin":"IRO1TEST0001","symbolName":"TEST",'
            '"currentAsset":1000,"todayBoughtAsset":200,"todaySoldAsset":100,'
            '"openSellOrders":50,"openBuyOrders":0,"averageBuyPrice":2000},'
            '{"symbolIsin":"IRO1OTHER001","symbolName":"OTHER",'
            '"currentAsset":10,"todayBoughtAsset":0,"todaySoldAsset":0,'
            '"openSellOrders":20}]}')),
        "/Order/open-orders": WireResponse(200, {}, (
            '{"data":[{"orderId":"O-1","symbol":"TEST","symbolIsin":"IRO1TEST0001",'
            '"orderSide":"Buy","orderPrice":2474,"quantity":10,'
            '"executedQuantity":4,"orderState":"PartiallyExecution"}]}')),
        "/Order/detail/O-1": WireResponse(200, {}, (
            '{"data":{"orderId":"O-1","orderState":"Done","quantity":10,'
            '"executedQuantity":10,"orderPrice":2474,"symbolIsin":"IRO1TEST0001"}}')),
        "/Order/detail/missing": WireResponse(404, {}, "{}"),
        "/Order/state/missing": WireResponse(404, {}, "{}"),
    })
    ad_ro = MofidAdapter(transport=rt, token=long_tok, writes_allowed=False)
    st = ad_ro.authenticate()
    ck(st.state.value == "connected" and ad_ro.session_proven(),
       "GET customer/status نشست را تأیید می‌کند", st)
    money = ad_ro.get_money()
    ck(money["buying_power"] == 500000000.0 and money["unit"] == "IRR"
       and money["formula"] == "purchasingPower"
       and "/Order/customer/status" in money["source"],
       "قدرت خرید فقط از purchasingPower ساخته می‌شود", money)
    bal = ad_ro.get_balances()
    ck(bal["cash"] == 400000000.0 and bal["blocked"] == 10000000.0
       and bal["buying_power"] == 500000000.0,
       "مانده/بلوکه از همان پاسخ و بی‌صفرِ جعلی", bal)
    ck(len(rt.calls) == 1 and rt.calls[0]["method"] == "GET"
       and rt.calls[0]["url"].endswith("/apigateway/api/v1/Order/customer/status")
       and rt.calls[0]["headers"].get("x-appname") == "titan"
       and rt.calls[0]["headers"].get("Authorization") == "Bearer " + long_tok,
       "خواندنِ حساب فقط GET و با هدرهایِ Titan است", rt.calls)
    ck(long_tok not in repr(ad_ro)
       and all(long_tok not in str(x) for x in ad_ro.redacted_log),
       "توکن در repr/لاگِ خواندن نیست", ad_ro.redacted_log)

    pos = ad_ro.get_positions()
    first = next(r for r in pos if r["isin"] == "IRO1TEST0001")
    second = next(r for r in pos if r["isin"] == "IRO1OTHER001")
    ck(first["settled"] == 900.0 and first["sellable"] == 850.0
       and first["sellable_state"] == SELLABLE_STATE,
       "sellable = min(دارایی، تسویه‌شده) - سفارشِ بازِ فروش", first)
    ck(second["sellable"] == 0.0, "کرانِ منفی به صفر بریده می‌شود، نه منفی", second)
    ck(ad_ro.get_sellable_quantity("IRO1TEST0001") == 850.0
       and ad_ro.get_sellable_quantity("IRO1UNKNOWN001") == 0.0,
       "sellable برایِ نمادِ موجود/غایب درست است")
    ck(ad_ro.sellable_provenance()["state"] == "CLIENT_DERIVED_UNVERIFIED",
       "sellable با برچسبِ برآوردِ کلاینت اعلام می‌شود")

    orders = ad_ro.get_orders()
    ck(len(orders) == 1 and orders[0].order_state is OrderState.PARTIAL
       and orders[0].filled_quantity == 4.0
       and orders[0].broker_order_id == "O-1"
       and orders[0].side is Side.BUY,
       "فهرستِ سفارشِ باز به رکوردِ خودی نگاشت می‌شود", orders)
    detail = ad_ro.get_order("O-1")
    ck(detail is not None and detail.order_state is OrderState.FILLED,
       "detail/state وضعیت را می‌دهد", detail)
    try:
        ad_ro.get_order("missing")
        ro_unknown = None
    except Exception as e:                       # noqa: BLE001
        ro_unknown = getattr(e, "code", None)
    ck(ro_unknown is ErrorCode.UNSUPPORTED,
       "read_only: شناسهٔ خارج از فهرست پیش از هر درخواست مسدود می‌شود", ro_unknown)
    ad_live = MofidAdapter(transport=rt, token=long_tok, writes_allowed=True,
                          read_only=False)
    ck(ad_live.get_order("missing") is None,
       "detail/state 404 ⇒ None در حالتِ غیرِ read_only")
    ck(map_order_state("Open") is OrderState.OPEN
       and map_order_state("Done") is OrderState.FILLED
       and map_order_state("Cancel") is OrderState.CANCELLED
       and map_order_state("Reject") is OrderState.REJECTED
       and map_order_state("چیزِ-ناشناخته") is OrderState.UNKNOWN,
       "نگاشتِ enumِ Titan و UNKNOWNِ محافظه‌کارانه")
    ck(all(c["method"] == "GET" for c in rt.calls),
       "هیچ درخواستِ تغییردهنده‌ای در مسیرِ خواندن ساخته نشد", rt.calls)

    # نشستِ منقضی/ردشده دو حالتِ جدا؛ 5xx «نامعلوم» است نه «باطل».
    for code, err, state in ((401, ErrorCode.SESSION_EXPIRED, "expired"),
                             (403, ErrorCode.AUTH_FAILED, "auth_failed")):
        ad_x = MofidAdapter(transport=ScriptTransport(WireResponse(code, {}, "{}")),
                            token="x")
        try:
            ad_x.authenticate()
            got = None
        except Exception as e:                   # noqa: BLE001
            got = getattr(e, "code", None)
        ck(got is err and ad_x.session_status().state.value == state,
           "HTTP %d ⇒ %s" % (code, err.value), ad_x.session_status())
    seq = {"n": 0}

    def flaky_status(method, url, headers, payload):
        seq["n"] += 1
        if seq["n"] == 1:
            return WireResponse(200, {}, status_body)
        return WireResponse(401, {}, "{}")

    ad_flaky = MofidAdapter(
        transport=RouteTransport({"/Order/customer/status": flaky_status}),
        token="T" * 48)
    ad_flaky.authenticate()
    was_proven = ad_flaky.session_proven()
    try:
        ad_flaky.authenticate()
    except Exception:                            # noqa: BLE001
        pass
    ck(was_proven and not ad_flaky.session_proven()
       and ad_flaky.session_status().state.value == "expired",
       "401 پس از نشستِ سالم، شاهدِ قبلی را باطل می‌کند",
       ad_flaky.session_status())
    try:
        ad_flaky.get_money()
        stale = None
    except Exception as e:                       # noqa: BLE001
        stale = getattr(e, "code", None)
    ck(stale is ErrorCode.SESSION_EXPIRED,
       "پس از 401، money از کشِ کهنه نمی‌آید", stale)

    ad_5 = MofidAdapter(transport=ScriptTransport(WireResponse(503, {}, "{}")), token="x")
    try:
        ad_5.authenticate()
        got5 = None
    except Exception as e:                       # noqa: BLE001
        got5 = getattr(e, "code", None)
    ck(got5 is ErrorCode.UNKNOWN_RESULT and ad_5.session_status().state.value == "error",
       "5xx در نشست ⇒ UNKNOWN و state=error", ad_5.session_status())
    ad_html = MofidAdapter(transport=ScriptTransport(WireResponse(200, {}, "<html>")),
                           token="x")
    try:
        ad_html.authenticate()
        got_html = None
    except Exception as e:                       # noqa: BLE001
        got_html = getattr(e, "code", None)
    ck(got_html is ErrorCode.UNKNOWN_RESULT and not ad_html.session_proven(),
       "200 غیرِJSON نشست را تأیید نمی‌کند", got_html)

    # preflight با دادهٔ واقعیِ حساب: خرید PASS، فروشِ بیش از sellable FAIL.
    svc_ro = ExecutionService(ad_ro, dry_run=False, limits=Limits())
    buy_pf = svc_ro.preflight(draft)
    ck(buy_pf.checks.get("balance") == "PASS"
       and "source=mofid" in buy_pf.reasons.get("balance", ""),
       "preflightِ خرید با purchasingPower واقعی PASS می‌شود",
       buy_pf.reasons.get("balance"))
    small_sell = OrderDraft("M-3", instr, Side.SELL, 1000.0, 800.0, OrderMode.SAFE)
    big_sell = OrderDraft("M-4", instr, Side.SELL, 1000.0, 900.0, OrderMode.SAFE)
    ck(svc_ro.preflight(small_sell).checks.get("sellable") == "PASS",
       "فروشِ ۸۰۰ از ۸۵۰ قبول می‌شود")
    big_pf = svc_ro.preflight(big_sell)
    big = big_pf.reasons.get("sellable", "")
    ck(big_pf.checks.get("sellable") == "FAIL" and "CLIENT_DERIVED_UNVERIFIED" in big,
       "فروشِ ۹۰۰ رد می‌شود و برچسبِ برآورد را نشان می‌دهد", big)

    ev = ad_ro.readiness_evidence()
    ck(ev["write"]["status"] == "UNVERIFIED" and ev["live_verified"] is False
       and ev["sellable"]["state"] == SELLABLE_STATE,
       "شاهدِ آمادگی، نوشتن/برآورد را ادعایِ تأییدشده نمی‌کند", ev)

    print("\n%d checks, %d failed" % (PASS + FAIL, FAIL))
    print("MOFID ADAPTER " + ("OK" if FAIL == 0 else "FAILED"))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
