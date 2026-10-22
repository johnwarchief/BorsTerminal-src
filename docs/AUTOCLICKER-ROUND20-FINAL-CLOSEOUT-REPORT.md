# Round 20 — بستن نهایی سرخطی: قرارداد جایگاه، شاهد واقعی و تصمیم انتشار

- تاریخ: 2026-10-22
- شاخه: `mission/sarkhati-round20-final-closeout-2026-10-22`
- پایه: `2c8c269b` (نوک Round 19)
- دامنه: تکمیل قرارداد جایگاه، خطاها، readiness و گزارش نهایی. هیچ قابلیت نمایشی تازه اضافه نشد.

## ۰) خلاصهٔ حکم

| حکم | نتیجه |
|---|---|
| A. ENGINEERING COMPLETE | **YES** در دامنهٔ mock/قرارداد/حساب فقط‌خواندنی؛ مسیرِ زندهٔ جایگاهِ Mofid عامدانه سیم‌کشی نشده و مرزِ آن مستند است |
| B. READ-ONLY QUEUE VERIFIED | **NO** |
| C. REAL PERFORMANCE VERIFIED | **NO** |
| وضعیت فعلی استفاده | **MOCK_READY** |
| گام بعدی لازم | **SUPERVISED_LIVE_TEST_REQUIRED** (هنوز محقق نشده) |
| READ_ONLY_READY / LIVE_EXECUTION_READY | **NO / NO** |
| `live_enabled` / `live_ready` | `false` / `false` |
| سفارش ثبت/ویرایش/لغو از طریق BorsTerminal | **صفر** |

## ۱) بازیابی وضعیت واقعی

| مورد | مقدار واقعی |
|---|---|
| شاخهٔ گزارش‌شدهٔ Round 19 در مأموریت | `mission/sarkhati-round19-queue-position-2026-10-22` |
| شاخهٔ واقعی Round 19 | `mission/sarkhati-round19-queue-position-latency-2026-10-22` |
| Base | `03ce4b67` |
| Implementation | `639106fe` |
| Report | `51bf826e` |
| Mission tip | `2c8c269b` |
| Remote | `github` = `https://github.com/johnwarchief/BorsTerminal-src.git` |

شناسه‌های `03ce4b67`، `639106fe`، `51bf826e` و `2c8c269b` با Git واقعی تطبیق داده شدند. تنها اختلاف، واژهٔ `latency` در نام شاخهٔ واقعی است؛ محتوای commitها یکی است. تغییرات منتشرنشدهٔ دیگری overwrite نشد.

## ۲) قرارداد نهایی هر کارگزاری

### Mofid (Titan)

| مورد | شاهد |
|---|---|
| order ID | `GET /Order/open-orders` و `/Order/today-order`، فیلد `orderId` |
| پرسش جایگاه | `POST /Order/OrderPlaceInfo` (نام کلاینت `GetOrderPlaceAPI`) و `POST /Order/OrderPlace` (`GetOrderPlacePostAPI`) |
| بدنهٔ مشاهده‌شده | `{orderId: ["<broker order id>"]}` در effect پایش ۵ثانیه‌ای |
| پاسخ | `data.orderPlaces` با فیلدهای `orderId`، `orderPlace`، `volumeAhead` |
| نوشتن‌ها | `/Order/send` (POST)، `/Order/update` (PUT)، `/Order/delete` (DELETE) — جدا از پرسش‌های بالا |
| stream واقعی | WebSocket روی `https://ls.mofidonline.com` (تبدیل به `wss://`)، تاپیک `orderplace:{orderId}`، فیلدهای `isin`، `volume-ahead`، `placement`، بدون snapshot |
| معنای `orderPlace`/`placement` | خام؛ `0` به‌معنای رتبهٔ اول نیست. کلاینت اول‌طرف خودش مقدار falsy را با `-` نشان می‌دهد |
| دامنه | per-order؛ همان نماد و سمتِ همان سفارش، نه رتبهٔ کل بازار |
| واحد `volumeAhead` | `UNVERIFIED`؛ هیچ مرجع معتبری واحدش را تعریف نکرده |
| `source_verified` | **false**؛ هیچ پاسخ واقعیِ جایگاه مشاهده نشده |
| `invoked` | **false**؛ هیچ‌کدام از دو POST و هیچ stream صدا زده نشد |

