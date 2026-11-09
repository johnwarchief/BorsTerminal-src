# گزارشِ پایانیِ فاز ۴٫۷ — یکپارچگیِ خطِ داده و چرخهٔ تحویلِ دسکتاپ

**شاخه:** `mission/phase47-data-pipeline-desktop-delivery-2026-11`
**مبنایِ مأموریت (Phase 4.5 base):** `7d2335de0e0f3b6bb2c4bc23f26bc6814388674a`
**کدِ آزمون‌شده در فاز ۴٫۵:** `6db018f25c692d84347e5079e13f9e59291b79e2`
**کامیت‌هایِ این فاز:** `19bdc30c` (اصلاحِ ingestion + ابزارها + CI)، `73065371`
(گزارشِ دورِ اول)، و کامیتِ همین دور (گاردِ `market_watch` + نتایجِ نصاب)
**worktree:** `C:/Users/PCMOD/Desktop/BorsTerminal`

نسبتِ دو SHA: `7d2335de` فرزندِ `11f4b128` است و `6db018f2` جدِ آن؛ یعنی مبنایِ
مأموریت **۲۸ کامیت جلوتر** از درختی بود که این نشست رویِ آن باز شد. شاخهٔ مأموریت
از `7d2335de` ساخته شد، نه از `11f4b128`.

## ۱. خلاصهٔ اجرایی

| محور | وضعیت |
| --- | --- |
| علتِ ریشه‌ایِ مشکلاتِ ingestion | **پیدا و اصلاح شد** (۳ نقصِ واقعی + ۲ ادعایِ نادرستِ گزارشِ قبل) |
| Backfill | **idempotent با snapshot و manifest؛ رویِ کپی اجرا شد** |
| `market_watch` (پاسخِ لاغر) | **اندازه‌گیری و اصلاح شد** — ۱۶ + ۱٬۳۷۷ ردیفِ آسیب‌دیده شاهد |
| اعتبارسنجیِ محلیِ ۳۰ نماد | **PASS** (پوشش، تکرار، provenance) |
| تطبیق با مرجع (ره‌آورد) | **BLOCKED** — برداشتِ مرجع در درخت نیست (۱۱/۳۰ نماد فقط ردیفِ آرشیویِ غیرقابل‌اتصال دارند) |
| Benchmark B0/B1 | **PASS با هشِ یکسان؛ هیچ بهبودِ سرعتی ادعا نمی‌شود** |
| Build | **PARTIAL** (Go/فرانت/بسته سبز؛ پوستهٔ Tauri ساخته نشد: `cargo` نیست) |
| Installer: نصبِ تمیز / ارتقا / Uninstall | **PASS — واقعاً اجرا شد** (۸ فایل‌شماری، هشِ `user.db`، رجیستری) |
| Repair (تعاملی) | **NOT_MEASURED** (فقط در نصبِ تعاملی فعال است) |
| Auto-Update / Rollback | **NOT_MEASURED** (نیازمندِ artifactِ امضاشده و شبکه) |
| CI | **۳ جابِ تازه؛ اجرا نشد — NOT_RUN** |
| main / tag / release | **دست‌نخورده** |

## ۲. فایل‌هایِ تغییرکرده

| فایل | تغییر |
| --- | --- |
| `candle_contract.py` | `SRC_LEGACY='legacy-unknown'` با رتبهٔ صفر؛ `from_db_row` دیگر `published` نمی‌گوید |
| `test_tsetmc.py` | `dp_insert_sql(conn)` (UPSERTِ محافظت‌شده) در هر سه مسیر؛ `_upsert` صاحبِ `keep_if_zero`/`session_col`/`row_guard` شد و `market_watch` هم گارد گرفت |
| `backend-go/internal/chart/canonical.go` | همان قراردادِ provenance در مسیرِ Go |
| `dev/test_phase47_ingestion_v1.py` | گاردها با کنترلِ منفی (provenance، `daily_prices`، `market_watch`، idempotency) |
| `dev/run_all_tests.py` | ثبتِ همان گارد در مجموعهٔ گیت |
| `tools/phase47/{probe_ingestion,backfill_phase47,bench_pipeline}.py` | سنجش، backfillِ idempotent، بنچمارکِ B0/B1 با هش |
| `.github/workflows/guards.yml` | `go-windows` (ماتریس)، `delivery-contract`، `data-integrity` |
| `docs/opportunity-center/phase47/*.md` | همین گزارش‌ها |

