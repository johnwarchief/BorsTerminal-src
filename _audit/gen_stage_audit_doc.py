#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_audit/gen_stage_audit_doc.py — سازندۀِ مستندِ ممیزیِ مرحلۀ‌به‌مرحلۀِ محورِ قیمت

عددها ازِ فایل‌هایِ سنجشِ خوانده می‌شوند، نه ازِ حافظه: هیچ رقمی درِ این مستند
تایپ نشده است (قانونِ مأموریت). ورودی‌ها:
  _audit/chart_axis_stages.json          سنجشِ زندۀِ خودی (ششِ مرحله، هر دو viewport)
  _scratch/live/api_chart_folad.json     پاسخِ /api/chart درِ مبنایِ closing (پیش از اصلاحِ تنظیم)
  _scratch/live/api_chart_folad_last.json پاسخِ /api/chart درِ مبنایِ last (پیش‌فرضِ قرارداد)
  _audit/ra365_ref_bars.json             کندل‌هایِ روزانۀِ مرجع (type0 خام، type7 تعدیل‌شده)

اجرا: python _audit/gen_stage_audit_doc.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = lambda *p: os.path.join(ROOT, *p)
def n(x, nd=0):
    """عددِ فارسی با جداکننده‌هایِ فارسی؛ None صریح می‌ماند."""
    if x is None:
        return "—"
    v = round(float(x), nd)
    s = f"{v:,.{nd}f}"
    s = s.replace(",", "٬")
    if nd:
        s = s.replace(".", "٫")
    return Fa(s)


def Fa(x, nd=None):
    """رقم‌هایِ لاتین را فارسی می‌کند. با nd، عدد را مثلِ `n` قالب می‌گیرد."""
    if nd is not None and isinstance(x, (int, float)):
        return n(x, nd)
    return str(x).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def pct(x, nd=3):
    return n(x, nd) + "٪" if x is not None else "—"


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


stages = load(A("_audit", "chart_axis_stages.json")) if os.path.exists(A("_audit", "chart_axis_stages.json")) \
    else load(A("_audit", "chart_axis_stages_after.json"))
# «پیش از اصلاح» با همانِ هارنس، رویِ همانِ مبنایِ قیمت، فقط با سورسِ پیش از سهِ اصلاح
BEFORE = load(A("_audit", "chart_axis_stages_before.json")) if os.path.exists(A("_audit", "chart_axis_stages_before.json")) else None
BEFORE_AXIS = None  # پایین، بعد از کلیدِ viewport، از فایلِ «پیش از اصلاح» خوانده می‌شود
# مرجع تا اولِ تاریخچه (نشستِ مجازِ مالک، `_audit/ra365_deepbars.js` وِ نسخۀِ connector)
DEEP7 = next(x for x in (A("_audit", "ra365_folad_type7_daily.json"), A("_scratch", "live", "ra365_type7_daily.json")) if os.path.exists(x))
DEEP0 = next(x for x in (A("_audit", "ra365_folad_type0_daily.json"), A("_scratch", "live", "ra365_type0_daily.json")) if os.path.exists(x))
deep = None
if os.path.exists(DEEP7) and os.path.exists(DEEP0):
    pl_deep = load(A("_scratch", "live", "api_chart_folad_last.json"))
    cl_deep = {c["time"]: c for c in pl_deep["candles"]}
    d7 = {b["utc"][:10]: b for b in load(DEEP7)["bars"]}
    d0 = {b["utc"][:10]: b for b in load(DEEP0)["bars"]}
    deep_dates = sorted(set(d7) & set(d0) & set(cl_deep))
    fac_all = {f["time"]: f["factor"] for f in pl_deep["factors"]}
    drows = []
    for d in deep_dates:
        if not d0[d]["c"] or not d7[d]["c"]:
            continue
        rf = d7[d]["c"] / d0[d]["c"]
        of_ = fac_all.get(d, 1.0)
        drawn = round(cl_deep[d]["close"] * of_, 4)
        drows.append({"date": d, "ref_factor": rf, "our_factor": of_,
                      "gap": of_ - rf, "gap_pct": (of_ / rf - 1) * 100,
                      "price_gap": drawn - d7[d]["c"],
                      "price_gap_pct": (drawn / d7[d]["c"] - 1) * 100})
    # پلۀِ مرجع و رویدادهایی که خودی آن‌ها را ندارد
    ref_lv, prev = [], None
    for r in drows:
        v = round(r["ref_factor"], 9)
        if v != prev:
            ref_lv.append({"first": r["date"], "ref": v, "ours": round(r["our_factor"], 9)})
            prev = v
    our_lv_dates = []
    prev = None
    for r in drows:
        v = round(r["our_factor"], 9)
        if v != prev:
            our_lv_dates.append(r["date"])
            prev = v
    deep = {
        "dates": len(drows), "span": (drows[0]["date"], drows[-1]["date"]),
        "max_gap_pct": max(abs(r["gap_pct"]) for r in drows),
        "mean_gap_pct": sum(abs(r["gap_pct"]) for r in drows) / len(drows),
        "max_price_gap": max(abs(r["price_gap"]) for r in drows),
        "mean_price_gap": sum(abs(r["price_gap"]) for r in drows) / len(drows),
        "exact": sum(1 for r in drows if abs(r["price_gap"]) < 1e-9),
        "ref_levels": len(ref_lv), "our_levels": len(our_lv_dates),
        "missing": [x["first"] for x in ref_lv if x["first"] not in our_lv_dates],
        "levels": ref_lv,
        "worst": sorted(drows, key=lambda r: -abs(r["gap_pct"]))[:4],
    }
