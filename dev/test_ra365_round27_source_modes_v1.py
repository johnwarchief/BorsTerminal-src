#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 27: shadow source-mode invariants (no production wiring)."""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("shadow", os.path.join(ROOT, "tools", "ra365_source_shadow.py"))
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   ← %s" % (detail,)) if detail else ""))


t = [{"date": "2024-01-01", "open": 1, "high": 2, "low": 1, "close": 2}]
r = [{"date": "2024-01-01", "open": 1, "high": 3, "low": 1, "close": 2}]

s = S.select_series_source("X", "tsetmc", t, r, "tsetmc-snap", "ref-snap")
ck(s.source == "tsetmc" and len(s.bars) == 1 and s.provenance["snapshot"] == "tsetmc-snap",
   "tsetmc-primary uses only the TSETMC rows with provenance", s.provenance)

s = S.select_series_source("X", "rahavard", t, r, "tsetmc-snap", "ref-snap")
ck(s.source == "rahavard" and s.provenance["snapshot"] == "ref-snap",
   "rahavard-primary uses only the reference rows with provenance", s.provenance)

s = S.select_series_source("X", "dual", t, r, "tsetmc-snap", "ref-snap")
ck(s.source == "tsetmc" and s.provenance["policy"] == "dual_per_series_tsetmc",
   "dual mode picks one source per series (TSETMC when present)", s.provenance)
ck({b["source"] for b in s.bars} == {"tsetmc"},
   "dual mode never merges reference rows into a TSETMC series")

s = S.select_series_source("X", "dual", [], r, "tsetmc-snap", "ref-snap")
ck(s.source == "rahavard" and s.provenance["policy"] == "dual_per_series_rahavard",
   "dual mode falls back to the reference only when TSETMC has no series")

try:
    S.select_series_source("X", "dual", [], [], None, None)
    ck(False, "both sources empty must be UNAVAILABLE")
except LookupError as e:
    ck("UNAVAILABLE" in str(e), "both sources empty is UNAVAILABLE, not a silent fallback", e)

try:
    S.SourceSeries("X", "tsetmc", [{"date": "d", "source": "tsetmc"}, {"date": "e", "source": "rahavard"}])
    ck(False, "a mixed series must be rejected")
except S.SourceMixError:
    ck(True, "constructing a mixed-source series raises SourceMixError")

cmp = S.compare_sources(t, r)
ck(cmp["common_rows"] == 1 and cmp["rows_with_field_difference"] == 1 and cmp["rahavard_only"] == 0,
   "source comparison reports overlap and field differences", cmp)

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
