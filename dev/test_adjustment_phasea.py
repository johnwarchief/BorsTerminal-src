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
# این چک درِ دورِ پیشین «hardcode شده» را pin کرده بود (`"functional_available": False`).
# دورِ پنجم قدمِ ۵ همان سخت‌کد را **عمداً** برداشت: پرچم از قاعدۀ `_functional_state`
# حساب می‌شود. چیزی که باید ثابت بماند همان است که خطرناک بود: ادعایِ فعالِ بی‌سنجش.
# پس «True سخت‌کدشده» ممنوع است و منبعِ مقدار باید همان قاعده باشد، نه یک بولینِ ثابت.
ck("سرور functional_available را با True سخت‌کد نمی‌کند (ادعایِ بی‌سنجش ممنوع)",
   '"functional_available": True' not in SRC)
ck("مقدار از قاعدۀ محاسبه‌شده می‌آید، نه از ثابتِ بولین",
   '"functional_available": available' in SRC and "def _functional_state(" in SRC
   and "chain, coverage, kind=kind" in SRC, SRC.count("_functional_state"))
ck("دفترِ رسمی درِ همان مسیر خوانده می‌شود (پوشش/اعتبار از داده، نه از متن)",
   "corporate_ledger.build_typed_events" in SRC or "CL.build_typed_events" in SRC)
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
ck("با رویداد، combined در دسترس است", cap1["combined_available"] is True)
ck("بی‌سنجشِ زنجیره/پوشش، functional در دسترس اعلام نمی‌شود (سنجش‌نشده ≠ موجود)",
   cap1["functional_available"] is False and
   any(str(b).startswith("unmeasured") for b in cap1["functional_blockers"]),
   cap1["functional_blockers"])

# ─── قاعدۀِ محاسبه‌شدۀِ functional: کنترلِ مثبت و هشت کنترلِ منفی ───
# پرچم باید **بتواند** True شود؛ اگر تنها با «هرگز» سبز می‌ماند، همان سخت‌کدِ
# قبلی است با لباسِ تابع. پس یک وضعیتِ کاملِ ساخته‌شده (هر الزامِ `_functional_state`
# برقرار) می‌آید و سپس هر الزام یکی‌یکی می‌شکند: هر شکست باید با نامِ خودش و با
# `False` پاسخ دهد — نه با سکوت. داده‌هایِ این بخش مصنوعی‌اند و **فقط** منطقِ
# داوری را می‌سنجند؛ به هیچ جدولی نوشته نمی‌شوند.
_FULL_CHAIN = {"provenance": [], "incomplete": [], "complete": True, "anchored_last": True}
_FULL_COV = {"available": True, "ins_code": "1", "error": None, "rows_total": 2,
             "rows_valid": 2, "rows_rejected": 0, "rows_unmatched": 0,
             "coverage_start": "2019-01-01", "coverage_end": "2026-01-01",
             "pre_coverage_candles": 0, "typed_events": 2, "unresolved_events": 0,
             "needs_offer_price_events": 0, "truncated_flow": False, "flow_cap": 500}
_EV2 = [{"date": "2020-01-11", "ratio": 0.5}, {"date": "2021-06-01", "ratio": 0.8}]
cap_full = CH._adjust_capability(_EV2, "base-price-discontinuity",
                                chain=_FULL_CHAIN, coverage=dict(_FULL_COV))
ck("کنترلِ مثبت: با همهٔ الزاماتِ برقرار، پرچم واقعاً True می‌شود (پس سخت‌کد نیست)",
   cap_full["functional_available"] is True and cap_full["functional_blockers"] == [],
   cap_full["functional_blockers"])
for _fld, _val, _want in [
        ("unresolved_events", 1, "event-type-unresolved"),
        ("rows_unmatched", 1, "ledger-rows-unmatched-by-price-series"),
        ("pre_coverage_candles", 5, "candles-before-ledger-coverage"),
        ("truncated_flow", True, "ledger-flow-truncated-at-cap"),
        ("rows_rejected", 1, "ledger-rows-rejected"),
        ("needs_offer_price_events", 1, "offer-price-missing"),
        ("available", False, "ledger-unavailable"),
        ("rows_total", 0, "no-official-rows-for-instrument")]:
    _c = dict(_FULL_COV)
    _c[_fld] = _val
    if _fld == "rows_total":
        _c["rows_valid"] = 0
    _r = CH._adjust_capability(_EV2, "base-price-discontinuity",
                               chain=_FULL_CHAIN, coverage=_c)
    ck(f"کنترلِ منفی: شکستِ «{_fld}» ⇒ False با دلیلِ {_want}",
       _r["functional_available"] is False and
       any(str(b).startswith(_want) for b in _r["functional_blockers"]),
       _r["functional_blockers"])
