"""api/execution.py — درِ محلیِ موتورِ اجرای سرخطی (Stage K — رابطِ نازک).

چیزی که این در **نیست**: هیچ راهِ ورود به کارگزاری. تنها adapterی که هرگز
ساخته می‌شود `MockBrokerAdapter` است و `dry_run` ثابتِ True — نه با بدنهٔ
درخواست، نه با تنظیم، نه با هیچ مسیرِ دیگری خاموش نمی‌شود. دلیلش در
`docs/execution/SARKHATI-ARCHITECTURE.md` §۹-ث است: دو رأیِ بازِ مالک (D8 کدام
سکوی موفید، D1 آیا PoC رویِ حسابِ واقعی مجاز است) پاسخ نگرفته‌اند، و بی‌آنها
حتی یک endpointِ واقعی صدا زده نمی‌شود.

چیزی که این در هست: همان سرویسِ `execution_service` که گاردهایِ `dev/execution_*`
می‌آزمایند — پیش‌فرود، آماده‌سازی، ارسالِ بدلی، دفترِ اجرا، reconcile و صفِ
سه‌حالته. پس رابطِ نازکِ UI قضاوتِ تازه‌ای نمی‌سازد و عددِ جعلی نمی‌بیند:
نبودِ نگاشتِ کارگزاری درِ `instrument` به‌شکلِ FAIL خوانده می‌شود، نه صفر.
"""
from __future__ import annotations

import dataclasses
import sqlite3
import threading
import uuid
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from bors_config import DB_PATH
from execution_contract import (
    BrokerError, Capabilities, ErrorCode, ExecutionRecord, ExecutionStatus,
    InstrumentRef, OrderDraft, OrderMode, Resolution, Side,
)
from execution_ledger import ARMED, HALT, TRIPPED, default_ledger
from execution_mock import MockBrokerAdapter
from execution_service import ExecutionError, ExecutionService, Limits

router = APIRouter()

_LOCK = threading.Lock()
#: تنها adapterِ ممکن؛ اگر روزی کسی اینجا کارگزاریِ واقعی بگذارد، همین ثابت
#: باید با رأیِ صریحِ مالک عوض شود (D8/D1).
ADAPTER_KIND = "mock"
DRY_RUN = True

#: ردِّپایِ ماندگار رویِ `user.db` + قفلِ توقفِ اضطراری. بی‌این، هر restart
#: «چه فرستادم و چه شد» را می‌سوزاند (بندِ ۵-۳ و ۶-۴ مأموریتِ ۱۴۰۵-۰۷-۲۳).
_AUDIT = default_ledger()


def _adapter() -> MockBrokerAdapter:
    # صف/وضعیت/لیست را بدل «می‌دهد» تا مسیرِ reconcile و پایشِ صف قابلِ دیدن
    # باشد؛ `balances` عمداً False است تا پیش‌فرود «بی‌داده» را از «صفر» جدا
    # نگه دارد (§۱۶ دستورِ کار).
    return MockBrokerAdapter(capabilities=Capabilities(
        place=True, list_orders=True, order_state=True,
        queue_position=True, cancel=True, best_bid_ask=False, balances=False))


_SERVICE = ExecutionService(_adapter(), dry_run=DRY_RUN, limits=Limits(), audit=_AUDIT)


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
        # صریحِ mock یک شناسهٔ بدل می‌چسباند و درِ پاسخ هم همان را اعلام می‌کند.
        ref = dataclasses.replace(
            ref, broker_instrument=f"MOCK:{symbol}",
            resolution=Resolution.EXACT if ref.isin else ref.resolution)
        _SERVICE.adapter.add_instrument(ref)
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


@router.get("/api/execution/status")
def get_status() -> dict[str, Any]:
    caps = _SERVICE.adapter.capabilities()
    stopped, kstate = _SERVICE.halted()
    return {
        "status": "success",
        "adapter": ADAPTER_KIND,
        "dry_run": DRY_RUN,
        "experimental": True,
        "live_enabled": False,
        "blocked_on": ["D8: کدام سکوی کارگزاری (EasyTrader/MTS یا Online-Plus/Titan)",
                       "D1: آیا PoC روی حساب واقعی مجاز است"],
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
    }


@router.post("/api/execution/preflight")
def post_preflight(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    draft = _draft_from(body)
    p = _SERVICE.preflight(draft)
    return {"status": "success", "adapter": ADAPTER_KIND, "dry_run": DRY_RUN,
            "execution_id": draft.execution_id,
            "instrument": dataclasses.asdict(draft.instrument),
            "checks": p.checks, "reasons": p.reasons, "ok": p.ok,
            "unknown": list(p.unknown)}


@router.post("/api/execution/prepare")
def post_prepare(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
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
            "payload_preview": prepared.payload_preview}


@router.post("/api/execution/dispatch")
def post_dispatch(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    draft = _draft_from(body)
    try:
        with _LOCK:
            prepared = _SERVICE.prepare(
                draft,
                target_wall_ms=body.get("target_wall_ms"),
                one_way_ms=float(body.get("one_way_ms") or 0.0),
                margin_ms=float(body.get("margin_ms") or 0.0),
                confirmed=bool(body.get("confirmed")))
            rec = _SERVICE.execute(prepared)
    except ExecutionError as e:
        return {"status": "error", "code": e.code.value, "detail": e.detail,
                "checks": e.checks, "execution_id": draft.execution_id}
    except BrokerError as e:
        return {"status": "error", "code": e.code.value, "detail": e.detail,
                "unknown_result": e.is_unknown_result, "execution_id": draft.execution_id}
    return {"status": "success", "adapter": ADAPTER_KIND, "dry_run": DRY_RUN,
            "kill_switch": _AUDIT.kill_state(),
            "record": _record_dict(rec)}


@router.post("/api/execution/reconcile/{execution_id}")
def post_reconcile(execution_id: str) -> dict[str, Any]:
    try:
        with _LOCK:
            rec = _SERVICE.reconcile(execution_id)
    except ExecutionError as e:
        raise HTTPException(404, f"{e.code.value}: {e.detail}") from None
    return {"status": "success", "record": _record_dict(rec)}


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
            "kill_switch": _AUDIT.kill_state(),
            # سفارش‌هایی که هنوز بسته نشده‌اند و باید بعدِ restart دیده/تطبیق شوند
            "open_ids": _AUDIT.open_ids(),
            "records": [_record_dict(r) for r in _SERVICE.ledger()]}


@router.get("/api/execution/limits")
def get_limits() -> dict[str, Any]:
    return {"status": "success", "limits": dataclasses.asdict(_SERVICE.limits),
            "codes": [c.value for c in ErrorCode]}


@router.post("/api/execution/halt")
def post_halt(body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """قفلِ توقفِ اضطراری: از همین لحظه هیچ سفارشِ تازه‌ای ساخته نمی‌شود.

    رویِ دیسک می‌نشیند، نه درِ حافظه — چون «متوقفم» نباید با یک restart پاک
    شود و برنامه دوباره با حالتِ «آماده» بالا بیاید (بندِ ۶-۴).
    """
    reason = str(body.get("reason") or "دستوری")
    state = TRIPPED if body.get("auto") is True else HALT
    with _LOCK:
        _AUDIT.set_kill(state, reason, actor=str(body.get("actor") or "user"))
    return {"status": "success", "kill_switch": _AUDIT.kill_state(),
            "halted": _AUDIT.halted(), "reason": reason,
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
    with _LOCK:
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
