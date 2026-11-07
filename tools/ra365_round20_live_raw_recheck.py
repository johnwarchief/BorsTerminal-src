# -*- coding: utf-8 -*-
"""Round 20: re-check frozen raw mismatches against the current live chart feed.

Read-only.  It never writes a market DB and never refreshes a reference row.
The frozen R19 field-mismatch artifact supplies the exact comparison key and
reference value; this tool only asks whether the live product row now matches
that same reference value.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("BORS_NO_FETCH_LOOPS", "1")
os.environ.setdefault("BORS_DB", "D:/BorsTerminal-tmp/r19_perf/market_perf.db")
import api.chart as CH  # noqa: E402
CH.DB_PATH = os.environ["BORS_DB"]

ART = os.path.join(ROOT, "artifacts", "ra365", "r20")
SRC = os.path.join(ROOT, "artifacts", "ra365", "r18-rahavard",
                   "rahavard-raw-ohlc-field-mismatches.csv")
CACHE = os.path.join(ART, "live-raw-cache")
OUT = os.path.join(ART, "live-raw-recheck.csv")
SUM = os.path.join(ART, "live-raw-recheck-summary.json")


def tol(ref, live):
    if ref is None or live is None:
        return None
    d = abs(float(ref) - float(live))
    return d <= max(0.5, 1e-6 * abs(float(ref)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--causes", default="HISTORICAL_REVISION,PARSING_OR_TRANSFORM")
    ap.add_argument("--limit-symbols", type=int, default=0)
    ap.add_argument("--pace", type=float, default=0.4)
    args = ap.parse_args()
    os.makedirs(CACHE, exist_ok=True)
    causes = {s.strip() for s in args.causes.split(",") if s.strip()}
    rows = [r for r in csv.DictReader(open(SRC, encoding="utf-8-sig"))
            if r["cause"] in causes]
    bysym = defaultdict(list)
    for r in rows:
        bysym[r["symbol"]].append(r)
    symbols = sorted(bysym)
    if args.limit_symbols:
        symbols = symbols[:args.limit_symbols]
    out = open(OUT, "w", encoding="utf-8-sig", newline="")
    w = csv.writer(out)
    w.writerow(["symbol", "date", "field", "cause", "ref", "frozen_product",
                "live_product", "old_status", "live_status", "live_row_present"])
    counts = Counter()
    for ix, sym in enumerate(symbols, 1):
        cachep = os.path.join(CACHE, sym + ".json")
        data = None
        if os.path.exists(cachep):
            try:
                data = json.load(open(cachep, encoding="utf-8"))
            except Exception:
                data = None
        if data is None:
            try:
                r = CH.get_chart_tsetmc(sym)
                candles = r.get("candles") or []
                vols = {str(v.get("time"))[:10]: v.get("value")
                        for v in (r.get("volumes") or [])}
                data = {"status": r.get("status"), "candles": {
                    str(c.get("time"))[:10]: {
                        "open": c.get("open"), "high_raw": c.get("high_raw"),
                        "low_raw": c.get("low_raw"), "last": c.get("last"),
                        "close": c.get("close"), "volume": c.get("volume", vols.get(str(c.get("time"))[:10])),
                    } for c in candles}}
                json.dump(data, open(cachep, "w", encoding="utf-8"),
                          ensure_ascii=False)
            except Exception as e:
                data = {"status": "ERROR", "error": type(e).__name__ + ":" + str(e)[:120],
                        "candles": {}}
        for r in bysym[sym]:
            fld = "close" if r["field"] == "close_display" else r["field"]
            live = (data.get("candles") or {}).get(r["date"], {}).get(fld)
            if live is None and r["field"] == "volume":
                live = (data.get("candles") or {}).get(r["date"], {}).get("volume")
            ref = r["ref"]
            old_ok = tol(ref, r["prod"])
            live_ok = tol(ref, live)
            counts["rows"] += 1
            counts["old_ok" if old_ok else "old_bad"] += 1
            counts["live_ok" if live_ok else "live_bad"] += 1
            if live_ok and not old_ok:
                counts["closed"] += 1
            if not live_ok and old_ok:
                counts["regressed"] += 1
            w.writerow([sym, r["date"], r["field"], r["cause"], ref, r["prod"],
                        "" if live is None else live,
                        "OK" if old_ok else "BAD",
                        "OK" if live_ok else ("MISSING" if live is None else "BAD"),
                        "yes" if live is not None else "no"])
        out.flush()
        print(f"{ix}/{len(symbols)} {sym} live={data.get('status')} rows={len(bysym[sym])}",
              flush=True)
        time.sleep(args.pace)
    out.close()
    summary = {"causes": sorted(causes), "symbols": len(symbols),
               "rows": counts["rows"], "old_ok": counts["old_ok"],
               "old_bad": counts["old_bad"], "live_ok": counts["live_ok"],
               "live_bad": counts["live_bad"], "closed": counts["closed"],
               "regressed": counts["regressed"]}
    json.dump(summary, open(SUM, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
