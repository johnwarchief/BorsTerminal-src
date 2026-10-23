#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 21: a share change hidden inside a long suspension must still adjust.

Regression fixture (فولاد): official share row 2026-03-30 ratio 0.7751938,
last pre-gap candle 2026-02-25 close 3359, first post-gap candle 2026-08-08
close 2332.  The old pipeline dropped the row (gap detector only sees
consecutive candles, `_sharpen_share_gaps` window is 10 days, no PA row).
Live Rahavard type7 factor at 2026-08-08 is 1.3136 = 1/(0.7752*0.9789).
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


TIMES = ["2026-02-25", "2026-08-08", "2026-08-09", "2026-10-21"]
CLOSE = {"2026-02-25": 3359.0, "2026-08-08": 2332.0,
         "2026-08-09": 2316.0, "2026-10-21": 4580.0}
SHARE = [("2026-03-30", 0.7751938)]

# ── helper: the three witnesses ─────────────────────────────────────────────
out = C._apply_long_gap_share_changes([], SHARE, TIMES, CLOSE)
added = [e for e in out if e.get("long_gap")]
ck(len(added) == 1, "long-gap share row becomes one event", out)
ck(added and added[0]["date"] == "2026-08-08",
   "event sits on the first candle after the suspension", added)
ck(added and abs(added[0]["ratio"] - 0.7751938) < 1e-12,
   "event keeps the official share ratio", added)

# Covered: an existing event at that candle already applies the share ratio.
covered = [{"date": "2013-07-28", "ratio": 0.646729, "source": "base-price-discontinuity"}]
same_share = [("2013-07-27", 0.71666667)]
out2 = C._apply_long_gap_share_changes(covered, same_share,
                                       ["2013-07-16", "2013-07-28"], {"2013-07-16": 3359.0,
                                                                     "2013-07-28": 2172.0})
ck(not [e for e in out2 if e.get("long_gap")],
   "an existing deeper step is not double-applied", out2)

# No price witness: the market did not drop across the gap.
no_gap_close = dict(CLOSE, **{"2026-08-08": 3500.0})
out3 = C._apply_long_gap_share_changes([], SHARE, TIMES, no_gap_close)
ck(not [e for e in out3 if e.get("long_gap")],
   "a gap with no price drop is not turned into an event", out3)

# Short gap is left to the existing 10-day sharpener.
out4 = C._apply_long_gap_share_changes([], [("2026-08-08", 0.5)],
                                       ["2026-08-08", "2026-08-09"], CLOSE)
ck(not [e for e in out4 if e.get("long_gap")],
   "a same-day share row is not a long-gap event", out4)

# ── production path: factors must carry the event ───────────────────────────
saved = (C._official_price_adjust_events, C._fund_profit_events,
         C._share_change_events, C._share_type_evidence_dates,
         C._ledger_coverage)
captured = {}
_engine = C._engine_events
try:
    C._official_price_adjust_events = lambda *a, **k: []
    C._fund_profit_events = lambda symbol: []
    C._share_change_events = lambda symbol: list(SHARE)
    C._share_type_evidence_dates = lambda symbol: None

    def fake_cov(symbol, times, wrapped):
        captured["events"] = list(wrapped)
        return {}

    C._ledger_coverage = fake_cov

    def engine_spy(events):
        captured["pre_engine"] = [dict(e) for e in events]
        return _engine(events)

    C._engine_events = engine_spy
    closings = {d: v for d, v in CLOSE.items()}
    applied, rej, factors, chain, cov = C._canonical_adjustment(
        "X", list(TIMES), [], closings=closings, gap_closings=dict(CLOSE))
    fmap = dict(zip(TIMES, factors))
    ck(any(e.get("date") == "2026-08-08" and abs(float(e.get("ratio")) - 0.7751938) < 1e-12
           for e in applied), "canonical chain applies the long-gap share row", applied)
    ck(abs(fmap["2026-02-25"] - 0.7751938) < 1e-9,
       "pre-suspension factor carries the share ratio", fmap)
    ck(abs(fmap["2026-08-08"] - 1.0) < 1e-12,
       "the event does not scale its own candle", fmap)
    ck(captured.get("pre_engine") and any(
        e.get("long_gap") and e.get("source") == "shareChange"
        for e in captured["pre_engine"]),
       "the added event reaches the engine with its source", captured.get("pre_engine"))

    # Backward compatibility: callers without the witness map are unchanged.
    applied2, _r2, factors2, _c2, _v2 = C._canonical_adjustment(
        "X", list(TIMES), [], closings=closings)
    ck(abs(dict(zip(TIMES, factors2))["2026-02-25"] - 1.0) < 1e-12,
       "no witness map means no new event", factors2)
finally:
    (C._official_price_adjust_events, C._fund_profit_events,
     C._share_change_events, C._share_type_evidence_dates,
     C._ledger_coverage) = saved
    C._engine_events = _engine

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
