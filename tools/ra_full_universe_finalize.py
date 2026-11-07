# -*- coding: utf-8 -*-
"""Join the universe manifest with reference coverage and measured parity.

Usage:
  python tools/ra_full_universe_finalize.py --manifest _audit/universe_manifest.csv \
    --ref _audit/ref_bars.jsonl --parity-dir _audit/out --out _audit/out/universe_manifest_final.csv
"""
import argparse, collections, csv, json, os


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--parity-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    ref = {}
    for line in open(a.ref, encoding="utf-8"):
        r = json.loads(line)
        k = r.get("key") or ""
        if k.startswith("deep|"):
            continue
        aid, typ, res = k.split("|")
        ref.setdefault(aid, {})[f"{typ}_{res}"] = r.get("bars") or []
    parity = {}
    p = os.path.join(a.parity_dir, "parity_symbols.csv")
    if os.path.exists(p):
        for r in csv.DictReader(open(p, encoding="utf-8-sig")):
            parity[r["asset_id"]] = r

    rows = []
    for r in csv.DictReader(open(a.manifest, encoding="utf-8-sig")):
        aid = r.get("ra_asset_id") or ""
        rr = ref.get(aid, {})
        d0, d7, w0 = rr.get("type0_D", []), rr.get("type7_D", []), rr.get("type0_W", [])
        def fl(bars):
            if not bars:
                return "", ""
            keys = [str((b[0] if isinstance(b, list) else b.get("utc")))[:10] for b in bars]
            return min(keys), max(keys)
        rfirst, rlast = fl(d0)
        pr = parity.get(aid, {})
        live = pr.get("product_live_available")
        live = True if live == "True" else (False if live == "False" else None)
        fmax = num(pr.get("factor_max"))
        ref_only = num(pr.get("ref_only_steps")) or 0
        prod_only = num(pr.get("prod_only_steps")) or 0
        const = pr.get("constant_pre_history_offset") == "True"
        functional = pr.get("functional_available")
        if not aid or not d0 or fmax is None:
            factor_status = "REFERENCE_UNAVAILABLE"
        elif live is False:
            factor_status = "PARTIAL_COVERAGE"
        elif fmax <= 0.000001:
            factor_status = "MATCH"
        elif fmax <= 0.0005:
            factor_status = "ROUNDING_ONLY"
        elif fmax <= 0.01:
            factor_status = "NEAR_MATCH"
        elif ref_only > 0:
            factor_status = "UNRESOLVED_EVENT"
        elif const:
            factor_status = "PARTIAL_COVERAGE"
        else:
            factor_status = "MISMATCH"
        pre = pr.get("pre_coverage_candles") or ""
        unres = pr.get("unresolved_events") or ""
        if not aid or not d0:
            coverage_status = "REFERENCE_UNAVAILABLE"
        elif not pr:
            coverage_status = "NOT_COMPARED"
        elif live is False:
            coverage_status = "PRODUCT_LIVE_UNAVAILABLE"
        elif functional == "False" or str(pre) not in ("", "0") or str(unres) not in ("", "0"):
            coverage_status = "PARTIAL_COVERAGE"
        else:
            coverage_status = "COMPLETE"
        if not aid:
            cause = "NO_REFERENCE_DATA"
        elif not d0:
            cause = "REFERENCE_UNAVAILABLE"
        elif not pr:
            cause = "NOT_COMPARED"
        elif live is False:
            cause = "PRODUCT_LIVE_UNAVAILABLE"
        elif fmax is not None and fmax > 0.01 and num(pr.get("factor_norm_max")) is not None and num(pr.get("factor_norm_max")) > 0.01:
            cause = "FACTOR_MISMATCH"
        elif ref_only > 0 and prod_only == 0:
            cause = "REFERENCE_ONLY_STEPS"
        elif prod_only > 0:
            cause = "PRODUCT_ONLY_STEPS"
        elif const and fmax is not None and fmax > 0.01:
            cause = "PRE_HISTORY_OFFSET"
        elif (num(pr.get("step_ratio_mismatch")) or 0) > 0:
            cause = "STEP_RATIO_DIFFERENCE"
        elif functional == "False":
            cause = "COVERAGE_INCOMPLETE"
        else:
            cause = "MATCH"
        row = dict(r)
        row.update({
            "factor_status": factor_status, "coverage_status": coverage_status, "primary_cause": cause,
            "ref_daily_candles": len(d0), "ref_functional_candles": len(d7),
            "ref_weekly_candles": len(w0), "ref_first_date": rfirst, "ref_last_date": rlast,
            "common_daily": pr.get("common_daily", ""), "weekly_common": pr.get("weekly_common", ""),
            "parity_status": pr.get("status", ""), "product_live_available": "" if live is None else str(live),
            "raw_ok_pct": pr.get("raw_ok_pct", ""), "factor_ok_pct": pr.get("factor_ok_pct", ""),
            "factor_norm_ok_pct": pr.get("factor_norm_ok_pct", ""),
            "factor_max": pr.get("factor_max", ""), "factor_norm_max": pr.get("factor_norm_max", ""),
            "func_ok_pct": pr.get("func_ok_pct", ""),
            "ref_only_steps": pr.get("ref_only_steps", ""), "prod_only_steps": pr.get("prod_only_steps", ""),
            "step_ratio_mismatch": pr.get("step_ratio_mismatch", ""),
            "constant_pre_history_offset": pr.get("constant_pre_history_offset", ""),
            "coverage_start": pr.get("coverage_start", ""), "coverage_end": pr.get("coverage_end", ""),
            "pre_coverage_candles": pr.get("pre_coverage_candles", ""),
            "unresolved_events": pr.get("unresolved_events", ""),
            "rows_unmatched": pr.get("rows_unmatched", ""), "rows_total": pr.get("rows_total", ""),
            "typed_events": pr.get("typed_events", ""), "functional_available": pr.get("functional_available", ""),
            "functional_blockers": pr.get("functional_blockers", ""),
            "adjust_source": pr.get("adjust_source", ""), "price_basis": pr.get("basis", ""),
        })
        rows.append(row)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {a.out}: {len(rows)} rows")
    print("factor_status:", dict(collections.Counter(r["factor_status"] for r in rows)))
    print("coverage_status:", dict(collections.Counter(r["coverage_status"] for r in rows)))
    print("primary_cause:", dict(collections.Counter(r["primary_cause"] for r in rows)))


if __name__ == "__main__":
    main()
