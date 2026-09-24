# -*- coding: utf-8 -*-
"""make_patch.py — سازندهٔ پچ بهروزشوندهٔ ماژولار BorsTerminal_Ultimate (v10)

خروجی: dist/BorsTerminal_Patch_<from>_to_<to>.zip — یک پچ «رویهمگذاری» flat که
باید دقیقاً روی پوشهٔ نصب فعلی extract شود (ریشهٔ zip == ریشهٔ نصب).

دلتای واقعی (v1.0.10): اگر --baseline DIR داده شود، فقط فایلهایی وارد پچ
میشوند که نسبت به همان نسخهٔ مبدأ تغییر کرده‌اند (یا جدیدند). بقیهٔ فایلها —
مثلِ ۴۳ مگابایتِ PySide6 یا ۲۰ مگابایتِ numpy.libs — بینِ دو نسخه یکسانند و
دانلود نمی شوند. این یعنی پچ از ~۸۱ مگابایت به چند مگابایت می‌رسد، در حالی که
نصبِ کامل هنوز ~۸۶ مگابایت است.

قاعدهٔ طلایی: وضعیت کاربر هرگز داخل پچ سفر نمیکند — market.db/market.db.lzma،
adb_config.json، codal_control.json، codal_state.json، sync*.json، لاگها و کشها
حذف میشوند تا اعمال بهروزرسانی هیچوقت دیتابیس/تنظیمات تترینگ کاربر را له نکند.

apply_update.bat هم در ریشهٔ zip قرار میگیرد؛ کافیست کاربر آن را کنار zip
اجرا کند: توقف نرم برنامه → extract درجا → مهر Version.txt → اجرای دوباره.

امضا (v1.0.10): پچ با همان کلید minisignِ نصاب امضا می‌شود (scripts/sign_setup.py)
و latest.json از طریقِ scripts/publish_github_release.py به آن اشاره می‌کند.
آپدیتِرِ درون‌برنامه‌ای قبل از اجرای هر چیزی امضای پچ را راستی‌آزمایی می‌کند.

اجرا:  python scripts/make_patch.py --from 1.0.9 --baseline <old-install>
       (بعد از scripts/build_exe.py)
"""
import datetime
import hashlib
import os
import re
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
DEFAULT_DIST = "dist"
BAT = os.path.join(ROOT, "scripts", "apply_update.bat")
SIG = os.path.join(ROOT, "scripts", "sign_setup.py")

# وضعیت/تنظیمات کاربر: هرگز داخل پچ نمیآیند
EXCLUDE_FILES = {
    "market.db", "market.db.lzma", "adb_config.json", "codal_control.json",
    "codal_state.json", "market_sync.json", "sync_status.json",
    "sync_ondemand.json", "sync_summary.json", "fts_update_state.json",
}
EXCLUDE_EXT = {".db", ".db-shm", ".db-wal", ".lzma", ".log", ".pyc", ".pyo",
               ".tmp", ".bak", ".err", ".out"}
EXCLUDE_DIRS = {"__pycache__", "logs", ".pytest_cache", "WT"}


def app_version():
    """نسخهٔ مقصدِ پچ = APP_VERSION منبعِ واحد (bors_config).

    v1.0.10: static/index.html حذف شده (SPA حالا از frontend/dist سرو می‌شود)،
    پس خواندنِ نسخه از آن مسیر همیشه 0.0.0 برمی‌گرداند. bors_config همان
    منبعی است که api/update.py و bors_setup.iss می‌خوانند.
    """
    sys.path.insert(0, ROOT)
    import bors_config  # noqa: PLC0415  (importِ محلی: جلوگیری از import دورهای)
    return bors_config.APP_VERSION


def git_short():
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8")
        return (r.stdout or "").strip() or "unknown"
    except OSError:
        return "unknown"


