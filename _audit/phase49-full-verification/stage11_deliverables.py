#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assemble and verify the Phase 4.9.1 full-verification deliverables.

This stage is deliberately narrow:

* copy the two ledgers and the Seed manifest byte-for-byte from the ignored
  evidence tree into docs/opportunity-center/phase49/;
* verify their row counts and SHA-256 against the recorded values;
* verify the copied manifest does not point at raw capture paths;
* verify the CI record is a parseable pending/complete record;
* write ARTIFACTS-SHA256-full-verification.txt with SHA-256 and size for the
  seven other deliverables, the tracked evidence files, the reference inputs
  and the Seed DB/LZMA/gzip.

It never writes the report bodies and never touches the Seed artifacts. Run it
from the repository root or through its absolute path; it is idempotent.
"""
from __future__ import annotations

import csv
import datetime
import hashlib
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "_audit", "phase49-full-verification")
DOCS = os.path.join(ROOT, "docs", "opportunity-center", "phase49")
OUT = os.path.join(DOCS, "ARTIFACTS-SHA256-full-verification.txt")

STEPS_EXPECTED = {
    "rows": 8308,
    "sha256": "c0ab45bf60ba8d95fa4f4f33d60d4fa6f465a62c07271053c8ca7781f5114a28",
}
SYMBOLS_EXPECTED = {
    "rows": 6103,
    "sha256": "c3ad3741daaa55b849fb51aca7cc066ea859d0469de2eb85d82471988a69a650",
}
MANIFEST_EXPECTED = {
    "sha256": "6a930818b05f3ef180064e7c8c908830bac5a72d89b28111dd43fba9cb859aa7",
    "size": 5468,
}

DELIVERABLES = [
    "FULL-VERIFICATION-REPORT.md",
    "ADJUSTMENT-EVIDENCE-LEDGER.csv",
    "HISTORY-COVERAGE-LEDGER.csv",
    "UNVERIFIED-RECONCILIATION.md",
    "PYTHON-CI-MIGRATION.md",
    "CI-FINAL-RESULTS.json",
    "FINAL-SEED-MANIFEST.json",
]

EVIDENCE = [
    "evidence/anomaly-counts.json",
    "evidence/backfill-availability.json",
    "evidence/backfill-fresh.json",
    "evidence/backfill-idempotency.json",
    "evidence/backfill-price-basis.json",
    "evidence/backfill-six.json",
    "evidence/baseline.json",
    "evidence/capture-summary.json",
    "evidence/ci-failures.json",
    "evidence/inventory-reconcile.json",
    "evidence/ledger-counts.json",
    "evidence/parity.json",
    "evidence/post-backfill-anomalies.json",
    "evidence/product-tests.json",
    "evidence/seed-integrity.json",
    "evidence/stage00_baseline.manifest.json",
    "evidence/stage01_capture_plan.manifest.json",
    "evidence/stage02_import_reference-30.manifest.json",
    "evidence/stage02_import_reference-7.manifest.json",
    "evidence/stage03_step_ledger.manifest.json",
    "evidence/stage04_volana_rootcause.manifest.json",
    "evidence/stage05_symbol_ledger.manifest.json",
    "evidence/stage06_anomaly_ledger.manifest.json",
    "evidence/stage07_inventory_reconcile.manifest.json",
    "evidence/step-ledger-counts.json",
    "evidence/symbol-ledger-counts.json",
    "evidence/volana-rootcause.json",
]

INPUTS = [
    "captures/reference-index-all.json",
    "captures/bars-all.ndjson.gz",
    "capture-plan/capture-plan.json",
    "capture-plan/symbols.json",
    "seed/market.db",
    "seed/market.db.lzma",
    "seed/market.db.gz",
]


def sha256_size(path):
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def rel(path):
    return os.path.relpath(path, ROOT).replace("\\", "/")


def copy_checked(src_name, dst_name, expected, rows=None):
    src = os.path.join(SRC, src_name)
    dst = os.path.join(DOCS, dst_name)
    if not os.path.isfile(src):
        raise SystemExit("stage11_deliverables: missing source %s" % rel(src))
    shutil.copyfile(src, dst)
    digest, size = sha256_size(dst)
    if digest != expected["sha256"]:
        raise SystemExit(
            "stage11_deliverables: %s sha256 %s != expected %s"
            % (dst_name, digest, expected["sha256"]))
    if "size" in expected and size != expected["size"]:
        raise SystemExit(
            "stage11_deliverables: %s size %d != expected %d"
            % (dst_name, size, expected["size"]))
    if rows is not None:
        with open(dst, encoding="utf-8", newline="") as fh:
            reader = csv.reader(fh)
            next(reader)
            count = sum(1 for _ in reader)
        if count != rows:
            raise SystemExit(
                "stage11_deliverables: %s rows %d != expected %d"
                % (dst_name, count, rows))
    return digest, size


def check_manifest(path):
    with open(path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    blob = json.dumps(manifest, ensure_ascii=False)
    if "captures/" in blob:
        raise SystemExit(
            "stage11_deliverables: manifest points at a raw capture path")
    for key in ("seed_db", "seed_lzma", "seed_gzip", "counts", "seed_manifest"):
        if key not in manifest:
            raise SystemExit(
                "stage11_deliverables: manifest missing key %r" % key)
    if manifest["counts"]["reference_derived_rows"] <= 0:
        raise SystemExit(
            "stage11_deliverables: reference_derived_rows must be positive")
    return manifest


def check_ci_record(path):
    with open(path, encoding="utf-8") as fh:
        record = json.load(fh)
    if record.get("status") not in ("PENDING_FINAL_CI", "COMPLETE"):
        raise SystemExit(
            "stage11_deliverables: unknown CI status %r" % record.get("status"))
    if record.get("status") == "PENDING_FINAL_CI" and record.get("runs"):
        raise SystemExit(
            "stage11_deliverables: a pending CI record must not carry runs")
    expected = ["guards", "python-tooling", "python-legacy"]
    if record.get("expected_workflows") != expected:
        raise SystemExit(
            "stage11_deliverables: expected_workflows must be %s" % expected)
    if record.get("status") == "COMPLETE":
        runs = record.get("runs") or []
        if not runs:
            raise SystemExit(
                "stage11_deliverables: a complete CI record needs runs")
        seen = {r.get("workflow") for r in runs}
        if seen != set(expected):
            raise SystemExit(
                "stage11_deliverables: CI record workflows %s != %s"
                % (sorted(seen), expected))
        for run in runs:
            if not run.get("url") or not run.get("run_id"):
                raise SystemExit(
                    "stage11_deliverables: CI run %r lacks url/run_id"
                    % run.get("workflow"))
            if run.get("conclusion") not in ("success", "failure"):
                raise SystemExit(
                    "stage11_deliverables: CI run %r has no conclusion"
                    % run.get("workflow"))
            for job in run.get("jobs") or []:
                if not job.get("name") or not job.get("details_url"):
                    raise SystemExit(
                        "stage11_deliverables: CI job without name/url in %r"
                        % run.get("workflow"))
    return record


def verify_report(path, record=None):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    verdict = "PHASE49_PARTIAL_WITH_EXPLICIT_BLOCKERS"
    if verdict not in text:
        raise SystemExit(
            "stage11_deliverables: report does not state the verdict %s" % verdict)
    if record and record.get("status") == "PENDING_FINAL_CI" \
            and "PENDING" not in text:
        raise SystemExit(
            "stage11_deliverables: report must disclose the pending final CI")
    if record and record.get("status") == "COMPLETE":
        if "CI-FINAL-RESULTS.json" not in text:
            raise SystemExit(
                "stage11_deliverables: report does not cite CI-FINAL-RESULTS.json")
        if record.get("commit_sha") not in text:
            raise SystemExit(
                "stage11_deliverables: report does not cite the CI commit")
    return verdict


def main():
    copy_checked("ledgers/ADJUSTMENT-EVIDENCE-LEDGER.csv",
                 "ADJUSTMENT-EVIDENCE-LEDGER.csv", STEPS_EXPECTED,
                 STEPS_EXPECTED["rows"])
    copy_checked("ledgers/HISTORY-COVERAGE-LEDGER.csv",
                 "HISTORY-COVERAGE-LEDGER.csv", SYMBOLS_EXPECTED,
                 SYMBOLS_EXPECTED["rows"])
    copy_checked("seed/FINAL-SEED-MANIFEST.json", "FINAL-SEED-MANIFEST.json",
                 MANIFEST_EXPECTED)

    manifest = check_manifest(os.path.join(DOCS, "FINAL-SEED-MANIFEST.json"))
    record = check_ci_record(os.path.join(DOCS, "CI-FINAL-RESULTS.json"))
    verdict = verify_report(os.path.join(DOCS, "FULL-VERIFICATION-REPORT.md"), record)

    for name in DELIVERABLES:
        path = os.path.join(DOCS, name)
        if not os.path.isfile(path):
            raise SystemExit("stage11_deliverables: missing deliverable %s" % name)

    lines = []
    lines.append("# Phase 4.9.1 full-verification artifact SHA-256 manifest")
    lines.append("# generated by _audit/phase49-full-verification/stage11_deliverables.py")
    lines.append("# generated_at: %s" % datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    lines.append("# verdict: %s" % verdict)
    lines.append("# ci_status: %s commit %s" % (record.get("status"),
                                                record.get("commit_sha")))
    lines.append("# seed_reference_derived_rows: %d"
                 % manifest["counts"]["reference_derived_rows"])
    lines.append("# format: sha256  size_bytes  path")
    lines.append("# section: 1=deliverables (7; this manifest is the eighth) "
                 "2=tracked evidence 3=inputs and seed artifacts")

    for name in DELIVERABLES:
        digest, size = sha256_size(os.path.join(DOCS, name))
        lines.append("%s  %d  %s" % (digest, size,
                                     "docs/opportunity-center/phase49/" + name))

    for name in EVIDENCE:
        digest, size = sha256_size(os.path.join(SRC, name))
        lines.append("%s  %d  %s" % (digest, size,
                                     "_audit/phase49-full-verification/" + name))

    for name in INPUTS:
        digest, size = sha256_size(os.path.join(SRC, name))
        lines.append("%s  %d  %s" % (digest, size,
                                     "_audit/phase49-full-verification/" + name))

    payload = "\n".join(lines) + "\n"
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(payload)

    print("DELIVERABLES OK: 7 files + manifest")
    print("steps ledger: 8,308 rows sha256 %s" % STEPS_EXPECTED["sha256"])
    print("symbols ledger: 6,103 rows sha256 %s" % SYMBOLS_EXPECTED["sha256"])
    print("seed manifest: sha256 %s size %d"
          % (MANIFEST_EXPECTED["sha256"], MANIFEST_EXPECTED["size"]))
    print("ci: %s commit %s" % (record.get("status"), record.get("commit_sha")))
    print("wrote %s (%d lines)" % (rel(OUT), len(lines)))


if __name__ == "__main__":
    main()
