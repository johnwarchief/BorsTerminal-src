# -*- coding: utf-8 -*-
# structure_engine3.py -- موتور سومِ تحلیلی: ZigZagِ آستانه‌دار بر بسترِ ATR٪
#
# مأموریت (docs/FTS-INDICATOR-MISSION-PLAN.md §۴ بند ۴): موتورِ سوم باید
# «تفاوتِ الگوریتمیِ محاسبه‌پذیر» با موتورِ اول داشته باشد، نه بازمصرفِ همان
# فراکتالِ k=3. اینجا پیوت از آستانهٔ برگشتِ درصدیِ مبتنی بر ATR می‌آید (نه از
# مقایسهٔ همسایه‌ها) و زمانِ تأیید «لحظهٔ بازگشتِ کافی» است (نه idx+k). پس روی
# همان داده فهرست پیوت‌ها می‌تواند متفاوت باشد و همین مقایسه را معنا می‌دهد.
#
# قواعدِ زمان (anti-repaint):
#   - یک extreme فقط وقتی پیوت می‌شود که closeِ کندلی از آن به اندازهٔ آستانه
#     فاصله گرفته باشد؛ confirm_idx/confirm_time همان کندلِ برگشت است.
#   - ekstremumِ بی‌برگشت «pending» اعلام می‌شود و رسم نمی‌شود.
#   - مسئولیتِ برشِ کندلِ در حال تشکیل با فراخوان است (سریِ بستۀ بسته بدهید --
#     همان قراردادِ _fts_clean_candles در api/chart.py).
#
# صداقتِ آستانه: ATR_MULT و FLOOR_PCT پارامترِ اجرایِ این موتورِ مقایسه‌ای‌اند؛
# جزوه برای ZigZagِ آستانه‌دار عددی نمی‌دهد (سطرهایِ AMBIGUOUS در
# FTS-RULE-ALGORITHM-MAP.md -- اختراع نمی‌شود). این موتور در قیف/داوریِ رسمی
# وارد نمی‌شود؛ مصرفش harnessِ مقایسه (dev/structure_engine3_compare_v1.py)
# و لایۀ «موتورِ سوم» است، بی‌تغییرِ رأیِ `/api/fts`.

from __future__ import annotations

import math

ATR_PERIOD = 14
ATR_MULT = 1.0
FLOOR_PCT = 3.0


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def atr_series(candles, period=ATR_PERIOD):
    """ATRِ Wilder بر True Range؛ خانه‌هایِ warm-up ⇒ None («سنجیده نشد»، نه صفر)."""
    n = len(candles)
    out = [None] * n
    if n < period:
        return out
    tr = []
    for i in range(n):
        h, l = _num(candles[i].get("high")), _num(candles[i].get("low"))
        prev = _num(candles[i - 1].get("close")) if i > 0 else None
        if h is None or l is None:
            tr.append(None)
            continue
        base = h - l
        if prev is not None:
            base = max(base, abs(h - prev), abs(l - prev))
        tr.append(base)
    seed = tr[:period]
    if any(t is None for t in seed):
        return out
    atr = sum(seed) / period
    out[period - 1] = atr
    for i in range(period, n):
        t = tr[i]
        if t is not None:
            atr = (atr * (period - 1) + t) / period
        out[i] = atr
    return out


def _threshold(atr, ref_price, atr_mult, floor_pct):
    """آستانهٔ٪ بینِ دو پیوت: max(floor, mult×ATR%) روی بستِ مرجع.

    بی‌ATRِ معتبر فقط floor_pct جاری می‌شود؛ meta هر دو حالت را جدا می‌شمارد
    تا harness بداند چند تأیید «بی‌ATR» بوده است.
    """
    if atr is None or ref_price is None or ref_price <= 0:
        return floor_pct, False
    return max(floor_pct, atr_mult * 100.0 * atr / ref_price), True


def _time(candles, i):
    return candles[i].get("time") if 0 <= i < len(candles) else None


