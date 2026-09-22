---
name: bors-build-install-guard
description: گارد بیلد/نصب/اجرای BorsTerminal — قبل از هر تغییر در spec، release.ps1، وابستگی‌ها یا وب‌اپ بیلد بخوان؛ شامل تضمین اجرا روی سیستم ضعیف و ویندوز قدیمی.
---

# bors-build-install-guard — گارد بیلد، نصب و اجرا

هدف: بیلد و نصب/اجرا روی **ویندوز قدیمی** و **سخت‌افزار ضعیف** هم بدون خطا کار کند.

## ناورداها (نباید بشکنند)

- **`numpy==2.0.2` پین‌شده است.** numpy ۲.۱+ نیازمند baseline x86-v2 است و روی CPUهای قدیمی کرش می‌کند. «مدرن‌سازی» ممنوع.
- **پکیجینگ onedir، نه onefile:** `bors_exe_onedir.spec` (onefile کل market.db را هر بار استخراج می‌کرد).
- **`market.db.lzma` کنار EXE توزیع می‌شود، نه داخلش.** `ensure_market_db()` در `bors_config.py` بازسازی می‌کند.
- **هر ماژول جدید `api/*.py` باید به `hiddenimports` در `bors_exe_onedir.spec` اضافه شود** وگرنه EXE روی اولین درخواست `ModuleNotFoundError` می‌دهد (چون `api_router()` ایمپورت‌ها را داخل بدنه‌ی تابع انجام می‌دهد).
- **گارد ویندوز:** `WIN_TOO_OLD` (ویندوز < ۱۰) در `bors_entry.py` قبل از استارت اپ بررسی می‌شود.
- **رندر نرم افزاری:** `_render_flags()` برای GPU مجتمع/قدیمی/بدون GPU و RAM کم → فلگ‌های SwiftShader به مرورگر پاس می‌شود.
- **کدگذاری خروجی:** روی ویندوز انگلیسی، stdout با cp1252 کرش می‌کند (`UnicodeEncodeError`) — هر print با متن فارسی باید زیر UTF-8 بماند.
- **لانچ بدون پنجره:** `lost sys.stdin` قبلاً رخ داده؛ مسیر windowless باید هندل شود.
- **آپدیترها:** پکیجینگ با Velopack؛ Inno Setup کنار گذاشته شد.

## چک‌لیست بیلد (محیط توسعه)

```powershell
# 1) وابستگی‌ها و گیت اسکریپت‌های نصب (npm v12 + Node 22.22.0 ناسازگاریِ ENGINE می‌دهد)
cd frontend; npm ci
npm install-scripts approve esbuild     # esbuild@0.21.5 زیر allowScripts مسدود می‌شود
npm run build                           # vite build؛ خروجی به dist/
# 2) تایپ‌چک: پروژه ~۴۴ خطای از قبل موجود در features/technical دارد (قاعدهٔ compare-with-baseline)
npx tsc -b
```

## چک‌لیست تست روی سیستم هدف

1. نصب خام روی **ویندوز ۱۰** (هم فارسی، هم locale انگلیسی).
2. ماشین **بدون GPU مجتمع/قدیمی** + **RAM کم** (فلگ‌های SwiftShader باید فعال شوند).
3. بوت و سرو API روی `127.0.0.1:8001` و بررسی پاسخ‌های کلیدی (`/api/update/version`, `/api/market`, `/api/screener`).
4. مسیر آپدیت دلتا (Velopack) روی نصب خام.

## گردش کار انتشار

`release.ps1 all` زنجیره‌ی بیلد فرانت‌اند + PyInstaller onedir + بسته‌بندی Velopack + امضا را اجرا می‌کند.
گاردهای مخزن در `dev/` (مثل `repo_hygiene_v97.py`, `soft_warnings_v974.py`, `run_all_tests.py`) قرارداد تست‌اند؛
اگر گاردی قرمز شد، اول بررسی کن باگ داده واقعی است یا نه — سریع «فیکسش» نکن.
