# -*- coding: utf-8 -*-
"""dev/test_fts_ind4_v11.py — مسیرِ پذیرش و برچسبِ سالانه‌سازیِ شاخص ۴ (Task 7).

قاعدهٔ مالک دست‌نخورده است: دروازهٔ OR با «فروش سالانه ÷ ارزش بازار ≥ ۰٫۳۳×»
(مسیر اول) و «پتانسیل سود ناخالص ÷ ارزش بازار ≥ ۴۰٪» (مسیر دوم — سند v2.1).
این آزمون فقط **نامِ مسیرِ پذیرفته‌شده** و **برچسبِ سالانه‌سازی** را می‌سنجد:
`acceptance_path` ∈ {sales_to_mcap, profit_potential, None} و
`annualize_label` = «سالانه‌شده از دورهٔ N ماهه». یک برچسب برایِ یکِ نماد در
هر سه سطح: کارت (`evaluate_v10`)، ردیفِ `bulk_scan` و `scan_symbol`.
معاف/بی‌داده (هلدینگ/مالی/صندوق یا نبودِ فروش) هیچ مسیری نمی‌گیرد.

اجرا:  python dev/test_fts_ind4_v11.py
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
from api.fundamental import ind4_valuation                 # noqa: E402
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

PATHS = ("sales_to_mcap", "profit_potential", None)
LABEL = "سالانه‌شده از دورهٔ %d ماهه"


def annual_full(sales_mrl=600e9, months=6, basis="تجمیعی 06/1405 × ۱۲÷۶"):
    """همان شکلِ `fts_engine.annualized_sales` — کلیدهایِ نمایشی هم حاضرند."""
    return {"annual_sales_mrl": sales_mrl,
            "annual_sales_bt": round(sales_mrl * 1e-4, 1),
            "months_used": months,
            "scale_factor": round(12.0 / max(int(months or 12), 1), 4),
            "basis": basis, "reconciled": True}


def ratio(mcap_rials, sales_mrl=600e9):
    return sales_mrl * 1e6 / mcap_rials


# ═══════════════════════════════════════════════════════════════════════════
#  ۱) همان آزمونِ brief — «فروش ÷ ارزش بازار» مسیرِ اول است
# ═══════════════════════════════════════════════════════════════════════════
annual = {"annual_sales_mrl": 1_000_000.0, "months_used": 6}
gm = {"margin_pct": 50.0}
th_brief = {"sales_to_mcap_min": 0.33, "profit_potential_min": 40.0}
r = ind4_valuation(annual, gm, market_cap_rials=2_000_000.0, th=th_brief)
chk(r["acceptance_path"] == "sales_to_mcap", r)
chk("۶" in r["annualize_label"] or "6" in r["annualize_label"], r)
chk(r.get("annualize_months") == 6, "annualize_months از months_used",
    r.get("annualize_months"))
chk(r.get("annualize_label") == LABEL % 6,
    "برچسب دقیقاً «سالانه‌شده از دورهٔ ۶ ماهه» است", r.get("annualize_label"))
chk(r.get("pass") is True and r.get("sales_pass") is True,
    "پذیرش با فروش÷ارزش بازار (OR دست‌نخورده)", (r.get("pass"), r.get("sales_pass")))

# ═══════════════════════════════════════════════════════════════════════════
#  ۲) دو مسیر و اولویتِ مسیرِ اول (فروش مقدم است)
# ═══════════════════════════════════════════════════════════════════════════
# فروش پاس، پتانسیل مردود: نسبت ۰٫۴ (≥۰٫۳۳) با حاشیهٔ ۲۰٪ ⇒ پتانسیل ۸٪.
r = ind4_valuation(annual_full(600e9), {"margin_pct": 20.0}, 1.5e18)
chk(round(ratio(1.5e18), 2) == 0.40, "پیش‌فرض: نسبت فروش ۰٫۴۰", ratio(1.5e18))
chk(r["sales_pass"] is True and r["potential_pass"] is False,
    "مسیر اول: فروش پاس و پتانسیل مردود",
    (r["sales_pass"], r["potential_pass"], r.get("potential_pct")))
chk(r["acceptance_path"] == "sales_to_mcap", "acceptance_path مسیر اول",
    r.get("acceptance_path"))

# پتانسیل پاس، فروش مردود: نسبت ۰٫۲ با حاشیهٔ ۲۱۰٪ ⇒ پتانسیل ۴۲٪.
r = ind4_valuation(annual_full(600e9), {"margin_pct": 210.0}, 3.0e18)
chk(r["sales_pass"] is False and r["potential_pass"] is True,
    "مسیر دوم: فروش مردود و پتانسیل پاس",
    (r["sales_pass"], r["potential_pass"], r.get("potential_pct")))
chk(r["acceptance_path"] == "profit_potential",
    "acceptance_path مسیر دوم (پتانسیل ۴۰٪)", r.get("acceptance_path"))
chk(r.get("pass") is True, "پذیرش OR با مسیر دوم", r.get("pass"))

# هر دو پاس: مسیر اول برنده است (همان conditionalِ brief).
r = ind4_valuation(annual_full(600e9), {"margin_pct": 50.0}, 6.0e17)
chk(r["sales_pass"] is True and r["potential_pass"] is True,
    "پیش‌فرضِ هر دو پاس", (r["sales_pass"], r["potential_pass"]))
chk(r["acceptance_path"] == "sales_to_mcap",
    "اولویت: با پاسِ هر دو مسیر، نامِ مسیر اول می‌آید", r.get("acceptance_path"))

# هیچ‌کدام: نسبت ۰٫۰۶۷ با حاشیهٔ ۳۵٪ ⇒ پتانسیل ۲٫۳٪.
r = ind4_valuation(annual_full(600e9), {"margin_pct": 35.0}, 9.0e18)
chk(r["sales_pass"] is False and r["potential_pass"] is False,
    "پیش‌فرضِ هیچ‌کدام", (r["sales_pass"], r["potential_pass"]))
chk(r["pass"] is False and r["acceptance_path"] is None,
    "بدونِ مسیر: acceptance_path=None و pass=False",
    (r.get("pass"), r.get("acceptance_path")))

# ═══════════════════════════════════════════════════════════════════════════
#  ۳) آستانه‌های ۰٫۳۳ و ۴۰٪ دست‌نخورده‌اند (فقط برچسب اضافه شد)
# ═══════════════════════════════════════════════════════════════════════════
r = ind4_valuation(annual_full(600e9), {"margin_pct": 100.0}, 600e9 * 1e6 / 0.3299)
chk(r["sales_pass"] is False and r["potential_pass"] is False
    and r["acceptance_path"] is None,
    "۰٫۳۲۹۹× زیرِ کفِ ۰٫۳۳ ⇒ بی‌مسیر",
    (r.get("sales_to_mcap"), r.get("pass"), r.get("acceptance_path")))
r = ind4_valuation(annual_full(600e9), {"margin_pct": 100.0}, 600e9 * 1e6 / 0.3301)
chk(r["sales_pass"] is True and r["acceptance_path"] == "sales_to_mcap",
    "۰٫۳۳۰۱× بالای کفِ ۰٫۳۳ ⇒ مسیر اول",
    (r.get("sales_to_mcap"), r.get("acceptance_path")))

r = ind4_valuation(annual_full(1998.0), {"margin_pct": 200.0}, 1.0e10)
chk(r["sales_pass"] is False and r["potential_pass"] is False,
    "پتانسیلِ خام ۳۹٫۹۶٪ هنوز «≥۴۰» نیست",
    (r.get("potential_pct"), r.get("potential_pass")))
r = ind4_valuation(annual_full(1998.0), {"margin_pct": 202.0}, 1.0e10)
chk(r["potential_pass"] is True and r["acceptance_path"] == "profit_potential",
    "پتانسیلِ خام ۴۰٫۳۶٪ مسیر دوم را باز می‌کند",
    (r.get("potential_pct"), r.get("acceptance_path")))

# اعدادِ آستانه از خودِ پاسخ (۰٫۳۳ و ۴۰) — بی‌تغییر.
r = ind4_valuation(annual_full(600e9), {"margin_pct": 20.0}, 1.5e18, th=None)
chk(r.get("sales_threshold") == 0.33, "sales_threshold همان ۰٫۳۳ است",
    r.get("sales_threshold"))
chk(r.get("potential_threshold") == 40.0, "potential_threshold همان ۴۰٪ است",
    r.get("potential_threshold"))
# نامِ کلیدِ آستانه در پیکربندیِ خام «profit_potential_min» است و در
# `v10_thresholds` به «potential_min» نگاشت می‌شود؛ هر دو یک عددند.
r = ind4_valuation(annual_full(1998.0), {"margin_pct": 202.0}, 1.0e10,
                   th={"sales_to_mcap_min": 0.33, "profit_potential_min": 40.0})
chk(r.get("potential_threshold") == 40.0 and r["potential_pass"] is True,
    "آستانه از کلیدِ خامِ پیکربندی هم خوانده می‌شود",
    (r.get("potential_threshold"), r.get("potential_pass")))

# ═══════════════════════════════════════════════════════════════════════════
#  ۴) معاف/N/A و بی‌داده — هیچ مسیری، هیچ برچسبی، هیچ عددِ ساختگی
# ═══════════════════════════════════════════════════════════════════════════
r = ind4_valuation(annual_full(600e9), {"margin_pct": 210.0}, 3.0e18, exempt=True)
chk(r.get("available") is False and r.get("na") is True,
    "هلدینگ/مالی: معاف (N/A)، نه پاس و نه رد",
    (r.get("available"), r.get("na")))
chk(r.get("acceptance_path") is None,
    "معاف: acceptance_path=None (حتی اگر پتانسیل عدد داشت)", r.get("acceptance_path"))
chk(r.get("annualize_months") == 0 and r.get("annualize_label") == "",
    "معاف: بی‌برچسبِ سالانه‌سازی",
    (r.get("annualize_months"), r.get("annualize_label")))
chk(r.get("pass") is False and r.get("sales_pass") is False
    and r.get("potential_pass") is False,
    "معاف: هیچ پاسِ رایگانی نمی‌سازد",
    (r.get("pass"), r.get("sales_pass"), r.get("potential_pass")))

r = ind4_valuation(None, {"margin_pct": 50.0}, 1.0e18)
chk(r.get("available") is False and r.get("acceptance_path") is None,
    "نبودِ فروش سالانه: available=False و بی‌مسیر",
    (r.get("available"), r.get("acceptance_path")))
chk(r.get("annualize_label") == "" and r.get("annualize_months") == 0,
    "نبودِ فروش: برچسبِ سالانه‌سازی خالی است",
    (r.get("annualize_label"), r.get("annualize_months")))

r = ind4_valuation(annual_full(600e9), {"margin_pct": 210.0}, 0.0)
chk(r.get("available") is False and r.get("acceptance_path") is None,
    "نبودِ ارزش بازار: available=False و بی‌مسیر",
    (r.get("available"), r.get("acceptance_path")))
chk(r.get("annualize_label") == "", "نبودِ ارزش بازار: بی‌برچسب",
    r.get("annualize_label"))

# ═══════════════════════════════════════════════════════════════════════════
#  ۵) قراردادِ helper ها — یک قاعده، دو مسیر
# ═══════════════════════════════════════════════════════════════════════════
for m in range(1, 13):
    chk(fts_engine.annualize_label(m) == LABEL % m,
        "annualize_label(%d) = «سالانه‌شده از دورهٔ %d ماهه»" % (m, m),
        fts_engine.annualize_label(m))
for m in (0, None, "", "x"):
    chk(fts_engine.annualize_label(m) == "",
        "annualize_label(%r) خالی است" % (m,), fts_engine.annualize_label(m))
chk(fts_engine.i4_acceptance_path(True, True) == "sales_to_mcap",
    "acceptance helper: هر دو ⇒ مسیر اول")
chk(fts_engine.i4_acceptance_path(False, True) == "profit_potential",
    "acceptance helper: فقط پتانسیل ⇒ مسیر دوم")
chk(fts_engine.i4_acceptance_path(False, False) is None,
    "acceptance helper: هیچ‌کدام ⇒ None")
chk(fts_engine.i4_acceptance_path(None, None) is None,
    "acceptance helper: معاف (None) ⇒ None")

print("OK ind4 paths")
print("%d/%d passed" % (PASS, PASS + FAIL))


# ═══════════════════════════════════════════════════════════════════════════
#  ۶) DB موقت — کارت، ردیفِ bulk و scan_symbol یک مسیر/برچسب می‌دهند
# ═══════════════════════════════════════════════════════════════════════════
FS_COLS = ("tracing_no,symbol,company_name,title,report_kind,period_months,"
           "period_end,publish_date,revenue,gross_profit,operating_profit,"
           "net_profit,total_assets,total_liabilities,total_equity,capital,"
           "retained_earnings,basic_eps,unit,url,fetched_at,is_audited,"
           "is_consolidated,fiscal_year,unit_norm,has_operating_sales")

SEC = "فلزات اساسي"
AUD = "صورت مالی سالانه حسابرسی شده"
# (symbol, company name, sector, margin%, mcap ریال, monthly?, نوعِ انتظاری)
# نوع: sales/potential/both/none = سنجیده‌شده؛ holding = معاف؛ nodata = بی‌فروش.
CASES = [
    ("شالف", "شرکت شالف", SEC, 20.0, 1.5e18, True, "sales"),
    ("شبتا", "شرکت شبتا", SEC, 210.0, 3.0e18, True, "potential"),
    ("شجار", "شرکت شجار", SEC, 50.0, 6.0e17, True, "both"),
    ("شدال", "شرکت شدال", SEC, 35.0, 9.0e18, True, "none"),
    # هلدینگ با فروش/حاشیهٔ عدددار: معافیت باید برچسبِ مسیر نسازد.
    ("شههلد", "شرکت سرمایه گذاری شههلد", "سرمایه گذاری", 58.0, 1.0e14, True, "holding"),
    # تولیدیِ بی‌فروش (نه ماهانه، نه صورتِ مالیِ عدددار): بی‌داده، نه مسیرِ ساختگی.
    ("شوبی", "شرکت شوبی", SEC, 0.0, 1.0e14, False, "nodata"),
    # تولیدی با صورتِ مالیِ سالانه و ماهانه، ولی ارزش بازارِ صفر: کارت این را
    # «دادهٔ ناکافی» می‌خواند (available=False) ⇒ هر سه سطح باید ۰/"" بدهند.
    ("شصفر", "شرکت شصفر", SEC, 50.0, 0.0, True, "zeromcap"),
]
WANT_PATH = {"sales": "sales_to_mcap", "potential": "profit_potential",
             "both": "sales_to_mcap", "none": None, "holding": None,
             "nodata": None, "zeromcap": None}
NO_DATA = "شوبی"
HOLDING = "شههلد"
ZERO_MCAP = "شصفر"


def _seed_instrument(con, code, symbol, name, sector, mcap):
    shares = 1e9
    price = mcap / shares
    con.execute(
        "INSERT INTO instruments (ins_code,l_val18,l_val30,sector_code,"
        "sector_name,total_shares,eps,pe,base_vol,updated_at,paper_type) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (code, symbol, name, "", sector, shares, 500, 10, 1, "2026-09-09", 1))
    con.execute(
        "INSERT INTO market_watch (ins_code,d_even,p_closing,total_shares,"
        "sector_code,market_cap,market_cap_src) VALUES (?,?,?,?,?,?,?)",
        (code, 20260909, price, shares, "", mcap, "tse_raw"))
    con.execute(
        "INSERT INTO daily_prices (ins_code,d_even,p_closing,q_tot_cap) "
        "VALUES (?,?,?,?)", (code, 20260909, price, mcap))


def _seed_fs(con, tn0, symbol, name, margin, rev=1000e9):
    """سه سالِ سالانهٔ حسابرسی‌شدهٔ غیرتلفیقی؛ حاشیه از سود ناخالصِ خام."""
    gp = rev * margin / 100.0
    for i, fy in enumerate((1402, 1403, 1404)):
        con.execute(
            "INSERT INTO financial_statements (" + FS_COLS + ") "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tn0 + i, symbol, name, AUD, "annual", 12, "%d/12/29" % fy,
             "2026-08-01", rev, gp, rev * 0.30, rev * 0.22,
             900e9, 800e9, 100e9, 100e9, 40e9, 100.0 * (i + 1),
             "mrl", None, "t", 1, 0, str(fy), "mrl", 1))


def _seed_monthly(con, tn0, symbol, per_m=50e9):
    """شش ماهِ ۱۴۰۵؛ YTDِ ماهِ ۶ = ۳۰۰ میلیارد ریال ⇒ سالانه‌شدهٔ ۶۰۰."""
    for m in range(1, 7):
        con.execute(
            "INSERT INTO monthly_sales (tracing_no,symbol,title,period_end,"
            "year,month,monthly_revenue,ytd_revenue,ytd_revenue_prev,"
            "pdf_url,excel_url) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (tn0 + m, symbol, "گزارش فعالیت ماهانه", "1405/06/31", 1405, m,
             per_m, per_m * m, per_m * m * 0.8, None, None))


def _temp_db_case():
    path, con = U11.make_db()
    try:
        for i, (sym, name, sec, margin, mcap, monthly, kind) in enumerate(CASES):
            _seed_instrument(con, "M7%d" % (i + 1), sym, name, sec, mcap)
            _seed_fs(con, 7100 + i * 10, sym, name, margin,
                     rev=0.0 if kind == "nodata" else 1000e9)
            if monthly:
                _seed_monthly(con, 7500 + i * 10, sym)
        con.commit()

        cfg = fts_engine.load_fts_config(os.path.join(ROOT, "fts_thresholds.json"))
        rows = fts_engine.bulk_scan(con, cfg=cfg)
        by_key = {r["symbol_norm"]: r for r in rows}

        def card(sym, name, sec, mcap):
            return FD.evaluate_v10(con, sym, mcap, 2.0e15, sec, cfg=cfg,
                                   company_name=name, has_instrument=True)

        def scan(sym, sec, mcap):
            return fts_engine.scan_symbol(con, sym, mcap, 2.0e15, sec, cfg=cfg)

        for sym, name, sec, margin, mcap, monthly, kind in CASES:
            # `kind` فقط نامِ کوتاهِ سناریو است؛ مسیرِ انتظاری از نگاشت می‌آید.
            want = WANT_PATH[kind]
            key = fts_engine.norm_fa(sym)
            b = by_key.get(key)
            chk(b is not None, "%s در bulk_scan هست" % sym, sorted(by_key))
            if b is None:
                continue
            chk("i4_acceptance_path" in b,
                "ردیفِ bulk کلیدِ i4_acceptance_path دارد", sorted(b))
            chk("annualize_label" in b,
                "ردیفِ bulk کلیدِ annualize_label دارد", sorted(b))
            chk(b.get("i4_acceptance_path") == want,
                "bulk %s ⇒ مسیر %r" % (sym, want),
                b.get("i4_acceptance_path"))
            chk(b.get("i4_acceptance_path") in PATHS,
                "مسیرِ bulk در قراردادِ سه‌مقداره است", b.get("i4_acceptance_path"))
            chk(bool(b.get("i4_pass")) is (want is not None),
                "bulk %s: pass همان وجودِ مسیر است" % sym,
                (b.get("i4_pass"), want))

            c4 = card(sym, name, sec, mcap)["indicators"]["4"]
            chk(c4.get("acceptance_path") == want,
                "card %s ⇒ مسیر %r" % (sym, want),
                c4.get("acceptance_path"))
            s = scan(sym, sec, mcap)
            chk(s.get("i4_acceptance_path") == want,
                "scan_symbol %s ⇒ مسیر %r" % (sym, want),
                s.get("i4_acceptance_path"))
            chk(c4.get("acceptance_path") == b.get("i4_acceptance_path")
                == s.get("i4_acceptance_path"),
                "پاریتیِ مسیرِ bulk/card/scan برایِ %s" % sym,
                (b.get("i4_acceptance_path"), c4.get("acceptance_path"),
                 s.get("i4_acceptance_path")))

            if sym == NO_DATA:
                # بی‌فروشِ تولیدی: بی‌داده ⇒ نه مسیر، نه برچسبِ ساختگی.
                chk(b.get("annualize_months") == 0 and b.get("annualize_label") == "",
                    "bulk بی‌داده: ماه=۰ و بی‌برچسب",
                    (b.get("annualize_months"), b.get("annualize_label")))
                chk(c4.get("available") is False,
                    "card بی‌داده: available=False", c4.get("available"))
                chk(c4.get("annualize_label") == "",
                    "card بی‌داده: بی‌برچسب", c4.get("annualize_label"))
            elif kind == "holding":
                # هلدینگ معاف: جدول/کارت/موتور همه بی‌مسیر و بی‌برچسب،
                # و pass «نظر نمی‌دهد» (None) است — نه Falseِ ساختگی.
                chk(b.get("i4_pass") is None,
                    "bulk معاف %s: «نظر نمی‌دهد» (None)" % sym, b.get("i4_pass"))
                chk(b.get("annualize_label") == "",
                    "bulk معاف %s: بی‌برچسبِ سالانه‌سازی" % sym,
                    b.get("annualize_label"))
                chk(b.get("annualize_months") == 0,
                    "bulk معاف %s: ماه=۰ (نه ۱۲)" % sym,
                    b.get("annualize_months"))
                chk(c4.get("na") is True or c4.get("exempt") is True,
                    "card معاف %s: N/A" % sym, (c4.get("na"), c4.get("exempt")))
                chk(c4.get("annualize_label") == "",
                    "card معاف %s: بی‌برچسب" % sym, c4.get("annualize_label"))
                chk(c4.get("annualize_months") == 0,
                    "card معاف %s: ماه=۰" % sym, c4.get("annualize_months"))
                chk(s.get("passes", {}).get("4_sales_to_mcap") is None,
                    "scan معاف %s: شاخص ۴ None" % sym,
                    s.get("passes", {}).get("4_sales_to_mcap"))
                chk(s.get("annualize_label") == "",
                    "scan معاف %s: بی‌برچسب" % sym, s.get("annualize_label"))
                chk(s.get("annualize_months") == 0,
                    "scan معاف %s: ماه=۰ (نه ۱۲)" % sym,
                    s.get("annualize_months"))
            elif kind == "zeromcap":
                # سالانه + ماهانه ولی mcap=0: کارت مرجع است (شاخهٔ دادهٔ ناکافی)
                # و هر سه سطح باید مسیرِ None، ماه=۰ و برچسبِ خالی بدهند.
                chk("i4_acceptance_path" in b and b.get("i4_acceptance_path") is None,
                    "bulk mcap=0 %s: مسیر None (کلید حاضر)" % sym,
                    b.get("i4_acceptance_path"))
                chk("annualize_months" in b and b.get("annualize_months") == 0,
                    "bulk mcap=0 %s: ماه=۰" % sym, b.get("annualize_months"))
                chk("annualize_label" in b and b.get("annualize_label") == "",
                    "bulk mcap=0 %s: بی‌برچسب" % sym, b.get("annualize_label"))
                chk(b.get("i4_pass") is False,
                    "bulk mcap=0 %s: i4_pass=False" % sym, b.get("i4_pass"))
                chk("acceptance_path" in c4 and c4.get("acceptance_path") is None,
                    "card mcap=0 %s: مسیر None (کلید حاضر)" % sym,
                    c4.get("acceptance_path"))
                chk("annualize_months" in c4 and c4.get("annualize_months") == 0,
                    "card mcap=0 %s: ماه=۰" % sym, c4.get("annualize_months"))
                chk("annualize_label" in c4 and c4.get("annualize_label") == "",
                    "card mcap=0 %s: بی‌برچسب" % sym, c4.get("annualize_label"))
                chk(c4.get("available") is False,
                    "card mcap=0 %s: available=False (دادهٔ ناکافی)" % sym,
                    c4.get("available"))
                chk("i4_acceptance_path" in s and s.get("i4_acceptance_path") is None,
                    "scan mcap=0 %s: مسیر None (کلید حاضر)" % sym,
                    s.get("i4_acceptance_path"))
                chk("annualize_months" in s and s.get("annualize_months") == 0,
                    "scan mcap=0 %s: ماه=۰" % sym, s.get("annualize_months"))
                chk("annualize_label" in s and s.get("annualize_label") == "",
                    "scan mcap=0 %s: بی‌برچسب" % sym, s.get("annualize_label"))
            elif want is None:
                # تولیدیِ سنجیده‌شده با هیچ مسیرِ پاس: حکم «رد» (False) است،
                # نه N/A؛ مسیر None می‌ماند ولی برچسبِ سالانه‌سازی هست، چون
                # داده و دوره وجود دارد (برچسب، برچسبِ داده است نه برچسبِ پذیرش).
                chk(b.get("i4_pass") is False,
                    "bulk بدونِ‌مسیر %s: i4_pass=False (نه None)" % sym,
                    b.get("i4_pass"))
                chk("i4_acceptance_path" in b and b.get("i4_acceptance_path") is None,
                    "bulk بدونِ‌مسیر %s: مسیر None (کلید حاضر)" % sym,
                    b.get("i4_acceptance_path"))
                chk("annualize_months" in b and b.get("annualize_months") == 6,
                    "bulk بدونِ‌مسیر %s: م=۶" % sym, b.get("annualize_months"))
                chk("annualize_label" in b and b.get("annualize_label") == LABEL % 6,
                    "bulk بدونِ‌مسیر %s: برچسبِ ۶ ماه" % sym,
                    b.get("annualize_label"))
                chk(c4.get("available") is True and c4.get("pass") is False,
                    "card بدونِ‌مسیر %s: available=True و pass=False" % sym,
                    (c4.get("available"), c4.get("pass")))
                chk("acceptance_path" in c4 and c4.get("acceptance_path") is None,
                    "card بدونِ‌مسیر %s: مسیر None (کلید حاضر)" % sym,
                    c4.get("acceptance_path"))
                chk("annualize_months" in c4 and c4.get("annualize_months") == 6,
                    "card بدونِ‌مسیر %s: م=۶" % sym, c4.get("annualize_months"))
                chk("annualize_label" in c4 and c4.get("annualize_label") == LABEL % 6,
                    "card بدونِ‌مسیر %s: برچسبِ ۶ ماه" % sym,
                    c4.get("annualize_label"))
                chk(s.get("passes", {}).get("4_sales_to_mcap") is False,
                    "scan بدونِ‌مسیر %s: شاخص ۴ False" % sym,
                    s.get("passes", {}).get("4_sales_to_mcap"))
                chk("i4_acceptance_path" in s and s.get("i4_acceptance_path") is None,
                    "scan بدونِ‌مسیر %s: مسیر None (کلید حاضر)" % sym,
                    s.get("i4_acceptance_path"))
                chk("annualize_months" in s and s.get("annualize_months") == 6,
                    "scan بدونِ‌مسیر %s: م=۶" % sym, s.get("annualize_months"))
                chk("annualize_label" in s and s.get("annualize_label") == LABEL % 6,
                    "scan بدونِ‌مسیر %s: برچسبِ ۶ ماه" % sym,
                    s.get("annualize_label"))
            else:
                chk(b.get("annualize_months") == 6,
                    "bulk %s: م=۶" % sym, b.get("annualize_months"))
                chk(b.get("annualize_label") == LABEL % 6,
                    "bulk %s: «سالانه‌شده از دورهٔ ۶ ماهه»" % sym,
                    b.get("annualize_label"))
                chk(c4.get("annualize_months") == 6,
                    "card %s: م=۶" % sym, c4.get("annualize_months"))
                chk(c4.get("annualize_label") == LABEL % 6,
                    "card %s: برچسبِ ۶ ماه" % sym, c4.get("annualize_label"))
                chk(c4.get("annualize_label") == b.get("annualize_label"),
                    "پاریتیِ برچسبِ card/bulk برایِ %s" % sym,
                    (b.get("annualize_label"), c4.get("annualize_label")))
                chk(s.get("annualize_months") == 6,
                    "scan %s: م=۶" % sym, s.get("annualize_months"))
                chk(s.get("annualize_label") == LABEL % 6,
                    "scan %s: برچسبِ ۶ ماه" % sym, s.get("annualize_label"))
                chk(s.get("annualize_label") == b.get("annualize_label"),
                    "پاریتیِ برچسبِ scan/bulk برایِ %s" % sym,
                    (b.get("annualize_label"), s.get("annualize_label")))
                # آستانه‌ها از خودِ پاسخ — همان ۰٫۳۳ و ۴۰.
                chk(c4.get("sales_threshold") == 0.33,
                    "card %s: کفِ فروش ۰٫۳۳" % sym, c4.get("sales_threshold"))
                chk(c4.get("potential_threshold") == 40.0,
                    "card %s: کفِ پتانسیل ۴۰٪" % sym,
                    c4.get("potential_threshold"))

        # مقایسهٔ دو مسیر در DB: هر کدام با شاهدِ عددیِ خودش.
        names = {sym: name for sym, name, _s, _m, _c, _mo, _p in CASES}
        for sym, want in (("شالف", "sales_to_mcap"), ("شبتا", "profit_potential")):
            c4 = card(sym, names[sym], SEC,
                      by_key[fts_engine.norm_fa(sym)]["mcap"])["indicators"]["4"]
            chk(c4.get("acceptance_path") == want,
                "کارت %s مسیر را به عدد می‌چسباند" % sym, c4.get("acceptance_path"))
            chk((c4.get("sales_pass") is True) or (c4.get("potential_pass") is True),
                "کارت %s لااقل یک مسیرِ پاس دارد" % sym,
                (c4.get("sales_pass"), c4.get("potential_pass")))
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
