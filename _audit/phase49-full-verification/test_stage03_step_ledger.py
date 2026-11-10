#!/usr/bin/env python3
import os
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stage03_step_ledger as S  # noqa: E402

RULES = {"tolerances": {"EXACT_EQ": 1e-9, "FACTOR_EXACT": 1e-3,
                         "FACTOR_MATERIAL": 1e-2}}


def step(ratio=0.9, date="2020-01-02"):
    return {"symbol": "الف", "effective_date": date, "ratio": ratio,
            "prod_ratio": ratio, "ref_ratio": ratio,
            "cum_factor_after": 0.9, "prov_kind": "pack",
            "method": "multi_field_step_inference",
            "fields_used": "open,high,low,close", "validity": "unverified"}


def test_reference_direction():
    """The frozen index stores factor_t/factor_t-1; the pack uses its inverse."""
    rr = S._ref_step_ratio({"date": "2020-01-02", "factor": 0.9,
                            "ratio_change": 1.0 / 0.9})
    assert abs(rr - 0.9) < 1e-12, rr
    assert S._ref_step_ratio({"date": "2020-01-02", "factor": 0.9}) == 0.9


def test_chain_audit_direction():
    base = {"symbol": "ب", "method": "m", "fields_used": "f",
            "prov_kind": "pack", "validity": "reconstructed_verified"}
    newer = dict(base, effective_date="2021-01-01", ratio=0.8,
                 cum_factor_after=1.0)
    older = dict(base, effective_date="2020-01-01", ratio=0.5,
                 cum_factor_after=0.8)
    a = S.audit_reconstruction([older, newer])
    assert a[("ب", "2020-01-01")]["ok"], a
    broken = dict(older, cum_factor_after=0.9)
    a = S.audit_reconstruction([broken, newer])
    assert "cum-factor-chain" in a[("ب", "2020-01-01")]["notes"], a


def test_duplicate_spelling():
    base = {"effective_date": "2020-01-02", "cum_factor_after": 1.0,
            "method": "m", "fields_used": "f", "prov_kind": "pack",
            "validity": "reconstructed_verified"}
    steps = [dict(base, symbol="ك", ratio=0.9),
             dict(base, symbol="ک", ratio=0.8)]
    a = S.audit_reconstruction(steps)
    for raw in ("ك", "ک"):
        notes = a[(raw, "2020-01-02")]["notes"]
        assert "duplicate-date" in notes, notes
        assert "symbol-identity" in notes, notes


def test_dropped_and_o2():
    r = S.classify({"symbol": "ج", "effective_date": "2020-01-02",
                    "ratio": 0.9, "validity": "invalid_dropped",
                    "action": "drop-contradicted"}, {}, {}, RULES)
    assert r["final_status"] == "INVALID_DROPPED", r
    notices = {"الف": [{"date": "2020-01-05", "title": "افزایش سرمایه",
                        "url": "u"}]}
    r = S.classify(step(), {}, {}, RULES, notices=notices)
    assert "O2" in r["evidence_tier"].split("+"), r


def test_witness_preference():
    cands = [(0, {"ratio": 0.5}, 0.5), (2, {"ratio": 0.9}, 0.9)]
    picked = S._pick_witness(cands, 0.9, 1e-3, 1e-2)
    assert picked[2] == "MATCH" and picked[0] == 2, picked


def main():
    off = {("الف", "2020-01-02"): [{"ratio": 0.9, "tier": "O1"}]}
    ref = {"الف": {"factor_changes": [{"date": "2020-01-02", "factor": 0.9}]}}
    r = S.classify(step(), off, ref, RULES)
    assert r["final_status"] == "VERIFIED_MULTI_SOURCE", r
    off_bad = {("الف", "2020-01-02"): [{"ratio": 0.5, "tier": "O1"}]}
    r = S.classify(step(), off_bad, {"الف": {"factor_changes": []}}, RULES)
    assert r["final_status"] == "CONFLICT_RATIO", r
    r = S.classify(step(), {}, {"الف": {"factor_changes": []}}, RULES)
    assert r["final_status"] == "RECONSTRUCTED_AUDITED", r
    r = S.classify(step(ratio=1.2), {}, {}, RULES)
    assert r["final_status"] == "INSUFFICIENT_EVIDENCE", r
    test_reference_direction()
    test_chain_audit_direction()
    test_duplicate_spelling()
    test_dropped_and_o2()
    test_witness_preference()
    print("STEP LEDGER TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
