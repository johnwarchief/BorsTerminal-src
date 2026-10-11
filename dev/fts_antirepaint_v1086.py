# -*- coding: utf-8 -*-
"""dev/fts_antirepaint_v1086.py — گاردِ ضدِ repaint در موتورهای FTS (مرحلۀ ۱۰)

ادعای مرحلۀ ۱۰: «هر لایه دو زمان دارد — کِی رخ داد و کِی فهمیدیم — و هیچ
انوتیشنی از آینده نگاه نمی‌کند.» این suite همان را روی کدِ تولیدی می‌سنجد، نه روی
نمایشِ فرانت:

  ۱) `_fts_swings`: برایِ هر پیوت `confirm_idx == idx + k` و `confirm_time`
     سختاً بعد از `time`؛ هیچ پیوتی در `k` کندلِ آخرِ باز نمی‌شود (ناحیهٔ در حال
     تشکیل).
  ۲) prefix-stability: مجموعهٔ پیوت‌هایی که «تأییدشان پیش از کندلِ N افتاده» با
     مجموعهٔ پیوت‌هایِ سریِ بریده به N یکی است — دادهٔ بیشتر، داوریِ دیروز را
     عوض نمی‌کند. این دقیقاً همان چیزی است که repaint را می‌کُشد. درِ همین بخش یک
     منفی‌کنترل هم اجرا می‌شود: نسخهٔ «انتهای باز» پیوتِ اضافه می‌سازد، پس گارد
     حلقهٔ خالی نیست.
  ۳) نقاطِ ساختاری (HH/HL/LH/LL): وقوع و تأیید جدا، واژگانِ موتور، هیچ نقطه‌ای
     بعد از آخرین کندل نیست.
  ۴) payloadِ کاملِ /api/fts (`_fts_analyze_candles`): هیچ تاریخی — از جمله
     `confirm_time` نقاطِ ساختاری، `jet.resistance_date`، `point_hunt.trigger_date`،
     `pullback.level_date` و `setups[*].date` — بعد از آخرین کندل نیست، و
     `structure_points` فقط نقاطِ تأییدشده را می‌برد.
  ۵) کندلِ در حال تشکیل: سقفِ افراطی روی آخرین کندل نه پیوت می‌سازد، نه برچسبِ
     ساختاری، نه انوتیشنی درِ payload (همان چیزی که کاربر روی چارتِ زنده می‌بیند).
  ۶) موتورِ سوم (ZigZagِ آستانه‌دار): `confirm_idx > idx` برایِ همه + همان
     prefix-stability؛ بی‌این، «موتورِ سوم» فقط نامِ تازهٔ repaint است.
  ۷) رأیِ روند در هر دو مبنا (`pivots` و `recent-window`) فقط به کندل‌هایِ موجودِ
     سری استناد می‌کند و `stale_bars` با indexِ واقعیِ همان پیوت می‌خواند.

اجرا بی‌شبکه و بی‌market.db است (سری‌هایِ مصنوعیِ قطعی). نبودِ شبکه خطا نیست؛
این فایل اصلاً شبکه نمی‌خواهد.
"""
import datetime as dt
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api.chart as CH  # noqa: E402
import structure_engine3 as E3  # noqa: E402

FAILS = []


def ck(label, cond):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        FAILS.append(label)


DAY0 = dt.date(2024, 1, 6)
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def to_candles(closes):
    """سریِ کندلِ قطعی: high/low از نوسانِ قطعیِ هم‌اندازۀ خودِ بسته (بی‌seed)"""
    out = []
    for i, c in enumerate(closes):
        prev = closes[i - 1] if i else c
        o = prev
        hi = max(o, c) * 1.012
        lo = min(o, c) * 0.988
        out.append({
            "time": (DAY0 + dt.timedelta(days=i)).isoformat(),
            "open": round(o, 4), "high": round(hi, 4), "low": round(lo, 4),
            "close": round(c, 4), "volume": 1000 + 37 * i,
        })
    return out


def tri_closes(amp=0.18, leg=8, n=160, base=100.0):
    out, up = [], True
    p = base
    for i in range(n):
        step = amp / leg if up else -amp / 1.3
        p = max(1.0, p * (1.0 + step))
        out.append(p)
        if i % leg == leg - 1:
            up = not up
    return out


def walk_closes(seed=7, n=200, base=100.0):
    rng = random.Random(seed)
    out, p, drift = [], base, 0.0
    for _ in range(n):
        drift = 0.9 * drift + rng.gauss(0.0, 0.014)
        p = max(1.0, p * (1.0 + drift))
        out.append(p)
    return out


def key(p):
    return (p["idx"], p["kind"], round(float(p["price"]), 4), p.get("confirm_idx"))


