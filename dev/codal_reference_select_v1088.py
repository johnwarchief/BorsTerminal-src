#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/codal_reference_select_v1088.py — گاردِ CA-2: «کدام ردیف نمایندهٔ این دوره است».

چرا (ممیزی CODAL دور ۲، ۱۴۰۵-۰۷-۲۰): `/api/fundamental/{symbol}/quarters` ردیفِ
هر دوره را با `ORDER BY period_end DESC, publish_date DESC LIMIT ?` و «اولینِ
هر کلید» برمی‌گزید. `publish_date` درِ همین بانک مخلوطِ رقمِ فارسی (U+06F0..) و
لاتین است و قفسۀ فارسی در مقایسۀ واژگانی **بعد** از لاتین می‌آید ⇒ ردیفِ
کهنه‌تر «تازۀ‌ترین» خوانده می‌شد؛ و `LIMIT` پیش از حذفِ تکراری اعمال می‌شد ⇒
دوره‌هایِ واقعی کم می‌آمدند. سنجشِ بانکِ کاری (.tools/codal_record_identity_probe.py):
۲۰۷ اسلوتِ چندردیفی، ۵۰ جابه‌جایی به‌سببِ رقم، ۹۲ جابه‌جایی در برابرِ قاعدۀ
یگانۀ پروژه، ۳۷ اسلوت با **عددِ عوض‌شده** (۳۵ نماد).

اصلاح: انتخابِ برنده با همان `fts_engine.statement_rank` (غیرتلفیقی ← کامل‌ترین
← newest `tracing_no`) — همان قاعدۀ `annual_statements`/`pick_reference` (موتور
قیف) و `codal_fetcher.period_winners` (نویسنده). no parser دوم، no آستانۀ دوم.

این گارد دو چیز را با هم الزامی می‌کند (نه فقط «جواب درست»):
  الف) **انتخابِ درست** در هشت سناریو (شاملِ کنترلِ منفی: الگوریتمِ کهنه روی
     همان داده جوابِ دیگری می‌دهد، پس سنسور کور نیست)؛
  ب) **حفظِ رکوردهایِ مستقل** — ردیفِ بازنده از بانک حذف نمی‌شود و دو نوعِ
     بیانِ متفاوت (pm=3 و pm=6) هر دو می‌مانند.

