# -*- coding: utf-8 -*-
"""اندازۀ اثرِ قاعدۀ اکیدِ پیوت رویِ داوری (ابزارِ بازتولیدِ §F-1ِ
`docs/technical-indicators/reviewed/FTS-ALGORITHM-VERIFICATION-1405-07-20.md`).

`api/chart.py` امروز اکید است ⇒ «پس از» = خودِ موتور؛ «پیش از» = همان تابع با
`>=` در هر دو طرف (رفتارِ پیش از این ویرایش). اختلافِ داوری شمرده می‌شود تا
ادعای «فقط لایۀ رسم تمیز می‌شود» رویِ سری‌های تختِ مصنوعی هم سنجیده باشد، نه
فقط ۹ نمادِ واقعی.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from api import chart as CH  # noqa: E402

K = CH._FTS_SWING_K


def permissive(series, k=K):
    """رفتارِ پیش از این ویرایش: `>=` / `<=` در هر دو طرف (مساوی = پیوت)."""
    n = len(series)
    out = []
    for i in range(k, n - k):
        hi, lo = series[i]["high"], series[i]["low"]
        lh = [series[j]["high"] for j in range(i - k, i)]
        rh = [series[j]["high"] for j in range(i + 1, i + k + 1)]
        ll = [series[j]["low"] for j in range(i - k, i)]
        rl = [series[j]["low"] for j in range(i + 1, i + k + 1)]
        t = str(series[i].get("time") or "")[:10]
        ct = str(series[i + k].get("time") or "")[:10]
        if hi >= max(lh) and hi >= max(rh):
            out.append({"idx": i, "price": float(hi), "kind": "high", "time": t,
                        "confirm_idx": i + k, "confirm_time": ct})
        if lo <= min(ll) and lo <= min(rl):
            out.append({"idx": i, "price": float(lo), "kind": "low", "time": t,
                        "confirm_idx": i + k, "confirm_time": ct})
    return out


def series(n, mode, amp=2.0, seed=7):
    out, p, v = [], 1000.0, seed
    for i in range(n):
        v = (v * 1103515245 + 12345) & 0x7FFFFFFF
        step = ((v % 1000) / 500.0 - 1.0) * amp
        if mode == "flat":
            step = 0.0
        p = max(50.0, p + step)
        o, c = p - step * 0.3, p + step * 0.2
        hi, lo = max(o, c) + abs(step) * 0.4, min(o, c) - abs(step) * 0.4
        if mode == "flat":
            hi = lo = o = c = p
        out.append({"time": f"20{i // 250:02d}-{(i % 250) // 21 + 1:02d}-{i % 21 + 1:02d}",
                    "open": o, "high": hi, "low": lo, "close": c, "volume": 1e6 + i})
    return out


CASES = [("saw-40", series(40, "saw")), ("saw-60", series(60, "saw")),
         ("saw-80", series(80, "saw")), ("saw-120", series(120, "saw")),
         ("flat30+120", series(30, "flat") + series(120, "saw", amp=0.05, seed=11)),
         ("flat-120", series(120, "flat"))]

DIGEST = ("trend", "fib", "jet", "choch", "point_hunt", "double_bottom",
          "range_box", "pullback", "hourglass", "exit_engine", "status", "roles")

for name, s in CASES:
    after = CH._fts_analyze_candles("P", s)            # قاعدۀ اکید (امروز)
    old = CH._fts_swings
    CH._fts_swings = permissive
    try:
        before = CH._fts_analyze_candles("P", s)        # قاعدۀ `>=` (دیروز)
    finally:
        CH._fts_swings = old
    sp_b = len(CH._fts_structure_points(permissive(s)))
    sp_a = len(CH._fts_structure_points(CH._fts_swings(s)))
    diff = [k for k in DIGEST
            if json.dumps(before.get(k), sort_keys=True) != json.dumps(after.get(k), sort_keys=True)]
    print(f"{name:12s} bars={len(s):5d} piv {len(permissive(s)):4d} -> {len(CH._fts_swings(s)):4d}"
          f" | structure_points {sp_b:3d} -> {sp_a:3d} | verdict-diff={diff or '—'}"
          f" | keys={sorted(after)[:4]}…")
