#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""probe_ingestion.py — فاز ۴٫۷: بازتولیدِ یافته‌هایِ فاز ۴٫۵ روی دادهٔ واقعی.

این ابزار **هیچ چیزی را اصلاح نمی‌کند** و رویِ بانکِ عملیاتی نمی‌نویسد: فقط با
`mode=ro` رویِ یک کپیِ آزمایشگاهی (پیش‌فرض `_audit/phase47/lab/market.db`) خوانده
می‌شود و یک JSON + خلاصهٔ Markdown می‌دهد. هر عدد در گزارشِ فاز ۴٫۷ باید از این
خروجی بیاید، نه از نقلِ عددِ گزارشِ قبلی.

سنجه‌ها (هر کدام یک پرسشِ مستقل):

  A) موجودی و provenance — تعدادِ ردیف، بازهٔ تاریخ، توزیعِ `src`، و سهمِ ردیف‌هایِ
     بدونِ `src` (ادعایِ «کندل‌هایِ قدیمی فاقدِ src»).
  B) تهی‌بودنِ فیلدها — `last` تهی، حجمِ صفر/تهی، OHLCِ تهی، و نقضِ هندسه
     (high < max(open,close) یا low > min(open,close) یا low <= 0).
  C) معنایِ `last` — آیا `last` با `close` یکی است (یعنی کسی جای‌شان را عوض
     کرده) یا واقعاً «آخرین معامله» است؛ و نرخِ پرشدنِ آن به تفکیکِ `src`.
  D) حراج در `low` — `low`ِ کندل با `price_min`ِ همان نشست در `daily_prices`
     مقایسه می‌شود. `low < price_min` یعنی کفِ کندل از کفِ دامنهٔ ثبت‌شدهٔ تابلو
     پایین‌تر است: تنها منبعِ ممکن برایِ چنین عددی معاملهٔ خارج از دامنه (حراجِ
     پایانی) است. این تعریف **محلی** است و به دادهٔ مرجع نیاز ندارد.
  E) جابه‌جایی/تکرارِ ردیفِ تابلو — هر کندلِ `src='board'` با ردیفِ
     `daily_prices`ِ همان نماد و همان `d_even` مقایسه می‌شود. اگر با ردیفِ همان
     روز نخواند ولی با ردیفِ روزِ مجاور خواند، «جابه‌جایی» است نه «اختلافِ منبع».
  F) تکرارِ حجم — حجمِ یک کندل با حجمِ کندلِ نشستِ قبل/بعد مقایسه می‌شود.

استفاده:
    python tools/phase47/probe_ingestion.py --db _audit/phase47/lab/market.db \\
        --out _audit/phase47/probe.json --md _audit/phase47/probe.md
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

SRC_UNKNOWN = "(null)"
SRC_LEGACY = "(empty)"


def iso(deven) -> str | None:
    s = str(deven or "").strip()
    if len(s) != 8 or not s.isdigit():
        return None
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"


def connect_ro(path: str) -> sqlite3.Connection:
    uri = "file:%s?mode=ro" % path.replace("\\", "/")
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    return con


def table_names(con) -> set[str]:
    return {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def probe_a_inventory(con) -> dict:
    total, syms, dmin, dmax = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(date), MAX(date) FROM price_history"
    ).fetchone()
    src = {}
    for row in con.execute(
            "SELECT COALESCE(src, ?) AS s, COUNT(*) AS n FROM price_history GROUP BY 1 "
            "ORDER BY n DESC", (SRC_UNKNOWN,)):
        src[row["s"]] = row["n"]
    legacy = sum(n for s, n in src.items() if s in (SRC_UNKNOWN, SRC_LEGACY))
    return {"rows": total, "symbols": syms, "date_min": dmin, "date_max": dmax,
            "src": src, "src_missing_rows": legacy,
            "src_missing_pct": round(100.0 * legacy / total, 2) if total else None}


