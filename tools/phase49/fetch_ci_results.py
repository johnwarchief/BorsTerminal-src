#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Record the final GitHub Actions evidence for the mission HEAD (Task A9).

Two read-only `gh` queries and one JSON file:

  gh run list --commit <sha> ...     every run for the commit, all workflows
  gh run view <id> --json jobs ...   the per-job conclusion and its log link

The file is docs/opportunity-center/phase49/CI-FINAL-RESULTS.json (override with
--out).  Every run whose headSha is the requested commit is recorded, including
several runs of the same workflow (push and pull_request) - the evidence is not
reduced to one run per workflow.  A run that has not finished is written with
"status": "incomplete" instead of being dropped.

The collector is deliberately loud rather than helpful when the evidence is not
complete:

  0  every run for the commit is completed; the file records all of them
  2  `gh` is missing, unauthenticated, or a query failed (nothing is written)
  3  no workflow run exists for the commit (nothing is written; an empty
     evidence file would be a fabricated result)
  4  the file was written, but at least one run is still in progress; rerun
     after CI finishes - an incomplete record is never final evidence

`--self-test` exercises the SHA filter, the JSON shaping and the exit-code
verdict against fixtures, so this tool can be verified on a machine without
`gh` (as on the authoring machine) and never touches the network.  The module is
stdlib-only, read-only outside --out, and reads no secret: `gh` owns the token.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_OUT = os.path.join(
    ROOT, "docs", "opportunity-center", "phase49", "CI-FINAL-RESULTS.json")

RUN_FIELDS = ",".join([
    "databaseId", "headSha", "headBranch", "workflowName", "name",
    "status", "conclusion", "url", "event", "createdAt",
])
VIEW_FIELDS = "status,conclusion,headSha,url,workflowName,jobs"

MISSING_GH = (
    "`gh` (GitHub CLI) is not installed or not on PATH; install it, run "
    "`gh auth login`, then rerun this tool"
)


class GhError(RuntimeError):
    """A condition that must stop the collector, never degrade it silently."""


def _last_line(proc):
    text = (proc.stderr or proc.stdout or "").strip()
    return text.splitlines()[-1] if text else "no output"


