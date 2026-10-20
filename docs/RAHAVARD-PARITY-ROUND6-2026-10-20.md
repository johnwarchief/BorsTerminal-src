# Rahavard 100% Parity — گزارش دور ششم

- **تاریخ:** 2026-10-20
- **شاخه:** `mission/ra365-100pct-parity-2026-10-20` (از `b5504c5c`)
- **وضعیت:** `PARTIAL — یک باگِ اثبات‌شده اصلاح شد؛ منبع DPS کشف شد؛ شکاف‌های منبع باز است.`
- **ادعای 100%:** ندارد.

> اعداد با ارقام لاتین و از رجیسترهای ماشین‌خوان نوشته شده‌اند. CSV corpus و رجیسترهای Round 5 منبع بازتولیدند.

## خلاصهٔ چهار سؤالی

1. **کدام اختلاف عددی حل شد؟** دوبار‌شماری یک ردیف دفتری در `داسوه` و `فولاژ`؛ `غويتا` از 4.82% به 1.06% رسید. جزئیات در §3.
2. **کدام فرمول/رفتار کشف شد؟** `ref_factor=type7/type0`؛ `ref_ratio=1/factor_step`؛ هویت ردیف دفتری؛ گام‌های سالانه از DPS/افزایش سرمایه (`timescale_marks`)، با فرمول دقیق هنوز نیمه‌اثبات‌شده. جزئیات در §5 و spec.
3. **تطابق دقیق/نزدیک/پوشش چه تغییری کرد؟** baseline دقیقاً بازتولید شد؛ exact و functional headline تغییر نکرد؛ near مطلق سه نماد بهتر شد (projected +1993 تاریخ، +0.168 واحد درصد). مخرج و تلورانس تغییر نکرد.
4. **مهم‌ترین اختلاف باقی‌مانده و آزمون بعدی؟** 578 گام REF_ONLY در جهت DPS/افزایش سرمایه که محصول رویداد ندارد؛ آزمون بعدی: 10–20 نمونه با `timescale_marks` و فرمول `(previous_capital/new_capital)` + DPS. سپس 150 اختلاف نسبت base و 632 گام بدون رویداد محصول.

## 1. Git، دیتابیس و baseline

| مورد | مقدار |
|---|---|
| HEAD مبنا | `b5504c5c` |
| کامیت‌های این دور | `354ac2e6` (DB isolation)، `6fc5f8c4` (ledger dedupe)، `9f290721` (history writer test) |
| `market.db` عملیاتی (Round 5) | `fff358a78be74e8d21961251a727116e102df84cea70f87b4dcb7da198667004` |
| اثرانگشت منطقی عملیاتی | `cdb73c40a14f3fefbf6053bb65716e3cbc50f2af464b4dd2a1934ace2b73fcd4` |
| وضعیت پس از تحقیق | بدون تغییر (byte و logical) |
| main/tag/release | دست‌نخورده؛ هیچ push/merge انجام نشد |

### بازتولید baseline روی ورودی ثابت

ورودی‌ها:

- manifest: `_audit/RAHAVARD-FULL-UNIVERSE-MANIFEST-v2-2026-10-20.csv`
- ref: `_scratch/ra_fup_2026_10_20/ref_bars_v2.jsonl`
- product-live: `_scratch/ra_round3/product_live_final_v4.jsonl`
- product-db: `_scratch/ra_fup_2026_10_20/product_bars.jsonl`

| سنجه | Round 5 | بازتولید این دور |
|---|---:|---:|
| assets measured | 2595 | 2595 |
| live assets | 2520 | 2520 |
| raw exact | 97.5526% | 97.5526% |
| Factor exact | 38.6269% (457727/1184995) | 38.6269% (457727/1184995) |
| Factor ±1% | 81.6474% (967518) | 81.6474% (967518) |
| Factor نرمال ±1% | 81.0311% (960214) | 81.0311% (960214) |
| OHLC عملکردی | 39.4074% (1867902/4739980) | 39.4074% (1867902/4739980) |
| فقط مرجع | 658 | 658 |
| کندل گم‌شدهٔ محصول | 1361 | 1361 |
| step pairs / mismatch | 5858 / 269 | 5858 / 269 |

