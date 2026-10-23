#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""autoclicker_round22_browser_v1173 — لایۀ ۲: Chromiumِ واقعی + EasyTraderِ تقلبی.

چرا این گارد لازم است: داوریِ فرم/دکمه در `execution_ui_state` رویِ DOMِ واقعیِ
مرورگر اجرا می‌شود و کلیکِ نهایی `locator.click()` خودِ Playwright است. تستِ
واحد با fixtureِ JSON این دو را اثبات نمی‌کند. این‌جا:

  ۱) یک سرورِ محلیِ 127.0.0.1 صفحه‌هایِ هم‌شکلِ EasyTrader را سرو می‌کند
     (فرمِ RTLِ فارسی، دکمۀ هم‌نامِ مخفی، دکمۀ تکراری، دکمۀ بیرونِ viewport،
     دکمۀ غیرفعال، صفحۀ دیگری برایِ ناوبری).
  ۲) یک Chromiumِ واقعی (همان باینریِ `browser_candidates`، بی‌شبکه) با
     `--remote-debugging-port` بالا می‌آید؛ driver با CDP به همان context وصل
     می‌شود — همان توپولوژیِ تولید (پنجرۀ host + تبِ پنل).
  ۳) هر کلیک دکمه در صفحه یک beacon و یک POST به `/core/api/v2/order` می‌زند؛
     شمارندۀ سرور می‌گوید چه چیزی واقعاً «رسید».

قیدِ امنیتی: میزبانِ مجاز فقط 127.0.0.1 است؛ هیچ درخواستی به کارگزاری نمی‌رود،
هیچ دکمۀ ثبتِ واقعی فعال نمی‌شود و هیچ نشستی خوانده نمی‌شود. آزمونِ «مسیرِ
زنده» هم فقط به همین fixtureِ محلی POST می‌زند تا زنجیرۀ
کلیک→درخواست→پاسخ→داوری اثبات شود — نه سفارشِ واقعی.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
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
        print("FAIL " + label + "  -> " + str(detail)[:320])


# ── صفحۀ تقلبی ───────────────────────────────────────────────────────────────
PAGE = u"""<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8">
<title>EasyTrader Local Fixture</title>
<style>
 body{font-family:Tahoma,sans-serif;margin:16px;background:#fff}
 #order-form{width:520px;border:1px solid #ccc;padding:12px;background:#fafafa}
 .order-submit{display:block;margin:8px 0;padding:6px 14px}
 #side-label{font-weight:bold;margin:6px 0}
</style>
<body>
__PAD__
<div id="order-form">
  <div data-cy="order-form-header-symbol-name">__SYMBOL__</div>
  <div id="side-label">__SIDE__</div>
  <label>قیمت <input id="price" value="__PRICE__"></label>
  <label>تعداد <input id="quantity" value="10"></label>
  <input id="isin" value="IRO1TEST0001" readonly>
  __BUTTONS__
</div>
__OTHER__
<script>
window.__clicks = 0;
function fire(which, side) {
  window.__clicks += 1;
  new Image().src = '/beacon?which=' + which + '&side=' + side + '&t=' + Date.now();
  var p = document.querySelector('#price');
  var q = document.querySelector('#quantity');
  fetch('/core/api/v2/order', {method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({price: Number(p ? p.value : 0),
                              quantity: Number(q ? q.value : 0),
                              side: side})}).catch(function () {});
}
</script>
</body></html>"""

ORDERS_PAGE = u"""<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8">
<title>سفارش‌های امروز</title>
<body><div id="orders-mark">فهرستِ سفارش‌های امروز</div></body></html>"""

APP_PAGE = u"""<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8">
<title>پنل کارگزاری</title>
<body><main-layout><div id="app-mark">پنل کارگزاری</div></main-layout>
<script>
 sessionStorage.setItem('oidc.user:https://login.emofid.com:client',
                        '{"access_token":"SECRET-SHOULD-NOT-LEAK"}');
</script>
</body></html>"""

PANEL_STUB = u"""<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8">
<title>AutoClicker Panel</title>
<body><div id="panel-mark">پنلِ اتوکلیکر</div></body></html>"""

MAIN_BUY = ('<button class="order-submit" aria-label="ارسال خرید" '
            'onclick="fire(\'main\',\'buy\')">ارسال خرید</button>')
SECOND_BUY = ('<button class="order-submit" aria-label="ارسال خرید" '
              'onclick="fire(\'second\',\'buy\')">ارسال خرید دوم</button>')
