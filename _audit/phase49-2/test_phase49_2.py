#!/usr/bin/env python3
"""Consistency gate for the Phase 4.9.2 evidence bundle (stdlib only).

Runs on the committed evidence JSON/CSV, not on the licensed raw capture or the
large DB. It proves the numbers in the report agree with the files that back
them, so a silent edit or a stale artifact fails the gate.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AUD = os.path.join(ROOT, "_audit", "phase49-2")
DOC = os.path.join(ROOT, "docs", "opportunity-center", "phase49-2")
PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS " + name)
    else:
        FAIL += 1
        print("  FAIL " + name + (" — " + detail if detail else ""))


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main():
    baseline = load(os.path.join(AUD, "evidence", "baseline.json"))
    c = baseline["counts"]
    check("baseline: 1,358 baseline-unverified", c["baseline_unverified_rows"] == 1358)
    check("baseline: 1,179 still unverified", c["still_unverified_steps"] == 1179)
    check("baseline: 5,185 no reference+step",
          c["symbols_without_reference_and_step"] == 5185)
    check("baseline: 53,176 unresolved anomalies", c["anomaly_unresolved_gap"] == 53176)
    check("baseline: 306 invalid OHLC", c["invalid_ohlc_rows"] == 306)
    check("baseline: 105,367 reference rows", c["reference_derived_rows"] == 105367)
    check("baseline: 339 unmapped", c["unmapped_asset_symbols"] == 339)

    pilot = load(os.path.join(AUD, "rahavard", "pilot-symbols.json"))
    names = [p["symbol"] for p in pilot]
    check("pilot: 30 unique symbols", len(names) == 30 and len(set(names)) == 30)
    for sym in ("شنفت", "طلا", "تپسي", "غشان", "ولانا"):
        check("pilot: mandatory %s" % sym, sym in names)

    analysis = load(os.path.join(AUD, "rahavard", "pilot-analysis.json"))
    t = analysis["totals"]
    check("analysis: 30 symbols", t["symbols"] == 30)
    check("analysis: 1,027 reference changes",
          t["MATCH"] + t["NO_PACK_STEP"] + t["RATIO_DIFF"] == 1027,
          repr(t))
    check("analysis: 364 no-pack steps", t["NO_PACK_STEP"] == 364)
    check("analysis: 2 ratio diffs", t["RATIO_DIFF"] == 2)

    ingest = load(os.path.join(AUD, "evidence", "candle-ingest.json"))
    ic = ingest["counts"]
    check("ingest: 105,692 raw rows", ic["reference_raw_rows"] == 105692)
    check("ingest: 105,692 adjusted rows", ic["reference_adjusted_rows"] == 105692)
    check("ingest: 1,027 factors", ic["adjustment_factors"] == 1027)
    check("ingest: factor kinds sum", sum(ic["kinds"].values()) == 1027)
    check("ingest: 30 partial bars excluded", ingest["partial_bars_excluded"] == 30)
    check("ingest: revision is sha256", len(ingest["revision"]) == 64)

    before = load(os.path.join(AUD, "rahavard", "engine-parity-before.json"))
    after = load(os.path.join(AUD, "rahavard", "engine-parity-after.json"))
    before_ok = sum(1 for s in before["symbols"] if (s["max_rel"] or 0) <= 1e-6)
    check("parity before: 16 exact", before_ok == 16, str(before_ok))
    check("parity before: worst > 1000x",
          max(s["max_rel"] or 0 for s in before["symbols"]) > 1000)
    check("parity after: 30 symbols", len(after["symbols"]) == 30)
    check("parity after: all exact",
          all((s["max_rel"] or 0) <= 1e-6 for s in after["symbols"]))
    check("parity after: all local-measured-factors",
          all(s["adjust_source"] == "local-measured-factors"
              for s in after["symbols"]))
    check("parity after: 1,027 events",
          sum(s["event_count"] for s in after["symbols"]) == 1027)
    check("parity after: no missing/extra/ratio diff",
          all(not s["missing_engine_steps"] and not s["extra_engine_steps"]
              and not s["ratio_diffs"] for s in after["symbols"]))

    events = load(os.path.join(AUD, "evidence", "event-parity.json"))
    check("event parity: after all exact", events["after_all_exact"] is True)
    check("event parity: 1,027 matches",
          events["counts"]["after"].get("MATCH") == 1027)
    check("event parity: before 67 missing",
          events["counts"]["before"].get("MISSING_IN_ENGINE") == 67)

    coverage = load(os.path.join(AUD, "evidence", "coverage-status.json"))
    check("coverage: 6,103 rows", coverage["rows"] == 6103)
    check("coverage: 30 READY_PILOT",
          coverage["status_counts"].get("READY_PILOT") == 30)
    for sym in ("شنفت", "طلا", "تپسي", "غشان", "ولانا"):
        row = coverage["named_cases"][sym]
        check("coverage: %s READY" % sym, row and row["status"] == "READY_PILOT")

    update = load(os.path.join(AUD, "evidence", "update-chain-proof.json"))
    check("update: all checks true", update["ok"] is True)
    check("update: revision changed", update["checks"]["revision_changed"] is True)
    check("update: pre-event factor 1.0",
          update["before"]["factor_last_pre_event"] == 1.0)
    check("update: measured split factor",
          abs(update["after"]["factor_last_pre_event"] / 0.14950616 - 1) < 1e-5)

    seed = load(os.path.join(AUD, "evidence", "seed-recheck.json"))
    check("seed: all checks true", seed["ok"] is True)
    check("seed: 14 checks", len(seed["checks"]) == 14)

    approval = load(os.path.join(
        DOC, "OWNER-APPROVAL-REFERENCE-DERIVED.json"))
    check("approval: approved + scope + count",
          approval["approved"] is True
          and approval["scope"] == "reference_derived_rows"
          and approval["expected_reference_derived_rows"] == 105367)
    manifest = load(os.path.join(
        ROOT, "docs", "opportunity-center", "phase49", "FINAL-SEED-MANIFEST.json"))
    check("manifest: owner_approvals recorded",
          manifest.get("owner_approvals")
          and manifest["owner_approvals"][0]["approved"] is True)

    print("PHASE 4.9.2 EVIDENCE GATE: %d PASS, %d FAIL" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
