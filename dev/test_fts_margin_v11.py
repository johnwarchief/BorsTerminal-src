# -*- coding: utf-8 -*-
"""dev/test_fts_margin_v11.py — طبقهٔ نمایشیِ حاشیهٔ ناخالص (Task 6).

قاعدهٔ مالک: حکم همچنان با کف ۲۰٪ و استاندارد ۳۰٪ سنجیده می‌شود؛ ۵۰٪ فقط
برچسبِ نمایشیِ «خوب» است و هیچ دروازهٔ تازه‌ای نمی‌سازد. `margin_tier` برایِ
نمادی که حاشیه‌اش ساخته نمی‌شود (مالی/هلدینگ/صندوق/بی‌سطر) باید None باشد،
نه صفرِ کاذب و نه حکمِ تازه. یک برچسب برایِ یکِ نماد در هر سه سطح: کارت
(`ind3_gross_margin`/`evaluate_v10`)، ردیفِ `bulk_scan` و `scan_symbol`.

اجرا:  python dev/test_fts_margin_v11.py
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
from api.fundamental import ind3_gross_margin              # noqa: E402
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

AUD = "صورت مالی سالانه حسابرسی شده"
ALLOWED = {"below_floor", "floor", "standard", "good"}


def ref(gp, rev=1000):
    return {"revenue": rev, "gross_profit": gp, "period_end": "1404/12/29",
            "period_months": 12, "title": AUD}


# ═══════════════════════════════════════════════════════════════════════════
#  ۱) همان دو آزمونِ brief — ۵۸٪ «خوب» و N/A با None
# ═══════════════════════════════════════════════════════════════════════════
c = sqlite3.connect(":memory:")
r = ind3_gross_margin(c, "الف", ref=ref(580))
chk(r["margin_tier"] == "good" and abs(r["margin_pct"] - 58.0) < 0.1,
    "۵۸٪ ⇒ margin_tier=good و margin_pct=58", (r.get("margin_tier"), r.get("margin_pct")))
chk(r.get("pass") is True and r.get("ideal") is True,
    "۵۸٪ همان حکمِ قبلی را دارد (پاس/ایده‌آل)", (r.get("pass"), r.get("ideal")))

r2 = ind3_gross_margin(c, "ب", ref=ref(None))
chk(r2["na"] is True and r2["margin_tier"] is None,
    "سود ناخالصِ غایب ⇒ na=True و margin_tier=None",
    (r2.get("na"), r2.get("margin_tier")))
chk(r2.get("margin_pct") is None and bool(r2.get("reason")),
    "N/A عددِ ساختگی نمی‌سازد ولی دلیلِ قاعده را می‌گوید",
    (r2.get("margin_pct"), bool(r2.get("reason"))))

# helper مستقل هم محدوده‌هایِ قرارداد را نگه می‌دارد.
for pct, want in ((None, None), (19.9, "below_floor"), (20, "floor"),
                  (29.9, "floor"), (30, "standard"), (49.9, "standard"),
                  (50, "good"), (58, "good"), (0, "below_floor"),
                  (-10, "below_floor"), (1885.9, "good")):
    chk(fts_engine.margin_tier(pct) == want, "margin_tier(%r) = %r" % (pct, want),
        fts_engine.margin_tier(pct))

# ═══════════════════════════════════════════════════════════════════════════
#  ۲) مرزها و «۵۰ فقط برچسب است» — حکم دست‌نخورده
# ═══════════════════════════════════════════════════════════════════════════
BOUNDS = [
    (199, "below_floor", False, False),   # ۱۹٫۹٪ زیرِ کف
    (200, "floor", True, False),          # ۲۰٪ کف — پاس، نه ایده‌آل
    (299, "floor", True, False),          # ۲۹٫۹٪ کف
    (300, "standard", True, True),        # ۳۰٪ استاندارد — همان ایده‌آلِ قبلی
    (499, "standard", True, True),        # ۴۹٫۹٪ استاندارد ولی هنوز پاس/ایده‌آل
    (500, "good", True, True),            # ۵۰٪ فقط برچسبِ تازه؛ دروازهٔ تازه نه
    (580, "good", True, True),
]
for gp, want_tier, want_pass, want_ideal in BOUNDS:
    rr = ind3_gross_margin(c, "x", ref=ref(gp))
    pct = round(gp / 10.0, 1)
    chk(rr.get("margin_tier") == want_tier,
        "%s%% ⇒ %s" % (pct, want_tier), rr.get("margin_tier"))
    chk(bool(rr.get("pass")) is want_pass,
        "%s%% ⇒ pass=%s (کف ۲۰٪ دست‌نخورده)" % (pct, want_pass), rr.get("pass"))
    chk(bool(rr.get("ideal")) is want_ideal,
        "%s%% ⇒ ideal=%s (استاندارد ۳۰٪ دست‌نخورده)" % (pct, want_ideal),
        rr.get("ideal"))
    chk(rr.get("margin_tier") in ALLOWED - {None},
        "برچسب در قراردادِ چهارگانه است", rr.get("margin_tier"))

# حاشیهٔ منفیِ واقعی N/A نیست: عدد است و «زیرِ کف».
rr = ind3_gross_margin(c, "منفی", ref=ref(-100))
chk(rr.get("na") is False and rr.get("margin_tier") == "below_floor"
    and rr.get("margin_pct") == -10.0,
    "حاشیهٔ منفیِ واقعی (−۱۰٪) عدد می‌ماند و below_floor است",
    (rr.get("na"), rr.get("margin_tier"), rr.get("margin_pct")))

# گردشدنِ نمایش، برچسب را از حکم جدا نمی‌کند: ۱۹٫۹۶٪ که «۲۰٫۰» دیده می‌شود
# هنوز زیرِ کف است؛ برچسبش هم «کف» نمی‌شود (مبنایِ ۲۰/۳۰ عددِ خام است).
rr = ind3_gross_margin(c, "گرد", ref=ref(1996, rev=10000))
chk(rr.get("margin_pct") == 20.0 and rr.get("pass") is False
    and rr.get("margin_tier") == "below_floor",
    "۱۹٫۹۶٪: نمایش ۲۰٫۰ ولی حکم و برچسب بر مبنایِ عددِ خام (زیرِ کف)",
    (rr.get("margin_pct"), rr.get("pass"), rr.get("margin_tier")))

# صفرِ واقعی هم عدد است، نه N/A.
rr = ind3_gross_margin(c, "صفر", ref=ref(0))
chk(rr.get("na") is False and rr.get("margin_tier") == "below_floor",
    "حاشیهٔ صفرِ واقعی below_floor است، نه N/A",
    (rr.get("na"), rr.get("margin_tier")))

# ═══════════════════════════════════════════════════════════════════════════
#  ۳) مالی/هلدینگ/صندوق و درآمدِ صفر — N/A با دلیلِ قاعده، بی‌برچسب
# ═══════════════════════════════════════════════════════════════════════════
for prof in (fts_engine.company_profile("لیزینگ", "شرکت لیزینگ الف"),
             fts_engine.company_profile("سرمایه گذاری", "شرکت سرمایه گذاری ب"),
             {"kind": "fund"}):
    rn = ind3_gross_margin(c, "مالی", ref=ref(None), profile=prof)
    chk(rn.get("na") is True and rn.get("margin_tier") is None,
        "طبقهٔ %s ⇒ N/A و بی‌برچسب" % prof.get("kind"),
        (rn.get("na"), rn.get("margin_tier")))
    chk(bool(rn.get("reason")),
        "طبقهٔ %s دلیلِ قاعده را می‌گوید" % prof.get("kind"), rn.get("reason"))

rz = ind3_gross_margin(c, "بی‌درآمد", ref=ref(100, rev=0))
chk(rz.get("na") is True and rz.get("margin_tier") is None,
    "درآمدِ صفر ⇒ N/A و بی‌برچسب", (rz.get("na"), rz.get("margin_tier")))

print("OK margin tiers (pure)")
print("%d/%d passed" % (PASS, PASS + FAIL))


# ═══════════════════════════════════════════════════════════════════════════
#  ۴) DB موقت — کارت، ردیفِ bulk و scan_symbol یک برچسب می‌دهند
# ═══════════════════════════════════════════════════════════════════════════
FS_COLS = ("tracing_no,symbol,company_name,title,report_kind,period_months,"
           "period_end,publish_date,revenue,gross_profit,operating_profit,"
           "net_profit,total_assets,total_liabilities,total_equity,capital,"
           "retained_earnings,basic_eps,unit,url,fetched_at,is_audited,"
           "is_consolidated,fiscal_year,unit_norm,has_operating_sales")

SEC = "فلزات اساسي"
# (symbol, company name, sector, gross margin % یا None, برچسبِ انتظاری)
CASES = [
    ("شگود", "شرکت شگود", SEC, 58.0, "good"),
    ("شاستان", "شرکت شاستان", SEC, 35.0, "standard"),
    ("شکف", "شرکت شکف", SEC, 25.0, "floor"),
    ("شزیر", "شرکت شزیر", SEC, 12.0, "below_floor"),
    ("شگرد", "شرکت شگرد", SEC, 19.96, "below_floor"),
    ("شپنجاه", "شرکت شپنجاه", SEC, 50.0, "good"),
    ("شنال", "شرکت شنال", "سرمایه گذاری", None, None),
]


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


def _seed_fs(con, tn0, symbol, name, margin):
    """سه سالِ سالانهٔ حسابرسی‌شدهٔ غیرتلفیقی؛ gross_profit خام برایِ N/A تهی است."""
    rev = 1000e9
    gp = None if margin is None else rev * margin / 100.0
    for i, fy in enumerate((1402, 1403, 1404)):
        con.execute(
            "INSERT INTO financial_statements (" + FS_COLS + ") "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tn0 + i, symbol, name, AUD, "annual", 12, "%d/12/29" % fy,
             "2026-08-01", rev, gp, rev * 0.30, rev * 0.22,
             900e9, 800e9, 100e9, 100e9, 40e9, 100.0 * (i + 1),
             "mrl", None, "t", 1, 0, str(fy), "mrl", 1))


def _temp_db_case():
    path, con = U11.make_db()
    try:
        for i, (sym, name, sec, _margin, _tier) in enumerate(CASES):
            _seed_instrument(con, "M6%d" % (i + 1), sym, name, sec)
            _seed_fs(con, 6100 + i * 10, sym, name, _margin)
        con.commit()

        cfg = fts_engine.load_fts_config(os.path.join(ROOT, "fts_thresholds.json"))
        rows = fts_engine.bulk_scan(con, cfg=cfg)
        by_key = {r["symbol_norm"]: r for r in rows}

        def card(sym, name, sec):
            return FD.evaluate_v10(con, sym, cfg=cfg, sector=sec,
                                   company_name=name, has_instrument=True)

        def scan(sym, sec):
            return fts_engine.scan_symbol(con, sym, 1.0e14, 2.0e15, sec, cfg=cfg)

        for sym, name, sec, margin, want_tier in CASES:
            key = fts_engine.norm_fa(sym)
            b = by_key.get(key)
            chk(b is not None, "%s در bulk_scan هست" % sym, sorted(by_key))
            if b is None:
                continue
            chk("margin_tier" in b, "ردیفِ bulk کلیدِ margin_tier دارد", sorted(b))
            chk(b.get("margin_tier") == want_tier,
                "bulk %s ⇒ margin_tier=%r" % (sym, want_tier),
                b.get("margin_tier"))
            if margin is None:
                chk(b.get("gross_margin") is None and b.get("i3_pass") is None,
                    "bulk N/A %s: بی‌عدد و «سنجیده نشد»" % sym,
                    (b.get("gross_margin"), b.get("i3_pass")))
                chk(b.get("margin_optimal") is False,
                    "bulk N/A %s: optimalِ کاذب نه" % sym, b.get("margin_optimal"))
            else:
                chk(abs((b.get("gross_margin") or 0) - margin) < 0.1,
                    "bulk %s عددِ حاشیه را نگه می‌دارد" % sym, b.get("gross_margin"))
                chk(b.get("i3_pass") is (margin >= 20.0),
                    "bulk %s حکم را از کف ۲۰٪ می‌گیرد (بی‌گیتِ ۵۰)" % sym,
                    b.get("i3_pass"))
                chk(bool(b.get("margin_optimal")) is (margin >= 30.0),
                    "bulk %s optimal از ۳۰٪ می‌آید" % sym, b.get("margin_optimal"))

            c3 = card(sym, name, sec)["indicators"]["3"]
            chk(c3.get("margin_tier") == want_tier,
                "card %s ⇒ margin_tier=%r" % (sym, want_tier),
                c3.get("margin_tier"))
            chk(c3.get("margin_tier") == b.get("margin_tier"),
                "پاریتیِ برچسبِ bulk/card برایِ %s" % sym,
                (b.get("margin_tier"), c3.get("margin_tier")))
            if margin is None:
                chk(c3.get("na") is True and c3.get("margin_tier") is None,
                    "card N/A %s: na و بی‌برچسب" % sym,
                    (c3.get("na"), c3.get("margin_tier")))
                chk(bool(c3.get("reason")), "card N/A %s دلیل دارد" % sym,
                    c3.get("reason"))

            s = scan(sym, sec)
            chk(s.get("margin_tier") == want_tier,
                "scan_symbol %s ⇒ margin_tier=%r" % (sym, want_tier),
                s.get("margin_tier"))
            d3 = ((s.get("detail") or {}).get("gross_margin") or {})
            chk(d3.get("margin_tier") == want_tier,
                "scan_symbol.detail.gross_margin %s ⇒ margin_tier=%r"
                % (sym, want_tier), d3.get("margin_tier"))

        # نمادِ بی‌صورتِ مالی: کارت N/A و بی‌برچسب، نه استثنا.
        empty = FD.evaluate_v10(con, "بی‌صورت", cfg=cfg, sector=SEC,
                                company_name="شرکت بی‌صورت", has_instrument=True)
        chk(empty["indicators"]["3"].get("na") is True
            and empty["indicators"]["3"].get("margin_tier") is None,
            "نمادِ بی‌صورت: N/A و بی‌برچسب",
            (empty["indicators"]["3"].get("na"),
             empty["indicators"]["3"].get("margin_tier")))
    finally:
        con.close()
        import shutil
        shutil.rmtree(os.path.dirname(path), ignore_errors=True)


_temp_db_case()
print("%d/%d passed" % (PASS, PASS + FAIL))
sys.exit(0 if FAIL == 0 else 1)
