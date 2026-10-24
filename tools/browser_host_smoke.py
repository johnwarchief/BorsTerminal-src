# -*- coding: utf-8 -*-
"""Local browser-host + CDP reuse smoke. No broker, no order, no secrets."""
import dataclasses
import http.server
import json
import os
import shutil
import tempfile
import sys
import threading
import time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from urllib.parse import urlparse
TMP = tempfile.mkdtemp(prefix="bors_host_smoke_")
os.environ["BORS_BROWSER_HOST_STATUS"] = os.path.join(TMP, "host.json")
os.environ["BORS_BROWSER_HOST_PROFILE"] = os.path.join(TMP, "profile")
os.environ["BORS_EXECUTION_CDP_URL"] = ""
os.chdir(ROOT)

import execution_browser_host as H  # noqa: E402
import execution_browser as EB  # noqa: E402
import execution_strategy_core as SC  # noqa: E402

PAGE = b"""<!doctype html><html><head><meta charset="utf-8"></head><body>
<input id="symbol" aria-label="symbol"><input id="price" aria-label="price">
<input id="quantity" aria-label="quantity">
<button aria-label="submit" onclick="sessionStorage.setItem('kept','yes')">send</button>
</body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(PAGE)))
        self.end_headers()
        self.wfile.write(PAGE)

    def log_message(self, *a):
        pass


def main():
    out = {"broker_touched": False, "order_submitted": False}
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    url = "http://127.0.0.1:%d/" % port
    got = H.start_host(url=url, wait_s=25, hold=False)
    out["host"] = {k: got.get(k) for k in ("status", "pid", "port", "cdp_url", "profile")}
    if got.get("status") != "ready":
        print(json.dumps(out, ensure_ascii=False, indent=1))
        srv.shutdown()
        return 2
    settings = SC.default_settings(SC.PLAYWRIGHT_DOM)
    opts = dict(settings.options)
    opts.update({"order_url": url, "origin_allowlist": [urlparse(url).scheme + "://" + urlparse(url).netloc],
                 "cdp_url": got["cdp_url"], "symbol_selector": "#symbol",
                 "price_selector": "#price", "quantity_selector": "#quantity",
                 "submit_selector": "button[aria-label=submit]",
                 "intercept_pattern": "**/none*", "action_timeout_ms": 2000,
                 "headless": True})
    settings = dataclasses.replace(settings, options=opts)
    d1 = EB.PlaywrightBrowserDriver(settings, strategy_id=SC.PLAYWRIGHT_DOM)
    try:
        d1.start()
        d1.goto(url)
        d1.evaluate("() => { sessionStorage.setItem('kept','yes'); return location.href; }")
        probe = d1.probe({"symbol_selector": "#symbol"})
        out["cdp_ok"] = True
        out["probe_inputs"] = len(probe.get("inputs") or [])
        out["probe_visible"] = any(i.get("visible") for i in (probe.get("inputs") or []))
    finally:
        d1.close()
    time.sleep(1.0)
    d2 = EB.PlaywrightBrowserDriver(settings, strategy_id=SC.PLAYWRIGHT_DOM)
    try:
        d2.start()
        out["sessionstorage_after_reconnect"] = d2.evaluate(
            "() => sessionStorage.getItem('kept')")
        out["page_url_after_reconnect"] = d2.url()
    finally:
        d2.close()
    out["host_still_healthy"] = H.read_status(check=True).get("healthy")
    stopped = H.stop_host()
    out["stop"] = {"status": stopped.get("status")}
    time.sleep(1.0)
    out["host_after_stop"] = H.read_status(check=True).get("healthy")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    srv.shutdown()
    shutil.rmtree(TMP, ignore_errors=True)
    return 0 if (out.get("cdp_ok") and out.get("probe_visible")
                 and out.get("sessionstorage_after_reconnect") == "yes"
                 and out.get("host_after_stop") is False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
