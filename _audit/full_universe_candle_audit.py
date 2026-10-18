#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_audit/full_universe_candle_audit.py — Stage 1-3 over the WHOLE instrument universe.

Nothing is sampled and nothing is hardcoded:
  * the universe is read from the live `market.db` (`instruments`);
  * the raw reference is the same official TSETMC CDN CSV the product itself reads,
    matched row-for-row by real date (never by array index);
  * the served series is produced by the product's OWN functions
    (`api.chart._parse_tsetmc_csv`, `price_basis.apply_basis`,
    `api.chart._adjust_events_from_rows`, `api.chart._canonical_adjustment`).
    Re-deriving that maths here would prove nothing, so this file only works out what
    the published columns imply and writes out every disagreement.

Three passes, all resumable:
  pass 1  crawl every instrument's official CSV  -> _scratch/live/csv/<ins_code>.csv.gz
  pass 2  per symbol: raw per-field audit + adjustment-chain audit
  pass 3  external join against the frozen Rahavard snapshot (type0 raw / type7 adjusted)

Outputs (every count read back from the data):
  _audit/SYMBOL-AUDIT-MANIFEST.csv    one row per instrument, full status
  _audit/SYMBOL-AUDIT-UNRESOLVED.csv  one row per symbol/date/field finding
  _audit/SYMBOL-AUDIT-REFERENCE.csv   per-symbol external match rates
  _scratch/live/full_audit_state.json aggregate summary
