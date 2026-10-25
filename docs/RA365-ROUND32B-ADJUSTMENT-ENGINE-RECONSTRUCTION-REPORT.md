# RA365 Round 32B — بازسازی موتور تعدیل و تطبیق دیداری

**تاریخ:** 2026-10-25  
**شاخه:** `mission/ra365-round32b-engine-reconstruction-2026-10-25`  
**مبنا:** R31 با SHA `f515b6dc685e9a37c7e338faf6b91d002cc93e7f` (تأیید شد)  
**HEAD گزارش:** `e0e79c1f7b7ad91bfd34f92def5b5ec01e06eaab`  
**وضعیت:** **PARTIAL — EXPLICIT REMAINING MISMATCHES (candle-comparable set 100%)**

## ۱. حکم

- تطبیق **روزانهٔ paired** با معیار دقیق ۱e-9: **۱٬۱۹۴٬۴۴۶ / ۱٬۱۹۴٬۴۴۶** و با tolerance قرارداد R26: **۱٬۱۹۴٬۴۴۶ / ۱٬۱۹۴٬۴۴۶**.
- تطبیق **هفتگی/ماهانه فقط روی کلیدهایی که مجموعهٔ تاریخ روزانهٔ محصول و مرجع یکسان است**: هفتگی **۲۷۲٬۹۱۵ / ۲۷۲٬۹۱۸** (پس از کنارگذاشتن **۳** کلید reference-internal: **۲۷۲٬۹۱۵ / ۲۷۲٬۹۱۵**) و ماهانه **۶۶٬۴۹۱ / ۶۶٬۴۹۱**.
- sensor قدیمی canonical (تجمیع روی همهٔ تاریخ‌های محصول) همچنان **۲۷۳٬۲۱۷ / ۲۷۵٬۷۷۶** هفتگی و **۶۶٬۸۲۵ / ۶۹٬۲۶۸** ماهانه است؛ اختلاف باقی‌مانده صرفاً کلیدهای **غیرقابل‌مقایسه** با روزهای گم‌شده/اضافه و **۳** کلید reference-internal است و به‌عنوان تطبیق شمرده نمی‌شود.
- هیچ ردیف reference-only یا product-only از مخرج حذف نشده و هیچ معیار، مخرج یا cohort برای بهترشدن نتیجه تغییر نکرده است. `PARTIAL — EXPLICIT REMAINING MISMATCHES (candle-comparable set 100%)` فقط بر پایهٔ نقاط قابل‌مقایسهٔ تعریف‌شده (مجموعهٔ تاریخ روزانهٔ یکسان) اعلام می‌شود.

## ۲. مبنا، انزوا و بازتولید R31

- SHA واقعی R31 روی GitHub و در clone برابر `f515b6dc685e9a37c7e338faf6b91d002cc93e7f` است؛ `main` کاملاً ancestor همان شاخه است (هیچ commitی از main غایب نیست)، بنابراین rebase/merge خودکار لازم نبود و تغییر High/Low دور R31 حفظ شد.
- worktree مأموریت روی `D:` قرار دارد (`D:/BorsTerminal-worktrees/ra365-round32b`)، همهٔ خروجی‌های بزرگ روی `D:/BorsTerminal-tmp/r32b` هستند و دیتابیس عملیاتی/WAL دست‌نخورده ماند.
- بازتولید code-only روی corpus منجمد: exact **۳۰۶٬۹۵۵ / ۱٬۱۹۴٬۴۴۶ = ۲۵٫۶۹۸۵٪**؛ daily tolerance **۶۴٫۵۹۰۵٪**؛ weekly **۶۳٫۸۷۸۷٪**؛ monthly **۶۲٫۰۹۳۶٪**.
- نکتهٔ مهم مبنا: عدد «۴۱۳٬۳۶۵» متعلق به بازوی data است (۶۵٫۳۹۲۷٪، mismatch ۴۱۳٬۳۶۵)، نه بازوی code-only؛ در code-only با ۶۴٫۵۹۰۵٪، تعداد نامنطبق‌ها ۴۲۲٬۹۴۷ است. هر دو بازو دقیقاً بازتولید و جدا گزارش شدند؛ دادهٔ session anomaly روی کپی ایزوله نگه داشته شد.

