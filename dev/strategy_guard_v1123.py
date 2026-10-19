#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""strategy_guard_v1123 — قراردادِ Strategyهای چندروشی، بدونِ شبکه.

می‌سنجد:
  ۱) تنظیماتِ غیرمحرمانه و ردِ کلیدِ رازدار.
  ۲) p50/p95/p99 فقط از نمونهٔ واقعی؛ نمونهٔ کم ⇒ None.
  ۳) arbiter: چند prepare، یک submit؛ UNKNOWN هیچ fallbackی نمی‌دهد.
  ۴) Direct API در dry-run هیچ ترابری صدا نمی‌زند.
  ۵) AutoClicker/DOM/JS/Keyboard با mock browser: درخواست دیده و abort می‌شود.
  ۶) تطبیقِ قیمت/حجم/نماد و توقفِ سخت در mismatch؛ یک کلیک، بی‌حلقهٔ کور.
  ۷) ساعتِ نامعتبر در قصدِ زنده prepare را می‌بندد.
  ۸) reconcile فقط با تطبیقِ یکتای فیلدها؛ نبود/ابهام ⇒ نامعلوم.
هیچ سوکت و هیچ سفارشِ واقعی در این گارد نیست.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import tempfile

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
        print("FAIL " + label + "  -> " + str(detail)[:220])


class _Tripwire:
    def __init__(self):
        self.hits = []
        self._old = socket.socket

    def __enter__(self):
        outer = self

        class Guarded(outer._old):
            def connect(self, addr, *a, **k):
                outer.hits.append(addr)
                raise OSError("network disabled in strategy guard")

        socket.socket = Guarded
        return self

    def __exit__(self, *exc):
        socket.socket = self._old
        return False