def zigzag(candles, atr_mult=ATR_MULT, floor_pct=FLOOR_PCT, atr_period=ATR_PERIOD):
    """ZigZagِ آستانه‌دارِ زمان‌دار.

    خروجی: {'pivots': [ {'idx','time','price','kind','confirm_idx','confirm_time',
    'threshold_pct','atr_used'} ], 'meta': {...}} -- kind ∈ {'high','low'} و
    پیوت‌ها یک‌درمیان alternating. pendingِ آخر (بی‌برگشتِ کافی) در meta می‌نشیند.
    """
    n = len(candles)
    meta = {"bars": n, "atr_period": atr_period, "atr_mult": atr_mult,
            "floor_pct": floor_pct, "confirmed_atr": 0, "confirmed_floor_only": 0,
            "pending": None}
    if n < 2:
        return {"pivots": [], "meta": meta}
    atrs = atr_series(candles, atr_period)
    pivots = []
    hi_i = lo_i = 0
    hi_p = lo_p = None
    direction = None  # None تا نخستین پیوت؛ سپس 'up' یعنی کفِ تأییدشده و سقفِ جاری دنبال می‌شود
    atr_none_rows = 0
    for i in range(n):
        h, l, c = (_num(candles[i].get("high")), _num(candles[i].get("low")),
                   _num(candles[i].get("close")))
        if i >= atr_period and atrs[i] is None:
            atr_none_rows += 1
        if h is None or l is None:
            continue
        if hi_p is None or h > hi_p:
            hi_p, hi_i = h, i
        if lo_p is None or l < lo_p:
            lo_p, lo_i = l, i
        if c is None or c <= 0:
            continue
        if direction is None:
            thr_h, ok_h = _threshold(atrs[hi_i], hi_p, atr_mult, floor_pct)
            thr_l, ok_l = _threshold(atrs[lo_i], lo_p, atr_mult, floor_pct)
            if hi_p is not None and hi_i < i and (hi_p - c) / hi_p * 100.0 >= thr_h:
                pivots.append(_pv(candles, hi_i, hi_p, "high", i, thr_h, ok_h, meta))
                direction = "down"
                hi_p, hi_i, lo_p, lo_i = h, i, l, i
            elif lo_p is not None and lo_i < i and (c - lo_p) / lo_p * 100.0 >= thr_l:
                pivots.append(_pv(candles, lo_i, lo_p, "low", i, thr_l, ok_l, meta))
                direction = "up"
                hi_p, hi_i, lo_p, lo_i = h, i, l, i
        elif direction == "up":
            thr, ok = _threshold(atrs[hi_i], hi_p, atr_mult, floor_pct)
            if hi_i < i and (hi_p - c) / hi_p * 100.0 >= thr:
                pivots.append(_pv(candles, hi_i, hi_p, "high", i, thr, ok, meta))
                direction = "down"
                hi_p, hi_i, lo_p, lo_i = h, i, l, i
        else:  # 'down'
            thr, ok = _threshold(atrs[lo_i], lo_p, atr_mult, floor_pct)
            if lo_i < i and (c - lo_p) / lo_p * 100.0 >= thr:
                pivots.append(_pv(candles, lo_i, lo_p, "low", i, thr, ok, meta))
                direction = "up"
                hi_p, hi_i, lo_p, lo_i = h, i, l, i
    if direction is not None and (hi_p is not None or lo_p is not None):
        kind = "high" if direction == "up" else "low"
        idx, price = (hi_i, hi_p) if kind == "high" else (lo_i, lo_p)
        if price is not None:
            meta["pending"] = {"idx": idx, "time": _time(candles, idx),
                               "price": price, "kind": kind, "confirmed": False}
    meta["atr_missing_bars"] = atr_none_rows
    return {"pivots": pivots, "meta": meta}


def _pv(candles, idx, price, kind, confirm_i, thr, atr_used, meta):
    if atr_used:
        meta["confirmed_atr"] += 1
    else:
        meta["confirmed_floor_only"] += 1
    return {"idx": idx, "time": _time(candles, idx), "price": price, "kind": kind,
            "confirm_idx": confirm_i, "confirm_time": _time(candles, confirm_i),
            "threshold_pct": round(thr, 4), "atr_used": atr_used}


def label_structure(pivots):
    """برچسبِ HH/LH/HL/LL بر پیوت‌هایِ alternating + رویدادِ CHoCH.

    CHoCH اینجا «واژگونیِ روندِ ساختاری» است: نخستین پیوتِ هم‌سمتی که الگوی
    دو جفتِ پیشین را می‌شکند (مثلاً پس از LH/LH یک HH). بی‌پیوت ⇒ برچسب/رویداد
    نمی‌سازیم؛ رأیِ خنثیِ بی‌داده با رأیِ خنثیِ واقعی یکی نیست، پس None می‌دهیم.
    """
    highs = [p for p in pivots if p["kind"] == "high"]
    lows = [p for p in pivots if p["kind"] == "low"]
    out = []
    for p in pivots:
        q = dict(p)
        if p["kind"] == "high":
            prev = [h for h in highs if h["idx"] < p["idx"]]
            q["label"] = None if not prev else ("HH" if p["price"] > prev[-1]["price"] else "LH")
        else:
            prev = [w for w in lows if w["idx"] < p["idx"]]
            q["label"] = None if not prev else ("HL" if p["price"] > prev[-1]["price"] else "LL")
        out.append(q)
    events = []
    for p in out[2:]:
        same = [x for x in out if x["kind"] == p["kind"] and x["idx"] < p["idx"]]
        if len(same) < 2:
            continue
        a, b = same[-2], same[-1]
        flip_up = p["label"] == "HH" and a["label"] == "LH" and b["label"] == "LH"
        flip_down = p["label"] == "LL" and a["label"] == "HL" and b["label"] == "HL"
        if flip_up or flip_down:
            events.append({"kind": p["kind"], "direction": "bullish" if flip_up else "bearish",
                           "idx": p["idx"], "time": p["time"],
                           "confirm_idx": p["confirm_idx"], "confirm_time": p["confirm_time"],
                           "level": p["price"]})
    return {"points": out, "choch": events}
