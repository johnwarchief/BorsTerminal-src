"""api/execution.py — درِ محلیِ موتورِ اجرای سرخطی (Stage K — رابطِ نازک).

چیزی که این در **نیست**: تصمیم‌گیرندهٔ «کجا وصل شویم». انتخابِ آداپتور فقط از
دو متغیرِ محیطیِ صریح خوانده می‌شود و از هیچ بدنهٔ درخواستی نه:

  BORS_EXECUTION_ADAPTER = mock | easytrader     (پیش‌فرض: mock)
  BORS_EXECUTION_LIVE    = 1                     (پیش‌فرض: خاموش)

تا «mock» یا تا LIVE نخورده باشد، `DRY_RUN` ثابتِ True می‌ماند و هیچ درخواستِ
برون‌سازمانی ساخته نمی‌شود. رأیِ مالک در ۱۴۰۵-۰۷-۲۴ سکوی هدف را تعیین کرد
(EasyTrader/Orbis-MTS، نه Mofid Online-Plus/Titan) — این همان D8 بسته‌شده است.
اما **D1 باز است**: نشستنِ به حسابِ واقعی دستِ خودِ مالک است (ورودِ تعاملی،
بی‌دورزدنِ CAPTCHA/MFA) و هیچ سفارشِ واقعی بی‌تأییدِ روشنِ او رویِ فرمِ نهایی
انجام نمی‌شود.

چیزی که این در هست: همان سرویسِ `execution_service` که گاردهایِ `dev/execution_*`
می‌آزمایند — پیش‌فرود، آماده‌سازی، ارسال، reconcile، صفِ سه‌حالته، قفلِ توقفِ
ماندگار و بازیابی پسِ restart. رابطِ نازکِ UI قضاوتِ تازه‌ای نمی‌سازد و عددِ
جعلی نمی‌بیند: نبودِ نگاشتِ کارگزاری درِ `instrument` به‌شکلِ FAIL خوانده
می‌شود، نه صفر؛ و `live_enabled` ازِ وضعیتِ واقعیِ آداپتور خوانده می‌شود، نه
ازِ یکِ ثابت.

token درِ همین پروسه و درِ حافظه می‌ماند (`POST /api/execution/session`): هیچ
مسیری آن را درِ فایل، دیتابیس، لاگ یا پاسخِ HTTP نمی‌نویسد.
"""
from __future__ import annotations

import dataclasses
import os
import sqlite3
import threading
import time
import uuid
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from bors_config import DB_PATH
from execution_contract import (
    BrokerAdapter, BrokerError, Capabilities, ErrorCode, ExecutionRecord,
    ExecutionStatus, InstrumentRef, OrderDraft, OrderMode, Resolution, Side,
)
from execution_easytrader import (
    EasyTraderAdapter, RefusingTransport, RequestsTransport, WIRE_HYPOTHESIS,
    easytrader_payload,
)
from execution_ledger import ARMED, HALT, TRIPPED, default_ledger
from execution_mock import MockBrokerAdapter
from execution_service import ExecutionError, ExecutionService, Limits
from execution_timing import Scheduler, TimeSource

router = APIRouter()

_LOCK = threading.Lock()
ADAPTER_ENV = "BORS_EXECUTION_ADAPTER"
LIVE_ENV = "BORS_EXECUTION_LIVE"
ALLOWED_ADAPTERS = ("mock", "easytrader")
#: آستانهٔ «فوری»: اگر مهلتِ هدف از این نزدیک‌تر باشد، درِ همان درخواست
#: می‌نشینیم و threadِ تازه‌ای نمی‌سازیم — هزینهٔ یکِ خوابِ کوتاه کمتر از یکِ
#: اجرایِ هم‌زمان است.
IMMEDIATE_WINDOW_MS = 250.0


