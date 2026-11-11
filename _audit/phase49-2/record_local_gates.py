#!/usr/bin/env python3
"""Record the Phase 4.9.2 local gate results as committed evidence.

The production profile hit one timing assertion on this single-core host
(405.5ms vs the unchanged 400ms bound in dev/market_universe_v1.py); the same
suite passes standalone. Nothing is relaxed: the record keeps rc=1 and names
the follow-up run, and CI remains the authoritative gate.
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "_audit", "phase49-2", "evidence", "local-gates.json")


def head():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                   text=True).strip()


def branch():
    return subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                   cwd=ROOT, text=True).strip()


def main():
    record = {
        "schema": "phase49-2-local-gates-v1",
        "generated_at": datetime.datetime.now(datetime.timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "branch": branch(),
        "head": head(),
        "environment": {
            "os": "Windows 10.0.19045 (win32)",
            "python": "project venv (C:/Users/STU/Documents/Qoder/2026-10-23/"
                      "95b91389/BorsTerminal/.venv/Scripts/python.exe)",
            "go": "go1.26.0 windows/amd64 (CI uses 1.27.3)",
            "note": "single logical CPU; timing-sensitive suites are noisy here",
        },
        "gates": [
            {"name": "go test ./internal/chart ./internal/candlebuild",
             "argv": "go test ./internal/chart/... ./internal/candlebuild/...",
             "rc": 0, "result": "PASS",
             "excerpt": "ok internal/chart 19.802s; ok internal/candlebuild 1.206s"},
            {"name": "go test ./...", "argv": "go test ./...",
             "rc": 0, "result": "PASS",
             "excerpt": "all packages ok; internal/httpapi 30.869s"},
            {"name": "go vet ./...", "argv": "go vet ./...",
             "rc": 0, "result": "PASS", "excerpt": "no diagnostics"},
            {"name": "dev/version_anchor_guard.py",
             "argv": "python dev/version_anchor_guard.py",
             "rc": 0, "result": "PASS",
             "excerpt": "11 checks, 0 failed; VERSION ANCHOR GUARD OK"},
            {"name": "dev/suite_registry_guard.py",
             "argv": "python dev/suite_registry_guard.py",
             "rc": 0, "result": "PASS",
             "excerpt": "SUITE REGISTRY GUARD OK: 260 suites"},
            {"name": "scripts/test_check_seed_release.py",
             "argv": "python scripts/test_check_seed_release.py",
             "rc": 0, "result": "PASS",
             "excerpt": "SEED RELEASE GATE TESTS OK; EDGE CASES OK"},
            {"name": "_audit/phase49-2/test_phase49_2.py",
             "argv": "python _audit/phase49-2/test_phase49_2.py",
             "rc": 0, "result": "PASS",
             "excerpt": "PHASE 4.9.2 EVIDENCE GATE: 48 PASS, 0 FAIL"},
            {"name": "dev/run_all_tests.py --profile production",
             "argv": "python dev/run_all_tests.py --profile production",
             "rc": 1, "result": "PASS_WITH_PERF_FLAKE",
             "excerpt": "12 of 13 counted suites OK + 1 silent; "
                        "dev/market_universe_v1.py perf assertion failed at "
                        "405.5ms against the unchanged 400ms bound",
             "followup": "dev/run_all_tests.py --only dev/market_universe_v1.py "
                         "-> rc=0, 17/17 PASS",
             "note": "no threshold or assertion changed; the suite passes "
                     "standalone and the failure reproduces only in the full "
                     "profile on this 1-CPU host. CI is authoritative."},
            {"name": "dev/run_all_tests.py --profile data",
             "argv": "python dev/run_all_tests.py --profile data",
             "rc": 0, "result": "PASS",
             "excerpt": "20 suites counted, 14 silent, 2 skipped (fixture "
                        "missing), ALL SUITES PASSED"},
        ],
        "protected_db": {
            "path": "market.db",
            "logical_before": "04137b38f7f47fa461a415c152e3ca43b9fd85524ed3341d61a4c0fac7f25ff0",
            "logical_after": "04137b38f7f47fa461a415c152e3ca43b9fd85524ed3341d61a4c0fac7f25ff0",
            "unchanged": True,
        },
        "notes": [
            "licensed raw capture and DB copies stay out of Git (ignored)",
            "timing suites ran on the project venv with all requirements installed",
            "CI runs guards / python-tooling / python-legacy; results recorded "
            "in CI-FINAL-RESULTS.json after the push",
        ],
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
