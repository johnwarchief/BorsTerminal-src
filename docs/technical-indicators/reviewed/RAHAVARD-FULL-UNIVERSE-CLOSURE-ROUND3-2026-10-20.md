# بستن مأموریت تطبیق Rahavard365 — دور سوم

- **تاریخ:** ۲۰۲۶-۱۰-۲۰
- **شاخه:** `mission/rahavard-full-universe-parity-2026-10-20`
- **مبنا:** `7b22de6d` (پایان دور دوم)
- **گزارش‌های همراه:** `RAHAVARD-FULL-UNIVERSE-CLOSURE-2026-10-20.md`، `RAHAVARD-DATA-CONTRACT-2026-10-20.md`

**حکم: `COMPLETE WITH EXPLICIT BLOCKERS` — نه تطبیق ۱۰۰٪.**

دور سوم سه گلوگاه اصلی را از حالت «برچسب» خارج کرد: توزیع‌های صندوق از پورتال رسمی مدیر صندوق وارد زنجیره شد، گپ ۲۰۲۳-۰۳-۲۷ از endpoint رسمی روزانه پر شد، و ۸۷۹ دارایی از ۹۵۷ داراییِ live-unavailable با pull تازه زنده شدند. ۵ گام ETF و بخشی از اختلاف‌های رویداد سهام همچنان منبع/قرارداد روشن ندارند و صریح ثبت شده‌اند.

## ۱. Git و دامنه تغییر

| مورد | مقدار |
|---|---|
| شاخه | `mission/rahavard-full-universe-parity-2026-10-20` |
| HEAD پایه | `7b22de6d` |
| کامیت این دور | `ROUND3_SHA_PLACEHOLDER` |
| `main` / push / merge | دست‌نخورده؛ هیچ push یا merge انجام نشد |
| `market.db` عملیاتی | دست‌نخورده؛ همهٔ ingestها و pullها روی کپی |
| تست‌ها | در بخش ۹ |

## ۲. کنترل شمارش‌ها (یک مخرج برای هر عدد)

| سطح | تعداد | تعریف |
|---|---|---|
| ابزار در `instruments` | ۵۹۸۱ | ردیف‌های جدول instruments |
| نگاشت قطعی | ۳۷۱۰ | exact + normalized exact + variant با شاهد |
| دارایی canonical رهاورد | ۲۹۶۵ | asset_id یکتا در نگاشت |
| دارایی دارای دادهٔ مرجع | ۲۵۹۶ | type0/type7 × D/W |
| دارایی مقایسه‌شده | ۲۵۹۵ | دارایی با کندل مشترک |
| دارایی زنده (basis=last) | ۲۵۱۷ | پاسخ محصول با basis=last و منبع غیر-fallback |
| دارایی در inventory دسترس‌پذیری | ۲۵۹۵ | یک ردیف per asset؛ شامل fallback |
| دارایی live-unavailable دور دوم | ۹۵۷ | CSV fallback دور دوم |

**هم‌پوشانی وضعیت‌ها (v3):** `functional_available=True` = ۱۴۲۰؛ `window_available` = ۱۴۳۶؛ fallback در inventory = ۱۴۲. این‌ها یک مخرج نیستند: fallback بودن با SOURCE_GAP/UNVERIFIED هم‌پوشانی دارد و در CSV ستون‌های `adjust_source` و `functional_status` جدا نگه داشته شده‌اند.

## ۳. P0-A — توزیع‌های صندوق/ETF

**منبع رسمی:** برای هر ۱۶ صندوق، پورتال رسمی مدیر صندوق پیدا شد. ۱۰ صندوق روی سامانهٔ Rayan Ham Afza و ۵ صندوق روی گزارش قدیمی ASP.NET هستند؛ اطلس هیچ رکورد توزیع دوره‌ای ندارد. مبلغ، تاریخ سود و شناسهٔ رکورد در `fund_profit_events` و `tools/fund_profit_sources.json` ثبت شده است.

