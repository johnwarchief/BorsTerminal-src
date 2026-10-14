# دست‌نویسِ تحویل — سرخطی EasyTrader (مرحلۀ ۰ تا ۲ انجام شد؛ ۳ به بعد باقی است)

تاریخ: ۱۴۰۵-۰۷-۲۴ (۲۰۲۶-۱۰-۱۵، ~۰۰:۴۵ تهران) · شاخه `mission/4-axes-2026-10-10` ·
مأموریت: «بستن کامل سرخطی با اتصال واقعی EasyTrader بر مبنای پنج مخزن».
این فایل ادامهٔ `docs/trading/EASYTRADER-OSS-RESEARCH-MATRIX.md` است و جایِ آن را نمی‌گیرد.

**وضعیت Git:** HEAD = `9cf9308` (ماتریسِ پنج مخزن). `main`ِ ریموت رویِ `a412697` است و
این شاخه یکِ کامیت جلوتر ازِ ریموتِ خودی — **بی‌push**، چون مأموریتِ حاضر push/merge/tag/
release را بدونِ مجوزِ صریح ممنوع کرده است. دو فایلِ نشستِ دیگر
(`_audit/FTS_TREND_COMPARE.csv`، `tools/market_state_probe.mts`) دست‌نخورده و استیج نشده‌اند.

## ۱) نقشۀ مسیرِ فعلی، با برچسبِ خواستۀ مأموریت

`UI → BorsTerminal API → EasyTrader Adapter → Broker Request → Broker Response → Order State → History/Queue/Stop`

| حلقه | جایِ واقعی | برچسب |
|---|---|---|
| UI | `frontend/src/features/portfolio/lib/orderClient.ts:147` (`GET /api/execution/status`) و `components/WatchSummaryPanel.tsx:9-101` (کنترل «غیرفعال» از `capabilities`ِ پاسخِ واقعی خوانده می‌شود) | `IMPLEMENTED` برایِ وضعیت‌نمایی؛ **فرمِ سفارش/پیش‌نمایش/تاریخچه ندارد** ⇒ `UNVERIFIED` به‌عنوانِ قابلیت |
| API | `api/execution.py` (۳۲۹ سطر): status/preflight/prepare/dispatch/reconcile/queue/ledger/limits/halt/resume/audit | `TESTED_WITH_MOCK` — و رویِ **بیلدِ منجمدِ ۱٫۰٫۸۸** هم آزموده شد (`docs/SAME-DAY-CLOSURE-2026-10-14.md` §۹-پ بندِ ۴: halt → ردِ dispatch با `code: HALTED` → resume؛ ۳ رخداد پسِ کشتنِ پروسه از اتصالِ تازه) |
| قرارداد/حالت | `execution_contract.py`: `ErrorCode` با `TIMEOUT`/`NETWORK_ERROR`/`UNKNOWN_RESULT` درِ `UNRESOLVED_CODES` (:133) و `RETRY_FORBIDDEN_CODES` (:137)، `HALTED` (:121) که عامدانه درِ UNRESOLVED **نیست**، `SessionState` چهارمقداری (:176-179) | `IMPLEMENTED` |
| ارکستراسیون | `execution_service.py`: dry-run پیش‌فرض، preflight (شاملِ `kill_switch`، `data_age`، تکراریِ پایدار)، `_check_limits` با fail-closed | `TESTED_WITH_MOCK` (۴۴/۴۴) |
| آداپتور | **تنها `execution_mock.MockBrokerAdapter`**؛ `ADAPTER_KIND` فقط `"mock"` و `DRY_RUN` ثابتِ `True` (بندِ ۳ گاردِ `dev/execution_service_v1.py` ثابت می‌کند هیچ بدنه‌ای آن‌ها را عوض نمی‌کند) | `TESTED_WITH_MOCK` |
| **EasyTrader Adapter** | **وجود ندارد** — `grep -i easytrader` رویِ کلِ کد جزِ یکِ رشتهٔ توضیحی درِ `api/execution.py:178` (`blocked_on`) چیزی نمی‌دهد | `NOT_STARTED_BUT_REQUIRED` |
| Broker Request/Response | هیچ درخواستِ واقعی هرگز ساخته و سنجیده نشده | `UNVERIFIED` (فقط فرضیه‌هایِ مخزن، درِ ماتریس) |
| Order State | درِ ماشینِ موجود است؛ «۲xx ⇒ پذیرش» درِ هیچ کدِ ما نیست | `TESTED_WITH_MOCK` |
| History/Queue | `execution_ledger.py` ردِّپایِ append-only رویِ `user.db` با `redact()` پیش ازِ INSERT؛ صف: `QueueSnapshot.position = None` یعنی UNKNOWN | `TESTED_WITH_MOCK` |
| Stop | قفلِ سه‌حالتهٔ `ARMED/HALTED/TRIPPED` پایدار رویِ دیسک؛ `TRIPPED` بی‌`confirm=True` باز نمی‌شود؛ درِ preflight بازخوانی می‌شود | `TESTED_WITH_MOCK` + رویِ بیلدِ منتشرشده |
| Frozen/Windows | درِ ۱٫۰٫۸۸ ثابت شد که `api/execution.py` و `execution_*` درِ `PYZ` بیلدِ منجمد هستند (بی‌`ModuleNotFoundError`)؛ ولی مسیرِ EasyTrader هنوز ساخته نشده پس آزمونِ frozenِ آن باقی است | `UNVERIFIED` برایِ آداپتور |

