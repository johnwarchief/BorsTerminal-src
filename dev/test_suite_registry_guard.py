#!/usr/bin/env python3
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import suite_registry_guard as G  # noqa: E402


def base_entry(**kw):
    e = {"script": "a.py", "label": "x", "kind": "SUITES", "category": "A",
         "disposition": "KEEP", "profile": "production",
         "go_equivalent": None, "ts_equivalent": None,
         "reason": "contract guard", "retirement_date": None}
    e.update(kw)
    return e


def run_case(name, entry, want_ok):
    reg = {"schema": 1, "suites": {"a.py": entry}}
    suites = {"a.py": {"script": "a.py", "label": "x", "kind": "SUITES"}}
    errors = G.validate(reg, suites)
    ok = not errors
    assert ok == want_ok, (name, errors)
    print("ok  ", name)


def main():
    assert len(G.parse_suites()) >= 250, "runner must expose >=250 suites"
    run_case("valid keep", base_entry(), True)
    run_case("missing label", base_entry(label=""), False)
    run_case("bad category", base_entry(category="Z"), False)
    run_case("A must be production",
             base_entry(profile="legacy"), False)
    run_case("migrate needs equivalent",
             base_entry(disposition="MIGRATE", profile="legacy"), False)
    run_case("migrate with missing file",
             base_entry(disposition="MIGRATE", profile="legacy",
                        go_equivalent="backend-go/internal/nope/no_test.go:TestX"),
             False)
    run_case("remove needs reason",
             base_entry(disposition="REMOVE", profile="legacy", reason="",
                        retirement_date="2026-11-10"), False)
    run_case("remove needs date",
             base_entry(disposition="REMOVE", profile="legacy", reason="obsolete",
                        retirement_date=None), False)
    with tempfile.NamedTemporaryFile("w", suffix=".go", delete=False,
                                     encoding="utf-8") as fh:
        fh.write("package x\nfunc TestReal(t *testing.T) {}\n")
        tmp = fh.name
    try:
        rel = os.path.relpath(tmp, G.ROOT).replace("\\", "/")
        run_case("migrate with real test",
                 base_entry(disposition="MIGRATE", profile="legacy",
                            go_equivalent=rel + ":TestReal"), True)
    finally:
        os.unlink(tmp)
    print("SUITE REGISTRY TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
