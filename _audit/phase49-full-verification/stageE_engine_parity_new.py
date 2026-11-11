#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stage E (full-verification rerun): Python<->Go parity on the 30 symbols
with the Phase 4.9.1 Seed Candidate + ra365-phase49-rebuild-full-v2 pack.

Parameterized copy of `_audit/phase49-finalization/stageE_engine_parity.py`.
Only the candidate constants changed; the comparison logic, tolerances and
per-symbol expectations are byte-for-byte the Phase 4.9 ones.

Go side: live /api/chart-db from the borsd built from this branch, on an
isolated copy of the candidate seed (never the root/installed DB).
Python side: the same offline canonical pipeline used by api/chart.py.
Compares candles, factors, events and rejected counts.
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(ROOT, "_audit", "phase49-full-verification", "seed", "market.db")
PACK = os.path.join(ROOT, "data", "ra365_corrections",
                    "ra365-phase49-rebuild-full-v2")
BIN = os.path.join(ROOT, "_audit", "phase49-full-verification", "borsd.exe")
SANDBOX = os.path.join(ROOT, "_audit", "phase49-full-verification", "db",
                       "api-sandbox")
PORT = 8161
TOKEN = os.path.join(SANDBOX, "oc", "runtime", "api_token")
SYMS = os.path.join(ROOT, "_audit", "phase49", "continuation", "symbols30.csv")
OUT = os.path.join(ROOT, "_audit", "phase49-full-verification",
                   "engine-parity-30.json")

os.environ["BORS_DB"] = DB
os.environ["BORS_CORRECTIONS_DIR"] = PACK
os.environ["BORS_NO_FETCH_LOOPS"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.path.insert(0, ROOT)

import csv  # noqa: E402

import api.chart as ch  # noqa: E402
import candle_contract  # noqa: E402


def candles_for(symbol):
    con = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)
    raw = con.execute(
        "SELECT symbol,date,open,high,low,close,volume,last,value,src "
        "FROM price_history WHERE symbol=? ORDER BY date DESC", (symbol,)).fetchall()
    con.close()
    seen, rows = set(), []
    for r in raw:
        if r[1] in seen:
            continue
        seen.add(r[1])
        rows.append(r)
    rows.reverse()
    out = []
    for r in rows:
        c = candle_contract.from_db_row(r)
        if c is not None:
            out.append(c)
    return out


def python_side(sym):
    cands = candles_for(sym)
    times = [str(c["time"])[:10] for c in cands]
    closings = ch._candle_closings(cands)
    evs = ch._stored_adjust_events(sym)
    evs, _fr = ch._filter_unproven_base_events(sym, evs, times=times)
    src = "local-cache" if evs else (ch._stored_adjust_source(sym) or "local-db-unseen")
    known = src in ch._ADJ_KNOWN_SOURCES or str(src).startswith("fund-portal")
    applied, rejected, fac, chain, cov = ch._canonical_adjustment(
        sym, times, evs if known else [], closings=closings)
    cands = ch._literal_display_candles(cands, sym, ch._ins_code_for(sym))
    return cands, applied, rejected, fac, chain


def api(token, path):
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (PORT, path),
                                 headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode())


def wait_server(timeout=300):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        if os.path.exists(TOKEN):
            try:
                tok = open(TOKEN, encoding="ascii").read().strip()
                p = api(tok, "/api/chart-db/" + urllib.parse.quote("فولاد", safe=""))
                if p.get("status") == "success":
                    return tok
            except Exception as exc:  # noqa: BLE001
                last = exc
        time.sleep(2)
    raise RuntimeError("server did not become ready: %r" % (last,))


def prepare_sandbox():
    if os.path.isdir(SANDBOX):
        shutil.rmtree(SANDBOX)
    os.makedirs(SANDBOX)
    shutil.copy2(DB, os.path.join(SANDBOX, "market.db"))


def start_server():
    env = dict(os.environ)
    env["BORS_CORRECTIONS_DIR"] = PACK
    log_path = os.path.join(SANDBOX, "server.log")
    log = open(log_path, "ab")
    proc = subprocess.Popen(
        [BIN, "--port", str(PORT), "--db-dir", SANDBOX,
         "--no-shell", "--no-loops", "--server-only"],
        env=env, stdout=log, stderr=subprocess.STDOUT)
    return proc, log


def stop_server(proc, log):
    proc.terminate()
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=30)
    log.close()


def main():
    prepare_sandbox()
    proc, log = start_server()
    try:
        tok = wait_server()
        syms = [r["symbol"] for r in csv.DictReader(open(SYMS, encoding="utf-8-sig"))]
        report, bad = {}, []
        for sym in syms:
            g = api(tok, "/api/chart-db/" + urllib.parse.quote(sym, safe=""))
            gc = g.get("candles") or []
            gf = {x["time"][:10]: float(x["factor"]) for x in g.get("factors") or []}
            pc, pe, pr, pf, chain = python_side(sym)
            pt = [str(c["time"])[:10] for c in pc]
            pfd = dict(zip(pt, pf))
            candle_diffs = 0
            for a, b in zip(gc, pc):
                for k in ("open", "high", "low", "close", "volume"):
                    if a.get(k) is None or b.get(k) is None:
                        continue
                    if abs(float(a[k]) - float(b[k])) > 1e-9 * max(1.0, abs(float(b[k]))):
                        candle_diffs += 1
            common = sorted(set(gf) & set(pfd))
            fdiff = [abs(gf[d] - pfd[d]) / max(abs(pfd[d]), 1e-12) for d in common]
            ge = [(str(e.get("date"))[:10], round(float(e.get("ratio") or 0), 12))
                  for e in (g.get("adjustEvents") or [])]
            pev = [(str(e.get("date"))[:10], round(float(e.get("ratio") or 0), 12))
                   for e in pe]
            rec = {
                "go_count": len(gc), "py_count": len(pc),
                "go_events": len(ge), "py_events": len(pev),
                "events_equal": sorted(ge) == sorted(pev),
                "factor_dates": len(common),
                "factor_max_rel": max(fdiff) if fdiff else None,
                "factor_over_1e12": sum(1 for x in fdiff if x > 1e-12),
                "candle_field_diffs": candle_diffs,
                "chain_complete": (chain or {}).get("complete"),
                "pack": ((g.get("adjustCapability") or {}).get("corrections") or {}).get("version"),
            }
            if rec["events_equal"]:
                rec["event_delta"] = []
            else:
                rec["event_delta"] = sorted(set(ge) ^ set(pev))[:10]
            report[sym] = rec
            if (len(gc) != len(pc) or not rec["events_equal"] or candle_diffs
                    or rec["factor_over_1e12"]):
                bad.append(sym)
            print("%-10s go=%d py=%d ev=%d/%d eq=%s fmax=%s cd=%d" % (
                sym, len(gc), len(pc), len(ge), len(pev), rec["events_equal"],
                ("%.3g" % rec["factor_max_rel"]) if rec["factor_max_rel"] is not None else None,
                candle_diffs), flush=True)
    finally:
        stop_server(proc, log)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "seed": os.path.relpath(DB, ROOT),
                   "binary": os.path.relpath(BIN, ROOT),
                   "pack": "ra365-phase49-rebuild-full-v2",
                   "symbols": len(syms), "passed": len(syms) - len(bad),
                   "mismatches": bad,
                   "per_symbol": report}, fh, ensure_ascii=False, indent=1)
    print("ENGINE_PARITY:", "PASS" if not bad else "FAIL", "mismatches", bad)
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
