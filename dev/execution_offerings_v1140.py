#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""گارد چند عرضهٔ اولیه: provenance، بودجهٔ اتمیک، Preflight و Timing.

هیچ شبکه/سفارشی صدا زده نمی‌شود؛ همهٔ رزروها رویِ SQLiteِ موقت‌اند.
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
from dataclasses import replace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import execution_offerings as O  # noqa: E402
import execution_timing as T  # noqa: E402

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


def new_store():
    d = tempfile.mkdtemp(prefix="offer_guard_")
    return O.OfferingStore(os.path.join(d, "offerings.db")), d


def raises(code, fn):
    try:
        fn()
        return False
    except O.OfferingsError as e:
        return e.code == code


def make(store, sym="TESTA", isin="IRO1TEST0001", *, method="BOOK_BUILDING",
         start=None, end=None, pmin=100.0, pmax=110.0, qmin=1.0, qmax=1000.0,
         quota=500.0, fee=0.0012, source="unit-test", verified=None,
         data_as_of=None, price_source="unit-test", fee_source="unit-test",
         source_url="https://example.test/offering", unverified=False):
    at = O.now_ms()
    vts = None if unverified else (at if verified is None else verified)
    dts = None if unverified else (at if data_as_of is None else data_as_of)
    return store.upsert(
        symbol=sym, isin=isin, method=method, market="test",
        start_ms=start if start is not None else at - 3600_000,
        end_ms=end if end is not None else at + 3600_000,
        price_min=pmin, price_max=pmax, price_source=price_source,
        min_qty=qmin, max_qty=qmax, per_code_quota=quota,
        fee_rate=fee, fee_source=fee_source, source=source, source_url=source_url,
        verified_at_ms=vts, data_as_of_ms=dts)


