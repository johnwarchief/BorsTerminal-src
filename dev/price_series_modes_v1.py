#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/price_series_modes_v1.py — رابط دقیقاً دو حالتِ سریِ قیمت دارد: خام و عملکردی.

چرا این گارد نوشته شد (دورِ ممیزیِ کلِ نمادها، ۱۴۰-۰۷-۲۷). رأیِ مالک صریح است:
«فقط دو حالتِ سریِ قیمت در رابط باقی بماند: خام و عملکردی». پنج گزینه رویِ سه فایل
پخش بود و سه‌تاش دادهٔ پشتیبان نداشت:

  • `performance` («نمایِ بازدهی (شاخصِ ۱۰۰)») — *نوعِ سری نبود*: همان سریِ combined را
    بر پایانیِ نخستین کندل تقسیم می‌کرد. نامش دقیقاً همان دامِ رأیِ ۲۰۲۶-۰۹-۲۴ بود:
    کاربر آن را «تعدیلِ عملکردی» می‌خواند و محورِ فولاد ۶۵٬۰۰۰ تا ۱۶۶٬۰۰۰ می‌شد در
    حالی که آخرین کندلِ همان پاسخِ API ۴٬۴۱۰ است (`_audit/chart_axis_stages.json`).
  • `capital` و `cash` — درِ UI «غیرفعال» بودند؛ دو حالتی که از یکِ نسبتِ ترکیبی
    تفکیک نمی‌شوند (سرور فقط گسستِ قیمتِ پایه را می‌دهد).
  • درِ بک‌اند هم `indexed_available: True` سخت‌کد شده بود — ادعایِ فعالِ بی‌سنجش برایِ
    همان حالتِ حذف‌شده، و `get_chart_db(adjustment=0|3)` که هیچ‌کس نمی‌فرستادش و هیچ
    شاخه‌ای به آن وصل نبود.

همزمان این گارد ثابت می‌کند چیزی که *حذف نشده* دست‌نخورده مانده: محورِ خطی،
لگاریتمی و درصدی، حجم، و اعشارِ صریحِ کاربر. حذفِ این‌ها رأیِ مالک نیست.

اجرا:  python dev/price_series_modes_v1.py   → ۰ قرمز لازم است
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADJ = os.path.join(ROOT, "frontend", "src", "features", "technical",
                   "nahayatnegar", "lib", "adjustments.ts")
BAR = os.path.join(ROOT, "frontend", "src", "features", "technical",
                   "nahayatnegar", "components", "FtsToolbar.tsx")
WRAP = os.path.join(ROOT, "frontend", "src", "features", "technical",
                    "nahayatnegar", "components", "KLineChartWrapper.tsx")
TPL = os.path.join(ROOT, "frontend", "src", "features", "technical",
                   "stores", "chartTemplateStore.ts")
DIALOG = os.path.join(ROOT, "frontend", "src", "features", "technical",
                      "components", "ChartSettingsDialog.tsx")
TECHPAGE = os.path.join(ROOT, "frontend", "src", "features", "technical",
                        "routes", "TechnicalPage.tsx")
CHARTPY = os.path.join(ROOT, "api", "chart.py")

PASS = FAIL = 0


