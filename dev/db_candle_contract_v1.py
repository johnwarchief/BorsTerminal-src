#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/db_candle_contract_v1.py — مسیرِ بانکِ کندل هم از قراردادِ مشترک می‌گذرد

چرا این گارد نوشته شد (دورِ ممیزیِ کلِ نمادها، ۱۴۰-۰۷-۲۷). ممیزیِ ۵٬۹۸۱ نمادیِ مسیرِ CDN
را با صفرِ نقضِ هندسه بست؛ اما `/api/chart-db` ردیف‌هایِ `price_history` را **دستی**
می‌ساخت و هیچ فیلتری نداشت. سنجشِ `_audit/db_row_contract_impact.py` رویِ کلِ بانک:

  • ۲٬۶۹۲ ردیفِ حجم‌صفر (روزِ بی‌معامله) که درِ CDN کندل نمی‌شوند، اینجا کندل می‌شدند؛
  • ۳۰۶ ردیفِ `open=high=low=0` با پایانیِ معتبر (۲۹۴ ردیفش High/Low صفر) ⇒ کندلِ
    ناممکن: `Low ≤ min(O,C)` نقض، و دامانۀِ خودکارِ محور تا صفر باز می‌شد؛
  • ۴۴ نماد از این تغییر متأثرند.

قاعدهٔ اصلاح همان `candle_contract.from_db_row` است (نه ساختارِ دوم): صفر درِ سایه یعنی
«منبع پر نکرده» ⇒ گِشاد از بدنه، و open از پایانیِ **منتشرشده** برمی‌دارد. هیچ عددِ
منتشرشده‌ای کُنده نمی‌شود و هیچ ردیفی بی‌علت حذف نمی‌شود (شمارش‌ها درِ پاسخ‌اند).

