# -*- coding: utf-8 -*-
"""tools/codal_coverage_audit.py — سرشماریِ پوشش/freshness با queryهایِ قابلِ بازتولید.

بندِ ۸ مأموریت: هر شکاف باید بداند از کجاست — نبودِ واقعیِ داده، نقصِ ingestion،
mappingِ هویت، تناقضِ دوره/واحد، یا خطای API/UI. این ابزار هیچ شمارشی را از
گزارشِ پیشین کپی نمی‌کند: همه از همین بانک، درِ همین اجرا، با **واحدِ شمارشِ
یکسان** (کلیدِ هویت، نه نوشتار) خوانده می‌شود.

usage: PYTHONIOENCODING=utf-8 python tools/codal_coverage_audit.py [--db market.db]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import codal_periods as CP                    # noqa: E402
import codal_units as CU                      # noqa: E402
import fts_engine as FE                       # noqa: E402
import symbol_identity as SI                  # noqa: E402


def keys(conn, sql, params=()):
    """شمارشِ **یکسانِ کلیدِ هویت** برایِ هر جامعۀ نمادها."""
    return len({SI.key(r[0]) for r in conn.execute(sql, params) if r[0]})


# ─── علیت‌سنجیِ هر شکاف (بندِ ۸: «نبودِ داده در برابرِ نقصِ ingestion») ─── #

def unit_causes(conn):
    """شکافِ واحد: آیا منبع چیزی نگفته، یا گفته و ما نشناخته‌ایم؟

    «بی‌واحد» با «ردیفِ کهنه» یکی نیست: اگر هر دو دورۀ واکشی همان نسبتِ
    بی‌واحد را داشته باشند، علتِ نبودش era نیست، نبودِ خطِ واحد درِ خودِ
    گزارش است.
    """
    rows = list(conn.execute("SELECT symbol, unit, unit_norm, revenue, gross_profit, "
                             "substr(fetched_at,1,10) d FROM financial_statements"))
    miss = [r for r in rows if CU.is_missing(r["unit_norm"])]
    have = [r for r in rows if CU.is_valid(r["unit_norm"])]
    per = {}
    for r in rows:
        k = SI.key(r["symbol"])
        if k:
            per.setdefault(k, set()).add(CU.is_valid(r["unit_norm"]))
    return {
        "rows": len(miss),
        "symbols_with_any_unitless_row": len({SI.key(r["symbol"]) for r in miss if r["symbol"]}),
        "symbols_with_no_unit_row_at_all": sorted(
            k for k, v in per.items() if v == {False}),
        "source_silent_unit_raw_NULL": sum(1 for r in miss
                                           if not str(r["unit"] or "").strip()),
        "source_spoke_but_label_unmatched": sum(1 for r in miss
                                                if str(r["unit"] or "").strip()),
        "unitless_rows_that_carry_revenue": sum(1 for r in miss if (r["revenue"] or 0) > 0),
        "unitless_rows_that_carry_gross_profit": sum(
            1 for r in miss if r["gross_profit"] is not None),
        "era_check": {"unitless_days": [min(r["d"] for r in miss), max(r["d"] for r in miss)]
                      if miss else None,
                      "with_unit_days": [min(r["d"] for r in have),
                                         max(r["d"] for r in have)] if have else None},
    }


def sector_causes(conn, fs_keys):
    """شکافِ صنعت: نماد اصلاً درِ تابلو نیست، یا هست و صنعتش خالی است؟"""
    board = {SI.key(r[0]) for r in conn.execute("SELECT l_val18 FROM instruments") if r[0]}
    sect = {SI.key(r[0]) for r in conn.execute(
        "SELECT l_val18 FROM instruments WHERE sector_name IS NOT NULL "
        "AND TRIM(sector_name) <> ''") if r[0]}
    absent = sorted(k for k in fs_keys if k not in board)
    empty = sorted(k for k in fs_keys if k in board and k not in sect)
    return {"total": len(absent) + len(empty),
            "not_on_board_at_all": len(absent), "sample_absent": absent[:8],
            "on_board_but_sector_empty": len(empty), "sample_empty_sector": empty[:8]}


def notice_causes(conn, fs_keys, stale_new):
    """شکافِ «اطلاعیه هست، رکورد نیست»: تلاشِ شکست‌خورده، تلاشِ موفقِ بی‌ردیف،
    یا بی‌شاهد. `codal_extracted` فقط یکِ روز را شاهد است، پس «بی‌شاهد» را
    هرگز «هرگز تلاش‌نشده» نخوان."""
    led = {r["tracing_no"]: r["ok"] for r in conn.execute(
        "SELECT tracing_no, ok FROM codal_extracted WHERE kind='fs'")}
    span = conn.execute("SELECT MIN(substr(tried_at,1,10)), MAX(substr(tried_at,1,10))"
                        " FROM codal_extracted WHERE kind='fs'").fetchone()
    ok_fail = ok_yes = unseen = 0
    for k, (_pd, tn) in stale_new.items():
        if k in fs_keys:
            continue
        try:
            tn_i = int(tn)
        except (TypeError, ValueError):
            tn_i = -1
        if tn_i in led:
            if led[tn_i]:
                ok_yes += 1
            else:
                ok_fail += 1
        else:
            unseen += 1
    return {"total": ok_yes + ok_fail + unseen,
            "ledger_window_days": [span[0], span[1]],
            "tried_ok_but_no_row": ok_yes,
            "tried_and_failed": ok_fail,
            "no_ledger_witness": unseen}


def eps_causes(conn, fs_keys):
    """شکافِ شاخص ۲ (سه‌سالۀ EPS): کمتر از سه سالِ خودیِ قابل‌خواندن، یا سه سال
    هست ولی عددِ EPS ندارد."""
    few = no_eps = ok = 0
    dist = {}
    for k in fs_keys:
        e = FE.eps_trend_3y(conn, k, years=3, sector="")
        ya = (e or {}).get("years_available") or 0
        dist[ya] = dist.get(ya, 0) + 1
        if ya >= 3:
            ok += 1
        else:
            rows = list(conn.execute(
                "SELECT basic_eps, period_end, period_months, title FROM financial_statements"
                " WHERE symbol=?", (k,)))
            own = [r for r in rows
                   if not FE.title_entity_suffix(str(r["title"] or ""))]
            if any(r["basic_eps"] is not None for r in own) and len(own) >= 3:
                no_eps += 1
            else:
                few += 1
    return {"computable": ok, "fewer_than_three_own_annuals": few,
            "three_rows_but_no_eps_value": no_eps,
            "years_available_distribution": {str(a): b for a, b in sorted(dist.items())}}


def margin_causes(conn, fs_keys):
    """شکافِ شاخص ۳ (حاشیۀ سود ناخالص): خطِ سود ناخالص درِ منبع نیست، یا
    واحدِ ردیف معلوم نیست، یا صنعتِ بی‌مفهومِ حاشیه (بانک/بیمه/…) است."""
    ok = no_gp = unitless = na_sector = no_row = 0
    for k in fs_keys:
        gm = FE.gross_margin(conn, k)
        if gm and gm.get("margin_pct") is not None:
            ok += 1
            continue
        ref = FE.margin_reference(conn, k) if hasattr(FE, "margin_reference") else None
        rows = [r for r in conn.execute(
            "SELECT revenue, gross_profit, unit_norm, title FROM financial_statements"
            " WHERE symbol=?", (k,))]
        own = [r for r in rows if not FE.title_entity_suffix(str(r["title"] or ""))]
        annual = [r for r in own if (r["gross_profit"] is not None or r["revenue"])]
        if not annual:
            no_row += 1
        elif all(r["gross_profit"] is None for r in annual):
            if FE.no_sales_concept(conn, k, ""):
                na_sector += 1
            else:
                no_gp += 1
        elif not any(CU.is_valid(r["unit_norm"]) for r in annual):
            unitless += 1
        else:
            no_gp += 1
    return {"computable": ok, "no_own_annual_row": no_row,
            "no_gross_profit_line_in_source": no_gp,
            "sector_without_margin_concept": na_sector,
            "reference_rows_all_unitless": unitless,
            "ref_helper": bool(hasattr(FE, "margin_reference"))}


def monthly_causes(conn):
    """تازگیِ فروشِ ماهانه: آخرین دورۀ ثبت‌شده و چگالیِ نمادها درِ آن دوره."""
    per = conn.execute("SELECT year*100+month ym, COUNT(DISTINCT symbol) n"
                       " FROM monthly_sales GROUP BY ym ORDER BY ym DESC LIMIT 4").fetchall()
    return {"latest_periods": [{"ym": r["ym"], "symbols": r["n"]} for r in per]}


# `save_annual` درِ `dev/codal_fts_updater.py` از روزی که چهار ستونِ مشتق به
# جدولِ `financial_statements` افزودیم (کامیتِ 82bd877، 2026-09-21) هر سالانه را
# با `OperationalError` رد می‌کرد و خطا را به‌شکل «استخراج ناموفق» چاپ می‌کرد.
# این تاریخ را از خودِ git خوانده‌ایم، نه از حافظه — وگرنه شمارشِ زیر بی‌معناست.
ANNUAL_INGEST_BROKEN_SINCE = "2026-09-21"


def fs_title_sql(alias=""):
    col = (alias + "." if alias else "") + "title"
    # پرانتز الزامی است: `AND` درِ SQLite بر `OR` تقدم دارد، پس بی‌آن یکِ LIKE
    # از فیلترِ تاریخ/جوا فرار می‌کند و شمارشِ بالا می‌رود (سنجیده شد: ۹۸۵ در
    # برابرِ ۹۸۰ اطلاعیهٔ درست).
    return ("(%s LIKE '%%صورتهای مالی%%' OR %s LIKE '%%صورت‌های مالی%%')" % (col, col))


def ingest_window_causes(conn):
    """چند اطلاعیهٔ صورتِ مالی درِ پنجرۀ خرابیِ نوشتن آمده و ردیف نشده است."""
    sys.path.insert(0, os.path.join(ROOT, "dev"))
    import codal_fts_updater as UP              # noqa: E402  (تنها تعریفِ «کدام عنوان را واکشی کن»)
    led = {r["tracing_no"]: r["ok"] for r in conn.execute(
        "SELECT tracing_no, ok FROM codal_extracted WHERE kind='fs'")}
    rows = conn.execute(
        "SELECT n.tracing_no tn, n.symbol sym, n.title title"
        " FROM codal_notices n LEFT JOIN financial_statements f"
        " ON f.tracing_no = n.tracing_no WHERE %s AND substr(n.fetched_at,1,10) >= ?"
        " AND f.tracing_no IS NULL" % fs_title_sql("n"),
        (ANNUAL_INGEST_BROKEN_SINCE,)).fetchall()
    tns = [r["tn"] for r in rows]

    def w(t):
        try:
            return int(t)
        except (TypeError, ValueError):
            return -1
    in_win = conn.execute("SELECT COUNT(*) FROM codal_notices WHERE %s"
                          " AND substr(fetched_at,1,10) >= ?" % fs_title_sql(),
                          (ANNUAL_INGEST_BROKEN_SINCE,)).fetchone()[0]
    # «کدام یک از این‌ها کارِ همان واکشی‌گرِ سالانه بود؟» — تفکیک از خودِ
    # `notice_kind`، نه از حدسِ عنوان: ۱۱۶ عنوانِ سالانۀ ردشده یعنی اثرِ مستقیمِ
    # باگِ `save_annual`؛ میاندوره‌ای‌ها را همین واکشی‌گر هرگز نمی‌خواست.
    would_take = sum(1 for r in rows if UP.notice_kind(r["title"]) == "annual")
    # ردیفِ «ok=۱ ولی ردیف نیست»: آیا خواهری هم‌دورۀ همان نماد وجود دارد؟
    # اگر باشد، با پاک‌سازیِ دورۀ قدیم (حذفِ فیزیکیِ بازنده) می‌خواند.
    ok_rows = [r for r in rows if led.get(w(r["tn"])) == 1]
    sib = lone = 0
    have = {}
    for sym, pe in conn.execute("SELECT symbol, period_end FROM financial_statements"):
        k = SI.key(sym)
        if k:
            have.setdefault((k, str(pe or "").strip()), 0)
            have[(k, str(pe or "").strip())] += 1
    for r in ok_rows:
        pe, _src = CP.derive(None, r["title"])
        if pe and have.get((SI.key(r["sym"]), pe)):
            sib += 1
        else:
            lone += 1
    return {"broken_since": ANNUAL_INGEST_BROKEN_SINCE,
            "fs_notices_seen_in_window": in_win,
            "fs_notices_in_window_without_row": len(tns),
            "of_those_annual_titles_the_updater_takes": would_take,
            "of_those_ledger_ok": len(ok_rows),
            "of_those_ledger_failed": sum(1 for t in tns if led.get(w(t)) == 0),
            "of_those_no_witness": sum(1 for t in tns if w(t) not in led),
            "ledger_ok_with_sibling_row_same_period": sib,
            "ledger_ok_without_any_sibling": lone}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="market.db")
    ap.add_argument("--out", default="_audit/codal_coverage_audit.json")
    a = ap.parse_args()
    conn = sqlite3.connect("file:%s?mode=ro" % os.path.abspath(a.db).replace("\\", "/"),
                           uri=True)
    conn.row_factory = sqlite3.Row
    FE.register_sql(conn)

    universe_board = keys(conn, "SELECT l_val18 FROM instruments")
    fs_syms = keys(conn, "SELECT DISTINCT symbol FROM financial_statements")
    ms_syms = keys(conn, "SELECT DISTINCT symbol FROM monthly_sales")
    notice_syms = keys(conn, "SELECT DISTINCT symbol FROM codal_notices")

    fs_keys_all = {SI.key(r[0]) for r in conn.execute(
        "SELECT DISTINCT symbol FROM financial_statements") if r[0]}
    # صورتِ مالیِ «معتبر» = سالانۀ خودی (بی‌عنوانِ شرکتِ دیگر) با دورۀ تعیین‌شده
    no_unit = conflict = undated = 0
    seen = set()
    for sym, pe, pm, title in conn.execute(
            "SELECT symbol, period_end, period_months, title FROM financial_statements"):
        k = SI.key(sym)
        months, _src = CP.effective_months(pe, pm, title)
        # «گزارشِ خودیِ سالانۀ قابل‌استفاده» — همان سه شرطی که موتور می‌گذراند:
        # دورۀ ۱۲ماهه (از ستون یا عنوان)، و بی‌عنوانِ شرکتِ دیگر (بندِ P-1).
        if k and not FE.title_entity_suffix(str(title or "")) and months and months >= 12:
            seen.add(k)
    own_annual = len(seen)

    # شکاف‌ها، هر یک با علتِ خودش
    rows = list(conn.execute("SELECT symbol, unit_norm, period_end, period_months, title, "
                             "revenue, gross_profit FROM financial_statements"))
    per = {}
    for r in rows:
        k = SI.key(r["symbol"])
        d = per.setdefault(k, {"unit_ok": False, "conflict": False,
                               "undated": False, "gp": False})
        if CU.is_valid(r["unit_norm"]):
            d["unit_ok"] = True
        else:
            no_unit += 1
        if r["period_end"] and not CP.CANON_RE.match(str(r["period_end"]).strip()):
            undated += 1
            d["undated"] = True
        if FE.row_conflicts(r["period_end"], r["title"], r["period_months"]):
            conflict += 1
            d["conflict"] = True
        if r["gross_profit"] is not None and r["revenue"]:
            d["gp"] = True
    unitless_syms = sum(1 for d in per.values() if not d["unit_ok"])
    conflict_syms = sum(1 for d in per.values() if d["conflict"])
    undated_syms = sum(1 for d in per.values() if d["undated"])

    # صنعت: از instruments (تابلو) — نمادی که نبودش «بی‌صنعت» است، نه «سایر»
    sect_keys = {SI.key(r[0]) for r in conn.execute(
        "SELECT l_val18 FROM instruments WHERE sector_name IS NOT NULL "
        "AND TRIM(sector_name) <> ''")}
    fs_no_sector = len([k for k in fs_keys_all if k not in sect_keys])

    # freshness: «منبعِ تازه دارد ولی رکوردِ مشتق ندارد» — اطلاعیه‌ای که هنوز
    # درِ financial_statements ننشسته (با کلیدِ هویت، نه نوشتار)
    fs_keys = fs_keys_all
    stale_new = {}
    for sym, tn, pd in conn.execute(
            "SELECT symbol, tracing_no, publish_date FROM codal_notices "
            "WHERE %s" % fs_title_sql()):
        k = SI.key(sym)
        if not k:
            continue
        pd_c = CP.pub_key(pd)
        if pd_c and (k not in stale_new or pd_c > stale_new[k][0]):
            stale_new[k] = (pd_c, tn)
    notices_wo_record = sum(1 for k in stale_new if k not in fs_keys)

    # سه‌سالۀ EPS و حاشیه — با همان قاعدۀ موتور (per-index need)
    eps3 = margin = 0
    for k in sorted(fs_keys_all):
        e = FE.eps_trend_3y(conn, k, years=3, sector="")
        if e and (e.get("years_available") or 0) >= 3:
            eps3 += 1
        gm = FE.gross_margin(conn, k)
        if gm and gm.get("margin_pct") is not None:
            margin += 1

    last_fetch = conn.execute("SELECT MAX(fetched_at) FROM financial_statements").fetchone()[0]
    old_days = conn.execute(
        "SELECT julianday('now') - julianday(MAX(fetched_at)) FROM financial_statements"
    ).fetchone()[0]
    ms_latest = conn.execute("SELECT MAX(year * 100 + month) FROM monthly_sales").fetchone()[0]

    causes = {
        "unit": unit_causes(conn),
        "sector": sector_causes(conn, fs_keys_all),
        "notice_without_record": notice_causes(conn, fs_keys_all, stale_new),
        "annual_ingest_window": ingest_window_causes(conn),
        "eps_three_year": eps_causes(conn, fs_keys_all),
        "gross_margin": margin_causes(conn, fs_keys_all),
        "monthly_freshness": monthly_causes(conn),
    }

    rep = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "db": os.path.abspath(a.db),
        "unit_of_count": "SI.key(symbol) — نه نوشتارِ خام",
        "universe": {"board_instruments": universe_board, "codal_notices": notice_syms,
                     "financial_statements": fs_syms, "monthly_sales": ms_syms,
                     "own_annual_available": own_annual},
        "gaps": {
            "fs_symbols_with_no_unit_row_at_all": unitless_syms,
            "fs_without_unit_rows": no_unit,
            "fs_without_board_sector": fs_no_sector,
            "rows_with_title_period_conflict": conflict,
            "symbols_with_title_period_conflict": conflict_syms,
            "rows_undated": undated,
            "symbols_undated": undated_syms,
            "notice_fresher_than_any_fs_record": notices_wo_record,
        },
        "causes": causes,
        "computable": {"eps_three_year": eps3, "gross_margin": margin},
        "freshness": {"last_fs_fetch": last_fetch,
                      "age_days": round(float(old_days or 0), 2),
                      "latest_monthly_period": ms_latest},
    }
    d = os.path.dirname(a.out)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
