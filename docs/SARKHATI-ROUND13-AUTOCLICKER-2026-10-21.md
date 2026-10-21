# Sarkhati Round 13 — صفحهٔ تنظیمات و آمادگیِ AutoClicker

**تاریخ:** ۲۰۲۶-۱۰-۲۱  
**شاخه:** `mission/sarkhati-round13-autoclicker-2026-10-21`  
**مبنا:** `5bff573218444cd17b7ac42ae1d8429eabf756a0`

## ۱) تصمیمِ مالک

مالک خواست AutoClicker از یک **صفحهٔ مستقل** تنظیم شود و قیمت/تعداد در فرمِ
خودِ کارگزاری وارد شود؛ AutoClicker فقط دکمه و محدودیت‌ها را بشناسد و در زمان
هدف عمل کند. این پیاده‌سازی دقیقاً رویِ همان قید ساخته شد:

- no autofill: صفحه فرمِ EasyTrader را پر نمی‌کند.
- فرم باید ازپیش‌پر باشد و AutoClicker فقط دکمهٔ ارسالِ همان فرم را می‌زند.
- یک کلیک در هر قصد؛ هیچ حلقه/retry/کلیکِ تکراری وجود ندارد.
- `preclick_check` اختیاری، وجود و فعال‌بودن دکمه را پیش از کلیک بررسی می‌کند.
- Live از این صفحه در دسترس نیست؛ dry-run با intercept و abort پیش از dispatch.

## ۲) چه چیزی از قبل بود

- `execution_strategy_engine.AutoClickerStrategy` با `autofill_default=False` و
  `require_prefilled_default=True`، selectorهای فرم، `_verify_form` برای
  تطبیقِ نماد/قیمت/تعداد، یک کلیک و `intercept` در dry-run.
- `StrategySettingsStore` غیرمحرمانه روی `user.db`، مسیرهای `prepare/trigger/abort/probe`.
- گارد `dev/strategy_guard_v1123.py`: ۵۷/۵۷.

هیچ موتورِ کلیکِ دومی ساخته نشد.

## ۳) چه چیزی تازه شد

| تغییر | مسیر |
| --- | --- |
| صفحهٔ مستقل `/autoclicker` | `frontend/src/features/portfolio/routes/AutoClickerPage.tsx` |
| لینکِ ناوبری در گروهِ سرمایه و دارایی | `frontend/src/app/components/Sidebar.tsx` |
| عنوانِ مسیر | `frontend/src/app/components/Topbar.tsx` |
| لینک از کارتِ آمادگیِ سرخطی | `SarkhatiReadinessCard.tsx` |
| آزمونِ صفحه | `frontend/src/__tests__/autoclicker-page.spec.tsx` |

صفحه شاملِ:

- **آمادگی:** host، نشست، Strategy، شناسه‌های فرم، پیش‌فرضِ prefill، زمان هدف،
  وضعیت Live.
- **تنظیمات:** `form_symbol_selector`، `open_form_selector`، `price_selector`،
  `quantity_selector`، `submit_selector`، `action_timeout_ms`،
  `intercept_pattern` و `preclick_check`.
- **سفارشِ ازپیش‌پر:** نماد/ISIN/سمت/قیمت/تعداد/زمان هدف را فقط برایِ
  **تأییدِ انتظار** می‌گیرد؛ آن‌ها را به فرمِ کارگزاری تزریق نمی‌کند.
- **Probe فقط‌خواندنی:** صفحه را باز می‌کند و login/selector/structure را
  برمی‌گرداند؛ مقدارِ inputها را برنمی‌گرداند.
- **آماده‌سازی:** `strategyPrepare`؛ هیچ trigger/dispatch خودکار.
- **dry-run:** فقط پس از `prepared_id` و یک checkbox صریح؛ در موتور با
  `intercept` و `abort` پیش از dispatch؛ هیچ شناسه/پذیرشی ادعا نمی‌شود.
- **توقف:** abort آماده‌سازی؛ هیچ سفارشی لغو نمی‌شود.

## ۴) امنیت

- Live/`strategyDispatch` از صفحه صدا زده نمی‌شود؛ `live_allowed` باید false باشد.
- هیچ token/Cookie/رمز در تنظیماتِ این صفحه نیست؛ جدولِ تنظیمات نیز کلیدهای
  حساس را رد می‌کند.
- قیمت/تعداد از فرمِ خودِ کارگزاری می‌آید و صفحه فقط انتظارِ خود را با
  `_verify_form` تطبیق می‌دهد.
- تک‌کلیک و بی‌retry: «محدودیت بین کلیک‌ها» با حذفِ کلیکِ تکراری حل شد، نه
  با ساختنِ یک عددِ فاصلهٔ بی‌شاهد.
- dry-run فقط با تأیید صریح و intercept؛ اگر intercept برقرار نشود موتور
  `INTERCEPT_FAILED` می‌دهد و کلیک نمی‌کند.

## ۵) وضعیتِ سیمکات و شنبه

سیمکات از نشستِ مجاز به‌عنوان یک عرضهٔ عمومی دیده شد، ولی:

- `IRO3SIMC0001` در `market.db` محلی نیست؛ مسیرِ `strategyPrepare` با
  `NOT_ORDERABLE` متوقف می‌شود.
- پنجرهٔ عرضه ۲۰۲۶-۱۰-۲۱ ۱۲:۱۵–۱۴:۱۵ بود؛ آزمون خارج از آن انجام شد.
- هیچ بودجه/قیمت/تعداد/مجوزِ سفارشِ صریح برای این نماد تعیین نشده است.

بنابراین صفحه برای **آماده‌سازی و آزمونِ امن** آماده است، ولی برای ثبتِ سفارشِ
واقعیِ سیمکات در شنبه نیاز به mapping محلی، تنظیمِ صریح و مجوزِ جداگانه دارد.
هیچ سفارش واقعی در این راند ارسال نشد.

## ۶) آزمون‌ها

| آزمون | نتیجه |
| --- | --- |
| `autoclicker-page.spec.tsx` | ۲/۲ |
| `sarkhati-guided-flow` + `sarkhati-tab` + `sarkhati-readiness` | ۳۸/۳۸ |
| `dev/strategy_guard_v1123.py` | ۵۷/۵۷ |
| `npx tsc -b` | صفر خطا |
| `npm run build` | موفق |
| Frontend کامل | ۲۰۲ فایل، ۲۰۹۳ passed، ۵ skipped، ۰ failed |
| گیتِ کاملِ ایزولهٔ Round 11A | ۱۴۳ counted، ۲۷ exit-code-only، ۲ SKIP، ۰ FAIL |
| fingerprintِ عملیاتی | قبل/بعد یکسان: `5a9117aa…135bea3` / `381736f1…c74500e` |

## ۷) نتیجه

صفحهٔ مستقلِ تنظیمات/آمادگیِ AutoClicker آماده است و روی همان استراتژیِ
موجود کار می‌کند. `live_enabled=false` و `live_ready=false` باقی می‌مانند؛
هیچ ارسال، شناسه، پذیرش یا صفی ادعا نمی‌شود. موانعِ باقی‌مانده: mapping محلی
سیمکات، مجوز/مقادیر صریحِ سفارش، و تأییدِ عملیاتیِ قرارداد نوشتن.
