#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/codal_ingest_identity_v1088.py — گاردِ CA-3: هویتِ اطلاعیه و بی‌انباشتِ تکراری.

ادعایِ دورِ اول («نبودِ upsert ⇒ ردیفِ تکراری انباشته می‌شود») با شواهد باطل شد:
  • `financial_statements.tracing_no INTEGER PRIMARY KEY`
  • `codal_fetcher.FS_UPSERT = INSERT … ON CONFLICT(tracing_no) DO UPDATE SET …`
پس بازنشرِ **یکِ اطلاعیه** ردیفِ تازه نمی‌سازد. یگانۀ هویتِ ingest = شمارهٔ ردّ
خودِ کدال (`tracing_no`) است، نه ترکیبِ حدسیِ (نماد، دوره).

این گارد رویِ بانکِ موقتِ کوچک با schemaِ **خودِ** `codal_fetcher` (create_schema +
migrate_schema) می‌دود و چیزی را ثابت می‌کند که اگر روزی شکست، یعنی دادهٔ بنیادی
درِ خطر است:
  ۱) ingestِ مکررِ یکِ اطلاعیه ⇒ شمارِ ردیف ثابت، مقدارِ نو اعمال می‌شود، و
     ستون‌هایِ بی‌FS_COLS (مثلِ `has_operating_sales`) له نمی‌شوند؛
  ۲) دو اطلاعیهٔ متفاوت برایِ یکِ دوره ⇒ **ادغام نمی‌شوند** (سه ردیف، سه ردیف می‌ماند)؛
  ۳) اصلی و تلفیقیِ یکِ دوره، و دو دورۀ متفاوت، و FS در برابرِ ماهانه ⇒ جدا؛
  ۴) مهاجرتِ اسکیما یدم‌پذیر است (دو بار = یک بار، بی‌از دست دادنِ ردیف/ستون)؛
  ۵) هیچِ مسیرِ ingest ردیفی را **حذف** نمی‌کند — شمارشِ کل فقط می‌افزاید.

این گارد «پاک‌سازیِ تاریخی» نمی‌کند و نمی‌تواند: قاعدۀ جمعِ ردیف‌ها
(`codal_fetcher.collapse_symbol`) رویِ نمادهایِ هلدینگ ۱۴ از ۱۵ ردیفِ مشروعِ
شرکت‌هایِ فرعی را می‌کُشد (شاهد: `_audit/codal_record_identity_2026-10-12.csv`)،
پس هر پاک‌سازیِ خودکار پیش از رأیِ جزوه دربارهٔ «کدامِ رکورد خودِ نماد است»
ممنوع است → NEEDS_REVIEW.

