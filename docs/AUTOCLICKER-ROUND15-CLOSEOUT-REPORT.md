# Round 15 — AutoClicker Project Closeout

> تاریخ: ۲۰۲۶-۱۰-۲۱ | شاخه: `mission/sarkhati-round15-closeout-2026-10-21` | مبنا: `7f95c6a4` (Round 14) | commit: `e88c0f88`
> وضعیتِ اجرای زنده: `live_enabled=false` · `live_ready=false` · هیچ سفارش/کلیکِ واقعی روی کارگزاری انجام نشد.

## ۰) حکمِ نهایی

**AutoClicker از نظرِ فنی برایِ محیطِ mock و قضاوتِ آمادگی آماده است، اما برایِ اجرای واقعی هنوز NO-GO است.** دلیلِ اصلی، نه کدِ mock است و نه گاردها: انتخابگرهایِ فرمِ واقعی EasyTrader (خصوصاً فروش) با نشستِ زندهٔ این ماشین قابلِ مشاهده نبودند، قراردادِ نوشتن هنوز `operationally_verified=false` است، و مجوزِ صریحِ مالک برایِ سفارشِ واقعی ثبت نشده است. جزئیات در جدولِ GO/NO-GO بند ۹.

## ۱) مبنا و دامنه

Round 15 از `7f95c6a4` شروع شد و فقط blockerهایِ اعلام‌شده را بست: containment دیتابیس، idempotency چندتب، selectorهایِ واقعی، scheduler پس از restart، readiness واقعی، و E2E mock. تحقیقِ مجددِ مراجع، بازطراحی UI، قابلیتِ تازه، و تغییرِ فرمول‌های مالی انجام نشد.

## ۲) Database containment

### ۲.۱ snapshot قبل از هر تست

پیش از هر اجرایِ تست، از `market.db` و `user.db` با SQLite backup (سازگار با WAL) در مسیرِ بیرونِ worktree snapshot گرفته شد:

| فایل | hash فعلی | snapshot hash | integrity_check |
| --- | --- | --- | --- |
| `market.db` | `fd688edbfe07e125…790b73dc` | `7fe8765874866407…62340d` | `ok` |
| `user.db` | `fbffd6eff0a9bd2f…3fe4ff8` | `86c7670bb627b7ec…61620a` | `ok` |

- مسیر: `C:/Users/PCMOD/Desktop/_bors-db-snapshots/round15_2026-10-21/`
- manifest شاملِ اندازه، mtime، وضعیتِ WAL/SHM و countِ جداولِ مهم (market: instruments 6179، market_watch 6186، daily_prices 138782، tape_history 149753، financial_statements 8723).
- **هیچ restore، بازنویسی، حذف یا بازسازی انجام نشد.** چون نسخهٔ سالمِ قبل از Round 14 در دسترس نیست، مقایسه/بازیابیِ تاریخی ممکن نیست؛ snapshot فقط وضعیتِ فعلی را برایِ داوری و rollback حفظ می‌کند.

### ۲.۲ اصلاحِ resolver و runner

- `bors_config` حالا `BORS_DATA_DIR` را برایِ `WORK_DIR` می‌پذیرد و `DB_PATH` را در حالتِ ایزوله فقط از همان مسیر می‌سازد؛ fallbackهایِ `_SRC_DIR`/کنارِ EXE در این حالت بسته‌اند.
- در حالتِ `BORS_TEST_ISOLATION=1`: وجودِ marker `.bors_test_isolation` الزامی است و مسیرِ `BORS_OPERATIONAL_ROOT` صریحاً رد می‌شود.
- `dev/run_all_tests.py` خودش یک clone کامل از worktree + cloneِ SQLiteیِ `market.db` در Temp می‌سازد، marker می‌گذارد، همهٔ زیرفرآیندها را با `BORS_DATA_DIR`/`BORS_USER_DB`/`BORS_INTENT_DB` همان clone اجرا می‌کند و hashِ `market.db`/`user.db` عملیاتی را قبل/بعد می‌سنجد. لاگِ هر اجرا بیرونِ clone ذخیره می‌شود.
- `dev/db_isolation_guard_v1160.py`: **۶/۶** — resolver، ردِ operational worktree (با و بدونِ marker)، ارث‌بریِ subprocess، و اثباتِ اینکه نوشتن در clone هشِ `market.db` عملیاتی را عوض نمی‌کند.
- suite کاملِ backend روی clone (با git مستقل و fixtureهایِ لازم) به انتها رسید: **۱۴۴ سوئیتِ شمارش‌شده، ۳۰ فقط-exit-code، ۲ skip با علتِ fixture، ۰ FAIL**؛ hashهایِ `market.db` و `user.db` عملیاتی قبل/بعد یکسان ماندند.

> وضعیتِ فعلی: snapshot سالم است؛ تغییرِ قبلیِ `market.db`/`user.db` جبران/بازگردانی نشده و تصمیمِ بازیابی به مالک واگذار شده است.

