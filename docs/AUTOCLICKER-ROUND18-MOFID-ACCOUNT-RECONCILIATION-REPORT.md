# Round 18 — تطبیقِ حساب مفید و اعتبارسنجیِ دادهٔ واقعی

- تاریخ: 2026-10-22
- شاخه: `mission/sarkhati-round18-mofid-account-reconciliation-2026-10-22`
- پایه: `a0f4f792` (Round 17 live)
- دامنه: تطبیقِ داده‌هایِ واقعی حساب، واحد/دقت، sellable، تازگی، قرارداد سفارش و readiness.

## ۱) خلاصهٔ اجرایی

نشستِ Round 17 (Edgeِ اختصاصی + توکنِ در حافظه) بدونِ ورودِ مجدد ادامه یافت.
Probeِ فقط‌خواندنی با همان نشست دو بار دیگر اجرا شد و به `READ_ONLY_PROBE_OK`
رسید: 12 دارایی، 0 سفارش باز، 0 سفارش امروز.

- **واحد/معنا/دقت:** مقدارِ `purchasingPower` از `/Accounting/Remain` با
  «قدرت خرید» در UI رسمی مفید دقیقاً یکی است (مقدار در گزارش ماسک شده) و
  «بلوکه شده» با `blockedBalance=0` می‌خواند. همان صفحه مبالغ پولی را «ریال»
  برچسب می‌زند؛ ویجتِ قدرت خرید خودش پسوندِ واحد ندارد. بستهٔ Titan همان فیلد
  را با فرمترِ مشترکِ رقم (همان فرمترِ قیمت/حجم، بدونِ تقسیم بر ۱۰) و
  `toFixed(0)` نمایش می‌دهد. وضعیت: **VERIFIED**، دقت **0**، `server_unit_field=false`.
- **12 دارایی:** هر 12 ردیف با ستون‌هایِ رسمیِ `runTimeShareCount`
  (دارایی لحظه)، `csdPortfolioCount` (دارایی سهام) و خرید/فروش امروز مقایسه شد؛
  هر 12 ردیف مطابق بودند. UI رسمی ستونِ «قابل‌فروش» **ندارد**؛ فرمولِ ما
  همچنان `CLIENT_DERIVED_UNVERIFIED` است.
- **تازگی:** هیچ فیلدِ زمانِ سرور در پاسخِ `/Accounting/Remain` نبود
  (`response_keys` فقط کلیدهایِ حساب/مالی داشت)؛ `fetched_at` زمانِ دریافتِ
  محلی است و تازگی **UNVERIFIED** است.
- **سفارش/read-back:** فهرست‌هایِ واقعی خالی‌اند؛ read-back **NOT_MEASURED** و
  هیچ شناسهٔ ساختگی فرستاده نشد. قرارداد/parsing/خطاها با fixture آزموده شد.
- **readiness:** `read_only_account_ready=false` (sellable/freshness/preflight_sell
  باز) و `live_enabled=false`/`live_ready=false`؛ موفقیتِ Probe اجرای زنده را
  فعال نکرد.
- **پیامد غیرمستقیم:** `customer/status` در این حساب `purchasingPower` ندارد؛
  منبعِ مبلغ `/Accounting/Remain` است. این در Round 17 اصلاح شد و در این راند
  با UI/API دوباره تأیید شد.

## ۲) نشست در آغاز و پایان

| زمان | وضعیت |
|---|---|
| آغاز | hostِ نام‌دارِ Mofid باز و سالم؛ صفحهٔ `tg.mofidonline.com`؛ `READ_ONLY_PROBE_OK` |
| میانه | Probe دوباره در 01:44 و 02:29/02:32؛ نشست همچنان معتبر |
| پایان | `READ_ONLY_PROBE_OK`؛ host باز؛ توکن در حافظه؛ `live_enabled=false`/`live_ready=false` |
| ورود مجدد | انجام نشد (نشست حفظ شد؛ پنجره/UI reset نشد) |

توکن فقط در حافظه و با اقدامِ «بررسی اتصال» خوانده شد؛ مقدار/کوکی در این گزارش
نیست. پروفایلِ مرورگر مطابقِ Round 17 رفتار می‌کند و برنامه آن را export نمی‌کند.

## ۳) P0-1 — واحد، معنا و دقتِ قدرت خرید

