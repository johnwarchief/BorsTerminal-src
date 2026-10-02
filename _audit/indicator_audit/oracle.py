# -*- coding: utf-8 -*-
"""`_audit/indicator_audit/oracle.py` — پیادۀ مرجعِ مستقل برایِ ممیزیِ اندیکاتورها.

چرا این فایل این‌جاست: مرحلهٔ «Indicator Audit» می‌خواهد بداند خروجیِ اندیکاتورهای
BorsTerminal (فرانتِ TS، پایتونِ بک‌اند، و klinecharts) با تعریفِ استاندارد می‌خواند
یا نه. هیچ library تازۀ TA به پروژه افزوده نشده (TA-Lib/pandas_ta/ta رویِ همین
ماشین نصب نیستند و قانونِ مرحله «افزودنِ وابستگی» را منع می‌کند). مرجع سه‌پایه است:

  ۱) تعریفِ کتابِ مرجعِ همان اندیکاتور (Wilder 1978، Appel، Bollinger، Lambert،
     Elder/Halma برایِ HMA، Harris برایِ VWAP) — این‌جا مستقل از کدِ محصول نوشته شده.
  ۲) `pandas` (نصبِ موجود رویِ ماشین: pandas 3.0.5) به‌عنوان پیادۀ مستقلِ
     `rolling().mean()` / `ewm()` / `std(ddof=)` برایِ همین داده‌ها — تنها برایِ
     مووینگ‌ها و انحرافِ معیار، که معناشان درِ pandas مستند است.
  ۳) «variant»: هر تابعِ چند قرائتِ معتبر را با یکِ flag تولید می‌کند
     (seed=SMA-یا-first-value، smoothing=Wilder-یا-EMA-یا-SMA، ddof=0-یا-1،
     input=close-یا-typical-یا-hl2)، تا واگراییِ دیده‌شده **قابل‌انتساب** باشد:
     اگر variant دیگری عددِ محصول را بیت‌به‌بیت تولید کرد، علت «smoothing/seed/
     rounding» است نه «bug».

هیچ کدِ محصولی از این فایل import نمی‌شود و این فایل هیچ کدِ محصولی را import
نمی‌کند. اجرا: `python _audit/indicator_audit/run.py`.
"""
from __future__ import annotations

import math
from typing import Callable, Iterable, Optional, Sequence

List = list
NaN = None


def _f(x) -> Optional[float]:
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


# ─────────────────────────────────────── moving averages ───────────────────────────────────────

def sma(vals: Sequence, n: int) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(vals)
    s = 0.0
    cnt = 0
    for i, v in enumerate(vals):
        x = _f(v)
        s += x if x is not None else 0.0
        cnt += 1 if x is not None else 0
        if i >= n:
            y = _f(vals[i - n])
            s -= y if y is not None else 0.0
            cnt -= 1 if y is not None else 0
        if i >= n - 1 and cnt == n:
            out[i] = s / n
    return out


def ema(vals: Sequence, n: int, seed: str = "sma", alpha: Optional[float] = None
        ) -> List[Optional[float]]:
    """`seed='sma'` = قاعدۀ کلاسیک (اولینِ EMA میانگینِ n مقدارِ اول، از index n-1).

    `seed='first'` = قاعدۀ TradingView/Pine برایِ `ta.ema`ی داخلیِ برخی مطالعه‌ها
    (alpha از اولینِ مقدارِ معتبر شروع می‌شود، پس از index 0 عدد داریم).
    """
    out: List[Optional[float]] = [None] * len(vals)
    a = alpha if alpha is not None else 2.0 / (n + 1.0)
    xs = [_f(v) for v in vals]
    if n < 1:
        return out
    first = next((i for i, x in enumerate(xs) if x is not None), None)
    if first is None:
        return out
    if seed == "sma":
        start = first + n - 1
        if start >= len(xs):
            return out
        window = xs[first:start + 1]
        if any(x is None for x in window):
            # پنجره بی‌مقدار: از اولینِ پنجرۀ کاملِ بعدی شروع کن
            for j in range(start, len(xs)):
                window = xs[j - n + 1:j + 1]
                if all(x is not None for x in window):
                    start, break_window = j, None
                    break
            else:
                return out
        prev = sum(window) / n                     # type: ignore[arg-type]
        out[start] = prev
        for i in range(start + 1, len(xs)):
            if xs[i] is None:
                continue
            prev = xs[i] * a + prev * (1 - a)
            out[i] = prev
    else:
        prev = xs[first]
        out[first] = prev
        for i in range(first + 1, len(xs)):
            if xs[i] is None:
                continue
            prev = xs[i] * a + prev * (1 - a)
            out[i] = prev
    return out


