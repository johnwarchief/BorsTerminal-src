# BorsTerminal — معماری جداسازی دامنه‌ای پایگاه‌های داده

**نسخه:** 1.0.0 · **تاریخ بازبینی:** 2026-11-13  
**مخزن و شاخه مبنا:** `johnwarchief/BorsTerminal-src` · `main`  
**وضعیت:** `PROPOSED TARGET ARCHITECTURE` — سند طراحی؛ هنوز هیچ دیتابیسی در محصول جابه‌جا نشده است.

## ۱. تصمیم معماری پیشنهادی

داده‌ها باید بر اساس **مالکیت دامنه و چرخهٔ عمر داده** از هم جدا شوند، نه صرفاً بر اساس صفحه‌های UI. پیشنهاد، سه پایگاه عملیاتی اصلی است:

1. `fundamental.db` — داده‌های Codal، صورت‌های مالی و خروجی‌های بنیادی/FTS.
2. `tape.db` — تابلوی زنده، معاملات حقیقی/حقوقی، دفتر سفارش و تاریخچهٔ ریزساختار بازار.
3. `technical.db` — تاریخچهٔ قیمت و حجم، کندل‌های کانونیکال، تعدیلات و خروجی‌های محاسبات تکنیکال.

در کنار این سه، دو فایل کوچک با مسئولیت متفاوت حفظ/تعریف می‌شوند:

- `reference.db` — مرجع مشترک هویت نمادها، شناسه‌ها و aliasها؛ تا هر دامنه یک جدول instruments متناقض نسازد.
- `user.db` — اطلاعات و تنظیمات شخصی کاربر، watchlist و selection decisions؛ این فایل نباید با snapshot داده‌های بازار جایگزین شود.

**`analytics.db` فعلاً مرحلهٔ بعدی است، نه پیش‌نیاز جداسازی اولیه.** وقتی Feature Store نقطه‌درزمان، تاریخچهٔ رژیم‌ها، پیش‌بینی نوسان/ریسک، پیش‌بینی جهت و رجیستری آزمایش‌ها ساخته شوند، آن داده‌های مشتق‌شده در این بانک قرار می‌گیرند؛ نه در `user.db` و نه در بانک خام یکی از دامنه‌ها.

### اصل مالکیت

هر جدول فقط یک **بانک مالک** و یک نویسندهٔ کانونیکال دارد. مصرف‌کننده‌های دیگر از repository/read interface آن دامنه می‌خوانند؛ آن‌ها نباید نسخهٔ دوم دادهٔ خام را بسازند یا همان جدول را بنویسند.

---

## ۲. وضع موجود در main — شواهد واقعی کد

در snapshot بررسی‌شده، جداسازی فیزیکی دامنه‌ها انجام نشده است:

| موضوع | وضعیت فعلی و شاهد |
|---|---|
| مسیر اصلی | `bors_config.DB_PATH` به `market.db` اشاره می‌کند؛ `USER_DB_PATH` برای `user.db` وجود دارد |
| دادهٔ تکنیکال | `test_tsetmc.create_schema()` جدول‌های `price_history` و `daily_prices` را می‌سازد؛ `price_history` کندل کانونیکال است |
| دادهٔ تابلو | همان `create_schema()` جدول‌های `market_watch`، `client_type`، `boards`، `order_book` و `mstat_snap` را در همان `market.db` می‌سازد؛ `tsetmc_p0_schema.py` هم جدول‌های تکمیلی مانند `client_type_value` و رویدادهای تعدیل را اضافه می‌کند |
| دادهٔ بنیادی/Codal | `codal_fetcher.create_schema()` در همان اتصال، `codal_notices`، `codal_extracted`، `financial_statements`، `monthly_sales`، `fts_results` و جدول‌های صف/اجرای pipeline را می‌سازد |
| وابستگی بنیادی به تابلو | `api/fundamental.py` و `fts_engine.py` در کوئری‌های خود، اطلاعات مالی را با `market_watch` و `instruments` ترکیب می‌کنند؛ نمونه: ارزش بازار از `market_watch.market_cap` و fallbackهای قیمت |
| وابستگی تابلو به تاریخچهٔ قیمت | `api/market.py` علاوه بر `market_watch`، تاریخچهٔ `price_history`، حقیقی/حقوقی و تاریخچهٔ نشست را می‌خواند |
| تاریخچهٔ پرچم‌های تابلو | `api/market.py` فعلاً `tape_flag_history` را در `user.db` ثبت می‌کند تا با جایگزینی baseline از بین نرود |
| snapshot کدال | `api/_sync_codal.py` فایل مستقل `codal.db.lzma` را می‌گیرد، اما `_merge_codal_snapshot()` جدول‌های Codal را داخل `market.db` ادغام می‌کند؛ پس فایل snapshot مستقل است، نه بانک عملیاتی مستقل |

