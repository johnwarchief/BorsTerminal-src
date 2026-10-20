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
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import execution_offerings as O  # noqa: E402

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


def make(store, sym="TESTA", isin="IRO1TEST0001", *, method="BOOK_BUILDING",
         start=None, end=None, pmin=100.0, pmax=110.0, qmin=1.0, qmax=1000.0,
         quota=500.0, fee=0.0012, source="unit-test", verified=None,
         data_as_of=None, price_source="unit-test", fee_source="unit-test"):
    at = O.now_ms()
    return store.upsert(
        symbol=sym, isin=isin, method=method, market="test",
        start_ms=start if start is not None else at - 3600_000,
        end_ms=end if end is not None else at + 3600_000,
        price_min=pmin, price_max=pmax, price_source=price_source,
        min_qty=qmin, max_qty=qmax, per_code_quota=quota,
        fee_rate=fee, fee_source=fee_source, source=source,
        verified_at_ms=verified if verified is not None else at,
        data_as_of_ms=data_as_of if data_as_of is not None else at)


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
    uns = make(st, "TESTN", "IRO1TEST0004", source="")
    ck(uns.status == "UNVERIFIED", "بی‌منبع/تأیید ⇒ UNVERIFIED")
    rep_n = O.preflight(uns, at=at, price=105, quantity=10, max_age_s=3600)
    ck(not rep_n["ok"] and rep_n["checks"]["source_verified"]["state"] == "FAIL",
       "UNVERIFIED در Preflight رد می‌شود")

    print("\n── ۲) Preflight قیمت/تعداد/سهمیه/کارمزد/کهنگی ──")
    ok = O.preflight(a, at=at, price=105, quantity=100, max_age_s=3600)
    ck(ok["ok"] and ok["amount"] is not None, "Preflight معتبر با مبلغ", ok.get("amount"))
    for label, kw, check in (
            ("قیمت خارج از دامنه", dict(price=200, quantity=10), "price"),
            ("تعداد بالای سهمیه", dict(price=105, quantity=600), "quota"),
            ("تعداد اعشاری", dict(price=105, quantity=10.5), "quantity"),
            ("قیمت صفر", dict(price=0, quantity=10), "price")):
        r = O.preflight(a, at=at, max_age_s=3600, **kw)
        ck(not r["ok"] and r["checks"][check]["state"] == "FAIL",
           "Preflight ردِ %s" % label, r["checks"].get(check))
    stale = make(st, "TESTOLD", "IRO1TEST0005", data_as_of=at - 7_200_000)
    rs = O.preflight(stale, at=at, price=105, quantity=10, max_age_s=3600)
    ck(not rs["ok"] and rs["checks"]["data_fresh"]["state"] == "FAIL",
       "دادهٔ کهنه Preflight را می‌بندد")
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
    ck(st.set_reservation(a.id, "I-A", "RELEASED", "evidence: not sent")["state"] == "RELEASED",
       "آزادسازی فقط با شاهد/دستور ثبت می‌شود")
    ck(st.active_reserved() < p["reserved_total"], "آزادسازی بودجه را کم می‌کند")
    p_after = st.plan([{"offering_id": a.id, "intent_id": "I-A4",
                        "price": 105, "quantity": 10}], now=at, max_age_s=3600)
    ck(p_after["decisions"][0]["state"] == "RESERVED",
       "پس از آزادسازیِ مستند، رزرو تازه مجاز است")

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
    st2 = O.OfferingStore(stp.path)
    ck(st2.get(op.id) is not None
       and st2.get_by_identity("TESTP", "IRO1TEST0009") is not None,
       "بازگشایی store رکورد عرضه را می‌بیند")
    ck(st2.capital()["total_cap"] == 500_000 and st2.capital()["version"] == 1,
       "تنظیم سرمایه/نسخه در همان DB می‌ماند")

    print("\n%d passed / %d failed" % (PASS, FAIL))
    if FAILED:
        print("FAILED: " + ", ".join(FAILED))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
