# طراحی Phase 4.9.1 — تأیید کامل داده، بستن شواهد تعدیل و مهاجرت CI پایتون

- تاریخ: 2026-11-10
- وضعیت: تأییدشده در گفتگو؛ در انتظار بازبینی نهایی سند توسط مالک
- شاخهٔ مأموریت: `mission/phase49-full-verification-python-ci-2026-11-10`
- مبنای شاخه: `f7fc8e8a771e44b24687921851ccb8f61fda2ee3`
- `main`: `9a919e82` — باید بدون تغییر بماند
- شاخهٔ قبلی: `mission/phase49-data-finalization-2026-11-10` و `mission/phase49-adjustment-chain-closure-2026-11-10` — باید حفظ شوند
- مرجع مأموریت: متن Phase 4.9.1 (Full Historical Data Verification, Adjustment Evidence Closure & Python CI Decommission/Migration)
- حکم نهایی: بر اساس معیارهای بند ۱۵؛ از پیش تعیین نمی‌شود.

---

## ۱) زمینه و وضعیت مبنا (اندازه‌گیری‌شده در 2026-11-10)

| مورد | مقدار / وضعیت |
| --- | --- |
| HEAD مبنا | `f7fc8e8a` — مطابق متن مأموریت |
| شاخهٔ کاری | `mission/phase49-full-verification-python-ci-2026-11-10` (جدید از `f7fc8e8a`) |
| CI فعلی | ۹ job YAML (۱۰ runner با matrix ویندوز)؛ `python-guards` با ۲۵۴ سوئیت Python + ۲ سوئیت JS و ۲۴ سوئیت قرمزِ شناخته‌شده |
| پوشش Go | ۷۵۱ تابع تست در ۱۳۷ فایل `_test.go` |
| پوشش frontend-v2 | ۴۲۵ مورد Vitest در ۵۲ فایل تست |
| پک تعدیل فعلی | `ra365-phase49-rebuild-full-v2`؛ ۸٬۲۸۰ گام، ۹۵۱ نماد، ۶۲۲ verified، ۶٬۳۰۰ reconstructed_verified، ۱٬۳۵۸ unverified، ۲۸ invalid |
| نمادهای دارای گام unverified | ۷۸۲ نماد |
| `as_of` پک | `2026-10-25` |
| Seed قبلی | ۵۱۱٬۱۳۹ ردیف `price_history`، ۶٬۱۰۳ نماد، ۶٬۱۰۳ ردیف `history_validity` |
| وضعیت اعتبار Seed قبلی | ۳۵ verified، ۸۸۰ reconstructed_verified، ۵٬۱۸۸ unverified |
| SHA-256 DB قبلی | `2ee662980ef0dcebbb06b0679f3c0e54282984a060f3b9da62e02f0b389deffc` |
| SHA-256 LZMA قبلی | `46ff29830b99626c22dff43601c1e6b203ab0340e67727e41992732d14a6e35c` |
| SHA-256 gzip قبلی | `41e90ffc2431100931bd35b99b9221eaf964cda250d5fa07e066ab374cb2e4ad` |
| `adjust_events` | ۱۲٬۸۲۹ رویداد در ۱٬۰۸۷ نماد؛ همه با منبع `base-price-discontinuity` (استنباطی، نه رسمی) |
| `price_adjust_events` | ۱٬۰۰۱ ردیف (TSETMC flow) |
| `share_change_events` | ۳٬۴۸۳ ردیف (TSETMC flow) |
| `codal_notices` | ۳۶٬۳۵۰ اطلاعیه در ۱٬۸۰۰ نماد |
| capture مرجع موجود | `capture-30.json` (۱۸۰ سری) + `capture-7.json` (۴۲ سری)؛ ۲۶۶٬۴۰۸ ردیف؛ پنجرهٔ 2010-01-01 تا 2026-11-10 |
| نمادهای مرجع | ۳۶ نماد یکتا طبق گزارش Phase 4.9 (۳۰ + ۷) |
| `instruments` | ۵٬۹۴۴ ردیف در Seed؛ ستون `symbol` ندارد (کلید `ins_code`)؛ گزارش Phase 4.9 عدد ۵٬۹۴۱ را ثبت کرده — نیازمند reconciliation |
| release فعلی | job `release-inno` با `scripts/build_all.py` (Go + frontend-v2 + Tauri shell)؛ توضیحات قدیمی PyInstaller باید اصلاح/اثبات شود |
| محیط محلی | gcc/CGO محلی نیست ⇒ race detector فقط در CI؛ Python پروژه در venv محلی؛ Node باندل‌شده روی PATH نیست |

### نقص شناخته‌شدهٔ مبنا

`history_validity` فعلی برای هر ۵٬۱۸۸ ردیف `unverified` مقدار `factor_steps=0` دارد، در حالی که ۷۸۲ نمادِ همان مجموعه در پک گام `unverified` دارند. مجموع `factor_steps` جدول ۷٬۷۳۰ است، ولی پک ۸٬۲۸۰ گام دارد. بنابراین **شمارش و وضعیت از پک بازتولید می‌شود، نه از این جدول**؛ جدول فقط پس از materialize شدن Ledgerهای این مأموریت معتبر است.

---

## ۲) هدف و غیرهدف

### هدف

1. بررسی گام‌به‌گام ۱٬۳۵۸ گام `unverified` با شواهد مستقل و ثبت نتیجهٔ هر گام.
2. ممیزی روش و provenance همهٔ ۶٬۳۰۰ گام `reconstructed_verified`.
3. تعیین تکلیف سه گام ولانا بدون تغییر آستانه.
4. تعیین تکلیف نمادبه‌نماد ۶٬۱۰۳ نماد دارای تاریخچه، ۵٬۱۸۸ ردیف `unverified` و reconciliation عدد ۶٬۳۲۸ گزارش‌شده.
5. Backfill شش نماد کوتاه‌تاریخ تا بیشترین تاریخچهٔ مرجع و رفع کهنگی نمادهای فعالِ capture‌شده.
6. تعیین تکلیف ۲۵۴ سوئیت Python و ۲۴ شکست، جداسازی گیت Production از Data-Tooling و Legacy.
7. اثبات zero-Python بودن runtime با شاهد bundle، فرایند و نصاب.
8. ساخت Seed Candidate جدید با provenance کامل، idempotency، integrity و پاریتی Go/Python؛ بدون انتشار.
9. تولید هشت تحویل‌شدنی الزامی و شواهد CI واقعی روی HEAD نهایی.

