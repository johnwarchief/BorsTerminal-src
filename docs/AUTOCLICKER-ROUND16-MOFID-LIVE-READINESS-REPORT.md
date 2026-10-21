# Round 16 — آمادگیِ زندهٔ Mofid و یکپارچگیِ کارگزاری

- تاریخ: 2026-10-21
- شاخه: `mission/sarkhati-round16-mofid-live-readiness-2026-10-21`
- پایه: `6ae3d779` (Round 15.5)
- دامنه: فقط مسیر مفید/Titan؛ EasyTrader دست‌نخورده؛ هیچ سفارش واقعی.

## ۱) خلاصهٔ اجرایی

مسیرهایِ فقط‌خواندنیِ Mofid از **بستهٔ منتشرشدهٔ خودِ کارگزاری** استخراج شد، نه از
حدس و نه فقط از کدِ شخصِ ثالث: `https://tg.mofidonline.com/` یک Next.js export است
و چانکِ `_next/static/chunks/3rfv56m3yme3b.js` (951,185 بایت) تعریفِ API client،
آدرسِ gateway، قاعدهٔ هدرِ `Authorization`، و نامِ enumهایِ وضعیتِ سفارش را دارد.
بر همین شاهد، آداپتورِ Mofid مسیرهایِ نشست، قدرت خرید، پرتفوی، سفارش‌هایِ باز/امروز،
و `state/detail` را پیاده می‌کند. ترافیک در همهٔ آزمون‌ها تزریقی است؛ **هیچ درخواستِ
واقعیِ حساب یا سفارش در این راند ساخته نشد**.

بررسیِ زنده **مسدود** است: در hostِ بازِ همین ماشین، صفحهٔ EasyTrader و
صفحهٔ **ورود** Mofid باز است (`login.emofid.com`)، ولی هیچ صفحهٔ واردشدهٔ
`tg.mofidonline.com` وجود ندارد. آن host در اختیارِ فرایندِ دیگری است و در این راند
کنترل/بازنشانی نشد. بنابراین: نشستِ واقعی، پاسخِ واقعی، واحدِ عددیِ واقعی، و
read-backِ واقعی **اندازه‌گیری نشده‌اند**؛ فقط قراردادِ کلاینتِ اول‌طرف و
پیاده‌سازیِ آن با ترافیکِ تزریقی تأیید شده است.

مسیرِ دادنِ دسترسیِ Mofid درون‌برنامه پیاده نشد؛ آداپتور فعلاً token/cookie را از
envِ فرایند می‌خواند و اگر نباشد، همهٔ خواندن‌ها با پیامِ روشن مسدود می‌مانند. این
یک گامِ جدا و تصمیمِ مالک است (پرسش ۸-۲).

`live_enabled=false` و `live_ready=false` باقی ماندند. `submit_order` هیچ تغییری
نکرد: حتی 2xx همچنان `UNKNOWN_RESULT` است و هیچ retry یا read-backِ ادعایی ندارد.

## ۲) وضعیتِ نهایی