`by_class`، `field_status` و `weekly_field_status` نیز مو‌به‌مو یکسان‌اند. یعنی baseline Round 5 با ورودی ثابت **دقیقاً** بازتولید می‌شود.

## 2. نویسندهٔ ۱۴ ردیف `price_history`

### شاهد

- 14 ردیف با `src='published'` و `date='2026-10-20'`: `تفارس، حپارسا، ددانا، رمپنا، ساروم، سخاش، سفار، سمتاز، شسپا، شفارس، فجام، مارون، همراه، ولراز`.
- آخرین ردیف قبل از آن‌ها برای همه `2026-10-19` با `src='board'` بود.
- هر 14 نماد در `.screener_cache.json` (50 ردیف watchlist) حاضرند؛ cache در 21:32:35 و DB در 21:37:48 نوشته شده است.
- مسیر کد: `api/chart.py::_schedule_history_repair` → `test_tsetmc.fetch_price_history` → `candle_contract.UPSERT_SQL` با `src='published'`.

### بازتولید کنترل‌شده

یک کپی «پیش از نوشتن» از DB (443738 ردیف) ساخته و `_schedule_history_repair('شفارس','2026-10-19','2026-10-20')` روی آن اجرا شد:

```
[history] شفارس: 1 OHLCV rows saved
copy_row == operational_row  → True
```

دیتابیس عملیاتی در این آزمون لمس نشد. تست آفلاین و قطعی `dev/test_history_repair_writer_v1.py` همین مسیر را با DB موقت و CSV ساختگی ثابت می‌کند: 6/6 سبز.

### نتیجه

- **داده‌مسیر:** CONFIRMED.
- **مجموعهٔ 14 نماد:** با watchlist کش اسکرینر هم‌خوان است.
- **ابزار/صفحهٔ دقیقی که آن 14 درخواست چارت را ساخت:** UNVERIFIED (یک UI/پروبِ زندهٔ Round 5 بوده؛ خود مسیر داده اثبات شده است).
- **ایزوله‌سازی:** `BORS_WORK_DIR`/`BORS_DB`، `dev/db_fingerprint.py` (اثرانگشت منطقی مستقل از ترتیب صفحه)، `dev/gate_db_guard.py`، و `BORS_NO_FETCH_LOOPS=1`. تست `dev/test_db_isolation_v1.py` 12/12 سبز است.

## 3. اصلاح‌های این دور

| اصلاح | فایل | تست | اثر |
|---|---|---|---|
| ایزوله‌سازی DB و گیت ضد‌نوشتن | `bors_config.py`, `dev/gate_db_guard.py`, `dev/db_fingerprint.py` | `test_db_isolation_v1.py` 12/12 | گیت کپیِ موقت می‌سازد؛ اثرانگشت منبع قبل/بعد مقایسه می‌شود |
| تاریخ‌نگار writer | `dev/test_history_repair_writer_v1.py` | 6/6 | مسیر published و بستنِ fetch-loop |
| حذف دوبار‌شماری یک ردیف دفتری | `api/chart.py`, `dev/test_official_ledger_dedupe_v1.py` | 7/7 | داسوه/فولاژ اصلاح شد؛ غويتا به 1.06% رسید |

### اثر عددی ledger dedupe (روی corpus ثابت)

| نماد | Factor near مطلق قبل | بعد | تغییر |
|---|---:|---:|---:|
| داسوه | 4.7252% | 95.1721% | +90.4469 |
| فولاژ | 15.6376% | 31.2081% | +15.5705 |
| غويتا | 6.5816% | 6.5816% | 0 (خطای گام 4.82%→1.06%) |

- **Projected** aggregate: `+1993` تاریخ near، حدود `+0.168` واحد درصد روی `live_factor_near_pct` (از 81.6474 به ~81.8155). این عدد باید با اجرای کامل بعدی تأیید شود؛ فعلاً per-symbol measured است.
- **Factor exact و functional OHLC headline تغییر نکردند.** این اصلاح را به‌عنوان بهبود گسترده اعلام نمی‌کنیم.

## 4. معیارهای شکست در سطح گام (آستانهٔ 1%)

