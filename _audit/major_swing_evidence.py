#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_audit/major_swing_evidence.py — پیش از نوشتنِ دیتکتور ماژور، خودِ مشکل را می‌سنجد

سه پرسش که بی‌جواب‌شان هر آستانه‌ای «اختراع» است:
  ۱) پیوتی که جهتِ روزانه را می‌سازد چقدر کوچک است؟ (نسبتِ پایۀِ تصمیم به نوسانِ خودِ
     نماد، بر حسب ATR و درصدِ قیمت)
  ۲) اگر آن پیوت را «ماژور» نبینیم، رأیِ D به کدام طرف تکان می‌خورد و چند نماد — و
     آیا آن تکان، D را به W نزدیک‌تر می‌کند یا نه؟ (معیارِ انتخابِ آستانه، نه حدس)
  ۳) کندلِ جاریِ تزریق‌شده چقدر می‌تواند رأیِ گذشته را عوض کند؟ (اندازۀِ نشتی/repaint)

این فایل فقط می‌خواند: از get_chart_db (بانکِ محلی، بی‌شبکه) می‌گیرد و هیچ‌چیز را
 عوض نمی‌کند. هیچ رأیی درِ کدِ محصول نوشته نمی‌شود.
اجرا: python _audit/major_swing_evidence.py [--limit 80] [--out _audit/MAJOR-SWING-EVIDENCE.json]
"""
import argparse
import datetime as dt
import io
import json
import math
import os
import sqlite3
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import api.chart as CH   # noqa: E402
import major_swings as MS  # noqa: E402


def git_sha():
    import subprocess
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True).stdout.strip()
    except Exception:
        return "unknown"


def atr14(series, period=14):
    """Wilder ATR — همان تعریفِ `structure_engine3.atr_series` (تک‌تعریفِ پروژه)."""
    if len(series) < period + 1:
        return None
    trs = []
    for i in range(1, len(series)):
        h = float(series[i]["high"]); l = float(series[i]["low"]); pc = float(series[i - 1]["close"])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    a = sum(trs[:period]) / float(period)
    for tr in trs[period:]:
        a = (a * (period - 1) + tr) / float(period)
    return a


def leg_amp(pivots, i):
    """بلندیِ حاکمِ پایِ پیوت = بزرگ‌ترینِ پایِ ورودی یا خروجی (همان تعريفِ محصول).

    پایِ خروجی با داده‌ای سنجیده می‌شود که درِ لحظۀِ ارزیابی **گذشته** است (پیوتِ
    مخالفِ بعدی خودش تأیید شده)، پس نگاه‌به‌آینده نیست.
    """
    a = MS.leg_amp(pivots, i)
    b = MS.leg_amp_out(pivots, i)
    vals = [x for x in (a, b) if x is not None]
    return max(vals) if vals else None


def decide(swings, series):
    """همان داورِ System 1، بی‌دست‌خوردن (فقط با فهرستِ پیوت‌هایِ داده‌شده)."""
    return CH._fts_classify_trend(swings, series=series)


def majors_only(swings, series, atr=None, min_pct=None, min_atr=None, ma=None):
    """پیوت‌هایِ ماژورِ کاندید — **دقیقاً با همان `major_swings.grade` که درِ محصول
    اجرا می‌شود** (میانیۀِ ATR، پایِ دوطرفه). پیش از این این فایل ATRِ لحظۀِ آخر را
    به همه پیوت‌ها می‌زد، پس عددی که انتخاب می‌کرد با عددی که اجرا می‌شد یکی نبود.

    `min_pct`/`min_atr` رویِ فهرستِ درجه‌بندی‌شدده بازتطبیق می‌شوند تا حساسیتِ
    آستانه با همان هندسۀِ تولید سنجیده شود.
    """
    kw = {}
    if min_atr is not None:
        kw["atr_x"] = float(min_atr)
    g = MS.grade(swings, series, **kw)
    out = []
    for x in g:
        if x.get("major") is not True:
            continue
        if min_pct is not None and (x.get("leg_pct") or 0) < min_pct:
            continue
        if ma is not None and x["idx"] < len(ma):
            ma_v = ma[x["idx"]]
            if ma_v:
                if x["kind"] == "low" and float(x["price"]) > ma_v * 1.02:
                    continue
                if x["kind"] == "high" and float(x["price"]) < ma_v * 0.98:
                    continue
        out.append(x)
    return out


def ma_series(series, window=100):
    out = []
    s = 0.0
    for i, c in enumerate(series):
        s += float(c["close"])
        if i >= window:
            s -= float(series[i - window]["close"])
        out.append(s / float(min(i + 1, window)) if i + 1 >= window else None)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=80)
    ap.add_argument("--min-rows", type=int, default=160)
    ap.add_argument("--out", default=os.path.join(ROOT, "_audit", "MAJOR-SWING-EVIDENCE.json"))
    a = ap.parse_args()

    con = sqlite3.connect(os.path.join(ROOT, "market.db"))
    all_syms = [r[0] for r in con.execute(
        "select symbol from price_history group by symbol having count(*) >= ? "
        "and max(date) >= '2026-01-01' order by count(*) desc", (a.min_rows,))]
    con.close()
    # نمونه‌برداریِ یکنواخت رویِ کلِ توزیعِ حجمِ داده: «۴۰۰ نمادِ اولِ پُرداده» یعنی
    # فقطِ سهامِ بزرگ و نقدشونده، و پایۀِ تصمیمِ آن‌ها ذاتاً درشت است ⇒ آستانه از
    # رویِ یکِ نمونه‌یِ سوگیرانه بسته می‌شد.
    n_pick = max(a.limit, 1)
    stride = max(1, len(all_syms) // n_pick)
    syms = all_syms[::stride][:n_pick]
    print("qualifying symbols: %d; sampled %d evenly across the row-count distribution"
          % (len(all_syms), len(syms)))

    # آستانه‌هایِ کاندید — همه با **همان** `major_swings.grade` محصول سنجیده می‌شوند؛
    # انتخابِ نهایی با این اعداد است، نه با حدس. `no_grade` کنترلِ مثبت است.
    CAND = {
        "no_grade": dict(control=True),
        "pct_2": dict(min_pct=0.02),
        "pct_3": dict(min_pct=0.03),
        "pct_5": dict(min_pct=0.05),
        "pct_8": dict(min_pct=0.08),
        "atr_1.0": dict(min_atr=1.0),
        "atr_1.5": dict(min_atr=1.5),
        "atr_2.0": dict(min_atr=2.0),
        "atr_2.5": dict(min_atr=2.5),
        "atr_3.0": dict(min_atr=3.0),
        "atr_4.0": dict(min_atr=4.0),
        "pct_5_and_ma100": dict(min_pct=0.05, use_ma=True),
        "atr_2.0_and_ma100": dict(min_atr=2.0, use_ma=True),
    }
    rep = {
        "ranAt": dt.datetime.now().isoformat(timespec="seconds"), "db": "market.db",
        "sha": git_sha(), "grading": "major_swings.grade (product code path)",
        "limit": a.limit, "symbols_examined": 0, "symbols_usable": 0,
        "deciding_leg_pct": [], "deciding_leg_atr_x": [],
        "tiny_decides": 0, "live_nudge_flips": 0, "live_nudge_flips_by": {},
        "cand": {k: {"changed": 0, "toward_w": 0, "away_from_w": 0, "na_more": 0,
                     "gate_changed": 0, "verdict_now": {}, "verdict_new": {}} for k in CAND},
        "per_symbol": [],
    }
    for sym in syms:
        if rep["symbols_examined"] >= a.limit:
            break
        try:
            pl = CH.get_chart_db(sym)
        except Exception as ex:
            continue
        if not pl or pl.get("status") != "success":
            continue
        raw = pl.get("candles") or []
        if len(raw) < a.min_rows:
            continue
        clean = CH._fts_clean_candles(raw)
        try:
            series = CH._fts_scaled(clean, pl.get("factors") or [], pl.get("volumes") or [])
        except Exception:
            continue
        if len(series) < a.min_rows:
            continue
        rep["symbols_examined"] += 1
        atr = atr14(series)
        swings = CH._fts_swings(series, k=3)
        highs = [s for s in swings if s["kind"] == "high"]
        lows = [s for s in swings if s["kind"] == "low"]
        v0 = decide(swings, series)
        w_series = CH._fts_resample(series, "W")
        vw = decide(CH._fts_swings(w_series, k=2), w_series)
        if len(highs) < 2 or len(lows) < 2:
            continue
        rep["symbols_usable"] += 1

        # ۱) پایۀِ تصمیم چقدر کوچک است؟
        idx_h = [swings.index(highs[-1]), swings.index(highs[-2])]
        idx_l = [swings.index(lows[-1]), swings.index(lows[-2])]
        amps = [leg_amp(swings, i) for i in idx_h + idx_l]
        amps = [x for x in amps if x is not None]
        if not amps or not atr:
            rep["symbols_usable"] -= 1
            continue
        worst = min(amps)
        rep["deciding_leg_pct"].append(worst)
        rep["deciding_leg_atr_x"].append(worst * float(series[-1]["close"]) / atr)
        if worst * float(series[-1]["close"]) < 1.0 * atr:
            rep["tiny_decides"] += 1

        # ۲) حساسیتِ رأی به آستانه‌هایِ ماژور
        ma = ma_series(series, 100)
        row = {"symbol": sym, "rows": len(series), "atr_pct": round(100.0 * atr / float(series[-1]["close"]), 3),
               "min_deciding_leg_pct": round(100.0 * worst, 3),
               "deciding_leg_atr_x": round(worst * float(series[-1]["close"]) / atr, 3),
               "verdict_d": v0.get("trend"), "verdict_w": vw.get("trend"), "cand": {}}
        for name, kw in CAND.items():
            if kw.get("control"):
                sub = list(swings)          # بی‌درجه‌بندی: کنترلِ مثبتِ همان مسیر
            else:
                sub = majors_only(swings, series, atr,
                                  min_pct=kw.get("min_pct"), min_atr=kw.get("min_atr"),
                                  ma=ma if kw.get("use_ma") else None)
            v1 = decide(sub, series)
            t1 = v1.get("trend")
            c = rep["cand"][name]
            if t1 != v0.get("trend"):
                c["changed"] += 1
                c["verdict_now"][sym] = v0.get("trend")
                c["verdict_new"][sym] = t1
                if v0.get("trend") != vw.get("trend") and t1 == vw.get("trend"):
                    c["toward_w"] += 1
                elif v0.get("trend") == vw.get("trend") and t1 != vw.get("trend"):
                    c["away_from_w"] += 1
                if t1 == "na" and v0.get("trend") != "na":
                    c["na_more"] += 1
            row["cand"][name] = t1
        rep["per_symbol"].append(row)

        # ۳) نشتیۀِ کندلِ جاری: یکِ تکانِ ±۲٪ درِ آخرینِ بسته، رأی را عوض می‌کند؟
        for delta, tag in ((1.02, "+2%"), (0.98, "-2%")):
            nudged = [dict(c) for c in series[:-1]] + [dict(series[-1])]
            for k in ("close", "high", "low"):
                nudged[-1][k] = float(series[-1][k]) * delta
            if nudged[-1]["high"] < nudged[-1]["low"]:
                nudged[-1]["high"], nudged[-1]["low"] = nudged[-1]["low"], nudged[-1]["high"]
            try:
                vn = decide(CH._fts_swings(nudged, k=3), nudged)
            except Exception:
                continue
            if vn.get("trend") != v0.get("trend"):
                rep["live_nudge_flips"] += 1
                key = "%s: %s→%s" % (tag, v0.get("trend"), vn.get("trend"))
                rep["live_nudge_flips_by"][key] = rep["live_nudge_flips_by"].get(key, 0) + 1
                row.setdefault("nudge_flips", []).append(key)

    def q(vals, p):
        if not vals:
            return None
        s = sorted(vals)
        return s[min(len(s) - 1, int(p * (len(s) - 1)))]

    print("\nusable symbols: %d of %d examined" % (rep["symbols_usable"], rep["symbols_examined"]))
    dl = rep["deciding_leg_pct"]
    da = rep["deciding_leg_atr_x"]
    if dl:
        print("deciding swing leg (بلندیِ پایِ تصمیم‌گیر)، percent of price:")
        print("   median %s   p25 %s   p10 %s   p05 %s   min %s" %
              (round(100 * statistics.median(dl), 2), round(100 * q(dl, .25), 2),
               round(100 * q(dl, .10), 2), round(100 * q(dl, .05), 2), round(100 * min(dl), 2)))
        print("   in ATR units: median %s  p10 %s  min %s" %
              (round(statistics.median(da), 2), round(q(da, .10), 2), round(min(da), 2)))
        print("   symbols whose deciding leg is under 1.0 ATR: %d of %d" %
              (rep["tiny_decides"], rep["symbols_usable"]))
    print("   verdict flips on a ±2%% move of the LAST candle: %d observations" % rep["live_nudge_flips"])
    for k, v in sorted(rep["live_nudge_flips_by"].items(), key=lambda x: -x[1])[:8]:
        print("      %-22s %d" % (k, v))
    print("\nsensitivity of the major-criterion candidates:")
    print("%-22s %7s %9s %9s %8s" % ("candidate", "changed", "toward W", "away W", "na more"))
    for name, c in sorted(rep["cand"].items(), key=lambda kv: -kv[1]["changed"]):
        n = max(rep["symbols_usable"], 1)
        print("%-22s %5d (%4.1f%%) %7d %9d %8d" %
              (name, c["changed"], 100.0 * c["changed"] / n, c["toward_w"],
               c["away_from_w"], c["na_more"]))
    with io.open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    print("\nout: " + a.out)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
