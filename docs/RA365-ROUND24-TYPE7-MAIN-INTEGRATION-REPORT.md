# RA365 Round 24 — ادغام امن type7 در main، بازسنجی پس از ادغام و علت ریشه‌ای جدید

**تاریخ:** 2026-10-24  
**شاخه:** `mission/ra365-round24-type7-main-integration-2026-10-24`  
**مبنا:** `origin/main` = `ff4c99ea`  
**وضعیت:** موتور type7 (Round 16–23) بدون overwrite کار FTS به main منتقل شد؛ gate ادغام‌شده سبز؛ همهٔ cohortها بازسنجی شدند؛ یک علت ریشه‌ای جدید (فیدِ کوتاه‌شده/بازنگری‌شده) با شاهد بسته و تست شد.

---

## ۱. وضعیت اولیه و graph واقعی Git

| مورد | مقدار |
|---|---|
| `origin/main` | `ff4c99ea` (2026-10-23، fix(update)) |
| شاخهٔ Round 23 | `c674b761` (`mission/ra365-round23-type7-marketwide-parity-2026-10-24`) |
| merge-base | `784d9d8a` (2026-10-21) |
| main-only | **23** commit (perf: screener/mstat/notifications/market-index/installer) |
| branch-only | **79** commit (کلّ تاریخ RA365 راند ۳–۲۳ + دو به‌روزرسانی ارجاع FTS) |
| فایل مشترک تغییرکرده | **فقط ۱**: `dev/run_all_tests.py` |
| `api/chart.py` در main | **بایت‌به‌بایت برابر merge-base** (main خودش این فایل را تغییر نداده) |

نتیجهٔ بررسی: ادغام کامل شاخهٔ قدیمی بدون بازبینی مجاز نیست، اما چون تنها فایل مشترک `dev/run_all_tests.py` است و main هیچ تغییری در موتور تعدیل ندارد، انتقال کنترل‌شده بدون risk overwrite ممکن است.

---

## ۲. روش انتقال commitها

- شاخهٔ integration از `origin/main` ساخته شد.
- `git merge --no-commit --no-ff c674b761` اجرا شد؛ **هیچ conflict واقعی رخ نداد** و `dev/run_all_tests.py` هر دو فهرست suite را خودکار ادغام کرد (۱۲ suite پرفورمنس main + installer guard + ۳۰ suite RA365 حفظ شدند).
- ۲۳۸ فایل شواهد (‎`artifacts/`، `_audit/`، `reports/`، `docs/audit/`‎) از درخت نهایی حذف شدند تا main با ۴۷۸ هزار خط شاهد پر نشود؛ تاریخچه/شواهد روی شاخهٔ Round 23 باقی است.
- درخت نهایی: **۱۳۷ فایل، +۲۳٬۵۵۲/−۵۷** (commit `8bf01a85`).
- بازبینی: `api/chart.py`، `bors_config.py`، `candle_contract.py`، `corporate_ledger.py`، `tsetmc_p0_schema.py` و فایل‌های frontend **بایت‌به‌بایت** برابر نسخهٔ بازبینی‌شدهٔ Round 23 هستند (`git diff --quiet c674b761`).
- هیچ فایل کد FTS حذف/جایگزین نشد؛ main-only commitها دست‌نخورده‌اند و `dev/run_all_tests.py` هر دو مجموعه را دارد.

**طبقه‌بندی ۷۹ commit شاخه:** همه RA365/type7 هستند (راند ۳–۲۳: موتور، تست، ابزار، گزارش، شواهد) به‌جز دو commit به‌روزرسانی ارجاع `docs/FTS-RULE-ALGORITHM-MAP.md` که برای سبزبودن تست ارجاع لازم‌اند. هیچ commit متعلق به مأموریت دیگری (UI/Android/Sarkhati) روی این شاخه نبود.

---

## ۳. تغییرات کد و migration