**قاعدهٔ تاریخ اثر:** اولین سشن معاملاتی **پس از** تاریخ سود پورتال؛ قیمت مرجع = LAST سشن قبل از آن. نسبت از `(P−D)/P` توسط موتور ساخته می‌شود، نه از گسست قیمت. اگر چند ماه بی‌معامله به یک سشن بازگشایی برسند، توزیع‌های همان سشن جمع می‌شوند (نه حذف دومی).

| گام | نماد | صندوق | حل‌شده | سایر وضعیت‌ها |
|---|---|---|---|---|
| ۸۲ | پارند | صندوق س. پارند پايدار سپهر | ۸۲ | — |
| ۸۱ | ارمغان | ص سرمايه گذاري ارمغان ايرانيان | ۸۱ | — |
| ۶۲ | تداوم | صندوق تداوم اطمينان تمدن-ثابت | ۶۲ | — |
| ۵۶ | هامرز | صندوق س اعتماد هامرز-ثابت | ۵۴ | REFERENCE_CONTRACT_UNCLEAR:OFFICIAL_ZERO_DISTRIBUTION=1; SOURCE_GAP_CONFIRMED:NO_OFFICIAL_EVENT_FOR_MONTH=1 |
| ۵۰ | نخل | صندوق س.خليج فارس-د | ۵۰ | — |
| ۴۴ | آفاق | صندوق س نوع دوم افق آتي-ثابت | ۴۴ | — |
| ۴۱ | دارا | صندوق س. دارا الگوريتم-د | ۴۱ | — |
| ۲۶ | ترنج ثابت | ص.س.درآمد ثابت ترنج سودمند-د | ۲۶ | — |
| ۲۲ | بلوط | صندوق س شكوه بامداد زاگرس-ثابت | ۲۲ | — |
| ۲۱ | آسان | صندوق س.درآمدثابت گنجينه مهر-د | ۲۱ | — |
| ۱۹ | همگام | صندوق س. م.اوراق دولتي همگام-د | ۱۹ | — |
| ۱۸ | سخند | صندوق س.سپهرخبرگان نفت-د | ۱۸ | — |
| ۱۰ | آسا | صندوق س آرمان كارآفرين-ثابت | ۱۰ | — |
| ۷ | پاداش | صندوق س. ارزش پاداش-د | ۷ | — |
| ۳ | اطلس | صندوق س.توسعه اطلس مفيد-س | ۰ | SOURCE_GAP_CONFIRMED:NO_DISTRIBUTION_POLICY=3 |
| ۳ | دامون | ص.س. درآمد ثابت آسمان دامون-د | ۳ | — |

| وضعیت Gate A | تعداد |
|---|---|
| RESOLVED_OFFICIAL_SOURCE | ۵۴۰ |
| SOURCE_GAP_CONFIRMED:NO_DISTRIBUTION_POLICY | ۳ |
| REFERENCE_CONTRACT_UNCLEAR:OFFICIAL_ZERO_DISTRIBUTION | ۱ |
| SOURCE_GAP_CONFIRMED:NO_OFFICIAL_EVENT_FOR_MONTH | ۱ |

**۵ گام باقی‌مانده:** ۳ گام اطلس (صندوق سهامی؛ پورتال رسمی `periodic-profit` صفر رکورد دارد) با وضعیت `SOURCE_GAP_CONFIRMED:NO_DISTRIBUTION_POLICY`؛ ۱ گام هامرز با ردیف رسمی «سود صفر» در برابر گام مرجع (`REFERENCE_CONTRACT_UNCLEAR:OFFICIAL_ZERO_DISTRIBUTION`)؛ ۱ گام هامرز بدون ردیف در گزارش رسمی (`SOURCE_GAP_CONFIRMED:NO_OFFICIAL_EVENT_FOR_MONTH`).

