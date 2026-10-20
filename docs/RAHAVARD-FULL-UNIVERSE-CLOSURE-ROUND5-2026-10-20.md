# بستن ریشه‌ای اختلاف‌های Rahavard — دور پنجم

- **تاریخ:** ۲۰۲۶-۱۰-۲۰
- **شاخه:** `mission/rahavard-full-universe-parity-2026-10-20`
- **HEAD مبنا:** `55fa7a72` (پس از `04698eaa`)
- **کامیت این دور:** `ROUND5_SHA_PLACEHOLDER`

**حکم: `PARTIAL — ANALYSIS COMPLETE, EXTERNAL SOURCE GAPS REMAIN`.** هیچ ادعای ۱۰۰٪ نیست؛ افت پوشش/فاکتور با مدرک بررسی شد و فقط اصلاحات دارای شاهد اعمال شدند.

## ۱. Git، دیتابیس و baseline

| مورد | مقدار |
|---|---|
| HEAD شروع | `55fa7a72` |
| working tree شروع/پایان | پاک / پاک |
| push / merge / tag / release | انجام نشد |
| `market.db` sha256 شروع/پایان | `ce74…22237` / `fff358a7…667004` |
| integrity_check | `ok` |
| جدول‌های جدید | ۰ ردیف |
| حکم یکپارچگی | `LOGICAL_CONTENT_DIFFERENCE_FOUND` — ۱۴ ردیف `price_history` با `src=published` در گیت اضافه شد |

جزئیات در `docs/RAHAVARD-DATABASE-INTEGRITY-ROUND5-2026-10-20.md`: کپی کاری `market_copy.db` خودش با ingestهای ما تغییر کرده و `market_copy_v2.db` قدیمی‌تر از گیت است؛ بنابراین برابری منطقی پیش/پس قابل اثبات نیست. سلامت فایل و schema تأیید شد.

## ۲. افت فاکتور پنج نماد

| نماد | near v3→v4 | علت |
|---|---|---|
| داسوه | 95.1721→4.7252 | REFERENCE_SEMANTIC_DIFFERENCE:OFFICIAL_PRICE_ADJUST_NOT_MIRRORED |
| غپينو | 20.8817→0.0 | SOURCE_REVISION:HISTORY_EXTENSION_FROM_LOCAL_FALLBACK |
| فاراك | 24.8276→7.4916 | SOURCE_REVISION:HISTORY_EXTENSION_FROM_LOCAL_FALLBACK |
| فولاژ | 31.2081→15.6376 | REFERENCE_SEMANTIC_DIFFERENCE:OFFICIAL_PRICE_ADJUST_NOT_MIRRORED |
| غويتا | 21.5596→6.5816 | SOURCE_REVISION:HISTORY_EXTENSION_FROM_LOCAL_FALLBACK |
| غچين | 21.1845→100.0 | SOURCE_REVISION:HISTORY_EXTENSION_FROM_LOCAL_FALLBACK |
| وبشهر | 4.5822→29.0431 | REFERENCE_SEMANTIC_DIFFERENCE:OFFICIAL_PRICE_ADJUST_NOT_MIRRORED |

**ریشه:** چهار نماد (`غپينو`، `غچين`، `فاراك`، `غويتا`) در v3 روی `local-db-fallback` با تاریخچهٔ ۴۳۳–۴۴۱ کندلی بودند؛ pull تازه تاریخچهٔ کامل ۲٬۰۰۰+ کندلی را آورد. سه نماد دیگر (`داسوه`، `فولاژ`، `وبشهر`) یک ردیف رسمی `price_adjust_events` گرفتند که رهاورد آن را منعکس نمی‌کند. هیچ‌کدام خطای parser نیست؛ `SOURCE_REVISION:HISTORY_EXTENSION` و `REFERENCE_SEMANTIC_DIFFERENCE:OFFICIAL_PRICE_ADJUST_NOT_MIRRORED` ثبت شدند. برای غپينو/فاراك/غچين میانهٔ خطا به‌شدت بهتر شد (مثلاً ۷۵۰٫۷٪→۸٫۶٪ برای غپينو)؛ غويتا بدتر شد (۲٫۷٪→۴٫۸٪) و بازمانده است.