## ۳. معماریِ ingestion — پیش و پس

**پیش:** یک مسیرِ نوشتن با سه ضعفِ هم‌زمان — `daily_prices` با
`INSERT OR REPLACE`؛ `src` تهی که «published» ترجمه می‌شد؛ و `_upsert`ِ
`market_watch` که هر ستونِ غیرِ sticky را با `excluded.c` می‌نوشت (NULL/۰ جای
مقدارِ موجود).

**پس:** همان مسیرِ واحد با سه تضمین: مالکیتِ صریحِ سطر (`src` با رتبهٔ ۰/۱/۲)،
محافظِ کامل‌بودنِ snapshot در `daily_prices` **و** `market_watch` (با گاردِ
هم‌نشست)، و provenance صادقانه (`legacy-unknown` به‌جایِ ادعایِ منبع).
جزئیات در `INGESTION.md`.

## ۴. علتِ ریشه‌ای و اصلاح

| مشکل | علتِ اثبات‌شده | اصلاح | قبل → بعد |
| --- | --- | --- | --- |
| ۳۶۹٬۳۵۹ ردیفِ بدونِ `src` | ستون بعد از نوشته‌شدنِ ردیف‌ها اضافه شد | برچسبِ `legacy-unknown` + اصلاحِ payload | ۳۶۹٬۳۵۹ → ۰ |
| `last` تهی | غیبتِ واقعی در منبع/ردیف‌هایِ قدیمی | هیچ مقداری ساخته نشد؛ `null` صادقانه | ۴۲۰٬۶۷۵ → ۴۲۰٬۶۷۵ |
| `low` = قیمتِ حراج | **قاعدهٔ frozenِ `widen`**، نه نقصِ تجمیع | دست‌نخورده + مستندسازیِ اختلافِ تعریف | ۵۱۶ → ۵۱۶ |
| ۹٬۴۳۶ کندلِ `board` ناهم‌خوان با تابلو | `INSERT OR REPLACE` + پاسخِ لاغرِ TSETMC | UPSERTِ محافظت‌شده | ۹٬۴۳۶ → ۹۰۹ (حجم: ۸٬۵۶۴ → ۰) |
| حجمِ صفر (۲٬۶۹۲) | روزِ بی‌معامله | دست‌نخورده | ۲٬۶۹۲ → ۲٬۶۹۲ |
| **`market_watch` صفرشده** | `_upsert` مقدارِ غایب را با NULL/۰ جای مقدارِ موجود می‌نوشت | keep-if-zero فقط در همان نشست + گاردِ ردیف | ۱۶ ردیفِ `price_first` تهی و ۱٬۳۷۷ ردیفِ بی‌حجمِ معامله‌شده شناسایی شد؛ رفتارِ آینده بسته شد |

**دو تصحیحِ گزارشِ فاز ۴٫۵:**

1. «حراج در `low` جمع شده» به‌عنوانِ **نقص** درست نیست؛ رفتارِ عمدیِ
   `candle_contract.widen` است. تفاوت با مرجع، اختلافِ **دامنهٔ تعریف** است.
2. «ردیف‌هایِ `board` جابه‌جا شده‌اند» دقیق‌تر: ردیف با پاسخِ لاغر **صفر** می‌شد و
   کندلِ ساخته‌شده از نسخهٔ کاملِ قبلی مانده بود — **بازنویسیِ ناقص**، نه جابه‌جاییِ تاریخ.

## ۵. ۳۰ نماد (فهرستِ فاز ۴٫۵، بی‌تغییر)

| محور | قبل | بعد |
| --- | --- | --- |
| نمادِ حاضر | ۳۰/۳۰ | ۳۰/۳۰ |
| کندل | ۱۱٬۵۳۳ | ۱۲٬۰۸۶ |
| تاریخِ تکراری | ۰ | ۰ |
| ردیفِ بدونِ `src` | بخشِ بزرگ | ۰ |
| حجمِ صفر (بی‌معامله) | ۹۲/۶۹/… | همان |
| تطبیق با مرجع | FAIL (فاز ۴٫۵) | **BLOCKED** (پایین) |