| موضوع | وضعیت | شاهد / دلیل |
|---|---|---|
| مسیرها، متدها، هدرِ احراز، enumِ وضعیت | `VERIFIED_FROM_SOURCE` | چانکِ منتشرشدهٔ Titan، خوانده‌شده در 2026-10-21 |
| نشست/auth در آداپتور | `IMPLEMENTED_AND_TESTED` | `GET /Order/customer/status`؛ آزمون 200/401/403/5xx/غیرJSON |
| نشستِ زندهٔ واقعی | `BLOCKED` | فقط صفحهٔ ورود Mofid در host؛ نشستِ واردشده موجود نیست |
| قدرت خرید/مانده | `IMPLEMENTED_AND_TESTED` (با دادهٔ تزریقی) | `purchasingPower` و فیلدهایِ نام‌دارِ همان پاسخ |
| قدرت خریدِ واقعی و واحدِ عددی | `NOT_MEASURED` | هیچ پاسخِ حسابِ واقعی دیده نشد |
| قابل‌فروش | `IMPLEMENTED_AND_TESTED` + برچسبِ `CLIENT_DERIVED_UNVERIFIED` | کرانِ محافظه‌کارانه از `Portfolio/Daily` |
| قابل‌فروشِ واقعیِ کارگزار | `NOT_MEASURED` | فرمولِ اعلامیِ کارگزار دیده نشد |
| خواندنِ سفارشِ باز/امروز، order-id و state | `IMPLEMENTED_AND_TESTED` (تزریقی) | `open-orders`، `today-order`، `state/{id}`، `detail/{id}` |
| تاریخچهٔ کاملِ سفارش (`/Order/report`) | `IDENTIFIED_NOT_IMPLEMENTED` | پارامترهایِ پرس‌وجو در بسته دیده شد، ولی معنا/قالبشان تأیید نشد |
| پاسخِ واقعیِ سفارش/read-back | `NOT_MEASURED` | نیاز به نشستِ واقعی؛ سفارشی ارسال نشد |
| preflight بر پایهٔ دادهٔ حساب | `IMPLEMENTED_AND_TESTED` | خرید با `purchasingPower`، فروش با sellableِ برچسب‌دار |
| readiness مبتنی بر شاهد | `IMPLEMENTED` | `readiness_evidence` در status؛ `live_ready=false` |
| UI مسیر API مفید | `IMPLEMENTED_AND_TESTED` | پنلِ حساب در `/autoclicker`؛ 7 آزمونِ فرانت |
| عدمِ ارسالِ سفارشِ واقعی | `VERIFIED_BY_CONSTRUCTION` | POSTهایِ آزمون فقط به ترابریِ تزریقی؛ `live_enabled=false` |
| گیتِ کاملِ پروژه | `PASS` | اجرایِ نهایی: 145 counted / 31 silent / 2 skipped / 0 FAIL؛ `operational_changed=none` |

## ۳) شاهدِ اول‌طرف

### ۳-۱) منبع و روش

| مورد | مقدار |
|---|---|
| صفحهٔ عمومی | `https://tg.mofidonline.com/` — HTTP 200، 3,703 بایت، `nextExport: true` |
| Build ID | `68NT3Xp-L3HkT3OJYvmrD` |
| چانکِ اصلی | `/_next/static/chunks/3rfv56m3yme3b.js` — 951,185 بایت |
| پایهٔ gateway | `https://mofidonline.com/apigateway/api/v1` |
| پایهٔ نسخهٔ دوم | `https://mofidonline.com/apigateway/api/v2` |
| پایهٔ وب V4 | `https://api.mofidonline.com/Web/V4` |
| روش | فقط GETِ عمومی روی فایل‌هایِ استاتیک؛ بدونِ کوکی/توکن/بدنه؛ بدونِ وابستگی به نشست |

این شاهد «کدِ اول‌طرفِ منتشرشده» است، نه سندِ رسمی و نه پاسخِ زنده. هرچه در
جدول‌هایِ زیر می‌آید، عیناً از همان بسته استخراج شده است؛ چیزهایی که در بسته نبودند
نیز صریحاً «پیاده‌نشده» یا `UNKNOWN` مانده‌اند.

### ۳-۲) مسیرهایِ استخراج‌شده

| مسیر | متد | پایه | کاربرد | وضعیت در آداپتور |
|---|---|---|---|---|
| `/Order/customer/status` | GET | gateway v1 | نشست + `purchasingPower`/`blockedBalance`/`credit` | پیاده |
| `/Portfolio/Daily` | GET | gateway v1 | دارایی، خرید/فروش امروز، سفارشِ باز | پیاده |
| `/Order/open-orders` | GET | gateway v1 | سفارش‌هایِ باز | پیاده |
| `/Order/today-order` | GET | gateway v1 | سفارش‌هایِ امروز | پیاده |
| `/Order/state/{orderId}` | GET | gateway v1 | وضعیتِ یک سفارش | پیاده |
| `/Order/detail/{orderId}` | GET | gateway v1 | جزئیاتِ یک سفارش | پیاده |
| `/Order/report` | GET | gateway v1 | تاریخچهٔ سفارش | شناسایی‌شده، پیاده‌نشده |
| `/Accounting/Remain` | GET | web V4 | مانده/قدرت خرید | شناسایی‌شده، پیاده‌نشده |
| `/Order/send` | POST | gateway v1 | ثبتِ سفارش | بدونِ تغییر؛ 2xx = `UNKNOWN_RESULT` |

