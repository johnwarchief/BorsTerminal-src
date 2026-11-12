#!/usr/bin/env python3
"""Phase 4.9.5 stage02: engine + API runtime parity for the 13 new symbols.

Reuses phase49-4 stage11 functions and the restored BEFORE/AFTER binaries.
The working DB is the independent 43-symbol market43.db; only the 13 new
symbols are measured, with the frozen 30 as controls.
"""
from __future__ import annotations

import argparse
import collections
import io
import json
import os
import shutil
import sqlite3
import subprocess
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
S11 = _load("s11", "_audit/phase49-4/stage11_runtime_parity.py")

BARS_REL = "_audit/phase49-full-verification/captures/bars-all.ndjson.gz"
INDEX_REL = "_audit/phase49-full-verification/captures/reference-index-all.json"
SUMMARY_REL = "_audit/phase49-full-verification/evidence/capture-summary.json"
COHORT43_REL = "_audit/phase49-5/cohort/COHORT43.json"
INGEST43_REL = "_audit/phase49-5/evidence/INGEST43.json"
DB_REL = "_audit/phase49-5/db/market43.db"
BASELINE_DB_REL = "_audit/phase49-4/db/engine-after/market.db"
CACHE_REL = "_audit/phase49-5/db/cohort13-bars.json"
RUN_REL = "_audit/phase49-5/db/runtime"
LOG_REL = "_audit/phase49-5/logs"
PAYLOAD_REL = "_audit/phase49-5/db/api-payloads-13.json"
OUT_REL = "_audit/phase49-5/evidence/RUNTIME-PARITY-13.json"
MANIFEST_REL = "_audit/phase49-5/manifests/stage02-runtime13.json"

S7_OUT = "_audit/phase49-3/evidence/COHORT-CANDLES.json"
S8_OUT = "_audit/phase49-3/evidence/RUNTIME-READPATH.json"
BEFORE_BUILD_REL = "_audit/phase49-3/bin/candlebuild.exe"
BEFORE_BORSD_REL = "_audit/phase49-3/bin/borsd.exe"
AFTER_BUILD_REL = "_audit/phase49-4/bin/candlebuild.exe"
AFTER_BORSD_REL = "_audit/phase49-4/bin/borsd.exe"

BASE_COMMIT = "18563a6659d5d20b3c74105826ca84b4704340b2"
PINS = {
    COHORT43_REL: "2d1ccbbdcefce12015f3bd2fc49d8660aa78959c55f32f3079ec47fdf0776365",
    SUMMARY_REL: "6cbeb62811f42d143a9d6b5c10324e2eae57b6914e8f875a3ee0e50d6154da8b",
    BEFORE_BUILD_REL: "ba34c90be644060d1ff45b7477f2eafb61a39be78169282a72554501babd3673",
    BEFORE_BORSD_REL: "a797c88343f49a4d20240b452cdacfcf193cc332f7738ecfdef41983ba319cd7",
    AFTER_BUILD_REL: "4d28cece967b735750fb4668fee32a882253a9425d20471babfd3e98addd56ef",
    AFTER_BORSD_REL: "27ea06c088c58d6fead302ac4951263aee455d997310e4e57dfbedb619a95de2",
    BASELINE_DB_REL: "b5e895c979a9bd18ec0b20292ae027a1194969b9dea1f49388d566e40be8573a",
}


def sha(rel):
    return S6.sha256_file(os.path.join(ROOT, rel.replace("/", os.sep)))


