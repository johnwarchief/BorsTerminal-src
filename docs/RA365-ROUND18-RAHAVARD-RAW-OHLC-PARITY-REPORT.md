# RA365 Round 18 — Rahavard (type0) Raw OHLC Parity

**تاریخ:** 2026-10-22  
**شاخه:** `mission/ra365-round18-raw-ohlc-parity-2026-10-22`  
**مبنای Track A:** `f6e3c4e0`  
**Commit ابزار/تست این ممیزی:** `4305ab58`  
**مرجع Rahavard:** snapshot منجمد `ref_bars_v2.jsonl` (۲۰۲۶-۱۰-۲۰)، type0 و type7 با resolution روزانه

> این گزارش مکمل گزارش اصلی `docs/RA365-ROUND18-RAW-OHLC-PARITY-REPORT.md` است. تمرکز آن فقط Raw OHLC در برابر Rahavard است؛ Track B و موتور الگو دست‌نخورده‌اند. اعداد و علت‌شناسی این نسخه با داوری نهایی Round 19 به‌روزرسانی شده‌اند؛ گزارش داوری: `docs/RA365-ROUND19-MISMATCH-CLOSURE-REPORT.md`.

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
| SOURCE_DATA_DIVERGENCE | ۵۳۸ | ۱٬۱۵۰ | ۱٬۱۵۰ | ۵۴٫۳۷٪ |
| HISTORICAL_REVISION | ۳۶۸ | ۵۴۹ | ۵۴۹ | ۲۵٫۹۶٪ |
| PRECISION_OR_ROUNDING | ۲۱۹ | ۲۹۸ | ۲۹۸ | ۱۴٫۰۹٪ |
| CANDLE_GEOMETRY | ۴۱ | ۶۲ | ۶۲ | ۲٫۹۳٪ |
| PARSING_OR_TRANSFORM | ۴۸ | ۵۶ | ۵۶ | ۲٫۶۵٪ |

### فیلدها

| علت | دارایی | تاریخ | فیلد |
|---|---|---|---|
| FIELD_MAPPING | ۷۱ | ۲٬۹۲۳ | ۲٬۹۲۳ |
| SOURCE_DATA_DIVERGENCE | ۵۴۵ | ۱٬۲۵۸ | ۲٬۳۵۶ |
| HISTORICAL_REVISION | ۳۸۰ | ۶۳۶ | ۱٬۴۸۸ |
| PRECISION_OR_ROUNDING | ۳۰۴ | ۵۴۳ | ۶۴۱ |
| CANDLE_GEOMETRY | ۹۸ | ۱۸۴ | ۳۳۵ |
| PARSING_OR_TRANSFORM | ۵۵ | ۶۳ | ۶۳ |
| PRICE_SCALE_OR_UNIT | ۵ | ۵ | ۵ |

**تفسیر:**
- `SOURCE_DATA_DIVERGENCE`: محصول با TSETMC مطابق است، type0 نیست؛ عمدتاً اراد/آپشن‌ها، flat bars و تاریخ‌های خاص.
- `HISTORICAL_REVISION`: type0 و TSETMC با هم می‌خوانند، snapshot محصول قدیمی‌تر/اصلاح‌شده است.
- `CANDLE_GEOMETRY`: type0 تخت یا H/L بیرون body؛ product با widen آن را ترمیم می‌کند.
- `FIELD_MAPPING`: فقط `close_display` با basis=closing؛ انتظار می‌رود.
- `PRECISION_OR_ROUNDING`: اختلاف‌های کوچک مستند؛ exact و tolerance جدا نگه داشته شده‌اند و تلورانس تغییر نکرده است.
- `PARSING_OR_TRANSFORM`: ۶۳ فیلد؛ ۶۰ فیلد open با `TSETMC FIRST=0` که product طبق قرارداد مستند به base clamp‌شده برمی‌گردد و ۳ فیلد volume صفر در snapshot با TSETMC مثبت. هیچ‌کدام نقص اثبات‌شدهٔ کد فعلی نیستند.
- `PRICE_SCALE_OR_UNIT`: پنج ردیف آپشن/صندوق با مقیاس واحد متفاوت.
- `UNCLASSIFIED`: ۰ فیلد؛ تمام ۱۰۱ فیلد قبلی تعیین تکلیف شدند (۶۰ open → PARSING، ۴۱ فیلد سه‌منبعی → SOURCE).
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
- `UNCLASSIFIED` صفر شد؛ ۱۰۱ فیلد قبلی با شاهد TSETMC/type0 تعیین تکلیف شدند (۶۰ open → PARSING، ۴۱ فیلد سه‌منبعی → SOURCE).
- از ۶ ردیف PARSING اولیه، ۵ ردیف volume در واقع type0-only بودند و به SOURCE منتقل شدند؛ ۱ ردیف volume صفر snapshot با TSETMC مثبت ماند. در مجموع ۱۲ فیلد volume به SOURCE رفت (۵ ردیف مستقل + ۷ فیلد در ردیف‌هایی که علت دیگری داشتند).
- ۵ ردیف price-scale آپشن/صندوق و flat bars منبع، بدون اصلاح تولید.
- `INSTRUMENT_MAPPING` اثبات‌شده‌ای در این pass پیدا نشد؛ اتهام mapping بدون شاهد ثبت نشد.

