#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""bench_pipeline.py — بنچمارکِ قابلِ تکرارِ مسیرِ تاریخچهٔ کندل (فاز ۴٫۷ §۸).

یک تعریف، سه برچسب:

  B0  کدِ پیش از اصلاحِ فاز ۴٫۷   → `--contract <نسخهٔ کهنهٔ candle_contract.py>`
  B1  کدِ پس از اصلاحِ ingestion  → پیش‌فرض (ماژولِ همین درخت)
  B2  پس از هر بهینه‌سازی         → همان دستورِ B1 رویِ کدِ بهینه‌شده

مراحلِ اندازه‌گیری‌شده برایِ هر نماد (همان مسیری که `/api/chart-db` می‌رود):

  query      خواندنِ `price_history` برایِ یک نماد + حذفِ تکرارِ روز به‌نفعِ
             حجمِ بیشتر (قراردادِ `_fts_resample`؛ `ORDER BY date DESC, volume DESC`)
  normalize  `candle_contract.from_db_row` رویِ هر ردیف (شاملِ `widen`)
  agg_w      تجمیعِ هفتگی با کلیدِ شنبه (هم‌قراردادِ `compare_raw.py`)
  agg_m      تجمیعِ ماهانه با کلیدِ ماهِ جلالی (`wm_calendar`)

`output_sha256` از **اعداد** ساخته می‌شود (نه برچسبِ `src`)، پس تغییرِ یک برچسبِ
provenance هش را عوض نمی‌کند ولی هر تغییرِ عددی — حتی ۱ ریال — عوض می‌کند.
این همان شرطِ پذیرشِ §۸ است: «خروجی پس از بهینه‌سازی یکسان بماند».

    python tools/phase47/bench_pipeline.py --db _audit/phase47/lab/market.db \\
        --symbols-file docs/opportunity-center/phase45/SYMBOLS-30.csv \\
        --out _audit/phase47/bench-b1.json
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import importlib.util
import json
import os
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

DEDUPE_SQL = ("SELECT symbol, date, open, high, low, close, volume, last, value, src "
              "FROM price_history WHERE symbol = ? "
              "ORDER BY date DESC, volume DESC")


