# -*- coding: utf-8 -*-
"""backtest_engine.py — بک‌تستِ point-in-time، بی‌نشتِ آینده، با هزینه و ریسک.

مأموریتِ ۱۴۰۵-۰۷-۲۳، بندِ ۶-۲. تا پیشِ این درِ همین مخزن هیچ بک‌تستی نبود
(`grep backtest|strategy_runner|paper_trading` درِ *.py صفر بود) در حالی که
`docs/MASTER-EXECUTION-ROADMAP.md:1251-1296` پانزده قابلیت برایِ ربات وعده داده
بود. این فایل آن وعده را *آزمودنی* می‌کند، نه تبلیغاتی.

مدلِ پرشدن/حساب/هزینه درِ این فایل **نیست** — در `trade_sim.py` است و نشستِ
کاغذی هم همان را می‌خواند؛ دو کپی یعنی دو عدد برایِ یکِ سفارش.

چهار حکمی که کداً بسته شده‌اند، نه با کامنت:

۱) **نشتِ اطلاعات ساختاراً ممکن نیست.** استراتژی فقط `BarView` می‌گیرد و `bars`
   آن پرifixِ *شاملِ روزِ تصمیم* است؛ موتور هر روز برشِ تازه می‌سازد. «قیمتِ
   فردا» درِ آن شیء وجود ندارد که بخواهیم پنهانش کنیم. سیگنالِ روز T درِ روز
   T+1 اجرا می‌شود (`fill at next open`).

۲) **توقف و کهنگی داده مانعِ اقدام است، نه یادداشت.** ردیفِ بی‌معامله/متوقف ⇒
   no fill؛ نمادی که چند نشست پیاپی ردیف ندارد ⇒ کهنگی و رد. هیچ پرشدنی از
   هیچ‌جا ساخته نمی‌شود.

۳) **ریسک پیشِ ثبت، و پسِ نقض خاموش.** سقفِ ارزشِ هر سفارش، exposureِ نماد،
   exposureِ کل و ضرر روزانه همگی *پیشِ* ثبت بررسی می‌شوند؛ نقضِ ضرر روزانه
   قفلِ خودکار می‌زند و از آن به بعد هیچ سفارشِ تازه‌ای ساخته نمی‌شود.

۴) **قابلِ بازتولید.** `manifest` (استراتژی + پارامترها + universe + دورۀ
   زمانی + مدلِ هزینه + نسخۀ موتور) و `digest` (اثرِ انگشتیِ معاملات و منحنیِ
   حقوق) درِ نتیجه می‌نشینند؛ اجرایِ دوباره باید همان digest را بدهد.

این فایل هیچ شبکه‌ای نمی‌زند، هیچ بانکِ عملیاتی را نمی‌نویسد و هیچ سفارشی
ارسال نمی‌کند. داده را مصرف‌کننده می‌دهد: fixture برایِ گارد،
`tools/bot_backtest_run.py` برایِ سنجشِ واقعی.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Mapping, Protocol, Sequence

from trade_sim import (BUY, HOLD, SELL, Bar, CostModel, Fill, SimAccount,
                       apply_fill)

ENGINE_VERSION = "bot-backtest-2"


# ── ۱) داده ─────────────────────────────────────────────────────────────────
def bars_by_symbol(bars: Iterable[Bar]) -> dict[str, tuple[Bar, ...]]:
    """گروه‌بندی و مرتب‌سازیِ زمانی؛ ورودیِ بی‌مرتب هم درست می‌شود."""
    out: dict[str, list[Bar]] = {}
    for b in bars:
        out.setdefault(b.symbol, []).append(b)
    return {s: tuple(sorted(v, key=lambda x: x.date)) for s, v in out.items()}


def session_dates(by_symbol: Mapping[str, Sequence[Bar]]) -> tuple[str, ...]:
    days: set[str] = set()
    for v in by_symbol.values():
        days.update(b.date for b in v)
    return tuple(sorted(days))


# ── ۲) چیزی که استراتژی می‌بیند ─────────────────────────────────────────────
@dataclass(frozen=True)
class BarView:
    """پرifixِ داده تا روزِ تصمیم — تنها مجوزِ دیدِ استراتژی.

    هیچ فیلدی به نامِ `future` یا `next_bar` اینجا نیست؛ پس «بدونِ look-ahead»
    یک قولِ رفتاری نیست، یکِ واقعیتِ ساختاری است.
    """
    symbol: str
    cursor: Bar
    bars: tuple[Bar, ...]

    def closes(self) -> tuple[float, ...]:
        return tuple(float(b.close) for b in self.bars if b.close is not None)

    def last(self, n: int) -> tuple[Bar, ...]:
        return self.bars[-n:] if n > 0 else ()


class Strategy(Protocol):
    id: str
    params: Mapping[str, Any]

    def on_bar(self, view: BarView) -> "Signal | None": ...


@dataclass(frozen=True)
class Signal:
    symbol: str
    action: str
    reason: str = ""
    #: فقط برایِ ردِّپا: سیگنال رویِ کدامِ روز نشسته است.
    decided_on: str = ""
    #: حجمِ خواسته‌شده؛ None ⇒ موتور با sizing خودش تعیین می‌کند.
    quantity: float | None = None
    limit_price: float | None = None


# ── ۳) ریسک ─────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class RiskLimits:
    """کنترل‌های بندِ ۶-۴. `None` یعنی سقف تعریف نشده؛ عدد یعنی نگهبان."""
    max_order_value: float | None = None
    max_symbol_exposure: float | None = None
    max_total_exposure: float | None = None
    max_daily_loss: float | None = None
    #: حداکثر چند سفارش در یکِ روز (جلوگیری از حلقۀ ارسال)
    max_orders_per_day: int | None = None
    #: نمادی که `max_missing_sessions` روز پیاپی ردیف ندارد، کهنگی است.
    max_missing_sessions: int | None = None
    #: سهمِ هر موقعیت از حقوق (اگر استراتژی حجم نداده باشد)
    position_size_fraction: float = 0.1


# ── ۴) نتیجه ────────────────────────────────────────────────────────────────
@dataclass
class Trade:
    symbol: str
    signal_date: str
    fill_date: str
    action: str
    quantity: float
    price: float
    gross: float
    fee: float
    reason: str
    #: برایِ فروش: سود/زیانِ محقق‌شدۀ همین سفارش (پس از کارمزد). خرید ⇒ None.
    realized: float | None = None
    cost_basis: float | None = None


@dataclass
class Rejection:
    signal_date: str
    symbol: str
    action: str
    reason: str
    detail: str = ""


@dataclass
class BacktestResult:
    manifest: dict
    equity_dates: list[str]
    equity: list[float | None]
    trades: list[Trade]
    rejections: list[Rejection]
    metrics: dict
    daily_pnl: list[tuple[str, float | None]]

    def digest(self) -> str:
        """اثرِ انگشتیِ نتیجه — همان چیزی که «قابلِ بازتولید» را سنجیدنی می‌کند."""
        payload = {
            "manifest": self.manifest,
            "trades": [[t.symbol, t.signal_date, t.fill_date, t.action, round(t.quantity, 4),
                        round(t.price, 4), round(t.fee, 4), t.reason] for t in self.trades],
            "equity": [None if v is None else round(v, 2) for v in self.equity],
            "rejections": [[r.signal_date, r.symbol, r.action, r.reason] for r in self.rejections],
        }
        blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


# ── ۵) استراتژی‌های آماده ───────────────────────────────────────────────────
class BuyAndHold:
    """سنجشِ سلامتِ خودِ موتور: اگر «همه را بخر و نگه‌دار» هم عددِ منطقی ندهد،
    موتور غلط است — نه بازار.
    """
    id = "buy_and_hold"
    params: Mapping[str, Any] = {}

    def __init__(self) -> None:
        self._held: set[str] = set()

    def set_held(self, held: set[str]) -> None:
        """تنها حالتِ جانبیِ مجاز: آنچه *تا پیشِ امروز* باز بوده است."""
        self._held = set(held)

    def on_bar(self, view: BarView) -> Signal | None:
        if not view.cursor.tradable() or view.symbol in self._held:
            return None
        return Signal(symbol=view.symbol, action=BUY, reason="تخصیصِ اولیه",
                      decided_on=view.cursor.date)


class MaCross:
    """تقاطعِ دو میانگینِ متحرک — *راهبدِ آزمون* است، نه پیشنهادِ معاملاتی.

    پارامترها درِ manifest ثبت می‌شوند و هیچ ادعایِ روش‌شناختی ندارند؛ جزوۀ
    FTS این اعداد را تعریف نکرده است.
    """
    id = "ma_cross"

    def __init__(self, fast: int = 20, slow: int = 60) -> None:
        if fast >= slow:
            raise ValueError("fast باید کوچک‌تر از slow باشد")
        self.fast, self.slow = int(fast), int(slow)
        self.params = {"fast": self.fast, "slow": self.slow}

    @staticmethod
    def _ma(vals: Sequence[float], n: int) -> float | None:
        if len(vals) < n:
            return None
        return sum(vals[-n:]) / float(n)

    def on_bar(self, view: BarView) -> Signal | None:
        closes = view.closes()
        if len(closes) < self.slow + 1 or not view.cursor.tradable():
            return None
        f_now, s_now = self._ma(closes, self.fast), self._ma(closes, self.slow)
        f_prev, s_prev = self._ma(closes[:-1], self.fast), self._ma(closes[:-1], self.slow)
        if None in (f_now, s_now, f_prev, s_prev):
            return None
        decided = view.cursor.date
        if f_prev <= s_prev and f_now > s_now:
            return Signal(symbol=view.symbol, action=BUY,
                          reason="fastMA عبورِ رو به بالا از slowMA", decided_on=decided)
        if f_prev >= s_prev and f_now < s_now:
            return Signal(symbol=view.symbol, action=SELL,
                          reason="fastMA عبورِ رو به پایین از slowMA", decided_on=decided)
        return None


# ── ۶) موتور ────────────────────────────────────────────────────────────────
class BacktestEngine:
    def __init__(self, *, by_symbol: Mapping[str, Sequence[Bar]], strategy,
                 costs: CostModel | None = None, limits: RiskLimits | None = None,
                 start_cash: float = 100_000_000.0, universe: Sequence[str] | None = None,
                 dates: Sequence[str] | None = None) -> None:
        self.by_symbol = {k: tuple(v) for k, v in by_symbol.items()}
        if universe is not None:
            keep = set(universe)
            self.by_symbol = {k: v for k, v in self.by_symbol.items() if k in keep}
        self.strategy = strategy
        self.costs = costs or CostModel()
        self.limits = limits or RiskLimits()
        self.start_cash = float(start_cash)
        self.dates = tuple(dates) if dates is not None else session_dates(self.by_symbol)
        #: indexِ سریع: نماد → date → جایِ ردیف
        self._pos = {s: {b.date: i for i, b in enumerate(v)} for s, v in self.by_symbol.items()}
        self._reset()

    def _reset(self) -> None:
        """`run()` باید بی‌خطر دوباره صدا زده شود.

        بی‌این، اجرایِ دوم رویِ همان engine ردیف‌ها را *جمع* می‌کرد (دو برابرِ
        معامله، منحنیِ حقوقِ اشتباه، digest عوض) — و همان digest باید ثابت بماند.
        """
        self.account = SimAccount(start_cash=self.start_cash)
        self.trades: list[Trade] = []
        self.rejections: list[Rejection] = []
        self.equity_dates: list[str] = []
        self.equity: list[float | None] = []
        self.daily_pnl: list[tuple[str, float | None]] = []
        self.killed = False
        self.kill_reason = ""
        self.missing: dict[str, int] = {}
        self.last_equity: float = self.start_cash
        self._orders_today = 0
        self._peak_equity = self.start_cash

    # ---- کمکي ────────────────────────────────────────────────────────────
    def _bar(self, symbol: str, date: str) -> Bar | None:
        i = self._pos.get(symbol, {}).get(date)
        return None if i is None else self.by_symbol[symbol][i]

    @staticmethod
    def _view(seq: Sequence[Bar], i: int) -> BarView:
        return BarView(symbol=seq[i].symbol, cursor=seq[i], bars=tuple(seq[:i + 1]))

    def _prices_mark(self, date: str) -> dict[str, float | None]:
        """قیمتِ امروز برایِ هر موقعیتِ باز؛ نبودِ ردیف ⇒ None (کهنگی)."""
        out: dict[str, float | None] = {}
        for s in self.account.positions:
            b = self._bar(s, date)
            out[s] = None if b is None or b.close is None else float(b.close)
        return out

    def _trip(self, why: str) -> None:
        self.killed, self.kill_reason = True, why

    # ---- حلقهٔ اصلی ──────────────────────────────────────────────────────
    def run(self) -> BacktestResult:
        self._reset()
        pending: list[Signal] = []
        for date in self.dates:
            self._orders_today = 0
            self.account.realized_today = 0.0

            # ۱) اجرای سیگنال‌های دیروز (سیگنالِ امروز هرگز امروز پر نمی‌شود)
            for sig in pending:
                if self.killed:
                    self.rejections.append(Rejection(sig.decided_on, sig.symbol, sig.action,
                                                     "kill_switch", self.kill_reason))
                    continue
                fb = self._bar(sig.symbol, date)
                if fb is None:
                    self.missing[sig.symbol] = self.missing.get(sig.symbol, 0) + 1
                    self.rejections.append(Rejection(sig.decided_on, sig.symbol, sig.action,
                                                     "no_bar", "ردیفی برایِ این روز نیست"))
                    lim = self.limits.max_missing_sessions
                    if lim is not None and self.missing[sig.symbol] > lim:
                        self.rejections.append(Rejection(sig.decided_on, sig.symbol, sig.action,
                                                         "stale", "چند روز پیاپی بی‌ردیف"))
                    continue
                self.missing[sig.symbol] = 0
                if not fb.tradable():
                    self.rejections.append(Rejection(sig.decided_on, sig.symbol, sig.action,
                                                     "halted", "توقفِ نماد یا بی‌معامله"))
                    continue
                if (self.limits.max_orders_per_day is not None
                        and self._orders_today >= self.limits.max_orders_per_day):
                    self.rejections.append(Rejection(sig.decided_on, sig.symbol, sig.action,
                                                     "rejected_risk", "سقفِ تعدادِ سفارشِ روز"))
                    continue
                fill: Fill = apply_fill(
                    self.account, action=sig.action, symbol=sig.symbol, bar=fb,
                    costs=self.costs, fraction=self.limits.position_size_fraction,
                    requested_qty=sig.quantity, limit_price=sig.limit_price,
                    max_order_value=self.limits.max_order_value,
                    exposure_by_symbol=self._prices_mark(fb.date),
                    max_symbol_exposure=self.limits.max_symbol_exposure,
                    max_total_exposure=self.limits.max_total_exposure)
                if not fill.ok:
                    self.rejections.append(Rejection(sig.decided_on, sig.symbol, sig.action,
                                                     fill.reason, fill.detail))
                    continue
                self._orders_today += 1
                self.trades.append(Trade(symbol=fill.symbol, signal_date=sig.decided_on,
                                         fill_date=fill.date, action=fill.action,
                                         quantity=fill.quantity, price=fill.price,
                                         gross=fill.gross, fee=fill.fee, reason=fill.reason,
                                         realized=fill.realized, cost_basis=fill.cost_basis))
            pending = []

            # ۲) تصمیمِ امروز رویِ برشِ امروز
            for symbol, seq in self.by_symbol.items():
                i = self._pos[symbol].get(date)
                if i is None:
                    continue
                if hasattr(self.strategy, "set_held"):
                    self.strategy.set_held(set(self.account.positions))
                try:
                    sig = self.strategy.on_bar(self._view(seq, i))
                except Exception as e:  # استراتژیِ خراب نباید موتور را بکشد
                    self.rejections.append(Rejection(date, symbol, "-", "strategy_error",
                                                     str(e)[:90]))
                    continue
                if sig is not None and sig.action in (BUY, SELL):
                    pending.append(replace(sig, decided_on=sig.decided_on or date))

            # ۳) بستۀ روز و سقفِ ضرر
            eq = self.account.equity(self._prices_mark(date))
            self.equity_dates.append(date)
            self.equity.append(eq)
            prev = None
            for back in reversed(self.equity[:-1]):
                if back is not None:
                    prev = back
                    break
            if eq is not None:
                self.last_equity = eq
                self._peak_equity = max(self._peak_equity, eq)
                lim = self.limits.max_daily_loss
                if lim is not None and self.account.realized_today <= -abs(lim):
                    self._trip("ضررِ محقق‌شدۀ روز به سقف رسید: %.0f" % self.account.realized_today)
            # بی‌prev یعنی تا اینجا بستۀ معتبری نبوده — صفر ساختنش خطاست.
            self.daily_pnl.append((date, None if (eq is None or prev is None) else eq - prev))

        return BacktestResult(manifest=self._manifest(), equity_dates=self.equity_dates,
                              equity=self.equity, trades=self.trades,
                              rejections=self.rejections, metrics=self._metrics(),
                              daily_pnl=self.daily_pnl)

    # ---- متدیک و manifest ────────────────────────────────────────────────
    def _metrics(self) -> dict:
        eq = [v for v in self.equity if v is not None]
        if not eq:
            return {"status": "no_equity", "kill_switch": {"killed": self.killed,
                                                           "reason": self.kill_reason}}
        rets = [(eq[i] / eq[i - 1] - 1.0) for i in range(1, len(eq)) if eq[i - 1] > 0]
        peak, mdd = -math.inf, 0.0
        for v in eq:
            peak = max(peak, v)
            if peak > 0:
                mdd = min(mdd, v / peak - 1.0)
        sells = [t for t in self.trades if t.action == SELL]
        # نرخِ برد فقط از *سودِ محقق‌شدۀ خودِ همان سفارش* خوانده می‌شود. سنجش با
        # میانگینِ خریدِ موقعیتِ زنده دو اشتباه دارد: موقعیتِ بسته‌شده دیگر درِ
        # حساب نیست و «سودِ این فروش» به میانگینِ *بعدیِ* آن نماد وابسته می‌شود.
        closed = [t for t in sells if t.realized is not None]
        wins = sum(1 for t in closed if t.realized > 0)
        fees = sum(t.fee for t in self.trades)
        reasons: dict[str, int] = {}
        for r in self.rejections:
            reasons[r.reason] = reasons.get(r.reason, 0) + 1
        daily_mean = sum(rets) / len(rets) if rets else 0.0
        daily_var = sum((r - daily_mean) ** 2 for r in rets) / len(rets) if rets else 0.0
        sharpe = (daily_mean / math.sqrt(daily_var) * math.sqrt(250.0)) if daily_var > 0 else None
        return {
            "sessions": len(self.equity),
            "sessions_marked": len(eq),
            "end_equity": float(eq[-1]),
            "total_return": float(eq[-1] / self.start_cash - 1.0),
            "max_drawdown": float(mdd),
            "annualised_volatility": (math.sqrt(daily_var) * math.sqrt(250.0)) if rets else None,
            "sharpe_like": sharpe,
            "trades": len(self.trades),
            "buys": sum(1 for t in self.trades if t.action == BUY),
            "sells": len(sells),
            "closed_sells": len(closed),
            "win_count": wins,
            "win_rate": (wins / len(closed)) if closed else None,
            "best_trade": max((t.realized for t in closed), default=None),
            "worst_trade": min((t.realized for t in closed), default=None),
            "fees_total": float(fees),
            "turnover": float(sum(abs(t.gross) for t in self.trades)),
            "cost_drag_of_start": float(fees / self.start_cash),
            "realized_pnl_total": float(self.account.realized_total),
            "rejections": reasons,
            "rejected_total": len(self.rejections),
            "kill_switch": {"killed": self.killed, "reason": self.kill_reason},
            "final_positions": {s: {"qty": p.quantity, "avg": p.avg_price}
                                for s, p in self.account.positions.items()},
        }

    def _manifest(self) -> dict:
        params = getattr(self.strategy, "params", {}) or {}
        universe_hash = hashlib.sha256(
            "|".join(sorted(self.by_symbol)).encode("utf-8")).hexdigest()[:12]
        span = [self.dates[0], self.dates[-1]] if self.dates else [None, None]
        src_mix: dict[str, int] = {}
        halted_rows = 0
        for v in self.by_symbol.values():
            for b in v:
                src_mix[b.src or "null"] = src_mix.get(b.src or "null", 0) + 1
                if b.halted:
                    halted_rows += 1
        return {
            "engine_version": ENGINE_VERSION,
            "strategy": getattr(self.strategy, "id", type(self.strategy).__name__),
            "strategy_params": dict(params),
            "cost_model": self.costs.as_dict(),
            "risk_limits": dict(self.limits.__dict__),
            "start_cash": self.start_cash,
            "fill_rule": "signal on day T, fill at open of T+1, bounded by T+1 low/high and by max_volume_share",
            "lookahead_guard": "strategy receives BarView(bars = seq[:i+1]) only",
            "universe_size": len(self.by_symbol),
            "universe_hash": universe_hash,
            "sessions": len(self.dates),
            "date_span": span,
            "bar_rows": sum(len(v) for v in self.by_symbol.values()),
            "bar_src_mix": src_mix,
            "halted_rows": halted_rows,
        }


# ── ۷) تقسیمِ زمانی (بندِ ۶-۲: split زمانی، walk-forward) ──────────────────
def split_chronic(dates: Sequence[str], *, train: float = 0.6,
                  valid: float = 0.2) -> dict[str, tuple[str, ...]]:
    """برشِ *زمانی* — نه تصادفی. انتخابِ تصادفی یعنی نشتِ آینده درِ آموزش."""
    d = list(dates)
    n = len(d)
    i_tr = int(n * train)
    i_va = int(n * (train + valid))
    return {"train": tuple(d[:i_tr]), "validation": tuple(d[i_tr:i_va]),
            "test": tuple(d[i_va:])}


def walk_forward(dates: Sequence[str], *, folds: int = 3,
                 train_fraction: float = 0.5) -> list[dict[str, tuple[str, ...]]]:
    """هر fold یکِ پنجرۀ آزمایشِ جدا و *پس از* آموزش؛ بی‌همپوشانیِ رو به عقب."""
    d = list(dates)
    n = len(d)
    if folds < 1 or n < folds + 1:
        return []
    step = max(1, (n - int(n * train_fraction)) // folds)
    out: list[dict[str, tuple[str, ...]]] = []
    for k in range(folds):
        end_test = min(n, int(n * train_fraction) + step * (k + 1))
        start_test = end_test - step
        if start_test <= 0:
            break
        out.append({"train": tuple(d[:start_test]), "test": tuple(d[start_test:end_test])})
    return out
