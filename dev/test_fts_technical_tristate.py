"""سه‌حالۀ سیگنال‌هایِ تکنیکال + قاعدۀ جدیدِ هر ستاپ (دورِ «موتور تکنیکال»).

هیچ شبکه‌ای نمی‌زند و market.db نمی‌خواهد: کندلِ ساختگی می‌سازد و چهار چیز را
قفل می‌کند که پیش‌تر یا hard-False بودند یا دو‌تایی محاسبه می‌شدند:

  ۱) «داده برای قضاوت نیست» ⇒ None، نه False (رأیِ مالک: null ≠ false).
  ۲) جت دو لایه دارد: پلکان (هم‌رنگِ بجِ تابلو) و سقفِ ایستادهٔ ۲۵۰ روزه
     (جزوه ص ۲۷ «مقاومتِ استاتیک») — `tier` از همان دوم می‌آید.
  ۳) CHoCH با **تأییدِ دو بسته** و حاشیۀ ۱٪ کار می‌کند (جزوه ص ۹ «دو روز تثبیت»)
     و مارکرِ تاریخچه هم همان دو عدد را از ثابت‌هایِ موتور می‌خواند.
  ۴) نقطه‌زنی فقط با **ریباندِ همان کندل** فعال می‌شود؛ خروجِ کانال (لایۀ ۲
     موتور خروج) برعکسِ آن را با `touches` می‌سنجد، نه با `active`.
اجرا:  python dev/test_fts_technical_tristate.py
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from api import chart as CH  # noqa: E402

RES = []


def ck(name, cond, got=""):
    RES.append((name if cond else "✗ " + name, bool(cond), "" if cond else repr(got)))


def bars(prices, start="2024-01-01", bodies=None):
    """کندلِ صاف (open=high=low=close) مگر `bodies[i] = (o,h,l,c)` داده باشد."""
    d0 = dt.date.fromisoformat(start)
    out = []
    for i, p in enumerate(prices):
        o = h = l = c = float(p)
        if bodies and i < len(bodies) and bodies[i]:
            o, h, l, c = (float(x) for x in bodies[i])
        out.append({"time": (d0 + dt.timedelta(days=i)).isoformat(),
                    "open": o, "high": h, "low": l, "close": c, "volume": 100.0})
    return out


def wave(turns, n_per=10):
    prices = []
    for p0, p1 in zip(turns, turns[1:]):
        step = (p1 - p0) / n_per
        for j in range(n_per):
            prices.append(round(p0 + step * j, 2))
    prices.append(float(turns[-1]))
    return prices


# ══════════════ ۱) سه‌حالگی: نبودِ داده رأی نیست ══════════════
short = bars([100.0] * 30)
j = CH._fts_jet_setup(short)
ck("جت با ۳۰ کندل ⇒ active=None (نه False)", j["active"] is None, j)
ck("جت ⇒ static_broke هم None است", j["static_broke"] is None, j)
ck("جت ⇒ tier هم None است", j["tier"] is None, j)
ck("جت ⇒ reason علت را می‌گوید", bool(j.get("reason")), j)

tiny = bars(wave([100, 105, 102], n_per=2))
c = CH._fts_choch(tiny, CH._fts_swings(tiny, k=CH._FTS_SWING_K))
ck("CHoCH بی‌پیوت ⇒ bearish/bullish هر دو None", c["bearish"] is None and c["bullish"] is None, c)
p = CH._fts_point_hunt(tiny, CH._fts_swings(tiny, k=CH._FTS_SWING_K))
ck("نقطه‌زنی بی‌کانال ⇒ active=None و touches=None",
   p["active"] is None and p["touches"] is None, p)
d = CH._fts_double_bottom(tiny, [])
ck("دابل‌باتم بی‌دو کف ⇒ active=None", d["double_bottom"]["active"] is None, d)
ck("باکس رنج با کمتر از ۲۱ کندل ⇒ active=None", d["range_box"]["active"] is None, d)

# ══════════════ ۲) جت: پلکان و سقفِ ایستاده دو لایه‌اند ══════════════
# ۳۰۰ کندل: ۲۵۰ اول زیر ۱۲۰، بعد نوسانِ ۱۰۰–۱۱۰، و در آخر شکستِ ۱۱۵
hist = bars([100.0] * 250 + wave([100, 110, 100, 110, 100, 112], n_per=8))
n = len(hist)
# کندلِ آخر: بدنهٔ صعودی و پایانی بالای هر دو سطح
hist[-1] = dict(hist[-1], open=113.0, high=118.0, low=112.5, close=117.0)
jj = CH._fts_jet_setup(hist)
ck("جت: شکستِ سقفِ ایستاده ⇒ active=True", jj["active"] is True, jj)
ck("جت: شکستِ سقفِ ایستاده ⇒ static_broke=True", jj["static_broke"] is True, jj)
# مدلِ اصلیِ جت: confirmed / expired / none (رأیِ مالک ۱۴۰۵-۰۷: strong/breakout
# بدونِ مستندِ جزوه برنمی‌گردد). شکستِ تأییدشدهٔ امروز ⇒ confirmed.
ck("جت: tier = confirmed", jj["tier"] == "confirmed", jj)
ck("جت: ceiling منتشر می‌شود", jj.get("ceiling") is not None, jj)

# زیرِ سقفِ ایستاده، شکستِ دیگری نیست ⇒ رأیِ منفیِ واقعی (ارزیابی ممکن بوده،
# پس false نه null). tier = none.
mid = bars([100.0] * 250 + wave([100, 140, 100, 118], n_per=8))
mid[-1] = dict(mid[-1], open=126.0, high=131.0, low=125.5, close=130.0)
jm = CH._fts_jet_setup(mid)
ck("جت: سقفِ ایستاده دست‌نخورده ⇒ static_broke=False", jm["static_broke"] is False, jm)
ck("جت: ارزیابی ممکن بود ولی نشکست ⇒ tier = none (نه null)", jm["tier"] == "none", jm)
# قاعدۀ null≠false در همان یک نگاه: تاریخچۀ کافی ⇒ رأیِ دوهایی، نه سنجیده‌نشده.
ck("جتِ باسابقه هیچ‌وقت null نمی‌دهد",
   jj["tier"] is not None and jm["tier"] is not None
   and jj["active"] is not None and jm["active"] is not None, (jj["tier"], jm["tier"]))

# هیچ رأیِ confirmed بدونِ active نیست (تأییدِ شکستِ امروز).
ck("هیامی نیست: confirmed ⇒ active",
   all((CH._fts_jet_setup(x)["tier"] != "confirmed")
       or CH._fts_jet_setup(x)["active"] is True for x in (hist, mid)))

# ══════════════ ۳) CHoCH: تأییدِ دودرۀ جزوه ══════════════
ck("ثابت‌هایِ CHoCH از یک‌جاست (روز=2, حاشیه=1٪)",
   CH._FTS_CHOCH_DAYS == 2 and abs(CH._FTS_CHOCH_MARGIN - 0.01) < 1e-9)
# روند صعودیِ ساختگی؛ سپس دو بستهٔ زیرِ آخرین کف
up = bars(wave([100, 120, 105, 130, 112, 140], n_per=9))
last_low = max(s["price"] for s in CH._fts_swings(up, k=CH._FTS_SWING_K)
               if s["kind"] == "low")
brk = list(up) + bars([last_low * 0.985])          # یک بسته (حاشیۀ ۱٪ رد نشده)
c1 = CH._fts_choch(brk, CH._fts_swings(brk, k=CH._FTS_SWING_K))
ck("یک بستهٔ شکست‌کننده ⇒ هنوز CHoCH نزولی نیست", c1["bearish"] is False, c1)
brk2 = list(up) + bars([last_low * 0.985, last_low * 0.98])
c2 = CH._fts_choch(brk2, CH._fts_swings(brk2, k=CH._FTS_SWING_K))
ck("دو بستهٔ متوالی زیر کف ⇒ CHoCH نزولی", c2["bearish"] is True, c2)
ck("سطحِ CHoCH همان آخرین کف است", abs(c2["level"] - round(last_low, 2)) < 0.01, c2)
# بازگشت به بالای سطح در بستۀ دوم ⇒ رأی نمی‌دهد (تثبیت نشکسته)
brk3 = list(up) + bars([last_low * 0.985, last_low * 1.004])
c3 = CH._fts_choch(brk3, CH._fts_swings(brk3, k=CH._FTS_SWING_K))
ck("بازگشتِ بستۀ دوم به بالای سطح ⇒ تثبیت نشده", c3["bearish"] is False, c3)

# ══════════════ ۴) نقطه‌زنی: لمس + ریباند ══════════════
dn = bars(wave([150, 130, 145, 120, 140, 115, 138, 114], n_per=9))
sw = CH._fts_swings(dn, k=CH._FTS_SWING_K)
ph0 = CH._fts_point_hunt(dn, sw)
ck("نقطه‌زنی: لمس‌ها شمرده می‌شوند", (ph0["touches"] or 0) >= 1, ph0)
ck("نقطه‌زنی: بدونِ ریباندِ کندلِ آخر ⇒ active=False (نه None)",
   ph0["active"] is False and ph0["bounced"] is False, ph0)
lvl = ph0["floor_price"] or 115.0
bounce = list(dn[:-1])
bounce.append({"time": dn[-1]["time"], "open": lvl * 0.99, "high": lvl * 1.05,
               "low": lvl * 0.985, "close": lvl * 1.04, "volume": 100.0})
ph1 = CH._fts_point_hunt(bounce, CH._fts_swings(bounce, k=CH._FTS_SWING_K))
ck("نقطه‌زنی: ریباندِ سبزِ بالای خط ⇒ bounced=True", ph1["bounced"] is True, ph1)
# لایۀ ۲ موتور خروج باید با «شکستِ کف» فعال شود، نه با تریگرِ خرید
below = list(dn[:-1])
below.append({"time": dn[-1]["time"], "open": lvl * 1.02, "high": lvl * 1.03,
              "low": lvl * 0.94, "close": lvl * 0.95, "volume": 100.0})
ph2 = CH._fts_point_hunt(below, CH._fts_swings(below, k=CH._FTS_SWING_K))
l2 = CH._fts_exit_layer2(below, CH._fts_swings(below, k=CH._FTS_SWING_K))
ck("کفِ شکسته ⇒ active نقطه‌زنی False می‌ماند (تریگرِ خرید نیست)",
   ph2["active"] is False, ph2)
ck("لایۀ ۲ خروج با touches کار می‌کند، نه با active",
   l2["channel_break"] == (bool((ph2["touches"] or 0) >= 3)
                           and below[-1]["close"] < ph2["floor_price"] * 0.995), l2)

# ══════════════ ۵) مارکر = موتور (تک‌منبعی) — و جت هرگز تاریخی نمی‌شود ══════════════
# دورِ J: این پین برگردانده شد. پیش‌تر «تاریخچۀ ستاپ مارکرِ جت دارد» را الزام
# می‌کرد؛ حالا جت فقط کندلِ آخر است، پس تاریخچه نباید هیچ مارکرِ جتی بدهد.
ev = CH._fts_setup_history(hist, CH._fts_swings(hist, k=CH._FTS_SWING_K))
ck("تاریخچه هیچ مارکرِ جتی نمی‌سازد", not any(e["kind"] == "jet" for e in ev), ev[-4:])
ck("جدولِ برچسبِ رویدادها جت ندارد", "jet" not in CH._FTS_SETUP_LABELS,
   CH._FTS_SETUP_LABELS)
# و همان تاریخچه واقعهٔ شکست دارد، پس نبودنِ مارکر معنا دارد (کنترلِ شکست)
_L = CH.JET_LADDER
_broke = sum(1 for _i in range(1 + max(_L), len(hist))
             if max(float(hist[_i - 1 - _k]["high"]) for _k in _L) < float(hist[_i]["close"])
             and float(hist[_i]["close"]) >= float(hist[_i]["open"]))
ck("کنترل: همین سری چند شکستِ پلکان دارد (%d)" % _broke, _broke > 0, _broke)

# ══════════════ ۶) تریگرِ نقطه‌زنی از لنگرِ کف جداست ══════════════
ph3 = CH._fts_point_hunt(hist, CH._fts_swings(hist, k=CH._FTS_SWING_K))
ck("نقطه‌زنی هر دو تاریخ را منتشر می‌کند",
   "trigger_date" in ph3 and "floor_date" in ph3, sorted(ph3))
ck("بی‌تریگرِ فعال، trigger_date منتشر نمی‌شود (None، نه کندلِ آخر)",
   ph3["trigger_date"] is None or ph3["active"] is True, ph3)
if ph3["active"] is True:
    ck("تریگر رویِ کندلِ آخر است، لنگر رویِ کفِ گذشته",
       ph3["trigger_date"] == str(hist[-1]["time"])[:10]
       and ph3["floor_date"] != ph3["trigger_date"], ph3)

# ══════════════ ۷) taxonomyِ نقش‌ها و وضعیتِ اولویت‌دار ══════════════
fullj = CH._fts_analyze_candles("X", hist)
ck("نقشِ جت = entry و فیبو = context و سقفِ سوم = warning و MA14 = exit",
   fullj["roles"].get("jet") == "entry" and fullj["roles"].get("fib_zone") == "context"
   and fullj["roles"].get("third_peak") == "warning"
   and fullj["roles"].get("ma14_exit") == "exit", fullj["roles"])
ck("وضعیت یکی از کدهایِ اولویت‌دار است",
   fullj["status"]["code"] in CH.FTS_STATUS_PRIORITY, fullj["status"]["code"])
# وتوی هفتگی نباید «تریگرِ ورود» بدهد حتی با جتِ فعال
_o = dict(fullj)
_o["trend"] = {"D": {"trend": "up"}, "W": {"trend": "down"}, "M": {"trend": "up"},
               "alignment": "na", "matrix": {"decision": "REJECT"}}
_o["jet"] = {"active": True, "resistance": 123.0, "reason": None}
_st = CH._fts_status_block(hist, _o)
ck("وتوی هفتگی بر جتِ فعال غالب است", _st["code"] == "weekly_veto", _st["code"])
ck("متنِ وضعیت با وتو «پرواز» نمی‌گوید", "پرواز" not in _st["text"], _st["text"])

ck("تاریخچه هیچ رویدادی بی‌تاریخ یا بی‌قیمت نمی‌فرستد",
   all(e.get("date") and isinstance(e.get("price"), float) for e in ev), ev[:3])
# کندلِ نامرتب/تهی نباید کرش کند
ck("کندلِ تهی ⇒ ستاپ‌ها [] (کرش نه)", CH._fts_setup_history([], []) == [])
broken = [dict(x) for x in hist]
broken[40]["high"] = None
try:
    CH._fts_analyze_candles("X", broken)
    ck("کندلِ خراب ⇒ کرش نمی‌کند", True)
except Exception as e:
    ck("کندلِ خراب ⇒ کرش نمی‌کند", False, "%s: %s" % (type(e).__name__, e))

npass = sum(1 for _n_, ok, _g in RES if ok)
for nm, ok, g in RES:
    print(("  PASS  " if ok else "  FAIL  ") + nm + ("" if ok else "   <<< " + g))
print("\n%d/%d passed" % (npass, len(RES)))
sys.exit(0 if npass == len(RES) else 1)
