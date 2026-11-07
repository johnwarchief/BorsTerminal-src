# RA365 Round 20 — Raw & Performance-Adjusted Parity

**تاریخ:** 2026-10-23  
**شاخه:** `mission/ra365-round20-raw-performance-adjusted-2026-10-23`  
**مبنا:** `a36f4b0b` (Round 19 Track A)  
**HEAD گزارش:** `b3d1686153c0`  
**Commit ابزار/تست/شواهد این راند:** `c1f0cb78` + `b3d16861`  
**Gate:** `VERIFIED`

> این گزارش دو حالت را **کاملاً جدا** می‌سنجد: (۱) OHLCV خام در برابر `type0` ره‌آورد، (۲) کندل تعدیل عملکردی در برابر `type7`. موفقیت در یکی، اثبات دیگری نیست. هیچ قیمت، کندل، تاریخ، تلورانس یا مخرجی برای بهترشدن عدد تغییر نکرد. Track B (موتور الگوها/بهینه‌سازی) در شاخهٔ جدا و دست‌نخورده است.

---

## ۰. پاسخ کوتاه

- **Raw منجمد (همان cohort Round 19):** **۹۹٫۸۹۰۷٪** فیلد و **۹۹٫۸۲۲۱٪** ردیف؛ **۱٬۱۸۸٬۹۲۱** ردیف قابل‌مقایسه. تطبیق exact ۱۰۰٪ **حاصل نشد**.
- **Raw زنده (نمونهٔ هدفمند ۵۰ نماد / ۱۰۱ فیلد بد):** **۷۰** فیلد از ۱۰۱ فیلد قبلاً بد، در دادهٔ زندهٔ فعلی با مرجع **منطبق شد**؛ **۰** regression در همین نمونه. یعنی بخشی از mismatchهای `HISTORICAL` کهنگی snapshot بود، نه باگ فعلی. کل Universe زنده به‌علت rate/CDN ناقص ماند (`NOT_MEASURED`).
- **Performance-Adjusted (type7):** **۶۹٫۰۲۴۳٪** تطبیق exact فاکتور، **۸۸٫۰۸۲۳٪** ±۱٪، **۶۸٫۳۰۴۵٪** OHLC عملکردی. این عدد پس از اصلاح runner (candle-closing) **بازتولید دقیق R17** است.
- **علت اصلی شکاف Adjusted:** event-set/فرمول مرجع، نه محاسبهٔ سادهٔ DPS/سهام. DPS و افزایش سرمایهٔ اندوخته‌ای **اثبات‌شده**اند؛ فرمول آورده/مطالبات به **S (قیمت پذیره)** نیاز دارد که در `timescale_marks` نیست و CODAL فقط بخشی را داد. بدون marks کامل ۲٬۵۹۵ دارایی، ۱۰۰٪ قابل‌اثبات نیست.
- **Volume در حالت عملکردی:** در **۱٬۲۳۳٬۲۱۳** ردیف مشترک روزانه (D) type0/type7، حجم مرجع **دقیقاً برابر** حجم خام است (۱۰۰٫۰۰٪). product هم حجم را با factor مقیاس نمی‌کند؛ سیاست مرجع «حجم بدون تغییر» است.
- **هیچ اصلاح production انجام نشد**، چون هیچ فرمول/دادهٔ اثبات‌شدهٔ جدیدی که اختلاف را کم کند و ریسک داده را توجیه کند پیدا نشد. دیتابیس عملیاتی/promoted تغییر نکردند.

---

## ۱. Git، دامنه و منابع

- شاخهٔ مستقل: `mission/ra365-round20-raw-performance-adjusted-2026-10-23`، ساخته‌شده از `a36f4b0b`.
- Track B در `mission/technical-pattern-engine-round18-2026-10-22` و commit `e066f003` دست‌نخورده.
- مرجع: snapshot منجمد `ref_bars_v2.jsonl` (type0/type7، ۲۰۲۶-۱۰-۲۰).
- محصول: snapshot `product_live_final_v4.jsonl` (۳٬۳۴۴ رکورد، ۲٬۵۹۵ دارایی cohort).
- دیتابیس promoted (فقط‌خواندنی): `market_r17_migrated.db`؛ دیتابیس عملیاتی فقط read-only.
- SHA دیتابیس‌ها در §۸.

| حالت | مخرج | تعریف |
|---|---|---|
| Raw | ۱٬۱۸۸٬۹۲۱ ردیف / ۷٬۱۴۹٬۲۷۶ فیلد | type0 خام، قرارداد widen با official CLOSE |
| Adjusted factor | ۱٬۱۸۷٬۹۴۵ تاریخ | `type7.close / type0.close` در برابر factor محصول |
| Adjusted OHLC | ۴٬۷۵۱٬۷۸۰ فیلد | OHLC خام × factor در برابر type7 |

