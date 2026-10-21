# Round 14 — AutoClicker Reliability & Execution Correctness

> تاریخ: ۲۰۲۶-۱۰-۲۱ | شاخه: `mission/sarkhati-round14-reliability-2026-10-21` | مبنا: `865ef8d9` (راند ۱۳ + گزارشِ تحقیق) | commit: `3f59be54`
> وضعیتِ ارسالِ زنده: `live_enabled=false` · `live_ready=false` · هیچ سفارشِ واقعی ارسال نشد.
>
> **هشدارِ داده (باید به مالک اعلام شود):** در جریانِ suiteِ کاملِ backend، `market.db` عملیاتی تغییر کرد (fingerprint از `5a9117aa…135bea3` به `fd688edb…790b73dc`، mtime 21:44). suite پس از ۵۶ سوئیت متوقف شد؛ هیچ بازنویسی/بازیابیِ خودکار انجام نشد. جزئیات در بند ۷.

## ۱. مبنا و دامنه

این راند از HEADِ راند ۱۳ (`e13256b9`) و commitِ گزارشِ تحقیق (`865ef8d9`) شروع شد. مسیرِ واقعیِ اجرا پیش از تغییر خوانده شد: `AutoClickerPage` → `/api/execution/strategies/prepare|trigger|abort|dispatch` → `StrategyEngine` → `Scheduler`/`BrowserStrategyBase` → `PlaywrightBrowserDriver` → `/core/api/v2/order`. هیچ استراتژی موازی ساخته نشد و هیچ رفتارِ UI حذف نشد.

## ۲. وضعیتِ اولیهٔ ایرادها

| # | ایراد | محلِ اولیه | رفتارِ مشاهده‌شده |
| --- | --- | --- | --- |
| P0-1 | dry-run وابسته به `intercept_pattern` کاربر | `execution_strategy_engine.py:557` و `execution_browser.py:573` | اگر URL/host/path/method با الگو نمی‌خورد، POST می‌توانست از گارد عبور کند و نتیجه `failed/NO_ORDER_REQUEST` شود. |
| P0-2 | idempotency فقط در حافظه و بر اساسِ `execution_id` | `execution_strategy_core.py:364` و `AutoClickerPage.tsx:141` | UI برای هر prepare یک `ac-${Date.now()}` تازه می‌ساخت؛ یک قصدِ منطقی با ID تازه دوباره قابلِ اجرا بود. |
| P0-3 | انتخابگرهای خریدمحور، `.first` و `force` | `execution_strategy_core.py:67`، `execution_strategy_engine.py:399`، `AutoClickerPage` | سمت بررسی نمی‌شد؛ دکمهٔ چندگانه/فرمِ چندگانه و تغییرِ پس از validation به‌طور کامل بسته نبود. |
| P0-4 | preflight رویِ مسیرِ کلیک اعمال نمی‌شد | `api/execution.py:335` | `_risk_gate` فقط وجودِ یک cap را می‌سنجید و `ExecutionService.preflight/dispatch_preflight` صدا زده نمی‌شد. |
| P0-5 | `scheduled` در UI خطا، Abort بدونِ بیدارکردنِ sleep، زمانِ مرورگر | `AutoClickerPage.tsx:160`، `execution_timing.py:325`، `sarkhatiFormStore.ts:88` | وضعیتِ انتظار «شکست» خوانده می‌شد؛ abort تا پایانِ sleep صبر می‌کرد؛ هدف با timezone مرورگر ساخته می‌شد. |
| P0-6 | نبودِ تستِ browser-level با شمارنده | `dev/strategy_guard_v1123.py` | MockDriver همیشه `wait_for=True` برمی‌گرداند؛ رفتارِ واقعیِ کلیک/درخواست اثبات نمی‌شد. |
| P1 | Probe ناقص و timing مبهم | `execution_strategy_engine.py:284` | `form_symbol/open_form` در survey نبود؛ `send` با one-way/RTT اشتباه گرفته می‌شد. |

## ۳. تغییرات و چرایی

### P0-1 — گاردِ catch-all و اثباتِ عدمِ ارسال

