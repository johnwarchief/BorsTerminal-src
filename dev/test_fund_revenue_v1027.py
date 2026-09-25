"""dev/test_fund_revenue_v1027.py — رأیِ مالک: «سود سهام» هرگز فروش نمی‌شود

رأی ۱۴۰۵-۰۷-۰۳: اگر شیتِ صورتِ سود و زیان ردیفِ «جمع درآمدها» را نداشت، فروش
خالی می‌ماند؛ هیچ خطِ جزءِ درآمد (سود سهام، سود اوراق، سایر درآمدها) جانشینِ
ردیفِ جمع نمی‌شود. باگِ تاریخیِ همان‌جا بود: دو گزارشِ صندوقِ آلا در جدول
«فروش» = 21,390 دارند که در فایلِ کدال ردیفِ «سود سهام»ِ سالِ قبل است.

این تست رویِ همان شکلِ شیتِ صندوق اجرا می‌شود و هر دو جهت را می‌بندد:
  • revenue نباید از خطِ جزء برداشته شود (این‌جا None است چون «جمع درآمدها»
    در الگوهای فروش نیست — صندوق فروش عملیاتی ندارد)
  • net_profit باید درست بخوانده شود (یعنی None بودنِ فروش از خرابیِ پارس نیست)
  • اگر روزی «جمع درآمدها» به الگوهای فروش اضافه شد، فقط همان ردیف مچ شود
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import codal_fetcher as cf  # noqa: E402

ROWS = [
    (4, "درآمدها", None),
    (5, "سود (زيان) فروش اوراق بهادار", 285082),
    (6, "سود (زيان) تحقق نيافته نگهداري اوراق", 738742),
    (7, "سود سهام", 21390),
    (8, "سود اوراق بهادار با درآمد ثابت", 2955900),
    (9, "ساير درآمدها", 2337),
    (10, "جمع درآمدها", 3982061),
    (14, "جمع هزينه ها", -140749),
    (15, "سود (زيان) قبل از هزينه‌هاي مالي", 3841312),
    (17, "سود (زيان) خالص", 3839775),
]


def _ds():
    cells = []
    for r, label, value in ROWS:
        cells.append({"rowSequence": r, "columnSequence": 1, "value": label})
        if value is not None:
            cells.append({"rowSequence": r, "columnSequence": 2, "value": str(value)})
    return {"sheets": [{"tables": [{
        "description": "کليه مبالغ به ميليون ريال است", "cells": cells}]}]}


def main():
    out, rank = {}, {}
    unit = cf.parse_tables(_ds(), out, rank)
    fails = []

    if out.get("revenue") == 21390:
        fails.append("فروش از ردیفِ «سود سهام» برداشته شد — دقیقاً همان باگِ آلا")
    if out.get("revenue") not in (None, 3982061):
        fails.append("فروش از هیچ‌کدام از ردیفِ جمع یا خالی نیامده: %r" % (out.get("revenue"),))
    if out.get("net_profit") != 3839775:
        fails.append("سود خالص درست خوانده نشد: %r" % (out.get("net_profit"),))
    if "ريال" not in (unit or "").replace("ی", "ي"):
        fails.append("واحدِ شیت از دست رفت: %r" % (unit,))

    for f in fails:
        print("FAIL", f)
    if fails:
        print("FUND REVENUE GUARD FAILED")
        return 1
    print("revenue=%r net_profit=%r unit=%r" % (out.get("revenue"), out.get("net_profit"), unit))
    print("FUND REVENUE GUARD OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
