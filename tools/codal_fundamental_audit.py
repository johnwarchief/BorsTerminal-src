# -*- coding: utf-8 -*-
"""tools/codal_fundamental_audit.py — ممیزیِ قابل‌تولیدِ مجددِ جامعۀِ بنیادی (Phase 1: فقط گزارش)

مرجعِ قواعد: `docs/جزوه FTS.pdf` صفحۀ ۲ تا ۶ (تصویری؛ PNGها در `_audit/jozve_p0[2-6].png`).
این ابزار هیچِ آستانهٔ تازه‌ای نمی‌سازد: هر عددی که اینجا می‌آید یا ازِ جزوه است (با ذکرِ
صفحۀِ همان جمله) یا فقط «بود/نبودِ داده» را می‌شمارد. رأیِ مالی نمی‌دهد و هیچِ داده‌ای
نمی‌نویسد — دیتابیس را `mode=ro` باز می‌کند و خروجی‌اش فقط درِ `_audit/` است.

    python tools/codal_fundamental_audit.py [--db market.db] [--out _audit/codal_fundamental_audit]

خروجی:
  <out>.json  خلاصهٔ شمارش‌ها (جامعه، پوشش هر شاخص، گروه‌های A–E، نقص‌های لایه)
  <out>.csv   جدولِ تطبیقِ هر (نماد × شاخص) با وضعیتِ PASS/DEFECT/NOT_APPLICABLE/
              WAITING_FOR_FILING/NEEDS_REVIEW و علتِ ریشه‌ای
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import codal_periods as CP  # noqa: E402  # قراردادِ دوره — تنها تعریفِ «بی‌دوره»

FA = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

# جزوۀ ص ۴: «حاشیه سود ناخالص باید بالای ۳۰٪ باشد؛ بالای ۵۰٪ هم خوب است»
NOTEBOOK_MARGIN_FLOOR = 30.0
# جزوۀ ص ۳ (و رأیِ مالک بند ۳): «نسبت به سال قبل +۴۰٪ افزایش است» ⇒ کفِ قبولی ۴۰
NOTEBOOK_GROWTH_FLOOR = 40.0

_DIGITS_RE = re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})")


def date_key(v):
    """'۱۴۰۵/۰۶/۱۳ ۲۳:۵۳' و '1405/06/13' هر دو → '1405-06-13' (قابلِ مقایسه).

    چرا لازم: `publish_date` درِ همین بانک دو encoding دارد (ارقامِ فارسی و ASCII) و
    SQLite رشته را لغت‌شناختی مقایسه می‌کند؛ قفسۀِ ارقامِ فارسی بالاتر از ASCII است،
    پس `MAX(publish_date)` همیشه ردیفِ فارسی‌رقم را «تازۀترین» می‌خواند.
    """
    if v is None:
        return None
    m = _DIGITS_RE.search(str(v).translate(FA))
    if not m:
        return None
    return "%s-%02d-%02d" % (m.group(1), int(m.group(2)), int(m.group(3)))


def one(conn, sql, args=()):
    r = conn.execute(sql, args).fetchone()
    return r[0] if r else None


def universe(conn):
    """جامعۀِ دامنه — ازِ جدول‌هایِ **نماد-کلید**.

    چرا نه market_watch: تابلو درِ اینِ بانک با `ins_code` کلید می‌خورد و هیچِ جدولِ
    پایداری `ins_code ↔ symbol` درِ market.db نیست (instruments فقط ins_code دارد؛
    نماد درِ زمانِ اجرا ازِ فیدِ TSETMC می‌آید). پس جامعۀِ قابلِ اتصال به کدال،
    نمادهایِ_seen_درِ تابلو است و شمارشِ ins_code جدا گزارش می‌شود تا «پوشش»
    با عددِ نادرع اعلام نشود.

    صندوق‌ها خارج می‌مانند: «صندوق FTS ندارد» رأیِ صریحِ مالک است (رأیِ ۱۵).
    """
    board_syms = {r[0] for r in conn.execute(
        "SELECT symbol FROM board_hist_v UNION SELECT symbol FROM price_history") if r[0]}
    funds = {s for s in board_syms if "صندوق" in s}
    with_notice = {r[0] for r in conn.execute(
        "SELECT DISTINCT symbol FROM codal_notices WHERE symbol IS NOT NULL")}
    with_sector = {r[0] for r in conn.execute("SELECT DISTINCT symbol FROM symbol_sectors")}
    return {
        "board_symbols_symbol_keyed": len(board_syms),
        "board_excluding_funds": len(board_syms - funds),
        "funds_excluded": len(funds),
        "symbols_with_any_codal_notice": len(with_notice),
        "board_symbols_with_no_notice": len((board_syms - funds) - with_notice),
        "board_symbols_with_no_sector": len((board_syms - funds) - with_sector),
        "ins_code_keyed_board_rows": one(conn, "SELECT COUNT(*) FROM market_watch"),
        "join_caveat": ("market_watch/instruments با ins_code کلید می‌خورند و نماد درِ "
                        "اجرا ازِ فید می‌آید؛ اتصالِ پایدارِ نماد↔ins_code درِ بانک نیست"),
        "fs_symbols": one(conn, "SELECT COUNT(DISTINCT symbol) FROM financial_statements"),
        "monthly_sales_symbols": one(conn, "SELECT COUNT(DISTINCT symbol) FROM monthly_sales"),
    }


def freshness(conn):
    """مرزِ زمانیِ «تازگی» — بدونِ این، گروه D قابلِ سنجش نیست."""
    last_fetch = one(conn, "SELECT MAX(fetched_at) FROM financial_statements")
    newest_fs_pub = max([k for k in (date_key(r[0]) for r in
                                     conn.execute("SELECT publish_date FROM financial_statements")) if k])
    notices = [(r[0], r[1], r[2], date_key(r[3])) for r in conn.execute(
        "SELECT tracing_no, symbol, title, publish_date FROM codal_notices")]
    newer = [n for n in notices if n[3] and n[3] > newest_fs_pub]
    fs_t = {r[0] for r in conn.execute("SELECT tracing_no FROM financial_statements")}
    ms_t = {r[0] for r in conn.execute("SELECT tracing_no FROM monthly_sales")}
    tried = {r[0] for r in conn.execute("SELECT tracing_no FROM codal_extracted")}
    unprocessed = [n for n in newer if n[0] not in fs_t and n[0] not in ms_t]
    return {
        "last_fetched_at": last_fetch,
        "newest_fs_publish_date": newest_fs_pub,
        "newest_notice_publish_date": max([n[3] for n in notices if n[3]]),
        "notices_newer_than_newest_fs": len(newer),
        "symbols_affected": len({n[1] for n in newer}),
        "newer_notices_absent_from_data": len(unprocessed),
        "…of_which_never_attempted": sum(1 for n in unprocessed if n[0] not in tried),
        "…of_which_attempted_but_failed": sum(1 for n in unprocessed if n[0] in tried),
        "sample_absent": [{"tracing_no": n[0], "symbol": n[1], "title": (n[2] or "")[:70], "date": n[3]}
                          for n in unprocessed[:15]],
    }


def _date_ranges(conn):
    """بازۀِ تاریخِ هر یک از دو encoding — جهتِ اثرِ نقصِ رقم را تعیین می‌کند."""
    out = {}
    for label, want_fa in (("fa", True), ("ascii", False)):
        keys = [date_key(v) for (v,) in conn.execute("SELECT publish_date FROM codal_notices")
                if v and any("۰" <= ch <= "۹" for ch in str(v)) == want_fa]
        keys = [k for k in keys if k]
        out[label + "_rows"] = len(keys)
        out[label + "_min"] = min(keys) if keys else None
        out[label + "_max"] = max(keys) if keys else None
    return out


def encoding_defect(conn):
    """دو encoding درِ publish_date — و جهتِ اثرش (بیش‌دریافت، نه از‌دست‌رفتن)."""
    def split(tbl):
        syms_fa, syms_as = set(), set()
        for s, p in conn.execute("SELECT symbol, publish_date FROM %s" % tbl):
            if p is None:
                continue
            (syms_fa if any("۰" <= ch <= "۹" for ch in str(p)) else syms_as).add(s)
        return {"fa_symbols": len(syms_fa), "ascii_symbols": len(syms_as),
                "mixed_symbols": len(syms_fa & syms_as)}
    rng = _date_ranges(conn)
    return {
        "codal_notices": split("codal_notices"), "financial_statements": split("financial_statements"),
        "notice_dates_by_encoding": rng,
        "direction": ("MAX(publish_date) همیشه ردیفِ فارسی‌رقم را برمی‌گرداند و آن دسته "
                      "کهنه‌ترند ⇒ پنجرۀ increment زودتر از حد باز می‌شود = بیش‌دریافت "
                      "و فشارِ نرخِ درخواست، نه از‌دست‌رفتنِ داده. (جهت با مقایسۀ بازۀِ "
                      "تاریخِ هر دو دسته سنجیده شد.)"),
        "still_raw_max_at": ["codal_fetcher.update_symbol_incremental (MAX per symbol)",
                             "api/fundamental.py:2113 (ORDER BY period_end, publish_date DESC)",
                             "dev/pipeline_updater.py:19", "dev/update_codal.py:22"],
        "already_normalized_at": ["codal_fetcher.newest_publish_date()/date_key() (نشانۀ سراسری)",
                                  "codal_periods.order_expr() برای period_end (که ASCII canonical است)"],
    }


def duplicates(conn):
    """(symbol, period_end) تکراری — اصلاحیه باید جایگزین شود، نه انباشته."""
    pairs = list(conn.execute(
        "SELECT symbol, period_end, COUNT(*), GROUP_CONCAT(DISTINCT is_consolidated), "
        "GROUP_CONCAT(publish_date, '|') FROM financial_statements "
        "GROUP BY symbol, period_end HAVING COUNT(*) > 1"))
    worst = sorted(pairs, key=lambda r: -r[2])[:10]
    return {
        "pairs_with_multiple_rows": len(pairs),
        "total_extra_rows": sum(r[2] - 1 for r in pairs),
        "max_rows_for_one_period": max([r[2] for r in pairs] or [0]),
        "worst": [{"symbol": w[0], "period_end": w[1], "rows": w[2],
                   "publish_dates": (w[4] or "")[:160]} for w in worst],
        "pairs_mixing_consolidated_and_main": sum(1 for r in pairs if "1" in (r[3] or "") and "0" in (r[3] or "")),
    }


def period_contract(conn):
    """قراردادِ codal_periods: دورۀ معتبر، «بی‌دوره»، و مقادیرِ بیرونِ ۳/۶/۹/۱۲."""
    rows = list(conn.execute("SELECT period_months, COUNT(*) FROM financial_statements GROUP BY 1 ORDER BY 1"))
    return {
        "by_period_months": rows,
        "outside_3_6_9_12": [(m, n) for m, n in rows if m not in (None, 3, 6, 9, 12)],
        "undated_rows": one(conn, "SELECT COUNT(*) FROM financial_statements WHERE " + CP.UNDATED_SQL),
        "canonical_shape": "YYYY/MM/DD ارقامِ ASCII (CANON_RE) — همان چیزی که DATED_SQL هم با GLOBِ ASCII می‌سنجد",
    }


def units(conn):
    """مقیاس: جزوۀ ص ۲ «اعداد به میلیون ریال است… میلیارد تومان می‌شود»."""
    return {
        "unit_norm": dict(conn.execute("SELECT COALESCE(unit_norm,'∅'), COUNT(*) FROM financial_statements GROUP BY 1")),
        "rows_without_unit_norm": one(conn, "SELECT COUNT(*) FROM financial_statements WHERE unit_norm IS NULL"),
        "distinct_unit_texts": one(conn, "SELECT COUNT(DISTINCT unit) FROM financial_statements"),
        "symbols_with_unitless_rows": one(conn, "SELECT COUNT(DISTINCT symbol) FROM financial_statements WHERE unit_norm IS NULL"),
    }


def index_coverage(conn):
    """پوششِ هر پنج شاخص — فقط «داده هست نیست»، نه رأیِ مالی."""
    fs = "financial_statements"
    i1 = {"symbols_with_ytd_and_prev": one(conn,
          "SELECT COUNT(DISTINCT symbol) FROM monthly_sales WHERE ytd_revenue IS NOT NULL AND ytd_revenue_prev IS NOT NULL"),
          "symbols_with_volume": one(conn, "SELECT COUNT(DISTINCT symbol) FROM monthly_sales WHERE ytd_volume IS NOT NULL"),
          "note": "جزوۀ ص ۳: رشدِ فروش نسبت به مشابهِ سال قبل؛ کفِ قبولی ۴۰٪ (رأیِ مالک)"}
    i2 = {"symbols_with_3_year_end_eps": one(conn,
          "SELECT COUNT(*) FROM (SELECT symbol FROM %s WHERE period_months=12 AND is_consolidated=0 "
          "AND basic_eps IS NOT NULL GROUP BY symbol HAVING COUNT(DISTINCT fiscal_year)>=3)" % fs),
          "symbols_having_a_consolidated_year_end": one(conn,
          "SELECT COUNT(DISTINCT symbol) FROM %s WHERE period_months=12 AND is_consolidated=1" % fs),
          "note": "جزوۀ ص ۴: «اطلاعات و صورت‌های مالی تلفیقی مدنظر ما نیست…» + «سابقه عملکرد سه ساله»"}
    i3 = {"symbols_with_year_end_gross_and_revenue": one(conn,
          "SELECT COUNT(DISTINCT symbol) FROM %s WHERE period_months=12 AND gross_profit IS NOT NULL "
          "AND revenue IS NOT NULL" % fs),
          "symbols_missing_gross_on_year_end": one(conn,
          "SELECT COUNT(DISTINCT symbol) FROM %s WHERE period_months=12 AND gross_profit IS NULL" % fs),
          "note": "جزوۀ ص ۴: سود(زیان) ناخالص ÷ درآمدهای عملیاتی × ۱۰۰؛ ≥۳۰ مطلوب، ≥۵۰ خوب"}
    i4 = {"symbols_with_market_cap": one(conn, "SELECT COUNT(DISTINCT symbol) FROM market_cap_snapshots"),
          "note": "جزوۀ ص ۵: فروشِ سالانه‌سازی‌شده × حاشیه ÷ ارزش بازار (×۴ فقط مثالِ سه‌ماهه)"}
    return {"I1_growth": i1, "I2_eps_history": i2, "I3_gross_margin": i3, "I4_sales_to_mcap": i4,
            "I5_sector": {"note": "ص ۶ جدولِ ✓/✗؛ از sector_name خوانده می‌شود، نه از صورتِ مالی",
                          "symbols_with_sector": one(conn, "SELECT COUNT(DISTINCT symbol) FROM symbol_sectors")}}


def per_symbol_table(conn, out_csv):
    """جدولِ تطبیقِ هر (نماد × شاخص) با وضعیتِ معیارِ مأموریت."""
    uni = universe(conn)
    names = {r[0]: r[1] for r in conn.execute(
        "SELECT symbol, company_name FROM codal_notices WHERE company_name IS NOT NULL GROUP BY symbol")}
    sectors = {r[0]: r[1] for r in conn.execute(
        "SELECT symbol, sector_name FROM symbol_sectors WHERE sector_name IS NOT NULL")}
    board_syms = sorted({r[0] for r in conn.execute(
        "SELECT symbol FROM board_hist_v UNION SELECT symbol FROM price_history") if r[0]})
    rows = [(s, names.get(s, ""), sectors.get(s, "")) for s in board_syms]
    fs_by = {}
    for s, pm, cons, eps, rev, gp, fy in conn.execute(
            "SELECT symbol, period_months, is_consolidated, basic_eps, revenue, gross_profit, fiscal_year "
            "FROM financial_statements"):
        fs_by.setdefault(s, []).append((pm, cons, eps, rev, gp, fy))
    ms_by = {r[0]: r[1] for r in conn.execute(
        "SELECT symbol, MAX(CASE WHEN ytd_revenue IS NOT NULL AND ytd_revenue_prev IS NOT NULL THEN 1 ELSE 0 END) "
        "FROM monthly_sales GROUP BY symbol")}
    notice_syms = {r[0] for r in conn.execute("SELECT DISTINCT symbol FROM codal_notices")}
    n = 0
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as fo:
        wr = csv.writer(fo)
        wr.writerow(["symbol", "index", "required_report", "period", "codal_evidence",
                     "stored_value", "unit", "collection", "extraction", "calc", "display",
                     "defect_class", "root_cause", "status"])
        for sym, name, sector in rows:
            if "صندوق" in (sym or "") or "صندوق" in (name or ""):
                for idx in ("I1", "I2", "I3", "I4", "I5"):
                    wr.writerow([sym, idx, "", "", "", "", "", "", "", "", "",
                                 "NOT_APPLICABLE", "صندوق (رأیِ ۱۵ مالک: صندوق FTS ندارد)", "NOT_APPLICABLE"])
                    n += 1
                continue
            recs = fs_by.get(sym, [])
            yr = [r for r in recs if r[0] == 12]
            yr_main = [r for r in yr if not r[1]]
            # I1 — رشد فروش (جزوه ص ۳)
            wr.writerow([sym, "I1", "گزارش فعالیت ماهانه (YTD)", "", "tracing_no در codal_notices",
                         "ytd/prev در monthly_sales" if ms_by.get(sym) else "", "میلیون ریال",
                         "yes" if sym in ms_by else "no", "", "", "",
                         "" if ms_by.get(sym) else ("NO_NOTICE" if sym not in notice_syms else "NOT_EXTRACTED"),
                         "monthly_sales" if ms_by.get(sym) else "دریافت/استخراج",
                         "PASS" if ms_by.get(sym) else "NEEDS_REVIEW"])
            # I2 — سابقۀ سه‌سالۀ EPS، فقط غیرتلفیقی (جزوه ص ۴)
            st2 = "PASS" if len({r[5] for r in yr_main if r[2] is not None}) >= 3 else (
                "WAITING_FOR_FILING" if not yr else "NEEDS_REVIEW")
            wr.writerow([sym, "I2", "صورت سود و زیان سالانۀ شرکت اصلی", "سه سال مالی",
                         "", "%d سالِ غیرتلفیقی با EPS" % len({r[5] for r in yr_main if r[2] is not None}),
                         "ریال/سهم", "yes" if yr else "no", "", "", "",
                         "" if st2 == "PASS" else ("CONSOLIDATED_ONLY" if yr and not yr_main else "MISSING_YEARS"),
                         "source" if st2 == "PASS" else "منبع/دوره", st2])
            # I3 — حاشیۀ سود ناخالص (جزوه ص ۴)
            have3 = [r for r in yr_main if r[3] is not None and r[4] is not None]
            st3 = "PASS" if have3 else ("WAITING_FOR_FILING" if not yr else "NEEDS_REVIEW")
            wr.writerow([sym, "I3", "صورت سود و زیان (ناخالص)", "سال مالی",
                         "", "%d ردیف با هر دو فیلد" % len(have3), "میلیون ریال",
                         "yes" if yr else "no", "", "", "",
                         "" if have3 else "GROSS_PROFIT_NULL", "استخراج/منبع", st3])
            # I4 — فروش ÷ ارزش بازار (جزوه ص ۵)
            wr.writerow([sym, "I4", "همان I3 + ارزش بازار", "دورۀ جاری", "", "", "",
                         "yes" if have3 else "no", "", "", "", "" if have3 else "DEPENDS_ON_I3",
                         "محاسبه", "PASS" if have3 else "NEEDS_REVIEW"])
            # I5 — چهار بُعد (جزوه ص ۶)
            wr.writerow([sym, "I5", "—", "", "", sector or "", "", "", "", "", "",
                         "" if sector else "NO_SECTOR", "نقشۀ صنعت", "PASS" if sector else "NEEDS_REVIEW"])
            n += 5
    return {"rows_written": n, "csv": out_csv, "symbols": len(rows)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="market.db")
    ap.add_argument("--out", default="_audit/codal_fundamental_audit")
    a = ap.parse_args()
    if not os.path.exists(a.db):
        print("دیتابیس پیدا نشد:", a.db)
        return 2
    conn = sqlite3.connect("file:%s?mode=ro" % a.db, uri=True)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    rep = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "db": a.db,
           "db_size_bytes": os.path.getsize(a.db),
           "authority": "docs/جزوه FTS.pdf ص۲–۶ (تصویری؛ PNG: _audit/jozve_p0[2-6].png)",
           "read_only": True,
           "thresholds_used": {"margin_floor_pct": NOTEBOOK_MARGIN_FLOOR, "growth_floor_pct": NOTEBOOK_GROWTH_FLOOR,
                               "source": "جزوه ص ۴ و ص ۳ + رأیِ مالک؛ هیچ آستانۀ تازه‌ای ساخته نشد"},
           "universe": universe(conn), "freshness_group_D": freshness(conn),
           "date_encoding": encoding_defect(conn), "revisions_group_D2": duplicates(conn),
           "period_contract": period_contract(conn), "units": units(conn),
           "index_coverage": index_coverage(conn)}
    rep["mapping_table"] = per_symbol_table(conn, a.out + ".csv")
    with open(a.out + ".json", "w", encoding="utf-8") as fo:
        json.dump(rep, fo, ensure_ascii=False, indent=1)
    print(json.dumps({k: rep[k] for k in ("universe", "freshness_group_D", "date_encoding",
                                          "revisions_group_D2", "period_contract", "units", "mapping_table")},
                     ensure_ascii=False, indent=1))
    print("OUT →", a.out + ".json /", a.out + ".csv")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
