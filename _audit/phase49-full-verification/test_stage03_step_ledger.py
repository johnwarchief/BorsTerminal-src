#!/usr/bin/env python3
import inspect
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import stage03_step_ledger as S  # noqa: E402

RULES_PATH = os.path.join(ROOT, "dev", "phase49_status_rules.json")

#: The frozen vocabulary, spelled out so the unit tests do not depend on the
#: real rules file for their status names. The tolerance values below are
#: cross-checked against that file in ``test_rules_file_pins``.
RULES = {
    "tolerances": {"EXACT_EQ": 1e-9, "FACTOR_EXACT": 1e-3,
                   "FACTOR_MATERIAL": 1e-2, "DEDUPE_RATIO_TOL": 1e-2,
                   "STEP_DATE_SHIFT_MAX_DAYS": 5,
                   "STEP_DATE_SHIFT_TIERS": [[1, 3], [4, 5]]},
    "step_status_precedence": [
        "CONFLICT_RATIO", "CONFLICT_DATE", "CONFLICT_DUPLICATE",
        "CONFLICT_CHAIN", "BLOCKED_SOURCE", "INSUFFICIENT_EVIDENCE",
        "PARTIAL_OFFICIAL", "PARTIAL_REFERENCE", "RECONSTRUCTED_AUDITED",
        "VERIFIED_MULTI_SOURCE", "VERIFIED_OFFICIAL", "VERIFIED_REFERENCE",
        "INVALID_DROPPED",
    ],
}


def rules_with(**tolerances):
    out = json.loads(json.dumps(RULES))
    out["tolerances"].update(tolerances)
    return out


def step(ratio=0.9, date="2020-01-02"):
    return {"symbol": "الف", "effective_date": date, "ratio": ratio,
            "prod_ratio": ratio, "ref_ratio": ratio,
            "cum_factor_after": 0.9, "prov_kind": "pack",
            "method": "multi_field_step_inference",
            "fields_used": "open,high,low,close", "validity": "unverified"}


def audit_entry(*notes):
    return {"ok": not notes, "notes": list(notes)}


def test_rules_file_pins():
    """The defaults mirror the frozen rules file; they are not local values."""
    with open(RULES_PATH, encoding="utf-8") as fh:
        frozen = json.load(fh)
    for name, value in RULES["tolerances"].items():
        assert frozen["tolerances"][name] == value, name
    assert frozen["step_status_precedence"] == RULES["step_status_precedence"]
    dup_tol = inspect.signature(S.audit_reconstruction).parameters["dup_tol"]
    assert dup_tol.default == frozen["tolerances"]["DEDUPE_RATIO_TOL"], dup_tol
    assert not hasattr(S, "SHIFT_DAYS"), "the shift window must come from rules"


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


def test_dedupe_uses_frozen_one_percent():
    """0.5% apart is the same event; 2% apart is a duplicate (1% tolerance)."""
    base = {"effective_date": "2020-01-02", "cum_factor_after": 1.0,
            "method": "m", "fields_used": "f", "prov_kind": "pack",
            "validity": "reconstructed_verified"}
    close = [dict(base, symbol="ك", ratio=0.9000),
             dict(base, symbol="ک", ratio=0.9045)]
    a = S.audit_reconstruction(close, dup_tol=1e-2)
    assert a[("ك", "2020-01-02")]["ok"], a
    wide = [dict(base, symbol="ك", ratio=0.9000),
            dict(base, symbol="ک", ratio=0.9200)]
    a = S.audit_reconstruction(wide, dup_tol=1e-2)
    assert "duplicate-date" in a[("ك", "2020-01-02")]["notes"], a
    # At the old 0.1% tolerance the 0.5% pair would have been a duplicate; the
    # frozen rule must not regress to it.
    a = S.audit_reconstruction(close, dup_tol=1e-3)
    assert "duplicate-date" in a[("ك", "2020-01-02")]["notes"], a


def test_shift_window_comes_from_rules():
    """A witness 2 days away counts at max=5 and not at max=0."""
    idx = S.OfficialIndex()
    idx.add("الف", "2020-01-04", {"ratio": 0.9, "tier": "O1",
                                  "source": "price_adjust_events",
                                  "date": "2020-01-04"})
    r = S.classify(step(), idx, {}, RULES)
    assert r["final_status"] == "VERIFIED_OFFICIAL", r
    assert "@shift2d" in r["evidence_ref"], r
    tight = S.classify(step(), idx, {}, rules_with(STEP_DATE_SHIFT_MAX_DAYS=0))
    assert tight["final_status"] == "RECONSTRUCTED_AUDITED", tight


def test_precedence_is_an_order():
    """CONFLICT_RATIO outranks CONFLICT_DUPLICATE, as the spec table does."""
    precedence = RULES["step_status_precedence"]
    assert S._first_by_precedence(
        ["CONFLICT_DUPLICATE", "CONFLICT_RATIO"], precedence) == \
        "CONFLICT_RATIO"
    assert S._first_by_precedence(
        ["VERIFIED_OFFICIAL", "CONFLICT_DUPLICATE"], precedence) == \
        "CONFLICT_DUPLICATE"
    for bad in (["NOT_A_STATUS"],):
        try:
            S._first_by_precedence(bad, precedence)
        except ValueError:
            pass
        else:
            raise AssertionError("unknown status must raise")


def test_classify_precedence():
    """A duplicate spelling whose ratio conflicts reports the ratio conflict."""
    ds = "2020-01-02"
    dup = audit_entry("duplicate-date", "symbol-identity")
    off_bad = {(S.key("ك"), ds): [{"ratio": 0.5, "tier": "O1"}]}
    r = S.classify(dict(step(), symbol="ك"), off_bad, {}, RULES, audit=dup)
    assert r["final_status"] == "CONFLICT_RATIO", r
    assert r["discrepancy_cause"] == "EVENT_RATIO_MISMATCH", r
    off_ok = {(S.key("ك"), ds): [{"ratio": 0.9, "tier": "O1"}]}
    r = S.classify(dict(step(), symbol="ك"), off_ok, {}, RULES, audit=dup)
    assert r["final_status"] == "CONFLICT_DUPLICATE", r
    assert r["discrepancy_cause"] == "SYMBOL_IDENTITY_MISMATCH", r


def test_evidence_invariants():
    """The tracked counts must keep the mandatory row/validity invariants."""
    path = os.path.join(HERE, "evidence", "step-ledger-counts.json")
    with open(path, encoding="utf-8") as fh:
        counts = json.load(fh)
    assert counts["rows"] == 8308, counts["rows"]
    assert sum(counts["by_status"].values()) == counts["rows"]
    assert counts["by_validity"]["invalid_dropped"] == 28
    assert counts["by_validity"]["reconstructed_verified"] == 6300
    audit = counts["reconstruction_audit"]["by_validity"]
    assert audit["reconstructed_verified"]["rows"] == 6300
    assert (audit["reconstructed_verified"]["passed"]
            + audit["reconstructed_verified"]["failed"] == 6300)
    assert counts["inputs"]["dedupe_ratio_tol"] == 1e-2
    assert counts["inputs"]["step_date_shift_max_days"] == 5


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
    test_rules_file_pins()
    test_reference_direction()
    test_chain_audit_direction()
    test_duplicate_spelling()
    test_dedupe_uses_frozen_one_percent()
    test_shift_window_comes_from_rules()
    test_precedence_is_an_order()
    test_classify_precedence()
    test_evidence_invariants()
    test_dropped_and_o2()
    test_witness_preference()
    print("STEP LEDGER TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
