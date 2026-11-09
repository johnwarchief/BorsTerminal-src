# گزارشِ پایانیِ فاز ۴٫۸ — تأییدِ نهایی و بستنِ شکاف‌ها

**شاخه:** `mission/phase48-final-verification-2026-11-09`
**مبنایِ مأموریت:** `89f97bdca6b0c4a632faab91bee8c4e66046cbbc` (تأییدشده روی Remote)
**SHA کدِ آزمون‌شده و شاهدِ CI:** `d00fe7e6ff9309016076935ae97e2ffe46eb3297`
**کامیتِ مستنداتِ همین گزارش:** بعد از `d00fe7e6` (فقط docs و ابزارِ خواندنیِ هویت)
**worktree:** `C:/Users/PCMOD/Desktop/BorsTerminal`

این گزارش فقط بر پایهٔ خروجیِ واقعیِ تست‌ها و شواهدِ ثبت‌شده است. فایل‌هایِ محلیِ
شاهد زیرِ `_audit/phase48/` (gitignored) هستند و دادهٔ خامِ ره‌آورد در گیت نیست.

## ۱. خلاصهٔ ۱۲ موردِ خواسته‌شده

| # | مورد | وضعیت | شاهدِ کوتاه |
| ---: | --- | --- | --- |
| ۱ | SHA مبنا و SHA نهایی | **PASS** | مبنا `89f97bdc` روی Remote؛ کد `d00fe7e6`؛ گزارش فقط docs |
| ۲ | وضعیتِ Branch و Worktree | **PASS** | شاخهٔ تازه از مبنا؛ ۴۹ Worktree؛ فقط همین یکی تغییر کرد |
| ۳ | نسخهٔ Rust و Cargo | **PASS** | rustc/cargo `1.99.1`، `x86_64-pc-windows-msvc` |
| ۴ | ساختِ واقعیِ Tauri Shell | **PASS** | `cargo build --release --locked` محلی و CI؛ WebView2 واقعی |
| ۵ | ساختِ بستهٔ کاملِ Windows | **PASS** (شکل/اجرا) | ۷۷ فایل، bundlecheck PASS، اجرایِ واقعی؛ **دادهٔ بسته FAIL** |
| ۶ | نصبِ تمیز/ارتقا/Uninstall/Repair | **PASS** (Repair تعاملی `NOT_MEASURED`) | `[Run]` واقعی؛ حفظِ `user.db`/`fts_thresholds.json` |
| ۷ | چرخهٔ واقعیِ Auto-Update و Rollback | **BLOCKED** | هیچ موتورِ Update در بستهٔ Go نیست؛ ۱۰ سناریو `NOT_MEASURED` |
| ۸ | تطبیقِ ۳۰ نماد با ره‌آورد | **FAIL** | ضریب PASS؛ OHLC خام/تعدیل‌شده FAIL؛ پوشش FAIL |
| ۹ | Regression Testهای Market Watch | **PASS** | ۳۷ passed / ۰ failed؛ ۲ کنترلِ منفی |
| ۱۰ | GitHub Actions و Race Detector | **PASS** (کارهایِ الزامی) | ۱۰ جاب؛ ۹ سبز؛ `python-guards` از قبل قرمز |
| ۱۱ | مواردِ باقی‌مانده | — | جدولِ §۱۰ |
| ۱۲ | وضعیتِ main، Tag و Release | **PASS** | main دست‌نخورده؛ تگ/ریلیزِ تازه ساخته نشد |

## ۲. مبنا، شاخه، Worktree (مورد ۱ و ۲)

