# RA365 Round 17 — Historical Data Promotion, Regression Closure & Full-Universe Parity

**تاریخ:** 2026-10-22  
**شاخه:** `mission/ra365-round15-full-universe-type7-parity-2026-10-21`  
**مبنای Round 16:** `ba2cb953` (کد `0a76ac4b`)  
**دیتابیس عملیاتی:** دست‌نخورده — SHA `fff358a78be74e8d21961251a727116e102df84cea70f87b4dcb7da198667004`

---

## 0. خلاصهٔ اجرایی

| موضوع | وضعیت | شاهد |
|---|---|---|
| Baseline Round 16 از artifact بازبینی شد | `VERIFIED` | `68.8309 / 87.2290 / 68.0025` |
| Backfill کامل PA/SH | `IMPLEMENTED_AND_TESTED` | ۱۰٬۸۳۱ PA، ۳٬۴۹۳ SH، بازهٔ ۲۰۰۸–۲۰۲۶ |
| دادهٔ صندوق | `VERIFIED` (کپی) / `NOT_MEASURED` (عملیاتی) | ۲٬۲۲۲ ردیف در کپی؛ ۰ در عملیاتی |
| migration نسخه‌دار/ایدمپوتنت/برگشت‌پذیر | `IMPLEMENTED_AND_TESTED` | دو اجرا با همان checksum؛ rollback تأیید شد |
| انتشار به دیتابیس عملیاتی | `BLOCKED` (پیش‌شرط عملیاتی) | عملیاتی تغییر نکرد؛ migration آماده است |
| رگرسیون‌های Round 16 | `PARTIAL` | ۳ exact اصلاح شد، ۱ near، ۳ مستقیم و ۱۶ تجمعی باز |
| parser عمومی CODAL (فاراك) | `IMPLEMENTED_AND_TESTED` | ۳۰/۳۰ سند؛ ۲۹ no-cash، ۱ PAID_IN |
| Full-Universe نهایی (کپی promoted) | `VERIFIED` | `69.0243 / 88.0823 / 68.3045` |
| Full gate all-suite | `IMPLEMENTED_AND_TESTED` | ۱۴۲ سوئیت اجرا شد؛ ۳ failure اصلاح و مستقل تأیید شد؛ rerun کامل در جریان |
| build فرانت | `VERIFIED` | `✓ built in 30.63s` |
| دیتابیس عملیاتی | `VERIFIED` بدون تغییر | SHA پیش/پس یکسان |

**نتیجهٔ عددی:** روی کپی promoted (دادهٔ کامل + precedence + candle-closing)،
Factor exact از `68.8309` به **`69.0243`** (+۰٫۱۹۳۴pp)، ±1% از `87.2290` به
**`88.0823`** (+۰٫۸۵۳۳pp) و OHLC از `68.0025` به **`68.3045`** (+۰٫۳۰۲۰pp) رسید.
مهم‌تر از عدد، مسیر واقعی داده اکنون reproducible، keyed، idempotent و قابل‌rollback است.

---

## 1. Git و مبنای کار

- HEAD شروع: `ba2cb953`؛ کد Round 16: `0a76ac4b`.
- working tree شروع پاک؛ هیچ reset/force/بازنویسی انجام نشد.
- `main` تغییر نکرد؛ هیچ push/merge انجام نشد.
- دیتابیس عملیاتی فقط‌خواندنی بود؛ همهٔ اجراها روی کپی ایزوله.
- commitهای این راند در §12.

---

## 2. منابع وب و قراردادهای داده

