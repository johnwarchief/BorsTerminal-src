# -*- coding: utf-8 -*-
"""codal_row_gate.py — گیتِ ردیفیِ نوشتنِ افزایشی (stdlib-only، در بیلد frozen هم هست)."""
from __future__ import annotations

import datetime as _dt

import codal_periods as CP


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def validate_extracted_row(kind, row, today=None):
    """(ok, code) — همان بررسی‌هایِ ردیفیِ staging، رویِ یک ردیفِ استخراج‌شده.

    شاخص‌ها از قراردادِ tupleِ `codal_fetcher.scrape_notice_row` می‌آیند:
    MS: 3=period_end، 6=monthly_revenue، 7=ytd_revenue، 13/14=provenance
    FS: 6=period_end، 7=publish_date، 8=revenue، 9=gross_profit، 19=url

    پیش از هر شاخص‌خوانی، طولِ tuple سنجیده می‌شود؛ ردیفِ بریده (مثلاً از
    پارسرِ نیمه‌کاره) `bad_shape` می‌گیرد، نه `IndexError` که کلِ batch را
    بیندازد.
    """
    required = 15 if kind == "ms" else 25
    if not row or len(row) < required:
        return False, "bad_shape"
    if kind == "ms":
        for idx, name in ((6, "monthly_revenue"), (7, "ytd_revenue")):
            v = _to_float(row[idx])
            if v is not None and v < 0:
                return False, "negative_revenue:%s" % name
        if not (str(row[13] or "").strip() or str(row[14] or "").strip()):
            return False, "missing_provenance"
        period = row[3]
    else:
        revenue = _to_float(row[8])
        gross = _to_float(row[9])
        if revenue is not None and revenue < 0:
            return False, "negative_revenue:revenue"
        if revenue is not None and gross is not None and gross > revenue:
            return False, "gross_gt_revenue"
        if not str(row[7] or "").strip() or not str(row[19] or "").strip():
            return False, "missing_provenance"
        period = row[6]
    parsed = CP.canonicalize(period)
    if parsed:
        jy, jm, jd = (int(x) for x in parsed.split("/"))
        day = today or _dt.date.today()
        ty, tm, td = CP.g2j_tuple(day.year, day.month, day.day)
        if (jy, jm, jd) > (ty, tm, td):
            return False, "future_period"
    return True, ""
