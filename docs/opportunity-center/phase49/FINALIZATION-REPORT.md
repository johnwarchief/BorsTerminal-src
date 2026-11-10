# Phase 4.9 Finalization — گزارش نهایی: تکمیل موتور تعدیل، اعتبارسنجی تاریخی و آمادگی Seed

- تاریخ: 2026-11-10
- شاخه: `mission/phase49-data-finalization-2026-11-10`
- مبنای شاخه: `97d6294e` (HEAD شاخهٔ Phase 4.9 قبلی)
- `main`: `9a919e82` — بدون تغییر
- شاخهٔ قبلی `mission/phase49-adjustment-chain-closure-2026-11-10` روی `97d6294e` حفظ شد
- Merge / Tag / Release: انجام نشد
- **حکم نهایی: `PHASE49_PARTIAL_WITH_EXPLICIT_BLOCKERS`**

## ۰) خلاصهٔ اجرایی

1. **ریشهٔ نقصِ باقی‌مانده بسته شد:** بستهٔ Rebuildِ کامل (`ra365-phase49-rebuild-full-v2`) از
   canonical product + مرجعِ مستقلِ ره‌آورد ساخته شد: **8,280 گام در 951 نماد**، شامل **623 گام
   پیش از 2020**، با `as_of=2026-10-25` و 28 گامِ متناقض با مرجع که به‌صورت `invalid` حذف شدند.
2. **مرجع 2010–2024 برای هر 36 نماد (30 + 7) واقعاً گرفته شد:** 222 سری روزانه/هفتگی/ماهانه
   (type0 خام + type7 تعدیل‌شده)، 266,408 ردیف، از `2010-01-01` تا `2026-11-10`، با نشستِ
   وارد‌شدهٔ مالک و بدون ثبتِ هیچ Token/کوکی در Git.
3. **پاریتی 30 نماد: 29 `PASS_FACTOR` + 1 `PARTIAL_FACTOR`؛** 503 گام مرجع، هر 503 گام
   «دقیق»، صفر گامِ گم‌شده، صفر گامِ مادیِ اضافه. تنها `PARTIAL` ولانا با بیشینهٔ خطای نسبی
   factor **0.198%** است (زیر 1%، بالای آستانهٔ 0.1%). 7 نماد کوتاه‌تاریخ: 6 `PASS` + 1 `PARTIAL`.
4. **9 نمادِ مبنای Open مستقلاً ممیزی شد:** 11 نماد و 3,105 ردیف با شاهدِ مرجع اصلاح شد
   (Open مرجع باید داخل `[low, high]` همان ردیف DB باشد)؛ 0 رد، 0 درخواستِ بی‌شاهد،
   `integrity_check=ok`. هیچ Openی ساخته نشد.
5. **Seed Candidate ساخته و آزموده شد:** 511,139 ردیف `price_history`، 6,103 نماد، 8,280 گام،
   جدول‌های `adjust_pack_state` / `history_validity` / `seed_manifest`، merge ایدمپوتنت،
   دادهٔ کاربر حفظ‌شده، MA چهار دوره با 2,000 کندل، `/api/chart-db` تا 2010.
6. **پاریتی Python↔Go روی بستهٔ نهایی 30/30 PASS است:** صفر اختلاف در factor، صفر اختلاف در
   OHLC کندل، برابری events/rejected؛ `go vet` و `go test ./...` سبز.
7. **پوشش «کل دیتابیس» کامل نیست:** از 6,103 نماد، فقط 25 نماد بیش از 10 سال سابقه و
   **5,254 نماد کمتر از 1 سال** دارند؛ 6,328 نماد هیچ شاهدِ تعدیلی ندارند. این عدد پنهان
   نشده و «Full Database Coverage» اعلام نمی‌شود.
8. **`python-guards` در CI قرمز است (ازپیش‌موجود):** پس از اصلاح دو نقصِ محیطی
   (نصب `node_modules` و seamِ `B0–B4`)، 24 سوئیت قرمز ماند؛ B1/seam سبز شدند و B3 به
   49/50 رسید، اما B2/B4 (طلایی‌های کهنهٔ mstat/fundamental) و ~20 سوئیتِ دیگر
   (m141، confidence، soft-warnings، mstat_local، funnel، watchlist، codal، …) از merge
   `072a2607` به ارث رسیده‌اند و خارج از دامنهٔ Phase 4.9‌اند. جزئیات در §۱۴ و `B1`.

## ۱) تحویل‌شدنی ۱ — گزارش ریشه‌یابی

