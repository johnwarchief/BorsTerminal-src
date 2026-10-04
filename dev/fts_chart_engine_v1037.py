"""dev/fts_chart_engine_v1037.py — فیبوی چارت و مارکرهایش از یک موتور می‌آیند (#161)

چرا: تبِ تکنیکال دو موتورِ FTS داشت. پنل از `/api/fts` می‌خواند و چارت از
`analyzeFts` مرورگر. سنجشِ نُه نماد (۱۴۰۵-۰۷-۰۵): هیچ‌یک از دو کمربندِ فیبو با
هم نمی‌خواندند (فولاد: چارت ۲۵۲۸–۲۶۰۹ در برابر پنل ۳۳۲۴–۳۳۳۹)، چارت تا ۱۰
برچسبِ «CHoCH» رویِ یک نماد می‌زد که هیچ‌کدام در موتورِ جزوه نبود، و شرطِ
خروجِ MA14 دو تعریف داشت (یک کندلِ سایه‌دار در برابر دو کندلِ بدنه‌دار — مبين:
چارت «خروج»، پنل «احتیاط»). خودِ موتورِ سرور هم لنگرِ فیبو را غلط می‌زد:
سقفِ تک‌روزیِ *تمامِ تاریخ* و کفِ بعد از آن، پس نمادی که تازه سقفِ تاریخی زده
موجش به چند کندل خلاصه می‌شد و کمربندِ ۳۳–۴۰ پهنای ۱۵ ریال می‌شد (۰٫۴۶٪ِ
قیمت) — در نتیجه «داخل کمربند» روی هشت از هشت نماد false بود.

این گارد بی‌شبکه و بی‌market.db می‌دود و می‌سنجد:
  • موجِ فیبو از زنجیرهٔ کف‌هایِ بالاترِ *نشکسته* می‌آید، و به‌محضِ اینکه پایانی
    زیرِ یکی از آن کف‌ها بسته شود زنجیره همان‌جا می‌شکند (شاهدِ منفی)
  • سطوحِ ابزار همان هفت نسبتِ جزوه‌اند و قیمت‌هایشان نزولی
  • جت درِ تاریخچه مارکر نمی‌شود (فقط کندلِ آخر)، و هر رویدادِ دیگری از قاعدۀ پنل می‌خواند
  • جت هرگز مارکرِ تاریخی نمی‌شود؛ رویدادهای زنجیره‌ایِ دیگر یک برچسب‌اند
  • دیگر هیچ `analyzeFts` در فرانت‌اند نیست — چارت رسم می‌کند، محاسبه نه
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api.chart as CH  # noqa: E402

FAILS = []
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ck(label, cond):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        FAILS.append(label)


def series(prices, start="2025-01-01"):
    d0 = datetime.date.fromisoformat(start)
    out = []
    for i, p in enumerate(prices):
        out.append({"time": (d0 + datetime.timedelta(days=i)).isoformat(),
                    "open": p, "high": p, "low": p, "close": p, "volume": 100.0})
    return out


def wave(turns, n_per=10):
    """آروارهٔ پیوت‌دار: هر نقطهِٔ turns در indeksِ k*n_per می‌نشیند و میانِ
    آن‌ها خطی حرکت می‌کند — پنجرهٔ k=3 پیوت‌ها را درست تشخیص می‌دهد."""
    prices = []
    for p0, p1 in zip(turns, turns[1:]):
        step = (p1 - p0) / n_per
        for j in range(n_per):
            prices.append(round(p0 + step * j, 2))
    prices.append(float(turns[-1]))
    return prices


# کف‌های بالاتر (۹۰، ۱۰۰، ۱۱۲، ۱۳۰، ۱۵۰) و سقف‌های بالاتر (۱۱۰، ۱۲۵، ۱۴۵، ۱۶۵، ۱۹۰)
TURNS = [100, 90, 110, 100, 125, 112, 145, 130, 165, 150, 190]
up = series(wave(TURNS))
sw = CH._fts_swings(up, k=CH._FTS_SWING_K)
leg = CH._fts_fib_leg(up, sw)
ck("روندِ ساختاریِ آروارهٔ صعودی، موج را صعودی می‌خواند",
   (leg or {}).get("direction") == "up")
ck("موج از نخستین کفِ زنجیره آغاز می‌شود (۹۰ نه ۱۵۰)",
   bool(leg) and abs(leg["low"] - 90.0) < 0.01)
ck("سقفِ موج بالاترینِ پس از آن کف است (۱۹۰)", bool(leg) and abs(leg["high"] - 190.0) < 0.01)

violated = list(up)
violated[85] = dict(violated[85], open=105.0, high=105.0, low=105.0, close=105.0)
sw2 = CH._fts_swings(violated, k=CH._FTS_SWING_K)
leg2 = CH._fts_fib_leg(violated, sw2)
ck("شاهدِ منفی: با کفِ شکسته، موج از همان کفِ تازه آغاز می‌شود (۹۰ نه)",
   bool(leg2) and abs(leg2["low"] - 105.0) < 0.01)

# ---------- ۲) سطوح و کمربندها ----------
fz = CH._fts_fib_zones(up, sw)
ck("کمربندها ساخته می‌شوند", bool(fz) and bool(fz.get("zone_33_40")))
ratios = [lv["ratio"] for lv in (fz or {}).get("levels") or []]
ck("همان هفت نسبتِ ابزارِ فیبو در جزوه",
   ratios == [0.0, 0.33, 0.40, 0.50, 0.618, 0.70, 1.00])
prices = [lv["price"] for lv in (fz or {}).get("levels") or []]
ck("قیمتِ سطوح از سقفِ موج تا کفش نزولی است",
   all(a > b for a, b in zip(prices, prices[1:])))
ck("سرِ موج و کفِ موج خودِ دو سرِ فیلدِ لنگرند",
   bool(fz) and abs(fz["retrace_base_high"] - (leg or {}).get("high", -1)) < 0.01
   and abs(fz["retrace_base_low"] - (leg or {}).get("low", -1)) < 0.01)
ck("بازهٔ زمانِ موج با خودِ سری می‌خواند (start پیش از end)",
   bool(fz) and fz["leg"]["start"] <= fz["leg"]["end"] and fz["leg"]["start"] == up[leg["start_idx"]]["time"])
z1, z2 = fz["zone_33_40"], fz["zone_618_70"]
ck("کمربندِ کم‌عمق بالای کمربندِ طلایی می‌نشیند", z1["hi"] > z1["lo"] > z2["hi"] > z2["lo"])
width = (z1["hi"] - z1["lo"]) / z1["lo"]
ck("کمربند پهنای واقعی دارد، نه یک خطِ مو (بیش از ۲٪ قیمت)", width > 0.02)
ck("هیچ‌یک از دو کمربند بیرون از موج نیست",
   fz["retrace_base_low"] <= z2["lo"] and z1["hi"] <= fz["retrace_base_high"])

# ---------- ۳) لنگرِ تازه‌به‌سقف — همان باگِ فولاد ----------
# سقفِ تاریخی در کندلِ آخر؛ کفِ پس از آن چند ریال بیشتر نیست. تعریفِ پیشین موج
# را به همان چند ریال می‌بست و کمربند ناپدید می‌شد.
rally = series([round(100 + i * 1.5, 2) for i in range(200)])
sw3 = CH._fts_swings(rally, k=CH._FTS_SWING_K)
fz3 = CH._fts_fib_zones(rally, sw3)
z13 = (fz3 or {}).get("zone_33_40") or {}
ck("نمادی که تا سقف بالا رفته کمربندِ بی‌پهنا نمی‌گیرد",
   bool(z13) and (z13["hi"] - z13["lo"]) / z13["lo"] > 0.02)
ck("لنگرِ آن به پیشینهٔ موج برمی‌گردد نه به آخرین کندل",
   bool(fz3) and fz3["leg"]["start"] < rally[-1]["time"])

# ---------- ۴) تاریخِ مارکرها: عینِ قاعدهٔ پنل، و بی‌جتِ تاریخی ----------
# فیکسچرِ آرواره‌ای: پیوت‌هایِ fractal واقعی می‌سازد و CHoCHِ تاریخی می‌دهد،
# پس آزمون‌هایِ ترتیب/برچسب/ادغام رویِ دادهٔ راست می‌ایستند (فیکسچرِ `up`
# تنها جت می‌ساخت و با حذفِ جت خالی می‌ماند).
def _saw(n_cycles, start_px=200.0, depth=0.9, decay=0.96):
    out, top = [], start_px
    for _c in range(n_cycles):
        for j in range(4):
            out.append(top * (1 + 0.02 * j))
        nxt = top * depth
        for j in range(4):
            out.append(top - (top - nxt) * (j + 1) / 4)
        top = nxt * decay
    return out


_saw_px = _saw(8)
# و بعد یک شکستِ واقعی بالای کلِ پیشینه — چند واقعهٔ جت درِ میانهٔ تاریخ، که
# هیچ‌کدام نباید مارکر بسازد (و کندلِ آخر هم نیست، پس today هم جت ندارد).
_g = max(_saw_px)
saw_series = series(_saw_px + [_g * 1.02, _g * 1.045, _g * 1.06, _g * 1.03, _g * 1.01])
sw_saw = CH._fts_swings(saw_series, k=CH._FTS_SWING_K)
hist = CH._fts_setup_history(saw_series, sw_saw)
by_date = {c["time"]: i for i, c in enumerate(saw_series)}
ck("مارکر می‌شناسد و ستاپ ثبت می‌کند (%d رویداد)" % len(hist), len(hist) > 0)
ck("کنترل: فیکسچر پیوتِ کافی دارد (%d)" % len(sw_saw), len(sw_saw) >= 6)
ck("هیچ رویدادی بیرون از تاریخچه نیست", all(e["date"] in by_date for e in hist))
ck("رویدادها صعودیِ زمانی‌اند", all(a["date"] <= b["date"] for a, b in zip(hist, hist[1:])))
ck("هیچ رویدادی به آینده نگاه نمی‌کند (همه پیش از کندلِ آخر)",
   all(e["date"] < saw_series[-1]["time"] for e in hist) or not hist)
ck("برچسبِ هر رویداد از جدولِ خودِ موتور است",
   all(e["label"] == CH._FTS_SETUP_LABELS[e["kind"]] for e in hist))

# رأیِ مالک (دورِ J): جت فقط کندلِ آخر است، پس درِ تاریخچه هیچ مارکرِ جت نمی‌شود.
# پینِ این گارد درِ همین دور برگردانده شد (پیش‌تر «مارکرِ جت دارد» را الزام می‌کرد).
_ladder = CH.JET_LADDER
broke = []
for _i in range(1 + max(_ladder), len(saw_series)):
    _res = max(float(saw_series[_i - 1 - _k]["high"]) for _k in _ladder)
    _c = saw_series[_i]
    if _res > 0 and float(_c["close"]) > _res and float(_c["close"]) >= float(_c["open"]):
        broke.append(_i)
ck("کنترل: همین تاریخچه واقعهٔ شکستِ نردبان دارد (broke=%d)" % len(broke), len(broke) > 0)
ck("هیچ مارکرِ تاریخی جت ساخته نمی‌شود (%s)" % sorted({e["kind"] for e in hist}),
   not [e for e in hist if e["kind"] == "jet"])
ck("جدولِ برچسبِ ستاپ‌هایِ تاریخی جت ندارد", "jet" not in CH._FTS_SETUP_LABELS)


def _day(s):
    return datetime.date.fromisoformat(s)


for _kind in sorted({e["kind"] for e in hist}):
    _ev = [e for e in hist if e["kind"] == _kind]
    ck("رویدادهای زنجیره‌ایِ %s ادغام می‌شوند" % _kind,
       all((_day(b["date"]) - _day(a["date"])).days != 1 for a, b in zip(_ev, _ev[1:])))

# ---------- ۵) چارت دیگر موتورِ دوم ندارد ----------
fe = os.path.join(ROOT, "frontend", "src")
hits = []
for dirpath, _dirs, files in os.walk(fe):
    for fn in files:
        if not fn.endswith((".ts", ".tsx")):
            continue
        p = os.path.join(dirpath, fn)
        try:
            txt = open(p, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        if "export function analyzeFts" in txt:
            hits.append(os.path.relpath(p, ROOT))
nn = os.path.join(fe, "features", "technical", "nahayatnegar")
ck("موتورِ مرورگرِ FTS از مخزن بیرون رفته است",
   not os.path.exists(os.path.join(nn, "lib", "ftsOverlays.ts")))
imports = [os.path.join(dp, f) for dp, _d, fs in os.walk(nn) for f in fs
           if f.endswith((".ts", ".tsx")) and "from '../lib/ftsOverlays'" in open(
               os.path.join(dp, f), encoding="utf-8").read()]
ck("هیچ فایلی از پهنهٔ نهایات‌نگارِ فنی اورلیِ حذف‌شده را import نمی‌کند", not imports)
wrapper = open(os.path.join(fe, "features", "technical", "nahayatnegar",
                            "components", "KLineChartWrapper.tsx"), encoding="utf-8").read()
ck("چارت دیگر از موتورِ مرورگر فراخوانی نمی‌کند", "analyzeFts(" not in wrapper)
ck("اورلیِ فیبو و مارکر از فیلدِ سرور خوانده می‌شود",
   "ftsAnalysis.fib" in wrapper and "ftsAnalysis.setups" in wrapper)
page = open(os.path.join(fe, "features", "technical", "routes", "TechnicalPage.tsx"),
            encoding="utf-8").read()
ck("صفحه همان تحلیلی را به چارت می‌دهد که پنل می‌خواند (یک منبع، یک درخواست)",
   "fts={analysis.data?.fts ?? null}" in page and "useFtsAnalysis" in page)
ck("چارت کوئریِ تازه نمی‌زند — فقط prop می‌گیرد",
   "useFtsAnalysis(" not in wrapper and "fts?: FtsAnalysisData" in wrapper)

# ---------- ۶) لایۀ «الگوهای FTS» دیگر داور ندارد (#193) ----------
# این لایه تا همین نسخه سومین موتور بود: خودش پیوت می‌زد، خودش MA52 را از ۲۶۰
# کندلِ روزانه می‌گرفت و با عددِ پنل نمی‌خواند (سنجشِ ۱۲ نماد: ۱۱ اختلاف؛
# «پارس»: جتِ این لایه ۱۱٬۸۰۸ در برابر ۲٬۷۵۸ِ سرور). حالا فقط نگاشت است.
# سه چیز قفل می‌شود: موتورِ محلی از مخزن رفته، سرور برای هر هشت الگو عدد
# می‌دهد، و نشانگرِ نقطه‌زنی با *تاریخ* می‌آید نه با اندیسِ آرایۀ سرور.
po_path = os.path.join(fe, "features", "technical", "lib", "patternOverlays.ts")
po = open(po_path, encoding="utf-8").read()
ck("ftsPatterns.ts از مخزن بیرون رفت (یک موتورِ داور، نه سه‌تا)",
   not os.path.exists(po_path.replace("patternOverlays.ts", "ftsPatterns.ts")))
patt_imports = [os.path.join(dp, f) for dp, _d, fs in os.walk(fe) for f in fs
                if f.endswith((".ts", ".tsx"))
                and "ftsPatterns" in open(os.path.join(dp, f), encoding="utf-8").read()]
ck("هیچ فایلی موتورِ حذف‌شدۀ الگو را import نمی‌کند", not patt_imports)
for tok in ("swingHighs", "swingLows", "ma14TrailingExit", "sma(", "rsi(", "detect"):
    ck("لایۀ نگاشت هیچ محاسبۀ اندیکاتوری نمی‌کند: " + tok, tok not in po)
ck("نگاشت از دهانۀ خودِ سرور می‌خواند",
   "patternInputsFromFts" in po and "jet?.resistance" in po and "third_peak_level" in po
   and "weekly_rsi5" in po and "floor_date" in po)
ck("چارت همان نگاشت را صدا می‌زند و دیگر detect* ندارد",
   "patternInputsFromFts(" in wrapper and "detectJet(" not in wrapper
   and "detectFibZigzag(" not in wrapper)
ck("فیبو از این لایه حذف شد تا دوباره با موتورِ دوم رسم نشود (#161 #193)",
   "'fib'" not in po)
ck("هیچ قیمتی در چارت جانشینِ داده نمی‌شود (priceAt از لایه رفت)",
   "priceAt(" not in wrapper)

# کمربندِ بلند از پنل: سنجشِ پیکسلیِ زندۀ «آكام» نشان داد باندِ ±۲٪ سقفِ سوم
# ۲۶٬۲۳ پیکسل از ۴۰۳٬۳۳ پیکسلِ پنل را می‌پوشاند (کندل‌ها زیرِ رنگ می‌رفتند).
# داورِ jev-pilot «الف»: ارتفاعِ بصری سقف دارد و اگر بلندتر شد فقط خطِ سطح می‌ماند.
ck("سقفِ ارتفاعِ بصریِ کمربند درِ نگاشت تعریف شده",
   "BAND_MAX_OF_VIEW" in po and "(hi - lo) / span > BAND_MAX_OF_VIEW" in po)
ck("هر دو کمربند (سقف سوم و ساعت شنی) از همان pushBand عبور می‌کنند",
   po.count("pushBand(") == 2 and po.count("'ftsZoneBands'") == 2)
ck("شاخۀ «فقط دو خطِ سطح» یک بار و داخلِ همان helper تعریف شده",
   po.count("linesOnly: true") == 1)
ck("چارت دامنهٔ دید (low/high) را به نگاشت می‌دهد — بی‌آن سقفِ ارتفاع محاسبه نمی‌شود",
   "low: c.low, high: c.high" in wrapper)

# سرور باید برای نقطه‌زنی تاریخ بدهد — اندیسِ آرایۀ سرور با ردیف‌هایِ دیدۀ
# مرورگر یکی نیست (تجمیع هفتگی/ماهانه و بازگشتِ تاریخچه)
flat = series(wave([100, 88, 150, 120, 151, 119, 150, 118, 148, 117, 151, 116]))
sw_flat = CH._fts_swings(flat, k=CH._FTS_SWING_K)
ph = CH._fts_point_hunt(flat, sw_flat)
ck("نقطه‌زنیِ ساخته‌شده، floor_date دارد", bool(ph.get("touches")) and bool(ph.get("floor_date")))
ck("floor_date همان کندلِ لنگر است (با floor_idx می‌خواند)",
   ph.get("floor_date") == flat[ph["floor_idx"]]["time"])
# قاعدۀ جدید (سنجشِ lab): لمسِ خط به‌تنهایی سیگنال نیست — کندلِ باید سبز باشد،
# low آن روی/زیر خط بخورد و پایانی **بالای** خط بسته شود (ریباند). هر دو طرفِ
# این قاعده قفل می‌شود تا «لمس = خرید» برنگردد.
_lvl = ph["floor_price"]
_no_bounce = list(flat)
_no_bounce[-1] = dict(_no_bounce[-1], open=_lvl * 1.02, high=_lvl * 1.03,
                      low=_lvl * 0.99, close=_lvl * 1.01)   # سبزِ بالای خط، بی‌لمس
_ph2 = CH._fts_point_hunt(_no_bounce, CH._fts_swings(_no_bounce, k=CH._FTS_SWING_K))
ck("لمسِ بدونِ ریباندِ همان کندل ⇒ فعال نیست (False، نه None)",
   _ph2["active"] is False and _ph2["bounced"] is False)
_bounce = list(flat[:-1])
_bounce.append({"time": flat[-1]["time"], "open": _lvl * 0.995, "high": _lvl * 1.04,
                "low": _lvl * 0.99, "close": _lvl * 1.03, "volume": 100.0})
_ph3 = CH._fts_point_hunt(_bounce, CH._fts_swings(_bounce, k=CH._FTS_SWING_K))
ck("لمس + ریباند ⇒ فعال", _ph3["active"] is True and _ph3["bounced"] is True)
tops = series(wave([100, 88, 150, 120, 151, 121, 150, 122, 140]))
sw_tops = CH._fts_swings(tops, k=CH._FTS_SWING_K)
l3 = CH._fts_exit_layer3(tops, sw_tops)
ck("سقفِ سومِ تخت، سطحِ خودش را هم بیرون می‌دهد (۱۵۱)",
   l3["third_peak"] is True and abs((l3["third_peak_level"] or 0) - 151.0) < 0.01)
l3_none = CH._fts_exit_layer3(flat, sw_flat)
ck("بدونِ سقفِ سوم، سطحِ ساختگی نمی‌سازد (None می‌ماند)",
   l3_none["third_peak"] is False and l3_none["third_peak_level"] is None)

# ---------- ۷) فال‌بکِ CDN نباید یک ساعت قفل کند ----------
src = open(os.path.join(ROOT, "api", "chart.py"), encoding="utf-8").read()
ck("پاسخِ محلیِ موقت با TTLِ پاسخِ CDN قفل نمی‌شود",
   "CHART_FALLBACK_TTL" in src and "(_t.time() - _cached[0]) < _cached[2]" in src)
ck("TTLِ فال‌بک دست‌کم ده برابر کوتاه‌تر از CDN است",
   CH.CHART_FALLBACK_TTL * 10 <= CH.CHART_CACHE_TTL)

print()
if FAILS:
    print("FTS CHART ENGINE GUARD FAILED: %d" % len(FAILS))
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("FTS CHART ENGINE GUARD OK")