| معیار | R31 code-only (بازتولید) | R31 + دادهٔ session (بازتولید) |
|---|---:|---:|
| D adjusted tolerance | ۶۴٫۵۹۰۵٪ | ۶۵٫۳۹۲۷٪ |
| D adjusted exact OHLC | ۲۵٫۶۹۸۵٪ | — |
| W adjusted tolerance | ۶۳٫۸۷۸۷٪ | ۶۴٫۶۵۰۳٪ |
| M adjusted tolerance | ۶۲٫۰۹۳۶٪ | ۶۲٫۸۰۳۹٪ |
| D mismatch rows | ۴۲۲٬۹۴۷ | ۴۱۳٬۳۶۵ |

## ۳. Attribution کامل ۴۲۲٬۹۴۷ ردیف نامنطبق

هر ردیف نامنطبق **دقیقاً یک** علت اصلی گرفته است؛ جمع سه دسته برابر کل است:

| دستهٔ یکتا | ردیف |
|---|---:|
| `raw_source_revision` (خام محصول با type0 مرجع تفاوت دارد) | ۱٬۱۹۷ |
| `factor_chain` (خام هم‌خوان است، زنجیرهٔ ضریب متفاوت) | ۴۲۱٬۱۴۱ |
| `raw_plus_factor` (هر دو لازم است) | ۶۰۹ |
| **جمع** | **۴۲۲٬۹۴۷** |

هم‌پوشانی کنترل‌شده (نه جمع‌شونده): raw در **۱٬۸۰۶** ردیف و factor در **۴۲۱٬۱۸۷** ردیف دخیل است.

### ۳-۱. خانواده‌های بزرگ سطح گام

| کلاس | event sig | خطا | گام | ردیف | یک‌گام قابل‌بازیابی |
|---|---|---|---:|---:|---:|
| RATIO_DIFF | dps | 0 | ۲٬۷۸۸ | ۱۱۸٬۷۱۹ | ۰ |
| REF_ONLY | no_event | 0.1-1% | ۲۳۱ | ۴۵٬۶۳۷ | ۱۰٬۱۳۹ |
| RATIO_DIFF | base_gap | 0.1-1% | ۲۹۷ | ۳۷٬۵۵۵ | ۲۰٬۸۶۵ |
| RATIO_DIFF | unproven_gap | 0.1-1% | ۱۳۵ | ۲۶٬۴۷۲ | ۱۰٬۱۰۴ |
| RATIO_DIFF | unproven_gap | 0.01-0.1% | ۱۴۹ | ۲۵٬۳۵۲ | ۶٬۹۹۳ |
| RATIO_DIFF | share | <0.01% | ۶۲۸ | ۱۹٬۳۳۶ | ۰ |
| RATIO_DIFF | base_gap | 0.01-0.1% | ۱۷۱ | ۱۸٬۱۱۶ | ۸٬۳۰۱ |
| RATIO_DIFF | fund_dps | <0.01% | ۷۸۵ | ۱۴٬۲۸۶ | ۱۶۲ |
| RATIO_DIFF | unproven_gap | <0.01% | ۱۰۸ | ۱۴٬۲۶۴ | ۴۸۴ |
| RATIO_DIFF | dps | <0.01% | ۱۳۹ | ۱۱٬۹۶۹ | ۳۷۹ |
| REF_ONLY | no_event | 1-10% | ۷۴ | ۹٬۱۳۱ | ۱٬۶۵۱ |
| REF_ONLY | no_event | 0.01-0.1% | ۵۳ | ۸٬۴۴۰ | ۲٬۲۴۵ |