- ریشهٔ تاریخی (پیش از این مأموریت): `docs/opportunity-center/phase49/CHAIN-ANALYSIS.md` و
  `docs/opportunity-center/phase49/FINAL-REPORT.md` — بستهٔ `ra365-r32b-v2` برای 30 نماد صفر
  گامِ پیش از 2020 داشت و حالت `authoritative` رویدادهای canonical را Suppress می‌کرد.
- ریشهٔ باقی‌ماندهٔ این مرحله: **نبودِ مرجعِ مستقل** برای 2010–2024 (فایل `bars.ndjson.gz`
  Phase 4.8 روی این ماشین نبود) و **مبنای Open قدیمی** در ردیف‌های `legacy-unknown`.
- ریشهٔ دو نقصِ ریز که در همین مرحله بسته شد:
  1. یک گامِ جعلیِ Product در `2024-08-24` (نسبت 0.001067 در شنفت) زنجیرهٔ 7 نماد را خراب
     می‌کرد؛ مرجع آن را نقض کرد و گام به‌صورت `drop-contradicted` حذف شد (شاهد در
     `manifest.json → dropped_steps`).
  2. `adjust_pack_state` در Seed با نسخهٔ قدیمیِ manifest (بدون `file_sha256`) پر شده بود؛
     ستون‌های SHA خالی بودند و اکنون با SHA فایل‌های نهایی پر شده‌اند.
- ریشهٔ قرمزِ B2 (خارج از دامنهٔ تعدیل): §۱۵ / `B1`.

شاهد عددی: `_audit/phase49-finalization/evidence/canonical-summary.json` (1,118 نماد، 9,930
رویداد، 503 رویداد پیش از 2020)، `reference-step-decisions-all.csv` (تصمیم هر گام).

## ۲) تحویل‌شدنی ۲ — بستهٔ نهاییِ Rebuild

مسیر: `data/ra365_corrections/ra365-phase49-rebuild-full-v2/`

| فایل | حجم (بایت) | SHA-256 |
| --- | ---: | --- |
| `factors.jsonl` | 7,008,677 | `aa8e13fc2d172c3e3355e86bba1bd505b5070269d0a47baf0c3c2d59784ceb24` |
| `raw_ohlc.jsonl` | 2,848,986 | `b02e8859db53081a2b9f69c1a28cd513b54d968b53944363bfbd7932a399975a` |
| `manifest.json` | 124,248 | `458cd5ebfdcc7a752c7eba9839eba75c13db1efefd4fcf572b41095ef936578c` |

| سنجه | مقدار |
| --- | ---: |
| حالت | `authoritative` |
| `as_of` | `2026-10-25` |
| گام‌ها | 8,280 |
| نمادها | 951 |
| گام پیش از 2020 | 623 |
| verified / reconstructed_verified / unverified | 622 / 6,300 / 1,358 |
| invalid (drop-contradicted) | 28 |
| مرجع | `ab3b6a93…, c2a3d253…` (SHA سری‌های نرمال‌شدهٔ 30 و 7) |

- قواعد ادغام در `manifest.rules` ثبت شده‌اند: جایگزینیِ گامِ بسته در همان تاریخ، حذف
  Product هم‌تاریخ، نگه‌داشتن Product خارج از تاریخ‌های بسته، dedup با شاهد، و حذف گامِ
  مادیِ متناقض با مرجع (`drop-contradicted`) فقط داخل پوششِ مرجع.
- `cum_factor_after` برای هر گام ثبت است؛ `prov_kind` (pack/product/reference) و `validity`
  در هر ردیف `factors.jsonl` آمده است.
- **هیچ factor یا رویدادی ساخته نشد.** گام‌های `unverified` (1,358) آن‌هایی‌اند که شاهدِ
  مستقلِ 2026-11-10 ندارند (نمادهای بیرون از 36 نماد مرجع) و صریح برچسب خورده‌اند.

## ۳) تحویل‌شدنی ۳ — نقشهٔ کامل رویدادها

`_audit/phase49-finalization/EVENT-MAPPING-FULL.csv` — **8,280 ردیف**، یک ردیف به‌ازای هر گام:
`symbol, ins_code, asset_id, effective_date, action, ratio, prod_ratio, ref_ratio,
cum_factor_after, class, event_sig, method, confidence, samples, max_field_dev, prov_kind,
validity, source, suppressed_product_events, reason`.
مولد: `_audit/phase49-finalization/build_mapping_csv.py` (ورودی `factors.jsonl`، بدون محاسبهٔ
تازه). بازهٔ تاریخ‌های مؤثر: `2001-10-24` تا `2026-10-25`؛ گام‌های پیش از نخستین کندلِ DB
اثرِ عددی ندارند (در هیچ محاسبهٔ factor برای تاریخ‌های موجود وارد نمی‌شوند) و فقط برای
کامل‌بودنِ نقشه نگه داشته شده‌اند.

