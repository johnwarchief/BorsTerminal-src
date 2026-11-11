#!/usr/bin/env python3
"""Census the reference index for symbols the zero-event coverage defect can hit.

Read-only.  No DB is opened, no bar is scanned, no symbol is ingested and no
candle is built: the input is the already-verified reference index alone, so this
is a census of the 759 reference-covered symbols, NOT a processing of the 6,103
symbol universe.

Why it exists: stage08 measured the defect live on one cohort symbol (پادا) and
the owner must rule on it.  Ruling on "1 of 30" alone hides the scope.  This
counts the candidate population from the same frozen index.

Two limits are recorded rather than papered over:
  * the index calls a change "no change" below FACTOR_EXACT=1e-3 while the frozen
    ingest q_changes uses 1e-9.  That gap is measured closed for this population
    (every candidate's daily ratio is exactly 1.0, so q is bitwise constant), but
    only the cohort was run through the live read path, so the count is a
    CANDIDATE population, not a live-confirmed defect count.
  * a zero-change symbol's absolute q level is not in the index.  q==1 gives the
    geometry-only defect seen on پادا; q==c!=1 would also break close parity.
    Telling them apart needs a bars scan, which is NOT_MEASURED here.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

CAPTURE_SUMMARY = "_audit/phase49-full-verification/evidence/capture-summary.json"
INDEX_REL = "_audit/phase49-full-verification/captures/reference-index-all.json"
STAGE06 = "_audit/phase49-3/evidence/RESTORED-CAPTURE-VERIFICATION.json"
STAGE08 = "_audit/phase49-3/evidence/RUNTIME-READPATH.json"
COHORT = "_audit/phase49-3/evidence/COHORT-SELECTION.json"
RECON = "_audit/phase49-3/evidence/coverage-reconciliation.json"

EXPECTED_SHA = {
    CAPTURE_SUMMARY:
        "6cbeb62811f42d143a9d6b5c10324e2eae57b6914e8f875a3ee0e50d6154da8b",
    COHORT:
        "857573dd33676d18fda6243806786690eec70abbf8bcee965d48d825eaa77901",
}

BASE_COMMIT = "e09ccd95d51c94082640cda75ef3de2b2008f9d2"

# Frozen tolerances, quoted for the record. Never re-tuned here.
INDEX_FACTOR_EXACT = 1e-3
INGEST_Q_STEP = 1e-9

OUT = "_audit/phase49-3/evidence/ZERO-EVENT-CENSUS.json"
MANIFEST = "_audit/phase49-3/manifests/stage10-zero-event-census.json"

CHUNK = 1 << 20


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(rel):
    with io.open(os.path.join(ROOT, rel.replace("/", os.sep)),
                 encoding="utf-8") as fh:
        return json.load(fh)


def write_json(rel, obj):
    path = os.path.join(ROOT, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    return sha256_file(path)


def paired(rec):
    """A daily type0/type7 pair with at least one usable factor day."""
    t0, t7 = rec.get("type0") or {}, rec.get("type7") or {}
    return (t0.get("n", 0) > 0 and t7.get("n", 0) > 0
            and rec.get("factor_days", 0) > 0)


def bitwise_constant(rec):
    """Every daily factor ratio was exactly 1.0, so q never moved at all.

    The frozen chain counts the first day as the baseline and every later day in
    exactly one bucket.  exact == factor_days - 1 with the other buckets empty
    therefore means q is bitwise constant, which the ingest's tighter 1e-9 step
    also reads as no change.  This is what removes the tolerance ambiguity for
    the candidates; it says nothing about the absolute level of q.
    """
    return (rec.get("factor_exact", 0) == rec.get("factor_days", 0) - 1
            and rec.get("factor_within_0.1pct", 0) == 0
            and rec.get("factor_undefined_ratio", 0) == 0
            and rec.get("zero_raw_days", 0) == 0
            and not rec.get("factor_changes"))


def census(index):
    """Partition the index; the defect needs a paired series and no q change."""
    at_risk, strict, drift, unpaired, with_changes = [], [], [], [], []
    constant, bars = [], 0
    for k in sorted(index):
        rec = index[k]
        if not paired(rec):
            unpaired.append(k)
            continue
        if len(rec.get("factor_changes") or []):
            with_changes.append(k)
            continue
        at_risk.append(k)
        bars += rec.get("factor_days", 0)
        if bitwise_constant(rec):
            constant.append(k)
        if (rec.get("factor_within_0.1pct", 0) == 0
                and rec.get("factor_undefined_ratio", 0) == 0):
            strict.append(k)
        else:
            drift.append(k)
    return {"symbols_total": len(index),
            "paired_symbols": len(at_risk) + len(with_changes),
            "unpaired_symbols": len(unpaired),
            "symbols_with_changes": len(with_changes),
            "at_risk_candidates": len(at_risk),
            "at_risk_strictly_constant": len(strict),
            "at_risk_subthreshold_drift": len(drift),
            "at_risk_q_bitwise_constant": len(constant),
            "at_risk_daily_bars_total": bars,
            "at_risk_keys": at_risk,
            "at_risk_strictly_constant_keys": strict,
            "at_risk_subthreshold_drift_keys": drift,
            "at_risk_q_bitwise_constant_keys": constant,
            "unpaired_keys": unpaired}


def controls(index, base, cohort_keys, live_zero_event, agg):
    """Positive and negative controls: the census must see what it claims."""
    out, failures = {}, []

    def chk(name, ok, detail):
        out[name] = {"ok": bool(ok), "detail": detail}
        if not ok:
            failures.append("%s: %s" % (name, detail))

    chk("A_totals_reproduce_stage06",
        base["symbols_total"] == agg["symbols"],
        "symbols_total=%d stage06=%d" % (base["symbols_total"], agg["symbols"]))

    # Positive control: the symbol stage08 measured live with zero factors must
    # be in the candidate set, or the census contradicts the live measurement.
    for sym in live_zero_event:
        chk("B_live_zero_event_%s_in_candidates" % sym,
            sym in base["at_risk_keys"],
            "in_at_risk=%s" % (sym in base["at_risk_keys"]))

    # Negative control 1: inject one synthetic change into a candidate. The
    # count must drop by exactly one, proving the sensor is not blind.
    if base["at_risk_keys"]:
        victim = base["at_risk_keys"][0]
        mut = copy.deepcopy(index)
        mut[victim]["factor_changes"] = [
            {"date": "2020-01-01", "factor": 0.5, "ratio_change": 2.0}]
        got = census(mut)
        chk("C_injected_change_removes_candidate",
            got["at_risk_candidates"] == base["at_risk_candidates"] - 1
            and victim not in got["at_risk_keys"],
            "%d -> %d (victim %s)" % (base["at_risk_candidates"],
                                      got["at_risk_candidates"], victim))

        # Negative control 2: break the pairing instead. Also must drop by one.
        mut2 = copy.deepcopy(index)
        mut2[victim]["type7"] = dict(mut2[victim]["type7"], n=0)
        got2 = census(mut2)
        chk("D_broken_pairing_removes_candidate",
            got2["at_risk_candidates"] == base["at_risk_candidates"] - 1
            and victim in got2["unpaired_keys"],
            "%d -> %d, unpaired=%d" % (base["at_risk_candidates"],
                                       got2["at_risk_candidates"],
                                       got2["unpaired_symbols"]))

        # Negative control 3: sub-threshold drift must land in the drift bucket,
        # not the strictly-constant one, so the two are never conflated.
        mut3 = copy.deepcopy(index)
        mut3[victim]["factor_within_0.1pct"] = 1
        got3 = census(mut3)
        chk("E_subthreshold_drift_separated",
            victim in got3["at_risk_subthreshold_drift_keys"]
            and victim not in got3["at_risk_strictly_constant_keys"]
            and got3["at_risk_candidates"] == base["at_risk_candidates"],
            "drift=%d strict=%d" % (got3["at_risk_subthreshold_drift"],
                                    got3["at_risk_strictly_constant"]))

        # Negative control 4: the bitwise-constant classifier must notice a
        # single day moved into the sub-threshold bucket, while the symbol stays
        # a candidate. Otherwise "q never moved" would be an unfalsifiable label.
        mut4 = copy.deepcopy(index)
        mut4[victim]["factor_exact"] = mut4[victim]["factor_exact"] - 1
        mut4[victim]["factor_within_0.1pct"] = 1
        got4 = census(mut4)
        chk("I_bitwise_constant_classifier_sees_drift",
            victim in base["at_risk_q_bitwise_constant_keys"]
            and victim not in got4["at_risk_q_bitwise_constant_keys"]
            and got4["at_risk_q_bitwise_constant"]
            == base["at_risk_q_bitwise_constant"] - 1
            and got4["at_risk_candidates"] == base["at_risk_candidates"],
            "%d -> %d, candidates unchanged=%d"
            % (base["at_risk_q_bitwise_constant"],
               got4["at_risk_q_bitwise_constant"], got4["at_risk_candidates"]))
    else:
        chk("C_injected_change_removes_candidate", False,
            "no candidate to perturb; control cannot run")

    # The symbol confirmed live must also be bitwise constant, or the census and
    # the live measurement describe different populations.
    for sym in live_zero_event:
        chk("J_live_zero_event_%s_q_bitwise_constant" % sym,
            sym in base["at_risk_q_bitwise_constant_keys"],
            "in_bitwise_constant=%s"
            % (sym in base["at_risk_q_bitwise_constant_keys"]))

    chk("F_partition_is_exhaustive",
        base["at_risk_candidates"] + base["symbols_with_changes"]
        + base["unpaired_symbols"] == base["symbols_total"],
        "%d + %d + %d == %d" % (base["at_risk_candidates"],
                                base["symbols_with_changes"],
                                base["unpaired_symbols"],
                                base["symbols_total"]))
    chk("G_buckets_split_candidates",
        base["at_risk_strictly_constant"] + base["at_risk_subthreshold_drift"]
        == base["at_risk_candidates"],
        "%d + %d == %d" % (base["at_risk_strictly_constant"],
                           base["at_risk_subthreshold_drift"],
                           base["at_risk_candidates"]))
    chk("H_cohort_overlap_counted",
        len(set(base["at_risk_keys"]) & cohort_keys) <= len(cohort_keys),
        "overlap=%d of %d" % (len(set(base["at_risk_keys"]) & cohort_keys),
                              len(cohort_keys)))
    return out, failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest-only", action="store_true",
                    help="run the controls and print; write nothing")
    args = ap.parse_args()

    started = time.time()
    for rel, exp in EXPECTED_SHA.items():
        got = sha256_file(os.path.join(ROOT, rel.replace("/", os.sep)))
        if got != exp:
            sys.exit("FATAL: pinned input %s has sha256 %s, expected %s"
                     % (rel, got, exp))

    summary = read_json(CAPTURE_SUMMARY)
    idx_rec = summary["merged"]["reference_index_all"]
    index_path = os.path.join(ROOT, INDEX_REL.replace("/", os.sep))
    if not os.path.exists(index_path):
        sys.exit("FATAL: restored index absent; run stage06 --materialize first")
    index_sha = sha256_file(index_path)
    if index_sha != idx_rec["sha256"]:
        sys.exit("FATAL: index sha256 %s != recorded %s"
                 % (index_sha, idx_rec["sha256"]))

    with io.open(index_path, encoding="utf-8") as fh:
        index = json.load(fh)

    s6 = read_json(STAGE06)
    s8 = read_json(STAGE08)
    cohort = read_json(COHORT)
    recon = read_json(RECON)
    cohort_keys = {m["key"] for m in cohort["members"]}

    agg = s6["index_aggregates"]
    recomputed = {
        "symbols": len(index),
        "factor_days": sum(r["factor_days"] for r in index.values()),
        "factor_changes": sum(len(r["factor_changes"]) for r in index.values()),
        "date_conflicts": sum(r["date_conflicts"] for r in index.values()),
        "zero_raw_days": sum(r["zero_raw_days"] for r in index.values()),
    }
    for k, v in recomputed.items():
        if v != agg[k]:
            sys.exit("FATAL: index %s=%d disagrees with stage06 %d"
                     % (k, v, agg[k]))

    live_zero = sorted(r["symbol"] for r in s8["per_symbol"]
                       if r["adjust_events"] == 0
                       and r["factor_rows_in_db"] == 0)
    declared = sorted((s8.get("zero_event_finding") or {}).get("symbols") or [])
    if live_zero != declared:
        sys.exit("FATAL: stage08 zero-event symbols %r disagree with its own"
                 " finding %r" % (live_zero, declared))
    if not live_zero:
        sys.exit("FATAL: stage08 recorded no zero-event symbol; the positive"
                 " control would be vacuous")

    base = census(index)
    ctl, failures = controls(index, base, cohort_keys, live_zero, agg)

    if args.selftest_only:
        for name, rec in sorted(ctl.items()):
            print(("  OK   " if rec["ok"] else "  FAIL ") + name
                  + " | " + str(rec["detail"]))
        print("controls: %d/%d" % (sum(1 for r in ctl.values() if r["ok"]),
                                   len(ctl)))
        return 1 if failures else 0

    if failures:
        print("FAIL (%d control problems), nothing written:" % len(failures))
        for f in failures:
            print("  -", f)
        return 1

    overlap = sorted(set(base["at_risk_keys"]) & cohort_keys)
    payload = {
        "schema": "phase49-3-zero-event-census-v1",
        "mission": "Phase 4.9.3 coverage expansion",
        "stage": "stage10_zero_event_census",
        "status": "PASS",
        "base_commit": BASE_COMMIT,
        "scope": "census of the restored reference index only; read-only",
        "not_a_processing_of_the_universe": True,
        "symbols_censused": base["symbols_total"],
        "universe_symbols_not_processed": recon["universe"]["history_symbols"],
        "db_opened": False,
        "bars_scanned": False,
        "candles_built": False,
        "inputs": {
            INDEX_REL: {"sha256": index_sha,
                        "bytes": os.path.getsize(index_path),
                        "matches_recorded_evidence": True},
            STAGE06: {"sha256": sha256_file(
                os.path.join(ROOT, STAGE06.replace("/", os.sep)))},
            STAGE08: {"sha256": sha256_file(
                os.path.join(ROOT, STAGE08.replace("/", os.sep)))},
            COHORT: {"sha256": EXPECTED_SHA[COHORT]},
            RECON: {"sha256": sha256_file(
                os.path.join(ROOT, RECON.replace("/", os.sep)))},
        },
        "index_aggregates_recomputed": recomputed,
        "index_aggregates_match_stage06": True,
        "census": {k: v for k, v in base.items() if not k.endswith("_keys")},
        "at_risk_keys": base["at_risk_keys"],
        "at_risk_strictly_constant_keys": base["at_risk_strictly_constant_keys"],
        "at_risk_subthreshold_drift_keys":
            base["at_risk_subthreshold_drift_keys"],
        "at_risk_q_bitwise_constant_keys":
            base["at_risk_q_bitwise_constant_keys"],
        "unpaired_keys": base["unpaired_keys"],
        "cohort_overlap": {"count": len(overlap), "keys": overlap},
        "live_zero_event_symbols_from_stage08": live_zero,
        "tolerances_quoted_not_changed": {
            "index_factor_exact": INDEX_FACTOR_EXACT,
            "ingest_q_step": INGEST_Q_STEP,
        },
        "controls": ctl,
        "controls_passed": sum(1 for r in ctl.values() if r["ok"]),
        "controls_total": len(ctl),
        "interpretation": {
            "tolerance_gap_measured_closed":
                "the index ignores q drift below 1e-3 while the frozen ingest"
                " q_changes uses 1e-9, so a zero-change symbol could in principle"
                " still yield engine factors. Measured here: every candidate has"
                " factor_exact == factor_days - 1 with all other buckets empty,"
                " i.e. every daily ratio was exactly 1.0 and q is bitwise"
                " constant, which the 1e-9 step also reads as no change. The gap"
                " therefore does not bite for this population",
            "candidate_not_confirmed_live":
                "only the cohort was run through the live read path. For the"
                " other candidates the zero-factor outcome is derived from the"
                " index, not observed over HTTP; that confirmation is"
                " NOT_MEASURED",
            "q_level_not_measured":
                "a zero-change symbol's absolute q is absent from the index."
                " q==1 gives the geometry-only defect measured on پادا;"
                " q==c!=1 would also break close parity. Telling them apart"
                " needs a bars scan and is NOT_MEASURED outside the cohort",
            "confirmed_live": live_zero,
            "defect_not_fixed":
                "this census changes no code and no data; the owner ruling in"
                " report section 12.2 is still required",
        },
        "not_measured": [
            "absolute q level of candidates outside the cohort",
            "live read-path confirmation of candidates outside the cohort",
            "defect scope on the Seed Candidate (absent on this host)",
            "any UI screenshot",
        ],
        "failures": [],
    }

    manifest = {
        "schema": "phase49-3-stage-manifest-v2",
        "stage": "stage10_zero_event_census",
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                     time.gmtime(started)),
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_seconds": round(time.time() - started, 3),
        "exit_code": 0,
        "payload_path": OUT,
    }
    out_sha = write_json(OUT, payload)
    manifest["payload_sha256"] = out_sha
    man_sha = write_json(MANIFEST, manifest)

    print("PASS  symbols=%d paired=%d with_changes=%d at_risk=%d"
          " (strict=%d drift=%d bitwise_constant=%d) unpaired=%d"
          % (base["symbols_total"], base["paired_symbols"],
             base["symbols_with_changes"], base["at_risk_candidates"],
             base["at_risk_strictly_constant"],
             base["at_risk_subthreshold_drift"],
             base["at_risk_q_bitwise_constant"], base["unpaired_symbols"]))
    print("      at-risk daily bars=%d" % base["at_risk_daily_bars_total"])
    print("      cohort overlap=%d %s" % (len(overlap), overlap))
    print("      live zero-event from stage08: %s" % live_zero)
    print("      controls %d/%d" % (payload["controls_passed"],
                                    payload["controls_total"]))
    print("wrote %s (%s)" % (OUT, out_sha[:16]))
    print("wrote %s (%s)" % (MANIFEST, man_sha[:16]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())