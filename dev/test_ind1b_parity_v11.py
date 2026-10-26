# -*- coding: utf-8 -*-
"""dev/test_ind1b_parity_v11.py — یک قاعدهٔ وتوی ۱ب برای کارت و اسکرینر (Task 3).

سه لایه را می‌سنجد:
  ۱) تابعِ خالصِ `api.fundamental.axis1_state`: وتوی ۱ب فقط برایِ تولیدی‌ها،
     N/A برایِ خدماتی/مالی/هلدینگ (نه وتو)، و «شکافِ داده» = None.
  ۲) رگرسیونِ ZeroDivision: رشد کمیتِ گزارش‌شده که به −۱۰۰٪ گرد می‌شود
     (نمادِ واقعیِ «لبن» در market.db) نباید `ind1b_volume_growth` را بشکند —
     نتیجهٔ تعریف‌شده = وتو با دلیل، و قیمتِ ضمنی = None (تقسیم بر صفر ندارد).
  ۳) DB موقت با اسکیمای کامل: `bulk_scan` باید همان حکمِ `evaluate_v10` را
     بدهد و ردیف‌هایش `i1a_pass`/`i1b_pass`/`i1b_applicable`/`i1b_basis`/
     `i1_reason` را حمل کنند — تولیدی با تناژِ افت‌کرده وتو، مالی N/A، و
     داده‌گپ None.

اجرا:  python dev/test_ind1b_parity_v11.py
(بدونِ سرور، بدونِ شبکه؛ DB موقت؛ market.db فقط برایِ اسکیمایِ DB موقت.)
"""
import contextlib
import io
import os
import shutil
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
from api import fundamental as FD                          # noqa: E402
from api.fundamental import axis1_state, axis1_pass, ind1b_volume_growth  # noqa: E402

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
mon = {"pass": True, "monetary_pct": 55.0, "data_gap": False}
vol_down = {"applicable": True, "pass": False, "basis": "reported_quantity",
            "reason": "فروش تولیدی کم شده"}
vol_up = {"applicable": True, "pass": True, "basis": "reported_quantity"}
vol_na = {"applicable": False, "pass": False, "basis": "not_applicable"}
chk(axis1_state(mon, vol_down) == (False, "فروش تولیدی کم شده"),
    "1b veto returns the volume reason", axis1_state(mon, vol_down))
chk(axis1_state(mon, vol_up)[0] is True, "1b pass keeps axis 1 open")
chk(axis1_state(mon, vol_na)[0] is True,
    "N/A 1b is not a veto (service/financial/holding)")
chk(axis1_state({"pass": False, "data_gap": True}, vol_up)[0] is None,
    "monetary data gap is None, not a silent fail")
chk(axis1_pass(mon, vol_down) is False and axis1_pass(mon, vol_up) is True
    and axis1_pass(mon, vol_na) is True,
    "axis1_pass delegates to axis1_state")
print("OK 1b parity")


# ═══════════════════════════════════════════════════════════════════════════
#  ۲) رگرسیونِ ZeroDivision — کمیتِ −۱۰۰٪ (نمادِ «لبن» روی بانکِ واقعی)
# ═══════════════════════════════════════════════════════════════════════════
def _volume_db(now_qty, prev_qty):
    con = sqlite3.connect(":memory:")
    con.execute(
        "CREATE TABLE monthly_sales (symbol TEXT, year INTEGER, month INTEGER,"
        " monthly_revenue REAL, ytd_revenue REAL, ytd_revenue_prev REAL,"
        " ytd_volume REAL, volume_unit TEXT)")
    con.execute("INSERT INTO monthly_sales VALUES (?,?,?,?,?,?,?,?)",
                ("لبن", 1405, 6, 1.0, 50623637.0, 22280068.0, now_qty, None))
    con.execute("INSERT INTO monthly_sales VALUES (?,?,?,?,?,?,?,?)",
                ("لبن", 1404, 6, 1.0, 22280068.0, 13653585.0, prev_qty, None))
    con.commit()
    return con