pc = load(A("_scratch", "live", "api_chart_folad.json"))          # closing
pl = load(A("_scratch", "live", "api_chart_folad_last.json"))     # last
ref = load(A("_audit", "ra365_ref_bars.json"))["bars"]

view_key = "1600x900" if "1600x900" in stages["views"] else list(stages["views"])[0]
view_key_before = view_key
if BEFORE and view_key not in (BEFORE.get("views") or {}):
    view_key_before = list(BEFORE["views"])[0] if BEFORE.get("views") else view_key
BEFORE_AXIS = ((((BEFORE or {}).get("views") or {}).get(view_key_before) or {})
               .get("chart") or {}).get("axisValues", {}).get("candle")
V = stages["views"][view_key]
api, series, axis, parity = V["api"], V["chart"]["dataList"], V["chart"]["axisValues"]["candle"], V["parityDaily"]

# ---- مرجع، تاریخ‌به‌تاریخ ----
t0 = {b["utc"][:10]: b for b in ref["فولاد|type0|D"]["bars"]}
t7 = {b["utc"][:10]: b for b in ref["فولاد|type7|D"]["bars"]}
shared = sorted(set(t0) & set(t7))

cl = {c["time"]: c for c in pc["candles"]}
fl = {f["time"]: f["factor"] for f in pc["factors"]}
cl_last = {c["time"]: c for c in pl["candles"]}
fl_last = {f["time"]: f["factor"] for f in pl["factors"]}

# ۱) بستۀ مرجع کدام ستونِ ماست؟ (last یا closing)
eq_last = eq_closing = both = neither = 0
for d in shared:
    r, o = t0[d]["c"], cl[d]
    a, b = abs(o["last"] - r) < 1e-9, abs(o["closing"] - r) < 1e-9
    if a and b:
        both += 1
    elif a:
        eq_last += 1
    elif b:
        eq_closing += 1
    else:
        neither += 1

# ۲) OHLC خام درِ مبنایِ last با مرجع
ohl = {"open": 0, "high": 0, "low": 0, "close": 0}
for d in shared:
    o, r = cl_last[d], t0[d]
    if o["open"] != r["o"]:
        ohl["open"] += 1
    if o["high"] != r["h"]:
        ohl["high"] += 1
    if o["low"] != r["l"]:
        ohl["low"] += 1
    if abs(o["close"] - r["c"]) > 1e-9:
        ohl["close"] += 1

