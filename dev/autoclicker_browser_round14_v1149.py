#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""autoclicker_browser_round14_v1149 — تستِ browser-level با EasyTraderِ تقلبی.

هر سناریو یک صفحهٔ محلیِ instrument‌شده دارد:
  • GET /clicked شمارندهٔ کلیکِ واقعیِ صفحه است.
  • POST /core/api/v2/order شمارندهٔ درخواستِ سفارشِ رسیده است (باید ۰ بماند).
  • مسیرهای path/query/method/redirect/host برایِ تستِ گاردِ dry-run.
هیچ اتصالی به کارگزاری و هیچ سفارشِ واقعی وجود ندارد.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

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
        print("FAIL " + label + "  -> " + str(detail)[:280])


HTML = """<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8">
<title>EasyTrader Mock</title>
<body>
<div data-cy="order-form" id="order-form">
  <div data-cy="order-form-header-symbol-name">TEST</div>
  <div id="side-label">خرید</div>
  <input id="price" value="1000">
  <input id="quantity" value="10">
  <input id="isin" value="IRO1TEST0001">
  <button class="order-buy-btn" aria-label="ارسال خرید" %DISABLED% onclick="fire('buy')">ارسال خرید</button>
  <button class="order-sell-btn" aria-label="ارسال فروش" %DISABLED% onclick="fire('sell')">ارسال فروش</button>
  %EXTRA%
</div>
<script>
const q = new URLSearchParams(location.search);
const mode = q.get('mode') || 'standard';
const port = %PORT%;
window.__clicks = 0;
function fire(side) {
  window.__clicks += 1;
  new Image().src = '/clicked?side=' + side + '&t=' + Date.now();
  let url = '/core/api/v2/order';
  let opts = {method: 'POST', headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({price: 1000, quantity: 10, side: side})};
  if (mode === 'path') url = '/other/order';
  if (mode === 'query') url = '/core/api/v2/order?x=1';
  if (mode === 'redirect') url = '/redirect';
  if (mode === 'method') opts.method = 'PATCH';
  if (mode === 'slow') url = '/core/api/v2/order?slow=1';
  if (mode === 'drop') url = '/core/api/v2/order?drop=1';
  if (mode === 'host') url = 'http://localhost:' + port + '/core/api/v2/order';
  fetch(url, opts).catch(() => {});
}
</script>
</body></html>"""


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.order_hits = 0
        self.other_hits = 0
        self.redirect_hits = 0
        self.click_hits = 0
        self.sell_clicks = 0
        self.buy_clicks = 0
        self.paths = []

    def hit(self, name):
        with self.lock:
            setattr(self, name, getattr(self, name) + 1)

    def add_path(self, path):
        with self.lock:
            self.paths.append(path)


class Handler(BaseHTTPRequestHandler):
    server_version = "EasyTraderMock/1"

    def log_message(self, *_args):
        return

    def _json(self, code, obj):
        raw = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (ConnectionAbortedError, BrokenPipeError, OSError):
            pass

    def do_GET(self):
        p = urlparse(self.path)
        st = self.server.state
        st.add_path(p.path)
        if p.path in ("/", "/order"):
            mode = parse_qs(p.query).get("mode", ["standard"])[0]
            disabled = "disabled" if mode == "disabled" else ""
            extra = ("<button aria-label='ارسال خرید' onclick=\"fire('buy')\">"
                     "ارسال خرید دوم</button>" if mode == "multi" else "")
            body = (HTML.replace("%DISABLED%", disabled)
                    .replace("%EXTRA%", extra)
                    .replace("%PORT%", str(self.server.server_port)))
            raw = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if p.path == "/clicked":
            q = parse_qs(p.query)
            st.hit("click_hits")
            st.hit("%s_clicks" % (q.get("side", ["buy"])[0] or "buy"))
            self.send_response(204)
            self.end_headers()
            return
        if p.path == "/counters":
            with st.lock:
                self._json(200, {
                    "order_hits": st.order_hits, "other_hits": st.other_hits,
                    "redirect_hits": st.redirect_hits,
                    "click_hits": st.click_hits,
                    "buy_clicks": st.buy_clicks, "sell_clicks": st.sell_clicks,
                    "paths": list(st.paths),
                })
            return
        self._json(404, {"error": "not found"})

    def do_POST(self):
        p = urlparse(self.path)
        st = self.server.state
        st.add_path(p.path)
        length = int(self.headers.get("Content-Length") or 0)
        try:
            if length:
                self.rfile.read(length)
        except Exception:
            pass
        q = parse_qs(p.query)
        if p.path == "/core/api/v2/order":
            st.hit("order_hits")
            if "drop" in q:
                try:
                    self.connection.close()
                except Exception:
                    pass
                return
            if "slow" in q:
                time.sleep(1.5)
            self._json(200, {"isSuccessful": True, "id": "B-MOCK-1"})
            return
        if p.path == "/other/order":
            st.hit("other_hits")
            self._json(200, {"ok": True})
            return
        if p.path == "/redirect":
            st.hit("redirect_hits")
            self.send_response(307)
            self.send_header("Location", "/core/api/v2/order")
            self.end_headers()
            return
        self._json(404, {"error": "not found"})


