# -*- coding: utf-8 -*-
"""dev/test_fts_monthly_universe_v11.py — شرکت‌هایِ فقط-ماهانه در جهانِ FTS (Task 10A).

`bulk_scan` پیش از این فقط رویِ `annual.keys()` می‌چرخید؛ شرکتی که گزارشِ
فعالیتِ ماهانه دارد ولی صورتِ مالیِ سالانه ندارد در جدولِ بنیادی غایب بود
(۷۳ شرکتِ واقعیِ تابلو). این آزمون رویِ DB موقت می‌سنجد:

  ۱) شرکتِ تولیدیِ فقط-ماهانه (۶ ماهِ ۱۴۰۵، mcap>0) یک‌بار می‌آید؛ شاخص ۱ از
     سریِ ماهانه ساخته می‌شود، شاخص ۲ شکافِ داده است (نه سریِ ساختگی)،
     شاخص ۳ `None` است (نه حاشیهٔ جعلی)، و شاخص ۴ از مسیرِ «فروش ÷ ارزش
     بازار» پاس می‌شود؛ امتیاز فقط True‌هایِ واقعی را می‌شمارد.
  ۲) هلدینگِ فقط-ماهانه: شاخص ۴ `None` (معاف)، بی‌حاشیه و بی‌EPS ساختگی.
  ۳) صندوقِ فقط-ماهانه و نمادِ ماهانهٔ بی‌ابزار (۵۷ نامِ فانتوم) در ردیف‌ها
     نیستند.
  ۴) پاریتیِ کارت (`evaluate_v10`) و `scan_symbol` با ردیفِ bulk رویِ
     i1/i2/i3/i4 + مسیر/برچسبِ سالانه‌سازی (قراردادِ Task 7).

اجرا:  python dev/test_fts_monthly_universe_v11.py
(DB موقت با اسکیمایِ کامل؛ هیچ نوشتنی رویِ market.db نیست.)
"""
import contextlib
import io
import os
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
chk(U11.FAIL == 0, "imported universe fixture (test_fts_universe_v11) is green",
    "%d failing check(s)" % U11.FAIL)

LABEL = "سالانه‌شده از دورهٔ %d ماهه"

# (symbol, sector, mcap ریال, نوع)
# فقط-ماهانه: هیچ ردیفی در financial_statements ندارند.
PROD = "شماهپر"          # تولیدی، ۶ ماهِ ۱۴۰۵، رشد ۱۰۰٪
HOLD = "شهماهلد"         # هلدینگ/سرمایه‌گذاری
FUND = "شهماصندوق"       # صندوق — باید غایب باشد
PHANTOM = "شهماغیر"      # ماهانهٔ بی‌ابزار — باید غایب باشد
NODATA = "شهماغنوش"      # شرکتِ تابلو با یک گزارشِ ماهانهٔ YTDِ منفی (غنوشِ واقعی)
CASES = [
    (PROD, "فلزات اساسي", 1.5e18, "production"),
    (HOLD, "سرمایه گذاری", 1.0e15, "holding"),
    (FUND, "صندوق سرمايه گذاري قابل معامله", 2.0e14, "fund"),
]
WANT_IN = {PROD: True, HOLD: True, FUND: False, PHANTOM: False, NODATA: True}


def _seed_monthly_only(con, tn0, symbol, per_m=50e9, months=6):
    """۶ ماهِ ۱۴۰۵؛ YTDِ ماهِ ۶ = ۳۰۰ میلیارد ریال، مخرجِ سالِ قبل ۱۵۰ ⇒ رشد ۱۰۰٪."""
    for m in range(1, months + 1):
        ytd = per_m * m
        con.execute(
            "INSERT INTO monthly_sales (tracing_no,symbol,title,period_end,"
            "year,month,monthly_revenue,ytd_revenue,ytd_revenue_prev,"
            "pdf_url,excel_url) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (tn0 + m, symbol, "گزارش فعالیت ماهانه", "1405/06/31", 1405, m,
             per_m, ytd, ytd * 0.5, None, None))


