#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 25: replay a fix on a frozen product snapshot (same raw candles).

The live TSETMC feed flips between revisions, so a fresh export cannot
isolate a code change. This tool keeps every frozen product payload's raw
candles and re-derives `factors` from its applied events after applying the
Round 25 share-leg dedupe. Symbols whose events do not change must come out
byte-identical (validated before any write).

Usage:
  python tools/ra365_round25_replay.py --product <dir> --db <market.db> --out <dir>
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import adjustment_engine as AE  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dps-combined", action="store_true",
                    help="apply the engine's combined-action DPS rule (official ratio)")
    a = ap.parse_args()
    os.environ["BORS_DB"] = a.db
    os.environ.setdefault("BORS_NO_FETCH_LOOPS", "1")
    import api.chart as C
    C.DB_PATH = a.db
    os.makedirs(a.out, exist_ok=True)
    changed = []
    bad = []
    for fn in sorted(os.listdir(a.product)):
        if not fn.endswith(".json"):
            continue
        doc = json.load(open(os.path.join(a.product, fn), encoding="utf-8"))
        sym = doc.get("symbol_request")
        events = [dict(e) for e in (doc.get("adjustEvents") or []) if e.get("date")]
        sc = C._share_change_events(sym) if sym else []
        kept, dropped = C._drop_share_leg_of_observed_gap(events, sc)
        edited = bool(dropped)
        if a.dps_combined:
            import sqlite3
            conn = sqlite3.connect("file:%s?mode=ro" % a.db.replace("\\", "/"), uri=True)
            try:
                ins = conn.execute("select ins_code from instruments where l_val18=? limit 1",
                                   (sym,)).fetchone()
                off = conn.execute(
                    "select d_even,ratio,p_closing,p_closing_not_adjusted from"
                    " price_adjust_event_rows where ins_code=?", (ins[0],)).fetchall() if ins else []
            finally:
                conn.close()
            def _d2i(x):
                s = str(x).replace("-", "")
                return int(s)
            new = []
            for e in kept:
                dps = e.get("dividend_per_share")
                if dps is None:
                    new.append(e)
                    continue
                try:
                    dps = float(dps)
                except (TypeError, ValueError):
                    new.append(e)
                    continue
                dt = str(e.get("date"))[:10]
                cand = [o for o in off
                        if o[1] and o[2] and o[3]
                        and abs((o[3] - o[2]) - dps) <= max(0.5, 0.001 * dps)
                        and abs(o[0] - _d2i(dt)) <= 45]
                if not cand:
                    new.append(e)
                    continue
                o = min(cand, key=lambda x: abs(x[0] - _d2i(dt)))
                oro = float(o[1])
                if C._combined_dps_official_ratio(e.get("ratio"), oro, dt, sc) is not None:
                    e = dict(e)
                    e["ratio_before_combined"] = e.get("ratio")
                    e["ratio"] = oro
                    e["combined_share_leg"] = True
                    edited = True
                new.append(e)
            kept = new
        dates = [str(c.get("time"))[:10] for c in (doc.get("candles") or [])]
        wrapped = []
        for e in kept:
            r = float(e.get("ratio") or 0)
            if r <= 0:
                continue
            wrapped.append({"date": str(e["date"])[:10], "kind": AE.KIND_SOURCE_RATIO, "ratio": r})
        facs, _prov = AE.chain_factors(dates, wrapped)
        old = {str(f.get("time"))[:10]: f.get("factor") for f in (doc.get("factors") or [])}
        diffs = [d for d, f in zip(dates, facs) if old.get(d) is not None and abs(old[d] - f) > 1e-9]
        if not edited and diffs:
            bad.append((doc.get("symbol_request"), len(diffs), diffs[:2]))
            continue
        if dropped:
            changed.append({"symbol": sym, "dropped": dropped, "factor_rows_changed": len(diffs)})
        doc["factors"] = [{"time": d, "factor": f} for d, f in zip(dates, facs)]
        doc["adjustEvents"] = kept
        doc["adjustRejected"] = list(doc.get("adjustRejected") or []) + dropped
        doc["replay"] = {"source_product": a.product, "rule": "round25-share-leg-dedupe"}
        json.dump(doc, open(os.path.join(a.out, fn), "w", encoding="utf-8"), ensure_ascii=False)
    print(json.dumps({"changed": changed, "unchanged_mismatch": bad}, ensure_ascii=False, indent=1))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
