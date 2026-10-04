# dev/test_adjustment_phasea.py — Round K/PHASE A: جداسازیِ معناییِ تعدیل و مسیرِ کاننیکال
"""تستِ واحدِ تعدیل (کارِ #73، Round K — PHASE A).

سه چیز را می‌سنجد، نه بیشتر:
  ۱) چهار مفهومِ متفاوت‌اند: `none` · `combined` · نمایِ بازدهی (شاخصِ ۱۰۰) ·
     تعدیلِ عملکردیِ واقعی. آخری با دادهٔ این برنامه ساخته **نمی‌شود** و هیچ مسیرِ
     سرور آن را «در دسترس» اعلام نمی‌کند.
  ۲) یک سریِ کاننیکال: خام + ضریب‌هایِ یک‌بارکشف‌شده ⇒ `_fts_scaled`. چارت، FTS و
     موتورِ دوم همه از همان عبور می‌کنند و هیچ‌کدام دوباره ضرب نمی‌کند.
  ۳) فال‌بکِ محلی معنا را نمی‌شکند: یا همان مجموعهٔ رویداد را می‌دهد (local-cache)
     یا صریح اعلام می‌کند که داوریِ تعدیل در دسترس نیست — بی‌سروصدا «تعدیل‌شده»
     برنمی‌گرداند.

کنترلِ منفی هم دارد: اگر سنجشی بی‌دلیل سبز شود، همین‌جا قرمز می‌شود.
بی‌شبکه؛ بانکِ محلی اختیاری است و نبودش SKIP می‌شود نه شکست (CI بانک ندارد).
"""
import io
import json
import math
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api.chart as CH  # noqa: E402

PASS = FAIL = SKIP = 0


def ck(label, cond, detail=""):
    global PASS, FAIL, SKIP
    if cond is None:
        SKIP += 1
        print(f"  SKIP  {label}")
        return
    if cond:
        PASS += 1
        print(f"  OK    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}  {detail}")


def _db_ok():
    try:
        conn = sqlite3.connect(CH.DB_PATH, timeout=20)
        conn.execute("SELECT 1 FROM price_history LIMIT 1")
        conn.close()
        return True
    except Exception:
        return False


print("═" * 72)
print("PHASE A — تعدیلِ کاننیکال (Round K)")
print("═" * 72)

HAS_BANK = _db_ok()

# ══════════════ ۱) چهار مفهوم، دو تا ساختنی ══════════════
SRC = io.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "api", "chart.py"), encoding="utf-8").read()
ck("سرور هیچ‌جا functional_available را true نمی‌کند (منبعِ واگرایِ ادعا)",
   '"functional_available": False' in SRC and '"functional_available": True' not in SRC)
ck("بلوکِ توانایی درِ پاسخ می‌آید، نه فقط درِ متنِ خطا",
   SRC.count('"adjustCapability"') >= 3, SRC.count('"adjustCapability"'))
ck("دلیلِ نبودِ تعدیلِ عملکردی درِ خودِ پاسخ است (کاربر با متنِ سرور می‌خواند)",
   "_ADJ_FUNCTIONAL_REASON" in SRC and "functional_reason" in SRC)

cap0 = CH._adjust_capability([], "local-db-unseen")
cap1 = CH._adjust_capability([{"date": "2020-01-11", "ratio": 0.5}], "base-price-discontinuity")
cap2 = CH._adjust_capability([], "no-adjustment-event")
cap3 = CH._adjust_capability([], "base-not-anchored")
ck("«رویدادی نیستِ تأییدشده» با «نداریم» یکی نیست",
   cap2["combined_available"] is True and cap0["combined_available"] is False)
ck("لنگرِ NAV (صندوق) که داوریِ تعدیل ندارد، combined را «هست» جا نمی‌زند",
   cap3["combined_available"] is False and cap3["event_count"] == 0)
ck("با رویداد، combined در دسترس است و functional نه (هیچ‌وقت)",
   cap1["combined_available"] is True and cap1["functional_available"] is False)

