#!/usr/bin/env python3
"""Phase 4.9.3 stage04: product/runtime readiness, measured honestly.

No product test is claimed here. What this stage does establish, from committed
source and a real availability census:

1. the accepted Phase 4.9.2 engine is byte-unchanged at the mission base commit;
2. exactly which table, columns, revision and source label the Runtime reads,
   with verified file:line citations (line numbers are located by searching the
   literal SQL, never guessed);
3. which inputs a genuine product test would need, and which of them are
   actually present on this machine;
4. a per-item status. Anything not executed is NOT_MEASURED, never PASS. An API
   test is never called a screenshot or a UI test.

The only market.db in the worktree is the small git-tracked dev DB (2,209
price_history rows, no adjustment tables). It is NOT the Seed Candidate and NOT
the Pilot DB, and it cannot exercise the Runtime's measured-factor path. The
Production DB under the installed app is never opened for writing.
"""

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

BASE_COMMIT = "e09ccd95d51c94082640cda75ef3de2b2008f9d2"

ENGINE_FILES = [
    "backend-go/internal/chart/measured.go",
    "backend-go/internal/chart/canonical.go",
    "backend-go/internal/chart/chartdb.go",
    "backend-go/internal/chart/handlers.go",
    "backend-go/internal/candlebuild/candlebuild.go",
    "backend-go/cmd/candlebuild/main.go",
]

# Literal fragments that pin the Runtime contract. Each is located in source so
# the reported line number is verified rather than remembered.
CONTRACT_PROBES = [
    ("runtime_factor_read", "backend-go/internal/chart/measured.go",
     "SELECT date, ratio, kind, revision FROM adjustment_factors",
     "the chart Runtime reads adjustment_factors (date, ratio, kind, revision) "
     "per symbol, ordered by date"),
    ("runtime_raw_read", "backend-go/internal/chart/measured.go",
     "SELECT date, open, high, low, close, volume FROM reference_raw",
     "the chart Runtime reads reference_raw as a separate provenance-carrying "
     "raw series; the Seed price_history is never modified"),
    ("factor_event_source", "backend-go/internal/chart/measured.go",
     'Source: "rahavard-type7-type0"',
     "measured factor events are labelled rahavard-type7-type0"),
    ("raw_row_source", "backend-go/internal/chart/measured.go",
     '"src": "rahavard-type0"',
     "reference raw rows are labelled rahavard-type0"),
    ("runtime_source_switch", "backend-go/internal/chart/chartdb.go",
     'src = "local-measured-factors"',
     "a non-empty chain revision switches the reported price-history source to "
     "local-measured-factors"),
    ("adjusted_candles_schema", "backend-go/internal/candlebuild/candlebuild.go",
     "CREATE TABLE IF NOT EXISTS adjusted_candles(",
     "candlebuild materializes adjusted_candles(symbol,date,OHLC,volume,factor,"
     "revision)"),
    ("verification_schema", "backend-go/internal/candlebuild/candlebuild.go",
     "CREATE TABLE IF NOT EXISTS adjustment_verification(",
     "candlebuild materializes adjustment_verification with status, "
     "reference_close, adjusted_close, rel_error, revision, capture_sha256"),
    ("revisions_schema", "backend-go/internal/candlebuild/candlebuild.go",
     "CREATE TABLE IF NOT EXISTS candle_build_revisions(",
     "candle_build_revisions carries per-symbol revision, capture_sha256, "
     "raw/factor/adjusted row counts, max_rel_error, worst_date, built_at"),
    ("build_driver", "backend-go/internal/candlebuild/candlebuild.go",
     "SELECT DISTINCT symbol FROM adjustment_factors",
     "the build is driven by the symbols present in adjustment_factors"),
    ("api_route", "backend-go/internal/httpapi/server.go",
     'mux.HandleFunc("GET /api/chart-db/{symbol}", srv.Chart.ChartDB)',
     "the endpoint that exercises this path is GET /api/chart-db/{symbol}"),
]