| شاهد | مشاهده |
|---|---|
| API `/Accounting/Remain` | `purchasingPower` عددیِ صحیح؛ `blockedBalance=0`؛ `credit=0`؛ `accountBalanceT1/T2` برابر با قدرت خرید؛ مقدار ماسک‌شده |
| UI رسمی مفید | «قدرت خرید: [مقدار دقیقاً برابر API]» و «بلوکه شده: 0»؛ مبالغِ پولیِ صفحه با «ریال» برچسب خورده‌اند |
| بستهٔ Titan | `/Accounting/Remain` فیلد را با فرمترِ مشترکِ رقم و `toFixed(0)` می‌فرستد؛ همان فرمتر برایِ قیمت/حجم استفاده می‌شود ⇒ تقسیم بر ۱۰ نیست |
| مقایسهٔ مقیاس | اگر واحد تومان بود، UI باید یک‌دهمِ مقدارِ API را نشان می‌داد؛ دقیقاً برابر است |
| دقت | عددیِ صحیح؛ `precision=0`؛ UI هم بدونِ اعشار |
| فیلدِ واحد در سرور | دیده نشد (`server_unit_field=false`) |

**نتیجه:** واحد `IRR`، معنا «قدرت خرید» و دقت 0 با دو شاهدِ مستقل (UI رسمی و
بستهٔ منتشرشده) **VERIFIED** است. هیچ ضرب/تقسیمِ حدسی انجام نشد.

## ۴) P0-2 — تعداد قابل‌فروش برای ۱۲ دارایی

### ۴-۱) منبعِ هر ورودی

| فیلدِ نرمال | فیلدِ پاسخ | واحد/نوع | منبع/زمان |
|---|---|---|---|
| `current_asset` | `currentAsset` | سهم، عدد | `/Portfolio/Daily`؛ `fetched_at` محلی |
| `today_bought` | `todayBoughtAsset` | سهم، عدد | همان پاسخ |
| `today_sold` | `todaySoldAsset` | سهم، عدد | همان پاسخ |
| `open_sell` | `openSellOrders` | سهم، عدد | همان پاسخ |
| `settled` | فرمولِ کلاینت: `currentAsset + todaySoldAsset - todayBoughtAsset` | سهم، عدد | UI رسمی همین را `csdPortfolioCount` می‌نامد |
| `sellable` | `max(0, min(currentAsset, settled) - openSellOrders)` | سهم، عدد | مشتقِ سمتِ کلاینت |

هیچ timestampِ سروری در ردیف‌هایِ Portfolio دیده نشد؛ `fetched_at` محلی است.

### ۴-۲) جدولِ ۱۲ دارایی

مقادیر/نمادها ماسک شده‌اند. ستون‌هایِ UI رسمی با API مقایسه شدند:

| ردیف | `runTimeShareCount` ↔ currentAsset | `csdPortfolioCount` ↔ settled | خرید/فروش امروز ↔ API | openSell (API) | فرمول sellable | ستونِ رسمی sellable | وضعیت |
|---|---|---|---|---|---|---|---|
| #01 | ✓ | ✓ | ✓ (0/0) | 0 | ✓ | ندارد | `IMPLEMENTED_AND_TESTED` |
| #02 | ✓ | ✓ | ✓ (0/0) | 0 | ✓ | ندارد | `IMPLEMENTED_AND_TESTED` |
| #03 | ✓ | ✓ | ✓ (0/0) | 0 | ✓ | ندارد | `IMPLEMENTED_AND_TESTED` |
| #04 | ✓ | ✓ | ✓ (0/0) | 0 | ✓ | ندارد | `IMPLEMENTED_AND_TESTED` |
| #05 | ✓ | ✓ | ✓ (0/0) | 0 | ✓ | ندارد | `IMPLEMENTED_AND_TESTED` |
| #06 | ✓ | ✓ | ✓ (0/0) | 0 | ✓ | ندارد | `IMPLEMENTED_AND_TESTED` |
| #07 | ✓ | ✓ | ✓ (0/0) | 0 | ✓ | ندارد | `IMPLEMENTED_AND_TESTED` |
| #08 | ✓ | ✓ | ✓ (0/0) | 0 | ✓ | ندارد | `IMPLEMENTED_AND_TESTED` |
| #09 | ✓ | ✓ | ✓ (0/0) | 0 | ✓ | ندارد | `IMPLEMENTED_AND_TESTED` |
| #10 | ✓ | ✓ | ✓ (0/0) | 0 | ✓ | ندارد | `IMPLEMENTED_AND_TESTED` |
| #11 | ✓ | ✓ | ✓ (0/0) | 0 | ✓ | ندارد | `IMPLEMENTED_AND_TESTED` |
| #12 | ✓ | ✓ | ✓ (0/0) | 0 | ✓ | ندارد | `IMPLEMENTED_AND_TESTED` |

