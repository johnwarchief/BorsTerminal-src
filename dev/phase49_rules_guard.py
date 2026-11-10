#!/usr/bin/env python3
"""Phase 4.9.1 status-rules guard.

``dev/phase49_status_rules.json`` is the single place the verification ledgers
read their tolerances, status precedence, evidence tiers and reconciliation
categories from.  This guard proves the file still mirrors the frozen Phase 4.9
code and the design vocabulary:

* the four ``stageC_reference_parity.py`` thresholds (``EXACT_EQ``,
  ``FACTOR_EXACT``, ``FACTOR_MATERIAL``, ``OHLC_MATERIAL``) are read from the
  real AST: the values must still be the float literals carried by the summary
  dicts, and the rules file must pin exactly those values;
* ``FACTOR_EXACT`` also matches the named assignment in
  ``stage02_import_reference.py`` (the frozen importer rule);
* ``DEDUPE_RATIO_TOL`` matches
  ``adjustment_corrections.NEAR_DEDUPE_RATIO_TOL``;
* the 13 reconciliation categories, the five evidence tiers and both status
  precedence lists are exactly the design lists, in order.

A changed threshold, a missing/extra category, a reordered precedence list or a
source module that no longer defines the constant fails loudly.  This guard
never edits a threshold and never relaxes a comparison.  Stdlib only; no DB, no
network.
"""
import ast
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES = os.path.join(ROOT, "dev", "phase49_status_rules.json")
PARITY = os.path.join(ROOT, "_audit", "phase49-finalization",
                      "stageC_reference_parity.py")
IMPORT_REF = os.path.join(ROOT, "_audit", "phase49-full-verification",
                          "stage02_import_reference.py")
CORR = os.path.join(ROOT, "adjustment_corrections.py")

#: Design spec §§7.3-7.4 -- frozen.  Every value already exists in the code;
#: none is introduced here.  The JSON must mirror these exactly.
PINNED_TOLERANCES = {
    "EXACT_EQ": 1e-9,
    "FACTOR_EXACT": 1e-3,
    "FACTOR_MATERIAL": 1e-2,
    "OHLC_MATERIAL": 5e-2,
    "DEDUPE_RATIO_TOL": 1e-2,
}

#: stageC summary fields that carry each threshold (both spellings of the exact
#: bucket exist).  The AST check reads the float literals under these keys.
PARITY_FIELDS = {
    "EXACT_EQ": ("exact_1e9", "equal_1e9"),
    "FACTOR_EXACT": ("within_0.1pct",),
    "FACTOR_MATERIAL": ("within_1pct",),
    "OHLC_MATERIAL": ("over_5pct",),
}

#: Design spec §§7.2, 7.4, 8.1, 9 -- verbatim lists.
EXPECTED_EVIDENCE_TIERS = ["O1", "O2", "R1", "R2", "I1"]

EXPECTED_STEP_STATUSES = [
    "CONFLICT_RATIO", "CONFLICT_DATE", "CONFLICT_DUPLICATE", "CONFLICT_CHAIN",
    "BLOCKED_SOURCE", "INSUFFICIENT_EVIDENCE",
    "PARTIAL_OFFICIAL", "PARTIAL_REFERENCE",
    "RECONSTRUCTED_AUDITED",
    "VERIFIED_MULTI_SOURCE", "VERIFIED_OFFICIAL", "VERIFIED_REFERENCE",
    "INVALID_DROPPED",
]

EXPECTED_SYMBOL_STATUSES = [
    "CONFLICT", "BLOCKED_SOURCE", "INSUFFICIENT_EVIDENCE",
    "RECONSTRUCTED_VERIFIED", "VERIFIED_WITH_EVENTS",
    "VERIFIED_NO_APPLICABLE_EVENT",
]

EXPECTED_CATEGORIES = [
    "SOURCE_MISMATCH", "PRICE_BASIS_DIFFERENCE", "CORPORATE_ACTION_MISSING",
    "EVENT_DATE_MISMATCH", "EVENT_RATIO_MISMATCH", "SYMBOL_IDENTITY_MISMATCH",
    "MISSING_HISTORY", "CALENDAR_GAP", "SOURCE_REVISION", "PRECISION_OR_ROUNDING",
    "INVALID_SOURCE_RECORD", "VERIFIED_NO_EVENT", "UNRESOLVED_SOURCE_GAP",
]

COVERAGE_FLAGS = (
    "official_absence_requires_ingest_proof",
    "reference_no_event_requires_full_window",
    "price_continuity_alone_is_not_evidence",
)


def load_rules():
    with open(RULES, encoding="utf-8") as fh:
        return json.load(fh)


def _tree(path):
    with open(path, encoding="utf-8") as fh:
        return ast.parse(fh.read(), filename=path)


def _floats(path):
    """Every float literal in a module; empty when the module cannot be read."""
    try:
        tree = _tree(path)
    except (OSError, SyntaxError, ValueError):
        return set()
    return {n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, float)}


def _assign_float(path, name):
    """Value of a module-level ``name = <float literal>`` assignment, else None."""
    try:
        tree = _tree(path)
    except (OSError, SyntaxError, ValueError):
        return None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not (isinstance(target, ast.Name) and target.id == name):
                continue
            value = node.value
            if isinstance(value, ast.Constant) and isinstance(value.value, float):
                return value.value
    return None


