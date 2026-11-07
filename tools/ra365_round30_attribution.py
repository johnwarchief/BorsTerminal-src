#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 30: full-universe adjusted-parity attribution.

Aligns the product factor chain with the reference type7/type0 chain on every
common daily date, classifies each differing step (EXTRA / REF_ONLY /
RATIO_DIFF), and attributes failing adjusted rows to the nearest mismatched
step above them.  For every step it also evaluates the one-step
counterfactual: if that step alone were corrected to the reference ratio,
would the row pass the frozen tolerance?  This is read-only; it never edits
the product or the reference.

Outputs (out dir):
  steps.csv      every mismatched step with its event signature and row counts
  families.csv   aggregated by class + event signature (+ error bucket)
  assets.csv     per-asset totals and the dominant recoverable family
  summary.json   totals, ranking and sanity counters

Usage:
  python tools/ra365_round30_attribution.py --ref <ref.jsonl> \
      --product <dir>[,<dir>] --out <dir> [--cohort <cohort.jsonl>] [--limit N]
"""
import argparse
import bisect
import csv
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOL = 0.5
REL = 1e-6
STEP_EPS = 1e-7


def fnum(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def bar_tuple(b):
    if isinstance(b, dict):
        return (str(b.get("utc"))[:10], fnum(b.get("open")), fnum(b.get("high")),
                fnum(b.get("low")), fnum(b.get("close")))
    return (str(b[0])[:10], fnum(b[1]), fnum(b[2]), fnum(b[3]), fnum(b[4]))


def load_ref_only_d(path):
    """{asset: {'type0': {date: close}, 'type7': {date: (o,h,l,c)}}}"""
    out = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            if d.get("res") != "D" or d.get("type") not in ("type0", "type7"):
                continue
            aid = str(d.get("asset_id"))
            bars = {}
            for b in d.get("bars") or []:
                t = bar_tuple(b)
                if t[0]:
                    bars[t[0]] = t[1:] if d["type"] == "type7" else t[4]
            out.setdefault(aid, {})[d["type"]] = bars
    return out


def price_tol(ref):
    return max(TOL, REL * abs(ref))


def row_passes(prod, ref):
    """prod/ref = (o,h,l,c).  Tolerance per field; null non-price fails."""
    for pv, rv in zip(prod, ref):
        if pv is None or rv is None:
            return False
        if abs(pv - rv) > price_tol(rv):
            return False
    return True


def event_kind(src):
    s = "" if src is None else str(src)
    if s.startswith("fund-portal"):
        return "fund_dps"
    if s == "tsetmc_price_adjust_by_flow":
        return "dps"
    if s == "shareChange":
        return "share"
    if s == "base-price-discontinuity":
        return "base_gap"
    if s == "priceAdjust":
        return "pa"
    if s in ("", "None", "NoneType"):
        return "unproven_gap"
    return s


def event_signature(events):
    kinds = sorted({event_kind(e.get("source")) for e in events})
    return "+".join(kinds) if kinds else "no_event"


def err_bucket(err):
    a = abs(err)
    if a < 1e-4:
        return "<0.01%"
    if a < 1e-3:
        return "0.01-0.1%"
    if a < 1e-2:
        return "0.1-1%"
    if a < 0.1:
        return "1-10%"
    return ">=10%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--product", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cohort", default="")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    symbols = {}
    if a.cohort:
        for line in open(a.cohort, encoding="utf-8"):
            d = json.loads(line)
            symbols[str(d.get("ra_asset_id"))] = d.get("symbol")

    ref = load_ref_only_d(a.ref)
    products = []
    for root in a.product.split(","):
        if not os.path.isdir(root):
            continue
        for fn in sorted(os.listdir(root)):
            if fn.endswith(".json") and fn[:-5].isdigit():
                products.append(os.path.join(root, fn))

    steps_rows = []
    assets_rows = []
    fam = defaultdict(lambda: Counter())
    fam_by_asset = defaultdict(lambda: Counter())
    seen = set()
    sanity = Counter()
    for path in products:
        if a.limit and len(assets_rows) >= a.limit:
            break
        p = json.load(open(path, encoding="utf-8"))
        aid = str(p.get("asset_id"))
        if aid in seen or aid not in ref:
            continue
        seen.add(aid)
        t0 = ref[aid].get("type0") or {}
        t7 = ref[aid].get("type7") or {}
        candles = {}
        for c in p.get("candles") or []:
            dt = str(c.get("time"))[:10]
            if dt:
                candles[dt] = c
        fac = {str(f.get("time"))[:10]: fnum(f.get("factor"))
               for f in (p.get("factors") or [])}
        fac = {k: v for k, v in fac.items() if v}
        common = sorted(set(candles) & set(fac) & set(t0) & set(t7))
        if len(common) < 10:
            continue
        scale = fac[common[-1]] or 1.0
        pf = {d: f / scale for d, f in fac.items() if d in common}
        rf = {}
        for d in common:
            if t0.get(d) and t7.get(d) and t7[d][3] is not None:
                rf[d] = t7[d][3] / t0[d]

        events = defaultdict(list)
        for e in p.get("adjustEvents") or []:
            events[str(e.get("date"))[:10]].append(e)

        step_dates, step_data = [], []
        for prev, cur in zip(common, common[1:]):
            sp = pf[prev] / pf[cur] if pf.get(cur) else 1.0
            sr = rf[prev] / rf[cur] if rf.get(cur) else 1.0
            p_step = abs(sp - 1) > STEP_EPS
            r_step = abs(sr - 1) > STEP_EPS
            if not p_step and not r_step:
                continue
            cls = ("RATIO_DIFF" if p_step and r_step else
                   "REF_ONLY" if r_step else "EXTRA")
            ev = [e for d2, lst in events.items() if prev < d2 <= cur for e in lst]
            err = (sr / sp - 1.0) if sp else 0.0
            step_dates.append(cur)
            step_data.append((prev, cur, cls, sp, sr, err, ev))

        fails = []
        for d in common:
            c = candles[d]
            pv = (fnum(c.get("open")), fnum(c.get("high")), fnum(c.get("low")),
                  fnum(c.get("last")) or fnum(c.get("close")))
            if not row_passes((pv[0] * pf[d] if pv[0] is not None else None,
                               pv[1] * pf[d] if pv[1] is not None else None,
                               pv[2] * pf[d] if pv[2] is not None else None,
                               pv[3] * pf[d] if pv[3] is not None else None), t7[d]):
                fails.append((d, pv, pf[d]))


        n_aff = []
        for prev, cur, cls, sp, sr, err, ev in step_data:
            n_aff.append(bisect.bisect_left(common, cur))
        step_rec = []
        recovered = Counter()
        for idx, (prev, cur, cls, sp, sr, err, ev) in enumerate(step_data):
            sig = event_signature(ev)
            bucket = err_bucket(err)
            rec = {"asset_id": aid,
                   "symbol": symbols.get(aid) or p.get("symbol"),
                   "date": cur, "class": cls, "prod_ratio": round(sp, 12),
                   "ref_ratio": round(sr, 12), "err": round(err, 10),
                   "err_bucket": bucket, "event_sig": sig,
                   "event_sources": ";".join(str(e.get("source")) for e in ev),
                   "event_ratios": ";".join(str(e.get("ratio")) for e in ev),
                   "event_dps": ";".join(str(e.get("dividend_per_share")) for e in ev
                                         if e.get("dividend_per_share") is not None),
                   "affected_rows": n_aff[idx], "attributed_rows": 0,
                   "recovered_rows": 0}
            step_rec.append(rec)

        if step_data:
            for d, pv, f in fails:
                j = bisect.bisect_right(step_dates, d)  # first step with cur > d
                if j >= len(step_data):
                    continue
                rec = step_rec[j]
                sp, sr = rec["prod_ratio"], rec["ref_ratio"]
                if not sp or not sr:
                    continue
                corr = sr / sp
                if row_passes((pv[0] * f * corr if pv[0] is not None else None,
                               pv[1] * f * corr if pv[1] is not None else None,
                               pv[2] * f * corr if pv[2] is not None else None,
                               pv[3] * f * corr if pv[3] is not None else None),
                              t7[d]):
                    rec["recovered_rows"] += 1
                    recovered[j] += 1
                rec["attributed_rows"] += 1
        for rec in step_rec:
            key = (rec["class"], rec["event_sig"], rec["err_bucket"])
            c = fam[key]
            c["steps"] += 1
            c["affected"] += rec["affected_rows"]
            c["attributed"] += rec["attributed_rows"]
            c["recovered"] += rec["recovered_rows"]
            steps_rows.append(rec)
        total_fail = len(fails)
        recov_by_fam = Counter()
        for rec in step_rec:
            if rec["recovered_rows"]:
                recov_by_fam[(rec["class"], rec["event_sig"], rec["err_bucket"])] += rec["recovered_rows"]
        dom = recov_by_fam.most_common(1)[0][0] if recov_by_fam else ("", "", "")
        assets_rows.append({"asset_id": aid,
                            "symbol": symbols.get(aid) or p.get("symbol"),
                            "paired": len(common), "failing": total_fail,
                            "steps": len(step_data), "recovered": sum(recovered.values()),
                            "dominant_family": "|".join(dom)})
        sanity["assets"] += 1
        sanity["paired"] += len(common)
        sanity["failing"] += total_fail
        sanity["steps"] += len(step_data)
        sanity["recovered"] += sum(recovered.values())
        for key, rec in zip([(r["class"], r["event_sig"], r["err_bucket"]) for r in step_rec],
                            step_rec):
            fam_by_asset[key][aid] += 1

    step_fields = ["asset_id", "symbol", "date", "class", "prod_ratio", "ref_ratio",
                   "err", "err_bucket", "event_sig", "event_sources", "event_ratios",
                   "event_dps", "affected_rows", "attributed_rows", "recovered_rows"]
    with open(os.path.join(a.out, "steps.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=step_fields)
        w.writeheader()
        for r in steps_rows:
            w.writerow({k: r[k] for k in step_fields})
    with open(os.path.join(a.out, "assets.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(assets_rows[0]) if assets_rows else
                           ["asset_id", "symbol", "paired", "failing", "steps",
                            "recovered", "dominant_family"])
        w.writeheader()
        w.writerows(assets_rows)
    families = []
    for key, c in fam.items():
        families.append({"class": key[0], "event_sig": key[1], "err_bucket": key[2],
                         "steps": c["steps"], "assets": len(fam_by_asset[key]),
                         "affected": c["affected"], "attributed": c["attributed"],
                         "recovered": c["recovered"]})
    families.sort(key=lambda r: (-r["recovered"], -r["attributed"]))
    with open(os.path.join(a.out, "families.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["class", "event_sig", "err_bucket", "steps",
                                          "assets", "affected", "attributed", "recovered"])
        w.writeheader()
        w.writerows(families)
    summary = dict(sanity)
    summary["families"] = families[:60]
    summary["cohort_symbols"] = len(symbols)
    json.dump(summary, open(os.path.join(a.out, "summary.json"), "w",
                            encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in sanity.items() if not isinstance(v, Counter)},
                     ensure_ascii=False, indent=1))
    print("top families:")
    for r in families[:15]:
        print(r)


if __name__ == "__main__":
    main()
