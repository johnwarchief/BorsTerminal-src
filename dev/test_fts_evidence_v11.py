# -*- coding: utf-8 -*-
"""dev/test_fts_evidence_v11.py — برچسبِ شاهدِ EPS رویِ هر سه سطح (Task 5).

قاعدهٔ مالک: سالانهٔ حسابرسی‌شده مقدم است؛ در نبودش بهترین شاهدِ موجود با
توضیحِ صریح؛ مقدارِ تلفیقی فقط نمایشی است و حکم نمی‌گیرد (N/A، نه رد)؛
کمتر از سه سال «دادهٔ ناکافی» است. این آزمون همان قاعده را رویِ خودِ
`eps_assessment` و سپس رویِ کارت (`ind2_eps_track`/`evaluate_v10`)، ردیفِ
`bulk_scan` (`eps_evidence_label`) و `scan_symbol` می‌سنجد — یک برچسب برایِ
یکِ نماد در همهٔ سطوح، و سریِ EPS حتی در حالتِ تلفیقی/ناکافی دیده می‌شود.

اجرا:  python dev/test_fts_evidence_v11.py
(بدونِ سرور، بدونِ شبکه؛ DB موقت با اسکیمای کامل، هیچ نوشتنی رویِ market.db نیست.)
"""
import contextlib
import io
import os
import sqlite3
import sys

try:                       # پیام‌های فارسی روی کنسولِ cp1252 ویندوز
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fts_engine                                          # noqa: E402
from fts_engine import eps_assessment                      # noqa: E402
from api import fundamental as FD                          # noqa: E402

_u11_log = io.StringIO()
with contextlib.redirect_stdout(_u11_log):
    import test_fts_universe_v11 as U11                    # noqa: E402

PASS = FAIL = 0