---

## ۲. Raw — نتیجه، پوشش و باقی‌مانده

### ۲-۱. نتیجهٔ منجمد

- **قراردادی:** ۹۹٫۸۹۰۷٪ فیلد؛ **۹۹٫۸۲۲۱٪** ردیف (۱٬۱۸۶٬۸۰۶ از ۱٬۱۸۸٬۹۲۱).
- **تحت‌اللفظی:** high ۹۱٫۷۰۴۳٪، low ۹۶٫۴۲۷۳٪، ردیف ۸۷٫۶۱۰۱٪.
- **۲٬۱۱۵ ردیف mismatch** (کاملاً تعیین‌تکلیف‌شده در R19):

| علت ردیف | ردیف | دارایی |
|---|---|---|
| SOURCE_DATA_DIVERGENCE | ۱٬۱۵۰ | ۵۳۸ |
| HISTORICAL_REVISION | ۵۴۹ | ۳۶۸ |
| PRECISION_OR_ROUNDING | ۲۹۸ | ۲۱۹ |
| CANDLE_GEOMETRY | ۶۲ | ۴۱ |
| PARSING_OR_TRANSFORM | ۵۶ | ۴۸ |
| UNCLASSIFIED | ۰ | ۰ |

### ۲-۲. پوشش و missing

- type0: ۲٬۵۹۵ دارایی، ۱٬۲۳۳٬۲۱۳ ردیف؛ محصول ۲٬۱۲۵٬۳۳۰ ردیف؛ تاریخ مشترک ۱٬۱۹۲٬۰۷۱.
- ۲٬۱۷۰ ردیف فقط محصول داخل بازهٔ type0؛ ۹۳۱٬۰۸۹ ردیف خارج بازه؛ ۱٬۸۴۶ ردیف فقط type0 داخل بازه؛ ۳۹٬۲۹۶ خارج بازه.
- ۴۹۹ ردیف omission snapshot محصول؛ ۱٬۸۸۳ omission مرجع؛ ۱٬۳۴۵ تاریخ Rahavard-only؛ ۳٬۱۵۰ last-null؛ ۱۹۱٬۷۲۹ flat؛ ۶۷۷ هندسهٔ نامعتبر.
- هیچ missing با صفر/forward-fill پر نشد.

### ۲-۳. recheck زندهٔ Raw

- ۵۰ نماد اول cohort mismatch، **۱۰۱ فیلد** بد در snapshot؛ همان فیلدها از `get_chart_tsetmc` زندهٔ فعلی دوباره خوانده شدند.
- **۷۰ فیلد اکنون منطبق**، **۳۱ فیلد هنوز ناهمخوان**، **۰ regression**. تطبیق با همان تلورانسِ مطلق ۰٫۵ (و نسبیِ 1e-6) سنجیده شد. چون نمونه فقط از فیلدهای قبلاً بد انتخاب شده، «۰ regression» یعنی هیچکدام از همین ۱۰۱ فیلد بدتر نشد، نه نرخ regression در کل Universe.
- نتیجه: بخش قابل‌توجهی از `HISTORICAL` (و بخشی از `PARSING`) کهنگی snapshot محصول است؛ product زنده بهتر از snapshot منجمد است. این یک **بهبود داده‌ای قابل‌اندازه‌گیری** است، اما چون فقط نمونهٔ هدفمند است، درصد کل Universe زنده `NOT_MEASURED` می‌ماند. اجرای همهٔ نمادهای زنده به‌علت CDN/rate ناقص شد و متوقف شد؛ هیچ ادعای ۱۰۰٪ زنده نداریم.

### ۲-۴. چرا Raw ۱۰۰٪ نشد

| خانواده | علت | وضعیت |
|---|---|---|
| SOURCE ۱٬۱۵۰ | product با TSETMC می‌خواند، type0 Rahavard عدد دیگری دارد | `BLOCKED_SOURCE_REFERENCE` |
| HISTORICAL ۵۴۹ | snapshot محصول کهنه/اصلاح‌شده؛ نمونهٔ زنده بخشی را بست | `PARTIAL` / `NOT_MEASURED` برای کل |
| PRECISION ۲۹۸ | exact نیست، relative ≤ ۰٫۰۵٪؛ تلورانس تغییر نکرد | `VERIFIED_PRECISION_BAND` |
| CANDLE ۶۲ | type0 flat یا H/L بیرون body؛ product widen می‌کند | `BLOCKED_REFERENCE_GEOMETRY` |
| PARSING ۵۶ | ۶۰ فیلد open با FIRST=0 (fallback مستند) + ۳ فیلد volume صفر snapshot؛ ردیف‌های دارای فیلد هم‌زمان سه‌سنیبی به SOURCE رفتند | `BLOCKED_INDEPENDENT_SOURCE` |

