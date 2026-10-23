# -*- coding: utf-8 -*-
"""Round 20: literal raw/type0 parity, without the widen contract.

The R18 contract compared product high/low with a type0 high/low widened by
an independent official CLOSE, so a widen() difference could never show up.
This tool compares the frozen type0 bar field-by-field against the product
snapshot's own raw fields (last, open, high_raw, low_raw, volume), using the
same exact/tolerance protocol as R18.  It is read-only.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "artifacts", "ra365", "r20-literal")
CACHE = os.environ.get("RA365_R18_CACHE", "D:/BorsTerminal-tmp/ra365_round18")
PRICE_ABS = 0.5
PRICE_REL_ROUND = 0.0005
FIELDS = ("open", "high_raw", "low_raw", "last", "close_display", "volume")


def status(ref, prod):
    if prod is None or ref is None:
        return "NULL"
    try:
        ref = float(ref); prod = float(prod)
    except (TypeError, ValueError):
        return "NULL"
    if ref == prod:
        return "EXACT"
    d = abs(ref - prod)
    if d <= PRICE_ABS:
        return "TOL"
    if ref and d / abs(ref) <= PRICE_REL_ROUND:
        return "ROUNDING"
    return "DIFF"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cohort", default=os.path.join(CACHE, "cohort.jsonl"))
    ap.add_argument("--reference", default=os.path.join(CACHE, "reference.db"))
    ap.add_argument("--samples", type=int, default=250)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    con = sqlite3.connect(f"file:{args.reference}?mode=ro", uri=True)
    counts = Counter()
    direction = Counter()
    samples = []
    assets = 0
    rows = 0
    per_asset = []
    with open(args.cohort, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            aid = str(rec["ra_asset_id"])
            refs = {r[0]: r for r in con.execute(
                "SELECT date,open,high,low,close,volume FROM type0 WHERE ra_asset_id=?", (aid,))}
            if not refs:
                continue
            assets += 1
            a_counts = Counter()
            for c in rec.get("candles") or []:
                d = c[0]
                z = refs.get(d)
                if z is None:
                    continue
                rows += 1
                vals = {
                    "open": (z[1], c[1]),
                    "high_raw": (z[2], c[7] if c[7] is not None else c[2]),
                    "low_raw": (z[3], c[8] if c[8] is not None else c[3]),
                    "last": (z[4], c[6]),
                    "close_display": (z[4], c[4]),
                    "volume": (z[5], c[9]),
                }
                row_bad = False
                for fld, (ref, prod) in vals.items():
                    st = status(ref, prod)
                    counts[(fld, st)] += 1
                    a_counts[(fld, st)] += 1
                    if st in ("EXACT", "TOL"):
                        counts[(fld, "ok")] += 1
                    else:
                        row_bad = True
                        if fld in ("high_raw", "low_raw") and len(samples) < args.samples:
                            rh, rl = float(z[2]), float(z[3])
                            ph = float(c[7] if c[7] is not None else c[2])
                            pl = float(c[8] if c[8] is not None else c[3])
                            direction[("high", "ref_below" if rh < ph else "ref_above" if rh > ph else "equal")] += 1
                            direction[("low", "ref_above" if rl > pl else "ref_below" if rl < pl else "equal")] += 1
                            samples.append({
                                "symbol": rec["symbol"], "date": d, "field": fld,
                                "ref": ref, "prod_raw": prod, "status": st,
                                "ref_o": z[1], "ref_h": rh, "ref_l": rl, "ref_c": z[4],
                                "prod_o": c[1], "prod_h_widen": c[2], "prod_l_widen": c[3],
                                "prod_last": c[6], "prod_close": c[4],
                                "prod_h_raw": c[7], "prod_l_raw": c[8],
                                "volume": c[9], "basis": c[10],
                            })
                if not row_bad:
                    counts[("row", "ok")] += 1
            per_asset.append({"symbol": rec["symbol"], "asset_id": aid,
                              "rows": len(rec.get("candles") or []),
                              "high_raw_ok": a_counts[("high_raw", "EXACT")] + a_counts[("high_raw", "TOL")],
                              "low_raw_ok": a_counts[("low_raw", "EXACT")] + a_counts[("low_raw", "TOL")]})
    con.close()
    summary = {"assets": assets, "rows": rows, "tolerance": {"abs": PRICE_ABS, "rel": PRICE_REL_ROUND},
               "fields": {}, "row_exact_ok": counts[("row", "ok")],
               "row_exact_ok_pct": round(100.0 * counts[("row", "ok")] / rows, 4) if rows else None,
               "direction": {f"{k[0]}:{k[1]}": v for k, v in direction.items()}}
    for fld in FIELDS:
        cmp = sum(counts[(fld, s)] for s in ("EXACT", "TOL", "ROUNDING", "DIFF", "NULL"))
        ok = counts[(fld, "ok")]
        summary["fields"][fld] = {
            "compared": cmp,
            "ok": ok,
            "ok_pct": round(100.0 * ok / cmp, 4) if cmp else None,
            "exact": counts[(fld, "EXACT")],
            "tol": counts[(fld, "TOL")],
            "rounding": counts[(fld, "ROUNDING")],
            "diff": counts[(fld, "DIFF")],
            "null": counts[(fld, "NULL")],
        }
    json.dump(summary, open(os.path.join(OUT, "literal-raw-summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "literal-raw-samples.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(samples[0]) if samples else ["symbol"])
        w.writeheader()
        w.writerows(samples)
    per_asset.sort(key=lambda x: (x["high_raw_ok"] / max(1, x["rows"]), x["symbol"]))
    with open(os.path.join(OUT, "literal-raw-worst-assets.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(per_asset[0]) if per_asset else ["symbol"])
        w.writeheader()
        w.writerows(per_asset[:200])
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