# ══════════════ ۲) ضرایب: یک‌بار، ترتیب‌مستقل، یکنوا ══════════════
evs = [{"date": "2020-01-13", "ratio": 0.8}, {"date": "2020-01-11", "ratio": 0.5}]
times = ["2020-01-08", "2020-01-09", "2020-01-12", "2020-01-14", "2020-01-20"]
f_a = CH._factors_from_events(times, evs)
f_b = CH._factors_from_events(times, list(reversed(evs)))
ck("ترتیبِ ورودیِ رویداد ضرایب را عوض نمی‌کند", f_a == f_b, f"{f_a} vs {f_b}")
ck("ضریبِ پیش‌از‌رویداد کوچک‌تر است و درِ روزِ رویداد و بعدش دقیقاً ۱",
   f_a == [0.4, 0.4, 0.8, 1.0, 1.0], f_a)
ck("ضرایب صعودیِ زمانی‌اند (هیچ‌وقت به گذشته برنمی‌گردند)",
   all(x <= y for x, y in zip(f_a, f_a[1:])))
ck("بدونِ رویداد همه ضریب ۱ — یعنی «تعدیلِ بی‌جابه‌جایی»، نه حذفِ سری",
   CH._factors_from_events(times, []) == [1.0] * len(times))

# کنترلِ منفی: اگر حلقه از جدیدبهقدیمی اشتباه چیده شود، f[0] باید عوض شود
_bad = CH._factors_from_events(times, [{"date": "2020-01-11", "ratio": 0.5}])
ck("کنترلِ منفی: یک رویداد، فقط کندل‌هایِ پیش از خودش را جابه‌جا می‌کند",
   _bad == [0.5, 0.5, 1.0, 1.0, 1.0], _bad)

# ══════════════ ۳) `_fts_scaled` = تنها سریِ کاننیکال ══════════════
raw = [{"time": t, "open": 1000, "high": 1100, "low": 950, "close": 1000,
        "last": 1010, "volume": 1000} for t in times]
vols = [{"time": t, "value": 1000, "color": "#fff"} for t in times]
facts = [{"time": t, "factor": f} for t, f in zip(times, f_a)]
scaled = CH._fts_scaled(raw, facts, vols)
ck("سریِ تعدیل‌شده صعودی و هم‌تعداد است", len(scaled) == len(times)
   and [c["time"] for c in scaled] == times, [c["time"] for c in scaled])
ck("ضریبِ دوبار اعمال نمی‌شود: بارِ دوم عدد را عوض می‌کند (پس مصرف‌کننده خام می‌گیرد)",
   CH._fts_scaled(scaled, facts, vols)[0]["close"] != scaled[0]["close"])
ck("هندسه حفظ می‌شود: low ≤ open,close ≤ high در هر کندلِ تعدیل‌شده",
   all(c["low"] <= min(c["open"], c["close"]) and c["high"] >= max(c["open"], c["close"])
       for c in scaled), scaled[:2])
ck("حجم بر ضریب تقسیم می‌شود تا ارزشِ معامله ثابت بماند",
   scaled[0]["volume"] == round(1000 / 0.4) and scaled[-1]["volume"] == 1000,
   [c["volume"] for c in scaled])
ck("«آخرین» از «پایانی» بازسازی نمی‌شود (هر دو ×kِ خودشان)",
   scaled[0]["last"] != scaled[0]["closing"] and scaled[0]["last"] > 0,
   (scaled[0]["last"], scaled[0]["closing"]))

# نمایِ بازدهی (شاخصِ ۱۰۰) کارِ سرور نیست — سرور ریال می‌دهد؛ ادعایِ parity اینجا می‌مرد
ck("سرور هیچ سریِ شاخص‌شده‌ای به‌جایِ ریال نمی‌فرستد (تنها نقطۀ مقیاس = فرانت)",
   "PERFORMANCE_BASE" not in SRC and "indexed" not in [k.lower() for k in scaled[0]])

# ══════════════ ۴) کشفِ رویداد و فال‌بک ══════════════
# داوری‌ها رویِ تاریخ‌هایِ متمایز: تکرارِ یک روز، شمارشِ لنگر را جعلی می‌کند
_days = [f"2020-02-{d:02d}" for d in range(1, 29)]