`/Accounting/Remain` هم همان فیلدهایِ `purchasingPower` و `accountBalanceT1/T2` را
می‌دهد؛ عمداً پیاده نشد تا دو منبعِ موازی برایِ یک عدد ساخته نشود. اگر پاسخِ
`customer/status` در نشستِ واقعی فیلدِ لازم را نداشت، این مسیر جایگزینِ بعدی است.

### ۳-۳) احراز هویت

| مورد | شاهد در بستهٔ Titan |
|---|---|
| محلِ token | `localStorage.getItem("token")` |
| هدر | `Authorization: Bearer <token>` اگر طول > 36، وگرنه `Basic <token>` |
| هدرِ ثابت | `x-appname: titan` |
| timeout کلاینت | 10 ثانیه |
| رفتارِ 401 | حذفِ token و هدایت به ورود |
| کوکی | مسیرِ مرجعِ شخصِ ثالث از Cookie هم پشتیبانی می‌کند؛ مسیرِ اول‌طرف token است |

آداپتور همین قاعدهٔ Bearer/Basic را در `authorization_value` پیاده می‌کند و
`x-appname` را رویِ همهٔ درخواست‌ها می‌فرستد. توکن فقط در حافظه است و در
`repr`، لاگ یا پاسخِ HTTP نمی‌آید.

### ۳-۴) نگاشتِ وضعیتِ سفارش

| نامِ Titan | `OrderState` خودی |
|---|---|
| `Open`, `SentToNsc` | `OPEN` |
| `InOmsQueue`, `OnBoard`, `OnSending`, `Modify`, `OnModifying`, `OnModified`, `OnModifyBoard` | `PENDING` |
| `PartiallyExecution`, `PartiallyExecutedAndModified`, `PartiallyExecutedAndExpired`, `PartiallyExecutedAndError`, `PartiallyExecutedAndCanceled` | `PARTIAL` |
| `OrderExecuted`, `Done` | `FILLED` |
| `Cancel`, `CancelByBroker`, `CancelBySurveillance`, `DeleteByNsc`, `DeleteBySupervisor`, `DeleteByBroker`, `Expired` | `CANCELLED` |
| `Reject`, `Error` | `REJECTED` |
| هر نامِ دیگر (از جمله `OnCanceling`, `OnCancelError`, `OnModifyError`, `None`) | `UNKNOWN` |

نام‌هایِ ناشناخته عمداً `UNKNOWN` می‌مانند؛ «شاید پر شده» یا «شاید لغو شده» حدس نیست.
اگر `orderState` نیامده باشد ولی `executedQuantity` و `quantity` آمده باشند، فقط
حالتِ عددیِ `FILLED`/`PARTIAL` قابلِ استنتاج است.

### ۳-۵) فیلدهایِ حساب و پرتفوی

| منبع | فیلدهایی که آداپتور می‌خواند |
|---|---|
| `customer/status` | `purchasingPower`, `accountBalanceT2`, `accountBalanceT1`, `blockedBalance`, `credit`, `marginBlock` |
| `Portfolio/Daily` | `symbolIsin`, `symbolName`, `currentAsset`, `todayBoughtAsset`, `todaySoldAsset`, `openBuyOrders`, `openSellOrders`, `averageBuyPrice`, `averageSellPrice`, `breakEvenPrice`, `todayBuyAveragePrice`, `todaySellAveragePrice` |
| `open-orders` / `today-order` | `orderId`, `symbol`, `symbolIsin`, `orderPrice`, `quantity`, `executedQuantity`, `orderSide`, `validityType`, `validityDateTime`, `orderState`, `orderFrom`, `orderFromName`, `errorCodeId` |
| `state/{id}` / `detail/{id}` | همان شکل، با `orderState`/`state` و مقادیرِ اجرا |

