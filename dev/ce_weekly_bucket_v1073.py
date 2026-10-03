#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/ce_weekly_bucket_v1073.py — بستۀ هفتگیِ موتورِ اطمینان با سطلِ خودِ چارت می‌خواند

چرا: `confidence_engine` (ماتریسِ سه‌ستونۀ واچ‌لیست) و `api/chart.py` (موتورِ
کاننیکالِ FTS) هر دو «بستۀ هفتگی» و MA52 آن را منتشر می‌کنند. درِ چارت سطل
شنبه‌محور است (`_fts_resample`: `d - timedelta((weekday+2)%7)`) — چون نشستِ ایران
شنبه تا چهارشنبه است — ولی درِ اطمینان کلیدِ ISO دوشنبه‌محور بود. سنجشِ زنده
(`_audit/ce_weekly_calendar_impact.py`، ۷۴۸ نماد): شمارِ سطل در ۲۹ از ۴۰ نمادِ
نمونه فرق داشت، MA52 میانش ۰٫۹٪ و p90 ۲٫۲٪ (سقف ۱۲٫۲٪)، و نمونۀ سطلِ ایزو فقط
در ۱۱٫۷٪ موارد پایانِ همان هفتهٔ ایرانی بود.

این گارد سه چیز را قفل می‌کند:
  ۱) تقویم: شنبه و یکشنبه و چهارشنبۀ یک هفتهٔ ایرانی یک سطل، و جمعه/شنبه سطلِ بعد
     جدا — دقیقاً با همان قاعدۀ چارت، نه با ترجمۀ تازه.
  ۲) همتاییِ سری: بستۀ هفتگیِ `_weekly_closes` (نزولی) خانه‌به‌خانه با
     closeهای `_fts_resample(candles, 'W')` می‌خواند؛ پوشش (تعداد سطل‌هایِ مقابله‌شده)
     چاپ می‌شود، چون مقابله‌ای که چیزی نپوشاند عددِ «صفرِ اختلافِ بی‌معنی» می‌دهد.
  ۳) حالتِ شکست: کلیدِ ایزویِ پیشین درِ همان دیتاست باید اختلافِ غیرصفر بدهد؛ وگرنه
     سنجشِ بالا بی‌اثر است.

بدونِ شبکه و بدونِ market.db.
اجرا:  python dev/ce_weekly_bucket_v1073.py
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


import api.chart as CH                     # noqa: E402
import confidence_engine as CE             # noqa: E402

# شنبه ۱۴۰۵-۰۷-۰۴ = 2026-09-26؛ آن هفته: شنبه ۲۶، یکشنبه ۲۷، دوشنبه ۲۸،
# سه‌شنبه ۲۹، چهارشنبه ۳۰، جمعه ۰۲-۱۰ (تعطیل، ولی اگر روزی داده داشت سطلِ بعد).
SAT = datetime.date(2026, 9, 26)
ck(CE._week_key("2026-09-26") == "2026-09-26", "شنبه کلیدِ خودش است (گرفتیم %s)" % CE._week_key("2026-09-26"))
ck(CE._week_key("2026-09-27") == "2026-09-26", "یکشنبه در سطلِ همان هفتهٔ ایرانی (گرفتیم %s)" % CE._week_key("2026-09-27"))
ck(CE._week_key("2026-09-30") == "2026-09-26", "چهارشنبه در سطلِ همان هفتهٔ ایرانی (گرفتیم %s)" % CE._week_key("2026-09-30"))
ck(CE._week_key("2026-10-02") == "2026-09-26",
   "جمعهٔ همان هفته هم سطلِ تازه نمی‌خواهد (گرفتیم %s)" % CE._week_key("2026-10-02"))
ck(CE._week_key("2026-10-03") == "2026-10-03", "شنبهٔ هفتهٔ بعد سطلِ خودش است (گرفتیم %s)" % CE._week_key("2026-10-03"))
ck(CE._week_key("not-a-date") is None, "تاریخِ خراب ⇒ None، نه سطلِ جعلی")
ck(CE._week_key("") is None, "رشتهٔ خالی ⇒ None")


def iso_key_legacy(iso):
    """کلیدِ پیشین (ISO دوشنبه) — فقط برایِ حالتِ شکست."""
    try:
        return datetime.date(int(iso[0:4]), int(iso[5:7]), int(iso[8:10])).isocalendar()[:2]
    except (TypeError, ValueError):
        return None


