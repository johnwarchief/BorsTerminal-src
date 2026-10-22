# Round 19 — مهندسیِ جایگاهِ صف و اثباتِ تأخیرِ اجرا

- تاریخ: 2026-10-22
- شاخه: `mission/sarkhati-round19-queue-position-latency-2026-10-22`
- پایه: `03ce4b67` (گزارشِ Round 18)؛ پیاده‌سازی: `639106fe`
- دامنه: تلمتریِ مشترکِ API/Browser/Scheduler، قراردادِ جایگاهِ صف، Queue Monitor در `/autoclicker`، و Benchmarkِ mock. هیچ سفارشِ واقعی ارسال نشد.

## ۱) خلاصهٔ اجرایی

یک تلمتریِ مشترک ساخته شد که timestampهایِ ایجادِ قصد، preflight، هدفِ زمان‌بندی، شروعِ اجرا، کلیک، درخواست، پاسخ، ack، order-id و جایگاه را جدا نگه می‌دارد. فاصله‌هایِ درون‌فرایندی از monotonic و زمان‌هایِ دیواری با منبعِ صریح محاسبه می‌شوند؛ `one_way_ms` ساخته نمی‌شود و شاهدِ غایب `None` می‌ماند.

قراردادِ جایگاهِ Mofid از بستهٔ کلاینتِ اول‌طرف و ستون‌هایِ UI مشاهده شد: مسیرِ آن **POST** است (`/Order/OrderPlace` و `/Order/OrderPlaceInfo` با `data.orderPlaces` و فیلدهایِ `orderId`، `orderPlace`، `volumeAhead`). این مسیر در راندِ GET-only صدا زده نشد و `invoked=false` است. `/Rlc/MarketSheet/{isin}` فقط دفترِ تجمیعیِ خرید/فروش است و رتبهٔ سفارشِ کاربر نیست.

مسیرِ جایگاهِ EasyTrader یک **GET** مستقل است (`/ms/api/MarketSheet/order-place?actionType=get` با هدرِ `order-id`) و در آداپتور پیاده و با mock تست شده است. این قرارداد به Mofid تعمیم داده نشد.

Queue Monitor به بخشِ «جایگاه سفارش و عملکرد سرخطی» در `/autoclicker` متصل شد. در نبودِ سفارشِ واقعی یا قراردادِ فقط‌خواندنی، رتبه ساخته نمی‌شود: `UNSUPPORTED_READ_ONLY`، `UNKNOWN`، `ERROR` و `NO_ORDER_ID` با علتِ صریح نمایش داده می‌شوند و مقدارِ ناموجود هرگز صفر نمی‌شود. مقدارِ خامِ `0` هم «رتبهٔ اول» تفسیر نمی‌شود.

در Benchmarkِ mock، سربازِ محلیِ موتورِ API در p95 حدودِ `0.01 ms` و مسیرِ مرورگرِ mock در p95 حدودِ `5.54 ms` بود (۲۰ نمونه برایِ هر مسیر). تأخیرِ Scheduler در ۵ نمونه p95 حدودِ `0.003 ms` و خطای هدفِ دیواری p95 صفر بود. این اعداد **تأخیرِ کارگزاری، شبکه یا صفِ بورس نیستند** و همان‌طور که در بندِ ۷ توضیح داده شده `NOT_MEASURED` می‌مانند.

`live_enabled=false` و `live_ready=false` در همهٔ پاسخ‌ها و UI حفظ شدند. هیچ POSTِ سفارش، هیچ کلیکِ ثبت سفارش و هیچ تغییرِ وضعیت در کارگزاری انجام نشد؛ تعدادِ سفارش‌هایِ باز و امروز صفر است.

## ۲) مبنای Git

| مورد | مقدار |
|---|---|
| شاخهٔ مبنا | `mission/sarkhati-round18-mofid-account-reconciliation-2026-10-22` |
| commit پایه | `03ce4b67` |
| commit پیاده‌سازیِ Round 19 | `639106fe` |
| commit گزارش | commit بعدی رویِ همین شاخه |
| شاخهٔ راند | `mission/sarkhati-round19-queue-position-latency-2026-10-22` |

شناسه‌هایِ گزارش‌شدهٔ Round 18 (`724047c9` و `03ce4b67`) با Git واقعی تأیید شدند. هیچ تغییری رویِ `main` یا شاخه‌هایِ نامرتبط انجام نشد.

