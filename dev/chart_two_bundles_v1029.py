#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/chart_two_bundles_v1029.py — دو چارت، دو API: چیزی که صدا می‌زنیم باید در باندلِ خودش باشد.

چرا: این برنامه KLineCharts را از **دو** مسیر متفاوت می‌گیرد —
  ۱) `public/vendor/klinecharts.min.js` که با <script> روی `window.klinecharts`
     می‌نشیند و تایپش `src/vendor/klinecharts.d.ts` است
     (مصرف‌کننده: features/technical/components/KLineChartWrapper.tsx);
  ۲) پکیجِ npm به نام `klinecharts` که Vite از node_modules باندل می‌کند
     (مصرف‌کننده: features/technical/nahayatnegar/components/KLineChartWrapper.tsx).
در باندلِ npm، `getCrosshair` روی **Store** تعریف شده نه روی Chart؛ در باندلِ
وندورشده روی خودِ Chart هست. یعنی `chart.getCrosshair()` در یکی کار می‌کند و
در دیگری با «is not a function» می‌شکند — و چون `npm run build` اصلاً tsc
نیست، این خطا در بیلدِ ریلیز هم گرفته نشد. خط‌کشِ نمودارِ نهایات‌نگر دقیقاً
همین را صدا می‌زد و با هر بارِ فشردنِ ابزار کرش می‌کرد (دو نقطهٔ فراخوان).

گارد چهار چیز را ثابت می‌کند تا این طبقه برنگردد:
  * واقعیتِ باندل‌ها (هر کدام Chart‌شان چه متدهایی دارد);
  * هیچ فایلِ npm-محور روی Chart متدِ مالِ Store را صدا نمی‌زند;
  * فایلِ وندور-محور بی‌مقدمه به npm دست نمی‌برد (مخلوط‌شدنِ دو API = بازگشت باگ);
  * کمکیِ readCrosshair هر دو شکل را می‌پذیرد و ته‌اش null است، نه throw.

اگر node_modules در محیط نبود (شغلِ pythonِ CI هیچ npm ci ندارد) با پیام SKIP
رد می‌شود — گارد نباید به چیزی که CI ندارد وابسته باشد.

اجرا:  python dev/chart_two_bundles_v1029.py
خروج: ۰ اگر همه درست، ۱ در غیر این صورت.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FE = os.path.join(ROOT, "frontend")
NPM_BUNDLE = os.path.join(FE, "node_modules", "klinecharts", "dist", "index.esm.js")
VENDOR_BUNDLE = os.path.join(FE, "public", "vendor", "klinecharts.min.js")
NPM_FILE = os.path.join("src", "features", "technical", "nahayatnegar",
                        "components", "KLineChartWrapper.tsx")
VENDOR_FILE = os.path.join("src", "features", "technical", "components",
                           "KLineChartWrapper.tsx")
VENDOR_DTS = os.path.join("src", "vendor", "klinecharts.d.ts")

# متدهایی که روی Store‌اند و از Chart قابلِ صدا زدن نیستند (باندلِ npm).
STORE_ONLY = ("getCrosshair", "setCrosshair", "getChart", "getWidget")
PASS = FAIL = 0


