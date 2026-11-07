# -*- coding: utf-8 -*-
"""Round 21 live parity: Rahavard365 live bars vs the product's chart series.

Reference: _scratch/ra365_round21/ra365_r21_ref_live.json (captured in the owner's
authenticated session; type0/type7, D/W, price type real_close).
Product:   _scratch/ra365_round21/product_live/<asset>.json (get_chart_tsetmc).

Definitions (fixed before looking at results):
  exact      price |d| <= 1e-9, volume |d| <= 1e-9
  tolerance  price |d| <= max(0.5, 1e-6*|ref|), volume |d| <= 1
  rounding   price |d| <= max(1.0, 5e-4*|ref|), volume |d| <= 1e-6*|ref|
  weekly     product aggregateCandles rule: Saturday buckets, open=first,
             high=max(high), low=min(low), close=last, volume=sum, stamp=last day.
  raw        product displayed candle (basis last) and literal high_raw/low_raw.
  adjusted   product candle * server factor, rounded to 4 decimals (frontend rule).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE = os.environ.get("RA365_R21_LIVE", "D:/BorsTerminal-tmp/r21_live")
REF = os.environ.get("RA365_R21_REF", os.path.join(LIVE, "ra365_r21_ref_live.json"))
PROD = os.environ.get("RA365_R21_PRODUCT", os.path.join(LIVE, "product_live"))
OUT = os.path.join(ROOT, "artifacts", "ra365", "r21")
ASSETS = {
    "595": "حخزر", "48315": "آکو", "207": "لخزر", "325": "هجرت",
    "291": "ومعادن", "599": "ولانا", "2672": "طلا", "453": "فولاد",
    "149": "فنوال", "167": "خودرو", "182": "شنفت", "696": "شراز",
    "183": "شبهرن", "703": "فارس",
    "462": "وبملت", "484": "شپنا", "287": "قصفها", "384": "سصفها",
    "6274": "درهآور", "109": "سغرب", "485": "مارون", "7836": "شستا",
    "16449": "فزر", "17495": "فافق", "569": "فولاژ", "458": "فخاس",
    "159": "فجام", "252": "شاملا", "498": "وبصادر", "661": "ولراز",
    "302": "سرود",
    "711": "چخزر", "16272": "فگستر", "15239": "شاروم", "637": "شتران",
    "490": "تيپيكو", "500": "مبين", "24691": "معين", "1771": "حپارسا",
    "724": "كپرور", "60": "وملي", "32": "غشهد", "2967": "زقيام",
    "1585": "ساروج", "65": "وبانك", "273": "كبافق", "7831": "صبا",
    "20817": "نخريس", "6273": "رنيك", "540": "كمرجان",
}
FIELDS = ("o", "h", "l", "c", "v")
EPOCH = dt.date(1970, 1, 1)


def load_ref(path=None):
    d = json.load(open(path or REF, encoding="utf-8"))
    items = {}
    for it in d["items"]:
        bars = sorted(it.get("bars") or [], key=lambda b: b["utc"][:10])
        items[(str(it["asset_id"]), it["type"], it["res"])] = bars
    return d, items


def fnum(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def load_product(aid, prod_dir=None):
    p = os.path.join(prod_dir or PROD, aid + ".json")
    d = json.load(open(p, encoding="utf-8"))
    candles = sorted(d.get("candles") or [], key=lambda c: str(c.get("time"))[:10])
    factors = {str(f.get("time"))[:10]: fnum(f.get("factor")) for f in (d.get("factors") or [])}
    vols = {}
    for v in (d.get("volumes") or []):
        vd = str(v.get("time"))[:10]
        val = fnum(v.get("value"))
        if val is None:
            val = fnum(v.get("volume"))
        if vd and val is not None:
            vols[vd] = val
    rows = []
    for c in candles:
        date = str(c.get("time"))[:10]
        if len(date) != 10:
            continue
        f = factors.get(date)
        if f is None or not (f > 0):
            f = 1.0
        last = fnum(c.get("last"))
        closing = fnum(c.get("closing"))
        chosen = fnum(c.get("close"))
        if chosen is None:
            chosen = last if last is not None else closing
        hi_raw = fnum(c.get("high_raw"))
        lo_raw = fnum(c.get("low_raw"))
        if hi_raw is None:
            hi_raw = fnum(c.get("high"))
        if lo_raw is None:
            lo_raw = fnum(c.get("low"))
        rows.append({
            "date": date,
            "open": fnum(c.get("open")),
            "high": fnum(c.get("high")),
            "low": fnum(c.get("low")),
            "high_raw": hi_raw, "low_raw": lo_raw,
            "close": chosen, "last": last, "closing": closing,
            "volume": vols.get(date, fnum(c.get("volume"))), "factor": f,
            "a_open": None if fnum(c.get("open")) is None else round(fnum(c.get("open")) * f, 4),
            "a_high": None if fnum(c.get("high")) is None else round(fnum(c.get("high")) * f, 4),
            "a_low": None if fnum(c.get("low")) is None else round(fnum(c.get("low")) * f, 4),
            "a_close": None if chosen is None else round(chosen * f, 4),
            "a_high_raw": None if hi_raw is None else round(hi_raw * f, 4),
            "a_low_raw": None if lo_raw is None else round(lo_raw * f, 4),
        })
    meta = {
        "status": d.get("status"), "count": d.get("count"),
        "adjustSource": d.get("adjustSource"), "priceBasis": d.get("priceBasis"),
        "priceBasisReason": d.get("priceBasisReason"),
        "fetched_at": d.get("fetched_at"),
    }
    return rows, meta


def bucket_key(date):
    y, m, d = map(int, date.split("-"))
    day = (dt.date(y, m, d) - EPOCH).days
    return (day - 2) // 7


def aggregate_weekly(rows, value_prefix=""):
    out = []
    key = None
    bar = None
    for r in rows:
        k = bucket_key(r["date"])
        if k != key:
            if bar:
                out.append(bar)
            key = k
            bar = dict(r)
            bar["date"] = r["date"]
            continue
        for f in ("open", "high", "low", "close", value_prefix + "open",
                  value_prefix + "high", value_prefix + "low", value_prefix + "close",
                  value_prefix + "high_raw", value_prefix + "low_raw"):
            if f not in r or r.get(f) is None:
                continue
            cur = bar.get(f)
            if f.endswith("open") or f == "open":
                if cur is None:
                    bar[f] = r[f]
            elif f.endswith("high") or f == "high" or f.endswith("high_raw"):
                bar[f] = r[f] if cur is None else max(cur, r[f])
            elif f.endswith("low") or f == "low" or f.endswith("low_raw"):
                bar[f] = r[f] if cur is None else min(cur, r[f])
            else:
                bar[f] = r[f]
        bar["volume"] = (bar.get("volume") or 0) + (r.get("volume") or 0)
        bar["factor"] = r["factor"]
        bar["date"] = r["date"]
    if bar:
        out.append(bar)
    return out


def field_values(row, mode, displayed):
    if mode == "raw":
        return {
            "o": row["open"], "h": row["high"] if displayed else row["high_raw"],
            "l": row["low"] if displayed else row["low_raw"],
            "c": row["close"], "v": row["volume"],
        }
    return {
        "o": row["a_open"], "h": row["a_high"] if displayed else row["a_high_raw"],
        "l": row["a_low"] if displayed else row["a_low_raw"],
        "c": row["a_close"], "v": row["volume"],
    }


def ref_values(bar):
    return {"o": fnum(bar.get("o")), "h": fnum(bar.get("h")), "l": fnum(bar.get("l")),
            "c": fnum(bar.get("c")), "v": fnum(bar.get("v"))}


def price_status(ref, val):
    if ref is None or val is None:
        return "MISSING"
    d = abs(val - ref)
    if d <= 1e-9:
        return "EXACT"
    if d <= max(0.5, 1e-6 * abs(ref)):
        return "TOLERANCE"
    if d <= max(1.0, 5e-4 * abs(ref)):
        return "ROUNDING"
    return "MISMATCH"


def volume_status(ref, val):
    if ref is None or val is None:
        return "MISSING"
    d = abs(val - ref)
    if d <= 1e-9:
        return "EXACT"
    if d <= 1:
        return "TOLERANCE"
    if d <= max(1.0, 1e-6 * abs(ref)):
        return "ROUNDING"
    return "MISMATCH"


def rel_err(ref, val):
    if ref is None or val is None or ref == 0:
        return None
    return abs(val - ref) / abs(ref)


def quantile(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return xs[lo]
    return xs[lo] * (hi - k) + xs[hi] * (k - lo)


def compare(mode, res, aid, sym, prod_daily, prod_meta, ref_bars, displayed, out_csv, top):
    if res == "D":
        prod_rows = prod_daily
    else:
        prod_rows = aggregate_weekly(prod_daily, "a_" if mode == "adjusted" else "")
    prod_map = {r["date"]: r for r in prod_rows}
    prod_bucket = {}
    for r in prod_rows:
        prod_bucket[bucket_key(r["date"])] = r
    ref_map = {}
    ref_bucket = {}
    for b in ref_bars:
        d = b["utc"][:10]
        ref_map[d] = b
        ref_bucket[bucket_key(d)] = b
    if res == "D":
        pairs = sorted(set(prod_map) & set(ref_map))
        ref_dates = set(ref_map)
        prod_dates = set(prod_map)
    else:
        pairs = sorted(set(prod_bucket) & set(ref_bucket))
        ref_dates = set(ref_bucket)
        prod_dates = set(prod_bucket)
    counts = Counter()
    field_counts = {f: Counter() for f in FIELDS}
    errs = {f: [] for f in FIELDS}
    row_hit = 0
    row_tol = 0
    for p in pairs:
        if res == "D":
            pr = prod_map[p]
            rb = ref_map[p]
            date = p
        else:
            pr = prod_bucket[p]
            rb = ref_bucket[p]
            date = pr["date"]
        pv = field_values(pr, mode, displayed)
        rv = ref_values(rb)
        statuses = {}
        for f in FIELDS:
            st = volume_status(rv[f], pv[f]) if f == "v" else price_status(rv[f], pv[f])
            statuses[f] = st
            field_counts[f][st] += 1
            e = rel_err(rv[f], pv[f])
            if e is not None:
                errs[f].append(e)
        ok_exact = all(statuses[f] == "EXACT" for f in FIELDS)
        ok_tol = all(statuses[f] in ("EXACT", "TOLERANCE") for f in FIELDS)
        row_hit += ok_exact
        row_tol += ok_tol
        if not ok_tol:
            for f in FIELDS:
                if statuses[f] not in ("EXACT", "TOLERANCE"):
                    out_csv.writerow([mode, res, displayed and "displayed" or "literal", aid, sym,
                                      date, f, rv[f], pv[f],
                                      None if rv[f] is None or pv[f] is None else pv[f] - rv[f],
                                      None if rel_err(rv[f], pv[f]) is None else f"{rel_err(rv[f], pv[f]):.8f}",
                                      statuses[f]])
                    top.append((rel_err(rv[f], pv[f]) or 0.0, mode, res, displayed, aid, sym, date, f,
                                rv[f], pv[f], statuses[f]))
    return {
        "asset_id": aid, "symbol": sym, "mode": mode, "resolution": res,
        "variant": "displayed" if displayed else "literal",
        "product_basis": prod_meta.get("priceBasis"),
        "product_source": prod_meta.get("adjustSource"),
        "paired": len(pairs),
        "ref_in_scope": len(ref_dates), "product_in_scope": len(prod_dates),
        "ref_only": len(ref_dates - prod_dates), "product_only": len(prod_dates - ref_dates),
        "row_exact": row_hit, "row_tolerance": row_tol,
        "row_exact_pct": round(100.0 * row_hit / len(pairs), 4) if pairs else None,
        "row_tolerance_pct": round(100.0 * row_tol / len(pairs), 4) if pairs else None,
        "fields": {f: {"exact": field_counts[f]["EXACT"],
                       "tolerance": field_counts[f]["EXACT"] + field_counts[f]["TOLERANCE"],
                       "rounding_only": field_counts[f]["ROUNDING"],
                       "mismatch": field_counts[f]["MISMATCH"],
                       "missing": field_counts[f]["MISSING"],
                       "median_rel": quantile(errs[f], 0.5),
                       "p90_rel": quantile(errs[f], 0.9),
                       "p95_rel": quantile(errs[f], 0.95),
                       "p99_rel": quantile(errs[f], 0.99),
                       "max_rel": max(errs[f]) if errs[f] else None}
                   for f in FIELDS},
    }


def factor_compare(aid, sym, prod_daily, r0, r7, out_csv):
    p0 = {b["utc"][:10]: b for b in r0}
    p7 = {b["utc"][:10]: b for b in r7}
    paired = sorted(set(p0) & set(p7) & set(r["date"] for r in prod_daily))
    prod = {r["date"]: r["factor"] for r in prod_daily}
    exact = tol1 = 0
    errs = []
    worst = []
    for d in paired:
        ref0 = fnum(p0[d].get("c"))
        ref7 = fnum(p7[d].get("c"))
        if not ref0 or not ref7 or ref0 <= 0:
            continue
        ref_factor = ref7 / ref0
        pf = prod.get(d)
        if pf is None:
            continue
        e = abs(pf / ref_factor - 1.0) if ref_factor else None
        if e is not None:
            errs.append(e)
        if e is not None and e <= 5e-4:
            exact += 1
        if e is not None and e <= 0.01:
            tol1 += 1
        if e is not None and e > 0.01:
            worst.append((e, d, ref_factor, pf))
            out_csv.writerow(["factor", "D", "literal", aid, sym, d, "factor",
                              ref_factor, pf, pf - ref_factor, f"{e:.8f}", "MISMATCH" if e > 0.01 else "TOLERANCE"])
    worst.sort(reverse=True)
    return {"asset_id": aid, "symbol": sym, "paired": len(paired),
            "exact_5e4": exact, "within_1pct": tol1,
            "exact_pct": round(100.0 * exact / len(paired), 4) if paired else None,
            "within_1pct_pct": round(100.0 * tol1 / len(paired), 4) if paired else None,
            "median_rel": quantile(errs, 0.5), "p90_rel": quantile(errs, 0.9),
            "p99_rel": quantile(errs, 0.99), "max_rel": max(errs) if errs else None,
            "worst": [{"date": d, "ref_factor": rf, "product_factor": pf, "rel": e}
                      for e, d, rf, pf in worst[:10]]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=REF)
    ap.add_argument("--product", default=PROD)
    ap.add_argument("--assets", default="", help="comma-separated asset ids")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--exclude-fallback", action="store_true",
                    help="exclude product series whose price basis is not last")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ref_doc, ref = load_ref(a.ref)
    summary = {
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "reference": {
            "file": os.path.basename(a.ref), "generated_at": ref_doc.get("generated_at"),
            "source": ref_doc.get("source"), "price_type": ref_doc.get("price_type"),
            "series": len(ref_doc["items"]),
            "bars": sum(len(it.get("bars") or []) for it in ref_doc["items"]),
        },
        "tolerances": {
            "exact": "price |d| <= 1e-9; volume |d| <= 1e-9",
            "tolerance": "price |d| <= max(0.5, 1e-6*|ref|); volume |d| <= 1",
            "rounding": "price |d| <= max(1.0, 5e-4*|ref|); volume |d| <= max(1, 1e-6*|ref|)",
            "weekly_rule": "Saturday buckets (day-2)//7; open=first, high=max, low=min, close=last, volume=sum, stamp=last day",
        },
        "series": [],
        "factor": [],
        "aggregate": {},
    }
    csv_path = os.path.join(a.out, "live-parity-mismatches.csv")
    fcsv = open(csv_path, "w", encoding="utf-8-sig", newline="")
    fw = csv.writer(fcsv)
    fw.writerow(["mode", "resolution", "variant", "asset_id", "symbol", "date", "field",
                 "reference", "product", "diff", "rel", "status"])
    top = []
    factor_rows = []
    excluded = []
    wanted = {x.strip() for x in a.assets.split(",") if x.strip()}
    for aid, sym in ASSETS.items():
        if wanted and aid not in wanted:
            continue
        try:
            prod_daily, meta = load_product(aid, a.product)
        except FileNotFoundError:
            excluded.append({"asset_id": aid, "symbol": sym, "reason": "no product payload"})
            continue
        if a.exclude_fallback and meta.get("priceBasis") != "last":
            excluded.append({"asset_id": aid, "symbol": sym, "reason": f"product basis {meta.get('priceBasis')} ({meta.get('priceBasisReason')})"})
            continue
        for mode, rtype in (("raw", "type0"), ("adjusted", "type7")):
            for res in ("D", "W"):
                bars = ref.get((aid, rtype, res)) or []
                if not bars:
                    excluded.append({"asset_id": aid, "symbol": sym, "reason": f"no reference {rtype} {res}"})
                    continue
                for displayed in (True, False):
                    rec = compare(mode, res, aid, sym, prod_daily, meta, bars, displayed, fw, top)
                    summary["series"].append(rec)
        r0 = ref.get((aid, "type0", "D")) or []
        r7 = ref.get((aid, "type7", "D")) or []
        if r0 and r7:
            factor_rows.append(factor_compare(aid, sym, prod_daily, r0, r7, fw))
    fcsv.close()
    summary["factor"] = factor_rows
    summary["excluded"] = excluded
    # aggregates per (mode,res,variant)
    agg = defaultdict(lambda: {"paired": 0, "row_exact": 0, "row_tolerance": 0,
                               "series": 0, "ref_in_scope": 0, "ref_only": 0,
                               "product_only": 0,
                               "fields": {f: Counter() for f in FIELDS},
                               "errs": {f: [] for f in FIELDS}})
    for r in summary["series"]:
        k = (r["mode"], r["resolution"], r["variant"])
        g = agg[k]
        g["series"] += 1
        g["paired"] += r["paired"]
        g["row_exact"] += r["row_exact"]
        g["row_tolerance"] += r["row_tolerance"]
        g["ref_in_scope"] += r["ref_in_scope"]
        g["ref_only"] += r["ref_only"]
        g["product_only"] += r["product_only"]
        for f in FIELDS:
            fd = r["fields"][f]
            g["fields"][f]["exact"] += fd["exact"]
            g["fields"][f]["tolerance"] += fd["tolerance"]
            g["fields"][f]["mismatch"] += fd["mismatch"]
            g["fields"][f]["rounding_only"] += fd["rounding_only"]
            g["fields"][f]["missing"] += fd["missing"]
    for k, g in agg.items():
        n = g["paired"]
        summary["aggregate"][f"{k[0]}|{k[1]}|{k[2]}"] = {
            "series": g["series"], "paired": n,
            "ref_in_scope": g["ref_in_scope"], "ref_only": g["ref_only"],
            "product_only": g["product_only"],
            "row_exact": g["row_exact"], "row_exact_pct": round(100.0 * g["row_exact"] / n, 4) if n else None,
            "row_tolerance": g["row_tolerance"], "row_tolerance_pct": round(100.0 * g["row_tolerance"] / n, 4) if n else None,
            "fields": {f: dict(g["fields"][f]) for f in FIELDS},
        }
    top.sort(reverse=True)
    summary["top_errors"] = [
        {"rel": e, "mode": m, "resolution": r, "variant": "displayed" if d else "literal",
         "asset_id": aid, "symbol": sym, "date": date, "field": f, "reference": rv,
         "product": pv, "status": st}
        for e, m, r, d, aid, sym, date, f, rv, pv, st in top[:25]
    ]
    with open(os.path.join(a.out, "live-parity-summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: {"paired": v["paired"], "row_exact_pct": v["row_exact_pct"],
                          "row_tol_pct": v["row_tolerance_pct"],
                          "fields": {f: (round(100.0 * v["fields"][f]["tolerance"] / v["paired"], 4)
                                         if v["paired"] else None) for f in FIELDS}}
                      for k, v in summary["aggregate"].items()}, ensure_ascii=False, indent=1))
    print("excluded:", json.dumps(excluded, ensure_ascii=False))


if __name__ == "__main__":
    main()
