#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 18 Track A: Rahavard type0 semantics and contract-aware parity."""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

spec = importlib.util.spec_from_file_location(
    "rav", os.path.join(ROOT, "tools", "ra365_round18_rahavard_parity.py"))
RV = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RV)

P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   ← %s" % (detail,)) if detail else ""))


def tsetmc(first=100, high=110, low=90, close=105, volume=1000, base=99, last=108):
    return {"first": first, "high": high, "low": low, "close": close,
            "volume": volume, "base": base, "last": last}


def t0(o=100, h=110, lo=90, c=108, v=1000):
    return {"open": o, "high": h, "low": lo, "close": c, "volume": v}


def test_widen_official_close():
    print("\n[1] widen uses official close, not type0 last")
    hi, lo = RV.widen(1903, 1903, 1900, 1912)
    ck((hi, lo) == (1912, 1900), "official close 1912 widens high; low stays 1900",
       (hi, lo))
    hi2, lo2 = RV.widen(100, 110, 90, 105)
    ck((hi2, lo2) == (110, 90), "normal body leaves H/L untouched", (hi2, lo2))


def test_status():
    print("\n[2] exact/tolerance/rounding")
    ck(RV.status(100, 100) == "EXACT", "equal exact")
    ck(RV.status(100, 100.4) == "TOL", "0.4 is tolerance")
    ck(RV.status(1_000_000, 1_000_400) == "ROUNDING", "0.04% is rounding-only")
    ck(RV.status(100, 101) == "DIFF", "1 rial is diff")


def test_causes():
    print("\n[3] cause attribution")
    t = tsetmc()
    cause = RV.classify("high_raw", 2458, 2385, t0(2458, 2458, 2458, 2458, 100),
                        t, "closing", 2385, [], True, False)
    ck(cause[0] == "CANDLE_GEOMETRY", "flat type0 bar is a reference geometry issue", cause)
    cause = RV.classify("volume", 1000, 0, t0(), t, "last", 108, [], False, False)
    ck(cause[0] == "PARSING_OR_TRANSFORM",
       "product snapshot zero vs TSETMC positive is a transform/gap", cause)
    tz = tsetmc(volume=0)
    cause = RV.classify("volume", 1000, 0, t0(), tz, "last", 108, [], False, False)
    ck(cause[0] == "SOURCE_DATA_DIVERGENCE",
       "type0-only volume is a source divergence, not a product transform", cause)
    cause = RV.classify("close_display", 108, 105, t0(), t, "closing", 105, [], False, False)
    ck(cause[0] == "FIELD_MAPPING", "closing basis is a field mapping, not raw error", cause)
    cause = RV.classify("last", 100, 108, t0(), t, "last", 108, [], False, False)
    ck(cause[0] == "SOURCE_DATA_DIVERGENCE", "product matches TSETMC LAST", cause)
    t2 = tsetmc(last=100)
    cause = RV.classify("last", 100, 99, t0(), t2, "last", 99, [], False, False)
    ck(cause[0] == "HISTORICAL_REVISION", "type0/TSETMC agree, product is revised",
       cause)


def test_real_semantics():
    print("\n[4] real type0 semantics snapshot")
    import json
    p = os.path.join(ROOT, "artifacts", "ra365", "r18-rahavard",
                     "rahavard-raw-ohlc-summary.json")
    if not os.path.exists(p):
        print("  SKIP summary missing")
        return
    s = json.load(open(p, encoding="utf-8"))
    t = s["type0_vs_tsetmc"]
    ck(t["close_last_exact_pct"] > 99.5, "type0 close is LAST, not official", t)
    ck(t["close_official_exact_pct"] < 20, "official CLOSE is not type0 close", t)
    ck(t["open_first_exact_pct"] > 99.5 and t["open_base_exact_pct"] < 10,
       "type0 open is FIRST, not base", t)
    ck(s["contract_ok_pct"] > 99.5 and s["row_exact_pct"] > 99.5,
       "contract-aware raw parity is high", (s["contract_ok_pct"], s["row_exact_pct"]))


if __name__ == "__main__":
    test_widen_official_close()
    test_status()
    test_causes()
    test_real_semantics()
    print("\n%d passed, %d failed" % (P, F))
    sys.exit(1 if F else 0)