def _env_flag(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in ("1", "true", "yes", "on")


def _configured_adapter() -> str:
    """انتخابِ آداپتور فقط ازِ محیط، و بی‌اعتبار ⇒ mock. هیچ بدنه‌ای اینجا رأی ندارد."""
    got = (os.environ.get(ADAPTER_ENV) or "").strip().lower()
    return got if got in ALLOWED_ADAPTERS else "mock"


#: تنها adapterهایِ ممکن. `easytrader` بی‌`LIVE_ENV` با `RefusingTransport`
#: می‌نشیند — یعنی کدِ آداپتور موجود و آزمودنی است، ولی هیچ سوکتی باز نمی‌شود.
ADAPTER_KIND = _configured_adapter()
LIVE_REQUESTED = ADAPTER_KIND == "easytrader" and _env_flag(LIVE_ENV)
DRY_RUN = not LIVE_REQUESTED

#: ردِّپایِ ماندگار رویِ `user.db` + قفلِ توقفِ اضطراری. بی‌این، هر restart
#: «چه فرستادم و چه شد» را می‌سوزاند (بندِ ۵-۳ و ۶-۴ مأموریتِ ۱۴۰۵-۰۷-۲۳).
_AUDIT = default_ledger()

#: ساعتِ dispatch: فقط ساعتِ سیستم. محدودیتش درِ `/status` اعلام می‌شود —
#: ادعایِ دقتِ NTP اینجا نوشته نمی‌شود (بندِ ۴-د مأموریت: «اگر فقط ساعت سیستم
#: در دسترس است، محدودیت آن را گزارش کن»).
_CLOCK_SOURCE = "system"
_CLOCK_LIMIT = ("ساعتِ سیستم بدونِ آفستِ NTP؛ زمان‌بندی رویِ monotonic است پس پرشِ "
                "ساعتِ دیواری dispatch را جابه‌جا نمی‌کند، ولی خودِ هدفِ دیواری "
                "قابلِ ادعایِ دقتِ میلی‌ثانیه نیست")
_SCHEDULER = Scheduler(TimeSource())

_EASYTRADER: EasyTraderAdapter | None = None


def _adapter() -> BrokerAdapter:
    global _EASYTRADER
    if ADAPTER_KIND == "easytrader":
        _EASYTRADER = EasyTraderAdapter(
            transport=RequestsTransport() if LIVE_REQUESTED else RefusingTransport())
        return _EASYTRADER
    # صف/وضعیت/لیست را بدل «می‌دهد» تا مسیرِ reconcile و پایشِ صف قابلِ دیدن
    # باشد؛ `balances` عمداً False است تا پیش‌فرود «بی‌داده» را از «صفر» جدا
    # نگه دارد (§۱۶ دستورِ کار).
    return MockBrokerAdapter(capabilities=Capabilities(
        place=True, list_orders=True, order_state=True,
        queue_position=True, cancel=True, best_bid_ask=False, balances=False))


_ACTIVE_ADAPTER = _adapter()
_SERVICE = ExecutionService(_ACTIVE_ADAPTER, dry_run=DRY_RUN, limits=Limits(),
                            audit=_AUDIT, scheduler=_SCHEDULER)


def _recover() -> int:
    """ردِّپا را به دفترِ حافظه برمی‌گرداند. چندتا؟ همین را /status اعلام می‌کند.

    چرا بی‌ساختنِ وضعیت: رکوردِ بازیابی‌شده همان آخرینِ حالتِ *دیده‌شده* را
    دارد. سفارشی که UNKNOWN_RESULT مانده، UNKNOWN می‌ماند و باید `reconcile`
    شود — نه اینکه restart خودش را «پذیرفته شد» جا بزند.
    """
    n = 0
    for eid in _AUDIT.open_ids():
        last = _AUDIT.latest_status(eid)
        if not last:
            continue
        try:
            side = Side(last["side"]) if last.get("side") else Side.BUY
            mode = OrderMode(last["mode"]) if last.get("mode") else OrderMode.SAFE
        except ValueError:
            continue
        rec = ExecutionRecord(
            execution_id=eid, broker=last.get("broker") or ADAPTER_KIND,
            account=None, symbol=last.get("symbol") or "", isin=None,
            side=side, price=last.get("price"), quantity=last.get("quantity"),
            mode=mode)
        st = (last.get("status") or "").lower()
        rec.status = next((s for s in ExecutionStatus if s.value == st),
                          ExecutionStatus.UNKNOWN_RESULT)
        rec.error_code = next((c for c in ErrorCode
                               if c.value == (last.get("error_code") or "")), None)
        rec.error_detail = last.get("detail") or ""
        rec.note("recovered from durable ledger after restart")
        _SERVICE.adopt(rec)
        n += 1
    if n:
        _AUDIT.record(execution_id="-", kind="recovery", status=ARMED,
                      detail="%d order(s) re-adopted from durable ledger" % n)
    return n


_RECOVERED = _recover()


def _draft_from(body: dict[str, Any]) -> OrderDraft:
    symbol = str(body.get("symbol") or "").strip()
    if not symbol:
        raise HTTPException(400, "نماد داده نشده")
    side_s = str(body.get("side") or "buy").strip().lower()
    try:
        side = Side(side_s)
    except ValueError:
        raise HTTPException(400, f"جهتِ نامعلوم: {side_s}") from None
    try:
        mode = OrderMode(str(body.get("mode") or "safe").strip().lower())
    except ValueError:
        raise HTTPException(400, "حالتِ نامعلوم") from None

    ref = _resolve_instrument(symbol)
    if body.get("mock_instrument") is True:
        # نگاشتِ کارگزاری عمداً «نیست» (§۱-ج). برایِ دیدنِ کلِ مسیر، درخواستِ
        # صریحِ mock یک شناسهٔ بدل می‌چسباند و درِ پاسخِ همان را هم اعلام می‌کند.
        ref = dataclasses.replace(
            ref, broker_instrument=f"MOCK:{symbol}",
            resolution=Resolution.EXACT if ref.isin else ref.resolution)
        if isinstance(_ACTIVE_ADAPTER, MockBrokerAdapter):
            _ACTIVE_ADAPTER.add_instrument(ref)
    elif ADAPTER_KIND == "easytrader" and ref.isin:
        # درِ این سکو شناسۀِ قابلِ سفارش **خودِ ISIN** است (مخزن ۲: `symbolIsin`،
        # نه ins_code). پس نگاشتِ کارگزاری حدس نیست، برداشتنِ همان ISIN است.
        # برایِ mock این شاخه اجرا نمی‌شود تا رفتارِ آزموده‌شده‌یِ پیشین دست‌نخورده
        # بماند (§۱-ج: بی‌`mock_instrument` هیچ نگاشتی ساخته نمی‌شود).
        ref = dataclasses.replace(ref, broker_instrument=ref.isin)
    price = body.get("price")
    qty = body.get("quantity")
    return OrderDraft(
        execution_id=str(body.get("execution_id") or f"x-{uuid.uuid4().hex[:12]}"),
        instrument=ref, side=side,
        price=float(price) if price is not None else None,
        quantity=float(qty) if qty is not None else None,
        mode=mode,
        price_source=str(body.get("price_source") or "unspecified"),
        price_as_of=body.get("price_as_of"),
    )


def _resolve_instrument(symbol: str) -> InstrumentRef:
    """شناسه‌هایِ canonical از همان بانکِ محلی — بی‌حدس، بی‌ساختنِ ISIN."""
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=15)
    except sqlite3.Error:
        return InstrumentRef(symbol=symbol)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT ins_code, isin FROM instruments WHERE TRIM(l_val18) = ? "
            "ORDER BY updated_at DESC LIMIT 1", (symbol,)).fetchall()
    except sqlite3.OperationalError:
        return InstrumentRef(symbol=symbol)
    finally:
        conn.close()
    if not rows:
        return InstrumentRef(symbol=symbol)
    r = rows[0]
    isin = (r["isin"] or "").strip() or None
    return InstrumentRef(symbol=symbol, ins_code=(r["ins_code"] or "").strip() or None,
                         isin=isin,
                         resolution=Resolution.EXACT if isin else Resolution.UNRESOLVED)


