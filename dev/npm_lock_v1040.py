#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/npm_lock_v1040.py -- «npm ci» باید درِ CI هم همان درخت را نصب کند.

چرا این گارد هست: کامیتِ موتورِ چارت (6ebf6a3) وابستگی‌های تازه به package.json
افزود ولی قفل را کامل نکرد. محلی هیچ‌کس نفهمید: node_modules از قبل رویِ دیسک بود
و بیلد/تست از همان برمی‌داشت. درِ CI همان `npm ci` مرد و ریلیزِ ۱٫۰٫۳۹ هرگز ساخته
نشد — نه درِ تست، نه درِ بیلد، فقط درِ «Install Frontend Dependencies» با
`ERESOLVE … peerOptional react@">=19" from @pairlens/fast-financial-charts`.

دو کار می‌کند:
  ۱) ساختاریِ قطعی و بی‌شبکه: هر وابستگیِ package.json باید درِ ریشهٔ قفل با همان
     بازه باشد. همین تنها، گناه اصلی (افزودنِ وابستگیِ بدونِ قفل) را می‌گیرد.
  ۲) واقعی: `npm ci --dry-run` — همان داوریِ خودِ npm رویِ همان قفل. خطایِ
     ERESOLVE/EUSAGE یعنی قفل نصب‌شدنی نیست و ریلیز می‌میرد؛ خطایِ شبکه
     (EALLOWREMOTE و همتاها) گناهِ قفل نیست و فقط هشدار می‌شود.

