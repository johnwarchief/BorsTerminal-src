#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/weekly_veto_guard.py -- وتوی روند هفتگی: نزولی و خنثی رد، بی‌داده نه.

چرا: حکمِ ۱۲ مالک (docs/fts-notes/OWNER_RULINGS.md، چارت ۳ سطر ۳۱-۳۳) می‌گوید
درایم‌فریم هفتگی هم «نزولی» و هم «خنثی» باید reject باشد و فقط «صعودی» مجاز.
پیش از این همان رأی فقط *نمایش* داده می‌شد: جدول بنیادی بجِ قرمز می‌زد ولی
واچ‌لیستِ اسکرینر جای سهمِ وتوشده را نگه می‌داشت. این گارد سه چیز را قفل می‌کند:

  ۱) دسته‌بندیِ روند هفتگی چهارحالتی است (up/down/range/na) و ماتریسِ تصمیم
     دقیقاً همان را به PERMITTED / REJECT / UNKNOWN می‌برد.
  ۲) «کمبود داده» هرگز REJECT نمی‌شود (بی‌داده ≠ قرمز).
  ۳) اسکرینر روی decision == REJECT جای واچ‌لیست را آزاد می‌کند و دلیلش را
     در exclusion_reasons می‌نویسد؛ روی UNKNOWN این کار را نمی‌کند.

بدون شبکه و بدون market.db — کندل‌ها مصنوعی‌اند.
اجرا:  python dev/weekly_veto_guard.py
"""
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

CHECKS = []


def ck(cond, msg):
    CHECKS.append((bool(cond), msg))
    return cond


import api.chart as CH  # noqa: E402


def candles_from_weekly(closes, days_per_bar=5):
    """کندل روزانهٔ مصنوعی (صعودیِ زمانی) که هفت‌به‌هفت به بسته‌های `closes` می‌بندد.

    داخل هر هفته open/low/high حول close می‌چرخند ولی بستهٔ هفته همان close است،
    پس تشخیصِ ساختار فقط به توالیِ بسته‌های هفتگی وابسته می‌ماند.
    """
    out = []
    d = datetime.date(2024, 1, 1)          # دوشنبهٔ هفتهٔ ۱ ISO
    for wk, c in enumerate(closes):
        base = d + datetime.timedelta(weeks=wk)
        for i in range(days_per_bar):
            px = c * (1.0 + 0.002 * (i - 2))
            out.append({"time": (base + datetime.timedelta(days=i)).isoformat(),
                        "open": px, "high": px * 1.01, "low": px * 0.99,
                        "close": px, "volume": 1000.0})
    return out


# سه ساختارِ هفتگیِ سازگار با تشخیصِ پیوت (نیم‌پنجرهٔ k=2 ⇒ سقف‌ها باید دست‌کم
# سه هفته از هم فاصله داشته باشند، وگرنه سقفِ پایین‌تر در پنجرهٔ راست، پیوت را
# می‌سوزاند). UP صعودیِ تمیز، DOWN آینهٔ آن، RANGE سقف/کفِ مساوی.
UP = [11, 10, 12, 10.5, 10, 13, 11, 10.5, 14, 12, 11, 15, 13]
DOWN = [25 - x for x in UP]
RANGE = [10, 9, 14, 9, 10, 14, 9, 11, 14, 9, 12, 14, 10]


def decision(closes):
    fts = CH._fts_analyze_candles("آزمون", candles_from_weekly(closes))
    trend = fts["trend"]
    return trend["W"]["trend"], trend["matrix"]["decision"], trend


wk, dec, tr = decision(UP)
ck(wk == "up", "سقف/کفِ صعودی ⇒ روند هفتگی up (گرفتیم %s)" % wk)
ck(dec == "PERMITTED", "هفتگی صعودی ⇒ ورود مجاز (گرفتیم %s)" % dec)

wk, dec, _ = decision(DOWN)
ck(wk == "down", "سقف/کفِ نزولی ⇒ روند هفتگی down (گرفتیم %s)" % wk)
ck(dec == "REJECT", "هفتگی نزولی ⇒ وتوی کامل (گرفتیم %s)" % dec)

wk, dec, _ = decision(RANGE)
ck(wk == "range", "سقف/کفِ مساوی ⇒ روند هفتگی range، نه up (گرفتیم %s)" % wk)
ck(dec == "REJECT", "هفتگی خنثی هم reject است — حکم ۱۲ مالک (گرفتیم %s)" % dec)

short = CH._fts_analyze_candles("آزمون", candles_from_weekly([10, 11, 12]))
wk_na = short["trend"]["W"]["trend"]
dec_na = short["trend"]["matrix"]["decision"]
ck(wk_na == "na", "سه هفته ⇒ پیوتِ کافی نیست ⇒ trend=na (گرفتیم %s)" % wk_na)
ck(dec_na == "UNKNOWN",
   "بی‌داده ≠ وتو: decision=UNKNOWN، نه REJECT (گرفتیم %s)" % dec_na)

# ── گیتِ اسکرینر: دقیقاً همان منطقِ freed-slot، بدون FastAPI ──
src = open(os.path.join("api", "screener.py"), encoding="utf-8").read()
ck('r.get("tech_matrix_decision") == "REJECT"' in src,
   "اسکرینر وتو را از decision == REJECT می‌گیرد (از همان داورِ انحصاری)")
gate = src.split('if r.get("tech_matrix_decision") == "REJECT":')[1].split("else:")[0]
ck('r["watchlist"] = False' in gate and 'r["weekly_veto"] = True' in src,
   "ردیفِ وتوشده جای واچ‌لیست را آزاد می‌کند و weekly_veto می‌گیرد")
ck("UNKNOWN" not in gate, "UNKNOWN جای واچ‌لیست را نمی‌سوزاند")
ck('why' in gate and 'exclusion_reasons' in gate,
   "دلیلِ وتو در exclusion_reasons نوشته می‌شود (پنهان نمی‌ماند)")

failed = 0
for ok, msg in CHECKS:
    print(("  PASS " if ok else "  FAIL ") + msg)
    failed += 0 if ok else 1
print("\n%d checks, %d failed" % (len(CHECKS), failed))
print("WEEKLY VETO GUARD " + ("OK" if failed == 0 else "FAILED"))
sys.exit(1 if failed else 0)
