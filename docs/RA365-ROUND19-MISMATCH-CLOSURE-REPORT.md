# RA365 Round 19 — Mismatch Closure Report

**تاریخ:** 2026-10-22  
**شاخه:** `mission/ra365-round18-raw-ohlc-parity-2026-10-22`  
**مبنای Round 18:** `9531b39f`  
**HEAD هنگام تولید گزارش:** `4305ab582bbd`  
**Commit کد/ابزار/تست این راند:** `4305ab58`  
**مرجع:** snapshot منجمد Rahavard `ref_bars_v2.jsonl` (۲۰۲۶-۱۰-۲۰) و snapshot محصول `product_live_final_v4.jsonl`  
**وضعیت Track B:** دست‌نخورده، روی شاخه مستقل `02ffba94`؛ هیچ فایل Track B در این راند تغییر نکرد.

> این گزارش داوری نهایی اختلاف‌های Raw است. هیچ قیمت، تاریخ یا کندلی تغییر نکرد؛ هیچ تلورانس یا مخرجی تغییر نکرد؛ دیتابیس عملیاتی و promoted فقط read-only استفاده شدند.

---

## ۰. پاسخ کوتاه

- **۲٬۵۹۵ دارایی** و **۱٬۱۸۸٬۹۲۱ ردیف قابل‌مقایسه** دوباره با همان قرارداد Round 18 سنجیده شدند؛ نتیجهٔ عددی تغییر نکرد: **۹۹٫۸۹۰۷٪** فیلد و **۹۹٫۸۲۲۱٪** ردیف.
- **تمام ۲٬۱۱۵ ردیف mismatch تعیین تکلیف شدند؛ `UNCLASSIFIED` از ۸۶ به ۰ رسید.**
- **هیچ باگ عمومی جدیدی در production اثبات نشد.** تنها اصلاحات این راند در قرارداد تحلیل (widen با official CLOSE) و طبقه‌بندی علت بود؛ کد تولیدی قیمت/کندل تغییر نکرد.
- **۶ ردیف PARSING اولیه:** ۵ ردیف volume در واقع type0-only بودند و به SOURCE رفتند؛ ۱ ردیف volume صفر snapshot با TSETMC مثبت ماند (`BLOCKED_SNAPSHOT`).
- **۸۶ ردیف UNCLASSIFIED:** ۵۵ ردیف open با `TSETMC FIRST=0` (fallback مستند product) به PARSING رفتند؛ ۳۱ ردیف سه‌منبعی به SOURCE رفتند.
- **۶۲ ردیف CANDLE_GEOMETRY:** flat bar یا H/L بیرون body در منبع type0؛ product با `widen()` ترمیم می‌کند. نقص product اثبات نشد.
- **۲۹۸ ردیف PRECISION** (از ۲۹۹ اولیه): همه در باند relative ≤ ۰٫۰۵٪ هستند؛ exact و tolerance جدا گزارش شده‌اند و تلورانس تغییر نکرده است. exact mismatch همچنان در مخرج باقی است.
- **۵۴۹ ردیف HISTORICAL** (از ۵۵۲ اولیه): type0 و TSETMC با هم می‌خوانند و snapshot محصول قدیمی/اصلاح‌شده است؛ `widen()` و قرارداد `type0 close = LAST` حفظ شد.
- **۱٬۱۵۰ ردیف SOURCE** (از ۱٬۱۱۰ اولیه): اختلاف منبع/بازنگری/تقویم و volume-only؛ هیچ شرط hard-coded برای نماد اضافه نشد.

---

## ۱. مبنا، دامنه و مرزها

- شروع از `9531b39f` روی شاخه `mission/ra365-round18-raw-ohlc-parity-2026-10-22`؛ Track B در `mission/technical-pattern-engine-round18-2026-10-22` و commit `02ffba94` بدون تغییر.
- منبع مرجع: snapshot منجمد type0/type7، resolution روزانه، ۲٬۵۹۵ دارایی دارای type0.
- منبع محصول: snapshot `product_live_final_v4.jsonl` (همان cohort Round 18)؛ مقایسه روی ردیف‌های مشترک و قابل‌مقایسه.
- oracle مستقل: TSETMC خام، فقط برای اثبات معنای type0 و داوری منبع؛ جایگزین Rahavard نشد.
- دیتابیس عملیاتی و promoted فقط read-only؛ SHA در §۱۰ ثبت شده است.
- هیچ داده‌ای از حساب Rahavard در این راند دریافت نشد؛ مرجع همان snapshot منجمد است. `BLOCKED_LIVE_ACCESS` یعنی «استفاده نشد»، نه «دسترسی وجود ندارد».

---

## ۲. نتیجهٔ نهایی و تفکیک exact از tolerance

### ۲-۱. پوشش

| شاخص | مقدار |
|---|---:|
| دارایی‌های cohort / دارای type0 | ۲٬۵۹۵ / ۲٬۵۹۵ |
| ردیف‌های type0 | ۱٬۲۳۳٬۲۱۳ |
| تاریخ مشترک product/type0 | ۱٬۱۹۲٬۰۷۱ |
| ردیف قابل‌مقایسه (last موجود) | ۱٬۱۸۸٬۹۲۱ |
| last-null محصول (خارج از مخرج) | ۳٬۱۵۰ |
| product-only داخل بازه type0 | ۲٬۱۷۰ |
| product-only خارج بازه type0 | ۹۳۱٬۰۸۹ |
| type0-only داخل بازه محصول | ۱٬۸۴۶ |
| type0-only خارج بازه محصول | ۳۹٬۲۹۶ |

