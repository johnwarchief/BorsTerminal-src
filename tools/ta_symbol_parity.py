#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/ta_symbol_parity.py — سنجشِ نمادبه‌نماد با سریِ روزانۀ تریدرزآرنا (مرحلۀ ۶).

مرجع‌ها نقشِ یکی ندارند: TSETMC منبعِ خام است (سنجشِ کلِ universe در
`tools/board_field_parity.py`) و تریدرزآرنا **مرجعِ مستقل** است. آدرسِ سرویس حدس
نیست: `tradersarena.ir/data/{insCode}/prices?timeframe=0` — همان مسیری که
`tools/ra_parity.py` درِ کارِ چارت به کار می‌برد و پاسخ‌هایش درِ
`_audit/ra_probe_cache` کش شده بود.

ساختارِ سطرِ مرجع (ده‌ها سطر در ۱۴۰۵-۰۷-۲۳ دیده شد، بی‌حدس):
    [0] unixِ نشست  [1] open  [2] high  [3] low  [4] close  [5] volume
    [6] تاریخِ جلالیِ عددی  [7] [8] دو عددِ یکسان درِ همهٔ نمادها ⇒ شاخصِ خودِ
        مرجع است، نه دادۀ نماد — برایِ همین درِ شواهد می‌ماند و با ستون‌های
        نمادی مقایسه نمی‌شود.

قراردادِ سنجش:
  • سطرِ مرجع با «تاریخِ نشست» جفت می‌شود (unix → وقتِ تهران)، نه با این‌که
    آخرینِ سطر است. بی‌سطرِ هم‌تاریخ ⇒ `REFERENCE_UNAVAILABLE`؛ «هست» جا نمی‌زند.
  • `close` مرجع با **هر دو** مبنای ما (آخرین و پایانی) سنجیده می‌شود و گزارش
    می‌شود کدام‌شان می‌خواند — این همان پرسشِ `price_basis` است، نه انتخابِ من.
  • هیچ عددی hardcode نمی‌شود؛ هیچ غایبی صفر نمی‌شود.

مبنایِ دادهٔ خودِ برنامه: نشستِ کامل ازِ `daily_prices` خوانده می‌شود (هر چهار
قیمت + حجم/ارزش/تعدادِ همان نشست) — `market_watch` فقط آخرینِ snapshotِ زنده را
نگه می‌دارد و `price_first` ستونش نیست.

اجرا:  PYTHONIOENCODING=utf-8 python tools/ta_symbol_parity.py [--n 45] [--db market.db]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
import time
import urllib.request
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TA_URL = "https://tradersarena.ir/data/%s/prices?timeframe=0"
HDR = {"User-Agent": "Mozilla/5.0", "Referer": "https://tradersarena.ir/"}
CACHE = os.path.join(ROOT, "_audit", "ta_symbol_cache")
TEHRAN = dt.timezone(dt.timedelta(hours=3, minutes=30))

# (کلیدِ ما، شاخصِ ستونِ مرجع، برچسبِ سطر) — close جدا و با هر دو مبنای ما سنجیده می‌شود
FIELDS = (("p_first", 1, "open"), ("p_max", 2, "high"), ("p_min", 3, "low"),
          ("q_tot_tran", 5, "volume"))
COL_OF = {"p_first": 1, "p_max": 2, "p_min": 3, "q_tot_tran": 5,
          "p_closing": 4, "p_last": 4}


def fetch(ins_code, timeout=40):
    os.makedirs(CACHE, exist_ok=True)
    key = os.path.join(CACHE, "ta_%s.json" % ins_code)
    if os.path.isfile(key):
        return (json.load(open(key, encoding="utf-8")).get("candles") or []), "cache"
    try:
        req = urllib.request.Request(TA_URL % ins_code, headers=HDR)
        raw = json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace"))
    except Exception as e:                                # noqa: BLE001
        return None, "REFERENCE_UNAVAILABLE:%s" % type(e).__name__
    candles = raw.get("candles") or []
    json.dump({"candles": candles}, open(key, "w", encoding="utf-8"))
    return candles, "live"