def api_checks() -> None:
    """قراردادِ HTTP با TestClientِ محلی؛ هیچ درخواستِ بیرونی صدا زده نمی‌شود."""
    import api.execution as EX
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    tmp = tempfile.mkdtemp(prefix="offer_api_")
    old_env = os.environ.get("BORS_OFFERINGS_DB")
    old_store = EX._OFFERING_STORE
    os.environ["BORS_OFFERINGS_DB"] = os.path.join(tmp, "offerings.db")
    EX._OFFERING_STORE = None
    app = FastAPI()
    app.include_router(EX.router)
    c = TestClient(app, raise_server_exceptions=False)
    try:
        now = O.now_ms()
        base = {
            "symbol": "APIT", "isin": "IRO1APIT0001", "method": "BOOK_BUILDING",
            "start_ms": now - 3_600_000, "end_ms": now + 3_600_000,
            "price_min": 100, "price_max": 110, "price_source": "official",
            "min_qty": 1, "max_qty": 1000, "per_code_quota": 500,
            "fee_rate": 0.0012, "fee_source": "official", "source": "official",
            "source_url": "https://example.test/api-offering",
            "verified_at_ms": now, "data_as_of_ms": now - 1_000,
        }
        r = c.post("/api/execution/offerings", json=base)
        j = r.json()
        ck(r.status_code == 200 and j.get("offering", {}).get("status") == "VERIFIED",
           "API: عرضهٔ کامل VERIFIED می‌شود", j)
        oid = str(j.get("offering", {}).get("id") or "")
        bad = dict(base, symbol="APIN", isin="IRO1APIN0002", source_url="")
        jb = c.post("/api/execution/offerings", json=bad).json()
        ck(jb.get("status") == "error" and jb.get("code") == "INVALID_PROVENANCE",
           "API: تأیید بدون نشانی منبع رد می‌شود", jb)
        badfee = dict(base, symbol="APIF", isin="IRO1APIF0003", fee_rate=-1)
        jf = c.post("/api/execution/offerings", json=badfee).json()
        ck(jf.get("status") == "error" and jf.get("code") == "INVALID_FEE",
           "API: کارمزد نامعتبر رد می‌شود", jf)
        rb = c.post("/api/execution/offerings/budget", json={
            "total_cap": 100_000, "cash_reserve": 0, "max_per_offering": 100_000,
            "priorities": {oid: 0}}).json()
        ck(rb.get("status") == "success" and rb["capital"]["version"] == 1,
           "API: بودجه ذخیره می‌شود", rb)
        body = {"plans": [{"offering_id": oid, "intent_id": "API-1",
                           "price": 105, "quantity": 10}], "max_age_s": 3600}
        rp = c.post("/api/execution/offerings/plan", json=body).json()
        ck(rp.get("status") == "success"
           and rp["decisions"][0]["state"] == "RESERVED",
           "API: رزرو اتمیک", rp)
        first_total = rp.get("reserved_total")
        rp2 = c.post("/api/execution/offerings/plan", json=body).json()
        ck(rp2["decisions"][0]["state"] == "RESERVED"
           and rp2["decisions"][0]["reason"] == "IDEMPOTENT"
           and rp2["reserved_total"] == first_total,
           "API: تکرارِ همان درخواست رزرو دوم نمی‌سازد", rp2)
        g = c.get("/api/execution/offerings").json()
        ck(g.get("status") == "success" and g.get("available") is not None
           and g.get("reserved_total") == first_total,
           "API: موجودیِ باقی‌مانده گزارش می‌شود", g)
        bad_pf = c.post("/api/execution/offerings/%s/preflight" % oid,
                        json={"price": 105, "quantity": "abc"}).json()
        ck(bad_pf.get("status") == "error",
           "API: ورودی نامعتبر Preflight خطای قراردادی می‌دهد", bad_pf)
        no_note = c.post(
            "/api/execution/offerings/%s/reservation/API-1/state" % oid,
            json={"state": "UNKNOWN_HOLD"}).json()
        ck(no_note.get("status") == "error" and no_note.get("code") == "NOTE_REQUIRED",
           "API: UNKNOWN_HOLD بی‌شاهد رد می‌شود", no_note)
        hold = c.post(
            "/api/execution/offerings/%s/reservation/API-1/state" % oid,
            json={"state": "UNKNOWN_HOLD", "note": "timeout"}).json()
        ck(hold.get("status") == "success", "API: UNKNOWN_HOLD با شاهد ثبت می‌شود", hold)
        revive = c.post(
            "/api/execution/offerings/%s/reservation/API-1/state" % oid,
            json={"state": "RESERVED", "note": "revive"}).json()
        ck(revive.get("status") == "error"
           and revive.get("code") == "INVALID_TRANSITION",
           "API: UNKNOWN_HOLD به RESERVED برنمی‌گردد", revive)

        c2body = dict(base, symbol="APIC", isin="IRO1APIC0004")
        jc = c.post("/api/execution/offerings", json=c2body).json()
        oid2 = str(jc.get("offering", {}).get("id") or "")
        c2 = TestClient(app, raise_server_exceptions=False)
        got: list[dict] = []
        def _api_plan(intent: str) -> None:
            cli = c if intent.endswith("1") else c2
            try:
                got.append(cli.post("/api/execution/offerings/plan", json={
                    "plans": [{"offering_id": oid2, "intent_id": intent,
                               "price": 105, "quantity": 10}],
                    "max_age_s": 3600}).json())
            except Exception as e:               # noqa: BLE001
                got.append({"status": "exception", "detail": type(e).__name__})
        th = [threading.Thread(target=_api_plan, args=("C-1",)),
              threading.Thread(target=_api_plan, args=("C-2",))]
        for t in th:
            t.start()
        for t in th:
            t.join()
        c2.close()
        states = [str((x.get("decisions") or [{}])[0].get("state"))
                  for x in got if x.get("status") == "success"]
        ck(got and all(x.get("status") == "success" for x in got)
           and states.count("RESERVED") == 1,
           "API: دو درخواست هم‌زمان یک عرضه فقط یک رزرو می‌سازند", got)

        low = c.post("/api/execution/offerings/budget", json={
            "total_cap": 500, "cash_reserve": 0, "max_per_offering": 500}).json()
        ck(low.get("status") == "error" and low.get("code") == "BUDGET_BELOW_RESERVED",
           "API: کاهش بودجه زیرِ رزرو رد می‌شود", low)
    finally:
        c.close()
        EX._OFFERING_STORE = old_store
        if old_env is None:
            os.environ.pop("BORS_OFFERINGS_DB", None)
        else:
            os.environ["BORS_OFFERINGS_DB"] = old_env


