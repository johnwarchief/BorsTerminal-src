# -*- coding: utf-8 -*-
"""Simulate the fallback chart (local price_history + apply_basis) before/after repair."""
from __future__ import annotations

import csv
import importlib
import json
import os
import sqlite3
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.environ.get("RA365_R18_CACHE", "D:/BorsTerminal-tmp/ra365_round18")
ART = os.path.join(ROOT, "artifacts", "ra365", "r18")
ORIG = "D:/BorsTerminal-tmp/ra365_round17/market_r17_migrated.db"
REPAIRED = os.path.join(CACHE, "market_r18_repaired.db")
sys.path.insert(0, ROOT)
import candle_contract as CC  # noqa: E402
import price_basis as PB  # noqa: E402

PB.current = lambda: "last"


def eff_open(first, base, high, low, close):
    if first > 0:
        return first
    if base > 0:
        return min(max(base, low), high)
    return close


def status(ref, prod):
    if ref is None or prod is None:
        return "NULL"
    if ref == prod:
        return "EXACT"
    if abs(ref - prod) <= 0.5:
        return "TOL"
    if ref and abs(ref - prod) / abs(ref) <= 0.0005:
        return "ROUNDING"
    return "DIFF"


def run(dbpath, label):
    ref = sqlite3.connect(f"file:{os.path.join(CACHE, 'reference.db')}?mode=ro", uri=True)
    db = sqlite3.connect(f"file:{dbpath}?mode=ro", uri=True)
    out = []
    totals = Counter()
    for line in open(os.path.join(CACHE, "cohort.jsonl"), encoding="utf-8"):
        j = json.loads(line)
        if not str(j.get("adjust_source") or "").startswith("local-db"):
            continue
        sym = j["symbol"]; ins = j["ins_code"]
        rows = db.execute("SELECT symbol,date,open,high,low,close,volume,last,value,src "
                          "FROM price_history WHERE symbol=? ORDER BY date", (sym,)).fetchall()
        candles = [c for c in (CC.from_db_row(r) for r in rows) if c]
        if not candles:
            continue
        meta = PB.apply_basis(candles, copy=True)
        disp = {c["time"]: c for c in meta["candles"]}
        T = {r[0]: r for r in ref.execute(
            "SELECT date,first,high,low,close,volume,base,last FROM tsetmc WHERE ins_code=?",
            (ins,))}
        cnt = Counter()
        for d, c in disp.items():
            t = T.get(d)
            if not t or t[2] <= 0 or t[3] <= 0 or t[4] <= 0:
                continue
            o_eff = eff_open(t[1], t[6], t[2], t[3], t[4])
            hp, lp = CC.widen(o_eff, t[2], t[3], t[4])
            chosen = t[7] if (meta["basis_applied"] == "last" and t[7] > 0) else t[4]
            hc, lc = max(hp, chosen), min(lp, chosen)
            vals = [status(o_eff, c["open"]), status(hc, c["high"]),
                    status(lc, c["low"]), status(chosen, c["close"])]
            cnt["rows"] += 1
            if all(v == "EXACT" for v in vals):
                cnt["row_exact"] += 1
            if all(v in ("EXACT", "TOL") for v in vals):
                cnt["row_tol"] += 1
            if c.get("last") is None and t[7] > 0:
                cnt["last_null"] += 1
        out.append({"symbol": sym, "adjust_source": j.get("adjust_source"),
                    "basis_applied": meta["basis_applied"],
                    "basis_reason": meta.get("basis_reason") or "",
                    "rows": cnt["rows"], "row_exact": cnt["row_exact"],
                    "row_tol": cnt["row_tol"],
                    "row_exact_pct": round(100.0 * cnt["row_exact"] / cnt["rows"], 4)
                    if cnt["rows"] else "",
                    "row_tol_pct": round(100.0 * cnt["row_tol"] / cnt["rows"], 4)
                    if cnt["rows"] else "",
                    "last_null": cnt["last_null"]})
        totals["assets"] += 1
        totals["rows"] += cnt["rows"]; totals["row_exact"] += cnt["row_exact"]
        totals["row_tol"] += cnt["row_tol"]; totals["last_null"] += cnt["last_null"]
        totals["closing_basis"] += meta["basis_applied"] == "closing"
    db.close(); ref.close()
    path = os.path.join(ART, "fallback-display-parity-%s.csv" % label)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader(); w.writerows(out)
    summary = {"label": label, "assets": totals["assets"], "rows": totals["rows"],
               "row_exact": totals["row_exact"], "row_tol": totals["row_tol"],
               "row_exact_pct": round(100.0 * totals["row_exact"] / max(1, totals["rows"]), 4),
               "row_tol_pct": round(100.0 * totals["row_tol"] / max(1, totals["rows"]), 4),
               "last_null": totals["last_null"],
               "closing_basis_assets": totals["closing_basis"]}
    print(json.dumps(summary, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    before = run(ORIG, "before")
    after = run(REPAIRED, "after")
    with open(os.path.join(ART, "fallback-display-parity-summary.json"), "w",
              encoding="utf-8") as f:
        json.dump({"before": before, "after": after}, f, ensure_ascii=False, indent=1)
