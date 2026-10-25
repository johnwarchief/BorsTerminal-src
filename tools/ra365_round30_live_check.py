#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 30 Stage D: live /api/chart handler vs the canonical replay.

For each captured live payload and its replay payload, compares:
  * the factor chain on common dates after re-anchoring at the last common date
    (max relative difference, exact matches),
  * the applied event set (date/source/ratio),
  * adjusted row parity against the frozen reference under the canonical
    widen field set.
The live capture uses BORS_DB=<isolated copy>; this checker is read-only.

Usage:
  python tools/ra365_round30_live_check.py --live <dir> --replay <dirs> \
      --ref <ref.jsonl> --cohort <cohort.jsonl> --out <csv>
"""
import argparse
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from ra365_round30_attribution import (  # noqa: E402
    bar_tuple, fnum, load_ref_only_d, row_passes)

TOL = 0.5
REL = 1e-6


def rows_of(payload):
    out = {}
    for c in payload.get("candles") or []:
        d = str(c.get("time"))[:10]
        if not d:
            continue
        out[d] = (fnum(c.get("open")), fnum(c.get("high")),
                  fnum(c.get("low")),
                  fnum(c.get("last")) or fnum(c.get("close")))
    return out


def factors_of(payload):
    return {str(f.get("time"))[:10]: fnum(f.get("factor"))
            for f in (payload.get("factors") or []) if fnum(f.get("factor"))}


def parity(payload, ref0, ref7):
    rows = rows_of(payload)
    fac = factors_of(payload)
    common = sorted(set(rows) & set(fac) & set(ref0) & set(ref7))
    if len(common) < 10:
        return None
    scale = fac[common[-1]] or 1.0
    ok = n = 0
    for d in common:
        f = fac[d] / scale
        p = tuple(v * f if v is not None else None for v in rows[d])
        n += 1
        if row_passes(p, ref7[d]):
            ok += 1
    return (100.0 * ok / max(1, n), n, common, fac, scale, rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", required=True)
    ap.add_argument("--replay", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--cohort", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    sym2aid = {}
    for line in open(a.cohort, encoding="utf-8"):
        d = json.loads(line)
        sym2aid[d.get("symbol")] = str(d.get("ra_asset_id"))
    replay = {}
    for root in a.replay.split(","):
        if not os.path.isdir(root):
            continue
        for fn in os.listdir(root):
            if fn.endswith(".json") and fn[:-5].isdigit():
                aid = fn[:-5]
                if aid not in replay:
                    try:
                        replay[aid] = json.load(open(os.path.join(root, fn),
                                                     encoding="utf-8"))
                    except Exception:
                        pass
    ref = load_ref_only_d(a.ref)
    out = []
    for fn in sorted(os.listdir(a.live)):
        if not fn.endswith(".json"):
            continue
        sym = fn[:-5]
        aid = sym2aid.get(sym)
        live = json.load(open(os.path.join(a.live, fn), encoding="utf-8"))
        rep = replay.get(aid)
        if not rep or aid not in ref:
            out.append({"symbol": sym, "asset_id": aid or "", "state": "NO_REPLAY"})
            continue
        t0 = ref[aid].get("type0") or {}
        t7 = ref[aid].get("type7") or {}
        lp = parity(live, t0, t7)
        rp = parity(rep, t0, t7)
        if not lp or not rp:
            out.append({"symbol": sym, "asset_id": aid, "state": "NOT_COMPARABLE"})
            continue
        lf, rf = lp[3], rp[3]
        common = sorted(set(lf) & set(rf) & set(lp[2]))
        rel = [abs(lf[d] / rf[d] - 1.0) for d in common if rf.get(d)]
        le = {(str(e.get("date"))[:10], str(e.get("source")),
               round(float(e.get("ratio") or 0), 8))
              for e in (live.get("adjustEvents") or [])}
        re_ = {(str(e.get("date"))[:10], str(e.get("source")),
                round(float(e.get("ratio") or 0), 8))
               for e in (rep.get("adjustEvents") or [])}
        out.append({
            "symbol": sym, "asset_id": aid, "state": "OK",
            "live_candles": len(live.get("candles") or []),
            "replay_candles": len(rep.get("candles") or []),
            "common_factor_dates": len(common),
            "factor_max_rel": round(max(rel), 10) if rel else "",
            "factor_exact": sum(1 for x in rel if x <= 1e-9),
            "factor_tol": sum(1 for x in rel if x <= 1e-6),
            "live_adj_row": round(lp[0], 4),
            "replay_adj_row": round(rp[0], 4),
            "row_delta": round(lp[0] - rp[0], 4),
            "events_live": len(le), "events_replay": len(re_),
            "events_only_live": len(le - re_),
            "events_only_replay": len(re_ - le),
        })
    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]) if out else
                           ["symbol", "asset_id", "state"])
        w.writeheader(); w.writerows(out)
    ok = [r for r in out if r.get("state") == "OK"]
    print(json.dumps({"symbols": len(out), "ok": len(ok),
                      "live_adj_mean": round(sum(r["live_adj_row"] for r in ok) /
                                             max(1, len(ok)), 4),
                      "replay_adj_mean": round(sum(r["replay_adj_row"] for r in ok) /
                                               max(1, len(ok)), 4),
                      "identical_factors": sum(1 for r in ok
                                               if r["factor_max_rel"] == 0),
                      "rows": out}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
