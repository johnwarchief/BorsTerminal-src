#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_audit/candle_full_history_parity.py — Stage 1.1/1.2: full-history candle parity.

Aligns our daily candles with the Rahavard reference BY REAL DATE (never by index),
reports missing / extra / duplicate / mis-stamped candles, then compares Open, High,
Low, Close and Volume per candle over the WHOLE shared history, plus the internal
OHLC invariants of our own series.

Inputs (all on disk, produced by committed harnesses):
  _audit/ra365_folad_type0_daily.json   reference raw   (exchange.asset:453, type0, D)
  _audit/ra365_folad_type7_daily.json   reference adjusted (type7, D)
  _scratch/live/api_chart_folad_last.json  our /api/chart payload (price basis = last)

Outputs:
  _audit/CANDLE-FULL-HISTORY-PARITY-2026-10-18.csv   per-date table
  stdout summary (pasted into the stage report)
"""
import csv
import json
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = lambda *p: os.path.join(ROOT, *p)
CSV_OUT = A("_audit", "CANDLE-FULL-HISTORY-PARITY-2026-10-18.csv")


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


REF0_P = A("_audit", "ra365_folad_type0_daily.json")
REF7_P = A("_audit", "ra365_folad_type7_daily.json")
OURS_P = next(x for x in (A("_scratch", "live", "api_chart_folad_last.json"),
                          A("_audit", "api_chart_folad_last.json")) if os.path.exists(x))

ref0 = load(REF0_P)["bars"]
ref7 = load(REF7_P)["bars"]
ours = load(OURS_P)


def day_of_utc(s):
    """Reference daily bars are stamped 12:29/12:30Z; the calendar date is the key."""
    return str(s)[:10]


ref0_rows, ref0_dupes = {}, Counter()
for b in ref0:
    d = day_of_utc(b["utc"])
    ref0_dupes[d] += 1
    ref0_rows[d] = b
ref7_rows = {day_of_utc(b["utc"]): b for b in ref7}
ref7_dupes = Counter(day_of_utc(b["utc"]) for b in ref7)

our_rows, our_dupes = {}, Counter()
for c in ours["candles"]:
    d = str(c["time"])[:10]
    our_dupes[d] += 1
    our_rows[d] = c
our_vols = {str(v["time"])[:10]: v["value"] for v in ours.get("volumes", [])}
our_factors = {str(f["time"])[:10]: f["factor"] for f in ours.get("factors", [])}

ref_days = set(ref0_rows)
our_days = set(our_rows)
shared = sorted(ref_days & our_days)

print("== 1.1 coverage ==")
print(f"reference daily bars      : {len(ref0)}  (unique dates {len(ref_days)})")
print(f"our daily candles         : {len(ours['candles'])}  (unique dates {len(our_days)})")
print(f"shared dates              : {len(shared)}   {shared[0]} .. {shared[-1]}")
print(f"ref-only dates (we lack)  : {sorted(ref_days - our_days)}")
print(f"ours-only dates (ref lacks): {sorted(our_days - ref_days)}")
print(f"duplicate dates ref0/ref7 : {sum(v - 1 for v in ref0_dupes.values() if v > 1)}/"
      f"{sum(v - 1 for v in ref7_dupes.values() if v > 1)}")
print(f"duplicate dates ours      : {sum(v - 1 for v in our_dupes.values() if v > 1)}")

# ordering / timestamp sanity on our side (payload arrives newest-first; frontend sorts)
seq = [str(c["time"])[:10] for c in ours["candles"]]
mono_desc = all(seq[i] > seq[i + 1] for i in range(len(seq) - 1))
print(f"our payload strictly newest-first: {mono_desc}")
bad_stamp = [d for d in our_days if not (d[:4].isdigit() and len(d) == 10)]
print(f"our malformed dates: {len(bad_stamp)}")
ref_bad = [d for d in ref_days if len(d) != 10 or not d[:4].isdigit()]
print(f"reference malformed dates: {len(ref_bad)}")
# gap detection: weekdays with no candle on either side
missing_ref_only_in_span = [d for d in sorted(ref_days ^ our_days)]
print(f"total symmetric-difference dates: {len(missing_ref_only_in_span)}")

print("\n== 1.2 per-field OHLCV comparison over ALL shared dates ==")
stats = {k: {"n_diff": 0, "max_abs": 0.0, "max_rel": 0.0, "worst": None} for k in ("open", "high", "low", "close", "volume")}
inv_bad = []
rows_out = []
for d in shared:
    o, r = our_rows[d], ref0_rows[d]
    ov = our_vols.get(d)
    vals = {
        "open": (o["open"], r["o"]), "high": (o["high"], r["h"]), "low": (o["low"], r["l"]),
        "close": (o["close"], r["c"]), "volume": (ov, r["v"]),
    }
    line = {"date": d}
    for k, (a, b) in vals.items():
        if a is None or b is None:
            line[k + "_ours"], line[k + "_ref"], line[k + "_diff"] = None, b, None
            continue
        ad, rd = abs(a - b), (abs(a - b) / abs(b) * 100 if b else None)
        line[k + "_ours"], line[k + "_ref"], line[k + "_diff"] = a, b, a - b
        if ad > 1e-9:
            stats[k]["n_diff"] += 1
            if ad > stats[k]["max_abs"]:
                stats[k]["max_abs"], stats[k]["worst"] = ad, d
            if rd is not None and rd > stats[k]["max_rel"]:
                stats[k]["max_rel"] = rd
    lo, hi, op, cl = o["low"], o["high"], o["open"], o["close"]
    if not (lo <= min(op, cl) + 1e-9 and hi >= max(op, cl) - 1e-9 and lo <= hi):
        inv_bad.append(d)
    line["ref_adj"] = ref7_rows[d]["c"] if d in ref7_rows else None
    line["our_factor"] = our_factors.get(d)
    line["ref_factor"] = (ref7_rows[d]["c"] / r["c"]) if (d in ref7_rows and r["c"]) else None
    rows_out.append(line)

for k, s in stats.items():
    print(f"  {k:<7}: differing {s['n_diff']:>5} / {len(shared)}   max|Δ| {s['max_abs']:>14.4f}"
          f"   max|Δ%| {s['max_rel']:>8.4f}   worst date {s['worst']}")
print(f"  our internal OHLC invariant violations: {len(inv_bad)} {inv_bad[:5]}")

with open(CSV_OUT, "w", encoding="utf-8-sig", newline="") as f:
    keys = ["date", "open_ours", "open_ref", "open_diff", "high_ours", "high_ref", "high_diff",
            "low_ours", "low_ref", "low_diff", "close_ours", "close_ref", "close_diff",
            "volume_ours", "volume_ref", "volume_diff", "ref_adj", "our_factor", "ref_factor"]
    w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
    w.writeheader()
    for r in rows_out:
        w.writerow(r)
print(f"\nCSV: {os.path.relpath(CSV_OUT, ROOT)}  rows: {len(rows_out)}")