پوشش type0 نسبت به کل کندل‌های محصول **۵۵٫۹۴٪** است. «Full-Universe» در این گزارش یعنی تمام دارایی‌ها و ردیف‌های Rahavard قابل‌دسترسی، نه تمام تاریخ محصول. ردیف‌های خارج از بازهٔ type0 مقایسه نشدند و با صفر/forward-fill پر نشدند.

### ۲-۲. تطبیق قراردادی و تحت‌اللفظی

- قراردادی: **۹۹٫۸۹۰۷٪** فیلد؛ **۹۹٫۸۲۲۱٪** ردیف.
- تحت‌اللفظی: high **۹۱٫۷۰۴۳٪**، low **۹۶٫۴۲۷۳٪**، ردیف کامل **۸۷٫۶۱۰۱٪**.
- اختلاف تحت‌اللفظی عمدتاً `widen()` مستند است: product سایه را باز می‌کند تا official CLOSE داخل body باشد. این transform در قرارداد تحلیل با official CLOSE مستقل انجام شد، نه با type0 close (که LAST است).

| فیلد | مقایسه | exact | exact٪ | tol | exact+tol٪ |
|---|---|---|---|---|---|
| Open | ۱٬۱۹۲٬۰۷۱ | ۱٬۱۹۰٬۹۰۷ | ۹۹٫۹۰۲۴٪ | ۰ | ۹۹٫۹۰۲۴٪ |
| High (contract) | ۱٬۱۹۲٬۰۷۱ | ۱٬۱۹۱٬۱۴۶ | ۹۹٫۹۲۲۴٪ | ۰ | ۹۹٫۹۲۲۴٪ |
| Low (contract) | ۱٬۱۹۲٬۰۷۱ | ۱٬۱۹۱٬۳۸۳ | ۹۹٫۹۴۲۳٪ | ۰ | ۹۹٫۹۴۲۳٪ |
| Close last | ۱٬۱۸۸٬۹۲۱ | ۱٬۱۸۸٬۳۸۳ | ۹۹٫۹۵۴۷٪ | ۰ | ۹۹٫۹۵۴۷٪ |
| Close display | ۱٬۱۹۲٬۰۷۱ | ۱٬۱۸۸٬۵۷۹ | ۹۹٫۷۰۷۱٪ | ۰ | ۹۹٫۷۰۷۱٪ |
| Volume | ۱٬۱۹۲٬۰۷۱ | ۱٬۱۹۱٬۰۶۷ | ۹۹٫۹۱۵۸٪ | ۰ | ۹۹٫۹۱۵۸٪ |

**جمع:** ۷٬۱۴۹٬۲۷۶ فیلد، ۷٬۱۴۱٬۴۶۵ exact، **۹۹٫۸۹۰۷٪**. در این corpus هیچ ردیفی صرفاً با تلورانس «سبز» نشد: `row_tol == row_exact` و `field tol == field exact`؛ تلورانس تغییری در نتیجه نداد و برای بهبود عدد اضافه نشد.

### ۲-۳. معنای type0 (بدون تغییر)

| فیلد type0 | مرجع TSETMC | exact٪ |
|---|---|---:|
| close | LAST | ۹۹٫۹۱۰۲٪ |
| close | official CLOSE | ۱۴٫۰۷۶۰٪ |
| open | FIRST | ۹۹٫۸۶۴۱٪ |
| open | base OPEN | ۳٫۴۸۴۶٪ |
| high / low / volume | HIGH / LOW / VOL | ۹۹٫۸۷۵۴٪ / ۹۹٫۸۹۸۶٪ / ۹۹٫۸۸۴۷٪ |

type0 خام است، close آن LAST است و open آن FIRST؛ type7 تعدیل‌شده است. هیچ‌کدام از این سه لایه با هم مخلوط نشد.

---

## ۳. P0 — شش ردیف PARSING اولیه

شش ردیف اولیه بر اساس volume صفر product انتخاب شده بودند. داوری با TSETMC و دیتابیس عملیاتی:

| نماد | تاریخ | type0 volume | snapshot product | TSETMC volume | DB عملیاتی | علت نهایی | وضعیت |
|---|---|---|---|---|---|---|---|
| دابور | 2020-05-26 | ۹۳۷٬۵۹۶ | ۰ | ۰ | — | SOURCE_DATA_DIVERGENCE | VERIFIED_SOURCE_DIVERGENCE |
| وملت | 2026-07-21 | ۲٬۹۰۸ | ۰ | ۲٬۹۰۸ | ۲٬۹۰۸ | PARSING_OR_TRANSFORM | BLOCKED_SNAPSHOT |
| كابگن | 2022-12-03 | ۶۷٬۸۷۹ | ۰ | ۰ | — | SOURCE_DATA_DIVERGENCE | VERIFIED_SOURCE_DIVERGENCE |
| قشكر | 2020-05-26 | ۱٬۷۴۱٬۷۳۱ | ۰ | ۰ | — | SOURCE_DATA_DIVERGENCE | VERIFIED_SOURCE_DIVERGENCE |
| دلر | 2020-05-26 | ۱٬۰۳۴٬۲۹۶ | ۰ | ۰ | — | SOURCE_DATA_DIVERGENCE | VERIFIED_SOURCE_DIVERGENCE |
| زپارس | 2020-05-26 | ۲۲۵٬۸۴۵ | ۰ | ۰ | — | SOURCE_DATA_DIVERGENCE | VERIFIED_SOURCE_DIVERGENCE |

