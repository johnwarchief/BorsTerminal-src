# بستن ریشه‌ای اختلاف‌های Rahavard — دور چهارم

- **تاریخ:** ۲۰۲۶-۱۰-۲۰
- **شاخه:** `mission/rahavard-full-universe-parity-2026-10-20`
- **HEAD مبنا:** `8aedb480` (پس از `a65fa87b`)
- **کامیت این دور:** `04698eaac8835801fb7a790964dfd8b7d61fca79`
- **گزارش‌ها:** `RAHAVARD-FULL-UNIVERSE-CLOSURE-ROUND3-2026-10-20.md`، `RAHAVARD-DATA-CONTRACT-2026-10-20.md`

**حکم: `COMPLETE WITH EXPLICIT BLOCKERS` — بهبود واقعی در ۳۳ نماد و ۱۷ مرحله، بدون ادعای ۱۰۰٪.**

دور چهارم یک نقص قابل‌اثبات را بست: ردیف‌های رسمی `price_adjust_events` که کاشفِ گسستِ CSV ندیده بود، اکنون در نقطهٔ کانونی تعدیل تزریق می‌شوند؛ ۱۷ مرحلهٔ فقط‌مرجع به `PAIR` تبدیل شد و ۲۰ مرحلهٔ فقط‌مرجع از کل کم شد. در همان زمان، pull تازهٔ ۳۳ نماد دادهٔ خام چند نماد را بازنویسی کرد و factor ±۱٪ را ۰٫۴۱ واحد درصد کاهش داد؛ این افت در ۵ نماد متمرکز است و در بخش ۴ توضیح داده شده است.

## ۱. Git و دیتابیس

| مورد | مقدار |
|---|---|
| شاخه | `mission/rahavard-full-universe-parity-2026-10-20` |
| HEAD مبنا | `8aedb480` |
| working tree | پاک در شروع و پایان |
| push/merge/tag/release | انجام نشد |
| `market.db` sha256 شروع | `1601238326c196086ae25f246ac3be25b6b685d967c3b02e333ce32db4a13498` |
| `market.db` sha256 پایان | `ce74f80cf8ebb721239ff5114f8baa8db573fdc2b3f6c38a4adccb910ef22237` |
| جدول‌های جدید در `market.db` | `fund_profit_events` / `session_backfill` / `session_anomalies` با ۰ ردیف |

**هشدار شفاف:** در شروع دور چهارم، سه جدول جدید در `market.db` عملیاتی وجود داشتند ولی **هیچ ردیفی نداشتند**. این DDL خالی در گیت دور سوم هنگام اجرای `ensure_schema` ساخته شده بود؛ داده‌ای نوشته نشد. همهٔ پردازش‌های دور چهارم روی کپی انجام شد. checksum پایان در بخش ۱۲ آمده است. بایت‌های فایل در گیت تغییر کرد (سازگار با checkpoint/WAL)؛ هیچ ingest یا pull روی این فایل ننوشت و سه جدول جدید ۰ ردیف ماندند.

## ۲. تغییرات کد در برابر فایل‌های ممیزی

| نوع | فایل | تغییر |
|---|---|---|
| کد | `api/chart.py` | تزریق `price_adjust_events` رسمی + انتقال رویداد روز بی‌معامله به اولین کندل |
| کد | `tools/session_anomaly_scan.py` | قاعدهٔ `qualifies()` قابل تست، بدون تاریخ |
| کد | `tools/ra_full_universe_parity.py` | نمونه‌های factor/func و symbol/asset در mismatch samples |
| تست | `dev/test_fund_profit_and_backfill_v1.py` | ۱۹/۱۹ شامل تزریق priceAdjust |
| تست | `dev/test_session_anomaly_v1.py` | ۱۱/۱۱ کنترل مثبت/منفی/مصنوعی |
| ممیزی | `tools/ra_round4_refonly.py` | طبقه‌بندی ۶۷۸ مرحلهٔ فقط‌مرجع |
| ممیزی | `tools/ra_round4_registers.py` | ساخت سه رجیستر + رجیستر mismatch |
| مستند | قرارداد داده | تعریف دقیق سنجه‌ها و وضعیت‌ها |

## ۳. نتایج Round 3 و Round 4 با تعریف یکسان