HIDDEN_BUY = ('<div style="display:none"><button class="order-submit" '
              'aria-label="ارسال خرید" onclick="fire(\'hidden\',\'buy\')">'
              'ارسال خرید</button></div>')
DISABLED_BUY = ('<button class="order-submit" aria-label="ارسال خرید" disabled>'
                'ارسال خرید</button>')
SELL_BTN = ('<button class="order-submit" aria-label="ارسال فروش" '
            'onclick="fire(\'sell\',\'sell\')">ارسال فروش</button>')
OTHER_FORM = ('<div id="other-form" style="margin-top:10px;width:520px">'
              '<div data-cy="order-form-header-symbol-name">TEST</div>'
              '<input id="price2" value="1000"><input id="quantity2" value="10">'
              '<button class="order-submit" aria-label="ارسال خرید" '
              'onclick="fire(\'other\',\'buy\')">ارسال خرید</button></div>')


def page_for(mode):
    symbol, side, price = "TEST", u"خرید", "1000"
    buttons, pad, other = MAIN_BUY, "", ""
    if mode == "hidden":
        buttons = MAIN_BUY + HIDDEN_BUY
    elif mode == "multi":
        buttons = MAIN_BUY + SECOND_BUY
    elif mode == "otherform":
        other = OTHER_FORM
    elif mode == "offscreen":
        pad = '<div style="height:3000px">فاصله</div>'
    elif mode == "disabled":
        buttons = DISABLED_BUY
    elif mode == "sellonly":
        side, buttons = u"فروش", SELL_BTN
    elif mode == "nobutton":
        buttons = ""
    elif mode == "pricemismatch":
        price = "1010"
    elif mode == "symbolmismatch":
        symbol = u"دیگر"
    return (PAGE.replace("__SYMBOL__", symbol).replace("__SIDE__", side)
            .replace("__PRICE__", price).replace("__BUTTONS__", buttons)
            .replace("__PAD__", pad).replace("__OTHER__", other))


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.counters = {"click_main": 0, "click_second": 0, "click_hidden": 0,
                         "click_other": 0, "click_sell": 0, "order_hits": 0}
        self.paths = []

    def hit(self, key):
        with self.lock:
            self.counters[key] = self.counters.get(key, 0) + 1

    def snap(self):
        with self.lock:
            return dict(self.counters)

    def delta(self, before):
        now = self.snap()
        return {k: now.get(k, 0) - int(before.get(k, 0) or 0) for k in now}


def _clicks(delta):
    return sum(v for k, v in delta.items() if k.startswith("click_"))


def settle(quiet_ms=200, max_ms=1600):
    """شمارنده‌ها را تا آرام‌شدنِ کامل صبر می‌کند.

    beaconِ تصویر (`new Image`) و POSTِ fetch هم‌زمان نیستند؛ خواندنِ فوری
    باعث می‌شد کلیکِ سناریویِ قبلی به سناریویِ بعدی نسبت داده شود.
    """
    last = None
    stable_since = time.monotonic()
    deadline = time.monotonic() + (max_ms / 1000.0)
    while time.monotonic() < deadline:
        #: Playwright رویدادها را فقط با فراخوانیِ API تحویل می‌دهد؛ بی‌این
        #: درخواستِ beacon تا سناریویِ بعد در صف می‌ماند و به سناریویِ اشتباه
        #: نسبت داده می‌شود.
        try:
            if DRIVER is not None:
                DRIVER.evaluate("() => 0")
        except Exception:
            pass
        cur = STATE.snap()
        if cur != last:
            last = cur
            stable_since = time.monotonic()
        elif (time.monotonic() - stable_since) * 1000 >= quiet_ms:
            return cur
        time.sleep(0.03)
    return STATE.snap()


class Handler(BaseHTTPRequestHandler):
    server_version = "EasyTraderLocalFixture/1"
    #: HTTP/1.0 باعث می‌شد Chromium پس از dataReceived هرگز
    #: `Network.loadingFinished` نفرستد و `response.body()` معلق بماند؛
    #: هر پاسخ Content-Length دارد، پس HTTP/1.1 بی‌خطر و درست است.
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        return

    def _html(self, body, code=200):
        raw = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (ConnectionAbortedError, BrokenPipeError, OSError):
            pass

    def _json(self, code, obj):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
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
        with st.lock:
            st.paths.append(p.path)
        if p.path == "/order":
            mode = parse_qs(p.query).get("mode", ["standard"])[0]
            self._html(page_for(mode))
            return
        if p.path == "/orders":
            self._html(ORDERS_PAGE)
            return
        if p.path == "/app":
            self._html(APP_PAGE)
            return
        if p.path == "/static/autoclicker/panel.html":
            self._html(PANEL_STUB)
            return
        if p.path == "/beacon":
            which = (parse_qs(p.query).get("which", ["main"])[0] or "main")
            st.hit("click_" + which.replace("-", "_"))
            self.send_response(204)
            self.end_headers()
            return
        if p.path == "/counters":
            self._json(200, st.snap())
            return
        self._html("<html><body>404</body></html>", 404)

    def do_POST(self):
        p = urlparse(self.path)
        st = self.server.state
        n = int(self.headers.get("Content-Length") or 0)
        try:
            if n:
                self.rfile.read(n)
        except Exception:
            pass
        if p.path == "/core/api/v2/order":
            st.hit("order_hits")
            self._json(200, {"isSuccessful": True, "id": "LOCAL-MOCK-1",
                             "message": "ok", "orderStateStr": "در انتظار"})
            return
        self._json(404, {"error": "not found"})


