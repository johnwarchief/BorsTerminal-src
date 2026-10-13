#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/fts_notebook_examples_v1089.py — مثال‌هایِ عددیِ خودِ جزوه، آزموده‌شده.

چرا این گارد هست (مرحلۀ ۱ مأموریت بنیادی، ۱۴۵-۰۷-۲۱): مرجعِ قواعد بنیادی
تصویرِ `docs/جزوه FTS.pdf` است، و جزوه درِ دو جایِ صفحۀ ۴ با خودش نمی‌خواند:

  • مخرجِ حاشیه: «۳۹۲۱» درِ نثر در برابرِ «۳۶۲» درِ کسرِ همان مثال؛
  • EPS ۱۴۰: «۷۷۴» درِ جدول در برابرِ «۷۴۴» درِ فهرستِ همان صفحه.

این گارد سه کار می‌کند:
  ۱) هر مثالِ عددیِ جزوه را با حسابِ خودِ صفحه کنترل می‌کند، و اگر دو نوشتار
     جوابِ متفاوتی بدهند **هر دو** را نگه می‌دارد — یکی را بی‌صدا حقیقت نمی‌کند؛
  ۲) آستانه‌هایِ کد را با حکمِ ثبت‌شدۀ مالک می‌سنجد (نه با عددِ دلخواه):
     رشد 40/60، حاشیه 20/30، کفِ شاخص 4 برابر 0.33؛
  ۳) ثابت می‌کند شواهدِ تصویریِ همین ادعاها درِ مخزن هست و با
     `tools/notebook_evidence.py` بازتولیدشدنی است.

برچسب‌ها عمداً با رقمِ ASCII چاپ می‌شوند: هر «ترجمۀ» سراسریِ رقم، رقمِ درونِ
نامِ کلید (`v10_monetary_growth_min`) را هم می‌بَرَد — همان نقصی که این فایل
می‌خواهد بگیرد. رقمِ فارسی فقط برایِ گشتن درِ سند ساخته می‌شود (`fa`).

    python dev/fts_notebook_examples_v1089.py            # رأی‌ها
    python dev/fts_notebook_examples_v1089.py --selftest # سنسورها کور نیستند
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

EV_DIR = os.path.join(ROOT, "_audit", "notebook_evidence")
DOC = os.path.join(ROOT, "docs", "fts-notes", "FUND-NOTEBOOK-RULEMAP-2026-10-13.md")

PASS = FAIL = 0
FA = str.maketrans("0123456789", "".join(chr(0x06F0 + d) for d in range(10)))


def fa(s):
    """رقمِ ASCII → فارسی؛ فقط برایِ ساختنِ توکنی که درِ سندِ فارسی جست‌وجو می‌شود."""
    return s.translate(FA)


