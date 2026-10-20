# Round 7 — UI Cleanup + In-App Test Cockpit + Owner Monitoring

شاخه: `mission/sarkhati-round7-test-cockpit-2026-10-20`
پایه: `90825e2658a835399e84e3a099af089cb6e1c666` (Round 6)
وضعیت: **`live_ready=false`**؛ هیچ سفارش واقعی، هیچ POST سفارش به کارگزاری و
هیچ انتشار/تغییر نسخه انجام نشد. `main` و `1.0.95` دست‌نخورده‌اند.

## A. تغییرات واقعی

| فایل/API | تغییر |
| --- | --- |
| `execution_cockpit.py` | store مستقل `execution_cockpit.db` برای run/event؛ ۱۱ سناریوی Mock؛ Gateهای وضعیت؛ Preflight مرکز؛ گزارش JSON با redaction؛ بازیابی RUNNING پس از restart به `INTERRUPTED` |
| `api/execution.py` | `/api/execution/cockpit/status`، `/runs` (GET/POST)، `/runs/{id}`، `/runs/{id}/stop`، `/preflight`، `/report`؛ همه فقط‌خواندنی/محلی و `live_send=false` |
| `execution_offerings.py` و API | افزودن `price_step` با migration سازگار؛ Preflight اکنون نبود/ناهم‌ترازی گام را مسدود می‌کند |
| `SarkhatiCockpitCard.tsx` | پنل «آمادگی و مانیتورینگ سرخطی»: وضعیت، Gateهای فشرده، جزئیات بازشونده، Preflight، Mock runner، Timeline، گزارش و توقف |
| `SarkhatiOfferingsCard.tsx` | نمایش گام قیمت، اولویت، عمر داده، منبع و `UNKNOWN_HOLD`؛ فرم گام قیمت |
| `orderClient.ts` | types و hookهای cockpit؛ polling فقط تا زمانی که یک run در حال اجراست |
| `SarkhatiPage.tsx` / `sarkhatiFlow.ts` | پنل زمان‌بندی به «آمادگی و پایش» تبدیل شد؛ کارت‌های قدیمی در بخش‌های بازشونده حفظ شدند |
| specها | `execution_cockpit` در `hiddenimports` هر دو spec |
| تست | `dev/execution_cockpit_v1141.py` (۵۳ بررسی) + `sarkhati-cockpit.spec.tsx` (۶ تست UI) |

مسیر Mock هیچ اتصالی به `execution_service` یا آداپتور سفارش ندارد؛ فقط
رویدادهای `MOCK`/`SIMULATED` در DB خودش می‌نویسد. هیچ fallback یا retry
سفارش واقعی اضافه نشد.

## B. بهبود UX

- قبل: پنل زمان‌بندی سه کارتِ پشت‌سرهم (عرضه/بودجه + زمان‌بندی ماندگار +
  زمان‌بندی قدیمی) بود و وضعیت/Gateها بین جدول‌ها گم می‌شد.
- بعد: یک پنل وضعیت‌محور با ارتفاع **۲۹۳px** در حالت بسته (1366×768)؛
  Gateهای باز فشرده، دلیل هر Gate در بازشو، اقدام بعدی در بالای پنل.
- Preflight و Mock به‌صورت دو بخش بازشونده در یک ردیف‌اند؛ مدیریت عرضه و
  زمان‌بندی داخل جزئیات پایین‌تر مانده‌اند. هیچ قابلیتی حذف نشد.
- رنگ: PASS سبز، FAIL قرمز، BLOCKED قرمز، UNVERIFIED/UNKNOWN زرد؛ Live و
  Mock با چیپ روشن و صریح.
- در 1366، 1920×1080 و 1280×720 هیچ overflow افقی دیده نشد؛ Gateهای باز
  به‌جای یک جدول بلند، چیپ‌های قابل‌اسکن شدند.

## C. پنل تست و مانیتورینگ

1. «سرخطی» ← «آمادگی و پایش».
2. کارت بالا: `Live مسدود`، تعداد Gate باز، نسخه و «اقدام بعدی».
3. بازکردن «دلیل هر Gate»: دلیل/شاهد/منبع/عمر هر Gate.
4. «مرکز Preflight»: انتخاب عرضه، قیمت، تعداد، اجرا؛ نتیجه و منبع هر بررسی
   (شامل بودجه/سقف هر عرضه).
5. «اجرای Mock درون‌برنامه»: انتخاب یکی از ۱۱ سناریو، اجرا، توقف، انتخاب
   run و Timeline؛ `MOCK`/`SIMULATED` روی خروجی دیده می‌شود.
6. «گزارش JSON»: خروجی تشخیصی با ماسک token/cookie/password/authorization.
7. «مدیریت عرضه، بودجه و رزروها» و «زمان‌بندی ماندگار» در جزئیات بسته.
8. هیچ دکمهٔ سفارش/ارسال زنده در پنل نیست؛ `live_ready=false` باقی است.

سناریوها: success، stale_data، missing_source، insufficient_budget،
unverified_offering، backend_error، duplicate_request، unknown_result،
unknown_hold، restart_recovery، host_error. هر run `run_id` مستقل دارد و
stop/restart وضعیت را حفظ می‌کند.

## D. تست

