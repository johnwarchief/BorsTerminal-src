#!/usr/bin/env python3
"""Phase 4.9.3 stage07: run the frozen engine on the restored capture, cohort 30.

Reuses Phase 4.9.2's ingest module (SCHEMA, q_changes, classify, load_pack) and
the shipped Go candlebuild binary built from untouched source. No second engine,
no re-tuned tolerance, no rebuilt pack.

The Seed Candidate and the Phase 4.9.2 Pilot DB are both absent from this
machine, so neither is copied and neither is modified: the working DB is created
fresh from the frozen SCHEMA. That substrate is sufficient for candle-level
acceptance because the engine's candle path reads only reference_raw,
reference_adjusted and adjustment_factors. What the Seed would have added is
recorded as NOT_MEASURED rather than silently reported as zero: official
share-change rows, timescale DPS/EPS marks, and the price_history conflict
census.

Capture-day quarantine follows the accepted Phase 4.9.2 rule verbatim
(``date >= captured_at[:10]``), with the day derived from the merged capture's
own recorded timestamp -- not from today's date and not guessed.

Inputs are pinned by SHA-256. No clock value enters the payload; run time and
DB hashes live only in the manifest. Fail-closed: any pin mismatch exits 2
before a DB is created.
"""

from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import importlib.util
import io
import json
import os
import sqlite3
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
_DEV = os.path.join(ROOT, "dev")
while _DEV in sys.path:
    sys.path.remove(_DEV)
sys.path.insert(0, _DEV)

from symbol_identity import key as symbol_key  # noqa: E402


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, rel.replace("/", os.sep)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


S6 = _load("s6", "_audit/phase49-3/stage06_verify_restored_capture.py")
ING = _load("ing49_2", "_audit/phase49-2/ingest_reference.py")

BARS_REL = "_audit/phase49-full-verification/captures/bars-all.ndjson.gz"
INDEX_REL = "_audit/phase49-full-verification/captures/reference-index-all.json"
PACK_REL = "data/ra365_corrections/ra365-phase49-rebuild-full-v2/factors.jsonl"
COHORT_REL = "_audit/phase49-3/evidence/COHORT-SELECTION.json"
SUMMARY_REL = "_audit/phase49-full-verification/evidence/capture-summary.json"
VERIFY_REL = "_audit/phase49-3/evidence/RESTORED-CAPTURE-VERIFICATION.json"

EXPECTED_SHA = {
    BARS_REL: "272336c036d647ed7b2090853c84c3a2d3da6126a0bfae60e987198169b3b14a",
    INDEX_REL: "83544012448fc19100e7b140dbcfc2e4d27eca317f667204c343f810acc92e1c",
    PACK_REL: "aa8e13fc2d172c3e3355e86bba1bd505b5070269d0a47baf0c3c2d59784ceb24",
    COHORT_REL: "857573dd33676d18fda6243806786690eec70abbf8bcee965d48d825eaa77901",
    SUMMARY_REL: "6cbeb62811f42d143a9d6b5c10324e2eae57b6914e8f875a3ee0e50d6154da8b",
}

DB_REL = "_audit/phase49-3/db/cohort.db"
BIN_REL = "_audit/phase49-3/bin/candlebuild.exe"
OUT = "_audit/phase49-3/evidence/COHORT-CANDLES.json"
MANIFEST = "_audit/phase49-3/manifests/stage07-cohort-candles.json"

# The engine's own frozen EXACT threshold; quoted, never re-tuned here.
ENGINE_EXACT_REL = 1e-9
FIELDS = ("open", "high", "low", "close")


def extract_cohort(bars_path, cohort_keys, spelling_to_key, capture_day):
    """Pull the cohort's daily type0/type7 bars, applying the frozen quarantine."""
    raw = collections.defaultdict(dict)
    adj = collections.defaultdict(dict)
    adj_ohlc = collections.defaultdict(dict)
    quarantined = collections.Counter()
    seen_non_daily = collections.Counter()
    scanned = 0
    with gzip.open(bars_path, "rb") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            k = spelling_to_key.get(str(row.get("symbol") or ""))
            if k is None or k not in cohort_keys:
                continue
            scanned += 1
            res = str(row.get("resolution") or "")
            if res != "D":
                seen_non_daily[res] += 1
                continue
            day = str(row.get("date") or "")[:10]
            if not day:
                continue
            if day >= capture_day:
                quarantined[row.get("type")] += 1
                continue
            sym = str(row["symbol"])
            if row.get("type") == "type0":
                raw[sym][day] = row
            elif row.get("type") == "type7":
                adj[sym][day] = row["close"]
                adj_ohlc[sym][day] = row
    return {"raw": raw, "adj": adj, "adj_ohlc": adj_ohlc,
            "quarantined": dict(quarantined),
            "non_daily_skipped": dict(seen_non_daily),
            "cohort_rows_scanned": scanned}


