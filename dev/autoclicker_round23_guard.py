#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""autoclicker_round23_guard — رگرسیونِ نقص‌هایِ کشف‌شده در سنجشِ زندهٔ ۲۰۲۶-۱۰-۲۴.

سناریویِ محوری: صفحه‌ای با service worker واقعی که POSTِ سفارش را خودش
forward می‌کند. گاردِ صفحه‌ای (page.route) این درخواست را نمی‌دید و در آزمونِ
زنده یک POST به کارگزاری رسید؛ گاردِ CDP باید آن را در لایهٔ شبکه ببندد.

هر بررسی «ok label» چاپ می‌کند و در پایان شمارش دقیق می‌دهد.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PASS = 0
FAIL = 0


def ok(label: str, cond: bool, detail: str = "") -> bool:
    global PASS, FAIL
    if cond:
        PASS += 1
        print("ok   %s" % label)
    else:
        FAIL += 1
        print("FAIL %s%s" % (label, (" -> " + detail) if detail else ""))
    return bool(cond)


# ── fixture: صفحه + service worker ──────────────────────────────────────────
PAGE = b"""<!doctype html><html><body>
<button id="go">send</button>
<script>
navigator.serviceWorker.register('/sw.js').then(function(){
  return navigator.serviceWorker.ready;
}).then(function(){ window.__sw_ready = !!navigator.serviceWorker.controller; });
document.getElementById('go').onclick = function(){
  fetch('/core/api/v2/order', {method:'POST', headers:{'content-type':'application/json'},
        body: JSON.stringify({order:{symbol:'TEST', qty:1}})}).catch(function(){});
};
</script></body></html>"""

SW = b"""self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', e => {
  if (e.request.url.indexOf('/core/api/v2/order') >= 0) {
    var u = new URL(e.request.url);
    u.searchParams.set('via', 'sw');
    e.respondWith(fetch(u.toString(), {method: 'POST',
                 headers: {'content-type': 'application/json'},
                 body: '{"order":{"via":"sw"}}'}));
  }
});"""