| منبع | استفاده | اعتبار |
|---|---|---|
| `cdn.tsetmc.com/api/ClosingPrice/GetPriceAdjustByFlow/{flow}/{size}` | منبع اصلی PA؛ با `size=20000` تا ۲۰۰۸ | official-high (پاسخ زنده + parse) |
| `cdn.tsetmc.com/api/Instrument/GetInstrumentShareChangeByFlow/{flow}/{days}` | منبع اصلی SH؛ تا ۲۰۰۸ | official-high |
| `cdn.tsetmc.com/api/ClosingPrice/GetPriceAdjustList/{insCode}` | لیست PA هر ابزار؛ در probe تاریخچهٔ کامل‌تر | official-high (probe) |
| `cdn.tsetmc.com/api/Instrument/GetInstrumentShareChange/{insCode}` | لیست SH هر ابزار | official-high (probe) |
| `cdn.tsetmc.com/api/ClosingPrice/GetInstrumentCalendar/{insCode}` | تقویم روزانه (پایانیِ تعدیل‌شده + حجم) | official-high؛ **برای نسبت استفاده نشد** (خام نیست) |
| `cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList/{insCode}/{top}` | قیمت روزانهٔ زنده | official-high |
| CODAL `Decision.aspx` | ترکیب افزایش سرمایه/نوع رویداد | official-high |
| Rahavard type0/type7 bars | مرجع parity | reference-high؛ هرگز ورودی production نیست |
| `m-ahmadi/exref/tse/urls.txt` | کشف endpointهای per-instrument | community-medium |
| `mazaheriMahdi/fis-agent/docs/domain/tsetmc-api.md` | کشف base/pathهای per-instrument | community-medium |
| `amirziveh/tsetmc-skill` | فهرست سطوح API برای ایجنت‌ها | community-medium |
| `BabakEslami/tse-market-data` | مستندات غیررسمی؛ ادعای «بدون مسیر رسمی PA» | community-low (cross-check منفی) |

ماتریس کامل: `docs/audit/ra365-round17/data-source-matrix.csv`.
هیچ سند جامعه‌محور جایگزین پاسخ رسمی/سند CODAL نشد؛ endpointهای per-instrument پس از
probe زنده و تطبیق با مرجع، «official-high» برچسب گرفتند.

---

## 3. Manifest داده، lineage و checksum

| جدول | منبع | ردیف | کلید یکتا | checksum (SHA-256) |
|---|---|---:|---|---|
| `price_adjust_events` | TSETMC flow (۲۰۰۸–۲۰۲۶) | ۱۰٬۸۳۱ | `(ins_code,d_even)` | `490786e5…` |
| `share_change_events` | TSETMC flow (۲۰۰۸–۲۰۲۶) | ۳٬۴۹۳ | `(ins_code,d_even)` | `bd9eab71…` |
| `fund_profit_events` | پورتال‌های صندوق (Round 8) | ۲٬۲۲۲ | `(ins_code,d_even)` | `36270a60…` |
| `share_type_evidence` | CODAL + ۲ ردیف Round 17 | ۲۹ | `(ins_code,d_even)` | `8bcd60fb…` |

- کپی مرجع: `D:/BorsTerminal-tmp/ra365_round16/market_r16_fullcorp.db` (۲۷ ردیف شاهد).
- دو شاهد جدید Round 17: فاراك (RESERVE_ONLY) و كلر (RESERVE_ONLY)؛ منبع:
  `docs/audit/ra365-round17/codal-evidence-extra.jsonl`.
- snapshotهای CSV: `docs/audit/ra365-round16/tsetmc-price-adjust-full.csv` و
  `tsetmc-share-change-full.csv`.
- manifest migration: `docs/audit/ra365-round17/migration-manifest.json`.

---

## 4. Backfill و migration

### 4.1 مسیر

`tools/ra365_data_migration.py`:

- **plan** بدون نوشتن: شمارش/checksum منبع، بررسی schema و کلید یکتا.
- **apply**: backup منطقی (SQLite backup API) → `BEGIN IMMEDIATE` →
  `INSERT OR REPLACE` با کلید `(ins_code,d_even)` → `PRAGMA integrity_check` → commit.
- کلید یکتا در target بررسی/ساخته می‌شود؛ duplicateهای منبع یا target باعث توقف صریح
  (`SOURCE_DUPLICATE_KEYS` / `TARGET_DUPLICATE_KEYS`) می‌شوند.
- target عملیاتی بدون `--allow-operational` رد می‌شود.
- `--rollback` از baseline تغییرناپذیر برمی‌گرداند؛ هر اجرا یک pre-apply backup زمان‌دار هم دارد.
- manifest شامل version، source/target SHA، counts، checksums، keys و integrity است.

### 4.2 نتایج واقعی روی کپی

| مرحله | PA | SH | Fund | Evidence | Integrity |
|---|---:|---:|---:|---:|---|
| کپی عملیاتی (قبل) | ۱٬۰۰۵ | ۳٬۴۹۰ | ۰ | جدول موجود نیست | ok |
| پس از migration | ۱۰٬۸۳۱ | ۳٬۴۹۳ | ۲٬۲۲۲ | ۲۹ | ok |
| اجرای دوم (idempotent) | ۱۰٬۸۳۱ | ۳٬۴۹۳ | ۲٬۲۲۲ | ۲۹ | ok |
| rollback (روی کپی تست) | ۱٬۰۰۵ | ۳٬۴۹۰ | ۰ | جدول موجود نیست | ok |

