#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stage E (full-verification rerun): real product tests on isolated copies
against the Phase 4.9.1 Seed Candidate and ra365-phase49-rebuild-full-v2.

Parameterized copy of `_audit/phase49-finalization/stageE_product_tests.py`.
Only the candidate constants changed (seed, seed lzma, pack, binary, reference
bars, base dir); every check is the Phase 4.9 check, unchanged.

  clean install (no DB) -> seed extraction -> full history API
  upgrade (1-day-ish DB + user data) -> seed merge -> preserve + idempotent
  restart -> same data, no duplicate rows
  Daily/Weekly/Monthly data checks against the reference capture
"""
import gzip
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
SEED_DB = os.path.join(ROOT, "_audit", "phase49-full-verification", "seed",
                       "market.db")
SEED_LZMA = SEED_DB + ".lzma"
BASE = os.path.join(ROOT, "_audit", "phase49-full-verification", "db",
                    "product-test")
PACK = os.path.join(ROOT, "data", "ra365_corrections",
                    "ra365-phase49-rebuild-full-v2")
REF_BARS = os.path.join(ROOT, "_audit", "phase49-full-verification", "captures",
                        "bars-all.ndjson.gz")
OUT = os.path.join(ROOT, "_audit", "phase49-full-verification", "db",
                   "product-test-report.json")


def api(port, path, token):
    req = urllib.request.Request(
        "http://127.0.0.1:%d%s" % (port, path),
        headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode())


def wait_server(port, token_file, timeout=1200):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        if os.path.exists(token_file):
            try:
                tok = open(token_file, encoding="ascii").read().strip()
                p = api(port, "/api/chart-db/" + urllib.parse.quote("فولاد", safe=""), tok)
                if p.get("status") == "success":
                    return tok, p
            except Exception as exc:  # noqa: BLE001
                last = exc
        time.sleep(2)
    raise RuntimeError("server did not become ready: %r" % (last,))


def start(data_dir, port):
    env = dict(os.environ)
    env["BORS_CORRECTIONS_DIR"] = PACK
    log = open(os.path.join(BASE, "server-%d.log" % port), "ab")
    proc = subprocess.Popen(
        [BIN, "--port", str(port), "--db-dir", data_dir,
         "--no-shell", "--no-loops", "--server-only"],
        env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        tok, first = wait_server(port, os.path.join(data_dir, "oc", "runtime", "api_token"))
    except BaseException:
        stop(proc)
        log.close()
        raise
    return proc, tok, first


def stop(proc):
    proc.terminate()
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=30)


def ref_bars():
    raw, adj = {}, {}
    with gzip.open(REF_BARS, "rt", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            if r["symbol"] != "فولاد":
                continue
            if r["resolution"] == "D" and r["type"] == "type0":
                raw[r["date"]] = r
            elif r["resolution"] == "D" and r["type"] == "type7":
                adj[r["date"]] = r
    return raw, adj


def check_symbol(payload, raw, adj):
    candles = payload.get("candles") or []
    factors = {f["time"]: f["factor"] for f in payload.get("factors") or []}
    checks = {"count": len(candles),
              "first": candles[0]["time"] if candles else None,
              "last": candles[-1]["time"] if candles else None,
              "events": len(payload.get("adjustEvents") or []),
              "cap": ((payload.get("adjustCapability") or {}).get("corrections") or {}).get("version")}
    # adjusted close vs reference type7 on sample dates
    diffs = []
    for c in candles[:: max(1, len(candles) // 25)]:
        d = c["time"][:10]
        if d in adj and d in factors:
            want = float(adj[d]["close"])
            got = float(c["close"]) * float(factors[d])
            diffs.append(abs(got - want) / max(abs(want), 1e-9))
    checks["adj_sample_n"] = len(diffs)
    checks["adj_sample_max_rel"] = max(diffs) if diffs else None
    checks["adj_sample_median_rel"] = sorted(diffs)[len(diffs) // 2] if diffs else None
    return checks


def week_key(d):
    y, w, _ = __import__("datetime").date.fromisoformat(d).isocalendar()
    return "%04d-W%02d" % (y, w)


def month_key(d):
    return d[:7]


def wm_checks(candles):
    out = {}
    for name, key in (("W", week_key), ("M", month_key)):
        last = {}
        for c in candles:
            last[key(c["time"][:10])] = c
        out[name] = {"count": len(last), "first": min(last) if last else None,
                     "last": max(last) if last else None}
    return out


def main():
    if os.path.isdir(BASE):
        shutil.rmtree(BASE)
    os.makedirs(BASE, exist_ok=True)
    report = {"schema": "phase49-product-test-v1", "binary": os.path.relpath(BIN, ROOT),
              "seed": os.path.relpath(SEED_DB, ROOT),
              "pack": os.path.relpath(PACK, ROOT),
              "reference_bars": os.path.relpath(REF_BARS, ROOT),
              "seed_sha256": None, "tests": {}}
    import hashlib
    h = hashlib.sha256()
    with open(SEED_LZMA, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    report["seed_sha256"] = h.hexdigest()
    raw, adj = ref_bars()

    # ---- clean install: no market.db, seed only --------------------------------
    clean = os.path.join(BASE, "clean")
    os.makedirs(clean)
    shutil.copy2(SEED_LZMA, os.path.join(clean, "market.db.lzma"))
    proc, tok, first = start(clean, 8170)
    try:
        p = api(8170, "/api/chart-db/" + urllib.parse.quote("فولاد", safe=""), tok)
        rep = {"seed_state": json.load(open(os.path.join(clean, "market_seed.json"),
                                            encoding="utf-8")) if os.path.exists(
                   os.path.join(clean, "market_seed.json")) else None,
               "chart": check_symbol(p, raw, adj),
               "wm": wm_checks(p.get("candles") or []),
               "db_rows": sqlite3.connect(os.path.join(clean, "market.db")).execute(
                   "SELECT COUNT(*) FROM price_history").fetchone()[0],
               "provenance_rows": sqlite3.connect(os.path.join(clean, "market.db")).execute(
                   "SELECT COUNT(*) FROM raw_history_corrections").fetchone()[0],
               "validity_rows": sqlite3.connect(os.path.join(clean, "market.db")).execute(
                   "SELECT COUNT(*) FROM history_validity").fetchone()[0]}
        report["tests"]["clean_install"] = rep
    finally:
        stop(proc)

    # ---- upgrade: small DB + user data + seed merge ---------------------------
    up = os.path.join(BASE, "upgrade")
    os.makedirs(up)
    shutil.copy2(SEED_DB, os.path.join(up, "market.db"))
    con = sqlite3.connect(os.path.join(up, "market.db"))
    con.execute("PRAGMA journal_mode=DELETE")
    con.execute("DELETE FROM price_history WHERE NOT (symbol='فولاد' AND date>='2026-10-20') "
                "AND NOT (symbol='شبندر' AND date>='2026-10-20')")
    for t in ("adjust_events", "adjust_verdict", "price_adjust_events",
              "share_change_events", "instruments", "raw_history_corrections",
              "history_validity", "adjust_pack_state", "seed_manifest"):
        con.execute("DELETE FROM %s" % t)
    con.execute("UPDATE price_history SET close=close+7 WHERE symbol='فولاد' "
                "AND date=(SELECT MAX(date) FROM price_history WHERE symbol='فولاد')")
    mod = con.execute("SELECT date,close FROM price_history WHERE symbol='فولاد' "
                      "ORDER BY date DESC LIMIT 1").fetchone()
    con.execute("INSERT INTO user_watchlists VALUES ('فولاد','فولاد','یادداشت','تست','2026-11-10T00:00:00Z')")
    con.commit()
    con.close()
    shutil.copy2(SEED_LZMA, os.path.join(up, "market.db.lzma"))
    proc, tok, _ = start(up, 8171)
    try:
        p1 = api(8171, "/api/chart-db/" + urllib.parse.quote("فولاد", safe=""), tok)
        con = sqlite3.connect(os.path.join(up, "market.db"))
        rows1 = con.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
        ae1 = con.execute("SELECT COUNT(*) FROM adjust_events").fetchone()[0]
        keep = con.execute("SELECT close FROM price_history WHERE symbol='فولاد' AND date=?",
                           (mod[0],)).fetchone()
        watch = con.execute("SELECT COUNT(*) FROM user_watchlists").fetchone()[0]
        prov = con.execute("SELECT COUNT(*) FROM raw_history_corrections").fetchone()[0]
        con.close()
        state1 = json.load(open(os.path.join(up, "market_seed.json"), encoding="utf-8"))
        report["tests"]["upgrade_merge"] = {
            "state": {k: state1.get(k) for k in ("status", "mode", "reason",
                                                 "price_history_rows", "price_history_first")},
            "rows": rows1, "adjust_events": ae1,
            "modified_row_kept": keep is not None and abs(keep[0] - mod[1]) < 1e-9,
            "watchlist_kept": watch == 1, "provenance_rows": prov,
            "chart": check_symbol(p1, raw, adj),
            "wm": wm_checks(p1.get("candles") or [])}
        # restart: state applied, no duplicate rows
        p_before = api(8171, "/api/ma/" + urllib.parse.quote("فولاد", safe="") + "?days=5000", tok)
        report["tests"]["ma_full_history"] = {
            "count": len(p_before.get("points") or p_before.get("rows") or p_before.get("ma") or []),
            "keys": sorted(p_before.keys())[:12]}
    finally:
        stop(proc)
    proc, tok, p2 = start(up, 8171)
    try:
        con = sqlite3.connect(os.path.join(up, "market.db"))
        rows2 = con.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
        con.close()
        state2 = json.load(open(os.path.join(up, "market_seed.json"), encoding="utf-8"))
        report["tests"]["restart_idempotent"] = {
            "rows_before": rows1, "rows_after": rows2, "same": rows1 == rows2,
            "state_reason": state2.get("reason"),
            "chart": check_symbol(p2, raw, adj)}
    finally:
        stop(proc)

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
