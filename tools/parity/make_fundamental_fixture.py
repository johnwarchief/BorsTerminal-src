#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""فیکسچرِ B4: بنیادیِ پنج‌محور + تاریخچۀ نوار، رویِ پایه‌ایِ فیکسچرِ چارت.

سه جدولِ بازار افزوده می‌شود (monthly_sales، financial_statements، codal_notices)
و دو جدولِ نوار در user.db (tape_flag_day، tape_flag_day_meta). اسکیما عیناً از
همان CREATEهایِ بانکِ عملیاتی است (سنجشِ کپیِ یخ‌زده) تا هیچ ستونی در Go
«درِ فیکسچر هست، درِ تولید نیست» نشود.

پنج نماد، هر کدام برایِ یک شاخه:

  عادی01      تولیدیِ قبول  — رشد تجمیعی از ستون «مقایسه با دورۀ مشابه»،
               شش سالِ صورتِ مالیِ حسابرسی‌شدهِ صعودی، حاشیۀ ~۲۵٪
  پایین02     رد + وتو      — رشدِ صفر، EPSِ نزولی، اطلاعۀ مادۀ ۱۴۱
  اهرم‌ب      صندوق          — «FTS ندارد»، نه REJECT با جدولِ خالی
  کم‌سابقه11  داده‌گپ       — یک گزارشِ ماهانه، بی‌صورتِ مالی، بی‌ارزشِ بازار
  متنوع01    تله‌هایِ ترتیب — دورۀ یکسان با دو نوشتارِ تاریخ (رقمِ فارسی در
               برابرِ ASCII)، دو ردیفِ هم‌سال‌وماه، ردیفِ «شرکتِ دیگر»،
               ytd منفی، gross_profit تهی