SEED = {"path": "_audit/phase49-full-verification/seed/market.db",
        "sha256": "57118e8fc99ff69c9e9812002f1d72571f357c23287fc1880a2f00b8292bbcb5",
        "bytes": 281088000, "price_history_rows": 544284, "symbols": 6103}
PILOT = {"path": "_audit/phase49-2/db/market.db",
         "sha256": "8445624f1f947d80273a18d5560ae7db6337207cc93a51242e35693be183dd2b",
         "bytes": 364670976}

REQUIRED = [
    ("seed_candidate_db", SEED["path"], SEED["bytes"],
     "the frozen Seed Candidate; must never be modified or used as a dev copy"),
    ("pilot_db", PILOT["path"], PILOT["bytes"],
     "the independent Phase 4.9.2 pilot DB; must never be copied onto the Seed"),
    ("capture_bars", "_audit/phase49-full-verification/captures/bars-all.ndjson.gz",
     None, "merged paired type0/type7 bars (licensed, gitignored)"),
    ("reference_index",
     "_audit/phase49-full-verification/captures/reference-index-all.json",
     None, "merged factor index, 759 symbols (licensed, gitignored)"),
    ("pilot_capture", "_audit/phase49-2/rahavard/pilot-capture.json", None,
     "the prior 30-symbol raw capture (licensed, gitignored)"),
]

ADJUSTMENT_TABLES = ["reference_raw", "reference_adjusted", "adjustment_factors",
                     "adjusted_candles", "adjustment_verification",
                     "candle_build_revisions"]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(rel, payload):
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    return sha256_file(path)


def _git(*args):
    return subprocess.run(["git"] + list(args), cwd=ROOT,
                          capture_output=True, text=True)


def _locate(rel, fragment):
    """Return the 1-based line number of a literal fragment, or 0 if absent."""
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        return 0
    with io.open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            if fragment in line:
                return i
    return 0


def _db_probe(path):
    """Read-only, immutable inspection. Never creates -wal/-shm, never writes."""
    import sqlite3
    uri = "file:" + path.replace("\\", "/") + "?mode=ro&immutable=1"
    con = sqlite3.connect(uri, uri=True)
    try:
        tables = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        out = {"tables": len(tables)}
        for t in ["price_history"] + ADJUSTMENT_TABLES:
            out[t] = (con.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0]
                      if t in tables else "ABSENT")
        return out
    finally:
        con.close()


