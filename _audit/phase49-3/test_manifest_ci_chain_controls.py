#!/usr/bin/env python3
"""Controls for the manifest builder's preserved-CI-chain gate.

The gate exists so a stale, mis-bound or mission-blaming CI record cannot ride
along in the manifest.  A gate that cannot fail is decoration, so each rule is
exercised with a deliberately bad record and the builder must abort.  Temporary
records are removed in a finally block and the evidence directory is proven
unchanged afterwards.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
EV = os.path.join(HERE, "evidence")
BUILDER = os.path.join(HERE, "build_artifacts_manifest.py")
MAIN_CI = os.path.join(ROOT, "docs", "opportunity-center", "phase49-3",
                       "CI-FINAL-RESULTS.json")
TMP_PREFIX = "CI-ZZCONTROL-"


def load(p):
    with io.open(p, encoding="utf-8") as fh:
        return json.load(fh)


def run_builder():
    r = subprocess.run([sys.executable, BUILDER], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8",
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def cleanup():
    removed = []
    for f in os.listdir(EV):
        if f.startswith(TMP_PREFIX):
            os.remove(os.path.join(EV, f))
            removed.append(f)
    return removed


def main():
    base = load(MAIN_CI)
    with open(MAIN_CI, "rb") as fh:
        main_bytes = fh.read()
    good = load(os.path.join(EV, "CI-59a1c918.json"))
    before = sorted(os.listdir(EV))
    results = []
    try:
        # Positive control: the untouched chain must build.
        rc, out = run_builder()
        results.append(("P_chain_builds_when_records_are_sound", rc == 0,
                        "rc=%d" % rc))

        # Negative 1: a run whose head_sha is not the record's commit_sha.
        bad = json.loads(json.dumps(good))
        bad["commit_sha"] = "f" * 40
        p = os.path.join(EV, TMP_PREFIX + "headsha.json")
        with io.open(p, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(bad, fh)
        rc, out = run_builder()
        results.append(("N1_head_sha_must_equal_commit_sha",
                        rc != 0 and "head_sha is not its commit_sha" in out,
                        "rc=%d" % rc))
        os.remove(p)

        # Negative 2: two records bound to the same commit.
        bad = json.loads(json.dumps(good))
        bad["commit_sha"] = base["commit_sha"]
        p = os.path.join(EV, TMP_PREFIX + "duplicate.json")
        with io.open(p, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(bad, fh)
        rc, out = run_builder()
        results.append(("N2_no_two_records_bind_one_commit",
                        rc != 0 and "already recorded elsewhere" in out,
                        "rc=%d" % rc))
        os.remove(p)

        # Negative 3: a record blaming this mission for a report-only failure.
        bad = json.loads(json.dumps(good))
        bad["commit_sha"] = "e" * 40
        bad["report_only_failures_caused_by_this_mission"] = 1
        p = os.path.join(EV, TMP_PREFIX + "blame.json")
        with io.open(p, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(bad, fh)
        rc, out = run_builder()
        results.append(("N3_mission_blamed_failure_aborts",
                        rc != 0 and "attributes a report-only failure" in out,
                        "rc=%d" % rc))
        os.remove(p)

        # Negative 4: an INCOMPLETE record must not be presented as measured.
        bad = json.loads(json.dumps(good))
        bad["commit_sha"] = "d" * 40
        bad["status"] = "INCOMPLETE"
        p = os.path.join(EV, TMP_PREFIX + "incomplete.json")
        with io.open(p, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(bad, fh)
        rc, out = run_builder()
        results.append(("N4_incomplete_record_aborts",
                        rc != 0 and "is not COMPLETE" in out, "rc=%d" % rc))
        os.remove(p)

        # Negative 5: the primary record's runs must be SHA-bound too, not just
        # the preserved ones.  Restored byte-exactly in the finally block.
        bad = json.loads(json.dumps(base))
        bad["runs"][0]["head_sha"] = "a" * 40
        with io.open(MAIN_CI, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(bad, fh)
        rc, out = run_builder()
        results.append(("N5_primary_record_head_sha_must_bind",
                        rc != 0 and "CI-FINAL-RESULTS.json run" in out,
                        "rc=%d" % rc))
    finally:
        with open(MAIN_CI, "wb") as fh:
            fh.write(main_bytes)
        removed = cleanup()
        after = sorted(os.listdir(EV))
        results.append(("C_evidence_dir_restored", after == before and not removed,
                        "removed=%d before=%d after=%d"
                        % (len(removed), len(before), len(after))))
        with open(MAIN_CI, "rb") as fh:
            restored = fh.read()
        results.append(("C_main_ci_bytes_restored", restored == main_bytes,
                        "bytes=%d" % len(restored)))

    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, detail in results:
        print("%-42s %s  %s" % (name, "PASS" if ok else "FAIL", detail))
    print("manifest_ci_chain_controls: %d/%d passed" % (passed, len(results)))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())