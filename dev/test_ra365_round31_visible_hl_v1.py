#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 31: visible chart candles must use Rahavard's literal high/low.

The reference type7 preserves the literal type0 extremes even when they sit
inside the candle body (e.g. asset 6, 1996-09-16: type0 high 4020 < open 4022;
type7 high 7.47699 < open 7.48072).  The product's display builder widened
the shadow to contain the body, which changes the visible candle.  The route
must expose high_raw/low_raw as high/low while keeping the raw fields and the
internal widened form available for diagnostics.

These are structural checks: no network, no DB.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import api.chart as C  # noqa: E402

P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   ← %s" % (detail,)) if detail else ""))


src = [{"time": "2020-01-01", "open": 100.0, "high": 110.0, "low": 90.0,
        "high_raw": 105.0, "low_raw": 92.0, "close": 104.0}]
out = C._literal_display_candles(src)
ck(out[0]["high"] == 105.0 and out[0]["low"] == 92.0,
   "display high/low come from the literal raw extremes", out)
ck(out[0]["high_raw"] == 105.0 and out[0]["low_raw"] == 92.0,
   "raw fields are preserved for diagnostics", out)
ck(out[0]["open"] == 100.0 and out[0]["close"] == 104.0,
   "open/close are never changed by the display rule", out)
ck(src[0]["high"] == 110.0, "the input payload is not mutated", src)

# A candle without raw fields keeps its existing values.
src2 = [{"time": "2020-01-02", "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5}]
out2 = C._literal_display_candles(src2)
ck(out2[0]["high"] == 2.0 and out2[0]["low"] == 0.5,
   "a payload without raw fields is passed through unchanged", out2)

# The route wrapper applies the same rule to whatever the live handler returns.
orig = C.get_chart_tsetmc
try:
    C.get_chart_tsetmc = lambda symbol: {"status": "success", "symbol": symbol,
                                          "candles": [dict(src[0])]}
    route = C.get_chart_visible("TEST")
finally:
    C.get_chart_tsetmc = orig
ck(route["candles"][0]["high"] == 105.0 and route["candles"][0]["low"] == 92.0,
   "the /api/chart wrapper exposes literal high/low", route)

# The database route (technical page) must expose the same visible rule.
orig_db = C.get_chart_db
try:
    C.get_chart_db = lambda symbol: {"status": "success", "symbol": symbol,
                                      "candles": [dict(src[0])]}
    route_db = C.get_chart_db_visible("TEST")
finally:
    C.get_chart_db = orig_db
ck(route_db["candles"][0]["high"] == 105.0 and route_db["candles"][0]["low"] == 92.0,
   "the /api/chart-db wrapper exposes literal high/low", route_db)

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
