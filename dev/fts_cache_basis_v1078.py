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

    # ── دوم: کشِ `/api/chart` (CHART_CACHE) مبنی‌برِ نماد خالی است — چرا درست است؟ ──
    # دورِ E پرسید این کلید race/تازگیِ مبنا دارد یا نه. پاسخِ اندازه‌گیری‌شده:
    # هر خواندن از `_attach_live_bar` می‌گذرد و آن `price_basis.resolve_payload` را
    # **پس از** کش دوباره می‌زند؛ کندلِ کش‌شده هم `closing` و `last` هر دو را نگه
    # می‌دارد و هندسه را از `high_raw/low_raw` می‌خواند، پس عوض‌شدنِ setting درِ
    # همانِ درخواست اثر می‌کند و سایه هم انباشته نمی‌شود. این دو سنجه همان
    # نامشروطی را قفل می‌کنند؛ اگر روزی خواندن از resolve_payload بگذرد و نوشتن
    # نه، این‌جا سرخ می‌شود.
    import price_basis as PB  # noqa: E402
    orig_watch, orig_basis = C._watch_live_bar, PB.current()
    # نوشتنِ مبنایِ آزمایشی نباید تنظیماتِ واقعیِ کاربر را لمس کند — همان ترفندِ
    # dev/price_basis_v1070.py: مسیرِ فایل را به یکِ پوشۀ موقت می‌بریم.
    import tempfile  # noqa: E402
    import bors_config  # noqa: E402
    tmpdir = tempfile.mkdtemp(prefix="fts_basis_chart_")
    real_path = bors_config.PRICE_BASIS_PATH
    bors_config.PRICE_BASIS_PATH = os.path.join(tmpdir, "price_basis.json")
    try:
        C._watch_live_bar = lambda symbol, after: (None, None)
        raw = [{"time": "2026-10-05", "open": 100.0, "high": 110.0, "low": 90.0,
                "close": 105.0, "last": 118.0, "volume": 10.0}]
        PB.set_basis("closing")
        r1 = C._attach_live_bar("آزمون۲", {"status": "success", "symbol": "آزمون۲",
                                           "candles": [dict(x) for x in raw],
                                           "volumes": [], "factors": []})
        PB.set_basis("last")
        r2 = C._attach_live_bar("آزمون۲", {"status": "success", "symbol": "آزمون۲",
                                           "candles": [dict(x) for x in raw],
                                           "volumes": [], "factors": []})
        ck("خواندنِ `/api/chart` مبنایِ روز را می‌زند: دو مبنا ⇒ دو closeِ متفاوت از یکِ سری",
           r1["candles"][0]["close"] == 105.0 and r2["candles"][0]["close"] == 118.0)
        # بارِ دوم رویِ سریِ **حل‌شده** — همان چیزی که درِ کشِ فال‌بک می‌نشیند
        again = C._attach_live_bar("آزمون۲", r1)
        ck("بازخوانیِ سریِ حل‌شده مبنایِ تازه را می‌گیرد و سایه را گِشادِ انباشته نمی‌کند",
           again["candles"][0]["close"] == 118.0
           and again["candles"][0]["high_raw"] == 110.0
           and again["candles"][0]["low_raw"] == 90.0)
        ck("سایه درِ پاسخِ آخر هم همان ارتفاعِ خام می‌ماند (بی‌واحدِ ساختگی)",
           again["candles"][0]["high"] >= 118.0 and again["candles"][0]["low"] <= 100.0)
    finally:
        C._watch_live_bar = orig_watch
        # بازگرداندنِ مقدار **پیش از** برگرداندنِ مسیر: فایلِ واقعیِ تنظیماتِ کاربر
        # هیچ‌وقت نوشته نمی‌شود، حتی با همانِ مقدار.
        PB.set_basis(orig_basis)
        bors_config.PRICE_BASIS_PATH = real_path
        for f in (os.path.join(tmpdir, "price_basis.json"),
                  os.path.join(tmpdir, "price_basis.json.tmp")):
            if os.path.exists(f):
                os.unlink(f)
        try:
            os.rmdir(tmpdir)
        except OSError:
            pass

    print("\nfts_cache_basis_v1078: %d سنجه، %d خطا" % (CHECKS, len(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
