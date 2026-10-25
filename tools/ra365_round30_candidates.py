#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 30: evidence-backed candidate corrections and their row recovery.

For every differing factor step this audit asks what a *specific official
ledger row* would change (not what the reference ratio would change):

  R1 share_sharpen  base/unproven gap, one nearby official share row, no PA row
  R2 pa_sharpen     base/unproven gap, one nearby official price-adjust row
  R3 share_add      REF_ONLY step with a nearby share row and no product event
  R4 pa_add         REF_ONLY step with a nearby PA row and no product event

A candidate is accepted into the recovery count only when the official ratio
is within 2% of the observed gap (R1/R2) or would create the missing step
(R3/R4), and no competing official row sits in the same window.  The reported
`recovered` applies the official ratio to the product factor for the affected
rows and re-tests the frozen tolerance.  `ref_agree` only diagnoses whether
the official ratio equals the reference; it is never used to select a row.

Read-only.  Outputs candidates.csv and summary.json.

Usage:
  python tools/ra365_round30_candidates.py --ref <ref.jsonl> --product <dirs> \
      --db <market.db> --out <dir> [--limit N]
"""
import argparse
import bisect
import csv
import datetime as dt
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from ra365_round30_attribution import (  # noqa: E402
    fnum, load_ref_only_d, row_passes, STEP_EPS, event_signature)

MAX_OFFICIAL_GAP = 0.02


def d2i(s):
    try:
        return int(str(s)[:10].replace("-", ""))
    except (TypeError, ValueError):
        return None


def load_ledger(db):
    con = sqlite3.connect(db, timeout=60)
    shares = defaultdict(list)
    pas = defaultdict(list)
    try:
        for ins, d_even, ratio in con.execute(
                "SELECT ins_code, d_even, ratio FROM share_change_events"):
            if ratio and float(ratio) > 0:
                shares[str(ins)].append((int(d_even), float(ratio)))
        try:
            for ins, d_even, ratio in con.execute(
                    "SELECT ins_code, d_even, ratio FROM price_adjust_events"):
                if ratio and float(ratio) > 0:
                    pas[str(ins)].append((int(d_even), float(ratio)))
        except sqlite3.OperationalError:
            pass
    finally:
        con.close()
    for m in (shares, pas):
        for k in m:
            m[k].sort()
    return shares, pas


def nearby(rows, d, before=90, after=7):
    if d is None:
        return []
    return [(days, r) for days, r in rows
            if -before <= (days - d) <= after]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--product", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ref = load_ref_only_d(a.ref)
    shares, pas = load_ledger(a.db)
    products = []
    for root in a.product.split(","):
        if os.path.isdir(root):
            for fn in sorted(os.listdir(root)):
                if fn.endswith(".json") and fn[:-5].isdigit():
                    products.append(os.path.join(root, fn))

    out_rows = []
    agg = defaultdict(Counter)
    agg_assets = defaultdict(set)
    seen = set()
    for path in products:
        if a.limit and len(seen) >= a.limit:
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
            d = str(c.get("time"))[:10]
            if d:
                candles[d] = c
        fac = {str(f.get("time"))[:10]: fnum(f.get("factor"))
               for f in (p.get("factors") or [])}
        fac = {k: v for k, v in fac.items() if v}
        common = sorted(set(candles) & set(fac) & set(t0) & set(t7))
        if len(common) < 10:
            continue
        scale = fac[common[-1]] or 1.0
        pf = {d: f / scale for d, f in fac.items() if d in common}
        rf = {d: t7[d][3] / t0[d] for d in common
              if t0.get(d) and t7.get(d) and t7[d][3] is not None}
        events = defaultdict(list)
        for e in p.get("adjustEvents") or []:
            events[str(e.get("date"))[:10]].append(e)
        ins = str(p.get("ins_code"))
        sh_rows = shares.get(ins, [])
        pa_rows = pas.get(ins, [])

        for prev, cur in zip(common, common[1:]):
            if cur not in rf or prev not in rf:
                continue
            sp = pf[prev] / pf[cur]
            sr = rf[prev] / rf[cur]
            p_step = abs(sp - 1) > STEP_EPS
            r_step = abs(sr - 1) > STEP_EPS
            if not p_step and not r_step:
                continue
            if p_step and r_step and abs(sr / sp - 1) <= 1e-7:
                continue
            ev = [e for d2, lst in events.items() if prev < d2 <= cur for e in lst]
            ev_ratio = 1.0
            for e in ev:
                try:
                    ev_ratio *= float(e.get("ratio") or 1.0)
                except (TypeError, ValueError):
                    pass
            if p_step and not r_step:
                # EXTRA: a candidate is removal (official evidence absent).
                near_sh = nearby(sh_rows, d2i(cur))
                near_pa = nearby(pa_rows, d2i(cur))
                if not near_sh and not near_pa:
                    cand, rule = 1.0, "R5_extra_remove_no_ledger"
                else:
                    continue
            elif r_step and not p_step:
                near_sh = nearby(sh_rows, d2i(cur))
                near_pa = nearby(pa_rows, d2i(cur))
                if len(near_sh) == 1 and not near_pa:
                    cand, rule = near_sh[0][1], "R3_share_add"
                elif len(near_pa) == 1 and not near_sh:
                    cand, rule = near_pa[0][1], "R4_pa_add"
                else:
                    continue
            else:
                near_sh = nearby(sh_rows, d2i(cur))
                near_pa = nearby(pa_rows, d2i(cur))
                if len(near_sh) == 1 and not near_pa and \
                        abs(near_sh[0][1] / sp - 1.0) <= MAX_OFFICIAL_GAP \
                        and abs(near_sh[0][1] / sp - 1.0) > 1e-4:
                    cand, rule = near_sh[0][1], "R1_share_sharpen"
                elif len(near_pa) == 1 and not near_sh and \
                        abs(near_pa[0][1] / sp - 1.0) <= MAX_OFFICIAL_GAP \
                        and abs(near_pa[0][1] / sp - 1.0) > 1e-4:
                    cand, rule = near_pa[0][1], "R2_pa_sharpen"
                else:
                    continue
            if cand <= 0:
                continue
            corr = cand / ev_ratio
            if abs(corr - 1.0) <= 1e-9:
                continue
            recovered = attributed = 0
            idx = bisect.bisect_left(common, cur)
            for d in common[:idx]:
                c = candles[d]
                pv = (fnum(c.get("open")), fnum(c.get("high")), fnum(c.get("low")),
                      fnum(c.get("last")) or fnum(c.get("close")))
                adj = tuple(v * pf[d] if v is not None else None for v in pv)
                if row_passes(adj, t7[d]):
                    continue
                attributed += 1
                corr_adj = tuple(v * corr if v is not None else None for v in adj)
                if row_passes(corr_adj, t7[d]):
                    recovered += 1
            if not attributed:
                continue
            ref_agree = abs(cand / sr - 1.0) if sr else None
            out_rows.append({
                "asset_id": aid, "symbol": p.get("symbol"), "date": cur,
                "rule": rule, "class": ("EXTRA" if not r_step else
                                        "REF_ONLY" if not p_step else "RATIO_DIFF"),
                "event_sig": event_signature(ev), "prod_ratio": round(sp, 12),
                "ref_ratio": round(sr, 12), "official_ratio": round(cand, 12),
                "corr": round(corr, 12),
                "ref_agree": None if ref_agree is None else round(ref_agree, 10),
                "affected": attributed, "recovered": recovered})
            key = (rule, event_signature(ev),
                   "<=0.1%" if ref_agree is not None and ref_agree <= 1e-3 else
                   "<=1%" if ref_agree is not None and ref_agree <= 1e-2 else ">1%")
            c = agg[key]
            c["steps"] += 1
            agg_assets[key].add(aid)
            c["affected"] += attributed
            c["recovered"] += recovered

    with open(os.path.join(a.out, "candidates.csv"), "w",
              encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0]) if out_rows else
                           ["asset_id", "symbol", "date", "rule", "class",
                            "event_sig", "prod_ratio", "ref_ratio",
                            "official_ratio", "corr", "ref_agree", "affected",
                            "recovered"])
        w.writeheader(); w.writerows(out_rows)
    fam = []
    for key, c in agg.items():
        fam.append({"rule": key[0], "event_sig": key[1], "ref_agree": key[2],
                    "steps": c["steps"], "assets": len(agg_assets[key]),
                    "affected": c["affected"], "recovered": c["recovered"]})
    fam.sort(key=lambda r: -r["recovered"])
    summary = {"assets": len(seen), "candidates": len(out_rows),
               "recovered": sum(r["recovered"] for r in out_rows),
               "families": fam}
    json.dump(summary, open(os.path.join(a.out, "summary.json"), "w",
                            encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k != "families"},
                     ensure_ascii=False, indent=1))
    for r in fam[:20]:
        print(r)


if __name__ == "__main__":
    main()