- `PlaywrightBrowserDriver.dry_run_guard()` و `MockBrowserDriver.dry_run_guard()` اضافه شد: در dry-run `page.route("**/*")` نصب می‌شود، همهٔ متدهایِ نوشتنی (هر چیزی جز GET/HEAD/OPTIONS/TRACE) abort می‌شوند و فقط خواندن‌ها ادامه می‌یابند. الگویِ کاربر دیگر مرزِ امنیت نیست؛ فقط برایِ طبقه‌بندیِ نمایشی استفاده می‌شود.
- هر نوشتن با `order_paths`/`order_method` طبقه‌بندی می‌شود: `order`, `order_method_mismatch`, `other_write`. اگر نوشتنی «رهاشده» دیده شود یا تعدادِ abort از نوشتن‌ها کمتر باشد، نتیجه `unknown/DRY_RUN_ESCAPE` و قصد قفل می‌شود؛ نه «dry_run موفق».
- `network()` اکنون `writes`, `blocked_writes`, `escaped_writes`, `order_writes`, `other_writes`, `order_method_mismatch` را برمی‌گرداند. یک double-count در `_all_requests` پیدا و رفع شد.
- نتیجه: URL استاندارد، path جایگزین، host جایگزین، method جایگزین، query، redirect/alternate و الگویِ عمداً غلط، همه با endpoint سفارشِ صفر پوشش داده شدند.

### P0-2 — `execution_intent_store.py` پایدار

- جدولِ `execution_intents` در `user.db` (با `BORS_INTENT_DB` برایِ تست) اضافه شد: کلیدِ صریحِ `intent_key` یا fallbackِ `execution_id`، حالت‌های `prepared/scheduled/clicking/submitted/confirmed/rejected/unknown/aborted/dry_run/failed_pre_click/stale`.
- `begin()` چند Strategy را برایِ یک قصد مجاز می‌کند (shadow/benchmark) ولی همان Strategy با execution_id تازه را رد می‌کند. `claim_click()` یک UPDATEِ اتمیک است و فقط یک بار از `prepared/scheduled` به `clicking` می‌رود.
- `UNKNOWN` تا reconcile با همان کلید هر اجرایِ دوباره را مسدود می‌کند. `confirmed` هم همان کلید را قفل نگه می‌دارد؛ قصدِ تازه کلیدِ تازه می‌خواهد.
- `recover_stale()` در startup: `clicking → unknown`، `scheduled/prepared → aborted`؛ هیچ کارِ زمان‌بندی‌شده‌ای پس از restart خودکار اجرا نمی‌شود.
- `mark_prepare_failed()` فقط وقتی prepared_id هنوز bind نشده، حالت را `failed_pre_click` می‌کند؛ پس prepareِ ناموفق با همان کلید و پس از اصلاحِ فرم قابلِ تلاش است، ولی prepareِ موفقِ bind‌شده قفل می‌ماند.
- UI یک `intent_key` پایدار در حافظهٔ صفحه نگه می‌دارد و «قصد تازه» آن را عوض می‌کند.

### P0-3 — فرمِ سمت‌محور و انتخابگرِ یگانه

- `_side_sel()` انتخابگرهایِ `submit_selector_buy/sell` و `open_form_selector_buy/sell` را انتخاب می‌کند. برایِ فروش، نبودِ انتخابگرِ فروش `CONFIG_MISSING` می‌دهد و به دکمهٔ خرید برنمی‌گردد.
- `_verify_form()` اکنون سمت را از `side_selector` یا متن/`aria-label` دکمه اثبات می‌کند؛ نماد/ISIN/قیمت/تعداد را می‌سنجد؛ `count()==1` را برای هر انتخابگر الزام می‌کند؛ و `FORM_NOT_UNIQUE`/`ISIN_MISMATCH`/`SIDE_UNVERIFIED` را پیش از کلیک برمی‌گرداند.
- کلیکِ AutoClicker با `force=False` و بدونِ `.first` انجام می‌شود؛ Playwright strict-mode/actionability فعال است. بازخوانیِ نهایی پس از انتظارِ preclick و پیش از کلیک انجام می‌شود.
- مقدار `submit_text`/`side_text` فقط برایِ Mock است؛ در مرورگر واقعی از `aria-label`/متنِ دکمه خوانده می‌شود.

### P0-4 — اتصال به preflight واقعی

- `ExecutionService.dispatch_preflight()` اضافه شد: `preflight()` + `_check_limits()`، با تبدیلِ خطا به checkِ مسدودکننده.
- `StrategyEngine` یک `preflight_gate` گرفت و `_STRATEGY_ENGINE.preflight_gate = _SERVICE.dispatch_preflight` در API ست می‌شود. گیت فقط در `live_ok` اجرا می‌شود و پیش از arbiter/کلیک است؛ خطا `PREFLIGHT_BLOCKED` با checks است.
- تست‌ها: قدرتِ خرید ناکافی، تعدادِ قابلِ‌فروشِ ناکافی، سقفِ ارزش، gate موفق، و فراخوانیِ مستقیمِ موتور (بدونِ UI) — همه پیش از کلیک مسدود/اجرا شدند.

