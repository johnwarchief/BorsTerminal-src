# -*- coding: utf-8 -*-
# dev/execution_service_v1.py — گاردِ سرویسِ اجرا (Stage J)
#
# هیچ کارگزاریِ واقعی صدا زده نمی‌شود؛ همه‌چیز رویِ `MockBrokerAdapter` و با
# ساعتِ تزریق‌شده می‌چرخد. سه چیزی که این سوئیت نمی‌گذارد فراموش شود:
#   • dry-run پیش‌فرض است و درِ آن **هیچ** submit به بیرون نمی‌رود (بندِ ۲۸).
#   • بعدِ timeout تنها مسیرِ مجاز reconcile است، نه ارسالِ دوباره (بندِ ۲۰/۲۱).
#   • تکرار و ULTRA بی‌تأییدِ صریح و بی‌سقفِ ارزش/تعداد اجرا نمی‌شوند (بندِ ۱۵).
#
# اجرا:  python dev/execution_service_v1.py

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from execution_contract import (  # noqa: E402
    BrokerError, Capabilities, ErrorCode, ExecutionStatus, InstrumentRef, OrderDraft,
    OrderMode, Resolution, Side,
)
from execution_mock import MockBrokerAdapter  # noqa: E402
from execution_service import (  # noqa: E402
    ExecutionError, ExecutionService, Limits, ModePolicy, Prepared,
)
from execution_timing import ClockQuality, ClockState, Scheduler, TimeSource  # noqa: E402

PASS = FAIL = 0