def wait_counter(state, attr, timeout=1.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        with state.lock:
            if getattr(state, attr, 0) > 0:
                return True
        time.sleep(0.02)
    return False


def main() -> int:
    import execution_browser as EB
    import execution_intent_store as IS
    import execution_strategy_core as SC
    import execution_strategy_engine as SE
    import execution_timing as T
    from execution_contract import (
        InstrumentRef, OrderDraft, OrderMode, Side, Resolution,
    )

    ok, why = EB.browser_runtime_available()
    if not ok:
        print("SKIP browser-level: %s" % why)
        print("AUTOCLICKER BROWSER ROUND14 SKIP")
        return 0

    state = State()
    server = ThreadingHTTPServer(("0.0.0.0", 0), Handler)
    server.state = state
    server.daemon_threads = True
    port = server.server_port
    th = threading.Thread(target=server.serve_forever, daemon=True)
    th.start()

    tmp = tempfile.mkdtemp(prefix="ac14b_")
    db = os.path.join(tmp, "user.db")
    settings_store = SC.StrategySettingsStore(db)
    intent_store = IS.IntentStore(os.path.join(tmp, "intents.db"))

    instr = InstrumentRef(symbol="TEST", ins_code="1", isin="IRO1TEST0001",
                          broker_instrument="IRO1TEST0001",
                          resolution=Resolution.EXACT)

    def draft(eid, side=Side.BUY):
        return OrderDraft(execution_id=eid, instrument=instr, side=side,
                          price=1000.0, quantity=10.0, mode=OrderMode.SAFE)

    def opts(mode, **extra):
        base = {
            "order_url": "http://127.0.0.1:%d/order?mode=%s" % (port, mode),
            "origin_allowlist": ["http://127.0.0.1:%d" % port,
                                 "http://localhost:%d" % port],
            "symbol_selector": "",
            "form_symbol_selector": "[data-cy='order-form-header-symbol-name']",
            "open_form_selector": "",
            "open_form_selector_buy": "",
            "open_form_selector_sell": "",
            "price_selector": "#price",
            "quantity_selector": "#quantity",
            "submit_selector": "button[aria-label='ارسال خرید']",
            "submit_selector_buy": "button[aria-label='ارسال خرید']",
            "submit_selector_sell": "button[aria-label='ارسال فروش']",
            "form_selector": "",
            "side_selector": "",
            "isin_selector": "",
            "intercept_pattern": "**/core/api/v2/order*",
            "order_paths": ["/core/api/v2/order"],
            "order_method": "POST",
            "action_timeout_ms": 700,
            "response_timeout_ms": 250,
            "navigation_timeout_ms": 10000,
            "autofill": False,
            "require_prefilled": True,
            "headless": True,
            "profile_dir": os.path.join(tmp, "profile-%s" % mode),
            "browser_path": "",
            "no_proxy": True,
            "keep_driver_alive": False,
        }
        base.update(extra)
        return base

    def engine_for(mode, *, live=False, scheduler=None, **extra):
        settings_store.save(SC.AUTOCLICKER, mode=(
            SC.MODE_LIVE if live else SC.MODE_SHADOW), options=opts(mode, **extra))
        return SE.StrategyEngine(
            None, settings_store=settings_store, mock_browser=False,
            scheduler=scheduler, server_clock=lambda: {
                "verified": True, "delta_ms": 0.0, "rtt_ms": 1.0,
                "broker_time": "2026-10-21T00:00:00"},
            live_allowed=live, halted=lambda: (False, ""),
            intent_store=intent_store, recover_intents=False)

    def dry(mode, eid, *, side=Side.BUY, **extra):
        eng = engine_for(mode, **extra)
        d = draft(eid, side=side)
        o = eng.prepare(d, SC.AUTOCLICKER)
        return eng, o

    try:
        # ۱) استاندارد: کلیک ۱، سفارش ۰
        eng, o = dry("standard", "B-STD")
        r = eng.trigger(o.prepared_id, live=False)
        wait_counter(state, "click_hits")
        ck(r.status == "dry_run" and state.order_hits == 0
           and state.click_hits == 1,
           "browser dry-run استاندارد: کلیک ۱، سفارش ۰",
           {"status": r.status, "code": r.error_code, "order": state.order_hits,
            "clicks": state.click_hits, "evidence": r.evidence})

        # ۲) الگویِ غلط
        eng, o = dry("standard", "B-PATTERN",
                     intercept_pattern="**/never-order*")
        r = eng.trigger(o.prepared_id, live=False)
        wait_counter(state, "click_hits")
        ck(r.status == "dry_run" and state.order_hits == 0,
           "browser dry-run با الگویِ غلط: سفارش ۰",
           {"status": r.status, "order": state.order_hits})

        # ۳) path جایگزین
        eng, o = dry("path", "B-PATH")
        r = eng.trigger(o.prepared_id, live=False)
        wait_counter(state, "click_hits")
        ck(r.status == "blocked" and r.error_code == "NON_ORDER_WRITE_BLOCKED"
           and state.order_hits == 0 and state.other_hits == 0,
           "browser path جایگزین: هر دو endpoint صفر",
           {"status": r.status, "code": r.error_code,
            "order": state.order_hits, "other": state.other_hits})

        # ۴) host جایگزین
        eng, o = dry("host", "B-HOST")
        r = eng.trigger(o.prepared_id, live=False)
        wait_counter(state, "click_hits")
        ck(r.status == "dry_run" and state.order_hits == 0,
           "browser host جایگزین: سفارش ۰",
           {"status": r.status, "order": state.order_hits})

        # ۵) method جایگزین
        eng, o = dry("method", "B-METHOD")
        r = eng.trigger(o.prepared_id, live=False)
        wait_counter(state, "click_hits")
        ck(r.status == "blocked" and r.error_code == "ORDER_METHOD_MISMATCH"
           and state.order_hits == 0,
           "browser method جایگزین: سفارش ۰",
           {"status": r.status, "code": r.error_code})

        # ۶) query
        eng, o = dry("query", "B-QUERY")
        r = eng.trigger(o.prepared_id, live=False)
        wait_counter(state, "click_hits")
        ck(r.status == "dry_run" and state.order_hits == 0,
           "browser query: سفارش ۰", {"status": r.status})

        # ۷) redirect
        eng, o = dry("redirect", "B-REDIRECT")
        r = eng.trigger(o.prepared_id, live=False)
        wait_counter(state, "click_hits")
        ck(r.status == "blocked" and state.order_hits == 0
           and state.redirect_hits == 0,
           "browser redirect: سفارش/ریدایرکت ۰",
           {"status": r.status, "order": state.order_hits,
            "redirect": state.redirect_hits})

        # ۸) چند فرم/دکمه
        base_clicks = state.click_hits
        eng = engine_for("multi")
        d = draft("B-MULTI")
        try:
            eng.prepare(d, SC.AUTOCLICKER)
            multi_blocked = False
            multi_detail = ""
        except Exception as e:                   # noqa: BLE001
            multi_blocked = "FORM_NOT_UNIQUE" in str(e)
            multi_detail = str(e)
        ck(multi_blocked and state.click_hits == base_clicks,
           "browser چند دکمه: صفر کلیکِ تازه", multi_detail[:160])

        # ۹) دکمهٔ غیرفعال
        base_clicks = state.click_hits
        eng = engine_for("disabled")
        try:
            o_dis = eng.prepare(draft("B-DISABLED"), SC.AUTOCLICKER)
            dis_blocked = False
            dis_detail = "evidence=%s enabled=%s" % (
                o_dis.prepared.evidence,
                o_dis.prepared.driver.is_enabled(
                    "button[aria-label='ارسال خرید']"))
        except Exception as e:                   # noqa: BLE001
            dis_blocked = "SUBMIT_DISABLED" in str(e) or "FORM_NOT_UNIQUE" in str(e)
            dis_detail = str(e)
        ck(dis_blocked and state.click_hits == base_clicks,
           "browser دکمهٔ غیرفعال: صفر کلیکِ تازه", dis_detail[:220])

        # ۱۰) تغییرِ فرم پیش از trigger
        base_clicks = state.click_hits
        eng, o = dry("standard", "B-MUTATE")
        o.prepared.driver.evaluate(
            "document.querySelector('#price').value = '999'")
        r = eng.trigger(o.prepared_id, live=False)
        ck(r.status == "blocked" and r.error_code == "PRICE_MISMATCH"
           and state.click_hits == base_clicks,
           "browser تغییرِ قیمت پیش از کلیک: صفر کلیکِ تازه",
           {"status": r.status, "code": r.error_code,
            "clicks": state.click_hits - base_clicks})

        # ۱۱) فروش
        before_sell = state.sell_clicks
        eng, o = dry("standard", "B-SELL", side=Side.SELL)
        r = eng.trigger(o.prepared_id, live=False)
        wait_counter(state, "click_hits")
        ck(r.status == "dry_run" and state.sell_clicks > before_sell
           and state.order_hits == 0,
           "browser فروش با دکمهٔ فروش: سفارش ۰",
           {"status": r.status, "sell": state.sell_clicks,
            "order": state.order_hits})

        # ۱۲) live محلی: یک کلیک و پذیرشِ صریح
        settings_store.save(SC.AUTOCLICKER, mode=SC.MODE_LIVE,
                            options=opts("standard"))
        settings = settings_store.load()[SC.AUTOCLICKER]
        ctx = SE.StrategyContext(
            adapter=None, settings=settings, metrics=SC.StrategyMetrics(),
            dry_run=False, driver_factory=EB.make_driver, live_intent=True,
            server_clock=lambda: {"verified": True, "delta_ms": 0.0,
                                  "rtt_ms": 1.0,
                                  "broker_time": "2026-10-21T00:00:00"})
        strategy = SE.AutoClickerStrategy()
        handle = strategy.prepare(ctx, draft("B-LIVE"))
        order = SC.StrategyOrder("B-LIVE", SC.AUTOCLICKER, draft("B-LIVE"),
                                 None, intent_key="B-LIVE")
        order.prepared = handle
        r_live = strategy.trigger(ctx, order)
        wait_counter(state, "click_hits")
        ck(r_live.status == "accepted" and r_live.accepted is True
           and state.order_hits >= 1,
           "browser live محلی: پذیرشِ صریح و سفارشِ محلی ۱",
           {"status": r_live.status, "order": state.order_hits,
            "body": r_live.evidence.get("response_keys")})

        # ۱۳) live محلی: پاسخِ نیامده ⇒ UNKNOWN
        settings_store.save(SC.AUTOCLICKER, mode=SC.MODE_LIVE,
                            options=opts("slow"))
        settings = settings_store.load()[SC.AUTOCLICKER]
        ctx2 = SE.StrategyContext(
            adapter=None, settings=settings, metrics=SC.StrategyMetrics(),
            dry_run=False, driver_factory=EB.make_driver, live_intent=True,
            server_clock=lambda: {"verified": True, "delta_ms": 0.0,
                                  "rtt_ms": 1.0,
                                  "broker_time": "2026-10-21T00:00:00"})
        h2 = strategy.prepare(ctx2, draft("B-UNKNOWN"))
        o2 = SC.StrategyOrder("B-UNKNOWN", SC.AUTOCLICKER, draft("B-UNKNOWN"),
                              None, intent_key="B-UNKNOWN")
        o2.prepared = h2
        r_unk = strategy.trigger(ctx2, o2)
        ck(r_unk.status == "unknown" and r_unk.unknown is True,
           "browser live محلی: timeout پس از کلیک ⇒ UNKNOWN",
           {"status": r_unk.status, "unknown": r_unk.unknown})

        # ۱۴) scheduled + abort با مرورگر واقعی
        base_order = state.order_hits
        sched = T.Scheduler(T.TimeSource(), spin_window_ms=5)
        eng_ab = engine_for("standard", scheduler=sched)
        d_ab = draft("B-ABORT")
        o_ab = eng_ab.prepare(d_ab, SC.AUTOCLICKER,
                              target_wall_ms=int(time.time() * 1000) + 2000)
        box = {}

        def runner():
            box["r"] = eng_ab.trigger(o_ab.prepared_id, live=False)

        t = threading.Thread(target=runner, daemon=True)
        t.start()
        time.sleep(0.3)
        eng_ab.abort(o_ab.prepared_id)
        t.join(timeout=4)
        r_ab = box.get("r")
        ck(r_ab is not None and r_ab.status == "aborted"
           and state.order_hits == base_order,
           "browser Abort زمان‌بند: سفارشِ تازه ۰",
           {"status": r_ab and r_ab.status,
            "order_delta": state.order_hits - base_order})

        print("\nCOUNTERS order=%d other=%d redirect=%d clicks=%d buy=%d sell=%d"
              % (state.order_hits, state.other_hits, state.redirect_hits,
                 state.click_hits, state.buy_clicks, state.sell_clicks))
    finally:
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n%d checks, %d failed, %d skipped" % (PASS + FAIL, FAIL, SKIP))
    print("AUTOCLICKER BROWSER ROUND14 " + ("OK" if FAIL == 0 else "FAILED"))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
