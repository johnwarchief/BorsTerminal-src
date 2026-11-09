#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Phase 4.9 chain experiment: fetch a symbol from the local Go API and compare
its cumulative factor chain with the committed full-history reference chain
(فولاد: _audit/RA365-CHAIN-PARITY-FULL-HISTORY-2026-10-18.csv).

Read-only: only GET requests; evidence written under _audit/phase49/continuation/evidence.
"""
import argparse
import csv
import json
import math
import os
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
EVID = os.path.join(ROOT, "_audit", "phase49", "continuation", "evidence")
REF_CSV = os.path.join(ROOT, "_audit", "RA365-CHAIN-PARITY-FULL-HISTORY-2026-10-18.csv")


def api(path, token):
    req = urllib.request.Request(path, headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_ref():
    rows = list(csv.DictReader(open(REF_CSV, encoding="utf-8-sig")))
    return {r["date"]: float(r["ref_factor"]) for r in rows}, rows


def steps_from_factors(factors, tol=0.002):
    """[(date, ratio)] where ratio = factor(date)/factor(prev date)."""
    out = []
    prev = None
    for d in sorted(factors):
        f = factors[d]
        if prev is not None and prev[1] > 0:
            r = f / prev[1]
            if abs(r - 1.0) > tol:
                out.append((d, r))
        prev = (d, f)
    return out


def compare(api_rows, ref_factors, anchor):
    dates = sorted(set(api_rows) & set(ref_factors))
    ours_anchor = api_rows.get(anchor)
    if not ours_anchor:
        # nearest later date
        later = [d for d in api_rows if d >= anchor]
        if not later:
            return None
        anchor = min(later)
        ours_anchor = api_rows[anchor]
    rows = []
    for d in dates:
        if d > anchor:
            continue
        ref = ref_factors[d]
        ours = api_rows[d] / ours_anchor
        if ref <= 0 or ours <= 0:
            continue
        rows.append((d, ref, ours, ours / ref - 1.0))
    if not rows:
        return None
    rel = [abs(r[3]) for r in rows]
    exact = sum(1 for r in rows if abs(r[1] - r[2]) <= 1e-9)
    return {
        "anchor": anchor, "common": len(rows), "exact": exact,
        "max_rel": max(rel), "median_rel": sorted(rel)[len(rel) // 2],
        "le_001": sum(1 for x in rel if x <= 1e-3),
        "le_01": sum(1 for x in rel if x <= 1e-2),
        "le_05": sum(1 for x in rel if x <= 5e-2),
        "gt_05": sum(1 for x in rel if x > 5e-2),
        "first_gap": next((r[0] for r in rows if abs(r[3]) > 1e-9), None),
        "worst": max(rows, key=lambda r: abs(r[3])),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8159")
    ap.add_argument("--symbol", default="فولاد")
    ap.add_argument("--token-file", required=True)
    ap.add_argument("--label", default="authoritative")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    token = open(args.token_file, encoding="ascii").read().strip()
    url = args.api + "/api/chart-db/" + urllib.parse.quote(args.symbol, safe="")
    payload = api(url, token)
    candles = payload.get("candles") or []
    factors = {str(f["time"])[:10]: float(f["factor"]) for f in payload.get("factors") or []}
    api_rows = {str(c["time"])[:10]: factors.get(str(c["time"])[:10], 1.0) for c in candles}
    ref_factors, ref_rows = load_ref()
    ref_steps = steps_from_factors(ref_factors)
    our_steps = steps_from_factors(api_rows)
    report = {
        "label": args.label, "symbol": args.symbol, "api": args.api,
        "api_count": len(candles),
        "api_first": min(api_rows) if api_rows else None,
        "api_last": max(api_rows) if api_rows else None,
        "adjustSource": payload.get("adjustSource"),
        "adjustCapability": payload.get("adjustCapability"),
        "liveInjected": payload.get("liveInjected"),
        "applied_events": len(payload.get("adjustEvents") or []),
        "rejected_events": len(payload.get("adjustRejected") or []),
        "rejected_sample": (payload.get("adjustRejected") or [])[:10],
        "our_steps": [[d, r] for d, r in our_steps],
        "ref_steps": [[d, r] for d, r in ref_steps],
        "compare_vs_ref": compare(api_rows, ref_factors, max(ref_factors)),
    }
    os.makedirs(EVID, exist_ok=True)
    out = args.out or os.path.join(EVID, "chain-%s-%s.json" %
                                   (args.symbol.replace("/", "_"), args.label))
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    c = report["compare_vs_ref"]
    print(json.dumps({"label": args.label, "symbol": args.symbol,
                      "api_count": report["api_count"],
                      "api_first": report["api_first"], "api_last": report["api_last"],
                      "applied": report["applied_events"],
                      "rejected": report["rejected_events"],
                      "our_steps": len(our_steps), "ref_steps": len(ref_steps),
                      "compare": c}, ensure_ascii=False, indent=1))
    print("out:", out)


if __name__ == "__main__":
    main()
