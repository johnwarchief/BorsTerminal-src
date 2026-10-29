# -*- coding: utf-8 -*-
"""dev/test_fts_universe_v11.py — دروازهٔ جهانِ FTS (Task 1).

دو لایه را می‌سنجد:
  ۱) `fts_engine.classify_identity` روی مواردِ ثابت (شرکت، صندوق، بیمه، غیرشرکت).
  ۲) یک DB موقت با اسکیمای کاملِ `market.db` (بدونِ هیچ ردیف) که چهار هویت را
     می‌کارد و ثابت می‌کند `bulk_scan` و `evaluate_v10` یک حرف می‌زنند — به‌ویژه
     شرکتِ واقعیِ بی‌صنعت که باگِ ۲۶ نماد را می‌ساخت (جدول: شرکت، کارت: FTS ندارد).

اجرا:  python dev/test_fts_universe_v11.py   (بدونِ سرور، بدونِ شبکه؛ market.db
فقط برای *اسکیما* و با mode=ro خوانده می‌شود، هیچ نوشتنی رویِ آن نیست.)
"""
import os
import shutil
import sqlite3
import sys
import tempfile

try:                       # پیام‌های فارسی روی کنسولِ cp1252 ویندوز
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import fts_engine                                          # noqa: E402
import codal_periods as CP                                 # noqa: E402
from api import fundamental as FD                          # noqa: E402

PASS = FAIL = 0


