#!/usr/bin/env python3
"""Structural checks for the Phase 4.9 CI lane split.

Line-based on purpose: CI runs this with the bare stdlib, so no YAML parser.
Every positive check names a precise shape (a job key at two-space indent, a
`run:` command) instead of a substring, because a substring also matches a
display name or a comment and then survives the mutation it is meant to catch.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF = os.path.join(ROOT, ".github", "workflows")
JOB_KEY = re.compile(r"^  ([A-Za-z0-9_-]+):$")
RUN_KEY = "run:"


def fail(message):
    sys.stderr.write("WORKFLOW LAYOUT FAIL: %s\n" % message)
    raise SystemExit(1)


def text(name):
    path = os.path.join(WF, name)
    if not os.path.exists(path):
        fail(".github/workflows/%s is missing" % name)
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def job_keys(workflow):
    """Job ids: `  <id>:` at exactly two spaces inside the top-level jobs block.

    A key indented deeper is a property of a job, and an indented comment is
    neither; both are excluded, which is what makes the check mutation-proof.
    """
    keys = []
    in_jobs = False
    for line in workflow.splitlines():
        if line == "jobs:":
            in_jobs = True
            continue
        if not in_jobs:
            continue
        if line.startswith("#"):
            continue
        if line and not line.startswith(" "):
            break  # the next top-level key ends the jobs block
        match = JOB_KEY.match(line)
        if match:
            keys.append(match.group(1))
    return keys


def run_commands(workflow):
    """Whole commands of single-line `run:` keys, whitespace-normalised.

    Only the command text is returned, so a display name that repeats the
    command cannot satisfy a check that is about what actually executes.
    """
    commands = []
    for line in workflow.splitlines():
        stripped = line.strip()
        if stripped.startswith("- " + RUN_KEY):
            stripped = stripped[2:]
        if not stripped.startswith(RUN_KEY):
            continue
        commands.append(" ".join(stripped[len(RUN_KEY):].split()))
    return commands


def main():
    guards = text("guards.yml")
    tooling = text("python-tooling.yml")
    legacy = text("python-legacy.yml")

    # guards.yml: the production gate -------------------------------------
    guard_jobs = job_keys(guards)
    if "zero-python-runtime" not in guard_jobs:
        fail(
            "guards.yml needs a `zero-python-runtime:` job key at two-space "
            "indentation; a mention in a comment or an artifact name is not the job"
        )
    # Retired gates must be gone from the file, not merely renamed.
    if "python-guards:" in guards:
        fail("python-guards must leave the production gate")
    if "js-syntax:" in guards:
        fail("legacy static check must leave the production gate")
    if "python-tooling.yml" in guards:
        fail("the production gate must not reference the split lane files")

    # python-tooling.yml: the blocking data/research lane ------------------
    if "continue-on-error" in tooling:
        fail("python-tooling.yml is a blocking lane; continue-on-error must not appear")
    tooling_runs = run_commands(tooling)
    if "python dev/run_all_tests.py --profile data" not in tooling_runs:
        fail(
            "python-tooling.yml must run `python dev/run_all_tests.py --profile data`, "
            "not just name --profile data in a display name"
        )
    if "python dev/suite_registry_guard.py" not in tooling_runs:
        fail("python-tooling.yml must run `python dev/suite_registry_guard.py`")
    if "python dev/test_workflows_layout.py" not in tooling_runs:
        fail("python-tooling.yml must execute this test: python dev/test_workflows_layout.py")

    # python-legacy.yml: the report-only lane ------------------------------
    forgiving = [
        line.strip() for line in legacy.splitlines() if line.strip() == "continue-on-error: true"
    ]
    if len(forgiving) < 2:
        fail(
            "python-legacy.yml must mark both jobs report-only; "
            "`continue-on-error: true` appears %d time(s)" % len(forgiving)
        )
    if "python dev/run_all_tests.py --profile legacy" not in run_commands(legacy):
        fail(
            "python-legacy.yml must run `python dev/run_all_tests.py --profile legacy` "
            "in a run: line"
        )

    print("WORKFLOW LAYOUT TESTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
