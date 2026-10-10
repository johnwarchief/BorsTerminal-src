# -*- coding: utf-8 -*-
"""market_universe — طبقه‌بندیِ وضعیتِ معاملاتیِ هر نماد برایِ غربالگریِ زنده.

هدفِ این ماژول: فهرستِ فرصت‌هایِ زنده به نمادهایِ **واقعاً در حالِ معامله**
اولویت بگیرد، بدونِ آنکه دامنهٔ غربالگریِ FTS کوچک شود. یک نمادِ واجدِ شرایط
که درِ یکِ لحظه معامله‌ای ندارد از غربالگریِ FTS حذف نمی‌شود؛ فقط وضعیتش
برایِ اولویت‌بندیِ نمایش ثبت می‌شود.

تفکیکِ کلیدی (نه حدس):
  • «معاملۀِ انجام‌شده» = افزایشِ شمارندهٔ تجمعیِ نشست (z_tot_tran یا q_tot_cap)
    بینِ دو snapshot، همراه با revision/زمانِ تازه — نه تغییرِ قیمت.
  • «مظنه/دفترِ سفارش» = تغییرِ buy_q*/sell_q*/buy_q1_px/sell_q1_px/p_last
    بدونِ افزایشِ شمارندهٔ معامله.
  • تغییرِ قیمتِ تنها، هرگز دلیلِ انجامِ معامله حساب نمی‌شود.

وضعیت‌ها (از حقایِ کوچک‌تر به بزرگ‌ترِ اولویتِ نمایش):
  TRADING_ACTIVE / QUOTE_ACTIVE_NO_TRADE / NO_RECENT_TRADE /
  SUSPENDED / STALE_DATA / MARKET_CLOSED / UNKNOWN

آستانه‌ها قابل‌تنظیم‌اند (trade_window_s / stale_window_s) و ثابتِ یک‌ثانیه‌ای
نیستند؛ باید از cadence واقعیِ feed اندازه‌گیری شوند.
"""
from __future__ import annotations

import time
from typing import Any, Iterable, Optional

# وضعیت‌ها
TRADING_ACTIVE = "TRADING_ACTIVE"
QUOTE_ACTIVE_NO_TRADE = "QUOTE_ACTIVE_NO_TRADE"
NO_RECENT_TRADE = "NO_RECENT_TRADE"
SUSPENDED = "SUSPENDED"
STALE_DATA = "STALE_DATA"
MARKET_CLOSED = "MARKET_CLOSED"
UNKNOWN = "UNKNOWN"

# اولویتِ نمایشِ زنده (کمتر = بالاتر). نمادهایِ واجدِ شرایطِ کم‌فعال پایین‌تر
# می‌آیند ولی حذف نمی‌شوند.
PRIORITY = {TRADING_ACTIVE: 0, QUOTE_ACTIVE_NO_TRADE: 1, NO_RECENT_TRADE: 2,
            UNKNOWN: 3, STALE_DATA: 4, SUSPENDED: 5, MARKET_CLOSED: 6}

# کدهایِ c_etaval که درِ TSETMC «مجاز به معامله» را نشان می‌دهند. این نگاشت باید
# رویِ دادهٔ واقعیِ نشست راستی‌آزمایی شود؛ تا آن زمان، «توقف» فقط با شاهدِ صریح
# (stop_state/عنوانِ غیرمجاز) اعلام می‌شود، نه با نبودِ داده.
_ETAVAUL_FORBIDDEN_MARKERS = ("توقف", "ممنوع", "بسته", "غيرمجاز", "غیرمجاز", "ندارد")

# آستانه‌هایِ پیش‌فرض — قابل‌تنظیم؛ درِ production از cadence واقعی feed تنظیم
# می‌شوند (بندِ ۳ مأموریت: آستانۀ ثابتِ دلخواه نساز).
DEFAULT_TRADE_WINDOW_S = 120.0   # «معاملۀِ اخیر» تا این اندازه از آخرین افزایشِ شمارنده
DEFAULT_STALE_WINDOW_S = 180.0   # feed کهنه اگر fetched_at قدیمی‌تر از این باشد


def _f(v: Any) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.0
    return x if x == x else 0.0   # NaN → 0


def _trade_counter(row: dict) -> float:
    """شمارندهٔ تجمعیِ معامله: ترجیحاً تعدادِ معاملات (z_tot_tran)، وگرنه حجم."""
    z = _f(row.get("z_tot_tran"))
    return z if z > 0 else _f(row.get("q_tot_cap"))


