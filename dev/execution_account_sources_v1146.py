#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""گارد Round 10 — دیده‌بان/پرتفوی/قدرت خریدِ فقط‌خواندنی و پیش‌فرضِ ایمن.

هیچ شبکه و هیچ دادهٔ واقعی: transport و پاسخ‌ها fixture‌اند. تمرکز روی
  • پارسِ سه منبع و نبودِ customerIsin/بدنه در log،
  • ISIN→نمادِ یگانه و جدا نگه‌داشتنِ مبهم/بی‌نگاشت،
  • وضعیت‌هایِ مستقل و مستقل‌ماندنِ خطایِ هر منبع،
  • preflight: خرید با buying_power و فروش با تعدادِ آزاد؛ UNKNOWN سبز نیست.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import execution_easytrader as ET  # noqa: E402
import execution_service as ES  # noqa: E402
from execution_contract import (  # noqa: E402
    Capabilities, InstrumentRef, OrderDraft, Resolution, Side,
)

PASS = 0
FAIL = 0
FAILED: list[str] = []


def ck(ok: bool, label: str, extra=None) -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  ok   %s" % label)
    else:
        FAIL += 1
        FAILED.append(label)
        print("  FAIL %s -> %r" % (label, extra))


class FakeTransport:
    name = "fake"
    is_live = True

    def __init__(self, routes):
        self.routes = dict(routes)
        self.calls = []

    def request(self, *, method, url, headers, payload=None, timeout_s=7.0):
        path = url.split("api-mts.orbis.easytrader.ir", 1)[-1]
        self.calls.append((method, path))
        got = self.routes.get(path, (200, "{}"))
        if callable(got):
            got = got()
        status, body = got
        return ET.WireResponse(int(status), {"content-type": "application/json"},
                               body if isinstance(body, str) else json.dumps(body))


WATCH = [
    {"name": "list-a", "order": 0, "isDefault": True, "id": "c1",
     "watchCategorySymbols": [{"symbolIsin": "I1"}, {"symbolIsin": "I2"},
                              {"symbolIsin": "I1"}, {"symbolIsin": "I3"}]},
    {"name": "list-b", "order": 1, "isDefault": False, "id": "c2",
     "watchCategorySymbols": [{"symbolIsin": "I1"}]},
]
PORT = {"items": [
    {"symbolIsin": "I1", "symbolName": "one", "asset": 1000,
     "totalBuyAveragePrice": 900, "totalRealizedProfitAndLoss": 20,
     "date": "2026-10-20", "persianDate": 14050728},
    {"symbolIsin": "I2", "symbolName": "two", "asset": 2000,
     "totalBuyAveragePrice": 1900, "totalRealizedProfitAndLoss": -5},
    {"symbolIsin": "I9", "symbolName": "nine", "asset": 50},
]}
MONEY = {"t0": 10, "t1": 20, "t2": 30, "buyPowerT0": 100,
         "buyPowerT1": 200, "buyPowerT2": 300, "credit": 40,
         "avandCredit": 5, "block": 7, "marginBlock": 0}


def make_db():
    d = tempfile.mkdtemp(prefix="round10_")
    path = os.path.join(d, "market.db")
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE instruments(ins_code TEXT, isin TEXT, "
              "l_val18 TEXT, updated_at TEXT)")
    c.executemany("INSERT INTO instruments VALUES(?,?,?,?)", [
        ("1", "I1", "X", "2026-10-21"),
        ("2", "I2", "Y", "2026-10-21"),
        ("5", "I5", "Z1", "2026-10-21"),
        ("6", "I5", "Z2", "2026-10-21"),
    ])
    c.commit()
    c.close()
    return path, d


