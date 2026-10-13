# -*- coding: utf-8 -*-
"""گاردِ لایۀ canonical هویت نماد — Stage 1.2 مأموریت بنیادی (1405/07/22).

چرا این گارد هست: پیش‌تر «این دو رشته یکی‌اند؟» چهار تعریف مستقل داشت
(`symbol_aliases`ِ جایگشتی، `norm_fa` به‌عنوان کلید دسته‌بندی، زنجیرۀ REPLACE
دست‌ساز در `_INSTR_SQL`، و `norm()` در codal_fetcher). نتیجه‌اش یک باگِ واقعی
بود: کارتِ «شهر فرش» ۱ ردیف می‌دید و قیف ۷ ردیف، چون شش ردیف زیرِ نوشتارِ
«شهر + نیم‌فاصله + فرش» ثبت شده بودند و جایگشتِ ورودی هیچ‌وقت نیم‌فاصله را
**نمی‌ساخت**. این گارد سه چیز را می‌بندد:

  الف) قراردادِ لایه (کلید، دامنه‌ها، گیتِ ISIN) آزمون‌پذیر است؛
  ب) هیچ خوانندۀ پروداکشنی دوباره کلیدِ دوم یا جایگشتِ نویسه نمی‌سازد (AST)؛
  ج) هر ده پروندۀ رگرسیونِ مرحلۀ 1.2 با **رفتارِ واقعی** (نه با متنِ کد) سنجیده
     می‌شود، شامل چهار کنترلِ منفی که اگر سنسور کور شود، قرمز می‌شوند.

اجرا:  PYTHONIOENCODING=utf-8 python dev/symbol_identity_v1090.py
"""
from __future__ import annotations

import ast
import io
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import fts_engine as FE                      # noqa: E402
import symbol_identity as SI                  # noqa: E402

CHECKS = []


def ck(cond, msg, detail=""):
    CHECKS.append((bool(cond), msg))
    print("  %s %s%s" % ("✓" if cond else "✗", msg, (("   ← " + str(detail)[:150]) if detail else "")))