| دسته | تعداد |
|---|---:|
| PAIR با اختلاف نسبت >1% | 269 |
| منبع: base-price-discontinuity | 150 |
| منبع: priceAdjust | 49 |
| منبع: بدون رویداد نزدیک | 26 |
| منبع: None | 31 |
| shareChange | 6 |
| tsetmc_price_adjust_by_flow | 6 |
| fund-portal | 1 |
| REF_ONLY | 658 (632 بدون هیچ رویداد محصول) |
| REF_ONLY با `ref_ratio < 0.995` (قیمت کاهش/factor افزایش) | 578 |
| REF_ONLY با `ref_ratio` نزدیک 1 | 78 |
| REF_ONLY با `ref_ratio > 1.005` | 2 |
| PROD_ONLY | 141 |

### هفت نماد نمونه

| نماد | Factor exact | Factor near مطلق | Factor norm near | وضعیت |
|---|---:|---:|---:|---|
| داسوه | 4.7252% | 4.7252% → 95.1721% | 4.8279% | `FIXED_LEDGER_DEDUPE` |
| فولاژ | 3.9597% | 15.6376% → 31.2081% | 68.7919% | `PARTIAL_LEDGER_DEDUPE` |
| وبشهر | 4.5822% | 29.0431% | 69.1375% | `OPEN_DPS_SOURCE` |
| غپينو | 0.0% | 0.0% | 100.0% | `OPEN_ANCHOR` |
| فاراك | 7.4916% | 7.4916% | 22.4749% | `OPEN_BASE_OFFICIAL` |
| غچين | 67.7551% | 100.0% | 100.0% | `CONTROL` |
| غويتا | 6.5816% | 6.5816% | 93.4184% | `PARTIAL_LEDGER_DEDUPE` |

CSV کامل: `docs/RAHAVARD-PARITY-CORPUS-2026-10-20.csv`.

## 4.1. شکاف‌های منبع (572 ردیف)

رجیستر ردیف‌به‌ردیف: `docs/RAHAVARD-SOURCE-GAP-RECOVERY-ROUND5-2026-10-20.csv` (572 ردیف، ستون‌های asset_id/symbol/ref_date/ref_ratio/taxonomy/status_round5/next_action).

| taxonomy | تعداد |
|---|---:|
| NO_OFFICIAL_EVENT | 510 |
| BASE_GAP_NOT_DETECTED | 54 |
| LOCAL_FALLBACK_TRUNCATED | 6 |
| FUND_EVENT_NOT_MATCHED | 2 |

| status_round5 | تعداد |
|---|---:|
| SOURCE_GAP_CONFIRMED | 511 |
| UNVERIFIED:PARSER_OR_THRESHOLD | 54 |
| FIXED_BY_ROUND4_REFRESH | 5 |
| UNVERIFIED:FUND_EVENT_DATE | 2 |

`final_status` همهٔ 572 ردیف `SOURCE_GAP_CONFIRMED` است؛ این یعنی «نبودِ منبع تأیید شد»، نه «مشکل حل شد». 54 ردیف `BASE_GAP_NOT_DETECTED` هنوز در سطح parser/threshold بازند و نمونه‌های آن‌ها (`اطلس`, `حشكوه`, `حپرتو`, `دانيك`, `درازي`, `زگلدشت`, `سشمال`) در نمونهٔ شش‌تایی ما با `timescale_marks` هم‌پوشانی DPS/capital دارند.

### فبيرا (تنها LOCAL_FALLBACK_TRUNCATED باقی‌مانده)

- asset 158، ref step 2025-08-31، `ref_ratio=0.93243414`.
- `timescale_marks` زنده: یک capital_change در 2025-08-18 با `previous_capital=3.6T`, `new_capital=5.0T`, `contribution_percent=100` (و بدون DPS نزدیک).
- نتیجه: رویداد منبع پیدا شد، اما نسبت 0.93243414 با نسبت سهام 0.72 یکی نیست؛ نسبت دقیق نیازمند قیمت پذیره‌نویسی/ردیف رسمی CODAL است. این مورد دیگر «بدون رویداد» نیست؛ «نسبت رسمی نامعلوم» است.

### 4.2. جفت‌ها، دارایی‌ها و ETF — وضعیت باز

