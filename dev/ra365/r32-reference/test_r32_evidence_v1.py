#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 32A: the frozen R26-R31 ledgers become contract records."""
import _harness as H

import r32_evidence as EV
import r32_schema as S

CANDLE_HEADER = ["date", "our_c", "our_h", "our_l", "our_last", "our_o", "our_src", "our_v",
                 "ref_c", "ref_c_equals_our_last", "ref_h", "ref_l", "ref_o", "ref_v", "symbol"]
STEPS_HEADER = ["asset_id", "symbol", "date", "class", "prod_ratio", "ref_ratio", "err",
                "err_bucket", "event_sig", "event_sources", "event_ratios", "event_dps",
                "affected_rows", "attributed_rows", "recovered_rows"]

# --- the arm vocabulary --------------------------------------------------
arms = {
    "R1-\u0632\u0646\u062f\u0647-\u0622\u062e\u0631\u06cc\u0646-\u0639\u0645\u0644\u06a9\u0631\u062f\u06cc":
        ("live", "last", "adjusted"),
    "R2-\u0632\u0646\u062f\u0647-\u067e\u0627\u06cc\u0627\u0646\u06cc-\u062e\u0627\u0645":
        ("live", "closing", "raw"),
    "R3-\u062f\u06cc\u062a\u0627\u0628\u06cc\u0633-\u067e\u0627\u06cc\u0627\u0646\u06cc-\u062e\u0627\u0645":
        ("db", "closing", "raw"),
    "R4-\u062f\u06cc\u062a\u0627\u0628\u06cc\u0633-\u067e\u0627\u06cc\u0627\u0646\u06cc-\u0639\u0645\u0644\u06a9\u0631\u062f\u06cc":
        ("db", "closing", "adjusted"),
}
for label, want in arms.items():
    ctx = EV.arm_context(label)
    got = (ctx["transport"], ctx["basis"], ctx["adjust"])
    H.ck(got == want, "arm_context: %r -> %r" % (label[:2], want), got)

# --- timeframe derivation ------------------------------------------------
H.ck(EV.derive_timeframe(["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"])[0] == "D",
     "derive_timeframe: one-day spacing is daily")
H.ck(EV.derive_timeframe(["2024-01-06", "2024-01-13", "2024-01-20"])[0] == "W",
     "derive_timeframe: seven-day spacing is weekly")
H.ck(EV.derive_timeframe(["2024-01-01", "2024-02-01", "2024-03-01"])[0] == "M",
     "derive_timeframe: month spacing is monthly")
H.ck(EV.derive_timeframe(["2024-01-01", "2024-01-02"])[1] == "assumed",
     "derive_timeframe: too few points is flagged as assumed, not derived")

# --- the raw/adjusted pair -----------------------------------------------
csv1 = H.tmp_csv("r32_candle.csv", CANDLE_HEADER, [
    ["2024-01-05", 5780, 5810, 5650, "", 5680, "", 100, 2845.7, "no",
     2855.5, 2776.8, 2791.6, 100, "\u0641\u0648\u0644\u0627\u062f"],
    ["2024-01-06", 5850, 5920, 5780, "", 5870, "", 120, 2899.7, "yes",
     2909.5, 2840.7, 2885.0, 120, "\u0641\u0648\u0644\u0627\u062f"],
])
sources, bars = EV.bars_from_candle_diverge(csv1)
H.ck(len(bars) == 4, "candle ledger: two sessions produce a raw and an adjusted bar each")
H.ck({b["adjust"] for b in bars} == {"raw", "adjusted"},
     "candle ledger: both adjust modes are present")
H.ck(all(b["timeframe"] == "D" for b in bars), "candle ledger: the timeframe is derived as daily")
H.ck(all(S.validate(b, S.SCHEMA_BAR) == [] for b in bars),
     "candle ledger: every bar satisfies the contract")
raw = [b for b in bars if b["adjust"] == "raw"][0]
adj = [b for b in bars if b["adjust"] == "adjusted"][0]
H.ck(raw["close"] == 5780.0 and abs(adj["close"] - 2845.7) < 1e-9,
     "candle ledger: raw close comes from our_c, adjusted close from ref_c")

pairs = EV.pairs_from_candle_diverge(csv1)
H.ck(len(pairs) == 2, "candle ledger: two paired sessions")
H.ck(pairs[0]["prod"]["c"] == 5780.0 and abs(pairs[0]["ref"]["c"] - 2845.7) < 1e-9,
     "candle ledger: the pair holds product raw beside reference adjusted")
H.ck(pairs[0]["symbol_id"] == "\u0641\u0648\u0644\u0627\u062f",
     "candle ledger: the symbol name is the id when the ledger carries no numeric id")
H.ck(pairs[0]["source_ref"].startswith("rahavard-adjusted@"),
     "candle ledger: the reference side names its source")

