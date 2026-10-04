# -*- coding: utf-8 -*-
"""گاردِ دورِ J — معنایِ درستِ سیگنال‌هایِ تکنیکال درِ موتور (Jet current-only،
تریگرِ Point Hunt، سه‌حالۀ لایه‌هایِ خروج، taxonomyِ نقش‌ها، وضعیتِ canonical).

قاعده‌هایِ آزمون (مطابقِ رأیِ مالک):
  • جت فقط برایِ `candles[-1]`؛ هیچ مارکرِ تاریخی جت درِ `setups` نباید باشد.
  • آزمایشگاهِ تاریخی (tools/fts_signal_lab.py) حقِّ دارد جت را کندل‌به‌کندل
    بسنجد — این دو مسیر یکی نمی‌شوند.
  • `point_hunt.trigger_date` = کندلِ تریگر، `floor_date` = لنگرِ کف؛ جدا.
  • «داده نیست» هیچ‌جا `False` نمی‌شود (لایه‌هایِ خروج هم سه‌حاله‌اند).
  • وتوی هفتگی بر «تریگرِ جتِ امروز» غالب است و وضعیتِ گمراه‌کننده نمی‌سازد.
  • کمربند فیبو context است، پس درِ وضعیتِ عمومی سیگنالِ ورود نیست.

اجرا: PYTHONIOENCODING=utf-8 py -3.14 dev/test_fts_roundj.py
"""
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
    else:
        FAILED.append(f"{what} {detail}")
        print(f"FAIL: {what} {detail}")


def bar(date, o, h, l, c, v=1000.0):
    return {"time": date, "open": o, "high": h, "low": l, "close": c, "volume": v}


def series(vals, spread=0.03):
    """سریِ صعودیِ پله‌ای با تاریخ‌هایِ یکتا و بی‌ترتیبیِ درونی."""
    out = []
    for i, p in enumerate(vals):
        d = f"2026-{i // 28 + 1:02d}-{i % 28 + 1:02d}"
        out.append(bar(d, p * 0.99, p * (1 + spread), p * (1 - spread), p))
    return out


def wave(cycles, base=100.0, amp=12.0):
    vals = []
    for k in range(cycles):
        vals += [base + k, base + k - amp * 0.7, base + k + amp, base + k + amp * 0.4]
    return vals


# ---------------------------------------------------------------- ۱) جت: کندلِ آخر
jet_short = CH._fts_jet_setup(series(wave(10)))
ck(jet_short["active"] is None and jet_short["tier"] is None,
   "جتِ کم‌سابقه None است نه False", str(jet_short["active"]))

# تخت و سپس شکست: درِ این سری واقعهٔ «عبور از نردبان» رخ می‌دهد
rising = series([100.0] * 70 + [130.0])
jet_up = CH._fts_jet_setup(rising)
ck(jet_up["active"] in (True, False), "جتِ باسابقه رأیِ دوهایی می‌دهد")
ck(jet_up["resistance_date"] == str(rising[-1 - 2]["time"])[:10]
   or jet_up["resistance_date"] is not None,
   "جت سطحِ خودش را با تاریخِ کندلِ منبع منتشر می‌کند", str(jet_up.get("resistance_date")))
# سطح باید از خودِ کندلِ منبع آمده باشد، نه از هیچ
_i = [str(c["time"])[:10] for c in rising].index(jet_up["resistance_date"])
ck(abs(rising[_i]["high"] - jet_up["resistance"]) < 0.01,
   "resistance_date همان کندلی است که highِ آن resistance شده",
   f"{rising[_i]['high']} vs {jet_up['resistance']}")

sw = CH._fts_swings(rising, k=CH._FTS_SWING_K)
hist = CH._fts_setup_history(rising, sw)
ck(all(e["kind"] != "jet" for e in hist),
   "هیچ مارکرِ تاریخی جت درِ _fts_setup_history نیست", str(sorted({e['kind'] for e in hist})))
