#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 32H: the chart prefers the announced assembly DPS with the official close.

The measured source (R32H) is `DividendPerShare` on Codal's Decision.aspx, not
the exchange PA ledger's `pna - pcl`.  This test pins the wiring on an isolated
DB: the Codal row wins when present, the old PA-D path stays byte-identical
when the row/table/flag is absent, and a row from another year never attaches.
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


def make_db(with_table=True, codal_rows=((20230605, 150.0),), pa_dps=60.0,
            codal_ref=1000.0):
    """Isolated DB: one stock instrument, one PA row, one official close."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE instruments(ins_code TEXT, l_val18 TEXT, l_val30 TEXT,"
                " paper_type INTEGER, board TEXT, updated_at TEXT)")
    con.execute("INSERT INTO instruments VALUES"
                " ('1','TEST','Test Corp',1,'board','2026-01-01')")
    con.execute("CREATE TABLE price_adjust_event_rows (ins_code TEXT, d_even INTEGER,"
                " ratio REAL, source TEXT, p_closing REAL, p_closing_not_adjusted REAL)")
    con.execute("INSERT INTO price_adjust_event_rows VALUES"
                " ('1',20230605,0.94,'tsetmc',?,?)", (1000.0 - pa_dps, 1000.0))
    con.execute("CREATE TABLE price_history(symbol TEXT, date TEXT, close REAL)")
    con.execute("INSERT INTO price_history VALUES ('TEST','2023-06-05',1000.0)")
    if with_table:
        con.execute("CREATE TABLE stock_dividend_events (ins_code TEXT, d_even INTEGER,"
                    " symbol TEXT, dps REAL, reference_price REAL, ratio REAL,"
                    " publish_date TEXT, source TEXT, source_id TEXT, fetched_at TEXT)")
        for d, dps in codal_rows:
            con.execute("INSERT INTO stock_dividend_events VALUES"
                        " ('1',?,'TEST',?,?,?,NULL,'codal-assembly','x',NULL)",
                        (d, dps, codal_ref, codal_ref / (codal_ref + dps)))
    con.commit()
    con.close()
    return path


TIMES = ["2023-06-05", "2023-06-06"]
CLOSINGS = {"2023-06-05": 1000.0, "2023-06-06": 1010.0}


def run(path, closings=None):
    saved = C.DB_PATH
    C.DB_PATH = path
    try:
        return C._official_price_adjust_events(
            "TEST", TIMES, share_changes=[], closings=closings or CLOSINGS)
    finally:
        C.DB_PATH = saved


def only(evs):
    return evs[0] if len(evs) == 1 else None


# 1) Codal DPS wins over the PA ledger's pna-pcl (150 vs 60).
p = make_db()
try:
    e = only(run(p))
    ck(e is not None, "۱ یک رویدادِ PA ساخته می‌شود", e)
    if e:
        ck(abs(e["ratio"] - 1000.0 / 1150.0) <= 1e-9,
           "۲ نسبت = close/(close+DPSِ اعلامی)، نه PA-D", e["ratio"])
        ck(e.get("dividend_per_share") == 150.0,
           "۳ dividend_per_share همان DPSِ اعلامی است", e.get("dividend_per_share"))
        ck(e.get("_dps_source") == "codal", "۴ منبعِ D ثبت شده", e.get("_dps_source"))
finally:
    os.unlink(p)

# 1b) The stored official close wins over the chart candle's close.
# Measured on real data (معين 2025-06-01): candle 2655 vs official 2344.
p = make_db(codal_ref=1000.0)
try:
    e = only(run(p, closings={"2023-06-05": 1200.0, "2023-06-06": 1210.0}))
    if e:
        ck(abs(e["ratio"] - 1000.0 / 1150.0) <= 1e-9,
           "۱ب پایانیِ رسمیِ ذخیره‌شده بر پایانیِ کندل مقدم است", e["ratio"])
finally:
    os.unlink(p)

# 2) No table at all -> the previous PA-D path exactly (no crash).
p = make_db(with_table=False)
try:
    e = only(run(p))
    if e:
        ck(abs(e["ratio"] - 1000.0 / 1060.0) <= 1e-9,
           "۵ بی‌جدول: نسبتِ قبلیِ PA-D دست‌نخورده", e["ratio"])
        ck(e.get("dividend_per_share") == 60.0, "۶ بی‌جدول: D = pna-pcl", e.get("dividend_per_share"))
        ck(e.get("_dps_source") == "priceAdjust", "۷ بی‌جدول: منبع PA", e.get("_dps_source"))
finally:
    os.unlink(p)

# 3) Empty table -> same PA-D path.
p = make_db(codal_rows=())
try:
    e = only(run(p))
    if e:
        ck(abs(e["ratio"] - 1000.0 / 1060.0) <= 1e-9,
           "۸ جدولِ خالی: مسیرِ قبلی", e["ratio"])
finally:
    os.unlink(p)

# 4) A row from another year (65 days away) never attaches.
p = make_db(codal_rows=((20230401, 150.0),))
try:
    e = only(run(p))
    if e:
        ck(abs(e["ratio"] - 1000.0 / 1060.0) <= 1e-9,
           "۹ ردیفِ ۶۵ روزِ دور به این رویداد نسبت داده نمی‌شود", e["ratio"])
finally:
    os.unlink(p)

# 5) A row five days earlier (same event, off-by-days) is accepted.
p = make_db(codal_rows=((20230531, 150.0),))
try:
    e = only(run(p))
    if e:
        ck(abs(e["ratio"] - 1000.0 / 1150.0) <= 1e-9,
           "۱۰ ردیفِ ۵ روزِ نزدیک همان رویداد است", e["ratio"])
finally:
    os.unlink(p)

# 6) Rollback flag: BORS_CODAL_DPS=0 restores the PA-D path.
p = make_db()
saved_flag = os.environ.get("BORS_CODAL_DPS")
try:
    os.environ["BORS_CODAL_DPS"] = "0"
    e = only(run(p))
    if e:
        ck(abs(e["ratio"] - 1000.0 / 1060.0) <= 1e-9,
           "۱۱ فلگِ خاموش: مسیرِ PA-D برمی‌گردد", e["ratio"])
        ck(e.get("_dps_source") == "priceAdjust", "۱۲ فلگِ خاموش: منبع PA", e.get("_dps_source"))
finally:
    if saved_flag is None:
        os.environ.pop("BORS_CODAL_DPS", None)
    else:
        os.environ["BORS_CODAL_DPS"] = saved_flag
    os.unlink(p)

# 7) Junk rows (zero/negative/non-numeric) are ignored, not applied.
p = make_db(codal_rows=((20230605, 0.0), (20230606, -5.0)))
try:
    e = only(run(p))
    if e:
        ck(abs(e["ratio"] - 1000.0 / 1060.0) <= 1e-9,
           "۱۳ DPSِ صفر/منفی جای Dِ درست نمی‌نشیند", e["ratio"])
finally:
    os.unlink(p)

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
