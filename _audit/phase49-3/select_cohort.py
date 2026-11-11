#!/usr/bin/env python3
"""Phase 4.9.3 cohort selection: 30 new symbols, stratified on real data diversity.

Pool = QUEUE_REFERENCE_ONLY symbols with a resolved (non-ambiguous) identity,
a mappable asset id and valid raw OHLC. Halted / no-instruments / unmapped /
ambiguous symbols are never pulled in to reach the count of 30.

Selection is deterministic: within each stratum candidates are ordered by the
stratum's primary metric (desc) with the symbol as tie-break, then taken at
evenly spread positions so a stratum spans its own range instead of clustering
at one end. No RNG, no clock, so a rerun picks the identical 30.

Event kinds are taken from explicit evidence sources only (share_change_events,
price_adjust_events). A measured ratio with no official source stays
unclassified; the type is never inferred from the ratio.
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
OUT_DIR = "_audit/phase49-3"

MAP = os.path.join(OUT_DIR, "ledgers", "COVERAGE-EXPANSION-MAP.csv")
STEPS = "docs/opportunity-center/phase49/ADJUSTMENT-EVIDENCE-LEDGER.csv"
HISTORY = "docs/opportunity-center/phase49/HISTORY-COVERAGE-LEDGER.csv"
COVERAGE = "_audit/phase49-2/ledgers/COVERAGE-STATUS.csv"
RECON = os.path.join(OUT_DIR, "evidence", "coverage-reconciliation.json")

OUT_JSON = os.path.join(OUT_DIR, "evidence", "COHORT-SELECTION.json")
MANIFEST = os.path.join(OUT_DIR, "manifests", "stage02_cohort_selection.manifest.json")

TARGET = 30


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def I(r, k):
    try:
        return int(r[k] or 0)
    except (TypeError, ValueError):
        return 0


def F(r, k):
    try:
        return float(r[k] or 0.0)
    except (TypeError, ValueError):
        return 0.0


def step_agg(rows):
    sc = pa = caponly = conflict = mismatch = 0
    dates = []
    for r in rows:
        ref = r.get("evidence_ref") or ""
        has_sc = "share_change_events" in ref
        has_pa = "price_adjust_events" in ref
        if has_sc:
            sc += 1
        if has_pa:
            pa += 1
        if ref.startswith("capture:") and not has_sc and not has_pa:
            caponly += 1
        if r.get("final_status") == "CONFLICT_RATIO":
            conflict += 1
        if r.get("comparison_result") == "MISMATCH":
            mismatch += 1
        if r.get("effective_date"):
            dates.append(r["effective_date"])
    dates.sort()
    return {
        "share_change_evidenced_steps": sc,
        "price_adjust_evidenced_steps": pa,
        "capture_only_measured_steps": caponly,
        "conflict_ratio_steps": conflict,
        "mismatch_vs_reference_steps": mismatch,
        "first_step_date": dates[0] if dates else "",
        "last_step_date": dates[-1] if dates else "",
        "step_ledger_rows": len(rows),
    }


# (name, target, predicate, primary metric, why this stratum exists)
def strata_defs():
    return [
        ("LONG_HISTORY_DENSE_EVENTS", 3,
         lambda r, a: I(r, "ref_type0_bars") >= 4000 and I(r, "step_rows") >= 20,
         lambda r, a: (I(r, "step_rows"), I(r, "ref_type0_bars")),
         "long captured history with a dense adjustment chain"),
        ("LONG_HISTORY_SPARSE_EVENTS", 3,
         lambda r, a: I(r, "ref_type0_bars") >= 4000 and I(r, "step_rows") <= 8,
         lambda r, a: (I(r, "ref_type0_bars"), -I(r, "step_rows")),
         "long history where few events must still chain correctly"),
        ("SHORT_HISTORY", 3,
         lambda r, a: I(r, "ref_type0_bars") <= 600,
         lambda r, a: (-I(r, "ref_type0_bars"), I(r, "step_rows")),
         "short window: anchor and boundary behaviour dominates"),
        ("MID_HISTORY", 3,
         lambda r, a: 600 < I(r, "ref_type0_bars") < 4000,
         lambda r, a: (I(r, "ref_type0_bars"), I(r, "step_rows")),
         "the bulk of the queue: median-length windows"),
        ("CAPITAL_INCREASE_EVIDENCED", 4,
         lambda r, a: a["share_change_evidenced_steps"] >= 2,
         lambda r, a: (a["share_change_evidenced_steps"], I(r, "step_rows")),
         "official share-change evidence: shares_old/shares_new ratio path"),
        ("PRICE_ADJUST_EVIDENCED", 3,
         lambda r, a: a["price_adjust_evidenced_steps"] >= 2,
         lambda r, a: (a["price_adjust_evidenced_steps"], I(r, "step_rows")),
         "product price-adjust evidence alongside the measured reference"),
        ("CAPTURE_ONLY_MEASURED_RATIO", 3,
         lambda r, a: (a["capture_only_measured_steps"] > 0
                       and a["share_change_evidenced_steps"] == 0
                       and a["price_adjust_evidenced_steps"] == 0),
         lambda r, a: (a["capture_only_measured_steps"], I(r, "step_rows")),
         "measured ratio with no official type: must stay unclassified"),
        ("RATIO_CONFLICT_PRESENT", 3,
         lambda r, a: I(r, "factor_conflict") > 0,
         lambda r, a: (I(r, "factor_conflict"), I(r, "step_rows")),
         "pack ratio disagrees with the reference: supersede path"),
        ("HISTORICAL_ANOMALY", 2,
         lambda r, a: I(r, "anomalies") > 0,
         lambda r, a: (I(r, "anomalies"), I(r, "ref_type0_bars")),
         "zero-volume / invalid-OHLC history in the local seed"),
        ("REFERENCE_SESSION_DEFICIT", 1,
         lambda r, a: "_MISSING_" in r["session_completeness"],
         lambda r, a: (I(r, "seed_trading_sessions") - I(r, "ref_type0_bars"),),
         "reference spans the window but lacks local sessions"),
        ("FRESH_SERIES", 1,
         lambda r, a: r["stale_status"] == "fresh",
         lambda r, a: (-I(r, "sessions_behind"), I(r, "ref_type0_bars")),
         "current series: exercises the capture-day quarantine"),
        ("REFERENCE_WITH_ZERO_STEPS", 1,
         lambda r, a: I(r, "factor_steps") == 0,
         lambda r, a: (I(r, "ref_type0_bars"),),
         "full reference window and no factor step: factor must stay 1"),
    ]


def spread(cands, k, metric):
    """Deterministic spread over the stratum's own metric range."""
    ordered = sorted(cands, key=lambda x: (
        tuple(-v for v in metric(x[0], x[1])), x[0]["symbol"]))
    n = len(ordered)
    if n == 0:
        return []
    if k == 1:
        return [ordered[0]]
    idx, used, out = [], set(), []
    for i in range(k):
        j = round(i * (n - 1) / (k - 1))
        while j in used and j < n - 1:
            j += 1
        while j in used and j > 0:
            j -= 1
        if j in used:
            break
        used.add(j)
        idx.append(j)
        out.append(ordered[j])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    t0 = time.time()

    inputs = {}
    for rel in (MAP, STEPS, HISTORY, COVERAGE, RECON):
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            print("FATAL missing input %s" % rel, file=sys.stderr)
            return 2
        inputs[rel] = {"sha256": sha256(p), "bytes": os.path.getsize(p)}

    with open(os.path.join(ROOT, MAP), encoding="utf-8", newline="") as fh:
        M = list(csv.DictReader(fh))
    with open(os.path.join(ROOT, STEPS), encoding="utf-8", newline="") as fh:
        S = list(csv.DictReader(fh))
    bysym = collections.defaultdict(list)
    for r in S:
        bysym[r["symbol"]].append(r)

    pilot = {r["symbol"] for r in M if r["phase49_2_status"] == "READY_PILOT"}
    pool, excluded = [], []
    for r in M:
        if r["phase49_2_status"] != "QUEUE_REFERENCE_ONLY":
            continue
        why = []
        if r["identity_status"] != "resolved_instruments":
            why.append("IDENTITY_" + r["identity_status"].upper())
        if not r["asset_id"]:
            why.append("NO_ASSET_ID")
        if r["raw_ohlc_valid"] != "ok":
            why.append("RAW_OHLC_INVALID")
        if r["stale_status"] == "halted":
            why.append("HALTED")
        if r["symbol"] in pilot:
            why.append("ALREADY_PILOT")
        if why:
            excluded.append({"symbol": r["symbol"], "reasons": why})
        else:
            pool.append(r)

    agg = {r["symbol"]: step_agg(bysym.get(r["symbol"], [])) for r in pool}
    defs = strata_defs()
    if sum(d[1] for d in defs) != TARGET:
        print("FATAL strata targets do not sum to %d" % TARGET, file=sys.stderr)
        return 2

    chosen, strata_report = {}, []
    for name, k, pred, metric, why in defs:
        cands = [(r, agg[r["symbol"]]) for r in pool
                 if r["symbol"] not in chosen and pred(r, agg[r["symbol"]])]
        avail = sum(1 for r in pool if pred(r, agg[r["symbol"]]))
        picks = spread(cands, k, metric)
        for r, a in picks:
            chosen[r["symbol"]] = (name, why)
        strata_report.append({
            "stratum": name, "target": k, "selected": len(picks),
            "pool_matching_total": avail,
            "pool_matching_unselected": len(cands),
            "purpose": why,
            "symbols": [r["symbol"] for r, a in picks],
            "filled": len(picks) == k,
        })

    if len(chosen) != TARGET:
        print("FATAL selected %d, expected %d" % (len(chosen), TARGET),
              file=sys.stderr)
        for s in strata_report:
            if not s["filled"]:
                print("  underfilled: %s %d/%d" % (s["stratum"], s["selected"],
                                                   s["target"]), file=sys.stderr)
        return 2
    if set(chosen) & pilot:
        print("FATAL cohort overlaps the previous pilot", file=sys.stderr)
        return 2

    members = []
    for sym in sorted(chosen):
        r = next(x for x in pool if x["symbol"] == sym)
        a = agg[sym]
        name, why = chosen[sym]
        bars = I(r, "ref_type0_bars")
        steps = I(r, "step_rows")
        members.append({
            "symbol": sym, "key": r["key"], "ins_code": r["ins_code"],
            "isin": r["isin"], "asset_id": r["asset_id"],
            "stratum": name, "selection_reason": why,
            "identity_status": r["identity_status"],
            "asset_id_state": r["asset_id_state"],
            "stale_status": r["stale_status"],
            "sessions_behind": I(r, "sessions_behind"),
            "ref_coverage": r["ref_coverage"],
            "paired_type0_type7_evidenced": r["paired_type0_type7_evidenced"],
            "session_completeness": r["session_completeness"],
            "seed_price_rows": I(r, "seed_price_rows"),
            "seed_first_date": r["seed_first_date"],
            "seed_last_date": r["seed_last_date"],
            "expected_raw_rows": bars,
            "expected_history_gain_rows": bars - I(r, "seed_price_rows"),
            "ref_first": r["ref_first"], "ref_last": r["ref_last"],
            "step_rows": steps, "factor_steps": I(r, "factor_steps"),
            "factor_conflict": I(r, "factor_conflict"),
            "factor_partial": I(r, "factor_partial"),
            "factor_insufficient": I(r, "factor_insufficient"),
            "events_per_1000_sessions": (round(1000.0 * steps / bars, 3)
                                         if bars else 0.0),
            "anomalies": I(r, "anomalies"),
            "invalid_ohlc_legacy": I(r, "invalid_ohlc_legacy"),
            "gaps": I(r, "gaps"),
            "legacy_unknown_rows": I(r, "legacy_unknown_rows"),
            "price_basis_risk": r["price_basis_risk"],
            "ledger_final_status": r["ledger_final_status"],
            "evidence": a,
            "verification_status": "BLOCKED_CAPTURE_BYTES_ABSENT",
        })

    doc = {
        "schema": "phase49-3-cohort-selection-v1",
        "mission": "phase49-3-coverage-expansion",
        "target": TARGET, "selected": len(members),
        "disjoint_from_previous_pilot": True,
        "previous_pilot_symbols": sorted(pilot),
        "pool": {
            "definition": ("QUEUE_REFERENCE_ONLY with resolved non-ambiguous "
                           "identity, mappable asset id, valid raw OHLC, not halted"),
            "queue_reference_only_total": sum(
                1 for r in M if r["phase49_2_status"] == "QUEUE_REFERENCE_ONLY"),
            "eligible": len(pool), "excluded": excluded,
        },
        "selection_method": {
            "deterministic": True, "rng_used": False,
            "order": "stratum primary metric desc, symbol asc tie-break",
            "within_stratum": "evenly spread positions across the metric range",
            "strata_targets_sum": sum(d[1] for d in defs),
        },
        "strata": strata_report,
        "diversity_summary": {
            "expected_raw_rows_min": min(m["expected_raw_rows"] for m in members),
            "expected_raw_rows_max": max(m["expected_raw_rows"] for m in members),
            "expected_raw_rows_total": sum(m["expected_raw_rows"] for m in members),
            "seed_rows_total": sum(m["seed_price_rows"] for m in members),
            "expected_history_gain_rows_total": sum(
                m["expected_history_gain_rows"] for m in members),
            "step_rows_min": min(m["step_rows"] for m in members),
            "step_rows_max": max(m["step_rows"] for m in members),
            "step_rows_total": sum(m["step_rows"] for m in members),
            "ref_first_years": dict(sorted(collections.Counter(
                m["ref_first"][:4] for m in members).items())),
            "stale_status": dict(collections.Counter(m["stale_status"]
                                                     for m in members)),
            "with_capital_increase_evidence": sum(
                1 for m in members if m["evidence"]["share_change_evidenced_steps"]),
            "with_price_adjust_evidence": sum(
                1 for m in members if m["evidence"]["price_adjust_evidenced_steps"]),
            "with_capture_only_measured_steps": sum(
                1 for m in members if m["evidence"]["capture_only_measured_steps"]),
            "with_conflict": sum(1 for m in members if m["factor_conflict"]),
            "with_anomalies": sum(1 for m in members if m["anomalies"]),
            "with_legacy_unknown_price_basis": sum(
                1 for m in members if m["legacy_unknown_rows"]),
            "with_session_deficit": sum(
                1 for m in members if "_MISSING_" in m["session_completeness"]),
        },
        "capture_requirement": {
            "status": "BLOCKED_CAPTURE_BYTES_ABSENT",
            "new_network_capture_needed": False,
            "reason": ("a paired type0/type7 capture covering each member's full "
                       "local window is already evidenced by ref_coverage=full; "
                       "the licensed capture bytes are gitignored and absent "
                       "from this machine"),
            "required_artifacts": [
                {"path": "_audit/phase49-full-verification/captures/bars-all.ndjson.gz",
                 "sha256": "272336c036d647ed7b2090853c84c3a2d3da6126a0bfae60e987198169b3b14a",
                 "sha256_kind": "container"},
                {"path": "_audit/phase49-full-verification/captures/reference-index-all.json",
                 "sha256": "83544012448fc19100e7b140dbcfc2e4d27eca317f667204c343f810acc92e1c"},
            ],
            "alternative": ("re-capture these 30 symbols (type0+type7, D, "
                            "countback 100000) from an owner-authorised "
                            "authenticated Rahavard session"),
            "series_spec": {"types": ["type0", "type7"], "resolutions": ["D"],
                            "countback": 100000, "from": "1990-01-01",
                            "capture_day_candle": "QUARANTINED"},
            "credentials": "never requested, never stored",
        },
        "frozen_input_shas": inputs,
        "members": members,
    }

    for p in (OUT_JSON, MANIFEST):
        os.makedirs(os.path.dirname(os.path.join(ROOT, p)), exist_ok=True)
    with open(os.path.join(ROOT, OUT_JSON), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    manifest = {
        "schema": "phase49-3-stage-manifest-v1",
        "stage": "stage02_cohort_selection",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_ms": round((time.time() - t0) * 1000, 1),
        "inputs": inputs,
        "outputs": {OUT_JSON: {"sha256": sha256(os.path.join(ROOT, OUT_JSON)),
                               "rows": len(members),
                               "bytes": os.path.getsize(os.path.join(ROOT, OUT_JSON))}},
        "db_written": False, "status": "PASS", "idempotent_payload": True,
    }
    with open(os.path.join(ROOT, MANIFEST), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")

    if not args.quiet:
        print("pool eligible:", len(pool), "excluded:", len(excluded))
        print("selected:", len(members))
        for s in strata_report:
            print("  %-30s %d/%d  %s" % (s["stratum"], s["selected"], s["target"],
                                         ",".join(s["symbols"])))
        print("expected raw rows:", doc["diversity_summary"]["expected_raw_rows_total"])
        print("expected gain:", doc["diversity_summary"]["expected_history_gain_rows_total"])
    return 0


if __name__ == "__main__":
    sys.exit(main())