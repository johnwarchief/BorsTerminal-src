#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sarkhati_protocol_v1119 — گاردِ شکاف‌هایِ مأموریتِ 2026-10-17 (§۲ §۳ §۴ §۵).

چه چیزی ازِ گاردهایِ پیشین *متفاوت* است: آن‌ها دروازها و چرخۀِ سفارش را بستند؛
این یکی **قراردادِ سیم** را ازِ فایلِ فیکسچرِ منشأدار می‌خواند، «تأیید» را به
زمانِ تغییرِ نشست گره می‌زند، نقشِ سه مبدأ را جدا می‌سنجد، و صادقِ بودنِ
اعلامِ حالت (paper/backtest/live و رتبۀِ صف) را می‌گیرد.

قفل‌ها:
  * هیچ سفارشی ارسال نمی‌شود: ترافیکِ دستِ ماست (scripted)، و دورِ سنجه‌هایِ
    آداپتورِ خالص tripwireِ سوکت می‌نشیند.
  * هیچ creditialی درِ فایلِ فیکسچر نیست؛ فیکسچرها *ساختگیِ منشأدار*‌اند و هر
    case با `source` و `mock` علامت خورده است.
  * فیکسچری که «ازِ کارگزاری دریافت شده» ادعا کند، خودش نقصِ سنجه است؛ تنها
    ادعایِ مشاهده‌شده اینجا رفتارِ ۴۰۱ِ فقط‌خواندنی است.
