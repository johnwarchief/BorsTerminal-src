# -*- coding: utf-8 -*-
"""execution_autoclick_scheduler.py — حلقۀ اجرایِ زمان‌بندی‌شده با دقتِ میلی‌ثانیه.

چرا pollingِ ساده کافی نیست: با tickِ ۲۰۰ میلی‌ثانیه‌ای، «شروعِ ۰۹:۰۰:۰۰.۰۰۰»
در عمل تا ۲۰۰ms دیر می‌افتد و همان فاصله، همان چیزی است که سرخطی را می‌بازد.
این حلقه دو فاز دارد: خوابِ بلند تا نزدیکِ هدف (با Event.wait، بی‌مصرفِ CPU) و
spinِ کوتاهِ پایانی رویِ monotonic. اندازهٔ spin از تنظیمات می‌آید و در گزارش
تلمتری به‌عنوان «آخرین فاصلۀ مانده» ثبت می‌شود.

مسئولیت‌ها:
  • فقط یک اجرا هم‌زمان (تضمینش در store است، اینجا دوباره چک می‌شود).
  • بودجۀ نرخ پیش از claim گرفته می‌شود؛ ردِ نرخ = توقف، نه تلاشِ دوباره.
  • هر نتیجۀ مبهم (UNKNOWN / دیده‌نشدنِ درخواست / BLOCKED) ادامه را می‌بندد.
  • توقفِ اضطراری به شبکه وابسته نیست: Eventِ محلی + لغوِ ردیف‌ها درِ store.
  • warm-up: پیش از هدف، فرم و دکمه ارزیابی می‌شوند تا در لحظه فقط چک‌هایِ تازه
    بماند؛ warm ناموفق یعنی BLOCKED، نه کلیک.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional

from execution_autoclick_run import (
    A_BLOCKED, A_CANCELLED, A_DONE, A_SKIPPED, ARMED, BLOCKED, COMPLETED,
    DEFAULT_MISSED_GRACE_MS, MISSED_TARGET, NEEDS_REVIEW, RUNNING, WARMING,
    ActionRecord, RunError, RunRecord, TERMINAL_NO_RETRY)

#: فاصلۀ بیشینه بینِ دو بیداریِ حلقه (ثانیه)؛ برایِ واکنشِ سریع‌تر به توقف/تغییرِ وضعیت.
MAX_SLEEP_S = 0.20
#: چکِ تازه‌بودنِ وضعیتِ اجرا در هر دور؛ پیش‌فرضِ محافظه‌کارانه.
DEFAULT_STOP_POLL_S = 0.05

#: نتایجی که ادامهٔ اجرا را می‌بندند: ابهام، نبودِ درخواستِ دیده‌شده، یا قطعِ نشست.
#: «ردِ قطعیِ کارگزاری» (REJECTED) ادامه می‌دهد — بند ۶ مأموریت: وقتی پاسخ قطعی
#: دیده شده و کاربر حالت چندباره را با تعدادِ مشخص فعال کرده، اقدامِ مستقلِ بعدی
#: مجاز است. اما شاهدِ محدودیتِ نرخ (stop_run) همیشه اجرا را می‌بندد.
STOP_RESULTS = set(TERMINAL_NO_RETRY) | {"NOT_SENT", "NO_REQUEST", "BROWSER_LOST",
                                         "SESSION_LOST", "MISMATCH", "PAGE_CHANGED",
                                         "NO_BUTTON", "NO_USABLE_BUTTON",
                                         "WRONG_SIDE_ONLY", "STOPPED"}
CONTINUE_RESULTS = ("ACCEPTED", "REJECTED", "DRY_RUN", "FILLED", "CANCELLED")


def allows_continuation(state: str, outcome: Mapping[str, Any]) -> bool:
    """آیا بعدِ این اقدام، رفتن به اقدامِ بعدی مجاز است؟"""
    if bool(outcome.get("stop_run")):
        return False
    if str(state) in STOP_RESULTS:
        return False
    return str(state) in CONTINUE_RESULTS


@dataclass
class FireHooks:
    """پلِ executor به شمارندهٔ پایدار. executor بی‌این نمی‌تواند بشمارد."""
    run_id: str
    idx: int
    store: Any
    stop_event: threading.Event

    def mark_fired(self, at_ms: Optional[int] = None) -> bool:
        """اقدام را «شلیک‌شده» ثبت می‌کند. False یعنی کلیک نکن: کسی پیش‌تر شلیک کرد."""
        ms = int(at_ms if at_ms is not None else time.time() * 1000)
        return bool(self.store.mark_fired(self.run_id, self.idx, at_ms=ms))

    def should_stop(self) -> bool:
        return self.stop_event.is_set()

    def remaining_budget_ok(self) -> tuple[bool, str]:
        rec = self.store.get(self.run_id)
        if int(rec.fired_actions) >= int(rec.config.total_actions):
            return False, "سقفِ تعدادِ این اجرا (%d) خورده شده" % rec.config.total_actions
        return True, ""


@dataclass
class TickReport:
    action_idx: Optional[int] = None
    fired: bool = False
    outcome: dict[str, Any] = field(default_factory=dict)
    transition: str = ""
    detail: str = ""
    slept_s: float = 0.0

    def public(self) -> dict[str, Any]:
        return {"action_idx": self.action_idx, "fired": bool(self.fired),
                "transition": self.transition, "detail": self.detail[:240],
                "slept_s": round(self.slept_s, 4), "outcome": dict(self.outcome)}


class AutoClickRunRunner:
    """زمان‌بندِ اجرا. executor را می‌خواند و نتیجه را درِ store ثبت می‌کند."""

    def __init__(self, store: Any, *, executor: Callable[[RunRecord, ActionRecord,
                                                          FireHooks], Mapping[str, Any]],
                 limiter: Any = None, warm: Optional[Callable[[RunRecord], Mapping[str, Any]]]
                 = None, halt_check: Optional[Callable[[], tuple[bool, str]]] = None,
                 status_sink: Optional[Callable[[dict[str, Any]], None]] = None,
                 clock: Callable[[], float] = time.monotonic,
                 wall_ms: Optional[Callable[[], int]] = None,
                 account: str = "easytrader",
                 spin_ms: float = 12.0,
                 missed_grace_ms: int = DEFAULT_MISSED_GRACE_MS) -> None:
        self.store = store
        self.executor = executor
        self.limiter = limiter
        self._warm = warm
        self._halt_check = halt_check
        self._status_sink = status_sink
        self._clock = clock
        self._wall_ms = wall_ms or (lambda: int(time.time() * 1000))
        self.account = str(account)
        self.spin_ms = max(0.0, float(spin_ms))
        self.missed_grace_ms = int(missed_grace_ms)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._last: dict[str, Any] = {}

    # ---- lifecycle ----
    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop,
                                            name="bors-autoclick-runner", daemon=True)
            self._thread.start()

    def stop(self, *, reason: str = "توقفِ اضطراری") -> dict[str, Any]:
        """توقفِ محلی: Event + لغوِ ردیف‌ها؛ به هیچ تماسِ شبکه‌ای نیاز ندارد.

        deliberate stop → STOPPED (با reset_for_restart ادامه می‌یابد)؛ kill-switchِ
        خودکار یا restartِ نیمه‌تمام → NEEDS_REVIEW، چون آنجا وضعیتِ اقدامِ قبل
        روشن نیست.
        """
        self._stop.set()
        cancelled = 0
        run = self.store.active_run(self.account)
        if run is not None:
            try:
                cancelled = self.store.cancel_pending(run.run_id, reason)
                self.store.stop(run.run_id, reason)
            except RunError:
                pass
        return {"stopped": True, "reason": reason, "cancelled_actions": cancelled}

    @property
    def alive(self) -> bool:
        return bool(self._thread is not None and self._thread.is_alive())

    def close(self, *, join_s: float = 2.0) -> None:
        self._stop.set()
        th = self._thread
        if th is not None:
            th.join(timeout=join_s)
        self._thread = None

    def status(self) -> dict[str, Any]:
        return dict(self._last)

    # ---- حلقه ----
    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                rep = self.tick_and_wait()
            except Exception as e:                       # noqa: BLE001
                self._last = {"error": "%s: %s" % (type(e).__name__, str(e)[:160]),
                              "at_wall_ms": self._wall_ms()}
                self._stop.wait(0.25)
                continue
            if self._status_sink is not None:
                try:
                    self._status_sink(rep.public())
                except Exception:                       # noqa: BLE001
                    pass

    def next_due_ms(self, run: RunRecord) -> Optional[int]:
        for a in run.actions:
            if a.state in ("PENDING", "CLAIMED"):
                return int(a.planned_at_ms)
        return None

    def tick_and_wait(self) -> TickReport:
        run = self.store.active_run(self.account)
        if run is None:
            self._stop.wait(MAX_SLEEP_S)
            return TickReport(detail="no active run", slept_s=MAX_SLEEP_S)
        due = self.next_due_ms(run)
        now = self._wall_ms()
        if due is None:
            return self.tick()
        # ۱) warm-up پیش از هدف
        if run.state == ARMED:
            warm_at = int(run.config.planned_first_at_ms()) - int(run.config.prewarm_ms or 0)
            if now >= warm_at:
                if self._warm is None:
                    #: بی‌hookِ warm فقط وضعیت عوض می‌شود؛ چک‌هایِ ضروری و تازه درِ
                    #: executor همان لحظه انجام می‌شوند.
                    self.store.set_state(run.run_id, RUNNING, reason="شروعِ زمان‌بندی")
                else:
                    got = self._run_warm(run)
                    if not got.get("ok"):
                        return TickReport(transition=BLOCKED,
                                          detail=str(got.get("reason", ""))[:240],
                                          outcome=dict(got))
        # ۲) خوابِ بلند تا نزدیکِ هدف
        lead = max(0, due - now)
        if lead > int(self.spin_ms) + 5:
            self._stop.wait(min(lead / 1000.0, MAX_SLEEP_S))
            return TickReport(slept_s=min(lead / 1000.0, MAX_SLEEP_S),
                              detail="waiting for %s" % (run.run_id))
        # ۳) spinِ پایانی رویِ monotonic تا رسیدنِ زمانِ هدف
        spin_deadline = self._clock() + (lead / 1000.0) + 0.05
        while (not self._stop.is_set()) and self._wall_ms() < due \
                and self._clock() < spin_deadline:
            pass
        return self.tick()

    def _run_warm(self, run: RunRecord) -> dict[str, Any]:
        self.store.set_state(run.run_id, WARMING, reason="ارزیابیِ پیش‌از‌هدفِ فرم و دکمه")
        try:
            got = dict(self._warm(run) if self._warm is not None else {"ok": True})
        except Exception as e:                           # noqa: BLE001
            got = {"ok": False, "reason": "warm failed: %s" % type(e).__name__}
        if got.get("ok"):
            self.store.set_state(run.run_id, RUNNING, reason="warm OK")
        else:
            self.store.set_state(run.run_id, BLOCKED,
                                 reason=str(got.get("reason", ""))[:240],
                                 validation={"warm": got})
        self._last = {"warm": got, "at_wall_ms": self._wall_ms()}
        return got

    # ---- یک دورِ کامل ----
    def tick(self) -> TickReport:
        run = self.store.active_run(self.account)
        if run is None:
            return TickReport(detail="no active run")
        if self._stop.is_set():
            return TickReport(detail="stop requested")
        halted, why = self._halted()
        if halted:
            self.store.cancel_pending(run.run_id, "kill-switch")
            self.store.set_state(run.run_id, NEEDS_REVIEW, reason=why)
            return TickReport(transition=NEEDS_REVIEW, detail=why)
        now = self._wall_ms()
        # از دست رفتنِ هدف: بی‌catch-up (سفارشِ دیرهنگام جایگزینِ برنامهٔ از دست رفته نمی‌شود)
        if int(run.fired_actions) == 0 and run.state != MISSED_TARGET:
            last_planned = int(run.config.planned_last_at_ms())
            if now > last_planned + self.missed_grace_ms:
                self.store.cancel_pending(run.run_id, "missed target")
                self.store.set_state(run.run_id, MISSED_TARGET,
                                     reason="از زمانِ هدف گذشته است و هیچ اقدامی اجرا نشده؛ "
                                            "catch-up نمی‌شود")
                return TickReport(transition=MISSED_TARGET, detail="missed target")
        action = self.store.claim_next(run.run_id, at_ms=now, token="runner")
        if action is None:
            rec = self.store.get(run.run_id)
            if int(rec.fired_actions) >= int(rec.config.total_actions):
                self.store.set_state(rec.run_id, COMPLETED, reason="همۀ اقدام‌ها انجام شد")
                return TickReport(transition=COMPLETED, detail="all actions done")
            if self.next_due_ms(rec) is None:
                self.store.set_state(rec.run_id, COMPLETED, reason="ردیفِ مانده‌ای نیست")
                return TickReport(transition=COMPLETED, detail="nothing left")
            return TickReport(detail="not due yet")
        # بودجۀ نرخ پیش از اجرا؛ رد = توقفِ صریح، نه تلاشِ دوباره
        if self.limiter is not None:
            #: پیش‌چکِ بی‌مصرف: بودجه فقط وقتی اقدام واقعاً شلیک شد خرج می‌شود،
            #: وگرنه یک ردِ validationِ بی‌کلیک، سهمیۀ بی‌کلیک می‌خورد.
            dec = self.limiter.try_acquire(run.config.account, consume=False)
            if not dec.ok:
                self.store.finish_action(run.run_id, action.idx, state=A_BLOCKED,
                                         result={"reason": dec.reason,
                                                 "blocked_by": dec.blocked_by,
                                                 "retry_after_s": dec.retry_after_s,
                                                 "kind": dec.kind,
                                                 "rule_source": dec.rule_source,
                                                 "attributed_to_broker": dec.attributed_to_broker})
                rec = self.store.set_state(run.run_id, BLOCKED,
                                           reason="محدودیت نرخ: %s" % str(dec.reason)[:180])
                return TickReport(action_idx=action.idx, transition=BLOCKED,
                                  detail=str(dec.reason)[:240],
                                  outcome={"decision": dec.public()})
        hooks = FireHooks(run_id=run.run_id, idx=action.idx, store=self.store,
                          stop_event=self._stop)
        try:
            outcome = dict(self.executor(run, action, hooks) or {})
        except Exception as e:                           # noqa: BLE001
            outcome = {"state": "UNKNOWN",
                       "reason": "%s: %s" % (type(e).__name__, str(e)[:160]),
                       "exception": True}
        state = str(outcome.get("state") or "UNKNOWN")
        if self.limiter is not None and bool(outcome.get("fired")):
            self.limiter.record(run.config.account)
            seen = self.limiter.observe_response(
                status=outcome.get("http_status"), body=outcome.get("response_body"),
                headers=outcome.get("response_headers"), account=run.config.account,
                where="autoclick-action-%s" % action.idx)
            if seen is not None:
                outcome["throttle_lockout_s"] = seen
        #: ردیفِ BLOCKED یعنی کلیک رویِ دکمه نرفت؛ ردیفِ DONE یعنی شلیک ثبت شد.
        if not bool(outcome.get("fired")):
            a_state = A_BLOCKED
        elif state == "SKIPPED":
            a_state = A_SKIPPED
        else:
            a_state = A_DONE
        rec = self.store.finish_action(run.run_id, action.idx, state=a_state,
                                       result=outcome)
        rep = TickReport(action_idx=action.idx, fired=bool(outcome.get("fired")),
                         outcome=outcome, detail=str(outcome.get("reason", ""))[:240])
        if not allows_continuation(state, outcome):
            self.store.cancel_pending(run.run_id, "نتیجۀ %s" % state)
            self.store.set_state(run.run_id, BLOCKED if state == "BLOCKED" else NEEDS_REVIEW,
                                 reason="اقدامِ %s به %s رسید؛ ادامه نمی‌دهد"
                                        % (action.idx, state))
            rep.transition = NEEDS_REVIEW
            return rep
        if int(rec.fired_actions) >= int(rec.config.total_actions):
            self.store.set_state(run.run_id, COMPLETED, reason="سقفِ تعدادِ اجرا خورده شد")
            rep.transition = COMPLETED
        return rep

    def _halted(self) -> tuple[bool, str]:
        if self._halt_check is None:
            return False, ""
        try:
            got = self._halt_check()
        except Exception as e:                           # noqa: BLE001
            #: بررسیِ توقفِ اضطراری بی‌موقعیت نمی‌شود؛ شکستش یعنی «متوقف باش».
            return True, "halt check failed: %s" % type(e).__name__
        if isinstance(got, tuple) and len(got) == 2:
            return bool(got[0]), str(got[1] or "")
        return bool(got), "kill switch"

    # ---- اجرایِ همگامِ تستی ----
    def drain(self, *, until_wall_ms: int, step_ms: int = 50) -> list[TickReport]:
        """حلقه را بی‌thread پیش می‌برد؛ برایِ گاردها با ساعتِ ساختگی."""
        out: list[TickReport] = []
        guard = 0
        while guard < 5000:
            guard += 1
            now = self._wall_ms()
            run = self.store.active_run(self.account)
            if run is None:
                break
            due = self.next_due_ms(run)
            if due is not None and due > until_wall_ms:
                break
            rep = self.tick()
            out.append(rep)
            if rep.transition in (COMPLETED, NEEDS_REVIEW, BLOCKED, MISSED_TARGET):
                break
            if due is None and rep.action_idx is None:
                break
            if step_ms <= 0:
                continue
        return out


__all__ = ["AutoClickRunRunner", "FireHooks", "TickReport", "STOP_RESULTS",
           "CONTINUE_RESULTS", "allows_continuation",
           "MAX_SLEEP_S", "DEFAULT_STOP_POLL_S"]