### چرا «BLOCKED» و نه «اندازه‌گیری شد»

برداشتِ مرجعی که فاز ۴٫۵ رویِ آن سنجیده بود (`capture2.json`،
`sha256=b27564da…0ddba6`، ۱۸۰ سری، ۲۱۸٬۶۸۸ ردیف) در این درخت نیست و
`_audit/phase45/parity/raw-compare.json` هم موجود نیست. جست‌وجو شد و تنها
شبکهٔ مرجعِ آرشیوی موجود، `_audit/RA365-PARITY-DIVERGE-2026-10-12.csv` است:
۳۰٬۹۱۲ ردیف، **۲۹ نماد** که فقط **۱۱**تای‌شان با فهرستِ ۳۰ نمادِ فاز ۴٫۵
هم‌پوشانی دارند (خودرو، سرود، شستا، شپنا، فارس، فزر، فنوال، فولاد، وبملت،
ولانا، ومعادن). آن فایل هم در «آرم‌هایِ هفتگیِ تعدیل‌شده» (R0/R1) است و بدونِ
زنجیرهٔ تعدیل و همان برداشت، به کندلِ خامِ روزانه وصل نمی‌شود. پس عددِ پاریتی
تولید نشد؛ عددِ «هم‌پوشانی و علتِ نبودِ اتصال» تولید شد.

**چی باز می‌کند:** همان `capture2.json` (یا اجازهٔ اجرای
`tools/phase45/rahavard/capture_rahavard.mjs` با شبکه). بعد از آن،
`tools/phase45/compare_raw.py` بدونِ تغییر اجرا می‌شود.

## ۶. کندلِ خام و تعدیل‌شده

خام: پوشش/تکرار/provenance اندازه‌گیری و اصلاح شد (بالا). تعدیل‌شده:
**NOT_MEASURED** در این دور — موتورِ تعدیل تغییر نکرد؛ ادعاهایِ فاز ۴٫۵
(۳۰/۳۰ داخلِ تلورانسِ ۰٫۱٪، ۲۹/۳۰ دقیق، Python↔Go صفر اختلاف، B3 50/50)
«گزارش‌شده» می‌مانند، نه بازآزماییِ این دور.

## ۷. Benchmark

| سنجه | B0 | B1 |
| --- | ---: | ---: |
| هر نماد p50 (ms) | 2.949 | 3.169 |
| هر نماد p95 (ms) | 4.770 | 4.542 |
| کلِ ۳۰ نماد (ms) | 84.9 / 94.9 | 94.9 / 100.3 |
| کندل | 11,181 | 11,181 |
| هشِ خروجی | `37f12ffe…a9ee318` | `37f12ffe…a9ee318` |

**حکم:** برابریِ عددیِ خروجی اثبات شد (شرطِ پذیرشِ §۸). تفاوتِ زمان در حدِ نویز؛
نه بهبود و نه رگرسیون. B2 اعمال نشد (`PERF.md` §۴).

## ۸. Build

`GOOS=windows go build ./cmd/borsd` → ۲۱٬۷۲۳٬۱۳۶ بایت؛ بستهٔ مونتاژشده
(۷۵ فایل: exe + `frontend/dist` + پکِ تقویم + بستهٔ تصحیح + `apply_update.bat`)؛
`bundlecheck` = exit 0 («no python/uvicorn/fastapi artifacts»). لنگرهایِ نسخه:
۱٫۰٫۹۵ در ۱۱ جایِ محصول (11 checks / 0 failed).

**PARTIAL:** `cargo`/`rustc` رویِ این ماشین نیست، پس `scripts/build_shell.py`
(پوستهٔ Tauri) اجرا نشد. نصاب `BorsTerminal_Shell.exe` را در `[Files]` الزام
نمی‌کند، بنابراین تستِ نصب با بستهٔ بدونِ پوسته کامل شد.

## ۹. Installer — اجرایِ واقعی (دورِ دوم)

