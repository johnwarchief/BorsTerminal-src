#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""گارد زمان‌بندیِ ماندگارِ سرخطی (execution_schedule.py).

این گارد هیچ شبکه/مرورگری صدا نمی‌زند. هر سناریو با store موقت، ساعتِ تزریقی و
executorِ بدل سنجیده می‌شود؛ live executor واقعی وجود ندارد و همین را هم تست
می‌کند: مسیر زنده تا تأیید قرارداد/نشست باید NEEDS_REVIEW بماند.
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import execution_schedule as S                     # noqa: E402

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
    d = tempfile.mkdtemp(prefix="sched_guard_")
    return S.ScheduleStore(os.path.join(d, "schedule.db")), d


def good_facts(sym="داروند", isin="IRO1DRVN0001", name="زیست اروند فارمد", at=None):
    now = int(time.time() * 1000) if at is None else int(at)
    return S.DarvandFacts(
        symbol=sym, isin=isin, full_name=name, identity_source="test",
        form_symbol=sym, form_opened_after_switch=True,
        price_min=10370.0, price_max=11010.0, tick=10.0,
        price_source="live-form", price_as_of_ms=now - 1000,
        qty_min=1.0, qty_max=100000.0, buying_power_ok=True,
        buying_power_source="test", commission=41.0,
        commission_source="live-form", session_ok=True, calendar_open=True,
        max_data_age_s=300.0, now_ms=now)


class FakeCal:
    def __init__(self, status):
        self.status_value = status

    def status(self, _day):
        return self.status_value, "fake"


class FakeExec:
    def __init__(self, state="ACKNOWLEDGED"):
        self.state = state
        self.calls = []
        self.lock = threading.Lock()

    def __call__(self, rec, report):
        with self.lock:
            self.calls.append(rec.id)
        return S.ExecutionOutcome(self.state, "fake", {"fake": True})


class FilledExec:
    def __init__(self):
        self.calls = 0

    def __call__(self, rec, report):
        self.calls += 1
        return S.ExecutionOutcome("ACKNOWLEDGED", "filled with evidence",
                                  {"order_state": "filled", "filled_quantity": rec.quantity})


class BadProvider:
    def __init__(self, facts):
        self.facts = facts
        self.calls = 0

    def __call__(self, _rec, _at=None):
        self.calls += 1
        return self.facts


class GoodProvider:
    def __call__(self, _rec, at=None):
        return good_facts(at=at)


def make(store, *, target_offset=3600_000, price=11010, qty=1, mode="dry_run",
         isin="IRO1DRVN0001", target_ms=None):
    target = int(target_ms) if target_ms is not None else S.now_ms() + target_offset
    return store.create(symbol="داروند", isin=isin, price=price, quantity=qty,
                        side="buy", target_ms=target, mode=mode,
                        full_name="زیست اروند فارمد")


def arm_dry(store, rec):
    rep = S.validate_darvand(rec, good_facts(), check_target_future=True)
    return store.arm(rec.id, rep.to_dict(), ok_for_arm=rep.ok_for_arm(rec.mode)), rep