| قلم | مقدار |
| --- | --- |
| Remote مرحلهٔ ۴٫۷ | `89f97bdca6b0c4a632faab91bee8c4e66046cbbc` (`mission/phase47-…`) |
| Merge-base با شاخهٔ ۴٫۸ | همان `89f97bdc` |
| SHA کدِ این فاز | `d00fe7e6ff9309016076935ae97e2ffe46eb3297` |
| Worktreeهایِ ثبت‌شده | ۴۹؛ هیچ نوشتن/حذف در هیچ Worktreeِ دیگر انجام نشد |
| main روی Remote | `9a919e82f5b836cc7ec4be5ba04a39ec2f74b4e2` (بدونِ تغییر از سویِ این مأموریت) |
| تگِ آخر | `v1.0.98` (بدونِ تگِ تازه) |
| ریلیزِ آخر | `BorsTerminal Ultimate v1.0.98`، ۲۰۲۶-۱۰-۲۳ (بدونِ ریلیزِ تازه) |

شاخهٔ ۴٫۸ از `89f97bdc` ساخته شد، نه از main. هیچ merge یا release اجرا نشد.
تنها فایل‌هایِ تغییرکرده در این شاخه: گردش‌کارِ CI، `.gitignore`، گاردهایِ
Market Watch، ابزارِ تأییدِ هویت، و گزارش‌هایِ `docs/opportunity-center/phase48/`.

## ۳. Rust/Cargo و ساختِ Tauri Shell (مورد ۳ و ۴)

| قلم | مقدار |
| --- | --- |
| rustc | `1.99.1 (58cf8f9c3 2026-10-13)` |
| cargo | `1.99.1 (5f94df478 2026-08-27)` |
| host | `x86_64-pc-windows-msvc`، default `stable-x86_64-pc-windows-msvc` |
| lock | `frontend/src-tauri/Cargo.lock` دست‌نخورده؛ build با `--locked` |
| وابستگی‌ها | tauri `=2.12.5`، tauri-build `=2.7.4`، plugins log/updater/process |
| ساختِ محلی | `cargo build --release --locked` موفق (29.99s با کش) |
| `BorsTerminal_Shell.exe` | 12,756,480 B، `sha256=93afb2141fe04d28706df7e40bc624dd5084427f24e31e317ca2860aa3211d11` |
| اجرایِ واقعی | probe: `ready=true`؛ `GET /` = 200؛ اسکریپتِ صفحه اجرا شد (`/api-ping` = 404) |
| CI | Rust 1.99.1 در Windows runner؛ Shell ساخته و در بسته قرار گرفت |

**تصحیحِ گزارشِ ۴٫۷:** ادعایِ «cargo/rustc نصب نیست» درست نبود؛ زنجیرهٔ Rust
`1.99.1` رویِ همین ماشین موجود بود و ساختِ محلی موفق شد. علتِ گزارشِ قبلی،
محیط/PATH بود، نه نبودِ ابزار.

## ۴. بستهٔ کاملِ Windows و اجرایِ واقعی (مورد ۵)

| قلم | مقدار |
| --- | --- |
| خروجی | `dist/BorsTerminal_Ultimate/` — ۷۷ فایل، 77.2 MB |
| `BorsTerminal_Ultimate.exe` | 21,723,136 B، `sha256=7e07c289…bdbcb8e1` |
| `BorsTerminal_Shell.exe` | 12,756,480 B، `sha256=93afb214…3211d11` |
| `frontend/index.html` | `sha256=32b8ecfd…cabe2c` |
| `market.db` | 26,378,240 B، `sha256=c0979d4e…1511c8a9` |
| پکِ تقویم | `data/ra365_calendar/ra365-r32d` (manifest `4d61f437…`) |
| پک‌هایِ تصحیح | `ra365-live40-v1` + `ra365-r32b-v2` |
| `apply_update.bat` | موجود (برایِ مسیرِ آپدیتِ legacy) |
| bundlecheck | `dev/onedir_contract_v11.py` = **PASS** |
| Python/Uvicorn/FastAPI | صفر فایل؛ `bundlecheck` = «no python/uvicorn/fastapi artifacts» |

اجرایِ واقعی رویِ پورتِ مستقل `8137` و بانکِ آزمایشگاهی:

| بررسی | نتیجه |
| --- | --- |
| `/healthz` | 200؛ `data_dir` = `_audit/phase48/lab`؛ `market_mode=read-only` |
| Shell | خودکار اجرا شد (فرزندِ borsd)؛ WebView2 اتصالِ TCP به 8137 برقرار کرد |
| `/` | 200 (SPA) |
| `/api/market` | 200؛ 6,230,289 B |
| `/api/ma/فولاد` | 200؛ 35,247 B |
| `/api/chart-db/فولاد` | 200؛ 172,925 B |
| بستنِ Shell | borsd با exit 0 خاموش شد؛ فرآیندِ باقی‌مانده: هیچ؛ پورت آزاد |

### یافتهٔ مهم: دادهٔ بستهٔ توزیع‌شده تقویمِ کندل ندارد

`market.db`ِ داخلِ بسته فقط یک روزِ تابلو است، نه تاریخچهٔ کندل:

| جدول | بستهٔ `market.db` | `market.db.lzma` (وزن‌دار، بی‌استفاده) |
| --- | ---: | ---: |
| `price_history` | 2,209 ردیف، فقط 2026-11-04 | 445,676 ردیف، 2024-08-24 → 2026-10-14 |
| `daily_prices` | 3,680 ردیف، فقط 2026-11-04 | 129,577 ردیف، 2026-08-20 → 2026-10-14 |

نتیجهٔ عملی: نصبِ واقعی برای `/api/ma/فولاد` فقط `bars=1` می‌دهد (271 B) و
`/api/market` با ۳٬۶۸۰ ردیفِ تابلو کار می‌کند. برنامهٔ Go فایلِ
`market.db.lzma` را استخراج نمی‌کند؛ بیلد هم فقط `market.db`ِ ردیابِ گیت را
کپی می‌کند. این یک **شکافِ تحویلِ داده** است، نه شکستِ شکلِ بسته؛ بدونِ تصمیمِ
مالک تغییر داده نشد (جدولِ §۱۰، ردیفِ ۱).

## ۵. Installer — اجرایِ واقعی در محیطِ ایزوله (مورد ۶)

سندِ آزمون از `installer/bors_setup.iss` تولید شد با این تفاوت‌هایِ مستند:
`AppId/AppRegID` تست (`4B7E2D91-9C3A-4F6E-B1D2-7A48F48CE048`)، `AppName` تست،
مسیرهایِ مطلق، ریشهٔ پاک‌سازیِ `{localappdata}\BorsTerminal_Ultimate\data` →
`{app}\_la_sandbox`، و `[Run]` **فعال** با پارامترهایِ ایزوله
`--port 8138 --no-loops`. سایرِ بخش‌ها (payload، `[Files]`، `[InstallDelete]`،
`[Icons]`، `[Code]`، رمزنگاری، رمز) دست‌نخورده ماند.

| سناریو | نتیجه | شاهد |
| --- | --- | --- |
| نصبِ تمیز 1.0.95 (Silent) | **PASS** | rc=0؛ 87 فایل؛ `DisplayVersion=1.0.95`؛ Shortcut ساخته شد |
| اجرایِ `[Run]` پس از نصب | **PASS** | borsd + Shell واقعی؛ `/healthz` و `/api/market` = 200 |
| دادهٔ آزمایشگاهی | **PASS** | `/healthz.data_dir` = مسیرِ نصبِ آزمایشگاهی؛ `/api/market` 3,680 ردیف |
| ساختِ `user.db` واقعی | **PASS** | POST `/api/watchlist` با `--read-write`؛ `user.db` = 20,480 B |
| ارتقا 1.0.95 → 1.0.96 | **PASS** | rc=0؛ `DisplayVersion=1.0.96`؛ اجرایِ دوبارهٔ `[Run]` |
| حفظِ `user.db` | **PASS** | `sha256=f946bc89327e3dc9e8a3064016759314135a5aa4ab1580312aa60ec6966af29b` پیش/پس یکی |
| حفظِ `fts_thresholds.json` | **PASS** | هشِ کاشته‌شده پیش/پس یکی |
| حذفِ فایلِ کهنه | **PASS** | `_internal\stale.pyd` پس از ارتقا حذف شد |
| Repair (Silent reinstall) | **PASS** | `BorsTerminal_Shell.exe` و assetِ حذف‌شده با هشِ اصلی برگشتند؛ `user.db`/تنظیمات حفظ |
| Repair تعاملی | **NOT_MEASURED** | صفحهٔ maintenance نیازمندِ کلیکِ انسان است؛ رفتارِ سایلنت (معادلِ گزینهٔ ۰) اندازه‌گیری شد |
| Uninstall | **PASS** | rc=0؛ EXEها/فرانت/`market.db`/`market.db.lzma`/`apply_update.bat` پاک؛ Registry و Shortcut پاک |
| حفظِ دادهٔ کاربر در Uninstall | **PASS** | `user.db` و `fts_thresholds.json` با همان هش ماندند؛ `_la_sandbox` هم DB/تنظیمات را نگه داشت |
| عدمِ اثر روی نصبِ واقعی | **PASS** | درختِ `%LOCALAPPDATA%\BorsTerminal_Ultimate` و Registryِ واقعی پیش/پس یکسان؛ هیچ فرآیندِ نصب‌شده متوقف نشد |

