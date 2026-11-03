#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 16: type7 DPS base is the effective candle's closing (پایانی).

Holdout was split by a deterministic symbol hash and was not used to tune the
formula.  The last-price hypothesis is kept in the fixture as REJECTED; the
official source ratio p_closing/pna is the closing-based alternative, not the
exact type7 base for these pre-2024 events.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import api.chart as C  # noqa: E402

FIX = os.path.join(ROOT, "dev", "fixtures", "ra365_round16_pre2024_holdout.json")
P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   ← %s" % (detail,)) if detail else ""))


data = json.load(open(FIX, encoding="utf-8"))
samples = data["samples"]
ck(len(samples) >= 10, "holdout carries at least ten independent samples",
   len(samples))

exact = [s for s in samples if s["err_candle_closing"] <= 0.0005]
near = [s for s in samples if 0.0005 < s["err_candle_closing"] <= 0.01]
far = [s for s in samples if s["err_candle_closing"] > 0.01]
ck(len(exact) >= 4, "holdout has exact candle-closing samples", len(exact))
ck(len(near) >= 2, "holdout has near candle-closing samples", len(near))
ck(len(far) >= 1, "holdout keeps documented formula failures", len(far))

for s in samples:
    got = s["candle_closing"] / (s["candle_closing"] + s["dps"])
    ck(abs(got - s["formula_candle_closing"]) < 1e-10,
       "%s %s: closing/(closing+DPS) is deterministic" % (s["symbol"], s["step_date"]),
       (got, s["formula_candle_closing"]))

for s in exact:
    got = s["candle_closing"] / (s["candle_closing"] + s["dps"])
    ck(abs(got / s["ref_ratio"] - 1) <= 0.0005,
       "%s %s: candle-closing DPS matches type7 (exact)" % (s["symbol"], s["step_date"]),
       (got, s["ref_ratio"]))

for s in near:
    got = s["candle_closing"] / (s["candle_closing"] + s["dps"])
    ck(abs(got / s["ref_ratio"] - 1) <= 0.01,
       "%s %s: candle-closing DPS within 1%%" % (s["symbol"], s["step_date"]),
       (got, s["ref_ratio"]))

# The accepted formula must beat the source ratio on at least one sample.
contrast = [s for s in samples
            if s["err_candle_closing"] <= 0.0005 and s["err_source"] > 0.001]
ck(bool(contrast),
   "holdout proves candle closing beats the official source ratio",
   len(contrast))

# The rejected last-price hypothesis is recorded, not silently deleted.
ck(any(s.get("err_last") is not None and s["err_last"] > s["err_candle_closing"]
       for s in samples),
   "rejected last-price hypothesis is recorded with its larger error", None)

# The classifier uses the supplied candle closing, and never invents a base.
r, is_dps, _et = C._classify_pa_event(
    0.99, 100.0, 900.0, "2020-01-08", [])
ck(abs(r - 0.9) < 1e-12 and is_dps,
   "classifier uses the supplied candle closing", r)
r_none, is_dps_none, _et2 = C._classify_pa_event(
    0.99, 100.0, None, "2020-01-08", [])
ck(r_none == 0.99 and is_dps_none,
   "missing closing does not fabricate a DPS ratio", r_none)

# _canonical_adjustment must forward the closing map to the official builder.
captured = {}
saved = (C._official_price_adjust_events, C._fund_profit_events,
         C._share_change_events, C._share_type_evidence_dates,
         C._ledger_coverage)
try:
    def fake_official(symbol, times=None, share_changes=None, closings=None):
        captured["closings"] = closings
        return []

    C._official_price_adjust_events = fake_official
    C._fund_profit_events = lambda symbol: []
    C._share_change_events = lambda symbol: []
    C._share_type_evidence_dates = lambda symbol: None
    C._ledger_coverage = lambda *a, **k: {}
    C._canonical_adjustment("X", ["2020-01-01"], [],
                            closings={"2020-01-01": 1234.0})
    ck(captured.get("closings") == {"2020-01-01": 1234.0},
       "closing map reaches the official PA builder", captured)
finally:
    (C._official_price_adjust_events, C._fund_profit_events,
     C._share_change_events, C._share_type_evidence_dates,
     C._ledger_coverage) = saved

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
