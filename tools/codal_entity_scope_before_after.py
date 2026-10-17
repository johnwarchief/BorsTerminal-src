#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/codal_entity_scope_before_after.py — رأی‌هایِ جابه‌جا‌شده با لایۀ «شرکتِ دیگر»

لایۀ صفرِ `statement_rank` (صورتِ مالیِ شرکتِ فرعی/دیگری که کدال زیرِ نمادِ
هلدینگ منتشر می‌شود) رأیِ هیچ شاخصی را «به‌بهتر» نمی‌کند؛ باید شمارشِ واقعیِ
جابه‌جایی‌ها معلوم باشد، نه فقط «یک تابع اضافه شد». این ابزار فقط‌خواندنی است و
همان موتورِ canonical را دو بار اجرا می‌کند:

  الف) با لایۀ شرکت (کدِ امروز)
  ب) بی‌لایۀ شرکت (`title_entity_suffix` خنثی ⇒ رفتارِ پیش از این اصلاح)

و تفاوتِ رأی/عددِ منتشرشده را برایِ هر پنج شاخص می‌شمارد.

    python tools/codal_entity_scope_before_after.py [--db market.db] [--limit N]
"""
import argparse
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8")

import fts_engine as FE  # noqa: E402


def verdicts(conn, symbols):
    """خلاصۀِ رأی‌هایِ منتشرشدهٔ هر نماد (همان چیزی که کاربر درِ جدول می‌بیند)."""
    out = {}
    for sym in symbols:
        try:
            r = FE.scan_symbol(conn, sym, None)
        except Exception as e:                      # خطایِ یکِ نماد کلِ سنجش را نخورد
            out[sym] = ("ERR", (), ())
            continue
        ps = r.get("passes") or {}
        det = r.get("detail") or {}
        out[sym] = (
            r.get("verdict"),
            tuple((k, ps.get(k)) for k in sorted(ps)),
            tuple((k, _num(det.get(k))) for k in sorted(det)),
        )
    return out


def _num(v):
    """عددِ منتشرشدهٔ هر محور (برایِ این‌که «رأی یکی، عددِ فرق‌دار» هم دیده شود)."""
    if isinstance(v, dict):
        for k in ("margin_pct", "potential_pct", "growth_pct", "ratio", "sales_to_mcap",
                  "eps_series", "value"):
            if k in v:
                x = v[k]
                return round(float(x), 2) if isinstance(x, (int, float)) else str(x)[:24]
        return None
    return v if isinstance(v, (bool, type(None))) else str(v)[:24]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "market.db"))
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    db = os.path.abspath(a.db).replace("\\", "/")
    conn = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
    conn.row_factory = sqlite3.Row
    syms = [r[0] for r in conn.execute(
        "SELECT DISTINCT symbol FROM financial_statements ORDER BY symbol")]
    if a.limit:
        syms = syms[:a.limit]

    after = verdicts(conn, syms)
    orig = FE.title_entity_suffix
    FE.title_entity_suffix = lambda title: ""       # کنترلِ منفی: لایه خاموش
    try:
        before = verdicts(conn, syms)
    finally:
        FE.title_entity_suffix = orig
    conn.close()

    moved_verdict = [s for s in syms if before[s][0] != after[s][0]]
    moved_axes = [s for s in syms if before[s][1] != after[s][1]]
    print("نمادِ سنجیده‌شده:", len(syms))
    print("  رأیِ کلی جابه‌جا شد:", len(moved_verdict))
    print("  دست‌کم یکِ محورِ پنج‌گانه جابه‌جا شد:", len(moved_axes))
    print("  از PASSِ محورِ سه‌گانه به N/A/رد:",
          sum(1 for s in syms if before[s][0] == "PASS" and after[s][0] != "PASS"))
    for s in moved_axes[:12]:
        print("   ", s, "پیش:", before[s], "⇒ پس:", after[s])
    if len(moved_axes) > 12:
        print("    … و %d نمادِ دیگر" % (len(moved_axes) - 12))
    return 0


if __name__ == "__main__":
    sys.exit(main())
