# dev/test_portable_v1.py -- بندِ ۴ مأموریتِ انتشار: Portable صریح و جدا
"""چهار قراردادی که این گارد می‌بندد (همه با_reloadِ ماژول، بی‌EXE واقعی):

۱) تشخیصِ پرتابیل **صریح** است: متغیرِ محیطی `BORS_PORTABLE` یا نشانۀ
   `bors_portable.flag` کنارِ باینری. نوشتنی‌بودنِ پوشه هیچ‌وقت دلیلِ پرتابیل
   بودن نیست (آن حدس، نسخۀ نصبیِ writable و ZIPِ باز‌شده را یکی می‌کرد).
۲) داده‌ها جدا می‌نشینند: WORK_DIR، user.db، market.db و پروفایل همگی زیرِ
   `<exe>/data` می‌مانند و هرگز %LOCALAPPDATA% نسخۀ نصبی را نمی‌نویسند.
۳) پورتِ پیش‌فرض جداست (8101 در برابرِ 8001) و `instance_id` از پوشۀ واقعیِ
   داده می‌آید، پس لانچر نمی‌تواند به سرورِ نسخۀ دیگری بچسبد.
۴) درِ پرتابیل هیچ Inno اجرا نمی‌شود: `/api/update/check` می‌گوید
   `portable: true, installable: false` و بی‌امضا، و `download` و `install`
   پیشِ هر subprocess مردود می‌شوند (پیام + لینکِ ZIP).

خروجیِ صفرِ این گارد یعنی «Portable فقط یک ZIPِ تصادفی از پوشۀ نصب نیست».
"""
import importlib
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PASS = FAIL = SKIP = 0


def ck(label, cond, detail=""):
    global PASS, FAIL, SKIP
    if cond is None:
        SKIP += 1
        print(f"  SKIP  {label}")
        return
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL  {label}  {detail}")