**نتیجه:** ۵ ردیف از ۶ ردیف، type0-only هستند: TSETMC هم volume صفر دارد و product با TSETMC می‌خواند؛ این‌ها `SOURCE_DATA_DIVERGENCE` هستند، نه خطای parser. ۱ ردیف (`وملت`) volume صفر snapshot با TSETMC مثبت است؛ دیتابیس عملیاتی volume را مثبت دارد (۲٬۹۰۸), پس snapshot کهنه/ناقص است (`BLOCKED_SNAPSHOT`)، نه باگ کد فعلی.

### ۳-۱. volumeهای صفر دیگر

در مجموع **۱۵ فیلد volume صفر** با شاهد بررسی شد:

| نماد | تاریخ | type0 volume | snapshot product | TSETMC volume | DB عملیاتی | علت نهایی | وضعیت |
|---|---|---|---|---|---|---|---|
| كلوند | 2020-05-26 | ۴٬۱۳۸٬۵۷۲ | ۰ | ۰ | — | SOURCE_DATA_DIVERGENCE | VERIFIED_SOURCE_DIVERGENCE |
| كسعدي | 2020-05-26 | ۹٬۶۱۲ | ۰ | ۰ | — | SOURCE_DATA_DIVERGENCE | VERIFIED_SOURCE_DIVERGENCE |
| دابور | 2020-05-26 | ۹۳۷٬۵۹۶ | ۰ | ۰ | — | SOURCE_DATA_DIVERGENCE | VERIFIED_SOURCE_DIVERGENCE |
| فاهواز | 2020-09-23 | ۱٬۸۳۸٬۸۴۸ | ۰ | ۰ | — | SOURCE_DATA_DIVERGENCE | VERIFIED_SOURCE_DIVERGENCE |
| قشكر | 2020-05-26 | ۱٬۷۴۱٬۷۳۱ | ۰ | ۰ | — | SOURCE_DATA_DIVERGENCE | VERIFIED_SOURCE_DIVERGENCE |
| غپينو | 2020-05-26 | ۵٬۵۲۴٬۱۵۷ | ۰ | ۰ | — | SOURCE_DATA_DIVERGENCE | VERIFIED_SOURCE_DIVERGENCE |
| دلر | 2020-05-26 | ۱٬۰۳۴٬۲۹۶ | ۰ | ۰ | — | SOURCE_DATA_DIVERGENCE | VERIFIED_SOURCE_DIVERGENCE |
| غشهد | 2020-05-26 | ۱٬۳۴۷٬۵۴۵ | ۰ | ۰ | — | SOURCE_DATA_DIVERGENCE | VERIFIED_SOURCE_DIVERGENCE |
| فسديد | 2021-05-01 | ۱۴۵ | ۰ | ۰ | — | SOURCE_DATA_DIVERGENCE | VERIFIED_SOURCE_DIVERGENCE |
| زپارس | 2020-05-26 | ۲۲۵٬۸۴۵ | ۰ | ۰ | — | SOURCE_DATA_DIVERGENCE | VERIFIED_SOURCE_DIVERGENCE |
| كابگن | 2022-12-03 | ۶۷٬۸۷۹ | ۰ | ۰ | — | SOURCE_DATA_DIVERGENCE | VERIFIED_SOURCE_DIVERGENCE |
| يلدا | 2025-08-13 | ۱٬۰۰۰ | ۰ | ۱٬۰۰۰ | ۱٬۰۰۰ | PARSING_OR_TRANSFORM | BLOCKED_SNAPSHOT |
| صهمدا86 | 2026-01-05 | ۵٬۰۰۰ | ۰ | ۵٬۰۰۰ | — | PARSING_OR_TRANSFORM | BLOCKED_SNAPSHOT |
| وملت | 2026-07-21 | ۲٬۹۰۸ | ۰ | ۲٬۹۰۸ | ۲٬۹۰۸ | PARSING_OR_TRANSFORM | BLOCKED_SNAPSHOT |
| پرتو | 2025-09-17 | ۵۲ | ۰ | ۰ | ۵۲ | SOURCE_DATA_DIVERGENCE | BLOCKED_SNAPSHOT |

- **۱۱ فیلد type0-only:** TSETMC و snapshot محصول صفر، type0 مثبت. علت: منبع Rahavard؛ product دست‌کاری نشد.
- **۳ فیلد snapshot-zero:** TSETMC و type0 مثبت، snapshot صفر؛ دیتابیس عملیاتی برای `وملت` و `يلدا` عدد مثبت دارد. snapshot کهنه است؛ کد فعلی `get_chart_db` volume را از DB می‌خواند.
- **۱ فیلد snapshot-stale:** `پرتو`؛ TSETMC صفر ولی DB و type0 هر دو ۵۲ هستند. taxonomy دوعنصری آن را SOURCE می‌نامد، اما شاهد DB نشان می‌دهد snapshot کهنه است. این مورد در ستون وضعیت `BLOCKED_SNAPSHOT` است و در محاسبهٔ source/rounding دست‌کاری نشد.

