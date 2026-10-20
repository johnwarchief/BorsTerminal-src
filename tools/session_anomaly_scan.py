# -*- coding: utf-8 -*-
"""Populate `session_anomalies` from a cross-sectional gap scan.

Qualifying rule (no date is written in code):
  official_symbols == 0
  and product_only_steps >= 10
  and median_abs_ratio_deviation <= 0.02

Those are sessions where many symbols changed base price while the official
ledger has no corporate action and the deviations cluster near 1; the chart
treats them as a session-wide artifact, not as per-symbol events.
"""
import argparse
import csv
import datetime as dt
import io
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--gaps", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    import tsetmc_p0_schema as P0
    con = sqlite3.connect(a.db, timeout=60)
    P0.create_all(con)
    con.execute(P0.SESSION_ANOMALIES)
    built = dt.datetime.now().isoformat(timespec="seconds")
    rows, kept = [], []
    for r in csv.DictReader(open(a.gaps, encoding="utf-8-sig")):
        try:
            off = int(r.get("official_symbols") or 0)
            steps = int(r.get("product_only_steps") or 0)
            mad = float(r.get("median_abs_ratio_deviation") or 1)
        except Exception:
            continue
        rec = dict(r, qualifies=(off == 0 and steps >= 10 and mad <= 0.02))
        rows.append(rec)
        if not rec["qualifies"]:
            continue
        d_even = int(str(r["date"]).replace("-", ""))
        con.execute(
            "INSERT OR REPLACE INTO session_anomalies"
            "(d_even,gap_symbols,official_symbols,product_only_steps,"
            "median_abs_ratio_deviation,cause,evidence,built_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (d_even, int(r.get("gap_symbols") or 0), off, steps, mad,
             "MARKET_WIDE_SESSION_DIFFERENCE",
             f"gap_symbols={r.get('gap_symbols')};official=0;steps={steps};mad={mad}",
             built))
        kept.append(r["date"])
    con.commit()
    con.close()
    with open(a.out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(json.dumps({"qualifying_dates": kept, "rows": len(rows)},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
