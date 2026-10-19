#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""execution_budget.py — «چند سهم می‌توانم بخرم؟» بی‌هیچ حدسی.

چرا لایۀ جدا: اصلاحیهٔ مالک (2026-10-19) می‌گوید حداکثرِ سفارش از *قدرت خرید
واقعی* حساب شود و «هیچ عددی تخمین زده نشود». این دو با هم یک تابعِ خطرناک
می‌سازند: اگر قدرت خرید در دسترس نباشد، ساده‌ترین پیاده‌سازی موجودی را «صفر»
یا «نامحدود» می‌گیرد و کاربر را باِ تعدادِ اشتباه سرِ صف می‌برد. پس این فایل
*هیچ* مقدارِ پیش‌فرضی برایِ پولِ حساب نمی‌سازد؛ بی‌عددِ واقعی، خروجی `UNKNOWN`
است باِ همان دلیلی که ازِ کارگزاری نیامده.

سه قاعده‌ای که نگهبانش است:
  ۱) `buying_power is None` ⇒ `UNKNOWN`، بی‌تعداد. هیچ «تخمینِ سقف» نمی‌شود.
  ۲) کارمزد ازِ خودِ پاسخِ کارگزاری می‌آید؛ عددِ `WIRE_COMMISSION = 0.0012` درِ
     `execution_easytrader.py` عمداً تأییدنشده علامت خورده، پس اگر بیاید فقط باِ
     برچسبِ `assumption` مصرف می‌شود و همان فرض درِ پاسخ می‌نشیند.
  ۳) سرِ سقفِ تعداد، گامِ قیمت و مبنایِ قیمت (saghf/va30) که ازِ کارگزاری نیامده
     نمی‌تواند «رد» یا «قبول» بگیرد؛ نتیجه `LIMITS_UNKNOWN` است، نه `OK`.

هیچ شبکه، هیچ کارگزاری، هیچ سفارش. این ماژول فقط حساب می‌کند.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any, Optional

#: وضعیت‌هایِ روشنِ نتیجه. «نمی‌دانیم» یکِ وضعیت است، نه صفر.
UNKNOWN = "UNKNOWN"                 # قدرت خرید نرسیده ⇒ هیچ تعدادی ساخته نمی‌شود
LIMITS_UNKNOWN = "LIMITS_UNKNOWN"   # پول هست ولی سقف/گامِ مجاز ازِ کارگزاری نیامده
NOT_POSITIVE = "NOT_POSITIVE"       # قیمت یا پولِ نامعتبر ⇒ رد، بی‌محاسبه
OK = "OK"

_PRICE_STEP = Decimal("1")


def _dec(value: Any) -> Optional[Decimal]:
    """تبدیلِ امن به Decimal. هیچ گردکردنی درِ راهِ پول انجام نمی‌شود."""
    if value is None or isinstance(value, bool):
        return None
    try:
        d = Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not d.is_finite():
        return None
    return d


@dataclass(frozen=True)
class BudgetPlan:
    """پیش‌نمایشِ «حداکثرِ قابل‌سفارش». هیچ‌کدام ازِ میدان‌هایش ادعایِ پذیرش نیست."""
    status: str
    quantity: int = 0
    price: Optional[int] = None
    gross_rial: Optional[int] = None
    fee_rial: Optional[int] = None
    total_rial: Optional[int] = None
    remaining_rial: Optional[int] = None
    buying_power_rial: Optional[int] = None
    fee_rate: Optional[float] = None
    lot_size: int = 1
    max_qty: Optional[int] = None
    #: سقفِ تعداد ازِ خودِ کارگزاری رسیده است؟ بی‌آن، تعداد حساب می‌شود ولی
    #: «مجاز بودنش» تأیید نشده است — این را ازِ OKِ بی‌قید جدا نگه می‌داریم.
    caps_verified: bool = False
    assumptions: tuple[str, ...] = ()
    why: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "quantity": self.quantity if self.status == OK else None,
            "price": self.price,
            "gross_rial": self.gross_rial,
            "fee_rial": self.fee_rial,
            "total_rial": self.total_rial,
            "remaining_rial": self.remaining_rial,
            "buying_power_rial": self.buying_power_rial,
            "fee_rate": self.fee_rate,
            "lot_size": self.lot_size,
            "max_qty": self.max_qty,
            "caps_verified": self.caps_verified,
            "assumptions": list(self.assumptions),
            "why": self.why,
            # صریح: این یکِ *پیش‌نمایشِ محلی* است، نه پاسخِ کارگزاری
            "from_broker": False,
            "is_order": False,
        }


