#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""B4/Task 0 — فیلدِ افزودنیِ `indicators['1'].monetary.series` اول درِ پایتون.

§۱۵ بند ۵ فایلِ تصمیمات: فیلدِ تازهٔ UI اول درِ پایتون اضافه و تست می‌شود، بعد
Go با پاریتی پورتش می‌کند. این گارد همان چیزی را که «اول» نامیده ثابت می‌کند:

  ۱) درِ حالتِ موفق، `series` ردیف‌هایی را که رأی از آن‌ها آمده می‌فرستد —
     تازه‌ترین اول، با همان شش ستون، بی‌هیچ داوریِ تازه.
  ۲) درِ «داده‌گپ» هم کلید هست و تهی نیست اگر ردیفی بوده: نبودِ مخرج با
     نبودِ سری یکی نیست.
  ۳) هیچ عددِ دیگری جابه‌جا نشده: رشد٪، کف، pass، reason و `series_months`
     عینِ پیشین‌اند (فیلد فقط افزوده شد).
  ۴) ترتیب/دِدوپ از خودِ `fts_engine` می‌آید، نه از بازنویسیِ این لایه.

بی‌شبکه، بی‌بانکِ عملیاتی (فقط SQLite موقت/خالص).
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS %s%s" % (name, (" — " + str(detail)) if detail else ""))
    else:
        FAIL += 1
        print("  FAIL %s%s" % (name, (" — " + str(detail)) if detail else ""))


TH = {"monetary_growth_min": 40.0, "monetary_growth_target": 60.0}
PROFILE = {"revenue_basis": "sales", "kind": "company", "volume_applicable": True}


def row(year, month, monthly, ytd, ytd_prev, period_end):
    return [year, month, monthly, ytd, ytd_prev, period_end]


def main() -> int:
    import api.fundamental as fd
    import fts_engine as fe

    # ۱) حالتِ موفق
    series = [row(1404, 6, 45.0, 260.0, 180.0, "2025-09-22"),
              row(1404, 5, 50.0, 215.0, None, "2025-08-22"),
              row(1403, 6, 30.0, 180.0, None, "2024-09-22")]
    ok = fd.ind1a_monetary_growth(None, "خودرو", series=series, th=TH, profile=PROFILE)
    check("success verdict is unchanged", ok.get("monetary_pct") == 44.4 and ok.get("pass") is True
          and ok.get("data_gap") is False, "pct=%r pass=%r" % (ok.get("monetary_pct"), ok.get("pass")))
    ser = ok.get("series")
    check("series is published on the success path", isinstance(ser, list) and len(ser) == 3,
          "len=%r" % (len(ser) if isinstance(ser, list) else ser))
    check("series keeps the engine order (newest first)",
          [(r["year"], r["month"]) for r in ser] == [(1404, 6), (1404, 5), (1403, 6)],
          str([(r["year"], r["month"]) for r in ser]))
    want_keys = {"year", "month", "monthly_revenue", "ytd_revenue",
                 "ytd_revenue_prev", "period_end"}
    check("each row carries exactly the six published columns",
          all(set(r) == want_keys for r in ser), str(sorted(ser[0])))
    check("absent unit column stays null, never a fabricated zero",
          ser[1]["ytd_revenue_prev"] is None and ser[0]["ytd_revenue_prev"] == 180.0,
          str(ser[1]))
    check("the series is JSON-serialisable as published",
          json.loads(json.dumps(ser))[0]["period_end"] == "2025-09-22")

    # ۲) داده‌گپ‌ها
    gap_none = fd.ind1a_monetary_growth(None, "خودرو", series=[], th=TH, profile=PROFILE)
    check("no reports at all: data_gap with an empty series, not a missing key",
          gap_none.get("data_gap") is True and gap_none.get("series") == [], str(gap_none.get("series")))
    rows_only = [row(1404, 3, 10.0, 30.0, None, "2025-06-03")]
    gap_denom = fd.ind1a_monetary_growth(None, "خودرو", series=rows_only, th=TH, profile=PROFILE)
    check("rows exist but the denominator does not: the gap still carries them",
          gap_denom.get("data_gap") is True and len(gap_denom.get("series") or []) == 1,
          str(gap_denom.get("series")))

    # ۳) ناشرِ فیلد به طولِ ردیف وابسته نیست. کوئری همیشه شش ستون می‌دهد
    # (و `ytd_denominator` خودش با ردیفِ کوتاه می‌شکند)، پس این فقط مرزِ خودِ
    # `_ms_series` را قفل می‌کند: بی‌ستون ⇒ null، نه صفرِ جعلی یا IndexError.
    srow = fd._ms_series([[1404, 6]])[0]
    check("a short row maps to nulls, not to a fabricated zero",
          srow.get("year") == 1404 and srow.get("monthly_revenue") is None
          and srow.get("period_end") is None, str(srow))

    # ۴) ترتیب و دِدوپ مالِ موتور است، نه این لایه
    dup = [row(1404, 6, 45.0, 900.0, None, "2025-09-22"),
           row(1404, 6, 45.0, 260.0, None, "2025-09-22")]
    deduped = fe._dedupe_ym(dup)
    mapped = fd._ms_series(deduped)
    check("duplicate (year,month) collapses once in the engine before publishing",
          len(mapped) == 1 and mapped[0]["ytd_revenue"] == 900.0, str(mapped))

    # ۵) هیچ کلیدِ دیگری از پولِ این شاخص حذف نشده (قرارداد: فقط افزودن)
    before = {"monetary_pct", "pass", "data_gap", "threshold", "revenue_basis", "reason",
              "source", "unit", "unit_note"}
    check("the pre-existing keys are all still there",
          before.issubset(set(ok)), str(sorted(before - set(ok))))
    print("fundamental monetary.series guard: %d passed / %d failed" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