- checksumهای PA/SH/Fund پس از دو اجرا دقیقاً یکسان ماندند.
- **عملیاتی تغییر نکرد**؛ SHA پیش/پس `fff358…` است. انتقال به عملیاتی نیازمند
  توقف برنامه/backup/تأیید عملیاتی است و انجام نشد.
- نتیجهٔ parity روی کپی promoted: `69.0243 / 88.0823 / 68.3045` (همان cohort و مخرج).

---

## 5. رگرسیون‌های Round 16: تحلیل و اصلاح

### 5.1 علت اثبات‌شده

برای ۶ گام، R15 دقیق بود و R16 بد شد. الگوی مشترک:

- یک **گسست پایهٔ مشاهده‌شده** روی کندل اثربخش وجود داشت؛
- یک **تغییر سهام** نزدیک همان کندل اعمال می‌شد؛
- موتور، ردیف رسمی DPS را **دوباره** با پایانیِ پس از تغییر سهام محاسبه و اضافه می‌کرد.

نمونه‌ها: خديزل `0.97557×0.82527083` (R16: `0.800806` در برابر مرجع `0.804976`)،
ميدكو `0.985358×0.44134`، وخاور `0.97992×0.6`، ولبهمن `0.66093` در برابر DPS جدا.
همچنین ديران نشان داد قاعدهٔ خام «گسست همیشه برنده است» می‌تواند DPS صحیح را حذف کند.

### 5.2 قاعدهٔ عمومی precedence

در `_merge_official_price_adjust`:

1. اگر گسست همان تاریخ با نسبت سهام هم‌خوان باشد (share-only)، DPS جدا می‌ماند (بورس).
2. اگر تغییر سهام در زنجیرهٔ اعمال‌شده حاضر باشد و گسست share-only نباشد،
   ردیف DPS بازمحاسبه‌شده سرکوب می‌شود و گسست+سهام می‌مانند (خديزل/ميدكو/وخاور).
3. اگر گسست با نسبت منبع رسمی هم‌خوان باشد (≤۰٫۱٪)، DPS رسمی می‌ماند
   (ديران، negative control).
4. اگر گسست نه share-only است و نه منبع رسمی، گسست مشاهده‌شده برنده است و DPS جدا
   اعمال نمی‌شود (ولبهمن).
5. suppression با `included-in-observed-base-gap` گزارش می‌شود، نه خاموش.

### 5.3 وضعیت هر ۲۳ نماد Factor exact

| وضعیت | تعداد | نمادها |
|---|---:|---|
| `FIXED_BY_PRECEDENCE` | ۳ | خديزل (+۲۷۸ exact)، وخاور (+۲۲۶)، ولبهمن (+۷۸۷) |
| `NEAR_IMPROVED_BY_PRECEDENCE` | ۱ | والبر (near +۳۳۶) |
| `DIRECT_STEP_UNRESOLVED` | ۳ | ميدكو (۲۰۲۲-۰۶-۱۲)، كماسه (۲۰۲۱-۰۹-۱۵)، نمرينو (۲۰۲۵-۰۲-۲۳) |
| `CUMULATIVE_UNRESOLVED` | ۱۶ | آردينه، آسيا، بترانس، بشهاب، حآفرين، خگستر، زدشت، ساينا، شگامرن، كاما، كمرجان، لپارس، ولشرق، ومعلم، وهور، چكاپا |

- برای ۱۶ نماد دستهٔ سوم، **هیچ گام exact→bad مستقیمی** در diff گام‌ها پیدا نشد؛
  افت آن‌ها از تغییر نسبت در گام‌هایی است که در R15 هم غیرexact بودند و خطای تجمعی
  را از مرز عبور داده‌اند. این وضعیت در `regression-status.csv` ثبت شده است.
- ۳ نماد `DIRECT_STEP_UNRESOLVED` نیازمند قاعدهٔ دقیق‌تر در Round 18 هستند.
- ۶۲ رگرسیون OHLC: ۷ بهبود، ۵۵ بدون تغییر، **۰ بدترشده**؛ جزئیات در
  `regression-status-ohlc.csv`.
