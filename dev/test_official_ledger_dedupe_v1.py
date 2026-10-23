#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One ledger row must not be applied twice through two event shapes.

The discovered CSV event can be sharpened by the same `price_adjust_events` row
that `_official_price_adjust_events` later injects. When the effective candle
date is far from the raw event date (suspension), the old date-based merge did
not see them as one event and the factor was multiplied by the ratio twice.
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
        print("  FAIL %s%s" % (msg, ("   ← %s" % detail) if detail else ""))


def ev(date, ratio, source, key=None):
    d = {"date": date, "ratio": ratio, "source": source}
    if key:
        d["_ledger_key"] = key
    return d


# داسوه: discovered 2026-04-21 + official mapped to 2026-05-24, same ledger row.
rejected = []
merged = C._merge_official_price_adjust(
    [ev("2026-04-21", 0.92797119, "priceAdjust", ("2026-04-20", "priceAdjust"))],
    [ev("2026-05-24", 0.92797119, "tsetmc_price_adjust_by_flow",
        ("2026-04-20", "priceAdjust"))], rejected=rejected)
ck(len(merged) == 1 and merged[0]["date"] == "2026-04-21",
   "داسوه: same ledger row is applied once", merged)
ck(len(rejected) == 1 and rejected[0]["factor_status"] == "duplicate-ledger-row",
   "داسوه: duplicate is reported, not silently dropped", rejected)

# فولاژ: 6-day gap, old 5-day window missed it.
rejected = []
merged = C._merge_official_price_adjust(
    [ev("2025-08-12", 0.91368036, "priceAdjust", ("2025-08-05", "priceAdjust"))],
    [ev("2025-08-06", 0.91368036, "tsetmc_price_adjust_by_flow",
        ("2025-08-05", "priceAdjust"))], rejected=rejected)
ck(len(merged) == 1 and len(rejected) == 1,
   "فولاژ: same ledger row across a 6-day gap is applied once", (merged, rejected))

# غويتا: same pattern.
rejected = []
merged = C._merge_official_price_adjust(
    [ev("2026-04-26", 0.96258993, "priceAdjust", ("2026-04-25", "priceAdjust"))],
    [ev("2026-05-24", 0.96258993, "tsetmc_price_adjust_by_flow",
        ("2026-04-25", "priceAdjust"))], rejected=rejected)
ck(len(merged) == 1 and len(rejected) == 1,
   "غويتا: same ledger row is applied once", (merged, rejected))

# A genuinely distinct official row must survive.
rejected = []
merged = C._merge_official_price_adjust(
    [ev("2025-01-10", 0.95, "shareChange", ("2025-01-09", "shareChange"))],
    [ev("2025-03-10", 0.90, "tsetmc_price_adjust_by_flow",
        ("2025-03-09", "priceAdjust"))], rejected=rejected)
ck(len(merged) == 2 and not rejected,
   "distinct ledger rows are both kept", (merged, rejected))

# Existing 5-day/0.1% dedupe still applies when the key is absent.
rejected = []
merged = C._merge_official_price_adjust(
    [ev("2025-01-10", 0.95, "base-price-discontinuity")],
    [ev("2025-01-12", 0.95, "priceAdjust")], rejected=rejected)
ck(len(merged) == 1 and not rejected,
   "near-date + equal-ratio dedupe remains intact", merged)

# Private ledger metadata must not leak into the engine/payload.
saved = (C._fund_profit_events, C._official_price_adjust_events, C._ledger_coverage)
try:
    C._fund_profit_events = lambda symbol: []
    C._official_price_adjust_events = lambda symbol, times=None, share_changes=None, closings=None: []
    C._ledger_coverage = lambda *a, **k: {}
    applied, rejected, factors, chain, cov = C._canonical_adjustment(
        "X", ["2025-01-01"], [ev("2025-01-02", 0.95, "shareChange",
                                 ("2025-01-01", "shareChange"))])
    ck(applied and "_ledger_key" not in applied[0],
       "private ledger key is stripped before the engine/payload", applied)
finally:
    C._fund_profit_events, C._official_price_adjust_events, C._ledger_coverage = saved

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