### غیرهدف

- Phase 4.10، Opportunity Lab، Technical Intelligence، Kronos، AutoTrader، معاملات واقعی.
- Merge به `main`، Tag، Release، تغییر Visibility، Force Push.
- تغییر قواعد canonical FTS، آستانه‌ها برای سبزکردن تست، یا Expected Output بدون ممیزی.
- بازطراحی فرانت‌اند یا تغییر رفتار محصول خارج از دامنهٔ داده/CI.
- نصب واقعی روی ماشین کاربر یا لمس Registry واقعی.
- انتشار عمومی دادهٔ خام مرجع.

---

## ۳) تصمیم‌های مالک (تأییدشده در گفتگو)

| # | موضوع | تصمیم |
| --- | --- | --- |
| D1 | دامنهٔ capture مرجع | union سه مجموعه: ۷۸۲ نماد دارای گام unverified + همهٔ نمادهای ≥۱ سال سابقه + ۶ نماد کوتاه‌تاریخ؛ type0/type7 روزانه؛ برآورد ~۱٬۱۰۰ نماد؛ عدد دقیق در stage 1 |
| D2 | سیاست CI پایتون | نقشهٔ پوشش ماشین‌خوان + پورت هدفمند؛ `python-guards` از گیت Production حذف؛ Data-Tooling اجباری جدا؛ Legacy غیرمسدودکننده |
| D3 | شاهد «نبودِ رویداد» | لایه‌ای با مرز پوشش؛ فقط با اثبات پوشش کامل بازهٔ فعال توسط منبع رسمی یا capture مرجع؛ وگرنه `INSUFFICIENT_EVIDENCE` |
| D4 | محل backfill مرجع | Seed Candidate جدید با `src` و provenance کامل + گیت انتشار تا تأیید مالک دربارهٔ مجوز بازتوزیع |
| D5 | دامنهٔ backfill | ۶ نماد کوتاه‌تاریخ: کل تاریخچهٔ مرجع؛ سایر نمادهای فعالِ capture‌شده: فقط نشست‌های اخیر جاافتاده (freshness) پس از اعتبارسنجی price basis |

---

## ۴) اصول حاکم

1. **شاهد مقدم بر برچسب است.** هیچ گامی/نمادی فقط با تغییر Label از unverified به verified بسته نمی‌شود.
2. **هیچ داده‌ای ساخته نمی‌شود.** نبود داده ⇒ «بدون داده» یا `BLOCKED_SOURCE`/`INSUFFICIENT_EVIDENCE`.
3. **هیچ آستانه‌ای تغییر نمی‌کند.** تلورانس‌های موجود Phase 4.9 حفظ و از یک منبع واحد خوانده می‌شوند.
4. **هیچ Assert تضعیف یا Skip/ignore نمی‌شود.** Golden فقط با بازتولید oracle و diff مستند به‌روز می‌شود.
5. **همه‌چیز idempotent و بازتولیدپذیر است.** هر stage manifest با SHA ورودی/خروجی و شمارش می‌نویسد.
6. **Python فقط Data-Engineering/Research/Build Tooling است.** Production با Tauri v2 + Go + SQLite اجرا می‌شود و به Python وابسته نیست.
7. **`main`، شاخه‌های قبلی و DB عملیاتی دست‌نخورده می‌مانند.** همهٔ تغییرها روی کپی‌های ایزوله.
8. **دادهٔ خام مرجع در Git نمی‌رود.** فقط SHA، منبع، تاریخ، تعداد رکورد، نوع سری و روش نرمال‌سازی ثبت می‌شود.
9. **Credential/Cookie/Token/Private Key هرگز خوانده یا ذخیره نمی‌شود.** نشست در مرورگر خود مالک می‌ماند.

---

## ۵) معماری، چیدمان و خط لوله

### ۵.۱ شاخه و ایزولاسیون

- شاخهٔ مأموریت از `f7fc8e8a` ساخته می‌شود؛ فقط commit/push روی همین شاخه.
- کارهای سنگین در `_audit/phase49-full-verification/`؛ پیش از شروع، `_audit/.gitignore` با الگوهای صریح تکمیل می‌شود تا این مسیرها هرگز track نشوند:
  ```
  /phase49-full-verification/captures/
  /phase49-full-verification/db/
  /phase49-full-verification/seed/
  /phase49-full-verification/logs/
  /phase49-full-verification/ledgers/
  ```
  (`*.db` موجود نیز seed/db را پوشش می‌دهد؛ الگوی صریح برای جلوگیری از اشتباه است.)
  - `captures/` — capture خام مرجع
  - `db/` — کپی‌های کاری DB
  - `seed/` — Seed Candidate جدید
  - `ledgers/` — CSV/JSON میانی
  - `logs/`
- اسکریپت‌های stage و `evidence/*.json` خلاصه در Git می‌مانند؛ `evidence/` نباید هیچ سری خام مرجع داشته باشد.
- مسیر فایل‌های متنی و کد در Git:
  - `dev/suite_registry.json` — رجیستری ۲۵۴ سوئیت
  - `dev/phase49_status_rules.json` — قواعد وضعیت و تلورانس‌ها
  - `dev/phase49_rules_guard.py` — اعتبارسنجی قواعد در برابر کد موجود
  - `dev/suite_registry_guard.py` — اعتبارسنجی رجیستری
  - `backend-go/cmd/runtimecheck/` — اثبات zero-Python runtime
  - `scripts/check_seed_release.py` — گیت انتشار Seed
  - `docs/opportunity-center/phase49/` — هشت تحویل‌شدنی
  - `docs/superpowers/specs/2026-11-10-phase49-full-verification-design.md` — همین سند

### ۵.۲ Stageهای خط لوله

همهٔ اسکریپت‌ها در `_audit/phase49-full-verification/` هستند (کد ابزار، نه Production). هر stage یک `*.manifest.json` با `inputs_sha256`، `outputs_sha256`، `row_counts`، `command`، `started_at`، `finished_at` می‌نویسد.