def session_date(d_even: int) -> dt.date:
    return dt.date(d_even // 10000, (d_even // 100) % 100, d_even % 100)


def row_for_date(candles, want: dt.date):
    for r in reversed(candles or []):
        if len(r) < 7:
            continue
        try:
            d = dt.datetime.fromtimestamp(int(r[0]), TEHRAN).date()
        except (ValueError, OverflowError, TypeError):
            continue
        if d == want:
            return r
    return None


def verdict(ours, ref):
    if ref is None:
        return "MISSING_SOURCE"
    if ours is None:
        return "MISSING_MAPPING"
    if abs(ours - ref) <= max(1.0, 0.005 * abs(ref)):
        return "MATCH"
    return "MISMATCH"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=45)
    ap.add_argument("--db", default=os.path.join(ROOT, "market.db"))
    ap.add_argument("--out", default=os.path.join(ROOT, "_audit", "market_parity_20261014"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    p = os.path.abspath(a.db).replace(chr(92), "/")
    c = sqlite3.connect("file:" + p + "?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    day = c.execute("SELECT MAX(d_even) FROM daily_prices").fetchone()[0]
    want = session_date(day)
    print("نشستِ بانک: %s ⇒ %s" % (day, want.isoformat()))

    SQL = ("SELECT m.ins_code, i.l_val18 sym, i.l_val30 name, i.paper_type,"
           " m.p_closing, m.p_last, m.price_first AS p_first,"
           " m.price_max AS p_max, m.price_min AS p_min,"
           " m.q_tot_tran, m.q_tot_cap, m.z_tot_tran"
           " FROM daily_prices m JOIN instruments i ON i.ins_code = m.ins_code"
           " WHERE m.d_even=? AND ")

    def q(order, k, cond):
        return c.execute(SQL + cond + " ORDER BY " + order + " LIMIT ?", (day, k)).fetchall()

    picks = (q("m.q_tot_cap DESC", 12, "m.q_tot_tran > 0")
             + q("m.q_tot_cap ASC", 6, "m.q_tot_tran > 0")
             + q("m.q_tot_cap DESC", 8, "i.l_val30 LIKE '%صندوق%'")
             + q("m.q_tot_cap DESC", 8, "i.l_val18 LIKE 'ض%'")
             + q("m.q_tot_cap DESC", 5, "i.l_val18 LIKE 'ط%'")
             + q("m.ins_code", 8, "COALESCE(m.q_tot_tran,0) = 0"))
    seen, rows = set(), []
    for r in picks:
        if not r["ins_code"] or r["ins_code"] in seen:
            continue
        seen.add(r["ins_code"])
        rows.append(r)
    rows = rows[:a.n]
    kinds = dict(Counter(str(r["paper_type"]) for r in rows))
    print("نمونۀ متنوع: %d نماد | نوع‌ها: %s\n" % (len(rows), kinds))

    tally = Counter()
    basis = Counter()
    results = []
    for r in rows:
        candles, src = fetch(r["ins_code"])
        hit = row_for_date(candles, want) if candles else None
        rec = {"ins_code": r["ins_code"], "symbol": r["sym"], "name": r["name"],
               "paper_type": r["paper_type"], "source": src, "ref_found": hit is not None,
               "ours": {k: r[k] for k in ("p_closing", "p_last", "p_first", "p_max", "p_min",
                                          "q_tot_tran", "q_tot_cap", "z_tot_tran")},
               "ref_row": hit, "ref_index": [hit[7], hit[8]] if hit and len(hit) > 8 else None,
               "status": {}}
        if hit is None:
            rec["status"] = {"_all": src if candles is None else "NO_ROW_FOR_SESSION"}
            results.append(rec)
            time.sleep(0.15)
            continue
        for ours_key, idx, label in FIELDS:
            rv = float(hit[idx]) if hit[idx] is not None else None
            st = verdict(r[ours_key], rv)
            rec["status"][ours_key] = st
            tally["%s:%s" % (label, st)] += 1
        for ours_key, label in (("p_closing", "close_vs_پایانی"), ("p_last", "close_vs_آخرین")):
            rv = float(hit[4]) if hit[4] is not None else None
            st = verdict(r[ours_key], rv)
            rec["status"][ours_key] = st
            tally["%s:%s" % (label, st)] += 1
            if st == "MATCH":
                basis[label] += 1
        results.append(rec)
        time.sleep(0.15)

    n = len(results)
    found = sum(1 for x in results if x["ref_found"])
    labels = ["open", "high", "low", "volume", "close_vs_پایانی", "close_vs_آخرین"]
    print("=" * 78)
    print("%-26s %8s %8s %8s %8s" % ("سنجش", "MATCH", "MISMATCH", "بی‌مرجع", "بی‌ما"))
    print("-" * 78)
    for key in labels:
        t = {k.split(":")[1]: v for k, v in tally.items() if k.split(":")[0] == key}
        print("%-26s %8d %8d %8d %8d" % (key, t.get("MATCH", 0), t.get("MISMATCH", 0),
                                         t.get("MISSING_SOURCE", 0), t.get("MISSING_MAPPING", 0)))
    print("-" * 78)
    print("سطرِ مرجعِ هم‌تاریخ: %d از %d نماد | «close» مرجع با کدام مبنای ما می‌خواند: %s"
          % (found, n, dict(basis)))

    print("\nاختلاف‌های باقی‌مانده (با عددِ دو طرف):")
    shown = 0
    for x in results:
        bad = [k for k, v in x["status"].items() if v == "MISMATCH"]
        if not bad or shown >= 14:
            continue
        shown += 1
        parts = ["%s ما=%s مرجع=%s" % (k, x["ours"].get(k),
                                       (x["ref_row"] or [None] * 9)[COL_OF[k]]) for k in bad]
        print("  %-11s %-4s %s" % ((x["symbol"] or "?")[:11], x["paper_type"], " | ".join(parts)))

    out = os.path.join(a.out, "ta_symbol_parity_%s.json" % dt.datetime.now().strftime("%H%M%S"))
    json.dump({"session": day, "sample": n, "ref_found": found, "paper_types": kinds,
               "tally": dict(tally), "close_basis_match": dict(basis), "rows": results},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    c.close()
    print("\nشواهد: %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