def main() -> int:
    import execution_browser as EB
    import execution_strategy_core as SC
    import execution_strategy_engine as SE
    from execution_contract import (
        Capabilities, ExecutionRecord, InstrumentRef, OrderDraft, OrderMode,
        OrderState, Resolution, Side,
    )

    tmp = tempfile.mkdtemp(prefix="strategy_guard_")
    db = os.path.join(tmp, "user.db")
    store = SC.StrategySettingsStore(db)
    common = {
        "order_url": "http://mock.local/order",
        "origin_allowlist": ["http://mock.local"],
        "symbol_selector": "[data-testid=symbol]",
        "price_selector": "[data-testid=price]",
        "quantity_selector": "[data-testid=quantity]",
        "submit_selector": "[data-testid=submit]",
        "focus_selector": "[data-testid=submit]",
        "intercept_pattern": "**/mock/order*",
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

    print("\n── ۱) تنظیمات: راز و اعتبار ──")
    try:
        store.save(SC.AUTOCLICKER, options={"token": "must-not-store"})
        bad_secret = False
    except ValueError:
        bad_secret = True
    ck(bad_secret, "الف) کلیدِ token در تنظیمات رد می‌شود")
    try:
        store.save(SC.AUTOCLICKER, mode="live-ish")
        bad_mode = False
    except ValueError:
        bad_mode = True
    ck(bad_mode, "پ) mode ناشناخته رد می‌شود")
    try:
        store.save(SC.AUTOCLICKER, priority=101)
        bad_prio = False
    except ValueError:
        bad_prio = True
    ck(bad_prio, "ت) priority بیرونِ 0..100 رد می‌شود")

    print("\n── ۲) معیارها ──")
    met = SC.StrategyMetrics()
    for i in range(20):
        met.record(SC.DIRECT_API, "total", 10 + i, ok=True)
    s = met.summary(SC.DIRECT_API)["total"]
    ck(s["count"] == 20 and s["p50"] is not None and s["p95"] is not None
       and s["p99"] is not None, "الف) ۲۰ نمونه ⇒ p50/p95/p99 دارند", s)
    met.record(SC.PLAYWRIGHT_DOM, "total", 7.0, ok=True)
    s2 = met.summary(SC.PLAYWRIGHT_DOM)["total"]
    ck(s2["count"] == 1 and s2["p95"] is None and s2["p99"] is None
       and s2["thin"] is True, "پ) نمونهٔ کم ⇒ p95/p99=None، نه صفر", s2)

    print("\n── ۳) arbiter ──")
    arb = SC.IntentArbiter()
    ck(arb.reserve("I1", SC.DIRECT_API)[0] and arb.reserve("I1", SC.PLAYWRIGHT_DOM)[0],
       "الف) چند Strategy می‌توانند prepare کنند")
    ck(arb.claim("I1", SC.DIRECT_API)[0], "پ) یک Strategy claim می‌کند")
    ck(arb.claim("I1", SC.PLAYWRIGHT_DOM)[0] is False,
       "ت) Strategy دوم claim نمی‌گیرد")
    arb.mark_unknown("I1", SC.DIRECT_API, "timeout")
    ck(arb.claim("I1", SC.DIRECT_API)[0] is False,
       "ث) بعد از UNKNOWN هیچ claimی نیست (اول reconcile)")

    print("\n── ۴) رتبه‌بندی ──")
    met2 = SC.StrategyMetrics()
    for _ in range(20):
        met2.record("fast", "total", 10.0, ok=True)
        met2.record("slow", "total", 30.0, ok=True)
    ranked = SC.rank_strategies(met2, ["slow", "fast"], min_samples=5)
    ck(ranked[0]["strategy"] == "fast" and ranked[0]["usable"] is True,
       "الف) سریع‌ترین با نمونهٔ کافی اول می‌آید", ranked[:2])

    class FakeAdapter:
        name = "fake"

        def __init__(self, *, writes_allowed: bool = False):
            self.writes_allowed = bool(writes_allowed)
            self.submit_calls = 0
            self.rows = []

        def submit_order(self, draft):
            self.submit_calls += 1
            raise AssertionError("submit_order must not run in dry-run")

        def capabilities(self):
            return Capabilities(place=True, list_orders=True, order_state=True,
                                queue_position=False, cancel=False, balances=False)

        def get_orders(self):
            return list(self.rows)

    current = {"draft": None, "form": None, "response_override": None}

    def factory(settings, strategy_id, mock=False, **kw):
        d = current["draft"]
        form = current["form"] or {"symbol": d.instrument.symbol,
                                   "price": "1000", "quantity": "10"}
        return EB.MockBrowserDriver(
            order_url=settings.options["order_url"],
            intercept_pattern=settings.options["intercept_pattern"],
            on_submit=lambda payload: current["response_override"] or {
                "status": 200, "body": {"isSuccessful": True, "id": "MOCK-1"}},
            initial_form=form)

    clock_ok = lambda: {"verified": True, "delta_ms": 0.0, "rtt_ms": 1.0,
                        "broker_time": "2026-10-20T00:00:00"}
    instr = InstrumentRef(symbol="TEST", ins_code="1", isin="IRO1TEST0001",
                          broker_instrument="IRO1TEST0001",
                          resolution=Resolution.EXACT)

    def make_engine(adapter=None, *, live=False):
        return SE.StrategyEngine(
            adapter or FakeAdapter(), settings_store=store, mock_browser=True,
            driver_factory=factory, server_clock=clock_ok,
            live_allowed=live, halted=lambda: (False, ""))

    def draft(eid, price=1000.0, qty=10.0):
        return OrderDraft(execution_id=eid, instrument=instr, side=Side.BUY,
                          price=price, quantity=qty, mode=OrderMode.SAFE)

    print("\n── ۵) dry-runِ همهٔ Strategyها، صفر ترابریِ واقعی ──")
    with _Tripwire() as trip:
        ad = FakeAdapter()
        eng = make_engine(ad)
        for sid in (SC.DIRECT_API, SC.AUTOCLICKER, SC.PLAYWRIGHT_DOM,
                    SC.JAVASCRIPT, SC.KEYBOARD):
            d = draft("G-%s" % sid)
            current["draft"] = d
            current["form"] = None
            try:
                o = eng.prepare(d, sid)
                r = eng.trigger(o.prepared_id, live=False)
                if sid == SC.DIRECT_API:
                    ok = r.status == "dry_run" and not r.request_aborted
                else:
                    ok = (r.status == "dry_run" and r.request_aborted
                          and r.evidence.get("request_seen") is True)
                ck(ok, "%s: dry-run امن" % sid,
                   {"status": r.status, "aborted": r.request_aborted,
                    "evidence": r.evidence})
            except Exception as e:                   # noqa: BLE001
                ck(False, "%s: dry-run" % sid, "%s: %s" % (type(e).__name__, e))
        ck(ad.submit_calls == 0, "الف) submit_order هرگز صدا زده نشد", ad.submit_calls)
        ck(not trip.hits, "پ) هیچ سوکتِ واقعی باز نشد", trip.hits)

    print("\n── ۶) تطبیق و توقفِ سخت ──")
    eng = make_engine()
    d = draft("G-MISMATCH", price=1000.0)
    current["draft"] = d
    current["form"] = {"symbol": "TEST", "price": "999", "quantity": "10"}
    try:
        eng.prepare(d, SC.AUTOCLICKER)
        mismatch_blocked = False
    except Exception as e:                           # noqa: BLE001
        mismatch_blocked = "PRICE_MISMATCH" in str(e)
    ck(mismatch_blocked, "الف) AutoClicker با قیمتِ ناهمسان متوقف می‌شود")

    store.save(SC.KEYBOARD, options={"key_sequence": ["Enter", "Enter"]})
    d2 = draft("G-KEYS")
    current["draft"] = d2
    current["form"] = None
    o2 = eng.prepare(d2, SC.KEYBOARD)
    r2 = eng.trigger(o2.prepared_id, live=False)
    ck(r2.status == "blocked" and r2.error_code == "MULTIPLE_SUBMIT_KEYS",
       "پ) دو کلیدِ ارسال ⇒ توقف، نه دو کلیک", r2.public())
    store.save(SC.KEYBOARD, options={"key_sequence": ["Enter"]})

    print("\n── ۷) یک intent، یک مسیر ──")
    eng = make_engine()
    d3 = draft("G-ONE")
    current["draft"] = d3
    current["form"] = None
    a = eng.prepare(d3, SC.DIRECT_API)
    b = eng.prepare(d3, SC.PLAYWRIGHT_DOM)
    ra = eng.trigger(a.prepared_id, live=False)
    try:
        eng.trigger(b.prepared_id, live=False)
        second_allowed = True
        why = ""
    except Exception as e:                           # noqa: BLE001
        second_allowed = False
        why = str(e)[:120]
    ck(ra.status == "dry_run" and not second_allowed,
       "الف) مسیرِ دوم برای همان intent مسدود شد", why)
    try:
        eng.trigger(a.prepared_id, live=False)
        repeat_allowed = True
    except Exception:
        repeat_allowed = False
    ck(not repeat_allowed, "پ) تکرارِ همان مسیر هم مسدود است")

    print("\n── ۸) ساعتِ نامعتبر در قصدِ زنده ──")
    store.save(SC.PLAYWRIGHT_DOM, mode=SC.MODE_LIVE)
    eng_live = SE.StrategyEngine(
        FakeAdapter(), settings_store=store, mock_browser=True,
        driver_factory=factory,
        server_clock=lambda: {"verified": True, "delta_ms": 5000.0,
                              "rtt_ms": 1.0},
        live_allowed=True, halted=lambda: (False, ""))
    d4 = draft("G-CLOCK")
    current["draft"] = d4
    current["form"] = None
    try:
        eng_live.prepare(d4, SC.PLAYWRIGHT_DOM)
        clock_blocked = False
    except Exception as e:                           # noqa: BLE001
        clock_blocked = "CLOCK_MISMATCH" in str(e)
    ck(clock_blocked, "الف) اختلافِ ساعت ۵ثانیه‌ای prepare زنده را بست")
    store.save(SC.PLAYWRIGHT_DOM, mode=SC.MODE_SHADOW)

    print("\n── ۹) reconcile ──")
    ad = FakeAdapter()
    eng = make_engine(ad)
    d5 = draft("G-REC")
    current["draft"] = d5
    current["form"] = None
    o5 = eng.prepare(d5, SC.DIRECT_API)
    o5.result = SC.StrategyResult(d5.execution_id, SC.DIRECT_API, "unknown",
                                  unknown=True, detail="timeout")
    ad.rows = [ExecutionRecord(
        execution_id="", broker="fake", account=None, symbol="TEST",
        isin="IRO1TEST0001", side=Side.BUY, price=1000.0, quantity=10.0,
        mode=OrderMode.SAFE, broker_order_id="B-1",
        order_state=OrderState.UNKNOWN)]
    rr = eng.reconcile(o5.prepared_id)
    ck(rr.status == "reconciled" and rr.broker_order_id == "B-1",
       "الف) یک ردیفِ منطبق ⇒ reconciled", rr.public())
    o5b = eng.prepare(draft("G-REC2"), SC.DIRECT_API)
    o5b.result = SC.StrategyResult(o5b.execution_id, SC.DIRECT_API, "unknown",
                                   unknown=True)
    ad.rows = [
        ExecutionRecord(execution_id="", broker="fake", account=None,
                        symbol="TEST", isin="IRO1TEST0001", side=Side.BUY,
                        price=1000.0, quantity=10.0, mode=OrderMode.SAFE,
                        broker_order_id="B-2", order_state=OrderState.UNKNOWN),
        ExecutionRecord(execution_id="", broker="fake", account=None,
                        symbol="TEST", isin="IRO1TEST0001", side=Side.BUY,
                        price=1000.0, quantity=10.0, mode=OrderMode.SAFE,
                        broker_order_id="B-3", order_state=OrderState.UNKNOWN),
    ]
    rr2 = eng.reconcile(o5b.prepared_id)
    ck(rr2.unknown is True and rr2.status == "unknown",
       "پ) دو ردیفِ منطبق ⇒ همچنان نامعلوم، نه انتخابِ تصادفی", rr2.public())
    o5c = eng.prepare(draft("G-REC3"), SC.DIRECT_API)
    o5c.result = SC.StrategyResult(o5c.execution_id, SC.DIRECT_API, "unknown",
                                   unknown=True)
    ad.rows = []
    rr3 = eng.reconcile(o5c.prepared_id)
    ck(rr3.unknown is True, "ت) نبودِ ردیف ⇒ همچنان نامعلوم، نه شکست", rr3.status)

    print("\n── ۱۰) وضعیتِ بی‌راز ──")
    st = eng.status()
    blob = json.dumps(st, ensure_ascii=False)
    ck("strategies" in st and "rate_limiter" in st and "selection" in st,
       "الف) وضعیت شاملِ strategies/limiter/selection است")
    ck("TOKEN" not in blob.upper() and "AUTHORIZATION" not in blob.upper(),
       "پ) وضعیت هیچ کلیدِ رازی ندارد")
    sel = next(x for x in st["strategies"] if x["id"] == SC.SELENIUM)
    ck(sel["available"] is False and "selenium" in sel["unavailable_reason"],
       "ت) Selenium غایب صادقانه UNAVAILABLE است", sel["unavailable_reason"])

    print("\n── ۱۱) Probe و وضعیتِ واقعی ──")
    current["draft"] = draft("G-PROBE")
    pr = eng.probe(SC.PLAYWRIGHT_DOM)
    pblob = json.dumps(pr, ensure_ascii=False).lower()
    ck("structure" in pr and "value" not in pblob and "token" not in pblob
       and "cookie" not in pblob,
       "الف) Probe فقط ساختار است؛ هیچ مقدار/token/cookie ندارد", pr)
    ok_runtime, _why = EB.browser_runtime_available(
        SC.default_settings(SC.PLAYWRIGHT_DOM))
    ck(ok_runtime is True, "پ) مرورگرِ Chromiumِ سیستم/محلی شناسایی شد")
    _old_candidates = EB.browser_candidates
    EB.browser_candidates = lambda *a, **k: []
    try:
        ok_none, why_none = EB.browser_runtime_available(
            SC.default_settings(SC.PLAYWRIGHT_DOM))
    finally:
        EB.browser_candidates = _old_candidates
    ck(not ok_none and "no Chromium" in why_none,
       "ت) نبودِ مرورگر صادقانه UNAVAILABLE می‌شود", why_none)

    store_defaults = SC.StrategySettingsStore(os.path.join(tmp, "defaults.db"))
    eng_defaults = SE.StrategyEngine(
        FakeAdapter(), settings_store=store_defaults, mock_browser=True,
        driver_factory=factory, server_clock=clock_ok,
        live_allowed=False, halted=lambda: (False, ""))
    current["draft"] = draft("G-DEFAULT")
    try:
        eng_defaults.prepare(current["draft"], SC.PLAYWRIGHT_DOM)
        cfg_missing = False
        cfg_detail = ""
    except Exception as e:                           # noqa: BLE001
        cfg_missing = "CONFIG_MISSING" in str(e)
        cfg_detail = str(e)[:120]
    ck(cfg_missing, "ث) selectorِ پیکربندی‌نشده prepare نمی‌شود", cfg_detail)

    store.save(SC.PLAYWRIGHT_DOM, options={"login_selector": "[data-testid=login]"})
    current["draft"] = draft("G-LOGIN")
    current["form"] = None
    try:
        eng.prepare(current["draft"], SC.PLAYWRIGHT_DOM)
        login_blocked = False
    except Exception as e:                           # noqa: BLE001
        login_blocked = "LOGIN_REQUIRED" in str(e)
    ck(login_blocked, "ج) صفحهٔ ورود ⇒ LOGIN_REQUIRED، نه اجرای کور")
    store.save(SC.PLAYWRIGHT_DOM, options={"login_selector": ""})

    current["draft"] = draft("G-CLOSED")
    o_closed = eng.prepare(current["draft"], SC.PLAYWRIGHT_DOM)
    o_closed.prepared.driver.close()
    r_closed = eng.trigger(o_closed.prepared_id, live=False)
    ck(r_closed.status == "blocked" and r_closed.error_code == "BROWSER_NOT_READY",
       "چ) مرورگرِ بسته ⇒ خطای قابل‌فهم، نه کلیکِ کور", r_closed.public())

    store.save(SC.PLAYWRIGHT_DOM, mode=SC.MODE_LIVE)
    eng_live401 = SE.StrategyEngine(
        FakeAdapter(writes_allowed=True), settings_store=store,
        mock_browser=True, driver_factory=factory, server_clock=clock_ok,
        live_allowed=True, halted=lambda: (False, ""))
    current["draft"] = draft("G-401")
    current["form"] = None
    current["response_override"] = {
        "status": 401, "body": "{\"isSuccessful\":false,\"message\":\"expired\"}"}
    o401 = eng_live401.prepare(current["draft"], SC.PLAYWRIGHT_DOM)
    r401 = eng_live401.trigger(o401.prepared_id, live=True, live_allowed=True)
    ck(not r401.accepted and r401.error_code in ("SESSION_EXPIRED", "UNKNOWN_RESULT")
       and r401.status in ("failed", "unknown"),
       "ح) ۴۰۱ مرورگر پذیرش نمی‌شود و پاسخ تازه/تکرار ندارد", r401.public())
    current["response_override"] = None
    store.save(SC.PLAYWRIGHT_DOM, mode=SC.MODE_SHADOW)

    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    print("\n%d checks, %d failed, %d skipped" % (PASS + FAIL, FAIL, SKIP))
    print("STRATEGY GUARD " + ("OK" if FAIL == 0 else "FAILED"))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