| سناریو | نتیجه | شاهد |
| --- | --- | --- |
| نصبِ تمیز | **PASS** | rc=0؛ ۷۸ فایل؛ EXE/`apply_update.bat`/`frontend/index.html`/پکِ تقویم/بستهٔ تصحیح موجود؛ `DisplayVersion=1.0.95-test` |
| ارتقا (1.0.95 → 1.0.96) | **PASS** | rc=0؛ `sha256(user.db)` و `sha256(fts_thresholds.json)` پیش/پس یکی؛ `_internal\stale.pyd` پاک شد؛ `logs` ماند |
| Uninstall | **PASS** | rc=0؛ `market.db`, `market.db.lzma`, `logs`, `_internal` پاک؛ `user.db` و `fts_thresholds.json` ماند؛ کلیدِ رجیستری حذف |
| Repair (تعاملی) | **NOT_MEASURED** | `WizardSilent()` ⇒ صفحهٔ نگه‌داری ساخته نمی‌شود |

شاهدِ خام: `_audit/phase47/installer-evidence.json` (شاملِ هشِ دو نصابِ ساخته‌شده).

**افشا:** این اجرا با نسخهٔ سندباکس‌شدهٔ همان سند انجام شد، چون اجرایِ عیناً
خط‌به‌خط سه اثرِ مخرب داشت: بازنویسیِ ثبتِ نصبِ موجودِ کاربر (همان `AppId`)،
پاک‌شدنِ `{localappdata}\BorsTerminal_Ultimate\data\market.db`ِ واقعی، و بالا آمدنِ
بک‌اند رویِ پورتِ نصبِ موجود (چون `[Run]` با `nowait postinstall` در حالتِ سایلنت
اجرا می‌شود). سه جایگزینی: `AppId`/`AppRegID` ← GUIDِ تست، خطِ `[Run]` ← غیرفعال،
`{localappdata}\…\data` ← `{app}\_la_sandbox` (فایل کاشته و همان‌جا حذف شد).
`[Files]`, `[InstallDelete]`, `[UninstallDelete]`, `[Icons]`, `[Code]`, رمزنگاری و
رمزِ نصب دست‌نخورده بود. سندِ تست و هر دو نصابِ ساخته‌شده پس از ثبتِ هش حذف شدند.

## ۱۰. Auto-Update و Recovery

مسیرِ کد تأیید شد: `latest.json` → امضایِ minisign (`_verify_file`) → نصبِ سایلنت؛
و برایِ داده: manifest+`.sig` → `VerifyAsset` → `sha256` → staging → نسلِ تازه →
`reloadHook`. آزمون‌هایِ واقعیِ قطعِ اینترنت، فایلِ خراب، امضایِ نامعتبر،
بسته‌شدنِ برنامه، و Rollback: **NOT_MEASURED** — نیازمندِ artifactِ امضاشده و شبکه؛
در این نشست هیچ ریلیزی ساخته/استفاده نشد.

## ۱۱. CI

سه جابِ تازه در `guards.yml` (YAML پارس شد؛ ۹ جاب): `go-windows` (ماتریسِ
`windows-2022`/`windows-latest`), `delivery-contract` (ساخت + مونتاژ + `bundlecheck`
+ مانیفستِ `sha256` + artifact), `data-integrity` (گاردهایِ ingestion/candle/repair).

**نتیجهٔ اجرا: NOT_RUN.** منطقِ جابِ `delivery-contract` محلی بازتولید شد
(همان دستورها: ساختِ EXE، مونتاژ، `bundlecheck` = exit 0)، ولی «سبز شدن در runner»
ادعا نمی‌شود.

## ۱۲. تست‌هایِ عملیاتی و شواهد

| مجموعه | نتیجه |
| --- | --- |
| `dev/test_phase47_ingestion_v1.py` | ۳۱ passed / ۰ failed (شاملِ ۱۰ گاردِ `market_watch`) |
| `dev/candle_contract_v1071.py` | ۲۲ passed / ۰ failed |
| `dev/test_round18_history_repair_v1.py` | ۱۴ passed / ۰ failed |
| `dev/test_history_gap_repair_v1.py` | ۱۴ سبز / ۰ قرمز |
| `dev/version_anchor_guard.py` | 11 checks / ۰ failed |
| `dev/persian_glyph_guard.py` | ۴ passed / ۰ failed |
| `go build ./...` + `go test ./internal/chart ./internal/candle` | سبز |
| `bundlecheck` رویِ بستهٔ مونتاژشده | exit 0 |
| نصب/ارتقا/Uninstall ویندوز | **اجرا شد (PASS)** — `_audit/phase47/installer-evidence.json` |
| شاهدِ تصویری | **N/A** — هیچ تغییرِ رابط در این دور نبود |

