#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mofid_readiness_v1164 — API/readiness با شاهدِ فقط‌خواندنیِ Mofid.

هیچ شبکه‌ای نمی‌زند: ترافیک تزریقی است و همهٔ پاسخ‌ها بدلِ شکلِ قراردادند.
هدف این است که مسیرِ API (portfolio/buying-power/status/readiness) همان
داده‌ای را نشان دهد که آداپتور خوانده، و هیچ‌جا نوشتن یا «تأییدشده» ادعا نشود.
"""
from __future__ import annotations

import os
import sqlite3
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
                return item
        raise AssertionError("unrouted URL: %s" % url)


STATUS = ('{"data":{"purchasingPower":500000000,"accountBalanceT2":400000000,'
          '"blockedBalance":10000000,"credit":0,"marginBlock":0}}')
PORTFOLIO = ('{"data":[{"symbolIsin":"IRO1TEST0001","symbolName":"TEST",'
             '"currentAsset":1000,"todayBoughtAsset":200,"todaySoldAsset":100,'
             '"openSellOrders":50,"openBuyOrders":0,"averageBuyPrice":2000},'
             '{"symbolIsin":"IRO1OTHER001","symbolName":"OTHER",'
             '"currentAsset":10,"todayBoughtAsset":0,"todaySoldAsset":0,'
             '"openSellOrders":20}]}')
ORDERS = ('{"data":[{"orderId":"O-1","symbol":"TEST","symbolIsin":"IRO1TEST0001",'
          '"orderSide":"Buy","orderPrice":2474,"quantity":10,'
          '"executedQuantity":4,"orderState":"Open"}]}')


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="mofid_rt16_")
    os.environ["BORS_DATA_DIR"] = tmp
    os.environ["BORS_TEST_ISOLATION"] = "1"
    open(os.path.join(tmp, ".bors_test_isolation"), "w").close()
    os.environ["BORS_USER_DB"] = os.path.join(tmp, "user.db")
    os.environ["BORS_INTENT_DB"] = os.path.join(tmp, "intents.db")
    os.environ["BORS_EXECUTION_ADAPTER"] = "mock"

    db = os.path.join(tmp, "market.db")
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE instruments(ins_code TEXT, isin TEXT, "
                 "l_val18 TEXT, updated_at TEXT)")
    conn.execute("INSERT INTO instruments VALUES(?,?,?,?)",
                 ("1", "IRO1TEST0001", "TEST", "2026-10-21"))
    conn.commit()
    conn.close()

    from execution_easytrader import WireResponse
    from execution_mofid import CONTRACT_STATE, MofidAdapter

    import api.execution as EX

    old_adapter, old_kind, old_traffic = (
        EX._ACTIVE_ADAPTER, EX.ADAPTER_KIND, EX.TRAFFIC_ALLOWED)
    old_db, old_service_adapter = EX.DB_PATH, EX._SERVICE.adapter
    old_read_only = EX.READ_ONLY_REQUESTED
    EX.DB_PATH = db
    EX.ADAPTER_KIND = "mofid"
    EX.TRAFFIC_ALLOWED = True
    EX.READ_ONLY_REQUESTED = True
    tr = RouteTransport({
        "/Order/customer/status": WireResponse(200, {}, STATUS),
        "/Portfolio/Daily": WireResponse(200, {}, PORTFOLIO),
        "/Order/open-orders": WireResponse(200, {}, ORDERS),
    })
    adapter = MofidAdapter(transport=tr, token="T" * 48, writes_allowed=False)
    EX._ACTIVE_ADAPTER = adapter
    EX._SERVICE.adapter = adapter

    bp = EX.get_buying_power()
    ck(bp.get("state") == "BUYING_POWER_VERIFIED"
       and bp.get("value") == 500000000 and bp.get("unit") == "IRR"
       and "mofid" in str(bp.get("source")),
       "buying-power از purchasingPowerِ Mofid و با واحدِ ریال", bp)
    ck(bp.get("session_proven") is True and adapter.session_proven(),
       "همان GET نشست را تأیید کرد", bp.get("session_proven"))

    pf = EX.get_portfolio()
    rows = pf.get("rows") or []
    first = next((r for r in rows if r.get("isin") == "IRO1TEST0001"), {})
    ck(pf.get("state") == "PORTFOLIO_READ_ONLY_UNVERIFIED"
       and pf.get("sellable_state") == "CLIENT_DERIVED_UNVERIFIED"
       and first.get("sellable_quantity") == 850.0
       and first.get("sellable_state") == "CLIENT_DERIVED_UNVERIFIED",
       "پرتفوی با برچسبِ فقط‌خواندنی و sellableِ برآوردی", pf)
    ck(pf.get("resolved_count") == 1 and pf.get("unresolved_count") == 1,
       "نگاشتِ ISIN جدا از شمارشِ ردیف‌ها گزارش می‌شود",
       {"resolved": pf.get("resolved_count"), "unresolved": pf.get("unresolved_count")})
    ck((pf.get("buying_power") or {}).get("state") == "BUYING_POWER_VERIFIED",
       "قدرت خرید در پاسخِ پرتفوی هم از منبعِ خودش است", pf.get("buying_power"))

    st = EX.get_status()
    wprov = st.get("wire_provenance") or {}
    ck(st.get("adapter") == "mofid" and st.get("live_enabled") is False
       and st.get("read_only") is True
       and (st.get("capabilities") or {}).get("balances") is True
       and (st.get("capabilities") or {}).get("place") is False,
       "status: خواندن باز، نوشتن بسته", st.get("capabilities"))
    ck(wprov.get("contract") == CONTRACT_STATE
       and wprov.get("write", {}).get("status") == "UNVERIFIED"
       and wprov.get("sellable", {}).get("state") == "CLIENT_DERIVED_UNVERIFIED",
       "شاهدِ قرارداد در status می‌آید", wprov)
    ck(any("خواندنِ حساب/سفارش مجاز است" in b for b in st.get("blocked_on") or []),
       "پیامِ blockade نوشتن را از خواندن جدا می‌گوید", st.get("blocked_on"))

    rd = EX.get_readiness(symbol="TEST", side="buy", price=1000, quantity=10)
    gates = {g["id"]: g for g in rd.get("gates") or []}
    ck(rd.get("live_ready") is False
       and gates.get("read_only_session", {}).get("status") == "PASS"
       and gates.get("buying_power", {}).get("status") == "PASS"
       and gates.get("write_contract", {}).get("status") != "PASS",
       "readiness: داده/نشست سبز، نوشتن نه", {k: v.get("status") for k, v in gates.items()})

    ck(all(c["method"] == "GET" for c in tr.calls),
       "هیچ POSTای در کلِ مسیرِ خواندن ساخته نشد", tr.calls)
    ck(all("T" * 48 not in str(v) for v in (repr(adapter), adapter.redacted_log)),
       "توکن در repr/لاگ نیست")

    # 401: نشست تأیید نمی‌شود و عددِ جعلی ساخته نمی‌شود.
    tr401 = RouteTransport({"/Order/customer/status": WireResponse(401, {}, "{}")})
    ad401 = MofidAdapter(transport=tr401, token="x", writes_allowed=False)
    EX._ACTIVE_ADAPTER = ad401
    EX._SERVICE.adapter = ad401
    bp401 = EX.get_buying_power()
    ck(bp401.get("state") == "ACCOUNT_SOURCE_BLOCKED"
       and bp401.get("value") is None and not ad401.session_proven(),
       "401 ⇒ ACCOUNT_SOURCE_BLOCKED و بی‌مقدار", bp401)

    # ترافیکِ خاموش: هیچ درخواستی حتی برایِ تأییدِ نشست ساخته نمی‌شود.
    EX.TRAFFIC_ALLOWED = False
    tr_off = RouteTransport({})
    ad_off = MofidAdapter(transport=tr_off, token="x", writes_allowed=False)
    EX._ACTIVE_ADAPTER = ad_off
    EX._SERVICE.adapter = ad_off
    off = EX.get_buying_power()
    ck(off.get("state") == "ACCOUNT_SOURCE_BLOCKED" and not tr_off.calls,
       "ترافیکِ خاموش ⇒ صفر درخواست", off)

    spec_ok = True
    for spec in ("fts_terminal.spec", "bors_setup.spec"):
        text = open(os.path.join(ROOT, spec), encoding="utf-8").read()
        spec_ok = spec_ok and "execution_mofid" in text
    ck(spec_ok, "execution_mofid درِ هر دو spec ثبت شده است")

    EX._ACTIVE_ADAPTER, EX.ADAPTER_KIND, EX.TRAFFIC_ALLOWED = (
        old_adapter, old_kind, old_traffic)
    EX.DB_PATH, EX._SERVICE.adapter = old_db, old_service_adapter
    EX.READ_ONLY_REQUESTED = old_read_only

    print("\n%d checks, %d failed" % (PASS + FAIL, FAIL))
    print("MOFID READINESS " + ("OK" if FAIL == 0 else "FAILED"))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
