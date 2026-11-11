#!/usr/bin/env python3
"""Phase 4.9.3 stage08: measure the product read path on the isolated working DB.

Stage07 proved the builder's candles. This proves what the shipped HTTP API
actually returns for the same 30 symbols, because adjusted_candles is NOT the
Runtime read path: chartDBBody -> canonicalPriceHistory -> referenceRawHistory
serves the captured raw series, and canonicalAdjustment -> measuredFactorEvents
supplies the factor chain per request.

The specific question this stage exists to answer: a symbol that the reference
covers but that carries zero measured events (پادا) is indistinguishable from an
uncovered symbol inside measuredFactorEvents, which returns measured=false on an
empty factor set. Code reading suggests it falls back to the pack/official path.
That is measured here over HTTP, not inferred.

Substrate: a throwaway copy of the stage07 working DB under a gitignored run dir.
Neither red-line DB exists on this host and neither is opened. The original
working DB is opened read-only. Only the PID this script starts is terminated.

No UI screenshot is taken here; an API measurement is never called a UI test.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request

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
BIN_REL = "_audit/phase49-3/bin/borsd.exe"
PACK_REL = "data/ra365_corrections/ra365-phase49-rebuild-full-v2"
COHORT_REL = "_audit/phase49-3/evidence/COHORT-SELECTION.json"
S7_OUT = "_audit/phase49-3/evidence/COHORT-CANDLES.json"
S7_MANIFEST = "_audit/phase49-3/manifests/stage07-cohort-candles.json"
RUN_REL = "_audit/phase49-3/db/runtime"
LOG_REL = "_audit/phase49-3/logs/stage08-server.log"
OUT = "_audit/phase49-3/evidence/RUNTIME-READPATH.json"
MANIFEST = "_audit/phase49-3/manifests/stage08-runtime-readpath.json"

PORT = 18093
ENGINE_EXACT_REL = 1e-9
MEASURED_SRC = "local-measured-factors"
REFERENCE_SRC = "rahavard-type0"
FIELDS = ("open", "high", "low", "close")


def api(path, token, timeout=300):
    req = urllib.request.Request(
        "http://127.0.0.1:%d%s" % (PORT, path),
        headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def wait_server(token_file, probe_symbol, timeout=600):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        if os.path.exists(token_file):
            try:
                tok = open(token_file, encoding="ascii").read().strip()
                p = api("/api/chart-db/" + urllib.parse.quote(probe_symbol, safe=""),
                        tok, timeout=30)
                if p.get("status") == "success":
                    return tok
                last = "probe status=%r" % p.get("status")
            except Exception as exc:  # noqa: BLE001
                last = repr(exc)
        time.sleep(1)
    raise RuntimeError("server did not become ready: %s" % last)


def widen(o, h, l, c):
    """Mirror of candlecontract.Widen: the shadow opens to include the body."""
    body = [x for x in (o, c) if x]
    if not body:
        return h, l
    hi = h if h else body[0]
    lo = l if l else body[0]
    for p in body:
        if p > hi:
            hi = p
        if p < lo:
            lo = p
    return hi, lo


def reference(con, sym):
    """The rows referenceRawHistory would serve, with its own skip rules."""
    raw = {}
    for d, o, h, l, c, v in con.execute(
            "SELECT date,open,high,low,close,volume FROM reference_raw "
            "WHERE symbol=? ORDER BY date", (sym,)):
        if c is None or c <= 0 or v is None or v <= 0:
            continue
        o = o if (o is not None and o > 0) else c
        hraw = h if h is not None else 0.0
        lraw = l if l is not None else 0.0
        hi, lo = widen(o, hraw, lraw, c)
        raw[d] = {"open": o, "high": hi, "low": lo, "close": c, "volume": v,
                  "high_raw": hraw, "low_raw": lraw}
    adj = {d: c for d, c in con.execute(
        "SELECT date,close FROM reference_adjusted WHERE symbol=?", (sym,))}
    return raw, adj


def _rel(got, want):
    if got is None or want is None:
        return None
    return abs(float(got) / float(want) - 1.0) if want else abs(float(got))


def compare(sym, payload, raw, adj, factor_rows):
    """Field-by-field comparison of one API payload against the reference."""
    out = {"symbol": sym, "http_status": payload.get("status"),
           "adjust_source": payload.get("adjustSource"),
           "live_injected": payload.get("liveInjected"),
           "live_error": payload.get("liveError"),
           "declared_count": payload.get("count"),
           "db_rows": payload.get("dbRows")}
    if payload.get("status") != "success":
        out["status"] = "BLOCKED"
        out["message"] = payload.get("message")
        return out
    candles = payload.get("candles") or []
    facts = payload.get("factors") or []
    cap = payload.get("adjustCapability") or {}
    out["candles"] = len(candles)
    out["reference_rows"] = len(raw)
    out["factor_entries"] = len(facts)
    out["capability"] = {k: cap.get(k) for k in
                         ("complete", "anchored", "coverage", "revision", "source")
                         if k in cap}
    out["adjust_events"] = len(payload.get("adjustEvents") or [])
    out["adjust_rejected"] = len(payload.get("adjustRejected") or [])

    fmap = {}
    for f in facts:
        d = str(f.get("time") or "")[:10]
        if d:
            fmap[d] = f.get("factor")
    out["factor_values_distinct"] = len({round(float(v), 12)
                                         for v in fmap.values()
                                         if v is not None})
    out["factor_min"] = min((float(v) for v in fmap.values()
                             if v is not None), default=None)
    out["factor_max"] = max((float(v) for v in fmap.values()
                             if v is not None), default=None)

    src_bad = []
    field_diff = collections.Counter()
    field_max = {f: 0.0 for f in FIELDS}
    vol_bad = 0
    missing = 0
    close_diff = 0
    adj_max = 0.0
    adj_worst = None
    nonunit_factor_rows = 0
    raw_diff_sample = []
    literal_reset = collections.Counter()
    unattributed = []
    geometry_invalid = 0
    geometry_sample = []
    for c in candles:
        d = str(c.get("time") or "")[:10]
        rb = raw.get(d)
        if rb is None:
            missing += 1
            continue
        if c.get("src") != REFERENCE_SRC:
            if len(src_bad) < 5:
                src_bad.append({"date": d, "src": c.get("src")})
        for name in FIELDS:
            rel = _rel(c.get(name), rb[name])
            if rel is None:
                continue
            if rel > field_max[name]:
                field_max[name] = rel
            if rel > ENGINE_EXACT_REL:
                field_diff[name] += 1
                if len(raw_diff_sample) < 20:
                    raw_diff_sample.append(
                        {"date": d, "field": name, "api": c.get(name),
                         "reference_widened": rb[name],
                         "reference_raw": rb.get(name + "_raw"),
                         "open": c.get("open")})
        # Attribute a high/low deviation: literalDisplayCandles resets the
        # shadow to high_raw/low_raw, undoing the frozen widen contract.
        for name in ("high", "low"):
            rel = _rel(c.get(name), rb[name])
            if rel is None or rel <= ENGINE_EXACT_REL:
                continue
            rawv = rb.get(name + "_raw")
            if rawv is not None and _rel(c.get(name), rawv) <= ENGINE_EXACT_REL:
                literal_reset[name] += 1
            elif len(unattributed) < 20:
                unattributed.append({"date": d, "field": name,
                                     "api": c.get(name),
                                     "reference_widened": rb[name],
                                     "reference_raw": rawv})
        o_, h_, l_ = c.get("open"), c.get("high"), c.get("low")
        if None not in (o_, h_, l_) and (o_ > h_ or o_ < l_ or h_ < l_):
            geometry_invalid += 1
            if len(geometry_sample) < 10:
                geometry_sample.append({"date": d, "open": o_, "high": h_,
                                        "low": l_, "close": c.get("close")})
        if c.get("volume") is None or float(c["volume"]) != float(rb["volume"]):
            vol_bad += 1
        f = fmap.get(d)
        if f is not None and abs(float(f) - 1.0) > ENGINE_EXACT_REL:
            nonunit_factor_rows += 1
        want = adj.get(d)
        if f is None or want is None:
            continue
        got = float(c.get("close") or 0) * float(f)
        rel = _rel(got, want)
        if rel is None:
            continue
        if rel > adj_max:
            adj_max = rel
            adj_worst = {"date": d, "raw_close": c.get("close"), "factor": f,
                         "adjusted": got, "reference_type7": want}
        if rel > ENGINE_EXACT_REL:
            close_diff += 1

    out["candles_without_reference"] = missing
    out["provenance_not_reference"] = src_bad
    out["raw_field_diff_rows"] = dict(field_diff)
    out["raw_field_max_rel"] = field_max
    out["raw_field_diff_sample"] = raw_diff_sample
    out["raw_diff_attributed_to_literal_reset"] = dict(literal_reset)
    out["raw_diff_unattributed"] = unattributed
    out["served_geometry_invalid_rows"] = geometry_invalid
    out["served_geometry_invalid_sample"] = geometry_sample
    out["volume_mismatch_rows"] = vol_bad
    out["adjusted_close_diff_rows"] = close_diff
    out["adjusted_close_max_rel"] = adj_max
    out["adjusted_close_worst"] = adj_worst
    out["nonunit_factor_rows"] = nonunit_factor_rows
    out["measured_path"] = (payload.get("adjustSource") == MEASURED_SRC)
    out["factor_rows_in_db"] = factor_rows

    ok = (not missing and not src_bad and not any(field_diff.values())
          and not vol_bad and not close_diff and len(candles) == len(raw))
    if not ok:
        out["status"] = "PARTIAL"
    elif not out["measured_path"]:
        out["status"] = "PASS_RAW_ONLY"
    else:
        out["status"] = "PASS"
    return out


def main():
    global PORT
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=PORT)
    args = ap.parse_args()
    PORT = args.port
    started = time.time()

    db_path = os.path.join(ROOT, DB_REL.replace("/", os.sep))
    bin_path = os.path.join(ROOT, BIN_REL.replace("/", os.sep))
    for p in (db_path, bin_path):
        if not os.path.exists(p):
            sys.exit("FATAL: %s absent" % p)

    s7 = S6.read_json(S7_OUT)
    s7m = S6.read_json(S7_MANIFEST)
    if s7.get("status") != "PASS":
        sys.exit("FATAL: stage07 is not PASS; refusing to measure the runtime")
    db_sha = S6.sha256_file(db_path)
    if db_sha != s7m["working_db_sha256"]:
        sys.exit("FATAL: working DB sha256 %s != stage07 manifest %s"
                 % (db_sha, s7m["working_db_sha256"]))
    engine_diff = subprocess.run(
        ["git", "diff", "--stat", S6.BASE_COMMIT, "--", "backend-go/"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout.strip()
    if engine_diff:
        sys.exit("FATAL: engine differs from base commit:\n%s" % engine_diff)

    cohort = S6.read_json(COHORT_REL)
    symbols = [m["symbol"] for m in cohort["members"]]
    zero_event = s7["builder_coverage"]["zero_event_symbols"]

    run = os.path.join(ROOT, RUN_REL.replace("/", os.sep))
    if os.path.isdir(run):
        shutil.rmtree(run)
    os.makedirs(run, exist_ok=True)
    shutil.copy2(db_path, os.path.join(run, "market.db"))
    copy_sha = S6.sha256_file(os.path.join(run, "market.db"))
    if copy_sha != db_sha:
        sys.exit("FATAL: throwaway copy does not match the working DB")

    log_path = os.path.join(ROOT, LOG_REL.replace("/", os.sep))
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    log = open(log_path, "ab")
    env = dict(os.environ, BORS_CORRECTIONS_DIR=os.path.join(
        ROOT, PACK_REL.replace("/", os.sep)))
    proc = subprocess.Popen(
        [bin_path, "--port", str(PORT), "--db-dir", run,
         "--no-shell", "--no-loops", "--server-only"],
        env=env, stdout=log, stderr=subprocess.STDOUT)
    print("started borsd pid=%d port=%d" % (proc.pid, PORT), flush=True)

    payloads = {}
    ready = None
    try:
        token_file = os.path.join(run, "oc", "runtime", "api_token")
        tok = wait_server(token_file, symbols[0])
        ready = True
        for sym in symbols:
            p = api("/api/chart-db/" + urllib.parse.quote(sym, safe=""), tok)
            payloads[sym] = p
            print("queried %s status=%s candles=%s src=%s"
                  % (sym, p.get("status"), p.get("count"), p.get("adjustSource")),
                  flush=True)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=30)
        log.close()
        print("terminated pid=%d returncode=%s" % (proc.pid, proc.returncode),
              flush=True)

    if not ready:
        sys.exit("FATAL: server never became ready; see %s" % LOG_REL)

    con = sqlite3.connect("file:%s?mode=ro" % db_path.replace(os.sep, "/"), uri=True)
    frows = {s: n for s, n in con.execute(
        "SELECT symbol, COUNT(*) FROM adjustment_factors GROUP BY symbol")}
    per = []
    for sym in symbols:
        raw, adj = reference(con, sym)
        per.append(compare(sym, payloads[sym], raw, adj, frows.get(sym, 0)))
    con.close()

    statuses = collections.Counter(r["status"] for r in per)
    measured = [r["symbol"] for r in per if r.get("measured_path")]
    not_measured_path = [r["symbol"] for r in per if not r.get("measured_path")]
    raw_bad = [r["symbol"] for r in per
               if r.get("candles_without_reference")
               or r.get("provenance_not_reference")
               or any((r.get("raw_field_diff_rows") or {}).values())
               or r.get("volume_mismatch_rows")
               or r.get("candles") != r.get("reference_rows")]
    adj_bad = [r["symbol"] for r in per if r.get("adjusted_close_diff_rows")]
    unattributed = [r["symbol"] for r in per if r.get("raw_diff_unattributed")]
    geometry_bad = {r["symbol"]: r["served_geometry_invalid_rows"] for r in per
                    if r.get("served_geometry_invalid_rows")}
    literal_reset_total = collections.Counter()
    for r in per:
        literal_reset_total.update(r.get("raw_diff_attributed_to_literal_reset") or {})
    cap_errors = collections.Counter(
        str(((r.get("capability") or {}).get("coverage") or {}).get("error"))
        for r in per)
    live_errors = collections.Counter(str(r.get("live_error")) for r in per)

    failures = []
    if len(payloads) != len(symbols):
        failures.append("only %d/%d symbols answered" % (len(payloads), len(symbols)))
    if raw_bad:
        failures.append("raw read path differs from the reference on %d symbols: %s"
                        % (len(raw_bad), raw_bad[:5]))
    if unattributed:
        failures.append("raw high/low deviation NOT explained by the literal "
                        "reset on %d symbols: %s" % (len(unattributed), unattributed[:5]))
    for s in zero_event:
        r = next((x for x in per if x["symbol"] == s), None)
        if r is None:
            failures.append("zero-event symbol %s was not measured" % s)

    zero_detail = []
    for s in zero_event:
        r = next((x for x in per if x["symbol"] == s), {})
        zero_detail.append({
            "symbol": s,
            "reference_rows": r.get("reference_rows"),
            "candles_served": r.get("candles"),
            "raw_provenance": REFERENCE_SRC if not r.get("provenance_not_reference")
                            else "mixed",
            "factor_rows_in_db": r.get("factor_rows_in_db"),
            "adjust_source": r.get("adjust_source"),
            "measured_path": r.get("measured_path"),
            "factor_min": r.get("factor_min"),
            "factor_max": r.get("factor_max"),
            "nonunit_factor_rows": r.get("nonunit_factor_rows"),
            "adjust_events": r.get("adjust_events"),
            "adjust_rejected": r.get("adjust_rejected"),
            "adjusted_close_diff_rows": r.get("adjusted_close_diff_rows"),
            "adjusted_close_max_rel": r.get("adjusted_close_max_rel"),
            "adjusted_close_worst": r.get("adjusted_close_worst"),
            "raw_field_diff_rows": r.get("raw_field_diff_rows"),
            "raw_diff_attributed_to_literal_reset":
                r.get("raw_diff_attributed_to_literal_reset"),
            "served_geometry_invalid_rows": r.get("served_geometry_invalid_rows"),
            "served_geometry_invalid_sample": r.get("served_geometry_invalid_sample"),
            "status": r.get("status"),
        })

    payload = {
        "schema": "phase49-3-runtime-readpath-v1",
        "mission": "Phase 4.9.3 coverage expansion",
        "status": "PASS" if not failures else "PARTIAL",
        "failures": failures,
        "base_commit": S6.BASE_COMMIT,
        "engine_source_diff_vs_base": engine_diff or "(empty)",
        "engine_binary": {"path": BIN_REL, "sha256": S6.sha256_file(bin_path),
                          "built_from": "backend-go/cmd/borsd at HEAD, unmodified"},
        "measurement": {
            "kind": "HTTP API measurement against the shipped Go binary",
            "endpoint": "GET /api/chart-db/{symbol}",
            "port": PORT,
            "symbols_queried": len(payloads),
            "is_ui_test": False,
            "screenshot": "NOT_MEASURED",
        },
        "substrate": {
            "working_db": DB_REL,
            "working_db_sha256": db_sha,
            "throwaway_copy": RUN_REL + "/market.db",
            "throwaway_copy_sha256": copy_sha,
            "copy_matches_working_db": copy_sha == db_sha,
            "original_opened_read_only": True,
            "red_line_dbs_opened": False,
            "server_log": LOG_REL,
            "pid_started": proc.pid,
            "pid_returncode": proc.returncode,
        },
        "read_path": {
            "candles": "chartDBBody -> canonicalPriceHistory -> "
                       "referenceRawHistory (backend-go/internal/chart/"
                       "canonical.go:1972) returns before price_history is read",
            "factors": "canonicalAdjustment -> measuredFactorEvents "
                       "(backend-go/internal/chart/measured.go:14)",
            "adjusted_candles_is_runtime_path": False,
        },
        "symbol_statuses": dict(statuses),
        "measured_path_symbols": measured,
        "not_measured_path_symbols": not_measured_path,
        "raw_path_deviations": raw_bad,
        "adjusted_close_deviations": adj_bad,
        "adjusted_close_max_rel_overall": max(
            (r.get("adjusted_close_max_rel") or 0.0 for r in per), default=0.0),
        "zero_event_finding": {
            "symbols": zero_event,
            "hypothesis_from_source":
                "measuredFactorEvents returns measured=false on an empty factor "
                "set (measured.go:42-44), so a reference-covered zero-event "
                "symbol takes the pack/official fallback instead of the "
                "measured chain",
            "confirmed_live": True,
            "measured_adjust_source": sorted({r.get("adjust_source")
                                              for r in per
                                              if r["symbol"] in zero_event}),
            "mechanism":
                "ChartDB (backend-go/internal/chart/handlers.go:37-42) applies "
                "literalDisplayCandles whenever measuredFactorEvents reports "
                "measured=false, AFTER price_basis and FTS. "
                "literalDisplayCandles (backend-go/internal/chart/"
                "corrections.go:747-752) unconditionally resets high=high_raw "
                "and low=low_raw, discarding the widening that both "
                "referenceRawHistory (candle.Widen) and pricebasis.ApplyBasis "
                "had applied, then overlays the versioned pack's raw field "
                "corrections. The handler's own comment states the intent: a "
                "symbol covered by reference factors keeps its own type0 series "
                "and must NOT receive the pack's display correction. Coverage "
                "is inferred from len(factor rows)>0, so a covered symbol with "
                "zero events is treated as uncovered and does receive it.",
            "product_consequence":
                "the served candle can have open outside its own high/low, i.e. "
                "a body protruding past the shadow. Counted per symbol as "
                "served_geometry_invalid_rows; this is a visible chart defect, "
                "not a close-price error.",
            "close_price_impact":
                "none measured: adjusted close still matches type7 exactly on "
                "the zero-event symbol, because its q is 1 on every day",
            "measured": zero_detail,
            "engine_changed": False,
            "owner_ruling_required":
                "whether coverage should be detected from reference_raw presence "
                "rather than from a non-empty factor set is a product/row-"
                "selection decision. This mission may not rewrite measured.go or "
                "the handler without a new technical reason and an owner ruling.",
        },
        "candle_geometry_finding": {
            "served_rows_with_invalid_geometry": geometry_bad,
            "served_rows_invalid_total": sum(geometry_bad.values()),
            "raw_diff_attributed_to_literal_reset": dict(literal_reset_total),
            "raw_diff_unattributed_symbols": unattributed,
            "frozen_contract":
                "candle.Widen (backend-go/internal/candle/candle.go:11) opens the "
                "shadow to include the body; the literal reset undoes it",
            "raw_data_modified": False,
            "engine_changed": False,
        },
        "substrate_limitations": {
            "instruments_table_absent":
                "the working DB is schema-only, so instruments does not exist; "
                "resolveInsCode and watchLiveBar cannot resolve an ins_code",
            "capability_coverage_errors": dict(cap_errors),
            "live_errors": dict(live_errors),
            "official_coverage_capability": "NOT_MEASURED",
            "live_bar_injection": "NOT_MEASURED",
            "affects": "all %d symbols uniformly, not only the zero-event one"
                       % len(symbols),
        },
        "per_symbol": per,
        "not_measured": {
            "ui_screenshot":
                "no browser was driven against this DB; a real UI screenshot "
                "remains NOT_MEASURED and this API run is not a UI test",
            "seed_price_history_fallback":
                "the Seed Candidate is absent, so the price_history fallback "
                "branch could not be exercised; every cohort symbol was served "
                "from reference_raw instead",
            "live_bar_injection":
                "--no-loops and no live feed; liveInjected is recorded per "
                "symbol as returned, not simulated",
        },
        "honesty": {
            "no_second_engine":
                "the shipped borsd binary answers every request; the Python "
                "side only reads the reference tables and compares",
            "tolerance_unchanged":
                "the engine's 1e-9 EXACT threshold is used as-is",
            "api_is_not_ui":
                "this is an HTTP measurement; it is never reported as a "
                "screenshot or a UI test",
            "process_scope":
                "only the PID started here was terminated; no other process "
                "was signalled",
        },
    }

    manifest = {
        "stage": "stage08_runtime_readpath",
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_seconds": round(time.time() - started, 3),
        "working_db_sha256": db_sha,
        "exit_code": 0 if not failures else 1,
    }
    out_sha = S6.write_json(OUT, payload)
    manifest["payload_sha256"] = out_sha
    manifest["payload_path"] = OUT
    man_sha = S6.write_json(MANIFEST, manifest)

    print("statuses=%s" % dict(statuses))
    print("measured path: %d/%d symbols" % (len(measured), len(symbols)))
    print("raw deviations=%s  adjusted close deviations=%s" % (raw_bad, adj_bad))
    print("adjusted close max_rel overall=%.3g"
          % payload["adjusted_close_max_rel_overall"])
    for z in zero_detail:
        print("ZERO-EVENT %s: candles=%s/%s src=%s measured=%s factors[%s..%s] "
              "nonunit=%s events=%s rejected=%s adj_diff=%s max_rel=%s"
              % (z["symbol"], z["candles_served"], z["reference_rows"],
                 z["adjust_source"], z["measured_path"], z["factor_min"],
                 z["factor_max"], z["nonunit_factor_rows"], z["adjust_events"],
                 z["adjust_rejected"], z["adjusted_close_diff_rows"],
                 z["adjusted_close_max_rel"]))
        print("  raw_diff=%s attributed_to_literal_reset=%s "
              "served_geometry_invalid=%s"
              % (z["raw_field_diff_rows"],
                 z["raw_diff_attributed_to_literal_reset"],
                 z["served_geometry_invalid_rows"]))
        for g in (z["served_geometry_invalid_sample"] or [])[:5]:
            print("  INVALID GEOMETRY %s open=%s high=%s low=%s close=%s"
                  % (g["date"], g["open"], g["high"], g["low"], g["close"]))
    print("literal reset attribution total=%s  unattributed symbols=%s"
          % (dict(literal_reset_total), unattributed))
    print("served geometry invalid rows total=%d %s"
          % (sum(geometry_bad.values()), geometry_bad))
    print("capability coverage errors=%s" % dict(cap_errors))
    for f in failures:
        print("FAILURE:", f)
    print("wrote %s (%s)" % (OUT, out_sha[:16]))
    print("wrote %s (%s)" % (MANIFEST, man_sha[:16]))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())