_chain_bad = {"provenance": [{"date": "2020-01-11", "status": "incomplete:ratio"}],
              "incomplete": [{"date": "2020-01-11"}], "complete": False,
              "anchored_last": True}
_r = CH._adjust_capability(_EV2, "base-price-discontinuity",
                           chain=_chain_bad, coverage=dict(_FULL_COV))
ck("کنترلِ منفی: رویدادِ ناقص درِ زنجیره ⇒ False با دلیلِ chain-incomplete",
   _r["functional_available"] is False and _r["chain_complete"] is False and
   any(str(b).startswith("chain-incomplete") for b in _r["functional_blockers"]),
   _r["functional_blockers"])
ck("شکستِ هیچ الزامی دلیلی را خاموش نمی‌کند (بی‌سکوت درِ پاسخ)",
   all(len(CH._adjust_capability(_EV2, "base-price-discontinuity",
                                 chain=_FULL_CHAIN,
                                 coverage=dict(_FULL_COV, **{_f: _v}))
              ["functional_blockers"]) == 1
       for _f, _v in [("unresolved_events", 1), ("rows_unmatched", 2),
                      ("pre_coverage_candles", 3)]))

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
    stored, expected_rejected = [], []
    try:
        conn = sqlite3.connect(CH.DB_PATH, timeout=30)
        rows = conn.execute("SELECT symbol, COUNT(*) c FROM adjust_events GROUP BY symbol "
                            "ORDER BY c DESC LIMIT 40").fetchall()
        conn.close()
        for cand, _n in rows:
            kept, rejected = CH._filter_unproven_base_events(
                cand, CH._stored_adjust_events(cand))
            if kept:
                sym, stored, expected_rejected = cand, kept, rejected
                break
    except Exception:
        sym = None
    if sym:
        d = CH.get_chart_db(sym)
        ck("مسیرِ محلی همان مجموعهٔ رویدادِ کاننیکال را می‌دهد (نه [])",
           d.get("adjustEvents") == stored and len(stored) > 0, len(stored))
        ck("منبعِ مسیرِ محلی «local-cache» اعلام می‌شود",
           d.get("adjustSource") == "local-cache", d.get("adjustSource"))
        if expected_rejected:
            _rej = d.get("adjustRejected") or []
            ck("رویدادهایِ فیلترشدهٔ گسستِ پایه با علت در adjustRejected اعلام می‌شوند",
               all(any(str(x.get("date")) == str(e["date"]) and
                       x.get("factor_status") == e["factor_status"] for x in _rej)
                   for e in expected_rejected),
               (expected_rejected[:2], _rej[:3]))
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

