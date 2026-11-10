#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stage B (finalization): dump canonical product events (corrections disabled)
for every symbol that has stored adjust_events or a correction-pack entry.

Reuses the same offline canonical pipeline as /api/chart-db's local route:
  _stored_adjust_events -> _filter_unproven_base_events -> _canonical_adjustment
with BORS_CORRECTIONS_DISABLE=1. Read-only against the restored work DB.
"""
import collections
import gzip
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(ROOT, "_audit", "phase49-finalization", "db", "restored-work.db")
OUT = os.path.join(ROOT, "_audit", "phase49-finalization", "evidence", "canonical")
PACK = os.path.join(ROOT, "data", "ra365_corrections", "ra365-r32b-v2")

os.environ["BORS_DB"] = DB
os.environ["BORS_CORRECTIONS_DISABLE"] = "1"
os.environ["BORS_NO_FETCH_LOOPS"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.path.insert(0, ROOT)

import sqlite3  # noqa: E402

import api.chart as ch  # noqa: E402
import candle_contract  # noqa: E402


def safe(sym):
    return sym.replace("/", "_").replace("\\", "_")


def pack_symbols():
    syms = set()
    for line in open(os.path.join(PACK, "factors.jsonl"), encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("symbol"):
            syms.add(str(r["symbol"]))
    return syms


def db_modes():
    con = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\", "/"), uri=True)
    ae = {r[0] for r in con.execute("SELECT DISTINCT symbol FROM adjust_events")}
    con.close()
    return ae


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
    candles = []
    for r in rows:
        ck = candle_contract.from_db_row(r)
        if ck is not None:
            candles.append(ck)
    candles, _v, _r = ch._merge_session_backfill(
        candles, [], [], ch._session_backfill(symbol), descending=False)
    return candles


def main():
    only = sys.argv[1:] or None
    os.makedirs(OUT, exist_ok=True)
    symbols = sorted((pack_symbols() | db_modes()) if not only else only)
    print("symbols:", len(symbols))
    t0 = time.time()
    summary = {}
    for i, sym in enumerate(symbols, 1):
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
                     "source": e.get("source")}
                    for e in applied],
                "rejected_count": len(rejected) + len(false_rej),
                "chain_complete": (chain or {}).get("complete"),
                "chain_anchored_last": (chain or {}).get("anchored_last"),
                "coverage": cov,
            }
        except Exception as exc:  # keep going; report the failure per symbol
            rec = {"symbol": sym, "status": "error", "error": "%s: %s" % (
                type(exc).__name__, exc)}
        summary[sym] = rec
        with gzip.open(os.path.join(OUT, safe(sym) + ".json.gz"), "wt",
                       encoding="utf-8") as fh:
            json.dump(rec, fh, ensure_ascii=False)
        if i % 100 == 0:
            print("  %d/%d (%.1fs)" % (i, len(symbols), time.time() - t0), flush=True)
    ok = sum(1 for r in summary.values() if r["status"] == "ok")
    err = sum(1 for r in summary.values() if r["status"] == "error")
    total_events = sum(len(r.get("applied_events") or []) for r in summary.values())
    pre2020 = sum(1 for r in summary.values()
                  for e in (r.get("applied_events") or []) if e["date"] < "2020-01-01")
    out = {
        "schema": "phase49-finalization-canonical-dump-v1",
        "db": os.path.relpath(DB, ROOT).replace("\\", "/"),
        "db_sha256": ch.__dict__.get("_DB_SHA", ""),
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
                           } for k, v in summary.items()},
    }
    with open(os.path.join(ROOT, "_audit", "phase49-finalization", "evidence",
                           "canonical-summary.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)
    print("CANONICAL_DUMP:", "OK" if err == 0 else "WITH_ERRORS",
          "symbols", len(symbols), "ok", ok, "err", err,
          "events", total_events, "pre2020", pre2020)
    return 0 if err == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