def _parse_args(argv):
    """--from X.Y.Z: نسخهٔ مبدأِ پچ (پیش‌فرض: 1.0.9). گیت‌هاب ریلیز آن را در
    latest.json می‌نویسد و آپدیتِر فقط در صورتِ برابریِ current==from آن را
    اعمال می‌کند — وگرنه به نصبِ کامل برمی‌گردد.

    --baseline DIR: پوشهٔ نصبِ نسخهٔ مبدأ. اگر داده شود، پچ فقط فایلهای تغییر
    کرده/جدید را شامل می‌شود (دلتای واقعی). در غیر این صورت، همهٔ فایلها
    (رفتارِ قدیمی، سازگار با نصبِ قدیمی که apply_update.bat ندارد).

    --baseline-manifest FILE: جایِ دیگرِ --baseline: به‌جایِ نصب‌کردنِ نسخهٔ
    مبدأ در CI، فایلِ sha256ِ همان نسخه (BorsTerminal_Manifest_v<from>.json که
    خودِ همین اسکریپت با --emit-manifest می‌سازد و ریلیز منتشر می‌کند) خوانده
    می‌شود. نصب‌کردنِ نصابِ ۶۰ مگابایتی در رانر همزمانِ download+install چند
    دقیقه وقت می‌گیرد و به environment حساس است؛ مقایسهٔ هش این خطر را ندارد.

    --emit-manifest FILE: فقط نقشهٔ relpath -> sha256ِ بیلدِ فعلی را می‌نویسد و
    هیچ پچی نمی‌سازد (برایِ اینکه ریلیز، لنگهٔ مقایسهٔ نسخهٔ بعد را با خودش
    بفرستد).
    """
    from_version = "1.0.9"
    baseline = ""
    dist = DEFAULT_DIST
    baseline_manifest = ""
    emit_manifest = ""
    # i نسبت به خودِ args اندیس‌گذاری می‌شود، نه نسبت به argvیِ کامل؛ وگرنه
    # argv[i+1] به جایِ مقدار، خودِ پرچم را برمی‌دارد (باگِ نام‌گذاریٔ پچ).
    args = argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--from" and i + 1 < len(args):
            from_version = args[i + 1]
            i += 2
            continue
        if a == "--baseline" and i + 1 < len(args):
            baseline = args[i + 1]
            i += 2
            continue
        if a == "--baseline-manifest" and i + 1 < len(args):
            baseline_manifest = args[i + 1]
            i += 2
            continue
        if a == "--emit-manifest" and i + 1 < len(args):
            emit_manifest = args[i + 1]
            i += 2
            continue
        if a == "--dist" and i + 1 < len(args):
            dist = args[i + 1]
            i += 2
            continue
        i += 1
    if not re.match(r"^\d+\.\d+\.\d+$", from_version):
        print("[ERR] --from must look like X.Y.Z, got %r" % from_version)
        sys.exit(1)
    return from_version, baseline, dist, baseline_manifest, emit_manifest


def _file_sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _baseline_hashes(baseline_dir):
    """نقشهٔ relpath -> sha256 برای نصبِ مبدأ. فایلهای وضعیتِ کاربر را نادیده
    می‌گیریم (همان قاعدهٔ طلایی) تا هیچوقت دیتای کاربر معیارِ مقایسه نشود."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(baseline_dir):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            if fn in EXCLUDE_FILES or os.path.splitext(fn)[1].lower() in EXCLUDE_EXT:
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, baseline_dir).replace("\\", "/")
            try:
                out[rel] = _file_sha256(full)
            except OSError:
                pass
    return out


def sign_patch(patch_path):
    """پچ را با همان کلید minisignِ نصاب امضا می‌کند و مسیرِ .sig را برمی‌گرداند.

    بدونِ امضای معتبر آپدیتِر این پچ را رد می‌کند — دقیقاً مثلِ نصاب.
    """
    if not os.path.exists(SIG):
        print("[WARN] %s missing - patch left UNSIGNED" % SIG)
        return None
    r = subprocess.run([sys.executable, SIG, patch_path], cwd=ROOT)
    sig = patch_path + ".sig"
    if r.returncode != 0 or not os.path.exists(sig):
        print("[ERR] patch signing FAILED (rc=%d) - updater would reject it" % r.returncode)
        sys.exit(1)
    return sig


def _walk_bundle(bundle):
    """relpath -> مسیرِ کامل، با همان قاعدهٔ حذفِ فایل‌هایِ وضعیتِ کاربر."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(bundle):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            if fn in EXCLUDE_FILES or os.path.splitext(fn)[1].lower() in EXCLUDE_EXT:
                continue
            full = os.path.join(dirpath, fn)
            out[os.path.relpath(full, bundle).replace("\\", "/")] = full
    return out


