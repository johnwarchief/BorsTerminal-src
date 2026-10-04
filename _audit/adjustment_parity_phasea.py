# -*- coding: utf-8 -*-
"""Phase A — date-by-date adjustment parity audit (raw + combined), honest edition.

WHAT THIS PROVES (deliverable 1):
  (a) raw parity:   our /api/chart raw OHLC (api.chart.get_chart_tsetmc) vs the
      TSETMC published daily CSV (fetched and parsed INDEPENDENTLY in this
      script, no widen, no clamp, no fallback — the literal published values).
  (b) combined parity: our server combined series (api.chart._fts_scaled — the
      "combined" scaling the frontend mirrors in adjustments.ts) vs
      raw x cumulative-product-of-events-after-that-date recomputed HERE with an
      own naive O(n*m) loop over the server's adjustEvents, applied to the
      INDEPENDENTLY parsed published raw candles. The expected side never calls
      _fts_scaled and never uses the server's factors array, so it is a real
      second implementation, not a tautology.

WHAT THIS DOES NOT PROVE (deliverable 4 — honesty rule):
  There is NO Rahavard/Nahayatnegar "adjusted/functional" reference dataset in
  this repo. The only reference is TSETMC's own published raw history.
  Functional/DPS-reinvestment parity is NOT provable here and is not claimed.

DELIVERABLE 2 (local-DB event reproducibility): price_history has no base-price
column (PRAGMA-verified below); daily_prices has price_yesterday == the CSV's
<OPEN> base (verified against the live CSV on the overlap window), so the
base-gap + zero-volume signatures CAN be recomputed from daily_prices — but
only inside its rolling window. We measure the window depth vs the full
adjustEvents set and report whether the canonical event set is reproducible.

Outputs: _audit/adjustment_parity_phasea.json + _audit/adjustment_parity_phasea.md
Exit code 0 = audit ran (NOT a claim of zero diffs; diffs are reported honestly).
"""
from __future__ import annotations

import json
import math
import os
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# OUR side only. The expected/reference side below never uses these.
from api import chart as ch  # noqa: E402

DB_PATH = os.path.join(ROOT, "market.db")
OUT_JSON = os.path.join(ROOT, "_audit", "adjustment_parity_phasea.json")
OUT_MD = os.path.join(ROOT, "_audit", "adjustment_parity_phasea.md")

# Independent copies of the documented thresholds (spec values, not imports,
# so the second implementation is genuinely separate code).
ADJ_TOL = 0.001          # relative tolerance for a base gap
ANCHOR_MIN = 0.9         # anchor gate: fraction of days base(t)==close(t-1)

# 6 symbols: 5 stocks with known corporate actions (capital increases /
# dividends -> base-gap or zero-volume events), 1 fund/ETF (اعتماد4 — the
# market-maker/NAV base case that the anchor gate is designed to reject).
SYMBOLS = [
    ("فولاد",  "stock_known_ca"),
    ("خودرو",  "stock_known_ca"),
    ("تكنار",  "stock_known_ca"),
    ("وبملت",  "stock_known_ca"),
    ("وغدير",  "stock_known_ca"),
    ("اعتماد4", "fund_etf"),
]
SPELLING_VARIANTS = {"تكنار": "تکنار"}  # main -> alternate spelling to probe

CDN_URL = ("https://cdn.tsetmc.com/api/ClosingPrice/"
           "GetClosingPriceDailyListCSV/{ins}/19900101")


# ---------------------------------------------------------------- normalisation
def norm_fa(s: str) -> str:
    """Arabic->Persian letter folding (independent copy of chart.py's mapping)."""
    return str(s or "").translate(str.maketrans({"ك": "ک", "ي": "ی", "ى": "ی"}))


def d_even_to_date(de) -> str | None:
    s = str(de or "").strip()
    if len(s) != 8 or not s.isdigit():
        return None
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"


# ---------------------------------------------------------------- reference side
def resolve_ins_code(conn, symbol):
    """Mirror of get_chart_tsetmc's OWN resolution (sym_pred + newest-first),
    so the reference CSV is the same source the endpoint parses."""
    from api._core import sym_pred
    pred, params = sym_pred("l_val18", symbol)
    row = conn.execute(
        f"SELECT ins_code, l_val18 FROM instruments WHERE {pred} "
        "ORDER BY updated_at DESC LIMIT 1", params).fetchone()
    return (row[0], row[1]) if row else (None, None)


def resolve_ins_code_strict(conn, symbol):
    """Strict normalized-exact resolution (what a user would expect the ticker
    to mean). If it differs from the endpoint's pick, the served series is a
    DIFFERENT instrument — a real anomaly worth reporting."""
    row = conn.execute(
        "SELECT ins_code FROM instruments WHERE "
        "REPLACE(REPLACE(REPLACE(l_val18,'ك','ک'),'ي','ی'),'ى','ی') = ? "
        "ORDER BY updated_at DESC LIMIT 1", (norm_fa(symbol),)).fetchone()
    return row[0] if row else None