def probe_b_nulls(con) -> dict:
    def one(sql):
        return con.execute(sql).fetchone()[0]
    last_null = one("SELECT COUNT(*) FROM price_history WHERE last IS NULL")
    vol_zero = one("SELECT COUNT(*) FROM price_history "
                   "WHERE volume IS NULL OR volume <= 0")
    ohlc_null = one("SELECT COUNT(*) FROM price_history WHERE open IS NULL OR high IS NULL "
                    "OR low IS NULL OR close IS NULL")
    zero_price = one("SELECT COUNT(*) FROM price_history WHERE close IS NULL OR close <= 0")
    geom = one(
        "SELECT COUNT(*) FROM price_history WHERE open > 0 AND close > 0 AND ("
        " COALESCE(high,0) <= 0 OR COALESCE(low,0) <= 0"
        " OR COALESCE(high,0) < MAX(open, close)"
        " OR COALESCE(low,999999999999) > MIN(open, close))")
    # last == close یعنی «آخرین» با «پایانی» یکی نوشته شده؛ نه liveness، نه غیبت.
    last_eq_close = one("SELECT COUNT(*) FROM price_history "
                        "WHERE last IS NOT NULL AND close IS NOT NULL AND last = close")
    last_differs = one("SELECT COUNT(*) FROM price_history "
                       "WHERE last IS NOT NULL AND close IS NOT NULL AND last <> close")
    return {"last_null": last_null, "volume_zero_or_null": vol_zero,
            "ohlc_null": ohlc_null, "close_zero_or_null": zero_price,
            "geometry_violations": geom,
            "last_equals_close": last_eq_close, "last_differs_close": last_differs}


def probe_c_last_by_src(con) -> dict:
    out = {}
    for row in con.execute(
            "SELECT COALESCE(src, ?) AS s, COUNT(*) AS n,"
            " SUM(CASE WHEN last IS NULL THEN 1 ELSE 0 END) AS null_last,"
            " SUM(CASE WHEN last IS NOT NULL AND close IS NOT NULL AND last = close"
            "     THEN 1 ELSE 0 END) AS eq"
            " FROM price_history GROUP BY 1 ORDER BY n DESC", (SRC_UNKNOWN,)):
        n = row["n"] or 0
        out[row["s"]] = {
            "rows": n, "last_null": row["null_last"],
            "last_null_pct": round(100.0 * (row["null_last"] or 0) / n, 2) if n else None,
            "last_equals_close": row["eq"],
        }
    return out


def probe_d_auction(con) -> dict:
    """lowِ کندل در برابرِ price_minِ همان نشست در daily_prices."""
    rows = con.execute("""
        SELECT p.symbol, p.date, p.low, p.last, p.close, p.src,
               d.price_min, d.price_max, d.p_closing, d.p_last
        FROM price_history p
        JOIN (SELECT l_val18 AS sym, MIN(ins_code) AS ins_code FROM instruments
              WHERE l_val18 IS NOT NULL GROUP BY l_val18) i ON i.sym = p.symbol
        JOIN daily_prices d ON d.ins_code = i.ins_code
             AND d.d_even = CAST(REPLACE(p.date, '-', '') AS INTEGER)
        WHERE p.low > 0 AND d.price_min > 0
    """).fetchall()
    n = len(rows)
    below = [r for r in rows if r["low"] < r["price_min"]]
    above = [r for r in rows if r["low"] > r["price_min"]]
    low_eq_last = [r for r in below
                   if r["last"] is not None and r["low"] == r["last"]]
    low_eq_closing = [r for r in below
                      if r["close"] is not None and r["low"] == r["close"]]
    examples = [{"symbol": r["symbol"], "date": r["date"], "low": r["low"],
                 "board_price_min": r["price_min"], "last": r["last"],
                 "close": r["close"], "src": r["src"]}
                for r in below[:10]]
    return {
        "comparable_rows": n,
        "low_below_board_min": len(below),
        "low_above_board_min": len(above),
        "low_below_and_equals_last": len(low_eq_last),
        "low_below_and_equals_closing": len(low_eq_closing),
        "symbols_affected": len({r["symbol"] for r in below}),
        "examples": examples,
    }


