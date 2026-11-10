#!/usr/bin/env python3
import json
import os
import shutil
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


def check_derived_rebinding():
    """run_all_tests.py re-binds SUITES after lane filtering; the parser must
    read only the literal lists and never crash on the derived assignment."""
    src = ("SUITES = [('a.py', 'x')]\n"
           "JS_SUITES = []\n"
           "SUITES = [(s, l) for s, l in SUITES if s]\n")
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(src)
        tmp = fh.name
    try:
        got = G.parse_suites(tmp)
    finally:
        os.unlink(tmp)
    assert list(got) == ["a.py"], got
    print("ok  ", "derived SUITES re-binding is ignored")


def main():
    assert len(G.parse_suites()) >= 250, "runner must expose >=250 suites"
    check_derived_rebinding()
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
    run_case("migrate needs a TestName symbol",
             base_entry(disposition="MIGRATE", profile="legacy",
                        go_equivalent="backend-go/internal/pricebasis/pricebasis_test.go"),
             False)
    run_case("go_equivalent must be a .go file",
             base_entry(disposition="MIGRATE", profile="legacy",
                        go_equivalent="dev/run_all_tests.py:TestReal"),
             False)
    run_case("ts_equivalent must be a .ts/.tsx file",
             base_entry(disposition="MIGRATE", profile="legacy",
                        ts_equivalent="dev/run_all_tests.py:TestReal"),
             False)
    # A genuine .go test file outside the repo: containment must reject it even
    # though the file exists and declares the test.  The old case pointed at
    # ../outside_test.go, which never existed, so only the isfile check ran and
    # containment was never exercised.
    outside = tempfile.mkdtemp(dir=os.path.dirname(G.ROOT))
    try:
        p = os.path.join(outside, "outside_test.go")
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("package x\nfunc TestReal(t *testing.T) {}\n")
        rel = os.path.relpath(p, G.ROOT).replace("\\", "/")
        assert rel.startswith("../"), rel
        run_case("equivalence must stay inside the repo",
                 base_entry(disposition="MIGRATE", profile="legacy",
                            go_equivalent=rel + ":TestReal"),
                 False)
    finally:
        shutil.rmtree(outside, ignore_errors=True)
    run_case("equivalence must name an existing test function",
             base_entry(disposition="MIGRATE", profile="legacy",
                        go_equivalent="backend-go/internal/pricebasis/pricebasis_test.go:TestNotThere"),
             False)
    run_case("remove needs reason",
             base_entry(disposition="REMOVE", profile="legacy", reason="",
                        retirement_date="2026-11-10"), False)
    run_case("remove needs date",
             base_entry(disposition="REMOVE", profile="legacy", reason="obsolete",
                        retirement_date=None), False)
    # A real equivalence file must live inside the repo: the temp file is
    # created under backend-go/ (and removed again) so the containment check
    # is exercised with a genuine .go file, not a repo-relative lie.
    tmpdir = tempfile.mkdtemp(dir=os.path.join(G.ROOT, "backend-go", "internal"))
    try:
        p = os.path.join(tmpdir, "equiv_test.go")
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("package x\nfunc TestReal(t *testing.T) {}\n")
        rel = os.path.relpath(p, G.ROOT).replace("\\", "/")
        run_case("migrate with real test",
                 base_entry(disposition="MIGRATE", profile="legacy",
                            go_equivalent=rel + ":TestReal"), True)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("package x\n")
        run_case("known file but absent TestName",
                 base_entry(disposition="MIGRATE", profile="legacy",
                            go_equivalent=rel + ":TestReal"), False)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("package x\n// func TestReal(t *testing.T) {} lives elsewhere\n")
        run_case("TestName only in a comment",
                 base_entry(disposition="MIGRATE", profile="legacy",
                            go_equivalent=rel + ":TestReal"), False)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    print("SUITE REGISTRY TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