### P0-5 — زمان‌بندی، Abort و تهران

- `Scheduler.dispatch(..., abort_event=...)`: خوابِ درشت به بازه‌هایِ ۰٫۲۵s شکسته می‌شود و Abort scheduler را بیدار می‌کند. `DispatchTelemetry.aborted` اضافه شد و `StrategyEngine` نتیجهٔ `aborted` را ثبت می‌کند.
- `StrategyEngine.prepare` هدفِ گذشته/منقضی را با `TARGET_IN_PAST` رد می‌کند.
- `TimeSource.from_tehran_local()` اضافه شد؛ API با `target_tehran` رشتهٔ بی‌offset را در `Asia/Tehran` تفسیر می‌کند (نه timezone مرورگر). UI اکنون `target_tehran` می‌فرستد.
- UI `scheduled` را «زمان‌بندی شد» نمایش می‌دهد و برایِ `aborted`/`failed`/`UNKNOWN` پیامِ جدا دارد.
- restart با store پایدار تست شد: scheduled قبلی به aborted می‌رود و کلیکِ خودکار ندارد.

### P1 — Probe و اندازه‌گیری

- `_selector_map` اکنون `form_symbol_selector`، `open_form_selector`، `open_form_selector_buy/sell`، `submit_selector_buy/sell`، `form_selector`، `side_selector` و `isin_selector` را هم به Probe می‌دهد؛ صفحه ساختارِ buttons/inputs را (بدون مقدار) نمایش می‌دهد.
- timings اکنون شاملِ `target_wall_ms`، `click_to_request_ms`، `response_wait_ms` هستند و `one_way_ms`/`rtt_ms` صریحاً `None` می‌مانند؛ هیچ ادعایِ one-way از یک RTT ساخته نشد.
- `p50/p95/p99` همچنان فقط با نمونهٔ کافی محاسبه می‌شوند؛ نمونهٔ محیطِ mock کم است و در گزارش به‌عنوانِ آمارِ محیطِ ساختگی ذکر می‌شود.

## ۴. تست‌هایِ اضافه‌شده و نتیجهٔ واقعی

| تست | نتیجه |
| --- | --- |
| `dev/autoclicker_round14_v1148.py` | **۳۵/۳۵** (dry-run ۷ سناریو، idempotency/UNKNOWN/restart، فرم ۹ سناریو، preflight ۳، زمان/abort/timezone ۵) |
| `dev/autoclicker_browser_round14_v1149.py` | **۱۴/۱۴** browser-level با Playwright واقعی و EasyTraderِ محلیِ instrument‌شده |
| `dev/strategy_guard_v1123.py` | **۵۷/۵۷** |
| `dev/execution_timing_v1.py` | **۳۲/۳۲** |
| `dev/p0_gates_v1118.py` | **۳۳/۳۳** |
| `dev/easytrader_adapter_v1113.py` | **۱۶۳/۱۶۳** |
| `dev/execution_offerings_v1140.py` | **۱۰۰/۱۰۰** |
| `dev/execution_write_contract_v1147.py` | **۳۶/۳۶** |
| `dev/execution_account_sources_v1146.py` | **۲۵/۲۵** |
| frontend مرتبط (`autoclicker-page`, `sarkhati-readiness`, `sarkhati-guided-flow`, `sarkhati-tab`) | **۴۰/۴۰** |
| کلِ frontend (`npx vitest run`) | **۲۰۲ فایل سبز + ۲ فایل skip؛ ۲۰۹۵ تست سبز + ۵ skip؛ RC=0** |
| `npx tsc -b` | **۰ خطا** |
| `npm run build` | **موفق** |
| `dev/run_all_tests.py` (کلِ backend) | **ناتمام** — پس از ۵۶ سوئیت متوقف شد؛ تا آن نقطه ۰ FAIL و ۱ SKIP (fixtureِ `_audit/ra365_ref_bars.json`)؛ به‌دلیلِ تغییرِ `market.db` ادامه نداد. |

### شمارنده‌هایِ browser-level

در `autoclicker_browser_round14_v1149.py` شمارنده‌ها سمتِ سرورِ محلی و صفحهٔ instrument‌شده‌اند:

- `order_hits`: در همهٔ سناریوهایِ dry-run **۰**؛ فقط دو سناریویِ live محلی (پذیرش و timeout) هر کدام **۱** (جمعِ ۲).
- `other_hits`: **۰**؛ `redirect_hits`: **۰**.
- `click_hits`: **۹** (۸ خرید + ۱ فروش) در آخرین اجرا؛ هر سناریو شمارندهٔ خودش را جدا سنجید و هیچ کلیکِ تکراری در یک قصد دیده نشد.
- هیچ درخواستی به endpoint واقعیِ EasyTrader نرفت؛ سرور فقط `127.0.0.1` بود.

## ۵. نتایجِ موضوعی

- **Dry-run:** استاندارد، path، host، method، query، redirect و الگویِ غلط: `order_hits=0`؛ نتیجهٔ استاندارد `dry_run`، مسیرهایِ غیرمنتظره `blocked` و نشتیِ فرضی `unknown`.
- **Idempotency:** دو ID با یک `intent_key` در prepare دوم `DUPLICATE_GUARD`؛ دو Strategy یک قصد فقط یک کلیک؛ UNKNOWN تا reconcile قفل؛ confirmed همان کلید را قفل نگه می‌دارد؛ restart کارِ scheduled را خودکار اجرا نمی‌کند.
- **Preflight:** BP ناکافی، sellable ناکافی، سقفِ ارزش و gateِ خاموش پیش از کلیک مسدود؛ gate موفق یک کلیک و نتیجهٔ unknown (بدونِ پاسخ) داد.
- **Scheduler/Abort:** هدفِ آینده اجرا شد و یک کلیک؛ Abort پیش از مهلت نتیجهٔ `aborted` و صفر کلیک؛ هدفِ گذشته `TARGET_IN_PAST`.
- **Timezone:** `2026-10-22T08:45:00` به `2026-10-22T08:45:00.000+03:30` تفسیر شد؛ targetSource=`asia/tehran`.
- **Form:** خرید/فروش، نماد/ISIN/قیمت/تعداد، دکمهٔ غیرفعال، چند دکمه و تغییرِ قیمت پس از validation، همه پیش از کلیک مسدود/تفکیک شدند.

## ۶. اندازه‌گیریِ زمان و محدودیتِ آماری

- `click_to_request_ms` در dry-run و liveِ محلی ثبت شد؛ `one_way_ms` و `rtt_ms` صریحاً `None` هستند.
- `response_wait_ms` فقط انتظارِ پاسخ پس از request است، نهRTT کامل.
- تعدادِ نمونه‌ها در محیطِ mock کم است (< ۵ در برخی فازها)؛ p95/p99 به‌عنوانِ آمارِ معنادارِ محیطِ واقعی گزارش نمی‌شود. هیچ عددِ سرعت/دقتِ میلی‌ثانیه‌ای ادعا نمی‌شود.

## ۷. مواردِ باقی‌مانده و اثبات‌نشده

