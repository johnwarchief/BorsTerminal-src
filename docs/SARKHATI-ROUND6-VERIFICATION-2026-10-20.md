# Round 6 — اعتبارسنجی مالک‌محور، QA بصری و دروازهٔ Live (۲۰۲۶-۱۰-۲۰)

شاخه: `mission/multi-strategy-2026-10-20`
HEAD شروع: `85f7f2c38db17157766c6a675d9c1088b9aadbca` (Round 5)
وضعیت: **`live_ready=false`**؛ هیچ سفارش واقعی، هیچ POST ثبت سفارش، هیچ تخصیص
واقعی و هیچ انتشار/نسخه‌ای انجام نشد. همهٔ اعداد این سند از fixtureهای
Mock/ایزوله یا محاسبهٔ محلی‌اند، نه دادهٔ کارگزاری.

## ۱) وضعیت Git

| مورد | مقدار |
| --- | --- |
| شاخه | `mission/multi-strategy-2026-10-20` |
| HEAD شروع | `85f7f2c38db17157766c6a675d9c1088b9aadbca` |
| working tree شروع | پاک |
| `main` | دست‌نخورده |
| push/merge/tag/release | انجام نشد |
| کامیت کد/تست | `0e673e33` |
| HEAD پایان | این سند در آخرین کامیتِ شاخه است؛ SHA کد در بالا |

## ۲) ممیزی Round 5 — ایرادهای واقعی که بسته شدند

ممیزی فقط خواندنِ کد نبود؛ مسیر اجرا، API، SQLite و UI اجرا شد. این ایرادها
پیدا و در همین Round اصلاح شدند:

| # | ایراد | اثر | اصلاح | آزمون |
| --- | --- | --- | --- | --- |
| ۱ | `VERIFIED` بدون `source_url` معتبر ممکن بود | دادهٔ بی‌نشانی به‌عنوان تأییدشده | `upsert` نشانی http(s)، هر دو timestamp و نسبت `data_as_of ≤ verified_at` را الزام می‌کند | provenance checks |
| ۲ | زمان تأیید/دادهٔ آینده پذیرفته می‌شد | دادهٔ کهنه/جعل‌شده می‌توانست تازه دیده شود | ردِ timestamp آینده و ردِ دادهٔ آینده در Preflight (با تلورانس ۱s برای skew همان فرایند) | future-data checks |
| ۳ | قیمت/تعداد منفی یا NaN می‌توانست مبلغ منفی بسازد | احتمال دورزدن سقف بودجه با رزرو منفی | `price>0`، `quantity>0`، عدد متناهی، و ردِ NaN/Inf در Preflight و `plan` | price/qty checks |
| ۴ | کارمزد منفی یا ≥۱۰۰٪ پذیرفته می‌شد | کم‌برآورد هزینهٔ سفارش | `0 ≤ fee_rate < 1` و منبع کارمزد | fee checks |
| ۵ | کاهش سقف بودجه زیرِ رزروهای فعال ممکن بود | نقض invariant «جمع رزرو ≤ سقف» | `set_capital` داخل تراکنش، رزرو فعال را می‌خواند و `BUDGET_BELOW_RESERVED` می‌دهد | budget-below-reserved |
| ۶ | `plan` سقف را بیرون از تراکنش می‌خواند | race با تغییر هم‌زمان تنظیمات | خواندن `capital_settings` داخل `BEGIN IMMEDIATE` | concurrent plan |
| ۷ | اولویت `0` با `or` به ۱۰۰ تبدیل می‌شد | ترتیب تخصیص اشتباه | lookup صریح با `is None` | priority-zero |
| ۸ | `UNKNOWN_HOLD → RESERVED` مجاز بود | «نامعلوم» دوباره قابل اقدام می‌شد | ماتریس انتقال؛ UNKNOWN فقط به COMMITTED/RELEASED با شاهد | transition checks |
| ۹ | آزادسازی رزرو بدون شاهد ممکن بود | آزادکردن ناخواستهٔ بودجه | `NOTE_REQUIRED` برای UNKNOWN_HOLD/RELEASED | release-note checks |
| ۱۰ | intent مصرف‌شده پس از release باعث `IntegrityError` می‌شد | ۵۰۰ و رزرو مبهم | تصمیم `INTENT_ALREADY_USED` / `IDEMPOTENT` بدون درج دوم | API retry checks |
| ۱۱ | `price_source` در Preflight بررسی نمی‌شد | قیمت بی‌منبع می‌توانست PASS شود | check مستقل `price_source` | preflight checks |
| ۱۲ | فازِ Timing با برچسب ثابت `http_rtt` گزارش می‌شد | ادعای نادرست منبع/پذیرش | `source=phase`، `acceptance_time_observed=false` و `percentile_method=nearest_rank` | timing phase check |
| ۱۳ | `percentile` با `round` روی `n-1` برچسب nearest-rank را دقیق نمی‌کرد | p50 نمونهٔ زوج به مقدار بالاتر می‌رفت | `ceil(p/100*n)-1` استاندارد nearest-rank | percentile check |
| ۱۴ | UI هنگام تأیید، `data_as_of=now` می‌ساخت | دادهٔ کهنه «تازه» دیده می‌شد | فیلد صریح «زمان دادهٔ منبع» و ممانعت سمت کلاینت | UI form guard |
| ۱۵ | ذخیرهٔ بودجه در UI اولویت‌ها را با `{}` پاک می‌کرد | ازدست‌رفتن اولویت‌های ثبت‌شده | ارسال `capital.priorities` موجود + ستون اولویت | visual DOM |
| ۱۶ | UI حالت loading/error/empty را قاطی می‌کرد | پیام «هیچ عرضه‌ای نیست» روی خطا | گیت `isPending/isError` | UI route fixtures |