POSTS: list[dict] = []
LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):                    # noqa: A003
        pass

    def _send(self, body: bytes, ctype: str = "text/html; charset=utf-8",
              status: int = 200, extra: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Service-Worker-Allowed", "/")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):                             # noqa: N802
        if self.path.startswith("/page"):
            self._send(PAGE)
        elif self.path == "/sw.js":
            self._send(SW, "application/javascript")
        else:
            self._send(b"ok", "text/plain")

    def do_POST(self):                            # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else b""
        with LOCK:
            POSTS.append({"path": self.path,
                          "via_sw": "1" if "via=sw" in self.path else None,
                          "len": len(body)})
        self._send(b'{"isSuccessful":true,"id":"SW-MOCK-1"}', "application/json")


def _start_server() -> tuple[ThreadingHTTPServer, int]:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, int(srv.server_address[1])


def _count(via_sw: str | None = None) -> int:
    with LOCK:
        rows = list(POSTS)
    if via_sw is None:
        return len(rows)
    return sum(1 for r in rows if r.get("via_sw") == via_sw)


def main() -> int:
    srv, port = _start_server()
    base = "http://127.0.0.1:%d" % port
    import execution_browser as EB
    import execution_strategy_core as SC

    settings = SC.default_settings(SC.AUTOCLICKER)
    settings.options.update({
        "order_url": base + "/page",
        #: عایق از hostِ زندهٔ مالک؛ این گارد مرورگرِ خودش را می‌سازد.
        "cdp_url": "",
        "headless": True,
        "profile_dir": os.path.join(tempfile.gettempdir(), "bors_r23_sw_profile"),
        "action_timeout_ms": 6000,
        "navigation_timeout_ms": 20000,
        "order_paths": ["/core/api/v2/order"],
        "origin_allowlist": ["http://127.0.0.1:%d" % port],
    })
    drv = EB.PlaywrightBrowserDriver(settings, strategy_id="r23-guard")
    try:
        drv.start()
        drv.goto(base + "/page", timeout_ms=20000)
        # انتظارِ کنترلِ service worker
        controlled = False
        for _ in range(40):
            try:
                controlled = bool(drv.evaluate(
                    "() => !!navigator.serviceWorker.controller"))
            except Exception:
                controlled = False
            if controlled:
                break
            drv.evaluate("() => navigator.serviceWorker.ready.then(() => 0)")
            time.sleep(0.1)
        ok("service worker صفحه را کنترل می‌کند", controlled)

        # ۱) کاناری: بی‌گارد، POST باید از SW به سرور برسد
        drv.click("#go")
        for _ in range(40):
            if _count("1"):
                break
            time.sleep(0.1)
        ok("کاناری: POSTِ سفارش از service worker گذشت", _count("1") >= 1,
           "posts=%d via_sw=%d" % (_count(), _count("1")))
        # ۲) گاردِ dry-run: هیچ POSTی نباید به سرور برسد
        with LOCK:
            POSTS.clear()
        guard = drv.dry_run_guard(["/core/api/v2/order"], "POST")
        ok("گاردِ CDP مسلح شد", bool((guard.get("cdp_block") or {}).get("armed")),
           json.dumps(guard.get("cdp_block"), ensure_ascii=False))
        drv.click("#go")
        time.sleep(1.2)
        net = drv.network()
        ok("هیچ POSTی به سرورِ fixture نرسید", _count() == 0, "posts=%d" % _count())
        ok("درخواست در لایهٔ شبکه بسته شد", int(net.get("blocked_writes") or 0) >= 1,
           json.dumps(net, ensure_ascii=False)[:300])
        ok("هیچ نوشتنِ فراری دیده نشد", int(net.get("escaped_writes") or 0) == 0,
           json.dumps(net, ensure_ascii=False)[:300])
        ok("منبعِ شمارش CDP است", net.get("network_source") == "cdp",
           str(net.get("network_source")))

        # ۳) برداشتنِ گارد: همان کلیک باید دوباره به سرور برسد
        drv.intercept("**/core/api/v2/order*", abort=False)
        drv.click("#go")
        for _ in range(40):
            if _count():
                break
            time.sleep(0.1)
        ok("پس از برداشتنِ گارد، POSTِ تازه رسید", _count() >= 1, "posts=%d" % _count())
        # ۴) درخواستِ سفارشِ گذرکرده از service worker در CDP دیده می‌شود.
        #    بدنهٔ پاسخِ respondWith‌شده رویِ targetِ صفحه `loadingFinished`
        #    ندارد و از این مسیر خواندنی نیست؛ برایِ آن حالت `body_unavailable`
        #    صریح می‌ماند و داوری UNKNOWN است، نه ACCEPTEDِ کاذب.
        req = drv.wait_for_request(3000)
        ok("درخواستِ سفارش با متدِ POST در CDP دیده شد",
           bool(req) and str((req or {}).get("method")).upper() == "POST",
           json.dumps(req, ensure_ascii=False)[:300])
    finally:
        try:
            drv.close()
        except Exception:
            pass
        srv.shutdown()

    # ── واحد: تنظیماتِ تازه دیگر 500 نمی‌دهد ────────────────────────────────
    try:
        import api.execution_autoclicker as ACC
        import execution_strategy_core as SC2
        tmp = os.path.join(tempfile.mkdtemp(prefix="bors_r23_"), "user.db")
        orig = SC2.StrategySettingsStore
        SC2.StrategySettingsStore = lambda: orig(tmp)
        try:
            st = ACC.strategy_settings()
            ok("loaderِ تنظیمات با دیتابیسِ تازه کار می‌کند",
               st.strategy_id == SC2.AUTOCLICKER, repr(st))
        finally:
            SC2.StrategySettingsStore = orig
        ok("origin_allowlist کامل به hostname تبدیل می‌شود",
           ACC._hostnames(["https://d.easytrader.ir", "easytrader.ir"])
           == ("d.easytrader.ir", "easytrader.ir"),
           repr(ACC._hostnames(["https://d.easytrader.ir", "easytrader.ir"])))
        #: کلیدِ صریحِ خالی باید گارد را از hostِ زندهٔ مالک عایق کند؛ وگرنه
        #: درایورِ آزمون به مرورگرِ واقعی وصل می‌شود (سنجش ۲۰۲۶-۱۰-۲۴).
        ok("cdp_url صریحِ خالی، انتخابِ خودکارِ host را خاموش می‌کند",
           EB._resolve_cdp_url({"cdp_url": ""}) == "",
           repr(EB._resolve_cdp_url({"cdp_url": ""})))
        ok("cdp_url صریح بر انتخابِ خودکار مقدم است",
           EB._resolve_cdp_url({"cdp_url": "http://127.0.0.1:9"})
           == "http://127.0.0.1:9")
        _old_cdp = os.environ.get("BORS_EXECUTION_CDP_URL")
        os.environ["BORS_EXECUTION_CDP_URL"] = "http://127.0.0.1:7777"
        try:
            ok("بدونِ کلیدِ صریح، hostِ اعلام‌شده کشف می‌شود",
               EB._resolve_cdp_url({}) == "http://127.0.0.1:7777",
               repr(EB._resolve_cdp_url({})))
        finally:
            if _old_cdp is None:
                os.environ.pop("BORS_EXECUTION_CDP_URL", None)
            else:
                os.environ["BORS_EXECUTION_CDP_URL"] = _old_cdp
        #: خانهٔ «پنل وصل است» باید از ضربانِ معتبرِ خودِ پنل بیاید، نه از
        #: نشانهٔ درخواستِ گزارش‌گیرنده؛ وگرنه خواندنِ بیرونی همیشه UNKNOWN است.
        ACC._PANEL_SEEN["at"] = time.time()
        facts = ACC.build_facts(None, host={"healthy": True},
                                tabs={"tabs": [{"is_panel": True}]},
                                session={"state": "LOGGED_IN"}, ui={},
                                preflight={}, ticket_ok=False)
        ok("panel_connected از ضربانِ تازهٔ پنل PASS می‌شود",
           (facts.get("panel_connected") or {}).get("status") == "PASS",
           json.dumps(facts.get("panel_connected"), ensure_ascii=False))
        ACC._PANEL_SEEN["at"] = 0.0
        facts = ACC.build_facts(None, host={"healthy": True},
                                tabs={"tabs": [{"is_panel": True}]},
                                session={"state": "LOGGED_IN"}, ui={},
                                preflight={}, ticket_ok=False)
        ok("بدونِ ضربانِ تازه panel_connected دیگر PASS نیست",
           (facts.get("panel_connected") or {}).get("status") != "PASS",
           json.dumps(facts.get("panel_connected"), ensure_ascii=False))
    except Exception as e:                        # noqa: BLE001
        ok("loaderِ تنظیمات با دیتابیسِ تازه کار می‌کند", False,
           "%s: %s" % (type(e).__name__, str(e)[:160]))

    # ── واحد: dry-run فقط چک‌هایِ مالی/بازار را advisory می‌کند ─────────────
    import execution_trading_rules as TR
    rep = TR.run_preflight(symbol="X", side="buy", price=1000, quantity=1,
                           total_actions=1, interval_ms=None,
                           target_at_ms=int(time.time() * 1000), facts={}).public()
    ok("dry-run با ارزشِ زیرِ حد مجاز مسدود نمی‌شود",
       rep["ok_for_arm"] is False and rep["ok_for_dry_run"] is True,
       json.dumps({c["id"]: c["status"] for c in rep["checks"]}, ensure_ascii=False))
    rep2 = TR.run_preflight(symbol="X", side="buy", price=1005, quantity=1,
                            total_actions=25, interval_ms=100,
                            target_at_ms=int(time.time() * 1000), facts={}).public()
    ok("سقفِ اقدام و کفِ فاصله در dry-run هم مانع‌اند",
       rep2["ok_for_dry_run"] is False,
       json.dumps({c["id"]: c["status"] for c in rep2["checks"]}, ensure_ascii=False))

    # ── واحد: ثبتِ rate limiter در لحظهٔ شلیک، نه پایان ────────────────────
    import execution_rate_limiter as RL
    now = [1000.0]
    lim = RL.OrderRateLimiter(clock=lambda: now[0])
    lim.record("acct", at_mono_s=1000.0)
    now[0] = 1000.10
    dec2 = lim.try_acquire("acct", consume=False)
    ok("۱۰۰ms بعد از شلیک، کف هنوز بسته است", not dec2.ok, dec2.public().__repr__())
    now[0] = 1000.31
    dec = lim.try_acquire("acct", consume=False)
    ok("۳۱۰ms بعد از شلیک، کفِ ۳۰۰ms آزاد است", dec.ok, dec.public().__repr__())

    #: کفِ ۳۰۰ms فاصلۀ «بینِ دو اقدام» است، نه یک اقدامِ تنها (سنجش ۲۰۲۶-۱۰-۲۴:
    #: اجرایِ تک‌اقدامیِ زنده با interval=0 به‌غلط BLOCKED شد).
    lim2 = RL.OrderRateLimiter(clock=lambda: 5000.0)
    plan1 = lim2.check_plan(actions=1, interval_ms=0).public()
    ok("یک اقدامِ تنها با فاصلهٔ صفر مجاز است", bool(plan1.get("fits")),
       json.dumps(plan1, ensure_ascii=False)[:400])
    plan2 = lim2.check_plan(actions=2, interval_ms=100).public()
    ok("دو اقدام با فاصلهٔ ۱۰۰ms زیرِ کفِ ۳۰۰ms مسدود است",
       not bool(plan2.get("fits")), json.dumps(plan2, ensure_ascii=False)[:400])

    # ── واحد: خروجیِ فارسیِ live_verify رویِ کنسولِ cp1252 نمی‌شکند ────────
    env = dict(os.environ)
    env.pop("PYTHONIOENCODING", None)
    env["PYTHONIOENCODING"] = ""
    try:
        got = subprocess.run([sys.executable, os.path.join(ROOT, "dev",
                                                           "autoclicker_live_verify.py")],
                             capture_output=True, timeout=60, env=env)
        ok("live_verify با کنسولِ پیش‌فرض ویندوز کرش نمی‌کند",
           got.returncode == 0,
           (got.stderr or b"").decode("utf-8", "replace")[-200:])
        ok("live_verify خروجیِ JSONِ خوانا می‌دهد",
           got.stdout.strip().startswith(b"{"), got.stdout[:80].decode("utf-8", "replace"))
    except Exception as e:                        # noqa: BLE001
        ok("live_verify با کنسولِ پیش‌فرض ویندوز کرش نمی‌کند", False,
           "%s: %s" % (type(e).__name__, str(e)[:120]))

    print("\n%d pass / %d fail" % (PASS, FAIL))
    print("%d/%d passed" % (PASS, PASS + FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(main())
