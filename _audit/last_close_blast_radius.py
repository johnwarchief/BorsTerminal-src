# -*- coding: utf-8 -*-
"""Blast-radius measurement: daily-candle close = «قیمت پایانی» (CLOSE) → «آخرین قیمت» (LAST).

MEASUREMENT ONLY. Edits nothing. Reads a COPY of the live market.db
(_audit/last_blast_radius/market_copy.db) and the official TSETMC CSV.
Runs the REAL engine (api/chart.py `_fts_*`) over two candle series built
from the same fetched rows:
    A = baseline  : close = CLOSE   (what production does today)
    B = candidate : close = LAST    (the owner's decision under test)

Both series are ADJUSTED the way production adjusts (back-adjustment from
base-price discontinuity, `_adjust_events_from_rows`), each computed from
its OWN close definition — so metric "adjustment drift" is measured, not assumed.

Re-run (network-free after first pass):
    cd <repo> && PYTHONIOENCODING=utf-8 python -X utf8 _audit/last_close_blast_radius.py [--limit 800]
Outputs (all under _audit/last_blast_radius/):
    sample.json        fixed deterministic 800-symbol list
    csv_cache/<ins>.csv  cached TSETMC CSVs (fetch once, reuse forever)
    partial.jsonl      per-symbol measured record (resumable; delete to redo)
    report.json        aggregate table + top-flip symbols + risks + examples
    fetch_stats.json   cost: fetches, bytes, wall time
"""
import argparse
import datetime
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

WORK = os.path.join(HERE, "last_blast_radius")
DB_COPY = os.path.join(WORK, "market_copy.db")
CSV_DIR = os.path.join(WORK, "csv_cache")
SAMPLE_PATH = os.path.join(WORK, "sample.json")
PARTIAL_PATH = os.path.join(WORK, "partial.jsonl")
REPORT_PATH = os.path.join(WORK, "report.json")
FETCH_STATS_PATH = os.path.join(WORK, "fetch_stats.json")

CSV_URL = ("https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyListCSV"
           "/{ins}/19900101")

import test_tsetmc as tt          # noqa: E402  (session + rate helper)
import api.chart as ch            # noqa: E402  (THE REAL engine)


