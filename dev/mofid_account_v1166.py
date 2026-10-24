#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mofid_account_v1166 — Round 18: قرارداد حساب، واحد، sellable و readiness.

هیچ شبکه‌ای نمی‌زند. 12 ردیفِ fixture (نه حساب واقعی) برایِ فرمول، و
RouteTransport برایِ قراردادهایِ سفارش استفاده می‌شود.
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
        print("FAIL " + label + "  -> " + str(detail)[:300])


class RouteTransport:
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


def positions_body():
    rows = []
    for i in range(12):
        rows.append({
            "symbolIsin": "IRO1TST%04d" % i,
            "symbolName": "T%02d" % i,
            "currentAsset": 100 + i,
            "todayBoughtAsset": 10,
            "todaySoldAsset": 3,
            "openSellOrders": 5,
            "openBuyOrders": 0,
            "averageBuyPrice": 1000 + i,
        })
    import json
    return json.dumps({"data": rows}, ensure_ascii=False)


def main() -> int:
    from execution_easytrader import TransportTimeout, WireResponse
    from execution_mofid import (
        ORDER_CONTRACT, POSITION_FIELD_MAP, SELLABLE_STATE, UNIT_VERIFICATION,
        MofidAdapter,
    )

    ck(UNIT_VERIFICATION["state"] == "VERIFIED"
       and UNIT_VERIFICATION["unit"] == "IRR"
       and UNIT_VERIFICATION["precision"] == 0
       and UNIT_VERIFICATION["server_unit_field"] is False
       and "official" in UNIT_VERIFICATION["evidence"],
       "واحد/دقت با شاهدِ UI رسمی و بسته، VERIFIED است", UNIT_VERIFICATION)

    money_data = ('{"data":{"purchasingPower":42015035,'
                  '"accountBalanceT2":42015035,"accountBalanceT1":42015035,'
                  '"blockedBalance":0,"credit":0,"marginBlock":0,'
                  '"walletBalance":1,"bourseCode":"X","email":"x@y",'
                  '"title":"t"}}')
    rt = RouteTransport({
        "/Order/customer/status": WireResponse(200, {}, '{"data":{}}'),
        "/Accounting/Remain": WireResponse(200, {}, money_data),
        "/Portfolio/Daily": WireResponse(200, {}, positions_body()),
    })
    ad = MofidAdapter(transport=rt, token="T" * 48, writes_allowed=False)
    money = ad.get_money()
    ck(money["buying_power"] == 42015035.0
       and money["unit_state"] == "VERIFIED" and money["precision"] == 0
       and money["freshness"] == "LOCAL_FETCH_ONLY"
       and money["server_timestamp"] is None
       and "walletBalance" in money["response_keys"]
       and "email" not in money["raw"] and "bourseCode" not in money["raw"],
       "مبلغ/واحد/دقت و کلیدهایِ پاسخ درست‌اند؛ شناسه‌ها در raw نیستند", money)
    pos = ad.get_positions()
    ck(len(pos) == 12
       and all(p["sellable"] == (min(p["current_asset"], p["settled"])
                                  - p["open_sell"])
               for p in pos)
       and all(p["sellable_state"] == SELLABLE_STATE for p in pos),
       "فرمول رویِ ۱۲ ردیف سازگار و برچسبِ CLIENT_DERIVED_UNVERIFIED حفظ شد")
    ck(POSITION_FIELD_MAP["current_asset"] == "currentAsset"
       and POSITION_FIELD_MAP["settled"] ==
           "currentAsset + todaySoldAsset - todayBoughtAsset"
       and POSITION_FIELD_MAP["open_sell"] == "openSellOrders",
       "نقشهٔ فیلدهایِ sellable صریح است", POSITION_FIELD_MAP)

    # پاسخ با فیلد زمان: فقط خام گزارش می‌شود، نه تفسیرشده.
    rt_ts = RouteTransport({
        "/Order/customer/status": WireResponse(200, {}, '{"data":{}}'),
        "/Accounting/Remain": WireResponse(200, {}, (
            '{"data":{"purchasingPower":10,"lastUpdate":"2026-10-22T02:00:00"}}')),
    })
    ts = MofidAdapter(transport=rt_ts, token="T" * 48,
                      writes_allowed=False).get_money()
    ck(ts["server_timestamp"]["key"] == "lastUpdate"
       and ts["server_timestamp"]["interpretation"] == "UNVERIFIED"
       and ts["freshness"] == "SERVER_FIELD_RAW_UNVERIFIED",
       "زمانِ سرورِ نام‌دار فقط خام و UNVERIFIED گزارش می‌شود", ts)

    ck(ORDER_CONTRACT["open_orders"]["method"] == "GET"
       and ORDER_CONTRACT["state"]["method"] == "GET"
       and ORDER_CONTRACT["detail"]["method"] == "GET"
       and ORDER_CONTRACT["semantics"]["send_2xx"] ==
           "REQUEST_RECORDED_NOT_ACCEPTED",
       "قراردادِ مسیرها GET و معنایِ 2xx صریح است", ORDER_CONTRACT)

    rt_orders = RouteTransport({
        "/Order/customer/status": WireResponse(200, {}, '{"data":{}}'),
        "/Order/open-orders": WireResponse(200, {}, (
            '{"data":[{"orderId":"O-1","symbol":"T","symbolIsin":"I1",'
            '"orderSide":"Buy","orderPrice":10,"quantity":5,'
            '"executedQuantity":2,"orderState":"Open"}]}')),
        "/Order/today-order": WireResponse(200, {}, '{"data":[]}'),
        "/Order/detail/O-1": WireResponse(200, {}, (
            '{"data":{"orderId":"O-1","orderState":"Done","quantity":5,'
            '"executedQuantity":5,"orderPrice":10,"symbolIsin":"I1"}}')),
        "/Order/detail/missing": WireResponse(404, {}, "{}"),
        "/Order/state/missing": WireResponse(404, {}, "{}"),
        "/Order/detail/broken": WireResponse(503, {}, "{}"),
        "/Order/state/broken": WireResponse(503, {}, "{}"),
    })
    ad_o = MofidAdapter(transport=rt_orders, token="T" * 48,
                        writes_allowed=False)
    ad_o.authenticate()
    ad_o.get_orders()
    rec = ad_o.get_order("O-1")
    ck(rec is not None and rec.order_state.value == "filled"
       and rec.filled_quantity == 5.0,
       "detail فقط برایِ شناسهٔ فهرست و با نگاشتِ وضعیت", rec)
    before = len(rt_orders.calls)
    try:
        ad_o.get_order("FAKE")
        fake = None
    except Exception as e:                       # noqa: BLE001
        fake = getattr(e, "code", None)
    ck(fake is not None and len(rt_orders.calls) == before,
       "شناسهٔ ساختگی پیش از درخواستِ واقعی مسدود می‌شود", fake)
    try:
        ad_o.get_order("broken")
        broken = None
    except Exception as e:                       # noqa: BLE001
        broken = getattr(e, "code", None)
    ck(broken is not None, "5xx در detail نامعلوم است، نه «نبود»", broken)
    ck(all(c["method"] == "GET" for c in rt_orders.calls),
       "هیچ POSTِ سفارشی در مسیرِ قرارداد ساخته نشد", rt_orders.calls)

    # 401 و timeout: دادهٔ صفر/کهنه ساخته نمی‌شود.
    seq = {"n": 0}

    def flaky(method, url, headers, payload):
        seq["n"] += 1
        return WireResponse(200 if seq["n"] == 1 else 401, {},
                            '{"data":{"purchasingPower":10}}'
                            if seq["n"] == 1 else "{}")

    ad_401 = MofidAdapter(
        transport=RouteTransport({"/Order/customer/status": flaky}),
        token="T" * 48, writes_allowed=False)
    ad_401.authenticate()
    try:
        ad_401.authenticate()
    except Exception:                            # noqa: BLE001
        pass
    try:
        ad_401.get_money()
        stale = None
    except Exception as e:                       # noqa: BLE001
        stale = getattr(e, "code", None)
    ck(stale is not None and not ad_401.session_proven(),
       "401 بعد از نشستِ سالم، کش/شاهد را باطل می‌کند", stale)
    ad_to = MofidAdapter(
        transport=RouteTransport({"/Order/customer/status": TransportTimeout("no")}),
        token="T" * 48, writes_allowed=False)
    try:
        ad_to.authenticate()
        to_code = None
    except Exception as e:                       # noqa: BLE001
        to_code = getattr(e, "code", None)
    ck(to_code is not None, "timeout ⇒ خطایِ نامعلوم، نه صفر", to_code)

    # helperِ readiness با ورودیِ مصنوعی؛ هیچ شبکه‌ای نمی‌زند.
    tmp = tempfile.mkdtemp(prefix="mofid_r18_")
    os.environ["BORS_DATA_DIR"] = tmp
    os.environ["BORS_TEST_ISOLATION"] = "1"
    open(os.path.join(tmp, ".bors_test_isolation"), "w").close()
    os.environ["BORS_USER_DB"] = os.path.join(tmp, "user.db")
    os.environ["BORS_INTENT_DB"] = os.path.join(tmp, "intents.db")
    os.environ["BORS_EXECUTION_ADAPTER"] = "mock"
    import api.execution as EX
    ready = EX._mofid_account_readiness(
        money={"buying_power": 10, "unit_state": "VERIFIED",
               "freshness": "LOCAL_FETCH_ONLY", "server_timestamp": None},
        positions=[{"sellable_state": SELLABLE_STATE}], orders=[], today=[],
        details=[], steps={"session": "PASS"})
    gates = {g["id"]: g["status"] for g in ready["gates"]}
    ck(ready["probe_ok"] is True and ready["read_only_account_ready"] is False
       and ready["live_ready"] is False
       and gates.get("unit") == "PASS" and gates.get("sellable") == "UNVERIFIED"
       and gates.get("freshness") == "UNVERIFIED"
       and gates.get("read_back") == "NOT_MEASURED",
       "readiness: واحد PASS، sellable/تازگی باز، live_ready=false", gates)
    ready_ts = EX._mofid_account_readiness(
        money={"buying_power": 10, "unit_state": "VERIFIED",
               "freshness": "SERVER_FIELD_RAW_UNVERIFIED",
               "server_timestamp": {"key": "lastUpdate", "raw": "x",
                                    "interpretation": "UNVERIFIED"}},
        positions=[{"sellable_state": SELLABLE_STATE}], orders=[], today=[],
        details=[], steps={"session": "PASS"})
    fresh_gate = next(g for g in ready_ts["gates"] if g["id"] == "freshness")
    ck(fresh_gate["status"] == "UNVERIFIED" and "lastUpdate" in fresh_gate["detail"],
       "گیتِ تازگی فیلدِ خامِ زمانِ سرور را UNVERIFIED نگه می‌دارد", fresh_gate)

    print("\n%d checks, %d failed" % (PASS + FAIL, FAIL))
    print("MOFID ACCOUNT " + ("OK" if FAIL == 0 else "FAILED"))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
