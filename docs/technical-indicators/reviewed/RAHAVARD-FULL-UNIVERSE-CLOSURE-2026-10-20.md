# بستن مأموریت تطبیق داده‌های Rahavard365 — گزارش نهایی

- **تاریخ:** ۲۰۲۶-۱۰-۲۰
- **شاخه:** `mission/rahavard-full-universe-parity-2026-10-20`
- **مبنا:** `origin/main` = `a14375c1`
- **SHA کامیت پایه:** `dab2d30a` / `1418fccb`
- **گزارش‌های همراه:** `RAHAVARD-DATA-CONTRACT-2026-10-20.md`، `RAHAVARD-FULL-UNIVERSE-LIVE-PARITY-2026-10-20.md`

**حکم: `COMPLETE WITH EXPLICIT BLOCKERS` — نه تطبیق ۱۰۰٪.**

این دور سه کار را انجام داد که قبلاً انجام نشده بود: قرارداد دادهٔ رهاورد با آزمون اثبات شد؛ نگاشت هویت با نرمال‌سازیِ یونیکد از ۲٬۵۲۲ به ۳٬۷۱۰ ابزار رسید؛ و وضعیت `functional_available` از صفر به ۱۰۹۲ دارایی رسید، بدونِ پایین‌آوردنِ هیچ threshold. اختلاف‌های باقی‌مانده به علتِ مشخص و شاهدِ ردیابی‌شدنی متصل‌اند.

## ۱. وضعیت Git

| مورد | مقدار |
|---|---|
| شاخهٔ کاری | `mission/rahavard-full-universe-parity-2026-10-20` |
| HEAD پایه | `1418fccb` (پس از دو کامیت پایه) |
| سند قرارداد | `docs/technical-indicators/reviewed/RAHAVARD-DATA-CONTRACT-2026-10-20.md` |
| سند parity پایه | `docs/technical-indicators/reviewed/RAHAVARD-FULL-UNIVERSE-LIVE-PARITY-2026-10-20.md` |
| `main` | دست‌نخورده؛ هیچ push/merge انجام نشد |

## ۲. معماری نهایی زنجیره

```
TSETMC CDN CSV ─→ _parse_tsetmc_csv ─→ candles + all_rows
TSETMC price_adjust/share_change ─→ corporate_ledger ─→ canonical events
all_rows ─→ _adjust_events_from_rows ─→ _sharpen_events_with_ledger
          ─→ _filter_unproven_base_events (option/bond/right/positive)
          ─→ _canonical_adjustment → adjustment_engine.chain_factors
          ─→ factors + adjustEvents + adjustRejected + adjustCapability
          ─→ price_basis.resolve_payload → /api/chart + /api/chart-db
          ─→ frontend factors (applyAdjustmentToCandles) + status warning
Rahavard365 live bars (type0/type7) ─→ validation only (never operational source)
```

`_functional_state` اکنون `status` و `availability` را برمی‌گرداند: `AVAILABLE`، `AVAILABLE_NO_EVENTS`، `PARTIAL`، `SOURCE_GAP`، `STALE`، `UNVERIFIED`، `FAILED`، `UNMEASURED`. `functional_available` فقط برای دو وضعیت اول True است. `window_available` پوششِ بازهٔ درخواستی را از کل تاریخچه جدا می‌کند.

## ۳. قرارداد داده (خلاصه)

نسخهٔ ۱٫۰ در سندِ قرارداد ثبت شده است. اعدادِ کلیدی:

| سنجه | نتیجه |
|---|---|
| type0.close = LAST (۳۲۲ دارایی نمونه) | ۱۹۰٬۸۵۴ از ۱۹۰٬۸۷۹ = ۹۹٫۹۸۷٪ |
| type7 لنگر آخر = ۱ | ۱٬۸۹۴ از ۱٬۸۹۴ |
| type7 OHLC = type0 × factor | ۶۹۰٬۹۸۸+ از ۶۹۱٬۰۰۴؛ Close/Volume کامل |
| هفتگی: سطل شنبه + حجم جمع | ۱۶۱٬۷۸۱ هفته منطبق؛ حجم جمع ۱۶۱٬۷۶۸ |
| weekly factor = daily factor آخر هفته | ۱۶۱٬۷۸۱ از ۱۶۱٬۷۸۱ |
| بازهٔ full scan | ۲۰۲۰-۰۱-۰۴ تا ۲۰۲۶-۱۰-۱۹ (۱۵ دارایی از ۲۰۱۸) |

