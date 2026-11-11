#!/usr/bin/env python3
"""Phase 4.9.2 baseline: branch identity + the exact blocker counts.

Read-only. The counts are recomputed from the committed Phase 4.9.1 ledgers and
evidence so the new mission never trusts a hand-typed number.
"""
import csv
import json
import os
import subprocess
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "_audit", "phase49-2", "evidence", "baseline.json")
LEDGERS = os.path.join(ROOT, "_audit", "phase49-full-verification", "ledgers")
EVID = os.path.join(ROOT, "_audit", "phase49-full-verification", "evidence")
HERE = os.path.join(ROOT, "_audit", "phase49-2", "evidence")


def git(*args):
    return subprocess.check_output(["git"] + list(args), cwd=ROOT, text=True).strip()


def csv_rows(name):
    with open(os.path.join(LEDGERS, name), encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def main():
    steps = csv_rows("ADJUSTMENT-EVIDENCE-LEDGER.csv")
    symbols = csv_rows("HISTORY-COVERAGE-LEDGER.csv")
    anomalies = json.load(open(os.path.join(EVID, "anomaly-counts.json"), encoding="utf-8"))
    post = json.load(open(os.path.join(EVID, "post-backfill-anomalies.json"), encoding="utf-8"))
    baseline_unverified = json.load(open(os.path.join(
        HERE, "baseline-unverified-steps.json"), encoding="utf-8"))
    seed_manifest = json.load(open(os.path.join(
        ROOT, "docs", "opportunity-center", "phase49", "FINAL-SEED-MANIFEST.json"),
        encoding="utf-8"))
    unmapped = json.load(open(os.path.join(
        ROOT, "_audit", "phase49-full-verification", "capture-plan",
        "capture-unmapped.json"), encoding="utf-8"))

    step_status = Counter(r["final_status"] for r in steps)
    symbol_status = Counter(r["final_status"] for r in symbols)
    zero_reference = sum(1 for r in symbols if r["ref_coverage"] == "none")
    zero_reference_zero_step = sum(
        1 for r in symbols if r["ref_coverage"] == "none" and r["step_rows"] == "0")
    halted = sum(1 for r in symbols if r["stale_status"] == "halted")
    no_instruments = sum(
        1 for r in symbols if r["identity_status"] == "unresolved_no_instruments")
    post_events = post.get("events") or []

    out = {
        "schema": "phase49-2-baseline-v1",
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "head": git("rev-parse", "HEAD"),
        "main": git("rev-parse", "main"),
        "worktree_dirty": bool(git("status", "--short")),
        "counts": {
            "step_rows": len(steps),
            "step_status": dict(step_status),
            "baseline_unverified_rows": baseline_unverified["subset_rows"],
            "still_unverified_steps": baseline_unverified["still_unverified"],
            "became_verified_steps": baseline_unverified["became_verified"],
            "symbol_rows": len(symbols),
            "symbol_status": dict(symbol_status),
            "symbols_without_reference_coverage": zero_reference,
            "symbols_without_reference_and_step": zero_reference_zero_step,
            "halted_symbols": halted,
            "symbols_without_instruments": no_instruments,
            "unmapped_asset_symbols": len(unmapped),
            "reference_derived_rows": seed_manifest["counts"]["reference_derived_rows"],
            "seed_rows": seed_manifest["counts"]["price_history_rows"],
            "rows_added_vs_base": seed_manifest["counts"]["rows_added_vs_base"],
            "anomaly_events": anomalies["anomaly_events"],
            "anomaly_by_kind": anomalies["by_kind"],
            "anomaly_unresolved_gap": anomalies["residual_unverified"]["by_category"][
                "UNRESOLVED_SOURCE_GAP"],
            "anomaly_unresolved_by_kind": anomalies["residual_unverified"]["by_kind"],
            "invalid_ohlc_rows": anomalies["invalid_ohlc"]["rows"],
            "invalid_ohlc_by_root_cause": anomalies["invalid_ohlc"]["by_root_cause"],
            "post_backfill_events": len(post_events),
            "post_backfill_blockers": post["counts"]["blockers"],
            "post_backfill_blocker_dates": post["counts"]["blocker_dates"],
        },
        "source_files": {
            "steps_ledger_sha256": "c0ab45bf60ba8d95fa4f4f33d60d4fa6f465a62c07271053c8ca7781f5114a28",
            "symbols_ledger_sha256": "c3ad3741daaa55b849fb51aca7cc066ea859d0469de2eb85d82471988a69a650",
            "seed_manifest_sha256": "6a930818b05f3ef180064e7c8c908830bac5a72d89b28111dd43fba9cb859aa7",
        },
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(json.dumps(out["counts"], ensure_ascii=False, indent=1))
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
