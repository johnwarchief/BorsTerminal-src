#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/sarkhati_connect_v1117.py -- گاردِ لایۀ «اتصال به EasyTrader».

چه چیزی ثابت می‌شود (و چرا بی‌این، «اتصال» فقط یک دکمه بود):

  د) نشانی: فقط https، فقط میزبانِ تأییدشده، فقط بندرِ ۴۴۳؛ هر شکلِ دیگری که
     مرورگر و تجزیه‌گر یک‌جا نمی‌خوانند رد می‌شود.
  ه) بی‌دامنۀ ورود ⇒ `NO_LOGIN_HOST` با علت، و **هیچ پروسه‌ای** شروع نمی‌شود.
     با دامنهٔ تأییدشده ⇒ پنجره باز می‌شود، پروفایلِ موقت ساخته می‌شود و هنگام
     بستن **سنجیده می‌شود** که ازِ دیسک رفته است (نه ادعایِ ثابتِ کد).
  و) حالتِ نشست فقط از پرسشِ واقعی می‌آید: ۴۰۱⇒EXPIRED، احرازِ ناموفق⇒DISCONNECTED،
     timeout⇒UNKNOWN، پاکتِ معتبر⇒CONNECTED، و بی‌ترافیکِ مجاز⇒UNKNOWN+علت.
     دو سنجۀ «آداپتورِ واقعی» (F7/F8) نشان می‌دهند پاسخِ ۲۰۰ با بدنهٔ HTMLِ
     صفحۀ ورود «متصل» نمی‌شود، و اینکه همان آداپتور با بدنهٔ درست متصل می‌شود —
     پس F7 سنجهٔ کور نیست.
  ز) دامِ منفی: پنجره باز + بی‌نشانیِ معتبرِ حافظه ⇒ «CONNECTED» نیست.
  ح) راز هیچ‌جا نمی‌نشیند: نه در پاسخ، نه در وضعیتِ پنجره، و نشانیِ پوشۀ موقت
     هم بیرون نمی‌رود؛ پسِ بستن، پوشه واقعاً نیست.
  ط) چرخۀ mock سرِ هم: اتصال ← preflight ← prepare ← زمان‌بندی ← دروازۀ
     توقف ← reconcile ← ردیفِ حسابرسی، با «یک قصد = یک ارسال».

هیچ سوکتی زده نمی‌شود و هیچ مرورگری واقعی شروع نمی‌شود: Popen و taskkill
کارگذاری می‌شوند (قواعدِ مأموریت: برایِ آزمونِ یکِ گارد، کنشِ واقعیِ دستگاه
انجام نمی‌شود).