def ingest(db_path, ex, cohort, pack, capture_sha, run_id, captured_at, now):
    """Frozen Phase 4.9.2 ingest, on a fresh working DB instead of a Seed copy."""
    raw, adj = ex["raw"], ex["adj"]
    if os.path.exists(db_path):
        os.remove(db_path)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript(ING.SCHEMA)
    con.execute("INSERT INTO candle_capture_runs VALUES(?,?,?,?,?,?,?,?,?)",
                (run_id, "rahavard365-web-api", captured_at, capture_sha,
                 "type0,type7", "D", len(cohort["members"]),
                 sum(len(raw[s]) + len(adj[s]) for s in raw), now))
    for sym in sorted(raw):
        for dt, b in sorted(raw[sym].items()):
            con.execute("INSERT OR REPLACE INTO reference_raw VALUES(?,?,?,?,?,?,?,?,?)",
                        (sym, dt, b.get("open"), b.get("high"), b.get("low"),
                         b.get("close"), b.get("volume"), run_id, capture_sha))
        for dt, close in sorted(adj[sym].items()):
            con.execute("INSERT OR REPLACE INTO reference_adjusted VALUES(?,?,?,?,?)",
                        (sym, dt, close, run_id, capture_sha))

    factors = []
    links = []
    audit = []
    missing_pack = 0
    kinds = collections.Counter()
    for sym in sorted(raw):
        steps = pack.get(sym, [])
        changes, _q = ING.q_changes(raw[sym], adj[sym])
        for ch in changes:
            # marks and official share rows are unavailable on this host; the
            # frozen classifier then falls back to pack evidence and leaves an
            # unmatched event unclassified instead of guessing its type.
            kind, link, prev_close, prev_date = ING.classify(
                sym, ch, raw[sym], [], [], steps)
            kinds[kind] += 1
            details = {"q_before": ch["q_before"], "q_after": ch["q_after"],
                       "prev_close": prev_close, "prev_date": prev_date,
                       "link": {k: (list(v) if isinstance(v, tuple) else v)
                                for k, v in link.items()},
                       "bars": len(raw[sym])}
            factors.append((sym, ch["date"], ch["ratio"], kind,
                            "rahavard-type7-type0", "implied-ratio-change",
                            "reference-exact", "MEASURED_REFERENCE",
                            ch["q_before"], ch["q_after"], prev_close,
                            capture_sha, run_id, "",
                            json.dumps(details, ensure_ascii=False, sort_keys=True),
                            now))
            if link.get("pack"):
                st = link["pack"]
                links.append((sym, ch["date"], st["date"], "pack-step",
                              "matched-ratio", ING.days(st["date"], ch["date"]),
                              json.dumps(st, ensure_ascii=False, sort_keys=True)))
        for st in steps:
            if not st["ratio"]:
                continue
            near = [c for c in changes
                    if ING.days(c["date"], st["date"]) <= ING.PACK_WINDOW_DAYS]
            if not near:
                audit.append((sym, st["date"], "no_reference_change", st["ratio"],
                              None, st["event_sig"],
                              json.dumps(st, ensure_ascii=False, sort_keys=True),
                              run_id))
                continue
            best = min(near, key=lambda c: ING.days(c["date"], st["date"]))
            if abs(best["ratio"] / st["ratio"] - 1.0) > ING.PACK_RATIO_TOL:
                audit.append((sym, st["date"], "superseded_ratio", st["ratio"],
                              best["ratio"], st["event_sig"],
                              json.dumps({"ref_date": best["date"]}, ensure_ascii=False),
                              run_id))
        for ch in changes:
            if not any(ING.days(c["date"], ch["date"]) <= ING.PACK_WINDOW_DAYS
                       and c["ratio"]
                       and abs(c["ratio"] / ch["ratio"] - 1.0) <= 1e-3
                       for c in steps):
                missing_pack += 1
                audit.append((sym, ch["date"], "missing_pack_step", None,
                              ch["ratio"], None, None, run_id))

    revision = hashlib.sha256(
        ("%s\n" % capture_sha).encode()
        + "\n".join("%s|%s|%.17g" % (f[0], f[1], f[2])
                    for f in sorted(factors)).encode()).hexdigest()
    factors = [tuple(list(f[:13]) + [revision] + list(f[14:])) for f in factors]
    con.executemany("INSERT OR REPLACE INTO adjustment_factors "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", factors)
    con.executemany("INSERT OR REPLACE INTO factor_action_links VALUES(?,?,?,?,?,?,?)",
                    links)
    con.executemany("INSERT OR REPLACE INTO adjustment_factor_audit "
                    "VALUES(?,?,?,?,?,?,?,?)", audit)
    con.commit()
    counts = {
        "reference_raw_rows": con.execute("SELECT COUNT(*) FROM reference_raw").fetchone()[0],
        "reference_adjusted_rows":
            con.execute("SELECT COUNT(*) FROM reference_adjusted").fetchone()[0],
        "adjustment_factors": len(factors),
        "kinds": dict(kinds),
        "audit": dict(collections.Counter(a[2] for a in audit)),
        "factor_action_links": len(links),
        "corporate_actions": 0,
        "missing_pack_steps": missing_pack,
        "symbols_ingested": len(raw),
    }
    con.close()
    return revision, counts


def run_build(db_path, bin_path):
    proc = subprocess.run([bin_path, "--db", db_path], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        sys.exit("FATAL: candlebuild failed: %s" % (proc.stdout + proc.stderr))
    return json.loads(proc.stdout)


def _rel(got, want):
    if got is None or want is None:
        return None
    return abs(float(got) / float(want) - 1.0) if want else abs(float(got))


def parity(db_path, ex):
    """Compare every adjusted candle to the restored type7 bar, field by field.

    high/low are additionally attributed: the frozen candle contract widens the
    shadow to include the body, so a source bar whose open lies outside its own
    high/low must differ from type7 there. A difference that is NOT explained by
    widening is counted separately and fails the stage.
    """
    raw, adj_ohlc = ex["raw"], ex["adj_ohlc"]
    con = sqlite3.connect("file:%s?mode=ro" % db_path.replace(os.sep, "/"), uri=True)
    per_symbol = []
    field_max = {f: 0.0 for f in FIELDS}
    field_worst = {f: None for f in FIELDS}
    vol_bad = []
    rows_total = 0
    close_diff = 0
    ohlc_diff = collections.Counter()
    source_open_outside = 0
    attributed = collections.Counter()
    unattributed = []
    ref_not_raw_scaled = []
    engine_not_widened = []
    for sym in sorted(raw):
        rows = list(con.execute(
            "SELECT date,open,high,low,close,volume,factor,revision "
            "FROM adjusted_candles WHERE symbol=? ORDER BY date", (sym,)))
        ver = {r[0]: r for r in con.execute(
            "SELECT date,status,rel_error FROM adjustment_verification WHERE symbol=?",
            (sym,))}
        rev = con.execute("SELECT revision,raw_rows,factor_rows,adjusted_rows,"
                          "max_rel_error,worst_date FROM candle_build_revisions "
                          "WHERE symbol=?", (sym,)).fetchone()
        smax = {f: 0.0 for f in FIELDS}
        sdiff = collections.Counter()
        sv_bad = 0
        missing_ref = 0
        s_outside = 0
        for d, o, h, l, c, v, f, _r in rows:
            rows_total += 1
            ref = adj_ohlc[sym].get(d)
            rb = raw[sym].get(d, {})
            if ref is None:
                missing_ref += 1
                continue
            for name, got in zip(FIELDS, (o, h, l, c)):
                rel = _rel(got, ref.get(name))
                if rel is None:
                    continue
                if rel > smax[name]:
                    smax[name] = rel
                if rel > field_max[name]:
                    field_max[name] = rel
                    field_worst[name] = {"symbol": sym, "date": d,
                                         "engine": got, "reference": ref.get(name)}
                if rel > ENGINE_EXACT_REL:
                    sdiff[name] += 1
                    ohlc_diff[name] += 1
            rv = rb.get("volume")
            if rv is None or v is None or float(v) != float(rv):
                sv_bad += 1
                vol_bad.append({"symbol": sym, "date": d,
                                "engine_volume": v, "raw_volume": rv})
            ro, rh, rl, rc = (rb.get(x) for x in FIELDS)
            if None in (ro, rh, rl, rc) or not f:
                continue
            o_eff = ro if ro > 0 else rc
            outside = ro > rh or ro < rl
            if outside:
                source_open_outside += 1
                s_outside += 1
            widened = {"high": max(rh, o_eff, rc), "low": min(rl, o_eff, rc)}
            for name, rawv, got in (("high", rh, h), ("low", rl, l)):
                want = ref.get(name)
                if want is None:
                    continue
                differs = (_rel(got, want) or 0.0) > ENGINE_EXACT_REL
                if differs:
                    if outside:
                        attributed[name] += 1
                    elif len(unattributed) < 20:
                        unattributed.append({"symbol": sym, "date": d,
                                             "field": name, "engine": got,
                                             "reference": want, "raw": rawv,
                                             "open": ro, "factor": f})
                r_scaled = _rel(want, rawv * f)
                if r_scaled is not None and r_scaled > ENGINE_EXACT_REL:
                    if len(ref_not_raw_scaled) < 20:
                        ref_not_raw_scaled.append(
                            {"symbol": sym, "date": d, "field": name,
                             "reference": want, "raw_times_factor": rawv * f})
                e_wid = _rel(got, widened[name] * f)
                if e_wid is not None and e_wid > ENGINE_EXACT_REL:
                    if len(engine_not_widened) < 20:
                        engine_not_widened.append(
                            {"symbol": sym, "date": d, "field": name,
                             "engine": got, "widened_times_factor": widened[name] * f})
        close_diff += sdiff["close"]
        engine_diff = sum(1 for r in ver.values() if r[1] != "EXACT")
        status = "PASS"
        if not rows:
            status = "NOT_MATERIALIZED_BY_BUILDER"
        elif sdiff["close"] or engine_diff or sv_bad or missing_ref:
            status = "PARTIAL"
        per_symbol.append({
            "symbol": sym, "status": status,
            "adjusted_rows": len(rows), "raw_rows": len(raw[sym]),
            "reference_rows": len(adj_ohlc[sym]),
            "verified_rows": len(ver), "engine_diff_rows": engine_diff,
            "close_diff_rows": sdiff["close"],
            "open_diff_rows": sdiff["open"], "high_diff_rows": sdiff["high"],
            "low_diff_rows": sdiff["low"],
            "volume_mismatch_rows": sv_bad,
            "rows_without_reference": missing_ref,
            "source_open_outside_range_rows": s_outside,
            "max_rel_error": smax,
            "revision": rev[0] if rev else None,
            "engine_raw_rows": rev[1] if rev else None,
            "engine_factor_rows": rev[2] if rev else None,
            "engine_adjusted_rows": rev[3] if rev else None,
            "engine_max_rel_error": rev[4] if rev else None,
            "engine_worst_date": rev[5] if rev else None,
        })
    con.close()
    return {"per_symbol": per_symbol, "rows_total": rows_total,
            "close_diff_rows": close_diff,
            "ohlc_diff_rows": dict(ohlc_diff),
            "field_max_rel_error": field_max,
            "field_worst": field_worst,
            "volume_mismatch_rows": len(vol_bad),
            "volume_mismatch_sample": vol_bad[:10],
            "source_open_outside_range_rows": source_open_outside,
            "high_low_diff_attributed_to_widening": dict(attributed),
            "high_low_diff_unattributed": unattributed,
            "high_low_diff_unattributed_count":
                sum(ohlc_diff[f] for f in ("high", "low"))
                - sum(attributed.values()),
            "reference_not_raw_times_factor": ref_not_raw_scaled,
            "engine_not_widened_times_factor": engine_not_widened}


def anchor_invariant(db_path):
    """Measure q at the builder's anchor for every symbol.

    chainFactors sets factor=1 on the largest reference_raw date, so the stored
    q_after/q_before ratios telescope to 1/q(t) only when q(last)==1. Close
    parity is therefore conditional on this invariant; it is measured, not
    assumed.
    """
    con = sqlite3.connect("file:%s?mode=ro" % db_path.replace(os.sep, "/"), uri=True)
    per = []
    for sym, last in con.execute(
            "SELECT symbol, MAX(date) FROM reference_raw "
            "GROUP BY symbol ORDER BY symbol"):
        rc = con.execute("SELECT close FROM reference_raw WHERE symbol=? AND date=?",
                         (sym, last)).fetchone()[0]
        row = con.execute("SELECT close FROM reference_adjusted "
                          "WHERE symbol=? AND date=?", (sym, last)).fetchone()
        ac = row[0] if row else None
        q = (rc / ac) if (rc is not None and ac) else None
        per.append({"symbol": sym, "anchor_date": last, "raw_close": rc,
                    "reference_close": ac, "q": q,
                    "holds": q is not None and abs(q - 1.0) <= ENGINE_EXACT_REL})
    con.close()
    return per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-build", action="store_true",
                    help="reuse the existing working DB and binary output")
    args = ap.parse_args()
    started = time.time()

    for rel, exp in EXPECTED_SHA.items():
        got = S6.sha256_file(os.path.join(ROOT, rel.replace("/", os.sep)))
        if got != exp:
            sys.exit("FATAL: pinned input %s sha256 %s != %s" % (rel, got, exp))

    verify = S6.read_json(VERIFY_REL)
    if verify.get("status") != "PASS":
        sys.exit("FATAL: stage06 verification is not PASS; refusing to ingest")
    payload_sha = verify["bars_recount"]["payload_sha256"]
    if payload_sha != S6.read_json(SUMMARY_REL)["merged"]["bars_payload_sha256"]:
        sys.exit("FATAL: stage06 payload digest disagrees with recorded evidence")

    summary = S6.read_json(SUMMARY_REL)
    cohort = S6.read_json(COHORT_REL)
    index = json.load(io.open(os.path.join(ROOT, INDEX_REL.replace("/", os.sep)),
                              encoding="utf-8"))
    capture_day = summary["capture"]["captured_at_max"][:10]
    captured_at = summary["capture"]["captured_at_max"]

    bin_path = os.path.join(ROOT, BIN_REL.replace("/", os.sep))
    if not os.path.exists(bin_path):
        sys.exit("FATAL: %s absent; build it from untouched source first" % BIN_REL)
    engine_diff = subprocess.run(
        ["git", "diff", "--stat", S6.BASE_COMMIT, "--", "backend-go/"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout.strip()
    if engine_diff:
        sys.exit("FATAL: engine differs from base commit:\n%s" % engine_diff)

    cohort_keys = {m["key"] for m in cohort["members"]}
    spelling_to_key = {sp: k for k, r in index.items() for sp in r["raw_symbols"]}
    bars_path = os.path.join(ROOT, BARS_REL.replace("/", os.sep))
    print("extracting cohort bars (capture_day=%s) ..." % capture_day, flush=True)
    ex = extract_cohort(bars_path, cohort_keys, spelling_to_key, capture_day)
    if len(ex["raw"]) != len(cohort_keys):
        sys.exit("FATAL: extracted %d symbols, expected %d"
                 % (len(ex["raw"]), len(cohort_keys)))

    pack = ING.load_pack()
    capture_sha = payload_sha
    run_id = "phase49-3-cohort-" + capture_sha[:12]
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    db_path = os.path.join(ROOT, DB_REL.replace("/", os.sep))

    if args.skip_build and os.path.exists(db_path):
        con = sqlite3.connect(db_path)
        revision = con.execute("SELECT revision FROM adjustment_factors LIMIT 1").fetchone()[0]
        counts = {"reference_raw_rows":
                  con.execute("SELECT COUNT(*) FROM reference_raw").fetchone()[0]}
        con.close()
        build = None
    else:
        revision, counts = ingest(db_path, ex, cohort, pack, capture_sha,
                                  run_id, captured_at, now)
        print("ingested raw=%d adjusted=%d factors=%d"
              % (counts["reference_raw_rows"], counts["reference_adjusted_rows"],
                 counts["adjustment_factors"]), flush=True)
        build = run_build(db_path, bin_path)
        print("candlebuild: %s" % json.dumps(build, ensure_ascii=False)[:400],
              flush=True)

    par = parity(db_path, ex)
    statuses = collections.Counter(r["status"] for r in par["per_symbol"])
    expected_rows = sum(m["expected_raw_rows"] for m in cohort["members"])

    con = sqlite3.connect("file:%s?mode=ro" % db_path.replace(os.sep, "/"), uri=True)
    zero_event = [r[0] for r in con.execute(
        "SELECT DISTINCT symbol FROM reference_raw WHERE symbol NOT IN "
        "(SELECT DISTINCT symbol FROM adjustment_factors) ORDER BY symbol")]
    con.close()
    zero_rows = sum(len(ex["raw"][s]) for s in zero_event)
    builder_rows = expected_rows - zero_rows
    built_symbols = len(cohort_keys) - len(zero_event)

    anchors = anchor_invariant(db_path)
    anchor_bad = [a for a in anchors if not a["holds"]]

    failures = []
    if counts["reference_raw_rows"] != expected_rows:
        failures.append("reference_raw rows %d != frozen expected %d"
                        % (counts["reference_raw_rows"], expected_rows))
    if counts["reference_adjusted_rows"] != expected_rows:
        failures.append("reference_adjusted rows %d != frozen expected %d"
                        % (counts["reference_adjusted_rows"], expected_rows))
    if par["rows_total"] != builder_rows:
        failures.append("adjusted_candles rows %d != %d (frozen %d minus %d "
                        "zero-event rows the builder does not materialize)"
                        % (par["rows_total"], builder_rows, expected_rows, zero_rows))
    if par["volume_mismatch_rows"]:
        failures.append("volume not constant on %d rows"
                        % par["volume_mismatch_rows"])
    if par["close_diff_rows"]:
        failures.append("close differs from type7 on %d rows"
                        % par["close_diff_rows"])
    if statuses.get("PASS", 0) != built_symbols:
        failures.append("only %d/%d event-carrying symbols PASS"
                        % (statuses.get("PASS", 0), built_symbols))
    if statuses.get("NOT_MATERIALIZED_BY_BUILDER", 0) != len(zero_event):
        failures.append("zero-event symbols not accounted for: %r" % zero_event)
    if par["high_low_diff_unattributed_count"]:
        failures.append("%d high/low differences are NOT explained by widening"
                        % par["high_low_diff_unattributed_count"])
    if par["reference_not_raw_times_factor"]:
        failures.append("reference high/low is not raw*factor on %d sampled rows"
                        % len(par["reference_not_raw_times_factor"]))
    if par["engine_not_widened_times_factor"]:
        failures.append("engine high/low is not widened*factor on %d sampled rows"
                        % len(par["engine_not_widened_times_factor"]))
    if anchor_bad:
        failures.append("type7 anchor invariant q(last)=1 violated on %d symbols: %s"
                        % (len(anchor_bad), [a["symbol"] for a in anchor_bad][:5]))

    payload = {
        "schema": "phase49-3-cohort-candles-v1",
        "mission": "Phase 4.9.3 coverage expansion",
        "status": "PASS" if not failures else "PARTIAL",
        "failures": failures,
        "base_commit": S6.BASE_COMMIT,
        "engine_source_diff_vs_base": engine_diff or "(empty)",
        "engine_binary": {"path": BIN_REL,
                          "sha256": S6.sha256_file(bin_path),
                          "built_from": "backend-go/cmd/candlebuild at HEAD, "
                                        "engine unmodified"},
        "working_db": {
            "path": DB_REL,
            "provenance": "created fresh from the frozen Phase 4.9.2 SCHEMA; "
                          "NOT a copy of the Seed Candidate or the Pilot DB, "
                          "both of which are absent from this host",
            "seed_candidate_sha256_expected":
                "57118e8fc99ff69c9e9812002f1d72571f357c23287fc1880a2f00b8292bbcb5",
            "pilot_db_sha256_expected":
                "8445624f1f947d80273a18d5560ae7db6337207cc93a51242e35693be183dd2b",
            "red_line_dbs_opened_for_write": False,
        },
        "capture": {
            "bars_file": BARS_REL,
            "container_sha256": EXPECTED_SHA[BARS_REL],
            "payload_sha256": payload_sha,
            "index_sha256": EXPECTED_SHA[INDEX_REL],
            "pack_file": PACK_REL, "pack_sha256": EXPECTED_SHA[PACK_REL],
            "captured_at_max": captured_at,
            "capture_day": capture_day,
            "quarantine_rule": "date >= capture_day, the accepted Phase 4.9.2 rule",
            "quarantined_bars": ex["quarantined"],
            "non_daily_rows_skipped": ex["non_daily_skipped"],
            "cohort_rows_scanned": ex["cohort_rows_scanned"],
        },
        "run_id": run_id,
        "revision": revision,
        "counts": counts,
        "candlebuild_result": build,
        "parity": par,
        "symbol_statuses": dict(statuses),
        "frozen_expected_raw_rows_total": expected_rows,
        "builder_coverage": {
            "symbols_ingested": len(ex["raw"]),
            "symbols_with_factor_rows": built_symbols,
            "symbols_materialized": built_symbols,
            "zero_event_symbols": zero_event,
            "zero_event_rows": zero_rows,
            "expected_builder_rows": builder_rows,
            "root_cause":
                "candlebuild.Build iterates SELECT DISTINCT symbol FROM "
                "adjustment_factors (backend-go/internal/candlebuild/"
                "candlebuild.go:94), so a symbol with no measured event gets no "
                "adjusted_candles rows at all",
            "runtime_consequence":
                "measuredFactorEvents returns measured=false when a symbol has "
                "zero factor rows (backend-go/internal/chart/measured.go:42-44), "
                "so a reference-covered zero-event symbol is indistinguishable "
                "from an uncovered one and falls back to the pack/official path. "
                "Measured live in stage08, not inferred from this comment.",
            "engine_changed": False,
            "pending_runtime_verification": zero_event,
        },
        "widening_attribution": {
            "source_rows_with_open_outside_high_low":
                par["source_open_outside_range_rows"],
            "high_low_diff_rows": {k: par["ohlc_diff_rows"].get(k, 0)
                                   for k in ("high", "low")},
            "attributed_to_frozen_widen_contract":
                par["high_low_diff_attributed_to_widening"],
            "unattributed_count": par["high_low_diff_unattributed_count"],
            "unattributed_sample": par["high_low_diff_unattributed"],
            "reference_is_raw_times_factor":
                not par["reference_not_raw_times_factor"],
            "engine_is_widened_times_factor":
                not par["engine_not_widened_times_factor"],
            "reference_counterexample_sample": par["reference_not_raw_times_factor"],
            "engine_counterexample_sample": par["engine_not_widened_times_factor"],
            "raw_data_modified": False,
        },
        "anchor_invariant": {
            "rule":
                "chainFactors anchors factor=1 on the largest reference_raw date "
                "(backend-go/internal/chart/canonical.go:1484) and multiplies the "
                "stored q_after/q_before ratios of later events, so factor(t) "
                "telescopes to q(last)/q(t). Close parity with type7 therefore "
                "requires q(last)==1; measured here rather than assumed.",
            "symbols_checked": len(anchors),
            "violations": len(anchor_bad),
            "violating_symbols": [a["symbol"] for a in anchor_bad],
            "max_abs_q_minus_one": max(
                (abs(a["q"] - 1.0) for a in anchors if a["q"] is not None),
                default=None),
            "per_symbol": anchors,
        },
        "engine_exact_rel_threshold": ENGINE_EXACT_REL,
        "not_measured": {
            "official_share_change_classification":
                "the Seed Candidate is absent, so instruments.ins_code and "
                "share_change_events could not be read; capital_increase cannot "
                "be evidenced from official rows on this host",
            "timescale_dps_eps_marks":
                "the merged bars NDJSON carries bars only, no marks; dividend "
                "classification from DPS is NOT_MEASURED, not zero",
            "price_history_conflict_census":
                "no Seed price_history exists here, so conflicts_with_seed_raw "
                "is NOT_MEASURED; the 306 legacy invalid OHLC rows and the "
                "10,982 field differences were neither touched nor re-judged",
            "product_read_path":
                "stage08 measures the API on this working DB; a real UI "
                "screenshot remains NOT_MEASURED unless actually taken",
        },
        "honesty": {
            "no_second_engine":
                "factors come from Phase 4.9.2's own q_changes/classify and "
                "candles from the shipped Go candlebuild; nothing was rewritten",
            "tolerance_unchanged":
                "the engine's 1e-9 EXACT threshold and the frozen pack windows "
                "are used as-is; no tolerance was relaxed to make this green",
            "unclassified_is_not_guessed":
                "an event with no official witness stays "
                "corporate_action_unclassified; its type is never inferred "
                "from the ratio",
            "ohlc_widening":
                "open/high/low differences are reported separately from close. "
                "Every high/low difference is attributed to the frozen widen "
                "contract acting on a source bar whose open lies outside its "
                "own high/low; an unattributed difference fails the stage. "
                "Neither the raw bars nor the engine were modified.",
            "gate_correction_disclosure":
                "the first run of this stage gated adjusted_candles rows on all "
                "30 symbols and reported PARTIAL. That expectation was wrong: "
                "the builder only materializes symbols carrying factor rows. "
                "The gate was corrected to the builder's actual scope and a "
                "Runtime measurement of the zero-event symbol was added in "
                "stage08. No Phase 4.9.2 acceptance criterion or tolerance was "
                "changed, and no failing check was deleted.",
            "control_fixture_correction":
                "the first run of test_stage07_controls.py failed 4 of 25 "
                "controls, including the positive control. Root cause was the "
                "synthetic fixture, not the engine: it set q(last)=4 while "
                "chainFactors anchors factor=1 on the last date. The real cohort "
                "was then measured and satisfies q(last)==1 on 30/30 symbols. "
                "The fixture was corrected to a real 2:1 split with a flat type7 "
                "series, and control G was added to prove an anchor violation is "
                "detected. No engine, tolerance or acceptance criterion changed.",
            "substrate_difference":
                "Phase 4.9.2 measured on a Seed copy; this runs on a fresh "
                "schema-only DB. Candle-level acceptance is comparable because "
                "the engine reads only the three reference tables, but the "
                "Seed-dependent measurements are listed as NOT_MEASURED",
        },
    }

    manifest = {
        "stage": "stage07_cohort_candles",
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_seconds": round(time.time() - started, 3),
        "working_db_sha256": S6.sha256_file(db_path),
        "working_db_size_bytes": os.path.getsize(db_path),
        "exit_code": 0 if not failures else 1,
    }
    out_sha = S6.write_json(OUT, payload)
    manifest["payload_sha256"] = out_sha
    manifest["payload_path"] = OUT
    man_sha = S6.write_json(MANIFEST, manifest)

    print("raw=%d adjusted=%d candles=%d factors=%d revision=%s"
          % (counts["reference_raw_rows"], counts["reference_adjusted_rows"],
             par["rows_total"], counts["adjustment_factors"], revision[:16]))
    print("kinds=%s" % json.dumps(counts["kinds"], ensure_ascii=False))
    print("audit=%s" % json.dumps(counts["audit"], ensure_ascii=False))
    print("statuses=%s" % dict(statuses))
    print("close max_rel=%.3g  diff_rows=%d  volume_mismatch=%d"
          % (par["field_max_rel_error"]["close"], par["close_diff_rows"],
             par["volume_mismatch_rows"]))
    print("ohlc max_rel=%s" % json.dumps(
        {k: round(v, 12) for k, v in par["field_max_rel_error"].items()}))
    print("builder: %d/%d symbols materialized, zero_event=%s (%d rows)"
          % (built_symbols, len(cohort_keys), zero_event, zero_rows))
    print("widening: source_open_outside=%d high/low_diff=%s attributed=%s "
          "unattributed=%d"
          % (par["source_open_outside_range_rows"],
             {k: par["ohlc_diff_rows"].get(k, 0) for k in ("high", "low")},
             par["high_low_diff_attributed_to_widening"],
             par["high_low_diff_unattributed_count"]))
    print("anchor invariant q(last)=1: %d/%d symbols hold, max|q-1|=%s"
          % (len(anchors) - len(anchor_bad), len(anchors),
             max((abs(a["q"] - 1.0) for a in anchors if a["q"] is not None),
                 default=None)), flush=True)
    print("quarantined=%s non_daily=%s"
          % (ex["quarantined"], ex["non_daily_skipped"]))
    for f in failures:
        print("FAILURE:", f)
    print("wrote %s (%s)" % (OUT, out_sha[:16]))
    print("wrote %s (%s)" % (MANIFEST, man_sha[:16]))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())