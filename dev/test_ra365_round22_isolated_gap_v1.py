#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 22: an isolated <1.5% downward base gap without an official row is noise.

Live evidence: Fenoval 2023-03-28 (0.988962) and Behran 2020-05-26 (0.990878)
are applied by the product but have no state in Rahavard type7.  A small gap
that belongs to a same-date combined event (Hejrat 2025-08-17) must survive.
"""
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


fd, path = tempfile.mkstemp(suffix=".db")
os.close(fd)
con = sqlite3.connect(path)
con.execute("CREATE TABLE instruments(ins_code TEXT, l_val18 TEXT, l_val30 TEXT,"
            " paper_type INTEGER, board TEXT, updated_at TEXT)")
con.execute("INSERT INTO instruments VALUES"
            " ('1','STOCK','Stock Corp',1,'board','2026-01-01')")
con.execute("INSERT INTO instruments VALUES"
            " ('2','FUND','Fund',8,'board','2026-01-01')")
con.execute("CREATE TABLE price_adjust_events (ins_code TEXT, d_even INTEGER,"
            " p_closing REAL, p_closing_not_adjusted REAL, ratio REAL)")
con.execute("INSERT INTO price_adjust_events VALUES ('1',20230605,900.0,950.0,0.94737)")
con.execute("CREATE TABLE share_change_events (ins_code TEXT, d_even INTEGER, ratio REAL)")
con.execute("CREATE TABLE session_anomalies (d_even INTEGER, cause TEXT)")
con.commit()
con.close()

saved = C.DB_PATH
C.DB_PATH = path
try:
    ev = [
        {"date": "2023-03-28", "ratio": 0.988962, "source": "base-price-discontinuity"},
        {"date": "2023-01-10", "ratio": 0.97, "source": "base-price-discontinuity"},
        {"date": "2023-06-01", "ratio": 0.99, "source": "base-price-discontinuity"},
        {"date": "2023-08-17", "ratio": 0.996471, "source": "base-price-discontinuity"},
        {"date": "2023-08-17", "ratio": 0.077744, "source": "base-price-discontinuity"},
        {"date": "2023-04-04", "ratio": 1.011161, "source": "base-price-discontinuity"},
        {"date": "2023-03-28", "ratio": 0.95, "source": "priceAdjust"},
    ]
    kept, rejected = C._filter_unproven_base_events("STOCK", ev)
    rej = {(r["date"], r["ratio"]): r["factor_status"] for r in rejected}
    keep = {(e["date"], e["ratio"]) for e in kept}
    ck(("2023-03-28", 0.988962) not in keep
       and rej.get(("2023-03-28", 0.988962)) == "unproven-small-base-gap",
       "isolated 1.1% unproven gap is rejected", rejected)
    ck(("2023-01-10", 0.97) in keep, "a >1.5% unproven gap is kept", kept)
    ck(("2023-08-17", 0.996471) in keep and ("2023-08-17", 0.077744) in keep,
       "a small component of a same-date combined event is kept", kept)
    ck(("2023-06-01", 0.99) in keep, "a small gap with an official row within 30 days is kept", kept)
    ck(("2023-04-04", 1.011161) in rej, "positive unproven gap keeps the existing rejection", rejected)
    ck(("2023-03-28", 0.95) in keep, "ledger rows are never filtered", kept)

    fund_ev = [{"date": "2023-03-28", "ratio": 0.99, "source": "base-price-discontinuity"}]
    fk, fr = C._filter_unproven_base_events("FUND", fund_ev)
    ck(len(fk) == 1 and not fr, "fund distributions are not dropped", (fk, fr))
finally:
    C.DB_PATH = saved
    try:
        os.unlink(path)
    except OSError:
        pass

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