`orderSide` در این مسیرها رشتهٔ `Buy`/`Sell` است، نه عددِ 65/86 (آن دو برایِ
`SymbolForPortfolioCardex` بودند). آداپتور هر دو حالتِ رشته‌ای را می‌فهمد و هر چیزِ
دیگر را با یادداشتِ «تأییدنشده» به `BUY` نمایشی نگاشت می‌کند.

فرمولِ `sellable` برایِ سهامِ نقدی است. موقعیت‌هایِ اختیار در
`/Order/positions/open` جدا هستند و در این راند پیاده نشدند؛ برایِ آن‌ها
`UNKNOWN` می‌مانیم، نه صفر.

### ۳-۶) واحد و زمان

- **واحد:** `IRR` (ریال). شاهد: کاتالوگِ خطاهایِ خودِ Titan حداقلِ ارزشِ سفارش را
  «یک میلیون ریال» و «50 میلیون ریال» می‌گوید و قیمت/حجمِ سفارش در همان واحدند.
  این یک استنتاج از متنِ خودِ کلاینت است، نه اندازه‌گیریِ عددیِ پاسخ؛ در پاسخِ
  واقعی باید دوباره تأیید شود.
- **زمان:** `orderDateTime`، `validityDateTime` و `tradeDateTime` **خام** در
  `events` رکورد می‌مانند. منطقهٔ زمانی و قالبِ عددیِ پاسخِ واقعی دیده نشده، پس
  هیچ تبدیلِ تهران/UTC رویِ آن‌ها انجام نمی‌شود. `fetched_at` فقط زمانِ خواندنِ
  همین ماشین است.

## ۴) پیاده‌سازی

### ۴-۱) آداپتور — `execution_mofid.py`

- `authorization_value`: قاعدهٔ Bearer/Basic خودِ Titan.
- `map_order_state`: نگاشتِ جدولِ ۳-۴.
- `authenticate`: `GET /Order/customer/status`؛ 200 با شیءِ JSON ⇒ `CONNECTED` و
  `session_proven`؛ 401 ⇒ `EXPIRED`؛ 403 ⇒ `AUTH_FAILED`؛ 5xx/غیرJSON ⇒ `ERROR` و
  هیچ ادعایِ اتصال.
- `get_money` / `get_balances`: فقط از `purchasingPower` و فیلدهایِ نام‌دار؛ نبودِ
  `purchasingPower` ⇒ `UNKNOWN_RESULT`، نه صفر.
- `get_positions`: نگاشتِ `Portfolio/Daily`؛ `settled` از فرمولِ خودِ کلاینت
  (`currentAsset + todaySoldAsset - todayBoughtAsset`) و `sellable` از
  `max(0, min(currentAsset, settled) - openSellOrders)`.
- `sellable_provenance`: برچسبِ `CLIENT_DERIVED_UNVERIFIED` و فرمولِ کامل.
- `get_sellable_quantity`: صفر فقط وقتی فهرستِ پرتفوی دیده شد و ردیف نبود؛ ردیفِ
  ناقص ⇒ `UNKNOWN_RESULT`.
- `get_orders` / `get_today_orders` / `get_order`: `open-orders`، `today-order`،
  `detail/{id}` و `state/{id}`؛ 404 یعنی «دیده شد و نبود»، 5xx یعنی «نامعلوم».
- `submit_order`: بدونِ تغییر؛ 2xx ⇒ `UNKNOWN_RESULT`؛ 4xx ⇒ `FAILED`؛ 5xx/timeout
  ⇒ `UNKNOWN_RESULT`؛ بدونِ retry.