# همان ارقامِ واقعیِ بازار: ۶۵٬۰۴۵ در برابر ۲۵۰٬۰۶۳٬۷۵۰ ⇒ رشدِ گردشده −۱۰۰٪.
_mem = _volume_db(65045.0, 250063750.0)
try:
    vol = ind1b_volume_growth(
        _mem, "لبن",
        monetary={"year": 1405, "months": 6, "monetary_pct": 127.2,
                  "pass": True, "data_gap": False, "reason": ""},
        series=[], th=FD.v10_thresholds(), profile=FD.company_profile("فلزات اساسي"))
    chk(vol.get("basis") == "reported_quantity",
        "the physical pair is still used at −100%", vol.get("basis"))
    chk(vol.get("volume_pct") == -100.0,
        "rounded volume growth is exactly −100%", vol.get("volume_pct"))
    chk(vol.get("implied_price_pct") is None,
        "implied price is undefined at −100% volume (no zero division)",
        vol.get("implied_price_pct"))
    chk(vol.get("pass") is False,
        "−100% volume is a defined veto, not a crash", vol.get("pass"))
    st = axis1_state({"pass": True, "monetary_pct": 127.2, "data_gap": False}, vol)
    chk(st[0] is False and bool(st[1]),
        "axis 1 is vetoed with a reason at −100% volume", st)
except ZeroDivisionError as exc:
    chk(False, "ind1b_volume_growth must not raise ZeroDivisionError", repr(exc))
finally:
    _mem.close()

# حالتِ دقیقِ vol = −100 (کمیتِ فعلیِ ناچیز) هم نباید بشکند.
_mem = _volume_db(1.0, 100000.0)
try:
    vol0 = ind1b_volume_growth(
        _mem, "لبن",
        monetary={"year": 1405, "months": 6, "monetary_pct": 127.2,
                  "pass": True, "data_gap": False, "reason": ""},
        series=[], th=FD.v10_thresholds(), profile=FD.company_profile("فلزات اساسي"))
    chk(vol0.get("volume_pct") == -100.0 and vol0.get("pass") is False
        and vol0.get("implied_price_pct") is None,
        "exact −100% volume is a veto with implied price None",
        {k: vol0.get(k) for k in ("volume_pct", "pass", "implied_price_pct")})
finally:
    _mem.close()


# ═══════════════════════════════════════════════════════════════════════════
#  ۳) DB موقت — کارت ⇄ bulk_scan رویِ سه ماهیت
# ═══════════════════════════════════════════════════════════════════════════
PROD = "صنعتیآزمون"          # تولیدی: رشد ریالی +۱۰۰٪، تناژ −۹۰٪ ⇒ وتوی ۱ب
FIN = "مالیآزمون"            # مالی: رشد صورتِ مالی +۵۰٪، ۱ب N/A ⇒ پاس
GAP = "بیگزارشآزمون"         # تولیدیِ بی‌گزارشِ ماهانه ⇒ شکافِ داده
PROD_SECTOR = "فلزات اساسي"
FIN_SECTOR = "بانكها و موسسات اعتباري"
GAP_SECTOR = "فلزات اساسي"

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


def _seed_monthly(con, tn0, symbol, cur_m, prev_m, vol_cur, vol_prev):
    """۱۲ ماهِ ۱۴۰۴ و ۱۴۰۳؛ تجمیعیِ ماهِ ۱۲ همان cur_m/prev_m است."""
    tn = tn0
    for year, per_m, prev_per_m, vol in ((1404, cur_m, prev_m, vol_cur),
                                         (1403, prev_m, prev_m * 0.5, vol_prev)):
        for m in range(1, 13):
            tn += 1
            con.execute(
                "INSERT INTO monthly_sales (tracing_no,symbol,title,period_end,"
                "year,month,monthly_revenue,ytd_revenue,ytd_revenue_prev,"
                "monthly_volume,ytd_volume,volume_unit) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (tn, symbol, "گزارش فعالیت ماهانه", "1404/12/29", year, m,
                 per_m, per_m * m, prev_per_m * m,
                 vol, vol, "عدد"))