def _record_dict(rec: ExecutionRecord) -> dict[str, Any]:
    d = dataclasses.asdict(rec)
    # `events` نامِ فیلدِ ردِّپایِ داخلی است (`execution_contract.py:263`)؛
    # `notes` هرگز وجود نداشت و `getattr(..., ())` بی‌صدا فهرستِ رویدادها را
    # از پاسخِ HTTP حذف می‌کرد — یعنی همان چیزی که برایِ «چرا این سفارش رد
    # شد» لازم است، درِ UI هیچ‌وقت نمی‌رسید.
    d["events"] = list(rec.events)
    return d


def _live_now() -> bool:
    """وضعیتِ *الانِ* اتصال، از خودِ آداپتور — نه ازِ یکِ ثابت.

    سه چیز لازم است: آداپتورِ درست، ترافیکِ وصل‌شده، و tokenِ مالک. نبودِ هرکدام
    یعنی `live_enabled: false` و UI همان را می‌بیند.
    """
    return bool(getattr(_ACTIVE_ADAPTER, "live", False))


def _session_dict() -> dict[str, Any]:
    st = _ACTIVE_ADAPTER.session_status()
    return {"state": st.state.value, "account_label": st.account_label,
            "checked_at": st.checked_at}


# ── زمان‌بندیِ سرخطی: توقف‌پذیر، بی‌بلوکه‌کردنِ درِ halt ───────────────────────
_SCHEDULES: dict[str, dict[str, Any]] = {}
_SCHEDULE_LOCK = threading.Lock()


class ScheduleAborted(RuntimeError):
    """توقف پیش ازِ آتش — هیچ درخواستی ساخته نشد."""


def _abort_gate(execution_id: str) -> threading.Event:
    with _SCHEDULE_LOCK:
        entry = _SCHEDULES.get(execution_id) or {}
        ev = entry.get("abort")
        if ev is None:
            ev = threading.Event()
            entry.update({"abort": ev, "state": "waiting"})
            _SCHEDULES[execution_id] = entry
        return ev