اجرا:  python dev/codal_ingest_identity_v1088.py     (۰ = سبز، ۱ = رد)
"""
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import codal_fetcher as CF                                  # noqa: E402
import codal_periods as CP                                  # noqa: E402

PASS = FAIL = 0

T_MAIN = "صورت‌های مالی  سال مالی منتهی به ۱۴۰۴/۱۲/۲۹ (حسابرسی شده)"
T_CONS = "صورت‌های مالی تلفیقی سال مالی منتهی به ۱۴۰۴/۱۲/۲۹ (حسابرسی شده)"
T_SUB = "صورت‌های مالی  سال مالی منتهی به ۱۴۰۴/۱۲/۲۹ (حسابرسی شده) (شرکت فرعی الف)"
T_AMEND = "صورت‌های مالی  سال مالی منتهی به ۱۴۰۴/۱۲/۲۹ (حسابرسی شده)(اصلاحیه)"
PE = "1404/12/29"
PE2 = "1405/03/31"


def chk(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("  FAIL  %s   %s" % (label, extra))


def fs_values(tracing_no, symbol="هویت", title=T_MAIN, period_end=PE,
              period_months=12, publish_date="1405/05/01 10:00:00",
              revenue=100.0, gross_profit=40.0, net_profit=20.0, basic_eps=2.0,
              operating_profit=30.0, total_assets=500.0, total_equity=300.0,
              capital=100.0):
    """دیکشنریِ ستون→مقدار؛ ردیفِ `FS_UPSERT` از رویِ **نامِ** ستون ساخته می‌شود."""
    vals = {"tracing_no": tracing_no, "symbol": symbol,
            "company_name": "شرکت آزمون", "title": title,
            "report_kind": "Financial Statements", "period_months": period_months,
            "period_end": period_end, "publish_date": publish_date,
            "revenue": revenue, "gross_profit": gross_profit,
            "operating_profit": operating_profit, "net_profit": net_profit,
            "total_assets": total_assets, "total_liabilities": 200.0,
            "total_equity": total_equity, "capital": capital,
            "retained_earnings": 10.0, "basic_eps": basic_eps,
            "unit": "mrl", "url": "https://codal.ir/%d" % tracing_no,
            "fetched_at": "2026-10-12T00:00:00"}
    vals.update(dict(zip(("is_audited", "is_consolidated", "fiscal_year", "unit_norm"),
                         CF.fs_derived(title, period_end, "mrl"))))
    return vals


def row_from(vals):
    return [vals.get(c) for c in CF.FS_COLS]


class Ingest:
    """بانکِ موقت با schemaِ واقعی + فرمانِ نوشتنِ واقعیِ مسیرِ ingest."""

    def __init__(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.schema_once()

    def schema_once(self):
        c = self.conn()
        CF.create_schema(c)
        CF.migrate_schema(c)
        c.commit()
        c.close()

    def conn(self):
        return sqlite3.connect(self.path, timeout=15)

    def put(self, *valsd):
        c = self.conn()
        try:
            c.executemany(CF.FS_UPSERT, [row_from(v) for v in valsd])
            c.commit()
        finally:
            c.close()

    def count(self, table="financial_statements"):
        c = self.conn()
        try:
            return c.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
        finally:
            c.close()

    def get(self, tracing_no):
        c = self.conn()
        c.row_factory = sqlite3.Row
        try:
            r = c.execute("SELECT * FROM financial_statements WHERE tracing_no=?",
                          (tracing_no,)).fetchone()
            return dict(r) if r else None
        finally:
            c.close()

    def columns(self, table="financial_statements"):
        c = self.conn()
        try:
            return {r[1] for r in c.execute("PRAGMA table_info(%s)" % table)}
        finally:
            c.close()

    def close(self):
        try:
            os.remove(self.path)
        except OSError:
            pass


def t1_repeat_same_notice():
    # ── ۱) بازنشرِ یکِ اطلاعیه ⇒ یکِ ردیف، مقدارِ نو، ستون‌هایِ بی‌FS_COLS له‌نشده ─
    ing = Ingest()
    try:
        c = ing.conn()
        c.execute("INSERT INTO codal_notices (tracing_no, symbol, title, publish_date)"
                  " VALUES (900, 'هویت', ?, '1405/05/01 10:00:00')", (T_MAIN,))
        c.commit()
        c.close()
        ing.put(fs_values(900, revenue=100.0, gross_profit=40.0))
        c = ing.conn()
        c.execute("UPDATE financial_statements SET has_operating_sales=1 WHERE tracing_no=900")
        c.commit()
        c.close()
        first = ing.count()
        # بارِ دوم: همان اطلاعیه با عددِ اصلاح‌شده (بازخوانیِ همان URL)
        ing.put(fs_values(900, revenue=130.0, gross_profit=55.0))
        third = ing.count()
        chk(first == 1 and third == 1,
            "۱ بازنشرِ یکِ tracing_no ردیفِ دوم نمی‌سازد", "%d → %d" % (first, third))
        row = ing.get(900)
        chk(row["revenue"] == 130.0 and row["gross_profit"] == 55.0,
            "۱ مقدارِ نو اعمال شد (قراردادِ نسخه‌گذاری: DO UPDATE)")
        chk(row.get("has_operating_sales") == 1,
            "۱ ستونِ بی‌FS_COLS با بازنشر به NULL برنمی‌گردد (به‌همین‌دلیل INSERT OR REPLACE نیست)",
            str(row.get("has_operating_sales")))
    finally:
        ing.close()


def t2_two_notices_one_period_not_merged():
    # ── ۲) دو اطلاعیهٔ متفاوت، یکِ دوره ⇒ ادغام نمی‌شوند ─────────────────────
    ing = Ingest()
    try:
        ing.put(fs_values(901, publish_date="1405/05/01 10:00:00"),
                fs_values(902, title=T_AMEND,
                          publish_date="1405/06/01 10:00:00"),
                fs_values(903, title=T_SUB, publish_date="1405/06/02 10:00:00"))
        chk(ing.count() == 3,
            "۲ سه اطلاعیهٔ یکِ دوره ⇒ سه ردیف (کلیدِ ادغامِ فراترِ tracing_no اجرا نمی‌شود)")
        # ingestِ دوبارۀ هر سه ⇒ همان سه ردیف
        ing.put(fs_values(901), fs_values(902, title=T_AMEND),
                fs_values(903, title=T_SUB))
        chk(ing.count() == 3, "۲ re-ingestِ کاملِ دسته بی‌ردیفِ اضافه")
    finally:
        ing.close()


def t3_distinct_dimensions_stay_distinct():
    # ── ۳) اصلی/تلفیقی، دو دوره، FS/ماهانه ⇒ هر کدام هویتِ خودش ─────────────
    ing = Ingest()
    try:
        ing.put(fs_values(910, title=T_MAIN, period_end=PE),
                fs_values(911, title=T_CONS, period_end=PE),
                fs_values(912, title=T_MAIN, period_end=PE2),
                fs_values(913, title=T_SUB, period_end=PE))
        chk(ing.count() == 4, "۳ چهار ردیفِ مشروع از چهار بُعدِ متفاوت")
        periods = {}
        c = ing.conn()
        c.row_factory = sqlite3.Row
        for r in c.execute("SELECT tracing_no, period_end FROM financial_statements"):
            periods[r["tracing_no"]] = CP.canonicalize(r["period_end"])
        c.close()
        chk(periods[910] == PE and periods[912] == PE2 and periods[913] == PE,
            "۳ دوره‌ها با هم قاطی نمی‌شوند (هر شرکت/نوع، ردیفِ خودش)", str(periods))
        # ماهانۀ همان اطلاعیه در جدولِ جدا می‌نشیند و FS را کم نمی‌کند
        c = ing.conn()
        c.execute("INSERT INTO monthly_sales (tracing_no, symbol, title, period_end,"
                  " year, month, monthly_revenue, ytd_revenue)"
                  " VALUES (910, 'هویت', ?, ?, 1405, 4, 10.0, 40.0)", (T_MAIN, "1405/04/31"))
        c.commit()
        c.close()
        chk(ing.count() == 4 and ing.count("monthly_sales") == 1,
            "۳ ردیفِ ماهانه در جدولِ خودش؛ ردیفِ مالیِ هم‌tracing_no دست‌نخورده")
    finally:
        ing.close()


def t4_schema_migration_idempotent():
    # ── ۴) مهاجرتِ اسکیما دوبار = یک‌بار ────────────────────────────────────
    ing = Ingest()
    try:
        ing.put(fs_values(920))
        cols_before, cnt_before = ing.columns(), ing.count()
        ing.schema_once()
        ing.schema_once()
        chk(ing.columns() == cols_before,
            "۴ اجرایِ مکررِ create_schema+migrate_schema ستونِ اضافه/کم نمی‌کند")
        chk(ing.count() == cnt_before and ing.get(920) is not None,
            "۴ مهاجرتِ دوباره ردیف‌ها را له نمی‌کند")
    finally:
        ing.close()


def t5_ingest_never_deletes():
    # ── ۵) هیچِ مسیرِ ingest حذف نمی‌کند: شمارش فقط می‌افزاید ────────────────
    ing = Ingest()
    try:
        seen = [ing.count()]
        for i, (tno, title) in enumerate(((930, T_MAIN), (931, T_CONS), (932, T_SUB))):
            ing.put(fs_values(tno, title=title))
            seen.append(ing.count())
        chk(seen == sorted(seen) and seen[-1] == 3,
            "۵ ingestِ پیوسته ⇒ شمارش یکنوا (هیچ DELETE درِ مسیرِ نوشتن نیست)", str(seen))
    finally:
        ing.close()


def t6_period_contract_rejects_ambiguity():
    # ── ۶) ردیفِ بی‌دوره «برندهٔ دوره» نمی‌شود و بی‌هویت ذخیره می‌شود ────────
    ing = Ingest()
    try:
        ing.put(fs_values(940, period_end=PE),
                fs_values(941, period_end=None),
                fs_values(942, period_end="1404-12-29"))
        chk(ing.count() == 3, "۶ هر سه ذخیره می‌شوند (بی‌دوره رد نمی‌شود)")
        und = sum(1 for tno in (940, 941, 942)
                  if CP.is_undated((ing.get(tno) or {}).get("period_end")))
        chk(und == 2, "۶ دو ردیفِ غیرcanonical با همان قاعدۀ `codal_periods` بی‌دوره‌اند",
            str(und))
    finally:
        ing.close()


def main():
    for fn in (t1_repeat_same_notice, t2_two_notices_one_period_not_merged,
               t3_distinct_dimensions_stay_distinct, t4_schema_migration_idempotent,
               t5_ingest_never_deletes, t6_period_contract_rejects_ambiguity):
        fn()
    print("codal_ingest_identity_v1088: %d passed / %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