def _book_sig(row: dict) -> tuple:
    """امضایِ دفترِ سفارش/مظنه — مستقل از شمارندهٔ معامله.

    از ستون‌هایِ واقعیِ تابلو می‌خوانَد (نه buy_q_vol که درِ projectionِ تابلو
    نیست): حجمِ صفِ خرید/فروشِ حقیقی و حجمِ صفِ اول.
    """
    return (round(_f(row.get("p_last")), 4),
            round(_f(row.get("buy_q1_vol")), 2), round(_f(row.get("buy_q1_cnt")), 2),
            round(_f(row.get("buy_i_vol")), 2), round(_f(row.get("sell_i_vol")), 2))


def _is_suspended(row: dict) -> bool:
    st = str(row.get("stop_state") or "")
    code = str(row.get("st_code") or row.get("c_etaval") or "")
    if any(m in st for m in _ETAVAUL_FORBIDDEN_MARKERS):
        return True
    # c_etavalِ صریحِ غیرمجاز (اگر منبع کدِ متن/حرف داد). نبودِ کد ⇒ توقف نیست.
    if code and any(m in code for m in _ETAVAUL_FORBIDDEN_MARKERS):
        return True
    return False


def _feed_age_s(row: dict, now_wall: float) -> Optional[float]:
    fa = row.get("fetched_at") or row.get("feed_ts")
    try:
        fa = float(fa)
    except (TypeError, ValueError):
        return None
    return now_wall - fa


def classify_trading_status(cur: dict, prev: Optional[dict], *,
                            market_open: bool, now_wall: Optional[float] = None,
                            trade_window_s: float = DEFAULT_TRADE_WINDOW_S,
                            stale_window_s: float = DEFAULT_STALE_WINDOW_S) -> dict:
    """وضعیتِ یکِ نماد را از مشاهدۀِ فعلی + قبلی می‌سنجد. تابعِ خالصِ قابل‌تست."""
    now_wall = now_wall if now_wall is not None else time.time()
    ev: dict[str, Any] = {"market_open": market_open}

    if not market_open:
        return {"status": MARKET_CLOSED, "reason": "market-closed", "evidence": ev}

    if not cur:
        return {"status": UNKNOWN, "reason": "no-row", "evidence": ev}

    if _is_suspended(cur):
        return {"status": SUSPENDED, "reason": "suspended-by-source",
                "evidence": {**ev, "stop_state": cur.get("stop_state"), "st_code": cur.get("st_code")}}

    age = _feed_age_s(cur, now_wall)
    ev["feed_age_s"] = None if age is None else round(age, 1)
    if age is not None and age > stale_window_s:
        return {"status": STALE_DATA, "reason": "feed-too-old", "evidence": ev}

    cur_tr = _trade_counter(cur)
    prev_tr = _trade_counter(prev) if prev else None
    ev["z_tot_tran"] = cur_tr
    book_now = _book_sig(cur)
    book_prev = _book_sig(prev) if prev else None

    # افزایشِ شمارندهٔ تجمعی ⇒ معاملۀِ انجام‌شده (نه تغییرِ قیمت).
    trade_executed = prev_tr is not None and cur_tr > prev_tr
    quote_changed = book_prev is not None and book_now != book_prev
    ev["trade_executed"] = bool(trade_executed)
    ev["quote_changed"] = bool(quote_changed)

    if trade_executed:
        return {"status": TRADING_ACTIVE, "reason": "trade-counter-increased",
                "evidence": {**ev, "delta_trades": round(cur_tr - (prev_tr or 0), 2)}}

    # معامله‌ای در این دور نیست؛ آیا درِ پنجرۀِ «اخیر» معامله داشتیم؟
    last_trade_age = _last_trade_age_s(cur, prev, now_wall)
    ev["last_trade_age_s"] = last_trade_age
    if quote_changed:
        return {"status": QUOTE_ACTIVE_NO_TRADE, "reason": "book-changed-no-trade", "evidence": ev}
    if last_trade_age is not None and last_trade_age <= trade_window_s:
        return {"status": TRADING_ACTIVE, "reason": "recent-trade-within-window", "evidence": ev}
    # نه معاملۀِ جدید، نه تغییرِ دفتر در این دور. «is_live» سیگنالِ زنده‌بودنِ
    # خودِ تابلو است (نه حدسِ ما): false ⇒ واجدِ شرایط ولی خاملِ این نشست؛
    # true ⇒ زنده ولی بی‌تغییری که از دورِ پیش قابلِ اندازه‌گیری نبوده؛
    # نبودِ هر دو + نبودِ baseline ⇒ واقعاً UNKNOWN.
    live = cur.get("is_live")
    ev["is_live"] = live
    if live is False:
        return {"status": NO_RECENT_TRADE, "reason": "board-not-live", "evidence": ev}
    if live is True:
        return {"status": NO_RECENT_TRADE, "reason": "live-no-measurable-change", "evidence": ev}
    if age is None and prev_tr is None:
        return {"status": UNKNOWN, "reason": "no-baseline", "evidence": ev}
    return {"status": NO_RECENT_TRADE, "reason": "eligible-no-trade-in-window", "evidence": ev}


