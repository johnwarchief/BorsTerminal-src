#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""گاردِ Round 7 — cockpit وضعیت/Preflight/Mock، بدونِ شبکه یا سفارشِ واقعی."""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import execution_cockpit as C  # noqa: E402
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


def store():
    d = tempfile.mkdtemp(prefix="cockpit_guard_")
    return C.CockpitStore(os.path.join(d, "cockpit.db")), d


def offering():
    d = tempfile.mkdtemp(prefix="cockpit_offer_")
    st = O.OfferingStore(os.path.join(d, "offerings.db"))
    at = O.now_ms()
    rec = st.upsert(
        symbol="COCKPIT", isin="IRO1COCK0001", method="BOOK_BUILDING",
        start_ms=at - 3_600_000, end_ms=at + 3_600_000,
        price_min=100, price_max=110, price_source="fixture", price_step=1.0,
        min_qty=1, max_qty=1000, per_code_quota=500, fee_rate=0.0012,
        fee_source="fixture", source="fixture", source_url="https://example.test/cockpit",
        verified_at_ms=at, data_as_of_ms=at)
    return st, rec


def base_status(rec, *, reservations=(), old=False):
    pub = rec.public()
    if old:
        pub["data_as_of_ms"] = O.now_ms() - 7_200_000
    db = {k: {"readable": True, "mtime_ms": O.now_ms()} for k in
          ("market", "offerings", "schedules", "cockpit")}
    return C.build_status(
        app_version="1.0.95", offerings=[pub],
        capital={"total_cap": 100_000, "cash_reserve": 0, "max_per_offering": 100_000},
        reserved=0, reservations=reservations,
        readiness={"blockers": [{"code": "CALENDAR"}, {"code": "ORDER_CONTRACT"}]},
        host={"healthy": False},
        execution={"adapter": "mock", "live_enabled": False,
                   "session": {"proven": False}},
        db=db)


