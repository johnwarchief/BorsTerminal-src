#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sarkhati_waf_header_v1121 — WAF/Content-Type، مسیر زمان سرور و بازیابیِ نشست.

سنجشِ 2026-10-20 رویِ نشستِ واقعیِ EasyTrader:
  * هر GET با `Content-Type: application/json` ⇒ 200 + HTMLِ WAF (بدونِ JSON).
  * همان GET بدونِ آن هدر ⇒ JSONِ درست.
این گارد بدونِ هیچ شبکهٔ واقعی ثابت می‌کند:
  ۱) GET بدونِ Content-Type و POST با Content-Type می‌رود.
  ۲) شبیه‌سازِ WAF سبز می‌شود فقط اگر GET هدر را نبرد.
  ۳) مسیرِ مردهٔ server-time از کاندیدها حذف شده و شکلِ timestamp‌دار کار می‌کند.
  ۴) دروازهٔ فقط‌خواندنی هیچ POSTِ سفارشی به ترابری نمی‌فرستد.
  ۵) مخزنِ نشست: OK/EXPIRED/NO_EXP/MISSING/MALFORMED و عدمِ نشتِ توکن.
"""
from __future__ import annotations

import base64
import json
import os
import socket
import sys
import time

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
        print("FAIL " + label + "  -> " + str(detail)[:190])


class _SocketTripwire:
    """هر سوکتِ واقعی درِ دورِ این بلوک = شکستِ سنجه، نه هشدار."""

    def __init__(self):
        self.hits = []
        self._old = socket.socket

    def __enter__(self):
        outer = self

        class Guarded(outer._old):
            def connect(self, addr, *a, **k):
                outer.hits.append(("connect", addr))
                raise OSError("network is disabled in this guard")

        socket.socket = Guarded
        return self

    def __exit__(self, *exc):
        socket.socket = self._old
        return False


class Recorder:
    """ترابریِ بدلِ ثبت‌کننده؛ هیچ سوکتی باز نمی‌کند."""
    name = "v1121-recording"
    is_live = True

    def __init__(self, responder):
        self.calls = []
        self.responder = responder

    def request(self, *, method, url, headers, payload=None, timeout_s=7.0):
        h = dict(headers)
        self.calls.append({"method": method, "url": url, "headers": h,
                           "payload": payload})
        return self.responder(method, url, h, payload)


class WafResponder:
    """اگر Content-Type ببیند، همان پاسخِ 200 + HTMLِ WAF را می‌دهد."""

    def __init__(self):
        self.waf_hits = 0

    def __call__(self, method, url, headers, payload):
        import execution_easytrader as ET
        if "Content-Type" in headers:
            self.waf_hits += 1
            return ET.WireResponse(200, {"content-type": "text/html; charset=utf-8"},
                                   "<html><head><title>WAF</title></head></html>")
        path = url.replace(ET.WIRE_BASE_URL, "")
        if method == "GET" and path == ET.WIRE_PATH_ORDER_LIST:
            return ET.WireResponse(200, {"content-type": "application/json"},
                                   '{"orders":[]}')
        if method == "GET" and path in ET.WIRE_SESSION_PROBE_CANDIDATES:
            return ET.WireResponse(200, {"content-type": "application/json"},
                                   '{"ok":true}')
        if method == "GET" and path.startswith("/easy/api/account/server-time/"):
            ms = path.rsplit("/", 1)[-1]
            return ET.WireResponse(200, {}, '{"diff":0,"serverTimestamp":%s}' % ms)
        return ET.WireResponse(404, {}, "")


def _jwt(claims):
    def b64(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")
    return b64({"alg": "none", "typ": "JWT"}) + "." + b64(claims) + ".sig"


class FakeAdapter:
    def __init__(self):
        self.tokens = []

    def set_token(self, value):
        self.tokens.append(value)

    def has_token(self):
        return bool(self.tokens)


def _draft(EC):
    instr = EC.InstrumentRef(symbol="TEST", ins_code="1", isin="IRO1TEST0001",
                             broker_instrument="IRO1TEST0001",
                             resolution=EC.Resolution.EXACT)
    return EC.OrderDraft(execution_id="V1121-NO-REAL-ORDER", instrument=instr,
                         side=EC.Side.BUY, price=1000.0, quantity=1.0,
                         mode=EC.OrderMode.SAFE)


def main() -> int:
    import execution_contract as EC
    import execution_easytrader as ET
    import execution_session_store as SESS

    print("\n── ۱) هدرِ GET و POST (ترابریِ بدل، صفر شبکه) ──")
    got = {"method": "GET", "body": '{"orders":[]}'}

    def responder(method, url, headers, payload):
        return ET.WireResponse(200, {"content-type": "application/json"},
                               got["body"])

    rec = Recorder(responder)
    ad = ET.EasyTraderAdapter(transport=rec, token="TEST-TOKEN-NOT-REAL",
                              writes_allowed=True)
    with _SocketTripwire() as trip1:
        ad._call("GET", "/boot/api/build-number", tag="header-get", timeout_s=1)
        get_call = rec.calls[-1]
        ad._call("POST", ET.WIRE_PATH_ORDER_CREATE, payload={"order": {}},
                 tag="header-post", timeout_s=1)
        post_call = rec.calls[-1]
        ck("Content-Type" not in get_call["headers"],
           "الف) GET بدونِ Content-Type می‌رود", get_call["headers"])
        ck(get_call["headers"].get("Authorization", "").startswith("Bearer "),
           "پ) GET هنوز Authorization دارد", list(get_call["headers"]))
        ck(post_call["headers"].get("Content-Type") == "application/json",
           "ت) POST بدنه‌دار Content-Type را نگه می‌دارد", post_call["headers"])
        ck(post_call["payload"] == {"order": {}},
           "ث) بدنهٔ POST دست‌نخورده به ترابریِ بدل رسید", post_call["payload"])
        ck(not trip1.hits, "ج) هیچ سوکتِ واقعی باز نشد", trip1.hits)

    print("\n── ۲) شبیه‌سازِ WAF: سبز فقط اگر هدر نرود ──")
    waf = WafResponder()
    rec2 = Recorder(waf)
    ad2 = ET.EasyTraderAdapter(transport=rec2, token="TEST-TOKEN-NOT-REAL",
                               writes_allowed=False)
    try:
        probe = ad2.session_probe()
        auth_state = ad2.authenticate()
        auth_ok = auth_state.state is EC.SessionState.CONNECTED
        auth_error = ""
    except Exception as e:                       # noqa: BLE001 - گزارشِ شکست
        probe = {}
        auth_ok = False
        auth_error = "%s: %s" % (type(e).__name__, str(e)[:120])
    ck(probe.get("proven") is True, "الف) session_probe با JSONِ بدونِ WAF سبز شد",
       probe)
    ck(auth_ok and ad2.session_proven(),
       "پ) authenticate متصلِ تأییدشده شد", auth_error)
    ck(waf.waf_hits == 0, "ت) صفر پاسخِ WAF؛ هیچ GETی Content-Type نداشت",
       waf.waf_hits)
    ck(all(c["method"] == "GET" for c in rec2.calls),
       "ث) همهٔ درخواست‌های سنجشِ نشست GET بودند",
       [c["method"] for c in rec2.calls])

    print("\n── ۳) مسیرِ زمانِ سرور ──")
    ck("/easy/api/account/server-time" not in ET.WIRE_SESSION_PROBE_CANDIDATES,
       "الف) مسیرِ مردهٔ بدونِ timestamp در کاندیدها نیست",
       ET.WIRE_SESSION_PROBE_CANDIDATES)
    rec3 = Recorder(WafResponder())
    ad3 = ET.EasyTraderAdapter(transport=rec3, token="TEST-TOKEN-NOT-REAL",
                               writes_allowed=False)
    clock = ad3.server_clock()
    clock_urls = [c["url"] for c in rec3.calls if "server-time" in c["url"]]
    ck(bool(clock_urls) and clock_urls[-1].rsplit("/", 1)[-1].isdigit(),
       "پ) server_clock شکلِ timestamp‌دار را صدا زد", clock_urls[-1:])
    ck(bool(clock) and clock.get("verified") is True,
       "ت) ساعتِ کارگزاری از پاسخِ همان مسیر تأیید شد", clock)

    print("\n── ۴) دروازهٔ فقط‌خواندنی: هیچ POSTِ سفارشی ──")
    rec4 = Recorder(lambda *a: ET.WireResponse(500, {}, ""))
    ad4 = ET.EasyTraderAdapter(transport=rec4, token="TEST-TOKEN-NOT-REAL",
                               writes_allowed=False)
    with _SocketTripwire() as trip4:
        try:
            ad4.submit_order(_draft(EC))
            refused = False
            code = None
        except EC.BrokerError as e:
            refused = True
            code = e.code
        ck(refused and code is EC.ErrorCode.UNSUPPORTED,
           "الف) submit_order درِ فقط‌خواندنی با UNSUPPORTED رد شد", code)
        ck(rec4.calls == [], "پ) صفر فراخوانیِ ترابری؛ هیچ POSTی ساخته نشد",
           rec4.calls)
        ck(not trip4.hits, "ت) هیچ سوکتِ واقعی باز نشد", trip4.hits)
        ck("submit:REFUSED-read-only" in ad4.wire_calls and
           not any(str(w).startswith("submit:POST") for w in ad4.wire_calls),
           "ث) ردِّ فقط‌خواندنی درِ ردِّپای ثبت شد، نه POST", ad4.wire_calls)

    print("\n── ۵) مخزنِ نشست: exp، کدها و عدمِ نشت ──")
    now = int(time.time())
    future = _jwt({"exp": now + 3600})
    expired = _jwt({"exp": now - 10})
    no_exp = _jwt({"sub": "x"})
    fake_future = lambda target: (SESS.SESSION_PREFIX + future.encode(), 0)
    r = SESS.read_session_token(now=now, reader=fake_future)
    ck(r.ok and r.code == "OK" and r.exp == now + 3600 and r.token == future,
       "الف) توکنِ معتبر خوانده شد و exp درست است", r)
    r_exp = SESS.read_session_token(
        now=now, reader=lambda t: (SESS.SESSION_PREFIX + expired.encode(), 0))
    ck(not r_exp.ok and r_exp.code == "EXPIRED" and r_exp.token == "",
       "پ) توکنِ منقضی برنمی‌گردد", r_exp)
    r_no = SESS.read_session_token(
        now=now, reader=lambda t: (SESS.SESSION_PREFIX + no_exp.encode(), 0))
    ck(not r_no.ok and r_no.code == "NO_EXP" and r_no.token == "",
       "ت) توکنِ بی‌exp برنمی‌گردد", r_no)
    r_miss = SESS.read_session_token(now=now, reader=lambda t: (None, 1168))
    ck(not r_miss.ok and r_miss.code == "MISSING", "ث) نبود ⇒ MISSING", r_miss)
    r_bad = SESS.read_session_token(
        now=now, reader=lambda t: (b"not-v1", 0))
    ck(not r_bad.ok and r_bad.code == "MALFORMED", "ج) پیشوندِ بد ⇒ MALFORMED", r_bad)
    r_utf = SESS.read_session_token(
        now=now, reader=lambda t: (SESS.SESSION_PREFIX + b"\xff", 0))
    ck(not r_utf.ok and r_utf.code == "MALFORMED",
       "چ) UTF-8ِ خراب ⇒ MALFORMED", r_utf)

    fake = FakeAdapter()
    res = SESS.restore_session(fake, now=now, reader=fake_future)
    ck(res.get("loaded") is True and res.get("code") == "OK" and
       fake.tokens == [future], "ح) restore_session توکن را ست کرد", res)
    dumped = json.dumps(res, ensure_ascii=False)
    ck("token" not in res and future not in dumped and future not in repr(r),
       "خ) خروجی/`repr` هیچ توکنی ندارد", list(res))
    fake2 = FakeAdapter()
    res2 = SESS.restore_session(
        fake2, now=now,
        reader=lambda t: (SESS.SESSION_PREFIX + expired.encode(), 0))
    ck(res2.get("loaded") is False and res2.get("code") == "EXPIRED" and
       fake2.tokens == [], "د) منقضی هرگز ست نمی‌شود", res2)
    fake3 = FakeAdapter()
    fake3.set_token("SENTINEL-NEWER")
    res3 = SESS.restore_session(fake3, now=now, reader=fake_future)
    ck(res3.get("code") == "ALREADY_PRESENT" and fake3.tokens == ["SENTINEL-NEWER"],
       "ذ) نشستِ تازه‌تر با کهنه جایگزین نمی‌شود", res3)
    pub = SESS.public_status(r_exp)
    ck(pub.get("present") is True and pub.get("code") == "EXPIRED" and
       "token" not in pub, "ر) وضعیتِ عمومی فقط metadata دارد", pub)

    print("\n%d checks, %d failed, %d skipped" % (PASS + FAIL, FAIL, SKIP))
    print("SARKHATI WAF HEADER " + ("OK" if FAIL == 0 else "FAILED"))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
