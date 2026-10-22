# RA365 Round 18 — Rahavard (type0) Raw OHLC Parity

**تاریخ:** 2026-10-22  
**شاخه:** `mission/ra365-round18-raw-ohlc-parity-2026-10-22`  
**مبنای Track A:** `f6e3c4e0`  
**Commit ابزار/تست این ممیزی:** `6b851f9c`  
**مرجع Rahavard:** snapshot منجمد `ref_bars_v2.jsonl` (۲۰۲۶-۱۰-۲۰)، type0 و type7 با resolution روزانه

> این گزارش مکمل گزارش اصلی `docs/RA365-ROUND18-RAW-OHLC-PARITY-REPORT.md` است. تمرکز آن فقط Raw OHLC در برابر Rahavard است؛ Track B و موتور الگو دست‌نخورده‌اند.

---

## ۰. پاسخ کوتاه

- **تمام ۲٬۵۹۵ دارایی** دارای type0 در snapshot، در cohort اندازه‌گیری شدند؛ **۱٬۱۹۲٬۰۷۱ تاریخ مشترک** و **۱٬۱۸۸٬۹۲۱ ردیف قابل‌مقایسه** (با last موجود) مقایسه شد.
- **تطبیق قراردادی Raw:** **۹۹٫۸۹۰۷٪** فیلد و **۹۹٫۸۲۲۱٪** ردیف.
- **تطبیق تحت‌اللفظی OHLC:** high ۹۱٫۷۰۴۳٪، low ۹۶٫۴۲۷۳٪، ردیف کامل ۸۷٫۶۱۰۱٪. اختلاف عمدتاً `widen()` مستند BorsTerminal است، نه خطای داده خام.
- **معنای type0 با oracle مستقل TSETMC اثبات شد:** close = LAST (۹۹٫۹۱۰۲٪)، نه official CLOSE (۱۴٫۰۷۶۰٪)؛ open = FIRST (۹۹٫۸۶۴۱٪)، نه base OPEN (۳٫۴۸۴۶٪).
- **هیچ اصلاح تولیدی موجه اثبات نشد**؛ تنها قرارداد مقایسه (widen با official CLOSE) اصلاح شد. داده‌های خام product در open/last/volume و H/L قراردادی با Rahavard سازگارند.

---

## ۱. Git و مرزها

- Track A روی `mission/ra365-round18-raw-ohlc-parity-2026-10-22` از `f6e3c4e0`.
- Track B در شاخه `mission/technical-pattern-engine-round18-2026-10-22` مستقل و دست‌نخورده است؛ هیچ فایل Track B در این ممیزی تغییر نکرد.
- دیتابیس عملیاتی و promoted فقط read-only استفاده شدند؛ SHA آن‌ها در پایان گزارش ثبت شده است.

---

## ۲. اثبات معنای type0

مقایسه type0 با TSETMC به‌عنوان oracle مستقل (نه جایگزین Rahavard) روی **۱٬۱۹۷٬۸۷۱** ردیف مشترک:

| فیلد type0 | مرجع TSETMC | exact٪ |
|---|---|---|
| close | LAST | ۹۹٫۹۱۰۲٪ |
| close | official CLOSE | ۱۴٫۰۷۶۰٪ |
| open | FIRST | ۹۹٫۸۶۴۱٪ |
| open | base OPEN | ۳٫۴۸۴۶٪ |
| high | HIGH | ۹۹٫۸۷۵۴٪ |
| low | LOW | ۹۹٫۸۹۸۶٪ |
| volume | VOL | ۹۹٫۸۸۴۷٪ |

**نتیجه:** type0 یک سری **خام** با close = آخرین معامله است، نه قیمت پایانی رسمی. هر مقایسه‌ای که type0 را با `closing` مقایسه کند، اختلاف ساختاری تولید می‌کند. type7 یک سری **تعدیل‌شده** است: close آن با type0 در **۸۸۰٬۷۹۲** ردیف مشترک تفاوت دارد.

ماتریس کامل: `artifacts/ra365/r18-rahavard/source-field-matrix-rahavard.csv`.

---

## ۳. پوشش واقعی

| شاخص | مقدار |
|---|---:|
| دارایی‌های cohort | ۲٬۵۹۵ |
| دارایی‌های دارای type0 | ۲٬۵۹۵ |
| ردیف‌های type0 | ۱٬۲۳۳٬۲۱۳ |
| ردیف‌های محصول | ۲٬۱۲۵٬۳۳۰ |
| تاریخ‌های مشترک | ۱٬۱۹۲٬۰۷۱ |
| ردیف قابل‌مقایسه (last موجود) | ۱٬۱۸۸٬۹۲۱ |
| last_null محصول | ۳٬۱۵۰ |
| محصول فقط داخل بازه type0 | ۲٬۱۷۰ |
| محصول فقط خارج بازه type0 | ۹۳۱٬۰۸۹ |
| type0 فقط داخل بازه محصول | ۱٬۸۴۶ |
| type0 فقط خارج بازه محصول | ۳۹٬۲۹۶ |
| ردیف‌های type0 تخت (O=H=L=C) | ۱۹۱٬۷۲۹ |
| ردیف‌های type0 با هندسهٔ نامعتبر | ۶۷۷ |

