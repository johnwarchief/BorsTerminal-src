# -*- coding: utf-8 -*-
# dev/execution_queue_v1.py — گاردِ Status G: خواندنِ وضعیتِ سفارش و جایِ صف
#
# بندِ ۱۸ دستورِ کار: «اگر کارگزاری اطلاعات واقعیِ position نمی‌دهد: UNKNOWN».
# این سوئیت همان را رویِ بدل می‌سنجد، و چیزی که *نگهبانی* می‌کند این است که
# سرویس درِ سه حالتِ متفاوت، عدد نسازد:
#
#   • کارگزاری اصلاً اندپوینتِ صف ندارد (capability)          ⇒ supported=False
#   • اندپوینت هست ولی برایِ این سفارش چیزی نمی‌گوید          ⇒ known=False
#   • سفارش هنوز شناسۀِ کارگزاری ندارد / وضعیتش انتهایی است   ⇒ پرسید نمی‌شود
#
# هیچ‌جا submit تازه زده نمی‌شود (شمارندۀِ `wire_calls`)، و بی‌خوابِ واقعی
# می‌چرخد (`sleep` تزریق می‌شود).
#
# اجرا:  python dev/execution_queue_v1.py

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from execution_contract import (  # noqa: E402
    Capabilities, ErrorCode, ExecutionStatus, InstrumentRef, OrderDraft, OrderMode,
    OrderState, QueueSnapshot, Resolution, Side,
)
from execution_mock import MockBrokerAdapter  # noqa: E402
from execution_service import ExecutionError, ExecutionService, Limits  # noqa: E402

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


def draft(eid="EX-Q1"):
    return OrderDraft(execution_id=eid, instrument=FOOLAD, side=Side.BUY,
                      price=12610.0, quantity=1000.0, mode=OrderMode.FAST)


def placed(**kw):
    """بدلی که یکِ سفارشِ واقعی رویِ سرور دارد و سرویسِخش."""
    caps = kw.pop("caps", Capabilities(list_orders=True, order_state=True,
                                       queue_position=True))
    a = MockBrokerAdapter(instruments=(FOOLAD,), capabilities=caps, **kw)
    s = ExecutionService(a, dry_run=False, limits=Limits(max_orders=5))
    s.execute(s.prepare(draft()))
    return s, a


def submitted(a):
    return [w for w in a.wire_calls if w.startswith("submit:")]


def asked_queue(a):
    return [w for w in a.wire_calls if w.startswith("queue:")]


# ── ۱) خواندنِ وضعیتِ سفارش ─────────────────────────────────────────────────
def part_refresh():
    s, a = placed(order_states={"EX-Q1": OrderState.PARTIAL})
    rec = s.refresh("EX-Q1")
    ck(rec.order_state is OrderState.PARTIAL,
       "وضعیتِ سرور به رکورد منتقل می‌شود", str(rec.order_state))
    ck(rec.status is ExecutionStatus.RECONCILED,
       "read-back موفق، اجرا را RECONCILED می‌کند", str(rec.status))
    a.set_order_state("EX-Q1", OrderState.FILLED, filled=1000.0)
    rec = s.refresh("EX-Q1")
    ck(rec.order_state is OrderState.FILLED and rec.filled_quantity == 1000.0,
       "تغییرِ بعدیِ سرور هم خوانده می‌شود", f"{rec.order_state} {rec.filled_quantity}")
    ck(len(submitted(a)) == 1,
       "هیچ refreshی سفارشِ تازه نمی‌سازد", str(submitted(a)))

    # سرور چیزی ندارد ⇒ وضعیت دست‌نخورده می‌ماند، نه «لغو‌شده»
    s2, a2 = placed()
    a2.server_orders.clear()
    rec2 = s2.refresh("EX-Q1")
    ck(rec2.status is ExecutionStatus.ACKNOWLEDGED
       and any("nothing" in e for e in rec2.events),
       "read-backِ خالی ⇒ وضعیت عوض نمی‌شود و دلیلش ثبت می‌شود", str(rec2.events[-1]))

    # بی‌شناسۀِ کارگزاری: پرسیدنی نیست
    s3 = ExecutionService(MockBrokerAdapter(instruments=(FOOLAD,),
                                            capabilities=Capabilities(
                                                list_orders=True, order_state=True,
                                                queue_position=True)),
                          dry_run=False)
    try:
        s3.refresh("NOT-THERE")
        ck(False, "refresh بی‌رکورد باید رد شود")
    except ExecutionError as e:
        ck(e.code is ErrorCode.INVALID_EXECUTION_ID,
           "refresh بی‌رکورد با INVALID_EXECUTION_ID رد می‌شود", e.code.value)

    # سرور وضعیت نمی‌گوید ⇒ UNKNOWN می‌مانَد (نه «پُر شده»)
    s4, a4 = placed()
    ck(s4.record("EX-Q1").order_state is OrderState.UNKNOWN,
       "بی‌گفتنِ سرور، order_state همان UNKNOWN می‌ماند",
       str(s4.record("EX-Q1").order_state))
    ck(s4.record("EX-Q1").filled_quantity is None,
       "حجمِ خورده بی‌شواهد ساخته نمی‌شود", str(s4.record("EX-Q1").filled_quantity))