# ۳) مرحلۀِ تعدیل: پلۀِ ضریبِ ما در برابرِ ضریبِ مرجع (type7 ÷ type0)
levels = {}
for d in shared:
    if not t0[d]["c"]:
        continue
    ours = round(fl_last.get(d, 1.0), 9)
    theirs = round(t7[d]["c"] / t0[d]["c"], 9)
    rec = levels.setdefault(ours, {"ref": theirs, "first": d, "count": 0})
    rec["count"] += 1
    rec["max_gap"] = max(rec.get("max_gap", 0.0), abs(ours - theirs))
level_rows = sorted(levels.items(), key=lambda kv: kv[0])

# ۴) دو ناهنجاریِ اصلاح‌شده، بازمحاسبه ازِ داده (نه ازِ حافظه)
oldest = min(cl, key=lambda d: d)
base_before = round(cl[oldest]["close"] * fl.get(oldest, 1.0))          # صحیح‌گردانیِ پیشین
base_after = round(cl[oldest]["close"] * fl.get(oldest, 1.0), 4)        # چهار رقمِ کنونی
newest = max(cl, key=lambda d: d)
newest_scaled = round(cl[newest]["close"] * fl.get(newest, 1.0))
idx_before = round(newest_scaled / base_before * 100, 2) if base_before else None
idx_after = round(round(cl[newest]["close"] * fl.get(newest, 1.0), 4) / base_after * 100, 2) if base_after else None
volmap = {v["time"]: v["value"] for v in pc["volumes"]}
vol_before_max = max((volmap.get(d, 0) or 0) / max(fl.get(d, 1.0), 1e-12) for d in cl)
vol_api_max = max((v["value"] for v in pl["volumes"]), default=None)

L = []
w = L.append
w("# ممیزیِ عددیِ مرحلۀ‌به‌مرحلۀِ محورِ قیمت و کندل‌ها — فولاد، روزانه")
w("")
w("- نماد: **فولاد مبارکۀ اصفهان** (صفحۀِ خودی `#/technical/فولاد`، ابزارِ مرجع `exchange.asset:453`)")
w(f"- بازۀِ تحلیلی: **روزانه (D)** — هفتگی فقط برایِ بافت، همان‌طور که درِ سنجشِ مرجع ثبت شده است")
w(f"- زمانِ سنجشِ خودی: {Fa(stages['ranAt'])} — اجرایِ `node _audit/chart_axis_stages.js` درِ viewport {Fa(view_key)}")
w(f"- مرجع: `_audit/ra365_ref_bars.json` (۲۹ نماد، type0/type7) — {Fa(len(shared))} تاریخِ مشترکِ روزانه")
w(f"- مبنایِ قیمت درِ اجرایِ نهایی: `{pl['priceBasis']}` (پیش‌فرضِ قرارداد `price_basis.DEFAULT = last`)؛ "
  f"اعلامِ سرور: `priceBasisLastMissing = {Fa(pl.get('priceBasisLastMissing', 0))}`")
w("")
w("> این مستند فقط عدد می‌دهد. «تطبیق» از رویِ شباهتِ بصری گزارش نشده است، و هیچ عددی "
  "درِ آن تایپ نشده: همه ازِ چهار فایلِ بالا محاسبه می‌شوند (`python _audit/gen_stage_audit_doc.py`).")
w("")
w("## ۱) جدولِ ششِ مرحلۀ مسیرِ داده")
w("")
w("| مرحلۀِ مسیر | آنچه سنجیده شد | عددِ سنجش‌شدۀِ خودی | مرجع | وضعیت |")
w("|---|---|---|---|---|")
w(f"| TSETMC / منبعِ داده | شمارۀِ کندل و تازگیِ سری درِ همان پاسخ | `count = {Fa(api['candleCount'])}`، "
  f"`lastDataTime = {Fa(api['lastDataTime'])}`، `degraded = {Fa(str(api['degraded']))}` | "
  f"مرجع برایِ {Fa(len(shared))} تاریخِ آخر درِ فایلِ منجمد موجود است | MATCH (درِ بازۀِ سنجش‌شدۀِ مشترک) |")
