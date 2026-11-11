#!/usr/bin/env python3
"""Phase 4.9.3 stage03: what is still measurable for the frozen 30-symbol cohort.

The paired type0/type7 capture bytes are absent from this machine (licensed,
gitignored by design). This stage therefore does NOT compute candles, factors or
parity. It extracts the event-ratio witness evidence that Phase 4.9
full-verification already measured and committed, re-keys it onto the frozen
cohort with the project's standard identity key, and records the candle-level
block precisely.

Two distinct things are reported and never conflated:

* ``event_level`` -- witness agreement per adjustment step, already measured by
  ``stage03_step_ledger.py`` against the frozen tolerances (FACTOR_EXACT 1e-3,
  FACTOR_MATERIAL 1e-2, STEP_DATE_SHIFT_MAX_DAYS 5). Extracted, not re-measured.
* ``candle_level`` -- OHLC parity / volume constancy / revision / idempotency.
  BLOCKED: requires the capture bytes and a working DB copy.

The join is validated, not assumed: grouping the evidence ledger by
``symbol_identity.key`` must reproduce the history ledger's ``step_rows`` and
``factor_steps`` for every cohort symbol, which is the same grouping
``stage05_symbol_ledger.py`` performs. Any drift aborts the stage.

Inputs are pinned by SHA-256. No clock value enters any payload; the run time
lives only in the manifest. Reruns are byte-identical.
"""

import argparse
import collections
import csv
import hashlib
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
_DEV = os.path.join(ROOT, "dev")
while _DEV in sys.path:
    sys.path.remove(_DEV)
sys.path.insert(0, _DEV)  # dev/symbol_identity wins over the root shim

from symbol_identity import key  # noqa: E402

HISTORY = "docs/opportunity-center/phase49/HISTORY-COVERAGE-LEDGER.csv"
STEPS = "docs/opportunity-center/phase49/ADJUSTMENT-EVIDENCE-LEDGER.csv"
COHORT = "_audit/phase49-3/evidence/COHORT-SELECTION.json"
MAP = "_audit/phase49-3/ledgers/COVERAGE-EXPANSION-MAP.csv"
CAPTURE = "_audit/phase49-full-verification/evidence/capture-summary.json"

EXPECTED_SHA = {
    HISTORY: "c3ad3741daaa55b849fb51aca7cc066ea859d0469de2eb85d82471988a69a650",
    STEPS: "c0ab45bf60ba8d95fa4f4f33d60d4fa6f465a62c07271053c8ca7781f5114a28",
}

# Frozen Phase 4.9 tolerances, quoted for the record. Never re-tuned here.
TOLERANCES = {
    "FACTOR_EXACT": 0.001,
    "FACTOR_MATERIAL": 0.01,
    "STEP_DATE_SHIFT_MAX_DAYS": 5,
    "DEDUPE_RATIO_TOL": 0.01,
}

O1_PREFIXES = ("share_change_events:", "price_adjust_events:")
R1_PREFIX = "capture:"
O2_PREFIX = "codal:"

COMPARE_ORDER = ("MATCH", "PARTIAL", "MISMATCH", "NO_EVIDENCE")

CANDLE_BLOCK = "BLOCKED_CAPTURE_BYTES_ABSENT"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(rel):
    with io.open(os.path.join(ROOT, rel), encoding="utf-8-sig",
                 newline="") as fh:
        return list(csv.DictReader(fh))


def read_json(rel):
    with io.open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return json.load(fh)


def write_json(rel, payload):
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    return sha256_file(path)


def write_csv(rel, rows, fields):
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return sha256_file(path)


def _refs(row):
    return [t.strip() for t in (row.get("evidence_ref") or "").split(";")
            if t.strip()]


def _has(row, prefixes):
    return any(t.startswith(prefixes) for t in _refs(row))


def _sum_json(rows, field):
    total = collections.Counter()
    for r in rows:
        for k, v in json.loads(r[field]).items():
            total[k] += v
    return total


