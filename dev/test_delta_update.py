"""test_delta_update.py — تستِ منطقِ انتخاب/اعمالِ پچِ دلتا (v1.0.10)

بدونِ نیاز به بیلد یا اینترنت، قراردادهای حیاتیِ api/update.py را قفل می‌کند:

  1) _select_patch فقط پچِ «from==نسخهٔ فعلی و to==نسخهٔ هدف» را برمی‌گزیند.
     این مهم‌ترین ضمانتِ امنیتی است: پچِ 1.0.9→1.0.10 هرگز روی 1.0.8 اعمال
     نمی‌شود (فایلهای ناسازگار روی هم قرار می‌گرفتند).
  2) غیبتِ هر یک از پیش‌نیازها (patches، from، to، url، signature) → None،
     یعنی آپدیتِر شفافاً به نصبِ کامل برمی‌گردد.
  3) update_check فیلدهای delta/size را درست پر می‌کند.
  4) _install_dir_writable روی یک مسیرِ نوشتنی True و روی یک مسیرِ
     فقط‌خواندنی False برمی‌گرداند (این چیزی است که fallback را روشن می‌کند).

اجرا:  python dev/test_delta_update.py
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from api import update as upd  # noqa: E402

FAILURES = []


def check(label, cond):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        FAILURES.append(label)


def manifest(patches=None, version="1.0.10"):
    m = {
        "version": version,
        "notes": "test",
        "pub_date": "Mon, 01 Jan 2026 00:00:00 GMT",
        "platforms": {"windows-x86_64": {
            "signature": "SIG-INSTALLER",
            "url": "https://example.com/setup.exe",
        }},
    }
    if patches is not None:
        m["patches"] = patches
    return m


def good_patch(**over):
    p = {"from": upd.APP_VERSION, "to": "1.0.10",
         "signature": "SIG-PATCH", "url": "https://example.com/patch.zip",
         "size": 1234}
    p.update(over)
    return p


print("== _select_patch: happy path")
check("selects the matching patch",
      upd._select_patch(manifest([good_patch()])) is not None)

print("== _select_patch: rejection cases (must all fall back to None)")
check("no patches key -> None",
      upd._select_patch(manifest(None)) is None)
check("empty patches array -> None",
      upd._select_patch(manifest([])) is None)
check("patches not a list -> None",
      upd._select_patch(manifest({"from": upd.APP_VERSION})) is None)
check("wrong from (older client) -> None",
      upd._select_patch(manifest([good_patch(**{"from": "1.0.8"})])) is None)
check("wrong to (stale patch vs manifest) -> None",
      upd._select_patch(manifest([good_patch(**{"to": "1.0.9"})])) is None)
check("missing url -> None",
      upd._select_patch(manifest([good_patch(**{"url": ""})])) is None)
check("missing signature -> None",
      upd._select_patch(manifest([good_patch(**{"signature": ""})])) is None)
check("non-dict entry -> None",
      upd._select_patch(manifest(["junk"])) is None)
check("picks the right one among many",
      upd._select_patch(manifest([
          good_patch(**{"from": "1.0.7", "url": "https://e.com/old.zip"}),
          good_patch(),  # this one
          good_patch(**{"to": "1.0.11", "url": "https://e.com/future.zip"}),
      ])) is not None)

print("== update_check: delta metadata")
# update_check خودش مانیفست را fetch می‌کند (BORS_UPDATE_MANIFEST یا شبکه) و
# به _LAST_MANIFEST نگاه نمی‌کند؛ پس خودِ _fetch_manifest را جایگزین می‌کنیم.
# کلاینتِ قدیمیِ 1.0.9 را شبیه‌سازی می‌کنیم تا available=True و پچِ 1.0.9→1.0.10
# همزمان برقرار شوند (available نیازمندِ version > APP_VERSION است).
orig_fetch = upd._fetch_manifest
orig_version = upd.APP_VERSION
try:
    upd.APP_VERSION = "1.0.9"
    upd._fetch_manifest = lambda: manifest([good_patch(size=999)])
    res = upd.update_check()
finally:
    upd._fetch_manifest = orig_fetch
    upd.APP_VERSION = orig_version
check("available is True", res["available"] is True)
check("delta is True when a patch matches", res["delta"] is True)
check("size reports the patch size", res["size"] == 999)
check("url points at the patch", res["url"].endswith("patch.zip"))
check("signature is the patch signature", res["signature"] == "SIG-PATCH")

try:
    upd.APP_VERSION = "1.0.9"
    upd._fetch_manifest = lambda: manifest(None)
    res2 = upd.update_check()
finally:
    upd._fetch_manifest = orig_fetch
    upd.APP_VERSION = orig_version
check("delta is False without patches", res2["delta"] is False)
check("url falls back to the installer", res2["url"].endswith("setup.exe"))
check("size falls back to the installer size",
      res2["size"] == 0)  # manifest test has no size on the platform entry

print("== _install_dir_writable: fallback trigger")
# _install_dir() در محیطِ dev روی رجیستری می‌گردد و معمولاً None برمی‌گرداند؛
# پس خودِ تابع را با یک مسیرِ مستقیم می‌سنجیم تا منطقِ probe اثبات شود.
writable = tempfile.mkdtemp()
probe_dir = os.path.join(writable, "sub")
os.makedirs(probe_dir)
orig_install_dir = upd._install_dir
try:
    upd._install_dir = lambda: probe_dir
    check("probe write succeeds on writable dir",
          upd._install_dir_writable() is True)
finally:
    upd._install_dir = orig_install_dir

# «نوشتن ممکن نیست» باید به صورتِ قطعی رویِ ویندوز هم اثبات شود: chmodِ
# دایرکتوری رویِ ویندوز بی‌اثر است (ACL حاکم است، نه بیت‌های POSIX)، پس
# مسیری می‌سازیم که پدرش یک فایل است → NotADirectoryError (زیرکلاسِ OSError).
blocker = os.path.join(writable, "afile")
with open(blocker, "w") as fh:
    fh.write("x")
try:
    upd._install_dir = lambda: os.path.join(blocker, "nope")
    check("probe write fails on unusable path",
          upd._install_dir_writable() is False)
    upd._install_dir = lambda: None
    check("missing install dir -> not writable",
          upd._install_dir_writable() is False)
finally:
    upd._install_dir = orig_install_dir

# رویِ POSIX واقعاً می‌توان دایرکتوری را فقط‌خواندنی کرد؛ این شاخه فقط آنجا
# اجرا می‌شود تا سینتکسِ chmod در مسیرِ لینوکسی هم پوشش داده شود.
if os.name == "posix":
    is_root = getattr(os, "geteuid", lambda: -1)() == 0
    if is_root:
        # کاربر root در لینوکس محدودیت‌های دسترسی 0500 را دور می‌زند؛
        # بنابراین تست probe write در کانتینر/رانرِ root مستثنی می‌شود.
        check("probe write fails on read-only dir (posix: skipped for root)", True)
    else:
        ro = tempfile.mkdtemp()
        os.chmod(ro, 0o500)                # r-x: فقط خواندنی
        try:
            upd._install_dir = lambda: ro
            check("probe write fails on read-only dir (posix)",
                  upd._install_dir_writable() is False)
        finally:
            os.chmod(ro, 0o700)
            upd._install_dir = orig_install_dir

print("== _extract_applier_from_patch: bootstrap for pre-1.0.10 installs")
# نصبِ 1.0.9 اعمال‌کننده را در محلِ نصب ندارد (قبل از 1.0.10 به [Files]
# اضافه نشده بود). پچِ 1.0.10 خودش apply_update.bat را همراه دارد و چون پچ
# پیش‌تر با minisign راستی‌آزمایی شده، استخراج از آن درونِ مرزِ اعتماد است.
import zipfile  # noqa: E402

BAT_BODY = b"@echo off\r\nrem bootstrap test\r\n"


def _make_patch_zip(path, with_bat=True):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Version.txt", "app_version=1.0.10\r\n")
        if with_bat:
            zf.writestr("apply_update.bat", BAT_BODY)
        zf.writestr("_internal/bors_config.py", b"# v10\r\n")


tmpdir = tempfile.mkdtemp()
patch_with = os.path.join(tmpdir, "patch_with_bat.zip")
patch_without = os.path.join(tmpdir, "patch_without_bat.zip")
bad_zip = os.path.join(tmpdir, "not_a_zip.zip")
_make_patch_zip(patch_with, with_bat=True)
_make_patch_zip(patch_without, with_bat=False)
with open(bad_zip, "wb") as fh:
    fh.write(b"this is not a zip at all")

dest1 = os.path.join(tmpdir, "extracted_with.bat")
check("extracts apply_update.bat from a signed patch",
      upd._extract_applier_from_patch(patch_with, dest1) is True)
check("extracted bat has the expected body",
      open(dest1, "rb").read() == BAT_BODY)

dest2 = os.path.join(tmpdir, "extracted_without.bat")
check("returns False when the patch has no applier",
      upd._extract_applier_from_patch(patch_without, dest2) is False)
check("no file written when the patch has no applier",
      os.path.isfile(dest2) is False)

dest3 = os.path.join(tmpdir, "extracted_bad.zip")
check("corrupt zip -> False, no exception",
      upd._extract_applier_from_patch(bad_zip, dest3) is False)
check("missing patch file -> False, no exception",
      upd._extract_applier_from_patch(
          os.path.join(tmpdir, "nope.zip"), dest3) is False)

print("== _spawn_patch_apply: bootstraps the applier when absent")
# کلاینتِ 1.0.9: مسیرِ نصبِ نوشتنی ولی بدونِ apply_update.bat. نباید به
# fallbackِ نصبِ کامل برود — اعمال‌کننده از داخلِ پچ استخراج می‌شود.
sandbox = tempfile.mkdtemp()
orig_spawn = subprocess.Popen
orig_delayed_exit = upd._delayed_exit
spawned = []


class _FakePopen:
    def __init__(self, cmd, *a, **kw):
        spawned.append(cmd)


try:
    upd._install_dir = lambda: sandbox
    upd._delayed_exit = lambda _s: None          # در تست نباید خارج شویم
    upd.subprocess.Popen = _FakePopen
    applier = upd._spawn_patch_apply(patch_with)
finally:
    upd.subprocess.Popen = orig_spawn
    upd._delayed_exit = orig_delayed_exit
    upd._install_dir = orig_install_dir
check("applier path is returned", applier is not None)
check("applier was materialized in the install dir",
      os.path.isfile(os.path.join(sandbox, "apply_update.bat")))
check("patch was staged as BorsTerminal_Update.zip",
      os.path.isfile(os.path.join(sandbox, "BorsTerminal_Update.zip")))
check("cmd.exe was spawned to run the applier",
      any("apply_update.bat" in str(c) for c in spawned))

# و حالتِ واقعیِ «هیچ اعمال‌کننده‌ای در دسترس نیست»:
sandbox2 = tempfile.mkdtemp()
try:
    upd._install_dir = lambda: sandbox2
    upd.subprocess.Popen = _FakePopen
    applier2 = upd._spawn_patch_apply(patch_without)
finally:
    upd.subprocess.Popen = orig_spawn
    upd._install_dir = orig_install_dir
check("patch without applier and no shipped bat -> None",
      applier2 is None)
check("nothing spawned in the fallback case", len(spawned) == 1)

print("== manifest contract: publish side emits the same shape")
pub_manifest = {
    "version": "1.0.10",
    "patches": [{"from": "1.0.9", "to": "1.0.10",
                 "signature": "SIG", "url": "https://e.com/p.zip", "size": 5}],
}
# همان ساختاری که scripts/publish_github_release.py می‌سازد، باید توسطِ
# _select_patch روی یک کلاینتِ 1.0.9 قابلِ انتخاب باشد.
orig_version = upd.APP_VERSION
try:
    upd.APP_VERSION = "1.0.9"
    check("published patch entry is selectable by a 1.0.9 client",
          upd._select_patch(pub_manifest) is not None)
finally:
    upd.APP_VERSION = orig_version
check("json round-trips",
      json.loads(json.dumps(pub_manifest, ensure_ascii=False)) == pub_manifest)

print()
if FAILURES:
    print("DELTA TEST FAILED: %d" % len(FAILURES))
    for f in FAILURES:
        print("  - " + f)
    sys.exit(1)
print("DELTA TEST OK")
