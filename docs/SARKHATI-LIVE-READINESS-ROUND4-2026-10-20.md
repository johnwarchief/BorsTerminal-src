# آمادگی Live — Round 4 (۲۰۲۶-۱۰-۲۰)

شاخه: `mission/multi-strategy-2026-10-20`
مبنا: `cc07d154` + تغییراتِ این دور
هدف: بستنِ موانعِ کدمحور و تعیینِ صادقانهٔ Gateها؛ **هیچ سفارش واقعی و هیچ
انتشار عمومی در این مأموریت انجام نشد.**

## ۱) مانعِ نشست — معماریِ پیاده‌شده

- `execution_browser_host.py`: پنجرهٔ پایدارِ Chrome/Edge/Brave با پروفایلِ
  اختصاصی و CDP فقط روی `127.0.0.1` و بندرِ تصادفی. مالک خودش وارد می‌شود؛
  هیچ token/cookie خوانده یا ذخیره نمی‌شود.
- `execution_browser.py`: `connect_over_cdp` + انتخابِ صفحهٔ همان دامنه + عدمِ
  بستنِ مرورگر هنگام detach. `active_cdp_url()` فقط hostِ سالمِ همین لحظه را
  برمی‌گرداند.
- `execution_strategy_engine.py`: اجرایِ زندهٔ مرورگری بدونِ host ⇒
  `AUTH_REQUIRED` (حتی اگر env/setting live باشد). dry-run همچنان بی‌ارسال است.
- `bors_entry.py --browser-host` و API `GET/POST/DELETE /api/execution/browser-host`
  و کنترلِ UI «بازکردن پنجرهٔ ورود / بستن».
- تستِ مرورگریِ محلی `tools/browser_host_smoke.py`: host ready، CDP متصل،
  Probe سه ورودی، **sessionStorage بعد از detach/reconnect باقی ماند**، host
  سالم ماند، stop → بسته شد؛ هیچ درخواستی به کارگزاری نرفت.

**محدودیتِ باقی‌مانده:** بعد از restartِ host/برنامه، ورودِ دستیِ مالک لازم است؛
هیچ احرازِ هویتِ خودکارِ مستقل از کاربر وجود ندارد. این Gate
`BLOCKED_EXTERNALLY` است و Live با آن آماده اعلام نمی‌شود.

## ۲) جدول Gateها

| Gate | وضعیت | مدرک/مسیر | اقدامِ لازم |
| --- | --- | --- | --- |
| Git/شاخه/کامیت‌ها | **PASS** | `git log`؛ سه کامیتِ قبلی + کامیتِ این دور | — |
| مقایسهٔ مراجع | **PASS** | `docs/SARKHATI-REFERENCE-COMPARISON-2026-10-20.md` | — |
| معماریِ نشست (host/CDP/ورود دستی) | **PASS** | `execution_browser_host.py`، driver، `tools/browser_host_smoke.py` | — |
| نشست پس از restart بدونِ ورود | **BLOCKED_EXTERNALLY** | sessionStorage؛ host پس از restart خالی | ورود دستی یا provider مجاز |
| قرارداد write EasyTrader | **BLOCKED_EXTERNALLY** | `WIRE_HYPOTHESIS=True`؛ صفر POST واقعی | تأیید مالک + تست زندهٔ تحت نظارت |
| دادهٔ همان روز (دامنه/گام/تقویم) | **BLOCKED_EXTERNALLY** | `readiness`؛ validator؛ snapshot فقط |
| قدرت خرید | **BLOCKED_EXTERNALLY** | `balances=False`؛ هیچ عددی ساخته نشد | منبع read-only معتبر |
| هویت نماد/هدر فرم | **PARTIAL** | ISIN محلی + هدرِ فرم در باندل؛ پیش‌فرض‌های خرید | تأییدِ DOM زنده در نشستِ مالک |
| نتیجهٔ canonical/UNKNOWN/تکرار | **PASS (Mock)** | `ResultState`؛ schedule/strategy guards | اثبات live فقط با مجوز |
| زمان‌بند/restart/SKIPPED | **PASS** | `execution_schedule_v1130.py` | — |
| UI readiness/live-disabled | **PASS (کد) / بازبینی بصری محدود** | Vitest/tsc + کارت host؛ در 1366×768 فقط گیتِ ورود دیده شد | ورودِ مالک برای بازبینی صفحهٔ داخلی؛ بدونِ bypass auth |
| Frozen build | **PASS** | 230.3MB؛ build exit 0؛ `onedir_contract` PASS؛ smoke DRY_RUN؛ daemon exit 0؛ `--browser-host --help` exit 0 | — |
| Live ready | **false** | `readiness.live_ready=false` | همهٔ Gateهای بالا |

