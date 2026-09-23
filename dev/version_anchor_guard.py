#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/version_anchor_guard.py -- همهٔ لنگه‌هایِ نسخه باید یک عدد باشند.

چرا: نسخه در شش جا نوشته می‌شود (بک‌اند، فرانت، قفلِ npm، پیکربندیِ Tauri،
اسکریپتِ Inno). اگر فقط بعضی‌شان bump شوند، آپدیت‌کنندهٔ درون‌برنامهای نسخه‌ای
را می‌بیند که با نصب‌کننده نمی‌خواند و یا بی‌صدا هیچ آپدیتی نمی‌دهد یا آپدیتِ
تکراری می‌فرستد. هیچ‌کدام در زمانِ بیلد کنترل نمی‌شد — این گارد همان است.

خروج: کد ۰ اگر همه یکسان، ۱ در غیر این صورت.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


def main():
    anchors = []

    def find(label, value):
        anchors.append((label, value))

    m = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', read("bors_config.py"), re.M)
    find("bors_config.APP_VERSION", m.group(1) if m else None)

    pkg = json.loads(read(os.path.join("frontend", "package.json")))
    find("frontend/package.json", pkg.get("version"))

    lock = json.loads(read(os.path.join("frontend", "package-lock.json")))
    find("package-lock.json#version", lock.get("version"))
    find("package-lock.json#packages[\"\"]", (lock.get("packages") or {}).get("", {}).get("version"))

    tauri = json.loads(read(os.path.join("frontend", "src-tauri", "tauri.conf.json")))
    find("src-tauri/tauri.conf.json", tauri.get("version"))

    iss = read(os.path.join("installer", "bors_setup.iss"))
    m = re.search(r'#define\s+AppVersion\s+"([^"]+)"', iss)
    find("installer/bors_setup.iss AppVersion", m.group(1) if m else None)

    failed = 0
    values = {label: val for label, val in anchors}
    missing = [label for label, val in values.items() if not val]
    if missing:
        failed += len(missing)
        for label in missing:
            print(f"  FAIL {label}: لنگهٔ نسخه پیدا نشد")

    distinct = {val for val in values.values() if val}
    if len(distinct) > 1:
        failed += 1
        print("  FAIL لنگه‌ها یکسان نیستند:")
        for label, val in values.items():
            print(f"    {label} = {val}")
    else:
        version = distinct.pop() if distinct else "?"
        print(f"  PASS هر {len(values)} لنگه روی {version}")
        for label, val in values.items():
            print(f"    ok  {label} = {val}")

    print(f"\n{len(values)} checks, {failed} failed")
    print("VERSION ANCHOR GUARD " + ("OK" if failed == 0 else "FAILED"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
