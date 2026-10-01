#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/chart_single_bundle_v1038.py — چارتِ یکتا: هر متد باید در باندلِ خودش باشد.

چرا این گارد هست: تا نسخهٔ ۱.۰.۳۷ برنامه KLineCharts را از **دو** مسیر می‌گرفت —
  ۱) `public/vendor/klinecharts.min.js` که با <script> روی `window.klinecharts`
     می‌نشست (مصرف‌کننده: رپرِ قدیمیِ features/technical/components)،
  ۲) پکیجِ npm که Vite باندل می‌کرد (مصرف‌کننده: رپرِ نهایات‌نگر).
در باندلِ npm متد `getCrosshair` روی **Store** است نه روی Chart؛ در باندلِ
وندورشده روی خودِ Chart. یعنی `chart.getCrosshair()` در یکی کار می‌کرد و در
دیگری با «is not a function» می‌شکست — و `npm run build` که اصلاً tsc ندارد،
این را نمی‌گرفت. خط‌کشِ نمودار دقیقاً همین را صدا می‌زد و کرش می‌کرد.

در ENGINE-1 باندلِ دوم از برنامه بیرون رفت، پس این گارد سه چیز را ثابت می‌کند:
  * باندلِ دوم **برنگردد**: نه فایلِ vendor، نه <script> آن در index.html، نه
    هیچ ارجاعی به `window.klinecharts` در src (دو باندل = بازگشت همان باگ);
  * واقعیتِ باندلِ npm (هر چه روی Chart‌اش هست، و اینکه getCrosshair روی
    Store است) — این‌ها پایهٔ داوری‌های پایین‌اند، نه حدس;
  * هر متدی که کدِ زنده روی *نمونۀِ چارت* صدا می‌زند در باندلِ خودش وجود دارد,
    و کمکیِ readCrosshair بی‌throw به null می‌رسد.

اگر node_modules در محیط نبود (شغلِ pythonِ CI هیچ npm ci ندارد) با پیام SKIP
رد می‌شود — گارد نباید به چیزی که CI ندارد وابسته باشد.

اجرا:  python dev/chart_single_bundle_v1038.py
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
INDEX_HTML = os.path.join(FE, "index.html")
SRC = os.path.join(FE, "src")