نتیجه: این دو POST از نظر کدِ کلاینت **پرسشِ خواندنی** هستند (نام‌های GetOrderPlace…، `dto = response.orderPlaces`، و مسیرهای نوشتن جدا)، ولی این شاهد، «تأیید با پاسخ واقعی» نیست. طبق محدودیت ایمنی، هیچ‌کدام زنده فراخوانی نشد.

### EasyTrader (Orbis)

| مورد | شاهد |
|---|---|
| مسیر | `GET /ms/api/MarketSheet/order-place?actionType=get` |
| هدر | `order-id` با شناسهٔ همان سفارش |
| پاسخ | `orderPlaces[]` با `orderId`، `orderPlace`، `volumeAhead` |
| تطبیق | فقط با `orderId`؛ ردیف اول فهرست به سفارش ما نسبت داده نمی‌شود |
| خالی/ناموجود | `None` ⇒ `UNKNOWN`، نه صفر |
| HTTP 401/403 | خطای نشست (`SESSION_EXPIRED`/`AUTH_FAILED`) + به‌روزرسانی حکم نشست |
| HTTP 5xx | `NETWORK_ERROR` ⇒ `ERROR` |
| HTTP 404/سایر 4xx | `UNKNOWN` برای همان شناسه |
| timeout/network | `TIMEOUT`/`NETWORK_ERROR` ⇒ `ERROR` |
| هم‌زمانی | قفل per-order + کش ۲ثانیه‌ای؛ پنج فراخوانی هم‌زمان = یک GET، همان `as_of` |
| `as_of` | زمان محلیِ دریافت؛ timestamp سرور ندارد |
| واحد `volumeAhead` | `UNVERIFIED` |
| `source_verified` | **false**؛ تطبیق با UI واقعی کارگزاری انجام نشده |

## ۳) وضعیت نشست و endpointهای آزموده‌شده

| مورد | وضعیت |
|---|---|
| پنجرهٔ Mofid | باز و `ready` |
| نشست Mofid | `NEEDS_LOGIN` / `LOGIN_REQUIRED`؛ `NO_SESSION` |
| توکن در حافظه | ندارد |
| بررسیِ session این راند | انجام نشد؛ ورود دستی مالک لازم است |
| سفارش باز/امروز | آخرین وضعیت تأییدشده: صفر (03:40)؛ وضعیت فعلی بدون نشست `UNVERIFIED` |
| endpointهای Mofid صدا زده‌شده | فقط بارگیری GET بسته/صفحه از پنجرهٔ باز؛ هیچ POST سفارش/جایگاه |
| endpointهای EasyTrader صدا زده‌شده | هیچ؛ فقط mock transport |
| بازار | بسته (زمان محلی 22:xx) |

**داشتن نشست سالم هم به‌معنای تأیید رتبهٔ صف نیست.** در این راند حتی نشست سالم هم نداشتیم.

## ۴) معنای فیلدها و محدودیت‌ها

- `orderPlace` و `placement` خام‌اند؛ صفر «اول» نیست. UI اول‌طرف هم صفر/falsy را `-` نشان می‌دهد.
- `volumeAhead` خام و بی‌واحد است؛ هر عددی بدون تعریف قراردادی، «حجم جلوتر» نامیده نمی‌شود.
- جایگاه per-order است؛ تعمیم آن به «رتبه در کل بازار» ممنوع است.
- `as_of` زمان محلیِ مشاهده است، نه زمان تولید داده در کارگزاری.
- WebSocket تاپیک `orderplace:{orderId}` بدون snapshot است؛ مقدار اولیه از پرسش POST می‌آید و بعد push به‌روزش می‌کند.
- نوع بازار/صف عادی با عرضهٔ اولیه یکی گرفته نمی‌شود.

## ۵) Benchmark API در برابر Browser

شرایط: mock درون‌فرایندی، بدون شبکه و بدون سفارش؛ هر اجرا ۲۰ نمونه برای API و ۲۰ نمونه برای Browser. سه اجرای مستقل:

| اجرا | API p50 | API p95 | Browser p50 | Browser p95 | Scheduler p50 | Scheduler p95 | Target error p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| ۱ | 0.01 ms | 0.01 ms | 4.45 ms | 4.89 ms | 0.003 ms | 0.86 ms | 1.0 ms |
| ۲ | 0.01 ms | 0.01 ms | 4.66 ms | 6.10 ms | 0.001 ms | 0.003 ms | 0.0 ms |
| ۳ | 0.01 ms | 0.01 ms | 4.74 ms | 4.95 ms | 0.001 ms | 0.004 ms | 0.0 ms |