**اثر سنجیده:** در دامنهٔ ۱۶ صندوق، گام‌های فقط‌مرجع از ۵۴۵ در دور دوم به ۵ کاهش یافت و جفت‌های گام به ۵۹۷ رسید. raw زنده ۹۹٫۹۵٪ و factor در ±۱٪ برای صندوق‌های دارای پوشش کامل تا ۱۰۰٪ (پارند، نخل، ترنج، بلوط، تداوم، دارا، آسان، دامون، همگام، پاداش، آسا) است.

## ۴. P0-B — ۱۲۸ جفت سهام

| طبقهٔ Round-3 | تعداد |
|---|---|
| SOURCE_GAP_CONFIRMED:PRE_LEDGER_COVERAGE | ۵۱ |
| REFERENCE_CONTRACT_DIFFERENCE:PRODUCT_MATCHES_OFFICIAL | ۲۶ |
| REFERENCE_CONTRACT_DIFFERENCE:REFERENCE_DIFFERS_FROM_LEDGER | ۲۵ |
| SOURCE_GAP_CONFIRMED:NO_LEDGER_ROW | ۱۹ |
| UNRESOLVED:COMPOSITE_CAPITAL_EVENT | ۷ |

**نتیجه:** ۵۱ جفت پیش از پوشش دفتر رسمی (۲۰۲۴-۰۷-۲۱)، ۱۹ جفت بدون هیچ ردیف رسمی در پنجرهٔ ±۵ روز، ۲۶ جفت که محصول با ردیف رسمی می‌خواند و مرجع متفاوت است، ۲۵ جفت که مرجع با ردیف رسمی نمی‌خواند، و ۷ جفت با رویداد سرمایه‌ای مرکب (نسبت‌های shareChange که حاصل‌ضربشان ≈۱ است). هیچ exception ثابت یا ضریب حدسی اضافه نشد؛ CSV کامل در `_audit/RAHAVARD-EVENT-PAIRS-ROUND3-2026-10-20.csv` است.

## ۵. P0-C — ناهنجاری ۲۰۲۰-۰۵-۲۶

جدول `session_anomalies` از اسکن cross-sectional پر شد، نه از تاریخ ثابت. قاعده: `official_symbols=0` و `product_only_steps≥10` و `median_abs_ratio_deviation≤2%`. تنها تاریخ واجد شرط **۲۰۲۰-۰۵-۲۶** بود (۷۳ گپ، ۵۷ گام فقط‌محصول، میانهٔ انحراف ۰٫۸۴٪).

`_filter_unproven_base_events` اکنون گسست پایه در این سشن‌ها را با `session-wide-base-gap` رد می‌کند؛ رویداد نوع‌دار/رسمی دست‌نخورده می‌ماند. در cohort ۸۵ نمادیِ همین تاریخ، **هیچ گام ۲۰۲۰-۰۵-۲۶ در خروجی نماند**. هیچ تاریخ یا ضریب ویژه در کد نوشته نشد.

## ۶. P0-D — ۲۰۲۳-۰۳-۲۷/۲۸

| نتیجهٔ backfill | تعداد |
|---|---|
| RESOLVED_OFFICIAL_ROW | ۴۷ |
| ADMIN_NO_TRADE_ROW | ۴ |

۴۷ ردیف معامله‌شده از `GetClosingPriceDaily` رسمی پر شد؛ ۴ ردیف اداریِ حجم‌صفر طبق قرارداد no-trade کندل نشدند. در pull ۵۱ نمادی، `missing_product_candles` از ۵۱ به ۱ رسید؛ تنها مورد باقی‌مانده نماد `وشهر` بود که به دلیل انتخاب `ins_code` variant، backfillش در pull اول نیامده بود. پس از backfill همهٔ variantها و pull مجدد همان نماد، کندل ۲۰۲۳-۰۳-۲۷ در پاسخ حاضر شد (سنجش مستقیم).

## ۷. P0-E — ۹۵۷ دارایی live-unavailable

