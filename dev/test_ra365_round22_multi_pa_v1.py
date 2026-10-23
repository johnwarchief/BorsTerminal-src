#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 22: the official feed may emit several priceAdjust rows on one date.

The legacy table's PK is (ins_code, d_even), so all but one were dropped.
`price_adjust_event_rows` keeps every row; the engine applies their product.
"""
import json
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import api.chart as C  # noqa: E402

P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   ← %s" % (detail,)) if detail else ""))


def make_db(rows_table):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE instruments(ins_code TEXT, l_val18 TEXT, l_val30 TEXT,"
                " paper_type INTEGER, board TEXT, updated_at TEXT)")
    con.execute("INSERT INTO instruments VALUES ('1','X','X Corp',1,'board','2026-01-01')")
    if rows_table:
        con.execute(
            "CREATE TABLE price_adjust_event_rows (ins_code TEXT, d_even INTEGER,"
            " symbol TEXT, p_closing REAL, p_closing_not_adjusted REAL,"
            " corporate_type_code INTEGER, ratio REAL, source TEXT, fetched_at TEXT,"
            " PRIMARY KEY (ins_code,d_even,p_closing,p_closing_not_adjusted))")
        con.executemany(
            "INSERT INTO price_adjust_event_rows VALUES (?,?,?,?,?,?,?,?,?)", [
                ("1", 20190603, "X", 7335.0, 11136.0, None, 0.65867457,
                 "tsetmc_price_adjust_by_flow", "t"),
                ("1", 20190603, "X", 9777.0, 7335.0, None, 1.33292434,
                 "tsetmc_price_adjust_by_flow", "t"),
                ("1", 20200721, "X", 91350.0, 94050.0, None, 0.97129187,
                 "tsetmc_price_adjust_by_flow", "t"),
            ])
    else:
        con.execute(
            "CREATE TABLE price_adjust_events (ins_code TEXT, d_even INTEGER, symbol TEXT,"
            " p_closing REAL, p_closing_not_adjusted REAL, corporate_type_code INTEGER,"
            " ratio REAL, source TEXT, fetched_at TEXT, PRIMARY KEY (ins_code,d_even))")
        con.execute("INSERT INTO price_adjust_events VALUES"
                    " ('1',20190603,'X',0.9,1.0,-1,0.9,'tsetmc_price_adjust_by_flow','t')")
    con.commit()
    con.close()
    return path


saved = C.DB_PATH
try:
    # 1) multi-row table: product of both rows, one combined event
    p1 = make_db(True)
    C.DB_PATH = p1
    ev = C._official_price_adjust_events("X", times=None, share_changes=[], closings={})
    combined = [e for e in ev if e.get("_event_type") == "combined"]
    ck(len(combined) == 1, "two same-date rows become one combined event", ev)
    ck(combined and abs(combined[0]["ratio"] - 0.65867457 * 1.33292434) < 1e-9,
       "combined ratio is the product of both official rows", combined)
    single = [e for e in ev if e.get("date") == "2020-07-21"]
    ck(single and abs(single[0]["ratio"] - 0.97129187) < 1e-9,
       "a single-row date keeps its official ratio", single)

    # 2) legacy marker row is used as a combined ratio, never re-derived as DPS
    p2 = make_db(False)
    C.DB_PATH = p2
    ev2 = C._official_price_adjust_events("X", times=None, share_changes=[], closings={})
    ck(ev2 and abs(ev2[0]["ratio"] - 0.9) < 1e-9 and ev2[0].get("_event_type") == "combined",
       "legacy combined marker keeps the stored ratio", ev2)
finally:
    C.DB_PATH = saved
    for p in (p1, p2):
        try:
            os.unlink(p)
        except OSError:
            pass

# 3) ingest parser keeps every row and writes a product into the legacy row
import importlib.util
spec = importlib.util.spec_from_file_location(
    "ing", os.path.join(ROOT, "tools", "corp_events_full_history_ingest.py"))
ING = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ING)
rows = [
    {"insCode": "1", "dEven": 20190603, "pClosing": 7335.0,
     "pClosingNotAdjusted": 11136.0, "instrument": {"insCode": "1"}},
    {"insCode": "1", "dEven": 20190603, "pClosing": 9777.0,
     "pClosingNotAdjusted": 7335.0, "instrument": {"insCode": "1"}},
    {"insCode": "1", "dEven": 20200721, "pClosing": 91350.0,
     "pClosingNotAdjusted": 94050.0, "instrument": {"insCode": "1"}},
]
all_rows, legacy = ING.parse_pa(rows, "t")
ck(len(all_rows) == 3, "parser keeps all three individual rows", len(all_rows))
ck(len(legacy) == 2, "parser writes one legacy row per date", len(legacy))
comb = [r for r in legacy if r[1] == 20190603][0]
ck(comb[5] == -1 and abs(comb[6] - 0.65867457 * 1.33292434) < 1e-9,
   "legacy row is marked and carries the product", comb)
one = [r for r in legacy if r[1] == 20200721][0]
ck(abs(one[3] - 91350.0) < 1e-9 and abs(one[6] - 0.97129187) < 1e-9,
   "single-row legacy row keeps p/pn", one)

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