| Stage | مسئولیت | ورودی | خروجی | وابستگی |
| --- | --- | --- | --- | --- |
| `stage00_baseline.py` | snapshot مبنا: HEAD، SHA پک/DB/capture، شمارش‌ها، نسخهٔ ابزارها | repo + DB + pack + captures | `evidence/baseline.json` | — |
| `stage01_capture_plan.py` | ساخت فهرست capture (D1)، dedupe، نقشهٔ هویت symbol/ins_code/asset_id، شمارش دقیق | pack + DB + `make_symbols.py` | `symbols.json` + `evidence/capture-plan.json` | 00 |
| `stage02_import_reference.py` | نرمال‌سازی captureها، اعتبارسنجی SHA/تعداد، ساخت ایندکس پاریتی factor | captureها | `reference-index.json` + metadata | 01 |
| `stage03_step_ledger.py` | طبقه‌بندی ۸٬۲۸۰ گام با شواهد O1/O2/R1/R2/I1 | pack + DB + reference + official tables | `ledgers/steps.csv` → `ADJUSTMENT-EVIDENCE-LEDGER.csv` | 02 |
| `stage04_volana_rootcause.py` | استخراج و ریشه‌یابی سه گام ولانا | steps + reference | `evidence/volana.json` | 03 |
| `stage05_symbol_ledger.py` | Ledger نمادبه‌نماد ۶٬۱۰۳ ردیف: هویت، پوشش، وضعیت، freshness، gap، anomaly | DB + events + reference + steps | `HISTORY-COVERAGE-LEDGER.csv` | 03 |
| `stage06_anomaly_ledger.py` | طبقه‌بندی anomalyهای OHLC/گپ؛ برنامهٔ اصلاح فقط با شاهد | DB + reference | `ledgers/anomalies.csv` + اصلاح‌های تأییدشده | 02 |
| `stage07_inventory_reconcile.py` | reconciliation شمارش‌ها و کلیدها (۶٬۱۰۳/۵٬۹۴۴/۱٬۳۰۶/۱٬۴۶۸/۱٬۳۴۳) | DB + instruments + history | `evidence/inventory-reconcile.json` | 05 |
| `stage08_backfill.py` | برنامه و اعمال backfill (D5) روی کپی کاندید، با provenance و idempotency | reference + DB | کپی کاندید + `backfill_runs` | 02, 05 |
| `stage09_seed_build.py` | materialize اعتبار، manifest، SHA/LZMA/gzip، integrity | کپی کاندید + ledgers | Seed Candidate جدید | 08 |
| `stage10_parity.py` | پاریتی Go/Python و MA/Weekly/Monthly/chart-db | pack + seed | `evidence/parity.json` | 09 |
| `stage11_deliverables.py` | مونتاژ هشت تحویل‌شدنی، SHA همهٔ مصنوعات | همهٔ بالا | docs + `ARTIFACTS-SHA256-full-verification.txt` | 00..10 |

### ۵.۳ قواعد ثابت خط لوله

- منبع حقیقت گام‌ها `factors.jsonl` پک است؛ `history_validity` فعلی فقط ورودی مقایسه است.
- هیچ stage روی `market.db` ریشه یا `_audit/phase49-finalization/seed/market.db` نمی‌نویسد.
- capture خام فقط در `captures/` می‌ماند؛ stage 11 فقط metadata/SHA را منتشر می‌کند.
- تلورانس‌ها و نقشهٔ وضعیت فقط از `dev/phase49_status_rules.json` خوانده می‌شوند. `dev/phase49_rules_guard.py` مقادیر را با کد موجود (`stageC_reference_parity.py`، `adjustment_corrections.py`) مقایسه می‌کند و در صورت ناهم‌خوانی FAIL می‌دهد.
- هیچ عدد سرگردان در گزارش نهایی نیست: هر عدد به `evidence/*.json` با SHA ارجاع می‌دهد.

---

## ۶) Capture مرجع

### ۶.۱ دامنه

فهرست capture از union این مجموعه‌ها ساخته می‌شود و با `symbol` + `asset_id` dedupe می‌شود:

1. هر نمادی که در پک حداقل یک گام `unverified` دارد (۷۸۲ نماد).
2. هر نمادی که حداقل یک سال سابقهٔ تاریخچه دارد.
3. شش نماد کوتاه‌تاریخ: شنفت، فافق، فخاس، فولاژ، لخزر، مارون.
4. هر نمادی که stage 5/6 برای تعیین تکلیف anomaly یا coverage به آن نیاز دارد.

عدد دقیق union در `evidence/capture-plan.json` ثبت می‌شود؛ هیچ عدد دستی در گزارش نوشته نمی‌شود.

### ۶.۲ روش

- ابزار: `tools/phase45/rahavard/capture_rahavard.mjs` با `--types type0,type7 --res D --countback 100000 --from 1990-01-01 --to 2026-11-10 --delay-ms 400 --retries 3`.
- نشست: مرورگر لاگین‌شدهٔ مالک؛ attach یا launch. اگر کد ۳ برگشت (نشست منقضی)، اجرا متوقف می‌شود و مالک دستی وارد می‌شود؛ هیچ Credential/OTP درخواست یا ذخیره نمی‌شود.
- کد ۴ (مرورگر قابل attach نیست): توقف و گزارش دقیق.
- خطاهای جزئی هر نماد در `capture-failures.json` ثبت و در اجرای بعدی فقط همان‌ها resume می‌شوند.
- Computer Use فقط برای بازکردن/بررسی صفحه و عبور از بنر یا مودال غیرحساس؛ خود capture با اسکریپت انجام می‌شود. ورود، OTP و دیالوگ‌های امنیتی هرگز خودکار نمی‌شوند.

### ۶.۳ Import و metadata

`import_capture.py` سری‌ها را نرمال می‌کند. برای هر capture ثبت می‌شود:

- SHA-256 فایل خام
- منبع (`rahavard365 type0/type7`)
- `captured_at`
- تعداد سری و ردیف
- نوع سری (raw/adjusted) و resolution
- روش نرمال‌سازی
- مسیر محلی ignoreشده (در Git نمی‌آید)

### ۶.۴ اعتبار پوشش

برای هر نماد، `R1` فقط وقتی شاهد «نبودِ رویداد» است که سری type0/type7 از نخستین تاریخ فعال نماد شروع شود و تا آخرین تاریخ موجود ادامه داشته باشد. سری ناقص ⇒ `INSUFFICIENT_EVIDENCE` در سطح نماد.

