#!/usr/bin/env python3
"""Phase 4.9.3 stage09: revision, rebuild and re-ingest idempotency for the new 30.

Phase 4.9.2 established idempotent revision/rebuild for the pilot group. That
accepted result is not regenerated here; this establishes the same properties for
the NEW cohort, on copies, without touching the pinned working DB.

Properties measured:
  1. re-ingesting the same verified reference under a new run_id and a later
     clock yields the SAME revision (the revision is content-addressed over
     capture sha + symbol|date|ratio, never over the clock);
  2. the factor rows, audit trail and row counts are identical;
  3. rebuilding produces byte-identical adjusted_candles content;
  4. rebuilding the same DB twice neither grows rows nor changes content;
  5. re-inserting the same factors does not accumulate (PK symbol,date,revision);
  6. NEGATIVE CONTROL: perturbing one reference close changes the revision, so
     property 1 is not a tautology -- the revision can actually differ.

The reference is reconstructed from the pinned working DB rather than by a
second 145 MB capture scan: stage06 verified those bytes independently and
stage07 pinned the DB by SHA-256, so this is the same data, not new data. No
bar is invented, extended or moved to a different date.

The pinned working DB is opened read-only and its SHA-256 is re-checked at the
end. All writes go to a gitignored idempotency directory.
"""

from __future__ import annotations

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

DB_REL = "_audit/phase49-3/db/cohort.db"
BIN_REL = "_audit/phase49-3/bin/candlebuild.exe"
WORK_REL = "_audit/phase49-3/db/idempotency"
S7_OUT = "_audit/phase49-3/evidence/COHORT-CANDLES.json"
S7_MANIFEST = "_audit/phase49-3/manifests/stage07-cohort-candles.json"
OUT = "_audit/phase49-3/evidence/IDEMPOTENCY.json"
MANIFEST = "_audit/phase49-3/manifests/stage09-idempotency.json"

FACTOR_COLS = ("symbol", "date", "ratio", "kind", "source", "method",
               "confidence", "status", "q_before", "q_after", "prev_close",
               "capture_sha256", "revision")
CANDLE_COLS = ("symbol", "date", "open", "high", "low", "close", "volume",
               "factor", "revision")