class DualStackServer(ThreadingHTTPServer):
    address_family = socket.AF_INET6
    daemon_threads = True

    def server_bind(self):
        #: ویندوز پیش‌فرض IPv6 را v6-only می‌بندد؛ بی‌این 127.0.0.1 «refused»
        #: می‌دهد و fixture فقط با localhost در دسترس است.
        try:
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        except OSError:
            pass
        super().server_bind()

    def handle_error(self, request, client_address):
        #: بستنِ keep-alive توسطِ مرورگر خطا نیست؛ tracebackِ آن خروجیِ گارد را
        #: شبیهِ شکست می‌کند.
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError,
                            BrokenPipeError)):
            return
        super().handle_error(request, client_address)


# ── مقادیر مشترک ─────────────────────────────────────────────────────────────
STORE = None
DRIVER = None
STATE = None
FIX = ""
ALT = ""
CDP = ""
NAV_N = [0]


def _goto(url, path, n):
    DRIVER.evaluate("(u) => { window.location.assign(u); }", url)
    want_n = "n=%d" % n
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            cur = urlparse(DRIVER.url())
            if cur.path == path and want_n in (cur.query or ""):
                break
        except Exception:
            pass
        time.sleep(0.03)
    for _ in range(100):
        try:
            if DRIVER.evaluate("() => document.readyState") == "complete":
                return True
        except Exception:
            pass
        time.sleep(0.03)
    return False


def nav_mode(mode):
    NAV_N[0] += 1
    n = NAV_N[0]
    return _goto("%s/order?mode=%s&n=%d" % (FIX, mode, n), "/order", n)


def nav_path(path, host="127.0.0.1"):
    NAV_N[0] += 1
    n = NAV_N[0]
    base = FIX if host == "127.0.0.1" else ALT
    return _goto("%s%s?n=%d" % (base, path, n), path, n)


def ui_opts(K, side="buy", price=1000.0, qty=10.0):
    return K.UIOptions(
        submit_selector="button.order-submit", price_selector="#price",
        quantity_selector="#quantity",
        symbol_selector="[data-cy='order-form-header-symbol-name']",
        isin_selector="#isin", side_selector="#side-label",
        form_scope_selector="#order-form", side=side,
        expected_price=float(price), expected_quantity=float(qty),
        expected_symbol="TEST", expected_isin="IRO1TEST0001")


def new_exec(AC, UIS, *, dry=True, side="buy", price=1000.0, clock=None):
    ctx = AC.ExecutorContext(
        driver=DRIVER, ui=ui_opts(UIS, side=side, price=price), dry_run=bool(dry),
        order_paths=("/core/api/v2/order",), order_method="POST",
        intercept_pattern="**/core/api/v2/order*",
        allowed_hosts=("127.0.0.1",),
        request_timeout_ms=1500, response_timeout_ms=4000, clock_probe=clock)
    return AC.AutoClickExecutor(lambda: ctx)


def reset_active(RC):
    run = STORE.active_run("easytrader")
    if run is not None:
        try:
            STORE.cancel(run.run_id, "guard reset")
        except Exception:
            pass


def new_run(RC, *, count=1, interval=3000.0, dry=True, first_ms=0, mode="single",
            price=1000.0, side="buy"):
    reset_active(RC)
    target = RC.format_tehran(int(time.time() * 1000) + int(first_ms))
    cfg = RC.RunConfig(symbol="TEST", isin="IRO1TEST0001", side=side,
                       expected_price=float(price), expected_quantity=10.0,
                       target_at=target, mode=mode, total_actions=int(count),
                       interval_ms=float(interval), dry_run=bool(dry),
                       live_confirmed=not dry, prewarm_ms=0)
    rec = STORE.create(cfg)
    rec = STORE.arm(rec.run_id, validation={}, ok_for_arm=True)
    return STORE.start(rec.run_id)


