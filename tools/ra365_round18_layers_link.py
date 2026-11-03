# -*- coding: utf-8 -*-
"""Join Round 17's promoted Factor/OHLC metrics to Round 18 raw parity.

The product snapshot's own factor array is NOT the Round 17 promoted engine, so
it is not used here.  Factor/OHLC come from the R17 promoted per-symbol artifact;
raw comes from the independent R18 measurement.  This keeps each layer from its
authoritative run instead of mixing snapshots.
"""
from __future__ import annotations

import csv
import json
import os
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "artifacts", "ra365", "r18")
R17 = os.path.join(ROOT, "docs", "audit", "ra365-round17")


def f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def main():
    raw = {r["symbol"]: r for r in csv.DictReader(
        open(os.path.join(ART, "raw-ohlc-parity.csv"), encoding="utf-8-sig"))}
    r17 = list(csv.DictReader(
        open(os.path.join(R17, "parity-symbols-promoted-final.csv"), encoding="utf-8-sig")))
    out = []
    for r in r17:
        sym = r["symbol"]; p = raw.get(sym, {})
        fc = int(f(r["factor_cmp"])); fo = int(f(r["factor_ok"])); fn = int(f(r["factor_near"]))
        uc = int(f(r["func_cmp"])); uo = int(f(r["func_ok"]))
        rp = int(f(p.get("row_pairs"))); rex = int(f(p.get("row_contract_exact")))
        row_pct = 100.0 * rex / rp if rp else None
        cok = f(p.get("contract_ok_pct"), None)
        fpct = 100.0 * fo / fc if fc else None
        upct = 100.0 * uo / uc if uc else None
        raw_ok = row_pct is not None and row_pct >= 99.9
        factor_ok = fpct is not None and fpct >= 50.0
        if raw_ok and not factor_ok:
            layer = "RAW_HEALTHY_FACTOR_WEAK"
        elif not raw_ok and factor_ok:
            layer = "RAW_WEAK_FACTOR_HEALTHY"
        elif raw_ok and factor_ok:
            layer = "BOTH_HEALTHY"
        else:
            layer = "BOTH_WEAK"
        out.append({"symbol": sym, "adjust_source": r.get("adjust_source", ""),
                    "raw_pairs": rp, "raw_row_exact": rex,
                    "raw_row_exact_pct": round(row_pct, 4) if row_pct is not None else "",
                    "raw_contract_ok_pct": p.get("contract_ok_pct", ""),
                    "raw_missing_p_product": p.get("missing_p_product", ""),
                    "factor_cmp": fc, "factor_exact": fo, "factor_near": fn,
                    "factor_exact_pct": round(fpct, 4) if fpct is not None else "",
                    "factor_near_pct": round(100.0 * fn / fc, 4) if fc else "",
                    "adj_ohlc_cmp": uc, "adj_ohlc_ok": uo,
                    "adj_ohlc_ok_pct": round(upct, 4) if upct is not None else "",
                    "layer": layer})
    with open(os.path.join(ART, "layer-decomposition.csv"), "w", encoding="utf-8-sig",
              newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader(); w.writerows(out)

    # joint summary weighted by factor dates / OHLC fields, not by asset count
    groups = {}
    for o in out:
        g = groups.setdefault(o["layer"], {"assets": 0, "factor_cmp": 0, "factor_ok": 0,
                                           "adj_cmp": 0, "adj_ok": 0, "raw_pairs": 0,
                                           "raw_exact": 0})
        g["assets"] += 1
        g["factor_cmp"] += o["factor_cmp"]; g["factor_ok"] += o["factor_exact"]
        g["adj_cmp"] += o["adj_ohlc_cmp"]; g["adj_ok"] += o["adj_ohlc_ok"]
        g["raw_pairs"] += o["raw_pairs"]; g["raw_exact"] += o["raw_row_exact"]
    for g in groups.values():
        g["factor_exact_pct"] = round(100.0 * g["factor_ok"] / max(1, g["factor_cmp"]), 4)
        g["adj_ohlc_ok_pct"] = round(100.0 * g["adj_ok"] / max(1, g["adj_cmp"]), 4)
        g["raw_row_exact_pct"] = round(100.0 * g["raw_exact"] / max(1, g["raw_pairs"]), 4)
    summary = {
        "cohort": "R17 promoted, 2,595 assets",
        "factor_layer": {"cmp": sum(o["factor_cmp"] for o in out),
                         "exact": sum(o["factor_exact"] for o in out)},
        "adjusted_ohlc": {"cmp": sum(o["adj_ohlc_cmp"] for o in out),
                          "ok": sum(o["adj_ohlc_ok"] for o in out)},
        "raw": {"pairs": sum(o["raw_pairs"] for o in out),
                "exact": sum(o["raw_row_exact"] for o in out)},
        "groups": groups,
    }
    summary["factor_layer"]["exact_pct"] = round(
        100.0 * summary["factor_layer"]["exact"] / max(1, summary["factor_layer"]["cmp"]), 4)
    summary["adjusted_ohlc"]["ok_pct"] = round(
        100.0 * summary["adjusted_ohlc"]["ok"] / max(1, summary["adjusted_ohlc"]["cmp"]), 4)
    summary["raw"]["exact_pct"] = round(
        100.0 * summary["raw"]["exact"] / max(1, summary["raw"]["pairs"]), 4)
    with open(os.path.join(ART, "layer-joint-summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False))

    # regression symbols: raw vs factor vs OHLC
    reg = []
    seen = set()
    for name in ("regression-status.csv", "regression-status-ohlc.csv"):
        for r in csv.DictReader(open(os.path.join(R17, name), encoding="utf-8-sig")):
            key = (r.get("symbol"), r.get("metric"))
            if key in seen:
                continue
            seen.add(key)
            sym = r.get("symbol"); o = next((x for x in out if x["symbol"] == sym), None)
            reg.append({"symbol": sym, "metric": r.get("metric"),
                        "r17_status": r.get("status"), "r17_note": r.get("note"),
                        "raw_row_exact_pct": o["raw_row_exact_pct"] if o else "",
                        "raw_contract_ok_pct": o["raw_contract_ok_pct"] if o else "",
                        "factor_exact_pct": o["factor_exact_pct"] if o else "",
                        "adj_ohlc_ok_pct": o["adj_ohlc_ok_pct"] if o else "",
                        "layer": o["layer"] if o else "NOT_IN_COHORT"})
    with open(os.path.join(ART, "regression-layer-link.csv"), "w", encoding="utf-8-sig",
              newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(reg[0]))
        w.writeheader(); w.writerows(reg)
    print("regression rows", len(reg),
          Counter(x["layer"] for x in reg))


if __name__ == "__main__":
    main()