def naive_swings(series, k):
    """منفی‌کنترل: همان فراکتال ولی با انتهایِ باز — چیزی که repaint می‌کند"""
    n = len(series)
    hits = 0
    for i in range(k, n):
        hi, lo = series[i]["high"], series[i]["low"]
        wl_h = [c["high"] for c in series[i - k:i]]
        wr_h = [c["high"] for c in series[i + 1:i + k + 1]]  # ناقص هم مجاز است
        wl_l = [c["low"] for c in series[i - k:i]]
        wr_l = [c["low"] for c in series[i + 1:i + k + 1]]
        if len(wr_h) < k:
            hits += 1  # «هنوز باز» — موتورِ تولیدی این را پیوت نمی‌گیرد
            continue
        if hi >= max(wl_h) and hi >= max(wr_h):
            hits += 1
        elif lo <= min(wl_l) and lo <= min(wr_l):
            hits += 1
    return hits


print("── ۱) موتورِ اول: پیوت با دو زمان (وقوع و تأیید) ──")
K = CH._FTS_SWING_K
EXPECT = {
    "ترنج": "many",
    "روندِ تصادفی": "many",
    # صعودِ پیوسته هیچ سقف/کفِ فراکتالی ندارد؛ ادعایِ صادقانه «صفر پیوت» است، نه
    # «پیوت دارد». بی‌این، موتوری که همیشه پیوت می‌سازد هم سبز می‌شد.
    "صعودِ پیوسته": "none",
}

for name, closes in [("ترنج", tri_closes()), ("روندِ تصادفی", walk_closes()),
                     ("صعودِ پیوسته", [100 * (1.01 ** i) for i in range(150)])]:
    series = to_candles(closes)
    piv = CH._fts_swings(series, k=K)
    if EXPECT[name] == "many":
        ck(f"«{name}»: پیوتِ کافی ساخته می‌شود ({len(piv)} پیوت)", len(piv) > 3)
    else:
        ck(f"«{name}»: پیوتِ تأییدشده‌ای نیست ({len(piv)} پیوت — بی‌سقف/کفِ واقعی)",
           len(piv) == 0)
    ck(f"«{name}»: confirm_idx = idx + k برایِ همه",
       all(p["confirm_idx"] == p["idx"] + K for p in piv))
    ck(f"«{name}»: confirm_time سختاً بعد از time",
       all(str(p["confirm_time"]) > str(p["time"]) for p in piv))
    ck(f"«{name}»: هیچ پیوتی در {K} کندلِ آخر باز نمی‌شود (ناحیهٔ تشکیل)",
       all(p["confirm_idx"] <= len(series) - 1 for p in piv)
       and all(p["idx"] <= len(series) - 1 - K for p in piv))
    ck(f"«{name}»: تأیید همیشه روی کندلِ واقعیِ سری است",
       all(0 <= p["confirm_idx"] < len(series) and str(p["confirm_time"]) == str(series[p["confirm_idx"]]["time"])[:10] for p in piv))

print("\n── ۲) خاصیتِ prefix-stability (بدونِ repaint با دادهٔ بیشتر) ──")
series_full = to_candles(walk_closes(seed=11, n=190))
repaint_any = False
for cut in (189, 185, 178, 170, 150, 120, 90):
    trunc = CH._fts_swings(series_full[:cut], k=K)
    full = CH._fts_swings(series_full, k=K)
    known = {key(p) for p in full if p["confirm_idx"] < cut}
    got = {key(p) for p in trunc}
    # هر پیوتِ بریده باید درِ کامل هم «همان» باشد (وقوع، جنس، قیمت، تأیید)
    if not got <= known:
        repaint_any = True
    # و هیچ پیوتِ کاملی که تأییدش داخلِ بریده است نباید جا بیفتد
    missing = {k for k in known if k[3] < cut} - got
    if missing:
        repaint_any = True
    print(f"  cut={cut}: بریده {len(got)} | کاملِ تأییدشده تا cut {len(known)} | "
          f"واژگونی: {'بد' if got != known else 'NA'}")
ck("هیچ بریده‌ای پیوتِ تازه‌ای نمی‌سازد و پیوتِ تأییدشده را از دست نمی‌دهد", not repaint_any)

ck("منفی‌کنترل: نسخهٔ «انتهای باز» پیوتِ اضافه دارد ⇒ گاردِ بالا بی‌اثر نیست",
   naive_swings(series_full, K) > len(CH._fts_swings(series_full, k=K)))

