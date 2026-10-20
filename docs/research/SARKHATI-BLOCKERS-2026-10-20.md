# Blocker Burn-down سرخطی — ۲۰۲۶-۱۰-۲۰

شاخه: `mission/multi-strategy-2026-10-20`
مبنا: `0d593921` + `d5f517bc` + تغییر جاری
هدف: تفکیک «کدِ حل‌شده»، «آزمون‌شده» و «مسدودِ بیرونی»؛ بدون ادعای Live.

## جدول Blocker

| Blocker | اقدام انجام‌شده | مدرک | وضعیت | اقدام بعدی |
| --- | --- | --- | --- | --- |
| قرارداد واقعی POST سفارش | Adapter، payload و مفسر پاسخ موجود؛ هیچ POST واقعی | `WIRE_HYPOTHESIS=True`؛ smoke فقط Mock؛ هیچ پاسخ کارگزاری دیده نشد | **BLOCKED_EXTERNALLY** (`PENDING_ORDER_APPROVAL`) | مقادیر نهایی + تأیید صریح مالک + یک تست زندهٔ تحت نظارت |
| احراز هویت پایدار | lifecycle و sessionStorage مستند؛ هیچ token/HAR/جعل | نشست با بستن تب از بین رفت؛ daemon به پنجرهٔ زنده دسترسی ندارد؛ `readiness` صریح | **BLOCKED_EXTERNALLY** (`AUTH_REQUIRED`) | ورود دستی مالک در یک host پایدار یا provider مجاز؛ بدون دورزدن auth |
| دادهٔ روز جاری (قیمت/گام/دامنه) | validator شکست‌بسته؛ `LocalFactsProvider` فقط هویت | تقویم/دامنه/گام live در محصول UNKNOWN؛ `price_history` محلی کافی نیست | **BLOCKED_EXTERNALLY** (`MARKET_DATA_UNVERIFIED`) | منبع read-only همان روز از کارگزاری/UI با تاریخ و تازگی |
| قدرت خرید/موجودی | `balances=False` در capabilities؛ هیچ عددی ساخته نمی‌شود | `execution_easytrader.py`؛ preflight UNKNOWN | **BLOCKED_EXTERNALLY** | endpoint read-only معتبر یا خواندن کنترل‌شده از UI با ثبت sufficiency نه مقدار |
| هویت/هدر فرم | هویت محلی + بازکردن مجدد فرم + بازخوانی پیش از ارسال | `strategy_guard` 55/55؛ هدر فرم AutomationId پایدار ندارد | **PARTIAL** | selector پایدار هدر از DOM زنده + پیکربندی در Strategy |
| تقویم آینده | تقویم محلی از `price_history`؛ closed → SKIPPED | `execution_schedule_v1130` 55/55 | **PARTIAL** | منبع تقویم/TradingTime همان روز |
| restart و اجرای دوباره | ذخیرهٔ ماندگار؛ active → `NEEDS_REVIEW`؛ executor صدا زده نمی‌شود | تست restart/recover/claim | **RESOLVED** (رفتار ایمن) | در صورت نیاز، بازبینی دستی و re-arm |
| UNKNOWN/تکرار | UNKNOWN ترمینال؛ dedupe دقیقه‌ای؛ claim اتمیک | تست دو claim و UNKNOWN | **RESOLVED در Mock** (live اثبات نشده) | تست زنده فقط با مجوز |
| قطع اتصال/429 | 401/200-HTML/timeout/5xx پوشش دارد؛ 429 fixture موجود؛ نگاشتِ قطع اتصال مستقل ندارد | adapter/service/protocol guards | **PARTIAL** | تست NETWORK_ERROR→UNKNOWN پس از POST |
| Release | build Frozen 230.3MB و contract PASS | `d5f517bc` و smoke | **BLOCKED_PENDING_OWNER/CI** | bump شش anchor، notes، PR/CI، tag؛ بدون push به main |
| UI کامل | صفحهٔ سرخطی + کارت زمان‌بندی + preflight + نتیجه | Vitest/tsc؛ بصری زنده پس از تغییر آخر انجام نشده | **PARTIAL** | checklist عملیاتی و بازبینی بصری مالک |

## چک‌لیست عملیاتی فردا (Asia/Tehran)

| مورد | نحوهٔ بررسی | وضعیت امروز |
| --- | --- | --- |
| روشن‌بودن سیستم | قبل از 08:30 | باید توسط مالک انجام شود |
| daemon/سرویس | `--schedule-daemon --once` یا اجرای مستمر | dry-run تست شد؛ live executor وصل نیست |
| مرورگر/نشست | ورود دستی در پنجرهٔ host | پنجرهٔ زنده باز است؛ daemon به آن دسترسی ندارد |
| Preflight تازه | `/api/execution/schedules/readiness` + Probe | live_ready=false |
| نماد داروند | لینک «داروند TAL زیست اروند فارمد» + ISIN `IRO1DRVN0001` | هویت محلی تأیید شد؛ selector هدر UNVERIFIED |
| قیمت مجاز/تعداد | فرم زندهٔ همان لحظه | snapshot قبلی مبنای فردا نیست |
| بودجه | منبع معتبر | UNKNOWN |
| Live/Dry | `readiness` و وضعیت schedule | فقط dry-run مجاز |
| آخرین بررسی/نتیجه | events و result_state | ثبت در SQLite |

## شواهد تست

| اجرا | نتیجه |
| --- | --- |
| `dev/execution_schedule_v1130.py` | **55/55** |
| `dev/strategy_guard_v1123.py` | **55/55** |
| `dev/run_all_tests.py` | **167 suite** (138 شمارش‌دار + 27 silent + 2 skip)؛ **4977/4977** check؛ exit 0 |
| Vitest | 197/199 فایل؛ 2065/2070 تست؛ 5 skip؛ exit 0 |
| `tsc -b` | صفر خطا |
| Frozen | 230.3MB؛ build exit 0؛ contract PASS؛ smoke DRY_RUN؛ daemon exit 0 |

`SKIPPED` برای تقویم بسته اضافه شد؛ validator برای دامنه/گام/دادهٔ کهنه/بودجه/
نشست تست شد. هیچ سفارش واقعی در هیچ‌کدام ارسال نشد.

## نتیجهٔ صادقانه

Live **آماده نیست** و هیچ سفارشی ارسال نشد. کدِ قابل‌حل (ذخیره، restart، SKIPPED،
بازخوانی پیش از ارسال، preflight موازی، وضعیت canonical) حل/تست شده است؛
قرارداد واقعی، نشست پایدار، دادهٔ روز، قدرت خرید و انتشار به تأیید مالک/سرویس
بیرونی وابسته‌اند. هیچ موفقیت یا اول‌شدن در صف تضمین نمی‌شود.