def _field_floats(path):
    """dict field name -> list of float-literal sets found under its values.

    ``None`` values (e.g. the adjusted-OHLC placeholder) contribute no floats
    and are skipped, so only real thresholds take part in the comparison.
    """
    try:
        tree = _tree(path)
    except (OSError, SyntaxError, ValueError):
        return {}
    out = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                continue
            found = {n.value for n in ast.walk(value)
                     if isinstance(n, ast.Constant) and isinstance(n.value, float)}
            if found:
                out.setdefault(key.value, []).append(found)
    return out


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _list_errors(label, actual, expected, errors):
    if not isinstance(actual, list):
        errors.append("%s must be a list" % label)
        return
    missing = [v for v in expected if v not in actual]
    extra = [v for v in actual if v not in expected]
    for value in missing:
        errors.append("%s missing %r" % (label, value))
    for value in extra:
        errors.append("%s has unknown entry %r" % (label, value))
    if len(actual) != len(set(map(str, actual))):
        errors.append("%s contains duplicate entries" % label)
    if not missing and not extra and actual != list(expected):
        errors.append("%s is not in the frozen order" % label)


def _category_errors(rules):
    errors = []
    categories = rules.get("reconciliation_categories")
    _list_errors("reconciliation_categories", categories,
                 EXPECTED_CATEGORIES, errors)
    if isinstance(categories, list) and len(categories) != 13:
        errors.append("reconciliation_categories must contain 13 entries "
                      "(found %d)" % len(categories))
    return errors


def validate_sources(rules):
    """Compare the rules file with the existing Phase 4.9 modules (AST)."""
    errors = []
    tolerances = rules.get("tolerances")
    if not isinstance(tolerances, dict):
        return ["tolerances must be an object; no threshold can be pinned"]

    floats = _floats(PARITY)
    fields = _field_floats(PARITY)
    for name, expected in PINNED_TOLERANCES.items():
        value = tolerances.get(name)
        if not _number(value):
            errors.append("tolerances.%s is missing or not a number" % name)
        elif abs(float(value) - expected) > 0:
            errors.append("tolerances.%s differs from Phase 4.9 constant %r"
                          % (name, expected))

    for name in ("EXACT_EQ", "FACTOR_EXACT", "FACTOR_MATERIAL", "OHLC_MATERIAL"):
        expected = PINNED_TOLERANCES[name]
        if expected not in floats:
            errors.append("%s value %r not found in %s" % (name, expected, PARITY))
        for field in PARITY_FIELDS[name]:
            occurrences = fields.get(field)
            if not occurrences:
                errors.append("%s no longer defines %r in %s"
                              % (name, field, PARITY))
                continue
            for found in occurrences:
                if found != {expected}:
                    errors.append("%s: %r in %s carries %s, expected %r"
                                  % (name, field, PARITY, sorted(found), expected))

    named = _assign_float(IMPORT_REF, "FACTOR_EXACT")
    if named is None:
        errors.append("FACTOR_EXACT is not assigned in %s" % IMPORT_REF)
    elif abs(named - PINNED_TOLERANCES["FACTOR_EXACT"]) > 0:
        errors.append("FACTOR_EXACT in %s is %r, expected %r"
                      % (IMPORT_REF, named, PINNED_TOLERANCES["FACTOR_EXACT"]))

    dedupe = _assign_float(CORR, "NEAR_DEDUPE_RATIO_TOL")
    if dedupe is None:
        errors.append("NEAR_DEDUPE_RATIO_TOL is not assigned in %s" % CORR)
    else:
        value = tolerances.get("DEDUPE_RATIO_TOL")
        if not _number(value) or abs(float(value) - dedupe) > 0:
            errors.append("DEDUPE_RATIO_TOL differs from adjustment_corrections")
        if abs(dedupe - PINNED_TOLERANCES["DEDUPE_RATIO_TOL"]) > 0:
            errors.append("NEAR_DEDUPE_RATIO_TOL in %s is %r, expected %r"
                          % (CORR, dedupe, PINNED_TOLERANCES["DEDUPE_RATIO_TOL"]))

    errors.extend(_category_errors(rules))
    return errors


def validate_vocabulary(rules):
    """Schema, evidence tiers, status precedence and coverage rules."""
    errors = []
    if rules.get("schema") != 1:
        errors.append("schema must be 1")
    _list_errors("evidence_tiers", rules.get("evidence_tiers"),
                 EXPECTED_EVIDENCE_TIERS, errors)
    _list_errors("step_status_precedence", rules.get("step_status_precedence"),
                 EXPECTED_STEP_STATUSES, errors)
    _list_errors("symbol_status_precedence",
                 rules.get("symbol_status_precedence"),
                 EXPECTED_SYMBOL_STATUSES, errors)
    coverage = rules.get("coverage")
    if not isinstance(coverage, dict):
        errors.append("coverage must be an object")
    else:
        for flag in COVERAGE_FLAGS:
            if coverage.get(flag) is not True:
                errors.append("coverage.%s must be true" % flag)
        for key in sorted(set(coverage) - set(COVERAGE_FLAGS)):
            errors.append("coverage has unknown entry %r" % key)
    return errors


def validate_rules(rules):
    return validate_sources(rules) + validate_vocabulary(rules)


def main():
    try:
        rules = load_rules()
    except (OSError, ValueError) as exc:
        print("STATUS RULES GUARD FAIL")
        print(" - cannot read %s: %s" % (RULES, exc))
        return 1
    errors = validate_rules(rules)
    if errors:
        print("STATUS RULES GUARD FAIL")
        for error in errors:
            print(" -", error)
        return 1
    print("STATUS RULES GUARD OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
