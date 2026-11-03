#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 25: a DPS row that is the price leg of a combined share action.

Measured on the frozen 50-symbol snapshot: when a DPS row's official ratio is
close to a nearby share-count ratio, the candle-close DPS formula ignores the
share effect (سغرب 2019-01-29: 5.52% step error → 1.62%; ومعادن 2012-02-21:
4.95% → 0.32%; کمرجان 2018-05-09: 2.57% → 0.41%). The official ratio is the
combined price leg and is kept. Below a 1.5% difference the correction is
base-gap noise and rescaling the whole prior history can flip borderline rows
(شنفت 2016-10-29: 0.45% change, −4.9pp), so it is materiality-gated.
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


D = "2019-01-29"
SHARE = [("2019-01-29", 0.6)]          # سغرب: shares 300M → 500M
FORMULA = 0.7079081633                  # close 3885 / (3885 + 1603)
OFFICIAL = 0.67984821                   # p_closing / p_notAdjusted
REF = 0.668867

r = C._combined_dps_official_ratio(FORMULA, OFFICIAL, D, SHARE)
ck(r == OFFICIAL, "a combined DPS keeps the official ratio", r)

ck(C._combined_dps_official_ratio(FORMULA, FORMULA * 1.004, D, SHARE) is None,
   "a <1.5% difference stays with the candle-close formula (materiality gate)")

ck(C._combined_dps_official_ratio(FORMULA, OFFICIAL, D, [("2019-01-29", 0.9)]) is None,
   "an official ratio outside the ±15% share band is not treated as combined")

ck(C._combined_dps_official_ratio(FORMULA, OFFICIAL, D, []) is None,
   "a pure DPS with no nearby share change keeps the formula")

ck(C._combined_dps_official_ratio(FORMULA, OFFICIAL, "2025-01-01", SHARE) is None,
   "a share change 6 years away does not count")

times = ["2019-01-28", D, "2019-01-30"]
fac_formula, _ = AE.chain_factors(times, [{"date": D, "kind": AE.KIND_SOURCE_RATIO,
                                          "ratio": FORMULA}])
fac_official, _ = AE.chain_factors(times, [{"date": D, "kind": AE.KIND_SOURCE_RATIO,
                                           "ratio": OFFICIAL}])
ck(abs(fac_formula[0] / REF - 1) > abs(fac_official[0] / REF - 1),
   "the official combined leg is closer to the reference step than the formula",
   (fac_formula[0], fac_official[0], REF))

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