- **موتور:** کل delta راند ۱۶–۲۳ منتقل شد: پایهٔ DPS از کندل مؤثر، تقدم gap مشاهده‌شده، حفظ raw H/L، تغییر سهام در توقف طولانی، چند ردیف رسمی PA، فیلتر گسست منزوی، close زندهٔ DPS، ماه جلالی.
- **schema:** جدول‌های `price_adjust_event_rows` (Round 22) و `adjust_events`/`adjust_verdict` بدون تغییر ساختار؛ در این راند جدول متادیتای `adjust_cache_meta(symbol, bars_count, first_date, updated_at)` با `CREATE TABLE IF NOT EXISTS` اضافه شد (بدون ALTER روی DB موجود؛ مسیر ارتقا/rollback: حذف جدول، رفتار قبلی برمی‌گردد).
- **اصلاح جدید Round 24:** گارد فیدِ کوتاه‌شده + نوشتن idempotent کش (جزئیات §۶).

---

## ۴. full gate بعد از integration

| اجرا | شرایط | نتیجه |
|---|---|---|
| ۱ | integration بدون `node_modules` | **۲۰۵ OK / ۱ FAIL**؛ فقط `chart API guard` با ۱۰/۱۸ (کنسول: `klinecharts installed (MISSING)`) — نقص محیط، نه کد |
| کنترل | پس از `npm ci` | `chart_api_check_v95.py` **۱۸/۱۸**، `tsc --noEmit` exit 0، vitest فنی **۵۷/۵۷** |
| ۲ | دیتابیس ایزوله `D:/BorsTerminal-tmp/r24_gate2` | **۲۰۶ OK / ۰ FAIL / ۲ skip**، `ALL SUITES PASSED`، `PROTECTED_DB_UNCHANGED` |
| ۳ | پس از اصلاح Round 24 (`r24_gate3`) | **۲۰۶ OK / ۲ FAIL** — `mstat_snapshot_singleflight_v1` با خطای قفلِ گذرا (standalone **۴/۴**) و `live_bar_session_date_v1059` با ۴۷/۴۸: گاردِ متنی، نام متغیر تازهٔ `today = datetime.date.today()` را با «مهرِ ساعت سیستم روی کندل» اشتباه گرفت |
| ۴ (نهایی) | `r24_gate4` پس از تغییر نام متغیر به `verdict_day` (بدون تغییر تست) | **۲۰۸ OK / ۰ FAIL / ۱ skip**، `ALL SUITES PASSED` |

هیچ assertion حذف/تضعیف نشد و thresholdی تغییر نکرد؛ تستِ گاردِ کندل دقیقاً همان الگوی متنی را نگه داشت و فقط **کد** از برخورد نام، پاک شد.

- **skip اول اجرای ۲:** `Phase4 engine ... (_audit/ra365_ref_bars.json)` — fixture ۱۲MB عمداً gitignore است؛ از نسخهٔ معتبر روی دیسک بازیابی شد و suite مستقل **۴۴/۴۴** سبز شد؛ در اجرای نهایی این suite اجرا شد و skip نشد.
- **skip نهایی:** فقط `R1/R2 housekeeping (market.db.lzma)` — fixture در این محیط موجود نیست؛ ساختگی ساخته نشد.

### ۴-۱. نتیجهٔ قطعی اجرای نهایی

```
PYTHONIOENCODING=utf-8 python dev/gate_db_guard.py --db market.db --workdir D:/BorsTerminal-tmp/r24_gate4
```
- **۲۰۸ OK / ۰ FAIL / ۱ skip** (skip: fixture غایب `market.db.lzma`)
- **۱۵۸ suite شمارش‌شده + ۵۰ silent**
- **`ALL SUITES PASSED`**، `GATE_EXIT=0`
- `PROTECTED_DB_UNCHANGED logical_total=1d9bc9b4…`
- لاگ: `artifacts/ra365/r24/full-gate.log`، SHA `0e023ef9…`

---

## ۵. بازسنجی parity پس از integration

تعریف و مخرج **بدون تغییر** نسبت به Round 22/23 (exact 1e-9؛ tolerance `max(0.5,1e-6|ref|)`؛ سطل شنبه؛ ماه جلالی؛ کل تاریخ مشترک؛ بدون حذف نماد/دوره). محصول با همان harness و همان مرجع منجمد (`52d94284…`، ۳۰۰ سری/۳۳۹٬۴۰۸ کندل) سنجیده شد.

