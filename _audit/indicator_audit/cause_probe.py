# -*- coding: utf-8 -*-
"""`_audit/indicator_audit/cause_probe.py` — اثباتِ «علت» برایِ هر واگراییِ جدول.

برایِ هر اندیکاتورِ واگرا، یکِ **variant** ساخته می‌شود که دقیقاً همان کاری را بکند
که کدِ محصول می‌کند (بذرِ دوتabled، ورودیِ غلطِ برچسب‌خورده، TR از close تنها، …).
اگر variant با bad=0 بخواند، علت ثابت شده است؛ در غیر این صورت علت «نامعلوم» می‌ماند
و درِ گزارش هم همین‌طور نوشته می‌شود. هیچ کدِ محصولی عوض نمی‌شود.

اجرا:  python _audit/indicator_audit/cause_probe.py   →  causes.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import oracle as O                        # noqa: E402

RT = 0.005


def bad_count(a, b, rt=RT):
    n = min(len(a), len(b))
    k = 0
    for i in range(n):
        x, y = a[i], b[i]
        if x is None or y is None:
            if (x is None) != (y is None):
                k += 1
            continue
        if abs(float(x) - float(y)) > rt * max(1.0, abs(float(y))):
            k += 1
    return k, n


def wma_normalize(vals, period):
    """WMA نسخۀ TS: بی‌مقدارها از هر دو جمع (صورت و وزن) حذف می‌شوند."""
    out = []
    for i in range(len(vals)):
        if i < period - 1:
            out.append(None)
            continue
        s = w = 0.0
        for j in range(period):
            v = vals[i - j]
            if v is None:
                continue
            s += v * (period - j)
            w += period - j
        out.append(s / w if w else None)
    return out


def supertrend_close_only_tr(h, l, c, period=10, mult=3.0):
    """نسخۀ mabnaIndicators: «TR» تنها از تفاضلِ closeها (high/low نادیده)."""
    tr = [None]
    for i in range(1, len(c)):
        d = abs(c[i] - c[i - 1])
        tr.append(max(d, d, c[i] - c[i - 1]))
    atr = O.rma(tr, period)
    ub = lb = None
    up = True
    out = [None] * len(c)
    for i in range(len(c)):
        if atr[i] is None:
            continue
        mid = (h[i] + l[i]) / 2.0
        raw_ub, raw_lb = mid + mult * atr[i], mid - mult * atr[i]
        if ub is None:
            ub, lb = raw_ub, raw_lb
        else:
            ub = min(raw_ub, ub)
            lb = max(raw_lb, lb)
        if c[i] > ub:
            up = True
        elif c[i] < lb:
            up = False
        out[i] = lb if up else ub
    return out


def main():
    candles = json.load(open(os.path.join(HERE, "candles.json"), encoding="utf-8"))
    ts = json.load(open(os.path.join(HERE, "ts_out.json"), encoding="utf-8"))["series"]
    causes = {}
    print("%-22s %-52s %8s %8s" % ("indicator", "variant (= همان کاری که محصول می‌کند)", "bad", "n"))
    print("-" * 100)
    for sym, d in sorted(candles.items()):
        c, h, l, o, v, t = d["close"], d["high"], d["low"], d["open"], d["volume"], d["time"]

        def row(ind, variant, prod, ref):
            k, n = bad_count(prod, ref)
            causes.setdefault(ind, {})[sym] = [k, n]
            if sym == "فولاد":
                print("%-22s %-52s %8d %8d" % (ind[:22], variant[:52], k, n))

        tr_ = (T := lambda key, field: ((ts.get("%s|%s" % (sym, key)) or {}).get("rows", {}) or {}).get(field, []))
        # ۱) WaveTrend: ورودیِ اعلامی hlc3 نیست، tp است
        src_tp = [(a + b + x) / 3.0 for a, b, x in zip(h, l, c)]
        src_true = [(a + b + 3 * x) / 6.0 for a, b, x in zip(h, l, c)]

        def wt(s):
            esa = O.ema(s, 10, "sma")
            dd = O.ema([None if (a is None or b is None) else abs(a - b)
                        for a, b in zip(s, esa)], 10, "sma")
            ci = [None if (a is None or b is None or not z) else (a - b) / (0.015 * z)
                  for a, b, z in zip(s, esa, dd)]
            return O.ema(ci, 21, "sma")
        row("WaveTrend wt", "ورودی = (H+L+C)/3 به‌جای hlc3", tr_("MabnaWaveTrend", "wt"), wt(src_tp))
        row("WaveTrend wt", "مرجع‌صحیح: ورودی = hlc3 واقعی", tr_("MabnaWaveTrend", "wt"), wt(src_true))
        # ۲) HMA: نیمۀ‌دوره با Math.round و نرمال‌سازیِ بی‌مقدار
        wh = wma_normalize(c, 5)
        wf = wma_normalize(c, 9)
        diff = [None if (a is None or b is None) else 2 * a - b for a, b in zip(wh, wf)]
        row("HMA(9)", "half=Math.round(9/2)=5 + WMA با نرمال‌سازی", tr_("HMA", "hma"),
            wma_normalize(diff, 3))
        row("HMA(9)", "مرجع‌صحیح: half=floor(4) ≡ Halma/TA-Lib", tr_("HMA", "hma"), O.hma(c, 9, "floor"))
        # ۳) SuperTrend: TR از close تنها + قفلِ بندِ یک‌طرفه
        row("SuperTrend(10,3)", "TR تنها از close (high/low نادیده)", tr_("SuperTrend", "superTrend"),
            supertrend_close_only_tr(h, l, c, 10, 3.0))
        row("SuperTrend(10,3)", "مرجع‌صحیح: ATRِ واقعیِ Wilder", tr_("SuperTrend", "superTrend"),
            [x.get("line") for x in O.supertrend(h, l, c, 10, 3.0)])
        # ۴) VWAP: بدونِ ریستِ روزانه
        row("VWAP", "Σ تجمعی بی‌ریست (variantِ بی‌ریست)", tr_("VWAP", "vwap"),
            O.vwap(o, h, l, c, v, t, "full", "tp"))
        row("VWAP", "مرجع‌صحیح: session-anchored ≡ Harris", tr_("VWAP", "vwap"),
            O.vwap(o, h, l, c, v, t, "session", "tp"))
    out = os.path.join(HERE, "causes.json")
    json.dump(causes, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    agg = {}
    for ind, per in causes.items():
        agg[ind] = [sum(x[0] for x in per.values()), sum(x[1] for x in per.values()), len(per)]
    print("\nجمعِ ۱۲ نماد:")
    for ind, (b, n, s) in sorted(agg.items()):
        print("   %-24s bad=%-7d n=%-7d symbols=%d" % (ind, b, n, s))
    print("→", out)


if __name__ == "__main__":
    main()
