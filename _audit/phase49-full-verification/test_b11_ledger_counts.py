#!/usr/bin/env python3
"""Recompute the B11 ledger counts from the CSVs and pin the disclosure.

The review of B11 found that the 5,983 ``VERIFIED_*`` steps had been reported
as if all of them were independently evidenced. This test recomputes the
split from ``ADJUSTMENT-EVIDENCE-LEDGER.csv`` itself and fails if the tracked
``evidence/ledger-counts.json`` drifts from it: 4,846 of the 4,933
``VERIFIED_REFERENCE`` rows take their ratio from the reference index and are
confirmations of the same source, leaving 1,137 independently evidenced rows.

It also pins the corrected reference coverage (792 of 951 raw pack spellings,
756 of 915 normalised keys), the 1,467 vs 1,468 no-instrument off-by-one, the
two ``audit:ratio-out-of-range`` rows, and the B6/B5 Volana status pairing.
No status is changed or promoted here.
"""
import collections
import csv
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from symbol_identity import key  # noqa: E402

EVIDENCE = os.path.join(HERE, "evidence")
LEDGERS = os.path.join(HERE, "ledgers")
COUNTS = os.path.join(EVIDENCE, "ledger-counts.json")
STEP_CSV = os.path.join(LEDGERS, "ADJUSTMENT-EVIDENCE-LEDGER.csv")
SYMBOL_CSV = os.path.join(LEDGERS, "HISTORY-COVERAGE-LEDGER.csv")
REFERENCE = os.path.join(HERE, "captures", "reference-index-all.json")
VOLANA = os.path.join(EVIDENCE, "volana-rootcause.json")
STEP_MANIFEST = os.path.join(EVIDENCE, "stage03_step_ledger.manifest.json")
SYMBOL_MANIFEST = os.path.join(EVIDENCE, "stage05_symbol_ledger.manifest.json")

REFERENCE_DERIVED_METHODS = (
    "multi_field_step_inference", "reference-factor-step-v1")