| سنجه | Round 3 | Round 4 | تغییر |
|---|---|---|---|
| دارایی مقایسه‌شده | ۲۵۹۵ | ۲۵۹۵ | ۰ |
| دارایی زنده (basis=last) | ۲۵۱۷ | ۲۵۲۰ | +۳ |
| تاریخ مشترک روزانه | ۱۱۸۵۷۵۷ | ۱۱۸۸۵۵۶ | +۲۷۹۹ |
| هفتهٔ مشترک | ۲۷۵۹۱۶ | ۲۷۶۵۵۲ | +۶۳۶ |
| raw زنده | ۹۷.۵۵٪ | ۹۷.۵۵٪ | +۰.۰۰ واحد٪ |
| factor دقیق | ۳۸.۳۲٪ | ۳۸.۶۳٪ | +۰.۳۱ واحد٪ |
| factor ±۱٪ | ۸۲.۰۶٪ | ۸۱.۶۵٪ | -۰.۴۱ واحد٪ |
| factor نرمال دقیق | ۴۰.۵۰٪ | ۴۰.۵۰٪ | +۰.۰۰ واحد٪ |
| factor نرمال ±۱٪ | ۸۱.۱۱٪ | ۸۱.۰۳٪ | -۰.۰۸ واحد٪ |
| OHLC عملکردی | ۳۹.۱۰٪ | ۳۹.۴۱٪ | +۰.۳۰ واحد٪ |
| جفت‌های گام | ۵۸۱۶ | ۵۸۵۸ | +۴۲ |
| فقط‌مرجع | ۶۷۸ | ۶۵۸ | -۲۰ |
| فقط‌محصول | ۱۴۵ | ۱۴۱ | -۴ |
| کندل گم‌شدهٔ محصول | ۱۳۷۸ | ۱۳۶۱ | -۱۷ |

**چرا factor ±۱٪ کمی افت کرد:** تزریق رسمی در ۱۷ مرحله و pull تازهٔ ۳۳ نماد، ۱۲ نماد را تغییر داد. ۵ نماد (`داسوه`، `غپینو`، `فاراك`، `فولاژ`، `غويتا`) افت بزرگ دارند و ۲ نماد (`غچين`، `وبشهر`) بهبود بزرگ؛ بقیه تغییر ناچیز. سه نماد زندهٔ اضافه و ۲٬۷۹۹ تاریخ مشترک اضافه نیز از pull تازه است. بنابراین افت یک trade-off داده/قرارداد است، نه ضعیف‌شدن تلورانس.

## ۴. ریشهٔ اختلاف factor و OHLC

| علت | تعداد نمونه |
|---|---|
| SOURCE_GAP | ۲۲۶۱ |
| REFERENCE_SEMANTIC_DIFFERENCE:PRE_HISTORY_OFFSET | ۵۰۶ |
| ADJUSTMENT_FORMULA_MISMATCH | ۹۲ |
| ADJUSTMENT_PROPAGATION | ۴۹ |
| REFERENCE_SEMANTIC_DIFFERENCE | ۱۱ |
| UNVERIFIED | ۱۰ |
| RAW_PRICE_MISMATCH | ۵ |

رجیستر ۲٬۹۳۴ نمونه از cohort ۱۰۰ داراییِ هدفمندِ نامنطبق است، نه توزیع کل universe. نمونه‌های بازتولیدپذیر:

| نماد/تاریخ | اندازه‌گیری | علت |
|---|---|---|
| `بالاس` ۲۰۲۵-۰۱-۲۱ | مرجع ۰٫۹۹۹۱۲۲۰۴ / محصول ۰٫۹۹۹۱۴۳۱ | `FIXED`: ردیف رسمی ۲۰۲۵-۰۱-۱۹ (۰٫۹۹۹۱۴۳۱) تزریق شد و مرحله PAIR شد |
| `آريا` ۲۰۲۰-۰۵-۲۷ | factor مرجع ۰٫۰۶۶۰۱۶ / محصول ۰٫۰۶۴۵۳۰؛ نسبت ۰٫۹۹۷۴۹۱ ≈ میانهٔ ۰٫۹۹۷۶۳۴ | `REFERENCE_SEMANTIC_DIFFERENCE:PRE_HISTORY_OFFSET` |
| `الماس` ۲۰۲۵-۰۲-۱۱ | factor مرجع ۰٫۱ / محصول ۱٫۰؛ رویداد محصول ۰٫۱ | `ADJUSTMENT_FORMULA_MISMATCH`: قرارداد factor مرجع در همان تاریخ |
| `خكرمان` ۲۰۲۵-۰۳-۰۳ | close مرجع ۵٬۰۵۰ / محصول ۵٬۰۸۰ (۰٫۵۹٪) | `RAW_PRICE_MISMATCH`: بازنویسی/منبع خام |
| `سخند` ۲۰۲۰-۰۷-۰۶ | نسبت مرجع ۰٫۸۶۰۹ / رسمی ۰٫۸۳۸۱ | `EXPECTED_SEMANTIC_DIFFERENCE`: DPS رسمی با مقدار مرجع یکی نیست |
| `ضستا1068` ۲۰۲۶-۱۰-۱۲ | close مرجع ۴۷۰ / محصول ۶۷۰ | `UNVERIFIED`: قیمت اختیار و قرارداد مرجع |