## ۳. Cohortهای OHLC/factor

| سناریو | تعداد |
|---|---|
| MATCHED | ۱۶۵۹ |
| FACTOR_DIFF_WITH_HIGH_LOW_NOISE | ۵۶۶ |
| SESSION_HIGH_LOW_ONLY | ۳۷۸ |
| RAW_DIFF_FACTOR_OK | ۱۷۵ |
| RAW_OK_FACTOR_DIFF | ۷۹ |
| HISTORY_OFFSET | ۶۱ |
| BOTH_DIFF | ۴۰ |
| SOURCE_REVISION_FIVE | ۷ |

| علت | تعداد |
|---|---|
| MATCHED | ۱۶۵۹ |
| REFERENCE_SEMANTIC_DIFFERENCE:SESSION_HIGH_LOW | ۳۷۸ |
| ADJUSTMENT_FACTOR_MISMATCH | ۳۷۳ |
| REFERENCE_SEMANTIC_DIFFERENCE:PRE_HISTORY_OFFSET | ۳۷۳ |
| RAW_PRICE_MISMATCH | ۱۷۵ |
| SOURCE_REVISION:HISTORY_EXTENSION_FROM_LOCAL_FALLBACK | ۴ |
| REFERENCE_SEMANTIC_DIFFERENCE:OFFICIAL_PRICE_ADJUST_NOT_MIRRORED | ۳ |

رجیستر کامل: `docs/RAHAVARD-FACTOR-OHLC-ROOT-CAUSE-ROUND5-2026-10-20.csv`. مخرج این جدول **۲٬۹۶۵ دارایی canonical** است (شامل fallback)، نه فقط ۲٬۵۲۰ دارایی زنده. سناریوی غالب `FACTOR_DIFF_WITH_HIGH_LOW_NOISE` (۵۶۶) و `SESSION_HIGH_LOW_ONLY` (۳۷۸) است؛ دومی اختلاف سایه/سشن مرجع است، نه فاکتور.

## ۴. شکاف‌های منبع (۵۷۲)

| Taxonomy | تعداد |
|---|---|
| NO_OFFICIAL_EVENT | ۵۱۰ |
| BASE_GAP_NOT_DETECTED | ۵۴ |
| LOCAL_FALLBACK_TRUNCATED | ۶ |
| FUND_EVENT_NOT_MATCHED | ۲ |

| وضعیت Round 5 | تعداد |
|---|---|
| SOURCE_GAP_CONFIRMED | ۵۱۱ |
| UNVERIFIED:PARSER_OR_THRESHOLD | ۵۴ |
| FIXED_BY_ROUND4_REFRESH | ۵ |
| UNVERIFIED:FUND_EVENT_DATE | ۲ |

۵ مورد `FIXED_BY_ROUND4_REFRESH` (غويتا، غپينو، غچين×۲، فاراك) در v4 به PAIR رسیدند. ۵۱۱ مورد همچنان `SOURCE_GAP_CONFIRMED` هستند (بدون هیچ ردیف رسمی)، ۵۴ مورد `UNVERIFIED:PARSER_OR_THRESHOLD` (گسست پایه دیده شده ولی گام ساخته نشده)، و ۲ مورد اختلاف تاریخ رویداد صندوق. رجیستر: `docs/RAHAVARD-SOURCE-GAP-RECOVERY-ROUND5-2026-10-20.csv`.

## ۵. ۱۲۸ جفت، ۷۸ دارایی، ۵ ETF

| جفت‌های سهام | تعداد |
|---|---|
| SOURCE_GAP_CONFIRMED | ۷۰ |
| EXPECTED_SEMANTIC_DIFFERENCE | ۵۱ |
| UNVERIFIED | ۷ |

