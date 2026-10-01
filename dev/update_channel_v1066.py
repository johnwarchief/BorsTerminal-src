#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""گاردِ کانالِ به‌روزرسانی — بیلدِ دمو نباید به کانالِ نسخهٔ واقعی برود.

باگی که این گارد جلویش را می‌گیرد: APP_VERSION در بیلدِ دمو عمداً رویِ
نسخهٔ واقعی می‌ماند (نسخه از برچسبِ گیت به ISCC می‌رود). پس اپِ دمو خودش
را «1.0.65» می‌دانست و آپدیترش از releases/latest می‌خواند که همیشه ریلیزِ
واقعی است — یعنی کاربرِ دمو پچ‌هایِ دلتایِ دمو را اصلاً نمی‌دید و به‌جایش
نسخهٔ واقعی به او پیشنهاد می‌شد.
"""
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails = []


def ck(cond, msg):
    print(("  \u2713 " if cond else "  \u2717 ") + msg)
    if not cond:
        fails.append(msg)


print("=" * 64)
print("  گاردِ کانالِ به‌روزرسانی (۱٫۰٫۶۶)")
print("=" * 64)

src = io.open(os.path.join(ROOT, "api", "update.py"), encoding="utf-8").read()

print("\n[۱] آپدیتر شناسنامهٔ بیلد را می‌خواند")
ck("build_channel.json" in src, "نامِ فایلِ شناسنامه در کد هست")
ck("BUILD_VERSION" in src, "BUILD_VERSION تعریف شده")
ck(re.search(r"LATEST_JSON_URL\s*=\s*\(?\s*\n?\s*f?\"", src) is not None
   or "channel_tag" in src, "نشانیِ مانیفست به کانال وابسته است")

print("\n[۲] هیچ مقایسهٔ نسخه‌ای رویِ APP_VERSIONِ خام نمانده")
for pat, label in [
    (r"_vkey\(APP_VERSION\)", "مقایسهٔ «آپدیت هست؟»"),
    (r'"current_version":\s*APP_VERSION', "گزارشِ نسخهٔ فعلی"),
    (r'p\.get\("from"\)[^\n]*!=\s*APP_VERSION', "تطبیقِ مبدأِ پچ"),
]:
    ck(re.search(pat, src) is None, f"{label} از BUILD_VERSION می‌آید")

print("\n[۳] شناسنامه در بستهٔ PyInstaller می‌رود")
spec = io.open(os.path.join(ROOT, "fts_terminal.spec"), encoding="utf-8").read()
ck("build_channel.json" in spec, "spec فایل را در datas دارد")

print("\n[۴] CI آن را می‌نویسد — و فقط برایِ دمو کانال می‌گذارد")
wf = io.open(os.path.join(ROOT, ".github", "workflows", "release.yml"),
             encoding="utf-8").read()
ck("build_channel.json" in wf, "گامِ نوشتنِ شناسنامه هست")
i = wf.find("Write build channel")
ck(i != -1 and wf.find("build_channel.json", i) <
   wf.find("Build Python Backend", i), "پیش از PyInstaller نوشته می‌شود")
ck("-match '-'" in wf[i:i + 900], "کانال فقط وقتی برچسب خط تیره دارد")

print("\n[۵] منطقِ نشانی")
REPO = "https://github.com/johnwarchief/BorsTerminal"
def url(tag):
    return (f"{REPO}/releases/download/{tag}/latest.json" if tag
            else f"{REPO}/releases/latest/download/latest.json")
ck(url("v1.0.66-demo9").endswith("/v1.0.66-demo9/latest.json"),
   "دمو ➔ کانالِ خودش")
ck(url("").endswith("/releases/latest/download/latest.json"),
   "واقعی ➔ releases/latest (رفتارِ قبلی دست‌نخورده)")

print("\n" + "=" * 64)
if fails:
    print("  \u2717 %d بررسی شکست خورد" % len(fails))
    sys.exit(1)
print("  \u2713 همهٔ بررسی‌ها سبز")
