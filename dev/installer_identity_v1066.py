#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""گاردِ هویتِ نصب‌کننده — بیلدِ واقعی باید دقیقاً همان هویتِ قبلی را بدهد،
و بیلدِ دمو باید کاملاً جدا باشد.

چرا این گارد لازم است: `installer/bors_setup.iss` حالا `#ifdef Demo` دارد و
`AppId`/`AppRegID` به‌جایِ عددِ دستی از `AppGuid` مشتق می‌شوند. اگر کسی روزی
این اشتقاق را خراب کند، `AppId`ِ بیلدِ واقعی عوض می‌شود و آن‌وقت نصبِ بعدی
رویِ نصبِ فعلیِ کاربران **نمی‌نشیند**: Inno آن را برنامه‌ای تازه می‌بیند، دو
نسخه کنارِ هم می‌مانند، کلیدِ Uninstall دوتا می‌شود و آپدیترِ درون‌برنامه‌ای
(که در api/update.py با همین GUID دنبالِ مسیرِ نصب می‌گردد) کور می‌شود.
چنین خرابی‌ای در CI دیده نمی‌شود چون ISCC فقط رویِ ویندوز اجرا می‌شود و
خروجی‌اش هم کامپایل می‌گیرد — فقط سرِ کاربر خراب می‌شود.

پس اینجا پیش‌پردازندهٔ Inno را در حدِ همین چند دستور شبیه‌سازی می‌کنیم و
مقدارهایِ نهایی را با مقدارهایِ تثبیت‌شده می‌سنجیم.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISS = os.path.join(ROOT, "installer", "bors_setup.iss")

# هویتِ تاریخیِ نسخهٔ واقعی — این دو رشته قفل‌اند. عوض‌کردنشان یعنی شکستنِ
# ارتقاء برایِ هر کسی که امروز برنامه را نصب دارد.
REAL_APPID = "{8F3A2E7C-1B44-4C2E-9A77-0B0B5C0DE001}"
REAL_REGID = "{8F3A2E7C-1B44-4C2E-9A77-0B0B5C0DE001}_is1"
REAL_NAME = "BorsTerminal Ultimate"
# همان GUID در api/update.py هم hard-code شده؛ باید یکی بماند.
UPDATE_PY = os.path.join(ROOT, "api", "update.py")

fails = []


def check(cond, msg):
    if cond:
        print("  \u2713 " + msg)
    else:
        print("  \u2717 " + msg)
        fails.append(msg)


def evaluate(demo, appversion="1.0.65"):
    """شبیه‌سازیِ #ifdef/#define/#ifndef در حدِ چیزی که این فایل به‌کار می‌برد."""
    src = open(ISS, encoding="utf-8-sig", errors="surrogateescape").read()
    defs = {"AppVersion": appversion}
    if demo:
        defs["Demo"] = "1"
    active = [True]
    out = {}
    for raw in src.splitlines():
        line = raw.strip()
        m = re.match(r'#if\s+Pos\("-",\s*AppVersion\)\s*>\s*0', line)
        if m:
            active.append(active[-1] and "-" in defs.get("AppVersion", ""))
            continue
        if line.startswith("#ifdef "):
            active.append(active[-1] and line.split(None, 1)[1].strip() in defs)
            continue
        if line.startswith("#ifndef "):
            active.append(active[-1] and line.split(None, 1)[1].strip() not in defs)
            continue
        if line == "#else":
            # فقط یک سطح تودرتو در این فایل هست
            active[-1] = active[-2] and not active[-1]
            continue
        if line == "#endif":
            active.pop()
            continue
        if not active[-1]:
            continue
        # #define NumericVersion Copy(AppVersion, 1, Pos("-", AppVersion) - 1)
        m2 = re.match(
            r'#define\s+(\w+)\s+Copy\(AppVersion,\s*1,\s*Pos\("-",\s*AppVersion\)\s*-\s*1\)',
            line)
        if m2:
            defs[m2.group(1)] = defs.get("AppVersion", "").split("-", 1)[0]
            continue
        m = re.match(r'#define\s+(\w+)\s+(.+)$', line)
        if m:
            name, expr = m.group(1), m.group(2).strip()
            # الحاقِ رشته‌ها: "x" + Name + "y"
            val = ""
            for part in expr.split("+"):
                part = part.strip()
                if len(part) >= 2 and part[0] == '"' and part[-1] == '"':
                    val += part[1:-1]
                elif part in defs:
                    val += defs[part]
                else:
                    val = None
                    break
            if val is not None:
                defs[name] = val
            continue
        m = re.match(r'(AppId|OutputBaseFilename|AppName|VersionInfoVersion|VersionInfoTextVersion)=(.*)$', line)
        if m and m.group(1) not in out:
            v = m.group(2)
            # جانشینیِ {#Name}
            v = re.sub(r'\{#(\w+)\}', lambda g: defs.get(g.group(1), g.group(0)), v)
            # «{{» در Inno یعنی یک «{» تحت‌اللفظی
            out[m.group(1)] = v.replace("{{", "{")
    out["AppRegID"] = defs.get("AppRegID", "")
    out["_AppName"] = defs.get("AppName", "")
    return out