جمعِ گاردهایِ سرخطی امروز: **۱۸۶ سبز / ۰ سرخ** (`execution_contract_v1` ۲۰ · `execution_timing_v1` ۳۲ ·
`execution_latency_v1` ۲۱ · `execution_service_v1` ۴۴ · `execution_queue_v1` ۲۴ ·
`execution_ledger_v1108` ۴۵).

## ۲) D8 و D1 — آنچه ثابت شد و آنچه فقط مالک می‌دهد

- **D8 دیگر سؤالِ بی‌اطلاعات نیست.** دو پروتکلِ جدا وجود دارد: EasyTrader/Orbis-MTS
  (`api-mts.orbis.easytrader.ir`، بدنۀ `{"order":{…}}`، `side` عددی، `symbolIsin`) و
  Mofid Online-Plus/Titan (`mofidonline.com/apigateway/api/v1/Order/send`، بدنۀ تخت،
  `orderSide` رشته‌ای، `x-appname: titan`). چهار از پنج مخزن رویِ EasyTrader است و عنوانِ
  این مأموریت هم EasyTrader است ⇒ پیش‌فرضِ فنیِ امن: **EasyTrader**، با نگه‌داشتنِ شکلِ سیم در
  یکِ فایلِ ثابت تا شاخۀ دیگر جایگزینیِ پیکربندی باشد نه بازنویسی. تصمیمِ نهایی با مالک است
  چون بستگی به این دارد حسابِ او رویِ کدام سکو باز است.
- **D1 (مجوزِ PoC روی حسابِ واقعی) بی‌پاسخ است و درِ این ماشین چیزی برای آزمودن نیست:**
  `adb_config.json` نیست، هیچ فایلِ موفید/EasyTrader نیست، هیچ متغیرِ محیطیِ کارگزاری نیست
  (فقط `codal_control.json` وجود دارد). پس هیچ سنجشِ زنده‌ای درِ این دور انجام نشد و انجام
  دادنی نبود.
- لازمۀ هر سنجشِ زنده: **ورودِ تعاملی را خودِ مالک انجام می‌دهد**؛ هیچ CAPTCHA/MFA یا کنترلِ
  امنیتی دور زده نمی‌شود؛ و «آزمونِ ارسال» با سفارشِ واقعی کالیبره نمی‌شود (این کاری است که
  مخزن ۱ و ۲ می‌کنند و ما ردش کردیم).

## ۳) قراردادِ طراحیِ آداپتور (هشت قفلِ گرفته‌شده از ماتریس)

این‌ها را گارد می‌سازد، نه کامنت:

1. **`HTTP 2xx` هیچ حکمی نیست.** پذیرش فقط از پاکت: `isSuccessful` و نبودِ
   `omsError[{name,error,code}]`. شاهدِ مخزن ۲: `client.ts:414-419` و spec `:107-120` که
   `id` را درِ پاسخِ **ردشده** هم نشان می‌دهد ⇒ «id داشت» هرگز = پذیرش نیست.
2. **timeout/خطای شبکه ⇒ `UNKNOWN_RESULT`، و ارسالِ مجدد تا رفعِ ابهام ممنوع.** رفعِ ابهام از
   منبعِ وضعیتِ معتبر: `GET /core/api/order` + تطبیقِ `id` (یکۀ reconcile). این دقیقاً همان
   چیزی است که چهار مخزن نمی‌کنند (۲۵/۱۵/۴۰ کلیک، `batch_repeat`، retryِ `408/5xx`).
