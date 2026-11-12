#!/usr/bin/env python3
"""Emit the chart-package literal-extremes fixture from the extracted rows.

Reuses FIXTURE-ROWS.json (already read out of the pinned capture) so no Persian
symbol is hand-typed and no second capture scan is needed.
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
OUT = os.path.join(ROOT, "backend-go", "internal", "chart",
                   "reference_literal_fixture_test.go")

WANT = ("1999-02-14", "2021-11-30", "2022-02-12")
FIELDS = ("open", "high", "low", "close", "volume")


def gostr(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main():
    with open(SRC, encoding="utf-8") as fh:
        doc = json.load(fh)
    rows = [r for r in doc["rows"].values() if r["date"] in WANT]
    rows.sort(key=lambda r: (r["date"], r["symbol"]))
    assert len(rows) == len(WANT), [r["date"] for r in rows]
    for r in rows:
        t0 = r["type0"]
        assert t0["open"] > t0["high"] or t0["open"] < t0["low"], r

    lines = [
        "package chart",
        "",
        "// Real Rahavard type0 rows whose open sits outside [low, high], copied",
        "// from the pinned capture (bars sha256 " + doc["bars_sha256"][:12] + "...).",
        "// The reference series must reach the chart verbatim.",
        "",
        "var referenceLiteralRows = []struct {",
        "\tsymbol, date                 string",
        "\topen, high, low, close, volume float64",
        "}{",
    ]
    for r in rows:
        t0 = r["type0"]
        lines.append("\t{" + ", ".join(
            [gostr(r["symbol"]), gostr(r["date"])] +
            [repr(float(t0[f])) for f in FIELDS]) + "},")
    lines += ["}", ""]

    zero = sorted({r["symbol"] for r in rows if r["engine_factor"] is None})
    assert len(zero) == 1, zero
    zsym = zero[0]
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    zcap, zrun, zn = con.execute(
        "SELECT MAX(capture_sha256), MAX(run_id), COUNT(*) FROM reference_raw "
        "WHERE symbol=?", (zsym,)).fetchone()
    zfac = con.execute(
        "SELECT COUNT(*) FROM adjustment_factors WHERE symbol=?", (zsym,)).fetchone()[0]
    con.close()
    assert zfac == 0 and zn > 0 and zcap, (zfac, zn, zcap)
    lines += [
        "// " + zsym + " carries " + str(zn) + " reference rows and zero measured",
        "// events: its coverage must come from the reference series itself.",
        "const referenceZeroEventSymbol = " + gostr(zsym),
        "const referenceZeroEventCapture = " + gostr(zcap),
        "const referenceZeroEventRun = " + gostr(zrun or ""),
        "",
    ]
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))
    subprocess.run(["gofmt", "-w", OUT], check=True)
    print("wrote", OUT, "rows", len(rows), "zero-event", zsym, zn, "capture", zcap)
    for r in rows:
        print(json.dumps({"symbol": r["symbol"], "date": r["date"],
                          "type0": r["type0"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())