# --------------------------------------------------------------------------
# 1) sample
# --------------------------------------------------------------------------
def build_sample(limit):
    if os.path.exists(SAMPLE_PATH):
        with open(SAMPLE_PATH, encoding="utf-8") as f:
            return json.load(f)
    import sqlite3
    c = sqlite3.connect(f"file:{DB_COPY}?mode=ro", uri=True)
    try:
        rows = c.execute(
            "SELECT symbol, COUNT(*) AS n FROM price_history "
            "GROUP BY symbol ORDER BY n DESC, symbol LIMIT ?", (limit,)).fetchall()
        sample, no_ins = [], []
        for sym, n in rows:
            r = c.execute(
                "SELECT ins_code FROM instruments "
                "WHERE l_val18 = ? OR l_val30 = ? "
                "ORDER BY updated_at DESC LIMIT 1", (sym, sym)).fetchone()
            if not r:
                no_ins.append(sym)
                continue
            first = c.execute("SELECT MIN(date), MAX(date) FROM price_history "
                              "WHERE symbol = ?", (sym,)).fetchone()
            sample.append({"symbol": sym, "ins_code": r[0], "ph_rows": n,
                           "ph_first": first[0], "ph_last": first[1]})
        meta = {"generated": datetime.date.today().isoformat(),
                "limit": limit, "total_symbols_in_db":
                c.execute("SELECT COUNT(DISTINCT symbol) FROM price_history").fetchone()[0],
                "skipped_no_ins_code": no_ins, "symbols": sample}
    finally:
        c.close()
    with open(SAMPLE_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return meta


# --------------------------------------------------------------------------
# 2) fetch (cached)
# --------------------------------------------------------------------------
def csv_path(ins):
    return os.path.join(CSV_DIR, f"{ins}.csv")


def fetch_all(samples, force=False):
    todo = [s for s in samples
            if force or not _valid_cache(csv_path(s["ins_code"]))]
    stats = {"fetched": 0, "bytes": 0, "from_cache": len(samples) - len(todo),
             "failed": [], "wall_s": 0.0}
    if todo:
        s = tt.make_session(min_interval=0.08)
        t0 = time.time()
        for i, item in enumerate(todo, 1):
            tt._rate_wait(s)
            try:
                r = s.get(CSV_URL.format(ins=item["ins_code"]),
                          headers=tt.HEADERS, timeout=90)
                text = r.text if r.status_code == 200 and \
                    text_ok(r) else None
            except Exception as e:
                text = None
                print(f"  fetch error {item['symbol']}: {type(e).__name__}: {e}")
            if text is None:
                stats["failed"].append(item["symbol"])
            else:
                with open(csv_path(item["ins_code"]), "w", encoding="utf-8") as f:
                    f.write(text)
                stats["fetched"] += 1
                stats["bytes"] += len(r.content)
            if i % 50 == 0:
                print(f"  [fetch] {i}/{len(todo)} "
                      f"({time.time() - t0:.0f}s, {stats['bytes'] / 1e6:.1f} MB)")
        stats["wall_s"] = round(time.time() - t0, 1)
    with open(FETCH_STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)
    return stats


def text_ok(r):
    try:
        return r.text.lstrip().startswith("<TICKER>")
    except Exception:
        return False


def _valid_cache(p):
    if not os.path.exists(p):
        return False
    try:
        with open(p, encoding="utf-8") as f:
            return f.readline().lstrip().startswith("<TICKER>")
    except Exception:
        return False


# --------------------------------------------------------------------------
# 3) raw parse → validity + metric2 stats
# --------------------------------------------------------------------------
def parse_raw(text):
    """Mirror _parse_tsetmc_csv's column mapping but keep RAW (unwidened) values."""
    lines = text.splitlines()
    hdr = {}
    if lines and lines[0].strip().startswith("<"):
        hdr = {nm.strip().upper(): i for i, nm in enumerate(lines[0].split(","))}

    def col(p, name, default):
        i = hdr.get(name, default)
        try:
            v = p[i].strip()
            return float(v) if v else None
        except (IndexError, ValueError):
            return None

    out = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        p = [x.strip() for x in ln.split(",")]
        if len(p) < 11:
            continue
        d = p[1]
        if len(d) != 8 or not d.isdigit():
            continue
        try:
            first = float(p[2] or 0)
            hi = float(p[3])
            lo = float(p[4])
            cl = float(p[5])
        except ValueError:
            continue
        vol = col(p, "VOL", 7) or 0.0
        base = col(p, "OPEN", 10) or 0.0
        last = col(p, "LAST", 11)
        out.append({"date": f"{d[:4]}-{d[4:6]}-{d[6:]}", "first": first,
                    "high": hi, "low": lo, "close": cl, "vol": vol,
                    "base": base, "last": last})
    out.sort(key=lambda x: x["date"])
    return out


def candle_a_valid(row):
    return row["high"] > 0 and row["close"] > 0 and row["low"] > 0 and \
        (row["first"] > 0 or row["base"] > 0)


def build_ab(raw):
    """(candlesA, candlesB, validity, gap_hist) — B mirrors A's geometry rules,
    only close changes; shadows widened around LAST exactly as production
    widens them around CLOSE (chart.py:85)."""
    validity = {"days": 0, "last_zero_or_missing": 0,
                "last_below_low": 0, "last_above_high": 0,
                "last_outside_widened": 0, "no_trade_day": 0,
                "examples_out_of_range": [], "examples_zero": []}
    gaps = []          # |LAST/CLOSE - 1| in % over days where both > 0
    cA, cB = [], []
    for r in raw:
        if not (r["high"] > 0 and r["low"] > 0 and r["low"] <= r["high"]):
            continue
        o = r["first"] if r["first"] > 0 else \
            (min(max(r["base"], r["low"]), r["high"]) if r["base"] > 0 else r["close"])
        if o <= 0:
            continue
        hi_a = max(r["high"], r["low"], o, r["close"])
        lo_a = min(r["high"], r["low"], o, r["close"])
        # ---- validity of raw LAST vs raw [LOW, HIGH] (only on days that are candles)
        validity["days"] += 1
        last = r["last"]
        if r["vol"] <= 0:
            validity["no_trade_day"] += 1
        if last is None or last <= 0:
            validity["last_zero_or_missing"] += 1
            if len(validity["examples_zero"]) < 3:
                validity["examples_zero"].append(
                    {"date": r["date"], "last": last, "low": r["low"],
                     "high": r["high"], "close": r["close"], "vol": r["vol"]})
            last_eff = r["close"]
        else:
            if last < r["low"]:
                validity["last_below_low"] += 1
                validity["examples_out_of_range"].append(
                    {"date": r["date"], "last": last, "low": r["low"],
                     "high": r["high"], "close": r["close"], "vol": r["vol"],
                     "side": "below_low",
                     "dist_pct": round((r["low"] - last) / r["low"] * 100, 4)})
            elif last > r["high"]:
                validity["last_above_high"] += 1
                validity["examples_out_of_range"].append(
                    {"date": r["date"], "last": last, "low": r["low"],
                     "high": r["high"], "close": r["close"], "vol": r["vol"],
                     "side": "above_high",
                     "dist_pct": round((last - r["high"]) / r["high"] * 100, 4)})
            if last < lo_a or last > hi_a:
                validity["last_outside_widened"] += 1
            if r["close"] > 0:
                gaps.append(abs(last / r["close"] - 1.0) * 100.0)
            last_eff = last
        cA.append({"time": r["date"], "open": o, "high": hi_a, "low": lo_a,
                   "close": r["close"], "volume": r["vol"]})
        cB.append({"time": r["date"], "open": o,
                   "high": max(hi_a, last_eff), "low": min(lo_a, last_eff),
                   "close": last_eff, "volume": r["vol"]})
        # volumes kept on A's shadows only in cB when LAST widens them
    validity["examples_out_of_range"] = sorted(
        validity["examples_out_of_range"], key=lambda e: -e["dist_pct"])[:3]
    return cA, cB, validity, gaps


def hist_stats(gaps):
    """count >1%, mean/median of abs gap % — from per-symbol lists."""
    if not gaps:
        return {"n": 0, "gt1pct": 0, "mean": None, "median": None}
    return {"n": len(gaps), "gt1pct": sum(1 for g in gaps if g > 1.0),
            "mean": round(statistics.fmean(gaps), 3),
            "median": round(statistics.median(gaps), 3)}


# --------------------------------------------------------------------------
# 4) adjustment factors per close-definition, then the REAL engine
# --------------------------------------------------------------------------
def adjusted_series(candles, rows, volumes_src):
    """rows = all_rows-shaped [{'time','base','close'}] for THIS close def."""
    events, anchored = ch._adjust_events_from_rows(rows)
    ev_dates = [e["date"] for e in events]
    ev_ratios = [e["ratio"] for e in events]
    factors = [None] * len(candles)
    order = sorted(range(len(candles)), key=lambda i: candles[i]["time"])
    f = 1.0
    j = len(ev_dates) - 1
    for i in reversed(order):
        t = candles[i]["time"]
        while j >= 0 and ev_dates[j] > t:
            f *= ev_ratios[j]
            j -= 1
        factors[i] = {"time": t, "factor": round(f, 10)}
    vols = [{"time": c["time"], "value": c["volume"]} for c in candles]
    scaled = ch._fts_scaled(candles, factors, vols)
    return scaled, events, anchored, factors


def compare_engines(ftsA, ftsB):
    """Return dict of bool flips + before/after snapshot for the fields the
    owner asked about. Engine output shape: api/chart.py _fts_analyze_candles."""
    d = {}
    snap = {}
    tA, tB = ftsA.get("trend", {}), ftsB.get("trend", {})

    def tf(tr):
        return (tr or {}).get("trend")

    for k in ("D", "W", "M"):
        a, b = tf(tA.get(k)), tf(tB.get(k))
        d[f"trend_{k}"] = a != b
        snap[f"trend_{k}"] = [a, b]
    mA, mB = tA.get("matrix") or {}, tB.get("matrix") or {}
    d["matrix_decision"] = mA.get("decision") != mB.get("decision")
    d["into_REJECT"] = (mA.get("decision") != "REJECT" and mB.get("decision") == "REJECT")
    d["out_of_REJECT"] = (mA.get("decision") == "REJECT" and mB.get("decision") != "REJECT")
    d["matrix_setup"] = mA.get("setup") != mB.get("setup")
    snap["matrix"] = [f"{mA.get('decision')}/{mA.get('setup')}",
                      f"{mB.get('decision')}/{mB.get('setup')}"]
    jA, jB = ftsA.get("jet") or {}, ftsB.get("jet") or {}
    d["jet_active"] = bool(jA.get("active")) != bool(jB.get("active"))
    snap["jet"] = [jA.get("active"), jB.get("active")]

    eA, eB = ftsA.get("exit_engine") or {}, ftsB.get("exit_engine") or {}
    d["exit_verdict"] = eA.get("verdict") != eB.get("verdict")
    snap["exit_verdict"] = [eA.get("verdict"), eB.get("verdict")]
    d["exit_signals"] = sorted(eA.get("signals") or []) != sorted(eB.get("signals") or [])
    l1A, l1B = eA.get("l1") or {}, eB.get("l1") or {}
    d["hard_stop"] = (l1A.get("hard_stop") or 0) != (l1B.get("hard_stop") or 0)
    d["ma14"] = (l1A.get("ma14") or 0) != (l1B.get("ma14") or 0)
    d["stop_hit"] = bool(l1A.get("stop_hit")) != bool(l1B.get("stop_hit"))
    d["ma14_exit"] = bool(l1A.get("ma14_exit")) != bool(l1B.get("ma14_exit"))
    snap["hard_stop"] = [l1A.get("hard_stop"), l1B.get("hard_stop")]
    snap["ma14"] = [l1A.get("ma14"), l1B.get("ma14")]
    l2A, l2B = eA.get("l2") or {}, eB.get("l2") or {}
    d["l2_choch_break"] = bool(l2A.get("choch_break")) != bool(l2B.get("choch_break"))
    d["l2_channel_break"] = bool(l2A.get("channel_break")) != bool(l2B.get("channel_break"))
    l3A, l3B = eA.get("l3") or {}, eB.get("l3") or {}
    d["l3_third_peak"] = bool(l3A.get("third_peak")) != bool(l3B.get("third_peak"))
    d["l3_double_top"] = bool(l3A.get("double_top")) != bool(l3B.get("double_top"))
    d["l3_hs_break"] = bool(l3A.get("hs_break")) != bool(l3B.get("hs_break"))
    l4A, l4B = eA.get("l4") or {}, eB.get("l4") or {}
    d["l4_rsi_div"] = bool(l4A.get("rsi_divergence")) != bool(l4B.get("rsi_divergence"))
    d["l4_rsi_roll"] = bool(l4A.get("rsi_rollover")) != bool(l4B.get("rsi_rollover"))

    hA, hB = ftsA.get("hourglass") or {}, ftsB.get("hourglass") or {}
    d["hourglass_active"] = bool(hA.get("active")) != bool(hB.get("active"))
    d["ma52"] = (hA.get("ma52") or 0) != (hB.get("ma52") or 0)
    snap["ma52"] = [hA.get("ma52"), hB.get("ma52")]
    snap["hourglass"] = [hA.get("active"), hB.get("active")]

    fA, fB = ftsA.get("fib"), ftsB.get("fib")

    def fib_flat(f):
        if not f:
            return {}
        return {"hi33": (f.get("zone_33_40") or {}).get("hi"),
                "lo33": (f.get("zone_33_40") or {}).get("lo"),
                "in33": (f.get("zone_33_40") or {}).get("in_zone"),
                "hi618": (f.get("zone_618_70") or {}).get("hi"),
                "lo618": (f.get("zone_618_70") or {}).get("lo"),
                "in618": (f.get("zone_618_70") or {}).get("in_zone"),
                "leg": (f.get("leg") or {}).get("direction"),
                "legH": (f.get("leg") or {}).get("high"),
                "legL": (f.get("leg") or {}).get("low"),
                "levels": [x.get("price") for x in (f.get("levels") or [])]}
    a, b = fib_flat(fA), fib_flat(fB)
    d["fib_belt33_bounds"] = (a.get("hi33"), a.get("lo33")) != (b.get("hi33"), b.get("lo33"))
    d["fib_belt618_bounds"] = (a.get("hi618"), a.get("lo618")) != (b.get("hi618"), b.get("lo618"))
    d["fib_in33"] = a.get("in33") != b.get("in33")
    d["fib_in618"] = a.get("in618") != b.get("in618")
    d["fib_leg"] = (a.get("leg"), a.get("legH"), a.get("legL")) != \
                   (b.get("leg"), b.get("legH"), b.get("legL"))
    d["fib_levels"] = a.get("levels") != b.get("levels")
    snap["fib_belt618"] = [[a.get("lo618"), a.get("hi618")],
                           [b.get("lo618"), b.get("hi618")]]
    snap["fib_in618"] = [a.get("in618"), b.get("in618")]

    cA, cB = ftsA.get("choch") or {}, ftsB.get("choch") or {}
    d["choch_bearish"] = bool(cA.get("bearish")) != bool(cB.get("bearish"))
    d["choch_bullish"] = bool(cA.get("bullish")) != bool(cB.get("bullish"))
    snap["choch"] = [cA.get("label"), cB.get("label")]

    bA, bB = ftsA.get("double_bottom") or {}, ftsB.get("double_bottom") or {}
    d["double_bottom"] = bool(bA.get("active")) != bool(bB.get("active"))
    snap["double_bottom"] = [bA.get("active"), bB.get("active")]
    rA, rB = ftsA.get("range_box") or {}, ftsB.get("range_box") or {}
    d["range_box"] = bool(rA.get("active")) != bool(rB.get("active"))
    pA, pB = ftsA.get("point_hunt") or {}, ftsB.get("point_hunt") or {}
    d["point_hunt_active"] = bool(pA.get("active")) != bool(pB.get("active"))
    d["point_hunt_touches"] = pA.get("touches") != pB.get("touches")
    snap["point_hunt"] = [[pA.get("touches"), pA.get("active")],
                          [pB.get("touches"), pB.get("active")]]

    sA = [(e.get("date"), e.get("kind")) for e in (ftsA.get("setups") or [])]
    sB = [(e.get("date"), e.get("kind")) for e in (ftsB.get("setups") or [])]
    d["setups_history"] = sA != sB
    return d, snap


FLIP_KEYS = ["trend_D", "trend_W", "trend_M", "matrix_decision", "matrix_setup",
             "jet_active", "exit_verdict", "exit_signals", "hard_stop", "ma14",
             "stop_hit", "ma14_exit", "l2_choch_break", "l2_channel_break",
             "l3_third_peak", "l3_double_top", "l3_hs_break", "l4_rsi_div",
             "l4_rsi_roll", "hourglass_active", "ma52", "fib_belt33_bounds",
             "fib_belt618_bounds", "fib_in33", "fib_in618", "fib_leg",
             "fib_levels", "choch_bearish", "choch_bullish", "double_bottom",
             "range_box", "point_hunt_active", "point_hunt_touches",
             "setups_history"]
# categorical verdicts the owner cares most about
VERDICT_KEYS = ["trend_D", "trend_W", "trend_M", "matrix_decision", "matrix_setup",
                "jet_active", "exit_verdict", "stop_hit", "ma14_exit",
                "l2_choch_break", "l2_channel_break", "l3_double_top", "l3_hs_break",
                "hourglass_active", "fib_in33", "fib_in618", "choch_bearish",
                "choch_bullish", "double_bottom", "range_box", "point_hunt_active"]


# --------------------------------------------------------------------------
# 5) per-symbol pipeline
# --------------------------------------------------------------------------
def process_symbol(sym, ins):
    p = csv_path(ins)
    if not _valid_cache(p):
        return {"error": f"no csv for {sym}"}
    with open(p, encoding="utf-8") as f:
        text = f.read()
    raw = parse_raw(text)
    cA, cB, validity, gaps = build_ab(raw)

    # adjustment for EACH close-definition, from its own «قیمت پایه» continuity.
    # NOTE (fidelity): production _parse_tsetmc_csv feeds _adjust_events_from_rows
    # ALL days with base>0 and CLOSE>0 — including no-trade days (H=L=0) that
    # never become candles. rowsA/rowsB mirror that; B's close is LAST (fallback
    # to CLOSE when LAST is zero/missing, same fallback as the parser).
    rowsA = [{"time": r["date"], "base": r["base"], "close": r["close"]}
             for r in raw if r["base"] > 0 and r["close"] > 0]
    rowsB = [{"time": r["date"], "base": r["base"],
              "close": (r["last"] if (r["last"] and r["last"] > 0) else r["close"])}
             for r in raw if r["base"] > 0 and r["close"] > 0]
    adjA, evA, anchA, facA = adjusted_series(cA, rowsA, None)
    adjB1, evB1, anchB1, facB1 = adjusted_series(cB, rowsB, None)
    # B2 = the decision implemented WITHOUT touching the adjustment machinery:
    # candle close = LAST, but adjust events/factors still detected from the
    # CLOSE-based «قیمت پایه» chain (A's factors), as production computes them today.
    volsB = [{"time": c["time"], "value": c["volume"]} for c in cB]
    adjB2 = ch._fts_scaled(cB, facA, volsB)

    # adjustment drift (naive swap): days where factor differs >0.05%
    fa = {x["time"]: x["factor"] for x in facA}
    fb = {x["time"]: x["factor"] for x in facB1}
    fac_drift = sum(1 for t in fa if t in fb and abs(fa[t] / fb[t] - 1) > 0.0005)
    prodA = fa[min(fa)] if fa else 1.0
    prodB = fb[min(fb)] if fb else 1.0

    rec = {"symbol": sym, "ins_code": ins, "bars": len(adjA),
           "validity": validity, "gap_hist": hist_stats(gaps),
           "adj": {"events_A": len(evA), "events_B_naive": len(evB1),
                   "anchored_A": anchA, "anchored_B_naive": anchB1,
                   "factor_drift_days": fac_drift,
                   "oldest_factor_A": prodA, "oldest_factor_B_naive": prodB,
                   "events_dates_A": [e["date"] for e in evA][:80],
                   "events_dates_B_naive": [e["date"] for e in evB1][:80]}}
    if len(adjA) < 2:
        rec["error"] = "insufficient series"
        return rec
    t0 = time.time()
    ftsA = ch._fts_analyze_candles(sym, adjA, entry_hint=None)
    ftsB1 = ch._fts_analyze_candles(sym, adjB1, entry_hint=None)
    ftsB2 = ch._fts_analyze_candles(sym, adjB2, entry_hint=None)
    flips1, snap1 = compare_engines(ftsA, ftsB1)
    flips2, snap2 = compare_engines(ftsA, ftsB2)
    rec["flips"] = flips2            # PRIMARY = B2 (clean implementation)
    rec["snap"] = snap2
    rec["flips_naive"] = flips1      # B1 = naive full swap (adjust machinery follows)
    rec["snap_naive"] = snap1
    rec["verdict_score"] = sum(1 for k in VERDICT_KEYS if flips2.get(k))
    rec["total_score"] = sum(1 for k in FLIP_KEYS if flips2.get(k))
    rec["verdict_score_naive"] = sum(1 for k in VERDICT_KEYS if flips1.get(k))
    rec["last_close_A"] = adjA[-1]["close"]
    rec["last_close_B"] = adjB2[-1]["close"]
    rec["engine_ms"] = round((time.time() - t0) * 1000, 1)
    return rec


# --------------------------------------------------------------------------
# 6) main
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=800)
    ap.add_argument("--progress", type=int, default=50)
    ap.add_argument("--refetch", action="store_true")
    args = ap.parse_args()
    os.makedirs(CSV_DIR, exist_ok=True)

    meta = build_sample(args.limit)
    samples = meta["symbols"][:args.limit]
    print(f"sample: {len(samples)} symbols "
          f"(db total {meta['total_symbols_in_db']}, no-ins skipped "
          f"{len(meta['skipped_no_ins_code'])})")

    fs = fetch_all(samples, force=args.refetch)
    print(f"fetch: {fs['fetched']} new, {fs['from_cache']} cached, "
          f"{fs['bytes'] / 1e6:.1f} MB, {fs['wall_s']}s, failed={len(fs['failed'])}")

    done = {}
    if os.path.exists(PARTIAL_PATH):
        with open(PARTIAL_PATH, encoding="utf-8") as f:
            for ln in f:
                try:
                    r = json.loads(ln)
                    done[r["symbol"]] = r
                except Exception:
                    pass
    out = open(PARTIAL_PATH, "a", encoding="utf-8")
    t0 = time.time()
    todo = [s for s in samples if s["symbol"] not in done]
    for i, s in enumerate(todo, 1):
        try:
            rec = process_symbol(s["symbol"], s["ins_code"])
        except Exception as e:
            rec = {"symbol": s["symbol"], "error": f"{type(e).__name__}: {e}"}
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()
        done[s["symbol"]] = rec
        if i % args.progress == 0 or i == len(todo):
            print(f"  [engine] {i}/{len(todo)} remaining "
                  f"({time.time() - t0:.0f}s)")
    out.close()
    aggregate(samples, done, meta, fs)


