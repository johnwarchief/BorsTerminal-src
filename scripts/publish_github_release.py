# -*- coding: utf-8 -*-
"""
scripts/publish_github_release.py
=================================
ایجاد خودکار یا به‌روزرسانی ریلیز v1.0.1 در گیت‌هاب و آپلود فایل نصاب BorsTerminal_Ultimate_Setup_v1.0.1.exe
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
TAG = "v1.0.2"
RELEASE_NAME = "BorsTerminal Ultimate v1.0.2"
RELEASE_BODY = """## تغییرات نسخه v1.0.2

### 🔒 جداسازی دیتابیس کاربر از بازار (مهم‌ترین تغییر)
- **واچ‌لیست و سبد سرمایه‌گذاری** از این نسخه در فایل `user.db` مستقل ذخیره می‌شوند
- **آپدیت‌های آینده** دیگر واچ‌لیست، تصمیمات سبد، و تنظیمات فیلترها را پاک نمی‌کنند
- **Migration خودکار:** داده‌های نسخه‌های قبلی به‌صورت خودکار و بدون از دست دادن هیچ اطلاعاتی منتقل می‌شوند
- تنظیمات فیلترها (`fts_thresholds.json`) از قبل هم کنار EXE ذخیره می‌شد و امن بود
"""

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETUP_EXE = os.path.join(ROOT, "installer", "out", "BorsTerminal_Ultimate_Setup_v1.0.2.exe")

def get_github_token():
    try:
        proc = subprocess.Popen(
            ["git", "credential", "fill"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        out, _ = proc.communicate(input="protocol=https\nhost=github.com\n")
        for line in out.splitlines():
            if line.startswith("password="):
                return line.split("=", 1)[1].strip()
    except Exception as e:
        print(f"[-] Could not get git credentials: {e}")
    return os.environ.get("GITHUB_TOKEN", "")

def main():
    token = get_github_token()
    if not token:
        print("[-] هیچ توکنی یافت نشد.")
        sys.exit(1)

    if not os.path.exists(SETUP_EXE):
        print(f"[-] فایل نصاب در {SETUP_EXE} یافت نشد!")
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
            "name": RELEASE_NAME,
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

    # ۳. حذف فایل قدیمی با همین نام اگر قبلا آپلود شده
    upload_url_template = target_release["upload_url"]
    upload_url_base = upload_url_template.split("{")[0]
    assets = target_release.get("assets", [])
    for a in assets:
        if a.get("name") == os.path.basename(SETUP_EXE):
            print(f"[*] در حال حذف فایل قدیمی با ID {a['id']} ...")
            del_req = urllib.request.Request(a["url"], headers=headers, method="DELETE")
            try:
                with urllib.request.urlopen(del_req) as resp:
                    pass
            except Exception as e:
                print(f"[!] ناتوان در حذف: {e}")

    # ۴. آپلود فایل جدید
    asset_name = os.path.basename(SETUP_EXE)
    file_size = os.path.getsize(SETUP_EXE)
    size_mb = file_size / (1024 * 1024)
    print(f"[+] در حال آپلود {asset_name} ({size_mb:.1f} MB) ...")

    upload_url = f"{upload_url_base}?name={urllib.parse.quote(asset_name)}"
    with open(SETUP_EXE, "rb") as f:
        file_data = f.read()

    upload_headers = {
        "Authorization": f"token {token}",
        "Content-Type": "application/octet-stream",
        "Content-Length": str(file_size),
        "User-Agent": "BorsTerminal-Release-Tool"
    }

    req_upload = urllib.request.Request(upload_url, data=file_data, headers=upload_headers, method="POST")
    try:
        with urllib.request.urlopen(req_upload) as resp:
            res_data = json.loads(resp.read().decode())
            print(f"[✓] آپلود موفقیت‌آمیز بود! URL دانلود:")
            print(f"    {res_data.get('browser_download_url')}")
    except urllib.error.HTTPError as e:
        print(f"[-] خطا در آپلود: {e.code} - {e.read().decode()}")
        sys.exit(1)

if __name__ == "__main__":
    main()
