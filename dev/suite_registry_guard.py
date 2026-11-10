#!/usr/bin/env python3
"""Validate dev/suite_registry.json against dev/run_all_tests.py."""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(ROOT, "dev", "run_all_tests.py")
REGISTRY = os.path.join(ROOT, "dev", "suite_registry.json")
CATEGORIES = {"A", "B", "C", "D"}
DISPOSITIONS = {"KEEP", "MIGRATE", "DEPRECATE", "REMOVE"}
PROFILES = {"production", "data", "legacy"}


def parse_suites(path=RUNNER):
    tree = ast.parse(open(path, encoding="utf-8").read())
    out = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id not in ("SUITES", "JS_SUITES"):
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple)):
            # run_all_tests.py re-binds the names after lane filtering
            # (`SUITES = [(s, l) for s, l in SUITES if _selected(s)]`); only the
            # literal definitions are the source of truth for the registry.
            continue
        for elt in node.value.elts:
            script, label = ast.literal_eval(elt)
            if script in out:
                raise ValueError("duplicate suite in runner: %s" % script)
            out[script] = {"script": script, "label": label, "kind": target.id}
    return out


GO_SUFFIXES = (".go",)
TS_SUFFIXES = (".ts", ".tsx")


def _declares_test(text, test, suffixes):
    """The named test must be a real declaration, not a comment or a call.

    A bare name search accepted a name mentioned in a comment, an import or an
    unrelated call site.  The equivalence is the migration evidence, so it has
    to point at an executable test:

    - Go: `func <TestName>(` at the start of a line (leading whitespace allowed).
    - TS/TSX: `<TestName>` as the quoted title of `it(...)`, `test(...)` or
      `describe(...)`.
    """
    name = re.escape(test)
    if suffixes == GO_SUFFIXES:
        pattern = r"^[ \t]*func[ \t]+%s[ \t]*\(" % name
    else:
        pattern = r"""^[ \t]*(?:it|test|describe)[ \t]*\([ \t]*(["'`])%s\1""" % name
    return re.search(pattern, text, re.MULTILINE) is not None


def _equiv_exists(value, suffixes=GO_SUFFIXES):
    """A real repo-contained test file that declares the `:TestName` test.

    Accepting any existing file made the check vacuous: a `.py` path, a path
    without a symbol, or a path outside the repository all passed.  The
    equivalence is the migration evidence, so it must name a file of the right
    language, inside the repo, that actually declares the named test.
    """
    if not value:
        return False
    path, sep, test = value.partition(":")
    if not sep or not test:
        return False
    path = path.replace("\\", "/")
    if not path.endswith(suffixes):
        return False
    root = os.path.abspath(ROOT)
    full = os.path.abspath(os.path.join(root, path))
    try:
        if os.path.commonpath([full, root]) != root:
            return False
    except ValueError:
        return False
    if not os.path.isfile(full):
        return False
    text = open(full, encoding="utf-8", errors="replace").read()
    return _declares_test(text, test, suffixes)


def validate(registry, suites):
    errors = []
    if registry.get("schema") != 1:
        errors.append("schema must be 1")
    entries = registry.get("suites") or {}
    for script in sorted(set(suites) - set(entries)):
        errors.append("unregistered suite: %s" % script)
    for script in sorted(set(entries) - set(suites)):
        errors.append("registry entry not in runner: %s" % script)
    for script in sorted(set(suites) & set(entries)):
        e = entries[script]
        if not e.get("label"):
            errors.append("%s: label missing" % script)
        cat, disp, prof = e.get("category"), e.get("disposition"), e.get("profile")
        if cat not in CATEGORIES:
            errors.append("%s: bad category %r" % (script, cat))
        if disp not in DISPOSITIONS:
            errors.append("%s: bad disposition %r" % (script, disp))
        if prof not in PROFILES:
            errors.append("%s: bad profile %r" % (script, prof))
        # Category/profile must agree except for a migrating suite: Plan A3
        # migrates an A/B suite that already has a Go/TS equivalent.  That entry
        # keeps its category and moves to profile=legacy (enforced below) until
        # the Python suite is retired, so the lane mapping does not apply.
        if disp != "MIGRATE":
            if cat == "A" and prof not in ("production", "data"):
                errors.append("%s: category A must be production or data" % script)
            if cat == "B" and prof != "data":
                errors.append("%s: category B must be data" % script)
            if cat in ("C", "D") and prof != "legacy":
                errors.append("%s: category %s must be legacy" % (script, cat))
        if disp == "KEEP" and prof == "legacy":
            errors.append("%s: KEEP cannot be legacy" % script)
        if disp == "KEEP" and not e.get("reason"):
            errors.append("%s: KEEP needs an evidence reason" % script)
        if disp == "MIGRATE":
            if prof != "legacy":
                errors.append("%s: MIGRATE must be legacy until retired" % script)
            go_eq = e.get("go_equivalent")
            ts_eq = e.get("ts_equivalent")
            if not go_eq and not ts_eq:
                errors.append("%s: MIGRATE needs go_equivalent or ts_equivalent" % script)
            if go_eq and not _equiv_exists(go_eq, GO_SUFFIXES):
                errors.append("%s: equivalence missing: %s" % (script, go_eq))
            if ts_eq and not _equiv_exists(ts_eq, TS_SUFFIXES):
                errors.append("%s: equivalence missing: %s" % (script, ts_eq))
        if disp in ("DEPRECATE", "REMOVE"):
            if not e.get("reason"):
                errors.append("%s: %s needs a reason" % (script, disp))
            if not e.get("retirement_date"):
                errors.append("%s: %s needs retirement_date" % (script, disp))
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", default=REGISTRY)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    reg = json.load(open(args.registry, encoding="utf-8"))
    suites = parse_suites()
    errors = validate(reg, suites)
    if errors:
        print("SUITE REGISTRY GUARD FAIL")
        for e in errors[:60]:
            print(" -", e)
        return 1
    print("SUITE REGISTRY GUARD OK: %d suites" % len(suites))
    return 0


def selftest():
    suites = {"a.py": {"script": "a.py", "label": "x", "kind": "SUITES"}}
    good = {"schema": 1, "suites": {"a.py": {
        "script": "a.py", "label": "x", "kind": "SUITES", "category": "A",
        "disposition": "KEEP", "profile": "production",
        "go_equivalent": None, "ts_equivalent": None,
        "reason": "contract", "retirement_date": None}}}
    cases = [("valid", good, True)]
    bad = json.loads(json.dumps(good)); bad["suites"]["a.py"]["category"] = "Z"
    cases.append(("bad category", bad, False))
    bad = json.loads(json.dumps(good)); bad["suites"]["a.py"].update(
        disposition="MIGRATE", profile="legacy")
    cases.append(("migrate without equivalence", bad, False))
    bad = json.loads(json.dumps(good)); bad["suites"]["a.py"].update(
        disposition="REMOVE", profile="legacy", reason="", retirement_date="2026-11-10")
    cases.append(("remove without reason", bad, False))
    ok_all = True
    for name, reg, want_ok in cases:
        got_ok = not validate(reg, suites)
        ok = got_ok == want_ok
        print(("ok  " if ok else "FAIL") + " selftest: " + name)
        ok_all = ok_all and ok
    print("SELFTEST OK" if ok_all else "SELFTEST FAIL")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
