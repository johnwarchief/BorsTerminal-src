# -*- coding: utf-8 -*-
"""Backfill single official sessions that the TSETMC CSV omitted.

Input CSV needs `symbol` (and optionally `date`; default 2023-03-27 because that
is the measured gap in this mission).  The source is the official daily endpoint
`/ClosingPrice/GetClosingPriceDaily/<ins>/<YYYYMMDD>`.  Rows are upserted into
`session_backfill`; the chart merges them into the candle series, never copying
an adjacent day.

Use a copy of the operational DB as --db.
"""
import argparse
import csv
import datetime as dt
import io
import json
import os
import sqlite3
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HDR = {"User-Agent": "Mozilla/5.0", "Referer": "https://tsetmc.com/",
       "Origin": "https://tsetmc.com"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--symbols", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--date", default="2023-03-27")
    ap.add_argument("--retries", type=int, default=3)
    a = ap.parse_args()

    import tsetmc_p0_schema as P0
    con = sqlite3.connect(a.db, timeout=60)
    P0.create_all(con)
    con.execute(P0.SESSION_BACKFILL)
    con.commit()

    rows = list(csv.DictReader(open(a.symbols, encoding="utf-8-sig")))
    fetched_at = dt.datetime.now().isoformat(timespec="seconds")
    d_even = int(a.date.replace("-", ""))
    audit = []
    for rec in rows:
        sym = (rec.get("symbol") or "").strip()
        if not sym:
            continue
        head = con.execute(
            "SELECT ins_code, l_val30 FROM instruments WHERE l_val18=? "
            "ORDER BY updated_at DESC LIMIT 1", (sym,)).fetchone()
        if not head:
            audit.append({"symbol": sym, "status": "INSTRUMENT_NOT_FOUND"})
            continue
        name = head[1]
        variants = con.execute(
            "SELECT ins_code, l_val18 FROM instruments WHERE l_val30=? ORDER BY updated_at DESC",
            (name,)).fetchall() if name else [head]
        for ins, vsym in variants:
            ins = str(ins)
            url = f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDaily/{ins}/{d_even}"
            last_err = ""
            d = None
            for attempt in range(1, a.retries + 1):
                try:
                    r = requests.get(url, headers=HDR, timeout=45)
                    r.raise_for_status()
                    d = (r.json() or {}).get("closingPriceDaily") or {}
                    break
                except Exception as e:
                    last_err = f"{type(e).__name__}: {str(e)[:120]}"
                    time.sleep(1.2 * attempt)
            if not d:
                audit.append({"symbol": vsym, "ins_code": ins, "status": "HTTP_ERROR",
                              "error": last_err})
                continue
            if int(d.get("dEven") or 0) != d_even:
                audit.append({"symbol": vsym, "ins_code": ins, "status": "DATE_MISMATCH",
                              "d_even": d.get("dEven")})
                continue
            close = float(d.get("pClosing") or 0)
            hi = float(d.get("priceMax") or 0)
            lo = float(d.get("priceMin") or 0)
            op = float(d.get("priceFirst") or 0)
            base = float(d.get("priceYesterday") or 0)
            last = float(d.get("pDrCotVal") or 0)
            vol = float(d.get("qTotTran5J") or 0)
            admin = vol == 0 and hi == 0 and lo == 0
            if close <= 0:
                audit.append({"symbol": vsym, "ins_code": ins, "status": "NO_CLOSING_PRICE",
                              "raw": d})
                continue
            con.execute(
                "INSERT OR REPLACE INTO session_backfill"
                "(ins_code,d_even,symbol,open,high,low,close,last,base,volume,source,source_id,fetched_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (ins, d_even, vsym, op, hi, lo, close, last, base, vol,
                 "tsetmc:GetClosingPriceDaily", url, fetched_at))
            audit.append({"symbol": vsym, "ins_code": ins, "d_even": d_even,
                          "open": op, "high": hi, "low": lo, "close": close,
                          "last": last, "base": base, "volume": vol,
                          "status": "ADMIN_NO_TRADE_ROW" if admin else "RESOLVED_OFFICIAL_ROW"})
    con.commit()
    con.close()
    with open(a.out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=sorted({k for r in audit for k in r}))
        w.writeheader()
        w.writerows(audit)
    from collections import Counter
    print(json.dumps(dict(Counter(r.get("status") for r in audit)),
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
