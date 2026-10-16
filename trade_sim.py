# -*- coding: utf-8 -*-
"""trade_sim.py — تنها مدلِ پرشدن، هزینه و حسابِ شبیه‌سازی‌شده.

چرا این فایل جداست: بک‌تست (`backtest_engine`) و نشستِ کاغذی (`paper_trading`)
هر دو باید «این سفارش در این روز چند خورده می‌شد» را حساب کنند. اگر آن را در
هر دو بنویسیم، دو عدد از دو موتور می‌گیریم — و مقایسۀ «بک‌تست در برابرِ
paper» بی‌محتوا می‌شود. همین شکاف درِ این مخزن سابقه دارد (دو موتورِ چارت، دو
برگردانندۀ برچسب)، پس یک‌جا نوشته می‌شود و هر دو مصرف‌کننده از همان می‌خوانند.

سه حکم:
۱) **محدودیت از داده، نه از عددِ ساختگی.** پرشدن داخلِ [low, high] همان روز
   و تا سقفِ سهمیِ حجمِ *واقعاً معاملات‌شده* آن روز است. دامنۀ مجازِ قیمت فقط
   از خودِ ردیف خوانده می‌شود؛ نبودش یعنی بی‌قید، نه حدس.
۲) **قیمتِ غایب صفر نیست.** اگر قیمتِ بستۀ یکِ موقعیت نرسد، ارزشِ باز `None`
   است و sizing/ریسک با None باید رد شوند، نه اینکه «صفر درگیریم» بخوانند.
۳) **هزینه جزوِ نتیجه است.** کارمزد و لغزش درِ `CostModel` ثبت‌اند و درِ هر
   پرشدن کسر می‌شوند؛ عددِ بی‌هزینه درِ این مخزن «معتبر» گزارش نمی‌شود.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Mapping

# جهت‌ها همان رشته‌هایِ قراردادِ اجرا هستند (execution_contract.Side.value)
BUY, SELL, HOLD = "buy", "sell", "hold"


@dataclass(frozen=True)
class Bar:
    """یکِ روزِ معاملاتیِ یکِ نماد. `None` یعنی آن خانۀ منبع نبوده — نه صفر."""
    symbol: str
    date: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    value: float | None = None
    prev_close: float | None = None
    #: دامنۀ مجازِ *همان* نشست از منبع؛ None یعنی منبع آن را نگفته است.
    allowed_min: float | None = None
    allowed_max: float | None = None
    halted: bool = False
    src: str | None = None

    def tradable(self) -> bool:
        return (not self.halted and self.close is not None
                and self.open is not None and self.open > 0)


@dataclass(frozen=True)
class CostModel:
    """کارمزد و لغزش، هر دو bp. صفر *گزینه* نیست؛ صفر یعنی ادعایِ بی‌هزینه."""
    commission_bps: float = 30.0      # ۰٫۳٪ هر طرف
    slippage_bps: float = 10.0        # ۰٫۱٪ لغزش رویِ قیمتِ اجرا
    #: سقفِ مشارکت در حجمِ روز: خریدِ ۲۰٪ حجمِ یکِ روزِ کم‌حجم واقعیت ندارد.
    max_volume_share: float = 0.02

    def buy_price(self, ref: float) -> float:
        return ref * (1.0 + self.slippage_bps / 10_000.0)

    def sell_price(self, ref: float) -> float:
        return ref * (1.0 - self.slippage_bps / 10_000.0)

    def fee(self, turnover_value: float) -> float:
        return abs(turnover_value) * self.commission_bps / 10_000.0

    def as_dict(self) -> dict:
        return {"commission_bps": self.commission_bps, "slippage_bps": self.slippage_bps,
                "max_volume_share": self.max_volume_share}


@dataclass
class Position:
    symbol: str
    quantity: float = 0.0
    avg_price: float = 0.0
    realized_pnl: float = 0.0

    def market_value(self, price: float | None) -> float | None:
        return None if price is None else self.quantity * float(price)


@dataclass
class SimAccount:
    """نقد + موقعیت‌ها + سود/زیانِ محقق‌شده. همان حساب برایِ بک‌تست و paper."""
    start_cash: float
    cash: float = 0.0
    positions: dict[str, Position] = field(default_factory=dict)
    realized_today: float = 0.0
    realized_total: float = 0.0

    def __post_init__(self) -> None:
        self.cash = float(self.start_cash)

    def position(self, symbol: str) -> Position:
        return self.positions.setdefault(symbol, Position(symbol))

    def held(self, symbol: str) -> float:
        """حجمِ بازِ فعلی، *بی‌ساختنِ* موقعیت.

        چرا لازم است: `position()` موقعیتِ تازه می‌سازد، پس یکِ خواندنِ ساده
        («چقدر در این نماد دارم؟») حساب را با ردیف‌هایِ صفریِ نمادها پر می‌کند و
        بعدًاً equity/exposure همان صفرها را «موقعیتِ باز» می‌بینند.
        """
        p = self.positions.get(symbol)
        return 0.0 if p is None else float(p.quantity)

    def exposure(self, prices: Mapping[str, float | None],
                 symbol: str | None = None) -> float | None:
        """ارزشِ باز. اگر قیمتِ حتی یکِ موقعیت نرسیده باشد `None` — «نمی‌دانم
        چقدر درگیرم» با «هیچ درگیر نیستم» یکی نیست.
        """
        items = [symbol] if symbol is not None else sorted(self.positions)
        total = 0.0
        for s in items:
            p = self.positions.get(s)
            if p is None or p.quantity <= 0:
                continue
            px = prices.get(s)
            if px is None:
                return None
            total += p.quantity * float(px)
        return total

    def equity(self, prices: Mapping[str, float | None]) -> float | None:
        exp = self.exposure(prices)
        return None if exp is None else self.cash + exp

    def snapshot(self) -> dict:
        """وضعیتِ قابلِ ذخیره برایِ بازیابی پسِ restart."""
        return {"start_cash": self.start_cash, "cash": self.cash,
                "realized_today": self.realized_today, "realized_total": self.realized_total,
                "positions": {s: {"quantity": p.quantity, "avg_price": p.avg_price,
                                  "realized_pnl": p.realized_pnl}
                              for s, p in self.positions.items()}}

    @classmethod
    def restore(cls, snap: Mapping) -> "SimAccount":
        acc = cls(start_cash=float(snap.get("start_cash") or 0.0))
        acc.cash = float(snap.get("cash") or 0.0)
        acc.realized_today = float(snap.get("realized_today") or 0.0)
        acc.realized_total = float(snap.get("realized_total") or 0.0)
        for s, p in (snap.get("positions") or {}).items():
            acc.positions[s] = Position(symbol=s, quantity=float(p.get("quantity") or 0.0),
                                        avg_price=float(p.get("avg_price") or 0.0),
                                        realized_pnl=float(p.get("realized_pnl") or 0.0))
        return acc


@dataclass
class Fill:
    """نتیجۀ یکِ پرشدن — یا دلیلِ پرنشدن."""
    ok: bool
    reason: str = ""            # filled | partial | reject code
    detail: str = ""
    symbol: str = ""
    action: str = ""
    date: str = ""
    quantity: float = 0.0
    price: float = 0.0
    gross: float = 0.0
    fee: float = 0.0
    realized: float | None = None
    cost_basis: float | None = None


def plan_quantity(action: str, *, equity: float, price: float, cash: float,
                  held: float, fraction: float, requested: float | None) -> float:
    """حجم: درخواستِ استراتژی مقدم است، وگرنه سهمیِ از حقوق."""
    if action == BUY:
        q = float(requested) if requested else math.floor(equity * float(fraction) / price)
        return max(0.0, min(q, math.floor(cash / price) if price > 0 else 0))
    q = float(requested) if requested else held
    return max(0.0, min(q, held))


def apply_fill(account: SimAccount, *, action: str, symbol: str, bar: Bar,
               costs: CostModel, fraction: float = 0.1,
               requested_qty: float | None = None,
               limit_price: float | None = None,
               max_order_value: float | None = None,
               exposure_by_symbol: Mapping[str, float | None] | None = None,
               max_symbol_exposure: float | None = None,
               max_total_exposure: float | None = None) -> Fill:
    """قیمت ← حجم ← ریسک ← ثبت، در یکِ مسیرِ مشترک.

    ترتیب عمدی است: ریسک *پس از* حجم سنجیده می‌شود، چون ارزشِ سفارش از حجم
    می‌آید و گاردی که رویِ حجمِ حدسی قضاوت کند گارد نیست.
    """
    if action not in (BUY, SELL):
        return Fill(ok=False, reason="bad_action", detail="جهتِ نامعلوم", symbol=symbol,
                    action=action, date=bar.date)
    if bar.halted:
        return Fill(ok=False, reason="halted", detail="توقفِ نماد", symbol=symbol,
                    action=action, date=bar.date)
    ref = bar.open if bar.open and bar.open > 0 else bar.close
    if ref is None or ref <= 0:
        return Fill(ok=False, reason="no_price", detail="ردیفِ اجرا بی‌قیمت است",
                    symbol=symbol, action=action, date=bar.date)
    px = costs.buy_price(float(ref)) if action == BUY else costs.sell_price(float(ref))
    # پرشدن فقط داخلِ همان روزِ معاملاتی ممکن است — و این از داده می‌آید.
    if bar.low is not None and px < bar.low:
        px = float(bar.low)
    if bar.high is not None and px > bar.high:
        px = float(bar.high)
    if bar.allowed_min is not None and px < bar.allowed_min:
        return Fill(ok=False, reason="rejected_price", detail="زیرِ دامنۀ مجازِ نشست",
                    symbol=symbol, action=action, date=bar.date)
    if bar.allowed_max is not None and px > bar.allowed_max:
        return Fill(ok=False, reason="rejected_price", detail="بالایِ دامنۀ مجازِ نشست",
                    symbol=symbol, action=action, date=bar.date)
    if limit_price is not None:
        if action == BUY and px > float(limit_price):
            return Fill(ok=False, reason="rejected_price",
                        detail="قیمتِ اجرا از limit_price بالاتر", symbol=symbol,
                        action=action, date=bar.date)
        if action == SELL and px < float(limit_price):
            return Fill(ok=False, reason="rejected_price",
                        detail="قیمتِ اجرا از limit_price پایین‌تر", symbol=symbol,
                        action=action, date=bar.date)

    prices = dict(exposure_by_symbol or {})
    prices.setdefault(symbol, float(bar.close) if bar.close is not None else None)
    eq = account.equity(prices)
    if eq is None:
        return Fill(ok=False, reason="stale",
                    detail="قیمتِ بستۀ یکِ موقعیت نرسید — ارزشِ باز نامعلوم",
                    symbol=symbol, action=action, date=bar.date)

    qty = plan_quantity(action, equity=eq, price=px, cash=account.cash,
                        held=account.held(symbol), fraction=fraction,
                        requested=requested_qty)
    if qty <= 0:
        return Fill(ok=False, reason="size_zero", detail="حجمِ محاسبه‌شده صفر شد",
                    symbol=symbol, action=action, date=bar.date)

    value = qty * px
    if max_order_value is not None and value > max_order_value:
        return Fill(ok=False, reason="rejected_risk",
                    detail="ارزشِ سفارش (%.0f) از سقفِ تنها (%.0f) بیشتر است" % (value, max_order_value),
                    symbol=symbol, action=action, date=bar.date)
    if action == BUY and (max_symbol_exposure is not None or max_total_exposure is not None):
        cur_sym = (account.position(symbol).market_value(prices.get(symbol)))
        if cur_sym is None:
            return Fill(ok=False, reason="rejected_risk",
                        detail="exposureِ فعلیِ نماد نامعلوم (ردیفِ امروز نرسید)",
                        symbol=symbol, action=action, date=bar.date)
        if max_symbol_exposure is not None and cur_sym + value > max_symbol_exposure:
            return Fill(ok=False, reason="rejected_risk",
                        detail="سقفِ exposureِ نماد", symbol=symbol, action=action, date=bar.date)
        if max_total_exposure is not None:
            tot = account.exposure(prices)
            if tot is None:
                return Fill(ok=False, reason="rejected_risk",
                            detail="exposureِ کل نامعلوم", symbol=symbol,
                            action=action, date=bar.date)
            if tot + value > max_total_exposure:
                return Fill(ok=False, reason="rejected_risk",
                            detail="سقفِ exposureِ کل", symbol=symbol, action=action, date=bar.date)

    reason = "filled"
    if bar.volume:
        cap = float(bar.volume) * float(costs.max_volume_share)
        if cap > 0 and qty > cap:
            qty = math.floor(cap)
            reason = "partial"
            if qty <= 0:
                return Fill(ok=False, reason="partial",
                            detail="سهمِ مجاز از حجمِ روز صفر شد", symbol=symbol,
                            action=action, date=bar.date)

    gross = qty * px
    fee = costs.fee(gross)
    pos = account.position(symbol)
    realized: float | None = None
    basis: float | None = None
    if action == BUY:
        account.cash -= (gross + fee)
        new_q = pos.quantity + qty
        pos.avg_price = ((pos.avg_price * pos.quantity + gross) / new_q) if new_q > 0 else 0.0
        pos.quantity = new_q
    else:
        basis = pos.avg_price * qty
        realized = gross - fee - basis
        pos.realized_pnl += realized
        account.realized_today += realized
        account.realized_total += realized
        pos.quantity -= qty
        account.cash += (gross - fee)
        if pos.quantity <= 0:
            account.positions.pop(symbol, None)
    return Fill(ok=True, reason=reason, symbol=symbol, action=action, date=bar.date,
                quantity=qty, price=px, gross=gross, fee=fee, realized=realized,
                cost_basis=basis)