def probe_e_board_alignment(con) -> dict:
    """هر کندلِ board باید با ردیفِ تابلوِ همان روز یکی باشد."""
    rows = con.execute("""
        SELECT p.symbol, p.date, p.open, p.high, p.low, p.close, p.volume,
               d.d_even, d.price_first, d.price_max, d.price_min, d.p_closing,
               d.q_tot_tran
        FROM price_history p
        JOIN (SELECT l_val18 AS sym, MIN(ins_code) AS ins_code FROM instruments
              WHERE l_val18 IS NOT NULL GROUP BY l_val18) i ON i.sym = p.symbol
        JOIN daily_prices d ON d.ins_code = i.ins_code
             AND d.d_even = CAST(REPLACE(p.date, '-', '') AS INTEGER)
        WHERE COALESCE(p.src, '') = 'board'
    """).fetchall()
    n = len(rows)
    mism = {"open": 0, "high": 0, "low": 0, "close": 0, "volume": 0}
    any_mismatch = []
    for r in rows:
        bad = []
        if abs((r["open"] or 0) - (r["price_first"] or 0)) > 0.5:
            bad.append("open")
        if abs((r["close"] or 0) - (r["p_closing"] or 0)) > 0.5:
            bad.append("close")
        if abs((r["volume"] or 0) - (r["q_tot_tran"] or 0)) > 0.5:
            bad.append("volume")
        # high/low از widen می‌گذرند، پس فقط «کوچک‌تر از تابلو» نقص است.
        if (r["high"] or 0) + 0.5 < (r["price_max"] or 0):
            bad.append("high")
        if (r["low"] or 0) - 0.5 > (r["price_min"] or 0) and r["low"]:
            bad.append("low")
        if bad:
            any_mismatch.append({"symbol": r["symbol"], "date": r["date"], "fields": bad,
                                 "open": r["open"], "board_first": r["price_first"],
                                 "close": r["close"], "board_closing": r["p_closing"],
                                 "volume": r["volume"], "board_vol": r["q_tot_tran"]})
            for f in bad:
                mism[f] += 1
    # جابه‌جایی: کندل با ردیفِ روزِ مجاور می‌خواند، نه خودش.
    near = con.execute("""
        SELECT COUNT(*) FROM price_history p
        JOIN (SELECT l_val18 AS sym, MIN(ins_code) AS ins_code FROM instruments
              WHERE l_val18 IS NOT NULL GROUP BY l_val18) i ON i.sym = p.symbol
        JOIN daily_prices d ON d.ins_code = i.ins_code
             AND d.d_even <> CAST(REPLACE(p.date, '-', '') AS INTEGER)
             AND ABS(d.q_tot_tran - COALESCE(p.volume, -1)) < 0.5
             AND d.q_tot_tran > 0
        WHERE COALESCE(p.src, '') = 'board'
    """).fetchone()[0]
    return {"board_rows_with_board_counterpart": n, "mismatch_by_field": mism,
            "rows_with_any_mismatch": len(any_mismatch),
            "examples": any_mismatch[:12],
            "volume_matches_a_different_session": near}


def probe_f_volume_repeat(con, symbols: list[str]) -> dict:
    out = {}
    for sym in symbols:
        rows = con.execute(
            "SELECT date, volume, close, last, src FROM price_history "
            "WHERE symbol = ? ORDER BY date", (sym,)).fetchall()
        repeats = []
        for prev, cur in zip(rows, rows[1:]):
            if prev["volume"] and prev["volume"] == cur["volume"]:
                repeats.append({"date": cur["date"], "volume": cur["volume"],
                                "same_as": prev["date"], "src": cur["src"]})
        out[sym] = {"rows": len(rows), "identical_volume_to_previous": len(repeats),
                    "examples": repeats[:8]}
    return out


