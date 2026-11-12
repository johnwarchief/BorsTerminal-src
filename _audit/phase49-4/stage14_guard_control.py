#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 4.9.4 stage14: prove the local guard failures are environmental.

The local Python (3.15.2) has no fastapi/numpy/pandas/uvicorn/openpyxl/jdatetime,
so most legacy Python suites die at import. That is not a regression caused by
this phase, but "not caused by us" is an argument, not evidence. This script
compares the full guard run in the mission worktree against a full run in a
detached control worktree at HEAD with zero local changes, suite by suite.

No suite, guard or threshold is changed, skipped or weakened to make this pass.
The comparison is exact: same label set, same status, same exit code, same
reported counts. Any difference is a failure of this stage.

Usage: python _audit/phase49-4/stage14_guard_control.py
Inputs: _audit/phase49-4/logs/dev-guards.log         (mission worktree)
        _audit/phase49-4/logs/dev-guards-control.log (control worktree at HEAD)
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
LOGS = os.path.join(HERE, "logs")

ROW = re.compile(r"^  (OK|FAIL|SKIP)\s+(.*?)\s+(?:rc=(\d+)\s+\|\s+(.*)|\((.*)\))\s*$")
MODULE = re.compile(r"No module named '([A-Za-z_0-9]+)'")
FINGERPRINT = re.compile(r"PROTECTED_DB_UNCHANGED logical_total=([0-9a-f]{64})")
TOTALS = re.compile(r"^(\d+) suite counted, (\d+) silent \(exit-code only\), (\d+) skipped")


def parse(path):
    if not os.path.exists(path):
        sys.exit("FATAL: missing log %s" % path)
    with open(path, "rb") as fh:
        raw = fh.read()
    text = raw.decode("utf-8", errors="replace").replace("\r\n", "\n")
    suites = {}
    order = []
    current = None
    for line in text.splitlines():
        m = ROW.match(line)
        if m:
            status, label, rc, detail, skipwhy = m.groups()
            label = label.strip()
            if label in suites:
                sys.exit("FATAL: duplicate suite label %r in %s" % (label, path))
            suites[label] = {
                "status": status,
                "rc": int(rc) if rc is not None else None,
                "detail": (detail or skipwhy or "").strip(),
                "missing_modules": [],
            }
            order.append(label)
            current = label if status == "FAIL" else None
            continue
        if current and line.startswith("       "):
            for name in MODULE.findall(line):
                if name not in suites[current]["missing_modules"]:
                    suites[current]["missing_modules"].append(name)
    fp = FINGERPRINT.search(text)
    tot = TOTALS.search(text)
    verdict = "ALL SUITES PASSED" in text
    return {
        "log": os.path.relpath(path, ROOT).replace(os.sep, "/"),
        # The file bytes are what sha256sum reports, so that is the hash anyone
        # re-verifying will compute. A text-mode read rewrites CRLF and yields a
        # different digest; it is kept separately, never as the primary hash.
        "log_sha256": hashlib.sha256(raw).hexdigest(),
        "log_sha256_lf_normalized": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "log_bytes": len(raw),
        "log_crlf_pairs": raw.count(b"\r\n"),
        "suites": suites,
        "order": order,
        "protected_db_fingerprint": fp.group(1) if fp else None,
        "protected_db_unchanged": bool(fp),
        "totals_line": tot.group(0) if tot else None,
        "all_suites_passed": verdict,
    }


