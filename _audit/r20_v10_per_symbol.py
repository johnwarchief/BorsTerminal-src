# -*- coding: utf-8 -*-
"""Round 20 diagnostic: per-symbol V10 error levels on the frozen 29-symbol corpus."""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
from api.chart import _factors_from_events, _sharpen_events_with_ledger  # noqa: E402

REF = json.load(open("_audit/ra365_ref_bars.json", encoding="utf-8"))
CORPUS = json.load(open("_audit/ra365_corpus.json", encoding="utf-8"))
BASE = json.load(open("_audit/ra365_product_bars.json", encoding="utf-8"))
TOL = 0.0005
TEHRAN = timezone(timedelta(hours=3, minutes=30))


def td(b):
    s = str(b["utc"]).replace("Z", "+00:00")
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(TEHRAN).date().isoformat()


def q(a, p):
    a = sorted(a)
    return a[min(len(a) - 1, max(0, int(round(p * (len(a) - 1)))))] if a else 0.0


rows = []
for c in CORPUS:
    sym = c["sym"]
    e = REF["bars"].get(f"{sym}|type7|D")
    if not e:
        continue
    rf = {td(b): b["c"] for b in e["bars"] if b.get("c")}
    raw = BASE[sym]["live"].get("adjustEvents") or []
    ev = _sharpen_events_with_ledger(sym, raw)[0]
    cands = BASE[sym]["live"]["candles"]
    ts = sorted(x["time"] for x in cands)
    fac = dict(zip(ts, _factors_from_events(ts, ev)))
    errs = []
    for x in cands:
        d = x["time"]
        if d not in rf or not x.get("last"):
            continue
        pv = x["last"] * fac.get(d, 1.0)
        errs.append((abs(pv - rf[d]) / rf[d], d, rf[d], pv, fac.get(d, 1.0)))
    if not errs:
        continue
    vals = [z[0] for z in errs]
    hit = sum(1 for z in errs if abs(z[3] - z[2]) <= max(z[2] * TOL, 0.6))
    worst = sorted(errs, reverse=True)[:3]
    rows.append((q(vals, 0.5), q(vals, 0.9), max(vals), 100.0 * hit / len(errs), sym,
                 len(errs), len(ev), worst))
rows.sort(reverse=True)
import json as _json
_json.dump([{"symbol": r[4], "bars": r[5], "events": r[6], "within_tol_pct": round(r[3],4), "median_pct": round(100*r[0],4), "p90_pct": round(100*r[1],4), "max_pct": round(100*r[2],4), "worst_date": r[7][0][1], "worst_ref": r[7][0][2], "worst_prod": r[7][0][3], "worst_factor": r[7][0][4]} for r in rows], open("artifacts/ra365/r20-fix/v10-per-symbol.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
print("sym                  n  events  toll%   median%      p90%       max%  worst_date(ref/prod/factor)")
for med, p90, mx, hit, sym, n, ne, worst in rows:
    w = worst[0]
    print(f"{sym:18s} {n:5d} {ne:6d} {hit:7.2f} {100*med:9.4f} {100*p90:10.4f} {100*mx:9.4f}  "
          f"{w[1]} {w[2]:.2f}/{w[3]:.2f}/{w[4]:.6f}")