def probe_g_foulad_window(con, symbol: str, start: str, end: str) -> dict:
    """پنجرهٔ نمونهٔ گزارشِ فاز ۴٫۵ برایِ یک نماد، ردیف‌به‌ردیف."""
    bars = [dict(r) for r in con.execute(
        "SELECT date, open, high, low, close, volume, last, value, src "
        "FROM price_history WHERE symbol = ? AND date BETWEEN ? AND ? ORDER BY date",
        (symbol, start, end)).fetchall()]
    board = [dict(r) for r in con.execute("""
        SELECT printf('%04d-%02d-%02d', d.d_even/10000, (d.d_even/100)%100, d.d_even%100) AS date,
               d.price_first, d.price_max, d.price_min, d.p_closing, d.q_tot_tran, d.p_last
        FROM daily_prices d JOIN instruments i ON i.ins_code = d.ins_code
        WHERE (i.l_val18 = ? OR i.l_val30 = ?)
          AND printf('%04d-%02d-%02d', d.d_even/10000, (d.d_even/100)%100, d.d_even%100)
              BETWEEN ? AND ?
        ORDER BY d.d_even""", (symbol, symbol, start, end)).fetchall()]
    return {"symbol": symbol, "window": [start, end], "price_history": bars,
            "daily_prices": board}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--md", default="")
    ap.add_argument("--window-symbol", default="فولاد")
    ap.add_argument("--window-start", default="2026-10-10")
    ap.add_argument("--window-end", default="2026-11-05")
    ap.add_argument("--repeat-symbols", default="فولاد,وبملت,فملي")
    args = ap.parse_args()

    if not os.path.exists(args.db):
        print("db not found: %s" % args.db, file=sys.stderr)
        return 2
    con = connect_ro(args.db)
    try:
        tables = table_names(con)
        out = {"db": os.path.abspath(args.db), "tables_present": sorted(tables)}
        out["A_inventory"] = probe_a_inventory(con)
        out["B_nulls"] = probe_b_nulls(con)
        out["C_last_by_src"] = probe_c_last_by_src(con)
        if "daily_prices" in tables and "instruments" in tables:
            out["D_auction_low"] = probe_d_auction(con)
            out["E_board_alignment"] = probe_e_board_alignment(con)
            out["G_window"] = probe_g_foulad_window(
                con, args.window_symbol, args.window_start, args.window_end)
        else:
            out["D_auction_low"] = {"skipped": "daily_prices/instruments missing"}
            out["E_board_alignment"] = {"skipped": "daily_prices/instruments missing"}
        out["F_volume_repeat"] = probe_f_volume_repeat(
            con, [s for s in args.repeat_symbols.split(",") if s])
    finally:
        con.close()

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    if args.md:
        a, b = out["A_inventory"], out["B_nulls"]
        d = out.get("D_auction_low", {})
        e = out.get("E_board_alignment", {})
        lines = [
            "| سنجه | مقدار |", "| --- | --- |",
            "| ردیف‌هایِ `price_history` | %s |" % a["rows"],
            "| نمادها | %s |" % a["symbols"],
            "| بازهٔ تاریخ | %s → %s |" % (a["date_min"], a["date_max"]),
            "| ردیف‌هایِ بدونِ `src` | %s (%s%%) |" % (a["src_missing_rows"],
                                                      a["src_missing_pct"]),
            "| `last` تهی | %s |" % b["last_null"],
            "| حجمِ صفر/تهی | %s |" % b["volume_zero_or_null"],
            "| نقضِ هندسه | %s |" % b["geometry_violations"],
            "| `last` = `close` | %s |" % b["last_equals_close"],
            "| `low` < کفِ تابلو | %s از %s |" % (d.get("low_below_board_min"),
                                                  d.get("comparable_rows")),
            "| از آن، `low` = `last` | %s |" % d.get("low_below_and_equals_last"),
            "| کندلِ `board` ناهم‌خوان با تابلو | %s از %s |" % (
                e.get("rows_with_any_mismatch"), e.get("board_rows_with_board_counterpart")),
            "| حجم برابر با نشستِ دیگر | %s |" % e.get("volume_matches_a_different_session"),
        ]
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    print(json.dumps({k: out[k] for k in ("A_inventory", "B_nulls")},
                     ensure_ascii=False, indent=1))
    print("written", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