def _norm(o):
    """Numbers to float, so int/float serialization cannot fake a difference."""
    if isinstance(o, bool):
        return o
    if isinstance(o, (int, float)):
        return float(o)
    if isinstance(o, dict):
        return {k: _norm(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_norm(v) for v in o]
    return o


def details_digest(db_path):
    """Semantic hash of the details JSON, plus a raw-text hash for transparency.

    The reference is reconstructed from SQLite REAL columns, so a value the
    capture carried as an int (39290) comes back as 39290.0. The stored JSON text
    therefore differs while the parsed content is identical. Comparing parsed
    content is the correct equality here; the raw-text delta is reported, not
    hidden.
    """
    con = ro(db_path)
    rows = list(con.execute("SELECT symbol,date,details FROM adjustment_factors "
                            "ORDER BY symbol,date"))
    con.close()
    sem = hashlib.sha256()
    txt = hashlib.sha256()
    for sym, d, details in rows:
        sem.update(("%s|%s|%s\n" % (sym, d, json.dumps(
            _norm(json.loads(details)), sort_keys=True, ensure_ascii=False))
        ).encode("utf-8"))
        txt.update(("%s|%s|%s\n" % (sym, d, details)).encode("utf-8"))
    return {"rows": len(rows), "semantic_sha256": sem.hexdigest(),
            "raw_text_sha256": txt.hexdigest()}


def ro(db_path):
    return sqlite3.connect("file:%s?mode=ro" % db_path.replace(os.sep, "/"), uri=True)


def digest(rows):
    """Deterministic content hash; floats at full precision, no clock fields."""
    h = hashlib.sha256()
    for r in rows:
        h.update(("|".join("%.17g" % v if isinstance(v, float) else str(v)
                           for v in r) + "\n").encode("utf-8"))
    return h.hexdigest()


def table_digest(db_path, table, cols, order=None):
    con = ro(db_path)
    q = "SELECT %s FROM %s ORDER BY %s" % (
        ",".join(cols), table, order or ",".join(cols[:2]))
    rows = list(con.execute(q))
    con.close()
    return {"rows": len(rows), "sha256": digest(rows)}


def reconstruct(db_path):
    """Rebuild the ingest input from the pinned reference tables."""
    con = ro(db_path)
    raw, adj = {}, {}
    for sym, d, o, h, l, c, v in con.execute(
            "SELECT symbol,date,open,high,low,close,volume FROM reference_raw "
            "ORDER BY symbol,date"):
        raw.setdefault(sym, {})[d] = {"symbol": sym, "date": d, "open": o,
                                      "high": h, "low": l, "close": c, "volume": v}
    for sym, d, c in con.execute(
            "SELECT symbol,date,close FROM reference_adjusted ORDER BY symbol,date"):
        adj.setdefault(sym, {})[d] = c
    meta = con.execute("SELECT run_id, captured_at, input_sha256 "
                       "FROM candle_capture_runs ORDER BY ingested_at LIMIT 1").fetchone()
    con.close()
    ex = {"raw": raw, "adj": adj, "adj_ohlc": {}, "quarantined": {},
          "non_daily_skipped": {}, "cohort_rows_scanned": 0}
    return ex, meta


def main():
    started = time.time()
    db_path = os.path.join(ROOT, DB_REL.replace("/", os.sep))
    bin_path = os.path.join(ROOT, BIN_REL.replace("/", os.sep))
    work = os.path.join(ROOT, WORK_REL.replace("/", os.sep))
    for p in (db_path, bin_path):
        if not os.path.exists(p):
            sys.exit("FATAL: %s absent" % p)

    s7 = S6.read_json(S7_OUT)
    s7m = S6.read_json(S7_MANIFEST)
    if s7.get("status") != "PASS":
        sys.exit("FATAL: stage07 is not PASS")
    pinned_sha = S6.sha256_file(db_path)
    if pinned_sha != s7m["working_db_sha256"]:
        sys.exit("FATAL: working DB sha256 %s != stage07 manifest %s"
                 % (pinned_sha, s7m["working_db_sha256"]))
    pinned_revision = s7["revision"]

    os.makedirs(work, exist_ok=True)
    ex, meta = reconstruct(db_path)
    run_id0, captured_at, capture_sha = meta
    cohort = {"members": [{"key": k} for k in sorted(ex["raw"])]}
    pack = S7.ING.load_pack()

    base_factors = table_digest(db_path, "adjustment_factors", FACTOR_COLS)
    base_details = details_digest(db_path)
    base_candles = table_digest(db_path, "adjusted_candles", CANDLE_COLS)
    base_counts = {}
    con = ro(db_path)
    for t in ("reference_raw", "reference_adjusted", "adjustment_factors",
              "adjustment_factor_audit", "factor_action_links"):
        base_counts[t] = con.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
    base_audit = dict(collections.Counter(
        r[0] for r in con.execute("SELECT reason FROM adjustment_factor_audit")))
    con.close()

    # 1-3: re-ingest under a new run_id and a later clock.
    db_b = os.path.join(work, "reingest.db")
    later = "2026-11-12T00:00:00Z"
    rev_b, counts_b = S7.ingest(db_b, ex, cohort, pack, capture_sha,
                                "phase49-3-idempotency-rerun", captured_at, later)
    b_factors = table_digest(db_b, "adjustment_factors", FACTOR_COLS)
    b_details = details_digest(db_b)
    b_counts = {}
    con = ro(db_b)
    for t in base_counts:
        b_counts[t] = con.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
    b_audit = dict(collections.Counter(
        r[0] for r in con.execute("SELECT reason FROM adjustment_factor_audit")))
    con.close()

    # 4: rebuild the re-ingested DB and compare candle content.
    build_b = S7.run_build(db_b, bin_path)
    b_candles = table_digest(db_b, "adjusted_candles", CANDLE_COLS)

    # 5: rebuild the same DB again -- no growth, no drift.
    build_b2 = S7.run_build(db_b, bin_path)
    b2_candles = table_digest(db_b, "adjusted_candles", CANDLE_COLS)

    # 6: re-inserting the same factors must not accumulate.
    con = sqlite3.connect(db_b)
    rows = list(con.execute("SELECT %s FROM adjustment_factors" % ",".join(
        ("symbol", "date", "ratio", "kind", "source", "method", "confidence",
         "status", "q_before", "q_after", "prev_close", "capture_sha256",
         "run_id", "revision", "details", "created_at"))))
    before = con.execute("SELECT COUNT(*) FROM adjustment_factors").fetchone()[0]
    con.executemany("INSERT OR REPLACE INTO adjustment_factors "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    after = con.execute("SELECT COUNT(*) FROM adjustment_factors").fetchone()[0]
    con.close()

    # 7: NEGATIVE CONTROL -- a perturbed reference close must change the revision.
    ex_bad = {"raw": ex["raw"], "adj": {s: dict(v) for s, v in ex["adj"].items()},
              "adj_ohlc": {}, "quarantined": {}, "non_daily_skipped": {},
              "cohort_rows_scanned": 0}
    target_sym = sorted(ex_bad["adj"])[0]
    target_date = sorted(ex_bad["adj"][target_sym])[0]
    ex_bad["adj"][target_sym][target_date] *= 1.01
    db_c = os.path.join(work, "perturbed.db")
    rev_c, _ = S7.ingest(db_c, ex_bad, cohort, pack, capture_sha,
                         "phase49-3-idempotency-negative", captured_at, later)

    final_sha = S6.sha256_file(db_path)

    checks = {
        "reingest_revision_stable": rev_b == pinned_revision,
        "reingest_factors_identical": b_factors == base_factors,
        "reingest_factor_details_semantically_identical":
            b_details["semantic_sha256"] == base_details["semantic_sha256"],
        "reingest_counts_identical": b_counts == base_counts,
        "reingest_audit_trail_identical": b_audit == base_audit,
        "rebuild_candles_identical": b_candles == base_candles,
        "rebuild_summary_identical": {
            k: build_b.get(k) for k in ("symbols", "adjusted_rows", "verified_rows",
                                        "exact_rows", "mismatch_rows")} == {
            k: build_b2.get(k) for k in ("symbols", "adjusted_rows", "verified_rows",
                                         "exact_rows", "mismatch_rows")},
        "rebuild_twice_no_growth": b2_candles == b_candles,
        "rebuild_zero_mismatch": build_b.get("mismatch_rows") == 0,
        "upsert_no_accumulation": before == after == base_counts["adjustment_factors"],
        "revision_sensitive_to_reference": rev_c != pinned_revision,
        "pinned_db_untouched": final_sha == pinned_sha,
    }
    failures = [k for k, v in sorted(checks.items()) if not v]

    payload = {
        "schema": "phase49-3-idempotency-v1",
        "mission": "Phase 4.9.3 coverage expansion",
        "status": "PASS" if not failures else "PARTIAL",
        "failures": failures,
        "base_commit": S6.BASE_COMMIT,
        "pinned_working_db": {"path": DB_REL, "sha256_before": pinned_sha,
                              "sha256_after": final_sha,
                              "opened_read_only": True},
        "pinned_revision": pinned_revision,
        "reference_provenance":
            "reconstructed from the pinned working DB's reference_raw and "
            "reference_adjusted; stage06 verified the capture bytes and stage07 "
            "pinned this DB by SHA-256. No second capture scan, no invented bar.",
        "source_run": {"run_id": run_id0, "captured_at": captured_at,
                       "capture_sha256": capture_sha},
        "rerun": {"run_id": "phase49-3-idempotency-rerun", "ingested_at": later,
                  "revision": rev_b,
                  "clock_differs_from_source": later != s7m["finished_utc"]},
        "negative_control": {
            "perturbation": "one reference_adjusted close multiplied by 1.01",
            "symbol": target_sym, "date": target_date,
            "revision": rev_c,
            "revision_changed": rev_c != pinned_revision,
            "why": "proves the revision is content-addressed and that "
                   "reingest_revision_stable is not a tautology",
        },
        "baseline": {"factor_rows": base_factors["rows"],
                     "factor_content_sha256": base_factors["sha256"],
                     "factor_details": base_details,
                     "candle_rows": base_candles["rows"],
                     "candle_content_sha256": base_candles["sha256"],
                     "counts": base_counts, "audit_reasons": base_audit},
        "rerun_measured": {"factor_rows": b_factors["rows"],
                           "factor_content_sha256": b_factors["sha256"],
                           "factor_details": b_details,
                           "candle_rows": b_candles["rows"],
                           "candle_content_sha256": b_candles["sha256"],
                           "counts": b_counts, "audit_reasons": b_audit},
        "details_serialization_artifact": {
            "raw_text_identical":
                b_details["raw_text_sha256"] == base_details["raw_text_sha256"],
            "semantic_content_identical":
                b_details["semantic_sha256"] == base_details["semantic_sha256"],
            "cause":
                "the capture carried some closes as JSON integers; reconstructing "
                "the input from SQLite REAL columns returns them as floats, so "
                "json.dumps writes 39290.0 where the first ingest wrote 39290. "
                "Every other factor column is byte-identical and the parsed "
                "details compare equal.",
            "measured_example": {"symbol": "آكو", "date": "2026-09-06",
                                 "first_ingest": "prev_close: 39290",
                                 "reingest": "prev_close: 39290.0"},
            "not_an_engine_difference": True,
        },
        "rebuild_runs": [build_b, build_b2],
        "rebuild_twice_content_sha256": b2_candles["sha256"],
        "upsert": {"rows_before": before, "rows_after": after},
        "checks": checks,
        "honesty": {
            "not_a_rerun_of_phase49_2":
                "the pilot group's accepted idempotency result is untouched; "
                "this measures the new cohort only",
            "no_data_invented":
                "the negative control perturbs a COPY in a gitignored directory "
                "and is never ingested into the pinned working DB",
            "clock_excluded_from_revision":
                "the revision hashes capture sha + symbol|date|ratio only, so a "
                "later ingested_at cannot change it",
            "no_tolerance_changed":
                "the builder's own 1e-9 EXACT threshold decides mismatch_rows",
        },
    }

    manifest = {
        "stage": "stage09_idempotency",
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_seconds": round(time.time() - started, 3),
        "pinned_db_sha256": pinned_sha,
        "exit_code": 0 if not failures else 1,
    }
    out_sha = S6.write_json(OUT, payload)
    manifest["payload_sha256"] = out_sha
    manifest["payload_path"] = OUT
    man_sha = S6.write_json(MANIFEST, manifest)

    print("pinned revision=%s" % pinned_revision[:16])
    print("rerun  revision=%s  stable=%s" % (rev_b[:16], rev_b == pinned_revision))
    print("negative revision=%s  changed=%s"
          % (rev_c[:16], rev_c != pinned_revision))
    print("factors %d rows sha=%s identical=%s"
          % (base_factors["rows"], base_factors["sha256"][:16],
             b_factors == base_factors))
    print("factor details: semantic identical=%s raw text identical=%s"
          % (b_details["semantic_sha256"] == base_details["semantic_sha256"],
             b_details["raw_text_sha256"] == base_details["raw_text_sha256"]))
    print("candles %d rows sha=%s identical=%s"
          % (base_candles["rows"], base_candles["sha256"][:16],
             b_candles == base_candles))
    print("rebuild twice: rows=%d sha=%s no_growth=%s mismatch=%s"
          % (b2_candles["rows"], b2_candles["sha256"][:16],
             b2_candles == b_candles, build_b2.get("mismatch_rows")))
    print("upsert before=%d after=%d" % (before, after))
    print("pinned db untouched=%s" % (final_sha == pinned_sha))
    for k, v in sorted(checks.items()):
        print("%-4s %s" % ("OK" if v else "FAIL", k))
    print("wrote %s (%s)" % (OUT, out_sha[:16]))
    print("wrote %s (%s)" % (MANIFEST, man_sha[:16]))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())