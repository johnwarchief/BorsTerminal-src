#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_audit/candle_upstream_coverage.py — Stage 1.1: why does our series have fewer candles than upstream?

Compares three date sets for one instrument:
  upstream  cdn.tsetmc.com GetClosingPriceDailyListCSV  (the raw source of truth)
  ours      /api/chart/<symbol>                        (what the chart is drawn from)
  reference Rahavard type0 daily                       (the parity target)

Then characterises every upstream row that we drop, so the drop rule is stated with
numbers instead of guessed. Read-only; the upstream CSV is cached under _scratch.
"""
import csv
import io
import json
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = lambda *p: os.path.join(ROOT, *p)
INS = os.environ.get("BORS_INS", "46348559193224090")   # فولاد مبارکه اصفهان
CACHE = A("_scratch", "live", "tsetmc_closing_daily_folad.csv")
OURS = next(x for x in (A("_scratch", "live", "api_chart_folad_last.json"), A("_audit", "api_chart_folad_last.json"))
            if os.path.exists(x))
REF = A("_audit", "ra365_folad_type0_daily.json")


def fetch_upstream():
    if os.path.exists(CACHE):
        return open(CACHE, encoding="utf-8").read()
    url = f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyListCSV/{INS}/19900101"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://cdn.tsetmc.com/"})
    raw = urllib.request.urlopen(req, timeout=60).read().decode("utf-8-sig", "replace")
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    open(CACHE, "w", encoding="utf-8", newline="").write(raw)
    return raw


def iso(d):
    d = str(d).strip().replace("/", "")
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]}" if len(d) >= 8 else d


raw = fetch_upstream()
up = {}
for r in csv.DictReader(io.StringIO(raw)):
    key = iso(r.get("<DTYYYYMMDD>"))
    up[key] = {k.strip("<>"): (v or "").strip() for k, v in r.items() if k and k.strip()}
ours = json.load(open(OURS, encoding="utf-8"))
our_dates = {str(c["time"])[:10] for c in ours["candles"]}
our_vols = {str(v["time"])[:10]: v["value"] for v in ours.get("volumes", [])}
ref_dates = {b["utc"][:10] for b in json.load(open(REF, encoding="utf-8"))["bars"]}

print(f"upstream rows : {len(up)}   {min(up)} .. {max(up)}")
print(f"our candles   : {len(our_dates)}")
print(f"reference     : {len(ref_dates)}")
print(f"upstream-only (we drop)      : {len(set(up) - our_dates)}")
print(f"we-have-but-upstream-lacks   : {len(our_dates - set(up))}")
print(f"reference-only (neither us nor upstream): {sorted(ref_dates - set(up) - our_dates)[:6]}")
print(f"reference-only, present upstream       : {sorted(ref_dates - our_dates)[:6]}  (count {len(ref_dates - our_dates)})")

dropped = sorted(set(up) - our_dates)
from collections import Counter
prof = Counter()
for d in dropped:
    r = up[d]
    def num(k):
        try:
            return float(r.get(k) or 0)
        except ValueError:
            return 0.0
    close, first, high, low, vol, value = num("CLOSE"), num("FIRST"), num("HIGH"), num("LOW"), num("VOL"), num("VALUE")
    if close <= 0:
        prof["close<=0"] += 1
    if first <= 0:
        prof["first<=0"] += 1
    if vol <= 0:
        prof["vol<=0"] += 1
    if value <= 0:
        prof["value<=0"] += 1
    if high <= 0 or low <= 0:
        prof["high/low<=0"] += 1
    if close > 0 and first > 0 and vol > 0:
        prof["ALL POSITIVE (dropped for another reason)"] += 1
print("\ndropped-row profile:", dict(prof))
print("first 8 dropped rows (raw upstream fields):")
for d in dropped[:8]:
    r = up[d]
    print("  ", d, {k: r.get(k) for k in ("FIRST", "OPEN", "HIGH", "LOW", "CLOSE", "LAST", "VOL", "VALUE", "PER")})

# do the numbers we serve match the upstream numbers for shared dates?
mism = {"open": 0, "high": 0, "low": 0, "close": 0, "volume": 0}
worst = {"open": None, "high": None, "low": None, "close": None, "volume": None}
oc = {str(c["time"])[:10]: c for c in ours["candles"]}
for d in sorted(our_dates & set(up)):
    r, c = up[d], oc[d]
    def num(k):
        try:
            return float(r.get(k) or 0)
        except ValueError:
            return 0.0
    pairs = {
        "open": (c["open"], num("OPEN") or num("FIRST")),
        "high": (c["high"], num("HIGH")), "low": (c["low"], num("LOW")),
        "close": (c["close"], num("LAST") or num("CLOSE")),
        "volume": (our_vols.get(d), num("VOL")),
    }
    for k, (a, b) in pairs.items():
        if a is None or b == 0:
            continue
        if abs(a - b) > 1e-6:
            mism[k] += 1
            if worst[k] is None or abs(a - b) > abs(worst[k][1]):
                worst[k] = (d, a - b, a, b)
print("\nours vs UPSTREAM on shared dates (not the reference — the source itself):")
for k in mism:
    print(f"  {k:<7} differing {mism[k]:>4} / {len(our_dates & set(up))}   worst {worst[k]}")
