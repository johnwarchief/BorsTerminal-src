#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/fts_ind3_na_guard_v1065.py -- شاخص ۳: «بی‌داده» هیچ‌وقت «رد» نمی‌شود.

چرا: در نشستِ زندهٔ ۲۰۲۶-۰۹-۳۰ قیفِ غربالگری مرحلۀ بنیادی را برایِ نمادهایی
«رد» می‌گفت که اصلاً سطرِ «سود ناخالص» در صورتِ مالی‌شان نیست (صندوق،
هلدینگ، یا شرکتی که کدال آن سطر را منتشر نکرده). کارتِ جزئیات درست
«کاربرد ندارد» می‌گفت و ستونِ سه‌حالۀ جدول اشتباه «ردِ سرخ» — ۲۹۷ ردیف از
۸۷۳ با `gross_margin` تهی در اسکرینرِ زنده. رأیِ مالک (۱۴۰۵-۰۷-۰۳، همان
رأیِ ۱۶ روی شاخص ۴) می‌گوید معافیت/بی‌داده = «نظر نمی‌دهد».

این گارد سه چیز را قفل می‌کند:
  ۱) `ind3_na` حالت‌های na / exempt / marginِ تهی را «سنجیده نشد» می‌گوید و
     حاشیهٔ صفرِ واقعی را «سنجیده شده».
  ۲) اسکرینر در هر دو مسیر (زنده و نویسندهٔ fts_results) همان را به None
     می‌برد، نه False.
  ۳) حاشیهٔ عدددارِ زیرِ آستانه هنوز False است (بی‌داده را بهانۀ قبول نمی‌کنیم).

بدونِ شبکه و بدونِ market.db — کارت‌ها مصنوعی‌اند.
اجرا:  python dev/fts_ind3_na_guard_v1065.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

CHECKS = []


def ck(cond, msg):
    CHECKS.append((bool(cond), msg))
    return cond


import fts_engine as F  # noqa: E402

# ── ۱) خودِ پرسشِ «سنجیده نشد؟» ─────────────────────────────────────────────
ck(F.ind3_na({"na": True, "margin_pct": None, "pass": False}) is True,
   "کارتِ not_applicable (na=True) → سنجیده نشد")
ck(F.ind3_na({"exempt": True, "margin_pct": None}) is True,
   "exempt=True → سنجیده نشد")
ck(F.ind3_na({"margin_pct": None, "pass": False}) is True,
   "حاشیۀ تهی با pass=False هم سنجیده نشد است (نه رد)")
ck(F.ind3_na({"margin_pct": 0.0, "pass": False, "na": False}) is False,
   "حاشیۀ صفرِ واقعی سنجیده شده — رد می‌ماند")
ck(F.ind3_na({"margin_pct": 12.0, "pass": False, "na": False}) is False,
   "حاشیۀ عدددارِ زیرِ آستانه هنوز رد است")
ck(F.ind3_na(None) is False and F.ind3_na({}) is False,
   "کارتِ غایب/خالی → چیزی را «سنجیده نشد» اعلام نمی‌کند")

# ── ۲) کپی‌کارهایِ ستونِ جدول باید از همان پرسش بپرسند ─────────────────────
_scr = open("api/screener.py", encoding="utf-8").read()
ck("ind3_na(_g3)" in _scr,
   "اسکرینرِ زنده معافیتِ شاخص ۳ را به None می‌برد (ind3_na)")
ck('r["i3_pass"] = p["3_gross_margin"]' not in _scr,
   "نسخۀ صریحِ bool از passes[3] در اسکرینر نمانده")
_w = open(os.path.join("dev", "codal_fts_updater.py"), encoding="utf-8").read()
ck("ind3_na(_i3)" in _w,
   "نویسندۀ fts_results هم معافیتِ شاخص ۳ را NULL می‌نویسد (کشِ گرم = کشِ سرد)")

# ── ۳) خوانندۀ مادی‌شده None را None نگه می‌دارد ───────────────────────────
ck(F._tp(None) is None and F._tp(0) is False and F._tp(1) is True,
   "_tp سه‌حالۀ ستونِ پاس را حفظ می‌کند")

bad = [m for ok, m in CHECKS if not ok]
for ok, m in CHECKS:
    print(("  ✓ " if ok else "  ✗ ") + m)
print("IND3-NA GUARD %s — %d/%d" % ("OK" if not bad else "FAILED", len(CHECKS) - len(bad), len(CHECKS)))
sys.exit(1 if bad else 0)
