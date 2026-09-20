# -*- coding: utf-8 -*-
"""
scripts/publish_github_release.py
=================================
ایجاد خودکار یا به‌روزرسانی ریلیز موردنظر در گیت‌هاب و آپلود فایل نصب Inno BorsTerminal_Ultimate_Setup_{tag}.exe + latest.json (آپدیت‌ر به نصب Inno اشاره می‌کند).
"""
import os
import sys
import json
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
RELEASE_BODY = """## تغییرات نسخهٔ v1.0.9

### 🐛 رفعِ باگ (بحرانی)
- **دیتابیسِ ناقص در v1.0.7/8:** `market.db.lzma`یِ ارسالی در آن دو نسخه پس از استخراج فقط جداولِ پایه را داشت و `financial_statements` غایب بود؛ نتیجه خطای ۵۰۰ در اسکرینر («no such table: financial_statements»). دو ریشه اصلاح شد:
  1. `release.ps1` هر `market.db`ی را بی‌تفتش فشرده می‌کرد — حالا قبل از فشرده‌سازی منبع را اعتبارسنجی می‌کند (جداولِ موردنیاز + تعدادِ ردیف)، از baselineیِ فعلی بکاپ می‌گیرد و round-tripِ lzma را تأیید می‌کند.
  2. `ensure_market_db()` برای پذیرشِ یک دیتابیسِ موجود روی دیسک، اکنون `financial_statements` را هم الزامی می‌کند؛ دیتابیسهای ناقص کنار گذاشته و دوباره از `market.db.lzma` استخراج می‌شوند. این یعنی **ارتقا از روی v1.0.7/8 هم دیتای ناقص را اصلاح می‌کند** (قبلاً فایلِ قدیمی محفوظ می‌ماند و باگ سر جایش می‌ماند).
- **دیتابیسِ این نسخه:** یکپارچگیِ `market.db.lzma` تأیید شده (حدود ۱۰۳ مگابایت پس از استخراج: instruments=۵۱۲۹، daily_prices=۶۰۶۳۷، financial_statements=۸۰۰۹).

### ⚙️ آپدیتِ خودکار
- رمزِ نصب‌کننده داخلِ باندل (در `_internal`) قرار گرفت تا `/VERYSILENT` آپدیتِر بدونِ پرسش کار کند؛ `api.update` و `bors_minisign` به hiddenimports اضافه شدند.
- مسیرِ امضای minisign به `scripts/sign_setup.py` منتقل و به `release.ps1` متصل شد: اول `tauri signer sign` با timeoutِ ۱۲۰ ثانیه، سپس fallbackِ minisign خالصِ پایتون، و در پایان تأییدِ امضا مقابلِ `updater.key.pub` — بدونِ امضای معتبر بیلد متوقف می‌شود.

### 🖥 موارد دیگر
- افزایش نسخهٔ برنامه و مانیفست آپدیتِ درون‌برنامه‌ای به 1.0.9.
"""

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# CI / CLI may override the tag being published (RELEASE_TAG=v1.0.5). Default
# keeps the local single-release flow working unchanged. The installer name is
# derived from the tag so both always agree with bors_setup.iss output.
TAG = os.environ.get("RELEASE_TAG", "v1.0.9")
SETUP_EXE = os.path.join(ROOT, "installer", "out", f"BorsTerminal_Ultimate_Setup_{TAG}.exe")
# Tauri updater needs the minisign signature next to the installer asset.
SIG_FILE = SETUP_EXE + ".sig"

def get_github_token():
    # Feed the credential request via a pipe; an interactive helper with no
    # controlling tty can hang indefinitely waiting for stdin.
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
    for a in assets:
        # latest.json is regenerated per-publish and embeds the current .sig,
        # so a stale copy must be deleted too (GitHub 422s on duplicate names).
        if a.get("name") in (os.path.basename(SETUP_EXE), os.path.basename(SIG_FILE), "latest.json"):
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

    # 5) build + upload latest.json (Tauri updater manifest)
    latest_path = build_latest_json()
    if not upload_asset(latest_path):
        print("[-] upload of latest.json failed")
        sys.exit(1)
    try:
        os.remove(latest_path)
    except OSError:
        pass

    print(f"[✓] تمام فایل‌ها آپلود شدند ({os.path.basename(SETUP_EXE)} + .sig + latest.json).")

if __name__ == "__main__":
    main()
