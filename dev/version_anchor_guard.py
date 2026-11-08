#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/version_anchor_guard.py -- همهٔ لنگه‌هایِ نسخه باید یک عدد باشند.

چرا: نسخه در لنگه‌های کلیدی تولید نوشته می‌شود:
  - هدف فرانت‌اند مدرن: frontend-v2/package.json و package-lock.json
  - بک‌اند Go تولیدکننده: backend-go/cmd/bors-producer/main.go
  - پوسته دسکتاپ Tauri: tauri.conf.json و Cargo.toml
  - بسته نصب‌کننده Inno Setup: installer/bors_setup.iss
  - سازگاری بک‌اند پایتون و فرانت‌اند پیشین: bors_config.py و frontend/package.json

اگر هر کدام از این لنگه‌ها ناهمگام شوند، بسته نصبی، پوسته دسکتاپ یا کلاینت
نسخه ناسازگار می‌بینند و فرآیند همگام‌سازی و آپدیت دچار اختلال می‌شود.

خروج: کد ۰ اگر همه یکسان، ۱ در غیر این صورت.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_file(root_dir, path):
    full_path = os.path.join(root_dir, path)
    if not os.path.isfile(full_path):
        return None
    with open(full_path, encoding="utf-8") as f:
        return f.read()


def collect_anchors(root_dir):
    anchors = []

    def find(label, value):
        anchors.append((label, value))

    # 1. bors_config.py
    cfg_content = read_file(root_dir, "bors_config.py")
    if cfg_content:
        m = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', cfg_content, re.M)
        find("bors_config.APP_VERSION", m.group(1) if m else None)
    else:
        find("bors_config.APP_VERSION", None)

    # 2. Target Frontend-V2: package.json and lockfile
    v2_pkg_raw = read_file(root_dir, os.path.join("frontend-v2", "package.json"))
    if v2_pkg_raw:
        try:
            v2_pkg = json.loads(v2_pkg_raw)
            find("frontend-v2/package.json", v2_pkg.get("version"))
        except Exception:
            find("frontend-v2/package.json", None)
    else:
        find("frontend-v2/package.json", None)

    v2_lock_raw = read_file(root_dir, os.path.join("frontend-v2", "package-lock.json"))
    if v2_lock_raw:
        try:
            v2_lock = json.loads(v2_lock_raw)
            find("frontend-v2/package-lock.json#version", v2_lock.get("version"))
            find("frontend-v2/package-lock.json#packages[\"\"]", (v2_lock.get("packages") or {}).get("", {}).get("version"))
        except Exception:
            find("frontend-v2/package-lock.json#version", None)
            find("frontend-v2/package-lock.json#packages[\"\"]", None)
    else:
        find("frontend-v2/package-lock.json#version", None)
        find("frontend-v2/package-lock.json#packages[\"\"]", None)

    # 3. Backend Go: bors-producer main.go
    go_main_raw = read_file(root_dir, os.path.join("backend-go", "cmd", "bors-producer", "main.go"))
    if go_main_raw:
        m = re.search(r'var\s+version\s*=\s*"([^"]+)"', go_main_raw)
        find("backend-go/cmd/bors-producer/main.go", m.group(1) if m else None)
    else:
        find("backend-go/cmd/bors-producer/main.go", None)

    # 4. Tauri Desktop Shell: tauri.conf.json and Cargo.toml
    tauri_raw = read_file(root_dir, os.path.join("frontend", "src-tauri", "tauri.conf.json"))
    if tauri_raw:
        try:
            tauri = json.loads(tauri_raw)
            find("src-tauri/tauri.conf.json", tauri.get("version"))
        except Exception:
            find("src-tauri/tauri.conf.json", None)
    else:
        find("src-tauri/tauri.conf.json", None)

    cargo_raw = read_file(root_dir, os.path.join("frontend", "src-tauri", "Cargo.toml"))
    if cargo_raw:
        m = re.search(r'^version\s*=\s*"([^"]+)"', cargo_raw, re.M)
        find("src-tauri/Cargo.toml", m.group(1) if m else None)
    else:
        find("src-tauri/Cargo.toml", None)

    # 5. Inno Setup installer script
    iss_raw = read_file(root_dir, os.path.join("installer", "bors_setup.iss"))
    if iss_raw:
        m = re.search(r'#define\s+AppVersion\s+"([^"]+)"', iss_raw)
        find("installer/bors_setup.iss AppVersion", m.group(1) if m else None)
    else:
        find("installer/bors_setup.iss AppVersion", None)

    # 6. Legacy frontend (fallback UI)
    pkg_raw = read_file(root_dir, os.path.join("frontend", "package.json"))
    if pkg_raw:
        try:
            pkg = json.loads(pkg_raw)
            find("frontend/package.json", pkg.get("version"))
        except Exception:
            find("frontend/package.json", None)
    else:
        find("frontend/package.json", None)

    lock_raw = read_file(root_dir, os.path.join("frontend", "package-lock.json"))
    if lock_raw:
        try:
            lock = json.loads(lock_raw)
            find("package-lock.json#version", lock.get("version"))
            find("package-lock.json#packages[\"\"]", (lock.get("packages") or {}).get("", {}).get("version"))
        except Exception:
            find("package-lock.json#version", None)
            find("package-lock.json#packages[\"\"]", None)
    else:
        find("package-lock.json#version", None)
        find("package-lock.json#packages[\"\"]", None)

    return anchors


def evaluate_anchors(anchors, verbose=True):
    failed = 0
    values = {label: val for label, val in anchors}
    missing = [label for label, val in values.items() if not val]
    if missing:
        failed += len(missing)
        if verbose:
            for label in missing:
                print(f"  FAIL {label}: لنگهٔ نسخه پیدا نشد یا فایل مفقود است")

    distinct = {val for val in values.values() if val}
    if len(distinct) > 1:
        failed += 1
        if verbose:
            print("  FAIL لنگه‌ها یکسان نیستند:")
            for label, val in values.items():
                print(f"    {label} = {val}")
    else:
        version = distinct.pop() if distinct else "?"
        if verbose:
            print(f"  PASS هر {len(values)} لنگه روی {version}")
            for label, val in values.items():
                print(f"    ok  {label} = {val}")

    if verbose:
        print(f"\n{len(values)} checks, {failed} failed")
        print("VERSION ANCHOR GUARD " + ("OK" if failed == 0 else "FAILED"))

    return 1 if failed else 0


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    target_root = ROOT
    for arg in sys.argv[1:]:
        if arg.startswith("--root="):
            target_root = arg.split("=", 1)[1]

    anchors = collect_anchors(target_root)
    return evaluate_anchors(anchors, verbose=True)


if __name__ == "__main__":
    sys.exit(main())
