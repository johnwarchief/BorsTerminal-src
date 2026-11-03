# -*- coding: utf-8 -*-
"""Round-5 source-gap recovery register for the 572 SOURCE_GAP_CONFIRMED steps."""
import argparse
import collections
import csv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refonly", required=True)
    ap.add_argument("--v4-steps", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    arrived = set()
    for r in csv.DictReader(open(a.v4_steps, encoding="utf-8-sig")):
        if r.get("kind") == "PAIR":
            arrived.add((r["symbol"], r["ref_date"]))
    rows = []
    for r in csv.DictReader(open(a.refonly, encoding="utf-8-sig")):
        if r["final_status"] != "SOURCE_GAP_CONFIRMED":
            continue
        src = r.get("product_source") or ""
        pa = int(r.get("ledger_pa") or 0)
        sc = int(r.get("ledger_sc") or 0)
        fe = int(r.get("fund_events") or 0)
        if src.startswith("local-"):
            tax = "LOCAL_FALLBACK_TRUNCATED"
            st = ("FIXED_BY_ROUND4_REFRESH" if (r["symbol"], r["ref_date"]) in arrived
                  else "SOURCE_GAP_CONFIRMED")
            act = "fresh live pull" if st.startswith("FIXED") else "retry live source for this symbol"
        elif src in ("base-price-discontinuity", "ledger+base-price-discontinuity"):
            tax = "BASE_GAP_NOT_DETECTED"
            st = "UNVERIFIED:PARSER_OR_THRESHOLD"
            act = "compare raw gap at the date; do not infer an official ratio"
        elif src == "fund-portal":
            tax = "FUND_EVENT_NOT_MATCHED"
            st = "UNVERIFIED:FUND_EVENT_DATE"
            act = "match the fund event date/amount"
        else:
            tax = "NO_OFFICIAL_EVENT"
            st = "SOURCE_GAP_CONFIRMED"
            act = "official archive / preserve source gap"
        rows.append(dict(r, taxonomy=tax, status_round5=st, recovered_by="Round-4 fresh pull" if st.startswith("FIXED") else "",
                         official_ledger_rows=pa + sc + fe, next_action=act))
    with open(a.out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=sorted({k for r in rows for k in r}))
        w.writeheader(); w.writerows(rows)
    print("rows", len(rows))
    print(collections.Counter(r["taxonomy"] for r in rows))
    print(collections.Counter(r["status_round5"] for r in rows))


if __name__ == "__main__":
    main()
