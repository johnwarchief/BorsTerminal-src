#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/codal_period_canonical_v1075.py — یکِ حقیقت برایِ «دورۀ گزارش».

چرا این گارد متولد شد (بخشِ بنیادیِ کارِ #73، ۱۴۰۵-۰۷-۱۰، فرمانِ مالک: «برایِ
period_end یک منطقِ واحد و canonical بساز؛ هیچ query جداگانه‌ای برای شمارشِ
این رکوردها نداشته باشیم»):

  • پنج تعریفِ مختلف از «ردیفِ بی‌دوره» درِ مخزن باز شد (inventoryِ کامل درِ
    `docs/fts-notes/FUND_LIVE_AUDIT.md`): `period_end IS NOT NULL` درِ
    `dev/db_housekeeping.py`، `dev/db_final_report.py` و `dev/codal_logic_guard.py`؛
    `str(pe or "")[:4]` برایِ سالِ مالی درِ `fts_engine` وِ `int(str(pe)[:4])` درِ
    مسیرِ EPSِ `api/fundamental.py`؛ سه regexِ مجزا برایِ دوره درِ `codal_fetcher`؛
    و چهار کپیِ «first-wins رویِ ORDER BY period_end DESC» برایِ نگاشتِ نامِ شرکت.
  • «بی‌دوره» درِ آن تعریف‌ها با هم نمی‌خواند: رقمِ فارسی یا خط تیره درِ یکِ مسیر
    «دوره دارد» بود و درِ مسیرِ دیگر «nd IS NOT NULL» ردش می‌کرد، پس ترتیبِ
    «تازه‌ترین» به SQLite واگذار شده بود (NULL تصادفاً آخر می‌افتاد).

قراردادی که این گارد می‌کارد (بند به بند از `codal_periods`):
  ۱ شکلِ canonical `'YYYY/MM/DD'` است؛ هر چیزِ دیگر بی‌دوره است.
  ۲ شرطِ SQL (`DATED_SQL`/`UNDATED_SQL`) و شرطِ پایتون (`is_undated`) هم‌معناوند.
  ۳ زنجیرۀ استخراج: datasource ← عنوان («منتهی به» لنگر است).
  ۴ ردیفِ بی‌دوره **حذف نمی‌شود** و «آخرین دوره» هم نمی‌شود.
  ۵ شمارشِ بی‌دوره‌ها یکِ تابع است: `undated_counts` — و هر مصرف‌کننده همان عدد.