def ck(cond, what, got=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {what}")
    else:
        FAIL += 1
        print(f"  FAIL {what}" + (f"  -> {got}" if got else ""))


FOOLAD = InstrumentRef(symbol="فولاد", ins_code="46", isin="IRO1IKCO0001",
                       broker_instrument="IRO1IKCO0001", resolution=Resolution.EXACT)
NO_ISIN = InstrumentRef(symbol="پارسان", ins_code="9", isin=None,
                        broker_instrument=None, resolution=Resolution.EXACT)


def d(execution_id="EX-1", instrument=FOOLAD, mode=OrderMode.SAFE,
      price=12610.0, quantity=1000.0, side=Side.BUY) -> OrderDraft:
    return OrderDraft(execution_id=execution_id, instrument=instrument, side=side,
                      price=price, quantity=quantity, mode=mode)


class FakeClock:
    def __init__(self):
        self.t = 1000.0
        self.wall0 = 1_760_000_000_000

    def mono(self):
        return self.t

    def wall(self):
        return self.wall0 + int(self.t * 1000)

    def source(self):
        return TimeSource(wall_ms=self.wall, mono=self.mono)

    def scheduler(self):
        return Scheduler(self.source())

    def nap(self, seconds):
        self.t += seconds


def svc(*, script=None, caps=None, dry_run=True, limits=None, gate=None,
        with_scheduler=True, balances=None):
    a = MockBrokerAdapter(instruments=(FOOLAD, NO_ISIN),
                          capabilities=caps or Capabilities(list_orders=True,
                                                            order_state=True,
                                                            queue_position=True),
                          script=script or {})
    if balances is not None:
        a.balances = balances
    fc = FakeClock()
    sched = fc.scheduler() if with_scheduler else None
    return ExecutionService(a, scheduler=sched,
                            dry_run=dry_run, limits=limits or Limits(),
                            session_gate=gate), a, fc


def submits(a):
    return [w for w in a.wire_calls if w.startswith("submit:")]


# ── ۱) dry-run ───────────────────────────────────────────────────────────────
def part_dry_run():
    s, a, _fc = svc()
    p = s.prepare(d())
    rec = s.execute(p)
    ck(not submits(a), "dry-run هیچ submit_orderی صدا نمی‌زند", str(a.wire_calls))
    ck(rec.status is ExecutionStatus.VALIDATED, "وضعیتِ dry-run VALIDATED است", str(rec.status))
    ck(any("dry-run" in e for e in rec.events), "رکورد صریح می‌گوید چیزی ارسال نشد")
    ck(any("payload=" in e for e in rec.events), "معاینۀِ payload درِ رکورد است (بندِ ۲۸)")

    s2, a2, fc2 = svc()
    target = fc2.wall() + 1_000
    p2 = s2.prepare(d(), target_wall_ms=target, one_way_ms=20.0, margin_ms=5.0,
                    clock=ClockState(1.0, ClockQuality.TRUSTED))
    rec2 = s2.execute(p2)
    ck(p2.plan is not None and rec2.status is ExecutionStatus.SCHEDULED,
       "dry-run با زمانِ هدف، پلنِ SCHEDULED می‌دهد", str(rec2.status))
    ck(not submits(a2), "حتی با پلنِ زمان‌دار هم چیزی ارسال نمی‌شود", str(a2.wire_calls))
    ck(abs(p2.plan.send_at_wall_ms - (target - 25)) < 1e-6,
       "مهلتِ پلن = هدف − یک‌طرفه − حاشیه", str(p2.plan.send_at_wall_ms))


# ── ۲) حالت‌ها ───────────────────────────────────────────────────────────────
def part_modes():
    ck(ModePolicy.of(OrderMode.SAFE).blocking_verify
       and not ModePolicy.of(OrderMode.FAST).blocking_verify,
       "SAFE تأییدِ مسدودکننده دارد، FAST ندارد")
    ck(ModePolicy.of(OrderMode.ULTRA).requires_prepared,
       "ULTRA باید از پیش prepared باشد")

    s, a, _ = svc(dry_run=False)
    rec = s.execute(s.prepare(d(mode=OrderMode.SAFE)))
    ck(rec.status is ExecutionStatus.RECONCILED,
       "SAFE بعدِ ارسال، read-back می‌گیرد و RECONCILED می‌شود", str(rec.status))
    ck(any(w.startswith("get_order") for w in a.wire_calls),
       "تأییدِ SAFE واقعاً به سرور پرسیده شد", str(a.wire_calls))

    s2, a2, _ = svc(dry_run=False)
    rec2 = s2.execute(s2.prepare(d(mode=OrderMode.FAST)))
    ck(rec2.status is ExecutionStatus.ACKNOWLEDGED,
       "FAST بدونِ تأییدِ مسدودکننده برمی‌گردد", str(rec2.status))
    ck(not any(w.startswith("get_order") for w in a2.wire_calls),
       "FAST هیچ پرسشِ همگامی بعدِ ارسال نمی‌کند")

    s3, a3, _ = svc(dry_run=False)
    try:
        rec3 = ExecutionService(s3.adapter, scheduler=s3.scheduler, dry_run=False)
        raw = Prepared(draft=d(mode=OrderMode.ULTRA),
                       preflight=s3.preflight(d(mode=OrderMode.ULTRA)),
                       plan=None, payload_preview={}, mode=OrderMode.ULTRA,
                       dry_run=False)
        rec3.execute(raw)
        ck(False, "ULTRA بی‌prepare() باید رد شود")
    except ExecutionError as e:
        ck(e.code is ErrorCode.INVALID_EXECUTION_ID,
           "ULTRA بی‌prepare() رد می‌شود", e.code.value)

    # ULTRA با prepare + dispatch زمان‌دار
    s4, a4, fc4 = svc(dry_run=False)
    plan_target = fc4.wall() + 300
    prep = s4.prepare(d("EX-U", mode=OrderMode.ULTRA), target_wall_ms=plan_target,
                      one_way_ms=0.0, confirmed=True)
    spins = {"n": 0}

    def spin():
        spins["n"] += 1
        fc4.t += 0.001

    rec4 = s4.execute(prep, sleep=fc4.nap, yield_cpu=spin)
    ck(rec4.status is ExecutionStatus.ACKNOWLEDGED and len(submits(a4)) == 1,
       "ULTRA با پلن، دقیقاً یکِ ارسال دارد", f"{rec4.status} submits={len(submits(a4))}")
    ck(spins["n"] > 0 and rec4.drift_us is not None,
       "ULTRA از مسیرِ spinِ زمان می‌گذرد و drift را ثبت می‌کند", str(rec4.drift_us))


# ── ۳) timeout → reconcile ───────────────────────────────────────────────────
def part_unknown():
    s, a, _ = svc(script={"EX-1": ["timeout"]}, dry_run=False)
    prep = s.prepare(d())
    rec = s.execute(prep)
    ck(rec.status is ExecutionStatus.UNKNOWN_RESULT,
       "timeout به UNKNOWN_RESULT می‌رسد، نه استثنایِ مهارنشده", str(rec.status))
    ck(rec.error_code is ErrorCode.TIMEOUT and len(submits(a)) == 1,
       "یکِ ارسال، و خطا ثبت شده", f"submits={len(submits(a))}")
    # همان Preparedِ ازپیش‌ساخته‌شده، بارِ دوم: contractِ adapter جلویِ
    # execution_idِ مصرف‌شده را می‌گیرد و استثنایِ NON-unknown را بیرون می‌دهد.
    try:
        s.execute(prep)
        ck(False, "اجرایِ دوبارۀِ همان Prepared باید رد شود")
    except BrokerError as e:
        ck(e.code is ErrorCode.DUPLICATE_GUARD,
           "لایۀِ adapter هم خودِ تکرار را DUPLICATE_GUARD می‌کند", e.code.value)
    ck(len(submits(a)) == 1, "هیچ ارسالِ دومی به سرور نرسیده", str(submits(a)))
    out = s.reconcile("EX-1")
    ck(out.status is ExecutionStatus.RECONCILED and out.broker_order_id,
       "reconcile از فهرستِ سرور پیدایش می‌کند", f"{out.status} {out.broker_order_id}")
    ck(len(submits(a)) == 1, "reconcile هیچ ارسالِ تازه‌ای نمی‌سازد", str(submits(a)))

    # بندِ ۱۹/۲۰: timeout بعد از یکِ اجرا، اجرایِ دوبلِ همان execution_id
    # نباید بی‌رد شدنِ contract به سرور برسد (سفارشِ تکراری = فاجعۀِ واقعی).
    try:
        s.execute(s.prepare(d()))
        ck(False, "ارسالِ دوبارۀِ همان execution_id باید رد شود")
    except ExecutionError as e:
        ck(e.code is ErrorCode.DUPLICATE_GUARD,
           "پیش‌فرود، execution_idِ مصرف‌شده را DUPLICATE_GUARD می‌کند", e.code.value)
    ck(len(submits(a)) == 1, "ردِ پیش‌فرود یعنی سرور هیچ ارسالِ دوم ندیده", str(submits(a)))

    s2, a2, _ = svc(script={"EX-1": ["http5xx"]}, dry_run=False)
    r2 = s2.execute(s2.prepare(d()))
    ck(r2.status is ExecutionStatus.UNKNOWN_RESULT,
       "5xx هم UNKNOWN_RESULT است (نتیجه نامعلوم، نه شکستِ قطعی)", str(r2.status))
    out2 = s2.reconcile("EX-1")
    ck(out2.status is ExecutionStatus.FAILED and "no such order" in out2.events[-1],
       "اگر سرور چیزی نداشت، FAILED با دلیل — نه retry")
    ck(len(submits(a2)) == 1, "این هم ارسالِ دوم نمی‌سازد", str(submits(a2)))

    s3, a3, _ = svc(script={"EX-1": ["timeout"]}, dry_run=False,
                   caps=Capabilities(list_orders=True, order_state=True))
    s3.execute(s3.prepare(d()))
    a3._caps = Capabilities(list_orders=False, order_state=False)
    out3 = s3.reconcile("EX-1")
    ck(out3.status is ExecutionStatus.UNKNOWN_RESULT
       and any("reconcile impossible" in e for e in out3.events),
       "بی‌تواناییِ خواندن، UNKNOWN می‌ماند و دلیلش را می‌گوید")


# ── ۴) پیش‌فرود ─────────────────────────────────────────────────────────────
def part_preflight():
    s, a, _ = svc(dry_run=False)
    try:
        s.prepare(d(instrument=NO_ISIN))
        ck(False, "بی‌ISIN باید درِ پیش‌فرود رد شود")
    except ExecutionError as e:
        ck(e.code is ErrorCode.NOT_ORDERABLE, "بی‌ISIN ⇒ NOT_ORDERABLE", e.code.value)
    ck(not submits(a), "ردِ پیش‌فرود هیچ درخواستی بیرون نمی‌فرستد", str(a.wire_calls))

    pf = s.preflight(d())
    ck(pf.checks.get("balance") == "UNKNOWN",
       "بی‌capabilityِ نقدینگی ⇒ UNKNOWN، نه صفر", str(pf.checks.get("balance")))
    ck(pf.unknown == ("balance",) or "balance" in pf.unknown,
       "UNKNOWN درِ فهرستِ جدا می‌ماند و مانعِ ارسال نیست", str(pf.unknown))

    s2, a2, _ = svc(dry_run=False, caps=Capabilities(list_orders=True, balances=True),
                    balances={"cash": 10.0, "positions": {}})
    try:
        s2.prepare(d(price=12610.0, quantity=1000.0))
        ck(False, "نقدینگیِ ناکافی باید رد شود")
    except ExecutionError as e:
        ck(e.checks.get("balance") == "FAIL", "نقدینگیِ ناکافی ⇒ رد", str(e.checks))

    s3, _, _ = svc(dry_run=False, gate=lambda _t: "closed")
    try:
        s3.prepare(d())
        ck(False, "بازارِ بسته باید رد کند")
    except ExecutionError as e:
        ck(e.code is ErrorCode.MARKET_CLOSED, "بازارِ بسته ⇒ MARKET_CLOSED", e.code.value)
    s4, _, _ = svc(dry_run=False, gate=None)
    ck(s4.preflight(d()).checks.get("session") == "UNKNOWN",
       "بی‌دروازۀِ نشست ⇒ UNKNOWN (سه پنجرۀِ متناقض درِ ریپو، §۱-ه)")

    s5, _, _ = svc(dry_run=False)
    s5.execute(s5.prepare(d("EX-D")))
    ck(s5.preflight(d("EX-D")).checks.get("duplicate") == "FAIL",
       "execution_idِ تکراری درِ پیش‌فرود دیده می‌شود")

    s6, _, _ = svc(dry_run=False, caps=Capabilities(place=False, list_orders=True))
    try:
        s6.prepare(d())
        ck(False, "بی‌تواناییِ ارسال باید رد شود")
    except ExecutionError as e:
        ck(e.code is ErrorCode.UNSUPPORTED, "place=false ⇒ UNSUPPORTED", e.code.value)


# ── ۵) تکرار با گارد ────────────────────────────────────────────────────────
def part_repeat():
    s, a, _ = svc(dry_run=False)
    try:
        s.plan_repeat(d(mode=OrderMode.SAFE), 3, 100, confirmed=True)
        ck(False, "SAFE تکرار را مجاز نمی‌داند")
    except ExecutionError as e:
        ck(e.code is ErrorCode.UNSUPPORTED, "تکرار درِ SAFE/FAST ممنوع است", e.code.value)

    try:
        s.plan_repeat(d(mode=OrderMode.ULTRA), 3, 100)
        ck(False, "تکرار بی‌تأیید نباید بگذرد")
    except ExecutionError as e:
        ck(e.code is ErrorCode.DUPLICATE_GUARD, "تکرار بی‌تأییدِ صریح رد می‌شود", e.code.value)

    tight = ExecutionService(MockBrokerAdapter(instruments=(FOOLAD, NO_ISIN)),
                             limits=Limits(max_orders=2, max_total_value=3e7,
                                           max_total_quantity=2500))
    try:
        tight.plan_repeat(d(mode=OrderMode.ULTRA), 3, 50, confirmed=True)
        ck(False, "سقفِ تعدادِ سفارش باید جلویش را بگیرد")
    except ExecutionError as e:
        ck("سقف" in e.detail, "سقفِ تعدادِ سفارش فعال است", e.detail)
    try:
        ExecutionService(MockBrokerAdapter(instruments=(FOOLAD, NO_ISIN)),
                         limits=Limits(max_orders=9, max_total_quantity=2000)
                         ).plan_repeat(d(mode=OrderMode.ULTRA, quantity=1200), 2, 50,
                                       confirmed=True)
        ck(False, "سقفِ مجموعِ تعداد باید رد کند")
    except ExecutionError as e:
        ck("تعدادِ کل" in e.detail, "سقفِ مجموعِ تعداد فعال است", e.detail)

    ok = ExecutionService(MockBrokerAdapter(instruments=(FOOLAD, NO_ISIN)),
                          limits=Limits(max_orders=3, max_total_value=5e7,
                                        max_total_quantity=3500))
    offsets = ok.plan_repeat(d(mode=OrderMode.ULTRA, quantity=1000), 3, 120,
                             confirmed=True)
    ck(offsets == [0, 120, 240], "آفستِ مطلقِ تکرار همان delay×i است", str(offsets))


# ── ۶) دفترِ اجرا ───────────────────────────────────────────────────────────
def part_ledger():
    s, a, _ = svc()
    s.execute(s.prepare(d("EX-L1")))
    s.execute(s.prepare(d("EX-L2")))
    ck(len(s.ledger()) == 2 and s.record("EX-L1") is not None,
       "هر اجرا درِ دفتر ثبت می‌شود", str(len(s.ledger())))
    try:
        s.reconcile("NOT-EXISTENT")
        ck(False, "شناسۀِ نامعلوم باید رد شود")
    except ExecutionError as e:
        ck(e.code is ErrorCode.INVALID_EXECUTION_ID, "reconcile بی‌رکورد رد می‌شود")


def main():
    print("execution_service_v1 — سرویسِ اجرا: dry-run، حالت‌ها، reconcile، لیمیت")
    part_dry_run(); part_modes(); part_unknown(); part_preflight(); part_repeat(); part_ledger()
    print(f"\nexecution_service_v1: {PASS} passed / {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