# ── بانکِ آزمون: همان ستون‌هایی که مسیرهای واقعی می‌خوانند ──────────────────
def make_db():
    fd, path = tempfile.mkstemp(prefix="symid-", suffix=".db")
    os.close(fd)
    c = sqlite3.connect(path)
    c.executescript("""
    CREATE TABLE financial_statements (
        tracing_no INTEGER PRIMARY KEY, symbol TEXT, company_name TEXT, title TEXT,
        report_kind TEXT, period_months INTEGER, period_end TEXT, publish_date TEXT,
        revenue REAL, gross_profit REAL, operating_profit REAL, net_profit REAL,
        total_assets REAL, total_liabilities REAL, total_equity REAL, capital REAL,
        retained_earnings REAL, basic_eps REAL, unit TEXT, url TEXT, fetched_at TEXT,
        is_audited INTEGER DEFAULT 0, is_consolidated INTEGER DEFAULT 0,
        fiscal_year TEXT, unit_norm TEXT, has_operating_sales INTEGER);
    CREATE TABLE monthly_sales (
        tracing_no INTEGER PRIMARY KEY, symbol TEXT, title TEXT, period_end TEXT,
        year INTEGER, month INTEGER, monthly_revenue REAL, ytd_revenue REAL,
        pdf_url TEXT, excel_url TEXT, monthly_revenue_prev REAL, ytd_revenue_prev REAL,
        monthly_volume REAL, ytd_volume REAL, volume_unit TEXT);
    CREATE TABLE codal_notices (tracing_no INTEGER PRIMARY KEY, symbol TEXT,
        title TEXT, publish_date TEXT, report_type TEXT, url TEXT);
    CREATE TABLE instruments (ins_code TEXT PRIMARY KEY, l_val18 TEXT, l_val30 TEXT,
        sector_code TEXT, sector_name TEXT, total_shares REAL, eps REAL, pe REAL,
        base_vol REAL, updated_at TEXT, paper_type TEXT, isin TEXT, c_gr_val_cot REAL);
    CREATE TABLE price_history (symbol TEXT, date TEXT, close REAL);
    """)
    Z = "‌"
    rows = [
        # خانوادۀ «شهر فرش»: دو نوشتار، یک صادرکننده، یک ردیفِ شرکتِ دیگر
        (1604925, "شهر فرش", "تولیدی شهر فرش ایرانیان",
         "صورت‌های مالی  سال مالی منتهی به ۱۴۰۴/۱۲/۲۹ (حسابرسی شده) (شرکت داتیس نوین ایرانیان)",
         12, "1404/12/29", 191259093.0, 38180767.0, 1632924.0, 109.0),
        (1590682, "شهر " + Z + "فرش", "تولیدی شهر فرش ایرانیان",
         "صورت‌های مالی تلفیقی سال مالی منتهی به ۱۴۰۴/۱۲/۲۹ (حسابرسی شده)",
         12, "1404/12/29", 72287221.0, 27376608.0, 7640569.0, 382.0),
        (1591037, "شهر " + Z + "فرش", "تولیدی شهر فرش ایرانیان",
         "صورت‌های مالی تلفیقی سال مالی منتهی به ۱۴۰۳/۱۲/۳۰ (حسابرسی شده)",
         12, "1403/12/30", 56140426.0, 21384317.0, 9338809.0, 467.0),
        (1591214, "شهر " + Z + "فرش", "تولیدی شهر فرش ایرانیان",
         "صورت‌های مالی تلفیقی سال مالی منتهی به ۱۴۰۲/۱۲/۲۹ (حسابرسی شده)",
         12, "1402/12/29", 50000351.0, 18559389.0, 8960070.0, 448.0),
        # گزارشِ اصلاحیۀ همان دوره (تاریخچه می‌ماند، برنده عوض می‌شود)
        (1591215, "شهر " + Z + "فرش", "تولیدی شهر فرش ایرانیان",
         "صورت‌های مالی تلفیقی سال مالی منتهی به ۱۴۰۲/۱۲/۲۹ (حسابرسی شده)(اصلاحیه)",
         12, "1402/12/29", 50000351.0, 18900000.0, 8960070.0, 448.0),
        # دو گزارشِ مشروعِ یکِ دوره از یک شرکت (کامل‌تر برنده است)
        (1591300, "تولید " + Z + "الکتریک", "تولید الکتریک",
         "صورت‌های مالی سال مالی منتهی به ۱۴۰۳/۱۲/۲۹ (حسابرسی شده)",
         12, "1403/12/29", 1000.0, None, None, None),
        (1591301, "تولید " + Z + "الکتریک", "تولید الکتریک",
         "صورت‌های مالی سال مالی منتهی به ۱۴۰۳/۱۲/۲۹ (حسابرسی شده)",
         12, "1403/12/29", 1000.0, 400.0, 300.0, 50.0),
        # نوشتارهایِ عربیِ یک نماد (همان خانوادۀ داریک/داريك)
        (1591400, "داريك", "داریک", "صورت‌های مالی سال مالی منتهی به ۱۴۰۳/۱۲/۲۹ (حسابرسی شده)",
         12, "1403/12/29", 5000.0, 1500.0, 1200.0, 20.0),
        (1591401, "داریک", "داریک", "صورت‌های مالی سال مالی منتهی به ۱۴۰۲/۱۲/۲۹ (حسابرسی شده)",
         12, "1402/12/29", 4000.0, 1000.0, 900.0, 15.0),
        # چندنویشتاریِ نامِ شرکت برای یک نماد (ابهامِ هویت باید اعلام شود)
        (1591500, "احیا", "احیا استیل فولاد بافت",
         "صورت‌های مالی سال مالی منتهی به ۱۴۰۳/۱۲/۲۹ (حسابرسی شده)",
         12, "1403/12/29", 900.0, 200.0, 150.0, 10.0),
        (1591501, "احیا", "احیاء استیل فولاد بافت",
         "صورت‌های مالی سال مالی منتهی به ۱۴۰۲/۱۲/۲۹ (حسابرسی شده)",
         12, "1402/12/29", 800.0, 90.0, 70.0, 8.0),
    ]
    c.executemany("INSERT INTO financial_statements (tracing_no, symbol, company_name, "
                  "title, period_months, period_end, revenue, gross_profit, net_profit, "
                  "basic_eps) VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    c.execute("INSERT INTO monthly_sales (tracing_no, symbol, title, period_end, year, "
              "month, ytd_revenue) VALUES (1,'شهر فرش','گزارش فعالیت','1404/06/31',1404,6,10.0)")
    c.execute("INSERT INTO monthly_sales (tracing_no, symbol, title, period_end, year, "
              "month, ytd_revenue) VALUES (2,'شهر " + Z + "فرش','گزارش فعالیت','1404/03/31',"
              "1404,3,5.0)")
    inst = [("1", "شهر فرش061", "تولیدی شهر فرش ایرانیان", "IRO1SHFRA001", 4000000.0),
            ("2", "آباد3", "گردشگری آبادگران ایران", "IRO1ABAD0003", 11862388000.0),
            ("3", "آباد", "گردشگری آبادگران ایران", "IRO1ABAD0001", 11862388000.0),
            ("4", "خودرو2", "ایران خودرو", "IRO1IKCO0002", 2563746068000.0),
            ("5", "پا ر 2", "سرمایه‌گذاری پا ر", "IRE9P0D02001", 1000.0),
            ("6", "پا ر 5", "سرمایه‌گذاری پا ر", "IRE9P0D05001", 2000.0),
            ("7", "داریک", "داریک", "IRO1DARIK001", 10.0),
            ("8", "اراد275", "اوراق اراد", "IRB4O03001", 10.0),
            ("9", "اراد276", "اوراق اراد", "IRB4O03701", 10.0),
            ("10", "تازگی2", "تازگی", "IRO1TAZIG002", 5.0)]
    c.executemany("INSERT INTO instruments (ins_code, l_val18, l_val30, isin, total_shares) "
                  "VALUES (?,?,?,?,?)", inst)
    c.execute("INSERT INTO financial_statements (tracing_no, symbol, company_name, title, "
              "period_months, period_end, revenue, gross_profit) VALUES "
              "(900,'آباد','گردشگری آبادگران ایران','صورت‌های مالی سال مالی منتهی به "
              "۱۴۰۳/۱۲/۲۹ (حسابرسی شده)',12,'1403/12/29',700.0,300.0)")
    c.execute("INSERT INTO financial_statements (tracing_no, symbol, company_name, title, "
              "period_months, period_end, revenue, gross_profit) VALUES "
              "(901,'خودرو','ایران خودرو','صورت‌های مالی سال مالی منتهی به ۱۴۰۳/۱۲/۲۹ "
              "(حسابرسی شده)',12,'1403/12/29',8000.0,1200.0)")
    c.execute("INSERT INTO financial_statements (tracing_no, symbol, company_name, title, "
              "period_months, period_end, revenue, gross_profit) VALUES "
              "(902,'اراد','اوراق اراد','صورت‌های مالی سال مالی منتهی به ۱۴۰۳/۱۲/۲۹ "
              "(حسابرسی شده)',12,'1403/12/29',500.0,100.0)")
    par = c.execute("SELECT l_val18, l_val30 FROM instruments WHERE "
                    "isin='IRE9P0D02001'").fetchone()
    t902 = c.execute("SELECT title FROM financial_statements WHERE "
                     "tracing_no=902").fetchone()[0]
    c.execute("INSERT INTO financial_statements (tracing_no, symbol, company_name, "
              "title, period_months, period_end, revenue, gross_profit) "
              "VALUES (903,?,?,?,12,'1403/12/29',60.0,20.0)",
              (par[0][:-1].strip(), par[1], t902))
    for tn, sym in ((1, "شهر فرش"), (2, "آباد"), (3, "خودرو")):
        c.execute("INSERT INTO codal_notices (tracing_no, symbol, title, publish_date) "
                  "VALUES (?,?,'اطلاعیه','۱۴۰۵/۰۷/۰۱ ۱۰:۰۰:۰۰')", (1000 + tn, sym))
    c.execute("INSERT INTO price_history VALUES ('شهر فرش','2026/10/13',10.0)")
    c.commit()
    return c, path


def main() -> int:
    conn, path = make_db()
    try:
        section_layer(conn)
        section_paths(conn)
        section_regressions(conn)
    finally:
        conn.close()
        try:
            os.unlink(path)
        except OSError:
            pass
    section_ast()
    n_ok = sum(1 for ok, _ in CHECKS if ok)
    n_bad = len(CHECKS) - n_ok
    print("\nsymbol_identity_v1090: %d passed / %d failed" % (n_ok, n_bad))
    return 1 if n_bad else 0


# ── الف) قراردادِ لایه ─────────────────────────────────────────────────────
def section_layer(conn):
    Z = "‌"
    ck(SI.key("شهر" + Z + "فرش") == SI.key("شهر فرش"),
       "T1 کلید: نیم‌فاصله و فاصله هر دو بی‌اثرند")
    ck(SI.key("داريک") == SI.key("داریک") and SI.key("ك") == SI.key("ک"),
       "T1ب کلید: ي/ك/ى عربی با معادلِ فارسی یکی می‌شوند")
    ck(SI.key(None) == "" and SI.key("") == "",
       "T1پ ورودیِ تهی کلیدِ تهی می‌دهد (نه 'None')")

    v = SI.variants(conn, "شهر فرش")
    ck(set(v) == {"شهر فرش", "شهر " + Z + "فرش"}, "T2 نامزدها از خودِ بانک می‌آیند، نه از جایگشت", sorted(v))
    pred, params = SI.pred(conn, "symbol", "شهر فرش")
    n = conn.execute("SELECT COUNT(*) FROM financial_statements WHERE " + pred, params).fetchone()[0]
    ck(n == 5, "T3 کوئریِ تک‌نمادی هر پنج ردیفِ خانوادۀ «شهر فرش» را می‌بیند", n)

    # کنترلِ منفی ۱: نوشتاری که درِ بانک نیست نباید به‌عنوانِ نامزد ساخته شود
    ck("شهر  " + Z + "فرش" not in SI.variants(conn, "شهر فرش"),
       "T4 نامزدِ اختراعی ساخته نمی‌شود (فقط چیزی که بانک دارد)")
    ck(len(SI.variants(conn, "شهر فرش")) <= SI.MAX_VARIANTS,
       "T4ب شمارِ نامزدها کران‌دار است")

    # دامنه‌ها: پیشوندِ خطِ تابلو فقط درِ جهانِ کدال و فقط با شاهد
    ex, ev = SI.line_variants(conn, "آباد3")
    ck(ev == "isin-agree" and "آباد" in [str(x) for x in ex],
       "T5 پسوندهایِ یک‌رقمی با ISINِ هم‌قطار باز می‌شوند", (ex, ev))
    ex2, ev2 = SI.line_variants(conn, "پا ر 2")
    ck(ev2 == "isin-clash" and not ex2,
       "T6 دو ISINِ متفاوت ⇒ الحاق ممنوع (کنترلِ منفی)", (ex2, ev2))
    ex3, ev3 = SI.line_variants(conn, "اراد275")
    ck(not ex3 and ev3 == "exact",
       "T7 دنبالهٔ چندرقمی هرگز خرد نمی‌شود (اراد275 ≠ اراد)")
    exb, evb = SI.line_variants(conn, "خودرو2", SI.BOARD)
    ck(not exb and evb == "exact",
       "T8 درِ دامنهٔ تابلو پسوندِ رقمی هویتِ خودِ ابزار است؛ الحاق نمی‌شود")
    ck(SI.evidence(conn, "شهر فرش") == "same-key" and
       SI.evidence(conn, "پا ر 2") == "isin-clash" and
       SI.evidence(conn, "ZZZ9") == "unmatched",
       "T9 ردپا «الحاقِ ردشده» را از «بی‌نامزد» و «کلیدِ خود» جدا می‌کند")
    # خطِ «کلاس» درِ تابلو، جهتِ برعکسِ گیتِ ISIN (`پارتین` ← `پارتین2`)
    cs, evc = SI.class_siblings(conn, "پا ر")
    ck(not cs and evc == "ambiguous",
       "T19 دو خطِ کلاسِ بی‌شاهد ⇒ الحاق ممنوع و اعلام می‌شود", (cs, evc))
    cs2, evc2 = SI.class_siblings(conn, "تازگی")
    ck(set(cs2) == {"تازگی2"} and evc2 == "no-isin",
       "T19ب خطِ کلاسِ یکتا پذیرفته می‌شود، با ردپایِ بی‌شاهد", (cs2, evc2))
    cs3, evc3 = SI.class_siblings(conn, "آباد")
    ck(not cs3 and evc3 == "same-key",
       "T19پ خودِ پایه رویِ تابلو هست ⇒ الحاقِ خطِ کلاس لازم نیست", (cs3, evc3))
    st = SI.identity_stats(conn)
    ck(st["keys_with_multiple_spellings"] >= 2 and st["sources_codal"] and st["sources_board"],
       "T10 سرشماریِ خودِ لایه پرنشدنی است", st)
    # کنترلِ منفی ۴: `id(conn)` درِ CPython بازاستفاده می‌شود. اگر نقشۀِ یکِ اتصالِ
    # دیگر (مثلاً `codal.db` یا بانکِ آزمونِ حافظه) رویِ همین شماره بنشیند، لایه
    # باید آن را *دوباره بسازد*، نه اینکه ردیفِ بانکِ دیگر را به این نماد بچسباند.
    SI._CACHE[id(conn)] = {"conn": object(), "dv": conn.execute(
        "PRAGMA data_version").fetchone()[0], "by_key": {SI.key("شهر فرش"): [" جعلی"]},
        "by_key_board": {}, "isin": {}}
    vp = SI.variants(conn, "شهر فرش")
    ck("شهر فرش" in vp and "شهر " + Z + "فرش" in vp and " جعلی" not in vp,
       "T17 نقشۀِ بیگانه بی‌اعتبار می‌شود و از خودِ بانک بازسازی می‌گردد", sorted(vp))
    # کنترلِ منفی ۵: نوشتنِ **خودِ همین اتصال**. `PRAGMA data_version` با commitِ
    # همان connection تکان نمی‌خورد (سنجیده شد: بعد از INSERT همان ۱ ماند)، پس
    # سینکِ کدال یا هر نوشتِ تک‌اتصاله نقشۀ کهنه را نگه می‌داشت و نوشتارِ تازه هرگز
    # دیده نمی‌شد. سیگنالِ دوم `conn.total_changes` است. خانوادۀ «تازگی» ساخته
    # می‌شود — نه «شهر فرش» — تا شمارِ ردیف (T3) و سال‌هایِ پنجره (T12) و مرجعِ
    # سال (R5ب) دست‌نخورده بمانند؛ نوشتارِ دوم با ZWNJِ برنامۀ‌نوشته ساخته می‌شود
    # (دستِ تایپ، رقم و نویسه می‌دزدد).
    fam = "تازگی"
    fam2 = fam[:3] + Z + fam[3:]
    dv_before = conn.execute("PRAGMA data_version").fetchone()[0]
    v_before = SI.variants(conn, fam)
    conn.execute("INSERT INTO financial_statements (tracing_no, symbol, company_name, "
                 "title, period_months, period_end, revenue) VALUES (905,?,?,?,12,?,1.0)",
                 (fam2, fam, "صورت‌های مالی سال مالی منتهی به 1405/12/29",
                  "1405/12/29"))
    conn.commit()
    dv_after = conn.execute("PRAGMA data_version").fetchone()[0]
    v_after = SI.variants(conn, fam)
    ck(dv_before == dv_after and fam2 not in v_before and fam2 in v_after,
       "T21 نوشتنِ همین اتصال (بی‌تغییرِ data_version) در نقشۀ هویت دیده می‌شود",
       (dv_before, dv_after, sorted(v_before), sorted(v_after)))


# ── ب) هر دو مسیر، یک دید ──────────────────────────────────────────────────
def section_paths(conn):
    FE.register_sql(conn)
    for s in ("شهر فرش", "داریک", "احیا"):
        p_c, a_c = SI.pred(conn, "symbol", s)
        card = {r[0] for r in conn.execute(
            "SELECT tracing_no FROM financial_statements WHERE " + p_c, a_c)}
        bulk = {r[0] for r in conn.execute("SELECT tracing_no FROM financial_statements")}
        bulk = {t for t in bulk
                if SI.key(conn.execute("SELECT symbol FROM financial_statements WHERE tracing_no=?",
                                       (t,)).fetchone()[0]) in
                {SI.key(x) for x in a_c}}
        ck(card == bulk, "T11 کارت و قیف یک دستۀ ردیف می‌بینند: " + s,
           "card=%d bulk=%d" % (len(card), len(bulk)))
    # مسیرِ واقعیِ موتور هم باید همان ردیف‌ها را ببیند
    ann = FE.annual_statements(conn, "شهر فرش", require_audit=False,
                               exclude_consolidated=False, limit=12)
    ck(len(ann) == 3 and {r["fiscal_year"] for r in ann} == {"1402", "1403", "1404"},
       "T12 پنجرۀ سالانۀ کارت سه سالِ مالیِ خانوادۀ «شهر فرش» را دارد (یکی به ازای سال)",
       [(r["fiscal_year"], r["tracing_no"]) for r in ann])
    # ردیفِ «شرکتِ دیگر» نباید صورتِ مالیِ خودِ نماد را از سبدِ همان سال بیرون بیندازد
    ck(any(r["tracing_no"] == 1590682 and r["fiscal_year"] == "1404" for r in ann) and
       not any(r["tracing_no"] == 1604925 for r in ann),
       "T12ب ردیفِ شرکتِ فرعی، ردیفِ خودِ نماد را در ۱۴۰۴ حذف نمی‌کند",
       [(r["fiscal_year"], r["tracing_no"]) for r in ann])


# ── ج) پرونده‌هایِ رگرسیونِ مرحلۀ 1.2 ──────────────────────────────────────
def section_regressions(conn):
    Z = "‌"
    # ۱) نیم‌فاصله
    ck(SI.key("شهر" + Z + "فرش") == SI.key("شهر فرش"),
       "R1 شهر فرش: دو نوشتار، یک هویت")
    # ۲/۳) شرکتِ فرعی و اصلاحیه
    ref = FE.reference_annual(conn, "شهر فرش")
    ck(ref and ref["tracing_no"] != 1604925,
       "R2 ردیفِ «شرکت داتیس نوین ایرانیان» (شرکتِ دیگر) مرجع نمی‌شود",
       (ref or {}).get("tracing_no"))
    ck(any(t[0] == 1604925 for t in conn.execute(
        "SELECT tracing_no FROM financial_statements WHERE symbol LIKE '%فرش%'")),
       "R3 همان ردیف درِ تاریخچه باقی می‌ماند (حذف نمی‌شود)")
    am = [r[0] for r in conn.execute(
        "SELECT tracing_no FROM financial_statements WHERE title LIKE '%اصلاحیه%'")]
    ck(bool(am), "R4 گزارشِ اصلاحیۀ همان دوره درِ بانک هست (تاریخچه نه، حذف)", am)
    ann2 = FE.annual_statements(conn, "شهر " + Z + "فرش",
                                require_audit=False,
                                exclude_consolidated=False, limit=12)
    y1402 = [r for r in ann2 if r["fiscal_year"] == "1402"]
    ck(len(y1402) == 1 and y1402[0]["tracing_no"] == 1591215,
       "R5 در دورۀ ۱۴۰۲ اصلاحیه بر نسخۀ پیشین می‌برد (تاریخچه حفظ، انتخاب عوض)",
       [r["tracing_no"] for r in y1402])
    win = FE.pick_reference(ann2)
    ck(win and win["fiscal_year"] == "1404" and not win["other_entity"],
       "R5ب مرجع، آخرین سالِ مالیِ خودِ نماد است نه ردیفِ شرکتِ دیگر",
       (win or {}).get("tracing_no"))
    # ۵) تلفیقی در برابرِ اصلی
    two = FE.pick_reference([
        {"period_months": 12, "fiscal_year": "1403", "tracing_no": 1591300,
         "title": "تلفیقی", "audited": True, "consolidated": True, "other_entity": False,
         "revenue": 1000.0, "gross_profit": None, "net_profit": None, "basic_eps": None,
         "company_name": "تولید الکتریک", "period_end": "1403/12/29"},
        {"period_months": 12, "fiscal_year": "1403", "tracing_no": 1591301,
         "title": "اصلی", "audited": True, "consolidated": False, "other_entity": False,
         "revenue": 1000.0, "gross_profit": 400.0, "net_profit": 300.0, "basic_eps": 50.0,
         "company_name": "تولید الکتریک", "period_end": "1403/12/29"}])
    ck(two and two["tracing_no"] == 1591301,
       "R6 غیرتلفیقیِ کامل بر تلفیقی می‌برد", (two or {}).get("tracing_no"))
    # ۷) نوشتارهایِ متفاوتِ نامِ شرکت + ۶) نمادی با چند نام
    ident = FE.reference_identity(FE.annual_statements(conn, "احیا", require_audit=False,
                                                       exclude_consolidated=False, limit=12),
                                  FE.reference_annual(conn, "احیا") or {})
    ck(ident["checked"] is True and ident["match"] is False and "احیا" in (ident["reason"] or ""),
       "R7 ابهامِ هویت (احیا/احیاء) اعلام می‌شود، نه خاموش رد", ident)
    # ۸) عنوان/شرکت/دوره/نمادِ ناهمخوان
    tit = FE.title_entity_suffix("صورت‌های مالی سال مالی منتهی به ۱۴۰۴/۱۲/۲۹ "
                                 "(حسابرسی شده) (شرکت داتیس نوین ایرانیان)")
    ck(bool(tit) and "داتیس" in tit, "R8_SUFFIX عنوانِ شرکتِ دیگر از عنوانِ نامه خوانده می‌شود", tit)
    for t, why in (("صورت‌های مالی شامل مقادیر برآوردی", "R9 برچسبِ «برآوردی» شرکتِ دیگر نیست"),
                   ("صورت‌های مالی (شرکت اصلی) سال 1403", "R9ب «شرکت اصلی» یعنی خودِ صادرکننده"),
                   ("اطلاعیهٔ عادی بدونِ برچسب", "R9پ بی‌برچسب ⇒ شرکتِ دیگر شمرده نمی‌شود")):
        ck(not FE.title_entity_suffix(t), why)
    # ۱۰) ردیفی که «منتهی به»اش با دورۀ ستون، یا «X ماهه»اش با period_months نمی‌خواند:
    # تناقض **اعلام** می‌شود (نه رأیِ جدید، نه حذفِ خاموش). رقمِ عنوان عمداً با
    # translate ساخته می‌شود — دست‌نوشتِ فارسی رقم را می‌دزدد.
    FAD = str.maketrans("0123456789", "".join(chr(0x06F0 + d) for d in range(10)))
    t_mixed = ("اطلاعات و صورت‌های مالی میاندوره‌ای دوره 6 ماهه منتهی به 1403/06/31 "
               "(حسابرسی نشده)").translate(FAD)
    ck(FE.row_conflicts("1403/12/29", t_mixed, 12) == ["title_period", "title_months"],
       "R12 تناقضِ عنوان⇄ستون (دوره و ماه) رویِ ردیف برچسب می‌گیرد",
       FE.row_conflicts("1403/12/29", t_mixed, 12))
    t_clean = ("صورت‌های مالی سال مالی منتهی به 1403/12/29 (حسابرسی شده)").translate(FAD)
    ck(FE.row_conflicts("1403/12/29", t_clean, 12) == [],
       "R12پ ردیفِ هم‌خوان هیچ برچسبی نمی‌گیرد (کنترلِ مثبتِ سنسور)")
    ck(FE.row_conflicts("1403/12/29", t_mixed, None) == ["title_period"],
       "R12ت بی‌period_months داوری نمی‌کند — فقط همان تناقضِ قطعی اعلام می‌شود",
       FE.row_conflicts("1403/12/29", t_mixed, None))
    ident_c = FE.reference_identity([{"company_name": "الف", "conflicts": []}],
                                    {"company_name": "الف", "conflicts": ["title_months"]})
    ck(ident_c["checked"] is True and ident_c["match"] is True
       and ident_c["conflicts"] == ["title_months"] and "ماه" in ident_c["conflict_note"],
       "R12ج ردپایِ انتخابِ مرجع تناقض را هم حمل می‌کند (رأیِ هویت را عوض نمی‌کند)",
       ident_c)
    # ۱۱) نردبانِ شاخص ۲ هم باید همان قاعدۀ «شرکتِ دیگر» را ببیند: این reader
    # پنجم بود و پرچم را نمی‌دید — درِ بانکِ واقعی دقیقاً «شهر فرش» را می‌گرفت
    # (EPS ۱۴۰۴ از ردیفِ «شرکت داتیس نوین ایرانیان» در برابرِ EPSِ خودِ نماد).
    lad = FE.eps_ladder(conn, "شهر فرش", years=3)
    ck("1404" in (lad.get("fiscal_years") or []) and 382.0 in (lad.get("eps_series") or [])
       and 109.0 not in (lad.get("eps_series") or []),
       "R13 نردبانِ EPS هم سودِ شرکتِ دیگر را به این نماد نمی‌چسباند",
       (lad.get("eps_series"), lad.get("fiscal_years"), lad.get("evidence")))
    ck(lad.get("consolidated_used") is True and (lad.get("evidence") or [])[-1]
       == "consolidated_audited",
       "R13ب تنزلِ شاخص ۲ به تلفیقیِ خودِ نماد **اعلام** می‌ماند، نه پنهان",
       (lad.get("evidence"), lad.get("relaxed_evidence")))
    # P-2 (بندِ ۲.۳ مأموریت/سیاست): شرطِ «غیرتلفیقی» مالِ شاخص ۲ است. حاشیهٔ سود
    # نباید به‌خاطرِ آن شرط، سالی را که هر دو عددش درِ بانک هست دور بریزد — این
    # دقیقاً علتِ «بی‌داده» شدنِ `وكادو` و `سيتا` بود (سنجش: tn=1391011 با
    # ۱۰٬۶۷۷٬۸۷۵ ÷ ۳۶٬۰۸۳٬۶۱۷ در برابرِ tn=1224928 بی‌سودِ ناخالص).
    mix = [
        {"period_months": 12, "fiscal_year": "1404", "tracing_no": 1, "title": "اصلی",
         "audited": True, "consolidated": False, "other_entity": False, "conflicts": [],
         "revenue": 100.0, "gross_profit": None, "operating_profit": None,
         "net_profit": None, "basic_eps": None, "company_name": "الف",
         "period_end": "1404/12/29"},
        {"period_months": 12, "fiscal_year": "1403", "tracing_no": 2, "title": "تلفیقی",
         "audited": True, "consolidated": True, "other_entity": False, "conflicts": [],
         "revenue": 360.0, "gross_profit": 106.0, "operating_profit": 90.0,
         "net_profit": 70.0, "basic_eps": 5.0, "company_name": "الف",
         "period_end": "1403/12/30"},
    ]
    plain = FE.pick_reference(mix)
    ck(bool(plain) and plain["tracing_no"] == 1,
       "R15 پلکانِ عمومی همان سالانۀ غیرتلفیقی را می‌گزیند (رفتارِ پیشین)",
       (plain or {}).get("tracing_no"))
    mneed = FE.pick_reference(mix, need=FE.MARGIN_NEED)
    ck(bool(mneed) and mneed["tracing_no"] == 2,
       "R15ب شاخص ۳ ردیفی را می‌گزیند که سودِ ناخالص و درآمد دارد",
       (mneed or {}).get("tracing_no"))
    only = FE.pick_reference([mix[0]], need=FE.MARGIN_NEED)
    ck(bool(only) and only["tracing_no"] == 1,
       "R15پ اگر هیچ ردیفی عدد نداشته باشد، مرجع هم نمی‌پرد و None نمی‌شود",
       (only or {}).get("tracing_no"))
    ck(FE.row_carries(mix[0], FE.MARGIN_NEED) is False and
       FE.row_carries(mix[1], FE.MARGIN_NEED) is True,
       "R15ت سنجهٔ «توانِ محاسبه» صفرِ جعلی نمی‌سازد (None ≠ ۰)")
    # کنترلِ منفی ۲: اگر روزی پرچمِ other_entity درِ پلکان سالانه نادیده گرفته شود
    one = FE.pick_reference([
        {"period_months": 12, "fiscal_year": "1404", "tracing_no": 1,
         "title": "x (شرکت دیگری)", "audited": True, "consolidated": False,
         "other_entity": True, "revenue": 9.0, "gross_profit": 8.0, "net_profit": 7.0,
         "basic_eps": 6.0, "company_name": "الف", "period_end": "1404/12/29"}])
    ck(one is None, "R10 تنها ردیفِ «شرکتِ دیگر» مرجع نمی‌شود (کنترلِ منفیِ پلکان)", one)
    # کنترلِ منفی ۳: کلیدِ دوم اگر برگردد، سنسور باید ببیند
    ck(SI.key("شهر " + Z + "فرش") == SI.key("شهرفرش"),
       "R11 فاصله و نیم‌فاصله هر دو حذف می‌شوند (اگر یکی برگردد، این قرمز می‌شود)")


# ── د) هیچ تعریفِ دومی نماند (AST، نه grep) ────────────────────────────────
BANNED_CALLS = ("symbol_aliases",)
PROD = ("fts_engine.py", "api/fundamental.py", "api/chart.py", "api/screener.py",
        "api/selection.py", "api/_core.py", "confidence_engine.py", "codal_fetcher.py")


def section_ast():
    # حلقه‌هایِ AST «بی‌مصرف» می‌شوند اگر فایلِ مصرف‌کننده جابه‌یا حذف شود
    # (`continue` رویِ isfile). پس اولِ کار حضورِ تک‌تکِ فایل‌ها assert می‌شود:
    # یکِ rename نباید چک‌هایِ ضدِ کلیدِ دوم را بی‌صدا سبز کند.
    gone = [rel for rel in PROD if not os.path.isfile(os.path.join(ROOT, rel))]
    ck(not gone, "T18 هر مصرف‌کنندۀ فهرست‌شده درِ مخزن هست (AST بی‌فایل کور می‌شود)",
       gone[:4])
    offenders = []
    for rel in PROD:
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            continue
        tree = ast.parse(io.open(p, encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in BANNED_CALLS:
                offenders.append("%s:%d %s" % (rel, node.lineno, node.attr))
            if isinstance(node, ast.Name) and node.id in BANNED_CALLS:
                offenders.append("%s:%d %s" % (rel, node.lineno, node.id))
            if isinstance(node, ast.FunctionDef) and node.name in BANNED_CALLS:
                offenders.append("%s:%d def %s" % (rel, node.lineno, node.name))
    ck(not offenders, "T16 هیچ مصرف‌کننده‌ای جایگشتِ نویسه (symbol_aliases) را صدا نمی‌زند",
       offenders[:4])

    # نماد را با تابعِ SQLِ *دیگر* کلید نزنند: sym_key باید همان SI.key باشد
    bad_sql = []
    for rel in PROD:
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            continue
        src = io.open(p, encoding="utf-8").read()
        for m in ("REPLACE(REPLACE(REPLACE(", "norm_fa(i.l_val18)", "norm_fa(symbol)",
                  "norm_fa(l_val18)"):
            if m in src:
                bad_sql.append("%s: %s" % (rel, m))
    ck(not bad_sql, "T13 هیچ زنجیرۀ REPLACE/نرمال‌سازِ دوم روی ستونِ نماد نمانده است",
       bad_sql[:4])

    # sym_in/sym_pred همه جا conn می‌دهند (بی‌بانک نمی‌شود نامزد را دانست)
    missing = []
    for rel in PROD + ("dev/codal_reference_select_v1088.py",):
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            continue
        tree = ast.parse(io.open(p, encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = ast.unparse(node.func)
                if fn.endswith(("sym_in", "sym_pred")) and len(node.args) < 3:
                    missing.append("%s:%d" % (rel, node.lineno))
    ck(not missing, "T14 هر فراخوانِ تطبیقِ نماد، اتصال را هم می‌دهد", missing[:4])

    # کنترلِ سنسور: اگر فایلِ لایه حذف/خالی شود، خودِ این گارد قرمز می‌شود
    ck(os.path.isfile(os.path.join(ROOT, "symbol_identity.py")) and
       os.path.getsize(os.path.join(ROOT, "symbol_identity.py")) > 4000,
       "T15 لایۀ هویت موجود است و خالی نیست")


if __name__ == "__main__":
    sys.exit(main())