| وضعیت Round-3 | تعداد |
|---|---|
| LIVE_RECOVERED | ۸۷۹ |
| DB_FALLBACK | ۷۸ |

| علت باقی‌مانده | تعداد |
|---|---|
| OPTION_NO_LIVE_OR_EXPIRED | ۶۷ |
| STOCK_NO_LIVE_SINCE_2024_08_24 (delisted/transferred) | ۷ |
| BOND_EXPIRED_OR_NO_LIVE_ROW | ۲ |
| FUND_NO_LIVE_SOURCE | ۲ |

۸۷۹ دارایی با pull تازه زنده شدند (options 467، stocks 189، bonds 128، ETF 88، warrants 5، futures 2)؛ ۷۸ دارایی باقی ماندند: ۶۷ اختیارِ بدون CSV/منقضی، ۷ سهم بدون منبع زنده از ۲۰۲۴-۰۸-۲۴، ۲ صندوق بدون منبع زنده، و ۲ اوراق نزدیک انقضا. inventory کامل با `last_candle` و `adjust_source` در `_audit/RAHAVARD-FALLBACK-INVENTORY-ROUND3-2026-10-20.csv` است.

## ۸. Parity کامل v3

| سنجه | دور دوم | دور سوم | تغییر |
|---|---|---|---|
| دارایی مقایسه‌شده | ۲۵۹۵ | ۲۵۹۵ | ۰ |
| دارایی زنده (basis=last) | ۱۶۳۸ | ۲۵۱۷ | +۸۷۹ |
| تاریخ مشترک روزانه | ۹۹۴۰۳۲ | ۱۱۸۵۷۵۷ | +۱۹۱۷۲۵ |
| هفتهٔ مشترک | ۲۳۱۲۱۹ | ۲۷۵۹۱۶ | +۴۴۶۹۷ |
| raw زنده در تلورانس | ۹۷.۴۸٪ | ۹۷.۵۵٪ | +۰.۰۷ واحد٪ |
| factor ≤۰٫۰۵٪ | ۳۶.۸۴٪ | ۳۸.۳۲٪ | +۱.۴۸ واحد٪ |
| factor ≤۱٪ | ۸۰.۷۲٪ | ۸۲.۰۶٪ | +۱.۳۴ واحد٪ |
| factor نرمال ≤۰٫۰۵٪ | ۳۷.۵۷٪ | ۴۰.۵۰٪ | +۲.۹۲ واحد٪ |
| factor نرمال ≤۱٪ | ۷۷.۱۲٪ | ۸۱.۱۱٪ | +۳.۹۹ واحد٪ |
| OHLC عملکردی | ۳۸.۰۳٪ | ۳۹.۱۰٪ | +۱.۰۷ واحد٪ |
| جفت‌های گام | ۴۱۳۹ | ۵۸۱۶ | +۱۶۷۷ |
| گام فقط‌مرجع | ۱۲۰۳ | ۶۷۸ | -۵۲۵ |
| گام فقط‌محصول | ۲۰۱ | ۱۴۵ | -۵۶ |

**خواندن:** درصدهای factor مخرج بزرگ‌تری دارند چون ۸۷۹ دارایی زنده و صدها گام رسمی صندوق اضافه شده‌اند؛ بهبودِ خالص در تعداد و در `ref_only_steps` است. افزایش `step_ratio_mismatch` از ۲۱۸ به ۲۶۴ ناشی از جفت‌شدن گام‌های بیشتری است که قبلاً فقط‌مرجع بودند، نه بدترشدن موتور.

**به تفکیک کلاس (زنده، v3):**