def _invoke(arguments, runner=None):
    """Run `gh <arguments>` and return the process; only an absent binary raises."""
    if runner is None:
        exe = shutil.which("gh")
        if exe is None:
            raise GhError(MISSING_GH)
        runner = subprocess.run
    else:
        exe = "gh"
    try:
        return runner(
            [exe] + list(arguments),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
    except FileNotFoundError:
        raise GhError(MISSING_GH)
    except OSError as exc:
        raise GhError("cannot execute `gh`: %s" % exc)


def run_gh(arguments, runner=None):
    """Run a `gh` query that must exit zero, or raise with its last output line."""
    proc = _invoke(arguments, runner)
    if proc.returncode != 0:
        raise GhError("gh %s failed (exit %d): %s" % (
            " ".join(arguments[:2]), proc.returncode, _last_line(proc)))
    return proc


def gh_json(arguments, runner=None):
    """Run a `gh --json` query and return the parsed payload."""
    proc = run_gh(arguments, runner)
    try:
        return json.loads(proc.stdout or "null")
    except ValueError:
        raise GhError("gh %s returned non-JSON output: %s" % (
            " ".join(arguments[:2]), (proc.stdout or "")[:200]))


def require_auth(runner=None):
    """`gh auth status` exiting zero is the only proof of a usable login."""
    proc = _invoke(["auth", "status"], runner)
    if proc.returncode != 0:
        raise GhError("`gh` is not authenticated (%s); run `gh auth login`" % _last_line(proc))


def resolve_sha(sha):
    """Expand HEAD or a short SHA through git; pass a full SHA through untouched."""
    value = (sha or "").strip()
    if not value:
        raise GhError("--sha is empty")
    if len(value) in (40, 64) and all(c in "0123456789abcdefABCDEF" for c in value):
        return value.lower()
    proc = subprocess.run(
        ["git", "-C", ROOT, "rev-parse", value],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise GhError("cannot resolve %r to a commit: %s" % (
            value, detail[0] if detail else "no output"))
    return proc.stdout.strip().lower()


def shape(sha, runs, jobs_for, repo=None, branch=None, fetched_at=None):
    """Turn raw `gh` payloads into the evidence document.

    `jobs_for(run_id)` supplies the per-job rows, so --self-test can drive this
    function with fixtures.  Runs of another commit are dropped (gh is asked for
    one commit, the filter makes the guarantee local), runs are ordered by
    workflow then run id so the committed file is stable, and a run whose status
    is not `completed` is kept with status `incomplete`.
    """
    wanted = sha.lower()
    selected = [
        r for r in runs
        if str(r.get("headSha") or "").lower() == wanted
        and (not branch or r.get("headBranch") == branch)
    ]
    selected.sort(key=lambda r: (
        str(r.get("workflowName") or ""), int(r.get("databaseId") or 0)))

    out_runs = []
    for r in selected:
        gh_status = str(r.get("status") or "unknown")
        completed = gh_status == "completed"
        out_runs.append({
            "workflow": r.get("workflowName"),
            "run_id": r.get("databaseId"),
            "url": r.get("url"),
            "event": r.get("event"),
            "status": "completed" if completed else "incomplete",
            "gh_status": gh_status,
            "conclusion": r.get("conclusion") if completed else None,
            "jobs": jobs_for(r.get("databaseId")),
        })

    payload = {
        "commit_sha": sha.lower(),
        "repo": repo,
        "branch": branch,
        "fetched_at_utc": fetched_at or datetime.datetime.now(
            datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runs": out_runs,
    }
    payload["summary"] = summarize(payload)
    return payload


def summarize(payload):
    runs = payload["runs"]
    conclusions = {}
    for r in runs:
        key = r["conclusion"] if r["status"] == "completed" else "incomplete"
        conclusions[key] = conclusions.get(key, 0) + 1
    return {
        "runs": len(runs),
        "completed": sum(1 for r in runs if r["status"] == "completed"),
        "incomplete": sum(1 for r in runs if r["status"] != "completed"),
        "conclusions": conclusions,
    }


def verdict(payload):
    """(exit code, message) for a shaped payload: 0 final, 3 absent, 4 partial."""
    sha = payload["commit_sha"]
    if not payload["runs"]:
        return 3, (
            "no workflow run exists for commit %s; push the commit and let CI "
            "start before recording evidence" % sha)
    pending = [r for r in payload["runs"] if r["status"] != "completed"]
    if pending:
        names = ", ".join("%s#%s (%s)" % (r["workflow"], r["run_id"], r["gh_status"])
                          for r in pending)
        return 4, ("%d of %d run(s) for %s are not completed: %s; rerun this "
                   "tool after CI finishes" % (len(pending), len(payload["runs"]), sha, names))
    failed = [r for r in payload["runs"] if r["conclusion"] != "success"]
    if failed:
        names = ", ".join("%s#%s (%s)" % (r["workflow"], r["run_id"], r["conclusion"])
                          for r in failed)
        return 0, ("all %d run(s) completed for %s; not all green (report-only "
                   "lanes are expected to fail here): %s" % (
                       len(payload["runs"]), sha, names))
    return 0, "all %d run(s) completed successfully for %s" % (
        len(payload["runs"]), sha)


def collect(sha, repo=None, branch=None, limit=60, runner=None):
    """Query `gh` for every run of the commit and return the evidence document."""
    require_auth(runner)
    scope = ["--repo", repo] if repo else []
    runs = gh_json(
        ["run", "list", "--commit", sha, "--limit", str(limit),
         "--json", RUN_FIELDS] + scope,
        runner,
    )
    if not isinstance(runs, list):
        raise GhError("gh run list did not return a list for commit %s" % sha)

    def jobs_for(run_id):
        view = gh_json(
            ["run", "view", str(run_id), "--json", VIEW_FIELDS] + scope, runner)
        jobs = view.get("jobs") or []
        return [{
            "name": j.get("name"),
            "conclusion": j.get("conclusion"),
            "details_url": j.get("html_url"),
        } for j in jobs]

    return shape(sha, runs, jobs_for, repo=repo, branch=branch)


def write_evidence(payload, path):
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


# ---------------------------------------------------------------- self-test --

class _Proc(object):
    def __init__(self, code, out="", err=""):
        self.returncode = code
        self.stdout = out
        self.stderr = err


def _self_test_fixtures(sha):
    other = "b" * 40
    runs = [
        {"databaseId": 105, "headSha": sha, "headBranch": "mission/x",
         "workflowName": "guards", "name": "guards", "status": "completed",
         "conclusion": "success", "url": "https://example.test/105",
         "event": "pull_request", "createdAt": "2026-11-10T00:00:00Z"},
        {"databaseId": 103, "headSha": sha, "headBranch": "mission/x",
         "workflowName": "python-tooling", "name": "python-tooling",
         "status": "in_progress", "conclusion": None,
         "url": "https://example.test/103", "event": "push",
         "createdAt": "2026-11-10T00:00:00Z"},
        {"databaseId": 102, "headSha": sha, "headBranch": "mission/x",
         "workflowName": "python-legacy", "name": "python-legacy",
         "status": "completed", "conclusion": "failure",
         "url": "https://example.test/102", "event": "push",
         "createdAt": "2026-11-10T00:00:00Z"},
        {"databaseId": 101, "headSha": sha, "headBranch": "mission/x",
         "workflowName": "guards", "name": "guards", "status": "completed",
         "conclusion": "success", "url": "https://example.test/101",
         "event": "push", "createdAt": "2026-11-10T00:00:00Z"},
        {"databaseId": 104, "headSha": other, "headBranch": "main",
         "workflowName": "guards", "name": "guards", "status": "completed",
         "conclusion": "success", "url": "https://example.test/104",
         "event": "push", "createdAt": "2026-11-09T00:00:00Z"},
    ]
    views = {
        101: {"status": "completed", "conclusion": "success", "headSha": sha,
              "url": "https://example.test/101", "workflowName": "guards",
              "jobs": [{"name": "go backend", "conclusion": "success",
                        "html_url": "https://example.test/101/job/1"}]},
        102: {"status": "completed", "conclusion": "failure", "headSha": sha,
              "url": "https://example.test/102", "workflowName": "python-legacy",
              "jobs": [{"name": "legacy maintenance (report-only)",
                        "conclusion": "failure",
                        "html_url": "https://example.test/102/job/1"}]},
        103: {"status": "in_progress", "conclusion": None, "headSha": sha,
              "url": "https://example.test/103", "workflowName": "python-tooling",
              "jobs": []},
        105: {"status": "completed", "conclusion": "success", "headSha": sha,
              "url": "https://example.test/105", "workflowName": "guards",
              "jobs": [{"name": "repo-hygiene", "conclusion": "success",
                        "html_url": "https://example.test/105/job/1"}]},
    }
    return runs, views


def self_test():
    checks = []

    def check(label, ok):
        checks.append(label)
        if not ok:
            raise SystemExit("FETCH CI RESULTS SELF-TEST FAIL: %s" % label)

    sha = "a" * 40
    runs, views = _self_test_fixtures(sha)

    def fixture_runner(argv, **kwargs):
        if argv[0] != "gh":
            raise AssertionError("self-test runner got %r" % (argv,))
        args = argv[1:]
        if args[:2] == ["auth", "status"]:
            return _Proc(0, "Logged in to github.com account test\n")
        if args[:2] == ["run", "list"]:
            if "--commit" not in args or args[args.index("--commit") + 1] != sha:
                raise AssertionError("run list must be scoped to the commit")
            return _Proc(0, json.dumps(runs))
        if args[:2] == ["run", "view"]:
            run_id = int(args[2])
            return _Proc(0, json.dumps(views[run_id]))
        raise AssertionError("unexpected gh call: %r" % (argv,))

    payload = collect(sha, runner=fixture_runner)
    by_id = dict((r["run_id"], r) for r in payload["runs"])

    check("commit_sha is recorded", payload["commit_sha"] == sha)
    check("runs of another commit are dropped", 104 not in by_id)
    check("every run of the commit is kept (4)", sorted(by_id) == [101, 102, 103, 105])
    check("two runs of one workflow both survive",
          [r["run_id"] for r in payload["runs"] if r["workflow"] == "guards"] == [101, 105])
    check("runs are ordered by workflow then run id",
          [(r["workflow"], r["run_id"]) for r in payload["runs"]] ==
          [("guards", 101), ("guards", 105), ("python-legacy", 102),
           ("python-tooling", 103)])
    check("incomplete run is explicit, not dropped",
          by_id[103]["status"] == "incomplete"
          and by_id[103]["gh_status"] == "in_progress"
          and by_id[103]["conclusion"] is None)
    check("completed failure keeps its conclusion",
          by_id[102]["status"] == "completed" and by_id[102]["conclusion"] == "failure")
    check("job rows carry name/conclusion/details_url",
          by_id[101]["jobs"] == [{
              "name": "go backend", "conclusion": "success",
              "details_url": "https://example.test/101/job/1"}])
    check("summary counts the incomplete run",
          payload["summary"] == {"runs": 4, "completed": 3, "incomplete": 1,
                                 "conclusions": {"success": 2, "failure": 1,
                                                 "incomplete": 1}})
    check("verdict flags the incomplete run as exit 4", verdict(payload)[0] == 4)

    complete = shape(sha, [r for r in runs if r["databaseId"] != 103],
                     lambda rid: [], repo=None)
    code, message = verdict(complete)
    check("verdict is exit 0 when every run is completed", code == 0)
    check("verdict names the non-blocking failure", "python-legacy#102" in message)
    check("verdict is exit 3 when the commit has no runs",
          verdict(shape(sha, [], lambda rid: []))[0] == 3)

    scoped = shape(sha, runs, lambda rid: [], branch="mission/x")
    check("branch filter keeps the runs of that branch", len(scoped["runs"]) == 4)
    check("branch filter drops runs of another branch",
          shape(sha, runs, lambda rid: [], branch="main")["runs"] == [])

    seen = []

    def scoped_runner(argv, **kwargs):
        seen.append(list(argv[1:]))
        return fixture_runner(argv, **kwargs)

    collect(sha, repo="owner/name", runner=scoped_runner)
    check("--repo is a passthrough to gh",
          any(a[:2] == ["run", "list"] and "owner/name" in a for a in seen)
          and any(a[:2] == ["run", "view"] and "owner/name" in a for a in seen))

    def missing_runner(argv, **kwargs):
        raise FileNotFoundError(2, "No such file or directory", "gh")

    try:
        collect(sha, runner=missing_runner)
        check("missing gh raises", False)
    except GhError as exc:
        check("missing gh raises a clear error", "not installed" in str(exc))

    try:
        collect(sha, runner=lambda argv, **kw: _Proc(1, "", "HTTP 401: Bad credentials"))
        check("unauthenticated gh raises", False)
    except GhError as exc:
        check("unauthenticated gh raises a clear error", "not authenticated" in str(exc))

    try:
        collect(sha, runner=lambda argv, **kw: (
            _Proc(1, "", "boom") if argv[1:3] != ["auth", "status"]
            else _Proc(0, "ok")))
        check("failing query raises", False)
    except GhError as exc:
        check("failing query raises with the gh output", "boom" in str(exc))

    handle, path = tempfile.mkstemp(suffix=".json")
    os.close(handle)
    try:
        write_evidence(payload, path)
        raw = open(path, "rb").read()
        check("evidence file ends with one LF", raw.endswith(b"}\n") and b"\r\n" not in raw)
        check("evidence file round-trips", json.loads(raw.decode("utf-8")) == payload)
    finally:
        os.remove(path)

    check("default output is the docs evidence path",
          os.path.normpath(DEFAULT_OUT) == os.path.normpath(os.path.join(
              ROOT, "docs", "opportunity-center", "phase49", "CI-FINAL-RESULTS.json")))

    print("FETCH CI RESULTS SELF-TEST OK (%d checks)" % len(checks))
    return 0


# --------------------------------------------------------------------- main --

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Record every GitHub Actions run of one commit as final CI evidence.",
        epilog="Exit 0 = final evidence written; 2 = gh missing/unauthenticated/"
               "query failed; 3 = no run for the commit (nothing written); "
               "4 = evidence written but a run is still in progress.",
    )
    ap.add_argument("--sha", default="HEAD",
                    help="commit to record, HEAD or a SHA (default: HEAD)")
    ap.add_argument("--repo", help="owner/name; default is gh's current repository")
    ap.add_argument("--branch", help="only runs whose head branch is this (also recorded)")
    ap.add_argument("--limit", type=int, default=60,
                    help="max runs `gh run list` may return (default: 60)")
    ap.add_argument("--out", default=DEFAULT_OUT,
                    help="evidence path (default: docs/opportunity-center/phase49/"
                         "CI-FINAL-RESULTS.json)")
    ap.add_argument("--self-test", action="store_true",
                    help="verify the shaping/verdict logic on fixtures; no gh, no network")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    try:
        sha = resolve_sha(args.sha)
        payload = collect(sha, repo=args.repo, branch=args.branch, limit=args.limit)
    except GhError as exc:
        sys.stderr.write("FETCH CI RESULTS FAIL: %s\n" % exc)
        return 2

    code, message = verdict(payload)
    if code == 3:
        sys.stderr.write("FETCH CI RESULTS FAIL: %s\n" % message)
        return 3

    write_evidence(payload, os.path.abspath(args.out))
    for run in payload["runs"]:
        print("%-14s %-8s %-10s %s" % (
            run["workflow"], run["conclusion"] or "-", run["status"], run["url"]))
    print("wrote %s: %s" % (os.path.abspath(args.out), message))
    if code != 0:
        sys.stderr.write("FETCH CI RESULTS INCOMPLETE: %s\n" % message)
    return code


if __name__ == "__main__":
    sys.exit(main())
