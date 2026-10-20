# -*- coding: utf-8 -*-
"""dev/market_impact_official_v1.py — اثرِ رسمیِ نماد بر شاخص، نه برآورد.

منبع: `Index/GetInstEffect/0/1/{top}`. گارد:
  ۱) پنل‌های مثبت/منفی از `impact_points` رسمی می‌آیند و واحدشان «نقطهٔ شاخص» است؛
  ۲) جمعِ اثرها و تغییرِ رسمیِ شاخص در reconciliation می‌آید؛
  ۳) اگر اثر رسمی نرسد، مسیرِ برآوردی با برچسبِ صریح می‌ماند و ادعای رسمی نمی‌کند؛
  ۴) ذخیره/خواندنِ market_impact (نماد/نام/اثر) در حافظه سنجیده می‌شود.
خالص است؛ شبکه/DB عملیاتی لازم ندارد.
"""
from __future__ import annotations

import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import mstat_engine as E  # noqa: E402
import mstat_panels as P  # noqa: E402
import test_tsetmc as T  # noqa: E402

CHECKS = []
FAILS = []


def ck(label, cond, detail=""):
    CHECKS.append(bool(cond))
    print(("  ok   " if cond else "  FAIL ") + label +
          (("  <- " + str(detail)) if not cond and detail else ""))
    if not cond:
        FAILS.append(label)


def row(sym, ins, pcl=100.0, py=90.0, pct=10.0):
    return {
        "symbol": sym, "ins_code": ins, "name": sym + " co", "cls": E.PAPER_STOCK,
        "kind": "stock", "sector_name": "فلزات", "p_closing": pcl, "p_yesterday": py, "pct": pct,
        "total_shares": 1_000_000.0, "market_cap": pcl * 1_000_000.0,
        "_m": {"val": 1.0e9, "vol": 1.0e6, "trades": 100, "flow": 0.0},
    }


ROWS = [row("الف", "1"), row("ب", "2"), row("ج", "3")]
MI = {"last": 8_000_000.0, "change": 18_000.0, "pct": 0.23,
      "ew_last": 2_000_000.0, "ew_change": 1.0, "ew_pct": 0.1}
OFFICIAL = {"d_even": 20261020, "by_ins": {
    "1": {"symbol": "الف", "name": "الف co", "effect": 12_000.0, "p_closing": 100.0, "rank": 1},
    "2": {"symbol": "ب", "name": "ب co", "effect": -9_000.0, "p_closing": 90.0, "rank": 2},
    "3": {"symbol": "ج", "name": "ج co", "effect": 6_000.0, "p_closing": 80.0, "rank": 3},
}}


def run(official):
    old = (E.enrich, E.market_index, E.market_total_rials, E.market_impact)
    try:
        E.enrich = lambda _c: (ROWS, {})
        E.market_index = lambda _c: MI
        E.market_total_rials = lambda _c: (2.4e16, "test")
        E.market_impact = lambda _c: official
        return P.tops(None)
    finally:
        E.enrich, E.market_index, E.market_total_rials, E.market_impact = old


def panel(out, key):
    return next((p for p in out["panels"] if p["key"] == key), None)


def main():
    out = run(OFFICIAL)
    p = panel(out, "impact_pos")
    n = panel(out, "impact_neg")
    ck("positive panel exists", p is not None)
    ck("official impact unit is index points", p and p["unit"] == "نقطهٔ شاخص", p and p["unit"])
    ck("official formula names GetInstEffect",
       p and "GetInstEffect" in (p["formula"] or ""), p and p["formula"])
    ck("positive first is +12,000", p and p["rows"][0]["impact_points"] == 12_000.0,
       p and p["rows"][0].get("impact_points"))
    ck("negative first is -9,000", n and n["rows"][0]["impact_points"] == -9_000.0,
       n and n["rows"][0].get("impact_points"))
    r = out.get("reconciliation") or {}
    ck("reconciliation sums official effects", r.get("sum_of_impacts") == 9_000.0, r)
    ck("reconciliation reports official change", r.get("official_index_change") == 18_000.0, r)
    ck("reconciliation rel diff is computed", r.get("rel_diff_pct") == -50.0, r)

    out2 = run(None)
    p2 = panel(out2, "impact_pos")
    ck("fallback unit is not index points", p2 and p2["unit"] != "نقطهٔ شاخص", p2 and p2["unit"])
    ck("fallback flags official attribution unavailable",
       any(b.get("key") == "official_impact" and b.get("official_attribution_available") is False
           for b in out2.get("blockers") or []))

    con = sqlite3.connect(":memory:")
    n = T.save_market_impact(con, [
        {"insCode": "1", "instEffectValue": 2.5, "pClosing": 10,
         "instrument": {"lVal18AFC": "الف", "lVal30": "الف co"}},
        {"insCode": "2", "instEffectValue": -1.5, "pClosing": 9,
         "instrument": {"lVal18AFC": "ب", "lVal30": "ب co"}},
    ], 20261020, "2026-10-20 22:45:00")
    ck("save_market_impact writes two rows", n == 2, n)
    mi = E.market_impact(con)
    ck("read back symbol/name/effect",
       mi and mi["by_ins"]["1"]["symbol"] == "الف" and
       mi["by_ins"]["1"]["effect"] == 2.5 and mi["by_ins"]["2"]["effect"] == -1.5, mi)
    con.close()

    print("\n%d/%d passed" % (len(CHECKS) - len(FAILS), len(CHECKS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
