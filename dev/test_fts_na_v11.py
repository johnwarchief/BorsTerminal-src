# -*- coding: utf-8 -*-
"""dev/test_fts_na_v11.py — N/A صادقانه در ردیفِ غربالگری و قراردادِ دلیل (Task 4).

چهار لایه را می‌سنجد:
  ۱) همان آزمونِ brief رویِ `axis1_state`: شکافِ ۱الف = `None` + دلیل، نه `False`.
  ۲) `fs_growth_from_rows`: فقط «جدیدترین» دورهٔ هر مبنا داوری می‌شود؛ اگر
     جدیدترین صورتِ مالی سالانه جفتِ سالِ قبل ندارد، دورهٔ قدیمی‌ترِ دارای جفت
     بی‌صدا جای آن نمی‌نشیند — N/A با دلیل (`basis="fs_unavailable"`).
  ۳) DB موقت با اسکیمای کامل: ردیفِ `bulk_scan` باید `i1_na`/`i1_reason`/
     `i1_basis` را حمل کند و دلیلش دقیقاً همان دلیلِ کارت (`evaluate_v10`) باشد؛
     شکافِ ماهانه (`i1_basis=None`) از شکافِ صورتِ مالی (`fs_unavailable`) جدا
     باشد و `score` فقط `True` را بشمارد.
  ۴) سه‌گانهٔ ۱بِ اسکرینر: `applicable=False` همیشه `(pass=False,
     basis="not_applicable")` است، حتی اگر کارت برایِ همان ماهیت `pass=True`
     ساخته باشد؛ حکمِ محور ۱ وتو نمی‌شود.

اجرا:  python dev/test_fts_na_v11.py
(بدونِ سرور، بدونِ شبکه؛ DB موقت، هیچ نوشتنی رویِ market.db نیست.)
"""
import contextlib
import io
import os
import shutil
import sys

try:                       # پیام‌های فارسی روی کنسولِ cp1252 ویندوز
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fts_engine                                          # noqa: E402
from api import fundamental as FD                          # noqa: E402
from api.fundamental import axis1_state                    # noqa: E402

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


# ═══════════════════════════════════════════════════════════════════════════
#  ۱) آزمونِ brief — شکافِ داده رأی نیست
# ═══════════════════════════════════════════════════════════════════════════
state, reason = axis1_state({"monetary_pct": None, "pass": False, "data_gap": True,
                             "reason": "بدون گزارش ماهانه"}, {})
chk(state is None and "گزارش" in reason, "N/A gap is None with its own reason",
    (state, reason))
chk(axis1_state({"pass": False, "monetary_pct": 10.0, "data_gap": False,
                 "reason": ""}, {})[0] is False,
    "a measured below-floor growth is still a real fail")
print("OK N/A semantics")


# ═══════════════════════════════════════════════════════════════════════════
#  ۲) فقط جدیدترین دورهٔ هر مبنا داوری می‌شود — fallback بی‌صدا به دورهٔ قدیمی نه
# ═══════════════════════════════════════════════════════════════════════════
FS_TITLE = "صورت مالی ۱۲ ماهه حسابرسی شده غیرتلفیقی"


def _fs(rows):
    return [tuple(r) for r in rows]


# جدیدترین سالانه (۱۴۰۵) جفتِ ۱۴۰۴ ندارد، ولی ۱۴۰۳ جفتِ ۱۴۰۲ دارد.
# کدِ قدیمی +۱۰۰٪ از ۱۴۰۳ می‌ساخت؛ قراردادِ صادقانه = N/A با دلیل.
r_old_annual = fts_engine.fs_growth_from_rows(_fs([
    ("1405/12/29", 12, 3000.0, FS_TITLE),
    ("1403/12/29", 12, 2000.0, FS_TITLE),
    ("1402/12/29", 12, 1000.0, FS_TITLE),
]))
chk(r_old_annual.get("monetary_pct") is None,
    "an older annual pair never replaces the newest annual period",
    r_old_annual.get("monetary_pct"))
chk(r_old_annual.get("data_gap") is True and bool(r_old_annual.get("reason")),
    "the newest annual without a prior is an N/A with a reason",
    r_old_annual.get("reason"))
chk(r_old_annual.get("basis") == "fs_unavailable",
    "FS N/A basis is distinct from the monthly path (None)",
    r_old_annual.get("basis"))

