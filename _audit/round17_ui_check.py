# -*- coding: utf-8 -*-
"""round17_ui_check — اثباتِ مرورگریِ گردشِ ورود/بررسی Mofid با APIِ بدل.

Vite باید روی 5211 بالا باشد. هیچ درخواستی به بک‌اند/کارگزاری نمی‌رود؛ همهٔ
`/api/**` با page.route پاسخ می‌گیرند. این آزمون «ورود واقعی» نیست.
"""
import json
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

BASE = os.environ.get("ROUND17_UI_BASE", "http://127.0.0.1:5211")
OUT = os.path.dirname(os.path.abspath(__file__))

STRATEGIES = {
    "status": "success", "live_allowed": False, "dry_run": True, "adapter": "mofid",
    "strategies": [
        {"id": "autoclicker", "label": "AutoClicker", "kind": "browser",
         "available": True, "configured": True, "unavailable_reason": "",
         "live_ready": False,
         "settings": {"strategy": "autoclicker", "enabled": True, "mode": "shadow",
                      "priority": 10, "updated_at": 1, "options": {
                          "form_symbol_selector": "x", "open_form_selector": "x",
                          "price_selector": "#price", "quantity_selector": "#quantity",
                          "submit_selector": "x", "action_timeout_ms": 1200,
                          "preclick_check": True, "intercept_pattern": "x",
                          "autofill": False, "require_prefilled": True}},
         "metrics": {}, "outcomes": {}, "last_result": None},
        {"id": "direct_api", "label": "Direct API", "kind": "http",
         "available": True, "configured": True, "unavailable_reason": "",
         "live_ready": False,
         "settings": {"strategy": "direct_api", "enabled": True, "mode": "live",
                      "priority": 0, "updated_at": 1, "options": {}},
         "metrics": {}, "outcomes": {}, "last_result": None},
    ],
    "selection": [], "rate_limiter": {}, "orders": [],
}
STATUS = {
    "status": "success", "adapter": "mofid", "dry_run": True, "experimental": True,
    "live_enabled": False, "live": True, "live_requested": False,
    "nothing_will_leave_the_machine": False,
    "session": {"proven": False, "state": "unknown"},
    "blocked_on": [], "confirm_gate": {"required": False},
    "capabilities": {"place": False, "balances": True},
}
HOST = {"status": "success", "host": {"healthy": False, "status": "closed"}}
SESSION = {
    "status": "success", "state": "NEEDS_LOGIN", "reason": "LOGIN_REQUIRED",
    "adapter_ready": True, "session_proven": False, "host_open": False,
    "host_status": "closed", "token_present": False,
    "login_url": "https://tg.mofidonline.com/", "read_only": True,
    "live_enabled": False, "live_ready": False,
}
LOGIN = {
    "status": "success", "code": "LOGIN_WINDOW_OPEN",
    "host": {"name": "mofid", "status": "ready", "healthy": True},
    "login_url": "https://tg.mofidonline.com/", "adapter_ready": True,
    "note": "manual",
}
VERIFY = {
    "status": "success", "code": "READ_ONLY_PROBE_OK", "state": "READ_ONLY_PROBE_OK",
    "detail": "", "session": {"state": "connected", "proven": True,
                              "page_host": "tg.mofidonline.com"},
    "account": {
        "buying_power": 500000000, "cash": 400000000, "unit": "IRR",
        "source": "mofid:/Order/customer/status",
        "positions": [{"isin": "IRO1TEST0001", "symbol": "TEST",
                       "current_asset": 1000, "sellable": 850, "open_sell": 50,
                       "sellable_state": "CLIENT_DERIVED_UNVERIFIED"}],
        "orders": [], "today_orders": [], "order_details": [],
    },
    "steps": {"session": "PASS", "money": "PASS", "positions": "PASS",
              "open_orders": "PASS", "today_orders": "PASS",
              "order_detail": "SKIPPED_NO_ORDERS"},
    "counts": {"positions": 1, "open_orders": 0, "today_orders": 0,
               "order_details": 0},
    "read_only": True, "live_enabled": False, "live_ready": False,
}


