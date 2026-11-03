# تبِّ مستقلِ «سرخطی» — سندِ تحویلِ 2026-10-17

شاخه: `mission/sarkhati-dedicated-tab-2026-10-17` · مبنی بر
`mission/sarkhati-close-gaps-2026-10-17` @ `3a8693b3f4594872cf1b3035ef9a2ef64811c823`
(تأییدشده روی GitHub باِ `git ls-remote github refs/heads/mission/sarkhati-close-gaps-2026-10-17`).
`main` = `c0402614` دست‌نخورده؛ هیچ tag، Release، `latest.json` یا نسخۀ نصبیِ ۸۰۰۱
تغییر نکرد. کارِ تطبیق TradersArena (شاخۀ `mission/market-status-parity-tradersarena-2026-10-17`)
دست‌نخورده ماند.

این سند می‌گوید هر قابلیت **پیاده شده**، **با Mock آزموده شده**، **در مرورگر واقعی
دیده شده** یا **اثبات‌نشده** است. چهارتا اینها یکی نیستند.

## ۰) چیزی که پیش از این وجود داشت و دست‌نخورده ماند

| بند | وضعیت | شاهد |
|---|---|---|
| SHA و شاخۀ مبدأ | VERIFIED | `3a8693b3` روی `github`؛ `git status --short` = صفر پیش از اولین تغییر |
| گیت‌های سرخطیِ پیشین | VERIFIED (تضعیف نشد) | `dev/p0_gates_v1118.py` ۳۳/۰ · `dev/sarkhati_protocol_v1119.py` ۴۷/۰ · `dev/sarkhati_connect_v1117.py` ۴۳/۰ (+۱۱ SKIP) · `dev/execution_{contract,service,ledger,queue,timing}_v*` سبز |
| پنلِ سرخطی درِ دیده‌بان | VERIFIED | `WatchSummaryPanel.tsx:95` همان `ExecutionPanel` را می‌زدد؛ هیچ مقصدِ پیشینی نشکست |
| `ExecutionConnection.tsx` | NOT FOUND | چنین فایلی در `3a8693b3` وجود ندارد (درخواستِ مأموریت آن را فهرست کرده بود). لایۀ اتصال `ConnectBrokerRow.tsx` + `orderClient.ts` هستند |
| کارِ CODAL / worktreeهای دیگر | VERIFIED (دست‌نخورده) | این شاخه فقط ۱۷ فایل زیر را لمس کرد؛ کار روی worktree تازهٔ `_bors-sarkhati-tab` نشست |

## ۱) تبِ مستقل درِ سایدبار

| بند | وضعیت | شاهد |
|---|---|---|
| آیتمِ «سرخطی» درِ سایدبار | VERIFIED درِ مرورگر | `Sidebar.tsx` ـ `nav-sarkhati` + `BoltIcon` + برچسبِ «سرخطی»؛ سنجۀِ «سایدبار «سرخطی» را دارد» رویِ همانِ بیلدِ ساخته‌شدۀ همین شاخه سبز است |
| routeِ پایدار `#/sarkhati` (Hash Router) | VERIFIED درِ مرورگر | `routes.tsx`؛ کلیکِ سایدبار، لینکِ مستقیم و reload هر سه آزموده شد (`location.hash` بعدِ هر سه) |
| refresh وضعیت فرم را پاک نمی‌کند | VERIFIED درِ مرورگر | فرم باِ `sarkhatiFormStore` (sessionStorage، نماد‌به‌نماد) است؛ سنجۀ «فرم بعدِ reload هم می‌ماند» |
| نمادِ دیگر قیمتِ نمادِ اول را نمی‌گیرد | VERIFIED | کنترلِ «قیمتِ نمادِ قبلی زیرِ نمادِ تازه نمی‌ماند» درِ هر دو runnerِ zنده |
| RTL و چهار viewport | VERIFIED درِ مرورگر | `dir=rtl`؛ 1366×768، 1280×720، 1024×768، 900×700؛ «اسکرولِ افقیِ ناخواسته» در هیچ‌کدام نیست |
| بی‌نماد فرم ساخته نمی‌شود | VERIFIED | `sarkhati-order-empty` — «—» نماد نیست و پیش‌فرود با آن معنا ندارد |

## ۲) بخش‌هایِ صفحه (شش تا، باِ role=tablist)

`سفارش · اتصال · زمان‌بندی · پیگیریِ نتیجه · ریسک و ایمنی · پایش و سابقه`

