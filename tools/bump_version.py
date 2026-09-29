# -*- coding: utf-8 -*-
"""tools/bump_version.py — یک فرمان برایِ شش لنگرِ نسخه.

چرا این ابزار هست: نسخه در شش جا نوشته شده و دو تایِ آخرِ package-lock.json
همیشه جا می‌ماندند؛ گاردِ CI (dev/version_anchor_guard.py) به‌خاطرِ همین
یک‌بار ریلیز را قرمز کرد. این ابزار برایِ هر فایل «تعدادِ انتظارِ جایگزینی»
می‌خواهد و اگر هر لنگری پیدا نشد یا بیشتر از انتظار پیدا شد، بی‌آنکه چیزی
بنویسد می‌ایستد — یعنی نیمه‌بump نمی‌سازد.

    python tools/bump_version.py 1.0.54 1.0.55
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (path, regex, expected_matches, label)
ANCHORS = [
    ("bors_config.py", r'^APP_VERSION = "([0-9.]+)"$', 1, "bors_config.APP_VERSION"),
    ("frontend/package.json", r'^  "version": "([0-9.]+)",$', 1, "package.json"),
    # package-lock دو جا دارد: ریشه و packages[""] — هر دو با یک عدد.
    # برایِ packages[""] بی‌راه‌دیگران نمی‌توان به تورفتگی تکیه کرد (۴۳۶ سطرِ
    # "version" با شش فاصله در فایل هست); تنها بافتِ «کلیدِ خالی، بعد name،
    # بعد version» یکتاست.
    ("frontend/package-lock.json",
     r'"": \{\s*"name": "[^"]*",\s*"version": "([0-9.]+)"', 1, 'lock packages[""]'),
    ("frontend/package-lock.json", r'^  "version": "([0-9.]+)",$', 1, "lock root"),
    ("frontend/src-tauri/tauri.conf.json", r'^  "version": "([0-9.]+)",$', 1, "tauri.conf.json"),
    ("installer/bors_setup.iss", r'^#define AppVersion "([0-9.]+)"$', 1, "bors_setup.iss"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--no-guard", action="store_true")
    a = ap.parse_args()
    for v in (a.old, a.new):
        if not re.match(r"^\d+\.\d+\.\d+$", v):
            raise SystemExit(f"not x.y.z: {v}")

    # پیش‌خوانیِ کامل: اول همهٔ لنگرها را ببین، بعد بنویس. اگر یک لنگر جا
    # افتاده باشد، هیچ فایلی دست نخورده باید مانده باشد.
    #
    # دو لنگر در یک فایل (package-lock) باید رویِ *یک* متنِ مشترک اعمال شوند؛
    # نسخهٔ اولِ این ابزار هر لنگر را از متنِ اولیه حساب می‌کرد و دوباره می‌نوشت،
    # پس جایگزینیِ دوم جای اولی را می‌پاک می‌کرد و ریلیز با یک لنگرِ کهنه می‌ماند
    # — همان شکلی که گاردِ CI قرمز می‌کند.
    by_file: dict[str, list] = {}
    for rel, pat, want, label in ANCHORS:
        path = os.path.join(ROOT, rel)
        with open(path, encoding="utf-8", newline="") as fh:
            text = fh.read()
        hits = [m for m in re.finditer(pat, text, re.M)]
        found = [m.group(1) for m in hits]
        if len(hits) != want:
            raise SystemExit(f"{label}: expected {want} anchor, found {len(hits)} "
                             f"in {rel} — pattern drifted, nothing written")
        if any(v not in (a.old, a.new) for v in found):
            raise SystemExit(f"{label}: values {found} not in {{{a.old},{a.new}}} "
                             f"in {rel} — nothing written")
        by_file.setdefault(path, []).append((rel, text, pat, label, want))

    done = 0
    for path, entries in by_file.items():
        rel, text, _pat, _label, _want = entries[0]
        for _rel, _t, pat, label, want in entries:
            text, n = re.subn(pat, lambda m: m.group(0).replace(a.old, a.new),
                              text, flags=re.M)
            assert n == want, f"{label}: subn count {n} != {want}"
            print(f"  {label:24s} {rel}  replaced={n}")
            done += 1
        # newline='' باعث شده باشدِ CRLF/LF هر فایل حفظ شود.
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)

    print(f"bumped {a.old} -> {a.new} in {done} anchors")

    if not a.no_guard:
        r = subprocess.run([sys.executable, os.path.join(ROOT, "dev", "version_anchor_guard.py")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        print((r.stdout or "").strip() + (r.stderr or "").strip())
        return r.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
