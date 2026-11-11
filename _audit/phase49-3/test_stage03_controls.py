#!/usr/bin/env python3
"""Negative controls for stage03_cohort_evidence.

A gate that cannot fail is not a gate. These three controls prove the stage's
assertions actually bite:

A. the standard identity key reproduces the accepted pipeline's step counts;
B. removing the alias join (raw-spelling key) MUST abort -- six cohort symbols
   carry steps under a second spelling, so a raw-symbol join silently loses them;
C. a broken input SHA pin MUST abort before any output is written.

Run: PYTHONIOENCODING=utf-8 python _audit/phase49-3/test_stage03_controls.py
Writes only to a temporary directory, removed on exit. No repo file is touched.
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "dev"))

from symbol_identity import key as standard_key  # noqa: E402


def _load():
    spec = importlib.util.spec_from_file_location(
        "s3", os.path.join(HERE, "stage03_cohort_evidence.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    m = _load()
    tmp = tempfile.mkdtemp(prefix="phase49-3-controls-")
    results = {}
    try:
        def run(tag):
            paths = [os.path.join(tmp, tag + s)
                     for s in (".json", ".csv", "_plan.json", "_man.json")]
            return m.build(*paths), paths

        results["A_standard_key"], _ = run("ok")

        m.key = lambda s: s
        results["B_raw_spelling_key"], bad_paths = run("bad")
        # B must abort before writing anything.
        results["B_wrote_no_output"] = not any(
            os.path.exists(p) for p in bad_paths)

        m.key = standard_key
        m.EXPECTED_SHA = dict(m.EXPECTED_SHA)
        m.EXPECTED_SHA[m.STEPS] = "0" * 64
        results["C_broken_sha_pin"], sha_paths = run("sha")
        results["C_wrote_no_output"] = not any(
            os.path.exists(p) for p in sha_paths)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    expect = {"A_standard_key": 0, "B_raw_spelling_key": 2,
              "B_wrote_no_output": True, "C_broken_sha_pin": 2,
              "C_wrote_no_output": True}
    ok = all(results.get(k) == v for k, v in expect.items())
    print(json.dumps({"controls": results, "expected": expect,
                      "verdict": "PASS" if ok else "FAIL"},
                     ensure_ascii=False, indent=1, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())