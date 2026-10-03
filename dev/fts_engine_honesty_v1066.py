"""dev/fts_engine_honesty_v1066.py — چهار جا که موتورِ FTS عددِ جا‌زده منتشر می‌کرد

چرا: در آدیتِ تب تکنیکال (۱۴۰۵-۰۷-۰۹) چهار باگِ محاسبه در `api/chart.py` پیدا شد
که هیچ‌کدام خطا نمی‌دادند؛ فقط عددِ غلط می‌دادند و همان عدد در تابلو، قیف،
سبد و کارتِ پلن خوانده می‌شود:

  ۱) تجمیع هفتگی ISO (دوشنبه‌محور) بود ولی بازارِ ایران شنبه تا چهارشنبه باز
     است؛ شنبه و یکشنبه به هفتهٔ قبل می‌افتادند، پس «روند هفتگی»ِ وتو روی سبدی
     از روزها ساخته می‌شد که کاربر روی چارت نمی‌بیند (چارتِ فرانت شنبه‌محور است).
  ۲) کمربندهای فیبو همیشه «از سقف به پایین» اندازه گرفته می‌شدند؛ روی موجِ
     نزولی همان کمربندِ ۳۳–۴۰٪ جایی نزدیک سقف می‌افتاد — یعنی ابتدایِ ریزش،
     نه منطقۀ بازگشت.
  ۳) حدِ ضررِ سخت کمینۀ بیست کندلِ آخر را می‌گرفت و کندلِ آخر نشستِ جاریِ زنده
     است؛ یک سایۀ لحظه‌ای حدِ ضررِ منتشرشده را پایین می‌کشید.
  ۴) MA52 هفتگی با «کمترینِ ۵۲ و طولِ سابقه» ساخته می‌شد و همان میانگینِ
     کوتاه‌تر با نامِ ma52 منتشر و در شرطِ ساعتِ شنی به کار می‌رفت.
  ۵) روند روزانۀ na («کمتر از دو پیوت کامل») در آغالتِ «هفتگی صعودی + روزانۀ
     خنثی» می‌نشست و PERMITTED با پیشنهادِ ستاپ می‌داد.

رأیِ پایلوت در هر دو فورکِ قضاوتی (گزینهٔ «الف»، ۰٫۹۹ و ۰٫۹۴): صادق‌سازی —
na یعنی نظرِ ندادن، MA52 یعنی پنجاه‌دو کندل، و عددی که موتور نگفته نباید
جایِ عددِ دیگر را بزند.

بی‌شبکه و بی‌market.db می‌دود. هر پنج شاهدِ مثبت + شاهدِ منفیِ خودش.
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api.chart as CH  # noqa: E402

FAILS = []
CHECKS = [0]


def ck(label, cond):
    CHECKS[0] += 1
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        FAILS.append(label)


def bar(day, price, low=None, high=None):
    p = float(price)
    return {"time": day.isoformat(), "open": p, "high": float(high if high is not None else p),
            "low": float(low if low is not None else p), "close": p, "volume": 1000.0}


def days(n, start=datetime.date(2024, 3, 4)):
    return [start + datetime.timedelta(days=i) for i in range(n)]


# ── ۱) هفتهٔ شنبه‌محور ────────────────────────────────────────────────────────
sat = datetime.date(2026, 9, 26)
ck("تاریخِ آزمون واقعاً شنبه است", sat.weekday() == 5)
# ده روزِ پیوسته از شنبه ⇒ دقیقاً دو سبد (شنبه…جمعه، شنبه…دوشنبه)
w = CH._fts_resample([bar(d, 100 + i) for i, d in enumerate(days(10, sat))], "W")
ck("ده روزِ شنبه‌محور ⇒ دو کندلِ هفتگی", len(w) == 2)
ck("سبدِ اول با شنبه باز می‌شود", w[0]["open"] == 100.0)
ck("سبدِ دوم از شنبۀ بعد است", w[1]["open"] == 107.0)
# شاهدِ ریشه: در ISO شنبه و دوشنبۀ همان هفتهٔ کاری ایران در دو هفتهٔ جدا هستند
iso_first = sat.isocalendar()
ck("شنبه و دوشنبه در ISO دو هفته‌ان (ریشۀ باگ)",
   (sat + datetime.timedelta(days=2)).isocalendar()[1] != iso_first[1])


# ── ۲) کمربند فیبو در جهتِ موج ───────────────────────────────────────────────
# موجِ نزولیِ ساختگی: صعود تا ۲۰۰ در کندلِ ۱۸ (پیوتِ سقفِ تأییدشده) و سپس
# افت تا ۱۸۰؛ پس «آخرین پیوت، سقف است» ⇒ جهتِ موج down.
peak_i, top, bot = 18, 200.0, 180.0
down_prices = [100 + 5.5 * i for i in range(peak_i + 1)] + \
              [top - (top - bot) * (i + 1) / (29 - peak_i) for i in range(29 - peak_i)]
down = [bar(d, p) for d, p in zip(days(len(down_prices)), down_prices)]
swings = CH._fts_swings(down, k=CH._FTS_SWING_K)
leg = CH._fts_fib_leg(down, swings)
ck("ساختارِ آزمون موجِ نزولی می‌دهد", leg is not None and leg["direction"] == "down")
zones = CH._fts_fib_zones(down, swings)
belt = zones["zone_33_40"] if zones else None
ck("کمربند روی موجِ نزولی ساخته می‌شود", belt is not None)
if belt:
    # ۳۳–۴۰٪ *بازگشت* از کف: بینِ کف و سقف، و نزدیکِ کف — نه چسبیده به سقف
    ck("کمربندِ موج نزولی بالای کف است", belt["lo"] > leg["low"] - 1e-6)
    ck("کمربندِ موج نزولی زیر سقف است", belt["hi"] < leg["high"] + 1e-6)
    ck("کمربندِ ۳۳–۴۰٪ در فاصلۀ ۳۳–۴۰٪ از کف است",
       0.30 <= (belt["lo"] - leg["low"]) / (leg["high"] - leg["low"]) <= 0.43)
    ck("سطحِ ۰٫۵ midway است (دو طرفِ موج یکی)",
       any(abs(lv["price"] - (leg["high"] * leg["low"]) ** 0.5) < 0.6 for lv in zones["levels"] if lv["ratio"] == 0.5))
# موجِ صعودی باید دست‌نخورده بماند: سطحِ ۰ از سقفِ موج شروع می‌شود
up_prices = [200 - 5 * i for i in range(12)] + [145 + 6 * i for i in range(18)]
up = [bar(d, p) for d, p in zip(days(len(up_prices), datetime.date(2024, 1, 6)), up_prices)]
sw_up = CH._fts_swings(up, k=CH._FTS_SWING_K)
leg_up = CH._fts_fib_leg(up, sw_up)
z_up = CH._fts_fib_zones(up, sw_up)
if leg_up and leg_up["direction"] == "up" and z_up:
    ck("کمربندِ ۳۳–۴۰٪ موج صعودی از سقف پایین آمده",
       z_up["zone_33_40"]["hi"] < leg_up["high"] + 1e-6 and z_up["zone_33_40"]["hi"] > leg_up["low"])
else:
    ck("موج صعودیِ آزمون ساخته شد", leg_up is not None)


# ── ۳) حدِ ضرر سخت و کندلِ نیمه‌کار ──────────────────────────────────────────
hist = [bar(d, 1000 + i, low=990 + i) for i, d in enumerate(days(24))]
stop_a = CH._fts_exit_layer1(hist)["hard_stop"]
hist_deep = list(hist)
hist_deep[-1] = bar(days(24)[-1], 1020, low=100)  # سایۀ لحظه‌ایِ امروز
stop_b = CH._fts_exit_layer1(hist_deep)["hard_stop"]
ck("سایۀ کندلِ امروز حدِ ضرر را جابه‌جا نمی‌کند", stop_a == stop_b)
# کمینۀ بیست کندلِ بسته‌شده = بیست‌ویکمی از انتها منهای آخرین
want = min(float(c["low"]) for c in hist[:-1][-20:]) * 0.95
ck("حدِ ضرر از کمینۀ کندل‌هایِ بسته‌شده ساخته می‌شود", abs(stop_a - round(want, 2)) < 0.01)
hist_prev = list(hist)
hist_prev[-2] = bar(days(23)[-2], 1020, low=500)  # دیروز واقعاً کف بوده
ck("کفِ کندلِ بسته‌شدۀ دیروز حدِ ضرر را می‌سازد (شاهدِ منفی)",
   CH._fts_exit_layer1(hist_prev)["hard_stop"] < stop_a)


# ── ۴) MA52 فقط با پنجاه‌دو کندلِ هفتگی ─────────────────────────────────────
short_series = [bar(d, 100 + (i % 7), low=99 + (i % 7)) for i, d in enumerate(days(100))]
hg_short = CH._fts_analyze_candles("SHORT", short_series)["hourglass"]
ck("با ۱۵ تا ۵۱ کندلِ هفتگی ma52 منتشر نمی‌شود", hg_short["ma52"] is None)
ck("و ساعتِ شنی در آن حالت نظر نمی‌دهد (None، نه False — نبودِ MA52 رأی نیست)",
   hg_short["active"] is None and hg_short["action"] == "UNKNOWN")
ck("دلیلِ خاموشی در desc می‌آید", "52" in (hg_short["desc"] or ""))
ck("تعدادِ کندلِ هفتگی هم منتشر می‌شود", isinstance(hg_short.get("weekly_bars"), int))

long_series = [bar(d, 100 + (i % 11), low=99 + (i % 11)) for i, d in enumerate(days(420))]
hg_long = CH._fts_analyze_candles("LONG", long_series)["hourglass"]
ck("با ≥۵۲ کندلِ هفتگی ma52 عدد می‌شود", isinstance(hg_long["ma52"], (int, float)))


# ── ۵) روزانۀ na نظر نمی‌دهد ────────────────────────────────────────────────
# این شاخه با سریِ طبیعی تقریباً دست‌نیافتنی است (سریِ کوتاه که روزانۀ na دارد
# هفتگی‌اش هم na است)، پس شاخه را با جعلِ طبقه‌بند می‌سنجیم: روزانه na، هفتگی up.
N_D = 200
real_classify = CH._fts_classify_trend


def fake_classify(swings, series=None):
    t = "na" if series is not None and len(series) == N_D else "up"
    return {"trend": t}


CH._fts_classify_trend = fake_classify
try:
    mx = CH._fts_analyze_candles("NA", [bar(d, 100 + (i % 5)) for i, d in enumerate(days(N_D))])["trend"]["matrix"]
finally:
    CH._fts_classify_trend = real_classify
ck("هفتگی صعودی + روزانۀ na ⇒ UNKNOWN", mx["decision"] == "UNKNOWN")
ck("و هیچ ستاپی پیشنهاد نمی‌شود", mx["setup"] == "NONE")
ck("دلیلِ na در desc می‌آید", "سنجیده نشده" in (mx["desc"] or ""))
mx_range = None
real_classify2 = CH._fts_classify_trend


def fake_range(swings, series=None):
    return {"trend": "range" if series is not None and len(series) == N_D else "up"}


CH._fts_classify_trend = fake_range
try:
    mx_range = CH._fts_analyze_candles("RG", [bar(d, 100 + (i % 5)) for i, d in enumerate(days(N_D))])["trend"]["matrix"]
finally:
    CH._fts_classify_trend = real_classify2
ck("خنثیِ واقعی همان PERMITTEDِ سابق می‌ماند (شاهدِ منفی)", mx_range["decision"] == "PERMITTED")

# ── ۶) سطوح فیبو: فرانت و بک‌اند باید یک فهرست را بگویند ─────────────────────
import re

FE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "frontend", "src", "features", "technical", "lib", "ftsOverlays.ts")
with open(FE_PATH, encoding="utf-8") as fh:
    fe_src = fh.read()
m = re.search(r"FTS_FIB_LEVELS\s*=\s*\[([^\]]+)\]", fe_src)
fe_levels = [float(x.strip()) for x in m.group(1).split(",")] if m else []
ck("سطوح فیبوی فرانت عینِ جزوۀ بک‌اند است (۰ تا ۱، با ۰٫۵)",
   fe_levels == [float(r) for r in CH._FTS_FIB_LEVELS])

print()
print(f"RESULT: {'PASS' if not FAILS else 'FAIL'} — {CHECKS[0] - len(FAILS)}/{CHECKS[0]}")
if FAILS:
    for f in FAILS:
        print("  missed: " + f)
    sys.exit(1)
print("FTS ENGINE HONESTY GUARD OK")
