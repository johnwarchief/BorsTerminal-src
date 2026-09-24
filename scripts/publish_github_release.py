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
print(f"[=] ریلیزِ هدف: {TAG}  (RELEASE_TAG unset means bors_config.APP_VERSION)")
SETUP_EXE = os.path.join(ROOT, "installer", "out", f"BorsTerminal_Ultimate_Setup_{TAG}.exe")
# Tauri updater needs the minisign signature next to the installer asset.
SIG_FILE = SETUP_EXE + ".sig"

# v1.0.10 -- delta update. PATCH_FROM (default: the previously released
# version) is the only version this patch is valid for; the updater refuses to
# apply it on anything else and falls back to the full installer.
# نسخهٔ مبدأِ پچ دیگر دست‌نویس نیست («1.0.9» کهنه): اگر PATCH_FROM داده نشود،
# پچِ ساخته‌شده در dist بر اساسِ همان نسخهٔ مقصد پیدا می‌شود.
PATCH_FROM = os.environ.get("PATCH_FROM", "")
if not PATCH_FROM:
    import glob as _glob
    _cands = [x for x in _glob.glob(os.path.join(ROOT, "dist", "BorsTerminal_Patch_*_to_%s.zip"
                                                 % TAG.lstrip("v")))
              if not x.endswith(".sig")]
    if len(_cands) == 1:
        _stem = os.path.basename(_cands[0]).replace("BorsTerminal_Patch_", "").split("_to_")[0]
        PATCH_FROM = _stem
        print(f"[=] مبدأِ پچ از رویِ فایلِ dist خوانده شد: {PATCH_FROM}")
    elif len(_cands) > 1:
        raise SystemExit("چند پچِ مختلف در dist است؛ PATCH_FROM را صریح بده: %s" % _cands)
PATCH_ZIP = os.path.join(ROOT, "dist", f"BorsTerminal_Patch_{PATCH_FROM or 'NONE'}_to_{TAG.lstrip('v')}.zip")
PATCH_SIG = PATCH_ZIP + ".sig"

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
    # v1.0.10: پچِ دلتای اختیاری. فقط وقتی به مانیفست اضافه می‌شود که هم zip و
    # هم .sig روی دیسک موجود باشند؛ آپدیتِر با غیابِ آرایه شفافاً به نصبِ کامل
    # برمی‌گردد، پس ریلیزِ بدونِ پچ همچنان درست کار می‌کند.
    if os.path.isfile(PATCH_ZIP) and os.path.isfile(PATCH_SIG):
        with open(PATCH_SIG, "r", encoding="utf-8", errors="replace") as f:
            patch_signature = f.read().strip()
        patch_name = os.path.basename(PATCH_ZIP)
        manifest["patches"] = [
            {
                "from": PATCH_FROM,
                "to": version,
                "signature": patch_signature,
                "url": f"https://github.com/{REPO}/releases/download/{TAG}/{patch_name}",
                "size": os.path.getsize(PATCH_ZIP),
            }
        ]
        print(f"[+] پچِ دلتا به مانیفست اضافه شد: {PATCH_FROM} -> {version}")
        print(f"    url -> {manifest['patches'][0]['url']}")
    else:
        print(f"[*] پچِ دلتا یافت نشد ({PATCH_ZIP})؛ مانیفست فقط نصبِ کامل را معرفی می‌کند.")
    out_path = os.path.join(ROOT, "latest.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"[+] latest.json ساخته شد: {out_path}")
    print(f"    url -> {manifest['platforms']['windows-x86_64']['url']}")
    return out_path


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
            "body": RELEASE_BODY,
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
    if os.path.isfile(PATCH_ZIP):
        stale_names.add(os.path.basename(PATCH_ZIP))
        stale_names.add(os.path.basename(PATCH_SIG))
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

    # v1.0.10: پچِ دلتا + امضایش. اختیاری است — اگر ساخته نشده، ریلیز فقط
    # نصبِ کامل را معرفی می‌کند و آپدیتِر شفافاً همان مسیر را می‌رود.
    patch_uploaded = False
    if os.path.isfile(PATCH_ZIP) and os.path.isfile(PATCH_SIG):
        for local_path in (PATCH_ZIP, PATCH_SIG):
            if not upload_asset(local_path):
                print(f"[-] آپلود {os.path.basename(local_path)} پس از چندین تلاش ناموفق بود.")
                sys.exit(1)
        patch_uploaded = True
    else:
        print(f"[*] پچِ دلتا موجود نیست ({PATCH_ZIP})؛ بدونِ پچ ادامه می‌دهیم.")

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
              f"{os.path.basename(PATCH_ZIP)} + .sig + latest.json).")
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

    if patch_uploaded:
        remote_patch = verify_asset_bytes(PATCH_ZIP, os.path.basename(PATCH_ZIP))
        remote_patch_sig = verify_asset_bytes(PATCH_SIG, os.path.basename(PATCH_SIG))
        if remote_patch is None or remote_patch_sig is None:
            verify_ok = False
        elif not verify_signature(remote_patch, remote_patch_sig,
                                  os.path.basename(PATCH_ZIP)):
            verify_ok = False

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
