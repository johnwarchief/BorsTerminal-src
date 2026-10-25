#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 32A: the factor inference, on synthetic series with known answers.

Each case has one right answer, so a regression in the estimator shows up as a
wrong factor, a wrong segment count or a wrong cause rather than as a number
nobody can interpret.
"""
import _harness as H

import infer_factor_segments as INF
import r32_schema as S

OPTS = dict(INF.DEFAULTS)
OPTS["fields"] = ("o", "h", "l", "c")


def pair(date, raw_prices, factor, close_factor=None, raw_close=None):
    """One paired session: reference = raw x factor, per field."""
    o, h, l, c = raw_prices
    cf = factor if close_factor is None else close_factor
    return {
        "symbol_id": "S", "symbol": "S", "timeframe": "D", "timeframe_source": "derived",
        "date": date, "basis": "closing",
        "prod": {"o": o, "h": h, "l": l, "c": c, "v": 10.0},
        "prod_raw": {"c": raw_close if raw_close is not None else c},
        "ref": {"o": o * factor, "h": h * factor, "l": l * factor, "c": c * cf, "v": 10.0},
        "event": None, "source_ref": "test-ref", "source_prod": "test-prod",
    }


def run(pairs):
    return INF.infer_group(pairs, OPTS)


# --- one clean scalar ----------------------------------------------------
pairs = [pair("2024-01-%02d" % (d + 1), (100.0 + d, 110.0 + d, 90.0 + d, 105.0 + d), 0.5)
         for d in range(10)]
segs, stats = run(pairs)
H.ck(len(segs) == 1, "clean series: exactly one segment", len(segs))
H.ck(abs(segs[0]["factor"] - 0.5) < 1e-12, "clean series: the factor is recovered", segs[0]["factor"])
H.ck(segs[0]["n_sessions"] == 10 and segs[0]["evidence"]["n_support_sessions"] == 10,
     "clean series: every session is evidence")
H.ck(segs[0]["cause"] in ("exact_single_scalar", "single_scalar_with_rounding"),
     "clean series: the cause is a single scalar", segs[0]["cause"])
H.ck(segs[0]["confidence"] >= 0.7, "clean series: confidence is high", segs[0]["confidence"])
H.ck(segs[0]["breakpoint"] is None, "clean series: the first segment has no breakpoint")
H.ck(S.validate(segs[0], S.SCHEMA_SEGMENT) == [], "clean series: the record satisfies the contract")
H.ck(segs[0]["event_attribution"] == "unattributed",
     "clean series: a ratio break alone never claims an event")

# --- a factor regime change ---------------------------------------------
pairs = ([pair("2024-01-%02d" % (d + 1), (100.0 + d, 110.0 + d, 90.0 + d, 105.0 + d), 0.5)
          for d in range(6)] +
         [pair("2024-01-%02d" % (d + 7), (100.0 + d, 110.0 + d, 90.0 + d, 105.0 + d), 0.25)
          for d in range(6)])
segs, stats = run(pairs)
H.ck(len(segs) == 2, "regime change: two segments", len(segs))
H.ck(abs(segs[0]["factor"] - 0.5) < 1e-12 and abs(segs[1]["factor"] - 0.25) < 1e-12,
     "regime change: both factors are recovered")
H.ck(segs[1]["breakpoint"] is not None and abs(segs[1]["breakpoint"]["delta_rel"] - (-0.5)) < 1e-9,
     "regime change: the breakpoint reports -50%", segs[1]["breakpoint"])
H.ck(segs[1]["breakpoint"]["date"] == "2024-01-07",
     "regime change: the breakpoint sits on the first session of the new regime")

# --- a dissenting field --------------------------------------------------
pairs = [pair("2024-01-%02d" % (d + 1), (100.0 + d, 110.0 + d, 90.0 + d, 105.0 + d), 0.5,
              close_factor=1.0) for d in range(8)]
segs, stats = run(pairs)
H.ck(len(segs) == 1, "dissenting close: still one segment", len(segs))
H.ck(abs(segs[0]["factor"] - 0.5) < 1e-12, "dissenting close: the body fields set the factor")
H.ck(segs[0]["cause"] == "single_scalar_with_dissent",
     "dissenting close: the cause names the dissent", segs[0]["cause"])
H.ck("c" in segs[0]["dissent_fields"], "dissenting close: close is the dissenter",
     segs[0]["dissent_fields"])
H.ck("o" in segs[0]["consensus_fields"] and "l" in segs[0]["consensus_fields"],
     "dissenting close: open/high/low are the consensus")

# --- rounding at a low price must not fragment ---------------------------
pairs = []
for d in range(20):
    raw = 1000.0 + d
    pairs.append({
        "symbol_id": "S", "symbol": "S", "timeframe": "D", "timeframe_source": "derived",
        "date": "2024-02-%02d" % (d + 1), "basis": "closing",
        "prod": {"o": raw, "h": raw, "l": raw, "c": raw, "v": 1.0},
        "prod_raw": {"c": raw},
        "ref": {"o": raw + 1.0, "h": raw + 1.0, "l": raw - 1.0, "c": raw, "v": 1.0},
        "event": None, "source_ref": "r", "source_prod": "p",
    })
segs, stats = run(pairs)
H.ck(len(segs) == 1, "rounding: one unit of tick at ~1000 does not split the regime", len(segs))
H.ck(abs(segs[0]["factor"] - 1.0) < 2e-3, "rounding: the factor stays at 1", segs[0]["factor"])

# --- fields that cannot agree -------------------------------------------
pairs = []
for d in range(6):
    raw = 100.0 + d
    pairs.append({
        "symbol_id": "S", "symbol": "S", "timeframe": "D", "timeframe_source": "derived",
        "date": "2024-03-%02d" % (d + 1), "basis": "closing",
        "prod": {"o": raw, "h": raw, "l": raw, "c": raw, "v": 1.0},
        "prod_raw": {"c": raw},
        "ref": {"o": raw * 0.5, "h": raw * 2.0, "l": raw * 3.0, "c": raw * 0.1, "v": 1.0},
        "event": None, "source_ref": "r", "source_prod": "p",
    })
segs, stats = run(pairs)
H.ck(len(segs) == 1 and segs[0]["factor"] is None, "no scalar: no factor is claimed",
     [s["factor"] for s in segs])
H.ck(segs[0]["cause"] == "no_single_scalar",
     "no scalar: the record is routed to the data/model ledger", segs[0]["cause"])
H.ck("factor" in segs[0]["unavailable"], "no scalar: the absent factor is declared unavailable")
H.ck(S.validate(segs[0], S.SCHEMA_SEGMENT) == [], "no scalar: the record still validates")

# --- a session without enough fields is skipped, not averaged ------------
pairs = [pair("2024-04-%02d" % (d + 1), (100.0 + d, 110.0 + d, 90.0 + d, 105.0 + d), 0.5)
         for d in range(5)]
pairs.append({"symbol_id": "S", "symbol": "S", "timeframe": "D", "date": "2024-04-06",
              "basis": "closing", "prod": {"o": 1.0, "h": None, "l": None, "c": None, "v": None},
              "prod_raw": {}, "ref": {"o": 0.5, "h": None, "l": None, "c": None, "v": None},
              "event": None, "source_ref": "r", "source_prod": "p"})
segs, stats = run(pairs)
H.ck(stats["skipped"] == 1, "sparse session: it is counted as skipped", stats)
H.ck(sum(s["n_sessions"] for s in segs) == 5, "sparse session: it is not folded into a segment")

# --- one instrument per group -------------------------------------------
pairs = [pair("2024-01-%02d" % (d + 1), (100.0 + d, 110.0 + d, 90.0 + d, 105.0 + d), 0.5)
         for d in range(5)]
pairs += [dict(p, symbol_id="T", symbol="T") for p in pairs]
segs, per_group = INF.infer_all(pairs, OPTS)
H.ck(len(per_group) == 2, "grouping: one entry per instrument", list(per_group))
H.ck(len(segs) == 2, "grouping: each instrument gets its own segment")

H.report()