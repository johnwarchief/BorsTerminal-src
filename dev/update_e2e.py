# -*- coding: utf-8 -*-
"""dev/update_e2e.py — تستِ واقعیِ زنجیرهٔ آپدیتِ درون‌برنامه‌ای، بدونِ انتشار در گیت‌هاب.

آپدیتِر برای مانیفست به `BORS_UPDATE_MANIFEST` گوش می‌دهد (api/update.py) و اگر
urlِ پچ یک مسیرِ فایلِ محلی باشد، همان‌جا کپی می‌کند (میان‌برِ dev). پس می‌توان
کلِ جریانِ «تشخیص ← دانلود ← راستی‌آزماییِ minisign ← اعمال ← اجرای دوباره» را
روی همین ماشین طی کرد، بدونِ آنکه چیزی publish شود.

    python -X utf8 dev/update_e2e.py                # فقط تشخیص + دانلود + بررسیِ امضا
    python -X utf8 dev/update_e2e.py --apply        # تا نصب و اجرای دوباره هم برود
    python -X utf8 dev/update_e2e.py --dist dist2   # باندل/پچ از dist2

خروجی: هر مرحله با PASS/FAIL و عددِ حجم. اگر --apply ندهید، چیزی نصب نمی‌شود.
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                       "Programs", "BorsTerminal Ultimate")
APP_EXE = os.path.join(APP_DIR, "BorsTerminal_Ultimate.exe")
MANIFEST = os.path.join(os.environ.get("TEMP", ROOT), "bors_latest_e2e.json")
BASE_DEFAULT = "http://127.0.0.1:8001"

results = []


def say(step, ok, detail=""):
    results.append((step, bool(ok)))
    print("%-4s %s%s" % ("PASS" if ok else "FAIL", step, ("  — " + detail) if detail else ""))
    return bool(ok)


def find_artifacts(dist):
    root = os.path.join(ROOT, dist)
    # تازه‌ترینِ ساخته‌شده، نه «آخرِ ترتیبِ الفبایی»: 1.0.21 پیش از 1.0.9 مرتب می‌شود
    patches = sorted(glob.glob(os.path.join(root, "BorsTerminal_Patch_*_to_*.zip")),
                     key=os.path.getmtime)
    setups = sorted(glob.glob(os.path.join(root, "**", "BorsTerminal_Ultimate_Setup_v*.exe"),
                              recursive=True))
    if not patches:
        raise SystemExit("[ERR] no patch zip under %s - run: .\\release.ps1 allpatch -Dist %s"
                         % (root, dist))
    patch = patches[-1]
    setup = [s for s in setups if os.path.basename(APP_DIR) in s or True]
    return patch, patch + ".sig", (setup[-1] if setup else "")


def wait_http(base, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(base + "/api/update/version", timeout=3)
            if r.ok:
                return r.json().get("version")
        except requests.RequestException:
            pass
        time.sleep(1.5)
    return None


def restart_with_manifest(base, manifest_path):
    """نصب‌شده را می‌بندد و با BORS_UPDATE_MANIFEST دوباره بالا می‌آورد."""
    subprocess.run(["taskkill", "/IM", "BorsTerminal_Ultimate.exe", "/T", "/F"],
                   capture_output=True)
    time.sleep(3.0)
    env = dict(os.environ, BORS_UPDATE_MANIFEST=manifest_path)
    # پرچمِ DETACHED_PROCESS با CREATE_NEW_CONSOLE با هم نامعتبرند (WinError 87)؛
    # برای یک اپ GUI هیچ‌کدام لازم نیست — Popen بی‌درنگ برمی‌گردد.
    subprocess.Popen([APP_EXE], cwd=APP_DIR, env=env, close_fds=True)
    return wait_http(base)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE_DEFAULT)
    ap.add_argument("--dist", default="dist")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(APP_EXE):
        raise SystemExit("[ERR] installed app not found: %s" % APP_EXE)
    patch, sig_path, setup = find_artifacts(args.dist)
    sig = open(sig_path, encoding="utf-8").read() if os.path.isfile(sig_path) else ""
    if not sig:
        raise SystemExit("[ERR] %s missing - unsigned patch must never be applied" % sig_path)

    size = os.path.getsize(patch)
    to_ver = os.path.basename(patch).split("_to_")[1].split(".zip")[0]
    from_ver = os.path.basename(patch).split("Patch_")[1].split("_to_")[0]

    # مانیفستِ تستی: همان شکلِ latest.json، فقط urlها محلی‌اند.
    json.dump({
        "version": to_ver,
        "notes": "تستِ محلیِ زنجیرهٔ آپدیت (انتشار نیافته)",
        "pub_date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platforms": {"windows-x86_64": {
            "url": setup or patch, "signature": sig, "size": size}},
        "patches": [{"from": from_ver, "to": to_ver, "url": patch,
                     "signature": sig, "size": size}],
    }, open(MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say("مانیفستِ تستی نوشته شد", True, "%s (patch %.2f MB)" % (MANIFEST, size / 1e6))

    # مانیفست فقط هنگامِ شروعِ پروسه خوانده می‌شود، پس همیشه از نو بالا می‌آید؛
    # وگرنه یک نسخهٔ در حالِ اجرا با مانیفستِ دیگری جواب را تحریف می‌کند.
    cur = restart_with_manifest(args.base, MANIFEST)
    if not cur:
        return say("برنامهٔ نصب‌شده بالا نیامد", False, APP_EXE) or 1
    say("نسخهٔ در حالِ اجرا", cur == from_ver, "current=%s patch_from=%s" % (cur, from_ver))

    chk = requests.get(args.base + "/api/update/check", timeout=60).json()
    say("check: نسخهٔ جدید دیده شد", chk.get("available") is True,
        "latest=%s" % chk.get("latest_version"))
    say("check: مسیرِ دلتا انتخاب شد (نه نصبِ کامل)", chk.get("delta") is True,
        "size=%s url=%s" % (chk.get("size"), str(chk.get("url"))[-46:]))

    requests.post(args.base + "/api/update/download", json={
        "url": chk.get("url"), "signature": chk.get("signature"),
        "version": chk.get("latest_version")}, timeout=60)
    st = {}
    for _ in range(400):
        st = requests.get(args.base + "/api/update/progress", timeout=15).json()
        if st.get("status") in ("ready", "error"):
            break
        time.sleep(0.7)
    say("دانلود/کپی کامل شد", st.get("status") == "ready",
        "status=%s %s" % (st.get("status"), st.get("message", "")))
    # راستی‌آزماییِ امضا در همان worker انجام می‌شود؛ اگر امضا می‌خواست، هرگز
    # ready نمی‌شد. این سطرِ بعدی فقط ثابت می‌کند فایلِ رویِ دیسک همان است.
    say("امضای minisign پذیرفته شد", st.get("status") == "ready" and not st.get("message"),
        "")

    if not args.apply:
        print("\n(--apply ندادی: چیزی نصب نشد)")
        return 0 if all(ok for _, ok in results) else 1

    try:                       # /install عمداً برنامه را می‌بندد: قطعِ اتصال طبیعی است
        requests.post(args.base + "/api/update/install", timeout=60)
    except requests.RequestException as exc:
        print("      (اتصال بسته شد — همان انتظارِ اعمال‌کننده: %s)" % type(exc).__name__)
    print("      اعمال‌کننده اجرا شد؛ منتظرِ بالا آمدنِ نسخهٔ تازه…")
    new = wait_http(args.base, timeout=300)
    say("اعمال و اجرای دوباره", new == to_ver, "after install version=%s expected=%s" % (new, to_ver))
    vt = os.path.join(APP_DIR, "Version.txt")
    if not os.path.isfile(vt):
        vt = os.path.join(APP_DIR, "_internal", "Version.txt")
    ok_vt = os.path.isfile(vt) and to_ver in open(vt, encoding="utf-8", errors="replace").read()
    say("مهرِ Version.txt در محلِ نصب", ok_vt, vt if not ok_vt else "")

    bad = [s for s, ok in results if not ok]
    print("\n== %d/%d PASS" % (len(results) - len(bad), len(results)))
    for s in bad:
        print("   FAILED:", s)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