- UI رسمی ستونِ **قابل‌فروش** ندارد؛ فقط `runTimeShareCount` و
  `csdPortfolioCount` را نشان می‌دهد. بنابراین «قابل‌فروش» رسمی **BLOCKED/UNDEFINED**
  است و برچسبِ `CLIENT_DERIVED_UNVERIFIED` برداشته نمی‌شود.
- `openSellOrders` در 12 ردیف 0 بود و فهرستِ `open-orders` هم خالی بود؛ این
  ورودی از API همساز است، ولی UI رسمی ستونِ سفارشِ بازِ فروش در این جدول ندارد.
- محدودیت‌هایِ مالکیت/مسدودی/داراییِ وثیقه در این endpoint فیلدِ صریحی ندارند؛
  ادعایی درباره‌شان ثبت نشد.

## ۵) P0-3 — تازگی، cache، 401 و خطاها

- **تازگی:** `freshness=LOCAL_FETCH_ONLY` و `server_timestamp=null`؛
  `response_keys` هم هیچ فیلدِ زمان نداشت. تازگی **UNVERIFIED** است و
  `fetched_at` هرگز زمانِ تولیدِ سرور جا زده نمی‌شود.
- **تکرار:** دو Probeِ مجاز با فاصلهٔ زمانی، همان 12 ردیف/0 سفارش/مقدار را دادند.
- **cache:** کشِ `customer/status` فقط 5 ثانیه است؛ مبلغِ `/Accounting/Remain`
  در هر Probe خوانده می‌شود. 401/403 شاهد و کش را باطل می‌کنند.
- **401/timeout:** با mock آزموده شد؛ در نشستِ واقعی عمداً 401 تولید نشد.
  timeout به `UNKNOWN_RESULT` می‌رسد و به صفر/حسابِ خالی تبدیل نمی‌شود.
- **schema متفاوت:** `customer/status` این حساب `purchasingPower` نداشت؛
  fallbackِ GET به `/Accounting/Remain` و تشخیصِ فقط‌نام‌کلیدها اضافه شد.
  هیچ مقدارِ حساسی از `email`/`bourseCode`/`title` در خروجیِ آداپتور نیست.

## ۶) P0-4 — قرارداد سفارش و read-back

| مسیر | متد | شناسه/وضعیت | نکته |
|---|---|---|---|
| `open-orders` | GET | `orderId` (رشته) / `orderState` | فیلدهایِ قیمت، تعداد، اجراشده، سمت، اعتبار |
| `today-order` | GET | `orderId` / `orderState` | همان شکل |
| `state/{id}` | GET | فقط شناسهٔ از فهرستِ واقعی | `orderState`/`state` |
| `detail/{id}` | GET | فقط شناسهٔ از فهرستِ واقعی | جزئیات/اجرا |
| `Order/send` | POST | — | 2xx = «ثبتِ درخواست»، نه پذیرش؛ در این راند صدا زده نشد |

- `orderId` رشتهٔ شناسهٔ کارگزار است؛ هیچ شناسهٔ ساختگی به endpoint واقعی نرفت.
- فهرست‌هایِ واقعی خالی‌اند ⇒ `order_detail=SKIPPED_NO_ORDERS` و
  read-back **NOT_MEASURED**.
- تست‌هایِ قرارداد: ID از فهرست، ردِ ID ساختگی پیش از ترافیک، 404/5xx،
  state mapping، و صفر POST.

## ۷) P0-5 — readiness

| گیت | وضعیت | علت |
|---|---|---|
| session | PASS | `/Order/customer/status` 200 |
| account_data | PASS | 12 دارایی؛ 0/0 سفارش |
| unit | PASS | UI رسمی + بستهٔ Titan؛ دقت 0 |
| sellable | UNVERIFIED | ستونِ رسمی sellable وجود ندارد؛ برچسبِ derived |
| freshness | UNVERIFIED | فقط fetched_at محلی |
| preflight_buy | PASS | purchasingPower عددی + واحد تأییدشده |
| preflight_sell | UNVERIFIED | sellable رسمی تأیید نشده |
| read_back | NOT_MEASURED | سفارشی برایِ شناسهٔ واقعی نیست |

`read_only_account_ready=false` (به‌خاطرِ sellable/freshness/preflight_sell)،
`live_enabled=false` و `live_ready=false`. موفقیتِ `READ_ONLY_PROBE_OK` سطحِ
اجرای زنده را فعال نکرد.