## ۴) تحویل‌شدنی ۴ — جدول اعتبار 30 نماد

`_audit/phase49-finalization/VALIDITY-30.csv` (30 ردیف) + `reference-parity-30-final.csv`.

| سنجه | مقدار |
| --- | ---: |
| `PASS_FACTOR` | 29 |
| `PARTIAL_FACTOR` | 1 (ولانا) |
| `FAIL_*` | 0 |
| گام‌های مرجع / دقیق / گم‌شده / اضافهٔ مادی | 503 / 503 / 0 / 0 |
| گام اضافهٔ کوچک (بدون اثر مادی) | 4 |
| بیشینهٔ خطای نسبی factor | 0.198% (ولانا؛ بقیه < 0.1%) |
| reopen/corrected Open | 3,105 ردیف در 11 نماد |

ستون‌های `VALIDITY-30.csv`: سطرها، اولین/آخرین تاریخ DB، پوشش مرجع، تعداد روزهای مرجع،
گام‌ها به‌تفکیک verified/reconstructed/unverified، Openهای اصلاح‌شده، verdict، بیشینهٔ اختلاف
تعدیل‌شده، `status` (`verified` / `reconstructed_verified` / `unverified`) و `notes`.
وضعیت: 29 نماد `verified`، ولانا `reconstructed_verified` (3 گامِ `unverified`).

## ۵) تحویل‌شدنی ۵ — گزارش 7 نماد کوتاه‌تاریخ

`_audit/phase49-finalization/VALIDITY-7.csv` + `reference-parity-7-final.csv`

| نماد | ردیف DB | بازهٔ DB | روز مرجع | گام مرجع/دقیق | verdict |
| --- | ---: | --- | ---: | --- | --- |
| شنفت | 433 | 2024-08-24 .. 2026-10-11 | 3,488 | 26/26 | PASS_FACTOR |
| فافق | 408 | 2024-08-24 .. 2026-10-11 | 1,078 | 6/6 | PASS_FACTOR |
| فخاس | 434 | 2024-08-24 .. 2026-10-11 | 3,465 | 24/24 | PASS_FACTOR |
| فولاژ | 439 | 2024-08-31 .. 2026-10-11 | 3,446 | 25/25 | PASS_FACTOR |
| لخزر | 401 | 2024-08-24 .. 2026-11-08 | 3,240 | 22/22 | PASS_FACTOR |
| مارون | 513 | 2024-08-24 .. 2026-10-11 | 3,243 | 16/16 | PASS_FACTOR |
| ولانا | 1,893 | 2013-11-30 .. 2026-11-09 | 1,892 | 10 گام (7 verified) | PARTIAL_FACTOR |

- **اختلاف تعدیلِ >5% حل شد:** هر 126 گامِ مرجع در نمادهای دارای تاریخ مشترک دقیقاً منطبق‌اند؛
  هیچ گامِ گم‌شده یا مادیِ اضافه نیست. گامِ جعلیِ `2024-08-24` که 6 نماد را خراب می‌کرد حذف شد.
- **اما تاریخچهٔ خامِ این 7 نماد در DB ناقص است:** DB فقط ~400 ردیف از 2024-08 دارد، در حالی
  که مرجع برای همان نمادها 1,078 تا 3,488 روز دارد (مجموع 9,541 روزِ 2010–2019 و 5,804 روزِ
  2020–2024 فقط در مرجع). این نقص با تعدیل قابل رفع نیست و **Backfill آن نیازمند تصمیم مالک**
  دربارهٔ استفاده/انتشار دادهٔ مرجع است. وضعیت پوشش: `INSUFFICIENT_DATA` (نه شکستِ تعدیل).
- آخرین کندل این 7 نماد `2026-10-11` است (نه `2026-11-09`) — کهنگیِ ~1 ماه نیز ثبت می‌شود.

## ۶) تحویل‌شدنی ۶ — ممیزی 9 نماد Open

`OPEN-AUDIT-SUMMARY.json` + `OPEN-CORRECTIONS-BY-SYMBOL.csv` + `open-apply-report.json`

- **پرسش‌ها:** آیا Open تاریخی واقعاً اولین معامله است؟ آیا DB مبنای دیگری (last/closing) را
  نگه می‌دارد؟ آیا FIRST قابل بازیابی است؟ آیا backfill قیمت پایانی قبل را جای Open گذاشته؟