**نتیجه:** ۱۰۰٪ Raw با داده‌های موجود و بدون تغییر منبع/تعریف مرجع قابل‌اثبات نیست. هیچ ردیف، تلورانس یا مخرجی برای نزدیک‌شدن به ۱۰۰٪ تغییر نکرد.

---

## ۳. Performance-Adjusted — نتیجه و علت‌شناسی

### ۳-۱. baseline بازتولیدشده

پس از اصلاح runner (پایهٔ DPS = پایانیِ کندل، نه close دیتابیس):

| سنجه | مقدار |
|---|---:|
| Factor exact (≤ 5e-4) | ۶۹٫۰۲۴۳٪ (۸۱۹٬۹۷۱ / ۱٬۱۸۷٬۹۴۵) |
| Factor ±۱٪ | ۸۸٫۰۸۲۳٪ |
| Factor نرمال‌شده exact | ۶۰٫۲۰۵۷٪ |
| OHLC عملکردی | ۶۸٫۳۰۴۵٪ (۳٬۲۴۵٬۶۷۸ / ۴٬۷۵۱٬۷۸۰) |
| step pairs | ۶٬۳۷۷ |
| step ratio mismatch (>۱٪) | ۱۴۸ |
| ref-only / prod-only steps | ۱۳۹ / ۱۷۷ |

> طبقه‌بندی: `MATCH` تساوی است؛ `ROUNDING_ONLY` برای قیمت یعنی اختلاف نسبی ≤۰٫۰۵٪ یا مطلق ≤۱ ریال، و برای factor یعنی ≤5e-4. این‌ها همان تلورانس‌های R17/R18 هستند و در این راند تغییر نکردند.

### ۳-۲. ۱۲۸ رویداد اختلافی (R8 event-pair audit)

| علت | تعداد | اقدام/وضعیت |
|---|---|---|
| NO_OFFICIAL_RATIO_ROW | ۷۰ | ۵۱ پیش از پوشش دفتر + ۱۹ بدون ردیف؛ مرجع marks لازم است |
| PRODUCT_USES_OFFICIAL_RATIO_REFERENCE_DIFFERS | ۲۶ | product به نسبت رسمی وفادار است؛ ورودی رویداد مرجع متفاوت است |
| REFERENCE_RATIO_DIFFERS_FROM_OFFICIAL | ۲۵ | مرجع با دفتر رسمی متفاوت است؛ فرمول/S مرجع اثبات نشده |
| OFFICIAL_ROW_CLOSER_THAN_PRODUCT | ۷ | رویداد مرکب (اجزای رسمی)؛ یک ردیف تنها نسبت کل نیست |

### ۳-۳. فرمول‌های اثبات‌شده و نیمه‌اثبات‌شده

روی ۱۸ نماد دارای `timescale_marks` (۱۰۹ ردیف oracle):

| گروه | تعداد | exact | ±۱٪ | وضعیت |
|---|---|---|---|---|
| DPS خالص | ۴۸ | ۴۶ | ۰ | PROVEN |
| افزایش سرمایهٔ اندوخته‌ای | ۴ | ۳ | ۰ | PROVEN |
| آورده/مطالبات | ۱۱ | ۰ | ۹ | UNVERIFIED (S) |

- **DPS:** `price_ratio = close_ex / (close_ex + DPS)`؛ ۴۶ گام خالص exact (<1e-6) از ۴۸؛ یک ردیف combined با capital و یک ردیف mismatch که با DPS خالص توضیح داده نمی‌شود.
- **اندوخته/جایزه:** `price_ratio = previous_capital / new_capital`؛ ۳ گام خالص exact؛ یک combined.
- **آورده/مطالبات:** ساختار `pv/nw + (1-pv/nw)*(cp/100)*(S/P)` با ۹/۱۱ گام در ±۱٪، **۰ exact**. `S` (قیمت پذیره) در marks نیست و فقط درصدها موجودند. بنابراین تولید نمی‌تواند آن را بدون شاهد اعمال کند.
- **Volume:** type0/type7 در **۱٬۲۳۳٬۲۱۳** ردیف مشترک روزانه (D) volume یکسان دارند (۱۰۰٫۰۰٪)؛ product حجم را مقیاس نمی‌کند. رفتار حجم مرجع مستند است.