`[UninstallDelete]`ِ سندِ اصلی ریشهٔ `%LOCALAPPDATA%` را هدف می‌گیرد؛ در آزمون
این ریشه به `{app}\_la_sandbox` تغییر کرد تا LocalAppData واقعی لمس نشود.
Uninstall فایل‌هایِ زمانِ اجرایِ `oc/` (`oc_client.db`، `api_token`، `borsd.lock`،
`backups/*.bak`) را باقی می‌گذارد؛ این‌ها در فهرستِ `[UninstallDelete]` نیستند و
به‌عنوانِ مشاهده ثبت شد (تغییرِ رفتار بدونِ تأییدِ مالک انجام نشد).

هشِ نصاب‌هایِ آزمون: v1.0.95 = `139df24a…7337d97`، v1.0.96 = `a5e2671a…b203a85`
(هر دو 101,013,975 B). شاهدِ کامل: `_audit/phase48/installer-evidence.json`.

## ۶. Auto-Update و Rollback (مورد ۷)

بررسیِ واقعیِ مسیرِ تولید:

| قلم | یافته |
| --- | --- |
| Go backend | `GET /api/update/check`، `/version`، `/progress` = **501 NOT_PORTED** |
| frontend-v2 | هیچ کلاینت/دکمهٔ Update ندارد |
| بستهٔ Go | صفر فایلِ Python؛ `api/update.py` و `bors_minisign.py` در بسته نیستند |
| Tauri Shell | `tauri-plugin-updater` مقداردهی شده؛ endpoint و pubkey در config؛ **هیچ فراخواننده‌ای ندارد** |
| Capability | `updater:default` برای پنجرهٔ `main`؛ صفحه از `http://127.0.0.1` سرو می‌شود و مجوزِ remote ندارد |
| Legacy Python updater | در مخزن هست ولی در معماریِ Go تحویل نمی‌شود |

نتیجه: هیچ موتورِ Update در بستهٔ واقعی وجود ندارد؛ بنابراین چرخهٔ
`Check → Download → Verify → Stage → Apply → Restart → Health` قابلِ اجرا نبود.
موتورِ موازی ساخته نشد. هر ۱۰ سناریو (موفق، قطعِ دانلود، فایلِ خراب، هش/امضا،
manifest ناسازگار، بستنِ برنامه، شکستِ نسخهٔ جدید، Rollback، حفظِ داده،
Update متوالی) `NOT_MEASURED` است. تنها شاهدی که اندازه‌گیری شد، **primitives**
نصبِ سایلنت است: ارتقایِ واقعیِ نصبِ موجود با حفظِ `user.db`/تنظیمات (§۵).
شاهد: `_audit/phase48/update-audit.json`.

## ۷. تطبیقِ ۳۰ نماد با ره‌آورد (مورد ۸)

گزارشِ کامل و روشِ بازتولید: `docs/opportunity-center/phase48/PARITY.md`.

