# -*- coding: utf-8 -*-
"""Round 20: freeze the single raw-field witness used in the report."""
from __future__ import annotations

import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
CACHE = "D:/BorsTerminal-tmp/ra365_round18"
OUT = "artifacts/ra365/r20-fix/raw-witness.json"
SYMBOL = "غدشت"
DATE = "2009-01-21"


def main():
    rec = None
    for line in open(os.path.join(CACHE, "cohort.jsonl"), encoding="utf-8"):
        d = json.loads(line)
        if d.get("symbol") == SYMBOL:
            rec = d
            break
    if rec is None:
        raise SystemExit("symbol not found in cohort")
    candle = next(c for c in rec["candles"] if c[0] == DATE)
    csv_row = None
    for ln in open(os.path.join(CACHE, "cache", "tsetmc_csv", rec["ins_code"] + ".csv"),
                   encoding="utf-8-sig"):
        p = ln.strip().split(",")
        if len(p) >= 12 and p[1] == DATE.replace("-", ""):
            csv_row = [float(p[2]), float(p[3]), float(p[4]), float(p[5]), float(p[11])]
            break
    con = sqlite3.connect(f"file:{os.path.join(CACHE, 'reference.db')}?mode=ro", uri=True)
    z = con.execute("SELECT date,open,high,low,close FROM type0 WHERE ra_asset_id=? AND date=?",
                    (str(rec["ra_asset_id"]), DATE)).fetchone()
    con.close()
    out = {"symbol": SYMBOL, "date": DATE,
           "csv_first_high_low_close_last": csv_row,
           "product_before": {"open": candle[1], "high": candle[2], "low": candle[3],
                              "close": candle[4], "last": candle[6],
                              "high_raw": candle[7], "low_raw": candle[8]},
           "type0": {"open": z[1], "high": z[2], "low": z[3], "close": z[4]} if z else None}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