3. **`400` پایانی** (بی‌retry) و **`401` = باطل‌کردنِ نشست + بی‌retry** — همان دو رفتاری که درِ
   مخزن ۲ درست است؛ `429` باید مسیرِ صریحِ `RATE_LIMITED` داشته باشد (درِ هر پنج مخزن نبود).
4. **ادعای exactly-once نوشته نمی‌شود:** هیچ‌یک از پنج مخزن idempotency key ندارد؛ محافظت از
   ردیفِ پایدارِ dispatch + حالتِ UNKNOWN می‌آید.
5. **توقفِ ماندگارِ ما باقی می‌ماند** و درِ هر مرحله بازخوانی می‌شود (نه فقط پیش از ارسال)، چون
   الگویِ پنج مخزن پرچمِ در-حافظه/Ctrl-C/`window.myRunId` است که یا درِ حلقۀ ارسال خوانده
   نمی‌شود یا با reload می‌میرد.
6. **هیچ secret در فایل، دیتابیس، لاگ یا خروجِ فرمان.** مکانِ نگهداری: حافظه یا Windows
   Credential Manager/DPAPI. UI فقط *وضعیتِ نشست* را می‌بیند نه مقدار را. شاهدِ رد:
   `tokenCache.ts:95`، `browser.ts:108`، `advancedLogger.ts:235-245`، HARِ کامیت‌شدهٔ ۵٫۳MB،
   و رمزهایِ کامیت‌شده درِ تاریخچۀ مخزن ۴ (`web_scraping.py@b3f8eab:9-10`).
7. **زمان:** نه `now == target` (مخزن ۴) نه sleepِ ثابت. مقایسۀ monotonic با tolerance و
   deadline؛ منبعِ ساعت (`broker` یا `system`) و اختلافشان درِ ردِّپا ثبت شود؛ اگر هدف
   خورده شد ⇒ `UNKNOWN` نه چرخشِ بی‌صدا؛ ساعتِ گذشته «فردا» نمی‌شود (مخزن ۵).
8. **جایگاه صف فقط نمایش، با واحدِ نامعلوم، و هرگز تعبیرِ «اولِ صف»:** `orderPlace <= 1` درِ
   مخزن ۲ خطِ `:399-406` است و `volumeAhead` بی‌واحد؛ خالی‌بودنِ پاسخ درِ آن‌ها «موفق» حل
   می‌شود — ما خالی = `QUEUE_UNAVAILABLE` (بی‌داده)، نه صفر و نه اولِ صف.

## ۴) ترتیبِ کارِ باقی‌مانده (هر کدام بی‌credential و بی‌سفارشِ واقعی انجام‌دادنی است)

1. `execution_easytrader.py` — آداپتور با **ترافیکِ تزریقی** (transport/inject; درِ construction
   هیچ network نمی‌زند)، ثابت‌هایِ سیم درِ یکِ dictِ module-level با برچسبِ
   `HYPOTHESIS (repo mofid@72a2e8c …) — not verified against the broker`، timeoutِ صریح روی
   هر عملیات، و capabilities صادق (`live_enabled=False` تا روزِ اول).
2. `interpret_easytrader_response(status, body)` — تنها پیاده‌سازیِ قواعدِ بندِ ۱/۳؛ ورودی‌اش
   پاکتِ خام است و خروجی‌اش `(OrderState|None, ErrorCode|None, broker_id|None, oms_errors)`.
3. بازخوانیِ `SessionState` به شش مقدارِ خواستۀ مأموریت (افزودنِ `AUTH_FAILED` و `ERROR` درِ
   همان enumِ canonical، نه یک enumِ دوم درِ UI) — و `api/execution.py` آن را از آداپتور
   می‌خواند، نه ازِ مقدارِ ثابت.
4. UI: فرمِ سفارش + پیش‌نمایشِ نهایی + تاریخچه/وضعیت + «آزمونِ اتصال» با stateهایِ واقعی،
   پشتِ همان `capabilities` (هیچ دکمه‌ای بی‌پشتوانه فعال نمی‌شود؛ قاعدۀ نشستِ پیشین).
