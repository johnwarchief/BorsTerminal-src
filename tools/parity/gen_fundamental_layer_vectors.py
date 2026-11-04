#!/usr/bin/env python
"""وکتورهایِ لایه‌هایِ صورتِ مالی/شاخص‌ها/متن — بخشِ دومِ داورِ fan-out.

همه رویِ همان فیکسچرِ یخ‌زدۀ تسکِ ۱ ساخته می‌شوند (`internal/fundamental/testdata/
fixture/market.db`) — نه بانکِ عملیاتی؛ قیدِ سختِ پروژه همین است. اوراکل فقط
می‌خواند و چیزی نمی‌نویسد.

چرا وکتورِ لایه‌ای لازم است: `golden/*.json` رأیِ نهایی است و خطایِ یکِ لایه درِ
کلِ بدنه گم می‌شود. این‌جا هر تابع با ورودیِ مشخصِ خودش سنجیده می‌شود تا شاخه‌ای
از fan-out نتواند با «درست به‌نظر رسیدن» بسته شود.
"""
import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

FIX = os.path.join(ROOT, "backend-go", "internal", "fundamental", "testdata", "fixture")
OUT_DIR = os.path.join(ROOT, "backend-go", "internal", "fundamental", "testdata", "vectors")

UP, DOWN, FUND, THIN, MIXED = "عادی01", "پایین02", "اهرم‌ب", "کم‌سابقه11", "متنوع01"
SYMS = (UP, DOWN, FUND, THIN, MIXED)


def fixture_conn():
    """کپیِ فقط‌خواندنی از فیکسچر (ریشه هرگز باز نمی‌شود)."""
    tmp = tempfile.mkdtemp(prefix="b4-vec-")
    path = os.path.join(tmp, "market.db")
    shutil.copyfile(os.path.join(FIX, "market.db"), path)
    con = sqlite3.connect("file:%s?mode=ro" % path.replace("\\", "/"), uri=True)
    con.row_factory = sqlite3.Row
    return con, tmp


def rows_of(cur):
    return [dict(r) for r in cur]


def statement_vectors(con, fe):
    out = {"annual": [], "reference": [], "gross": [], "names": [], "quarter_ref": []}
    for sym in SYMS:
        for lim in (6, 3, 1):
            out["annual"].append({"symbol": sym, "limit": lim,
                                  "out": fe.annual_statements(con, sym, limit=lim)})
        ref = fe.reference_annual(con, sym)
        out["reference"].append({"symbol": sym, "out": ref})
        for th in ((20.0, 30.0), (5.0, 50.0), (40.0, 50.0)):
            out["gross"].append({"symbol": sym, "min": th[0], "opt": th[1], "ref": ref,
                                 "out": fe.gross_margin(con, sym, min_margin=th[0],
                                                        optimal=th[1], ref=ref)})
        out["names"].append({"symbol": sym, "out": fe.company_name_of(con, sym)})
    # انتخابِ مرجعِ سریِ فصلی رویِ ردیف‌هایِ واقعیِ همان فیکسچر
    for sym in SYMS:
        raw = rows_of(con.execute(
            "SELECT period_end, period_months, revenue, gross_profit, operating_profit,"
            " net_profit, basic_eps, publish_date, title, tracing_no, report_kind"
            " FROM financial_statements WHERE symbol = ? AND " + fe.CP.DATED_SQL, (sym,)))
        for lim in (16, 4, 1, 0, 999):
            out["quarter_ref"].append({"symbol": sym, "limit": lim,
                                       "out": fe.quarter_reference_rows(raw, limit=lim)})
    return out


