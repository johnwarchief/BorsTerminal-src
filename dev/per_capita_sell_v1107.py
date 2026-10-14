#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/per_capita_sell_v1107.py — گاردِ سرانۀ فروش حقیقی (بند ۴ مأموریتِ صحتِ داده).

چه چیزی بدونِ این گارد باورکردنی به نظر می‌رسد و دروغ است: `api/market.py` هر دو
سرانه را درِ یکِ پاس می‌سازد —

    buy_per_i  = buy_i_vol  / buy_count_i   ->  df["buy_power_i"]
    sell_per_i = sell_i_vol / sell_count_i  ->  df["sell_power_i"]

ولی `sell_power_i` درِ `_DROP_FIELDS` نشسته بود (فهرستِ «رابط این کلیدها را نمی‌خواند،
پس روی سیم نمی‌آید»). نتیجه درِ مقایسۀ هم‌نفسِ ۱۴۰۵-۰۷-۲۳ روی ۲٬۶۲۰ ردیف: سرانۀ
خرید سنجیده شد و سرانۀ فروش ۱٬۲۹۱ بار MISSING_MAPPING آمد — نه چون منبع عددی
ندارد، چون برنامۀ خودی آن را دور می‌ریخت. هر دو مرجع (تریدرزآرنا و رهاورد) سرانۀ
فروش را ستون می‌کنند و خروجیِ دیدهبان هم آن را می‌خواهد.

گارد چه قفلی می‌زند (و چرا بدونِ هرکدام باج داده می‌شود):
  ۱) هر دو کلید از فهرستِ حذف بیرون‌اند — با کنترلِ منفی رویِ یکِ کلیدِ
     هنوز-حذف‌شده (`tmax`)، وگرنه «بیرون است» یعنی «هیچ‌وقت نبود».
  ۲) مخرجِ صفر ⇒ NaN: نه ۰، نه ۱٫۰۰ِ بی‌طرف، نه بی‌نهایت (قراردادِ هر دو سمت).
  ۳) قدرتِ خرید از *همین* دو سرانه ساخته می‌شود، نه از فرمولِ سومِ خودی.
  ۴) هر دو سرانه درِ `_KEEP_NULL`اند تا تهی درِ سریال‌سازی صفر نشود.
  ۵) اسکیمای فرانت کلید را اعلام می‌کند (زodِ بی‌اعلام کلید را می‌بَرد و گاردِ
     پایتون سبزِ دروغ می‌دهد) و ستونِ خروجی هم واحدش را نوشته است.

بی‌شبکه، بی‌market.dbِ عملیاتی، بی‌نوشتن روی هیچ چیزی.
اجرا:  PYTHONIOENCODING=utf-8 python dev/per_capita_sell_v1107.py
خروجی: «N passed / M failed»، exit 0 یا 1
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASS = 0
FAIL = 0


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def ck(cond, label, detail=None):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   %s%s" % (label, "" if detail is None else "  ← %s" % (detail,)))
    else:
        FAIL += 1
        print("  FAIL %s%s" % (label, "" if detail is None else "  ← %s" % (detail,)))


def main() -> int:
    print("per_capita_sell_v1107 — سرانۀ فروش حقیقی روی سیم می‌آید")
    mkt = read("api/market.py")

    drop = re.search(r"_DROP_FIELDS = frozenset\(\((.*?)\n\)\)", mkt, re.S)
    ck(drop is not None, "بدنۀ _DROP_FIELDS خوانده شد")
    # سطرهای توضیح حساب نمی‌شوند: ورودیِ واقعیِ frozenset ملاک است
    body = "\n".join(l for l in (drop.group(1) if drop else "").splitlines()
                     if not l.strip().startswith("#"))
    for k in ("buy_power_i", "sell_power_i"):
        ck('"%s"' % k not in body, "%s درِ فهرستِ حذف نیست" % k)
    ck('"tmax"' in body,
       "کنترلِ منفی: کلیدِ حذف‌شدۀ دیگری درِ همان فهرست دیده می‌شود (سنسور کور نیست)")

    per = re.search(r'buy_per_i = df\["buy_i_vol"\] / _bc\.where\(_bc > 0\)\s*\n\s*'
                    r'sell_per_i = df\["sell_i_vol"\] / _sc\.where\(_sc > 0\)', mkt)
    ck(per is not None, "هر دو سرانه درِ یکِ پاس و با یکِ قرارداد حساب می‌شوند (مخرجِ صفر ⇒ NaN)")
    ck('df["buy_power_i"] = buy_per_i.round(0)' in mkt
       and 'df["sell_power_i"] = sell_per_i.round(0)' in mkt,
       "هر دو با یکِ گردکردۀ یکسان رویِ ستون می‌نشینند")
    ck('df["buyer_power"] = (buy_per_i / sell_per_i)' in mkt,
       "قدرت خرید از همین دو سرانه ساخته می‌شود (بی‌موتورِ دوم)")

    # این فهرست چند سطرِ توضیحِ فارسی *داخلِ خودش* دارد، پس regexِ «تا پرانتزِ
    # بسته» شکننده است؛ برشِ مستقیم از دو لنگرِ خوانا انجام می‌شود.
    i_keep = mkt.find("_KEEP_NULL = (")
    i_end = mkt.find("_nullish = frozenset(_KEEP_NULL)")
    keep_block = mkt[i_keep:i_end] if (i_keep >= 0 and i_end > i_keep) else ""
    ck(bool(keep_block), "فهرستِ نگه‌دارندۀ null خوانده شد",
       "%d کاراکتر" % len(keep_block))
    for k in ("buy_power_i", "sell_power_i", "buyer_power", "mcap"):
        ck('"%s"' % k in keep_block, "%s درِ _KEEP_NULL است (تهی ⇒ حذف، نه صفر)" % k)

    schema = read("frontend/src/shared/types/marketRow.ts")
    ck(re.search(r"sell_power_i:\s*num", schema) is not None,
       "اسکیمای ردیفِ بازار سرانۀ فروش را اعلام می‌کند (زod آن را نمی‌بَرد)")
    ck(re.search(r"buy_power_i:\s*num", schema) is not None,
       "و سرانۀ خرید هم اعلام شده (تک‌تعریفِ دو سمت)")

    exp = read("frontend/src/features/portfolio/lib/watchExport.ts")
    m_sell = re.search(r"key: 'sell_power_i', label: '([^']*)'", exp)
    ck(m_sell is not None and "سرانه فروش" in m_sell.group(1)
       and "سهم به ازای هر نفر" in m_sell.group(1),
       "خروجیِ دیدهبان ستونِ سرانۀ فروش را با واحدِ روشن دارد",
       m_sell.group(1) if m_sell else None)
    joined = exp.lower()
    ck("tradersarena" not in joined and "rahavard" not in joined,
       "درِ ستون‌های خروجی هیچ نام/عددِ مرجعی hardcode نشده")

    print("\n%d passed / %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