def build_series(weeks=70):
    """سریِ روزانۀ ساختگی با نشست‌های شنبه…چهارشنبه؛ بستۀ هر هفته عددِ هفته است."""
    candles = []
    for w in range(weeks):
        sat = SAT - datetime.timedelta(weeks=weeks - 1 - w)
        for i, day in enumerate([0, 1, 2, 3, 4]):        # شنبه تا چهارشنبه
            px = 100.0 + w * 3.0 + i * 0.5              # آخرینِ روزِ هفته بالاترین
            candles.append({"time": (sat + datetime.timedelta(days=day)).isoformat(),
                            "open": px - 0.5, "high": px + 1, "low": px - 1,
                            "close": px, "volume": 10.0})
    return candles


def closes_from_chart(candles):
    """closeهای هفتگیِ چارت، تازه‌ترین اول — همان ترتیبی که `_weekly_closes` می‌دهد."""
    w = CH._fts_resample(candles, "W")
    return [float(x["close"]) for x in reversed(w)]


def closes_from_engine(candles):
    rows = [(c["time"], c["close"], c["high"], c["low"], c["volume"]) for c in reversed(candles)]
    return CE._weekly_closes(rows)


candles = build_series()
eng = closes_from_engine(candles)
chart = closes_from_chart(candles)
ck(len(eng) == len(chart) and len(eng) >= 60,
   "شمارِ سطلِ دو موتور یکی است (اطمینان %s، چارت %s)" % (len(eng), len(chart)))
mismatch = sum(1 for a, b in zip(eng, chart) if abs(a - b) > 1e-9)
ck(mismatch == 0, "بستۀ هفتگیِ اطمینان = بستۀ هفتگیِ چارت، خانه‌به‌خانه (ناهمخوانی: %s)" % mismatch)
print("پوششِ مقابله: %d سطلِ هفتگی از %d کندلِ روزانه" % (min(len(eng), len(chart)), len(candles)))

# نمونهٔ دقیق: بستۀ هر هفته باید آخرینِ روزِ همان هفتهٔ ایرانی (چهارشنبه) باشد،
# نه شنبه/یکشنبهٔ ابتدایِ آن — همان چیزی که ISO می‌ساخت.
last_week_close = float([c for c in candles if c["time"].startswith("2026-09-30")][0]["close"])
ck(eng[0] == last_week_close,
   "تازۀ‌ترین سطل = بستۀ چهارشنبهٔ %s (گرفتیم %s)" % (last_week_close, eng[0]))

# ---- حالتِ شکست: کلیدِ ایزو باید همین سنجه را بشکند ----
orig = CE._week_key
try:
    CE._week_key = iso_key_legacy
    legacy = closes_from_engine(candles)
    legacy_mismatch = sum(1 for a, b in zip(legacy, chart) if abs(a - b) > 1e-9)
    ck(legacy_mismatch > 0,
       "منفی‌کنترل: با کلیدِ ISO ناهمخوانیِ غیرصفر برمی‌گردد (گرفتیم %s از %s)"
       % (legacy_mismatch, len(chart)))
finally:
    CE._week_key = orig
ck(closes_from_engine(candles) == eng, "کلیدِ بازگردانده‌شده همان سریِ اول را می‌سازد")

# ---- دروازه باید با سریِ همتا کار کند و بی‌داده رأی ندهد ----
rows_desc = [(c["time"], c["close"], c["high"], c["low"], c["volume"]) for c in reversed(candles)]
gate = CE._weekly_gate(rows_desc, CE._cfg())
cfg = CE._cfg()
need = int(cfg["tech_weekly_ma"])
ma_manual = sum(chart[:need]) / float(need)
ck(abs(gate["ma52"] - ma_manual) < 0.01,
   "MA52ِ دروازة اطمینان از همان سبدِ چارت می‌آید (%s در برابر %s)" % (gate["ma52"], round(ma_manual, 2)))
ck(gate["w_bars"] == len(chart), "w_bars شمارِ واقعیِ سطل‌ها را می‌گوید (%s)" % gate["w_bars"])
# ۵۲ سطلِ کامل لازم است؛ هر هفته اینجا پنج نشست دارد، پس ۵۲×۵ ردیف.
ck(CE._weekly_gate(rows_desc[: need * 5], cfg)["bullish"] is not None,
   "سریِ کافی (۵۲ سطل) ⇒ دروازه رأی دارد")
ck(CE._weekly_gate(rows_desc[: need * 4], cfg)["weak"] is None,
   "به ۵۲ سطل نمی‌رسد ⇒ weak=None، نه «ضعیف» — بی‌داده رأی نیست")

failed = 0
for ok, msg in CHECKS:
    print(("  PASS " if ok else "  FAIL ") + msg)
    failed += 0 if ok else 1
print("\n%d checks, %d failed" % (len(CHECKS), failed))
print("CE WEEKLY BUCKET GUARD " + ("OK" if failed == 0 else "FAILED"))
sys.exit(1 if failed else 0)
