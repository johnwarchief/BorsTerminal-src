#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sarkhati_tab_v1122 — گاردِ تبِّ مستقلِ «سرخطی»: لغوِ واقعی، سابقۀِ فیلترشدنی، و
صادقِ‌بودنِ چیزی که رابط ازِ `/status` می‌خواند.

چرا این گارد تازه است: تبِ جدید هیچ داوریِ تازه‌ای نمی‌سازد — همه‌چیز ازِ همان
`api/execution.py` خوانده می‌شود. پس سه چیزی که پیشِ این درِ HTTP نداشتیم و
رابطِ واحد بهشان نیاز دارد، همین‌جا قفل می‌شود:

  ۱) `POST /api/execution/cancel/{id}` — لغو باِ تأییدِ صریح، قفلِ ردیف‌به‌ردیف،
     و «تأییدِ لغو» فقط باِ بازخوانیِ وضعیت (پاسخِ `true` به‌تنهایی کافی نیست).
  ۲) `GET /api/execution/events` — سابقه باِ فیلترِ نماد/وضعیت/گونه/بازۀِ زمانی،
     بی‌`payload` و باِ `redact` رویِ `detail`.
  ۳) همان فیلدهایی که پنل‌هایِ جدید ازِ `/status` می‌خوانند: `mode_matrix`،
     `queue_rank`، `capabilities.cancel`، و `timings`.

