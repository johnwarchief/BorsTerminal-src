# -*- coding: utf-8 -*-
"""`_audit/indicator_audit/test_oracle.py` — پیش ازِ آن‌که oracle متهمی بزند، خودش آزموده می‌شود.

دو پایهٔ آزمودن (هیچ‌کدام کدِ محصول را نمی‌خواند):
  ۱) برابریِ عددی با پیادۀ مستقلِ *نگهداشتۀ بیرونی*: `pandas` (رویِ همین ماشین
     نصبِ موجود: 3.0.5). `rolling().mean()` با SMA من، `ewm(adjust=False, alpha=…)`
     با EMAِ من، و `rolling().std(ddof=k)` با انحرافِ معیارِ Bollinger من.
  ۲)ثابت‌ماندنی‌هایِ سری‌هایِ تباهیده (constant / ramp): RSI رویِ seriesِ یکنواختِ صعودی
     باید ۱۰۰ باشد و رویِ نزولی ۰؛ ATR رویِ کندل‌هایِ یکسان صفر؛ Bollinger width
     صفر؛ EMA رویِ series ثابت همان عدد؛ CCI بی‌تغییری → None (نه صفر).

اجرا:  python _audit/indicator_audit/test_oracle.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import oracle as O  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PASS = FAIL = 0


def ck(ok, what, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  ok   " + what)
    else:
        FAIL += 1
        print("  FAIL " + what + ("   ← %s" % detail if detail else ""))


def _nn(v):
    # pandas برای warmup NaN می‌دهد و oracle None؛ یکی‌اند.
    if v is None:
        return None
    v = float(v)
    return None if v != v else v


def close(a, b, tol=1e-9):
    a, b = _nn(a), _nn(b)
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= tol


def main():
    import pandas as pd

    print("— ۱) oracle در برابرِ pandas (پیادۀ مستقلِ بیرونی)")
    data = [float(100 + (i * 7919) % 37 - 18) for i in range(1200)]
    s = pd.Series(data)
    for n in (9, 14, 20, 50, 100):
        mine = O.sma(data, n)
        theirs = s.rolling(n).mean().tolist()
        bad = [i for i in range(len(data)) if not close(mine[i], theirs[i], 1e-8)]
        ck(not bad, "SMA(%d) = pandas.rolling(%d).mean()" % (n, n),
           "first diff @%s %s vs %s" % (bad[:1], mine[bad[0]], theirs[bad[0]]) if bad else "")
    for n in (12, 26, 9, 14):
        mine = O.ema(data, n, seed="first")
        theirs = s.ewm(alpha=2.0 / (n + 1), adjust=False).mean().tolist()
        bad = [i for i in range(len(data)) if not close(mine[i], theirs[i], 1e-8)]
        ck(not bad, "EMA(%d, seed=first) = pandas.ewm(adjust=False)" % n, str(bad[:3]))
        mine = O.rma(data, n)
        theirs = s.ewm(alpha=1.0 / n, adjust=False).mean().tolist()
        # RMA من SMA-seed است و pandas مقدارِ اول را seed می‌گیرد؛ تفاوت باید
        # هندسی (1-1/n)^k بمیرد، پس پس از ۱۰n بار زیر ۱e-۶ می‌آید.
        start = 20 * n
        dev = [abs(mine[i] - _nn(theirs[i])) / max(1.0, abs(_nn(theirs[i])))
               for i in range(start, len(data))
               if mine[i] is not None and _nn(theirs[i]) is not None]
        ck(dev and max(dev) < 1e-6,
           "RMA(%d) با pandas.ewm(alpha=1/n) همگرا می‌شود (اختلافِ seed می‌میرد)" % n,
           "max rel dev %.2e" % (max(dev) if dev else float("nan")))
    n = 20
    pop = O.bollinger(data, n, 2.0, ddof=0)
    sam = O.bollinger(data, n, 2.0, ddof=1)
    tp = s.rolling(n).std(ddof=0).tolist()
    ts = s.rolling(n).std(ddof=1).tolist()
    m_pop = [None if (p["up"] is None or p["mid"] is None) else p["up"] - p["mid"] for p in pop]
    m_sam = [None if (p["up"] is None or p["mid"] is None) else p["up"] - p["mid"] for p in sam]
    ck(all(close(a, None if b != b else b * 2.0, 1e-8)
           for a, b in zip(m_pop[19:], tp[19:])),
       "Bollinger(ddof=0) = pandas.std(ddof=0)×2")
    ck(all(close(a, None if b != b else b * 2.0, 1e-8)
           for a, b in zip(m_sam[19:], ts[19:])),
       "Bollinger(ddof=1) = pandas.std(ddof=1)×2")
    up_sma = s.rolling(n).mean().tolist()
    ck(all(close(pop[i]["mid"], up_sma[i], 1e-9) for i in range(len(data))),
       "Bollinger mid = SMA (هر دو)")

    print("\n— ۲) ثابت‌ماندنی‌هایِ سری‌هایِ تباهیده")
    flat = [50.0] * 60
    hi = [51.0] * 60
    lo = [49.0] * 60
    vol = [1000.0] * 60
    ck(all(v == 50.0 for v in O.ema(flat, 14, seed="first") if v is not None)
       and all(v == 50.0 for v in O.sma(flat, 14) if v is not None),
       "EMA/SMA رویِ series ثابت = همان عدد")
    r_up = O.rsi([10.0 + i for i in range(40)], 14)
    r_dn = O.rsi([100.0 - i for i in range(40)], 14)
    ck(r_up[39] == 100.0, "RSI seriesِ صعودیِ خالص = ۱۰۰", str(r_up[39]))
    ck(close(r_dn[39], 0.0, 1e-9), "RSI seriesِ نزولیِ خالص = ۰", str(r_dn[39]))
    ck(all(v is not None and abs(v - 2.0) < 1e-9 for v in O.atr(hi, lo, flat, 14)[14:]),
       "ATR بازۀ ثابتِ ۲ واحدی = همان ۲ (Wilder رویِ TR ثابت واگرا نمی‌شود)")
    ck(all(p["width"] == 0.0 for p in O.bollinger(flat, 20) if p["width"] is not None),
       "Bollinger width رویِ series ثابت = صفر")
    ck(all(v is None for v in O.cci(hi, lo, flat, 20)),
       "CCI بی‌تغییری → None (نه صفرِ گمراه‌کننده)")
    st = O.stoch(hi, lo, flat, 14, 3, 3)
    ck(close(st[39]["k"], 50.0, 1e-9), "Stoch %K رویِ close میانیِ بازه = ۵۰", str(st[39]))
    vw = O.vwap(flat, hi, lo, flat, vol, ["2026-01-%02d" % (i % 28 + 1) for i in range(60)])
    ck(all(v == 50.0 for v in vw[20:] if v is not None), "VWAP ثابت = همان قیمت")
    adx = O.adx(hi, lo, flat, 14)
    ck(all(d["adx"] is None or d["adx"] < 1e-9 for d in adx), "ADX بی‌نوسان ≈ صفر",
       str([d["adx"] for d in adx[20:26]]))
    roc = O.momentum_roc(flat, 10)
    ck(all(v == 0.0 for v in roc[10:] if v is not None), "ROC series ثابت = صفر")
    hm = O.hma(flat, 21)
    ck(all(v == 50.0 for v in hm[25:] if v is not None), "HMA series ثابت = همان عدد")
    ramp_hi = [10.0 + i + 1.0 for i in range(60)]
    ramp_lo = [10.0 + i - 1.0 for i in range(60)]
    ps = O.psar(ramp_hi, ramp_lo, 0.02, 0.02, 0.2)
    ck(all(p and 0.0 <= p["sar"] <= 70.0 for p in ps[1:]), "PSAR درِ بازۀ منطقیِ سری صعودی")
    ck(all(p.get("trend") == 1 for p in ps[5:] if p), "PSAR سری صعودی همیشه صعودی می‌ماند",
       str([p.get("trend") for p in ps[5:12]]))
    st2 = O.supertrend(ramp_hi, ramp_lo, [10.0 + i for i in range(60)], 10, 3.0)
    ck(all(s.get("trend") == 1 for s in st2[12:] if s), "SuperTrend سری صعودی = صعودی",
       str([s.get("trend") for s in st2[12:20]]))

    print("\n— ۳) هویت‌هایِ تحلیلی (WMA و HMA رویِ ramp)")
    ramp = [float(i) for i in range(60)]
    w = O.wma(ramp, 10)
    # وزنه‌های ۱..n رویِ ramp: WMA = i-(n-1)/2 + … → اختلافِ ثابت با SMA نصفِ (n-1)/n * slope
    diff = w[40] - O.sma(ramp, 10)[40]
    # برایِ rampِ واحدِ شیب: SMA = (n−1)/2 و WMA = 2(n−1)/3 ⇒ اختلاف = (n−1)/6
    ck(close(diff, (10 - 1.0) / 6.0, 1e-12),
       "WMA − SMA رویِ ramp = (n−1)/6", str(diff))
    ck(close(O.linreg(ramp, 12)[40], 40.0, 1e-9), "linreg رویِ ramp = خودِ نقطه",
       str(O.linreg(ramp, 12)[40]))

    print("\nنتیجه: %d سبز، %d قرمز" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