## ۳) چیزی که با مدرک بسته شد (PASS)

| Gate | مدرک |
| --- | --- |
| ثبت عرضه و provenance | `execution_offerings.py:246` و ۱۴ بررسی provenance؛ بدون منبع/URL/زمان، `UNVERIFIED` یا خطای قراردادی |
| بودجهٔ پایدار و بدون اضافه‌برداشت | `set_capital` داخل تراکنش؛ `plan` با `BEGIN IMMEDIATE`؛ تست‌های هم‌زمانی و کاهش سقف |
| یک رزرو فعال برای هر عرضه | ایندکس یکتا + تست دو worker؛ ۹۸/۹۸ گارد |
| `UNKNOWN` و عدم retry | `UNKNOWN_HOLD` بودجه را نگه می‌دارد؛ `UNKNOWN_HOLD→RESERVED` رد می‌شود؛ `plan` تازه `OFFERING_ALREADY_RESERVED` می‌دهد |
| API تکراری/هم‌زمان | TestClient: تکرار plan با همان intent = `IDEMPOTENT`؛ دو درخواست هم‌زمان = یک رزرو |
| Preflight | قیمت/تعداد/سهمیه/کارمزد/منبع قیمت/تازگی/پنجره/سقف کل/سقف هر عرضه |
| Timing | p50/p95/p99 با آستانهٔ n، MAD/IQR، اطمینان، فاز و منبع؛ HTTP RTT ≠ پذیرش کارگزاری |
| UI 1366×768 | اسکرین‌شات‌ها؛ عرض سند 1366 و بدون overflow افقی؛ جدول ۹ ستونی در 1162px |
| UI failure states | Preflight عرضهٔ UNVERIFIED ⇒ FAIL؛ خطای شبکه ⇒ پیام خطا؛ پاسخ خالی ⇒ empty؛ فرم تأیید بی‌زمان داده ⇒ پیام واضح |
| ماندگاری UI/سرور | پس از restart سرور، عرضه‌ها، بودجه، اولویت و `UNKNOWN_HOLD` باقی ماندند |
| بدون Live | هیچ دکمه/مسیر ارسال سفارش در کارت نیست؛ `live_send=false` |

## ۴) آزمون‌ها

| فرمان | نتیجه |
| --- | --- |
| `python dev/execution_offerings_v1140.py` | **98/98**، exit 0 |
| `python dev/execution_schedule_v1130.py` | **58/58**، exit 0 |
| `python dev/strategy_guard_v1123.py` | **57 checks / 0 failed** |
| `python dev/execution_timing_v1.py` | **32/32**، exit 0 |
| `python dev/run_all_tests.py` | **139 suite شمارش‌شده + 27 خاموش + 2 skip؛ 5078/5078 check؛ `ALL SUITES PASSED`**، exit 0 |
| `npx tsc -b` | **0 خطا** |
| `npx vitest run --maxWorkers=2` | **197 passed / 2 skipped files؛ 2065 passed / 5 skipped tests**، exit 0 |
| Frozen build (`scripts/build_all.py`) | **223.8 MB**، exit 0؛ PyInstaller onedir ساخته شد |
| Frozen API smoke | عرضه `VERIFIED`، بودجه v1، تصمیم `RESERVED` با `10512.6`، `available=99989487.4`، `live_send=false`، exit 0 |
| Frozen daemon `--once` | exit 0؛ `execution_schedules.db` ساخته شد؛ صفر schedule (بدون سفارش) |

### ۴.۱) skipها و سکوت‌ها

- Vitest: ۵ تست skip در ۳ فایل: `tape-fuzz-parity` (۲؛ corpus محلی
  `_audit/tape_parity_fuzz.json` نیست)، `tape-sort-bench` (۲؛ `BORS_BENCH`),
  `tape-badge-chip-parity` (۱؛ `TAPE_PAYLOAD`). این‌ها به داده/محیط محلی
  وابسته‌اند و پوشش جدیدی برای عرضه‌ها نیستند.