- `readiness_evidence`: قرارداد، مسیرهایِ خوانده‌شده، وضعیتِ نوشتن، فرمولِ sellable،
  واحد، و `live_verified: false`.

### ۴-۲) API — `api/execution.py`

- `READ_ONLY_REQUESTED` حالا `mofid` را هم می‌پذیرد؛ ترافیکِ خواندن با
  `adapter=mofid` و `read_only=true` باز می‌شود، ولی `LIVE_REQUESTED` همچنان فقط
  با `BORS_EXECUTION_LIVE=1` است.
- `_source_block`: برایِ Mofid، اگر نشست تأیید نشده باشد، همان‌جا یک GETِ
  فقط‌خواندنی به `customer/status` می‌زند و نشست را تأیید می‌کند؛ هیچ سفارشی
  برایِ ping ساخته نمی‌شود.
- `_mofid_portfolio`: پاسخِ `/api/execution/portfolio` برایِ Mofid با
  `state=PORTFOLIO_READ_ONLY_UNVERIFIED`، `sellable_state`، فرمول، و `buying_power`
  از همان منبع.
- `/api/execution/buying-power`: با `get_money` آداپتورِ Mofid کار می‌کند؛
  `session_proven` پس از تأیید به‌روزرسانی می‌شود.
- `/api/execution/status`: پیامِ blockade برایِ Mofid سه حالتِ جدا دارد
  (ترافیکِ خاموش، نبودِ token، نشستِ تأییدنشده) و در حالتِ تأییدشده صریح می‌گوید
  «خواندن مجاز، نوشتن/read-back تأییدنشده». `wire_provenance` برایِ Mofid از
  `readiness_evidence` می‌آید.

### ۴-۳) Preflight — `execution_service.py`

- خرید: `buying_power` از `get_balances`؛ متنِ دلیل شاملِ `unit` و `source` است.
- فروش: `get_sellable_quantity`؛ متنِ دلیل حالا منشأ را هم می‌آورد
  (`source=CLIENT_DERIVED_UNVERIFIED`). مقدارِ نبود ⇒ `UNKNOWN` و مسدود.

### ۴-۴) تنظیمِ اتصال — `execution_settings.py`

- `mofid` دیگر به `easytrader` alias نمی‌شود؛ آداپتورِ مستقل است.
- `traffic_allowed` برایِ Mofid در حالتِ `read_only` روشن می‌شود؛
  `writes_allowed` همچنان فقط با `BORS_EXECUTION_LIVE=1`.

### ۴-۵) رابط — `/autoclicker`

- در مسیر API و آداپتورِ `mofid`، پنلِ «حساب مفید (فقط‌خواندنی)» نمایش داده
  می‌شود: قدرت خرید، وضعیتِ پرتفوی، `sellable_state`، ردیفِ نمادِ انتخاب‌شده
  (دارایی/برآوردِ قابل‌فروش/سفارشِ بازِ فروش)، و یک دکمهٔ خواندنِ دوباره.
- `SarkhatiConnectionSettings` گزینهٔ «مفید آنلاین (Titan)» را دارد.
- برچسبِ صریح: «قابل‌فروش» برآوردِ محافظه‌کارانه است، نه عددِ اعلامیِ کارگزار.

## ۵) آزمون‌ها

