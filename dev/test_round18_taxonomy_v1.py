#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 18: raw-mismatch attribution picks the evidence-backed cause."""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

spec = importlib.util.spec_from_file_location(
    "tax", os.path.join(ROOT, "tools", "ra365_round18_taxonomy.py"))
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)

P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   ← %s" % (detail,)) if detail else ""))


# (date, first, high, low, close, volume, base, last)
ROW = ("2020-01-01", 100.0, 105.0, 95.0, 100.0, 1000.0, 99.0, 101.0)
# product row: [date, open, high, low, close, closing, last, high_raw, low_raw, vol, basis]
PROD = ["2020-01-01", 99.0, 105.0, 95.0, 101.0, 101.0, 101.0, 105.0, 95.0, 1000.0, "last"]
ASSET = {"basis": "last", "adjust_source": "ledger"}


def run(c, asset=ASSET, c0=None, c7=None, dbrow=None, near=None):
    return T.classify_row(asset, c, ROW, c0, c7, dbrow, [], near or [])


def test_source_divergence():
    print("\n[1] source divergence")
    c0 = ("2020-01-01", 100.0, 105.0, 95.0, 101.0, 1000.0)
    res = run(PROD, c0=c0)
    ck(res and res[0] == "SOURCE_DATA_DIVERGENCE", "product matches type0", res)


def test_fallback():
    print("\n[2] local fallback")
    asset = {"basis": "last", "adjust_source": "local-db-fallback"}
    dbrow = ("2020-01-01", 99.0, 105.0, 95.0, 101.0, 1000.0, 101.0, "board")
    res = run(PROD, asset=asset, dbrow=dbrow)
    ck(res and res[0] == "FALLBACK_DB_SOURCE", "product equals local fallback row", res)


def test_field_mapping():
    print("\n[3] field mapping")
    c = ["2020-01-01", 99.0, 105.0, 95.0, 100.0, 100.0, 100.0, 105.0, 95.0, 1000.0, "last"]
    res = run(c)
    ck(res and res[0] == "FIELD_MAPPING", "open equals base <OPEN>", res)


def test_date_mapping():
    print("\n[4] date mapping")
    c = ["2020-01-01", 100.0, 105.0, 95.0, 100.0, 100.0, 100.0, 105.0, 95.0, 1000.0, "last"]
    near = [("2019-12-31", 100.0, 105.0, 95.0, 100.0, 1000.0, 99.0, 100.0)]
    # make official close differ so a bad field exists, then let the neighbour match it
    row = ("2020-01-01", 100.0, 105.0, 95.0, 101.0, 1000.0, 98.0, 99.0)
    res = T.classify_row(ASSET, c, row, None, None, None, [], near)
    ck(res and res[0] == "DATE_MAPPING", "official close matches adjacent date", res)


def test_no_mismatch():
    print("\n[5] healthy row")
    c = ["2020-01-01", 100.0, 105.0, 95.0, 101.0, 100.0, 101.0, 105.0, 95.0, 1000.0, "last"]
    res = run(c)
    ck(res is None, "matching row has no cause", res)


if __name__ == "__main__":
    test_source_divergence()
    test_fallback()
    test_field_mapping()
    test_date_mapping()
    test_no_mismatch()
    print("\n%d passed, %d failed" % (P, F))
    sys.exit(1 if F else 0)