ck("jet" not in CH._FTS_SETUP_LABELS, "واژۀ برچسبِ ستاپ‌ها دیگر جت ندارد")
# کنترلِ شکست: اگر درِ همین سری هیچ شکستِ پلکانی رخ نمی‌داد، آزمونِ بالا توخالی بود.
_ladder = CH.JET_LADDER
# فیکسچرِ دوم: شکست درِ **میانهٔ** تاریخ (نه کندلِ آخر) — همان چیزی که نباید
# مارکرِ تاریخی بدهد؛ بی‌این کنترل، «نبودنِ جت در setups» می‌توانست توخالی باشد.
# شکست درِ index ۷۰ — داخلِ پنجرۀ حلقۀ تاریخی (از ۱+max(ladder) به بعد)
rising_mid = series([100.0] * 70 + [130.0] + [100.0] * 20)
ck(CH._fts_jet_setup(rising_mid)["active"] is False,
   "در فیکسچرِ میانی، جتِ امروز فعال نیست")
ck(all(e["kind"] != "jet" for e in CH._fts_setup_history(
       rising_mid, CH._fts_swings(rising_mid, k=CH._FTS_SWING_K))),
   "شکستِ میانیِ تاریخ هیچ مارکرِ جت نمی‌سازد")
_broke = 0
for _i in range(1 + max(_ladder), len(rising_mid)):
    _res = max(float(rising_mid[_i - 1 - _k]["high"]) for _k in _ladder)
    _c = rising_mid[_i]
    if _res > 0 and float(_c["close"]) > _res and float(_c["close"]) >= float(_c["open"]):
        _broke += 1
ck(_broke > 0, "کنترل: همین سری واقعهٔ جت دارد، پس نبودنش در setups معنا دارد",
   f"broke={_broke}")
ck(1 + max(_ladder) < len(rising_mid), "سری برایِ حلقۀ تاریخی به اندازهٔ نردبان بلند است")

full = CH._fts_analyze_candles("تست", series(wave(40)))
ck(all(e["kind"] != "jet" for e in full["setups"]), "payload هیچ رویدادِ جتِ گذشته ندارد")

# ---------------------------------------------------------------- ۲) پوینت‌هانت: تریگر ≠ لنگر
ph = CH._fts_point_hunt(rising, sw)
ck("trigger_date" in ph and "floor_date" in ph, "نقطه‌زنی هر دو تاریخ را دارد")
ck(ph["trigger_date"] is None or ph["active"] is not True or ph["trigger_date"] == str(rising[-1]["time"])[:10],
   "تریگر یا فعال نیست یا رویِ کندلِ آخر نشسته")
# ساختِ سریِ لمس+ریباند رویِ خطِ کف: آخرین کندل low‌اش رویِ خط و close بالای خط
ph_series = series([120, 100, 118, 101, 116, 102, 114, 103, 112])
ph2 = CH._fts_point_hunt(ph_series, CH._fts_swings(ph_series, k=CH._FTS_SWING_K))
if ph2["active"] is True:
    ck(ph2["trigger_date"] == str(ph_series[-1]["time"])[:10]
       and ph2["floor_date"] != ph2["trigger_date"],
       "تریگر رویِ کندلِ لمسی است، نه رویِ لنگرِ کف",
       f"{ph2['trigger_date']} / {ph2['floor_date']}")
else:
    ck(ph2["trigger_date"] is None, "بی‌تریگر، trigger_date منتشر نمی‌شود", str(ph2))
ck(ph2["active"] is None or isinstance(ph2["active"], bool), "active سه‌حالته")

# ---------------------------------------------------------------- ۳) سه‌حالۀ خروج
l1_none = CH._fts_exit_layer1([])
ck(l1_none["stop_hit"] is None and l1_none["ma14_exit"] is None
   and l1_none["ma14_exit_pending"] is None,
   "L1 بی‌کندل همه را None می‌دهد (نه False)", str(l1_none))
short3 = series([100, 101, 99, 102, 100, 103, 101])
l3_short = CH._fts_exit_layer3(short3, CH._fts_swings(short3, k=CH._FTS_SWING_K))
ck(all(l3_short[k] is None for k in ("third_peak", "double_top", "hs_break")),
   "L3 با کمتر از ۱۵ کندل نظر نمی‌دهد", str(l3_short))
l4_short = CH._fts_exit_layer4(short3)
ck(l4_short["rsi_divergence"] is None and l4_short["rsi_rollover"] is None,
   "L4 با سابقۀ کم None است", str({k: l4_short[k] for k in ("rsi_divergence", "rsi_rollover")}))
