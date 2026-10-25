#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 30: before/after payload and audit comparison.

Compares two full-universe capture directories on common candle dates and
joins the canonical D/W/M audits.  Reports every factor-changed symbol, its
event-set change, the largest relative factor move, and the row-parity
direction; checks a supplied control list for zero movement.

Usage:
  python tools/ra365_round30_compare.py --before <dirs> --after <dirs> \
      --audit-before <per-asset.csv> --audit-after <per-asset.csv> \
      --out <dir> [--controls <r29 controls.csv>]
"""
import argparse
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from ra365_round30_attribution import fnum  # noqa: E402


def payloads(dirs):
    out = {}
    for root in dirs.split(","):
        if not os.path.isdir(root):
            continue
        for fn in os.listdir(root):
            if fn.endswith(".json") and fn[:-5].isdigit() and fn[:-5] not in out:
                out[fn[:-5]] = os.path.join(root, fn)
    return out


def fac(p):
    return {str(f.get("time"))[:10]: fnum(f.get("factor"))
            for f in (p.get("factors") or []) if fnum(f.get("factor"))}


def evs(p):
    return {(str(e.get("date"))[:10], str(e.get("source")),
             round(float(e.get("ratio") or 0), 8))
            for e in (p.get("adjustEvents") or [])}


def audit(path):
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        out[str(r["asset_id"])] = r
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--audit-before", required=True)
    ap.add_argument("--audit-after", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--controls", default="")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    before, after = payloads(a.before), payloads(a.after)
    ab, aa = audit(a.audit_before), audit(a.audit_after)
    controls = set()
    if a.controls and os.path.exists(a.controls):
        for r in csv.DictReader(open(a.controls, encoding="utf-8-sig")):
            controls.add(str(r.get("symbol") or ""))
    rows = []
    for aid in sorted(set(before) & set(after), key=lambda x: int(x)):
        try:
            pb = json.load(open(before[aid], encoding="utf-8"))
            pa = json.load(open(after[aid], encoding="utf-8"))
        except Exception:
            continue
        fb, fa = fac(pb), fac(pa)
        common = sorted(set(fb) & set(fa))
        rel = [abs(fa[d] / fb[d] - 1.0) for d in common if fb.get(d)]
        max_rel = max(rel) if rel else 0.0
        eb, ea = evs(pb), evs(pa)
        rb, ra = ab.get(aid, {}), aa.get(aid, {})
        if not (max_rel > 1e-12 or eb != ea):
            continue
        d_b = float(rb.get("D_adj_row") or 0)
        d_a = float(ra.get("D_adj_row") or 0)
        w_b = float(rb.get("W_adj_row") or 0)
        w_a = float(ra.get("W_adj_row") or 0)
        m_b = float(rb.get("M_adj_row") or 0)
        m_a = float(ra.get("M_adj_row") or 0)
        delta = (d_a - d_b) + (w_a - w_b) + (m_a - m_b)
        rows.append({
            "symbol": pa.get("symbol") or pb.get("symbol"),
            "asset_id": aid,
            "factor_changed": int(max_rel > 1e-12),
            "factor_max_rel": round(max_rel, 10),
            "events_added": len(ea - eb),
            "events_removed": len(eb - ea),
            "D_before": round(d_b, 4), "D_after": round(d_a, 4),
            "W_before": round(w_b, 4), "W_after": round(w_a, 4),
            "M_before": round(m_b, 4), "M_after": round(m_a, 4),
            "D_delta": round(d_a - d_b, 4),
            "W_delta": round(w_a - w_b, 4),
            "M_delta": round(m_a - m_b, 4),
            "direction": ("IMPROVED" if delta > 1e-6 else
                          "WORSENED" if delta < -1e-6 else "UNCHANGED"),
            "control": int((pa.get("symbol") or "") in controls),
        })
    with open(os.path.join(a.out, "changed-symbols.csv"), "w",
              encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else
                           ["symbol", "asset_id", "direction"])
        w.writeheader(); w.writerows(rows)
    changed = [r for r in rows if r["factor_changed"]]
    ctrl = [r for r in rows if r["control"]]
    summary = {
        "assets_compared": len(set(before) & set(after)),
        "changed_rows": len(rows),
        "factor_changed": len(changed),
        "improved": sum(1 for r in rows if r["direction"] == "IMPROVED"),
        "worsened": sum(1 for r in rows if r["direction"] == "WORSENED"),
        "unchanged": sum(1 for r in rows if r["direction"] == "UNCHANGED"),
        "controls_touched": len(ctrl),
        "controls_moved": sum(1 for r in ctrl if r["factor_changed"] or
                              r["direction"] != "UNCHANGED"),
        "worsened_symbols": [r["symbol"] for r in rows
                             if r["direction"] == "WORSENED"],
    }
    json.dump(summary, open(os.path.join(a.out, "summary.json"), "w",
                            encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