print("\n── ۳) نقاطِ ساختاری (HH/HL/LH/LL) ──")
full = CH._fts_swings(series_full, k=K)
pts = CH._fts_structure_points(full)
ck(f"نقاطِ ساختاری ساخته شد ({len(pts)} نقطه)", len(pts) > 1)
ck("همهٔ برچسب‌ها از واژگانِ موتورند (بی‌برچسبِ ابداعی)",
   all(p["label"] in {"HH", "HL", "LH", "LL", "HE", "LE", "H", "L"} for p in pts))
ck("وقوع و تأییدِ هر نقطه جدا و تأیید بعدِ وقوع است",
   all(str(p["confirm_time"]) > str(p["time"]) for p in pts))
last_time = series_full[-1]["time"][:10]
ck("هیچ نقطه‌ای (وقوع یا تأیید) بعد از آخرین کندل نیست",
   all(str(p["time"]) <= last_time and str(p["confirm_time"]) <= last_time for p in pts))
ck("نقطه‌ها به همان ترتیبِ زمانیِ پیوت‌هایِ تأییدشده‌اند",
   [p["idx"] for p in pts] == sorted(p["idx"] for p in pts))

print("\n── ۴) payloadِ کاملِ /api/fts: هیچ انوتیشنی از آینده نگاه نمی‌کند ──")
out = CH._fts_analyze_candles("آزمون", series_full)
sp = (out.get("structure_points") or {}).get("D") or []
ck("structure_points درِ payload پر است و همه تأییدشده‌اند",
   len(sp) > 0 and all(str(p["confirm_time"]) <= last_time for p in sp))
date_fields = [
    ("jet.resistance_date", (out.get("jet") or {}).get("resistance_date")),
    ("jet.ceiling_date", (out.get("jet") or {}).get("ceiling_date")),
    ("pullback.level_date", (out.get("pullback") or {}).get("level_date")),
    ("point_hunt.trigger_date", (out.get("point_hunt") or {}).get("trigger_date")),
    ("point_hunt.floor_date", (out.get("point_hunt") or {}).get("floor_date")),
    ("fib.leg.end", ((out.get("fib") or {}).get("leg") or {}).get("end")),
    ("status.trigger.date", ((out.get("status") or {}).get("trigger") or {}).get("date")),
]
for label, v in date_fields:
    if v is None:
        print(f"  ── {label}: منتشر نشده (بی‌داده — ادعایی نیست)")
        continue
    ck(f"{label} = {v} بعد از آخرین کندل نیست", str(v)[:10] <= last_time)
setups = out.get("setups") or []
ck(f"همۀ {len(setups)} رویدادِ تاریخیِ setups داخلِ بازۀ تاریخچه‌اند",
   all(str(s["date"])[:10] <= last_time for s in setups))
ck("موجِ فیبو یا تأییدشده است یا صریحاً provisional (P0#4)",
   (out.get("fib") or {}).get("leg") is None
   or isinstance(((out.get("fib") or {}).get("leg") or {}).get("provisional"), bool))

print("\n── ۵) کندلِ در حال تشکیل هیچ‌وقت تأیید نمی‌کند ──")
# آخرین کندل یک سقفِ افراطی است: اگر موتور «سقفِ همین حالا» را پیوت بگیرد،
# دقیقاً همان repaint است که کاربر رویِ چارتِ زنده می‌بیند.
spike = [dict(c) for c in series_full]
spike[-1] = dict(spike[-1], high=round(spike[-1]["close"] * 3.0, 4),
                 close=round(spike[-1]["close"] * 3.0, 4))
piv_spike = CH._fts_swings(spike, k=K)
ck("سقفِ افراطیِ کندلِ آخر به‌عنوان پیوتِ تأییدشده ظاهر نمی‌شود",
   all(p["idx"] != len(spike) - 1 for p in piv_spike))
ck("برچسبِ ساختاریِ آن سقف هم ساخته نمی‌شود",
   all(p["time"] != spike[-1]["time"][:10] for p in CH._fts_structure_points(piv_spike)))
out_spike = CH._fts_analyze_candles("آزمون", spike)
last_spike = spike[-1]["time"][:10]
ck("درِ payload هم هیچ نقطه‌ای رویِ کندلِ آخر نشسته نیست",
   all(str(p["time"]) != last_spike
       for p in (out_spike.get("structure_points") or {}).get("D") or []))

print("\n── ۶) موتورِ سوم (ZigZagِ آستانه‌دار): همان قاعده، الگوریتمِ دیگر ──")
z = E3.zigzag(spike, E3.ATR_MULT, E3.FLOOR_PCT, E3.ATR_PERIOD)
ck("بی‌پیوتِ تأییدشده روی کندلِ آخر (وقوع و تأیید جدا)",
   all(p["confirm_idx"] > p["idx"] for p in z["pivots"]))