**OHLC عملکردی:** بیشتر نمونه‌ها (`func_*`) علت را از factor همان تاریخ به ارث می‌برند (`ADJUSTMENT_PROPAGATION`)؛ اختلاف‌های `SESSION_HIGH_LOW_DIFFERENCE` به سایه/سشن مرجع مربوط‌اند و در محاسبهٔ عملکردی جدا می‌مانند. هیچ کندلی برای بستن اختلاف ساخته نشد.

## ۵. ۱۲۸ جفت سهام

| وضعیت نهایی | تعداد |
|---|---|
| SOURCE_GAP_CONFIRMED | ۷۰ |
| EXPECTED_SEMANTIC_DIFFERENCE | ۵۱ |
| UNVERIFIED | ۷ |

۷۰ مورد `SOURCE_GAP_CONFIRMED` (۵۱ پیش از پوشش دفتر + ۱۹ بدون ردیف در پنجره)، ۵۱ مورد `EXPECTED_SEMANTIC_DIFFERENCE` (۲۶ محصول=رسمی/مرجع متفاوت + ۲۵ مرجع≠رسمی)، و ۷ مورد `UNVERIFIED` با رویداد سرمایه‌ای مرکب. هیچ جفت بدون وضعیت نماند؛ رجیستر: `docs/RAHAVARD-128-PAIR-CLOSURE-ROUND4-2026-10-20.csv`.

## ۶. ۶۷۸ مرحلهٔ فقط‌مرجع

| وضعیت نهایی | تعداد |
|---|---|
| SOURCE_GAP_CONFIRMED | ۵۷۲ |
| REFERENCE_SEMANTIC_DIFFERENCE | ۶۴ |
| FIXED | ۱۷ |
| SHARE_CHANGE_COMPONENT_UNSAFE | ۱۷ |
| UNVERIFIED | ۴ |
| EXPECTED_SEMANTIC_DIFFERENCE | ۳ |
| BELOW_STEP_DETECTION_TOLERANCE | ۱ |

۱۷ مورد با تزریق رسمی `FIXED` شد. ۵۷۲ مورد `SOURCE_GAP_CONFIRMED` (بدون رویداد رسمی/خارج از پوشش)، ۶۴ مورد `REFERENCE_SEMANTIC_DIFFERENCE` (مرحلهٔ کوچک مرجع)، ۱۷ مورد `SHARE_CHANGE_COMPONENT_UNSAFE` (نسبت‌های مرکب net≈۱)، ۳ مورد فیلترشدهٔ محصول، ۱ مورد زیر آستانهٔ ۰٫۰۵٪ و ۴ مورد `UNVERIFIED`. رجیستر: `docs/RAHAVARD-REFONLY-678-ROUND4-2026-10-20.csv`.

## ۷. ۷۸ دارایی فاقد دادهٔ زنده

| کلاس | تعداد | حکم |
|---|---|---|
| options | ۶۷ | `SOURCE_GAP_CONFIRMED`: CSV زنده/منبع اختیار |
| stocks | ۷ | `SOURCE_GAP_CONFIRMED`: بدون منبع زنده از ۲۰۲۴-۰۸-۲۴ |
| etf_funds | ۲ | `SOURCE_GAP_CONFIRMED`: منبع زندهٔ صندوق |
| bonds | ۲ | `SOURCE_GAP_CONFIRMED`: سرعت/انقضا |

mapping هر ۷۸ مورد با `ins_code` معتبر تأیید شد؛ endpoint روزانه برای اختیار/اوراق پشتیبانی نمی‌شود و سهام/صندوق‌های باقی‌مانده منبع زنده ندارند. قیمت دارایی دیگر یا رکورد قدیمی جایگزین نشد. رجیستر: `docs/RAHAVARD-LIVE-UNAVAILABLE-ROUND4-2026-10-20.csv`.

## ۸. پنج مورد ETF

