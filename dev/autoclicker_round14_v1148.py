#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""autoclicker_round14_v1148 — گاردِ سریعِ P0-1..P0-5 (بدونِ شبکه).

پوشش:
  ۱) گاردِ dry-run مستقل از الگویِ کاربر؛ path/host/method/query/redirect.
  ۲) idempotency پایدار: کلیدِ صریح، UNKNOWN، restart، reconcile.
  ۳) فرمِ سمت‌محور، انتخابگرِ یگانه، دکمهٔ غیرفعال، تغییرِ فرم پیش از کلیک.
  ۴) پیش‌فرود/سقفِ واقعی رویِ مسیرِ کلیکِ زنده.
  ۵) scheduled/abort/restart و هدفِ تهران.
هیچ سوکت و هیچ سفارشِ واقعی در این گارد نیست؛ MockBrowserDriver استفاده می‌شود.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
import time
import types
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PASS = FAIL = SKIP = 0


def ck(cond, label, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("ok   " + label)
    else:
        FAIL += 1
        print("FAIL " + label + "  -> " + str(detail)[:260])


def main() -> int:
    import execution_browser as EB
    import execution_intent_store as IS
    import execution_strategy_core as SC
    import execution_strategy_engine as SE
    import execution_timing as T
    from execution_contract import (
        Capabilities, InstrumentRef, OrderDraft, OrderMode, OrderState, Side,
        Resolution,
    )
    from execution_service import ExecutionService, Limits

    tmp = tempfile.mkdtemp(prefix="ac14_")
    db = os.path.join(tmp, "user.db")
    settings_store = SC.StrategySettingsStore(db)
    intent_store = IS.IntentStore(os.path.join(tmp, "intents.db"))

    common = {
        "order_url": "http://mock.local/core/api/v2/order",
        "origin_allowlist": ["http://mock.local"],
        "symbol_selector": "[data-testid=symbol]",
        "form_symbol_selector": "",
        "open_form_selector": "",
        "open_form_selector_buy": "",
        "open_form_selector_sell": "",
        "price_selector": "[data-testid=price]",
        "quantity_selector": "[data-testid=quantity]",
        "submit_selector": "[data-testid=submit]",
        "submit_selector_buy": "[data-testid=submit-buy]",
        "submit_selector_sell": "[data-testid=submit-sell]",
        "form_selector": "",
        "side_selector": "",
        "isin_selector": "",
        "intercept_pattern": "**/core/api/v2/order*",
        "order_paths": ["/core/api/v2/order"],
        "order_method": "POST",
        "action_timeout_ms": 150,
        "response_timeout_ms": 80,
        "autofill": False,
        "require_prefilled": True,
        "headless": True,
        "profile_dir": os.path.join(tmp, "profile"),
    }
    for sid in (SC.AUTOCLICKER, SC.PLAYWRIGHT_DOM):
        settings_store.save(sid, mode=SC.MODE_SHADOW, options=dict(common))

    instr = InstrumentRef(symbol="TEST", ins_code="1", isin="IRO1TEST0001",
                          broker_instrument="IRO1TEST0001",
                          resolution=Resolution.EXACT)

    def draft(eid, side=Side.BUY, price=1000.0, qty=10.0):
        return OrderDraft(execution_id=eid, instrument=instr, side=side,
                          price=price, quantity=qty, mode=OrderMode.SAFE)

    class FakeAdapter:
        name = "fake"

        def __init__(self, *, writes_allowed=False, balances=None, sellable=None,
                     rows=None):
            self.writes_allowed = bool(writes_allowed)
            self.balances = balances
            self.sellable = sellable
            self.rows = list(rows or [])
            self.submit_calls = 0

        def submit_order(self, _draft):
            self.submit_calls += 1
            raise AssertionError("submit_order must not run in AutoClicker tests")

        def capabilities(self):
            return Capabilities(place=True, list_orders=True, order_state=True,
                                queue_position=False, cancel=False,
                                balances=self.balances is not None)

        def get_balances(self):
            return dict(self.balances or {})

        def get_sellable_quantity(self, _isin):
            return self.sellable

        def get_orders(self):
            return list(self.rows)

    current = {
        "draft": None, "form": None, "driver": None,
        "request_url": "", "request_method": "POST",
        "selector_counts": {}, "suppress_response": False,
        "before_wait": None, "before_click": None,
        "submit_enabled": True, "submit_visible": True,
        "side_text": "", "response": None,
    }

    def factory(settings, strategy_id, mock=False, **kw):
        d = current["draft"]
        side = d.side
        form = current["form"]
        if form is None:
            form = {"symbol": d.instrument.symbol, "price": str(int(d.price or 0)),
                    "quantity": str(int(d.quantity or 0)),
                    "isin": d.instrument.isin}
        drv = EB.MockBrowserDriver(
            order_url=settings.options["order_url"],
            intercept_pattern=settings.options["intercept_pattern"],
            on_submit=lambda _p: current["response"] or {
                "status": 200,
                "body": {"isSuccessful": True, "id": "MOCK-1"}},
            initial_form=form)
        drv.submit_text = "ارسال فروش" if side is Side.SELL else "ارسال خرید"
        drv.side_text = current["side_text"] or (
            "فروش" if side is Side.SELL else "خرید")
        drv.submit_enabled = bool(current["submit_enabled"])
        drv.submit_visible = bool(current["submit_visible"])
        drv.request_url = current["request_url"]
        drv.request_method = current["request_method"]
        drv.selector_counts = dict(current["selector_counts"])
        drv.before_wait = current["before_wait"]
        drv.before_click = current["before_click"]
        drv.suppress_response = bool(current["suppress_response"])
        current["driver"] = drv
        return drv

    clock_ok = lambda: {"verified": True, "delta_ms": 0.0, "rtt_ms": 1.0,
                        "broker_time": "2026-10-21T00:00:00"}

    def make_engine(adapter=None, *, live=False, gate=None, scheduler=None,
                    recover=False, store=None):
        return SE.StrategyEngine(
            adapter or FakeAdapter(), settings_store=settings_store,
            mock_browser=True, driver_factory=factory, server_clock=clock_ok,
            live_allowed=live, halted=lambda: (False, ""),
            intent_store=store or intent_store, preflight_gate=gate,
            recover_intents=recover, scheduler=scheduler)

    def reset_form(d=None):
        current["form"] = None
        current["request_url"] = ""
        current["request_method"] = "POST"
        current["selector_counts"] = {}
        current["suppress_response"] = False
        current["before_wait"] = None
        current["before_click"] = None
        current["submit_enabled"] = True
        current["submit_visible"] = True
        current["side_text"] = ""
        current["response"] = None
        if d is not None:
            current["draft"] = d

    def prep(eng, d, **kw):
        current["draft"] = d
        return eng.prepare(d, SC.AUTOCLICKER, **kw)

    def fire(eng, order, **kw):
        return eng.trigger(order.prepared_id, live=False, **kw)

    # ── ۱) dry-run guard ────────────────────────────────────────────────────
    print("\n── ۱) dry-run مستقل از الگویِ کاربر ──")
    eng = make_engine()
    cases = [
        ("standard", "", "POST", "dry_run"),
        ("path", "http://mock.local/other/order", "POST", "blocked"),
        ("host", "http://evil.local/core/api/v2/order", "POST", "dry_run"),
        ("method", "", "PATCH", "blocked"),
        ("query", "http://mock.local/core/api/v2/order?x=1", "POST", "dry_run"),
        ("redirect/alt", "http://mock.local/redirect", "POST", "blocked"),
    ]
    for i, (label, url, method, want) in enumerate(cases):
        d = draft("G-DRY-%d" % i)
        reset_form(d)
        current["request_url"] = url
        current["request_method"] = method
        o = prep(eng, d)
        r = fire(eng, o)
        drv = current["driver"]
        ck(r.status == want and drv.order_endpoint_hits == 0
           and len(drv.blocked_writes) >= 1,
           "dry-run %s: endpoint=0، نوشتن مسدود" % label,
           {"status": r.status, "code": r.error_code,
            "hits": drv.order_endpoint_hits, "blocked": len(drv.blocked_writes),
            "ev": r.evidence})
    # الگویِ عمداً غلط
    settings_store.save(SC.AUTOCLICKER, options={
        "intercept_pattern": "**/never-match-order*"})
    d = draft("G-DRY-PATTERN")
    reset_form(d)
    o = prep(eng, d)
    r = fire(eng, o)
    ck(r.status == "dry_run" and current["driver"].order_endpoint_hits == 0,
       "dry-run با الگویِ غلط: گاردِ catch-all مانع شد",
       {"status": r.status, "ev": r.evidence})
    settings_store.save(SC.AUTOCLICKER, options={
        "intercept_pattern": common["intercept_pattern"]})

    # ── ۲) idempotency ──────────────────────────────────────────────────────
    print("\n── ۲) idempotency و UNKNOWN ──")
    d1 = draft("G-ID-1")
    reset_form(d1)
    prep(eng, d1, intent_key="K-SAME")
    d2 = draft("G-ID-2")
    reset_form(d2)
    try:
        prep(eng, d2, intent_key="K-SAME")
        same_key_blocked = False
    except Exception as e:                       # noqa: BLE001
        same_key_blocked = "DUPLICATE_GUARD" in str(e)
    ck(same_key_blocked, "دو execution_id با یک intent_key دوباره prepare نمی‌شود")

    # دو Strategy با یک کلید: prepare مجاز، کلیک فقط یک‌بار
    d3 = draft("G-ID-3")
    reset_form(d3)
    o3 = prep(eng, d3, intent_key="K-SHADOW")
    d4 = draft("G-ID-4")
    reset_form(d4)
    o4 = eng.prepare(d4, SC.PLAYWRIGHT_DOM, intent_key="K-SHADOW")
    r3 = fire(eng, o3)
    r4 = fire(eng, o4)
    ck(r3.status == "dry_run" and r4.status == "blocked"
       and o3.prepared.driver.click_count == 1
       and o4.prepared.driver.click_count == 0,
       "دو Strategy یک قصد: فقط کلیکِ اول",
       {"r3": r3.status, "r4": r4.status,
        "clicks3": o3.prepared.driver.click_count,
        "clicks4": o4.prepared.driver.click_count})

    # UNKNOWN بعد از کلیکِ زندهٔ ساختگی
    settings_store.save(SC.AUTOCLICKER, mode=SC.MODE_LIVE)
    adapter_ok = FakeAdapter(writes_allowed=True,
                             balances={"buying_power": 10_000_000},
                             rows=[SimpleNamespace(
                                 isin=instr.isin, side=Side.BUY, price=1000.0,
                                 quantity=10.0, broker_order_id="B-UNKNOWN",
                                 order_state=OrderState.UNKNOWN)])
    gate_ok = lambda _d: SimpleNamespace(ok=True, checks={"place": "PASS"})
    eng_live = make_engine(adapter_ok, live=True, gate=gate_ok)
    d5 = draft("G-UNKNOWN")
    reset_form(d5)
    current["suppress_response"] = True
    o5 = prep(eng_live, d5, intent_key="K-UNKNOWN")
    r5 = eng_live.trigger(o5.prepared_id, live=True, live_allowed=True)
    row5 = intent_store.get("K-UNKNOWN")
    ck(r5.status == "unknown" and r5.unknown
       and row5 is not None and row5["state"] == "unknown"
       and current["driver"].click_count == 1,
       "پاسخِ نیامده ⇒ UNKNOWN و قصد قفل ماند",
       {"status": r5.status, "state": row5 and row5["state"]})
    try:
        prep(eng_live, draft("G-UNKNOWN-2"), intent_key="K-UNKNOWN")
        unknown_reblocked = False
    except Exception as e:                       # noqa: BLE001
        unknown_reblocked = "DUPLICATE_GUARD" in str(e)
    ck(unknown_reblocked, "UNKNOWN تا reconcile اجازهٔ قصدِ تازه با همان کلید را نمی‌دهد")
    rec = eng_live.reconcile(o5.prepared_id)
    row5b = intent_store.get("K-UNKNOWN")
    ck(rec.status == "reconciled" and row5b is not None
       and row5b["state"] == "confirmed",
       "reconcile یکتای سفارش ⇒ confirmed", {"rec": rec.status,
                                             "state": row5b and row5b["state"]})
    try:
        prep(eng_live, draft("G-UNKNOWN-3"), intent_key="K-UNKNOWN")
        confirmed_reblocked = False
    except Exception as e:                       # noqa: BLE001
        confirmed_reblocked = "DUPLICATE_GUARD" in str(e)
    ck(confirmed_reblocked, "پس از confirmed همان کلید دوباره کلیک نمی‌شود")
    ck(intent_store.get("K-NEW") is None,
       "قصدِ تازه هنوز وجود ندارد")
    current["suppress_response"] = False
    settings_store.save(SC.AUTOCLICKER, mode=SC.MODE_SHADOW)

    # timeout پیش از کلیک: دکمهٔ ناپیدا ⇒ failed_pre_click و تلاشِ دوباره
    d6 = draft("G-PRECLICK")
    reset_form(d6)
    current["submit_visible"] = False
    o6 = prep(eng, d6, intent_key="K-PRECLICK")
    r6 = fire(eng, o6)
    row6 = intent_store.get("K-PRECLICK")
    ck(r6.status == "blocked" and r6.error_code == "SUBMIT_NOT_READY"
       and row6 is not None and row6["state"] == "failed_pre_click"
       and current["driver"].click_count == 0,
       "timeout پیش از کلیک ⇒ failed_pre_click و صفر کلیک",
       {"status": r6.status, "code": r6.error_code,
        "state": row6 and row6["state"]})
    current["submit_visible"] = True
    reset_form(d6)
    o6b = prep(eng, d6, intent_key="K-PRECLICK")
    r6b = fire(eng, o6b)
    ck(r6b.status == "dry_run", "پس از خطایِ پیش از کلیک، همان قصد قابلِ تلاش است",
       {"status": r6b.status})

    d_prep = draft("G-PREP-RETRY")
    reset_form(d_prep)
    current["form"] = {"symbol": "TEST", "price": "999", "quantity": "10"}
    try:
        prep(eng, d_prep, intent_key="K-PREP-RETRY")
        prep_failed = False
    except Exception as e:                       # noqa: BLE001
        prep_failed = "PRICE_MISMATCH" in str(e)
    reset_form(d_prep)
    o_prep = prep(eng, d_prep, intent_key="K-PREP-RETRY")
    r_prep = fire(eng, o_prep)
    ck(prep_failed and r_prep.status == "dry_run",
       "prepareِ ناموفق با همان قصد و پس از اصلاحِ فرم قابلِ تلاش است",
       {"failed": prep_failed, "status": r_prep.status})

    # ── ۳) فرم سمت‌محور ────────────────────────────────────────────────────
    print("\n── ۳) فرم و انتخابگرِ سمت‌محور ──")
    d_buy = draft("G-FORM-BUY")
    reset_form(d_buy)
    o_buy = prep(eng, d_buy)
    r_buy = fire(eng, o_buy)
    clicked_buy = [e.get("selector", "") for e in current["driver"].events
                   if e.get("kind") == "click"]
    ck(r_buy.status == "dry_run" and clicked_buy
       and "submit" in clicked_buy[-1],
       "فرمِ خرید با انتخابگرِ خرید",
       {"status": r_buy.status, "clicked": clicked_buy})

    d_sell = draft("G-FORM-SELL", side=Side.SELL)
    reset_form(d_sell)
    o_sell = prep(eng, d_sell)
    r_sell = fire(eng, o_sell)
    clicked = [e.get("selector", "") for e in current["driver"].events
               if e.get("kind") == "click"]
    ck(r_sell.status == "dry_run" and clicked
       and "submit-sell" in clicked[-1],
       "فرمِ فروش با انتخابگرِ فروش", {"status": r_sell.status, "clicked": clicked})

    for label, form, code in (
            ("نماد", {"symbol": "OTHER", "price": "1000", "quantity": "10"},
             "SYMBOL_MISMATCH"),
            ("قیمت", {"symbol": "TEST", "price": "999", "quantity": "10"},
             "PRICE_MISMATCH"),
            ("تعداد", {"symbol": "TEST", "price": "1000", "quantity": "7"},
             "QUANTITY_MISMATCH")):
        d_bad = draft("G-FORM-%s" % label)
        reset_form(d_bad)
        current["form"] = form
        try:
            prep(eng, d_bad)
            blocked = False
            got = ""
        except Exception as e:                   # noqa: BLE001
            blocked = code in str(e)
            got = str(e)
        ck(blocked and current["driver"].click_count == 0,
           "فرمِ %s ناهماهنگ ⇒ %s و صفر کلیک" % (label, code), got[:120])

    d_dis = draft("G-FORM-DISABLED")
    reset_form(d_dis)
    current["submit_enabled"] = False
    try:
        prep(eng, d_dis)
        dis_blocked = False
    except Exception as e:                       # noqa: BLE001
        dis_blocked = "SUBMIT_DISABLED" in str(e)
    ck(dis_blocked, "دکمهٔ غیرفعال ⇒ SUBMIT_DISABLED")

    d_multi = draft("G-FORM-MULTI")
    reset_form(d_multi)
    current["selector_counts"] = {"[data-testid=submit]": 2}
    try:
        prep(eng, d_multi)
        multi_blocked = False
    except Exception as e:                       # noqa: BLE001
        multi_blocked = "FORM_NOT_UNIQUE" in str(e)
    ck(multi_blocked, "چند دکمهٔ مشابه ⇒ FORM_NOT_UNIQUE")

    d_toctou = draft("G-FORM-TOCTOU")
    reset_form(d_toctou)
    current["before_wait"] = lambda: current["driver"].form.__setitem__("price", "999")
    o_toctou = prep(eng, d_toctou)
    r_toctou = fire(eng, o_toctou)
    ck(r_toctou.status == "blocked" and r_toctou.error_code == "PRICE_MISMATCH"
       and current["driver"].click_count == 0,
       "تغییرِ قیمت پس از validation و پیش از کلیک گرفته می‌شود",
       {"status": r_toctou.status, "code": r_toctou.error_code})

    d_side = draft("G-FORM-SIDE")
    reset_form(d_side)
    current["side_text"] = "فروش"
    try:
        prep(eng, d_side)
        side_blocked = False
    except Exception as e:                       # noqa: BLE001
        side_blocked = "SIDE_UNVERIFIED" in str(e)
    ck(side_blocked, "سمتِ ناهماهنگ ⇒ SIDE_UNVERIFIED")

    # ── ۴) preflight رویِ مسیرِ کلیکِ زنده ──────────────────────────────────
    print("\n── ۴) preflight و سقف‌هایِ ریسک ──")
    settings_store.save(SC.AUTOCLICKER, mode=SC.MODE_LIVE)
    svc = ExecutionService(
        FakeAdapter(writes_allowed=True,
                    balances={"buying_power": 500.0, "source": "test"}),
        dry_run=False, limits=Limits(max_order_value=1_000_000))
    gate_real = svc.dispatch_preflight
    eng_pf = make_engine(FakeAdapter(writes_allowed=True), live=True,
                         gate=gate_real)
    d_pf = draft("G-PF-BP", price=1000.0, qty=10.0)
    reset_form(d_pf)
    o_pf = prep(eng_pf, d_pf)
    try:
        eng_pf.trigger(o_pf.prepared_id, live=True, live_allowed=True)
        pf_blocked = False
        pf_detail = ""
    except Exception as e:                       # noqa: BLE001
        pf_blocked = "PREFLIGHT_BLOCKED" in str(e)
        pf_detail = str(e)
    ck(pf_blocked and current["driver"].click_count == 0,
       "قدرتِ خریدِ ناکافی پیش از کلیک مسدود می‌شود", pf_detail[:160])

    svc_sell = ExecutionService(
        FakeAdapter(writes_allowed=True, sellable=1, balances={}),
        dry_run=False, limits=Limits())
    eng_pf_sell = make_engine(FakeAdapter(writes_allowed=True), live=True,
                              gate=svc_sell.dispatch_preflight)
    d_pf_sell = draft("G-PF-SELL", side=Side.SELL, price=1000.0, qty=10.0)
    reset_form(d_pf_sell)
    o_pf_sell = prep(eng_pf_sell, d_pf_sell)
    try:
        eng_pf_sell.trigger(o_pf_sell.prepared_id, live=True, live_allowed=True)
        pf_sell_blocked = False
    except Exception as e:                       # noqa: BLE001
        pf_sell_blocked = "PREFLIGHT_BLOCKED" in str(e)
    ck(pf_sell_blocked and current["driver"].click_count == 0,
       "تعدادِ قابلِ‌فروشِ ناکافی پیش از کلیک مسدود می‌شود")

    gate_calls = []
    def gate_value(_d):
        gate_calls.append(1)
        return SimpleNamespace(ok=True, checks={})
    eng_pf_ok = make_engine(FakeAdapter(writes_allowed=True), live=True,
                            gate=gate_value)
    d_pf_ok = draft("G-PF-OK")
    reset_form(d_pf_ok)
    current["suppress_response"] = True
    o_pf_ok = prep(eng_pf_ok, d_pf_ok)
    r_pf_ok = eng_pf_ok.trigger(o_pf_ok.prepared_id, live=True, live_allowed=True)
    ck(gate_calls and r_pf_ok.status == "unknown"
       and current["driver"].order_endpoint_hits == 1,
       "preflight موفق ⇒ کلیکِ واحد و نتیجهٔ unknown", r_pf_ok.status)
    current["suppress_response"] = False
    settings_store.save(SC.AUTOCLICKER, mode=SC.MODE_SHADOW)

    # ── ۵) زمان، abort، restart ─────────────────────────────────────────────
    print("\n── ۵) scheduled/abort/restart/timezone ──")
    ts = T.TimeSource()
    epoch = ts.from_tehran_local("2026-10-22T08:45:00")
    ck(ts.label(epoch).startswith("2026-10-22T08:45:00"),
       "ورودیِ بی‌offset به Asia/Tehran تفسیر می‌شود", ts.label(epoch))
    d_past = draft("G-PAST")
    try:
        prep(eng, d_past, target_wall_ms=int(time.time() * 1000) - 1000)
        past_blocked = False
    except Exception as e:                       # noqa: BLE001
        past_blocked = "TARGET_IN_PAST" in str(e)
    ck(past_blocked, "هدفِ گذشته رد می‌شود")

    sched = T.Scheduler(T.TimeSource(), spin_window_ms=5)
    eng_sched = make_engine(scheduler=sched)
    d_future = draft("G-FUTURE")
    reset_form(d_future)
    target = int(time.time() * 1000) + 350
    o_future = prep(eng_sched, d_future, target_wall_ms=target)
    t0 = time.monotonic()
    r_future = fire(eng_sched, o_future)
    elapsed = time.monotonic() - t0
    ck(r_future.status == "dry_run" and current["driver"].click_count == 1
       and elapsed >= 0.2,
       "scheduledِ آینده اجرا شد و یک کلیک", {"status": r_future.status,
                                             "elapsed": round(elapsed, 3)})
    tm = r_future.timings or {}
    ck(tm.get("target_wall_ms") == target
       and tm.get("one_way_ms", "missing") is None
       and tm.get("rtt_ms", "missing") is None
       and tm.get("click_to_request_ms") is not None,
       "زمان‌ها تفکیک شده‌اند؛ one-way/RTT ادعا نشده",
       {"timings": tm})

    d_abort = draft("G-ABORT")
    reset_form(d_abort)
    o_abort = prep(eng_sched, d_abort,
                   target_wall_ms=int(time.time() * 1000) + 2500)
    box = {}

    def runner():
        box["r"] = fire(eng_sched, o_abort)

    th = threading.Thread(target=runner, daemon=True)
    th.start()
    time.sleep(0.25)
    eng_sched.abort(o_abort.prepared_id)
    th.join(timeout=3)
    r_abort = box.get("r")
    ck(r_abort is not None and r_abort.status == "aborted"
       and current["driver"].click_count == 0,
       "Abort زمان‌بند را بیدار می‌کند و کلیک صفر می‌ماند",
       {"result": r_abort and r_abort.status,
        "clicks": current["driver"].click_count})

    restart_path = os.path.join(tmp, "restart_intents.db")
    rs = IS.IntentStore(restart_path)
    d_rs = draft("G-RESTART")
    rs.begin(intent_key="K-RESTART", execution_id=d_rs.execution_id,
             strategy_id=SC.AUTOCLICKER, draft=d_rs, target_wall_ms=None)
    rs.mark_scheduled("K-RESTART")
    clicks_before = current["driver"].click_count
    eng_restart = make_engine(store=IS.IntentStore(restart_path), recover=True)
    row_rs = rs.get("K-RESTART")
    ck(row_rs is not None and row_rs["state"] == "aborted"
       and current["driver"].click_count == clicks_before,
       "restart کارِ scheduled را خودکار اجرا نمی‌کند (aborted)",
       row_rs and row_rs["state"])

    shutil.rmtree(tmp, ignore_errors=True)
    print("\n%d checks, %d failed, %d skipped" % (PASS + FAIL, FAIL, SKIP))
    print("AUTOCLICKER ROUND14 " + ("OK" if FAIL == 0 else "FAILED"))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