اجرا:  python dev/sarkhati_connect_v1117.py     (۰ = سبز، ۱ = رد)
"""
import json
import os
import subprocess
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
BS = chr(92)
AT = chr(64)

PASS = FAIL = SKIP = 0


def ck(cond, label, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("ok   %s" % label)
    else:
        FAIL += 1
        print("FAIL %s %s" % (label, str(detail)[:170]))
    return bool(cond)


def skip(n, band, reason):
    """SKIPِ شمرده (رأیِ مالک B): نامِ بند، تعداد، و علت — بی‌سبزکردنِ گیت."""
    global SKIP
    SKIP += n
    print("SKIP %d check(s) in %s — %s" % (n, band, reason))


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
        if self.outcome == "auth_state":
            # برخی آداپترها خطا نمی‌دهند، *حالت* را برمی‌گردانند — این مسیر هم
            # باید نگاشتِ خودش را داشته باشد (وگرنه ردیفِ dictِ مرده است).
            return EC.SessionStatus(state=EC.SessionState.AUTH_FAILED)
        if self.outcome == "error_state":
            return EC.SessionStatus(state=EC.SessionState.ERROR)
        return EC.SessionStatus(state=EC.SessionState.UNKNOWN)


class DeadProc:
    """فرزندی که دیگر نیست — برایِ سنجۀ جارویِ پروفایلِ مُرده."""
    pid = 4242

    def poll(self):
        return 0

    def wait(self, timeout=None):
        return 0


class LiveProc:
    """فرزندِ زندهٔ ساختگی؛ هیچِ چیزی درِ ویندوز شروع نمی‌شود."""
    pid = 4242

    def poll(self):
        return None

    def wait(self, timeout=None):
        return 0


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
d6_ok, d6_why = XC.validate_url("https://mts.example-broker.ir" + BS + AT +
                                "api-mts.orbis.easytrader.ir/")
ck(d6_ok is False and d6_why.startswith("«" + BS + "»"),
   "D6 «میزبانِ مخرب + جداکننده + میزبانِ مجاز» باِ همان علتِ جداکننده رد می‌شود", d6_why)
d7_ok, d7_why = XC.validate_url("https://user:pw" + AT + "mts.example-broker.ir/")
ck(d7_ok is False and "ساختار" in d7_why,
   "D7 اطلاعاتِ کاربری درِ نشانی باِ علتِ ساختارِ Authority رد می‌شود", d7_why)
ck(XC.validate_url("https://mts.example-broker.ir:8443/")[0] is False,
   "D8 بندرِ غیرِ ۴۴۳ رد می‌شود")
ck(XC.validate_url("https://mts.example-broker.ir:443.evil/")[0] is False,
   "D9 بندرِ عددی‌نبودن رد می‌شود")
ck(XC.validate_url("https://mts.example-broker.ir./")[0] is False,
   "D10 میزبانِ نقطه‌دارِ انتهایی رد می‌شود")

print("\n── ه) پنجره: یا با دامنهٔ تأییدشده، یا هیچ پروسه ──")
opened = []
_real_popen = XC.subprocess.Popen
_real_run = XC.subprocess.run
XC.subprocess.Popen = lambda *a, **k: opened.append(a)          # کارگذاری
XC.subprocess.run = lambda *a, **k: a
os.environ.pop("BORS_EXECUTION_CONNECT_HOSTS", None)
os.environ["BORS_CONNECT_BROWSER"] = sys.executable             # فایلِ موجود، بی‌اجرا
h, why = XC.open_login_window("https://anything.example/")
ck(h is None and "مجاز" in why, "E1 نشانیِ تأییدنشده پنجره باز نمی‌کند", why)
h2, why2 = XC.open_login_window("https://api-mts.orbis.easytrader.ir/")
ck(h2 is None and why2.startswith(XC.NO_LOGIN_HOST),
   "E2 بی‌دامنۀ ورود، میزبانِ API هم پنجره باز نمی‌کند", why2)
ck(not opened, "E3 هیچ پروسه‌ای شروع نشد (دامنه تأیید نشده)", opened)

os.environ["BORS_EXECUTION_CONNECT_HOSTS"] = "mts.example-broker.ir"
XC.subprocess.Popen = lambda *a, **k: LiveProc()
h4, why4 = XC.open_login_window("https://mts.example-broker.ir/login")
prof = getattr(h4, "profile_dir", "")
ck(isinstance(h4, XC.BrowserHandle) and not why4 and os.path.isdir(prof),
   "E4 با دامنهٔ تأییدشده پنجره و پروفایلِ موقت ساخته می‌شود", why4)
st = XC.browser_state()
ck(st["open"] is True and st["profile_kept"] is True,
   "E5 وضعیتِ پنجره زنده و پروفایلِ رویِ دیسک را صادق می‌گوید", st)
ck(prof and prof not in json.dumps(st, ensure_ascii=False),
   "E6 نشانیِ پوشۀ موقت درِ وضعیت بیرون نمی‌رود")
okc, note = XC.close_login_window()
ck(okc and note == "closed" and not os.path.isdir(prof),
   "E7 بستنِ پنجره پروفایل را واقعاً ازِ دیسک برمی‌دارد", note)
ck(XC.browser_state()["profile_kept"] is False,
   "E8 پسِ بستن، ادعایِ پاک‌شدن باِ دیسک می‌خواند")
# پروفایلِ مُرده نباید باِ بازِ‌کردنِ بعدی جا بی‌ماند
XC.subprocess.Popen = lambda *a, **k: LiveProc()
h9, _ = XC.open_login_window("https://mts.example-broker.ir/login")
stale = h9.profile_dir
XC._SESSION["browser"] = XC.BrowserHandle(proc=DeadProc(), profile_dir=stale,
                                          url=h9.url, opened_at=0.0)
h10, _ = XC.open_login_window("https://mts.example-broker.ir/login")
ck(not os.path.isdir(stale) and h10.profile_dir != stale,
   "E9 پروفایلِ پنجرۀ مُرده پیش ازِ جایگزینی پاک می‌شود",
   {"stale": os.path.isdir(stale)})
XC.close_login_window()
XC.subprocess.Popen = _real_popen
XC.subprocess.run = _real_run

print("\n── و/ز) حالتِ نشست فقط از پرسشِ واقعی ──")
r = XC.verify(FakeAdapter(live=False))
ck(r["state"] == XC.STATE_UNKNOWN and r["blocked_reason"],
   "F1 بی‌ترافیکِ مجاز ⇒ UNKNOWN با علت، نه CONNECTED", r)
ck(XC.verify(FakeAdapter(token="", outcome="ok"))['state'] == XC.STATE_DISCONNECTED,
   "F2 بی‌نشست ⇒ DISCONNECTED")
ck(XC.verify(FakeAdapter(token="t", outcome="expired"))['state'] == XC.STATE_EXPIRED,
   "F3 ۴۰۱ ⇒ EXPIRED")
ck(XC.verify(FakeAdapter(token="t", outcome="forbidden"))['state'] ==
   XC.STATE_DISCONNECTED,
   "F4 " + D("403") + " احرازِ ناموفق ⇒ DISCONNECTED (نه «منقضی»ِ بی‌مبناء، نه CONNECTED)")
ck(XC.verify(FakeAdapter(token="t", outcome="timeout"))['state'] == XC.STATE_UNKNOWN,
   "F5 timeout ⇒ UNKNOWN (نه «فرستاد»، نه «نفرستاد»)")
ck(XC.verify(FakeAdapter(token="t", outcome="auth_state"))['state'] ==
   XC.STATE_DISCONNECTED,
   "F4b آداپتوری که «احرازِ ناموفق» را برمی‌گرداند ⇒ DISCONNECTED (ردیفِ dict زنده است)")
ck(XC.verify(FakeAdapter(token="t", outcome="error_state"))['state'] == XC.STATE_UNKNOWN,
   "F4c «خطایِ عمومی» هرگز CONNECTED نمی‌شود")
ck(XC.verify(FakeAdapter(token="t", outcome="ok"))['state'] == XC.STATE_CONNECTED,
   "F6 پاسخِ معنادار ⇒ CONNECTED")

# آداپتورِ *واقعی* EasyTrader با ترافیکِ بدیل: HTMLِ ۲۰۰ اتصال نمی‌سازد
import execution_easytrader as ET                                 # noqa: E402


class HtmlTransport:
    """۲۰۰ با صفحۀ ورود — همان چیزی که «متصل» خواندنش نقصِ اصلی بود."""
    name = "html"
    is_live = True

    def __init__(self, body):
        self.body = body

    def request(self, **kw):
        return ET.WireResponse(200, {}, self.body)


html_a = ET.EasyTraderAdapter(transport=HtmlTransport(
    "<html><body>login</body></html>"), token="t", instruments=())
js_a = ET.EasyTraderAdapter(transport=HtmlTransport(
    json.dumps({"orders": []})), token="t", instruments=())
rh = XC.verify(html_a)
rj = XC.verify(js_a)
ck(rh["state"] != XC.STATE_CONNECTED and rh["state"] == XC.STATE_UNKNOWN,
   "F7 آداپتورِ واقعی: ۲۰۰ با بدنهٔ HTMLِ صفحۀ ورود ⇒ CONNECTED نیست", rh)
ck(rj["state"] == XC.STATE_CONNECTED,
   "F8 دامِ مثبتِ همان سنجه: ۲۰۰ با پاکتِ JSON ⇒ CONNECTED (پس F7 کور نیست)", rj)

class LeakyErrorAdapter:
    """خطایی که خودش نشانیِ خام را درِ جزئیات می‌برد — مسیرِ reason باید سانسور شود."""
    live = True
    name = "leaky"
    def has_token(self): return True
    def authenticate(self):
        raise EC.BrokerError(EC.ErrorCode.AUTH_FAILED,
                             "Authorization: Bearer " + SECRET_LEAK)


SECRET_LEAK = "BEARERTOKEN-must-never-appear"
rv = XC.verify(LeakyErrorAdapter())
ck("BEARERTOKEN-must-never-appear" not in json.dumps(rv, ensure_ascii=False),
   "F9 دلیلِ خطا پیش ازِ پاسخ سانسور می‌شود (redact)، نه خاموش", rv.get("reason"))
ck(rv["state"] == XC.STATE_DISCONNECTED, "F10 نشانهٔ خطا حالت را هم می‌سازد", rv)

st = XC.verify(FakeAdapter(token="", outcome="ok"))
ck(st["state"] != XC.STATE_CONNECTED,
   "G1 پنجرۀ باز و نشانیِ بی‌حافظه به‌تنهایی «متصل» نیست", st)

print("\n── ح) راز هیچ‌جا نمی‌نشیند ──")
SECRET = "SECRETTOKEN-must-never-appear"
d = XC.status_dict(FakeAdapter(token=SECRET), XC.verify(FakeAdapter(token=SECRET)))
blob = json.dumps(d, ensure_ascii=False, default=str)
ck(SECRET not in blob, "H1 وضعیتِ نشست نشانی را برنمی‌گرداند")
ck(d["secrets_stored"] is False, "H2 اعلامِ صریح: چیزی ذخیره نشده")


def _token_keys(o, path=""):
    """هر کلیدِ نشانه‌دار درِ هر لانه؛ مقدارش باید بولی باشد نه راز."""
    out = []
    if isinstance(o, dict):
        for k, v in o.items():
            if "token" in str(k).lower() or "secret" in str(k).lower():
                out.append((path + "/" + str(k), v))
            out += _token_keys(v, path + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            out += _token_keys(v, "%s[%d]" % (path, i))
    return out


flagged = [(p, v) for p, v in _token_keys(d) if not isinstance(v, bool)]
ck(not flagged, "H3 هر کلیدِ نشانه‌دار درِ پاسخ فقط بولی است، نه مقدارِ راز", flagged)
ck("profile_dir" not in blob and BS not in blob.replace(BS + BS, ""),
   "H4 نشانیِ ویندوزیِ پوشۀ موقت درِ هیچ پاسخ نمی‌آید")

print("\n── ط) چرخۀ mock سرِ هم ──")
# این بند به بانکِ کاری می‌خواهد تا `instruments` نشانیِ ISIN‌دار بدهد (بی‌ISIN
# خودِ قاعدۀ «بی‌نگاشتِ مبهم» رد می‌کند). بی‌بانک ⇒ SKIPِ شمرده با نامِ بند و علت.
import sqlite3                                                    # noqa: E402
_db = "market.db"
_row = None
if os.path.isfile(_db) and os.path.getsize(_db) > 0:
    _probe = sqlite3.connect("file:%s?mode=ro" % _db.replace(BS, "/"), uri=True)
    try:
        _row = _probe.execute("SELECT TRIM(l_val18), isin FROM instruments WHERE isin "
                              "IS NOT NULL AND length(isin) > 8 AND TRIM(l_val18) NOT "
                              "GLOB '*[0-9]' LIMIT 1").fetchone()
    except sqlite3.Error:
        _row = None
    finally:
        _probe.close()
if not _row:
    skip(11, "ط (I1–I11)",
         "market.dbِ ایزوله یا ردیفِ ISIN‌دار نبود؛ چرخۀ preflight→dispatch→reconcile "
         "سنجیده نشد")
else:
    SYM = _row[0]
    os.environ["BORS_EXECUTION_DB"] = os.path.join(
        tempfile.mkdtemp(prefix="bors_sarkhati_ledger_"), "ledger.db")

    from fastapi import FastAPI                                    # noqa: E402
    from fastapi.testclient import TestClient                      # noqa: E402
    import api.execution as EX                                    # noqa: E402

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
       "I3 prepare succeeds and reports sendable",
       {k: prep.get(k) for k in ("status", "code", "sendable")})
    hal = client.post("/api/execution/halt", json={"reason": "guard"}).json()
    ck(hal.get("status") == "success", "I4 the emergency halt answers", hal.get("code"))
    # dispatch رویِ همان eidِ آماده‌شده عمداً رد می‌شود (قفلِ تکراری)، پس دروازۀ
    # توقف باِ یکِ قصدِ تازه سنجیده می‌شود — وگرنه I5/I8 هر دو به‌خاطرِ اشتباه سبز
    # می‌ماندند (همین درِ اجرایِ پیشین رخ داد).
    draft2 = dict(draft, execution_id=eid2)
    blocked = client.post("/api/execution/dispatch", json=draft2).json()
    ck(blocked.get("status") != "success", "I5 after halt the gate does not send",
       {k: blocked.get(k) for k in ("status", "code", "detail")})
    rs = client.post("/api/execution/resume",
                     json={"reason": "guard-resume", "confirm": True}).json()
    ck(rs.get("status") == "success", "I6 explicit resume (confirm) works", rs.get("code"))
    disp = client.post("/api/execution/dispatch", json=draft2).json()
    rec = disp.get("record") or {}
    ck(disp.get("status") == "success" and rec.get("execution_id") == eid2
       and rec.get("symbol") == SYM,
       "I7 the mock send creates a traceable record (dry-run)",
       {k: rec.get(k) for k in ("execution_id", "symbol", "isin", "status")})
    again = client.post("/api/execution/dispatch", json=draft2).json()
    ck(again.get("code") == "DUPLICATE_GUARD", "I8 one intent is not sent twice",
       {k: again.get(k) for k in ("status", "code")})
    rc = client.post("/api/execution/reconcile/%s" % eid2).json()
    ck(rc.get("status") == "success"
       and (rc.get("record") or {}).get("execution_id") == eid2,
       "I9 reconcile has its own path for a sent execution", list(rc)[:5])
    bad = client.post("/api/execution/reconcile/never-sent").json()
    ck(str(bad.get("detail", "")).startswith("INVALID_EXECUTION_ID"),
       "I10 an unknown id is refused with a stated reason", bad)
    led = client.get("/api/execution/ledger").json()
    rows = led.get("records") or []
    ck(any(r.get("execution_id") == eid2 and r.get("symbol") == SYM and r.get("isin")
           for r in rows),
       "I11 the durable audit row keeps symbol + ISIN + id",
       {"n": len(rows), "first": {k: (rows[0].get(k) if rows else None)
                                 for k in ("execution_id", "symbol", "status")}})

print("\nsarkhati_connect_v1117: %d passed / %d failed / %d skipped" % (PASS, FAIL, SKIP))
if SKIP:
    print("SKIP total: %d check(s) — see the SKIP line above for the reason" % SKIP)
sys.exit(1 if FAIL else 0)