def chk(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("  FAIL  %s %s" % (label, extra))


# ═══════════════════════════════════════════════════════════════════════════
#  ۱) classifier — مواردِ ثابت
# ═══════════════════════════════════════════════════════════════════════════
CASES = [
    ("فولاد", "فلزات اساسي", "فولاد مباركه", True, "company", True),
    ("آگاه بازار", "", "", False, "non_company", False),
    ("آبين", "", "كشت و صنعت آبشيرين", True, "company", True),
    ("خیریه نمونه", "", "موسسه خیریه", True, "non_company", False),
    ("شپنا", "فراورده هاي نفتي", "پالايش نفت اصفهان", True, "company", True),
    # بیمه شرکت است، نه صندوق/غیرشرکت — با اینکه نامِ صنعتش «صندوق» دارد.
    ("آسیا", "بيمه وصندوق بازنشستگي به جزتامين اجتماعي", "بيمه آسيا",
     True, "company", True),
    # صندوقِ واقعی (صندوقِ سرمایه‌گذاری قابل معامله) → FTS ندارد.
    ("دارا یکم", "صندوق سرمايه گذاري قابل معامله", "دارا یکم",
     True, "fund", False),
]
for sym, sec, name, inst, kind, applicable in CASES:
    got = fts_engine.classify_identity(sym, sec, name, inst)
    ok = got["kind"] == kind and got["applicable"] is applicable and "reason" in got
    print(("OK  " if ok else "FAIL"), sym, got)
    chk(ok, "classify_identity %s" % sym, got)


# ═══════════════════════════════════════════════════════════════════════════
#  ۲) DB موقت — اسکیمای کامل، بدونِ ردیف
# ═══════════════════════════════════════════════════════════════════════════
# fallback قابل‌حمل اگر market.db روی این ماشین نباشد (CI): همان حداقلی که
# test_fts_results_materialize.py هم می‌سازد + market_totals.
_TSETMC_DDL = """
CREATE TABLE instruments (
    ins_code TEXT PRIMARY KEY, l_val18 TEXT, l_val30 TEXT, sector_code TEXT,
    sector_name TEXT, total_shares REAL, eps REAL, pe REAL, base_vol REAL,
    updated_at TEXT, paper_type INTEGER);
CREATE TABLE market_watch (
    ins_code TEXT PRIMARY KEY, d_even INTEGER, h_even INTEGER, p_closing REAL,
    p_last REAL, price_min REAL, price_max REAL, allowed_min REAL, allowed_max REAL,
    price_yesterday REAL, price_first REAL, q_tot_tran REAL, q_tot_cap REAL,
    z_tot_tran REAL, price_change REAL, eps REAL, pe REAL, total_shares REAL,
    sector_code TEXT, fetched_at TEXT, market_cap REAL, market_cap_src TEXT);
CREATE TABLE daily_prices (
    ins_code TEXT, d_even INTEGER, p_closing REAL, price_min REAL, price_max REAL,
    price_yesterday REAL, price_first REAL, q_tot_tran REAL, q_tot_cap REAL,
    price_change REAL, fetched_at TEXT, market_cap REAL, market_cap_src TEXT,
    PRIMARY KEY (ins_code, d_even));
CREATE TABLE market_totals (
    d_even INTEGER PRIMARY KEY, market_value REAL);
"""


def _real_bank():
    for cand in (os.path.join(ROOT, "market.db"),
                 os.path.join(os.path.dirname(ROOT), "market.db")):
        if os.path.isfile(cand):
            return cand
    return None


def _schema_sql():
    """DDL اشیایِ اسکیمای market.db (جدول/ایندکس/ویو/تریگر)، بدونِ sqlite_*."""
    bank = _real_bank()
    if not bank:
        return None
    ro = sqlite3.connect("file:%s?mode=ro" % bank, uri=True)
    try:
        return [r[0] for r in ro.execute(
            "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL "
            "AND name NOT LIKE 'sqlite_%' ORDER BY rowid")]
    finally:
        ro.close()


def make_db():
    path = os.path.join(tempfile.mkdtemp(prefix="ftsuni_"), "market.db")
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    ddl = _schema_sql()
    if ddl:
        for sql in ddl:
            con.execute(sql)
    else:
        con.executescript(_TSETMC_DDL)
        import codal_fetcher as cf
        cf.create_schema(con)
        cf.migrate_schema(con)

    # چهار هویت: شرکتِ بی‌صنعت (باگِ اصلی)، صندوق، بیمه، غیرشرکت.
    # sector_name شرکت و غیرشرکت عمداً خالی است تا مسیرِ استنتاجِ قدیمی
    # (has_instrument=bool(sector)) همان باگ را برگرداند.
    inst_rows = [
        ("I1", "آبین", "كشت و صنعت آبشيرين", "", ""),
        ("I2", "دارا یکم", "دارا یکم", "70", "صندوق سرمايه گذاري قابل معامله"),
        ("I3", "آسیا", "بيمه آسيا", "61",
         "بيمه وصندوق بازنشستگي به جزتامين اجتماعي"),
        ("I4", "خیریه نمونه", "موسسه خیریه", "", ""),
    ]
    con.executemany(
        "INSERT INTO instruments (ins_code,l_val18,l_val30,sector_code,"
        "sector_name,total_shares,eps,pe,base_vol,updated_at,paper_type) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [(code, l18, l30, sec_code, sec_name, 1e6 * (i + 1), 500, 10, 1,
          "2026-09-09", 1)
         for i, (code, l18, l30, sec_code, sec_name) in enumerate(inst_rows)])
    con.executemany(
        "INSERT INTO market_watch (ins_code,d_even,p_closing,total_shares,"
        "sector_code,market_cap,market_cap_src) VALUES (?,?,?,?,?,?,?)",
        [("I1", 20260909, 2881.0, 1e6, "", 2.0e13, "tse_raw"),
         ("I2", 20260909, 1000.0, 2e6, "70", 2.0e12, "tse_raw"),
         ("I3", 20260909, 5000.0, 3e6, "61", 1.5e13, "tse_raw"),
         ("I4", 20260909, 100.0, 4e6, "", 4.0e11, "tse_raw")])
    con.executemany(
        "INSERT INTO daily_prices (ins_code,d_even,p_closing,q_tot_cap) "
        "VALUES (?,?,?,?)",
        [("I1", 20260909, 2881.0, 2.0e13), ("I2", 20260909, 1000.0, 2.0e12),
         ("I3", 20260909, 5000.0, 1.5e13), ("I4", 20260909, 100.0, 4.0e11)])

    # ماهانه: ۱۲ ماهِ ۱۴۰۴ + ۱۲ ماهِ ۱۴۰۳ (مخرجِ YoY و پهنای رشد).
    plans = {
        "آبین": (1000e9, 500e9, "كشت و صنعت آبشيرين"),
        "دارا یکم": (100e9, 90e9, "دارا یکم"),
        "آسیا": (800e9, 700e9, "بيمه آسيا"),
        "خیریه نمونه": (50e9, 40e9, "موسسه خیریه"),
    }
    tn = 0
    for sym, (cur_m, prv_m, _name) in plans.items():
        for year, per_m, prev_per_m in ((1404, cur_m, prv_m),
                                        (1403, prv_m, prv_m * 0.5)):
            for m in range(1, 13):
                tn += 1
                con.execute(
                    "INSERT INTO monthly_sales (tracing_no,symbol,title,"
                    "period_end,year,month,monthly_revenue,ytd_revenue,"
                    "ytd_revenue_prev,pdf_url,excel_url) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (tn, sym, "گزارش فعالیت ماهانه", "1404/12/29", year, m,
                     per_m, per_m * m, prev_per_m * m, None, None))

    # سالانه: سه سالِ حسابرسی‌شدهٔ غیرتلفیقی (EPS صعودی، حاشیهٔ ۳۵٪).
    fs_tn = 5000
    for sym, (_cur, _prv, name) in plans.items():
        for fy, eps in ((1402, 500.0), (1403, 600.0), (1404, 700.0)):
            fs_tn += 1
            rev = 4000e9
            con.execute(
                "INSERT INTO financial_statements (tracing_no,symbol,"
                "company_name,title,report_kind,period_months,period_end,"
                "publish_date,revenue,gross_profit,operating_profit,"
                "net_profit,total_assets,total_liabilities,total_equity,"
                "capital,retained_earnings,basic_eps,unit,url,fetched_at,"
                "is_audited,is_consolidated,fiscal_year,unit_norm,"
                "has_operating_sales) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (fs_tn, sym, name,
                 "صورت مالی 12 ماهه حسابرسی شده غيرتلفيقي", "annual", 12,
                 "%d/12/29" % fy, "2026-04-01", rev, rev * 0.35,
                 rev * 0.28, rev * 0.21, 500e9, 410e9, 90e9, 100e9, 40e9,
                 eps, "mrl", None, "t", 1, 0, str(fy), "mrl", 1))
    con.commit()
    return path, con