# ── ۲) صف: سه معنایِ متفاوتِ «نمی‌دانیم» ────────────────────────────────────
def part_queue():
    s, a = placed()
    a.set_queue(list(a.server_orders)[0], 7, 3400.0)
    v = s.queue("EX-Q1")
    ck(v.supported and v.known and v.snapshot.position == 7,
       "عددِ واقعیِ صف خوانده می‌شود", str(v.snapshot))
    rec = s.record("EX-Q1")
    ck(rec.queue_position == 7 and rec.volume_ahead == 3400.0,
       "رکورد هم به‌روز می‌شود", f"{rec.queue_position}/{rec.volume_ahead}")
    ck(len(rec.queue_series) == 1,
       "مشاهده درِ رشتهٔ زمان‌دار می‌نشیند", str(rec.queue_series))

    # ۱) capability نیست ⇒ اصلاً سؤال نمی‌کند
    s2, a2 = placed(caps=Capabilities(list_orders=True, order_state=True))
    v2 = s2.queue("EX-Q1")
    ck(not v2.supported and not v2.known,
       "بی‌اندپوینتِ صف ⇒ supported=False، نه صفِ صفر", str(v2.reason))
    ck(not asked_queue(a2), "این حالت هیچ درخواستی بیرون نمی‌فرستد",
       str(a2.wire_calls))

    # ۲) اندپوینت هست ولی سرور برایِ این سفارش چیزی ندارد ⇒ UNKNOWN
    s3, a3 = placed()
    v3 = s3.queue("EX-Q1")
    ck(v3.supported and not v3.known,
       "پاسخِ خالیِ سرور ⇒ UNKNOWN (نه صفر، نه «اولِ صف»)", str(v3.snapshot))

    # ۳) صریح (None, None) رویِ سرور
    s4, a4 = placed()
    a4.set_queue(list(a4.server_orders)[0], None, None)
    v4 = s4.queue("EX-Q1")
    ck(v4.snapshot is not None and not v4.known,
       "ردیفِ بی‌مقدار درِ سرور هم UNKNOWN است", str(v4.snapshot))
    ck(s4.record("EX-Q1").queue_position is None,
       "و رکورد هم None می‌ماند", str(s4.record("EX-Q1").queue_position))

    # سفارشِ انتهایی: پرسیدن بی‌فایده است و زده نمی‌شود
    s5, a5 = placed(order_states={"EX-Q1": OrderState.FILLED})
    s5.refresh("EX-Q1")
    v5 = s5.queue("EX-Q1")
    ck(v5.terminal and not v5.known,
       "سفارشِ پُرشده دیگر صف ندارد", str(v5.reason))
    ck(not asked_queue(a5), "و برایِ آن پرسشِ صف نمی‌فرستد", str(a5.wire_calls))


# ── ۳) پایشِ صف ─────────────────────────────────────────────────────────────
def part_watch():
    s, a = placed()
    oid = list(a.server_orders)[0]
    steps = [5, 3, 1]
    sleeps = []

    def set_step(view_idx):
        a.set_queue(oid, steps[view_idx], 1000.0 * (view_idx + 1))

    views = []
    for i in range(len(steps)):
        set_step(i)
        views.append(s.queue("EX-Q1"))
    positions = [v.snapshot.position for v in views]
    ck(positions == steps,
       "سلسلۀِ جایِ صف خوانده می‌شود (۵←۳←۱)", str(positions))
    ck(len(s.record("EX-Q1").queue_series) == 3,
       "رکورد هر سه مشاهده را نگه می‌دارد", str(len(s.record("EX-Q1").queue_series)))

    # watch_queue با sleepِ تزریق‌شده: بی‌خوابِ واقعی، و بی‌ارسالِ تازه
    s2, a2 = placed()
    oid2 = list(a2.server_orders)[0]
    seq = iter([(3, 900.0), (2, 600.0), (1, 100.0)])

    def queue_swap(broker_order_id):
        try:
            pos, vol = next(seq)
        except StopIteration:
            pos, vol = (1, 100.0)
        a2.queue_by_order[broker_order_id] = (pos, vol)
        return QueueSnapshot(position=pos, volume_ahead=vol,
                             as_of=f"t{pos}", source="mock")

    a2.get_queue_position = queue_swap          # type: ignore[assignment]
    seen = s2.watch_queue("EX-Q1", samples=3, interval_ms=250,
                          sleep=lambda sec: sleeps.append(sec))
    ck([v.snapshot.position for v in seen] == [3, 2, 1],
       "پایشِ سه‌نمونه‌ای همان سه مقدار را می‌دهد",
       str([v.snapshot.position for v in seen]))
    ck(sleeps == [0.25, 0.25], "فاصله‌ها با sleepِ تزریق‌شده می‌خورند (بی‌خوابِ واقعی)",
       str(sleeps))
    ck(len(submitted(a2)) == 1, "پایش هیچ سفارشی نمی‌فرستد", str(submitted(a2)))

    # بی‌توانایی: نمونهٔ دوم گرفته نمی‌شود (اصرار ≠ reliability)
    s3, a3 = placed(caps=Capabilities(list_orders=True, order_state=True))
    slept = []
    seen3 = s3.watch_queue("EX-Q1", samples=5, interval_ms=10,
                           sleep=lambda sec: slept.append(sec))
    ck(len(seen3) == 1 and not slept,
       "بی‌اندپوینت، پایش درِ نمونهٔ اول می‌ایستد", f"{len(seen3)} samples")


def main():
    print("execution_queue_v1 — وضعیتِ سفارش و جایِ صف، بی‌ساختنِ عدد")
    part_refresh(); part_queue(); part_watch()
    print(f"\nexecution_queue_v1: {PASS} passed / {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