---

## ۴. P0 — ۶۲ ردیف CANDLE_GEOMETRY

- **۳۳۵ فیلد** در **۱۸۴ تاریخ** و **۹۸ دارایی**؛ **۶۲ ردیف** با علت غالب CANDLE_GEOMETRY.
- توزیع فیلد: open: ۱۲۸, high_raw: ۱۲۴, low_raw: ۸۳.
- ۳۱۶ فیلد flat bar (`O=H=L=C`) و ۱۹ فیلد H/L بیرون body.
- بیشترین تاریخ‌ها: 2026-10-12 (۲۳), 2026-09-28 (۱۶), 2026-09-30 (۱۲), 2026-02-18 (۱۰), 2026-09-01 (۹).

نمونه‌ها:

| نماد | تاریخ | فیلد | type0 | product | TSETMC | note |
|---|---|---|---|---|---|---|
| غدشت | 2019-03-17 | high_raw | ۳۵٬۰۰۰ | ۳۱٬۵۰۰ | ۳۱٬۵۰۰ | type0 H/L outside body; product widen() repairs geometry |
| شپارس | 2007-01-10 | low_raw | ۱۵٬۲۶۰ | ۱۵٬۳۲۹ | ۱۵٬۳۲۹ | type0 H/L outside body; product widen() repairs geometry |
| بترانس | 2024-06-11 | low_raw | ۱٬۷۳۰ | ۱٬۷۳۲ | ۱٬۷۳۲ | type0 O=H=L=C flat bar; only close/last is reliable |
| فبيرا | 2026-09-01 | open | ۲٬۴۵۸ | ۲٬۳۸۵ | ۲٬۴۵۸ | type0 O=H=L=C flat bar; only close/last is reliable |
| فبيرا | 2026-09-01 | high_raw | ۲٬۴۵۸ | ۲٬۳۸۵ | ۲٬۴۵۸ | type0 O=H=L=C flat bar; only close/last is reliable |

**علت عمومی:** flat bar یا H/L ناممکن در منبع type0. product طبق قرارداد `widen()` سایه را باز می‌کند و هیچ قیمت منتشرشده‌ای را خرد نمی‌کند. **اصلاح production لازم نیست**؛ اگر type0 را با `widen` مقایسه کنیم، این ردیف‌ها از mismatch خارج می‌شوند. `type0_bad_geom` کل corpus ۶۷۷ و flat ۱۹۱٬۷۲۹ ردیف است.

---

## ۵. P0 — ۸۶ ردیف UNCLASSIFIED

### ۵-۱. open با `TSETMC FIRST=0` — ۶۰ فیلد / ۵۵ ردیف غالب PARSING

- در **۶۰ فیلد open**، TSETMC ستون FIRST را صفر می‌دهد و product طبق قرارداد مستند (خط ۱۳۵ `api/chart.py`) به `clamp(base, low, high)` برمی‌گردد؛ type0 open عدد دیگری دارد.
- این transform **مستند و عمدی** است؛ تنها راه حذف اختلاف، جایگزینی open با مقدار type0 بدون شاهد مستقل است که مجاز نیست. بنابراین `PARSING_OR_TRANSFORM` با وضعیت `VERIFIED_CONTRACT_FALLBACK` ثبت شد.
- ۵۵ ردیف فقط این open را داشتند و PARSING شدند؛ ۵ ردیف هم‌زمان فیلد سه‌منبعی داشتند و به SOURCE رفتند.

نمونه‌ها:

| نماد | تاریخ | type0 open | product open | TSETMC FIRST | TSETMC base | TSETMC high | TSETMC low |
|---|---|---|---|---|---|---|---|
| چكارن | 2024-10-30 | ۳٬۴۴۴ | ۳٬۳۵۰ | ۰ | ۳٬۳۴۴ | ۳٬۴۴۴ | ۳٬۳۵۰ |
| چكارن | 2026-06-02 | ۴٬۰۸۰ | ۴٬۰۱۲ | ۰ | ۴٬۰۱۲ | ۴٬۰۸۰ | ۳٬۸۹۲ |
| بترانس | 2023-12-12 | ۲٬۸۰۵ | ۲٬۸۲۰ | ۰ | ۲٬۸۲۰ | ۲٬۸۶۹ | ۲٬۸۰۲ |
| وامين | 2024-12-08 | ۸٬۷۶۰ | ۸٬۵۹۰ | ۰ | ۸٬۵۳۰ | ۸٬۷۸۰ | ۸٬۵۹۰ |

**نتیجه:** نقص product اثبات نشد. `FIRST=0` یعنی منبع TSETMC اولین معامله را منتشر نکرده؛ fallback به base یک قرارداد مستند است و با hard-code یا داده ساختگی جایگزین نشد.

### ۵-۲. سه‌منبعی — ۴۱ فیلد / ۳۱ ردیف غالب SOURCE