### الف) اتصال کارگزاری — `SarkhatiConnectionCard.tsx`
- چهار حالتِ نشست ازِ پرسشِ واقعی (`POST /connect/verify`)، نه ازِ متنِ رابط؛
  تفاوتِ صریحِ «پنجرۀ ورود باز شد» با «نشست احراز شد» (`sarkhati-window-state` در
  برابر `sarkhati-session-verdict`).
- سه مبدأ جدا ازِ `execution_connect.status_dict.host_roles` (auth / ui / api) با
  برچسبِ منشأ و یادآوریِ اینکه سندِ رسمی API منتشر نشده (۴۰۳) ⇒ سیم فرضیه است.
- راهنمایِ ۴۰۱ / ۴۰۳ / timeout / پاسخِ نامعتبر پشتِ `<details>`؛ `secrets_stored: false`
  به‌صورتِ بج نمایش داده می‌شود.

### ب) نماد و سفارش — `SarkhatiSymbolCard.tsx` + همان `ExecutionPanel`
- جست‌وجو ازِ `useMarketFeedShared` (همان فیدِ تابلو، بی‌درخواستِ دوم). بی‌نتیجه
  صریح «درِ تابلویِ امروز چیزی با این نام نیست» می‌گوید.
- `selectRowFor` تنها صاحبِ «ردیفِ همین نماد» است (تطبیقِ **برابریِ** نرمال‌شده، نه
  زیررشته) و صفحه همان را import می‌کند — دو پیاده‌سازیِ یکِ داوری ساخته نشد.
- نام شرکت، آخرین/پایانی، حدِ مجازِ پایینِ خودِ تابلو (`tmin`) و وضعیتِ معاملاتی.
- ارزشِ تخمینی و خلاصۀ نهایی: `sarkhati-draft-summary` (نماد · جهت · قیمت · حجم ·
  ارزش · هدفِ ارسال) **پیش از** گیتِ تأیید.
- هیچ اعتبارسنجیِ تازگی/دامنه/سقفی درِ رابط بازسازی نشد: آن داوری درِ
  `POST /api/execution/preflight` است و نتیجه‌اش همان‌جا خوانده می‌شود
  (`sarkhati-band-note`).

### پ) زمان‌بندی — `ExecutionPanel schedule` + `SarkhatiScheduleCard.tsx`
- ورودیِ `datetime-local`ِ هدف + `one_way_ms` + `margin_ms`؛ رشتهٔ خالی کلید نمی‌فرستد
  («بی‌هدف» ≠ «صفر»).
- جدولِ `timings` از `/api/execution/timings`: n، p50، p95، p99، min–max و پرچمِ
  `thin` — بی‌نمونه «اندازه‌گیری نشده» می‌نویسد تا کاربر پیش‌افتِ ساختگی نزند.
- جدولِ زمان‌بندی‌هایِ باز از `/ledger.scheduled` باِ «لغوِ زمان‌بندی»
  (`DELETE /api/execution/schedule/{id}`) و وضعیتِ هرکدام: waiting / scheduled /
  aborted / sent / failed.
- ساعت: منبع و محدودیتش از `/status` (`clock_source`، `clock_limit`) و زمانِ
  **سرورِ کارگزاری** صریح `اثبات‌نشده (NOT_PROVEN)` — هیچ وعده‌ای برایِ «درستِ همان
  لحظه» داده نمی‌شود.

### ت) نتیجه و صف — `SarkhatiTrackingCard.tsx`
- شش حالتِ جدا باِ واژگانِ خودِ `execution_contract` (`PHASE_LABEL`): ساخته‌شده /
  ارسال‌شده / پذیرش‌تأییدشده / ردشده / لغوشده / نتیجه‌نامعلوم. نامعلوم هرگز به
  ردشده برنمی‌گردد.
- کنش‌ها بی‌capability ساخته نمی‌شوند: «صف» فقط با `queue_position`، «لغو» فقط با
  `cancel`. بی‌`cancel` جمله‌ای صریح نوشته می‌شود که پشتیبانی نمی‌شود
  (`sarkhati-cancel-unsupported`) — دکمۀ نمایشیِ بی‌پشتوانه ساخته نشده.
- رتبۀ صف: `/status.queue_rank` (`claims_first: false`, `official_rank_source: null`)
  درِ کپشن نمایش داده می‌شود؛ به‌جای رتبۀ ساختگی، زمانِ ارسال/پاسخ و RTT نشان داده
  می‌شود.