def _event_status(counts, valid_rows):
    """Honest label for the extracted event-ratio evidence only.

    NO_EVIDENCE rows carry no witness at all, so a symbol whose steps are all
    unwitnessed is NOT_MEASURED at event level even though its rows exist.
    A single MISMATCH keeps the symbol at PARTIAL: the mission forbids letting
    one symbol's agreement hide another step's defect.
    """
    if not valid_rows:
        return "NOT_MEASURED"
    witnessed = valid_rows - counts["NO_EVIDENCE"]
    if witnessed == 0:
        return "NOT_MEASURED"
    if counts["MISMATCH"] or counts["PARTIAL"] or counts["NO_EVIDENCE"]:
        return "PARTIAL"
    return "PASS"


FIELDS = [
    "symbol", "key", "ins_code", "asset_id", "stratum",
    "identity_check", "identity_note",
    "event_rows_total", "event_rows_valid", "event_rows_invalid_dropped",
    "event_distinct_dates", "history_step_rows", "history_factor_steps",
    "step_rows_reproduced", "factor_steps_reproduced",
    "cmp_match", "cmp_partial", "cmp_mismatch", "cmp_no_evidence",
    "o1_witness_rows", "r1_witness_rows", "o2_witness_rows",
    "ref_ratio_rows", "prod_ratio_rows", "ratio_only_rows",
    "evidence_tiers", "final_statuses", "discrepancy_causes",
    "raw_spellings", "event_level_status", "event_level_scope",
    "candle_level_status", "candle_block_cause", "verification_status",
    "seed_price_rows", "expected_raw_rows", "expected_history_gain_rows",
    "session_completeness", "price_basis_risk",
]