**نتیجه:** در حال حاضر یک اتصال `DB_PATH` برای سه دامنه استفاده می‌شود. جدا کردن فقط نام فایل‌ها بدون بازطراحی اتصال‌ها، کوئری‌ها و مالکیت جدول‌ها باعث شکست کدهای موجود خواهد شد.

---

## ۳. مالکیت پیشنهادی جدول‌ها

### ۳.۱ `fundamental.db` — Codal + Fundamental

**دادهٔ ورودی و canonical:**
- `codal_notices` و `codal_extracted`
- `financial_statements`
- `monthly_sales`
- فرادادهٔ واحد/دوره/نسخهٔ canonical و تاریخ انتشار واقعی

**عملیات ingest و پردازش:**
- `pipeline_cursor`، `pipeline_runs`، `pipeline_dirty`، `pipeline_lock`
- وضعیت استخراج، retry، checkpoint و سلامت worker کدال
- رجیستری تغییرات بنیادی که باید باعث محاسبهٔ مجدد نماد شوند

**خروجی بنیادی:**
- `fts_results` و snapshot پنج شاخص کانونیکال
- نتایج محاسبهٔ بنیادی، وضعیت قابل‌محاسبه/ناموجود و دلایل رد/قبول
- طبقه‌بندی‌های مختص منطق بنیادی، مانند pricing-mode، اگر مالکیت آن‌ها مختص FTS باشد

پیشنهاد می‌کنم در گام اول Codal خام/استخراج‌شده و نتایج بنیادی در **یک فایل فیزیکی `fundamental.db` اما در جدول‌ها و لایه‌های repository جدا** باشند. هر دو یک چرخهٔ ingest → canonicalize → recalculate → publish دارند. جدا کردن آن‌ها به دو فایل، قبل از اثبات نیاز به استقلال انتشار یا امنیت/حجم متفاوت، پیچیدگی join و نسخه‌بندی را بالا می‌برد.

**وابستگی بیرونی:** محاسبهٔ FTS می‌تواند به ارزش بازار و شناسهٔ نماد نیاز داشته باشد؛ این ورودی‌ها را از `tape.db` و `reference.db` به‌صورت read-only می‌گیرد. نتیجهٔ بنیادی باید `as_of`، زمان ارزش بازار و revision منابع را ثبت کند تا نتیجهٔ قدیمی به‌عنوان نتیجهٔ تازه نمایش داده نشود.

### ۳.۲ `tape.db` — Tape Reading / Microstructure

**دادهٔ زنده و تاریخی مختص تابلو:**
- `market_watch` (آخرین snapshot جاری نمادها)
- `client_type` و `client_type_value` (حقیقی/حقوقی و ارزش خرید/فروش)
- `order_book` (عمق سفارش)
- `tape_history` و `tape_history_state` (پنجرهٔ تاریخی اختصاصی TSETMC برای فرمول‌های تابلو)
- `tape_ih_slot`، `tse_inst_stat` و جدول‌های وضعیت/صف متناظر
- `mstat_snap` و snapshotهای تجمیعی وضعیت/نبض بازار
- `tape_flag_day` و `tape_flag_day_meta` (تاریخچهٔ هفت فیلتر تابلو)
- وضعیت‌های نظارت، توقف، پیام‌ها و metadata مربوط به فید TSETMC

**نکتهٔ مالکیت:** تاریخچهٔ `tape_flag_day` از نظر معنا دادهٔ تابلو است، نه تنظیم شخصی کاربر. در معماری هدف باید از `user.db` به `tape.db` منتقل شود؛ اما چون این تاریخچه فقط از زمان شروع ثبت قابل اتکاست، مهاجرت آن باید row-count/fingerprint داشته باشد و هیچ روزِ ثبت‌نشده‌ای با دادهٔ امروز بازسازی نشود.

### ۳.۳ `technical.db` — Price History / Technical Intelligence

