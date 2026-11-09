# گزارش نهایی Phase 4.8 Closeout — بسته‌بندی داده، آپدیت، تاریخچه و Repair

- تاریخ: 2026-11-09
- شاخه: `mission/phase48-closeout-2026-11-09`
- Base: `8d291ca21a6ba43f35905dd69b9a0484fb9c6788`
- Final code: `1c5be5df35b8b6547b9bdc00cf1d718e64b87e0c` (کامیتِ گزارش روی همین شاخه اضافه می‌شود)
- CI: [run 42689986136](https://github.com/johnwarchief/BorsTerminal-src/actions/runs/42689986136)

## وضعیتِ کلی

| مورد | وضعیت | خلاصه |
| --- | --- | --- |
| S1 — پایه/شاخه/Worktree | PASS | Base واقعی `8d291ca2`؛ هیچ Worktree دیگری تغییر نکرد |
| S2 — بستهٔ داده و Seed | PASS (بستهٔ موجود) | 447,885 ردیف در نصبِ واقعیِ سندباکس؛ 2010–2024 در بستهٔ نصب نیست (BLOCKED) |
| S3 — آپدیت و Rollback | PASS | 25/25 سناریو با کلید/کانال آزمایشیِ مستقل |
| S4 — تاریخچه و Backfill | PASS خام / BLOCKED تعدیل | 72,222 ردیفِ خام با provenance؛ زنجیرهٔ تعدیلِ پیش از 2024 ناقص است |
| S5 — Repair تعاملی | PASS | 3/3 سناریو؛ فایل‌های برنامه بازگردانی، دادهٔ کاربر دست‌نخورده، اپ سالم |
| S6 — Regression و CI واقعی | PASS با یک استثنای مستقل | 9 از 10 Job سبز؛ `python-guards` همان خطای ازپیش‌موجودِ Chart API |
| S7 — گزارش و Commit/Push | PASS | همین فایل؛ بدون Merge/Tag/Release |

## پنجرهٔ داده و پوشش

| منبع | پوشش | حجم/تعداد | وضعیت |
| --- | --- | --- | --- |
| `market.db.lzma` مخزن | 2024-08-24 تا 2026-11-04 | 78,667,800 بایت | مرجعِ Seed |
| `market.db.gz` بیلد | همان Seed با gzip | 118,483,498 بایت | در بستهٔ نصب |
| `market.db` پس از merge | 2024-08-24 تا 2026-11-04 | 302,022,656 بایت؛ 447,885 ردیف `price_history`؛ 133,257 `daily_prices`؛ 3,680 `market_watch` | اعمال‌شده (merge) |
| Backfill ره‌آورد (کاربرگ) | 2010-01-02 تا 2026-11-09 | 511,139 ردیفِ کل؛ 72,222 ردیفِ تازه | در Work DB، نه در بستهٔ نصب |

## ۱) SHA پایه و نهایی

- Base: `8d291ca21a6ba43f35905dd69b9a0484fb9c6788`
- Final code: `1c5be5df35b8b6547b9bdc00cf1d718e64b87e0c`
- Remote branch head پیش از این گزارش: `1c5be5df35b8b6547b9bdc00cf1d718e64b87e0c`
- کامیتِ همین گزارش با `git log -1 --format=%H` روی شاخه خوانده می‌شود; گزارش بدون Merge/Tag/Release Push می‌شود.

**وضعیت: PASS**

## ۲) فایل‌های تغییر‌یافته

مجموعِ کدِ مأموریت در `8d291ca2..1c5be5df` (بدونِ همین گزارش): **38 فایل، +6,329 / -48**.

| حوزه | فایل‌های اصلی |
| --- | --- |
| Seed (Go) | `backend-go/internal/seed/seed.go`، `seed_test.go`، `cmd/borsd/app.go`، `main.go`، `internal/config/config.go`، `internal/httpapi/server.go` |
| Updater (Go) | `backend-go/internal/update/{update,watcher,download,backup,handlers,process_windows,process_other}.go` و تست‌ها؛ `scripts/make_go_update_manifest.py` |
| Backfill/Verify | `tools/phase48/backfill_reference.py`، `tools/phase48/verify_history_api.py`، `dev/test_phase48_backfill_history_v1.py`، `dev/test_phase48_history_verify_v1.py`، `dev/run_all_tests.py` |
| Frontend-v2 | `src/features/updater/api/useUpdater.ts`، `ui/UpdateChip.tsx`، `app/shell/Topbar.tsx`، `shared/api/http.ts`، `__tests__/update-chip.spec.tsx`، `__tests__/board-views-export.spec.tsx` |
| بسته/انتشار | `installer/bors_setup.iss`، `release.ps1`، `scripts/build_all.py`، `scripts/make_fast_seed.py`، `scripts/publish_github_release.py` |
| CI | `.github/workflows/guards.yml`، `.github/workflows/release.yml` |
| متفرقه | `.gitignore` |

فهرستِ کامل: `git diff --name-only 8d291ca2..1c5be5df`.

**وضعیت: PASS**

## ۳) وضعیتِ بستهٔ دیتابیس و تعداد کندلِ نصب‌شده

از `_audit/phase48closeout/installer/installer-evidence.json`:

| سنجه | مقدار |
| --- | --- |
| `price_history` نصب | **447,885 ردیف** |
| بازه | `2024-08-24` تا `2026-11-04` |
| `daily_prices` | 133,257 |
| `market_watch` | 3,680 |
| Seed | `applied`، حالت `merge`، منبع `market.db.gz`، SHA-256 `f3c627c6…` |
| Backup پیش از Seed | `backups/market.db.before-seed-20261109T181744.bak` |
| Health پس از نصب | `ok`، Go 1.27.3، read-only |

تاریخچهٔ 2010–2024 در Work DB بازیابی شده (بخش ۶) اما **در بستهٔ نصب/Seed منتشر نشده** است; فعال‌سازیِ آن به‌دلیلِ ناقص‌بودنِ زنجیرهٔ تعدیلِ پیش از 2024 مسدود (BLOCKED) است.

**وضعیت: PASS برای بستهٔ کاملِ موجود؛ BLOCKED برای 2010–2024 در نصب**

## ۴) `/api/ma/فولاد` و تاریخچهٔ واقعی

### نصب/آزمایشگاه (Seed موجود)

- `/api/ma/فولاد`: **200**، 394 Bar، بازهٔ `2024-08-24..2026-11-04` (`_audit/phase48closeout/lab-evidence.json`)
- `/api/chart-db/فولاد`: 200، 394 کندل، همان بازه
- `/api/market`: 200، 3,680 ردیف
- اولین استارت با Seed: 18.88 ثانیه

### Work DB پس از Backfill (کاربرگ، نه نصب)

- `/api/chart-db/فولاد`: **3,689 کندل**، `2010-01-02..2026-11-09`
- `/api/ma/فولاد`: **2,000 Bar**، `ma_status=ok`؛ MA5 اول `2017-09-25=80.72`، آخر `2026-11-09=4432`
- `acceptance` در `_audit/phase48closeout/backfill/verify-api.json`

### پاریتی خام و تعدیل‌شده (30 نماد)

| سنجه | مقدار |
| --- | --- |
| ردیف‌های جدیدِ خام (2010–2024 و پس از 2024) | 72,222 مشترک، **0 اختلاف** در O/H/L/V |
| ردیف‌های قدیمیِ خام | 11,121 مشترک؛ open 3,251، high 1,328، low 1,508، volume 115 |
| مبناهای close در ردیف‌های قدیمی | last 156، closing 2,355، other 8,610؛ 10,911 ردیف بدون `last` |
| ردیف‌های Open=Close قبلی | 729؛ جابه‌جاییِ تاریخ: 8؛ ردیفِ نامعتبر مرجع: 21 |
| تعدیلِ دقیقِ پیش از 2024 | 6,472 / 11,121 = **58.2%** (تلورانس 0.5)؛ factor_bad 448؛ حداکثر خطای نسبی 6.213% |
| تعدیلِ جدید (همان تلورانس) | 35,254 / 72,222 = **48.8%**؛ factor_bad 37,404؛ حداکثر خطای نسبی 2446.29 |
| شکل پس از حذفِ لنگرِ ثابت (قدیم/جدید) | 6,909 و 18,580 |

**وضعیت: PASS برای API و پاریتی خام؛ BLOCKED برای تعدیلِ پیش از 2024؛ INSUFFICIENT_DATA برای داوریِ close در 10,911 ردیفِ بی‌last**

## ۵) آپدیت واقعی و Rollback

از `_audit/phase48closeout/update/update-evidence.json`:

- **25/25 سناریو PASS** دربارهٔ: Manifest ناسازگار، امضا/هش، دانلود ناقص، قطعِ شبکه، نصب، Restart، Health، Update پشت‌سرهم، Rollback دستی و خودکار.
- کلیدِ آزمایشیِ مستقل Ed25519؛ `test_pubkey_sha256=f441def9…`؛ کانال `go`؛ هیچ کلید/کانالِ تولیدی استفاده نشد.
- نسخه‌ها: 1.0.95 → 1.0.96 → 1.0.97؛ بیلدِ خرابِ 1.0.98 عمداً Rollback شد.
- Health نهایی: `version=1.0.96`, `status=ok`؛ `update_last.status=rolled_back`.
- دادهٔ کاربر (`user.db`، `oc/oc_client.db`، Cache و FTS) در هر گذار بایت‌به‌بایت حفظ شد.
- همه در سندباکسِ `%LOCALAPPDATA%\BorsTerminal_Phase48UpdateTest\app`؛ نصب/رجیستریِ واقعی دست نخورد.

**وضعیت: PASS**

## ۶) Backfill و پاریتی 30 نماد

از `_audit/phase48closeout/backfill/backfill.json` و `verify-api.json`:

| سنجه | مقدار |
| --- | --- |
| نمادها | 30 |
| ردیف‌های پیش از اجرا | 438,917 |
| ردیف‌های پس از اجرا | 511,139 |
| درج‌شده | **72,222** (71,158 در 2010–2024؛ 1,064 پس از 2024) |
| فقط‌در‌مرجع | 72,243؛ هم‌پوشانی 11,121 |
| تغییرِ ردیفِ موجود | **0**؛ ردیفِ گم‌شده 0 |
| نامعتبر | 21 (هندسهٔ O/H/L/C) |
| `src` پس از اجرا | `rahavard365=72,222`، `legacy-unknown=11,217`، `board=869` |
| مرجع | 30 نماد، Sha-256 `68a1c803…`؛ بستهٔ اصلاح `ra365-r32b-v2` با Sha-256 `4b1ecb4c…` |
| Capability | 30 × `AVAILABLE_REFERENCE_CORRECTION` |

### ریشهٔ انسدادِ تعدیل (مهم)

| سنجه | مقدار |
| --- | --- |
| رویدادهای Product | 652 |
| Stepهای بستهٔ اصلاح | 271 |
| Stepهای مرجع | 501 |
| Product‌های منطبق با مرجع | 443 |
| Stepهای بستهٔ منطبق با مرجع | 264 |
| ردیف‌های رسمیِ ledger | 284 |

حالتِ `authoritative` همهٔ رویدادهای Product پیش از `as_of=2026-10-19` را Suppress می‌کند؛ چون بستهٔ اصلاح فقط 271 گام دارد، 443 گامِ Product که با مرجع می‌خواند حذف می‌شود. نتیجه: سریِ تعدیل‌شدهٔ پیش از 2024 از مرجع مستقل نیست. پیشنهادِ اصلاح (Rebuild بستهٔ کامل یا حالت Overlay) **اجرا نشد** چون نیازمند تصمیم/تأیید مالک است.

- «شستا»: نسبتِ ثابت `1.06213` در ردیف‌های قدیمی؛ علت: رویدادِ 2026-10-25 در Product موجود است ولی در سریِ مرجعِ استفاده‌شده نیست. 448 ردیف.
- 9 نماد با مبنایِ `open` قدیمی؛ 729 ردیف `open=prev close`؛ 8 جابه‌جاییِ تاریخ؛ 21 ردیفِ نامعتبرِ مرجع؛ 10,911 ردیفِ بی‌last.
- 6 نمادِ کوتاه‌تاریخ کاملاً منطبق‌اند؛ 29 از 30 نماد در پنجرهٔ اخیر ضریبِ یکسان دارند و 9 نماد فقط به‌خاطرِ `open` خام شکست می‌خورند.

**وضعیت: PASS برای اجرا/Provenance/Idempotency/رول‌بک و پاریتی خام؛ BLOCKED برای تعدیلِ 2010–2024 و انتشار در Seed**

## ۷) Repair تعاملیِ Installer

از `_audit/phase48closeout/repair/repair-evidence.json` و `installer-repair-audit.json`:

- **3/3 سناریو PASS**: Repair سالم؛ پس از حذف `BorsTerminal_Ultimate.exe`؛ پس از خراب‌کردن `frontend/index.html`.
- UI با **Computer Use (UI Automation)** روی نصب‌کنندهٔ آزمایشیِ ایزوله؛ صفحهٔ Maintenance با 4 گزینه، گزینهٔ 0 («نصبِ مجدد / تعمیر فایلها در همان مسیر (توصیه‌شده)») انتخاب‌شده و مسیرِ قبلی = سندباکس.
- قفل‌های ایمنی: AppId آزمایشی `{C3D84F60-2A19-4E7B-8C55-6F9A1B2D3E40}`، `DefaultDirName` سندباکس، حذفِ Password/Encryption فقط در نسخهٔ آزمایشی، حذفِ `[Run]/[Icons]/[Tasks]`، و `EnsureAppNotRunning`/`SweepOrphanLeftovers` قبل از `taskkill`/`DelTree` خارج می‌شوند.
- نصب‌کنندهٔ تولیدی هرگز اجرا نشد؛ Registry واقعی و `market.db` عملیاتی دست نخوردند.

| سنجه | مقدار |
| --- | --- |
| `BorsTerminal_Ultimate.exe` | `1b203399…` = هشِ باندل (پس از حذف، بازگردانده شد) |
| `frontend/index.html` | `32b8ecfd…` = هشِ باندل (پس از خرابی، بازگردانده شد) |
| `market.db` | `1666dd02…` بدون تغییر در هر 3 سناریو |
| `user.db` / `oc/oc_client.db` / `fts_thresholds.json` / `price_basis.json` | هش‌ها قبل و بعد یکسان؛ Sentinelهای SQLite سالم |
| Health پس از Repair | `status=ok`، پورت 8158، `market_mode=read-only`؛ `/api/ma/فولاد` و `/api/market` پاسخ 200 |

- نصب‌کنندهٔ آزمایشی از `installer/bors_setup.iss` (Sha-256 `7861f31c…`) ساخته شد؛ Sha-256 نسخهٔ آزمایشی `c22dce20…` و Setup `0015050f…`.
- صفحهٔ رمزِ نصب‌کنندهٔ تولیدی تست نشد (طبقِ سیاستِ عدمِ Automation دیالوگِ احراز هویت)؛ منطقِ Repair خودِ اسکریپتِ تولیدی است.

**وضعیت: PASS**

## ۸) نصب تمیز، ارتقا و حذف

از `_audit/phase48closeout/installer/installer-evidence.json` (AppId آزمایشی، مسیر و پورت ایزوله):

| سناریو | نتیجه |
| --- | --- |
| نصب تمیز | Health ok؛ Seed اعمال شد؛ 447,885 ردیف |
| ارتقا روی نصبِ لاغر | Health ok؛ ردیفِ Sentinel حفظ شد؛ Seed merge شد؛ `user.db`/FTS هش یکسان |
| ارتقای Seed دوم | ردیفِ Sentinel جدید درج شد؛ `price_history=447,887`؛ دادهٔ کاربر هش یکسان |
| حذف | `rc=0`؛ EXE/Shell/market.db/Seed حذف؛ `user.db` و `fts_thresholds.json` باقی؛ Registry پاک |

- این تست پیش از Backfill اجرا شد؛ Backfill در بستهٔ نصب نیست (بخش ۶).
- S5 روی همین شاخه نصب/Repair را دوباره اجرا کرد و PASS داد.

**وضعیت: PASS**

## ۹) نتیجهٔ Go / Frontend / Rust / Race

| بخش | محلی | CI |
| --- | --- | --- |
| Go `go vet ./...` | PASS | PASS (`go backend`) |
| Go `go test ./...` | PASS (همهٔ پکیج‌ها) | PASS (Linux + Windows 2022 + windows-latest) |
| Go Race Detector | اجرا نشد (GCC روی این ماشین نیست) | **PASS** (`go race detector`) |
| Frontend-v2 Typecheck | PASS | PASS |
| Frontend-v2 Vitest | **105 فایل / 861 تست PASS** | PASS |
| Frontend-v2 Build | PASS | PASS |
| Rust/Tauri `cargo test --locked` | **4/4 PASS** | PASS (Delivery) |
| Rust/Tauri `cargo build --release --locked` | PASS | PASS (Delivery) |
| Bundlecheck / Onedir Contract | — | **PASS** (`desktop delivery`) |
| Seed Merge واقعی (445k) | — | **PASS** (`desktop delivery`) |
| ساختِ نصب‌کنندهٔ ویندوز | — | **PASS** (`desktop delivery`) |

نکتهٔ اصلاحیِ مرتبط: `UpdateChip` در S3 به Topbar اضافه شد و تستِ قدیمیِ `board-views-export` بدون `QueryClientProvider` رندر می‌شد. تست با Provider اصلاح و در کامیت `1c5be5df` ثبت شد؛ کلِ 861 تست سبز است. CI نیز Frontend را سبز تأیید کرد.

**وضعیت: PASS**

## ۱۰) GitHub Actions واقعی

- Link: **[run 42689986136](https://github.com/johnwarchief/BorsTerminal-src/actions/runs/42689986136)**
- Head: `1c5be5df35b8b6547b9bdc00cf1d718e64b87e0c`

| Job | نتیجه |
| --- | --- |
| `go backend` | success |
| `go race detector` | success |
| `go backend on windows (2022)` | success |
| `go backend on windows (latest)` | success |
| `frontend v2` | success |
| `data integrity` | success |
| `repo hygiene` | success |
| `js syntax` | success |
| `desktop delivery` | **success** (Frontend، Go، Tauri، Bundlecheck، Seed Merge، Installer، Upload) |
| `python-guards` | **failure** — خطای ازپیش‌موجود |

### مقایسهٔ `python-guards` با Main و Base

| اجرا | نتیجه |
| --- | --- |
| همین شاخه، Base `8d291ca2` (run 42662403979) | همان `FAILED: chart API guard: installed klinecharts v10 exports…` |
| اجرای جدید `1c5be5df` (run 42689986136) | همان `FAILED: chart API guard…` |
| Main `9a919e82` (run 40825133692، 2026-10-29) | `GATE_REFUSED: protected DB not found` — علتِ قدیمی‌تر و متفاوت |
| محلی با `frontend/node_modules` | `dev/chart_api_check_v95.py` → **18/18 PASS** |

علت: Jobِ `python-guards` فقط `requirements.txt` نصب می‌کند و `frontend/node_modules` (klinecharts) را ندارد؛ گاردِ Chart API به آن نیاز دارد. این نقصِ محیطِ CI است، ازپیش‌موجود روی Base، و به تغییراتِ این مأموریت مربوط نیست؛ طبقِ قیدِ مأموریت («فقط در صورت ارتباط مستقیم اصلاح شود») اصلاح نشد. Database محافظت‌شده در همین Job با اثرانگشتِ `04137b38…` قبل/بعد یکسان ماند (`PROTECTED_DB_UNCHANGED`).

**وضعیت: PASS برای اجرای واقعی و 9/10 Job؛ FAIL برای Jobِ ازپیش‌موجودِ `python-guards` (مستقل)**

## ۱۱) موارد باز و ریسک‌ها

1. **BLOCKED — تعدیلِ پیش از 2024:** زنجیرهٔ `authoritative` فقط 271 گام دارد در برابر 501 مرجع/652 Product؛ 443 گامِ Productِ منطبق حذف می‌شود. نتیجه: 58.2% تطابقِ دقیق در 2010–2024؛ Max Rel 6.213% (قدیم) و 2446.29 (جدید). اصلاح پیشنهادی: بازسازیِ بستهٔ کامل یا Overlayِ Product؛ نیازمند تأیید مالک و بازسازیِ بستهٔ اصلاح.
2. **BLOCKED — انتشار 2010–2024 در نصب:** 72,222 ردیفِ خام با Provenance در Work DB هست؛ به Seed/نصب منتقل نشده. نصبِ واقعی 447,885 ردیف (2024-08-24..2026-11-04) دارد.
3. **9 اختلافِ Openِ باقی‌مانده:** 9 نماد با مبنایِ Openِ قدیمی؛ 729 ردیف `open=prev close`؛ 8 جابه‌جاییِ تاریخ؛ 21 ردیفِ نامعتبرِ هندسه؛ 10,911 ردیفِ بی‌last. مبنا: `verify-api.json`.
4. **INSUFFICIENT_DATA — مبنای close:** `close` محلی = قیمتِ پایانیِ حراج؛ مرجع Type0 = آخرین معامله. برای ردیف‌هایِ بی‌last داوریِ close با این مرجع ممکن نیست.
5. **شستا:** نسبتِ ثابت `1.06213` در 448 ردیفِ قدیمی؛ علت: نبودِ رویدادِ 2026-10-25 در سریِ مرجع. بدونِ اصلاح.
6. **`python-guards`:** Chart API Guard در CI بدونِ `frontend/node_modules` شکست می‌خورد؛ محلی 18/18. نقصِ مستقل از تغییرات.
7. **مشاهده — `SweepOrphanLeftovers`:** در `installer/bors_setup.iss` تعریف شده ولی هیچ‌جا فراخوانی نمی‌شود (Dead Code). روی Repair تأثیری ندارد.
8. **محدودیتِ تستِ Repair:** صفحهٔ رمزِ نصب‌کنندهٔ تولیدی Automation نشد؛ نسخهٔ آزمایشی Password/Encryption ندارد. منطقِ Repair همان `[Code]` تولیدی است.
9. **سندباکس‌های تست:** `%LOCALAPPDATA%\BorsTerminal_Phase48RepairTest\app`، `%LOCALAPPDATA%\BorsTerminal_Phase48UpdateTest\app` و `_audit/phase48closeout/installer/install` باقی مانده‌اند؛ هیچ‌کدام نصبِ واقعی نیستند.
10. هیچ اندیکاتور/استراتژی فاز 5 اضافه نشد؛ `/fts-screen`، `approval_enabled=false`، Q1 Deferred، رتبه‌بندی Lexicographic و نبودِ Composite Score/Weight دست‌نخورده‌اند.

**وضعیت: PASS (مستندسازی)؛ موارد 1 و 2 BLOCKED**

## ۱۲) main / Tag / Release / Worktree

- **Merge به main:** انجام نشد.
- **Tag:** ساخته نشد.
- **Release:** ساخته نشد.
- **Push:** فقط شاخهٔ `mission/phase48-closeout-2026-11-09` روی `johnwarchief/BorsTerminal-src`.
- **کیتِ ادامهٔ سشن:** `tools/phase48/continuation/README.md` — مسیرها، هش‌ها و فرمان‌های بازتولیدِ S4/S5. نسخهٔ فشردهٔ سه DB در `data/phase48/db/` با SHA-256 در گیت است؛ DBهای خام و بستهٔ مرجعِ اشتراکی در گیت نیستند (دلیل و مسیرشان در همان فایل).
- **Main:** Remote `9a919e82…`؛ Local `92703183…`؛ هیچ تغییری روی main انجام نشد.
- **Worktreeها:** فقط Worktree اصلی بررسی/استفاده شد؛ سایر Worktreeها تغییر نکردند.
- **نصب واقعی/Registry واقعی/دیتابیس عملیاتی:** دست نخوردند؛ تست‌ها روی AppId/مسیر/پورت/کلید/کانالِ آزمایشی و کپیِ کاربرگ اجرا شدند.

**وضعیت: PASS**

## جمع‌بندی

- **PASS:** افزایشِ دادهٔ Seed و حفظِ دادهٔ کاربر در نصب/ارتقا (447,885 ردیف)؛ آپدیتِ امضاشده با Health و Rollback (25/25)؛ Raw Backfill با Provenance (72,222 ردیف، 0 تغییرِ موجود، 21 نامعتبر)؛ Repair تعاملی (3/3)؛ نصب/ارتقا/حذف با حفظ دادهٔ کاربر؛ Go/Frontend/Rust/Race و Delivery ویندوز در CI.
- **BLOCKED:** زنجیرهٔ تعدیلِ پیش از 2024 (58.2% دقیق) و در نتیجه انتشارِ 2010–2024 در بستهٔ نصب. رفعِ آن نیازمند بازسازی/Overlayِ بستهٔ اصلاح و تأیید جداگانهٔ مالک است.
- **مستقل/ازپیش‌موجود:** `python-guards` در CI به‌دلیلِ نبودِ `frontend/node_modules`؛ محلی 18/18 و در Base هم قرمز بوده است.
- **فاز 5:** شروع نشود تا تصمیمِ مالک دربارهٔ بستهٔ تعدیل و پذیرشِ این گزارش.