| قلم | نتیجه |
| --- | --- |
| مرجع | `capture2.json` با `sha256=b27564da…0ddba6` بازیابی شد؛ ۱۸۰ سری، ۲۱۸٬۶۸۸ ردیف، همه 200 |
| پاک‌سازی | 16,798 ردیفِ تکراری حذف؛ 376 تعارض؛ ۰ ردیفِ بی‌تاریخ/ناموجود |
| هویت | ۳۰/۳۰ با `ins_code` و `symbol_identity`؛ هر نماد یک `asset_id` |
| بانکِ پاریتی | بانکِ فاز ۴٫۵: 11,533 کندل؛ 11,470 روزِ مشترک؛ پایان 2026-11-04 |
| ضریبِ type7 | ۲۹/۳۰ دقیق؛ **۳۰/۳۰ داخلِ ۰٫۱٪**؛ شستا بیشینهٔ 3.44e-04 |
| OHLC تعدیل‌شده | 6,677 / 11,470 (58.2%) در گردکردن — **FAIL** |
| حجمِ type7 | 11,116 = خام÷ضریب؛ ۰ = خام؛ 354 سایر (تفاوتِ قراردادی) |
| مقدارِ خام type0 | 3,378 open، 1,537 high، 1,716 low، 354 حجم نابرابر — **FAIL** |
| پوشش | 71,894 روزِ فقط-مرجع (۲۰۱۰→۲۰۲۴)؛ Bors از 2024-08 — **FAIL/OPEN** |
| بانکِ فاز ۴٫۷/۴٫۸ | 12,086 کندل؛ پایان 2026-09-30…10-11؛ شستا ۶٫۲۱۳٪ (رویدادِ 2026-10-24 غایب) |

**تفسیر:** کدِ فعلی رویِ بانکِ فاز ۴٫۵ عیناً اعدادِ گزارشِ فاز ۴٫۵ را می‌دهد
(11,470 مشترک؛ 3,378 open؛ 6,677 OHLC؛ 3.44e-04). بنابراین تفاوتِ نتیجه رویِ
بانکِ فاز ۴٫۷ از **دادهٔ عقب‌ماندهٔ آن بانک** است، نه تغییرِ موتور. عددِ 12,086ِ
گزارشِ ۴٫۷ همین بانک است. هیچ دادهٔ خامی اصلاح/بازسازی نشد و Backfillِ عملیاتی
اجرا نشد.

## ۸. Market Watch Regression (مورد ۹)

`python dev/test_phase47_ingestion_v1.py` → **37 passed / 0 failed**.

| دسته | تعداد | نتیجه |
| --- | ---: | --- |
| گاردهایِ اصلیِ `market_watch` | ۱۰ | همه سبز |
| گاردهایِ معنایِ depth/price_change/eps/pe (فاز ۴٫۸) | ۶ | همه سبز |
| کنترلِ منفی | ۲ | هر دو نقص را بدونِ گارد اثبات کردند |
| سایرِ گاردهایِ ingestion/candle | باقی | سبز |

مواردِ پوشش‌داده‌شده: `price_first` با پاسخِ لاغر NULL نمی‌شود؛ حجمِ مثبت همان
نشست صفر نمی‌شود؛ رشدِ واقعی ثبت می‌شود؛ اجرایِ تکراری idempotent است؛ نشستِ
تازه مقدارِ قبلی را جایگزین می‌کند؛ نمادِ متوقف حجم/اولین قیمتِ دیروز را نشان
نمی‌دهد؛ صفرِ `price_change`/`eps` و عمقِ خالیِ پس از بستن مقدارِ واقعی‌اند؛
`pe`ِ غایب NULL می‌ماند. ۱۶ + 1,377 رکوردِ تاریخیِ بازسازی‌ناپذیر دست‌نخورده
ماندند و هیچ Backfill اجرا نشد.

## ۹. GitHub Actions و Race Detector (مورد ۱۰)