def _sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _rows(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def main():
    counts = json.load(open(COUNTS, encoding="utf-8"))
    steps = _rows(STEP_CSV)
    symbols = _rows(SYMBOL_CSV)

    # Row and status counts are unchanged by the B11 fix.
    assert len(steps) == 8308, len(steps)
    assert len(symbols) == 6103, len(symbols)
    by_status = collections.Counter(r["final_status"] for r in steps)
    assert dict(by_status) == counts["step_ledger"]["by_status"], by_status
    assert sum(by_status.values()) == 8308

    # Reference-derived VR = ratio taken from the reference; product-derived
    # VR = the 87 base-price-discontinuity rows that keep a product ratio.
    vr = [r for r in steps if r["final_status"] == "VERIFIED_REFERENCE"]
    refd = [r for r in vr if r["method"] in REFERENCE_DERIVED_METHODS]
    prod = [r for r in vr if r["method"] not in REFERENCE_DERIVED_METHODS]
    assert len(vr) == 4933, len(vr)
    assert len(refd) == 4846, len(refd)
    assert len(prod) == 87, len(prod)
    assert all(abs(float(r["ratio"]) - float(r["ref_ratio"])) < 1e-12
               for r in refd)
    vref = counts["independence"]["verified_reference"]
    assert (vref["total"], vref["reference_derived_confirmations"],
            vref["product_derived"]) == (4933, 4846, 87)
    assert "not independent validation" in vref["reference_derived_note"]

    # Independent witnesses: VMS (O1+R1) + VO (O1) + product-derived VR.
    vms = [r for r in steps if r["final_status"] == "VERIFIED_MULTI_SOURCE"]
    vo = [r for r in steps if r["final_status"] == "VERIFIED_OFFICIAL"]
    independent = len(vms) + len(vo) + len(prod)
    assert (len(vms), len(vo), independent) == (955, 95, 1137)
    assert independent + len(refd) == 5983
    assert counts["independence"]["verified_group_total"] == 5983
    assert counts["independence"]["independently_evidenced"] == independent

    # Shifted witnesses (primary witness, ±1-5 days) and exact dates.
    vms_shift = sum(1 for r in vms if "O1 date shifted" in r["notes"])
    vo_shift = sum(1 for r in vo if "date shifted" in r["notes"])
    prod_shift = sum(1 for r in prod if "date shifted" in r["notes"])
    assert (vms_shift, vo_shift, prod_shift) == (839, 58, 59)
    shifted = vms_shift + vo_shift + prod_shift
    assert counts["independence"]["shifted_witness"]["total"] == shifted == 956
    assert counts["independence"]["exact_date"] == independent - shifted == 181
    no_shift = independent - sum(
        1 for r in vms + vo + prod if "date shifted" in r["notes"])
    assert no_shift == 157, no_shift

    # The two out-of-range ratios stay visible and are reference-derived.
    out = [r for r in steps if "audit:ratio-out-of-range" in r["notes"]]
    assert len(out) == 2, out
    assert all(r["final_status"] == "VERIFIED_REFERENCE"
               and float(r["ratio"]) > 1.0 for r in out)
    assert counts["independence"]["ratio_out_of_range_verified_reference"][
        "rows"] == 2

    # Corrected raw coverage: 792 of 951 spellings (756 of 915 keys).
    reference = json.load(open(REFERENCE, encoding="utf-8"))
    covered_keys = {str(rec.get("key") or raw)
                    for raw, rec in reference.items()}
    raw_symbols = {r["symbol"] for r in steps}
    raw_keys = {key(s) for s in raw_symbols}
    covered_raw = sum(1 for s in raw_symbols if key(s) in covered_keys)
    assert (len(raw_symbols), len(raw_keys)) == (951, 915)
    assert covered_raw == 792, covered_raw
    assert len(raw_keys & covered_keys) == 756
    ref = counts["symbol_ledger"]["reference"]
    assert ref["pack_symbols_covered_raw"] == 792
    assert ref["pack_symbols_covered_keys"] == 756
    assert ref["coverage_pct_raw"] == 83.3
    assert "792 of 951" in ref["coverage_note"]

    # Off-by-one: 1,467 no-instrument rows are zero-step; one has a step.
    no_inst = [r for r in symbols
               if r["identity_status"] == "unresolved_no_instruments"]
    assert len(no_inst) == 1468
    zero_step = [r for r in no_inst if int(r["factor_steps"] or 0) == 0]
    assert len(zero_step) == 1467, len(zero_step)
    assert counts["validity_reconciliation"][
        "no_instrument_rows_in_zero_step_remainder"] == 1467
    assert counts["validity_reconciliation"]["no_instrument_rows_total"] == 1468

    # B6 assessment label vs the B5 ledger status: both recorded, no promotion.
    volana = json.load(open(VOLANA, encoding="utf-8"))
    disclosure = volana["status_disclosure"]
    assert disclosure["ledger_statuses"] == {"RECONSTRUCTED_AUDITED": 3}
    ledger_by_date = {r["effective_date"]: r["final_status"]
                      for r in steps if r["symbol"] == volana["symbol"]}
    for row in disclosure["steps"]:
        assert row["assessment_status"] == "PARTIAL_REFERENCE"
        assert ledger_by_date[row["effective_date"]] == "RECONSTRUCTED_AUDITED"

    # Hash consistency: the CSVs are pinned in the counts and the manifests.
    assert counts["step_ledger"]["sha256"] == _sha256(STEP_CSV)
    assert counts["symbol_ledger"]["sha256"] == _sha256(SYMBOL_CSV)
    step_manifest = json.load(open(STEP_MANIFEST, encoding="utf-8"))
    symbol_manifest = json.load(open(SYMBOL_MANIFEST, encoding="utf-8"))
    assert step_manifest["outputs"][
        "_audit/phase49-full-verification/ledgers/"
        "ADJUSTMENT-EVIDENCE-LEDGER.csv"] == counts["step_ledger"]["sha256"]
    assert symbol_manifest["outputs"][
        "_audit/phase49-full-verification/ledgers/"
        "HISTORY-COVERAGE-LEDGER.csv"] == counts["symbol_ledger"]["sha256"]
    assert counts["reference"]["sha256"] == _sha256(REFERENCE)

    print("B11 COUNT TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
