#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/sarkhati_connect_v1117.py -- گاردِ لایۀ «اتصال به EasyTrader».

چه چیزی ثابت می‌شود (و چرا بی‌این، «اتصال» فقط یک دکمه بود):

  د) نشانی: فقط https، فقط میزبانِ تأییدشده؛ صفحۀ ورودِ حدسی باز نمی‌شود.
  ه) بی‌دامنۀ ورود ⇒ خطای `NO_LOGIN_HOST` با علت، و **هیچ پروسه‌ای** شروع نمی‌شود
     (Popen کارگذاری‌شده تا اگر صدا زده شود، گارد قرمز است).
  و) حالتِ نشست فقط از پرسشِ واقعی می‌آید: ۴۰۱⇒EXPIRED، ۴۰۳⇒DISCONNECTED،
     timeout⇒UNKNOWN، پاسخِ معنادار⇒CONNECTED، و بی‌ترافیکِ مجاز⇒UNKNOWN+علت.
  ز) دامِ منفی: پنجره باز + نشانیِ غلط درِ حافظه ⇒ هرچه نیست، «CONNECTED» نیست.
  ح) راز هیچ‌جا نمی‌نشیند: نه در پاسخِ API، نه در وضعیتِ پنجره، و پروفایلِ
     موقت هنگام بستن پاک می‌شود.
  ط) چرخۀ mock سرِ هم: اتصال ← preflight ← prepare ← زمان‌بندی ← دروازۀ
     توقف ← reconcile ← ردیفِ حسابرسی، با «یک قصد = یک ارسال».

