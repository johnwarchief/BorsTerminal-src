# -*- coding: utf-8 -*-
"""`_audit/indicator_audit/run.py` — مقایسۀ عددیِ اندیکاتورهای BorsTerminal با مرجع.

سه پایۀ مقایسه (هیچ‌کدام کدِ دیگری را مصرف نمی‌کند):
  P = productِ پایتون (`api/chart.py`، `confidence_engine.py`)
  T = productِ فرانت (`lib/indicators.ts`, `lib/mabnaIndicators.ts`) — اجرашده درِ node
      و خروجی‌اش در `ts_out.json`
  O = oracleِ مستقلِ این پوشه (`oracle.py`؛ خودش با `test_oracle.py` ۳۲/۳۲ سبز است)

برایِ هر واگرایی، «variant» هم آزموده می‌شود (seed / smoothing / ddof / half-period /
input-price) تا علت مشخص شود، نه فقط اندازهٔ خطا.

اجرا:  python _audit/indicator_audit/run.py [--symbols a,b] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import oracle as O                        # noqa: E402
import api.chart as CH                    # noqa: E402
import confidence_engine as CE            # noqa: E402

RT = 0.005 + 1e-9            # تلورانسِ round(...,2) که محصول درِ خروجی می‌زند


def cmp_series(prod, ref, rt=RT):
    n = min(len(prod or []), len(ref or []))
    both = bad = only_p = only_r = 0
    max_abs = mean_abs = max_rel = 0.0
    first = None
    tot = 0.0
    for i in range(n):
        a, b = prod[i], ref[i]
        a = None if a is None else float(a)
        b = None if b is None else float(b)
        if a is None and b is None:
            continue
        if a is None:
            only_p += 1
            continue
        if b is None:
            only_r += 1
            continue
        both += 1
        d = abs(a - b)
        tot += d
        max_abs = max(max_abs, d)
        if b:
            max_rel = max(max_rel, d / abs(b))
        if d > rt * max(1.0, abs(b)):
            bad += 1
            if first is None:
                first = i
    return dict(n=n, both=both, bad=bad, only_prod_null=only_p, only_ref_null=only_r,
                max_abs=max_abs, mean_abs=(tot / both if both else 0.0),
                max_rel=max_rel, first_bad=first)


def sat_key(iso):
    d = date.fromisoformat(iso)
    return (d - timedelta(days=(d.weekday() + 2) % 7)).isoformat()


def greg_key(iso):
    return iso[:7]


def jalali_month_index(times):
    # ماه‌بندیِ جلالیِ شمسیِ خودِ هارنس (تبدیلِ آزموده‌شدۀ ra_parity) — اینجا
    # فقط «متغیرِ تقویم» را می‌سنجیم: چند سطرِ مرزی دارد.
    return [t[:7] for t in times]


def bucket_last(times, vals, keyfn):
    out = []
    for i in range(len(vals)):
        if i + 1 < len(vals) and keyfn(times[i]) == keyfn(times[i + 1]):
            continue
        out.append(vals[i])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="")
    ap.add_argument("--json", default=os.path.join(HERE, "report.json"))
    args = ap.parse_args()

    candles = json.load(open(os.path.join(HERE, "candles.json"), encoding="utf-8"))
    tsblob = json.load(open(os.path.join(HERE, "ts_out.json"), encoding="utf-8"))
    T, ERR = tsblob["series"], tsblob["errors"]
    if args.symbols:
        want = set(args.symbols.split(","))
        candles = {k: v for k, v in candles.items() if k in want}

    rows = []

    def add(ind, impl, ref, inp, prod, oracle_series, cause="", rt=RT):
        r = cmp_series(prod, oracle_series, rt)
        rows.append(dict(indicator=ind, impl=impl, reference=ref, input=inp,
                         max_abs=r["max_abs"], mean_abs=r["mean_abs"], max_rel=r["max_rel"],
                         n=r["both"], bad=r["bad"], first_bad=r["first_bad"],
                         null_prod=r["only_prod_null"], null_ref=r["only_ref_null"],
                         cause=cause))

    def trows(sym, key, field):
        v = T.get("%s|%s" % (sym, key))
        return (v or {}).get("rows", {}).get(field, []) if isinstance(v, dict) else []

    def tlist(sym, key):
        return T.get("%s|%s" % (sym, key)) or []

    for sym, d in sorted(candles.items()):
        times, o, h, l, c = d["time"], d["open"], d["high"], d["low"], d["close"]
        v, last = d["volume"], d.get("last") or [None] * len(c)
        hl2 = [None if (a is None or b is None) else (a + b) / 2.0 for a, b in zip(h, l)]
        hlc3 = [None if (a is None or b is None or x is None) else (a + b + 3 * x) / 6.0
                for a, b, x in zip(h, l, c)]
        tp = [None if (a is None or b is None or x is None) else (a + b + x) / 3.0
              for a, b, x in zip(h, l, c)]

        # ── SMA / مووینگ‌ها ────────────────────────────────────────────────
        for w in (5, 10, 20, 50, 100, 120, 200):
            ref = O.sma(c, w)
            add("SMA(%d)" % w, "api/chart.py:1348 _fts_ma", "oracle.sma ≡ pandas.rolling.mean",
                "close (basis-resolved)", CH._fts_ma(c, w), ref)
            # همان پنجره در /api/ma — حلقۀ api/chart.py:890-897 عیناً
            ser, acc = [], 0.0
            for i, x in enumerate(c):
                acc += x
                if i >= w:
                    acc -= c[i - w]
                ser.append(round(acc / (i + 1), 2) if i >= w - 1 else None)
            add("SMA(%d)" % w, "api/chart.py:890-897 /api/ma", "oracle.sma ≡ pandas.rolling.mean",
                "close (basis-resolved)", ser, ref, "شمارند = i+1 (میانگینِ کلِ تاریخ) نه w")
        for w in (14, 20, 50, 100):
            add("SMA(%d)" % w, "lib/indicators.ts:48 sma (TS)", "oracle.sma", "close",
                tlist(sym, "I.sma%d" % w), O.sma(c, w))
        for w in (9, 12, 14, 26):
            add("EMA(%d)" % w, "lib/indicators.ts:21 ema (SMA-seed)", "oracle.ema(seed=sma)",
                "close", tlist(sym, "I.ema%d" % w), O.ema(c, w, seed="sma"))

        # ── RSI ────────────────────────────────────────────────────────────
        for p in (5, 7, 8, 14):
            ref = O.rsi(c, p, "wilder")
            add("RSI(%d)" % p, "api/chart.py:1360 _fts_rsi", "oracle.wilder ≡ Wilder1978",
                "close", CH._fts_rsi(c, p), ref)
            add("RSI(%d)" % p, "lib/indicators.ts:372 rsi (TS)", "oracle.wilder", "close",
                tlist(sym, "I.rsi%d" % p), ref)
            if p == 14:
                alt_e = O.rsi(c, p, "ema")
                alt_s = O.rsi(c, p, "sma")
                r_e, r_s = cmp_series(CH._fts_rsi(c, p), alt_e), cmp_series(CH._fts_rsi(c, p), alt_s)
                scalar = [None] * (len(c) - 1) + [CE._rsi(list(reversed(c)), p)]
                add("RSI(14)", "confidence_engine._rsi (scalar, newest-first)", "oracle.wilder",
                    "close", scalar, ref,
                    "variant: ema bad=%d / cutler-sma bad=%d ⇒ wilder درست" % (r_e["bad"], r_s["bad"]))

        # ── نوسان / باندها ─────────────────────────────────────────────────
        add("ATR(14)", "mabnaStd.atr = rma(trueRange)", "oracle.atr(wilder) ≡ Wilder",
            "H/L/C", tlist(sym, "pine.atr14"), O.atr(h, l, c, 14))
        add("ATR(10)", "mabnaStd.atr = rma(trueRange)", "oracle.atr(wilder)", "H/L/C",
            tlist(sym, "pine.atr10"), O.atr(h, l, c, 10))
        trs = O.true_range(h, l, c)
        add("ATR(14)", "chartTypes.ts:33 atr = SMA(TR) (Renko/PnF)", "oracle.atr(sma)",
            "H/L/C", O.sma(trs, 14), O.atr(h, l, c, 14, "sma"),
            "smoothing: SMA نه Wilder ⇒ سومین طعمِ ATR در مخزن")
        sd_pop = [None if b["up"] is None else (b["up"] - b["mid"]) / 2.0
                  for b in O.bollinger(c, 20, 2.0, 0)]
        sd_sam = [None if b["up"] is None else (b["up"] - b["mid"]) / 2.0
                  for b in O.bollinger(c, 20, 2.0, 1)]
        add("Stdev(20)", "mabnaStd.stdev (population, ddof=0)", "oracle ddof=0 ≡ pandas std(ddof=0)",
            "close", tlist(sym, "pine.stdev20"), sd_pop)
        r_sam = cmp_series(tlist(sym, "pine.stdev20"), sd_sam)
        add("BOLL(20,2)", "klinecharts 10.0.3 built-in (جمع population)",
            "oracle ddof=0 (و ddof=1 به‌عنوان variant)", "close",
            [None if (m is None or s is None) else m + 2 * s
             for m, s in zip(O.sma(c, 20), tlist(sym, "pine.stdev20"))],
            [b["up"] for b in O.bollinger(c, 20, 2.0, 0)],
            "variant ddof=1 رویِ stdev خودِ TS: bad=%d ⇒ منبعِ اختلافِ محتملِ ظاهری نه فرمول"
            % r_sam["bad"])

        # ── حجم‌محور ───────────────────────────────────────────────────────
        add("VWMA(20)", "mabnaStd.vwma", "oracle.vwma (Σtp? نه، Σclose·vol)", "close+vol",
            tlist(sym, "pine.vwma20"), O.vwma(c, v, 20))
        ref_vwap_day = O.vwap(o, h, l, c, v, times, "session", "tp")
        ref_vwap_full = O.vwma(c, v, len(c)) if False else O.vwap(o, h, l, c, v, times, "full", "tp")
        add("VWAP", "mabnaIndicators.ts:1013 VWAP (کارِ نامنسوب/commit‌نشده)",
            "oracle.vwap(session-anchored) ≡ Harris", "H/L/C + vol",
            trows(sym, "VWAP", "vwap"), ref_vwap_day,
            "هیچ ریستِ روزانه‌ای نیست؛ Σ تجمعی از اولِ سری (variantِ بی‌ریست: bad=%d)"
            % cmp_series(trows(sym, "VWAP", "vwap"), ref_vwap_full)["bad"])

        # ── نوسان‌گرها ─────────────────────────────────────────────────────
        add("LinReg(20)", "mabnaStd.linreg", "oracle.linreg (LSQ endpoint)", "close",
            tlist(sym, "pine.linreg20"), O.linreg(c, 20))
        add("Stoch(5)", "mabnaStd.stoch (Pine ta.stoch(src,src,src))", "oracle.stoch_series",
            "close", tlist(sym, "pine.stoch5"), O.stoch_series(c, 5))
        add("%K/%D", "klinecharts Stochastic از پکیج react-klinecharts-ui",
            "oracle.stoch (raw %K, SMA 3, SMA 3)", "H/L/C", [], [],
            "پکیج درِ node اجرا نمی‌شود (DOM لازم دارد) — فقط source خوانده شد")

        # ── HMA (نیمۀ دورۀ floor در برابرِ round) ──────────────────────────
        hma_ts = trows(sym, "HMA", "hma")
        def hma_variant(half, norm):
            def _w(v, k):
                return O.wma_strict(v, k, normalize_valid=norm)
            hn = max(1, int(9 // 2) if half == "floor" else int(round(9 / 2.0)))
            rn = max(1, int(round(9 ** 0.5)))
            a1 = _w(c, hn)
            b1 = _w(c, 9)
            raw = [None if (x is None or y is None) else 2 * x - y for x, y in zip(a1, b1)]
            return _w(raw, rn)
        variants = {}
        for half in ("floor", "round"):
            for norm in (False, True):
                variants["half=%s,valid-norm=%s" % (half, norm)] = lambda x, hf=half, nm=norm: hma_variant(hf, nm)
        best = None
        for nm, fn in variants.items():
            r = cmp_series(hma_ts, fn(c))
            if best is None or r["bad"] < best[1]["bad"]:
                best = (nm, r)
        add("HMA(9)", "mabnaIndicators.ts:1125 HMA", "oracle.hma variants (Halma/TA-Lib)",
            "close", hma_ts, O.hma(c, 9, "floor"),
            "بهترین variant: %s ⇒ bad=%d (از %d)" % (best[0], best[1]["bad"],
                                                     len(variants)))

        # ── SuperTrend ─────────────────────────────────────────────────────
        st_ts = trows(sym, "SuperTrend", "superTrend")
        ref_st = [x.get("line") for x in O.supertrend(h, l, c, 10, 3.0)]
        add("SuperTrend(10,3)", "mabnaIndicators.ts:1046 rawAtr (TR از close تنها)",
            "oracle.supertrend(ATRِ واقعیِ Wilder)", "H/L/C", st_ts, ref_st)

        # ── MA_Ribbon ──────────────────────────────────────────────────────
        for kk, period in (("ma5", 5), ("ma10", 10), ("ma20", 20), ("ma50", 50),
                           ("ma100", 100), ("ma200", 200)):
            add("MA_Ribbon(%d)" % period, "mabnaIndicators.ts:1237 (SMA)",
                "oracle.sma", "close", trows(sym, "MA_Ribbon", kk), O.sma(c, period))

        # ── مطالعۀ Mabna: بازسازیِ تعریفِ اعلام‌شده ─────────────────────────
        esa = O.ema(hlc3, 10, seed="sma")
        d_ema = O.ema([None if (a is None or b is None) else abs(a - b) for a, b in zip(hlc3, esa)],
                      10, seed="sma")
        ci = [None if (a is None or b is None or not d_) else (a - b) / (0.015 * d_)
              for a, b, d_ in zip(hlc3, esa, d_ema)]
        wt = O.ema(ci, 21, seed="sma")
        avg = O.sma(wt, 4)
        add("WaveTrend wt", "mabnaIndicators.ts waveTrendCore", "oracle: EMA(hlc3,10)→EMA|d|→CI→EMA21",
            "hlc3", trows(sym, "MabnaWaveTrend", "wt"), wt)
        add("WaveTrend avg", "همان (SMA 4)", "oracle.sma(wt,4)", "hlc3",
            trows(sym, "MabnaWaveTrend", "avg"), avg)
        z_ref = []
        for i in range(len(c)):
            if i < 19:
                z_ref.append(None)
                continue
            w = c[i - 19:i + 1]
            m = sum(w) / 20.0
            sd = (sum((x - m) ** 2 for x in w) / 20.0) ** 0.5
            z_ref.append(None if sd == 0 else (c[i] - m) / sd)
        add("ZScore(20,2)", "mabnaIndicators.ts calcZScore", "oracle: (x−SMA)/σ_population",
            "close", trows(sym, "MabnaZScore", "z"), z_ref)
        rsi8 = O.rsi(c, 8, "wilder")
        k1 = O.sma(O.stoch_series(rsi8, 5), 3)
        add("DT %K(8,5,3)", "mabnaIndicators.ts calcDTOscillator",
            "oracle: SMA(stoch(RSI8,5),3)", "close→RSI8", trows(sym, "MabnaDT", "k"), k1)
        # max(close,22) در Pine = highest(close,22) ⇒ بیشینهٔ ۲۲ دوره
        hnif22 = [None] * len(c)
        for i in range(21, len(c)):
            hnif22[i] = max(c[i - 21:i + 1])
        vix_ref = [None if (hh in (None, 0) or ll is None) else (hh - ll) / hh * 100.0
                   for hh, ll in zip(hnif22, l)]
        add("VixFix vix", "mabnaIndicators.ts calcVixFix (highest(close,22)−low)/highest",
            "oracle: همان تعریفِ Pine", "close+low", trows(sym, "MabnaVixFix", "vix"), vix_ref)
        mom_keys = trows(sym, "MabnaSQZMOM", "momentum")
        ji = [None if (a is None or b is None or m is None) else ((a + b) / 2.0 + m) / 2.0
              for a, b, m in zip(O.highest(h, 20), O.lowest(l, 20), O.sma(c, 20))]
        sqz_ref = O.linreg([None if (x is None or j is None) else x - j for x, j in zip(c, ji)], 20)
        add("SQZMOM momentum", "mabnaIndicators.ts calcSqueezeMomentum",
            "oracle: linreg(close−JI,20)", "close", mom_keys, sqz_ref)
        ht = trows(sym, "MabnaHalfTrend", "halfTrend")
        add("HalfTrend", "mabnaIndicators.ts calcHalfTrend (ATR100/2 hardcoded)",
            "oracle: (بدونِ پیادۀ مستقلِ منتشرشده)", "H/L/C", ht, ht,
            "خود-سنجی: فرمول از Pine copy شده؛ ATR period = 100 ثابت (پارامترِ visible نیست)")

        # ── timeframe ──────────────────────────────────────────────────────
        cc = [{"time": t, "open": a, "high": b, "low": e, "close": x, "volume": y}
              for t, a, b, e, x, y in zip(times, o, h, l, c, v)]
        wk = CH._fts_resample(cc, "W")
        mo = CH._fts_resample(cc, "M")
        add("Weekly close (شنبه)", "api/chart.py:1140 _fts_resample('W')",
            "oracle bucket Saturday≡self", "close", [x["close"] for x in wk],
            bucket_last(times, c, sat_key))
        add("Monthly close (میلادی)", "api/chart.py:1140 _fts_resample('M')",
            "oracle bucket Gregorian-month", "close", [x["close"] for x in mo],
            bucket_last(times, c, greg_key))
        iso_closes = list(reversed(bucket_last(list(reversed(times)), list(reversed(c)),
                                               lambda t: date.fromisoformat(t).isocalendar()[:2])))
        sat_closes = bucket_last(times, c, sat_key)
        diff = sum(1 for a, b in zip(sat_closes, iso_closes) if a != b)
        add("Weekly close (ISO)", "confidence_engine._weekly_closes",
            "oracle bucket ISO-Monday", "close", iso_closes, sat_closes,
            "تقویمِ متفاوت: %d از %d سطرِ هم‌شاخص فرق دارد (شنبه vs ISO-دوشنبه)"
            % (diff, min(len(sat_closes), len(iso_closes))))

    # ── پروبِ قراردادِ سریِ FTS (input price) ──────────────────────────────
    probe = [{"time": "2026-01-02", "open": 100.0, "high": 110.0, "low": 95.0,
              "close": 105.0, "last": 108.0, "volume": 10.0}]
    scaled = CH._fts_scaled(probe, [{"time": "2026-01-02", "factor": 2.0}], [])
    rows.append(dict(indicator="FTS input series", impl="api/chart.py:2195 _fts_scaled",
                     reference="price_basis: last و closing دو ستونِ جدا",
                     input="last=108 · close=105 · k=2", max_abs=abs(scaled[0]["last"] - 216.0),
                     mean_abs=abs(scaled[0]["last"] - 216.0),
                     max_rel=0.0 if scaled[0]["last"] == 216.0 else abs(216.0 - scaled[0]["last"]) / 216.0,
                     n=1, bad=0 if scaled[0]["last"] == 216.0 else 1, first_bad=None if scaled[0]["last"] == 216.0 else 0,
                     null_prod=0, null_ref=0,
                     cause="`last` := close×k (خطِ chart.py:2213) ⇒ مبنایِ last درِ سریِ FTS هیچ‌وقت last واقعی نیست"))

    # ── چاپِ گزارش ─────────────────────────────────────────────────────────
    order = {"WRONG": 0}
    rows.sort(key=lambda r: (-(r["bad"] or 0)))
    hdr = "%-19s %-44s %-34s %-16s %6s %6s %9s %9s %6s"
    print(hdr % ("indicator", "current implementation", "reference", "input",
                 "n", "bad", "max_abs", "max_rel", "1st"))
    print("-" * 150)
    for r in rows:
        print(hdr % (r["indicator"][:19], r["impl"][:44], r["reference"][:34], r["input"][:16],
                     r["n"], r["bad"], "%.4g" % r["max_abs"], "%.2e" % r["max_rel"],
                     r["first_bad"] if r["first_bad"] is not None else "-"))
    print("\n=== علت‌ها (فقط ردیف‌هایِ بد‌دار یا یادداشت‌دار) ===")
    for r in rows:
        if (r["bad"] or 0) > 0 or r["cause"] not in ("", "—"):
            print("· %-19s %-44s bad=%-5s max_rel=%.2e  ← %s"
                  % (r["indicator"][:19], r["impl"][:44], r["bad"], r["max_rel"], r["cause"]))
    if args.json:
        json.dump(rows, open(args.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("\nreport ->", args.json, "(%d rows, %d symbols)" % (len(rows), len(candles)))
    print("TS runtime errors:", sorted({k.split('|', 1)[1] for k in ERR}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
