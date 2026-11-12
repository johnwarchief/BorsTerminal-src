#!/usr/bin/env python3
"""Phase 4.9.4 stage11: before/after OHLCV parity against Rahavard, cohort 30.

The reference law is measured, not assumed: on the cohort's captured rows
type7 = type0 x factor exactly for open/high/low/close, and type7.volume ==
type0.volume. stage07/stage08 compared against a WIDENED baseline, which
manufactured high/low divergences the reference does not have. This stage uses
the literal law on both sides of the fix, with one instrument.

Two layers are measured here; the third (the browser transform) is stage12:
  engine   adjusted_candles materialized by cmd/candlebuild
  api      GET /api/chart-db/{symbol} answered by cmd/borsd

BEFORE binaries are the SHA-pinned phase49-3 artifacts, re-verified here before
use, so the "before" numbers come from the same bytes that produced the
phase49-3 evidence. AFTER binaries are built from the working tree.

Neither red-line DB exists on this host and neither is opened. The working DB
is opened read-only; only throwaway copies under a gitignored run dir are
written. Only the PIDs this script starts are terminated. No UI screenshot is
taken; an API measurement is never called a UI test.
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

WORK_DB_REL = "_audit/phase49-3/db/cohort.db"
BEFORE_BORSD_REL = "_audit/phase49-3/bin/borsd.exe"
BEFORE_BUILD_REL = "_audit/phase49-3/bin/candlebuild.exe"
S7_OUT = "_audit/phase49-3/evidence/COHORT-CANDLES.json"
S8_OUT = "_audit/phase49-3/evidence/RUNTIME-READPATH.json"
S8_MANIFEST = "_audit/phase49-3/manifests/stage08-runtime-readpath.json"

RUN_REL = "_audit/phase49-4/db"
BIN_REL = "_audit/phase49-4/bin"
LOG_REL = "_audit/phase49-4/logs"
BARS_CACHE_REL = "_audit/phase49-4/db/cohort-bars.json"
PAYLOAD_REL = "_audit/phase49-4/db/api-payloads.json"
OUT = "_audit/phase49-4/evidence/RUNTIME-PARITY.json"
MANIFEST = "_audit/phase49-4/manifests/stage11-runtime-parity.json"

PACK_REL = "data/ra365_corrections/ra365-phase49-rebuild-full-v2"
# The engine's own frozen EXACT threshold; quoted, never re-tuned here.
ENGINE_EXACT_REL = 1e-9
FIELDS = ("open", "high", "low", "close", "volume")
PRICE_FIELDS = ("open", "high", "low", "close")
MEASURED_SRC = "local-measured-factors"
REFERENCE_SRC = "rahavard-type0"


def _rel(got, want):
    if got is None or want is None:
        return None
    return abs(float(got) / float(want) - 1.0) if want else abs(float(got))


def ro(path):
    return sqlite3.connect("file:%s?mode=ro" % path.replace(os.sep, "/"), uri=True)


def literal_reference(ex):
    """type0 exactly as captured, plus the engine's own row-skip accounting.

    No widening: the reference's open may legitimately lie outside its own
    high/low, and that geometry is what the product must serve.
    """
    ref0, ref7, skipped = {}, {}, {}
    for sym, bars in ex["raw"].items():
        keep, drop = {}, []
        for d, b in bars.items():
            c, v = b.get("close"), b.get("volume")
            if c is None or c <= 0 or v is None or v <= 0:
                drop.append(d)
                continue
            o = b.get("open")
            keep[d] = {"open": o if (o is not None and o > 0) else c,
                       "high": b.get("high"), "low": b.get("low"),
                       "close": c, "volume": v}
        ref0[sym] = keep
        skipped[sym] = drop
        ref7[sym] = {d: {f: b.get(f) for f in FIELDS}
                     for d, b in ex["adj_ohlc"].get(sym, {}).items()}
    return ref0, ref7, skipped


def compare(sym, got, factors, ref0, ref7):
    """One symbol, field by field, against the literal reference law.

    factors=None means `got` already holds adjusted values (engine table,
    browser bars). Otherwise `got` is the raw series and the adjusted value is
    got*f, which is exactly what the browser does with the server's factors.
    """
    r0, r7 = ref0[sym], ref7[sym]
    out = {"symbol": sym, "rows_served": len(got), "rows_reference": len(r0),
           "rows_missing": sorted(set(r0) - set(got))[:20],
           "rows_missing_count": len(set(r0) - set(got)),
           "rows_extra": sorted(set(got) - set(r0))[:20],
           "rows_extra_count": len(set(got) - set(r0))}
    raw_diff = collections.Counter()
    raw_max = {f: 0.0 for f in PRICE_FIELDS}
    adj_diff = collections.Counter()
    adj_max = {f: 0.0 for f in PRICE_FIELDS}
    adj_worst = {f: None for f in PRICE_FIELDS}
    vol_bad = []
    sample = []
    served_outside = 0
    no_factor = []
    for d, g in sorted(got.items()):
        want0, want7 = r0.get(d), r7.get(d)
        if want0 is None:
            continue
        f = 1.0 if factors is None else factors.get(d)
        if f is None:
            no_factor.append(d)
            continue
        for name in PRICE_FIELDS:
            gv = g.get(name)
            if factors is not None:
                rel = _rel(gv, want0.get(name))
                if rel is not None:
                    raw_max[name] = max(raw_max[name], rel)
                    if rel > ENGINE_EXACT_REL:
                        raw_diff[name] += 1
                        if len(sample) < 20:
                            sample.append({"date": d, "field": name,
                                           "layer": "raw", "served": gv,
                                           "reference": want0.get(name)})
            if want7.get(name) is None:
                continue
            av = gv if factors is None else (
                None if gv is None else float(gv) * float(f))
            rel = _rel(av, want7[name])
            if rel is None:
                continue
            if rel > adj_max[name]:
                adj_max[name] = rel
                adj_worst[name] = {"date": d, "served": gv, "factor": f,
                                   "adjusted": av, "reference_type7": want7[name]}
            if rel > ENGINE_EXACT_REL:
                adj_diff[name] += 1
                if len(sample) < 20:
                    sample.append({"date": d, "field": name, "layer": "adjusted",
                                   "served": gv, "factor": f, "adjusted": av,
                                   "reference_type7": want7[name]})
        # Volume is never scaled: type7.volume == type0.volume on every row.
        if g.get("volume") is None or float(g["volume"]) != float(want0["volume"]):
            vol_bad.append({"date": d, "served": g.get("volume"),
                            "reference": want0["volume"]})
        o_, h_, l_ = g.get("open"), g.get("high"), g.get("low")
        if None not in (o_, h_, l_) and (o_ > h_ or o_ < l_):
            served_outside += 1
    ref_outside = sum(1 for b in r0.values()
                      if None not in (b["open"], b["high"], b["low"])
                      and (b["open"] > b["high"] or b["open"] < b["low"]))
    out.update({
        "raw_layer_measured": factors is not None,
        "rows_without_factor": len(no_factor),
        "rows_without_factor_sample": no_factor[:20],
        "raw_diff_rows": dict(raw_diff), "raw_max_rel": raw_max,
        "adjusted_diff_rows": dict(adj_diff), "adjusted_max_rel": adj_max,
        "adjusted_worst": adj_worst,
        "volume_mismatch_rows": len(vol_bad), "volume_mismatch_sample": vol_bad[:10],
        "served_open_outside_rows": served_outside,
        "reference_open_outside_rows": ref_outside,
        "diff_sample": sample,
    })
    bad = (out["rows_missing_count"] or out["rows_extra_count"] or no_factor
           or any(raw_diff.values()) or any(adj_diff.values()) or vol_bad)
    out["status"] = "PARTIAL" if bad else "PASS"
    return out


def roll_up(per):
    rows = sum(r["rows_served"] for r in per)
    adj = collections.Counter()
    raw = collections.Counter()
    amax = {f: 0.0 for f in PRICE_FIELDS}
    rmax = {f: 0.0 for f in PRICE_FIELDS}
    for r in per:
        adj.update(r["adjusted_diff_rows"])
        raw.update(r["raw_diff_rows"])
        for f in PRICE_FIELDS:
            amax[f] = max(amax[f], r["adjusted_max_rel"][f])
            rmax[f] = max(rmax[f], r["raw_max_rel"][f])
    return {
        "symbols": len(per),
        "symbols_pass": sum(1 for r in per if r["status"] == "PASS"),
        "symbols_partial": [r["symbol"] for r in per if r["status"] != "PASS"],
        "rows_served": rows,
        "rows_missing": sum(r["rows_missing_count"] for r in per),
        "rows_extra": sum(r["rows_extra_count"] for r in per),
        "rows_without_factor": sum(r.get("rows_without_factor", 0) for r in per),
        "raw_layer_measured": all(r.get("raw_layer_measured", False) for r in per),
        "adjusted_diff_rows": dict(adj),
        "adjusted_diff_total": sum(adj.values()),
        "adjusted_max_rel": amax,
        "raw_diff_rows": dict(raw),
        "raw_diff_total": sum(raw.values()),
        "raw_max_rel": rmax,
        "volume_mismatch_rows": sum(r["volume_mismatch_rows"] for r in per),
        "served_open_outside_rows": sum(r["served_open_outside_rows"] for r in per),
        "reference_open_outside_rows":
            sum(r["reference_open_outside_rows"] for r in per),
    }


# ---------- engine layer ----------

def engine_side(db_copy, bin_path, ref0, ref7):
    proc = subprocess.run([bin_path, "--db", db_copy], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        sys.exit("FATAL: candlebuild failed: %s" % (proc.stdout + proc.stderr))
    build = json.loads(proc.stdout)
    con = ro(db_copy)
    per = []
    for sym in sorted(ref0):
        got = {d: {"open": o, "high": h, "low": l, "close": c, "volume": v}
               for d, o, h, l, c, v in con.execute(
                   "SELECT date,open,high,low,close,volume FROM adjusted_candles "
                   "WHERE symbol=? ORDER BY date", (sym,))}
        per.append(compare(sym, got, None, ref0, ref7))
    con.close()
    return build, per


# ---------- api layer ----------

def api(port, path, token, timeout=300):
    req = urllib.request.Request(
        "http://127.0.0.1:%d%s" % (port, path),
        headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def wait_server(port, token_file, probe, timeout=600):
    t0, last = time.time(), None
    while time.time() - t0 < timeout:
        if os.path.exists(token_file):
            try:
                tok = open(token_file, encoding="ascii").read().strip()
                p = api(port, "/api/chart-db/" + urllib.parse.quote(probe, safe=""),
                        tok, timeout=30)
                if p.get("status") == "success":
                    return tok
                last = "probe status=%r" % p.get("status")
            except Exception as exc:  # noqa: BLE001
                last = repr(exc)
        time.sleep(1)
    raise RuntimeError("server did not become ready: %s" % last)


def api_side(db_dir, bin_path, port, symbols, ref0, ref7, log_path):
    env = dict(os.environ, BORS_CORRECTIONS_DIR=os.path.join(
        ROOT, PACK_REL.replace("/", os.sep)))
    log = open(log_path, "ab")
    proc = subprocess.Popen(
        [bin_path, "--port", str(port), "--db-dir", db_dir,
         "--no-shell", "--no-loops", "--server-only"],
        env=env, stdout=log, stderr=subprocess.STDOUT)
    print("  started borsd pid=%d port=%d" % (proc.pid, port), flush=True)
    payloads, ready, tok = {}, False, None
    try:
        tok = wait_server(port, os.path.join(db_dir, "oc", "runtime", "api_token"),
                          symbols[0])
        ready = True
        for sym in symbols:
            payloads[sym] = api(
                port, "/api/chart-db/" + urllib.parse.quote(sym, safe=""), tok)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=30)
        log.close()
        print("  terminated pid=%d returncode=%s" % (proc.pid, proc.returncode),
              flush=True)
    if not ready:
        sys.exit("FATAL: server never became ready; see %s" % log_path)
    per = []
    for sym in symbols:
        p = payloads[sym]
        if p.get("status") != "success":
            per.append({"symbol": sym, "status": "BLOCKED",
                        "message": p.get("message"), "rows_served": 0,
                        "rows_reference": len(ref0[sym]),
                        "rows_missing_count": len(ref0[sym]),
                        "rows_extra_count": 0, "rows_missing": [], "rows_extra": [],
                        "raw_diff_rows": {}, "adjusted_diff_rows": {},
                        "raw_max_rel": {f: 0.0 for f in PRICE_FIELDS},
                        "adjusted_max_rel": {f: 0.0 for f in PRICE_FIELDS},
                        "adjusted_worst": {f: None for f in PRICE_FIELDS},
                        "volume_mismatch_rows": 0, "volume_mismatch_sample": [],
                        "served_open_outside_rows": 0,
                        "reference_open_outside_rows": 0, "diff_sample": []})
            continue
        got, factors = {}, {}
        for c in p.get("candles") or []:
            d = str(c.get("time") or c.get("date") or "")[:10]
            if d:
                got[d] = {f: c.get(f) for f in FIELDS}
        for f in p.get("factors") or []:
            d = str(f.get("time") or "")[:10]
            if d:
                factors[d] = f.get("factor")
        r = compare(sym, got, factors, ref0, ref7)
        r["adjust_source"] = p.get("adjustSource")
        r["measured_path"] = p.get("adjustSource") == MEASURED_SRC
        r["live_injected"] = p.get("liveInjected")
        r["declared_count"] = p.get("count")
        r["provenance_not_reference"] = sorted(
            {str(c.get("src")) for c in (p.get("candles") or [])
             if c.get("src") != REFERENCE_SRC})
        r["factor_min"] = min((v for v in factors.values() if v is not None),
                              default=None)
        r["factor_max"] = max((v for v in factors.values() if v is not None),
                              default=None)
        if r["provenance_not_reference"]:
            r["status"] = "PARTIAL"
        per.append(r)
    return payloads, per, {"pid": proc.pid, "returncode": proc.returncode,
                           "port": port}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", choices=("engine", "api", "all"), default="all")
    ap.add_argument("--skip-build", action="store_true",
                    help="reuse the AFTER binaries already in " + BIN_REL)
    ap.add_argument("--port-before", type=int, default=18096)
    ap.add_argument("--port-after", type=int, default=18097)
    args = ap.parse_args()
    started = time.time()

    for rel, exp in S7.EXPECTED_SHA.items():
        got = S6.sha256_file(os.path.join(ROOT, rel.replace("/", os.sep)))
        if got != exp:
            sys.exit("FATAL: pinned input %s sha256 %s != %s" % (rel, got, exp))

    s7, s8 = S6.read_json(S7_OUT), S6.read_json(S8_OUT)
    s8m = S6.read_json(S8_MANIFEST)
    work_db = os.path.join(ROOT, WORK_DB_REL.replace("/", os.sep))
    db_sha = S6.sha256_file(work_db)
    if db_sha != s8m["working_db_sha256"]:
        sys.exit("FATAL: working DB sha256 %s != stage08 pin %s"
                 % (db_sha, s8m["working_db_sha256"]))
    before = {}
    for tag, rel, rec in (("borsd", BEFORE_BORSD_REL, s8["engine_binary"]),
                          ("candlebuild", BEFORE_BUILD_REL, s7["engine_binary"])):
        p = os.path.join(ROOT, rel.replace("/", os.sep))
        got = S6.sha256_file(p)
        if got != rec["sha256"]:
            sys.exit("FATAL: BEFORE %s sha256 %s != recorded %s"
                     % (tag, got, rec["sha256"]))
        before[tag] = {"path": rel, "sha256": got}
    base_engine_diff = subprocess.run(
        ["git", "diff", "--stat", S6.BASE_COMMIT, "HEAD", "--", "backend-go/"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout.strip()
    if base_engine_diff:
        sys.exit("FATAL: HEAD engine differs from the pinned BEFORE base:\n%s"
                 % base_engine_diff)
    after_diff = subprocess.run(
        ["git", "diff", "--stat", "HEAD", "--", "backend-go/"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout.strip()

    run = os.path.join(ROOT, RUN_REL.replace("/", os.sep))
    os.makedirs(run, exist_ok=True)
    bin_dir = os.path.join(ROOT, BIN_REL.replace("/", os.sep))
    log_dir = os.path.join(ROOT, LOG_REL.replace("/", os.sep))
    os.makedirs(bin_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)

    after = {}
    if not args.skip_build:
        for tag, cmd in (("borsd", "./cmd/borsd"), ("candlebuild", "./cmd/candlebuild")):
            dest = os.path.join(bin_dir, tag + ".exe")
            proc = subprocess.run(["go", "build", "-o", dest, cmd],
                                  cwd=os.path.join(ROOT, "backend-go"),
                                  capture_output=True, text=True, encoding="utf-8")
            if proc.returncode != 0:
                sys.exit("FATAL: go build %s failed: %s" % (cmd, proc.stderr))
            after[tag] = {"path": os.path.relpath(dest, ROOT).replace(os.sep, "/"),
                          "sha256": S6.sha256_file(dest)}
            print("built AFTER %s (%s)" % (tag, after[tag]["sha256"][:16]), flush=True)
    else:
        for tag in ("borsd", "candlebuild"):
            dest = os.path.join(bin_dir, tag + ".exe")
            if not os.path.exists(dest):
                sys.exit("FATAL: --skip-build but %s absent" % dest)
            after[tag] = {"path": os.path.relpath(dest, ROOT).replace(os.sep, "/"),
                          "sha256": S6.sha256_file(dest)}

    cohort = S6.read_json(S7.COHORT_REL)
    symbols = [m["symbol"] for m in cohort["members"]]
    summary = S6.read_json(S7.SUMMARY_REL)
    capture_day = summary["capture"]["captured_at_max"][:10]
    cache = os.path.join(ROOT, BARS_CACHE_REL.replace("/", os.sep))
    if os.path.exists(cache):
        ex = json.load(io.open(cache, encoding="utf-8"))
        print("reusing cached cohort bars (%s)" % cache, flush=True)
    else:
        index = json.load(io.open(os.path.join(
            ROOT, S7.INDEX_REL.replace("/", os.sep)), encoding="utf-8"))
        keys = {m["key"] for m in cohort["members"]}
        spelling = {sp: k for k, r in index.items() for sp in r["raw_symbols"]}
        print("extracting cohort bars (capture_day=%s) ..." % capture_day, flush=True)
        ex = S7.extract_cohort(os.path.join(
            ROOT, S7.BARS_REL.replace("/", os.sep)), keys, spelling, capture_day)
        if len(ex["raw"]) != len(keys):
            sys.exit("FATAL: extracted %d symbols, expected %d"
                     % (len(ex["raw"]), len(keys)))
        with io.open(cache, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(ex, fh, ensure_ascii=False)
    ref0, ref7, skipped = literal_reference(ex)
    print("reference rows: type0=%d type7=%d skipped=%d"
          % (sum(len(v) for v in ref0.values()),
             sum(len(v) for v in ref7.values()),
             sum(len(v) for v in skipped.values())), flush=True)

    layers, failures = {}, []
    con = ro(work_db)
    zero_event = [s for s in symbols if not con.execute(
        "SELECT 1 FROM adjustment_factors WHERE symbol=? LIMIT 1", (s,)).fetchone()]
    con.close()

    if args.layer in ("engine", "all"):
        layers["engine"] = {}
        for side, binrec in (("before", before["candlebuild"]),
                             ("after", after["candlebuild"])):
            copy = os.path.join(run, "engine-%s" % side)
            os.makedirs(copy, exist_ok=True)
            dst = os.path.join(copy, "market.db")
            shutil.copy2(work_db, dst)
            if S6.sha256_file(dst) != db_sha:
                sys.exit("FATAL: engine %s copy does not match the working DB" % side)
            print("engine %s ..." % side, flush=True)
            build, per = engine_side(dst, os.path.join(
                ROOT, binrec["path"].replace("/", os.sep)), ref0, ref7)
            layers["engine"][side] = {"build": build, "summary": roll_up(per),
                                      "per_symbol": per,
                                      "db_copy_sha256": S6.sha256_file(dst)}
            print("  %s" % json.dumps(layers["engine"][side]["summary"],
                                       ensure_ascii=False)[:400], flush=True)

    if args.layer in ("api", "all"):
        layers["api"] = {}
        dumped = {"capture_day": capture_day, "payloads": {}}
        for side, binrec, port in (("before", before["borsd"], args.port_before),
                                   ("after", after["borsd"], args.port_after)):
            copy = os.path.join(run, "api-%s" % side)
            if os.path.isdir(copy):
                shutil.rmtree(copy)
            os.makedirs(copy, exist_ok=True)
            dst = os.path.join(copy, "market.db")
            shutil.copy2(work_db, dst)
            if S6.sha256_file(dst) != db_sha:
                sys.exit("FATAL: api %s copy does not match the working DB" % side)
            print("api %s ..." % side, flush=True)
            payloads, per, procinfo = api_side(
                copy, os.path.join(ROOT, binrec["path"].replace("/", os.sep)),
                port, symbols, ref0, ref7,
                os.path.join(log_dir, "stage11-%s-server.log" % side))
            layers["api"][side] = {"summary": roll_up(per), "per_symbol": per,
                                   "server": procinfo,
                                   "measured_path_symbols":
                                       [r["symbol"] for r in per if r.get("measured_path")],
                                   "not_measured_path_symbols":
                                       [r["symbol"] for r in per
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
            failures.append("%s AFTER: %d adjusted field divergences, %d volume "
                            "divergences" % (name, a["adjusted_diff_total"],
                                             a["volume_mismatch_rows"]))
        if a["raw_diff_total"]:
            failures.append("%s AFTER: %d raw field divergences"
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
            failures.append("api AFTER: %d symbols still off the measured path: %s"
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
        "schema": "phase49-4-runtime-parity-v1",
        "mission": "Phase 4.9.4 runtime parity with Rahavard",
        "status": "PASS" if not failures else "PARTIAL",
        "failures": failures,
        "base_commit": S6.BASE_COMMIT,
        "head_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                      capture_output=True, text=True,
                                      encoding="utf-8").stdout.strip(),
        "engine_source_diff_after_vs_head": after_diff or "(empty)",
        "reference_law": {
            "statement": "type7 = type0 x factor for open/high/low/close; "
                         "type7.volume == type0.volume",
            "widening_applied_to_reference": False,
            "correction_vs_phase49_3":
                "stage07.parity and stage08.reference built a WIDENED baseline "
                "(candlecontract.Widen). The measured reference has no such "
                "widening, so that baseline manufactured high/low divergences "
                "and stage08 attributed them to the handler's literal reset. "
                "This stage compares against the literal captured values.",
            "tolerance": ENGINE_EXACT_REL,
            "tolerance_unchanged": True,
        },
        "binaries": {"before": before, "after": after},
        "substrate": {
            "working_db": WORK_DB_REL,
            "working_db_sha256": db_sha,
            "original_opened_read_only": True,
            "red_line_dbs_opened": False,
            "copies_under": RUN_REL,
            "capture_day_quarantine": capture_day,
            "bars_capture_sha256": S7.EXPECTED_SHA[S7.BARS_REL],
            "reference_rows_type0": sum(len(v) for v in ref0.values()),
            "reference_rows_type7": sum(len(v) for v in ref7.values()),
            "reference_rows_skipped_by_engine_rules":
                {s: d for s, d in skipped.items() if d},
        },
        "cohort": {"symbols": symbols, "count": len(symbols),
                   "zero_event_symbols": zero_event},
        "before_after_delta": delta,
        "layers": layers,
        "frontend_layer": {
            "measured_by": "_audit/phase49-4/stage12_frontend_parity.mts",
            "input": PAYLOAD_REL,
            "status": "PENDING" if "api" in layers else "NOT_MEASURED",
        },
        "not_measured": {
            "ui_screenshot": "no browser was driven against this DB; a real UI "
                             "screenshot remains NOT_MEASURED and this API run "
                             "is not a UI test",
            "seed_price_history_fallback": "the Seed Candidate is absent, so the "
                                           "price_history fallback branch could "
                                           "not be exercised",
            "live_bar_injection": "--no-loops and no live feed; liveInjected is "
                                  "recorded as returned, not simulated",
            "instruments_table_absent": "the working DB is schema-only, so "
                                        "resolveInsCode cannot resolve an ins_code",
        },
        "honesty": {
            "no_second_engine": "the shipped Go binaries answer every request; "
                                "Python only reads the reference and compares",
            "before_bytes_are_the_pinned_artifacts":
                "the BEFORE binaries were re-hashed against the phase49-3 "
                "evidence before use, so both sides share one substrate",
            "tolerance_unchanged": "the engine's 1e-9 EXACT threshold is used as-is",
            "no_guard_weakened": "the widened baseline was a wrong reference law, "
                                 "not a tolerance; correcting it makes the check "
                                 "stricter, and every divergence now fails",
            "process_scope": "only the PIDs started here were terminated",
        },
    }

    manifest = {
        "stage": "stage11_runtime_parity",
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

    for name, d in delta.items():
        print("%s: adjusted diff %d -> %d | raw diff %d -> %d | volume %d -> %d "
              "| PASS symbols %d -> %d | rows %d -> %d"
              % (name, d["adjusted_diff_rows_before"], d["adjusted_diff_rows_after"],
                 d["raw_diff_rows_before"], d["raw_diff_rows_after"],
                 d["volume_mismatch_before"], d["volume_mismatch_after"],
                 d["symbols_pass_before"], d["symbols_pass_after"],
                 d["rows_served_before"], d["rows_served_after"]), flush=True)
    for f in failures:
        print("FAILURE:", f)
    print("wrote %s (%s)" % (OUT, out_sha[:16]))
    print("wrote %s (%s)" % (MANIFEST, man_sha[:16]))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())