def build(out_json, manifest_path):
    started = time.time()

    head = _git("rev-parse", "HEAD").stdout.strip()
    ancestry = _git("merge-base", "--is-ancestor", BASE_COMMIT, head)
    if ancestry.returncode != 0:
        print("FATAL HEAD %s does not descend from the mission base %s"
              % (head, BASE_COMMIT), file=sys.stderr)
        return 2
    engine_diff = _git("diff", "--stat", BASE_COMMIT, "--", "backend-go/")
    engine_unchanged = (engine_diff.returncode == 0
                        and not engine_diff.stdout.strip())
    if not engine_unchanged:
        print("FATAL backend-go/ differs from the mission base commit:\n%s"
              % engine_diff.stdout, file=sys.stderr)
        return 2
    engine_sha = {rel: sha256_file(os.path.join(ROOT, rel))
                  for rel in ENGINE_FILES}

    contract, missing_probes = [], []
    for name, rel, fragment, meaning in CONTRACT_PROBES:
        line = _locate(rel, fragment)
        if not line:
            missing_probes.append({"probe": name, "file": rel,
                                   "fragment": fragment})
        contract.append({"probe": name, "file": rel, "line": line,
                         "citation": "%s:%d" % (rel, line) if line else "",
                         "meaning": meaning, "located": bool(line)})
    if missing_probes:
        print("FATAL runtime contract probe not found in source: %s"
              % json.dumps(missing_probes, ensure_ascii=False), file=sys.stderr)
        return 2

    availability = []
    for name, rel, want_bytes, why in REQUIRED:
        path = os.path.join(ROOT, rel)
        present = os.path.exists(path)
        rec = {"name": name, "path": rel, "present": present, "why": why}
        if present:
            rec["bytes"] = os.path.getsize(path)
            rec["sha256"] = sha256_file(path)
            if want_bytes is not None:
                rec["bytes_match_recorded"] = rec["bytes"] == want_bytes
        else:
            rec["bytes"] = None
            rec["sha256"] = None
            rec["block"] = "ABSENT_FROM_THIS_MACHINE"
        availability.append(rec)

    # The only DB actually present in the worktree: the git-tracked dev DB.
    tracked_db = os.path.join(ROOT, "market.db")
    tracked = {"path": "market.db",
               "git_tracked": _git("ls-files", "--error-unmatch",
                                   "market.db").returncode == 0,
               "bytes": os.path.getsize(tracked_db),
               "sha256": sha256_file(tracked_db),
               "schema": _db_probe(tracked_db)}
    tracked["is_seed_candidate"] = tracked["sha256"] == SEED["sha256"]
    tracked["is_pilot_db"] = tracked["sha256"] == PILOT["sha256"]
    tracked["carries_adjustment_tables"] = all(
        tracked["schema"].get(t) != "ABSENT" for t in ADJUSTMENT_TABLES)
    tracked["can_exercise_measured_factor_path"] = (
        tracked["schema"].get("adjustment_factors") not in ("ABSENT", 0))

    # A genuine product test needs a Runtime-compatible DB. None is available.
    can_product_test = (tracked["can_exercise_measured_factor_path"]
                        and any(a["present"] for a in availability
                                if a["name"] == "capture_bars"))

    items = [
        ("runtime_contract_identified", "PASS",
         "table, columns, revision, source label and API route located in "
         "committed source with verified line numbers"),
        ("engine_byte_unchanged", "PASS",
         "git diff of backend-go/ against the mission base commit is empty; "
         "the stage aborts if it is not"),
        ("isolated_working_db_created", "NOT_MEASURED",
         "no Seed/Pilot DB and no capture bytes on this machine; creating a "
         "copy would require fabricating inputs, which the mission forbids"),
        ("candles_table_compared", "NOT_MEASURED",
         "adjusted_candles absent from every DB present here"),
        ("factors_table_compared", "NOT_MEASURED",
         "adjustment_factors absent from every DB present here"),
        ("api_path_exercised", "NOT_MEASURED",
         "GET /api/chart-db/{symbol} identified but not called: no "
         "Runtime-compatible DB to serve the new cohort"),
        ("chart_ui_screenshot", "NOT_MEASURED",
         "no real UI screenshot was taken; an API test is never reported as a "
         "screenshot or a UI test"),
        ("seed_release_gate_rerun", "NOT_MEASURED",
         "the Seed Candidate is absent and must not be modified; the gate is "
         "not re-run and its threshold is not changed"),
    ]
    if can_product_test:
        print("FATAL availability says a product test is possible but this "
              "stage hard-codes NOT_MEASURED; re-derive the statuses",
              file=sys.stderr)
        return 2

    payload = {
        "schema": "phase49-3-product-readiness-v1",
        "stage": "stage04_product_readiness",
        "code_commit": BASE_COMMIT,
        "base_commit": BASE_COMMIT,
        "engine": {"files": engine_sha, "byte_unchanged_vs_base": engine_unchanged,
                   "diff_stdout": engine_diff.stdout.strip()},
        "runtime_contract": {
            "reads_table": "adjustment_factors",
            "reads_columns": ["date", "ratio", "kind", "revision"],
            "raw_table": "reference_raw",
            "revision_effect": ("a non-empty chain revision switches the "
                                "reported source to local-measured-factors"),
            "materialized_by_candlebuild": ["adjusted_candles",
                                            "adjustment_verification",
                                            "candle_build_revisions"],
            "api_route": "GET /api/chart-db/{symbol}",
            "probes": contract,
            "note": ("the Runtime reads adjustment_factors and reference_raw "
                     "directly; adjusted_candles is the materialized build "
                     "output, not the Runtime's read path"),
        },
        "required_inputs": availability,
        "seed_candidate_recorded": SEED,
        "pilot_db_recorded": PILOT,
        "only_db_present": tracked,
        "production_db": {
            "path": ("C:/Users/PCMOD/AppData/Local/Programs/"
                     "BorsTerminal Ultimate/market.db"),
            "opened_for_write": False,
            "note": ("the installed app's DB carries an active -wal and -shm; "
                     "it was never opened, copied or modified by this mission"),
        },
        "product_test_possible": can_product_test,
        "items": [{"item": n, "status": s, "basis": b} for n, s, b in items],
        "status_counts": {s: sum(1 for _, x, _ in items if x == s)
                          for s in ("PASS", "PARTIAL", "BLOCKED", "NOT_MEASURED")},
        "isolated_copy_plan": {
            "precondition": "restore the licensed capture artifacts first",
            "steps": [
                "verify SHA-256 of bars-all.ndjson.gz and "
                "reference-index-all.json against the recorded values",
                "create a NEW working copy under _audit/phase49-3/db/ from the "
                "restored Seed bytes; never write to the Seed Candidate path "
                "and never copy the Pilot DB onto it",
                "record the working copy's own SHA-256 and revision before and "
                "after ingest",
                "ingest reference_raw + reference_adjusted for the frozen 30 "
                "with independent provenance",
                "build adjustment_factors with the accepted Phase 4.9.2 logic",
                "run cmd/candlebuild -db <working copy> to materialize "
                "adjusted_candles + adjustment_verification + "
                "candle_build_revisions",
                "compare every OHLC against reference_adjusted; check volume "
                "constancy; prove revision, update chain and idempotency",
                "only then call GET /api/chart-db/{symbol} on the working copy, "
                "and take a real UI screenshot if a browser is available",
            ],
            "forbidden": ["modifying the Seed Candidate",
                          "modifying the Production DB",
                          "copying either red-line DB onto the other",
                          "fabricating capture data",
                          "loosening any acceptance tolerance"],
        },
        "inputs": {rel: sha256_file(os.path.join(ROOT, rel))
                   for rel in ENGINE_FILES},
    }
    sha_json = write_json(out_json, payload)
    manifest = {
        "schema": "phase49-3-stage-manifest-v1",
        "stage": "stage04_product_readiness",
        "script": "_audit/phase49-3/stage04_product_readiness.py",
        "script_sha256": sha256_file(os.path.abspath(__file__)),
        "code_commit": BASE_COMMIT,
        "inputs": payload["inputs"],
        "outputs": {out_json: sha_json},
        "row_counts": {"contract_probes": len(contract),
                       "required_inputs": len(availability),
                       "status_items": len(items)},
        "runtime_seconds": round(time.time() - started, 3),
        "status": "PASS_CONTRACT_ONLY",
        "product_test_status": "NOT_MEASURED",
        "deterministic": True,
        "clock_in_payload": False,
    }
    write_json(manifest_path, manifest)
    print("stage04 OK: engine byte_unchanged=%s, %d contract probes located"
          % (engine_unchanged, len(contract)))
    print("  only DB present: market.db %d bytes, price_history=%s, "
          "adjustment_factors=%s" % (tracked["bytes"],
                                     tracked["schema"]["price_history"],
                                     tracked["schema"]["adjustment_factors"]))
    print("  is_seed=%s is_pilot=%s carries_adjustment_tables=%s"
          % (tracked["is_seed_candidate"], tracked["is_pilot_db"],
             tracked["carries_adjustment_tables"]))
    print("  required inputs present: %d/%d"
          % (sum(1 for a in availability if a["present"]), len(availability)))
    print("  statuses: %s" % json.dumps(payload["status_counts"]))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-json",
                    default="_audit/phase49-3/evidence/product-readiness.json")
    ap.add_argument("--manifest",
                    default="_audit/phase49-3/manifests/stage04_product_readiness.manifest.json")
    a = ap.parse_args()
    return build(a.out_json, a.manifest)


if __name__ == "__main__":
    sys.exit(main())