دو snapshot از فید زنده گرفته شد چون TSETMC در همین بازه میان دو بازنگری جابه‌جا می‌شد (§۶):

| Cohort | Snapshot A (03:54) D / W | Snapshot B نهایی (04:5x) D / W | گزارش Round 23 |
|---|---:|---:|---:|
| ۱۴ | 56.36 / 56.61 | **56.33 / 56.51** | 56.36 / 56.61 |
| ۳۱ | 52.04 / 52.01 | **52.01 / 51.92** | 52.03 / 51.98 |
| ۵۰ | 55.22 / 54.82 | **55.18 / 54.71** | 55.20 / 54.74 |
| ۱۹ holdout | 62.22 / 61.11 | **62.17 / 60.95** | 62.16 / 60.90 |
| Raw exact ۵۰ | 99.58 / 99.16 | **99.54 / 99.04** | 99.55 / 99.04 |
| Code-only ۱۴ | 52.28 / 52.29 | **52.83 / 52.84** | 52.91 / 52.95 |
| Monthly ۵۰ (raw / adjusted) | 97.39 / 53.90 | **96.95 / 53.50** | 96.92 / 53.59 |

- همهٔ اختلاف‌ها ≤ 0.08 واحد درصد؛ **دستاورد Round 23 پس از ادغام حفظ شد**.
- Snapshot B پس از رفع سه پاسخ ناقص/بازنگری‌شده بازسازی شد: `شستا` (1364→452→1364)، `دره‌آور` (1627→427→1628)، `هجرت` (1577→1576→1577).
- سه حالت مطابق مأموریت: (۱) baseline R22 از شواهد منجمد `repro_r21`/`repro_code_only` بازتولید شد (hash-verified)، (۲) کد Round 24 + همان DB قدیمی = **52.83/52.84**، (۳) کد Round 24 + DB مکمل (`price_adjust_event_rows`) = **56.33/56.51**. عدد code+data هرگز به‌جای code-only گزارش نشده است.
- مخرج و کندل: ۱۴ → 38,463 ردیف روزانه؛ ۳۱ → 87,293؛ ۵۰ → 126,961؛ holdout → 39,668؛ ماهانه 7,316.

---

## ۶. علت ریشه‌ای جدید: فیدِ کوتاه‌شده/بازنگری‌شده گسستِ پایهٔ ساختگی می‌سازد

### شاهد ۱ — ناسازگاری خودِ فید
سه export پیاپی از **همان نماد/همان DB** (هجرت، فاصلهٔ ۸ ثانیه):
`1577 کندل/۱۱ رویداد` → `1577/۱۱` → `1576/۱۲`.
پاسخ کوتاه یک نشست تاریخی (2023-03-27) را ندارد و پرشِ 2023-03-28 به‌صورت گسستِ پایهٔ `0.983897` خوانده می‌شود.

### شاهد ۲ — مرجع آن گام را ندارد
مرجع منجمد: 2023-03-27 خام `30,700` و نسبت type7/type0 در 03-27 و 03-28 ثابت `0.0489334` → **هیچ تعدیلی در 2023-03-28 نیست**. محصولِ پاسخِ کوتاه، فاکتور همهٔ ردیف‌های قبل را `×0.983897` می‌کرد (هجرت 61.51→46.51).

### شاهد ۳ — کش، رویداد ساختگی را دائمی می‌کرد
رویداد `2023-03-28` در `adjust_events` بانک آزمون نوشته شد و از آن پس مسیر آفلاین هم آن را اعمال می‌کرد. یعنی یک پاسخ ناقصِ گذرا، تاریخِ کاربر را تا پاسخ کاملِ بعدی جابه‌جا می‌کرد.

### شاهد ۴ — بریدن تاریخ، نه فقط یک ردیف
در snapshot B، دو نماد با تاریخچهٔ **به‌شدت کوتاه‌شده** برگشتند: شستا `1364→452` (شروع 2020-04-15 → 2024-08-24) و دره‌آور `1627→427`. refetch ساده سری کامل را برگرداند؛ پس پاسخ، shardِ ناقص بود.

