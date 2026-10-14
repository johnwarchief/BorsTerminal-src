# -*- coding: utf-8 -*-
"""paper_trading.py — رباتِ کاغذی: سیگنال ← پیش‌فرود/ریسک ← پرشدنِ شبیه‌سازی‌شده.

مأموریتِ ۱۴۰۵-۰۷-۲۳، بندِ ۶-۳. **هیچ سفارشی به بازار ارسال نمی‌شود**: تنها
adapterِ این فایل `PaperBroker` است که یکِ حسابِ شبیه‌سازی‌شده رویِ دیسکِ خودِ
کاربر نگه می‌دارد. این جایگزینِ اتصالِ کارگزاری نیست و ادعایِ آن را هم ندارد —
ادعایش این است که زنجیرۀ «تصمیم → ریسک → وضعیتِ سفارش → ردِّپا → بازیابی»
واقعاً اجرا و آزموده می‌شود، پیشِ آنکه پولی درگیر شود.

چه چیزی مشترک است و چرا:
• مدلِ پرشدن/حساب/هزینه از `trade_sim` — همان چیزی که `backtest_engine` می‌خواند.
  دو مدلِ متفاوت یعنی دو عددِ متفاوت برایِ یکِ روز؛ مقایسۀ بک‌تست و paper آن
  وقت بی‌محتوا می‌شود.
• قفلِ توقف و ردِّپا از `execution_ledger` (رویِ `user.db`) — همان چیزی که
  دروازۀ سرخطی می‌نویسد. یکِ دفتر، دو مصرف‌کننده.
• ماشینِ حالتِ سفارش از `execution_service` (پیش‌فرود، limitها، reconcile) —
  رباتِ کاغذی و مسیرِ واقعی یکِ داور دارند، نه دو تا.

لوحِ زمانی عمداً مثلِ بک‌تست است: سیگنالِ روز T درِ روز T+1 اجرا می‌شود، چون
«با ردیفِ امروز تصمیم گرفت و با همان امروز خرید» نشتِ اطلاعات است، نه سرعت.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

from execution_contract import (
    BrokerAdapter, BrokerError, Capabilities, ErrorCode, ExecutionRecord,
    ExecutionStatus, InstrumentRef, OrderDraft, OrderMode, OrderState,
    QueueSnapshot, Resolution, SessionState, SessionStatus, Side,
)
from execution_ledger import ARMED, TRIPPED, ExecutionLedger
from execution_service import ExecutionService, Limits, RiskContext
from trade_sim import BUY, SELL, Bar, CostModel, SimAccount, apply_fill

#: کلیدِ وضعیتِ حساب درِ جدولِ flags — تنها راهِ بازیابی پسِ restart.
STATE_KEY = "paper_account"
HISTORY_KEY = "paper_history"


def order_id(symbol: str, date: str, action: str) -> str:
    """ شناسهٔ بی‌تکرار: یکِ نماد در یکِ روز برایِ یکِ جهت فقط یکِ بار فرستاده
    می‌شود — حتی پسِ restart، چون ردِّپا رویِ دیسک است.
    """
    return "paper:%s:%s:%s" % (symbol, date, action)


class PaperBroker(BrokerAdapter):
    """کارگزاریِ شبیه‌سازی‌شده. `place` دارد، صفِ جعلی ندارد.

    وضعیتِ سفارش فقط از *پرشدنی که واقعاً رخ داده* ساخته می‌شود؛ اگر ردیفِ
    آن روز نرسیده باشد، سفارش درِ `PENDING` می‌ماند — نه `FILLED` با حدس.
    """
    name = "paper"

    def __init__(self, account: SimAccount, *, costs: CostModel | None = None,
                 sizing_fraction: float = 0.1,
                 limits: Mapping[str, object] | None = None) -> None:
        self.account = account
        self.costs = costs or CostModel()
        self.sizing_fraction = float(sizing_fraction)
        self.limits = dict(limits or {})
        self.orders: dict[str, ExecutionRecord] = {}
        self.by_exec: dict[str, ExecutionRecord] = {}
        self._seq = 0
        self._bars: dict[str, Bar] = {}
        self._session = SessionStatus(SessionState.CONNECTED, "paper-account")
        #: شمارشِ تماس‌ها — برایِ اثباتِ «بی‌ارسالِ دوم» درِ آزمون‌ها
        self.submit_calls = 0

    # ---- قرارداد ---------------------------------------------------------
    def capabilities(self) -> Capabilities:
        return Capabilities(place=True, list_orders=True, order_state=True,
                            queue_position=False, cancel=True, best_bid_ask=False,
                            balances=True)

    def authenticate(self) -> SessionStatus:
        return self._session

    def session_status(self) -> SessionStatus:
        return self._session

    def set_session(self, st: SessionStatus) -> None:
        self._session = st

    def resolve_instrument(self, symbol: str) -> InstrumentRef:
        return InstrumentRef(symbol=symbol, ins_code=None, isin="PAPER-" + symbol,
                             broker_instrument=symbol, resolution=Resolution.EXACT)

    def add_instrument(self, ref: InstrumentRef) -> None:
        pass

    def on_bar(self, bar: Bar) -> None:
        """تازترین ردیفِ هر نماد؛ تنها منبعِ قیمتِ این نشست."""
        self._bars[bar.symbol] = bar

    def validate_order(self, draft: OrderDraft) -> str | None:
        ok, why = draft.instrument.orderable()
        return None if ok else why

    def submit_order(self, draft: OrderDraft) -> ExecutionRecord:
        if draft.execution_id in self.by_exec:
            raise BrokerError(ErrorCode.DUPLICATE_GUARD,
                              "%s پیش‌تر ثبت شده" % draft.execution_id)
        self.submit_calls += 1
        bar = self._bars.get(draft.instrument.symbol)
        if bar is None:
            raise BrokerError(ErrorCode.QUEUE_UNAVAILABLE,
                              "ردیفی برایِ این نماد نرسیده — پرشدن نامعلوم")
        self._seq += 1
        rec = ExecutionRecord(execution_id=draft.execution_id, broker=self.name,
                              account="paper", symbol=draft.instrument.symbol,
                              isin=draft.instrument.isin, side=draft.side,
                              price=draft.price, quantity=draft.quantity,
                              mode=draft.mode, status=ExecutionStatus.DISPATCHED,
                              broker_order_id="P%d" % self._seq, attempts=1)
        side = "buy" if draft.side is Side.BUY else "sell"
        # `draft.price` مبنایِ *حجم‌سنجی* است (بستۀ روزِ تصمیم)، نه سفارشِ limit؛
        # فرستادنش به‌عنوانِ limit_price یعنی هر خریدی که آغازِ روزِ بعد بالاتر
        # از بستۀ دیروز باشد رد شود — درِ بازارِ صعودی یعنی «هرگز پر نمی‌شود».
        # بستۀ *همهٔ* موقعیت‌هایِ باز لازم است: `apply_fill` ارزشِ باز را با
        # equity حساب می‌کند و اگر قیمتِ یکِ نمادِ دیگر درِ این فهرست نباشد،
        # «رسیدگی‌نشده» با «نرسیده» یکی می‌شود و هر خریدِ دوم بی‌دلیل stale
        # رد می‌شد. این فهرست را از ردیف‌هایِ خودِ broker می‌سازیم، نه از حدس.
        marks: dict[str, float | None] = {}
        for s in list(self.account.positions) + [draft.instrument.symbol]:
            b = self._bars.get(s)
            marks[s] = None if b is None or b.close is None else float(b.close)
        marks.setdefault(draft.instrument.symbol,
                         float(bar.close) if bar.close is not None else None)
        fill = apply_fill(self.account, action=side, symbol=draft.instrument.symbol,
                          bar=bar, costs=self.costs, fraction=self.sizing_fraction,
                          requested_qty=draft.quantity, exposure_by_symbol=marks,
                          **self.limits)
        if not fill.ok:
            rec.status = ExecutionStatus.FAILED
            rec.order_state = OrderState.REJECTED
            rec.error_code = (ErrorCode.MARKET_CLOSED if fill.reason == "halted"
                              else ErrorCode.BROKER_REJECTED)
            rec.error_detail = "%s: %s" % (fill.reason, fill.detail)
        elif fill.reason == "partial":
            rec.status = ExecutionStatus.ACKNOWLEDGED
            rec.order_state = OrderState.PARTIAL
            rec.filled_quantity = fill.quantity
            rec.note("partial fill at %.0f" % fill.price)
        else:
            rec.status = ExecutionStatus.ACKNOWLEDGED
            rec.order_state = OrderState.FILLED
            rec.filled_quantity = fill.quantity
            rec.note("filled at %.0f fee=%.0f" % (fill.price, fill.fee))
        rec.response_at = time.time()
        self.orders[rec.broker_order_id or ""] = rec
        self.by_exec[rec.execution_id] = rec
        return rec

    def get_orders(self) -> list[ExecutionRecord]:
        return list(self.by_exec.values())

    def get_order(self, broker_order_id: str) -> ExecutionRecord | None:
        return self.orders.get(broker_order_id)

    def get_queue_position(self, broker_order_id: str) -> QueueSnapshot | None:
        return None      # capability false ⇒ هیچ عددی ساخته نمی‌شود

    def cancel_order(self, broker_order_id: str) -> bool:
        rec = self.orders.get(broker_order_id)
        if rec is None or rec.order_state in (OrderState.FILLED, OrderState.CANCELLED,
                                              OrderState.REJECTED):
            return False
        rec.order_state = OrderState.CANCELLED
        rec.note("cancelled")
        return True

    def get_balances(self) -> Mapping[str, float]:
        prices = {s: (b.close if b else None) for s, b in self._bars.items()}
        eq = self.account.equity(prices)
        return {"cash": float(self.account.cash),
                # None درِ equity یعنی کهنگی؛ اینجا عمداً منتقل می‌شود تا
                # پیش‌فرود آن را «بی‌داده» بداند نه «صفر».
                "equity": eq,
                "realized_today": float(self.account.realized_today),
                "realized_total": float(self.account.realized_total)}


@dataclass
class PaperDecision:
    """چیزی که ربات درِ هر نشست اعلام می‌کند — برایِ UI/ردِّپا، نه برایِ نمایشِ عددِ جعلی."""
    date: str
    signals: int
    dispatched: int
    rejected: int
    equity: float | None
    halt_state: str
    notes: list[str] = field(default_factory=list)


class PaperSession:
    """یکِ رباتِ کاغذی: استراتژی + جریانِ ردیف + داورِ ریسک + ردِّپا.

    `fail_closed` پیش‌فرض true است: با ردیفِ کهنگ‌شده یا بی‌ردیف هیچ سفارشی
    ساخته نمی‌شود. بندِ ۶-۳: «با داده stale، ناقص یا نامعتبر fail closed شود».
    """

    def __init__(self, *, strategy, ledger: ExecutionLedger,
                 account: SimAccount | None = None,
                 costs: CostModel | None = None,
                 limits: Limits | None = None,
                 sizing_fraction: float = 0.1,
                 max_stale_sessions: int = 1,
                 epoch: Callable[[], float] = time.time,
                 fail_closed: bool = True) -> None:
        self.costs = costs or CostModel()
        self.sizing_fraction = float(sizing_fraction)
        self.account = account or SimAccount(start_cash=100_000_000.0)
        self.broker = PaperBroker(self.account, costs=self.costs,
                                  sizing_fraction=self.sizing_fraction)
        self.limits = limits or Limits(max_orders=1, require_confirmation=False)
        self.ledger = ledger
        self.strategy = strategy
        self.max_stale_sessions = int(max_stale_sessions)
        self.epoch = epoch
        self.fail_closed = fail_closed
        self.history: dict[str, list[Bar]] = {}
        self.last_seen: dict[str, str] = {}
        self._seen_sessions: list[str] = []
        self.service = ExecutionService(self.broker, dry_run=False, audit=ledger,
                                        limits=self.limits,
                                        risk_ctx=self._risk_context, epoch=epoch)

    # ---- ریسک و کهنگی ----------------------------------------------------
    def _prices(self) -> dict[str, float | None]:
        """بستۀ آخرِ ردیفِ هر موقعیت؛ نبودِ ردیف ⇒ None (کهنگی، نه صفر)."""
        out: dict[str, float | None] = {}
        for s in self.account.positions:
            b = self._latest(s)
            out[s] = None if b is None or b.close is None else float(b.close)
        return out

    def _risk_context(self, draft: OrderDraft) -> RiskContext:
        prices = self._prices()
        exposure: dict[str, float | None] = {}
        for s in self.account.positions:
            px = prices.get(s)
            exposure[s] = None if px is None else self.account.position(s).quantity * px
        return RiskContext(exposure_by_symbol=exposure,
                           exposure_total=self.account.exposure(prices),
                           realized_pnl_today=self.account.realized_today,
                           data_as_of_epoch=self.epoch(), source="paper-account")

    def _latest(self, symbol: str) -> Bar | None:
        seq = self.history.get(symbol)
        return seq[-1] if seq else None

    def stale(self, symbol: str, date: str) -> bool:
        """فاصلۀ نشستیِ نماد از نشستِ جاری. بی‌ردیف ⇒ کهنگی، نه صفرِ داده.

        «چند روز تقویمی» نه: شمارشِ *نشست‌هایِ دیده‌شده*، چون تعطیلاتِ طولانی
        نباید یکِ نمادِ سالم را کهنگ بنامد.
        """
        seen_at = self.last_seen.get(symbol)
        if seen_at is None or seen_at not in self._seen_sessions:
            return True
        gap = self._seen_sessions.index(date) - self._seen_sessions.index(seen_at)
        return gap > self.max_stale_sessions

    def _size(self, action: str, symbol: str, price: float | None,
              requested: float | None) -> float:
        """حجمِ سفارش از حقوقِ *امروز* و نقدِ حساب. `None` هیچ‌جا صفر نمی‌شود.

        چرا پیشِ draft تعیین می‌شود: پیش‌فرودِ قرارداد حجمِ نامعلوم را
        `INVALID_QUANTITY` می‌خواند (درست هم هست — سفارشِ بی‌عدد به کارگزاری
        نمی‌رود)، پس sizing باید اینجا اتفاق بیفتد، نه درِ مدلِ پرشدن.
        """
        if price is None or price <= 0:
            return 0.0
        if action == SELL:
            held = self.account.held(symbol)
            return float(min(requested, held) if requested else held)
        eq = self.account.equity(self._prices())
        if eq is None:
            return 0.0
        budget = eq * float(self.sizing_fraction)
        if requested:
            budget = min(budget, float(requested) * price)
        qty = math.floor(min(budget, self.account.cash) / price)
        return float(max(0.0, qty))

    # ---- وضعیت رویِ دیسک -------------------------------------------------
    def persist(self) -> None:
        self.ledger.save_state(STATE_KEY, self.account.snapshot())
        self.ledger.save_state(HISTORY_KEY, {"sessions": self._seen_sessions[-400:],
                                             "last_seen": self.last_seen})

    def recover(self) -> bool:
        """وضعیتِ حساب را از دیسک برمی‌گرداند و سفارش‌هایِ باز را به سرویس می‌دهد.

        بی‌این، restart همه‌چیز را «صفرِ موقعیت، بی‌سفارشِ باز» نشان می‌داد —
        یعنی دقیقاً همان وضعیتی که بندِ ۶-۳ ممنوعش کرده.
        """
        snap = self.ledger.load_state(STATE_KEY)
        loaded = False
        if snap:
            self.account.__dict__.update(SimAccount.restore(snap).__dict__)
            self.broker.account = self.account
            loaded = True
        hist = self.ledger.load_state(HISTORY_KEY)
        if hist:
            self._seen_sessions = list(hist.get("sessions") or [])
            self.last_seen = dict(hist.get("last_seen") or {})
            loaded = True
        for eid in self.ledger.open_ids():
            last = self.ledger.latest_status(eid)
            if not last:
                continue
            rec = ExecutionRecord(execution_id=eid, broker=last.get("broker") or "paper",
                                  account="paper", symbol=last.get("symbol") or "", isin=None,
                                  side=Side(last["side"]) if last.get("side") else Side.BUY,
                                  price=last.get("price"), quantity=last.get("quantity"),
                                  mode=OrderMode(last["mode"]) if last.get("mode") else OrderMode.SAFE)
            st = (last.get("status") or "").lower()
            rec.status = next((s for s in ExecutionStatus if s.value == st),
                              ExecutionStatus.UNKNOWN_RESULT)
            rec.error_detail = last.get("detail") or ""
            rec.note("recovered after restart")
            self.service.adopt(rec)
            loaded = True
        return loaded

    # ---- حلقهٔ ربات -------------------------------------------------------
    def on_bar(self, bar: Bar) -> PaperDecision:
        date = bar.date
        if date not in self._seen_sessions:
            self._seen_sessions.append(date)
            self._seen_sessions.sort()
        self.broker.on_bar(bar)
        self.history.setdefault(bar.symbol, []).append(bar)
        self.last_seen[bar.symbol] = bar.date
        notes: list[str] = []
        signals = dispatched = rejected = 0

        # ۱) اجرایِ سیگنال‌هایِ نشَستِ پیشین (همان لوحِ زمانیِ بک‌تست)
        pend = getattr(self, "_pending", {})
        self._pending = {}
        for eid, draft in pend.items():
            sym = draft.instrument.symbol
            newest = self._latest(sym)
            # سیگنالِ روز T فقط با ردیفی که *تاریخِ تازه‌تر* دارد پر می‌شود.
            # بی‌این شرط، ردیفِ آمدۀ یکِ نمادِ دیگر درِ *همان* روز T باعث
            # می‌شد سفارشِ X رویِ خودِ X@D بسته شود — یعنی نشتِ آینده درِ
            # paper، همان چیزی که بندِ ۶-۲ ممنوعش کرده.
            if newest is None or newest.date <= (draft.price_as_of or ""):
                self._pending[eid] = draft
                continue
            if self.ledger.halted():
                notes.append("halted: %s" % self.ledger.kill_reason())
                rejected += 1
                continue
            if self.fail_closed and self.stale(draft.instrument.symbol, date):
                self.ledger.record(execution_id=eid, kind="risk_reject",
                                   status="stale", symbol=draft.instrument.symbol,
                                   detail="ردیفِ کهنگ یا بی‌ردیف — بی‌اقدام")
                notes.append("stale: %s" % draft.instrument.symbol)
                rejected += 1
                continue
            try:
                prepared = self.service.prepare(draft)
                rec = self.service.execute(prepared)
            except BrokerError as e:
                rejected += 1
                notes.append("broker: %s" % e.code.value)
                continue
            except Exception as e:  # ExecutionError و هر ردِ پیش‌فرود
                rejected += 1
                notes.append("rejected: %s" % str(e)[:90])
                continue
            dispatched += 1
            if rec.status is ExecutionStatus.UNKNOWN_RESULT:
                notes.append("unknown_result → reconcile برایِ %s" % eid)

        # ۲) تصمیمِ همین نشَست رویِ برشِ همین نشَست
        import backtest_engine as BE
        seq = tuple(self.history[bar.symbol])
        i = len(seq) - 1
        view = BE.BarView(symbol=bar.symbol, cursor=seq[i], bars=seq[:i + 1])
        if hasattr(self.strategy, "set_held"):
            self.strategy.set_held(set(self.account.positions))
        sig = self.strategy.on_bar(view)
        if sig is not None and sig.action in (BUY, SELL):
            signals = 1
            eid = order_id(bar.symbol, sig.decided_on or date, sig.action)
            ref = self.broker.resolve_instrument(bar.symbol)
            px = bar.close if bar.close and bar.close > 0 else None
            qty = self._size(sig.action, bar.symbol, px, sig.quantity)
            if px is None or qty <= 0:
                # بی‌قیمت یا بی‌حجم هیچ draftی ساخته نمی‌شود: یکِ سفارشِ بی‌عدد
                # یا رد می‌شود یا از همان جا نمی‌آید — نه صفرِ جعلی.
                self.ledger.record(execution_id=eid, kind="risk_reject",
                                   status="not_sized", symbol=bar.symbol,
                                   detail="قیمت/حجمِ قابلِ سفارش نرسید")
                notes.append("not_sized: %s" % bar.symbol)
                rejected += 1
            else:
                draft = OrderDraft(execution_id=eid, instrument=ref,
                                   side=Side.BUY if sig.action == BUY else Side.SELL,
                                   price=float(px), quantity=float(qty),
                                   mode=OrderMode.SAFE,
                                   price_source="paper:bar.close", price_as_of=date)
                self._pending[eid] = draft

        # ۳) سقفِ ضرر روزانه ⇒ قفلِ خودکار (TRIPPED)
        eq = self.account.equity(self._prices())
        dl = self.limits.max_daily_loss
        if dl is not None and self.account.realized_today <= -abs(dl):
            if self.ledger.kill_state() != TRIPPED:
                self.ledger.set_kill(TRIPPED, "ضررِ روزانه به سقف رسید", actor="risk-engine")
            notes.append("kill switch TRIPPED by risk engine")

        self.persist()
        return PaperDecision(date=date, signals=signals, dispatched=dispatched,
                             rejected=rejected, equity=eq,
                             halt_state=self.ledger.kill_state(), notes=notes)

    def run(self, bars: Sequence[Bar]) -> list[PaperDecision]:
        self._pending = {}
        return [self.on_bar(b) for b in bars]
