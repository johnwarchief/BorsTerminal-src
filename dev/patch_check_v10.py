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
# a patch only overlays files; without this the uninstall entry would keep
# advertising the version that was just replaced (found by the 1.0.11 e2e).
ck("apply_update.bat: syncs DisplayVersion so Add/Remove Programs agrees",
   "DisplayVersion" in bat and "reg add" in bat
   and "{8F3A2E7C-1B44-4C2E-9A77-0B0B5C0DE001}_is1" in bat)
ck("apply_update.bat: reads the target version from the shipped Version.txt",
   "app_version=" in bat)
# the worker is copied to %TEMP% *before* extraction, so it is always the
# pre-update applier; without this re-entry a fix here would only land on the
# user's NEXT update. found by the 1.0.11 delta (registry stayed 1.0.10).
ck("apply_update.bat: re-enters the freshly extracted copy so it can update itself",
   "phase3" in bat and "WORKER2" in bat and "fc /b" in bat
   and "goto finalize" in bat and "exit /b %RC2%" in bat)
ck("apply_update.bat: finalize steps are reachable without the self-update chain",
   ":finalize" in bat and ":noreg" in bat and ":regok" in bat)
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

# --- v1.0.10: قراردادهای بهروزرسانیِ دلتا ---------------------------------
# این قراردادها کلِ زنجیرهٔ امنیتِ پچ را قفل میکنند: پچ باید امضا شود،
# مانیفست باید from/to داشته باشد که آپدیتِر بر اساسش انتخاب میکند، و
# اعمالکننده باید خودش در کنارِ نصب قرار گیرد تا آپدیتِر بتواند آن را spawn کند.
upd = io.open("api/update.py", encoding="utf-8", errors="replace").read()
for token in ["_select_patch", "_install_dir_writable", "_spawn_patch_apply",
              "is_patch", '"patches"', '"from"', '"to"', "UPDATE_PUBKEY"]:
    ck("api/update.py: delta path uses %s" % token, token in upd)
ck("api/update.py: patch selection requires from==APP_VERSION",
   bool(re.search(r'p\.get\(\s*"from"\s*\)\s*or\s*""\)\s*!=\s*APP_VERSION', upd)))
ck("api/update.py: patch selection requires to==manifest version",
   bool(re.search(r'p\.get\(\s*"to"\s*\)\s*or\s*""\)\s*!=\s*target', upd)))
ck("api/update.py: patch needs url + signature",
   bool(re.search(r'p\.get\(\s*"url"\s*\)\s*and\s*p\.get\(\s*"signature"\s*\)', upd)))
ck("api/update.py: falls back to full installer",
   "در حال نصبِ کامل (fallback)" in upd)
ck("api/update.py: offline path accepts .zip patches",
   bool(re.search(r'\.zip', upd)) and "is_patch" in upd)

pub = io.open("scripts/publish_github_release.py", encoding="utf-8",
              errors="replace").read()
# v1.0.26: به‌جایِ «یک پچ»، آرایه‌ای از پچ‌ها منتشر می‌شود (یک ورودی به ازای هر
# نسخهٔ مبدأِ ریلیز‌شده) تا کاربرِ دو سه نسخه عقب هم آپدیتِ کوچک بگیرد.
# قراردادِ همان سه چیز است، فقط به‌صورتِ چندتایی: امضا الزامی، هر ورودی
# from/to/url/signature/size دارد، و نبودِ پچ یعنی نصبِ کامل.
for token in ['manifest["patches"]', '"from"', '"to"', '"url"', '"signature"',
              '"size"', "PATCH_FROM"]:
    ck("publish_github_release.py: manifest has %s" % token, token in pub)
ck("publish_github_release.py: a patch without its .sig is never published",
   'PATCHES = [e for e in PATCHES if os.path.isfile(e["sig"])]' in pub)
ck("publish_github_release.py: patch upload is optional",
   "patch_uploaded = bool(PATCHES)" in pub)
ck("publish_github_release.py: a patch near the installer size falls back to setup",
   "PATCH_MAX_RATIO" in pub and 'PATCHES.remove(_e)' in pub)

iss = io.open("installer/bors_setup.iss", encoding="utf-8",
              errors="replace").read()
ck("installer ships apply_update.bat (updater needs it on disk)",
   "apply_update.bat" in iss and "DestDir: \"{app}\"" in iss)
ck("installer has maintenance/repair mode",
   "MaintenancePage" in iss and "RunFullUninstall" in iss)
ck("make_patch.py signs the patch",
   "sign_patch" in mp and "sign_setup.py" in mp)
ck("make_patch.py stamps patch_from into Version.txt",
   "patch_from" in mp)
ck("make_patch.py rejects from==to (no-op patch)",
   bool(re.search(r"from\s*==\s*to|from_version\s*==\s*to", mp)))

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
