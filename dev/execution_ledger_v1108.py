# -*- coding: utf-8 -*-
"""dev/execution_ledger_v1108.py — گاردِ ردِّپایِ ماندگار، قفلِ توقف، و درِ HTTPِ اجرا

مأموریتِ ۱۴۰۵-۰۷-۲۳، بندِ ۵ (سرخطی) و بندِ ۶-۴ (کنترلِ ریسکِ اجباری). پنج گاردِ
`dev/execution_*_v1` از قبل سرویسِ اجرا را می‌آزمایند، ولی هیچ‌کدام این چهار چیز
را ندیده بودند — و هر چهار تاِ پیشین رویِ همین مخزن *سبز* بودند:

۱) درِ `/api/execution/*` درِ `api/__init__.py` ثبت نشده بود، پس تمامِ مسیر
   درِ EXE ۴۰۴ است؛ و `frontend/src/features/portfolio/lib/orderClient.ts:147`
   همان را صدا می‌زند. گاردِ ثابت می‌کند هم ثبت است، هم درِ `hiddenimports`
   هر دو spec (قاعدۀ AGENTS.md: هر api/*.py تازه باید آنجا باشد).
۲) قفلِ توقفِ اضطراری هیچ‌جا وجود نداشت (و «kill switch» درِ هیچ فایلی نبود).
۳) ردِّپا یک dictِ درحافظه بود ⇒ با restart «چه فرستادم» می‌سوخت و
   `UNKNOWN_RESULT` بی‌sahib می‌ماند.
۴) ریسکِ سطحِ دوم (exposure، ضرر روزانه، نرخِ ارسال) نبود؛ و *قاعدۀ* نبودش
   مهم‌تر از خودِ عدد است: سقفِ تعریف‌نشده ⇒ داوری نمی‌شود، سقفِ تعریف‌شده
   با اندازۀ نیامده ⇒ **رد**.

چه قفلی می‌زند (شماره‌ها درِ متنِ خروجی هم همان‌اند):
  ۱ ثبتِ روتر در api/__init__.py (هم import، هم mods)
  ۲ 'api.execution' درِ hiddenimportsِ هر دو spec
  ۳ DRY_RUN و ADAPTER_KIND ثابت‌اند و ازِ بدنهٔ درخواست عوض نمی‌شوند
  ۴ قفلِ بسته ⇒ هیچ سفارشی ساخته نمی‌شود و هیچ تماسی با سرور نمی‌رود
  ۵ قفل رویِ دیسک می‌ماند: نشستِ تازه همان HALTED را می‌بیند
  ۶ TRIPPED بی‌confirm=True باز نمی‌شود (توقفِ خودکارِ ریسک دستِ انسان می‌خواهد)
  ۷ fail-closed: exposure خواسته شده ولی نداده شده ⇒ RISK_LIMIT
  ۸ fail-openِ عمدی: سقفِ تعریف‌نشده ⇒ هیچ داوری‌ای نمی‌شود (None ⇒ صفر نیست)
  ۹ dry-run پنجرۀ نرخِ ارسالِ واقعی را نمی‌خورد
  ۱۰ سفارشِ تکراری پسِ restart از ردِّپایِ ماندگار گرفته می‌شود
  ۱۱ timeout ⇒ UNKNOWN_RESULT، یکِ تماس، بی‌retryِ خودکار؛ بعدِ reconcile بسته می‌شود
  ۱۲ ردِّپا ترتیبِ واقعیِ رخداد را نگه می‌دارد (dispatch بعد ack)
  ۱۳ هیچ secretی رویِ دیسک نمی‌نشیند (token/cookie ⇒ <redacted>)
  ۱۴ دروازۀ HTTP از رشتۀ *دیگر* جواب می‌دهد (همان Thread-2 که گاردِ تک‌رشته نمی‌بیند)
  ۱۵ رکوردِ بازیابی‌شده وضعیتِ ساختگی نمی‌سازد: UNKNOWN همان می‌ماند
  ۱۶ کنترلِ منفی: اگر redaction و fail-closed و دروازۀ توقف را خراب کنیم، سنسور قرمز می‌شود
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

#: ردِّپا *پیش از هر importِ دیگری* به یک فایلِ موقت بدل می‌شود. چرا این‌قدر
#: بالای فایل: `api.execution` درِ سطحِ ماژول `default_ledger()` را صدا می‌زند،
#: پس اگر این خط دیرتر بیاید، گارد رویِ `user.db`ِ واقعیِ مالک می‌نویسد.
GUARD_DB = os.path.join(tempfile.mkdtemp(prefix="bors_exec_guard_"), "ledger.db")
os.environ["BORS_EXECUTION_DB"] = GUARD_DB

from execution_contract import (  # noqa: E402
    Capabilities, ErrorCode, InstrumentRef, OrderDraft, OrderState, OrderMode,
    Resolution, Side, redact,
)
from execution_ledger import (  # noqa: E402
    ARMED, HALT, TRIPPED, ExecutionLedger, KILL_KEY,
)
from execution_mock import MockBrokerAdapter  # noqa: E402
from execution_service import (  # noqa: E402
    ExecutionError, ExecutionService, Limits, RiskContext,
)

PASS, FAIL = 0, 0
defects: list[str] = []


def ck(cond, label, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("ok   %s" % label)
    else:
        FAIL += 1
        print("FAIL %s %s" % (label, detail))
    return bool(cond)


CAPS = Capabilities(place=True, list_orders=True, order_state=True,
                    queue_position=True, cancel=True)
INS = InstrumentRef(symbol="فولاد", ins_code="62563248656957441", isin="IRO1FOLN0001",
                    broker_instrument="FOLAD", resolution=Resolution.EXACT)


def draft(eid, price=100.0, qty=2.0, mode=OrderMode.SAFE):
    return OrderDraft(execution_id=eid, instrument=INS, side=Side.BUY,
                      price=price, quantity=qty, mode=mode)


def tmpdb(name="ledger.db"):
    return os.path.join(tempfile.mkdtemp(prefix="bors_exec_guard_"), name)


def svc(audit=None, limits=None, dry_run=False, script=None, risk=None):
    ad = MockBrokerAdapter(capabilities=CAPS, script=script or {})
    s = ExecutionService(ad, dry_run=dry_run, audit=audit,
                         limits=limits or Limits(), risk_ctx=risk)
    return s, ad


# ── ۱ و ۲) درِ HTTP ثبت شده و درِ spec هست؟ ─────────────────────────────────
def test_wiring():
    src = open(os.path.join(ROOT, "api", "__init__.py"), encoding="utf-8").read()
    imp = re.search(r"from \. import \(([^)]*)\)", src, re.S)
    mods = re.search(r"mods = \[([^\]]*)\]", src, re.S)
    ck(imp is not None and "execution" in imp.group(1),
       "۱ execution درِ importِ api_router هست")
    ck(mods is not None and re.search(r"\bexecution\b", mods.group(1)) is not None,
       "۱ execution درِ فهرست mods هست")
    # adb عمداً درِ EXE حذف می‌شود؛ اگر execution هم به آن فیلتر افتد، درِ EXE
    # همان ۴۰۴ِ همیشگی می‌ماند.
    filt = re.findall(r"if not .+:\s*\n\s*mods = .+", src)
    ck(not any("execution" in f for f in filt),
       "۱ execution ازِ بیلدِ فریزشده حذف نمی‌شود", str(filt)[:120])
    for spec in ("fts_terminal.spec", "bors_setup.spec"):
        t = open(os.path.join(ROOT, spec), encoding="utf-8").read()
        hid = t[t.index("hiddenimports"):]
        ck("'api.execution'" in hid, "۲ %s درِ hiddenimports 'api.execution' دارد" % spec)
    import api.execution as EX
    # این سنجه پیش‌تر «adapter فقط mock است» را می‌خواند. آن ادعا از
    # مأموریتِ ۱۴۰۵-۰۷-۲۴ دیگر درست نیست: آداپتورِ EasyTrader درِ کد وجود دارد.
    # چیزی که قفل می‌ماند *پیش‌فرض* است، نه تنوعِ پیاده‌شده — و همان قفل سه
    # بخش شد تا اگر روزی پیش‌فرض عوض شد، گارد فریاد بزند.
    ck(EX.DRY_RUN is True and EX.ADAPTER_KIND == "mock",
       "۳ پیش‌فرضِ EXE (بی‌متغیرِ محیطی): mock و dry-run قفل")
    ck(EX.ADAPTER_KIND == EX._configured_adapter()
       and EX._configured_adapter() == "mock",
       "۳ انتخابِ آداپتور فقط ازِ محیط خوانده می‌شود", EX._configured_adapter())
    ck("easytrader" in EX.ALLOWED_ADAPTERS and "titan" not in EX.ALLOWED_ADAPTERS
       and "onlineplus" not in EX.ALLOWED_ADAPTERS,
       "۳ سکوی مجاز: mock/easytrader — Online-Plus/Titan درِ فهرست نیست "
       "(رأیِ مالک ۱۴۰۵-۰۷-۲۴)")
    ck(EX.LIVE_REQUESTED is False,
       "۳ ترافیکِ زنده بی‌BORS_EXECUTION_LIVE خاموش است")
    body_has_dry = "dry_run" in re.sub(r"\"dry_run\"", "",
                                       open(os.path.join(ROOT, "api", "execution.py"),
                                          encoding="utf-8").read())
    ck("body.get(\"dry_run\")" not in open(os.path.join(ROOT, "api", "execution.py"),
                                          encoding="utf-8").read(),
       "۳ هیچ مسیرِ بدنه‌ای dry_run را عوض نمی‌کند", str(body_has_dry))


# ── ۴، ۵، ۶) قفلِ توقف ─────────────────────────────────────────────────────
def test_kill_switch():
    led = ExecutionLedger(tmpdb())
    s, ad = svc(audit=led)
    led.set_kill(HALT, "توقفِ دستی")
    try:
        s.prepare(draft("k-1"))
        ck(False, "۴ قفلِ بسته سفارش می‌سازد!")
    except ExecutionError as e:
        ck(e.code is ErrorCode.HALTED, "۴ قفلِ بسته ⇒ HALTED", e.code.value)
        ck("kill_switch" in [k for k, v in e.checks.items() if v == "FAIL"],
           "۴ دلیلِ رد درِ checks دیده می‌شود", str(e.checks))
    ck(not [w for w in ad.wire_calls if w.startswith("submit:")],
       "۴ بی‌ارسالِ واقعی به سرور", str(ad.wire_calls))
    led.close()

    # ۵) ماندگاری رویِ دیسک: نشستِ تازه با همان فایل
    path = tmpdb()
    a1 = ExecutionLedger(path)
    a1.set_kill(HALT, "از نشستِ پیشین")
    a1.close()
    a2 = ExecutionLedger(path)
    ck(a2.kill_state() == HALT and a2.halted(), "۵ قفل پسِ restart همان HALTED است",
       a2.kill_state())
    # ۶) توقفِ خودکارِ ریسک بی‌تأییدِ صریح باز نمی‌شود
    a2.set_kill(TRIPPED, "ضررِ روزانه")
    ck(a2.kill_state() == TRIPPED, "۶ حالتِ TRIPPED ثبت شد")
    a2.close()


# ── ۷ و ۸) قاعدۀ fail-closed / fail-open ───────────────────────────────────
def test_risk_rules():
    # ۷ سقف خواسته، اندازه نیامده ⇒ رد
    s, _ = svc(audit=ExecutionLedger(tmpdb()), limits=Limits(max_symbol_exposure=1e9))
    try:
        s.prepare(draft("r-1"))
        ck(False, "۷ exposure نداده‌شده پذیرفته شد!")
    except ExecutionError as e:
        ck(e.code is ErrorCode.RISK_LIMIT, "۷ exposure نداده‌شده ⇒ RISK_LIMIT", e.code.value)

    # ۷-پ) exposure داده‌شده + سرِ سقف ⇒ رد
    ctx_full = RiskContext(exposure_by_symbol={"فولاد": 900.0}, source="test")
    s2, _ = svc(audit=ExecutionLedger(tmpdb()), limits=Limits(max_symbol_exposure=1000.0),
                risk=ctx_full)
    try:
        s2.prepare(draft("r-2", price=200.0, qty=2.0))
        ck(False, "۷-پ عبور از سقفِ نماد پذیرفته شد!")
    except ExecutionError as e:
        ck(e.code is ErrorCode.RISK_LIMIT, "۷-پ سقفِ نماد نگهبان است", e.code.value)

    # ۸ سقفِ تعریف‌نشده ⇒ داوری نمی‌شود (None معنی «صفر» ندارد)
    s3, ad3 = svc(audit=ExecutionLedger(tmpdb()), limits=Limits(max_orders=5))
    p3 = s3.prepare(draft("r-3"))
    ck(p3.sendable, "۸ بی‌سقفِ exposure داوری نمی‌شود")
    ck(s3._risk_for(draft("x")).symbol_exposure("فولاد") is None,
       "۸ نبودِ context ⇒ None، نه صفر")

    # ضرر روزانه
    ctx_loss = RiskContext(realized_pnl_today=-120.0, exposure_by_symbol={}, source="t")
    s4, _ = svc(audit=ExecutionLedger(tmpdb()), limits=Limits(max_daily_loss=100.0, max_orders=5),
               risk=ctx_loss)
    try:
        s4.prepare(draft("r-4"))
        ck(False, "۸ ضرر روزانه از سقف گذشته!")
    except ExecutionError as e:
        ck(e.code is ErrorCode.RISK_LIMIT, "۸ ضرر روزانه ⇒ RISK_LIMIT", e.code.value)

    # ارزشِ هر سفارش
    s5, _ = svc(audit=ExecutionLedger(tmpdb()), limits=Limits(max_order_value=150.0, max_orders=5))
    try:
        s5.prepare(draft("r-5", price=100.0, qty=2.0))
        ck(False, "۸ ارزشِ تنها از سقف گذشته!")
    except ExecutionError as e:
        ck(e.code is ErrorCode.RISK_LIMIT, "۸ max_order_value نگهبان است", e.code.value)


# ── ۹ و ۱۰) نرخِ ارسال و تکراری پسِ restart ────────────────────────────────
def test_rate_and_duplicate():
    led = ExecutionLedger(tmpdb())
    s, _ = svc(audit=led, dry_run=True,
               limits=Limits(max_orders=50, max_orders_per_window=2, window_seconds=60))
    for i in range(3):
        s.execute(s.prepare(draft("dry-%d" % i)))
    ck(led.orders_in_window(60.0) == 0,
       "۹ dry-run پنجرۀ نرخِ واقعی را نمی‌خورد", str(led.orders_in_window(60.0)))

    led2 = ExecutionLedger(tmpdb())
    s2, _ = svc(audit=led2, dry_run=False, limits=Limits(max_orders=50,
                                                         max_orders_per_window=1))
    s2.execute(s2.prepare(draft("real-1")))
    try:
        s2.execute(s2.prepare(draft("real-2")))
        ck(False, "۹ پنجرۀ نرخِ واقعی کار نکرد!")
    except ExecutionError as e:
        ck(e.code is ErrorCode.RISK_LIMIT, "۹ پنجرۀ نرخ نگهبان است", e.code.value)

    # ۱۰) تکراری پسِ restart: دفترِ حافظه خالی، ردِّپا پُر
    path = tmpdb()
    a1 = ExecutionLedger(path)
    s1, _ = svc(audit=a1, dry_run=False)
    s1.execute(s1.prepare(draft("dup-1")))
    a1.close()
    a2 = ExecutionLedger(path)
    s3, ad3 = svc(audit=a2, dry_run=False)
    try:
        s3.prepare(draft("dup-1"))
        ck(False, "۱۰ تکراری پسِ restart پذیرفته شد!")
    except ExecutionError as e:
        ck(e.code is ErrorCode.DUPLICATE_GUARD, "۱۰ تکراری پسِ restart گرفته شد",
           e.code.value)
    ck(not [w for w in ad3.wire_calls if w.startswith("submit:")],
       "۱۰ بی‌تماسِ دوم با سرور", str(ad3.wire_calls))
    a2.close()


# ── ۱۱، ۱۲، ۱۳) timeout، ترتیب، redaction ─────────────────────────────────
def test_timeout_and_trail():
    led = ExecutionLedger(tmpdb())
    s, ad = svc(audit=led, dry_run=False, script={"t-1": ["timeout"]})
    rec = s.execute(s.prepare(draft("t-1")))
    ck(rec.status.value == "unknown_result", "۱۱ timeout ⇒ UNKNOWN_RESULT",
       rec.status.value)
    ck(len([w for w in ad.wire_calls if w == "submit:t-1"]) == 1,
       "۱۱ timeout بی‌retryِ خودکار", str(ad.wire_calls))
    # سرور پذیرفته ولی کلاینت ندیده — reconcile همان را می‌یابد
    ad.set_order_state("t-1", OrderState.OPEN)
    r2 = s.reconcile("t-1")
    ck(r2.status.value == "reconciled", "۱۱ reconcile بسته‌اش می‌کند", r2.status.value)

    kinds = [e["kind"] for e in led.trail("t-1")]
    # ترتیبِ ردِّپا: dispatch *حتماً* پیشِ هر نتیجهٔ بعدی باشد. `ack` درِ این
    # سناریو نیست (سرور timeout داد ⇒ «error»)، پس جست‌وجویِ بی‌مراقبتِ
    # `kinds.index('ack')` خودِ آزمون را می‌شکست.
    ck("dispatch" in kinds and kinds.index("dispatch") == 0
       and len(kinds) > 1, "۱۲ dispatch اول از همه ثبت می‌شود", str(kinds))
    ck("error" in kinds, "۱۲ خطایِ timeout هم ردِّپا می‌شود", str(kinds))
    ck("reconcile" in kinds and kinds.index("reconcile") > kinds.index("error"),
       "۱۲ reconcile بعدِ خطا می‌آید (ترتیبِ رخداد، نه ترتیبِ آرایه)", str(kinds))

    # ۱۳) secret رویِ دیسک نمی‌نشیند
    led3 = ExecutionLedger(tmpdb())
    led3.record(execution_id="sec-1", kind="dispatch",
                payload={"authorization": "Bearer abcdef123456",
                         "cookie": "session=xyz", "price": 100})
    with sqlite3.connect(led3.db_path) as conn:
        raw = conn.execute("SELECT payload FROM execution_event WHERE execution_id='sec-1'").fetchone()[0]
    ck("abcdef123456" not in raw and "session=xyz" not in raw and "<redacted>" in raw,
       "۱۳ token/cookie رویِ دیسک نیست", raw[:120])
    ck(json_ok(raw) and "price" in raw, "۱۳ redaction ساختار را نمی‌شکند", raw[:80])
    led3.close()


def json_ok(raw):
    import json
    try:
        json.loads(raw)
        return True
    except Exception:
        return False


# ── ۱۴ و ۱۵) دروازۀ HTTP از رشتۀ دیگر، و بازیابی بی‌ساختِ وضعی ─────────────
def test_http_door():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import api.execution as EX

    tmp = GUARD_DB
    os.environ["BORS_EXECUTION_DB"] = tmp
    app = FastAPI()
    app.include_router(EX.router)
    c = TestClient(app)

    got: dict = {}
    err: list[BaseException] = []

    def worker():
        try:
            got["status"] = c.get("/api/execution/status").json()
        except BaseException as e:  # noqa: BLE001
            err.append(e)

    # FastAPI خودش endpointهایِ sync را درِ threadpool می‌اندازد، ولی این آزمون
    # صریحاً از رشتۀ *خارجی* هم صدا می‌زند: اتصالِ sqliteِ مشترک بی‌
    # `check_same_thread=False` همین‌جا می‌ترکد، نه درِ گاردِ تک‌رشته.
    th = threading.Thread(target=worker)
    th.start()
    th.join(30)
    ck(not err and "status" in got, "۱۴ status از رشتۀ دیگر خطا نمی‌دهد",
       str(err[:1])[:160])
    st = got.get("status") or {}
    ck(st.get("kill_switch") in (ARMED, HALT, TRIPPED, "UNKNOWN"),
       "۱۴ status حالتِ قفل را اعلام می‌کند", str(st.get("kill_switch")))
    ck(st.get("live_enabled") is False and st.get("dry_run") is True,
       "۱۴ status دروغ نمی‌گوید: live نیست و dry-run است")
    ck(st.get("audit_db") == tmp, "۱۴ status مسیرِ ردِّپا را می‌گوید",
       str(st.get("audit_db")))

    h = c.post("/api/execution/halt", json={"reason": "تستِ گارد"})
    ck(h.status_code == 200 and h.json()["halted"] is True, "۱۴ halt کار می‌کند")
    d = c.post("/api/execution/dispatch",
               json={"symbol": "فولاد", "price": 100, "quantity": 2,
                     "mock_instrument": True, "dry_run": False}).json()
    ck(d["status"] == "error" and d.get("code") == ErrorCode.HALTED.value,
       "۴ بدنهٔ درخواست هم قفل را باز نمی‌کند", str(d)[:120])
    tr = c.post("/api/execution/resume", json={}).json()
    ck(tr["status"] == "success", "۱۴ resume دستی کار می‌کند", str(tr)[:100])

    # ۶ درِ سطحِ HTTP: TRIPPED بی‌confirm باز نمی‌شود
    c.post("/api/execution/halt", json={"auto": True, "reason": "ضرر روزانه"})
    blocked = c.post("/api/execution/resume", json={}).json()
    ck(blocked["status"] == "error", "۶ resumeِ TRIPPED بی‌confirm رد می‌شود",
       str(blocked)[:100])
    ok = c.post("/api/execution/resume", json={"confirm": True}).json()
    ck(ok["status"] == "success" and ok["kill_switch"] == ARMED,
       "۶ resume با confirm=True راه می‌دهد", str(ok)[:100])

    # ۱۵) بازیابی: رکوردِ UNKNOWN پسِ restart همان UNKNOWN می‌ماند
    EX._AUDIT.set_kill(ARMED, "پاک")
    ex = EX._SERVICE.execute(EX._SERVICE.prepare(
        EX._draft_from({"symbol": "فولاد", "price": 10, "quantity": 1,
                        "execution_id": "rec-1", "mock_instrument": True})))
    _rec_ign = ex
    led_now = EX._AUDIT
    led_now.record(execution_id="rec-2", kind="dispatch",
                   status="unknown_result", symbol="فولاد", side="buy",
                   price=10.0, quantity=1.0, mode="safe", broker="mock")
    fresh = ExecutionLedger(led_now.db_path)
    ck("rec-2" in fresh.open_ids(), "۱۵ unknown_result درِ open_ids می‌ماند",
       str(fresh.open_ids())[:120])
    last = fresh.latest_status("rec-2")
    ck(last and last["status"] == "unknown_result",
       "۱۵ بازیابی وضعیتی نمی‌سازد", str(last)[:80])
    fresh.close()


# ── ۱۶) کنترلِ منفی: سنسور کور نیست ────────────────────────────────────────
def test_negative_controls():
    import execution_ledger as EL
    import execution_service as ES

    # الف) redaction را خاموش کن ⇒ آزمونِ ۱۳ باید قرمز شود
    orig = EL.redact
    EL.redact = lambda v: v
    try:
        led = ExecutionLedger(tmpdb())
        led.record(execution_id="neg-1", kind="dispatch",
                   payload={"authorization": "Bearer abcdef123456"})
        raw = sqlite3.connect(led.db_path).execute(
            "SELECT payload FROM execution_event WHERE execution_id='neg-1'").fetchone()[0]
        ck("abcdef123456" in raw, "۱۶-الف اگر redact خاموش شود، token رویِ دیسک می‌آید")
        led.close()
    finally:
        EL.redact = orig

    # ب) fail-closed را «fail-open» کن ⇒ ریسک دیگر نگهبان نیست
    led2 = ExecutionLedger(tmpdb())
    s, _ = svc(audit=led2, limits=Limits(max_symbol_exposure=1e9, max_orders=5))
    real = ES.RiskContext.symbol_exposure
    ES.RiskContext.symbol_exposure = lambda self, symbol: 0.0
    try:
        try:
            s.prepare(draft("neg-2"))
            ck(True, "۱۶-ب با جعلِ exposureِ صفر، سفارش می‌گذرد (پس سنسور زنده است)")
        except ExecutionError:
            ck(False, "۱۶-ب سنسورِ ریسک حتی با جعل هم قرمز شد — چیزی درِ مسیر نیست")
    finally:
        ES.RiskContext.symbol_exposure = real

    # پ) دروازۀ توقف را بی‌اثر کن ⇒ قفل نباید سفارش را نگه دارد
    led3 = ExecutionLedger(tmpdb())
    s3, ad3 = svc(audit=led3, dry_run=False, limits=Limits(max_orders=5))
    real_h = ES.ExecutionService.halted
    ES.ExecutionService.halted = lambda self: (False, "ARMED")
    try:
        led3.set_kill(HALT, "بسته")
        try:
            s3.prepare(draft("neg-3"))
            ck(True, "۱۶-پ اگر دروازۀ توقف بی‌اثر شود، سفارش می‌سازد (سنسور زنده است)")
        except ExecutionError:
            ck(False, "۱۶-پ قفل حتی با بی‌اثرکردنِ halted هم جلو را گرفت — "
                      "یعنی توقف جایِ دیگری هم اعمال می‌شود و این آزمونِ جعل بی‌معنی است")
    finally:
        ES.ExecutionService.halted = real_h
    led3.close()

    # ت) ادعایِ «ثبتِ روتر» را بسنج: اگر execution از mods حذف شود، سنسور ۱ قرمز می‌شود
    src = open(os.path.join(ROOT, "api", "__init__.py"), encoding="utf-8").read()
    ck(src.count("execution") >= 2, "۱۶-ت متنِ api/__init__.py دو بار execution دارد",
       str(src.count("execution")))


if __name__ == "__main__":
    for fn in (test_wiring, test_kill_switch, test_risk_rules, test_rate_and_duplicate,
               test_timeout_and_trail, test_http_door, test_negative_controls):
        print("── %s" % fn.__name__)
        try:
            fn()
        except Exception as e:
            import traceback
            FAIL += 1
            print("FAIL %s استثنا: %s" % (fn.__name__, e))
            traceback.print_exc()
    print("\n%d passed / %d failed" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