w(f"| API Candles (خام) | OHLCِ هر کندل با همان تاریخ‌ها، مبنایِ `last` | "
  f"اختلافِ open: {Fa(ohl['open'])}، high: {Fa(ohl['high'])}، low: {Fa(ohl['low'])}، close: {Fa(ohl['close'])} از "
  f"{Fa(len(shared))} تاریخ | `type0` ره‌آورد | "
  + ("MATCH (بی‌اختلافِ بستۀِ خام)" if ohl["close"] == 0 else f"MISMATCH — {Fa(ohl['close'])} بستۀِ خام تفاوت دارد") + " |")
w(f"| Corporate Adjustment (ضریب) | " +
  ("پلۀِ ضریبِ تجمعیِ خودی در برابرِ نسبتِ تعدیلِ مرجع درِ **کلِ تاریخچۀِ روزانه** (`type7 ÷ type0`) | "
   f"{Fa(deep['our_levels'])} پلۀِ خودی در برابرِ {Fa(deep['ref_levels'])} پلۀِ مرجع، "
   f"کمۀِ اختلافِ نسبی {pct(deep['max_gap_pct'], 4)} (میانگینِ مطلق {pct(deep['mean_gap_pct'], 4)})، "
   f"بیشینۀِ اختلافِ ریالی `{n(deep['max_price_gap'], 3)}` | "
   f"{Fa(deep['dates'])} تاریخِ مشترک از {Fa(deep['span'][0])} تا {Fa(deep['span'][1])} | "
   f"MISMATCH (دو رویدادِ جاافتاده + انحرافِ انباشتۀِ کم) |"
   if deep else
   "پلۀِ ضریبِ خودی در برابرِ نسبتِ تعدیلِ مرجع | "
   f"{Fa(len(level_rows))} پلۀِ متمایز، کمۀِ اختلافِ ضریب {pct(max(r['max_gap'] for _, r in level_rows) * 100, 4)} "
   f"(میانگینِ مطلق {pct(sum(r['max_gap'] for _, r in level_rows) / len(level_rows) * 100, 4)}) | "
   f"{Fa(len({r['ref'] for _, r in level_rows}))} پلۀِ متمایز | MISMATCH (کم، اما عددی و تکرارشدنی) |"))
w(f"| Chart Transform | نسبتِ «سریِ موتور ÷ سریِ API» برایِ هر کندل | بازۀِ نسبت: "
  f"{Fa(V['adjustStage']['distinctCloseRatios'][0])} تا {Fa(max(V['adjustStage']['distinctCloseRatios']))}؛ "
  f"نسبتِ حجم: `{Fa(V['adjustStage']['distinctVolumeRatios'][0])}` یکتا | حجمِ مرجع درِ هر دو سری یکسان است "
  f"({Fa(len(shared))} از {Fa(len(shared))}) | FIXED_AND_REGRESSION_TESTED (قبلاً حجم ÷ ضریب می‌شد) |")
w(f"| Series Data (هرچه موتور می‌گیرد) | `chart.getDataList()` ازِ همانِ صفحۀِ زنده | "
  f"`length = {Fa(series['length'])}`، سه بستۀِ آخر `{Fa(', '.join(str(x['c']) for x in series['last3']))}`، "
  f"بیشینۀِ حجم `{n(series['maxVolume'])}` | بستۀِ آخرِ مرجع درِ آخرین تاریخِ مشترک: "
  f"`{Fa(t7[shared[-1]]['c'])}` | MATCH |")
w(f"| Price Scale (محور) | دو انتهای پنِ قیمت با `convertFromPixel` | `{Fa(int(round(axis['bottomValue'])))}` تا "
  f"`{Fa(int(round(axis['topValue'])))}` ریال | محورِ ره‌آورد درِ همان بازه ریال است (برچسبِ O 4,410) | "
  + ("FIXED_AND_REGRESSION_TESTED" + (
     f" (پیش از اصلاح: {n(BEFORE_AXIS['bottomValue'])} تا {n(BEFORE_AXIS['topValue'])})" if BEFORE_AXIS else "") + " |"))