Run واقعی: [42660266858](https://github.com/johnwarchief/BorsTerminal-src/actions/runs/42660266858)
روی `d00fe7e6`، شاخهٔ `mission/phase48-final-verification-2026-11-09`.

| جاب | نتیجه | نقش |
| --- | --- | --- |
| go backend (vet / ast-arch / unit-tests) | success | Go tests |
| go race detector | **success** | Race Detector ([job](https://github.com/johnwarchief/BorsTerminal-src/actions/runs/42660266858/job/129309651413)) |
| go backend on windows (windows-latest) | success | Windows build |
| go backend on windows (windows-2022) | success | Windows build |
| frontend v2 (typecheck / vitest / build) | success | Frontend tests/build |
| desktop delivery (bundle + Tauri + installer) | **success** | Rust/Tauri build، Bundle Contract، Installer Artifact ([job](https://github.com/johnwarchief/BorsTerminal-src/actions/runs/42660266858/job/129312548968)) |
| data integrity guards | success | ingestion/candle/repair |
| node --check on our bundles | success | syntax |
| EOL / attributes / no tracked junk | success | hygiene |
| offline guard suites (`python dev/run_all_tests.py`) | **failure** | از قبل قرمز؛ بی‌ربط به این شاخه |

در جابِ delivery: `onedir contract PASS`، `bundle contract OK`، Shell با Rust
`1.99.1` ساخته شد (`sha256=b0c1cdbd…`)، و نصابِ `v1.0.95` با ISCC ساخته شد
(`sha256=5ff645c6…`، 8.2s). خروجی‌ها به‌عنوانِ artifact آپلود شدند.

**قرمزیِ `python-guards` از قبل موجود است:** همان جاب رویِ main
(`9a919e82`، run [40825133692](https://github.com/johnwarchief/BorsTerminal-src/actions/runs/40825133692))
هم failure است و annotation آن «chart API guard» را نشان می‌دهد (نیازمندِ
`node_modules`/fixture در آن جاب). این مأموریت آن را تغییر نداد و PASS اعلام
نمی‌کند؛ اجرایِ کلِ run به همین دلیل `failure` است، در حالی که هر هفت جابِ
الزامیِ مأموریت سبزند.

## ۱۰. مواردِ باقی‌مانده و علتِ دقیق (مورد ۱۱)

| # | مورد | وضعیت | علتِ دقیق / کاری که لازم است |
| ---: | --- | --- | --- |
| ۱ | دادهٔ کندلِ بستهٔ نصب‌شده | **FAIL** | `market.db`ِ بسته فقط یک روز است؛ `market.db.lzma` (445,676 ردیف) استفاده نمی‌شود؛ نیازمندِ تصمیمِ مالک (استخراجِ lzma یا بسته‌بندیِ DB کامل) |
| ۲ | بانکِ ۴٫۷ عقب‌مانده | **FAIL** | پایان 2026-09-30…10-11؛ رویدادِ 2026-10-24 شستا غایب؛ ۶٫۲۱۳٪ ضریب |
| ۳ | پوششِ ۲۰۱۰–۲۰۲۴ | **FAIL / OPEN** | 71,894 روزِ فقط-مرجع؛ Bors از 2024-08 |
| ۴ | OHLC خام/تعدیل‌شده | **FAIL** | 9 نمادِ قدیمیِ بدونِ `src` (open ۸–۱۱٪)؛ OHLC تعدیل‌شده 58.2٪؛ نیازمندِ اصلاح/تصمیمِ داده |
| ۵ | موتورِ Auto-Update | **BLOCKED** | 501 NOT_PORTED؛ بدونِ کلاینت؛ legacy Python در بسته نیست؛ ساختِ موتورِ تازه خارج از محدوده |
| ۶ | نصب/Repair تعاملی | **NOT_MEASURED** | صفحهٔ maintenance فقط با کلیکِ انسان؛ رفتارِ سایلنت اندازه‌گیری شد |
| ۷ | `python-guards` در CI | **FAIL** (از قبل) | chart API guard رویِ main هم قرمز است؛ بی‌ربط به تغییراتِ این شاخه |
| ۸ | باقی‌ماندهٔ `oc/` در Uninstall | مشاهده | در `[UninstallDelete]` نیست؛ تغییرِ رفتار بدونِ تأییدِ مالک انجام نشد |
| ۹ | مجوزِ remote برایِ صفحهٔ Tauri | مشاهده | صفحه از loopback سرو می‌شود؛ plugin بدونِ فراخواننده بی‌اثر است |

## ۱۱. main، Tag و Release (مورد ۱۲)

- **main:** `9a919e82f5b836cc7ec4be5ba04a39ec2f74b4e2` روی Remote؛ این مأموریت
  هیچ commit/merge رویِ main انجام نداد.
- **Tag:** آخرین تگِ Remote `v1.0.98`؛ تگِ تازه ساخته/ push نشد.
- **Release:** آخرین ریلیز `BorsTerminal Ultimate v1.0.98` (۲۰۲۶-۱۰-۲۳)؛
  ریلیزِ تازه‌ای ساخته نشد.
- **Worktreeها:** ۴۹ ثبت؛ فقط همین Worktree تغییر کرد؛ هیچ Worktreeِ دیگری
  خوانده/نوشته/پاک نشد.

## ۱۲. پایبندی به محدودیت‌ها و شرطِ ورود به فاز ۵

| محدودیت | رعایت |
| --- | --- |
| بدونِ تغییر به main / بدونِ merge / بدونِ tag یا release | بله |
| بدونِ تغییرِ دیتابیسِ عملیاتی | بله؛ همهٔ آزمون‌ها رویِ کپیِ آزمایشگاهی و نصبِ موقت |
| بدونِ انتشارِ دادهٔ خامِ ره‌آورد | بله؛ فقط جمع‌بندی و روشِ بازتولید در گیت |
| بدونِ اندیکاتور/استراتژیِ فاز ۵ | بله |
| بدونِ تغییرِ قواعدِ FTS؛ `approval_enabled=false` | بله |
| بدونِ حذفِ قابلیتِ موجود | بله |
| بدونِ توقفِ فرآیند/سرویسِ نصب‌شدهٔ واقعی | بله |

**شرطِ ورود به فاز ۵:** این فاز **آغاز نشده است**. سه گیتِ باقی‌مانده:
(۱) دادهٔ کندلِ بستهٔ نصب‌شده (§۱۰ ردیفِ ۱)، (۲) موتورِ Update و Rollback
(§۶)، (۳) پوشش/کیفیتِ دادهٔ پاریتی و قرمزیِ از قبل موجودِ `python-guards`.
تا وقتی مالک این‌ها را تکمیل یا صریحاً بپذیرد، فاز ۵ آغاز نمی‌شود.

## شواهدِ محلی (gitignored)

| فایل | چیست |
| --- | --- |
| `_audit/phase48/bundle-manifest.txt` | sha256 همهٔ ۷۷ فایلِ بسته |
| `_audit/phase48/shell-probe.json` | اجرایِ واقعیِ Shell/WebView2 |
| `_audit/phase48/run-evidence.json` | اجرایِ borsd رویِ پورتِ 8137 و APIها |
| `_audit/phase48/installer-evidence.json` | نصب/ارتقا/Repair/Uninstall با هش‌ها |
| `_audit/phase48/update-audit.json` | وضعیتِ مسیرِ Update و ۱۰ سناریو |
| `_audit/phase48/parity/summary.json` و `per-symbol.csv` | جمع‌بندیِ ۳۰ نماد |
| `_audit/phase48/parity/control-p45lab/*` | بازتولیدِ اعدادِ فاز ۴٫۵ با کدِ فعلی |
| `_audit/phase48/parity/identity-p45.json` | تأییدِ هویت با `ins_code` |

**CI:** [run 42660266858](https://github.com/johnwarchief/BorsTerminal-src/actions/runs/42660266858)
— جاب‌هایِ الزامی سبز؛ `python-guards` از قبل قرمز.