def indicator_vectors(con, fe, fd):
    out = {"profile": [], "monthly": [], "ind1a": [], "ind1b": [], "axis1": [],
           "eps_ladder": [], "eps_assess": [], "ind2": [], "states": []}
    for sym in SYMS:
        sector = str((con.execute("SELECT sector_name FROM instruments WHERE l_val18 = ?",
                                 (sym,)).fetchone() or [None])[0] or "")
        prof = fe.company_profile(sector, fe.company_name_of(con, sym))
        out["profile"].append({"symbol": sym, "sector": sector, "out": prof})
        series = fe.monthly_series(con, sym)
        out["monthly"].append({"symbol": sym, "rows": [list(r) for r in series]})
        th = fd.v10_thresholds({})
        g = fd.ind1a_monetary_growth(con, sym, series=series, th=th, profile=prof)
        out["ind1a"].append({"symbol": sym, "out": g})
        v = fd.ind1b_volume_growth(con, sym, monetary=g, series=series, th=th, profile=prof)
        out["ind1b"].append({"symbol": sym, "out": v})
        out["axis1"].append({"symbol": sym, "out": bool(fd.axis1_pass(g, v))})
        for years in (3, 2, 4):
            out["eps_ladder"].append({"symbol": sym, "years": years,
                                      "out": fe.eps_ladder(con, sym, years=years)})
            out["eps_assess"].append({"symbol": sym, "years": years, "sector": sector,
                                      "out": fe.eps_assessment(con, sym, years=years,
                                                               sector=sector)})
        e = fd.ind2_eps_track(con, sym, th=th, sector=sector)
        out["ind2"].append({"symbol": sym, "out": e})
        gm = fd.ind3_gross_margin(con, sym, th=th,
                                 ref=fe.reference_annual(con, sym), profile=prof)
        out["states"].append({"symbol": sym, "out": fd.v10_axis_states(
            {"1": {"monetary": g, "volume": v}, "2": e, "3": gm,
             "4": {"na": bool(sym == FUND)}, "5": {"pass": True}},
            {"1_growth": bool(g.get("pass")), "2_eps_trend": bool(e.get("pass")),
             "3_gross_margin": bool(gm.get("pass")), "4_sales_to_mcap": False,
             "5_industry": True})})
    return out


def valuation_vectors(fe, fd):
    """شاخص ۴ رویِ شبکه‌ای از ورودی‌ها — از جمله سه‌حالۀ exempt/no-sales/no-mcap."""
    out = []
    th = fd.v10_thresholds({})
    annuals = [
        None,
        {},
        {"annual_sales_mrl": 0.0, "annual_sales_bt": 0.0, "months_used": 6,
         "scale_factor": 2.0, "basis": "x", "reconciled": True},
        {"annual_sales_mrl": 4200000.0, "annual_sales_bt": 420.0, "months_used": 9,
         "scale_factor": 1.3333333333333333, "basis": " Annualized", "reconciled": True,
         "fs_unit": "mrl", "fs_unit_label": "میلیون ریال", "unit_unverified": False},
        {"annual_sales_mrl": 4200000.0, "annual_sales_bt": 420.0, "months_used": 12,
         "scale_factor": 1.0, "basis": "کدال", "reconciled": False,
         "unit_unverified": True},
    ]
    gms = [None, {}, {"na": True}, {"na": True, "net_margin_pct": 18.0},
           {"na": False, "margin_pct": 11.0}, {"na": False, "margin_pct": 48.75},
           {"na": False, "margin_pct": 0.0}]
    for i, ann in enumerate(annuals):
        for j, gm in enumerate(gms):
            for mc in (0.0, 1e12, 7.5e12, 4e14):
                for ex in (False, True):
                    out.append({"annual": i, "gm": j, "mcap": mc, "exempt": ex,
                                "out": fd.ind4_valuation(ann, gm, mc, th=th, exempt=ex)})
    return {"cases": out, "annuals": annuals, "gms": gms}


def annualize_vectors(con, fe, fd):
    out = []
    for sym in SYMS:
        sector = str((con.execute("SELECT sector_name FROM instruments WHERE l_val18 = ?",
                                  (sym,)).fetchone() or [None])[0] or "")
        prof = fe.company_profile(sector, fe.company_name_of(con, sym))
        ref = fe.reference_annual(con, sym)
        series = fe.monthly_series(con, sym)
        for exempt in (False, True):
            out.append({"symbol": sym, "exempt": exempt,
                        "out": fd.dynamic_annualized_sales(con, sym, series=series, ref=ref,
                                                           profile=prof, exempt=exempt)})
        out.append({"symbol": sym, "kind": "no_exempt_arg",
                    "out": fe.annualized_sales(con, sym, ref=ref, series=series,
                                               profile=prof)})
        out.append({"symbol": sym, "kind": "ind4_exempt", "out": {
            "na": bool(fe.ind4_exempt(con, sym, sector, holdings_na=True)),
            "na_false": bool(fe.ind4_exempt(con, sym, sector, holdings_na=False))}})
    return {"cases": out}


