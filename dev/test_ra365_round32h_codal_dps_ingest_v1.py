#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 32H: the ingest writes only proven rows, resumes, and respects the budget.

No network: the finder is injected.  The temp DB mirrors the real schema
(tsetmc_p0_schema) plus one stock, one fund, and one right instrument.
"""
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import dev.codal_dividend_ingest as ING  # noqa: E402
import tsetmc_p0_schema as SCHEMA        # noqa: E402

P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   ← %s" % (detail,)) if detail else ""))


def make_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    con = sqlite3.connect(path)
    SCHEMA.create_all(con)
    con.execute("CREATE TABLE instruments(ins_code TEXT, l_val18 TEXT, l_val30 TEXT,"
                " paper_type INTEGER, board TEXT, updated_at TEXT)")
    con.execute("CREATE TABLE price_history(symbol TEXT, date TEXT, close REAL)")
    rows = [
        ("1", "AAA", "شرکت آ", 1),
        ("2", "BBB", "شرکت ب", 8),          # fund: never a stock-dividend candidate
        ("3", "CCCH", "حق تقدم ج", 2),      # right: excluded by name
        ("4", "DDD", "شرکت د", 1),
    ]
    for r in rows:
        con.execute("INSERT INTO instruments VALUES (?,?,?,?, 'board','2026-01-01')", r)
    con.execute("CREATE TABLE price_adjust_event_rows(ins_code TEXT, d_even INTEGER,"
                " ratio REAL, source TEXT, p_closing REAL,"
                " p_closing_not_adjusted REAL)")
    con.execute("INSERT INTO price_adjust_event_rows VALUES"
                " ('1',20230605,0.94,'tsetmc',940.0,1000.0)")
    con.execute("INSERT INTO price_adjust_event_rows VALUES"
                " ('2',20230605,0.95,'tsetmc',950.0,1000.0)")
    con.execute("INSERT INTO price_adjust_event_rows VALUES"
                " ('3',20230605,0.95,'tsetmc',950.0,1000.0)")
    con.execute("INSERT INTO price_adjust_event_rows VALUES"
                " ('4',20230606,0.95,'tsetmc',950.0,1000.0)")
    con.execute("INSERT INTO price_history VALUES ('AAA','2023-06-05',1000.0)")
    con.commit()
    return con, path


con, path = make_db()
try:
    cand = ING.select_candidates(con)
    syms = [(s, d) for _i, s, d, _p in cand]
    ck(syms == [("DDD", 20230606), ("AAA", 20230605)],
       "۱ فقط سهامِ بی‌ردیف، جدید به قدیم", syms)

    calls = []

    def ok_finder(symbol, eff_date):
        calls.append(symbol)
        return {"status": "OK", "dps": 150.0, "notice_id": "N-1",
                "publish_date": "1402/03/10", "requests": 2}

    res = ING.ingest(con, cand, ok_finder, budget=20)
    ck(res["ok"] == 2 and res["requests"] == 4, "۲ دو ردیف نوشته شد", res)
    row = con.execute("SELECT dps, reference_price, ratio, source_id"
                      " FROM stock_dividend_events WHERE ins_code='1'").fetchone()
    ck(row is not None and row[0] == 150.0, "۳ DPSِ اعلامی ذخیره شد", row)
    ck(row and abs(row[2] - 1000.0 / 1150.0) <= 1e-12,
       "۴ نسبت = close/(close+dps)", row)
    ck(row and row[3] == "N-1", "۵ شناسهٔ اطلاعیه ثبت شد", row)
    # DDD has no price_history row -> p_closing fallback (950), not skipped.
    row4 = con.execute("SELECT reference_price, ratio FROM stock_dividend_events"
                       " WHERE ins_code='4'").fetchone()
    ck(row4 is not None and row4[0] == 950.0, "۶ بی price_history: p_closingِ PA مبنا", row4)
    ck(row4 and abs(row4[1] - 950.0 / 1100.0) <= 1e-12,
       "۷ نسبتِ fallback هم از فرمول است", row4)

    ck(ING.select_candidates(con) == [], "۸ اجرایِ دوم: resume، هیچ کاندیدِ تکراری")
    calls.clear()
    ING.ingest(con, [], ok_finder, budget=20)
    ck(not calls, "۹ برایِ ردیفِ موجود هیچ درخواستی زده نمی‌شود")

    # NO_DPS rows are not written and do not block later rows.
    con.execute("DELETE FROM stock_dividend_events")
    con.commit()
    cand = ING.select_candidates(con)
    seen = []

    def mixed_finder(symbol, eff_date):
        seen.append(symbol)
        if symbol == "DDD":
            return {"status": "NO_DPS", "requests": 2}
        return {"status": "OK", "dps": 100.0, "notice_id": "N-2", "requests": 2}

    res = ING.ingest(con, cand, mixed_finder, budget=20)
    ck(res["ok"] == 1 and res["no_dps"] == 1, "۱۰ بی‌DPS نوشته نمی‌شود، ادامه می‌دهد", res)
    ck(con.execute("SELECT COUNT(*) FROM stock_dividend_events").fetchone()[0] == 1,
       "۱۱ فقط ردیفِ اثبات‌شده در جدول است")

    # BLOCKED stops immediately and leaves later candidates untouched.
    con.execute("DELETE FROM stock_dividend_events")
    con.commit()
    cand = ING.select_candidates(con)
    seen = []

    def blocked_finder(symbol, eff_date):
        seen.append(symbol)
        return {"status": "BLOCKED", "requests": 1}

    res = ING.ingest(con, cand, blocked_finder, budget=20)
    ck(res["blocked"] == 1 and len(seen) == 1, "۱۲ ۴۲۹: توقفِ فوری", (res, seen))
    ck(con.execute("SELECT COUNT(*) FROM stock_dividend_events").fetchone()[0] == 0,
       "۱۳ ۴۲۹: هیچ ردیفِ نیمه‌کاره")

    # Budget is hard: zero network calls, nothing written.
    res = ING.ingest(con, cand, ok_finder, budget=0)
    ck(res["requests"] == 0 and res["skipped"] == len(cand), "۱۴ بودجهٔ صفر: هیچ درخواست", res)

    # Explicit pairs target the exact event even without p_closing.
    con.execute("DELETE FROM stock_dividend_events")
    con.commit()
    pc = ING.select_candidates(con, pairs=[["AAA", 20230605]])
    ck([(s, d) for _i, s, d, _p in pc] == [("AAA", 20230605)],
       "۱۵ pairs اجرایِ هدف‌دار", pc)
finally:
    con.close()
    os.unlink(path)

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
