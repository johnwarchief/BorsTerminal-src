#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 18: general price_history repair uses the published CSV contract.

Pins the three invariants that make the fallback repair safe:
  * open comes from FIRST (not the base <OPEN> column),
  * published rows outrank board/NULL rows,
  * a re-run is keyed and changes no logical value.
"""
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import candle_contract as CC  # noqa: E402

P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   ← %s" % (detail,)) if detail else ""))


HEAD = "<TICKER>,<DTYYYYMMDD>,<FIRST>,<HIGH>,<LOW>,<CLOSE>,<VALUE>,<VOL>,<OPENINT>,<PER>,<OPEN>,<LAST>\r\n"
VALID = "19900101,20200101,100.00,110.00,90.00,105.00,1000,500,1,D,95.00,108.00\r\n"
NO_TRADE = "19900101,20200102,0.00,0.00,0.00,104.00,0,0,0,D,105.00,0.00\r\n"


def make_db():
    con = sqlite3.connect(":memory:")
    con.execute("""CREATE TABLE price_history(
        symbol TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL,
        volume REAL, last REAL, value REAL, src TEXT, PRIMARY KEY(symbol,date))""")
    con.execute("INSERT INTO price_history VALUES(?,?,?,?,?,?,?,?,?,?)",
                ("X", "2020-01-01", 95.0, 100.0, 90.0, 100.0, 400.0, None, 900.0, "board"))
    return con


def test_published_contract():
    print("\n[1] published CSV row")
    f = VALID.strip().split(",")
    bar = CC.from_csv_row("X", f)
    ck(bar is not None, "row parses")
    ck(bar["open"] == 100.0, "open is FIRST", bar)
    ck(bar["close"] == 105.0, "close is official CLOSE", bar)
    ck(bar["last"] == 108.0, "last is LAST", bar)
    ck(bar["volume"] == 500.0, "volume is VOL", bar)
    ck(bar["src"] == CC.SRC_PUBLISHED, "src is published", bar)
    ck(CC.from_csv_row("X", NO_TRADE.strip().split(",")) is None,
       "no-trade row never becomes a candle")


def test_priority_and_idempotency():
    print("\n[2] priority and idempotency")
    con = make_db()
    f = VALID.strip().split(",")
    bar = CC.from_csv_row("X", f)
    con.execute(CC.UPSERT_SQL, CC.upsert_row(bar))
    row = con.execute("SELECT open,last,src FROM price_history WHERE symbol='X' "
                      "AND date='2020-01-01'").fetchone()
    ck(row == (100.0, 108.0, "published"), "board row replaced by published", row)
    # a later board write must not clobber a published row
    con.execute(CC.UPSERT_SQL, CC.upsert_row(dict(bar, open=99.0, src=CC.SRC_BOARD)))
    row2 = con.execute("SELECT open,src FROM price_history WHERE symbol='X' "
                       "AND date='2020-01-01'").fetchone()
    ck(row2 == (100.0, "published"), "board cannot overwrite published", row2)
    # re-run the same published row: one row, same values
    con.execute(CC.UPSERT_SQL, CC.upsert_row(bar))
    n, o, l, s = con.execute("SELECT COUNT(*),MIN(open),MIN(last),MIN(src) "
                             "FROM price_history").fetchone()
    ck(n == 1 and o == 100.0 and l == 108.0 and s == "published",
       "second upsert is keyed, no duplicate", (n, o, l, s))
    con.close()


def test_db_row_roundtrip():
    print("\n[3] price_history -> candle")
    candle = CC.from_db_row(("X", "2020-01-01", 100.0, 110.0, 90.0, 105.0,
                             500.0, 108.0, 1000.0, "published"))
    ck(candle["open"] == 100.0 and candle["close"] == 105.0, "db row keeps open/close", candle)
    ck(candle["last"] == 108.0, "db row keeps last", candle)
    ck(candle["high"] == 110.0 and candle["low"] == 90.0, "geometry stays valid", candle)
    ck(CC.from_db_row(("X", "2020-01-02", 0, 0, 0, 0, 0, None, 0, "board")) is None,
       "zero-volume legacy row is not a candle")


if __name__ == "__main__":
    test_published_contract()
    test_priority_and_idempotency()
    test_db_row_roundtrip()
    print("\n%d passed, %d failed" % (P, F))
    sys.exit(1 if F else 0)