---

## ۷) Ledger گام‌ها

### ۷.۱ فیلدها

هر ردیف (۸٬۲۸۰ گام معتبر + ۲۸ ردیف invalid) شامل:

`symbol, ins_code, asset_id, effective_date, action, ratio, prod_ratio, ref_ratio, cum_factor_after, provenance, method, evidence_tier, evidence_ref, comparison_result, discrepancy_cause, final_status, risk_score, notes`

### ۷.۲ لایه‌های شاهد

| لایه | منبع | کاربرد |
| --- | --- | --- |
| `O1` | `price_adjust_events` / `share_change_events` | شاهد مثبت رسمی وجود/نسبت/تاریخ |
| `O2` | `codal_notices` | تقویت وجود/تاریخ؛ نسبت فقط با استخراج و تأیید متقابل |
| `R1` | ره‌آورد type0/type7 | پاریتی زنجیرهٔ factor و شاهد بود/نبودِ رویداد |
| `R2` | منبع ثانویه | فقط مقایسه/تکمیل |
| `I1` | بازسازی داخلی | فقط پس از ممیزی؛ غیرمستقل |

**قاعدهٔ مرز پوشش:** نبودِ ردیف در `O1/O2` فقط با سند کامل بودن ingest برای همان نماد و بازه، شاهد «نبودِ رویداد» است. در غیر این صورت این جدول‌ها فقط شاهد مثبت‌اند.

### ۷.۳ تلورانس‌ها (موجود، بدون تغییر)

| ثابت | مقدار | منبع |
| --- | --- | --- |
| `EXACT_EQ` | `1e-9` | `stageC_reference_parity.py` |
| `FACTOR_EXACT` | `1e-3` (۰٫۱٪) | `stageC_reference_parity.py` |
| `FACTOR_MATERIAL` | `1e-2` (۱٪) | `stageC_reference_parity.py` |
| `OHLC_MATERIAL` | `5e-2` (۵٪) | `stageC_reference_parity.py` |
| `DEDUPE_RATIO_TOL` | `1e-2` | `adjustment_corrections.NEAR_DEDUPE_RATIO_TOL` |
| step date shift | ۱–۳ و ۴–۵ روز | `stageC_reference_parity.py` |

`dev/phase49_status_rules.json` این مقادیر را آینه می‌کند و `dev/phase49_rules_guard.py` برابری را تضمین می‌کند. تغییر هر مقدار در این مأموریت ممنوع است.

### ۷.۴ وضعیت گام و قواعد

| وضعیت | شرط |
| --- | --- |
| `VERIFIED_MULTI_SOURCE` | `O1` و `R1` هر دو منطبق |
| `VERIFIED_OFFICIAL` | `O1` منطبق (تاریخ + نسبت)؛ `O2` تقویتی |
| `VERIFIED_REFERENCE` | زنجیرهٔ factor با `R1` در `FACTOR_EXACT` منطبق |
| `PARTIAL_REFERENCE` | اختلاف factor با `R1` بین `FACTOR_EXACT` و `FACTOR_MATERIAL`؛ نه تأیید کامل، نه تعارض |
| `PARTIAL_OFFICIAL` | نسبت رسمی `O1` بین `FACTOR_EXACT` و `FACTOR_MATERIAL` با تاریخ منطبق |
| `RECONSTRUCTED_AUDITED` | بدون شاهد مستقل؛ `I1` در ممیزی فرمول/ورودی/provenance/زنجیره/idempotency قبول؛ برچسب «غیرمستقل» |
| `CONFLICT_RATIO` | اختلاف نسبت با شاهد ≥ `FACTOR_MATERIAL` |
| `CONFLICT_DATE` | رویداد در تاریخ مؤثر متفاوت؛ خارج از پنجرهٔ shift |
| `CONFLICT_DUPLICATE` | رویداد تکراری/دوگانه با نسبت ناسازگار |
| `CONFLICT_CHAIN` | ضریب تجمعی یا گام قبل ناسازگار |
| `BLOCKED_SOURCE` | منبع لازم برای همان نماد/تاریخ وجود ندارد یا در دسترس/مجاز نیست، پس از تلاش مستند |
| `INSUFFICIENT_EVIDENCE` | شاهد موجود بازهٔ مربوطه را پوشش نمی‌دهد |
| `INVALID_DROPPED` | متناقض با شاهد و حذف‌شده؛ با شاهد حفظ می‌شود |

**قاعدهٔ نسبت:** تاریخ رویداد باید دقیقاً منطبق باشد (یا در پنجرهٔ shift موجود)؛ نسبت با خطای ≤ `FACTOR_EXACT` تأیید کامل، بین `FACTOR_EXACT` و `FACTOR_MATERIAL` وضعیت partial، و ≥ `FACTOR_MATERIAL` تعارض است. آستانه‌ها همان مقادیر موجود بند ۷.۳ هستند.

**تقدم گزارش نماد:** `CONFLICT_* > BLOCKED_SOURCE > INSUFFICIENT_EVIDENCE > PARTIAL_* > RECONSTRUCTED_AUDITED > VERIFIED_*`.

### ۷.۵ ولانا

سه گام `unverified` ولانا دقیقاً استخراج می‌شوند. برای هر گام بررسی می‌شود:

1. آیا رویداد در Product واقعی است؟
2. آیا تاریخ مؤثر اشتباه است؟
3. آیا اختلاف از تعریف رویداد/Corporate Action است؟
4. آیا منبع مرجع رویداد را متفاوت اعمال کرده است؟
5. آیا رویداد duplicate یا misclassified است؟
6. آیا `cum_factor` گام قبل اشتباه است؟

آستانهٔ ۰٫۱٪ تغییر نمی‌کند. اگر شواهد مستقل مسئله را حل کرد، `PASS_FACTOR`؛ وگرنه `PARTIAL_FACTOR` با علت دقیق. حذف رویداد فقط با مدرک.

### ۷.۶ ممیزی ۶٬۳۰۰ گام reconstructed_verified

برای همهٔ گام‌ها به‌صورت برنامه‌ای:

- بازتولید فرمول و ورودی‌ها از منبع
- بررسی provenance (`prov_kind`, source row)
- بررسی زنجیرهٔ `cum_factor_after` و نبود duplicate
- محاسبهٔ حساسیت factor: `risk_score = |اثر حذف گام بر سری تعدیل‌شدهٔ همان نماد| ÷ آخرین قیمت پایانی × وزن نبود شاهد مستقل`
- تفکیک «مستقل تأییدشده» از «فقط بازسازی داخلی»

هیچ گامی فقط به‌دلیل برچسب `reconstructed_verified` پذیرفته نمی‌شود. موارد پرریسک برای بازبینی دستی علامت می‌خورند.

---

## ۸) Ledger نمادها

### ۸.۱ فیلدها

`symbol, ins_code, asset_id, instrument_status, first_date, last_date, rows, trading_sessions, source_coverage, raw_ohlc_valid, adjusted_available, evidence_tier, event_coverage, ref_coverage, stale_status, gaps, anomalies, verification_method, final_status, remaining_blocker`

`final_status` یکی از شش وضعیت مأموریت است: `VERIFIED_WITH_EVENTS`, `VERIFIED_NO_APPLICABLE_EVENT`, `RECONSTRUCTED_VERIFIED`, `CONFLICT`, `BLOCKED_SOURCE`, `INSUFFICIENT_EVIDENCE`.

### ۸.۲ هویت

- نگاشت `symbol ↔ ins_code ↔ asset_id` با ابزار موجود (`internal/symbolid` و ابزار دادهٔ Python)؛ تغییر نماد، ادغام، توقف، حذف.
- هویت حل‌نشده ⇒ `SYMBOL_IDENTITY_MISMATCH`؛ هیچ حدسی مجاز نیست.

### ۸.۳ بازهٔ فعال و پوشش

- بازهٔ فعال از تاریخچه + وضعیت ابزار + تقویم + اطلاعیه‌ها.
- IPO/نماد جدید با تاریخ آغاز مستند، نقص تاریخی محسوب نمی‌شود.
- `VERIFIED_NO_APPLICABLE_EVENT` فقط با هویت حل‌شده + پوشش کامل `O1/O2` اثبات‌شده یا `R1` برای کل بازهٔ فعال. تداوم قیمت به‌تنهایی کافی نیست.
- نبود شاهد مستقل ⇒ `INSUFFICIENT_EVIDENCE` یا `BLOCKED_SOURCE`، حتی اگر هیچ رویدادی در DB نباشد.

### ۸.۴ Freshness

- متوقف/معلق/حذف‌شده از کهنه جدا می‌شود.
- کهنگی (stale) از نبودِ تاریخچه (missing) جدا می‌شود.
- برای نماد فعال، شکاف اخیر با backfill (D5) یا برنامهٔ مستند تازه‌سازی.
- هیچ نماد فعالی بدون توضیح و برنامه رها نمی‌شود.

### ۸.۵ Anomalyها

- Open/High/Low/Last/Close/Volume؛ `open_eq_prev_close`؛ تاریخ تکراری؛ `zero_fields`؛ تک‌کندل؛ شکاف تقویمی.
- هر anomaly با یکی از ۱۳ دستهٔ بند ۹ طبقه‌بندی می‌شود.
- اختلاف `LAST` و Official Closing = `PRICE_BASIS_DIFFERENCE`، نه خطای داده.

### ۸.۶ Reconciliation شمارش‌ها

اعداد ۶٬۱۰۳ تاریخچه‌دار، ۵٬۹۴۴/۵٬۹۴۱ `instruments`، ۱٬۳۰۶ بدون تاریخچه، ۱٬۴۶۸ تاریخچه‌دار خارج از `instruments`، ۱٬۳۴۳ بدون `price_history` و ۶٬۳۲۸ نماد «بدون شاهد تعدیل» (عدد گزارش Phase 4.9؛ اندازه‌گیری Seed برای نمادهای بدون رویداد Product عدد ۵٬۰۵۳ می‌دهد) با کلید واقعی بازتولید و اختلافشان توضیح داده می‌شود. نتیجه در `evidence/inventory-reconcile.json` و گزارش نهایی.

---

## ۹) Reconciliation و اصلاح داده

هر اختلاف باید در یکی از ۱۳ دسته باشد:

`SOURCE_MISMATCH, PRICE_BASIS_DIFFERENCE, CORPORATE_ACTION_MISSING, EVENT_DATE_MISMATCH, EVENT_RATIO_MISMATCH, SYMBOL_IDENTITY_MISMATCH, MISSING_HISTORY, CALENDAR_GAP, SOURCE_REVISION, PRECISION_OR_ROUNDING, INVALID_SOURCE_RECORD, VERIFIED_NO_EVENT, UNRESOLVED_SOURCE_GAP`

برای هر اختلاف ثبت می‌شود: نمونهٔ واقعی، ریشه، اثر روی DB، اثر روی adjusted OHLC، اثر روی API/چارت، روش اصلاح، شاهد قبل/بعد، تست رگرسیون.

### ۹.۱ قاعدهٔ اصلاح

- اصلاح فقط با شاهد مستقل.
- مقدار مرجع باید داخل `[low, high]` همان ردیف DB باشد (قاعدهٔ Phase 4.9).
- فقط ردیف‌های `legacy-unknown` برای اصلاح Open واجد شرایط‌اند.
- هیچ کندل synthetic ساخته نمی‌شود.
- هر اصلاح در `raw_history_corrections` با before/after، شاهد و SHA ثبت می‌شود.
- ردیفی که مرجع هم همان مقدار مشکوک را می‌دهد، «مشکوک ولی تأییدشده» می‌ماند، نه «اصلاح‌شده».
- `LAST` و پایانی بر اساس قرارداد `price_basis` تفسیر می‌شوند؛ جایگزینی بی‌برچسب raw و adjusted ممنوع.

---

## ۱۰) Backfill

### ۱۰.۱ شش نماد کوتاه‌تاریخ

- کل تاریخچهٔ روزانهٔ مرجع (type0) از نخستین تاریخ مرجع تا آخرین تاریخ، روی کپی مستقل DB.
- منبع و timestamp هر ردیف ثبت می‌شود (`src=rahavard-type0`, capture SHA, captured_at).
- Raw و adjusted مخلوط نمی‌شوند.
- نوع `type0` فقط در جایگاه سری خام با provenance صریح.
- سری تعدیل‌شده از موتور تعدیل داخلی و زنجیرهٔ معتبر خودش ساخته می‌شود.
- `type7` فقط برای parity/validation؛ نه جایگزینی بی‌برچسب raw.
- شکاف تاریخی و آخرین کندل هر نماد بررسی می‌شود.
- عدم وجود کندل با synthetic جبران نمی‌شود.