- در **۴۱ فیلد**، type0، TSETMC و product سه عدد متفاوت می‌دهند؛ product در بسیاری از موارد با official CLOSE widen‌شده یا TSETMC مطابق است.
- این‌ها `SOURCE_DATA_DIVERGENCE` هستند؛ نه rounding، نه product transform. هیچ‌کدام از این ردیف‌ها از مخرج حذف نشدند.

نمونه‌ها:

| نماد | تاریخ | فیلد | type0 | product | TSETMC high/low | TSETMC official close |
|---|---|---|---|---|---|---|
| كاريس | 2020-08-03 | high_raw | ۲۳۸٬۰۰۰ | ۲۳۷٬۱۰۰ | ۲۳۷٬۰۰۰ | ۲۳۴٬۵۵۱ |
| ثالوند | 2020-10-06 | low_raw | ۱۲٬۵۴۳ | ۱۲٬۷۳۸ | ۱۳٬۳۶۵ | ۱۲٬۷۳۸ |
| گنج | 2024-06-11 | low_raw | ۲۹٬۸۵۳ | ۳۰٬۱۱۸ | ۳۰٬۲۷۳ | ۳۰٬۱۱۸ |
| فجهان | 2024-06-09 | high_raw | ۳٬۴۸۰ | ۳٬۴۶۹ | ۳٬۴۱۶ | ۳٬۴۶۹ |

### ۵-۳. انتقال ردیف‌ها

| سطح | قبل | بعد | delta | توضیح |
|---|---:|---:|---:|---|
| `UNCLASSIFIED` | ۸۶ | ۰ | -۸۶ | ۵۵ → PARSING، ۳۱ → SOURCE |
| `PARSING_OR_TRANSFORM` | ۶ | ۵۶ | ۵۰ | +۵۵ از UNCLASSIFIED، -۵ به SOURCE |
| `SOURCE_DATA_DIVERGENCE` | ۱٬۱۱۰ | ۱٬۱۵۰ | ۴۰ | +۳۱ + ۵ + ۳ HISTORICAL + ۱ PRECISION |
| `HISTORICAL_REVISION` | ۵۵۲ | ۵۴۹ | -۳ | ۳ ردیف با فیلد سه‌منبعی به SOURCE |
| `PRECISION_OR_ROUNDING` | ۲۹۹ | ۲۹۸ | -۱ | ۱ ردیف با فیلد سه‌منبعی به SOURCE |
| `CANDLE_GEOMETRY` | ۶۲ | ۶۲ | ۰ | بدون تغییر |

**تغییر علت در سطح فیلد:** `UNCLASSIFIED→PARSING` ۶۰، `UNCLASSIFIED→SOURCE` ۴۱، `PARSING→SOURCE` ۱۲، `PARSING→PARSING` ۳. ماتریس کامل: `rahavard-raw-ohlc-round19-transitions.csv`.

---

## ۶. P1 — ۲۹۸ ردیف PRECISION_OR_ROUNDING

- **۶۴۱ فیلد** در **۵۴۳ تاریخ** و **۳۰۴ دارایی**؛ **۲۹۸ ردیف** با علت غالب.
- توزیع فیلد: volume: ۱۶۹, close_display: ۱۴۲, low_raw: ۹۶, high_raw: ۹۲, open: ۸۹, last: ۵۳.
- بیشینهٔ relative diff: **۰٫۰۵۰۰٪**؛ میانهٔ relative diff در کل این گروه بسیار کوچک‌تر است. این‌ها در باند `REL_ROUND = 0.0005` هستند، اما **exact نیستند** و exact mismatch در مخرج باقی مانده است.
- بیشترین تاریخ‌ها: 2020-05-26 (۲۸), 2025-06-23 (۲۶), 2025-01-22 (۱۹), 2026-09-30 (۱۶), 2020-08-05 (۱۴).

نمونه‌ها:

| نماد | تاریخ | فیلد | type0 | product | abs | relative |
|---|---|---|---|---|---|---|
| غدشت | 2003-05-28 | open | ۲٬۵۵۰ | ۲٬۵۵۱ | ۱ | ۰٫۰۳۹۲٪ |
| غدشت | 2004-10-12 | open | ۳٬۱۰۸ | ۳٬۱۰۹ | ۱ | ۰٫۰۳۲۲٪ |
| غدشت | 2005-12-19 | open | ۴٬۷۸۴ | ۴٬۷۸۳ | ۱ | ۰٫۰۲۰۹٪ |
| غدشت | 2006-01-07 | open | ۵٬۴۵۳ | ۵٬۴۵۴ | ۱ | ۰٫۰۱۸۳٪ |
| غدشت | 2006-02-21 | open | ۵٬۳۴۷ | ۵٬۳۴۶ | ۱ | ۰٫۰۱۸۷٪ |

**داوری:** PRECISION به معنای «اختلاف کوچک عددی» است، نه «تطبیق کامل». تلورانس برای سبزکردن گزارش افزایش نیافت؛ `field tol == field exact` و `row_tol == row_exact` نشان می‌دهد باند tolerance نتیجه را عوض نکرده است. در volume، اختلاف‌های شمارشی کوچک هستند و به‌عنوان همان PRECISION ثبت شده‌اند؛ ادعای rounding ماشینی برای آن‌ها مطرح نشد.

---

## ۷. P2 — ۵۴۹ ردیف HISTORICAL_REVISION

