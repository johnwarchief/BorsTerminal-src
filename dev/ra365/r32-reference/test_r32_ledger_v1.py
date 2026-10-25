#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 32A: the mismatch ledger passes the right rows and names the right cause."""
import os
import tempfile

import _harness as H

import build_mismatch_ledger as LED
import r32_io as IO


def mk(prod, ref, **over):
    base = {"symbol_id": "\u0641\u0648\u0644\u0627\u062f", "symbol": "\u0641\u0648\u0644\u0627\u062f",
            "timeframe": "D", "date": "2024-01-05", "basis": "closing", "adjust": "adjusted",
            "prod": prod, "ref": ref, "prod_raw": {}, "event": None,
            "source_ref": "ref@x", "source_prod": "prod@x"}
    base.update(over)
    return base


# --- the contract tolerance ---------------------------------------------
P = {"o": 100.0, "h": 110.0, "l": 90.0, "c": 105.0, "v": 1.0}
H.ck(LED.passes(P, dict(P))[0], "tolerance: identical sides pass")
H.ck(LED.passes(P, dict(P, o=100.4))[0], "tolerance: a 0.4 absolute difference passes")
H.ck(not LED.passes(P, dict(P, o=100.6))[0], "tolerance: a 0.6 absolute difference fails")
big = {"o": 1e6, "h": 1e6, "l": 1e6, "c": 1e6}
H.ck(LED.passes(big, {"o": 1e6 + 0.9, "h": 1e6, "l": 1e6, "c": 1e6})[0],
     "tolerance: at a large price the relative floor applies")
H.ck(not LED.passes(P, dict(P, c=None))[0], "tolerance: a missing field fails")

# --- causes --------------------------------------------------------------
r = LED.ledger_row(mk(P, {"o": 100.8, "h": 110.8, "l": 90.8, "c": 105.8, "v": 1.0}))
H.ck(r["cause"] == "rounding", "cause: a sub-unit difference is rounding", r["cause"])
H.ck(r["passes_contract"] is False,
     "cause: 0.8 exceeds the 0.5 absolute tolerance, so the row still fails")

r = LED.ledger_row(mk(P, {"o": 100.0, "h": 110.0, "l": 90.0, "c": 205.0, "v": 1.0}))
H.ck(r["cause"] == "close_definition", "cause: only the close differing is a close definition",
     r["cause"])

r = LED.ledger_row(mk(P, {"o": 50.0, "h": 55.0, "l": 45.0, "c": 52.5, "v": 1.0}))
H.ck(r["cause"] == "adjust_ratio", "cause: one ratio across every field is an adjustment",
     r["cause"])
H.ck(r["effective_ratio_ref_over_prod"]["c"] == 0.5,
     "cause: the effective ratio is recorded", r["effective_ratio_ref_over_prod"])

r = LED.ledger_row(dict(mk(P, dict(P)), prod_raw={"c": 105.0},
                        prod={"o": 500.0, "h": 500.0, "l": 500.0, "c": 500.0, "v": 1.0}))
H.ck(r["cause"] == "raw_or_revision",
     "cause: the raw value matching the reference is a raw/revision difference", r["cause"])

r = LED.ledger_row(mk(P, {"o": 13.0, "h": 907.0, "l": 55.0, "c": 201.0, "v": 1.0}))
H.ck(r["cause"] == "unattributed",
     "cause: fields that disagree on the ratio stay unattributed", r["cause"])

# --- the stable key ------------------------------------------------------
H.ck(r["key"] == "\u0641\u0648\u0644\u0627\u062f|D|2024-01-05|closing",
     "key: symbol_id|timeframe|date|price_basis", r["key"])

# --- the denominator -----------------------------------------------------
d = os.path.join(tempfile.gettempdir(), "r32-reference-tests", "ledger")
os.makedirs(d, exist_ok=True)
pairs = [mk(P, dict(P)), mk(P, {"o": 50.0, "h": 55.0, "l": 45.0, "c": 52.5, "v": 1.0}),
         mk(P, {"o": 13.0, "h": 907.0, "l": 55.0, "c": 201.0, "v": 1.0})]
summary = LED.build_ledger(pairs, d, generated_at="2026-10-25T00:00:00Z")
H.ck(summary["denominator"]["paired_compared"] == 3, "denominator: every pair is counted")
H.ck(summary["denominator"]["pass"] == 1 and summary["denominator"]["fail"] == 2,
     "denominator: pass and fail split the whole set", summary["denominator"])
H.ck(summary["denominator"]["removed_from_denominator"] == 0,
     "denominator: nothing is removed from it")
rows = list(IO.read_ndjson_gz(os.path.join(d, "mismatch_map.ndjson.gz")))
H.ck(len(rows) == 2, "ledger: only the failing rows are written", len(rows))
H.ck(all(r["key"] for r in rows), "ledger: every row carries the stable key")

summary2 = LED.build_ledger(pairs[:1], d, prefiltered=True,
                            generated_at="2026-10-25T00:00:00Z")
H.ck(any("divergence ledger" in n for n in summary2["notes"]),
     "prefiltered: the summary says pass=0 is a property of the input")

# --- disposition ---------------------------------------------------------
fam = H.tmp_csv("r32_families.csv",
                ["class", "event_sig", "err_bucket", "steps", "assets", "affected",
                 "attributed", "recovered"],
                [["RATIO_DIFF", "base_gap", "0.1-1%", 297, 223, 179452, 37619, 18302],
                 ["RATIO_DIFF", "unproven_gap", "0.1-1%", 135, 77, 92867, 26644, 7680],
                 ["REF_ONLY", "no_event", "0.1-1%", 231, 118, 130375, 45527, 7106]])
disp = LED.disposition(fam, d, "2026-10-25T00:00:00Z")
H.ck(disp["r30_families"]["recovered_rows_sum"] == 33088,
     "disposition: recovered rows sum exactly", disp["r30_families"]["recovered_rows_sum"])
H.ck(disp["frozen"]["r31_D_tolerance_mismatch"] == 413365,
     "disposition: the frozen mismatch count is carried")
H.ck(len(disp["overlaps_found"]) >= 1, "disposition: overlaps between categories are reported")
H.ck(any(o["class"] == "RATIO_DIFF" for o in disp["overlaps_found"]),
     "disposition: RATIO_DIFF is flagged as spanning several signatures")

H.report()