def _gate_sleep(seconds: float, ev: threading.Event) -> None:
    """خوابِ تکه‌تکه، با بازرسیِ پرچمِ توقف درِ هر تکه.

    چرا تکه‌تکه: `Scheduler` تا آستانۀِ spin یکِ خوابِ درشت می‌کند؛ اگر آن خواب
    بی‌بازگشت باشد، «توقف» تا مهلت هیچ اثری ندارد و این همان چیزی است که درِ
    پنج مخزنِ مرجع نبود (پرچمِ در-حافظه که فقط پیشِ خرید خوانده می‌شود).
    """
    remaining = float(seconds)
    while remaining > 0:
        if ev.is_set():
            raise ScheduleAborted("توقفِ دستوری پیش ازِ آتش")
        step = min(0.2, remaining)
        time.sleep(step)
        remaining -= step


def _gate_spin(ev: threading.Event) -> None:
    if ev.is_set():
        raise ScheduleAborted("توقفِ دستوری پیش ازِ آتش")
    time.sleep(0.0005)


def _scheduled_send(prepared: Any, ev: threading.Event) -> None:
    """اجرا درِ threadِ پس‌زمینه؛ قفلِ سرویس فقط دورِ خودِ dispatch گرفته می‌شود."""
    eid = prepared.draft.execution_id
    out: dict[str, Any] = {"execution_id": eid, "state": "sending"}
    try:
        if ev.is_set():
            raise ScheduleAborted("توقفِ دستوری پیش ازِ آتش")
        with _LOCK:
            rec = _SERVICE.execute(prepared,
                                   sleep=lambda s: _gate_sleep(s, ev),
                                   yield_cpu=lambda: _gate_spin(ev))
        out.update({"state": "done", "record": _record_dict(rec)})
        _AUDIT.record(execution_id=eid, kind="schedule", status="done",
                      detail="scheduled dispatch executed")
    except ScheduleAborted as e:
        out.update({"state": "aborted", "detail": str(e)})
        _AUDIT.record(execution_id=eid, kind="schedule", status=HALT,
                      detail="aborted before fire (halt or explicit cancel)")
    except ExecutionError as e:
        out.update({"state": "refused", "code": e.code.value, "detail": e.detail,
                    "checks": e.checks})
        _AUDIT.record(execution_id=eid, kind="schedule", status="refused",
                      error_code=e.code.value, detail=e.detail)
    except BrokerError as e:
        out.update({"state": "unknown" if e.is_unknown_result else "error",
                    "code": e.code.value, "detail": e.detail,
                    "unknown_result": e.is_unknown_result})
        _AUDIT.record(execution_id=eid, kind="schedule",
                      status="unknown" if e.is_unknown_result else "error",
                      error_code=e.code.value, detail=e.detail)
    except Exception as e:                                      # noqa: BLE001
        out.update({"state": "error", "code": "UNKNOWN_RESULT",
                    "detail": "%s: %s" % (type(e).__name__, e)})
    finally:
        with _SCHEDULE_LOCK:
            entry = _SCHEDULES.get(eid) or {"abort": ev}
            entry.update(out)
            _SCHEDULES[eid] = entry


def _schedule_status(execution_id: str) -> dict[str, Any]:
    with _SCHEDULE_LOCK:
        got = _SCHEDULES.get(execution_id)
    if not got:
        return {"execution_id": execution_id, "state": "none"}
    return {k: v for k, v in got.items() if k != "abort"}


def _halt_pending(reason: str) -> int:
    """پرچمِ توقف را به همهٔ زمان‌بندی‌هایِ درِ انتظار می‌دهد. تعدادِ لغوشده‌ها."""
    with _SCHEDULE_LOCK:
        pending = [e for e in _SCHEDULES.values()
                   if e.get("state") in ("waiting", "scheduled") and e.get("abort")]
    for e in pending:
        e["abort"].set()
    return len(pending)


def _wire_preview(draft: OrderDraft) -> dict[str, Any] | None:
    """پیش‌نمایشِ *بدنۀِ واقعی* که به کارگزاری می‌رود — برایِ تأییدِ آگاهانه.

    درِ mock چیزی اینجا نیست (بدل بدنۀِ سیم ندارد) و `None` برمی‌گردد؛ UI «بی‌
    پیش‌نمایش» نشان می‌دهد نه یکِ بدنهٔ جعلی.
    """
    if ADAPTER_KIND != "easytrader":
        return None
    return easytrader_payload(draft)


