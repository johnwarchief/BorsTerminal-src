#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/local_path_guard.py — شُمارِ ریشه‌دار: مسیرِ شخصیِ تازه به گیت اضافه نشود.

چرا: درِ بازبینیِ ۲۰۲۶-۱۰-۱۶ روشن شد ردیف‌هایِ شاهد (`_audit/**`) و حتی یک
fixtureِ آزمونِ محصول (`frontend/src/__tests__/fixtures/execution-contract.json`)
نشانیِ مطلقِ `C:\\Users\\<نامِ کاربر>\\…` را نگه داشته‌اند — یعنی نامِ حسابِ یک
اپراتور درِ مخزن. پاک‌سازیِ آن‌ها درِ کامیتِ `security(audit)` انجام شد، ولی
بی‌نگهبان دوباره برمی‌گردد: هر probe یا لاگِ اجرایِ واقعی، مسیرِ cwd را می‌نویسد.

قاعدهٔ این گارد **شُمارِ ریشه‌دار (ratchet)** است، نه صفرِ ساختگی: شمارِ فایل‌های
ردیابی‌شده‌ای که هنوز مسیرِ پروفایلِ کاربر دارند با `dev/local_path_baseline.txt`
سنجیده می‌شود؛ **افزایش = قرمز**، کاهش = سبز + اعلامِ جایِ بهبود. بی‌این، گارد
یا از روزِ اول قرمز می‌ماند (و بی‌اعتبار) یا چیزی را که هست انکار می‌کند.

هیچ مسیری، نامی یا مقدارِ حساسی چاپ نمی‌شود — فقط نامِ فایل و شمار.

اجرا:  python dev/local_path_guard.py [--update]     (۰ = سبز، ۱ = رد)
"""
import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join("dev", "local_path_baseline.txt")

# نشانیِ پروفایلِ کاربر درِ ویندوز یا POSIX — نامِ واقعیِ حساب را می‌گیرد
USER_PATH = re.compile(r"(?i)(?:[a-z]:[\\/]+)?users?[\\/]+([^\s\"'`,;\\/]+)")
# نام‌هایِ عمومیِ ویندوز که حسابِ کسی نیستند
GENERIC = {"public", "default", "all users", "default user", "wd", "temp", "[local_user]"}
TEXT_EXT = (".json", ".txt", ".log", ".md", ".py", ".mts", ".mjs", ".ts", ".tsx", ".csv",
            ".ps1", ".yml", ".yaml", ".html", ".out")


def tracked_text_files():
    out = subprocess.run(["git", "-C", ROOT, "ls-files"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stdout
    return [f for f in out.splitlines() if f.lower().endswith(TEXT_EXT)]


def offenders():
    bad = []
    for f in tracked_text_files():
        p = os.path.join(ROOT, f.replace("/", os.sep))
        try:
            s = io.open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for m in USER_PATH.finditer(s):
            who = m.group(1).strip().lower()
            if who and who not in GENERIC and not who.startswith("$"):
                bad.append(f)
                break
    return sorted(set(bad))


def main():
    bad = offenders()
    if "--update" in sys.argv:
        with io.open(os.path.join(ROOT, BASELINE), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(bad) + "\n")
        print("local_path_guard: baseline written — %d فایلِ ردیابی‌شده هنوز مسیرِ "
              "پروفایل دارند (پاک‌سازیِ زمان‌دار، نه پذیرش)" % len(bad))
        return 0

    path = os.path.join(ROOT, BASELINE)
    if not os.path.exists(path):
        print("FAIL  baseline نیست — با `--update` بساز (صداقتِ گارد به آن بند است)")
        return 1
    base = {l.strip() for l in io.open(path, encoding="utf-8").read().splitlines() if l.strip()}
    new = [f for f in bad if f not in base]
    fixed = [f for f in base if f not in bad]
    print("local_path_guard: %d فایلِ ردیابی‌شده مسیرِ پروفایلِ کاربر دارد "
          "(baseline: %d)" % (len(bad), len(base)))
    if fixed:
        print("  %d فایل پاک شده — با `--update` پایین بیاور: %s…" % (len(fixed), fixed[0]))
    if new:
        print("  FAIL %d فایلِ تازه مسیرِ شخصی آورده (نام/مقدار چاپ نمی‌شود):" % len(new))
        for f in new[:12]:
            print("    + %s" % f)
        return 1
    print("ok   هیچ مسیرِ شخصیِ تازه‌ای به گیت اضافه نشد")
    return 0


if __name__ == "__main__":
    sys.exit(main())