5. گاردِ `dev/easytrader_adapter_v1113.py` با **کنترلِ منفی**: بدنه‌ای بسازید که ۲۰۰+
   `isSuccessful:false` دارد ⇒ باید رد شود؛ اگر آداپتور ۲۰۰ را پذیرش بخواند سنسور قرمز
   شود. سناریوهایِ خواستۀ بندِ ۷-A: نشستِ منقضی، ۴xx/۵xx/۴۲۹، timeout ⇒ UNKNOWN + بی‌ارسالِ
   مجدد، dispatch هم‌زمان، halt/resume/restart، پاک‌سازیِ secret درِ خروج، و **جست‌وجویِ
   هرگونهِ token درِ لاگِ خروجیِ تست**.
6. `hiddenimports` درِ `fts_terminal.spec` و `bors_setup.spec` برایِ هر ماژولِ ریشةِ تازه
   (قاعدۀ مخزن: وگرنه EXE درِ اولین درخواست می‌میرد).
7. آزمونِ Frozen/Portable رویِ ویندوز با workload یکسان (پیش/پس) و CPU/RAM/latency.
8. گیت‌ها (`tsc`، `vitest`، `build`، `run_all_tests`) و سپس گزارشِ چهارده‌بخشی با رأیِ
   `DONE_VERIFIED`/`PARTIAL`/`BLOCKED`. تا پیش ازِ دیدنِ اتصالِ واقعی و رفتارِ سفارش با شاهد،
   رأی **نمی‌تواند** `DONE_VERIFIED` باشد.

## ۵) خط‌هایِ سرخِ این مأموریت (دست‌نخورده می‌مانند)

- push/merge/tag/release بی‌مجوزِ صریح؛ force-push؛ بازنویسیِ تاریخچه.
- هیچ سفارشِ واقعی تا تأییدِ روشنِ مالک رویِ فرمِ نهایی؛ و هیچ‌گاه سفارشِ واقعی برایِ سنجشِ
  سرعت/retry/کالیبراسیون/سبزشدنِ تست. اگر `UNKNOWN` شد، ارسالِ مجدد ممنوع.
- دورزدنِ CAPTCHA/MFA یا هر کنترلِ امنیتی؛ استفاده ازِ نشستِ کسی غیر از مالک.
- چاپِ token/cookie/Authorization درِ لاگ، خروجِ فرمان، گزارش، تست یا Git — حتی نمایشِ
  فرمانِ curlِ حاویِ token.
- دست‌زدنِ `market.db`، پاک‌کردنِ کارِ ایجنتِ دیگر، و ورود به دامنهٔ تکنیکال/موتورِ تعدیل.
- تستی که اجرا نشده نباید سبز گزارش شود؛ ادعایِ اتصالِ واقعی ازِ رویِ mock ساخته نمی‌شود.

## ۶) رأیِ دورِ اول

`PARTIAL` — مرحلۀ ۰ (نقشهٔ مسیر با برچسب)، مرحلۀ ۱ (ماتریسِ پنج مخزن با commitها و
file:lineها) و تعیینِ تکلیفِ مستندِ D8/D1 انجام شد. مرحلۀ ۲ تا ۸ انجام **نشد**: آداپتور،
ماشینِ حالت رویِ پاسخِ واقعی، UI، تست‌هایِ mock، frozen/Windows و گیت‌هایِ نهایی. هیچ ادعایِ
«اتصالِ واقعی تأیید شد» درِ این دور نوشته نمی‌شود.


## ۷) دورِ دوم (۲۰۲۶-۱۰-۱۵، ~۰۱:۳۰) — بندِ ۴، steps ۱ تا ۶ انجام شد؛ ۷ و ۸ نه

شاخه `mission/easytrader-adapter-2026-10-15` درِ worktree جدا، بی‌دست‌زدنِ کارِ
نشست‌هایِ دیگر. رأیِ مالک D8 را بست: سکوی هدف EasyTrader/Orbis-MTS است، و
Online-Plus/Titan هیچ ثابتی درِ این کد ندارد — نه حتی یکِ کلیدِ مشترک.

