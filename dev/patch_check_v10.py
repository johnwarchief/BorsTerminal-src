"""patch_check_v10.py — گارد سامانهٔ پچ/بهروزرسانی ماژولار (v10)

قراردادهای scripts/make_patch.py و scripts/apply_update.bat را قفل میکند تا
بازآرایی بعدی، خط لولهٔ بهروزرسانی را بیصدا نشکند:
  - پچ هرگز وضعیت کاربر را حمل نمیکند (market.db, *.lzma, adb/codal configs)
  - بات توقف نرم + extract درجا + مهر Version.txt + اجرای دوباره دارد
  - بات هرگز پوشهٔ کاربر را پاک نمیکند (rd /s /q ممنوع)
وقتی dist/BorsTerminal_Update.zip روی همین ماشین ساخته شده باشد ساختارش هم
اعتبارسنجی میشود؛ روی ماشین بدون dist/ آن چکها SKIP میشوند (خروجی rc=0).

اجرا:  python dev/patch_check_v10.py
"""
import io
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

CHECKS = []


def ck(label, cond, detail=""):
    CHECKS.append((bool(cond), label, detail))


MAKE_PATCH = "scripts/make_patch.py"
BAT = "scripts/apply_update.bat"
ZIP = os.path.join("dist", "BorsTerminal_Update.zip")

mp = io.open(MAKE_PATCH, encoding="utf-8", errors="replace").read()
ck("make_patch.py: ROOT reaches repo root",
   bool(re.search(r"^ROOT\s*=\s*os\.path\.dirname\(os\.path\.dirname\("
                  r"os\.path\.abspath\(__file__\)\)\)", mp, re.M)))
for token in ["market.db", "market.db.lzma", "adb_config.json", "codal_control.json",
              "apply_update.bat", "Version.txt", "BorsTerminal_Update.zip",
              "compresslevel=9"]:
    ck("make_patch.py: mentions %s" % token, token in mp)

raw = open(BAT, "rb").read()
first_line = raw.split(b"\n")[0] + b"\n"
ck("apply_update.bat: CRLF line endings", b"\r\n" in first_line and b"\r\n" in raw)
bat = raw.decode("utf-8", "replace")
for token in ["taskkill /IM", "taskkill /F /IM", "BorsTerminal_Ultimate.exe",
              "tar -xf", "Expand-Archive", "phase2", "Version.txt",
              "BORS_UPDATE_NORELAUNCH", "_internal"]:
    ck("apply_update.bat: has %s" % token, token in bat)
ck("apply_update.bat: no rd /s /q (never wipes user dirs)",
   "rd /s /q" not in bat.lower())
ck("apply_update.bat: no del of user data",
   not re.search(r"del\s+/[qfs]\s.*(market\.db|\.lzma|adb_config|codal_control)",
                 bat, re.I))

ck("UPDATE.md documents the pipeline",
   os.path.exists("UPDATE.md")
   and "apply_update.bat" in io.open("UPDATE.md", encoding="utf-8",
                                     errors="replace").read())
runner = io.open("dev/run_all_tests.py", encoding="utf-8", errors="replace").read()
ck("run_all_tests.py registers patch guard", "patch_check_v10.py" in runner)

if os.path.exists(ZIP):
    with zipfile.ZipFile(ZIP) as zf:
        names = [n.replace("\\", "/") for n in zf.namelist()]
        ck("patch zip: has exe", "BorsTerminal_Ultimate.exe" in names)
        ck("patch zip: has _internal payload",
           any(n.startswith("_internal/") for n in names))
        ck("patch zip: has apply_update.bat", "apply_update.bat" in names)
        ck("patch zip: has Version.txt", "Version.txt" in names)
        ck("patch zip: no market.db", "market.db" not in names)
        ck("patch zip: no *.lzma", not any(n.endswith(".lzma") for n in names))
        ck("patch zip: no adb_config.json",
           not any(n.endswith("adb_config.json") for n in names))
        ck("patch zip: no codal_control.json",
           not any(n.endswith("codal_control.json") for n in names))
        ck("patch zip: integrity", zf.testzip() is None)
else:
    print("SKIP  dist/BorsTerminal_Update.zip not built on this machine "
          "- artifact checks skipped")

passed = sum(1 for ok, _, _ in CHECKS if ok)
for ok, label, detail in CHECKS:
    if not ok:
        print("FAIL  %s %s" % (label, ("| " + detail) if detail else ""))
print("%d/%d passed" % (passed, len(CHECKS)))
print("PATCH GUARD OK" if passed == len(CHECKS) else "PATCH GUARD FAILED")
sys.exit(0 if passed == len(CHECKS) else 1)
