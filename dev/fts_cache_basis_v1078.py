# -*- coding: utf-8 -*-
"""dev/fts_cache_basis_v1078.py — کلیدِ کشِ تحلیل FTS باید مبنایِ قیمت را هم ببیند

چرا: `/api/fts/{symbol}` سریِ کندل را **با مبنایِ انتخابیِ کاربر** می‌سازد
(`_fts_analysis_series` ⇒ `(candles, basis)`) و داوری را رویِ همان سری می‌کند،
ولی کلیدِ `FTS_ANALYSIS_CACHE` فقط `symbol|last_close|entry_hint` بود. برایِ
نمادی که آخرینِ کندلش `last == closing` است (سقفِ روز، یا نمادِ بی‌معامله در
انتهای نشست) عوض‌کردنِ مبنایِ قیمتِ «آخرین ↔ پایانی» کلید را عوض نمی‌کرد و
تا ۹۰۰ ثانیه همان داوریِ مبنایِ قبلی پاسخ داده می‌شد — در حالی که سه کشِ دیگرِ
همین فایل (`key-levels`، `ma`، `patterns`) مبنا را درِ کلید دارند.

گارد دو چیز را ثابت می‌کند، و هر دو با **کنترلِ منفی** (سنجشِ اینکه اگر کلید
مبنا را نداشت، می‌بایست می‌سوخت):
  ۱) یکِ مبنا، دو فراخوانی ⇒ یکِ کلیدِ کش و همان پاسخ از کش (بی‌محاسبۀ دوباره)؛
  ۲) دو مبنا ⇒ دو کلیدِ جدا و پاسخِ مبنایِ دوم از کشِ اول نمی‌آید.

بی‌شبکه و بی‌بانک: `_fts_analysis_series` و `_fts_analyze_candles` جعل می‌شوند؛
هیچ نوشتنی رویِ market.db یا CDN نیست.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api.chart as C  # noqa: E402

FAILS = []
CHECKS = 0


def ck(label, cond):
    global CHECKS
    CHECKS += 1
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        FAILS.append(label)


def bars(n=140, drift=1.0):
    out = []
    px = 100.0
    for i in range(n):
        px += drift if i % 3 else -drift / 2.0
        o = px - drift
        h = px + drift
        l = px - drift * 1.5
        out.append({"time": f"2026-0{(i % 9) + 1}-{(i % 28) + 1:02d}",
                    "open": round(o, 2), "high": round(h, 2),
                    "low": round(l, 2), "close": round(px, 2),
                    "last": round(px, 2), "volume": 1000.0 + i})
    return out


SERIES = {}          # basis -> candles
CALLS = {"analyze": 0}
LAST_CLOSE = None    # آخرینِ close در هر دو مبنا عمداً یکی است (حالتِ خطرناک)


def fake_series(symbol):
    return SERIES["cur"], SERIES["basis"]


def fake_analyze(symbol, candles, entry_hint=None):
    CALLS["analyze"] += 1
    return {"marker": CALLS["analyze"], "bars": len(candles),
            "basis_seen": candles[-1]["close"]}


def main():
    global LAST_CLOSE
    C._fts_analysis_series = fake_series
    C._fts_analyze_candles = fake_analyze
    C.FTS_ANALYSIS_CACHE.clear()

    same = bars()
    # هر دو مبنا «آخرینِ ته‌بندیِ یکسان» دارند ⇒ کلیدِ قدیمی تصادماً می‌خورد
    diff = [dict(r) for r in same]
    assert diff[-1]["close"] == same[-1]["close"]
    LAST_CLOSE = same[-1]["close"]

    SERIES.update({"cur": same, "basis": "last"})
    a1 = C._fts_analyze_symbol("آزمون۱")
    a2 = C._fts_analyze_symbol("آزمون۱")
    ck("یکِ مبنا، دو فراخوانی ⇒ یکِ محاسبه (دومی از کش آمد)",
       CALLS["analyze"] == 1 and a1 is a2)
    ck("یکِ مبنا ⇒ یکِ کلیدِ کش", len(C.FTS_ANALYSIS_CACHE) == 1)

    SERIES.update({"cur": diff, "basis": "closing"})
    b1 = C._fts_analyze_symbol("آزمون۱")
    ck("دو مبنا ⇒ محاسبهٔ دوباره انجام شد (پاسخِ کهنه از کشِ مبنایِ دیگر نیامد)",
       CALLS["analyze"] == 2 and b1 is not a1)
    ck("دو مبنا ⇒ دو کلیدِ جدا در کش", len(C.FTS_ANALYSIS_CACHE) == 2)
    keys = sorted(C.FTS_ANALYSIS_CACHE)
    ck("کلیدها مبنا را در خود دارند (تنها چیزی که تفاوتِ مبنا را می‌بیند)",
       all("last" in k or "closing" in k for k in keys) and len({k.split("|")[-1] for k in keys}) == 2)

    # ── کنترلِ منفی: همان سناریو با کلیدِ بدونِ مبنا باید بشکند ───────────
    C.FTS_ANALYSIS_CACHE.clear()
    CALLS["analyze"] = 0
    orig_key = C._fts_analyze_symbol.__code__

    def no_basis_symbol(symbol, entry_hint=None):
        candles, basis = fake_series(symbol)
        key = f"{symbol}|{candles[-1].get('close')}|{entry_hint}"   # کلیدِ پیشین
        cached = C.FTS_ANALYSIS_CACHE.get(key)
        if cached:
            return cached[1]
        r = fake_analyze(symbol, candles, entry_hint=entry_hint)
        C.FTS_ANALYSIS_CACHE[key] = (0.0, r)
        return r

    C._fts_analyze_symbol = no_basis_symbol
    SERIES.update({"cur": same, "basis": "last"})
    x1 = C._fts_analyze_symbol("آزمون۱")
    SERIES.update({"cur": diff, "basis": "closing"})
    x2 = C._fts_analyze_symbol("آزمون۱")
    ck("کنترلِ منفی: با کلیدِ بدونِ مبنا، پاسخِ مبنایِ دوم همانِ اول است (یعنی گارد حساس است)",
       x2 is x1 and CALLS["analyze"] == 1)
    C._fts_analyze_symbol = getattr(C, "_real_fts_analyze_symbol", C._fts_analyze_symbol)
    del orig_key

    print("\nfts_cache_basis_v1078: %d سنجه، %d خطا" % (CHECKS, len(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
