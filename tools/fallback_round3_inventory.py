# -*- coding: utf-8 -*-
"""Classify the 957 Round-2 live-fallback assets after a fresh Round-3 pull."""
import argparse
import csv
import json
import os
from collections import Counter


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", action="append", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    old = {r["symbol"]: r for r in csv.DictReader(open(a.old, encoding="utf-8-sig"))}
    new = {}
    for path in a.new:
        for line in open(path, encoding="utf-8"):
            try:
                j = json.loads(line)
            except Exception:
                continue
            new[j["symbol"]] = j

    rows = []
    for sym, o in old.items():
        j = new.get(sym) or {}
        src = str(j.get("adjustSource") or "")
        candles = j.get("candles") or []
        last = str(candles[0]["time"])[:10] if candles else ""
        if j.get("status") == "success" and not src.startswith("local-"):
            status = "LIVE_RECOVERED"
            cause = "fresh pull succeeded"
        elif o.get("class") == "options":
            status = "DB_FALLBACK"
            cause = "OPTION_NO_LIVE_OR_EXPIRED"
        elif o.get("class") == "stocks":
            status = "DB_FALLBACK"
            cause = "STOCK_NO_LIVE_SINCE_2024_08_24 (delisted/transferred)"
        elif o.get("class") == "etf_funds":
            status = "DB_FALLBACK"
            cause = "FUND_NO_LIVE_SOURCE"
        elif o.get("class") == "bonds":
            status = "DB_FALLBACK"
            cause = "BOND_EXPIRED_OR_NO_LIVE_ROW"
        else:
            status = "DB_FALLBACK"
            cause = "SOURCE_STILL_UNAVAILABLE"
        rows.append({
            "symbol": sym, "asset_id": o.get("asset_id"), "class": o.get("class"),
            "lifecycle": o.get("lifecycle"), "round2_status": o.get("coverage_status"),
            "round3_status": status, "adjust_source": src or "missing",
            "candles": len(candles), "last_candle": last, "root_cause": cause,
        })
    with open(a.out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(Counter(r["round3_status"] for r in rows))
    print(Counter(r["root_cause"] for r in rows if r["round3_status"] == "DB_FALLBACK"))


if __name__ == "__main__":
    main()