# --- the frozen step evidence -------------------------------------------
csv2 = H.tmp_csv("r32_steps.csv", STEPS_HEADER, [
    ["107", "\u06a9\u067e\u0627\u0631\u0633", "2020-09-26", "RATIO_DIFF", 0.987576182007,
     0.987576183779, 1.8e-09, "<0.01%", "dps", "tsetmc_price_adjust_by_flow", "0.9875761838",
     "1060.0", 138, 12, 0],
    ["107", "\u06a9\u067e\u0627\u0631\u0633", "2021-07-31", "RATIO_DIFF", 0.957795223401,
     0.957795222419, -1e-09, "<0.01%", "dps", "tsetmc_price_adjust_by_flow", "0.9577952224",
     "5000.0", 331, 78, 0],
])
segs = EV.segments_from_steps(csv2)
H.ck(len(segs) == 2, "steps ledger: one boundary record per step")
H.ck(all(s["evidence"]["evidence_kind"] == "step-boundary" for s in segs),
     "steps ledger: the evidence kind says step-boundary")
H.ck(all(s["evidence"]["n_sessions"] is None for s in segs),
     "steps ledger: sessions inside the interval are null, never a fabricated zero")
H.ck(all("sessions_in_segment" in s["unavailable"] for s in segs),
     "steps ledger: the unknown interval length is declared unavailable")
H.ck(all(S.validate(s, S.SCHEMA_SEGMENT) == [] for s in segs),
     "steps ledger: every segment satisfies the contract")
H.ck(segs[0]["event_attribution"] == "inferential",
     "steps ledger: an event source present makes the attribution inferential, not independent")
H.ck(abs(segs[0]["factor"] - 0.987576182007 / 0.987576183779) < 1e-12,
     "steps ledger: the factor is the product ratio over the reference ratio")

# --- the four arms become pairs with their own basis ---------------------
PARITY_HEADER = ["arm", "date", "prod_c", "prod_closing_raw", "prod_h", "prod_l",
                 "prod_last_raw", "prod_o", "ref_c", "ref_h", "ref_l", "ref_o", "rel_err",
                 "symbol"]
csv3 = H.tmp_csv("r32_parity.csv", PARITY_HEADER, [
    ["R4-\u062f\u06cc\u062a\u0627\u0628\u06cc\u0633-\u067e\u0627\u06cc\u0627\u0646\u06cc-\u0639\u0645\u0644\u06a9\u0631\u062f\u06cc",
     "2024-01-06", 11730, 11730, 11880, 11730, "", 11880, 11880, 11880, 11850, 11880,
     0.01263, "\u0634\u0628\u0647\u0631\u0646"],
])
pp = EV.pairs_from_parity_diverge(csv3)
H.ck(len(pp) == 1, "parity ledger: one pair")
H.ck((pp[0]["transport"], pp[0]["basis"], pp[0]["adjust"]) == ("db", "closing", "adjusted"),
     "parity ledger: the arm is decoded into a basis and an adjust mode")
H.ck(pp[0]["prod_raw"]["c"] == 11730.0, "parity ledger: the raw column is preserved")
H.ck(pp[0]["proven_rel_err"] == 0.01263, "parity ledger: the ledger's own error is carried")

# --- a capture: type0 raw beside type7 adjusted --------------------------
import json as _json
import os as _os
import tempfile as _tmp
cap = _os.path.join(_tmp.gettempdir(), "r32-reference-tests", "capture.json")
_os.makedirs(_os.path.dirname(cap), exist_ok=True)
with open(cap, "w", encoding="utf-8") as fh:
    _json.dump({"source": {"kind": "rahavard365-web-api", "captured_at": "2026-10-25T18:28:15Z"},
                "series": [
                    {"asset_id": 453, "symbol": "\u0641\u0648\u0644\u0627\u062f", "adjust": "raw",
                     "resolution": "D", "basis": "real_close",
                     "bars": [{"utc": "2026-10-20T12:29:59Z", "open": 100.0, "high": 110.0,
                               "low": 90.0, "close": 105.0, "volume": 5}]},
                    {"asset_id": 453, "symbol": "\u0641\u0648\u0644\u0627\u062f", "adjust": "adjusted",
                     "resolution": "D", "basis": "real_close",
                     "bars": [{"utc": "2026-10-20T12:29:59Z", "open": 50.0, "high": 55.0,
                               "low": 45.0, "close": 52.5, "volume": 5},
                              {"utc": "2026-10-21T12:29:59Z", "open": 1.0, "high": 1.0,
                               "low": 1.0, "close": 1.0, "volume": 1}]}]}, fh)
cp = EV.pairs_from_rahavard_capture(cap)
H.ck(len(cp) == 1, "capture: only dates present on both sides pair", len(cp))
H.ck(cp[0]["prod"]["c"] == 105.0 and cp[0]["ref"]["c"] == 52.5,
     "capture: type0 is prod (raw) and type7 is ref (adjusted)")
H.ck(cp[0]["date"] == "2026-10-20" and cp[0]["timeframe"] == "D",
     "capture: the ISO stamp keeps its day and the resolution is the timeframe")
H.ck(cp[0]["source_prod"].endswith("#type0") and cp[0]["source_ref"].endswith("#type7"),
     "capture: each side names which series it came from")
H.ck(abs(cp[0]["ref"]["o"] / cp[0]["prod"]["o"] - 0.5) < 1e-12,
     "capture: the ratio is the reference's own factor")

H.report()