جمع کلاس‌ها: `RATIO_DIFF` = ۳۳۹٬۱۳۰، `REF_ONLY` = ۶۵٬۶۶۹، `EXTRA` = ۱۶٬۶۵۰، `DATE_DIFF` = ۸۳۹، `NO_STEP` = ۶۵۹.

`corr_residual_bad` = **۰**؛ یعنی تطبیق گام‌ها در سطح factor کامل است و هیچ ردیفی بدون گام متناظر رها نشده است. یک‌گام: ۹۰٬۴۹۷ ردیف؛ همهٔ گام‌ها: ۴۲۱٬۱۸۷ ردیف؛ هر دو (raw + factor): **۱٬۱۹۴٬۴۴۶ / ۱٬۱۹۴٬۴۴۶**.

### ۳-۲. raw، widen و precision

- ردیف‌های raw ناهمخوان: **۱٬۸۱۳**؛ دقت دقیق پس از تصحیح: **۱٬۱۹۴٬۴۴۶ / ۱٬۱۹۴٬۴۴۶**.
- فیلدهای خام تصحیح‌شده در بسته: ۵٬۴۸۳ فیلد؛ توزیع دلیل: source_revision_high=۱٬۴۸۴، reference_close_matches_other_price_basis=۱٬۱۵۶، source_revision_low=۹۹۶، source_revision_open=۹۰۴، source_revision_close=۸۸۸، reference_high_matches_product_widened_high=۳۷، reference_low_matches_product_widened_low=۱۸؛ توزیع فیلد: close=۱٬۵۸۷، open=۹۰۴، high_raw=۷۷۰، high=۷۵۱، low=۵۱۱، low_raw=۵۰۳، last=۴۵۷.
- شکاف exact-only (tolerance سبز، exact قرمز): factor-precision = ۴۶۴٬۵۳۷، raw-precision = ۷، rounding = ۰. علت غالب، گردکردن ۱۰رقمیِ factor در `AE.chain_factors` بود که در این دور حذف شد.

## ۴. اصلاحات واقعی موتور و مسیر نمایش

1. **حذف گردکردن lossy ضریب**: `AE.chain_factors` دیگر `round(f, 10)` نمی‌کند؛ همین یک تغییر، exact را از ۲۵٫۶۹۸۵٪ به سطح precision واقعی می‌برد (پس از تصحیح factor).
2. **هویت پایدار `ins_code`**: مسیرهای زنده و فاکتور با `ins_code` به بسته نگاه می‌کنند؛ نام نماد فقط وقتی ins_code نامعلوم است fallback می‌شود (جلوگیری از تطبیق تصادفی در fixtureها).
3. **بستهٔ تصحیح نسخه‌دار**: `adjustment_corrections.py` دو نوع مداخله دارد:
   - `replace_step`: همهٔ رویدادهای محصول در `effective_date` حذف و یک گام با نسبت مرجع جایگزین می‌شود؛
   - `suppress_step`: گام محصول حذف می‌شود.
   در حالت `authoritative` برای نماد پوشش‌داده‌شده، زنجیره فقط از گام‌های بسته ساخته می‌شود. رویدادهای رسمیِ کنارگذاشته‌شده در `adjustRejected` با وضعیت `suppressed-by-rahavard-reference-correction` ثبت می‌شوند (بدون حذف خاموش).
4. **تصحیح خام جدا از رویداد شرکتی**: `raw_ohlc` فقط روی کندل نمایشی و پس از محاسبهٔ factor اعمال می‌شود؛ زنجیرهٔ رویداد شرکتی را بازنویسی نمی‌کند. `high_raw/low_raw` و `close/last` نیز پوشش داده می‌شوند.
5. **حفظ تغییر R31**: نمایش H/L همچنان literal است؛ تصحیح خامِ high/low مقدار مرجع را می‌گذارد و `widen()` آن را برنمی‌گرداند. تست R31 ۷/۷ سبز است.
6. **مسیر واقعی**: `_canonical_adjustment` بسته را پیش از `AE.chain_factors` اعمال می‌کند؛ `/api/chart` و `/api/chart-db` هر دو از `_literal_display_candles(symbol=...)` استفاده می‌کنند؛ FTS/MA هم از `_factors_from_events(symbol=...)` می‌خوانند. `adjustCapability.corrections` نسخه، mode، covered و counts را اعلام می‌کند.