def _mk(base_fn, close_v=1000):
    return [{"time": t, "close": close_v, "base": base_fn(t), "vol": 100} for t in _days]


e_flat, a_flat = CH._adjust_events_from_rows(_mk(lambda t: 1000))
ck("سریِ بی‌گسست ⇒ بی‌رویداد و لنگر پذیرفته («رویدادی نیست» ≠ «نمی‌دانیم»)",
   e_flat == [] and a_flat is True, (e_flat, a_flat))


def _gap(t):
    return 500 if t == "2020-02-15" else 1000


e_gap, a_gap = CH._adjust_events_from_rows(_mk(_gap))
ck("گسستِ پایه درِ نمادِ لنگر ⇒ یک رویداد، با نسبتِ درست و درِ همان روز",
   a_gap is True and len(e_gap) == 1 and abs(e_gap[0]["ratio"] - 0.5) < 1e-9
   and e_gap[0]["date"] == "2020-02-15", (a_gap, e_gap))

e_nav, a_nav = CH._adjust_events_from_rows(_mk(lambda t: 900))
ck("نمادی که پایه‌اش هر روز جابه‌جاست (لنگرِ NAV) ⇒ هیچ رویدادی نمی‌سازد",
   e_nav == [] and a_nav is False, (e_nav, a_nav))

# نشانۀ (ب): سطرِ بی‌معامله که پایانی‌اش رویِ پایه بازنویسی شده، و از آن روز به
# بعد پایه همان عدد می‌ماند (پس نشانۀ (ی) آتش نمی‌زند — فقط (ب) رویداد می‌سازد)
# نشانۀ (ب): روزِ توقفِ معامله (VOL=0) که تعدیل داخلِ ستونِ پایانیِ همان سطر نشسته،
# بی‌آنکه پایه جابه‌جا شود — همان shape ای که وبملتِ ۱۳۹۰ را از نشانۀ (ی) درمی‌آورد
_zero = _mk(lambda t: 1000)
for _r in _zero:
    if _r["time"] >= "2020-02-20":
        _r["close"] = 800
    if _r["time"] > "2020-02-20":
        _r["base"] = 800
    if _r["time"] == "2020-02-20":
        _r["vol"] = 0.0
e_zero, a_zero = CH._adjust_events_from_rows(_zero)
ck("سطرِ VOL=0 با پایانیِ جابه‌جا ⇒ یک رویداد، حتی بی‌گسستِ پایه",
   a_zero is True and len(e_zero) == 1 and abs(e_zero[0]["ratio"] - 0.8) < 1e-9
   and e_zero[0]["date"] == "2020-02-20", (a_zero, e_zero))

