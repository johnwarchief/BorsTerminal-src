# وضعیت اجرایی سرخطی — ۲۰۲۶-۱۰-۲۰ (پس از P0 زمان‌بندی)

شاخه: `mission/multi-strategy-2026-10-20`
مبنای این گزارش: `0d593921` + تغییرات جاری
هدف: پیاده‌سازی سرتاسری سرخطی، نه گزارشِ صرف.

## ۱) ماتریس پژوهش و تصمیم

جزئیاتِ پنج مخزن و endpoint/payload در
`docs/trading/EASYTRADER-OSS-RESEARCH-MATRIX.md` و
`docs/research/SARKHATI-CAPABILITY-MATRIX-2026-10-17.md` ثبت شده است. خلاصهٔ تصمیم:

| قابلیت | مرجعِ اصلی | وضعیت در BorsTerminal | تصمیم |
| --- | --- | --- | --- |
| Direct API | `RezaMahdaviiDev/mofid`, `m-fazel/Sarkhati` | `execution_easytrader.py`؛ read-only زنده دیده شد؛ POST واقعی نه | نگه‌داشتن؛ live تا تأیید قرارداد خاموش |
| Playwright/DOM | `AutoBuy-MofidBroker`, `RezaMahdaviiDev/mofid` | `execution_browser.py` + `DomStrategy`؛ Mock و Frozen Probe | نگه‌داشتن؛ بازخوانیِ پیش از ارسال اضافه شد |
| JavaScript | `RezaMahdaviiDev/mofid` | `JavaScriptStrategy`؛ Mock | نگه‌داشتن؛ live نه |
| Keyboard | `RezaMahdaviiDev/mofid` | `KeyboardStrategy`؛ یک ارسال حداکثر | نگه‌داشتن؛ live نه |
| AutoClicker | `AutoBuy-MofidBroker` | `AutoClickerStrategy`؛ یک کلیک | نگه‌داشتن؛ live نه |
| Selenium | — | بسته نصب نیست | `UNAVAILABLE` صادقانه |
| زمان‌بند پایدار | مأموریتِ P0 | `execution_schedule.py` + daemon | پیاده و تست شد |
| تأیید سفارش/صف | قراردادِ EasyTrader | `isSuccessful`/`id`، reconcile؛ صف فقط UI | POST واقعی UNVERIFIED؛ صف UNVERIFIED |
| داشبورد/گزارش | UI موجود + کارت ماندگار | Sarkhati page + DurableScheduleCard | تکمیلِ تدریجی |

## ۲) قابلیت‌های تازهٔ این مرحله

- **Preflight موازی فقط‌خواندنی:** `StrategyEngine.parallel_probe` +
  `POST /api/execution/strategies/preflight`؛ هر Strategy جدا Probe می‌شود،
  زمان/وضعیت برمی‌گردد، هیچ prepare/trigger/dispatch صدا زده نمی‌شود.
- **بازخوانیِ پیش از ارسال:** در `BrowserStrategyBase.trigger` پیش از هر کلیک،
  نماد/قیمت/تعداد فرم دوباره خوانده می‌شود؛ تغییر async → `SYMBOL/PRICE/QUANTITY_MISMATCH`
  و توقف، بدون کلیک.
- **وضعیت canonical سفارش:** `NOT_SENT, REJECTED, ACCEPTED, UNKNOWN, FILLED, CANCELLED`؛
  `ACKNOWLEDGED` بدون شاهدِ پر شدن = `ACCEPTED`، نه `FILLED`.
- **نتیجهٔ ماندگار:** `result_state` در پاسخ API/UI؛ dry-run = `NOT_SENT`.
- **کارت UI:** زمان‌بندی ماندگار، Preflight موازی، چک‌لیست validation، نتیجهٔ canonical.

## ۳) تست و پذیرش (Mock/Frozen)

| سناریو | پوشش |
| --- | --- |
| انتخاب/تغییر نماد و mismatch | `strategy_guard` (بازکردن فرم، هدر، async) |
| تغییر async قیمت/تعداد | `strategy_guard` — سه تست |
| Preflight موازی / عدم تداخل | `strategy_guard` — دو تست |
| ذخیره/restart/NEEDS_REVIEW | `execution_schedule_v1130` |
| دو claim هم‌زمان/تکرار | `execution_schedule_v1130` |
| MISSED_TARGET/Hibernate-like late | `execution_schedule_v1130` |
| UNKNOWN/عدم retry/کلید قفل | `execution_schedule_v1130` |
| session/401/timeout/5xx/200 بدون فیلد | adapter/service/protocol guards |
| UI/TypeScript | Vitest + `tsc -b` |