پوشش type0 فقط **۵۵٫۹۴٪** از کل کندل‌های محصول است؛ type0 برای بسیاری از دارایی‌ها از ۲۰۱۹/۲۰۲۰ آغاز می‌شود. بنابراین «Full Universe» در این گزارش یعنی **تمام دارایی‌ها و تمام ردیف‌های Rahavard قابل‌دسترسی**، نه تمام تاریخ محصول. ردیف‌های محصول خارج از بازهٔ type0 با قیمت مقایسه نشدند.

---

## ۴. نتیجهٔ تطبیق

### ۴-۱. قراردادی (پس از اعمال widen مستند)

| فیلد | مقایسه | exact | exact٪ | diff | null |
|---|---|---|---|---|---|
| Open (FIRST) | ۱٬۱۹۲٬۰۷۱ | ۱٬۱۹۰٬۹۰۷ | ۹۹٫۹۰۲۴٪ | ۱٬۰۷۵ | ۰ |
| High (parser contract) | ۱٬۱۹۲٬۰۷۱ | ۱٬۱۹۱٬۱۴۶ | ۹۹٫۹۲۲۴٪ | ۸۳۳ | ۰ |
| Low (parser contract) | ۱٬۱۹۲٬۰۷۱ | ۱٬۱۹۱٬۳۸۳ | ۹۹٫۹۴۲۳٪ | ۵۹۲ | ۰ |
| Close last trade | ۱٬۱۸۸٬۹۲۱ | ۱٬۱۸۸٬۳۸۳ | ۹۹٫۹۵۴۷٪ | ۴۸۵ | ۳٬۱۵۰ |
| Close display (basis) | ۱٬۱۹۲٬۰۷۱ | ۱٬۱۸۸٬۵۷۹ | ۹۹٫۷۰۷۱٪ | ۳٬۳۵۰ | ۰ |
| Volume | ۱٬۱۹۲٬۰۷۱ | ۱٬۱۹۱٬۰۶۷ | ۹۹٫۹۱۵۸٪ | ۸۳۵ | ۰ |

**جمع قراردادی:** ۹۹٫۸۹۰۷٪؛ **ردیف قابل‌مقایسه:** ۹۹٫۸۲۲۱٪ (۱٬۱۸۶٬۸۰۶ از ۱٬۱۸۸٬۹۲۱).

### ۴-۲. تحت‌اللفظی (بدون widen)

- high: **۹۱٫۷۰۴۳٪**؛ low: **۹۶٫۴۲۷۳٪**؛ ردیف کامل: **۸۷٫۶۱۰۱٪**.
- اختلاف بالا عمدتاً همان `widen()` است: product سایه را باز می‌کند تا body/close رسمی داخل آن باشد. contract-aware high/low به ۹۹٫۹۲۲۴٪ / ۹۹٫۹۴۲۳٪ می‌رسد. بنابراین «high خام برابر نیست» را نباید خطای دیتای خام نامید.

### ۴-۳. فیلدهای خاص

- `close_display` ۹۹٫۷۰۷۱٪: اختلاف ۲٬۹۲۳ فیلد عمدتاً برای ۷۱ دارایی با basis=closing است (نمایش official close در برابر close=last در type0)؛ `FIELD_MAPPING`، نه خطای raw.
- `open` ۹۹٫۹۰۲۴٪؛ `last` ۹۹٫۹۵۴۷٪؛ `volume` ۹۹٫۹۱۵۸٪.

---

## ۵. علت‌شناسی

### ردیف‌ها (۲٬۱۱۵ ردیف قابل‌مقایسه با mismatch)

| علت | دارایی | تاریخ | ردیف | سهم از mismatch |
|---|---|---|---|---|
| SOURCE_DATA_DIVERGENCE | 517 | 1110 | 1110 | ۵۲٫۴۸٪ |
| HISTORICAL_REVISION | 369 | 552 | 552 | ۲۶٫۱۰٪ |
| PRECISION_OR_ROUNDING | 220 | 299 | 299 | ۱۴٫۱۴٪ |
| UNCLASSIFIED | 76 | 86 | 86 | ۴٫۰۷٪ |
| CANDLE_GEOMETRY | 41 | 62 | 62 | ۲٫۹۳٪ |
| PARSING_OR_TRANSFORM | 6 | 6 | 6 | ۰٫۲۸٪ |

