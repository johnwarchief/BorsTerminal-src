#!/usr/bin/env python3
"""Emit a self-contained Go fixture from real Rahavard rows (read-only).

The unit test must assert against the reference's own type7 numbers, so the
fixture carries the symbol's complete measured factor chain plus the raw and
adjusted rows for the dates under test. Nothing is hand-typed: raw/factor rows
come from the pinned working DB and the expected type7 OHLCV comes from the
pinned capture, never from the engine's current output.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import sqlite3
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "dev"))

DB = os.path.join(ROOT, "_audit", "phase49-3", "db", "cohort.db")
BARS = os.path.join(
    ROOT, "_audit", "phase49-full-verification", "captures", "bars-all.ndjson.gz")
BARS_SHA = "272336c036d647ed7b2090853c84c3a2d3da6126a0bfae60e987198169b3b14a"
OUT = os.path.join(ROOT, "backend-go", "internal", "candlebuild",
                   "reference_fixture_test.go")

DATES = ("1999-02-14", "1999-03-02", "2026-11-10")
FIELDS = ("open", "high", "low", "close", "volume")


def gostr(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def num(v):
    return repr(float(v))


def main():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    sym = con.execute(
        "SELECT symbol FROM reference_raw WHERE date=? AND open=1014",
        (DATES[0],)).fetchone()[0]
    raw = con.execute(
        "SELECT date,open,high,low,close,volume FROM reference_raw "
        "WHERE symbol=? AND date IN (?,?,?) ORDER BY date",
        (sym, *DATES)).fetchall()
    adj = dict(con.execute(
        "SELECT date,close FROM reference_adjusted WHERE symbol=? AND date IN (?,?,?)",
        (sym, *DATES)).fetchall())
    fac = con.execute(
        "SELECT date,ratio,kind,revision,capture_sha256 FROM adjustment_factors "
        "WHERE symbol=? ORDER BY date", (sym,)).fetchall()
    con.close()
    assert len(raw) == len(DATES) and len(adj) == len(DATES), (raw, adj)

    h = hashlib.sha256()
    with open(BARS, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    if h.hexdigest() != BARS_SHA:
        print("PIN MISMATCH", h.hexdigest())
        return 2

    cap = {}
    with gzip.open(BARS, "rb") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            if str(row.get("symbol") or "") != sym:
                continue
            day = str(row.get("date") or "")[:10]
            if day not in DATES or str(row.get("resolution") or "") != "D":
                continue
            cap.setdefault(day, {})[str(row.get("type"))] = row
    for d in DATES:
        assert "type0" in cap[d] and "type7" in cap[d], (d, cap.get(d))
        for i, f in enumerate(FIELDS):
            assert float(cap[d]["type0"][f]) == float(raw[DATES.index(d)][i + 1]), (d, f)
        assert float(cap[d]["type7"]["close"]) == float(adj[d]), (d, "close")

    lines = [
        "package candlebuild",
        "",
        "// Real Rahavard rows for " + sym + " from the pinned Phase 4.9.3 capture",
        "// (input sha256 6aec345f817c...). The two 1999 bars have open below low, so",
        "// Widen would reshape them; 2026-11-10 is the chain anchor. Expected values",
        "// are the reference's own type7 OHLCV, not the engine's output.",
        "",
        "const referenceFixtureSymbol = " + gostr(sym),
        "",
        "var referenceFixtureRaw = []struct {",
        "\tdate             string",
        "\topen, high, low, close, volume float64",
        "}{",
    ]
    for d, o, hh, l, c, v in raw:
        lines.append("\t{" + ", ".join([gostr(d)] + [num(x) for x in (o, hh, l, c, v)]) + "},")
    lines += ["}", "",
              "var referenceFixtureAdjustedClose = map[string]float64{"]
    for d in DATES:
        lines.append("\t" + gostr(d) + ": " + num(adj[d]) + ",")
    lines += ["}", "",
              "var referenceFixtureFactors = []struct {",
              "\tdate                    string",
              "\tratio                   float64",
              "\tkind, revision, capture string",
              "}{"]
    for d, r, kind, rev, cp in fac:
        lines.append("\t{" + ", ".join(
            [gostr(d), num(r), gostr(kind or ""), gostr(rev or ""), gostr(cp or "")]) + "},")
    lines += ["}", "",
              "var referenceFixtureType7 = map[string][5]float64{"]
    for d in DATES:
        lines.append("\t" + gostr(d) + ": {" + ", ".join(
            num(cap[d]["type7"][f]) for f in FIELDS) + "},")
    lines += ["}", ""]

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))
    subprocess.run(["gofmt", "-w", OUT], check=True)
    print("wrote", OUT, "| factors", len(fac), "| raw", len(raw))
    print(json.dumps({"symbol": sym, "dates": list(DATES),
                      "bars_sha256": h.hexdigest()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())