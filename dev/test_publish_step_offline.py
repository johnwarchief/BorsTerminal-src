# -*- coding: utf-8 -*-
"""dev/test_publish_step_offline.py — شبیه‌سازیِ غیرانتشاریِ گامِ «Publish Android release»

چرا: اصلاحِ مسیرِ notes (A99) فقط با `bash -n` و رندرِ heredoc سنجیده شده بود.
اینجا همان تکهٔ واقعیِ اسکریپتِ ران، بیرون ازِ CI و **بدونِ هیچ تماسِ شبکه** اجرا
می‌شود: `gh` به یکِ shimِ ثبت‌کننده تبدیل می‌شود که هیچ‌جا publish نمی‌کند.

سناریوها:
  S1  ریلیز موجود است (idempotent) → create نباید صدا زده شود، edit باید با
      همان فایلِ notes صدا زده شود، و بدنهٔ بازخوانی‌شده باید هشِ همین build
      را داشته باشد ⇒ خروجِ صفر.
  S2  بدنهٔ ریلیز هنوز هشِ قدیمی را دارد ⇒ گام باید با پیامِ «هنوز هشِ این
      build را ندارد» و کدِ غیرصفر بمیرد (کنترلِ منفی).
  S3  ریلیز موجود نیست ⇒ create صدا زده می‌شود و edit هم برایِ هم‌ردیف‌ماندن.
  S4  فرمانِ چکِ asset باید **یک** آرگومانِ موقعیتی بفرستد — همان دامی که درِ
      ران 38817210463 با «accepts at most 1 arg(s), received 2» لو رفت.

اجرا:  python dev/test_publish_step_offline.py
"""
from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import yaml

WORKFLOW = ".github/workflows/mobile.yml"
STEP = "Publish Android release"
SUM = "4adca3602a5815a638f0106ffca37792c0ea65a0c5b737f6e4110b1467c63506"
OLD_SUM = "5655afa1432fce2feeed6959880be23412270808d3c22fa72fed9b16e03ae432"
PUB_NAME = "bors-terminal-android-1.1.0.apk"

results = []


def chk(ok: bool, label: str) -> bool:
    results.append(bool(ok))
    print(("  ok   " if ok else "  FAIL ") + label)
    return bool(ok)


def publish_segment() -> str:
    """تیکۀ واقعیِ notes→create→edit→چکِ بدنه→upload→چکِ asset نام از اسکریپتِ ران."""
    d = yaml.safe_load(io.open(WORKFLOW, encoding="utf-8"))
    body = ""
    for jd in d["jobs"].values():
        for s in jd.get("steps", []):
            if s.get("name") == STEP:
                body = s["run"]
    if not body:
        raise AssertionError("step not found in workflow")
    lines = body.splitlines()
    try:
        i = next(k for k, l in enumerate(lines) if l.strip() == "mkdir -p _pubcheck")
        # فقط تا چکِ بدنه — خطوطِ آپلود/asset درِ رانِ واقعی 38819805470 سبز
        # بودند و A96 آن‌ها را می‌پاید؛ اینجا هدفِ تستِ آفلاین همان notes است.
        j = next(k for k, l in enumerate(lines) if 'grep -q "$SUM"' in l)
    except StopIteration:
        raise AssertionError("segment bounds not found — the step was restructured")
    return "\n".join(lines[i:j + 1])


def posix(p: str) -> str:
    """مسیرِ داخلِ اسکریپت باید فرمِ MSYS باشد (/c/Users/…): `bash` این ماشین
    «C:/…» را به‌عنوان آرگومانِ اسکریپت نمی‌پذیرد و فایل‌عملیات هم با آن
    گیج می‌شوند. اجرای خودِ اسکریپت هم با `bash -s` و stdin است، بی‌مسیر."""
    q = p.replace(chr(92), "/")
    m = re.match(r"^([A-Za-z]):/(.*)$", q)
    return ("/" + m.group(1).lower() + "/" + m.group(2)) if m else q