def claim(RC, rec):
    return STORE.claim_next(rec.run_id, at_ms=int(time.time() * 1000), token="guard")


def scenario(RC, AC, UIS, SC, mode, *, dry=True, side="buy", price=1000.0,
             clock=None):
    nav_mode(mode)
    rec = new_run(RC, dry=dry, price=price, side=side, first_ms=0)
    act = claim(RC, rec)
    ex = new_exec(AC, UIS, dry=dry, side=side, price=price, clock=clock)
    warm = ex.run_warm()
    hooks = SC.FireHooks(run_id=rec.run_id, idx=act.idx, store=STORE,
                         stop_event=threading.Event())
    out = ex(rec, act, hooks)
    return rec, act, ex, warm, out


def context_shape():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.connect_over_cdp(CDP)
        return [len(c.pages) for c in b.contexts]


def ensure_host_page(url):
    """تبِ اولِ Chromium را تا بارگذاریِ صفحۀ fixture می‌برد (بی‌ساختِ تبِ دوم)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        if urlparse(pg.url).path != "/order":
            pg.goto(url, wait_until="load", timeout=20000)
        else:
            pg.wait_for_load_state("load", timeout=20000)
        return len(ctx.pages)


def open_tab(url):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        pg = ctx.new_page()
        pg.goto(url, wait_until="domcontentloaded", timeout=15000)
        pg.wait_for_timeout(250)
        return len(ctx.pages)


def close_path(path):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.connect_over_cdp(CDP)
        n = 0
        for ctx in b.contexts:
            for pg in list(ctx.pages):
                if urlparse(pg.url).path == path:
                    try:
                        pg.close()
                        n += 1
                    except Exception:
                        pass
        return n


def wait_cdp(url, timeout_s=25.0):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url + "/json/version", timeout=0.6) as r:
                if int(getattr(r, "status", 0) or 0) == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.15)
    return False


def free_port():
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])
    finally:
        s.close()


def main() -> int:
    global STORE, DRIVER, FIX, ALT, CDP, STATE
    import execution_browser as EB
    import execution_ui_state as UIS
    import execution_autoclick_executor as AC
    import execution_autoclick_run as RC
    import execution_autoclick_scheduler as SC
    import execution_panel as EP
    import execution_strategy_core as Core

    ok, exe = EB.browser_runtime_available()
    if not ok:
        print("SKIP browser-level: %s" % exe)
        print("AUTOCLICKER ROUND22 BROWSER SKIP")
        return 0

    state = State()
    STATE = state
    server = DualStackServer(("::", 0), Handler)
    server.state = state
    port = int(server.server_port)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    FIX = "http://127.0.0.1:%d" % port
    ALT = "http://localhost:%d" % port
    cdp_port = free_port()
    CDP = "http://127.0.0.1:%d" % cdp_port

    tmp = tempfile.mkdtemp(prefix="ac22b_")
    profile = os.path.join(tmp, "profile")
    os.makedirs(profile, exist_ok=True)
    args = [exe, "--headless=new", "--remote-debugging-port=%d" % cdp_port,
            "--remote-allow-origins=*",
            "--user-data-dir=%s" % profile, "--no-first-run",
            "--no-default-browser-check", "--disable-extensions",
            "--disable-sync", "--disable-background-networking", "--no-proxy-server",
            "--window-size=1280,900", "about:blank"]
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not wait_cdp(CDP):
            print("SKIP browser-level: Chromium did not open its CDP port")
            print("AUTOCLICKER ROUND22 BROWSER SKIP")
            return 0
        # یک تبِ بارشده تضمین می‌کند driver صفر/دو تب نسازد.
        if ensure_host_page(FIX + "/order?mode=standard") != 1:
            print("SKIP browser-level: host window is not a single loaded tab")
            print("AUTOCLICKER ROUND22 BROWSER SKIP")
            return 0
        shape0 = context_shape()
        ck(len(shape0) == 1 and shape0[0] == 1,
           "host: یک context و یک تب با صفحۀ fixture", shape0)

        settings = Core.default_settings(Core.AUTOCLICKER)
        settings.options = {
            "cdp_url": CDP, "order_url": FIX + "/order",
            "headless": True, "action_timeout_ms": 2000,
            "navigation_timeout_ms": 15000,
            "intercept_pattern": "**/core/api/v2/order*",
            "keep_driver_alive": True}
        DRIVER = EB.PlaywrightBrowserDriver(settings, strategy_id="round22-guard",
                                            profile_dir=profile)
        DRIVER.start()
        ck(DRIVER.is_alive(), "driver attaches over CDP to the fixture window")
        ck(urlparse(DRIVER.url()).hostname == "127.0.0.1",
           "driver page is the fixture host", DRIVER.url())

        STORE = RC.AutoClickRunStore(os.path.join(tmp, "runs.db"))
        live_clock = lambda: {"verified": True, "delta_ms": 2.0, "rtt_ms": 1.0,
                             "broker_time": "2026-10-23T10:00:00"}

        # ── ۱) خوانش/داوریِ واقعی ───────────────────────────────────────────
        nav_mode("standard")
        st = UIS.read_ui_state(DRIVER, ui_opts(UIS))
        res = UIS.judge(st, ui_opts(UIS))
        ck(res.ok and res.verdict == "UNIQUE",
           "real DOM: single form -> UNIQUE and ok",
           {"verdict": res.verdict, "checks": res.checks, "reason": res.reason})
        ck(st.get("url_path") == "/order" and st.get("ready_state") == "complete",
           "real DOM: url_path/ready_state read from the real page", st.get("url_path"))
        ck((res.button or {}).get("in_viewport") is True
           and (res.button or {}).get("form_bound") is True,
           "real DOM: chosen button is in-viewport and bound to the price/qty form",
           res.button)
        candidates = {c["index"]: c for c in (st.get("submit_candidates") or [])}
        ck(len(candidates) == 1 and candidates[0]["aria"] == u"ارسال خرید",
           "real DOM: submit candidate carries its aria label", candidates)

        # ── ۲) dry-run: کلیکِ واقعی، صفر POSTِ رسیده ────────────────────────
        before = settle()
        rec, act, ex, warm, out = scenario(RC, AC, UIS, SC, "standard")
        settle()
        d = state.delta(before)
        ck(warm.get("ok") is True, "dry-run: prewarm resolves the real form", warm)
        ck(out["state"] == "DRY_RUN" and out.get("fired") is True,
           "dry-run: real click reached DRY_RUN", {k: out.get(k) for k in
                                                   ("state", "reason", "fired")})
        ck(d["click_main"] == 1 and d["order_hits"] == 0,
           "dry-run: one real click, zero order POST reached the server",
           {"clicks": d, "evidence": out.get("evidence", {}).get("request")})
        ck((out.get("evidence", {}).get("request") or {}).get("blocked") is True,
           "dry-run: the order write was blocked inside the browser",
           out.get("evidence", {}).get("request"))
        ck((out.get("metrics") or {}).get("click_to_request_ms") is not None,
           "dry-run: click->request latency measured", out.get("metrics"))
        ck((out.get("metrics") or {}).get("target_error_ms") is not None,
           "dry-run: target error measured against the planned wall time",
           out.get("metrics"))
        ck(STORE.get(rec.run_id).fired_actions == 1,
           "dry-run: store counted exactly one fired action", None)

        # ── ۳) دکمۀ هم‌نامِ مخفی: فقط نمایان کلیک می‌شود ────────────────────
        before = settle()
        rec, act, ex, warm, out = scenario(RC, AC, UIS, SC, "hidden")
        settle()
        d = state.delta(before)
        checks = (out.get("evidence") or {}).get("resolution", {}).get("checks", {})
        ck(out["state"] == "DRY_RUN" and d["click_main"] == 1 and d["click_hidden"] == 0,
           "hidden duplicate: visible button clicked, hidden one ignored",
           {"state": out["state"], "clicks": d})
        ck(str(checks.get("submit_hidden_same_name")) == "1",
           "hidden duplicate: evidence counted the hidden same-name button", checks)

        # ── ۴) دکمۀ هم‌نام در فرمِ دیگر: وابستگی به فرم جدا می‌کند ───────────
        before = settle()
        rec, act, ex, warm, out = scenario(RC, AC, UIS, SC, "otherform")
        settle()
        d = state.delta(before)
        ck(out["state"] == "DRY_RUN" and d["click_main"] == 1 and d["click_other"] == 0,
           "other-form duplicate: the form-bound button is the one clicked",
           {"state": out["state"], "clicks": d})

        # ── ۵) دو دکمۀ هم‌شرایط در همان فرم: مبهم، صفر کلیک ─────────────────
        before = settle()
        rec, act, ex, warm, out = scenario(RC, AC, UIS, SC, "multi")
        settle()
        d = state.delta(before)
        ck(out["state"] == "AMBIGUOUS" and _clicks(d) == 0 and d["order_hits"] == 0,
           "two usable buttons in the same form: AMBIGUOUS, zero clicks",
           {"state": out["state"], "clicks": d, "reason": out.get("reason")})

        # ── ۶) دکمۀ بیرونِ viewport ─────────────────────────────────────────
        before = settle()
        rec, act, ex, warm, out = scenario(RC, AC, UIS, SC, "offscreen")
        settle()
        d = state.delta(before)
        ck(out["state"] == "NO_USABLE_BUTTON" and _clicks(d) == 0,
           "off-viewport button: NO_USABLE_BUTTON, zero clicks",
           {"state": out["state"], "clicks": d, "reason": out.get("reason")})

        # ── ۷) دکمۀ غیرفعال ────────────────────────────────────────────────
        before = settle()
        rec, act, ex, warm, out = scenario(RC, AC, UIS, SC, "disabled")
        settle()
        d = state.delta(before)
        ck(out["state"] == "NO_USABLE_BUTTON" and _clicks(d) == 0,
           "disabled button: NO_USABLE_BUTTON, zero clicks",
           {"state": out["state"], "clicks": d})

        # ── ۸) فقط دکمۀ سمتِ مخالف ─────────────────────────────────────────
        before = settle()
        rec, act, ex, warm, out = scenario(RC, AC, UIS, SC, "sellonly")
        settle()
        d = state.delta(before)
        ck(out["state"] == "WRONG_SIDE_ONLY" and _clicks(d) == 0,
           "buy request with only a sell button: WRONG_SIDE_ONLY, zero clicks",
           {"state": out["state"], "clicks": d})

        # ── ۹) بی‌دکمه ──────────────────────────────────────────────────────
        before = settle()
        rec, act, ex, warm, out = scenario(RC, AC, UIS, SC, "nobutton")
        settle()
        d = state.delta(before)
        ck(out["state"] == "NO_BUTTON" and _clicks(d) == 0,
           "no submit button: NO_BUTTON, zero clicks",
           {"state": out["state"], "clicks": d})

        # ── ۱۰) قیمتِ فرم ≠ انتظار (فرم دست نمی‌خورد) ───────────────────────
        before = settle()
        rec, act, ex, warm, out = scenario(RC, AC, UIS, SC, "pricemismatch")
        settle()
        d = state.delta(before)
        price_after = DRIVER.read_value("#price")
        ck(out["state"] == "MISMATCH" and _clicks(d) == 0,
           "form price 1010 != expected 1000: MISMATCH, zero clicks",
           {"state": out["state"], "clicks": d})
        ck(price_after == "1010",
           "AutoClicker never rewrote the user's price field", price_after)

        # ── ۱۱) نمادِ فرم ≠ انتظار ─────────────────────────────────────────
        before = settle()
        rec, act, ex, warm, out = scenario(RC, AC, UIS, SC, "symbolmismatch")
        settle()
        d = state.delta(before)
        ck(out["state"] == "MISMATCH" and _clicks(d) == 0,
           "form symbol differs: MISMATCH, zero clicks",
           {"state": out["state"], "clicks": d})

        # ── ۱۲) جابه‌جاییِ صفحه بعد از ارزیابی ──────────────────────────────
        nav_mode("standard")
        rec = new_run(RC, first_ms=0)
        act = claim(RC, rec)
        ex = new_exec(AC, UIS)
        ck(ex.run_warm().get("ok") is True, "page-change: warm OK on /order")
        nav_path("/orders")
        before = settle()
        out = ex(rec, act, SC.FireHooks(run_id=rec.run_id, idx=act.idx, store=STORE,
                                        stop_event=threading.Event()))
        settle()
        d = state.delta(before)
        ck(out["state"] == "PAGE_CHANGED" and _clicks(d) == 0,
           "page changed after warm: PAGE_CHANGED, zero clicks",
           {"state": out["state"], "clicks": d})

        # ── ۱۳) میزبانِ بیرون از allowlist ─────────────────────────────────
        nav_path("/order", host="localhost")
        rec = new_run(RC, first_ms=0)
        act = claim(RC, rec)
        ex = new_exec(AC, UIS)
        before = settle()
        out = ex(rec, act, SC.FireHooks(run_id=rec.run_id, idx=act.idx, store=STORE,
                                        stop_event=threading.Event()))
        settle()
        d = state.delta(before)
        ck(out["state"] == "SESSION_LOST" and _clicks(d) == 0,
           "page on a non-allowlisted host: SESSION_LOST, zero clicks",
           {"state": out["state"], "clicks": d})

        # ── ۱۴) مسیرِ زنده فقط رویِ fixtureِ محلی: کلیک→POST→پاسخ→ACCEPTED ──
        nav_mode("standard")
        rec = new_run(RC, dry=False, first_ms=0)
        act = claim(RC, rec)
        ex = new_exec(AC, UIS, dry=False, clock=live_clock)
        ck(ex.run_warm().get("ok") is True, "live-path: warm OK before the click")
        before = settle()
        out = ex(rec, act, SC.FireHooks(run_id=rec.run_id, idx=act.idx, store=STORE,
                                        stop_event=threading.Event()))
        settle()
        d = state.delta(before)
        ck(out["state"] == "ACCEPTED" and d["order_hits"] == 1 and d["click_main"] == 1,
           "live-path on local fixture: one click, one POST, ACCEPTED from the wire",
           {"state": out["state"], "broker_order_id": out.get("broker_order_id"),
            "clicks": d})
        ck((out.get("metrics") or {}).get("request_rtt_ms") is not None,
           "live-path: request RTT measured", out.get("metrics"))
        ck(out.get("broker_order_id") == "LOCAL-MOCK-1",
           "live-path: broker order id comes from the response body",
           out.get("broker_order_id"))

        # ── ۱۵) تکرارِ محدود: ۳ اقدام، فاصله، شمارشِ پایدار ────────────────
        nav_mode("standard")
        before = settle()
        rec = new_run(RC, count=3, interval=400.0, mode="repeat", first_ms=1200)
        ex = new_exec(AC, UIS)
        runner = SC.AutoClickRunRunner(
            STORE, executor=ex, warm=lambda _run: ex.run_warm(),
            clock=time.monotonic, spin_ms=4, missed_grace_ms=60000)
        runner.start()
        deadline = time.monotonic() + 20
        final = STORE.get(rec.run_id)
        while time.monotonic() < deadline:
            final = STORE.get(rec.run_id)
            if final.state in ("COMPLETED", "BLOCKED", "NEEDS_REVIEW",
                               "MISSED_TARGET", "STOPPED"):
                break
            time.sleep(0.1)
        runner.close()
        settle()
        d = state.delta(before)
        ck(final.state == "COMPLETED" and final.fired_actions == 3,
           "repeat: three scheduled actions completed and counted in the store",
           {"state": final.state, "fired": final.fired_actions})
        ck(d["click_main"] == 3 and d["order_hits"] == 0,
           "repeat: three real clicks, zero order POST reached the server",
           {"clicks": d})
        results = [(a.result or {}).get("state") for a in final.actions]
        ck(results == ["DRY_RUN", "DRY_RUN", "DRY_RUN"],
           "repeat: every action row carries its own DRY_RUN verdict", results)
        planned = [a.planned_at_ms for a in final.actions]
        ck(planned[1] - planned[0] == 400 and planned[2] - planned[1] == 400,
           "repeat: planned spacing follows the configured interval", planned)
        fired = [a.fired_at_ms or 0 for a in final.actions]
        gaps = [fired[1] - fired[0], fired[2] - fired[1]]
        ck(all(g >= 300 for g in gaps),
           "repeat: measured spacing never below the 300 ms floor", gaps)
        ck(all((a.result or {}).get("metrics", {}).get("click_to_request_ms") is not None
               for a in final.actions),
           "repeat: click->request latency present per action", None)
        ck(all(a.state == "DONE" for a in final.actions),
           "repeat: every action row is DONE, no row left claimed",
           [a.state for a in final.actions])

        # ── ۱۶) توقفِ اضطراری بی‌شبکه ───────────────────────────────────────
        nav_mode("standard")
        rec = new_run(RC, first_ms=2500)
        ex = new_exec(AC, UIS)
        runner = SC.AutoClickRunRunner(
            STORE, executor=ex, warm=lambda _run: ex.run_warm(),
            clock=time.monotonic, spin_ms=4, missed_grace_ms=60000)
        runner.start()
        time.sleep(0.7)
        before = settle()
        stop = runner.stop(reason="توقفِ اضطراریِ گارد")
        time.sleep(0.4)
        runner.close()
        final = STORE.get(rec.run_id)
        settle()
        d = state.delta(before)
        ck(final.state == "STOPPED" and final.fired_actions == 0 and _clicks(d) == 0,
           "emergency stop before the target: STOPPED, zero clicks",
           {"state": final.state, "stop": stop, "clicks": d})

        # ── ۱۷) پنل + نشست + CDP ────────────────────────────────────────────
        nav_mode("standard")
        ck(EP.panel_asset_present()[0], "panel asset exists on disk",
           EP.panel_asset_present()[1])
        sp = EP.session_presence(CDP, broker_hosts=("127.0.0.1",))
        ck(sp.get("state") == "LOGIN_REQUIRED",
           "session probe without oidc key: LOGIN_REQUIRED", sp)
        opened = open_tab(FIX + "/app")
        ck(opened == 2, "a second broker tab was opened for the login proof",
           {"tabs_in_context": opened})
        sp = EP.session_presence(CDP, broker_hosts=("127.0.0.1",))
        blob = json.dumps(sp, ensure_ascii=False)
        ck(sp.get("state") == "LOGGED_IN",
           "session probe with oidc key and no visible password: LOGGED_IN", sp)
        ck("SECRET" not in blob and "access_token" not in blob,
           "session probe returns no token value", blob)
        ck(close_path("/app") == 1, "login-proof tab closed")
        time.sleep(0.15)
        ck(EP.session_presence(CDP, broker_hosts=("127.0.0.1",)).get("state")
           == "LOGIN_REQUIRED",
           "session probe after closing the proof tab: LOGIN_REQUIRED again")

        ts = EP.PanelTicketStore()
        tk = ts.mint(cdp_url=CDP)
        panel_url = EP.panel_url_for(FIX, tk.value)
        ck(panel_url == FIX + "/static/autoclicker/panel.html#ticket=" + tk.value,
           "panel url carries the one-time ticket in the fragment", None)
        shape_before = context_shape()
        r1 = EP.open_panel_tab(CDP, panel_url)
        ck(r1.get("status") == "success" and r1.get("opened") is True,
           "panel opened as a real tab", r1)
        shape_after = context_shape()
        ck(len(shape_after) == 1 and shape_after[0] == shape_before[0] + 1,
           "panel tab lives in the SAME context/profile as the broker page",
           {"before": shape_before, "after": shape_after})
        r2 = EP.open_panel_tab(CDP, panel_url)
        ck(r2.get("already_open") is True and context_shape() == shape_after,
           "opening the panel twice does not create a second controller tab", r2)
        tabs = EP.list_tabs(CDP, broker_hosts=("127.0.0.1",))
        ck(tabs.get("status") == "success"
           and any(t.get("is_panel") for t in tabs.get("tabs") or [])
           and any(t.get("is_broker") for t in tabs.get("tabs") or []),
           "list_tabs sees both the broker page and the panel tab", tabs)
        ck(ts.verify(tk.value, cdp_url=CDP)[0] is True,
           "panel ticket verifies against its bound CDP host")
        ck(ts.verify(tk.value, cdp_url="http://127.0.0.1:1") ==
           (False, "TICKET_BINDING_CHANGED"),
           "panel ticket refused on another CDP host")
        ck(ts.verify("bogus") == (False, "UNKNOWN_TICKET"),
           "unknown panel ticket refused")
        ck(EP.open_panel_tab("http://example.com:9222", panel_url).get("code")
           == "CDP_NOT_LOOPBACK",
           "panel refuses a non-loopback CDP endpoint")
        ck(EP.list_tabs("http://example.com:9222").get("code") == "CDP_NOT_LOOPBACK",
           "list_tabs refuses a non-loopback CDP endpoint")
        try:
            ts.mint(cdp_url="http://example.com:9222")
            mint_refused = False
        except ValueError:
            mint_refused = True
        ck(mint_refused, "ticket minting refuses a non-loopback CDP endpoint")
        ck(EP.close_panel_tab(CDP).get("closed") == 1,
           "panel tab closes without touching the broker page")
        ck(context_shape() == shape_before,
           "after closing the panel only the broker tab remains", context_shape())

        # ── ۱۸) جمعِ نهایی: تنها POSTِ رسیده همان آزمونِ fixture بود ─────────
        final_counts = settle()
        ck(final_counts["order_hits"] == 1,
           "aggregate: exactly one order POST ever reached any server "
           "(the local live-path fixture)", final_counts)
    finally:
        try:
            if DRIVER is not None:
                DRIVER.close()
        except Exception:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass
        for _ in range(3):
            try:
                shutil.rmtree(tmp, ignore_errors=True)
                if not os.path.isdir(tmp):
                    break
            except Exception:
                pass
            time.sleep(0.2)
        cleanup = state.snap()

    print("")
    print("%d/%d passed, %d skipped" % (PASS, PASS + FAIL, SKIP))
    print("AUTOCLICKER ROUND22 BROWSER " + ("OK" if FAIL == 0 else "FAILED"))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
