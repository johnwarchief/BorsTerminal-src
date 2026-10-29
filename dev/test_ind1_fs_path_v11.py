# -*- coding: utf-8 -*-
"""dev/test_ind1_fs_path_v11.py — مسیرِ صورتِ مالی برای شاخص ۱ (Task 2).

سه لایه را می‌سنجد:
  ۱) تابعِ خالص `api.fundamental.ind1a_fs_growth` روی یک DB در حافظه:
     میاندورهٔ غیرتلفیقی ÷ همان دورهٔ سالِ قبل (۵۰٪)، و در نبودِ دورهٔ قبل
     fallback سالانه / data_gap با دلیل — از جمله سالانه‌ای که پایانِ سالش
     یک روز جابه‌جا شده (۱۴۰۴/۱۲/۲۹ در برابر ۱۴۰۳/۱۲/۳۰).
  ۲) `bulk_scan` روی DB موقت با اسکیمای کامل: نمادِ مالیِ بی‌گزارشِ ماهانه
     باید `i1_basis="fs_interim"` و همان درصدِ رشد را بگیرد — از نقشهٔ
     تک‌گذرِ صورت‌های مالی، نه فراخوانیِ N+1 — و در نبودِ میاندوره
     `i1_basis="fs_annual"` با همان جفتِ یک‌روزه‌جابه‌جا.
  ۳) کارتِ `evaluate_v10`: `indicators["1"]["monetary"]["basis"]` باید دقیقاً
     همان `i1_basis` ردیفِ غربالگری باشد؛ مسیرِ ماهانه هم کلیدِ `basis=None`
     را در تابع/کارت/ردیف دارد (قراردادِ parity).

اجرا:  python dev/test_ind1_fs_path_v11.py
(بدونِ سرور، بدونِ شبکه؛ DB موقت، هیچ نوشتنی رویِ market.db نیست.)
"""
import os
import shutil
import sqlite3
import sys
import contextlib
import io

try:                       # پیام‌های فارسی روی کنسولِ cp1252 ویندوز
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fts_engine                                          # noqa: E402
from api.fundamental import ind1a_fs_growth                # noqa: E402
from api import fundamental as FD                          # noqa: E402
with contextlib.redirect_stdout(io.StringIO()):
    # اسکیمای کاملِ DB موقت از گاردِ Task 1 می‌آید؛ آزمون‌های ماژولیِ آن
    # هنگامِ import اجرا می‌شوند و چاپشان این‌جا فقط نویز است، پس ساکت می‌شود.
    import test_fts_universe_v11 as U11                    # noqa: E402

PASS = FAIL = 0