def ck(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("  FAIL  %s %s" % (label, extra))


def read(path):
    return io.open(path, encoding="utf-8", errors="replace").read()


def code_only(src):
    """کامنت‌ها حذف می‌شوند — وگرنه توضیحِ خودِ باگ، مثلِ صدازدنِ باگ گزارش می‌شود.

    (همین دلیلِ `strip_comments` در dev/chart_api_check_v95.py است.)
    """
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", "", src)


def proto_methods(bundle, cls):
    return {m.group(1) for m in re.finditer(
        re.escape(cls) + r"\.prototype\.(\w+)\s*=", bundle)}


def class_holding(bundle, meth):
    """کلاسِ (ممکن است مینیفای‌شده باشد) که متدِ موردنظر روی prototype‌اش است."""
    return {m.group(1) for m in re.finditer(r"([A-Za-z_$][\w$]*)\.prototype\.%s\s*=" % meth,
                                            bundle)}


def main():
    if not os.path.isfile(NPM_BUNDLE) or not os.path.isfile(VENDOR_BUNDLE):
        print("SKIP: باندل‌های klinecharts در این محیط نیستند — "
              "gardsِ frontend فقط رویِ ماشینِ توسعه با node_modules اجرا می‌شوند")
        print("chart_two_bundles_v1029: 0 passed, 0 failed (skipped)")
        return 0

    npm = read(NPM_BUNDLE)
    ven = read(VENDOR_BUNDLE)

    # ── ۱) واقعیتِ باندل‌ها ────────────────────────────────────────────────
    ck("ChartImp" in npm, "npm bundle exposes a ChartImp class to introspect")
    chart_m = proto_methods(npm, "ChartImp")
    ck(len(chart_m) > 40, "npm ChartImp has a real method surface", "n=%d" % len(chart_m))
    ck("getChartStore" in chart_m, "npm Chart has getChartStore (our only path to the store)")
    ck("getCrosshair" not in chart_m,
       "npm Chart does NOT have getCrosshair — the assumption the fix rests on")
    store_owner = class_holding(npm, "getCrosshair")
    ck(bool(store_owner) and "ChartImp" not in store_owner,
       "in the npm bundle getCrosshair lives on the store class", str(store_owner))

    # وندور: همان کلاسی که createIndicator دارد باید getCrosshair هم داشته باشد
    ind_cls = class_holding(ven, "createIndicator")
    cross_cls = class_holding(ven, "getCrosshair")
    ck(bool(ind_cls) and bool(cross_cls) and (ind_cls & cross_cls),
       "the vendored bundle really does put getCrosshair on the Chart class",
       "chart=%s crosshair=%s" % (sorted(ind_cls), sorted(cross_cls)))
    ck("getCrosshair: () => Crosshair | null;" in read(os.path.join(FE, VENDOR_DTS)),
       "the vendored .d.ts still declares getCrosshair for the window.klinecharts path")

    # ── ۲) کدِ npm-محور ───────────────────────────────────────────────────
    src = code_only(read(os.path.join(FE, NPM_FILE)))
    ck("from 'klinecharts'" in src, "the نهایات‌نگر wrapper is the npm-importing one")
    ck("readCrosshair(" in src and src.count("readCrosshair(chartRef.current)") >= 2,
       "both ruler call sites read the crosshair through the helper")
    bad = [m.group(0) for m in re.finditer(r"(?:chartRef\.current|chart|ch)\s*\??\.\s*(%s)\s*\("
                                           % "|".join(STORE_ONLY), src)]
    ck(not bad, "no store-only method is called directly on a Chart", str(bad[:3]))
    # هر متدی که روی «chart» صدا زده می‌شود باید روی ChartImp وجود داشته باشد
    called = set(re.findall(r"chartRef\.current\s*\?\.\s*(\w+)\s*\(", src))
    unknown = {c for c in called if c not in chart_m}
    ck(not unknown, "every chartRef method exists on the npm Chart class", str(sorted(unknown)))

    # ── ۳) کمکی نباید throw کند ───────────────────────────────────────────
    helper = src[src.find("function readCrosshair"):src.find("function readCrosshair") + 900]
    ck(bool(helper), "readCrosshair is defined in the file that uses it")
    ck("?.()" in helper and "?? null" in helper,
       "readCrosshair degrades to null (callers keep their last-candle fallback)")
    ck("getChartStore" in helper and "getCrosshair" in helper,
       "readCrosshair tries the store path and accepts a vendor-style Chart too")

    # ── ۴) مسیرِ وندور با npm قاطی نشود ───────────────────────────────────
    vs = read(os.path.join(FE, VENDOR_FILE))
    ck(not re.search(r"from ['\"]klinecharts['\"]", vs),
       "the window.klinecharts wrapper must not start importing the npm package",
       "mixing the two bundles is what produced the crash")
    ck("vendor/klinecharts" in vs, "the vendor wrapper keeps compiling against the vendor types")

    print("chart_two_bundles_v1029: %d passed, %d failed "
          "(npm Chart methods=%d, called=%d)" % (PASS, FAIL, len(chart_m), len(called)))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
