#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Measure reference revision: today's capture against the frozen snapshot.

The frozen ledger (`_audit/RA365-CANDLE-DIVERGE-2026-10-12.csv`) carries the
reference's adjusted close/high/low/open as they stood on 2026-10-12.  A fresh
capture of the same series, on the same dates, is therefore a second snapshot:
any difference is a revision of the reference, not a product defect and not a
factor change.

This is the separation Round 31 listed as unmeasured ("revision needs two
snapshots").  Output is per symbol: how many common dates, how many still
exact, how many now outside the frozen contract tolerance, and the worst
relative move.

Usage
  python compare_capture.py --capture <rahavard-export.json> \
      --frozen _audit/RA365-CANDLE-DIVERGE-2026-10-12.csv --out <pack dir>
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import r32_evidence as EV  # noqa: E402
import r32_io as IO  # noqa: E402
import r32_schema as S  # noqa: E402

FIELDS = ("o", "h", "l", "c")
TOL_ABS = 0.5
TOL_REL = 1e-6


def capture_series(path, resolution, adjust):
    """{symbol: {date: {o,h,l,c}}} from a capture export."""
    with open(path, encoding="utf-8-sig") as fh:
        doc = json.load(fh)
    out = {}
    for series in doc.get("series") or []:
        if (series.get("resolution") or series.get("timeframe")) != resolution:
            continue
        if series.get("adjust") != adjust:
            continue
        sym = S.normalize_symbol(series.get("symbol"))
        bars = {}
        for b in series.get("bars") or []:
            if not b.get("utc"):
                continue
            bars[str(b["utc"])[:10]] = {
                "o": S.normalize_number(b.get("open")), "h": S.normalize_number(b.get("high")),
                "l": S.normalize_number(b.get("low")), "c": S.normalize_number(b.get("close")),
            }
        out[sym] = bars
    return out, (doc.get("source") or {})


def compare(capture_path, frozen_path, resolution="D", adjust="adjusted", generated_at=None):
    cap, source = capture_series(capture_path, resolution, adjust)
    frozen_pairs = EV.pairs_from_candle_diverge(frozen_path)
    frozen = {}
    for pair in frozen_pairs:
        if pair["timeframe"] != resolution:
            continue
        frozen.setdefault(pair["symbol"], {})[pair["date"]] = pair["ref"]

    per_symbol = []
    for sym in sorted(set(cap) & set(frozen)):
        a, b = cap[sym], frozen[sym]
        common = sorted(set(a) & set(b))
        exact = within = outside = 0
        rels = []
        worst = None
        for d in common:
            ok_all, within_all = True, True
            for f in FIELDS:
                x, y = a[d].get(f), b[d].get(f)
                if x is None or y is None:
                    ok_all = within_all = False
                    continue
                diff = abs(x - y)
                if diff > 1e-9:
                    ok_all = False
                if diff > max(TOL_ABS, TOL_REL * abs(y)):
                    within_all = False
                if y:
                    rels.append(diff / abs(y))
                    if worst is None or diff / abs(y) > worst[1]:
                        worst = (d, diff / abs(y), f, x, y)
            exact += 1 if ok_all else 0
            within += 1 if within_all else 0
            outside += 0 if within_all else 1
        per_symbol.append({
            "symbol": sym,
            "common_dates": len(common),
            "exact": exact,
            "within_contract_tolerance": within,
            "outside_tolerance": outside,
            "outside_pct": round(100.0 * outside / len(common), 4) if common else None,
            "first_common": common[0] if common else None,
            "last_common": common[-1] if common else None,
            "median_rel_diff": round(statistics.median(rels), 12) if rels else None,
            "max_rel_diff": round(max(rels), 12) if rels else None,
            "worst_case": ({"date": worst[0], "rel": round(worst[1], 12), "field": worst[2],
                            "capture": worst[3], "frozen": worst[4]} if worst else None),
        })
    total_common = sum(r["common_dates"] for r in per_symbol)
    total_outside = sum(r["outside_tolerance"] for r in per_symbol)
    return {
        "generated_at": generated_at or S.now_utc(),
        "kind": "reference-revision",
        "resolution": resolution,
        "adjust": adjust,
        "capture": {"path_basename": os.path.basename(capture_path),
                    "captured_at": source.get("captured_at"),
                    "input_sha256": source.get("input_sha256")},
        "frozen": {"path_basename": os.path.basename(frozen_path),
                   "input_sha256": S.sha256_file(frozen_path)},
        "totals": {"symbols": len(per_symbol), "common_dates": total_common,
                   "outside_tolerance": total_outside,
                   "outside_pct": round(100.0 * total_outside / total_common, 4)
                   if total_common else None},
        "per_symbol": per_symbol,
        "note": "a difference here is a revision of the reference between the two "
                "snapshots; it is neither a product defect nor a factor change",
    }


def main():
    ap = argparse.ArgumentParser(description="Reference revision: capture vs frozen snapshot.")
    ap.add_argument("--capture", required=True)
    ap.add_argument("--frozen", required=True)
    ap.add_argument("--resolution", default="D")
    ap.add_argument("--adjust", default="adjusted")
    ap.add_argument("--out", required=True)
    ap.add_argument("--generated-at", default=None)
    a = ap.parse_args()
    result = compare(a.capture, a.frozen, a.resolution, a.adjust, a.generated_at)
    path = IO.write_json(os.path.join(a.out, "capture-vs-frozen-summary.json"), result)
    t = result["totals"]
    print("revision: %d symbols, %d common dates, %d now outside tolerance (%s%%)"
          % (t["symbols"], t["common_dates"], t["outside_tolerance"], t["outside_pct"]))
    for r in result["per_symbol"]:
        print("  %-10s common=%-4d exact=%-4d outside=%-4d max_rel=%s"
              % (r["symbol"], r["common_dates"], r["exact"], r["outside_tolerance"],
                 r["max_rel_diff"]))
    print("wrote %s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main())