def compare(work, ctrl):
    """Exact per-suite comparison. Shared by the real run and the self-test."""
    failures = []
    if set(work["suites"]) != set(ctrl["suites"]):
        only_w = sorted(set(work["suites"]) - set(ctrl["suites"]))
        only_c = sorted(set(ctrl["suites"]) - set(work["suites"]))
        failures.append("suite label sets differ: worktree-only=%s control-only=%s"
                        % (only_w, only_c))
    if work["order"] != ctrl["order"]:
        failures.append("suite execution order differs")

    compared = []
    mismatched = []
    for label in ctrl["order"]:
        c = ctrl["suites"][label]
        w = work["suites"].get(label)
        if w is None:
            continue
        same = (w["status"] == c["status"] and w["rc"] == c["rc"]
                and w["detail"] == c["detail"])
        row = {
            "suite": label,
            "control_status": c["status"], "worktree_status": w["status"],
            "control_rc": c["rc"], "worktree_rc": w["rc"],
            "control_detail": c["detail"], "worktree_detail": w["detail"],
            "control_missing_modules": c["missing_modules"],
            "worktree_missing_modules": w["missing_modules"],
            "identical": same,
        }
        compared.append(row)
        if not same:
            mismatched.append(row)
    if mismatched:
        failures.append("%d suites differ between control and worktree" % len(mismatched))
    return failures, compared, mismatched


def selftest(work, ctrl):
    """Prove the comparison can fail: a flipped status and an edited count must
    both be caught. A sensor that reports 'identical' no matter what is worse
    than no sensor."""
    import copy
    caught = []

    flipped = copy.deepcopy(work)
    target = next(l for l in flipped["order"] if flipped["suites"][l]["status"] == "OK")
    flipped["suites"][target]["status"] = "FAIL"
    flipped["suites"][target]["rc"] = 1
    f, _, m = compare(flipped, ctrl)
    caught.append(("status flip on %r" % target, bool(m) and any(
        r["suite"] == target for r in m)))

    edited = copy.deepcopy(work)
    target2 = next(l for l in edited["order"]
                   if re.search(r"\d+ pass / \d+ fail", edited["suites"][l]["detail"] or ""))
    edited["suites"][target2]["detail"] = re.sub(
        r"(\d+) pass", lambda mm: "%d pass" % (int(mm.group(1)) + 1),
        edited["suites"][target2]["detail"], count=1)
    f2, _, m2 = compare(edited, ctrl)
    caught.append(("count edit on %r" % target2, bool(m2) and any(
        r["suite"] == target2 for r in m2)))

    dropped = copy.deepcopy(work)
    target3 = dropped["order"][0]
    del dropped["suites"][target3]
    dropped["order"].remove(target3)
    f3, _, _ = compare(dropped, ctrl)
    caught.append(("dropped suite %r" % target3, bool(f3)))

    ok = all(passed for _, passed in caught)
    for name, passed in caught:
        print("  selftest %-46s %s" % (name, "CAUGHT" if passed else "MISSED"))
    print("GUARD CONTROL SELFTEST %s" % ("OK" if ok else "FAILED"))
    return 0 if ok else 1