1. **انتخابگرهایِ فروشِ EasyTraderِ واقعی** در UI زنده دیده نشده‌اند؛ `submit_selector_sell`/`open_form_selector_sell` عمداً خالی‌اند و مالک باید مقدارِ دیده‌شده را تنظیم کند، وگرنه فروش `CONFIG_MISSING` می‌گیرد.
2. **صفحهٔ readiness** همچنان `contract_operational=False` و `owner_approved=False` را ثابت نگه می‌دارد؛ این مقدارها عمداً true نشدند و live_ready باید بسته بماند.
3. **دور زدنِ gate از طریقِ فراخوانیِ مستقیمِ `BrowserStrategyBase.trigger`** در کدِ تولیدی وجود ندارد؛ اما این کلاس در سطحِ پایین‌تر gate ندارد. اگر روزی مسیرِ تازه‌ای آن را مستقیم صدا بزند، باید gate را خودش صدا بزند.
4. **دو تبِ UI** با دو `intent_key` مستقل می‌توانند دو قصدِ هم‌مقدار بسازند؛ dedupe فقط با کلیدِ مشترک کار می‌کند. یک قفلِ حساب‌محور/فرم‌محورِ سراسری برایِ این حالت وجود ندارد.
5. **زمان‌بندیِ live پایدار نیست**: triggerِ زمان‌بندی‌شده در حافظه است و با restart به aborted منتقل می‌شود؛ عمداً هیچ اجرایِ خودکارِ پس از restart وجود ندارد.
6. **تستِ واقعیِ EasyTrader** انجام نشد؛ browser-level فقط mock محلی است.
7. **تغییرِ دو دیتابیسِ عملیاتی (حادثهٔ داده):**
   - `user.db` هنگامِ اجرایِ گاردهایِ مرتبط پیش از ایزوله‌سازی تغییر کرد: fingerprint از `381736f1…c74500e` به `fbffd6ef…3fe4ff8` (mtime 21:33).
   - `market.db` در جریانِ suiteِ کاملِ backend تغییر کرد: fingerprint از `5a9117aa…135bea3` به `fd688edb…790b73dc` (mtime 21:44). `market.db-wal`/`shm` پس از توقف دیده شد؛ حجمِ فایل تغییر نکرد، ولی تغییرِ صفحه‌ها با هش تأیید می‌شود.
   - علتِ ریشه‌ای: `WORK_DIR` در حالتِ dev ریشهٔ ریپو است؛ `BORS_USER_DB` فقط `user.db` را جدا کرد و `market.db` همچنان همان فایلِ عملیاتیِ worktree بود. suite در ۵۶ سوئیت متوقف شد تا نوشتنِ بیشتر رخ ندهد.
   - هیچ نسخهٔ پشتیبانِ پیش‌از‌suite از `market.db` در این worktree نبود و هیچ بازیابی/بازنویسیِ خودکار انجام نشد. تصمیمِ بازیابی (مثلاً از یک کپیِ سالمِ مالک) به عهدهٔ مالک است؛ بازنویسیِ کورکورانه انجام نمی‌شود.
   - برایِ هر اجرایِ کاملِ بعدی باید **کلِ worktree** یا دست‌کم `market.db` هم به کپیِ ایزوله منتقل شود، نه فقط `user.db`.
8. **فایل‌هایِ untrackedِ قدیمیِ `_audit/round6..9`** دست‌نخورده‌اند و در commitهایِ این راند وارد نمی‌شوند.

## ۸. commit و فایل‌هایِ تغییرکرده

- commit اصلی: `3f59be54` — `feat(autoclicker): راند ۱۴ — گاردِ dry-run، idempotency پایدار و preflight مسیرِ کلیک`
- commitِ تکمیلیِ گزارش/اعدادِ نهایی، پس از پایانِ suiteِ کامل (در صورتِ نیاز) ثبت می‌شود.

- `execution_intent_store.py` (جدید)
- `execution_browser.py`
- `execution_strategy_engine.py`
- `execution_strategy_core.py`
- `execution_timing.py`
- `execution_service.py`
- `api/execution.py`
- `bors_config.py` (فقط `BORS_USER_DB` برایِ ایزوله‌سازیِ تست)
- `frontend/src/features/portfolio/routes/AutoClickerPage.tsx`
- `frontend/src/__tests__/autoclicker-page.spec.tsx`
- `dev/autoclicker_round14_v1148.py` (جدید)
- `dev/autoclicker_browser_round14_v1149.py` (جدید)
- `dev/run_all_tests.py` (ثبتِ دو گاردِ تازه)
- `dev/strategy_guard_v1123.py` (fixtureِ مسیرِ Mock)
- `fts_terminal.spec` (`execution_intent_store` در hiddenimports)

## ۹. جمع‌بندیِ صادقانه

**پیاده‌سازی و تست شده‌اند:** گاردِ dry-run مستقل از الگو، idempotency پایدار تا UNKNOWN/restart، فرمِ سمت‌محور و یگانه، preflight واقعی رویِ مسیرِ کلیک، scheduled/abort/تهران، و تستِ browser-level با شمارنده.

**فقط پیاده‌سازی شده و در محیطِ واقعی اثبات نشده:** انتخابگرهایِ فروشِ EasyTrader، مسیرِ host/CDPِ زنده، و اندازه‌گیریِ latency در محیطِ مالک.

**هنوز حل نشده/باز:** قفلِ سراسریِ چندتب، زمان‌بندیِ live پایدار، readinessِ واقعیِ قرارداد/مالک، و **حادثهٔ تغییرِ `user.db` و `market.db`** که جزئیات و هش‌هایش در بند ۷ آمده و تصمیمِ بازیابی با مالک است. suiteِ کاملِ backend به همین دلیل ناتمام ماند؛ گاردهایِ مرتبطِ اجرایی همه جداگانه سبز شدند.

**هیچ سفارشِ واقعی، هیچ credential و هیچ کپیِ کدی از مراجع انجام نشد.**