**منبع حقیقت قیمت:**
- `price_history` با قرارداد `candle_contract.py` و مبنای `price_basis.py`
- `daily_prices` به‌عنوان دادهٔ نشست/منبع خام TSETMC برای ساخت و تکمیل سری قیمت
- تاریخچهٔ OHLCV، قیمت پایانی/آخرین قیمت و منشأ هر ردیف
- رویدادهای تعدیل و تغییر سرمایه‌ای که برای ساخت قیمت تعدیل‌شده لازم‌اند: `adjust_events`، `price_adjust_events`، `share_change_events`، `fund_profit_events`، `stock_dividend_events`
- شاخص‌ها و ویژگی‌های قیمت/حجم که از همین سری مرجع محاسبه می‌شوند؛ مانند ATR، بازده‌ها، نوسان تاریخی، سوئینگ و ساختار قیمت، مشروط به داشتن schema/version و `as_of`

**قاعدهٔ مهم:** تکنیکال مالک تاریخچهٔ قیمت است. تابلوخوانی ممکن است برای فرمول‌هایی مثل نسبت حجم امروز به میانگین ۳۰ نشست، به تاریخچهٔ حجم نیاز داشته باشد؛ اما آن سری نباید در `tape.db` دوباره کپی شود. `tape.db` از یک interface مشترک مانند `TechnicalRepository.rolling_volume(...)` یا snapshot ویژگیِ versioned می‌خواند.

### ۳.۴ `reference.db` — هویت مشترک نماد

- کلید پایدار `ins_code`
- نگاشت `l_val18`، `l_val30`، ISIN و نام‌ها/aliasهای فارسی و تاریخی
- صنعت و مشخصات مرجع مشترک
- نگاشت تالار/بازار در صورت تأیید مالکیت مرجع

`reference.db` نباید snapshot قیمت یا queue داشته باشد. دادهٔ متغیر نشست در `tape.db` و OHLCV در `technical.db` می‌ماند. هیچ‌کدام از بانک‌های دامنه‌ای نباید یک کپی مستقل و قابل‌ویرایش از «هویت نماد» بسازند.

### ۳.۵ `user.db` و `analytics.db`

- `user.db`: تنظیمات، watchlists، selection decisions و ترجیحات/نمایش کاربر. بانک baseline دادهٔ بازار نباید آن را overwrite کند.
- `analytics.db` (مرحلهٔ بعد): `feature_snapshot` نقطه‌درزمان، پنج رژیم تاریخی، پیش‌بینی volatility/risk و direction/return، رجیستری algorithm/experiment و مانیفست‌ها. تا وقتی این قابلیت‌ها ساخته نشده‌اند، فایل خالی یا اضافی ایجاد نمی‌کنیم.

---

## ۴. داده‌های واقعاً مشترک بین تکنیکال و تابلوخوانی

این قسمت باید با دقت طراحی شود؛ اشتراک در مصرف به معنی مالکیت مشترک یا تکرار داده نیست.

| داده/ویژگی | مالک کانونیکال | مصرف‌کنندگان |
|---|---|---|
| کندل و OHLCV روزانه | `technical.db` | نمودار و الگوریتم‌های تکنیکال؛ تابلوخوانی برای زمینهٔ حجم/قیمت |
| بازده‌های ۱/۵/۲۰ نشست و میانگین‌های حجمی تاریخی | محاسبه بر اساس `technical.db`؛ در صورت materialize شدن، با revision/schema مشخص | تکنیکال، فیلترهای حجمی تابلو، رژیم بازار |
| ATR، realized volatility، نوسان تاریخی | `technical.db` | تکنیکال و مدل ریسک/پیش‌بینی |
| قیمت و حجم جاری، معاملات و ریزساختار | `tape.db` | تابلوخوانی، نمایش قیمت زنده، context بنیادیِ ارزش بازار |
| قدرت خریدار/فروشنده و تغییر مالکیت حقیقی/حقوقی | `tape.db` | تابلوخوانی و featureهای مشترک بعدی؛ نه به‌عنوان تاریخچهٔ ساختگی OHLCV |
| شناسه و alias نماد | `reference.db` | همهٔ دامنه‌ها |
| صورت مالی، فروش ماهانه و پنج شاخص بنیادی | `fundamental.db` | بنیادی و گیت رسمی FTS |

**نمونهٔ مشترک واقعی:** فیلتر «حجم مشکوک» هم حجم امروز از تابلو می‌خواهد و هم مبنای تاریخی ۳۰ نشست. حجم امروز در `tape.db` است؛ میانگین تاریخی از دادهٔ کانونیکال `technical.db` می‌آید. تابع فیلتر در لایهٔ tape می‌ماند، اما تاریخچهٔ قیمت/حجم را دوباره ذخیره نمی‌کند.

