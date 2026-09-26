# -*- coding: utf-8 -*-
"""
scripts/publish_github_release.py
=================================
ایجاد خودکار یا به‌روزرسانی ریلیز موردنظر در گیت‌هاب و آپلود فایل نصب Inno BorsTerminal_Ultimate_Setup_{tag}.exe + latest.json (آپدیت‌ر به نصب Inno اشاره می‌کند).
"""
import os
import sys
import json
import hashlib
import subprocess
import urllib.request
import urllib.parse

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO = "johnwarchief/BorsTerminal"
# TAG is resolved below from RELEASE_TAG (see ROOT block) so CI can override it.
RELEASE_NAME_TEMPLATE = "BorsTerminal Ultimate {tag}"
RELEASE_NOTES_FILE = "docs/RELEASE_NOTES.md"


def release_body(tag):
    """بخشِ همان نسخه از docs/RELEASE_NOTES.md.

    متنِ ثابتِ v1.0.19 در کدِ اسکریپت دست‌نویس مانده بود، پس ریلیزِ ۱٫۰٫۲۰ هم
    همان یادداشت‌های ۱٫۰٫۱۹ را به کاربر نشان می‌داد. حالا اگر بخشِ نسخه پیدا
    نشود صریحاً همان را می‌گوید، نه متنِ نسخهٔ دیگر.
    """
    path = os.path.join(ROOT, RELEASE_NOTES_FILE)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        want = ("## " + tag, "## v" + tag.lstrip("v"), "## " + tag.lstrip("v"))
        lines = text.splitlines()
        out, hit = [], False
        for ln in lines:
            if ln.startswith("## "):
                if hit:
                    break
                hit = ln.strip() in [w.strip() for w in want] or any(
                    ln.strip().startswith(w) for w in want)
                continue
            if hit:
                out.append(ln)
        if hit and any(x.strip() for x in out):
            return "\n".join(out).strip()
        return ("یادداشتِ نسخه‌ای برای %s در %s پیدا نشد. "
                "پیش از انتشارِ نهایی همین فایل را به‌روز کنید." % (tag, RELEASE_NOTES_FILE))
    return "%s ساخته شد؛ %s موجود نیست." % (tag, RELEASE_NOTES_FILE)




ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# CI / CLI may override the tag being published (RELEASE_TAG=v1.0.5). Default
# keeps the local single-release flow working unchanged. The installer name is
# derived from the tag so both always agree with bors_setup.iss output.
def _app_version():
    """نسخه از bors_config.APP_VERSION — تنها لنگه‌ای که کاربر اجرا می‌کند.

    پیش‌تر اینجا یک "v1.0.19" دست‌نویس بود؛ یعنی اسکریپتِ انتشار می‌توانست
    مانیفستِ نسخهٔ قبلی را بسازد و هیچ‌کس متوجه نشود.
    """
    import re
    with open(os.path.join(ROOT, "bors_config.py"), encoding="utf-8") as f:
        m = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', f.read(), re.M)
    if not m:
        raise SystemExit("APP_VERSION in bors_config.py not found - cannot publish")
    return m.group(1)


TAG = os.environ.get("RELEASE_TAG") or ("v" + _app_version())
RELEASE_BODY = release_body(TAG)
# صفحهٔ ریلیز گیت‌هاب جهتِ پیش‌فرضِ چپ‌به‌راست دارد، پس نامِ لاتینِ داخل
# گیومه («Unexpected Application Error») و پرانتزهای پایانِ خط جابه‌جا چاپ می‌شوند.
# فقط بدنهٔ ریلیز پاکت HTML می‌گیرد؛ «notes»ِ latest.json عیناً به آپدیترِ Tauri
# می‌رود و اگر تگ داشته باشد همان تگ را به کاربر نشان می‌دهد.
RELEASE_BODY_RTL = '<div dir="rtl">\n\n%s\n\n</div>' % RELEASE_BODY
print(f"[=] ریلیزِ هدف: {TAG}  (RELEASE_TAG unset means bors_config.APP_VERSION)")
SETUP_EXE = os.path.join(ROOT, "installer", "out", f"BorsTerminal_Ultimate_Setup_{TAG}.exe")
# Tauri updater needs the minisign signature next to the installer asset.
SIG_FILE = SETUP_EXE + ".sig"
# فهرستِ sha256ِ فایل‌های همین بیلد. نسخهٔ بعد پچِ دلتایش را از رویِ همین فایل
# می‌سازد — بدونِ دانلودکردنِ نصاب و بدونِ اجرایِ installer روی رانیِر، که منبعِ
# شکستِ خاموش بود. نبودش ریلیز را متوقف نمی‌کند؛ فقط نسخهٔ بعد مجبور می‌شود
# دوباره باس‌لاین نصب کند.
MANIFEST_JSON = os.path.join(ROOT, "dist", f"BorsTerminal_Manifest_{TAG}.json")

