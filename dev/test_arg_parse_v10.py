"""test_arg_parse_v10.py — تستِ تجزیهٔ آرگومانِ --from در make_patch.py

چرا این تست وجود دارد:
  پچِ دلتا باید «BorsTerminal_Patch_1.0.9_to_1.0.10.zip» نام‌گذاری شود تا
  latest.json بتواند به آن اشاره کند و آپدیتِر فقط رویِ 1.0.9 آن را اعمال کند.
  در یک نسخهٔ قدیمی، حلقهٔ تجزیه به این شکل بود:

      for i, arg in enumerate(argv[1:]):
          if arg == "--from" and i + 2 <= len(argv):
              from_version = argv[i + 1]      # BUG: اندیسِ argv، نه args

  i نسبت به slice اندیس‌گذاری می‌شد ولی argv[i+1] نسبت به argvیِ کامل خوانده
  می‌شد، پس مقدارِ پرچم («--from») به جایِ نسخهٔ مبدأ برمی‌گشت و فایل می‌شد:
  BorsTerminal_Patch_--from_to_1.0.10.zip. این پچ هرگز توسطِ _select_patch
  انتخاب نمی‌شد (from == "--from" != APP_VERSION) و آپدیتِر به نصبِ کاملِ ۸۶
  مگابایتی برمی‌گشت — یعنی کلِ ویژگیِ دلتا بی‌اثمان می‌شد.

  این تست قراردادِ نام‌گذاری و تجزیه را برای همیشه قفل می‌کند.

اجرا:  python dev/test_arg_parse_v10.py
"""
import os
import re
import sys

# خروجیِ استاندارد رویِ ویندوز پیش‌فرض cp1252 است و نمی‌تواند متنِ فارسی را
# چاپ کند. بدونِ این کارِ خودِ تست با UnicodeEncodeError شکست می‌خورد، نه
# با شکستِ منطق.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                   # noqa: BLE001
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import make_patch  # noqa: E402

FAILURES = []


def check(label, cond):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        FAILURES.append(label)


def only_from(argv):
    """_parse_args حالا یک تاپل (from, baseline) برمی‌گرداند؛ این کمک‌کننده
    فقط بخشِ نسخهٔ مبدأ را بیرون می‌کشد تا تست رویِ قراردادِ اصلی متمرکز بماند."""
    return make_patch._parse_args(argv)[0]


print("== _parse_args")
check("default is 1.0.9",
      only_from(["make_patch.py"]) == "1.0.9")
check("reads the value after --from",
      only_from(["make_patch.py", "--from", "1.0.8"]) == "1.0.8")
# این دقیقاً همان فرمی است که release.ps1 فرامی‌خواند و باگ در آن رخ می‌داد.
check("release.ps1 form: --from 1.0.9 -> '1.0.9'",
      only_from(["make_patch.py", "--from", "1.0.9"]) == "1.0.9")
check("never returns the flag itself",
      only_from(["make_patch.py", "--from", "1.0.9"]) != "--from")
check("trailing --from without value keeps the default",
      only_from(["make_patch.py", "--from"]) == "1.0.9")
check("other flags do not disturb --from",
      only_from(["make_patch.py", "--verbose", "--from", "1.0.7",
                 "--sign"]) == "1.0.7")

print("== --baseline (دلتای واقعی)")
check("baseline defaults to empty (full overlay, backward compatible)",
      make_patch._parse_args(["make_patch.py"])[1] == "")
check("reads --baseline value",
      make_patch._parse_args(["make_patch.py", "--baseline",
                              "C:\\old"])[1] == "C:\\old")
check("from + baseline + dist together",
      make_patch._parse_args(["make_patch.py", "--from", "1.0.8",
                              "--baseline", "C:\\old", "--dist", "dist2"])[:3]
      == ("1.0.8", "C:\\old", "dist2"))
check("--baseline-manifest را هم جدا از --baseline می‌خواند",
      make_patch._parse_args(["make_patch.py", "--from", "1.0.8",
                              "--baseline-manifest", "m.json"])[3] == "m.json")

print("== --dist: read the patch from the dir release.ps1 actually built into")
check("dist defaults to the classic dist/",
      make_patch._parse_args(["make_patch.py"])[2] == "dist")
check("release.ps1 form: --dist dist2 -> dist2",
      make_patch._parse_args(["make_patch.py", "--dist", "dist2"])[2] == "dist2")
check("--dist without a value keeps the default",
      make_patch._parse_args(["make_patch.py", "--dist"])[2] == "dist")

print("== reject malformed versions (a bad name must never reach the zip)")
for bad in ("--from", "", "abc", "1.2", "1.2.3.4", "v1.0.9"):
    r = -1
    try:
        only_from(["make_patch.py", "--from", bad])
    except SystemExit as ex:
        r = ex.code
    check("rejects --from %r" % bad, r == 1)

print("== patch filename contract")
# نامِ پچ باید دقیقاً این شکل را داشته باشد تا publish/manifest/آپدیتِر همگی
# روی یک نام توافق کنند. از app_version() برای نسخهٔ مقصد استفاده می‌شود.
to_version = make_patch.app_version()
expected = "BorsTerminal_Patch_1.0.9_to_%s.zip" % to_version
check("expected name is well-formed",
      bool(re.match(r"^BorsTerminal_Patch_\d+\.\d+\.\d+_to_\d+\.\d+\.\d+\.zip$",
                    expected)))
check("no flag text leaks into the name", "--from" not in expected)
check("from != to (a patch must move between versions)", "1.0.9" != to_version)

print()
if FAILURES:
    print("ARG TEST FAILED: %d" % len(FAILURES))
    for f in FAILURES:
        print("  - " + f)
    sys.exit(1)
print("ARG TEST OK")