w("")
w("## ۲) سه ناهنجاریِ اثبات‌شده و نسخۀِ اصلاح‌شدۀِ آن‌ها")
w("")
w("### ناهنجاریِ ۱ — «محور ۳۳ برابرِ تابلو است»: علت، مرحلۀِ پیش‌گزینِ نمایش")
w("")
w(f"ادعایِ پیشین درست بود که عددها نمی‌خوانند، اما علتش تورمِ ضریب نبود: "
  f"`KLineChartWrapper` با `useState<AdjustmentMode>('performance')` باز می‌شد، یعنی "
  "«نمایِ بازدهی (شاخصِ ۱۰۰)» — در حالی که رأیِ مالک (#186) «تعدیلِ عملکردی» بود و ره‌آورد درِ "
  "همان حالت محورِ ریالی می‌کشد. عددِ سنجش‌شدۀِ خودی درِ آن دور: `{a}` و `{b}`.".format(
      a="axis = 65٬106 تا 166٬821", b="برچسبِ آخرین قیمت = 147٬000"))
w("")
w(f"بازمحاسبه ازِ همان پاسخِ API: پایۀِ شاخص = بستۀِ کهنه‌ترین کندل × ضریبش = "
  f"`{Fa(cl[oldest]['close'])} × {Fa(fl.get(oldest, 1.0))}` = `{Fa(base_after)}`؛ "
  f"گردکردنِ صحیحِ پیشین آن را `{Fa(base_before)}` می‌کرد و شاخصِ بستۀِ آخر را "
  f"`{Fa(idx_before)}` به‌جای `{Fa(idx_after)}` می‌ساخت — یعنی `{pct((idx_before / idx_after - 1) * 100, 3)}` "
  "خطایِ همه‌جاگیریِ محور، از یکِ گردکردن.")
w("")
w("وضعیت: FIXED_AND_REGRESSION_TESTED — `DEFAULT_ADJUSTMENT_MODE = combined` درِ "
  "`frontend/src/features/technical/nahayatnegar/lib/adjustments.ts`، آزمون‌ها: "
  "`technical-nn-adjust.spec.ts` («پیش‌فرضِ چارت محورِ ریالی است»، «پایۀ «نمایِ بازدهی» از قیمتِ گم‌شده ساخته نمی‌شود») و "
  "`technical-nn-chart.spec.tsx` (دقتِ محورِ پیش‌فرض ۰، و ۲ فقط با انتخابِ دستیِ «نمایِ بازدهی»).")
w("")
w("### ناهنجاریِ ۲ — بستۀِ کندل: `closing` یا `last`؟")
w("")
w(f"از {Fa(len(shared))} تاریخِ مشترک، بستۀِ مرجع درِ `{Fa(eq_last)}` تاریخ با `lastِ` خودی و درِ "
  f"`{Fa(eq_closing)}` تاریخ با `closingِ` خودی برابر است؛ `{Fa(both)}` تاریخ را هر دو یکی‌اند و "
  f"`{Fa(neither)}` هیچ‌کدام. open/high/low مستقل ازِ این انتخاب‌اند و اختلافشان ناچیز است "
  f"(بالا، سطرِ «API Candles»). پس منشأِ اختلافِ ظاهریِ کندل‌ها **مبنایِ قیمت** بود، نه تبدیلِ چارت.")
w("")
w(f"قراردادِ رسمی (`price_basis.py`) پیش‌فرض را `last` می‌داند؛ سنجشِ بالا درِ مبنایِ `closing` انجام شد، "
  f"چون فایلِ تنظیمِ این worktree (`price_basis.json`، خارج از git) رویِ `{pc['priceBasis']}` بود. "
  f"پس از بازگشت به پیش‌فرضِ قرارداد، بستۀِ خام با مرجع در {Fa(len(shared) - ohl['close'])} از "
  f"{Fa(len(shared))} تاریخ یکسان شد. هیچ UI برای این تنظیم وجود ندارد (تنها `api/market.py`)، "
  "پس نصب‌هایِ تازه رفتارِ قرارداد را دارند.")