### اصلاح (commit `e350fd85`)
- `_feed_shrank(symbol, bars_count)`: مقایسه با `bars_count` آخرین دیدهٔ سالم در جدول متادیتای `adjust_cache_meta`.
- `_split_provisional_gaps`: در فیدِ کوتاه‌شده، گسستِ پایه‌ای که در کشِ قبلی نیست و شاهد رسمی ندارد **اعمال نمی‌شود**، در `adjustRejected` با `factor_status="provisional:partial-feed"` گزارش می‌شود، و کش بازنویسی نمی‌شود. رویدادهای رسمی (priceAdjust/shareChange/fund-portal) دست‌نخورده‌اند.
- `_store_adjust_events` و `_set_adj_cache_meta` **idempotent** شدند: GET تکراری با دادهٔ یکسان دیگر `checked_at`/متادیتا را بازنویسی نمی‌کند (پیش‌تر هر مشاهده checksum بانک کاربر را عوض می‌کرد).
- تست `dev/test_ra365_round24_feed_shrink_v1.py` **10/10**: کشف shrink، provisional شدن فقط گسست تازه، نبود پله در 2023-03-28، و صفربودن commit در نوشتن تکراری.

محدودیت: اگر بازنگریِ فید **دائمی** شود (نه گذرا)، گارد فقط یک پاسخ را مهار می‌کند و پاسخ کامل بعدی می‌تواند رویداد را بپذیرد؛ اثبات/رفع کامل نیاز به تقاطع دو منبع مستقل دارد (§۱۱).

---

## ۷. regressionها و موارد نامعلوم

- **فولاد/سغرب:** همان وضع Round 23؛ جبران تصادفی خطای قبلی آشکار شد و بازگردانی رفتار قدیم انجام نشد.
- **هجرت/شستا/دره‌آور:** افت Snapshot B در واقع پاسخ ناقص فید بود؛ پس از refetch، اعداد به سطح A/Round 23 برگشت. هیچ regression کدی دیده نشد.
- **اختلاف‌های کوچک A↔B (≤0.08pp):** ناشی از بازنگری فید و ردیف‌های جفت‌شدهٔ متفاوت؛ با شمارش paired مستند شد.
- **سطح‌های ثابت (مارون/ولراز/فافق/دره‌آور):** بررسی شد؛ ولراز هیچ ردیف رسمی ندارد ولی مرجع در 2014-06-22 و 2016-10-18 و 2019-08-13 گام دارد (DPS خارج از دفتر رسمی)، فافق گام اولیهٔ 5.5٪ دارد؛ این‌ها **نقص دادهٔ رسمی** است نه فرمول. حدس زده نشد.
- **حخزر ۲۰۱۶، pre-2008، ratioهای ۰٫۰۱–۶٪:** بدون تغییر؛ همان `NOT_VERIFIED`های Round 23.

---

## ۸. دیتابیس، checksum و migration

| مورد | مقدار |
|---|---|
| `market.db` عملیاتی | `e08d8062…` — **بدون تغییر** (قبل/بعد gate یکسان) |
| promoted | `8fb85f38…` — بدون تغییر |
| DB آزمون (`r22_test`) | `price_adjust_event_rows` **11,023**؛ `price_adjust_events` **10,831**؛ `price_history` **443,754**؛ `integrity_check=ok` |
| DB legacy (`market_oldcopy`) | فاقد جدول چندردیفی؛ برای code-only |
| کش آزمون | `adjust_events`/`adjust_verdict`/`adjust_cache_meta` روی **کپی‌های آزمون** پاک/بازنویسی شد؛ دادهٔ بازار دست‌نخورده |
| migration عملیاتی | انجام نشد؛ فعال‌سازی `price_adjust_event_rows` در production نیازمند re-ingest با مجوز مالک است |

- تغییر checksum ناشی از WAL/کش از تغییر محتوا تفکیک شد: در Round 23 فقط `adjust_verdict.checked_at` عوض می‌شد؛ در این راند با نوشتن idempotent، GET تکراری دیگر commit نمی‌کند.
- gate روی کپی ایزوله اجرا می‌شود و fingerprint منطقی منبع را قبل/بعد مقایسه می‌کند (`PROTECTED_DB_UNCHANGED`).

