#!/usr/bin/env python3
"""Write the Phase 4.9.3 artifact SHA-256 manifest.

Deterministic: no wall clock anywhere in the payload, so a rerun over unchanged
inputs is byte-identical.  The file lists itself nowhere (a self-hash cannot
converge).  Inputs that deliberately stay out of git are listed with the SHA-256
*recorded by the phase that produced them*, read back from committed evidence
rather than retyped, and marked absent on this host.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCS = os.path.join(ROOT, "docs", "opportunity-center", "phase49-3")
AUDIT = os.path.join(ROOT, "_audit", "phase49-3")
OUT = os.path.join(DOCS, "ARTIFACTS-SHA256.txt")
CI = os.path.join(DOCS, "CI-FINAL-RESULTS.json")
SELF = "docs/opportunity-center/phase49-3/ARTIFACTS-SHA256.txt"

BASE_COMMIT = "e09ccd95d51c94082640cda75ef3de2b2008f9d2"
VERDICT = "BLOCKED_CAPTURE_REQUIRED"

CODE = [
    "backend-go/internal/chart/measured.go",
    "backend-go/internal/chart/canonical.go",
    "backend-go/internal/chart/chartdb.go",
    "backend-go/internal/chart/handlers.go",
    "backend-go/internal/candlebuild/candlebuild.go",
    "backend-go/cmd/candlebuild/main.go",
    "backend-go/internal/httpapi/server.go",
    "dev/symbol_identity.py",
    "dev/run_all_tests.py",
    "dev/suite_registry.json",
    "dev/persian_glyph_guard.py",
    "dev/phase49_rules_guard.py",
    "dev/suite_registry_guard.py",
    "dev/test_workflows_layout.py",
    "scripts/check_seed_release.py",
    "scripts/test_check_seed_release.py",
    ".github/workflows/guards.yml",
    "_audit/.gitignore",
    "_audit/phase49-full-verification/stage03_step_ledger.py",
    "_audit/phase49-full-verification/stage05_symbol_ledger.py",
    "_audit/phase49-2/build_coverage_ledger.py",
    "docs/opportunity-center/phase49/HISTORY-COVERAGE-LEDGER.csv",
    "docs/opportunity-center/phase49/ADJUSTMENT-EVIDENCE-LEDGER.csv",
    "docs/opportunity-center/phase49-2/ARTIFACTS-SHA256.txt",
    "_audit/phase49-full-verification/evidence/capture-summary.json",
    "_audit/phase49-full-verification/evidence/ledger-counts.json",
]

# (path, note, where the recorded sha256/size come from)
PRIOR_MANIFEST = "docs/opportunity-center/phase49-2/ARTIFACTS-SHA256.txt"
CAPTURE_SUMMARY = "_audit/phase49-full-verification/evidence/capture-summary.json"


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, ROOT).replace(os.sep, "/")


def line(r):
    p = os.path.join(ROOT, r.replace("/", os.sep))
    return "%s  %d  %s" % (sha(p), os.path.getsize(p), r)


def discover(sub, exts):
    d = os.path.join(AUDIT, sub)
    if not os.path.isdir(d):
        return []
    return sorted(rel(os.path.join(d, f)) for f in os.listdir(d)
                  if os.path.isfile(os.path.join(d, f))
                  and os.path.splitext(f)[1] in exts)


def prior_inputs():
    """Read the not-committed input hashes back from the phase49-2 manifest."""
    out = {}
    p = os.path.join(ROOT, PRIOR_MANIFEST.replace("/", os.sep))
    with io.open(p, encoding="utf-8") as fh:
        for ln in fh:
            if ln.startswith("#") or "  # " not in ln:
                continue
            body, note = ln.split("  # ", 1)
            parts = body.split()
            if len(parts) != 3:
                continue
            h, size, path = parts
            out[path] = (h, size, note.strip())
    return out


def capture_inputs():
    p = os.path.join(ROOT, CAPTURE_SUMMARY.replace("/", os.sep))
    merged = json.load(io.open(p, encoding="utf-8"))["merged"]
    idx = merged["reference_index_all"]
    return [
        (merged["bars_file"], merged["bars_container_sha256"], "-",
         "licensed paired type0/type7 bars, gzip container (not committed)"),
        (merged["bars_file"], merged["bars_payload_sha256"], "-",
         "same file, uncompressed NDJSON payload hash (not committed)"),
        (idx["file"], idx["sha256"], "-",
         "licensed reference index, 759 symbols (not committed)"),
    ]


def main():
    deliverables = sorted(
        rel(os.path.join(DOCS, f)) for f in os.listdir(DOCS)
        if os.path.isfile(os.path.join(DOCS, f))
        and rel(os.path.join(DOCS, f)) != SELF)

    evidence = (discover("ledgers", {".csv"})
                + discover("evidence", {".json"})
                + discover("manifests", {".json"}))
    scripts = sorted(rel(os.path.join(AUDIT, f)) for f in os.listdir(AUDIT)
                     if f.endswith(".py"))

    # The docs copies must be byte-identical to the audit originals.
    pairs = [("docs/opportunity-center/phase49-3/COHORT-SELECTION.json",
              "_audit/phase49-3/evidence/COHORT-SELECTION.json"),
             ("docs/opportunity-center/phase49-3/COVERAGE-EXPANSION-MAP.csv",
              "_audit/phase49-3/ledgers/COVERAGE-EXPANSION-MAP.csv")]
    for a, b in pairs:
        pa = os.path.join(ROOT, a.replace("/", os.sep))
        pb = os.path.join(ROOT, b.replace("/", os.sep))
        if not os.path.exists(pa) or not os.path.exists(pb):
            sys.exit("FATAL: missing docs/audit pair %s | %s" % (a, b))
        if sha(pa) != sha(pb):
            sys.exit("FATAL: docs copy drifted from audit original: %s" % a)

    ci_status = "PENDING (no CI run recorded yet)"
    ci_sha = "-"
    ci_jobs = "NOT_MEASURED"
    ci_legacy = "NOT_MEASURED"
    if os.path.exists(CI):
        rec = json.load(io.open(CI, encoding="utf-8"))
        ci_status = rec.get("status", "UNKNOWN")
        ci_sha = rec.get("commit_sha", "?")
        ci_jobs = ("workflows_success=%s jobs_success=%s blocking_jobs_success=%s"
                   % (rec.get("all_workflows_success"),
                      rec.get("all_jobs_success"),
                      rec.get("all_blocking_jobs_success")))
        attr = rec.get("report_only_failure_attribution", [])
        if rec.get("report_only_failures_caused_by_this_mission"):
            sys.exit("FATAL: a report-only CI failure gained suites at this"
                     " commit; the manifest must not call it pre-existing")
        for a in attr:
            if a.get("status") != "MEASURED":
                ci_legacy = "%s: %s" % (a["job"], a.get("status"))
                continue
            if not a["parse_complete_both"]:
                sys.exit("FATAL: legacy suite parse incomplete for %s" % a["job"])
            c, b = a["this_commit_counts"], a["base_commit_counts"]
            ci_legacy = ("%s: %d/%d failed here vs %d/%d at base,"
                         " identical_sets=%s new=%d resolved=%d"
                         % (a["job"], c["suites_failed"], c["suites_total"],
                            b["suites_failed"], b["suites_total"],
                            a["failed_sets_identical"], len(a["new_failures"]),
                            len(a["resolved_failures"])))

    gates = json.load(io.open(os.path.join(AUDIT, "evidence", "gates.json"),
                              encoding="utf-8"))
    go = gates["go"]
    prod = gates["profiles"]["production"]
    data = gates["profiles"]["data"]
    dl = gates["data_lane_failures"]
    if dl["caused_by_this_mission"]:
        sys.exit("FATAL: a data-lane failure is attributed to this mission;"
                 " the manifest must not call it pre-existing")
    for s in dl["suites"]:
        if not s["counts_identical"]:
            sys.exit("FATAL: control counts differ at base for %s" % s["suite"])
    if len(dl["suites"]) != dl["count"]:
        sys.exit("FATAL: data-lane failure count disagrees with its suite list")

    out = [
        "# Phase 4.9.3 artifact SHA-256 manifest",
        "# generated by _audit/phase49-3/build_artifacts_manifest.py",
        "# deterministic: no timestamp in the payload; rerun is byte-identical",
        "# verdict: %s" % VERDICT,
        "# code_commit: %s (base; this mission changed no engine code)" % BASE_COMMIT,
        "# ci_status: %s" % ci_status,
        "# ci_commit: %s" % ci_sha,
        "# ci_jobs: %s (python-legacy is continue-on-error: workflow success is"
        " NOT all-jobs success)" % ci_jobs,
        "# ci_report_only_attribution: %s" % ci_legacy,
        "# independent_db_revision: NOT_CREATED"
        " (no working DB copy was built: the paired capture bytes are absent,"
        " and fabricating inputs is forbidden)",
        "# independent_db_rows: NOT_MEASURED (raw=0 adjusted=0 factors=0 written"
        " by this mission)",
        "# go: %s packages ok, %s without test files, %s failures" % (
            go["packages_ok"], go["packages_no_test_files"], go["failures"]),
        "# profile production: exit %s, %s suites counted, ALL_SUITES_PASSED=%s" % (
            prod["exit_code"], prod["suites_counted"], prod["all_suites_passed"]),
        "# profile data: exit %s, %s suites counted, %s failed suites"
        " (pre-existing local dependency gap; identical counts on a pristine"
        " base-commit control worktree)" % (
            data["exit_code"], data["suites_counted"], dl["count"]),
        "# format: sha256  size_bytes  path",
        "# section: 1=deliverables 2=ledgers/evidence/manifests 3=mission scripts"
        " 4=code, gates and pinned inputs 5=inputs not committed (recorded hashes)",
        "# note: this manifest does not list itself",
    ]
    for header, group in (("1", deliverables), ("2", evidence),
                          ("3", scripts), ("4", CODE)):
        out.append("# --- section %s ---" % header)
        for r in group:
            p = os.path.join(ROOT, r.replace("/", os.sep))
            if not os.path.exists(p):
                sys.exit("FATAL: listed artifact is absent: %s" % r)
            out.append(line(r))

    out.append("# --- section 5 (recorded sha256, recorded size, path) ---")
    prior = prior_inputs()
    absent = []
    wanted = [
        "_audit/phase49-full-verification/seed/market.db",
        "_audit/phase49-full-verification/seed/market.db.lzma",
        "_audit/phase49-full-verification/seed/market.db.gz",
        "_audit/phase49-2/db/market.db",
        "_audit/phase49-2/rahavard/pilot-capture.json",
    ]
    for r in wanted:
        if r not in prior:
            sys.exit("FATAL: no recorded hash for input %s" % r)
        h, size, note = prior[r]
        p = os.path.join(ROOT, r.replace("/", os.sep))
        if os.path.exists(p):
            actual = sha(p)
            if actual != h:
                sys.exit("FATAL: present input %s does not match its recorded"
                         " hash; refusing to publish a stale manifest" % r)
            out.append("%s  %s  %s  # %s" % (actual, os.path.getsize(p), r, note))
        else:
            absent.append(r)
            out.append("%s  %s  %s  # %s — ABSENT on this host; hash recorded by"
                       " phase49-2, not re-measured here" % (h, size, r, note))
    for r, h, size, note in capture_inputs():
        p = os.path.join(ROOT, r.replace("/", os.sep))
        if os.path.exists(p):
            sys.exit("FATAL: %s is present; re-measure it before publishing" % r)
        absent.append(r)
        out.append("%s  %s  %s  # %s — ABSENT on this host; hash recorded by"
                   " phase49-full-verification, not re-measured here"
                   % (h, size, r, note))

    text = "\n".join(out) + "\n"
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("wrote", rel(OUT))
    print("deliverables=%d evidence=%d scripts=%d code=%d absent_inputs=%d"
          % (len(deliverables), len(evidence), len(scripts), len(CODE),
             len(set(absent))))
    print("verdict=%s ci=%s" % (VERDICT, ci_status))


if __name__ == "__main__":
    main()