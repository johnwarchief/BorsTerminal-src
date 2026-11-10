#!/usr/bin/env python3
"""Tests for dev/phase49_rules_guard.py.

Proves the guard pins the five frozen Phase 4.9 tolerances to the real AST of
the existing modules, and that a changed tolerance, a dropped/extra
reconciliation category, a changed evidence tier or a broken status precedence
list fails loudly.  Stdlib only; no DB, no network.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import phase49_rules_guard as G  # noqa: E402


class Checker:
    def __init__(self):
        self.total = 0

    def ok(self, cond, msg):
        self.total += 1
        assert cond, msg

    def eq(self, got, want, msg):
        self.total += 1
        assert got == want, "%s: got %r, want %r" % (msg, got, want)


def mutated(rules):
    return json.loads(json.dumps(rules))


def main():
    c = Checker()
    rules = G.load_rules()

    c.eq(rules["tolerances"]["FACTOR_EXACT"], 1e-3, "FACTOR_EXACT")
    c.eq(rules["tolerances"]["FACTOR_MATERIAL"], 1e-2, "FACTOR_MATERIAL")
    c.eq(rules["tolerances"]["OHLC_MATERIAL"], 5e-2, "OHLC_MATERIAL")
    c.eq(rules["tolerances"]["EXACT_EQ"], 1e-9, "EXACT_EQ")
    c.eq(rules["tolerances"]["DEDUPE_RATIO_TOL"], 1e-2, "DEDUPE_RATIO_TOL")
    c.eq(len(rules["reconciliation_categories"]), 13, "category count")
    c.eq(rules["reconciliation_categories"], G.EXPECTED_CATEGORIES,
         "categories verbatim")
    c.eq(rules["evidence_tiers"], G.EXPECTED_EVIDENCE_TIERS, "evidence tiers")
    c.eq(rules["step_status_precedence"], G.EXPECTED_STEP_STATUSES,
         "step statuses")
    c.eq(rules["symbol_status_precedence"], G.EXPECTED_SYMBOL_STATUSES,
         "symbol statuses")
    c.eq(G.validate_sources(rules), [], "sources")
    c.eq(G.validate_vocabulary(rules), [], "vocabulary")
    c.eq(G._assign_float(G.CORR, "NEAR_DEDUPE_RATIO_TOL"), 1e-2,
         "dedupe source")
    c.eq(G._assign_float(G.IMPORT_REF, "FACTOR_EXACT"), 1e-3, "importer rule")

    bad = mutated(rules)
    bad["tolerances"]["FACTOR_EXACT"] = 0.002
    c.ok(any("FACTOR_EXACT" in e for e in G.validate_sources(bad)),
         "changed threshold must fail")

    for name, value in (("FACTOR_MATERIAL", 0.02), ("OHLC_MATERIAL", 0.06),
                        ("EXACT_EQ", 1e-8), ("DEDUPE_RATIO_TOL", 0.02)):
        bad = mutated(rules)
        bad["tolerances"][name] = value
        c.ok(any(name in e for e in G.validate_sources(bad)),
             "%s change must fail" % name)

    bad = mutated(rules)
    del bad["tolerances"]["FACTOR_EXACT"]
    c.ok(any("FACTOR_EXACT" in e for e in G.validate_sources(bad)),
         "missing tolerance must fail")

    bad = mutated(rules)
    removed = bad["reconciliation_categories"].pop()
    c.ok(any(removed in e for e in G.validate_sources(bad)),
         "removed category must fail")

    bad = mutated(rules)
    bad["reconciliation_categories"].append("EXTRA_CATEGORY")
    c.ok(any("EXTRA_CATEGORY" in e for e in G.validate_sources(bad)),
         "extra category must fail")

    bad = mutated(rules)
    removed = bad["step_status_precedence"].pop(0)
    c.ok(any(removed in e for e in G.validate_vocabulary(bad)),
         "removed step status must fail")

    bad = mutated(rules)
    bad["evidence_tiers"].remove("R2")
    c.ok(any("R2" in e for e in G.validate_vocabulary(bad)),
         "removed tier must fail")

    bad = mutated(rules)
    bad["coverage"]["price_continuity_alone_is_not_evidence"] = False
    c.ok(any("price_continuity_alone_is_not_evidence" in e
             for e in G.validate_vocabulary(bad)),
         "weakened coverage rule must fail")

    # A source that no longer carries a threshold must fail, not pass silently.
    orig = G.PARITY
    try:
        with tempfile.TemporaryDirectory() as tmp:
            text = open(orig, encoding="utf-8").read()
            path = os.path.join(tmp, "stageC_reference_parity.py")
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text.replace("x <= 1e-3", "x <= 2e-3"))
            G.PARITY = path
            errs = G.validate_sources(rules)
            c.ok(any("FACTOR_EXACT" in e and "within_0.1pct" in e for e in errs),
                 "changed source threshold must fail")
    finally:
        G.PARITY = orig

    # A source that no longer defines the named constant must fail loudly.
    orig = G.IMPORT_REF
    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "stage02_import_reference.py")
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("UNRELATED = 1\n")
            G.IMPORT_REF = path
            errs = G.validate_sources(rules)
            c.ok(any("FACTOR_EXACT" in e and "not assigned" in e for e in errs),
                 "missing named constant must fail")
    finally:
        G.IMPORT_REF = orig

    # The CI entry point must exit 0 and print the exact OK line.
    proc = subprocess.run(
        [sys.executable, os.path.join(HERE, "phase49_rules_guard.py")],
        capture_output=True, text=True)
    c.eq(proc.returncode, 0, "guard exit code")
    c.ok("STATUS RULES GUARD OK" in proc.stdout, "guard OK line")

    print("%d/%d passed" % (c.total, c.total))
    print("STATUS RULES TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
