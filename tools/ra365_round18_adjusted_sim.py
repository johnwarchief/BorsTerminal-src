# -*- coding: utf-8 -*-
"""Fallback adjusted-OHLC simulation, factors held constant before/after repair.

This is NOT the official adjusted metric. It isolates the effect of the raw
price_history repair on the 148 fallback assets while keeping the existing
product factor array and Rahavard type7 fixed.
"""
from __future__ import annotations

import csv
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.environ.get("RA365_R18_CACHE", "D:/BorsTerminal-tmp/ra365_round18")
ART = os.path.join(ROOT, "artifacts", "ra365", "r18")
ORIG = "D:/BorsTerminal-tmp/ra365_round17/market_r17_migrated.db"
REPAIRED = os.path.join(CACHE, "market_r18_repaired.db")
sys.path.insert(0, ROOT)
import candle_contract as CC  # noqa: E402
import price_basis as PB  # noqa: E402

PB.current = lambda: "last"


def run(ref, dbpath, label):
    db = sqlite3.connect(f"file:{dbpath}?mode=ro", uri=True)
    out = []
    tot = [0, 0]
    for line in open(os.path.join(CACHE, "cohort.jsonl"), encoding="utf-8"):
        j = json.loads(line)
        if not str(j.get("adjust_source") or "").startswith("local-db"):
            continue
        sym = j["symbol"]
        rows = db.execute("SELECT symbol,date,open,high,low,close,volume,last,value,src "
                          "FROM price_history WHERE symbol=? ORDER BY date", (sym,)).fetchall()
        candles = [c for c in (CC.from_db_row(r) for r in rows) if c]
        if not candles:
            continue
        meta = PB.apply_basis(candles, copy=True)
        disp = {c["time"]: c for c in meta["candles"]}
        t7 = {r[0]: r for r in ref.execute(
            "SELECT date,open,high,low,close,volume FROM type7 WHERE ra_asset_id=?",
            (j["ra_asset_id"],))}
        F = {r[0]: r[1] for r in j.get("factors") or []}
        n = ok = 0
        for d, c in disp.items():
            r = t7.get(d); pf = F.get(d)
            if not r or pf is None:
                continue
            vals = []
            for idx in (1, 2, 3, 4):
                a = c[("", "open", "high", "low", "close")[idx]] * pf
                b = r[idx]
                if b is None:
                    continue
                vals.append(abs(a - b) <= max(0.5, 1e-6 * abs(b)))
            if not vals:
                continue
            n += 1; ok += all(vals)
        out.append({"symbol": sym, "rows": n, "row_ok": ok,
                    "row_ok_pct": round(100.0 * ok / n, 4) if n else ""})
        tot[0] += n; tot[1] += ok
    db.close()
    with open(os.path.join(ART, "fallback-adjusted-parity-%s.csv" % label), "w",
              encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader(); w.writerows(out)
    return {"label": label, "assets": len(out), "rows": tot[0], "row_ok": tot[1],
            "row_ok_pct": round(100.0 * tot[1] / max(1, tot[0]), 4)}


def main():
    ref = sqlite3.connect(f"file:{os.path.join(CACHE, 'reference.db')}?mode=ro", uri=True)
    res = {"before": run(ref, ORIG, "before"),
           "after": run(ref, REPAIRED, "after")}
    ref.close()
    with open(os.path.join(ART, "fallback-adjusted-parity-summary.json"), "w",
              encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