def write_manifest(bundle, out_path, version):
    """فهرستِ هشِ بیلدِ فعلی — لنگهٔ مقایسهٔ پچِ نسخهٔ بعد، بدونِ نصب‌کردنِ چیزی.

    چرا: ساختنِ پچ در CI تا پیش‌از‌این یعنی دانلودِ نصابِ ۶۰ مگابایتیِ نسخهٔ
    قبلی و اجرایِ سایلنتِ آن روی رانر. آن کار چند دقیقه طول می‌کشد و به
    محیطِ رانر حساس است (نصبِ همان فایلِ سالم روی رانر با کد ۱ شکست خورد، در
    حالی که روی ماشینِ توسعه کد ۰ می‌دهد). فایلِ JSON چند صد کیلوبایت است و
    هیچ اجرایی ندارد.
    """
    import json
    files = {}
    for rel, full in sorted(_walk_bundle(bundle).items()):
        try:
            files[rel] = _file_sha256(full)
        except OSError:
            continue
    if not files:
        print("[ERR] manifest خالی شد: %s" % bundle)
        sys.exit(1)
    payload = {"version": version, "git": git_short(),
               "generated": datetime.datetime.now().isoformat(timespec="seconds"),
               "files": files}
    parent = os.path.dirname(os.path.abspath(out_path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=True, indent=0, sort_keys=True)
    print("[OK] manifest نوشته شد: %s (%d فایل، نسخهٔ %s)" % (out_path, len(files), version))


def main():
    from_version, baseline, dist_arg, baseline_manifest, emit_manifest = _parse_args(sys.argv)
    dist_root = dist_arg if os.path.isabs(dist_arg) else os.path.join(ROOT, dist_arg)
    bundle = os.path.join(dist_root, "BorsTerminal_Ultimate")
    exe = os.path.join(bundle, "BorsTerminal_Ultimate.exe")
    if not os.path.exists(exe):
        print("[ERR] %s missing - run scripts/build_exe.py first" % exe)
        sys.exit(1)
    if emit_manifest:
        write_manifest(bundle, emit_manifest, app_version())
        return
    bat = open(BAT, "rb").read()
    if b"\r\n" not in bat:
        print("[ERR] apply_update.bat must keep CRLF line endings")
        sys.exit(1)

    version, sha = app_version(), git_short()
    if from_version == version:
        print("[ERR] patch from == to (%s); a patch must move between versions"
              % version)
        sys.exit(1)
    # v1.0.10: نامِ پچ نسخه‌دار است تا چند پچ روی یک ریلیز بتوانند کنار هم
    # باشند و latest.json دقیقاً به همین فایل اشاره کند.
    out = os.path.join(dist_root,
                       "BorsTerminal_Patch_%s_to_%s.zip" % (from_version, version))
    alias = os.path.join(dist_root, "BorsTerminal_Update.zip")
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    version_txt = "app_version=%s\npatch_from=%s\ngit_commit=%s\nbuilt=%s\n" % (
        version, from_version, sha, stamp)

    # دلتای واقعی: اگر نصبِ مبدأ موجود باشد، فقط فایلهای تغییرکرده/جدید را
    # می‌فرستیم. این تنها راهِ رسیدن به «فقط تغییرات دانلود شود» است؛ وگرنه
    # پچِ overlayِ کامل تقریباً به اندازهٔ نصبِ کامل است و فایده‌ای ندارد.
    base_hashes = {}
    if baseline_manifest:
        import json
        try:
            with open(baseline_manifest, encoding="utf-8") as f:
                manifest = json.load(f)
        except (OSError, ValueError) as exc:
            print("[ERR] --baseline-manifest خوانده نشد (%s): %s"
                  % (baseline_manifest, exc))
            sys.exit(1)
        base_hashes = dict(manifest.get("files") or {})
        if not base_hashes:
            print("[ERR] --baseline-manifest هیچ فایلی ندارد: %s" % baseline_manifest)
            sys.exit(1)
        if str(manifest.get("version") or "") != from_version:
            print("[ERR] manifestِ مبدأ نسخهٔ %r دارد ولی --from=%r است؛ "
                  "پچِ اشتباه ساخته نشود" % (manifest.get("version"), from_version))
            sys.exit(1)
        print("[delta] manifest: %s  (%d فایل، نسخهٔ %s)"
              % (baseline_manifest, len(base_hashes), manifest.get("version")))
    elif baseline:
        if not os.path.isdir(baseline):
            print("[ERR] --baseline dir not found: %s" % baseline)
            sys.exit(1)
        base_hashes = _baseline_hashes(baseline)
        print("[delta] baseline: %s  (%d files hashed)" % (baseline, len(base_hashes)))

    if os.path.exists(out):
        os.remove(out)
    kept = skipped = unchanged = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for dirpath, dirnames, filenames in os.walk(bundle):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            for fn in filenames:
                if fn in EXCLUDE_FILES or os.path.splitext(fn)[1].lower() in EXCLUDE_EXT:
                    skipped += 1
                    continue
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, bundle).replace("\\", "/")
                if base_hashes:
                    try:
                        if base_hashes.get(rel) == _file_sha256(full):
                            unchanged += 1
                            continue
                    except OSError:
                        pass
                zf.write(full, rel)
                kept += 1
        zf.writestr("Version.txt", version_txt)
        zf.writestr("apply_update.bat", bat)

    sig = sign_patch(out)

    # نامِ ثابتِ قدیمی را هم نگه می‌داریم تا ابزارهای قدیمی (و گاردِ فعلی) که
    # dist/BorsTerminal_Update.zip را می‌شناسند همچنان کار کنند.
    import shutil
    shutil.copyfile(out, alias)

    print("patch  : %s" % out)
    print("  alias: %s" % alias)
    if sig:
        print("  sig  : %s" % sig)
    if unchanged:
        print("from=%s to=%s commit=%s changed=%d unchanged=%d skipped_user_state=%d"
              " size=%.1f MB" % (from_version, version, sha, kept + 2, unchanged,
                                 skipped, os.path.getsize(out) / 1048576))
    else:
        print("from=%s to=%s commit=%s files=%d skipped_user_state=%d size=%.1f MB"
              % (from_version, version, sha, kept + 2, skipped,
                 os.path.getsize(out) / 1048576))


if __name__ == "__main__":
    main()