@router.get("/api/execution/status")
def get_status() -> dict[str, Any]:
    caps = _ACTIVE_ADAPTER.capabilities()
    stopped, kstate = _SERVICE.halted()
    live = _live_now()
    blocked: list[str] = []
    if ADAPTER_KIND == "mock":
        blocked.append("آداپتورِ واقعی انتخاب نشده (BORS_EXECUTION_ADAPTER=easytrader)")
    if ADAPTER_KIND == "easytrader" and not LIVE_REQUESTED:
        blocked.append("ترافیکِ زنده خاموش است (BORS_EXECUTION_LIVE=1 لازم است)")
    if ADAPTER_KIND == "easytrader" and LIVE_REQUESTED and not live:
        blocked.append("D1: نشستِ مالک درِ حافظه نیست — ورودِ تعاملی با خودِ مالک")
    return {
        "status": "success",
        "adapter": ADAPTER_KIND,
        "dry_run": DRY_RUN,
        "experimental": True,
        # وضعیتِ واقعی، نه ثابت: live یعنی آداپتورِ درست + ترافیکِ وصل + tokenِ مالک.
        "live_enabled": live,
        # «چیزی از این ماشین بیرون نمی‌رود» = یا dry-run است یا نشستی نداریم.
        # جدا از `dry_run` اعلام می‌شود تا `dry_run` دروغِ دو طرفه نگویَد: هم
        # «flag روشن است ولی نشست نیست» و هم «flag خاموش است» یک معنا دارند.
        "nothing_will_leave_the_machine": bool(DRY_RUN or not live),
        "live_requested": LIVE_REQUESTED,
        "wire_hypothesis": (ADAPTER_KIND == "easytrader") and WIRE_HYPOTHESIS,
        "session": _session_dict(),
        "blocked_on": blocked,
        "capabilities": dataclasses.asdict(caps),
        "limits": dataclasses.asdict(_SERVICE.limits),
        "ledger_size": len(_SERVICE.ledger()),
        # حالتِ قفلِ توقف و شمارشِ ماندگار: UI باید «متوقف» را از «هیچ سفارشی
        # نبوده» جدا ببیند، نه اینکه بی‌داده را صفر بخواند.
        "kill_switch": kstate,
        "halted": stopped,
        "kill_reason": _AUDIT.kill_reason(),
        "durable_events": len(_AUDIT.events(limit=1000)),
        "recovered_after_restart": _RECOVERED,
        "audit_db": _AUDIT.db_path,
        "clock_source": _CLOCK_SOURCE,
        "clock_limit": _CLOCK_LIMIT,
        "scheduled_pending": sum(1 for e in _schedule_all()
                                 if e.get("state") in ("waiting", "scheduled")),
    }


def _schedule_all() -> list[dict[str, Any]]:
    with _SCHEDULE_LOCK:
        return [{k: v for k, v in e.items() if k != "abort"} for e in _SCHEDULES.values()]


@router.get("/api/execution/session")
def get_session() -> dict[str, Any]:
    """وضعیتِ نشست — هیچ‌وقت مقدارِ token نه. UI فقط *حالت* می‌بیند."""
    return {"status": "success", "adapter": ADAPTER_KIND, "live": _live_now(),
            "dry_run": DRY_RUN, "session": _session_dict(),
            "token_present": _has_token()}


def _has_token() -> bool:
    check = getattr(_ACTIVE_ADAPTER, "has_token", None)
    return bool(check()) if callable(check) else False


