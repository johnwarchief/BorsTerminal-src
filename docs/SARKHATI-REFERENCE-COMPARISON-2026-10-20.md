# مقایسهٔ مراجع GitHub با BorsTerminal — ۲۰۲۶-۱۰-۲۰ (Round 4)

روش: کلونِ سطحی در `%TEMP%` بیرون از مخزن، فقط خواندنِ کد/مستندات؛ هیچ کد اجرا
نشد، هیچ وابستگی نصب نشد، هیچ درخواستی به کارگزاری نرفت، و هیچ کد/فایلی از این
مراجع داخل BorsTerminal کپی نشد. مجوزها از فایلِ LICENSE هر مخزن بررسی شد.

| مرجع | HEAD | مجوز | مسیرهایِ کلیدی | الگوهایِ مفید | محدودیت/ادعای اثبات‌نشده | چه چیزی کپی نشد |
| --- | --- | --- | --- | --- | --- | --- |
| `Mahdi-mghs/AutoBuy-MofidBroker` | `05bfb179` | **MIT** | `order.py`, `locators.py`, `driver.py`, `broker.py`, `api_flow.py`, `token_store.py`, `smoke_test.py` | selectorهای fallback، بازکردن/تأیید فرم، بررسی فهرست سفارش، smoke بدونِ ارسال | `API_BUY_MAX_ATTEMPTS=20` هر کدام یک POST واقعی؛ توکنِ روی‌دیسک (`.mofid_token.json`)؛ پذیرشِ «بدونِ error» به‌عنوان موفقیت؛ rate-limit فقط سمتِ کلاینت | هیچ؛ الگوها بازنویسی شدند |
| `m-fazel/Sarkhati` | `c7c94879` | **فایل LICENSE ندارد** | `src/easy_trader.rs`, `src/mofid_online_plus.rs`, `src/rate_limiter.rs`, `src/time_reference.rs`, `src/calibration.rs` | جداکردنِ دو پروتکل، rate limiter، مرجعِ زمان، مدلِ config | مجوزِ استفاده نامشخص؛ rate-limit هر ترد/نمونه (بودجهٔ جهانی ندارد)؛ endpointها community-only | هیچ |
| `RezaMahdaviiDev/mofid` | `72a2e8c` | **فایل LICENSE ندارد** | `docs/api/easytrader-api-spec.md`, `docs/api/client-usage.md`, `docs/development/strategy.md`, `src/` | مدل‌های چندروشی، مستندِ API، اندازه‌گیریِ سرعت، MultiModelExecutor | مجوز نامشخص؛ شاملِ HAR و گزارش‌هایِ حساس (نباید بازنشر شود)؛ ادعای سرعت بدونِ بازتولیدِ ما | هیچ |
| `abolfazlrezaie260/Autobottrader` | `fe9e279` | **فایل LICENSE ندارد** | `trader.py`, `browser.py`, `scheduler.py`, `main.py`, `tests/` | `data-cy`های DOM، خواندنِ هدر/صف/خلاصهٔ سفارش، scheduler، تست‌های کوچک | مجوز نامشخص؛ `session_state.json` کوکی/localStorage را روی دیسک می‌نویسد؛ برخی selectorها در باندلِ فعلی EasyTrader وجود ندارند | هیچ |

## راستی‌آزماییِ مستقل selectorها

فقط رشته‌های `data-cy` از AutoBot به‌عنوانِ **فرضیه** گرفته و در باندلِ عمومیِ
خودِ EasyTrader (`main-*.js`) جستجو شدند:

| selector | در باندلِ فعلی EasyTrader |
| --- | --- |
| `order-buy-btn` / `order-sell-btn` | **هست** |
| `order-form-header-symbol-name` | **هست** |
| `order-list-clock` | **هست** |
| `best-buy-limit-price` | **هست** |
| `order-summary-asset` | **هست** |
| `symbol-header-symbol-name` | **نیست** |
| `order-form-max-price` / `order-form-min-price` | **نیست** |
| `easy-clock-id` | **نیست** |
| `market-depth-aggregates` / `symbol-detail-candle-max-price` | **نیست** |

از شواهدِ زندهٔ همین مأموریت هم تأیید شد: `#price`, `#quantity`, دکمهٔ
`button.order-buy-btn`, و `button[aria-label='ارسال خرید']`. بر این اساس
پیش‌فرض‌هایِ خرید در `execution_strategy_core.py` تنظیم شد؛ selectorهایِ
ناموجود استفاده نشدند.

## تطبیق با BorsTerminal

| الگو | وضعیتِ BorsTerminal | تصمیم |
| --- | --- | --- |
| بازخوانیِ نماد/قیمت/تعداد | `execution_strategy_engine.py` `_verify_form` + بازخوانیِ پیش از trigger | نگه‌داشته/تکمیل شد |
| هویت با ISIN | `execution_schedule.py` validator + `market.db` | تأیید محلی؛ live منبع لازم |
| selector پایدار | پیش‌فرض‌هایِ bundle/UI؛ fallback چندگانه ندارد | fallback در این دور اضافه نشد (خارج از حداقلِ لازم) |
| ساعت/زمان‌بند | `execution_timing.py` + `execution_schedule.py` | نگه‌داشته شد |
| فهرستِ سفارش/reconcile | `execution_easytrader.py` + `execution_service.py` | موجود؛ live نه |
| smoke بدونِ ارسال | `tools/browser_host_smoke.py` + dry-run strategy | **PASS** با صفحهٔ محلی |
| payload/response EasyTrader | `execution_easytrader.py` + باندل | قرارداد write همچنان `UNVERIFIED` |
| lifecycle نشست | `execution_browser_host.py` + CDP + ورود دستی | **پیاده و آزمون‌شده**؛ restart نیازِ ورود دستی |
| قطعی در برابر نامعلوم | `execution_contract` + canonical ResultState | موجود/تست‌شده |
| shutdown/restart/idempotency | `execution_schedule.py` + daemon | موجود/تست‌شده |

## نتیجهٔ تصمیم

- فقط الگوهایِ **معماری** استفاده شد؛ هیچ کد از سه مخزنِ بدونِ مجوز کپی نشد.
- الگویِ چند-POSTِ AutoBuy و ذخیرهٔ token/کوکیِ AutoBuy/AutoBot **رد** شد.
- selectorهای AutoBot فقط پس از راستی‌آزماییِ مستقل در باندل استفاده شدند؛
  selectorهایِ ناموجود کنار گذاشته شدند.
- برایِ اثبات زنده، همچنان به مجوزِ سفارش، نشستِ معتبر و دادهٔ همان روز نیاز است.