هیچ شبکه‌ای، هیچ نوشتنی بیرونِ پوشۀ موقت.
"""
import json
import os
import shutil
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
SRC_FIX = os.path.join(ROOT, "backend-go", "internal", "chart", "testdata", "fixture")
OUT = os.path.join(ROOT, "backend-go", "internal", "fundamental", "testdata", "fixture")

UP, DOWN, FUND, THIN, MIXED = ("عادی01", "پایین02", "اهرم‌ب", "کم‌سابقه11", "متنوع01")

MS_DDL = """CREATE TABLE monthly_sales (
            tracing_no INTEGER PRIMARY KEY,
            symbol TEXT, title TEXT, period_end TEXT,
            year INTEGER, month INTEGER,
            monthly_revenue REAL, ytd_revenue REAL,
            pdf_url TEXT, excel_url TEXT, monthly_revenue_prev REAL, ytd_revenue_prev REAL, monthly_volume REAL, ytd_volume REAL, volume_unit TEXT)"""
FS_DDL = """CREATE TABLE financial_statements (
            tracing_no INTEGER PRIMARY KEY, symbol TEXT, company_name TEXT, title TEXT,
            report_kind TEXT, period_months INTEGER, period_end TEXT, publish_date TEXT,
            revenue REAL, gross_profit REAL, operating_profit REAL, net_profit REAL,
            total_assets REAL, total_liabilities REAL, total_equity REAL, capital REAL,
            retained_earnings REAL, basic_eps REAL, unit TEXT, url TEXT, fetched_at TEXT,
            is_audited INTEGER NOT NULL DEFAULT 0, is_consolidated INTEGER NOT NULL DEFAULT 0,
            fiscal_year TEXT, unit_norm TEXT, has_operating_sales INTEGER)"""
CN_DDL = """CREATE TABLE codal_notices (
            tracing_no INTEGER PRIMARY KEY, symbol TEXT, company_name TEXT, title TEXT,
            letter_code TEXT, publish_date TEXT, sent_date TEXT, url TEXT, fetched_at TEXT,
            pdf_url TEXT, excel_url TEXT)"""
TD_DDL = """CREATE TABLE tape_flag_day (
            ins_code TEXT NOT NULL, flag TEXT NOT NULL, d_even INTEGER NOT NULL, symbol TEXT,
            first_seen_at TEXT, last_seen_at TEXT, passes INTEGER NOT NULL DEFAULT 1,
            evidence TEXT, source TEXT, PRIMARY KEY (ins_code, flag, d_even))"""
TM_DDL = """CREATE TABLE tape_flag_day_meta (
            d_even INTEGER PRIMARY KEY, first_at TEXT, last_at TEXT,
            passes INTEGER NOT NULL DEFAULT 1, symbols INTEGER, active_rows INTEGER)"""

FA_MONTH = ("گزارش فعالیت ماهانه دوره {m} ماهه منتهی به {pe}")
FA_YEAR = "صورت‌های مالی  سال مالی منتهی به {pe} (حسابرسی شده)"
UNIT_MRL = "کليه مبالغ به ميليون ريال است"


def pe(year, month, day=None):
    """تاریخِ دورۀ با جداکنندۀ اسلش — `CP.DATED_SQL` دقیقاً همین شکل را GLOB
    می‌کند؛ «1404-12-29» (خط تیره) درِ تولید هم «بی‌دوره» خوانده می‌شود و
    از همه لایه‌ها بیرون می‌افتد. یکی از ردیف‌هایِ متنوع01 عمداً همان خط تیره
    و یکی رقمِ فارسی است تا این مرز هم سنجیده شود."""
    if day is None:
        day = 31 if month <= 6 else 30
        if month == 12:
            day = 29
    return "%d/%02d/%02d" % (year, month, day)


def fa_digits(n):
    return "".join(chr(0x06F0 + int(d)) for d in str(abs(int(n))))


def ym_to_fa(year, month):
    """رقمِ ASCII، همان شکلِ بیشترِ period_endهایِ کدال؛ نسخۀِ فارسی عمداً درِ
    `متنوع01` گذاشته می‌شود تا هر دو نوشتار درِ یک بانک سنجیده شوند."""
    return "%s/%02d" % (year, month)


def add_months(year, month, k):
    total = (month + k - 1) % 12 + 1
    y = year + (month + k - 1) // 12
    return y, total


def ms_rows(symbol, start_year, base_ytd, step, prev_col, tn=1000):
    """۲۴ ماهِ متوالی: تجمیعیِ صعودی، و «مقایسه با دورۀ مشابه» یا تهی."""
    rows = []
    for y in (start_year, start_year + 1):
        for m in range(1, 13):
            idx = (y - start_year) * 12 + m
            ytd = base_ytd + step * idx
            rows.append((tn, symbol, FA_MONTH.format(m=m, pe=ym_to_fa(y, m)),
                         ym_to_fa(y, m), y, m, ytd - (base_ytd + step * (idx - 1) if idx > 1 else 0),
                         ytd, "https://codal.ir/x/%d" % tn, None,
                         None, (ytd / 1.5) if prev_col and y > start_year else None,
                         None, None, None))
            tn += 1
    return rows


def fs_annual(symbol, name, years, eps0, eps_mul, rev, margin, base, audited=1, cons=1):
    rows = []
    tn = base     # شماره‌هایِ دستی: قطعیتِ بی‌هشِ پایتون (hashِ رشته بینِ پروسه‌ها عوض می‌شود)
    for i, y in enumerate(years):
        eps = eps0 * (eps_mul ** i)      # صعودی با سال — ladderِ محور ۲
        gp = rev * margin
        rows.append((tn, symbol, name, FA_YEAR.format(pe=pe(y, 12)),
                     "Financial Statements", 12, pe(y, 12),
                     "%d/11/19 15:11:02" % (y + 1), rev, gp, gp * 0.9, eps * 1000,
                     rev * 3.0, rev * 1.2, rev * 1.8, rev * 0.5, -rev * 0.2, eps,
                     UNIT_MRL, "https://codal.ir/R/%d" % tn, "2026-08-24 05:41:44",
                     audited, cons, str(y), "mrl", 1))
        tn += 1
    return rows


def seed_market(path):
    con = sqlite3.connect(path)
    con.executescript("DROP TABLE IF EXISTS monthly_sales; DROP TABLE IF EXISTS financial_statements;"
                      "DROP TABLE IF EXISTS codal_notices;" + MS_DDL + ";" + FS_DDL + ";" + CN_DDL + ";"
                      "CREATE INDEX IF NOT EXISTS ix_ms_symbol ON monthly_sales(symbol);"
                      "CREATE INDEX IF NOT EXISTS ix_ms_sym_ym ON monthly_sales(symbol, year DESC, month DESC);"
                      "CREATE INDEX IF NOT EXISTS ix_codal_symbol ON codal_notices(symbol);"
                      "CREATE INDEX IF NOT EXISTS ix_codal_date ON codal_notices(publish_date DESC);")
    # فیکسچرِ چارت فقط شش ستونِ instruments دارد؛ بانکِ تولید اینها را دارد و
    # مسیرهایِ بنیادی (نقدشوندگی، بانِ مجاز، سهام) از همان ستون‌ها می‌خوانند،
    # پس اضافه می‌شوند — نه حذفِ پرس‌وجوها.
    have = {r[1] for r in con.execute("PRAGMA table_info(instruments)")}
    for col, decl in (("sector_code", "TEXT"), ("total_shares", "REAL"), ("eps", "REAL"),
                      ("pe", "REAL"), ("base_vol", "REAL"), ("paper_type", "INTEGER"),
                      ("c_gr_val_cot", "TEXT")):
        if col not in have:
            con.execute("ALTER TABLE instruments ADD COLUMN %s %s" % (col, decl))
    have_dp = {r[1] for r in con.execute("PRAGMA table_info(daily_prices)")}
    for col, decl in (("p_closing", "REAL"), ("price_yesterday", "REAL"), ("price_first", "REAL"),
                      ("q_tot_cap", "REAL"), ("price_change", "REAL"), ("fetched_at", "TEXT"),
                      ("market_cap_src", "TEXT"), ("z_tot_tran", "REAL"), ("p_last", "REAL")):
        if col not in have_dp:
            con.execute("ALTER TABLE daily_prices ADD COLUMN %s %s" % (col, decl))
    for sym, sector, cname in ((UP, "فلزات اساسي", "فولادِ آزمايشي"),
                              (DOWN, "سيمنت، آهك و گچ", "سیمانِ آزمايشي"),
                              (FUND, "صندوق سرمايه گذاري قابل معامله", "صندوقِ آزمون"),
                              (THIN, "خدمات فني و مهندسي", "خدماتِ آزمايشي")):
        con.execute("UPDATE instruments SET sector_name=?, c_gr_val_cot=?, total_shares=?, paper_type=?"
                    " WHERE l_val18=?", (sector, cname, 40_000_000.0, 1 if sym != FUND else 2, sym))

    rows = []
    rows += ms_rows(UP, 1403, 900.0, 40.0, True, tn=1000)
    rows += ms_rows(DOWN, 1403, 1500.0, 0.0, False, tn=2000)      # رشدِ صفر ⇒ محور ۱ رد
    rows += ms_rows(FUND, 1403, 200.0, 12.0, False, tn=3000)
    rows.append((90001, THIN, FA_MONTH.format(m=6, pe=ym_to_fa(1404, 6)), ym_to_fa(1404, 6),
                 1404, 6, 50.0, 300.0, None, None, None, None, None, None, None))
    # تله‌هایِ متنوع01 — ترتیب، دِدوپ، «شرکتِ دیگر»، ytd منفی، دورۀ بی‌سال
    tn = 91000
    for (y, m, ytd, title, pep) in (
        (1404, 6, 700.0, FA_MONTH.format(m=6, pe="1404/06/31"), "1404/06/31"),
        (1404, 6, 640.0, FA_MONTH.format(m=6, pe="1404/06/31"), "1404/06/31"),      # دِدوپ: بزرگ‌تر می‌ماند
        (1404, 5, 560.0, "گزارش فعالیت ماهانه دوره ۵ ماهه منتهی به ۱۴۰۴/۰۵/31 (سهامی خاص شرکت other)", "1404/05/31"),
        (1403, 6, 500.0, FA_MONTH.format(m=6, pe="1403/06/31"), "1403/06/31"),
        (1402, 12, -25.0, FA_MONTH.format(m=12, pe="1402/12/30"), "1402/12/30"),      # ytd منفی ⇒ بیرون
        (1404, 4, 400.0, FA_MONTH.format(m=4, pe=fa_digits(1404) + "/" + fa_digits(4) + "/31"), "۱۴۰۴/۰۴/۳۱"),  # رقمِ فارسی
    ):
        rows.append((tn, MIXED, title, pep, y, m, ytd / 6.0, ytd, None, None, None,
                     ytd * 0.75 if y == 1404 else None, None, None, None))
        tn += 1
    con.executemany("INSERT INTO monthly_sales VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)

    fs = []
    fs += fs_annual(UP, "فولادِ آزمايشي", [1399, 1400, 1401, 1402, 1403, 1404], 120.0, 1.22, 4_200_000.0, 0.25, 5000)
    fs += fs_annual(DOWN, "سیمانِ آزمايشي", [1400, 1401, 1402, 1403, 1404], 90.0, 0.86, 2_100_000.0, 0.11, 6000)
    fs += fs_annual(FUND, "صندوقِ آزمون", [1403, 1404], 55.0, 1.05, 240_000.0, 0.40, 7000)
    fs.append((95100, MIXED, "متنوعِ آزمايشي", FA_YEAR.format(pe="1404/12/30"), "Financial Statements",
               12, "1404-12-30", "۱۴۰۵/۱۱/۱۹ ۱۵:۱۱:۰۲",     # دورۀ ASCII + انتشارِ فارسی
               800_000.0, 210_000.0, 190_000.0, 150_000.0, 2_400_000.0, 900_000.0, 1_500_000.0,
               400_000.0, -50_000.0, 37.5, UNIT_MRL, None, "2026-08-24 05:41:44", 1, 1, "1404", "mrl", 1))
    fs.append((95101, MIXED, "متنوعِ آزمايشي", "صورت‌های مالی  سال مالی منتهی به ۱۴۰۴/۱۲/۳۰ (حسابرسی شده)",
               "Financial Statements", 12, "۱۴۰۴/۱۲/۳۰",              # همان دوره با نوشتارِ فارسی
               "1405-11-19 15:11:02",                                  # و انتشارِ ASCII
               800_000.0, None, 190_000.0, 150_000.0, 2_400_000.0, 900_000.0, 1_500_000.0,
               400_000.0, -50_000.0, 37.5, UNIT_MRL, None, "2026-08-24 05:41:44", 0, 0, "1404", "mrl", None))
    fs.append((95102, MIXED, "متنوعِ آزمايشي", "گزارش فعالیت دوره ۳ ماهه منتهی به ۱۴۰۵/۰۳/31",
               "Financial Statements", 3, "1405-03-31", "1405/05/20 10:00:00",
               210_000.0, 52_000.0, 48_000.0, 40_000.0, 2_400_000.0, 900_000.0, 1_540_000.0,
               400_000.0, -10_000.0, 10.0, UNIT_MRL, None, "2026-08-24 05:41:44", 0, 0, "1405", "mrl", 1))
    fs.append((95103, MIXED, "متنوعِ آزمايشي", FA_YEAR.format(pe="1403/12/30"), "Financial Statements",
               12, "1403-12-30", "1404/11/19 15:11:02", 700_000.0, 170_000.0, 160_000.0, 130_000.0,
               2_300_000.0, 880_000.0, 1_420_000.0, 400_000.0, -40_000.0, 32.5, UNIT_MRL, None,
               "2026-08-24 05:41:44", 1, 0, "1403", "mrl", 1))
    qn = 96000
    for sym, name, year, months, rev, gp, net, eps, aud, cons, tn_suffix in (
        (UP, "فولادِ آزمايشي", 1405, 3, 1_200_000.0, 306_000.0, 210_000.0, 41.0, 0, 1, 1),
        (UP, "فولادِ آزمايشي", 1405, 6, 2_450_000.0, 620_000.0, 430_000.0, 84.0, 0, 1, 2),
        (UP, "فولادِ آزمايشي", 1405, 9, 3_700_000.0, 940_000.0, 650_000.0, 126.0, 0, 1, 3),
        (UP, "فولادِ آزمايشي", 1405, 9, 3_700_000.0, 900_000.0, 600_000.0, 120.0, 0, 0, 4),  # تکراریِ همان دوره
        (MIXED, "متنوعِ آزمايشي", 1405, 6, 420_000.0, 105_000.0, 80_000.0, 20.0, 0, 1, 5),
    ):
        ped = pe(year, months * 3)
        fs.append((qn, sym, name,
                   "گزارش فعالیت میاندورهای %d ماهه منتهی به %s" % (months, ped),
                   "Financial Statements", months, ped,
                   ("۱۴۰۵/%02d/20 10:00:00" % (months * 3 + 2)) if tn_suffix == 5 else
                   "1405/%02d/20 10:00:00" % (months * 3 + 2),
                   rev, gp, gp * 0.95, net, rev * 3.0, rev * 1.1, rev * 1.9, rev * 0.5,
                   -rev * 0.1, eps, UNIT_MRL, None, "2026-10-20 05:41:44", aud, cons,
                   str(year), "mrl", 1))
        qn += 1
    con.executemany("INSERT INTO financial_statements VALUES (" + ",".join("?" * 26) + ")", fs)

    notices = [
        (97001, UP, "فولادِ آزمايشي", "گزاره استفاده از محل آورده نقدی و سود تقسیمی", "9-41",
         "1404/09/01", "1404/08/30 09:00:00", None, "2026-08-24 05:55:47", None, None),
        (97002, DOWN, "سیمانِ آزمايشي", "اطلاعیه اجرای ماده ۱۴۱ قانون تجارت", "1-141",
         "1405/04/01", "1405/03/30 09:00:00", None, "2026-08-24 05:55:47", None, None),
        (97003, FUND, "صندوقِ آزمون", "تغییر در ترکیب پرتفوی صندوق", "ن-۳۱",
         "۱۴۰۵/۰۶/۰۱", "1405/05/30 09:00:00", None, "2026-08-24 05:55:47", None, None),
    ]
    con.executemany("INSERT INTO codal_notices VALUES (?,?,?,?,?,?,?,?,?,?,?)", notices)

    # ارزشِ بازار: ستونِ market_cap در market_watch + تاریخچۀ daily_prices
    for sym, cap in ((UP, 62_000_000.0), (DOWN, 18_000_000.0), (FUND, 4_000_000.0),
                     (MIXED, 9_500_000.0)):
        cur = con.execute("SELECT ins_code FROM instruments WHERE l_val18=?", (sym,))
        row = cur.fetchone()
        if row:
            # بانِ مجازِ زنده: بدونش `mcap_dead_band_sql` ارزشِ بازار را «مرده»
            # می‌خواند و شاخص ۴ data_gap می‌شود (که خودش شاخهٔ دیگری است، ولی
            # نه اینجا).
            con.execute("UPDATE market_watch SET market_cap=?, market_cap_src='official',"
                        " allowed_min=900.0, allowed_max=1100.0 WHERE ins_code=?", (cap, row[0]))
            con.execute("INSERT OR REPLACE INTO daily_prices (ins_code, d_even, price_max, price_min,"
                        " q_tot_tran, market_cap, p_closing, price_yesterday, price_first, q_tot_cap,"
                        " price_change, fetched_at, market_cap_src, z_tot_tran, p_last)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (row[0], 20260928, 1010.0, 990.0, 100000.0, cap, 1000.0, 995.0, 998.0,
                         cap * 0.001, 0.5, "2026-09-28 12:00:00", "official", 50000.0, 1002.0))
    # THIN عمداً بی‌market_cap می‌ماند (شاخص ۴ باید data_gap بدهد نه صفر)
    con.commit()
    con.close()


DAYS = (20261025, 20261026, 20261027, 20261028)
FLAGS = ("f_clock", "f_susp", "f_jet", "f_roobi", "f_noqteh", "f_smart", "f_legal")


def seed_user(path, mkt_path):
    con = sqlite3.connect(path)
    con.executescript("DROP TABLE IF EXISTS tape_flag_day; DROP TABLE IF EXISTS tape_flag_day_meta;"
                      + TD_DDL + ";" + TM_DDL + ";")
    codes = {}
    mc = sqlite3.connect(mkt_path)
    for sym in (UP, DOWN, THIN, MIXED):
        row = mc.execute("SELECT ins_code FROM instruments WHERE l_val18=?", (sym,)).fetchone()
        if row:
            codes[sym] = (row[0], sym)
    mc.close()
    rows = []
    for i, (sym, (ins, label)) in enumerate(sorted(codes.items())):
        for d_i, day in enumerate(DAYS):
            # یک روزِ جاافتاده عمداً ساخته می‌شود: ۲۶ برایِ THIN وجود ندارد ⇒
            # HistoryFor باید placeholderِ active:false بدهد، نه حذفِ روز.
            if sym == THIN and day == 20261026:
                continue
            for f_i, flag in enumerate(FLAGS):
                if sym == THIN and f_i > 2:
                    continue                       # فقط سه فیلتر در آن روز
                passes = 0 if (sym == DOWN and flag == "f_jet") else 1
                ev = json.dumps({"vol_ratio": 3.4 + f_i, "is_live": True}, sort_keys=True) \
                    if not (sym == MIXED and flag == "f_legal") else None
                rows.append((ins, flag, day, label, "%02d:0%d:07" % (9 + d_i, f_i % 6),
                             "%02d:1%d:52" % (12 + d_i, f_i % 6), passes, ev, "tape-loop"))
    con.executemany("INSERT OR REPLACE INTO tape_flag_day VALUES (?,?,?,?,?,?,?,?,?)", rows)
    meta = []
    for d_i, day in enumerate(DAYS):
        symbols_here = sum(1 for sym, (ins, _l) in codes.items()
                           if not (sym == THIN and day == 20261026))
        meta.append((day, "08:00:0%d" % d_i, "15:30:0%d" % d_i, 1, symbols_here,
                     None if day == 20261025 else symbols_here * 5))
    con.executemany("INSERT OR REPLACE INTO tape_flag_day_meta VALUES (?,?,?,?,?,?)", meta)
    # سبد: عادی01 accept با قیمتِ بالا (حدِ ضرر از سبد)، پایین02 reject، متنوع01 acceptِ بی‌قیمت
    con.execute("DELETE FROM selection_decisions")
    con.executemany("INSERT INTO selection_decisions(symbol, status, price) VALUES (?,?,?)",
                    [(UP, "accept", 2400.0), (DOWN, "reject", 300.0), (MIXED, "accept", None)])
    con.commit()
    con.close()


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else OUT
    os.makedirs(out, exist_ok=True)
    for name in ("market.db", "user.db"):
        shutil.copyfile(os.path.join(SRC_FIX, name), os.path.join(out, name))
    mkt = os.path.join(out, "market.db")
    seed_market(mkt)
    seed_user(os.path.join(out, "user.db"), mkt)
    counts = {}
    con = sqlite3.connect(mkt)
    for t in ("monthly_sales", "financial_statements", "codal_notices"):
        counts[t] = con.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
    con.close()
    con = sqlite3.connect(os.path.join(out, "user.db"))
    for t in ("tape_flag_day", "tape_flag_day_meta", "selection_decisions"):
        counts[t] = con.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
    con.close()
    print(json.dumps(counts, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