def chk(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("  FAIL  %s %s" % (label, extra))


# ═══════════════════════════════════════════════════════════════════════════
#  ۱) تابعِ خالص — همان آزمونِ brief
# ═══════════════════════════════════════════════════════════════════════════
c = sqlite3.connect(":memory:")
c.execute("""CREATE TABLE financial_statements (
  symbol TEXT, title TEXT, period_end TEXT, period_months INTEGER,
  revenue REAL, is_consolidated INTEGER, is_audited INTEGER)""")
rows = [
  ("وبملت", "صورت مالی ۶ ماهه حسابرسی نشده", "1405/06/31", 6, 1500.0, 0, 0),
  ("وبملت", "صورت مالی ۶ ماهه حسابرسی نشده", "1404/06/31", 6, 1000.0, 0, 0),
  ("وبملت", "صورت مالی سالانه", "1404/12/29", 12, 2200.0, 0, 1),
]
c.executemany("INSERT INTO financial_statements VALUES (?,?,?,?,?,?,?)", rows)
prof = {"kind": "financial"}
r = ind1a_fs_growth(c, "وبملت", prof)
assert r["basis"] == "fs_interim", r
assert r["months"] == 6, r
assert abs(r["monetary_pct"] - 50.0) < 0.01, r
assert r["pass"] is True, r
c.execute("DELETE FROM financial_statements WHERE period_end='1404/06/31'")
r2 = ind1a_fs_growth(c, "وبملت", prof)
assert r2["data_gap"] is True and r2["reason"], r2
c.close()
print("OK ind1 fs path")


# ═══════════════════════════════════════════════════════════════════════════
#  ۱ب) سالانه با جابه‌جاییِ یک‌روزهٔ پایانِ سال (۱۴۰۴/۱۲/۲۹ در برابر ۱۴۰۳/۱۲/۳۰)
#  سالانه بر (سال−۱، همان ماه، همان تعدادِ ماه) تطبیق می‌خورد، نه بر روز؛
#  میاندوره همچنان روزِ دقیق می‌خواهد (۱۴۰۵/۰۶/۳۰ در برابر ۱۴۰۴/۰۶/۳۱ جفت
#  نیست) — پس نتیجه باید از fallback سالانه بیاید، نه N/A و نه میاندوره.
# ═══════════════════════════════════════════════════════════════════════════
c2 = sqlite3.connect(":memory:")
c2.execute("""CREATE TABLE financial_statements (
  symbol TEXT, title TEXT, period_end TEXT, period_months INTEGER,
  revenue REAL, is_consolidated INTEGER, is_audited INTEGER)""")
c2.executemany("INSERT INTO financial_statements VALUES (?,?,?,?,?,?,?)", [
  ("وبملت", "صورت مالی ۶ ماهه حسابرسی نشده", "1405/06/30", 6, 1500.0, 0, 0),
  ("وبملت", "صورت مالی ۶ ماهه حسابرسی نشده", "1404/06/31", 6, 1000.0, 0, 0),
  ("وبملت", "صورت مالی سالانه", "1404/12/29", 12, 2200.0, 0, 1),
  ("وبملت", "صورت مالی سالانه", "1403/12/30", 12, 2000.0, 0, 1),
])
r_ann = ind1a_fs_growth(c2, "وبملت", prof)
c2.close()
chk(r_ann.get("basis") == "fs_annual",
    "annual day-shift matches the prior fiscal year", r_ann.get("basis"))
chk(r_ann.get("data_gap") is False and r_ann.get("monetary_pct") is not None,
    "annual day-shift returns growth, not N/A", r_ann)
chk(r_ann.get("monetary_pct") is not None
    and abs(r_ann["monetary_pct"] - 10.0) < 0.01,
    "annual day-shift growth is +10%", r_ann)
chk(r_ann.get("months") == 12 and r_ann.get("period") == "1404/12/29",
    "annual day-shift reports the annual period", r_ann)


# ═══════════════════════════════════════════════════════════════════════════
#  ۲/۳) DB موقت — کارت و غربالگری رویِ یک نمادِ مالیِ بی‌گزارشِ ماهانه
# ═══════════════════════════════════════════════════════════════════════════
BANK = "وبملت"
BANK_SECTOR = "بانكها و موسسات اعتباري"


def _seed_bank(con):
    """نمادِ مالی با صورتِ مالی میاندوره (۱۴۰۵/۰۶ در برابر ۱۴۰۴/۰۶) و سالانه،
    بدونِ هیچ ردیفِ monthly_sales — دقیقاً مسیری که Task 2 اضافه می‌کند."""
    con.execute(
        "INSERT INTO instruments (ins_code,l_val18,l_val30,sector_code,"
        "sector_name,total_shares,eps,pe,base_vol,updated_at,paper_type) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("I9", BANK, "بانك ملت", "61", BANK_SECTOR, 1e7, 800, 5, 1,
         "2026-09-09", 1))
    con.execute(
        "INSERT INTO market_watch (ins_code,d_even,p_closing,total_shares,"
        "sector_code,market_cap,market_cap_src) VALUES (?,?,?,?,?,?,?)",
        ("I9", 20260909, 5000.0, 1e7, "61", 5.0e13, "tse_raw"))
    con.execute(
        "INSERT INTO daily_prices (ins_code,d_even,p_closing,q_tot_cap) "
        "VALUES (?,?,?,?)", ("I9", 20260909, 5000.0, 5.0e13))
    fs = [
        # (period_end, months, revenue, title, audited)
        ("1405/06/31", 6, 1500.0, "صورت مالی ۶ ماهه حسابرسی نشده غیرتلفیقی", 0),
        ("1404/06/31", 6, 1000.0, "صورت مالی ۶ ماهه حسابرسی نشده غیرتلفیقی", 0),
        ("1404/12/29", 12, 2200.0, "صورت مالی ۱۲ ماهه حسابرسی شده غیرتلفیقی", 1),
        # پایانِ سالِ قبل یک روز جلوتر (سالِ کبیسه): جفتِ سالانه باید معتبر بماند.
        ("1403/12/30", 12, 2000.0, "صورت مالی ۱۲ ماهه حسابرسی شده غیرتلفیقی", 1),
    ]
    for i, (pe, months, rev, title, audited) in enumerate(fs):
        con.execute(
            "INSERT INTO financial_statements (tracing_no,symbol,"
            "company_name,title,report_kind,period_months,period_end,"
            "publish_date,revenue,gross_profit,operating_profit,"
            "net_profit,total_assets,total_liabilities,total_equity,"
            "capital,retained_earnings,basic_eps,unit,url,fetched_at,"
            "is_audited,is_consolidated,fiscal_year,unit_norm,"
            "has_operating_sales) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (9000 + i, BANK, "بانك ملت", title, "interim" if months < 12 else "annual",
             months, pe, "2026-08-01", rev, rev * 0.35, rev * 0.28,
             rev * 0.21, 900e9, 800e9, 100e9, 100e9, 40e9, 800.0, "mrl",
             None, "t", audited, 0, pe.split("/")[0], "mrl", 1))
    con.commit()