- trade-off ثبت‌شده: خديزل exact +۲۷۸ ولی func −۵۲۹؛ ولبهمن exact +۷۸۷ و func +۲٬۹۹۹؛
  وخاور exact +۲۲۶ و func +۴٬۱۲۹. هیچ‌کدام پنهان نشده‌اند.

---

## 6. تغییرات production

| فایل | تغییر |
|---|---|
| `api/chart.py` | قاعدهٔ precedence گسست/سهام/DPS در `_merge_official_price_adjust`؛ حفظ کامل candle-closing Round 16 |
| `tools/codal_share_type.py` | parser عمومی: مبلغ پس از برچسب، total increase، واحد، paid-cash مشتق‌شده، stage paid-cash، incomplete→UNPARSED |
| `tools/ra365_data_migration.py` | migration نسخه‌دار، keyed، idempotent، transactional، rollback |
| `dev/test_round17_gap_precedence_v1.py` | ۸ تست با ۶ نمونهٔ واقعی + ديران + بورس |
| `dev/test_round17_codal_parser_v1.py` | ۸ تست با سند واقعی فاراك و فرمت‌های قدیم/جدید/روایتی |
| `dev/test_round17_migration_v1.py` | ۹ تست idempotency/rollback/refusal/integrity |
| `dev/run_all_tests.py` | ثبت سه سوئیت جدید |

هیچ شرط/ضریب مخصوص نماد اضافه نشد؛ `P=2620` و نرخ ۳٫۷۵٪ وارد فرمول نشدند.

---

## 7. Before/After

| مرحله | Factor exact | Factor ±1% | OHLC | نرمال exact | نرمال ±1% |
|---|---:|---:|---:|---:|---:|
| R15 final (۲۷ ردیفی) | 49.5933 | 85.4817 | 50.2502 | 41.5983 | 82.4325 |
| R16 code-only (۲۷ ردیفی) | 51.4664 | 85.7996 | 52.2521 | 41.6970 | 82.3603 |
| R16 data+code | 68.8309 | 87.2290 | 68.0025 | 60.0912 | 83.5676 |
| R17 precedence (full, ۲۷ شاهد) | **68.9256** | **88.0823** | **68.2073** | **60.2008** | **85.0035** |
| **R17 promoted (۲۹ شاهد)** | **69.0243** | **88.0823** | **68.3045** | **60.2057** | **85.0916** |

تفکیک اثر:

| اثر | exact | ±1% | OHLC | نرمال exact |
|---|---:|---:|---:|---:|
| Code: precedence (R16→R17) | +0.0947pp | +0.8533pp | +0.2048pp | +0.1096pp |
| Evidence: فاراك+كلر | +0.0987pp | 0 | +0.0972pp | +0.0049pp |
| **کل R17 vs R16** | **+0.1934pp** (+۲٬۲۹۸ تاریخ) | **+0.8533pp** (+۱۰٬۱۳۶) | **+0.3020pp** (+۱۴٬۳۴۸ فیلد) | **+0.1145pp** (+۱٬۳۶۱) |

- Step mismatch: ۱۶۷ → **۱۴۸**؛ REF_ONLY: ۱۴۶ → **۱۳۹**؛ PROD_ONLY: ۱۸۴ → **۱۷۷**.
- اثر داده در R16 (با کد اصلاح‌شدهٔ candle-closing) همان `+17.3645pp` exact است؛
  این راند آن را به یک مسیر migration واقعی تبدیل کرد.
- هیچ denominator یا تعریفی تغییر نکرد؛ universe=۲٬۵۹۵ و مخرج‌ها ۱٬۱۸۷٬۹۴۵ / ۴٬۷۵۱٬۷۸۰.

---

## 8. پوشش تاریخی باقی‌مانده

### 8.1 ۲۸۰ گام بدون PA خام

| وضعیت | تعداد | توضیح |
|---|---:|---|
| `FOUND_AND_VALIDATED` | ۳۳ | ۵۳ گام با PA مؤثر؛ بخشی با DPS پایانیِ کندل exact/near؛ چند share+شاهد |
| `BLOCKED` | ۱۸۴ | ۱۶۴ share مؤثر (اکثراً بدون شاهد no-cash یا نسبت دور)؛ ۲۰ PA با فرمول دور |
| `MISSING_AT_SOURCE` | ۶۳ | هیچ PA/SH mapping به کندل اثربخش ندارد |