def db_symbols(path):
    con = sqlite3.connect("file:%s?mode=ro" % path.replace(os.sep, "/"), uri=True)
    try:
        return {r[0] for r in con.execute("SELECT DISTINCT symbol FROM reference_raw")}
    finally:
        con.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-engine", action="store_true")
    ap.add_argument("--skip-api", action="store_true")
    ap.add_argument("--port-before", type=int, default=18106)
    ap.add_argument("--port-after", type=int, default=18107)
    args = ap.parse_args()
    started = time.time()

    for rel, exp in PINS.items():
        if sha(rel) != exp:
            sys.exit("FATAL pinned input %s sha256 mismatch" % rel)
    ingest = S6.read_json(INGEST43_REL)
    if ingest.get("status") != "PASS":
        sys.exit("FATAL stage01 ingest is not PASS; refusing runtime measurement")
    db_path = os.path.join(ROOT, DB_REL.replace("/", os.sep))
    if S6.sha256_file(db_path) != ingest["db"]["sha256"]:
        sys.exit("FATAL market43.db sha256 does not match stage01 evidence")

    s7 = S6.read_json(S7_OUT)
    s8 = S6.read_json(S8_OUT)
    for tag, rel, rec in (("borsd", BEFORE_BORSD_REL, s8["engine_binary"]),
                          ("candlebuild", BEFORE_BUILD_REL, s7["engine_binary"])):
        got = sha(rel)
        if got != rec["sha256"]:
            sys.exit("FATAL BEFORE %s sha256 %s != recorded %s" % (tag, got, rec["sha256"]))
    before = {"candlebuild": {"path": BEFORE_BUILD_REL, "sha256": sha(BEFORE_BUILD_REL)},
              "borsd": {"path": BEFORE_BORSD_REL, "sha256": sha(BEFORE_BORSD_REL)}}
    after = {"candlebuild": {"path": AFTER_BUILD_REL, "sha256": sha(AFTER_BUILD_REL)},
             "borsd": {"path": AFTER_BORSD_REL, "sha256": sha(AFTER_BORSD_REL)}}

    cohort = S6.read_json(COHORT43_REL)
    new_members = [m for m in cohort["members"]
                   if m.get("verification_status") == "CAPTURE_RESTORED_READY_INGEST"]
    if len(new_members) != 13:
        sys.exit("FATAL cohort43 new members %d != 13" % len(new_members))
    baseline_path = os.path.join(ROOT, BASELINE_DB_REL.replace("/", os.sep))
    symbols = sorted(db_symbols(db_path) - db_symbols(baseline_path))
    if len(symbols) != 13:
        sys.exit("FATAL market43 difference from the frozen-30 DB is %d symbols, expected 13: %r"
                 % (len(symbols), symbols))

    summary = S6.read_json(SUMMARY_REL)
    capture_day = summary["capture"]["captured_at_max"][:10]
    cache = os.path.join(ROOT, CACHE_REL.replace("/", os.sep))
    if os.path.exists(cache):
        ex = json.load(io.open(cache, encoding="utf-8"))
    else:
        index = json.load(io.open(os.path.join(
            ROOT, INDEX_REL.replace("/", os.sep)), encoding="utf-8"))
        keys = {m["key"] for m in new_members}
        spelling = {sp: k for k, r in index.items() for sp in r["raw_symbols"]}
        print("extracting 13-symbol bars (capture_day=%s) ..." % capture_day, flush=True)
        ex = S7.extract_cohort(os.path.join(
            ROOT, BARS_REL.replace("/", os.sep)), keys, spelling, capture_day)
        if len(ex["raw"]) != 13:
            sys.exit("FATAL extracted %d symbols, expected 13" % len(ex["raw"]))
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        with io.open(cache, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(ex, fh, ensure_ascii=False)
    ref0, ref7, skipped = S11.literal_reference(ex)
    missing = [s for s in symbols if s not in ref0]
    extra = [s for s in ref0 if s not in symbols]
    if missing or extra:
        sys.exit("FATAL runtime symbols vs reference keys differ: missing=%r extra=%r"
                 % (missing, extra))

    con = sqlite3.connect("file:%s?mode=ro" % db_path.replace(os.sep, "/"), uri=True)
    zero_event = [s for s in symbols if not con.execute(
        "SELECT 1 FROM adjustment_factors WHERE symbol=? LIMIT 1", (s,)).fetchone()]
    con.close()

    run = os.path.join(ROOT, RUN_REL.replace("/", os.sep))
    log_dir = os.path.join(ROOT, LOG_REL.replace("/", os.sep))
    os.makedirs(run, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)
    layers, failures = {}, []
    db_sha = S6.sha256_file(db_path)

    if not args.skip_engine:
        layers["engine"] = {}
        for side, binrec in (("before", before["candlebuild"]),
                             ("after", after["candlebuild"])):
            copy_dir = os.path.join(run, "engine-" + side)
            if os.path.isdir(copy_dir):
                shutil.rmtree(copy_dir)
            os.makedirs(copy_dir, exist_ok=True)
            dst = os.path.join(copy_dir, "market.db")
            shutil.copy2(db_path, dst)
            if S6.sha256_file(dst) != db_sha:
                sys.exit("FATAL engine %s copy does not match market43.db" % side)
            print("engine %s ..." % side, flush=True)
            build, per = S11.engine_side(
                dst, os.path.join(ROOT, binrec["path"].replace("/", os.sep)),
                ref0, ref7)
            layers["engine"][side] = {"build": build, "summary": S11.roll_up(per),
                                      "per_symbol": per,
                                      "db_copy_sha256": S6.sha256_file(dst)}
            print("  %s" % json.dumps(layers["engine"][side]["summary"],
                                       ensure_ascii=False)[:400], flush=True)

    if not args.skip_api:
        layers["api"] = {}
        dumped = {"capture_day": capture_day, "symbols": symbols, "payloads": {}}
        for side, binrec, port in (("before", before["borsd"], args.port_before),
                                   ("after", after["borsd"], args.port_after)):
            copy_dir = os.path.join(run, "api-" + side)
            if os.path.isdir(copy_dir):
                shutil.rmtree(copy_dir)
            os.makedirs(copy_dir, exist_ok=True)
            dst = os.path.join(copy_dir, "market.db")
            shutil.copy2(db_path, dst)
            if S6.sha256_file(dst) != db_sha:
                sys.exit("FATAL api %s copy does not match market43.db" % side)
            print("api %s (port %d) ..." % (side, port), flush=True)
            payloads, per, procinfo = S11.api_side(
                copy_dir, os.path.join(ROOT, binrec["path"].replace("/", os.sep)),
                port, symbols, ref0, ref7,
                os.path.join(log_dir, "stage02-%s-server.log" % side))
            layers["api"][side] = {
                "summary": S11.roll_up(per), "per_symbol": per, "server": procinfo,
                "measured_path_symbols": [r["symbol"] for r in per if r.get("measured_path")],
                "not_measured_path_symbols": [r["symbol"] for r in per
                                              if not r.get("measured_path")],
                "db_copy_sha256": S6.sha256_file(dst)}
            print("  %s" % json.dumps(layers["api"][side]["summary"],
                                       ensure_ascii=False)[:400], flush=True)
            dumped["payloads"][side] = payloads
        with io.open(os.path.join(ROOT, PAYLOAD_REL.replace("/", os.sep)),
                     "w", encoding="utf-8", newline="\n") as fh:
            json.dump(dumped, fh, ensure_ascii=False)

    for name, layer in layers.items():
        a = layer["after"]["summary"]
        if a["adjusted_diff_total"] or a["volume_mismatch_rows"]:
            failures.append("%s AFTER: %d adjusted divergences, %d volume divergences"
                            % (name, a["adjusted_diff_total"], a["volume_mismatch_rows"]))
        if a["raw_diff_total"]:
            failures.append("%s AFTER: %d raw divergences"
                            % (name, a["raw_diff_total"]))
        if a["rows_missing"] or a["rows_extra"]:
            failures.append("%s AFTER: %d missing / %d extra rows"
                            % (name, a["rows_missing"], a["rows_extra"]))
        if a["rows_without_factor"]:
            failures.append("%s AFTER: %d served rows carry no factor"
                            % (name, a["rows_without_factor"]))
        if a["symbols_pass"] != a["symbols"]:
            failures.append("%s AFTER: only %d/%d symbols PASS (%s)"
                            % (name, a["symbols_pass"], a["symbols"],
                               a["symbols_partial"][:5]))
    if "api" in layers:
        nm = layers["api"]["after"]["not_measured_path_symbols"]
        if nm:
            failures.append("api AFTER: %d symbols off the measured path: %s"
                            % (len(nm), nm))
        for s in zero_event:
            r = next((x for x in layers["api"]["after"]["per_symbol"]
                      if x["symbol"] == s), None)
            if r is None or not r.get("measured_path"):
                failures.append("zero-event symbol %s is not on the measured path" % s)

    delta = {}
    for name, layer in layers.items():
        b, a = layer["before"]["summary"], layer["after"]["summary"]
        delta[name] = {
            "adjusted_diff_rows_before": b["adjusted_diff_total"],
            "adjusted_diff_rows_after": a["adjusted_diff_total"],
            "raw_diff_rows_before": b["raw_diff_total"],
            "raw_diff_rows_after": a["raw_diff_total"],
            "volume_mismatch_before": b["volume_mismatch_rows"],
            "volume_mismatch_after": a["volume_mismatch_rows"],
            "symbols_pass_before": b["symbols_pass"],
            "symbols_pass_after": a["symbols_pass"],
            "rows_served_before": b["rows_served"],
            "rows_served_after": a["rows_served"],
            "adjusted_max_rel_before": b["adjusted_max_rel"],
            "adjusted_max_rel_after": a["adjusted_max_rel"],
        }

    payload = {
        "schema": "phase49-5-runtime-parity-13-v1",
        "mission": "phase49-5-43symbol-independent-db",
        "status": "PASS" if not failures else "PARTIAL",
        "failures": failures,
        "base_commit": BASE_COMMIT,
        "head_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                      capture_output=True, text=True,
                                      encoding="utf-8").stdout.strip(),
        "reference_law": {
            "statement": "type7 = type0 x factor for open/high/low/close; "
                         "type7.volume == type0.volume",
            "widening_applied_to_reference": False,
            "tolerance": S11.ENGINE_EXACT_REL,
            "tolerance_unchanged": True,
        },
        "binaries": {"before": before, "after": after},
        "substrate": {
            "working_db": DB_REL,
            "working_db_sha256": db_sha,
            "original_opened_read_only": True,
            "copies_under": RUN_REL,
            "capture_day_quarantine": capture_day,
            "bars_capture_sha256": "272336c036d647ed7b2090853c84c3a2d3da6126a0bfae60e987198169b3b14a",
            "reference_rows_type0": sum(len(v) for v in ref0.values()),
            "reference_rows_type7": sum(len(v) for v in ref7.values()),
            "reference_rows_skipped_by_engine_rules":
                {s: d for s, d in skipped.items() if d},
        },
        "cohort": {"symbols": symbols, "count": 13,
                   "new_member_spellings": [m["symbol"] for m in new_members],
                   "zero_event_symbols": zero_event},
        "before_after_delta": delta,
        "layers": layers,
        "payload_file": PAYLOAD_REL,
        "not_measured": {
            "ui_screenshot": "no browser was driven against this DB",
            "browser_transform": "stage12 frontend transform not run for the 13",
            "live_feed": "--no-loops; liveInjected is recorded as returned",
            "instruments_table_absent": "schema-only working DB",
        },
        "elapsed_seconds": round(time.time() - started, 1),
    }

    out = os.path.join(ROOT, OUT_REL.replace("/", os.sep))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    outputs = {OUT_REL: {"sha256": S6.sha256_file(out),
                         "bytes": os.path.getsize(out)}}
    payload_path = os.path.join(ROOT, PAYLOAD_REL.replace("/", os.sep))
    if os.path.exists(payload_path):
        outputs[PAYLOAD_REL] = {"sha256": S6.sha256_file(payload_path)}
    manifest = {
        "schema": "phase49-5-stage-manifest-v1",
        "stage": "stage02_runtime13",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_seconds": payload["elapsed_seconds"],
        "inputs": {rel: {"sha256": sha(rel)} for rel in PINS},
        "outputs": outputs,
        "db_written": False, "status": payload["status"],
    }
    man = os.path.join(ROOT, MANIFEST_REL.replace("/", os.sep))
    with open(man, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    print(json.dumps({"status": payload["status"], "failures": failures,
                      "symbols": symbols, "zero_event": zero_event,
                      "delta": delta}, ensure_ascii=False, indent=1))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
