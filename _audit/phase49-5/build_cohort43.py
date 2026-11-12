#!/usr/bin/env python3
"""Phase 4.9.5: define the 43-symbol cohort (30 frozen + 13 approved).

Reads the frozen phase49-3 selection and the restored capture index.
Writes only _audit/phase49-5/cohort/COHORT43.json and its manifest.
"""
from __future__ import annotations

import collections
import csv
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "dev"))
from symbol_identity import key as K  # noqa: E402

MAP_REL = "_audit/phase49-3/ledgers/COVERAGE-EXPANSION-MAP.csv"
STEPS_REL = "docs/opportunity-center/phase49/ADJUSTMENT-EVIDENCE-LEDGER.csv"
SEL_REL = "_audit/phase49-3/evidence/COHORT-SELECTION.json"
INDEX_REL = "_audit/phase49-full-verification/captures/reference-index-all.json"
OUT_REL = "_audit/phase49-5/cohort/COHORT43.json"
MANIFEST_REL = "_audit/phase49-5/manifests/stage00-cohort43.json"
BASE_COMMIT = "18563a6659d5d20b3c74105826ca84b4704340b2"

APPROVED_13 = [
    ("وپترو", "LONG_HISTORY_SPARSE_EVENTS",
     "long history where few events must still chain correctly"),
    ("وملت", "FRESH_SERIES",
     "current series: exercises the capture-day quarantine"),
    ("شكلر", "LONG_HISTORY_DENSE_EVENTS",
     "long captured history with a dense adjustment chain"),
    ("فولاد", "CAPITAL_INCREASE_EVIDENCED",
     "official share-change evidence: shares_old/shares_new ratio path"),
    ("پكرمان", "MID_HISTORY",
     "the bulk of the queue: median-length windows"),
    ("وسديد", "HISTORICAL_ANOMALY",
     "zero-volume / invalid-OHLC history in the local seed"),
    ("شتران", "REFERENCE_SESSION_DEFICIT",
     "reference spans the window but lacks local sessions"),
    ("كوثر", "PRICE_ADJUST_EVIDENCED",
     "product price-adjust evidence alongside the measured reference"),
    ("دبالك", "RATIO_CONFLICT_PRESENT",
     "pack ratio disagrees with the reference: supersede path"),
    ("هامرز", "CAPTURE_ONLY_MEASURED_RATIO",
     "measured ratio with no official type: must stay unclassified"),
    ("فن افزار", "CAPITAL_INCREASE_EVIDENCED",
     "official share-change evidence: shares_old/shares_new ratio path"),
    ("نيك گستر", "REFERENCE_WITH_ZERO_STEPS",
     "full reference window and no factor step: factor must stay 1"),
    ("ثپهران", "SHORT_HISTORY",
     "short window: anchor and boundary behaviour dominates"),
]

SELECTION_RULE = (
    "phase49-3 strata predicates + deterministic spread over the eligible "
    "QUEUE_REFERENCE_ONLY pool present in the restored capture; 1 symbol per "
    "stratum + 1 extra to CAPITAL_INCREASE_EVIDENCED; disjoint from the frozen "
    "30 and the previous pilot; paired type0/type7 required"
)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def I(r, k):
    try:
        return int(r.get(k) or 0)
    except (TypeError, ValueError):
        return 0


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


def member_from_row(r, agg, capture, stratum, reason, verification):
    bars = I(r, "ref_type0_bars")
    steps = I(r, "step_rows")
    return {
        "symbol": r["symbol"], "key": r["key"], "ins_code": r["ins_code"],
        "isin": r["isin"], "asset_id": r["asset_id"],
        "stratum": stratum, "selection_reason": reason,
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
        "events_per_1000_sessions": (round(1000.0 * steps / bars, 3) if bars else 0.0),
        "anomalies": I(r, "anomalies"),
        "invalid_ohlc_legacy": I(r, "invalid_ohlc_legacy"),
        "gaps": I(r, "gaps"),
        "legacy_unknown_rows": I(r, "legacy_unknown_rows"),
        "price_basis_risk": r["price_basis_risk"],
        "ledger_final_status": r["ledger_final_status"],
        "evidence": agg,
        "verification_status": verification,
        "capture_type0_rows": capture["type0"]["n"],
        "capture_type7_rows": capture["type7"]["n"],
        "capture_first": capture["type0"]["first"],
        "capture_last": capture["type0"]["last"],
        "capture_date_conflicts": capture.get("date_conflicts"),
    }