def main():
    work = parse(os.path.join(LOGS, "dev-guards.log"))
    ctrl = parse(os.path.join(LOGS, "dev-guards-control.log"))

    if "--selftest" in sys.argv:
        return selftest(work, ctrl)

    failures, compared, mismatched = compare(work, ctrl)

    def tally(side):
        out = {"OK": 0, "FAIL": 0, "SKIP": 0}
        mods = {}
        for s in side["suites"].values():
            out[s["status"]] += 1
            if s["status"] == "FAIL":
                for m in s["missing_modules"] or ["(no import error captured)"]:
                    mods[m] = mods.get(m, 0) + 1
        return {"status_counts": out, "fail_root_causes": mods,
                "suites_total": len(side["suites"])}

    tw, tc = tally(work), tally(ctrl)
    if tw["status_counts"] != tc["status_counts"]:
        failures.append("status counts differ: %s vs %s"
                        % (tw["status_counts"], tc["status_counts"]))
    for side, name in ((work, "worktree"), (ctrl, "control")):
        if not side["protected_db_unchanged"]:
            failures.append("%s: protected DB fingerprint not reported unchanged" % name)
    if (work["protected_db_fingerprint"] and ctrl["protected_db_fingerprint"]
            and work["protected_db_fingerprint"] != ctrl["protected_db_fingerprint"]):
        failures.append("protected DB fingerprints differ between the two runs")

    env_failures = [r for r in compared
                    if r["worktree_status"] == "FAIL" and r["worktree_missing_modules"]]
    unexplained = [r for r in compared
                   if r["worktree_status"] == "FAIL" and not r["worktree_missing_modules"]]

    evidence = {
        "schema": "phase49-4-guard-control-v1",
        "mission": "Phase 4.9.4 runtime parity with Rahavard",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "purpose": "prove the local legacy-Python guard failures pre-date this phase "
                   "and are caused by missing local dependencies, not by the fix",
        "method": {
            "control": "a detached git worktree at HEAD with zero local changes",
            "worktree": "the mission worktree carrying the Phase 4.9.4 changes",
            "runner": "python dev/run_all_tests.py (unchanged in both; delegates to "
                      "dev/gate_db_guard.py, which copies the DB and fingerprints it)",
            "comparison": "exact per-suite status + exit code + reported counts",
            "log_hash_convention": "log_sha256 is the digest of the file bytes, which "
                                   "is what sha256sum reports; these logs are CRLF, so "
                                   "a text-mode read yields a different digest and is "
                                   "recorded separately as log_sha256_lf_normalized",
            "no_guard_weakened": True,
            "no_suite_skipped_or_removed": True,
            "no_threshold_changed": True,
        },
        "worktree": {k: work[k] for k in
                     ("log", "log_sha256", "log_sha256_lf_normalized", "log_bytes",
                      "log_crlf_pairs", "protected_db_fingerprint",
                      "protected_db_unchanged", "totals_line", "all_suites_passed")},
        "control": {k: ctrl[k] for k in
                    ("log", "log_sha256", "log_sha256_lf_normalized", "log_bytes",
                     "log_crlf_pairs", "protected_db_fingerprint",
                     "protected_db_unchanged", "totals_line", "all_suites_passed")},
        "tally_worktree": tw,
        "tally_control": tc,
        "suites_compared": len(compared),
        "suites_identical": sum(1 for r in compared if r["identical"]),
        "suites_mismatched": mismatched,
        "failures_attributed_to_missing_modules": len(env_failures),
        "failures_without_an_import_error": unexplained,
        "local_python": sys.version.split()[0],
        "ci_authority": "CI installs requirements.txt on Python 3.12; the per-job CI "
                        "record for the final commit is the authority for the legacy "
                        "Python lane, not this local run",
        "per_suite": compared,
    }

    out_rel = "_audit/phase49-4/evidence/GUARD-CONTROL.json"
    man_rel = "_audit/phase49-4/manifests/stage14-guard-control.json"
    for rel in (out_rel, man_rel):
        os.makedirs(os.path.dirname(os.path.join(ROOT, rel.replace("/", os.sep))), exist_ok=True)
    body = json.dumps(evidence, ensure_ascii=False, indent=1) + "\n"
    io.open(os.path.join(ROOT, out_rel.replace("/", os.sep)), "w",
            encoding="utf-8", newline="\n").write(body)
    sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    io.open(os.path.join(ROOT, man_rel.replace("/", os.sep)), "w",
            encoding="utf-8", newline="\n").write(json.dumps({
                "stage": "stage14_guard_control",
                "finished_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "payload_path": out_rel,
                "payload_sha256": sha,
                "exit_code": 1 if failures else 0,
            }, ensure_ascii=False, indent=1) + "\n")

    print("control  : %s" % json.dumps(tc, ensure_ascii=False))
    print("worktree : %s" % json.dumps(tw, ensure_ascii=False))
    print("compared %d suites, identical %d, mismatched %d"
          % (len(compared), evidence["suites_identical"], len(mismatched)))
    print("FAIL with a missing module: %d | FAIL without one: %d"
          % (len(env_failures), len(unexplained)))
    for r in unexplained:
        print("  unexplained FAIL: %s | %s" % (r["suite"], r["worktree_detail"]))
    print("protected DB unchanged: control=%s worktree=%s"
          % (ctrl["protected_db_unchanged"], work["protected_db_unchanged"]))
    for f in failures:
        print("FAILURE:", f)
    print("wrote %s (%s)" % (out_rel, sha[:16]))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())