| آزمون | نتیجه | چه چیزی را ثابت می‌کند |
|---|---|---|
| `dev/mofid_adapter_v1163.py` | 37/37 | payload تخت، 2xx=UNKNOWN، بدونِ retry، redaction، نشست/401/403/5xx/غیرJSON، باطل‌شدنِ شاهد و کش پس از 401، money/positions/sellable، نگاشتِ state، preflight خرید/فروش |
| `dev/mofid_readiness_v1164.py` | 14/14 | API و readiness با ترافیکِ تزریقی؛ reading باز، writing بسته؛ صفر POSTِ واقعی؛ 401/offline بی‌مقدار؛ ثبت در هر دو spec |
| `dev/broker_connect_v1120.py` | 38/38 | تنظیمِ اتصال و سه گیتِ جدا؛ `mofid` دیگر alias نیست |
| `dev/readiness_round15_v1162.py` | 7/7 | گیت‌هایِ readiness و `live_ready=false` بی‌مجوزِ مالک |
| `dev/db_isolation_guard_v1160.py` | 6/6 | ایزولاسیونِ دیتابیسِ آزمون |
| `autoclicker-page.spec.tsx` | 7/7 | مسیر API، dry-run، intent مشترک، scheduled، پنلِ حساب Mofid |
| `npx tsc -b` | 0 خطا | تایپ‌چکِ فرانت |
| `npm run build` | exit 0 | بیلدِ Vite |
| `dev/autoclicker_browser_round14_v1149.py` | 15/15 (سه اجرایِ مستقل) | پس از یک قرمزِ `0 pass / 1 fail` در suite، سه بار پیاپی سبز شد |
| `dev/run_all_tests.py` (اسنپ‌شات) | `PASS` | 145 counted / 31 silent / 2 skipped / 0 FAIL؛ `operational_changed=none` |
| `dev/run_all_tests.py` (نهایی، اجرای 1) | **1 قرمز** | همهٔ گاردها سبز جز browser-level (`0 pass / 1 fail`) |
| `dev/run_all_tests.py` (نهایی، اجرای 2) | `PASS` | 145 counted / 31 silent / 2 skipped / 0 FAIL؛ `ALL SUITES PASSED`؛ `operational_changed=none` |

قرمزِ browser-level در اجرایِ اول با بارِ هم‌زمانِ tsc/vitest/build دیده شد و در سه
اجرایِ مستقلِ بعدی (۱۵/۱۵ هر بار) و اجرایِ دومِ کاملِ suite رویِ ماشینِ بی‌بار تکرار
نشد. این را «نوسانِ محیطی، رگرسیونِ اثبات‌شده نیست» ثبت می‌کنیم، نه «همیشه سبز».

اجرایِ کامل: `PYTHONIOENCODING=utf-8 python dev/run_all_tests.py` (cloneِ خودایزوله)؛
خروجیِ نهایی در `_audit/round16_run_all_final2.txt` (و اجرایِ قرمزِ اول در
`_audit/round16_run_all_final.txt`). هشِ دیتابیس‌هایِ عملیاتی پیش و پس از اجرا یکسان
ماند: `market.db=fd688edb...` و `user.db=fbffd6ef...`.

## ۶) آنچه هنوز باید با نشستِ واقعی سنجیده شود

1. مالک در یک hostِ کنترل‌شده (نه hostِ فعلیِ EasyTrader) وارد
   `tg.mofidonline.com` شود؛ دسترسی در envِ فرایندِ خودِ برنامه قرار گیرد،
   آداپتور روی `mofid` و `read_only=true` تنظیم شود و برنامه یک‌بار restart شود.
2. `GET /Order/customer/status` واقعی خوانده شود: وجودِ `purchasingPower`،
   عددی‌بودن، واحد، و رفتارِ 401/403.
3. `GET /Portfolio/Daily` واقعی خوانده شود: `currentAsset`، `todayBoughtAsset`،
   `todaySoldAsset`، `openSellOrders` و مقایسهٔ کرانِ ما با «حداکثر قابلِ فروش»
   خودِ کارگزار (اگر نمایش می‌دهد).
4. `open-orders`، `today-order`، `state/{id}` و `detail/{id}` واقعی خوانده شوند:
   رشته‌هایِ `orderState`، قالب/منطقهٔ زمانیِ `orderDateTime`، و رفتارِ 404.
5. فقط پس از تأییدِ مواردِ بالا و با مجوزِ صریحِ مالک، یک آزمونِ نوشتنِ کنترل‌شده
   طراحی شود. در این راند هیچ سفارشِ واقعی طراحی/ارسال نشد.

## ۷) پاسخ به دستور کار