def main() -> int:
    db_path, tmp = make_db()
    old = {
        "adapter": getattr(ET, "WIRE_PATH_MARKET_WATCH", None),
    }
    import api.execution as EX
    old_adapter, old_kind, old_traffic, old_db = (
        EX._ACTIVE_ADAPTER, EX.ADAPTER_KIND, EX.TRAFFIC_ALLOWED, EX.DB_PATH)
    transport = FakeTransport({
        ET.WIRE_PATH_MARKET_WATCH: (200, WATCH),
        ET.WIRE_PATH_ASSET_PERFORMANCE: (200, PORT),
        ET.WIRE_PATH_MONEY: (200, MONEY),
    })
    adapter = ET.EasyTraderAdapter(transport=transport, token="SENTINEL-TOKEN",
                                   writes_allowed=False)
    adapter.session_proven = lambda: True
    try:
        print("── ۱) پارسِ سه منبع و نبودِ بدنه در log ──")
        watch = adapter.get_watchlist()
        perf = adapter.get_portfolio_performance()
        money = adapter.get_money()
        ck(len(watch) == 2 and [len(c["isins"]) for c in watch] == [4, 1],
           "دیده‌بان: دو دسته و ۴+۱ ISIN", watch)
        ck(all("customerIsin" not in c for c in watch),
           "customerIsin در خروجی نیست")
        ck(len(perf) == 3 and "asset" in perf[0] and "symbolIsin" in perf[0],
           "پرتفوی: سه ردیف با فیلدهای شناخته‌شده", len(perf))
        ck("quantity" not in perf[0] and "sellable" not in perf[0],
           "پرتفوی: تعداد/قابل‌فروش ادعا نمی‌شود")
        ck(money["buying_power"] == 255 and money["unit"] == "IRR",
           "قدرت خرید = ۳۰۰ − ۴۰ − ۵، واحد IRR", money["buying_power"])
        ck("SENTINEL-TOKEN" not in json.dumps(adapter.redacted_log,
                                             ensure_ascii=False),
           "token در log نیست")
        tags = {"watchlist", "portfolio", "money"}
        entries = [e for e in adapter.redacted_log if e.get("tag") in tags]
        ck(len(entries) == 3 and all("body_head" not in e for e in entries),
           "بدنهٔ منابع در log نمی‌نشیند")

        print("\n── ۲) ISIN→نماد، مبهم و بی‌نگاشت ──")
        EX.DB_PATH = db_path
        m1 = EX._instrument_by_isin("I1")
        m3 = EX._instrument_by_isin("I3")
        m5 = EX._instrument_by_isin("I5")
        ck(m1["resolved"] and m1["symbol"] == "X" and m1["ins_code"] == "1",
           "ISIN شناخته‌شده به نماد/ins_code نگاشت می‌شود", m1)
        ck(not m3["resolved"] and m3["reason"] == "ISIN_NOT_MAPPED",
           "ISIN ناشناس resolved نمی‌شود", m3)
        ck(not m5["resolved"] and m5["ambiguous"] is True,
           "ISIN تکراری مبهم می‌ماند", m5)

        print("\n── ۳) API: وضعیت‌هایِ مستقل ──")
        EX._ACTIVE_ADAPTER, EX.ADAPTER_KIND, EX.TRAFFIC_ALLOWED = (
            adapter, "easytrader", True)
        w = EX.get_easytrader_watchlist()
        p = EX.get_portfolio()
        b = EX.get_buying_power()
        ck(w["state"] == EX.WATCHLIST_VERIFIED and w["raw_count"] == 5
           and w["unresolved_count"] == 1 and w["duplicate_count"] == 2,
           "دیده‌بان VERIFIED با شمارشِ خام/نگاشت‌نشده/تکراری", w.get("state"))
        ck(p["state"] == EX.PORTFOLIO_PARTIALLY_VERIFIED
           and p["raw_count"] == 3 and p["resolved_count"] == 2
           and "quantity" in p["missing_fields"],
           "پرتفوی PARTIAL با فقدانِ صریحِ تعداد", p.get("state"))
        ck((p.get("buying_power") or {}).get("state") == EX.BUYING_POWER_VERIFIED,
           "قدرت خرید در پاسخِ پرتفوی جدا VERIFIED است")
        ck(b["state"] == EX.BUYING_POWER_VERIFIED and b["unit"] == "IRR"
           and b["value"] == 255,
           "BUYING_POWER_VERIFIED با واحد و مقدارِ واقعیِ fixture", b.get("state"))
        for obj in (w, p, b):
            ck("SENTINEL-TOKEN" not in json.dumps(obj, ensure_ascii=False),
               "پاسخِ API توکن را برنمی‌گرداند")

        print("\n── ۴) شکستِ مستقل ──")
        bad_tr = FakeTransport({
            ET.WIRE_PATH_MARKET_WATCH: (500, "boom"),
            ET.WIRE_PATH_ASSET_PERFORMANCE: (200, PORT),
            ET.WIRE_PATH_MONEY: (200, MONEY),
        })
        bad = ET.EasyTraderAdapter(transport=bad_tr, token="SENTINEL-TOKEN",
                                   writes_allowed=False)
        bad.session_proven = lambda: True
        EX._ACTIVE_ADAPTER = bad
        wb = EX.get_easytrader_watchlist()
        pb = EX.get_portfolio()
        ck(wb["state"] == EX.WATCHLIST_UNAVAILABLE and wb["rows"] == []
           and "boom" not in str(wb.get("error")),
           "خطای دیده‌بان = UNAVAILABLE، نه فهرستِ خالی/بدنه", wb.get("state"))
        ck(pb["state"] == EX.PORTFOLIO_PARTIALLY_VERIFIED
           and len(pb["rows"]) == 3,
           "خطای دیده‌بان پرتفوی را متوقف نمی‌کند")

        print("\n── ۵) پیش‌فرضِ خرید/فروش و UNKNOWN ──")
        class A:
            def capabilities(self):
                return Capabilities(place=True, list_orders=True, order_state=True,
                                    queue_position=False, cancel=False,
                                    best_bid_ask=False, balances=True)
            def get_balances(self):
                return {"buying_power": 1000.0, "unit": "IRR",
                        "source": "fixture"}
            def get_sellable_quantity(self, isin=None):
                return None
        svc = ES.ExecutionService(A(), session_gate=lambda _n: "open")
        inst = InstrumentRef(symbol="X", ins_code="1", isin="I1",
                             broker_instrument="I1", resolution=Resolution.EXACT)
        def draft(side, qty, price=100.0):
            return OrderDraft(execution_id="t-%s-%s" % (side.value, qty),
                              instrument=inst, side=side, price=price,
                              quantity=qty)
        pb1 = svc.preflight(draft(Side.BUY, 5))
        ck(pb1.checks.get("balance") == ES.PASS and pb1.ok is True,
           "خرید ۵۰۰ از buying_power ۱۰۰۰ ⇒ PASS", pb1.checks)
        pb2 = svc.preflight(draft(Side.BUY, 20))
        ck(pb2.checks.get("balance") == ES.FAIL_ and pb2.ok is False,
           "خرید ۲۰۰۰ از buying_power ۱۰۰۰ ⇒ FAIL", pb2.checks)
        ps = svc.preflight(draft(Side.SELL, 5))
        ck(ps.checks.get("sellable") == ES.UNKNOWN and ps.ok is False,
           "فروش بی‌منبعِ تعداد آزاد ⇒ UNKNOWN و مسدود", ps.checks)
        class Bad:
            def capabilities(self):
                return Capabilities(place=True, list_orders=True, order_state=True,
                                    queue_position=False, cancel=False,
                                    best_bid_ask=False, balances=True)
            def get_balances(self):
                raise ET.BrokerError(ET.ErrorCode.UNKNOWN_RESULT, "no money")
            def get_sellable_quantity(self, isin=None):
                return None
        sb = ES.ExecutionService(Bad(), session_gate=lambda _n: "open")
        pbad = sb.preflight(draft(Side.BUY, 1))
        ck(pbad.checks.get("balance") == ES.UNKNOWN and pbad.ok is False,
           "بی‌پاسخِ buying power ⇒ UNKNOWN، نه PASS")
        class BadSell:
            def capabilities(self):
                return Capabilities(place=True, list_orders=True, order_state=True,
                                    queue_position=False, cancel=False,
                                    best_bid_ask=False, balances=True)
            def get_balances(self):
                return {"buying_power": 1000.0}
            def get_sellable_quantity(self, isin=None):
                raise ET.BrokerError(ET.ErrorCode.UNKNOWN_RESULT, "no positions")
        ss = ES.ExecutionService(BadSell(), session_gate=lambda _n: "open")
        pbs = ss.preflight(draft(Side.SELL, 1))
        ck(pbs.checks.get("sellable") == ES.UNKNOWN and pbs.ok is False,
           "خطایِ منبعِ تعداد آزاد ⇒ UNKNOWN و مسدود، نه ۵۰۰")
    finally:
        EX._ACTIVE_ADAPTER, EX.ADAPTER_KIND, EX.TRAFFIC_ALLOWED, EX.DB_PATH = (
            old_adapter, old_kind, old_traffic, old_db)
        try:
            os.remove(os.path.join(tmp, "market.db"))
            os.rmdir(tmp)
        except OSError:
            pass

    print("\n%d passed / %d failed" % (PASS, FAIL))
    if FAILED:
        print("FAILED: " + ", ".join(FAILED))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