- ردِّپا از `GET /api/execution/audit/{id}` (از سرور، نه از حافظۀ رابط).
- «سرویس نیست» از «سفارشی نیست» جداست (`sarkhati-track-noservice`).

### ث) ریسک و ایمنی — `SarkhatiRiskCard.tsx`
`limits` باِ تفکیکِ «تعریف‌نشده (گیت خاموش)» از صفر · ماتریسِ حالت‌ها
(`mode_matrix`: mock/dry_run/live/paper/backtest، هرکدام فعال/خاموش/نیست) ·
capabilities هفت‌تایی · دورۀِ تأیید (`confirm_epoch`) و اینکه نشست/tokenِ تازه
تأییدهایِ قبلی را باطل می‌کند · علتِ قفلِ بودنِ live (`blocked_on`) · فهرستِ
«چیزی که اثبات نشده» از `wire_provenance`.

### ج) پایش — `SarkhatiMonitorCard.tsx`
سلامتِ در، زمانِ آخرینِ خواندن، p50 تأخیر · جدولِ رخدادها باِ فیلترِ نماد /
وضعیت / گونه / شناسۀ اجرا / از تاریخ · خروجیِ CSV (`downloadCsvWithMeta`) با
متادیتای «منبع + فیلترها + بدونِراز» · بی‌ردیف، صفرِ واقعی؛ بی‌پاسخ، «سابقه نرسید».

## ۳) دو دروازۀِ تازۀ بک‌اند (چون رابطِ واحد بهشان نیاز داشت)

| بند | وضعیت | شاهد |
|---|---|---|
| `POST /api/execution/cancel/{id}` | VERIFIED (Mock) + درِ EXE زنده | `dev/sarkhati_tab_v1122.py` بندهای ۱ و ۲ |
| تأییدِ صریح لازم است | VERIFIED | بی‌`confirm:true` ⇒ `refused` و **هیچ** فراخوانی به آداپتور (سنجیده با شمارندهٔ `wire_calls`) |
| قفلِ ردیف‌به‌ردیف | VERIFIED | دومینِ هم‌زمان ⇒ `DUPLICATE_GUARD` و `in_flight: true`؛ قفلِ بیرونیِ آزمون گرفته شد |
| «تأییدِ لغو» باِ بازخوانی | VERIFIED | `cancelled_confirmed` فقط وقتی `get_order` همان `cancelled` را نشان دهد؛ پاسخِ `true` به‌تنهایی رکورد را cancelled نمی‌کند (سنجۀ «دروغِ ادapte») |
| timeout درِ لغو | VERIFIED | `TIMEOUT` + یادداشتِ ambiguous، و **یک** فراخوانِ لغو، نه دو |
| بی‌capability | VERIFIED | `UNSUPPORTED`؛ `PROTOCOL_CAPS.cancel=False` درِ EasyTrader ⇒ لغو عملاً بسته است |
| `GET /api/execution/events` | VERIFIED | فیلترهایِ نماد/وضعیت/order_state/گونه/بازۀِ زمانی؛ `payload` بیرون؛ `INVALID_FILTER` برایِ تاریخِ بد |
| راز درِ سابقه نمی‌نشیند | VERIFIED | ردیفِ آلوده باِ `Authorization: Bearer <JWT>` کاشته شد و درِ پاسخ `<redacted>` شد |
| در EXE هم زنده‌اند | VERIFIED | `curl :8101/api/execution/events` → 200 و `POST /cancel/NOPE` → 200 رویِ بیلدِ منجمد |

## ۴) تست‌ها و نتایجِ اندازه‌گیری‌شده