def chk(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("  FAIL  %s %s" % (label, extra))


if U11.FAIL:
    print(_u11_log.getvalue())
chk(U11.FAIL == 0, "imported Task 1 classifier (test_fts_universe_v11) is green",
    "%d failing check(s)" % U11.FAIL)

# برچسب‌هایِ قرارداد — عیناً همان پنج مقدارِ brief (و هیچ ششمِ دیگری).
LBL_AUD = "سالانهٔ حسابرسی‌شده"
LBL_UNAUD = "سالانهٔ حسابرسی‌نشده"
LBL_INTERIM = "برآورد میان‌دوره"
LBL_CONS = "تلفیقی — نمایشی"
LBL_GAP = "دادهٔ ناکافی"
ALLOWED = {LBL_AUD, LBL_UNAUD, LBL_INTERIM, LBL_CONS, LBL_GAP}

AUD = "صورت مالی سالانه حسابرسی شده"
UNAUD = "صورت مالی سالانه حسابرسی نشده"
CA = "صورتهای مالی تلفیقی سالانه حسابرسی شده"
I6 = "صورت مالی ۶ ماهه حسابرسی نشده"


def mk():
    c = sqlite3.connect(":memory:")
    c.execute("""CREATE TABLE financial_statements (
        symbol TEXT, period_end TEXT, period_months INTEGER, title TEXT,
        basic_eps REAL, net_profit REAL)""")
    return c


def add(c, pe, title, eps, symbol="A", months=12):
    c.execute("INSERT INTO financial_statements VALUES (?,?,?,?,?,?)",
              (symbol, pe, months, title, eps, eps * 1000))


# ═══════════════════════════════════════════════════════════════════════════
#  ۱) همان سه آزمونِ brief — سه برچسبِ پایه
# ═══════════════════════════════════════════════════════════════════════════
c = mk()
for pe, eps in (("1402/12/29", 100), ("1403/12/29", 120), ("1404/12/29", 150)):
    add(c, pe, AUD, eps)
r = eps_assessment(c, "A", 3, "")
chk(r["pass"] is True and r["evidence_label"] == LBL_AUD,
    "۳ سالِ سالانهٔ حسابرسی‌شده ⇒ «%s»" % LBL_AUD,
    (r.get("pass"), r.get("evidence_label")))

c = mk()
for pe, eps in (("1402/12/29", 100), ("1403/12/29", 120), ("1404/12/29", 150)):
    add(c, pe, CA, eps)
r2 = eps_assessment(c, "A", 3, "")
chk(r2["na"] is True and r2["evidence_label"] == LBL_CONS,
    "۳ سالِ فقط تلفیقی ⇒ N/A با «%s»" % LBL_CONS,
    (r2.get("na"), r2.get("evidence_label")))
chk(r2["pass"] is False and r2.get("eps_series") == [100.0, 120.0, 150.0],
    "حکمِ تلفیقی رد/سبز نمی‌شود ولی سری نمایشی می‌ماند",
    (r2.get("pass"), r2.get("eps_series")))

c = mk()
add(c, "1403/12/29", AUD, 120)
add(c, "1404/12/29", AUD, 150)
r3 = eps_assessment(c, "A", 3, "")
chk(r3["evidence_label"] == LBL_GAP,
    "دو سال (کمتر از سه) ⇒ «%s»" % LBL_GAP, r3.get("evidence_label"))
chk(r3.get("na") is not True and r3.get("data_gap") is True and r3["pass"] is False,
    "سابقهٔ ناقص داده‌گپ است، نه N/A", (r3.get("na"), r3.get("data_gap")))
chk(len(r3.get("eps_series") or []) == 3 and r3["eps_series"][0] is None,
    "سریِ ناقص با جایِ خالی («-») می‌ماند", r3.get("eps_series"))

# ═══════════════════════════════════════════════════════════════════════════
#  ۲) دو برچسبِ تنزل + پیش‌گیتِ بیمه + نمادِ بی‌رکورد
# ═══════════════════════════════════════════════════════════════════════════
c = mk()
add(c, "1402/12/29", AUD, 100)
add(c, "1403/12/29", UNAUD, 120)
add(c, "1404/12/29", UNAUD, 150)
r4 = eps_assessment(c, "A", 3, "")
chk(r4["evidence_label"] == LBL_UNAUD and r4["pass"] is True
    and r4.get("evidence_tier") == "year_end_unaudited",
    "سالانهٔ غیرحسابرسی‌شده ⇒ «%s» با همان حکم" % LBL_UNAUD,
    (r4.get("evidence_label"), r4.get("evidence_tier"), r4.get("pass")))

c = mk()
add(c, "1402/12/29", AUD, 300)
add(c, "1403/12/29", AUD, 500)
add(c, "1404/06/31", I6, 400, months=6)
r5 = eps_assessment(c, "A", 3, "")
chk(r5["evidence_label"] == LBL_INTERIM
    and r5.get("evidence_tier") == "year_end_plus_interim" and r5["pass"] is True,
    "سالِ آخر فقط میاندوره ⇒ «%s»" % LBL_INTERIM,
    (r5.get("evidence_label"), r5.get("evidence_tier")))
chk(r5.get("eps_series") == [300.0, 500.0, 800.0],
    "برآوردِ میاندوره ×۱۲÷۶ = ۸۰۰ در سری می‌ماند", r5.get("eps_series"))

c = mk()
add(c, "1402/12/29", AUD, 100)
add(c, "1403/12/29", AUD, 120)
add(c, "1404/12/29", AUD, 150)
r6 = eps_assessment(c, "A", 3, "بیمه و صندوق بازنشستگی")
chk(r6.get("na") is True and r6.get("evidence_label") == LBL_GAP,
    "بیمه پیش‌گیت است و برچسبِ شاهدش «%s»" % LBL_GAP,
    (r6.get("na"), r6.get("evidence_label")))
r7 = eps_assessment(mk(), "Z", 3, "")
chk(r7.get("data_gap") is True and r7.get("evidence_label") == LBL_GAP,
    "نمادِ بی‌رکورد ⇒ «%s»" % LBL_GAP, r7.get("evidence_label"))

# کمتر از سه سال حتی با شاهدِ تلفیقی هم «دادهٔ ناکافی» است (قاعدهٔ مالک).
c = mk()
add(c, "1403/12/29", CA, 120)
add(c, "1404/12/29", CA, 150)
r8 = eps_assessment(c, "A", 3, "")
chk(r8.get("na") is True and r8["evidence_label"] == LBL_GAP,
    "دو سالِ تلفیقی: N/A + «%s» (کمتر از سه سال)" % LBL_GAP,
    (r8.get("na"), r8.get("evidence_label")))

# هیچ برچسبی بیرون از قراردادِ پنج‌گانه ساخته نمی‌شود.
for _r in (r, r2, r3, r4, r5, r6, r7, r8):
    chk(_r.get("evidence_label") in ALLOWED,
        "برچسب در قراردادِ پنج‌گانه است", _r.get("evidence_label"))

print("OK evidence labels")
print("%d/%d passed" % (PASS, PASS + FAIL))


# ═══════════════════════════════════════════════════════════════════════════
#  ۳) DB موقت — همان برچسب در کارت، ردیفِ bulk و scan_symbol
# ═══════════════════════════════════════════════════════════════════════════
FS_COLS = ("tracing_no,symbol,company_name,title,report_kind,period_months,"
           "period_end,publish_date,revenue,gross_profit,operating_profit,"
           "net_profit,total_assets,total_liabilities,total_equity,capital,"
           "retained_earnings,basic_eps,unit,url,fetched_at,is_audited,"
           "is_consolidated,fiscal_year,unit_norm,has_operating_sales")

SEC = "فلزات اساسي"
AUD3 = ("شاهدس", "شرکت شاهد سالانه")
CONS3 = ("شاهدت", "شرکت شاهد تلفیقی")
AUD2 = ("شاهدب", "شرکت شاهد دو ساله")
UNAUD3 = ("شاهدو", "شرکت شاهد حسابرسی‌نشده")


def _seed_instrument(con, code, symbol, name, sector):
    con.execute(
        "INSERT INTO instruments (ins_code,l_val18,l_val30,sector_code,"
        "sector_name,total_shares,eps,pe,base_vol,updated_at,paper_type) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (code, symbol, name, "", sector, 1e8, 500, 10, 1, "2026-09-09", 1))
    con.execute(
        "INSERT INTO market_watch (ins_code,d_even,p_closing,total_shares,"
        "sector_code,market_cap,market_cap_src) VALUES (?,?,?,?,?,?,?)",
        (code, 20260909, 1000.0, 1e8, "", 1.0e14, "tse_raw"))
    con.execute(
        "INSERT INTO daily_prices (ins_code,d_even,p_closing,q_tot_cap) "
        "VALUES (?,?,?,?)", (code, 20260909, 1000.0, 1.0e14))


def _seed_fs(con, tn0, symbol, name, rows):
    """rows: (period_end, months, title, eps) — بقیهٔ ستون‌ها ساختگی‌اند."""
    for i, (pe, months, title, eps) in enumerate(rows):
        con.execute(
            "INSERT INTO financial_statements (" + FS_COLS + ") "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tn0 + i, symbol, name, title,
             "interim" if months < 12 else "annual", months, pe, "2026-08-01",
             4000e9, 1400e9, 1120e9, 840e9, 900e9, 800e9, 100e9,
             100e9, 40e9, eps, "mrl", None, "t",
             0 if "نشده" in title else 1,
             1 if "تلفیقی" in title and "غیرتلفیقی" not in title else 0,
             pe.split("/")[0], "mrl", 1))


def _temp_db_case():
    path, con = U11.make_db()
    try:
        _seed_instrument(con, "I51", AUD3[0], AUD3[1], SEC)
        _seed_instrument(con, "I52", CONS3[0], CONS3[1], SEC)
        _seed_instrument(con, "I53", AUD2[0], AUD2[1], SEC)
        _seed_instrument(con, "I54", UNAUD3[0], UNAUD3[1], SEC)
        _seed_fs(con, 5100, AUD3[0], AUD3[1], [
            ("1402/12/29", 12, AUD, 100), ("1403/12/29", 12, AUD, 120),
            ("1404/12/29", 12, AUD, 150)])
        _seed_fs(con, 5200, CONS3[0], CONS3[1], [
            ("1402/12/29", 12, CA, 100), ("1403/12/29", 12, CA, 120),
            ("1404/12/29", 12, CA, 150)])
        _seed_fs(con, 5300, AUD2[0], AUD2[1], [
            ("1403/12/29", 12, AUD, 120), ("1404/12/29", 12, AUD, 150)])
        _seed_fs(con, 5400, UNAUD3[0], UNAUD3[1], [
            ("1402/12/29", 12, AUD, 100), ("1403/12/29", 12, UNAUD, 120),
            ("1404/12/29", 12, UNAUD, 150)])
        con.commit()

        cfg = fts_engine.load_fts_config(os.path.join(ROOT, "fts_thresholds.json"))
        rows = fts_engine.bulk_scan(con, cfg=cfg)
        by_key = {r["symbol_norm"]: r for r in rows}

        def card(sym, name):
            return FD.evaluate_v10(con, sym, cfg=cfg, sector=SEC,
                                   company_name=name, has_instrument=True)

        def scan(sym):
            return fts_engine.scan_symbol(con, sym, 1.0e14, 2.0e15, SEC, cfg=cfg)

        def track(sym):
            return FD.ind2_eps_track(con, sym, sector=SEC)

        # ── سالانهٔ حسابرسی‌شده: سه سطح یک برچسب ─────────────────────────
        key = fts_engine.norm_fa(AUD3[0])
        b = by_key.get(key)
        chk(b is not None, "نمادِ سالانه در bulk_scan هست", sorted(by_key))
        if b is not None:
            c2 = card(AUD3[0], AUD3[1])["indicators"]["2"]
            t2 = track(AUD3[0])
            s2 = scan(AUD3[0])
            chk(b.get("eps_evidence_label") == LBL_AUD,
                "bulk: eps_evidence_label = «%s»" % LBL_AUD,
                b.get("eps_evidence_label"))
            chk(c2.get("evidence_label") == LBL_AUD,
                "card indicators[2].evidence_label = «%s»" % LBL_AUD,
                c2.get("evidence_label"))
            chk(t2.get("evidence_label") == LBL_AUD,
                "ind2_eps_track همان برچسب را می‌دهد", t2.get("evidence_label"))
            chk(s2.get("eps_evidence_label") == LBL_AUD,
                "scan_symbol.eps_evidence_label = «%s»" % LBL_AUD,
                s2.get("eps_evidence_label"))
            chk((s2.get("detail") or {}).get("eps_trend", {}).get("evidence_label")
                == LBL_AUD,
                "scan_symbol.detail.eps_trend هم همان برچسب را دارد",
                (s2.get("detail") or {}).get("eps_trend", {}).get("evidence_label"))
            chk(b.get("eps_series") == [100.0, 120.0, 150.0],
                "سریِ EPS در ردیف کامل است", b.get("eps_series"))

        # ── فقط تلفیقی: N/A و «نمایشی»، ولی سری حذف نمی‌شود ───────────────
        key = fts_engine.norm_fa(CONS3[0])
        b = by_key.get(key)
        if b is not None:
            c2 = card(CONS3[0], CONS3[1])["indicators"]["2"]
            chk(b.get("eps_evidence_label") == LBL_CONS,
                "bulk تلفیقی: «%s»" % LBL_CONS, b.get("eps_evidence_label"))
            # ادغام با main: حکمِ شاخص ۲ سه‌حال شد (None = «سنجیده نشد»)، پس
            # «N/A و نه پاس» با None هم برقرار است؛ `i2_na` تنها پرچمِ N/A است.
            chk(b.get("i2_na") is True and not b.get("i2_pass"),
                "bulk تلفیقی: N/A و نه پاس", (b.get("i2_na"), b.get("i2_pass")))
            chk(b.get("eps_series") == [100.0, 120.0, 150.0]
                and b.get("eps_last") == 150.0,
                "bulk تلفیقی: سری و آخرین مقدار نمایشی می‌مانند",
                (b.get("eps_series"), b.get("eps_last")))
            chk(c2.get("evidence_label") == LBL_CONS
                and c2.get("na") is True and c2.get("pass") is False,
                "card تلفیقی: همان برچسب + na، نه رد",
                (c2.get("evidence_label"), c2.get("na"), c2.get("pass")))
            chk(c2.get("eps_series") == [100.0, 120.0, 150.0],
                "card تلفیقی: سریِ نمایشی می‌ماند", c2.get("eps_series"))
            chk(scan(CONS3[0]).get("eps_evidence_label") == LBL_CONS,
                "scan_symbol تلفیقی: «%s»" % LBL_CONS,
                scan(CONS3[0]).get("eps_evidence_label"))
        else:
            chk(False, "نمادِ تلفیقی در bulk_scan هست", sorted(by_key))

        # ── دو سال: «دادهٔ ناکافی» در هر سه سطح ───────────────────────────
        key = fts_engine.norm_fa(AUD2[0])
        b = by_key.get(key)
        if b is not None:
            c2 = card(AUD2[0], AUD2[1])["indicators"]["2"]
            chk(b.get("eps_evidence_label") == LBL_GAP,
                "bulk دو ساله: «%s»" % LBL_GAP, b.get("eps_evidence_label"))
            chk(b.get("eps_years_available") == 2
                and b.get("eps_series") == [None, 120.0, 150.0],
                "bulk دو ساله: دو مقدار و یک جای خالی",
                (b.get("eps_years_available"), b.get("eps_series")))
            chk(c2.get("evidence_label") == LBL_GAP,
                "card دو ساله: «%s»" % LBL_GAP, c2.get("evidence_label"))
            chk(scan(AUD2[0]).get("eps_evidence_label") == LBL_GAP,
                "scan_symbol دو ساله: «%s»" % LBL_GAP,
                scan(AUD2[0]).get("eps_evidence_label"))
        else:
            chk(False, "نمادِ دو ساله در bulk_scan هست", sorted(by_key))

        # ── سالانهٔ غیرحسابرسی‌شده ─────────────────────────────────────────
        key = fts_engine.norm_fa(UNAUD3[0])
        b = by_key.get(key)
        if b is not None:
            c2 = card(UNAUD3[0], UNAUD3[1])["indicators"]["2"]
            chk(b.get("eps_evidence_label") == LBL_UNAUD,
                "bulk غیرحسابرسی: «%s»" % LBL_UNAUD,
                b.get("eps_evidence_label"))
            chk(c2.get("evidence_label") == LBL_UNAUD,
                "card غیرحسابرسی: «%s»" % LBL_UNAUD,
                c2.get("evidence_label"))
        else:
            chk(False, "نمادِ غیرحسابرسی در bulk_scan هست", sorted(by_key))

        # پاریتیِ برچسب بینِ bulk و کارت برایِ هر ردیفِ این چهار نماد.
        for sym, name in (AUD3, CONS3, AUD2, UNAUD3):
            k = fts_engine.norm_fa(sym)
            b = by_key.get(k)
            if b is None:
                continue
            c2 = card(sym, name)["indicators"]["2"]
            chk(b.get("eps_evidence_label") == c2.get("evidence_label"),
                "پاریتیِ bulk/card برایِ %s" % sym,
                (b.get("eps_evidence_label"), c2.get("evidence_label")))
    finally:
        con.close()
        import shutil
        shutil.rmtree(os.path.dirname(path), ignore_errors=True)


_temp_db_case()
print("%d/%d passed" % (PASS, PASS + FAIL))
sys.exit(0 if FAIL == 0 else 1)
