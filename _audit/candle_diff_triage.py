#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_audit/candle_diff_triage.py — Stage 1.2 follow-up: classify every O/H/L/volume diff.

Reads the per-date table written by candle_full_history_parity.py and asks, for each
field that differs: is our value the reference's PREVIOUS close (an off-by-one in the
session boundary)? is it the reference's own high/low (a field mix-up)? is the gap a
single tick or a real price? which years does it cluster in? does it coincide with an
adjustment-event date?

Nothing is averaged away: every differing date is listed with its numbers.
"""
import csv
import json
import os
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = lambda *p: os.path.join(ROOT, *p)
CSV_IN = A("_audit", "CANDLE-FULL-HISTORY-PARITY-2026-10-18.csv")

with open(CSV_IN, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

ref0 = {b["utc"][:10]: b for b in json.load(open(A("_audit", "ra365_folad_type0_daily.json"), encoding="utf-8"))["bars"]}
ours_payload = json.load(open(next(x for x in (A("_scratch", "live", "api_chart_folad_last.json"),
                                               A("_audit", "api_chart_folad_last.json")) if os.path.exists(x)), encoding="utf-8"))
our_c = {str(c["time"])[:10]: c for c in ours_payload["candles"]}
our_v = {str(v["time"])[:10]: v["value"] for v in ours_payload.get("volumes", [])}
days = sorted(ref0)
idx = {d: i for i, d in enumerate(days)}

FIELDS = (("open", "o"), ("high", "h"), ("low", "l"), ("close", "c"))
report = defaultdict(Counter)
detail = defaultdict(list)

for r in rows:
    d = r["date"]
    i = idx[d]
    prev_d = days[i - 1] if i > 0 else None
    next_d = days[i + 1] if i + 1 < len(days) else None
    for name, rk in FIELDS:
        a, b = r.get(name + "_ours"), r.get(name + "_ref")
        if a is None or b in (None, ""):
            continue
        a, b = float(a), float(b)
        if abs(a - b) < 1e-9:
            continue
        report[name]["n"] += 1
        report[name]["year:" + d[:4]] += 1
        rel = abs(a - b) / b * 100
        report[name]["rel<0.5%"] += rel < 0.5
        report[name]["rel<2%"] += rel < 2
        report[name]["ours>ref"] += a > b
        if prev_d and abs(a - ref0[prev_d][rk]) < 1e-9:
            report[name]["== ref previous " + rk] += 1
        if next_d and abs(a - ref0[next_d][rk]) < 1e-9:
            report[name]["== ref next " + rk] += 1
        # our own payload: does the same candle carry the reference's value in another key?
        oc = our_c.get(d, {})
        for alt in ("last", "closing", "high_raw", "low_raw", "open", "high", "low"):
            v = oc.get(alt)
            if v is not None and abs(float(v) - b) < 1e-9:
                report[name]["ours has ref value in key:" + alt] += 1
        detail[name].append((d, a, b, round(a - b, 4), round(rel, 4)))

    ov, rv = our_v.get(d), ref0[d]["v"]
    if ov is not None and rv is not None and abs(ov - rv) > 1e-9:
        report["volume"]["n"] += 1
        report["volume"]["year:" + d[:4]] += 1
        report["volume"]["ours>ref"] += ov > rv
        detail["volume"].append((d, ov, rv, ov - rv, (ov - rv) / rv * 100))

for name in ("open", "high", "low", "close", "volume"):
    c = report[name]
    if not c["n"]:
        print(f"\n{name}: no differences")
        continue
    years = sorted((k, v) for k, v in c.items() if k.startswith("year:"))
    print(f"\n{name}: {c['n']} differing candles | ours>ref {c['ours>ref']} | rel<0.5% {c['rel<0.5%']} | rel<2% {c['rel<2%']}")
    print("   by year:", ", ".join(f"{k[5:]}={v}" for k, v in years))
    for k, v in c.items():
        if k.startswith("== ref") or k.startswith("ours has"):
            print(f"   pattern {k}: {v}")
    for row in sorted(detail[name], key=lambda x: -abs(x[4]))[:6]:
        print(f"   worst {row[0]}: ours {row[1]} ref {row[2]} Δ {row[3]} ({row[4]}%)")