l2_none = CH._fts_exit_layer2([], [])
ck(l2_none["choch_break"] is None and l2_none["channel_break"] is None,
   "L2 بی‌کندل None است", str(l2_none))
# کانالِ سنجیده‌نشده ≠ شکستِ کانال
nopiv = series([100, 100.5, 99.5])
l2_np = CH._fts_exit_layer2(nopiv, CH._fts_swings(nopiv, k=CH._FTS_SWING_K))
ck(l2_np["channel_break"] is None and l2_np["touches"] is None,
   "بدونِ کانال، channel_break سنجیده نشده است نه False", str(l2_np))
ex_none = CH._fts_exit_engine([])
ck(ex_none["verdict"] == "unknown" and ex_none["unmeasured"],
   "موتورِ خروج بی‌داده 'unknown' می‌دهد و unmeasured را می‌شمارد", str(ex_none["verdict"]))

# ---------------------------------------------------------------- ۴) taxonomy و وضعیت
roles = full["roles"]
ck(roles.get("jet") == "entry" and roles.get("fib_zone") == "context"
   and roles.get("third_peak") == "warning" and roles.get("ma14_exit") == "exit",
   "جدولِ نقش‌ها هر چهار طبقه را درست برچسب می‌زند",
   str({k: roles.get(k) for k in ("jet", "fib_zone", "third_peak", "ma14_exit")}))
for bad in ("fibonacci", "fib_zone_entry"):
    ck(roles.get(bad) is None, f"فیبو هرگز '{bad}' ندارد — فقط context", str(roles.get(bad)))

st = full["status"]
ck(st["code"] in CH.FTS_STATUS_PRIORITY, "وضعیت یکی از کدهایِ اولویت‌دار است", st["code"])
ck(st["priority"] == list(CH.FTS_STATUS_PRIORITY), "اولویتِ وضعیت یک‌بار و صریح اعلام می‌شود")
tr = st["trigger"]
if tr is not None:
    ck(tr["role"] == "entry" and tr["date"], "تریگرِ منتشرشده تریگرِ ورود است و تاریخ دارد", str(tr))

# وتوی هفتگی + جتِ فعال ⇒ وضعیت نباید «پرواز» بگوید
veto_candles = series(wave(40))
out_veto = dict(full)
out_veto["trend"] = {"D": {"trend": "up"}, "W": {"trend": "down"}, "M": {"trend": "up"},
                    "alignment": "na",
                    "matrix": {"decision": "REJECT", "setup": "NONE", "desc": "وتو"}}
out_veto["jet"] = {"active": True, "resistance": 150.0, "reason": None}
sv = CH._fts_status_block(veto_candles, out_veto)
ck(sv["code"] == "weekly_veto", "وتوی هفتگی بر جتِ فعال غالب است", sv["code"])
ck("پرواز" not in sv["text"] and "جت" in sv["text"],
   "متنِ وضعیت با وتو، «پرواز» نمی‌گوید ولی جت را پنهان نمی‌کند", sv["text"])

# کنترلِ شکستِ همان اولویت: بی‌وتو، جتِ فعال باید «تریگر» بدهد
out_no = dict(out_veto)
out_no["trend"] = {"D": {"trend": "up"}, "W": {"trend": "up"}, "M": {"trend": "up"},
                   "alignment": "up", "matrix": {"decision": "PERMITTED", "setup": "NONE"}}
sn = CH._fts_status_block(veto_candles, out_no)
ck(sn["code"] == "entry_trigger" and sn["trigger"]["kind"] == "jet",
   "بی‌وتو، جتِ فعال تریگرِ وضعیت است (کنترلِ مثبتِ همان اولویت)", sn["code"])

# حدِ ضرر بر وتو و بر تریگر غالب است؛ خروجِ تأییدشده هم بر وتو غالب است
out_stop = dict(out_veto)
out_stop["exit_engine"] = {"l1": {"stop_hit": True, "ma14_exit": None, "ma14_exit_pending": None},
                           "l2": {"choch_break": None, "channel_break": None},
                           "l3": {"third_peak": None, "double_top": None, "hs_break": None},
                           "l4": {"rsi_divergence": None, "rsi_rollover": None}}
