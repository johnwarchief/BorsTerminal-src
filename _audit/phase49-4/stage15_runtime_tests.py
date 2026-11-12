#!/usr/bin/env python3
"""Phase 4.9.4 stage15: run the runtime test lanes and record them as evidence.

The owner asked for the tests to be checked, not remembered. Every lane here is
executed fresh, its exit code and output are hashed into a log, and the parsed
counts are written to evidence/RUNTIME-TESTS.json. Nothing is inferred from an
earlier console scroll.

The parsers carry negative controls (--selftest): a parser that cannot see a
failure would report every lane green, which is exactly the vacuous pass this
phase must not produce.

Run from the repo root:  python _audit/phase49-4/stage15_runtime_tests.py
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AUDIT = os.path.join(ROOT, "_audit", "phase49-4")
LOGS = os.path.join(AUDIT, "logs")
EVIDENCE = os.path.join(AUDIT, "evidence")
MANIFESTS = os.path.join(AUDIT, "manifests")

BASE_COMMIT = "e09ccd95d51c94082640cda75ef3de2b2008f9d2"

# Frozen by the owner's ruling: these must not move at all.
FROZEN = [
    "candle_contract.py",
    "price_basis.py",
    "codal_periods.py",
    "backend-go/internal/candle/candle.go",
]

CHANGED_GO = [
    "backend-go/internal/candlebuild/candlebuild.go",
    "backend-go/internal/candlebuild/candlebuild_test.go",
    "backend-go/internal/candlebuild/reference_fixture_test.go",
    "backend-go/internal/candlebuild/reference_zeroevent_fixture_test.go",
    "backend-go/internal/chart/handlers.go",
    "backend-go/internal/chart/measured.go",
    "backend-go/internal/chart/measured_test.go",
    "backend-go/internal/chart/reference_literal_fixture_test.go",
]

GO_OK = re.compile(r"^ok\s+\S+", re.M)
GO_FAIL = re.compile(r"^(?:FAIL|--- FAIL)", re.M)
GO_NOTEST = re.compile(r"^\?\s+\S+\s+\[no test files\]", re.M)
VITEST_FILES = re.compile(r"Test Files\s+(?:(\d+) failed \| )?(?:(\d+) passed)")
VITEST_TESTS = re.compile(r"^\s*Tests\s+(?:(\d+) failed \| )?(?:(\d+) passed)", re.M)
GLYPH = re.compile(r"(\d+) passed\s*/\s*(\d+) failed")
ANCHOR_OK = "VERSION ANCHOR GUARD OK"

# vitest colourises its summary even when stdout is a pipe, so the counts sit
# inside escape sequences. Parsing the raw bytes finds nothing and would report
# a green lane as unparseable.
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def strip_ansi(text):
    return ANSI.sub("", text)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, ROOT).replace(os.sep, "/")


def parse_go(text):
    return {
        "packages_ok": len(GO_OK.findall(text)),
        "packages_no_test_files": len(GO_NOTEST.findall(text)),
        "failures": len(GO_FAIL.findall(text)),
    }


def parse_vitest(text):
    f = VITEST_FILES.search(text)
    t = VITEST_TESTS.search(text)
    if not f or not t:
        return {"parse_complete": False}
    return {
        "parse_complete": True,
        "files_failed": int(f.group(1) or 0),
        "files_passed": int(f.group(2) or 0),
        "tests_failed": int(t.group(1) or 0),
        "tests_passed": int(t.group(2) or 0),
    }


def parse_glyph(text):
    hits = GLYPH.findall(text)
    if not hits:
        return {"parse_complete": False}
    return {
        "parse_complete": True,
        "passed": sum(int(a) for a, _ in hits),
        "failed": sum(int(b) for _, b in hits),
    }


def selftest():
    """Every parser must see a planted failure, and must not invent one."""
    cases = [
        ("go: planted FAIL line", parse_go,
         "ok  \tbors/x\t1.0s\nFAIL\tbors/y\t0.5s\n",
         lambda r: r["failures"] == 1 and r["packages_ok"] == 1),
        ("go: clean run reports zero failures", parse_go,
         "ok  \tbors/x\t1.0s\n?   \tbors/z\t[no test files]\n",
         lambda r: r["failures"] == 0 and r["packages_no_test_files"] == 1),
        ("vitest: planted failed test", parse_vitest,
         " Test Files  1 failed | 106 passed (107)\n      Tests  2 failed | 865 passed (867)\n",
         lambda r: r["parse_complete"] and r["tests_failed"] == 2
         and r["files_failed"] == 1 and r["tests_passed"] == 865),
        ("vitest: clean run", parse_vitest,
         " Test Files  107 passed (107)\n      Tests  867 passed (867)\n",
         lambda r: r["parse_complete"] and r["tests_failed"] == 0
         and r["tests_passed"] == 867),
        ("vitest: missing summary is not a pass", parse_vitest,
         "some unrelated output\n", lambda r: r["parse_complete"] is False),
        # The real vitest payload is ANSI-coloured; a clean-text fixture alone
        # would leave the parser blind to every actual run.
        ("vitest: ANSI-coloured summary (real payload shape)",
         lambda t: parse_vitest(strip_ansi(t)),
         "\x1b[2m Test Files \x1b[22m \x1b[1m\x1b[32m107 passed\x1b[39m\x1b[22m"
         "\x1b[90m (107)\x1b[39m\n\x1b[2m      Tests \x1b[22m \x1b[1m\x1b[32m"
         "867 passed\x1b[39m\x1b[22m\x1b[90m (867)\x1b[39m\n",
         lambda r: r["parse_complete"] and r["tests_passed"] == 867
         and r["files_passed"] == 107 and r["tests_failed"] == 0),
        ("vitest: ANSI-coloured FAILURE is still seen",
         lambda t: parse_vitest(strip_ansi(t)),
         "\x1b[2m Test Files \x1b[22m \x1b[1m\x1b[31m1 failed\x1b[39m\x1b[22m"
         " | \x1b[1m\x1b[32m106 passed\x1b[39m\x1b[22m\n\x1b[2m      Tests \x1b[22m"
         " \x1b[1m\x1b[31m2 failed\x1b[39m\x1b[22m | \x1b[1m\x1b[32m865 passed"
         "\x1b[39m\x1b[22m\n",
         lambda r: r["parse_complete"] and r["tests_failed"] == 2
         and r["files_failed"] == 1),
        ("ansi stripper keeps the digits", strip_ansi,
         "\x1b[32m107 passed\x1b[39m", lambda r: r == "107 passed"),
        ("glyph: planted failure", parse_glyph,
         "persian_glyph_guard: 3 passed / 1 failed\n",
         lambda r: r["parse_complete"] and r["failed"] == 1),
        ("glyph: clean run", parse_glyph,
         "persian_glyph_guard: 4 passed / 0 failed\n",
         lambda r: r["parse_complete"] and r["failed"] == 0 and r["passed"] == 4),
        ("glyph: missing summary is not a pass", parse_glyph,
         "nothing here\n", lambda r: r["parse_complete"] is False),
    ]
    ok = True
    for name, fn, text, want in cases:
        got = fn(text)
        passed = bool(want(got))
        ok = ok and passed
        print("  selftest %-46s %s" % (name, "CAUGHT" if passed else "MISSED"))
    # A frozen-diff check that cannot see a change is decorative.
    probe = subprocess.run(
        ["git", "diff", "--stat", BASE_COMMIT, "--", "backend-go/internal/chart/measured.go"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    moved = bool(probe.stdout.strip())
    print("  selftest %-46s %s" % ("frozen-diff sensor sees a changed file",
                                   "CAUGHT" if moved else "MISSED"))
    ok = ok and moved
    print("stage15 selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def run(label, argv, cwd, timeout=1800):
    os.makedirs(LOGS, exist_ok=True)
    log = os.path.join(LOGS, "stage15-%s.log" % label)
    # Windows CreateProcess does not apply PATHEXT, so npx.cmd must be resolved.
    exe = shutil.which(argv[0])
    if exe is None:
        sys.exit("FATAL: %s is not on PATH" % argv[0])
    argv = [exe] + argv[1:]
    proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)
    body = (proc.stdout or "") + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")
    with io.open(log, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("$ %s\n[cwd] %s\n\n%s" % (" ".join(argv), rel(cwd), body))
    plain = strip_ansi(body)
    tail = [ln for ln in plain.splitlines() if ln.strip()][-12:]
    return {
        "label": label,
        "command": " ".join(argv),
        "cwd": rel(cwd),
        "exit_code": proc.returncode,
        "log": rel(log),
        "log_sha256": sha(log),
        "output_tail": tail,
        "_text": plain,
    }


def git_out(argv):
    p = subprocess.run(["git"] + argv, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode != 0:
        sys.exit("FATAL: git %s failed: %s" % (" ".join(argv), p.stderr.strip()))
    return p.stdout


def main():
    if "--selftest" in sys.argv[1:]:
        return selftest()

    head = git_out(["rev-parse", "HEAD"]).strip()
    branch = git_out(["rev-parse", "--abbrev-ref", "HEAD"]).strip()
    lanes = []
    failures = []

    go_dir = os.path.join(ROOT, "backend-go")
    v2_dir = os.path.join(ROOT, "frontend-v2")

    r = run("go-build", ["go", "build", "./..."], go_dir)
    r["pass"] = r["exit_code"] == 0
    lanes.append(r)
    if not r["pass"]:
        failures.append("go build exited %d" % r["exit_code"])

    r = run("go-test", ["go", "test", "./...", "-count=1"], go_dir)
    r["parsed"] = parse_go(r["_text"])
    r["pass"] = r["exit_code"] == 0 and r["parsed"]["failures"] == 0
    lanes.append(r)
    if not r["pass"]:
        failures.append("go test exited %d with %d failure lines"
                        % (r["exit_code"], r["parsed"]["failures"]))

    r = run("gofmt", ["gofmt", "-l"] + CHANGED_GO, ROOT)
    unformatted = [ln for ln in r["_text"].splitlines() if ln.strip()]
    r["unformatted_files"] = unformatted
    r["pass"] = r["exit_code"] == 0 and not unformatted
    lanes.append(r)
    if not r["pass"]:
        failures.append("gofmt lists %d unformatted files" % len(unformatted))

    r = run("v2-tsc", ["npx", "tsc", "-b"], v2_dir)
    r["pass"] = r["exit_code"] == 0
    lanes.append(r)
    if not r["pass"]:
        failures.append("frontend-v2 tsc -b exited %d" % r["exit_code"])

    r = run("v2-vitest", ["npx", "vitest", "run"], v2_dir, timeout=2400)
    r["parsed"] = parse_vitest(r["_text"])
    r["pass"] = (r["exit_code"] == 0 and r["parsed"].get("parse_complete")
                 and r["parsed"]["tests_failed"] == 0
                 and r["parsed"]["files_failed"] == 0
                 and r["parsed"]["tests_passed"] > 0)
    lanes.append(r)
    if not r["pass"]:
        failures.append("frontend-v2 vitest exited %d, parsed=%s"
                        % (r["exit_code"], json.dumps(r["parsed"])))

    for label, argv in (("version-anchor", ["dev/version_anchor_guard.py"]),
                        ("persian-glyph", ["dev/persian_glyph_guard.py"]),
                        ("persian-glyph-selftest",
                         ["dev/persian_glyph_guard.py", "--selftest"])):
        r = run(label, [sys.executable] + argv, ROOT)
        if label == "version-anchor":
            r["anchor_ok"] = ANCHOR_OK in r["_text"]
            r["pass"] = r["exit_code"] == 0 and r["anchor_ok"]
        else:
            r["parsed"] = parse_glyph(r["_text"])
            r["pass"] = (r["exit_code"] == 0 and r["parsed"].get("parse_complete")
                         and r["parsed"]["failed"] == 0 and r["parsed"]["passed"] > 0)
        lanes.append(r)
        if not r["pass"]:
            failures.append("%s exited %d" % (label, r["exit_code"]))

    r = run("guard-control-selftest",
            [sys.executable, "_audit/phase49-4/stage14_guard_control.py", "--selftest"], ROOT)
    r["all_controls_caught"] = ("MISSED" not in r["_text"]
                                and r["_text"].count("CAUGHT") >= 3)
    r["pass"] = r["exit_code"] == 0 and r["all_controls_caught"]
    lanes.append(r)
    if not r["pass"]:
        failures.append("stage14 negative controls did not all fire")

    frozen_diff = git_out(["diff", "--stat", BASE_COMMIT, "--"] + FROZEN)
    frozen_ok = not frozen_diff.strip()
    if not frozen_ok:
        failures.append("a frozen contract moved:\n" + frozen_diff)

    engine_diff = git_out(["diff", "--stat", BASE_COMMIT, "--", "backend-go", "frontend-v2"])
    untracked = [p for p in git_out(["ls-files", "--others", "--exclude-standard"]).splitlines()
                 if p.startswith(("backend-go/", "frontend-v2/"))]

    # Cross-check against the captured bytes: a parser that only works on the
    # in-memory string would still be blind to what the log actually recorded.
    reparsers = {"go-test": parse_go, "v2-vitest": parse_vitest}
    for lane in lanes:
        if "parsed" not in lane:
            continue
        with io.open(os.path.join(ROOT, lane["log"].replace("/", os.sep)),
                     encoding="utf-8") as fh:
            disk = fh.read()
        again = reparsers.get(lane["label"], parse_glyph)(strip_ansi(disk))
        lane["parsed_from_log_on_disk"] = again
        lane["log_reparse_agrees"] = again == lane["parsed"]
        if not lane["log_reparse_agrees"]:
            failures.append("%s: the log on disk parses differently from the run"
                            % lane["label"])

    for lane in lanes:
        lane.pop("_text", None)

    evidence = {
        "schema": "phase49-4-runtime-tests-v1",
        "mission": "Phase 4.9.4 runtime parity with Rahavard",
        "status": "PASS" if not failures else "PARTIAL",
        "failures": failures,
        "base_commit": BASE_COMMIT,
        "head_commit": head,
        "branch": branch,
        "measurement": {
            "kind": "the repo's own test and gate commands, executed fresh",
            "is_ui_test": False,
            "screenshot": "NOT_MEASURED",
            "note": "no browser was driven here; the frontend lane is tsc + vitest "
                    "over the real modules, not a rendered UI",
        },
        "frozen_contracts": {
            "paths": FROZEN,
            "diff_vs_base": frozen_diff.strip() or "(empty)",
            "unchanged": frozen_ok,
            "owner_ruling": "candle_contract.py and candle.go must not change",
        },
        "engine_diff_vs_base": engine_diff.strip(),
        "new_engine_test_files": sorted(untracked),
        "lanes": lanes,
        "local_legacy_python_lane": {
            "status": "NOT_MEASURED_HERE",
            "reason": "dev/run_all_tests.py needs fastapi/numpy/pandas which this host's "
                      "Python 3.15.2 lacks; stage14 proved its 152 failures are identical "
                      "on a clean control worktree, and CI is the authority for that lane",
            "evidence": "_audit/phase49-4/evidence/GUARD-CONTROL.json",
        },
        "not_measured": {
            "ui_screenshot": "no browser render was exercised by any lane here",
            "legacy_frontend_v1_tests": "frontend/node_modules is absent on this host; "
                                        "v1 was measured by stage13, not fixed",
        },
    }

    os.makedirs(EVIDENCE, exist_ok=True)
    os.makedirs(MANIFESTS, exist_ok=True)
    out = os.path.join(EVIDENCE, "RUNTIME-TESTS.json")
    body = json.dumps(evidence, ensure_ascii=False, indent=1) + "\n"
    with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)
    manifest = {
        "stage": "stage15_runtime_tests",
        "finished_utc": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat().replace("+00:00", "Z"),
        "payload_path": rel(out),
        "payload_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "exit_code": 0 if not failures else 1,
    }
    man = os.path.join(MANIFESTS, "stage15-runtime-tests.json")
    with io.open(man, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n")

    for lane in lanes:
        extra = lane.get("parsed") or lane.get("unformatted_files")
        print("%-24s rc=%d %s %s" % (lane["label"], lane["exit_code"],
                                     "PASS" if lane["pass"] else "FAIL",
                                     json.dumps(extra, ensure_ascii=False) if extra is not None else ""))
    print("frozen contracts unchanged:", frozen_ok)
    for f in failures:
        print("FAILURE:", f)
    print("wrote", rel(out), manifest["payload_sha256"][:16])
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())