## ۳) قراردادِ جایگاهِ صف به‌ازایِ هر کارگزاری

| کارگزاری | منبعِ order ID | مسیرِ جایگاه | فیلدهایِ پاسخ | معنایِ رتبه | timestamp | تازگی | شاهد | وضعیت |
|---|---|---|---|---|---|---|---|---|
| Mofid (Titan) | `GET /Order/open-orders` و `/Order/today-order`، فیلدِ `orderId` | `POST /Order/OrderPlace`، `/Order/OrderPlaceInfo` رویِ gateway | `data.orderPlaces` → `orderId`، `orderPlace`، `volumeAhead` | خام؛ `0` به‌معنایِ رتبهٔ اول نیست | هیچ timestampِ سرور برایِ ورود به صف دیده نشد | `as_of` محلیِ مشاهده | بستهٔ کلاینتِ اول‌طرف + ستون‌هایِ DOM؛ `invoked=false` | `FIRST_PARTY_CLIENT_OBSERVED`؛ در مسیرِ فقط‌خواندنی `BLOCKED` |
| Mofid — UI | همان `orderId` فهرست | ستون‌هایِ جدولِ سفارش‌ها | `COMMON_ORDER-orderPlace` («جایگاه») و `COMMON_ORDER-orderVolume` («جایگاه حجمی») | خام؛ نگاشتِ ردیف به `orderId` تأیید نشده | زمانِ مشاهدهٔ UI | لحظهٔ مشاهده | هدرهایِ DOM؛ سفارشِ واقعی برایِ نگاشت وجود ندارد | `DOM_HEADERS_OBSERVED`؛ نگاشت `UNVERIFIED` |
| Mofid — MarketSheet | — | `GET /Rlc/MarketSheet/{symbolIsin}` | دفترِ تجمیعیِ خرید/فروش | رتبهٔ سفارشِ کاربر نیست | — | — | مسیرِ فقط‌خواندنی | `usable_as_rank=false` |
| EasyTrader (Orbis) | فهرستِ سفارش‌هایِ آداپتور | `GET /ms/api/MarketSheet/order-place?actionType=get` با هدرِ `order-id` | `orderPlaces` → `orderId`، `orderPlace`، `volumeAhead` | خام؛ `0` به‌معنایِ اول نیست | `as_of` محلیِ آداپتور | مشاهدهٔ لحظه‌ای | `RezaMahdaviiDev/mofid`، `src/brokerages/easy/api/order.ts:291-301` + mock | `IMPLEMENTED_AND_TESTED`؛ تأییدِ کارگزاری `NOT_MEASURED` |

قواعدِ ثابت:

- وجودِ `orderId` یا پاسخِ موفقِ سفارش، اثباتِ رتبهٔ صف نیست.
- `orderPlace` و `volumeAhead` فقط مقدارِ خام‌اند؛ واحدِ `volumeAhead` در هیچ مرجعِ معتبری تعریف نشده و `UNVERIFIED` است.
- رتبه در یک کارگزاری با رتبه در کل بازار یکی گرفته نمی‌شود.
- `/Rlc/MarketSheet` برایِ Mofid و `MarketSheet` برایِ EasyTrader به‌عنوانِ رتبه استفاده نمی‌شوند.

## ۴) معنایِ رتبه و دامنهٔ پوشش

| وضعیتِ ردیف | معنا | نمایش |
|---|---|---|
| `KNOWN` | آداپتور برایِ همان `orderId` مقدار برگرداند | جایگاهِ خام + منبع + `as_of` + سریِ تغییرات |
| `UNKNOWN` | پاسخ خالی بود یا ردیفِ همان `orderId` پیدا نشد | «مقدار نداد»؛ بدونِ صفر |
| `UNSUPPORTED_READ_ONLY` | قراردادِ جایگاه در مسیرِ فقط‌خواندنی قابلِ صدا زدن نیست (Mofid) | علتِ POST و ممنوعیتِ GET |
| `NO_ORDER_ID` | ردیفِ سفارش شناسهٔ کارگزاری ندارد | علتِ نبودِ شناسه |
| `ERROR` | خطایِ شبکه/قرارداد در خواندنِ جایگاه | کدِ خطا؛ بدونِ رتبه |

