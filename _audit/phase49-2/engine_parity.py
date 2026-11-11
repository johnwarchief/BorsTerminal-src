#!/usr/bin/env python3
"""Run the shipped Go engine against an isolated Seed copy and compare its
adjusted output with the fresh Rahavard type7 capture for the 30-symbol pilot.

The server is started from _audit/phase49-full-verification/borsd.exe against
a throwaway copy; the Seed and the root market.db are never opened for write.
Every difference is classified so the engine audit can root-cause it:
  * factor==1 where the reference q!=1 (missing history step),
  * a factor jump with no reference change (bogus/extra step),
  * a ratio mismatch at a matched change (wrong ratio),
  * per-candle residual after those (should be zero: type7 = raw/q exactly).
"""
import argparse
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
BIN = os.path.join(ROOT, "_audit", "phase49-full-verification", "borsd.exe")
SEED = os.path.join(ROOT, "_audit", "phase49-full-verification", "seed", "market.db")
PACK = os.path.join(ROOT, "data", "ra365_corrections",
                    "ra365-phase49-rebuild-full-v2")
CAPTURE = os.path.join(ROOT, "_audit", "phase49-2", "rahavard", "pilot-capture.json")
PILOT = os.path.join(ROOT, "_audit", "phase49-2", "rahavard", "pilot-symbols.json")
BASE = os.path.join(ROOT, "_audit", "phase49-2", "product")
RUN = os.path.join(BASE, "run")
OUT = os.path.join(ROOT, "_audit", "phase49-2", "rahavard", "engine-parity.json")
PORT = 18081
TOL = 1e-6


def api(port, path, token):
    req = urllib.request.Request(
        "http://127.0.0.1:%d%s" % (port, path),
        headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode())


