# -*- coding: utf-8 -*-
"""Enrich the 128 stock event pairs with an auditable Round-3 classification.

No engine exception is created here.  The tool answers two questions per pair:
  1) does the official ledger have any row in a +/-5 day window?
  2) is the pair explained by the official/product/reference relationship?
"""
import argparse
import csv
import datetime as dt
import os
import sqlite3
import sys


def _d(s):
    return dt.date.fromisoformat(str(s)[:10])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    con = sqlite3.connect("file:" + a.db + "?mode=ro", uri=True)
    rows = list(csv.DictReader(open(a.pairs, encoding="utf-8-sig")))
    for r in rows:
        sym = r.get("symbol")
        d = _d(r["product_date"])
        lo = int((d - dt.timedelta(days=5)).strftime("%Y%m%d"))
        hi = int((d + dt.timedelta(days=5)).strftime("%Y%m%d"))
        ins_row = con.execute(
            "SELECT ins_code FROM instruments WHERE l_val18=? ORDER BY updated_at DESC LIMIT 1",
            (sym,)).fetchone()
        ins = str(ins_row[0]) if ins_row else ""
        pa = sc = 0
        if ins:
            pa = con.execute(
                "SELECT COUNT(*) FROM price_adjust_events WHERE ins_code=? AND d_even BETWEEN ? AND ?",
                (ins, lo, hi)).fetchone()[0]
            sc = con.execute(
                "SELECT COUNT(*) FROM share_change_events WHERE ins_code=? AND d_even BETWEEN ? AND ?",
                (ins, lo, hi)).fetchone()[0]
        r["ins_code"] = ins
        r["ledger_rows_pa"] = pa
        r["ledger_rows_sc"] = sc
        r["ledger_rows_window"] = pa + sc
        r["pre_ledger_coverage"] = "yes" if d < dt.date(2024, 7, 21) else "no"
        cause = r.get("cause") or ""
        if cause == "NO_OFFICIAL_RATIO_ROW":
            if r["pre_ledger_coverage"] == "yes":
                r["round3_class"] = "SOURCE_GAP_CONFIRMED:PRE_LEDGER_COVERAGE"
                r["round3_action"] = "no official row exists before TSETMC ledger coverage; keep base-gap ratio"
            elif pa + sc == 0:
                r["round3_class"] = "SOURCE_GAP_CONFIRMED:NO_LEDGER_ROW"
                r["round3_action"] = "official ledger has no row in +/-5d; keep base-gap ratio and record gap"
            else:
                r["round3_class"] = "UNRESOLVED:LEDGER_ROW_OUTSIDE_TOLERANCE"
                r["round3_action"] = "inspect ledger ratio/date; do not change engine without a proven rule"
        elif cause == "PRODUCT_USES_OFFICIAL_RATIO_REFERENCE_DIFFERS":
            r["round3_class"] = "REFERENCE_CONTRACT_DIFFERENCE:PRODUCT_MATCHES_OFFICIAL"
            r["round3_action"] = "product follows the official ratio; reference uses a different event input"
        elif cause == "REFERENCE_RATIO_DIFFERS_FROM_OFFICIAL":
            r["round3_class"] = "REFERENCE_CONTRACT_DIFFERENCE:REFERENCE_DIFFERS_FROM_LEDGER"
            r["round3_action"] = "reference differs from the official ledger row; no product change"
        elif cause == "OFFICIAL_ROW_CLOSER_THAN_PRODUCT":
            r["round3_class"] = "UNRESOLVED:COMPOSITE_CAPITAL_EVENT"
            r["round3_action"] = "official rows are capital-increase components (ratios multiply to ~1); no single row is the adjustment ratio"
        else:
            r["round3_class"] = "UNRESOLVED:UNCLASSIFIED"
            r["round3_action"] = "manual review"
    con.close()
    with open(a.out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    print(Counter(r["round3_class"] for r in rows))


if __name__ == "__main__":
    main()
