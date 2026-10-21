# Sarkhati GitHub Reference Audit — Round 11A

**تاریخ:** ۲۰۲۶-۱۰-۲۱  
**دامنه:** شش مخزنِ سرخطی؛ فقط بررسیِ کدِ pin‌شده و شواهدِ نشستِ مجاز.  
**قاعده:** هیچ کدی از این مخازن مستقیماً وارد BorsTerminal نشد.

## حکمِ مجوز

برایِ هر شش مخزن، endpointِ مجوزِ GitHub در commitِ بررسی‌شده ۴۰۴ داد و هیچ
فایلِ `LICENSE`/`COPYING` در درختِ مخزن نبود. بنابراین «عمومی‌بودن» را مجوزِ
کپی نمی‌دانیم. تصمیم‌ها فقط `REFERENCE_ONLY` یا `REJECT` هستند؛ هیچ
`REUSE_DIRECTLY` وجود ندارد.

| مخزن | Commit | زبان/معماری | تصمیم |
| --- | --- | --- | --- |
| [m-fazel/Sarkhati](https://github.com/m-fazel/Sarkhati) | `c7c94879e3d8b303202348e66ce95fc468b1bb1c` | Rust/CLI چندکارگزاری | `REFERENCE_ONLY` |
| [estakhri/Sarkhati](https://github.com/estakhri/Sarkhati) | `b63f55b071ed15aa43781964005d40f58ddcd744` | Rust/CLI چندکارگزاری | `REFERENCE_ONLY` / برایِ EasyTrader `REJECT` |
| [HosseinSayyedMousavi/Sarkhati](https://github.com/HosseinSayyedMousavi/Sarkhati) | `fd4b3731765fef1aec42e8a0829244538867fbcb` | Python + PyQt + Selenium | `REJECT` (کد) / `REFERENCE_ONLY` (رفتار) |
| [sajadghandehari/mofid-autotrader](https://github.com/sajadghandehari/mofid-autotrader) | `582d57032ea463b47827b2bc924d7b8ce6021490` | Python + PyQt + Selenium (Mofid) | `REJECT` / `REFERENCE_ONLY` |
| [RezaMahdaviiDev/mofid](https://github.com/RezaMahdaviiDev/mofid) | `72a2e8cbd58aba4841dc0e98a10d77571505d862` | TypeScript + Playwright | `REFERENCE_ONLY` |
| [amirali110/Sarkhati-Bourse](https://github.com/amirali110/Sarkhati-Bourse) | `2fb5b604fe4bd2b04d95dd3423f5a0acf68fc9b9` | C++/Qt | `REJECT` |

## ۱) m-fazel/Sarkhati

| محور | یافته |
| --- | --- |
| ارسال | `src/easy_trader.rs` → `POST https://api-mts.orbis.easytrader.ir/core/api/v2/order`، بدنهٔ `{order: …}` |
| فیلدهایِ payload | `price`, `quantity`, `side`, `validityType`, `symbolIsin`, `orderModelType`, `orderFrom` — فقط ۷ فیلد |
| enumها | `side 0/1`, `orderModelType=1`, `orderFrom=34`, `validityType=0` در نمونه |
| زمان | NTP اختیاری + `time_reference.rs`؛ target_time نمونه `08:45:00.000`؛ calibration با probeهای `HEAD` |
| نرخ/چند سفارش | `rate_limiter.rs` فاصلهٔ ساده؛ `batch_delay_ms=100`، `batch_repeat` |
| پایش/تکرار | هیچ GET سفارش، reconcile، order-id یا idempotency ندارد؛ فقط موفقیتِ HTTP |
| خطا/توقف | خطای HTTP را bail می‌کند؛ توقفِ برنامه = توقفِ loop، نه لغو سفارش |
| تست | هیچ فایلِ test/spec پیدا نشد |
| امنیت | توکن/Cookie در config؛ `test_mode` **curl با Authorization را چاپ می‌کند** — الگویِ ناامن |
| مجوز | هیچ فایلِ مجوز؛ GitHub API 404 |
| اثر | فقط تأییدِ مسیر/envelope و فیلدهایِ حداقلی؛ کد یا زمان‌بندی کپی نشد |

## ۲) estakhri/Sarkhati

| محور | یافته |
| --- | --- |
| ارسال | `src/mofid.rs` → `POST https://mofidonline.com/apigateway/api/v1/Order/send`؛ پروتکلِ **Mofid/Titan**، نه EasyTrader |
| فیلدها | `orderSide` رشته‌ای، `price`, `quantity`, `symbolIsin`, `validityType`, `validityDate`, `orderFrom` رشته‌ای |
| احراز | Cookie یا Bearer؛ هدرهایِ Titan (`x-appname`, Origin, Referer) |
| زمان/نرخ | batch delay ساده؛ NTP/کالیبراسیونِ EasyTrader در این فایل دیده نشد |
| پایش/خطا | فقط status کد؛ پاسخِ خام چاپ می‌شود؛ reconcile/لغو ندارد |
| تست | هیچ test/spec پیدا نشد |
| امنیت | در `test_mode` کوکی/توکن و بدنهٔ سفارش چاپ می‌شود؛ الگویِ ناامن |
| مجوز | هیچ فایلِ مجوز؛ GitHub API 404 |
| اثر | فقط برایِ **تفکیک پروتکل** مفید است؛ هیچ‌چیز وارد BorsTerminal نشد |

## ۳) HosseinSayyedMousavi/Sarkhati

| محور | یافته |
| --- | --- |
| معماری | PyQt + Selenium؛ `Sarkhati.py` ۸۸۱ خط و xpathهایِ ثابت؛ `Captcha.py` ورودِ دستیِ CAPTCHA |
| ارسال | از طریقِ کلیک رویِ فرمِ وب (`send-order`)، نه قراردادِ API |
| احراز | نام کاربری/رمز در UI؛ CAPTCHA به‌صورتِ دستی؛ هیچ دورزدنی دیده نشد |
| زمان | QTime/NTP/ping در UI؛ منطقِ زمان‌بندی به DOM وابسته |
| پایش/خطا | خواندنِ جدولِ سفارش‌ها با xpath؛ بدونِ reconcile مستقل |
| تست | هیچ تستی پیدا نشد |
| مجوز | هیچ فایلِ مجوز؛ GitHub API 404 |
| تصمیم | `REJECT` برایِ کد؛ استفادهٔ رفتاری هم نبود |

## ۴) sajadghandehari/mofid-autotrader

| محور | یافته |
| --- | --- |
| معماری | PyQt + Selenium برایِ **Mofid**؛ `manage.py` فقط ۱۵۲ خط؛ فایل‌هایِ اجرایی/UI همراه |
| ارسال | کلیکِ DOM با xpath؛ نام کاربری/رمز در فرم؛ CAPTCHA دستی |
| زمان | loop تا `formatted_time == selected_time`؛ تأخیرِ ۳ ثانیه‌ای؛ بدون drift واقعی |
| پایش | هیچ؛ فقط `time.sleep` و کلیک |
| تست | هیچ |
| امنیت | رمز در حافظهٔ UI؛ هیچ ذخیرهٔ امن/کنترلِ نشت دیده نشد |
| مجوز | هیچ فایلِ مجوز؛ GitHub API 404 |
| تصمیم | `REJECT`؛ «۵ ثانیه قبل از بازار» در README ادعایِ تجربی است، نه قرارداد |

## ۵) RezaMahdaviiDev/mofid — نزدیک‌ترین مرجع

| محور | یافته |
| --- | --- |
| ارسال | `src/brokerages/easy/api/order.ts` → `POST .../core/api/v2/order`، `{order:{…}}` |
| فیلدها | `price`, `quantity`, `side`, `validityType`, `createDateTime`, `commission: 0.0012`, `symbolIsin`, `symbolName`, `orderModelType:1`, `orderFrom:34` |
| تبدیل | `side` عددی؛ `symbolName` همان ticker؛ `createDateTime` قالبِ `M/D/YYYY h:mm:ss AM/PM` |
| پایش | `GET /core/api/order` با `orders[]`؛ typeها `id/symbolIsin/price/quantity/side/orderStateStr/executedQuantity` |
| صف | `GET /ms/api/MarketSheet/order-place?actionType=get` + هدرِ `order-id`؛ `orderPlace/volumeAhead` |
| تفسیر صف | کدِ مرجع، `orderPlace <= 1` را «اولِ صف» می‌خواند — **فرضیه**، نه شاهدِ مستقل |
| نرخ/زمان | rate limiter ۱۰ درخواست/ثانیه؛ monitor loop هر ۵s تا ۶۰ بار؛ بدونِ backoff |
| امنیت | `tokenCache.ts` هدرهایِ Authorization/Cookie را در `.user-data/easy/token-cache.json` **روی دیسک** ذخیره می‌کند؛ log نیز payload دارد — الگویِ ناامن |
| تست | تست‌هایِ unit/performance/integration، ولی بیشترشان live/مرتبط با خریدِ واقعی‌اند؛ برایِ CI امن نیستند |
| مجوز | هیچ فایلِ مجوز؛ GitHub API 404 |
| اثر | مقایسهٔ schema و شناسهٔ صف؛ **هیچ کد یا token storage کپی نشد** |

## ۶) amirali110/Sarkhati-Bourse

| محور | یافته |
| --- | --- |
| معماری | C++/Qt، `mainwindow.cpp` ۱۶۵ خط |
| ارسال | URLهایِ ناقص/متفاوت (`https://com/Web/V1/Order/Post` و `https://.ir/Web/V1/Order/Post`)؛ فیلدهایِ `orderCount/orderPrice/orderSide` رشته‌ای |
| احراز | هیچ مکانیزمِ واقعی در کد پیدا نشد |
| زمان | QTimer یک‌میلی‌ثانیه‌ای و مقایسهٔ QTime؛ بدون clock drift واقعی |
| پایش/تست | هیچ |
| مجوز | هیچ فایلِ مجوز؛ GitHub API 404 |
| تصمیم | `REJECT` |

## چه چیزی در BorsTerminal از قبل بود

- قراردادِ `POST /core/api/v2/order` و envelope `{order}` (Round 11).
- دیده‌بان/پرتفوی/قدرت خرید فقط‌خواندنی (Round 10).
- `GET /core/api/order` و `ExecutionRecord`/`reconcile`.
- صفِ `/ms/api/MarketSheet/order-place` با عدمِ ادعایِ معنایِ `orderPlace`.
- Scheduler monotonic + ثبتِ target/actual/drift؛ محدودیت‌هایِ نرخِ durable.
- preflight خرید با BP و فروش با sellable؛ فروش همچنان مسدود.
- Paper lifecycle، duplicate guard، UNKNOWN/no-retry، halt.

## چه چیزی در Round 11A تغییر کرد

1. `get_money` فیلدِ `blockT2` (مشاهده‌شده در نشستِ زندهٔ ۲۰۲۶-۱۰-۲۱) را حفظ می‌کند.
2. `get_queue_position` دیگر در نبودِ `orderId` تطبیق، ردیفِ اول را به سفارشِ ما
   نسبت نمی‌دهد؛ بی‌تطبیق ⇒ `None/UNKNOWN`.
3. گاردِ قرارداد، حضورِ فیلدهایِ الزامیِ m-fazel و Reza را می‌سنجد و حذفِ
   آگاهانهٔ `commission/totalValue` را ثبت می‌کند.
4. گزارش‌هایِ این audit و live-session اضافه شدند.

## چه چیزی کپی نشد

- هیچ کدِ Rust/TypeScript/Python/C++ از شش مخزن کپی نشد.
- الگوهایِ ناامنِ token cache، log کردنِ Authorization/بدنه، و UI xpath کپی نشدند.
- منطقِ «HEAD probe = latency ارسال» و «orderPlace<=1 = اولِ صف» به‌عنوانِ
  فرضیه ثبت شد، نه واقعیت.

## تست‌ها و محدودیت

- `dev/execution_write_contract_v1147.py`: ۳۶/۳۶.
- `dev/easytrader_adapter_v1113.py`: ۱۶۳/۱۶۳ (شاملِ کنترلِ منفیِ صفِ بیگانه).
- `dev/execution_account_sources_v1146.py`: ۲۵/۲۵ (شاملِ `blockT2`).
- تست‌هایِ live مراجع اجرا نشدند؛ هیچ سفارشِ واقعی در این audit ارسال نشد.
- مجوزِ هیچ مرجع روشن نشد؛ استفادهٔ مستقیم از کد ممنوع است.