def probe(frozen=True, exe_dir=None, env=None):
    """bors_config را با باینریِ ساختگی از نو بار می‌کند و مقدارها را *همان‌جا*
    می‌خواند.

    چرا داخلِ همان context: `runtime_mode()` به `sys.frozen` زنده نگاه می‌کند و
    ماژولِ reload‌شده یکی است (WORK_DIRِ instance دوم جای اولی را می‌گیرد). اگر
    بعدِ بازگرداندنِ patch بخوانیم، یا «dev» می‌گیریم یا دو پوشه را یکسان —
    که خودِ همین، دورِ اولِ این گارد را قرمز کرد.
    """
    saved = {k: os.environ.get(k) for k in (
        "BORS_PORTABLE", "LOCALAPPDATA", "BORS_DATA_DIR", "BORS_USER_DB",
        "BORS_INTENT_DB", "BORS_TEST_ISOLATION", "BORS_OPERATIONAL_ROOT")}
    old_frozen = getattr(sys, "frozen", None)
    old_exe = sys.executable
    try:
        # این گارد مسیرهایِ portable/dev را می‌سنجد، نه DB عملیاتی؛ بنابراین
        # overrideهایِ ایزوله‌سازیِ runner نباید در probe دخالت کنند.
        for _k in ("BORS_DATA_DIR", "BORS_USER_DB", "BORS_INTENT_DB",
                   "BORS_TEST_ISOLATION", "BORS_OPERATIONAL_ROOT"):
            os.environ.pop(_k, None)
        if env:
            os.environ["BORS_PORTABLE"] = env
        else:
            os.environ.pop("BORS_PORTABLE", None)
        if exe_dir:
            os.environ["LOCALAPPDATA"] = os.path.join(exe_dir, "_localappdata_fake")
        if frozen:
            sys.frozen = True
            sys.executable = os.path.join(exe_dir or ROOT, "BorsTerminal_Ultimate.exe")
        else:
            try:
                del sys.frozen
            except AttributeError:
                pass
        import bors_config
        cfg = importlib.reload(bors_config)
        return {
            "cfg": cfg,
            "mode": cfg.runtime_mode(),
            "portable": cfg.is_portable(),
            "WORK_DIR": cfg.WORK_DIR,
            "USER_DB": cfg.USER_DB_PATH,
            "DB_PATH": cfg.DB_PATH,
            "instance": cfg.instance_id(),
            "problem": cfg.portable_data_problem(),
            "STATUS_PATH": getattr(cfg, "STATUS_PATH", None),
            "MARKET_STATUS_PATH": getattr(cfg, "MARKET_STATUS_PATH", None),
            "PRICE_BASIS_PATH": getattr(cfg, "PRICE_BASIS_PATH", None),
            "SRC_DIR": cfg._SRC_DIR,
        }
    finally:
        sys.executable = old_exe
        if old_frozen is None:
            try:
                del sys.frozen
            except AttributeError:
                pass
        else:
            sys.frozen = old_frozen
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ── ۱) تشخیصِ صریح ──────────────────────────────────────────────────────────
with tempfile.TemporaryDirectory() as td:
    # پوشه نوشتنی است؛ اگر تشخیص بر پایۀ writable بودن بود این حالت «پرتابیل»
    # می‌شد و اولین آزمونِ زیر می‌بوست -- دقیقاً همان حدسی که بسته شد.
    p = probe(frozen=True, exe_dir=td, env=None)
    ck("باینریِ نوشتنی به‌تنهایی پرتابیل نیست (حدسِ دسترسی ممنوع)",
       p["mode"] == "installed" and p["portable"] is False, p["mode"])

    open(os.path.join(td, "bors_portable.flag"), "w").close()
    p2 = probe(frozen=True, exe_dir=td, env=None)
    ck("نشانۀ bors_portable.flag پرتابیل می‌کند",
       p2["portable"] is True and p2["mode"] == "portable", p2["mode"])

    os.remove(os.path.join(td, "bors_portable.flag"))
    p3 = probe(frozen=True, exe_dir=td, env="1")
    ck("BORS_PORTABLE=1 پرتابیل می‌کند (بی‌نشانۀ دیسک)",
       p3["portable"] is True and p3["mode"] == "portable", p3["mode"])
    open(os.path.join(td, "bors_portable.flag"), "w").close()
    p4 = probe(frozen=True, exe_dir=td, env="0")
    ck("BORS_PORTABLE=0 خاموشِ صریح است، حتی با نشانۀ دیسک",
       p4["portable"] is False and p4["mode"] == "installed", p4["mode"])
    os.remove(os.path.join(td, "bors_portable.flag"))

    pd = probe(frozen=False, exe_dir=None, env=None)
    ck("حالتِ dev پرتابیل نیست و ریشۀ ریپو را می‌دهد",
       pd["mode"] == "dev" and pd["WORK_DIR"] == pd["SRC_DIR"], (pd["mode"], pd["WORK_DIR"]))

# ── ۲) جداسازیِ مسیرِ داده ───────────────────────────────────────────────────
def reload_config(**kw):
    """نسخۀِ سازگارِ probe که ماژول را برمی‌گرداند.

    هر `with` تنها یک reload می‌کند و بعد مقدارها را می‌خواند، پس مقدارهای ماژول
    هنوز مالِ همین reload‌اند. جایی که دو پوشه پشتِ هم سنجیده می‌شود (بخشِ ۳)
    باید بی‌درنگ درِ probe خوانده شود، وگرنه هر دو عدد مالِ آخری‌اند.
    """
    return probe(**kw)["cfg"]

