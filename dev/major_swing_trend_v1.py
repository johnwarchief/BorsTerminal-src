#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/major_swing_trend_v1.py — سقف/کفِ ماژور، داورِ حفظ‌شدۀ System 1 و ضدِّ repaint

منبعِ حکم: `docs/جزوه FTS.pdf` ص ۷ (روند = ساختارِ سقف/کف: HH+HL صعودی، LH+LL نزولی،
مساوی خنثی) و چارت ۳ صفحۀ ۲ (هفتگی دروازۀ یک‌طرفۀ وتو است). تصمیمِ مالک درِ همین
مأموریت (۱۴۰۵-۰۷-۲۸، «سابق بر این: جزوه مقدم»): day-to-day گیتِ «روزانه هم باید
صعودی باشد» اعمال **نمی‌شود**؛ هفتگی وتو می‌کند و روزانه شاخه را انتخاب می‌کند.
بنابراین این سوئیت جدولِ هفتگی×روزانه را با معنایِ جزوه می‌سنجد و بندِ ۴ دستورِ
مأموریت را به‌عنوانِ «اعمال‌نشده با ارجاع» ثبت می‌کند (بخشِ G).

هر سه طبقۀ آزمون:
  A/B  ساختار و درجه‌بندیِ ماژور (FIXTURE — کندل‌هایِ مصنوعی)
  C    سلسلهمراتبِ دروازه (FIXTURE)
  D    ضدِّ آینده‌نگری/repaint (FIXTURE)
  E    حفظِ داورِ System 1 (متنِ تابع + یکسان‌بودنِ رأی رویِ یکِ فهرستِ پیوت)
  F    سازگاریِ مسیرها (موتور ← /api/fts ← قیف)
  G    مرزهایِ اعلام‌شده (آستانه یکِ انتخابِ implementation است، نه قاعدۀ جزوه)

