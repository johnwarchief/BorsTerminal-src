#!/usr/bin/env python3
"""Poll GitHub Actions for the mission commit and record CI-FINAL-RESULTS.json.

Unauthenticated public-repo API: one runs request per poll plus one jobs
request per expected workflow. The script exits 0 only when all expected
workflows (guards, python-tooling, python-legacy) completed successfully for
the exact HEAD commit it was started with.
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "docs", "opportunity-center", "phase49-2",
                   "CI-FINAL-RESULTS.json")
REPO = "johnwarchief/BorsTerminal-src"
BRANCH = "mission/phase49-full-verification-python-ci-2026-11-10"
EXPECTED = ["guards", "python-tooling", "python-legacy"]
POLL_SECONDS = 120
TIMEOUT_SECONDS = 75 * 60


def get(path):
    req = urllib.request.Request(
        "https://api.github.com" + path,
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": "borsterminal-phase49-2-ci"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def head_sha():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                   text=True).strip()


def main():
    head = head_sha()
    started = time.time()
    runs = []
    while time.time() - started < TIMEOUT_SECONDS:
        data = get("/repos/%s/actions/runs?per_page=30&branch=%s"
                   % (REPO, urllib.parse.quote(BRANCH, safe="")))
        mine = [r for r in data.get("workflow_runs", [])
                if r.get("head_sha") == head and r.get("name") in EXPECTED]
        names = {r["name"] for r in mine}
        done = all(r.get("status") == "completed" for r in mine)
        print("%s mine=%d/%d %s" % (
            datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%SZ"),
            len(names), len(EXPECTED),
            " ".join("%s=%s" % (r["name"], r.get("conclusion") or r.get("status"))
                     for r in mine)), flush=True)
        if len(names) == len(EXPECTED) and done:
            runs = mine
            break
        time.sleep(POLL_SECONDS)
    else:
        print("TIMEOUT waiting for %s on %s" % (EXPECTED, head))
        return 2

    record = {
        "commit_sha": head,
        "branch": BRANCH,
        "repository": REPO,
        "status": "COMPLETE",
        "expected_workflows": EXPECTED,
        "fetched_at": datetime.datetime.now(datetime.timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runs": [],
    }
    ok = True
    for name in EXPECTED:
        run = next(r for r in runs if r["name"] == name)
        jobs = get("/repos/%s/actions/runs/%d/jobs?per_page=100"
                   % (REPO, run["id"]))["jobs"]
        entry = {
            "workflow": name,
            "run_id": run["id"],
            "url": run["html_url"],
            "conclusion": run.get("conclusion"),
            "jobs": [{"name": j["name"], "conclusion": j.get("conclusion"),
                      "details_url": j["html_url"]} for j in jobs],
        }
        record["runs"].append(entry)
        if run.get("conclusion") != "success":
            ok = False
    record["all_expected_success"] = ok
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print("wrote", OUT, "all_success=%s" % ok)
    for entry in record["runs"]:
        print(entry["workflow"], entry["conclusion"],
              "jobs=%d" % len(entry["jobs"]))
        for job in entry["jobs"]:
            print(" ", job["conclusion"], job["name"])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