# v1.0.10 -- delta update. هر پچ فقط برای یک نسخهٔ مبدأ اعتبار دارد؛ اگر
# نسخهٔ کاربر با `from` نخواند، آپدیتِر شفافاً به نصبِ کامل برمی‌گردد.
# چندنسخه‌ای (v1.0.25 به بعد): کاربری که دو سه نسخه عقب است باید همان آپدیتِ
# کوچک را بگیرد، نه نصابِ ۵۷ مگابایتی. چون هر پچ diff کاملِ درختِ مبدأ با بیلدِ
# تازه است (نه پچِ زنجیره‌ای)، پچِ 1.0.22→1.0.25 به‌خودِ خودِ cumulative است و
# آرایهٔ patches جای بیش از یک ورودی را دارد. `PATCH_FROM` (اگر داده شود) فقط
# همان یک مبدأ را نگه می‌دارد — برای اجرایِ دستیِ محلی.
import glob as _glob

TARGET_VER = TAG.lstrip("v")
_patch_paths = sorted(_glob.glob(os.path.join(ROOT, "dist", "BorsTerminal_Patch_*_to_%s.zip"
                                              % TARGET_VER)))
_wanted = (os.environ.get("PATCH_FROM") or "").strip()
PATCHES = []
for _p in _patch_paths:
    _stem = os.path.basename(_p).replace("BorsTerminal_Patch_", "").split("_to_")[0]
    if _wanted and _stem != _wanted:
        print(f"[=] پچِ {_stem} نادیده گرفته شد (PATCH_FROM={_wanted})")
        continue
    PATCHES.append({"from": _stem, "zip": _p, "sig": _p + ".sig"})

# فقط پچ‌هایی که امضایشان هم ساخته شده واقعاً منتشر می‌شوند.
for _e in PATCHES:
    if not os.path.isfile(_e["sig"]):
        print("::error::[publish] امضایِ %s نیست؛ این پچ منتشر نمی‌شود"
              % os.path.basename(_e["zip"]))
PATCHES = [e for e in PATCHES if os.path.isfile(e["sig"])]

# سقفِ اندازه: پچ «رویهمگذاری» است و هیچ فایلی را پاک نمی‌کند. هرچه مبدأ دورتر
# باشد هم حجم به نصاب نزدیک‌تر می‌شود (بیشترش همان exe است) و هم فایل‌های بیاتِ
# آن نسخه روی دیسک می‌ماند — نصاب برعکس، پیشِ نصب پوشهٔ قدیمی را پاک می‌کند.
# پس پچی که از سقفِ PATCH_MAX_RATIO نصاب را بگیرد دیگر نه «آپدیتِ کوچک» است و نه
# تمیز: آن مبدأ صریحاً به نصبِ کامل برمی‌گردد (کلاینت نبودِ ورودی‌اش را خودش
# می‌فهمد، پس سمتِ برنامه هیچ تغییری لازم نیست).
PATCH_MAX_RATIO = float(os.environ.get("PATCH_MAX_RATIO") or 0.60)
_setup_size = os.path.getsize(SETUP_EXE) if os.path.isfile(SETUP_EXE) else 0
if _setup_size:
    for _e in list(PATCHES):
        _sz = os.path.getsize(_e["zip"])
        _ratio = _sz / _setup_size
        _e["ratio"] = _ratio
        if _ratio > PATCH_MAX_RATIO:
            PATCHES.remove(_e)
            print("[!] پچِ %s → %s equals %d%% of the installer; that source "
                  "version takes the full installer instead (a patch never "
                  "deletes files)" % (_e["from"], TARGET_VER, int(round(_ratio * 100))))
            print("::error::[patch] %s→%s = %d%% of installer — پچ منتشر نشد"
                  % (_e["from"], TARGET_VER, int(round(_ratio * 100))))
        else:
            print("[=] پچِ %s: %d%% از اندازهٔ نصاب" % (_e["from"], int(round(_ratio * 100))))