---

## ۹. تست‌ها، دیتابیس و artifactها

- `dev/test_rahavard_raw_parity_v1.py`: **۱۶/۱۶** بررسی (widen با official close، status، taxonomy، type0-only volume در برابر snapshot volume، semantics واقعی).
- Full gate این راند دوباره اجرا نشد چون هیچ کد production تغییر نکرد؛ گیت Track A قبلی روی `f6e3c4e0` سبز بود. این محدودیت `NOT_RE-RUN` است، نه ادعای سبز جدید.
- دیتابیس عملیاتی و promoted read-only؛ SHA پایان در manifest/پاسخ نهایی ثبت می‌شود.

| artifact | bytes | sha256 |
|---|---|---|
| `rahavard-raw-ohlc-parity.csv` | ۵۹۰٬۲۷۱ | `b3596cc76003b9d21af5ccb33dd3bc3eaf352b052c421ef8aa81aa6b842a31f0` |
| `rahavard-type0-vs-tsetmc.csv` | ۲۵۳٬۶۷۰ | `caa9ba0e5c5474d5720026cb7d1efb539e767310e167d77f8903f6c4a7163b87` |
| `rahavard-raw-ohlc-field-mismatches.csv` | ۱٬۲۴۷٬۳۲۷ | `82bed90c6f05f45d9697fca13800bb9f9d55553660672a9d16bb06100638136a` |
| `rahavard-raw-ohlc-taxonomy.csv` | ۲٬۸۲۵ | `280264bbe7cae0521220ffaaabc83cccee45b9ae12956f0ed1041e2a3daa54e0` |
| `rahavard-raw-ohlc-row-taxonomy.csv` | ۱۹۱ | `1bd5db2d78985d24c2fe956d6d4eafed35e55c3ca6760420db89d262cb111ea2` |
| `rahavard-raw-ohlc-missing.csv` | ۴٬۱۹۹٬۸۲۴ | `88ac77b698cefec70884c435afa7917e7dd2f5de9b58fcc7aacd8f444cb5cfdc` |
| `rahavard-raw-ohlc-summary.json` | ۲٬۳۹۶ | `4841aa5af6363805bec0be9e4d135192233663d56e16a656e87ac5ad65eea307` |
| `rahavard-raw-ohlc-cohort-manifest.json` | ۵٬۰۷۸ | `8300fdb22e1149cfa7c0693b7b4d5ffde97622fe442dc31ee6b7a54ba06a782b` |
| `source-field-matrix-rahavard.csv` | ۲٬۹۹۰ | `56b2270ee5b054c0638fec576195aa5cc7501e2fd207f3b39d75caf62c81e5f5` |

---

## ۱۰. جمع‌بندی

برای ردیف‌های Rahavard قابل‌دسترسی، OHLC خام محصول از نظر **open، last و volume** و H/L پس از transform مستند، تطبیق بسیار بالایی دارد. اختلاف high/low تحت‌اللفظی عمدتاً widen است؛ اختلاف‌های باقی‌مانده به flat/geometry منبع Rahavard، basis نمایش، اصلاح snapshot و چند مورد کوچک تقسیم می‌شوند. هیچ شاهد کافی برای یک اصلاح عمومی production به دست نیامد.