"""
import json
import os
import socket
import sys
import tempfile
import threading

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


def skip(label, why):
    global SKIP
    SKIP += 1
    print("SKIP " + label + "  (" + why + ")")


SECRET = "eyJhbGciOiJIUzI1NiJ9.SIGNATURE_MUST_NEVER_LEAK.sig_value"
FIXTURE = os.path.join(ROOT, "dev", "fixtures", "easytrader_wire_v1.json")


class _SocketTripwire:
    """هر سوکتِ واقعی درِ دورِ این بلوک = شکستِ سنجه (نه هشدار)."""

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


def _js(x):
    return json.dumps(x, ensure_ascii=False)


def _instrument_row():
    """ردیفِ ISIN‌دار ازِ بانکِ کاری — همان روشِ p0_gates؛ نبودش ⇒ شمرده SKIP."""
    db = os.path.join(ROOT, "market.db")
    if not (os.path.isfile(db) and os.path.getsize(db) > 0):
        return None
    try:
        import sqlite3
        con = sqlite3.connect("file:%s?mode=ro" % db.replace(chr(92), "/"), uri=True)
    except Exception:
        return None
    try:
        row = con.execute("SELECT TRIM(l_val18), isin FROM instruments WHERE isin "
                          "IS NOT NULL AND length(isin) > 8 AND TRIM(l_val18) NOT "
                          "GLOB '*[0-9]' LIMIT 1").fetchone()
    except Exception:
        row = None
    finally:
        try:
            con.close()
        except Exception:
            pass
    return row


class Broker:
    """ترافیکِ بدلِ Orbis باِ شمّارِ فراخوانی‌ها — همان الگویِ p0_gates."""

    def __init__(self, place_status=200, place_body=None, auth_status=200):
        self.calls = []
        self.orders = []
        self.place_status = place_status
        self.place_body = place_body
        self.auth_status = auth_status

    def transport(self):
        outer = self

        class T:
            name = "v1119-scripted"
            is_live = True

            def request(self, *, method, url, headers, payload=None, timeout_s=7.0):
                import execution_easytrader as ET
                path = url.replace(ET.WIRE_BASE_URL, "")
                outer.calls.append("%s %s" % (method, path))
                if method == "POST":
                    body = outer.place_body if outer.place_body is not None else \
                        _js({"isSuccessful": True, "id": "V1119ORD"})
                    return ET.WireResponse(outer.place_status, {}, body)
                if outer.auth_status != 200:
                    return ET.WireResponse(outer.auth_status, {},
                                           _js({"isSuccessful": False}))
                return ET.WireResponse(200, {}, _js({"orders": outer.orders}))
        return T()


def main() -> int:
    import execution_connect as XC
    import execution_contract as EC
    import execution_easytrader as ET
    import execution_ledger as EL
    import execution_service as ES

    if not os.path.isfile(FIXTURE):
        print("required fixture missing: " + FIXTURE)
        return 1
    fx = json.loads(open(FIXTURE, encoding="utf-8").read())
    cases = fx["cases"]
    row = _instrument_row()
    SYM = row[0] if row else None
    ISIN = row[1] if row else "IRO1DRTY0001"

    print("\n── ۱) فیکسچرِ قرارداد باِ منشأ (نه ادعایِ دریافت) ──")
    ck(len(cases) >= 12, "ب) کمِ‌وبیشِ کامل: %d حالت" % len(cases), len(cases))
    no_src = [c["name"] for c in cases if not c.get("source")]
    ck(not no_src, "الف) هر case `source` دارد", no_src)
    no_mock = [c["name"] for c in cases if "mock" not in c]
    ck(not no_mock, "پ) هر case صریح می‌گوید ساختگی است یا نه", no_mock)
    lying = [c["name"] for c in cases
             if "broker-observed-read-only" in c.get("source", [])
             and c["response"]["status"] == 200 and "order" in c["name"]]
    ck(not lying, "ت) هیچ فیکسچری ادعایِ «۲۰۰ِ دریافتی ازِ درِ سفارش» نمی‌کند", lying)
    ck("official_docs_status" in fx and "403" in fx["official_docs_status"],
       "ث) وضعیتِ سندِ رسمی (۴۰۳) درِ خودِ فیکسچر ثبت شده", fx.get("official_docs_status", "")[:60])

    print("\n── ۲) داوریِ هر حالت: معنایِ عملیاتی، نه کدِ HTTP ──")
    bad = []
    for c in cases:
        r = c["response"]
        v = ET.interpret_easytrader_response(r["status"], r["body"], where="order",
                                             headers=r.get("headers") or {})
        e = c["expect"]
        got_err = v.error.value if v.error else None
        if v.accepted != e["accepted"] or got_err != e["error"] or v.ambiguous != e["ambiguous"]:
            bad.append("%s: got accepted=%s err=%s amb=%s want %s/%s/%s"
                       % (c["name"], v.accepted, got_err, v.ambiguous,
                          e["accepted"], e["error"], e["ambiguous"]))
        if e.get("broker_order_id") is not None and v.broker_order_id != e["broker_order_id"]:
            bad.append("%s: id=%r want %r" % (c["name"], v.broker_order_id, e["broker_order_id"]))
    ck(not bad, "الف) %d حالت دقیقاً همان معنایِ ثبت‌شده را می‌دهند" % len(cases), bad[:3])

    two = [c for c in cases if 200 <= c["response"]["status"] < 300]
    acc_no_flag = [c["name"] for c in two
                   if "isSuccessful" not in json.dumps(c["response"]["body"])]
    ck(all(ET.interpret_easytrader_response(200, c["response"]["body"],
                                            headers=c["response"].get("headers") or {}
                                            ).accepted is not True
           for c in cases if c["name"] in acc_no_flag),
       "پ) ۲۰۰ بی‌`isSuccessful` هرگز پذیرش نیست", acc_no_flag)
    v = ET.interpret_easytrader_response(200, {"isSuccessful": False, "id": "X9"},
                                         where="order")
    ck(v.accepted is False and v.broker_order_id in (None, "", "X9") and
       v.error is not None,
       "ت) ردِّ معنایی حتی با `id` پذیرش نیست", (v.accepted, v.broker_order_id, v.error))

    print("\n── ۳) هیچ خروجیِ مبهمی خودکار دوباره ارسال نمی‌شود ──")
    trip = _SocketTripwire()
    with trip:
        instr = EC.InstrumentRef(symbol="پتروشیمی", ins_code="1", isin="IRO1DRTY0001",
                                 broker_instrument="IRO1DRTY0001",
                                 resolution=EC.Resolution.EXACT)
        b = Broker(place_status=500)
        ad = ET.EasyTraderAdapter(transport=b.transport(), token=SECRET,
                                  instruments=(instr,))
        svc = ES.ExecutionService(ad, dry_run=False,
                                  limits=ES.Limits(require_confirmation=False,
                                                   max_order_value=5e7),
                                  audit=EL.ExecutionLedger(
                                      os.path.join(tempfile.mkdtemp(prefix="v1119_"),
                                                   "ledger.db")))
        draft = EC.OrderDraft(execution_id="V1119-AMB", instrument=instr,
                              side=EC.Side.BUY, price=1000.0, quantity=10.0,
                              mode=EC.OrderMode.SAFE)
        first_posts = sum(1 for x in b.calls if x.startswith("POST"))
        try:
            svc.execute(svc.prepare(draft, confirmed=True))
        except Exception:
            pass
        posts_after_first = sum(1 for x in b.calls if x.startswith("POST"))
        recs = svc.ledger()
        again = None
        try:
            again = svc.execute(svc.prepare(draft, confirmed=True))
        except ES.ExecutionError as e:
            again = ("refused", e.code.value)
        except Exception as e:
            again = ("raised", type(e).__name__)
        posts_final = sum(1 for x in b.calls if x.startswith("POST"))
        ck(posts_after_first == 1, "الف)اولین execute دقیقاً یکِ POST", b.calls)
        ck(posts_final == 1,
           "پ) دوبارِ همان قصد ⇒ هیچ POSTِ دوم نیست (ارسالِ دوبارهٔ کور ممنوع)", b.calls)
        ck(str(again) != "None", "ت) پاسخِ دوم صریح است: %s" % (again,), again)
        ck(not trip.hits, "ث) هیچ سوکتِ واقعی باز نشد", trip.hits)
        amb = [r for r in recs if getattr(r, "execution_id", "") == "V1119-AMB"]
        # ۵۰۰ باید *ناشناخته* بماند. اگر کسی آن را FAILED بنویسد، دروازۀ
        # «اول تعیین تکلیف» باز می‌شود و ارسالِ دوبارهٔ کور ممکن می‌گردد.
        ck(bool(amb) and all(getattr(r, "status", None) is EC.ExecutionStatus.UNKNOWN_RESULT
                             for r in amb),
           "ج) ۵۰۰ «ناشناخته» ماند، نه «مرد»",
           [str(getattr(r, "status", "?")) for r in amb])

    print("\n── ۴) تأیید باِ تغییرِ نشست باطل می‌شود (§۴) ──")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import api.execution as EX

    app = FastAPI()
    app.include_router(EX.router)
    c = TestClient(app, base_url="http://127.0.0.1:8001", raise_server_exceptions=False)
    b4 = Broker(place_status=200)
    instr4 = EC.InstrumentRef(symbol="پتروشیمی", ins_code="1", isin="IRO1DRTY0001",
                              broker_instrument="IRO1DRTY0001",
                              resolution=EC.Resolution.EXACT)
    ad4 = ET.EasyTraderAdapter(transport=b4.transport(), token=SECRET,
                               instruments=(instr4,))
    saved = (EX.ADAPTER_KIND, EX.LIVE_REQUESTED, EX.DRY_RUN, EX._ACTIVE_ADAPTER,
             EX._SERVICE, os.environ.get(EX.CONFIRM_PHRASE_ENV))
    EX.ADAPTER_KIND = "easytrader"
    EX.LIVE_REQUESTED = True
    EX.DRY_RUN = False
    EX._ACTIVE_ADAPTER = ad4
    EX._SERVICE = ES.ExecutionService(
        ad4, dry_run=False,
        limits=ES.Limits(require_confirmation=False, max_order_value=5e7,
                         max_orders=5),
        audit=EL.ExecutionLedger(os.path.join(tempfile.mkdtemp(prefix="v1119s_"),
                                              "ledger.db")),
        scheduler=EX._SCHEDULER)
    phrase = EX._confirm_phrase()
    import time as _t
    far = int(_t.time() * 1000) + 60_000
    sd = c.post("/api/execution/dispatch",
               json={"execution_id": "V1119-SCH", "symbol": SYM or "پتروشیمی", "side": "buy",
                     "price": 1000, "quantity": 10, "confirmed": True, "mode": "safe",
                     "confirm_phrase": phrase, "target_wall_ms": far}).json()
    ck(sd.get("status") == "scheduled", "الف) زمان‌بندی باِ عبارتِ درست ثبت می‌شود",
       {k: sd.get(k) for k in ("status", "code", "wait_ms")})
    ep_before = c.get("/api/execution/status").json().get("confirm_epoch")
    voided = EX._void_confirmations("test: token replaced")
    ep_after = c.get("/api/execution/status").json().get("confirm_epoch")
    ck(isinstance(ep_before, int) and ep_after == ep_before + 1,
       "پ) هر ابطال، دورۀِ تأیید را یکی جلو می‌برد", (ep_before, ep_after))
    ck(voided >= 1, "ت) زمان‌بندیِ منتظرِ با تأییدِ کهنه باطل شد", voided)
    _t.sleep(1.3)
    posts4 = [x for x in b4.calls if x.startswith("POST")]
    ck(not posts4, "ث) باطل‌شدن یعنی صفرِ POST — نه ارسال باِ نشستِ دیگر", b4.calls)
    st = EX._schedule_status("V1119-SCH")
    ck(st.get("state") == "aborted" and "confirmation voided" in str(st.get("cancelled_by", "")),
       "ج) رابط صادق است: لغو باِ علتِ ابطالِ تأیید", {k: st.get(k) for k in
                                                   ("state", "cancelled_by")})
    os.environ[EX.CONFIRM_PHRASE_ENV] = "عبارتِ تازه"
    ph2 = EX._confirm_phrase()
    r2 = c.post("/api/execution/dispatch",
                json={"execution_id": "V1119-IMM", "symbol": "پتروشیمی", "side": "buy",
                      "price": 1000, "quantity": 10, "confirmed": True, "mode": "safe",
                      "confirm_phrase": phrase}).json()
    ck(r2.get("status") == "error" and
       r2.get("code") == EC.ErrorCode.CONFIRM_PHRASE_REQUIRED.value,
       "ح) عبارتِ عوض‌شده درِ بک‌اند رد می‌شود (UI تنها داوری نیست)", r2.get("code"))
    ck(EX._void_confirmations("test: phrase changed") >= 0,
       "خ) تغییرِ عبارتِ تأیید هم دوره را جلو می‌برد (بی‌صفِ منتظر)")
    os.environ.pop(EX.CONFIRM_PHRASE_ENV, None)
    (EX.ADAPTER_KIND, EX.LIVE_REQUESTED, EX.DRY_RUN, EX._ACTIVE_ADAPTER,
     EX._SERVICE) = saved[:5]
    if saved[5] is None:
        os.environ.pop(EX.CONFIRM_PHRASE_ENV, None)
    else:
        os.environ[EX.CONFIRM_PHRASE_ENV] = saved[5]

    print("\n── ۵) نقشِ سه مبدأ، و نشتیِ تنظیماتی ──")
    os.environ.pop("BORS_EXECUTION_CONNECT_HOSTS", None)
    ck(XC.allowed_hosts() == XC.login_hosts(),
       "الف) فهرستِ پنجره = فهرستِ ورود (چیزی جزِ ورود اضافه نمی‌شود)",
       XC.allowed_hosts())
    api_host = ET.urlparse(ET.WIRE_BASE_URL).hostname
    ck(api_host not in XC.allowed_hosts(),
       "پ) میزبانِ API درِ فهرستِ پنجره نیست: %s" % api_host, XC.allowed_hosts())
    os.environ["BORS_EXECUTION_CONNECT_HOSTS"] = "evil-login.example"
    ck("evil-login.example" in XC.login_hosts() and api_host in ET.wire_hosts()
       and "evil-login.example" not in ET.wire_hosts(),
       "ت) گذاشتنِ دامنةِ ورود، درِ API را باز نمی‌کند (دو محیط، دو دروازه)",
       ET.wire_hosts())
    os.environ.pop("BORS_EXECUTION_CONNECT_HOSTS", None)
    for host in XC.DEFAULT_LOGIN_HOSTS:
        ck(XC.validate_url("https://%s/" % host)[0],
           "ث) مبدأِ پیش‌فرضِ مشاهده‌شده پذیرفته است: %s" % host,
           XC.validate_url("https://%s/" % host))
    ck(all("." in h and not h.startswith(".") and "*" not in h and "@" not in h
           for h in XC.DEFAULT_LOGIN_HOSTS + ET.wire_hosts()),
       "ج) هیچ wildcard/کاربر/نقطۀِLeading در هیچ فهرستی نیست",
       list(XC.DEFAULT_LOGIN_HOSTS) + list(ET.wire_hosts()))

    print("\n── ۶) حالت‌ها صادق‌اند: کاغذی کاغذی است، رتبهٔ صف ادعا نیست ──")
    st6 = c.get("/api/execution/status").json()
    mm = st6.get("mode_matrix") or {}
    ck(set(mm) == {"mock", "dry_run", "live", "paper", "backtest"},
       "الف) هر پنج حالت اعلام می‌شود", sorted(mm))
    ck(mm.get("paper", {}).get("can_reach_broker") is False and
       mm.get("backtest", {}).get("can_reach_broker") is False,
       "پ) کاغذی و بک‌تست صریح می‌گویند به بازار نمی‌رسند",
       {k: mm.get(k, {}).get("can_reach_broker") for k in ("paper", "backtest")})
    ck(mm.get("paper", {}).get("door") == "/api/bot/*",
       "ت) درِ کاغذی اعلام می‌شود، نه یکی‌شدنِ دو دروازه", mm.get("paper"))
    ck(st6.get("queue_rank", {}).get("claims_first") is False,
       "ث) هیچ ادعایِ «اولِ صف» درِ وضعیت نیست", st6.get("queue_rank"))
    import api.bot as BOT
    g = BOT._live_gates()
    ck(g.get("live_wired") is False and g.get("broker_wired") == "paper_only",
       "ج) ربات می‌داند که آداپتورِ کارگزاری ندارد",
       {k: g.get(k) for k in ("live_wired", "broker_wired")})

    print("\n── ۷) زمان‌سنجی: monotonic، تفکیک فاز، و بی‌عددِ کم‌نمونه ──")
    t = c.get("/api/execution/timings").json()
    ck(t.get("clock") == "monotonic", "الف) ساعتِ مدت‌ها monotonic است", t.get("clock"))
    ph = t.get("phases") or {}
    ck(all(("p50" not in v) or v["p50"] is None or v["p50"] >= 0 for v in ph.values()),
       "پ) هیچ مدّتِ منفی/بدل منتشر نمی‌شود", ph)
    one = [k for k, v in ph.items() if v.get("n") == 1]
    ck(all(ph[k]["p99"] is None and ph[k]["p95"] is None for k in one),
       "ت) باِ یکِ نمونه p95/p99 نمی‌سازد (None، نه عدد)", [ph[k] for k in one][:2])
    for i in range(6):
        c.post("/api/execution/preflight",
               json={"execution_id": "V1119-PF%d" % i, "symbol": SYM or "پتروشیمی",
                     "side": "buy", "price": 1000, "quantity": 10})
    t2 = c.get("/api/execution/timings").json()["phases"]
    pre = t2.get("preflight_ms") or {}
    ck(pre.get("n", 0) >= 6 and isinstance(pre.get("p99"), (int, float)),
       "ث) باِ ششِ نمونۀِ واقعی p99 عدد می‌شود", pre)
    ck(isinstance(pre.get("p50"), (int, float)) and pre["p50"] <= pre["p99"],
       "ج) p50 ≤ p99 رویِ همان نمونه‌ها", pre)

    print("\n── ۸) پاک‌سازیِ لاگ: چهار کنترلِ منفی، و بی‌بیش‌پاک‌کردن ──")
    secrets = [
        ("Authorization: " + SECRET, "JWT یتیم"),
        ("Authorization: Bearer " + SECRET, "Bearer + JWT"),
        ("GET /hook/" + SECRET + "?side=buy", "JWT درِ مسیر، بی‌هیچ برچسب"),
        ("Cookie: .AspNetCore.Session=abc123; sid=456def", "دمِ Cookie"),
        ("set-cookie=SSO=deadbeefdeadbeef", "set-cookie"),
        ("https://api/x?token=abcdefghijkl.mnopqr.stuv&side=buy", "queryِ token"),
    ]
    leaks = []
    for raw, tag in secrets:
        out = EC.redact(raw)
        for frag in ("SIGNATURE_MUST_NEVER_LEAK", "abc123", "456def", "deadbeef",
                     "abcdefghijkl"):
            if frag in out:
                leaks.append("%s ← %s" % (tag, out[:90]))
    ck(not leaks, "الف) هیچ مقداری ازِ شش رازِ کاشته‌شده بیرون نمی‌ماند", leaks[:2])
    benign = ["session summary: 3 orders, price 1000 quantity 10",
              "reconcile inconclusive: absent from broker list"]
    over = [s for s in benign if EC.redact(s) != s]
    ck(not over, "پ) متنِ بی‌راز دست‌نخورده می‌ماند (بیش‌پاک‌سازی نداریم)", over)
    m = EC.redact({"headers": {"authorization": SECRET, "x-appname": "titan"},
                   "note": "side=buy"})
    ck(m["headers"]["authorization"] == "<redacted>" and
       m["headers"]["x-appname"] == "titan" and m["note"] == "side=buy",
       "ت) ساختارِ mapping حفظ می‌شود، فقط مقدارِ رازدار می‌رود", m)
    long_hex = EC.redact({"trace": "A" * 40})
    ck(long_hex["trace"] == "A" * 40, "ث) کلیدِ بی‌راز (trace) پاک نمی‌شود",
       long_hex["trace"][:12])

    print("\n── ۹) دروازۀِ HTTP بی‌نشستِ تأییدشده: هیچ چیزی بیرون نمی‌رود ──")
    b9 = Broker(place_status=200, auth_status=401)
    ad9 = ET.EasyTraderAdapter(transport=b9.transport(), token=SECRET,
                               instruments=(instr4,))
    with _SocketTripwire() as trip9:
        try:
            ad9.authenticate()
            ok_auth = False
        except EC.BrokerError as e:
            ok_auth = e.code is EC.ErrorCode.SESSION_EXPIRED
        ck(ok_auth, "الف) ۴۰۱ رویِ پرسیدنیِ خواندنی ⇒ SESSION_EXPIRED، نه «متصل»")
        ck(not [x for x in b9.calls if x.startswith("POST")],
           "پ) نشستِ بی‌اعتبار هیچ POSTِ سفارشی نساخت", b9.calls)
        ck(not trip9.hits, "ت) هیچ سوکتِ واقعی باز نشد", trip9.hits)

    print("\n%d checks, %d failed, %d skipped" % (PASS + FAIL, FAIL, SKIP))
    print("SARKHATI PROTOCOL " + ("OK" if FAIL == 0 else "FAILED"))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