## ۳) Global idempotency و چند تب

- `execution_intent_store.py` (Round 14) کلیدِ قصد را در `user.db` نگه می‌دارد؛ `claim_click` یک `UPDATE` اتمیک با `BEGIN IMMEDIATE` است. اکنون UI کلید را در `localStorage` با امضایِ فرم (نماد/سمت/قیمت/تعداد/هدف) به اشتراک می‌گذارد؛ دو تب با همان فرم همان `intent_key` را می‌گیرند و «قصد تازه» کلید را عوض می‌کند. این deduplication بر مبنایِ هشِ حدسیِ قیمت/نماد در backend نیست؛ کلیدِ صریح و مشترک است.
- API: `GET /api/execution/strategies/intents/{key}` و `POST .../abort` اضافه شد؛ Abort از engine/تبِ دیگر با intent_key کار می‌کند.
- تست‌ها: دو engine/تب با یک intent_key در یک fixture و در Playwright واقعی؛ شمارندهٔ کلیکِ دوم صفر.

## ۴) Selectorهایِ فرمِ EasyTrader

- ابزارِ فقط‌خواندنیِ `dev/easytrader_selector_probe_v1161.py` ساخته شد. در این ماشین **هیچ browser-host/CDP زنده‌ای** وجود ندارد (`EB.active_cdp_url()` خالی است)، بنابراین خروجیِ آن `NO_ACCESS` است و هیچ selector را `VERIFIED` اعلام نمی‌کند.
- candidateهایی که از کدِ مرجعِ سوم‌شخص دیده شدند (نه از DOM واقعیِ این نشست): `order-sell-btn`، `oms-order-form-submit-button-sell`، `order-form-input-price/quantity`، `order-form-header`. این‌ها فقط diagnostic هستند و به‌عنوانِ پیش‌فرضِ تولیدیِ تأییدشده استفاده نشدند.
- خرید همچنان از selectorهایِ مشاهده‌شدهٔ Round 11A (`button[aria-label='ارسال خرید']`, `button.order-buy-btn`, `#price`, `#quantity`) استفاده می‌کند؛ در این راند دوباره رویِ فرمِ واقعی تأیید نشد.
- **نتیجه:** Buy = تأییدشده در راندهایِ پیشین ولی re-verify نشده؛ Sell = NO-GO/UNVERIFIED تا نشستِ واقعی و مشاهدهٔ read-only.

## ۵) Scheduler و restart

- target، intent_key و state در `execution_intents` پایدارند. `recover_stale` پس از restart:
  - `clicking → unknown` (ممکن است کلیک شده باشد)
  - `scheduled/prepared` با هدفِ آینده → `needs_review`
  - `scheduled` با هدفِ منقضی → `missed`
- هیچ intentِ زمان‌بندی‌شده‌ای پس از restart خودکار کلیک نمی‌شود. `needs_review`/`missed` تا بررسیِ صریح مسدودند.
- Abort با intent_key از تبِ دیگر کار می‌کند؛ دو engine/تب فقط یک claimِ کلیک می‌گیرند.
- **محدودیتِ صریح:** اجرای خودکارِ live پس از restart پیاده‌سازی نشد و طبقِ مأموریت ممنوع است. schedulingِ liveِ پایدار برایِ اجرایِ خودکار بدونِ تأییدِ مالک، blocker باقی است.

## ۶) Readiness واقعی

- `execution_owner_approval.py` اضافه شد: جدولِ `execution_owner_approval`، پیش‌فرض `approved=false`، تأیید فقط با عبارتِ صریحِ `BORS_OWNER_APPROVAL_PHRASE` و ثبتِ زمان؛ `GET` فقط‌خواندنی است و جدول نمی‌سازد.
- `contract_operational` اکنون از `execution_write_contract.contract_report()["operationally_verified"]` می‌آید (فعلاً false)؛ `lifecycle_tests`/`full_gate` از فایل‌هایِ نتیجهٔ ماندگار خوانده می‌شوند و نبودشان `None/NOT_RUN` است، نه true.
- API `owner-approval` برایِ ثبت/ابطالِ صریح؛ readiness هر گیت `status/detail/action/source` دارد و UI `next_action` و مانع‌ها را نشان می‌دهد.
- تستِ `dev/readiness_round15_v1162.py`: **۷/۷** — تغییرِ یک گیتِ واقعی حکم را برمی‌گرداند و هیچ‌کدام خودکار true نمی‌شود.
- `live_ready` همچنان false است.

## ۷) E2E mock

`dev/autoclicker_round14_v1148.py` مسیرِ production را در mock اجرا می‌کند: `prepare intent → validate form → claim → click → result → intent state`؛ نتیجه: `prepared → dry_run`، یک کلیک، صفر درخواستِ سفارش. `dev/autoclicker_browser_round14_v1149.py` همان مسیر را با Playwright و صفحهٔ EasyTraderِ محلی در خرید/فروش/فرمِ چندگانه/دکمهٔ غیرفعال/تغییرِ فرم/scheduled/abort/دو تب پوشش می‌دهد.