- `queue_position=0` فقط «مقدارِ خامِ صفر» است؛ UI صریح می‌گوید `0 is not interpreted as first`.
- رتبهٔ قدیمی به‌عنوانِ جایگاهِ لحظه‌ای نمایش داده نمی‌شود؛ `as_of` و `queue_freshness` همراهِ آن است.
- تغییرِ جایگاه در `queue_series` (حداکثر ۵۰ مشاهده، با حذفِ تکرارِ پشتِ‌سرِهم) ثبت می‌شود.
- polling هر ۱۰ ثانیه است (`_QUEUE_POLL_MS`) و سریع‌تر از آن دقتِ بیشتری نمی‌سازد.

## ۵) تلمتریِ مشترک و تفکیکِ تأخیرها

فایلِ `execution_telemetry.py` منبعِ واحدِ timestampها و معیارهاست. همهٔ اعداد بر حسبِ میلی‌ثانیه‌اند؛ timezone برچسبِ `Asia/Tehran (fixed +03:30)` و precision برابرِ `ms` است.

| timestamp | منبع | واحد | معنا |
|---|---|---|---|
| `intent_created_wall_ms` | ساعتِ دیواریِ محلی | ms | لحظهٔ ساختِ قصد |
| `preflight_started_mono_ms` / `preflight_completed_mono_ms` | monotonic | ms | شروع/پایانِ آماده‌سازی |
| `scheduled_target_wall_ms` / `scheduled_target_mono_ms` | دیواری + لنگرِ monotonic | ms | زمانِ هدف |
| `execution_start_mono_ms` / `execution_start_wall_ms` | monotonic + دیواری | ms | شروعِ trigger |
| `send_started_mono_ms` / `send_started_wall_ms` | Scheduler | ms | ارسالِ واقعی پس از انتظار |
| `browser_click_started_mono_ms` | رویدادِ مرورگر | ms | شروعِ کلیک (فقط مسیرِ مرورگر) |
| `request_started_mono_ms` / `request_started_wall_ms` | موتور/درایور | ms | شروعِ درخواستِ مشاهده‌شده |
| `response_received_mono_ms` / `response_received_wall_ms` | موتور/درایور | ms | دریافتِ پاسخ |
| `broker_acknowledged_mono_ms` / `broker_acknowledged_wall_ms` | پاسخِ کارگزاری | ms | فقط با ackِ صریح |
| `order_id_observed_mono_ms` / `order_id_observed_wall_ms` | پاسخِ کارگزاری | ms | فقط با شناسهٔ صریح |
| `queue_position_observed_mono_ms` / `queue_position_observed_wall_ms` | آداپتور | ms | هنگامِ مشاهدهٔ جایگاه؛ در trigger نیست |
| `first_fill_mono_ms` / `first_fill_wall_ms` | شاهدِ اجرا | ms | فقط در صورتِ وقوع و شاهد |
| `clock_offset_ms` / `clock_quality` | Scheduler | ms / برچسب | آفست و کیفیتِ ساعت |

| معیار | فرمول | محدودیت |
|---|---|---|
| `preflight_ms` | پایان − شروعِ preflight | فقط سربازِ محلی |
| `scheduler_lag_ms` | ارسالِ واقعی − هدفِ monotonic | دقتِ spin/wake |
| `click_to_request_ms` | شروعِ درخواست − شروعِ کلیک | **latency یک‌طرفهٔ شبکه نیست** |
| `request_rtt_ms` | دریافتِ پاسخ − شروعِ درخواست | RTT؛ یک‌طرفه از آن ساخته نمی‌شود |
| `response_to_order_id_ms` | مشاهدهٔ order-id − دریافتِ پاسخ | فقط با شناسهٔ صریح |
| `order_id_to_queue_ms` | مشاهدهٔ جایگاه − مشاهدهٔ order-id | شاملِ فاصلهٔ polling است |
| `target_error_ms` | ارسالِ دیواری − هدفِ دیواری | عدم‌قطعیتِ آفستِ ساعت |
| `execution_to_request_ms` | شروعِ درخواست − شروعِ trigger | فقط مسیرِ دارایِ درخواست |
| `one_way_ms` | — | همیشه `None`؛ `RTT/2` مجاز نیست |

## ۶) تغییراتِ واقعیِ کد و UI