def gh_func(body_returned: str, release_exists: str = "0") -> str:
    """به‌جای shim رویِ PATH (رویِ ویندوز exec-bit دردسر دارد) یکِ تابعِ bash
    تعریف می‌کنیم: تابع بر جست‌وجویِ PATH مقدم است و همان `gh …`هایِ گام را
    می‌گیرد. هیچ تماسِ شبکه‌ای رخ نمی‌دهد."""
    return (
        "gh() {\n"
        "  printf '%s\\n' \"$*\" >> \"$GHLOG\"\n"
        "  case \"$*\" in\n"
        "    *\"--json assets\"*) printf '%s\\napp-release.apk\\n' \"" + PUB_NAME + "\"; return 0;;\n"
        "    *\"--json body\"*)   printf '%s\\n' " + repr(body_returned).replace("'", "'\"'\"'") + "; return 0;;\n"
        "  esac\n"
        "  case \"$*\" in\n"
        "    *\"release view\"*) return " + release_exists + ";;\n"
        "  esac\n"
        "  return 0\n"
        "}\n"
    )


def run_case(tmp: str, gh_setup: str, skip_create: str = "1") -> tuple[int, str, list[str]]:
    seg = publish_segment()
    logf = "./gh_calls.txt"
    apk = "./app-release.apk"
    with io.open(os.path.join(tmp, "app-release.apk"), "wb") as fh:
        fh.write(b"PK\x05\x06" + b"\x00" * 20)   # فقط برایِ cp/sha256sum

    pre = (
        gh_setup
        + "export GHLOG=\"" + logf + "\"\n"
        + "TAG=\"android-1.1.0\"\n"
        + "PUB_NAME=\"" + PUB_NAME + "\"\n"
        + "SUM=\"" + SUM + "\"\n"
        + "SIZE=1\n"
        + "APK=\"" + apk + "\"\n"
        + "PRERELEASE_FLAG=\"--prerelease\"\n"
        + "SKIP_CREATE=" + skip_create + "\n"
        # روی این ماشین متغیر env تازه به Git Bash نمی‌رسد (آزموده شد:
        # subprocess(env=…) با BORS_VERSION_NAME → bash خالی می‌بیند، و با env
        # حداقلی bash خطای رجیستری می‌دهد). پس هرچه گام می‌خواند همین‌جا
        # نوشته می‌شود؛ آزمون بی‌هیچ وابستگی به محیطِ بیرونی است.
        + "PUBLISH_REPO=\"example.invalid/nowhere\"\n"
        + "BORS_VERSION_NAME=1.1.0\n"
        + "BORS_VERSION_CODE=1001000\n"
        + "GITHUB_SHA=" + "0" * 40 + "\n"
        + "BASE=" + "b" * 40 + "\n"
        + "APK_CERT_SHA256=1A:4D\n"
        + "VERIFIED=verified\n"
        + "SNAPSHOT_SERIES=mobile-latest-v2\n"
        + "SNAP_BYTES=1\nSNAP_STAMP=t\nSNAP_PACKAGE_ID=p\n"
        + "SNAP_SCHEMA_VERSION=2\nSNAP_DB_SCHEMA=1\nSNAP_GZ_SHA=g\n"
        + "DOWNLOAD=\"https://example.invalid/$TAG/" + PUB_NAME + "\"\n"
    )
    script = os.path.join(tmp, "full.sh")
    body = "set -e\n" + pre + seg + "\n"
    with io.open(script, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)

    env = dict(os.environ)
    env.update({
        "PUBLISH_REPO": "example.invalid/nowhere",
        "BORS_VERSION_NAME": "1.1.0",
        "BORS_VERSION_CODE": "1001000",
        "GITHUB_SHA": "0" * 40,
        "APK_CERT_SHA256": "1A:4D",
        "SNAPSHOT_SERIES": "mobile-latest-v2",
        "SNAP_BYTES": "1", "SNAP_STAMP": "t", "SNAP_PACKAGE_ID": "p",
        "SNAP_SCHEMA_VERSION": "2", "SNAP_DB_SCHEMA": "1", "SNAP_GZ_SHA": "g",
        "VERIFIED": "verified", "BASE": "b" * 40,
        "GITHUB_STEP_SUMMARY": posix(os.path.join(tmp, "summary.md")),
    })
    p = subprocess.run(["bash", "./full.sh"], cwd=tmp, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env)
    lf = os.path.join(tmp, "gh_calls.txt")
    raw = io.open(lf, encoding="utf-8").read() if os.path.exists(lf) else ""
    calls = [l for l in raw.splitlines() if l.strip()]
    # logِ خالی یعنی هیچ gh صدا زده نشده — این نباید «create نشد» را سبز کند
    if not calls:
        raise AssertionError("gh shim was never called; rc=%d err=%s" % (p.returncode, (p.stderr or "")[:160]))
    return p.returncode, (p.stdout or "") + (p.stderr or ""), calls