def main() -> int:
    print("── ۱) ذخیره/بازیابی/اعتبارسنجی ──")
    st, _ = new_store()
    r = make(st)
    ck(r.state == "PREPARED" and r.target_ms > S.now_ms(), "ایجاد PREPARED با هدفِ آینده")
    ck(r.tz == "Asia/Tehran" and "+03:30" in r.target_local,
       "منطقهٔ زمانی و برچسب محلی ذخیره شد", r.target_local)
    st2 = S.ScheduleStore(st.path)
    ck(st2.get(r.id) is not None and st2.get(r.id).execution_id == r.execution_id,
       "بازگشایی store همان رکورد را می‌بیند (persistence)")
    for kw, label in ((dict(isin=""), "ISIN خالی"), (dict(price=0), "قیمت صفر"),
                      (dict(qty=1.5), "تعداد اعشاری"),
                      (dict(target_offset=-1000), "هدف در گذشته")):
        try:
            make(st, **kw)
            ok = False
        except S.ScheduleError as e:
            ok = e.code in ("INVALID_ISIN", "INVALID_ORDER", "INVALID_QUANTITY",
                            "TARGET_IN_PAST")
        ck(ok, "ردِ %s" % label)
    rep_ok = S.validate_darvand(r, good_facts(), check_target_future=True)
    ck(rep_ok.static_ok and rep_ok.live_ready,
       "factِ کامل → static و live_ready", rep_ok.blockers[:3])
    partial = S.DarvandFacts(symbol="داروند", isin="IRO1DRVN0001",
                             full_name="زیست اروند فارمد", identity_source="test")
    rep_partial = S.validate_darvand(r, partial, check_target_future=True)
    ck(rep_partial.static_ok and not rep_partial.live_ready
       and rep_partial.ok_for_arm("dry_run") and not rep_partial.ok_for_arm("live"),
       "factِ ناقص: dry-run مسلح، live نه", rep_partial.blockers[:3])
    for field, value, label in (("symbol", "داروند3", "نماد اشتباه"),
                                ("isin", "IRO1DRVN0003", "ISIN اشتباه"),
                                ("full_name", "پتروشیمی اروند", "نامِ اشتباه")):
        f = good_facts()
        setattr(f, field, value)
        bad = S.validate_darvand(r, f, check_target_future=True)
        ck(not bad.static_ok, "validator ردِ %s" % label, bad.blockers[:2])
    for label, mutate, key in (
            ("خارج از دامنه", lambda f: (setattr(f, "price_min", 12000.0),
                                        setattr(f, "price_max", 13000.0)), "price_band"),
            ("گام نامعتبر", lambda f: setattr(f, "price_min", 10371.0), "price_tick"),
            ("دادهٔ کهنه", lambda f: setattr(f, "price_as_of_ms",
                                             S.now_ms() - 900_000), "data_fresh"),
            ("بودجهٔ ناکافی", lambda f: setattr(f, "buying_power_ok", False),
             "buying_power"),
            ("نشست نامعتبر", lambda f: setattr(f, "session_ok", False), "session")):
        f = good_facts()
        mutate(f)
        bad = S.validate_darvand(r, f, check_target_future=True)
        ck(not bad.live_ready and bad.checks.get(key, {}).get("state") != "PASS",
           "validator live را برای %s می‌بندد" % label, bad.checks.get(key))
    r = arm_dry(st, r)[0]
    ck(r.state == "ARMED", "مسلح‌شدن dry-run با validation سبز")
    try:
        st.arm(r.id, rep_ok.to_dict(), ok_for_arm=True)
        ck(False, "armِ دوم باید رد شود")
    except S.ScheduleError as e:
        ck(e.code == "INVALID_TRANSITION", "armِ دوم رد می‌شود", e.code)

    print("\n── ۲) claim اتمیک و جلوگیری از dispatch تکراری ──")
    st, _ = new_store()
    r = make(st); arm_dry(st, r)
    results: dict[str, bool] = {}
    threads = []
    def _claim(tok):
        results[tok] = st.claim(r.id, tok, r.target_ms)
    for tok in ("tok-a", "tok-b"):
        threads.append(threading.Thread(target=_claim, args=(tok,)))
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    ck(list(results.values()).count(True) == 1,
       "دو claim هم‌زمان: دقیقاً یکی برنده", results)
    ck(st.get(r.id).attempts == 1, "attempt فقط یک بار ثبت شد")
    ck(not st.begin_submit(r.id, "wrong", r.target_ms), "submit با token اشتباه رد می‌شود")
    # token دقیق را از رکورد نمی‌خوانیم؛ دوباره با claimِ قطعی:
    st, _ = new_store(); r = make(st); arm_dry(st, r)
    st.claim(r.id, "good", r.target_ms)
    ck(st.begin_submit(r.id, "good", r.target_ms + 1), "submit فقط با claimِ همان اجرا")
    fin = st.finish(r.id, "good", "DRY_RUN", {"dry_run": True}, at_ms=r.target_ms + 2)
    ck(fin.state == "DRY_RUN", "نتیجهٔ dry-run ثبت شد")
    ck(fin.public().get("result_state") == "NOT_SENT",
       "وضعیتِ canonical برای dry-run = NOT_SENT", fin.public().get("result_state"))
    try:
        st.finish(r.id, "good", "DRY_RUN", {}, at_ms=S.now_ms())
        ck(False, "finish دوم باید رد شود")
    except S.ScheduleError as e:
        ck(e.code == "INVALID_TRANSITION", "finish دوم/تکراری رد می‌شود", e.code)

    print("\n── ۳) runner: dry-run، validation، halt، زمان ازدست‌رفته ──")
    st, _ = new_store(); r = make(st); arm_dry(st, r)
    ex = FakeExec("DRY_RUN")
    runner = S.ScheduleRunner(st, GoodProvider(), executor=ex,
                              clock_ms=lambda: r.target_ms + 500,
                              max_lateness_s=60)
    out = runner.tick()
    ck(st.get(r.id).state == "DRY_RUN" and len(ex.calls) == 1,
       "due ARMED در موعد → dry-run و یک executor", out)
    st, _ = new_store(); r = make(st); arm_dry(st, r)
    ex = FakeExec("DRY_RUN")
    runner = S.ScheduleRunner(st, BadProvider(good_facts(sym="داروند3")),
                              executor=ex, clock_ms=lambda: r.target_ms + 500)
    runner.tick()
    ck(st.get(r.id).state == "NEEDS_REVIEW" and not ex.calls,
       "fact اشتباه → NEEDS_REVIEW و صفر executor")
    st, _ = new_store(); r = make(st); arm_dry(st, r)
    ex = FakeExec("DRY_RUN")
    runner = S.ScheduleRunner(st, GoodProvider(), executor=ex,
                              clock_ms=lambda: r.target_ms + 500,
                              halted=lambda: (True, "test halt"))
    runner.tick()
    ck(st.get(r.id).state == "NEEDS_REVIEW" and not ex.calls,
       "halt → NEEDS_REVIEW و صفر executor")
    st, _ = new_store(); r = make(st); arm_dry(st, r)
    ex = FakeExec("DRY_RUN")
    runner = S.ScheduleRunner(st, GoodProvider(), executor=ex,
                              clock_ms=lambda: r.target_ms + 120_000,
                              max_lateness_s=60)
    runner.tick()
    ck(st.get(r.id).state == "MISSED_TARGET" and not ex.calls,
       "تأخیر > سقف → MISSED_TARGET و صفر executor (بدون جبران)")

    print("\n── ۴) restart و بازبینی ──")
    st, _ = new_store(); r = make(st); arm_dry(st, r)
    ex = FakeExec("DRY_RUN")
    runner = S.ScheduleRunner(st, GoodProvider(), executor=ex,
                              clock_ms=lambda: S.now_ms())
    got = runner.recover()
    ck(st.get(r.id).state == "NEEDS_REVIEW" and got["needs_review"] >= 1,
       "recover → NEEDS_REVIEW (هیچ ارسالِ خودکار)", got)
    ck(not ex.calls, "recover executor را صدا نزد")
    reset = st.reset_to_prepared(r.id)
    ck(reset.state == "PREPARED", "بازبینیِ مالک → PREPARED")
    # هدفِ گذشته قابل reset نیست
    st, _ = new_store(); r = make(st, target_offset=2000); arm_dry(st, r)
    time.sleep(2.1)
    try:
        st.reset_to_prepared(r.id)
        ck(False, "resetِ هدف گذشته باید رد شود")
    except S.ScheduleError as e:
        ck(e.code == "TARGET_IN_PAST", "resetِ هدف گذشته رد می‌شود", e.code)

    print("\n── ۵) لغو پیش از اجرا و لغو پس از claim ──")
    st, _ = new_store(); r = make(st); arm_dry(st, r)
    c = st.cancel(r.id)
    ck(c.state == "CANCELLED", "لغوِ ARMED → CANCELLED")
    ck(c.public().get("result_state") == "CANCELLED",
       "وضعیتِ canonical برای لغو = CANCELLED", c.public().get("result_state"))
    ck(not st.claim(r.id, "late", r.target_ms + 1000), "بعد از لغو claim ممکن نیست")
    st, _ = new_store(); r = make(st); arm_dry(st, r)
    st.claim(r.id, "x", r.target_ms)
    try:
        st.cancel(r.id)
        ck(False, "لغوِ RUNNING باید رد شود")
    except S.ScheduleError as e:
        ck(e.code == "INVALID_TRANSITION", "لغوِ RUNNING رد می‌شود", e.code)

    print("\n── ۶) dedupe و UNKNOWN ترمینال ──")
    st, _ = new_store(); r = make(st)
    try:
        make(st, target_ms=r.target_ms)
        ck(False, "ساختِ دوباره با همان کلید باید رد شود")
    except S.ScheduleError as e:
        ck(e.code == "DUPLICATE_SCHEDULE", "dedupe فعال است", e.code)
    st.cancel(r.id)
    r2 = make(st, target_ms=r.target_ms)
    ck(r2.id != r.id, "پس از CANCELLED کلید آزاد می‌شود")
    # UNKNOWN از مسیر live با executor بدل؛ executor واقعی نیست
    st, _ = new_store(); r = make(st, mode="live")
    rep = S.validate_darvand(r, good_facts(), check_target_future=True)
    st.arm(r.id, rep.to_dict(), ok_for_arm=True)
    ex = FakeExec("UNKNOWN")
    runner = S.ScheduleRunner(st, GoodProvider(), executor=ex,
                              calendar=FakeCal(S.CalendarStatus.OPEN),
                              clock_ms=lambda: r.target_ms + 500,
                              clock_ok=lambda: (True, "fake"),
                              live_enabled=True, contract_verified=True)
    runner.tick()
    ck(st.get(r.id).state == "UNKNOWN" and len(ex.calls) == 1,
       "live با همهٔ flagها → یک ارسال و UNKNOWN", st.get(r.id).state)
    ck(st.get(r.id).public().get("result_state") == "UNKNOWN",
       "وضعیتِ canonical برای UNKNOWN = UNKNOWN")
    try:
        make(st, mode="live", target_ms=r.target_ms)
        ck(False, "پس از UNKNOWN نباید سفارشِ هم‌کلید ساخت")
    except S.ScheduleError as e:
        ck(e.code == "DUPLICATE_SCHEDULE", "UNKNOWN کلید را قفل نگه می‌دارد", e.code)
    ck(not st.claim(r.id, "again", r.target_ms + 1000), "بعد از UNKNOWN claim ممکن نیست")

    print("\n── ۷) live گیت‌ها: بدون executor/contract/session/calendar ──")
    st, _ = new_store(); r = make(st, mode="live")
    rep = S.validate_darvand(r, good_facts(), check_target_future=True)
    st.arm(r.id, rep.to_dict(), ok_for_arm=True)
    ex = FakeExec("ACKNOWLEDGED")
    runner = S.ScheduleRunner(st, GoodProvider(), executor=ex,
                              calendar=FakeCal(S.CalendarStatus.OPEN),
                              clock_ms=lambda: r.target_ms + 500,
                              clock_ok=lambda: (True, "fake"),
                              live_enabled=False, contract_verified=False)
    runner.tick()
    ck(st.get(r.id).state == "NEEDS_REVIEW" and not ex.calls,
       "live بدون flag/contract → NEEDS_REVIEW، صفر ارسال")
    st, _ = new_store(); r = make(st, mode="live")
    st.arm(r.id, rep.to_dict(), ok_for_arm=True)
    ex = FakeExec("ACKNOWLEDGED")
    runner = S.ScheduleRunner(st, GoodProvider(), executor=ex,
                              calendar=FakeCal(S.CalendarStatus.CLOSED),
                              clock_ms=lambda: r.target_ms + 500,
                              clock_ok=lambda: (True, "fake"),
                              live_enabled=True, contract_verified=True)
    runner.tick()
    ck(st.get(r.id).state == "SKIPPED" and not ex.calls,
       "calendar بسته → SKIPPED، صفر ارسال")
    st, _ = new_store(); r = make(st, mode="live")
    st.arm(r.id, rep.to_dict(), ok_for_arm=True)
    ex = FakeExec("ACKNOWLEDGED")
    runner = S.ScheduleRunner(st, GoodProvider(), executor=ex,
                              calendar=FakeCal(S.CalendarStatus.OPEN),
                              clock_ms=lambda: r.target_ms + 500,
                              clock_ok=lambda: (False, "no ntp"),
                              live_enabled=True, contract_verified=True)
    runner.tick()
    ck(st.get(r.id).state == "NEEDS_REVIEW" and not ex.calls,
       "clock نامعتبر → NEEDS_REVIEW، صفر ارسال")
    st, _ = new_store(); r = make(st, mode="live")
    st.arm(r.id, rep.to_dict(), ok_for_arm=True)
    ex = FakeExec("ACKNOWLEDGED")
    runner = S.ScheduleRunner(st, GoodProvider(), executor=ex,
                              calendar=FakeCal(S.CalendarStatus.OPEN),
                              clock_ms=lambda: r.target_ms + 500,
                              clock_ok=lambda: (True, "fake"),
                              live_enabled=True, contract_verified=True)
    runner.tick()
    ck(st.get(r.id).state == "ACKNOWLEDGED" and len(ex.calls) == 1,
       "live با همهٔ flagها → ACKNOWLEDGED (executor بدل، هیچ شبکه)", st.get(r.id).state)
    ck(st.get(r.id).public().get("result_state") == "ACCEPTED",
       "ACK بدون شاهدِ fill = ACCEPTED، نه FILLED", st.get(r.id).public().get("result_state"))

    rec_probe = st.get(r.id)
    rec_probe.state = "ACKNOWLEDGED"
    rec_probe.result = {"order_state": "filled", "filled_quantity": 1}
    ck(S.canonical_result(rec_probe) == "FILLED",
       "FILLED فقط با شاهدِ صریحِ fill")
    print("\n── ۸) readiness و timezone ──")
    rd = S.readiness()
    ck(rd["live_ready"] is False and rd["dry_run_scheduling"] is True,
       "readiness: dry-run بله، live نه")
    ck(any(b["code"] == "SESSION_PERSISTENCE" for b in rd["blockers"]),
       "مانعِ sessionStorage صریح است")
    ms = S.parse_local("2026-10-21T08:45")
    ck(S.to_local(ms).startswith("2026-10-21T08:45"), "پارس/برچسب Asia/Tehran", S.to_local(ms))
    ck(S.local_identity_facts(os.path.join(ROOT, "market.db"), "داروند").isin ==
       "IRO1DRVN0001", "هویت محلی داروند = IRO1DRVN0001")
    st, _ = new_store(); r = make(st); arm_dry(st, r)
    ck(st.set_kill("test") >= 1 and st.get(r.id).state == "NEEDS_REVIEW",
       "kill switch زمان‌بندیِ ماندگار را به NEEDS_REVIEW می‌برد")

    print("\n%d passed / %d failed" % (PASS, FAIL))
    if FAILED:
        print("FAILED: " + ", ".join(FAILED))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