# ─── جانشینیِ مجموعهٔ کش (ردیفِ شبح) ───
# بازنویسیِ بانکِ واقعی نشود: این بخش رویِ یک بانکِ موقتِ جدا اجرا می‌شود.
# چرا آزمون لازم است: نویسندۀِ کشupsert-only بود و هیچ‌گاه ردیفِ کهنه را برنمی‌داشت.
# کاشفِ زنده هر بار CSV کاملِ تاریخ را می‌پیماید، پس ردیفی که درِ آن پیمایش نیست
# دیگر پشتیبانیِ داده‌ای ندارد؛ ماندنش یعنی «یک ضریبِ اضافی روی کلِ تاریخِ قبل» —
# همان نقصی که میانۀِ بازوِ دیتابیس را ۰٫۶۴٪ → ۶٫۱۵٪ برد (`_audit/_ghost_probe.py`).
import tempfile  # noqa: E402
_tmp_db = os.path.join(tempfile.mkdtemp(prefix="adj_ghost_"), "ghost.db")
_DB_OLD = CH.DB_PATH
CH.DB_PATH = _tmp_db
try:
    GSYM = "شبحِ_آزمون"
    g_all = [{"date": "2024-01-05", "ratio": 0.90, "source": "base-price-discontinuity"},
             {"date": "2024-06-02", "ratio": 0.80, "source": "base-price-discontinuity"},
             {"date": "2024-09-01", "ratio": 0.95, "source": "priceAdjust"}]
    CH._store_adjust_events(GSYM, g_all, "base-price-discontinuity")
    ck("کشِ initial هر سه ردیف را دارد",
       [str(e["date"]) for e in CH._stored_adjust_events(GSYM)]
       == ["2024-01-05", "2024-06-02", "2024-09-01"],
       CH._stored_adjust_events(GSYM))
    # کشفِ تازه همان نماد، ردیفِ میانی را دیگر نمی‌بیند (بک‌فیلِ مبدأ) → باید برود
    CH._store_adjust_events(GSYM, [g_all[0], g_all[2]], "base-price-discontinuity")
    g_after = [str(e["date"]) for e in CH._stored_adjust_events(GSYM)]
    ck("کشفِ کاملِ تازه، ردیفِ نمانده را از کش می‌زداید (جانشینی، نه upsert)",
       g_after == ["2024-01-05", "2024-09-01"], g_after)
    g_fac = CH._factors_from_events(["2024-01-01"], CH._stored_adjust_events(GSYM))
    ck("کنترلِ منفی: ضریبِ ردیفِ زدوده‌شده از فاکتور بیرون می‌آید (۰٫۸۵۵ نه ۰٫۶۸۴)",
       abs(g_fac[0] - 0.855) < 1e-9, g_fac)
    # منبعِ «کشف‌شده از CSV» نه: حقِّ پاک‌کردنِ ردیفِ دیدہ‌شدۀِ دیگر را ندارد
    CH._store_adjust_events(GSYM, g_all, "base-price-discontinuity")
    CH._store_adjust_events(GSYM, [g_all[0]], "local-cache")
    ck("منبعِ غیرِکشفی (local-cache) هیچ ردیفِ دیدہ‌شدۀِ دیگری را پاک نمی‌کند",
       [str(e["date"]) for e in CH._stored_adjust_events(GSYM)]
       == ["2024-01-05", "2024-06-02", "2024-09-01"],
       CH._stored_adjust_events(GSYM))
    # «رویدادی نیست» یک داوریِ کامل است: مجموعه باید خالی شود، نه پر از شبح
    CH._store_adjust_events(GSYM, [], "no-adjustment-event")
    ck("داوریِ «رویدادی نیست» مجموعهٔ کش را خالی می‌کند",
       CH._stored_adjust_events(GSYM) == [], CH._stored_adjust_events(GSYM))
    # منبعِ خارج از شمارۀِ منابع: نه ردیفی می‌نویسد، نه ردیفِ دیگری را می‌زداید
    CH._store_adjust_events(GSYM, g_all, "base-price-discontinuity")
    CH._store_adjust_events(GSYM, [g_all[1]], "some-future-source")
    ck("منبعِ ناشناخته نه ردیفی می‌نویسد نه ردیفِ دیدہ‌شده را پاک می‌کند",
       [str(e["date"]) for e in CH._stored_adjust_events(GSYM)]
       == ["2024-01-05", "2024-06-02", "2024-09-01"],
       CH._stored_adjust_events(GSYM))
finally:
    CH.DB_PATH = _DB_OLD

# ─── تیزکردنِ ضریبِ رویداد با دفترِ رویدادِ مبدأ (RC3) ───
# ledger جعلی تزریق می‌شود (`_ledger_events_for`) تا هر چهار شاخۀِ قاعدۀِ پذیرش
# بدونِ وابستگی به پوششِ بانکِ واقعی سنجیده شوند. عددِ مرجع از خودِ پروندهاست:
# بانکِ واقعی پوششِ ناقص دارد (پیشِ ۲۰۲۴-۰۷-۲۱ هیچ ردیفِ تعدیل، ولانا صفر ردیف)،
# پس نبودِ ردیف باید «دست‌نخورده» بدهد نه «صفر» و نه «حدس».
_LED = [{"date": "2026-09-17", "ratio": 0.2836879433, "kind": "priceAdjust"},
        {"date": "2026-09-17", "ratio": 0.2836879433, "kind": "shareChange"},
        {"date": "2024-03-17", "ratio": 1.0031515, "kind": "priceAdjust"},
        {"date": "2020-01-05", "ratio": 0.9, "kind": "priceAdjust"}]