### ۳-۴. CODAL و محدودیت دسترسی

- برای ۵۶ رویداد سهامِ نزدیک به mismatch، CODAL عمومی جست‌وجو شد: **۳** ترکیب کامل، **۴۶** خطای HTTP/rate، **۱** خطای شبکه، **۶** بی‌نامه/ناقص.
- سه ترکیب کامل (تفارس، خنور، تاپ‌كيش) برای آزمون ساختاری استفاده شد؛ تفارس/خنور به `S` و event-set مرجع نیاز دارند. CODAL نرخ‌محدود شد و درخواست بیشتر بدون backoff ارسال نشد.
- `timescale_marks` ره‌آورد بدون نشست لاگین‌شده **403** می‌دهد؛ marks کامل ۲٬۵۹۵ دارایی در دسترس نیست. این **BLOCKED_REFERENCE_MARKS** است، نه یک باگ product.

### ۳-۵. تصمیم مهندسی

**هیچ تغییر فرمول production اعمال نشد.** دلیل: `S` پذیره و event-set مرجع برای اکثریت رویدادها قابل‌استخراج نیست؛ اعمال فرمول با `S=1000` یا حدس، داده را برای رسیدن به عدد ۱۰۰٪ تغییر می‌دهد و ممنوع است. product فعلی روی DPS و اندوخته طبق فرمول اثبات‌شده کار می‌کند و باقی اختلاف‌ها به ورودی مرجع محدود است.

---

## ۴. تجمیع زمانی، تایم‌فریم و حجم

- baseline این راند روزانه (`D`) است؛ بازهٔ مشترک و تمام ردیف‌های قابل‌مقایسه پوشش داده شد.
- `W` در snapshot موجود است اما در این راند بازاندازه‌گیری نشد: `NOT_MEASURED`. تجمیع هفتگی باید با همان مرز جلسه و همان سقف/کف/باز/بسته در راند بعد سنجیده شود.
- حجم در حالت performance-adjusted توسط مرجع مقیاس **نمی‌شود** (۱۰۰٫۰۰٪ برابری روزانهٔ type0/type7)، بنابراین سیاست product (بدون تغییر حجم) درست است. volume raw exact ۹۹٫۹۱۵۸٪ (۱٬۱۹۱٬۰۶۷ / ۱٬۱۹۲٬۰۷۱، از R18) و mismatchهای حجم از raw منبع/دقت می‌آید، نه از ضریب.

---

## ۵. تست‌ها، gate و دیتابیس

- `tools/ra365_round15_parity.py`: مسیر DPS اصلاح شد تا `closings` را بپذیرد و **پایانیِ کندل** (نه close دیتابیس) را مبنا بگیرد؛ خطای `TypeError` و اختلافِ ناشی از close محلی برطرف شد.
- `tools/ra365_round16_parity.py --candle-closing`: baseline authoritative را تولید کرد و **۶۹٫۰۲۴۳٪** را دقیقاً بازتولید R17 کرد (`method=candle_closing=True`).
- `dev/test_ra365_round20_formula_oracle_v1.py`: **۸/۸** (DPS، اندوخته، ساختار آورده، رد S نامعلوم).
- `tools/ra365_round20_marks_oracle.py`: ۱۸ نماد / ۱۰۹ ردیف؛ artifact: `marks-oracle.csv/json`.
- `tools/ra365_round20_live_raw_recheck.py`: نمونهٔ ۵۰ نماد / ۱۰۱ ردیف؛ artifact: `live-raw-recheck.csv` + archive خام `live-raw-cache.tar.gz`.
- `tools/ra365_round20_reference_invariants.py`: بازتولید مستقل volume روزانه type0/type7 و شمارش snapshot محصول؛ artifact: `reference-volume-parity.json` / `product-snapshot-count.json`.
- Full gate: `VERIFIED` — ۱۴۶ suite counted، ۴۴ silent، ۲ skipped؛ PROTECTED_DB_UNCHANGED (`artifacts/ra365/r20/full-gate.log`). دو skip فیکسچرِ شناخته‌شده (`_audit/ra365_ref_bars.json`, `market.db.lzma`) است، نه شکست تست.
- دیتابیس عملیاتی SHA `7b933b05d03b8a2f9383f901faf6b2c34f1500e70619d6cc5c8039f171b1848c` و promoted SHA `8fb85f381317634430cae429bd9775eba0a364b692e0868b4d9b17dbbcc6c17f`؛ فقط read-only، بدون تغییر.
- Track B: هیچ فایل/تست/benchmark آن در این راند تغییر نکرد.

