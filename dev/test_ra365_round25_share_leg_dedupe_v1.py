#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 25: one capital increase with contribution must not be applied twice.

Measured on the frozen 50-symbol snapshot: the base gap (price leg, carries
the subscription price) and the official share-count leg land on the same
effective date and differ by 2–6%, so the existing ≤2% dedupe misses them
and both are applied. The frozen reference tracks the base gap in all four
cases (وبانك ×1.40, كبافق ×4.02, شتران ×1.50, شاملا ×2.00 over-applied
before the step). The rule drops the share leg only when it provably equals
a share-count ratio within 0.1%; independent same-day actions and DPS rows
are untouched.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import adjustment_engine as AE  # noqa: E402
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


D = "2013-07-31"
SHARE = [("2013-07-27", 0.71555556)]
base = {"date": D, "ratio": 0.698785, "source": "base-price-discontinuity"}

kept, dropped = C._drop_share_leg_of_observed_gap(
    [dict(base), {"date": D, "ratio": 0.71545408, "source": "priceAdjust"}], SHARE)
ck([e["source"] for e in kept] == ["base-price-discontinuity"],
   "the observed base gap survives", kept)
ck(len(dropped) == 1 and dropped[0]["factor_status"] == "duplicate:share-leg-of-observed-gap",
   "the official share leg is dropped and reported", dropped)

kept, dropped = C._drop_share_leg_of_observed_gap(
    [dict(base), {"date": D, "ratio": 0.705, "source": "priceAdjust"}], SHARE)
ck(len(kept) == 2 and not dropped,
   "a ≤2% divergence stays with the existing merge rule", (kept, dropped))

kept, dropped = C._drop_share_leg_of_observed_gap(
    [dict(base), {"date": D, "ratio": 0.71545408, "source": "shareChange"}], SHARE)
ck(len(kept) == 1, "the shareChange source is deduped too", kept)

kept, dropped = C._drop_share_leg_of_observed_gap(
    [dict(base), {"date": D, "ratio": 0.71545408, "source": "priceAdjust", "_dps": True}], SHARE)
ck(len(kept) == 2, "a DPS row is never treated as the share leg", (kept, dropped))

kept, dropped = C._drop_share_leg_of_observed_gap(
    [dict(base), {"date": D, "ratio": 0.60, "source": "priceAdjust"}], SHARE)
ck(len(kept) == 2, "an independent action >6% away is preserved", (kept, dropped))

kept, dropped = C._drop_share_leg_of_observed_gap(
    [dict(base), {"date": D, "ratio": 0.71545408, "source": "priceAdjust"}],
    [("2013-07-27", 0.80)])
ck(len(kept) == 2, "the 2–6% band alone is not enough: the share identity is required",
   (kept, dropped))

times = ["2013-07-27", "2013-07-31", "2013-08-01"]
before = [dict(base), {"date": D, "ratio": 0.71545408, "source": "priceAdjust"}]
fac_before, _ = AE.chain_factors(times, [dict(e, kind=AE.KIND_SOURCE_RATIO) for e in before])
fac_after, _ = AE.chain_factors(times, [dict(base, kind=AE.KIND_SOURCE_RATIO)])
ck(abs(fac_before[0] / fac_after[0] - 0.71545408) < 1e-9,
   "before the fix the share leg divided every earlier factor again",
   fac_before[0] / fac_after[0])
ck(abs(fac_after[0] - 0.698785) < 1e-9,
   "after the fix the earlier factor is the observed base gap alone", fac_after[0])

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