**کشفِ بازنویسیِ منبع:** TSETMC ردیف‌های تاریخی را بین دو pull اضافه می‌کند. `آپ/ثامان 2023-03-27` و `آسان/آسود 2026-04-04` در pull اولیه غایب و در pull تازه حاضر بودند. پس هر parity باید snapshot و تازگیِ منبع را ثبت کند؛ غیبتِ تاریخ بدونِ pull تازه «اختلافِ محصول» نیست.

## ۴. Universe و نگاشت canonical

| سنجه | عدد |
|---|---|
| کل ابزار | ۵۹۸۱ |
| نگاشت قطعی | ۳۷۱۰ (exact ۲۹۶۸ + variant ۷۴۲) |
| از exact، با نرمال‌سازی یونیکد | ۸۷۸ |
| دارایی یکتای Rahavard | ۲۹۶۵ |
| دارایی دارای دادهٔ مرجع (v2) | ۲۵۹۶ |
| دارایی مقایسه‌شده (v2) | ۲۵۹۵ |
| بدون نگاشت (UNMAPPED_NO_REFERENCE) | ۱۳۵۱ |
| بدون دادهٔ محصول (NO_PRODUCT_DATA) | ۹۲۰ |
| دارایی چند-ابزاری (variant group) | ۶۳۰ |
| گروه تغییر نام | ۶۲۸ |
| نماد نگاشت‌شده به چند دارایی | ۰ |

کلاس‌ها: bond: ۱۰۲۲، fund: ۶۸۶، future: ۷۸، option: ۲۴۷۲، right: ۴۲، stock: ۱۶۸۱.

نگاشت‌نشده‌های فعال: bond: ۱۰۵، fund: ۱۴۶، future: ۲۵، option: ۱۶۰، right: ۱۲، stock: ۳۸۳. این‌ها حذف نشده‌اند؛ با دلیل در canonical table مانده‌اند. قواعد: exact trade symbol، normalized exact (ک/ی، فاصله، ZWNJ) و variant فقط با نام یکسان شرکت + پیوستگی سری. هیچ نگاشتِ حدسی یا حذفِ پسوند به‌تنهایی انجام نشد.

## ۵. Provenance و منابع

| منبع | نقش | وضعیت |
|---|---|---|
| TSETMC CDN CSV | تولید کندل خام محصول | زنده؛ قابل بازنویسی تاریخی |
| TSETMC price_adjust/share_change | دفتر رسمی رویداد | read-only؛ پوشش ناقص |
| CODAL notices / financial statements | نوع/مقدار رویداد | ۳۶٬۳۵۰ notice؛ بدون DPS/توزیع کافی |
| Rahavard365 type0/type7 | اعتبارسنجی مستقل | فقط validation؛ منبع عملیاتی نشد |
| price_history محلی | fallback DB | با lineage و STALE |

## ۶. وضعیت availability

| وضعیت | تعداد دارایی |
|---|---|
| AVAILABLE_NO_EVENTS | ۱۰۹۲ |
| PARTIAL | ۳ |
| SOURCE_GAP | ۴۶۶ |
| STALE | ۳۶۹ |
| UNVERIFIED | ۶۶۵ |

`functional_available=True`: **۱۰۹۲** از **۲۵۹۵** دارایی مقایسه‌شده؛ `window_available`: **۱۰۹۵**.

این عدد با **تابع جدید `_functional_state` روی همان coverage** محاسبه شده است؛ ۴۷۷ مورد نیز در payloadهای pullشده با کد جدید مستقیماً `functional_status=AVAILABLE_NO_EVENTS` دارند (بقیه در اولین درخواست چارت همان وضعیت را برمی‌گردانند، چون coverage و کد یکی است).

علتِ صفر بودنِ قبلی: ۱٬۰۳۹ دارایی فقط مانعِ «no-official-rows» داشتند و ۸۸۷ تای آن‌ها اختیار/اوراق/آتی/حق‌تقدم بودند که در قراردادِ رهاورد صفر گامِ تعدیل دارند. قراردادِ کلاس‌محور `AVAILABLE_NO_EVENTS` (raw=functional) برای همین‌ها اعمال شد. برای سهام/صندوق، نبودِ ردیف رسمی به‌تنهایی اثباتِ بی‌رویدادی نیست و `SOURCE_GAP`/`UNVERIFIED` ماند. تستِ مثبت/منفی: `dev/test_functional_availability_v1.py` (۲۴/۲۴).