def max_affordable(buying_power_rial: Any, price_rial: Any,
                   fee_rate: Any = None, lot_size: Any = None,
                   max_qty: Any = None) -> BudgetPlan:
    """حداکثرِ تعدادِ سهم باِ پولِ *داده‌شده*. بی‌پولِ واقعی ⇒ UNKNOWN.

    `fee_rate` اگر None باشد یعنی کارگزاری هنوز کارمزد را اعلام نکرده است؛ درِ
    آن‌صورت محاسبه بی‌کارمزد انجام می‌شود و همین فرض درِ `assumptions` می‌نشیند —
    هرگز عددی «از پیشِ خود» اضافه نمی‌شود.
    """
    money = _dec(buying_power_rial)
    price = _dec(price_rial)
    assumptions: list[str] = []

    if money is None:
        return BudgetPlan(UNKNOWN, why="قدرت خرید ازِ کارگزاری نرسیده؛ هیچ تعدادی "
                                      "ساخته نمی‌شود (تخمینِ سقف ممنوع)")
    if price is None or price <= 0:
        return BudgetPlan(NOT_POSITIVE, buying_power_rial=int(money),
                          why="قیمتِ سفارش معتبر نیست (تهی یا غیرِ مثبت)")
    if money <= 0:
        return BudgetPlan(NOT_POSITIVE, price=int(price), buying_power_rial=int(money),
                          why="قدرت خرید صفر یا منفی گزارش شده؛ چیزی قابل سفارش نیست")

    fee = _dec(fee_rate)
    if fee is None:
        fee = Decimal("0")
        assumptions.append("کارمزد ازِ کارگزاری نرسیده ⇒ محاسبه بی‌کارمزد؛ "
                           "تعدادِ نهایی ممکن است کمی کمتر باشد")
    elif fee < 0 or fee > Decimal("0.2"):
        return BudgetPlan(NOT_POSITIVE, price=int(price), buying_power_rial=int(money),
                          why="نرخِ کارمزدِ داده‌شده معقول نیست")

    lot = _dec(lot_size)
    lot_i = int(lot) if (lot is not None and lot >= 1) else 1
    if lot is None:
        assumptions.append("سهمیۀ (lot) ازِ کارگزاری نرسیده ⇒ گامِ یک سهم")

    cap = _dec(max_qty)
    cap_i = int(cap) if (cap is not None and cap >= 0) else None
    if cap is None:
        # تعداد ازِ پول قابلِ محاسبه است؛ چیزی که نمی‌دانیم این است که کارگزاری
        # چنین حجمی را در یکِ سفارش می‌پذیرد یا نه. پس OK باِ پرچمِ جدا، نه
        # ردِ کلِ محاسبه و نه ادعایِ مجازبودن.
        assumptions.append("سقفِ تعداد ازِ کارگزاری نرسیده ⇒ مجازبودنِ این حجم تأیید نشده")

    # تعدادِ حداکثر: k * lot * price * (1 + fee) <= money، گرد به پایین
    per_lot = price * (Decimal("1") + fee)
    if per_lot <= 0:
        return BudgetPlan(NOT_POSITIVE, price=int(price), buying_power_rial=int(money),
                          why="مبلغِ هر سهم صفر شد")
    lots = int((money / per_lot) // _PRICE_STEP) if lot_i == 1 else \
        int((money / (per_lot * Decimal(lot_i))).to_integral_value(rounding=ROUND_DOWN))
    qty = lots * lot_i
    if cap_i is not None and cap_i > 0:
        allowed = (cap_i // lot_i) * lot_i
        if qty > allowed:
            qty = allowed
            assumptions.append("سقفِ تعدادِ کارگزاری جایِ قدرت خرید را گرفت")
    if qty <= 0:
        return BudgetPlan(UNKNOWN, price=int(price), buying_power_rial=int(money),
                          fee_rate=float(fee), lot_size=lot_i, max_qty=cap_i,
                          assumptions=tuple(assumptions),
                          why="باِ این قیمت، حتی یکِ سهمی ازِ این پول ساخته نمی‌شود")

    gross = qty * price
    fee_rial = int((gross * fee).to_integral_value(rounding=ROUND_DOWN))
    total = int(gross) + fee_rial
    return BudgetPlan(
        OK, quantity=qty, price=int(price), gross_rial=int(gross), fee_rial=fee_rial,
        total_rial=total, remaining_rial=int(money) - total,
        buying_power_rial=int(money), fee_rate=float(fee), lot_size=lot_i,
        max_qty=cap_i, assumptions=tuple(assumptions), caps_verified=cap_i is not None,
        why="حداکثرِ تعداد ازِ قدرت خریدِ گزارش‌شده؛ تأییدِ کارگزاری نیست")


def plan_from_status(status: Optional[dict[str, Any]], price_rial: Any) -> BudgetPlan:
    """پل بینِ پاسخِ سرویس و محاسبه. هیچ‌جا عددی ازِ خودِ رابط ساخته نمی‌شود:
    اگر `account` درِ پاسخ نباشد، همان UNKNOWN برگردانده می‌شود."""
    acct = (status or {}).get("account") if isinstance(status, dict) else None
    acct = acct if isinstance(acct, dict) else {}
    lim = (status or {}).get("limits") if isinstance(status, dict) else None
    lim = lim if isinstance(lim, dict) else {}
    return max_affordable(acct.get("buying_power_rial"), price_rial,
                          fee_rate=acct.get("fee_rate", lim.get("fee_rate")),
                          lot_size=lim.get("lot_size"), max_qty=lim.get("max_quantity"))