---

## ۵. الگوی دسترسی و تراکنش

### ۵.۱ یک Data Access Layer؛ چند فایل مستقل

همهٔ ماژول‌ها نباید مستقیم `sqlite3.connect(DB_PATH)` یا مسیر فایل را خودشان انتخاب کنند. یک registry و connection factory مرکزی تعریف می‌شود:

- `get_fundamental_db()`
- `get_tape_db()`
- `get_technical_db()`
- `get_reference_db()`
- `get_user_db()`
- read-only multi-domain connection برای queryهایی که واقعاً join لازم دارند

APIها و موتورهای دامنه‌ای از repository استفاده می‌کنند؛ برای نمونه:
- `CodalRepository` / `FundamentalRepository`
- `TapeRepository`
- `TechnicalRepository`
- `InstrumentRepository`

برای readهای چنددامنه‌ای می‌توان از `ATTACH DATABASE` و aliasهای صریح مانند `fundamental.financial_statements` و `tape.market_watch` استفاده کرد؛ SQLite خواندن جدول‌های attached را پشتیبانی می‌کند. [SQLite ATTACH](https://www.sqlite.org/lang_attach.html)

اما `ATTACH` مجوزی برای بازسازی یک monolith پنهان نیست: نام جدول‌ها همیشه با schema prefix نوشته می‌شود و منطق business همچنان در repository دامنهٔ مالک می‌ماند.

### ۵.۲ قانون تراکنش

اتصال‌های فعلی از WAL استفاده می‌کنند. در WAL، تراکنش روی چند فایل attached به‌صورت مجموعه‌ای atomic نیست؛ تضمین atomicity فقط برای هر فایل جداگانه برقرار می‌ماند. [SQLite WAL](https://www.sqlite.org/wal.html) · [SQLite ATTACH transaction note](https://www.sqlite.org/lang_attach.html)

بنابراین:
- هر worker فقط بانک دامنهٔ خودش را می‌نویسد و commit می‌کند.
- هیچ عملیات عادی، transaction نوشتن را میان `fundamental.db` و `tape.db` یا `technical.db` پخش نمی‌کند.
- تغییرات بین‌دامنه‌ای با `revision/outbox/dirty marker` و پردازش idempotent منتقل می‌شوند؛ نه با فرض commit اتمیک چند فایل.
- نتیجهٔ مشتق‌شده، revision و `as_of` ورودی‌هایش را نگه می‌دارد تا ناسازگاری زمانی قابل تشخیص باشد.

### ۵.۳ freshness و revision

هر بانک جدول `db_meta` یا معادل آن را دارد:
- `schema_version`
- `data_revision`
- `source`
- `updated_at`
- `as_of` یا آخرین نشست/دورهٔ معتبر
- `snapshot_id` و checksum در صورت دریافت baseline

UI و API نباید با تازه بودن یک بانک، freshness بقیه را نتیجه‌گیری کنند. بنیادی، تابلو و تکنیکال هرکدام freshness و health مستقل دارند.

---

## ۶. راهبرد مهاجرت — بدون شکستن مسیر فعلی

**مهاجرت باید additive، قابل بازگشت و مبتنی بر شواهد باشد.** حذف `market.db` یا dual-write طولانی‌مدت مجاز نیست.

| مرحله | محدوده | خروجی و گیت پذیرش |
|---|---|---|
| **۰** | Table ownership & dependency inventory | فهرست تمام جدول‌ها، DDLها، writerها، readerها، queryهای cross-domain، snapshotها و تست‌ها؛ هر جدول دقیقاً یک مالک |
| **۱** | DB registry و repository contracts | مسیرهای مستقل و connection factory با `BORS_*_DB`؛ هنوز هیچ جدول عملیاتی جابه‌جا نمی‌شود؛ `BORS_DB` فقط compatibility override موقت |
| **۲** | ساخت shadow DBها | کپیِ read-only از جدول‌های هر دامنه به فایل مستقل؛ منبع قدیمی دست‌نخورده؛ fingerprint و schema hash برای هر جدول |
| **۳** | جداسازی technical | مهاجرت `price_history`، `daily_prices` و eventهای تعدیل؛ parity چارت/کندل، قیمت تعدیل‌شده، API و مقایسهٔ Rahavard |
| **۴** | جداسازی tape | مهاجرت `market_watch`، حقیقی/حقوقی، order book، tape history و flag history؛ parity فرمول‌ها، freshness، polling و delta |
| **۵** | جداسازی Codal/fundamental | انتقال Codal pipeline، canonical FS/MS و `fts_results`; جداشدن snapshot کدال از `market.db`؛ parity پنج شاخص، publish-date، اصلاحیه و گزارش سلامت |
| **۶** | جداسازی reference و پاک‌سازی اتصال‌ها | مرجع واحد هویت نماد، حذف queryهای مستقیمِ وابسته به monolith، ثبت گیت‌های startup/backup/restore |
| **۷** | analytics store (وقتی لازم شد) | ایجاد `analytics.db` فقط همراه Feature Store، regime history، forecastها و experiment registry |

### معیارهای لازم برای هر cutover

1. row-count، کلیدهای اصلی و fingerprint منطقی هر جدول مبدأ/مقصد با هم تطبیق کنند.
2. هیچ ردیف یکتا حذف نشود؛ ردیف‌های تکراری فقط با قاعدهٔ canonical مستند حل شوند.
3. تمام writerها به بانک مالک هدایت شده باشند؛ «نوشتن دوگانه» به‌عنوان راه‌حل دائمی پذیرفته نیست.
4. خروجی‌های `/api/chart`، `/api/market`، `/api/fts` و screener روی یک snapshot ثابت با نسخهٔ monolith مقایسه شوند؛ null/missing/stale و زمان `as_of` هم جزو parity است.
5. sync و backfill کدال، refresh تابلو، client-type، order-book، corporate action و startup در صورت قطع/خرابی یک بانک آزموده شوند.
6. backup/restore مستقل هر فایل و restore کامل مجموعه با manifest نسخه‌ها آزموده شود.
7. rollback به `market.db` قدیمی با یک تغییر پیکربندی ممکن باشد؛ منبع قدیمی تا پایان دورهٔ تثبیت حذف نشود.

---

## ۷. موانع و ریسک‌هایی که باید پیش از پیاده‌سازی حل شوند

- **SQLهای تک‌اتصالی:** `api/fundamental.py`، `fts_engine.py` و `api/market.py` queryهایی دارند که حالا از جدول‌های چنددامنه در همان `market.db` join می‌گیرند. این‌ها باید به repository/read model تبدیل شوند.
- **تک‌منبع بودن schema:** `codal_fetcher.create_schema()` و `test_tsetmc.create_schema()` هر دو در بانک فعلی جدول‌های خود را می‌سازند؛ پس ابتدا مالکیت DDL و migrationها باید منتقل شود.
- **Codal snapshot merge:** `api/_sync_codal.py` هنوز snapshot کدال را در `market.db` merge می‌کند؛ مسیر انتشار، امضا، freshness و update باید به `fundamental.db` تغییر کند.
- **تاریخچهٔ شخصی تابلو:** `tape_flag_day` فعلاً در `user.db` نوشته می‌شود. انتقال آن باید حفظ سابقهٔ قابل اعتماد را تضمین کند.
- **WAL و چندفایلی:** transactionهای cross-db را atomic فرض نکنید؛ هر دامنه commit مستقل دارد.
- **فضای دیسک و بسته‌بندی:** baselineهای مستقل، نصب، آپدیت، migration، backup و restore باید با footprint کل سنجیده شوند؛ تعداد فایل بیشتر به‌تنهایی به معنی سبک‌تر یا سریع‌تر نیست.

## جمع‌بندی

**بله، جداسازی بنیادی/Codal، تابلوخوانی و تکنیکال تصمیم معماری درستی است؛ اما با یک مرجع مشترک نماد و یک لایهٔ دسترسی مرکزی.** مهم‌ترین مرز مشترک بین تابلو و تکنیکال، تاریخچهٔ قیمت/حجم است: مالکیت آن با `technical.db` می‌ماند و تابلو فقط از آن مصرف می‌کند. دادهٔ حقیقی/حقوقی، صف و snapshot زنده فقط در `tape.db` هستند. صورت‌های مالی و پردازش Codal در `fundamental.db` باقی می‌مانند و FTS خروجی بنیادی همان دامنه است.

این طرح هنوز **پیشنهاد هدف** است. قبل از هر پیاده‌سازی، inventory کامل writer/readerها و تصمیم نهایی مالک دربارهٔ مرزهای جدول‌ها لازم است.