## ۳) Preflight فقط‌خواندنیِ همین نشست

پنجرهٔ مالک باز است و صفحه رویِ **داروند** است؛ فرم با هدر «داروند»:
- قیمت‌هایِ نمایشی: 11,010 / 10,370؛ تعداد 1..100,000
- وضعیت: «نماد بسته است» / «خارج از ساعت معاملات!»؛ شروعِ آنلاین 08:45
- `order_posts=0`؛ هیچ کلیک/سفارش؛ buying power خوانده/ثبت نشد
- این snapshot **دادهٔ فردا نیست**؛ فردا باید از منبعِ معتبر دوباره خوانده شود.

## ۴) تست‌ها

| اجرا | نتیجه |
| --- | --- |
| `dev/execution_schedule_v1130.py` | **58/58** |
| `dev/strategy_guard_v1123.py` | **57/57** |
| `tools/browser_host_smoke.py` | host/CDP ready؛ probe سه ورودی؛ sessionStorage پس از reconnect = yes؛ host stop closed؛ no broker |
| `dev/run_all_tests.py` | **167 suite** (138 + 27 silent + 2 skip)؛ **4980/4980** check؛ exit 0 |
| Vitest / tsc | **197/199 فایل، 2065/2070 تست، 5 skip؛ tsc صفر خطا** |
| Frozen build/smoke | **PASS**؛ 230.3MB؛ contract PASS؛ create/arm → DRY_RUN؛ exit 0؛ بدون فرزند؛ daemon exit 0 |

## ۵) اقداماتِ دقیق برای عبور به آزمون مجاز Live

1. مالک در پنجرهٔ host (UI) وارد شود و نشست را باز نگه دارد.
2. مقادیرِ دقیق سفارش (نماد/ISIN، خرید، قیمت، تعداد، اعتبار) را تأیید کند.
3. منبعِ معتبرِ قدرت خرید و دادهٔ همان روز (دامنه/گام/تقویم) فراهم/تأیید شود.
4. یک تست زندهٔ تحت نظارت با حداقلِ ریسک مجاز شود؛ پیش از آن هیچ POST.
5. در صورت UNKNOWN، فقط reconcile خواندنی؛ هیچ retry/fallback.
6. انتشار نسخه مأموریتِ جداگانه است (بدون bump/tag در این دور).

**نتیجه:** موانعِ کدمحورِ نشست/زمان‌بند/نتیجه/تکرار/UI تا حدِ ممکن بسته شدند؛
Live تا تأیید مالک، دادهٔ روز و قرارداد واقعی `false` می‌ماند.

## ۶) محدودیتِ بازبینی بصری

در 1366×768، SPA قبل از هر صفحهٔ داخلی گیتِ «احراز هویت محلی» نشان می‌دهد
(نام کاربری/رمز عبور). بدونِ اعتبارنامهٔ مالک وارد نشدم و گیت را دور نزدم؛
بنابراین کارتِ زمان‌بندی/نشست در مرورگر واقعی دیده نشد. شواهدِ کد: Vitest و
tsc سبز؛ اسکرین‌شاتِ گیت در `%TEMP%` ثبت شد. بازبینیِ بصریِ کارت پس از
ورودِ مالک انجام می‌شود.

## ۷) SHA و تحویل

- HEAD پیش از این تغییرات: `cc07d154`؛ کامیتِ این دور پس از تأییدِ تست‌ها
  رویِ همان شاخه ثبت می‌شود (SHA در گزارشِ نهایی).
- هیچ version bump، tag، release، push به main یا انتشار انجام نشد.
- هیچ سفارش واقعی/POSTِ ثبت ارسال نشد.