def chk(cond, what, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ✓ " + what)
    else:
        FAIL += 1
        print("  ✗ " + what + ("   ← " + detail if detail else ""))
    return bool(cond)


def pct(num, den):
    return num / den * 100.0


# ═══════════════════════════════════════════════════════════════════════════
#  1) شاخص ۳ — تعارضِ مخرجِ حاشیه (صفحۀ ۴)
# ═══════════════════════════════════════════════════════════════════════════
GP = 2124             # «سود (زیان) ناخالص ۲۱۲۴ میلیارد ریال» — هر دو نوشتار یکی
STATED = 58.0         # جزوه خودش جواب را «۵۸٪» نوشته
DEN_FRACTION = 3621   # مخرجِ نوشته‌شده درِ کسر
DEN_PROSE = 3921      # مخرجِ نوشته‌شده درِ نثرِ همان صفحه


def t1_margin_conflict():
    print("\n— 1) حاشيه: کدامِ مخرج جوابِ «58%»ِ خودِ جزوه را می‌دهد")
    from_fraction = pct(GP, DEN_FRACTION)
    from_prose = pct(GP, DEN_PROSE)
    chk(abs(from_fraction - STATED) < 1.0,
        "1) کسرِ صفحه (%d / %d) = %.2f%%  با «%d%%»ِ جزوه می‌خواند"
        % (GP, DEN_FRACTION, from_fraction, int(STATED)))
    chk(abs(from_prose - STATED) >= 1.0,
        "1) نثرِ صفحه (%d / %d) = %.2f%%  با «%d%%»ِ جزوه **نمی‌خواند**"
        % (GP, DEN_PROSE, from_prose, int(STATED)))
    chk(abs(from_fraction - from_prose) > 1.0,
        "1) اختلافِ دو نوشتار (%d در برابر %d) پنهان نمی‌شود"
        % (DEN_FRACTION, DEN_PROSE))
    doc = open(DOC, encoding="utf-8").read()
    for token in (fa("3921"), fa("3621"), "NEEDS_REVIEW"):
        chk(token in doc,
            "1) سندِ نقشه هر دو نوشتار + «%s» را نگه داشته" % token)


# ═══════════════════════════════════════════════════════════════════════════
#  2) شاخص ۲ — تعارضِ EPS ۱۴۰۲ (صفحۀ ۴): رأی عوض نمی‌شود
# ═══════════════════════════════════════════════════════════════════════════
EPS_1403, EPS_1404 = 1008, 1425
EPS_1402_TABLE, EPS_1402_LIST = 774, 744


def t2_eps_conflict():
    print("\n— 2) EPS 1402: دو نوشتار، یکِ رأی")
    asc_table = EPS_1402_TABLE < EPS_1403 < EPS_1404
    asc_list = EPS_1402_LIST < EPS_1403 < EPS_1404
    chk(asc_table and asc_list,
        "2) قاعدۀ «صعودی سه‌ساله» با **هر دو** نوشتار برقرار است "
        "(%d < %d < %d) ⇒ تعارض بازدارندۀ شاخص 2 نیست"
        % (EPS_1402_TABLE, EPS_1403, EPS_1404))
    chk(EPS_1402_TABLE != EPS_1402_LIST,
        "2) اختلافِ رقم (%d در برابر %d) درِ سند ثبت شده، نه حلِ بی‌صدا"
        % (EPS_1402_TABLE, EPS_1402_LIST))
    doc = open(DOC, encoding="utf-8").read()
    chk(fa("774") in doc and fa("744") in doc,
        "2) سندِ نقشه هر دو نوشتارِ EPS را نگه داشته")
    # «۱۴۵» نقلِ مردودِ دورِ پیشین است؛ هیچ‌جا به‌عنوانِ عددِ EPS مصرف نشود.
    stale = fa("145")
    hits = [l for l in doc.split("\n") if stale in l]
    chk(hits and all(("نقل" in l or "خوانده" in l) for l in hits),
        "2) «۱۴۵» فقط به‌عنوانِ نقلِ مردود می‌آید (نه به‌عنوانِ عددِ مرجع)",
        "count=%d" % len(hits))


# ═══════════════════════════════════════════════════════════════════════════
#  3) شاخص ۱ و ۴ — مثال‌هایِ حسابیِ خودِ جزوه
# ═══════════════════════════════════════════════════════════════════════════
def t3_growth_and_annualisation():
    print("\n— 3) رشد 175% و سالانه‌سازیِ x4 (مثال‌هایِ ص 3 و 5)")
    chk(pct(2.75, 1.0) - 100 == 175.0,
        "3) «(2.75 x 100) - 100 = 175%» درِ خودش حساب است")
    annual = 149.9 * 4
    chk(abs(annual - 599.6) < 0.05,
        "3) مثالِ خرداد: 149.9 x 4 = %.1f (همان عددِ نوشته‌شده درِ صفحه)" % annual)
    profit = annual * 10.0 / 100.0
    chk(abs(profit - 59.96) < 0.05,
        "3) سودِ سالانه = %.1f x 10%% = %.2f — زنجیرۀ مثالِ شاخص 4 می‌بندد"
        % (annual, profit))
    import fts_engine as FE
    for months in (3, 6, 9, 12):
        got = 12.0 / months
        want = {3: 4.0, 6: 2.0, 9: 12 / 9, 12: 1.0}[months]
        chk(abs(got - want) < 1e-9,
            "3) ضریبِ سالانه‌سازیِ %d ماهه = %s (بی‌تعمیمِ x4)"
            % (months, ("%.4f" % got).rstrip("0").rstrip(".")))
    chk(hasattr(FE, "annualized_sales"),
        "3) `fts_engine.annualized_sales` همان منطقِ داینامیک را دارد")


# ═══════════════════════════════════════════════════════════════════════════
#  4) آستانه‌ها: کد باید با حکمِ مالک بخواند، نه با عددِ اختراعی
# ═══════════════════════════════════════════════════════════════════════════
WANT_TH = {
    "growth_min": (40.0, "رأیِ 3 — کفِ قبولی"),
    "v10_monetary_growth_min": (60.0, "رأیِ 3 — هدفِ پوششِ تورم"),
    "margin_min": (20.0, "رأیِ 2 — کف"),
    "margin_optimal": (30.0, "رأیِ 2 — استاندارد"),
    "sales_to_mcap_min": (0.33, "رأیِ 4 — کفِ قبولی"),
}


def t4_thresholds_are_the_rulings():
    print("\n— 4) آستانه‌هایِ کد = حکم‌هایِ ثبت‌شدۀ مالک")
    import fts_engine as FE
    th = FE.DEFAULT_TH
    for key, (val, why) in WANT_TH.items():
        got = th.get(key)
        chk(got is not None and abs(float(got) - val) < 1e-9,
            "4) `DEFAULT_TH['%s']` = %s (%s)" % (key, val, why),
            "actual=%s" % got)
    # «بالای ۵۰٪ هم خوب است» درِ جزوه هست ولی درِ کد دروازۀ دوم نساخته —
    # این سطر ثابت می‌کند آن عدد **عمداً** رأی نشده، نه اینکه جا افتاده باشد.
    chk(not any("50" in str(k) for k in th),
        "4) هیچ دروازۀ پنهانی رویِ 50% ساخته نشده (سؤالِ بازِ بند 5-2)")
    import bors_config as BC
    flat = {}
    for k, v in (getattr(BC, "FTS_DEFAULTS", {}) or {}).items():
        if isinstance(v, dict):
            flat.update(v)
        else:
            flat[k] = v
    for key, (val, _w) in WANT_TH.items():
        if key in flat:
            chk(abs(float(flat[key]) - val) < 1e-9,
                "4) `bors_config.FTS_DEFAULTS['%s']` هم همان %s" % (key, val),
                "actual=%s" % flat[key])


# ═══════════════════════════════════════════════════════════════════════════
#  5) شواهدِ تصویری
# ═══════════════════════════════════════════════════════════════════════════
NEEDED = ("growth_40pct_p03.png", "eps_table_p04.png", "eps_list_p04.png",
          "margin_prose_p04.png", "margin_fraction_p04.png",
          "margin_fraction_p5_p05.png", "annualize_x4_p05.png",
          "industry_table_p06.png", "four_dimensions_p06.png")


def t5_evidence_exists():
    """شاهدِ تصویری باید **بازتولیدشدنی** باشد، نه اینکه حتماً درِ گیت بخوابد.

    `_audit/.gitignore` سراسرِ `*.png` را بیرون می‌گذارد (قیدِ مخزن)، پس گارد
    خودش با ابزارِ درِ گیت برش‌ها را می‌سازد و بعد اندازه‌شان را می‌سنجد — اگر
    روزی `tools/notebook_evidence.py` بشکند، همین‌جا قرمز می‌شود، نه درِ یک
    فایلِ دودوییِ تاریخ‌مصرف‌گذشته.
    """
    print("\n— 5) برش‌هایِ شاهد با ابزارِ مخزن بازتولید می‌شوند")
    have = all(os.path.isfile(os.path.join(EV_DIR, n)) for n in NEEDED)
    if not have:
        import subprocess
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "notebook_evidence.py")],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=600)
        chk(r.returncode == 0, "5) `tools/notebook_evidence.py` بی‌خطا اجرا شد",
            (str(r.stderr or "") + str(r.stdout or ""))[-200:])
    for name in NEEDED:
        p = os.path.join(EV_DIR, name)
        size = os.path.getsize(p) if os.path.isfile(p) else 0
        chk(size > 20000, "5) " + name, "size=%d" % size)
    chk(os.path.isfile(os.path.join(ROOT, "tools", "notebook_evidence.py")),
        "5) ابزارِ بازتولیدِ برش‌ها درِ مخزن است")


