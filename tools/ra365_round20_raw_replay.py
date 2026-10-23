# -*- coding: utf-8 -*-
"""Round 20: replay the frozen TSETMC CSV through the production parser.

This is the after-fix raw measurement on a fixed fixture: the same cached CSV
rows the live path consumes, parsed by api.chart._parse_tsetmc_csv (now with
raw H/L preservation), compared field-by-field with Rahavard type0.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sqlite3
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("BORS_NO_FETCH_LOOPS", "1")
import api.chart as CH  # noqa: E402

OUT = os.path.join(ROOT, "artifacts", "ra365", "r20-literal")
CACHE = os.environ.get("RA365_R18_CACHE", "D:/BorsTerminal-tmp/ra365_round18")
PRICE_ABS = 0.5
PRICE_REL_ROUND = 0.0005
FIELDS = ("open", "high_raw", "low_raw", "last", "volume")


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
    ap.add_argument("--csv-dir", default=os.path.join(CACHE, "cache", "tsetmc_csv"))
    ap.add_argument("--samples", type=int, default=200)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    con = sqlite3.connect(f"file:{args.reference}?mode=ro", uri=True)
    counts = Counter()
    before = Counter()
    samples = []
    assets = rows = missing_csv = skipped_not_in_product = parser_skipped_product_dates = 0
    for line in open(args.cohort, encoding="utf-8"):
        rec = json.loads(line)
        product_dates = {c[0] for c in (rec.get("candles") or [])}
        prodmap = {c[0]: c for c in (rec.get("candles") or [])}
        ins = str(rec.get("ins_code") or "")
        csvp = os.path.join(args.csv_dir, ins + ".csv")
        if not ins or not os.path.exists(csvp):
            missing_csv += 1
            continue
        assets += 1
        text = io.open(csvp, encoding="utf-8-sig", errors="replace").read()
        candles, volumes, _ = CH._parse_tsetmc_csv(text)
        pmap = {c["time"]: c for c in candles}
        vmap = {v["time"]: v["value"] for v in volumes}
        refs = con.execute(
            "SELECT date,open,high,low,close,volume FROM type0 WHERE ra_asset_id=?",
            (str(rec["ra_asset_id"]),)).fetchall()
        for z in refs:
            c = pmap.get(z[0])
            if c is None:
                if z[0] in product_dates:
                    parser_skipped_product_dates += 1
                continue
            if z[0] not in product_dates:
                skipped_not_in_product += 1
                continue
            rows += 1
            vals = {
                "open": (z[1], c.get("open")),
                "high_raw": (z[2], c.get("high_raw")),
                "low_raw": (z[3], c.get("low_raw")),
                "last": (z[4], c.get("last")),
                "volume": (z[5], vmap.get(z[0])),
            }
            old = prodmap.get(z[0])
            if old is not None:
                old_vals = {
                    "open": (z[1], old[1]),
                    "high_raw": (z[2], old[7] if old[7] is not None else old[2]),
                    "low_raw": (z[3], old[8] if old[8] is not None else old[3]),
                    "last": (z[4], old[6]),
                    "volume": (z[5], old[9]),
                }
                old_bad = False
                for fld, (ref, prod) in old_vals.items():
                    st = status(ref, prod)
                    before[(fld, st)] += 1
                    before[(fld, "cmp")] += 1
                    if st in ("EXACT", "TOL"):
                        before[(fld, "ok")] += 1
                    else:
                        old_bad = True
                before[("row", "ok")] += 0 if old_bad else 1
                before[("row", "cmp")] += 1
            bad = False
            for fld, (ref, prod) in vals.items():
                st = status(ref, prod)
                counts[(fld, st)] += 1
                counts[(fld, "cmp")] += 1
                if st in ("EXACT", "TOL"):
                    counts[(fld, "ok")] += 1
                else:
                    bad = True
                    if len(samples) < args.samples:
                        samples.append({"symbol": rec.get("symbol"), "date": z[0], "field": fld,
                                        "ref": ref, "prod": prod, "status": st,
                                        "ref_o": z[1], "ref_h": z[2], "ref_l": z[3],
                                        "ref_c": z[4], "prod_o": c.get("open"),
                                        "prod_h": c.get("high"), "prod_l": c.get("low"),
                                        "prod_hr": c.get("high_raw"), "prod_lr": c.get("low_raw"),
                                        "prod_last": c.get("last"), "prod_close": c.get("close")})
            if not bad:
                counts[("row", "ok")] += 1
            counts[("row", "cmp")] += 1
    con.close()
    summary = {"assets": assets, "missing_csv": missing_csv, "rows": rows,
               "skipped_not_in_product": skipped_not_in_product,
               "parser_skipped_product_dates": parser_skipped_product_dates,
               "tolerance": {"abs": PRICE_ABS, "rel": PRICE_REL_ROUND},
               "fields": {}, "row_exact_ok": counts[("row", "ok")],
               "row_exact_ok_pct": round(100.0 * counts[("row", "ok")] / rows, 4) if rows else None,
               "before": {}, "before_row_exact_ok": before[("row", "ok")],
               "before_row_exact_ok_pct": round(100.0 * before[("row", "ok")] / before[("row", "cmp")], 4)
               if before[("row", "cmp")] else None}
    for fld in FIELDS:
        cmp = before[(fld, "cmp")]; ok = before[(fld, "ok")]
        summary["before"][fld] = {
            "compared": cmp, "ok": ok,
            "ok_pct": round(100.0 * ok / cmp, 4) if cmp else None,
            "exact": before[(fld, "EXACT")], "tol": before[(fld, "TOL")],
            "rounding": before[(fld, "ROUNDING")], "diff": before[(fld, "DIFF")],
            "null": before[(fld, "NULL")],
        }
    for fld in FIELDS:
        cmp = counts[(fld, "cmp")]; ok = counts[(fld, "ok")]
        summary["fields"][fld] = {
            "compared": cmp, "ok": ok,
            "ok_pct": round(100.0 * ok / cmp, 4) if cmp else None,
            "exact": counts[(fld, "EXACT")], "tol": counts[(fld, "TOL")],
            "rounding": counts[(fld, "ROUNDING")], "diff": counts[(fld, "DIFF")],
            "null": counts[(fld, "NULL")],
        }
    json.dump(summary, open(os.path.join(OUT, "literal-raw-after-replay-summary.json"), "w",
                            encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "literal-raw-after-replay-samples.csv"), "w",
              encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(samples[0]) if samples else ["symbol"])
        w.writeheader(); w.writerows(samples)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