# ── S1: ریلیز موجود است ⇒ create نه، edit بله ───────────────────────────────
tmp = tempfile.mkdtemp(prefix="bors-pub-s1-")
try:
    rc, out, calls = run_case(tmp, gh_func("sha256: " + SUM + " · 1 بایت"))
    create = [c for c in calls if "release create " in c]
    edit = [c for c in calls if "release edit " in c]
    notesf = os.path.join(tmp, "_pubcheck", "release_notes.md")
    notes = io.open(notesf, encoding="utf-8").read() if os.path.exists(notesf) else ""
    chk(rc == 0, "S1 گام با خروجِ صفر تمام شد (rc=%d) %s" % (rc, out.strip()[:90]))
    chk(not create, "S1 با ریلیزِ موجود، create صدا زده نشد (idempotent)")
    chk(len(edit) == 1, "S1 متنِ ریلیز با edit تازه شد (%d فراخوانی)" % len(edit))
    chk(SUM in notes, "S1 فایلِ notes هشِ همین build را دارد")
    chk("example.invalid" in notes and "1.1.0" in notes, "S1 متغیرهایِ notes واقعاً گسترش یافتند")
    chk(all(c.startswith("release ") and c.count("android-1.1.0") == 1 for c in calls),
        "S1 هر فراخوانِ gh دقیقاً یکِ برچسبِ ریلیز دارد (دامِ آرگومانِ دوم)")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ── S2: کنترلِ منفی — بدنه هنوز هشِ قدیمی دارد ─────────────────────────────
tmp = tempfile.mkdtemp(prefix="bors-pub-s2-")
try:
    rc, out, calls = run_case(tmp, gh_func("sha256: " + OLD_SUM + " · 1 بایت"))
    chk(rc != 0, "S2 بدنهٔ کهنه ⇒ گام باید بمیرد (rc=%d)" % rc)
    chk("متن ریلیز هنوز" in out, "S2 پیامِ علت را می‌گوید، نه یکِ شکستِ بی‌نام")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ── S3: ریلیز موجود نیست ⇒ create هم edit هم ───────────────────────────────
tmp = tempfile.mkdtemp(prefix="bors-pub-s3-")
try:
    rc, out, calls = run_case(tmp, gh_func("sha256: " + SUM, release_exists="1"), skip_create="0")
    chk(rc == 0, "S3 مسیرِ ریلیزِ تازه با خروجِ صفر (rc=%d) %s" % (rc, out.strip()[:80]))
    chk(any("release create " in c for c in calls), "S3 create صدا زده شد")
    chk(any("release edit " in c for c in calls), "S3 edit هم اجرا شد (همیشه تازه)")
    chk(not any('--notes "' in c for c in calls), "S3 یادداشت از فایل است، نه رشتهٔ درون‌خطی")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ── S4: بازتولیدِ شکلِ خطایِ رانِ واقعی ─────────────────────────────────────
broken = 'gh release view "android-1.1.0" --json assets --jq \'.assets[].name\' ' \
         + chr(92) + 'n | grep -q x'
positional = [w for w in broken.split()
              if not w.startswith("-") and w not in ("gh", "release", "view", "|")]
chk(any(w.strip(chr(34)) == "android-1.1.0" for w in positional)
    and any(w == chr(92) + "n" for w in broken.split()),
    "S4 شکلِ باگ‌آلود «\\ + n» واقعاً یکِ آرگومانِ موقعیتیِ اضافه می‌سازد "
    "(gh 2.100: accepts at most 1 arg)")
seg = publish_segment()
chk(chr(92) + "n" not in seg.replace(chr(92) + chr(92) + "n", ""),
    "S4 درِ گامِ فعلی هیچ «\\n» دونویسه‌ای نمانده است")

passed = sum(results)
failed = len(results) - passed
print("test_publish_step_offline: %d passed / %d failed" % (passed, failed))
sys.exit(1 if failed else 0)
