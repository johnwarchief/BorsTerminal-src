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


def main() -> int:
    from execution_contract import (
        ErrorCode, ExecutionStatus, InstrumentRef, OrderDraft, OrderMode,
        Resolution, Side,
    )
    from execution_easytrader import TransportTimeout, WireResponse
    from execution_mofid import MofidAdapter, build_payload
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

    print("\n%d checks, %d failed" % (PASS + FAIL, FAIL))
    print("MOFID ADAPTER " + ("OK" if FAIL == 0 else "FAILED"))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