# همان قاعده برایِ میاندوره: جدیدترین ۱۴۰۵/۰۶ جفت ندارد؛ ۱۴۰۴/۰۳ جفتِ ۱۴۰۳/۰۳
# دارد ولی نباید جای جدیدترین را بگیرد.
r_old_interim = fts_engine.fs_growth_from_rows(_fs([
    ("1405/06/31", 6, 1500.0, "صورت مالی ۶ ماهه حسابرسی نشده غیرتلفیقی"),
    ("1404/03/31", 3, 900.0, "صورت مالی ۳ ماهه حسابرسی نشده غیرتلفیقی"),
    ("1403/03/31", 3, 600.0, "صورت مالی ۳ ماهه حسابرسی نشده غیرتلفیقی"),
]))
chk(r_old_interim.get("monetary_pct") is None
    and r_old_interim.get("basis") == "fs_unavailable",
    "an older interim pair never replaces the newest interim period",
    (r_old_interim.get("monetary_pct"), r_old_interim.get("basis")))

# اگر جدیدترین میاندوره جفت ندارد ولی سالانهٔ جدید جفت دارد، fallback سالانه
# معتبر است (مبنا صریحاً fs_annual می‌شود) — نه دورهٔ میاندورهٔ قدیمی.
r_annual_fallback = fts_engine.fs_growth_from_rows(_fs([
    ("1405/06/31", 6, 1500.0, "صورت مالی ۶ ماهه حسابرسی نشده غیرتلفیقی"),
    ("1404/03/31", 3, 900.0, "صورت مالی ۳ ماهه حسابرسی نشده غیرتلفیقی"),
    ("1403/03/31", 3, 600.0, "صورت مالی ۳ ماهه حسابرسی نشده غیرتلفیقی"),
    ("1404/12/29", 12, 2200.0, FS_TITLE),
    ("1403/12/30", 12, 2000.0, FS_TITLE),
]))
chk(r_annual_fallback.get("basis") == "fs_annual"
    and abs((r_annual_fallback.get("monetary_pct") or 0) - 10.0) < 0.01,
    "the newest annual pair is still the honest fallback",
    (r_annual_fallback.get("basis"), r_annual_fallback.get("monetary_pct")))


# ═══════════════════════════════════════════════════════════════════════════
#  ۳) DB موقت — ردیف/کارت رویِ دو نوع شکاف و یک مسیرِ سالم
# ═══════════════════════════════════════════════════════════════════════════
MONTH_GAP = "ماهانه‌گپ"      # تولیدی: گزارشِ ۱۴۰۴ هست، ۱۴۰۳ نیست ⇒ N/A ماهانه
FS_GAP = "مالی‌گپ"           # مالی: جدیدترین سالانه جفت ندارد ⇒ N/A صورتِ مالی
FIN_OK = "مالی‌سالم"         # مالی: میاندوره +۱۰۰٪ ⇒ ۱ب N/A ولی محور ۱ پاس

PROD_SECTOR = "فلزات اساسي"
FIN_SECTOR = "بانكها و موسسات اعتباري"

FS_COLS = ("tracing_no,symbol,company_name,title,report_kind,period_months,"
           "period_end,publish_date,revenue,gross_profit,operating_profit,"
           "net_profit,total_assets,total_liabilities,total_equity,capital,"
           "retained_earnings,basic_eps,unit,url,fetched_at,is_audited,"
           "is_consolidated,fiscal_year,unit_norm,has_operating_sales")


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
    for i, (pe, months, rev, title, audited) in enumerate(rows):
        con.execute(
            "INSERT INTO financial_statements (" + FS_COLS + ") "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tn0 + i, symbol, name, title,
             "interim" if months < 12 else "annual", months, pe, "2026-08-01",
             rev, rev * 0.35, rev * 0.28, rev * 0.21, 900e9, 800e9, 100e9,
             100e9, 40e9, 800.0, "mrl", None, "t", audited, 0,
             pe.split("/")[0], "mrl", 1))


def _seed_monthly_1404(con, tn0, symbol, per_month):
    """فقط ۱۲ ماهِ ۱۴۰۴ — هیچ ردیفِ ۱۴۰۳ و هیچ ستونِ مقایسه‌ای ⇒ شکاف."""
    for m in range(1, 13):
        con.execute(
            "INSERT INTO monthly_sales (tracing_no,symbol,title,period_end,"
            "year,month,monthly_revenue,ytd_revenue,ytd_revenue_prev,"
            "monthly_volume,ytd_volume,volume_unit) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (tn0 + m, symbol, "گزارش فعالیت ماهانه", "1404/12/29", 1404, m,
             per_month, per_month * m, 0.0, None, None, None))