- **یافته:** 11 نماد (9 نمادِ شناخته‌شدهٔ قبلی + خودرو و دالبر) در ردیف‌های `legacy-unknown`
  الگوی «Open = Previous Close» داشتند. مرجع type0 برای همان تاریخ‌ها Open متفاوتی می‌دهد.
- **قاعدهٔ اصلاح (بدون ساخت داده):** فقط ردیفی اصلاح شد که (1) Open مرجع موجود باشد،
  (2) Open مرجع داخل `[low, high]` همان ردیف DB باشد، (3) ردیف از منبع `legacy-unknown` باشد.
  مقدار جایگزین = Open مرجع؛ مبدأ در `raw_history_corrections` ثبت شد.
- **نتیجه:** 3,105 کاندید، 3,105 اعمال، 0 رد، 0 بی‌شاهد؛ 11 نماد؛ `integrity_check=ok`.
  ردیف‌های `rahavard365` (72,222 ردیف) از قبل Openشان با مرجع منطبق بود و دست نخوردند.
- **محدودیت صریح:** برای ردیف‌هایی که مرجع هم `Open = Previous Close` می‌دهد، تغییری انجام
  نشد (شاهدِ تغییر وجود ندارد)؛ این ردیف‌ها «مشکوک ولی تأییدشده» می‌مانند، نه «اصلاح‌شده».

## ۷) تحویل‌شدنی ۷ — پوشش کل دیتابیس

`_audit/phase49-finalization/DB-INVENTORY.md` + `evidence/db-inventory.json`

| سنجه | مقدار |
| --- | ---: |
| ردیف `price_history` | 511,139 |
| تاریخ‌های معاملاتی | 4,056 (2010-01-02 .. 2026-11-09) |
| نمادهای دارای تاریخچه | 6,103 |
| نمادهای `instruments` | 5,941 |
| ابزارهای بدون تاریخچه | 1,306 |
| نمادهای تاریخچه‌دارِ بیرون از `instruments` | 1,468 |
| رویداد Product | 12,829 (4,954 پیش از 2020) |
| نمادهای دارای رویداد Product | 1,087 |
| گام‌های بستهٔ نهایی | 8,280 در 951 نماد (623 پیش از 2020) |
| نمادهای دارای دفتر رسمی | 674 |

| عمق سابقه | نمادها |
| --- | ---: |
| 10y+ | 25 |
| 5-10y | 2 |
| 1-5y | 822 |
| <1y | 5,254 |

| پرچم کیفیت | نمادها |
| --- | ---: |
| بدون شاهد تعدیل | 6,328 |
| شکاف تقویمی | 4,542 |
| `open = prev close` | 3,548 |
| بدون `price_history` | 1,343 |
| تک‌کندل | 685 |
| `zero_fields` | 44 |

**نتیجه:** دادهٔ موجود کامل منتشر می‌شود، اما پوششِ کلِ بازار **کامل نیست** و این گزارش آن را
«Full Database Coverage» نمی‌نامد. فقط 36 نماد (30+7) مرجعِ مستقلِ 2026-11-10 دارند؛ بقیه
برچسب `unverified` می‌گیرند.

## ۸) تحویل‌شدنی ۸ — موتور Go + تست‌های Python

- کدِ تولید: Go (`backend-go/internal/chart/{corrections.go,engine.go}`) با بستهٔ v2 به‌عنوان
  پیش‌فرض؛ Python فقط Backfill/اعتبارسنجی/رگرسیون. مسیر تولید به Python وابسته نیست.
- تغییرهای این مرحله:
  - `adjustment_corrections.py`: `DEFAULT_VERSION = "ra365-phase49-rebuild-full-v2"`.
  - `backend-go/internal/chart/corrections.go`: `FindCorrectionsDir` نسخهٔ v2 را اول جست‌وجو
    می‌کند و به `ra365-r32b-v2` fallback دارد.
  - `backend-go/internal/seed/seed.go`: جدول‌های `adjust_pack_state`, `history_validity`,
    `seed_manifest`, `raw_history_corrections` در `seedOnlyTables` (همراه با بقیهٔ مسیر Seed).
  - `adjust_engine_test.go`: تست قدیمیِ Round 32B عمداً به بستهٔ legacy پین شد تا معنای اصلیِ
    تست (پاریتی با بستهٔ قدیمی) بدون تضعیفِ انتظار حفظ شود.
  - 18 طلاییِ chart فقط بلوک `corrections`شان به نسخهٔ v2 به‌روز شد.
- شواهد سبز: `dev/test_phase49_correction_parity_v1.py` **76/76**،
  `test_ra365_round32b…` **14/14**، `test_ra365_round32c…` **12/12**، B1 **6/6**، B3 **50/50**،
  `go vet ./...` و `go test ./...` سبز.