اجرا: PYTHONIOENCODING=utf-8 python dev/major_swing_trend_v1.py
"""
import datetime as dt
import importlib.util
import inspect
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

CHECKS = []


def ck(cond, msg, detail=""):
    CHECKS.append((bool(cond), msg + ("" if cond else "  ← " + str(detail))))
    return bool(cond)


import api.chart as CH          # noqa: E402
import major_swings as MS       # noqa: E402

BASE_SHA = "a853cc75"
BASE_FILE = os.path.join(ROOT, "_scratch", "base_api_chart_%s.py" % BASE_SHA)


def load_baseline():
    """نسخۀِ کامیتِ پایه (قبل ازِ این مأموریت) — برایِ اثباتِ «داور عوض نشد» و
    «قبلاً همین fixture رأیِ غلط می‌داد». بی‌این فایل، هر ادعایِ «قبل» توصیف است
    نه سنجش. ساختش: `_audit/major_swing_before_after.py` (§ مستندِ روش)."""
    if not os.path.exists(BASE_FILE):
        return None
    spec = importlib.util.spec_from_file_location("base_api_chart", BASE_FILE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["base_api_chart"] = mod
    spec.loader.exec_module(mod)
    return mod


# ────────────────────────── FIXTURE: مولّدِ مسیرِ قیمتیِ کنترل‌شده ─────────────
WAY_BARS = 6          # کندل‌هایِ هر پا — بیشتر ازِ ۲k تا پیوتِ دوهمسایه زنده بماند
BAR_UP, BAR_DN = 1.004, 0.996    # سایۀِ کندل ⇒ ATR ≈ ۰٫۸٪ قیمت ⇒ آستانۀ ماژور ≈ ۱٫۶٪


def path_waypoints(points, bars=WAY_BARS, start_date="2024-01-06"):
    """مسیرِ خطیِ روزانۀِ رویِ waypointها (valueها قیمت‌اند) با سایۀِ کندلِ ثابت.

    ساعتِ شروعِ جمعهٔ ۲۰۲۴-۰۱-۰۶ نیست: ۲۰۲۴-۰۱-۰۶ شنبه است، پس سبدِ هفتگیِ
    شنبه‌محورِ `_fts_resample` با همین سریِ ۶ روزه دقیقاً هفته‌به‌هفته می‌بندد.
    """
    d0 = dt.date.fromisoformat(start_date)
    out = []
    prev = float(points[0])
    idx = 0
    for target in points[1:]:
        target = float(target)
        for s in range(1, bars + 1):
            px = prev + (target - prev) * (s / float(bars))
            out.append({"time": (d0 + dt.timedelta(days=idx)).isoformat(),
                        "open": prev, "high": px * BAR_UP, "low": px * BAR_DN,
                        "close": px, "volume": 1000.0})
            idx += 1
        prev = target
    return out


def series_tail_forming(series):
    """آخرینِ کندل را «تکمیل‌نشده» می‌کند (همان نشانۀِ `_watch_live_bar`)."""
    out = [dict(c) for c in series]
    out[-1]["live_forming"] = True
    return out


def nudge_last(series, delta, forming=False):
    out = [dict(c) for c in series]
    for k in ("close", "high", "low", "last", "closing"):
        if out[-1].get(k) is not None:
            out[-1][k] = float(out[-1][k]) * delta
    out[-1]["high"] = max(out[-1]["high"], out[-1]["low"])
    if forming:
        out[-1]["live_forming"] = True
    return out


def pivots(series, k=CH._FTS_SWING_K):
    return CH._fts_swings(series, k=k)


# ───────────────────────── A/B: درجه‌بندیِ ماژور و ساختار ──────────────────────
# waypointها با `path_waypoints` به مسیرِ روزانه بدل می‌شوند (۶ کندلِ ششم‌به‌ششم).
# آستانه درِ این خانواده ≈ ۱٫۶٪ قیمت، پس پاهايِ ۸..۱۵٪ ماژور و notchهایِ ~۱٪ غیرماژورند.
UP_THEN_MINOR = [100.0, 112.0, 101.0, 112.5, 111.1, 112.4, 111.0]
MINOR_DOWN = [112.0, 100.0, 111.0, 99.5, 100.9, 99.6, 101.0]
HH_HL = [95.0, 105.0, 92.0, 112.0, 99.0, 120.0, 106.0, 130.0]
LH_LL = [135.0, 118.0, 138.0, 111.0, 128.0, 104.0, 121.0, 100.0]
FLAT = [100.0, 94.0, 100.2, 94.1, 100.1, 94.2, 100.3, 94.3, 100.2]

sHH = path_waypoints(HH_HL)
sLH = path_waypoints(LH_LL)
sFL = path_waypoints(FLAT)
sMI = path_waypoints(UP_THEN_MINOR)
sMD = path_waypoints(MINOR_DOWN)

for name, s, want in (("HH/HL", sHH, "up"), ("LH/LL", sLH, "down")):
    majors, info = MS.select(pivots(s), s)
    verdict = CH._fts_classify_trend(majors, series=s)
    ck(verdict["trend"] == want, "FIXTURE ساختار %s ⇒ %s (گرفتیم %s)" % (name, want, verdict["trend"]),
       verdict)
    ck(verdict["basis"] == "pivots",
       "FIXTURE %s واقعاً با «دو Extreme ماژور» داوری شد، نه با شیبِ بازه (basis=%s)"
       % (name, verdict["basis"]), verdict)
    ck(info["enough"] is True, "FIXTURE %s دو Extreme ماژور دارد" % name, info)

fl_majors, fl_info = MS.select(pivots(sFL), sFL)
fl_v = CH._fts_classify_trend(fl_majors, series=sFL)
ck(fl_v["trend"] == "range" and fl_v["basis"] == "pivots" and fl_info["enough"],
   "FIXTURE ساختارِ هم‌سطح ⇒ range روی دو Extreme ماژورِ هم‌سطح، نه جهتِ پیش‌فرض (گرفتیم %s/%s)"
   % (fl_v["trend"], fl_v["basis"]), fl_v)

# نکتۀِ محوریِ مأموریت: پیوتِ Minor به‌تنهایی نباید روندِ ماژور را برگرداند.
mi_swings = pivots(sMI)
mi_graded = MS.grade(mi_swings, sMI)
mi_majors, mi_info = MS.summarize(mi_graded)
new_v = CH._fts_classify_trend(mi_majors, series=sMI)
old_v = CH._fts_classify_trend(mi_swings, series=sMI)
ck(mi_info["minor_highs"] + mi_info["minor_lows"] > 0,
   "FIXTURE notch کوچک، پیوتِ Minor می‌سازد (%d سقف + %d کف غیرماژور)"
   % (mi_info["minor_highs"], mi_info["minor_lows"]))
ck(all(g["major"] is False for g in mi_graded if g["kind"] == "low" and g["leg_pct"] < 0.016),
   "پیوت‌هایِ زیرِ آستانه درجه‌بندی‌شده ماژور شمرده نمی‌شوند")
ck(new_v["trend"] == "up",
   "روندِ ماژور با یکِ نوسانِ کوچک برعکس نمی‌شود (رأیِ جدید %s با مبنا %s)"
   % (new_v["trend"], new_v.get("basis")), new_v)
ck(old_v["trend"] != "up",
   "همین fixture با «دو پیوتِ آخرِ بی‌تمایز» رأیِ غلط می‌داد (نقصِ واقعی است، نه fixtureِ «درست‌سازی» شده): old=%s/%s"
   % (old_v["trend"], old_v.get("basis")), {"old": old_v["trend"], "new": new_v["trend"]})

md_swings = pivots(sMD)
md_graded = MS.grade(md_swings, sMD)
md_majors, md_info = MS.summarize(md_graded)
md_new = CH._fts_classify_trend(md_majors, series=sMD)
md_old = CH._fts_classify_trend(md_swings, series=sMD)
ck(md_new["trend"] == "down",
   "درجۀبندی سوگیرانه نیست: روندِ نزولیِ ماژور هم با Minor برعکس نمی‌شود (گرفتیم %s)"
   % md_new["trend"], md_new)
print("   [measure] down-trend fixture: old=%s new=%s minors=%d"
      % (md_old["trend"], md_new["trend"], md_info["minor_highs"] + md_info["minor_lows"]))

# بی‌دو Extreme ماژور ⇒ na + دلیل، نه جهتِ ساخته‌شدہ
tiny = path_waypoints([100.0, 100.9, 100.2, 101.0, 100.3, 101.1])
t_sw = pivots(tiny)
t_majors, t_info = MS.select(t_sw, tiny)
t_v = CH._fts_classify_trend(t_majors, series=tiny)
ck(not t_info["enough"], "نوسان‌هایِ ریز، دو Extreme ماژور نمی‌سازند")
ck(t_v["trend"] in ("na", "range"),
   "بی‌ماژورِ کافی: na یا range، هیچ‌وقت upِ پیش‌فرض (گرفتیم %s)" % t_v["trend"], t_v)
ck(t_v["trend"] != "up", "هیچ‌وقت جهتِ صعودیِ پیش‌فرض ساخته نمی‌شود", t_v["trend"])
ck(bool(t_sw), "این fixture پیوتِ تأییدشده دارد، پس کمبودِ «ماژور» سنجیده می‌شود نه کمبودِ داده", len(t_sw))
ck(bool(t_info["reason"]), "دلیلِ کمبودِ ماژور در info هست", t_info)

# کمبودِ داده ≠ روندِ نزولی: دو حالت درِ خروجی جدا خوانده می‌شوند
short = path_waypoints([100.0, 101.0])           # ۱۲ کندلِ بدونِ هیچ پیوتِ کامل
sw_short = pivots(short)
v_short = CH._fts_classify_trend(sw_short, series=short)
ck(v_short["trend"] == "na" and not sw_short,
   "سریِ بی‌پیوت ⇒ na (کمبود داده), نه down", v_short)
r_short = CH._fts_trend_reason(v_short, ctx=CH._fts_major_context("D", {
    "series": short, "graded": [], "majors": [],
    "info": MS.summarize([])[1], "verdict": v_short}, short))
ck("کمبود داده" in r_short, "متنِ دلیل، «کمبود داده» را نام می‌برد: %s" % r_short)
majors_dn, info_dn = MS.select(pivots(sLH), sLH)
v_dn = CH._fts_classify_trend(majors_dn, series=sLH)
r_dn = CH._fts_trend_reason(v_dn, ctx=CH._fts_major_context("D", {
    "series": sLH, "graded": MS.grade(pivots(sLH), sLH), "majors": majors_dn,
    "info": info_dn, "verdict": v_dn}, sLH))
ck(v_dn["trend"] == "down" and v_dn["basis"] == "pivots"
   and r_dn.startswith("مبنایِ ماژور") and "کمبود داده" not in r_dn,
   "نزولیِ قطعی (روی ماژور) متنِ «کمبود داده» ندارد: %s" % r_dn, v_dn)

# ───────────────────────── C: سلسلهمراتبِ دروازه (هفتگی، بعد روزانه) ────────────
# همان جدولِ چارت ۳: هفتگی وتو است و روزانه شاخه را انتخاب می‌کند. مولّدِ
# کندلِ هفتگی، همان الگویِ ثابت‌شدۀ `dev/weekly_veto_guard.py` است (۵ کندلِ
# دوشنبه‌تا‌جمعه حولِ بستۀِ هفته ⇒ سبدِ شنبه‌محورِ `_fts_resample` یکِ کندلِ هفتگی
# به ازای هر عضوِ فهرست می‌سازد).
def candles_from_weekly(closes, days_per_bar=5):
    out = []
    d = dt.date(2024, 1, 1)
    for wk, c in enumerate(closes):
        base = d + dt.timedelta(weeks=wk)
        for i in range(days_per_bar):
            px = c * (1.0 + 0.002 * (i - 2))
            out.append({"time": (base + dt.timedelta(days=i)).isoformat(),
                        "open": px, "high": px * 1.01, "low": px * 0.99,
                        "close": px, "volume": 1000.0})
    return out


UP_W = [11, 10, 12, 10.5, 10, 13, 11, 10.5, 14, 12, 11, 15, 13]
DOWN_W = [25 - x for x in UP_W]
FLAT_W = [11, 10, 11.2, 10.2, 10.9, 10.1, 11.1, 10.3, 11.0, 10.2, 11.15, 10.25, 11.05]

CASES = [
    # (نام، جامعۀِ هفتگی، انتظارِ روندِ هفتگی، انتظارِ decision)
    ("W-up", UP_W, "up", "PERMITTED"),
    ("W-down", DOWN_W, "down", "REJECT"),
    ("W-flat", FLAT_W, "range", "REJECT"),
    ("W-short", [10, 11, 12], "na", "UNKNOWN"),
]
gate = {}
for name, cl, want_w, want in CASES:
    s = candles_from_weekly(cl)
    o = CH._fts_analyze_candles("آزمون", s)
    tw = o["trend"]["W"]["trend"]
    td = o["trend"]["D"]["trend"]
    dec = o["trend"]["matrix"]["decision"]
    gate[name] = {"W": tw, "D": td, "decision": dec, "payload": o, "series": s}
    ck(tw == want_w, "FIXTURE %s: روندِ هفتگی %s (گرفتیم %s)" % (name, want_w, tw), o["trend"]["W"])
    ck(dec == want, "FIXTURE %s: هفتگی %s ⇒ دروازۀ %s (گرفتیم %s، روزانۀ %s)"
       % (name, tw, want, dec, td), o["trend"]["matrix"])
    if want == "REJECT":
        ck((o["trend"]["matrix"] or {}).get("setup") == "NONE",
           "FIXTURE %s: وتوی هفتگی هیچِ ستاپی پیشنهاد نمی‌کند" % name, o["trend"]["matrix"])

ck(gate["W-down"]["D"] in ("up", "down", "range", "na") and gate["W-down"]["decision"] == "REJECT",
   "حتی با روزانۀ %s، هفتگیِ نزولی عبور نمی‌دهد" % gate["W-down"]["D"])
ck(gate["W-short"]["decision"] == "UNKNOWN" and gate["W-short"]["W"] == "na"
   and gate["W-short"]["D"] == "up",
   "هفتگیِ کم‌داده ⇒ UNKNOWN با روزانۀِ صعودیِ آماده؛ نه عبورِ خودکار و نه ردِ قطعی", gate["W-short"])

mx = gate["W-up"]["payload"]["trend"]["matrix"]
ck(mx["decision"] == "PERMITTED" and mx["setup"] in
   ("JET_OR_PULLBACK_HOLD", "FIB_CHOCH_STEP_ENTRY", "DOUBLE_BOTTOM_OR_LAST_STRUCTURE"),
   "هفتگی صعودی ⇒ شاخۀِ روزانه بر اساس خودِ روزانه (گرفتیم %s/%s)" % (mx["decision"], mx["setup"]))
ck(mx["basis"]["weekly"] and mx["basis"]["daily"],
   "هر دو پا درِ خروجی دلیلِ جدا دارند", mx["basis"])

# ── جدولِ هشت‌سطریِ هفتگی×روزانه درِ خودِ قیف (funnel_engine.technical_stage) ──
# معنایِ «عبور» اینجا وضعیتِ رسمیِ قیف است. طبقِ جزوه (تصمیمِ مالک ۱۴۰۵-۰۷-۲۸):
# هفتگی دروازۀِ یک‌طرفه است و روزانه شاخه را انتخاب می‌کند؛ بندِ ۴ دستورِ مأموریت
# («روزانۀ نزولی/خنثی هم باید رد شود») اعمال **نشده** و درِ §G همین فایل ثبت است.
import funnel_engine as FE       # noqa: E402

ROWS = [
    # (هفتگی، روزانه، decisionِ موتور، انتظارِ وضعیتِ قیف)
    ("up", "up", "PERMITTED", FE.PASS),
    ("up", "down", "PERMITTED", FE.PASS),
    ("up", "range", "PERMITTED", FE.PASS),
    ("up", "na", "UNKNOWN", FE.PENDING),
    ("down", "up", "REJECT", FE.REJECT),
    ("down", "down", "REJECT", FE.REJECT),
    ("range", "up", "REJECT", FE.REJECT),
    ("na", "up", "UNKNOWN", FE.PENDING),
]
for w_, d_, mat, want in ROWS:
    r = {"symbol": "آزمون-%s-%s" % (w_, d_), "tech_trend_w": w_, "tech_trend_d": d_,
         "tech_matrix_decision": mat}
    st = FE.technical_stage([r], tech=None)["decisions"][0]
    ck(st["status"] == want,
       "دروازۀ FTS: هفتگی=%s روزانۀ=%s ⇒ %s (گرفتیم %s، کدها %s)"
       % (w_, d_, want, st["status"], [x["code"] for x in st["why"]]), st)
    if want == FE.REJECT:
        ck(st["why"][0]["code"].startswith("WEEKLY_TREND_"),
           "ردِ هفتگی دلیلِ هفتگی دارد، نه دلیلِ عمومی", st["why"])
    if want == FE.PENDING:
        ck(st["why"][0]["code"] in ("WEEKLY_UNMEASURED", "WEEKLY_UNCLASSIFIED"),
           "کمبودِ داده با «رد» یکی نمی‌شود: کدِ جدا دارد", st["why"])
ck(all(FE.technical_stage([{"symbol": "x", "tech_trend_w": w_, "tech_trend_d": d_,
                            "tech_matrix_decision": m}], tech=None)["decisions"][0]["status"]
       != FE.PASS for w_, d_, m in [("down", "up", "PERMITTED"), ("range", "up", "PERMITTED"),
                                    ("na", "up", "UNKNOWN")]),
   "هیچ ترکیبی جز هفتگیِ صعودیِ تأییدشده از دروازه عبور نمی‌کند")

# ───────────────────────── D: ضدِّ آینده‌نگری و repaint ────────────────────────
base_mod = load_baseline()

# ۱) پیوتِ تأییدنشده درِ تاریخ گذشته به‌عنوانِ پیوتِ قطعی ثبت نمی‌شود
s = path_waypoints(UP_THEN_MINOR)
sw = pivots(s)
k = CH._FTS_SWING_K
ck(all(x["confirm_idx"] == x["idx"] + k for x in sw),
   "هر پیوتِ منتشرشده k کندلِ بعدازِ خودش هم لازم دارد (confirm_idx = idx + k)")
tail_idx = max(x["idx"] for x in sw)
ck(len(s) - 1 - tail_idx >= k, "پیوتِ نزدیکِ انتها تا پنجره‌اش کامل نشده منتشر نمی‌شود",
   {"n": len(s), "last_pivot_idx": tail_idx})

# ۲) برشِ as-of-T: نتیجه‌ای که فقط با داده‌هایِ ≤ T ساخته می‌شود
T = len(s) - 8
s_T = s[:T]
v_T_new = CH._fts_analyze_candles("آزمون", [dict(c) for c in s_T])["trend"]["D"]["trend"]
s_more = [dict(c) for c in s]
v_full_new = CH._fts_analyze_candles("آزمون", s_more)["trend"]["D"]["trend"]
ck(v_T_new in ("up", "down", "range", "na"), "ارزیابیِ as-of-T یکِ رأیِ معتبر است", v_T_new)
# اگر کندل‌هایِ بعدِ T بیایند و رأیِ as-of-T عوض شود، آن رأی «قطعیِ بازنویسی‌شده» است:
# مجاز است، به‌شرطِ اینکه *تاریخِ ماژور* عوض نشود. پس شاهدِ اصلیِ ضدِّ repaint:
asof_T = str(s_T[-1]["time"])[:10]
ms_T = CH._fts_analyze_candles("آزمون", [dict(c) for c in s_T])["trend"]["major_swings"]["D"]
ms_full = CH._fts_analyze_candles("آزمون", [dict(c) for c in s_more])["trend"]["major_swings"]["D"]
before_T = [x for x in ms_full["major_swings"] if str(x["time"])[:10] <= asof_T]
prev_T = [x for x in ms_T["major_swings"] if str(x["time"])[:10] <= asof_T]
ck([x["time"] for x in before_T] == [x["time"] for x in prev_T],
   "فهرستِ ماژورهایِ as-of-T با آمدنِ کندل‌هایِ آینده برایِ تاریخ‌هایِ ≤ T عوض نمی‌شود",
   {"T": [x["time"] for x in prev_T], "with_future": [x["time"] for x in before_T]})
ck(all(str(x["confirm_time"])[:10] <= asof_T for x in ms_T["major_swings"]),
   "درِ ارزیابیِ as-of-T هیچِ ماژوری زودتر ازِ زمانِ تأییدش منتشر نشده",
   [(x["time"], x["confirm_time"], asof_T) for x in ms_T["major_swings"]])

# ۳) تکانِ آخرینِ کندلِ **تکمیل‌نشده** رأیِ قطعی را عوض نمی‌کند
s_form = series_tail_forming(s)
v0 = CH._fts_analyze_candles("آزمون", [dict(c) for c in s_form])["trend"]["D"]["trend"]
flips = []
for d in (1.02, 1.05, 0.98, 0.95):
    vv = CH._fts_analyze_candles("آزمون", nudge_last(s_form, d, forming=True))
    fl = vv["trend"]["major_swings"]["D"]
    if vv["trend"]["D"]["trend"] != v0:
        flips.append((d, vv["trend"]["D"]["trend"]))
    # and the provisional report must show the moved bar without entering the verdict
    pv = fl["provisional"]
    if pv and pv.get("high"):
        ck(pv["high"]["confirmed"] is False and pv["high"]["provisional"] is True,
           "کندلِ تکمیل‌نشده فقط زیرِ provisional و با confirmed=False می‌آید (×%s)" % d)
        ck(str(pv["high"]["time"]) == str(s[-1]["time"])[:10]
           or str(pv["low"]["time"]) == str(s[-1]["time"])[:10],
           "ردیفِ تکمیل‌نشده درِ اطلاعِ موقت دیده می‌شود، نه درِ فهرستِ قطعی (×%s)" % d,
           pv)
ck(not flips, "تکانِ ±۲..۵٪ کندلِ تکمیل‌نشده رأیِ روزانه را عوض نمی‌کند", flips)
# بدونِ نشانه (کندلِ بسته) همان تکان **مجازات می‌شود**: لایهٔ ساختار باید به
# تغییرِ دادهٔ بسته واکنش نشان دهد، وگرنه سنسورِ این آزمایش خودش خراب است.
v_plain = CH._fts_analyze_candles("آزمون", nudge_last(s, 0.80))
ck(v_plain["trend"]["D"]["trend"] != v0,
   "کنترلِ مثبت: تکانِ ۲۰٪ِ کندلِ **بسته** رأی را عوض می‌کند (پس لایهٔ ساختار زنده است)",
   {"closed": v_plain["trend"]["D"]["trend"], "forming": v0})
ck(v_plain["trend"]["major_swings"]["D"]["as_of"] == str(s[-1]["time"])[:10],
   "کندلِ بسته درِ as-of می‌گنجد، کندلِ تکمیل‌نشده نه", v_plain["trend"]["major_swings"]["D"]["as_of"])

# ۴) نسخهٔ «قبل» همین تکان را مجاز می‌دانست (اثباتِ اینکه نقصِ واقعی بوده، نه ساختگی)
if base_mod is not None:
    b0 = base_mod._fts_analyze_candles("آزمون", [dict(c) for c in s])["trend"]["D"]["trend"]
    bmove = base_mod._fts_analyze_candles("آزمون", nudge_last(s, 1.05))["trend"]["D"]["trend"]
    bmove2 = base_mod._fts_analyze_candles("آزمون", nudge_last(s, 0.95))["trend"]["D"]["trend"]
    n_flips = sum(1 for x in (bmove, bmove2) if x != b0)
    print("   [measure] baseline (a853cc75) on the same fixture: %d از ۲ تکانِ ±۵٪ رأی را عوض کرد (rأیِ پایه %s)"
          % (n_flips, b0))
    ck(n_flips >= 1,
       "نقصِ repaint درِ نسخۀِ پایه رویِ همین fixture اندازه‌گرفتنی است (نه ادعایِ بدونِ شاهد)", n_flips)
    n_flips_new = sum(1 for x in
                      (CH._fts_analyze_candles("آزمون", nudge_last(series_tail_forming(s), 1.05))["trend"]["D"]["trend"],
                       CH._fts_analyze_candles("آزمون", nudge_last(series_tail_forming(s), 0.95))["trend"]["D"]["trend"])
                      if x != v0)
    ck(n_flips_new == 0, "نسخۀِ جدید رویِ همان دو تکان صفرِ بازنویسی دارد", n_flips_new)
else:
    ck(False, "ماژولِ پایهٔ %s پیدا نشد — سنجشِ «قبل» ممکن نیست" % BASE_FILE)

# ۵) provisional هرگز جهت یا حکمِ قیف را عوض نمی‌کند: همان سری با provisionalِ بزرگ‌تر
prov_small = CH._fts_analyze_candles("آزمون", [dict(c) for c in s_form])
s_big_last = [dict(c) for c in s]
s_big_last[-1] = dict(s_big_last[-1], high=s_big_last[-1]["high"] * 1.06,
                      close=s_big_last[-1]["close"] * 1.06, live_forming=True)
prov_big = CH._fts_analyze_candles("آزمون", s_big_last)
ck(prov_big["trend"]["D"]["trend"] == prov_small["trend"]["D"]["trend"],
   "بزرگ‌شدنِ Extreme در حالِ شکل‌گیری جهتِ قطعی را عوض نمی‌کند",
   {"small": prov_small["trend"]["D"]["trend"], "big": prov_big["trend"]["D"]["trend"]})
ck(prov_big["trend"]["matrix"]["decision"] == prov_small["trend"]["matrix"]["decision"],
   "و حکمِ قیف را هم عوض نمی‌کند")
ck(prov_big["trend"]["major_swings"]["D"]["provisional"]["high"]["price"]
   > prov_small["trend"]["major_swings"]["D"]["provisional"]["high"]["price"],
   "اما اطلاعِ موقت، دقیقاً همان جابه‌جایی را گزارش می‌کند (یعنی سنسور زنده است)")

# ۶) دادهٔ نامنظم: رفتارِ صریح، بی‌شکست
zero_vol = [dict(c, volume=0.0) for c in path_waypoints(HH_HL)]
zv = CH._fts_analyze_candles("آزمون", zero_vol)["trend"]["D"]["trend"]
ck(zv in ("up", "down", "range", "na"), "کندلِ حجم‌صفر رأی را نمی‌شکند", zv)
dup = path_waypoints(HH_HL)
dup.append(dict(dup[-1]))
dv = CH._fts_analyze_candles("آزمون", dup)["trend"]["major_swings"]["D"]
ck(dv["bars"] == len({str(c["time"])[:10] for c in dup}),
   "تاریخِ تکراری یکی می‌شود (نه دو پیوت از یکِ روز)", dv["bars"])
bad = [dict(c) for c in path_waypoints(HH_HL)]
bad[3]["high"] = 0
bad[4]["close"] = float("nan")
bad.append({"time": "", "open": 1, "high": 1, "low": 1, "close": 1})
bv = CH._fts_analyze_candles("آزمون", bad)["trend"]["D"]["trend"]
ck(bv in ("up", "down", "range", "na"), "کندلِ معیوب/بی‌تاریخ حذف می‌شود، رأی می‌ماند", bv)
gap = [c for c in path_waypoints(HH_HL) if c["time"][-2:] in ("06", "07", "08", "09", "10", "11", "20", "21", "22", "23", "24", "25")]
gv = CH._fts_analyze_candles("آزمون", gap)["trend"]["D"]["trend"]
ck(gv in ("up", "down", "range", "na"), "شکافِ تاریخ رأی را نمی‌شکند", gv)

# ───────────────────────── E: حفظِ داورِ System 1 ──────────────────────────────
if base_mod is not None:
    for fname in ("_fts_classify_trend", "_fts_swings", "_fts_recent_window_trend",
                  "_fts_resample", "_fts_structure_points"):
        a = inspect.getsource(getattr(base_mod, fname))
        b = inspect.getsource(getattr(CH, fname))
        ck(a == b, "بدنِ %s بایت‌به‌بایت همان است (داورِ دوم ساخته نشده)" % fname)
    # و همان قانون، رویِ یکِ فهرستِ پیوتِ یکسان، یکِ جواب می‌دهد:
    for nm, s2 in (("HH/HL", sHH), ("LH/LL", sLH), ("minor", sMI)):
        sw2 = CH._fts_swings(s2, k=CH._FTS_SWING_K)
        x = CH._fts_classify_trend(sw2, series=s2)
        y = base_mod._fts_classify_trend(sw2, series=s2)
        ck(x["trend"] == y["trend"], "رأیِ یکِ تابع رویِ یکِ ورودی درِ دو نسخه یکی است (%s)" % nm,
           {"new": x["trend"], "base": y["trend"]})

# ───────────────────────── F: سازگاریِ مسیرها ─────────────────────────────────
sym = "آزمون"
sers = path_waypoints(HH_HL)
eng = CH._fts_analyze_candles(sym, [dict(c) for c in sers])
# مسیرِ API: همان موتور با سریِ تزریق‌شده (بدونِ شبکه)
_old_series = CH._fts_analysis_series
CH._fts_analysis_series = lambda sy: (sers, "test-fixture")
try:
    api_payload = CH._fts_analyze_symbol(sym)
finally:
    CH._fts_analysis_series = _old_series
fts = (api_payload or {}).get("fts") or {}
ck(fts.get("trend", {}).get("D", {}).get("trend") == eng["trend"]["D"]["trend"],
   "مسیرِ API همان رأیِ موتورِ تکنیکال را می‌دهد",
   {"api": fts.get("trend", {}).get("D"), "engine": eng["trend"]["D"]})
ck(fts.get("trend", {}).get("matrix", {}).get("decision")
   == eng["trend"]["matrix"]["decision"], "و همان حکمِ قیف را",
   {"api": fts.get("trend", {}).get("matrix"), "engine": eng["trend"]["matrix"]})

# مسیرِ قیف: ستون‌هایِ tech از همین payload ساخته می‌شوند (api/screener.py:610-631)
tr = fts.get("trend") or {}
row = {"symbol": "آزمون", "tech_trend_w": tr["W"]["trend"], "tech_trend_d": tr["D"]["trend"],
       "tech_matrix_decision": tr["matrix"]["decision"]}
out_stage = FE.technical_stage([row], tech=None, gate=None)
st = (out_stage.get("decisions") or [{}])[0]
ck(st.get("status") in (FE.PASS, FE.REJECT, FE.PENDING, FE.UNAVAILABLE),
   "قیف یکِ وضعیتِ رسمی می‌دهد", st)
ck((st.get("weekly"), st.get("daily"), st.get("matrix"))
   == (tr["W"]["trend"], tr["D"]["trend"], tr["matrix"]["decision"]),
   "قیف همان سه مقدارِ موتور را داوری می‌کند (بی‌منطقِ جدا)", st)
ck(tr["W"]["trend"] != "up" or st["status"] == FE.PASS,
   "عبورِ قیف فقط با هفتگی صعودی (گرفتیم %s/%s)" % (tr["W"]["trend"], st["status"]))

# ───────────────────────── G: مرزهایِ اعلام‌شدہ ───────────────────────────────
ck(MS.MAJOR_LEG_ATR_X == 2.0 and MS.MAJOR_LEG_FLOOR_PCT == 0.005,
   "آستانه‌ها درِ یکِ فایلِ تک‌منبع‌اند، نه پراکنده درِ موتور")
src = inspect.getsource(CH._fts_analyze_candles)
ck("major_swings.select" not in src and "major_swings.summarize" in src,
   "موتور فقط درجه‌بندی می‌گیرد؛ رأی را همان `_fts_classify_trend` می‌سازد")
ck(CH.FTS_TECH_RULESET_VERSION == "6",
   "نسخۀِ قواعد بالا رفته (کشِ کهنه با قواعدِ نو جواب نمی‌دهد)",
   CH.FTS_TECH_RULESET_VERSION)
ck(MS.MAJOR_LEG_ATR_X not in (0, None), "آستانه بی‌واحدِ صفر نیست (همه را ماژور نمی‌بیند)")
g = MS.grade(pivots(sMI), sMI)
ck(all("major" in x and "leg_pct" in x and "confirm_age_bars" in x for x in g),
   "هر پیوتِ درجه‌بندی‌شده قابلِ ردیابی است (ماژور؟ با چه عددی؟)")
ck(all(x["leg_atr_x"] is None or x["leg_atr_x"] > 0 for x in g), "بلندیِ پا منفی نیست")
ck(all(isinstance(x["major"], bool) or x["major"] is None for x in g),
   "درجه‌بندی سه‌حالتي است: ماژور / غیرماژور / تصمیم‌نگرفته")
und = [i for i, x in enumerate(g) if x["major"] is None]
ck(all(MS.leg_amp(g, i) is None for i in und),
   "«تصمیم‌نگرفته» فقط وقتی پایِ هم‌جنسِ پیشین وجود ندارد (بی‌عددِ حدسی)",
   {"undecided": len(und), "no_leg": sum(1 for i in und if MS.leg_amp(g, i) is None)})

failed = 0
for ok, msg in CHECKS:
    print(("  PASS " if ok else "  FAIL ") + msg)
    failed += 0 if ok else 1
print("\n%d checks, %d failed" % (len(CHECKS), failed))
print("MAJOR SWING TREND " + ("OK" if failed == 0 else "FAILED"))
sys.exit(1 if failed else 0)
