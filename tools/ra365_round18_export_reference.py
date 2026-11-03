# -*- coding: utf-8 -*-
"""Export the Round 18 TSETMC raw reference: per-asset registry + full gzip CSV."""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import sqlite3
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.environ.get("RA365_R18_CACHE", "D:/BorsTerminal-tmp/ra365_round18")
ART = os.path.join(ROOT, "artifacts", "ra365", "r18")
DB = os.path.join(CACHE, "reference.db")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    cohort = {}
    for line in open(os.path.join(CACHE, "cohort.jsonl"), encoding="utf-8"):
        j = json.loads(line)
        cohort[j["ins_code"]] = j
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    registry = []
    for ins, j in cohort.items():
        m = con.execute("SELECT rows,first_date,last_date,duplicate_dates,sha256 "
                        "FROM tsetmc_meta WHERE ins_code=?", (ins,)).fetchone()
        trad = con.execute("SELECT COUNT(*) FROM tsetmc WHERE ins_code=? AND high>0 "
                           "AND low>0 AND close>0", (ins,)).fetchone()[0]
        t0 = con.execute("SELECT COUNT(*),MIN(date),MAX(date) FROM type0 WHERE ra_asset_id=?",
                         (j["ra_asset_id"],)).fetchone()
        registry.append({
            "ra_asset_id": j["ra_asset_id"], "symbol": j["symbol"], "ins_code": ins,
            "ra_class": j.get("ra_class"), "paper_type": j.get("paper_type"),
            "tsetmc_rows": m[0] if m else 0,
            "tsetmc_tradable": trad,
            "first_date": m[1] if m else "", "last_date": m[2] if m else "",
            "duplicate_dates": m[3] if m else 0,
            "csv_sha256": m[4] if m else "",
            "type0_rows": t0[0], "type0_first": t0[1] or "", "type0_last": t0[2] or "",
        })
    reg_path = os.path.join(ART, "raw_ohlc_reference.csv")
    with open(reg_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(registry[0]))
        w.writeheader(); w.writerows(registry)
    full_path = os.path.join(ART, "raw_ohlc_reference.csv.gz")
    n = 0
    with gzip.open(full_path, "wt", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source", "ra_asset_id", "symbol", "ins_code", "date", "first",
                    "high", "low", "close", "last", "base", "volume", "value"])
        for ins, j in cohort.items():
            for r in con.execute(
                    "SELECT date,first,high,low,close,last,base,volume,value FROM tsetmc "
                    "WHERE ins_code=? ORDER BY date", (ins,)):
                w.writerow(["tsetmc_csv", j["ra_asset_id"], j["symbol"], ins,
                            r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]])
                n += 1
    con.close()
    manifest = {
        "round": "ra365-r18",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "reference": {
            "source": "TSETMC CDN ClosingPrice/GetClosingPriceDailyListCSV/{insCode}/19900101",
            "fields": ["first", "high", "low", "close", "last", "base", "volume", "value"],
            "meaning": {"first": "first trade", "high": "daily high", "low": "daily low",
                        "close": "official closing (پایانی)", "last": "last trade",
                        "base": "previous close / base <OPEN>", "volume": "volume",
                        "value": "turnover"},
            "rows": n, "assets": len(registry),
            "full_csv_gz": full_path, "full_csv_gz_sha256": sha(full_path),
            "full_csv_gz_bytes": os.path.getsize(full_path),
            "registry_csv": reg_path, "registry_csv_sha256": sha(reg_path),
            "type0": "frozen Rahavard type0 (ref_bars_v2.jsonl), used as an independent check",
        },
        "notes": [
            "This is raw market data; no adjustment factor, event chain or type7 value is applied.",
            "Missing/no-trade rows are present in the reference; the product contract drops them.",
            "JSON route cross-checked 10,539/10,539 rows exact; top=N truncates, top=0 returns all.",
        ],
    }
    with open(os.path.join(ART, "raw-ohlc-reference-manifest.json"), "w",
              encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(json.dumps({"rows": n, "assets": len(registry),
                      "gzip_bytes": manifest["reference"]["full_csv_gz_bytes"],
                      "gzip_sha": manifest["reference"]["full_csv_gz_sha256"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