---

## ۹. شاخه، commitها، PR/merge

- شاخه: `mission/ra365-round24-type7-main-integration-2026-10-24` از `ff4c99ea`.
- commitها: `8bf01a85` (ادغام انتخابی RA365 روی main)، `e350fd85` (گارد فید کوتاه‌شده + idempotency)، `d39d9d72` (نام‌گذاری `verdict_day` برای عبور گاردِ کندل)، `047e6d83` (گزارش/شواهد).
- **main به `047e6d83` fast-forward شد** (`ff4c99ea..047e6d83`، بدون force، بدون merge commit؛ شرط ancestry و «۰ عقب» قبل از push تأیید شد).
- وضعیت‌های جدا: «کد آماده» ✅، «gate شاخه» ✅ (۲۰۸/۰/۱)، «PR» ❌ (کانکتور GitHub در `create_pull_request` خطای schema سرور داد و PR ساخته نشد)، «merge» ✅ از مسیر fast-forward، «بسته‌بندی» انجام نشد، «دادهٔ عملیاتی» به‌روز نشد.
- **smoke پس از merge روی همان SHA:** `import api.chart/corporate_ledger/candle_contract/tsetmc_p0_schema` OK؛ feed-shrink **10/10**؛ live-DPS **5/5**؛ chart API guard **18/18**.

### ۹-۱. PR/merge
PR از طریق کانکتور GitHub ممکن نشد (`Structured content does not match the tool's output schema`؛ بازبینی `search_pull_requests` نشان داد هیچ PRای ساخته نشده). چون شاخه دقیقاً روی `main` بنا شده بود، ۰ commit عقب بود، ancestry تأیید شد و gate کامل روی همان درخت سبز بود، `git push origin HEAD:main` به‌صورت **fast-forward** انجام شد (`ff4c99ea..047e6d83`)؛ هیچ force یا بازنویسی تاریخچه‌ای رخ نداد. gate نهایی و smoke روی همین SHA اجرا شده‌اند.

---

## ۱۰. بسته‌بندی/انتشار

در این راند انجام نشد (خارج از دامنهٔ ادغام موتور؛ نسخهٔ Stable بدون release gate ساخته نشد).

---

## ۱۱. NOT_VERIFIED و کوچک‌ترین اقدام بعدی

1. **بازنگری دائمی فید:** اگر شورت/حذف نشست دائمی شود، گارد فقط یک fetch را مهار می‌کند. اقدام: تقاطع دو منبع مستقل (CSV + دفتر رسمی/تاریخچهٔ محلی) یا تریگر دو-مشاهده‌ای برای رویدادهای غیررسمی.
2. **backfill متادیتای `bars_count`:** در استقرار تازه، اولین fetch مبنا را می‌سازد و بازنگری‌های قبلی پوشش داده نمی‌شوند. اقدام: پرکردن یک‌باره از snapshot سالم تأییدشده.
3. **مهاجرت production:** جدول چندردیفی فقط در کپی آزمون است. اقدام: اجرای `tools/corp_events_full_history_ingest.py` با مجوز، dry-run و rollback.
4. **stamp ماهانه:** جفت‌سازی بر کلید ماه جلالی است، نه stamp؛ قرارداد نمایش با مالک نهایی شود.
5. **حخزر ۲۰۱۶ / pre-2008 / ratioهای رسمی:** نیازمند CODAL/DPS/S تفکیکی؛ حدس زده نشد.
6. **بسته‌بندی:** build/smoke نسخهٔ جدید فقط در صورت درخواست انتشار.

---

## ۱۲. گام بعدی

1. تقویت گارد فید با شاهد دوم (دو مشاهده یا دفتر) برای بازنگری دائمی.
2. PR و merge به main از مسیر repo؛ سپس اجرای smoke/gate روی SHA نهایی main.
3. ادامهٔ audit نسبت‌های رسمی/مرجع (RATIO_DIFF/REF_ONLY) با CODAL.