- **۱٬۴۸۸ فیلد** در **۶۳۶ تاریخ** و **۳۸۰ دارایی**؛ **۵۴۹ ردیف** با علت غالب.
- توزیع فیلد: volume: ۳۷۱, high_raw: ۲۹۳, open: ۲۸۰, low_raw: ۲۴۳, last: ۱۹۱, close_display: ۱۱۰.
- بیشترین تاریخ‌ها: 2026-10-12 (۴۹۷), 2026-09-30 (۲۰۹), 2026-09-28 (۱۵۵), 2026-09-01 (۱۱۴), 2024-06-09 (۴۱), 2024-06-02 (۳۶).

نمونه‌ها:

| نماد | تاریخ | فیلد | type0 | product | TSETMC | note |
|---|---|---|---|---|---|---|
| ددام | 2024-06-18 | high_raw | ۱۲٬۱۷۰ | ۱۲٬۱۰۰ | ۱۲٬۱۷۰ | type0/TSETMC agree, product snapshot differs |
| دجابر | 2024-06-11 | low_raw | ۱۱٬۳۴۰ | ۱۱٬۳۵۰ | ۱۱٬۳۴۰ | type0/TSETMC agree, product snapshot differs |
| دابور | 2020-05-23 | high_raw | ۴۶٬۸۴۰ | ۵۰٬۹۹۹ | ۴۶٬۸۴۰ | type0/TSETMC agree, product snapshot differs |
| درازك | 2025-04-23 | open | ۷٬۲۹۰ | ۷٬۱۶۰ | ۷٬۲۹۰ | type0/TSETMC agree, product snapshot differs |
| دامين | 2025-08-02 | volume | ۱۲٬۶۹۴٬۱۲۳ | ۱۲٬۶۸۷٬۱۲۳ | ۱۲٬۶۹۴٬۱۲۳ | type0/TSETMC agree, product snapshot differs |

**داوری:** در این ردیف‌ها type0 و TSETMC با هم می‌خوانند و snapshot محصول عدد دیگری دارد؛ یعنی snapshot قدیمی‌تر یا اصلاح‌نشده است. این یک **بازنگری/کهنگی snapshot** است، نه خطای transform. قرارداد `widen()` حفظ شد و `type0 close` معادل official CLOSE فرض نشد. هیچ مقدار داخلی برای نزدیک‌شدن به Rahavard تغییر نکرد.

---

## ۸. P3 — ۱٬۱۵۰ ردیف SOURCE_DATA_DIVERGENCE

- **۲٬۳۵۶ فیلد** در **۱٬۲۵۸ تاریخ** و **۵۴۵ دارایی**؛ **۱٬۱۵۰ ردیف** با علت غالب.
- توزیع فیلد: open: ۶۰۷, volume: ۴۵۷, high_raw: ۴۱۶, close_display: ۳۱۷, last: ۲۹۴, low_raw: ۲۶۵.
- بیشترین تاریخ‌ها: 2020-05-26 (۲۷۲), 2025-01-22 (۲۰۷), 2021-05-17 (۱۱۸), 2025-12-22 (۳۸), 2026-04-06 (۳۵), 2020-08-03 (۳۴), 2026-02-16 (۳۳), 2025-12-29 (۳۱).

خوشه‌های معنادار:

| خوشه | شاهد | نتیجه |
|---|---|---|
| volume-only ۲۰۲۰-۰۵-۲۶ و تاریخ‌های مشابه | TSETMC volume صفر، type0 مثبت، product صفر | منبع Rahavard؛ product با TSETMC می‌خواند |
| open/high/low ۲۰۲۰-۲۰۲۱ و ۲۰۲۴-۲۰۲۶ | product با TSETMC FIRST/HIGH/LOW یا official CLOSE widen‌شده می‌خواند | اختلاف type0 با oracle؛ transform product نیست |
| close/last | product با TSETMC LAST/CLOSE مطابق است | نوع قیمت یا بازنگری منبع |
| صندوق/آپشن با مقیاس واحد | ratio ۱۰/۱۰۰/۱۰۰۰ | `PRICE_SCALE_OR_UNIT` جدا و بدون اصلاح |
| تاریخ‌های سه‌منبعی | type0، TSETMC و product سه عدد | `P0_THREE_SOURCE_DIVERGENCE` |

نمونه‌ها:

| نماد | تاریخ | فیلد | type0 | product | abs | note |
|---|---|---|---|---|---|---|
| غدشت | 2001-05-12 | open | ۱٬۵۵۸ | ۱٬۵۴۳ | ۱۵ | product open matches TSETMC FIRST, type0 does not |
| غدشت | 2001-10-31 | open | ۱٬۳۶۱ | ۱٬۳۶۰ | ۱ | product open matches TSETMC FIRST, type0 does not |
| غدشت | 2001-11-10 | open | ۱٬۳۶۱ | ۱٬۳۶۰ | ۱ | product open matches TSETMC FIRST, type0 does not |
| غدشت | 2002-01-29 | open | ۱٬۳۵۳ | ۱٬۳۲۰ | ۳۳ | product open matches TSETMC FIRST, type0 does not |
| غدشت | 2002-02-02 | open | ۱٬۳۲۱ | ۱٬۳۲۰ | ۱ | product open matches TSETMC FIRST, type0 does not |
| غدشت | 2002-02-03 | open | ۱٬۳۲۲ | ۱٬۳۲۱ | ۱ | product open matches TSETMC FIRST, type0 does not |

