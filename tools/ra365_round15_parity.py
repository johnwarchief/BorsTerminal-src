# -*- coding: utf-8 -*-
"""Fast production-path parity runner: preload DB events, stream products.

The per-symbol chart functions are replaced with in-memory lookups.  The PA
ratio uses the product candle's `closing` on the mapped date (same field the
chart shows); this is validated against the slow production path on samples.
"""
import argparse
import csv
import datetime as _dt
import importlib.util
import json
import os
import sqlite3
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WT = ROOT
BASE = os.path.dirname(os.path.dirname(ROOT))
REF = os.path.join(BASE, "_scratch", "ra_fup_2026_10_20", "ref_bars_v2.jsonl")
MAN = os.path.join(ROOT, "_audit", "RAHAVARD-FULL-UNIVERSE-MANIFEST-v2-2026-10-20.csv")
PROD = os.path.join(BASE, "_scratch", "ra_round3", "product_live_final_v4.jsonl")

spec = importlib.util.spec_from_file_location(
    "parity", os.path.join(WT, "tools", "ra_full_universe_parity.py"))
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)


def iso(d):
    s = str(d)
    return f"{s[:4]}-{s[4:6]}-{s[6:]}" if len(s) == 8 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ref", default=REF)
    ap.add_argument("--manifest", default=MAN)
    ap.add_argument("--product", default=PROD)
    ap.add_argument("--symbols", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-source-ratio", action="store_true",
                    help="omit the official source-ratio witness (pre-fix baseline)")
    ap.add_argument("--share-gap-window", type=int, default=0,
                    help="override _SHARE_GAP_WINDOW_DAYS for an A/B measurement")
    a = ap.parse_args()
    use_source_ratio = not a.no_source_ratio
    os.makedirs(a.out, exist_ok=True)
    os.environ["BORS_DB"] = a.db
    os.environ["BORS_NO_FETCH_LOOPS"] = "1"
    sys.path.insert(0, WT)
    import api.chart as CH
    CH.DB_PATH = a.db
    if a.share_gap_window:
        CH._SHARE_GAP_WINDOW_DAYS = a.share_gap_window

    con = sqlite3.connect("file:%s?mode=ro" % a.db.replace("\\", "/"), uri=True)
    ins2sym = {}
    sym2ins = {}
    for ins, sym in con.execute("SELECT ins_code,l_val18 FROM instruments"):
        ins2sym[str(ins)] = sym
        sym2ins.setdefault(sym, str(ins))
    fund = {}
    for row in con.execute("SELECT ins_code,d_even,unit_profit,reference_price,ratio,source,"
                           "profit_date,source_id FROM fund_profit_events"):
        fund.setdefault(str(row[0]), []).append(row)
    pa = {}
    for row in con.execute("SELECT ins_code,d_even,p_closing,p_closing_not_adjusted,ratio,source"
                           " FROM price_adjust_events ORDER BY d_even"):
        pa.setdefault(str(row[0]), []).append(row[1:])
    sc = {}
    for ins, d, r in con.execute("SELECT ins_code,d_even,ratio FROM share_change_events"):
        if r is not None and abs(float(r) - 1.0) > 1e-9:
            sc.setdefault(str(ins), []).append((iso(d), float(r)))
    for _ins in list(sc):
        sc[_ins] = CH._filter_share_changes(sc[_ins])
    # The real chart path reads the DPS base from price_history.close; preload
    # it once so the evaluator uses the same source instead of candle closing.
    hist = {}
    for sym, d, c in con.execute("SELECT symbol,date,close FROM price_history"):
        if sym and d and c is not None:
            hist[(sym, str(d)[:10])] = float(c)
    has_evidence = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='share_type_evidence'"
    ).fetchone()
    evidence = None
    if has_evidence:
        evidence = {}
        for ins, d in con.execute(
                "SELECT ins_code,d_even FROM share_type_evidence WHERE no_cash=1"):
            dt = iso(d)
            if dt:
                evidence.setdefault(str(ins), set()).add(dt)
    con.close()

    man = {}
    for r in csv.DictReader(open(a.manifest, encoding="utf-8-sig")):
        if r.get("ra_asset_id"):
            man.setdefault(r["symbol"], r)
    ref_all = P.load_ref(a.ref)
    # Two-pass variant selection: one product record per asset (longest series),
    # matching the 2,965-asset universe instead of counting symbol variants.
    best = {}
    for line in open(a.product, encoding="utf-8"):
        j = json.loads(line)
        sym = j.get("symbol")
        m = man.get(sym)
        if not m:
            continue
        aid = str(m["ra_asset_id"])
        n = len(j.get("candles") or [])
        if aid not in best or n > best[aid][0]:
            best[aid] = (n, sym)
    keep = {sym for _n, sym in best.values()}
    if a.symbols:
        want = {x.strip() for x in a.symbols.split(",") if x.strip()}
        keep &= want
    print("assets", len(keep), flush=True)

    state = {"pa": {}, "fund": {}, "sc": {}}
    CH._official_price_adjust_events = lambda sym, times=None, share_changes=None, closings=None: state["pa"].get(sym, [])
    CH._fund_profit_events = lambda sym: state["fund"].get(sym, [])
    CH._share_change_events = lambda sym: state["sc"].get(sym, [])
    if evidence is None:
        CH._share_type_evidence_dates = lambda sym: None
    else:
        CH._share_type_evidence_dates = lambda sym: evidence.get(sym2ins.get(sym), set())
    CH._ledger_coverage = lambda *args, **kwargs: {}

    totals = Counter()
    factor_all, func_all, norm_all, close_all = [], [], [], []
    step_rows = []
    sym_rows = []
    n = 0
    for line in open(a.product, encoding="utf-8"):
        p = json.loads(line)
        sym = p.get("symbol")
        if sym not in keep:
            continue
        m = man.get(sym)
        if not m:
            continue
        n += 1
        if a.limit and n > a.limit:
            break
        aid = str(m["ra_asset_id"])
        r0 = (ref_all.get(f"{aid}|type0|D") or {}).get("bars") or []
        r7 = (ref_all.get(f"{aid}|type7|D") or {}).get("bars") or []
        times = [c["time"] for c in p.get("candles") or []]
        if not times or not r0 or not r7:
            continue
        merged = {}
        for c in p.get("candles") or []:
            merged[c["time"]] = {"open": c.get("open"), "high": c.get("high"),
                                 "low": c.get("low"), "close": c.get("close"),
                                 "closing": c.get("closing"), "last": c.get("last"),
                                 "volume": 0.0}
        for v in p.get("volumes") or []:
            if v.get("time") in merged:
                merged[v["time"]]["volume"] = v.get("value", 0.0)
        ins = sym2ins.get(sym)
        close_map = {c["time"]: c.get("closing") for c in (p.get("candles") or [])}
        tset = sorted(times)
        # PA events, mapped to the first candle >= d_even; ratio from closing.
        pa_events = []
        scs = sc.get(ins, [])
        for d, pc, pn, stored, src in pa.get(ins, []):
            dt = iso(d)
            if not dt:
                continue
            nxt = next((t for t in tset if t >= dt), None)
            if not nxt:
                continue
            try:
                dps = float(pn) - float(pc)
            except Exception:
                dps = None
            cl = close_map.get(nxt) or hist.get((sym, nxt))
            ratio = float(stored) if stored is not None else None
            rec = {"date": nxt, "source": src or "priceAdjust",
                   "_ledger_key": (dt, "priceAdjust")}
            if use_source_ratio:
                rec["_source_ratio"] = (float(pc) / float(pn)
                                        if pc and pn and float(pn) > 0 else None)
            near = None
            for sd, sr in scs:
                try:
                    diff = abs((_dt.date.fromisoformat(sd) -
                                _dt.date.fromisoformat(dt)).days)
                except Exception:
                    continue
                if diff <= 10 and (near is None or diff < near[0]):
                    near = (diff, sr)
            dps_ratio = (float(cl) / (float(cl) + dps)
                         if dps and dps > 0 and cl and float(cl) > 0 else None)
            if near:
                if ratio is None and pc and pn:
                    ratio = float(pc) / float(pn)
                sr = float(near[1])
                cap_err = abs(ratio / sr - 1.0)
                comb_err = (abs(ratio / (sr * dps_ratio) - 1.0)
                            if dps_ratio else 9.0)
                if comb_err < cap_err and comb_err <= 0.02:
                    rec["_event_type"] = "combined"
                elif cap_err <= 0.02:
                    rec["_event_type"] = "capital"
                elif dps_ratio is not None:
                    ratio = dps_ratio
                    rec["_dps"] = True
                    rec["dividend_per_share"] = dps
            elif dps_ratio is not None:
                ratio = dps_ratio
                rec["_dps"] = True
                rec["dividend_per_share"] = dps
            if ratio is not None:
                rec["ratio"] = round(ratio, 10)
                pa_events.append(rec)
        state["pa"][sym] = pa_events
        fund_events = []
        for (fins, d, unit, refp, ratio, src, pdate, sid) in fund.get(ins, []):
            dt = iso(d)
            if not dt or unit is None or refp is None:
                continue
            fund_events.append({"date": dt, "kind": CH.AE.KIND_CASH_DIVIDEND,
                                "reference_price": float(refp),
                                "dividend_per_share": float(unit),
                                "ratio": float(ratio) if ratio is not None else None,
                                "source": src or "fund-portal", "profit_date": pdate,
                                "source_id": sid})
        state["fund"][sym] = fund_events
        state["sc"][sym] = sc.get(ins, [])
        try:
            applied, rej, factors, chain, cov = CH._canonical_adjustment(
                sym, times, [dict(e) for e in (p.get("adjustEvents") or [])])
        except Exception as e:
            sym_rows.append({"symbol": sym, "asset_id": aid, "status": "ERROR:" + str(e)[:100]})
            continue
        fac = dict(zip(times, factors))
        basis = p.get("priceBasis") or "last"
        cmp = P.compare_series(merged, fac, r0, r7, basis)
        fd = [x for x in cmp["factor_diffs"] if x is not None]
        nd = [x for x in cmp["factor_norm_diffs"] if x is not None]
        fok = sum(1 for x in fd if x <= P.FACTOR_ROUND)
        fnear = sum(1 for x in fd if x <= P.FACTOR_NEAR)
        nok = sum(1 for x in nd if x <= P.FACTOR_ROUND)
        nnear = sum(1 for x in nd if x <= P.FACTOR_NEAR)
        func_ok = sum(v for (f, s), v in cmp["func_counts"].items()
                      if s in ("MATCH", "ROUNDING_ONLY"))
        func_cmp = sum(cmp["func_counts"].values())
        fc = cmp["field_counts"]
        raw_cmp = sum(v for (f, s), v in fc.items()
                      if f != "factor" and not s.startswith("MISSING")
                      and not s.endswith("_RANGE_STARTS_LATER")
                      and not s.endswith("_RANGE_ENDS_EARLIER"))
        raw_ok = sum(v for (f, s), v in fc.items()
                     if f != "factor" and not s.startswith("MISSING")
                     and not s.endswith("_RANGE_STARTS_LATER")
                     and not s.endswith("_RANGE_ENDS_EARLIER")
                     and s in ("MATCH", "ROUNDING_ONLY"))
        missing_p = sum(v for (f, s), v in fc.items() if s == "MISSING_PRODUCT_CANDLE")
        missing_r = sum(v for (f, s), v in fc.items() if s == "MISSING_REFERENCE_CANDLE")
        totals["factor_cmp"] += len(fd); totals["factor_ok"] += fok; totals["factor_near"] += fnear
        totals["norm_cmp"] += len(nd); totals["norm_ok"] += nok; totals["norm_near"] += nnear
        totals["func_cmp"] += func_cmp; totals["func_ok"] += func_ok
        totals["raw_cmp"] += raw_cmp; totals["raw_ok"] += raw_ok
        totals["missing_p"] += missing_p; totals["missing_r"] += missing_r
        totals["assets"] += 1
        factor_all.extend(fd); func_all.extend(cmp["func_diffs"]); norm_all.extend(nd)
        close_all.extend(x for x in cmp["close_diffs"] if x is not None)
        dates = sorted(cmp["factor_by_date"])
        rf = [cmp["factor_by_date"][d][0] for d in dates]
        pf = [cmp["factor_by_date"][d][1] for d in dates]
        rs = P.steps(dates, rf); ps = P.steps(dates, [x if x is not None else 0 for x in pf])
        used = set(); pairs = ref_only = prod_only = bad = 0
        import datetime as dt
        for s in rs:
            sd = dt.date.fromisoformat(s["date"]); best = None
            for j, t in enumerate(ps):
                if j in used:
                    continue
                dd = abs((dt.date.fromisoformat(t["date"]) - sd).days)
                if dd <= P.STEP_DAYS and abs(t["ratio"] / s["ratio"] - 1) <= P.STEP_RATIO_PAIR:
                    if best is None or dd < best[0]:
                        best = (dd, j)
            if best:
                used.add(best[1]); pairs += 1
                t = ps[best[1]]
                rd = abs(t["ratio"] / s["ratio"] - 1)
                if rd > P.FACTOR_NEAR:
                    bad += 1
                step_rows.append({"symbol": sym, "asset_id": aid, "ref_date": s["date"],
                                  "prod_date": t["date"], "ref_ratio": round(s["ratio"], 8),
                                  "prod_ratio": round(t["ratio"], 8), "ratio_diff": round(rd, 8),
                                  "kind": "PAIR"})
            else:
                ref_only += 1
                step_rows.append({"symbol": sym, "asset_id": aid, "ref_date": s["date"],
                                  "prod_date": "", "ref_ratio": round(s["ratio"], 8),
                                  "prod_ratio": "", "ratio_diff": "", "kind": "REF_ONLY"})
        for j, t in enumerate(ps):
            if j not in used:
                prod_only += 1
                step_rows.append({"symbol": sym, "asset_id": aid, "ref_date": "",
                                  "prod_date": t["date"], "ref_ratio": "",
                                  "prod_ratio": round(t["ratio"], 8), "ratio_diff": "",
                                  "kind": "PROD_ONLY"})
        totals["pairs"] += pairs; totals["ref_only"] += ref_only
        totals["prod_only"] += prod_only; totals["bad"] += bad
        sym_rows.append({
            "symbol": sym, "asset_id": aid, "adjust_source": p.get("adjustSource"),
            "common": cmp["common"], "factor_ok": fok, "factor_near": fnear,
            "factor_cmp": len(fd), "norm_ok": nok, "norm_near": nnear,
            "func_ok": func_ok, "func_cmp": func_cmp, "raw_ok": raw_ok,
            "raw_cmp": raw_cmp, "events_applied": len(applied),
            "ref_only": ref_only, "prod_only": prod_only, "pairs": pairs, "bad": bad,
        })
        if totals["assets"] % 250 == 0:
            print("  %d assets" % totals["assets"], flush=True)

    summary = {
        "assets_measured": totals["assets"],
        "live_factor_compared_dates": totals["factor_cmp"],
        "live_factor_ok_dates": totals["factor_ok"],
        "live_factor_near_dates": totals["factor_near"],
        "live_factor_ok_pct": round(100.0 * totals["factor_ok"] / max(1, totals["factor_cmp"]), 4),
        "live_factor_near_pct": round(100.0 * totals["factor_near"] / max(1, totals["factor_cmp"]), 4),
        "live_factor_norm_ok_dates": totals["norm_ok"],
        "live_factor_norm_near_dates": totals["norm_near"],
        "live_factor_norm_ok_pct": round(100.0 * totals["norm_ok"] / max(1, totals["norm_cmp"]), 4),
        "live_factor_norm_near_pct": round(100.0 * totals["norm_near"] / max(1, totals["norm_cmp"]), 4),
        "live_func_compared_fields": totals["func_cmp"],
        "live_func_ok_fields": totals["func_ok"],
        "live_func_ok_pct": round(100.0 * totals["func_ok"] / max(1, totals["func_cmp"]), 4),
        "live_raw_compared_fields": totals["raw_cmp"],
        "live_raw_ok_fields": totals["raw_ok"],
        "live_raw_ok_pct": round(100.0 * totals["raw_ok"] / max(1, totals["raw_cmp"]), 4),
        "missing_product_candles": totals["missing_p"],
        "missing_reference_candles": totals["missing_r"],
        "ref_only_steps": totals["ref_only"], "prod_only_steps": totals["prod_only"],
        "step_pairs": totals["pairs"], "step_ratio_mismatch": totals["bad"],
        "close_p50": P.pct(close_all, 0.5), "close_p95": P.pct(close_all, 0.95),
        "close_max": max(close_all) if close_all else None,
        "factor_p50": P.pct(factor_all, 0.5), "factor_p95": P.pct(factor_all, 0.95),
        "factor_max": max(factor_all) if factor_all else None,
        "norm_p50": P.pct(norm_all, 0.5), "norm_p95": P.pct(norm_all, 0.95),
        "norm_max": max(norm_all) if norm_all else None,
        "func_p50": P.pct(func_all, 0.5), "func_p95": P.pct(func_all, 0.95),
        "func_max": max(func_all) if func_all else None,
        "db": a.db,
        "method": "production-path-preloaded; source_ratio=%s" % use_source_ratio,
    }
    json.dump(summary, open(os.path.join(a.out, "parity_summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    with open(os.path.join(a.out, "parity_symbols.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=sorted({k for r in sym_rows for k in r}))
        w.writeheader(); w.writerows(sym_rows)
    with open(os.path.join(a.out, "parity_steps.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["symbol", "asset_id", "ref_date", "prod_date",
                                          "ref_ratio", "prod_ratio", "ratio_diff", "kind"])
        w.writeheader(); w.writerows(step_rows)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