with tempfile.TemporaryDirectory() as td:
    open(os.path.join(td, "bors_portable.flag"), "w").close()
    cfg = reload_config(frozen=True, exe_dir=td, env=None)
    want_data = os.path.join(td, "data")
    ck("WORK_DIR پرتابیل = <exe>/data", os.path.samefile(cfg.WORK_DIR, want_data)
       if os.path.isdir(cfg.WORK_DIR) else cfg.WORK_DIR == want_data,
       (cfg.WORK_DIR, want_data))
    ck("user.db درِ پوشۀ پرتابیل است (نه %LOCALAPPDATA% نسخۀ نصبی)",
       cfg.USER_DB_PATH.startswith(want_data), cfg.USER_DB_PATH)
    ck("market.dbِ برنامه‌ریزی‌شده برایِ استخراج درِ پوشۀ پرتابیل است",
       cfg.DB_PATH.startswith(want_data), cfg.DB_PATH)
    for name in ("STATUS_PATH", "MARKET_STATUS_PATH", "PRICE_BASIS_PATH"):
        v = getattr(cfg, name, None)
        ck(f"{name} درِ پوشۀ پرتابیل است", bool(v) and str(v).startswith(want_data), v)
    # پوشۀ ساختنیِ تازه: داده از صفر همین‌جا می‌نشیند
    ck("portable_data_problem برایِ پوشۀ نوشتنی None است",
       cfg.portable_data_problem() is None, cfg.portable_data_problem())

# مسیرِ غیرقابل‌ساخت/غیرقابل‌نوشتن: پیامِ روشن، نه سکوت.
# اینجا به‌جای attrsِ فقط‌خواندنی (که رویِ NTFS نوشتنِ فایل را نمی‌بندد) «data»
# را یک *فایل* می‌سازیم: os.makedirs رویِ آن OSError می‌دهد و همان مسیرِ شکستِ
# واقعیِ کاربر (پوشۀ نامعتبر/بسته‌شده) می‌افتد.
with tempfile.TemporaryDirectory() as td:
    open(os.path.join(td, "bors_portable.flag"), "w").close()
    open(os.path.join(td, "data"), "w").close()          # فایل، نه پوشه
    cfg = reload_config(frozen=True, exe_dir=td, env=None)
    problem = cfg.portable_data_problem()
    ck("مسیرِ دادۀ نامعتبر پیامِ روشن می‌دهد (نه جابه‌جایی بی‌صدا به LOCALAPPDATA)",
       bool(problem) and "داده" in problem and td in problem, problem)
    ck("درِ همان حالتِ خراب، WORK_DIR همچنان پوشۀ پرتابیل است (نه LOCALAPPDATA)",
       cfg.WORK_DIR == os.path.join(td, "data"), cfg.WORK_DIR)

# ── ۳) پورت و هویّتِ اجرا ────────────────────────────────────────────────────
cfg = reload_config(frozen=False, exe_dir=None, env=None)
ck("پورتِ پیش‌فرضِ پرتابیل از نصبی جداست",
   cfg.PORTABLE_DEFAULT_PORT != cfg.INSTALLED_DEFAULT_PORT
   and cfg.INSTALLED_DEFAULT_PORT == 8001,
   (cfg.PORTABLE_DEFAULT_PORT, cfg.INSTALLED_DEFAULT_PORT))
with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
    for d in (td1, td2):
        open(os.path.join(d, "bors_portable.flag"), "w").close()
    # مقدارها بی‌درنگ بعدِ هر reload خوانده می‌شوند: ماژولِ reload‌شده همان
    # آبجکتِ پیشین است، پس instance اگر بعداً خوانده شود مالِ آخرینِ reload است و
    # دو پوشه یک عدد می‌دهند.
    a = probe(frozen=True, exe_dir=td1, env=None)
    b = probe(frozen=True, exe_dir=td2, env=None)
    c = probe(frozen=True, exe_dir=td1, env=None)
    ck("دو پوشۀ پرتابیل دو instance_id می‌دهند (لانچر نمی‌چسبد)",
       a["instance"] != b["instance"] and a["WORK_DIR"] != b["WORK_DIR"],
       (a["instance"], b["instance"]))
    ck("همان پوشه همان instance_id را می‌دهد (دубارۀِ همان ZIP چسبیدنی است)",
       c["instance"] == a["instance"], (c["instance"], a["instance"]))

# ── ۴) آپدیتِر درِ پرتابیل نصاب اجرا نمی‌کند ─────────────────────────────────
import api.update as UP                                        # noqa: E402
import bors_config                                              # noqa: E402