## ۸) نتایجِ تست

| تست | نتیجه |
| --- | --- |
| `dev/db_isolation_guard_v1160.py` | ۶/۶ |
| `dev/readiness_round15_v1162.py` | ۷/۷ |
| `dev/autoclicker_round14_v1148.py` | ۴۲/۴۲ |
| `dev/autoclicker_browser_round14_v1149.py` | ۱۵/۱۵ |
| `dev/strategy_guard_v1123.py` | ۵۷/۵۷ |
| `dev/execution_timing_v1.py` | ۳۲/۳۲ |
| `dev/p0_gates_v1118.py` | ۳۳/۳۳ |
| `dev/easytrader_adapter_v1113.py` | ۱۶۳/۱۶۳ |
| `dev/execution_offerings_v1140.py` | ۱۰۰/۱۰۰ |
| `dev/execution_write_contract_v1147.py` | ۳۶/۳۶ |
| `dev/execution_account_sources_v1146.py` | ۲۵/۲۵ |
| frontend مرتبط | ۴۰/۴۰ |
| کلِ frontend | ۲۰۲ فایل سبز + ۲ skip؛ ۲۰۹۶ تست سبز + ۵ skip |
| `tsc -b` / `npm run build` | ۰ خطا / موفق |
| کلِ backend (`run_all_tests.py`) | **۱۴۴ counted / ۳۰ silent / ۲ skip / ۰ FAIL؛ rc=0** (`ALL SUITES PASSED`) |
| skipها | Phase4 (fixture `_audit/ra365_ref_bars.json`) و R1/R2 (fixture `market.db.lzma`) |
| hashِ دیتابیس عملیاتی در پایان | **بدونِ تغییر**: `market.db=fd688edb…790b73dc`، `user.db=fbffd6ef…3fe4ff8` |

## ۹) GO/NO-GO

| ردیف | حکم | شاهد | blocker باقی‌مانده |
| --- | --- | --- | --- |
| Database isolation | **GO** | snapshot + guard ۶/۶ + runner clone + hash unchanged | هیچ |
| Full backend suite | **GO** | runner به انتهای طبیعی رسید: ۱۴۴ counted / ۳۰ silent / ۲ skip / ۰ FAIL | دو fixture در clone موجود نبود؛ skip ثبت شد |
| Buy selector | **PARTIAL** | selectorهایِ Round 11A و mock | re-verify رویِ DOM واقعی |
| Sell selector | **NO-GO** | `NO_ACCESS` در diagnostic؛ candidateهایِ مرجع | نشستِ واقعی EasyTrader و مشاهدهٔ read-only |
| Global idempotency | **GO** | storeِ SQLite + ۴۲/۴۲ + ۱۵/۱۵ + دو تب | هیچ |
| Scheduler recovery | **GO برایِ ایمنی؛ NO-GO برایِ auto-live** | needs_review/missed/unknown + abort | اجرایِ خودکارِ پایدارِ live مجاز/پیاده‌نشده |
| Actual readiness gates | **GO برایِ مکانیزم؛ NO-GO برایِ live** | owner store + contract source + ۷/۷ | contract operational + owner approval + lifecycle/full gate |
| End-to-end mock | **GO** | E2E + browser ۱۵/۱۵ | real EasyTrader E2E |

## ۱۰) فایل‌ها و commitها

- جدید: `execution_owner_approval.py`، `dev/db_isolation_guard_v1160.py`، `dev/readiness_round15_v1162.py`، `dev/easytrader_selector_probe_v1161.py`
- تغییر: `bors_config.py`، `dev/run_all_tests.py`، `execution_intent_store.py`، `execution_strategy_engine.py`، `api/execution.py`، `execution_readiness.py`، `fts_terminal.spec`، `frontend/.../AutoClickerPage.tsx`، `orderClient.ts`، `autoclicker-page.spec.tsx`، `autoclicker_round14_v1148.py`، `autoclicker_browser_round14_v1149.py`
- commit: `e88c0f88` — `feat(autoclicker): راند ۱۵ — containment دیتابیس، idempotency چندتب و readiness واقعی`
- لاگِ suite نهایی: `C:/Users/PCMOD/AppData/Local/Temp/bors_suite_round15_39148.log` (۱۴۴ counted / ۳۰ silent / ۲ skip / ۰ FAIL).
- `dev/test_portable_v1.py` هم برایِ پاک‌کردنِ overrideهایِ ایزوله در probe اصلاح شد؛ این تغییر فقط محیطِ همان تست را جدا می‌کند.

**تفکیکِ سه چیز:** تستِ mock سبز است؛ رابطِ واقعی EasyTrader برایِ فروش تأیید نشده؛ و اجازهٔ ارسالِ زنده وجود ندارد. این سه یکی نیستند.