| آزمون | نتیجه |
| --- | --- |
| `dev/execution_cockpit_v1141.py` | **57/57**، exit 0 |
| `dev/execution_offerings_v1140.py` | **100/100**، exit 0 (شامل `price_step`) |
| `dev/execution_schedule_v1130.py` | **58/58** |
| `dev/strategy_guard_v1123.py` | **57 checks / 0 failed** |
| `dev/execution_timing_v1.py` | **32/32** |
| `dev/run_all_tests.py` | **140 suite شمارش‌شده + 27 خاموش + 2 skip؛ 5137/5137 check؛ `ALL SUITES PASSED`**، exit 0 |
| `npx vitest run --maxWorkers=2` | **198 passed / 2 skipped files؛ 2071 passed / 5 skipped tests**، exit 0 |
| `npx tsc -b` | **0 خطا** |
| Frozen build / onedir contract | **230.5 MB**، build exit 0؛ `onedir_contract PASS` (webview/pythonnet/clr_loader) |
| Frozen API smoke | عرضه `VERIFIED`، `RESERVED 10512.6`، `live_send=false`، cockpit status success/`live_ready=false`، Mock run `PASS` |
| Frozen daemon `--once` | exit 0؛ صفر schedule/event؛ بدون سفارش |

## E. QA تصویری

شواهد کامل و توضیح هر تصویر:
[`_audit/round7/visual/index.md`](../../_audit/round7/visual/index.md)

- 1366×768: پنل بسته ۲۹۳px، بدون overflow افقی.
- 1920×1080: پنل بسته ۲۸۰px، بدون overflow.
- 1280×720: پنل بسته ۳۰۵px، بدون overflow.
- Preflight روی TESTA = PASS؛ روی TESTB (UNVERIFIED) = BLOCKED با
  `source_verified=FAIL`؛ بودجهٔ ناکافی نیز در guard/API مسدود می‌شود.
- Mock success: `run-… · موفق`، `order_sent=false`، بدون retry.
- unknown_hold، stale_data، missing_source و backend_error همگی تصویر و
  Timeline دارند.
- قبل/بعد: `00-before-1366x768.png` از Round 6 (واقعی) در برابر
  `01-cockpit-1366x768.png`؛ قبل جعل نشده است.
- محدودیت هارنس: فقط روتر execution سرو می‌شود؛ ۴۰۴های سایر APIها در
  تصاویر/کنسول محدودیت هارنس‌اند، نه ادعای سلامت آن مسیرها. داده‌ها fixture
  با علامت `MOCK` هستند.
- **داوری زیبایی‌شناختی نهایی مالک: UNVERIFIED**؛ من PASS بصری اعلام نمی‌کنم.

## F. GitHub

- شاخه: `mission/sarkhati-round7-test-cockpit-2026-10-20`
- کامیت کد/تست: `6ab9d5ae`
- اسناد و تصاویر در آخرین کامیت همین شاخه‌اند.
- گزارش: https://github.com/johnwarchief/BorsTerminal-src/blob/mission/sarkhati-round7-test-cockpit-2026-10-20/docs/SARKHATI-ROUND7-REPORT-2026-10-20.md
- شواهد بصری: https://github.com/johnwarchief/BorsTerminal-src/blob/mission/sarkhati-round7-test-cockpit-2026-10-20/_audit/round7/visual/index.md
- تصویر اصلی 1366: https://raw.githubusercontent.com/johnwarchief/BorsTerminal-src/mission/sarkhati-round7-test-cockpit-2026-10-20/_audit/round7/visual/01-cockpit-1366x768.png
- فقط همین شاخه push می‌شود؛ `main`، tag و release دست‌نخورده‌اند.

## G. تست مالک

پیش‌نیاز: Python/Node و همین worktree؛ هیچ حساب کارگزاری لازم نیست.

```bash
cd C:\Users\PCMOD\Desktop\_bors-sarkhati-minfix
.venv\Scripts\python.exe scripts\build_all.py
dist\BorsTerminal_Ultimate\BorsTerminal_Ultimate.exe
```

بیلد را با `.venv` رسمی اجرا کنید؛ مفسرِ سیستم (Python 3.14) بسته‌های
`webview/pythonnet/clr_loader` را ندارد و قرارداد onedir را رد می‌کند.

یا برای UI توسعه:

```bash
cd frontend
npm run dev
```

مراحل:
1. «سرخطی» ← «آمادگی و پایش».
2. `Live مسدود` و Gateهای باز را ببینید؛ «دلیل هر Gate» را باز کنید.
3. «مرکز Preflight» را باز کنید؛ یک عرضه را انتخاب و قیمت/تعداد را وارد کنید.
4. «اجرای Mock درون‌برنامه» را باز کنید؛ `success` را اجرا و Timeline را ببینید.
5. `unknown_hold`، `stale_data` و `backend_error` را جدا اجرا کنید.
6. «گزارش JSON» را بگیرید و بازبینی کنید که token/cookie ندارد.
7. انتظار: هیچ سفارش واقعی، هیچ Live و هیچ سبزشدن Gate بیرونی.

## H. موانع باقی‌مانده

- دادهٔ رسمی عرضه/تقویم/قدرت خرید: `BLOCKED_EXTERNALLY`.
- نشست EasyTrader و host: `BLOCKED_EXTERNALLY` (ورود دستی مالک).
- قرارداد write، پذیرش و جایگاه صف: `UNVERIFIED`/`BLOCKED_EXTERNALLY`.
- `live_ready=false`؛ هیچ ادعای سود/تخصیص/سرعت/صف نداریم.
- داوری بصری نهایی مالک: `UNVERIFIED`.

## I. گام بعدی

Round 8: مالک host را باز و دستی وارد می‌شود؛ منبع رسمی عرضه/تقویم/قدرت خرید
با provenance واقعی وصل می‌شود؛ Preflight واقعی و read-only اجرا می‌شود.
Round 9 (فقط با مجوز جداگانه): اندازه‌گیری read-only پذیرش/صف؛ هیچ Gateای
بدون شاهد سبز نمی‌شود.
