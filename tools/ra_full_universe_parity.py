# -*- coding: utf-8 -*-
"""ra_full_universe_parity.py — full-universe Rahavard365 parity measurement.

Usage:
  python tools/ra_full_universe_parity.py --manifest _audit/universe_manifest.csv \n    --ref _audit/ref_bars.jsonl --product-live _audit/product_live_final.jsonl \n    --product-db _audit/product_bars.jsonl --out-dir _audit/out

Compares daily and weekly raw OHLCV, the canonical adjustment factor (absolute and
normalized to the first common date), functional OHLC, per-event step chains, and
coverage. Pre-registered tolerances are in the module header.

Original docstring:
Full-universe Rahavard365 parity measurement.

Pre-registered tolerances (fixed before looking at full results):
  price MATCH            |a-b| <= max(0.5 rial, 1e-6*|b|)
  price ROUNDING_ONLY    relative <= 0.05% or absolute <= 1 rial
  factor MATCH           relative <= 1e-6
  factor ROUNDING_ONLY   relative <= 0.05%
  factor NEAR_MATCH      relative <= 1%
  factor MISMATCH        relative > 1%
  step detection         |factor(d)/factor(prev)-1| > 0.05%
  step date alignment    +/-5 calendar days
  step ratio alignment   |ratio/ref_ratio-1| <= 20% (for pairing only)

Raw daily uses product basis=last (live path). DB path (basis=closing) is measured
separately and never mixed into the primary raw metric.
"""
import argparse, csv, datetime as dt, io, json, os, statistics, sys
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

PRICE_MATCH_ABS = 0.5
PRICE_ROUND_ABS = 1.0
PRICE_ROUND_REL = 0.0005
FACTOR_MATCH = 1e-6
FACTOR_ROUND = 0.0005
FACTOR_NEAR = 0.01
STEP_TOL = 0.0005
STEP_DAYS = 5
STEP_RATIO_PAIR = 0.20
# Session-wide source difference measured on 2026-10-20: on this date the reference
# close differs from TSETMC's LAST/open for many symbols while OHLC otherwise agrees.
# It is classified as explained, never as a silent match.
KNOWN_SESSION_DIFF_DATES = {"2020-05-26"}