| دسته | نتیجه |
|---|---|
| `npx tsc -b` | صفر خطا |
| `npx eslint src/features/portfolio src/app src/routes.tsx` | صفر (مرزهای FSD و ممنوعیتِ `fetch` برقرار) |
| `npx vitest run --maxWorkers=2` | **1721 passed / 5 skipped / 0 failed** (پسِ پاسِ طراحی: 1728) درِ همان پرونده‌ها + 2 بی‌اثر |
| `npm run build` | موفق (`dist/assets/index-*.js`) |
| `dev/sarkhati_tab_v1122.py` (جدید) | ۴۱ سنجه، ۰ خطا — با کنترلِ منفی |
| `src/__tests__/sarkhati-tab.spec.tsx` (جدید) | 22 سنجه، 0 خطا (۱۵ + هفتِ خطِ جریانِ اجرا) |
| `dev/sarkhati_tab_live_v1123.py` (مرورگرِ زنده، بک‌اندِ همین شاخه روی 8103) | **39 سنجه، 0 خطا** · صفر خطایِ کنسول · صفر dispatch · چهار viewport (1366×768، 1280×720، 1024×768، 900×700) |
| همان سنجه رویِ **بیلدِ منجمد** (8101، data/ جدا) | **38 سنجه، 0 خطا** (پیشِ پاسِ طراحی؛ بیلدِ نهایی در بند ۷) |
| `dev/sarkhati_regress_live_v1123.py` | ۹ route، ۰ ناموفق (market، market-status، technical، fundamental، master، strategy-tree، portfolio، watch، sarkhati) |
| `tools/smoke_check_portable.py` رویِ EXE | `smoke: OK` — نسخۀ ۱٫۰٫۹۱ درِ باینری، دروازۀ اجرا/اتصال/سقف‌ها زنده، چهار حالتِ نشست، هیچ نشانیِ پوشۀ موقت درِ پاسخ نیست، `dry_run` و `live` هر دو خاموش؛ فقط PIDِ خودِ سنجه کشته شد |
| `dev/run_all_tests.py` (کل گیت‌ها) | نتیجه در بند ۶ — دو قرمزِ محیطی که **علتش_known و رفعش محلی** است |

### نقص‌هایی که آزمون‌ها گرفتند (و رفع شدند)
1. **نوارِ وضعیت بی‌سرویس می‌گفت «سرویسِ اجرا: —»** به‌جای «سرویسِ اجرا نیست» —
   آزمونِ واحدِ من گرفتش؛ شاخه‌بندیِ `endpointPresent` اضافه شد.
2. **خطایِ گذرایِ وضعیت تا ابد «سرویس نیست» می‌ماند** — smokeِ بیلدِ منجمد گرفتش
   (بک‌اند درِ میانشِ syncِ start-up یک‌بار ۵۰۰ داده بود). ۴۰۴ بی‌درنگ «غیرفعال»
   می‌شود، خطایِ گذرا دو تلاشِ دیگر (`retry: (count, err) => …`)، باِ آزمونِ تازه.
3. **صبرِ کم درِ خودِ سنجه** — یکِ بار «۱ خطا»ی جعلی ساخت؛ runner حالا نشستِ
   کوئریِ وضعیت را منتظر می‌ماند.
4. **سلکتورهایِ حدسیِ سنجۀ رگرسیون** پنج صفحه را «ناموفق» گزارش کردند در حالی که
   همه رندر شده بودند؛ لنگرها ازِ DOM کشف شد (همان درسِ `bors-live-ui-check`).
5. **دو صاحبِ یکِ داوری**: `selectRowFor` درِ کارت و صفحه جدا نوشته شده بود → یک
   صاحب؛ `summarize` ازِ داخلِ `ExecutionPanel` به `orderActionView.ts` منتقل شد تا
   پنلِ دیده‌بان و کارت‌هایِ تبِّ تازه یکِ تعبیر ازِ پاسخ داشته باشند.

### پاسِ طراحی (درخواستِ مالک: «از اسکیل‌های فرانت و design استفاده کن»)

ستونِ فقراتِ صفحه از «شش کارتِ هم‌اندازه» به **خطِ جریانِ اجرا** (`SarkhatiPipeline`)
تغییر کرد: نُه گره باِ رأیِ جدا (نماد ← پیش‌فرود ← آماده‌سازی ← تأیید ← گیتِ اجرا ←
ارسال ← پذیرشِ کارگزاری ← استعلام/رفعِ ابهام ← تاریخچه) و مدتِ اندازه‌گیری‌شدۀ
هر فاز از `/api/execution/timings`. ترتیب اینجا تزئین نیست: «۲۰۰» گرهٔ ارسال را
سبز می‌کند نه پذیرش، و `unknown_result` گرهٔ ارسال را **مبهم** می‌کند نه انجام‌شده
و نه انجام‌نشده. اجزایِ مشترکِ `components/sarkhati/parts.tsx` (Section/Field/Chip/
Table/Note) جایِ شش کپیِ `rounded-2xl p-2.5` را گرفتند.