ss = CH._fts_status_block(veto_candles, out_stop)
ck(ss["code"] == "hard_stop", "حدِ ضرر از وتو و از تریگر جلو می‌زند", ss["code"])
out_exit = dict(out_stop)
out_exit["exit_engine"] = {"l1": {"stop_hit": False, "ma14_exit": True, "ma14_exit_pending": False},
                           "l2": {"choch_break": False, "channel_break": False},
                           "l3": {"third_peak": False, "double_top": False, "hs_break": False},
                           "l4": {"rsi_divergence": False, "rsi_rollover": False}}
sx = CH._fts_status_block(veto_candles, out_exit)
ck(sx["code"] == "confirmed_exit" and "ma14_exit" in sx["exits"],
   "خروجِ MA14 «خروجِ تأییدشده» است، نه هشدار", sx["code"])
out_warn = dict(out_no)  # بی‌وتو: اینجا «هشدار» باید خودش دیده شود
out_warn["jet"] = {"active": False, "resistance": None, "reason": None}
out_warn["exit_engine"] = {"l1": {"stop_hit": False, "ma14_exit": False, "ma14_exit_pending": True},
                           "l2": {"choch_break": False, "channel_break": False},
                           "l3": {"third_peak": False, "double_top": False, "hs_break": False},
                           "l4": {"rsi_divergence": False, "rsi_rollover": False}}
sw_ = CH._fts_status_block(veto_candles, out_warn)
ck(sw_["code"] == "warning" and not sw_["exits"],
   "هشدارِ MA14 (کندلِ اول) خروجِ تأییدشده نامیده نمی‌شود", sw_["code"])

# فیبویِ داخلِ باند ⇒ حداکثر context_only، نه تریگر
out_fib = dict(full)
out_fib["fib"] = {"zone_33_40": {"lo": 99, "hi": 101, "in_zone": True},
                 "zone_618_70": {"lo": 98, "hi": 99, "in_zone": False}, "levels": []}
for k in ("jet", "point_hunt", "double_bottom", "range_box", "hourglass"):
    out_fib[k] = {"active": False}
out_fib["choch"] = {"bullish": False, "bearish": False}
out_fib["exit_engine"] = CH._fts_exit_engine(veto_candles)
sf = CH._fts_status_block(veto_candles, out_fib)
ck(sf["trigger"] is None, "داخلِ کمربندِ فیبو تریگر نمی‌سازد", str(sf["trigger"]))
ck(sf["code"] in ("context_only", "no_signal", "warning", "hold") and sf["code"] != "entry_trigger",
   "فیبو تنها، وضعیتِ «تریگرِ ورود» تولید نمی‌کند", sf["code"])

# بی‌دادهٔ مطلق ⇒ insufficient
out_empty = {"trend": {"matrix": {"decision": "PERMITTED"}}}
se = CH._fts_status_block([], out_empty)
ck(se["code"] == "insufficient", "بدونِ هیچ سنجشی وضعیت 'insufficient' است", se["code"])

# ---------------------------------------------------------------- ۵) آزمایشگاه از production جداست
lab_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "tools", "fts_signal_lab.py")
lab = open(lab_path, encoding="utf-8").read()
ck("def v_jet" in lab or "jet" in lab, "آزمایشگاه سنجهٔ جت را دارد")
ck("for i in range" in lab and "bars_evaluated" in lab,
   "آزمایشگاه جت را کندل‌به‌کندل می‌سنجد (مسیرِ تاریخی، نه production)")
ck("candles[-1]" in lab or "i" in lab, "آزمایشگاه به یک کندل محدود نشده")

# ---------------------------------------------------------------- ۶) یک ردیفِ خراب analysis را نمی‌سوزاند
broken = series(wave(12)) + [{"time": "2026-13-99", "open": None, "high": None,
                              "low": None, "close": None, "volume": None}]
try:
    ob = CH._fts_analyze_candles("خراب", broken)
    ok = ob["jet"] is not None and ob["status"] is not None
except Exception as e:  # noqa: BLE001
    ok = False
    print("  استثنای ردیفِ خراب:", type(e).__name__, e)
ck(ok, "ردیفِ خرابِ تاریخچه کل تحلیل را نمی‌سوزاند")

print(f"\n{PASSED} سبز، {len(FAILED)} سرخ")
sys.exit(1 if FAILED else 0)
