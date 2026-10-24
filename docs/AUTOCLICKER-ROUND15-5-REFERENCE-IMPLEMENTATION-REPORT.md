# Round 15.5 — Reference-to-Product Implementation

> تاریخ: ۲۰۲۶-۱۰-۲۱ | شاخه: `mission/sarkhati-round15-5-reference-implementation-2026-10-21` | مبنا: `6e58be07` (Round 15) | commit: `0afcc234`
> وضعیت: `live_enabled=false` · `live_ready=false` · هیچ سفارش/کلیکِ واقعی روی کارگزاری انجام نشد.

## ۱) وضعیت واقعی Git و دامنه

Round 15 روی `6e58be07` با گزارشِ closeout و suiteِ کاملِ ایزوله بسته شده بود. این راند از همان HEAD شروع شد، تغییراتِ Round 15 را حفظ کرد، و فقط قابلیت‌های محصولِ AutoClicker را تکمیل کرد. گزارش‌های Round 13/14/15 بازنویسی نشدند.

هدف این راند، تبدیلِ قابلیت‌های مفیدِ شش مرجع به کدِ محصول بود؛ نه تحقیقِ مجدد، نه صرفاً تستِ بیشتر.

## ۲) ماتریسِ شش مرجع → محصول

| مرجع | فایل/تابعِ شاهد | قابلیت | نوعِ استفاده | مقصد در BorsTerminal | تست |
| --- | --- | --- | --- | --- | --- |
| `m-fazel/Sarkhati` | `src/easy_trader.rs:send_order`, `src/time_reference.rs`, `src/calibration.rs` | مسیرِ API، clock/reference، rate؛ **batch repeat پذیرفته نشد** | adaptation (نه reuse) | `execution_easytrader.py`, `execution_write_contract.py`, `execution_timing.py`, `DirectApiStrategy`؛ UI مسیر API | strategy ۵۷/۵۷، timing ۳۲/۳۲، API mode در frontend ۶/۶ |
| `estakhri/Sarkhati` | `src/mofid.rs:MofidOrderData/send_order`, `config_mofid.example.json` | پروتکلِ جدا Mofid/Titan، payloadِ تخت، هدرها | **port** با جایگزینیِ منطقِ ناامن | **`execution_mofid.py` → `MofidAdapter`/`build_payload`؛ ثبت در `ALLOWED_ADAPTERS` و `DirectApiStrategy`** | `mofid_adapter_v1163.py` ۱۲/۱۲ |
| `HosseinSayyedMousavi/Sarkhati` | `Sarkhati.py:Transaction` (فرم/جدول/toast) | شناسایی فرم، خواندن نتیجه | behavioral replacement (نه کپیِ XPath/retry) | `execution_strategy_engine._side_sel/_verify_form`, `AutoClickerStrategy`, `UNKNOWN`/reconcile | fast ۴۲/۴۲، browser ۱۵/۱۵ |
| `sajadghandehari/mofid-autotrader` | `manage.py:122-141` | اجرای زمان‌بندی‌شده و پنجرهٔ بازار | replace (۱۲/۲۴ و ۱۵ کلیک رد شد) | `execution_timing.Scheduler`, `TimeSource`, UI هدفِ Tehran | fast/abort/timezone، timing ۳۲/۳۲ |
| `RezaMahdaviiDev/mofid` | `src/brokerages/easy/api/order.ts:getOrders/getQueuePosition/monitorOrder` | پایشِ فهرست/صف و تفکیک API/DOM | adaptation؛ **fallbackِ API→DOM ممنوع** | `EasyTraderAdapter.get_orders/get_queue_position`, `ExecutionService.queue`, پنلِ «نتیجه و پایش سفارش» | strategy ۵۷/۵۷، UI monitor ۶/۶ |
| `amirali110/Sarkhati-Bourse` | `mainwindow.cpp:116-162` (QTimer ۱ms، تایمرِ هدف) | ایدهٔ واکنشِ سریع؛ تایمرِ UI معیوب | idea only (کد قابلِ‌استفاده نبود) | `execution_timing.Scheduler` (monotonic/spin)؛ بدونِ تایمرِ UI | timing ۳۲/۳۲ |