- **B2 قرمز است** (جزئیات §۱۵)؛ B3 در CI فقط یک بررسیِ cross-platform (FTS vectors) دارد
  و B4 سه بررسیِ طلاییِ کهنه؛ هیچ‌کدام به موتور تعدیل مربوط نیستند.

## ۹) تحویل‌شدنی ۹ — پاریتی خام/تعدیل‌شده با مرجع

مرجع: `rahavard type0/type7`، پنجرهٔ `2010-01-01 .. 2026-11-10`، countback=100000،
سه رزولوشن D/W/M. 30 نماد: 180 سری، 215,182 ردیف؛ 7 نماد: 42 سری، 51,226 ردیف.

| سنجه (30 نماد) | نتیجه |
| --- | --- |
| روزهای مشترک خام | 83,343 |
| روزهای خامِ فقط‌مرجع (2010–2019 / 2020–2024) | 20 / 1 |
| روزهای خامِ فقط‌DB | 965 |
| Open با اختلاف >5% | 25 روز |
| High / Low با اختلاف >5% | 19 / 12 |
| Close با اختلاف >5% | 16 روز |
| Volume با اختلاف >5% | 102 روز |
| گام‌های factor: مرجع/دقیق/گم‌شده/مادیِ اضافه | 503 / 503 / 0 / 0 |
| بیشینهٔ خطای نسبی factor | 0.198% (ولانا) |
| پاریتی Go↔Python (factor/OHLC/events) | 30/30، صفر اختلاف |

| سنجه (7 نماد) | نتیجه |
| --- | --- |
| گام‌های factor: مرجع/دقیق/گم‌شده/مادیِ اضافه | 126 / 126 / 0 / 0 |
| بیشینهٔ خطای نسبی factor | 0.198% (ولانا) |
| روزهای خامِ فقط‌مرجع | 15,345 (نقصِ تاریخچهٔ DB؛ §۵) |

- اختلاف‌های خامِ >5% عمدتاً از **مبنای قیمت** می‌آیند (close آخرین معامله در برابر
  close پایانی) و در گزارش به‌عنوان anomaly جدا ثبت شده‌اند؛ verdict تعدیل بر factor و
  گام‌ها استوار است، نه بر خام. جزئیات روزبه‌روز در `reference-parity-*.json/csv`.
- `adjusted.product.*.max_abs` در JSON بر حسب ریال است (نه درصد)؛ مقایسهٔ نسبی از factor و
  verdict می‌آید.

## ۱۰) تحویل‌شدنی ۱۰ — Seed Candidate نهایی

مسیر: `_audit/phase49-finalization/seed/market.db` (خارج از Git؛
`*.db`/`*.lzma`/`market.db.gz` طبق قواعد ignore).

| سنجه | مقدار |
| --- | --- |
| حجم DB | 270,614,528 بایت |
| SHA-256 DB | `2ee662980ef0dcebbb06b0679f3c0e54282984a060f3b9da62e02f0b389deffc` |
| LZMA | 63,159,112 بایت — `46ff29830b99626c22dff43601c1e6b203ab0340e67727e41992732d14a6e35c` |
| gzip (fast seed) | 101,045,110 بایت — `41e90ffc2431100931bd35b99b9221eaf964cda250d5fa07e066ab374cb2e4ad` |
| `price_history` | 511,139 ردیف / 6,103 نماد |
| بستهٔ تعدیل | v2، 8,280 گام / 951 نماد |
| `raw_history_corrections` | 3,105 ردیف / 11 نماد |
| `history_validity` | 6,103 ردیف |
| وضعیت اعتبار | 35 `verified`، 880 `reconstructed_verified`، 5,188 `unverified` |
| `integrity_check` | `ok` |
| round-trip LZMA | SHA بازشده = SHA خام |

- جدول‌های وضعیتِ جاری (`market_watch`, `order_book`, `instrument_state`, `client_type`, …)
  دست‌نخورده‌اند؛ Seed فقط تاریخچه و متادیتای اعتبار را اضافه می‌کند.
- `seed_manifest` شامل نسخهٔ بسته، SHA مرجع، تعداد ردیف‌ها، تعداد اصلاح Open و provenance است.
- مرجع مستقل/داده‌های خام در Git نیستند (سیاست عدم انتشار سریِ خامِ اشتراکی)؛ SHA و نقشهٔ
  بازتولید ثبت شده است.

## ۱۱) تحویل‌شدنی ۱۱ — نصب/ارتقا (محصول، روی کپی مستقل)

`product-test-report.json` + `evidence/product-clean-evidence.json`