| فایل | تغییر |
|---|---|
| `execution_telemetry.py` | ماژولِ جدیدِ timestampها/معیارها؛ `to_dict` با timezone/precision/`one_way_ms=None` |
| `execution_strategy_core.py` | `telemetry` رویِ `StrategyResult` و `StrategyOrder` و در `public()` |
| `execution_strategy_engine.py` | ثبتِ preflight، هدف، Scheduler، کلیک، درخواست، پاسخ، ack و order-id در یک تلمتریِ مشترک؛ جایگاه در trigger ساخته نمی‌شود |
| `execution_mofid.py` | `MOFID_QUEUE_CONTRACT` با وضعیتِ `FIRST_PARTY_CLIENT_OBSERVED` و `invoked=false`؛ `queue_contract()` |
| `api/execution.py` | `GET /api/execution/queue-monitor`، سریِ جایگاه، حالت‌هایِ صریح، نرخِ ۱۰ ثانیه، بدونِ رتبهٔ جعلی |
| `frontend/.../orderClient.ts` | schema و hookِ `useQueueMonitor` + گاردِ `queueRankText` |
| `frontend/.../AutoClickerPage.tsx` | بخشِ «جایگاه سفارش و عملکرد سرخطی» با منبع/زمان/تازگی/علت، سریِ جایگاه و تلمتریِ آخرین اجرا |

نمونهٔ UI در `_audit/round19_queue_section.png` (حالتِ خوانده‌شده) و `_audit/round19_queue_blocked.png` (حالتِ بی‌دسترسی) ثبت شده است. اسکرین‌شاتِ تمام‌صفحه به‌دلیلِ نمایشِ قدرتِ خرید در گیت ذخیره نشد.

## ۷) Benchmark و بزرگ‌ترین منابعِ تأخیر

شرایط: mockِ درون‌فرایندی، بدونِ شبکه و بدونِ سفارشِ واقعی. مسیرِ API dryness و مسیرِ مرورگر با `MockBrowserDriver` اجرا شد. برایِ مسیرِ پذیرفته‌شدهٔ API یک آداپتورِ بدل با RTTِ کنترل‌شده (۲۰ ms) استفاده شد.

| سنجه | نمونه | p50 | p95 | max | تفسیر |
|---|---:|---:|---:|---:|---|
| API dry-run — total موتور | 20 | 0.01 ms | 0.01 ms | 0.02 ms | سربازِ محلیِ موتور |
| Browser mock — total موتور | 20 | 4.59 ms | 5.54 ms | 5.68 ms | سربازِ محلیِ درایورِ mock |
| Scheduler lag | 5 | 0.001 ms | 0.003 ms | — | فاصلهٔ ارسال از هدفِ monotonic |
| Target error (دیواری) | 5 | 0.0 ms | 0.0 ms | — | با عدم‌قطعیتِ ساعت |

- مسیرِ مرورگرِ mock حدودِ ۴.۵ ms در هر اجرا بیشتر از API طول می‌کشد؛ این عدد فقط سربازِ موتور/درایورِ بدل است و شاملِ رندر، ناوبری، کلیکِ واقعی، شبکه یا OMS نیست.
- بزرگ‌ترین اجزایِ باقی‌مانده — ورود به OMS/سامانهٔ معاملاتی، RTTِ واقعی، تأخیرِ کلیک/صفحه و زمانِ صف — با سفارشِ واقعی اندازه‌گیری نشده‌اند: `NOT_MEASURED`.
- بهینه‌سازیِ حدسی اضافه نشد. پیش‌ساختِ payload و preflight پیش از لحظهٔ هدف از قبل وجود دارد؛ حذفِ بررسی‌هایِ حیاتی، JS injection یا `force click` فقط به‌دلیلِ سرعت وارد مسیر نشد. polling از ۵ به ۱۰ ثانیه رفت تا نرخِ درخواست با قراردادِ کارگزاری سازگار بماند.

## ۸) قاعدهٔ تقدمِ قیمت و زمان

متنِ مادهٔ ۴ «آیین‌نامهٔ معاملات در شرکت بورس اوراق بهادار تهران»:

> «معاملات بورس با رعایت اولویت قیمت و زمان ورود سفارش به سامانهٔ معاملاتی انجام می‌شود. جزئیات نحوه انجام معاملات در "دستورالعمل نحوه انجام معاملات" خواهد آمد.»

منابع: نسخهٔ منتشرشده در سایتِ اتحادیهٔ کارگزاران (`seba.ir`) و دو نسخهٔ هم‌سانِ دیگر. نسخهٔ کاملِ PDF به‌دلیلِ timeout شبکه دانلود نشد؛ متنِ ماده از snippetهایِ همان نسخه‌ها و نسخه‌هایِ هم‌سان خوانده شد.