کنترلِ بی‌معنا-سبز هم اجرا می‌شود: اگر سازندۀِ قدیمی دوباره واردِ همین مسیر شود،
آزمون باید قرمز شود.
اجرا:  python dev/db_candle_contract_v1.py
"""
import io
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

sys.path.insert(0, os.path.join(ROOT, "dev"))
import basis_sandbox                  # noqa: E402  (جعبهٔ موقتِ price_basis.json)
import candle_contract as CC          # noqa: E402
import price_basis as PB              # noqa: E402

PASS = FAIL = 0

SYM = "آزمون۱"
# (symbol,date,open,high,low,close,volume,last,value,src)
ROWS = [
    # ردیفِ سالم
    (SYM, "2026-01-03", 1000.0, 1060.0, 980.0, 1040.0, 1e9, 1035.0, 5e12, "published"),
    # همان شکلِ ۲۹۴ ردیفِ بانک: سایه/بدن صفر، پایانیِ معتبر، حجمِ مثبت
    (SYM, "2026-01-04", 0.0, 0.0, 0.0, 1200.0, 2e6, None, None, None),
    # روزِ بی‌معامله: حجم صفر ⇒ کندل نمی‌شود (درِ CDN هم همین)
    (SYM, "2026-01-05", 1300.0, 1300.0, 1300.0, 1300.0, 0.0, None, None, None),
    # پایانیِ صفر ⇒ بی‌عددِ معتبر، حذف
    (SYM, "2026-01-06", 1100.0, 1100.0, 1100.0, 0.0, 3e6, None, None, None),
    # تکراریِ همان روز با حجمِ کمتر ⇒ پرحجم‌تر می‌ماند
    (SYM, "2026-01-03", 900.0, 900.0, 900.0, 900.0, 1.0, None, None, None),
    # سایۀ ناقص از خودِ منبع (H < C) ⇒ گِشاد، بی‌کُندنِ پایانی
    (SYM, "2026-01-07", 1500.0, 1400.0, 1600.0, 1550.0, 4e6, 1560.0, 1e10, "published"),
]


def ck(ok, what, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  ok   " + what)
    else:
        FAIL += 1
        print(f"  FAIL {what}" + (f"  ← {detail}" if detail else ""))


def new_db(rows=ROWS):
    fd, p = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    con = sqlite3.connect(p)
    # درِ بانکِ واقعی `PRIMARY KEY (symbol, date)` هست و سنجش صفرِ تکراری نشان می‌دهد؛
    # این جا purposely بی‌PK ساخته می‌شود تا شاخۀ «حذفِ تکراریِ روز» (نمادِ دو-نوشتار
    # درِ یکِ تاریخ) سنجیده شود، نه اینکه بی‌آزمون بماند.
    con.execute("CREATE TABLE price_history (symbol TEXT, date TEXT, open REAL, high REAL,"
                " low REAL, close REAL, volume REAL, last REAL, value REAL, src TEXT)")
    con.execute("CREATE TABLE instruments (ins_code TEXT, l_val18 TEXT, l_val30 TEXT)")
    con.execute("CREATE TABLE market_watch (ins_code TEXT, d_even INTEGER, price_first REAL,"
                " price_max REAL, price_min REAL, p_closing REAL, q_tot_tran REAL, p_last REAL)")
    con.execute("CREATE TABLE adjust_events (symbol TEXT, date TEXT, ratio REAL,"
                " source TEXT, discovered_at TEXT)")
    con.executemany("INSERT INTO price_history VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    con.execute("INSERT OR REPLACE INTO instruments VALUES ('IC1', ?, ?)", (SYM, SYM))
    con.commit()
    con.close()
    return p


def old_builder(rows):
    """سازندۀِ پیش ازِ اصلاح (کنترلِ بی‌معنا-سبز): بدونِ فیلتر، بدونِ هندسه"""
    return [{"time": r[1], "open": float(r[2]), "high": float(r[3]), "low": float(r[4]),
             "close": float(r[5]), "last": float(r[7]) if r[7] is not None else None,
             "value": float(r[8]) if r[8] is not None else None,
             "volume": float(r[6] or 0)} for r in rows]


def geometry_ok(c):
    o, h, l, cl = c["open"], c["high"], c["low"], c["close"]
    return (l <= min(o, cl) + 1e-9 and h >= max(o, cl) - 1e-9 and l <= h
            and all(isinstance(v, float) and v == v and v not in (float("inf"), -float("inf"))
                    for v in (o, h, l, cl)) and h > 0 and l > 0 and o > 0 and cl > 0)


def main():
    print("\n[۱] مسیرِ بانک از قراردادِ مشترک")
    src = io.open(os.path.join(ROOT, "api", "chart.py"), encoding="utf-8").read()
    i0 = src.index("def get_chart_db")
    body = src[i0:src.index("def get_patterns")]
    ck("candle_contract.from_db_row(" in body,
       "سازندۀِ کندلِ بانک همان `from_db_row` است، نه حلقۀِ دستی", "")
    ck("candle_contract.SELECT_SQL" in body,
       "ستون‌ها از خودِ قرارداد خوانده می‌شوند (DB_COLUMNS)، نه فهرستِ دستی", "")
    ck('"open": float(r[1])' not in body,
       "ساختارِ دستیِ قدیم (بدونِ فیلتر و بدونِ هندسه) برگنگردد", "")
    ck('"dbRows"' in body and '"dbNoTradeRows"' in body and '"dbInvalidRows"' in body,
       "شمارشِ ردیف/حذف با علت درِ پاسخ اعلام می‌شود (بی‌حذفِ خاموش)", "")

    print("\n[۲] کنترلِ بی‌معنا-سبز: سازندۀِ قدیمی همین داده را می‌شکند")
    bad = [c for c in old_builder(ROWS) if not geometry_ok(c)]
    ck(len(bad) >= 2,
       "اگر قراردادِ مشترک برداشته شود، آزمون قرمز می‌شود (قدیم: %d کندلِ ناممکن)" % len(bad), "")

    print("\n[۳] شکلِ واقعیِ بانک: کلیدِ (symbol,date) و صفرِ تکراری")
    rcon = sqlite3.connect(os.path.join(ROOT, "market.db"))
    try:
        ddl = rcon.execute("select sql from sqlite_master where name='price_history'").fetchone()[0]
        n_dup = rcon.execute("select count(*) from (select symbol, date, count(*) n "
                             "from price_history group by 1,2 having n>1)").fetchone()[0]
        ck("PRIMARY KEY (symbol, date)" in " ".join((ddl or "").split()),
           "بانکِ واقعی کلیدِ (symbol,date) دارد ⇒ هرِ ردیفِ همان روز یکتاست",
           " ".join((ddl or "").split())[-70:])
        ck(n_dup == 0,
           "صفرِ روزِ تکراری درِ بانکِ واقعی ⇒ حذفِ تکراریِ درِ endpoint دفاعی است",
           "dup=%s" % n_dup)
    finally:
        rcon.close()

    print("\n[۴] پاسخِ زندهٔ endpoint رویِ بانکِ موقت")
    # این سوئیت set_basis می‌زند؛ بی‌جعبهٔ موقت، فایلِ تنظیمِ واقعیِ محصول رویِ
    # آخرینِ مقدار می‌ماند و نگهبانِ گیت (`dev/basis_guard.py`) درست همین را قرمز
    # می‌کند — همان نقصی که دورِ پیش درِ دو سوئیتِ دیگر بسته شد.
    basis_sandbox.use_sandboxed_basis("db_candle_contract_v1")
    dbp = new_db()
    import api._core as CORE
    import api.chart as CH
    import test_tsetmc
    keep = (CH.DB_PATH, CORE.DB_PATH, test_tsetmc.DB_PATH, PB.current())
    CH.DB_PATH = CORE.DB_PATH = test_tsetmc.DB_PATH = dbp
    try:
        PB.set_basis("last")
        r = CH.get_chart_db(SYM)
        ck(r.get("status") == "success", "پاسخ موفق است", str(r)[:120])
        cs = r.get("candles") or []
        by = {c["time"]: c for c in cs}
        ck(r.get("dbRows") == 5, "پس ازِ حذفِ تکراریِ روز، ۵ ردیف خوانده شد",
           "dbRows=%s" % r.get("dbRows"))
        ck(r.get("dbNoTradeRows") == 1,
           "یکِ ردیفِ حجم‌صفر با علت «روزِ بی‌معامله» رد شد",
           "dbNoTradeRows=%s" % r.get("dbNoTradeRows"))
        ck(r.get("dbInvalidRows") == 1,
           "یکِ ردیفِ بی‌پایانیِ معتبر با علتِ دیگر رد شد",
           "dbInvalidRows=%s" % r.get("dbInvalidRows"))
        ck(len(cs) == 3 and r.get("count") == 3,
           "خروجی = ۳ کندل (ورودی ۵ − ۱ بی‌معامله − ۱ بی‌پایانی)",
           "count=%s len=%s" % (r.get("count"), len(cs)))
        ck(all(geometry_ok(c) for c in cs),
           "هیچ کندلی هندسه را نقض نمی‌کند (Low≤min(O,C)≤max(O,C)≤High، بی‌صفر و بی‌NaN)",
           str([c for c in cs if not geometry_ok(c)])[:200])
        c4 = by.get("2026-01-04") or {}
        ck(c4.get("close") == 1200.0 and c4.get("open") == 1200.0
           and c4.get("high") == 1200.0 and c4.get("low") == 1200.0,
           "ردیفِ سایه‌صفر: پایانیِ منتشرشده می‌ماند و بدن/سایه از همان ساخته می‌شود",
           str(c4)[:160])
        c7 = by.get("2026-01-07") or {}
        ck(c7.get("close") == 1550.0 and c7.get("high") >= 1550.0 and c7.get("low") <= 1550.0,
           "سایۀِ ناقصِ منبع گِشاد می‌شود؛ پایانیِ منتشرشده کُنده نمی‌شود", str(c7)[:160])
        ck("2026-01-05" not in by and "2026-01-06" not in by,
           "ردیف‌هایِ ردشده درِ سری نمی‌نشینند (نه کندلِ صفر، نه کپیِ روزِ پیش)", "")
        ck(by.get("2026-01-03", {}).get("volume") == 1e9,
           "تکراریِ همان روز: پرحجم‌تر می‌ماند، نه آخرینِ نوشتار",
           str(by.get("2026-01-03"))[:120])
        ck([c["time"] for c in cs] == sorted(c["time"] for c in cs),
           "ترتیبِ صعودیِ زمانی حفظ می‌شود", "")
        ck(len({c["time"] for c in cs}) == len(cs), "تاریخِ تکراری درِ خروجی نیست", "")
        ck(c4.get("last") is None,
           "«آخرینِ» نبودِ منبع None می‌ماند (هیچ‌وقت جای‌نمایِ پایانی نمی‌شود)",
           str(c4.get("last")))
        facts = r.get("factors") or []
        ck(len(facts) == len(cs),
           "ضریب‌ها هم‌تعدادِ کندل‌ها می‌آیند (تطبیق با تاریخ، نه اندیس)",
           "factors=%s candles=%s" % (len(facts), len(cs)))
        ck(all(f.get("time") in by for f in facts),
           "هرِ ضریب رویِ همان تاریخِ کندل خودش است", "")
        # دو حالتِ سریِ قیمت: مبنایِ انتخابی عوض می‌شود، خامِ lنگر می‌ماند
        times = [c["time"] for c in cs]
        closes_last = [c["close"] for c in cs]
        PB.set_basis("closing")
        r2 = CH.get_chart_db(SYM)
        cs2 = {c["time"]: c for c in (r2.get("candles") or [])}
        ck([t for t in (c["time"] for c in r2.get("candles") or [])] == times,
           "هرِ دو مبنایِ ممکن همان مجموعهٔ روزها را می‌دهد (مبنا روز حذف نمی‌کند)", "")
        ck(cs2["2026-01-03"]["close"] == 1040.0,
           "مبنایِ `closing` پایانیِ خامِ منتشرشده را می‌دهد", str(cs2.get("2026-01-03"))[:120])
        ck(all(geometry_ok(c) for c in cs2.values()),
           "درِ هرِ دو مبن، هندسه برقرار می‌ماند", "")
        # این سری یکِ ردیفِ بی‌«آخرین» دارد (2026-01-04؛ منبع آن را منتشر نکرده).
        # قاعدۀِ ۳ قرارداد: بی‌مخالفتِ مبنی رویِ `closing` می‌نشیند و صریح اعلام می‌کند —
        # نه سریِ مخلوط، نه عددِ ساخته‌شده، نه سکوت.
        ck(r.get("priceBasisRequested") == "last" and r.get("priceBasis") == "closing"
           and r.get("priceBasisLastMissing") == 1,
           "مبنایِ درخواستیِ `last` با اعلامِ صریحِ «بی‌آخرین» به `closing` می‌نشیند "
           "(سریِ مخلوط نمی‌سازیم)",
           "req=%s applied=%s missing=%s" % (r.get("priceBasisRequested"),
                                             r.get("priceBasis"), r.get("priceBasisLastMissing")))
        ck(r2.get("priceBasis") == "closing" and r2.get("priceBasisRequested") == "closing",
           "پاسخ می‌گوید کدامِ مبنا درخواست و اعمال شده (شرطِ ۵ قرارداد)",
           "%s / %s" % (r2.get("priceBasisRequested"), r2.get("priceBasis")))
        ck(cs2["2026-01-03"]["close"] == closes_last[0],
           "درِ هرِ دو درخواست، همان عددِ پایانیِ خام می‌ماند (بی‌جعلِ «آخرین»)",
           "%s vs %s" % (closes_last[0], cs2["2026-01-03"]["close"]))
        # د) بانکِ دوم: همان روزها با «آخرینِ» کامل ⇒ مبنایِ `last` واقعاً اعمال می‌شود
        # و با `closing` فرق دارد؛ بی‌این، تستِ بالا فقط جانبِ «بازگشتِ safe» را می‌دید.
        rows_full = [(r[0], r[1], r[2], r[3], r[4], r[5], r[6],
                      (r[7] if r[7] is not None else float(r[5]) * 0.99),
                      r[8], r[9]) for r in ROWS]
        dbp2 = new_db(rows_full)
        CH.DB_PATH = CORE.DB_PATH = test_tsetmc.DB_PATH = dbp2
        try:
            PB.set_basis("last")
            rf = CH.get_chart_db(SYM)
            fb = {c["time"]: c for c in rf.get("candles") or []}
            PB.set_basis("closing")
            rc = CH.get_chart_db(SYM)
            cb = {c["time"]: c for c in rc.get("candles") or []}
            ck(rf.get("priceBasis") == "last" and not rf.get("priceBasisLastMissing"),
               "با «آخرینِ» کامل، مبنایِ `last` اعمال می‌شود (بی‌بازگشتِ safe)",
               "applied=%s missing=%s" % (rf.get("priceBasis"), rf.get("priceBasisLastMissing")))
            ck(abs(fb["2026-01-03"]["close"] - 1035.0) < 1e-9
               and abs(cb["2026-01-03"]["close"] - 1040.0) < 1e-9,
               "دو مبنا دو عددِ متفاوتِ منتشرشده می‌دهند (هیچ‌کدام جعل نیست)",
               "%s vs %s" % (fb["2026-01-03"]["close"], cb["2026-01-03"]["close"]))
            ck(sorted(fb) == sorted(cb),
               "مبنا هیچ روزی از سری کم یا زیاد نمی‌کند", "")
            ck(all(geometry_ok(c) for c in fb.values()) and all(geometry_ok(c) for c in cb.values()),
               "درِ هرِ دو مبنایِ کامل هم هندسه برقرار است", "")
        finally:
            try:
                os.remove(dbp2)
            except OSError:
                pass
    finally:
        CH.DB_PATH, CORE.DB_PATH, test_tsetmc.DB_PATH, want = keep
        PB.set_basis(want if want in PB.ALLOWED else PB.DEFAULT)
        try:
            os.remove(dbp)
        except OSError:
            pass

    print(f"\ndb_candle_contract_v1: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