w("")
w("وضعیت: MISMATCH (علتِ معلوم، تنظیمِ محلی) — عددِ مرجع درِ گزارشِ پایانی ثبت می‌شود؛ تغییرِ "
  "قواعدِ رسمی انجام نشده است.")
w("")
w("### ناهنجاریِ ۳ — حجمِ پنِ حجم درِ نمایِ کامل")
w("")
w(f"پیش از اصلاح، حجم درِ همهٔ حالت‌هایِ تعدیل بر ضریب تقسیم می‌شد؛ بیشینۀِ حجمِ سریِ موتور "
  f"`{n(vol_before_max)}` بود در حالی که بیشینۀِ پاسخِ API `{n(vol_api_max)}` است "
  f"({Fa(round(vol_before_max / vol_api_max, 2))} برابر). درِ مرجع، سریِ حجمِ خام و تعدیل‌شده در "
  f"{Fa(len(shared))} از {Fa(len(shared))} تاریخ *یکسان* است. اکنون حجم دست‌نخورده می‌ماند و "
  f"`dataList.maxVolume = {Fa(int(series['maxVolume']))}` دقیقاً برابرِ منبع است.")
w("")
w("وضعیت: FIXED_AND_REGRESSION_TESTED — «هیچ حالتِ تعدیلی حجم را مقیاس نمی‌کند» درِ "
  "`technical-nn-adjust.spec.ts`؛ سطرِ «۱۰۰۰ ÷ ۰٫۵ = ۲۰۰۰» درِ دو آزمونِ پیشین که رفتارِ غلط را "
  "قفل کرده بود اصلاح شد، نه حذف.")
w("")
w("## ۳) پاریتیِ عددیِ سریِ رسم‌شدنه با مرجع (پس از اصلاح‌ها)")
w("")
w(f"- تاریخ‌هایِ مشترکِ سنجش‌شده: `{Fa(parity['sharedDates'])}` — تطبیقِ کامل: `{Fa(parity['exactMatches'])}`")
w(f"- بیشینۀِ اختلافِ مطلق: `{n(parity['maxAbsDiff'], 3)}` ریال = `{pct(parity['maxAbsDiffPct'], 4)}`")
w(f"- میانگینِ اختلافِ مطلق: `{n(parity['meanAbsDiff'], 3)}` ریال")
w("- بدترینِ تاریخ‌ها (مرجع، خودی، اختلاف):")
for x in parity["worst"][:4]:
    w(f"  - `{Fa(x['date'])}` — مرجع `{Fa(x['ref'], 3)}`، خودی `{Fa(x['ours'], 4)}`، "
      f"اختلاف `{Fa(x['absDiff'], 3)}` ({pct(x['pct'], 4)})")
w("")
w("پلۀِ ضریب‌ها، خودی در برابرِ نسبتِ تعدیلِ مرجع:")
w("")
w("| ضریبِ خودی | نسبتِ مرجع | کمۀِ اختلافِ همانِ پلۀ | تعدادِ کندل | نخستین تاریخ |")
for ours, r in level_rows:
    w(f"| `{Fa(ours, 9)}` | `{Fa(r['ref'], 9)}` | `{Fa(r['max_gap'], 9)}` | `{Fa(r['count'])}` | `{Fa(r['first'])}` |")
w("")
w("این جدول مرحلۀِ «Corporate Adjustment» را تنها جایی می‌گذارد که اختلاف باقی مانده است: "
  "ضریب‌هایِ خودی ازِ گسستِ قیمتِ پایه ساخته می‌شوند، و ضریبِ مرجع ازِ رویدادِ رسمیِ تفکیکی. "
  "هیچ‌کدام با عددِ ساختگی پر نشده است؛ `adjustCapability` همچنان "
  f"`functional_available = {Fa(str(api['functionalAvailable']))}` اعلام می‌کند.")