# تنها مصرف‌کننده‌های مجازِ APIِ چارت: رپرِ زنده و آداپترِ موتور.
CHART_FILES = [
    os.path.join("src", "features", "technical", "nahayatnegar", "components",
                 "KLineChartWrapper.tsx"),
    os.path.join("src", "features", "technical", "engine", "klinecharts",
                 "KLineChartsEngine.ts"),
]
# موتورِ دومی که در registry هست ولی در برنامه روشن نمی‌شود (لاب experiments):
LAB_ONLY_ENGINE = "ffc"

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
    """کامنت‌ها حذف می‌شوند — وگرنه توضیحِ خودِ باگ، مثلِ صدازدنِ باگ گزارش می‌شود."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", "", src)


def proto_methods(bundle, cls):
    return {m.group(1) for m in re.finditer(
        re.escape(cls) + r"\.prototype\.(\w+)\s*=", bundle)}


def class_holding(bundle, meth):
    return {m.group(1) for m in re.finditer(
        r"([A-Za-z_$][\w$]*)\.prototype\.%s\s*=" % meth, bundle)}


def ts_files():
    out = []
    for root, dirs, names in os.walk(SRC):
        dirs[:] = [d for d in dirs if d not in ("__tests__", "node_modules")]
        for n in names:
            if n.endswith((".ts", ".tsx")):
                p = os.path.join(root, n)
                out.append((os.path.relpath(p, FE).replace("\\", "/"), p))
    return out


def main():
    # ── ۱) چارتِ یکتا: باندلِ دوم نباید برگردد ────────────────────────────
    ck(not os.path.isfile(VENDOR_BUNDLE),
       "no second klinecharts bundle in public/vendor", VENDOR_BUNDLE)
    html = read(INDEX_HTML) if os.path.isfile(INDEX_HTML) else ""
    ck("klinecharts.min.js" not in html,
       "index.html loads no vendored klinecharts <script>")
    hits = []
    for rel, p in ts_files():
        body = code_only(read(p))
        # شکل‌هایِ واقعیِ خطر: `window.klinecharts` و `(window as any).klinecharts`
        # و `window['klinecharts']` — همان‌ها که باندلِ دوم را برمی‌گردانند.
        if re.search(r"window\b[^\n]{0,40}?\bklinecharts\b", body):
            hits.append(rel)
    ck(not hits, "no window.klinecharts fallback left in src (code only, comments stripped)",
       str(hits[:4]))

    if not os.path.isfile(NPM_BUNDLE):
        print("SKIP: باندلِ npm نیست — گاردِ متدها فقط روی ماشینِ توسعه اجرا می‌شود")
        print("chart_single_bundle_v1038: %d passed, %d failed (rest skipped)" % (PASS, FAIL))
        return 1 if FAIL else 0

    npm = read(NPM_BUNDLE)

    # ── ۲) واقعیتِ باندلِ npm (پایۀِ داوری‌ها) ────────────────────────────
    ck("ChartImp" in npm, "npm bundle exposes a ChartImp class to introspect")
    chart_m = proto_methods(npm, "ChartImp")
    ck(len(chart_m) > 40, "npm ChartImp has a real method surface", "n=%d" % len(chart_m))
    ck("getChartStore" in chart_m, "npm Chart has getChartStore (our only path to the store)")
    ck("getCrosshair" not in chart_m,
       "npm Chart does NOT have getCrosshair — the assumption the fix rests on")
    store_owner = class_holding(npm, "getCrosshair")
    ck(bool(store_owner) and "ChartImp" not in store_owner,
       "in the npm bundle getCrosshair lives on the store class", str(store_owner))

    # ── ۳) کدِ زنده: هر متدی که روی چارت صدا می‌زند در باندل باشد ─────────
    called_all, bad_direct, unknown = set(), [], set()
    for rel in CHART_FILES:
        path = os.path.join(FE, rel)
        ck(os.path.isfile(path), "chart file still exists", rel)
        if not os.path.isfile(path):
            continue
        src = code_only(read(path))
        if "nahayatnegar" in rel:
            ck("from 'klinecharts'" in src, "the نهایات‌نگر wrapper is npm-importing", rel)
            ck("readCrosshair(" in src, "the wrapper reads the crosshair through the helper", rel)
            helper = src[src.find("function readCrosshair"):src.find("function readCrosshair") + 900]
            ck("?.()" in helper and "?? null" in helper,
               "readCrosshair degrades to null (no throw, no fake number)", rel)
        bad_direct += [(rel, m.group(0)) for m in re.finditer(
            r"(?:chartRef\.current|chart|ch|this\.chart)\s*\??\.\s*(%s)\s*\(" % "|".join(STORE_ONLY), src)]
        called = set(re.findall(r"(?:chartRef\.current|this\.chart)\s*\??\.\s*(\w+)\s*\(", src))
        called_all |= called
        unknown |= {c for c in called if c not in chart_m}
    ck(not bad_direct, "no store-only method is called directly on a Chart", str(bad_direct[:3]))
    ck(not unknown, "every chart method the live code calls exists on the npm Chart class",
       str(sorted(unknown)))

    # ── ۴) رجیستری: پیش‌فرض KLineCharts می‌ماند و هیچ موتوری ایستا وارد نمی‌شود ─
    # تا v1.0.65 این شاخه «دقیقاً یک موتورِ production» را می‌سنجید، چون FFC فقط
    # در لاب بود. مالک خواست FFC «به‌عنوان یک موتورِ دیگر» در تب تکنیکال باشد، پس
    # دوتا production شد؛ چیزی که واقعاً باید ثابت بماند همین دو است:
    #   · DEFAULT_ENGINE still klinecharts (هیچ انتخابِ پیش‌فرضی جابه‌جا نشود)
    #   · هر دو create پویا باشند (importِ ایستا یعنی نشتِ باندلِ یک موتور به
    #     چانکِ دیگری — همان باگِ دو-باندلیِ ۱٫۰٫۳۷ در لباسِ تازه)
    reg = os.path.join(FE, "src", "features", "technical", "engine", "registry.ts")
    if os.path.isfile(reg):
        body = read(reg)
        prod = re.findall(r"production:\s*(true|false)", body)
        ck(prod.count("true") >= 1, "the registry has at least one production engine", str(prod))
        ck("import { KLineChartsEngine }" not in body and "import { FastFinancialChartsEngine }" not in body,
           "no engine is imported statically into the registry", "static import")
        ck(body.count("await import(") >= 2, "both engines load lazily", str(body.count("await import(")))
        ck("DEFAULT_ENGINE: ChartEngineId = 'klinecharts'" in body,
           "the default engine is KLineCharts")
        ck("id: '%s'" % LAB_ONLY_ENGINE in body,
           "the second engine stays registered (the lab needs it)", LAB_ONLY_ENGINE)
    else:
        ck(False, "engine registry exists", reg)

    print("chart_single_bundle_v1038: %d passed, %d failed "
          "(npm Chart methods=%d, called=%d)" % (PASS, FAIL, len(chart_m), len(called_all)))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