## ۱۳. مشکلاتِ حل‌نشده

| # | مورد | وضعیت | علت |
| --- | --- | --- | --- |
| ۱ | ۹۰۹ کندلِ `board` با `price_first=0` | رفتارِ قرارداد | `widen` آن را از `close` پر می‌کند؛ تغییرش خروجی را عوض می‌کند |
| ۲ | ۱۶ + ۱٬۳۷۷ ردیفِ تاریخیِ `market_watch` | بازسازی‌ناپذیر | جدول عکسِ لحظه‌ای است؛ گارد فقط رفتارِ آینده را می‌بندد |
| ۳ | تطبیقِ مرجعِ ۳۰ نماد | BLOCKED | `capture2.json` در درخت نیست؛ آرشیو فقط ۱۱ نمادِ غیرقابل‌اتصال |
| ۴ | پوششِ ۲۰۱۰–۲۰۲۴ | باز | نیازمندِ `--backfill-history` با مجوز |
| ۵ | Repairِ تعاملی | NOT_MEASURED | فقط در نصبِ تعاملی فعال است |
| ۶ | Update/Rollback/قطعِ شبکه | NOT_MEASURED | نیازمندِ ریلیزِ امضاشده |
| ۷ | پوستهٔ Tauri | NOT_RUN | `cargo`/`rustc` نصب نیست |
| ۸ | CI | NOT_RUN | push/اکشن اجرا نشد |
| ۹ | ingestion هنوز Pythonی است | بدهیِ معماری | بستهٔ کلاینت Go است، ولی تولیدِ داده Python |

## ۱۴. وضعیتِ شاخه، main، Tag، Release، Worktree

- **شاخهٔ مأموریت:** `mission/phase47-data-pipeline-desktop-delivery-2026-11` رویِ
  `7d2335de`، سه کامیت رویِ آن.
- **main:** دست‌نخورده — هیچ merge/commit رویِ `main`.
- **Tag/Release:** هیچ تگ و هیچ ریلیزی ساخته نشد.
- **Worktreeها:** ۱۰ worktree بررسی شد؛ ۸ تمیز، `_bors-sarkhati-minfix` با ۱۵ فایلِ
  untracked (دست‌نخورده)، و این worktree. تغییرِ هیچ worktree دیگری خوانده/نوشته نشد.
- **دیتابیسِ عملیاتی:** بازسازی/جایگزین/نوشتن نشد. همهٔ محاسبات رویِ کپیِ
  `_audit/phase47/lab/market.db` (gitignored) و یک نصبِ موقت در `_audit/phase47/install/`.

## ۱۵. پایبندی به تصمیم‌هایِ ثابتِ مالک

`approval_enabled=false` و مسیرهایِ Approved/Stable دست‌نخورده؛ FTS و
`/fts-screen` و رتبه‌بندیِ لکسوگرافیک تغییر نکردند؛ هیچ اندیکاتورِ فاز ۵ ساخته نشد؛
هیچ قابلیت/انیمیشنِ رابط حذف نشد؛ معماریِ Tauri v2 + Go حفظ شد؛ دادهٔ خام و شواهدِ
مرجع منتشر نشد (فقط شمارش و هش منتشر شد).

## شرطِ ورود به فاز ۵

از سه گیت، **Desktop Delivery** حالا شاهدِ واقعیِ نصب/ارتقا/حذف دارد (PASS) ولی
Repair و Update/Rollback هنوز `NOT_MEASURED`اند، **CI** اجرا نشده، و **Data
Integrity** در محورِ «تطبیقِ مرجع» با نبودِ `capture2.json` مسدود است. بنابراین فاز ۵
**آغاز نمی‌شود** تا این سه شاهد تکمیل یا صریحاً توسطِ مالک پذیرفته شوند.