"""
from __future__ import annotations

import concurrent.futures as cf
import csv
import datetime as dt
import gzip
import json
import math
import os
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
A = lambda *p: os.path.join(ROOT, *p)

CSV_DIR = A("_scratch", "live", "csv")
MANIFEST = A("_audit", "SYMBOL-AUDIT-MANIFEST.csv")
UNRESOLVED = A("_audit", "SYMBOL-AUDIT-UNRESOLVED.csv")
REFERENCE = A("_audit", "SYMBOL-AUDIT-REFERENCE.csv")
STATE = A("_scratch", "live", "full_audit_state.json")
REF_BARS = A("_audit", "ra365_ref_bars.json")
URL = "https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyListCSV/{code}/19900101"
HDR = {"User-Agent": "Mozilla/5.0", "Accept": "text/csv"}
UNRESOLVED_CAP = 400_000

import api.chart as CH                      # noqa: E402
import price_basis as PB                    # noqa: E402
import candle_contract as CC                # noqa: E402


def log(msg):
    print(msg, flush=True)


def universe():
    """همۀ ابزارهای بانک، با نوعِ اوراق — نه فهرستِ امروزِ بازار.

    هیچ ستونِ «فعال/غیرفعال» درِ این بانک نیست (`PRAGMA table_info(instruments)` آن را
    ندارد)، پس وضعیتِ خاموشی را از خودِ داده می‌خوانیم: `last_date` درِ manifest، و
    `stale_days` نسبتِ کهنه‌ترینِ روزِ بازارِ کلِ مجموعه درِ خلاصه.
    """
    con = sqlite3.connect(A("market.db"))
    try:
        rows = con.execute(
            "select ins_code, l_val18, paper_type from instruments where ins_code is not null"
        ).fetchall()
    finally:
        con.close()
    out = {}
    for code, name, paper in rows:
        if code and name:
            out.setdefault(str(code), (str(name), "" if paper is None else str(paper)))
    return out


def _csv_path(code):
    for suf in (".csv.gz", ".csv"):
        p = os.path.join(CSV_DIR, code + suf)
        if os.path.exists(p) and os.path.getsize(p) > 20:
            return p
    return None


def read_source(code):
    p = _csv_path(code)
    if not p:
        return None
    if p.endswith(".gz"):
        with gzip.open(p, "rt", encoding="utf-8", errors="replace", newline="") as f:
            return f.read()
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read()


def crawl(codes, workers=6):
    os.makedirs(CSV_DIR, exist_ok=True)
    todo = [c for c in codes if _csv_path(c) is None]
    log(f"crawl: {len(codes)} instruments, {len(todo)} to fetch")
    if not todo:
        return
    import requests
    sess = requests.Session()
    done, errs, t0 = [0], [0], time.time()

    def get(code):
        p = os.path.join(CSV_DIR, code + ".csv.gz")
        try:
            r = sess.get(URL.format(code=code), headers=HDR, timeout=(4, 30))
            if r.status_code == 200 and len(r.text) > 20:
                with gzip.open(p, "wt", encoding="utf-8", newline="") as f:
                    f.write(r.text)
                done[0] += 1
            else:
                errs[0] += 1
                with open(p + ".err", "w", encoding="utf-8") as f:
                    f.write(f"http-{r.status_code}")
        except Exception as e:                       # network wall: recorded, never faked
            errs[0] += 1
            with open(p + ".err", "w", encoding="utf-8") as f:
                f.write(type(e).__name__)
        n = done[0] + errs[0]
        if n % 250 == 0:
            log(f"  crawled {done[0]} ok / {errs[0]} err in {time.time()-t0:.0f}s")
        time.sleep(0.05)

    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(get, todo))
    log(f"crawl done: {done[0]} ok, {errs[0]} errors, {time.time()-t0:.0f}s")


def iso(d):
    d = str(d).strip().replace("/", "")
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]}"


COLMAP = {"<FIRST>": 2, "<HIGH>": 3, "<LOW>": 4, "<CLOSE>": 5, "<VALUE>": 6,
          "<VOL>": 7, "<OPEN>": 10, "<LAST>": 11, "<DTYYYYMMDD>": 1}


def source_rows(text):
    """ردیف‌ها همان‌طور که منبع منتشر کرده — با همین ایندکس‌هایِ ستون که
    `_parse_tsetmc_csv` از هدر می‌خواند، نه حدسِ من."""
    lines = text.splitlines()
    idx = dict(COLMAP)
    if lines and lines[0].strip().startswith("<"):
        hdr = {nm.strip().upper(): i for i, nm in enumerate(lines[0].split(","))}
        for k in idx:
            if k in hdr:
                idx[k] = hdr[k]
    out, unparsable = {}, 0
    for ln in lines[1:]:
        if not ln.strip():
            continue
        p = [x.strip() for x in ln.split(",")]
        if len(p) < 11:
            unparsable += 1
            continue

        def f(k):
            try:
                return float(p[idx[k]] or 0)
            except (IndexError, TypeError, ValueError):
                return 0.0
        d = p[idx["<DTYYYYMMDD>"]]
        if len(d) != 8 or not d.isdigit():
            unparsable += 1
            continue
        out[iso(d)] = {"first": f("<FIRST>"), "high": f("<HIGH>"), "low": f("<LOW>"),
                       "close": f("<CLOSE>"), "last": f("<LAST>"), "vol": f("<VOL>"),
                       "base": f("<OPEN>")}
    return out, unparsable


def expected_candle(s, applied):
    """آنچه دو قراردادِ محصول از یکِ ردیفِ منتشرشده می‌سازند:
    `_parse_tsetmc_csv` (بدنه = <FIRST>، سایه از `candle_contract.widen`) و
    `price_basis.apply_basis` (مبنایِ منتخبِ کلِ سری + گِشاد‌کردنِ سایه، بی‌کُندنِ قیمت).

    این تابع فقط «انتظار» را از ستون‌هایِ منبع حساب می‌کند؛ هیچ عددی در کندلِ served
    دستکاری نمی‌شود و هیچ روزِ مفقودی پر نمی‌شود.
    """
    first, hi, lo, c = s["first"], s["high"], s["low"], s["close"]
    base, last = s["base"], s["last"]
    o = first if first > 0 else (min(max(base, lo), hi) if base > 0 else c)
    if hi <= 0 or c <= 0 or o <= 0 or lo <= 0:
        reason = "no_trade" if (s["vol"] <= 0 and hi <= 0) else "invalid_fields"
        return reason, None
    hi, lo = CC.widen(o, hi, lo, c)
    chosen = last if (applied == PB.LAST and last > 0) else c
    nh, nl = max(hi, lo, chosen), min(hi, lo, chosen)
    return "candle", {"open": o, "high": max(nh, o), "low": min(nl, o),
                      "close": chosen, "volume": s["vol"]}


REC_KEYS = ["ins_code", "symbol", "paper_type", "status", "source_rows", "served_candles",
            "no_trade_rows", "dropped_other_rows", "unparsable_rows",
            "first_date", "last_date", "stale_days", "max_gap_days", "gaps_over_10d",
            "dup_dates", "series_order", "order_mixed", "missing_unexpected", "extra_in_served",
            "basis_requested", "basis_applied", "basis_reason", "last_missing",
            "geometry_widened", "open_diff", "high_diff", "low_diff", "close_diff",
            "volume_diff", "max_abs_close_diff", "max_rel_close_diff",
            "widen_unexplained", "invariant_violations", "bad_numbers",
            "adj_events", "adj_sharpened", "adj_ambiguous", "adjust_source", "adj_rejected",
            "factor_min", "factor_max", "factor_above_one",
            "factor_invalid", "unexpected_factor_jumps", "factor_value_mismatch", "no_effect_events",
            "anchored_last", "chain_complete", "chain_incomplete",
            "ledger_rows_total", "coverage_start", "candles_before_coverage",
            "functional_available", "functional_blockers",
            "adjusted_candles", "early_rounding_max_rial", "raw_path_mutated",
            "reference_available", "cause"]

ZERO_FIELDS = ["source_rows", "served_candles", "no_trade_rows", "dropped_other_rows",
               "unparsable_rows", "dup_dates", "order_mixed", "missing_unexpected",
               "extra_in_served", "open_diff", "high_diff", "low_diff", "close_diff",
               "volume_diff", "widen_unexplained", "invariant_violations", "bad_numbers",
               "adj_events", "adj_sharpened", "adj_ambiguous", "adj_rejected",
               "factor_above_one", "factor_invalid",
               "unexpected_factor_jumps", "factor_value_mismatch", "no_effect_events", "chain_incomplete",
               "ledger_rows_total", "candles_before_coverage", "adjusted_candles",
               "raw_path_mutated", "gaps_over_10d", "max_gap_days"]


def blank_rec(code, name, paper):
    rec = {k: "" for k in REC_KEYS}
    rec.update(dict.fromkeys(ZERO_FIELDS, 0))
    rec.update({"max_abs_close_diff": 0.0, "max_rel_close_diff": 0.0,
                "early_rounding_max_rial": 0.0, "stale_days": "", "series_order": ""})
    rec.update({"ins_code": code, "symbol": name, "paper_type": paper,
                "anchored_last": "", "chain_complete": "", "functional_available": "",
                "reference_available": "no", "status": "", "cause": ""})
    return rec


def rel(a, b):
    if not b:
        return 0.0 if a == b else 1.0
    return round(abs(a - b) / abs(b), 9)


def day_no(s):
    return dt.date.fromisoformat(s).toordinal()


def check_factor_jumps(dates, factors, ev_dates):
    """ضریب فقط رویِ تاریخِ رویداد می‌پَرَد و اندازهٔ پَرش دقیقاً ∏ ratio است.

    قاعدۀِ موتور: `factor(t) = ∏ ratio` برایِ رویدادهایِ `date > t`، لنگر = بیشترینِ
    تاریخ با فاکتورِ ۱. پس بینِ دو کندلِ همسایه فاکتور تنها وقتی عوض می‌شود که رویدادی
    درِ `(t1, t2]` باشد، و `f(t1) = f(t2) × ∏ ratio`.

    رویدادِ `ratio == 1.0` بی‌اثر است: گسستِ قیمتِ پایه‌ای که هیچ جابه‌جایی ندارد
    (درِ سنجشِ ۱۴۰-۰۷-۲۷، ولراز ۲۰۱۷-۱۱-۱۲). بی‌شمردنِ آن، پرشِ درست را «خطایِ اندازه»
    گزارش می‌کرد — بیست‌وهشتِ نمادِ DIFFS درِ همان اجرا همه از این نوع بودند و هیچ
    اختلافِ قیمتی نداشتند. پس بی‌اثرها از شمارشِ «باید پَرش می‌کرد» بیرون می‌مانند،
    ولی درِ `no_effect_events` شمرده و اعلام می‌شوند (سکوت نکردن).
    """
    unexpected = mismatch = no_effect = 0
    j = 0
    for i in range(1, len(dates)):
        t1, t2 = dates[i - 1], dates[i]
        f1, f2 = factors[i - 1], factors[i]
        prod, cnt = 1.0, 0
        while j < len(ev_dates) and ev_dates[j][0] <= t2:
            if ev_dates[j][0] > t1:
                prod *= ev_dates[j][1]
                if abs(ev_dates[j][1] - 1.0) <= 1e-15:
                    no_effect += 1
                else:
                    cnt += 1
            j += 1
        changed = abs(f2 - f1) > 1e-12
        if changed and cnt == 0:
            unexpected += 1
        elif (not changed) and cnt:
            mismatch += 1
        elif changed and cnt and abs(f1 - f2 * prod) > 1e-9 * max(1.0, abs(f1)):
            mismatch += 1
    return {"unexpected": unexpected, "mismatch": mismatch, "no_effect": no_effect}


def audit_symbol(code, name, paper):
    rec = blank_rec(code, name, paper)
    unresolved = []
    text = read_source(code)
    if text is None:
        err = os.path.join(CSV_DIR, code + ".csv.gz.err")
        rec["status"] = "SOURCE_UNAVAILABLE"
        rec["cause"] = (open(err, encoding="utf-8").read()[:40] if os.path.exists(err)
                        else "no csv on disk")
        return rec, unresolved, {}

    src, unparsable = source_rows(text)
    rec["unparsable_rows"] = unparsable
    candles, volumes, all_rows = CH._parse_tsetmc_csv(text)
    meta = PB.apply_basis(candles, copy=True)
    applied = meta["basis_applied"]
    series = meta["candles"]
    served = {str(c["time"])[:10]: c for c in series}
    vol_by_date = {str(v["time"])[:10]: v["value"] for v in volumes}

    rec["source_rows"] = len(src)
    rec["served_candles"] = len(served)
    rec["basis_requested"] = meta["basis_requested"]
    rec["basis_applied"] = applied
    rec["basis_reason"] = meta["basis_reason"] or ""
    rec["last_missing"] = meta["last_missing"]
    rec["geometry_widened"] = meta["geometry_widened"]

    dates = sorted(served)
    if dates:
        rec["first_date"], rec["last_date"] = dates[0], dates[-1]
        gaps = [day_no(b) - day_no(a) for a, b in zip(dates, dates[1:])]
        rec["max_gap_days"] = max(gaps) if gaps else 0
        rec["gaps_over_10d"] = sum(1 for g in gaps if g > 10)
    rec["dup_dates"] = len(series) - len(served)
    # ترتیبِ *سیرِ یکدست* مدنظر است، نه صعودی‌بودن: `/api/chart` از مسیرِ CDN عمداً
    # نزولی می‌دهد و مسیرِ محلی صعودی — خودِ `_attach_live_bar` هر دو را مستند کرده
    # و رابط با `.sort(timestamp)` یکدست می‌کند. چیزی که نقص است، عوض‌شدنِ جهت
    # داخلِ همان سری است (بی‌نظمی)، پس همان سنجیده می‌شود.
    dirs, changes = None, 0
    for i in range(len(candles) - 1):
        a, b = str(candles[i]["time"])[:10], str(candles[i + 1]["time"])[:10]
        if a == b:
            continue
        d = "asc" if b > a else "desc"
        if dirs is None:
            dirs = d
        elif d != dirs:
            changes += 1
    rec["series_order"] = dirs or ("single" if len(candles) <= 1 else "all-equal")
    rec["order_mixed"] = changes

    # ۱) ردیف‌هایِ منبع: چرا کندل شدند یا نشدند (هیچ روزِ مفقودی پر نمی‌شود)
    for d, s in src.items():
        reason, exp = expected_candle(s, applied)
        if reason == "no_trade":
            rec["no_trade_rows"] += 1
        elif reason != "candle":
            rec["dropped_other_rows"] += 1
        elif d not in served:
            rec["missing_unexpected"] += 1
            unresolved.append((code, name, d, "candle_missing", "", "", "", "",
                               f"published row is a valid candle by the product's own rule "
                               f"but nothing is served for it (reason={reason})",
                               "UNRESOLVED"))
    for d in served:
        if d not in src:
            rec["extra_in_served"] += 1
            c = served[d]
            unresolved.append((code, name, d, "extra_candle", "",
                               json.dumps({k: c.get(k) for k in ("open", "high", "low", "close")}),
                               "", "",
                               "served candle has no row in the official source for that date",
                               "UNRESOLVED"))

    # ۲) تک‌تکِ کندل‌هایِ served در برابرِ ستون‌هایِ منتشرشده
    for d, c in served.items():
        vals = [c.get("open"), c.get("high"), c.get("low"), c.get("close")]
        if any(v is None or not isinstance(v, (int, float)) or math.isnan(v)
               or math.isinf(v) for v in vals):
            rec["bad_numbers"] += 1
            unresolved.append((code, name, d, "bad_number", "", "", "", "",
                               "non-finite OHLC in served candle", "UNRESOLVED"))
            continue
        o, h, l, cl = vals
        if not (l <= min(o, cl) + 1e-9 and h >= max(o, cl) - 1e-9 and l <= h):
            rec["invariant_violations"] += 1
            unresolved.append((code, name, d, "geometry", f"{o}/{h}/{l}/{cl}", "", "", "",
                               "served candle breaks Low<=min(O,C)<=max(O,C)<=High",
                               "UNRESOLVED"))
        s = src.get(d)
        if s is None:
            continue
        _reason, exp = expected_candle(s, applied)
        if exp is None:
            continue
        if s["first"] > 0 and abs(o - s["first"]) > 1e-9:
            rec["open_diff"] += 1
            unresolved.append((code, name, d, "open", s["first"], o,
                               round(abs(o - s["first"]), 6), rel(o, s["first"]),
                               "served open differs from <FIRST> (body rule of the parser)",
                               "UNRESOLVED"))
        if abs(cl - exp["close"]) > 1e-9:
            rec["close_diff"] += 1
            ad = abs(cl - exp["close"])
            rec["max_abs_close_diff"] = max(rec["max_abs_close_diff"], ad)
            rec["max_rel_close_diff"] = max(rec["max_rel_close_diff"], rel(cl, exp["close"]))
            col = "<LAST>" if applied == PB.LAST else "<CLOSE>"
            unresolved.append((code, name, d, "close", exp["close"], cl, round(ad, 6),
                               rel(cl, exp["close"]),
                               f"served close differs from {col} (basis_applied={applied})",
                               "UNRESOLVED"))
        sv = vol_by_date.get(d)
        if sv is None or abs(sv - s["vol"]) > 1e-6:
            rec["volume_diff"] += 1
            unresolved.append((code, name, d, "volume", s["vol"], sv,
                               round(abs((sv or 0) - s["vol"]), 6), rel(sv or 0, s["vol"]),
                               "served volume differs from <VOL>", "UNRESOLVED"))
        for field, served_v, pub_v, exp_v in (("high", h, s["high"], exp["high"]),
                                              ("low", l, s["low"], exp["low"])):
            if abs(served_v - pub_v) <= 1e-9:
                continue
            rec[field + "_diff"] += 1
            if abs(served_v - exp_v) > 1e-9:
                rec["widen_unexplained"] += 1
                unresolved.append((code, name, d, field, pub_v, served_v,
                                   round(abs(served_v - pub_v), 6), rel(served_v, pub_v),
                                   f"neither the published value nor the widen rule "
                                   f"(expected {exp_v}) — outside the documented geometry",
                                   "UNRESOLVED"))
            else:
                unresolved.append((code, name, d, field + "_widened", pub_v, served_v,
                                   round(abs(served_v - pub_v), 6), rel(served_v, pub_v),
                                   "shadow widened by the documented rule; no published "
                                   "price was lowered (expected)", "EXPLAINED"))

    # ۳) زنجیرۀِ تعدیل (Stage 3) — همان مسیری که `/api/chart` می‌سازد: کشفِ گسست از
    # CSV، تیزکردنِ ضریب با دفترِ مبدأ، و سپس `AE.chain_factors`. بی‌تیزکردن، زنجیرۀ
    # سنجیده‌شده با زنجیرۀِ served یکی نبود.
    factor_by_date = {}
    try:
        events, _anchored = CH._adjust_events_from_rows(all_rows)
        events, sharp_n, amb_n = CH._sharpen_events_with_ledger(name, events)
        rec["adj_sharpened"] = sharp_n
        rec["adj_ambiguous"] = amb_n
        led_n = sum(1 for e in events if e.get("source") in ("priceAdjust", "shareChange"))
        rec["adjust_source"] = ("ledger+base-price-discontinuity" if led_n
                                else "base-price-discontinuity" if events
                                else "base-not-anchored" if not _anchored
                                else "no-adjustment-event")
        times = [str(c["time"])[:10] for c in candles]
        _applied_ev, rejected, factors, chain, cov = CH._canonical_adjustment(name, times, events)
        factor_by_date = dict(zip(times, factors))
        rec["adj_events"] = len(events)
        rec["adj_rejected"] = len(rejected or [])
        if factor_by_date:
            vals = list(factor_by_date.values())
            rec["factor_min"] = f"{min(vals):.10f}"
            rec["factor_max"] = f"{max(vals):.10f}"
            rec["factor_above_one"] = sum(1 for v in vals if v > 1.0 + 1e-12)
            rec["factor_invalid"] = sum(1 for v in vals if not (math.isfinite(v) and v > 0))
            seq_dates = sorted(factor_by_date)
            ev_dates = sorted([(p["date"], p["ratio"]) for p in (chain.get("provenance") or [])
                               if p.get("ratio") is not None])
            jumps = check_factor_jumps(seq_dates, [factor_by_date[d] for d in seq_dates],
                                       ev_dates)
            rec["unexpected_factor_jumps"] = jumps["unexpected"]
            rec["factor_value_mismatch"] = jumps["mismatch"]
            rec["no_effect_events"] = jumps["no_effect"]
        rec["anchored_last"] = bool(chain.get("anchored_last"))
        rec["chain_complete"] = bool(chain.get("complete"))
        rec["chain_incomplete"] = len(chain.get("incomplete") or [])
        if isinstance(cov, dict):
            rec["coverage_start"] = str(cov.get("coverage_start") or "")
            rec["candles_before_coverage"] = int(cov.get("pre_coverage_candles") or 0)
            rec["ledger_rows_total"] = int(cov.get("rows_total") or 0)
            if cov.get("unresolved_events"):
                rec["cause"] = f"event-type-unresolved:{cov['unresolved_events']}"
        avail, blockers = CH._functional_state(chain, cov)
        rec["functional_available"] = "yes" if avail else "no"
        rec["functional_blockers"] = "|".join(blockers)[:200]

        #_seriesِ عملکردی، همان‌طور که رابط می‌سازد: خام × ضریب (بی‌هیچ گردِ زودهنگام)
        worst = 0.0
        for c in series:
            f = factor_by_date.get(str(c["time"])[:10])
            if f is None or not (math.isfinite(f) and f > 0):
                continue
            rec["adjusted_candles"] += 1
            for k in ("open", "high", "low", "close"):
                v = c.get(k)
                if isinstance(v, (int, float)) and v > 0:
                    worst = max(worst, abs(round(v * f) - (v * f)))
        rec["early_rounding_max_rial"] = round(worst, 6)
    except Exception as e:
        rec["status"] = "ADJUST_AUDIT_ERROR"
        rec["cause"] = (type(e).__name__ + ":" + str(e))[:140]
        return rec, unresolved, {}

    # ۴) مسیرِ خام دست‌نخورده مانده؟ (تعدیل باید خروجیِ جدا داشته باشد)
    for raw in candles:
        s = src.get(str(raw["time"])[:10])
        if s and abs(float(raw.get("close") or 0) - s["close"]) > 1e-9:
            rec["raw_path_mutated"] += 1

    if not rec["status"]:
        # `high_diff`/`low_diff` شمارۀِ روزهایی است که سایه با عددِ منتشرشده فرق دارد؛
        # تا وقتی `widen_unexplained` صفر است، همه‌شان دقیقاً قاعدۀِ مستندِ گِشاد‌کردن
        # هستند (هیچ قیمتِ منتشرشده‌ای کُنده نشده) و نقص شمرده نمی‌شوند.
        bad = (rec["close_diff"] + rec["open_diff"] + rec["volume_diff"]
               + rec["widen_unexplained"] + rec["invariant_violations"]
               + rec["bad_numbers"] + rec["dup_dates"] + rec["order_mixed"]
               + rec["extra_in_served"] + rec["missing_unexpected"] + rec["factor_invalid"]
               + rec["unexpected_factor_jumps"] + rec["factor_value_mismatch"]
               + rec["raw_path_mutated"])
        rec["status"] = "CLEAN" if bad == 0 else "DIFFS"
        parts = [f"{k}={rec[k]}" for k in ("close_diff", "open_diff", "volume_diff",
                                           "high_diff", "low_diff", "widen_unexplained",
                                           "invariant_violations", "missing_unexpected",
                                           "extra_in_served", "dup_dates", "order_mixed",
                                           "factor_invalid", "unexpected_factor_jumps",
                                           "factor_value_mismatch", "raw_path_mutated")
                 if rec[k]]
        rec["cause"] = (rec["cause"] + ";" if rec["cause"] else "") + ";".join(parts)

    ref = {d: {"raw": c["close"],
               "adj": (c["close"] * factor_by_date[d]
                       if factor_by_date.get(d) is not None else None)}
           for d, c in served.items()}
    return rec, unresolved, ref


def load_reference():
    """اسنپشاتِ فریزشدۀِ رهاورد: type0 = خام، type7 = عملکردی، روزانۀِ ۶۰۱ کندل."""
    if not os.path.exists(REF_BARS):
        return {}
    d = json.load(open(REF_BARS, encoding="utf-8"))
    out = {}
    for key, blk in (d.get("bars") or {}).items():
        parts = key.split("|")
        if len(parts) != 3 or parts[2] != "D" or not isinstance(blk, dict):
            continue
        if blk.get("status") != 200:
            continue
        bars = {}
        for b in blk.get("bars") or []:
            t = b.get("t")
            if not t:
                continue
            day = dt.datetime.fromtimestamp(t / 1000 + 3.5 * 3600,
                        dt.timezone.utc).strftime("%Y-%m-%d")
            bars[day] = b
        out.setdefault(parts[0], {})[parts[1]] = bars
    return out


def reference_join(rows, refs, ref_bars):
    out = []
    for rec in rows:
        name = rec["symbol"]
        if name not in ref_bars:
            continue
        rec["reference_available"] = "yes"
        raw_bars = ref_bars[name].get("type0") or {}
        adj_bars = ref_bars[name].get("type7") or {}
        mine = refs.get(rec["ins_code"]) or {}
        r = {"ins_code": rec["ins_code"], "symbol": name,
             "basis_applied": rec["basis_applied"],
             "ref_raw_bars": len(raw_bars), "ref_adj_bars": len(adj_bars),
             "dates_compared_raw": 0, "close_mismatch_raw": 0, "max_abs_raw": 0.0,
             "max_rel_raw": 0.0, "dates_compared_adj": 0, "close_mismatch_adj": 0,
             "max_abs_adj": 0.0, "max_rel_adj": 0.0,
             "adj_unavailable_dates": 0, "note": ""}
        for d, v in mine.items():
            b = raw_bars.get(d)
            if b and v["raw"] is not None:
                r["dates_compared_raw"] += 1
                ad = abs(v["raw"] - b["c"])
                if ad > 1e-6:
                    r["close_mismatch_raw"] += 1
                r["max_abs_raw"] = max(r["max_abs_raw"], ad)
                r["max_rel_raw"] = max(r["max_rel_raw"], rel(v["raw"], b["c"]))
            b = adj_bars.get(d)
            if b:
                if v["adj"] is None:
                    r["adj_unavailable_dates"] += 1
                    continue
                r["dates_compared_adj"] += 1
                ad = abs(v["adj"] - b["c"])
                if ad > 1e-6:
                    r["close_mismatch_adj"] += 1
                r["max_abs_adj"] = max(r["max_abs_adj"], ad)
                r["max_rel_adj"] = max(r["max_rel_adj"], rel(v["adj"], b["c"]))
        r["note"] = ("frozen Rahavard snapshot, 601 daily bars"
                     if (r["dates_compared_raw"] or r["dates_compared_adj"])
                     else "symbol in snapshot but no overlapping dates")
        out.append(r)
    return out


def _count(rows, key):
    out = {}
    for r in rows:
        v = r[key] if r[key] != "" else "-"
        out[v] = out.get(v, 0) + 1
    return out


def main():
    limit = int(os.environ.get("BORS_AUDIT_LIMIT", "0"))
    skip_crawl = os.environ.get("BORS_AUDIT_SKIP_CRAWL") == "1"
    codes = universe()
    log(f"universe read from DB: {len(codes)} instruments with a name")
    items = sorted(codes.items(), key=lambda kv: kv[0])
    if limit:
        items = items[:limit]
    if not skip_crawl:
        crawl([c for c, _ in items], workers=int(os.environ.get("BORS_AUDIT_WORKERS", "6")))

    t0 = time.time()
    rows, unresolved, refs = [], [], {}
    for i, (code, (name, paper)) in enumerate(items, 1):
        rec, un, ref = audit_symbol(code, name, paper)
        rows.append(rec)
        unresolved.extend(un)
        refs[code] = ref
        if i % 250 == 0 or i == len(items):
            cnt = lambda s: sum(1 for r in rows if r["status"] == s)
            log(f"  audited {i}/{len(items)} in {time.time()-t0:.0f}s "
                f"(CLEAN={cnt('CLEAN')}, DIFFS={cnt('DIFFS')}, "
                f"SOURCE_UNAVAILABLE={cnt('SOURCE_UNAVAILABLE')}, "
                f"ADJUST_AUDIT_ERROR={cnt('ADJUST_AUDIT_ERROR')})")

    ref_rows = reference_join(rows, refs, load_reference())

    # وضعیتِ خاموشی از خودِ داده خوانده می‌شود: فاصلهٔ آخرینِ کندلِ هر نماد تا
    # تازه‌ترینِ روزِ معاملاتیِ کلِ مجموعه (بی‌فهرستِ «فعال» درِ بانک نیست).
    newest = max((r["last_date"] for r in rows if r["last_date"]), default="")
    if newest:
        n_ord = day_no(newest)
        for r in rows:
            if r["last_date"]:
                r["stale_days"] = n_ord - day_no(r["last_date"])

    with open(MANIFEST, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=REC_KEYS)
        w.writeheader()
        w.writerows(rows)
    trunc = max(0, len(unresolved) - UNRESOLVED_CAP)
    with open(UNRESOLVED, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ins_code", "symbol", "date", "field", "source_value", "ours",
                    "abs_diff", "rel_diff", "cause", "status"])
        w.writerows(unresolved[:UNRESOLVED_CAP])
    with open(REFERENCE, "w", encoding="utf-8-sig", newline="") as f:
        fields = list(ref_rows[0].keys()) if ref_rows else ["ins_code", "symbol"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(ref_rows)

    def tot(k):
        return sum(r[k] for r in rows if isinstance(r[k], (int, float)))

    basis_counts = {}
    for r in rows:
        b = r["basis_applied"] or "-"
        basis_counts[b] = basis_counts.get(b, 0) + 1
    st = {
        "instruments": len(codes), "audited": len(rows),
        "by_status": {s: sum(1 for r in rows if r["status"] == s)
                      for s in ("CLEAN", "DIFFS", "SOURCE_UNAVAILABLE", "ADJUST_AUDIT_ERROR")},
        "source_rows": tot("source_rows"), "candles_compared": tot("served_candles"),
        "no_trade_rows": tot("no_trade_rows"), "dropped_other_rows": tot("dropped_other_rows"),
        "open_diff": tot("open_diff"), "high_diff": tot("high_diff"),
        "low_diff": tot("low_diff"), "close_diff": tot("close_diff"),
        "volume_diff": tot("volume_diff"), "widen_unexplained": tot("widen_unexplained"),
        "invariant_violations": tot("invariant_violations"), "bad_numbers": tot("bad_numbers"),
        "dup_dates": tot("dup_dates"), "order_mixed": tot("order_mixed"),
        "series_order_counts": _count(rows, "series_order"),
        "missing_unexpected": tot("missing_unexpected"), "extra_in_served": tot("extra_in_served"),
        "factor_invalid": tot("factor_invalid"),
        "unexpected_factor_jumps": tot("unexpected_factor_jumps"),
        "factor_value_mismatch": tot("factor_value_mismatch"),
        "no_effect_events": tot("no_effect_events"),
        "symbols_with_no_effect_events": sum(1 for r in rows if r["no_effect_events"]),
        "raw_path_mutated": tot("raw_path_mutated"),
        "adjusted_candles": tot("adjusted_candles"),
        "symbols_with_events": sum(1 for r in rows if r["adj_events"]),
        "symbols_chain_complete": sum(1 for r in rows if r["chain_complete"] is True),
        "symbols_functional_available": sum(1 for r in rows
                                            if r["functional_available"] == "yes"),
        "symbols_with_candles_before_coverage": sum(
            1 for r in rows if (r["candles_before_coverage"] or 0) > 0),
        "basis_applied_counts": basis_counts,
        "newest_trading_date": newest,
        "symbols_stale_over_30d": sum(1 for r in rows
                                      if isinstance(r["stale_days"], int) and r["stale_days"] > 30),
        "unresolved_rows": len(unresolved),
        "unresolved_written": min(len(unresolved), UNRESOLVED_CAP),
        "unresolved_truncated": trunc,
        "explained_rows": sum(1 for u in unresolved if u[9] == "EXPLAINED"),
        "reference_symbols": len(ref_rows),
        "reference_dates_raw": sum(r["dates_compared_raw"] for r in ref_rows),
        "reference_dates_adj": sum(r["dates_compared_adj"] for r in ref_rows),
        "reference_close_mismatch_raw": sum(r["close_mismatch_raw"] for r in ref_rows),
        "reference_close_mismatch_adj": sum(r["close_mismatch_adj"] for r in ref_rows),
        "elapsed_s": round(time.time() - t0),
    }
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    log("SUMMARY " + json.dumps(st, ensure_ascii=False))
    log("manifest: " + MANIFEST)
    log("unresolved: " + UNRESOLVED)
    log("reference: " + REFERENCE)


if __name__ == "__main__":
    main()
