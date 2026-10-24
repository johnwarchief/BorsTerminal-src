#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 26: one-event-at-a-time counterfactual on a frozen product snapshot.

For the largest residual factor steps it corrects (RATIO_DIFF), removes
(EXTRA) or adds (REF_ONLY) one step at a time, recomputes the factor chain
with the same contract, and counts the adjusted rows that become equal
(fixed) or stop being equal (broken). Read-only; the original rows stay.

Usage:
  python tools/ra365_round26_counterfactual.py --ref <ref50.json> \
      --product <dir> --steps <steps.csv> --out <dir> [--top 40]
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import adjustment_engine as AE  # noqa: E402

TOL = 0.5
REL = 1e-6


def fnum(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def load_ref(path):
    doc = json.load(open(path, encoding="utf-8"))
    out = {}
    for it in doc["items"]:
        if it.get("type") in ("type0", "type7") and it.get("res") == "D":
            out.setdefault(str(it["asset_id"]), {})[it["type"]] = {
                b["utc"][:10]: fnum(b.get("c")) for b in (it.get("bars") or [])
            }
    return out


def load_product(path):
    d = json.load(open(path, encoding="utf-8"))
    candles = sorted(d.get("candles") or [], key=lambda c: str(c.get("time"))[:10])
    close = {}
    for c in candles:
        date = str(c.get("time"))[:10]
        v = fnum(c.get("close")) or fnum(c.get("closing"))
        if date and v is not None:
            close[date] = v
    fac = {str(f.get("time"))[:10]: fnum(f.get("factor"))
           for f in (d.get("factors") or [])}
    fac = {k: v for k, v in fac.items() if v}
    events = [dict(e) for e in (d.get("adjustEvents") or []) if e.get("date")]
    return d, close, fac, events


def factors_for(dates, events):
    wrapped = []
    for e in events:
        r = fnum(e.get("ratio"))
        if r and r > 0:
            wrapped.append({"date": str(e["date"])[:10],
                            "kind": AE.KIND_SOURCE_RATIO, "ratio": r})
    f, _ = AE.chain_factors(dates, wrapped)
    return f


def score(dates, close, fac, ref_adj, ref_raw):
    ok = 0
    for dt, f in zip(dates, fac):
        if dt not in ref_adj or dt not in close:
            continue
        adj = close[dt] * f
        if abs(adj - ref_adj[dt]) <= max(TOL, REL * abs(ref_adj[dt])):
            ok += 1
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--product", required=True)
    ap.add_argument("--steps", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--top", type=int, default=40)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ref = load_ref(a.ref)
    rows = list(csv.DictReader(open(a.steps, encoding="utf-8-sig")))
    err = defaultdict(int)
    err_path = os.path.join(os.path.dirname(a.steps), "error_rows.csv")
    if os.path.exists(err_path):
        for r in csv.DictReader(open(err_path, encoding="utf-8-sig")):
            err[(r["asset_id"], r["attributed_date"])] += 1
    cand = sorted(rows, key=lambda r: -err.get((r["asset_id"], r["date"]), 0))[:a.top]
    out = []
    cache = {}
    for r in cand:
        aid, date, cls = r["asset_id"], r["date"], r["class"]
        if aid not in cache:
            cache[aid] = load_product(os.path.join(a.product, aid + ".json"))
        doc, close, fac, events = cache[aid]
        dates = sorted(fac)
        t = ref.get(aid) or {}
        t0, t7 = t.get("type0") or {}, t.get("type7") or {}
        ref_adj = {dt: t7[dt] for dt in t7 if t7.get(dt)}
        base_ok = score(dates, close, [fac[d] for d in dates], ref_adj, t0)
        ev = [e for e in events if str(e.get("date"))[:10] != date]
        if cls == "RATIO_DIFF":
            ev.append({"date": date, "ratio": float(r["step_ref"]),
                       "source": "source_ratio"})
        elif cls == "REF_ONLY":
            ev.append({"date": date, "ratio": float(r["step_ref"]),
                       "source": "source_ratio"})
        # EXTRA: ev already removed the date
        new_fac = factors_for(dates, ev)
        new_ok = score(dates, close, new_fac, ref_adj, t0)
        out.append({"asset_id": aid, "symbol": r["symbol"], "date": date,
                    "class": cls, "prod_step": r["step_prod"],
                    "ref_step": r["step_ref"], "attributed_rows": err.get((aid, date), 0),
                    "rows_fixed": max(0, new_ok - base_ok),
                    "rows_broken": max(0, base_ok - new_ok),
                    "net": new_ok - base_ok})
    with open(os.path.join(a.out, "counterfactual.csv"), "w",
              encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader(); w.writerows(out)
    tot = sum(x["net"] for x in out)
    fixed = sum(x["rows_fixed"] for x in out)
    broken = sum(x["rows_broken"] for x in out)
    print(json.dumps({"events": len(out), "fixed": fixed, "broken": broken,
                      "net_sum": tot,
                      "events_positive": sum(1 for x in out if x["net"] > 0),
                      "events_negative": sum(1 for x in out if x["net"] < 0)},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