MANIFEST = {
    "version": "9.9.9",
    "notes": "آزمون",
    "pub_date": "2026-10-11T09:00:00Z",
    "platforms": {"windows-x86_64": {
        "url": "https://example/BorsTerminal_Ultimate_Setup_v9.9.9.exe",
        "signature": "sig-of-installer",
        "size": 57_000_000}},
    "patches": [],
    "portable": {"url": "https://example/BorsTerminal_Ultimate_Portable_v9.9.9.zip",
                 "size": 71_000_000},
}

_real_spawn = None


class NoSpawn:
    """جای‌گرِ subprocess.Popen: اگر حتی یک بار صدا زده شود، آزمون می‌بوسد."""
    called = 0

    def __init__(self, *a, **k):
        NoSpawn.called += 1

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


import subprocess as _sp                                      # noqa: E402
_real_popen = _sp.Popen
_sp.Popen = NoSpawn                                           # type: ignore[misc]
_old_fetch = UP._fetch_manifest
_old_is_portable = bors_config.is_portable
_old_version = UP.APP_VERSION
try:
    UP.APP_VERSION = "1.0.83"
    UP._fetch_manifest = lambda: dict(MANIFEST)
    bors_config.is_portable = lambda: True
    UP._LAST_MANIFEST = {}

    chk = UP.update_check()
    ck("check درِ پرتابیل: portable=true و installable=false اعلام می‌شود",
       chk.get("portable") is True and chk.get("installable") is False
       and chk.get("updater") == "portable", chk)
    ck("check درِ پرتابیل امضایِ نصاب را رد نمی‌کند (امضایی که به‌کار نمی‌رود)",
       chk.get("signature") == "" and chk.get("delta") is False, chk)
    ck("check درِ پرتابیل لینکِ ZIPِ همان نسخه را می‌دهد",
       chk.get("url") == MANIFEST["portable"]["url"], chk.get("url"))
    ck("check درِ پرتابیل آپدیت را پنهان نمی‌کند (available=true)",
       chk.get("available") is True and chk.get("latest_version") == "9.9.9", chk)
    ck("check درِ پرتابیل پیامِ راهنما دارد", bool(chk.get("message")), chk.get("message"))

    dl = UP.update_download(UP.DownloadRequest())
    ck("download درِ پرتابیل مردود است (نصاب ۵۷ مگابایتی دانلود نمی‌شود)",
       dl.get("status") == "error" and dl.get("portable") is True, dl)
    inst = UP.update_install()
    ck("install درِ پرتابیل مردود است (بسته‌ای آماده نیست)",
       inst.get("status") == "error", inst)
    forced = UP._run_install("C:/fake/BorsTerminal_Ultimate_Setup_v9.9.9.exe", "sig", False)
    ck("اجبارِ مسیرِ install هم نصاب را اجرا نمی‌کند",
       forced.get("status") == "error" and forced.get("portable") is True, forced)
    ck("هیچ Popen برایِ نصاب ساخته نشد", NoSpawn.called == 0, NoSpawn.called)

    # نسخه/هویّت: لانچر با این می‌فهمد سرورِ رویِ پورت مالِ همین پوشه است یا نه
    ver = UP.update_version()
    ck("/api/update/version mode و instance را اعلام می‌کند",
       "mode" in ver and "instance" in ver, ver)

    # نسخۀ نصبی نباید دست‌کاری شده باشد: همان مسیرِ همیشگیِ check
    bors_config.is_portable = lambda: False
    UP._LAST_MANIFEST = {}
    chk2 = UP.update_check()
    ck("درِ نسخۀ نصبی check همان urlِ نصاب/پچ و امضا را می‌دهد (بدونِ تغییرِ رفتار)",
       chk2.get("url") == MANIFEST["platforms"]["windows-x86_64"]["url"]
       and chk2.get("signature") == "sig-of-installer"
       and not chk2.get("portable"), chk2)
    ck("درِ نسخۀ نصبی هم هنوز Popen اجرا نشده", NoSpawn.called == 0, NoSpawn.called)
finally:
    _sp.Popen = _real_popen                                   # type: ignore[misc]
    UP._fetch_manifest = _old_fetch
    bors_config.is_portable = _old_is_portable
    UP.APP_VERSION = _old_version
    importlib.reload(bors_config)