| دسته | تعداد | وضعیت این دور | اقدام |
|---|---:|---|---|
| جفت‌های سهام | 128 | 70 SOURCE_GAP_CONFIRMED، 51 EXPECTED_SEMANTIC_DIFFERENCE، 7 UNVERIFIED | هیچ‌کدام در این دور حل نشد؛ نیازمند منبع رسمی/تصمیم معنایی |
| دارایی‌های فاقد منبع زنده | 78 | 67 options، 7 stocks، 2 funds، 2 bonds — SOURCE_UNAVAILABLE | جایگزینی با دادهٔ نزدیک ممنوع؛ منتظر منبع رسمی |
| ETFها | 5 | 3 اطلس با «تقسیم سود ندارد»، 1 هامرز سود صفر، 1 هامرز ماه غایب | صفر رسمی از نبود رکورد جدا بماند؛ تأیید مالک/منبع |

این سه دسته در شمارش 100% این دور **حل‌شده حساب نمی‌شوند**. هیچ برچسب `EXPECTED_SEMANTIC_DIFFERENCE` به‌تنهایی از شمارش خارج نشده است.

### دو ردیف صندوق (هامرز)

- 2025-02-04 و 2025-07-07، `FUND_EVENT_NOT_MATCHED`, `fund_events=0`, `product_source=fund-portal`.
- نتیجه: صفر رسمی/ماه غایب باید از «عدم توزیع» جدا بماند؛ تطبیق تاریخ/مبلغ منبع رسمی صندوق باقی است.

## 5. کشف DPS و مسیر 100%

دادهٔ زندهٔ `type0/type7` داسوه (5001 کندل، 2001-03-18 تا 2026-10-20) همان 9 گام 2018-2026 را با نسبت‌های یکسان با snapshot ثابت برگرداند؛ پس snapshot برای مقایسه معتبر است. آخرین کندل زنده 2026-10-20 است و در snapshot نیست.

از API مرجع (`/api/v2/chart/timescale_marks`) برای سه نماد، DPS واقعی دریافت شد:

- داسوه: 2024-03-13 `dps=1300`، 2026-04-18 `dps=1800`
- فولاژ: 2025-08-05 `dps=330`، 2026-07-22 `dps=540`
- وبشهر: 2026-07-02 `dps=480`

گام‌های سالانهٔ مرجع با همین DPSها هم‌زمان‌اند. فرمول `dps / close` در 8 مورد HIT و 12 مورد MISS داد؛ برای داسوه 2026، base ضمنی `25680` است در حالی که آخرین close در دسترس `24920` است. یعنی مرجع احتمالاً از **قیمت پایه/پایانی روز رویداد** استفاده می‌کند، نه close قبل از گام. جزئیات در `docs/RAHAVARD-FACTOR-OHLC-SPEC-2026-10-20.md`.

### REF_ONLY: بیشتر افزایش سرمایه، نه فقط DPS

از 658 گام REF_ONLY، 578 گام با `ref_ratio < 0.995` (قیمت کاهش/factor افزایش) هستند؛ یعنی سمت DPS/افزایش سرمایه، نه سمت تجزیه. `timescale_marks` علاوه بر DPS، `type_id=4` با `capital_change` (`previous_capital`, `new_capital`, `contribution_percent`, `reserve_percent`) دارد.

شش نماد نمونه (`ولانا 599`, `غانيزان 36712`, `كربن 28076`, `سشمال 112`, `سهرمز 236`, `فبيرا 158`) بررسی شدند؛ همه گام‌های REF_ONLY آن‌ها در جهت `<0.995` بودند و در بازهٔ نزدیک گام، DPS و/یا capital_change وجود داشت. مثلاً `ولانا` در 2026-06-28 و 2026-07-25 دو capital_change دارد. **وجود و هم‌ترازی منبع CONFIRMED؛ فرمول دقیق ترکیب UNVERIFIED است.**

این کشف توضیح می‌دهد چرا 632 گام REF_ONLY در محصول رویداد ندارند و چرا نسبت رسمی `priceAdjust` همیشه با مرجع یکی نیست.

## 6. کارهای بعدی (اولویت‌دار)

