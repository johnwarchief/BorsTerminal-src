# -*- coding: utf-8 -*-
"""چند رأی جابه می‌شود اگر قاعدۀ «شرکتِ دیگر» در انتخابِ گزارشِ مرجع فعال شود؟

پیش ازِ Stage 1.2 این کار ممکن نبود: مسیرِ تک‌نمادی (SQL) و `bulk_scan` دو دستۀ
ردیفِ متفاوت می‌دیدند و افزودنِ پلِ «شرکتِ دیگر» فقط واگراییِ دوم می‌ساخت
(کامنتِ `pick_reference` همین را می‌گفت). حالا هر دو مسیر یک لایۀ هویت را صدا
می‌زنند (`symbol_identity`)، پس می‌شود داوری کرد.

روش: یکِ پچِ موقت درِ **حافظه** — `title_entity_suffix` رشتهٔ تهی برمی‌گرداند.
همین یک پچ کل قاعدۀ دورِ جدید را خاموش می‌کند (سبدِ سال درِ `annual_statements`،
پلکانِ `pick_reference`، نردبانِ `eps_ladder` و سریِ فصلی همه از همان تابع
می‌خوانند)، پس «پیش» عیناً رفتارِ HEAD است و «پس» رفتارِ امروز. هیچ فایلی عوض
نمی‌شود و بانک فقط‌خواندنی است.

دو سؤالی که جواب می‌دهد:
  * چند رأیِ محوری و چند عددِ منتشرشده جابه می‌شود؟ (مالک عدد می‌خواهد، نه
    فهرستِ نمادها)
  * آیا نمادی هست که حاشیه‌اش از «عدد» به «بی‌داده» بیفتد؟ (همان عدد باید
    درِ رابط دلیل داشته باشد، نه صفر)

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
import symbol_identity as SI     # noqa: E402

_real_suffix = FE.title_entity_suffix

AXES = {"1_growth": "i1_pass", "2_eps_trend": "i2_pass", "3_gross_margin": "i3_pass",
        "4_sales_to_mcap": "i4_pass", "5_industry": "i5_pass"}
NUMS = ("score", "primary_score", "rev_growth", "gross_margin", "sales_to_mcap",
        "profit_potential_pct")


def rule_off():
    """HEAD: هیچ ردیفی «شرکتِ دیگر» شمرده نمی‌شود."""
    FE.title_entity_suffix = lambda title: ""


def rule_on():
    FE.title_entity_suffix = _real_suffix


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

    rule_off()
    try:
        old = {r["symbol"]: r for r in FE.bulk_scan(conn, cfg=None)}
    finally:
        rule_on()
    new = {r["symbol"]: r for r in FE.bulk_scan(conn, cfg=None)}

    # اثباتِ اینکه سنسور کور نیست: ردیفِ `bulk_scan` کلیدِ `passes` ندارد و پنج
    # محور با نامِ `i1_pass` … `i5_pass` می‌آید. اگر روزی این نام‌ها عوض شوند،
    # مقایسه بی‌صدا «۰ جابه‌جایی» می‌گوید — پس حضورِ هر ستون assert می‌شود.
    blind = [col for col in AXES.values() if not any(col in r for r in new.values())]
    if blind:
        print("BLOCKED: ردیفِ bulk_scan ستون‌هایِ %s را ندارد — ابزار کور است" % blind)
        return 1

    moved_axes, score_changed, moved_num, lost_margin = [], [], [], []
    directions = {}
    for s, orow in old.items():
        nrow = new.get(s) or {}
        diff = {k: (orow.get(col), nrow.get(col)) for k, col in AXES.items()
                if orow.get(col) != nrow.get(col)}
        for k, (o, n) in diff.items():
            tag = "%s->%s" % (o, n)
            directions[tag] = directions.get(tag, 0) + 1
        if diff:
            moved_axes.append({"symbol": s, "axes": diff,
                               "score": (orow.get("score"), nrow.get("score")),
                               "sector": orow.get("sector_name") or orow.get("sector")})
        if (orow.get("score") or 0) != (nrow.get("score") or 0):
            score_changed.append({"symbol": s})
        nd = {k: (orow.get(k), nrow.get(k)) for k in NUMS
              if _cmp(orow.get(k)) != _cmp(nrow.get(k))}
        if nd:
            moved_num.append({"symbol": s, "fields": nd})
        if orow.get("gross_margin") is not None and nrow.get("gross_margin") is None:
            lost_margin.append(s)

    # نمادهایِ یکِ خانوادۀ نوشتاری یکِ رأی دارند؛ شمارِ واحد = کلیدِ هویت.
    def uniq(rows):
        return len({SI.key(r["symbol"]) for r in rows})

    flag_rows = conn.execute(
        "SELECT COUNT(*) FROM financial_statements").fetchone()[0]
    flag_named = sum(1 for (t,) in conn.execute("SELECT title FROM financial_statements")
                     if _real_suffix(t or ""))
    rep = {"db": a.db, "funnel_rows": len(new),
           "fs_rows": flag_rows, "fs_rows_naming_another_company": flag_named,
           "today_card_references_naming_another_company": sum(
               1 for s in new if _real_suffix((FE.reference_annual(conn, s) or {}).get(
                   "title") or "")),
           "verdicts_with_axis_change": uniq(moved_axes),
           "verdict_rows_with_axis_change": len(moved_axes),
           "verdicts_with_score_change": uniq(score_changed),
           "verdicts_with_number_change": uniq(moved_num),
           "margin_becomes_no_data": len(lost_margin),
           "axis_tally": {k: uniq([m for m in moved_axes if k in m["axes"]]) for k in AXES},
           "axis_directions": {k: v for k, v in sorted(directions.items())},
           "number_examples": moved_num[:20],
           "examples": moved_axes[:25]}
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in rep.items()
                      if k not in ("examples", "number_examples")}, ensure_ascii=False, indent=1))
    for e in rep["number_examples"][:6]:
        print("   ", json.dumps(e, ensure_ascii=False)[:170])
    print("out=%s" % a.out)
    rule_on()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
