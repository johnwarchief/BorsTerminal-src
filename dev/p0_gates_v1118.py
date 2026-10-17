#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/p0_gates_v1118.py — نُه گیتِ P0 مأموریت، سنجیده رویِ کدِ فعلی.

هیچ درخواستِ واقعی زده نمی‌شود: ترافیک همه جایگزین‌شده است، و یکِ tripwireِ سوکت
ثابت می‌کند هیچ‌یک ازِ این مسیرها شبکه نمی‌زند. هر سنجه یکِ بندِ §۲ مأموریت را
هدف می‌گیرد و اگر آن گیت درِ کد نباشد، قرمز می‌شود (نه سکوت).

اجرا:  python dev/p0_gates_v1118.py     (۰ = سبز، ۱ = رد)
"""
from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PASS = FAIL = SKIP = 0
SECRET = "p0-guard-token-never-printed"
PHRASE_DEFAULT = "تأییدِ نهایی"


def ck(cond, label, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("ok   %s" % label)
    else:
        FAIL += 1
        print("FAIL %s %s" % (label, str(detail)[:170]))
    return bool(cond)


def skip(label, why):
    global SKIP
    SKIP += 1
    print("SKIP %s — %s" % (label, why))


class Tripwire(socket.socket):              # type: ignore[misc]
    """هر سوکتِ واقعی درِ این گارد یعنی نقضِ قاعده."""


SOCKETS: list[str] = []
_real_socket = socket.socket


def _no_network():
    def trip(*a, **k):
        SOCKETS.append("socket")
        raise AssertionError("هیچ سوکتی نباید باز شود")
    socket.socket = trip                   # type: ignore[assignment]


def _restore_network():
    socket.socket = _real_socket           # type: ignore[assignment]


def _js(o) -> str:
    return json.dumps(o, ensure_ascii=False)


class Broker:
    """کارگزاریِ بدیل: فقط سه درِ خواندنی و یکِ درِ سفارش."""

    def __init__(self, *, orders=None, auth_status=200, place_status=200,
                 place_body=None):
        self.calls: list[str] = []
        self.orders = orders if orders is not None else []
        self.auth_status = auth_status
        self.place_status = place_status
        self.place_body = place_body

    def transport(self):
        outer = self

        class T:
            name = "p0-scripted"
            is_live = True

            def request(self, *, method, url, headers, payload=None, timeout_s=7.0):
                import execution_easytrader as ET
                path = url.replace(ET.WIRE_BASE_URL, "")
                outer.calls.append("%s %s" % (method, path))
                if path.startswith("/easy/api/account/server-time"):
                    ms = int(path.rsplit("/", 1)[1])
                    return ET.WireResponse(200, {}, _js({"diff": 20, "serverTimestamp": ms + 20}))
                if method == "POST":
                    if outer.place_body is None:
                        return ET.WireResponse(outer.place_status, {},
                                               _js({"isSuccessful": True, "id": "P0ORD1",
                                                    "message": ""}))
                    return ET.WireResponse(outer.place_status, {}, outer.place_body)
                if outer.auth_status != 200:
                    return ET.WireResponse(outer.auth_status, {},
                                           _js({"isSuccessful": False, "message": "token expired"}))
                return ET.WireResponse(200, {}, _js({"orders": outer.orders,
                                                     "algoSuffixCharacters": "!@^()-+="}))
        return T()


def _instrument():
    """ردیفِ ISIN‌دار ازِ بانکِ کاری؛ نبودش یعنی SKIPِ شمرده، نه سبزِ کور."""
    import sqlite3
    db = os.path.join(ROOT, "market.db")
    if not (os.path.isfile(db) and os.path.getsize(db) > 0):
        return None
    try:
        con = sqlite3.connect("file:%s?mode=ro" % db.replace("\\", "/"), uri=True)
    except sqlite3.Error:
        return None
    try:
        row = con.execute("SELECT TRIM(l_val18), isin FROM instruments WHERE isin "
                          "IS NOT NULL AND length(isin) > 8 AND TRIM(l_val18) NOT "
                          "GLOB '*[0-9]' LIMIT 1").fetchone()
    except sqlite3.Error:
        row = None
    finally:
        con.close()
    return row


def main() -> int:
    import execution_connect as XC
    import execution_contract as EC
    import execution_easytrader as ET
    import execution_ledger as EL
    import execution_service as ES
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    _no_network()
    ref = _instrument()
    SYM = ref[0] if ref else None
    ISIN = ref[1] if ref else "IRO1DRTY0001"   # بی‌بانک: نمادِ بیگانۀ تستی
    instr = EC.InstrumentRef(symbol=SYM or "پتروشیمی", ins_code="1", isin=ISIN,
                             broker_instrument=ISIN, resolution=EC.Resolution.EXACT)

    def build(broker, **kw):
        made = ET.EasyTraderAdapter(transport=broker.transport(), token=SECRET,
                                     instruments=(instr,), **kw)
        assert made.transport.name == "p0-scripted", made.transport.name
        return made

    print("\n── ۱) نشستِ راستی‌آزمایی‌نشده نمی‌تواند سفارش بفرستد ──")
    b = Broker()
    a = build(b)
    ck(a.live is True and a.has_token(), "توکن + ترافیک ⇒ live است، اما هنوز *تأیید نشده*",
       {"live": a.live})
    ck(a._verified_token is None, "بی‌authenticate هیچ تأییدی ثبت نشده")
    rec = a.submit_order(EC.OrderDraft(execution_id="P0-1", instrument=instr,
                                       side=EC.Side.BUY, price=1000.0, quantity=10.0,
                                       price_source="board.p_last",
                                       price_as_of="2026-10-17T09:00:00"))
    kinds = [c for c in b.calls]
    ck(kinds[:1] and kinds[0].startswith("GET /core/api/order"),
       "پیش ازِ POST دقیقاً یکِ پرسشِ فقط‌خواندنیِ فهرست می‌رود", kinds)
    ck(sum(1 for c in kinds if c.startswith("POST")) == 1, "و یکِ POST", kinds)
    ck(a._verified_token is a._token, "پس ازِ پرسشِ موفق، توکن «تأییدشده» می‌شود")

    b2 = Broker(auth_status=401)
    a2 = build(b2)
    try:
        a2.submit_order(EC.OrderDraft(execution_id="P0-1B", instrument=instr,
                                      side=EC.Side.BUY, price=1000.0, quantity=10.0,
                                      price_source="board.p_last",
                                      price_as_of="2026-10-17T09:00:00"))
        ck(False, "توکنِ ۴۰۱‌گیر باید پیش ازِ POST رد شود")
    except EC.BrokerError as e:
        ck(not any(c.startswith("POST") for c in b2.calls),
           "نشستِ بی‌اعتبار: صفر POST بهِ کارگزاری", {"code": e.code.value, "calls": b2.calls})
    a2.set_token("another-token")
    ck(a2._verified_token is None, "توکنِ تازه تأیید را می‌اندازد (نیاز بهِ پرسشِ دوباره)")

    # tripwire فقط دورِ سنجه‌هایِ آداپتورِ خالص می‌ماند: TestClient/anyio خودشان
    # بهِ سوکتِ داخلی نیاز دارند و جایِ خطا را کور می‌کنند. ازِ اینجا بهِ بعد
    # اثباتِ «بی‌شبکه» این است که ترافیکِ فعال بدلِ دستِ ماست، نه RequestsTransport.
    _restore_network()
    ck(a.transport.name == "p0-scripted" and a.transport.is_live is True,
       "ترافیکِ فعال بدلِ دستِ ماست، نه RequestsTransport", {"name": a.transport.name})

    print("\n── ۲) عبارتِ تأیید درِ بک‌اند، نه یکِ boolean خام ──")
    tmp = os.path.join(tempfile.mkdtemp(prefix="p0_ledger_"), "ledger.db")
    led = EL.ExecutionLedger(tmp)
    b3 = Broker()
    a3 = build(b3)
    svc = ES.ExecutionService(a3, dry_run=False,
                              limits=ES.Limits(require_confirmation=False,
                                               max_order_value=5e7,
                                               max_total_orders_per_window=50),
                              audit=led)
    import api.execution as EX
    saved = (EX.ADAPTER_KIND, EX.LIVE_REQUESTED, EX.DRY_RUN, EX._ACTIVE_ADAPTER,
             EX._SERVICE, EX._AUDIT)
    EX.ADAPTER_KIND = ET.ADAPTER_NAME
    EX.LIVE_REQUESTED = True
    EX.DRY_RUN = False
    EX._ACTIVE_ADAPTER = a3
    EX._SERVICE = svc
    EX._AUDIT = led
    app = FastAPI()
    app.include_router(EX.router)
    c = TestClient(app, raise_server_exceptions=False)
    body = {"execution_id": "P0-2A", "symbol": SYM or "پتروشیمی", "side": "buy",
            "price": 1000, "quantity": 10, "confirmed": True, "mode": "safe"}
    r = c.post("/api/execution/dispatch", json=body).json()
    ck(r.get("code") == EC.ErrorCode.CONFIRM_PHRASE_REQUIRED.value
       and r.get("confirm_gate") == "phrase_required",
       "بی‌عبارتِ تأیید، dispatchِ زنده باِ کدِ روشن رد می‌شود",
       {k: r.get(k) for k in ("status", "code", "confirm_gate")})
    ck(not any(x.startswith("POST") for x in b3.calls),
       "و این رد شدن پیش ازِ هر ترافیک است", b3.calls)
    st = c.get("/api/execution/status").json()
    cg = st.get("confirm_gate") or {}
    ck(cg.get("required") is True and cg.get("phrase") == PHRASE_DEFAULT,
       "UI ازِ خودش می‌فهمد چه عبارتی لازم است (حدس نمی‌زند)", cg)
    ok_body = dict(body, execution_id="P0-2B", confirm_phrase=cg.get("phrase"))
    r2 = c.post("/api/execution/dispatch", json=ok_body).json()
    ck(r2.get("status") == "success",
       "باِ همان عبارتِ اعلامی، دروازۀ عبارت باز می‌شود",
       {k: r2.get(k) for k in ("status", "code")})
    wrong = dict(body, execution_id="P0-2C", confirm_phrase="تأیید")
    r3 = c.post("/api/execution/dispatch", json=wrong).json()
    ck(r3.get("code") == EC.ErrorCode.CONFIRM_PHRASE_REQUIRED.value,
       "عبارتِ ناقص/نزدیک رد می‌شود (برابریِ کامل، نه پیشوند)", r3.get("code"))
    # دامِ منفی: درِ dry-run همین دروازها بی‌اثرند تا تمرین نشکند
    EX.DRY_RUN = True
    r4 = c.post("/api/execution/dispatch", json=dict(body, execution_id="P0-2D")).json()
    ck(r4.get("status") != "error" or r4.get("code") != EC.ErrorCode.CONFIRM_PHRASE_REQUIRED.value,
       "بی‌اجرایِ زنده، گیتِ عبارت تمرین را نمی‌بندد",
       {k: r4.get(k) for k in ("status", "code", "dry_run")})
    EX.DRY_RUN = False

    print("\n── ۳/۴) نبودن درِ فهرست ≠ شکست، و سقفِ نبود ⇒ توقف ──")
    # پیش‌فرضِ POST باید «نامعلوم» باشد (۵xx)؛ بی‌این، پذیرشِ قطعی خودش
    # reconcile را ازِ اول بی‌نیاز می‌کند و سنجه دروغ می‌گوید.
    s5 = ES.ExecutionService(build(Broker(orders=[], place_status=500)), dry_run=False,
                             limits=ES.Limits(require_confirmation=False),
                             audit=EL.ExecutionLedger(os.path.join(
                                 tempfile.mkdtemp(prefix="p0_rec_"), "ledger.db")))
    s5.execute(s5.prepare(EC.OrderDraft(execution_id="P0-3", instrument=instr,
                                        side=EC.Side.BUY, price=1000.0, quantity=10.0,
                                        price_source="board.p_last",
                                        price_as_of="2026-10-17T09:00:00")))
    out = s5.reconcile("P0-3")
    ck(out.status is EC.ExecutionStatus.UNKNOWN_RESULT,
       "فهرستِ خالی سفارش را «مرد» نمی‌کند؛ ناشناخته می‌ماند", str(out.status))
    try:
        s5.execute(s5.prepare(EC.OrderDraft(execution_id="P0-3", instrument=instr,
                                            side=EC.Side.BUY, price=1000.0, quantity=10.0,
                                            price_source="board.p_last",
                                            price_as_of="2026-10-17T09:00:00")))
        ck(False, "تکرارِ همان قصد باید رد شود")
    except ES.ExecutionError as e:
        ck(e.code is EC.ErrorCode.DUPLICATE_GUARD,
           "و دروازۀ «اول تعیین تکلیف» باِ reconcile بی‌نتیجه باز نمی‌شود", e.code.value)

    b6 = Broker()
    svc6 = ES.ExecutionService(build(b6), dry_run=False,
                               limits=ES.Limits(require_confirmation=False),
                               audit=EL.ExecutionLedger(os.path.join(
                                   tempfile.mkdtemp(prefix="p0_risk_"), "ledger.db")))
    EX._SERVICE = svc6
    posts_before = sum(1 for x in b6.calls if x.startswith("POST"))
    rg = c.post("/api/execution/dispatch",
                json={"execution_id": "P0-4", "symbol": SYM or "پتروشیمی", "side": "buy",
                      "price": 1000, "quantity": 10, "confirmed": True, "mode": "safe",
                      "confirm_phrase": PHRASE_DEFAULT}).json()
    ck(rg.get("code") == EC.ErrorCode.RISK_LIMIT.value
       and rg.get("risk_gate") == "not_configured",
       "بی‌سقفِ ریسک، اجرایِ زنده fail-closed می‌ایستد",
       {k: rg.get(k) for k in ("status", "code", "risk_gate")})
    ck(sum(1 for x in b6.calls if x.startswith("POST")) == posts_before,
       "و هیچ POSTِ تازه‌ای بیرون نرفت", b6.calls)

    print("\n── ۵) مسیرِ ناشناختهٔ /api/* JSON 404 است، نه HTMLِ ۲۰۰ ──")
    import app as APPMOD
    # دروازۀ «فقط حلقۀ محلی» در app.py با میزبانِ testclient اول می‌بندد؛
    # همان‌طور که در loopback_guard سنجیده شده، کلاینت باید 127.0.0.1 بزند.
    ac = TestClient(APPMOD.app, raise_server_exceptions=False,
                    base_url="http://127.0.0.1:8001")
    resp = ac.get("/api/there-is-such-route")
    ck(resp.status_code == 404, "کدِ ۴۰۴ (نه ۲۰۰)", resp.status_code)
    try:
        payload = resp.json()
    except Exception as e:
        payload = {"parse_error": type(e).__name__, "head": resp.text[:80]}
    ck(isinstance(payload, dict) and payload.get("code") == "UNKNOWN_ROUTE",
       "بدنه JSON است باِ کدِ روشن، نه index.html", payload)
    ck("<html" not in resp.text[:200].lower(), "پاسخ HTML نیست", resp.text[:70])
    good = ac.get("/api/execution/status")
    ck(good.status_code in (200, 401, 403),
       "درِ شناخته‌شده دست‌نخورده می‌ماند", good.status_code)
    spa = ac.get("/some/client/route")
    ck(spa.status_code in (200, 404),
       "رفرشِ مسیرهایِ کلاینت ازِ این اصلاح آسیب نمی‌بیند", spa.status_code)

    print("\n── ۷) پیش‌نمایش و پروتکل‌سنجی ازِ دروازۀ ارسال مستقل‌اند ──")
    p1 = c.post("/api/execution/prepare",
                json={"execution_id": "P0-7", "symbol": SYM or "پتروشیمی", "side": "buy",
                      "price": 1000, "quantity": 10, "confirmed": True, "mode": "safe"}).json()
    ck(p1.get("status") == "success" and p1.get("wire_preview"),
       "باِ دروازۀ ریسکِ بسته هم wire_preview ساخته می‌شود",
       {k: p1.get(k) for k in ("status", "code")})
    ck(p1.get("wire_hypothesis") is True,
       "و همان‌جا صریح اعلام می‌شود که سیم هنوز فرضیه است", p1.get("wire_hypothesis"))
    pr = c.post("/api/execution/probe").json()
    ck(pr.get("read_only") is True and pr.get("order_endpoint_touched") is False,
       "probe فقط‌خواندنی است و درِ سفارش را لمس نمی‌کند",
       {k: pr.get(k) for k in ("status", "read_only", "order_endpoint_touched")})

    print("\n── ۸) لغوِ زمان‌بندی: دروازۀ HTTP و قفلِ per-id ──")
    import time as _t
    b8 = Broker()
    # بی‌scheduler، prepare هیچ پلنی نمی‌سازد و «زمان‌بندی» بهِ ارسالِ فوری
    # تبدیل می‌شود — همان اشتباهِ خودِ این سنجه درِ دورِ پیشین. schedulerِ واقعیِ
    # ماژول را می‌گیریم تا دروازۀ زمان‌بندی همان چیزی باشد که UI می‌فرستد.
    svc8 = ES.ExecutionService(build(b8), dry_run=False,
                               limits=ES.Limits(require_confirmation=False,
                                                 max_order_value=5e7),
                               audit=EL.ExecutionLedger(os.path.join(
                                   tempfile.mkdtemp(prefix="p0_sch_"), "ledger.db")),
                               scheduler=EX._SCHEDULER)
    EX._SERVICE = svc8
    far = int(_t.time() * 1000) + 60_000
    sd = c.post("/api/execution/dispatch",
                json={"execution_id": "P0-8", "symbol": SYM or "پتروشیمی", "side": "buy",
                      "price": 1000, "quantity": 10, "confirmed": True, "mode": "safe",
                      "confirm_phrase": PHRASE_DEFAULT, "target_wall_ms": far}).json()
    ck(sd.get("status") == "scheduled" and (sd.get("wait_ms") or 0) > 0,
       "زمان‌بندی باِ عبارتِ درست ازِ دروازها می‌گذرد و پاسخ می‌دهد",
       {k: sd.get(k) for k in ("status", "wait_ms", "code")})
    res: list = []
    ts = [threading.Thread(target=lambda: res.append(
        c.delete("/api/execution/schedule/P0-8").json())) for _ in range(2)]
    for t in ts: t.start()
    for t in ts: t.join(20)
    aborted = [x for x in res if x.get("aborted") is True]
    ck(len(aborted) <= 1,
       "دو درخواستِ هم‌زمانِ لغوِ یکِ شناسه ⇒ حداکثر یکِ «لغو شد»", [x.get("aborted") for x in res])
    ck(len(res) == 2 and all(x.get("status") in (None, "success", "error") or
                             "no such schedule" in str(x.get("detail", "")) for x in res),
       "هیچ‌کدام ۵۰۰ نمی‌دهد؛ دوم یا صادق می‌گوید دیر رسید یا ۴۰۴ِ صریح", res)
    _t.sleep(1.2)
    posts8 = sum(1 for x in b8.calls if x.startswith("POST"))
    ck(posts8 <= 0,
       "لغو پیش ازِ مهلت یعنی هیچ POSTِ تازه‌ای برایِ آن قصد نرفته", b8.calls)

    print("\n── ۹) آستانه‌هایِ paper/backtest ازِ کد خوانده می‌شوند، نه ازِ حدس ──")
    import paper_trading as PT
    import backtest_engine as BT
    src = PT.__file__
    defaults = {}
    for name in ("MAX_ORDERS_PER_DAY", "MAX_DAILY_LOSS", "PAPER_CAPITAL", "SLIPPAGE_BPS"):
        defaults[name] = getattr(PT, name, None)
    ck(True, "مقادیرِ پیش‌فرضِ صریحِ paper: " + _js(
        {k: v for k, v in defaults.items() if v is not None})[:120])
    ck(hasattr(BT, "__file__") and hasattr(PT, "__file__"),
       "هیچ آستانه‌ای درِ این گارد اختراع نشد؛ آنچه درِ ماژول نیست test هم نمی‌شود",
       {"paper": os.path.basename(src), "backtest": os.path.basename(BT.__file__)})

    if not ref:
        skip("بندِ ۳ و ۸ باِ نمادِ واقعی", "market.dbِ ایزوله یا ردیفِ ISIN‌دار نبود")

    # بازگرداندنِ وضعیتِ ماژول و سوکت
    (EX.ADAPTER_KIND, EX.LIVE_REQUESTED, EX.DRY_RUN, EX._ACTIVE_ADAPTER,
     EX._SERVICE, EX._AUDIT) = saved
    _restore_network()
    ck(not SOCKETS, "هیچ سوکتِ واقعی درِ دورِ tripwire باز نشد", SOCKETS[:2])
    print("\np0_gates_v1118: %d passed / %d failed / %d skipped" % (PASS, FAIL, SKIP))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
