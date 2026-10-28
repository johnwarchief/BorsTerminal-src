# -*- coding: utf-8 -*-
"""scripts/publish_codal_snapshot.py — انتشارِ snapshotِ کدال روی تگِ پایدار.

این ماژول همان حلقهٔ آخرِ خطِ لولهٔ خودکارِ کدال است (بدون ADB): سه فایلِ
اجباری — ``codal.db.lzma``، ``codal.db.lzma.sig`` و ``codal.meta.json`` — و
در صورتِ وجود، ``calendar.json`` را با ``gh release upload ... --clobber``
روی تگِ ``data-codal`` در مخزنِ توزیع می‌گذارد. اگر تگ نباشد، اول به‌صورتِ
prerelease ساخته می‌شود. کلاینت از همین تگ می‌خواند تا snapshot به ریلیزِ
برنامه Coupling نشود (api/_sync_codal.py).

last-known-good: آخرین مجموعهٔ *موفق* در ``LAST`` کپی می‌شود؛ ``rollback``
همان مجموعه را دوباره آپلود می‌کند. اگر آپلود شکست بخورد، last_good دست
نخورده می‌ماند و خطا برگردانده می‌شود — هرگز «موفق» جعلی ساخته نمی‌شود.

``BORS_GH`` فرمانِ gh را بازنویسی می‌کند (تست‌ها یک اسکریپتِ پایتونِ جعلی
می‌گذارند). روی ویندوز در ``BORS_GH`` مسیرها را در گیومه بگذارید؛
``shlex.split`` در حالتِ POSIX بک‌اسلش‌هایِ مسیرِ بی‌گیومه را می‌خورد.

استفاده:
    python scripts/publish_codal_snapshot.py codal.db.lzma \\
        codal.db.lzma.sig codal.meta.json [--calendar calendar.json]
    python scripts/publish_codal_snapshot.py --rollback
    python scripts/publish_codal_snapshot.py ... --dry-run
"""
import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)       # برای import bors_config در اجرای CLI

import bors_config  # noqa: E402

REPO = "johnwarchief/BorsTerminal"
DEFAULT_TAG = "data-codal"
MANDATORY = ("codal.db.lzma", "codal.db.lzma.sig", "codal.meta.json")
CALENDAR_NAME = "calendar.json"
LAST = os.path.join(ROOT, "last_good")
WORK_DIR = bors_config.WORK_DIR
STATIC_CALENDAR = os.path.join(ROOT, "static", "calendar", "cache.json")


def _gh():
    """فرمانِ gh از ``BORS_GH`` (پیش‌فرض: ``gh``) به‌صورتِ argv.

    fallbackِ ویندوز: ``shlex.split`` در حالتِ POSIX بک‌اسلش را escape
    می‌کند، پس ``C:\\Python\\python.exe`` به ``C:Pythonpython.exe`` تبدیل
    می‌شود. اگر توکنِ اول وجود نداشت، یک بار در حالتِ غیرِPOSIX هم تلاش
    می‌کنیم (گیومه‌ها را دستی برمی‌داریم).
    """
    raw = (os.environ.get("BORS_GH") or "gh").strip() or "gh"
    argv = shlex.split(raw)
    if not argv:
        return ["gh"]
    if not (os.path.isfile(argv[0]) or shutil.which(argv[0])):
        alt = [t.strip("\"'") for t in shlex.split(raw, posix=False)]
        if alt and (os.path.isfile(alt[0]) or shutil.which(alt[0])):
            return alt
    return argv


def _calendar_source(calendar=None):
    """مسیرِ فایلِ تقویم: آرگومانِ صریح > WORK_DIR > static؛ فقط اگر باشد.

    آرگومانِ صریحِ ناموجود به معنیِ «تقویمی نده» است و به فایلِ دیگری
    سقوط نمی‌کند؛ زنجیرهٔ fallback فقط وقتی است که آرگومانی نداده باشند.
    """
    if calendar is not None:
        return calendar if os.path.isfile(calendar) else None
    for cand in (os.path.join(WORK_DIR, "calendar.json"), STATIC_CALENDAR):
        if os.path.isfile(cand):
            return cand
    return None


def _proc_error(proc, limit=500):
    text = (proc.stderr or "").strip() or (proc.stdout or "").strip()
    if not text:
        text = "exit %d" % proc.returncode
    return text[-limit:]


def _run(gh, args):
    """اجرای gh بدونِ شبکه‌پراکسیِ اضافی؛ خروجی برای پیامِ خطا گرفته می‌شود."""
    return subprocess.run(gh + args, capture_output=True, text=True)


def keep_last_good(files):
    """کپیِ مجموعهٔ آپلودشده در ``LAST``؛ فایل‌های غایب فقط رد می‌شوند.

    برمی‌گرداند: فهرستِ مسیرهایِ کپی‌شده (برایِ گزارش/تست). این تابع هرگز
    برایِ فایلِ غایب exception نمی‌دهد — یک assetِ اختیاری (تقویم) نباید
    last-known-good را بشکند.
    """
    kept = []
    os.makedirs(LAST, exist_ok=True)
    for path in files:
        if not os.path.isfile(path):
            continue
        dst = os.path.join(LAST, os.path.basename(path))
        shutil.copy2(path, dst)
        kept.append(dst)
    return kept