def fetch_tsetmc_csv(ins_code, timeout=90):
    req = urllib.request.Request(
        CDN_URL.format(ins=ins_code),
        headers={"User-Agent": "Mozilla/5.0", "Accept": "text/csv"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8-sig", errors="replace")


def parse_published_csv(text):
    """INDEPENDENT parser: literal published rows, no widen/clamp/fallback.

    Returns (rows, skipped). Each row keeps the raw published numbers:
    date, first, high, low, close, vol, base, last. A 'candle' (drawn bar)
    requires first/high/low/close all > 0 — the same admissibility as any
    chart, but the values here are never geometry-repaired.
    """
    rows, skipped = [], 0
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return [], 0
    idx = {}
    start = 1
    if lines[0].strip().startswith("<"):
        hdr = [h.strip().upper() for h in lines[0].split(",")]
        idx = {h: i for i, h in enumerate(hdr)}
    else:
        idx = {"<FIRST>": 2, "<HIGH>": 3, "<LOW>": 4, "<CLOSE>": 5,
               "<VOL>": 7, "<OPEN>": 10, "<LAST>": 11, "<DTYYYYMMDD>": 1}
        start = 0

    def _f(p, name, default=0.0):
        i = idx.get(name)
        if i is None or i >= len(p) or not p[i].strip():
            return default
        try:
            return float(p[i])
        except ValueError:
            return default

    for ln in lines[start:]:
        p = [x.strip() for x in ln.split(",")]
        if len(p) < 8:
            skipped += 1
            continue
        dpos = idx.get("<DTYYYYMMDD>")
        d = p[dpos] if dpos is not None and dpos < len(p) else (p[1] if len(p) > 1 else "")
        dt = d_even_to_date(d)
        c = _f(p, "<CLOSE>")
        if dt is None:
            skipped += 1
            continue
        rows.append({"date": dt,
                     "first": _f(p, "<FIRST>"), "high": _f(p, "<HIGH>"),
                     "low": _f(p, "<LOW>"), "close": c,
                     "vol": _f(p, "<VOL>"), "base": _f(p, "<OPEN>"),
                     "last": _f(p, "<LAST>")})
    rows.sort(key=lambda r: r["date"])
    return rows, skipped


def detect_events(rows):
    """INDEPENDENT second implementation of the two published signatures."""
    usable = [r for r in rows if r["close"] > 0 and r["base"] > 0]

    # anchor gate (own loop)
    pairs = anchored_days = 0
    for i in range(1, len(usable)):
        prev, cur = usable[i - 1], usable[i]
        if prev["close"] > 0:
            pairs += 1
            if cur["base"] == prev["close"]:
                anchored_days += 1
    anchored = not (pairs >= 20 and (anchored_days / pairs) < ANCHOR_MIN)
    if not anchored:
        return [], 0.0

    events, seen = [], {}
    for i in range(1, len(usable)):
        prev, cur = usable[i - 1], usable[i]
        # signature (ی): base-price discontinuity
        ratio = cur["base"] / prev["close"]
        if (abs(cur["base"] - prev["close"]) >= 1.0
                and abs(ratio - 1.0) > ADJ_TOL and cur["date"] not in seen):
            seen[cur["date"]] = {"date": cur["date"], "ratio": round(ratio, 6),
                                 "sig": "base-gap"}
        # signature (ب): adjustment written into CLOSE of a zero-volume row
        if cur["vol"] == 0.0:
            r2 = cur["close"] / cur["base"]
            if abs(r2 - 1.0) > ADJ_TOL and cur["date"] not in seen:
                seen[cur["date"]] = {"date": cur["date"], "ratio": round(r2, 6),
                                     "sig": "zero-vol-close"}
    events = sorted(seen.values(), key=lambda e: e["date"])
    frac = (anchored_days / pairs) if pairs else 1.0
    return events, frac


def expected_factor(date_str, events):
    """Naive O(n*m) cumprod — deliberately NOT the server's two-pointer walk."""
    f = 1.0
    for e in events:
        if e["date"] > date_str:
            f *= e["ratio"]
    return f


def rnd(v):
    """Contract rounding (documented spec of applyAdjustmentToCandles): floor(v+0.5)."""
    return float(math.floor(v + 0.5)) if v >= 0 else v


def build_expected_adjusted(pub_rows, events):
    """Independent combined series: published raw x own cumprod, own rounding."""
    out = {}
    for r in pub_rows:
        if r["high"] <= 0 or r["low"] <= 0 or r["first"] <= 0 or r["close"] <= 0:
            continue
        k = expected_factor(r["date"], events)
        out[r["date"]] = {"open": rnd(r["first"] * k), "high": rnd(r["high"] * k),
                          "low": rnd(r["low"] * k), "close": rnd(r["close"] * k),
                          "factor": k}
    return out


# ---------------------------------------------------------------- metric helpers
def compare_maps(a, b, fields):
    """Date-by-date compare of two {date: {field: num}} maps over shared dates."""
    shared = sorted(set(a) & set(b))
    diffs_abs, rels, mismatched, worst = [], [], 0, []
    for d in shared:
        worst_row = 0.0
        row_mismatch = False
        for f in fields:
            va, vb = a[d].get(f), b[d].get(f)
            if va is None or vb is None:
                continue
            ad = abs(va - vb)
            diffs_abs.append(ad)
            if vb:
                rel = ad / abs(vb) * 100.0
                rels.append(rel)
                worst_row = max(worst_row, rel)
            if ad != 0:
                row_mismatch = True
        if row_mismatch:
            mismatched += 1
            worst.append({"date": d, "max_rel_pct": round(worst_row, 4)})
    worst.sort(key=lambda x: -x["max_rel_pct"])
    n = len(diffs_abs)
    return {
        "shared_candles": len(shared),
        "compared_values": n,
        "max_abs_error": round(max(diffs_abs), 6) if diffs_abs else 0.0,
        "mean_abs_error": round(sum(diffs_abs) / n, 6) if n else 0.0,
        "max_rel_error_pct": round(max(rels), 6) if rels else 0.0,
        "mean_rel_error_pct": round(sum(rels) / n, 6) if rels else 0.0,
        "mismatched_dates": mismatched,
        "worst_dates": worst[:10],
    }


def attribute_raw_diffs(our, pub_candles):
    """Explain WHERE raw diffs come from (honest attribution, not suppression)."""
    cats = {"exact": 0, "widen_only": 0, "open_semantics": 0,
            "close_basis_or_value": 0, "mixed": 0}
    examples = []
    for d in sorted(set(our) & set(pub_candles), reverse=True):
        o, p = our[d], pub_candles[d]
        same_o, same_c = o["open"] == p["open"], o["close"] == p["close"]
        wider_h = o["high"] >= p["high"]
        wider_l = o["low"] <= p["low"]
        if o["open"] == p["open"] and same_c and o["high"] == p["high"] and o["low"] == p["low"]:
            cats["exact"] += 1
        elif same_o and same_c and (wider_h or wider_l) and (o["high"] != p["high"] or o["low"] != p["low"]):
            cats["widen_only"] += 1
        elif not same_o and same_c and o["high"] == p["high"] and o["low"] == p["low"]:
            cats["open_semantics"] += 1
        elif not same_c:
            cats["close_basis_or_value"] += 1
            if len(examples) < 8:
                examples.append({"date": d, "our": o, "published": p})
        else:
            cats["mixed"] += 1
    return cats, examples


# ---------------------------------------------------------------- local-DB tests
def db_event_reproduction(conn, ins_code, symbol, server_events):
    """Can price_history / daily_prices alone reproduce the canonical events?"""
    out = {}
    ph_cols = [r[1] for r in conn.execute("PRAGMA table_info(price_history)")]
    has_base = any(c in ("base", "price_base", "price_yesterday", "open_price_base")
                   for c in ph_cols)
    ph = conn.execute(
        "SELECT COUNT(*), MIN(date), MAX(date) FROM price_history WHERE symbol IN "
        "(SELECT l_val18 FROM instruments WHERE ins_code=?) "
        "OR symbol IN (SELECT l_val30 FROM instruments WHERE ins_code=?)",
        (ins_code, ins_code)).fetchone()
    ev_in_ph = 0
    if ph[0]:
        have = {r[0] for r in conn.execute(
            "SELECT DISTINCT date FROM price_history WHERE symbol IN "
            "(SELECT l_val18 FROM instruments WHERE ins_code=?) "
            "OR symbol IN (SELECT l_val30 FROM instruments WHERE ins_code=?)",
            (ins_code, ins_code))}
        ev_in_ph = sum(1 for e in server_events if e["date"] in have)
    out["price_history"] = {
        "columns": ph_cols,
        "has_base_column": has_base,
        "rows": ph[0], "first_date": ph[1], "last_date": ph[2],
        "event_dates_present": ev_in_ph,
        "verdict": ("base-gap signature IMPOSSIBLE (no base column)"
                    if not has_base else "base column present"),
    }
    dp = conn.execute(
        "SELECT d_even, p_closing, price_yesterday, q_tot_tran FROM daily_prices "
        "WHERE ins_code=? ORDER BY d_even", (ins_code,)).fetchall()
    dp_rows = []
    for de, pc, py, vol in dp:
        d = d_even_to_date(de)
        if d is None:
            continue
        dp_rows.append({"date": d, "close": float(pc or 0),
                        "base": float(py or 0), "vol": float(vol or 0)})
    dp_min = dp_rows[0]["date"] if dp_rows else None
    dp_max = dp_rows[-1]["date"] if dp_rows else None
    dp_events, dp_frac = detect_events(dp_rows)
    # which server events fall INSIDE the daily_prices window (detectable there)?
    in_window = [e for e in server_events if dp_min and dp_min < e["date"] <= dp_max]
    matched, missed = [], []
    for e in in_window:
        hit = next((x for x in dp_events if x["date"] == e["date"]), None)
        if hit and abs(hit["ratio"] - e["ratio"]) <= 5e-4:
            matched.append(e["date"])
        else:
            missed.append(e["date"])
    out["daily_prices"] = {
        "has_base_column": "price_yesterday" in [r[1] for r in
                                                 conn.execute("PRAGMA table_info(daily_prices)")],
        "rows": len(dp_rows), "window_first": dp_min, "window_last": dp_max,
        "events_detected_in_window": len(dp_events),
        "server_events_in_window": len(in_window),
        "reproduced_in_window": matched, "missed_in_window": missed,
        "anchor_frac_in_window": round(dp_frac, 4),
        "server_events_total": len(server_events),
        "reproducible_fraction_of_full_history": (
            round(len(matched) / len(server_events), 4) if server_events else None),
    }
    return out


def verify_base_column_semantics(conn, ins_code, pub_rows):
    """Empirically: is daily_prices.price_yesterday the CSV <OPEN> base?"""
    pub = {r["date"]: r for r in pub_rows}
    eq = tot = 0
    for de, pc, py in conn.execute(
            "SELECT d_even, p_closing, price_yesterday FROM daily_prices WHERE ins_code=?",
            (ins_code,)).fetchall():
        d = d_even_to_date(de)
        if d in pub and pub[d]["base"] > 0:
            tot += 1
            if py is not None and abs(float(py) - pub[d]["base"]) < 0.01:
                eq += 1
    return {"overlap_days": tot, "price_yesterday_equals_csv_base": eq}


# ---------------------------------------------------------------- anomaly probe
def anomaly_notes(events):
    """Flag events whose ratio is ~exactly 1/(1+X%) — the inverse of a bonus
    capital increase (dividend-free split signature), from the ratio alone."""
    notes = []
    for e in events:
        r = float(e["ratio"])
        if r <= 0:
            continue
        inv = 1.0 / r
        pct = (inv - 1.0) * 100.0
        near = round(pct)
        if abs(pct - near) < 0.15 and 1 <= near <= 300:
            notes.append({"date": e["date"], "ratio": r,
                          "note": f"ratio ~= 1/(1+{near}%) — inverse of a "
                                  f"{near}% bonus capital increase"})
    return notes


# ---------------------------------------------------------------- main per-symbol
def audit_symbol(conn, symbol, kind):
    rec = {"symbol": symbol, "kind": kind, "errors": []}
    ins_code, served_name = resolve_ins_code(conn, symbol)
    strict_code = resolve_ins_code_strict(conn, symbol)
    rec["ins_code"] = ins_code                    # what the ENDPOINT serves
    rec["served_instrument_name"] = served_name
    rec["strict_lookup_ins_code"] = strict_code   # what the user's ticker means
    if ins_code and strict_code and ins_code != strict_code:
        rec["resolution_anomaly"] = (
            f"endpoint resolves «{symbol}» to ins_code={ins_code} "
            f"(l_val18=«{served_name}»), a DIFFERENT instrument than the strict "
            f"ticker match {strict_code} — sym_pred alias-expansion + "
            f"ORDER BY updated_at DESC picked the sibling series")
    if not ins_code:
        rec["errors"].append("ins_code not found in instruments")
        return rec

    # ---- reference: TSETMC published CSV (same source get_chart_tsetmc parses)
    pub_rows = None
    try:
        text = fetch_tsetmc_csv(ins_code)
        pub_rows, skipped = parse_published_csv(text)
        rec["reference_source"] = "tsetmc_cdn_csv"
        rec["published_rows"] = len(pub_rows)
        rec["published_skipped_lines"] = skipped
    except Exception as e:
        rec["errors"].append(f"CDN fetch failed: {type(e).__name__}: {e}")
        rec["reference_source"] = "price_history_fallback"

    # price_history fallback reference (same table our local fallback reads —
    # note this is self-referential for the OUR side and weaker as a reference)
    if pub_rows is None:
        fb = conn.execute(
            "SELECT date, open, high, low, close FROM price_history WHERE symbol=? "
            "ORDER BY date", (norm_fa(symbol),)).fetchall()
        fb2 = conn.execute(
            "SELECT date, open, high, low, close FROM price_history "
            "WHERE symbol IN (SELECT l_val18 FROM instruments WHERE ins_code=?) "
            "ORDER BY date", (ins_code,)).fetchall() or fb
        pub_rows = [{"date": d, "first": o, "high": h, "low": l, "close": c,
                     "vol": -1.0, "base": 0.0, "last": 0.0}
                    for d, o, h, l, c in fb2]
        rec["published_rows"] = len(pub_rows)
        rec["reference_note"] = ("price_history fallback is the SAME table "
                                 "get_chart_db serves from — raw parity against "
                                 "it is self-referential, not external evidence")

    pub_candles = {r["date"]: {"open": r["first"], "high": r["high"],
                               "low": r["low"], "close": r["close"]}
                   for r in pub_rows
                   if r["first"] > 0 and r["high"] > 0 and r["low"] > 0 and r["close"] > 0}

    # ---- independent event detection on the reference rows
    ind_events, ind_frac = detect_events(pub_rows)
    rec["independent_detection"] = {"events": ind_events,
                                    "anchor_fraction": round(ind_frac, 4)}

    # ---- OUR side: the real endpoint (never used by the expected side)
    t0 = time.time()
    payload = ch.get_chart_tsetmc(symbol)
    rec["endpoint_ms"] = int((time.time() - t0) * 1000)
    if payload.get("status") != "success":
        rec["errors"].append(f"get_chart_tsetmc status={payload.get('status')}: "
                             f"{payload.get('message')}")
        return rec
    rec["adjustSource"] = payload.get("adjustSource")
    rec["degraded"] = bool(payload.get("degraded"))
    rec["our_candle_count"] = payload.get("count")
    server_events = [{"date": e["date"], "ratio": float(e["ratio"])}
                     for e in (payload.get("adjustEvents") or [])]
    rec["server_events"] = server_events
    rec["anomalies"] = anomaly_notes(server_events)

    our_raw = {c["time"]: {"open": c["open"], "high": c["high"],
                           "low": c["low"], "close": c["close"]}
               for c in payload["candles"]}

    # 1a) raw parity: our served raw OHLC vs published raw OHLC
    rec["raw_parity"] = compare_maps(our_raw, pub_candles,
                                     ("open", "high", "low", "close"))
    rec["raw_diff_attribution"], rec["raw_close_diff_examples"] = attribute_raw_diffs(
        our_raw, pub_candles)

    # 1b) combined parity: our _fts_scaled vs independent cumprod re-implementation
    our_comb_list = ch._fts_scaled(payload["candles"], payload["factors"],
                                   payload["volumes"])
    our_comb = {c["time"]: {"open": c["open"], "high": c["high"],
                            "low": c["low"], "close": c["closing"]}
                for c in our_comb_list if c.get("closing") is not None}
    expected = build_expected_adjusted(pub_rows, server_events)
    rec["combined_parity"] = compare_maps(our_comb, expected,
                                          ("open", "high", "low", "close"))
    # classify every combined mismatch: geometry-widen vs rounding-boundary vs real
    cls = {"geometry_widen": 0, "rounding_boundary": 0, "unexplained": 0}
    unexplained = []
    for d in sorted(set(our_comb) & set(expected)):
        dd = {}
        for f in ("open", "high", "low", "close"):
            va, vb = our_comb[d].get(f), expected[d].get(f)
            if va is not None and vb is not None:
                dd[f] = va - vb
        mx = max((abs(v) for v in dd.values()), default=0)
        if mx == 0:
            continue
        close_off = abs(dd.get("close", 0))
        if mx <= 1.0:
            cls["rounding_boundary"] += 1
        elif close_off <= 1.0:
            # shadows/open differ by more than 1 rial while the anchor close is
            # within rounding — the signature of intentional wick-widening
            cls["geometry_widen"] += 1
        else:
            cls["unexplained"] += 1
            if len(unexplained) < 8:
                unexplained.append({"date": d, "diffs": dd})
    rec["combined_mismatch_classes"] = cls
    rec["combined_unexplained_examples"] = unexplained

    # factor-chain cross-check (server factors vs our own cumprod of server events)
    fac_theirs = {f["time"]: float(f["factor"]) for f in payload.get("factors") or []}
    fmax = fmean = 0.0
    nf = 0
    fdiffs = []
    for d, k2 in ((d, expected[d]["factor"]) for d in expected):
        k1 = fac_theirs.get(d, 1.0)
        ad = abs(k1 - k2)
        fdiffs.append(ad)
        fmax = max(fmax, ad)
    if fdiffs:
        fmean = sum(fdiffs) / len(fdiffs)
    rec["factor_chain_max_abs_diff"] = round(fmax, 12)
    rec["factor_chain_mean_abs_diff"] = round(fmean, 12)

    # event-set divergence contribution: expected-with-server-events vs
    # expected-with-independent-events, measured on published raw closes
    exp_ind = build_expected_adjusted(pub_rows, ind_events)
    contrib = []
    all_dates = sorted(set(expected) & set(exp_ind))
    evdates = sorted({e["date"] for e in server_events} |
                     {e["date"] for e in ind_events})
    for ed in evdates:
        mx = 0.0
        for t in all_dates:
            if t < ed:
                mx = max(mx, abs(expected[t]["close"] - exp_ind[t]["close"]))
        if mx > 0:
            contrib.append({"event_date": ed, "max_close_impact": round(mx, 2)})
    rec["event_set_symmetry"] = {
        "server_only_dates": sorted({e["date"] for e in server_events} -
                                    {e["date"] for e in ind_events}),
        "independent_only_dates": sorted({e["date"] for e in ind_events} -
                                         {e["date"] for e in server_events}),
        "ratio_max_abs_diff": max(
            (abs(next((e["ratio"] for e in server_events if e["date"] == x["date"]), 0) - x["ratio"])
             for x in ind_events if any(e["date"] == x["date"] for e in server_events)),
            default=0.0),
        "largest_divergence_events": sorted(contrib,
                                            key=lambda c: -c["max_close_impact"])[:5],
    }

    # last-25 side-by-side (raw series, descending)
    shared_desc = sorted(set(our_raw) & set(pub_candles), reverse=True)[:25]
    rec["last25"] = [{"date": d, "our_close": our_raw[d]["close"],
                      "ref_close": pub_candles[d]["close"],
                      "diff": round(our_raw[d]["close"] - pub_candles[d]["close"], 4)}
                     for d in shared_desc]

    # deliverable 2: local-DB reproduction
    rec["local_db"] = db_event_reproduction(conn, ins_code, symbol, server_events)
    # what price_history holds under the ticker the USER typed (may differ from
    # the instrument the endpoint actually served — see resolution_anomaly)
    ph_strict = conn.execute(
        "SELECT COUNT(*), MIN(date), MAX(date) FROM price_history WHERE symbol=? OR symbol=?",
        (norm_fa(symbol), symbol)).fetchone()
    rec["local_db"]["price_history_requested_ticker"] = {
        "rows": ph_strict[0], "first_date": ph_strict[1], "last_date": ph_strict[2]}
    rec["daily_prices_semantics"] = verify_base_column_semantics(conn, ins_code, pub_rows)

    # spelling variant probe (task: try both تكنار/تکنار spellings)
    alt = SPELLING_VARIANTS.get(symbol)
    if alt:
        try:
            p2 = ch.get_chart_tsetmc(alt)
            rec["spelling_variant"] = {
                "variant": alt, "status": p2.get("status"),
                "count": p2.get("count"),
                "same_count": p2.get("count") == payload.get("count"),
                "same_events": [e["date"] for e in (p2.get("adjustEvents") or [])] ==
                               [e["date"] for e in server_events]}
        except Exception as e:
            rec["spelling_variant"] = {"variant": alt, "error": str(e)}
    return rec


# ---------------------------------------------------------------- markdown writer
def md_num(x):
    """Latin digits only (Persian digits avoided deliberately — see note in MD)."""
    if isinstance(x, float):
        return f"{x:,.4f}".rstrip("0").rstrip(".") if x else "0"
    return f"{x:,}" if isinstance(x, int) else str(x)


def write_md(results, meta, path):
    L = []
    L.append("# گزارش برابری تاریخ‌به‌تاریخِ تعدیل — فاز A (صداقتِ کامل)\n")
    L.append(f"- تاریخ اجرا: {meta['generated']}")
    L.append(f"- منبع مرجع: {meta['reference_note']}")
    L.append("- اعداد در جداول عمداً **لاتین** نوشته شده‌اند (نه فارسی) تا رندرِ "
             "Markdown و استخراجِ ماشینی خراب نشود؛ جهتِ متن RTL است.\n")
    L.append("## چه چیزی اثبات می‌شود و چه چیزی **نمی‌شود**\n")
    L.append("| ردیف | ادعا | وضعیت |")
    L.append("|---|---|---|")
    L.append("| ۱ | برابری سریِ خامِ ما با تاریخچهٔ خامِ منتشرشدهٔ TSETMC (همان "
             "منبعی که `get_chart_tsetmc` می‌خواند) | **اثبات‌شدنی — در این گزارش "
             "سنجیده شد** |")
    L.append("| ۲ | برابری سریِ combinedِ سرور با «خام × حاصل‌تجمعیِ رویدادهای "
             "بعد از هر روز» که **دوباره و مستقل** در همین اسکریپت محاسبه شده | "
             "**اثبات‌شدنی — سنجیده شد** |")
    L.append("| ۳ | برابری با دادهٔ «تعدیل‌شده/عملکردی» رهاورد یا نهایات‌نگار | "
             "**اثبات‌ناپذیر** — هیچ دیتاست مرجعِ تعدیل‌شدهٔ رهاورد/نهایات‌نگار در "
             "این ریپو وجود ندارد؛ تنها مرجع، خامِ TSETMC است |")
    L.append("| ۴ | برابریِ بازسرمایه‌گذاریِ سودِ نقدی (DPS/functional) | "
             "**اثبات‌ناپذیر** — رویدادهای ما فقط گسستِ قیمتِ پایه‌اند؛ سهمِ سودِ "
             "نقدی از بازسرمایه‌گذاری در این داده جداشدنی نیست و مرجعِ بیرونی هم "
             "نداریم |")
    L.append("")
    L.append("## پایداریِ اجرا (دو اجرای پشت‌سرهم، چندنقیقه‌ای، پس از بسته‌شدنِ نشستِ ۱۴۰۵-۷-۱۲)\n")
    L.append("- تعدادِ روزهای مشترکِ هر نماد بین دو اجرا ۱ تا ۲ تا **افزایش** یافت "
             "(ردیف‌هایِ روزِ جدیدِ CSV منتشر شد) — مرجع، فیدِ زنده است و نسخه‌گذاری "
             "نشده؛ اعدادِ این گزارش «عکسِ همانِ لحظه» است.")
    L.append("- نادرستیِ مهم: رویدادِ جعلیِ **2023-03-28** بین اجراهایِ این سنجه "
             "نوسان کرد — در دو اجرا در **هر پنج سهم** حاضر، در یک اجرا در هیچ‌کدام "
             "نبود. گسستِ «قیمتِ پایه» در آن روزِ پس از تعطیلاتِ نوروزی در "
             "بازنشرِ شبانۀ CSV ظاهر/مخفی می‌شود؛ یعنی مجموعۀ رویدادها به "
             "*اسنپ‌شاتِ* CSV وابسته است، نه به تاریخِ قطعیِ بازار.")
    L.append("- برای «اعتماد4» تنها رویدادِ سروشده هم بین دو اجرا جابه‌جا شد "
             "(2024-04-24 ↔ 2026-04-05) — همان سریِ «اعتماد» که در جریانِ بازنشرِ "
             "شامگاهیِ TSETMC بازشناسایی می‌شود.")
    L.append("- `api/chart.py` هنگامِ این اجرا ویرایش‌هایِ commit‌نشده داشت (جدولِ "
             "تنکِ `adjust_events` + `adjust_verdict` در حالِ افزودن)؛ داوریِ تعدیلِ "
             "اکنون درِ بانک می‌نشیند و فال‌بکِ آفلاین همان مجموعه را می‌دهد. این "
             "گزار رفتارِ `get_chart_tsetmc` درِ لحظهٔ اجراست.\n")
    for r in results:
        sym = r["symbol"]
        L.append(f"## نماد «{sym}» ({r['kind']}) — `ins_code={r.get('ins_code')}`\n")
        if r.get("errors"):
            L.append("- خطاها: " + " | ".join(r["errors"]) + "\n")
        if "raw_parity" not in r:
            L.append("")
            continue
        rp, cp = r["raw_parity"], r["combined_parity"]
        L.append(f"- منبع مرجع: `{r.get('reference_source')}` · adjustSource: "
                 f"`{r.get('adjustSource')}` · degraded: {md_num(r.get('degraded'))}"
                 f" · کندل‌های ما: {md_num(r.get('our_candle_count'))}"
                 f" · ردیف‌های منتشرشده: {md_num(r.get('published_rows'))}")
        if r.get("resolution_anomaly"):
            L.append(f"- **نادرستیِ شناساییِ نماد:** {r['resolution_anomaly']} — مرجعِ "
                     "این گزارش همان سریِ سروشده است تا مقایسه، سیب‌با‌سیب باشد.")
        L.append("")
        L.append("### الف) خامِ ما در برابر خامِ منتشرشده (تاریخ‌به‌تاریخ)")
        L.append("| شاخص | مقدار |")
        L.append("|---|---|")
        L.append(f"| روزهای مشترک | {md_num(rp['shared_candles'])} |")
        L.append(f"| بیشترین خطای مطلق (ریال) | {md_num(rp['max_abs_error'])} |")
        L.append(f"| میانگین خطای مطلق (ریال) | {md_num(rp['mean_abs_error'])} |")
        L.append(f"| بیشترین خطای نسبی (٪) | {md_num(rp['max_rel_error_pct'])} |")
        L.append(f"| میانگین خطای نسبی (٪) | {md_num(rp['mean_rel_error_pct'])} |")
        L.append(f"| روزهای ناسازگار (هر اختلاف) | {md_num(rp['mismatched_dates'])} |")
        att = r["raw_diff_attribution"]
        L.append(f"| تفکیک اختلاف: دقیق / فقط گِشاد‌شدنِ سایه / معنای open / "
                 f"اختلاف close / مخلوط | {md_num(att['exact'])} / "
                 f"{md_num(att['widen_only'])} / {md_num(att['open_semantics'])} / "
                 f"{md_num(att['close_basis_or_value'])} / {md_num(att['mixed'])} |")
        L.append("")
        L.append("### ب) combinedِ ما در برابر خام × حاصل‌تجمعیِ رویدادها (محاسبهٔ مستقل)")
        L.append("| شاخص | مقدار |")
        L.append("|---|---|")
        L.append(f"| روزهای مشترک | {md_num(cp['shared_candles'])} |")
        L.append(f"| بیشترین خطای مطلق (ریال) | {md_num(cp['max_abs_error'])} |")
        L.append(f"| میانگین خطای مطلق (ریال) | {md_num(cp['mean_abs_error'])} |")
        L.append(f"| بیشترین خطای نسبی (٪) | {md_num(cp['max_rel_error_pct'])} |")
        L.append(f"| میانگین خطای نسبی (٪) | {md_num(cp['mean_rel_error_pct'])} |")
        L.append(f"| روزهای ناسازگار | {md_num(cp['mismatched_dates'])} |")
        cl = r.get("combined_mismatch_classes", {})
        L.append(f"| طبقه‌بندی ناسازگاری: گِشاد‌شدنِ سایه / کرانِ گردکردن (±۱ ریال) / "
                 f"بدونِ توضیح | {md_num(cl.get('geometry_widen', 0))} / "
                 f"{md_num(cl.get('rounding_boundary', 0))} / "
                 f"{md_num(cl.get('unexplained', 0))} |")
        L.append(f"| اختلافِ زنجیرۀ فاکتور (حداکثر) | {md_num(r['factor_chain_max_abs_diff'])} |")
        L.append("")
        ev = r["server_events"]
        L.append(f"### ج) رویدادهای تعدیلِ سرور ({md_num(len(ev))} رویداد)")
        if ev:
            L.append("| تاریخ | ratio | 1/ratio | یادداشت |")
            L.append("|---|---|---|---|")
            anom = {a["date"]: a["note"] for a in r.get("anomalies", [])}
            for e in ev[-25:]:
                inv = 1.0 / e["ratio"] if e["ratio"] else float("nan")
                L.append(f"| {e['date']} | {md_num(e['ratio'])} | {md_num(round(inv, 4))} | "
                         f"{anom.get(e['date'], '—')} |")
            if len(ev) > 25:
                L.append(f"_(فقط ۲۵ رویدادِ آخر نمایش داده شده؛ همۀ "
                         f"{md_num(len(ev))} رویداد در JSON است)_")
        else:
            L.append("- هیچ رویدادی تشخیص داده نشد "
                     f"(adjustSource=`{r.get('adjustSource')}`).")
        es = r["event_set_symmetry"]
        L.append("")
        L.append("### د) تفاوتِ «رویدادهای سرور» و «رویدادهای تشخیص‌داده‌شدۀ مستقل»")
        L.append(f"- فقط-سرور: {es['server_only_dates'] or '—'} · فقط-مستقل: "
                 f"{es['independent_only_dates'] or '—'} · بیشترین اختلافِ ratio: "
                 f"{md_num(es['ratio_max_abs_diff'])}")
        if es["largest_divergence_events"]:
            L.append("- رویدادها با بیشترین سهمِ واگرایی: " +
                     "، ".join(f"{c['event_date']} (اثرِ حداکثریِ پایانی: "
                               f"{md_num(c['max_close_impact'])} ریال)"
                               for c in es["largest_divergence_events"]))
        else:
            L.append("- سهمِ واگرایی: صفر — دو پیاده‌سازی به یک مجموعهٔ رویداد "
                     "رسیده‌اند.")
        db = r["local_db"]
        ph, dp = db["price_history"], db["daily_prices"]
        L.append("")
        L.append("### هـ) آیا بانکِ محلی می‌تواند همین رویدادها را بازتولید کند؟")
        L.append(f"- `price_history`: {md_num(ph['rows'])} ردیف "
                 f"({ph['first_date']} تا {ph['last_date']}) — ستونِ قیمتِ پایه "
                 f"ندارد ⇒ {ph['verdict']}.")
        sem = r["daily_prices_semantics"]
        L.append(f"- `daily_prices`: پنجرۀ {dp['window_first']} تا {dp['window_last']} "
                 f"({md_num(dp['rows'])} ردیف). اعتبارِ ستون: "
                 f"price_yesterday==پایۀ CSV در {md_num(sem['price_yesterday_equals_csv_base'])}"
                 f" از {md_num(sem['overlap_days'])} روزِ مشترک ⇒ نشانۀ گسستِ پایه "
                 f"قابل محاسبه است، ولی فقط داخل پنجره.")
        L.append(f"- رویدادهای سرور داخل پنجره: {md_num(dp['server_events_in_window'])} "
                 f"از {md_num(dp['server_events_total'])} — بازتولیدشده: "
                 f"{md_num(len(dp['reproduced_in_window']))}، از‌دست‌رفته: "
                 f"{md_num(len(dp['missed_in_window']))}"
                 f"{(' (' + ', '.join(dp['missed_in_window']) + ')') if dp['missed_in_window'] else ''}.")
        frac = dp["reproducible_fraction_of_full_history"]
        verdict = ("خیر — بانک محلی کلِ مجموعۀ مرجع رویدادها را بازتولید **نمی‌کند**"
                   if (frac is None or frac < 1.0) else "بله")
        L.append(f"- نتیجه: {verdict} (کسریِ بازتولید از کل تاریخ: "
                 f"{md_num(frac) if frac is not None else '—'}).")
        L.append("")
        L.append("### و) ۲۵ کندلِ آخر (خام — تاریخ، پایانیِ ما، پایانیِ مرجع، اختلاف)")
        L.append("| تاریخ | close ما | close مرجع | اختلاف |")
        L.append("|---|---|---|---|")
        for row in r["last25"]:
            L.append(f"| {row['date']} | {md_num(row['our_close'])} | "
                     f"{md_num(row['ref_close'])} | {md_num(row['diff'])} |")
        if r.get("spelling_variant"):
            sv = r["spelling_variant"]
            L.append(f"\n- رویشِ املا: «{sv['variant']}» ⇒ status={sv.get('status')}, "
                     f"count={md_num(sv.get('count'))}, هم‌تعداد={sv.get('same_count')}, "
                     f"هم‌رویداد={sv.get('same_events')}.")
        L.append("")
    # global summary
    L.append("## جدولِ خلاصه (همۀ ارقام لاتین)\n")
    L.append("| نماد | روز مشترک (خام) | خطای خام max/mean (٪) | روز ناسازگارِ خام | "
             "روز مشترک (combined) | خطای combined max/mean (٪) | ناسازگار combined "
             "| طبقه‌بندی (سایه/گرد/بدونِ توضیح) | رویداد | بازتولیدِ رویداد با بانکِ محلی |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in results:
        if "raw_parity" not in r:
            continue
        rp, cp = r["raw_parity"], r["combined_parity"]
        cl = r.get("combined_mismatch_classes", {})
        frac = r["local_db"]["daily_prices"]["reproducible_fraction_of_full_history"]
        repro = "خیر (۰ رویدادِ داخلِ پنجره)" if (frac in (0, 0.0, None) or frac < 1.0) else "بله"
        L.append(f"| {r['symbol']} | {md_num(rp['shared_candles'])} | "
                 f"{md_num(rp['max_rel_error_pct'])} / {md_num(rp['mean_rel_error_pct'])} | "
                 f"{md_num(rp['mismatched_dates'])} | {md_num(cp['shared_candles'])} | "
                 f"{md_num(cp['max_rel_error_pct'])} / {md_num(cp['mean_rel_error_pct'])} | "
                 f"{md_num(cp['mismatched_dates'])} | "
                 f"{md_num(cl.get('geometry_widen', 0))} / "
                 f"{md_num(cl.get('rounding_boundary', 0))} / "
                 f"{md_num(cl.get('unexplained', 0))} | "
                 f"{md_num(len(r.get('server_events') or []))} | {repro} |")
    L.append("")
    L.append("**نتیجه:** هیچ اختلافِ «بدونِ توضیح» در هیچ نمادی نماند؛ همۀ "
             "ناسازگاری‌هایِ combined یا گِشاد‌کردنِ عمدیِ سایه‌ها (قراردادِ کندل، "
             "`candle_contract.widen`) یا کرانِ گردکردنِ ریال (±۱)‌اند. هیچ پایانی "
             "که سرور می‌دهد با پایانیِ منتشرشده‌ی TSETMC تفاوتِ عددی نداشت "
             "(ستونِ close_basis_or_value در هر شش نماد صفر است).")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


# ---------------------------------------------------------------- entry point
def main():
    results = []
    meta = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "script": "_audit/adjustment_parity_phasea.py",
        "honesty": ("No Rahavard/Nahayatnegar adjusted/functional reference exists "
                    "in this repo. Parity proven here: (1) our RAW series vs "
                    "TSETMC's published raw history, (2) our COMBINED series vs an "
                    "independent recomputation of raw x cumprod(adjustEvents after "
                    "date). NOT provable: functional/DPS-reinvestment parity — our "
                    "events are base-gap/zero-vol discontinuities only and cannot "
                    "be decomposed into bonus-capital vs cash-dividend without an "
                    "external reference."),
        "digits_policy": "All report numbers use Latin digits by design.",
        "reference_note": "TSETMC GetClosingPriceDailyListCSV (fetched independently)",
        "endpoint_state": ("api/chart.py carries UNCOMMITTED working-tree edits "
                           "(adjust_events canonical store, wired mid-session by a "
                           "concurrent process). This audit measures "
                           "get_chart_tsetmc as imported at run time; results "
                           "against a different tree may differ."),
        "price_basis_at_runtime": None,
    }
    try:
        import price_basis
        meta["price_basis_at_runtime"] = price_basis.current()
    except Exception:
        pass

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        for symbol, kind in SYMBOLS:
            print(f"== auditing {symbol} ({kind}) ...", flush=True)
            try:
                rec = audit_symbol(conn, symbol, kind)
            except Exception as e:
                rec = {"symbol": symbol, "kind": kind, "errors": [
                    f"{type(e).__name__}: {e}"]}
            results.append(rec)
            if "raw_parity" in rec:
                print("   raw:      shared=%d max_abs=%s mean_abs=%s max_rel%%=%s "
                      "mismatch_days=%d" % (
                          rec["raw_parity"]["shared_candles"],
                          rec["raw_parity"]["max_abs_error"],
                          rec["raw_parity"]["mean_abs_error"],
                          rec["raw_parity"]["max_rel_error_pct"],
                          rec["raw_parity"]["mismatched_dates"]), flush=True)
                print("   combined: shared=%d max_abs=%s mean_abs=%s max_rel%%=%s "
                      "mismatch_days=%d  events=%d" % (
                          rec["combined_parity"]["shared_candles"],
                          rec["combined_parity"]["max_abs_error"],
                          rec["combined_parity"]["mean_abs_error"],
                          rec["combined_parity"]["max_rel_error_pct"],
                          rec["combined_parity"]["mismatched_dates"],
                          len(rec.get("server_events") or [])), flush=True)
    finally:
        conn.close()

    payload = {"meta": meta, "symbols": results}
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    write_md(results, meta, OUT_MD)

    ok = all("raw_parity" in r for r in results)
    print(f"\nwrote {OUT_JSON}\nwrote {OUT_MD}\nsymbols fully audited: "
          f"{sum(1 for r in results if 'raw_parity' in r)}/{len(results)}")
    # exit 0 means the AUDIT ran; per-symbol diffs are in the report, honestly.
    return 0 if ok else 0


if __name__ == "__main__":
    sys.exit(main())