## ۸) P1 — UI

پنلِ «حساب مفید (ورود دستی، فقط‌خواندنی)» اکنون نشان می‌دهد:

- وضعیتِ اتصال و `READ_ONLY_PROBE_OK`.
- قدرت خرید + `IRR` + `VERIFIED` + دقت 0 + زمانِ دریافت.
- تعداد دارایی‌ها، سفارش باز/امروز، و وضعیتِ read-back.
- `sellable: CLIENT_DERIVED_UNVERIFIED` و آمادگیِ حساب «ناقص» با گیت‌هایِ باز.
- `تازگی: LOCAL_FETCH_ONLY` / نبودِ `server_timestamp`.
- `live_enabled=false` و `live_ready=false`.

آزمونِ مرورگرِ زنده با همان نشست: 5/5. اسکرین‌شاتِ حسابِ واقعی برایِ
حفظِ حریمِ خصوصی commit نشد.

## ۹) تست‌ها، build و دیتابیس

| مورد | نتیجه |
|---|---|
| `dev/mofid_account_v1166.py` | 14/14 |
| `dev/mofid_adapter_v1163.py` | 39/39 |
| `dev/mofid_session_v1165.py` | 25/25 |
| `dev/mofid_readiness_v1164.py` | 14/14 |
| `frontend/src/__tests__/autoclicker-page.spec.tsx` | 8/8 |
| `_audit/round18_ui_check.py` (مرورگرِ زنده، backend واقعی) | 5/5 |
| `npx tsc -b` | 0 خطا |
| `npm run build` | exit 0 |
| suite کامل | عمداً تکرار نشد (تغییر زیرساختی نبود؛ suite پیشینِ Round 17 سبز) |
| دیتابیس عملیاتی | `market.db=fd688edb...` و `user.db=fbffd6ef...` بدون تغییر |

## ۱۰) جمع‌بندیِ وضعیت‌ها

| موضوع | وضعیت |
|---|---|
| واحد/معنا/دقتِ قدرت خرید | `VERIFIED` (UI رسمی + بستهٔ Titan) |
| 12 ردیف: ورودی‌های current/settled/خرید/فروش امروز | `VERIFIED` با UI رسمی |
| فرمولِ sellable | `IMPLEMENTED_AND_TESTED` (12/12) |
| تعریفِ رسمی sellable | `BLOCKED` (ستون/فیلدِ رسمی وجود ندارد) |
| تازگی | `UNVERIFIED` (فقط زمانِ دریافت محلی) |
| 401/timeout/cache | `IMPLEMENTED_AND_TESTED` |
| قرارداد/parsing سفارش | `IMPLEMENTED_AND_TESTED` |
| read-backِ سفارش | `NOT_MEASURED` (سفارشی نیست) |
| readiness فقط‌خواندنی | `PARTIAL` (unit PASS؛ sellable/freshness باز) |
| اجرای زنده | خاموش؛ هیچ سفارش/درخواست تغییردهنده |

## ۱۱) محدودیت‌ها

- ستونِ «قابل‌فروش» در UI رسمی دیده نشد؛ فقط دارایی لحظه/دارایی سهام.
  بنابراین فرمولِ مشتقِ ما نباید `VERIFIED` شود.
- تازگیِ داده سمتِ کارگزاری قابل‌تشخیص نیست؛ `fetched_at` محلی است.
- read-back رویِ سفارشِ واقعی ممکن نبود (هیچ سفارشی وجود ندارد)؛ قرارداد و
  خطاها با fixture آزموده شد.
- 401/timeout واقعی تولید نشد تا نشستِ سالم تخریب نشود؛ آزمونِ کنترل‌شده کافی است.
- پنجرهٔ Edge/نشست باز ماند و ورود مجدد لازم نشد.
- مقدارهایِ حساسِ حساب در این گزارش ماسک شده‌اند؛ اسکرین‌شاتِ زنده commit نشد.

## ۱۲) commitها

- پایه: `a0f4f792`
- کامیتِ Round 18: `724047c9`
- تست‌هایِ هدفمندِ پس از تغییر: account 14/14 · adapter 39/39 ·
  session 25/25 · readiness 14/14 · UI 8/8 · live UI 5/5 · tsc 0 · build 0.
- suite کامل عمداً تکرار نشد؛ تغییر زیرساختی نبود و suite پیشینِ Round 17 سبز بود.