**هیچ کدی از مراجع کپی نشد** (مجوزِ قطعی وجود ندارد). در Mofid، شکلِ سیم و نامِ فیلدها port شد؛ در بقیه رفتار با پیاده‌سازیِ مستقل جایگزین شد. batch/retry/۱۵کلیک عمداً وارد نشدند.

## ۳) مسیرِ محصول

`AutoClicker page → Intent Manager → Preflight → Clock/Scheduler → API یا Browser Adapter → Confirmation/Reconciliation → Order/Queue Monitor`

- **انتخابِ مسیر:** صفحهٔ `/autoclicker` دو دکمهٔ «مرورگر» و «API» دارد. مسیرِ API از `DirectApiStrategy` و قراردادِ adapter فعال استفاده می‌کند؛ مسیرِ مرورگر همان `AutoClicker` است. انتخاب پیش از اقدام روشن است.
- **intent مشترک:** `intent_key` در localStorage با امضایِ فرم به اشتراک گذاشته می‌شود؛ دو تب با همان فرم یک intent می‌بینند و «قصد تازه» کلید را می‌چرخاند. `IntentStore` در SQLite قفلِ نهاییِ کلیک/ارسال است.
- **preflight مشترک:** هر دو مسیر از `StrategyEngine.preflight_gate`/`ExecutionService.dispatch_preflight` عبور می‌کنند؛ مسیرِ مرورگر و API یک دروازهٔ ریسک دارند.
- **زمان:** `target_tehran` در backend به `Asia/Tehran` تفسیر می‌شود؛ `Scheduler` روی monotonic کار می‌کند و Abort قابلِ‌بیدارکردن است.
- **نتیجه و پایش:** پنلِ «نتیجه و پایش سفارش» وضعیت، `broker_order_id`، `UNKNOWN` و `queue_position` را نشان می‌دهد؛ اگر منبعِ صف/شناسه معتبر نباشد «در دسترس نیست» می‌گوید، نه صفر.
- **مسیر Mofid:** `MofidAdapter` با payloadِ تختِ `orderSide/price/quantity/symbolIsin/validityType/validityDate/orderFrom` و هدرهایِ `Origin/Referer/x-appname`؛ انتخاب با `BORS_EXECUTION_ADAPTER=mofid` و توکنِ env؛ 2xx ⇒ UNKNOWN (نه acceptance)، بدونِ retry، read-back/balance ندارد و preflight را می‌بندد.

## ۴) تغییراتِ کد

- `execution_mofid.py` (جدید): adapter مستقل، `build_payload`، `MofidAdapter`، تستِ قرارداد. `2xx` فقط ثبتِ درخواست است؛ `get_orders/get_queue_position` عمداً UNSUPPORTED؛ token/cookie در repr/لاگ نمی‌نشیند.
- `execution_strategy_engine.py`: `DirectApiStrategy` برای adapter مفید، payloadِ Mofid را از `execution_mofid.build_payload` می‌سازد؛ payloadِ EasyTrader دست‌نخورده ماند.
- `api/execution.py`: `mofid` در `ALLOWED_ADAPTERS`، انتخابِ adapter، نقشهٔ `symbolIsin`، و پیامِ وضعیتِ «Mofid؛ read-back/balance تأیید نشده».
- `frontend/.../AutoClickerPage.tsx`: انتخابِ مسیر API/مرورگر، ارسالِ `strategy` درست، پنلِ نتیجه/پایش، نمایشِ `unknown/order-id/queue` و `next_action` readiness.
- `frontend/.../orderClient.ts` و تست: متدهایِ intent/order monitor؛ تستِ مسیر API و intent مشترک.
- `fts_terminal.spec`: `execution_mofid` در hiddenimports؛ `dev/run_all_tests.py`: gاردِ Mofid.

## ۵) تست‌ها و نتایج