def aggregate(samples, done, meta, fs):
    n = len(samples)
    ok = [r for r in (done.get(s["symbol"]) for s in samples)
          if r and "flips" in r]
    errors = [(s["symbol"], r.get("error")) for s in samples
              for r in [done.get(s["symbol"])]
              if r is None or "flips" not in (r or {})]
    tot = {"symbols_total": n, "symbols_measured": len(ok),
           "symbols_failed": len(errors),
           "failed_list": errors[:40]}

    # 1) validity
    v = {"days": 0, "last_zero_or_missing": 0, "last_below_low": 0,
         "last_above_high": 0, "last_outside_widened": 0, "no_trade_day": 0}
    oor_ex, zero_ex = [], []
    for r in ok:
        for k in v:
            v[k] += r["validity"][k]
        oor_ex += r["validity"]["examples_out_of_range"]
        zero_ex += r["validity"]["examples_zero"]
    v["pct_last_zero_or_missing"] = round(
        v["last_zero_or_missing"] / max(1, v["days"]) * 100, 3)
    v["pct_last_outside_range"] = round(
        (v["last_below_low"] + v["last_above_high"]) / max(1, v["days"]) * 100, 4)
    v["top_examples_out_of_range"] = sorted(
        oor_ex, key=lambda e: -e["dist_pct"])[:3]
    v["examples_zero"] = zero_ex[:3]

    # 2) gap A vs B
    n_days = sum(r["gap_hist"]["n"] for r in ok)
    gt1 = sum(r["gap_hist"]["gt1pct"] for r in ok)
    means = [r["gap_hist"]["mean"] for r in ok if r["gap_hist"]["mean"] is not None]
    gsum = sum((r["gap_hist"]["mean"] or 0) * r["gap_hist"]["n"] for r in ok)
    gap = {"symbol_days_compared": n_days,
           "pct_gt_1": round(gt1 / max(1, n_days) * 100, 2),
           "mean_all": round(gsum / max(1, n_days), 3),
           "mean_of_symbol_means": round(statistics.fmean(means), 3) if means else None,
           "median_of_symbol_medians": round(
               statistics.median([r["gap_hist"]["median"] for r in ok
                                  if r["gap_hist"]["median"] is not None]), 3)}

    # 3) flips — primary = B2 (clean), plus B1 naive
    flips = {}
    flips_naive = {}
    for k in FLIP_KEYS:
        c = sum(1 for r in ok if r["flips"].get(k))
        flips[k] = {"symbols": c, "pct": round(c / max(1, len(ok)) * 100, 1)}
        cn = sum(1 for r in ok if r["flips_naive"].get(k))
        flips_naive[k] = {"symbols": cn, "pct": round(cn / max(1, len(ok)) * 100, 1)}
    into = sum(1 for r in ok if r["flips"].get("into_REJECT"))
    out_ = sum(1 for r in ok if r["flips"].get("out_of_REJECT"))
    rejA = sum(1 for r in ok if r["snap"]["matrix"][0].startswith("REJECT"))
    rejB = sum(1 for r in ok if r["snap"]["matrix"][1].startswith("REJECT"))
    flips["matrix_decision"] = {**flips["matrix_decision"],
                                "into_REJECT": into, "out_of_REJECT": out_,
                                "reject_A": rejA, "reject_B": rejB}
    into_n = sum(1 for r in ok if r["flips_naive"].get("into_REJECT"))
    out_n = sum(1 for r in ok if r["flips_naive"].get("out_of_REJECT"))
    rejB_n = sum(1 for r in ok if r["snap_naive"]["matrix"][1].startswith("REJECT"))
    flips_naive["matrix_decision"] = {**flips_naive["matrix_decision"],
                                      "into_REJECT": into_n, "out_of_REJECT": out_n,
                                      "reject_A": rejA, "reject_B": rejB_n}

    # 4) adjustment drift (naive swap re-derives factors from LAST-chain)
    adj = {"symbols_with_events": sum(1 for r in ok if r["adj"]["events_A"] or
                                      r["adj"]["events_B_naive"]),
           "symbols_events_count_differ_naive": sum(1 for r in ok
                                                    if r["adj"]["events_A"] != r["adj"]["events_B_naive"]),
           "symbols_anchor_differ_naive": sum(1 for r in ok
                                              if r["adj"]["anchored_A"] != r["adj"]["anchored_B_naive"]),
           "symbols_anchor_lost_naive": sum(1 for r in ok
                                            if r["adj"]["anchored_A"] and not r["adj"]["anchored_B_naive"]),
           "symbols_any_factor_drift_naive": sum(1 for r in ok
                                                 if r["adj"]["factor_drift_days"] > 0),
           "total_factor_drift_days_naive": sum(r["adj"]["factor_drift_days"] for r in ok),
           "median_drift_days_per_symbol_naive": statistics.median(
               [r["adj"]["factor_drift_days"] for r in ok]) if ok else 0,
           "max_oldest_factor_shift_naive": max(
               (max(r["adj"]["oldest_factor_B_naive"], r["adj"]["oldest_factor_A"])
                / max(min(r["adj"]["oldest_factor_B_naive"], r["adj"]["oldest_factor_A"]), 1e-9))
               for r in ok) if ok else None}

    # top-5 by verdict flips (B2 primary)
    top5 = sorted(ok, key=lambda r: (-r.get("verdict_score", 0),
                                     -r.get("total_score", 0), r["symbol"]))[:5]
    top = []
    for r in top5:
        top.append({"symbol": r["symbol"], "bars": r["bars"],
                    "verdict_flips": r["verdict_score"],
                    "total_flips": r["total_score"],
                    "before_after": {k: r["snap"].get(k) for k in
                                     ["trend_D", "trend_W", "matrix", "jet",
                                      "exit_verdict", "hard_stop", "ma14", "ma52",
                                      "fib_belt618", "choch", "double_bottom"]}})
    top5n = sorted(ok, key=lambda r: (-r.get("verdict_score_naive", 0),
                                      r["symbol"]))[:5]
    top_naive = [{"symbol": r["symbol"], "verdict_flips_naive": r["verdict_score_naive"]}
                 for r in top5n]

    # 5) cost
    bars = sum(r["bars"] for r in ok)
    eng_ms = sum(r.get("engine_ms", 0) for r in ok)
    cost = {"csv_fetches_new": fs["fetched"], "csv_from_cache": fs["from_cache"],
            "csv_bytes": fs["bytes"], "fetch_wall_s": fs["wall_s"],
            "symbol_days": bars, "engine_wall_ms": round(eng_ms)}

    # sample-bias note data
    ph = sorted((s["ph_rows"] for s in samples))
    bias = {"min_rows": ph[0], "median_rows": statistics.median(ph),
            "max_rows": ph[-1],
            "db_total_symbols": meta["total_symbols_in_db"],
            "cutoff": "price_history rows desc (≈2y window) — sample = most-active listings"}

    rep = {"generated": datetime.datetime.now().isoformat(timespec="seconds"),
           "basis": ("ADJUSTED CDN series via _fts_scaled + _fts_analyze_candles "
                     "(entry_hint=None). PRIMARY B2 = close=LAST with adjustment "
                     "detection left CLOSE-based; B1_naive = full swap where "
                     "adjust chain also uses LAST"),
           "totals": tot, "1_candle_validity_B": v, "2_gap_A_vs_B": gap,
           "3_engine_flips_B2_primary": flips,
           "3b_engine_flips_B1_naive": flips_naive,
           "4_adjustment_drift_naive": adj,
           "top5_flip_symbols": top, "top5_naive": top_naive,
           "5_cost": cost, "sample_bias": bias,
           "errors": errors[:40]}
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    print(json.dumps(rep["totals"], ensure_ascii=False))
    print(f"report → {REPORT_PATH}")


if __name__ == "__main__":
    main()