### فیلدها

| علت | دارایی | تاریخ | فیلد |
|---|---|---|---|
| FIELD_MAPPING | 71 | 2923 | 2923 |
| SOURCE_DATA_DIVERGENCE | 524 | 1218 | 2303 |
| HISTORICAL_REVISION | 380 | 636 | 1488 |
| PRECISION_OR_ROUNDING | 304 | 543 | 641 |
| CANDLE_GEOMETRY | 98 | 184 | 335 |
| UNCLASSIFIED | 88 | 100 | 101 |
| PARSING_OR_TRANSFORM | 15 | 15 | 15 |
| PRICE_SCALE_OR_UNIT | 5 | 5 | 5 |

**تفسیر:**
- `SOURCE_DATA_DIVERGENCE`: محصول با TSETMC مطابق است، type0 نیست؛ عمدتاً اراد/آپشن‌ها، flat bars و تاریخ‌های خاص.
- `HISTORICAL_REVISION`: type0 و TSETMC با هم می‌خوانند، snapshot محصول قدیمی‌تر/اصلاح‌شده است.
- `CANDLE_GEOMETRY`: type0 تخت یا H/L بیرون body؛ product با widen آن را ترمیم می‌کند.
- `FIELD_MAPPING`: فقط `close_display` با basis=closing؛ انتظار می‌رود.
- `PRECISION_OR_ROUNDING`: اختلاف‌های کوچک مستند.
- `PARSING_OR_TRANSFORM`: volume صفر product در چند ردیف.
- `PRICE_SCALE_OR_UNIT`: پنج ردیف آپشن/صندوق با مقیاس واحد متفاوت.
- `UNCLASSIFIED`: 101 فیلد؛ عمدتاً اختلاف‌های کوچک بدون شاهد کافی برای یک علت واحد.
- `INSTRUMENT_MAPPING` و `DATE_MAPPING` به‌صورت اثبات‌شده **صفر**؛ type0-only tradable ۱٬۸۴۴ تاریخ است که ۱٬۳۴۵ مورد آن Rahavard-only و ۴۹۹ مورد omission محصول است.

---

## ۶. missing bar و پوشش

- **۴۹۹** ردیف type0 معتبر که محصول snapshot ندارد؛ ۱۵۳ در ۲۰۲۳-۰۳-۲۷ و ۲۸۴ در تاریخ‌های ۲۰۲۶-۱۰-۱۰/۱۳/۱۷/۱۸. بررسی زنده نشان داد pipeline فعلی این تاریخ‌ها را دارد؛ این یک **gap در snapshot محصول** است، نه نقص فعلی دریافت.
- **۱٬۸۸۳** ردیف product معتبر که type0 ندارد (`PRODUCT_ONLY_RAHAVARD_OMISSION`)؛ reference gap.
- **۱٬۳۴۵** تاریخ type0-only که TSETMC هم ندارد (`TYPE0_ONLY_RAHAVARD_DATE`)؛ تقویم/داده Rahavard.
- **۳۹٬۲۹۶** تاریخ type0 خارج از بازه محصول؛ مقایسه نشد.
- **۲۰۴** product-only no-trade و **۲** type0-only no-trade؛ در درصد قیمت وارد نشدند.
- **۳٬۱۵۰** ردیف product بدون last؛ از denominator ردیف قابل‌مقایسه خارج شدند و جدا گزارش شده‌اند.

هیچ missing bar با صفر، forward-fill یا کندل ساختگی پر نشد.

---

## ۷. جداسازی لایه‌ها

| لایه | نتیجه | وضعیت |
|---|---|---|
| Raw product ↔ type0 (قراردادی) | ۹۹٫۸۹۰۷٪ فیلد / ۹۹٫۸۲۲۱٪ ردیف | `VERIFIED` |
| Raw product ↔ type0 (تحت‌اللفظی) | high ۹۱٫۷۰۴۳٪ / low ۹۶٫۴۲۷۳٪ | `VERIFIED` (شامل widen) |
| type0 ↔ type7 | ۸۸۰٬۷۹۲ ردیف diff | `VERIFIED` (type7 adjusted) |
| Factor (R17) | ۶۹٫۰۲۴۳٪ exact | `VERIFIED` (artifact R17) |
| Adjusted OHLC (R17) | ۶۸٫۳۰۴۵٪ | `VERIFIED` (artifact R17) |

`close_official_diff` = ۹۴۸٬۱۲۳ ردیف؛ این عدد عمداً به‌عنوان «خطای raw» گزارش نمی‌شود، چون product `closing` رسمی را با type0 `last` مقایسه می‌کند.

---

## ۸. اصلاح، محدودیت و وضعیت

