"""چند رأی جابه می‌شود اگر قاعدۀ «شرکتِ دیگر» در انتخابِ مرجع فعال شود؟

پیش ازِ Stage 1.2 این کار ممکن نبود: مسیرِ تک‌نمادی (SQL) و `bulk_scan` دو دستۀ
ردیفِ متفاوت می‌دیدند و افزودنِ پلِ «شرکتِ دیگر» فقط واگراییِ دوم می‌ساخت
(کامنتِ `pick_reference` همین را می‌گفت). حالا هر دو مسیر یک لایۀ هویت را صدا
می‌زنند (`symbol_identity`)، پس می‌شود داوری کرد.

این ابزار `pick_reference` را در **حافظه** پچ می‌کند (هیچ فایلی عوض نمی‌شود):
یک بار با منطقِ HEAD — سبدِ سال و پلکان، هیچ‌کدام پرچمِ `other_entity` را نمی‌
بینند — و یک بار با منطقِ امروز. سپس `bulk_scan` را با هر دو اجرا می‌گیرد و
تفاوتِ رأی‌ها را می‌شمارد: همان چیزی که مالک برایِ تصمیم لازم دارد، نه
فهرستِ نمادها. دو سؤالی که جواب می‌دهد:

  * چند نماد مرجعش از ردیفی که شرکتِ *دیگری* را نام می‌برد جدا می‌شود؟
  * آیا این جداسازی رأیی را عوض می‌کند، یا فقط عددِ نمایشی را؟

usage: PYTHONIOENCODING=utf-8 python tools/codal_annual_identity_tier_impact.py
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fts_engine as FE          # noqa: E402

_today_pick = FE.pick_reference


def head_pick_reference(rows):
    """منطقِ HEAD (73b1c00): بی‌پرچمِ `other_entity` در سبدِ سال و در پلکان."""
    by_year = {}
    for r in rows or []:
        if int(FE._f(r.get("period_months"))) < 12:
            continue
        yr = str(r.get("fiscal_year") or "")
        if not yr:
            continue
        rank = FE.statement_rank(FE.FS_NUMBER_KEYS, bool(r.get("consolidated")),
                                 FE.row_completeness(FE.FS_NUMBER_KEYS, r),
                                 r.get("tracing_no") or 0)
        cur = by_year.get(yr)
        if cur is None or rank < cur[0]:
            by_year[yr] = (rank, r)
    cand = sorted(by_year.values(), key=lambda t: str(t[1].get("fiscal_year") or ""),
                  reverse=True)
    for want in (lambda a, c: a and not c, lambda a, c: not c, lambda a, c: True):
        for _rank, r in cand:
            if want(bool(r.get("audited")), bool(r.get("consolidated"))):
                return r
    return None


def run(conn, cfg):
    """دو اجرای `bulk_scan` رویِ همان بانک: اول با منطقِ HEAD، دوم با منطقِ امروز."""
    FE.pick_reference = head_pick_reference
    try:
        old = {r["symbol"]: r for r in FE.bulk_scan(conn, cfg=cfg)}
    finally:
        FE.pick_reference = _today_pick
    new = {r["symbol"]: r for r in FE.bulk_scan(conn, cfg=cfg)}
    return old, new


# ردیفِ `bulk_scan` کلیدِ `passes` **ندارد** — پنج محور با نام‌هایِ `i1_pass` …
# `i5_pass` بیرون می‌آیند. اولین نسخۀ این ابزار `passes` را می‌خواند، همیشه {}.
# می‌گرفت و «۰ محور جابه شد» گزارش می‌کرد؛ سنسورِ کور، نه دادهٔ سالم.
AXES = {"1_growth": "i1_pass", "2_eps_trend": "i2_pass", "3_gross_margin": "i3_pass",
        "4_sales_to_mcap": "i4_pass", "5_industry": "i5_pass"}
NUMS = ("score", "primary_score", "rev_growth", "gross_margin", "sales_to_mcap",
        "profit_potential_pct")


def _cmp(v):
    return v if not isinstance(v, float) else round(v, 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="market.db")
    ap.add_argument("--out", default="_audit/codal_annual_identity_tier.json")
    a = ap.parse_args()
    conn = sqlite3.connect("file:%s?mode=ro" % a.db.replace("\\", "/"), uri=True)
    conn.row_factory = sqlite3.Row
    FE.register_sql(conn)
    old, new = run(conn, None)

    # اثباتِ اینکه سنسور کور نیست: اگر نامِ ستونی از ردیفِ `bulk_scan` حذف شود،
    # مقایسه بی‌صدا «۰ جابه‌جایی» می‌گفت (همان اشتباهی که این ابزار داشت). پس
    # هر ستون باید دست‌کم درِ یکِ ردیف حضور داشته باشد، وگرنه خروج موفق نیست.
    blind = [col for col in AXES.values() if not any(col in r for r in new.values())]
    if blind:
        print("BLOCKED: ردیفِ bulk_scan ستون‌هایِ %s را ندارد — ابزار کور است" % blind)
        return 1

    moved_axes, moved_score, moved_num, lost_ref = [], 0, [], []
    for s, orow in old.items():
        nrow = new.get(s) or {}
        diff = {k: (orow.get(col), nrow.get(col)) for k, col in AXES.items()
                if orow.get(col) != nrow.get(col)}
        if diff:
            moved_axes.append({"symbol": s, "axes": diff,
                               "score": (orow.get("score"), nrow.get("score")),
                               "sector": orow.get("sector_name") or orow.get("sector")})
        if (orow.get("score") or 0) != (nrow.get("score") or 0):
            moved_score += 1
        nd = {k: (orow.get(k), nrow.get(k)) for k in NUMS
              if _cmp(orow.get(k)) != _cmp(nrow.get(k))}
        if nd:
            moved_num.append({"symbol": s, "fields": nd})
        if orow.get("gross_margin") is not None and nrow.get("gross_margin") is None:
            lost_ref.append(s)

    # مرجعِ کارت درِ HEAD چند بار ردیفی بود که شرکتِ *دیگری* را نام می‌برد، و
    # امروز چند بار؟ (پنجرۀ سالانۀ HEAD = همان تابع با `statement_rank`ِ بی‌پرچم)
    def head_rows(sym):
        orig = FE.statement_rank
        FE.statement_rank = (lambda keys, cons, comp, tn, other=False:
                             orig(keys, cons, comp, tn, False))
        try:
            return FE.annual_statements(conn, sym, require_audit=False,
                                       exclude_consolidated=False, limit=12)
        finally:
            FE.statement_rank = orig

    named_other_head = named_other_today = 0
    for s in new:
        hr = head_pick_reference(head_rows(s))
        tr = FE.reference_annual(conn, s)
        if hr and FE.title_entity_suffix(hr.get("title") or ""):
            named_other_head += 1
        if tr and FE.title_entity_suffix(tr.get("title") or ""):
            named_other_today += 1

    rep = {"db": a.db, "funnel_rows": len(new),
           "head_card_references_naming_another_company": named_other_head,
           "today_card_references_naming_another_company": named_other_today,
           "verdicts_with_axis_change": len(moved_axes),
           "verdicts_with_score_change": moved_score,
           "verdicts_with_number_change": len(moved_num),
           "number_examples": moved_num[:20],
           "margin_lost": len(lost_ref),
           "examples": moved_axes[:25],
           "axis_tally": {k: sum(1 for m in moved_axes if k in m["axes"]) for k in AXES}}
    d = os.path.dirname(a.out)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in rep.items() if k not in ("examples", "number_examples")},
                     ensure_ascii=False, indent=1))
    for e in rep["number_examples"][:6]:
        print("   ", json.dumps(e, ensure_ascii=False)[:150])
    print("out=%s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
