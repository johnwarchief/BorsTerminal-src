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
* the step-date shift window is read from the real comparison in
  ``stageC_reference_parity.py`` (``delta <= 5`` plus the ``delta_days`` 1-3 /
  4-5 tier split) and pinned as ``STEP_DATE_SHIFT_MAX_DAYS`` /
  ``STEP_DATE_SHIFT_TIERS``;
* the 13 reconciliation categories, the five evidence tiers and both status
  precedence lists are exactly the design lists, in order; the four
  ``CONFLICT_*`` statuses keep the spec table order, because the ledgers read
  the list as a real precedence, not as a membership set.

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

#: stageC step-matching window, spec §7.3: ``delta <= 5`` next to the
#: ``shifted_1_3`` / ``shifted_4_5`` split at day 3.  The guard derives both
#: numbers from the AST below; these are the values it must find.
PINNED_SHIFT_MAX_DAYS = 5
PINNED_SHIFT_TIER_END = 3
PINNED_SHIFT_TIERS = [[1, 3], [4, 5]]

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

#: Spec §7.4 status table order.  The ledgers resolve competing statuses by
#: this order, so a reorder inside the CONFLICT_* block changes verdicts.
EXPECTED_CONFLICT_ORDER = [
    "CONFLICT_RATIO", "CONFLICT_DATE", "CONFLICT_DUPLICATE", "CONFLICT_CHAIN",
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


_CMP_OPS = {ast.LtE: "<=", ast.Gt: ">", ast.Lt: "<", ast.GtE: ">=",
            ast.Eq: "=="}


def _delta_comparisons(path):
    """``[(name, op, int)]`` for ``delta``/``delta_days`` compared to an int.

    Stage C matches reference steps with ``delta <= 5`` and splits the matched
    deltas with ``m["delta_days"] <= 3`` / ``m["delta_days"] > 3``.  Only those
    two names take part, so unrelated integer comparisons stay invisible.
    """
    try:
        tree = _tree(path)
    except (OSError, SyntaxError, ValueError):
        return []
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare) or len(node.ops) != 1:
            continue
        value = node.comparators[0]
        if not (isinstance(value, ast.Constant)
                and isinstance(value.value, int)
                and not isinstance(value.value, bool)):
            continue
        left = node.left
        name = None
        if isinstance(left, ast.Name):
            name = left.id
        elif isinstance(left, ast.Subscript):
            sl = left.slice
            if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                name = sl.value
        op = _CMP_OPS.get(type(node.ops[0]))
        if name in ("delta", "delta_days") and op:
            out.append((name, op, value.value))
    return out


def shift_window(path=None):
    """``(window_days, tier_boundary)`` read from stageC's step matching.

    ``window_days`` is the ``delta <= N`` bound of the matching loop; the tier
    boundary is the shared day count of the ``shifted_1_3`` (``<=``) and
    ``shifted_4_5`` (``>``) buckets.  Each must appear exactly once; a missing
    or duplicated expression yields ``None`` so the guard fails loudly.
    """
    found = _delta_comparisons(path or PARITY)
    windows = sorted({v for name, op, v in found
                      if name == "delta" and op == "<="})
    low = sorted({v for name, op, v in found
                  if name == "delta_days" and op == "<="})
    high = sorted({v for name, op, v in found
                   if name == "delta_days" and op == ">"})
    if len(windows) != 1 or low != high or len(low) != 1:
        return None
    return windows[0], low[0]


def _pairs(value):
    """``[[a, b], ...]`` when every entry is a two-integer list, else None."""
    if not isinstance(value, list):
        return None
    out = []
    for item in value:
        if not isinstance(item, list) or len(item) != 2:
            return None
        if not all(_number(x) and float(x).is_integer() for x in item):
            return None
        out.append([int(x) for x in item])
    return out


def _shift_errors(rules):
    """Pin the step-date shift window and its 1-3 / 4-5 tiers."""
    errors = []
    tolerances = rules.get("tolerances")
    if not isinstance(tolerances, dict):
        return ["tolerances must be an object; the shift window cannot be pinned"]
    window = shift_window()
    if window is None:
        errors.append("stageC step-date shift window (`delta <= N` with the "
                      "`delta_days` 1-3/4-5 split) was not found exactly once "
                      "in %s" % PARITY)
        return errors
    max_days, boundary = window
    if (max_days, boundary) != (PINNED_SHIFT_MAX_DAYS, PINNED_SHIFT_TIER_END):
        errors.append("stageC shift window is %r, expected %r"
                      % (window, (PINNED_SHIFT_MAX_DAYS,
                                  PINNED_SHIFT_TIER_END)))
    expected_tiers = [[1, boundary], [boundary + 1, max_days]]
    if expected_tiers != PINNED_SHIFT_TIERS:
        errors.append("stageC shift tiers %r differ from the design %r"
                      % (expected_tiers, PINNED_SHIFT_TIERS))

    value = tolerances.get("STEP_DATE_SHIFT_MAX_DAYS")
    if not (isinstance(value, int) and not isinstance(value, bool)):
        errors.append("STEP_DATE_SHIFT_MAX_DAYS is missing or not an integer")
    elif value != expected_tiers[-1][-1]:
        errors.append("STEP_DATE_SHIFT_MAX_DAYS %r differs from the stageC "
                      "window %d" % (value, expected_tiers[-1][-1]))
    tiers = _pairs(tolerances.get("STEP_DATE_SHIFT_TIERS"))
    if tiers is None:
        errors.append("STEP_DATE_SHIFT_TIERS must be two [start, end] pairs")
    elif tiers != expected_tiers:
        errors.append("STEP_DATE_SHIFT_TIERS %r differ from the stageC tiers %r"
                      % (tiers, expected_tiers))
    return errors


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

    errors.extend(_shift_errors(rules))
    errors.extend(_category_errors(rules))
    return errors


def _precedence_errors(rules):
    """The CONFLICT_* block must keep the spec table order."""
    errors = []
    precedence = rules.get("step_status_precedence")
    if not isinstance(precedence, list):
        return ["step_status_precedence must be a list"]
    conflicts = [s for s in precedence if str(s).startswith("CONFLICT_")]
    if conflicts != EXPECTED_CONFLICT_ORDER:
        errors.append("CONFLICT_* precedence %r differs from the spec table "
                      "order %r" % (conflicts, EXPECTED_CONFLICT_ORDER))
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
    errors.extend(_precedence_errors(rules))
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
