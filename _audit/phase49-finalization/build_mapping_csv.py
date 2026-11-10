"""Build the full Rebuild-v2 event mapping CSV (one row per pack factor step).

Input : data/ra365_corrections/ra365-phase49-rebuild-full-v2/factors.jsonl
Output: _audit/phase49-finalization/EVENT-MAPPING-FULL.csv

Each row keeps the provenance needed to audit a step: symbol/ins_code, date,
ratio, cumulative factor, source and validity. No data is invented; fields are
copied verbatim from the pack.
"""
import csv
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", ".."))
PACK = os.path.join(ROOT, "data", "ra365_corrections",
                    "ra365-phase49-rebuild-full-v2", "factors.jsonl")
OUT = os.path.join(ROOT, "_audit", "phase49-finalization",
                   "EVENT-MAPPING-FULL.csv")

COLS = ("symbol", "ins_code", "asset_id", "effective_date", "action", "ratio",
        "prod_ratio", "ref_ratio", "cum_factor_after", "class", "event_sig",
        "method", "confidence", "samples", "max_field_dev", "prov_kind",
        "validity", "source", "suppressed_product_events", "reason")


def main():
    rows = []
    with open(PACK, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    rows.sort(key=lambda r: (r.get("symbol", ""), r.get("effective_date", ""),
                             r.get("ins_code", "")))
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in COLS})
    print("wrote %s rows=%d" % (OUT, len(rows)))


if __name__ == "__main__":
    main()