1. **منبع DPS + capital_change برای REF_ONLY:** 10–20 نماد از 632 مورد (۶ نمونه انجام شد)؛ خواندن `timescale_marks` و تطبیق DPS/capital_change با گام مرجع. اگر >80% هم‌تراز بود، منبع با مجوز مالک و نرخ محدود به زنجیر اضافه شود (نه درخواست انبوه).
2. **قیمت پایهٔ رویداد:** استخراج از سطر بی‌معامله/پایهٔ همان روز در CSV و مقایسه با base ضمنی مرجع؛ فرمول ترکیب `(previous_capital/new_capital)` و DPS.
3. **تداخل base/official:** قاعدهٔ برنده بر اساس `collapsed` و DPS؛ فاراك (base نزدیک‌تر) و وبشهر (official نزدیک‌تر) دو سر طیف‌اند.
4. **لنگر:** دارایی‌هایی مثل غپينو که مرجعشان زودتر تمام می‌شود، در مقایسهٔ مطلق با لنگر آخرین تاریخ مشترک جدا شوند.
5. **گام‌های گم‌شده:** فقط از منبع رسمی/مجاز پر شوند؛ هیچ رویدادی از عدد مرجع ساخته نشود.

## 7. گیت و یکپارچگی

- دستور گیت: `python dev/run_all_tests.py` (خودکار به `dev/gate_db_guard.py` واگذار می‌شود).
- گیت با `BORS_WORK_DIR`/`BORS_DB` موقت و `BORS_NO_FETCH_LOOPS=1` اجرا می‌شود.
- اثرانگشت DB عملیاتی قبل/بعد مقایسه می‌شود؛ تغییر منطقی ⇒ `PROTECTED_DB_CHANGED` و شکست گیت.
- در اجرای اول، `dev/chart_api_check_v95.py` در worktree تازه 10/18 شد چون `frontend/node_modules` وجود نداشت. با اتصال (junction) به نصب موجود `klinecharts 10.0.3`، همین گارد مستقل **18/18** سبز شد؛ این یک رفع محیطی است، نه تغییر کد.
- نتیجهٔ اجرای کامل این دور: **در حال اجرا** (سوئیت سنگین `confidence_engine_v973`). پس از پایان، همین بخش با نتیجهٔ واقعی (`ALL SUITES PASSED` یا فهرست شکست‌ها) به‌روزرسانی می‌شود. هیچ سبزی محیطی ادعا نمی‌شود.

## 8. فایل‌ها و شواهد

| مورد | مسیر |
|---|---|
| corpus هفت نماد | `docs/RAHAVARD-PARITY-CORPUS-2026-10-20.csv` |
| مشخصات Factor/OHLC | `docs/RAHAVARD-FACTOR-OHLC-SPEC-2026-10-20.md` |
| بازتولید baseline | `_scratch/ra365_100pct/baseline_v4_repro/` (محلی، gitignored) |
| لاگ بازتولید | `_scratch/ra365_100pct/baseline_v4_repro.log` |
| نمونه‌های هفت نماد | `_scratch/ra365_100pct/cases/` |
| DPS marks (سه نماد) | `_scratch/ra365_100pct/live/ra365_dps_marks.json` |
| REF_ONLY marks (شش نماد) | `_scratch/ra365_100pct/live/refonly_marks.json` |
| گام‌ها/منبع اختلاف | `_scratch/ra365_100pct/step_source_audit.csv` |
| گیت | `_scratch/ra365_100pct/gate_full.log` |

## 9. محدودیت‌ها

- ابزار دقیق trigger چهارده ردیف در Round 5 شناسایی نشد؛ مسیر داده و ایزوله‌سازی اثبات شد.
- فرمول دقیق DPS/base کامل نشده؛ 12 MISS در نمونه داریم.
- 632 گام REF_ONLY هنوز رویداد رسمی در محصول ندارند.
- Factor exact/functional headline با اصلاح این دور تغییر نکرد.
- Full-universe parity **پس از** اصلاح ledger دوباره اجرا نشد؛ عدد `+1993` از جمع per-symbol اندازه‌گیری‌شده تخمین زده شده و باید در اجرای بعدی تأیید شود.
- 128 جفت، 78 دارایی و 5 ETF در این دور بازآزمایی نشدند؛ وضعیت Round 5 برای آن‌ها معتبر است، نه «حل‌شده».
- هیچ عددی با تغییر مخرج، تلورانس یا حذف نمونه سبز نشد.