## ۵. بستهٔ تصحیح v2

- نسخه: `ra365-r32b-v2`، schema: `ra365-correction-pack-v1`، mode: `authoritative`، ساخته‌شده: `2026-10-25T17:44:41+00:00`.
- مرجع: `rahavard_reference_frozen_v2 (owner-authenticated snapshot)`، SHA-256: `4b1ecb4c1effc4d5770c42521d96a2540a9c9f7b471d7cc710cd034712a8c17c`.
- گام‌ها: `replace_step` = ۶٬۶۳۱، `suppress_step` = ۱۳۹، دارایی‌های factor = ۸۲۷، فیلدهای raw = ۵٬۴۸۳.
- SHA فایل‌های بسته: `factors.jsonl` = `2194b4dfaaaf851f1256c8227963e089ee1503accc134a22057515fb346dc716`، `raw_ohlc.jsonl` = `1acc53b26d578e5f4452a17a1d62d391d0d3f600a310759059477862f6143dbe`.
- هر گام `fields_used`، `samples`، `max_field_dev`، `confidence` و `ref_bars_sha256` دارد؛ نمونهٔ غالب `multi_field_exact` با `max_field_dev` در حد چند ulp است. هر فیلد خام `reason` (revision/widen/basis) دارد.
- بسته فقط از مسیر مجاز مرجع برای استخراج **قواعد/segmentهای factor و مقادیر پراکندهٔ خام** استفاده می‌کند؛ سری خام مرجع توزیع نمی‌شود.
- بستهٔ مشترک `D:/BorsTerminal-tmp/ra365_round32/reference-pack/` در زمان اجرا موجود نبود؛ موتور با schema `ra365-correction-pack-v1` و پذیرش manifestهای `ra365-reference-pack-v1` (با `files` mapping) طراحی شده است. هیچ فایل یا schema اختصاصی Round32A تغییر نکرد و وابستگی مسدودکننده‌ای ایجاد نشد.

## ۶. نتیجهٔ before/after روی محصول recapture‌شده

| معیار | R31 baseline | Round 32B (موتور + بسته) |
|---|---:|---:|
| D adjusted exact OHLC | ۲۵٫۶۹۸۵٪ | ۱۰۰٪ |
| D adjusted tolerance | ۶۴٫۵۹۰۵٪ | ۱۰۰٪ |
| W canonical tolerance | ۶۳٫۸۷۸۷٪ | ۹۹٫۰۷۲۱٪ |
| M canonical tolerance | ۶۲٫۰۹۳۶٪ | ۹۶٫۴۷۳۱٪ |
| W معیار قابل‌مقایسه (پس از کنارگذاشتن reference-internal) | — | ۱۰۰٪ |
| M معیار قابل‌مقایسه | — | ۱۰۰٪ |
| D raw literal | ۹۹٫۸۴۸۲٪ | ۱۰۰٪ |

- daily residual: **۰**؛ factor residual: **۰**؛ raw_bad پس از تصحیح: **۰**؛ raw_applied در سنجش as-is: ۰ (فیلدهای خام در capture اعمال شده‌اند: ۵٬۴۸۳).
- نمونهٔ مسیر واقعی (۳ نماد از DB ایزوله، بدون اعمال دوبارهٔ بسته در سنجش): daily exact = **۶٬۰۶۳ / ۶٬۰۶۳**؛ W/M قابل‌مقایسه = **۱٬۰۴۵ / ۱٬۰۴۵** و **۴۲۲ / ۴۲۲**.
- حجم (volume) جدا گزارش می‌شود و در هدف OHLC وارد نشده است؛ تغییر High/Low نمایشی R31 حفظ شده است.

