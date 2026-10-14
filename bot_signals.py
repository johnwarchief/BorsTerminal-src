# -*- coding: utf-8 -*-
"""bot_signals.py — ربات رأیِ تازه نمی‌سازد؛ رأیِ داوریِ موجود را *مصرف* می‌کند.

چرا این فایل هست: `docs/MASTER-EXECUTION-ROADMAP.md` (بستۀ تصویب‌شدۀ مالک،
کامیت `cbd9035`) صریح می‌گوید «ربات باید تصمیمِ canonical FTS/market را مصرف
کند، نه آنکه داورِ دومِ متناقض بسازد». استراتژی‌های `backtest_engine`
(`MaCross`، `BuyAndHold`) راهبدِ آزمون‌اند — همان‌طور که درِ سرآمدشان نوشته
شده، هیچ ادعایِ روش‌شناختی ندارند. این فایل تنها مسیری است که برایِ «تصمیم»
درِ رباتِ واقعی مجاز است: عضویتِ نماد در *خروجیِ خودِ داور*.

یکアダپتر، سه قاعده:
۱) هیچ آستانه، هیچ وزن، هیچ «امتیاز» درِ این فایل تعریف نمی‌شود. تنها ورودی،
   تابعِ `judge(session) → {symbol: "in"|"out"}` است که از داورِ canonical
   (قیف/FTS با `as_of`) می‌آید. اگر داور چیزی نگوید، اینجا هم چیزی نیست.
۲) تصمیم رویِ نشستِ *بسته‌شدۀ* داور گرفته می‌شود و اجرا روزِ بعد — همان لوحِ
   زمانیِ `backtest_engine`؛ ورودیِ judge برایِ روز T هر داده‌ای پس از T
   نمی‌تواند داشته باشد (این مسئولیتِ خودِ داور است و درِ
   `dev/test_fts_asof_cutoff.py` قفل شده).
۳) تغییرِ عضویت تنها محرکِ سفارش است: «تازه وارد شد» ⇒ خرید، «تازه خارج شد»
   ⇒ فروشِ موقعیتِ باز. بی‌تغییری ⇒ هیچ. بی‌موقعیت ⇒ هیچ فروشی.
"""
from __future__ import annotations

from typing import Callable, Mapping, Sequence

from backtest_engine import BarView, Signal
from trade_sim import BUY, SELL

#: نوعِ داوری که بیرون تزریق می‌شود: نشست → نماد → عضو/خروج
Judge = Callable[[str], Mapping[str, str]]


class FunnelMembership:
    """سیگنال از *عضویتِ* قیف — بی‌آستانهٔ دوم.

    `judge` را مصرف‌کننده می‌دهد: درِ تولید همان `funnel_engine`/`api/funnel`
    با `as_of` است (تصمیمِ canonical با نسخۀ ruleset)، و درِ آزمون یکِ تابعِ
    قطعی. خودِ این کلاس هیچ عددِ بازار را نمی‌بیند و هیچ قاعده‌ای نمی‌شمارد؛
    تنها «دیروز در بود / امروز نیست» را مقایسه می‌کند.
    """

    id = "funnel_membership"

    def __init__(self, judge: Judge) -> None:
        if not callable(judge):
            raise TypeError("judge باید فراخوانِ session → {symbol: in|out} باشد")
        self.judge = judge
        self.params = {"judge": getattr(judge, "__name__", type(judge).__name__)}
        self._cur_session: str | None = None
        self._cur_map: dict[str, str] = {}
        self._prev_session: str | None = None
        self._prev: dict[str, str] = {}
        self._held: set[str] = set()

    def set_held(self, held: set[str]) -> None:
        """موقعیت‌هایِ بازِ حساب — برایِ آنکه «فروشِ بی‌موقعیت» ساخته نشود."""
        self._held = set(held)

    def _membership(self, session: str) -> dict[str, str]:
        got = self.judge(session) or {}
        if not isinstance(got, Mapping):
            raise TypeError("judge باید نگاشتِ symbol→in/out برگرداند")
        out: dict[str, str] = {}
        for sym, state in got.items():
            s = str(state or "").strip().lower()
            # «نیست» با «نمی‌دانیم» یکی نیست: هر مقدارِ دیگری بی‌اقدام است،
            # نه «خارج‌شدن» — و بی‌دلیل فروشی نمی‌سازد.
            out[str(sym)] = s if s in ("in", "out") else "unknown"
        return out

    def on_bar(self, view: BarView) -> Signal | None:
        session = view.cursor.date
        if not view.cursor.tradable():
            return None
        # نگاشتِ همین نشست یک‌بار ساخته می‌شود و نشستِ پیشین «دیروز» می‌ماند؛
        # بی‌این، هر نمادِ دیگری درِ همان روز داور را دوباره صدا می‌زد.
        if session != self._cur_session:
            self._prev_session, self._prev = self._cur_session, self._cur_map
            self._cur_session = session
            self._cur_map = self._membership(session)
        symbol = view.symbol
        now = self._cur_map.get(symbol, "unknown")
        was = self._prev.get(symbol, "unknown") if self._prev_session else "unknown"
        if now == "in" and was != "in" and symbol not in self._held:
            return Signal(symbol=symbol, action=BUY, reason="ورودِ تازه به خروجیِ داور",
                          decided_on=session)
        if now == "out" and was == "in" and symbol in self._held:
            return Signal(symbol=symbol, action=SELL, reason="خروجِ تازه از خروجیِ داور",
                          decided_on=session)
        return None


def verdicts_to_membership(survivor_symbols: Sequence[str], all_symbols: Sequence[str]) -> dict[str, str]:
    """کمکیِ بی‌منطق: خروجیِ قیف (`survivors`) را به نگاشتِ in/out تبدیل می‌کند.

    تنها چیزی که اینجا انجام می‌شود «عضو هست یا نه» است — هیچ فیلترِ دومی
    اعمال نمی‌شود، پس اگر روزی قیف تغییر کند، ربات هم همان را می‌بیند.
    """
    keep = {str(s) for s in survivor_symbols}
    return {str(s): ("in" if str(s) in keep else "out") for s in all_symbols}