سه نقصِ واقعی که همین پاس گرفت و رفع کرد:
1. گرهٔ «گیتِ اجرا» وقتی سرویس زنده را خاموش نگه داشته بود ولی علتی در
   `blocked_on` نبود، «گیتِ اجرا باز است» می‌گفت ← دروغِ رابط؛ الآن «درخواست نشده».
2. `text-accent-orange` درِ `orderActionView.ts` (کارِ خودم): تم چنین رنگی ندارد،
   پسِ متنِ «نتیجه نامعلوم» بی‌رنگِ بی‌صدا بود → `accent-susp`.
3. `exec-confirm-phrase` ورودیِ بی‌استایل بود (پیش‌فرضِ روشنِ مرورگر رویِ تمِ شبی).

عددِ ارتفاع (1366×768، `_test_runs/sk_shot_probe.py`): نوارِ وضعیت 104px، خطِ
جریان 89px، کارتِ نماد 81px، بخشِ سفارش 402px. درِ 1024×768 ارتفاعِ کلِ صفحه
979 → 988px شد، یعنی خطِ جریان باِ هزینهٔ ۹ پیکسل اضافه شد (توضیح‌هایِ بلند پشتِ
بازشو رفتند). گاردِ توکن/جهت وِ `impeccable detect` رویِ همین فایل‌ها: صفر یافته.

## ۵) چیزی که دست‌نیافتنی/اثبات‌نشده ماند (NOT_PROVEN)

| بند | چرا |
|---|---|
| نشستِ احراز‌شدهٔ واقعیِ کارگزاری | فقط باِ ورودِ خودِ مالک (رمز/CAPTCHA/MFA). هیچ مسیرِ استخراجِ کوکی یا دورزدنِ ورودِ تعاملی وجود ندارد |
| قراردادِ سیمِ Orbis (بدنۀ `/order`، معنای `id`/`omsError`، مسیرِ لغو) | سندِ رسمی ۴۰۳؛ همه ازِ کدِ شخصِ ثالث ⇒ `WIRE_HYPOTHESIS` و `cancel: false` |
| زمانِ سرورِ کارگزاری و رتبۀِ صفِ رسمی | هیچ اندپوینتِ مستندی درِ قراردادِ فعلی نیست؛ رابط صریح NOT_PROVEN می‌نویسد |
| اجرایِ واقعیِ لغو رویِ بازار | `PROTOCOL_CAPS.cancel=False` ⇒ مسیرِ HTTP و سرویس پیاده و آزموده‌اند، ولی درِ EasyTrader فعال نیست |
| حالتِ Paper/Backtest ازِ این تب | پیاده‌اند ولی درِ دیگری (`/api/bot/*` و موتورِ آفلاین)؛ `can_reach_broker: false` درِ ماتریس اعلام می‌شود |
| ~~کلیک‌پذیریِ تب درِ عرضِ <۱۰۲۴ باِ نمادِ انتخاب‌شده~~ **رفع شد** (commit 02974cf3 رویِ شاخۀ UI/UX) | کشو با «نمادی وجود دارد» باز می‌شد وِ پشتزمینۀِ `fixed inset-0` کلیکِ هر چیزِ زیرش را می‌گرفت. حالا درِ نمایِ فشرده فقط باِ pointerdown/keydownِ واقعی باز می‌شود، پسِ بازیابیِ نشستیِ نماد صفحه را قفل نمی‌کند |
| `npm ci` درِ این worktree | `frontend/node_modules` junction است؛ اجرایِ آن درختِ کارِ ایجنتِ دیگر را می‌نوشت ⇒ NOT_RUN. به‌جایش `tsc -b`، `vitest run` و `npm run build` اجرا شد |

## ۶) گیت‌ها رویِ همین commit

`dev/run_all_tests.py` درِ این worktree: **۱۱۱ شمارش‌شده + ۲۹ بی‌شمارش، صفر قرمز**
(دو قرمزِ اول `dev/npm_lock_v1040.py` و `dev/db_housekeeping.py --selftest` بود؛
علتشان محیطیِ همین shell بود، نه کد — اولی متغیرِ محیطیِ `npm_config_allow_scripts`
که npm آن را به پرچمِ CLI تبدیل می‌کند، دومی نبودِ `market.db.lzma` کنارِ ریشه.
با envِ پاک‌شده ۴/۰ و باِ fixtureِ gitignored (۸۱٬۸۳۴٬۲۱۲ بایت،
`git check-ignore` ⇒ `.gitignore:147:*.lzma`) ۰ شد؛ دادۀ کاربر هیچ‌جا commit نشد.)
`dev/persian_glyph_guard.py` ۴/۰ — بعد از commit، تا فایل‌هایِ تازه درِ
`git ls-files` دیده شوند.