| مورد | حکم |
|---|---|
| اطلس ۱۴۰۰/۰۲–۰۴ (۳ گام) | `SOURCE_GAP_CONFIRMED:NO_DISTRIBUTION_POLICY`؛ صفحهٔ رسمی مفید «تقسیم سود: ندارد» |
| هامز ۱۴۰۳/۱۱ | `REFERENCE_CONTRACT_UNCLEAR:OFFICIAL_ZERO_DISTRIBUTION`؛ گزارش رسمی سود صفر دارد |
| هامز ۱۴۰۴/۰۴ | `SOURCE_GAP_CONFIRMED:NO_OFFICIAL_EVENT_FOR_MONTH`؛ ماه در گزارش رسمی غایب است |

## ۹. تست‌ها

| گیت | نتیجه |
|---|---|
| `dev/test_fund_profit_and_backfill_v1.py` | ۱۹/۱۹ |
| `dev/test_session_anomaly_v1.py` | ۱۱/۱۱ |
| `dev/test_functional_availability_v1.py` | ۲۸/۲۸ |
| `dev/test_adjustment_phasea.py` | ۵۸ pass / ۰ fail |
| `dev/test_adjustment_engine_v1.py` | ۴۴/۴۴ |
| `dev/test_corporate_ledger_v1.py` | ۲۴/۲۴ |
| `dev/test_unproven_base_events_v1.py` | ۱۰/۱۰ |
| `dev/test_rahavard_contract_v1.py` | ۲۵/۲۵ |
| `dev/price_last_value_v1070.py` | ۲۶/۲۶ |
| `dev/test_rule_map_citations.py` | ۱۱/۱۱ |
| `python dev/run_all_tests.py` | ALL SUITES PASSED — ۱۳۸ suite شمارش‌شده، ۳۰ silent، ۱ skip (fixture missing)، rc=0 |
| `npx vitest run` | ۲۰۶۵ pass / ۵ skip / ۰ fail (دور سوم؛ بدون تغییر فرانت) |
| `npx tsc -b` / `npm run build` | rc=0 / rc=0 (دور سوم؛ بدون تغییر فرانت) |

## ۱۰. اصلاح‌شده در برابر فقط‌طبقه‌بندی‌شده

| دسته | اصلاح واقعی | فقط طبقه‌بندی/مستند |
|---|---|---|
| factor/OHLC | تزریق رسمی priceAdjust؛ ۱۷ مرحله PAIR شد | ۲٬۹۳۴ نمونهٔ cohort با علت و شاهد |
| ۱۲۸ جفت | ۰ | ۱۲۸ |
| ۶۷۸ فقط‌مرجع | ۱۷ FIXED + ۲۰ کاهش کل | ۶۶۱ |
| ۷۸ live-unavailable | ۰ (منبع واقعی ندارد) | ۷۸ |
| ۵ ETF | ۰ | ۵ |

## ۱۱. محدودیت‌ها و شواهد لازم

- ۵۷۲ مرحلهٔ فقط‌مرجع و ۷۰ جفت سهام منبع رسمی تاریخی ندارند؛ برای بستن آن‌ها آرشیو رسمی/کدال یا دفتر پیش از ۲۰۲۴-۰۷-۲۱ لازم است.
- ۱۷ مورد `SHARE_CHANGE_COMPONENT_UNSAFE` نسبت‌های مرکب دارند که حاصل‌ضربشان ≈۱ است؛ نسبت واحد قابل استخراج نیست.
- ۷۸ دارایی زنده‌ناپذیر: ۶۷ اختیار و ۲ اوراق با endpoint روزانه پشتیبانی نمی‌شوند؛ ۷ سهم/۲ صندوق منبع زنده ندارند.
- افت factor ±۱٪ در ۵ نماد نتیجهٔ pull تازه/بازنویسی منبع است؛ برای جداسازی کامل، snapshot قبل و بعد همان نمادها با checksum منبع لازم است.
- هیچ تست یا تلورانسی برای بهترشدن درصد تغییر نکرد؛ تعریف سنجه‌ها در قرارداد داده ثبت شد.

## ۱۲. SHA و تأییدها

- **SHA کامیت این دور:** `04698eaac8835801fb7a790964dfd8b7d61fca79`
- **push/merge/tag/release:** انجام نشد.
- **`market.db`:** sha256 شروع `1601238326c196086ae25f246ac3be25b6b685d967c3b02e333ce32db4a13498`؛ sha256 پایان `ce74f80cf8ebb721239ff5114f8baa8db573fdc2b3f6c38a4adccb910ef22237`؛ سه جدول جدید ۰ ردیف.