### ۱۰.۲ نمادهای فعالِ captureشده

- فقط نشست‌های اخیرِ جاافتاده (freshness) پر می‌شوند؛ نه کل شکاف تاریخی.
- type0 خام با provenance؛ پس از اعتبارسنجی price basis.
- شکاف تاریخی بزرگ‌تر به‌عنوان blocker باقی‌مانده مستند می‌شود.

### ۱۰.۳ قواعد مشترک

- فقط تاریخ‌های مفقود درج می‌شوند؛ ردیف موجود هرگز overwrite نمی‌شود.
- یکتایی `(symbol, date)` تضمین می‌شود.
- اجرای دوم = صفر insert/update.
- بازه‌های تعطیلی رسمی، توقف نماد و نبود معامله از هم تفکیک می‌شوند.
- هیچ ردیفی به‌عنوان «معامله‌شده» جعل نمی‌شود.

---

## ۱۱) Seed Candidate جدید

### ۱۱.۱ مسیر و مبنا

- مسیر جدید: `_audit/phase49-full-verification/seed/market.db`
- مبنا: کپی کاندید قبلی (`2ee66298…`)؛ کاندید قبلی هرگز overwrite نمی‌شود.
- عملیات: backfill (بند ۱۰) + materialize `history_validity` از Ledgerهای جدید + `adjust_pack_state` با SHA + `seed_manifest` کامل.

### ۱۱.۲ الزامات

- تمام دادهٔ موجود حفظ شود.
- Raw corrections و adjustment provenance کامل باشد.
- هیچ داده‌ای ساخته نشود.
- Merge idempotent باشد؛ اجرای دوم صفر insert.
- Duplicate `(symbol,date)` صفر باشد.
- دادهٔ کاربر (`market_watch`, watchlist, instrument_state, …) دست‌نخورده بماند.
- `PRAGMA integrity_check = ok`.
- SHA-256 DB و LZMA و gzip + round-trip LZMA.
- `seed_manifest` شامل نسخهٔ پک، SHA مرجع، تعداد ردیف‌های مرجع‌دار، tier شواهد، شمارش‌ها و دستور بازتولید.
- `history_validity` وضعیت‌های جدید را نشان دهد؛ `unverified` هرگز Live/Verified نمایش داده نشود.
- MA، Weekly، Monthly و `/api/chart-db` دوباره بررسی شوند.
- پاریتی Go/Python: oracle 76/76 و Go engine 30/30 روی پک/Seed جدید؛ صفر اختلاف factor/OHLC/events.
- Seed فقط Candidate می‌ماند؛ انتشار در این مأموریت ممنوع.

### ۱۱.۳ گیت انتشار Seed

`scripts/check_seed_release.py`:

- `seed_manifest.reference_derived_rows` را می‌خواند.
- اگر > 0 باشد و `--owner-approved-reference-redistribution` داده نشده باشد، بسته‌بندی/انتشار را رد می‌کند.
- در `release.yml` پیش از بسته‌بندی و در هر اسکریپت بسته‌بندی/انتشار Seed (از جمله `build_all.py` در صورت جاسازی `market.db`) سیم‌کشی می‌شود.
- در این مأموریت release اجرا نمی‌شود؛ گیت با manifest ساختگی آزموده می‌شود.

### ۱۱.۴ برچسب API/UI

- پاسخ‌های API که وضعیت اعتبار را حمل می‌کنند باید `unverified`/`reconstructed`/`stale` را صریح نشان دهند.
- تست API و تست فرانت تضمین می‌کند unverified/stale با Live/Verified اشتباه نمی‌شود.
- بازطراحی UI در دامنه نیست؛ فقط صداقت برچسب.

---

## ۱۲) CI مقصد

### ۱۲.۱ `guards.yml` (Production Gates)

Jobها: `go-backend`، `go-race`، `go-windows`، `delivery-contract`، `frontend-v2`، `data-integrity` (فقط سوئیت‌های A)، `repo-hygiene`، `zero-python-runtime`.

- `python-guards` حذف می‌شود.
- `js-syntax` (اسمبلی‌های static قدیمی) به lane Legacy منتقل می‌شود؛ بستهٔ Production فقط `frontend-v2` را حمل می‌کند.
- `data-integrity` فقط بررسی‌های داده‌ای A را نگه می‌دارد که معادل Go ندارند یا تا پورت شدن لازم‌اند. این job یک گیت داده است، نه اجرای Backend قدیمی Python؛ Test-harness بودن Python در CI مجاز است و به runtime محصول راه ندارد.

### ۱۲.۲ `python-tooling.yml` (Data/Research Gates)

- اجباری برای داده/پژوهش، نه گیت انتشار Production.
- سوئیت‌های B: oracle تعدیل، parity، backfill، import مرجع، seed build، اعتبارسنجی داده.
- fixtureهای بازتولیدپذیر؛ SKIP فقط با نام صریح فایل gitignoredِ غایب، بدون سبزِ بی‌سنجش.
- Python 3.12 + `requirements.txt`.

### ۱۲.۳ `python-legacy.yml` (Legacy Maintenance)

- سوئیت‌های C/D.
- `continue-on-error: true`؛ گزارش visibility، نه مسدودکردن انتشار.
- هر ردیف دلیل، تاریخ بازنشستگی و معادل Go/TS را در رجیستری دارد.

### ۱۲.۴ `run_all_tests.py` و رجیستری

- `--profile production|data|legacy|all` (پیش‌فرض `all` برای اجرای محلی).
- `dev/suite_registry.json` برای هر ۲۵۴ سوئیت: `id, script, label, category (A/B/C/D), disposition (KEEP/MIGRATE/DEPRECATE/REMOVE), profile, go_equivalent, ts_equivalent, reason, retirement_date`.
- `dev/suite_registry_guard.py`:
  - هر سوئیت موجود در `SUITES`/`JS_SUITES` دقیقاً یک ردیف دارد.
  - هیچ ردیف یتیم/فایل غایب وجود ندارد.
  - هر `MIGRATE` فایل/تابع Go/TS موجود را نام می‌برد.
  - هر `DEPRECATE/REMOVE` دلیل و معادل/تاریخ دارد.
  - خروجی JSON برای گزارش.

