# -*- coding: utf-8 -*-
"""گاردِ fixtureهایِ روند — سه جامعۀِ ساختگی، سه رأیِ چارتِ FTS صفحهٔ ۲.

منبعِ حکم: `docs/FTS.CHART_3.pdf` صفحۀ ۲ (تکنیکال:T) و جزوۀ دست‌نویس ص ۷
(تعریفِ روند = ساختارِ سقف/کف؛ نه MA):
    هفتگی نزولی ⇒ REJECT · هفتگی خنثی ⇒ REJECT · هفتگی صعودی ⇒ بررسیِ روزانه
    روزانه صعودی ⇒ جت/پولبک · نزولی ⇒ فیبو/CHoCH · خنثی ⇒ آخرین کف/سقف
ادعایِ محوریِ این سوئیت (فاز ۴ دستورِ مالک): «روزانه صعودی ⇒ PASS» هرگز با
هفتگیِ نزولی/خنثی رخ نمی‌دهد — هفتگی دروازۀِ یک‌طرفه است، نه تزئین.

اجرا: PYTHONIOENCODING=utf-8 python dev/fts_trend_fixtures_v1075.py
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import chart as CH  # noqa: E402

PASSED = 0
FAILED = []


def ck(cond, what, detail=""):
    global PASSED
    if cond:
        PASSED += 1
        print(f"  ok   {what}")
    else:
        FAILED.append(what)
        print(f"  FAIL {what}  {detail}")


def week_bars(week_open, o, h, l, c, days=(0, 1, 2, 3)):
    """چهار کندلِ شنبه‌تا‌سه‌شنبه برای یک هفته — تجمیعِ شنبه‌محورِ موتور همین
    سبد را به یک کندلِ هفتگی بدل می‌کند (high/low = ماکس/مینِ سبد)."""
    sat = week_open
    out = []
    for i, d in enumerate(days):
        date = (sat + dt.timedelta(days=d)).isoformat()
        if i == 0:
            out.append({"time": date, "open": o, "high": h, "low": l, "close": (o + c) / 2, "volume": 1e6})
        elif i == len(days) - 1:
            out.append({"time": date, "open": (o + c) / 2, "high": h, "low": l, "close": c, "volume": 1e6})
        else:
            out.append({"time": date, "open": c if i % 2 else o, "high": h, "low": l,
                        "close": (o + c) / 2, "volume": 1e6})
    return out


def build(weeks, start=dt.date(2024, 1, 6)):  # 2024-01-06 = شنبه
    """weeks = [(high, low, open, close)] — بدنه‌ها داخلِ [low, high] می‌مانند
    تا کف/سقفِ هفتگی دقیقاً همان عددِ خواسته‌شده باشد."""
    out = []
    for i, (h, l, o, c) in enumerate(weeks):
        out += week_bars(start + dt.timedelta(weeks=i), o, h, l, c)
    return out


BULL = [(100 + 10 * k, 88 + 10 * k, 90 + 10 * k, 98 + 10 * k) for k in range(14)]
BEAR = [(120 - 8 * k, 100 - 8 * k, 118 - 8 * k, 102 - 8 * k) for k in range(14)]
RANGE = [(110, 90, 95, 105) if k % 2 == 0 else (110, 90, 105, 95) for k in range(14)]


def analyze(weeks, daily_tail=None):
    candles = build(weeks)
    if daily_tail:
        candles = candles + daily_tail
    return CH._fts_analyze_candles("آزمون", candles)


def mx(out):
    return out["trend"]["matrix"]


# ── ۱) هفتگی صعودی ───────────────────────────────────────────────────────────
o = analyze(BULL)
ck(o["trend"]["W"]["trend"] == "up", "ساختارِ HH/HL هفتگی ⇒ up", str(o["trend"]["W"]))
ck(mx(o)["decision"] == "PERMITTED", "هفتگی صعودی ⇒ دروازه باز", str(mx(o)))
ck(mx(o)["setup"] == "JET_OR_PULLBACK_HOLD", "روزانۀ صعودی ⇒ جت/پولبک (عینِ چارت ص ۲)", str(mx(o)["setup"]))

# ── ۲) هفتگی نزولی ───────────────────────────────────────────────────────────
o = analyze(BEAR)
ck(o["trend"]["W"]["trend"] == "down", "ساختارِ LH/LL هفتگی ⇒ down", str(o["trend"]["W"]))
ck(mx(o)["decision"] == "REJECT", "هفتگی نزولی ⇒ REJECT", str(mx(o)))

# ── ۳) هفتگی خنثی (کف و سقف‌هایِ برابرِ جزوه) ────────────────────────────────
o = analyze(RANGE)
ck(o["trend"]["W"]["trend"] == "range", "برابریِ کف/سقف ⇒ range (تلورانسِ ۰٫۵٪)", str(o["trend"]["W"]))
ck(mx(o)["decision"] == "REJECT", "هفتگی خنثی ⇒ REJECT (چارت ص ۲، سطرِ سوم)", str(mx(o)))

# ── ۴) ادعایِ محوری: روزانۀ صعودی هفتگیِ بسته را نمی‌شکند ────────────────────
# V-بانتوم: ۱۲ هفته نزولیِ تمیز، بعد ۱۶ کندلِ روزانۀ صریح: کف‌شکنیِ ۶،
# بازگشتِ ۳۴، پولبکِ ۱۲، رالیِ ۳۶ — درِ روزانه پیوت‌ها HH/HL می‌شوند ⇒ up؛
# هفتگی چون سقفِ ۳۶ هنوز دو هفتهِ راست تأیید نشده و کف‌ها یکی‌اند، بر مبنایِ
# recent-window نزولی می‌ماند. اگر جایی «روزانه» بر «هفتگی» غالب شود این
# fixture قرمز می‌شود.
def daily_tail(start, rows):
    return [{"time": (start + dt.timedelta(days=i)).isoformat(),
             "open": o, "high": h, "low": l, "close": c, "volume": 1e6}
            for i, (h, l, o, c) in enumerate(rows)]


TAIL_V = [(14, 6, 12, 7), (22, 7, 7, 14), (34, 12, 14, 30), (30, 16, 30, 20),
          (26, 14, 20, 16), (24, 12, 16, 13), (28, 13, 13, 24), (32, 15, 24, 30),
          (35, 18, 30, 33), (36, 20, 33, 35), (33, 24, 35, 28), (30, 22, 28, 26),
          (29, 21, 26, 25), (27, 22, 25, 24), (26, 23, 24, 25), (28, 24, 25, 27)]
tail_start = dt.date(2024, 1, 6) + dt.timedelta(weeks=12)
o = CH._fts_analyze_candles("آزمون", build(BEAR[:12]) + daily_tail(tail_start, TAIL_V))
ck(o["trend"]["W"]["trend"] == "down", "V-بانتوم: هفتگی هنوز down", str(o["trend"]["W"]))
ck(o["trend"]["D"]["trend"] == "up", "… ولی روزانه up شده (تلهٔ آزمون)", str(o["trend"]["D"]))
ck(mx(o)["decision"] == "REJECT", "روزانۀ صعودی ⇒ PASS نمی‌شود وقتی هفتگی نزولی است", str(mx(o)))
ck("وتوی" in mx(o)["desc"] or "ممنوعیت" in mx(o)["desc"], "دلیلِ وتوی هفتگی در desc نوشته شده", mx(o)["desc"])

# ── ۵) بی‌ساختار ⇒ UNKNOWN، نه REJECT (کمبودِ داده رأی نیست) ─────────────────
tiny = build(BULL[:3])
o = CH._fts_analyze_candles("آزمون", tiny)
ck(o["trend"]["W"]["trend"] == "na", "سه هفته ⇒ هفتگی na", str(o["trend"]["W"]["trend"]))
ck(mx(o)["decision"] == "UNKNOWN", "na ⇒ UNKNOWN — بی‌داده «رد» نمی‌شود", str(mx(o)))

# ── ۶) تجمیعِ هفتگی واقعی است، نه سیگنالِ روزانهٔ دُوروزَه ───────────────────
w = CH._fts_resample(build(BULL), "W")
ck(len(w) == 14, "۵۶ روز = ۱۴ کندلِ هفتگی", str(len(w)))
ck(all(dt.date.fromisoformat(c["time"]).weekday() <= 4 for c in w), "کلیدِ هفته شنبه‌محور می‌بندد", str(w[-1]["time"]))
first = w[0]
ck(abs(first["high"] - BULL[0][0]) < 1e-6 and abs(first["low"] - BULL[0][1]) < 1e-6,
   "high/low هفتگی = مین/ماکسِ سبدِ روزانه", str(first))

# ── ۷) شاخه‌هایِ روزانه زیرِ چترِ صعودی ──────────────────────────────────────
# هفتگی صعودی + روزانۀ نزولی ⇒ FIB_CHOCH_STEP_ENTRY. دنبالهٔ نزولی رویِ
# همان سطحِ BULL می‌نشیند (بی‌پرشِ قیمت) تا هفتگی up بماند و فقط روزانه down شود.
H_DN = [210, 208, 206, 216, 212, 208, 204, 214, 210, 206, 202, 212,
        208, 204, 200, 210, 206, 202, 198, 194, 190, 198]
L_DN = [204, 202, 200, 210, 206, 202, 198, 208, 204, 200, 196, 206,
        202, 198, 194, 204, 200, 196, 192, 198, 194, 190]
TAIL_DN = [(h, l, h - 1, l + 1) for h, l in zip(H_DN, L_DN)]
o2 = CH._fts_analyze_candles("آزمون", build(BULL) + daily_tail(dt.date(2024, 1, 6) + dt.timedelta(weeks=14), TAIL_DN))
ck(o2["trend"]["W"]["trend"] == "up", "اصلاحِ روزانه هفتگیِ صعودی را down نمی‌کند", str(o2["trend"]["W"]))
ck(o2["trend"]["D"]["trend"] == "down", "روزانۀ نزولیِ تازه خوانده می‌شود", str(o2["trend"]["D"]))
ck(mx(o2)["setup"] == "FIB_CHOCH_STEP_ENTRY", "صعودی+نزولی ⇒ فیبو/CHoCH (عینِ چارت ص ۲)", str(mx(o2)))

print(f"\nfts_trend_fixtures_v1075: {PASSED} passed / {len(FAILED)} failed")
sys.exit(1 if FAILED else 0)