def _temp_db_case():
    path, con = make_db()
    try:
        cfg = fts_engine.load_fts_config(os.path.join(ROOT, "fts_thresholds.json"))
        rows = fts_engine.bulk_scan(con, cfg=cfg)
        by_key = {r["symbol_norm"]: r for r in rows}
        member = set(by_key)

        chk("آبین" in member, "empty-sector real company is in bulk_scan", sorted(member))
        chk("آسیا" in member, "insurer is in bulk_scan", sorted(member))
        chk("دارا یکم" not in member, "fund is absent from bulk_scan", sorted(member))
        chk("خیریه نمونه" not in member,
            "non-company is absent from bulk_scan", sorted(member))

        m141m = fts_engine.m141_map(con)
        liqm = fts_engine.avg_trade_value_hmt(con)
        total_mcap = fts_engine.mstat_engine.market_total_rials(con)[0]
        name_of = {}
        for sym, name in con.execute(
                "SELECT symbol, company_name FROM financial_statements "
                "ORDER BY %s, tracing_no DESC" % CP.order_expr()):
            k = fts_engine.norm_fa(sym)
            if k and k not in name_of:
                name_of[k] = name or ""
        sector_of = {}
        for sym, sec in con.execute(
                "SELECT l_val18, COALESCE(sector_name, '') FROM instruments"):
            k = fts_engine.norm_fa(sym)
            if k and k not in sector_of:
                sector_of[k] = sec or ""

        def card(sym, **kw):
            return FD.evaluate_v10(
                con, sym, cfg=cfg, sector=sector_of.get(sym, ""),
                company_name=name_of.get(sym, ""), m141_map=m141m,
                liq_map=liqm, **kw)

        # شرکتِ بی‌صنعت: هم با has_instrument صریح (مسیرِ جزئیات/اسکرینر) و هم
        # با fallback (فراخوانندهٔ بی‌اطلاع) باید شرکت بماند — قلبِ باگِ ۲۶ نماد.
        c_exp = card("آبین", has_instrument=True)
        chk(c_exp["applicable"] is True and c_exp["identity_kind"] == "company"
            and c_exp["verdict"] != "FTS ندارد",
            "empty-sector company is applicable on the card (explicit instrument)",
            {k: c_exp.get(k) for k in ("applicable", "identity_kind", "verdict")})
        c_fb = card("آبین")
        chk(c_fb["applicable"] is True and c_fb["identity_kind"] == "company",
            "empty-sector company survives the no-instrument fallback",
            {k: c_fb.get(k) for k in ("applicable", "identity_kind", "verdict")})

        c_ins = card("آسیا", has_instrument=True)
        chk(c_ins["applicable"] is True and c_ins["identity_kind"] == "company"
            and c_ins["verdict"] != "FTS ندارد",
            "insurer is a company on the card (veto stays in the risk gate)",
            {k: c_ins.get(k) for k in ("applicable", "identity_kind", "verdict")})
        chk(c_ins["excluded"] is True and "صنعت بیمه" in " ".join(
            c_ins.get("exclusion_reasons") or []),
            "insurer is excluded by the insurance risk gate, not by the universe",
            c_ins.get("exclusion_reasons"))

        c_fund = card("دارا یکم", has_instrument=True)
        chk(c_fund["applicable"] is False and c_fund["identity_kind"] == "fund"
            and c_fund["verdict"] == "FTS ندارد",
            "fund is not applicable on the card",
            {k: c_fund.get(k) for k in ("applicable", "identity_kind", "verdict")})

        c_nc = card("خیریه نمونه", has_instrument=True)
        chk(c_nc["applicable"] is False and c_nc["identity_kind"] == "non_company"
            and c_nc["verdict"] == "FTS ندارد",
            "non-company is not applicable on the card",
            {k: c_nc.get(k) for k in ("applicable", "identity_kind", "verdict")})

        # گاردِ برابری: هر ردیفِ جدول باید در کارت هم applicable باشد و
        # «FTS ندارد» نگیرد — همان چیزی که اسکرینر به کاربر نشان می‌دهد.
        mism = []
        for r in rows:
            key = r["symbol_norm"]
            res = card(key, has_instrument=True)
            if (bool(r.get("applicable", True)) != bool(res.get("applicable"))
                    or res.get("verdict") == "FTS ندارد"):
                mism.append((r["symbol"], r.get("applicable"),
                             res.get("applicable"), res.get("verdict")))
        chk(not mism, "every bulk_scan row agrees with the card", mism[:4])
    finally:
        con.close()
        shutil.rmtree(os.path.dirname(path), ignore_errors=True)


def _run_main():
    _temp_db_case()
    print("fts-universe: %d pass / %d fail" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(_run_main())