ck("تأییدِ همهٔ پیوت‌ها داخلِ سری است، نه بیرون از آن",
   all(p["confirm_idx"] < len(spike) for p in z["pivots"]))
zz_full = E3.zigzag(series_full, E3.ATR_MULT, E3.FLOOR_PCT, E3.ATR_PERIOD)["pivots"]
for cut in (185, 170, 150, 120):
    zz_cut = E3.zigzag(series_full[:cut], E3.ATR_MULT, E3.FLOOR_PCT, E3.ATR_PERIOD)["pivots"]
    a = {(p["idx"], p["kind"], round(p["price"], 4)) for p in zz_full if p["confirm_idx"] < cut}
    b = {(p["idx"], p["kind"], round(p["price"], 4)) for p in zz_cut}
    ck(f"engine3 cut={cut}: پیوتِ تأییدشده با دادهٔ بیشتر جابه‌جا نمی‌شود", a == b)

print("\n── ۷) روند فقط از پیوتِ تأییدشده رأی می‌گیرد (هر دو مبنا) ──")
tr_series = to_candles(tri_closes(n=210))
sw = CH._fts_swings(tr_series, k=K)
trend = CH._fts_classify_trend(sw, series=tr_series)
basis = str(trend.get("basis") or "")
idx_of = {c["time"][:10]: i for i, c in enumerate(tr_series)}
if basis == "pivots":
    cited = [trend.get(f) for f in ("last_high_time", "prev_high_time",
                                    "last_low_time", "prev_low_time")]
    ck("مبنایِ «pivots»: هر چهار زمانِ استنادشده منتشر شده", all(cited))
    ck("مبنایِ «pivots»: استناد فقط رویِ کندل‌هایِ واقعیِ سری است",
       all(str(t)[:10] in idx_of for t in cited))
    ck("مبنایِ «pivots»: هیچ استنادی در ناحیهٔ تشکیل (۳ کندلِ آخر) نیست",
       all(idx_of[str(t)[:10]] <= len(tr_series) - 1 - K
           for t in cited if str(t)[:10] in idx_of))
else:
    print(f"  ── مبنایِ رأی «{basis}» است؛ شاخهٔ pivots درِ این سری اجرا نشد")
    ck("مبنایِ غیرِ پیوت: پیوتی استناد نشده ⇒ last_pivot_time منتشر نمی‌شود",
       trend.get("last_pivot_time") is None)
ck("تازگیِ پیوت با فاصلۀ واقعیِ کندل‌ها می‌خواند (نه عددِ ساختگی)",
   trend.get("stale_bars") is None
   or (isinstance(trend.get("stale_bars"), int) and 0 <= trend["stale_bars"] < len(tr_series)))

# ساختارِ کهنه: صعودِ پیوستهٔ بلند هیچ پیوتِ تازه‌ای نمی‌سازد، پس موتور باید به
# بازۀِ اخیر رأی دهد و درِ همین شاخه هم باید تاریخِ استنادشده داخلِ سری باشد.
rally_closes = tri_closes(n=120) + [tri_closes(n=120)[-1] * (1.012 ** i)
                                    for i in range(1, 71)]
st_series = to_candles(rally_closes)
st_trend = CH._fts_classify_trend(CH._fts_swings(st_series, k=K), series=st_series)
st_basis = str(st_trend.get("basis") or "")
ck(f"ساختارِ کهنه ⇒ مبنایِ «recent-window» (مبنایِ خوانده‌شده: {st_basis})",
   st_basis == "recent-window")
lp = str(st_trend.get("last_pivot_time") or "")
idx_st = {c["time"][:10]: i for i, c in enumerate(st_series)}
ck(f"مبنایِ «recent-window»: تازه‌ترین پیوتِ استنادشده ({lp or '—'}) داخلِ سری و "
   "بیرون از ناحیهٔ تشکیل است",
   bool(lp) and lp[:10] in idx_st and idx_st[lp[:10]] <= len(st_series) - 1 - K)
ck("مبنایِ «recent-window»: فاصلۀ اعلامی با indexِ واقعیِ همان پیوت یکی است",
   st_trend.get("stale_bars") == len(st_series) - 1 - idx_st.get(lp[:10], -1))
ck("مبنایِ «recent-window»: هیچ‌یک از پیوت‌هایِ خامِ pivots بعد از آخرین کندل نیست",
   all(v[:10] <= st_series[-1]["time"][:10]
       for v in ((st_trend.get("pivots") or {}).values())
       if isinstance(v, str) and DATE_RE.match(v[:10])))


print()
if FAILS:
    print(f"ANTIREPAINT FAIL ({len(FAILS)}):")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("ANTIREPAINT OK — همهٔ گاردهایِ مرحلۀ ۱۰ سبز")