def main() -> int:
    st, _ = store()
    print("── ۱) سناریوهای Mock ──")
    expected = {
        "success": "PASS", "stale_data": "BLOCKED", "missing_source": "BLOCKED",
        "insufficient_budget": "BLOCKED", "unverified_offering": "BLOCKED",
        "backend_error": "FAIL", "duplicate_request": "PASS",
        "unknown_result": "UNKNOWN", "unknown_hold": "UNKNOWN_HOLD",
        "restart_recovery": "INTERRUPTED", "host_error": "BLOCKED",
    }
    for scenario, want in expected.items():
        run = C.run_scenario(st, scenario, step_delay_s=0)
        ck(run.get("status") == want, "سناریو %s → %s" % (scenario, want), run.get("status"))
        ck(run.get("mode") == "MOCK" and run.get("summary", {}).get("order_sent") is False
           and run.get("summary", {}).get("live_send") is False,
           "سناریو %s خروجیِ Mock و بی‌ارسال است" % scenario, run.get("summary"))
        ck(len(run.get("events") or []) >= 2, "سناریو %s رویداد دارد" % scenario)
    ck(C.SCENARIOS and len(C.SCENARIO_INFO) == 11, "فهرست سناریوها کامل است")

    print("\n── ۲) UNKNOWN و جلوگیری از retry ──")
    u = C.run_scenario(st, "unknown_result", step_delay_s=0)
    ck(u.get("summary", {}).get("retry_performed") is False
       and any(e["phase"] == "retry_suppressed" and e["status"] == "PASS"
               for e in u.get("events", [])),
       "UNKNOWN هیچ retry خودکاری نمی‌سازد", u.get("events"))
    h = C.run_scenario(st, "unknown_hold", step_delay_s=0)
    ck(h.get("status") == "UNKNOWN_HOLD"
       and h.get("summary", {}).get("retry_performed") is False,
       "UNKNOWN_HOLD گروگان می‌ماند و retry ندارد", h.get("summary"))

    print("\n── ۳) stop و restart ──")
    result: list[dict] = []
    th = threading.Thread(target=lambda: result.append(
        C.run_scenario(st, "success", step_delay_s=0.05)))
    th.start()
    rid = ""
    deadline = time.time() + 2
    while time.time() < deadline and not rid:
        runs = st.runs(10)
        running = [r for r in runs if str(r.get("status")) == "RUNNING"]
        rid = str(running[0]["id"]) if running else ""
        if not rid:
            time.sleep(0.005)
    stopped = st.stop(rid) if rid else {}
    th.join(5)
    ck(bool(rid) and stopped.get("status") in ("STOPPING", "STOPPED")
       and result and result[0].get("status") == "STOPPED",
       "توقف آزمون Mock ثبت می‌شود", (stopped, result))
    st2, d2 = store()
    pending = st2.start_run("success")
    st3 = C.CockpitStore(st2.path)
    recovered = st3.run(pending["id"]) or {}
    ck(recovered.get("status") == "INTERRUPTED"
       and any(e["phase"] == "recovery" for e in recovered.get("events", [])),
       "restart اجرای RUNNING را INTERRUPTED می‌کند، نه موفق", recovered)

    print("\n── ۴) وضعیت و Gateها ──")
    offer_st, rec = offering()
    good = base_status(rec)
    gates = {g["id"]: g for g in good["gates"]}
    ck(good["live_ready"] is False and good["live_send"] is False,
       "وضعیت live_ready=false را نگه می‌دارد")
    ck(gates["offering"]["status"] == "PASS"
       and gates["terms"]["status"] == "PASS"
       and gates["data_fresh"]["status"] == "PASS",
       "عرضهٔ کامل در Gateها PASS است", gates)
    ck(gates["browser_host"]["status"] == "BLOCKED"
       and gates["buying_power"]["status"] == "BLOCKED"
       and gates["live_ready"]["status"] == "BLOCKED",
       "host/قدرت خرید/Live مسدود می‌مانند", gates)
    stale = base_status(rec, old=True)
    sg = {g["id"]: g for g in stale["gates"]}
    ck(sg["data_fresh"]["status"] == "FAIL", "دادهٔ کهنه data_fresh را FAIL می‌کند", sg["data_fresh"])
    hold = base_status(rec, reservations=[{"state": "UNKNOWN_HOLD"}])
    hg = {g["id"]: g for g in hold["gates"]}
    ck(hg["unknown_hold"]["status"] == "FAIL", "UNKNOWN_HOLD در Gate قرمز است", hg["unknown_hold"])

    print("\n── ۵) Preflight مرکز ──")
    pub = rec.public()
    pf = C.preflight_snapshot(offering=pub, price=105, quantity=10,
                              status=good, max_age_s=3600)
    ck(pf.get("preflight", {}).get("ok") is True,
       "Preflight با قیمت/تعداد/گام معتبر PASS است", pf.get("preflight"))
    bad = C.preflight_snapshot(offering=pub, price=105.5, quantity=10,
                               status=good, max_age_s=3600)
    ck(bad.get("preflight", {}).get("ok") is False,
       "قیمت ناهم‌تراز با گام در مرکز Preflight رد می‌شود", bad.get("preflight"))
    poor = C.preflight_snapshot(
        offering=pub, price=105, quantity=10, status=good, max_age_s=3600,
        capital={"total_cap": 1_000, "cash_reserve": 0, "max_per_offering": 1_000},
        reserved=0)
    ck(poor.get("preflight", {}).get("ok") is False,
       "بودجهٔ ناکافی در مرکز Preflight رد می‌شود", poor.get("preflight"))
    none = C.preflight_snapshot(offering=None, price=None, quantity=None,
                                status=good)
    ck(none.get("preflight", {}).get("state") == "NOT_RUN",
       "بی‌عرضه/بی‌قیمت Preflight NOT_RUN می‌ماند", none.get("preflight"))

    print("\n── ۶) گزارش/redaction/ماندگاری ──")
    leaked = C.build_report(status={"status": "success", "token": "Bearer abcdefghijklmnop",
                                    "nested": {"cookie": "secret-value"}},
                            runs=[{"id": "r1", "session": "top-secret"}])
    ck("Bearer abcdefghijklmnop" not in str(leaked)
       and "secret-value" not in str(leaked)
       and "top-secret" not in str(leaked),
       "گزارشِ تشخیصی مقدارِ حساس را ماسک می‌کند", leaked)
    st4 = C.CockpitStore(st.path)
    ck(any(r["scenario"] == "success" for r in st4.runs(20)),
       "runها پس از بازگشایی DB باقی می‌مانند")

    print("\n── ۷) قرارداد HTTP (TestClient، بدونِ شبکهٔ بیرونی) ──")
    import api.execution as EX
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    tmp = tempfile.mkdtemp(prefix="cockpit_api_")
    old_env = {k: os.environ.get(k) for k in
               ("BORS_OFFERINGS_DB", "BORS_COCKPIT_DB", "BORS_SCHEDULE_DB")}
    old_stores = (EX._OFFERING_STORE, EX._COCKPIT_STORE, EX._SCHEDULE_STORE)
    os.environ["BORS_OFFERINGS_DB"] = os.path.join(tmp, "offerings.db")
    os.environ["BORS_COCKPIT_DB"] = os.path.join(tmp, "cockpit.db")
    os.environ["BORS_SCHEDULE_DB"] = os.path.join(tmp, "schedules.db")
    EX._OFFERING_STORE = None
    EX._COCKPIT_STORE = None
    EX._SCHEDULE_STORE = None
    app = FastAPI()
    app.include_router(EX.router)
    c = TestClient(app, raise_server_exceptions=False)
    try:
        r = c.get("/api/execution/cockpit/status").json()
        ck(r.get("status") == "success" and r.get("live_ready") is False,
           "API وضعیت cockpit", r.get("code"))
        r = c.get("/api/execution/cockpit/runs?limit=5").json()
        ck(r.get("status") == "success" and len(r.get("scenarios") or []) == 11,
           "API فهرست run/سناریو", r.get("code"))
        rr = c.post("/api/execution/cockpit/runs", json={"scenario": "success"}).json()
        rid = str(rr.get("run", {}).get("id") or "")
        ck(rr.get("status") == "success"
           and rr.get("run", {}).get("status") in ("RUNNING", "PASS")
           and rr.get("live_send") is False,
           "API شروع اجرای Mock", rr.get("code"))
        detail = {}
        deadline = time.time() + 10
        while time.time() < deadline:
            detail = c.get("/api/execution/cockpit/runs/%s" % rid).json()
            if detail.get("run", {}).get("status") not in ("RUNNING", "STOPPING"):
                break
            time.sleep(0.1)
        ck(detail.get("status") == "success"
           and detail.get("run", {}).get("status") == "PASS"
           and len(detail.get("run", {}).get("events") or []) > 0,
           "API جزئیات/رویدادهای run پس از پایان", detail.get("run", {}).get("status"))
        stopped = c.post("/api/execution/cockpit/runs/%s/stop" % rid).json()
        ck(stopped.get("status") == "success", "API توقف/وضعیت run", stopped)
        sr = c.post("/api/execution/cockpit/runs",
                    json={"scenario": "success"}).json().get("run", {})
        srid = str(sr.get("id") or "")
        stop_now = c.post("/api/execution/cockpit/runs/%s/stop" % srid).json()
        stop_detail = {}
        deadline = time.time() + 8
        while time.time() < deadline:
            stop_detail = c.get("/api/execution/cockpit/runs/%s" % srid).json()
            if stop_detail.get("run", {}).get("status") != "RUNNING":
                break
            time.sleep(0.05)
        ck(stop_now.get("status") == "success"
           and stop_detail.get("run", {}).get("status") == "STOPPED",
           "API توقفِ اجرای در حال اجرا", stop_detail.get("run", {}).get("status"))
        rp = c.get("/api/execution/cockpit/report").json()
        ck(rp.get("status") == "success" and rp.get("mode") == "MOCK"
           and rp.get("live_ready") is False and rp.get("secrets_stored") is False,
           "API گزارشِ تشخیصی", rp.get("code"))
        now = O.now_ms()
        created = c.post("/api/execution/offerings", json={
            "symbol": "APICOCK", "isin": "IRO1APIC0001", "method": "BOOK_BUILDING",
            "start_ms": now - 3600_000, "end_ms": now + 3600_000,
            "price_min": 100, "price_max": 110, "price_source": "fixture",
            "price_step": 1, "min_qty": 1, "max_qty": 1000, "per_code_quota": 500,
            "fee_rate": 0.0012, "fee_source": "fixture", "source": "fixture",
            "source_url": "https://example.test/api-cockpit", "verified_at_ms": now,
            "data_as_of_ms": now - 1000}).json()
        oid = created.get("offering", {}).get("id")
        c.post("/api/execution/offerings/budget", json={
            "total_cap": 100_000, "cash_reserve": 0, "max_per_offering": 100_000})
        pf = c.post("/api/execution/cockpit/preflight", json={
            "offering_id": oid, "price": 105, "quantity": 10}).json()
        ck(pf.get("status") == "success" and pf.get("preflight", {}).get("ok") is True,
           "API Preflight مرکز", pf.get("code"))
    finally:
        c.close()
        EX._OFFERING_STORE, EX._COCKPIT_STORE, EX._SCHEDULE_STORE = old_stores
        for k, v in old_env.items():
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