---

## ۶. وضعیت پذیرش

| معیار | نتیجه |
|---|---|
| Raw ۱۰۰٪ همهٔ فیلدها/ردیف‌ها | **خیر** — ۹۹٫۸۹۰۷٪ / ۹۹٫۸۲۲۱٪ منجمد؛ live نمونه ۶۹٫۳۱٪ |
| Performance-Adjusted ۱۰۰٪ | **خیر** — ۶۸٫۳۰۴۵٪ OHLC؛ factor ۶۹٫۰۲۴۳٪ |
| Volume مطابق مرجع | **VERIFIED** — type0/type7 volume روزانه در ۱٬۲۳۳٬۲۱۳ ردیف برابر (۱۰۰٫۰۰٪) |
| موارد بدون شاهد | `BLOCKED_REFERENCE_MARKS` / `BLOCKED_SOURCE_REFERENCE` / `NOT_MEASURED` |
| mismatch پنهان‌شده | صفر؛ هیچ ردیف/تلورانس/مخرجی تغییر نکرد |

---

## ۷. اقدام‌های بعدی با شاهد مشخص

1. **marks کامل ۲٬۵۹۵ دارایی** با نشست مجاز مالک یا export رسمی ره‌آورد؛ بدون آن ۱۰۰٪ Adjusted قابل‌اثبات نیست.
2. **S پذیره** برای رویدادهای آورده/مطالبات: CODAL صورت‌جلسه/آگهی ثبت با backoff و checkpoint؛ ۵۶ رویداد هدفمند.
3. **Raw live full**: همهٔ نمادها با rate limit و cache؛ نمونهٔ ۵۰ نمادی ۶۹٫۳٪ بهبود داد؛ کل Universe باید با manifest زمان‌دار ثبت شود.
4. **Weekly aggregation** و مرز جلسه؛ `NOT_MEASURED` فعلی.
5. **Fund/ETF monthly** formula (R8) در صورت ورود به cohort این راند؛ فعلاً از promoted DB جدا است.

---

## ۸. Git، commit و artifactها

- مبنا `a36f4b0b`; ابزار/تست/artifact: `c1f0cb78`.
- گزارش/checkpoint: commit جداگانه.
- هیچ push/merge به `main` انجام نشد.
- SHAها و artifactها:

| artifact | bytes | sha256 |
|---|---|---|
| `adjusted-baseline-candle/parity_summary.json` | ۱٬۲۶۹ | `d7fe45ba4daab510…` |
| `adjusted-baseline-candle/parity_steps.csv` | ۴۶۴٬۶۱۹ | `a144c2137c68fe28…` |
| `adjusted-baseline-candle/parity_symbols.csv` | ۲۲۷٬۸۳۷ | `db5fbd640f000efb…` |
| `live-raw-recheck.csv` | ۸٬۸۰۵ | `ce59efbe118f2c3f…` |
| `live-raw-recheck-summary.json` | ۲۰۸ | `44c3ca8936abb145…` |
| `live-raw-cache.tar.gz` | ۲٬۳۶۰٬۶۷۲ | `61aca01a2f5294e1…` |
| `marks-oracle.csv` | ۹٬۷۲۷ | `509f1c4fbd530ede…` |
| `marks-oracle.json` | ۶۶۰ | `970deccbcaf7b5ef…` |
| `share-composition.jsonl` | ۲۳٬۰۱۲ | `9828f267a0909c04…` |
| `share-events.csv` | ۷٬۴۸۸ | `6e9bcdf47a78d243…` |
| `rahavard-marks-18.json` | ۲۱٬۱۷۱ | `2ac50d7b02dec97a…` |
| `product-snapshot-count.json` | ۱۸۳ | `e8c3ca484ed4b666…` |
| `reference-volume-parity.json` | ۷۹ | `27e6d8230e07b950…` |
| `full-gate.log` | ۲۶٬۱۹۴ | `b0f204f37d9be8f8…` |

**دستور پایانی:** این گزارش ۱۰۰٪ را ادعا نمی‌کند. بخش Raw منجمد تثبیت شد و نمونهٔ زنده بخشی از کهنگی snapshot را بست؛ بخش Adjusted با فرمول‌های اثبات‌شده (DPS/اندوخته) بازتولید شد و شکاف باقی‌مانده به **marks/S مرجع** محدود است. هیچ داده‌ای برای سبزکردن عدد تغییر نکرد.
