#!/usr/bin/env python3
"""Targeted product re-check on the approved Seed Candidate.

The full stageE clean-install path extracts the 281 MB lzma Seed, which is slow
on this host (the same path passed in Phase 4.9.1 C5 and its round-trip is
re-verified by seed_recheck). This check starts the shipped Phase 4.9.1 borsd
against a direct copy of the approved Seed and exercises the local chart API,
which is the product path the owner cares about.
"""
import json
import os
import shutil
import sqlite3
import subprocess
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BIN = os.path.join(ROOT, "_audit", "phase49-full-verification", "borsd.exe")
SEED = os.path.join(ROOT, "_audit", "phase49-full-verification", "seed", "market.db")
PACK = os.path.join(ROOT, "data", "ra365_corrections",
                    "ra365-phase49-rebuild-full-v2")
BASE = os.path.join(ROOT, "_audit", "phase49-2", "product", "seed-check")
OUT = os.path.join(ROOT, "_audit", "phase49-2", "evidence", "seed-product-check.json")
PORT = 18082
SYMBOLS = ["فولاد", "شنفت", "شبندر", "وبملت", "خودرو", "تپسي", "طلا", "غشان"]


def api(path, token):
    req = urllib.request.Request(
        "http://127.0.0.1:%d%s" % (PORT, path),
        headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode())


def wait_server(token_file, timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if os.path.exists(token_file):
            try:
                tok = open(token_file, encoding="ascii").read().strip()
                p = api("/api/chart-db/" + urllib.parse.quote("فولاد", safe=""), tok)
                if p.get("status") == "success":
                    return tok
            except Exception:  # noqa: BLE001
                pass
        time.sleep(1)
    raise RuntimeError("server did not become ready")


def main():
    if os.path.isdir(BASE):
        shutil.rmtree(BASE)
    os.makedirs(BASE)
    shutil.copy2(SEED, os.path.join(BASE, "market.db"))
    con = sqlite3.connect("file:%s?mode=ro" % os.path.join(BASE, "market.db")
                          .replace("\\", "/"), uri=True)
    seed_counts = {
        "price_history": con.execute("SELECT COUNT(*) FROM price_history").fetchone()[0],
        "symbols": con.execute(
            "SELECT COUNT(DISTINCT symbol) FROM price_history").fetchone()[0],
        "history_validity": con.execute(
            "SELECT COUNT(*) FROM history_validity").fetchone()[0],
        "reference_derived_rows": con.execute(
            "SELECT COUNT(*) FROM price_history WHERE src='rahavard365'").fetchone()[0],
        "integrity": con.execute("PRAGMA integrity_check").fetchone()[0],
    }
    con.close()
    env = dict(os.environ, BORS_CORRECTIONS_DIR=PACK)
    log = open(os.path.join(BASE, "server.log"), "ab")
    proc = subprocess.Popen(
        [BIN, "--port", str(PORT), "--db-dir", BASE,
         "--no-shell", "--no-loops", "--server-only"],
        env=env, stdout=log, stderr=subprocess.STDOUT)
    result = {"schema": "phase49-2-seed-product-check-v1",
              "seed": os.path.relpath(SEED, ROOT).replace("\\", "/"),
              "seed_counts": seed_counts, "symbols": {}}
    try:
        tok = wait_server(os.path.join(BASE, "oc", "runtime", "api_token"))
        for sym in SYMBOLS:
            p = api("/api/chart-db/" + urllib.parse.quote(sym, safe=""), tok)
            candles = p.get("candles") or []
            factors = p.get("factors") or []
            cap = p.get("adjustCapability") or {}
            result["symbols"][sym] = {
                "status": p.get("status"),
                "candles": len(candles),
                "first": candles[0]["time"][:10] if candles else None,
                "last": candles[-1]["time"][:10] if candles else None,
                "factors": len(factors),
                "events": len(p.get("adjustEvents") or []),
                "adjust_source": p.get("adjustSource"),
                "functional_status": cap.get("functional_status"),
                "last_data_time": p.get("lastDataTime"),
            }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()
    checks = {
        "seed_integrity_ok": seed_counts["integrity"] == "ok",
        "seed_rows_544284": seed_counts["price_history"] == 544284,
        "seed_symbols_6103": seed_counts["symbols"] == 6103,
        "seed_reference_rows_105367":
            seed_counts["reference_derived_rows"] == 105367,
        "all_symbols_responded":
            all(v["status"] == "success" for v in result["symbols"].values()),
        "all_symbols_have_candles":
            all(v["candles"] > 0 for v in result["symbols"].values()),
        "factors_match_candles":
            all(v["factors"] == v["candles"] for v in result["symbols"].values()),
        "all_have_source":
            all(v["adjust_source"] for v in result["symbols"].values()),
    }
    result["checks"] = checks
    result["ok"] = all(checks.values())
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(json.dumps({"ok": result["ok"], "checks": checks}, ensure_ascii=False,
                     indent=1))
    for sym, v in result["symbols"].items():
        print(sym, v)
    print("wrote", OUT)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
