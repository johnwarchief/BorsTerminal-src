# -*- coding: utf-8 -*-
"""
scripts/publish_github_release.py
=================================
ایجاد خودکار یا به‌روزرسانی ریلیز v1.0.1 در گیت‌هاب و آپلود فایل نصاب BorsTerminal_Ultimate_Setup_v1.0.3.exe
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
TAG = "v1.0.3"
RELEASE_NAME = "BorsTerminal Ultimate v1.0.3"
RELEASE_BODY = """## تغییرات نسخه v1.0.3

### 🐛 اصلاح طبقه‌بندی تابلوی بازار (مهم‌ترین تغییر)
- **ریشهٔ باگ:** TSETMC قراردادهای اختیار را در فهرست `paperType=1` (همان فهرست سهام) هم برمی‌گرداند؛ `fetch_paper_types` این فهرست را منبع `instruments.paper_type` می‌سازد، پس اختیارها `paper_type=1` می‌گرفتند و `mstat_engine.classify` آن‌ها را «سهام» می‌خواند.
- **اثر:** اختیارها با حجمِ خردِ خود به سطرِ «سهام و حق تقدم»، تجمیعِ حجمِ سهام، و جدولِ الگوی ساعت می‌رسیدند و ارقام تابلوی بازار را می‌ریختند.
- **اصلاح (دو لایه):** ۱) `mstat_engine.classify` حالا پیش از `paperType` و از روی نام، اختیارها را جدا می‌کند. ۲) `fetch_paper_types` دیگر به اختیارها `paperType` اختصاص نمی‌دهد تا سینکِ بعدی `paper_type` آن‌ها را `NULL` نگه دارد (خود-ترمیمیِ بانک). گاردِ `dev/mstat_local_v975.py` **۱۴۰/۱۴۰ سبز**.
- **نتیجه:** تابلوی «سهام و حق تقدم» از ۲۳۴۴ به ۲۳۱۵ نماد اصلاح شد (۲۹ اختیارِ آلوده کنار رفت) و هر ۴۰ نامزدِ الگوی ساعت اکنون حجمِ واقعی دارند.

### 🖥 اصلاح «رزولوشن» — فضای خالی روی مانیتورهای ۲K
- **ریشهٔ باگ:** محتوای صفحه در نمایشگرهای ۱۹۲۰px و بالاتر به عرض ثابت ۱۶۰۰px (در ۴K: ۱۹۲۰px) محدود و وسط‌چین می‌شد، در حالی که نوار تب بالای صفحه تمام‌عرض بود؛ نتیجه، فضای خالیِ چپ/راستِ محتوا روی مانیتورهای ۲K بود.
- **اصلاح:** سقفِ عرضِ محتوا (`--content-max-w`) در ۲K/۴K حذف شد تا جدول‌ها و چارت‌ها مثل نوار تب، تمام‌عرض رندر شوند. مقیاسِ تایپوگرافی و gutter واکنشی دست‌نخورده باقی ماند.

### 🧰 به‌روزرسانی خودکار
- نسخهٔ مرجعِ updater و فایل‌های نصاب به ۱.۰.۳ هماهنگ شدند؛ نصب‌های قبلی با امضای موجود به‌طور خودکار این نسخه را دریافت می‌کنند.
"""

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETUP_EXE = os.path.join(ROOT, "installer", "out", "BorsTerminal_Ultimate_Setup_v1.0.3.exe")
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

    # ۳. حذف فایل‌های قدیمی با همین نام اگر قبلا آپلود شده‌اند
    upload_url_template = target_release["upload_url"]
    upload_url_base = upload_url_template.split("{")[0]
    assets = target_release.get("assets", [])
    existing_names = {a.get("name") for a in assets}
    for a in assets:
        if a.get("name") in (os.path.basename(SETUP_EXE), os.path.basename(SIG_FILE)):
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

    print(f"[✓] تمام فایل‌ها آپلود شدند ({os.path.basename(SETUP_EXE)} + .sig).")

if __name__ == "__main__":
    main()