| دارایی فاقد دادهٔ زنده | تعداد | حکم |
|---|---|---|
| options | ۶۷ | `SOURCE_UNAVAILABLE` / endpoint اختیار |
| stocks | ۷ | `SOURCE_UNAVAILABLE` (بدون منبع از ۲۰۲۴-۰۸-۲۴) |
| etf_funds | ۲ | `SOURCE_UNAVAILABLE` |
| bonds | ۲ | `SOURCE_UNAVAILABLE` (انقضا) |

۵ مورد ETF: ۳ اطلس با صفحهٔ رسمی مفید («تقسیم سود: ندارد»)؛ ۱ هامرز با سود رسمی صفر (`REFERENCE_CONTRACT_UNCLEAR`)؛ ۱ هامرز با ماه غایب (`SOURCE_GAP_CONFIRMED`). صفر رسمی با «عدم توزیع» یکی نشد.

## ۶. ناهنجاری جلسات و رویداد مرکب

قاعدهٔ `qualifies()` با کنترل مثبت/منفی/مصنوعی ۱۱/۱۱ آزموده شد؛ تاریخ در کد نیست. رویداد رسمی روی روز بی‌معامله به اولین کندل منتقل می‌شود و dedupe فقط رویدادهای هم‌تاریخ/بعدی با نسبت مشابه را ادغام می‌کند (پنجرهٔ قبلی ۵روزه به ۳روزه با شرط `ed>=d` اصلاح شد). تست `test_fund_profit_and_backfill_v1.py` به ۲۰/۲۰ رسید.

## ۷. متریک‌های قبل و بعد

| سنجه | Round 4 | Round 5 | تغییر |
|---|---|---|---|
| دارایی زنده | ۲۵۲۰ | ۲۵۲۰ | ۰ |
| تاریخ مشترک روزانه | ۱۱۸۸۵۵۶ | ۱۱۸۸۵۵۶ | ۰ |
| raw زنده | ۹۷.۵۵٪ | ۹۷.۵۵٪ | +۰.۰۰ واحد٪ |
| factor دقیق | ۳۸.۶۳٪ | ۳۸.۶۳٪ | +۰.۰۰ واحد٪ |
| factor ±۱٪ | ۸۱.۶۵٪ | ۸۱.۶۵٪ | +۰.۰۰ واحد٪ |
| factor نرمال ±۱٪ | ۸۱.۰۳٪ | ۸۱.۰۳٪ | +۰.۰۰ واحد٪ |
| OHLC عملکردی | ۳۹.۴۱٪ | ۳۹.۴۱٪ | +۰.۰۰ واحد٪ |
| فقط‌مرجع | ۶۵۸ | ۶۵۸ | ۰ |
| جفت گام | ۵۸۵۸ | ۵۸۵۸ | ۰ |
| کندل گم‌شدهٔ محصول | ۱۳۶۱ | ۱۳۶۱ | ۰ |

**صورت/مخرج factor دقیق:** ۴۵۷۷۲۷ از ۱۱۸۴۹۹۵ تاریخ؛ **±۱٪:** ۹۶۷۵۱۸؛ **نرمال ±۱٪:** ۹۶۰۲۱۴؛ **OHLC:** ۱۸۶۷۹۰۲ از ۴۷۳۹۹۸۰ فیلد؛ **raw:** ۵۷۷۹۹۶۸ از ۵۹۲۴۹۷۵.