def load_contract(path: str | None):
    if not path:
        import candle_contract
        return candle_contract
    spec = importlib.util.spec_from_file_location("phase47_contract_b0", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def week_key(date_str: str) -> str:
    d = dt.date.fromisoformat(date_str[:10])
    delta = (d.weekday() + 2) % 7       # شنبه
    return (d - dt.timedelta(days=delta)).isoformat()


def month_key(date_str: str) -> str:
    import wm_calendar as WMC
    d = dt.date.fromisoformat(date_str[:10])
    jy, jm, _ = WMC.g2j(d.year, d.month, d.day)
    return "%04d-%02d" % (jy, jm)


def aggregate(series, keyf):
    buckets = {}
    for c in series:
        k = keyf(c["date"])
        b = buckets.get(k)
        if b is None:
            buckets[k] = {"open": c["open"], "high": c["high"], "low": c["low"],
                          "close": c["close"], "volume": c["volume"] or 0.0}
        else:
            b["high"] = max(b["high"], c["high"])
            b["low"] = min(b["low"], c["low"])
            b["close"] = c["close"]
            b["volume"] += c["volume"] or 0.0
    return buckets


def pct(values, q):
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return ordered[lo] + (ordered[hi] - ordered[lo]) * frac


def one_symbol(con, contract, sym):
    t0 = time.perf_counter()
    rows = con.execute(DEDUPE_SQL, (sym,)).fetchall()
    t1 = time.perf_counter()
    seen = {}
    for r in rows:                      # حذفِ تکرارِ روز به‌نفعِ حجمِ بیشتر
        if r["date"] not in seen:
            seen[r["date"]] = r
    series = []
    for date in sorted(seen):
        bar = contract.from_db_row(tuple(seen[date]))
        if bar:
            series.append(bar)
    t2 = time.perf_counter()
    agg_w = aggregate(series, week_key)
    t3 = time.perf_counter()
    agg_m = aggregate(series, month_key)
    t4 = time.perf_counter()
    return {
        "symbol": sym, "rows": len(rows), "candles": len(series),
        "weeks": len(agg_w), "months": len(agg_m),
        "t_query": t1 - t0, "t_normalize": t2 - t1,
        "t_agg_w": t3 - t2, "t_agg_m": t4 - t3,
        "t_total": t4 - t0,
        "fingerprint": [(c["symbol"], c["date"], c["open"], c["high"], c["low"],
                         c["close"], c["volume"], c["last"]) for c in series],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--contract", default="")
    ap.add_argument("--symbols-file", default=os.path.join(
        ROOT, "docs", "opportunity-center", "phase45", "SYMBOLS-30.csv"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--passes", type=int, default=3)
    ap.add_argument("--out", default="")
    ap.add_argument("--label", default="B1")
    args = ap.parse_args()

    import sqlite3
    contract = load_contract(args.contract or None)
    con = sqlite3.connect("file:%s?mode=ro" % args.db.replace("\\", "/"), uri=True)
    con.row_factory = sqlite3.Row

    symbols = []
    if args.symbols_file and os.path.exists(args.symbols_file):
        with open(args.symbols_file, encoding="utf-8-sig") as fh:
            symbols = [r["symbol"].strip() for r in csv.DictReader(fh) if r.get("symbol")]
    present = {r[0] for r in con.execute("SELECT DISTINCT symbol FROM price_history")}
    missing = [s for s in symbols if s not in present]
    symbols = [s for s in symbols if s in present]
    if not symbols:
        symbols = [r[0] for r in con.execute(
            "SELECT symbol FROM price_history GROUP BY symbol "
            "ORDER BY COUNT(*) DESC, symbol LIMIT ?", (args.limit or 30,))]
    if args.limit:
        symbols = symbols[:args.limit]

    result = {"label": args.label, "db": os.path.abspath(args.db),
              "contract": os.path.abspath(args.contract) if args.contract else "repo",
              "symbols": symbols, "symbols_missing_from_db": missing,
              "passes": args.passes, "runs": []}

    for p in range(args.passes):
        wall0 = time.perf_counter()
        per = [one_symbol(con, contract, s) for s in symbols]
        wall = time.perf_counter() - wall0
        result["runs"].append({
            "pass": p,
            "wall_s": wall,
            "per_symbol_ms": round(1000.0 * wall / max(len(symbols), 1), 3),
            "candles": sum(x["candles"] for x in per),
        })
        if p == 0:      # گذرِ گرم‌کردن؛ آماری نمی‌شود ولی هش از همین ساخته می‌شود
            fp = hashlib.sha256()
            for x in sorted(per, key=lambda y: y["symbol"]):
                for row in x["fingerprint"]:
                    fp.update(("%s|%s|%.4f|%.4f|%.4f|%.4f|%.4f|%s\n" % (
                        row[0], row[1], row[2] or 0, row[3] or 0, row[4] or 0,
                        row[5] or 0, row[6] or 0,
                        "" if row[7] is None else "%.4f" % row[7])).encode("utf-8"))
            result["output_sha256"] = fp.hexdigest()
            result["candles_total"] = sum(x["candles"] for x in per)
            result["fingerprint_rows"] = sum(len(x["fingerprint"]) for x in per)

    measured = result["runs"][1:] or result["runs"]
    for stage in ("t_query", "t_normalize", "t_agg_w", "t_agg_m", "t_total"):
        vals = [x[stage] * 1000.0 for x in per]
        result.setdefault("stages_ms", {})[stage] = {
            "p50": round(pct(vals, 0.50) or 0, 3),
            "p95": round(pct(vals, 0.95) or 0, 3),
            "p99": round(pct(vals, 0.99) or 0, 3),
            "mean": round(statistics.fmean(vals) if vals else 0, 3),
        }
    totals = [r["wall_s"] * 1000.0 for r in measured]
    result["total_ms"] = {"p50": round(pct(totals, 0.50) or 0, 1),
                          "mean": round(statistics.fmean(totals) if totals else 0, 1),
                          "runs": [round(t, 1) for t in totals]}
    con.close()

    print(json.dumps({k: result[k] for k in ("label", "symbols_missing_from_db",
                                             "candles_total", "output_sha256",
                                             "total_ms") if k in result},
                     ensure_ascii=False, indent=1))
    print("per stage (ms) p50/p95/p99:",
          {k: (v["p50"], v["p95"], v["p99"]) for k, v in result["stages_ms"].items()})
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        print("written", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