def rma(vals: Sequence, n: int) -> List[Optional[float]]:
    """Wilder's smoothing = EMA با alpha = 1/n (تعریفِ Wilder 1978)."""
    return ema(vals, n, seed="sma", alpha=1.0 / n)


def wma(vals: Sequence, n: int) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(vals)
    xs = [_f(v) for v in vals]
    denom = n * (n + 1) / 2.0
    for i in range(n - 1, len(xs)):
        w = xs[i - n + 1:i + 1]
        if any(x is None for x in w):
            continue
        out[i] = sum((k + 1) * x for k, x in enumerate(w)) / denom
    return out


def hma(vals: Sequence, n: int, half: str = "floor") -> List[Optional[float]]:
    """HMA (Halma): WMA(2·WMA(x, n/2) − WMA(x, n), √n).

    `half` = قرائتِ متفاوتِ «نصفِ دوره»: floor (کتابِ Halma و TA-Lib و پکیجِ
    react-klinecharts-ui) در برابرِ round (نسخۀ commit‌نشندۀ mabnaIndicators).
    """
    half_n = max(1, int(n // 2) if half == "floor" else int(round(n / 2.0)))
    root = max(1, int(round(math.sqrt(n))))
    a = wma(vals, half_n)
    b = wma(vals, n)
    raw = [None if (a[i] is None or b[i] is None) else 2 * a[i] - b[i] for i in range(len(vals))]
    return wma(raw, root)


def linreg(vals: Sequence, n: int) -> List[Optional[float]]:
    """Pine `ta.linreg`: بهترین برازشِ خطی رویِ n نقطه، مقدارِ نقطۀ آخر + intercept."""
    out: List[Optional[float]] = [None] * len(vals)
    xs = [_f(v) for v in vals]
    for i in range(n - 1, len(xs)):
        w = xs[i - n + 1:i + 1]
        if any(x is None for x in w):
            continue
        sx = n * (n - 1) / 2.0
        sxx = (n - 1) * n * (2 * n - 1) / 6.0
        sy = sum(w)                                       # type: ignore[arg-type]
        sxy = sum(k * x for k, x in enumerate(w))
        d = n * sxx - sx * sx
        if d == 0:
            continue
        b = (n * sxy - sx * sy) / d
        a = (sy - b * sx) / n
        out[i] = a + b * (n - 1)
    return out


# ─────────────────────────────────────── oscillators ───────────────────────────────────────

def rsi(closes: Sequence, n: int = 14, smooth: str = "wilder") -> List[Optional[float]]:
    """RSI — سه قرائتِ معتبر: Wilder (RMA)، EMA کلاسیک، و SMA متحرک (Cutler)."""
    xs = [_f(v) for v in closes]
    gain: List[Optional[float]] = [None] * len(xs)
    loss: List[Optional[float]] = [None] * len(xs)
    prev = None
    for i, x in enumerate(xs):
        if x is None:
            continue
        if prev is not None:
            d = x - prev
            gain[i] = d if d > 0 else 0.0
            loss[i] = -d if d < 0 else 0.0
        prev = x
    smooth_f: Callable[[List[Optional[float]], int], List[Optional[float]]] = {
        "wilder": rma, "ema": lambda v, k: ema(v, k, seed="sma"), "sma": sma,
    }[smooth]
    ag, al = smooth_f(gain, n), smooth_f(loss, n)
    out: List[Optional[float]] = [None] * len(xs)
    for i in range(len(xs)):
        if ag[i] is None or al[i] is None:
            continue
        if al[i] == 0:
            out[i] = 100.0
        else:
            rs = ag[i] / al[i]
            out[i] = 100.0 - 100.0 / (1.0 + rs)
    return out


def macd(closes: Sequence, fast: int = 12, slow: int = 26, signal: int = 9,
         seed: str = "first") -> List[dict]:
    xs = [_f(v) for v in closes]
    f = ema(xs, fast, seed=seed)
    s = ema(xs, slow, seed=seed)
    line = [None if (f[i] is None or s[i] is None) else f[i] - s[i] for i in range(len(xs))]
    sig = ema(line, signal, seed=seed)
    return [{"macd": line[i], "signal": sig[i],
             "hist": (None if (line[i] is None or sig[i] is None) else line[i] - sig[i])}
            for i in range(len(xs))]


def stoch(highs: Sequence, lows: Sequence, closes: Sequence, k_period: int = 14,
          smooth_k: int = 3, d_period: int = 3, ma: str = "sma") -> List[dict]:
    xs = [_f(v) for v in closes]
    hs = [_f(v) for v in highs]
    ls = [_f(v) for v in lows]
    raw: List[Optional[float]] = [None] * len(xs)
    for i in range(k_period - 1, len(xs)):
        hh = max(hs[i - k_period + 1:i + 1])
        ll = min(ls[i - k_period + 1:i + 1])
        if hh is None or ll is None or xs[i] is None or hh == ll:
            continue
        raw[i] = (xs[i] - ll) / (hh - ll) * 100.0
    smooth_f = {"sma": sma, "ema": lambda v, n: ema(v, n, seed="sma")}[ma]
    kk = smooth_f(raw, smooth_k) if smooth_k > 1 else raw
    dd = smooth_f(kk, d_period) if d_period > 1 else kk
    return [{"k": kk[i], "d": dd[i]} for i in range(len(xs))]


def bollinger(closes: Sequence, n: int = 20, mult: float = 2.0, ddof: int = 0) -> List[dict]:
    xs = [_f(v) for v in closes]
    mid = sma(xs, n)
    up: List[Optional[float]] = [None] * len(xs)
    lo: List[Optional[float]] = [None] * len(xs)
    width: List[Optional[float]] = [None] * len(xs)
    for i in range(n - 1, len(xs)):
        if mid[i] is None:
            continue
        w = xs[i - n + 1:i + 1]
        m = mid[i]
        var = sum((x - m) ** 2 for x in w) / (n - ddof)
        sd = math.sqrt(var)
        up[i], lo[i] = m + mult * sd, m - mult * sd
        width[i] = 0.0 if m == 0 else (up[i] - lo[i]) / m
    return [{"mid": mid[i], "up": up[i], "low": lo[i], "width": width[i],
             "pb": (None if (up[i] is None or lo[i] is None or up[i] == lo[i] or xs[i] is None)
                    else (xs[i] - lo[i]) / (up[i] - lo[i]))} for i in range(len(xs))]


def cci(highs: Sequence, lows: Sequence, closes: Sequence, n: int = 20,
        const: float = 0.015, input: str = "tp") -> List[Optional[float]]:
    xs = [_f(v) for v in closes]
    hs = [_f(v) for v in highs]
    ls = [_f(v) for v in lows]
    if input == "tp":
        src = [None if (hs[i] is None or ls[i] is None or xs[i] is None)
               else (hs[i] + ls[i] + xs[i]) / 3.0 for i in range(len(xs))]
    elif input == "hlc3w":
        src = [None if (hs[i] is None or ls[i] is None or xs[i] is None)
               else (hs[i] + ls[i] + 3 * xs[i]) / 6.0 for i in range(len(xs))]
    else:
        src = [None if (hs[i] is None or ls[i] is None) else (hs[i] + ls[i]) / 2.0
               for i in range(len(xs))]
    mid = sma(src, n)
    out: List[Optional[float]] = [None] * len(xs)
    for i in range(n - 1, len(xs)):
        if mid[i] is None:
            continue
        w = src[i - n + 1:i + 1]
        mad = sum(abs(x - mid[i]) for x in w) / n
        if mad == 0:
            continue
        out[i] = (src[i] - mid[i]) / (const * mad)
    return out


# ─────────────────────────────────────── volatility / trend ───────────────────────────────────────

def true_range(highs, lows, closes) -> List[Optional[float]]:
    xs = [_f(v) for v in closes]
    hs = [_f(v) for v in highs]
    ls = [_f(v) for v in lows]
    out: List[Optional[float]] = []
    for i in range(len(xs)):
        h, l, pc = hs[i], ls[i], xs[i - 1] if i else None
        if h is None or l is None:
            out.append(None)
            continue
        if pc is None:
            out.append(h - l)
            continue
        out.append(max(h - l, abs(h - pc), abs(l - pc)))
    return out


def atr(highs, lows, closes, n: int = 14, smooth: str = "wilder") -> List[Optional[float]]:
    tr = true_range(highs, lows, closes)
    if smooth == "wilder":
        return rma(tr, n)
    if smooth == "ema":
        return ema(tr, n, seed="sma")
    return sma(tr, n)


def psar(highs, lows, af0: float = 0.02, af_step: float = 0.02, af_max: float = 0.2
         ) -> List[dict]:
    """Parabolic SAR (Wilder). الگوریتمِ استاندارد با flip رویِ high/low مخالف."""
    hs = [_f(v) for v in highs]
    ls = [_f(v) for v in lows]
    n = len(hs)
    out: List[dict] = [{} for _ in range(n)]
    if n < 2:
        return out
    up = hs[1] >= hs[0]
    af, ep = af0, (max(hs[0], hs[1]) if up else min(ls[0], ls[1]))
    sar = (ls[0] if up else hs[0])
    for i in range(1, n):
        sar = sar + af * (ep - sar)
        if up:
            sar = min(sar, ls[i - 1], ls[i] if i < n else sar)
            if hs[i] > ep:
                ep, af = hs[i], min(af_max, af + af_step)
            if ls[i] < sar:
                up, sar, ep, af = False, ep, ls[i], af0
        else:
            sar = max(sar, hs[i - 1], hs[i] if i < n else sar)
            if ls[i] < ep:
                ep, af = ls[i], min(af_max, af + af_step)
            if hs[i] > sar:
                up, sar, ep, af = True, ep, hs[i], af0
        out[i] = {"sar": sar, "trend": 1 if up else -1}
    return out


def adx(highs, lows, closes, n: int = 14, smooth: str = "wilder") -> List[dict]:
    hs = [_f(v) for v in highs]
    ls = [_f(v) for v in lows]
    xs = [_f(v) for v in closes]
    n_ = len(xs)
    plus_dm: List[Optional[float]] = [None] * n_
    minus_dm: List[Optional[float]] = [None] * n_
    tr = true_range(hs, ls, xs)
    smooth_f = rma if smooth == "wilder" else (lambda v, k: ema(v, k, seed="sma"))
    for i in range(1, n_):
        up = hs[i] - hs[i - 1] if hs[i] is not None and hs[i - 1] is not None else None
        dn = ls[i - 1] - ls[i] if ls[i] is not None and ls[i - 1] is not None else None
        plus_dm[i] = up if (up is not None and dn is not None and up > dn and up > 0) else 0.0
        minus_dm[i] = dn if (up is not None and dn is not None and dn > up and dn > 0) else 0.0
    atr_n = smooth_f(tr, n)
    pdm = smooth_f(plus_dm, n)
    mdm = smooth_f(minus_dm, n)
    dx: List[Optional[float]] = [None] * n_
    dip: List[Optional[float]] = [None] * n_
    dim: List[Optional[float]] = [None] * n_
    for i in range(n_):
        if not atr_n[i]:
            continue
        dip[i] = 100.0 * pdm[i] / atr_n[i] if pdm[i] is not None else None
        dim[i] = 100.0 * mdm[i] / atr_n[i] if mdm[i] is not None else None
        if dip[i] is None or dim[i] is None:
            continue
        s = dip[i] + dim[i]
        dx[i] = 100.0 * abs(dip[i] - dim[i]) / s if s else 0.0
    adx_n = smooth_f(dx, n)
    return [{"plus": dip[i], "minus": dim[i], "dx": dx[i], "adx": adx_n[i]} for i in range(n_)]


def vwap(open_, highs, lows, closes, volumes, dates: Sequence[str],
         anchor: str = "session", src: str = "tp") -> List[Optional[float]]:
    """VWAP (Harris): Σ(price×volume)/Σ(volume). `anchor='session'` هر روز ری‌ست می‌شود،
    `'full'` از اولِ سری یکجا جمع می‌بندد. `src` = typical price یا close."""
    n = len(closes)
    price = []
    for i in range(n):
        if src == "tp":
            h, l, c = _f(highs[i]), _f(lows[i]), _f(closes[i])
            price.append(None if (h is None or l is None or c is None) else (h + l + c) / 3.0)
        else:
            price.append(_f(closes[i]))
    out: List[Optional[float]] = [None] * n
    cum_pv = cum_v = 0.0
    day = object()
    for i in range(n):
        p, v = price[i], (_f(volumes[i]) or 0.0)
        if anchor == "session":
            d = str(dates[i])[:10]
            if d != day:
                day, cum_pv, cum_v = d, 0.0, 0.0
        if p is None:
            continue
        cum_pv += p * v
        cum_v += v
        out[i] = cum_pv / cum_v if cum_v else None
    return out


def supertrend(highs, lows, closes, n: int = 10, mult: float = 3.0,
               smooth: str = "wilder") -> List[dict]:
    """SuperTrend (Villatrique): bands از ATRِ دورِ میانِ high/low، با قفلِ بند
    (band تنها وقتی جابه‌جا می‌شود که شرطِ استانداردش رخ دهد) و flip با close."""
    a = atr(highs, lows, closes, n, smooth)
    hs = [_f(v) for v in highs]
    ls = [_f(v) for v in lows]
    xs = [_f(v) for v in closes]
    out: List[dict] = [{} for _ in range(len(xs))]
    ub = lb = None
    up = True
    for i in range(len(xs)):
        if a[i] is None or xs[i] is None:
            continue
        mid = ((hs[i] + ls[i]) / 2.0) if hs[i] is not None and ls[i] is not None else xs[i]
        raw_ub, raw_lb = mid + mult * a[i], mid - mult * a[i]
        pc = xs[i - 1] if i else None
        if ub is None or lb is None:
            ub, lb = raw_ub, raw_lb
        else:
            ub = raw_ub if (raw_ub < ub or (pc is not None and pc > ub)) else ub
            lb = raw_lb if (raw_lb > lb or (pc is not None and pc < lb)) else lb
        # قاعدۀ Pine (ta.supertrend v5): جهتِ قبلی حفظ می‌شود مگر close از
        # upperBandِ نهایی بالا بزند (صعودی) یا از lowerBandِ نهایی پایین بیفتد (نزولی).
        if xs[i] > ub:
            up = True
        elif xs[i] < lb:
            up = False
        out[i] = {"trend": 1 if up else -1, "line": lb if up else ub,
                  "upper": ub, "lower": lb}
    return out


def zscore(closes: Sequence, n: int = 100, mult: float = 1.0, ddof: int = 0) -> List[dict]:
    xs = [_f(v) for v in closes]
    mid = sma(xs, n)
    out: List[dict] = [{} for _ in range(len(xs))]
    for i in range(len(xs)):
        if mid[i] is None or xs[i] is None:
            continue
        w = xs[i - n + 1:i + 1]
        sd = math.sqrt(sum((x - mid[i]) ** 2 for x in w) / (n - ddof))
        out[i] = {"mid": mid[i], "z": (xs[i] - mid[i]) / sd if sd else None,
                  "up": mid[i] + mult * sd, "low": mid[i] - mult * sd}
    return out


def momentum_roc(closes: Sequence, n: int = 10) -> List[Optional[float]]:
    xs = [_f(v) for v in closes]
    return [None if i < n or not xs[i - n] else (xs[i] - xs[i - n]) / xs[i - n] * 100.0
            for i in range(len(xs))]


def vwma(vals: Sequence, volumes: Sequence, n: int, src: Optional[Sequence] = None
         ) -> List[Optional[float]]:
    """VWMA = Σ(src·vol)/Σ(vol) رویِ پنجرۀ n; src پیش‌فرض close."""
    xs = list(src) if src is not None else [_f(v) for v in vals]
    vs = [_f(v) for v in volumes]
    out: List[Optional[float]] = [None] * len(vals)
    for i in range(n - 1, len(vals)):
        w_p, w_v = xs[i - n + 1:i + 1], vs[i - n + 1:i + 1]
        if any(p is None for p in w_p):
            continue
        den = sum(v or 0.0 for v in w_v)
        if den == 0:
            continue
        out[i] = sum((p or 0.0) * (v or 0.0) for p, v in zip(w_p, w_v)) / den
    return out


def stoch_raw(highs, lows, closes, n: int = 14, src: str = "close") -> List[Optional[float]]:
    """%K خام = (src − lowest(n)) / (highest(n) − lowest(n)) × ۱۰۰ — سه قرائتِ src."""
    hs = [_f(v) for v in highs]
    ls = [_f(v) for v in lows]
    xs = [_f(v) for v in closes]
    if src == "close":
        s_ = xs
    elif src == "hl2":
        s_ = [None if (hs[i] is None or ls[i] is None) else (hs[i] + ls[i]) / 2.0 for i in range(len(xs))]
    else:
        s_ = xs
    out: List[Optional[float]] = [None] * len(xs)
    for i in range(n - 1, len(xs)):
        hh = max(hs[i - n + 1:i + 1])
        ll = min(ls[i - n + 1:i + 1])
        if s_[i] is None or hh is None or ll is None or hh == ll:
            continue
        out[i] = (s_[i] - ll) / (hh - ll) * 100.0
    return out


def stoch_series(vals: Sequence, n: int = 14) -> List[Optional[float]]:
    """Stochastic رویِ خودِ سری (Pine `ta.stoch(src, src, src, n)`) — نه high/low."""
    xs = [_f(v) for v in vals]
    out: List[Optional[float]] = [None] * len(xs)
    for i in range(n - 1, len(xs)):
        w = xs[i - n + 1:i + 1]
        if any(x is None for x in w):
            continue
        hi, lo = max(w), min(w)
        # Pine: span==0 ⇒ na (نه ۵۰). نسخه‌هایِ na-vs-50 هر دو درِ مخزن دیده شدند.
        out[i] = None if hi == lo else (xs[i] - lo) / (hi - lo) * 100.0
    return out


def _roll(vals, n, pick):
    xs = [_f(v) for v in vals]
    out: List[Optional[float]] = [None] * len(xs)
    for i in range(n - 1, len(xs)):
        w = [x for x in xs[i - n + 1:i + 1] if x is not None]
        if len(w) == n:
            out[i] = pick(w)
    return out


def highest(vals, n):
    return _roll(vals, n, max)


def lowest(vals, n):
    return _roll(vals, n, min)


def wma_strict(vals, n, normalize_valid: bool = False) -> List[Optional[float]]:
    """WMA با دو قرائتِ «مقدارِ نامعتبر»: normalize_valid=True وزنِ آن ردیف به
    جمعِ وزن‌ها اضافه نمی‌شود (چیزی که mabnaIndicators می‌کند)."""
    xs = [_f(v) for v in vals]
    out: List[Optional[float]] = [None] * len(xs)
    for i in range(n - 1, len(xs)):
        w = xs[i - n + 1:i + 1]
        bad = [x for x in w if x is None]
        if bad and not normalize_valid:
            continue
        num = den = 0.0
        for k, x in enumerate(w):
            if x is None:
                continue
            num += (k + 1) * x
            den += (k + 1)
        out[i] = num / den if den else None
    return out