- مسیر API در mock عملاً سربازِ موتور است؛ مسیر Browser حدود ۴.۵ ms بیشتر است، ولی این عدد شامل رندر/ناوبری/کلیک واقعی/شبکه/OMS نیست.
- Scheduler p95 در یک اجرا outlier 0.86 ms داشت؛ میانه 0.001–0.003 ms.
- تعداد درخواست mock: صفر ترابری واقعی؛ مسیر پذیرفته‌شدهٔ بدل: یک submit؛ retry: صفر؛ HTTP error: صفر.
- `one_way_ms` همیشه `None` است؛ از RTT/2 یا اختلاف ساعت استخراج نشد.
- **زمان ورود به سامانهٔ معاملاتی، OMS و صف واقعی اندازه‌گیری نشد: `NOT_MEASURED`.**
- Benchmark زنده ممکن نبود: نشست ندارد، سفارش ندارد، بازار بسته است.

## ۶) نتایج Queue Monitor

| سناریو | نتیجه |
|---|---|
| Mofid، بدون سفارش/نشست | `blocked`؛ `queue_source_verified=false`، `queue_result_known=false`، بدون رتبه |
| Mofid، سفارش فرضی | `UNSUPPORTED_READ_ONLY`؛ علت POST/WS و ممنوعیت مسیر فقط‌خواندنی |
| EasyTrader KNOWN | مقدار خام ۰/حجم ۰ حفظ می‌شود؛ `queue_result_known=true`، `queue_source_verified=false` |
| EasyTrader خالی | `UNKNOWN`، بدون صفر |
| EasyTrader خطا | `ERROR`، بدون رتبه |
| UI زندهٔ حالت بی‌دسترسی | ۶/۶؛ چیپ‌های «منبع: تأییدنشده» و «نتیجه: نامعلوم» و «دریافت در رابط» دیده شدند |

Queue Monitor به `/autoclicker` متصل است و هیچ ادعای رتبهٔ اول ندارد (`claims_first_rank=false`). نرخ polling ۱۰ ثانیه است.

## ۷) تفکیک گلوگاه

| مرحله | وضعیت |
|---|---|
| آماده‌سازی در برنامه | اندازه‌گیری‌شده (preflight monotonic) |
| انتظار Scheduler | اندازه‌گیری‌شده (p50/p95 در سه اجرا) |
| تأخیر کلاینت/شبکه | فقط mock؛ زنده `NOT_MEASURED` |
| پردازش سمت کارگزاری | `NOT_MEASURED` |
| پذیرش/رد سفارش | mock یک submit؛ زنده `NOT_MEASURED` |
| ورود به سامانهٔ معاملاتی | `NOT_MEASURED` (timestamp/sequence ندارد) |
| دریافت/نبود جایگاه | `BLOCKED` برای Mofid؛ EasyTrader فقط mock |
| به‌روزرسانی UI | زمان ثبت در رابط (performance.now) اضافه شد؛ زمان واقعی سرور→paint `NOT_MEASURED` |

نتیجه: نمی‌توان گفت کدام مرحله در کارگزاری غالب است. تنها چیزی که با شاهد می‌توان گفت این است که سربازِ محلیِ موتور کوچک است و مسیر Browser در mock چند میلی‌ثانیه بیشتر است؛ ادعای بیشتر نیازمند سفارش واقعی است.

## ۸) readiness

گیت‌های مستقل:

- broker connection ready
- read-only account ready
- queue-position source verified
- queue-position result known
- execution preflight ready
- live execution authorized
- observed real-world performance

| گیت | وضعیت |
|---|---|
| اتصال کارگزاری | `NO_SESSION` / `BLOCKED` |
| حساب فقط‌خواندنی | آخرین Probe موفق: ۱۲ دارایی، ۰ سفارش؛ در این راند `NOT_MEASURED` |
| منبع جایگاه تأییدشده | **false** برای هر دو کارگزاری |
| نتیجهٔ جایگاه معلوم | **false** |
| preflight | `IMPLEMENTED_AND_TESTED` |
| مجوز اجرای زنده | `false` |
| عملکرد واقعی | `NOT_MEASURED` |

`read_only_account_ready` عمداً گیت‌های `queue_position` و `read_back` را در جمع خود نمی‌آورد؛ این دو مفهوم جدا هستند. گیت جایگاه در `warnings` و UI دیده می‌شود و باعث سبز شدن نادرست نمی‌شود.

## ۹) تست‌ها و گیت‌های نهایی