**اصلاح انجام‌شده (analysis contract):** در comparator قبلی، widen با type0 close انجام می‌شد و هزاران اختلاف را اشتباهاً `HISTORICAL_REVISION` می‌نامید. اکنون widen با **official CLOSE مستقل** انجام می‌شود و high_raw/low_raw به ۹۹٫۹۲۲۴٪/۹۹٫۹۴۲۳٪ رسیده‌اند.

**اصلاح production انجام نشد**، چون هیچ علت عمومی اثبات‌شده در pipeline فعلی پیدا نشد: gapهای ۴۹۹تایی snapshot در pipeline زنده وجود ندارند و flat/geometry مربوط به منبع Rahavard است. هیچ شرط یا مقدار مخصوص نمادی اضافه نشد.

**محدودیت‌ها:**
- مرجع، snapshot منجمد Rahavard است؛ دسترسی live در این راند استفاده نشد (`BLOCKED_LIVE_ACCESS` در حد عدم استفاده، نه ادعای نبود دسترسی).
- type0 فقط ۵۶٪ کندل‌های محصول را پوشش می‌دهد؛ Full-Universe برای ردیف‌های قابل‌دسترسی، نه کل تاریخ محصول.
- ۸۶ ردیف / ۱۰۱ فیلد `UNCLASSIFIED` باقی مانده‌اند.
- ۵ ردیف price-scale آپشن/صندوق و flat bars منبع، بدون اصلاح تولید.
- `INSTRUMENT_MAPPING` اثبات‌شده‌ای در این pass پیدا نشد؛ اتهام mapping بدون شاهد ثبت نشد.

---

## ۹. تست‌ها، دیتابیس و artifactها

- `dev/test_rahavard_raw_parity_v1.py`: **۱۵/۱۵** بررسی (widen با official close، status، taxonomy، semantics واقعی).
- Full gate این راند دوباره اجرا نشد چون هیچ کد production تغییر نکرد؛ گیت Track A قبلی روی `f6e3c4e0` سبز بود. این محدودیت `NOT_RE-RUN` است، نه ادعای سبز جدید.
- دیتابیس عملیاتی و promoted read-only؛ SHA پایان در manifest/پاسخ نهایی ثبت می‌شود.

| artifact | bytes | sha256 |
|---|---|---|
| `rahavard-raw-ohlc-parity.csv` | ۵۹۰٬۲۷۱ | `b3596cc76003b9d21af5ccb33dd3bc3eaf352b052c421ef8aa81aa6b842a31f0` |
| `rahavard-type0-vs-tsetmc.csv` | ۲۵۳٬۶۷۰ | `caa9ba0e5c5474d5720026cb7d1efb539e767310e167d77f8903f6c4a7163b87` |
| `rahavard-raw-ohlc-field-mismatches.csv` | ۱٬۲۴۲٬۰۱۸ | `2090916b855bc57fd6a5037d490ace57c3f27c19dbf5781c4584fc8c437c0a9a` |
| `rahavard-raw-ohlc-taxonomy.csv` | ۳٬۰۹۰ | `10f554cb30a2bc7feb3454d5b22aa6c2873fc50db797c112afacae0740092101` |
| `rahavard-raw-ohlc-row-taxonomy.csv` | ۲۱۱ | `49d687ee0e287b8d8c142321d436a210b1516ce94ff5340ae5381e0795a27697` |
| `rahavard-raw-ohlc-missing.csv` | ۴٬۱۹۹٬۸۲۴ | `61608a2dfdc02260c28f1bfeb399489714a5c0c74235c9345764a50a86d9cabd` |
| `rahavard-raw-ohlc-summary.json` | ۲٬۵۶۱ | `b723ecee22db6ed502f3579e82c8dd79091411dcb9d05a554a48f40351dae043` |
| `rahavard-raw-ohlc-cohort-manifest.json` | ۵٬۴۵۴ | `252375822dc2c24bf9ddb1a4a7c501164f5a0b79a40f2f9111ac9db40acba8ae` |
| `source-field-matrix-rahavard.csv` | ۲٬۹۹۰ | `56b2270ee5b054c0638fec576195aa5cc7501e2fd207f3b39d75caf62c81e5f5` |

---

## ۱۰. جمع‌بندی

برای ردیف‌های Rahavard قابل‌دسترسی، OHLC خام محصول از نظر **open، last و volume** و H/L پس از transform مستند، تطبیق بسیار بالایی دارد. اختلاف high/low تحت‌اللفظی عمدتاً widen است؛ اختلاف‌های باقی‌مانده به flat/geometry منبع Rahavard، basis نمایش، اصلاح snapshot و چند مورد کوچک تقسیم می‌شوند. هیچ شاهد کافی برای یک اصلاح عمومی production به دست نیامد.
