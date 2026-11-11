#!/usr/bin/env python3
"""Phase 4.9.3 coverage-expansion map over all 6,103 history symbols.

Builds the per-symbol matrix from committed, hash-verified Phase 4.9/4.9.2
ledgers only. It never opens a market DB and never writes to one, so it runs
on a machine where the gitignored capture/DB artifacts are absent.

Why a new script: build_coverage_ledger.py (phase49-2) requires the pilot DB
and capture-plan/capture-unmapped.json, neither of which is committed. This
script reproduces its priority classification from the committed
COVERAGE-STATUS.csv and joins the raw overlapping causes back onto it.

Deterministic: no clock reads in the CSV/JSON payload, so a rerun is
byte-identical. The manifest carries the run time separately.
"""
import argparse
import collections
import csv
import hashlib
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HISTORY = "docs/opportunity-center/phase49/HISTORY-COVERAGE-LEDGER.csv"
STEPS = "docs/opportunity-center/phase49/ADJUSTMENT-EVIDENCE-LEDGER.csv"
COVERAGE = "_audit/phase49-2/ledgers/COVERAGE-STATUS.csv"
COVERAGE_JSON = "_audit/phase49-2/evidence/coverage-status.json"
CAPTURE = "_audit/phase49-full-verification/evidence/capture-summary.json"
LEDGER_COUNTS = "_audit/phase49-full-verification/evidence/ledger-counts.json"
AVAILABILITY = "_audit/phase49-full-verification/evidence/backfill-availability.json"

OUT_DIR = "_audit/phase49-3"
MAP_CSV = os.path.join(OUT_DIR, "ledgers", "COVERAGE-EXPANSION-MAP.csv")
RECON_JSON = os.path.join(OUT_DIR, "evidence", "coverage-reconciliation.json")
MANIFEST = os.path.join(OUT_DIR, "manifests", "stage01_coverage_map.manifest.json")

# Recorded in phase49-full-verification/evidence/ledger-counts.json.
EXPECTED_SHA = {
    HISTORY: "c3ad3741daaa55b849fb51aca7cc066ea859d0469de2eb85d82471988a69a650",
    STEPS: "c0ab45bf60ba8d95fa4f4f33d60d4fa6f465a62c07271053c8ca7781f5114a28",
}

