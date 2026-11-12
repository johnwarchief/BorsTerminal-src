#!/usr/bin/env python3
"""Read-only extraction of the exact reference rows used as regression fixtures.

The wanted (symbol, date) pairs are selected by SQL from the working cohort DB,
never hand-typed, so no Persian glyph can drift between the fixture and the
capture. type0/type7 values then come straight from the pinned capture.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "dev"))

from symbol_identity import key as symbol_key  # noqa: E402

BARS = os.path.join(
    ROOT, "_audit", "phase49-full-verification", "captures", "bars-all.ndjson.gz")
DB = os.path.join(ROOT, "_audit", "phase49-3", "db", "cohort.db")
EXPECTED = "272336c036d647ed7b2090853c84c3a2d3da6126a0bfae60e987198169b3b14a"

QUERIES = {
    # open outside [low, high] with a non-unit factor: Widen reshapes these.
    "widen_visible": """
        SELECT r.symbol, r.date FROM reference_raw r
        JOIN adjusted_candles a ON a.symbol=r.symbol AND a.date=r.date
        WHERE (r.open>r.high OR r.open<r.low) AND a.factor<>1.0
        ORDER BY ABS(a.factor-1.0) DESC, r.symbol, r.date LIMIT 2""",
    # zero-event symbol rows the engine never materialized.
    "zero_event_open_outside": """
        SELECT symbol, date FROM reference_raw
        WHERE date IN ('2021-11-30','2022-02-12') AND open>high
        ORDER BY date""",
    # sub-rial adjusted price: integer rounding annihilates it.
    "fractional_adjusted": """
        SELECT symbol, date FROM reference_raw
        WHERE date='1996-03-17' AND close=1300 AND volume=2178060""",
}


def main():
    h = hashlib.sha256()
    with open(BARS, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    got = h.hexdigest()
    if got != EXPECTED:
        print(f"PIN MISMATCH {got}")
        return 2

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    want, groups = set(), {}
    for name, q in QUERIES.items():
        pairs = [(r[0], r[1][:10]) for r in con.execute(q)]
        groups[name] = [f"{s}|{d}" for s, d in pairs]
        want.update(pairs)
    factors = {}
    for sym, day in want:
        row = con.execute(
            "SELECT factor FROM adjusted_candles WHERE symbol=? AND date=?",
            (sym, day)).fetchone()
        factors[f"{sym}|{day}"] = row[0] if row else None
    con.close()

    found = {}
    with gzip.open(BARS, "rb") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            sym = str(row.get("symbol") or "")
            day = str(row.get("date") or "")[:10]
            if (sym, day) not in want:
                continue
            if str(row.get("resolution") or "") != "D":
                continue
            found.setdefault((sym, day), {})[str(row.get("type"))] = row

    out = {}
    for (sym, day), types in sorted(found.items()):
        k = f"{sym}|{day}"
        entry = {"symbol": sym, "date": day, "key": symbol_key(sym),
                 "engine_factor": factors.get(k)}
        for t in ("type0", "type7"):
            r = types.get(t)
            entry[t] = None if r is None else {
                f: r.get(f) for f in ("open", "high", "low", "close", "volume")}
        a, b = entry["type0"], entry["type7"]
        entry["implied_factor"] = (
            b["close"] / a["close"] if a and b and a.get("close") else None)
        out[k] = entry

    missing = sorted(f"{s}|{d}" for s, d in want if f"{s}|{d}" not in out)
    dest = os.path.join(HERE, "evidence")
    os.makedirs(dest, exist_ok=True)
    payload = {"bars_sha256": got, "groups": groups, "rows": out,
               "missing": missing}
    with open(os.path.join(dest, "FIXTURE-ROWS.json"), "w", encoding="utf-8",
              newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())