def main() -> int:
    checks = []

    def ck(cond, label, detail=""):
        checks.append(bool(cond))
        print(("ok   " if cond else "FAIL ") + label +
              ("" if cond else "  -> " + str(detail)[:200]))

    def handler(route):
        url = route.request.url
        method = route.request.method
        if url.endswith("/api/execution/strategies"):
            body = STRATEGIES
        elif url.endswith("/api/execution/status"):
            body = STATUS
        elif url.endswith("/api/execution/browser-host"):
            body = HOST
        elif url.endswith("/api/execution/mofid/session"):
            body = SESSION
        elif url.endswith("/api/execution/mofid/login-window") and method == "POST":
            body = LOGIN
        elif url.endswith("/api/execution/mofid/login-window") and method == "DELETE":
            body = {"status": "success", "host": {"status": "closed"}}
        elif url.endswith("/api/execution/mofid/verify-session"):
            body = VERIFY
        else:
            body = {"status": "success"}
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(body, ensure_ascii=False))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1366, "height": 768},
                                  locale="fa-IR")
        ctx.add_init_script(
            "try{sessionStorage.setItem('bors_auth_session','true')}catch(e){}")
        page = ctx.new_page()
        # فقط مسیرِ /api/؛ globِ **/api/** ماژول‌هایِ Vite در features/*/api را هم
        # می‌گرفت و صفحه را خراب می‌کرد.
        page.route(re.compile(r"^https?://[^/]+/api/.*"), handler)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE + "/", wait_until="domcontentloaded")
        page.wait_for_selector("body", timeout=10000)
        page.evaluate("location.hash = '#/autoclicker'")
        page.wait_for_selector("[data-testid='autoclicker-page']", timeout=15000)
        page.click("[data-testid='autoclicker-path-api']")
        page.wait_for_selector("[data-testid='autoclicker-mofid-account']",
                               timeout=10000)
        ck(page.get_by_test_id("autoclicker-mofid-state").inner_text().find("نیازمند") >= 0,
           "حالتِ اولیه NEEDS_LOGIN نمایش داده می‌شود")
        page.click("[data-testid='autoclicker-mofid-login']")
        page.wait_for_function(
            "() => document.querySelector('[data-testid=\"autoclicker-answer\"]')"
            "?.textContent?.includes('پنجره')")
        ck(True, "دکمهٔ ورود، پنجرهٔ اختصاصی را درخواست می‌کند")
        page.click("[data-testid='autoclicker-mofid-verify']")
        page.wait_for_function(
            "() => document.querySelector('[data-testid=\"autoclicker-mofid-state\"]')"
            "?.textContent?.includes('خواندن تأیید شد')", timeout=10000)
        bp = page.get_by_test_id("autoclicker-mofid-bp").inner_text()
        ck("IRR" in bp and "۵۰۰" in bp, "قدرت خریدِ probe با واحد نمایش داده می‌شود", bp)
        sell = page.get_by_test_id("autoclicker-mofid-sellable-state").inner_text()
        ck("CLIENT_DERIVED_UNVERIFIED" in sell,
           "sellable با برچسبِ تأییدنشده می‌ماند", sell)
        closed = page.get_by_test_id("autoclicker-mofid-live-closed").inner_text()
        ck("live_ready=false" in closed, "ارسال/live_ready بسته نمایش داده می‌شود", closed)
        ck(page.get_by_test_id("autoclicker-gate-account").inner_text().find("خوانده شد") >= 0,
           "chipِ آمادگیِ حساب سبز/خوانده‌شده است")
        page.screenshot(path=os.path.join(OUT, "round17_ui.png"), full_page=True)
        ck(not errors, "بدونِ خطایِ runtime در صفحه", errors[:3])
        ctx.close()
        browser.close()
    print("\n%d checks, %d failed" % (len(checks), checks.count(False)))
    print("ROUND17 UI " + ("OK" if all(checks) else "FAILED"))
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