| بررسی | نتیجه |
|---|---|
| `dev/sarkhati_closeout_v1168.py` | 32 / 32 |
| `dev/sarkhati_queue_round19_v1167.py` | 51 / 51 |
| `dev/easytrader_adapter_v1113.py` | 163 / 0 |
| `dev/mofid_account_v1166.py` | 14 / 14 |
| `dev/mofid_adapter_v1163.py` | 39 / 39 |
| `dev/mofid_session_v1165.py` | 25 / 25 |
| `dev/strategy_guard_v1123.py` | 57 / 57 |
| `dev/p0_gates_v1118.py` | 33 / 33 |
| `dev/execution_ledger_v1108.py` | 48 / 48 |
| `dev/readiness_round15_v1162.py` | 7 / 7 |
| `dev/broker_connect_v1120.py` | 38 / 38 |
| `npx vitest run src/__tests__/autoclicker-page.spec.tsx` | 11 / 11 |
| `npx tsc -b` | exit 0 |
| `npm run build` | exit 0 (فقط هشدار chunk > 500 kB) |
| بررسی UI زندهٔ حالت بی‌دسترسی | 6 / 6 |
| `dev/persian_glyph_guard.py` | 4 / 4 |
| `python dev/run_all_tests.py` کامل | **NOT_COMPLETED** (اجرای هدفمند طبق مأموریت) |
| Frozen/PyInstaller build | **NOT_COMPLETED** |

دیتابیس‌های محافظت‌شده:

- `user.db` = `fbffd6eff0a9bd2fe68ee0cc48fcd783d97642a98dffc4961f877008d3fe4ff8`
- `market.db` = `fd688edbfe07e125018bf833bd6067ff5d0a0049ad4ddce37c49ded6790b73dc`
- هش پیش و پس از این راند یکسان است.

## ۱۰) تصمیم GO/NO-GO

- **GO** برای استفادهٔ mock/آزمایشی و ادامهٔ توسعهٔ فقط‌خواندنی.
- **NO-GO** برای هر ادعای «رتبهٔ واقعی صف» یا «عملکرد واقعی سرخطی».
- **NO-GO** برای اجرای زنده؛ `live_enabled=false` و `live_ready=false`.
- **SUPERVISED_LIVE_TEST_REQUIRED** تنها گام بعدی مجاز است، نه اجرای خودکار.

## ۱۱) موانع و اقدام مشخص

| مانع | یک اقدام لازم |
|---|---|
| نشست Mofid موجود نیست (`NO_SESSION`) | مالک در پنجرهٔ بازشدهٔ Mofid وارد شود و «ورود انجام شد؛ بررسی اتصال» زده شود |
| هیچ سفارش واقعی برای اثبات جایگاه نیست | مالک یک سفارش کوچک را **دستی** در UI رسمی Mofid ثبت کند (یا سفارش باز موجود را اعلام کند)؛ سپس فقط همان `orderId` برای پرسش جایگاه استفاده شود |
| مسیر جایگاه Mofid POST/WS است و adapter فقط GET می‌خواند | برای همان سفارش، مجوز صریح و جداگانه برای یک فراخوانی خواندنی `OrderPlaceInfo`/مشاهدهٔ stream داده شود؛ بدون این مجوز `BLOCKED` بماند |
| تأیید EasyTrader با کارگزاری | با نشست EasyTrader، یک سفارش واقعی موجود را در UI و API مقایسه کنید؛ هیچ نوشتن سفارش لازم نیست |
| timestamp/sequence ورود به سامانهٔ معاملاتی | از قرارداد کارگزاری درخواست شود؛ تا آن زمان `NOT_MEASURED` |
| واحد `volumeAhead` | تا تعریف رسمی، `UNVERIFIED` بماند |

## ۱۲) commit و وضعیت شاخه

- پایه: `2c8c269b`
- commit پیاده‌سازی: `94a99b3e`
- commit گزارش: commit بعدی رویِ همین شاخه
- شاخه: `mission/sarkhati-round20-final-closeout-2026-10-22`
- push فقط رویِ `github` و فقط همین شاخه؛ هیچ push/merge روی `main`.

## ۱۳) تأیید صریح عدم نوشتن سفارش

در این راند:

- تعداد درخواست‌های `POST /Order/send`: **صفر**
- تعداد `PUT /Order/update`: **صفر**
- تعداد `DELETE /Order/delete`: **صفر**
- تعداد سفارش واقعی ثبت/ویرایش/لغو‌شده: **صفر**
- تعداد کلیک ثبت سفارش در UI: **صفر**
- `live_enabled=false` و `live_ready=false`: **حفظ شد**
