#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mofid_session_v1165 — ورودِ دستی/پلِ نشست و گاردِ سخت‌گیرانهٔ فقط‌خواندنی.

سه لایه را با هم می‌سنجد:
  ۱) parse توکن و پلِ CDP با یک صفحهٔ محلی و Playwright (بدونِ کارگزاری).
  ۲) allowlistِ MofidAdapter: GET-only، order detail فقط با شناسهٔ فهرست،
     ردِ POST/مسیرِ ناشناخته پیش از هر ترافیک.
  ۳) مسیرِ API: verify-session با captureِ بدل، حالت‌های READ_ONLY_PROBE_OK،
     SESSION_EXPIRED، READ_ONLY_PROBE_FAILED و صفر دادهٔ کهنه/راز.
هیچ درخواستِ واقعی به کارگزاری و هیچ سفارشی ساخته نمی‌شود.
"""
from __future__ import annotations

import base64
import json
import os
import queue
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from urllib.request import urlopen

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
        print("FAIL " + label + "  -> " + str(detail)[:300])


def skip(label, detail=""):
    global SKIP
    SKIP += 1
    print("SKIP " + label + (("  -> " + str(detail)[:160]) if detail else ""))


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


STATUS = ('{"data":{"purchasingPower":500000000,"accountBalanceT2":400000000,'
          '"blockedBalance":10000000,"credit":0,"marginBlock":0}}')
PORTFOLIO = ('{"data":[{"symbolIsin":"IRO1TEST0001","symbolName":"TEST",'
             '"currentAsset":1000,"todayBoughtAsset":200,"todaySoldAsset":100,'
             '"openSellOrders":50,"openBuyOrders":0,"averageBuyPrice":2000}]}')
ORDERS = ('{"data":[{"orderId":"O-1","symbol":"TEST","symbolIsin":"IRO1TEST0001",'
          '"orderSide":"Buy","orderPrice":2474,"quantity":10,'
          '"executedQuantity":4,"orderState":"Open"}]}')
TODAY = ('{"data":[{"orderId":"O-2","symbol":"TEST","symbolIsin":"IRO1TEST0001",'
         '"orderSide":"Sell","orderPrice":2500,"quantity":5,'
         '"executedQuantity":0,"orderState":"Done"}]}')
DETAIL = ('{"data":{"orderId":"%s","orderState":"Done","quantity":10,'
          '"executedQuantity":10,"orderPrice":2474,"symbolIsin":"IRO1TEST0001"}}')


def _b64(obj):
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")


def expired_jwt():
    return _b64({"alg": "none"}) + "." + _b64({"exp": 1}) + ".sig"


class PageHandler(BaseHTTPRequestHandler):
    def log_message(self, *_a):
        return

    def do_GET(self):
        p = urlparse(self.path)
        if p.path not in ("/token", "/empty", "/expired"):
            self.send_response(404)
            self.end_headers()
            return
        token = ("T" * 48) if p.path == "/token" else (
            expired_jwt() if p.path == "/expired" else "")
        body = ("<!doctype html><meta charset='utf-8'><title>mofid mock</title>"
                "<script>localStorage.setItem('token', %s);</script>"
                % json.dumps(token)).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])
    finally:
        s.close()


def _wait_cdp(port, timeout=15.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen("http://127.0.0.1:%d/json/version" % port, timeout=0.5) as r:
                if int(getattr(r, "status", 0) or 0) == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


def browser_capture_checks() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:                       # noqa: BLE001
        skip("Playwright در دسترس نیست", type(e).__name__)
        return
    from execution_browser import browser_candidates
    from execution_mofid_capture import CaptureError, capture_from_host
    server = ThreadingHTTPServer(("127.0.0.1", 0), PageHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = int(server.server_port)
    base = "http://127.0.0.1:%d" % port
    cdp_port = _free_port()
    profile = tempfile.mkdtemp(prefix="mofid_cap_")
    ready = threading.Event()
    cmds: queue.Queue = queue.Queue()
    launch_err: list[str] = []
    cdp = "http://127.0.0.1:%d" % cdp_port

    def launcher():
        # Playwrightِ sync thread-affine است؛ اجرای هم‌زمانِ دو نمونه در یک thread
        # خطا می‌دهد. این thread فقط مرورگر را باز/هدایت می‌کند و thread اصلی
        # capture_from_host را با نمونهٔ خودش صدا می‌زند.
        try:
            with sync_playwright() as p:
                exe = next((x for x in browser_candidates()
                            if x and os.path.isfile(x)), p.chromium.executable_path)
                ctx = p.chromium.launch_persistent_context(
                    user_data_dir=profile, headless=True, executable_path=exe,
                    args=["--remote-debugging-address=127.0.0.1",
                          "--remote-debugging-port=%d" % cdp_port,
                          "--no-first-run", "--no-default-browser-check"])
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                page.goto(base + "/token", wait_until="domcontentloaded")
                ready.set()
                while True:
                    path = cmds.get()
                    if path is None:
                        break
                    page.goto(base + path, wait_until="domcontentloaded")
                    cmds.task_done()
                ctx.close()
        except Exception as e:                   # noqa: BLE001
            launch_err.append(type(e).__name__)
            ready.set()

    thread = threading.Thread(target=launcher, daemon=True)
    thread.start()
    ready.wait(25)
    try:
        if launch_err or not _wait_cdp(cdp_port, timeout=5):
            skip("مرورگرِ آزمونِ CDP بالا نیامد", launch_err or "no cdp")
            return
        token, meta = capture_from_host(cdp, allowed_hosts=("127.0.0.1",))
        ck(token == "T" * 48 and meta.get("page_host") == "127.0.0.1"
           and meta.get("token_type") == "Bearer"
           and token not in json.dumps(meta),
           "پلِ CDP توکنِ صفحهٔ مجاز را می‌خواند و در meta نمی‌گذارد", meta)
        cmds.put("/empty"); cmds.join()
        try:
            capture_from_host(cdp, allowed_hosts=("127.0.0.1",))
            empty_code = None
        except CaptureError as e:
            empty_code = e.code
        ck(empty_code == "NO_SESSION",
           "صفحهٔ بی‌توکن ⇒ NO_SESSION، نه نشستِ جعلی", empty_code)
        cmds.put("/expired"); cmds.join()
        try:
            capture_from_host(cdp, allowed_hosts=("127.0.0.1",))
            exp_code = None
        except CaptureError as e:
            exp_code = e.code
        ck(exp_code == "EXPIRED", "توکنِ منقضی ⇒ EXPIRED", exp_code)
    finally:
        cmds.put(None)
        thread.join(timeout=8)
        server.shutdown()
        shutil.rmtree(profile, ignore_errors=True)


def parse_checks() -> None:
    from execution_mofid_capture import CaptureError, parse_mofid_token
    for raw, code in (("", "NO_SESSION"), ("short", "BAD_TOKEN"), (expired_jwt(), "EXPIRED")):
        try:
            parse_mofid_token(raw)
            got = None
        except CaptureError as e:
            got = e.code
        ck(got == code, "parse: %r ⇒ %s" % (raw[:12], code), got)
    token, meta = parse_mofid_token("T" * 48, page_host="tg.mofidonline.com",
                                    page_path="/")
    ck(token == "T" * 48 and meta["token_type"] == "Bearer"
       and token not in json.dumps(meta) and meta["token_length"] == 48,
       "parse: توکن در حافظه می‌ماند و meta فقط طول/نوع دارد", meta)


def adapter_checks() -> None:
    from execution_contract import (
        ErrorCode, InstrumentRef, OrderDraft, OrderMode, Resolution, Side,
    )
    from execution_easytrader import TransportTimeout, WireResponse
    from execution_mofid import MofidAdapter, WIRE_URL

    rt = RouteTransport({
        "/Order/customer/status": WireResponse(200, {}, STATUS),
        "/Portfolio/Daily": WireResponse(200, {}, PORTFOLIO),
        "/Order/open-orders": WireResponse(200, {}, ORDERS),
        "/Order/today-order": WireResponse(200, {}, TODAY),
        "/Order/detail/O-1": WireResponse(200, {}, DETAIL % "O-1"),
        "/Order/detail/O-2": WireResponse(200, {}, DETAIL % "O-2"),
    })
    ad = MofidAdapter(transport=rt, token="T" * 48, writes_allowed=False)
    ck(ad.read_only and not ad.writes_allowed, "adapter با writes_allowed=false وارد read_only می‌شود")
    ad.authenticate()
    ad.get_orders()
    ad.get_today_orders()
    ck(ad.get_order("O-1") is not None and ad.get_order("O-2") is not None,
       "detail فقط برایِ شناسه‌هایِ فهرست کار می‌کند")
    before = len(rt.calls)
    try:
        ad.get_order("FAKE-ID")
        fake_code = None
    except Exception as e:                       # noqa: BLE001
        fake_code = getattr(e, "code", None)
    ck(fake_code is ErrorCode.UNSUPPORTED and len(rt.calls) == before,
       "شناسهٔ ساختگی پیش از هر درخواست مسدود می‌شود", fake_code)
    try:
        ad._call("POST", WIRE_URL, tag="send", payload={})
        post_code = None
    except Exception as e:                       # noqa: BLE001
        post_code = getattr(e, "code", None)
    ck(post_code is ErrorCode.UNSUPPORTED and len(rt.calls) == before,
       "POST در read_only پیش از ترافیک رد می‌شود", post_code)
    try:
        ad._call("GET", "https://mofidonline.com/apigateway/api/v1/Other",
                 tag="other")
        other_code = None
    except Exception as e:                       # noqa: BLE001
        other_code = getattr(e, "code", None)
    ck(other_code is ErrorCode.UNSUPPORTED and len(rt.calls) == before,
       "GETِ بیرون از allowlist رد می‌شود", other_code)
    instr = InstrumentRef(symbol="TEST", isin="IRO1TEST0001",
                          broker_instrument="IRO1TEST0001", resolution=Resolution.EXACT)
    draft = OrderDraft("R17-1", instr, Side.BUY, 1000.0, 1.0, OrderMode.SAFE)
    try:
        ad.submit_order(draft)
        sub_code = None
    except Exception as e:                       # noqa: BLE001
        sub_code = getattr(e, "code", None)
    ck(sub_code is ErrorCode.UNSUPPORTED
       and not any(c["method"] != "GET" for c in rt.calls),
       "submit_order در read_only هیچ POSTی نمی‌سازد", sub_code)

    # 401: توکن/کش باطل؛ درخواست بعدی دادهٔ کهنه نمی‌دهد.
    seq = {"n": 0}

    def flaky(method, url, headers, payload):
        seq["n"] += 1
        return WireResponse(200 if seq["n"] == 1 else 401, {},
                            STATUS if seq["n"] == 1 else "{}")

    ad_flaky = MofidAdapter(
        transport=RouteTransport({"/Order/customer/status": flaky}),
        token="T" * 48, writes_allowed=False)
    ad_flaky.authenticate()
    try:
        ad_flaky.authenticate()                  # دومین GET عمداً 401 می‌دهد
    except Exception:                            # noqa: BLE001
        pass
    try:
        ad_flaky.get_money()
        stale = "returned"
    except Exception as e:                       # noqa: BLE001
        stale = getattr(e, "code", None)
    ck(stale is ErrorCode.SESSION_EXPIRED and not ad_flaky.session_proven(),
       "401 پس از نشستِ سالم، توکن/کش را باطل می‌کند و داده کهنه نمی‌دهد", stale)


def api_checks() -> None:
    tmp = tempfile.mkdtemp(prefix="mofid_r17_")
    os.environ["BORS_DATA_DIR"] = tmp
    os.environ["BORS_TEST_ISOLATION"] = "1"
    open(os.path.join(tmp, ".bors_test_isolation"), "w").close()
    os.environ["BORS_USER_DB"] = os.path.join(tmp, "user.db")
    os.environ["BORS_INTENT_DB"] = os.path.join(tmp, "intents.db")
    os.environ["BORS_EXECUTION_ADAPTER"] = "mock"
    from execution_easytrader import TransportTimeout, WireResponse
    from execution_mofid import MofidAdapter
    import api.execution as EX

    old = (EX._ACTIVE_ADAPTER, EX.ADAPTER_KIND, EX.TRAFFIC_ALLOWED,
           EX.READ_ONLY_REQUESTED, EX._SERVICE.adapter,
           EX.EMC.capture_from_host, EX.BH.read_status, EX.BH.stop_host,
           EX.subprocess.Popen)
    rt = RouteTransport({
        "/Order/customer/status": WireResponse(200, {}, STATUS),
        "/Portfolio/Daily": WireResponse(200, {}, PORTFOLIO),
        "/Order/open-orders": WireResponse(200, {}, ORDERS),
        "/Order/today-order": WireResponse(200, {}, TODAY),
        "/Order/detail/O-1": WireResponse(200, {}, DETAIL % "O-1"),
        "/Order/detail/O-2": WireResponse(200, {}, DETAIL % "O-2"),
    })
    adapter = MofidAdapter(transport=rt, token="x", writes_allowed=False)
    EX._ACTIVE_ADAPTER = adapter
    EX.ADAPTER_KIND = "mofid"
    EX.TRAFFIC_ALLOWED = True
    EX.READ_ONLY_REQUESTED = True
    EX._SERVICE.adapter = adapter
    captured = "T" * 48
    EX.EMC.capture_from_host = lambda *_a, **_k: (
        captured, {"page_host": "tg.mofidonline.com", "token_type": "Bearer",
                   "token_length": 48, "expires_at": None})
    EX.BH.read_status = lambda *a, **k: {
        "status": "ready", "healthy": True, "name": "mofid",
        "cdp_url": "http://127.0.0.1:1"}
    out = EX._mofid_verify_session()
    ck(out.get("status") == "success" and out.get("state") == "READ_ONLY_PROBE_OK"
       and (out.get("account") or {}).get("buying_power") == 500000000
       and out.get("live_enabled") is False and out.get("live_ready") is False
       and out.get("read_only") is True,
       "verify: READ_ONLY_PROBE_OK با حسابِ خوانده‌شده و نوشتنِ بسته", out.get("state"))
    acct = out.get("account") or {}
    ck(len(acct.get("positions") or []) == 1
       and len(acct.get("orders") or []) == 1
       and len(acct.get("today_orders") or []) == 1
       and len(acct.get("order_details") or []) == 2,
       "پرتفوی/سفارش‌های باز/امروز/جزئیاتِ مجاز در پاسخ هست",
       {k: len(acct.get(k) or []) for k in ("positions", "orders", "today_orders",
                                            "order_details")})
    ck(captured not in json.dumps(out, ensure_ascii=False, default=str)
       and all(c["method"] == "GET" for c in rt.calls),
       "پاسخِ verify توکن ندارد و همهٔ درخواست‌ها GET‌اند", rt.calls)
    sess = EX.get_mofid_session()
    ck(sess.get("state") == "READ_ONLY_PROBE_OK" and "account" not in sess
       and captured not in json.dumps(sess, default=str),
       "session فقط metadata/شمارش می‌دهد، نه حساب/توکن", sess)

    # 401 => SESSION_EXPIRED، account=None
    rt401 = RouteTransport({"/Order/customer/status": WireResponse(401, {}, "{}")})
    ad401 = MofidAdapter(transport=rt401, token="x", writes_allowed=False)
    EX._ACTIVE_ADAPTER = ad401
    EX._SERVICE.adapter = ad401
    out401 = EX._mofid_verify_session()
    ck(out401.get("state") == "SESSION_EXPIRED" and out401.get("account") is None
       and not ad401.session_proven(),
       "401 در verify ⇒ SESSION_EXPIRED و بی‌حساب", out401.get("state"))

    # timeout => READ_ONLY_PROBE_FAILED، account=None
    rt_to = RouteTransport({"/Order/customer/status": TransportTimeout("no")})
    ad_to = MofidAdapter(transport=rt_to, token="x", writes_allowed=False)
    EX._ACTIVE_ADAPTER = ad_to
    EX._SERVICE.adapter = ad_to
    out_to = EX._mofid_verify_session()
    ck(out_to.get("state") == "READ_ONLY_PROBE_FAILED"
       and out_to.get("account") is None,
       "timeout در verify ⇒ READ_ONLY_PROBE_FAILED و بی‌حساب", out_to.get("state"))

    # no orders => SKIPPED_NO_ORDERS و هیچ detailِ حدسی
    rt_empty = RouteTransport({
        "/Order/customer/status": WireResponse(200, {}, STATUS),
        "/Portfolio/Daily": WireResponse(200, {}, PORTFOLIO),
        "/Order/open-orders": WireResponse(200, {}, '{"data":[]}'),
        "/Order/today-order": WireResponse(200, {}, '{"data":[]}'),
    })
    ad_empty = MofidAdapter(transport=rt_empty, token="x", writes_allowed=False)
    EX._ACTIVE_ADAPTER = ad_empty
    EX._SERVICE.adapter = ad_empty
    out_empty = EX._mofid_verify_session()
    ck(out_empty.get("state") == "READ_ONLY_PROBE_OK"
       and (out_empty.get("steps") or {}).get("order_detail") == "SKIPPED_NO_ORDERS"
       and not any("/Order/detail/" in c["url"] for c in rt_empty.calls),
       "بدونِ سفارش، detail حدسی فرستاده نمی‌شود", out_empty.get("steps"))

    # login window: نامِ mofid + URLِ اول‌طرف، بدونِ host پیش‌فرض
    calls = {}
    state = {"healthy": False}

    class FakeProc:
        pid = 12345

    def fake_popen(cmd, **kw):
        calls["cmd"] = list(cmd)
        state["healthy"] = True
        return FakeProc()

    EX.subprocess.Popen = fake_popen
    EX.BH.read_status = lambda *a, **k: {
        "status": "ready" if state["healthy"] else "closed",
        "healthy": state["healthy"], "name": "mofid", "cdp_url": "http://127.0.0.1:1"}
    req = types.SimpleNamespace(headers={})
    win = EX.post_mofid_login_window(req)
    cmd = calls.get("cmd") or []
    ck(win.get("status") == "success" and win.get("adapter_ready") is True
       and "--name" in cmd and "mofid" in cmd
       and any("tg.mofidonline.com" in str(x) for x in cmd),
       "پنجرهٔ ورود با نام/URLِ اول‌طرف باز می‌شود", cmd)
    stopped = {}
    EX.BH.stop_host = lambda name="": (stopped.update({"name": name}) or
                                       {"status": "closed", "name": name})
    EX.delete_mofid_login_window()
    ck(stopped.get("name") == "mofid", "بستن فقط hostِ mofid را هدف می‌گیرد", stopped)

    EX._ACTIVE_ADAPTER, EX.ADAPTER_KIND, EX.TRAFFIC_ALLOWED, EX.READ_ONLY_REQUESTED = (
        old[0], old[1], old[2], old[3])
    EX._SERVICE.adapter = old[4]
    EX.EMC.capture_from_host = old[5]
    EX.BH.read_status, EX.BH.stop_host = old[6], old[7]
    EX.subprocess.Popen = old[8]


def host_checks() -> None:
    import execution_browser_host as BH
    ck(BH.status_path("mofid").endswith("bors_browser_host_mofid.json")
       and BH._profile("mofid").endswith("browser_host_profile_mofid")
       and BH._host_suffix("../x") == "_x",
       "hostِ نام‌دارِ mofid مسیر/پروفایلِ جدا و نامِ امن دارد",
       {"status": BH.status_path("mofid"), "profile": BH._profile("mofid")})
    ck(BH.status_path("mofid") != BH.status_path(""),
       "وضعیتِ mofid با hostِ پیش‌فرضِ EasyTrader قاطی نمی‌شود")


def main() -> int:
    print("dev/mofid_session_v1165 — ورودِ دستی، پلِ CDP و allowlistِ فقط‌خواندنی")
    parse_checks()
    adapter_checks()
    browser_capture_checks()
    api_checks()
    host_checks()
    print("\n%d checks, %d failed, %d skipped" % (PASS + FAIL, FAIL, SKIP))
    print("MOFID SESSION " + ("OK" if FAIL == 0 else "FAILED"))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
