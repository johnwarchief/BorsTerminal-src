"""Export the per-symbol validity table for the Phase 4.9 30 and the 7 short-history
symbols straight from the Seed DB's `history_validity` table.

Outputs:
  _audit/phase49-finalization/VALIDITY-30.csv
  _audit/phase49-finalization/VALIDITY-7.csv

No value is computed here; all columns are copied from the Seed DB, which was
filled from the pack manifest and the reference-parity evidence.
"""
import csv
import json
import os
import sqlite3

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", ".."))
SEED = os.path.join(ROOT, "_audit", "phase49-finalization", "seed", "market.db")
BASE = os.path.join(ROOT, "_audit", "phase49-finalization")
COLS = ("symbol", "rows", "first_date", "last_date", "reference_coverage",
        "ref_days", "ref_first", "ref_last", "factor_steps", "factor_verified",
        "factor_reconstructed", "factor_unverified", "raw_open_corrected",
        "factor_parity", "adjusted_max_abs", "status", "notes")


def export(list_path, out_name):
    symbols = [r["symbol"] for r in
               json.load(open(list_path, encoding="utf-8"))]
    con = sqlite3.connect("file:" + SEED.replace("\\", "/") + "?mode=ro", uri=True)
    try:
        con.row_factory = sqlite3.Row
        rows = []
        for sym in symbols:
            r = con.execute("SELECT * FROM history_validity WHERE symbol=?",
                            (sym,)).fetchone()
            if r is None:
                raise SystemExit("seed has no history_validity row for %r" % sym)
            rows.append({k: r[k] for k in COLS})
    finally:
        con.close()
    out = os.path.join(BASE, out_name)
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    print("wrote %s rows=%d" % (out, len(rows)))


def main():
    export(os.path.join(BASE, "rahavard", "symbols30.json"), "VALIDITY-30.csv")
    export(os.path.join(BASE, "rahavard", "symbols7.json"), "VALIDITY-7.csv")


if __name__ == "__main__":
    main()
