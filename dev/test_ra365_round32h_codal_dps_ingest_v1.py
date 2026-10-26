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
        ("5", "EEE", "شرکت ه", 1),          # PA day has no candle; next candle does
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
    con.execute("INSERT INTO price_adjust_event_rows VALUES"
                " ('5',20230610,0.98399,'tsetmc',11860.0,12053.0)")
    con.execute("INSERT INTO price_history VALUES ('AAA','2023-06-05',1000.0)")
    con.execute("INSERT INTO price_history VALUES ('EEE','2023-06-12',14000.0)")
    con.commit()
    return con, path


con, path = make_db()
try:
    cand = ING.select_candidates(con)
    syms = [(s, d) for _i, s, d, _p in cand]
    ck(syms == [("EEE", 20230610), ("DDD", 20230606), ("AAA", 20230605)],
       "۱ فقط سهامِ بی‌ردیف، جدید به قدیم", syms)

    calls = []

    def ok_finder(symbol, eff_date):
        calls.append(symbol)
        return {"status": "OK", "dps": 150.0, "notice_id": "N-1",
                "publish_date": "1402/03/10", "requests": 2}

    res = ING.ingest(con, cand, ok_finder, budget=20)
    ck(res["ok"] == 3 and res["requests"] == 6, "۲ سه ردیف نوشته شد", res)
    row = con.execute("SELECT dps, reference_price, ratio, source_id"
                      " FROM stock_dividend_events WHERE ins_code='1'").fetchone()
    ck(row is not None and row[0] == 150.0, "۳ DPSِ اعلامی ذخیره شد", row)
    ck(row and abs(row[2] - 1000.0 / 1150.0) <= 1e-12,
       "۴ نسبت = close/(close+dps)", row)
    ck(row and row[3] == "N-1", "۵ شناسهٔ اطلاعیه ثبت شد", row)
    # EEE: the PA day has no candle; the reference close is the next candle's
    # (14000), not the PA row's p_closing (11860) — same mapping as the chart.
    row5 = con.execute("SELECT reference_price, ratio FROM stock_dividend_events"
                       " WHERE ins_code='5'").fetchone()
    ck(row5 is not None and row5[0] == 14000.0,
       "۶ روزِ بی‌کندل: پایانیِ اولین کندلِ بعد مبنا است", row5)
    ck(row5 and abs(row5[1] - 14000.0 / 14150.0) <= 1e-12,
       "۷ نسبتِ نگاشت‌شده هم از فرمول است", row5)
    # DDD has no price_history row at all -> p_closing fallback (950).
    row4 = con.execute("SELECT reference_price, ratio FROM stock_dividend_events"
                       " WHERE ins_code='4'").fetchone()
    ck(row4 is not None and row4[0] == 950.0, "۸ بی price_history: p_closingِ PA مبنا", row4)
    ck(row4 and abs(row4[1] - 950.0 / 1100.0) <= 1e-12,
       "۹ نسبتِ fallback هم از فرمول است", row4)

    ck(ING.select_candidates(con) == [], "۱۰ اجرایِ دوم: resume، هیچ کاندیدِ تکراری")
    calls.clear()
    ING.ingest(con, [], ok_finder, budget=20)
    ck(not calls, "۱۱ برایِ ردیفِ موجود هیچ درخواستی زده نمی‌شود")

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
    ck(res["ok"] == 2 and res["no_dps"] == 1, "۱۲ بی‌DPS نوشته نمی‌شود، ادامه می‌دهد", res)
    ck(con.execute("SELECT COUNT(*) FROM stock_dividend_events").fetchone()[0] == 2,
       "۱۳ فقط ردیف‌هایِ اثبات‌شده در جدول است")

    # BLOCKED stops immediately and leaves later candidates untouched.
    con.execute("DELETE FROM stock_dividend_events")
    con.commit()
    cand = ING.select_candidates(con)
    seen = []

    def blocked_finder(symbol, eff_date):
        seen.append(symbol)
        return {"status": "BLOCKED", "requests": 1}

    res = ING.ingest(con, cand, blocked_finder, budget=20)
    ck(res["blocked"] == 1 and len(seen) == 1, "۱۴ ۴۲۹: توقفِ فوری", (res, seen))
    ck(con.execute("SELECT COUNT(*) FROM stock_dividend_events").fetchone()[0] == 0,
       "۱۵ ۴۲۹: هیچ ردیفِ نیمه‌کاره")

    # Budget is hard: zero network calls, nothing written.
    res = ING.ingest(con, cand, ok_finder, budget=0)
    ck(res["requests"] == 0 and res["skipped"] == len(cand), "۱۶ بودجهٔ صفر: هیچ درخواست", res)

    # Explicit pairs target the exact event even without p_closing.
    con.execute("DELETE FROM stock_dividend_events")
    con.commit()
    pc = ING.select_candidates(con, pairs=[["AAA", 20230605]])
    ck([(s, d) for _i, s, d, _p in pc] == [("AAA", 20230605)],
       "۱۷ pairs اجرایِ هدف‌دار", pc)

    # Local Codal notices: only a Decision.aspx with an assembly/dividend title
    # and an assembly date inside [eff-150d, eff] is a candidate.
    con.execute("CREATE TABLE codal_notices(tracing_no TEXT, symbol TEXT,"
                " title TEXT, publish_date TEXT, url TEXT)")
    con.executemany("INSERT INTO codal_notices VALUES (?,?,?,?,?)", [
        ("N1", "AAA", "تصمیمات مجمع عمومی عادی سالیانه", "1402/03/10 10:00:00",
         "https://codal.ir/Reports/Decision.aspx?LetterSerial=A"),
        ("N2", "AAA", "تصمیمات مجمع عمومی عادی سالیانه", "1402/03/12 10:00:00",
         "https://codal.ir/Reports/Attachment.aspx?LetterSerial=B"),
        ("N3", "AAA", "تصمیمات مجمع", "1401/01/01 10:00:00",
         "https://codal.ir/Reports/Decision.aspx?LetterSerial=C"),
        ("N4", "AAA", "اطلاعیه دیگر", "1402/03/11 10:00:00",
         "https://codal.ir/Reports/Decision.aspx?LetterSerial=D"),
    ])
    con.commit()
    loc = ING.local_decision_urls(con, "AAA", "2023-06-05")
    ck([x[0] for x in loc] == ["N1"], "۱۸ فقط اطلاعیهٔ مجمعِ در پنجره", loc)
    ck(ING.local_decision_urls(con, "NOPE", "2023-06-05") == [],
       "۱۹ نمادِ بی‌اطلاعیه → لیستِ تهی")

    # The finder tries the local notice first and never calls the search API.
    PAGE = ("<td>DividendPerShare</td><td>سود نقدی هر سهم (ریال)</td><td>۸۵۱</td>")

    class Resp:
        text = PAGE

    class Sess:
        def __init__(self):
            self.calls = []

        def get(self, url, **kw):
            self.calls.append(url)
            return Resp()

    search_calls = []

    def fake_fetch(*a, **k):
        search_calls.append(1)
        return []

    saved_fetch = ING.CF.fetch_page
    try:
        ING.CF.fetch_page = fake_fetch
        sess = Sess()
        f = ING.make_live_finder(
            sess, page_pause=0,
            local_lookup=lambda s, e: [("N1", "http://x", "1402/03/10")])
        r = f("AAA", "2023-06-05")
        ck(r.get("status") == "OK" and r.get("dps") == 851.0
           and r.get("via") == "local-notices",
           "۲۰ local-first: DPS از اطلاعیهٔ محلی", r)
        ck(not search_calls, "۲۱ local-first: جستجویِ API صدا زده نشد", search_calls)
        # No local notice -> the search path is used.
        search_calls.clear()
        ING.CF.fetch_page = lambda *a, **k: (
            search_calls.append(1) or
            [{"Url": "/Reports/Decision.aspx?LetterSerial=Z",
              "Title": "تصمیمات مجمع عمومی عادی سالیانه",
              "PublishDateTime": "1402/03/10 10:00:00", "TracingNo": "S1"}])
        f2 = ING.make_live_finder(sess, page_pause=0, local_lookup=lambda s, e: [])
        r2 = f2("AAA", "2023-06-05")
        ck(r2.get("status") == "OK" and r2.get("via") == "search" and search_calls,
           "۲۲ بی‌اطلاعیهٔ محلی: مسیرِ جستجو", r2)
        # Search blocked -> BLOCKED, no fake success.
        ING.CF.fetch_page = lambda *a, **k: None
        f3 = ING.make_live_finder(sess, page_pause=0)
        r3 = f3("AAA", "2023-06-05")
        ck(r3.get("status") == "BLOCKED", "۲۳ ۴۲۹ در جستجو: BLOCKED", r3)
    finally:
        ING.CF.fetch_page = saved_fetch
finally:
    con.close()
    os.unlink(path)

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
