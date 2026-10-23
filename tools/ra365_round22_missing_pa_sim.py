# -*- coding: utf-8 -*-
"""Round 22 diagnosis: what if every official same-date PA row were applied?

The official cache has rows the DB cannot hold because the table's primary key
is (ins_code, d_even).  This script adds the missing rows to the *existing*
factor series (post-hoc, no DB write) and measures adjusted parity against the
frozen live reference.  It is a hypothesis test, not a production fix.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sqlite3
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "p21", os.path.join(ROOT, "tools", "ra365_round21_live_parity.py"))
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)

CACHE_DIR = "D:/BorsTerminal-tmp/ra365_round16"
INS = {
    "595": "28253678449273505", "48315": "60235881999727383",
    "207": "65414507129586385", "325": "5317427172344706",
    "291": "58931793851445922", "599": "66830065858417081",
    "2672": "46700660505281786", "453": "46348559193224090",
    "149": "57875847776839336", "167": "65883838195688438",
    "182": "14073782708315535", "696": "14031158866706953",
    "183": "22667016906590506", "703": "25244329144808274",
}


def cache_rows():
    out = []
    for name in ("price_adjust_20000.json", "price_adjust_flow2.json"):
        p = os.path.join(CACHE_DIR, name)
        if not os.path.exists(p):
            continue
        d = json.load(open(p, encoding="utf-8"))
        for r in d.get("priceAdjust") or []:
            ins = str((r.get("instrument") or {}).get("insCode") or r.get("insCode") or "")
            try:
                out.append((ins, int(r["dEven"]), float(r["pClosing"]),
                            float(r["pClosingNotAdjusted"])))
            except (KeyError, TypeError, ValueError):
                continue
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=P.REF)
    ap.add_argument("--product", default=os.path.join(
        "D:/BorsTerminal-tmp/r21_live", "product_live_after"))
    ap.add_argument("--db", default=os.path.join(ROOT, "market.db"))
    ap.add_argument("--drop-small-unproven", action="store_true",
                    help="remove base-price gaps <1.5%% with no official PA/SC row")
    ap.add_argument("--out", default=os.path.join(ROOT, "artifacts", "ra365", "r22", "missing-pa-sim.json"))
    a = ap.parse_args()
    ref_doc, ref = P.load_ref()
    con = sqlite3.connect("file:%s?mode=ro" % a.db.replace("\\", "/"), uri=True)
    cr = cache_rows()
    by_ins = defaultdict(list)
    for row in cr:
        by_ins[row[0]].append(row)
    results = []
    for aid, sym in P.ASSETS.items():
        ic = INS.get(aid)
        if not ic:
            continue
        try:
            prod, meta = P.load_product(aid, a.product)
        except FileNotFoundError:
            continue
        if meta.get("priceBasis") != "last":
            continue
        db_rows = {(r[0], round(float(r[1]), 6), round(float(r[2]), 6))
                   for r in con.execute(
                       "SELECT d_even,p_closing,p_closing_not_adjusted "
                       "FROM price_adjust_events WHERE ins_code=?", (ic,))}
        missing = []
        seen = set()
        for _ins, d_even, pc, pn in by_ins.get(ic, []):
            key = (d_even, round(pc, 6), round(pn, 6))
            if key in db_rows or key in seen or not pc or not pn:
                continue
            seen.add(key)
            ratio = pc / pn
            if abs(ratio - 1.0) <= 1e-9:
                continue
            missing.append((d_even, ratio, pc, pn))
        dates = [r["date"] for r in prod]
        def eff(d_even):
            s = "%04d-%02d-%02d" % (d_even // 10000, (d_even // 100) % 100, d_even % 100)
            return next((t for t in dates if t >= s), None)
        evs = [(eff(d), r) for d, r, pc, pn in missing if eff(d)]
        official_dates = [r[0] for r in con.execute(
            "SELECT d_even FROM price_adjust_events WHERE ins_code=? "
            "UNION SELECT d_even FROM share_change_events WHERE ins_code=?", (ic, ic))]
        drops = []
        if a.drop_small_unproven:
            import datetime as _dt
            def _dd(a, b):
                try:
                    return abs((_dt.date.fromisoformat(a) - _dt.date.fromisoformat(b)).days)
                except Exception:
                    return 9999
            off_iso = ["%04d-%02d-%02d" % (x // 10000, (x // 100) % 100, x % 100)
                       for x in official_dates]
            payload = json.load(open(os.path.join(a.product, aid + ".json"), encoding="utf-8"))
            date_counts = defaultdict(int)
            for e in payload.get("adjustEvents") or []:
                date_counts[str(e.get("date"))[:10]] += 1
            for e in payload.get("adjustEvents") or []:
                if e.get("source") != "base-price-discontinuity":
                    continue
                try:
                    r = float(e.get("ratio") or 0)
                except (TypeError, ValueError):
                    continue
                ed = str(e.get("date"))[:10]
                if not (0.985 < r < 1.0) or not ed:
                    continue
                if date_counts[ed] > 1:
                    continue
                if any(_dd(ed, od) <= 30 for od in off_iso):
                    continue
                drops.append((ed, r))
        # current and corrected factor
        before = {r["date"]: r["factor"] for r in prod}
        after = {}
        for r in prod:
            t = r["date"]
            f = r["factor"]
            for ed, ratio in evs:
                if ed > t:
                    f *= ratio
            for ed, ratio in drops:
                if ed > t:
                    f /= ratio
            after[t] = f
        # adjusted close/high/low/open
        def parity(fmap):
            bars = ref.get((aid, "type7", "D")) or []
            rm = {b["utc"][:10]: b for b in bars}
            n = ok = okc = 0
            for r in prod:
                rb = rm.get(r["date"])
                if not rb:
                    continue
                n += 1
                vals = {
                    "o": round((r["open"] or 0) * fmap[r["date"]], 4),
                    "h": round((r["high_raw"] or 0) * fmap[r["date"]], 4),
                    "l": round((r["low_raw"] or 0) * fmap[r["date"]], 4),
                    "c": round((r["close"] or 0) * fmap[r["date"]], 4),
                }
                rv = {"o": rb["o"], "h": rb["h"], "l": rb["l"], "c": rb["c"]}
                hit = all(P.price_status(rv[k], vals[k]) in ("EXACT", "TOLERANCE")
                          for k in ("o", "h", "l", "c"))
                ok += hit
                okc += P.price_status(rv["c"], vals["c"]) in ("EXACT", "TOLERANCE")
            return n, ok, okc
        n0, ok0, c0 = parity(before)
        n1, ok1, c1 = parity(after)
        results.append({
            "asset_id": aid, "symbol": sym, "paired": n0,
            "missing_rows": len(missing), "events": len(evs),
            "row_tol_before": round(100.0 * ok0 / n0, 4) if n0 else None,
            "row_tol_after": round(100.0 * ok1 / n0, 4) if n0 else None,
            "close_tol_before": round(100.0 * c0 / n0, 4) if n0 else None,
            "close_tol_after": round(100.0 * c1 / n0, 4) if n0 else None,
            "missing": [[d, round(r, 8)] for d, r, _pc, _pn in missing],
            "drops": [[d, round(r, 8)] for d, r in drops],
        })
    tot0 = sum(r["row_tol_before"] / 100 * r["paired"] for r in results)
    tot1 = sum(r["row_tol_after"] / 100 * r["paired"] for r in results)
    n = sum(r["paired"] for r in results)
    out = {"baseline_row_tol": round(100 * tot0 / n, 4),
           "corrected_row_tol": round(100 * tot1 / n, 4),
           "paired": n, "series": results}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in results:
        print(f"{r['symbol']:8s} missing {r['missing_rows']:2d} events {r['events']:2d} "
              f"row_tol {r['row_tol_before']:6.2f} -> {r['row_tol_after']:6.2f} "
              f"close {r['close_tol_before']:6.2f} -> {r['close_tol_after']:6.2f}")
    print("TOTAL", out["baseline_row_tol"], "->", out["corrected_row_tol"], "paired", n)


if __name__ == "__main__":
    main()