def _temp_db_case():
    path, con = U11.make_db()
    try:
        _seed_bank(con)
        cfg = fts_engine.load_fts_config(os.path.join(ROOT, "fts_thresholds.json"))
        rows = fts_engine.bulk_scan(con, cfg=cfg)
        by_key = {r["symbol_norm"]: r for r in rows}
        row = by_key.get(BANK)
        chk(row is not None, "financial symbol is in bulk_scan", sorted(by_key))
        if row is not None:
            chk(row.get("i1_basis") == "fs_interim",
                "bulk_scan exposes i1_basis=fs_interim", row.get("i1_basis"))
            chk(row.get("rev_growth") is not None
                and abs(row["rev_growth"] - 50.0) < 0.05,
                "bulk_scan growth comes from the FS interim pair",
                row.get("rev_growth"))
            chk(row.get("i1_pass") is True, "bulk_scan i1 passes on +50%",
                row.get("i1_pass"))

        card = FD.evaluate_v10(con, BANK, cfg=cfg, sector=BANK_SECTOR,
                               company_name="بانك ملت", has_instrument=True)
        mon = card["indicators"]["1"]["monetary"]
        chk(mon.get("basis") == "fs_interim",
            "card exposes the same basis", mon.get("basis"))
        if row is not None:
            chk(mon.get("basis") == row.get("i1_basis"),
                "card basis == bulk i1_basis",
                (mon.get("basis"), row.get("i1_basis")))
            chk(mon.get("monetary_pct") is not None
                and abs(mon["monetary_pct"] - row["rev_growth"]) < 0.05,
                "card growth == bulk rev_growth",
                (mon.get("monetary_pct"), row.get("rev_growth")))
        chk(card["passes"]["1_growth"] is True,
            "card axis 1 passes with FS-based growth", card["passes"])

        # بدونِ دورهٔ قبل: fallback سالانه (۱۴۰۴/۱۲ در برابر ۱۴۰۳/۱۲ = +۱۰٪)
        con.execute("DELETE FROM financial_statements WHERE period_end='1404/06/31'")
        con.commit()
        r_annual = FD.ind1a_fs_growth(con, BANK, {"kind": "financial"}, th=None)
        chk(r_annual.get("basis") == "fs_annual",
            "annual fallback when the prior interim is absent",
            r_annual.get("basis"))
        chk(r_annual.get("monetary_pct") is not None
            and abs(r_annual["monetary_pct"] - 10.0) < 0.01,
            "annual fallback computes +10%", r_annual)
        chk(r_annual.get("pass") is False, "annual +10% is below the 40% floor")

        # همان جفتِ سالانه از مسیرِ غربالگری و کارت — parity برایِ fs_annual
        # هم ثابت می‌شود، نه فقط fs_interim (جفتِ سالانه یک روز اختلاف دارد).
        rows_a = fts_engine.bulk_scan(con, cfg=cfg)
        row_a = {r["symbol_norm"]: r for r in rows_a}.get(BANK)
        chk(row_a is not None and row_a.get("i1_basis") == "fs_annual",
            "bulk_scan exposes i1_basis=fs_annual",
            row_a and row_a.get("i1_basis"))
        if row_a is not None:
            chk(row_a.get("rev_growth") is not None
                and abs(row_a["rev_growth"] - 10.0) < 0.05,
                "bulk_scan annual growth comes from the day-shifted pair",
                row_a.get("rev_growth"))
            chk(row_a.get("i1_pass") is False,
                "bulk_scan annual +10% is below the 40% floor",
                row_a.get("i1_pass"))
        card_a = FD.evaluate_v10(con, BANK, cfg=cfg, sector=BANK_SECTOR,
                                 company_name="بانك ملت", has_instrument=True)
        mon_a = card_a["indicators"]["1"]["monetary"]
        chk(mon_a.get("basis") == "fs_annual",
            "card exposes fs_annual on the annual fallback", mon_a.get("basis"))
        if row_a is not None:
            chk(mon_a.get("basis") == row_a.get("i1_basis"),
                "card annual basis == bulk i1_basis",
                (mon_a.get("basis"), row_a.get("i1_basis")))
            chk(mon_a.get("monetary_pct") is not None
                and abs(mon_a["monetary_pct"] - row_a["rev_growth"]) < 0.05,
                "card annual growth == bulk rev_growth",
                (mon_a.get("monetary_pct"), row_a.get("rev_growth")))

        # مسیرِ ماهانه (بدونِ صورتِ مالی مسیرِ Task 2): کلیدِ `basis` باید در
        # تابع، کارت و ردیفِ غربالگری حاضر باشد و None بدهد — قراردادِ کامل.
        mon_fn = FD.ind1a_monetary_growth(con, "آبین")
        chk("basis" in mon_fn and mon_fn.get("basis") is None,
            "monthly ind1a_monetary_growth exposes basis=None",
            mon_fn.get("basis", "<missing>"))
        mon_gap = FD.ind1a_monetary_growth(con, "آبین", series=[])
        chk("basis" in mon_gap and mon_gap.get("basis") is None,
            "monthly data-gap return exposes basis=None",
            mon_gap.get("basis", "<missing>"))
        m_row = by_key.get("آبین")
        chk(m_row is not None and m_row.get("i1_basis") is None,
            "bulk_scan monthly row has i1_basis=None",
            m_row and m_row.get("i1_basis"))
        card_m = FD.evaluate_v10(con, "آبین", cfg=cfg, sector="",
                                 company_name="كشت و صنعت آبشيرين",
                                 has_instrument=True)
        mon_m = card_m["indicators"]["1"]["monetary"]
        chk("basis" in mon_m and mon_m.get("basis") is None,
            "card monthly monetary exposes basis=None",
            mon_m.get("basis", "<missing>"))
        chk(mon_m.get("basis") == (m_row or {}).get("i1_basis"),
            "card monthly basis == bulk i1_basis",
            (mon_m.get("basis"), (m_row or {}).get("i1_basis")))
    finally:
        con.close()
        shutil.rmtree(os.path.dirname(path), ignore_errors=True)


def _run_main():
    _temp_db_case()
    print("ind1-fs-path: %d pass / %d fail" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(_run_main())