| stepِ §۴ | وضعیت | کجا |
|---|---|---|
| ۱ آداپتور با ترافیکِ تزریقی | انجام | `execution_easytrader.py` — پیش‌فرض `RefusingTransport`؛ درِ construction صفرِ سوکت (سنجیده با خاموش‌کردنِ `socket.socket`) |
| ۲ `interpret_easytrader_response` | انجام | همان فایل؛ یگانه مالکِ معنایِ پاسخ، با نگاشتِ `omsError.code` ← `ErrorCode` |
| ۳ `SessionState` شش‌مقداری | انجام | `execution_contract.py`؛ درِ `api/execution.py` ازِ آداپتور خوانده می‌شود نه ازِ ثابت |
| ۴ UI: فرم/پیش‌نمایش/تاریخچه/آزمونِ اتصال | انجام | `features/portfolio/components/ExecutionPanel.tsx` + `lib/orderClient.ts`؛ هر کنترل پشتِ `capabilities`ِ واقعی، نشستِ بدل «Connected» نمی‌شود، توقف/ادامه درِ حالتِ بدل هم کار می‌کند |
| ۵ گارد با کنترلِ منفی | انجام | `dev/easytrader_adapter_v1113.py`؛ `run_contract`ِ سوئیتِ قرارداد رویِ همین آداپتور هم می‌دود (۱۶ سبز + یکِ استثنایِ ثبت‌شده که خطرِاش رویِ دفترِ خودِ بروکرِ بدیل بازنویسی شد) |
| ۶ hiddenimports | انجام | هر دو spec + سنجهٔ متنِ spec درِ گارد |
| ۷ Frozen/Portable رویِ ویندوز | باقی | بیلدِ onedir درِ این دور گرفته نشده؛ `api.execution` درِ ۱٫۰٫۸۸ ثابت شد ولی مسیرِ EasyTrader هنوز درِ EXE دیده نشده |
| ۸ گیت‌هایِ نهایی و گزارش | درِ همین دور | tsc / eslint / vitest / build / `run_all_tests` |

**آنچه آزموده شد و آنچه نشد.** همهٔ آزمون‌ها آفلاین‌اند: ترافیکِ بدیلِ سمتِ سرور،
با بدنه‌هایِ همان قالبِ گزارش‌شده. هیچ درخواستی به `api-mts.orbis.easytrader.ir`
نرفته، هیچ نشانیِ واقعی درِ این ماشین نیست، و هیچ سفارشِ واقعی ساخته نشده.
درِ بیلدِ devِ محلی هم فقط مسیرِ ردشدن با HTTPِ زنده سنجیده شد (۱۲۷.۰.۰.۱):
`adapter=easytrader` بی‌`BORS_EXECUTION_LIVE` و بی‌نشست ⇒ `live_enabled=false`،
همۀ `capabilities` false، `dispatch` با `place: FAIL` رد، `probe` بی‌هیچ درخواست،
و `session` بی‌LIVE نشانی را ذخیره نمی‌کند. رأیِ این دور هم **`PARTIAL`**:
`LIVE_READ_ONLY_VERIFIED` و `LIVE_ORDER_VERIFIED` صفر بار اجرا شده‌اند.

**قفل‌هایی که گارد می‌سنجد، نه کامنت.** ۲۰۰ با `isSuccessful:false` ⇒ رد، و `id`
ِ پاسخِ ردشده نگه نمی‌ماند؛ نبودِ `isSuccessful` ⇒ نامعلوم؛ ۴۰۸/۵xx/۳xx/HTML ⇒
نامعلوم و بی‌ارسالِ دوباره؛ ۴۰۱ نشست را باطل می‌کند و ۴۰۳ حالتی جداست؛ ۴۲۹ ⇒
`RATE_LIMITED` با `Retry-After`؛ صفِ خالی ⇒ None نه صفر؛ `max_retries=0` درِ
لایۀِ HTTP؛ token درِ لاگ/ردِّپا/دیسک/`repr`/پاسخِ HTTP نمی‌ماند؛ halt درِ همان
لحظه زمان‌بندیِ درِ انتظار را لغو می‌کند و پیش ازِ آتش هیچ درخواستی نمی‌زند.

**باقی‌ماندهٔ دستِ مالک (D1).** ورودِ تعاملی به `d.easytrader.ir` و دادنِ نشانی به
`POST /api/execution/session` — فقط درِ حافظه، با restart می‌میرد. پسِ آن
«آزمونِ اتصالِ» فقط‌خواندنی، و سپسِ پیش‌نمایشِ نهایی با تأییدِ روشنِ او رویِ فرم.
هیچ سفارشی برایِ سنجشِ سرعت/retry/کالیبراسیون فرستاده نمی‌شود.
