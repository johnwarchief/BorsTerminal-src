"""ساختِ fixture آفلاین برایِ dev/test_fts_v10_ui.js — پیکربندیِ واقعیِ لایهٔ ۲.

مقادیر از خودِ `api.fundamental` تولید میشوند (`_eps_track_blended` + `_eps_row`)
تا آزمونِ رندرِ UI هرگز از منبعِ داده دور نیفتد. اجرا:
    python dev/make_fts_ui_fixture.py
خروجی: dev/fixtures/fts_v10_payloads.json
"""
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from api import fundamental as F  # noqa: E402

AUD = "صورت مالی سالانه حسابرسی شده"
I3 = "اطلاعاتیه و صورت‌های مالی میاندوره‌ای ۳ ماهه حسابرسی نشده"

ROWS = [
    ("A", "1402-12-29", 12, AUD, 400), ("A", "1403-12-29", 12, AUD, 500),
    ("A", "1404-12-29", 12, AUD, 600),
    # E: فقط ۲ دوره (۱۴۰۳ غایب) → قاعدهٔ «سطر حذف نمیشود، قرمز میشود»
    ("E", "1404-12-29", 12, AUD, 500), ("E", "1405-03-31", 3, I3, 80),
    # N: هیچ دوره‌ای
]

conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE financial_statements (symbol TEXT, period_end TEXT, "
             "period_months INTEGER, title TEXT, basic_eps REAL)")
conn.executemany("INSERT INTO financial_statements VALUES (?,?,?,?,?)", ROWS)
conn.commit()

TH = F.v10_thresholds()


def layer2(sym):
    """حداقلِ ساختارِ payload لایهٔ ۲ — درست همان چیزی که UI می‌خواند."""
    e = F._eps_track_blended(conn, sym, years=TH["eps_years"])
    row = F._eps_row(e)
    cells = row["cells"]
    if row["red"]:
        text = ("🚫 شاخص ۲ (تنها %s دوره موجود است) — EPS %s ریال · %s"
                % (F._fa(row["available"]), " ← ".join(cells), e.get("reason")))
        typ = "danger"
    elif e.get("data_gap"):
        text = "⚠️ محاسبه نمیشود — %s" % (e.get("reason") or "کمبود صورت مالی")
        typ = "warning"
    else:
        text = "EPS %s ریال" % " ← ".join(cells)
        typ = "success" if e.get("pass") else "danger"
    state = ("nodata" if e.get("data_gap") and not row["red"]
             else "fail" if row["red"]
             else "pass" if e.get("pass") else "fail")
    return {
        "methodology": {"version": "FTS-v10", "thresholds": TH},
        "score": 0 if row["red"] else (3 if e.get("pass") else 1),
        "verdict": "تأیید مشروط", "sector": "فلزات", "profile": {"label": "تولیدی"},
        "fs_count": 2, "metrics": {
            "mcap": 1e13, "eps_series": e.get("eps_series"),
            "eps_partial": bool(row["red"]), "eps_available": row["available"],
            "eps_required": row["required"],
            "eps_slots": e.get("period_slots") or [],
            "gross_margin": 25.0, "monetary_growth_pct": 70.0,
            "volume_growth_pct": 5.0, "sales_to_mcap": 1.2,
            "profit_potential_pct": 40.0, "months_used": 12, "scale_factor": 1},
        "passes": {"1a_monetary_growth": True, "2_eps_trend": bool(e.get("pass")),
                   "4_sales_to_mcap": True, "5_industry": True},
        "insights": [{"step": "۲", "title": "لایهٔ ۲ — سابقهٔ ۳ سالهٔ سودسازی (EPS)",
                      "type": typ, "text": text, "row": row["markdown"],
                      "partial": bool(row["red"])}],
        "details": {"۲": {
            "title": "سابقهٔ سودسازی", "formula": "EPSy > EPSy−1 > EPSy−2",
            "source": "کدال", "calc": "EPS: " + " | ".join(cells),
            "period_row": row,
            "subchecks": [
                {"key": "2a", "label": "سابقهٔ ۳ سالهٔ EPS"
                                       + (" (تنها %s دوره موجود است)" % F._fa(row["available"])
                                          if row["red"] else ""),
                 "state": state, "value": " ← ".join(cells),
                 "threshold": "%d سال صعودی" % TH["eps_years"],
                 "partial": row["red"], "available_periods": row["available"],
                 "periods": row["periods"], "row": row["markdown"],
                 "detail": " | ".join("%s: %s" % (p["year"], p["value"])
                                      for p in row["periods"])}]},
        },
        "data_gaps": ([{"layer": "۲", "axis": "2_eps_trend",
                        "why": e.get("reason") or "", "partial": bool(row["red"]),
                        "available_periods": row["available"],
                        "required_periods": row["required"],
                        "fix": "همگام‌سازی کدال با mode=backfill"}]
                      if e.get("data_gap") else []),
    }


out = {"full": layer2("A"), "partial": layer2("E"), "nodata": layer2("N")}
d = os.path.join(ROOT, "dev", "fixtures")
os.makedirs(d, exist_ok=True)
p = os.path.join(d, "fts_v10_payloads.json")
with open(p, "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)
print("wrote", p)
print("partial row:", out["partial"]["details"]["۲"]["period_row"]["markdown"])