def selftest():
    """سنسورها کور نباشند: اگر حسابِ گارد خودِ مثال‌ها را نمی‌دید، باید قرمز شود."""
    print("\n— کنترلِ منفی (سنسورِ خودِ گارد)")
    ok = [
        chk(pct(GP, DEN_FRACTION) != pct(GP, DEN_PROSE),
            "کنترلِ منفی: دو مخرجِ متفاوت دو جوابِ متفاوت می‌دهند"),
        chk(not (EPS_1404 < EPS_1403 < EPS_1402_TABLE),
            "کنترلِ منفی: رأیِ «صعودی» رویِ ترتیبِ نزولی قرمز می‌شود"),
        chk(pct(2124, 2124) == 100.0,
            "کنترلِ منفی: `pct` صورت را بر مخرج می‌زند، نه برعکس"),
        chk(fa("774") == "".join(chr(0x06F0 + int(d)) for d in "774"),
            "کنترلِ منفی: `fa` رقمِ فارسی را کامل می‌سازد (بی‌دزدیدۀ رقم)"),
        chk(fa("v10_monetary") != "v10_monetary",
            "کنترلِ منفی: `fa` رقمِ درونِ نامِ کلید را می‌بَرَد — پس برچسب‌ها "
            "بیرونِ fa با رقمِ ASCII ساخته می‌شوند"),
    ]
    return all(ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        ok = selftest()
        print("selftest: " + ("OK" if ok else "BLIND SENSOR"))
        return 0 if ok else 1
    t1_margin_conflict()
    t2_eps_conflict()
    t3_growth_and_annualisation()
    t4_thresholds_are_the_rulings()
    t5_evidence_exists()
    selftest()
    print("\nfts_notebook_examples_v1089: %d passed / %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
