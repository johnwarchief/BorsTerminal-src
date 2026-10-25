#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 32A: the versioned contract holds, and normalisation is canonical."""
import _harness as H

import r32_schema as S

# --- normalisation -------------------------------------------------------
H.ck(S.normalize_symbol("  \u0641\u0648\u0644\u0627\u062f  ") == "\u0641\u0648\u0644\u0627\u062f",
     "symbol: surrounding whitespace is stripped")
H.ck(S.normalize_symbol("\u0643\u067e\u0627\u0631\u0633") == "\u06a9\u067e\u0627\u0631\u0633",
     "symbol: Arabic KAF folds to Persian KEHEH")
H.ck(S.normalize_symbol("a\u200cb") == "ab", "symbol: zero-width joiners are removed")
H.ck(S.normalize_symbol("a\t b") == "a b", "symbol: inner whitespace collapses to one space")

H.ck(S.normalize_date("2024/01/05") == "2024-01-05", "date: YYYY/MM/DD normalises")
H.ck(S.normalize_date("2024-1-5") == "2024-01-05", "date: single digits are padded")
H.ck(S.normalize_date("2024-01-05T11:22:33Z") == "2024-01-05", "date: an ISO stamp keeps its day")
H.ck(S.normalize_date("1704412800") == "2024-01-05", "date: epoch seconds convert (UTC)")
try:
    S.normalize_date("not-a-date")
    H.ck(False, "date: garbage is rejected")
except S.SchemaError:
    H.ck(True, "date: garbage is rejected")

H.ck(S.normalize_timeframe("d") == "D", "timeframe: lowercase folds to D")
H.ck(S.normalize_timeframe("W") == "W", "timeframe: W passes through")
try:
    S.normalize_timeframe("H")
    H.ck(False, "timeframe: unknown value is rejected")
except S.SchemaError:
    H.ck(True, "timeframe: unknown value is rejected")

H.ck(S.normalize_adjust("type7") == "adjusted", "adjust: type7 is the adjusted series")
H.ck(S.normalize_adjust("type0") == "raw", "adjust: type0 is the raw series")
H.ck(S.normalize_basis("\u067e\u0627\u06cc\u0627\u0646\u06cc") == "closing",
     "basis: the Persian label for closing is understood")
H.ck(S.normalize_basis("nonsense") == "unknown", "basis: an unknown label degrades to unknown")
H.ck(S.normalize_number("") is None and S.normalize_number("nan") is None,
     "number: empty and nan are absent, not zero")
H.ck(S.normalize_number("2.5") == 2.5, "number: numeric strings convert")

# --- the stable key ------------------------------------------------------
k = S.mismatch_key("453", "d", "2024/01/05", "\u067e\u0627\u06cc\u0627\u0646\u06cc")
H.ck(k == "453|D|2024-01-05|closing", "key: symbol_id|timeframe|date|price_basis", k)

# --- bar validation ------------------------------------------------------
def bar(**over):
    base = {"schema": S.SCHEMA_BAR, "symbol_id": "1", "timeframe": "D", "date": "2024-01-05",
            "adjust": "raw", "source_id": "s", "open": 1.0, "high": 2.0, "low": 0.5,
            "close": 1.5, "volume": 10.0, "unavailable": []}
    base.update(over)
    return base

H.ck(S.validate(bar(), S.SCHEMA_BAR) == [], "bar: a complete record validates")
H.ck(S.validate(bar(adjust=None), S.SCHEMA_BAR), "bar: a missing adjust mode is rejected")
H.ck(any("unavailable" in e for e in S.validate(bar(volume=None), S.SCHEMA_BAR)),
     "bar: a null field not listed as unavailable is rejected")
H.ck(S.validate(bar(volume=None, unavailable=["volume"]), S.SCHEMA_BAR) == [],
     "bar: a null field listed as unavailable validates")
H.ck(S.validate(bar(schema="other/9"), S.SCHEMA_BAR), "bar: a foreign schema is rejected")

# --- segment validation --------------------------------------------------
def seg(**over):
    base = {"schema": S.SCHEMA_SEGMENT, "symbol_id": "1", "timeframe": "D",
            "segment_index": 0, "date_from": "2024-01-05", "date_to": "2024-02-05",
            "factor": 0.5, "event_attribution": "unattributed",
            "evidence": {"evidence_kind": "series", "n_sessions": 10}, "unavailable": []}
    base.update(over)
    return base

H.ck(S.validate(seg(), S.SCHEMA_SEGMENT) == [], "segment: a complete record validates")
H.ck(S.validate(seg(evidence={"evidence_kind": "magic", "n_sessions": 1}), S.SCHEMA_SEGMENT),
     "segment: an unknown evidence kind is rejected")
H.ck(S.validate(seg(evidence={"evidence_kind": "series"}), S.SCHEMA_SEGMENT),
     "segment: evidence without n_sessions is rejected")
H.ck(S.validate(seg(factor=None), S.SCHEMA_SEGMENT),
     "segment: a null factor must be declared unavailable")
H.ck(S.validate(seg(factor=None, unavailable=["factor"]), S.SCHEMA_SEGMENT) == [],
     "segment: a null factor declared unavailable validates")
H.ck(S.validate(seg(event_attribution="guessed"), S.SCHEMA_SEGMENT),
     "segment: an out-of-vocabulary attribution is rejected")

# --- mismatch validation -------------------------------------------------
def mis(**over):
    base = {"schema": S.SCHEMA_MISMATCH, "symbol_id": "1", "timeframe": "D",
            "date": "2024-01-05", "price_basis": "closing", "cause": "rounding",
            "key": "1|D|2024-01-05|closing"}
    base.update(over)
    return base

H.ck(S.validate(mis(), S.SCHEMA_MISMATCH) == [], "mismatch: a complete record validates")
H.ck(S.validate(mis(key="wrong"), S.SCHEMA_MISMATCH),
     "mismatch: a key that disagrees with the stable key is rejected")

# --- hashing is order-independent ---------------------------------------
H.ck(S.row_hash({"a": 1, "b": 2}) == S.row_hash({"b": 2, "a": 1}),
     "row_hash: key order does not change the digest")
H.ck(S.row_hash({"a": 1}) != S.row_hash({"a": 2}), "row_hash: a changed value changes the digest")

# --- Persian digits are built, never typed ------------------------------
H.ck(S.fa_digits("149") == "\u06f1\u06f4\u06f9", "fa_digits: digits are generated from codepoints")

H.report()