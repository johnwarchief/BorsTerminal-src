#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 23: the live DPS base is the parsed official close, not the DB close.

The CDN path parses candles with `close` before price_basis fills `closing`;
building the anchor map from `closing` only made it all None, so the DPS
formula silently used the local DB close (Lakhzar 2013: 5245/(5245+250)
matches the live reference, the DB close did not).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

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


m = C._candle_closings([
    {"time": "2013-07-15", "close": 5245.0, "closing": None},
    {"time": "2020-01-02", "close": 100.0, "closing": 105.0},
    {"time": "2020-01-03", "close": None, "closing": None},
    {"time": "", "close": 9.0, "closing": None},
])
ck(m.get("2013-07-15") == 5245.0,
   "a parsed CDN close fills the DPS anchor when closing is not set yet", m)
ck(m.get("2020-01-02") == 105.0,
   "the price-basis closing wins once it exists", m)
ck("2020-01-03" not in m and "" not in m,
   "missing values are not fabricated", m)

r, is_dps, etype = C._classify_pa_event(
    0.91093694, 250.0, m["2013-07-15"], "2013-07-14", [])
ck(abs(r - 5245.0 / (5245.0 + 250.0)) < 1e-9 and is_dps,
   "the DPS formula uses the live close, not the official source ratio", (r, etype))
ck(r not in (0.91093694,), "the stale source ratio is not kept for a valid DPS", r)

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