### ۱۲.۵ تعیین تکلیف ۲۴ شکست

- هر شکست با خطای واقعی بازتولید و ریشه‌یابی می‌شود؛ «محیطی» فقط با اثبات.
- A/B: اصلاح کد/فیکسچر یا پورت؛ بدون تضعیف assert.
- C/D: بازنشستگی با شاهد پوشش Go/TS؛ در lane Legacy می‌ماند تا پورت/حذف مستند.
- Goldenها فقط با بازتولید oracle و diff مستند به‌روز می‌شوند؛ ویرایش دستی Expected ممنوع.
- سوئیت‌های B2 (mstat)، B3 (chart)، B4 (fundamental) و m141/confidence/soft-warnings/mstat_local/funnel/watchlist/codal همگی root-cause می‌شوند؛ هیچ‌کدام «pre-existing» رها نمی‌شود.

### ۱۲.۶ پورت هدفمند

- فقط Aهایی که معادل Go/TS ندارند پورت می‌شوند.
- اولویت: candle contract، price basis، history-repair/ingestion، seed merge، API/chart contracts.
- هر پورت با تست Go/TS و رجیستری `MIGRATE` مستند می‌شود.
- حفاظت هیچ Aای تا پورت شدن از بین نمی‌رود.

### ۱۲.۷ Zero-Python Runtime

- `cmd/runtimecheck` (Go): `borsd` را با `BORS_DATA_DIR` موقت بالا می‌آورد، `/api/health` را می‌خواند، درخت فرایند را enumerate می‌کند و نبود python/py/pythonw/libpython را اثبات می‌کند؛ فقط PIDهای خودش را می‌کشد؛ خروجی JSON artifact.
- توسعهٔ `cmd/bundlecheck`: اسکن پسوند/نام/`_internal`/site-packages/PyInstaller + حضور اجزای لازم (`BorsTerminal_Ultimate.exe`، `BorsTerminal_Shell.exe`، `frontend/index.html`، `Version.txt`).
- اثبات نصاب در CI: نصب سایلنت در پوشهٔ موقتِ رانر، اسکن درخت نصب، اجرای `runtimecheck`، سپس uninstall؛ بدون لمس نصب/Registry واقعی.
- `release.yml`: همان اسکن + runtimecheck پیش از بسته‌بندی؛ در این فاز release اجرا نمی‌شود.

---

## ۱۳) تست و بازتولید

### ۱۳.۱ گیت‌های محلی

- `go vet ./...` و `go test ./...` در `backend-go`.
- frontend-v2: `npm ci`، typecheck، `npx vitest run`، build.
- `dev/suite_registry_guard.py` و `dev/phase49_rules_guard.py`.
- repo-hygiene: `git ls-files _audit/phase49-full-verification/captures` خالی باشد و `git check-ignore` برای نمونهٔ capture/DB/seed موفق باشد.
- `python dev/run_all_tests.py --profile data` و `--profile production`.
- Seed: integrity، idempotency، merge، restart، حفظ دادهٔ کاربر، MA/Weekly/Monthly/chart-db.
- Zero-Python: bundlecheck + runtimecheck روی بستهٔ CI-shaped.
- `python dev/version_anchor_guard.py` (بدون تغییر نسخه).
- race detector محلی قابل اندازه‌گیری نیست (نبود gcc/CGO)؛ فقط CI.

### ۱۳.۲ CI نهایی

- فقط روی HEAD نهایی، پس از آخرین commit.
- `CI-FINAL-RESULTS.json` شامل: `workflow_run_id`، `commit_sha`، `job_name`، `result`، `failure_details`، `run_url`.
- هیچ Run قدیمی یا روی commit قبلی پذیرفته نیست.

### ۱۳.۳ مصنوعات

- `ARTIFACTS-SHA256-full-verification.txt` برای همهٔ تحویل‌شدنی‌ها.
- capture خام در Git نیست؛ فقط metadata/SHA.
- دستورهای بازتولید در `FULL-VERIFICATION-REPORT.md`.

---

## ۱۴) تحویل‌شدنی‌ها

| # | فایل | محتوا | منبع |
| --- | --- | --- | --- |
| ۱ | `docs/opportunity-center/phase49/FULL-VERIFICATION-REPORT.md` | حکم، شمارش‌ها، فهرست حل‌شده/حل‌نشده، دستورهای بازتولید | stage 11 |
| ۲ | `docs/opportunity-center/phase49/ADJUSTMENT-EVIDENCE-LEDGER.csv` | ۸٬۲۸۰ گام + invalidها با شاهد/وضعیت | stage 3 |
| ۳ | `docs/opportunity-center/phase49/HISTORY-COVERAGE-LEDGER.csv` | ۶٬۱۰۳ نماد با هویت/پوشش/وضعیت/blocker | stage 5 |
| ۴ | `docs/opportunity-center/phase49/UNVERIFIED-RECONCILIATION.md` | ۱۳ دسته، نمونه، اثر، اصلاح، تست رگرسیون | stage 6/11 |
| ۵ | `docs/opportunity-center/phase49/PYTHON-CI-MIGRATION.md` | جدول ۲۵۴ سوئیت، ۲۴ ریشه‌یابی، disposition، تقسیم Workflow | stage 11 + رجیستری |
| ۶ | `docs/opportunity-center/phase49/CI-FINAL-RESULTS.json` | Run ID، SHA، هر job، نتیجه، جزئیات، لینک | CI نهایی |
| ۷ | `docs/opportunity-center/phase49/FINAL-SEED-MANIFEST.json` | SHA DB/LZMA، شمارش، provenance، ردیف‌های مرجع‌دار | stage 9 |
| ۸ | `docs/opportunity-center/phase49/ARTIFACTS-SHA256-full-verification.txt` | SHA همهٔ مصنوعات | stage 11 |

پشتیبان‌های الزامی: `dev/suite_registry.json`، `dev/phase49_status_rules.json`، `evidence/*.json`، `volana.json`، `inventory-reconcile.json`، `parity.json`.

---

## ۱۵) معیارهای پذیرش و حکم