**داوری:** هیچ شرط hard-coded برای نماد، حذف ردیف از مخرج، یا تغییر قیمت انجام نشد. مواردی که product با TSETMC مطابق است، شاهد مستقل دارند که اختلاف از type0/Rahavard می‌آید. موارد سه‌منبعی هم با شاهد سه منبع ثبت شدند، نه با حدس.

---

## ۹. missing bar، پوشش و محدودیت‌ها

- **۴۹۹ ردیف type0 معتبر** که snapshot محصول ندارد؛ 2023-03-27 (۱۵۳), 2026-10-13 (۹۶), 2026-10-10 (۸۳), 2026-10-18 (۵۳), 2026-10-17 (۵۲). بررسی زنده در Round 18 نشان داد pipeline فعلی این تاریخ‌ها را دارد؛ این یک **gap در snapshot محصول** است، نه نقص فعلی دریافت.
- **۱٬۸۸۳ ردیف product** که type0 ندارد؛ gap مرجع Rahavard.
- **۱٬۳۴۵ تاریخ type0-only** که TSETMC هم ندارد؛ تقویم/داده Rahavard.
- **۸۳ ردیف product-only** که با شاهد مستقل تعیین تکلیف نشد.
- **۳٬۱۵۰ ردیف last-null** از مخرج ردیف قابل‌مقایسه خارج شد و جدا گزارش شده است.
- **۲۰۴ product-only no-trade** و **۲ type0-only no-trade** در درصد قیمت وارد نشدند.
- هیچ missing bar با صفر، forward-fill یا کندل ساختگی پر نشد. هیچ ردیفی برای بهبود درصد حذف نشد.

**محدودیت:** مرجع، snapshot منجمد است و دسترسی live استفاده نشد. type0 فقط ۵۵٫۹۴٪ از کندل‌های محصول را می‌پوشاند؛ نتیجه برای ردیف‌های Rahavard قابل‌دسترسی معتبر است، نه تمام تاریخ محصول.

---

## ۱۰. اصلاحات، تست، گیت و دیتابیس‌های محافظت‌شده

### ۱۰-۱. چه چیزی اصلاح شد و چه چیزی نه

- **قرارداد تحلیل:** widen با official CLOSE مستقل (نه type0 close=LAST)؛ این اصلاح در Round 18 انجام و در Round 19 تثبیت شد. نتیجه: high/low قراردادی به ۹۹٫۹۲۲۴٪ / ۹۹٫۹۴۲۳٪.
- **طبقه‌بندی علت:** volume-only type0 با TSETMC صفر به SOURCE منتقل شد؛ snapshot-zero با TSETMC مثبت PARSING ماند؛ open با `FIRST=0` به‌عنوان fallback مستند PARSING ثبت شد. این تغییر فقط تحلیل است و هیچ قیمت/کندلی را تغییر نمی‌دهد.
- **کد تولیدی تغییر نکرد.** هیچ فایل `api/`, `fts_engine.py`, `candle_contract.py` یا دیتابیس در این راند تغییر نکرد.
- **Track B تغییر نکرد.**

### ۱۰-۲. تست‌ها

- `dev/test_rahavard_raw_parity_v1.py`: **۱۶/۱۶** pass (widen با official close، status، taxonomy، type0-only volume در برابر snapshot volume، semantics واقعی). خروجی: `round19-test-output.txt`.
- **Full gate دوباره اجرا نشد** چون هیچ کد production تغییر نکرد؛ آخرین full gate سبز روی `f6e3c4e0` ثبت شده است. این وضعیت `NOT_RE-RUN` است، نه ادعای سبز جدید.
- Track B تست‌ها و build آن در این راند اجرا نشدند؛ فایل‌های آن دست‌نخورده‌اند.

### ۱۰-۳. دیتابیس‌های محافظت‌شده

| دیتابیس | SHA256 | وضعیت |
|---|---|---|
| عملیاتی `BorsTerminal-src/market.db` | `7b933b05d03b8a2f9383f901faf6b2c34f1500e70619d6cc5c8039f171b1848c` | بدون تغییر، read-only |
| promoted `market_r17_migrated.db` | `8fb85f381317634430cae429bd9775eba0a364b692e0868b4d9b17dbbcc6c17f` | بدون تغییر، read-only |
| مرجع موقت `reference.db` | `0d9898bab7d241c29286e829d17e46d7b3b80d07c38281d3eee9bc21c470b4e0` | فقط read-only برای مقایسه |

هیچ migration، write، VACUUM یا بازسازی روی دیتابیس عملیاتی/promoted انجام نشد. SHA ابتدا و انتهای راند یکسان است.

---

## ۱۱. معیار خروج Track A