def _temp_db_case():
    path, con = U11.make_db()
    try:
        _seed_instrument(con, "I41", MONTH_GAP, "شرکت ماهانه‌گپ", PROD_SECTOR)
        _seed_instrument(con, "I42", FS_GAP, "بانک مالی‌گپ", FIN_SECTOR)
        _seed_instrument(con, "I43", FIN_OK, "بانک مالی‌سالم", FIN_SECTOR)

        _seed_monthly_1404(con, 8100, MONTH_GAP, 1000e9)
        # سالانه‌هایِ ثابت فقط برایِ حضور در جهانِ bulk/EPS — مسیرِ ۱ همان ماهانه است.
        _seed_fs(con, 8200, MONTH_GAP, "شرکت ماهانه‌گپ", [
            ("1402/12/29", 12, 4000e9, FS_TITLE, 1),
            ("1403/12/29", 12, 4000e9, FS_TITLE, 1),
            ("1404/12/29", 12, 4000e9, FS_TITLE, 1),
        ])
        # جدیدترین سالانه (۱۴۰۵) جفتِ ۱۴۰۴ ندارد؛ ۱۴۰۳ جفتِ ۱۴۰۲ دارد.
        _seed_fs(con, 8300, FS_GAP, "بانک مالی‌گپ", [
            ("1405/12/29", 12, 3000e9, FS_TITLE, 1),
            ("1403/12/29", 12, 2000e9, FS_TITLE, 1),
            ("1402/12/29", 12, 1000e9, FS_TITLE, 1),
        ])
        # میاندورهٔ ۱۴۰۵/۰۶ در برابر ۱۴۰۴/۰۶ = +۱۰۰٪ (۱ب برایِ مالی N/A).
        _seed_fs(con, 8400, FIN_OK, "بانک مالی‌سالم", [
            ("1405/06/31", 6, 2000e9, "صورت مالی ۶ ماهه حسابرسی نشده غیرتلفیقی", 0),
            ("1404/06/31", 6, 1000e9, "صورت مالی ۶ ماهه حسابرسی نشده غیرتلفیقی", 0),
            ("1404/12/29", 12, 2200e9, FS_TITLE, 1),
            ("1403/12/30", 12, 2000e9, FS_TITLE, 1),
        ])
        con.commit()

        cfg = fts_engine.load_fts_config(os.path.join(ROOT, "fts_thresholds.json"))
        rows = fts_engine.bulk_scan(con, cfg=cfg)
        by_key = {r["symbol_norm"]: r for r in rows}
        key_month = fts_engine.norm_fa(MONTH_GAP)
        key_fs = fts_engine.norm_fa(FS_GAP)
        key_ok = fts_engine.norm_fa(FIN_OK)

        def card(sym, sector, name):
            return FD.evaluate_v10(con, sym, cfg=cfg, sector=sector,
                                   company_name=name, has_instrument=True)

        # ── شکافِ ماهانه: i1_na، دلیلِ مشترک با کارت، basis=None ─────────
        b = by_key.get(key_month)
        chk(b is not None, "monthly-gap symbol is in bulk_scan", sorted(by_key))
        if b is not None:
            for f in ("i1_na", "i1_reason", "i1_basis", "i1a_pass", "i1b_pass",
                      "i1b_applicable", "i1b_basis"):
                chk(f in b, "bulk row exposes %s" % f, sorted(b))
            chk(b.get("i1_pass") is None and b.get("i1_na") is True,
                "monthly gap: i1_pass=None and i1_na=True",
                (b.get("i1_pass"), b.get("i1_na")))
            chk(b.get("i1_basis") is None,
                "monthly gap keeps i1_basis=None (monthly path)",
                b.get("i1_basis"))
            chk("ی" in (b.get("i1_reason") or "")
                and "سال قبل" in (b.get("i1_reason") or ""),
                "monthly gap carries the specific prior-period reason",
                b.get("i1_reason"))
            chk(b.get("i1a_pass") is False and b.get("i1b_pass") is False,
                "monthly gap is not a pass on either leg",
                (b.get("i1a_pass"), b.get("i1b_pass")))
            chk(b.get("i1b_applicable") is True
                and b.get("i1b_basis") == "unavailable",
                "monthly gap 1b is applicable but unavailable",
                (b.get("i1b_applicable"), b.get("i1b_basis")))
            c = card(MONTH_GAP, PROD_SECTOR, "شرکت ماهانه‌گپ")
            chk(c["passes"]["1_growth"] is None
                and c["indicators"]["1"].get("pass") is None,
                "card gap axis is None too", c["passes"])
            chk(b.get("i1_reason") == (c["indicators"]["1"].get("reason") or ""),
                "bulk i1_reason == card axis-1 reason",
                (b.get("i1_reason"), c["indicators"]["1"].get("reason")))
            chk(b.get("score") == sum(1 for i in (2, 3, 4, 5)
                                      if b.get("i%d_pass" % i) is True),
                "a None axis never scores", b.get("score"))

        # ── شکافِ صورتِ مالی: basis جدا، دلیلِ مشترک با کارت ───────────────
        b = by_key.get(key_fs)
        chk(b is not None, "FS-gap symbol is in bulk_scan", sorted(by_key))
        if b is not None:
            chk(b.get("i1_pass") is None and b.get("i1_na") is True,
                "FS gap: i1_pass=None and i1_na=True",
                (b.get("i1_pass"), b.get("i1_na")))
            chk(b.get("i1_basis") == "fs_unavailable",
                "FS gap basis is fs_unavailable, not the monthly None",
                b.get("i1_basis"))
            chk(b.get("rev_growth") is None,
                "FS gap never uses an older annual pair for a number",
                b.get("rev_growth"))
            c = card(FS_GAP, FIN_SECTOR, "بانک مالی‌گپ")
            chk(c["passes"]["1_growth"] is None,
                "card FS gap axis is None", c["passes"])
            mon = c["indicators"]["1"]["monetary"]
            chk(mon.get("basis") == "fs_unavailable",
                "card monetary basis matches the row",
                mon.get("basis"))
            chk(b.get("i1_reason") == (c["indicators"]["1"].get("reason") or "")
                and bool(b.get("i1_reason")),
                "FS gap bulk i1_reason == card axis-1 reason",
                (b.get("i1_reason"), c["indicators"]["1"].get("reason")))
            chk(b.get("i1b_applicable") is False
                and b.get("i1b_pass") is False
                and b.get("i1b_basis") == "not_applicable",
                "FS gap 1b triple is the consistent N/A",
                (b.get("i1b_applicable"), b.get("i1b_pass"),
                 b.get("i1b_basis")))

        # ── مسیرِ سالم: رفتارِ Task 2/3 دست‌نخورده ─────────────────────────
        b = by_key.get(key_ok)
        chk(b is not None, "healthy financial symbol is in bulk_scan", sorted(by_key))
        if b is not None:
            chk(b.get("i1_na") is False and b.get("i1_pass") is True,
                "healthy FS interim passes without N/A",
                (b.get("i1_na"), b.get("i1_pass")))
            chk(b.get("i1_basis") == "fs_interim",
                "healthy FS interim keeps its basis", b.get("i1_basis"))
            chk(b.get("i1b_applicable") is False
                and b.get("i1b_pass") is False
                and b.get("i1b_basis") == "not_applicable",
                "healthy financial 1b is a consistent N/A triple",
                (b.get("i1b_applicable"), b.get("i1b_pass"),
                 b.get("i1b_basis")))
            c = card(FIN_OK, FIN_SECTOR, "بانک مالی‌سالم")
            chk(c["indicators"]["1"]["volume"].get("pass") is True,
                "the card still computes a 1b pass for a non-production kind",
                c["indicators"]["1"]["volume"])
            chk(c["passes"]["1_growth"] is True,
                "the card N/A 1b is not a veto", c["passes"])
    finally:
        con.close()
        shutil.rmtree(os.path.dirname(path), ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════════
#  ۴) سه‌گانهٔ ۱بِ اسکرینر — یک قاعده، دو مسیر
# ═══════════════════════════════════════════════════════════════════════════
from api.screener import _merge_1b_fields                  # noqa: E402

chk(_merge_1b_fields(False, True, "price_effect_decomposition", "unavailable")
    == (False, "not_applicable"),
    "screener: non-applicable 1b is always (False, not_applicable)")
chk(_merge_1b_fields(True, False, "reported_quantity", "reported_quantity")
    == (False, "reported_quantity"),
    "screener: applicable 1b keeps the card verdict/basis")
chk(_merge_1b_fields(True, True, None, "unavailable") == (True, "unavailable"),
    "screener: applicable 1b falls back to the bulk basis")


def _run_main():
    _temp_db_case()
    print("fts-na: %d pass / %d fail" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(_run_main())