| کلاس | دارایی | raw | factor دقیق | factor نرمال دقیق | عملکردی |
|---|---|---|---|---|---|
| stocks | ۷۸۷ | ۹۶٫۹۳٪ | ۲۵٫۵۵٪ | ۲۹٫۵۷٪ | ۲۶٫۵۶٪ |
| etf_funds | ۳۴۴ | ۹۹٫۹۵٪ | ۸۵٫۱۵٪ | ۷۹٫۶۴٪ | ۸۵٫۱۱٪ |
| bonds | ۳۷۱ | ۹۹٫۵۲٪ | ۱۰۰٫۰۰٪ | ۱۰۰٫۰۰٪ | ۹۹٫۴۲٪ |
| options | ۱۰۰۱ | ۹۹٫۶۶٪ | ۱۰۰٫۰۰٪ | ۱۰۰٫۰۰٪ | ۹۹٫۶۵٪ |
| futures | ۱۴ | ۹۹٫۸۲٪ | ۷۰٫۵۴٪ | ۷۰٫۵۴٪ | ۷۰٫۵۴٪ |
| warrants | ۶ | ۹۹٫۸۹٪ | ۱۰۰٫۰۰٪ | ۱۰۰٫۰۰٪ | ۹۹٫۹۳٪ |

## ۹. Availability

| وضعیت | v2 | v3 |
|---|---|---|
| AVAILABLE_NO_EVENTS | ۱۰۹۲ | ۱۴۲۰ |
| SOURCE_GAP | ۴۶۶ | ۴۶۴ |
| UNVERIFIED | ۶۶۵ | ۶۶۶ |
| STALE | ۳۶۹ | ۳۲ |
| PARTIAL | ۳ | ۱۳ |
| functional_available=True | ۱۰۹۲ | ۱۴۲۰ |
| window_available | ۱۰۹۵ | ۱۴۳۶ |

کاهش STALE از ۳۶۹ به ۳۲ نتیجهٔ مستقیم pull تازه است. ۱٬۴۲۰ دارایی `True` عمدتاً اختیار/اوراق/آتی/حق‌تقدمِ بی‌رویداد و صندوق‌های دارای پوشش رسمی هستند؛ سهام بدون دفتر کامل همچنان UNVERIFIED/SOURCE_GAP می‌ماند.

## ۱۰. موانع باقی‌مانده (فیلدهای اجباری)

| id | asset/date | observed | evidence | root cause | why unresolved | next |
|---|---|---|---|---|---|---|
| ETF-01 | اطلس ۱۴۰۰/۰۲–۰۴ | ۳ گام مرجع، ۰ رکورد رسمی | `RAHAVARD-ETF-STEPS-ROUND3` | صندوق سهامی؛ پورتال دوره‌ای ندارد | رکورد رسمی توزیع موجود نیست | بررسی اساسنامه/مجامع اطلس |
| ETF-02 | هامرز ۱۴۰۳/۱۱ | مرجع ۰٫۹۷۶۸، رسمی صفر | گزارش ASP.NET هامرز | ردیف رسمی سود صفر | تعریف مرجع با رکورد رسمی یکی نیست | داوری مالک روی قرارداد صندوق |
| ETF-03 | هامرز ۱۴۰۴/۰۴ | مرجع ۰٫۹۷۵۳، رسمی ندارد | گزارش ASP.NET هامرز | ماه در گزارش رسمی غایب | منبع رسمی برای همان ماه نیست | آرشیو/اطلاعیهٔ ماهانه |
| PAIR-01 | ۵۱ جفت pre-2024 | اختلاف نسبت | `RAHAVARD-EVENT-PAIRS-ROUND3` | دفتر رسمی پیش از ۲۰۲۴-۰۷-۲۱ پوشش ندارد | منبع رسمی تاریخی موجود نیست | آرشیو رسمی/CODAL |
| PAIR-02 | ۱۹ جفت post-2024 | بدون ردیف ±۵روز | `RAHAVARD-EVENT-PAIRS-ROUND3` | ردیف رسمی برای همان رویداد نیست | نمی‌توان نسبت را ساخت | reconciliation منبع |
| PAIR-03 | ۷ جفت سرمایه‌ای مرکب | نسبت shareChange چندتکه | `RAHAVARD-EVENT-PAIRS-ROUND3` | حاصل‌ضرب نسبت‌ها ≈۱ | نسبت واحد قابل استخراج نیست | داوری روی ترکیب رویداد |
| LIVE-01 | ۷ سهم last=2024-08-24 | DB fallback | inventory fallback | منبع زنده ندارد (delisted/transfer) | CSV زنده خالی است | منبع جایگزین/حذف از eligible |
| LIVE-02 | ۶۷ اختیار | DB fallback | inventory fallback | CSV زنده برای این اختیارها نیست | بازار/سرور ردیف نمی‌دهد | منبع اختصاصی اختیار |

