#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 32H: Codal assembly `DividendPerShare` parser + live formula lock.

No network, no DB: the parser is pure, and the five formula cases are the
values measured live on 2026-10-26 from the assembly Decision pages and the
official TSETMC daily CSV `CLOSE` (not `LAST`).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import adjustment_engine as AE  # noqa: E402
import codal_dividends as CD  # noqa: E402

P = F = 0


def check(name, got, want):
    global P, F
    if got == want:
        P += 1
        print("  ok   %s" % name)
    else:
        F += 1
        print("  FAIL %s  got=%r want=%r" % (name, got, want))


def close(name, got, want, tol=1e-12):
    global P, F
    if got is not None and abs(got - want) <= tol:
        P += 1
        print("  ok   %s" % name)
    else:
        F += 1
        print("  FAIL %s  got=%r want=%r" % (name, got, want))


PAGE = """
<html><body><table>
<tr><td>TotalEndingRetainedEarnings</td><td>سود (زیان) انباشته پایان دوره</td><td>(۱٬۹۹۹٬۸۵۰)</td></tr>
<tr><td>EarningsPerShareAfterTax</td><td>سود (زیان) خالص هر سهم- ریال</td><td>۳٬۴۵۱</td></tr>
<tr><td>DividendPerShare</td><td>سود نقدی هر سهم (ریال)</td><td>۸۵۱</td></tr>
<tr><td>ListedCapital</td><td>سرمایه</td><td>۲٬۳۵۰٬۰۰۰</td></tr>
</table></body></html>
"""

check("الف۱ سود نقدی هر سهم از صفحهٔ مجمع: ۸۵۱", CD.parse_dividend_per_share(PAGE), 851.0)
check("الف۲ عددِ منفیِ سودِ انباشته به‌جایِ DPS گرفته نمی‌شود",
      CD.parse_dividend_per_share(PAGE), 851.0)
check("الف۳ صفحهٔ بی‌فیلد → None",
      CD.parse_dividend_per_share("<html><body>هیچ</body></html>"), None)
check("الف۴ برچسب بی‌عدد → None",
      CD.parse_dividend_per_share(
          "<td>DividendPerShare</td><td>سود نقدی هر سهم (ریال)</td><td>-</td>"), None)
check("الف۵ صفرِ معتبر → ۰",
      CD.parse_dividend_per_share(
          "<td>DividendPerShare</td><td>سود نقدی هر سهم (ریال)</td><td>۰</td>"), 0.0)
check("الف۶ رقمِ اعشاری با جداکنندهٔ فارسی",
      CD.parse_dividend_per_share(
          "<td>DividendPerShare</td><td>سود نقدی هر سهم (ریال)</td><td>۱٬۲۳۴٫۵</td>"),
      1234.5)

# Live cases: assembly DPS (Codal Decision page) + official TSETMC CLOSE + the
# reference ratio from the R32B pack. All five are exact to 1e-12.
LIVE = [
    ("سپيدار", 14000.0, 851.0, 0.9426974614504081),
    ("كگهر", 16230.0, 3200.0, 0.8353062274832728),
    ("فغدير", 8430.0, 1900.0, 0.8160696999031957),
    ("وسپهر", 7460.0, 1000.0, 0.8817966903073281),
    ("كربن", 5850.0, 3480.0, 0.627009646302251),
]
for name, px, dps, ref in LIVE:
    r, status = AE.event_factor({"kind": AE.KIND_CASH_DIVIDEND,
                                 "reference_price": px,
                                 "dividend_per_share": dps})
    check("ب۱ %s وضعیت ok" % name, status, AE.OK)
    close("ب۲ %s close/(close+dps) = مرجع" % name, r, ref)

print("\nنتیجه: %d سبز، %d قرمز" % (P, F))
sys.exit(0 if F == 0 else 1)
