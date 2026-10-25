#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 30: factor-chain parity (daily) for a product payload set.

Reports exact (<=1e-9) and tolerance (<=1e-6 relative) factor equality on all
common daily dates after re-anchoring the product factor at the last common
date, plus step-chain exactness (adjacent common dates).  Read-only.

Usage:
  python tools/ra365_round30_factor_parity.py --ref <ref.jsonl> \
      --product <dirs> --out <json>
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from ra365_round30_attribution import fnum, load_ref_only_d  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--product", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    ref = load_ref_only_d(a.ref)
    n = exact = tol = step_n = step_exact = step_tol = 0
    assets = 0
    seen = set()
    for root in a.product.split(","):
        if not os.path.isdir(root):
            continue
        for fn in sorted(os.listdir(root)):
            if not (fn.endswith(".json") and fn[:-5].isdigit()):
                continue
            aid = fn[:-5]
            if aid in seen or aid not in ref:
                continue
            seen.add(aid)
            p = json.load(open(os.path.join(root, fn), encoding="utf-8"))
            t0 = ref[aid].get("type0") or {}
            t7 = ref[aid].get("type7") or {}
            fac = {str(f.get("time"))[:10]: fnum(f.get("factor"))
                   for f in (p.get("factors") or [])}
            fac = {d: f for d, f in fac.items() if f}
            common = sorted(set(fac) & set(t0) & set(t7))
            if len(common) < 10:
                continue
            scale = fac[common[-1]] or 1.0
            rf = {d: t7[d][3] / t0[d] for d in common if t7[d][3] is not None}
            common = [d for d in common if d in rf]
            if len(common) < 10:
                continue
            assets += 1
            off = []
            for d in common:
                n += 1
                e = abs((fac[d] / scale) / rf[d] - 1.0)
                off.append(e)
                exact += e <= 1e-9
                tol += e <= 1e-6
            for i in range(1, len(common)):
                sp = (fac[common[i - 1]] / scale) / (fac[common[i]] / scale)
                sr = rf[common[i - 1]] / rf[common[i]]
                e = abs(sp / sr - 1.0)
                step_n += 1
                step_exact += e <= 1e-9
                step_tol += e <= 1e-6
    out = {"assets": assets, "dates": n,
           "factor_exact": exact,
           "factor_tolerance": tol,
           "factor_exact_pct": round(100.0 * exact / max(1, n), 4),
           "factor_tolerance_pct": round(100.0 * tol / max(1, n), 4),
           "steps": step_n,
           "step_exact_pct": round(100.0 * step_exact / max(1, step_n), 4),
           "step_tolerance_pct": round(100.0 * step_tol / max(1, step_n), 4)}
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
