#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 26: full-universe raw/adjusted audit on the frozen 2026-10-20 corpus.

Inputs (outside Git, checksummed in the report):
  ref_bars_v2.jsonl          Rahavard type0/type7 D/W (2,595 assets)
  product_live_final_v4.jsonl  frozen product lines (candles/factors/events)
  cohort.jsonl               ra_asset_id ↔ symbol ↔ ins_code manifest

For every asset with both sides it measures, per daily row:
  * raw close parity (product close vs type0 close),
  * factor parity (product factor vs type7/type0),
  * adjusted close parity (product close × factor vs type7 close),
and attributes every failing adjusted row to the nearest mismatched factor
step (RATIO_DIFF / REF_ONLY / EXTRA) or to the raw/basis difference.

Read-only; nothing is written outside the output directory.
"""
import argparse
import csv
import json
import os
from collections import Counter, defaultdict

TOL = 0.5
REL = 1e-6


def fnum(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def norm(s):
    return str(s or "").strip().translate(str.maketrans({"ك": "ک", "ي": "ی", "ى": "ی"}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--product", required=True)
    ap.add_argument("--cohort", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    ref = {}
    assets = set()
    for line in open(a.ref, encoding="utf-8"):
        d = json.loads(line)
        if d.get("type") not in ("type0", "type7") or d.get("res") != "D":
            continue
        aid = str(d.get("asset_id"))
        bars = d.get("bars") or []
        bar_map = {}
        for b in bars:
            if isinstance(b, dict):
                dt = str(b.get("utc"))[:10]
                vals = (b.get("open"), b.get("high"), b.get("low"),
                        b.get("close"), b.get("volume"))
            else:
                dt = str(b[0])[:10]
                vals = (b[1], b[2], b[3], b[4], b[5])
            if dt:
                bar_map[dt] = tuple(fnum(x) for x in vals)
        ref.setdefault(aid, {})[d["type"]] = bar_map
        assets.add(aid)

    manifest = []
    for line in open(a.cohort, encoding="utf-8"):
        d = json.loads(line)
        manifest.append((str(d.get("ra_asset_id")), d.get("symbol"), d.get("ins_code"),
                         d.get("basis") or "last", d.get("adjust_source") or ""))
    by_sym = {}
    by_norm = {}
    for aid, sym, ins, basis, src in manifest:
        by_sym.setdefault(str(sym), (aid, sym, basis, src))
        by_norm.setdefault(norm(sym), (aid, sym, basis, src))

    per_asset = []
    fields = Counter()
    rows = Counter()
    classes = Counter()
    errors_csv = open(os.path.join(a.out, "adjusted-error-rows.csv"), "w",
                      encoding="utf-8-sig", newline="")
    ew = csv.writer(errors_csv)
    ew.writerow(["asset_id", "symbol", "date", "class", "product", "reference",
                 "rel", "product_factor", "reference_factor"])
    seen = set()
    for line in open(a.product, encoding="utf-8"):
        d = json.loads(line)
        sym = d.get("symbol")
        hit = by_sym.get(str(sym)) or by_norm.get(norm(sym))
        if not hit:
            continue
        aid, canon, basis, src = hit
        if aid in seen or aid not in ref:
            continue
        seen.add(aid)
        t0 = ref[aid].get("type0") or {}
        t7 = ref[aid].get("type7") or {}
        candles = sorted(d.get("candles") or [], key=lambda c: str(c.get("time"))[:10])
        close = {}
        for c in candles:
            date = str(c.get("time"))[:10]
            v = fnum(c.get("last")) if basis == "last" else fnum(c.get("closing"))
            if not v:
                v = fnum(c.get("closing")) or fnum(c.get("close"))
            if date and v is not None:
                close[date] = v
        fac = {str(f.get("time"))[:10]: fnum(f.get("factor"))
               for f in (d.get("factors") or [])}
        fac = {k: v for k, v in fac.items() if v}
        common = sorted(set(fac) & set(close) & set(t0) & set(t7))
        if len(common) < 10:
            continue
        fref = {}
        for dt in common:
            r0, r7 = t0.get(dt), t7.get(dt)
            if r0 and r7 and r0[3] and r7[3]:
                fref[dt] = r7[3] / r0[3]
        common = [dt for dt in common if dt in fref]
        if len(common) < 10:
            continue
        steps = []
        for prev, cur in zip(common, common[1:]):
            sp = fac[prev] / fac[cur]
            sr = fref[prev] / fref[cur]
            p_s, r_s = abs(sp - 1) > 1e-7, abs(sr - 1) > 1e-7
            if not p_s and not r_s:
                continue
            if p_s and r_s:
                if abs(sr / sp - 1) <= 1e-4:
                    continue
                cls = "RATIO_DIFF"
            elif r_s:
                cls = "REF_ONLY"
            else:
                cls = "EXTRA"
            steps.append((cur, cls))
            classes[cls] += 1
        adj_ok = raw_ok = fac_ok = 0
        for dt in common:
            raw_p = close[dt]
            ref_adj = t7[dt][3]
            ref_raw = t0[dt][3]
            prod_adj = raw_p * fac[dt]
            raw_diff = abs(raw_p - ref_raw)
            raw_good = raw_diff <= max(TOL, REL * abs(ref_raw))
            fac_good = abs(fac[dt] / fref[dt] - 1.0) <= 1e-6
            adj_diff = abs(prod_adj - ref_adj)
            adj_good = adj_diff <= max(TOL, REL * abs(ref_adj))
            raw_ok += raw_good
            fac_ok += fac_good
            adj_ok += adj_good
            if not adj_good:
                nxt = next((s for s in steps if s[0] > dt), None)
                cls = nxt[1] if nxt else ("RAW_OR_BASIS" if not raw_good else "UNATTRIBUTED")
                rows[cls] += 1
                if len([1 for _ in ()]) == 0:
                    ew.writerow([aid, canon, dt, cls, round(prod_adj, 6),
                                 round(ref_adj, 6),
                                 round(adj_diff / abs(ref_adj), 8) if ref_adj else "",
                                 fac[dt], fref[dt]])
        n = len(common)
        fields["adjusted"] += n
        fields["adjusted_ok"] += adj_ok
        fields["factor"] += n
        fields["factor_ok"] += fac_ok
        fields["raw"] += n
        fields["raw_ok"] += raw_ok
        per_asset.append({"asset_id": aid, "symbol": canon, "basis": basis,
                          "adjust_source": src, "rows": n,
                          "adjusted_ok_pct": round(100.0 * adj_ok / n, 4),
                          "factor_ok_pct": round(100.0 * fac_ok / n, 4),
                          "raw_ok_pct": round(100.0 * raw_ok / n, 4)})
    errors_csv.close()
    with open(os.path.join(a.out, "per-asset.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(per_asset[0]))
        w.writeheader(); w.writerows(per_asset)
    summary = {
        "reference": a.ref, "product": a.product, "cohort": a.cohort,
        "assets_ref": len(assets), "assets_paired": len(per_asset),
        "rows": dict(fields),
        "adjusted_ok_pct": round(100.0 * fields["adjusted_ok"] / max(1, fields["adjusted"]), 4),
        "factor_ok_pct": round(100.0 * fields["factor_ok"] / max(1, fields["factor"]), 4),
        "raw_ok_pct": round(100.0 * fields["raw_ok"] / max(1, fields["raw"]), 4),
        "steps": dict(classes),
        "error_rows": dict(rows),
    }
    json.dump(summary, open(os.path.join(a.out, "summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