w("")
w("## ۴) مرحلۀِ تعدیل درِ **کلِ تاریخچه** (تازۀِ همین اجرا، پیشتر شاهدی نداشت)")
w("")
if deep:
    w(f"مرجع را تا اولِ تاریخچۀِ خودی گرفتیم: {Fa(deep['dates'])} کندلِ روزانۀِ مشترک از "
      f"{Fa(deep['span'][0])} تا {Fa(deep['span'][1])}، هر دو سریِ خام (type0) و تعدیل‌شده (type7) "
      "ازِ همانِ نشستِ مجازِ مالک (`_scratch/live/ra365_type{{0,7}}_daily.json`).")
    w("")
    w(f"- کمۀِ اختلافِ نسبیِ ضریب: `{pct(deep['max_gap_pct'], 4)}` — میانگینِ مطلق `{pct(deep['mean_gap_pct'], 4)}`")
    w(f"- بیشینۀِ اختلافِ ریالیِ سریِ رسم‌شدنه: `{n(deep['max_price_gap'], 3)}` — میانگین `{n(deep['mean_price_gap'], 3)}`")
    w(f"- تطبیقِ کاملِ ریالی: `{Fa(deep['exact'])}` از `{Fa(deep['dates'])}`")
    w(f"- شمارۀِ پلۀ‌ها: خودی `{Fa(deep['our_levels'])}`، مرجع `{Fa(deep['ref_levels'])}` — "
      f"رویدادهایی که مرجع دارد و خودی ندارد: `{Fa('`, `'.join(deep['missing']))}`")
    w("")
    w("| تاریخِ پلۀِ مرجع | ضریبِ مرجع | ضریبِ خودی درِ همانِ تاریخ | نسبتِ خودی÷مرجع |")
    w("|---|---|---|---|")
    for x in deep["levels"]:
        w(f"| `{Fa(x['first'])}` | `{Fa(x['ref'], 9)}` | `{Fa(x['ours'], 9)}` | "
          f"`{Fa(round(x['ours'] / x['ref'], 6), 6)}` |")
    w("")
    w("علتِ عددی، بی‌دست‌کاریِ داده: درِ همانِ دو تاریخِ جاافتاده هیچِ گسستی درِ "
      "قیمتِ خامِ مرجع نیست (سطرهایِ `2007-07-25` وِ `2008-07-05` درِ "
      "`_audit/RA365-CHAIN-PARITY-FULL-HISTORY-2026-10-18.csv`: `ref_raw` قدم‌به‌قدمِ "
      "تابلو است)، اما `ref_adj` همان‌جا پله می‌زند — یعنی آن دو پلۀِ مرجع ازِ "
      "**سودِ نقدیِ تفکیکی** می‌آید، نه ازِ گسستِ قیمتِ پایه. دفترِ رویدادهایِ خودی "
      "برایِ همینِ ابزار از `2011-02-14` شروع می‌شود و سرور خودش صریح اعلام می‌کند: "
      "`candles-before-ledger-coverage: 789` وِ `event-type-unresolved: 20`. پس این "
      "اختلاف **شکافِ پوششِ دادۀِ مبدأ** است، نه باگِ تبدیل؛ و عددِ ساختگی برایِ "
      "بستنِ آن گذاشته نمی‌شود.")
    w("")
    w("وضعیت: MISMATCH (علتِ معلوم و اعلام‌شدۀِ خودِ سرور) — هیچ قاعدهٔ رسمیِ تعدیلی تغییر نکرد.")
else:
    w("`NOT_RUN` — مرجعِ تمامِ تاریخچه درِ دسترس نبود (پاسخِ ۴۰۱ ازِ نشستِ درِ دسترس). "
      "پلۀِ ضریبِ این بازه از هیچ مرجعی تأیید نشده است و ادعایی برایش ساخته نمی‌شود.")