def build(out_json, out_csv, out_plan, manifest_path):
    started = time.time()
    for rel, want in EXPECTED_SHA.items():
        got = sha256_file(os.path.join(ROOT, rel))
        if got != want:
            print("FATAL input SHA mismatch %s: %s != %s"
                  % (rel, got, want), file=sys.stderr)
            return 2

    hist_rows = read_csv(HISTORY)
    hist = {r["symbol"]: r for r in hist_rows}
    steps = read_csv(STEPS)
    cohort = read_json(COHORT)
    members = cohort["members"]
    capture = read_json(CAPTURE)

    by_key = collections.defaultdict(list)
    for row in steps:
        by_key[key(row["symbol"])].append(row)

    out, drift = [], []
    for m in members:
        sym = m["symbol"]
        k = key(sym)
        h = hist[sym]
        rows = by_key.get(k, [])
        valid = [r for r in rows
                 if r["final_status"] != "INVALID_DROPPED"]
        dropped = len(rows) - len(valid)
        dates = sorted({r["effective_date"] for r in valid})

        # The join must reproduce the accepted pipeline's own grouping.
        sr_ok = len(valid) == int(h["step_rows"])
        fs_ok = len(dates) == int(h["factor_steps"])
        if not (sr_ok and fs_ok):
            drift.append({"symbol": sym, "valid": len(valid),
                          "step_rows": h["step_rows"], "dates": len(dates),
                          "factor_steps": h["factor_steps"]})

        cmp_counts = collections.Counter(r["comparison_result"] for r in valid)
        counts = {c: cmp_counts.get(c, 0) for c in COMPARE_ORDER}

        # Identity is checked, never assumed: every NON-EMPTY ins_code/asset_id
        # in the evidence rows must equal the history ledger's. Empty fields are
        # missing data on alias rows, not a competing identity.
        ins = {r["ins_code"] for r in rows if r["ins_code"].strip()}
        aid = {r["asset_id"] for r in rows if r["asset_id"].strip()}
        ins_ok = ins <= {h["ins_code"]}
        aid_ok = aid <= {h["asset_id"]} if h["asset_id"].strip() else not aid
        empty_ins = sum(1 for r in rows if not r["ins_code"].strip())
        empty_aid = sum(1 for r in rows if not r["asset_id"].strip())
        if ins_ok and aid_ok:
            ident = "CONSISTENT"
            note = ("all non-empty ins_code/asset_id equal the history ledger; "
                    "%d rows with empty ins_code, %d with empty asset_id"
                    % (empty_ins, empty_aid))
        else:
            ident = "CONFLICT"
            note = ("ins_code evidence=%s history=%s; asset_id evidence=%s "
                    "history=%s" % (sorted(ins), h["ins_code"], sorted(aid),
                                    h["asset_id"]))

        tiers = sorted({t for r in valid
                        for t in (r["evidence_tier"] or "").split("+") if t})
        statuses = collections.Counter(r["final_status"] for r in valid)
        causes = collections.Counter(r["discrepancy_cause"] for r in valid
                                     if r["discrepancy_cause"])
        spellings = sorted({r["symbol"] for r in rows})

        ev_status = _event_status(counts, len(valid))
        out.append({
            "symbol": sym, "key": k, "ins_code": h["ins_code"],
            "asset_id": h["asset_id"], "stratum": m["stratum"],
            "identity_check": ident, "identity_note": note,
            "event_rows_total": len(rows), "event_rows_valid": len(valid),
            "event_rows_invalid_dropped": dropped,
            "event_distinct_dates": len(dates),
            "history_step_rows": h["step_rows"],
            "history_factor_steps": h["factor_steps"],
            "step_rows_reproduced": "YES" if sr_ok else "NO",
            "factor_steps_reproduced": "YES" if fs_ok else "NO",
            "cmp_match": counts["MATCH"], "cmp_partial": counts["PARTIAL"],
            "cmp_mismatch": counts["MISMATCH"],
            "cmp_no_evidence": counts["NO_EVIDENCE"],
            "o1_witness_rows": sum(1 for r in valid if _has(r, O1_PREFIXES)),
            "r1_witness_rows": sum(1 for r in valid if _has(r, R1_PREFIX)),
            "o2_witness_rows": sum(1 for r in valid if _has(r, O2_PREFIX)),
            "ref_ratio_rows": sum(1 for r in valid if r["ref_ratio"].strip()),
            "prod_ratio_rows": sum(1 for r in valid
                                   if r["prod_ratio"].strip()),
            "ratio_only_rows": sum(1 for r in valid
                                   if r["ratio"].strip()
                                   and not r["ref_ratio"].strip()
                                   and not r["prod_ratio"].strip()),
            "evidence_tiers": "+".join(tiers),
            "final_statuses": json.dumps(dict(sorted(statuses.items())),
                                         ensure_ascii=False, sort_keys=True),
            "discrepancy_causes": json.dumps(dict(sorted(causes.items())),
                                             ensure_ascii=False, sort_keys=True),
            "raw_spellings": "|".join(spellings),
            "event_level_status": ev_status,
            "event_level_scope": "PRIOR_PHASE_EVENT_RATIO_WITNESS_EXTRACTED",
            "candle_level_status": "BLOCKED",
            "candle_block_cause": CANDLE_BLOCK,
            "verification_status": "BLOCKED",
            "seed_price_rows": m["seed_price_rows"],
            "expected_raw_rows": m["expected_raw_rows"],
            "expected_history_gain_rows": m["expected_history_gain_rows"],
            "session_completeness": m["session_completeness"],
            "price_basis_risk": m["price_basis_risk"],
        })

    if drift:
        print("FATAL identity-key join does not reproduce the accepted "
              "pipeline step counts: %s" % json.dumps(drift, ensure_ascii=False),
              file=sys.stderr)
        return 2

    conflicts = [r["symbol"] for r in out if r["identity_check"] == "CONFLICT"]
    if conflicts:
        print("FATAL identity conflict on cohort symbols: %s" % conflicts,
              file=sys.stderr)
        return 2

    # The frozen ledger's own SYMBOL_IDENTITY_MISMATCH cause is an alias-spelling
    # duplicate-date conflict (stage03_step_ledger.py:395-401,570-571): two raw
    # spellings of one key disagree by more than DEDUPE_RATIO_TOL on one date.
    # It is not a wrong-instrument identity. Surface every such row explicitly.
    flagged = []
    for m in members:
        for r in by_key.get(key(m["symbol"]), []):
            if r["discrepancy_cause"] != "SYMBOL_IDENTITY_MISMATCH":
                continue
            h = hist[m["symbol"]]
            flagged.append({
                "symbol": m["symbol"], "raw_spelling": r["symbol"],
                "effective_date": r["effective_date"],
                "ins_code": r["ins_code"], "asset_id": r["asset_id"],
                "final_status": r["final_status"],
                "ins_code_equals_history": (
                    "YES" if r["ins_code"].strip() in ("", h["ins_code"])
                    else "NO"),
                "ratio": r["ratio"], "ref_ratio": r["ref_ratio"],
                "prod_ratio": r["prod_ratio"],
                "audit_notes": r["notes"],
            })
    flagged.sort(key=lambda x: (x["symbol"], x["effective_date"]))
    wrong_instrument = [f for f in flagged
                        if f["ins_code_equals_history"] == "NO"]
    if wrong_instrument:
        print("FATAL alias flag hides a real instrument mismatch: %s"
              % json.dumps(wrong_instrument, ensure_ascii=False),
              file=sys.stderr)
        return 2

    out.sort(key=lambda r: r["symbol"])
    ev_counts = collections.Counter(r["event_level_status"] for r in out)
    totals = {f: sum(int(r[f]) for r in out) for f in FIELDS
              if f.startswith(("cmp_", "event_rows", "event_distinct",
                               "o1_", "r1_", "o2_", "ref_ratio", "prod_ratio",
                               "ratio_only", "seed_price", "expected_"))}

    payload = {
        "schema": "phase49-3-cohort-event-evidence-v1",
        "stage": "stage03_cohort_evidence",
        "mission": "phase49-3-coverage-expansion",
        "measurement_scope": {
            "event_level": ("witness agreement per adjustment step, already "
                            "measured by phase49-full-verification "
                            "stage03_step_ledger.py and committed in "
                            "ADJUSTMENT-EVIDENCE-LEDGER.csv; extracted and "
                            "re-keyed here, NOT re-measured"),
            "candle_level": ("NOT PERFORMED: OHLC parity, volume constancy, "
                             "revision, update chain and idempotency all "
                             "require the paired capture bytes and a working "
                             "DB copy, neither of which is on this machine"),
            "not_a_parity_claim": True,
        },
        "tolerances_quoted_not_changed": TOLERANCES,
        "identity_key": "dev/symbol_identity.py:key (same module stage05 uses)",
        "join_validation": {
            "method": ("group ADJUSTMENT-EVIDENCE-LEDGER.csv by "
                       "symbol_identity.key; valid rows must equal the history "
                       "ledger step_rows and distinct effective dates must "
                       "equal factor_steps"),
            "step_rows_reproduced": sum(1 for r in out
                                        if r["step_rows_reproduced"] == "YES"),
            "factor_steps_reproduced": sum(
                1 for r in out if r["factor_steps_reproduced"] == "YES"),
            "cohort_size": len(out),
            "identity_conflicts": conflicts,
            "alias_spellings_joined": sum(
                len(r["raw_spellings"].split("|")) - 1 for r in out),
        },
        "totals": totals,
        "event_level_status_counts": dict(sorted(ev_counts.items())),
        "candle_level_status_counts": {"BLOCKED": len(out)},
        "verification_status_counts": {"BLOCKED": len(out)},
        "symbols_with_zero_event_rows": [r["symbol"] for r in out
                                         if r["event_rows_total"] == 0],
        "symbols_with_mismatch": [r["symbol"] for r in out
                                  if int(r["cmp_mismatch"]) > 0],
        "symbols_with_no_witness": [r["symbol"] for r in out
                                    if r["event_level_status"] == "NOT_MEASURED"],
        "discrepancy_cause_totals": dict(sorted(_sum_json(
            out, "discrepancy_causes").items())),
        "final_status_totals": dict(sorted(_sum_json(
            out, "final_statuses").items())),
        "identity_audit_flags": {
            "meaning": ("SYMBOL_IDENTITY_MISMATCH in the frozen ledger is an "
                        "alias-spelling duplicate-date ratio conflict "
                        "(stage03_step_ledger.py:395-401,570-571), not a "
                        "wrong-instrument identity; every flagged row's "
                        "non-empty ins_code equals the history ledger's"),
            "rows": len(flagged),
            "wrong_instrument_rows": len(wrong_instrument),
            "detail": flagged,
            "action": ("left untouched: no valid witness authorises rewriting "
                       "a discrepant row, and the ratio/provenance are kept"),
        },
        "inputs": {rel: sha256_file(os.path.join(ROOT, rel))
                   for rel in (HISTORY, STEPS, COHORT, MAP, CAPTURE)},
        "members": out,
    }
    sha_json = write_json(out_json, payload)
    sha_csv = write_csv(out_csv, out, FIELDS)

    plan = _capture_plan(cohort, capture, out)
    sha_plan = write_json(out_plan, plan)

    manifest = {
        "schema": "phase49-3-stage-manifest-v1",
        "stage": "stage03_cohort_evidence",
        "script": "_audit/phase49-3/stage03_cohort_evidence.py",
        "script_sha256": sha256_file(os.path.abspath(__file__)),
        "code_commit": "e09ccd95d51c94082640cda75ef3de2b2008f9d2",
        "inputs": payload["inputs"],
        "outputs": {out_json: sha_json, out_csv: sha_csv, out_plan: sha_plan},
        "row_counts": {"cohort_symbols": len(out),
                       "event_rows_joined": totals["event_rows_total"],
                       "event_rows_valid": totals["event_rows_valid"],
                       "event_distinct_dates": totals["event_distinct_dates"],
                       "identity_audit_flag_rows": len(flagged)},
        "runtime_seconds": round(time.time() - started, 3),
        "status": "PASS_EXTRACTION_ONLY",
        "candle_level_status": "BLOCKED",
        "deterministic": True,
        "clock_in_payload": False,
    }
    write_json(manifest_path, manifest)
    print("stage03 OK: %d symbols, %d event rows (%d valid, %d distinct dates)"
          % (len(out), totals["event_rows_total"], totals["event_rows_valid"],
             totals["event_distinct_dates"]))
    print("  join reproduced step_rows %d/30, factor_steps %d/30"
          % (payload["join_validation"]["step_rows_reproduced"],
             payload["join_validation"]["factor_steps_reproduced"]))
    print("  event-level (extracted): %s"
          % json.dumps(payload["event_level_status_counts"], ensure_ascii=False))
    print("  candle-level: BLOCKED x%d (%s)" % (len(out), CANDLE_BLOCK))
    print("  identity-audit flag rows: %d (wrong-instrument: %d)"
          % (len(flagged), len(wrong_instrument)))
    return 0