def pct(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    i = min(len(xs) - 1, max(0, int(q * (len(xs) - 1) + 0.5)))
    return xs[i]


def rel(a, b):
    if b in (None, 0):
        return None
    return abs(a - b) / abs(b)


def load_ref(path):
    out = {}
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        key = r.get("key") or ""
        if key.startswith("deep|"):
            continue
        bars = []
        for b in r.get("bars") or []:
            if isinstance(b, list):
                u, o, h, l, c, v = (list(b) + [None] * 6)[:6]
            else:
                u = b.get("utc"); o = b.get("open"); h = b.get("high"); l = b.get("low"); c = b.get("close"); v = b.get("volume")
            d = str(u)[:10]
            try:
                bars.append({"date": d, "open": float(o), "high": float(h), "low": float(l),
                             "close": float(c), "volume": float(v or 0)})
            except (TypeError, ValueError):
                continue
        out[key] = {"status": r.get("status"), "bars": bars, "error": r.get("error")}
    return out


def load_product(path):
    out = {}
    if not path or not os.path.exists(path):
        return out
    for line in open(path, encoding="utf-8"):
        try:
            p = json.loads(line)
        except Exception:
            continue
        out[p.get("symbol")] = p
    return out


def product_daily(p):
    """symbol -> {date: raw candle} using the basis each candle declares."""
    candles = p.get("candles") or []
    vols = {str(v.get("time"))[:10]: float(v.get("value") or 0) for v in p.get("volumes") or []}
    out = {}
    for c in candles:
        d = str(c.get("time"))[:10]
        basis = c.get("basis") or p.get("priceBasis") or "closing"
        close = c.get("last") if (basis == "last" and c.get("last") is not None) else c.get("closing")
        vol = c.get("volume")
        if vol is None:
            vol = vols.get(d, 0)
        out[d] = {
            "open": float(c.get("open") or 0), "high": float(c.get("high") or 0),
            "low": float(c.get("low") or 0), "close": float(close or 0),
            "closing": float(c.get("closing") or 0),
            "last": None if c.get("last") is None else float(c.get("last")),
            "volume": float(vol or 0), "basis": basis,
        }
    return out


def factors_of(p):
    return {str(f.get("time"))[:10]: float(f.get("factor") or 1.0) for f in p.get("factors") or []}


def agg_weekly(daily):
    buckets = defaultdict(list)
    for d, c in daily.items():
        try:
            day = dt.date.fromisoformat(d)
        except ValueError:
            continue
        start = day - dt.timedelta(days=(day.weekday() - 5) % 7)
        buckets[start.isoformat()].append((d, c))
    out = {}
    for k, items in buckets.items():
        items.sort(key=lambda x: x[0])
        first = items[0][1]; last = items[-1][1]
        out[k] = {
            "open": first["open"], "high": max(x["high"] for _, x in items),
            "low": min(x["low"] for _, x in items), "close": last["close"],
            # Rahavard weekly volume is the SUM of daily volumes (measured 384/385
            # on the deep pilot); the product's aggregateCandles also sums.
            "volume": sum(x["volume"] for _, x in items),
            "volume_first": first["volume"], "volume_sum": sum(x["volume"] for _, x in items),
            "ndays": len(items), "end": items[-1][0],
        }
    return out


def price_field_status(ref, prod, field, basis, close_ok):
    if ref is None and prod is None:
        return None
    if ref is None:
        return "MISSING_REFERENCE_CANDLE"
    if prod is None:
        return "MISSING_PRODUCT_CANDLE"
    ae = abs(ref - prod)
    if ae <= max(PRICE_MATCH_ABS, 1e-6 * abs(ref)):
        return "MATCH"
    r = rel(prod, ref)
    if r is not None and (r <= PRICE_ROUND_REL or ae <= PRICE_ROUND_ABS):
        return "ROUNDING_ONLY"
    if field in ("high", "low") and close_ok:
        return "SESSION_HIGH_LOW_DIFFERENCE"
    if basis == "closing":
        return "PRICE_BASIS_MISMATCH"
    if r is not None and r <= 0.05:
        return "SOURCE_DATA_MISMATCH"
    return "UNRESOLVED"


def factor_status(diff):
    if diff is None:
        return "REFERENCE_UNAVAILABLE"
    if diff <= FACTOR_MATCH:
        return "MATCH"
    if diff <= FACTOR_ROUND:
        return "ROUNDING_ONLY"
    if diff <= FACTOR_NEAR:
        return "NEAR_MATCH"
    return "MISMATCH"


def steps(dates, fac):
    out = []
    for i in range(1, len(dates)):
        a, b = fac[i - 1], fac[i]
        if not a or not b:
            continue
        r = b / a
        if abs(r - 1.0) > STEP_TOL:
            out.append({"date": dates[i], "inv_ratio": r, "ratio": 1.0 / r})
    return out


def compare_series(prod_daily, prod_fac, ref0, ref7, basis, prod_func=None):
    """Per-date raw/factor/functional comparison on common dates."""
    r0 = {b["date"]: b for b in ref0}
    r7 = {b["date"]: b for b in ref7}
    common = sorted(set(prod_daily) & set(r0))
    field_counts = Counter(); field_samples = []
    factor_samples = []; func_samples = []
    close_diffs = []; factor_diffs = []
    func_counts = Counter(); func_diffs = []
    factor_by_date = {}
    for d in common:
        pd = prod_daily[d]; rd = r0[d]
        cstat = price_field_status(rd["close"], pd["close"], "close", basis, True)
        if d in KNOWN_SESSION_DIFF_DATES and cstat not in ("MATCH", "ROUNDING_ONLY"):
            cstat = "OTHER_EXPLAINED"
        field_counts[("close", cstat)] += 1
        close_diffs.append(rel(pd["close"], rd["close"]))
        close_ok = cstat in ("MATCH", "ROUNDING_ONLY")
        for f in ("open", "high", "low"):
            st = price_field_status(rd[f], pd[f], f, basis, close_ok)
            if d in KNOWN_SESSION_DIFF_DATES and st not in ("MATCH", "ROUNDING_ONLY"):
                st = "OTHER_EXPLAINED"
            field_counts[(f, st)] += 1
        vst = "MATCH" if pd["volume"] == rd["volume"] else (
            "ROUNDING_ONLY" if abs(pd["volume"] - rd["volume"]) <= 0.5 else
            "SOURCE_DATA_MISMATCH" if (rel(pd["volume"], rd["volume"]) or 9) <= 0.05 else "UNRESOLVED")
        field_counts[("volume", vst)] += 1
        if cstat not in ("MATCH", "ROUNDING_ONLY") and len(field_samples) < 200:
            field_samples.append({"date": d, "field": "close", "status": cstat,
                                  "ref": rd["close"], "prod": pd["close"],
                                  "closing": pd.get("closing"), "last": pd.get("last"), "basis": basis})
        f = prod_fac.get(d)
        if d in r7 and rd["close"]:
            rf = r7[d]["close"] / rd["close"]
            pf = f
            fd = rel(pf, rf) if pf is not None else None
            factor_diffs.append(fd)
            factor_by_date[d] = (rf, pf)
            fst = factor_status(fd)
            field_counts[("factor", fst)] += 1
            if fst not in ("MATCH", "ROUNDING_ONLY") and len(factor_samples) < 200:
                factor_samples.append({"date": d, "field": "factor", "status": fst,
                                       "ref": rf, "prod": pf, "basis": basis})
            if pf is not None:
                fsrc = prod_func.get(d) if prod_func else None
                for fld in ("open", "high", "low", "close"):
                    a = fsrc[fld] if fsrc else pd[fld] * pf
                    b = r7[d][fld]
                    st = price_field_status(b, a, fld, "adjusted", True)
                    func_counts[(fld, st)] += 1
                    func_diffs.append(rel(a, b))
                    if st not in ("MATCH", "ROUNDING_ONLY") and len(func_samples) < 200:
                        func_samples.append({"date": d, "field": "func_" + fld, "status": st,
                                             "ref": b, "prod": a, "basis": basis})
    # missing dates on each side (outside the other's range)
    prod_dates = set(prod_daily); ref_dates = set(r0)
    if prod_dates and ref_dates:
        pmin, pmax = min(prod_dates), max(prod_dates)
        rmin, rmax = min(ref_dates), max(ref_dates)
        for d in ref_dates - prod_dates:
            if d < pmin:
                field_counts[("close", "PRODUCT_RANGE_STARTS_LATER")] += 1
            elif d > pmax:
                field_counts[("close", "PRODUCT_RANGE_ENDS_EARLIER")] += 1
            else:
                field_counts[("close", "MISSING_PRODUCT_CANDLE")] += 1
        for d in prod_dates - ref_dates:
            if d < rmin:
                field_counts[("close", "REFERENCE_RANGE_STARTS_LATER")] += 1
            elif d > rmax:
                field_counts[("close", "REFERENCE_RANGE_ENDS_EARLIER")] += 1
            else:
                field_counts[("close", "MISSING_REFERENCE_CANDLE")] += 1
    norm_diffs = []
    if common and factor_by_date:
        first = common[0]
        rf0, pf0 = factor_by_date.get(first, (None, None))
        if rf0 and pf0:
            for d in common:
                rf, pf = factor_by_date.get(d, (None, None))
                if rf is not None and pf is not None:
                    norm_diffs.append(rel(pf / pf0, rf / rf0))
    return {"common": len(common), "field_counts": field_counts, "samples": field_samples,
            "factor_samples": factor_samples, "func_samples": func_samples,
            "close_diffs": [x for x in close_diffs if x is not None],
            "factor_diffs": [x for x in factor_diffs if x is not None],
            "factor_norm_diffs": [x for x in norm_diffs if x is not None],
            "factor_ratios": [pf / rf for rf, pf in factor_by_date.values()
                              if rf and pf is not None],
            "func_diffs": [x for x in func_diffs if x is not None],
            "func_counts": func_counts, "factor_by_date": factor_by_date}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--product-live", required=True)
    ap.add_argument("--product-db", default="")
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    ref = load_ref(a.ref)
    live = load_product(a.product_live)
    db = load_product(a.product_db)
    manifest = list(csv.DictReader(open(a.manifest, encoding="utf-8-sig")))
    by_asset = defaultdict(list)
    for r in manifest:
        if r.get("ra_asset_id"):
            by_asset[r["ra_asset_id"]].append(r)

    symbol_rows, step_rows, samples = [], [], []
    totals = Counter(); diffs_all = []; factor_all = []; func_all = []; norm_all = []
    field_totals = Counter(); field_status = Counter(); status_counts = Counter()
    weekly_field_status = Counter()
    by_class = defaultdict(Counter)
    done_assets = 0
    for aid, rows in by_asset.items():
        r0 = ref.get(f"{aid}|type0|D", {}).get("bars") or []
        r7 = ref.get(f"{aid}|type7|D", {}).get("bars") or []
        r0w = ref.get(f"{aid}|type0|W", {}).get("bars") or []
        r7w = ref.get(f"{aid}|type7|W", {}).get("bars") or []
        if not r0:
            for r in rows:
                symbol_rows.append({"symbol": r["symbol"], "asset_id": aid, "class": r["ra_class"],
                                    "status": "REFERENCE_UNAVAILABLE", "common_daily": 0})
            continue
        # primary product series: prefer live; merge non-overlapping variant symbols
        chosen = [r for r in rows if r["symbol"] in live]
        if not chosen:
            chosen = [r for r in rows if r["symbol"] in db]
        if not chosen:
            for r in rows:
                symbol_rows.append({"symbol": r["symbol"], "asset_id": aid, "class": r["ra_class"],
                                    "status": "NO_PRODUCT_SERIES", "common_daily": 0})
            continue
        chosen.sort(key=lambda r: (r["symbol"] != rows[0]["symbol"], -int(r.get("product_candles") or 0)))
        products = [(r, live.get(r["symbol"]) or db.get(r["symbol"])) for r in chosen]
        merged = {}; overlap = 0; srcs = []
        for r, p in products:
            d = product_daily(p)
            srcs.append(r["symbol"])
            for k, v in d.items():
                if k in merged:
                    overlap += 1
                else:
                    merged[k] = v
        # factors: only for dates that symbol actually has a candle for; on overlaps
        # prefer the first (current) symbol. Merging full factor histories would let an
        # old variant overwrite the current symbol on dates it has no candle for.
        fac = {}
        for r, p in products:
            f = factors_of(p)
            for d in product_daily(p):
                if d not in fac:
                    fac[d] = f.get(d, 1.0)
        basis = (products[0][1].get("priceBasis") or "closing")
        p0 = products[0][1]
        live_ok = basis == "last" and p0.get("adjustSource") != "local-db-fallback"
        cap = p0.get("adjustCapability") or {}
        cov = cap.get("coverage") or {}
        cmp = compare_series(merged, fac, r0, r7, basis)
        # weekly
        pw = agg_weekly(merged)
        daily_func = {d: {**{f: merged[d][f] * fac.get(d, 1.0)
                            for f in ("open", "high", "low", "close")},
                          "volume": merged[d]["volume"]}
                      for d in merged}
        pw_func = agg_weekly(daily_func)
        pw_fac = {k: ((pw_func[k]["close"] / pw[k]["close"]) if pw[k]["close"] else None)
                  for k in pw}
        cmpw = compare_series(pw, pw_fac, r0w, r7w, basis, prod_func=pw_func)
        # step alignment
        dates = sorted(cmp["factor_by_date"])
        rf = [cmp["factor_by_date"][d][0] for d in dates]
        pf = [cmp["factor_by_date"][d][1] for d in dates]
        rs = steps(dates, rf); ps = steps(dates, [x if x is not None else 0 for x in pf])
        used = set(); pairs = ref_only = prod_only = ratio_bad = 0
        for s in rs:
            sd = dt.date.fromisoformat(s["date"]); best = None
            for j, t in enumerate(ps):
                if j in used:
                    continue
                dd = abs((dt.date.fromisoformat(t["date"]) - sd).days)
                if dd <= STEP_DAYS and abs(t["ratio"] / s["ratio"] - 1) <= STEP_RATIO_PAIR:
                    if best is None or dd < best[0]:
                        best = (dd, j)
            if best:
                used.add(best[1]); t = ps[best[1]]; pairs += 1
                rd = abs(t["ratio"] / s["ratio"] - 1)
                if rd > FACTOR_NEAR:
                    ratio_bad += 1
                step_rows.append({"symbol": rows[0]["symbol"], "asset_id": aid, "ref_date": s["date"],
                                  "prod_date": t["date"], "ref_ratio": round(s["ratio"], 8),
                                  "prod_ratio": round(t["ratio"], 8), "ratio_diff": round(rd, 8),
                                  "kind": "PAIR"})
            else:
                ref_only += 1
                step_rows.append({"symbol": rows[0]["symbol"], "asset_id": aid, "ref_date": s["date"],
                                  "prod_date": "", "ref_ratio": round(s["ratio"], 8),
                                  "prod_ratio": "", "ratio_diff": "", "kind": "REF_ONLY"})
        for j, t in enumerate(ps):
            if j not in used:
                prod_only += 1
                step_rows.append({"symbol": rows[0]["symbol"], "asset_id": aid, "ref_date": "",
                                  "prod_date": t["date"], "ref_ratio": "", "prod_ratio": round(t["ratio"], 8),
                                  "ratio_diff": "", "kind": "PROD_ONLY"})
        fc = cmp["field_counts"]
        raw_compared = sum(v for (f, s), v in fc.items()
                           if f != "factor" and not s.startswith("MISSING")
                           and not s.endswith("_RANGE_STARTS_LATER")
                           and not s.endswith("_RANGE_ENDS_EARLIER"))
        raw_ok = sum(v for (f, s), v in fc.items()
                     if f != "factor" and not s.startswith("MISSING")
                     and not s.endswith("_RANGE_STARTS_LATER")
                     and not s.endswith("_RANGE_ENDS_EARLIER")
                     and s in ("MATCH", "ROUNDING_ONLY"))
        missing_product = sum(v for (f, s), v in fc.items() if s == "MISSING_PRODUCT_CANDLE")
        missing_reference = sum(v for (f, s), v in fc.items() if s == "MISSING_REFERENCE_CANDLE")
        factor_compared = len(cmp["factor_diffs"])
        factor_ok = sum(1 for x in cmp["factor_diffs"] if x <= FACTOR_ROUND)
        factor_near = sum(1 for x in cmp["factor_diffs"] if x <= FACTOR_NEAR)
        fnorm = cmp["factor_norm_diffs"]
        fnorm_ok = sum(1 for x in fnorm if x <= FACTOR_ROUND)
        fnorm_near = sum(1 for x in fnorm if x <= FACTOR_NEAR)
        fnorm_max = max(fnorm) if fnorm else None
        fr = cmp["factor_ratios"]
        fr_min = min(fr) if fr else None
        fr_max = max(fr) if fr else None
        fr_med = statistics.median(fr) if fr else None
        constant_offset = bool(fr and fr_med and (fr_max - fr_min) <= 0.002 * abs(fr_med))
        func_ok = sum(v for (f, s), v in cmp["func_counts"].items() if s in ("MATCH", "ROUNDING_ONLY"))
        func_compared = sum(cmp["func_counts"].values())
        # status
        fmax = max(cmp["factor_diffs"]) if cmp["factor_diffs"] else None
        unresolved = sum(v for (f, s), v in fc.items() if s in ("UNRESOLVED",))
        history_lead = ""
        if dates and r0:
            history_lead = f"{r0[0]['date']}..{dates[0]}"
        pre_offset = None
        if dates:
            rf0 = cmp["factor_by_date"].get(dates[0], (None, None))[0]
            pf0 = cmp["factor_by_date"].get(dates[0], (None, None))[1]
            if rf0 and pf0:
                pre_offset = pf0 / rf0
        if fmax is not None and fmax > FACTOR_NEAR and constant_offset:
            status = "PARTIAL_COVERAGE"      # constant pre-history factor offset
        elif fnorm_max is not None and fnorm_max > FACTOR_NEAR:
            status = "MISMATCH"
        elif cmp["common"] < len(r0) * 0.9:
            status = "PARTIAL_COVERAGE"
        elif ref_only or prod_only or ratio_bad:
            status = "UNRESOLVED_EVENT"
        elif fmax is not None and fmax > FACTOR_ROUND:
            status = "NEAR_MATCH"
        elif unresolved:
            status = "NEAR_MATCH"
        else:
            status = "MATCH"
        row = {
            "symbol": rows[0]["symbol"], "asset_id": aid, "class": rows[0]["ra_class"],
            "product_symbols": ",".join(srcs), "overlap_dates": overlap,
            "product_candles": len(merged), "ref_candles": len(r0), "common_daily": cmp["common"],
            "first_common": dates[0] if dates else "", "last_common": dates[-1] if dates else "",
            "basis": basis, "adjust_source": p0.get("adjustSource"),
            "ref_history_start": r0[0]["date"] if r0 else "",
            "product_history_start": dates[0] if dates else "",
            "pre_history_offset": pre_offset,
            "product_live_available": live_ok,
            "functional_available": cap.get("functional_available"),
            "functional_blockers": " | ".join(str(x) for x in (cap.get("functional_blockers") or [])),
            "coverage_start": cov.get("coverage_start"), "coverage_end": cov.get("coverage_end"),
            "pre_coverage_candles": cov.get("pre_coverage_candles"),
            "unresolved_events": cov.get("unresolved_events"),
            "rows_unmatched": cov.get("rows_unmatched"),
            "rows_total": cov.get("rows_total"), "typed_events": cov.get("typed_events"),
            "missing_product": missing_product, "missing_reference": missing_reference,
            "raw_compared": raw_compared, "raw_ok": raw_ok,
            "raw_ok_pct": round(100.0 * raw_ok / raw_compared, 4) if raw_compared else None,
            "raw_unresolved": unresolved,
            "close_p50": pct(cmp["close_diffs"], 0.5), "close_p95": pct(cmp["close_diffs"], 0.95),
            "close_max": max(cmp["close_diffs"]) if cmp["close_diffs"] else None,
            "factor_compared": factor_compared, "factor_ok": factor_ok,
            "factor_ok_pct": round(100.0 * factor_ok / factor_compared, 4) if factor_compared else None,
            "factor_near_pct": round(100.0 * factor_near / factor_compared, 4) if factor_compared else None,
            "factor_norm_compared": len(fnorm), "factor_norm_ok": fnorm_ok,
            "factor_norm_ok_pct": round(100.0 * fnorm_ok / len(fnorm), 4) if fnorm else None,
            "factor_norm_near_pct": round(100.0 * fnorm_near / len(fnorm), 4) if fnorm else None,
            "factor_norm_p50": pct(fnorm, 0.5), "factor_norm_p95": pct(fnorm, 0.95),
            "factor_norm_max": fnorm_max,
            "factor_ratio_min": fr_min, "factor_ratio_max": fr_max,
            "factor_ratio_median": fr_med, "constant_pre_history_offset": constant_offset,
            "factor_p50": pct(cmp["factor_diffs"], 0.5), "factor_p95": pct(cmp["factor_diffs"], 0.95),
            "factor_max": fmax,
            "func_compared": func_compared, "func_ok": func_ok,
            "func_ok_pct": round(100.0 * func_ok / func_compared, 4) if func_compared else None,
            "func_p50": pct(cmp["func_diffs"], 0.5), "func_p95": pct(cmp["func_diffs"], 0.95),
            "func_max": max(cmp["func_diffs"]) if cmp["func_diffs"] else None,
            "weekly_common": cmpw["common"],
            "weekly_raw_ok_pct": (round(100.0 * sum(v for (f, s), v in cmpw["field_counts"].items()
                                                    if s in ("MATCH", "ROUNDING_ONLY")) /
                                         max(1, sum(cmpw["field_counts"].values())), 4)),
            "ref_steps": len(rs), "prod_steps": len(ps), "step_pairs": pairs,
            "ref_only_steps": ref_only, "prod_only_steps": prod_only,
            "step_ratio_mismatch": ratio_bad,
            "status": status,
        }
        if len(rows) > 1:
            row["status"] += "+MERGED_VARIANTS"
        symbol_rows.append(row)
        for (fld, st), v in fc.items():
            field_totals[fld] += v; field_status[(fld, st)] += v
        for (fld, st), v in cmpw["field_counts"].items():
            weekly_field_status[(fld, st)] += v
        status_counts[status] += 1
        totals["assets"] += 1
        totals["raw_compared"] += raw_compared; totals["raw_ok"] += raw_ok
        totals["factor_compared"] += factor_compared; totals["factor_ok"] += factor_ok
        totals["factor_near"] += factor_near
        totals["func_compared"] += func_compared; totals["func_ok"] += func_ok
        totals["norm_compared"] += len(fnorm); totals["norm_ok"] += fnorm_ok
        totals["norm_near"] += fnorm_near
        totals["missing_product"] += missing_product; totals["missing_reference"] += missing_reference
        if live_ok:
            totals["live_assets"] += 1
            totals["live_raw_compared"] += raw_compared; totals["live_raw_ok"] += raw_ok
            totals["live_factor_compared"] += factor_compared; totals["live_factor_ok"] += factor_ok
            totals["live_factor_near"] += factor_near
            totals["live_norm_compared"] += len(fnorm); totals["live_norm_ok"] += fnorm_ok
            totals["live_norm_near"] += fnorm_near
            totals["live_func_compared"] += func_compared; totals["live_func_ok"] += func_ok
        totals["common_daily"] += cmp["common"]; totals["weekly_common"] += cmpw["common"]
        totals["ref_only_steps"] += ref_only; totals["prod_only_steps"] += prod_only
        totals["step_pairs"] += pairs; totals["step_ratio_mismatch"] += ratio_bad
        diffs_all.extend(cmp["close_diffs"]); factor_all.extend(cmp["factor_diffs"]); func_all.extend(cmp["func_diffs"])
        norm_all.extend(fnorm)
        if constant_offset and fmax is not None and fmax > FACTOR_NEAR:
            totals["constant_offset_assets"] += 1
        by_class[rows[0]["ra_class"]]["assets"] += 1
        by_class[rows[0]["ra_class"]]["raw_ok"] += raw_ok
        by_class[rows[0]["ra_class"]]["raw_compared"] += raw_compared
        by_class[rows[0]["ra_class"]]["factor_ok"] += factor_ok
        by_class[rows[0]["ra_class"]]["factor_compared"] += factor_compared
        by_class[rows[0]["ra_class"]]["func_ok"] += func_ok
        by_class[rows[0]["ra_class"]]["func_compared"] += func_compared
        by_class[rows[0]["ra_class"]]["norm_ok"] += fnorm_ok
        by_class[rows[0]["ra_class"]]["norm_compared"] += len(fnorm)
        by_class[rows[0]["ra_class"]]["norm_near"] += fnorm_near
        for s in cmp["samples"][:20]:
            samples.append(dict(s, symbol=products[0][0]["symbol"], asset_id=str(rows[0].get("ra_asset_id", ""))))
        for s in cmp.get("factor_samples", [])[:20]:
            samples.append(dict(s, symbol=products[0][0]["symbol"], asset_id=str(rows[0].get("ra_asset_id", ""))))
        for s in cmp.get("func_samples", [])[:20]:
            samples.append(dict(s, symbol=products[0][0]["symbol"], asset_id=str(rows[0].get("ra_asset_id", ""))))
        done_assets += 1
        if done_assets % 100 == 0:
            print(f"  {done_assets}/{len(by_asset)} assets", flush=True)

    with open(os.path.join(a.out_dir, "parity_symbols.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        fields = sorted({k for r in symbol_rows for k in r}) if symbol_rows else ["symbol"]
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader(); w.writerows(symbol_rows)
    with open(os.path.join(a.out_dir, "parity_steps.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["symbol", "asset_id", "ref_date", "prod_date", "ref_ratio",
                                          "prod_ratio", "ratio_diff", "kind"])
        w.writeheader(); w.writerows(step_rows)
    with open(os.path.join(a.out_dir, "parity_mismatch_samples.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["symbol", "asset_id", "date", "field", "status", "ref", "prod", "closing", "last", "basis"])
        w.writeheader()
        for s in samples[:5000]:
            w.writerow({"symbol": "", **s})
    summary = {
        "assets_measured": totals["assets"],
        "live_assets": totals["live_assets"],
        "live_raw_compared_fields": totals["live_raw_compared"], "live_raw_ok_fields": totals["live_raw_ok"],
        "live_raw_ok_pct": round(100.0 * totals["live_raw_ok"] / max(1, totals["live_raw_compared"]), 4),
        "live_factor_compared_dates": totals["live_factor_compared"], "live_factor_ok_dates": totals["live_factor_ok"],
        "live_factor_ok_pct": round(100.0 * totals["live_factor_ok"] / max(1, totals["live_factor_compared"]), 4),
        "live_factor_near_pct": round(100.0 * totals["live_factor_near"] / max(1, totals["live_factor_compared"]), 4),
        "live_factor_near_dates": totals["live_factor_near"],
        "live_factor_norm_ok_dates": totals["live_norm_ok"],
        "live_factor_norm_near_dates": totals["live_norm_near"],
        "live_func_compared_fields": totals["live_func_compared"], "live_func_ok_fields": totals["live_func_ok"],
        "live_func_ok_pct": round(100.0 * totals["live_func_ok"] / max(1, totals["live_func_compared"]), 4),
        "missing_product_candles": totals["missing_product"], "missing_reference_candles": totals["missing_reference"],
        "raw_compared_fields": totals["raw_compared"], "raw_ok_fields": totals["raw_ok"],
        "raw_ok_pct": round(100.0 * totals["raw_ok"] / max(1, totals["raw_compared"]), 4),
        "factor_compared_dates": totals["factor_compared"], "factor_ok_dates": totals["factor_ok"],
        "factor_ok_pct": round(100.0 * totals["factor_ok"] / max(1, totals["factor_compared"]), 4),
        "factor_near_pct": round(100.0 * totals["factor_near"] / max(1, totals["factor_compared"]), 4),
        "func_compared_fields": totals["func_compared"], "func_ok_fields": totals["func_ok"],
        "func_ok_pct": round(100.0 * totals["func_ok"] / max(1, totals["func_compared"]), 4),
        "common_daily": totals["common_daily"], "weekly_common": totals["weekly_common"],
        "ref_only_steps": totals["ref_only_steps"], "prod_only_steps": totals["prod_only_steps"],
        "step_pairs": totals["step_pairs"], "step_ratio_mismatch": totals["step_ratio_mismatch"],
        "close_p50": pct(diffs_all, 0.5), "close_p95": pct(diffs_all, 0.95),
        "close_max": max(diffs_all) if diffs_all else None,
        "factor_norm_compared": totals["norm_compared"], "factor_norm_ok": totals["norm_ok"],
        "factor_norm_ok_pct": round(100.0 * totals["norm_ok"] / max(1, totals["norm_compared"]), 4),
        "factor_norm_near_pct": round(100.0 * totals["norm_near"] / max(1, totals["norm_compared"]), 4),
        "live_factor_norm_ok_pct": round(100.0 * totals["live_norm_ok"] / max(1, totals["live_norm_compared"]), 4),
        "live_factor_norm_near_pct": round(100.0 * totals["live_norm_near"] / max(1, totals["live_norm_compared"]), 4),
        "factor_p50": pct(factor_all, 0.5), "factor_p95": pct(factor_all, 0.95),
        "factor_max": max(factor_all) if factor_all else None,
        "norm_p50": pct(norm_all, 0.5), "norm_p95": pct(norm_all, 0.95),
        "norm_max": max(norm_all) if norm_all else None,
        "constant_offset_assets": totals["constant_offset_assets"],
        "func_p50": pct(func_all, 0.5), "func_p95": pct(func_all, 0.95),
        "func_max": max(func_all) if func_all else None,
        "by_class": {k: dict(v) for k, v in by_class.items()},
        "field_totals": dict(field_totals),
        "weekly_field_status": {f"{k[0]}|{k[1]}": v for k, v in sorted(weekly_field_status.items())},
        "weekly_raw_compared_fields": sum(v for (f, st), v in weekly_field_status.items()
                                          if f != "factor" and not st.startswith("MISSING")
                                          and not st.endswith("_RANGE_STARTS_LATER")
                                          and not st.endswith("_RANGE_ENDS_EARLIER")),
        "weekly_raw_ok_fields": sum(v for (f, st), v in weekly_field_status.items()
                                    if f != "factor" and st in ("MATCH", "ROUNDING_ONLY")),
        "field_status": {f"{k[0]}|{k[1]}": v for k, v in sorted(field_status.items())},
        "symbol_status_counts": dict(status_counts),
        "tolerances": {"price_match_abs": PRICE_MATCH_ABS, "price_round_abs": PRICE_ROUND_ABS,
                       "price_round_rel": PRICE_ROUND_REL, "factor_match": FACTOR_MATCH,
                       "factor_round": FACTOR_ROUND, "factor_near": FACTOR_NEAR,
                       "step_tol": STEP_TOL, "step_days": STEP_DAYS},
    }
    json.dump(summary, open(os.path.join(a.out_dir, "parity_summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1)[:3000])


if __name__ == "__main__":
    main()