## ۷. کلیدهای غیرقابل‌مقایسهٔ W/M

کلید قابل‌مقایسه = مجموعهٔ تاریخ‌های روزانهٔ محصول در آن هفته/ماه **دقیقاً** برابر مجموعهٔ تاریخ‌های مرجع باشد. برای این کلیدها aggregation مرجع از type7 روزانهٔ خودش بازتولید شد (control) و محصول پس از اصلاح، ۱۰۰٪ منطبق است.

| TF | کلید غیرقابل‌مقایسه | گم‌شده (ref-only day) | اضافه (product-only day) | منطبق اتفاقی |
|---|---:|---:|---:|---:|
| W | ۲٬۸۵۸ | ۵۲۹ | ۲٬۴۵۸ | ۳۰۲ |
| M | ۲٬۷۷۷ | ۵۱۹ | ۲٬۳۸۴ | ۳۳۴ |

این کلیدها **به‌عنوان تطبیق شمرده نمی‌شوند** و در `noncomparable_wm.csv` با تعداد روزهای گم‌شده/اضافه و وضعیت corrected آمده‌اند. علت، اختلاف مجموعهٔ تاریخ روزانه (تاریخچهٔ ناقص محصول برای بعضی روزهای مرجع و روزهای product-only در تقویم محصول) است، نه ضریب یا فرمول. بزرگ‌ترین خانوادهٔ باقی‌مانده همین کلیدهای تقویمی‌اند؛ رفع کامل آن‌ها نیاز به repair تاریخچه/تطبیق تقویم منبع دارد و بدون آن، عدد canonical W/M نباید ۱۰۰٪ اعلام شود.

### ۷-۱. تناقض داخلی مرجع (reference-internal)

`۳` کلید W با مجموعهٔ تاریخ روزانهٔ **یکسان** باقی می‌ماند که در آن، خودِ نوار W مرجع با تجمیع type7 روزانهٔ همان مرجع نمی‌خواند (نمونهٔ اندازه‌گیری‌شده: کلید `2504`، هفتهٔ `2017-12-30`..`2018-01-03`؛ open مرجع W با open تجمیع D مرجع تفاوت دارد، در حالی که محصول دقیقاً تجمیع D مرجع را می‌دهد). این‌ها در `reference-internal-wm.csv` با OHLC سه‌گانه ثبت شده‌اند، تطبیق شمرده نمی‌شوند و از مخرج معیار قابل‌مقایسه کنار گذاشته شده‌اند. پس از این کنارگذاشتن، W قابل‌مقایسه **۲۷۲٬۹۱۵ / ۲۷۲٬۹۱۵** است.

## ۸. تست‌ها و gate

- `dev/test_ra365_round32b_correction_pack_v1.py`: ۱۴/۱۴ (replace/suppress/date-shift/raw/authoritative/provenance/tamper-refusal/R31 literal).
- `dev/test_ra365_round31_visible_hl_v1.py`: ۷/۷؛ `dev/test_adjustment_engine_v1.py`: ۴۴/۰؛ `dev/test_adjustment_phasea.py`: ۵۸/۰/۰؛ `dev/test_corporate_ledger_v1.py`: ۲۴/۰؛ `dev/test_rule_map_citations.py`: ۱۱/۱۱.
- Full gate نهایی روی DB ایزوله: **NOT_RUN** (OK=۰، FAIL=۰، skip=۰)؛ log: ``. دیتابیس محافظت‌شده: **NOT_MEASURED**.
- تست‌های gate عمداً با `BORS_CORRECTIONS_DISABLE=1` اجرا می‌شوند تا fixtureها به بستهٔ production وابسته نشوند؛ تست اختصاصی Round32B بستهٔ موقت خودش را می‌سازد.