# Phase 4.9.2 status priority, highest first (build_coverage_ledger.py:77-90).
PRIORITY = ["READY_PILOT", "QUEUE_UNMAPPED_ASSET_ID", "QUEUE_NO_INSTRUMENTS",
            "QUEUE_HALTED", "QUEUE_NO_REFERENCE", "QUEUE_REFERENCE_ONLY"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def read_json(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return json.load(fh)


def as_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def source_rows(raw):
    try:
        d = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return d if isinstance(d, dict) else {}


FIELDS = [
    "symbol", "key", "ins_code", "isin", "asset_id", "identity_status",
    "instrument_candidates", "instrument_status", "instrument_state_date",
    "asset_id_state", "stale_status", "stale_basis", "sessions_behind",
    "latest_session", "ref_coverage", "ref_type0_bars", "ref_first", "ref_last",
    "paired_type0_type7_evidenced", "window_span_ok", "session_completeness",
    "seed_price_rows", "seed_trading_sessions", "seed_duplicate_dates",
    "seed_first_date", "seed_last_date", "raw_ohlc_valid", "anomalies",
    "invalid_ohlc_legacy", "gaps", "legacy_unknown_rows", "rahavard365_rows",
    "board_rows", "price_basis_risk", "step_rows", "factor_steps",
    "factor_verified", "factor_reconstructed", "factor_unverified",
    "factor_conflict", "factor_partial", "factor_insufficient",
    "adjusted_available", "evidence_tier", "event_coverage", "official_o1",
    "official_o1_in_range", "ledger_final_status", "ledger_remaining_blocker",
    "phase49_2_status", "phase49_2_queue_reason", "ingestable_raw_rows",
    "history_gain_rows", "verification_eligible", "recovery_class",
    "block_cause", "required_source", "local_capture_bytes",
    "pilot_raw_rows", "pilot_factors", "pilot_adjusted_rows",
    "pilot_verified_exact", "pilot_max_rel_error", "pilot_revision",
]


def classify(h, cov, pilot_syms, unmapped_syms):
    """Reproduce the phase49-2 priority ladder from raw causes."""
    sym = h["symbol"]
    if sym in pilot_syms:
        return "READY_PILOT", ""
    if sym in unmapped_syms:
        return "QUEUE_UNMAPPED_ASSET_ID", "NO_ASSET_ID"
    if h["identity_status"] == "unresolved_no_instruments":
        return "QUEUE_NO_INSTRUMENTS", "NO_INSTRUMENTS_ROW"
    if h["stale_status"] == "halted":
        return "QUEUE_HALTED", "INSTRUMENT_STATE_HALTED"
    if h["ref_coverage"] == "none":
        return ("QUEUE_NO_REFERENCE",
                "NO_REFERENCE_WINDOW;NO_PACK_STEPS"
                if h["step_rows"] == "0" else "NO_REFERENCE_WINDOW")
    return "QUEUE_REFERENCE_ONLY", "FACTORS_NOT_INGESTED"


def recovery(h, status, paired, session_ok):
    """Recovery class, block cause and the source needed to unblock.

    Two independent layers are kept apart on purpose:
      * whether a paired type0/type7 capture is EVIDENCED for the symbol;
      * whether those capture BYTES are present on this machine.
    A symbol can be recoverable from existing capture and still be blocked
    locally because the licensed bytes are not here.
    """
    if status == "READY_PILOT":
        return ("ALREADY_VERIFIED", "", "none", "PRESENT_IN_PILOT_DB")
    if status == "QUEUE_UNMAPPED_ASSET_ID":
        return ("NEEDS_ASSET_ID_MAPPING", "NO_MAPPABLE_RAHAVARD_ASSET_ID",
                "asset-id mapping for the instrument (owner/reference identity)",
                "ABSENT")
    if status == "QUEUE_NO_INSTRUMENTS":
        return ("NEEDS_IDENTITY_RESOLUTION", "NO_INSTRUMENTS_ROW",
                "instruments row / identity resolution (TSETMC instrument master)",
                "ABSENT")
    if status == "QUEUE_HALTED":
        if paired:
            return ("RECOVERABLE_HALTED_EXISTING_CAPTURE",
                    "INSTRUMENT_STATE_HALTED",
                    "owner ruling on halted symbols; capture already evidenced",
                    "ABSENT")
        return ("NEEDS_HALT_RULING_AND_CAPTURE",
                "INSTRUMENT_STATE_HALTED;NO_REFERENCE_WINDOW",
                "owner ruling on halted symbols + new paired capture", "ABSENT")
    if status == "QUEUE_REFERENCE_ONLY":
        cause = "FACTORS_NOT_INGESTED"
        if not session_ok:
            cause += ";REFERENCE_SESSIONS_FEWER_THAN_LOCAL"
        return ("RECOVERABLE_EXISTING_CAPTURE", cause,
                "ingest of the already-captured paired type0/type7 series",
                "ABSENT")
    # QUEUE_NO_REFERENCE
    return ("NEEDS_NEW_CAPTURE", "NO_REFERENCE_WINDOW",
            "new paired type0/type7 capture from an authorised Rahavard session",
            "ABSENT")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    t0 = time.time()

    inputs = {}
    for rel in (HISTORY, STEPS, COVERAGE, COVERAGE_JSON, CAPTURE,
                LEDGER_COUNTS, AVAILABILITY):
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            print("FATAL missing input: %s" % rel, file=sys.stderr)
            return 2
        inputs[rel] = {"sha256": sha256(p), "bytes": os.path.getsize(p)}
    for rel, want in EXPECTED_SHA.items():
        got = inputs[rel]["sha256"]
        if got != want:
            print("FATAL sha mismatch %s\n want %s\n got  %s"
                  % (rel, want, got), file=sys.stderr)
            return 2

    hist = read_csv(HISTORY)
    cov_rows = read_csv(COVERAGE)
    cov = {r["symbol"]: r for r in cov_rows}
    H = {r["symbol"]: r for r in hist}
    if set(H) != set(cov):
        print("FATAL symbol-set mismatch between ledgers", file=sys.stderr)
        return 2
    if len(hist) != 6103 or len(H) != 6103:
        print("FATAL expected 6103 unique history symbols, got %d/%d"
              % (len(hist), len(H)), file=sys.stderr)
        return 2

    pilot_syms = {r["symbol"] for r in cov_rows if r["status"] == "READY_PILOT"}
    unmapped_syms = {r["symbol"] for r in cov_rows
                     if r["status"] == "QUEUE_UNMAPPED_ASSET_ID"}

    capture = read_json(CAPTURE)
    counts = read_json(LEDGER_COUNTS)
    avail = read_json(AVAILABILITY)

    # Per-symbol type0 bar counts for the freshness/backfill plans are only
    # committed for the six backfill symbols; the 644 freshness list lives in a
    # gitignored CSV. Record that boundary instead of guessing.
    six = {r["symbol"]: r for r in avail.get("six", [])}

    out = []
    for sym in sorted(H):
        h = H[sym]
        c = cov[sym]
        status, reason = classify(h, c, pilot_syms, unmapped_syms)
        if status != c["status"] or reason != c["queue_reason"]:
            print("FATAL classification drift for %s: %s/%s vs %s/%s"
                  % (sym, status, reason, c["status"], c["queue_reason"]),
                  file=sys.stderr)
            return 2

        src = source_rows(h["source_coverage"])
        legacy = as_int(src.get("legacy-unknown"))
        ref_bars = as_int(h["ref_days"])
        sessions = as_int(h["trading_sessions"])
        # ref_coverage=="full" is defined in stage05_symbol_ledger.py:592-597 as
        # BOTH type0 and type7 spanning the local first/last date. It is a span
        # guarantee, not a per-session completeness guarantee.
        paired = h["ref_coverage"] == "full"
        span_ok = paired
        if not paired:
            completeness = "NO_REFERENCE"
        elif ref_bars > sessions:
            completeness = "REFERENCE_SUPERSET"
        elif ref_bars == sessions:
            completeness = "EQUAL"
        else:
            completeness = "REFERENCE_MISSING_%d_SESSIONS" % (sessions - ref_bars)
        session_ok = ref_bars >= sessions
        cls, cause, need, local = recovery(h, status, paired, session_ok)
        ingestable = ref_bars if paired else 0

        out.append({
            "symbol": sym, "key": h["key"], "ins_code": h["ins_code"],
            "isin": h["isin"], "asset_id": h["asset_id"],
            "identity_status": h["identity_status"],
            "instrument_candidates": h["instrument_candidates"],
            "instrument_status": h["instrument_status"],
            "instrument_state_date": h["instrument_state_date"],
            "asset_id_state": ("UNMAPPED" if sym in unmapped_syms
                               else ("MAPPED" if h["asset_id"] else "EMPTY")),
            "stale_status": h["stale_status"], "stale_basis": h["stale_basis"],
            "sessions_behind": h["sessions_behind"],
            "latest_session": h["latest_session"],
            "ref_coverage": h["ref_coverage"], "ref_type0_bars": ref_bars,
            "ref_first": h["ref_first"], "ref_last": h["ref_last"],
            "paired_type0_type7_evidenced": "YES" if paired else "NO",
            "window_span_ok": "YES" if span_ok else "NO",
            "session_completeness": completeness,
            "seed_price_rows": h["rows"],
            "seed_trading_sessions": h["trading_sessions"],
            "seed_duplicate_dates": h["duplicate_dates"],
            "seed_first_date": h["first_date"], "seed_last_date": h["last_date"],
            "raw_ohlc_valid": h["raw_ohlc_valid"], "anomalies": h["anomalies"],
            "invalid_ohlc_legacy": c["invalid_ohlc_legacy"], "gaps": h["gaps"],
            "legacy_unknown_rows": legacy,
            "rahavard365_rows": as_int(src.get("rahavard365")),
            "board_rows": as_int(src.get("board")),
            "price_basis_risk": ("LEGACY_UNKNOWN_PRESENT" if legacy else "NONE"),
            "step_rows": h["step_rows"], "factor_steps": h["factor_steps"],
            "factor_verified": h["factor_verified"],
            "factor_reconstructed": h["factor_reconstructed"],
            "factor_unverified": h["factor_unverified"],
            "factor_conflict": h["factor_conflict"],
            "factor_partial": h["factor_partial"],
            "factor_insufficient": h["factor_insufficient"],
            "adjusted_available": h["adjusted_available"],
            "evidence_tier": h["evidence_tier"],
            "event_coverage": h["event_coverage"],
            "official_o1": h["official_o1"],
            "official_o1_in_range": h["official_o1_in_range"],
            "ledger_final_status": h["final_status"],
            "ledger_remaining_blocker": h["remaining_blocker"],
            "phase49_2_status": status, "phase49_2_queue_reason": reason,
            "ingestable_raw_rows": ingestable,
            "history_gain_rows": (ingestable - as_int(h["rows"])
                                  if paired else ""),
            # Eligibility to ENTER compute+verification, not a PASS verdict.
            "verification_eligible": (
                "YES" if (paired and h["identity_status"] == "resolved_instruments"
                          and h["raw_ohlc_valid"] == "ok") else "NO"),
            "recovery_class": cls, "block_cause": cause,
            "required_source": need, "local_capture_bytes": local,
            "pilot_raw_rows": c["pilot_raw_rows"],
            "pilot_factors": c["pilot_factors"],
            "pilot_adjusted_rows": c["pilot_adjusted_rows"],
            "pilot_verified_exact": c["pilot_verified_exact"],
            "pilot_max_rel_error": c["pilot_max_rel_error"],
            "pilot_revision": c["pilot_revision"],
        })

    # ---- denominator reconciliation, asserted not asserted-by-comment ----
    noref = {s for s, r in H.items() if r["ref_coverage"] == "none"}
    ref = {s for s, r in H.items() if r["ref_coverage"] == "full"}
    noinst = {s for s, r in H.items()
              if r["identity_status"] == "unresolved_no_instruments"}
    halted = {s for s, r in H.items() if r["stale_status"] == "halted"}
    zero = {s for s, r in H.items() if as_int(r["step_rows"]) == 0}

    def split(base, exclude=()):
        ex = set().union(*exclude) if exclude else set()
        rem = base - ex
        return rem

    nr_unmapped = noref & unmapped_syms
    nr_noinst = split(noref, (unmapped_syms,)) & noinst
    nr_halted = split(noref, (unmapped_syms, noinst)) & halted
    nr_final = split(noref, (unmapped_syms, noinst, halted, pilot_syms))
    rf_pilot = ref & pilot_syms
    rf_halted = split(ref, (pilot_syms, unmapped_syms, noinst)) & halted
    rf_final = split(ref, (unmapped_syms, noinst, halted, pilot_syms))
    z_noref = zero & noref
    byst = {r["symbol"]: r["phase49_2_status"] for r in out}

    recon = {
        "schema": "phase49-3-coverage-reconciliation-v1",
        "universe": {"history_symbols": len(out),
                     "definition": "one row per price_history symbol"},
        "status_counts": dict(collections.Counter(r["phase49_2_status"]
                                                 for r in out)),
        "priority_ladder": PRIORITY,
        "raw_cause_sizes": {
            "ref_coverage_none": len(noref), "ref_coverage_full": len(ref),
            "unresolved_no_instruments": len(noinst), "stale_halted": len(halted),
            "unmapped_asset_id_in_history": len(unmapped_syms),
            "zero_step_rows": len(zero),
        },
        "ref_none_to_queue_no_reference": {
            "ref_coverage_none": len(noref),
            "absorbed_unmapped": len(nr_unmapped),
            "absorbed_no_instruments": len(nr_noinst),
            "absorbed_halted": len(nr_halted),
            "queue_no_reference": len(nr_final),
            "identity_holds": (len(nr_unmapped) + len(nr_noinst)
                               + len(nr_halted) + len(nr_final)) == len(noref),
        },
        "ref_full_to_queue_reference_only": {
            "ref_coverage_full": len(ref), "ready_pilot": len(rf_pilot),
            "absorbed_halted": len(rf_halted),
            "queue_reference_only": len(rf_final),
            "identity_holds": (len(rf_pilot) + len(rf_halted)
                               + len(rf_final)) == len(ref),
        },
        "halted_to_queue_halted": {
            "stale_halted": len(halted),
            "absorbed_unmapped_or_no_instruments": len(halted & (unmapped_syms | noinst)),
            "ready_pilot_halted": len(halted & pilot_syms),
            "ready_pilot_halted_symbols": sorted(halted & pilot_syms),
            "queue_halted": len(halted - unmapped_syms - noinst - pilot_syms),
        },
        "no_reference_window_5185_vs_3308": {
            "definition_5185": "zero pack step rows AND ref_coverage none",
            "zero_step_and_ref_none": len(z_noref),
            "matches_recorded_5185": len(z_noref) == counts[
                "validity_reconciliation"]["unverified_rows_no_reference_remaining"],
            "split_by_final_status": dict(collections.Counter(byst[s] for s in z_noref)),
            "definition_3308": "ref_coverage none surviving the priority ladder",
            "queue_no_reference": len(nr_final),
            "queue_no_reference_zero_step": sum(
                1 for s in nr_final if as_int(H[s]["step_rows"]) == 0),
            "queue_no_reference_with_steps": sum(
                1 for s in nr_final if as_int(H[s]["step_rows"]) > 0),
            "ref_none_with_steps": len(noref - zero),
            "ref_none_with_steps_split": dict(collections.Counter(
                byst[s] for s in (noref - zero))),
            "zero_step_with_reference": len(zero - noref),
            "zero_step_with_reference_symbols": sorted(zero - noref),
            "note": ("5185 and 3308 are different populations, not a contradiction: "
                     "5185 counts zero-step symbols without a reference window "
                     "before the priority ladder; 3308 counts reference-less "
                     "symbols after identity/asset-id/halt have been peeled off. "
                     "3308 = 3219 zero-step + 89 with pack steps."),
        },
        "capture_evidence": {
            "merged_symbols": capture["totals"]["merged_symbols"],
            "paired_bars_per_type": capture["merged"]["per_type"],
            "daily_bars": capture["merged"]["per_resolution"]["D"],
            "bars_file": capture["merged"]["bars_file"],
            "bars_container_sha256": capture["merged"]["bars_container_sha256"],
            "index_file": capture["merged"]["index_file"],
            "index_sha256": capture["merged"]["reference_index_all"]["sha256"],
            "index_factor_changes": capture["merged"]["reference_index_all"]["factor_changes"],
            "index_factor_days": capture["merged"]["reference_index_all"]["factor_days"],
            "sum_ref_type0_bars_over_ref_full": sum(
                as_int(r["ref_days"]) for r in H.values()
                if r["ref_coverage"] == "full"),
            "raw_capture_committed": capture["raw_capture_committed"],
        },
        "session_completeness": {
            "definition": ("ref_coverage full guarantees type0 AND type7 span the "
                           "local first/last date; it does not guarantee one "
                           "reference bar per local session"),
            "counts": dict(collections.Counter(
                r["session_completeness"].split("_MISSING_")[0]
                if "_MISSING_" in r["session_completeness"] else r["session_completeness"]
                for r in out)),
            "ref_full_missing_sessions_symbols": [
                {"symbol": r["symbol"], "seed_trading_sessions": r["seed_trading_sessions"],
                 "ref_type0_bars": r["ref_type0_bars"],
                 "missing": as_int(r["seed_trading_sessions"]) - as_int(r["ref_type0_bars"])}
                for r in out if "_MISSING_" in r["session_completeness"]],
        },
        "history_expansion": {
            "pilot_seed_rows": sum(as_int(H[s]["rows"]) for s in pilot_syms),
            "pilot_ingested_rows": sum(as_int(cov[s]["pilot_raw_rows"]) for s in pilot_syms),
            "pilot_ref_days_equals_ingested_for_all_30": all(
                as_int(H[s]["ref_days"]) == as_int(cov[s]["pilot_raw_rows"])
                for s in pilot_syms),
            "queue_reference_only_seed_rows": sum(as_int(H[s]["rows"]) for s in rf_final),
            "queue_reference_only_type0_bars": sum(as_int(H[s]["ref_days"]) for s in rf_final),
            "queue_reference_only_halted_type0_bars": sum(
                as_int(H[s]["ref_days"]) for s in rf_halted),
        },
        "recovery_class_counts": dict(collections.Counter(r["recovery_class"]
                                                          for r in out)),
        "verification_eligible_counts": dict(collections.Counter(
            r["verification_eligible"] for r in out)),
        "local_artifact_state": {
            "note": ("gitignored licensed captures and both Phase 4.9 DBs are absent "
                     "from this machine; every ingestable row count below is an "
                     "EVIDENCED EXPECTATION from the committed index, not a local "
                     "measurement"),
            "seed_candidate_db": "_audit/phase49-full-verification/seed/market.db",
            "pilot_db": "_audit/phase49-2/db/market.db",
            "capture_bars": capture["merged"]["bars_file"],
            "reference_index": capture["merged"]["index_file"],
        },
        "backfill_six_per_symbol_bars": six,
        "freshness_plan": {"planned": avail["planned"]["freshness"],
                           "available": avail["available"]["freshness"],
                           "per_symbol_counts_committed": False},
    }

    for key in ("ref_none_to_queue_no_reference", "ref_full_to_queue_reference_only"):
        if not recon[key]["identity_holds"]:
            print("FATAL reconciliation identity failed: %s" % key, file=sys.stderr)
            return 2

    map_path = os.path.join(ROOT, args.out_dir, "ledgers",
                            "COVERAGE-EXPANSION-MAP.csv")
    recon_path = os.path.join(ROOT, args.out_dir, "evidence",
                              "coverage-reconciliation.json")
    man_path = os.path.join(ROOT, args.out_dir, "manifests",
                            "stage01_coverage_map.manifest.json")
    for p in (map_path, recon_path, man_path):
        os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(map_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    with open(recon_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(recon, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")

    manifest = {
        "schema": "phase49-3-stage-manifest-v1",
        "stage": "stage01_coverage_map",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_ms": round((time.time() - t0) * 1000, 1),
        "inputs": inputs,
        "outputs": {
            os.path.relpath(map_path, ROOT).replace("\\", "/"): {
                "sha256": sha256(map_path), "rows": len(out),
                "bytes": os.path.getsize(map_path)},
            os.path.relpath(recon_path, ROOT).replace("\\", "/"): {
                "sha256": sha256(recon_path),
                "bytes": os.path.getsize(recon_path)},
        },
        "db_written": False,
        "status": "PASS",
        "idempotent_payload": True,
    }
    with open(man_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")

    if not args.quiet:
        print("rows:", len(out))
        print("status:", json.dumps(recon["status_counts"], ensure_ascii=False))
        print("recovery:", json.dumps(recon["recovery_class_counts"], ensure_ascii=False))
        print("eligible:", json.dumps(recon["verification_eligible_counts"]))
        print("identities hold:",
              recon["ref_none_to_queue_no_reference"]["identity_holds"],
              recon["ref_full_to_queue_reference_only"]["identity_holds"])
        print("wrote", map_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())