def _last_trade_age_s(cur: dict, prev: Optional[dict], now_wall: float) -> Optional[float]:
    """سنِ آخرینِ افزایشِ شمارندهٔ معامله، از h_even/d_evenِ feed (تقریبِ ساعتی)."""
    # h_even معمولاً «HHMM» یا ثانیهٔ روز است؛ اگر نبود None برمی‌گردانیم تا
    # NO_RECENT_TRADE بر پایهٔ نبودِ شاهد بماند، نه حدس.
    he = cur.get("h_even")
    try:
        he = int(he)
    except (TypeError, ValueError):
        return None
    # تبدیلِ HHMM به ثانیهٔ روز؛ اگر منبع ثانیهٔ خام داد همان استفاده می‌شود.
    if he > 86400:
        secs = he
    else:
        hh, mm = divmod(he, 100)
        secs = hh * 3600 + mm * 60
    # now_wall از زمانِ واقعیِ سیستمِ تهران در فراخوان بیرونی می‌آید؛ اینجا فقط
    # اختلافِ feed را با «اکنونِ feed» می‌سنجیم — caller باید now_feed_wall بدهد.
    return None   # محافظه‌کارانه: بدونِ ساعتِ مطمئنِ تهران، سنِ معامله را حدس نمی‌زنیم


class UniverseTracker:
    """نگهدارندۀِ snapshotِ آخرین‌دیده‌شدهٔ هر نماد + تولیدِ فهرستِ اولویت‌دار.

    بر مبنایِ revision/شمارندهٔ تجمعی کار می‌کند تا یک دادهٔ ثابت را چند بار
    معاملۀِ جدید نشمارد. برایِ هر نماد وضعیت + دلیل + شاهد ثبت می‌کند.
    """

    def __init__(self, *, trade_window_s: float = DEFAULT_TRADE_WINDOW_S,
                 stale_window_s: float = DEFAULT_STALE_WINDOW_S):
        self.trade_window_s = trade_window_s
        self.stale_window_s = stale_window_s
        self._prev: dict[str, dict] = {}

    def observe(self, rows: Iterable[dict], *, market_open: bool,
                now_wall: Optional[float] = None,
                key: str = "symbol") -> tuple[list[dict], dict]:
        now_wall = now_wall if now_wall is not None else time.time()
        results: list[dict] = []
        counts = {"total": 0, "eligible": 0, "trading": 0, "quote": 0,
                  "no_trade": 0, "stale": 0, "suspended": 0, "unknown": 0}
        for r in rows:
            sym = r.get(key) or r.get("ins_code")
            if not sym:
                continue
            counts["total"] += 1
            prev = self._prev.get(str(sym))
            cls = classify_trading_status(r, prev, market_open=market_open, now_wall=now_wall,
                                          trade_window_s=self.trade_window_s,
                                          stale_window_s=self.stale_window_s)
            self._prev[str(sym)] = r   # snapshot برایِ دورِ بعد
            st = cls["status"]
            rec = {"symbol": sym, "status": st, "reason": cls["reason"],
                   "evidence": cls["evidence"], "priority": PRIORITY.get(st, 9)}
            results.append(rec)
            if st in (TRADING_ACTIVE, QUOTE_ACTIVE_NO_TRADE, NO_RECENT_TRADE):
                counts["eligible"] += 1
            counts[{"TRADING_ACTIVE": "trading", "QUOTE_ACTIVE_NO_TRADE": "quote",
                    "NO_RECENT_TRADE": "no_trade", "STALE_DATA": "stale",
                    "SUSPENDED": "suspended", "UNKNOWN": "unknown",
                    "MARKET_CLOSED": "unknown"}.get(st, "unknown")] += 1
        results.sort(key=lambda x: x["priority"])
        return results, counts