- ۵۳ گام با PA **مؤثر** (per-instrument/date mapping) پیدا شد، نه با فاصلهٔ خام؛
  این نشان می‌دهد بخشی از «no-PA» در واقع date-mapping بود.
- ۲۸۰ ردیف در `docs/audit/ra365-round17/no_pa_status.csv` با status/source/err ثبت شده‌اند.
- خوشهٔ اصلی باقی‌مانده، همان `BLOCKED_TYPE_EVIDENCE` است: share-only بدون سند no-cash.

### 8.2 Far

تعریف: خطای نسبی فرمول candle-closing نسبت به مرجع >۱٪ در dataset مرجع.

| دوره | far | وضعیت |
|---|---:|---|
| پیش از ۲۰۲۴ | ۶۸ | ۹ share-identity (`FOUND_AND_VALIDATED`)، ۳۵ share نزدیک با نسبت دور، ۲۴ بدون share (`BLOCKED`) |
| پس از ۲۰۲۴ | ۱۵ از ۳۶۴ PA-covered | ۳۴۵ exact (۹۴٫۸٪)؛ far باقی‌مانده multi-event/بدون share |

فایل: `docs/audit/ra365-round17/far_pre2024_status.csv`.

---

## 9. CODAL

| وضعیت | تعداد |
|---|---:|
| `COMPLETE` | **۳۰/۳۰** |
| `RESERVE_ONLY` | ۲۷ |
| `COMBINED_CLAIMS` | ۲ |
| `PAID_IN` | ۱ (وپاسار، ۵۰٬۰۰۰ میلیارد ریال stage) |
| `UNPARSED` | ۰ |

- فاراك: cache قبلی یک صفحهٔ CAPTCHA بود؛ یک retry محترمانه بدنهٔ واقعی را آورد.
  parser عمومی (مبلغ پس از برچسب + total + واحد + paid-cash مشتق‌شده) آن را
  `RESERVE_ONLY` با paid_cash=0 و revaluation=8,064,632 (میلیون ریال) خواند.
- regression-check روی ۳۰ بدنهٔ cache: **۰ mismatch**؛ فقط فاراك از UNPARSED به
  RESERVE_ONLY تغییر کرد (اصلاح مورد انتظار) و وپاسار PAID_IN ماند.
- checkpoint: `docs/audit/ra365-round17/codal-checkpoint.csv`.

---

## 10. Full gate و build

- `frontend/node_modules` از مسیر استاندارد (worktree هم‌نسخه) تکمیل شد؛
  `klinecharts` و ۲۵۷ بسته موجودند.
- `npm run build`: `✓ built in 30.63s`.
- Full gate روی کپی promoted (DB کامل، ۲۹ شاهد) **کامل اجرا شد**:
  `142 suite counted, 42 silent (exit-only), 1 skipped`؛
  `PROTECTED_DB_UNCHANGED` تأیید شد.
- سه شکست، ریشه و اصلاح:
  1. **نقشهٔ FTS**: ارجاع‌های `_fts_analyze_candles:4691`، `_fts_jet_setup:3669`،
     `_fts_analyze_symbol:5099` با سطرهای جدید (۴۸۴۶/۳۸۲۴/۵۲۵۴) هم‌خوان نبودند؛
     نقشه اصلاح شد و گارد **11/11** شد.
  2. **scan_symbol == bulk_scan**: علت، نبود `fts_thresholds.json` در کنار snapshot
     کپی‌شده بود (gate فقط sidecarهای کنار DB را کپی می‌کند)؛ sidecarها
     (`fts_thresholds.json`, `user.db`, `codal_control.json`) به پوشهٔ snapshot کپی شدند؛
     پس از آن **7/7** با ۹۲۲ نماد و **۰ واگرایی**.
  3. **ledger dedupe**: mock قدیمی تست، امضای `_official_price_adjust_events` را
     بدون `closings` می‌ساخت؛ به امضای R16 به‌روز شد و سوئیت **7/7** شد.
- هر سه سوئیت پس از اصلاح، مستقل سبز شدند (11/11، 7/7، 7/7).
- اجرای دوبارهٔ all-suite با همین snapshot و dependencyها آغاز شد؛
  log: `D:/BorsTerminal-tmp/ra365_round17/full_gate_r17_final.log`.
  تا لحظهٔ تنظیم این به‌روزرسانی، وضعیت «یک اجرای کاملاً سبز» `NOT_MEASURED` است.
- skip تنها سوئیتِ `market.db.lzma` است (فایل در snapshot نیست).

