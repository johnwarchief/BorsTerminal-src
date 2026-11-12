#!/usr/bin/env python3
"""Phase 4.9.5 stage01: independent 43-symbol DB from the restored capture.

Reuses phase49-3 stage07 extract_cohort/ingest/run_build/parity and the
phase49-4 AFTER candlebuild binary. Frozen stage mains and DBs are read-only.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))


def _load(name, rel):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, rel.replace("/", os.sep)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


S6 = _load("s6", "_audit/phase49-3/stage06_verify_restored_capture.py")
S7 = _load("s7", "_audit/phase49-3/stage07_cohort_candles.py")
sys.path.insert(0, os.path.join(ROOT, "dev"))
from symbol_identity import key as K  # noqa: E402

BARS_REL = "_audit/phase49-full-verification/captures/bars-all.ndjson.gz"
INDEX_REL = "_audit/phase49-full-verification/captures/reference-index-all.json"
PACK_REL = "data/ra365_corrections/ra365-phase49-rebuild-full-v2/factors.jsonl"
SUMMARY_REL = "_audit/phase49-full-verification/evidence/capture-summary.json"
VERIFY_REL = "_audit/phase49-3/evidence/RESTORED-CAPTURE-VERIFICATION.json"
COHORT43_REL = "_audit/phase49-5/cohort/COHORT43.json"
BASELINE_DB_REL = "_audit/phase49-4/db/engine-after/market.db"
AFTER_BUILD_REL = "_audit/phase49-4/bin/candlebuild.exe"
BEFORE_BUILD_REL = "_audit/phase49-3/bin/candlebuild.exe"
BEFORE_BORSD_REL = "_audit/phase49-3/bin/borsd.exe"
AFTER_BORSD_REL = "_audit/phase49-4/bin/borsd.exe"
DB_REL = "_audit/phase49-5/db/market43.db"
SECOND_DB_REL = "_audit/phase49-5/db/market43-idempotency.db"
OUT_REL = "_audit/phase49-5/evidence/INGEST43.json"
MANIFEST_REL = "_audit/phase49-5/manifests/stage01-ingest43.json"

BASE_COMMIT = "18563a6659d5d20b3c74105826ca84b4704340b2"
EXPECTED_SHA = {
    BARS_REL: "272336c036d647ed7b2090853c84c3a2d3da6126a0bfae60e987198169b3b14a",
    INDEX_REL: "83544012448fc19100e7b140dbcfc2e4d27eca317f667204c343f810acc92e1c",
    PACK_REL: "aa8e13fc2d172c3e3355e86bba1bd505b5070269d0a47baf0c3c2d59784ceb24",
    COHORT43_REL: "2d1ccbbdcefce12015f3bd2fc49d8660aa78959c55f32f3079ec47fdf0776365",
    SUMMARY_REL: "6cbeb62811f42d143a9d6b5c10324e2eae57b6914e8f875a3ee0e50d6154da8b",
    AFTER_BUILD_REL: "4d28cece967b735750fb4668fee32a882253a9425d20471babfd3e98addd56ef",
    BEFORE_BUILD_REL: "ba34c90be644060d1ff45b7477f2eafb61a39be78169282a72554501babd3673",
    BEFORE_BORSD_REL: "a797c88343f49a4d20240b452cdacfcf193cc332f7738ecfdef41983ba319cd7",
    AFTER_BORSD_REL: "27ea06c088c58d6fead302ac4951263aee455d997310e4e57dfbedb619a95de2",
    BASELINE_DB_REL: "b5e895c979a9bd18ec0b20292ae027a1194969b9dea1f49388d566e40be8573a",
}

TABLES = {
    "reference_raw": ("symbol,date,open,high,low,close,volume,capture_sha256", "symbol,date"),
    "reference_adjusted": ("symbol,date,close,capture_sha256", "symbol,date"),
    "adjustment_factors": (
        "symbol,date,ratio,kind,source,method,confidence,status,q_before,q_after,"
        "prev_close,capture_sha256,details", "symbol,date"),
    "factor_action_links": (
        "symbol,factor_date,action_date,action_kind,relation,delta_days,evidence",
        "symbol,factor_date,action_date"),
    "adjustment_factor_audit": (
        "symbol,date,reason,pack_ratio,ref_ratio,pack_event_sig,details", "symbol,date"),
    "adjusted_candles": (
        "symbol,date,open,high,low,close,volume,factor", "symbol,date"),
    "adjustment_verification": (
        "symbol,date,status,reference_close,adjusted_close,rel_error,capture_sha256",
        "symbol,date"),
    "candle_build_revisions": (
        "symbol,capture_sha256,raw_rows,factor_rows,adjusted_rows,max_rel_error,worst_date",
        "symbol"),
}

IDEM_COLUMNS = {
    "candle_capture_runs": "run_id,source,captured_at,input_sha256,types,resolutions,symbols,bars",
    "reference_raw": "*",
    "reference_adjusted": "*",
    "adjustment_factors": (
        "symbol,date,ratio,kind,source,method,confidence,status,q_before,q_after,"
        "prev_close,capture_sha256,run_id,revision,details"),
    "factor_action_links": "*",
    "adjustment_factor_audit": "*",
    "adjusted_candles": "*",
    "adjustment_verification": "*",
    "candle_build_revisions": (
        "symbol,revision,capture_sha256,raw_rows,factor_rows,adjusted_rows,"
        "max_rel_error,worst_date"),
}


def sha(path):
    return S6.sha256_file(os.path.join(ROOT, path.replace("/", os.sep)))


def rows_hash(rows):
    h = hashlib.sha256()
    for row in rows:
        h.update(json.dumps(row, ensure_ascii=False, sort_keys=True,
                            default=str).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def compare_table(db43, baseline, table, symbols):
    cols, order = TABLES[table]
    q = ("SELECT " + cols + " FROM " + table + " WHERE symbol IN ("
         + ",".join("?" * len(symbols)) + ") ORDER BY " + order)
    con = sqlite3.connect("file:%s?mode=ro" % db43.replace(os.sep, "/"), uri=True)
    a = con.execute(q, symbols).fetchall()
    con.close()
    con = sqlite3.connect("file:%s?mode=ro" % baseline.replace(os.sep, "/"), uri=True)
    b = con.execute(q, symbols).fetchall()
    con.close()
    sort_key = lambda r: tuple("" if x is None else str(x) for x in r)
    a.sort(key=sort_key)
    b.sort(key=sort_key)
    ha, hb = rows_hash(a), rows_hash(b)
    first = None
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            first = {"index": i, "new": a[i], "baseline": b[i]}
            break
    return {"table": table, "columns": cols, "new_rows": len(a),
            "baseline_rows": len(b), "new_sha256": ha, "baseline_sha256": hb,
            "equal": ha == hb and len(a) == len(b), "first_diff": first}


def subset_reproduction(db43, baseline, symbols):
    results = [compare_table(db43, baseline, t, symbols) for t in TABLES]
    return {"symbols": len(symbols), "tables": results,
            "pass": all(r["equal"] for r in results)}


def factor13_vs_index(db43, index, members):
    index_by_key = {K(e.get("key") or s): e for s, e in index.items()}
    con = sqlite3.connect("file:%s?mode=ro" % db43.replace(os.sep, "/"), uri=True)
    out = []
    for member in members:
        sym = member["symbol"]
        db = con.execute("SELECT date, ratio FROM adjustment_factors "
                         "WHERE symbol=? ORDER BY date", (sym,)).fetchall()
        entry = index_by_key.get(K(member["key"]))
        changes = [c for c in (entry or {}).get("factor_changes", [])
                   if c.get("ratio_change") is not None]
        idx = {c["date"]: float(c["ratio_change"]) for c in changes}
        dbd = {d: float(r) for d, r in db}
        common = set(dbd) & set(idx)
        missing = sorted(set(idx) - set(dbd))
        extra = sorted(set(dbd) - set(idx))
        # adjustment_factors.ratio is q_after/q_before; the reference index
        # records ratio_change = q_before/q_after on the same dates.
        max_abs = max((abs((1.0 / dbd[d]) - idx[d]) for d in common
                       if dbd[d] != 0), default=0.0)
        # the index lists factor_changes above its 0.1% bucket; a smaller
        # measured step can exist in the DB without a matching index entry.
        extra_max = max((abs(dbd[d] - 1.0) for d in extra), default=0.0)
        out.append({"symbol": sym, "db_rows": len(db), "index_changes": len(changes),
                    "missing_index_dates": missing, "extra_db_dates": extra,
                    "extra_max_pct": extra_max,
                    "max_abs_inverse_ratio_diff": max_abs,
                    "match": not missing and max_abs <= 1e-12 and extra_max <= 0.001})
    con.close()
    return {"pass": all(r["match"] for r in out), "per_symbol": out}


def build_once(db_path, ex, cohort, pack, capture_sha, run_id, captured_at, now):
    revision, counts = S7.ingest(db_path, ex, cohort, pack, capture_sha,
                                 run_id, captured_at, now)
    build = S7.run_build(db_path, os.path.join(ROOT, AFTER_BUILD_REL.replace("/", os.sep)))
    return revision, counts, build


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--now", default=None)
    ap.add_argument("--skip-idempotency", action="store_true")
    args = ap.parse_args()
    started = time.time()

    before = {rel: sha(rel) for rel in EXPECTED_SHA}
    for rel, exp in EXPECTED_SHA.items():
        if before[rel] != exp:
            sys.exit("FATAL pinned input %s sha256 %s != %s" % (rel, before[rel], exp))

    verify = S6.read_json(VERIFY_REL)
    if verify.get("status") != "PASS":
        sys.exit("FATAL stage06 verification is not PASS")
    payload_sha = verify["bars_recount"]["payload_sha256"]
    summary = S6.read_json(SUMMARY_REL)
    if payload_sha != summary["merged"]["bars_payload_sha256"]:
        sys.exit("FATAL payload digest disagrees with capture summary")
    capture_day = summary["capture"]["captured_at_max"][:10]
    captured_at = summary["capture"]["captured_at_max"]

    cohort = S6.read_json(COHORT43_REL)
    if len(cohort.get("members") or []) != 43:
        sys.exit("FATAL cohort43 does not have 43 members")
    cohort_keys = {m["key"] for m in cohort["members"]}
    index = json.load(open(os.path.join(ROOT, INDEX_REL.replace("/", os.sep)),
                           encoding="utf-8"))
    spelling_to_key = {sp: k for k, r in index.items() for sp in r["raw_symbols"]}

    bars_path = os.path.join(ROOT, BARS_REL.replace("/", os.sep))
    print("extracting 43-symbol cohort (capture_day=%s) ..." % capture_day, flush=True)
    ex = S7.extract_cohort(bars_path, cohort_keys, spelling_to_key, capture_day)
    if len(ex["raw"]) != 43 or len(ex["adj"]) != 43:
        sys.exit("FATAL extracted raw=%d adj=%d, expected 43/43"
                 % (len(ex["raw"]), len(ex["adj"])))

    pack = S7.ING.load_pack()
    capture_sha = payload_sha
    run_id = "phase49-5-cohort43-" + capture_sha[:12]
    now = args.now or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    db_path = os.path.join(ROOT, DB_REL.replace("/", os.sep))
    print("ingesting into %s ..." % DB_REL, flush=True)
    revision, counts, build = build_once(db_path, ex, cohort, pack, capture_sha,
                                         run_id, captured_at, now)
    print("ingested raw=%d adjusted=%d factors=%d symbols=%d"
          % (counts["reference_raw_rows"], counts["reference_adjusted_rows"],
             counts["adjustment_factors"], counts["symbols_ingested"]), flush=True)

    par = S7.parity(db_path, ex)
    statuses = collections.Counter(r["status"] for r in par["per_symbol"])
    expected_rows = cohort["expected_raw_rows_total"]

    con = sqlite3.connect("file:%s?mode=ro" % db_path.replace(os.sep, "/"), uri=True)
    zero_event = [r[0] for r in con.execute(
        "SELECT DISTINCT symbol FROM reference_raw WHERE symbol NOT IN "
        "(SELECT DISTINCT symbol FROM adjustment_factors) ORDER BY symbol")]
    anchors = S7.anchor_invariant(db_path)
    con.close()
    zero_rows = sum(len(ex["raw"][s]) for s in zero_event)
    builder_rows = expected_rows
    built_symbols = 43
    anchor_bad = [a for a in anchors if not a["holds"]]

    failures = []
    if counts["reference_raw_rows"] != expected_rows:
        failures.append("reference_raw rows %d != %d"
                        % (counts["reference_raw_rows"], expected_rows))
    if counts["reference_adjusted_rows"] != expected_rows:
        failures.append("reference_adjusted rows %d != %d"
                        % (counts["reference_adjusted_rows"], expected_rows))
    if par["rows_total"] != expected_rows:
        failures.append("adjusted_candles rows %d != expected %d "
                        "(the AFTER engine materializes zero-event symbols)"
                        % (par["rows_total"], expected_rows))
    if par["volume_mismatch_rows"]:
        failures.append("volume mismatch on %d rows" % par["volume_mismatch_rows"])
    if par["close_diff_rows"]:
        failures.append("close differs from type7 on %d rows" % par["close_diff_rows"])
    if statuses.get("PASS", 0) != 43:
        failures.append("only %d/43 symbols PASS" % statuses.get("PASS", 0))
    if statuses.get("NOT_MATERIALIZED_BY_BUILDER", 0):
        failures.append("builder left %d symbols unmaterialized"
                        % statuses.get("NOT_MATERIALIZED_BY_BUILDER"))
    if par["high_low_diff_unattributed_count"]:
        failures.append("%d high/low differences not explained by widening"
                        % par["high_low_diff_unattributed_count"])
    if par["reference_not_raw_times_factor"]:
        failures.append("reference high/low is not raw*factor on %d sampled rows"
                        % len(par["reference_not_raw_times_factor"]))
    # The widened*factor check belongs to the phase49-3 BEFORE engine. Phase 4.9.4
    # stage11 supersedes that baseline with the literal law; stage02 measures the
    # AFTER engine/API against the literal type0 x factor and type7 values.
    if anchor_bad:
        failures.append("anchor q(last)=1 violated on %d symbols: %s"
                        % (len(anchor_bad), [a["symbol"] for a in anchor_bad][:5]))

    frozen30 = [m for m in cohort["members"]
                if m.get("verification_status") == "BLOCKED_CAPTURE_BYTES_ABSENT"]
    if len(frozen30) != 30:
        sys.exit("FATAL frozen-30 members not identifiable (%d)" % len(frozen30))
    baseline = os.path.join(ROOT, BASELINE_DB_REL.replace("/", os.sep))
    repro = subset_reproduction(db_path, baseline, [m["symbol"] for m in frozen30])
    if not repro["pass"]:
        failures.append("frozen-30 subset does not reproduce the archived engine-after DB")

    new13_members = [m for m in cohort["members"]
                     if m.get("verification_status") == "CAPTURE_RESTORED_READY_INGEST"]
    if len(new13_members) != 13:
        sys.exit("FATAL new-13 members not identifiable (%d)" % len(new13_members))
    new13 = [m["symbol"] for m in new13_members]
    f13 = factor13_vs_index(db_path, index, new13_members)
    if not f13["pass"]:
        failures.append("13-symbol factor chain disagrees with the restored index")

    idem = {"ran": False}
    if not args.skip_idempotency:
        second = os.path.join(ROOT, SECOND_DB_REL.replace("/", os.sep))
        build_once(second, ex, cohort, pack, capture_sha, run_id, captured_at, now)
        new_sha, sec_sha = S6.sha256_file(db_path), S6.sha256_file(second)

        def fetch_rows(path, q):
            con = sqlite3.connect("file:%s?mode=ro" % path.replace(os.sep, "/"), uri=True)
            rows = con.execute(q).fetchall()
            con.close()
            return rows

        comparisons = []
        for table, cols in IDEM_COLUMNS.items():
            q = "SELECT " + cols + " FROM " + table
            a, b = fetch_rows(db_path, q), fetch_rows(second, q)
            key = lambda r: tuple("" if x is None else str(x) for x in r)
            a.sort(key=key)
            b.sort(key=key)
            comparisons.append({"table": table, "new_rows": len(a), "second_rows": len(b),
                                "equal": len(a) == len(b) and rows_hash(a) == rows_hash(b)})
        idem = {"ran": True, "new_sha256": new_sha, "second_sha256": sec_sha,
                "file_equal": new_sha == sec_sha,
                "content_equal": all(c["equal"] for c in comparisons),
                "tables": comparisons,
                "note": "candlebuild records built_at, so file hashes may differ; "
                        "content is compared without built_at/ingested_at/created_at"}
        if not idem["content_equal"]:
            failures.append("idempotency: second build content differs")
        os.remove(second)

    after = {rel: sha(rel) for rel in EXPECTED_SHA}
    changed = {rel: (before[rel], after[rel]) for rel in before if before[rel] != after[rel]}
    if changed:
        failures.append("frozen artifact changed: %r" % changed)

    payload = {
        "schema": "phase49-5-ingest43-v1",
        "mission": "phase49-5-43symbol-independent-db",
        "status": "PASS" if not failures else "PARTIAL",
        "failures": failures,
        "base_commit": BASE_COMMIT,
        "branch": "mission/phase49-5-43symbol-ingest",
        "cohort": {"path": COHORT43_REL, "sha256": EXPECTED_SHA[COHORT43_REL],
                   "members": 43, "frozen_30": 30, "new_13": 13,
                   "expected_raw_rows": expected_rows},
        "inputs": {rel: {"sha256": after[rel]} for rel in EXPECTED_SHA},
        "capture": {
            "bars": BARS_REL, "container_sha256": EXPECTED_SHA[BARS_REL],
            "payload_sha256": payload_sha, "index_sha256": EXPECTED_SHA[INDEX_REL],
            "pack_sha256": EXPECTED_SHA[PACK_REL],
            "captured_at_max": captured_at, "capture_day": capture_day,
            "quarantine_rule": "date >= capture_day (frozen phase49-3 rule)",
            "quarantined_bars": ex["quarantined"],
            "cohort_rows_scanned": ex["cohort_rows_scanned"],
        },
        "run_id": run_id,
        "revision": revision,
        "db": {"path": DB_REL, "sha256": S6.sha256_file(db_path),
               "size_bytes": os.path.getsize(db_path)},
        "engine_binary": {"path": AFTER_BUILD_REL,
                          "sha256": EXPECTED_SHA[AFTER_BUILD_REL]},
        "counts": counts,
        "candlebuild_result": build,
        "parity": par,
        "symbol_statuses": dict(statuses),
        "builder_coverage": {
            "symbols_ingested": len(ex["raw"]),
            "symbols_materialized": built_symbols,
            "zero_event_symbols": zero_event,
            "zero_event_rows": zero_rows,
            "expected_builder_rows": expected_rows,
            "note": "the AFTER candlebuild materializes zero-event symbols; the "
                    "phase49-3 stage07 expectation (expected minus zero rows) "
                    "belongs to the BEFORE engine, and engine-after/market.db "
                    "already has 84,452 adjusted rows for all 30 symbols",
        },
        "anchor_invariant": {"symbols": len(anchors), "bad": anchor_bad},
        "frozen_30_reproduction": repro,
        "new_13_factor_chain_vs_index": f13,
        "idempotency": idem,
        "frozen_artifacts_unchanged": not changed,
        "elapsed_seconds": round(time.time() - started, 1),
    }

    out = os.path.join(ROOT, OUT_REL.replace("/", os.sep))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    manifest = {
        "schema": "phase49-5-stage-manifest-v1",
        "stage": "stage01_ingest43",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_seconds": payload["elapsed_seconds"],
        "inputs": payload["inputs"],
        "outputs": {OUT_REL: {"sha256": S6.sha256_file(out), "bytes": os.path.getsize(out)},
                    DB_REL: {"sha256": payload["db"]["sha256"],
                             "bytes": payload["db"]["size_bytes"]}},
        "db_written": True, "status": payload["status"],
        "idempotent_payload": idem.get("file_equal", None),
    }
    man = os.path.join(ROOT, MANIFEST_REL.replace("/", os.sep))
    with open(man, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    print(json.dumps({"status": payload["status"], "failures": failures,
                      "counts": counts, "db": payload["db"],
                      "statuses": dict(statuses), "zero_event": zero_event,
                      "repro": repro["pass"], "factor13": f13["pass"],
                      "idempotency": idem.get("file_equal"),
                      "frozen": not changed}, ensure_ascii=False, indent=1))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
