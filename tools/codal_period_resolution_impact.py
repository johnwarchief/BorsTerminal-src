# -*- coding: utf-8 -*-
"""بهایِ بندِ ۲.۳ سیاستِ بنیادی: تعیینِ طولِ دوره از عنوان، در برابرِ ستونِ خام.

پیشِ این سیاست، سه reader (`annual_statements`، `bulk_scan`، `eps_ladder`) و
سریِ فصلی عددِ ستونِ `period_months` را می‌خواندند. حالا همه از
`codal_periods.effective_months` می‌خوانند:
  * اگر عنوان «X ماهه» می‌گوید و همان عنوان همان `period_end` را می‌شمارد،
    عنوان بر ستون می‌برد (یکِ ردیفِ بانک: «دورۀ ۶ ماهه منتهی به ۱۴۰۰/۰۶/۳۱»
    با ستونِ ۱۲ — فپردیس).
  * اگر ستون تهی بود و عنوان دوره داشت، همان عنوان می‌نشیند (۲۴ ردیف).
  * اگر عنوان با ستونِ دوره بجنگد (دو تاریخِ متفاوت)، هیچ‌کدام برنده نمی‌شود.

این ابزار همان دو حالت را با پچِ موقتِ درِ حافظه مقایسه می‌کند و جابه‌جاییِ
رأی/امتیاز/عدد را می‌شمارد. بانک فقط‌خواندنی است.

usage: PYTHONIOENCODING=utf-8 python tools/codal_period_resolution_impact.py
"""
from __future__ import annotations

import argparse
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

import codal_periods as CP         # noqa: E402
import fts_engine as FE            # noqa: E402
import symbol_identity as SI       # noqa: E402

_real = CP.effective_months
AXES = {"1_growth": "i1_pass", "2_eps_trend": "i2_pass", "3_gross_margin": "i3_pass",
        "4_sales_to_mcap": "i4_pass", "5_industry": "i5_pass"}
NUMS = ("score", "primary_score", "rev_growth", "gross_margin", "sales_to_mcap",
        "profit_potential_pct", "eps_years_available")


def raw_column(period_end, period_months, title):
    """رفتارِ پیشین: فقط ستون، بی‌عنوان."""
    try:
        n = int(period_months) if period_months is not None and str(period_months).strip() else None
    except (TypeError, ValueError):
        n = None
    return n, ("column" if n is not None else None)


def _cmp(v):
    return v if not isinstance(v, float) else round(v, 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="market.db")
    ap.add_argument("--out", default="_audit/codal_period_resolution.json")
    a = ap.parse_args()
    conn = sqlite3.connect("file:%s?mode=ro" % a.db.replace("\\", "/"), uri=True)
    conn.row_factory = sqlite3.Row
    FE.register_sql(conn)

    CP.effective_months = raw_column
    try:
        old = {r["symbol"]: r for r in FE.bulk_scan(conn, cfg=None)}
    finally:
        CP.effective_months = _real
    new = {r["symbol"]: r for r in FE.bulk_scan(conn, cfg=None)}

    blind = [col for col in AXES.values() if not any(col in r for r in new.values())]
    if blind:
        print("BLOCKED: ستون‌هایِ %s درِ bulk_scan نیست — ابزار کور است" % blind)
        return 1

    axes_moved, nums_moved, directions = [], [], {}
    for s, orow in old.items():
        nrow = new.get(s) or {}
        diff = {k: (orow.get(col), nrow.get(col)) for k, col in AXES.items()
                if orow.get(col) != nrow.get(col)}
        for k, (o, n) in diff.items():
            tag = "%s:%s->%s" % (k, o, n)
            directions[tag] = directions.get(tag, 0) + 1
        if diff:
            axes_moved.append({"symbol": s, "axes": diff})
        nd = {k: (orow.get(k), nrow.get(k)) for k in NUMS
              if _cmp(orow.get(k)) != _cmp(nrow.get(k))}
        if nd:
            nums_moved.append({"symbol": s, "fields": nd})

    keys = {SI.key(s) for s in new}
    rep = {"db": a.db, "funnel_rows": len(new), "unique_symbols": len(keys),
           "symbols_with_axis_change": len({SI.key(m["symbol"]) for m in axes_moved}),
           "symbols_with_number_change": len({SI.key(m["symbol"]) for m in nums_moved}),
           "axis_directions": directions,
           "axis_examples": axes_moved[:10],
           "number_examples": nums_moved[:10],
           "resolution_cases": {}}
    # خودِ ردیف‌هایِ حل‌شده، تا معلوم باشد تغییر از کجاست
    for tn, pe, pm, title in conn.execute(
            "SELECT tracing_no, period_end, period_months, title FROM financial_statements"):
        months, src = _real(pe, pm, title)
        if src == "title":
            rep["resolution_cases"][str(tn)] = {"period_end": pe, "column": pm,
                                               "resolved": months,
                                               "title": (title or "")[:70]}
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in rep.items()
                      if k not in ("axis_examples", "number_examples")},
                     ensure_ascii=False, indent=1)[:1400])
    for e in rep["axis_examples"][:6]:
        print("   axis:", json.dumps(e, ensure_ascii=False)[:150])
    print("out=%s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
