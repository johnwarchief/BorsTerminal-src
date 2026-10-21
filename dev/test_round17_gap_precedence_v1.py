#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 17: an observed base gap + share change is the price leg.

Round 16 added pre-2024 official DPS rows and sometimes applied the
recomputed DPS on top of an observed base gap that already carried the
pre-share DPS leg.  The four real regressions below pin the general rule:
keep the gap, keep the share, suppress the separately recomputed DPS.
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


def ev(date, ratio, source):
    return {"date": date, "ratio": ratio, "source": source}


def off(date, ratio, source_ratio, dps=100.0):
    return {"date": date, "ratio": ratio, "source": "tsetmc_price_adjust_by_flow",
            "_dps": True, "dividend_per_share": dps,
            "_source_ratio": source_ratio, "_ledger_key": (date, "priceAdjust")}


def prod(events):
    p = 1.0
    for e in events:
        p *= float(e["ratio"])
    return p


# خديزل 2023-06-19: gap 0.97557 is the pre-share DPS leg; share 0.82527083.
merged = C._merge_official_price_adjust(
    [ev("2023-06-19", 0.97557, "base-price-discontinuity"),
     ev("2023-06-19", 0.82527083, "shareChange")],
    [off("2023-06-19", 0.9703557312, 0.9755700325732899, 300.0)],
    share_changes=[("2023-06-19", 0.82527083)])
ck(len(merged) == 2 and abs(prod(merged) - 0.8051094636) < 1e-9,
   "خديزل: gap + share is the price chain; recomputed DPS is suppressed", merged)

# ميدكو 2022-06-12: two gaps (DPS + share), official DPS on top was wrong.
merged = C._merge_official_price_adjust(
    [ev("2022-06-12", 0.985358, "base-price-discontinuity"),
     ev("2022-06-12", 0.44134, "base-price-discontinuity")],
    [off("2022-06-12", 0.967459932, 0.9853583916083916, 670.0)],
    share_changes=[("2022-06-12", 0.42857143)])
ck(len(merged) == 2 and abs(prod(merged) - 0.4348778997) < 1e-9,
   "ميدكو: two observed gaps kept; official DPS suppressed", merged)

# ولبهمن 2023-06-13: gap 0.66093 is the observed action; DPS is not added.
merged = C._merge_official_price_adjust(
    [ev("2023-06-13", 0.66093, "base-price-discontinuity")],
    [off("2023-06-13", 0.9502611291, 0.964349376114082, 200.0)],
    share_changes=[("2023-06-12", 0.61538462)])
ck(len(merged) == 1 and abs(prod(merged) - 0.66093) < 1e-12,
   "ولبهمن: observed gap wins over the separate DPS", merged)

# وخاور 2021-07-27: gap 0.97992 is the DPS leg; share 0.6 is separate.
merged = C._merge_official_price_adjust(
    [ev("2021-07-27", 0.97992, "base-price-discontinuity"),
     ev("2021-07-27", 0.6, "shareChange")],
    [off("2021-07-27", 0.9668325041, 0.9799196787148594, 200.0)],
    share_changes=[("2021-07-27", 0.6)])
ck(len(merged) == 2 and abs(prod(merged) - 0.587952) < 1e-9,
   "وخاور: gap + share kept; recomputed DPS suppressed", merged)

# بورس 2026-07-26: gap≈share (share-only); the separate DPS must survive.
merged = C._merge_official_price_adjust(
    [ev("2026-07-26", 0.750923, "base-price-discontinuity")],
    [off("2026-07-26", 0.987542, 0.9899543379, 55.0)],
    share_changes=[("2026-07-26", 0.75)])
ck(len(merged) == 2,
   "بورس: share-only gap keeps the separate DPS", merged)

# No share change: Round 15 DPS replacement is unchanged.
merged = C._merge_official_price_adjust(
    [ev("2026-05-23", 0.82668187, "priceAdjust")],
    [off("2026-05-23", 0.8572769953, 0.82668187, 1520.0)],
    share_changes=[])
ck(len(merged) == 1 and abs(merged[0]["ratio"] - 0.8572769953) < 1e-12,
   "no-share DPS replacement is unchanged", merged)

# The suppression is reported, never silent.
rejected = []
C._merge_official_price_adjust(
    [ev("2023-06-13", 0.66093, "base-price-discontinuity")],
    [off("2023-06-13", 0.9502611291, 0.964349376114082, 200.0)],
    rejected=rejected, share_changes=[("2023-06-12", 0.61538462)])
ck(len(rejected) == 1 and
   rejected[0]["factor_status"] == "included-in-observed-base-gap",
   "suppressed official row is reported", rejected)


# ديران 2024-04-24: no share is actually applied; the official DPS is the
# correct event and must replace the observed gap (negative control).
merged = C._merge_official_price_adjust(
    [ev("2024-04-24", 0.936937, "base-price-discontinuity")],
    [off("2024-04-24", 0.9133765468, 0.93709884, 735.0)],
    share_changes=[("2024-04-21", 0.66165414)])
ck(len(merged) == 1 and abs(merged[0]["ratio"] - 0.9133765468) < 1e-10,
   "ديران: source-ratio gap keeps the official DPS", merged)

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
