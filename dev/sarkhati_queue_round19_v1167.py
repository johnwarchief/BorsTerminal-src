#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sarkhati_queue_round19_v1167 — Round 19: تلمتریِ مشترک، تأخیرها، و جایگاهِ صف.

هیچ شبکه‌ای نمی‌زند و هیچ سفارشی نمی‌سازد. موتور با MockBrowserDriver و
clockِ کنترل‌شده اجرا می‌شود؛ پایشِ صف با آداپتورِ بدل و DBِ موقت.
"""
from __future__ import annotations

import json
import os
import statistics
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


class VirtualClock:
    """ساعتِ کنترل‌شده برای مسیرِ API؛ هر فراخوانی گامِ ثابت برمی‌دارد."""

    def __init__(self, start: float = 1000.0, step: float = 2.0) -> None:
        self.t = float(start)
        self.step = float(step)

    def __call__(self) -> float:
        self.t += self.step
        return self.t

    def advance(self, ms: float) -> None:
        self.t += float(ms)


def pct(values, q):
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
    return ordered[idx]


def main() -> int:
    import execution_browser as EB
    import execution_intent_store as IS
    import execution_strategy_core as SC
    import execution_strategy_engine as SE
    from execution_contract import (
        Capabilities, ExecutionRecord, ExecutionStatus, InstrumentRef, OrderDraft,
        OrderMode, OrderState, QueueSnapshot, Resolution, Side,
    )
    from execution_telemetry import ExecutionTelemetry, METRIC_FIELDS, TELEMETRY_FIELDS
    from execution_timing import Scheduler, TimeSource

    print("\n── ۱) حسابِ تأخیرها فقط از شاهدِ خودش ──")
    tel = ExecutionTelemetry(
        intent_created_wall_ms=1_000_000,
        preflight_started_mono_ms=1000.0, preflight_completed_mono_ms=1125.0,
        scheduled_target_wall_ms=2_000_000, scheduled_target_mono_ms=5000.0,
        execution_start_mono_ms=5050.0, execution_start_wall_ms=2_000_050,
        send_started_mono_ms=5003.5, send_started_wall_ms=2_000_004,
        browser_click_started_mono_ms=5055.0,
        request_started_mono_ms=5060.0,
        response_received_mono_ms=5270.0,
        broker_acknowledged_mono_ms=5270.0,
        order_id_observed_mono_ms=5282.0,
        queue_position_observed_mono_ms=6182.0,
        first_fill_mono_ms=7000.0,
    )
    lat = tel.latencies()
    ck(lat["preflight_ms"] == 125.0, "الف) preflight از monotonic", lat)
    ck(lat["scheduler_lag_ms"] == 3.5,
       "پ) تأخیرِ Scheduler از هدفِ monotonic تا ارسالِ واقعی", lat)
    ck(lat["click_to_request_ms"] == 5.0,
       "ت) کلیک→درخواست جدا از RTT", lat)
    ck(lat["request_rtt_ms"] == 210.0, "ث) RTT فقط از شروع/دریافتِ پاسخ", lat)
    ck(lat["response_to_order_id_ms"] == 12.0,
       "ج) پاسخ→order-id", lat)
    ck(lat["order_id_to_queue_ms"] == 900.0,
       "چ) order-id→جایگاه (شاملِ فاصلهٔ polling؛ نه تأخیرِ شبکه)", lat)
    ck(lat["target_error_ms"] == 4.0,
       "ح) خطای هدف فقط دیواری و با عدم‌قطعیتِ ساعت", lat)
    ck(lat["execution_to_request_ms"] == 10.0, "خ) شروع اجرا→درخواست", lat)
    ck(set(lat) == set(METRIC_FIELDS), "د) هیچ معیارِ خارج از فهرست ساخته نمی‌شود",
       sorted(set(lat) ^ set(METRIC_FIELDS)))
    ck("first_fill_ms" not in METRIC_FIELDS and "first_fill_mono_ms" in TELEMETRY_FIELDS,
       "ذ) پر شدن فقط timestamp است، نه تأخیرِ ساختگی")
    body = tel.to_dict()
    ck(body["one_way_ms"] is None and "RTT/2" in body["one_way_reason"],
       "ر) یک‌طرفه از RTT/2 ساخته نمی‌شود", body.get("one_way_reason"))
    ck(body["timezone"].startswith("Asia/Tehran") and body["precision"] == "ms",
       "ز) timezone/precision صریح‌اند", body.get("timezone"))
    ck(all("monotonic" in str(v) or "wall" in str(v)
           for v in body["metric_sources"].values()),
       "ژ) منبعِ هر معیار صریح است", body["metric_sources"])

    empty = ExecutionTelemetry().to_dict()
    ck(all(v is None for v in empty["latencies"].values()),
       "س) بی‌شاهد ⇒ None، نه صفر", empty["latencies"])
    restored = ExecutionTelemetry.from_mapping({
        **tel.to_dict(), "unknown_field": 1, "latencies": {"fake": 0},
    })
    ck(restored.request_started_mono_ms == 5060.0
       and restored.latencies()["request_rtt_ms"] == 210.0,
       "ش) from_mapping فقط فیلدهایِ شاهددار را برمی‌گرداند")

    print("\n── ۲) موتور و مسیرهایِ mock با clockِ کنترل‌شده ──")
    tmp = tempfile.mkdtemp(prefix="round19_")
    store = SC.StrategySettingsStore(os.path.join(tmp, "user.db"))
    intent_store = IS.IntentStore(os.path.join(tmp, "intents.db"))
    common = {
        "order_url": "http://mock.local/order",
        "origin_allowlist": ["http://mock.local"],
        "symbol_selector": "[data-testid=symbol]",
        "form_symbol_selector": "",
        "open_form_selector": "",
        "price_selector": "[data-testid=price]",
        "quantity_selector": "[data-testid=quantity]",
        "submit_selector": "[data-testid=submit]",
        "focus_selector": "[data-testid=submit]",
        "intercept_pattern": "**/mock/order*",
        "order_paths": ["/order", "/mock/order"],
        "order_method": "POST",
        "action_timeout_ms": 300,
        "headless": True,
        "api_path": "/mock/order",
        "profile_dir": os.path.join(tmp, "profile"),
    }
    for sid in SC.ALL_STRATEGIES:
        opts = dict(common)
        if sid == SC.AUTOCLICKER:
            opts.update({"autofill": False, "require_prefilled": True})
        if sid == SC.KEYBOARD:
            opts.update({"key_sequence": ["Enter"]})
        store.save(sid, mode=SC.MODE_SHADOW, options=opts)

    current = {"draft": None, "last_driver": None}

    class FakeAdapter:
        name = "fake"
        writes_allowed = False

        def __init__(self) -> None:
            self.submit_calls = 0

        def submit_order(self, draft):
            self.submit_calls += 1
            raise AssertionError("dry-run must not submit")

        def capabilities(self):
            return Capabilities(place=True, list_orders=True, order_state=True,
                                queue_position=False, cancel=False, balances=False)

    def factory(settings, strategy_id, mock=False, **kw):
        d = current["draft"]
        drv = EB.MockBrowserDriver(
            order_url=settings.options["order_url"],
            intercept_pattern=settings.options["intercept_pattern"],
            on_submit=lambda payload: {
                "status": 200, "body": {"isSuccessful": True, "id": "MOCK-1"}},
            initial_form={"symbol": d.instrument.symbol, "price": "1000",
                          "quantity": "10"})
        current["last_driver"] = drv
        return drv

    clock_ok = lambda: {"verified": True, "delta_ms": 0.0, "rtt_ms": 1.0,
                        "broker_time": "2026-10-22T00:00:00"}
    instr = InstrumentRef(symbol="TEST", ins_code="1", isin="IRO1TEST0001",
                          broker_instrument="IRO1TEST0001",
                          resolution=Resolution.EXACT)

    def make_engine(adapter=None):
        return SE.StrategyEngine(
            adapter or FakeAdapter(), scheduler=Scheduler(TimeSource()),
            settings_store=store, mock_browser=True,
            driver_factory=factory, server_clock=clock_ok,
            live_allowed=False, halted=lambda: (False, ""),
            intent_store=intent_store, recover_intents=False)

    def draft(eid):
        return OrderDraft(execution_id=eid, instrument=instr, side=Side.BUY,
                          price=1000.0, quantity=10.0, mode=OrderMode.SAFE)

    ad = FakeAdapter()
    eng = make_engine(ad)
    old_now = SE.now_ms
    virtual = VirtualClock(start=5000.0, step=2.0)
    SE.now_ms = virtual
    try:
        current["draft"] = draft("R19-API-CLOCK")
        o = eng.prepare(current["draft"], SC.DIRECT_API)
        r = eng.trigger(o.prepared_id, live=False)
    finally:
        SE.now_ms = old_now
    tele = r.telemetry.get("latencies") if r.telemetry else None
    ck(r.status == "dry_run" and ad.submit_calls == 0,
       "الف) API dry-run هیچ ترابری صدا نزد", r.status)
    ck((r.telemetry.get("latencies") or {}).get("preflight_ms") == 6.0,
       "پ) با clockِ کنترل‌شده، preflight عددِ ثابت دارد",
       r.telemetry.get("latencies"))
    ck(tele is not None and tele["execution_to_request_ms"] is None,
       "ت) dry-run مرحلهٔ درخواست ندارد، پس None است", tele)
    ck(tele["request_rtt_ms"] is None and tele["click_to_request_ms"] is None
       and tele["response_to_order_id_ms"] is None,
       "ث) API dry-run هیچ RTT/کلیک/order-id جعل نمی‌کند", tele)
    ck(r.telemetry.get("one_way_ms") is None
       and r.telemetry.get("precision") == "ms",
       "ج) تلمتریِ نتیجه یک‌طرفه و precision صریح دارد",
       r.telemetry.get("one_way_ms"))

    class AcceptingAdapter(FakeAdapter):
        writes_allowed = True

        def submit_order(self, draft):
            self.submit_calls += 1
            virtual2.advance(20.0)         # RTTِ کنترل‌شده، بدونِ شبکه
            return ExecutionRecord(
                execution_id=draft.execution_id, broker="fake", account=None,
                symbol=draft.instrument.symbol, isin=draft.instrument.isin,
                side=draft.side, price=draft.price, quantity=draft.quantity,
                mode=draft.mode, status=ExecutionStatus.ACKNOWLEDGED,
                broker_order_id="O-LIVE-1", order_state=OrderState.PENDING)

    live_ad = AcceptingAdapter()
    store.save(SC.DIRECT_API, mode=SC.MODE_LIVE)
    eng_live = make_engine(live_ad)
    virtual2 = VirtualClock(start=7000.0, step=2.0)
    SE.now_ms = virtual2
    try:
        current["draft"] = draft("R19-API-ACCEPTED")
        o2 = eng_live.prepare(current["draft"], SC.DIRECT_API)
        r2 = eng_live.trigger(o2.prepared_id, live=True, live_allowed=True)
    finally:
        SE.now_ms = old_now
        store.save(SC.DIRECT_API, mode=SC.MODE_SHADOW)
    t2 = r2.telemetry.get("latencies") if r2.telemetry else {}
    ck(r2.status == "submitted" and r2.accepted
       and r2.broker_order_id == "O-LIVE-1" and live_ad.submit_calls == 1,
       "چ) مسیرِ پذیرفته‌شده یک ارسال و order-id صریح", r2.status)
    ck(t2.get("execution_to_request_ms") == 2.0
       and t2.get("request_rtt_ms") == 22.0,
       "ح) RTTِ کنترل‌شده و شروع→درخواست عددِ ثابت دارند", t2)
    ck(t2.get("response_to_order_id_ms") == 0.0
       and r2.telemetry.get("broker_acknowledged_mono_ms") is not None,
       "خ) order-id فقط از پاسخِ همان درخواست ثبت می‌شود", t2)
    ck(t2.get("order_id_to_queue_ms") is None,
       "د) جایگاه در لحظهٔ trigger مشاهده نشده، پس None است", t2)

    current["draft"] = draft("R19-BROWSER-MOCK")
    ob = eng.prepare(current["draft"], SC.PLAYWRIGHT_DOM)
    rb = eng.trigger(ob.prepared_id, live=False)
    bt = rb.telemetry.get("latencies") if rb.telemetry else {}
    ck(rb.status == "dry_run" and rb.request_aborted,
       "چ) مرورگرِ mock در dry-run درخواست را abort می‌کند", rb.status)
    ck(bt.get("click_to_request_ms") is not None
       and bt["click_to_request_ms"] >= 0,
       "ح) کلیک→درخواست در مسیر مرورگر اندازه‌گیری شد", bt)
    ck(bt.get("request_rtt_ms") is None,
       "خ) پاسخِ abort‌شده RTT نمی‌سازد", bt)
    ck(bt.get("preflight_ms") is not None,
       "د) preflight در مسیر مرورگر هم ثبت شد", bt)

    print("\n── ۳) Scheduler: تأخیرِ واقعی نسبت به هدف ──")
    import time as _time
    sched_lags = []
    target_errors = []
    for i in range(5):
        current["draft"] = draft("R19-SCHED-%d" % i)
        target = int(_time.time() * 1000) + 300
        o = eng.prepare(current["draft"], SC.DIRECT_API, target_wall_ms=target)
        rs = eng.trigger(o.prepared_id, live=False)
        lt = rs.telemetry.get("latencies") if rs.telemetry else {}
        if lt.get("scheduler_lag_ms") is not None:
            sched_lags.append(float(lt["scheduler_lag_ms"]))
        if lt.get("target_error_ms") is not None:
            target_errors.append(float(lt["target_error_ms"]))
    ck(len(sched_lags) == 5 and all(-50.0 <= v <= 300.0 for v in sched_lags),
       "الف) ۵ نمونهٔ تأخیرِ Scheduler با شاهدِ monotonic", sched_lags)
    ck(len(target_errors) == 5,
       "پ) خطای هدفِ دیواری برای همان ۵ نمونه ثبت شد", target_errors)
    print("     scheduler_lag_ms p50=%s p95=%s | target_error_ms p50=%s p95=%s"
          % (pct(sched_lags, 0.5), pct(sched_lags, 0.95),
             pct(target_errors, 0.5), pct(target_errors, 0.95)))

    print("\n── ۴) Benchmark موتور رویِ mock (۲۰+۲۰ نمونه؛ نه تأخیرِ کارگزاری) ──")
    api_ms: list[float] = []
    browser_ms: list[float] = []
    for i in range(20):
        current["draft"] = draft("R19-BENCH-API-%d" % i)
        o = eng.prepare(current["draft"], SC.DIRECT_API)
        r = eng.trigger(o.prepared_id, live=False)
        api_ms.append(float(r.timings.get("total") or 0.0))
        current["draft"] = draft("R19-BENCH-BROWSER-%d" % i)
        o = eng.prepare(current["draft"], SC.PLAYWRIGHT_DOM)
        r = eng.trigger(o.prepared_id, live=False)
        browser_ms.append(float(r.timings.get("total") or 0.0))
    ck(len(api_ms) == 20 and len(browser_ms) == 20,
       "الف) ۲۰ نمونه برایِ هر مسیر", (len(api_ms), len(browser_ms)))
    ck(all(v >= 0 for v in api_ms + browser_ms),
       "پ) هیچ تأخیرِ منفی در mock نیست")
    print("     API dry-run total ms     p50=%.2f p95=%.2f max=%.2f"
          % (statistics.median(api_ms), pct(api_ms, 0.95), max(api_ms)))
    print("     Browser mock total ms    p50=%.2f p95=%.2f max=%.2f"
          % (statistics.median(browser_ms), pct(browser_ms, 0.95), max(browser_ms)))
    print("     محدودیت: این عدد فقط سربازِ موتورِ محلی است؛ RTT/صفِ کارگزاری "
          "بدونِ سفارشِ واقعی NOT_MEASURED می‌ماند.")

    print("\n── ۵) قراردادِ جایگاهِ Mofid: POST است و در این راند صدا زده نمی‌شود ──")
    from execution_easytrader import RefusingTransport
    from execution_mofid import MOFID_QUEUE_CONTRACT, MofidAdapter

    qc = MOFID_QUEUE_CONTRACT
    ck(qc["api"]["method"] == "POST" and qc["api"]["invoked"] is False,
       "الف) قراردادِ API مفید POST است و در راند صدا زده نشد", qc["api"])
    ck("/Order/OrderPlace" in qc["api"]["paths"]
       and "/Order/OrderPlaceInfo" in qc["api"]["paths"],
       "پ) مسیرهایِ جایگاه از بستهٔ خودِ مفید", qc["api"]["paths"])
    ck(set(qc["api"]["fields"]) == {"orderId", "orderPlace", "volumeAhead"},
       "ت) فیلدهایِ پاسخ صریح‌اند", qc["api"]["fields"])
    ck(qc["market_sheet"]["usable_as_rank"] is False
       and "aggregate" in qc["market_sheet"]["semantics"],
       "ث) MarketSheet دفترِ تجمیعی است، نه رتبهٔ سفارش")
    ck("0/first not inferred" in qc["rank_semantics"]["orderPlace"]
       and "UNVERIFIED" in qc["rank_semantics"]["volumeAhead"],
       "ج) معنایِ ۰ و واحدِ حجم حدس زده نمی‌شود", qc["rank_semantics"])
    mofid = MofidAdapter(transport=RefusingTransport(), token="fixture-token",
                         read_only=True, writes_allowed=False)
    ck(mofid.capabilities().queue_position is False
       and mofid.get_queue_position("O-1") is None,
       "چ) Mofid capability=false و هیچ رتبهٔ ساختگی نمی‌دهد")

    print("\n── ۶) Queue Monitor: حالت‌ها، سریِ جایگاه و بی‌صفرِ جعلی ──")
    os.environ["BORS_EXECUTION_DB"] = os.path.join(tmp, "execution.db")
    os.environ["BORS_SCHEDULE_DB"] = os.path.join(tmp, "schedules.db")
    os.environ["BORS_OFFERINGS_DB"] = os.path.join(tmp, "offerings.db")
    os.environ["BORS_COCKPIT_DB"] = os.path.join(tmp, "cockpit.db")
    import api.execution as EX

    old_adapter, old_kind, old_block = EX._ACTIVE_ADAPTER, EX.ADAPTER_KIND, EX._source_block
    EX._source_block = lambda: None

    class QueueFake:
        def __init__(self, *, queue_position: bool, snap=None, boom=None,
                     contract=None):
            self._caps = Capabilities(
                place=False, list_orders=True, order_state=True,
                queue_position=queue_position, cancel=False, best_bid_ask=False,
                balances=False)
            self.snap = snap
            self.boom = boom
            self.contract = contract
            self.rows = [ExecutionRecord(
                execution_id="e1", broker="fake", account=None, symbol="TEST",
                isin="IRO1TEST0001", side=Side.BUY, price=1000.0, quantity=10.0,
                mode=OrderMode.SAFE, status=ExecutionStatus.ACKNOWLEDGED,
                broker_order_id="O-1", order_state=OrderState.OPEN,
                events=["ACK"])]

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
                raise AttributeError("no contract")
            return dict(self.contract)

    try:
        EX._QUEUE_SERIES.clear()
        EX.ADAPTER_KIND = "mofid"
        EX._ACTIVE_ADAPTER = QueueFake(queue_position=False,
                                       contract=MOFID_QUEUE_CONTRACT)
        mon = EX._queue_monitor()
        row = (mon.get("rows") or [{}])[0]
        ck(mon.get("queue_supported") is False and mon.get("claims_first_rank") is False,
           "الف) مانیتور ادعای جایگاه/رتبهٔ اول نمی‌کند", mon.get("claims_first_rank"))
        ck(row.get("queue_status") == "UNSUPPORTED_READ_ONLY"
           and row.get("queue_position") is None
           and row.get("volume_ahead") is None,
           "پ) Mofid: جایگاه ناموجود است، نه صفر", row)
        ck("POST" in str(row.get("queue_reason")) and row.get("queue_source") == "none",
           "ت) علتِ نبودِ جایگاه صریح است", row.get("queue_reason"))
        ck(mon.get("contract", {}).get("api", {}).get("method") == "POST",
           "ث) قرارداد در پاسخِ مانیتور هست")

        EX.ADAPTER_KIND = "easytrader"
        EX._ACTIVE_ADAPTER = QueueFake(
            queue_position=True,
            snap=QueueSnapshot(position=0, volume_ahead=0,
                               as_of="2026-10-22T10:00:05",
                               source="easytrader:orderPlace/volumeAhead"))
        m1 = EX._queue_monitor()
        r1 = (m1.get("rows") or [{}])[0]
        ck(r1.get("queue_status") == "KNOWN" and r1.get("queue_position") == 0
           and r1.get("volume_ahead") == 0,
           "ج) مقدارِ خامِ ۰ گزارش می‌شود (نه حذف/نه تفسیر)", r1)
        ck(r1.get("position_semantics", "").find("0 is not interpreted") >= 0
           and r1.get("volume_ahead_unit") == "UNVERIFIED",
           "چ) معنایِ ۰ و واحدِ حجم در ردیف اعلام شده", r1)
        ck(len(r1.get("queue_series") or []) == 1,
           "ح) اولین مشاهده در سری ثبت شد", r1.get("queue_series"))

        EX._ACTIVE_ADAPTER.snap = QueueSnapshot(
            position=5, volume_ahead=400, as_of="2026-10-22T10:00:15",
            source="easytrader:orderPlace/volumeAhead")
        m2 = EX._queue_monitor()
        r2 = (m2.get("rows") or [{}])[0]
        series = r2.get("queue_series") or []
        ck(len(series) == 2 and series[-1].get("position") == 5
           and series[0].get("position") == 0,
           "خ) حرکتِ جایگاه در سری ثبت شد", series)
        EX._queue_monitor()
        r3 = (EX._queue_monitor().get("rows") or [{}])[0]
        ck(len(r3.get("queue_series") or []) == 2,
           "د) مشاهدهٔ تکراری سری را شلوغ نمی‌کند", r3.get("queue_series"))

        EX._ACTIVE_ADAPTER.snap = None
        r4 = (EX._queue_monitor().get("rows") or [{}])[0]
        ck(r4.get("queue_status") == "UNKNOWN"
           and r4.get("queue_position") is None
           and "مقدار" in str(r4.get("queue_reason")),
           "ذ) پاسخِ بی‌مقدار ⇒ UNKNOWN، نه صفر", r4)

        from execution_contract import BrokerError, ErrorCode
        EX._ACTIVE_ADAPTER.boom = BrokerError(ErrorCode.NETWORK_ERROR, "timeout")
        r5 = (EX._queue_monitor().get("rows") or [{}])[0]
        ck(r5.get("queue_status") == "ERROR"
           and r5.get("queue_position") is None,
           "ر) خطای دریافت ⇒ ERROR بدونِ رتبهٔ جعلی", r5)
        ck(isinstance(json.dumps(EX._queue_monitor()), str),
           "ز) پاسخِ مانیتور JSON-safe است")
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        app.include_router(EX.router)
        client = TestClient(app, raise_server_exceptions=False)
        EX._ACTIVE_ADAPTER.boom = None
        EX._ACTIVE_ADAPTER.snap = QueueSnapshot(
            position=2, volume_ahead=100, as_of="2026-10-22T10:00:25",
            source="easytrader:orderPlace/volumeAhead")
        http = client.get("/api/execution/queue-monitor")
        hbody = http.json() if http.status_code == 200 else {}
        ck(http.status_code == 200 and hbody.get("claims_first_rank") is False
           and (hbody.get("rows") or [{}])[0].get("queue_status") == "KNOWN",
           "س) مسیرِ HTTP مانیتور همان قرارداد را می‌دهد", http.status_code)
    finally:
        EX._ACTIVE_ADAPTER, EX.ADAPTER_KIND, EX._source_block = (
            old_adapter, old_kind, old_block)
        EX._QUEUE_SERIES.clear()

    print("\n%d pass / %d fail" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