| کلاس | AVAILABLE_NO_EVENTS | SOURCE_GAP | UNVERIFIED | STALE | PARTIAL |
|---|---|---|---|---|---|
| bonds | ۲۶۸ | ۱ | ۰ | ۱۰۴ | ۰ |
| options | ۸۰۸ | ۰ | ۰ | ۲۵۴ | ۰ |
| futures | ۱۰ | ۳ | ۰ | ۱ | ۰ |
| warrants | ۶ | ۰ | ۰ | ۰ | ۰ |
| stocks | ۰ | ۱۷۳ | ۶۱۰ | ۸ | ۳ |
| etf_funds | ۰ | ۲۸۹ | ۵۵ | ۲ | ۰ |

## ۷. Parity: خط مبنا در برابر اجرای گسترده

| سنجه | پایه | اجرای v2 |
|---|---|---|
| دارایی مقایسه‌شده | ۱۴۹۷ | ۲۵۹۵ |
| دارایی زنده (basis=last) | ۹۲۸ | ۱۶۳۸ |
| تاریخ مشترک روزانه | ۶۲۰۹۸۴ | ۹۹۴۰۳۲ |
| هفتهٔ مشترک | ۱۴۵۰۴۷ | ۲۳۱۲۱۹ |
| خام زنده در تلورانس | ۹۷.۴۰٪ | ۹۷.۴۸٪ |
| فاکتور ≤۰٫۰۵٪ | ۳۵.۹۵٪ | ۳۶.۸۴٪ |
| فاکتور ≤۱٪ | ۸۰.۷۰٪ | ۸۰.۷۲٪ |
| فاکتور نرمال ≤۰٫۰۵٪ | ۳۵.۵۰٪ | ۳۷.۵۷٪ |
| فاکتور نرمال ≤۱٪ | ۷۶.۱۵٪ | ۷۷.۱۲٪ |
| OHLC عملکردی | ۳۷.۰۱٪ | ۳۸.۰۳٪ |

**چرا درصدهای factor با گسترش universe تقریباً ثابت ماندند:** universe بزرگ‌تر شامل اختیار/اوراقِ بیشتری شد که factor=۱ دارند (۱۰۰٪)، و در همان حال سهام/صندوق‌های بیشتری با SOURCE_GAP اضافه شدند. بهبودِ واقعی در پوشش (۱٬۴۹۷→۲٬۵۹۵ دارایی) و availability (۰→۱٬۰۹۲) است، نه در یک درصدِ واحد.

| کلاس (زنده) | دارایی | خام | factor دقیق | factor ±۱٪ | factor نرمال دقیق | عملکردی |
|---|---|---|---|---|---|---|
| stocks | ۵۹۸ | ۹۶.۸۹٪ | ۲۴.۹۹٪ | ۷۹.۲۸٪ | ۲۷.۹۶٪ | ۲۶.۴۹٪ |
| etf_funds | ۲۵۶ | ۹۹.۹۵٪ | ۸۴.۵۶٪ | ۸۵.۶۱٪ | ۷۵.۳۹٪ | ۸۴.۵۱٪ |
| bonds | ۲۴۳ | ۹۹.۹۶٪ | ۱۰۰.۰۰٪ | ۱۰۰.۰۰٪ | ۱۰۰.۰۰٪ | ۹۹.۹۶٪ |
| options | ۵۲۸ | ۹۹.۳۲٪ | ۱۰۰.۰۰٪ | ۱۰۰.۰۰٪ | ۱۰۰.۰۰٪ | ۹۹.۳۱٪ |
| futures | ۱۲ | ۱۰۰.۰۰٪ | ۶۹.۴۴٪ | ۸۷.۹۶٪ | ۶۹.۴۴٪ | ۶۹.۴۴٪ |

**زنجیرهٔ factor قابل بازتولید است:** `tools/ra_factor_audit.py` روی ۱٬۵۵۳ رکورد زنده، **۰ نقطهٔ ناسازگار** بین `factors` سرور و بازسازیِ `raw + events` پیدا کرد. برای فولاد ۲۰۲۲-۰۸-۰۹، ۷ رویدادِ بعد از آن تاریخ دقیقاً همان factor را می‌سازند.

## ۸. اصلاحات انجام‌شده