def ck(ok, what, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  ok   " + what)
    else:
        FAIL += 1
        print(f"  FAIL {what}" + (f"  ← {detail}" if detail else ""))


def read(path):
    return io.open(path, encoding="utf-8").read()


def main():
    adj, bar, wrap, tpl = read(ADJ), read(BAR), read(WRAP), read(TPL)
    dialog, page, chartpy = read(DIALOG), read(TECHPAGE), read(CHARTPY)

    print("\n[۱] نوعِ سری فقط دو مقدار دارد")
    m = re.search(r"export type AdjustmentMode = ([^;]+);", adj)
    ck(m is not None, "تعریفِ AdjustmentMode درِ adjustments.ts پیدا شد", "")
    union = m.group(1) if m else ""
    ck("'none'" in union and "'combined'" in union and union.count("|") == 1,
       "یونیون دقیقاً `none | combined` است", union)

    print("\n[۲] حالت‌هایِ حذف‌شده درِ مسیرِ شمارشِ قیمت زنده نیستند")
    for dead in ("toIndexedSeries", "PERFORMANCE_BASE", "pricePrecisionFor"):
        ck(dead not in adj, f"`{dead}` از موتورِ تعدیل بیرون رفت", "")
    ck("mode === 'performance'" not in adj and "mode === 'performance'" not in wrap,
       "هیچ شاخه‌ای درِ lib یا wrapper حالتِ سوم را دوباره فعال نمی‌کند", "")
    ck("'capital'" not in bar and "'cash'" not in bar,
       "دو گزینهٔ بی‌داده درِ نوارِ ابزار نیستند", "")
    ck("nn-disabled" not in bar,
       "کرکره دیگر گزینهٔ «غیرفعال» نمی‌سازد (بی‌حالتِ تزئینی)", "")

    print("\n[۳] رابط دقیقاً دو انتخاب دارد — شمارش از خودِ سورس، نه عددِ ثابت")
    block = bar[bar.index("const adjustments"):bar.index("const currentAdj")]
    opts = re.findall(r"value: '([a-z]+)'", block)
    ck(len(opts) == 2, "فهرستِ کرکرۀِ تعدیل دو گزینه دارد", str(opts))
    ck(sorted(opts) == ["combined", "none"], "همان دو مقدارِ یونیون، بی‌سومی", str(opts))
    ck("AVAILABLE_MODES" not in bar,
       "دروازۀِ «available» لازم نیست: هرچه درِ فهرست است واقعی است", "")

    print("\n[۴] برچسب با داده می‌خواند (نه ادعایِ جدا)")
    ck("خام" in bar and "عملکردی" in bar, "دو برچسب: خام و عملکردی", "")
    ck("DPS" in bar,
       "توضیحِ حالتِ عملکردی می‌گوید سودِ نقدی سرمایه‌گذاریِ دوباره نمی‌شود", "")
    ck("DEFAULT_ADJUSTMENT_MODE: AdjustmentMode = 'combined'" in adj,
       "پیش‌فرض = سریِ ریالیِ تعدیل‌شده (رأیِ #186)", "")
    ck("FFC_ADJUSTMENT_MODE: AdjustmentMode = 'combined'" in adj and
       "FFC_ADJUSTMENT_MODE" in page,
       "موتورِ دوم از همان ثابتِ یکِ منبع می‌خواند", "")

    print("\n[۵] کوچکتِ کنترل‌شده، درِ یکِ نقطه")
    ck("export function migrateAdjustmentMode" in adj,
       "کوچکت درِ adjustments.ts تعریف شده", "")
    ck("migrateAdjustmentMode" in wrap,
       "اعمالِ قالب از همان کوچکت می‌گذرد", "")
    for legacy in ("performance", "capital", "cash"):
        ck(f"{legacy}: 'combined'" in adj, f"«{legacy}» کهنه به combined می‌نشیند", "")
    ck("LEGACY_ADJUSTMENTS" not in tpl and "saneAdjustment" not in tpl,
       "storeِ نقشۀِ دوم نمی‌سازد (واگراییِ دو‌نقطه‌ای همین‌جا متولد می‌شد)", "")

    print("\n[۶] چیزهایی که حذف نشده‌اند (رأیِ مالک: این‌ها بمانند)")
    for scale in ("'normal'", "'logarithm'", "'percentage'"):
        ck(scale in wrap and scale in dialog, f"مقیاسِ {scale} درِ wrapper و تنظیمات هست", "")
    ck("view.pricePrecision" in dialog and "setView({ pricePrecision: p })" in dialog,
       "اعشارِ صریحِ کاربر درِ تنظیمات خوانده و نوشته می‌شود (بر 'auto' مقدم است)", "")
    ck("createScaleLock" in wrap,
       "قفلِ مقیاسِ اصلاح‌شدۀِ دورِ پیشین سرِ جایش است", "")

    print("\n[۷] بک‌اند هیچ حالتِ سومی اعلام نمی‌کند")
    ck('"indexed_available"' not in chartpy,
       "ادعایِ سخت‌کدشدۀِ حالتِ شاخص از پاسخ بیرون رفت", "")
    ck('"combined_available": source in _ADJ_KNOWN_SOURCES' in chartpy,
       "combined از منبعِ داوری‌شدۀِ همان نماد حساب می‌شود", "")
    ck('"functional_available": available' in chartpy,
       "functional از قاعدۀِ محاسبه‌شده می‌آید، نه از ثابت", "")
    ck("adjustment: int = 3" not in chartpy and '"adjustment": adjustment' not in chartpy,
       "دستکۀِ بی‌مسیرِ /api/chart-db حذف شد", "")
    ck("def get_chart_db(symbol: str)" in chartpy,
       "امضایِ /api/chart-db فقط نماد می‌گیرد", "")

    print(f"\nprice_series_modes_v1: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