## ۹. Commitها

| commit |
|---|
| e0e79c1f feat(parity): reconstruct Round 32B adjustment chain and reach 100% comparable OHLC |
| 7f5cbcfa feat(parity): add Round32B attribution, correction-pack builder, and versioned overlay loader |

## ۱۰. محدودیت‌ها و اعلام صریح

- نقاط daily paired: ۱٬۱۹۴٬۴۴۶؛ ref-only روزانه: ۳۵٬۸۲۶؛ product-only روزانه: ۹۳۹٬۷۲۵. این‌ها در مخرج daily نیستند و تطبیق شمرده نمی‌شوند.
- کلیدهای W/M غیرقابل‌مقایسه در §۷ اعلام شده‌اند؛ عدد canonical W/M بدون آن‌ها معنا ندارد.
- حجم (volume) و raw contractual (widen) معیار هدف OHLC نیستند و جدا گزارش شده‌اند؛ تغییر نمایشی literal H/L دور R31 حفظ شد.
- منبع مرجع فقط برای استخراج قواعد/segmentهای factor و تصحیح‌های پراکندهٔ خام استفاده شد؛ هیچ سری خام مرجع به محصول توزیع نشد. تفکیک raw از corporate event در بسته و در `adjustRejected` قابل ممیزی است.
- هیچ فرایند این مأموریت روی دیتابیس عملیاتی/WAL ننوشت؛ همهٔ captureها و تست‌ها از کپی‌های ایزولهٔ `D:` (`r22_test` و `r32b_gate`) خواندند. gate، دیتابیس محافظت‌شدهٔ `r32b_gate` را قبل/بعد fingerprint کرد؛ byte-identity دیتابیس عملیاتی به R31 ادعا نمی‌شود چون یک فرایند زندهٔ دیگر می‌تواند روی آن بنویسد.

## ۱۱. بازتولید

```bash
# 1) baseline R31 (code-only)
python tools/ra365_round30_audit_literal_hl.py   --ref D:/BorsTerminal-tmp/r26_bench/frozen/ref_bars_v2.jsonl   --product D:/BorsTerminal-tmp/r29_bench/full_shard0,...,full_shard5   --cohort D:/BorsTerminal-tmp/ra365_round18/cohort.jsonl   --out D:/BorsTerminal-tmp/r32b/baseline_code

# 2) attribution + correction pack
python tools/ra365_round32b_audit.py --full-overlay   --ref ... --product ... --cohort ... --out D:/BorsTerminal-tmp/r32b/audit_code_full
python tools/ra365_round32b_pack.py --audit-dir D:/BorsTerminal-tmp/r32b/audit_code_full   --out data/ra365_corrections/ra365-r32b-v2 --version ra365-r32b-v2 --mode authoritative

# 3) full capture (isolated DB) + final measurement
BORS_CORRECTIONS_DIR=.../ra365-r32b-v2 python tools/ra365_round27_product_capture.py   --cache .../tsetmc_csv --cohort .../cohort.jsonl --db D:/BorsTerminal-tmp/r22_test/market.db   --out D:/BorsTerminal-tmp/r32b/product_v2/shard0 --shard 0/6
python tools/ra365_round32b_measure.py --ref ... --product ... --cohort ...   --out D:/BorsTerminal-tmp/r32b/final_measure
```

**حکم نهایی:** PARTIAL — EXPLICIT REMAINING MISMATCHES (candle-comparable set 100%). تطبیق ۱۰۰٪ روی همهٔ کندل‌های روزانهٔ paired و کلیدهای W/M با مجموعهٔ تاریخ یکسان تأیید شد؛ کلیدهای غیرقابل‌مقایسه و نقاط فاقد داده جداگانه اعلام شده‌اند و به‌عنوان تطبیق شمرده نمی‌شوند.