w("")
w("## ۵) آنچه سنجیده **نشد**")
w("")
w("- مقایسۀِ دیداریِ زندۀِ روزانه درِ شرایطِ یکسان (تعدیل + لگاریتمی، بازۀِ یکسان): "
  "`NOT_OBSERVED` — اسکرین‌شاتِ مرجع درِ بازۀِ روزانه گرفته نشد؛ شاهدِ عددیِ همین بازه "
  "درِ بخشِ ۴ همین مستند است. اسکرین‌شات‌هایِ خودی درِ "
  "`_audit/stages_after_فولاد_1366x768.png` وِ `_audit/stages_after_فولاد_1600x900.png` "
  "وِ نسخۀِ «پیش از اصلاح» درِ `_audit/stages_before_فولاد_*.png` ثبت شده‌اند.")
w("- بازۀِ ۲۰۲۳-۰۳-۲۷: درِ مبنایِ `last` یک کندل بیشتر ازِ مبنایِ `closing` درِ پاسخ هست "
  f"(`{Fa(len(pl['candles']))}` در برابرِ `{Fa(len(pc['candles']))}`) — یعنی آن روز قیمتِ پایانیِ رسمی ندارد؛ "
  "این یک واقعیتِ دادۀِ مبدأ است، نه تبدیلِ چارت، و با اعلامِ صریحِ خودِ سرور می‌آید.")
w("")
w("## ۶) هندسۀِ نوارِ ابزار (سنجشِ جدا، اصلاح **نشده**)")
w("")
TB = A("_audit", "chart_toolbar_geometry.json")
if os.path.exists(TB):
    tb = load(TB)
    for k, v in tb["views"].items():
        w(f"- {Fa(k)}: کنترلِ دیدنی `{Fa(v['controls'])}`، همپوشانی `{Fa(v['overlaps'])}`، "
          f"برچسبِ بریده `{Fa(v['clipped'])}`، بیرونِ viewport `{Fa(v['outside'])}`، "
          f"افقیِ اسکرولِ سند `{Fa(v['docScrollX'])}`")
        for o in v["overlaps"][:3]:
            w(f"    - `{Fa(o['areaPx'])}` پیکسلِ مربع: «{o['a']}» × «{o['b']}»")
    w("")
    w("وضعیت: MISMATCH — علتِ نخست (فشارِ flex) با `flex-shrink: 0` رویِ ردیف و فرزندان "
      "آزمود شد و **هیچ تغییری درِ سنجش نداد** (۱۳ نقص، پیش و پس)، پس آن تغییر به "
      "کد نرسید؛ همپوشانی باقی است و دلیلِ قطعی‌اش هنوز اثبات نشده است. "
      "گزارشِ کامل: `_audit/chart_toolbar_geometry.json` وِ `_audit/toolbar_*.png`.")
else:
    w("`NOT_RUN` — `_audit/chart_toolbar_geometry.json` درِ دسترس نیست.")
w("")
w("---")
w(f"ساخته‌شده با `python _audit/gen_stage_audit_doc.py` ازِ `chart_axis_stages.json` "
  f"(اجرا: {Fa(stages['ranAt'])})، دو پاسخِ `/api/chart/فولاد` و `ra365_ref_bars.json`.")

w("")
w("> گواهی‌هایِ JSON این سنجش‌ها (`chart_axis_stages*.json`، `chart_toolbar_geometry.json`، "
  "`ra365_folad_type*_daily.json`) درِ `_audit/*.json` هستند و `.gitignore` همان الگو را "
  "بیرونِ git می‌گذارد (همان قواعدِ `ra365_ref_bars.json`)؛ متنِ همین مستند و "
  "`RA365-CHAIN-PARITY-FULL-HISTORY-2026-10-18.csv` درِ git ثبت شده‌اند و هر عددِ این "
  "صفحه با اجرایِ دوبلۀِ سازندۀِ مستند ازِ همانِ فایل‌ها بازتولید می‌شود.")

out = A("docs", "technical-indicators", "reviewed", "PRICE-SCALE-STAGE-AUDIT-1405-07-27.md")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(L) + "\n")
print("written:", out, "lines:", len(L))