def main() -> int:
    at = O.now_ms()
    print("── ۱) رکورد عرضه و provenance ──")
    st, _ = new_store()
    a = make(st)
    ck(a.status == "VERIFIED" and a.method == "BOOK_BUILDING", "رکورد تأییدشده ذخیره شد")
    ck(a.timing_relevance == "NOT_PROVEN", "BOOK_BUILDING مزیتِ زمانی ادعا نمی‌کند")
    ck(st.get_by_identity("TESTA", "IRO1TEST0001") is not None, "هویت symbol+ISIN یکتاست")
    b = make(st, "TESTB", "IRO1TEST0002", method="FIRST_LISTING_QUEUE")
    ck(b.timing_relevance == "QUEUE_SENSITIVE_UNPROVEN", "صف حساس گزارش می‌شود، نه تضمین")
    u = make(st, "TESTU", "IRO1TEST0003", method="UNKNOWN")
    rep_u = O.preflight(u, at=at, price=105, quantity=10, max_age_s=3600)
    ck(not rep_u["ok"] and rep_u["checks"]["method"]["state"] == "FAIL",
       "روشِ UNKNOWN قابل تخصیص نیست")
    uns = make(st, "TESTN", "IRO1TEST0004", source="", unverified=True)
    ck(uns.status == "UNVERIFIED", "بی‌منبع/تأیید ⇒ UNVERIFIED")
    rep_n = O.preflight(uns, at=at, price=105, quantity=10, max_age_s=3600)
    ck(not rep_n["ok"] and rep_n["checks"]["source_verified"]["state"] == "FAIL",
       "UNVERIFIED در Preflight رد می‌شود")
    ck(raises("INVALID_PROVENANCE", lambda: make(
        st, "TESTNS", "IRO1TEST0010", source_url="")),
       "تأیید بدونِ نشانی منبع رد می‌شود")
    ck(raises("INVALID_SOURCE_URL", lambda: make(
        st, "TESTBU", "IRO1TEST0011", source_url="file:///secret.txt")),
       "نشانی منبعِ غیر http(s) رد می‌شود")
    ck(raises("INVALID_TIME", lambda: make(
        st, "TESTFT", "IRO1TEST0012", verified=at + 600_000,
        data_as_of=at + 600_000)),
       "زمانِ تأییدِ آینده رد می‌شود")
    ck(raises("INVALID_PROVENANCE", lambda: make(
        st, "TESTORD", "IRO1TEST0013", verified=at, data_as_of=at + 60_000)),
       "data_as_of جدیدتر از verified_at رد می‌شود")
    ck(raises("INVALID_FEE", lambda: make(
        st, "TESTNEG", "IRO1TEST0014", fee=-0.01)),
       "نرخ کارمزدِ منفی رد می‌شود")
    ck(raises("INVALID_RANGE", lambda: make(
        st, "TESTRNG", "IRO1TEST0015", pmin=120, pmax=100)),
       "دامنهٔ قیمتِ وارونه رد می‌شود")
    ck(raises("INVALID_WINDOW", lambda: make(
        st, "TESTWIN", "IRO1TEST0016", start=at + 3600_000, end=at)),
       "پنجرهٔ وارونه رد می‌شود")
    ck(raises("INVALID_RANGE", lambda: make(
        st, "TESTQ", "IRO1TEST0017", quota=-1)),
       "سهمیهٔ منفی رد می‌شود")
    ck(raises("INVALID_RANGE", lambda: make(
        st, "TESTQ2", "IRO1TEST0018", qmin=100, qmax=10)),
       "بازهٔ تعدادِ وارونه رد می‌شود")

    print("\n── ۲) Preflight قیمت/تعداد/سهمیه/کارمزد/کهنگی ──")
    ok = O.preflight(a, at=at, price=105, quantity=100, max_age_s=3600)
    ck(ok["ok"] and ok["amount"] is not None, "Preflight معتبر با مبلغ", ok.get("amount"))
    for label, kw, check in (
            ("قیمت خارج از دامنه", dict(price=200, quantity=10), "price"),
            ("تعداد بالای سهمیه", dict(price=105, quantity=600), "quota"),
            ("تعداد اعشاری", dict(price=105, quantity=10.5), "quantity"),
            ("قیمت صفر", dict(price=0, quantity=10), "price"),
            ("قیمت منفی", dict(price=-1, quantity=10), "price"),
            ("تعداد منفی", dict(price=105, quantity=-10), "quantity"),
            ("تعداد NaN", dict(price=105, quantity=float("nan")), "quantity"),
            ("قیمت بی‌کران", dict(price=float("inf"), quantity=10), "price")):
        try:
            r = O.preflight(a, at=at, max_age_s=3600, **kw)
            ck(not r["ok"] and r["checks"][check]["state"] == "FAIL",
               "Preflight ردِ %s" % label, r["checks"].get(check))
        except Exception as e:                   # noqa: BLE001
            ck(False, "Preflight ردِ %s (نباید exception بدهد)" % label,
               "%s: %s" % (type(e).__name__, e))
    stale = make(st, "TESTOLD", "IRO1TEST0005", data_as_of=at - 7_200_000)
    rs = O.preflight(stale, at=at, price=105, quantity=10, max_age_s=3600)
    ck(not rs["ok"] and rs["checks"]["data_fresh"]["state"] == "FAIL",
       "دادهٔ کهنه Preflight را می‌بندد")
    future = replace(a, data_as_of_ms=at + 60_000)
    rfut = O.preflight(future, at=at, price=105, quantity=10, max_age_s=3600)
    ck(not rfut["ok"] and rfut["checks"]["data_fresh"]["state"] == "FAIL",
       "دادهٔ با زمانِ آیندهٔ Preflight را می‌بندد")
    no_price_src = replace(a, price_source="")
    rps = O.preflight(no_price_src, at=at, price=105, quantity=10, max_age_s=3600)
    ck(not rps["ok"] and rps["checks"]["price_source"]["state"] == "FAIL",
       "نبودِ منبع قیمت Preflight را می‌بندد")
    nofee = make(st, "TESTFEE", "IRO1TEST0006", fee=None, fee_source="")
    rf = O.preflight(nofee, at=at, price=105, quantity=10, max_age_s=3600)
    ck(not rf["ok"] and rf["checks"]["fee"]["state"] == "FAIL",
       "نبودِ منبعِ کارمزد ⇒ BLOCKED")
    closed = make(st, "TESTC", "IRO1TEST0007", start=at - 7_200_000, end=at - 3_600_000)
    rc = O.preflight(closed, at=at, price=105, quantity=10, max_age_s=3600)
    ck(not rc["ok"] and rc["checks"]["window"]["state"] == "FAIL",
       "پنجرهٔ بسته Preflight را می‌بندد")

    print("\n── ۳) بودجه و رزرو ──")
    st, _ = new_store()
    a = make(st, "TESTA", "IRO1TEST0001", quota=500)
    b = make(st, "TESTB", "IRO1TEST0002", quota=500)
    try:
        st.set_capital(total_cap=10, cash_reserve=20, max_per_offering=5)
        ck(False, "ذخیرهٔ بیشتر از سقف باید رد شود")
    except O.OfferingsError as e:
        ck(e.code == "INVALID_BUDGET", "ذخیرهٔ نا‌معتبر رد می‌شود", e.code)
    cap = st.set_capital(total_cap=120_000, cash_reserve=10_000,
                         max_per_offering=100_000, priorities={a.id: 1, b.id: 2})
    ck(cap["version"] == 1 and cap["total_cap"] == 120_000, "سقف/اولویت‌ها ذخیره شد")
    p = st.plan([
        {"offering_id": b.id, "intent_id": "I-B", "price": 105, "quantity": 500},
        {"offering_id": a.id, "intent_id": "I-A", "price": 105, "quantity": 500},
    ], now=at, max_age_s=3600)
    ck(p["decisions"][0]["offering_id"] == a.id and p["decisions"][1]["offering_id"] == b.id,
       "اولویتِ A قبل از B رزرو می‌شود", p["decisions"])
    ck(all(d["state"] == "RESERVED" for d in p["decisions"]), "هر دو رزرو شدند")
    ck(abs(p["reserved_total"] - st.active_reserved()) < 1e-6, "جمع رزروها درست است")
    p2 = st.plan([{"offering_id": a.id, "intent_id": "I-A2", "price": 105, "quantity": 10}],
                 now=at, max_age_s=3600)
    ck(p2["decisions"][0]["state"] == "SKIPPED_BUDGET"
       and p2["decisions"][0]["reason"] == "OFFERING_ALREADY_RESERVED",
       "یک عرضه حداکثر یک رزرو فعال دارد", p2["decisions"])
    ck(st.set_reservation(a.id, "I-A", "UNKNOWN_HOLD", "timeout")["state"] == "UNKNOWN_HOLD",
       "UNKNOWN_HOLD ثبت می‌شود")
    ck(abs(st.active_reserved() - p["reserved_total"]) < 1e-6,
       "UNKNOWN_HOLD بودجه را نگه می‌دارد")
    st.set_reservation(a.id, "I-A", "UNKNOWN_HOLD", "cancel failed")
    _res = st.reservations(a.id)[0]
    ck(_res["state"] == "UNKNOWN_HOLD" and _res["note"] == "cancel failed",
       "شکستِ لغو ⇒ UNKNOWN_HOLD با همان دلیل", _res)
    p_hold = st.plan([{"offering_id": a.id, "intent_id": "I-A3",
                       "price": 105, "quantity": 10}], now=at, max_age_s=3600)
    ck(p_hold["decisions"][0]["state"] == "SKIPPED_BUDGET"
       and p_hold["decisions"][0]["reason"] == "OFFERING_ALREADY_RESERVED",
       "تا تعیین تکلیف UNKNOWN، رزرو/تلاش تازه ممنوع است", p_hold["decisions"])
    ck(st.set_reservation(a.id, "I-A", "RELEASED",
                          "evidence: not sent")["state"] == "RELEASED",
       "آزادسازی فقط با شاهد/دستور ثبت می‌شود")
    rel_retry = st.set_reservation(a.id, "I-A", "RELEASED", "retry")
    ck(rel_retry["state"] == "RELEASED" and rel_retry.get("unchanged") is True,
       "retry همان وضعیت رزرو را دوباره فعال نمی‌کند", rel_retry)
    ck(st.active_reserved() < p["reserved_total"], "آزادسازی بودجه را کم می‌کند")
    ck(raises("INVALID_TRANSITION",
              lambda: st.set_reservation(a.id, "I-A", "RESERVED", "revive")),
       "رزروِ آزادشده دوباره فعال نمی‌شود")
    reused = st.plan([{"offering_id": a.id, "intent_id": "I-A",
                       "price": 105, "quantity": 10}], now=at, max_age_s=3600)
    ck(reused["decisions"][0]["state"] == "BLOCKED"
       and reused["decisions"][0]["reason"] == "INTENT_ALREADY_USED",
       "intentِ مصرف‌شده دوباره رزرو نمی‌کند و خطا نمی‌دهد", reused["decisions"])
    ck(raises("INVALID_TRANSITION",
              lambda: st.set_reservation(a.id, "I-A", "UNKNOWN_HOLD", "revive")),
       "UNKNOWN_HOLD از رزروِ بسته مجاز نیست")
    p_after = st.plan([{"offering_id": a.id, "intent_id": "I-A4",
                        "price": 105, "quantity": 10}], now=at, max_age_s=3600)
    ck(p_after["decisions"][0]["state"] == "RESERVED",
       "پس از آزادسازیِ مستند، رزرو تازه مجاز است")
    ck(raises("NOTE_REQUIRED",
              lambda: st.set_reservation(a.id, "I-A4", "RELEASED")),
       "آزادسازی بدون شاهد رد می‌شود")
    ck(raises("INVALID_STATE",
              lambda: st.set_reservation(a.id, "I-A4", "SKIPPED_BUDGET", "x")),
       "SKIPPED_BUDGET وضعیتِ رزرو نیست")
    st.set_reservation(a.id, "I-A4", "UNKNOWN_HOLD", "timeout")
    ck(raises("INVALID_TRANSITION",
              lambda: st.set_reservation(a.id, "I-A4", "RESERVED", "clear unknown")),
       "UNKNOWN_HOLD بدون شاهد به RESERVED برنمی‌گردد")
    ck(st.set_reservation(a.id, "I-A4", "COMMITTED", "reconciled")["state"] == "COMMITTED",
       "UNKNOWN_HOLD با شاهد به COMMITTED می‌رود")
    ck(st.set_reservation(a.id, "I-A4", "RELEASED", "order not found")["state"] == "RELEASED",
       "COMMITTED با شاهد آزاد می‌شود")
    active_now = st.active_reserved()
    new_cap = max(0.01, active_now - 1)
    ck(raises("BUDGET_BELOW_RESERVED", lambda: st.set_capital(
        total_cap=new_cap, cash_reserve=0, max_per_offering=new_cap)),
       "کاهشِ سقف به زیرِ رزروهایِ فعال رد می‌شود", active_now)
    ck(raises("BUDGET_BELOW_RESERVED", lambda: st.set_capital(
        total_cap=120_000, cash_reserve=10_000, max_per_offering=1_000)),
       "کاهشِ سقف هر عرضه به زیرِ بزرگ‌ترین رزرو رد می‌شود", active_now)

    print("\n── ۴) کمبود بودجه/هم‌زمانی ──")
    st, _ = new_store()
    a = make(st, "TESTA", "IRO1TEST0001", quota=500)
    b = make(st, "TESTB", "IRO1TEST0002", quota=500)
    st.set_capital(total_cap=60_000, cash_reserve=0, max_per_offering=60_000,
                   priorities={a.id: 1, b.id: 2})
    p = st.plan([
        {"offering_id": a.id, "intent_id": "I-A", "price": 105, "quantity": 500},
        {"offering_id": b.id, "intent_id": "I-B", "price": 105, "quantity": 500},
    ], now=at, max_age_s=3600)
    ck(p["decisions"][0]["state"] == "RESERVED"
       and p["decisions"][1]["state"] == "SKIPPED_BUDGET",
       "کمبود بودجه ⇒ SKIPPED_BUDGET برایِ کم‌اولویت", p["decisions"])
    ck(st.active_reserved() <= 60_000 + 1e-6, "رزرو از سقف عبور نمی‌کند")
    # دو plan هم‌زمان روی دو عرضهٔ تازه با سقفِ یک‌نفره
    st, _ = new_store()
    c = make(st, "TESTC", "IRO1TEST0003", quota=500)
    d = make(st, "TESTD", "IRO1TEST0004", quota=500)
    st.set_capital(total_cap=60_000, cash_reserve=0, max_per_offering=60_000,
                   priorities={c.id: 1, d.id: 2})
    results = []
    def _plan(oid, intent):
        try:
            results.append(st.plan([{"offering_id": oid, "intent_id": intent,
                                     "price": 105, "quantity": 500}],
                                   now=at, max_age_s=3600))
        except Exception as e:                   # noqa: BLE001
            results.append({"error": type(e).__name__})
    ts = [threading.Thread(target=_plan, args=(c.id, "I-C")),
          threading.Thread(target=_plan, args=(d.id, "I-D"))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    reserved = st.active_reserved()
    ck(reserved <= 60_000 + 1e-6, "دو plan هم‌زمان از سقف عبور نمی‌کنند", reserved)
    ck(sum(1 for r in results if "error" not in r) >= 1, "حداقل یک plan موفق", results)

    # دو worker رویِ همان عرضه: فقط یکی رزرو می‌کند.
    st, _ = new_store()
    e = make(st, "TESTE", "IRO1TEST0005", quota=500)
    st.set_capital(total_cap=60_000, cash_reserve=0, max_per_offering=60_000)
    same = []
    def _same(intent):
        try:
            same.append(st.plan([{"offering_id": e.id, "intent_id": intent,
                                  "price": 105, "quantity": 500}],
                                now=at, max_age_s=3600)["decisions"][0]["state"])
        except Exception as ex:                  # noqa: BLE001
            same.append("ERR:%s" % type(ex).__name__)
    tt = [threading.Thread(target=_same, args=("S1",)),
          threading.Thread(target=_same, args=("S2",))]
    for t in tt:
        t.start()
    for t in tt:
        t.join()
    ck(same.count("RESERVED") == 1 and len(st.reservations(e.id)) == 1,
       "دو worker یک عرضه: فقط یک رزرو", same)
    ck(abs(st.active_reserved() - (105 * 500 * 1.0012)) < 0.05,
       "مبلغِ رزروِ یگانه درست است", st.active_reserved())

    # اولویت صفر نباید به ۱۰۰ تبدیل شود.
    st, _ = new_store()
    lo = make(st, "TESTLO", "IRO1TEST0006", quota=500)
    hi = make(st, "TESTHI", "IRO1TEST0007", quota=500)
    st.set_capital(total_cap=60_000, cash_reserve=0, max_per_offering=60_000,
                   priorities={lo.id: 0, hi.id: 1})
    pp = st.plan([{"offering_id": hi.id, "intent_id": "H", "price": 105, "quantity": 500},
                  {"offering_id": lo.id, "intent_id": "L", "price": 105, "quantity": 500}],
                 now=at, max_age_s=3600)
    ck(pp["decisions"][0]["offering_id"] == lo.id,
       "اولویت ۰ معتبر است و قبل از ۱ می‌آید", pp["decisions"])
    p_empty = st.plan([{"offering_id": lo.id, "intent_id": "",
                        "price": 105, "quantity": 10}], now=at, max_age_s=3600)
    ck(p_empty["decisions"][0]["reason"] == "INTENT_REQUIRED",
       "intent خالی رزرو نمی‌کند", p_empty["decisions"])
    p_neg = st.plan([{"offering_id": lo.id, "intent_id": "N",
                      "price": -105, "quantity": 10}], now=at, max_age_s=3600)
    ck(p_neg["decisions"][0]["state"] == "BLOCKED",
       "قیمت منفی حتی با دامنهٔ باز رزرو نمی‌شود", p_neg["decisions"])
    p_nan = st.plan([{"offering_id": lo.id, "intent_id": "NN",
                      "price": 105, "quantity": float("nan")}],
                    now=at, max_age_s=3600)
    ck(p_nan["decisions"][0]["state"] == "BLOCKED",
       "تعداد NaN رزرو نمی‌سازد و exception نمی‌دهد", p_nan["decisions"])

    print("\n── ۵) سناریوهای چندعرضه ──")
    st, _ = new_store()
    a = make(st, "TESTA", "IRO1TEST0001", quota=300)
    b = make(st, "TESTB", "IRO1TEST0002", method="UNKNOWN")
    c = make(st, "TESTC", "IRO1TEST0003", data_as_of=at - 8_000_000)
    st.set_capital(total_cap=100_000, cash_reserve=0, max_per_offering=100_000)
    p = st.plan([
        {"offering_id": a.id, "intent_id": "I-A", "price": 105, "quantity": 500},
        {"offering_id": b.id, "intent_id": "I-B", "price": 105, "quantity": 10},
        {"offering_id": c.id, "intent_id": "I-C", "price": 105, "quantity": 10},
    ], now=at, max_age_s=3600)
    states = {d["offering_id"]: d["state"] for d in p["decisions"]}
    ck(states[a.id] == "BLOCKED", "درخواست بالای سهمیه ⇒ BLOCKED (تخصیص جزئی حدس زده نمی‌شود)")
    ck(states[b.id] == "BLOCKED", "روش UNKNOWN ⇒ BLOCKED")
    ck(states[c.id] == "BLOCKED", "دادهٔ کهنه ⇒ BLOCKED")
    ck(st.active_reserved() == 0, "هیچ رزروی برایِ موارد مسدود ساخته نشد")
    p_part = st.plan([{"offering_id": a.id, "intent_id": "I-A-PART",
                       "price": 105, "quantity": 300}], now=at, max_age_s=3600)
    ck(p_part["decisions"][0]["state"] == "RESERVED",
       "تخصیصِ جزئی فقط با تعدادِ صریح (سهمیه) رزرو می‌شود، نه حدس")

    print("\n── ۶) Timing ──")
    st, _ = new_store()
    for i in range(4):
        st.record_timing(adapter="direct_api", method="BOOK_BUILDING",
                         value_ms=10 + i, source="unit-test")
    s4 = st.timing_stats(adapter="direct_api", method="BOOK_BUILDING")
    ck(s4["confidence"] == "INSUFFICIENT" and s4["p95"] is None,
       "نمونهٔ کم ⇒ INSUFFICIENT و p95 None")
    for i in range(21):
        st.record_timing(adapter="direct_api", method="BOOK_BUILDING",
                         value_ms=10 + i % 7, source="unit-test")
    s25 = st.timing_stats(adapter="direct_api", method="BOOK_BUILDING")
    ck(s25["n"] == 25 and s25["p95"] is not None and s25["confidence"] == "MEDIUM",
       "۲۵ نمونه ⇒ p95 و MEDIUM", s25)
    sug = O.timing_suggestion(s25, target_ms=at + 60_000, method="BOOK_BUILDING")
    ck(sug["suggested_send_wall_ms"] is not None and sug["acceptance_time_observed"] is False,
       "پیشنهاد زمان از RTT است، نه پذیرش")
    ck(sug["timing_relevance"] == "NOT_PROVEN", "BOOK_BUILDING مزیتِ زمانی ندارد")
    try:
        st.record_timing(adapter="direct_api", method="BOOK_BUILDING",
                         value_ms=1, source="")
        ck(False, "نمونهٔ بی‌منبع باید رد شود")
    except O.OfferingsError as e:
        ck(e.code == "SOURCE_REQUIRED", "نمونهٔ زمان بی‌منبع رد می‌شود", e.code)
    q = st.timing_stats(adapter="direct_api", method="FIRST_LISTING_QUEUE")
    sq = O.timing_suggestion(q, target_ms=at, method="FIRST_LISTING_QUEUE")
    ck(sq["timing_relevance"] == "QUEUE_SENSITIVE_UNPROVEN"
       and "تضمین" in sq["timing_note"], "صف: حساس ولی بدون تضمین", sq["timing_note"])
    st.record_timing(adapter="direct_api", method="BOOK_BUILDING", value_ms=7,
                     source="unit-test", phase="preparation")
    sp = st.timing_stats(adapter="direct_api", method="BOOK_BUILDING",
                         phase="preparation")
    ck(sp["source"] == "preparation" and sp["phase"] == "preparation"
       and sp["acceptance_time_observed"] is False,
       "فازِ آماده‌سازی به‌جای RTT برچسب می‌خورد", sp)
    ck(raises("INVALID_ADAPTER", lambda: st.record_timing(
        adapter="", method="BOOK_BUILDING", value_ms=1, source="x")),
       "نمونهٔ بی‌آداپتور رد می‌شود")
    ck(T.percentile([1, 2, 3, 4], 50) == 2 and T.percentile([1, 2, 3, 4], 25) == 1,
       "percentile روشِ nearest-rank است", (T.percentile([1, 2, 3, 4], 50),
                                             T.percentile([1, 2, 3, 4], 25)))
    empty_sug = O.timing_suggestion(O.OfferingStore(os.path.join(
        tempfile.mkdtemp(prefix="offer_timing_"), "x.db")).timing_stats(
            adapter="x", method="BOOK_BUILDING"), target_ms=at, method="BOOK_BUILDING")
    ck(empty_sug["suggested_send_wall_ms"] is None,
       "بی‌نمونه، زمان پیشنهادی ساخته نمی‌شود", empty_sug)

    print("\n── ۶.۵) کشفِ CODAL (فقط کاندید) ──")
    import sqlite3 as _sq
    db = os.path.join(tempfile.mkdtemp(prefix="codal_discover_"), "market.db")
    con = _sq.connect(db)
    con.execute("CREATE TABLE codal_notices(symbol TEXT, company_name TEXT, title TEXT, "
                "publish_date TEXT, url TEXT)")
    con.execute("INSERT INTO codal_notices VALUES(?,?,?,?,?)",
                ("TESTX", "شرکت آزمون", "اطلاعیه عرضه اولیه سهام", "1405/07/01", "https://codal.ir/x"))
    con.commit(); con.close()
    cand = O.discover_codal(db, limit=10)
    ck(len(cand) == 1 and cand[0]["structured"] is False
       and cand[0]["status"] == "UNVERIFIED",
       "کشفِ CODAL فقط کاندیدِ UNVERIFIED می‌دهد، نه رکورد ساختگی", cand)
    try:
        O.discover_codal(os.path.join(os.path.dirname(db), "missing.db"))
        ck(False, "نبودِ منبع کشف باید خطا بدهد")
    except O.OfferingsError as e:
        ck(e.code == "DISCOVERY_UNAVAILABLE", "نبودِ منبع کشف صریح است", e.code)

    print("\n── ۷) پایداری/نسخه ──")
    stp, _ = new_store()
    op = make(stp, "TESTP", "IRO1TEST0009")
    stp.set_capital(total_cap=500_000, cash_reserve=0, max_per_offering=500_000)
    p_res = stp.plan([{"offering_id": op.id, "intent_id": "P-1",
                       "price": 105, "quantity": 10}], now=O.now_ms(), max_age_s=3600)
    ck(p_res["decisions"][0]["state"] == "RESERVED", "رزروِ پیش از restart ساخته شد")
    st2 = O.OfferingStore(stp.path)
    ck(st2.get(op.id) is not None
       and st2.get_by_identity("TESTP", "IRO1TEST0009") is not None,
       "بازگشایی store رکورد عرضه را می‌بیند")
    ck(st2.capital()["total_cap"] == 500_000 and st2.capital()["version"] == 1,
       "تنظیم سرمایه/نسخه در همان DB می‌ماند")
    ck(st2.active_reserved() == p_res["reserved_total"]
       and st2.reservations(op.id)[0]["intent_id"] == "P-1"
       and st2.reservations(op.id)[0]["state"] == "RESERVED",
       "رزرو بینِ restart حفظ می‌شود و خودکار آزاد نمی‌شود")

    print("\n── ۸) قراردادِ HTTP و اتمیک‌بودن از مسیرِ API ──")
    api_checks()

    print("\n%d passed / %d failed" % (PASS, FAIL))
    if FAILED:
        print("FAILED: " + ", ".join(FAILED))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
