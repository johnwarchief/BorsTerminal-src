# -*- coding: utf-8 -*-
"""_audit/engine_change_impact_v1066.py — اثرِ پنج اصلاحِ موتور رویِ بیسِ زنده

پیش از بریدنِ ریلیز می‌پرسد: این تغییرات چند نماد را واقعاً عوض می‌کند؟
هفتۀ شنبه‌محور، کمربندِ قرینۀ موجِ نزولی، MA52ِ صادق، حدِ ضررِ بی‌کندلِ امروز.
بی‌شبکه، رویِ market.db با mode=ro (هیچ نوشتنی، هیچ شبکه‌ای).
"""
import datetime
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import api.chart as CH  # noqa: E402

DB = os.path.join(ROOT, "market.db")
conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

SQL = (
    "select date as d, open as o, close as c, high as h, low as l, volume as v"
    " from price_history where symbol = ? order by date"
)


def series(sym):
    out = []
    for d, o, c, h, l, v in conn.execute(SQL, (sym,)):
        if None in (c, h, l) or not c:
            continue
        ds = str(d)[:10]
        try:
            datetime.date.fromisoformat(ds)
        except ValueError:
            continue
        out.append({"time": ds, "open": float(o or c), "high": float(h), "low": float(l),
                    "close": float(c), "volume": float(v or 0)})
    return out


def resample_iso(candles):
    """تجمیعِ پیش از اصلاح (ISO، دوشنبه‌محور) فقط برایِ مقایسه."""
    out = {}
    for c in candles:
        d = datetime.date.fromisoformat(c["time"])
        iso = d.isocalendar()
        k = f"{iso[0]}-W{int(iso[1]):02d}"
        p = out.get(k)
        if p is None:
            out[k] = dict(c)
        else:
            p["high"] = max(p["high"], c["high"])
            p["low"] = min(p["low"], c["low"])
            p["close"] = c["close"]
    return [out[k] for k in sorted(out.keys())]


SYMS = [r[0] for r in conn.execute(
    "select symbol from price_history group by symbol having count(*) >= 120 order by count(*) desc limit 800"
).fetchall()]

impact = {"checked": 0, "weekly_bar_count_diff": 0, "weekly_trend_flip": 0,
          "into_veto": 0, "out_of_veto": 0, "veto_to_unknown": 0, "flip_other": 0,
          "fib_down_legs": 0, "belt_moved": 0,
          "ma52_unknown": 0, "ma52_number": 0, "hourglass_had_been_fake": 0,
          "stop_changed": 0, "short_history_skipped": 0}
flips = []

for sym in SYMS:
    s = series(sym)
    if len(s) < 120:
        impact["short_history_skipped"] += 1
        continue
    impact["checked"] += 1

    w_new = CH._fts_resample(s, "W")
    w_old = resample_iso(s)
    if len(w_new) != len(w_old):
        impact["weekly_bar_count_diff"] += 1
    t_new = CH._fts_classify_trend(CH._fts_swings(w_new, k=2), series=w_new)["trend"]
    t_old = CH._fts_classify_trend(CH._fts_swings(w_old, k=2), series=w_old)["trend"]
    if t_new != t_old:
        impact["weekly_trend_flip"] += 1
        V = ("down", "range")          # هر دو وتوی کامل می‌دهند (چارت ۳)
        if t_old == "up" and t_new in V:
            impact["into_veto"] += 1
        elif t_old in V and t_new == "up":
            impact["out_of_veto"] += 1
        elif t_old in V and t_new == "na":
            impact["veto_to_unknown"] += 1
        else:
            impact["flip_other"] += 1
        if len(flips) < 14:
            flips.append({"symbol": sym, "weekly_old": t_old, "weekly_new": t_new,
                          "bars_old": len(w_old), "bars_new": len(w_new)})

    sw = CH._fts_swings(s, k=CH._FTS_SWING_K)
    leg = CH._fts_fib_leg(s, sw)
    z = CH._fts_fib_zones(s, sw)
    if leg and z and leg["direction"] == "down":
        impact["fib_down_legs"] += 1
        old_lo = round(CH._fts_fib_price(leg["high"], leg["low"], 0.40), 2)
        if abs(z["zone_33_40"]["lo"] - old_lo) > 0.5:
            impact["belt_moved"] += 1

    hg = CH._fts_analyze_candles(sym, s)["hourglass"]
    weekly_bars = hg.get("weekly_bars") or 0
    if hg["ma52"] is None:
        impact["ma52_unknown"] += 1
    else:
        impact["ma52_number"] += 1
    if weekly_bars < 52 and hg["ma52"] is None:
        # پیش از این همین‌جا میانگینِ کوتاه‌تر با نامِ ma52 منتشر می‌شد
        impact["hourglass_had_been_fake"] += 1

    l1 = CH._fts_exit_layer1(s)
    live = round(min(float(c["low"]) for c in s[-20:]) * 0.95, 2)
    if l1["hard_stop"] is not None and abs(l1["hard_stop"] - live) > 0.01:
        impact["stop_changed"] += 1

print(json.dumps({"impact": impact, "weekly_flips": flips}, ensure_ascii=False, indent=1))