### تست‌ها

| سوئیت | نتیجه |
|---|---|
| `test_round17_gap_precedence_v1.py` | 8/8 |
| `test_round17_codal_parser_v1.py` | 8/8 |
| `test_round17_migration_v1.py` | 9/9 |
| `test_round16_candle_closing_dps_v1.py` | 27/27 |
| `test_round15_dps_source_duplicate_v1.py` | 21/21 |
| `test_dps_formula_v1.py` | 61/61 |
| `test_round14_official_events_v1.py` | 17/17 |
| `test_adjustment_engine_v1.py` | 44/44 |
| `py_compile` | OK |

---

## 11. سلامت دیتابیس و rollback

- دیتابیس عملیاتی: SHA `fff358a78be74e8d21961251a727116e102df84cea70f87b4dcb7da198667004`
  پیش/پس یکسان؛ هیچ جدول/ردیفی نوشته نشد.
- کپی migrated: `PRAGMA integrity_check=ok`؛ کلیدهای یکتا `(ins_code,d_even)`.
- rollback آزمایشی: بازگشت به PA=۱٬۰۰۵، SH=۳٬۴۹۰، Fund=۰ و نبود جدول evidence.
- migration برای عملیاتی **آماده** است اما اجرا نشد (نیازمند توقف برنامه/backup/تأیید).

---

## 12. فایل‌ها، commitها و موارد باقی‌مانده

### 12.1 commitها

- `e1131541` — precedence + parser + migration + تست‌ها + artifactها
- `18055a78` — گزارش Round 17
- `e521b2ad` — اصلاح gate (نقشهٔ FTS، sidecar، mock تست)
- به‌روزرسانی شاهد gate — همین commit

### 12.2 artifactها

| فایل | نقش |
|---|---|
| `docs/audit/ra365-round17/parity-stages.csv` | پنج مرحلهٔ before/after |
| `docs/audit/ra365-round17/migration-manifest.json` | version/keys/counts/checksums/backup |
| `docs/audit/ra365-round17/data-source-matrix.csv` | منبع→endpoint→coverage→confidence→usage |
| `docs/audit/ra365-round17/regression-status.csv` | ۲۳ رگرسیون exact با status |
| `docs/audit/ra365-round17/regression-status-ohlc.csv` | ۶۲ رگرسیون OHLC |
| `docs/audit/ra365-round17/no_pa_status.csv` | ۲۸۰ گام بدون PA |
| `docs/audit/ra365-round17/far_pre2024_status.csv` | ۶۸ گام far پیش از ۲۰۲۴ |
| `docs/audit/ra365-round17/parity-summary-promoted-final.json` | نتیجهٔ نهایی |

### 12.3 `BLOCKED` / `NOT_MEASURED`

| مورد | وضعیت | دلیل |
|---|---|---|
| انتشار migration به عملیاتی | `BLOCKED` | توقف برنامه/backup/تأیید عملیاتی فراهم نیست |
| ۳ رگرسیون مستقیم (ميدكو/كماسه/نمرينو) | `BLOCKED` | نیازمند قاعدهٔ classification دقیق‌تر |
| ۱۶ رگرسیون تجمعی | `NOT_MEASURED` | علت مستقیم گام پیدا نشد؛ خطای تجمعی |
| ۱۸۴ گام no-cash بدون شاهد | `BLOCKED` | خوشهٔ `BLOCKED_TYPE_EVIDENCE` |
| ۶۳ گام بدون منبع | `MISSING_AT_SOURCE` | no PA/SH maps to the step |
| ۵۹ far پیش از ۲۰۲۴ | `BLOCKED` | ۳۵ share دور، ۲۴ بدون share |
| ۱۵ far پس از ۲۰۲۴ | `NOT_MEASURED` | multi-event؛ نیازمند Round 18 |
| Full gate all-suite کاملاً سبز | `NOT_MEASURED` | اجرا کامل نشد؛ بخش‌های ابتدایی سبز |
| فروي (`P`) | `BLOCKED` | `BLOCKED_P_DEFINITION` |
| حخزر (net-DPS) | `BLOCKED` | `UNVERIFIED_NET_DPS` |

**هیچ ضریب/قیمت/رویداد حدسی برای بهبود مصنوعی استفاده نشد.** مخرج‌ها ثابت ماندند و
دادهٔ جدید فقط از مسیر migration keyed/قابل‌rollback وارد کپی شد.