# ── ۵) بسته‌بندی: ZIPِ پرتابیل نشان دارد و بی‌دادِ کاربر ─────────────────────
script = os.path.join(ROOT, "release.ps1")
if os.path.exists(script):
    src = open(script, encoding="utf-8", errors="replace").read()
    ck("release.ps1 نشانۀ پرتابیل را درِ بسته می‌گذارد",
       "PORTABLE_MARKER" in src or "bors_portable.flag" in src, "")
    ck("release.ps1 ZIP می‌سازد (نه فقط پوشۀ staging)",
       "BorsTerminal_Ultimate_Portable_" in src and ("Compress-Archive" in src or "ZipFile" in src), "")
    ck("بستۀ پرتابیل دادِ کاربر را بیرون می‌گذارد (data/ و *.db و log)",
       "PORTABLE_EXCLUDE" in src, "")
else:
    ck("release.ps1 پیدا نشد", None)

ci = os.path.join(ROOT, ".github", "workflows", "release.yml")
if os.path.exists(ci):
    y = open(ci, encoding="utf-8", errors="replace").read()
    ck("CI هم ZIPِ پرتابیل می‌سازد (از همان بیلدِ نصاب)",
       "Portable" in y and "Compress-Archive" in y, "")
    ck("CI پرتابیل را پیشِ انتشار می‌سازد (همان commit، همان dist)",
       0 <= y.find("Build Portable ZIP") < y.find("python scripts/publish_github_release.py"), "")
    step = (y.split("Build Portable ZIP", 1)[-1].split("Build Delta Patch", 1)[0]
            if "Build Portable ZIP" in y else "")
    ck("CI هم نشانۀ پرتابیل را می‌نویسد", "bors_portable.flag" in step, "")
    ck("CI هم دادِ زمانِ اجرا را بیرون می‌گذارد", "$exclude" in step and "user.db" in step, "")
    ck("مرحلۀ پرتابیل continue-on-error ندارد (ریلیزِ بی‌پرتابیل سبز نمی‌شود)",
       bool(step) and not re.search(r"^\s*continue-on-error:\s*true", step, re.M), "")
    # بانکِ بیس‌لاین درِ گیت نیست (*.lzma ایگنور) و CI آن را از ریلیزِ بیرونیِ
    # data-latest می‌گیرد؛ نبودنش نباید کلِ انتشار را بخواباند، چون نصابِ CI هم
    # همین راه را می‌رود و برنامه درِ اولین اجرا دانلود می‌کند.
    ck("CI بی‌بانک هشدار می‌دهد نه خطایِ مرگبار",
       bool(step) and "data-latest" in step and "::error::[portable] market.db.lzma" not in step, "")
else:
    ck("release.yml پیدا نشد", None)

pub = os.path.join(ROOT, "scripts", "publish_github_release.py")
if os.path.exists(pub):
    ps = open(pub, encoding="utf-8", errors="replace").read()
    ck("منتشرکننده ZIPِ پرتابیل را آپلود می‌کند", "PORTABLE_ZIP" in ps, "")
    ck("latest.json بلوکِ portable دارد (تا آپدیتِر لینکِ درست بدهد)",
       '"portable"' in ps, "")
else:
    ck("publish_github_release.py پیدا نشد", None)

# ── ۶) امضایِ نصاب درِ پرتابیل نباید از راهِ دیگری باز شود ──────────────────
src_upd = open(os.path.join(ROOT, "api", "update.py"), encoding="utf-8").read()
ck("check/download/install سه لایۀ محافظتِ پرتابیل دارند",
   src_upd.count("is_portable()") >= 3, src_upd.count("is_portable()"))
ck("متنِ راهنمایِ پرتابیل یک‌جا تعریف شده (نه سه نسخه‌ی متفرق)",
   src_upd.count("PORTABLE_UPDATE_MESSAGE") >= 3, src_upd.count("PORTABLE_UPDATE_MESSAGE"))

print("─" * 72)
print(f"نتیجۀِ گاردِ حالتِ Portable: {PASS}_pass / {FAIL}_fail / {SKIP}_skip")
sys.exit(1 if FAIL else 0)