def _staged_calendar(src):
    """کپیِ موقت با نامِ ``calendar.json`` + دایرکتوریِ موقت.

    منبعِ fallback ممکن است ``cache.json`` باشد؛ نامِ asset در ریلیز باید
    ثابت ``calendar.json`` بماند، پس در صورتِ تفاوت نام یک کپیِ موقت
    می‌سازیم. (آپلودِ gh قابلیتِ rename ندارد.)
    """
    if os.path.basename(src) == CALENDAR_NAME:
        return src, None
    stage = tempfile.mkdtemp(prefix="codal_publish_cal_")
    dst = os.path.join(stage, CALENDAR_NAME)
    shutil.copy2(src, dst)
    return dst, stage


def publish(lzma, sig, meta, tag=DEFAULT_TAG, dry_run=False, calendar=None):
    """آپلودِ snapshotِ امضاشده روی تگِ پایدار؛ dictِ نتیجه برمی‌گرداند.

    dry_run هیچ gh‌ای اجرا نمی‌کند (و فایلِ موقتی هم نمی‌سازد). خطایِ gh
    (یا نبودِ فایلِ اجباری) با ``uploaded False`` + ``error`` برمی‌گردد و
    last_good را دست نمی‌زند.
    """
    missing = [f for f in (lzma, sig, meta) if not os.path.isfile(f)]
    cal_src = _calendar_source(calendar)
    files = [lzma, sig, meta] + ([cal_src] if cal_src else [])

    base = {"tag": tag, "repo": REPO, "files": files, "calendar": cal_src}
    if cal_src:
        base["calendar_asset"] = CALENDAR_NAME

    if missing:
        base.update({"uploaded": False, "dry_run": dry_run,
                     "error": "missing mandatory file(s): %s"
                              % ", ".join(missing)})
        return base

    if dry_run:
        base.update({"uploaded": False, "dry_run": True})
        return base

    # live: asset در ریلیز همیشه calendar.json نام دارد
    stage = None
    if cal_src:
        staged, stage = _staged_calendar(cal_src)
        files = [lzma, sig, meta, staged]
        base["files"] = files

    gh = _gh()
    try:
        view = _run(gh, ["release", "view", tag, "--repo", REPO])
        created = False
        if view.returncode != 0:
            create = _run(gh, ["release", "create", tag, "--repo", REPO,
                               "--title", "CODAL data (latest)",
                               "--prerelease",
                               "--notes", "Automatic CODAL snapshot"])
            if create.returncode != 0:
                base.update({"uploaded": False, "dry_run": False,
                             "created_tag": False,
                             "error": "gh release create %s failed: %s"
                                      % (tag, _proc_error(create))})
                return base
            created = True

        upload = _run(gh, ["release", "upload", tag] + files
                      + ["--repo", REPO, "--clobber"])
        if upload.returncode != 0:
            base.update({"uploaded": False, "dry_run": False,
                         "created_tag": created,
                         "error": "gh release upload %s failed: %s"
                                  % (tag, _proc_error(upload))})
            return base

        kept = keep_last_good(files)
        base.update({"uploaded": True, "dry_run": False,
                     "created_tag": created, "last_good": kept})
        return base
    finally:
        if stage:
            shutil.rmtree(stage, ignore_errors=True)


def rollback(tag=DEFAULT_TAG):
    """آپلودِ دوبارهٔ آخرین مجموعهٔ last-known-good روی ``tag``.

    اگر هیچ last-good اجباری‌ای نباشد، بدونِ تماس با gh خطا برمی‌گردد
    (rollbackِ بی‌محتوا موفقیتِ جعلی نیست). خروجی gh هم بررسی می‌شود.
    """
    paths = {name: os.path.join(LAST, name)
             for name in MANDATORY + (CALENDAR_NAME,)}
    files = [paths[n] for n in MANDATORY if os.path.isfile(paths[n])]
    present = files + ([paths[CALENDAR_NAME]]
                       if os.path.isfile(paths[CALENDAR_NAME]) else [])
    base = {"tag": tag, "repo": REPO, "files": present}
    if len(files) != len(MANDATORY):
        missing = [n for n in MANDATORY if not os.path.isfile(paths[n])]
        base.update({"rolled_back": False,
                     "error": "incomplete last-known-good in %s (missing: %s)"
                              % (LAST, ", ".join(missing))})
        return base
    files = present
    base["files"] = files

    gh = _gh()
    upload = _run(gh, ["release", "upload", tag] + files
                  + ["--repo", REPO, "--clobber"])
    if upload.returncode != 0:
        base.update({"rolled_back": False,
                     "error": "gh release upload %s failed: %s"
                              % (tag, _proc_error(upload))})
        return base
    base.update({"rolled_back": True})
    return base


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Publish the signed CODAL snapshot to the stable data tag")
    ap.add_argument("lzma", nargs="?", help="path to codal.db.lzma")
    ap.add_argument("sig", nargs="?", help="path to codal.db.lzma.sig")
    ap.add_argument("meta", nargs="?", help="path to codal.meta.json")
    ap.add_argument("--tag", default=DEFAULT_TAG)
    ap.add_argument("--calendar", default=None,
                    help="calendar asset (default: WORK_DIR/calendar.json, "
                         "then static/calendar/cache.json)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rollback", action="store_true",
                    help="re-upload the last-known-good set")
    args = ap.parse_args(argv)

    if args.rollback:
        result = rollback(args.tag)
        ok = result.get("rolled_back") is True
    else:
        if not (args.lzma and args.sig and args.meta):
            ap.error("lzma, sig and meta are required unless --rollback")
        result = publish(args.lzma, args.sig, args.meta, tag=args.tag,
                         dry_run=args.dry_run, calendar=args.calendar)
        ok = (result.get("uploaded") is True
              or (args.dry_run and "error" not in result))
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
