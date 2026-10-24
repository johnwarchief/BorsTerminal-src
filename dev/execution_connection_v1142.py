#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""گارد Round 8 — تشخیص مرحله‌ای اتصال، بدون شبکه/سفارش/راز."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import execution_connection as C  # noqa: E402
import execution_connect as EXC  # noqa: E402
import execution_session_capture as ESC  # noqa: E402

PASS = 0
FAIL = 0
FAILED: list[str] = []


def ck(ok: bool, label: str, extra=None) -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  ok   %s" % label)
    else:
        FAIL += 1
        FAILED.append(label)
        print("  FAIL %s -> %r" % (label, extra))


def ex(**patch):
    base = {
        "status": "success", "adapter": "easytrader", "traffic_allowed": True,
        "live_enabled": True, "wire_hypothesis": True,
        "session": {"state": "connected", "proven": True,
                    "verified_by": {"path": "/easy/api/account/server-time",
                                    "status": 200, "kind": "observed-read-only"}},
        "capabilities": {"place": False, "list_orders": True, "order_state": True,
                         "balances": False, "cancel": False},
        "wire_provenance": {"order_create": {"kind": "third-party-code-only"}},
    }
    base.update(patch)
    return base


def host(**patch):
    base = {"healthy": True, "status": "ready", "port": 9333,
            "cdp_url": "http://127.0.0.1:9333"}
    base.update(patch)
    return base


def pages(title="EasyTrader", url="https://d.easytrader.ir/"):
    return ([{"title": title, "url": url, "host": "d.easytrader.ir"}], "")


def diag(*, h=None, e=None, p=None, pg=pages):
    return C.diagnose(app_version="1.0.95", host=h or host(), execution=e or ex(),
                      portfolio=p or {"status": "no_source", "rows": None},
                      pages_fn=pg)