**آزمایش ردشده:** یک تغییر موقت در پنجرهٔ dedupe (۵→۳ روز با شرط `ed>=d`) روی ۳۳ نماد رسمی اعمال شد. نتیجه: سه گام فقط‌محصول اضافه و factor ±۱٪ از ۸۱٫۶۵٪ به ۸۱٫۳۹٪ کاهش یافت؛ بررسی نمونهٔ `فباهنر` نشان داد ردیف رسمی ۲۰۲۶-۰۷-۲۰ و رویداد کشف‌شدهٔ ۲۰۲۶-۰۷-۲۱ با نسبت یکسان، **یک اقدام واحد** هستند. تغییر به پنجرهٔ ۵روزه بازگردانده شد و v5b کنار گذاشته شد. متریک Round 5 بنابراین همان v4 است؛ ارزش این دور در ریشه‌یابی و رجیسترهاست، نه تغییر عددی.

## ۸. تست‌ها

| گیت | نتیجه |
|---|---|
| `dev/test_fund_profit_and_backfill_v1.py` | ۲۰/۲۰ |
| `dev/test_session_anomaly_v1.py` | ۱۱/۱۱ |
| `dev/test_adjustment_phasea.py` | ۵۸/۰ |
| `dev/test_adjustment_engine_v1.py` | ۴۴/۴۴ |
| `dev/test_corporate_ledger_v1.py` | ۲۴/۲۴ |
| `dev/test_functional_availability_v1.py` | ۲۸/۲۸ |
| `dev/test_unproven_base_events_v1.py` | ۱۰/۱۰ |
| `dev/test_rahavard_contract_v1.py` | ۲۵/۲۵ |
| `dev/price_last_value_v1070.py` | ۲۶/۲۶ |
| `dev/test_rule_map_citations.py` | ۱۱/۱۱ |
| `python dev/run_all_tests.py` | ALL SUITES PASSED — ۱۳۸ suite شمارش‌شده، ۳۰ silent، ۱ skip (fixture missing)، rc=0 |
| `npx vitest run` / `tsc -b` / `npm run build` | از دور سوم بدون تغییر فرانت |

اجرای اول گیت به دلیل پر شدن دیسک (`ENOSPC`) در ۵ سوئیت نامرتبط شکست خورد؛ پس از حذف snapshotهای تکراریِ scratch، همان ۵ سوئیت جداگانه پاس شدند و گیت کامل دوباره `ALL SUITES PASSED` داد.

## ۹. اصلاح‌شده در برابر طبقه‌بندی‌شده

| دسته | اصلاح واقعی | طبقه‌بندی/مستند |
|---|---|---|
| ۵ نماد افت | ۴ نماد تاریخچهٔ کامل گرفتند؛ ۳ نماد منبع رسمی | ۷ ریشه‌یابی |
| شکاف منبع | ۵ مورد با refresh به PAIR | ۵۶۷ |
| ۱۲۸ جفت | ۰ | ۱۲۸ |
| ۷۸ دارایی | ۰ | ۷۸ |
| ۵ ETF | ۰ | ۵ |

## ۱۰. محدودیت‌ها

- ۵۱۱ شکاف منبع هیچ ردیف رسمی در دفتر/CSV ندارند؛ آرشیو رسمی یا CODAL لازم است.
- ۵۴ شکاف `PARSER_OR_THRESHOLD` نیازمند بررسی دستی گسست پایه در تاریخ مشخص‌اند؛ نسبت رسمی برای ساختن گام وجود ندارد.
- ۷۸ دارایی زنده‌ناپذیر منبع زنده ندارند؛ نباید با دادهٔ نزدیک جایگزین شوند.
- افت پوشش v5 خام کشف و با merge کیفیت‌محور جبران شد؛ v5b ملاک است.
- `LOGICAL_CONTENT_DIFFERENCE_FOUND`: ۱۴ ردیف price_history در گیت اضافه شد؛ baseline پیش از گیت برای مقایسهٔ کامل وجود ندارد.

## ۱۱. SHA

- **SHA این دور:** `ROUND5_SHA_PLACEHOLDER`
- **`market.db`:** `fff358a78be74e8d21961251a727116e102df84cea70f87b4dcb7da198667004`؛ integrity `ok`؛ سه جدول جدید ۰ ردیف.