| اجرا | نتیجهٔ نهایی |
| --- | --- |
| `dev/execution_schedule_v1130.py` | **50/50** |
| `dev/strategy_guard_v1123.py` | **55/55** |
| `dev/run_all_tests.py` | **167 suite** (138 شمارش‌دار + 27 silent + 2 skip)؛ **4972/4972** check؛ exit 0 |
| Vitest | 197/199 فایل؛ 2065/2070 تست؛ 5 skip؛ exit 0 |
| `npx tsc -b` | صفر خطا |
| Frozen | 230.3MB؛ build exit 0؛ `onedir_contract` PASS |
| Frozen smoke | create/arm → **DRY_RUN**؛ خروج 0؛ بدون فرزند |
| Frozen daemon | `--schedule-daemon --once` → exit 0 |

### جدول بنچمارک (Mockِ منصفانه، اجرای ۱۰۰تاییِ commit 7d16d888)

| روش | trigger p50/p95/p99 (ms) | RTT HTTP p50/p95/p99 (ms) | E2E p95 (ms) |
| --- | --- | --- | --- |
| Direct API | 0.018 / 0.027 / 0.049 | 11.6 / 29.4 / 33.0 | 29.458 |
| JavaScript | 7.698 / 8.726 / 9.479 | 13.522 / 14.659 / 14.9 | 23.328 |
| Keyboard | 11.526 / 13.278 / 14.1 | 13.919 / 15.505 / 15.943 | 28.049 |
| Playwright/DOM | 11.358 / 13.95 / 15.284 | 13.899 / 15.024 / 15.662 | 28.127 |
| AutoClicker | 26.086 / 29.509 / 30.265 | 13.686 / 14.757 / 15.507 | 44.26 |

۳ warm-up + ۱۰۰ اندازه‌گیری، همه به یک Mockِ HTTPSِ محلی، صفر درخواستِ خارجی،
صفر سفارش. این اعداد پیش از افزودنِ بازخوانیِ پیش از ارسال هستند و در این
increment دوباره اندازه‌گیری نشدند؛ برای ادعای live معتبر نیستند.

## ۴) اثبات‌شده در برابر تأییدنشده

| ادعا | وضعیت |
| --- | --- |
| ذخیرهٔ ماندگار و بازیابی | **اثبات‌شده** (Mock + Frozen) |
| اجرای dry-run بدون UI/Qoder | **اثبات‌شده** (daemon Frozen) |
| Preflight موازی بدون ارسال | **اثبات‌شده** (Mock) |
| بازخوانیِ فرم پیش از ارسال | **اثبات‌شده** (Mock) |
| ارسال واقعی سفارش | **اثبات‌نشده** — هیچ POST/پاسخ کارگزاری مشاهده نشد |
| نشست پایدار برای اجرای خودکار | **مسدود** — sessionStorage، بدون provider مجاز |
| قدرت خرید/دامنه/گام واقعی | **مسدود/UNKNOWN** |
| صف و اول‌شدن | **تضمین نمی‌شود** |

## ۵) Release

- بیلد Frozen ساخته و سنجیده شد: `dist/BorsTerminal_Ultimate`، **230.3MB**،
  contract PASS، smoke DRY_RUN، daemon exit 0.
- نسخهٔ فعلی `1.0.95` است و **منتشر نشد**: Gateهای زنده (قرارداد/نشست) عبور
  نکرده‌اند، شاخهٔ مأموریت local-only است و انتشار نیاز به merge/CI و تأیید
  مالک دارد. bump/تگ/انتشار در این مرحله انجام نشد. خروجیِ قابل نصب همان
  پوشهٔ `dist/BorsTerminal_Ultimate` است.

## ۶) اقدامات باقی‌مانده برای اجرای زنده

1. احراز هویت پایدار و مجاز (خارج از sessionStorage/HAR حساس).
2. تأیید قرارداد POST/پاسخ با یک تست زندهٔ تحت نظارت و مقادیر منتخب مالک.
3. منبع معتبر قدرت خرید، دامنه/گام و تقویم همان روز.
4. selector پایدار هدر/فرم و پیکربندی در تنظیمات Strategy.
5. تست‌های باقی‌مانده: restart در آستانهٔ ارسالِ واقعی، 429، صف، و
   قطع شبکه حین POST — فقط با Mock/ترافیک بدل تا مجوز زنده.