اجرا:  python dev/codal_reference_select_v1088.py     (خروج ۰ = سبز، ۱ = رد)
"""
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import codal_fetcher as CF                                  # noqa: E402
import codal_periods as CP                                  # noqa: E402
import fts_engine as FE                                     # noqa: E402
import api.fundamental as fundamental                       # noqa: E402

PASS = FAIL = 0
_FA_DIGITS = str.maketrans("0123456789", "".join(chr(0x06F0 + d) for d in range(10)))


def fa(s):
    """همان تاریخِ لاتین با رقمِ فارسی — برایِ ثابتِ کردنِ بی‌اثریِ نوشتار."""
    return str(s).translate(_FA_DIGITS)


def chk(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("  FAIL  %s   %s" % (label, extra))


def fs_row(tracing_no, symbol, title, period_end, period_months, publish_date,
           company_name="شرکت آزمون", revenue=None, gross_profit=None,
           net_profit=None, basic_eps=None, operating_profit=None,
           total_assets=None, total_equity=None, capital=None):
    """ردیفِ موقعیتیِ `FS_UPSERT` از رویِ **نامِ** ستون‌ها (نه حدسِ ترتیب)."""
    vals = {
        "tracing_no": tracing_no, "symbol": symbol, "company_name": company_name,
        "title": title, "report_kind": "Financial Statements",
        "period_months": period_months, "period_end": period_end,
        "publish_date": publish_date, "revenue": revenue,
        "gross_profit": gross_profit, "operating_profit": operating_profit,
        "net_profit": net_profit, "total_assets": total_assets,
        "total_liabilities": None, "total_equity": total_equity,
        "capital": capital, "retained_earnings": None, "basic_eps": basic_eps,
        "unit": "mrl", "url": "https://codal.ir/%d" % tracing_no,
        "fetched_at": "2026-10-12T00:00:00",
    }
    vals.update(dict(zip(("is_audited", "is_consolidated", "fiscal_year", "unit_norm"),
                         CF.fs_derived(title, period_end, "mrl"))))
    return [vals.get(c) for c in CF.FS_COLS]


class Bank:
    """بانکِ موقتِ کوچک با schemaِ واقعیِ خودِ `codal_fetcher.create_schema`."""

    def __init__(self, rows):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        c = sqlite3.connect(self.path)
        CF.create_schema(c)
        CF.migrate_schema(c)      # همان زنجیرۀ واقعی: DDL + ستون‌هایِ افزوده
        c.executemany(CF.FS_UPSERT, rows)
        c.executemany("INSERT OR REPLACE INTO codal_notices (tracing_no, symbol,"
                      " company_name, title, publish_date) VALUES (?,?,?,?,?)",
                      [(r[CF.FS_COLS.index("tracing_no")],
                        r[CF.FS_COLS.index("symbol")],
                        r[CF.FS_COLS.index("company_name")],
                        r[CF.FS_COLS.index("title")],
                        r[CF.FS_COLS.index("publish_date")]) for r in rows])
        c.commit()
        c.close()

    def connect(self):
        c = sqlite3.connect(self.path, timeout=15)
        c.row_factory = sqlite3.Row
        return c

    def all_rows(self):
        c = self.connect()
        try:
            return [dict(r) for r in c.execute(
                "SELECT tracing_no, symbol, title, period_end, period_months,"
                " publish_date FROM financial_statements ORDER BY tracing_no")]
        finally:
            c.close()

    def close(self):
        try:
            os.remove(self.path)
        except OSError:
            pass


def quarters(bank, symbol, limit=16):
    """فراخوانِ واقعیِ اندپوینت (نه تقلیدِ آن) با get_dbِ وصل‌شده به بانکِ موقت."""
    orig = fundamental.get_db
    fundamental.get_db = bank.connect
    try:
        return fundamental.get_fundamental_quarters(symbol, limit=limit)
    finally:
        fundamental.get_db = orig


def legacy_pick(bank, symbol, period_end, period_months):
    """الگوریتمِ **کهنه** (قبلِ اصلاح) — فقط برایِ کنترلِ منفی: ثابت کند سنسور
    این حالت را می‌بیند و سبزیِ تست از کور بودنِ تست نیامده است."""
    c = bank.connect()
    pred, params = FE.sym_in(c, "symbol", symbol)
    try:
        raw = c.execute(
            "SELECT period_end, period_months, tracing_no FROM financial_statements"
            " WHERE %s AND %s ORDER BY period_end DESC, publish_date DESC LIMIT ?"
            % (pred, CP.DATED_SQL), (*params, 40)).fetchall()
        for r in raw:
            if r["period_end"] == period_end and r["period_months"] == period_months:
                return r["tracing_no"]
        return None
    finally:
        c.close()


def picked(payload, period_end, period_months):
    for q in payload.get("quarters", []):
        if q["period_end"] == period_end and q["period_months"] == period_months:
            return q
    return None


# ═══════════════════════════════════════════════════════════════════════════
PE = "1404/12/29"
T_MAIN = "صورت‌های مالی  سال مالی منتهی به ۱۴۰۴/۱۲/۲۹ (حسابرسی شده)"
T_CONS = "صورت‌های مالی تلفیقی سال مالی منتهی به ۱۴۰۴/۱۲/۲۹ (حسابرسی شده)"
T_AMEND = "صورت‌های مالی  سال مالی منتهی به ۱۴۰۴/۱۲/۲۹ (حسابرسی شده)(اصلاحیه)"


def t1_script_independent():
    # ── ۱) نوشتارِ رقم نباید جواب را عوض کند (هر دو جهت) ────────────────────
    # دو ردیفِ هم‌مبنا، هم‌طولِ دوره، با کامل‌بودنِ یکسان؛ تنها «کدِ رقمِ
    # publish_date» بینِ دو واریانت جابه‌جا می‌شود. قاعدۀ پروژه (تساوی‌شکنِ
    # newest tracing_no) در هر دو واریانت ردیفِ ۲۰ را می‌خواهد؛ الگوریتمِ
    # کهنه واژگانی، وقتی رقمِ فارسی رویِ ردیفِ ۱۰ است، ردیفِ ۱۰ را برنده می‌کند.
    variants = {
        "fa-on-20": {"10": "1405/05/01 10:00:00", "20": fa("1405/07/01 10:00:00")},
        "fa-on-10": {"10": fa("1405/05/01 10:00:00"), "20": "1405/07/01 10:00:00"},
    }
    for label, pubs in variants.items():
        b = Bank([
            fs_row(10, symbol="ثابت", title=T_MAIN, period_end=PE, period_months=12,
                   publish_date=pubs["10"], revenue=10.0, gross_profit=4.0,
                   net_profit=2.0, basic_eps=0.5),
            fs_row(20, symbol="ثابت", title=T_MAIN, period_end=PE, period_months=12,
                   publish_date=pubs["20"], revenue=20.0, gross_profit=8.0,
                   net_profit=4.0, basic_eps=1.0),
        ])
        try:
            got = picked(quarters(b, "ثابت"), PE, 12)
            chk(got is not None and got["revenue"] == 20.0,
                "۱%s برنده با قاعدۀ یگانه (newest tracing_no)، بی‌وابستگی از رقم" % label,
                str(got))
            expected_legacy = 20 if label == "fa-on-20" else 10
            chk(legacy_pick(b, "ثابت", PE, 12) == expected_legacy,
                "۱%s کنترلِ منفی: کهنه با جابه‌جاییِ رقم عوض می‌شود "
                "(انتظار=%d)" % (label, expected_legacy),
                "legacy=%s" % legacy_pick(b, "ثابت", PE, 12))
            chk(len(b.all_rows()) == 2, "۱%s هر دو ردیف در بانک می‌مانند" % label)
        finally:
            b.close()


def t2_same_date_two_notices():
    # ── ۲) یکِ publish_date، دوِ اطلاعیه ⇒ تساوی‌شکنِ پایدار (tracing_no) ─────
    pub = "1405/06/01 12:00:00"
    for order in (1, 2):     # ترتیبِ فیزیکیِ درج نباید جواب را عوض کند
        rows = [fs_row(30, symbol="تساوی", title=T_MAIN, period_end=PE,
                       period_months=12, publish_date=pub, revenue=10.0,
                       gross_profit=4.0, net_profit=1.0, basic_eps=0.5),
                fs_row(31, symbol="تساوی", title=T_AMEND, period_end=PE,
                       period_months=12, publish_date=pub, revenue=11.0,
                       gross_profit=5.0, net_profit=2.0, basic_eps=0.6)]
        if order == 2:
            rows.reverse()
        b = Bank(rows)
        try:
            got = picked(quarters(b, "تساوی"), PE, 12)
            chk(got["revenue"] == 11.0,
                "۲ درِ تساویِ تاریخ، newest tracing_no برنده است (ترتیب درج: %d)" % order)
            chk(len(b.all_rows()) == 2,
                "۲ ردیفِ بازنده از بانک حذف نشده", str(len(b.all_rows())))
        finally:
            b.close()


def t3_main_beats_consolidated():
    # ── ۳) اصلی در برابرِ تلفیقیِ همان دوره ────────────────────────────────
    b = Bank([
        fs_row(40, symbol="مبنا", title=T_CONS, period_end=PE, period_months=12,
               publish_date="1405/06/10 09:00:00", revenue=900.0, gross_profit=100.0,
               net_profit=50.0, basic_eps=5.0),
        fs_row(41, symbol="مبنا", title=T_MAIN, period_end=PE, period_months=12,
               publish_date="1405/05/10 09:00:00", revenue=100.0, gross_profit=40.0,
               net_profit=20.0, basic_eps=2.0),
    ])
    try:
        got = picked(quarters(b, "مبنا"), PE, 12)
        chk(got["revenue"] == 100.0,
            "۳ ردیفِ غیرتلفیقی (مبنایِ جزوه) برنده است حتی اگر کهنه‌تر باشد", str(got))
        chk(legacy_pick(b, "مبنا", PE, 12) == 40,
            "۳ کنترلِ منفی: کهنه بر پایهٔ تاریخِ انتشار تلفیقی را می‌گزید")
        rows = b.all_rows()
        chk(len(rows) == 2 and any("تلفیقی" in (r["title"] or "") for r in rows),
            "۳ ردیفِ تلفیقی در بانک **حفظ** شد (اینجا فقط از سریِ فصلی کنار می‌رود)")
    finally:
        b.close()


def t4_different_statement_types():
    # ── ۴) دو نوعِ گزارش برایِ یکِ دوره ⇒ ادغام نمی‌شوند ────────────────────
    b = Bank([
        fs_row(50, symbol="دونوع", title="اطلاعات و صورت‌های مالی میاندوره‌ای دوره ۳ ماهه منتهی به  ۱۴۰۵/۰۳/۳۱ (حسابرسی نشده)",
               period_end="1405/03/31", period_months=3,
               publish_date="1405/04/28 09:00:00", revenue=10.0, gross_profit=5.0,
               net_profit=1.0, basic_eps=0.1),
        fs_row(51, symbol="دونوع", title="اطلاعات و صورت‌های مالی میاندوره‌ای دوره ۶ ماهه منتهی به  ۱۴۰۵/۰۳/۳۱ (حسابرسی شده)",
               period_end="1405/03/31", period_months=6,
               publish_date="1405/05/28 09:00:00", revenue=20.0, gross_profit=9.0,
               net_profit=3.0, basic_eps=0.3),
    ])
    try:
        payload = quarters(b, "دونوع")
        chk(payload["count"] == 2, "۴ هر دو نوعِ گزارش در پاسخ هست", str(payload["count"]))
        chk(picked(payload, "1405/03/31", 3)["revenue"] == 10.0
            and picked(payload, "1405/03/31", 6)["revenue"] == 20.0,
            "۴ ادغامِ بینِ period_months اتفاق نیفتاده")
        chk(len(b.all_rows()) == 2, "۴ ردیف‌ها در بانک دست‌نخورده‌اند")
    finally:
        b.close()


def t5_undated_rows():
    # ── ۵) تاریخِ نامعتبر/غایب ⇒ بی‌دوره؛ از سریِ فصلی بیرون، از بانک بیرون نه ─
    b = Bank([
        fs_row(60, symbol="بیدوره", title=T_MAIN, period_end=PE, period_months=12,
               publish_date="1405/05/01 10:00:00", revenue=100.0, gross_profit=40.0,
               net_profit=20.0, basic_eps=2.0),
        fs_row(61, symbol="بیدوره", title=T_MAIN, period_end=None, period_months=12,
               publish_date="1405/05/02 10:00:00", revenue=700.0, gross_profit=1.0,
               net_profit=1.0, basic_eps=1.0),
        fs_row(62, symbol="بیدوره", title=T_MAIN, period_end=fa("1404/12/29"),
               period_months=12, publish_date="1405/05/03 10:00:00", revenue=800.0,
               gross_profit=1.0, net_profit=1.0, basic_eps=1.0),
        fs_row(63, symbol="بیدوره", title=T_MAIN, period_end="1404-12-29",
               period_months=12, publish_date="1405/05/04 10:00:00", revenue=900.0,
               gross_profit=1.0, net_profit=1.0, basic_eps=1.0),
    ])
    try:
        payload = quarters(b, "بیدوره")
        chk(payload["count"] == 1 and payload["quarters"][0]["revenue"] == 100.0,
            "۵ فقط ردیفِ canonical در سری می‌آید (بی‌دوره و غیرcanonical بیرون)",
            str(payload["count"]))
        chk(len(b.all_rows()) == 4,
            "۵ هر چهار ردیف در بانک **مانده‌اند** (بی‌دوره حذف نمی‌شود)")
    finally:
        b.close()


def t6_limit_after_dedupe():
    # ── ۶) LIMIT بعدِ dedupe ⇒ دوره‌ها کم نمی‌آیند ──────────────────────────
    periods = ["140%d/12/29" % i for i in range(1, 5)]
    rows = []
    tno = 70
    for pe in periods:
        for _dup in range(3):        # هر دوره سه ردیفِ هم‌مبنایِ کامل
            rows.append(fs_row(tno, symbol="سقف", title=T_MAIN, period_end=pe,
                               period_months=12,
                               publish_date="1405/06/01 10:00:0%d" % (_dup + 1),
                               revenue=float(tno), gross_profit=1.0, net_profit=1.0,
                               basic_eps=1.0))
            tno += 1
    b = Bank(rows)
    try:
        payload = quarters(b, "سقف", limit=4)
        pes = {q["period_end"] for q in payload["quarters"]}
        chk(pes == set(periods),
            "۶ با limit=۴ هر چهار دوره برگردانده می‌شود (نه کمتر)", str(sorted(pes)))
        chk(len(b.all_rows()) == 12, "۶ ردیف‌هایِ بازنده حذف نشده‌اند")
    finally:
        b.close()


def t7_stability_and_shape():
    # ── ۷) پاسخِ تکراری پایدار است + شکلِ payload دست‌نخورده ────────────────
    b = Bank([
        fs_row(80, symbol="پایدار", title=T_CONS, period_end=PE, period_months=12,
               publish_date=fa("1405/06/09 09:00:00"), revenue=900.0, gross_profit=100.0,
               net_profit=50.0, basic_eps=5.0),
        fs_row(81, symbol="پایدار", title=T_MAIN, period_end=PE, period_months=12,
               publish_date="1405/06/10 09:00:00", revenue=100.0, gross_profit=40.0,
               net_profit=20.0, basic_eps=2.0),
        fs_row(82, symbol="پایدار", title=T_MAIN, period_end=PE, period_months=9,
               publish_date="1405/06/11 09:00:00", revenue=70.0, gross_profit=30.0,
               net_profit=15.0, basic_eps=1.5),
    ])
    try:
        import json as _json
        a = _json.dumps(quarters(b, "پایدار"), sort_keys=True, ensure_ascii=False)
        for _ in range(3):
            chk(_json.dumps(quarters(b, "پایدار"), sort_keys=True,
                            ensure_ascii=False) == a, "۷ پاسخ در فراخوان‌هایِ پیاپی یکسان")
        q0 = quarters(b, "پایدار")["quarters"][0]
        chk(set(q0.keys()) == {"period_end", "period_months", "revenue",
                               "gross_profit", "operating_profit", "net_profit",
                               "basic_eps", "publish_date"},
            "۷ هشت کلیدِ قرارداد حفظ شده (title/tracing_no نشت نمی‌کند)", str(set(q0.keys())))
        chk(len(b.all_rows()) == 3, "۷ هیچ ردیفی له نشده")
    finally:
        b.close()


def t8_real_bank_spot_check():
    """سنجشِ سراسریِ همان قاعده رویِ بانکِ کاری (فقط‌خواندنی). نبودش در CI ⇒ SKIPِ صریح."""
    db = os.path.join(ROOT, "market.db")
    if not os.path.isfile(db):
        print("SKIP  ۸ بانکِ کاری نبود — سنجشِ رویِ دادهٔ واقعی خوانده نشد")
        return
    uri = "file:%s?mode=ro" % db.replace("\\", "/")

    def ro():
        c = sqlite3.connect(uri, uri=True, timeout=30)
        c.row_factory = sqlite3.Row
        return c

    orig = fundamental.get_db
    fundamental.get_db = ro
    slots = 0
    mismatch = 0
    legacy_rows_moved = 0
    legacy_numbers_moved = 0
    try:
        conn = ro()
        try:
            syms = [r["symbol"] for r in conn.execute(
                "SELECT symbol FROM financial_statements WHERE " + CP.DATED_SQL +
                " GROUP BY symbol, period_end HAVING COUNT(*) > 1 LIMIT 60")]
        finally:
            conn.close()
        for sym in syms:
            payload = fundamental.get_fundamental_quarters(sym, limit=16)
            want = contract_winners_for(ro, sym)
            old = legacy_winners_for(ro, sym)
            for q in payload["quarters"]:
                k = (q["period_end"], q["period_months"])
                if k not in want:
                    continue
                slots += 1
                if numbers_of(q) != want[k][0]:
                    mismatch += 1
                    print("   MISMATCH %s %s" % (sym, k))
                if k in old and old[k][1] != want[k][1]:
                    legacy_rows_moved += 1
                    if old[k][0] != want[k][0]:
                        legacy_numbers_moved += 1
        chk(slots > 0, "۸ اسلاتِ چندردیفی رویِ بانکِ کاری خوانده شد", str(slots))
        chk(mismatch == 0,
            "۸ رویِ بانکِ کاری: پاسخِ اندپوینت = برندۀ قاعدۀ یگانۀ موتور "
            "(%d اسلات از %d نماد)" % (slots, len(syms)), str(mismatch))
        print("  info  ۸ %d اسلات از %d نمادِ چندردیفی سنجیده شد؛ الگوریتمِ کهنه در "
              "%d اسلات ردیفِ دیگری برنده می‌کرد و در %d تا عددِ نمایشی عوض می‌شد"
              % (slots, len(syms), legacy_rows_moved, legacy_numbers_moved))
    finally:
        fundamental.get_db = orig


def numbers_of(q):
    return tuple(q.get(k) for k in FE.FS_NUMBER_KEYS)


def contract_winners_for(connect, symbol):
    """برندۀ هر (دوره، طول) با همان توابعِ `fts_engine` — برایِ سنجشِ بی‌ SIDE-effect
    رویِ بانک؛ قاعدۀ دوم ساخته نمی‌شود، تنها همان قاعده مصرف می‌شود.

    برگردان: `{(period_end, period_months): (numbers, tracing_no, publish_date)}`
    """
    c = connect()
    pred, params = FE.sym_in(c, "symbol", symbol)
    out = {}
    try:
        for r in c.execute("SELECT * FROM financial_statements WHERE %s AND %s"
                           % (pred, CP.DATED_SQL), params):
            d = dict(r)
            k = (d["period_end"], d["period_months"])
            rank = (1 if FE.title_entity_suffix(d.get("title") or "") else 0,) + \
                FE.statement_rank(FE.FS_NUMBER_KEYS,
                                  FE._is_consolidated(d.get("title") or ""),
                                  FE.row_completeness(FE.FS_NUMBER_KEYS, d),
                                  d["tracing_no"])
            cur = out.get(k)
            if cur is None or rank < cur[3]:
                out[k] = (tuple(d.get(x) for x in FE.FS_NUMBER_KEYS),
                          d["tracing_no"], d["publish_date"], rank)
        return {k: v[:3] for k, v in out.items()}
    finally:
        c.close()


def legacy_winners_for(connect, symbol):
    """برندۀ **کهنه** (کنترلِ منفی): کوئریِ پیش از اصلاح، یعنی
    `ORDER BY period_end DESC, publish_date DESC` و اولینِ هر کلید — واژگانیِ
    خامِ `publish_date` با رقمِ مخلوط."""
    c = connect()
    pred, params = FE.sym_in(c, "symbol", symbol)
    out = {}
    try:
        for r in c.execute("SELECT period_end, period_months, tracing_no,"
                           " publish_date, revenue, gross_profit, operating_profit,"
                           " net_profit, basic_eps FROM financial_statements"
                           " WHERE %s AND %s ORDER BY period_end DESC, publish_date DESC"
                           % (pred, CP.DATED_SQL), params):
            k = (r["period_end"], r["period_months"])
            if k in out:
                continue
            out[k] = (tuple(r[i] for i in range(4, 9)), r["tracing_no"],
                      r["publish_date"])
        return out
    finally:
        c.close()



def t9_company_scope():
    # ── ۹) صورتِ مالیِ شرکتِ فرعی نمایندۀ نماد نیست ────────────────────────
    chk(FE.title_entity_suffix(T_MAIN) == "",
        "۹ «(حسابرسی شده)» شرکتِ دیگر نیست")
    chk(FE.title_entity_suffix(T_CONS) == "",
        "۹ «تلفیقی» شرکتِ دیگر نیست")
    chk(FE.title_entity_suffix(T_AMEND) == "",
        "۹ «(اصلاحیه)» شرکتِ دیگر نیست")
    T_SUB = "صورت‌های مالی  سال مالی منتهی به ۱۴۰۴/۱۲/۲۹ (حسابرسی شده) (شرکت فرعی الف)"
    chk(FE.title_entity_suffix(T_SUB) != "", "۹ پسوندِ «(شرکت …)» خوانده می‌شود")
    chk(FE.title_entity_suffix("صورت مالی منتهی به ۱۴۰۴/۱۲/۲۹ （شرکت فرعی ب）") != "",
        "۹ پرانتزِ تمام‌عرض هم خوانده می‌شود")

    sub_newer = "صورت‌های مالی  سال مالی منتهی به ۱۴۰۴/۱۲/۲۹ (حسابرسی شده) (شرکت فرعی الف)"
    b = Bank([
        fs_row(200, symbol="هلدینگ", title=T_MAIN, period_end=PE, period_months=12,
               publish_date="1405/05/01 10:00:00", revenue=10.0, gross_profit=1.0,
               net_profit=1.0, basic_eps=0.1, operating_profit=None, total_assets=None),
        fs_row(201, symbol="هلدینگ", title=sub_newer, period_end=PE, period_months=12,
               publish_date="1405/07/01 10:00:00", revenue=999.0, gross_profit=900.0,
               net_profit=800.0, basic_eps=80.0, operating_profit=700.0,
               total_assets=5000.0),
    ])
    try:
        got = picked(quarters(b, "هلدینگ"), PE, 12)
        chk(got["revenue"] == 10.0,
            "۹ ردیفِ خودِ نماد بر ردیفِ شرکتِ فرعی (تازه‌تر و کامل‌تر) برنده است", str(got))
        chk(len(b.all_rows()) == 2, "۹ هر دو ردیف در بانک می‌مانند")
    finally:
        b.close()

    # همهٔ ردیف‌ها فرعی ⇒ پاسخ حذف نمی‌شود؛ قاعدۀ موتور بینِ آن‌ها می‌گزیند
    b = Bank([
        fs_row(210, symbol="فقط‌فرعی", title="صورت‌های مالی  سال مالی منتهی به ۱۴۰۴/۱۲/۲۹ (حسابرسی شده) (شرکت الف)",
               period_end=PE, period_months=12, publish_date="1405/05/01 10:00:00",
               revenue=1.0, gross_profit=1.0, net_profit=1.0, basic_eps=1.0),
        fs_row(211, symbol="فقط‌فرعی", title="صورت‌های مالی  سال مالی منتهی به ۱۴۰۴/۱۲/۲۹ (حسابرسی شده) (شرکت ب)",
               period_end=PE, period_months=12, publish_date="1405/05/02 10:00:00",
               revenue=2.0, gross_profit=2.0, net_profit=2.0, basic_eps=2.0),
    ])
    try:
        payload = quarters(b, "فقط‌فرعی")
        chk(payload["count"] == 1 and payload["quarters"][0]["revenue"] == 2.0,
            "۹_slotِ فقط‌فرعی بی‌جواب نمی‌ماند و با tracing_no newest می‌گزیند",
            str(payload["quarters"]))
    finally:
        b.close()


def t11_spelling_variants():
    # ── ۱۱) دو نوشتارِ یکِ نماد (ی↔ي) ⇒ یکِ اسلات، یکِ جواب، هر دو ردیف سالم ──
    # چرا لازم است: `collapse_symbol` با `WHERE symbol=?`ِ خام می‌کاهد، پس این دو
    # ردیف هرگز درِ بانک ادغام نمی‌شوند (سنجشِ بانکِ کاری: ۷۲ اسلات فقط بعدِ
    # نرمال‌سازیِ املا دیده می‌شوند). تنها جایی که می‌توانند به هم برسند خواننده
    # است، از راهِ `sym_in` — و همان‌جا باید داوریِ نسخه انجام شود، نه ترتیبِ SQLite.
    ar = "آينده"      # ي عربی
    fa_sym = "آینده"  # ی فارسی
    b = Bank([
        fs_row(220, symbol=ar, title=T_MAIN, period_end=PE, period_months=12,
               publish_date=fa("1405/05/01 10:00:00"), revenue=1.0, gross_profit=1.0,
               net_profit=1.0, basic_eps=0.1),
        fs_row(221, symbol=fa_sym, title=T_MAIN, period_end=PE, period_months=12,
               publish_date="1405/07/01 10:00:00", revenue=2.0, gross_profit=2.0,
               net_profit=2.0, basic_eps=0.2),
    ])
    try:
        for asked in (ar, fa_sym):
            payload = quarters(b, asked)
            chk(payload["count"] == 1,
                "۱۱ پرس‌وجو با «%s» ⇒ یکِ ردیف برایِ آن دوره (نه دو نوشتار)" % asked,
                str(payload["count"]))
            chk(payload["quarters"][0]["revenue"] == 2.0,
                "۱۱ درِ تساویِ نوشتار، ردیفِ کامل‌تر/تازه‌تر برنده است",
                str(payload["quarters"][0]["revenue"]))
        chk(len(b.all_rows()) == 2, "۱۱ هیچِ نوشتاری درِ بانک حذف/یکی نمی‌شود")
    finally:
        b.close()


def t10_no_second_rule():
    """«کدامِ ردیف برنده است» فقط درِ لایۀ canonical نوشته می‌شود، نه درِ API.

    متنِ docstring منظور نیست: بدنهٔ اجراشدۀ اندپوینت خوانده می‌شود (docstring
    و توضیح‌هایِ کنارِ سطر حذف می‌شوند) و باید *واگذار* کند، نه خودش بگزیند.
    """
    import inspect
    import io
    import re as _re
    body = _re.sub(r'""".*?"""', "", inspect.getsource(fundamental.get_fundamental_quarters),
                   count=1, flags=_re.S)
    body = _re.sub(r"#.*", "", body)
    chk("quarter_reference_rows" in body,
        "۱۰ اندپوینت به `fts_engine.quarter_reference_rows` واگذار می‌کند (تک‌منبع)")
    for second_rule in ("statement_rank", "title_entity_suffix", "row_completeness"):
        chk(second_rule not in body,
            "۱۰ «%s» درِ بدانۀ اندپوینت تکرار نمی‌شود" % second_rule)
    chk("publish_date DESC" not in body,
        "۱۰ درِ بدانۀ کوئری هیچ ترتیبِ واژگانیِ publish_date نمانده")
    chk("ORDER BY" not in body,
        "۱۰ کوئریِ سریِ فصلی بی‌ORDER BY است (ترتیبِ مرجع کارِ لایۀ canonical است)",
        "")
    eng = io.open(os.path.join(ROOT, "fts_engine.py"), encoding="utf-8").read()
    for name in ("def title_entity_suffix", "def quarter_reference_rows",
                 "def statement_rank"):
        chk(eng.count(name) == 1, "۱۰ تعریفِ `%s` یکی است" % name,
            str(eng.count(name)))
    # لایۀ دامنۀ شرکت باید درِ همان تابعِ canonical مصرف شود، نه فقط تعریف شده باشد.
    qr = _re.search(r"def quarter_reference_rows\(.*?\n(?=\ndef |\nFS_COLS)", eng, _re.S)
    chk(qr is not None and "title_entity_suffix(" in qr.group(0),
        "۱۰ `quarter_reference_rows` خودِ `title_entity_suffix` را می‌خواند")


def main():
    for fn in (t1_script_independent, t2_same_date_two_notices,
               t3_main_beats_consolidated, t4_different_statement_types,
               t5_undated_rows, t6_limit_after_dedupe, t7_stability_and_shape,
               t9_company_scope, t11_spelling_variants, t10_no_second_rule,
               t8_real_bank_spot_check):
        fn()
    print("codal_reference_select_v1088: %d passed / %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
