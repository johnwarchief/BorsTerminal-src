#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 29: a combined base gap must absorb its share and DPS legs.

شپاکسا 2022: the CSV base gap at the reopening is 0.112426; official share
0.1171189 (dated before the halt) and two official DPS rows (source ratios
0.95858 and 0.95679) map to the reopening. The gap is the observed combined
action; applying a DPS formula on the post-share close (0.742078) is wrong,
and dropping the gap leaves a 6.6x factor error. The merge must keep the gap
once and suppress the component legs that are consistent with gap/share.

The negative controls keep ordinary DPS rows, unrelated base gaps and
materially different same-date rows untouched.
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


SC = [("2022-03-16", 0.1171189)]
BASE = {"date": "2022-05-01", "ratio": 0.112426,
        "source": "base-price-discontinuity"}


def official(orig, mapped, source_ratio):
    return {"date": mapped, "ratio": 0.742078, "source": "tsetmc_price_adjust_by_flow",
            "dividend_per_share": 700.0, "_dps": True,
            "_source_ratio": source_ratio, "_ledger_key": (orig, "priceAdjust")}


out = C._merge_official_price_adjust(
    [dict(BASE)], [official("2022-03-06", "2022-05-02", 0.95858),
                   official("2022-03-13", "2022-05-02", 0.95679)],
    share_changes=SC)
ratios = [(e.get("date"), round(float(e.get("ratio") or 0), 6), bool(e.get("_dps")))
          for e in out]
ck(any(d == "2022-05-01" and abs(r - 0.112426) < 1e-9 for d, r, _ in ratios),
   "the observed combined base gap survives", ratios)
ck(not any(dps for _d, _r, dps in ratios),
   "the consistent DPS legs are suppressed, not applied on the post-share close", ratios)
ck(len(out) == 1, "exactly one economic adjustment for the reopening", out)

# negative control: a DPS with no nearby share keeps the existing behavior
out2 = C._merge_official_price_adjust(
    [], [official("2022-03-13", "2022-05-02", 0.95679)], share_changes=[])
ck(len(out2) == 1 and out2[0].get("_dps") is True,
   "an ordinary DPS with no share change keeps the DPS row", out2)

# negative control: a share far outside the orig..mapped halt does not claim
out3 = C._merge_official_price_adjust(
    [dict(BASE)], [official("2022-03-13", "2022-05-02", 0.95679)],
    share_changes=[("2021-01-01", 0.1171189)])
ck(any(e.get("_dps") for e in out3),
   "a share outside the official→mapped window does not form a combined claim", out3)

# negative control: materially different same-date rows are ambiguous -> kept
out4 = C._merge_official_price_adjust(
    [dict(BASE)], [official("2022-03-13", "2022-05-02", 0.95679),
                   official("2022-03-13", "2022-05-02", 0.90)],
    share_changes=SC)
ck(any(e.get("_dps") for e in out4) or any(abs(float(e.get("ratio") or 0) - 0.90) < 1e-9 for e in out4),
   "materially different same-date legs stay ambiguous/kept", out4)

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
