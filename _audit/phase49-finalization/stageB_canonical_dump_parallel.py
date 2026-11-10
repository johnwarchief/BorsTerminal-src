#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Parallel canonical dump (resumes over valid cached files).

Same pipeline as stageB_canonical_dump.py, but with a process pool and
--skip-existing. Writes one .json.gz per symbol and a merged summary.
"""
import collections
import gzip
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(ROOT, "_audit", "phase49-finalization", "db", "restored-work.db")
OUT = os.path.join(ROOT, "_audit", "phase49-finalization", "evidence", "canonical")
PACK = os.path.join(ROOT, "data", "ra365_corrections", "ra365-r32b-v2")
SUMMARY = os.path.join(ROOT, "_audit", "phase49-finalization", "evidence",
                       "canonical-summary.json")


def safe(sym):
    return sym.replace("/", "_").replace("\\", "_")


def _worker_init():
    os.environ["BORS_DB"] = DB
    os.environ["BORS_CORRECTIONS_DISABLE"] = "1"
    os.environ["BORS_NO_FETCH_LOOPS"] = "1"
    os.environ["PYTHONIOENCODING"] = "utf-8"
    sys.path.insert(0, ROOT)


def candles_for(symbol):
    import sqlite3
    import api.chart as ch
    import candle_contract
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
    candles = []
    for r in rows:
        ck = candle_contract.from_db_row(r)
        if ck is not None:
            candles.append(ck)
    candles, _v, _r = ch._merge_session_backfill(
        candles, [], [], ch._session_backfill(symbol), descending=False)
    return candles


def dump_one(sym):
    _worker_init()
    path = os.path.join(OUT, safe(sym) + ".json.gz")
    if os.path.exists(path):
        try:
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                rec = json.load(fh)
            if rec.get("symbol") == sym:
                return sym, rec, "cached"
        except Exception:
            pass
    import api.chart as ch
    try:
        candles = candles_for(sym)
        times = [str(c["time"])[:10] for c in candles]
        closings = ch._candle_closings(candles)
        evs = ch._stored_adjust_events(sym)
        evs, false_rej = ch._filter_unproven_base_events(sym, evs, times=times)
        src = "local-cache" if evs else (ch._stored_adjust_source(sym) or "local-db-unseen")
        known = src in ch._ADJ_KNOWN_SOURCES or str(src).startswith("fund-portal")
        applied, rejected, _fac, chain, cov = ch._canonical_adjustment(
            sym, times, evs if known else [], closings=closings)
        rec = {
            "symbol": sym,
            "status": "ok" if candles else "no_candles",
            "candles": len(times),
            "first_date": times[0] if times else None,
            "last_date": times[-1] if times else None,
            "source": src,
            "known_source": known,
            "applied_events": [
                {"date": str(e.get("date"))[:10], "ratio": e.get("ratio"),
                 "source": e.get("source")} for e in applied],
            "rejected_count": len(rejected) + len(false_rej),
            "chain_complete": (chain or {}).get("complete"),
            "chain_anchored_last": (chain or {}).get("anchored_last"),
            "coverage": cov,
        }
    except Exception as exc:
        rec = {"symbol": sym, "status": "error",
               "error": "%s: %s" % (type(exc).__name__, exc)}
    tmp = path + ".tmp"
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False)
    os.replace(tmp, path)
    return sym, rec, "dumped"


def symbols_all():
    pack = set()
    for line in open(os.path.join(PACK, "factors.jsonl"), encoding="utf-8"):
        line = line.strip()
        if line:
            r = json.loads(line)
            if r.get("symbol"):
                pack.add(str(r["symbol"]))
    import sqlite3
    con = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)
    ae = {r[0] for r in con.execute("SELECT DISTINCT symbol FROM adjust_events")}
    con.close()
    return sorted(pack | ae)


def main():
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    os.makedirs(OUT, exist_ok=True)
    symbols = symbols_all()
    print("symbols:", len(symbols), "workers:", workers, flush=True)
    t0 = time.time()
    results, done, cached = {}, 0, 0
    with ProcessPoolExecutor(max_workers=workers, initializer=_worker_init) as ex:
        futs = {ex.submit(dump_one, s): s for s in symbols}
        for fut in as_completed(futs):
            sym, rec, how = fut.result()
            results[sym] = rec
            done += 1
            cached += 1 if how == "cached" else 0
            if done % 50 == 0:
                print("  %d/%d cached=%d (%.1fs)" % (
                    done, len(symbols), cached, time.time() - t0), flush=True)
    ok = sum(1 for r in results.values() if r["status"] == "ok")
    err = sum(1 for r in results.values() if r["status"] == "error")
    total_events = sum(len(r.get("applied_events") or []) for r in results.values())
    pre2020 = sum(1 for r in results.values()
                  for e in (r.get("applied_events") or []) if e["date"] < "2020-01-01")
    out = {
        "schema": "phase49-finalization-canonical-dump-v1",
        "db": os.path.relpath(DB, ROOT).replace("\\", "/"),
        "corrections": "disabled",
        "symbols": len(symbols),
        "symbols_ok": ok,
        "symbols_error": err,
        "events_total": total_events,
        "events_pre2020": pre2020,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "per_symbol": {k: {kk: v[kk] for kk in
                           ("status", "candles", "first_date", "last_date", "source",
                            "applied_events", "chain_complete", "chain_anchored_last")
                           } for k, v in results.items()},
    }
    with open(SUMMARY, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)
    print("CANONICAL_DUMP:", "OK" if err == 0 else "WITH_ERRORS",
          "symbols", len(symbols), "ok", ok, "err", err,
          "events", total_events, "pre2020", pre2020,
          "cached", cached, "(%.1fs)" % (time.time() - t0))
    return 0 if err == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