def _temp_db_case():
    path, con = U11.make_db()
    try:
        for i, (sym, sec, mcap, _kind) in enumerate(CASES):
            shares = 1e9
            price = mcap / shares
            con.execute(
                "INSERT INTO instruments (ins_code,l_val18,l_val30,sector_code,"
                "sector_name,total_shares,eps,pe,base_vol,updated_at,paper_type) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                ("M9%d" % (i + 1), sym, sym, "", sec, shares, 500, 10, 1,
                 "2026-09-09", 1))
            con.execute(
                "INSERT INTO market_watch (ins_code,d_even,p_closing,total_shares,"
                "sector_code,market_cap,market_cap_src) VALUES (?,?,?,?,?,?,?)",
                ("M9%d" % (i + 1), 20260909, price, shares, "", mcap, "tse_raw"))
            con.execute(
                "INSERT INTO daily_prices (ins_code,d_even,p_closing,q_tot_cap) "
                "VALUES (?,?,?,?)", ("M9%d" % (i + 1), 20260909, price, mcap))
            _seed_monthly_only(con, 7600 + i * 10, sym)
        # فانتوم: گزارشِ ماهانه دارد ولی هیچ ابزاری در تابلو نیست.
        _seed_monthly_only(con, 7900, PHANTOM)
        # شرکتِ تابلو با گزارشِ ماهانهٔ بی‌سریِ قابلِ استفاده (YTD منفی/صفر):
        # مثلِ غنوش در دادهٔ واقعی — باید ردیفِ شکافِ داده بگیرد، نه حذف.
        shares = 1e9
        con.execute(
            "INSERT INTO instruments (ins_code,l_val18,l_val30,sector_code,"
            "sector_name,total_shares,eps,pe,base_vol,updated_at,paper_type) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("M99", NODATA, NODATA, "", "محصولات غذايي و آشاميدني", shares,
             500, 10, 1, "2026-09-09", 1))
        con.execute(
            "INSERT INTO market_watch (ins_code,d_even,p_closing,total_shares,"
            "sector_code,market_cap,market_cap_src) VALUES (?,?,?,?,?,?,?)",
            ("M99", 20260909, 100.0, shares, "", 1e14, "tse_raw"))
        con.execute(
            "INSERT INTO daily_prices (ins_code,d_even,p_closing,q_tot_cap) "
            "VALUES (?,?,?,?)", ("M99", 20260909, 100.0, 1e14))
        con.execute(
            "INSERT INTO monthly_sales (tracing_no,symbol,title,period_end,"
            "year,month,monthly_revenue,ytd_revenue,ytd_revenue_prev,"
            "pdf_url,excel_url) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (7950, NODATA, "گزارش فعالیت ماهانه", "1405/05/31", 1405, 5,
             -62.0, -62.0, None, None, None))
        con.commit()

        # هیچ‌کدام صورتِ مالیِ سالانه ندارند — پیش‌شرطِ خودِ سناریو.
        for sym in (PROD, HOLD, FUND, PHANTOM, NODATA):
            n = con.execute("SELECT COUNT(*) FROM financial_statements "
                            "WHERE symbol=?", (sym,)).fetchone()[0]
            chk(n == 0, "%s هیچ صورتِ مالیِ سالانه ندارد" % sym, n)

        cfg = fts_engine.load_fts_config(os.path.join(ROOT, "fts_thresholds.json"))
        rows = fts_engine.bulk_scan(con, cfg=cfg)
        by_key = {r["symbol_norm"]: r for r in rows}
        total_mcap = fts_engine.mstat_engine.market_total_rials(con)[0]
        sector_of = dict(con.execute(
            "SELECT l_val18, COALESCE(sector_name, '') FROM instruments"))
        mcap_of = {r["symbol_norm"]: r["mcap"] for r in rows}

        # ── ۱) حضور/غیاب ────────────────────────────────────────────────
        for sym, want in WANT_IN.items():
            key = fts_engine.norm_fa(sym)
            n = sum(1 for r in rows if r["symbol_norm"] == key)
            chk(n == (1 if want else 0),
                "%s %s در bulk_scan" % (sym, "یک‌بار می‌آید" if want else "غایب است"),
                "ردیف=%d" % n)
            if not want:
                continue
            b = by_key.get(key)
            chk(b is not None and b.get("symbol") == sym,
                "نمایشِ %s تیکرِ تابلو است (نه کلیدِ نرمال)" % sym,
                (b or {}).get("symbol"))
            chk(b is not None and b.get("identity_kind") == "company",
                "%s شرکت است" % sym, (b or {}).get("identity_kind"))

        # ── ۲) تولیدیِ فقط-ماهانه: i1 محاسبه، i2 شکاف، i3 None، i4 مسیر ──
        b = by_key.get(fts_engine.norm_fa(PROD))
        if b is None:
            chk(False, "ردیفِ تولیدیِ فقط-ماهانه نیست", sorted(by_key))
        else:
            chk(b.get("rev_growth") == 100.0,
                "i1 از سریِ ماهانه محاسبه شد (رشد ۱۰۰٪)", b.get("rev_growth"))
            chk(b.get("i1_pass") is True,
                "i1 پاس (رشد ۱۰۰٪ و چکِ تولیدی مثبت)", b.get("i1_pass"))
            chk(b.get("i1a_pass") is True and b.get("i1b_applicable") is True,
                "تفکیکِ ۱الف/۱ب در ردیف هست",
                (b.get("i1a_pass"), b.get("i1b_applicable")))
            chk(b.get("i2_pass") is False,
                "i2 پاس نیست (بی‌سابقهٔ EPS)", b.get("i2_pass"))
            chk(b.get("i2_na") is False and b.get("eps_data_gap") is True,
                "i2 «شکافِ داده» است، نه N/A و نه سریِ ساختگی",
                (b.get("i2_na"), b.get("eps_data_gap")))
            chk(b.get("eps_series") is None and b.get("eps_last") is None,
                "سریِ EPS ساخته نشد", (b.get("eps_series"), b.get("eps_last")))
            chk(b.get("i3_pass") is None,
                "i3 None است (بی‌حاشیهٔ صورتِ مالی، نه ۰٪)", b.get("i3_pass"))
            chk(b.get("gross_margin") is None and b.get("margin_tier") is None,
                "حاشیهٔ ساختگی/برچسبِ حاشیه ساخته نشد",
                (b.get("gross_margin"), b.get("margin_tier")))
            chk(b.get("i3_na") is False
                and b.get("i3_reason") == FD.margin_gap_detail(None)["reason"],
                "i3 شکافِ داده است (نه N/Aِ طبقه) و دلیلش متنِ کارت است",
                (b.get("i3_na"), b.get("i3_reason")))
            chk(b.get("i4_acceptance_path") == "sales_to_mcap",
                "i4 از مسیرِ فروش ÷ ارزش بازار", b.get("i4_acceptance_path"))
            chk(b.get("i4_pass") is True and b.get("sales_to_mcap") == 0.4,
                "نسبتِ ۰٫۴۰ ≥ ۰٫۳۳ ⇒ پاس", (b.get("i4_pass"),
                                             b.get("sales_to_mcap")))
            chk(b.get("profit_potential_pct") is None,
                "پتانسیل سود بدونِ حاشیه ساخته نشد", b.get("profit_potential_pct"))
            chk(b.get("annualize_months") == 6
                and b.get("annualize_label") == LABEL % 6,
                "برچسبِ سالانه‌سازیِ ۶ ماه (Task 7)",
                (b.get("annualize_months"), b.get("annualize_label")))
            _flags = tuple(b.get("i%d_pass" % i) for i in (1, 2, 3, 4, 5))
            chk(b.get("score") == sum(1 for x in _flags if x is True),
                "امتیاز فقط True‌هایِ واقعی را می‌شمارد (N/A نمره نمی‌گیرد)",
                (b.get("score"), _flags))

        # ── ۳) هلدینگِ فقط-ماهانه: i4 معاف، بی‌حاشیه/بی‌EPS ────────────
        b = by_key.get(fts_engine.norm_fa(HOLD))
        if b is None:
            chk(False, "ردیفِ هلدینگِ فقط-ماهانه نیست", sorted(by_key))
        else:
            chk(b.get("i4_pass") is None and b.get("i4_acceptance_path") is None,
                "هلدینگ: شاخص ۴ «نظر نمی‌دهد» (None)",
                (b.get("i4_pass"), b.get("i4_acceptance_path")))
            chk(b.get("annualize_months") == 0 and b.get("annualize_label") == "",
                "هلدینگ: بی‌دوره/بی‌برچسبِ سالانه‌سازی",
                (b.get("annualize_months"), b.get("annualize_label")))
            chk(b.get("i3_pass") is None and b.get("gross_margin") is None,
                "هلدینگ: حاشیهٔ ساختگی ندارد",
                (b.get("i3_pass"), b.get("gross_margin")))
            chk(b.get("i3_na") is True,
                "هلدینگ: i3 N/Aِ طبقه است (نه شکافِ داده)", b.get("i3_na"))
            chk(b.get("eps_series") is None,
                "هلدینگ: سریِ EPS ساختگی ندارد", b.get("eps_series"))

        # ── ۳ب) ماهانهٔ بی‌سریِ قابلِ استفاده: ردیفِ شکاف، نه حذف ────────
        b = by_key.get(fts_engine.norm_fa(NODATA))
        if b is None:
            chk(False, "ردیفِ شرکتِ ماهانهٔ بی‌YTD نیست", sorted(by_key))
        else:
            chk(b.get("i1_pass") is None and b.get("i1_na") is True,
                "بی‌YTD: i1 «قابل محاسبه نبود» (None)، نه صفر/رد",
                (b.get("i1_pass"), b.get("i1_na")))
            chk(b.get("eps_data_gap") is True and b.get("eps_series") is None,
                "بی‌YTD: i2 شکافِ داده، نه سریِ ساختگی",
                (b.get("eps_data_gap"), b.get("eps_series")))
            chk(b.get("i4_pass") is False and b.get("i4_acceptance_path") is None
                and b.get("annualize_months") == 0
                and b.get("annualize_label") == "",
                "بی‌YTD: i4 بی‌مسیر/بی‌دوره/بی‌برچسب (بدونِ عددِ جعلی)",
                (b.get("i4_pass"), b.get("i4_acceptance_path"),
                 b.get("annualize_months"), b.get("annualize_label")))

        # ── ۴) پاریتیِ کارت/اسکن با ردیفِ bulk (تولیدیِ فقط-ماهانه) ─────
        b = by_key.get(fts_engine.norm_fa(PROD))
        if b is not None:
            key = fts_engine.norm_fa(PROD)
            mcap = b["mcap"]
            sec = sector_of.get(PROD, "")
            card = FD.evaluate_v10(con, PROD, mcap, total_mcap, sec, cfg=cfg,
                                   company_name="", has_instrument=True)
            scan = fts_engine.scan_symbol(con, PROD, mcap, total_mcap, sec, cfg=cfg)
            c4 = card["indicators"]["4"]
            s4 = scan.get("passes", {}).get("4_sales_to_mcap")
            cp = card["passes"]

            chk(bool(b.get("i1_pass")) == bool(cp["1_growth"])
                == bool(scan["passes"]["1_growth"]),
                "پاریتیِ i1 بین bulk/card/scan",
                (b.get("i1_pass"), cp["1_growth"], scan["passes"]["1_growth"]))
            chk(bool(b.get("i2_pass")) == bool(cp["2_eps_trend"])
                == bool(scan["passes"]["2_eps_trend"]),
                "پاریتیِ i2 بین bulk/card/scan",
                (b.get("i2_pass"), cp["2_eps_trend"],
                 scan["passes"]["2_eps_trend"]))
            chk(bool(b.get("i3_pass")) == bool(cp["3_gross_margin"])
                == bool(scan["passes"]["3_gross_margin"]),
                "پاریتیِ i3 بین bulk/card/scan",
                (b.get("i3_pass"), cp["3_gross_margin"],
                 scan["passes"]["3_gross_margin"]))
            chk(bool(b.get("i4_pass")) == bool(s4) == bool(c4.get("pass")),
                "پاریتیِ i4 بین bulk/card/scan",
                (b.get("i4_pass"), s4, c4.get("pass")))
            chk(b.get("i4_acceptance_path") == c4.get("acceptance_path")
                == scan.get("i4_acceptance_path"),
                "پاریتیِ مسیرِ شاخص ۴ (sales_to_mcap)",
                (b.get("i4_acceptance_path"), c4.get("acceptance_path"),
                 scan.get("i4_acceptance_path")))
            chk(b.get("annualize_label") == c4.get("annualize_label")
                == scan.get("annualize_label") == LABEL % 6,
                "پاریتیِ برچسبِ سالانه‌سازی (۶ ماه)",
                (b.get("annualize_label"), c4.get("annualize_label"),
                 scan.get("annualize_label")))
            chk(b.get("annualize_months") == c4.get("annualize_months")
                == scan.get("annualize_months") == 6,
                "پاریتیِ ماهِ سالانه‌سازی (۶)",
                (b.get("annualize_months"), c4.get("annualize_months"),
                 scan.get("annualize_months")))
            chk(c4.get("potential_pct") is None
                and b.get("profit_potential_pct") is None,
                "پتانسیلِ سود در کارت و bulk None است (بی‌حاشیه)",
                (c4.get("potential_pct"), b.get("profit_potential_pct")))
            chk(card.get("ref") is None,
                "کارت هم ref=None می‌بیند (بی‌صورتِ مالی)", card.get("ref"))
            chk(b.get("score") == card.get("score") == scan.get("score"),
                "امتیازِ bulk/card/scan یکی است",
                (b.get("score"), card.get("score"), scan.get("score")))
    finally:
        con.close()
        try:
            os.remove(path)
        except OSError:
            pass


_temp_db_case()
print("%d/%d passed (with temp DB)" % (PASS, PASS + FAIL))
if FAIL:
    raise SystemExit(1)
print("OK monthly-only universe")