def wait_server(port, token_file, timeout=600):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        if os.path.exists(token_file):
            try:
                tok = open(token_file, encoding="ascii").read().strip()
                p = api(port, "/api/chart-db/" + urllib.parse.quote("فولاد", safe=""), tok)
                if p.get("status") == "success":
                    return tok
            except Exception as exc:  # noqa: BLE001
                last = exc
        time.sleep(1)
    raise RuntimeError("server did not become ready: %r" % (last,))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=SEED)
    ap.add_argument("--bin", default=BIN)
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()
    if os.path.isdir(RUN):
        shutil.rmtree(RUN)
    os.makedirs(RUN, exist_ok=True)
    shutil.copy2(args.db, os.path.join(RUN, "market.db"))
    env = dict(os.environ, BORS_CORRECTIONS_DIR=PACK)
    log = open(os.path.join(BASE, "server-%d.log" % PORT), "ab")
    proc = subprocess.Popen(
        [args.bin, "--port", str(PORT), "--db-dir", RUN,
         "--no-shell", "--no-loops", "--server-only"],
        env=env, stdout=log, stderr=subprocess.STDOUT)
    payloads = {}
    try:
        tok = wait_server(PORT, os.path.join(RUN, "oc", "runtime", "api_token"))
        for item in json.load(open(PILOT, encoding="utf-8")):
            sym = item["symbol"]
            payloads[sym] = api(
                PORT, "/api/chart-db/" + urllib.parse.quote(sym, safe=""), tok)
            print("queried", sym, len(payloads[sym].get("candles") or []))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=30)
        log.close()

    cap = json.load(open(CAPTURE, encoding="utf-8"))
    ref = {}
    for s in cap["series"]:
        typ = "raw" if s["ticker"].endswith(":type0") else "type7"
        ref.setdefault(s["symbol"], {})[typ] = {
            b["utc"][:10]: b["close"] for b in s["bars"] if b.get("close")}

    symbols = []
    for item in json.load(open(PILOT, encoding="utf-8")):
        sym = item["symbol"]
        p = payloads[sym]
        candles = p.get("candles") or []
        factors = {f["time"][:10]: float(f["factor"]) for f in p.get("factors") or []}
        raw = ref[sym]["raw"]
        adj = ref[sym]["type7"]
        common = sorted(set(raw) & set(adj) & set(factors))
        devs = []
        worst = None
        for dt in common:
            want = adj[dt]
            got = raw[dt] * factors[dt]
            dev = abs(got / want - 1.0)
            devs.append(dev)
            if worst is None or dev > worst[1]:
                worst = (dt, dev, raw[dt], factors[dt], got, want)
        # observed q changes vs engine factor changes
        q = {dt: raw[dt] / adj[dt] for dt in common}
        q_changes = []
        prev = None
        for dt in common:
            if prev is not None and abs(q[dt] / prev - 1.0) > 1e-9:
                q_changes.append((dt, q[dt] / prev))
            prev = q[dt]
        f_changes = []
        prev = None
        for dt in common:
            if prev is not None and abs(factors[dt] / prev - 1.0) > 1e-9:
                f_changes.append((dt, factors[dt] / prev))
            prev = factors[dt]
        # q = raw/adjusted; factor = 1/q, so the factor change at an event is
        # the inverse of the q change. Compare f against 1/q.
        missing = [c for c in q_changes if not any(
            abs((1.0 / c[1]) / f[1] - 1) <= TOL
            for f in f_changes if abs(_days(c[0], f[0])) <= 7)]
        extra = [f for f in f_changes if not any(
            abs(f[1] / (1.0 / c[1]) - 1) <= TOL
            for c in q_changes if abs(_days(c[0], f[0])) <= 7)]
        ratio_diff = []
        for c in q_changes:
            best = None
            for f in f_changes:
                dd = abs(_days(c[0], f[0]))
                if dd <= 7 and (best is None or dd < best[0]):
                    best = (dd, f)
            if best and abs(best[1][1] * c[1] - 1) > TOL:
                ratio_diff.append({"date": c[0], "observed": c[1],
                                   "engine": best[1][1], "engine_date": best[1][0]})
        capb = p.get("adjustCapability") or {}
        symbols.append({
            "symbol": sym,
            "candles": len(candles),
            "first": candles[0]["time"][:10] if candles else None,
            "last": candles[-1]["time"][:10] if candles else None,
            "adjust_source": p.get("adjustSource"),
            "event_count": len(p.get("adjustEvents") or []),
            "functional_status": capb.get("functional_status"),
            "common_dates": len(common),
            "max_rel": max(devs) if devs else None,
            "median_rel": sorted(devs)[len(devs) // 2] if devs else None,
            "worst": ({"date": worst[0], "rel": worst[1], "raw": worst[2],
                       "factor": worst[3], "got": worst[4], "want": worst[5]}
                      if worst else None),
            "q_changes": len(q_changes),
            "engine_changes": len(f_changes),
            "missing_engine_steps": [{"date": d, "ratio": r} for d, r in missing],
            "extra_engine_steps": [{"date": d, "ratio": r} for d, r in extra],
            "ratio_diffs": ratio_diff,
            "engine_version": ((p.get("adjustCapability") or {}).get("corrections")
                               or {}).get("version"),
        })
        print("%-10s max_rel=%.6g missing=%d extra=%d ratio_diff=%d"
              % (sym, symbols[-1]["max_rel"] or 0,
                 len(symbols[-1]["missing_engine_steps"]),
                 len(symbols[-1]["extra_engine_steps"]),
                 len(symbols[-1]["ratio_diffs"])))

    out = {
        "schema": "phase49-2-engine-parity-v1",
        "binary": os.path.relpath(args.bin, ROOT).replace("\\", "/"),
        "db": os.path.relpath(args.db, ROOT).replace("\\", "/"),
        "pack": os.path.relpath(PACK, ROOT).replace("\\", "/"),
        "capture_sha256": cap["source"].get("input_sha256"),
        "tolerance": TOL,
        "symbols": symbols,
    }
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    worst = max(symbols, key=lambda s: s["max_rel"] or 0)
    print("worst symbol:", worst["symbol"], worst["max_rel"])
    print("symbols with max_rel <= tol:", sum(1 for s in symbols
                                              if (s["max_rel"] or 0) <= TOL))
    print("wrote", args.out)
    return 0


def _days(a, b):
    import datetime
    try:
        return (datetime.date.fromisoformat(a) - datetime.date.fromisoformat(b)).days
    except ValueError:
        return 10 ** 6


if __name__ == "__main__":
    sys.exit(main())