۱. **نگاشت canonical:** نرمال‌سازی یونیکد (ک/ی، فاصله، ZWNJ) به‌عنوان exact-normalized اضافه شد؛ ۸۷۸ ابزار جدید با شاهدِ نامِ یکسان و ۷۴۲ variant با نام شرکت+پیوستگی. نگاشت ۲٬۵۲۲→۳٬۷۱۰. هیچ fuzzy matching انجام نشد.
۲. **تازگی منبع:** ۱۰۵۶ تاریخِ غایب در ۲۶۷ دارایی شناسایی شد؛ ۳۷۳ نماد دوباره خوانده شد. `2023-03-28` که ۱۶۶ گپ و ۶۵ گام فقط‌محصول ساخته بود، به stale snapshot (غیبت `2023-03-27`) منتسب و برای بخش زیادی حذف شد؛ ۵۱ رکوردِ باقی‌مانده به `_audit/RAHAVARD-MISSING-SESSION-20230328-2026-10-20.csv` رفته است.
۳. **وضعیت availability:** `functional_status`/`availability`/`window_available` + قرارداد no-event کلاس‌محور + تست ۲۴/۲۴؛ `functional_available` ۰→۱٬۰۹۲.
۴. **Live retry/lineage:** ابزار pull حالا retry محدود (۳ تلاش با backoff)، `fetchAttempts`، `liveError` و `fetchedAt` را ثبت می‌کند؛ DB fallback با basis=closing و STALE برچسب می‌خورد.
۵. **UI:** هشدار کوتاه فارسی برای سهام باقی می‌ماند؛ برای اختیار/اوراقِ بی‌رویدادِ فعال **هیچ هشداری** نشان داده نمی‌شود. شاهد مرورگر واقعی ۱۳۶۶×۷۶۸: `ui_option_no_warning.png` و `ui_stock_warning.png`.
۶. **گارد ارجاع کد:** سه ارجاع `NAME:LINE` به‌روز شد؛ ۱۱/۱۱.

## ۹. موانع باقی‌مانده (با فیلدهای اجباری)

| خانواده | تعداد | شاهد | علت ریشه‌ای | گزینه‌های بررسی‌شده | دلیل حل‌نشدن | اقدام بعدی |
|---|---|---|---|---|---|---|
| توزیع صندوق/ETF | ۵۴۵ گام | `_audit/RAHAVARD-ETF-STEPS-2026-10-20.csv` | مقدار/تاریخ توزیع در منابع موجود نیست | TSETMC adjust/share (۰)، CODAL notices (۲۰ AGM، بدون مبلغ)، financial statements (بدون DPS) | دفتر رسمی مقدار توزیع ندارد | پارس PDF تصمیمات مجمع / منبع NAV-توزیع صندوق |
| نسبت رویداد سهام | ۱۲۸ جفت | `_audit/RAHAVARD-EVENT-PAIRS-2026-10-20.csv` | ۷۰ بدون ردیف رسمی؛ ۲۶ محصول=رسمی ولی مرجع متفاوت؛ ۲۵ مرجع≠رسمی؛ ۷ رسمی نزدیک‌تر | دفتر رسمی، ratio محصول، ratio مرجع | تعریف عملکردی مرجع با دفتر رسمی یکی نیست | تصمیم مالک روی قرارداد functional (total-return یا price-only) |
| ناهنجاری ۲۰۲۰-۰۵-۲۶ | ۷۳ گپ | `_audit/RAHAVARD-MARKET-GAP-DATES-2026-10-20.csv` | ۰ ردیف رسمی؛ ۵۷ گام فقط‌محصول؛ close مرجع≠LAST | cross-sectional gap، official ledger، raw/LAST | منبع برای این سشن ناسازگار است؛ اصلاح تاریخ‌محور مجاز نیست | reconciliation با منبع سشن / حذف cross-sectional فقط با شاهد مستقل |
| اقامت ۲۰۲۳-۰۳-۲۸ | ۱۶۶ گپ؛ ۵۱ باقی‌مانده | `_audit/RAHAVARD-MISSING-SESSION-20230328-2026-10-20.csv` | snapshot کهنه `2023-03-27` | refresh ۳۷۳ نماد، TSETMC CSV | ۵۱ نماد هنوز ردیف ۳/۲۷ را در منبع ندارند | fetch مجدد/منبع جایگزین برای همان سشن |
| Live unavailable | ۹۵۷ دارایی | `_audit/RAHAVARD-FALLBACK-ASSETS-2026-10-20.csv` | TSETMC CSV خالی/خطا؛ basis=closing | retry/backoff، DB fallback، lineage | منبع زنده برای این ابزار/سشن موجود نیست | retry کنترل‌شده و منبع اختصاصی؛ status STALE/SOURCE_GAP |
| سهام/صندوق با SOURCE_GAP | ۷۸۳ سهم؛ ۳۴۴ صندوق | `_audit/RAHAVARD-FULL-UNIVERSE-PARITY-v2-SYMBOLS-2026-10-20.csv` (ستون‌های functional_status/availability_status) | رویداد رسمی ناقص/بدون نوع/توزیع | coverage/ledger/kind | `functional_available=True` برای این‌ها ادعای بی‌سند می‌شد | تکمیل CODAL type/DPS و پوشش دفتر |