| آزمون | نتیجه |
| --- | --- |
| استخراج Seed از LZMA در پوشهٔ تازه | PASS |
| `chart-db` پس از استخراج | 3,689 کندل، 2010-01-02 .. 2026-11-09 |
| merge روی DB موجود (بدون Seed) | PASS — 511,139 ردیف، 12,829 رویداد |
| حفظ دادهٔ کاربر (ردیف ویرایش‌شده + watchlist) | PASS |
| idempotency (اجرای دوباره = بدون ردیف/فاکتور تکراری) | PASS — 0 duplicate (symbol,date) |
| restart | PASS — همان 511,139 ردیف و 3,689 کندل |
| MA چهار دوره | PASS — 2,000 کندل برای 5/20/50/120 |
| `weekly` / `monthly` | PASS |
| FTS تمام‌تاریخ (فولاد) | PASS — 3,689 بار |
| نصب واقعی/Registry واقعی | **NOT_TOUCHED** (عمداً؛ همهٔ آزمون‌ها روی کپی مستقل) |
| نصب‌کنندهٔ Inno / پوستهٔ Tauri | **NOT_MEASURED محلی** — در CI جاب `desktop delivery` سنجیده می‌شود |

- آزمون‌های merge/restart با Seed نهایی (SHA `2ee66298…`) دوباره اجرا و تأیید شدند.
- آزمونِ clean-extraction روی همان دادهٔ منطقی اجرا شده بود؛ تنها تغییرِ بعدی در DB، دو
  ستونِ SHA در `adjust_pack_state` و timestampها بود (مستقیماً در DB نهایی بازبینی شد) و
  رفتار API را تغییر نمی‌دهد.

## ۱۲) تحویل‌شدنی ۱۲ — SHA-256 همهٔ مصنوعات

`docs/opportunity-center/phase49/ARTIFACTS-SHA256-finalization.txt` (تولید با
`_audit/phase49-finalization/make_final_manifest.py`) — شامل بستهٔ v2، DB/Seed محلی،
شواهد JSON/CSV، مرجع capture (فقط metadata/هش، فایل خام در Git نیست) و باینری آزمون.

## ۱۳) تحویل‌شدنی ۱۳ — دستورات بازتولید

```bash
# 0) بازبینی آرشیوها و بازیابی ایزوله
python tools/phase48/continuation/verify_artifacts.py
python _audit/phase49-finalization/stageA_restore.py

# 1) dumpِ canonical و ساخت بستهٔ کامل
python _audit/phase49-finalization/stageB_inventory.py
python _audit/phase49-finalization/stageB_canonical_dump_parallel.py
python _audit/phase49-finalization/stageB_build_rebuild.py

# 2) پاریتی با مرجع (پس از ضبط/نرمال‌سازی مرجع)
python _audit/phase49-finalization/stageC_reference_parity.py --label 30-final --symbols 30
python _audit/phase49-finalization/stageC_reference_parity.py --label 7-final --symbols 7

# 3) ممیزی و اصلاح Open
python _audit/phase49-finalization/stageD_open_audit.py
python _audit/phase49-finalization/stageD_apply_open_fix.py

# 4) ادغام مرجع در بستهٔ نهایی
python _audit/phase49-finalization/stageD_merge_reference.py

# 5) متادیتای Seed + فشرده‌سازی + گزارش
python _audit/phase49-finalization/stageE_seed_meta.py
python scripts/make_fast_seed.py _audit/phase49-finalization/seed/market.db.lzma \
  _audit/phase49-finalization/seed/market.db.gz --force

# 6) آزمون‌های محصول و پاریتی موتور
python _audit/phase49-finalization/stageE_product_tests.py
python _audit/phase49-finalization/stageE_upgrade_test.py
python _audit/phase49-finalization/stageE_engine_parity.py --pack data/ra365_corrections/ra365-phase49-rebuild-full-v2

# 7) گیت‌ها
python dev/test_phase49_correction_parity_v1.py
python dev/test_chart_fixture_b3.py
python dev/test_mstat_fixture_v1121.py
cd backend-go && go vet ./... && go test ./... && cd ..
```

ضبط مرجع نیازمند ورود دستی مالک به ره‌آورد است؛ اسکریپت‌های `capture_rahavard.mjs` و
`import_capture.py` توکن را برنمی‌گردانند و هیچ Credentialی ذخیره نمی‌کنند.

## ۱۴) تحویل‌شدنی ۱۴ — CI (واقعی)

سه Run واقعی روی همین شاخه ثبت شد؛ همه روی `johnwarchief/BorsTerminal-src`:

| Run | commit | Jobهای سبز | نتیجهٔ کلی | نکته |
| --- | --- | ---: | --- | --- |
| [42824363753](https://github.com/johnwarchief/BorsTerminal-src/actions/runs/42824363753) | `836e47e4` | 9/10 | failure | فقط `python-guards` قرمز؛ نصب `node_modules` (step 5/6) موفق |
| [42827123901](https://github.com/johnwarchief/BorsTerminal-src/actions/runs/42827123901) | `69398bab` | 9/10 | failure | با اصلاح `NO_DB_ISOLATION`، B1 و BORS_DATA_DIR seam از فهرست FAILED حذف شدند |
| [42828239358](https://github.com/johnwarchief/BorsTerminal-src/actions/runs/42828239358) | `b5d8e1e1` | 8/10 | failure | python-guards + یک تستِ flaky در Go Linux؛ Windows/race/delivery سبز |

- **۱۰ Job:** `go backend` (Linux و دو Windows)، `go race detector`،
  `desktop delivery` (BorsTerminal bundle + Tauri shell + installer + Seed merge)،
  `frontend v2` (tsc/vitest/build)، `data integrity guards`، `node --check`،
  `EOL/attributes/repo hygiene`، `python-guards`.
- **اصلاح‌های CI این مرحله:** نصب `frontend` با `npm ci --ignore-scripts` در Jobِ python
  (چون `chart_api_check_v95.py` و `npm_lock_v1040.py` درخت واقعی `node_modules` را
  می‌خوانند)؛ اجرای B0–B4 و seam بدون `BORS_WORK_DIR/BORS_DB` (وگرنه seamِ
  `BORS_DATA_DIR` را می‌شکستند)؛ نگه‌داشتن پک v2 فعال برای B3.
- **پس از این اصلاح‌ها، 24 سوئیت در `python-guards` قرمز ماند** — همگی از merge
  `072a2607` (2026-11-03) به ارث رسیده‌اند و در commit پایه هم قرمز بودند؛
  نمونه‌های بازتولیدشده محلی: `fts_m141_parity_v97` (1 fail)،
  `confidence_engine_v973` (IndexError)، `soft_warnings_v974` (3 fail)،
  `mstat_local_v975` (AttributeError)، B2 (1 fail)، B4 (3 fail). فهرست کامل
  در annotation همان Run آمده است (24 label).
- **B3 در CI: 49/50.** تنها بررسیِ بازمانده `FTS engine vectors equal a fresh oracle run`
  است؛ همین بررسی محلی دقیقاً برابر است، پس اختلاف، cross-platform (Linux/Windows
  float/کتابخانه) است و به تعدیل مربوط نیست. B1 و seam اکنون در CI سبزند.
- **Go Linux flake:** در Run سوم `TestGracefulShutdownWorkerContextCancelled`
  با پیام «worker observed resources already closed» شکست؛ همان Job در Runهای
  اول/دوم و دو Job ویندوز سبز بود. تستِ lifecycle وابسته به زمان است و به
  تغییرهای این مرحله مربوط نیست (فایلش دست نخورده).

| گیت محلی | نتیجه |
| --- | --- |
| `go vet ./...` | PASS (rc=0) |
| `go test -count=1 ./...` | PASS (53 پکیج `ok`، rc=0، صفر FAIL) |
| Phase 4.9 parity | 76/76 PASS |
| Round 32B / 32C | 14/14 / 12/12 PASS |
| B1 board | 6/6 PASS (بدون DB override) |
| B3 chart | 50/50 PASS (بدون DB override) |
| B2 mstat | **1 FAIL** — طلایی‌ها با oracle فعلی یکی نیستند (B1 در §۱۵) |
| Race detector | NOT_MEASURED محلی (نبود gcc/CGO) — Jobِ CI سبز |
| Frontend / Rust | NOT_MEASURED محلی (نبود `node_modules`) — Jobِ CI سبز |

## ۱۵) تحویل‌شدنی ۱۵ — مسائل باز و تصمیم‌های مالک

| # | موضوع | وضعیت | جزئیات / تصمیم لازم |
| --- | --- | --- | --- |
| B1 | `python-guards` در CI: 24 سوئیت قرمزِ ازپیش‌موجود | **FAIL (مستقل از تعدیل)** | merge `072a2607` (2026-11-03) سطح Python را جلوتر از Go/طلایی‌ها/fixtureها برد: B2/B4 طلایی‌های کهنه، B3 فقط FTS-vectorsِ cross-platform (49/50)، و ~20 سوئیتِ m141/confidence/soft-warnings/mstat_local/funnel/watchlist/codal. `m141` و `mstat_local` و `confidence` محلی هم با خطای واقعی (نه محیطی) بازتولید شدند. رفع هرکدام نیازمند پورت/فیکسچر مستقل است؛ خارج از Phase 4.9. دو نقصِ محیطیِ CI (node_modules، DB override) در همین مرحله رفع شد. |
| B2 | پوشش کل دیتابیس ناقص | **PARTIAL / INSUFFICIENT_DATA** | 5,254 نماد <1y، 6,328 نماد بدون شاهد تعدیل، 1,343 ابزار بدون تاریخچه. فقط 36 نماد مرجع مستقل دارند. تصمیم: اولویت‌بندی نمادهای دارای سابقه و سیاست Backfill. |
| B3 | تاریخچهٔ خام 7 نماد کوتاه‌تاریخ | **BLOCKED (نیازمند تصمیم مالک)** | DB فقط از 2024-08 (≈400 ردیف) دارد؛ مرجع 1,078–3,488 روز دارد. تعدیل موجود تأیید شد، اما Backfill/انتشار دادهٔ مرجع مجوز جدا می‌خواهد. |
| B4 | ولانا | **PARTIAL_FACTOR** | بیشینهٔ خطای نسبی factor 0.198% (>0.1% و <1%)، 3 گام `unverified`. بدون آستانه‌شکنی گزارش می‌شود. |
| B5 | Race detector | **NOT_MEASURED محلی** | gcc/CGO محلی نیست؛ در CI جاب `go race detector` باید سبز باشد. |
| B6 | نصب‌کننده/Tauri | **NOT_MEASURED محلی** | همهٔ آزمون‌ها روی کپی؛ نصب/Registry واقعی دست‌نخورده. CI جاب `desktop delivery` مرجع است. |
| B7 | انتشار دادهٔ مرجع | **CONSTRAINT** | captureهای ره‌آورد (37MB/8.6MB) و `bars.ndjson.gz` در Git نیستند؛ فقط هش و metadata ثبت شده. هر انتشار/انتقال نیازمند تصمیم مالک است. |
| B8 | Seed «تولید» در بستهٔ نصبی | **PENDING** | Seed Candidate ساخته و آزموده شد، اما قراردادن آن در بستهٔ انتشار/نصب واقعی انجام نشد (خارج از دامنه/نیازمند تأیید مالک). |

## ۱۶) انطباق با قیود ثابت

| قید | وضعیت | شاهد |
| --- | --- | --- |
| `main` دست‌نخورده | PASS | `origin/main=9a919e82` پیش و پس |
| Merge/Tag/Release نشد | PASS | فقط commit روی شاخهٔ مأموریت |
| شاخه‌های قبلی حفظ شدند | PASS | `mission/phase49-adjustment-chain-closure-2026-11-10=97d6294e` |
| DBهای اصلی/آرشیوهای Phase 4.8 حذف/Overwrite نشدند | PASS | فقط restore به مسیرهای نو (`_audit/phase49-finalization/db/`) |
| آزمون‌ها روی کپی مستقل | PASS | `db/`, `seed/`, `product-test/`, `api-sandbox/` |
| نصب/Registry واقعی دست‌نخورده | PASS | هیچ نصب واقعی اجرا نشد |
| Credential/Cookie/Token/Private Key در Git | PASS | توکن runtime فقط محلی و ignore شد؛ capture توکن برنمی‌گرداند |
| Visibility مخزن | PASS | تغییر نکرد |
| دادهٔ مرجع/حجیم با ثبت منشأ و وضعیت | PASS | captureها ignore؛ SHA و منشأ در manifest/گزارش |
| تصمیم یک‌طرفه دربارهٔ انتشار داده | PASS | B7/B3 به مالک ارجاع شد |
| قواعد FTS و `/fts-screen` و `approval_enabled=false` | PASS | تغییر نکرد |
| Phase 5 / اندیکاتور / AutoTrader / سرخطی | PASS (وارد نشد) | خارج از دامنه |

## ۱۷) حکم

**`PHASE49_PARTIAL_WITH_EXPLICIT_BLOCKERS`**

دلیل: زنجیرهٔ تعدیل برای 36 نمادِ دارای مرجع مستقل با 8,280 گامِ قابل‌ممیزی بسته شد و
پاریتی موتور 30/30 است؛ اما پوشش کل دیتابیس کامل نیست (B2)، 7 نماد تاریخچهٔ خام ناقص دارند
(B3)، ولانا PARTIAL است (B4)، و `python-guards` در CI 24 سوئیتِ قرمزِ ازپیش‌موجود دارد
(B1). هیچ داده، factor یا رویدادی ساختگی وارد نشد و هیچ آستانه‌ای برای سبزشدن تست تغییر نکرد.