- Backend: ۲ suite به‌خاطر fixtureهای gitignored (`ra365_ref_bars.json` و
  `market.db.lzma`) skip شدند. ۲۷ suite فقط exit-code دارند و «۰ pass» آن‌ها
  به‌عنوان شمارشِ واقعی گزارش نشده است؛ فهرست `silent` در خروجی خام است.
- `build_all.py` هشدارهای اختیاری `webview/clr/jinja2` را چاپ کرد؛ این‌ها
  مسیر اجرای تست‌شده نیستند و build/API smoke با آن‌ها سبز شد.
- برای Frozen API smoke یک نسخهٔ ۲۶۰MB از `market.db` فقط داخل `data/` بستهٔ
  تست کپی شد؛ اندازهٔ خروجیِ build پیش از این کپی **223.8 MB** است. این کپی
  دادهٔ عملیاتی را تغییر نداد و پس از smoke از بستهٔ تست حذف شد.

## ۵) QA بصری 1366×768

- viewport واقعی: **1366×768**؛ `documentScrollWidth=1366`؛ بدون overflow افقی.
- کارت در `x=8,y=165,w=1182,h=426` رندر شد؛ جدول عرض 1162 بدون سرریز.
- ردیف‌ها: `TESTA` با `VERIFIED`، اولویت `۰` و عمر داده؛ `TESTB` با `UNVERIFIED`.
- دادهٔ `TESTA` در اجرای نهایی از ۳۶۰۰ ثانیه کهنه‌تر شد و هشدار
  «دادهٔ کهنه… Preflight آن را می‌بندد» دیده شد؛ این همان رفتار مورد انتظار است.
- `UNKNOWN_HOLD` با هشدار «بودجه نگه داشته می‌شود…» دیده شد.
- Preflight عرضهٔ `UNVERIFIED`: `source_verified=FAIL` و پیام «Preflight مسدود است».
- فرم تأیید بدون زمان داده: پیام «زمان کلیک، معادل زمان داده نیست».
- خطای شبیه‌سازی‌شدهٔ شبکه: پیام خطای صریح؛ پاسخ خالی: «هیچ عرضه‌ای ثبت نشده است».
- شواهد: `_audit/round6/screen-1366x768.png`،
  `_audit/round6/offerings-1366x768.png`،
  `_audit/round6/offerings-preflight-blocked.png`،
  `_audit/round6/offerings-error.png`، `_audit/round6/offerings-empty.png`،
  `_audit/round6/offerings-after-restart.png`.
- **داوری بصری نهایی مالک: UNVERIFIED**؛ من PASS بصری اعلام نمی‌کنم. هارنس
  محلی فقط روترِ execution را سرو می‌کرد؛ 404های سایر APIها محدودیت هارنس‌اند،
  نه ادعای سالم‌بودن آن مسیرها.

## ۶) تفکیک Mock از واقعی

| چیز | وضعیت |
| --- | --- |
| عرضه‌های `TESTA/TESTB` | fixture ایزوله در Temp؛ نه عرضهٔ واقعی |
| بودجه/رزرو 10,512.6 | دادهٔ شبیه‌سازی؛ نه موجودی واقعی |
| Timing 25 نمونه | fixture محلی؛ نه اندازه‌گیری شبکه/کارگزاری |
| نشست کارگزاری | استفاده نشد؛ هیچ token/cookie خوانده یا ذخیره نشد |
| `market.db` | دست‌کاری نشد؛ سرور بصری فقط روتر execution با DB موقت داشت |
| سفارش/POST کارگزاری | صفر |
| تخصیص/فیل/جایگاه صف | صفر ادعا؛ UNVERIFIED |

## ۷) Timing Intelligence

- `percentile` اکنون nearest-rank است: `k = ceil(p/100*n)-1`؛ برای `[1,2,3,4]`
  و p50 مقدار ۲ می‌دهد (نه ۳).
- p95 فقط با n≥20 و p99 فقط با n≥100 گزارش می‌شود؛ p50 همیشه با نمونه.
- `confidence`: INSUFFICIENT (<5)، LOW (<20)، MEDIUM (<100)، HIGH (≥100)؛
  این آستانه‌ها قراردادِ گزارش‌اند، نه ادعای دقت آماری.
- `source` برابر فاز است (`http_rtt/trigger/preparation/end_to_end`) و
  `acceptance_time_observed=false` همیشه؛ HTTP RTT جانشین زمان پذیرش نیست.
