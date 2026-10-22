#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 18: raw OHLC mapping, basis, tolerance and cause classification.

These pin the definitions used by tools/ra365_round18_raw.py:
  * production open is FIRST (not the base <OPEN> column),
  * no-trade rows never become candles,
  * high/low are widened around the body, never the close,
  * the display close is basis-selected while closing stays the anchor,
  * raw parity never applies a factor.
"""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import api.chart as C  # noqa: E402
import price_basis as PB  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "r18", os.path.join(ROOT, "tools", "ra365_round18_raw.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)

P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   ← %s" % (detail,)) if detail else ""))


HEAD = ("<TICKER>,<DTYYYYMMDD>,<FIRST>,<HIGH>,<LOW>,<CLOSE>,<VALUE>,<VOL>,"
        "<OPENINT>,<PER>,<OPEN>,<LAST>\r\n")
CSV = HEAD + "\n".join([
    "19900101,20200101,100.00,110.00,90.00,105.00,1000,500,1,D,95.00,108.00",
    "19900101,20200102,0.00,0.00,0.00,104.00,0,0,0,D,105.00,0.00",
    "19900101,20200103,0.00,120.00,100.00,115.00,1000,500,1,D,104.00,118.00",
    "19900101,20200104,80.00,100.00,90.00,95.00,1000,500,1,D,95.00,99.00",
]) + "\r\n"


def test_parser_mapping():
    print("\n[1] CSV field mapping")
    candles, volumes, all_rows = C._parse_tsetmc_csv(CSV)
    ck(len(candles) == 3, "no-trade row (H=L=0, VOL=0) does not become a candle",
       len(candles))
    c0 = candles[0]
    ck(c0["open"] == 100.0, "open is FIRST, not base OPEN (95)", c0)
    ck(c0["high"] == 110.0 and c0["low"] == 90.0, "H/L kept when body fits", c0)
    ck(c0["close"] == 105.0, "close is official CLOSE", c0)
    ck(c0["last"] == 108.0, "last is LAST", c0)
    c1 = candles[1]
    ck(c1["open"] == 104.0, "FIRST=0 falls back to base clamped into [L,H]", c1)
    c2 = candles[2]
    ck(c2["open"] == 80.0 and c2["low"] == 80.0 and c2["high"] == 100.0,
       "widen() lowers LOW to contain the body, HIGH untouched", c2)
    ck(c2["close"] == 95.0, "widen() never changes close", c2)
    ck(volumes[0]["value"] == 500.0 and len(volumes) == 3, "volume follows candles",
       volumes)
    ck(len(all_rows) == 4, "no-trade row stays in all_rows for adjustment detection",
       len(all_rows))


def test_eff_open():
    print("\n[2] effective open")
    ck(R._eff_open(100, 95, 110, 90, 105) == 100.0, "FIRST wins when positive")
    ck(R._eff_open(0, 95, 110, 90, 105) == 95.0, "base clamped into [L,H]")
    ck(R._eff_open(0, 130, 110, 90, 105) == 110.0, "base clamped down to H")
    ck(R._eff_open(0, 0, 0, 0, 105) == 105.0, "no base -> close fallback")


def test_basis():
    print("\n[3] basis contract")
    old = PB.current
    try:
        PB.current = lambda: "last"
        c = [{"open": 100, "high": 110, "low": 90, "close": 105, "last": 108}]
        meta = PB.apply_basis(c)
        ck(meta["basis_applied"] == "last", "last requested and available", meta)
        ck(c[0]["closing"] == 105.0, "closing is the official anchor", c[0])
        ck(c[0]["close"] == 108.0, "close is the chosen last", c[0])
        ck(c[0]["high"] == 110.0 and c[0]["low"] == 90.0, "body inside H/L: no widen", c[0])
        c2 = [{"open": 100, "high": 110, "low": 90, "close": 105, "last": 115}]
        PB.apply_basis(c2)
        ck(c2[0]["high"] == 115.0 and c2[0]["high_raw"] == 110.0,
           "display last outside H/L widens shadow; high_raw preserved", c2[0])
        c3 = [{"open": 100, "high": 110, "low": 90, "close": 105, "last": None}]
        m3 = PB.apply_basis(c3)
        ck(m3["basis_applied"] == "closing", "any missing last switches whole series", m3)
        ck(c3[0]["close"] == 105.0, "switched series uses closing", c3[0])
        ck("last_missing" in (m3.get("basis_reason") or ""), "switch is declared", m3)
    finally:
        PB.current = old


def test_status():
    print("\n[4] exact vs tolerance")
    ck(R._status(100, 100) == "EXACT", "equal is exact")
    ck(R._status(100, 100.4) == "TOL", "0.4 rial is tolerance, not exact")
    ck(R._status(1_000_000, 1_000_400) == "ROUNDING", "0.04% is rounding-only")
    ck(R._status(100, 101) == "DIFF", "1 rial on 100 is a real diff")
    ck(R._status(None, 100) == "NULL" and R._status(100, None) == "NULL", "missing is null")


def test_classification():
    print("\n[5] cause taxonomy")
    # (date, first, high, low, close, volume, base, last)
    t = ("2012-12-24", 3150.0, 3200.0, 3140.0, 3264.0, 236610.0, 3148.0, 3290.0)
    c = ["2012-12-24", 3150.0, 3264.0, 3140.0, 3290.0, 3264.0, 3290.0,
         3264.0, 3140.0, 236610.0, "last"]
    cause = R.classify_diff("high_literal", 3200.0, 3264.0, t, c, "last", None)
    ck(cause[0] == "PARSING_OR_TRANSFORM", "H below close -> widen transform", cause)
    c0 = (11500.0, 11500.0, 11000.0, 11200.0, 6087928.0)
    cause = R.classify_diff("close_last", 11000.0, 11200.0, t, c, "last", c0)
    ck(cause[0] == "SOURCE_DATA_DIVERGENCE", "product matches type0 -> source divergence",
       cause)
    c_rev = ["2025-06-09", 2960.0, 3043.0, 2960.0, 2960.0, 3043.0, 3043.0,
             3043.0, 2960.0, 414090.0, "last"]
    cause = R.classify_diff("close_last", 3044.0, 2960.0, t, c_rev, "last", None)
    ck(cause[0] == "HISTORICAL_REVISION", "snapshot last differs from both sides",
       cause)
    cause = R.classify_diff("close_official", 100.0, 1000.0, t, c, "last", None)
    ck(cause[0] == "PRICE_SCALE_OR_UNIT", "10x ratio flagged", cause)
    cause = R.classify_diff("close_official", 1_000_000.0, 1_000_400.0, t, c,
                            "last", None)
    ck(cause[0] == "PRECISION_OR_ROUNDING", "rounding flagged", cause)


def test_raw_is_independent_of_factor():
    print("\n[6] raw never applies a factor")
    candles, _, _ = C._parse_tsetmc_csv(CSV)
    before = [(x["open"], x["high"], x["low"], x["close"], x["last"]) for x in candles]
    # A factor column may exist in the product payload; it must not be read here.
    ck(before[0] == (100.0, 110.0, 90.0, 105.0, 108.0),
       "parser returns raw values with no factor input", before[0])
    ck(R._status(105.0, candles[0]["close"]) == "EXACT",
       "raw compare reads the raw close", candles[0])
    ck(R._status(105.0, candles[0]["close"] * 0.5) == "DIFF",
       "an applied half-factor would be visible as a diff")


if __name__ == "__main__":
    test_parser_mapping()
    test_eff_open()
    test_basis()
    test_status()
    test_classification()
    test_raw_is_independent_of_factor()
    print("\n%d passed, %d failed" % (P, F))
    sys.exit(1 if F else 0)
