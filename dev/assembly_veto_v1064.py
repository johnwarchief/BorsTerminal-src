#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/assembly_veto_v1064.py -- وتوی مجمع: پرچمِ تازه، بی‌داده وتو نیست.

چرا: رأیِ مالک («برچسب داده بشه … و اینکه وتو بخوره») دو مصرفِ یک تقویم ساخت —
برچسبِ ردیفِ جدول از `/api/calendar/upcoming` و وتو از `/api/screener`. اگر این دو
از هم جدا بیفتند، ردیفی هشدارِ زرد دارد ولی در واچ‌لیست می‌ماند (یا برعکس)،
و هیچ تستی قرمز نمی‌شود. این گارد پنج چیز را قفل می‌کند:

  ۱) مجمعِ قطعی (assembly / assemblyExtra) ⇒ وتو + آزادشدنِ جای واچ‌لیست.
  ۲) لغو/تعویق (assemblyChange) ⇒ وتو نیست: تاریخِ نامعلوم، وتوی ساختگی است.
  ۳) نبودِ رویداد یا خطای تقویم ⇒ وتو نیست («بی‌داده وتو نیست»، هم‌قاعده با
     dev/weekly_veto_guard.py).
  ۴) پنجرهٔ تقویمِ `upcoming_assemblies` — همان تابعی که برچسب هم می‌خواند:
     افقِ ۱۴ روزه، نزدیک‌ترین رویداد، و بردِ لغو در تساویِ تاریخ.
  ۵) دلیلِ وتو آیدمپوتنت است و ردیفِ ورودی دست‌نخورده می‌ماند.
  ۶) وتو بیرونِ کشِ ۱۲ ساعته حساب می‌شود و payloadِ کش جهش نمی‌خورد — وگرنه
     نمادی که مجمعمان تمام شده تا ۱۲ ساعت وتو می‌ماند.