if HAS_BANK:
    try:
        conn = sqlite3.connect(CH.DB_PATH, timeout=30)
        n_ev = conn.execute("SELECT COUNT(*) FROM adjust_events").fetchone()[0]
        n_ver = conn.execute("SELECT COUNT(*) FROM adjust_verdict").fetchone()[0]
        conn.close()
    except Exception as e:
        n_ev = n_ver = -1
        print(f"  (جدولِ رویداد هنوز ساخته نشده: {e})")
    ck("جدول‌هایِ رویداد و داوری ساخته‌اند (یک‌بار کشف، همیشه خوانده)",
       n_ev >= 0 and n_ver >= 0, (n_ev, n_ver))

    sym = None
    try:
        conn = sqlite3.connect(CH.DB_PATH, timeout=30)
        r = conn.execute("SELECT symbol, COUNT(*) c FROM adjust_events GROUP BY symbol "
                         "ORDER BY c DESC LIMIT 1").fetchone()
        conn.close()
        sym = r[0] if r else None
    except Exception:
        sym = None
    if sym:
        stored = CH._stored_adjust_events(sym)
        d = CH.get_chart_db(sym)
        ck("مسیرِ محلی همان مجموعهٔ رویدادِ کاننیکال را می‌دهد (نه [])",
           d.get("adjustEvents") == stored and len(stored) > 0, len(stored))
        ck("منبعِ مسیرِ محلی «local-cache» اعلام می‌شود",
           d.get("adjustSource") == "local-cache", d.get("adjustSource"))
        ck("ضرایبِ مسیرِ محلی از همان رویدادها می‌آیند و بی‌ضریبِ یک نیستند",
           any(abs(f["factor"] - 1.0) > 1e-9 for f in d.get("factors") or []),
           len(d.get("factors") or []))
        ck("ضرایبِ مسیرِ محلی = حاصلِ ضربِ مستقلِ رویدادهایِ بعداز آن روز",
           [round(f["factor"], 8) for f in d["factors"]]
           == [round(x, 8) for x in CH._factors_from_events(
               [str(c["time"])[:10] for c in d["candles"]], stored)],
           (d["factors"][:2], stored[:2]))
        f1 = CH._fts_scaled(d["candles"], d["factors"], d["volumes"])
        _raw_by_date = {str(c["time"])[:10]: c for c in d["candles"]}
        _fac_by_date = {str(x["time"])[:10]: float(x["factor"]) for x in d["factors"]}
        # برابریِ روز‌به‌روزِ «سریِ کاننیکال» با بازسازیِ مستقلِ خام × ضریب (همان
        # گردکردنِ پایین‌گردِ +۰٫۵ که `_fts_scaled` می‌کند). این همان سنجشِ #۵ است،
        # بی‌شبکه و با اعدادِ واقعیِ بانک.
        _mism = []
        for c in f1:
            _raw = _raw_by_date.get(c["time"])
            if _raw is None:
                _mism.append((c["time"], "بدونِ خام")); continue
            _want = math.floor(float(_raw["close"]) * _fac_by_date.get(c["time"], 1.0) + 0.5)
            if abs(c["close"] - _want) > 1.0:
                _mism.append((c["time"], c["close"], _want))
        ck("برابریِ روز‌به‌روز: سریِ تعدیل = خام × ضریبِ تجمعی (بیرونِ ±۱ ریال صفر مورد)",
           not _mism, _mism[:4])
        _moved = sum(1 for c in f1 if c["close"] != _raw_by_date[c["time"]]["close"])
        ck("کنترلِ منفی: اگر ضرایب را همه ۱ بگیریم، همان کندلِ اول عوض می‌شود",
           CH._fts_scaled(d["candles"], [{"time": c["time"], "factor": 1.0} for c in d["candles"]],
                          d["volumes"])[0]["close"] != f1[0]["close"])
        ck("آخرین کندل دقیقاً خام می‌ماند (لنگرِ مقیاسِ روزِ آخر)",
           abs(f1[-1]["close"] - _raw_by_date[f1[-1]["time"]]["close"]) < 1e-9,
           (f1[-1]["close"], _raw_by_date[f1[-1]["time"]]["close"]))
        print(f"  ·  {_moved} کندل از {len(f1)} با ضریب جابه‌جا شده‌اند "
              f"(رویداد: {len(stored)})")
    else:
        ck("مسیرِ محلی همان رویدادها را می‌دهد", None, "بانک هنوز رویدادی ندارد")

    # نمادی که هرگز دیده نشده ⇒ اعلامِ صریحِ ناتوانی، نه ادعایِ تعدیل
    d_unk = CH.get_chart_db("نمادِ_وجود_ندارد_۹۹۹")
    ck("نمادِ ندیده‌شده: combined در دسترس نیست و صادقاً اعلام می‌شود",
       d_unk.get("status") == "success" and
       d_unk.get("adjustCapability", {}).get("combined_available") is False and
       d_unk.get("adjustSource") == "local-db-unseen",
       (d_unk.get("adjustSource"), d_unk.get("count")))
else:
    ck("بانکِ محلی برایِ سنجشِ فال‌بک", None, "market.db درِ این محیط نیست — SKIP")

print("─" * 72)
print(f"نتیجه: {PASS}_pass / {FAIL}_fail / {SKIP}_skip")
sys.exit(1 if FAIL else 0)