نکتۀ درمان: `frontend/.npmrc` با legacy-peer-deps=true. بدونِ آن، npm هفتم به بعد
پیرِ «react-klinecharts» را (که react-klinecharts-ui واجب اعلامش کرده ولی تنها
زیرمسیرِ ./chart مصرفش می‌کند و کدِ ما هرگز آن زیرمسیر را import نمی‌کند) خودکار
نصب می‌کند و درِ قفلِ ناقص می‌شکند. اگر .npmrc حذف شود، داوریِ ۲ دوباره قرمز می‌شود
— یعنی گاردِ ما همان چیزی را می‌بیند که CI می‌بیند.
"""
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FE = os.path.join(ROOT, "frontend")

NET_CODES = ("EALLOWREMOTE", "ENOTFOUND", "ECONNRESET", "ERR_SOCKET", "ETIMEDOUT",
             "EAI_AGAIN", "ENETUNREACH", "EPROTO", "CERT_HAS_EXPIRED", "UNABLE_TO_VERIFY")

failed = 0
passed = 0
warned = 0


def ck(cond, msg):
    global failed, passed
    if cond:
        passed += 1
        print(f"  ok   {msg}")
    else:
        failed += 1
        print(f"  FAIL {msg}")
    return cond


def warn(msg):
    global warned
    warned += 1
    print(f"  SKIP {msg}")


def sync_gaps(pkg, lock):
    """(نبودِ وابستگی در قفل، بازه‌هایِ ناهمخوان) — دقیقاً همان گناهِ 6ebf6a3."""
    root = (lock.get("packages") or {}).get("") or {}
    missing, mismatched = [], []
    for field in ("dependencies", "devDependencies"):
        for name, spec in (pkg.get(field) or {}).items():
            got = (root.get(field) or {}).get(name)
            if got is None:
                missing.append(name)
            elif got != spec:
                mismatched.append(f"{name}: package.json={spec} lock={got}")
    return missing, mismatched


def classify(rc, blob):
    """تصمیم‌گیری روی خروجیِ `npm ci --dry-run`: خطایِ قفل یا خطایِ شبکه؟"""
    if rc == 0:
        return "ok"
    strict = any(k in blob for k in ("ERESOLVE", "EUSAGE", "Missing:", "out of sync"))
    net = any(c in blob for c in NET_CODES)
    if net and not strict:
        return "net"
    return "strict"


def selftest():
    """کنترلِ منفی: داده‌هایِ ساختگی باید داوری را بشکانند، نه خودِ داوری را."""
    pkg = {"dependencies": {"react": "^18.3.1", "klinecharts": "^10.0.3"}}
    good = {"lockfileVersion": 3, "packages": {"": {"dependencies": {
        "react": "^18.3.1", "klinecharts": "^10.0.3"}}}}
    m, mm = sync_gaps(pkg, good)
    ck(not m and not mm, "خودسنجی: قفلِ همخوان سبز است")

    # گناهِ اصلی: وابستگی به package.json اضافه شده ولی درِ قفل نیست
    noLock = {"lockfileVersion": 3, "packages": {"": {"dependencies": {"react": "^18.3.1"}}}}
    m, mm = sync_gaps(pkg, noLock)
    ck(m == ["klinecharts"], f"خودسنجی: وابستگیِ ثبت‌نشده لو می‌رود ({m})")

    # بازه‌هایِ ناهمخوان (بumpی که فقط یک طرف انجام شده)
    drift = {"lockfileVersion": 3, "packages": {"": {"dependencies": {
        "react": "^17.0.0", "klinecharts": "^10.0.3"}}}}
    m, mm = sync_gaps(pkg, drift)
    ck(len(mm) == 1 and "react" in mm[0], f"خودسنجی: بازهٔ ناهمخوان لو می‌رود ({mm})")

    # متنِ واقعیِ شکستِ CI درِ ریلیزِ ۱٫۰٫۳۹
    ci_1039 = ("npm error code ERESOLVE\nnpm error ERESOLVE could not resolve\n"
               'npm error peerOptional react@">=19" from '
               "@pairlens/fast-financial-charts@2.2.0")
    ck(classify(1, ci_1039) == "strict", "خودسنجی: ERESOLVE خطایِ قفل است")

    local_eusage = ("npm error code EUSAGE\nnpm error Missing: "
                    "react-klinecharts@1.0.1 from lock file")
    ck(classify(1, local_eusage) == "strict", "خودسنجی: قفلِ ناقص خطایِ قفل است")

    blocked = ('npm error code EALLOWREMOTE\nnpm error Fetching packages of type '
               '"remote" have been disabled')
    ck(classify(1, blocked) == "net", "خودسنجی: انسدادِ شبکه قفل را متهم نمی‌کند")

    ck(classify(0, "") == "ok", "خودسنجی: خروجِ صفر سبز است")
    print(f"\nselftest: {passed + failed} checks, {failed} failed")
    return 1 if failed else 0


def main():
    if "--selftest" in sys.argv:
        return selftest()

    with open(os.path.join(FE, "package.json"), encoding="utf-8") as f:
        pkg = json.load(f)
    with open(os.path.join(FE, "package-lock.json"), encoding="utf-8") as f:
        lock = json.load(f)

    missing, mismatched = sync_gaps(pkg, lock)

    ck(lock.get("lockfileVersion") == 3, "قفلِ npm نسخهٔ ۳ است")
    ck(not missing, f"هر وابستگیِ package.json درِ قفل هم ثبت شده (نبود: {missing or '—'})")
    ck(not mismatched, f"بازه‌ها درِ قفل و package.json یکی است ({mismatched or '—'})")

    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        warn("npm در این ماشین نیست؛ داوریِ ساختاری بس است")
    else:
        try:
            p = subprocess.run([npm, "ci", "--dry-run"], cwd=FE, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=420)
        except subprocess.TimeoutExpired:
            warn("npm ci --dry-run بیشتر از ۴۲۰ ثانیه کشید (شبکه؟)")
            p = None
        if p is not None:
            blob = (p.stdout or "") + (p.stderr or "")
            errs = " | ".join(l.strip() for l in blob.splitlines()
                              if l.strip().startswith("npm error"))[:300]
            verdict = classify(p.returncode, blob)
            if verdict == "ok":
                ck(True, "npm ci --dry-run: قفل بی‌خطا نصب می‌شود")
            elif verdict == "net":
                warn(f"خطایِ شبکه، نه خطایِ قفل: {errs[:180]}")
            else:
                ck(False, f"npm ci درِ CI هم می‌میرد: {errs}")

    npmrc = os.path.join(FE, ".npmrc")
    has_relax = os.path.isfile(npmrc) and "legacy-peer-deps=true" in open(npmrc, encoding="utf-8").read()
    if has_relax:
        print("  info frontend/.npmrc پیرها را بی‌اعتبار کرده (دلیلش در سرِ همین فایل)")
    else:
        print("  info frontend/.npmrc نیست — اگر npm ci بالا قرمز شد، همین علت است")

    print(f"\n{passed + failed} checks, {failed} failed, {warned} skipped")
    print("NPM LOCK GUARD " + ("OK" if not failed else "FAILED"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
