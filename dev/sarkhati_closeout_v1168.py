#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sarkhati_closeout_v1168 — Round 20: قراردادِ جایگاه، خطاها و readiness.

هیچ شبکه/سفارشِ واقعی. EasyTrader با ترافیکِ بدیل و Mofid فقط با شاهدِ بسته.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from execution_easytrader import WireResponse as QueueWire  # noqa: E402
PASS = FAIL = 0


def ck(cond, label, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("ok   " + label)
    else:
        FAIL += 1
        print("FAIL " + label + "  -> " + str(detail)[:320])


class QueueTransport:
    """ترافیکِ بدیل؛ فقط پاسخِ مسیرِ صف را می‌دهد و تعدادِ فراخوانی را می‌شمارد."""
    name = "queue-mock"
    is_live = True

    def __init__(self, *, status=200, body="", raises=None, delay=0.0):
        self.status = status
        self.body = body
        self.raises = raises
        self.delay = delay
        self.calls = 0
        self._lock = threading.Lock()

    def request(self, *, method, url, headers, payload=None, timeout_s=7.0):
        with self._lock:
            self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        if self.raises is not None:
            raise self.raises
        return QueueWire(self.status, {}, self.body)


def main() -> int:
    from execution_contract import (
        BrokerError, Capabilities, ErrorCode, ExecutionRecord, ExecutionStatus,
        OrderMode, OrderState, QueueSnapshot, SessionState, Side,
    )
    from execution_easytrader import (
        EasyTraderAdapter, TransportNetwork, TransportTimeout,
    )
    from execution_mofid import MOFID_QUEUE_CONTRACT, MofidAdapter
    from execution_easytrader import RefusingTransport

    print("\n── ۱) قراردادِ Mofid: POSTِ پرسشی، جدا از نوشتن، و streamِ واقعی ──")
    qc = MOFID_QUEUE_CONTRACT
    ck(qc["api"]["method"] == "POST"
       and qc["api"]["read_only_by_code_evidence"] is True,
       "الف) هر دو POST پرسشِ خواندنی‌اند، نه نوشتن", qc["api"])
    ck(set(qc["api"]["client_names"]) == {"GetOrderPlaceAPI",
                                          "GetOrderPlacePostAPI"},
       "پ) نام‌های کلاینت صریح‌اند", qc["api"]["client_names"])
    ck(qc["api"]["request_observed"].get("orderId") == ["<broker order id>"],
       "ت) بدنهٔ مشاهده‌شده orderId است", qc["api"]["request_observed"])
    mut = qc["mutation_endpoints_separate"]
    ck(mut["send"] == {"path": "/Order/send", "method": "POST"}
       and mut["update"]["method"] == "PUT"
       and mut["delete"]["method"] == "DELETE",
       "ث) نوشتن‌ها مسیرهای جدا دارند", mut)
    st = qc["stream"]
    ck(st["origin"] == "https://ls.mofidonline.com"
       and st["topic"] == "orderplace:{orderId}"
       and set(st["fields"]) == {"isin", "volume-ahead", "placement"},
       "ج) streamِ واقعی با تاپیک و فیلدهای صریح", st)
    ck(st["snapshot"] is False and st["read_only"] is True
       and st["invoked"] is False,
       "چ) stream بی‌snapshot است و صدا زده نشد", st)
    ck(qc["source_verified"] is False and qc["api"]["source_verified"] is False
       and st["source_verified"] is False,
       "ح) هیچ مسیری با پاسخِ واقعی تأیید نشده")
    ck("per orderId" in qc["rank_semantics"]["scope"]
       and "0 is not treated as first" in qc["rank_semantics"]["zero_meaning"],
       "خ) دامنهٔ رتبه per-order است و ۰ اول نیست", qc["rank_semantics"])
    ck(qc["ui"]["zero_rendering"].find("'-'") >= 0,
       "د) UI خودش ۰ را با «-» نشان می‌دهد", qc["ui"]["zero_rendering"])
    mofid = MofidAdapter(transport=RefusingTransport(), token="fixture",
                         read_only=True, writes_allowed=False)
    ck(mofid.capabilities().queue_position is False
       and mofid.get_queue_position("O-1") is None,
       "ذ) Mofid در فقط‌خواندنی رتبه نمی‌سازد")

    print("\n── ۲) EasyTrader: تفکیکِ KNOWN/UNKNOWN/ERROR و بی‌صفر ──")
    caps = Capabilities(place=False, list_orders=True, order_state=True,
                        queue_position=True, cancel=False, best_bid_ask=False,
                        balances=False)

    def build(transport):
        return EasyTraderAdapter(transport=transport, token="fixture-token",
                                 capabilities=caps)

    known = json.dumps({"orderPlaces": [{"orderId": "O-1", "orderPlace": 0,
                                         "volumeAhead": 0}]})
    a = build(QueueTransport(body=known))
    snap = a.get_queue_position("O-1")
    ck(snap is not None and snap.known and snap.position == 0
       and snap.volume_ahead == 0,
       "الف) مقدارِ خامِ ۰ حفظ می‌شود", snap)
    ck("UNVERIFIED" in snap.source and snap.as_of,
       "پ) واحدِ حجم UNVERIFIED و as_of محلی ثبت می‌شود", snap)
    ck(build(QueueTransport(body='{"orderPlaces":[]}')).get_queue_position("O-1")
       is None, "ت) فهرستِ خالی ⇒ UNKNOWN، نه صفر")
    ck(build(QueueTransport(body=json.dumps({"orderPlaces": [
        {"orderId": "OTHER", "orderPlace": 1, "volumeAhead": 0}]})))
       .get_queue_position("O-1") is None,
       "ث) ردیفِ سفارشِ دیگر به سفارشِ ما نسبت داده نمی‌شود")
    ck(build(QueueTransport(body="<html>login</html>")).get_queue_position("O-1")
       is None, "ج) پاسخِ غیرJSON ⇒ UNKNOWN، نه موفق")

    for status, codes, label in (
            (401, (ErrorCode.SESSION_EXPIRED, ErrorCode.AUTH_FAILED, ErrorCode.UNKNOWN_RESULT),
             "چ) HTTP 401 ⇒ خطایِ نشست، نه UNKNOWNِ خاموش"),
            (500, (ErrorCode.NETWORK_ERROR,), "ح) HTTP 500 ⇒ ERRORِ شبکه")):
        ad = build(QueueTransport(status=status,
                                  body='{"isSuccessful":false,"message":"x"}'))
        try:
            ad.get_queue_position("O-1")
            ck(False, label, "no exception")
        except BrokerError as e:
            ck(e.code in codes, label, e.code.value)
            if status == 401:
                ck(ad.session_status().state in (SessionState.EXPIRED,
                                                 SessionState.AUTH_FAILED),
                   "خ) 401 حکمِ نشست را هم به‌روز می‌کند",
                   ad.session_status().state)
    ck(build(QueueTransport(status=404)).get_queue_position("O-1") is None,
       "د) HTTP 404 ⇒ UNKNOWN، نه ERROR/صفر")
    for exc, code, label in (
            (TransportTimeout("timeout"), ErrorCode.TIMEOUT, "ذ) timeout ⇒ TIMEOUT"),
            (TransportNetwork("net"), ErrorCode.NETWORK_ERROR,
             "ر) خطایِ شبکه ⇒ NETWORK_ERROR")):
        try:
            build(QueueTransport(raises=exc)).get_queue_position("O-1")
            ck(False, label, "no exception")
        except BrokerError as e:
            ck(e.code is code, label, e.code.value)

    print("\n── ۳) هم‌زمانیِ همان سفارش: یک GET، همان as_of ──")
    tr = QueueTransport(body=known, delay=0.03)
    ac = build(tr)
    results: list[object] = []
    barrier = threading.Barrier(5)

    def worker():
        barrier.wait()
        results.append(ac.get_queue_position("O-1"))

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    ck(tr.calls == 1 and len(results) == 5
       and all(r is not None and r.position == 0 for r in results),
       "الف) پنج فراخوانیِ هم‌زمان یک GET و همان مقدار", (tr.calls, len(results)))
    ac.QUEUE_CACHE_TTL_S = 0.0
    time.sleep(0.01)
    ac.get_queue_position("O-1")
    ck(tr.calls == 2, "پ) پس از انقضای TTL یک GET تازه می‌زند", tr.calls)

    print("\n── ۴) Queue Monitor: فلگ‌هایِ منبع/نتیجه جدا از هم ──")
    os.environ["BORS_EXECUTION_DB"] = os.path.join(
        tempfile.mkdtemp(prefix="round20_"), "execution.db")
    os.environ["BORS_SCHEDULE_DB"] = os.path.join(
        tempfile.mkdtemp(prefix="round20_sched_"), "schedules.db")
    import api.execution as EX
    from execution_contract import BrokerError as BErr

    old = (EX._ACTIVE_ADAPTER, EX.ADAPTER_KIND, EX._source_block)
    EX._source_block = lambda: None

    class Fake:
        def __init__(self, *, queue_position, snap=None, boom=None, contract=None):
            self._caps = Capabilities(place=False, list_orders=True,
                                      order_state=True, queue_position=queue_position,
                                      cancel=False, best_bid_ask=False, balances=False)
            self.snap, self.boom, self.contract = snap, boom, contract
            self.rows = [ExecutionRecord(
                execution_id="e1", broker="fake", account=None, symbol="TEST",
                isin="IRO1TEST0001", side=Side.BUY, price=1000.0, quantity=10.0,
                mode=OrderMode.SAFE, status=ExecutionStatus.ACKNOWLEDGED,
                broker_order_id="O-1", order_state=OrderState.OPEN, events=["ACK"])]

        def capabilities(self):
            return self._caps

        def get_orders(self):
            return list(self.rows)

        def get_queue_position(self, oid):
            if self.boom is not None:
                raise self.boom
            return self.snap

        def queue_contract(self):
            if self.contract is None:
                raise AttributeError("none")
            return dict(self.contract)

    try:
        EX._QUEUE_SERIES.clear()
        EX.ADAPTER_KIND = "mofid"
        EX._ACTIVE_ADAPTER = Fake(queue_position=False, contract=qc)
        m = EX._queue_monitor()
        r = (m.get("rows") or [{}])[0]
        ck(m.get("queue_source_verified") is False
           and m.get("queue_result_known") is False
           and r.get("queue_status") == "UNSUPPORTED_READ_ONLY"
           and r.get("queue_position") is None,
           "الف) منبع تأییدنشده و نتیجه نامعلوم، بدونِ رتبه", r)
        EX.ADAPTER_KIND = "easytrader"
        EX._ACTIVE_ADAPTER = Fake(
            queue_position=True,
            snap=QueueSnapshot(position=0, volume_ahead=0,
                               as_of="2026-10-22T10:00:00",
                               source="easytrader:orderPlace/volumeAhead"))
        m2 = EX._queue_monitor()
        r2 = (m2.get("rows") or [{}])[0]
        ck(m2.get("queue_result_known") is True
           and m2.get("queue_source_verified") is False
           and r2.get("queue_position") == 0,
           "پ) KNOWN از source_verified جدا است", m2.get("queue_result_known"))
        EX._ACTIVE_ADAPTER.snap = None
        m3 = EX._queue_monitor()
        ck(m3.get("queue_result_known") is False
           and (m3.get("rows") or [{}])[0].get("queue_status") == "UNKNOWN",
           "ت) خالی ⇒ UNKNOWN و queue_result_known=False")
        EX._ACTIVE_ADAPTER.boom = BErr(ErrorCode.NETWORK_ERROR, "timeout")
        m4 = EX._queue_monitor()
        ck(m4.get("queue_result_known") is False
           and (m4.get("rows") or [{}])[0].get("queue_status") == "ERROR",
           "ث) خطا ⇒ ERROR و queue_result_known=False")
        ck(isinstance(json.dumps(m4), str), "ج) پاسخ JSON-safe است")
    finally:
        EX._ACTIVE_ADAPTER, EX.ADAPTER_KIND, EX._source_block = old
        EX._QUEUE_SERIES.clear()

    print("\n── ۵) readiness: جایگاه، read-back و حساب سه گیتِ جدا ──")
    money = {"unit_state": "VERIFIED", "buying_power": 1000,
             "freshness": "LOCAL_FETCH_ONLY"}
    positions = [{"symbol": "TEST", "sellable_state": "CLIENT_DERIVED_UNVERIFIED"}]
    ready0 = EX._mofid_account_readiness(
        money=money, positions=positions, orders=[], today=[], details=[],
        steps={"session": "PASS"})
    gate0 = {g["id"]: g for g in ready0["gates"]}["queue_position"]
    qp0 = ready0["queue_position"]
    ck(gate0["status"] == "NOT_MEASURED" and qp0["ready"] is False
       and qp0["source_verified"] is False and qp0["result_known"] is False,
       "الف) بی‌سفارش ⇒ جایگاه NOT_MEASURED و ready=False", qp0)
    ck(ready0["read_only_account_ready"] is False
       and "queue_position" in [w["id"] for w in ready0["warnings"]],
       "پ) جایگاه در warnings هست ولی read-only را سبز نمی‌کند")
    order = ExecutionRecord(
        execution_id="e1", broker="mofid", account=None, symbol="TEST",
        isin="IRO1TEST0001", side=Side.BUY, price=1000.0, quantity=10.0,
        mode=OrderMode.SAFE, status=ExecutionStatus.ACKNOWLEDGED,
        broker_order_id="O-1", order_state=OrderState.OPEN, events=["ACK"])
    ready1 = EX._mofid_account_readiness(
        money=money, positions=positions, orders=[order], today=[order],
        details=[], steps={"session": "PASS"})
    gate1 = {g["id"]: g for g in ready1["gates"]}["queue_position"]
    ck(gate1["status"] == "BLOCKED"
       and ready1["queue_position"]["orders_with_id"] == 1,
       "ت) سفارش هست ولی مسیر جایگاه مسدود ⇒ BLOCKED",
       ready1["queue_position"])
    ck(len({g["id"] for g in ready1["gates"]}) == len(ready1["gates"]),
       "ث) شناسهٔ گیت‌ها یکتاست")

    print("\n%d pass / %d fail" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