print("=" * 66)
print("  گاردِ هویتِ نصب‌کننده (۱٫۰٫۶۶)")
print("=" * 66)

if not os.path.exists(ISS):
    print("SKIP: installer/bors_setup.iss نیست")
    sys.exit(0)

print("\n[۱] بیلدِ واقعی — هویت باید دست‌نخورده بماند")
real = evaluate(demo=False)
check(real.get("AppId") == REAL_APPID,
      "AppId همان GUIDِ تاریخی است  (%s)" % real.get("AppId"))
check(real.get("AppRegID") == REAL_REGID,
      "AppRegID همان کلیدِ Uninstall است  (%s)" % real.get("AppRegID"))
check(real.get("_AppName") == REAL_NAME,
      "AppName همان «%s» است" % real.get("_AppName"))

print("\n[۲] بیلدِ دمو — باید کاملاً جدا باشد")
demo = evaluate(demo=True)
check(demo.get("AppId") and demo.get("AppId") != real.get("AppId"),
      "AppIdِ دمو فرق دارد  (%s)" % demo.get("AppId"))
check(demo.get("AppRegID") != real.get("AppRegID"),
      "کلیدِ Uninstallِ دمو فرق دارد → نصبِ واقعی را نمی‌بلعد")
check(demo.get("_AppName") != real.get("_AppName"),
      "AppNameِ دمو فرق دارد → پوشهٔ نصب هم جدا می‌شود  (%s)" % demo.get("_AppName"))
check(re.fullmatch(r"\{[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}\}",
                   demo.get("AppId") or ""),
      "GUIDِ دمو شکلِ درستِ GUID دارد")

print("\n[۳] نسخهٔ فایل — برچسبِ دمو نباید 0.0.0.0 بسازد")
d = evaluate(demo=True, appversion="1.0.66-demo")
r = evaluate(demo=False, appversion="1.0.66")
check(d.get("VersionInfoVersion") == "1.0.66",
      "VersionInfoVersionِ دمو بخشِ عددی را می‌گیرد  (1.0.66-demo \u2192 %s)"
      % d.get("VersionInfoVersion"))
check(d.get("VersionInfoTextVersion") == "1.0.66-demo",
      "متنِ نسخه هنوز کاملِ برچسب است  (%s)" % d.get("VersionInfoTextVersion"))
check(r.get("VersionInfoVersion") == "1.0.66",
      "نسخهٔ واقعی دست‌نخورده می‌ماند  (%s)" % r.get("VersionInfoVersion"))
check(d.get("OutputBaseFilename") == "BorsTerminal_Ultimate_Setup_v1.0.66-demo",
      "نامِ فایلِ ستاپ با برچسبِ گیت می‌خواند  (%s)" % d.get("OutputBaseFilename"))

print("\n[۴] همگامی با api/update.py")
if os.path.exists(UPDATE_PY):
    up = open(UPDATE_PY, encoding="utf-8").read()
    m = re.search(r'APP_ID\s*=\s*"(\{[^"]+\})"', up)
    check(bool(m) and m.group(1) == REAL_APPID,
          "APP_IDِ آپدیتر با AppIdِ نصب‌کننده یکی است")
else:
    print("  - api/update.py نیست، رد شد")

print("\n" + "=" * 66)
if fails:
    print("  \u2717 %d بررسی شکست خورد" % len(fails))
    sys.exit(1)
print("  \u2713 همهٔ بررسی‌ها سبز")
sys.exit(0)