**تفکیک صریحِ «منبع دارد ولی اصلاح نشده» از «منبع ندارد»:**

- **منبع دارد ولی اصلاح عمومی نشده:** ۲۶ جفت که نسبتِ محصول با ردیف رسمی می‌خواند و مرجع متفاوت است؛ ۲۵ جفت که مرجع با ردیف رسمی نمی‌خواند؛ ۷ جفت که ردیف رسمی به مرجع نزدیک‌تر است ولی قاعدهٔ عمومیِ امنی برای جایگزینی نسبت وجود ندارد؛ ۲۰ گام ETF با اعلانِ مجمع ولی بدون مبلغِ توزیع.
- **منبع ندارد (یا سشنِ منبع ناسازگار است):** ۵۲۵ گام توزیع بدون رکورد؛ ۷۰ جفت بدون ردیف رسمی؛ ۵۷ گام فقط‌محصول در ۲۰۲۰-۰۵-۲۶؛ ۵۱ رکورد باقی‌ماندهٔ ۲۰۲۳-۰۳-۲۸؛ ۹۵۷ داراییِ live-unavailable.

هیچ ضریب، تاریخ یا تلورانسی برای بهترشدن درصد hard-code نشد. هیچ نماد دشواری حذف نشد.

## ۱۰. تست‌ها

| گیت | نتیجه |
|---|---|
| `dev/test_rahavard_contract_v1.py` | ۲۵/۲۵ |
| `dev/test_functional_availability_v1.py` | ۲۴/۲۴ |
| `dev/test_unproven_base_events_v1.py` | ۱۰/۱۰ |
| `dev/test_adjustment_phasea.py` | ۵۸ pass / ۰ fail |
| `npx vitest run` | ۲۰۶۴ pass / ۵ skip / ۱ flake (standalone ۱۴/۱۴) |
| `npx tsc -b` / `npm run build` | rc=0 / rc=0 |
| `python dev/run_all_tests.py` | ALL SUITES PASSED — ۱۳۸ suite شمارش‌شده، ۲۸ silent، ۱ skip (fixture missing)، rc=0 |

## ۱۱. بازتولید

```bash
python tools/ra365_contract_probe.py --ref _audit/ref_bars.jsonl --out _audit/contract_probe.json
python dev/test_rahavard_contract_v1.py
python tools/ra_full_universe_manifest.py --db market.db --bulk _audit/RAHAVARD-BULK-ASSETS-2026-10-20.csv --out _audit/universe_manifest.csv
python tools/ra365_ingest_server.py --port 8791 --dir _scratch/ra365 --targets _scratch/ra365/targets.json
python tools/ra_full_universe_product.py --manifest _audit/universe_manifest.csv --source-db market.db --db _scratch/copy.db --live --out _audit/product_live.jsonl
python tools/ra_full_universe_parity.py --manifest _audit/universe_manifest.csv --ref _audit/ref_bars.jsonl --product-live _audit/product_live_final.jsonl --product-db _audit/product_bars.jsonl --out-dir _audit/out
python tools/ra_full_universe_canonical.py --db market.db --manifest _audit/universe_manifest.csv --out _audit/canonical.csv
python tools/ra_factor_audit.py --product _audit/product_live_final.jsonl --out _audit/factor_audit.json
python dev/run_all_tests.py
```

## ۱۲. محدودیت‌ها

- اعدادِ parity این سند از snapshotهای مشخصِ ۲۰۲۶-۱۰-۲۰ است؛ TSETMC می‌تواند ردیف‌های تاریخی را بازنویسی کند. هر اجرای بعدی باید snapshot و تازگی را ثبت کند.
- هیچ ادعای «۱۰۰٪» یا «functional کامل برای همه» مطرح نیست. `functional_available=True` فقط ۱٬۰۹۲ دارایی (عمدتاً اختیار/اوراق/آتی/حق‌تقدمِ بی‌رویداد) است.
- توزیع‌های صندوق، نسبت‌های رویداد سهام، ناهنجاری ۲۰۲۰-۰۵-۲۶ و ۵۱ رکوردِ ۲۰۲۳-۰۳-۲۸ باز مانده‌اند؛ جزئیات و اقدام بعدی در بخش ۹.
- `market.db` عملیاتی نوشته نشد؛ همهٔ pullها روی کپیِ محلی و همهٔ تست‌های تغییردهنده روی DB موقت اجرا شدند.

---

_SHA کامیت این دور: `FINAL_SHA_PLACEHOLDER`._