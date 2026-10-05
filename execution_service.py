# -*- coding: utf-8 -*-
"""execution_service.py — ارکستراسیونِ اجرا: پیش‌فرود، آماده‌سازی، dispatch، reconcile.

مرجع: docs/execution/SARKHATI-ARCHITECTURE.md §۹ و §۱۰، و بندهایِ ۱۴/۱۵/۱۶/۲۰/۲۱/۲۸
دستورِ کار. این فایل *سرویس* است، نه روتر: هیچ `api/` و هیچ network درِ آن نیست،
پس نه hiddenimports لازم دارد نه تغییرِ spec.

سه حکمی که کداً بسته شده:

۱) **dry-run پیش‌فرض است.** تا وقتی مصرف‌کننده صریح `dry_run=False` ندهد، هیچ
   `submit_order` ای صدا زده نمی‌شود. بندِ ۲۸: «همهٔ مسیر اجرا شود ولی dispatch
   واقعی انجام نشود» — و این باید حالتِ پیش‌فرض باشد، نه گزینه‌ای که فراموش می‌شود.

۲) **mode فقط سیاستِ تأیید است، نه سیاستِ سرعتِ بی‌حد.** SAFE بعدِ ارسال
   تأییدِ مسدودکننده می‌گیرد؛ FAST نمی‌گیرد؛ ULTRA علاوه بر آن *باید* از پیش
   آماده شده باشد (`prepare()`) و بی‌آن رد می‌شود. هیچ حالتی retryِ خودکار
   ندارد (§۷-الف).

۳) **UNKNOWN با reconcile بسته می‌شود، نه با ارسالِ دوباره.** بعدِ
   `is_unknown_result` تنها مسیرِ مجاز `reconcile()` است؛ `execute()` دوباره
   همان `execution_id` را نمی‌فرستد (قرارداد هم DUPLICATE_GUARD می‌دهد).

چیزهایی که *حدس نمی‌زنیم*: نقدینگی اگر کارگزاری ندهد `UNKNOWN` می‌ماند؛ وضعیتِ
نشستِ بازار از یک `session_gate` تزریق‌شده می‌آید و نبودش یعنی UNKNOWN — چون
§۱-ه نشان داد ریپو سه پنجرۀِ متفاوت دارد و یک منبعِ حقیقت نیست.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

from execution_contract import (
    BrokerAdapter, BrokerError, Capabilities, ErrorCode, ExecutionRecord,
    ExecutionStatus, OrderDraft, OrderMode, OrderState, QueueSnapshot,
    TERMINAL_ORDER_STATES, Side,
)
from execution_timing import ClockState, DispatchPlan, Scheduler

PASS, FAIL_, UNKNOWN = "PASS", "FAIL", "UNKNOWN"


@dataclass(frozen=True)
class Limits:
    """گاردِ بندِ ۱۵. پیش‌فرضِ محافظه‌کارانه: یکِ سفارش، بی‌تکرار، بی‌قیمتِ کلان."""
    max_orders: int = 1
    max_total_value: float | None = None
    max_total_quantity: float | None = None
    require_confirmation: bool = True


@dataclass(frozen=True)
class ModePolicy:
    blocking_verify: bool
    requires_prepared: bool
    allow_repeat: bool

    @staticmethod
    def of(mode: OrderMode) -> "ModePolicy":
        if mode is OrderMode.SAFE:
            return ModePolicy(True, False, False)
        if mode is OrderMode.FAST:
            return ModePolicy(False, False, False)
        return ModePolicy(False, True, True)          # ULTRA


@dataclass(frozen=True)
class QueueView:
    """آنچه از صف می‌دانیم. سه حالتِ متفاوت، و تنها یکی «اطلاعات داریم» است.

    • `supported=False` ⇒ کارگزاری اصلاً صف نمی‌دهد (capability).
    • `supported=True` و `snapshot.known=False` ⇒ می‌دهد ولی برایِ این سفارش
      چیزی ندارد (هنوز درِ صف ننشسته، یا endpoint خاموش است).
    • `snapshot.known=True` ⇒ عددِ واقعی، همراه با `as_of`.

    هیچ‌کدام صفرِ «اولِ صف شدید» نمی‌سازد (§۱۸ دستورِ کار).
    """
    execution_id: str
    supported: bool
    snapshot: QueueSnapshot | None
    reason: str = ""
    terminal: bool = False

    @property
    def known(self) -> bool:
        return self.snapshot is not None and self.snapshot.known


@dataclass
class Preflight:
    checks: dict[str, str] = field(default_factory=dict)
    reasons: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not any(v == FAIL_ for v in self.checks.values())

    @property
    def unknown(self) -> tuple[str, ...]:
        return tuple(k for k, v in self.checks.items() if v == UNKNOWN)

    def add(self, name: str, state: str, reason: str = "") -> None:
        self.checks[name] = state
        if reason:
            self.reasons[name] = reason


@dataclass
class Prepared:
    draft: OrderDraft
    preflight: Preflight
    plan: DispatchPlan | None
    payload_preview: dict
    mode: OrderMode
    dry_run: bool

    @property
    def sendable(self) -> bool:
        return self.preflight.ok


class ExecutionError(Exception):
    """ردِ پیش‌فرود/لیمیت — پیش از آنکه چیزی به کارگزاری برود."""

    def __init__(self, code: ErrorCode, detail: str = "", *,
                 checks: Mapping[str, str] | None = None) -> None:
        super().__init__(f"{code.value}: {detail}" if detail else code.value)
        self.code = code
        self.detail = detail
        self.checks = dict(checks or {})


class ExecutionService:
    def __init__(self, adapter: BrokerAdapter, *,
                 scheduler: Scheduler | None = None,
                 dry_run: bool = True,
                 limits: Limits = Limits(),
                 session_gate: Callable[[int], str] | None = None) -> None:
        self.adapter = adapter
        self.scheduler = scheduler
        self.dry_run = dry_run
        self.limits = limits
        self.session_gate = session_gate
        self.confirmed_ids: set[str] = set()
        self._prepared: dict[str, Prepared] = {}
        self._ledger: dict[str, ExecutionRecord] = {}

    # ---- ۱) پیش‌فرود (بندِ ۱۶) --------------------------------------------
    def preflight(self, draft: OrderDraft) -> Preflight:
        p = Preflight()
        p.add("execution_id", PASS if (draft.execution_id or "").strip() else FAIL_)
        ok, reason = draft.instrument.orderable()
        p.add("instrument", PASS if ok else FAIL_, reason)
        p.add("side", PASS if isinstance(draft.side, Side) else FAIL_)
        p.add("price", PASS if draft.price and draft.price > 0 else FAIL_,
              "" if draft.price else "قیمتِ بدونِ منبع/مقدار")
        p.add("quantity", PASS if draft.quantity and draft.quantity > 0 else FAIL_)

        # نشستِ بازار: فقط از دروازهٔ تزریق‌شده؛ حدس نمی‌زنیم (§۱-ه)
        if self.session_gate is None:
            p.add("session", UNKNOWN, "no session gate injected")
        else:
            state = self.session_gate(0)
            p.add("session", PASS if state == "open" else
                  (UNKNOWN if state == "unknown" else FAIL_), str(state))

        # نقدینگی/موقعیت: اگر کارگزاری نمی‌دهد UNKNOWN، نه صفر
        caps: Capabilities = self.adapter.capabilities()
        if not caps.balances:
            p.add("balance", UNKNOWN, "broker exposes no balances")
        else:
            try:
                b = self.adapter.get_balances() or {}
                need = (draft.price or 0.0) * (draft.quantity or 0.0)
                cash = float(b.get("cash", 0.0) or 0.0)
                p.add("balance", PASS if (draft.side is not Side.BUY or cash >= need)
                      else FAIL_, f"cash={cash} need={need:.0f}")
            except BrokerError as e:
                p.add("balance", UNKNOWN, e.code.value)

        # تکراری‌بودن (بندِ ۱۹)
        p.add("duplicate", FAIL_ if draft.execution_id in self._ledger else PASS)
        # تواناییِ ارسال
        p.add("place", PASS if caps.place else FAIL_, "broker cannot place orders")
        return p

    # ---- ۲) آماده‌سازی (پیش از مهلت) --------------------------------------
    def prepare(self, draft: OrderDraft, *, target_wall_ms: int | None = None,
                one_way_ms: float = 0.0, margin_ms: float = 0.0,
                clock: ClockState | None = None,
                confirmed: bool = False) -> Prepared:
        policy = ModePolicy.of(draft.mode)
        p = self.preflight(draft)
        if not p.ok:
            raise ExecutionError(_code_for(p), "preflight failed", checks=p.checks)
        self._check_limits([draft])
        if policy.allow_repeat or draft.mode is OrderMode.ULTRA:
            if self.limits.require_confirmation and not confirmed:
                raise ExecutionError(ErrorCode.DUPLICATE_GUARD,
                                     "تکرار/ULTRA به تأییدِ صریحِ کاربر نیاز دارد")
            self.confirmed_ids.add(draft.execution_id)

        plan = None
        if target_wall_ms is not None and self.scheduler is not None:
            plan = self.scheduler.plan(target_wall_ms, one_way_ms=one_way_ms,
                                       margin_ms=margin_ms, clock=clock)
        preview = {
            "execution_id": draft.execution_id,
            "instrument": draft.instrument.broker_instrument,
            "isin": draft.instrument.isin,
            "side": draft.side.value,
            "price": draft.price,
            "quantity": draft.quantity,
            "mode": draft.mode.value,
            "dry_run": self.dry_run,
        }
        prepared = Prepared(draft=draft, preflight=p, plan=plan,
                            payload_preview=preview, mode=draft.mode,
                            dry_run=self.dry_run)
        self._prepared[draft.execution_id] = prepared
        return prepared

    # ---- ۳) اجرا ----------------------------------------------------------
    def execute(self, prepared: Prepared, *,
                sleep: Callable[[float], None] = time.sleep,
                yield_cpu: Callable[[], None] | None = None) -> ExecutionRecord:
        policy = ModePolicy.of(prepared.mode)
        if policy.requires_prepared and prepared.draft.execution_id not in self._prepared:
            # NOT_ORDERABLE یعنی «این نماد قابلِ سفارش نیست» — اینجا نماد
            # سالم است و فقط فراخوان *ترتیبِ مسیر* را رد می‌کند.
            raise ExecutionError(ErrorCode.INVALID_EXECUTION_ID,
                                 "ULTRA بی‌prepare() اجرا نمی‌شود")
        if not prepared.sendable:
            raise ExecutionError(_code_for(prepared.preflight), "preflight failed",
                                 checks=prepared.preflight.checks)

        if prepared.dry_run:
            rec = self._dry_run_record(prepared)
            self._ledger[rec.execution_id] = rec
            return rec

        if prepared.plan is not None and self.scheduler is not None:
            tel = self.scheduler.dispatch(
                prepared.plan,
                send=lambda: self._send_once(prepared.draft, policy).broker_order_id,
                sleep=sleep, yield_cpu=yield_cpu)
            rec = self._ledger[prepared.draft.execution_id]
            rec.drift_us = tel.drift_us
            rec.actual_send_wall_ms = tel.actual_send_wall_ms
            rec.clock_offset_ms = tel.clock_offset_ms
            return rec
        return self._send_once(prepared.draft, policy)

    def _send_once(self, draft: OrderDraft, policy: ModePolicy) -> ExecutionRecord:
        try:
            rec = self.adapter.submit_order(draft)
        except BrokerError as e:
            stored = self._ledger.get(draft.execution_id)
            if e.code is ErrorCode.DUPLICATE_GUARD:
                # ارسال از خطِ بیرون رد شده و چیزی به سرور نرفته؛ پس وضعیتِ
                # سفارشِ اول را بازنویسی نمی‌کنیم. اگر اینجا FAILED بگذاریم،
                # UNKNOWN_RESULT گم می‌شود و `reconcile()` دیگر دیرش نیست
                # (بندِ ۲۰/۲۱: بعدِ نامعلوم بودن فقط reconcile).
                if stored is not None:
                    stored.note("duplicate send refused: order state unchanged")
                raise
            if stored is None:
                stored = ExecutionRecord(execution_id=draft.execution_id,
                                         broker=self.adapter.name, account=None,
                                         symbol=draft.instrument.symbol,
                                         isin=draft.instrument.isin, side=draft.side,
                                         price=draft.price, quantity=draft.quantity,
                                         mode=draft.mode)
            stored.status = (ExecutionStatus.UNKNOWN_RESULT if e.is_unknown_result
                             else ExecutionStatus.FAILED)
            stored.error_code = e.code
            stored.error_detail = e.detail
            stored.attempts += 1
            stored.note(f"{e.code.value}: {e.detail}")
            self._ledger[draft.execution_id] = stored
            if e.is_unknown_result:
                # تنها پاسخِ مجاز: reconcile. ارسالِ دوباره درِ اینجا انجام نمی‌شود.
                return stored
            raise
        rec.attempts = max(rec.attempts, 1)
        self._ledger[draft.execution_id] = rec
        if policy.blocking_verify:
            self._verify(rec)
        return rec

    def _verify(self, rec: ExecutionRecord) -> None:
        caps = self.adapter.capabilities()
        if not (caps.order_state or caps.list_orders):
            rec.note("verify unavailable: broker exposes no order read-back")
            return
        found = self._read_back(rec, caps)
        rec.status = ExecutionStatus.RECONCILED if found is not None \
            else ExecutionStatus.UNKNOWN_RESULT
        if found is not None:
            _carry_state(rec, found, "verified")
        else:
            rec.note("not found in read-back")

    def _read_back(self, rec: ExecutionRecord,
                   caps: Capabilities) -> ExecutionRecord | None:
        """سفارشِ موجود را از سرور می‌پرسد. هیچ ارسالی نمی‌سازد و هیچ وضعیتی
        را از خود نمی‌سازد: نبودِ read-back ⇒ None ⇒ همان UNKNOWN.
        """
        if caps.order_state and rec.broker_order_id:
            found = self.adapter.get_order(rec.broker_order_id)
            if found is not None:
                return found
        if caps.list_orders:
            return next((o for o in self.adapter.get_orders()
                         if o.execution_id == rec.execution_id), None)
        return None

    def _dry_run_record(self, prepared: Prepared) -> ExecutionRecord:
        d = prepared.draft
        rec = ExecutionRecord(execution_id=d.execution_id, broker=self.adapter.name,
                              account=None, symbol=d.instrument.symbol,
                              isin=d.instrument.isin, side=d.side, price=d.price,
                              quantity=d.quantity, mode=d.mode,
                              status=ExecutionStatus.SCHEDULED
                              if prepared.plan else ExecutionStatus.VALIDATED)
        if prepared.plan is not None:
            rec.scheduled_at = prepared.plan.send_at_wall_ms / 1000.0
            rec.clock_offset_ms = prepared.plan.clock_offset_ms
        rec.note("dry-run: nothing was sent")
        rec.note(f"payload={prepared.payload_preview}")
        return rec

    # ---- ۴) reconcile (بندِ ۲۰/۲۱) ----------------------------------------
    def reconcile(self, execution_id: str) -> ExecutionRecord:
        rec = self._ledger.get(execution_id)
        if rec is None:
            raise ExecutionError(ErrorCode.INVALID_EXECUTION_ID,
                                 f"no such execution {execution_id}")
        if rec.status is not ExecutionStatus.UNKNOWN_RESULT:
            return rec
        caps = self.adapter.capabilities()
        if not caps.list_orders:
            rec.note("reconcile impossible: broker exposes no order list")
            return rec
        remote = self.adapter.get_orders()
        hit = next((o for o in remote if o.execution_id == execution_id), None)
        if hit is not None:
            rec.status = ExecutionStatus.RECONCILED
            rec.broker_order_id = hit.broker_order_id
            _carry_state(rec, hit, "reconciled from broker order list")
        else:
            rec.status = ExecutionStatus.FAILED
            rec.note("reconciled: broker has no such order")
        return rec

    # ---- ۴-پ) خواندنِ وضعیت / صف (بندِ ۱۸) ---------------------------------
    def refresh(self, execution_id: str) -> ExecutionRecord:
        """نظرِ سرور دربارهٔ سفارشِ *موجود*. هیچ ارسالی نمی‌کند.

        بعدِ `UNKNOWN_RESULT` باید `reconcile()` خوانده شود، نه این؛ `refresh`
        رویِ رکوردی که هنوز معلوم نیست چه شده، سفارشِ دوم نمی‌سازد و وضعیت را
        هم بی‌شواهد عوض نمی‌کند.
        """
        rec = self._ledger.get(execution_id)
        if rec is None:
            raise ExecutionError(ErrorCode.INVALID_EXECUTION_ID,
                                 f"no such execution {execution_id}")
        caps = self.adapter.capabilities()
        found = None
        if caps.order_state and rec.broker_order_id:
            found = self.adapter.get_order(rec.broker_order_id)
        if found is None and caps.list_orders:
            found = next((o for o in self.adapter.get_orders()
                          if o.execution_id == execution_id), None)
        if found is None:
            rec.note("refresh: read-back has nothing for this order")
            return rec
        _carry_state(rec, found, "refreshed from broker")
        if rec.status in (ExecutionStatus.ACKNOWLEDGED, ExecutionStatus.DISPATCHED):
            rec.status = ExecutionStatus.RECONCILED
        return rec

    def queue(self, execution_id: str) -> QueueView:
        caps = self.adapter.capabilities()
        rec = self._ledger.get(execution_id)
        if rec is None:
            raise ExecutionError(ErrorCode.INVALID_EXECUTION_ID,
                                 f"no such execution {execution_id}")
        if not caps.queue_position:
            return QueueView(execution_id, False, None,
                             "broker exposes no queue endpoint",
                             rec.order_state in TERMINAL_ORDER_STATES)
        if not rec.broker_order_id:
            return QueueView(execution_id, True, None,
                             "order id not known yet (nothing to ask about)",
                             rec.order_state in TERMINAL_ORDER_STATES)
        if rec.order_state in TERMINAL_ORDER_STATES:
            return QueueView(execution_id, True, None,
                             f"order already {rec.order_state.value}", True)
        snap = self.adapter.get_queue_position(rec.broker_order_id)
        if snap is None:
            return QueueView(execution_id, True, None,
                             "queue endpoint returned nothing", False)
        rec.queue_position = snap.position
        rec.volume_ahead = snap.volume_ahead
        rec.queue_as_of = snap.as_of
        rec.queue_series.append((snap.as_of or "", snap.position, snap.volume_ahead))
        return QueueView(execution_id, True, snap, "", False)

    def watch_queue(self, execution_id: str, samples: int = 3,
                    interval_ms: int = 500, *,
                    sleep: Callable[[float], None] = time.sleep) -> list[QueueView]:
        """چندِ مشاهدهٔ پیاپی از صف. «تغییرِ جایِ صف» بدونِ رشتهٔ زمان‌دار
        اندازه‌گیری نیست؛ و بی‌تواناییِ کارگزاری اصلاً سؤال نمی‌کند (§۱۸).
        """
        seen: list[QueueView] = []
        for i in range(max(1, int(samples))):
            view = self.queue(execution_id)
            seen.append(view)
            if not view.supported or view.terminal:
                break
            if i + 1 < max(1, int(samples)):
                sleep(interval_ms / 1000.0)
        return seen

    # ---- ۵) تکرار با گارد (بندِ ۱۵) ---------------------------------------
    def plan_repeat(self, draft: OrderDraft, count: int, delay_ms: int, *,
                    confirmed: bool = False) -> list[int]:
        policy = ModePolicy.of(draft.mode)
        if not policy.allow_repeat:
            raise ExecutionError(ErrorCode.UNSUPPORTED,
                                 f"mode {draft.mode.value} تکرار را مجاز نمی‌داند")
        if not confirmed and self.limits.require_confirmation:
            raise ExecutionError(ErrorCode.DUPLICATE_GUARD,
                                 "تکرار N سفارش به تأییدِ صریح نیاز دارد")
        self._check_limits([draft] * max(1, count))
        return [i * int(delay_ms) for i in range(max(1, count))]

    def _check_limits(self, drafts: Sequence[OrderDraft]) -> None:
        n = len(drafts)
        if n > self.limits.max_orders:
            raise ExecutionError(ErrorCode.DUPLICATE_GUARD,
                                 f"{n} سفارش از سقفِ {self.limits.max_orders} بیشتر است")
        total_value = sum((d.price or 0.0) * (d.quantity or 0.0) for d in drafts)
        total_qty = sum((d.quantity or 0.0) for d in drafts)
        if (self.limits.max_total_value is not None
                and total_value > self.limits.max_total_value):
            raise ExecutionError(ErrorCode.DUPLICATE_GUARD,
                                 f"ارزشِ کلِ {total_value:.0f} از سقف بیرون است")
        if (self.limits.max_total_quantity is not None
                and total_qty > self.limits.max_total_quantity):
            raise ExecutionError(ErrorCode.DUPLICATE_GUARD,
                                 f"تعدادِ کلِ {total_qty:.0f} از سقف بیرون است")

    # ---- کمکي ------------------------------------------------------------
    def _require(self, execution_id: str) -> ExecutionRecord:
        rec = self._ledger.get(execution_id)
        if rec is None:
            raise ExecutionError(ErrorCode.INVALID_EXECUTION_ID,
                                 f"no such execution {execution_id}")
        return rec

    def record(self, execution_id: str) -> ExecutionRecord | None:
        return self._ledger.get(execution_id)

    def ledger(self) -> list[ExecutionRecord]:
        return list(self._ledger.values())


def _carry_state(dst: ExecutionRecord, src: ExecutionRecord, why: str) -> None:
    """وضعیتِ سرور را به رکوردِ خودمان منتقل می‌کند — و فقط همان را که هست.

    `order_state` بی‌مقدارِ پیش‌فرض نمی‌ماند اگر سرور گفته؛ و اگر سرور نگفته،
    UNKNOWN می‌ماند. حجمِ خورده هم از سرور کپی می‌شود، نه محاسبه.
    """
    if src.order_state is not OrderState.UNKNOWN:
        dst.order_state = src.order_state
    if src.filled_quantity is not None:
        dst.filled_quantity = src.filled_quantity
    dst.note(why)


def _code_for(p: Preflight) -> ErrorCode:
    if p.checks.get("instrument") == FAIL_:
        return ErrorCode.NOT_ORDERABLE
    if p.checks.get("price") == FAIL_:
        return ErrorCode.INVALID_PRICE
    if p.checks.get("quantity") == FAIL_:
        return ErrorCode.INVALID_QUANTITY
    if p.checks.get("session") == FAIL_:
        return ErrorCode.MARKET_CLOSED
    if p.checks.get("duplicate") == FAIL_:
        return ErrorCode.DUPLICATE_GUARD
    if p.checks.get("place") == FAIL_:
        return ErrorCode.UNSUPPORTED
    return ErrorCode.BROKER_REJECTED


__all__ = ["ExecutionService", "ExecutionError", "Preflight", "Prepared", "QueueView",
           "Limits", "ModePolicy"]