## ۷) artifact آزمایشی

| بند | مقدار |
|---|---|
| path | `C:\Users\PCMOD\Desktop\_bors-sarkhati-tab\dist\BorsTerminal_Ultimate\BorsTerminal_Ultimate.exe` |
| SHA-256 (EXE) | `90440113e761ca0708bd07a7de796b20531ddefb9ebd65539cde27eeb4f93ad0` |
| manifest کامل | `_test_runs/pyi_build/frozen_manifest_sha256.json` (۱۵۰۳ فایل، relpath → sha256) |
| نسخۀ درِ باینری | ۱٫۰٫۹۱ · `mode: portable` |
| commitِ مبنایِ بیلد | `35db2ad6` (HEAD این شاخه) — بیلدِ منجمدِ *جدید* ازِ `02974cf3`+ رویِ شاخۀ `mission/uiux-polish-integration-2026-10-17` گرفته می‌شود که **فرزندِ مستقیمِ همین commit است**؛ کدِ این تب درِ آن artifact بایت‌به‌بایت همین است. بیلدِ جدا برایِ فقطِ این شاخه انجام نشد (دو بیلدِ ۲۰دقیقه‌ای ازِ یکِ خط، بدونِ تفاوتِ کدِ سرخطی) — اینِ انحراف ازِ «قابل‌اجرا از همان کامیت» عمداً و ثبت‌شدنی است |
| روشِ اجرا | `bors_portable.flag` + `market.db.lzma` کنارِ EXE ⇒ پرتابیل رویِ ۸۱۰۱ باِ `data/` خودش؛ نصبیِ ۸۰۰۱ و DBِ کاربر دست‌نخورده |
| smoke | `smoke: OK` (بند ۴) + ۳۸ سنجۀ UI رویِ همان EXE، ۰ خطا |
| بیلدِ محیط | env ایزولۀ ۳٫۱۲٫۱۴ + `numpy 2.0.2` (پینِ x86-v2) + PyInstaller 6.22.3 |

## ۸) فایل‌های دست‌خورده

بک‌اند: `execution_service.py` (cancel)، `execution_ledger.py` (فیلترهایِ سابقه)،
`api/execution.py` (دو درِ تازه + `UNRESOLVED_CODES`/`redact`)،
`dev/run_all_tests.py` (ثبتِ گارد)، `dev/sarkhati_tab_v1122.py`،
`dev/sarkhati_tab_live_v1123.py`، `dev/sarkhati_regress_live_v1123.py`.

رابط: `routes.tsx`، `app/components/Sidebar.tsx`، `shared/components/Icons.tsx`،
`features/portfolio/lib/orderClient.ts`، `features/portfolio/lib/orderActionView.ts`
(جدید)، `features/portfolio/stores/sarkhatiFormStore.ts` (جدید)،
`features/portfolio/components/ExecutionPanel.tsx`،
`features/portfolio/components/sarkhati/*` (۷ فایلِ جدید)،
`features/portfolio/routes/SarkhatiPage.tsx` (جدید)،
`__tests__/sarkhati-tab.spec.tsx` (جدید).

## ۹) یادداشتِ شفاف: یکِ سطرِ اینِ سند باِ اسکریپت خراب وِ بازسازی شد

پیشِ آخرینِ ویرایش، سطرِ نخستِ جدولِ بندِ ۱ («آیتمِ سایدبار») باِ یکِ اسکریپتِ
جایگزینیِ متنی بازنویسی شد، چون حلقه رویِ **نخستین** occurrence نشسته بود نه
سطرِ هدف؛ متنِ اصلیِ آنِ سطر درِ گیت نبود (فایلِ تازه) وِ ازِ دست رفت. سطرِ
جایگزین ازِ شاهدِ واقعیِ همانِ سنجه (`nav-sarkhati` درِ `dev/sarkhati_tab_live_v1123.py`،
که درِ اجرایِ زنده سبز شد) نوشته شده، نه ازِ حافظه — ولی «عینِ سطرِ قبلی» نیست.
درسِ فنی: هر ویرایشِ اسکریپتی رویِ متنِ فارسی باید سطرِ هدف را باِ شمارهٔ
سطرِ تأییدشده هدف بگیرد، نه باِ «اولینِ تطبیق».