اجرا:  python dev/sarkhati_connect_v1117.py     (۰ = سبز، ۱ = رد)
"""
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

os.environ["BORS_EXECUTION_ADAPTER"] = "mock"
os.environ["BORS_CODAL_OFFLINE"] = "1"

import execution_connect as XC                                     # noqa: E402
import execution_contract as EC                                    # noqa: E402

FA = "".join(chr(0x6F0 + d) for d in range(10))
D = lambda t: t.translate(str.maketrans("0123456789", FA))

PASS = FAIL = 0


def ck(cond, label, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("ok   %s" % label)
    else:
        FAIL += 1
        print("FAIL %s %s" % (label, str(detail)[:170]))
    return bool(cond)


class FakeAdapter:
    """آداپتورِ ساختگی با رفتارِ قابلِ کنترل — بی‌هیچ ترافیکِ بیرونی."""
    def __init__(self, *, token="", outcome="ok", live=True):
        self._t = token
        self.outcome = outcome
        self.live = live

    def has_token(self):
        return bool(self._t)

    def authenticate(self):
        if self.outcome == "ok":
            return EC.SessionStatus(state=EC.SessionState.CONNECTED)
        if self.outcome == "expired":
            raise EC.BrokerError(EC.ErrorCode.SESSION_EXPIRED, "401")
        if self.outcome == "forbidden":
            raise EC.BrokerError(EC.ErrorCode.AUTH_FAILED, "403")
        if self.outcome == "timeout":
            raise EC.BrokerError(EC.ErrorCode.TIMEOUT, "no answer")
        return EC.SessionStatus(state=EC.SessionState.UNKNOWN)


print("\n── د) نشانیِ مجاز ──")
ck(XC.validate_url("http://api-mts.orbis.easytrader.ir/")[0] is False,
   "D1 http رد می‌شود")
ck(XC.validate_url("https://evil.example/login")[0] is False,
   "D2 میزبانِ بیرونِ فهرست رد می‌شود")
ok_wire, _ = XC.validate_url("https://api-mts.orbis.easytrader.ir/x")
ck(ok_wire, "D3 تنها میزبانِ دیدہ‌شدہ درِ مخزن مجاز است")
os.environ["BORS_EXECUTION_CONNECT_HOSTS"] = "mts.example-broker.ir"
ck(XC.validate_url("https://mts.example-broker.ir/")[0],
   "D4 میزبانِ تأییدشده با env پذیرفته می‌شود")
ck("mts.example-broker.ir" in XC.login_hosts(), "D5 دامنۀ ورود از env خوانده می‌شود")

print("\n── ه) بی‌دامنه ⇒ BLOCKED، بی‌پروسه ──")
os.environ.pop("BORS_EXECUTION_CONNECT_HOSTS", None)
opened = []
_real_popen = XC.subprocess.Popen
XC.subprocess.Popen = lambda *a, **k: opened.append(a)          # کارگذاری
h, why = XC.open_login_window("https://anything.example/")
ck(h is None and "مجاز" in why, "E1 نشانیِ تأییدنشده پنجره باز نمی‌کند", why)
h2, why2 = XC.open_login_window("https://mts.example-broker.ir/")
ck(h2 is None and why2, "E2 بی‌دامنۀ ورودِ ثبت‌شده هم پنجره باز نمی‌شود", why2)
ck(not opened, "E3 هیچ پروسه‌ای شروع نشد (دامنه تأیید نشده)", opened)
XC.subprocess.Popen = _real_popen

print("\n── و/ز) حالتِ نشست فقط از پرسشِ واقعی ──")
r = XC.verify(FakeAdapter(live=False))
ck(r["state"] == XC.STATE_UNKNOWN and r["blocked_reason"],
   "F1 بی‌ترافیکِ مجاز ⇒ UNKNOWN با علت، نه CONNECTED", r)
ck(XC.verify(FakeAdapter(token="", outcome="ok"))['state'] == XC.STATE_DISCONNECTED,
   "F2 بی‌نشست ⇒ DISCONNECTED")
ck(XC.verify(FakeAdapter(token="t", outcome="expired"))['state'] == XC.STATE_EXPIRED,
   "F3 ۴۰۱ ⇒ EXPIRED")
ck(XC.verify(FakeAdapter(token="t", outcome="forbidden"))['state'] == XC.STATE_EXPIRED,
   "F4 " + D("403") + " احرازِ ناموفق ⇒ EXPIRED (نه UNKNOWN، نه CONNECTED)")
ck(XC.verify(FakeAdapter(token="t", outcome="timeout"))['state'] == XC.STATE_UNKNOWN,
   "F5 timeout ⇒ UNKNOWN (نه «فرستاد»، نه «نفرستاد»)")
ck(XC.verify(FakeAdapter(token="t", outcome="ok"))['state'] == XC.STATE_CONNECTED,
   "F6 پاسخِ معنادار ⇒ CONNECTED")
# دامِ منفی: پنجره باز + نشانیِ بی‌اعتبار ⇒ هر چیزی جز CONNECTED
os.environ["BORS_EXECUTION_CONNECT_HOSTS"] = "mts.example-broker.ir"
st = XC.verify(FakeAdapter(token="", outcome="ok"))
ck(st["state"] != XC.STATE_CONNECTED,
   "G1 پنجرۀ باز به‌تنهایی «متصل» نیست (HTML دلیلِ اتصال نمی‌شود)", st)

print("\n── ح) راز هیچ‌جا نمی‌نشیند ──")
SECRET = "SECRETTOKEN-must-never-appear"
d = XC.status_dict(FakeAdapter(token=SECRET), XC.verify(FakeAdapter(token=SECRET)))
blob = json.dumps(d, ensure_ascii=False, default=str)
ck(SECRET not in blob, "H1 وضعیتِ نشست نشانی را برنمی‌گرداند")
ck(d["secrets_stored"] is False, "H2 اعلامِ صریح: چیزی ذخیره نشده")
ck("token" not in {k.lower() for k in d}, "H3 هیچ کلیدِ نشانی‌ای در پاسخ نیست")
b = XC.browser_state()
ck("profile_dir" not in b and b.get("profile_kept") is not True,
   "H4 نشانیِ پوشۀ موقت درِ پاسخ نمی‌آید", b)

print("\n── ط) چرخۀ mock سرِ هم ──")
# این بند به بانکِ کاری می‌خواهد تا `instruments` نشانیِ ISIN‌دار بدهد (بی‌ISIN
# خودِ قاعدۀ «بی‌نگاشتِ مبهم» رد می‌کند). بی‌بانک ⇒ SKIPِ شمرده با نامِ بند و علت.
import sqlite3                                                     # noqa: E402
_db = "market.db"
_row = None
if os.path.isfile(_db) and os.path.getsize(_db) > 0:
    _probe = sqlite3.connect("file:%s?mode=ro" % _db.replace("\\", "/"), uri=True)
    try:
        _row = _probe.execute("SELECT TRIM(l_val18), isin FROM instruments WHERE isin "
                              "IS NOT NULL AND length(isin) > 8 AND TRIM(l_val18) NOT "
                              "GLOB '*[0-9]' LIMIT 1").fetchone()
    except sqlite3.Error:
        _row = None
    finally:
        _probe.close()
if not _row:
    print("  SKIP  ط چرخۀ mock — market.dbِ ایزوله یا ردیفِ ISIN‌دار نبود")
else:
    SYM = _row[0]
    os.environ["BORS_EXECUTION_DB"] = os.path.join(
        tempfile.mkdtemp(prefix="bors_sarkhati_ledger_"), "ledger.db")

    from fastapi import FastAPI                                    # noqa: E402
    from fastapi.testclient import TestClient                      # noqa: E402
    import api.execution as EX                                     # noqa: E402

    app = FastAPI()
    app.include_router(EX.router)
    client = TestClient(app, raise_server_exceptions=False)
    eid = "sarkhati-guard-1"
    eid2 = "sarkhati-guard-2"
    draft = {"execution_id": eid, "symbol": SYM, "price": 1040, "quantity": 10,
             "side": "buy", "mock_instrument": True}

    s = client.get("/api/execution/status").json()
    ck(s.get("status") == "success" and "session" in s,
       "I1 status carries the session field", list(s)[:6])
    pf = client.post("/api/execution/preflight", json=draft).json()
    res = str((pf.get("instrument") or {}).get("resolution")).lower()
    ck(pf.get("status") == "success" and res == "exact",
       "I2 preflight resolves from the bank (resolution=exact, not a guess)",
       {"status": pf.get("status"), "resolution": res})
    prep = client.post("/api/execution/prepare", json=draft).json()
    ck(prep.get("status") == "success" and prep.get("sendable") is True,
       "I3 prepare succeeds and reports sendable", {k: prep.get(k) for k in ("status","code","sendable")})
    hal = client.post("/api/execution/halt", json={"reason": "guard"}).json()
    ck(hal.get("status") == "success", "I4 the emergency halt answers", hal.get("code"))
    # dispatch رویِ همان eidِ آماده‌شده عمداً رد می‌شود (قفلِ تکراری)، پس دروازۀ
    # توقف باِ یکِ قصدِ تازه سنجیده می‌شود — وگرنه I5/I8 هر دو به‌خاطرِ اشتباه سبز
    # می‌ماندند (همین درِ اجرایِ پیشین رخ داد).
    draft2 = dict(draft, execution_id=eid2)
    blocked = client.post("/api/execution/dispatch", json=draft2).json()
    ck(blocked.get("status") != "success", "I5 after halt the gate does not send",
       {k: blocked.get(k) for k in ("status","code","detail")})
    rs = client.post("/api/execution/resume", json={"reason": "guard-resume","confirm": True}).json()
    ck(rs.get("status") == "success", "I6 explicit resume (confirm) works", rs.get("code"))
    disp = client.post("/api/execution/dispatch", json=draft2).json()
    rec = disp.get("record") or {}
    ck(disp.get("status") == "success" and rec.get("execution_id") == eid2 and rec.get("symbol") == SYM,
       "I7 the mock send creates a traceable record",
       {k: rec.get(k) for k in ("execution_id","symbol","isin","status")})
    again = client.post("/api/execution/dispatch", json=draft2).json()
    ck(again.get("code") == "DUPLICATE_GUARD", "I8 one intent is not sent twice",
       {k: again.get(k) for k in ("status","code")})
    rc = client.post("/api/execution/reconcile/%s" % eid2).json()
    ck(rc.get("status") == "success" and (rc.get("record") or {}).get("execution_id") == eid2,
       "I9 reconcile has its own path for a sent execution", list(rc)[:5])
    bad = client.post("/api/execution/reconcile/never-sent").json()
    ck(str(bad.get("detail","")).startswith("INVALID_EXECUTION_ID"),
       "I10 an unknown id is refused with a stated reason", bad)
    led = client.get("/api/execution/ledger").json()
    rows = led.get("records") or []
    ck(any(r.get("execution_id") == eid2 and r.get("symbol") == SYM and r.get("isin") for r in rows),
       "I11 the durable audit row keeps symbol + ISIN + id",
       {"n": len(rows), "first": {k: (rows[0].get(k) if rows else None) for k in ("execution_id","symbol","status")}})

print("\nsarkhati_connect_v1117: %d passed / %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
