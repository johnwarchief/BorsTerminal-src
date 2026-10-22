#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Count SQL statements and wall time per read-only endpoint, in-process.

Purpose: the HTTP benchmark shows *what* is slow; this shows *why* (query
volume, repeated identical SQL, connection setup). It calls the same handler
functions the routes call, with `sqlite3.connect` wrapped to record every
statement. No HTTP server, no writes, no network.

usage:
  BORS_NO_FETCH_LOOPS=1 python tools/performance/query_profile.py \
      --out artifacts/performance/2026-10-22/query-profile.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

_orig_connect = sqlite3.connect
_state = {"enabled": False, "stmts": [], "conns": 0}


def _normalize(sql: str) -> str:
    return re.sub(r"\s+", " ", sql.strip())[:300]


def _traced_connect(*args, **kwargs):
    conn = _orig_connect(*args, **kwargs)
    if _state["enabled"]:
        _state["conns"] += 1

        def _cb(sql):
            _state["stmts"].append(_normalize(sql))
        try:
            conn.set_trace_callback(_cb)
        except Exception:
            pass
    return conn


sqlite3.connect = _traced_connect


def _reset():
    _state["stmts"] = []
    _state["conns"] = 0
    _state["enabled"] = True


def _stop():
    _state["enabled"] = False
    stmts = _state["stmts"]
    counts = {}
    for s in stmts:
        counts[s] = counts.get(s, 0) + 1
    return {
        "queries": len(stmts),
        "connections": _state["conns"],
        "unique_sql": len(counts),
        "top_sql": sorted(counts.items(), key=lambda kv: -kv[1])[:8],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--symbol", default="فولاد")
    ap.add_argument("--runs", type=int, default=2)
    args = ap.parse_args()

    import api.fundamental as F
    import api.market_status as MS
    import api.notifications as NT
    import api.screener as SC
    import api.market as MK
    import api.funnel as FN

    calls = [
        ("get_db (setup only)", lambda: _db_setup()),
        ("fundamental card", lambda: F.get_fundamental(args.symbol)),
        ("fundamental quarters", lambda: F.get_fundamental_quarters(args.symbol)),
        ("fundamental screen", lambda: F.api_fundamental_screen(limit=50)),
        ("screener", lambda: SC.get_screener()),
        ("funnel", lambda: FN._run("trend", [], "standard", {}, {})),
        ("mstat summary", lambda: MS.mstat_summary()),
        ("mstat mainwatch", lambda: MS.mstat_mainwatch("eq_all", "", "vol_b_shares", True, 120)),
        ("mstat treemap", lambda: MS.mstat_treemap("eq_all", "", "volume")),
        ("mstat industries", lambda: MS.mstat_industries()),
        ("mstat board", lambda: MS.mstat_board() if hasattr(MS, "mstat_board") else None),
        ("notifications sources", lambda: NT.notifications_sources()),
        ("market sync-state", lambda: MK.market_sync_state()),
    ]

    out = {"symbol": args.symbol, "runs": args.runs, "calls": {}}
    for name, fn in calls:
        rows = []
        for i in range(args.runs):
            _reset()
            t0 = time.perf_counter()
            err = None
            try:
                fn()
            except Exception as e:  # noqa: BLE001
                err = f"{type(e).__name__}: {e}"
                traceback.print_exc()
            wall = (time.perf_counter() - t0) * 1000.0
            meta = _stop()
            meta["wall_ms"] = round(wall, 1)
            meta["error"] = err
            rows.append(meta)
            print(f"{name:<24} run{i + 1}: {meta['queries']:>4} queries  "
                  f"{meta['connections']:>2} conns  {meta['wall_ms']:>8.1f} ms"
                  + (f"  ERROR {err}" if err else ""))
        out["calls"][name] = rows

    path = args.out if os.path.isabs(args.out) else os.path.join(ROOT, args.out)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"wrote {path}")
    return 0


def _db_setup():
    from api._core import get_db
    conn = get_db()
    conn.close()


if __name__ == "__main__":
    sys.exit(main())