نتیجهٔ مهندسی:

- ملاکِ تقدم، **زمانِ ورودِ سفارش به سامانهٔ معاملاتی** است، نه زمانِ ارسال از BorsTerminal.
- زمانِ ارسالِ ما، زمانِ پذیرشِ کارگزاری و زمانِ ورود به صف سه چیزِ جدا هستند. تا وقتی timestamp/sequenceِ سامانهٔ معاملاتی در دسترس نباشد، نمی‌توانیم زمانِ ورود به صف را ادعا کنیم.
- قواعدِ عرضهٔ اولیه یا روش‌هایِ خاصِ بازار به صفِ عادی تعمیم داده نشد.
- شرایطی که اولویت را تغییر می‌دهند (اصلاح/لغو/تغییرِ قیمت) در این راند اندازه‌گیری نشده و `NOT_MEASURED` است.

منابع:
- [آیین‌نامهٔ معاملات — seba.ir](https://www.seba.ir/uploads/1/2022/Sep/05/ayinname%20moamelat.pdf)
- [نسخهٔ هم‌سان — nnovin.ir](https://nnovin.ir/uploads/6013c5ec-5e44-4448-aa5a-af58636ded1f/%D9%85%D8%B9%D8%A7%D9%85%D9%84%D8%A7%D8%AA_%D9%86%DA%AF%D8%A7%D9%87_%D9%86%D9%88%DB%8C%D9%86.pdf)
- [متنِ ماده ۴ — vindad](https://vindad.com/blog/iran-rules-reference/burse/p8484/)

## ۹) گردشِ کارِ آزمونِ زندهٔ آینده (بدونِ اجرایِ خودکار)

1. مالک صریحاً یک سفارشِ مشخص را مجاز کند: نماد، سمت، قیمت، تعداد و سقفِ مبلغ.
2. وضعیتِ بازار و شرایطِ سفارش از منبعِ واقعی بررسی شود؛ اگر داده یا مجوز نیست، توقف.
3. `live_enabled` و `live_ready` فقط با تصمیمِ صریحِ مالک و گذرِ گیت‌هایِ عملیاتی روشن شوند؛ هیچ مسیرِ خودکار مجاز نیست.
4. فقط یک سفارش ارسال شود؛ پس از UNKNOWN هیچ retry یا fallback خودکار مجاز نیست.
5. فقط `orderId` واقعیِ همان سفارش برایِ خواندنِ جایگاه استفاده شود؛ شناسه ساخته نشود.
6. اگر endpointِ جایگاه در زمانِ آزمون در دسترس نبود، نتیجه `BLOCKED` ثبت شود؛ سفارشِ دوم ممنوع.
7. تلمتریِ همان اجرا (همهٔ timestampها و تأخیرها) ذخیره و با سریِ جایگاه مقایسه شود.

وضعیتِ فعلی: هیچ سفارشِ واقعی وجود ندارد؛ مسیرِ جایگاهِ Mofid با POST است و در allowlistِ GET-only نیست؛ بنابراین آزمونِ زنده در این راند `NOT_PERFORMED` و رتبهٔ واقعی `BLOCKED` است.

## ۱۰) تست‌ها، build و سلامتِ دیتابیس

| بررسی | نتیجه |
|---|---|
| `dev/sarkhati_queue_round19_v1167.py` | 51 / 51 |
| `dev/mofid_account_v1166.py` | 14 / 14 |
| `dev/mofid_adapter_v1163.py` | 39 / 39 |
| `dev/strategy_guard_v1123.py` | 57 / 57 |
| `npx vitest run src/__tests__/autoclicker-page.spec.tsx` | 11 / 11 |
| `npx tsc -b` | exit 0 |
| `npm run build` | exit 0 (فقط هشدارِ chunk > 500 kB) |
| بررسیِ زندهٔ UI با نشستِ تأییدشده | 7 / 7 (پیش از بسته‌شدنِ پنجره) |
| بررسیِ زندهٔ UI در حالتِ بی‌دسترسی | 6 / 6 |
| `dev/persian_glyph_guard.py` | 4 / 4 |
| دیتابیسِ عملیاتیِ worktree | `user.db` و `market.db` بدونِ تغییر (هشِ پیش/پس یکسان) |
| `live_enabled` / `live_ready` | `false` / `false` در API و UI |
| سفارشِ واقعی / POSTِ سفارش | صفر |

خطِ زمانیِ نشست:

- 03:40 — `READ_ONLY_PROBE_OK`؛ ۱۲ دارایی، ۰ سفارشِ باز، ۰ سفارشِ امروز.
- 03:47 — بررسیِ زندهٔ UI: بخشِ جایگاه، منبع، نرخِ ۱۰ ثانیه، نبودِ رتبهٔ جعلی و `live_ready=false` (7/7).
- 21:39 — پنجرهٔ Mofid در فاصلهٔ زمانیِ جلسه بسته شده بود (`HOST_DOWN`).
- 21:41 — همان پروفایلِ نام‌دار بدونِ reset باز شد؛ `NO_SESSION` (نشستِ ذخیره‌شده در پروفایل موجود نبود). پنجره باز و منتظرِ ورودِ دستیِ مالک است.

## ۱۱) وضعیت‌ها

| موضوع | وضعیت |
|---|---|
| قراردادِ API جایگاهِ Mofid (POST، فیلدها) | `FIRST_PARTY_CLIENT_OBSERVED` |
| ستون‌هایِ UI جایگاهِ Mofid | `DOM_HEADERS_OBSERVED`؛ نگاشتِ ردیف `UNVERIFIED` |
| خواندنِ جایگاهِ Mofid در راندِ فقط‌خواندنی | `BLOCKED` |
| قراردادِ GETِ جایگاهِ EasyTrader | `IMPLEMENTED_AND_TESTED` |
| تأییدِ واقعیِ جایگاهِ EasyTrader با کارگزاری | `NOT_MEASURED` |
| تلمتریِ مشترکِ API/Browser/Scheduler | `IMPLEMENTED_AND_TESTED` |
| Scheduler lag رویِ همین ماشین | `IMPLEMENTED_AND_TESTED` (۵ نمونه) |
| Queue Monitor و اتصال به UI | `IMPLEMENTED_AND_TESTED` |
| رتبهٔ واقعیِ صف / معیارهایِ عملکردِ واقعی | `BLOCKED` / `NOT_MEASURED` |
| قاعدهٔ تقدمِ قیمت و زمان (مادهٔ ۴) | `VERIFIED` (متنِ ماده) |
| شرایطِ تغییرِ اولویت | `NOT_MEASURED` |
| ارسالِ سفارشِ واقعی | `NOT_PERFORMED` |
| نشستِ Mofid در پایان | `BLOCKED` (`NO_SESSION`؛ نیازمندِ ورودِ مالک) |

## ۱۲) commitها و محدودیت‌هایِ باقی‌مانده

- پایه: `03ce4b67`
- پیاده‌سازی: `639106fe` — تلمتری، قرارداد، مانیتور، UI، گارد و شواهد.
- گزارش: commit بعدی رویِ همین شاخه.

محدودیت‌ها:

1. هیچ سفارشِ واقعی وجود ندارد؛ رتبهٔ واقعیِ صف و latencyِ واقعیِ کارگزاری اندازه‌گیری نشده است.
2. مسیرِ جایگاهِ Mofid POST است و در allowlistِ فقط‌خواندنیِ این راند قابلِ صدا زدن نبود؛ برایِ عبور از این گیت، مجوزِ صریحِ مالک و قراردادِ نوشتنِ معتبر لازم است.
3. هیچ timestamp/sequenceِ ورود به سامانهٔ معاملاتی از Mofid یا EasyTrader دیده نشد؛ «زمانِ ارسالِ ما» با «زمانِ ورود به صف» یکی گرفته نمی‌شود.
4. نگاشتِ ستون‌هایِ UIِ Mofid به `orderId` بدونِ سفارشِ واقعی تأیید نشد.
5. واحد و معنایِ `volumeAhead` در هیچ مرجعِ معتبری تعریف نشده و `UNVERIFIED` است.
6. Benchmark فقط سربازِ محلیِ موتور/درایورِ mock را می‌سنجد؛ RTT، OMS و صفِ واقعی خارج از آن است.
7. پنجرهٔ Mofid پس از فاصلهٔ جلسه بسته شده بود؛ پروفایلِ بازشده نشست ندارد و برایِ بررسیِ زندهٔ تازه، ورودِ دستیِ مالک لازم است.
8. سقفِ نرخِ polling ۱۰ ثانیه است؛ سریع‌تر شدنِ آن دقتِ رتبه را اثبات نکرده و فقط نرخِ درخواست را بالا می‌برد.
