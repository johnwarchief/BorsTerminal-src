#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""پیش‌چکِ مفسرِ بیلد: آیا هر dependencyِ declared واقعاً import می‌شود؟

ریشه: بیلدِ محلی با پایتونِ ۳.۱۴ِ بدونِ pywebview، EXEیِ کاملاً سالم تولید
کرد — فقط پنجرهٔ بومی ناپدید شده بود و bors_entry بی‌صدا به msedge --app
برمی‌گشت. نه تستی قرمز شد، نه بیلدی شکست. چکِ پسازبیلد (onedir_contract)
همین را می‌گیرد، اما دو دقیقه دیر؛ این اسکریپت قبلِ شروعِ PyInstaller
می‌گوید کدام پکیج در همین مفسر نیست.

خروجی: ۰ = همه‌چیز هست؛ ۱ = کم دارد (با نامِ مفسر و لیستِ گمشده‌ها).
"""
import importlib.util
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# نامِ پکیج در requirements.txt  ->  نامِ ماژولِ importشونده
PROBES = [
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("requests", "requests"),
    ("httpx", "httpx"),
    ("numpy", "numpy"),
    ("pandas", "pandas"),
    ("orjson", "orjson"),
    # پنجرهٔ بومی (WebView2). نبودِ pywebview اپ را نمی‌خواباند، فقط
    # پنجره را از دست می‌دهد — و همین باعث شد ماه‌ها ناشناسه بماند.
    ("pywebview", "webview"),
    ("pythonnet", "pythonnet"),
    ("pyinstaller", "PyInstaller"),
]
# app.py در نبودش به JSONResponse استاندارد برمی‌گردد، پس ریلیز نمی‌شکند.
OPTIONAL = {"orjson"}


def main():
    missing = [(pkg, mod) for pkg, mod in PROBES
               if importlib.util.find_spec(mod) is None]
    present = [mod for pkg, mod in PROBES if (pkg, mod) not in missing]

    print("[build-env] interpreter: %s" % sys.executable)
    print("[build-env] python     : %s" % sys.version.split()[0])
    if not missing:
        print("[build-env] OK — %d importable modules: %s"
              % (len(present), ", ".join(sorted(present))))
        return 0

    hard = [(p, m) for p, m in missing if p not in OPTIONAL]
    soft = [(p, m) for p, m in missing if p in OPTIONAL]
    for pkg, mod in hard:
        print("[build-env] [MISSING] %s  (import %s)" % (pkg, mod))
    for pkg, mod in soft:
        print("[build-env] [optional] %s  (import %s)" % (pkg, mod))
    if not hard:
        print("[build-env] OK — only optional modules are absent")
        return 0
    print("")
    print("[build-env] This interpreter cannot produce the intended bundle.")
    print("[build-env]   %s -m pip install -r %s"
          % (sys.executable, os.path.join(_ROOT, "requirements.txt")))
    print("[build-env] CI uses python 3.12 + requirements.txt; a local build")
    print("[build-env] with a different interpreter ships a degraded EXE.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