| تست | نتیجه |
| --- | --- |
| `dev/mofid_adapter_v1163.py` | **۱۲/۱۲** — payload تخت/فروش، 2xx⇒UNKNOWN، 401/5xx/timeout، بدونِ retry، token در log نیست، preflightِ بی‌داده fail-closed |
| `dev/autoclicker_round14_v1148.py` | **۴۲/۴۲** |
| `dev/autoclicker_browser_round14_v1149.py` | **۱۵/۱۵**؛ dry-run endpoint=۰، دو engine/تب یک کلیک |
| `dev/strategy_guard_v1123.py` | **۵۷/۵۷** |
| `dev/execution_timing_v1.py` | **۳۲/۳۲** |
| `dev/db_isolation_guard_v1160.py` | **۶/۶** |
| `dev/readiness_round15_v1162.py` | **۷/۷** |
| frontend مرتبط (`autoclicker-page`) | **۶/۶** (شاملِ مسیر API و intent مشترک) |
| کلِ frontend | **۲۰۲ فایل سبز + ۲ skip؛ ۲۰۹۷ تست سبز + ۵ skip** |
| `tsc -b` / `npm run build` | ۰ خطا / موفق |
| کلِ backend (`run_all_tests.py`) | **۱۴۴ counted / ۳۱ silent / ۲ skip / ۰ FAIL؛ `ALL SUITES PASSED`؛ rc=0** |
| skipها | Phase4 (`_audit/ra365_ref_bars.json`)، R1/R2 (`market.db.lzma`) — fixture در clone نبود |
| hash دیتابیس عملیاتی | بدونِ تغییر: `fd688edb…790b73dc` و `fbffd6ef…3fe4ff8` |

skip/خطاهایِ fixture و timeout به‌صورتِ جداگانه در لاگِ suite ثبت می‌شوند و پنهان نمی‌شوند.

## ۶) سه دستهٔ تحویل

### ۱. تکمیل‌شده و تست‌شده
- مسیرِ API و مرورگر در یک صفحه، با intent/preflight مشترک.
- آداپتورِ Mofid/Titan با قراردادِ مستقل و تستِ ۱۲/۱۲.
- پنلِ نتیجه/پایشِ سفارش؛ نمایشِ صریحِ صف/شناسهٔ ناموجود.
- idempotency چندتب/دوباره، UNKNOWN و restart (Round 15).
- ابزارِ زمان/Tehran و Abort.
- DB isolation و suiteِ کاملِ Round 15؛ این راند روی همان زیرساخت اجرا می‌شود.

### ۲. پیاده‌سازی‌شده، نیازمند تأیید با کارگزاری/UI واقعی
- `MofidAdapter` زنده: توکن/کوکی و balance/read-back واقعی در دسترس نیست؛ preflight عمداً می‌بندد.
- selectorهایِ واقعیِ خرید/فروش EasyTrader و سیگنالِ تأییدِ واقعی.
- دادهٔ واقعیِ صف/فروشگاهِ سفارش برای مسیر Strategy.
- نمایش/تأییدِ نهایی در UI با نشستِ واقعیِ مالک.

### ۳. مانع‌های واقعی و شاهدِ لازم
- **قراردادِ عملیاتی EasyTrader:** `operationally_verified=false`؛ شاهدِ لازم یک نشستِ مجاز و پاسخِ واقعی.
- **Mofid:** مسیرِ account/read-back/balance و مجوزِ استفاده از API کارگزاری؛ شاهدِ لازم مستندات/نشستِ رسمی.
- **مجوز مالک:** `owner_approval` پیش‌فرض false؛ یک تأییدِ صریحِ قابلِ‌ردیابی و بازبینیِ انسانی لازم است.
- **selectorهای فروش/فرم واقعی:** `NO_ACCESS` در diagnostic این ماشین؛ شاهدِ لازم DOMِ واقعیِ EasyTrader.
- **زمان‌بندیِ liveِ پایدار:** عمداً پیاده نشده؛ شاهد/مجوزِ روشن برای اجرای خودکار پس از restart لازم است.

**تفکیک:** mock/مسیرِ محصول اکنون قابلِ‌تست است؛ رابطِ واقعی و مجوزِ ارسال هنوز تأیید نشده‌اند. این سه یکی نیستند.

## ۷) commit و artifacts

- commit اصلی: `0afcc234` — `feat(autoclicker): Round 15.5 — Mofid adapter و مسیر API/مرورگر`.
- لاگِ suite نهایی: `C:/Users/PCMOD/AppData/Local/Temp/bors_suite_round15_39008.log` (۱۴۴ counted / ۳۱ silent / ۲ skip / ۰ FAIL).
- `live_enabled=false` و `live_ready=false` در طولِ راند حفظ شدند؛ هیچ سفارش/کلیکِ واقعی انجام نشد.
