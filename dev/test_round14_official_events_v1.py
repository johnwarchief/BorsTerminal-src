#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 14: official-event fixture contract (capital vs share ratio, P)."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import api.chart as C  # noqa: E402

FIX = os.path.join(ROOT, "dev", "fixtures", "ra365_round14_official_events.json")
P = F = 0
TOL = 5e-9


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   ← %s" % (detail,)) if detail else ""))


def need(ev, key):
    """A missing official field must never be replaced by a guess."""
    if key not in ev or ev[key] in (None, ""):
        raise ValueError("missing official field: %s" % key)
    return ev[key]


def main():
    data = json.load(open(FIX, encoding="utf-8"))
    events = {e["symbol"]: e for e in data["events"]}
    ck(len(events) == 3, "fixture carries the three audited events", sorted(events))

    # آکو: official closing + gross DPS reproduce type7 exactly.
    a = events["آكو"]
    dps_ratio = a["effective_close"] / (a["effective_close"] + a["dps"])
    ck(abs(dps_ratio - a["live_type7"]) < TOL,
       "آکو: close/(close+DPS) equals live type7", (dps_ratio, a["live_type7"]))
    ck(abs(a["production"] - a["live_type7"]) < 5e-7,
       "آکو: production matches live type7 (no regression)", (a["production"], a["live_type7"]))

    # حخزر: two independent ratios are equal here; type3 = capital × gross PA.
    h = events["حخزر"]
    ck(need(h, "capital_ratio") == need(h, "share_ratio") == 0.84,
       "حخزر: capital ratio equals share ratio (0.84)")
    type3 = h["capital_ratio"] * h["pa_ratio"]
    ck(abs(type3 - h["live_type3"]) <= 1e-4,
       "حخزر: type3 is within 1e-4 of capital × official PA ratio",
       (type3, h["live_type3"]))
    type3_dps_leg = h["live_type3"] / h["capital_ratio"]
    ck(abs(type3_dps_leg - h["pa_ratio"]) > 5e-5,
       "حخزر: type3 DPS leg differs from official PA ratio (documented, not fitted)",
       (type3_dps_leg, h["pa_ratio"]))
    dps_leg = h["live_type7"] / h["capital_ratio"]
    ck(abs(dps_leg - 0.985871397) < 1e-8,
       "حخزر: type7 DPS leg isolated from the capital leg", dps_leg)
    hyp = h["net_dps_hypothesis"]
    net_ratio = hyp["close_numerator"] / (hyp["close_numerator"] + hyp["net_dps"])
    ck(abs(net_ratio - dps_leg) <= 1e-5,
       "حخزر: net-DPS (3.75%) hypothesis fits type7 within 1e-5",
       (net_ratio, dps_leg))
    ck(hyp["status"] == "UNVERIFIED",
       "حخزر: net-DPS remains a labelled hypothesis, not a fact")

    # فروي: capital and share ratios are both 0.5; P is not official.
    f = events["فروي"]
    ck(need(f, "capital_ratio") == need(f, "share_ratio") == 0.5,
       "فروي: capital ratio equals share ratio (0.5)")
    ck(need(f, "paid_ratio_c") == 1.0,
       "فروي: the whole increase is paid-in/claims (c=1)")
    type2 = f["share_ratio"] + (1 - f["share_ratio"]) * (f["nominal_value"] / f["last_price_before"])
    ck(abs(type2 - f["live_type2"]) < 1e-9,
       "فروي: type2 = s + (1-s)×(S/P) with last price", (type2, f["live_type2"]))
    implied_p = f["nominal_value"] / ((f["live_type7"] - f["share_ratio"]) / (1 - f["share_ratio"]))
    ck(abs(implied_p - f["implied_p_type7"]) < 1e-6,
       "فروي: type7 implies P=2620 exactly", implied_p)
    try:
        need(f, "official_p")
        has_official_p = True
    except ValueError:
        has_official_p = False
    ck(not has_official_p,
       "فروي: no official P in the fixture → BLOCKED_P_DEFINITION stays")

    # Explicit ratios: a missing capital ratio is not silently replaced.
    try:
        broken = {"symbol": "X", "share_ratio": 0.5}
        need(broken, "capital_ratio")
        raised = False
    except ValueError:
        raised = True
    ck(raised, "missing capital_ratio raises, never falls back to share_ratio")

    # Event order: capital and DPS legs commute; chain product is stable.
    ab = h["capital_ratio"] * h["pa_ratio"]
    ba = h["pa_ratio"] * h["capital_ratio"]
    ck(abs(ab - ba) < 1e-15 and abs(ab - h["live_type3"]) <= 1e-4,
       "حخزر: capital+DPS chain is order-stable (1e-4 envelope)")

    # Round 12 regression: inverse/reverse share noise filter stays intact.
    out = C._filter_share_changes([("2026-04-12", 0.41666667),
                                   ("2026-07-08", 2.4),
                                   ("2026-07-12", 0.41666667)])
    ck([d for d, _r in out] == ["2026-04-12"],
       "Round 12 share filter keeps the real row and drops the reverse pair", out)

    print()
    print("result: %d pass, %d fail" % (P, F))
    print("%d/%d" % (P, P + F))
    return 0 if F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
