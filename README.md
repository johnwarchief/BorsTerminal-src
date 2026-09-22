# BorsTerminal Ultimate — ایستگاه معاملاتی و داوری نخبگان بورس

اپلیکیشن دسکتاپ ویندوزی برای تحلیل بازار بورس ایران: تابلو (بازار)، بنیادی (ماتریس FTS)، تکنیکال، پرتفوی و نبضِ بازار.

- هستهٔ بک‌اند: Python + FastAPI/uvicorn (قابل بستن به‌صورت onedir با PyInstaller).
- رابط کاربری: React + Vite + Tailwind (در `frontend/`).
- پنجرهٔ بومی: WebView2 (pywebview) بدون مرورگر/تب/نوار آدرس؛ در صورت نبودِ WebView2 به مرورگر fallback می‌کند.
- داده: اسنپ‌شاتِ آمادهٔ `market.db.lzma` (اولین اجرا خودش استخراج می‌کند) + به‌روزرسانی از TSETMC/کدال.

> این مخزن، آینهٔ **خصوصیِ منبع** است. باینری‌های منتشرشده روی مخزنِ عمومیِ [`johnwarchief/BorsTerminal`](https://github.com/johnwarchief/BorsTerminal/releases) قرار می‌گیرند.

## اجرا (توسعه)

```powershell
# ویندوز: اسکریپت آماده
.\run_terminal.bat

# یا مستقیم
python bors_entry.py
```

بک‌اند روی `http://127.0.0.1:8001` بالا می‌آید (پورتِ آزاد به‌صورت خودکار انتخاب می‌شود).

## تست و گاردها

منطقِ درستیِ این پروژه در اسکریپت‌های `dev/*.py` است، نه تست‌های واحدِ متعارف. همان‌هایی که CI اجرا می‌کند:

```powershell
python dev/run_all_tests.py     # مجموعِ گاردهای آفلاین
```

گاردِ سمتِ CI در `.github/workflows/guards.yml` شامل: گاردهای پایتونی، `node --check` روی باندل‌های فرست‌پارتی، و بهداشتِ مخزن (EOL/attributes/فایل‌های سرگردان).

## بیلد و ریلیز

```powershell
# ۱) فرانت + بستهٔ onedir (PyInstaller)
python scripts/build_all.py
#    خروجی: dist/BorsTerminal_Ultimate/  (+ market.db.lzma کنارش)

# ۲) رمزِ نصاب (gitignored) — باید همان مقدارِ سکرتِ BORS_SETUP_PASSWORD باشد
Set-Content installer/.setup_password.iss '#define SetupPassword "..."' -Encoding ascii -NoNewline

# ۳) کامپایل نصابِ Inno (ISCC از Inno Setup 6)
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "/DAppVersion=1.0.x" installer\bors_setup.iss
#    خروجی: installer/out/BorsTerminal_Ultimate_Setup_v1.0.x.exe

# ۴) امضای minisign (کلیدِ .tauri/updater.key — gitignored)
python scripts/sign_setup.py installer\out\BorsTerminal_Ultimate_Setup_v1.0.x.exe

# ۵) انتشار روی مخزنِ عمومی + ساخت latest.json
$env:RELEASE_TAG="v1.0.x"; $env:GITHUB_TOKEN="<PAT>"
python scripts/publish_github_release.py
```

### ریلیزِ خودکار (GitHub Actions)

`.github/workflows/release.yml` با پوش‌شدنِ تگِ `v*` یا `workflow_dispatch` (ورودیِ `tag`) اجرا می‌شود:

- `release-windows`: بیلدِ Tauri/NSIS (پوستهٔ سبک).
- `release-inno`: زنجیرهٔ اصلی — PyInstaller → ISCC → امضا با `tauri signer` → انتشار روی مخزنِ عمومی.

سکرت‌های لازم (Settings → Secrets → Actions):

| سکرت | کاربرد |
| --- | --- |
| `TAURI_SIGNING_PRIVATE_KEY` | محتوای `.tauri/updater.key` (کلیدِ امضای updater، بدونِ رمز) |
| `BORS_SETUP_PASSWORD` | رمزِ `installer/.setup_password.iss` (نصاب) |
| `RELEASE_TOKEN` | PAT با دسترسی به هر دو مخزن؛ برای انتشار روی مخزنِ عمومی از داخلِ آینهٔ منبع لازم است |

## ساختار مخزن

| مسیر | توضیح |
| --- | --- |
| `app.py`, `api/` | بک‌اند FastAPI و روترها |
| `bors_entry.py` | نقطهٔ ورودِ دسکتاپ (سرور + پنجرهٔ بومی) |
| `frontend/` | اپلیکیشن React/Vite |
| `installer/` | اسکریپت و منابعِ Inno Setup |
| `scripts/` | زنجیرهٔ بیلد/امضا/انتشار |
| `dev/` | ابزارها و گاردهای آفلاین |
| `skills/` | اسکیل‌های دستیار برای نگهداریِ همین پروژه |
| `market.db.lzma` | اسنپ‌شاتِ دادهٔ ارسالی |

نقشهٔ دقیق‌ترِ ماژول‌ها: `REPO_MAP.md`. راهنمای به‌روزرسانی: `UPDATE.md`. تاریخچهٔ نسخه‌ها: `CHANGELOG.md`.

## اسکیل‌ها

پوشهٔ `skills/` شامل جریان‌های کاریِ نگهداریِ این پروژه است — `bors-architecture` (پیش از هر refactor)، `bors-build-release` (بیلد/انتشار)، `bors-code-review` (بازبینیِ پیش از کامیت)، `bors-frontend-ui-guard` (تغییراتِ UI) و `bors-build-install-guard` (بیلد/نصب). جزئیات در `skills/README.md`.
