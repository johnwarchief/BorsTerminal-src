# -*- coding: utf-8 -*-
"""Universe-closure register for Round 5."""
import argparse
import collections
import csv
import os


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", required=True)
    ap.add_argument("--factors", required=True)
    ap.add_argument("--inventory", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    fac = {r["asset_id"]: r for r in csv.DictReader(open(a.factors, encoding="utf-8-sig"))}
    inv = {}
    if a.inventory and os.path.exists(a.inventory):
        for r in csv.DictReader(open(a.inventory, encoding="utf-8-sig")):
            inv[r["asset_id"]] = r
    rows = []
    for r in csv.DictReader(open(a.symbols, encoding="utf-8-sig")):
        aid = r["asset_id"]
        f = fac.get(aid, {})
        cause = f.get("cause", "UNVERIFIED")
        if cause == "MATCHED":
            st = "MATCHED"
        elif cause.startswith("REFERENCE_SEMANTIC_DIFFERENCE"):
            st = "EXPECTED_SEMANTIC_DIFFERENCE"
        elif cause.startswith("SOURCE_REVISION"):
            st = "EXPECTED_SEMANTIC_DIFFERENCE"
        elif cause == "RAW_PRICE_MISMATCH":
            st = "UNVERIFIED:DATA_QUALITY"
        elif cause == "ADJUSTMENT_FACTOR_MISMATCH":
            st = "UNVERIFIED:ADJUSTMENT"
        else:
            st = "SOURCE_GAP_CONFIRMED"
        rows.append({
            "asset_id": aid, "symbol": r["symbol"], "class": r["class"],
            "basis": r.get("basis"), "product_live": r.get("product_live_available"),
            "raw_ok_pct": r.get("raw_ok_pct"), "factor_near_pct": r.get("factor_near_pct"),
            "factor_norm_near_pct": r.get("factor_norm_near_pct"), "func_ok_pct": r.get("func_ok_pct"),
            "scenario": f.get("scenario"), "cause": cause,
            "functional_status": (inv.get(aid) or {}).get("functional_status"),
            "availability": (inv.get(aid) or {}).get("window_available"),
            "closure_status": st,
            "next_action": ("document reference contract" if st == "EXPECTED_SEMANTIC_DIFFERENCE"
                            else "official archive / source gap" if st == "SOURCE_GAP_CONFIRMED"
                            else "inspect raw/event evidence" if st.startswith("UNVERIFIED")
                            else "—"),
        })
    with open(a.out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print("rows", len(rows), collections.Counter(r["closure_status"] for r in rows))


if __name__ == "__main__":
    main()
