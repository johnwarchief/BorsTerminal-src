# -*- coding: utf-8 -*-
"""Round 21: pooled relative-error quantiles over every paired row."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "p21", os.path.join(ROOT, "tools", "ra365_round21_live_parity.py"))
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=P.REF)
    ap.add_argument("--product", default=P.PROD)
    ap.add_argument("--out", default=os.path.join(ROOT, "artifacts", "ra365", "r21"))
    a = ap.parse_args()
    ref_doc, ref = P.load_ref()
    pooled = defaultdict(lambda: defaultdict(list))
    counts = defaultdict(lambda: defaultdict(int))
    for aid, sym in P.ASSETS.items():
        try:
            prod_daily, meta = P.load_product(aid, a.product)
        except FileNotFoundError:
            continue
        if meta.get("priceBasis") != "last":
            continue
        for mode, rtype in (("raw", "type0"), ("adjusted", "type7")):
            for res in ("D", "W"):
                bars = ref.get((aid, rtype, res)) or []
                if not bars:
                    continue
                prod_rows = prod_daily if res == "D" else P.aggregate_weekly(
                    prod_daily, "a_" if mode == "adjusted" else "")
                if res == "D":
                    pm = {r["date"]: r for r in prod_rows}
                    rm = {b["utc"][:10]: b for b in bars}
                    keys = sorted(set(pm) & set(rm))
                else:
                    pm = {P.bucket_key(r["date"]): r for r in prod_rows}
                    rm = {P.bucket_key(b["utc"][:10]): b for b in bars}
                    keys = sorted(set(pm) & set(rm))
                for displayed in (True, False):
                    tag = f"{mode}|{res}|{'displayed' if displayed else 'literal'}"
                    for k in keys:
                        pr = pm[k] if res == "D" else pm[k]
                        rb = rm[k] if res == "D" else rm[k]
                        pv = P.field_values(pr, mode, displayed)
                        rv = P.ref_values(rb)
                        for f in P.FIELDS:
                            e = P.rel_err(rv[f], pv[f])
                            if e is None:
                                counts[tag][f + "_missing"] += 1
                                continue
                            pooled[tag][f].append(e)
                            st = (P.volume_status if f == "v" else P.price_status)(rv[f], pv[f])
                            counts[tag][f + "_" + st] += 1
    out = {}
    for tag, fields in pooled.items():
        out[tag] = {}
        for f, xs in fields.items():
            c = counts[tag]
            n = len(xs)
            out[tag][f] = {
                "n": n,
                "exact_pct": round(100.0 * c[f + "_EXACT"] / n, 4) if n else None,
                "tolerance_pct": round(100.0 * (c[f + "_EXACT"] + c[f + "_TOLERANCE"]) / n, 4) if n else None,
                "rounding_pct": round(100.0 * c[f + "_ROUNDING"] / n, 4) if n else None,
                "median_rel": P.quantile(xs, 0.5), "p90_rel": P.quantile(xs, 0.9),
                "p95_rel": P.quantile(xs, 0.95), "p99_rel": P.quantile(xs, 0.99),
                "max_rel": max(xs),
            }
    with open(os.path.join(a.out, "pooled-errors.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    for tag in sorted(out):
        print(tag, {f: (round(v["tolerance_pct"], 3), round(v["median_rel"] or 0, 6),
                         round(v["p99_rel"] or 0, 6)) for f, v in out[tag].items()})


if __name__ == "__main__":
    main()