| # | معیار | وضعیت مجاز |
| --- | --- | --- |
| ۱ | بررسی همهٔ ۱٬۳۵۸ گام unverified | PASS / INSUFFICIENT_EVIDENCE / BLOCKED |
| ۲ | ممیزی ۶٬۳۰۰ گام reconstructed_verified | PASS / INSUFFICIENT_EVIDENCE |
| ۳ | تعیین تکلیف سه گام ولانا | PASS / PARTIAL_FACTOR / BLOCKED |
| ۴ | تعیین تکلیف ۶٬۳۲۸ نماد بدون evidenceِ گزارش‌شده و reconciliation آن با ۶٬۱۰۳ نماد تاریخچه‌دار؛ Ledger باید هر دو عدد را توضیح دهد | PASS / INSUFFICIENT_EVIDENCE / BLOCKED |
| ۵ | بررسی ۵٬۱۸۸ ردیف unverified | PASS / INSUFFICIENT_EVIDENCE / BLOCKED |
| ۶ | Backfill شش نماد کوتاه‌تاریخ | PASS / BLOCKED_SOURCE |
| ۷ | تعیین هویت/وضعیت ابزارهای بدون history و تاریخچه‌های خارج از instruments | PASS / INSUFFICIENT_EVIDENCE |
| ۸ | ریشه‌یابی anomalyهای مهم OHLC و gapها | PASS / INSUFFICIENT_EVIDENCE |
| ۹ | تعیین تکلیف CI Python و سبزی Production Gates | PASS / FAIL |
| ۱۰ | تأیید Seed Candidate از نظر integrity/idempotency/provenance/Go parity | PASS / FAIL |

حکم نهایی:

- `PHASE49_COMPLETE_DATA_READY` فقط اگر همهٔ معیارهای لازم PASS باشند.
- در غیر این صورت `PARTIAL_WITH_EXPLICIT_BLOCKERS` یا `BLOCKED_BY_SOURCE_GAPS` با فهرست دقیق موارد باز.

**هیچ موردی فقط با تغییر Label از Unverified به Verified حل نمی‌شود.** اگر منبع مستقل واقعی وجود ندارد: `BLOCKED_SOURCE` یا `UNRESOLVED_SOURCE_GAP` با نماد، تاریخ، مقدار، منبع موردنیاز، تلاش‌ها و اثر بر استفادهٔ آینده ثبت می‌شود.

---

## ۱۶) ریسک‌ها و کاهش

| ریسک | اثر | کاهش |
| --- | --- | --- |
| انقضای نشست ره‌آورد | توقف capture | کد ۳ ⇒ توقف و ورود دستی مالک؛ بدون Credential |
| ۴۲۹/بن ره‌آورد | کندی/توقف | batch، delay، retries، resume فقط نمادهای ناموفق |
| شکست نقشهٔ هویت برخی نمادها | عدم تأیید | `SYMBOL_IDENTITY_MISMATCH`/`INSUFFICIENT_EVIDENCE`، نه حدس |
| نبود gcc/CGO محلی | race محلی | فقط CI؛ ثبت `NOT_MEASURED` محلی |
| نصب‌کننده در CI | ریسک نصب | فقط پوشهٔ موقتِ رانر، سپس uninstall |
| branch protection ناشناخته | Legacy اجباری بماند | تنظیمات مخزن تغییر نمی‌کند؛ در گزارش ثبت می‌شود |
| مجوز دادهٔ مرجع | انتشار | Candidate فقط؛ گیت انتشار؛ تأیید مالک |
| حجم/زمان capture | تأخیر | دامنهٔ D1 + اجرای موازی با کار CI |

---

## ۱۷) ترتیب اجرا

1. **Baseline و شاخه:** تأیید HEAD، ساخت شاخه، commit سند طراحی.
2. **CI Audit (موازی با capture):** رجیستری ۲۵۴ سوئیت، ریشه‌یابی ۲۴ شکست، پورت‌های هدفمند، تقسیم Workflow.
3. **Capture:** ساخت فهرست D1، capture در نشست مالک، import و metadata.
4. **Step Ledger:** ۸٬۲۸۰ گام، شواهد، وضعیت‌ها، ولانا.
5. **Symbol Ledger:** ۶٬۱۰۳ نماد، هویت، پوشش، freshness، anomaly، inventory reconciliation.
6. **Backfill:** ۶ نماد کامل + freshness فعال‌ها روی کپی.
7. **Seed Candidate:** build، manifest، SHA/LZMA، integrity، idempotency.
8. **Zero-Python:** bundlecheck/runtimecheck/installer/micro-smoke.
9. **Parity:** Go/Python، MA/Weekly/Monthly/chart-db.
10. **Deliverables:** هشت فایل + SHA؛ بازبینی سند؛ commit/push.
11. **CI نهایی:** روی HEAD نهایی؛ ثبت `CI-FINAL-RESULTS.json`؛ گزارش نهایی.

نقاط توقف اجباری: پس از capture (پوشش)، پس از Step Ledger (شمارش‌ها)، پس از Seed (integrity/idempotency)، و پیش از CI نهایی.

---

## ۱۸) قواعد Commit و Push

- فقط روی `mission/phase49-full-verification-python-ci-2026-11-10`.
- commitهای افزایشی با پیام‌های `docs(phase49): …`، `feat(phase49): …`، `fix(phase49): …`.
- ممنوع: Merge به `main`، Tag، Release، Force Push، تغییر Visibility، حذف/overwrite DB عملیاتی.
- `main` و شاخه‌های قبلی و آرشیوهای Phase 4.8 بدون تغییر.
- در پایان: Push شاخهٔ مأموریت؛ بدون Merge.
- هیچ Credential/Token/Cookie/Private Key یا دادهٔ خام مرجع در commit نیست.

---

## ۱۹) معیار بازبینی سند

این سند وقتی نهایی است که:

1. هیچ جای‌نگهدار، بخش ناقص یا نیازِ تصمیم باز نداشته باشد.
2. بین بخش‌های capture/ledger/seed/CI تناقض نباشد.
3. هر تصمیم مالک (D1–D5) در معماری و آزمون‌ها ردپای صریح داشته باشد.
4. هیچ عدد مبهم یا «تقریبی» بدون منبع بازتولید نمانده باشد (عدد union با stage 1).
5. دامنه برای یک مأموریت واحد کافی و برای Phase 4.10 باز نباشد.