اجرا:  python dev/codal_period_canonical_v1075.py     → ۰ سبز، ۰ قرمز
"""
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import codal_periods as CP  # noqa: E402
import codal_fetcher as CF  # noqa: E402

PASS = FAIL = 0


def ck(cond, what, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {what}")
    else:
        FAIL += 1
        print(f"  ✗ {what}" + (f"   ← {detail}" if detail else ""))


SLASH = chr(47)          # «/» — بی‌نقلِ مستقیم درِ رشته‌هایِ دوزبانه
FS_TITLE = "اطلاعات و صورت\u200cهای مالی میاندورهای  دوره ۳ ماهه منتهی به  ۱۴۰۵/۰۶/۳۱"


def new_db():
    path = os.path.join(tempfile.mkdtemp(prefix="period_guard_"), "t.db")
    conn = sqlite3.connect(path)
    CF.create_schema(conn)
    CF.migrate_schema(conn)
    return conn


def seed_fs(conn, rows):
    """rows = [(tracing_no, symbol, period_end_raw, is_consolidated, revenue)]"""
    for tn, sym, pe, cons, rev in rows:
        conn.execute("INSERT OR REPLACE INTO financial_statements"
                     " (tracing_no, symbol, company_name, title, period_end,"
                     "  period_months, revenue, gross_profit, net_profit, is_consolidated)"
                     " VALUES (?,?,?,?,?,12,?,?,?,?)",
                     (tn, sym, sym, FS_TITLE, pe, rev, (rev or 0) / 2, (rev or 0) / 5, cons))
    conn.commit()


# ── ۱) شکل و شرط ────────────────────────────────────────────────────────────
def test_shape():
    print("\n— ۱) شکلِ canonical و یکی‌بودنِ شرطِ SQL با شرطِ پایتون")
    good = ["1405" + SLASH + "06" + SLASH + "31", "۱۴۰۵" + SLASH + "۰۶" + SLASH + "۳۱",
            "1405-06-31", "1405/6/3", "1405" + SLASH + "06" + SLASH + "31 18:10:30"]
    expect = ["1405" + SLASH + "06" + SLASH + "31", "1405" + SLASH + "06" + SLASH + "31",
              "1405" + SLASH + "06" + SLASH + "31", "1405" + SLASH + "06" + SLASH + "03",
              "1405" + SLASH + "06" + SLASH + "31"]
    for raw, want in zip(good, expect):
        ck(CP.canonicalize(raw) == want, "canonicalize(%r) → %r" % (raw, want),
           str(CP.canonicalize(raw)))
    # رقمِ فارسی **ورودیِ معتبر** است (منبعِ کدال/عنوان) ولی **ستونِ canonical** نیست:
    # canonicalize آن را می‌خواند، is_canonical آن را بی‌دوره می‌شناسد تا شرطِ SQL و
    # شرطِ پایتون جدا نیفتند (بندِ ۲ قرارداد).
    ck(CP.canonicalize("۱۴۰۵/۰۶/۳۱") == "1405" + SLASH + "06" + SLASH + "31"
       and CP.is_undated("۱۴۰۵/۰۶/۳۱") and not CP.is_canonical("۱۴۰۵/۰۶/۳۱"),
       "ورودیِ فارسی‌رقم پذیرفته، ولی درِ ستون canonical شمرده نمی‌شود", "")
    bad = [None, "", "   ", "بی‌تاریخ", "۱۴۰۵/۱۳/۴۵", "1405/02/301", "06/31"]
    for raw in bad:
        ck(CP.canonicalize(raw) is None, "canonicalize(%r) بی‌دوره است" % (raw,),
           str(CP.canonicalize(raw)))

    conn = new_db()
    seed_fs(conn, [(1, "الف", "1405" + SLASH + "06" + SLASH + "31", 0, 100.0),
                   (2, "ب", "۱۴۰۴" + SLASH + "۱۲" + SLASH + "۲۹", 0, 50.0),   # رقمِ فارسی
                   (3, "پ", "1403-09-30", 0, 20.0),                          # خط تیره
                   (4, "ت", None, 0, 7.0),                                   # NULL
                   (5, "ث", "   ", 0, 6.0),                                  # فاصله
                   (6, "ج", "۱۴۰۴/۰۹/۲۳ ۱۸:۱۰:۳۰", 0, 5.0)])      # برچسبِ ساعت (سطرِ خرابِ واقعی)
    sql_und = {r[0] for r in conn.execute(
        f"SELECT symbol FROM financial_statements WHERE {CP.UNDATED_SQL}")}
    py_und = {sym for (sym, pe) in conn.execute(
        "SELECT symbol, period_end FROM financial_statements") if CP.is_undated(pe)}
    ck(sql_und == py_und, "شرطِ SQL و شرطِ پایتون رویِ همان داده یکِ مجموعه می‌دهند",
       "sql=%s py=%s" % (sorted(sql_und), sorted(py_und)))
    ck(sql_und == {"ب", "پ", "ت", "ث", "ج"},
       "«دوره دارد» یعنی شکلِ canonical — نه «غیرNULL»: رقمِ فارسی، خط تیره، "
       "فاصله و برچسبِ ساعت همه بی‌دوره‌اند", str(sorted(sql_und)))
    conn.close()


# ── ۲) زنجیرۀ استخراج ───────────────────────────────────────────────────────
def test_derive():
    print("\n— ۲) زنجیرۀ استخراج: datasource بر عنوان می‌چربد")
    pe, src = CP.derive("1404" + SLASH + "12" + SLASH + "29", "منتهی به ۱۴۰۵/۰۶/۳۱")
    ck((pe, src) == ("1404" + SLASH + "12" + SLASH + "29", "datasource"),
       "datasource موجود ⇒ همان منبع", str((pe, src)))
    pe, src = CP.derive(None, FS_TITLE)
    ck((pe, src) == ("1405" + SLASH + "06" + SLASH + "31", "title"),
       "datasource تهی ⇒ عنوان، و عنوان با دو فاصله هم خوانده می‌شود", str((pe, src)))
    pe, src = CP.derive("چرند", "بدون تاریخ")
    ck((pe, src) == (None, None), "هیچ منبعی ⇒ بی‌دوره (بی‌حدس، بی صفر)", str((pe, src)))
    two = "گزارش بازگشایی: از ۱۴۰۳/۰۱/۰۱ تا ۱۴۰۴/۰۶/۳۱ — دوره منتهی به ۱۴۰۴/۰۶/۳۱"
    ck(CP.from_title(two) == "1404" + SLASH + "06" + SLASH + "31",
       "لنگرِ «منتهی به»: تاریخِ اولِ بازه نه، پایانِ دوره", str(CP.from_title(two)))


# ── ۳) ترتیب: بی‌دوره هرگز «آخرین» نمی‌شود ──────────────────────────────────
def test_order():
    print("\n— ۳) تازه‌ترین اول؛ بی‌دوره همیشه بازنده")
    vals = ["1403" + SLASH + "12" + SLASH + "29", None, "1405" + SLASH + "06" + SLASH + "31",
            "1404" + SLASH + "12" + SLASH + "29", "1404" + SLASH + "12" + SLASH + "29"]
    ordered = sorted(vals, key=CP.desc_sort_key, reverse=True)
    ck(ordered[:3] == ["1405" + SLASH + "06" + SLASH + "31", "1404" + SLASH + "12" + SLASH + "29",
                       "1404" + SLASH + "12" + SLASH + "29"] and ordered[-1] is None,
       "desc_sort_key: تاریخ‌ها کاهشی، بی‌دوره آخر", str(ordered))
    ck(CP.latest([None, "", "1402" + SLASH + "09" + SLASH + "30", "1403" + SLASH + "03" + SLASH + "31"])
       == "1403" + SLASH + "03" + SLASH + "31", "latest() بی‌دوره را رد می‌کند", "")

    conn = new_db()
    seed_fs(conn, [(11, "خ", "1399" + SLASH + "12" + SLASH + "30", 0, 10.0),
                   (12, "خ", None, 0, 900.0),                  # بی‌دوره با بزرگ‌ترین عدد
                   (13, "خ", "1398" + SLASH + "12" + SLASH + "30", 0, 20.0)])
    got = conn.execute("SELECT tracing_no FROM financial_statements WHERE symbol='خ' "
                       "%s LIMIT 1" % CP.latest_order_sql()).fetchone()[0]
    ck(got == 11, "latest_order_sql درِ SQL: ردیفِ ۱۳۹۹ می‌برد نه بی‌دورۀ ۹۰۰تایی", str(got))
    conn.close()


# ── ۴) ردیفِ بی‌دوره حذف نمی‌شود ─────────────────────────────────────────────
def test_undated_survives():
    print("\n— ۴) جمع‌شدنِ دوره‌ها به ردیفِ بی‌دوره دست نمی‌زند")
    conn = new_db()
    seed_fs(conn, [(21, "د", "1405" + SLASH + "06" + SLASH + "31", 1, 160.0),
                   (22, "د", "1405" + SLASH + "06" + SLASH + "31", 0, 100.0),
                   (23, "د", None, 0, 7.0),
                   (24, "د", "1404" + SLASH + "12" + SLASH + "29", 0, 60.0)])
    removed = CF.collapse_symbol(conn, "د")
    left = conn.execute("SELECT tracing_no FROM financial_statements ORDER BY tracing_no"
                        ).fetchall()
    ck([r[0] for r in left] == [22, 23, 24],
       "تلفیقیِ هم‌دوره حذف شد؛ بی‌دوره و تنها-ردیفِ دورهٔ دیگر سالم‌اند",
       "%s removed=%s" % ([r[0] for r in left], removed))
    ck(CP.undated_counts(conn)["financial_statements"] == 1,
       "و آن یکِ ردیفِ سالم، درِ شمارشِ واحد «بی‌دوره» دیده می‌شود",
       str(CP.undated_counts(conn)))


# ── ۵) همهٔ مصرف‌کننده‌ها یک عدد می‌بینند ────────────────────────────────────
def test_one_number(conn, label):
    print("\n— ۵) یکِ عدد، همهٔ مسیرها (%s)" % label)
    want = CP.undated_counts(conn)
    per_table = {t: conn.execute(
        f"SELECT COUNT(*) FROM {t} WHERE {CP.UNDATED_SQL}").fetchone()[0]
        for t in CP.tables(conn)}
    ck(all(want.get(t) == n for t, n in per_table.items())
       and want["total"] == sum(per_table.values()),
       "undated_counts = شرطِ canonical رویِ هر دو جدول + جمعشان",
       "%s vs %s" % (want, per_table))
    # خانه‌هایِ دستِ‌سازِ همان جدول‌ها هم‌خوان‌اند (نه شمارشِ دوم)
    ck(set(want) == set(per_table) | {"total"}, "undated_counts ستونِ سومی ندارد",
       str(sorted(want)))
    # housekeeping: کوئریِ شمارشِ ندارد، از همان counts می‌خواند
    sys.path.insert(0, os.path.join(ROOT, "dev"))
    import db_housekeeping as HK  # noqa: E402
    cov = HK._coverage(conn)
    ck(cov["undated"] == want, "dev/db_housekeeping همان عدد را گزارش می‌کند",
       str(cov.get("undated")))
    # fts_engine: «آخرینِ سالانه» هرگز بی‌دوره نیست
    import fts_engine as FE  # noqa: E402
    bad = []
    for sym in {r[0] for r in conn.execute("SELECT DISTINCT symbol FROM financial_statements")}:
        for row in FE.annual_statements(conn, sym, require_audit=False,
                                       exclude_consolidated=False, limit=4):
            if CP.is_undated(row["period_end"]) or not row["fiscal_year"]:
                bad.append((sym, row["period_end"]))
    ck(not bad, "fts_engine.annual_statements: نه ردیفِ بی‌دوره، نه سالِ مالیِ تهی", str(bad[:3]))
    # موتورِ بنیادی (card): کوئری‌هایِ «آخرین» به canonical واگرد کرده‌اند
    src = open(os.path.join(ROOT, "api", "fundamental.py"), encoding="utf-8").read()
    ck(src.count("CP.DATED_SQL") + src.count("CP.latest_order_sql") >= 3,
       "api/fundamental.py هر سه کوئریِ «آخرین» را به canonical واگرد کرده", "")
    scr = open(os.path.join(ROOT, "api", "screener.py"), encoding="utf-8").read()
    ck("ORDER BY period_end DESC" not in scr,
       "api/screener.py ترتیبِ خامِ period_end ندارد", "")
    return want


def test_real_db():
    print("\n— ۵-ب) بانکِ کاریِ خواندنی (اگر هست)")
    if not os.path.exists(CF.DB_PATH):
        print("  · market.db نیست — این بخش رد شد")
        return None
    conn = sqlite3.connect(CF.DB_PATH, timeout=30, isolation_level=None)
    try:
        return test_one_number(conn, "market.db واقعی")
    finally:
        conn.close()


def main():
    test_shape()
    test_derive()
    test_order()
    test_undated_survives()
    conn = new_db()
    seed_fs(conn, [(31, "ی", "1405" + SLASH + "06" + SLASH + "31", 0, 10.0),
                   (32, "ی", "۱۴۰۴/۱۲/۲۹", 0, 11.0),
                   (33, "ی", None, 0, 12.0)])
    test_one_number(conn, "بانکِ آزمون")
    conn.close()
    test_real_db()
    print(f"\nنتیجه: {PASS} سبز، {FAIL} قرمز")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