- `timing_suggestion` فقط با p95 موجود و target مثبت پیشنهاد می‌دهد؛ برای
  BOOK_BUILDING/TWO_STAGE مزیت زمانی NOT_PROVEN و برای صف QUEUE_SENSITIVE_UNPROVEN
  است. هیچ ادعای اول‌شدن/سرعت/تخصیص بیشتر مطرح نمی‌شود.

## ۸) دروازه‌ها و موانع

| Gate | وضعیت | علت/اقدام |
| --- | --- | --- |
| اعتبارسنجی provenance و بودجه | PASS | تست‌های 98/98 و API |
| جلوگیری از اضافه‌برداشت/رزرو تکراری | PASS | تست هم‌زمانی store و API |
| عدم retry برای UNKNOWN | PASS | ماتریس انتقال و تست |
| UI layout 1366×768 | PASS (DOM/چیدمان) | اسکرین‌شات و اندازه‌گیری |
| داوری بصری مالک | UNVERIFIED | نیازمند تأیید مالک روی اسکرین‌شات |
| دادهٔ رسمی عرضه | BLOCKED_EXTERNALLY | نماد/ISIN/روش/پنجره/قیمت/سهمیه/کارمزد از منبع رسمی لازم است |
| تقویم/دادهٔ همان روز | BLOCKED_EXTERNALLY | منبع معتبر روز جاری در دسترس نبود |
| قدرت خرید/موجودی | BLOCKED_EXTERNALLY | منبع read-only تأییدشده موجود نیست |
| نشست کارگزاری | BLOCKED_EXTERNALLY | ورود دستی مالک و host سالم لازم است |
| قرارداد write کارگزاری | BLOCKED_EXTERNALLY | هیچ POST واقعی انجام نشد؛ `UNVERIFIED` |
| Timing پذیرش/صف | UNVERIFIED | نمونهٔ واقعی کارگزاری وجود ندارد |
| Live | BLOCKED_EXTERNALLY | `live_ready=false`؛ داده/نشست/قرارداد تأیید نشده |

## ۹) سه فهرست

### A. کارهایی که بدون دخالت مالک کامل شد

- ممیزی و اصلاح ۱۶ ایراد کد/UI/قرارداد.
- 98 بررسی گارد عرضه + 58 زمان‌بند + 57 استراتژی + 32 Timing.
- API TestClient: تکرار، هم‌زمانی، transition، بودجه.
- QA بصری 1366×768، حالت خطا/خالی/Preflight مسدود، ماندگاری پس از restart.
- Frozen build/contract/smoke (نتیجهٔ نهایی در جدول آزمون‌ها).

### B. کارهایی که مالک می‌تواند بدون ثبت سفارش انجام دهد

- یک یا چند عرضهٔ رسمی را با `source_url` و `data_as_of` واقعی در کارت ثبت/تأیید
  کند و اولویت‌ها را تنظیم کند.
- اسکرین‌شات 1366×768 را ببیند و داوری بصری بدهد.
- بودجهٔ واقعی و ذخیرهٔ نقدی را وارد کند (بدون ارسال سفارش).
- Preflight و Timing را با دادهٔ واقعی اجرا کند؛ هر Gate قرمز را گزارش کند.

### C. کارهایی که به تأیید/دسترسی مالک نیاز دارند

- ورود دستی به EasyTrader در host و تأیید سلامت نشست.
- تأیید صریح یک سفارش مشخص (نماد/سمت/تعداد/قیمت/اعتبار) برای آزمون مجاز Live.
- تأیید رسمی دادهٔ عرضه/تقویم/قدرت خرید از منبع کارگزاری.
- مجوز جداگانه برای push/merge/tag/release.

## ۱۰) نتیجه

Round 6 مسیر بودجهٔ چندعرضه‌ای را از «Mock سبز» به «اعتبارسنجی سخت‌گیرانه +
آزمون شکست + QA بصری + ماندگاری» برد. با این حال، دادهٔ رسمی، نشست، قرارداد
واقعی و قدرت خرید هنوز تأیید نشده‌اند؛ بنابراین `live_ready=false` و هیچ
سفارش واقعی مجاز نیست.

## ۱۱) SHA و فایل‌ها

- کامیت کد/تست: `0e673e33` (۶ فایل، +749/−143).
- فایل‌های کد: `api/execution.py`، `execution_offerings.py`،
  `execution_timing.py`، `dev/execution_offerings_v1140.py`،
  `frontend/src/features/portfolio/components/sarkhati/SarkhatiOfferingsCard.tsx`،
  `frontend/src/features/portfolio/lib/orderClient.ts`.
- اسناد این Round در آخرین کامیتِ شاخه‌اند.
- `main`، نسخه (1.0.95)، تگ و Release دست‌نخورده‌اند؛ هیچ push/merge انجام نشد.
- شواهد خام (لاگ‌ها/اسکرین‌شات‌ها) در `_audit/round6/` و عمداً خارج از گیت‌اند.