@router.post("/api/execution/session")
def post_session(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """نشست را درِ حافظه می‌گذارد. هیچ مسیرِ دیگری token نمی‌نویسد.

    ورودِ تعاملی کارگزاری (CAPTCHA/MFA/پیامک) درِ حیطۀِ این برنامه نیست و دور
    زده نمی‌شود؛ مالک خودش درِ مرورگر وارد می‌شود و نشانه‌ای که خودش در دسترس
    دارد را اینجا می‌گذارد. بی‌`BORS_EXECUTION_LIVE=1` این کار فقط وضعیت را
     «آماده‌به‌آزمون» می‌کند، نه متصل.
    """
    token = str(body.get("token") or "").strip()
    if ADAPTER_KIND != "easytrader":
        return {"status": "error", "code": ErrorCode.UNSUPPORTED.value,
                "detail": "آداپتورِ فعال token نمی‌پذیرد (adapter=%s)" % ADAPTER_KIND,
                "session": _session_dict()}
    if not LIVE_REQUESTED or not isinstance(_ACTIVE_ADAPTER, EasyTraderAdapter):
        # نگه‌داشتنِ credential درِ حافظه برایِ مسیری که هیچ‌وقت ترافیک نمی‌زند
        # فقط سطحِ نشتی را بالا می‌برد، نه قابلیت را.
        return {"status": "error", "code": ErrorCode.UNSUPPORTED.value,
                "detail": "ترافیکِ زنده خاموش است — token ذخیره نمی‌شود "
                          "(BORS_EXECUTION_LIVE=1 لازم است)",
                "session": _session_dict()}
    if not token:
        return {"status": "error", "code": "MISSING_TOKEN",
                "detail": "هیچ نشانی داده نشد — نشست پاک نمانده"}
    _ACTIVE_ADAPTER.set_token(token)
    return {"status": "success", "live": _live_now(), "dry_run": DRY_RUN,
            "session": _session_dict(),
            "capabilities": dataclasses.asdict(_ACTIVE_ADAPTER.capabilities()),
            "detail": ("token فقط درِ حافظه ماند؛ با restart می‌میرد و هیچ‌جا "
                       "نوشته/لاگ نمی‌شود")}


@router.delete("/api/execution/session")
def delete_session() -> dict[str, Any]:
    if isinstance(_ACTIVE_ADAPTER, EasyTraderAdapter):
        _ACTIVE_ADAPTER.clear_token()
    return {"status": "success", "live": _live_now(), "session": _session_dict()}


@router.post("/api/execution/probe")
def post_probe() -> dict[str, Any]:
    """آزمونِ اتصالِ کم‌خطر: فقط پرسیدنی‌هایِ خواندنی، صفرِ سفارش.

    درِ `/order` هرگز برایِ سنجشِ سرعت یا «آیا وصلیم» زده نمی‌شود؛ مرجع‌ها همین
    کار را می‌کردند (مخزن ۲ با سفارشِ واقعی) و ما ردش کردیم.
    """
    probe = getattr(_ACTIVE_ADAPTER, "probe", None)
    if probe is None:
        return {"status": "error", "code": ErrorCode.UNSUPPORTED.value,
                "detail": "این adapter آزمونِ اتصال ندارد (adapter=%s)" % ADAPTER_KIND,
                "read_only": True, "order_endpoint_touched": False}
    with _LOCK:
        got = probe()
    return {"status": "success" if got.get("ok") else "error", **got}


@router.post("/api/execution/preflight")
def post_preflight(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    draft = _draft_from(body)
    p = _SERVICE.preflight(draft)
    return {"status": "success", "adapter": ADAPTER_KIND, "dry_run": DRY_RUN,
            "live": _live_now(), "execution_id": draft.execution_id,
            "instrument": dataclasses.asdict(draft.instrument),
            "checks": p.checks, "reasons": p.reasons, "ok": p.ok,
            "unknown": list(p.unknown)}


@router.post("/api/execution/prepare")
def post_prepare(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    t0 = time.monotonic()
    draft = _draft_from(body)
    try:
        with _LOCK:
            prepared = _SERVICE.prepare(
                draft,
                target_wall_ms=body.get("target_wall_ms"),
                one_way_ms=float(body.get("one_way_ms") or 0.0),
                margin_ms=float(body.get("margin_ms") or 0.0),
                confirmed=bool(body.get("confirmed")))
    except ExecutionError as e:
        return {"status": "error", "code": e.code.value, "detail": e.detail,
                "checks": e.checks, "execution_id": draft.execution_id}
    return {"status": "success", "execution_id": draft.execution_id,
            "mode": prepared.mode.value, "dry_run": prepared.dry_run,
            "sendable": prepared.sendable,
            "checks": prepared.preflight.checks,
            "plan": dataclasses.asdict(prepared.plan) if prepared.plan else None,
            "payload_preview": prepared.payload_preview,
            # بدنهٔ واقعیِ سیم — چیزی که اگر اتصال وصل باشد می‌رود. ثابتِ
            # `WIRE_HYPOTHESIS` درِ `/status` می‌گوید این هنوز فرضیه است.
            "wire_preview": _wire_preview(draft),
            "wire_hypothesis": (ADAPTER_KIND == "easytrader") and WIRE_HYPOTHESIS,
            "timings": {"prepared_ms": round((time.monotonic() - t0) * 1000, 1),
                        "dispatch_ms": None, "response_ms": None,
                        "observed_ms": None}}


@router.post("/api/execution/dispatch")
def post_dispatch(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    t0 = time.monotonic()
    draft = _draft_from(body)
    target = body.get("target_wall_ms")
    try:
        with _LOCK:
            prepared = _SERVICE.prepare(
                draft,
                target_wall_ms=target,
                one_way_ms=float(body.get("one_way_ms") or 0.0),
                margin_ms=float(body.get("margin_ms") or 0.0),
                confirmed=bool(body.get("confirmed")))
    except ExecutionError as e:
        return {"status": "error", "code": e.code.value, "detail": e.detail,
                "checks": e.checks, "execution_id": draft.execution_id}

    wait_ms = None
    if prepared.plan is not None:
        wait_ms = prepared.plan.send_at_wall_ms - int(time.time() * 1000)
    if wait_ms is not None and wait_ms > IMMEDIATE_WINDOW_MS:
        # زمان‌بندی‌شده: درِ همان درخواست نمی‌خوابیم، چون «توقف» باید همان لحظه
        # پاسخ‌گو باشد. نتیجه را UI ازِ /schedule و /ledger می‌خواند.
        ev = _abort_gate(draft.execution_id)
        with _SCHEDULE_LOCK:
            entry = _SCHEDULES[draft.execution_id]
            entry.update({"state": "scheduled", "send_at_wall_ms":
                          prepared.plan.send_at_wall_ms, "target_wall_ms":
                          prepared.plan.target_wall_ms})
        threading.Thread(target=_scheduled_send, args=(prepared, ev),
                         name="bors-schedule-%s" % draft.execution_id,
                         daemon=True).start()
        return {"status": "scheduled", "adapter": ADAPTER_KIND, "dry_run": DRY_RUN,
                "kill_switch": _AUDIT.kill_state(),
                "execution_id": draft.execution_id,
                "send_at_wall_ms": prepared.plan.send_at_wall_ms,
                "wait_ms": wait_ms,
                "payload_preview": prepared.payload_preview,
                "timings": {"prepared_ms": round((time.monotonic() - t0) * 1000, 1),
                            "dispatch_ms": None, "response_ms": None,
                            "observed_ms": None}}

    try:
        with _LOCK:
            rec = _SERVICE.execute(prepared)
    except ExecutionError as e:
        return {"status": "error", "code": e.code.value, "detail": e.detail,
                "checks": e.checks, "execution_id": draft.execution_id}
    except BrokerError as e:
        return {"status": "error", "code": e.code.value, "detail": e.detail,
                "unknown_result": e.is_unknown_result,
                "execution_id": draft.execution_id}
    dispatch_ms = round((time.monotonic() - t0) * 1000, 1)
    return {"status": "success", "adapter": ADAPTER_KIND, "dry_run": DRY_RUN,
            "live": _live_now(),
            "kill_switch": _AUDIT.kill_state(),
            "record": _record_dict(rec),
            "timings": {"prepared_ms": None, "dispatch_ms": dispatch_ms,
                        "response_ms": rec.rtt_ms,
                        # «مشاهدهٔ سفارش» با «پذیرش» یکی نیست (§۴-ج): تا
                        # reconcile/queue آن را اندازه نگیرد، None است.
                        "observed_ms": None}}


@router.get("/api/execution/schedule/{execution_id}")
def get_schedule(execution_id: str) -> dict[str, Any]:
    return {"status": "success", **_schedule_status(execution_id)}


@router.delete("/api/execution/schedule/{execution_id}")
def delete_schedule(execution_id: str) -> dict[str, Any]:
    """لغوِ یکِ زمان‌بندی پیش ازِ آتش. پس ازِ POST هیچ‌چیز لغو نمی‌شود و این
     «لغو شد» را ادعا نمی‌کند."""
    with _SCHEDULE_LOCK:
        entry = _SCHEDULES.get(execution_id)
    if not entry:
        raise HTTPException(404, "no such schedule: %s" % execution_id)
    ev = entry.get("abort")
    state = entry.get("state")
    if state in ("waiting", "scheduled") and ev is not None:
        ev.set()
        return {"status": "success", "execution_id": execution_id,
                "aborted": True, "note": "پیش ازِ آتش لغو شد"}
    return {"status": "success", "execution_id": execution_id, "aborted": False,
            "state": state,
            "note": "زمان‌بندی دیگر درِ انتظار نیست — وضعیت از /ledger خوانده می‌شود"}


@router.post("/api/execution/reconcile/{execution_id}")
def post_reconcile(execution_id: str) -> dict[str, Any]:
    try:
        with _LOCK:
            rec = _SERVICE.reconcile(execution_id)
    except ExecutionError as e:
        raise HTTPException(404, f"{e.code.value}: {e.detail}") from None
    return {"status": "success", "record": _record_dict(rec)}


@router.post("/api/execution/refresh/{execution_id}")
def post_refresh(execution_id: str) -> dict[str, Any]:
    """نظرِ تازهٔ سرور دربارهٔ سفارشِ *موجود*. هیچ ارسالی نمی‌سازد."""
    t0 = time.monotonic()
    try:
        with _LOCK:
            rec = _SERVICE.refresh(execution_id)
    except ExecutionError as e:
        raise HTTPException(404, f"{e.code.value}: {e.detail}") from None
    return {"status": "success", "record": _record_dict(rec),
            "observed_ms": round((time.monotonic() - t0) * 1000, 1)}


@router.get("/api/execution/queue/{execution_id}")
def get_queue(execution_id: str) -> dict[str, Any]:
    try:
        v = _SERVICE.queue(execution_id)
    except ExecutionError as e:
        raise HTTPException(404, f"{e.code.value}: {e.detail}") from None
    return {"status": "success", "execution_id": v.execution_id,
            "supported": v.supported, "known": v.known, "reason": v.reason,
            "terminal": v.terminal,
            "snapshot": dataclasses.asdict(v.snapshot) if v.snapshot else None}


@router.get("/api/execution/ledger")
def get_ledger() -> dict[str, Any]:
    return {"status": "success", "adapter": ADAPTER_KIND, "dry_run": DRY_RUN,
            "live": _live_now(),
            "kill_switch": _AUDIT.kill_state(),
            # سفارش‌هایی که هنوز بسته نشده‌اند و باید بعدِ restart دیده/تطبیق شوند
            "open_ids": _AUDIT.open_ids(),
            "scheduled": _schedule_all(),
            "records": [_record_dict(r) for r in _SERVICE.ledger()]}


@router.get("/api/execution/limits")
def get_limits() -> dict[str, Any]:
    return {"status": "success", "limits": dataclasses.asdict(_SERVICE.limits),
            "codes": [c.value for c in ErrorCode]}


@router.post("/api/execution/halt")
def post_halt(body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """قفلِ توقفِ اضطراری: از همین لحظه هیچ سفارشِ تازه‌ای ساخته نمی‌شود.

    رویِ دیسک می‌نشیند، نه درِ حافظه — چون «متوقفم» نباید با یک restart پاک
    شود و برنامه دوباره با حالتِ «آماده» بالا بیاید (بندِ ۶-۴). زمان‌بندی‌هایِ
    درِ انتظار هم همین‌جا لغو می‌شوند: توقفی که فقط جلویِ «بعدی‌ها» را بگیرد و
    آن یکی که درِ صفِ خواب است را رها کند، توقف نیست.
    """
    reason = str(body.get("reason") or "دستوری")
    state = TRIPPED if body.get("auto") is True else HALT
    # عمداً بی‌`_LOCK`: قفلِ سرویس ممکن است موقعِ یکِ POSTِ ۷ ثانیه‌ای گرفته شده
    # باشد و «توقف» نباید پشتِ آن بایستد. خودِ ledger قفلِ رشته‌ایِ دارد.
    _AUDIT.set_kill(state, reason, actor=str(body.get("actor") or "user"))
    aborted = _halt_pending(reason)
    return {"status": "success", "kill_switch": _AUDIT.kill_state(),
            "halted": _AUDIT.halted(), "reason": reason,
            "aborted_schedules": aborted,
            "dry_run": DRY_RUN, "adapter": ADAPTER_KIND}


@router.post("/api/execution/resume")
def post_resume(body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """بازکردنِ قفل. صریح و با ردِّپا — بی‌این هیچ مسیری «خاموش» را «آماده» نمی‌کند.

    حالتِ `TRIPPED` (خودکار: ضرر روزانه، دادهٔ کهنه) بی‌`confirm=True` باز نمی‌شود:
    توقفی که موتورِ ریسک انداخته باید دستِ انسان لازم باشد، نه یک درخواستِ GET.
    """
    state = _AUDIT.kill_state()
    if state == TRIPPED and body.get("confirm") is not True:
        return {"status": "error", "code": "HALTED",
                "detail": "توقفِ خودکارِ ریسک بی‌confirm=True باز نمی‌شود",
                "kill_switch": state}
    reason = str(body.get("reason") or "ادامهٔ دستوری")
    _AUDIT.set_kill(ARMED, reason, actor=str(body.get("actor") or "user"))
    return {"status": "success", "kill_switch": _AUDIT.kill_state(),
            "halted": _AUDIT.halted(), "reason": reason,
            "open_ids": _AUDIT.open_ids()}


@router.get("/api/execution/audit/{execution_id}")
def get_audit(execution_id: str) -> dict[str, Any]:
    """ردِّپایِ کاملِ یکِ سفارش، از کهنه به تازه — بی‌secret (redact رویِ دیسک)."""
    ev = _AUDIT.trail(execution_id)
    return {"status": "success", "execution_id": execution_id,
            "found": bool(ev), "events": ev,
            "latest": ev[-1] if ev else None}