def text_vectors(fd):
    """رشته‌سازهایِ کارت — رقمِ هزارگان، ٪، سه‌حاله و سلول‌هایِ جدولِ شاخص ۲."""
    import codal_periods as cp

    vals = [None, 0, 0.0, -1.0, 12.5, 1234.5, 1234567.891, 1e15, 0.125, 1.005, "abc", ""]
    # `_pct_txt` رویِ رشته درِ پایتون TypeError می‌دهد (فراخوان‌هایش همیشه عدد یا
    # None می‌فرستند)، پس وکتورِ آن فقط اعداد/None دارد — همین را صریح ثبت می‌کنیم.
    pct_vals = [None, 0, 0.0, -1.0, 12.5, 1234.5, 1234567.891, 1e15, 0.125, 1.005]
    out = {"n": [], "pct": [], "fa": [], "state": [], "eps_row": []}
    for v in vals:
        for nd in (0, 1, 2, 3, 4):
            out["n"].append({"v": v, "nd": nd, "out": fd._n(v, nd)})
        out["fa"].append({"v": v, "out": fd._fa(v)})
    for v in pct_vals:
        out["pct"].append({"v": v, "signed": fd._pct_txt(v, True),
                           "unsigned": fd._pct_txt(v, False)})
    # عبارتِ SQLِ «تازۀترینِ انتشار» — دست‌نویسی‌اش درِ گیت یک‌بار رقم را
    # دزدید (یک `replace` اضافه)، پس از این به بعد داورش همین وکتور است.
    out["pub_canon"] = [
        {"col": col, "canon": cp.pub_canon_sql(col), "order": cp.pub_order_expr(col)}
        for col in ("publish_date", "d.publish_date")
    ]
    for passed in (True, False):
        for na in (True, False):
            for gap in (True, False):
                out["state"].append({"p": passed, "na": na, "gap": gap,
                                     "out": fd._state(passed, na=na, gap=gap)})
    eps_inputs = [
        {"period_slots": ["1402", "1403", "1404"], "eps_series": [10.0, 20.0, 30.0],
         "years_required": 3, "available_periods": 3},
        {"period_slots": ["1403", "1404"], "eps_series": [None, 20.0, 30.0],
         "years_required": 3, "available_periods": 2},
        {"period_slots": [], "eps_series": [], "years_required": 3},
        {"fiscal_years": [1402, 1404], "eps_series": [1.0], "years_required": 3},
        {"period_slots": ["", "1404"], "eps_series": [None, None], "years_required": 2},
        {"period_slots": ["1402"], "eps_series": [1234.5, 67.0], "years_required": 1},
    ]
    for e in eps_inputs:
        cells, slots = fd._eps_cells(dict(e))
        out["eps_row"].append({"in": e, "cells": cells, "slots": slots,
                               "row": fd._eps_row(dict(e))})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT_DIR)
    args = ap.parse_args(argv)

    import fts_engine as fe
    import api.fundamental as fd

    os.makedirs(args.out, exist_ok=True)
    con, tmp = fixture_conn()
    try:
        files = {
            "statements.json": statement_vectors(con, fe),
            "indicators.json": indicator_vectors(con, fe, fd),
            "annualize.json": annualize_vectors(con, fe, fd),
            "valuation.json": valuation_vectors(fe, fd),
            "text.json": text_vectors(fd),
        }
    finally:
        con.close()
        shutil.rmtree(tmp, ignore_errors=True)

    total = 0
    for name, payload in files.items():
        path = os.path.join(args.out, name)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
        n = sum(len(v) for v in payload.values() if isinstance(v, list))
        total += n
        print("vectors ->", path, "(%d)" % n)
    print("total:", total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
