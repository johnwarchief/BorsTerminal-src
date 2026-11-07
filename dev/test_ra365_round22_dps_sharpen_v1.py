#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 22: a DPS row must keep the candle-closing formula, not the sharpened PA ratio.

Lakhzar 2013-07-15: official PA 2557/2807 (0.91093694), candle closing 5245,
DPS 250 => 5245/(5245+250)=0.95450144, which is exactly the live Rahavard
type7 step.  The CSV sharpener had already claimed the ledger key with the
official PA ratio, so the recomputed DPS was rejected as a duplicate.
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


KEY = ("2013-07-14", "priceAdjust")
dps_ratio = 5245.0 / (5245.0 + 250.0)

# The sharpened base-gap event owns the ledger key with the source ratio.
ev = [{"date": "2013-07-15", "ratio": 0.91093694, "source": "priceAdjust",
       "_ledger_key": KEY}]
official = [{"date": "2013-07-15", "ratio": round(dps_ratio, 10),
             "source": "tsetmc_price_adjust_by_flow", "_dps": True,
             "dividend_per_share": 250.0, "_source_ratio": 0.91093694,
             "_ledger_key": KEY}]
rej = []
out = C._merge_official_price_adjust(ev, official, rej, [])
ck(len(out) == 1, "the official DPS does not create a second event", out)
ck(out and abs(out[0]["ratio"] - dps_ratio) < 1e-9,
   "the DPS formula replaces the sharpened source ratio", out)
ck(out and out[0].get("_dps") is True and out[0].get("dividend_per_share") == 250.0,
   "the replaced event is typed as DPS", out)
ck(out and out[0].get("_source_ratio") == 0.91093694,
   "the official source ratio is kept for provenance", out)
ck(any(r.get("factor_status") == "duplicate-ledger-row" for r in rej),
   "the duplicate is still reported", rej)

# A capital/combined official row must not overwrite the sharpened ratio.
ev2 = [{"date": "2013-07-15", "ratio": 0.9, "source": "priceAdjust",
        "_ledger_key": KEY}]
off2 = [{"date": "2013-07-15", "ratio": 0.9, "source": "tsetmc_price_adjust_by_flow",
         "_event_type": "capital", "_source_ratio": 0.9, "_ledger_key": KEY}]
out2 = C._merge_official_price_adjust(ev2, off2, [], [])
ck(len(out2) == 1 and abs(out2[0]["ratio"] - 0.9) < 1e-12,
   "a capital duplicate leaves the existing ratio unchanged", out2)

# Same-ratio DPS: no change, only the duplicate report.
ev3 = [{"date": "2013-07-15", "ratio": round(dps_ratio, 10),
        "source": "priceAdjust", "_ledger_key": KEY}]
out3 = C._merge_official_price_adjust(ev3, official, [], [])
ck(len(out3) == 1 and abs(out3[0]["ratio"] - dps_ratio) < 1e-9,
   "an identical DPS ratio is idempotent", out3)


# The DPS formula is authoritative even for small discrepancies (the live
# reference follows it); the sharpened source ratio is replaced.
for old, dps in ((0.9020979, 0.8966789668), (0.85776373, 0.8575385833)):
    evx = [{"date": "2025-08-06", "ratio": old, "source": "priceAdjust",
            "_ledger_key": ("2025-08-05", "priceAdjust")}]
    offx = [{"date": "2025-08-06", "ratio": dps,
             "source": "tsetmc_price_adjust_by_flow", "_dps": True,
             "dividend_per_share": 280.0, "_source_ratio": old,
             "_ledger_key": ("2025-08-05", "priceAdjust")}]
    outx = C._merge_official_price_adjust(evx, offx, [], [])
    ck(len(outx) == 1 and abs(outx[0]["ratio"] - dps) < 1e-9
       and outx[0].get("_dps") is True,
       "a small DPS difference still replaces the sharpened ratio", outx)

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