| خواسته | نتیجه |
|---|---|
| اعتبارسنجیِ نشست/auth واقعی | پیاده و با ترافیکِ تزریقی آزموده؛ زنده `BLOCKED` |
| balances/قدرت خرید | پیاده از `purchasingPower`؛ زنده `NOT_MEASURED` |
| قابل‌فروش | پیاده به‌صورتِ کرانِ محافظه‌کارانهٔ برچسب‌دار؛ زنده `NOT_MEASURED` |
| schema/واحد/زمانِ پاسخ | منبع `VERIFIED_FROM_SOURCE`؛ پاسخِ واقعی `NOT_MEASURED` |
| خواندنِ سفارش/order-id/state | پیاده (`open-orders`/`today-order`/`state`/`detail`)؛ زنده `NOT_MEASURED` |
| تاریخچهٔ کاملِ سفارش | `/Order/report` شناسایی شد، ولی پارامترهایِ پرس‌وجو تأیید نشدند؛ پیاده نشد |
| preflight بر پایهٔ دادهٔ واقعی | پیاده و آزموده با دادهٔ تزریقی |
| قراردادِ پاسخ/reconciliation | 2xx=UNKNOWN، نگاشتِ state، `get_order`؛ زنده `NOT_MEASURED` |
| readiness مبتنی بر شاهد | پیاده؛ `live_ready=false` |
| استفادهٔ UI | پنلِ حساب Mofid و انتخابِ آداپتور؛ آزموده |
| عدمِ سفارشِ واقعی و `live_enabled=false` | حفظ شد |

## ۸) پرسش‌هایِ غیرفوری

1. آیا کرانِ محافظه‌کارانهٔ `min(currentAsset, settled) - openSellOrders` برایِ
   preflightِ فروش موردِ قبول است، یا کارگزار عددِ «قابل‌فروش» دیگری اعلام می‌کند؟
2. مسیرِ tokenِ Mofid در نسخهٔ بعدی: همان envِ فرایند بماند، یا مثلِ EasyTrader
   یک captureِ درون‌برنامه‌ای (فقط در حافظه) اضافه شود؟
3. آیا واحدِ `purchasingPower` در پاسخِ واقعی هم ریال است؟ شاهدِ فعلی متنِ
   کاتالوگِ خطا و فیلدهایِ قیمت است، نه یک عددِ مشاهده‌شده.

## ۹) تغییرات

| فایل | تغییر |
|---|---|
| `execution_mofid.py` | مسیرهایِ فقط‌خواندنی، session proof، money/positions/sellable، orders/state/detail، شاهد |
| `api/execution.py` | READ_ONLY برایِ mofid، `_source_block`، `_mofid_portfolio`، status/provenance |
| `execution_service.py` | منشأِ sellable در دلیلِ preflight |
| `execution_settings.py` | آداپتورِ مستقلِ mofid و traffic خواندن |
| `execution_readiness.py` | متنِ اقدامِ عمومی (بی‌اشاره به مسیرِ EasyTrader) |
| `frontend/.../AutoClickerPage.tsx` | پنلِ حساب Mofid و chipِ آمادگی |
| `frontend/.../SarkhatiConnectionSettings.tsx` | گزینهٔ «مفید آنلاین (Titan)» |
| `frontend/src/__tests__/autoclicker-page.spec.tsx` | آزمونِ پنلِ حساب Mofid |
| `dev/mofid_adapter_v1163.py` | 25 آزمونِ تازه (37 در کل) |
| `dev/mofid_readiness_v1164.py` | گاردِ تازهٔ API/readiness |
| `dev/broker_connect_v1120.py` | `mofid` دیگر alias نیست |
| `dev/run_all_tests.py` | ثبتِ گاردِ تازه + `encoding=utf-8` برایِ gitِ ایزوله |
| `bors_setup.spec` | حضورِ `execution_mofid` درِ بستۀ نصاب (هم‌ردهٔ `fts_terminal.spec`) |

SHA کامیت و نتیجهٔ suite پس از پایانِ اجرا در همین فایل به‌روزرسانی می‌شود.
