#!/usr/bin/env python3
"""Record CI for one exact Phase 4.9.4 commit into the preserved evidence chain.

The collection logic is phase49-3's fetch_ci, reused unchanged: the three success
flags stay separate (python-legacy marks both jobs continue-on-error, so workflow
success is NOT all-jobs success) and every report-only failure is still compared
suite-by-suite against the same job at the pinned base commit.

Only the record's identity and prose fields are relabelled for this phase, and
the relabel is gated: every measured number must be byte-identical before and
after, so no conclusion can be edited by the relabelling step.

A file cannot contain CI results about itself, so each commit's record is kept
separately and an existing record is never overwritten.

Usage:  python _audit/phase49-4/record_ci_for_commit.py --sha <40-char commit>
Output: _audit/phase49-4/evidence/CI-<first 8>.json
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PHASE3 = os.path.join(ROOT, "_audit", "phase49-3")
sys.path.insert(0, PHASE3)

import fetch_ci  # noqa: E402  (reused unchanged; see module docstring)

BRANCH = "mission/phase49-4-runtime-parity-2026-11-12"

MEASURED_KEYS = (
    "commit_sha", "branch", "repository", "base_commit", "expected_workflows",
    "runs", "missing_workflows", "all_workflows_success", "all_jobs_success",
    "all_blocking_jobs_success", "report_only_job_failures",
    "report_only_failure_attribution", "report_only_failures_caused_by_this_mission",
    "complete", "status",
)

RELABEL = {
    "schema": "phase49-4-ci-results-v1",
    "mission": "Phase 4.9.4 runtime parity with Rahavard",
}

HONESTY = {
    "workflow_success_is_not_job_success":
        "python-legacy marks both jobs continue-on-error, so its workflow can"
        " report success while its jobs fail; all_jobs_success and"
        " all_blocking_jobs_success are reported separately and neither is"
        " inferred from the workflow conclusion",
    "sha_binding":
        "every run listed here has head_sha equal to commit_sha; CI on any other"
        " commit is never presented as CI on this commit",
    "local_legacy_python_lane":
        "the local dev/run_all_tests.py run failed 152 suites because this host's"
        " Python 3.15.2 lacks fastapi/numpy/pandas/uvicorn/openpyxl/jdatetime and"
        " frontend/node_modules is absent; a detached clean control worktree at"
        " HEAD produced 261/261 identical per-suite results, so the cause is"
        " environmental. CI installs requirements.txt and is the authority for"
        " that lane (see evidence/GUARD-CONTROL.json)",
    "legacy_lane_attribution":
        "each report-only failure is compared suite-by-suite against the same job"
        " at the base commit; a failure is attributed to this mission only if its"
        " failed-suite set gains a name. Suite names contain commas, so the"
        " runner's FAILED summary is never comma-split; per-suite lines are parsed"
        " and the summary is rebuilt from them to prove completeness",
    "not_measured":
        "no real UI screenshot and no canvas pixel measurement exist for this"
        " phase; every parity layer is an API or transform measurement and is"
        " never called a UI test",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sha", required=True)
    ap.add_argument("--branch", default=BRANCH)
    ap.add_argument("--no-wait", action="store_true")
    args = ap.parse_args()
    sha = args.sha.strip()
    if len(sha) != 40:
        sys.exit("FATAL: --sha must be a full 40-character commit SHA")
    out = os.path.join(HERE, "evidence", "CI-%s.json" % sha[:8])
    if os.path.exists(out):
        sys.exit("FATAL: %s already exists; preserved CI records are never"
                 " overwritten" % out)

    fetch_ci.OUT = out
    sys.argv = ["fetch_ci.py", "--sha", sha, "--branch", args.branch]
    if args.no_wait:
        sys.argv.append("--no-wait")
    rc = fetch_ci.main()

    with io.open(out, encoding="utf-8") as fh:
        rec = json.load(fh)
    before = {k: rec[k] for k in MEASURED_KEYS}
    rec.update(RELABEL)
    rec["honesty"] = HONESTY
    rec["collection_logic"] = {
        "reused_from": "_audit/phase49-3/fetch_ci.py",
        "reused_unchanged": True,
        "relabelling_limited_to": "schema, mission and honesty prose only",
    }
    after = {k: rec[k] for k in MEASURED_KEYS}
    if json.dumps(before, sort_keys=True) != json.dumps(after, sort_keys=True):
        sys.exit("FATAL: relabelling changed a measured field")
    with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print("RECORDED=%s rc=%d measured_fields_unchanged=True"
          % (os.path.relpath(out, ROOT).replace(os.sep, "/"), rc))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())