_LED_OLD = CH._ledger_events_for
CH._ledger_events_for = lambda s: list(_LED)
try:
    # ۱) همان رویداد، عددِ گردِ ما ← عددِ بی‌گردِ مبدأ؛ تاریخ دست‌نخورده
    ev = [{"date": "2026-09-20", "ratio": 0.283787, "source": "base-price-discontinuity"}]
    o, n_sharp, n_amb = CH._sharpen_events_with_ledger("تست", ev)
    o1 = [dict(x) for x in o]
    ck("ردیفِ مبدأ درِ پنجره و تلورانس ⇒ عددِ دقیقِ مبدأ می‌نشیند",
       n_sharp == 1 and abs(o[0]["ratio"] - round(0.2836879433, 8)) < 1e-12 and
       o[0]["source"] == "priceAdjust", o)
    ck("تاریخِ رویدادِ دیدہ‌شده جابه‌جا نمی‌شود (۱۰ روز فاصله با ردیفِ مبدأ)",
       o[0]["date"] == "2026-09-20", o[0]["date"])
    ck("درِ تساویِ فاصله، priceAdjust بر shareChange تقدم دارد",
       o[0]["source"] == "priceAdjust", o[0]["source"])
    # ۲) ردیفِ مبدأ «رویدادِ دیگر» نباید مصرف شود (ولانا: ۰٫۳۰۰ در برابرِ ۰٫۳۷۵۵)
    ev = [{"date": "2026-09-20", "ratio": 0.3755, "source": "base-price-discontinuity"}]
    o, n_sharp, n_amb = CH._sharpen_events_with_ledger("تست", ev)
    ck("اختلافِ بیش از تلورانس ⇒ دست‌نخورده و بی‌برچسبِ مبدأ",
       n_sharp == 0 and abs(o[0]["ratio"] - 0.3755) < 1e-12 and
       o[0]["source"] == "base-price-discontinuity", o)
    # ۳) دو رویدادِ یک ردیف ⇒ هیچ‌کدام تیز نمی‌شود (بی‌طرفی، نه حذف)
    ev = [{"date": "2019-12-28", "ratio": 0.9005, "source": "base-price-discontinuity"},
          {"date": "2020-01-12", "ratio": 0.8998, "source": "base-price-discontinuity"}]
    o, n_sharp, n_amb = CH._sharpen_events_with_ledger("تست", ev)
    ck("دو رویداد برایِ یک ردیفِ مبدأ ⇒ هیچ‌کدام تیز نمی‌شود، هیچ‌کدام حذف نمی‌شود",
       n_sharp == 0 and n_amb == 2 and len(o) == 2 and
       all(e["source"] == "base-price-discontinuity" for e in o), (o, n_amb))
    # ۴) بی‌ردیفِ مبدأ (پوششِ ناقصِ بانک) ⇒ دقیقاً رفتارِ پیشین
    CH._ledger_events_for = lambda s: []
    ev = [{"date": "2026-07-01", "ratio": 0.333453, "source": "base-price-discontinuity"}]
    o, n_sharp, n_amb = CH._sharpen_events_with_ledger("ولانا", ev)
    ck("بی‌ردیفِ مبدأ: عددِ پیشین دست‌نخورده برمی‌گردد (نه صفر، نه حدس)",
       n_sharp == 0 and abs(o[0]["ratio"] - 0.333453) < 1e-12, o)
    # ۵) تیزکردن رویِ تکرارِ خواندن نباید چیزی را عوض کند (مسیرِ کش هر بار می‌خواند)
    CH._ledger_events_for = lambda s: list(_LED)
    one = [dict(x) for x in o1]
    twice = CH._sharpen_events_with_ledger("تست", one)[0]
    ck("تیزکردن idempotent است (خواندنِ دوبلۀِ کش عدد را جابه‌جا نمی‌کند)",
       [(e["date"], round(e["ratio"], 10), e.get("source")) for e in one]
       == [(e["date"], round(e["ratio"], 10), e.get("source")) for e in twice],
       (one, twice))
finally:
    CH._ledger_events_for = _LED_OLD

print("─" * 72)
print(f"نتیجه: {PASS}_pass / {FAIL}_fail / {SKIP}_skip")
sys.exit(1 if FAIL else 0)
