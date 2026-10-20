#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DPS / capital-change factor formula (Round 7).

Proven on the reference: for a cash dividend, the factor price-ratio is
`close_ex / (close_ex + dps)` where close_ex is the CLOSING price (پایانی) on
the ex-date and dps the cash dividend per share. For a reserve-based capital
increase the ratio is `previous_capital / new_capital`.

The numbers below are the measured reference steps and the TSETMC CSV closes.
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


# (symbol, ex-date, close(پایانی), dps, reference price-ratio)
DPS_CASES = [
    ("درازي", "2024-03-13", 17190.0, 1020.0, 0.94398682),
    ("درازي", "2025-03-25", 17730.0, 900.0, 0.95169082),
    ("درازي", "2026-05-23", 11190.0, 1400.0, 0.88880064),
    ("سهرمز", "2026-02-22", 16950.0, 10000.0, 0.62894249),
    ("غانيزان", "2026-07-22", 6460.0, 1300.0, 0.83247423),
    ("كربن", "2026-06-21", 5850.0, 3480.0, 0.62700965),
    ("حبندر", "2026-07-08", 6990.0, 2930.0, 0.70463710),
    ("سشمال", "2026-05-20", 11140.0, 4745.0, 0.70129053),
    ("سهرمز", "2024-02-04", 24660.0, 3790.0, 0.86678383),
    ("سهرمز", "2025-02-04", 59510.0, 7650.0, 0.88609291),
    ("كربن", "2025-06-29", 13150.0, 1480.0, 0.89883800),
    ("حشكوه", "2023-07-29", 8250.0, 16.0, 0.99806436),
    ("كنور", "2023-06-18", 22240.0, 1800.0, 0.92512479),
    ("ثنام", "2023-07-19", 2246.0, 10.0, 0.99556738),
]
for sym, d, cl, dps, ref in DPS_CASES:
    got = cl / (cl + dps)
    ck(abs(got / ref - 1) < 1e-6,
       "DPS %s %s: close=%.0f dps=%.0f -> %.8f == ref %.8f" % (sym, d, cl, dps, got, ref),
       "diff=%.2e" % (got / ref - 1))

# Reserve-based capital increase: ratio = previous_capital / new_capital.
CC_CASES = [
    ("ثنام", 2367650648000.0, 3311362648000.0, 0.71500796),
    ("حشكوه", 1726640000000.0, 2000000000000.0, 0.86332000),
    ("ولانا", 100000000000.0, 300000000000.0, 0.33333333),
]
for sym, pv, nw, ref in CC_CASES:
    got = pv / nw
    ck(abs(got / ref - 1) < 1e-6,
       "CC %s: pv/nw = %.8f == ref %.8f" % (sym, got, ref), "diff=%.2e" % (got / ref - 1))

# An official DPS row supersedes a discovered gap at the same action...
rejected = []
merged = C._merge_official_price_adjust(
    [{"date": "2026-02-21", "ratio": 0.907613, "source": "base-price-discontinuity"}],
    [{"date": "2026-02-22", "ratio": 0.62894249, "source": "tsetmc_price_adjust_by_flow",
      "_dps": True, "_ledger_key": ("2026-02-17", "priceAdjust")}],
    rejected=rejected)
ck(len(merged) == 1 and merged[0]["source"] == "tsetmc_price_adjust_by_flow",
   "DPS official row replaces the overlapping base-price gap", merged)

# ...but a non-DPS official row does NOT drop a distant discovered gap.
merged = C._merge_official_price_adjust(
    [{"date": "2026-02-21", "ratio": 0.907613, "source": "base-price-discontinuity"}],
    [{"date": "2026-02-22", "ratio": 0.62894249, "source": "shareChange"}])
ck(len(merged) == 2, "non-DPS official row keeps a distinct discovered event", merged)

# Distinct ledger rows are still kept.
merged = C._merge_official_price_adjust(
    [{"date": "2025-01-10", "ratio": 0.95, "source": "shareChange",
      "_ledger_key": ("2025-01-09", "shareChange")}],
    [{"date": "2025-03-10", "ratio": 0.90, "source": "tsetmc_price_adjust_by_flow",
      "_ledger_key": ("2025-03-09", "priceAdjust")}])
ck(len(merged) == 2, "distinct ledger rows are both kept", merged)

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)