def main() -> int:
    print("── ۱) ده مرحله و پیام‌های صادقانه ──")
    d = diag()
    ck(len(d["steps"]) == 10 and d["step_count"] == 10, "ده مرحله ساخته می‌شود")
    ck(d["state"] == C.STATE_READ_ONLY_VERIFIED
       and d["state"] != C.STATE_CONNECTED
       and "خواندن" in d["state_label"],
       "نشست read-only تأییدشده، CONNECTED نوشتن نمی‌شود", d["state_label"])
    ready = diag(e=ex(live_enabled=False,
                      session={"state": "unknown", "proven": False}))
    ck(ready["steps"][5]["status"] == C.UNVERIFIED
       and ready["state"] == C.STATE_API_UNVERIFIED,
       "توکن در حافظه و بی‌تأیید ⇒ UNVERIFIED، نه BLOCKED", ready["steps"][5])
    expired = diag(e=ex(session={"state": "expired", "proven": False}))
    ck(expired["steps"][5]["status"] == C.BLOCKED
       and "منقضی" in expired["steps"][5]["reason"],
       "نشست منقضی ⇒ BLOCKED با علتِ انقضا", expired["steps"][5])
    traffic_off = diag(e=ex(traffic_allowed=False,
                            session={"state": "unknown", "proven": False}))
    ck(traffic_off["steps"][5]["status"] == C.BLOCKED
       and "ارتباط" in traffic_off["steps"][5]["reason"],
       "ترافیک خاموش ⇒ BLOCKED با علتِ ترافیک", traffic_off["steps"][5])
    connected = diag(e=ex(wire_hypothesis=False))
    ck(connected["state"] == C.STATE_CONNECTED
       and connected["state_label"] == C.STATE_LABEL[C.STATE_CONNECTED],
       "قراردادِ تأییدشده + نشست + read-only ⇒ CONNECTED", connected["state"])
    ck(any(s["key"] == "login" and s["status"] == C.UNVERIFIED for s in d["steps"]),
       "بازبودن صفحهٔ UI = ورود تأییدشده نیست")
    ck(any(s["key"] == "contract" and s["status"] == C.UNVERIFIED for s in d["steps"]),
       "WIRE_HYPOTHESIS همچنان UNVERIFIED است")
    ck(any(s["key"] == "session" and s["status"] == C.PASS for s in d["steps"]),
       "پرسشِ read-only با شاهد، session را PASS می‌کند")
    ck(d["secrets_stored"] is False, "تشخیص ادعای ذخیرهٔ راز نمی‌کند")
    ck(all("token" not in json.dumps(s, ensure_ascii=False).lower() for s in d["steps"]),
       "مراحل هیچ token/cookie برنمی‌گردانند")

    print("\n── ۲) خطاهای واقعی و اقدام بعدی ──")
    hd = diag(h=host(healthy=False, status="closed", port=0, cdp_url=""))
    ck(hd["state"] == C.STATE_HOST_DOWN
       and hd["steps"][1]["status"] == C.FAIL and "پنجره" in hd["next_action"],
       "host خاموش ⇒ HOST_DOWN با اقدامِ بازکردن", hd.get("next_action"))
    no_page = diag(pg=lambda u: ([], ""))
    ck(no_page["state"] == C.STATE_PAGE_MISSING,
       "CDP هست ولی صفحه نیست ⇒ PAGE_MISSING", no_page["state"])
    cdp_bad = diag(pg=lambda u: ([], "connection refused"))
    ck(cdp_bad["state"] == C.STATE_CDP_DOWN,
       "خطای CDP ⇒ CDP_DOWN", cdp_bad["state"])
    login = diag(pg=lambda u: ([{"title": "ورود - کارگزاری مفید",
                                  "url": "https://login.emofid.com/",
                                  "host": "login.emofid.com"}], ""))
    ck(login["state"] == C.STATE_LOGIN_REQUIRED
       and login["steps"][4]["status"] == C.BLOCKED,
       "صفحهٔ ورود ⇒ LOGIN_REQUIRED، نه CONNECTED", login["state"])

    print("\n── ۳) API و سوءتفسیرها ──")
    mock = diag(e=ex(adapter="mock", session={"state": "connected", "proven": False},
                     wire_hypothesis=False))
    ck(mock["steps"][5]["status"] == C.BLOCKED
       and mock["state"] != C.STATE_CONNECTED,
       "آداپتور mock ⇒ نشست API مسدود، نه سبز", mock["steps"][5])
    ck(mock["steps"][6]["status"] == C.UNVERIFIED,
       "آداپتور mock ⇒ قرارداد ارسال UNVERIFIED، نه PASS", mock["steps"][6])
    no_token = diag(e=ex(live_enabled=False,
                         session={"state": "disconnected", "proven": False}))
    ck(no_token["steps"][5]["status"] in (C.BLOCKED, C.UNVERIFIED),
       "نبودِ نشست API ⇒ CONNECTED نمی‌شود")
    account = diag(p={"status": "no_source", "rows": None})
    ck(account["steps"][8]["status"] == C.BLOCKED,
       "نبودِ منبع حساب ⇒ BLOCKED", account["steps"][8])
    ok_account = diag(p={"status": "success", "rows": []})
    ck(ok_account["steps"][8]["status"] == C.PASS, "منبع حسابِ پاسخ‌دار PASS است")

    print("\n── ۳.۵) ترافیک روشن، نشست غایب ──")
    class NoToken:
        live = False
        class transport:
            is_live = True
        def has_token(self):
            return False
    class NoTraffic:
        live = False
        class transport:
            is_live = False
        def has_token(self):
            return False
    v1 = EXC.verify(NoToken())
    ck(v1["state"] == EXC.STATE_DISCONNECTED and "دسترسی" in v1["reason"],
       "ترافیک روشن + token غایب ⇒ DISCONNECTED، نه «ترافیک خاموش»", v1)
    v2 = EXC.verify(NoTraffic())
    ck(v2["state"] == EXC.STATE_UNKNOWN and "ارتباط" in v2["blocked_reason"],
       "ترافیک خاموش ⇒ UNKNOWN با علتِ ترافیک", v2)

    print("\n── ۴) CDP واقعی روی loopback ──")
    class H(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = json.dumps([{"type": "page", "title": "EasyTrader",
                                "url": "https://d.easytrader.ir/"}]).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *_a):
            pass
    srv = HTTPServer(("127.0.0.1", 0), H)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        pp, err = C.cdp_pages("http://127.0.0.1:%d" % srv.server_port)
        ck(not err and len(pp) == 1 and pp[0]["host"] == "d.easytrader.ir",
           "cdp_pages فقط url/title/host می‌خواند", (pp, err))
        d2 = diag(h=host(cdp_url="http://127.0.0.1:%d" % srv.server_port),
                  pg=C.cdp_pages)
        ck(d2["steps"][2]["status"] == C.PASS, "CDP loopback در diagnose PASS است")
    finally:
        srv.shutdown()

    print("\n── ۵) گزارش و قرارداد HTTP ──")
    rep = C.report(diagnosis={**d, "secret_token": "Bearer abcdefghijklmnop",
                              "cookie": "secret-value"})
    ck("Bearer abcdefghijklmnop" not in str(rep)
       and "secret-value" not in str(rep) and rep["secrets_stored"] is False,
       "گزارش تشخیصی راز را ماسک می‌کند")

    print("\n── ۵.۵) خواندنِ نشستِ OIDC (بدونِ چاپِ راز) ──")
    secret = "SECRET-TOKEN-XYZ"
    future = int(time.time()) + 3600
    raw_ok = json.dumps({"access_token": secret, "token_type": "Bearer",
                         "scope": "easy2_api mts_api openid", "expires_at": future})
    tok, meta = ESC.parse_oidc_user(raw_ok)
    ck(tok == secret and meta["expires_at"] == future and meta["has_access_token"],
       "نشستِ معتبر خوانده می‌شود", meta)
    for label, raw in (
        ("بدونِ access_token", json.dumps({"token_type": "Bearer",
                                           "scope": "easy2_api", "expires_at": future})),
        ("JSONِ خراب", "not-json"),
        ("منقضی", json.dumps({"access_token": secret, "token_type": "Bearer",
                              "scope": "easy2_api", "expires_at": 1})),
        ("بدونِ اسکوپِ API", json.dumps({"access_token": secret, "token_type": "Bearer",
                                        "scope": "openid", "expires_at": future})),
    ):
        try:
            ESC.parse_oidc_user(raw)
            ck(False, "نشستِ نامعتبر باید رد شود: " + label)
        except ESC.CaptureError as e:
            ck(secret not in str(e), "خطایِ %s راز را در متن نمی‌گذارد" % label, e.code)

    import api.execution as EX
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    tmp = tempfile.mkdtemp(prefix="conn_api_")
    old = {k: os.environ.get(k) for k in
           ("BORS_EXECUTION_DB", "BORS_BROWSER_HOST_STATUS", "BORS_OFFERINGS_DB",
            "BORS_SCHEDULE_DB", "BORS_COCKPIT_DB")}
    os.environ["BORS_EXECUTION_DB"] = os.path.join(tmp, "audit.db")
    os.environ["BORS_BROWSER_HOST_STATUS"] = os.path.join(tmp, "host.json")
    os.environ["BORS_OFFERINGS_DB"] = os.path.join(tmp, "offerings.db")
    os.environ["BORS_SCHEDULE_DB"] = os.path.join(tmp, "schedules.db")
    os.environ["BORS_COCKPIT_DB"] = os.path.join(tmp, "cockpit.db")
    app = FastAPI()
    app.include_router(EX.router)
    c = TestClient(app, raise_server_exceptions=False)
    try:
        r = c.get("/api/execution/connection/diagnose").json()
        ck(r.get("status") == "success" and r.get("state") in
           (C.STATE_HOST_DOWN, C.STATE_API_UNVERIFIED),
           "API diagnose", r.get("code"))
        ck(len(r.get("steps") or []) == 10, "API ده مرحله را برمی‌گرداند")
        rp = c.get("/api/execution/connection/report").json()
        ck(rp.get("status") == "success" and rp.get("secrets_stored") is False,
           "API report بدونِ راز", rp.get("code"))

        print("\n── ۶) capture-session: تحویلِ فقط-حافظه ──")
        class FakeAdapter:
            def __init__(self):
                self.tokens = []
            def set_token(self, value):
                self.tokens.append(value)
        fake = FakeAdapter()
        old_adapter, old_kind = EX._ACTIVE_ADAPTER, EX.ADAPTER_KIND
        old_host, old_capture = EX.BH.read_status, ESC.capture_from_host
        old_traffic = EX.TRAFFIC_ALLOWED
        try:
            EX._ACTIVE_ADAPTER = fake
            EX.ADAPTER_KIND = "easytrader"
            EX.TRAFFIC_ALLOWED = True
            EX.BH.read_status = lambda check=True: {
                "healthy": True, "cdp_url": "http://127.0.0.1:9333"}
            ESC.capture_from_host = lambda url, timeout_s=20.0: (
                "DUMMY-SECRET-TOKEN",
                {"page_host": "d.easytrader.ir", "token_type": "Bearer",
                 "expires_at": future, "scope": "easy2_api mts_api",
                 "has_refresh_token": False})
            cap = c.post("/api/execution/connection/capture-session")
            body = cap.json()
            ck(body.get("status") == "success" and body.get("token_present") is True
               and body.get("secrets_returned") is False
               and body.get("secrets_stored") is False,
               "capture موفق فقط متادیتا برمی‌گرداند", body)
            ck("DUMMY-SECRET-TOKEN" not in cap.text,
               "پاسخِ capture هیچ توکنی ندارد")
            ck(fake.tokens == ["DUMMY-SECRET-TOKEN"],
               "توکن فقط به set_tokenِ حافظه داده شد", len(fake.tokens))
            bad = c.post("/api/execution/connection/capture-session",
                         headers={"Origin": "http://evil.example"})
            ck(bad.json().get("code") == "CROSS_ORIGIN_BLOCKED"
               and len(fake.tokens) == 1,
               "originِ بیگانه capture را اجرا نمی‌کند", bad.json())
            EX.ADAPTER_KIND = "mock"
            mockcap = c.post("/api/execution/connection/capture-session")
            ck(mockcap.json().get("code") == "ADAPTER_NOT_EASYTRADER"
               and len(fake.tokens) == 1,
               "آداپتور mock اجازهٔ خواندنِ نشست را نمی‌دهد", mockcap.json())
            EX.ADAPTER_KIND = "easytrader"
            EX.TRAFFIC_ALLOWED = False
            offcap = c.post("/api/execution/connection/capture-session")
            ck(offcap.json().get("code") == "TRAFFIC_OFF"
               and len(fake.tokens) == 1,
               "ترافیکِ خاموش ⇒ capture نشست را در حافظه نمی‌گذارد", offcap.json())
        finally:
            EX._ACTIVE_ADAPTER, EX.ADAPTER_KIND = old_adapter, old_kind
            EX.BH.read_status, ESC.capture_from_host = old_host, old_capture
            EX.TRAFFIC_ALLOWED = old_traffic
    finally:
        c.close()
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    print("\n%d passed / %d failed" % (PASS, FAIL))
    if FAILED:
        print("FAILED: " + ", ".join(FAILED))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
