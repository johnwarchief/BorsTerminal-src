#!/usr/bin/env python3
"""Record real GitHub Actions results for one exact commit of this mission.

Why this exists next to phase49-2's fetch_ci.py: that script is bound to its own
branch/output path and derives its headline flag from the *workflow* conclusion.
python-legacy marks both of its jobs `continue-on-error: true`, so a workflow can
report `success` while every job in it failed.  This recorder takes the SHA as an
argument (so it can record the artifact commit while HEAD has moved on to the
docs-only follow-up) and keeps workflow-level and job-level success separate.

Read-only against GitHub; the only write is the committed JSON record.
"""
from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "docs", "opportunity-center", "phase49-3",
                   "CI-FINAL-RESULTS.json")
REPO = "johnwarchief/BorsTerminal-src"
BRANCH = "mission/phase49-3-coverage-expansion-2026-11-11"
EXPECTED = ["guards", "python-tooling", "python-legacy"]
# Jobs whose failure does not fail the workflow (continue-on-error in the YAML).
REPORT_ONLY = {
    "python-legacy": ["legacy Python maintenance (report-only)",
                      "legacy static JS syntax (report-only)"],
}
POLL_SECONDS = 90
TIMEOUT_SECONDS = 90 * 60


def gh(path):
    out = subprocess.run(["gh", "api", path], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8")
    if out.returncode != 0:
        sys.exit("FATAL: gh api %s failed: %s" % (path, out.stderr.strip()))
    return json.loads(out.stdout)


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def collect(sha, branch):
    runs = []
    started = time.time()
    while time.time() - started < TIMEOUT_SECONDS:
        data = gh("/repos/%s/actions/runs?per_page=50&branch=%s"
                  % (REPO, branch.replace("/", "%2F")))
        mine = [r for r in data.get("workflow_runs", [])
                if r.get("head_sha") == sha and r.get("name") in EXPECTED]
        # Keep the newest run per workflow name (a re-run supersedes).
        newest = {}
        for r in mine:
            prev = newest.get(r["name"])
            if prev is None or r["run_number"] > prev["run_number"]:
                newest[r["name"]] = r
        mine = list(newest.values())
        done = all(r.get("status") == "completed" for r in mine)
        print("%s sha=%s mine=%d/%d %s" % (
            now(), sha[:8], len(mine), len(EXPECTED),
            " ".join("%s=%s" % (r["name"], r.get("conclusion") or r.get("status"))
                     for r in sorted(mine, key=lambda x: x["name"]))), flush=True)
        if len(mine) == len(EXPECTED) and done:
            runs = mine
            break
        time.sleep(POLL_SECONDS)
    else:
        print("TIMEOUT waiting for %s on %s" % (EXPECTED, sha))
        return None
    return runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sha", required=True)
    ap.add_argument("--branch", default=BRANCH)
    ap.add_argument("--no-wait", action="store_true",
                    help="record whatever is completed now; do not poll")
    args = ap.parse_args()
    sha = args.sha.strip()
    if len(sha) != 40:
        sys.exit("FATAL: --sha must be a full 40-character commit SHA")

    if args.no_wait:
        data = gh("/repos/%s/actions/runs?per_page=50&branch=%s"
                  % (REPO, args.branch.replace("/", "%2F")))
        runs = [r for r in data.get("workflow_runs", [])
                if r.get("head_sha") == sha and r.get("name") in EXPECTED]
    else:
        runs = collect(sha, args.branch)
    if runs is None:
        return 2

    record = {
        "schema": "phase49-3-ci-final-results-v1",
        "mission": "Phase 4.9.3 coverage expansion",
        "commit_sha": sha,
        "branch": args.branch,
        "repository": REPO,
        "base_commit": "e09ccd95d51c94082640cda75ef3de2b2008f9d2",
        "expected_workflows": EXPECTED,
        "fetched_at": now(),
        "runs": [],
    }
    missing = sorted(set(EXPECTED) - {r["name"] for r in runs})
    record["missing_workflows"] = missing
    wf_ok = True
    job_ok = True
    blocking_job_ok = True
    report_only_failures = []
    for name in EXPECTED:
        run = next((r for r in runs if r["name"] == name), None)
        if run is None:
            wf_ok = job_ok = blocking_job_ok = False
            continue
        jobs = gh("/repos/%s/actions/runs/%d/jobs?per_page=100"
                  % (REPO, run["id"]))["jobs"]
        jl = []
        for j in jobs:
            ro = j["name"] in REPORT_ONLY.get(name, [])
            concl = j.get("conclusion")
            jl.append({"name": j["name"], "conclusion": concl,
                       "status": j.get("status"), "report_only": ro,
                       "details_url": j["html_url"]})
            if concl != "success":
                job_ok = False
                if ro:
                    report_only_failures.append(
                        {"workflow": name, "job": j["name"], "conclusion": concl})
                else:
                    blocking_job_ok = False
        entry = {
            "workflow": name,
            "run_id": run["id"],
            "run_number": run["run_number"],
            "url": run["html_url"],
            "workflow_conclusion": run.get("conclusion"),
            "head_sha": run.get("head_sha"),
            "jobs": jl,
            "jobs_total": len(jl),
            "jobs_success": sum(1 for j in jl if j["conclusion"] == "success"),
            "jobs_failure": sum(1 for j in jl if j["conclusion"] == "failure"),
        }
        record["runs"].append(entry)
        if run.get("conclusion") != "success":
            wf_ok = False

    record["all_workflows_success"] = wf_ok
    record["all_jobs_success"] = job_ok
    record["all_blocking_jobs_success"] = blocking_job_ok
    record["report_only_job_failures"] = report_only_failures
    record["complete"] = not missing and all(
        r.get("status") == "completed" for r in runs)
    record["status"] = ("COMPLETE" if record["complete"] else "INCOMPLETE")
    record["honesty"] = {
        "workflow_success_is_not_job_success":
            "python-legacy marks both jobs continue-on-error, so its workflow can"
            " report success while its jobs fail; all_jobs_success and"
            " all_blocking_jobs_success are reported separately and neither is"
            " inferred from the workflow conclusion",
        "sha_binding":
            "every run listed here has head_sha equal to commit_sha; CI on any"
            " other commit (including phase49-2's 3dc7318a) is never presented as"
            " CI on this commit",
        "local_data_lane":
            "the local --profile data run failed 5 suites because this host lacks"
            " fastapi and pypdfium2; a pristine base-commit control worktree"
            " produced identical counts, so the cause is environmental. CI"
            " installs requirements.txt and is the authority for that lane",
        "not_measured":
            "Stage E full LZMA extraction and any real UI screenshot remain"
            " NOT_MEASURED; no API test is called a UI test",
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print("wrote", os.path.relpath(OUT, ROOT).replace(os.sep, "/"))
    print("status=%s workflows_success=%s all_jobs_success=%s"
          " blocking_jobs_success=%s" % (record["status"], wf_ok, job_ok,
                                        blocking_job_ok))
    for e in record["runs"]:
        print(" %s workflow=%s jobs=%d ok=%d fail=%d"
              % (e["workflow"], e["workflow_conclusion"], e["jobs_total"],
                 e["jobs_success"], e["jobs_failure"]))
        for j in e["jobs"]:
            print("   %-8s %s%s" % (j["conclusion"], j["name"],
                                    "  [report-only]" if j["report_only"] else ""))
    if report_only_failures:
        print("REPORT-ONLY JOB FAILURES (not hidden by workflow success):")
        for f in report_only_failures:
            print("  %s / %s = %s" % (f["workflow"], f["job"], f["conclusion"]))
    return 0 if (record["complete"] and blocking_job_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())