| معیار | وضعیت | شاهد |
|---|---|---|
| همهٔ باگ‌های عمومی قابل‌اثبات اصلاح شدند | `VERIFIED` | هیچ باگ production اثبات نشد؛ اصلاحات فقط تحلیل |
| قرارداد Raw و adjusted واضح و پایدار | `VERIFIED` | type0=LAST/FIRST، type7=adjusted، widen با official CLOSE |
| موارد قابل‌اصلاح شناخته‌شده بسته شدند | `VERIFIED` | UNCLASSIFIED صفر؛ ۱۱۶ فیلد P0 تعیین تکلیف |
| اختلاف‌های منبع/تاریخی علت و وضعیت مستند دارند | `VERIFIED` | SOURCE ۱٬۱۵۰؛ HISTORICAL ۵۴۹ |
| هیچ علت جدید و نامشخصی باقی نمانده | `VERIFIED` | UNCLASSIFIED ۰ |
| artifact و تست رگرسیون ثبت شد | `IMPLEMENTED_AND_TESTED` | ۱۳ artifact + ۱۶ تست |
| وضعیت Git و دیتابیس‌های محافظت‌شده روشن است | `VERIFIED` | SHAها و commit جدا |

**تصمیم:** Track A به معیار خروج رسیده است. موارد باقی‌مانده در §۱۲ «منبع/بازنگری/snapshot» هستند و برای ادامهٔ Track B مسدودکننده نیستند. Track B از همین نقطه ادامه می‌یابد.

---

## ۱۲. موارد باقی‌مانده و وضعیت‌ها

| مورد | تعداد | وضعیت | علت |
|---|---:|---|---|
| volume صفر snapshot با TSETMC مثبت | ۳ فیلد | `BLOCKED_SNAPSHOT` | snapshot کهنه؛ DB عملیاتی مثبت |
| volume صفر snapshot با DB=type0 | ۱ فیلد | `BLOCKED_SNAPSHOT` | snapshot کهنه؛ taxonomy دوعنصری SOURCE |
| type0-only volume | ۱۱ فیلد | `VERIFIED_SOURCE_DIVERGENCE` | منبع Rahavard؛ product با TSETMC |
| open با `FIRST=0` | ۶۰ فیلد | `VERIFIED_CONTRACT_FALLBACK` | fallback مستند product |
| سه‌منبعی high/low | ۴۱ فیلد | `VERIFIED_SOURCE_DIVERGENCE` | type0/TSETMC/product سه عدد |
| CANDLE_GEOMETRY | ۶۲ ردیف | `VERIFIED_SOURCE_GEOMETRY` | flat/H/L منبع type0؛ widen |
| HISTORICAL_REVISION | ۵۴۹ ردیف | `VERIFIED_SNAPSHOT_REVISION` | snapshot محصول کهنه |
| PRECISION_OR_ROUNDING | ۲۹۸ ردیف | `VERIFIED_ROUNDING_BAND` | relative ≤ ۰٫۰۵٪؛ exact نیست |
| product snapshot omissions | ۴۹۹ ردیف | `BLOCKED_SNAPSHOT` | ۲۰۲۳-۰۳-۲۷ و ۲۰۲۶-۱۰ |
| Rahavard omissions | ۱٬۸۸۳ ردیف | `BLOCKED_REFERENCE` | مرجع type0 ندارد |
| type0 rows outside product window | ۳۹٬۲۹۶ ردیف | `NOT_COMPARABLE` | خارج از بازه محصول |

---

## ۱۳. Git، commit و artifactها

- شاخه Track A: `mission/ra365-round18-raw-ohlc-parity-2026-10-22`؛ مبنا `9531b39f`؛ HEAD گزارش `4305ab582bbd`.
- commit کد/ابزار/تست/artifact: `4305ab58`.
- هیچ push یا merge به `main` انجام نشد؛ Track B روی شاخهٔ مستقل و commit `02ffba94` دست‌نخورده است.
- تغییرات Track A و Track B در commitهای جداگانه نگه داشته شده‌اند.

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
| `rahavard-raw-ohlc-round19-adjudication.csv` | ۳۴٬۴۷۸ | `d49fa1141ca0cab6ea07d52aec795c77c48b25ac66092bd9d913caf142d5831b` |
| `rahavard-raw-ohlc-round19-transitions.csv` | ۱٬۳۲۹ | `78cb8603e8622114ac2fdc885330962f27f85fe72c130d50c746acc269c3ad51` |
| `rahavard-raw-ohlc-round19-summary.json` | ۳٬۴۵۹ | `46020a76f20bbb2ff342839cffd3319af57cf116c589d91bf53d12e824d09519` |
| `round19-test-output.txt` | ۸۶۰ | `c10a956c2332cd7c555b0435524af399040847c4cdac242ebd44830e9166dace` |

---

## ۱۴. جمع‌بندی

پاسخ نهایی به سؤال اصلی: از **۱٬۱۸۸٬۹۲۱** ردیف قابل‌مقایسه، **۹۹٫۸۲۲۱٪** ردیف و **۹۹٫۸۹۰۷٪** فیلد با قرارداد خام مستند تطبیق دارند. اختلاف‌های باقی‌مانده به سه خانوادهٔ روشن تقسیم شدند: (۱) منبع type0/Rahavard در برابر oracle TSETMC، (۲) snapshot کهنه/ناقص محصول، (۳) بازنگری تاریخی. هیچ‌کدام با تغییر داده، تلورانس، مخرج یا شرط نمادی «سبز» نشدند. `UNCLASSIFIED` صفر است و Track A قابل‌اعتماد و مستند است.