if not PATCHES:
    _other = [os.path.basename(x) for x in
              _glob.glob(os.path.join(ROOT, "dist", "BorsTerminal_Patch_*.zip"))
              if not x.endswith(".sig")]
    print("[!] هشدار: پچِ دلتایی با مقصدِ %s در dist نیست؛ ریلیز فقط نصبِ "
          "کامل را معرفی می‌کند.%s"
          % (TAG, (" (روی دیسک: %s)" % ", ".join(_other)) if _other else ""))
else:
    print("[=] پچ‌های قابل‌انتشار: %s" % ", ".join(e["from"] for e in PATCHES))

def get_github_token():
    # Prefer an explicit token from the environment. The release is published to
    # the *public* distribution repo (see REPO), but CI runs in the private
    # source mirror whose default GITHUB_TOKEN is scoped to that mirror only and
    # therefore cannot create releases on the public repo. A PAT (RELEASE_TOKEN)
    # passed in via the environment must win over the persisted git credential.
    env_token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    if env_token:
        return env_token
    # Local fallback: ask the git credential helper. Feed the request via a
    # pipe; an interactive helper with no controlling tty can hang on stdin.
    try:
        proc = subprocess.Popen(
            ["git", "credential", "fill"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        out, _ = proc.communicate(input="protocol=https\nhost=github.com\n", timeout=30)
        for line in out.splitlines():
            if line.startswith("password="):
                return line.split("=", 1)[1].strip()
    except Exception as e:
        print(f"[-] Could not get git credentials: {e}")
    return os.environ.get("GITHUB_TOKEN", "")

def build_latest_json():
    """Tauri v2 updater manifest pointing at the Inno installer.

    Signature is the minisign sig file content (already uploaded as .sig).
    The tauri CLI writes that .sig as a single base64-wrapped line, which is
    exactly the form the updater wants in this field (v1.0.6 shipped the same);
    bors_minisign.parse_minisign_signature decodes it internally, and the raw
    4-line block is recoverable by base64-decoding once if ever needed.
    """
    import datetime
    try:
        from email.utils import formatdate
        pub_date = formatdate(localtime=True, usegmt=True)
    except Exception:
        pub_date = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(SIG_FILE, "r", encoding="utf-8", errors="replace") as f:
        signature = f.read().strip()

    asset_name = os.path.basename(SETUP_EXE)
    version = TAG[1:] if TAG.startswith("v") else TAG
    manifest = {
        "version": version,
        "notes": RELEASE_BODY,
        "pub_date": pub_date,
        "platforms": {
            "windows-x86_64": {
                "signature": signature,
                "url": f"https://github.com/{REPO}/releases/download/{TAG}/{asset_name}",
            }
        },
    }
    # v1.0.10: پچ‌های دلتای اختیاری. آپدیتِر با غیابِ آرایه شفافاً به نصبِ کامل
    # برمی‌گردد، پس ریلیزِ بدونِ پچ همچنان درست کار می‌کند. هر ورودی یک مبدأ
    # است؛ کاربرِ دو سه نسخه عقب از همین‌ها نسخهٔ خودش را برمی‌دارد.
    if PATCHES:
        manifest["patches"] = []
        for e in PATCHES:
            with open(e["sig"], "r", encoding="utf-8", errors="replace") as f:
                patch_signature = f.read().strip()
            patch_name = os.path.basename(e["zip"])
            manifest["patches"].append({
                "from": e["from"],
                "to": version,
                "signature": patch_signature,
                "url": f"https://github.com/{REPO}/releases/download/{TAG}/{patch_name}",
                "size": os.path.getsize(e["zip"]),
            })
            print(f"[+] پچِ دلتا به مانیفست اضافه شد: {e['from']} -> {version}"
                  f" ({os.path.getsize(e['zip']):,} بایت)")
    else:
        print("[*] پچِ دلتایی نیست؛ مانیفست فقط نصبِ کامل را معرفی می‌کند.")
    out_path = os.path.join(ROOT, "latest.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"[+] latest.json ساخته شد: {out_path}")
    print(f"    url -> {manifest['platforms']['windows-x86_64']['url']}")
    return out_path


CODAL_MAX_AGE_DAYS = 21  # سقفِ codal.db.lzmaیِ منتقل‌شده؛ همان مقدارِ STAMPS


def _days_since(iso):
    """سنِ یک ریلیز/asset به روز؛ None اگر تاریخ قابل خواندن نبود.

    None با 0 قاطی نمی‌شود: «نمی‌دانیم» نباید به‌شکلِ «فایل کاملاً تازه است»
    گزارش شود.
    """
    if not iso:
        return None
    from datetime import datetime, timezone
    s = str(iso).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0


def _snapshot_age_days(lzma_path):
    """سنِ خودِ اسنپ‌شات از codal_notices.fetched_at — نه تاریخِ ریلیز.

    تاریخِ ریلیز فقط proxy است: اگر یک فایلِ چندماهه رویِ ریلیزِ امروز
    آپلود شود (دقیقاً کاری که برای v1.0.28 کردیم)، published_at «۰ روز»
    می‌گوید در حالی که داده چند روزه است. هیچ‌وقت صفر برنمی‌گرداند اگر
    خوانده نشد — «نمی‌دانیم» با «تازه است» یکی نمی‌شود.
    """
    import lzma
    import sqlite3
    import tempfile
    from datetime import datetime
    fd, tmp = tempfile.mkstemp(suffix=".db", prefix="codal_age_")
    os.close(fd)
    try:
        with open(lzma_path, "rb") as f:
            raw = lzma.decompress(f.read())
        with open(tmp, "wb") as f:
            f.write(raw)
        conn = sqlite3.connect("file:%s?mode=ro" % tmp.replace(os.sep, "/"), uri=True)
        try:
            stamp = conn.execute(
                "SELECT MAX(fetched_at) FROM codal_notices").fetchone()[0]
        finally:
            conn.close()
        if not stamp:
            return None
        dt = datetime.strptime(str(stamp).strip().replace("T", " ")[:19],
                               "%Y-%m-%d %H:%M:%S")
        # stamp محلیِ تهران و ساعتِ رانر UTC؛ اسنپ‌شاتِ همین‌لحظه «−۰٫۱ روز»
        # می‌شود که نباید عددِ منفی رویِ کنسول برود.
        return max(0.0, (datetime.now() - dt).total_seconds() / 86400.0)
    except Exception:
        return None
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def _codal_age_line(age, label):
    if age is None:
        print(f"[!] سنِ codal.db.lzma ({label}) خوانده نشد — قدمتی گزارش نمی‌شود.")
    elif age > CODAL_MAX_AGE_DAYS:
        print(f"::warning::[data-age] codal.db.lzmaیِ منتقل‌شده ({label}) "
              f"{age:.1f} روز قدیمی است (سقف {CODAL_MAX_AGE_DAYS} روز) — "
              f"بساز: scripts/build_codal_snapshot.py")
    else:
        print(f"[=] codal.db.lzmaیِ منتقل‌شده ({label}) {age:.1f} روز سابقه دارد "
              f"(سقف {CODAL_MAX_AGE_DAYS} روز).")


def main():
    token = get_github_token()
    if not token:
        print("[-] هیچ توکنی یافت نشد.")
        sys.exit(1)

    if not os.path.exists(SETUP_EXE):
        print(f"[-] فایل نصاب در {SETUP_EXE} یافت نشد!")
        sys.exit(1)

    if not os.path.exists(SIG_FILE):
        print(f"[-] فایل امضا {SIG_FILE} یافت نشد! بدون .sig آپدیت‌ر کار نمی‌کند.")
        sys.exit(1)

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "BorsTerminal-Release-Tool"
    }

    # ۱. استعلام ریلیز موجود
    url_releases = f"https://api.github.com/repos/{REPO}/releases"
    req = urllib.request.Request(url_releases, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            releases = json.loads(resp.read().decode())
    except Exception as e:
        print(f"[-] خطا در دریافت لیست ریلیزها: {e}")
        releases = []

    target_release = None
    for r in releases:
        if r.get("tag_name") == TAG:
            target_release = r
            break

    # ۲. ساخت یا بازیابی ریلیز
    if not target_release:
        print(f"[+] در حال ساخت ریلیز {TAG} ...")
        payload = json.dumps({
            "tag_name": TAG,
            "name": RELEASE_NAME_TEMPLATE.format(tag=TAG),
            "body": RELEASE_BODY_RTL,
            "draft": False,
            "prerelease": False
        }).encode("utf-8")
        req = urllib.request.Request(url_releases, data=payload, headers={**headers, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as resp:
                target_release = json.loads(resp.read().decode())
                print(f"[✓] ریلیز {TAG} ساخته شد. ID: {target_release['id']}")
        except urllib.error.HTTPError as e:
            err_content = e.read().decode()
            print(f"[-] خطا در ساخت ریلیز: {e.code} - {err_content}")
            sys.exit(1)
    else:
        print(f"[*] ریلیز {TAG} از قبل وجود دارد. ID: {target_release['id']}")

    # ۳. حذف فایل‌های قدیمی با همین نام اگر قبلا آپلود شده‌اند
    upload_url_template = target_release["upload_url"]
    upload_url_base = upload_url_template.split("{")[0]
    assets = target_release.get("assets", [])
    existing_names = {a.get("name") for a in assets}
    # v1.0.10: نامِ پچ هم در لیستِ پاکسازی است تا جایگزینیِ پچ روی یک ریلیزِ
    # موجود (GitHub روی اسمِ تکراری ۴۲۲ می‌دهد) بدونِ مانع بماند.
    stale_names = {os.path.basename(SETUP_EXE), os.path.basename(SIG_FILE), "latest.json"}
    for e in PATCHES:
        stale_names.add(os.path.basename(e["zip"]))
        stale_names.add(os.path.basename(e["sig"]))
    if os.path.isfile(MANIFEST_JSON):
        stale_names.add(os.path.basename(MANIFEST_JSON))
    for a in assets:
        # latest.json is regenerated per-publish and embeds the current .sig,
        # so a stale copy must be deleted too (GitHub 422s on duplicate names).
        if a.get("name") in stale_names:
            print(f"[*] در حال حذف فایل قدیمی {a.get('name')} (ID {a['id']}) ...")
            del_req = urllib.request.Request(a["url"], headers=headers, method="DELETE")
            try:
                with urllib.request.urlopen(del_req) as resp:
                    pass
            except Exception as e:
                print(f"[!] ناتوان در حذف: {e}")

    # ۴. آپلود فایل جدید + امضای آن (با retries)
    import time

    def upload_asset(local_path, max_retries=4):
        asset_name = os.path.basename(local_path)
        file_size = os.path.getsize(local_path)
        size_mb = file_size / (1024 * 1024)
        upload_url = f"{upload_url_base}?name={urllib.parse.quote(asset_name)}"

        for attempt in range(1, max_retries + 1):
            print(f"[+] آپلود {asset_name} ({size_mb:.2f} MB) - تلاش {attempt}/{max_retries} ...")
            with open(local_path, "rb") as f:
                file_data = f.read()
            upload_headers = {
                "Authorization": f"token {token}",
                "Content-Type": "application/octet-stream",
                "Content-Length": str(file_size),
                "User-Agent": "BorsTerminal-Release-Tool",
            }
            req_upload = urllib.request.Request(upload_url, data=file_data, headers=upload_headers, method="POST")
            try:
                with urllib.request.urlopen(req_upload, timeout=900) as resp:
                    res_data = json.loads(resp.read().decode())
                    print(f"[✓] آپلود موفقیت‌آمیز بود! URL دانلود:")
                    print(f"    {res_data.get('browser_download_url')}")
                    return True
            except urllib.error.HTTPError as e:
                body = e.read().decode(errors="replace")
                print(f"[-] خطای HTTP {e.code} در آپلود {asset_name}: {body[:300]}")
                if e.code in (401, 403, 404, 422):
                    return False
            except Exception as e:
                print(f"[!] خطای شبکه در آپلود {asset_name}: {e!r}")
            if attempt < max_retries:
                wait = 10 * attempt
                print(f"    منتظر {wait}s قبل از تلاش مجدد ...")
                time.sleep(wait)
        return False

    for local_path in (SETUP_EXE, SIG_FILE):
        if not upload_asset(local_path):
            print(f"[-] آپلود {os.path.basename(local_path)} پس از چندین تلاش ناموفق بود.")
            sys.exit(1)

    # v1.0.10: پچ‌های دلتا + امضاهایشان. اختیاری‌اند — اگر ساخته نشده باشند،
    # ریلیز فقط نصبِ کامل را معرفی می‌کند و آپدیتِر شفافاً همان مسیر را می‌رود.
    # یک پچِ ناموفق آپلود نشود کل ریلیز را متوقف می‌کند: کاربرِ آن مبدأ باید
    # بداند که پچ ندارد، نه اینکه مانیفست نصفه‌نیمه بماند.
    for e in PATCHES:
        for local_path in (e["zip"], e["sig"]):
            if not upload_asset(local_path):
                print(f"[-] آپلود {os.path.basename(local_path)} پس از چندین تلاش ناموفق بود.")
                sys.exit(1)
    patch_uploaded = bool(PATCHES)
    if not patch_uploaded:
        print("[*] پچِ دلتایی نیست؛ بدونِ پچ ادامه می‌دهیم.")

    # manifestِ فایل‌های همین بیلد: لنگهٔ مقایسهٔ پچِ نسخهٔ بعد. نبودش ریلیز را
    # متوقف نمی‌کند (فقط نسخهٔ بعد مجبور می‌شود نصابِ این نسخه را دانلود و نصب
    # کند تا فرقِ فایل‌ها را بفهمد)، پس اینجا هشدار است نه خطای مرگبار.
    manifest_path = MANIFEST_JSON
    manifest_uploaded = False
    if os.path.isfile(manifest_path):
        manifest_uploaded = bool(upload_asset(manifest_path))
        if not manifest_uploaded:
            print("[!] آپلودِ manifest ناموفق بود؛ پچِ نسخهٔ بعد به نصبِ باس‌لاین برمی‌گردد.")
            # workflow command: در annotations ثبت می‌شود (لاگ رانر خوانده نمی‌شود)
            print("::error::[publish] آپلودِ %s ناموفق بود" % os.path.basename(manifest_path))
    else:
        print(f"[!] {manifest_path} ساخته نشده؛ این ریلیز لنگهٔ مقایسهٔ پچِ بعد را ندارد.")
        print("::error::[publish] %s نیست؛ نسخهٔ بعد مجبور به نصبِ باس‌لاین می‌شود"
              % os.path.basename(manifest_path))

    # 5) build + upload latest.json (Tauri updater manifest)
    latest_path = build_latest_json()
    if not upload_asset(latest_path):
        print("[-] upload of latest.json failed")
        sys.exit(1)
    try:
        os.remove(latest_path)
    except OSError:
        pass

    if patch_uploaded:
        print(f"[✓] تمام فایل‌ها آپلود شدند ({os.path.basename(SETUP_EXE)} + .sig + "
              f"{len(PATCHES)} پچ + .sig‌هایشان + latest.json) "
              f"[{', '.join(e['from'] for e in PATCHES)}]).")
    else:
        print(f"[✓] تمام فایل‌ها آپلود شدند ({os.path.basename(SETUP_EXE)} + .sig + latest.json).")

    # ۶. راستی‌آزماییِ پس از آپلود — هر فایل از رویِ URLِ خودِ ریلیز دوباره دانلود
    # می‌شود و هشِ آن با فایلِ محلی مقایسه می‌گردد؛ نصب‌کننده و پچ علاوه بر آن
    # با کلیدِ عمومیِ minisign (همان کلیدی که آپدیتِرِ درون‌برنامه‌ای می‌شناسد)
    # تأیید می‌شوند — یعنی دقیقاً همان چیزی که روی دستگاهِ کاربر راستی‌آزمایی
    # می‌شود، اینجا هم راستی‌آزمایی می‌شود.
    # انگیزه: حادثهٔ v1.0.22 — مانتِ autoclaw بایت‌های کهنهٔ exe و .sig را تحویل
    # داد و آپلودِ «موفق»، فایلِ کهنه را منتشر کرد؛ بدونِ این مرحله کسی نمی‌فهمید.
    print("[=] راستی‌آزماییِ پس از آپلود …")

    def _sha256(path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    def _fetch_remote(url, attempts=3):
        for attempt in range(1, attempts + 1):
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "BorsTerminal-Release-Tool"})
                with urllib.request.urlopen(req, timeout=600) as resp:
                    return resp.read()
            except Exception as e:
                print(f"[!] خطا در دانلودِ {url} (تلاش {attempt}/{attempts}): {e!r}")
                if attempt < attempts:
                    time.sleep(5 * attempt)
        return None

    def verify_asset_bytes(local_path, asset_name):
        """دانلودِ همان فایل از ریلیز + مقایسهٔ SHA-256 با فایلِ محلی.

        برمی‌گرداند بایت‌هایِ از راه دور (برای راستی‌آزماییِ امضا) یا None."""
        url = (f"https://github.com/{REPO}/releases/download/{TAG}/"
               + urllib.parse.quote(asset_name))
        remote = _fetch_remote(url)
        if remote is None:
            print(f"[-] {asset_name}: دانلود از راه دور ممکن نشد.")
            return None
        local_hash = _sha256(local_path)
        remote_hash = hashlib.sha256(remote).hexdigest()
        if local_hash != remote_hash:
            print(f"[-] {asset_name}: هشِ محلی و از راه دور ناهم‌خوان است!\n"
                  f"    local  {local_hash}\n    remote {remote_hash}")
            return None
        print(f"[✓] {asset_name}: هش یکسان ({local_hash[:16]}…)")
        return remote

    def verify_signature(remote_data, remote_sig_bytes, label):
        try:
            # api.update و bors_minisign در ریشهٔ ریپو هستند؛ اسکریپت از
            # scripts/ اجرا می‌شود و sys.path[0] همان پوشهٔ scripts است.
            if ROOT not in sys.path:
                sys.path.insert(0, ROOT)
            from api.update import UPDATE_PUBKEY
            from bors_minisign import verify_minisign
            verify_minisign(remote_data,
                            remote_sig_bytes.decode("utf-8", errors="replace"),
                            UPDATE_PUBKEY)
            print(f"[✓] امضای minisignِ {label} با کلیدِ عمومیِ آپدیتِر تأیید شد.")
            return True
        except Exception as e:
            print(f"[-] راستی‌آزماییِ minisign برای {label} شکست خورد: {e!r}")
            return False

    verify_ok = True
    remote_setup = verify_asset_bytes(SETUP_EXE, os.path.basename(SETUP_EXE))
    remote_setup_sig = verify_asset_bytes(SIG_FILE, os.path.basename(SIG_FILE))
    if remote_setup is None or remote_setup_sig is None:
        verify_ok = False
    elif not verify_signature(remote_setup, remote_setup_sig,
                              os.path.basename(SETUP_EXE)):
        verify_ok = False

    for e in (PATCHES if patch_uploaded else []):
        remote_patch = verify_asset_bytes(e["zip"], os.path.basename(e["zip"]))
        remote_patch_sig = verify_asset_bytes(e["sig"], os.path.basename(e["sig"]))
        if remote_patch is None or remote_patch_sig is None:
            verify_ok = False
        elif not verify_signature(remote_patch, remote_patch_sig,
                                  os.path.basename(e["zip"])):
            verify_ok = False

    # manifest را هم راستی‌آزمایی می‌کنیم: نسخهٔ بعد پچش را از رویِ همین فایل
    # می‌سازد، پس manifestِ نیمه‌کاره یا کهنه یعنی پچِ اشتباه برایِ همهٔ کاربران.
    if manifest_uploaded:
        if verify_asset_bytes(manifest_path, os.path.basename(manifest_path)) is None:
            verify_ok = False

    # ۷. منتقل‌کردنِ codal.db.lzma به این ریلیز.
    #
    # چرا: دکمهٔ «بروزرسانی دیتابیس کدال» درونِ برنامه از
    # releases/latest/download/codal.db.lzma می‌خواند، و «latest» همیشه همین
    # ریلیزِ تازه است — یعنی هر ریلیزی که این فایل را نداشته باشد آن دکمه را
    # ۴۰۴ می‌کند (v1.0.20 تا v1.0.23 دقیقاً همین بود). فایل در ریپو نیست
    # (gitignore)، پس از آخرین ریلیزی که دارد کپی می‌شود. نبودش ریلیز را
    # متوقف نمی‌کند، ولی صریح و با هشدار گزارش می‌شود.
    try:
        _codal = ("codal.db.lzma", "codal.db.lzma.sig")
        have = {a.get("name") for a in target_release.get("assets", [])}
        if set(_codal) <= have:
            print("[=] codal.db.lzma از قبل روی این ریلیز است؛ دوباره آپلود نمی‌شود.")
        else:
            src = next((r for r in releases
                        if r.get("tag_name") != TAG
                        and set(_codal) <= {a.get("name") for a in r.get("assets", [])}),
                       None)
            if src is None:
                print("[!] در هیچ ریلیزِ دیگری codal.db.lzma نیست؛ دکمهٔ کدال ۴۰۴ "
                      "می‌گیرد. بساز: scripts/build_codal_snapshot.py")
            else:
                # سِن فایلِ جلو‌برده‌شده: تا پیش از این، codal.db.lzmaیِ یک
                # نسخهٔ قدیمی بی‌صدا به هر ریلیزِ بعدی منتقل می‌شد و «بروزرسانی
                # دیتابیس کدال» درونِ برنامه همان اسنپ‌شاتِ چندماهه را می‌داد.
                # ریلیز را نمی‌بندیم (کدال را نمی‌توان در CI ساخت)، فقط اعلام
                # می‌کنیم و در CI ::warning:: می‌شود.
                age = _days_since(src.get("published_at"))
                _codal_age_line(age, f"تاریخ ریلیز مبدأ {src['tag_name']}")
                import tempfile
                import shutil as _sh
                print(f"[=] در حال منتقل‌کردن codal.db.lzma از {src['tag_name']} "
                      f"به {TAG} …")
                tmpdir = tempfile.mkdtemp(prefix="codal_carry_")
                try:
                    for name in _codal:
                        a = next(x for x in src["assets"] if x.get("name") == name)
                        blob = _fetch_remote(a.get("browser_download_url"))
                        if blob is None:
                            print(f"[!] دانلودِ {name} از {src['tag_name']} نشد.")
                            continue
                        path = os.path.join(tmpdir, name)
                        with open(path, "wb") as f:
                            f.write(blob)
                        if name == "codal.db.lzma":
                            # عددِ واقعی: سِنِ داده‌ای که رویِ همین ریلیز می‌نشیند،
                            # نه سِنِ ریلیزی که از آن کپی شد.
                            _codal_age_line(_snapshot_age_days(path),
                                            "خودِ اسنپ‌شات")
                        if not upload_asset(path):
                            print(f"[!] آپلودِ {name} روی {TAG} ناموفق بود.")
                            continue
                        back = _fetch_remote(
                            f"https://github.com/{REPO}/releases/download/{TAG}/{name}")
                        if back == blob:
                            print(f"[✓] {name}: بایت‌های منتشرشده با مبدأ یکسان است "
                                  f"({len(blob)} بایت).")
                        else:
                            print(f"[!] {name}: مقایسهٔ پس از آپلود ناموفق بود.")
                finally:
                    _sh.rmtree(tmpdir, ignore_errors=True)
    except Exception as e:
        print(f"[!] انتقالِ codal.db.lzma خطا داد (ریلیز متوقف نمی‌شود): {e!r}")

    # latest.json از همان URLای که آپدیتِرِ کاربر می‌خواند (releases/latest)
    # بررسی می‌شود: نسخه باید همین TAG باشد.
    manifest_url = (f"https://github.com/{REPO}/releases/latest/download/latest.json")
    remote_manifest_bytes = _fetch_remote(manifest_url)
    if remote_manifest_bytes is None:
        print("[-] latest.json از URLِ آپدیتِر دانلود نشد.")
        verify_ok = False
    else:
        try:
            remote_manifest = json.loads(remote_manifest_bytes.decode("utf-8", errors="replace"))
        except Exception as e:
            print(f"[-] latest.json از راه دور JSON نیست: {e!r}")
            remote_manifest = {}
        if remote_manifest.get("version") != TAG.lstrip("v"):
            print(f"[-] latest.json از راه دور نسخهٔ {remote_manifest.get('version')!r} "
                  f"دارد (انتظار: {TAG.lstrip('v')!r}).")
            verify_ok = False
        else:
            print(f"[✓] latest.json از URLِ آپدیتِر نسخهٔ {remote_manifest.get('version')} "
                  f"را اعلام می‌کند.")

    if not verify_ok:
        print("[-] راستی‌آزماییِ پس از آپلود شکست خورد؛ ریلیز را دستی بررسی کن.")
        sys.exit(1)
    print("[✓] راستی‌آزماییِ پس از آپلود کامل شد — فایل‌های منتشرشده با محلی یکسان‌اند و امضاها معتبرند.")

if __name__ == "__main__":
    main()