def _capture_plan(cohort, capture, out):
    """Exact restore-or-recapture plan. No credential is requested or stored."""
    req = cohort["capture_requirement"]
    merged = capture["merged"]
    return {
        "schema": "phase49-3-capture-restore-plan-v1",
        "status": "BLOCKED_CAPTURE_REQUIRED",
        "block_cause": CANDLE_BLOCK,
        "block_cause_precise": (
            "the paired type0/type7 capture is EVIDENCED as already taken "
            "(759 symbols, 2,620,482 bars per type, container SHA recorded) "
            "but the capture BYTES are not present on this machine; they are "
            "gitignored licensed data. This is not 'no valid session' and not "
            "'no reference exists'."),
        "new_network_capture_needed": False,
        "preferred_path": {
            "action": "RESTORE the existing capture artifacts, then re-run the "
                      "accepted Phase 4.9.2 pipeline on an independent working "
                      "DB copy",
            "artifacts": [
                {"path": merged["bars_file"],
                 "container_sha256": merged["bars_container_sha256"],
                 "payload_sha256": merged["bars_payload_sha256"],
                 "symbols": merged["reference_index_all"]["symbols"]},
                {"path": merged["index_file"],
                 "sha256": merged["reference_index_all"]["sha256"],
                 "factor_days": merged["reference_index_all"]["factor_days"],
                 "factor_changes": merged["reference_index_all"]["factor_changes"]},
            ],
            "verification_on_restore": (
                "recompute SHA-256 of both artifacts and compare with the "
                "recorded values before any ingest; abort on mismatch"),
            "working_db": ("a NEW independent copy under "
                           "_audit/phase49-3/db/; never the Seed Candidate "
                           "57118e8f... and never the Pilot 8445624f..."),
        },
        "fallback_path": {
            "action": "re-capture only if restore is impossible",
            "precondition": ("an already-authenticated Rahavard session that "
                             "the owner authorized; no password or login "
                             "information is requested or stored by this "
                             "mission"),
            "if_no_valid_session": ("do not fabricate data and do not produce "
                                    "a fake capture; keep "
                                    "BLOCKED_CAPTURE_REQUIRED"),
            "parameters": {
                "endpoint": capture["capture"]["endpoint"],
                "types": ["type0", "type7"],
                "resolutions": ["D"],
                "countback": capture["capture"]["countback"],
                "from": capture["capture"]["from"],
                "symbols": sorted(r["symbol"] for r in out),
                "asset_ids": sorted({r["asset_id"] for r in out
                                     if r["asset_id"].strip()}),
                "capture_day_candle": "QUARANTINED; never enters the "
                                      "adjustment chain",
            },
            "must_record": ["symbol identity (key, ins_code, asset_id)",
                            "fetch date", "last complete session",
                            "series type", "resolution", "SHA-256"],
        },
        "cohort_symbols": sorted(r["symbol"] for r in out),
        "cohort_size": len(out),
        "expected_rows_after_restore": {
            "seed_price_rows": sum(int(r["seed_price_rows"]) for r in out),
            "expected_raw_rows": sum(int(r["expected_raw_rows"]) for r in out),
            "expected_gain_rows": sum(int(r["expected_history_gain_rows"])
                                      for r in out),
            "basis": ("ref_days (per-symbol type0 daily bar count) from the "
                      "committed history ledger; the prior 30-symbol pilot "
                      "showed ref_days == pilot_raw_rows for 30/30"),
        },
        "credentials": "never requested, never stored",
        "owner_decision_needed": (
            "restore the licensed capture bytes to this machine (or authorize "
            "a re-capture on an existing authenticated session) so the frozen "
            "30 can be processed end-to-end; no Seed or Production change is "
            "implied by this request"),
        "request": req,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-json",
                    default="_audit/phase49-3/evidence/cohort-event-evidence.json")
    ap.add_argument("--out-csv",
                    default="_audit/phase49-3/ledgers/COHORT-EVENT-EVIDENCE.csv")
    ap.add_argument("--out-plan",
                    default="_audit/phase49-3/evidence/capture-restore-plan.json")
    ap.add_argument("--manifest",
                    default="_audit/phase49-3/manifests/stage03_cohort_evidence.manifest.json")
    a = ap.parse_args()
    return build(a.out_json, a.out_csv, a.out_plan, a.manifest)


if __name__ == "__main__":
    sys.exit(main())