## ۱۱. تست‌ها و گیت

| گیت | نتیجه |
|---|---|
| `dev/test_fund_profit_and_backfill_v1.py` | ۱۷/۱۷ |
| `dev/test_functional_availability_v1.py` | ۲۸/۲۸ |
| `dev/test_adjustment_phasea.py` | ۵۸ pass / ۰ fail |
| `dev/test_adjustment_engine_v1.py` | ۴۴/۴۴ |
| `dev/test_corporate_ledger_v1.py` | ۲۴/۲۴ |
| `dev/test_unproven_base_events_v1.py` | ۱۰/۱۰ |
| `dev/test_rahavard_contract_v1.py` | ۲۵/۲۵ |
| `dev/price_last_value_v1070.py` | ۲۶/۲۶ |
| `dev/test_rule_map_citations.py` | ۱۱/۱۱ |
| `npx vitest run` | ۲۰۶۵ pass / ۵ skip / ۰ fail (۱۹۷ فایل) |
| `npx tsc -b` / `npm run build` | rc=0 / rc=0 |
| `python dev/run_all_tests.py` | ALL SUITES PASSED — ۱۳۸ suite شمارش‌شده، ۲۹ silent، ۱ skip (fixture missing)، rc=0 |

## ۱۲. بازتولید

```bash
python tools/fund_profits_ingest.py --db <copy.db> --sources tools/fund_profit_sources.json --out _audit/fund_profits.csv
python tools/session_backfill.py --db <copy.db> --symbols _audit/RAHAVARD-MISSING-SESSION-20230328-2026-10-20.csv --out _audit/backfill.csv
python tools/session_anomaly_scan.py --db <copy.db> --gaps _audit/RAHAVARD-MARKET-GAP-DATES-2026-10-20.csv --out _audit/anomalies.csv
python tools/etf_steps_round3.py --steps _audit/RAHAVARD-ETF-STEPS-2026-10-20.csv --canonical _audit/RAHAVARD-FULL-UNIVERSE-CANONICAL-v2-2026-10-20.csv --sources tools/fund_profit_sources.json --db <copy.db> --out _audit/etf_round3.csv
python tools/event_pairs_round3.py --pairs _audit/RAHAVARD-EVENT-PAIRS-2026-10-20.csv --db market.db --out _audit/pairs_round3.csv
python tools/ra_full_universe_parity.py --manifest ... --ref ... --product-live ... --out-dir ...
python dev/run_all_tests.py
```

## ۱۳. محدودیت‌ها

- اعداد parity از snapshotهای ۲۰۲۶-۱۰-۲۰ هستند؛ TSETMC تاریخی را بازنویسی می‌کند.
- داده‌های ۸۷۹ داراییِ زنده‌شده در cohortهای تازه pull شده‌اند؛ دارایی‌های بدون تغییر از snapshot همان‌روز v2 استفاده می‌کنند و منبع هر ردیف در `_round3_source` ثبت است.
- ۵ گام ETF و بخشی از ۱۲۸ جفت سهام منبع/قرارداد روشن ندارند؛ هیچ ضریب یا تاریخی برای سبزشدن جعل نشد.
- `market.db` عملیاتی نوشته نشد؛ جدول‌های جدید روی کپی ساخته و آزموده شدند.

---

_SHA کامیت این دور: `ROUND3_SHA_PLACEHOLDER`._