هیچ سفارشِ واقعی ارسال نمی‌شود: ترافیک ازِ `MockBrokerAdapter` و ساعتِ تزریق‌شده
می‌آید، ردِّپا رویِ بانکِ موقتِ خودِ گارد است، و دورِ چندِ سنجه tripwireِ سوکت
نشسته است.
"""
import json
import os
import socket
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

#: ردِّپایِ آزمون باید ازِ `user.db`ِ کاربر جدا باشد — پیشِ آنکه `api.execution`
#: ایمپورت شود، چون `_AUDIT = default_ledger()` درِ زمانِ ایمپورت مسیر را می‌خواند.
_TMP = tempfile.mkdtemp(prefix="bors_v1122_")
os.environ["BORS_EXECUTION_DB"] = os.path.join(_TMP, "exec.db")
os.environ["BORS_CODAL_OFFLINE"] = "1"

from execution_contract import (  # noqa: E402
    BrokerError, Capabilities, ErrorCode, ExecutionRecord, ExecutionStatus,
    InstrumentRef, OrderDraft, OrderMode, OrderState, Resolution, Side,
)
from execution_mock import MockBrokerAdapter  # noqa: E402
from execution_service import (  # noqa: E402
    ExecutionError, ExecutionService, Limits,
)

PASS = FAIL = SKIP = 0


def ck(cond, label, got=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("ok   " + label)
    else:
        FAIL += 1
        print("FAIL " + label + "  -> " + str(got)[:200])


def skip(label, why):
    global SKIP
    SKIP += 1
    print("SKIP " + label + "  (" + why + ")")


class Tripwire:
    """هر سوکتِ واقعی درِ دورِ این بلوک = شکستِ سنجه، نه هشدار."""

    def __init__(self):
        self.hits = []
        self._old = socket.socket

    def __enter__(self):
        outer = self

        class Guarded(outer._old):
            def connect(self, addr, *a, **k):
                outer.hits.append(addr)
                raise OSError("network is disabled in this guard")
        socket.socket = Guarded
        return self

    def __exit__(self, *exc):
        socket.socket = self._old
        return False


FOOLAD = InstrumentRef(symbol="فولاد", ins_code="46", isin="IRO1IKCO0001",
                       broker_instrument="IRO1IKCO0001", resolution=Resolution.EXACT)
CAPS_CANCEL = Capabilities(place=True, list_orders=True, order_state=True,
                           queue_position=True, cancel=True)
CAPS_NOCANCEL = Capabilities(place=True, list_orders=True, order_state=True,
                             queue_position=True, cancel=False)


def draft(eid="V1122-1", instrument=FOOLAD, price=12610.0, quantity=1000.0,
          side=Side.BUY) -> OrderDraft:
    return OrderDraft(execution_id=eid, instrument=instrument, side=side,
                      price=price, quantity=quantity, mode=OrderMode.SAFE)


def service(caps=CAPS_CANCEL, dry_run=False, script=None):
    a = MockBrokerAdapter(instruments=(FOOLAD,), capabilities=caps, script=script or {})
    return ExecutionService(a, scheduler=None, dry_run=dry_run, limits=Limits()), a


def live_order(svc_obj, adapter, eid="V1122-1"):
    """سفارشی که *واقعاً* پذیرفته شده تا لغو معنا داشته باشد."""
    rec = svc_obj.execute(svc_obj.prepare(draft(eid)))
    return rec


# ═══════════════ ۱) معنایِ لغو درِ سرویس ═════════════════════════════════════
s, a = service()
rec = live_order(s, a)
ck(rec.broker_order_id is not None and rec.order_state is not OrderState.CANCELLED,
   "پیشِ لغو: سفارشِ پذیرفته‌شده باِ شناسۀِ کارگزاری ساخته شد",
   "%s / %s" % (rec.broker_order_id, rec.order_state))

before = list(a.wire_calls)
with Tripwire() as tw:
    out = s.cancel(rec.execution_id, reason="سنجش")
ck(not tw.hits, "لغو هیچ سوکتِ واقعی نزد")
ck(sum(1 for w in a.wire_calls if w.startswith("cancel:")) == 1,
   "دقیقاً یکِ فراخوانِ لغو رفت", str(a.wire_calls))
ck(out.order_state is OrderState.CANCELLED,
   "بازخوانیِ وضعیت لغو را تأیید کرد ⇒ رکورد cancelled می‌شود", str(out.order_state))
ck(not [w for w in a.wire_calls[len(before):] if w.startswith("submit:")],
   "لغو هیچ سفارشِ تازه‌ای نمی‌سازد", str(a.wire_calls[len(before):]))

# لغوی دوم رویِ همان سفارشِ بسته: بی‌اثر، ولی ردِّپا و یادداشت می‌ماند
n_cancel = sum(1 for w in a.wire_calls if w.startswith("cancel:"))
again = s.cancel(rec.execution_id, reason="تکرار")
ck(sum(1 for w in a.wire_calls if w.startswith("cancel:")) == n_cancel,
   "لغوِ دوباره رویِ سفارشِ بسته هیچ درخواستی نمی‌زند")
ck(again.order_state is OrderState.CANCELLED
   and any("cancel skipped" in e for e in again.events),
   "حالتِ بسته حفظ می‌شود و «چرا بی‌اثر بود» درِ رکورد است", str(again.events[-3:]))

# ادapt باِ cancel=False: «نمی‌توانم» و **هیچ** درخواستی
s2, a2 = service(caps=CAPS_NOCANCEL)
r2 = live_order(s2, a2, "V1122-2")
try:
    s2.cancel(r2.execution_id)
    ck(False, "بی‌capabilityِ لغو باید ExecutionError بدهد")
except ExecutionError as e:
    ck(e.code is ErrorCode.UNSUPPORTED,
       "بی‌capabilityِ لغو ⇒ UNSUPPORTED، نه «لغو شد»", e.code.value)
ck(not [w for w in a2.wire_calls if w.startswith("cancel:")],
   "ردِ capability یعنی هیچ فراخوانی‌ای نرفته", str(a2.wire_calls))

# بی‌شناسۀِ کارگزاری (dry-run): لغوِ چیزی که نرفته ممکن نیست
s3, a3 = service(dry_run=True)
r3 = s3.execute(s3.prepare(draft("V1122-3")))
try:
    s3.cancel(r3.execution_id)
    ck(False, "سفارشِ نجوشیده نباید «لغو شد» بگیرد")
except ExecutionError as e:
    ck(e.code is ErrorCode.NOT_ORDERABLE,
       "بی‌broker_order_id ⇒ NOT_ORDERABLE (لغوِ پیش‌نویس کارِ این در نیست)", e.code.value)

# شناسۀِ ناموجود
try:
    s.cancel("no-such-id")
    ck(False, "شناسۀِ نامعلوم باید خطا بدهد")
except ExecutionError as e:
    ck(e.code is ErrorCode.INVALID_EXECUTION_ID, "شناسۀِ نامعتبر ⇒ INVALID_EXECUTION_ID")

# لغوی که پاسخِ روشنی ندارد: نامعلوم می‌ماند و **تلاشِ دوباره** نمی‌شود
s4, a4 = service()
r4 = live_order(s4, a4, "V1122-4")
calls_at_entry = len([w for w in a4.wire_calls if w.startswith("cancel:")])


def _boom(broker_order_id):
    raise BrokerError(ErrorCode.TIMEOUT, "mock: no answer to cancel")


a4.cancel_order = _boom
try:
    s4.cancel(r4.execution_id)
    ck(False, "timeout درِ لغو باید خطا بدهد")
except ExecutionError as e:
    ck(e.code is ErrorCode.TIMEOUT, "timeoutِ لغو ⇒ همان TIMEOUT، نه «رد شد»", e.code.value)
ck(len([w for w in a4.wire_calls if str(w).startswith("cancel:")]) == calls_at_entry,
   "بعدِ timeout هیچ تلاشِ دوباره‌ای درِ لغو نمی‌شود", str(a4.wire_calls[-4:]))
ck(r4.order_state is not OrderState.CANCELLED
   and any("cancel ambiguous" in e for e in r4.events),
   "نتیجهٔ نامعلومِ لغو «لغوشده» نوشته نمی‌شود", "%s / %s" % (r4.order_state, r4.events[-2:]))

# «لغو شد» گفت ولی بازخوانی چیزِ دیگری نشان داد ⇒ ادعایِ تأیید نمی‌شود
s5, a5 = service()
r5 = live_order(s5, a5, "V1122-5")


def _lie(broker_order_id):
    a5.server_orders[broker_order_id].order_state = OrderState.OPEN
    return True


a5.cancel_order = _lie
out5 = s5.cancel(r5.execution_id)
ck(out5.order_state is not OrderState.CANCELLED,
   "پاسخِ true بی‌بازخوانیِ موافق، رکورد را cancelled نمی‌کند", str(out5.order_state))
ck(any("read-back does not confirm" in e for e in out5.events),
   "و صریح می‌نویسد «پذیرفته شد، تأیید نشده»", str(out5.events[-2:]))

# کارگزاری صریحاً رد کرد
s6, a6 = service()
r6 = live_order(s6, a6, "V1122-6")
a6.cancel_order = lambda oid: False
try:
    s6.cancel(r6.execution_id)
    ck(False, "ردِ صریح کارگزاری باید خطا بدهد")
except ExecutionError as e:
    ck(e.code is ErrorCode.BROKER_REJECTED, "ردِ صریح ⇒ BROKER_REJECTED", e.code.value)
ck(r6.order_state is not OrderState.CANCELLED, "ردشده «لغوشده» نمی‌شود")


# ═══════════════ ۲) درِ HTTP: تأییدِ صریح، قفلِ ردیفی، سابقه ══════════════════
import fastapi                                                    # noqa: E402
import api.execution as E                                          # noqa: E402
from fastapi.testclient import TestClient                          # noqa: E402

_app = fastapi.FastAPI()
_app.include_router(E.router)
client = TestClient(_app)

st = client.get("/api/execution/status").json()
ck(st["status"] == "success" and "cancel" in st["capabilities"],
   "/status تواناییِ لغو را صریح اعلام می‌کند", str(st["capabilities"]))
ck(st["mode_matrix"]["live"]["active"] is False and st["mode_matrix"]["paper"]["door"] == "/api/bot/*",
   "ماتریسِ حالت‌ها ازِ همان منبعِ همیشگی می‌آید (paper درِ درِ ربات است)")
ck(st["queue_rank"]["claims_first"] is False and st["queue_rank"]["official_rank_source"] is None,
   "هیچ ادعایِ «اولِ صف» درِ پاسخ نیست")
ck(st["confirm_epoch"] == E._confirm_epoch(), "دورۀِ تأیید درِ /status زنده است")

# TestClient برایِ خودِ chرخدِ asyncio به socketpair نیاز دارد، پس tripwireِ
# سوکت دورِ آن نمی‌نشیند؛ بی‌اثریِ ردِ تأیید ازِ شمّارۀِ فراخوان‌هایِ آداپتور
# خوانده می‌شود — که همان چیزی است که «هیچ درخواستی نرفت» معنا دارد.
_wbefore = len(E._ACTIVE_ADAPTER.wire_calls)
refused = client.post("/api/execution/cancel/ANY", json={}).json()
ck(refused["status"] == "refused" and refused["confirm_gate"] == "explicit_confirm_required",
   "لغو بی‌confirm=true هیچ کاری نمی‌کند و صریح رد می‌شود", str(refused)[:160])
ck(len(E._ACTIVE_ADAPTER.wire_calls) == _wbefore,
   "ردِ تأیید هیچ فراخوانی به آداپتور نزد", str(E._ACTIVE_ADAPTER.wire_calls[-3:]))

unknown = client.post("/api/execution/cancel/nope", json={"confirm": True}).json()
ck(unknown["status"] == "error" and unknown["code"] == "INVALID_EXECUTION_ID",
   "درِ HTTP هم شناسۀِ نامعتبر را صادق می‌گوید", str(unknown)[:160])

# یکِ رکوردِ واقعی درِ سرویسِ ماژول می‌گذاریم تا مسیرِ موفقِ HTTP آزموده شود
_oid, _eid = "V1122BR", "V1122-HTTP"
_hrec = ExecutionRecord(execution_id=_eid, broker="mock", account="mock-acct-1",
                        symbol="فولاد", isin=FOOLAD.isin, side=Side.BUY, price=12610.0,
                        quantity=1000.0, mode=OrderMode.SAFE,
                        status=ExecutionStatus.ACKNOWLEDGED,
                        broker_order_id=_oid, order_state=OrderState.OPEN)
E._SERVICE._ledger[_eid] = _hrec
E._ACTIVE_ADAPTER.server_orders[_oid] = _hrec

blocked = threading.Event()
hold = E._cancel_lock(_eid)
hold.acquire()
inflight = client.post("/api/execution/cancel/%s" % _eid,
                       json={"confirm": True, "reason": "سنجشِ قفل"}).json()
ck(inflight["status"] == "refused" and inflight["code"] == "DUPLICATE_GUARD"
   and inflight.get("in_flight") is True,
   "دومینِ لغوی هم‌زمان رد می‌شود: یکِ سفارش یکِ صاحبِ لغو دارد", str(inflight)[:160])
hold.release()

ok_call = client.post("/api/execution/cancel/%s" % _eid,
                      json={"confirm": True, "reason": "سنجش"}).json()
ck(ok_call["status"] == "success" and ok_call["cancelled_confirmed"] is True
   and ok_call["order_state"] == "cancelled",
   "مسیرِ موفقِ HTTP: لغو باِ بازخوانی تأیید شد", str(ok_call)[:200])
ck(ok_call["record"]["execution_id"] == _eid and "payload" not in ok_call["record"],
   "رکوردِ برگشتی همان اجرایِ خواسته است")

ev = client.get("/api/execution/events").json()
ck(ev["status"] == "success" and ev["count"] == len(ev["events"]),
   "سابقه شمارشِ درست دارد", "%s/%s" % (ev["count"], len(ev["events"])))
ck(all("payload" not in e for e in ev["events"]),
   "فهرستِ سابقه بدنهٔ خامِ ردِّپا را بیرون نمی‌دهد")
kinds = {e["kind"] for e in ev["events"]}
ck("cancel" in kinds, "رخدادِ لغو درِ سابقه ثبت شده است", str(sorted(kinds)))
by_kind = client.get("/api/execution/events?kind=cancel").json()
ck(all(e["kind"] == "cancel" for e in by_kind["events"]) and by_kind["count"] >= 1,
   "فیلترِ گونه واقعاً فیلتر می‌کند", str([e["kind"] for e in by_kind["events"]]))
by_symbol = client.get("/api/execution/events?symbol=هیچ‌چنین").json()
ck(by_symbol["status"] == "success" and by_symbol["count"] == 0,
   "فیلترِ نماد باِ نمادِ ناموجود صفر می‌دهد (و صفرِ واقعی، نه خطا)")
by_state = client.get("/api/execution/events?order_state=cancelled&execution_id=%s" % _eid).json()
ck(all(e["order_state"] == "cancelled" for e in by_state["events"]),
   "فیلترِ وضعیتِ سفارش اعمال می‌شود", str([e.get("order_state") for e in by_state["events"]]))
future = client.get("/api/execution/events?since=%d" % int(time.time() + 86400)).json()
ck(future["count"] == 0, "بازۀِ زمانیِ آینده هیچ ردیفی نمی‌آورد")
bad = client.get("/api/execution/events?since=دیروز").json()
ck(bad["status"] == "error" and bad["code"] == "INVALID_FILTER",
   "قالبِ تاریخِ بد Loud رد می‌شود", str(bad)[:160])

# راز درِ سابقه نمی‌نشیند: ردیفی باِ detailِ آلوده می‌کاریم و همان در را می‌خوانیم
_SECRET = "eyJhbGciOiJIUzI1NiJ9.V1122_SIGNATURE_LEAK.sig"
E._AUDIT.record(execution_id="V1122-SECRET", kind="state",
                detail="Authorization: Bearer %s" % _SECRET, symbol="فولاد",
                status="acknowledged", order_state="open")
sec = client.get("/api/execution/events?execution_id=V1122-SECRET").json()
blob = json.dumps(sec, ensure_ascii=False)
ck(sec["count"] == 1 and _SECRET not in blob and "<redacted>" in blob,
   "توکن درِ پاسخِ سابقه رد می‌شود (همان redactِ قرارداد)", blob[:170])

# کنترلِ منفی: اگر فیلتر بی‌اثر شود، سنجه‌هایِ بالا سبزِ جعلی می‌گیرند
_real_events = E._AUDIT.events
E._AUDIT.events = lambda *x, **k: list(_real_events(limit=500))
try:
    blind = client.get("/api/execution/events?kind=cancel").json()
    ck(blind["count"] == len(blind["events"])
       and any(e["kind"] != "cancel" for e in blind["events"]),
       "کنترلِ منفی: بی‌اعمالِ فیلتر، سنجۀِ «فیلترِ گونه» قرمز می‌شود")
finally:
    E._AUDIT.events = _real_events

# ═══════════════ ۳) مسیرِ زمان‌بندی (لغوِ پیشِ آتش) دست‌نخورده ═══════════════
# `GET /schedule/{id}` برایِ شناسۀِ بی‌زمان‌بندی **۲۰۰ باِ `state:"none"`** می‌دهد
# (نه «scheduledِ جعلی»، نه ۴۰۴ِ بی‌مفهوم درِ صفحه‌ای که فقط می‌خواهد بداند).
sch = client.get("/api/execution/schedule/V1122-NONE").json()
ck(sch.get("state") == "none" and sch.get("execution_id") == "V1122-NONE",
   "زمان‌بندیِ ناموجود «none» اعلام می‌شود، نه یکِ حالتِ ساختگی", str(sch)[:150])
ck(client.delete("/api/execution/schedule/V1122-NONE").status_code == 404,
   "لغوِ زمان‌بندیِ نبودنی ۴۰۴ است — باِ لغوِ سفارشِ واقعی یکی نیست")
matrix = client.get("/api/execution/timings").json()
ck("p50_ms" in json.dumps(matrix) or matrix.get("thin") is True or "phases" in matrix,
   "/timings شکلِ همیشگی‌اش را نگه داشته است", str(sorted(matrix.keys()))[:180])

if FAIL == 0:
    print("\n%d سنجه، 0 خطا" % PASS)
else:
    print("\n%d سنجه، %d خطا" % (PASS + FAIL, FAIL))
if SKIP:
    print("(%d سنجه SKIP شد)" % SKIP)
print("SARKHATI TAB GUARD " + ("OK" if FAIL == 0 else "FAILED"))
sys.exit(1 if FAIL else 0)
