#!/usr/bin/env python3
"""Emit the candlebuild zero-event fixture from the extracted Rahavard rows.

The symbol has reference rows and no measured event at all, so the builder must
materialize it with an identity chain. type0 and type7 are equal on these rows,
which is what makes reference_adjusted consistent with factor 1.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(HERE, "evidence", "FIXTURE-ROWS.json")
DB = os.path.join(ROOT, "_audit", "phase49-3", "db", "cohort.db")
OUT = os.path.join(ROOT, "backend-go", "internal", "candlebuild",
                   "reference_zeroevent_fixture_test.go")
FIELDS = ("open", "high", "low", "close", "volume")


def gostr(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main():
    with open(SRC, encoding="utf-8") as fh:
        doc = json.load(fh)
    rows = [r for r in doc["rows"].values() if r["engine_factor"] is None]
    assert rows, "no zero-event row extracted"
    syms = {r["symbol"] for r in rows}
    assert len(syms) == 1, syms
    sym = rows[0]["symbol"]
    rows.sort(key=lambda r: r["date"])
    for r in rows:
        assert r["type0"] == r["type7"], r
        assert r["implied_factor"] == 1.0, r

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cap, run, n = con.execute(
        "SELECT MAX(capture_sha256), MAX(run_id), COUNT(*) FROM reference_raw "
        "WHERE symbol=?", (sym,)).fetchone()
    nf = con.execute(
        "SELECT COUNT(*) FROM adjustment_factors WHERE symbol=?", (sym,)).fetchone()[0]
    con.close()
    assert nf == 0 and n > 0 and cap, (nf, n, cap)

    lines = [
        "package candlebuild",
        "",
        "// " + sym + ": " + str(n) + " real reference rows, zero measured events.",
        "// type0 == type7 on every row, so the identity chain is the correct answer.",
        "",
        "const zeroEventSymbol = " + gostr(sym),
        "const zeroEventCapture = " + gostr(cap),
        "const zeroEventRun = " + gostr(run or ""),
        "",
        "var zeroEventRows = []struct {",
        "\tdate                         string",
        "\topen, high, low, close, volume float64",
        "}{",
    ]
    for r in rows:
        t0 = r["type0"]
        lines.append("\t{" + ", ".join(
            [gostr(r["date"])] + [repr(float(t0[f])) for f in FIELDS]) + "},")
    lines += ["}", ""]
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))
    subprocess.run(["gofmt", "-w", OUT], check=True)
    print("wrote", OUT, "symbol", sym, "rows", len(rows), "db_rows", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())