def main():
    started = time.time()
    inputs = {}
    for rel in (MAP_REL, STEPS_REL, SEL_REL, INDEX_REL):
        p = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.exists(p):
            sys.exit("FATAL missing input %s" % rel)
        inputs[rel] = {"sha256": sha256(p), "bytes": os.path.getsize(p)}

    M = list(csv.DictReader(open(os.path.join(ROOT, MAP_REL), encoding="utf-8", newline="")))
    S = list(csv.DictReader(open(os.path.join(ROOT, STEPS_REL), encoding="utf-8", newline="")))
    sel = json.load(open(os.path.join(ROOT, SEL_REL), encoding="utf-8"))
    index = json.load(open(os.path.join(ROOT, INDEX_REL), encoding="utf-8"))

    bysym = collections.defaultdict(list)
    for r in S:
        bysym[r["symbol"]].append(r)
    refk = {K(e.get("key") or s): e for s, e in index.items()}

    frozen = sel["members"]
    frozen_keys = {K(m["key"]) for m in frozen}
    assert len(frozen) == 30, len(frozen)

    approved_keys = {K(s) for s, _st, _why in APPROVED_13}
    assert len(approved_keys) == 13, len(approved_keys)
    assert not (approved_keys & frozen_keys), "13 overlaps the frozen 30"

    bykey = {K(r["key"]): r for r in M}
    new_members = []
    for symbol, stratum, reason in APPROVED_13:
        r = bykey.get(K(symbol))
        if r is None:
            sys.exit("FATAL approved symbol missing from map: %s" % symbol)
        if r["phase49_2_status"] != "QUEUE_REFERENCE_ONLY":
            sys.exit("FATAL %s status %s" % (symbol, r["phase49_2_status"]))
        if r["identity_status"] != "resolved_instruments" or not r["asset_id"]:
            sys.exit("FATAL %s identity/asset not eligible" % symbol)
        if r["raw_ohlc_valid"] != "ok" or r["stale_status"] == "halted":
            sys.exit("FATAL %s raw/ halted not eligible" % symbol)
        cap = refk.get(K(r["key"]))
        if cap is None:
            sys.exit("FATAL %s absent from restored capture index" % symbol)
        t0, t7 = cap["type0"]["n"], cap["type7"]["n"]
        if t0 <= 0 or t7 <= 0 or t0 != t7 or cap.get("date_conflicts") != 0:
            sys.exit("FATAL %s capture pairing invalid t0=%d t7=%d" % (symbol, t0, t7))
        if t0 != I(r, "ref_type0_bars"):
            sys.exit("FATAL %s capture n %d != map ref_type0_bars %d"
                     % (symbol, t0, I(r, "ref_type0_bars")))
        agg = step_agg(bysym.get(r["symbol"], []))
        new_members.append(member_from_row(
            r, agg, cap, stratum, reason, "CAPTURE_RESTORED_READY_INGEST"))

    members = list(frozen) + new_members
    keys = [K(m["key"]) for m in members]
    assert len(keys) == len(set(keys)) == 43, (len(keys), len(set(keys)))
    expected_total = sum(I(m, "expected_raw_rows") for m in members)
    expected_new = sum(m["expected_raw_rows"] for m in new_members)
    assert expected_total == 122944, expected_total
    assert expected_new == 38492, expected_new

    strata_report = []
    for name in sorted({m["stratum"] for m in new_members}):
        syms = [m["symbol"] for m in new_members if m["stratum"] == name]
        strata_report.append({"stratum": name, "selected": len(syms), "symbols": syms})

    doc = {
        "schema": "phase49-5-cohort43-v1",
        "mission": "phase49-5-43symbol-independent-db",
        "base_commit": BASE_COMMIT,
        "capture_status": "RESTORED_VERIFIED",
        "target": 43, "selected": 43,
        "frozen_30_source": {"path": SEL_REL, "sha256": inputs[SEL_REL]["sha256"]},
        "approved_13": {
            "selection_rule": SELECTION_RULE,
            "rule_script": "_audit/phase49-5/build_cohort43.py",
            "approved_by_owner": True,
            "members": [m["symbol"] for m in new_members],
        },
        "inputs": inputs,
        "strata": strata_report,
        "expected_raw_rows_total": expected_total,
        "expected_raw_rows_frozen_30": expected_total - expected_new,
        "expected_raw_rows_new_13": expected_new,
        "members": members,
    }

    out = os.path.join(ROOT, OUT_REL.replace("/", os.sep))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    manifest = {
        "schema": "phase49-5-stage-manifest-v1",
        "stage": "stage00_cohort43",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_ms": round((time.time() - started) * 1000, 1),
        "inputs": inputs,
        "outputs": {OUT_REL: {"sha256": sha256(out), "rows": 43,
                              "bytes": os.path.getsize(out)}},
        "db_written": False, "status": "PASS", "idempotent_payload": True,
    }
    man = os.path.join(ROOT, MANIFEST_REL.replace("/", os.sep))
    with open(man, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    print("cohort43 members:", len(members), "new:", len(new_members),
          "expected raw rows:", expected_total)
    print("output:", OUT_REL, sha256(out))


if __name__ == "__main__":
    main()