def _temp_db_case():
    path, con = U11.make_db()
    try:
        _seed_instrument(con, "I31", PROD, "شرکت تولیدی آزمون", PROD_SECTOR)
        _seed_instrument(con, "I32", FIN, "بانک آزمون", FIN_SECTOR)
        _seed_instrument(con, "I33", GAP, "شرکت بی‌گزارش آزمون", GAP_SECTOR)

        # تولیدی: رشد ریالی +۱۰۰٪ (۱۰۰۰ در برابر ۵۰۰ در ماه)، ولی تناژ از
        # ۱۰۰۰ به ۱۰۰ افت کرده ⇒ ۱ب باید وتو کند.
        _seed_monthly(con, 7000, PROD, 1000e9, 500e9, 100.0, 1000.0)
        _seed_fs(con, 7100, PROD, "شرکت تولیدی آزمون", [
            ("1402/12/29", 12, 4000e9, "صورت مالی ۱۲ ماهه حسابرسی شده غیرتلفیقی", 1),
            ("1403/12/29", 12, 4000e9, "صورت مالی ۱۲ ماهه حسابرسی شده غیرتلفیقی", 1),
            ("1404/12/29", 12, 4000e9, "صورت مالی ۱۲ ماهه حسابرسی شده غیرتلفیقی", 1),
        ])

        # مالی: بدونِ گزارشِ ماهانه؛ صورتِ مالی میاندوره +۵۰٪ ⇒ ۱ب N/A.
        _seed_fs(con, 7200, FIN, "بانک آزمون", [
            ("1405/06/31", 6, 1500e9, "صورت مالی ۶ ماهه حسابرسی نشده غیرتلفیقی", 0),
            ("1404/06/31", 6, 1000e9, "صورت مالی ۶ ماهه حسابرسی نشده غیرتلفیقی", 0),
            ("1404/12/29", 12, 2200e9, "صورت مالی ۱۲ ماهه حسابرسی شده غیرتلفیقی", 1),
            ("1403/12/30", 12, 2000e9, "صورت مالی ۱۲ ماهه حسابرسی شده غیرتلفیقی", 1),
        ])

        # تولیدیِ بی‌گزارشِ ماهانه: نه ۱الف نه ۱ب ⇒ شکافِ داده (None)، نه وتو.
        _seed_fs(con, 7300, GAP, "شرکت بی‌گزارش آزمون", [
            ("1402/12/29", 12, 4000e9, "صورت مالی ۱۲ ماهه حسابرسی شده غیرتلفیقی", 1),
            ("1403/12/29", 12, 4000e9, "صورت مالی ۱۲ ماهه حسابرسی شده غیرتلفیقی", 1),
            ("1404/12/29", 12, 4000e9, "صورت مالی ۱۲ ماهه حسابرسی شده غیرتلفیقی", 1),
        ])
        con.commit()

        cfg = fts_engine.load_fts_config(os.path.join(ROOT, "fts_thresholds.json"))
        rows = fts_engine.bulk_scan(con, cfg=cfg)
        by_key = {r["symbol_norm"]: r for r in rows}

        def card(sym, sector, name):
            return FD.evaluate_v10(con, sym, cfg=cfg, sector=sector,
                                   company_name=name, has_instrument=True)

        for sym in (PROD, FIN, GAP):
            b = by_key.get(sym)
            chk(b is not None, "bulk_scan contains %s" % sym, sorted(by_key))
            if b is None:
                continue
            for f in ("i1a_pass", "i1b_pass", "i1b_applicable", "i1b_basis",
                      "i1_reason"):
                chk(f in b, "bulk row exposes %s" % f, sorted(b))

        # تولیدی — وتوی ۱ب با دلیلِ یکسان در کارت و جدول
        b = by_key.get(PROD) or {}
        c = card(PROD, PROD_SECTOR, "شرکت تولیدی آزمون")
        v = c["indicators"]["1"]["volume"]
        chk(abs((b.get("rev_growth") or 0) - 100.0) < 0.1,
            "production monetary growth is +100%", b.get("rev_growth"))
        chk(b.get("i1a_pass") is True, "production 1a passes", b.get("i1a_pass"))
        chk(b.get("i1b_applicable") is True, "production 1b applies",
            b.get("i1b_applicable"))
        chk(b.get("i1b_basis") == "reported_quantity",
            "production 1b uses reported quantity", b.get("i1b_basis"))
        chk(b.get("i1b_pass") is False, "production 1b fails on −90% volume",
            b.get("i1b_pass"))
        chk(b.get("i1_pass") is False, "production axis 1 is vetoed",
            b.get("i1_pass"))
        chk(c["passes"]["1_growth"] is False
            and c["indicators"]["1"]["pass"] is False,
            "card axis 1 is vetoed too", c["passes"])
        chk(b.get("i1_reason") == (v.get("reason") or "")
            and bool(b.get("i1_reason")),
            "bulk and card carry the same 1b reason",
            (b.get("i1_reason"), v.get("reason")))
        chk(b.get("i1_reason") == (c["indicators"]["1"].get("reason") or ""),
            "card exposes the axis-1 reason", c["indicators"]["1"].get("reason"))
        chk(b.get("score") == sum(1 for i in (2, 3, 4, 5)
                                  if b.get("i%d_pass" % i) is True),
            "vetoed axis 1 does not score", b.get("score"))

        # مالی — ۱ب N/A است، نه وتو
        b = by_key.get(FIN) or {}
        c = card(FIN, FIN_SECTOR, "بانک آزمون")
        chk(abs((b.get("rev_growth") or 0) - 50.0) < 0.1,
            "financial growth comes from the FS pair", b.get("rev_growth"))
        chk(b.get("i1a_pass") is True, "financial 1a passes", b.get("i1a_pass"))
        chk(b.get("i1b_applicable") is False, "financial 1b is N/A",
            b.get("i1b_applicable"))
        chk(b.get("i1b_basis") == "not_applicable",
            "financial 1b basis is not_applicable", b.get("i1b_basis"))
        chk(b.get("i1_pass") is True and c["passes"]["1_growth"] is True,
            "financial N/A 1b is not a veto", (b.get("i1_pass"), c["passes"]))

        # داده‌گپ — None، نه False
        b = by_key.get(GAP) or {}
        c = card(GAP, GAP_SECTOR, "شرکت بی‌گزارش آزمون")
        chk(b.get("i1a_pass") is False, "gap 1a is not a pass", b.get("i1a_pass"))
        chk(b.get("i1_pass") is None, "gap axis 1 is None", b.get("i1_pass"))
        chk(b.get("i1b_applicable") is True and b.get("i1b_basis") == "unavailable",
            "gap 1b is applicable but unavailable",
            (b.get("i1b_applicable"), b.get("i1b_basis")))
        chk(bool(b.get("i1_reason")), "gap row carries a reason", b.get("i1_reason"))
        chk(bool(c["passes"]["1_growth"]) is bool(b.get("i1_pass")),
            "card and bulk agree on the gap verdict",
            (c["passes"]["1_growth"], b.get("i1_pass")))

        # پاریتیِ کاملِ دیکشنریِ ۱ب بینِ کارت و ردیف برایِ تولیدی
        b = by_key.get(PROD) or {}
        c = card(PROD, PROD_SECTOR, "شرکت تولیدی آزمون")
        v = c["indicators"]["1"]["volume"]
        chk(all(b.get("i1b_" + k) == v.get(k) for k in ("pass", "applicable", "basis")),
            "bulk i1b_* mirrors the card volume dict",
            {k: (b.get("i1b_" + k), v.get(k))
             for k in ("pass", "applicable", "basis")})
    finally:
        con.close()
        shutil.rmtree(os.path.dirname(path), ignore_errors=True)


def _run_main():
    _temp_db_case()
    print("ind1b-parity: %d pass / %d fail" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(_run_main())
