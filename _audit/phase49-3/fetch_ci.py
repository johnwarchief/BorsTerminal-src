#!/usr/bin/env python3
"""Record real GitHub Actions results for one exact commit of this mission.

Why this exists next to phase49-2's fetch_ci.py: that script is bound to its own
branch/output path and derives its headline flag from the *workflow* conclusion.
python-legacy marks both of its jobs `continue-on-error: true`, so a workflow can
report `success` while every job in it failed.  This recorder takes the SHA as an
argument (so it can record the artifact commit while HEAD has moved on to the
docs-only follow-up) and keeps workflow-level and job-level success separate.
It also compares every report-only failure suite-by-suite against the base
commit, so a pre-existing legacy failure is never blamed on this mission and a
newly broken suite is never hidden inside a green workflow.

Read-only against GitHub; the only write is the committed JSON record.
"""
from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "docs", "opportunity-center", "phase49-3",
                   "CI-FINAL-RESULTS.json")
REPO = "johnwarchief/BorsTerminal-src"
BRANCH = "mission/phase49-3-coverage-expansion-2026-11-11"
BASE_COMMIT = "e09ccd95d51c94082640cda75ef3de2b2008f9d2"
BASE_BRANCH = "mission/phase49-full-verification-python-ci-2026-11-10"
EXPECTED = ["guards", "python-tooling", "python-legacy"]
# Jobs whose failure does not fail the workflow (continue-on-error in the YAML).
REPORT_ONLY = {
    "python-legacy": ["legacy Python maintenance (report-only)",
                      "legacy static JS syntax (report-only)"],
}
POLL_SECONDS = 90
TIMEOUT_SECONDS = 90 * 60
SUITE_LINE = re.compile(r"\s(OK|FAIL)\s+(.*?)\s+rc=(-?\d+)\s*\|")


def gh(path):
    out = subprocess.run(["gh", "api", path], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8")
    if out.returncode != 0:
        sys.exit("FATAL: gh api %s failed: %s" % (path, out.stderr.strip()))
    return json.loads(out.stdout)


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def suite_results(job_id):
    """Per-suite OK/FAIL names from one job's failed-step log.

    Suite names themselves contain commas, so the runner's "FAILED: a, b"
    summary cannot be split on commas (that yields 46 fragments for 30 suites).
    The per-suite lines are authoritative; the summary is rebuilt from them and
    compared, which is what proves the parse saw every suite.
    """
    proc = subprocess.run(["gh", "run", "view", "--job", str(job_id),
                           "--log-failed"], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        return None
    ok, bad, summary = [], [], None
    for line in proc.stdout.splitlines():
        m = SUITE_LINE.search(line)
        if m:
            (ok if m.group(1) == "OK" else bad).append(m.group(2).strip())
        i = line.find("FAILED: ")
        if i >= 0:
            summary = line[i + 8:].strip()
    return {
        "suites_total": len(ok) + len(bad),
        "suites_ok": len(ok),
        "suites_failed": len(bad),
        "failed_names": sorted(bad),
        "parse_complete": summary == ", ".join(bad),
    }


def base_comparison(failures, runs):
    """Compare each report-only failure against the same job at the base commit.

    A report-only failure is only attributable to this mission if its failed-suite
    set differs from the base commit's.  Read-only against GitHub.
    """
    out = []
    base_runs = gh("/repos/%s/actions/runs?per_page=50&branch=%s"
                   % (REPO, BASE_BRANCH.replace("/", "%2F"))).get("workflow_runs", [])
    for f in failures:
        entry = {"workflow": f["workflow"], "job": f["job"],
                 "base_commit": BASE_COMMIT}
        run = next((r for r in base_runs
                    if r.get("head_sha") == BASE_COMMIT
                    and r.get("name") == f["workflow"]), None)
        if run is None:
            entry["status"] = "NOT_MEASURED"
            entry["why"] = "no base-commit run for this workflow in the API window"
            out.append(entry)
            continue
        jobs = gh("/repos/%s/actions/runs/%d/jobs?per_page=100"
                  % (REPO, run["id"]))["jobs"]
        bj = next((j for j in jobs if j["name"] == f["job"]), None)
        mine_run = next(r for r in runs if r["name"] == f["workflow"])
        mj = next(j for j in gh("/repos/%s/actions/runs/%d/jobs?per_page=100"
                                % (REPO, mine_run["id"]))["jobs"]
                  if j["name"] == f["job"])
        if bj is None or bj.get("conclusion") != "failure":
            entry["status"] = "NEW_AT_THIS_COMMIT"
            entry["base_job_conclusion"] = None if bj is None else bj.get("conclusion")
            entry["new_failures"] = []
            out.append(entry)
            continue
        a, b = suite_results(mj["id"]), suite_results(bj["id"])
        if a is None or b is None:
            entry["status"] = "NOT_MEASURED"
            entry["why"] = "failed-step log unavailable for one of the two jobs"
            out.append(entry)
            continue
        new = sorted(set(a["failed_names"]) - set(b["failed_names"]))
        gone = sorted(set(b["failed_names"]) - set(a["failed_names"]))
        entry.update({
            "status": "MEASURED",
            "base_run_id": run["id"], "base_job_id": bj["id"],
            "base_job_url": bj["html_url"],
            "this_job_id": mj["id"], "this_job_url": mj["html_url"],
            "this_commit_counts": {k: a[k] for k in
                                   ("suites_total", "suites_ok", "suites_failed")},
            "base_commit_counts": {k: b[k] for k in
                                   ("suites_total", "suites_ok", "suites_failed")},
            "parse_complete_both": a["parse_complete"] and b["parse_complete"],
            "failed_sets_identical": a["failed_names"] == b["failed_names"],
            "new_failures": new, "resolved_failures": gone,
            "caused_by_this_mission": bool(new),
        })
        out.append(entry)
    return out


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
        "base_commit": BASE_COMMIT,
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
    record["report_only_failure_attribution"] = base_comparison(
        report_only_failures, runs) if report_only_failures else []
    new_failures = [e for e in record["report_only_failure_attribution"]
                    if e.get("caused_by_this_mission")
                    or e.get("status") == "NEW_AT_THIS_COMMIT"]
    record["report_only_failures_caused_by_this_mission"] = len(new_failures)
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
        "legacy_lane_attribution":
            "each report-only failure is compared suite-by-suite against the same"
            " job at the base commit; a failure is attributed to this mission only"
            " if its failed-suite set gains a name. Suite names contain commas, so"
            " the runner's FAILED summary is never comma-split; per-suite lines are"
            " parsed and the summary is rebuilt from them to prove completeness",
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
    for e in record["report_only_failure_attribution"]:
        if e["status"] != "MEASURED":
            print("  attribution %s: %s (%s)"
                  % (e["job"], e["status"], e.get("why", "")))
            continue
        print("  attribution %s: this=%d/%d failed base=%d/%d failed"
              " identical=%s new=%d resolved=%d parse_complete=%s"
              % (e["job"], e["this_commit_counts"]["suites_failed"],
                 e["this_commit_counts"]["suites_total"],
                 e["base_commit_counts"]["suites_failed"],
                 e["base_commit_counts"]["suites_total"],
                 e["failed_sets_identical"], len(e["new_failures"]),
                 len(e["resolved_failures"]), e["parse_complete_both"]))
    if new_failures:
        print("FATAL: a report-only failure gained suites at this commit;"
              " it is attributable to this mission")
    return 0 if (record["complete"] and blocking_job_ok and not new_failures) else 1


if __name__ == "__main__":
    raise SystemExit(main())