بدون شبکه، بدون market.db و بدون فایلِ تقویم — هم `upcoming_assemblies` و هم
`_cal_cache_events` جعل می‌شوند (همان قاعدهٔ «هیچ منبعِ واقعی‌ای را برای آزمودنِ
گیت صدا نزن»).
اجرا:  python dev/assembly_veto_v1064.py
"""
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

CHECKS = []


def ck(cond, msg):
    CHECKS.append((bool(cond), msg))
    return cond


import api.screener as SC  # noqa: E402

TODAY = datetime.date.today()
_in3 = (TODAY + datetime.timedelta(days=3)).isoformat()


def ev(cat, date):
    return {"symbol": "فولاد", "date": date, "cat": cat, "title": "آگهی دعوت به مجمع"}


def row(**kw):
    r = {"symbol": "فولاد", "watchlist": True, "excluded": False,
         "exclusion_reasons": "", "score": 4}
    r.update(kw)
    return r


_orig_cal = SC.upcoming_assemblies


def stub_calendar(mapping=None, boom=False):
    def _f(days=None):
        if boom:
            raise RuntimeError("cache.json خوانده نشد")
        return dict(mapping or {})
    SC.upcoming_assemblies = _f


def restore():
    SC.upcoming_assemblies = _orig_cal


# ── ۱) مجمعِ قطعی ⇒ وتو ──────────────────────────────────────────────────────
for cat, label in (("assembly", "عمومی"), ("assemblyExtra", "فوق‌العاده")):
    stub_calendar({"فولاد": ev(cat, _in3)})
    out = SC._apply_assembly_veto([row()])[0]
    ck(out["assembly_veto"] is True, "%s ⇒ وتو روشن است" % cat)
    ck(out["watchlist"] is False, "%s ⇒ جای واچ‌لیست آزاد می‌شود" % cat)
    ck(out["assembly_days"] == 3 and out["assembly_date"] == _in3,
       "%s ⇒ تاریخ و شمارِ روزها میلادیِ ISO به فرانت می‌رسد" % cat)
    ck("وتوی مجمع" in out["exclusion_reasons"] and "۳ روز تا مجمع" in out["exclusion_reasons"],
       "%s ⇒ دلیل با رقمِ فارسی نوشته می‌شود (%r)" % (cat, out["exclusion_reasons"]))
    ck(out["excluded"] is False,
       "%s ⇒ `excluded` دست‌نخورده: مجمع ضعفِ بنیادی نیست، خاکستری‌کردنِ ردیف دروغ است" % cat)

# ── ۲) لغو/تعویق ⇒ وتو نیست ──────────────────────────────────────────────────
stub_calendar({"فولاد": ev("assemblyChange", _in3)})
out = SC._apply_assembly_veto([row()])[0]
ck(out["assembly_veto"] is False and out["watchlist"] is True,
   "لغو/تعویقِ مجمع وتو نمی‌سازد — تاریخِ نامعلوم، وتوی ساختگی است")
ck("وتوی مجمع" not in out["exclusion_reasons"],
   "لغو/تعویق دلیلی به exclusion_reasons اضافه نمی‌کند")

# ── ۳) بی‌داده وتو نیست ──────────────────────────────────────────────────────
stub_calendar({})
out = SC._apply_assembly_veto([row()])[0]
ck(out["assembly_veto"] is False and out["watchlist"] is True,
   "نبودِ رویداد ⇒ وتو نیست")

stub_calendar(boom=True)
out = SC._apply_assembly_veto([row()])[0]
ck(out["assembly_veto"] is False and out["watchlist"] is True,
   "خطای تقویم ⇒ وتو نیست (شکست به سمتِ «نه»، نه به سمتِ حدس)")

# رویدادِ بیرونِ افق هرگز به `_apply_assembly_veto` نمی‌رسد؛ پنجرهٔ زمانی کارِ
# `upcoming_assemblies` است و پایین‌تر، روی خودِ همان تابع سنجیده می‌شود.

# ── ۴) پنجرهٔ تقویم: همان تابعی که برچسب هم می‌خواند ─────────────────────────
# وتو و برچسب یک منبع دارند؛ اگر این پنجره اشتباه کند هر دو با هم اشتباه می‌کنند
# و هیچ تستی قرمز نمی‌شود. کشِ تقویم جعل می‌شود، نه فایلِ واقعی.
import api.chart as CH  # noqa: E402

T_TITLE = "آگهی دعوت به مجمع عمومی عادی سالیانه دوره ۱۲ ماهه"
X_TITLE = "تصمیمات مجمع عمومی عادی به طور فوق العاده دوره ۱۲ ماهه"
C_TITLE = "لغو مجمع عمومی فوق العاده مورخ ۱۴۰۵/۰۶/۲۰"
D_TITLE = "تصمیمات مجمع عمومی عادی سالیانه: تقسیم سود نقدی به ازای هر سهم"


def cal_event(title, days, sym="فولاد", tid=1):
    # دسته را `_cal_classify` از tid می‌گیرد (۱=عمومی، ۲=فوق‌العاده، ۳=سود)، نه از عنوان.
    return {"event_title": title, "event_type_id": tid, "asset_symbol_trade": sym,
            "date_time": (TODAY + datetime.timedelta(days=days)).isoformat() + "T10:00:00"}


def run_calendar(events, days=None):
    orig = CH._cal_cache_events
    CH._cal_cache_events = lambda: list(events)
    try:
        return CH.upcoming_assemblies() if days is None else CH.upcoming_assemblies(days)
    finally:
        CH._cal_cache_events = orig


got = run_calendar([cal_event(T_TITLE, 3)])
ck(list(got) == ["فولاد"] and got["فولاد"]["cat"] == "assembly",
   "مجمعِ ۳ روز دیگر در پنجره است (%r)" % got.get("فولاد"))

got = run_calendar([cal_event(T_TITLE, 20)])
ck(got == {}, "مجمعِ ۲۰ روز دیگر بیرونِ افق است — برچسب هم وتو هم ساکت")

got = run_calendar([cal_event(T_TITLE, -1)])
ck(got == {}, "مجمعِ دیروز (گذشته) برنمی‌گردد")

got = run_calendar([cal_event(T_TITLE, 10), cal_event(X_TITLE, 3, tid=2)])
ck(got["فولاد"]["cat"] == "assemblyExtra" and got["فولاد"]["date"] ==
   (TODAY + datetime.timedelta(days=3)).isoformat(),
   "دو مجمع برای یک نماد ⇒ نزدیک‌ترین برنده است (%r)" % got["فولاد"])

_d0 = TODAY.isoformat()
got = run_calendar([{"event_title": T_TITLE, "event_type_id": 1,
                     "asset_symbol_trade": "فولاد", "date_time": _d0 + "T09:00:00"},
                    {"event_title": C_TITLE, "event_type_id": 0,
                     "asset_symbol_trade": "فولاد", "date_time": _d0 + "T10:00:00"}])
ck(got["فولاد"]["cat"] == "assemblyChange",
   "تساویِ تاریخ ⇒ لغو/تعویق برنده است تا تاریخِ باطل‌شده به کاربر نشان داده نشود")

got = run_calendar([cal_event(D_TITLE, 3, tid=3)])
ck(got == {}, "تقسیمِ سود (dividend) مجمع نیست — وتو نمی‌سازد")

got = run_calendar([cal_event(T_TITLE, 3, sym="")])
ck(got == {}, "رویدادِ بی‌نماد رد می‌شود، نه کلِ پاسخ")

got = run_calendar([{"event_title": T_TITLE, "event_type_id": 1,
                     "asset_symbol_trade": "فولاد", "date_time": "نه یک تاریخ"}])
ck(got == {}, "تاریخِ خراب ⇒ ردیف رد می‌شود و تابع نمی‌میرد")

got = run_calendar([cal_event(T_TITLE, 10, sym="فولادي")])
ck(list(got) == ["فولادی"], "کلیدِ خروجی نرمال‌شده است (%r)" % list(got))

got = run_calendar([cal_event(T_TITLE, 20)], days=30)
ck(list(got) == ["فولاد"], "افقِ درخواستی بزرگ‌تر ⇒ همان تابع، پنجرهٔ بازتر")

ck(CH._clamp_days("abc") == CH.ASSEMBLY_NEAR_DAYS and CH._clamp_days(0) == 1
   and CH._clamp_days(9999) == 90,
   "افقِ نامعتبر/بیرونِ محدوده به [۱, ۹۰] برگردانده می‌شود")

# ── ۵) همزیستی با وتوی هفتگی و آیدمپوتنس ────────────────────────────────────
stub_calendar({"فولاد": ev("assemblyExtra", TODAY.isoformat())})
r0 = row(exclusion_reasons="بیمه — حذف خودکار", excluded=True)
out = SC._apply_assembly_veto([r0])[0]
ck("بیمه — حذف خودکار" in out["exclusion_reasons"],
   "وتوی مجمع دلیلِ قبلی را پاک نمی‌کند")
ck("امروز مجمع عمومی دارد" in out["exclusion_reasons"],
   "مجمعِ همان امروز ⇒ «امروز»، نه «۰ روز» (%r)" % out["exclusion_reasons"])
ck(out["excluded"] is True, "ردیفِ ازپیش‌مردود همان‌طور مردود می‌ماند")

again = SC._apply_assembly_veto([out])[0]
ck(again["exclusion_reasons"] == out["exclusion_reasons"],
   "دو بار اعمال ⇒ دلیل دو بار نمی‌نشیند (آیدمپوتنت)")

# نرمال‌سازیِ نماد: قراردادِ `upcoming_assemblies` این است که کلیدها نرمال‌شده
# برگردند (بالا سنجیده شد)، پس سمتِ ردیف باید «ي» عربیِ جدول را به همان برساند.
stub_calendar({"فولادی": ev("assembly", _in3)})
out = SC._apply_assembly_veto([row(symbol="فولادي")])[0]
ck(out["assembly_veto"] is True,
   "نمادِ ردیف با یای عربی هم به همان رویداد می‌رسد (نرمال‌سازیِ سمتِ ردیف)")

# کلیدِ تقویم `strip` می‌شود (`_norm` در api/chart.py)؛ اگر سمتِ ردیف strip
# نشود، نمادی که در جدولِ بازار فضای انتهایی دارد هرگز وتو نمی‌گیرد و هیچ تستی
# قرمز نمی‌شود. شاهدِ زنده ۱۴۰۵-۰۷-۰۹: ردیفِ «معيار » در /api/screener.
stub_calendar({"فولاد": ev("assembly", _in3)})
out = SC._apply_assembly_veto([row(symbol="فولاد ")])[0]
ck(out["assembly_veto"] is True,
   "نمادِ ردیف با فضای انتهایی هم وتو می‌گیرد (کلیدِ تقویم strip شده است)")

# ── ۶) ورودی جهش نمی‌خورد ───────────────────────────────────────────────────
stub_calendar({"فولاد": ev("assembly", _in3)})
src_row = row()
before = dict(src_row)
SC._apply_assembly_veto([src_row])
ck(src_row == before and "assembly_veto" not in src_row,
   "ردیفِ ورودی کپی می‌شود، جهش درجا نه — وگرنه دلیل هر درخواست یک‌بار اضافه می‌شد")

# ── ۷) وتو بیرونِ کشِ ۱۲ ساعته ──────────────────────────────────────────────
# این همان کلاسِ باگی است که وتو را داخلِ بدنهٔ کشیدهٔ اسکن می‌کاشت: payloadِ کشِ
# رم همان آبجکتِ برگشتی است، پس جهشِ آن کش را برای ۱۲ ساعت مسموم می‌کرد.
cached = {"v": 1, "data": [row(), row(symbol="خودرو")]}
SC._screener_cached = lambda: cached
stub_calendar({"فولاد": ev("assembly", _in3)})
res = SC.get_screener()
ck(res is not cached, "پاسخِ /api/screener کپیِ payloadِ کش است، نه خودش")
ck(res["v"] == 1, "بقیهٔ کلیدهای payload دست‌نخورده منتقل می‌شوند")
by_sym = {r["symbol"]: r for r in res["data"]}
ck(by_sym["فولاد"]["assembly_veto"] is True and "assembly_veto" not in cached["data"][0],
   "وتو روی پاسخِ تازه می‌نشیند و کشِ دیسک/رم را آلوده نمی‌کند")
ck(by_sym["خودرو"]["assembly_veto"] is False,
   "نمادِ بی‌مجمع در همان پاسخ وتو نمی‌گیرد")

# فردا که مجمع تمام شد، وتو باید بی‌آنکه کش باطل شود خودش برداشته شود.
stub_calendar({})
res2 = SC.get_screener()
ck(res2["data"][0]["assembly_veto"] is False
   and res2["data"][0]["watchlist"] is True,
   "پایانِ مجمع ⇒ وتو در درخواستِ بعدی خودش برداشته می‌شود (کش باطل نشد)")

# payloadِ خالی/خراب نباید ۵۰۰ بدهد.
SC._screener_cached = lambda: {"v": 1, "data": []}
ck(SC.get_screener() == {"v": 1, "data": []}, "پاسخِ خالی همان‌طور برمی‌گردد")
SC._screener_cached = lambda: None
ck(SC.get_screener() is None, "کشِ نساخته ⇒ None، نه استثنا")

restore()

failed = 0
for ok, msg in CHECKS:
    print(("  PASS " if ok else "  FAIL ") + msg)
    failed += 0 if ok else 1
print("\n%d checks, %d failed" % (len(CHECKS), failed))
print("ASSEMBLY VETO GUARD " + ("OK" if failed == 0 else "FAILED"))
sys.exit(1 if failed else 0)
