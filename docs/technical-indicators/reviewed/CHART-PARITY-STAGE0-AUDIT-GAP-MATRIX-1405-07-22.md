# Stage 0 — ممیزیِ خواندنی، گیتِ roadmap، و ماتریسِ شکافِ «تکنیکال + UI چارت» در برابر رهاورد ۳۶۵

تاریخ: ۱۴۰۵-۰۷-۲۲ (۲۰۲۶-۱۰-۱۴) · branch کاری: `mission/fts-indicator-engineering` · HEADِ این مرحلۀ ممیزی: `415c82b` (بستۀ Phase 5)
مأموریت: تطبیقِ کاملِ چارتِ تکنیکال و ابزارهایِ رسم و تعامل/اسکرول/زوم با رهاورد ۳۶۵، با اثباتِ مرورگری.
قیدِ حاکم برِ این مرحلۀ خاص: «ابتدا وضعیتِ مأموریتِ Fundamental/CODAL و خطِ لولۀ Auto-Update آن را از رویِ شواهد بررسی کن. اگر هرکدام هنوز باز است، درِ این مرحله **فقط** ممیزیِ خواندنی، تستِ غیرمخرب و ماتریسِ شکاف؛ تغییراتِ بزرگ یا تداخل‌زا درِ تکنیکال شروع نشود.»

---

## ۰. متد و قیودِ اجراشده (چون نتیجه به آن‌ها بند است)

| قید | چطور رعایت شد |
|---|---|
| خواندنی بودن | درِ این مرحلۀ ممیزی **هیچ** فایلِ تولیدی (`.py`/`.ts`/`.tsx`) ویرایش یا ساخته نشد؛ تنها افزودنی‌ها: سندِ حاضر + هارنس‌هایِ کاوشِ `_audit/*.js` + دو فایلِ شاهد. `git status` پس ازِ ممیزی درِ `api/`، `frontend/`، `docs/` (به‌جزِ این سند) خالی است. |
| مرجع فقط‌خواندنی | چارتِ مالک رویِ رهاورد ۳۶۵ با AutoSave **روشن** است (همان «All changes saved» درِ نوارِ بالا، `_audit/ra365_tools2.json` → `baseline.items`). هیچِ ابزاری انتخاب نشد، هیچِ اندیکاتوری اضافه/حذف نشد، هیچِ شکلی رسم نشد، کاربر ازِ نشست خارج نشد. کاوش فقط با caret/hover و سپس `Escape`. |
| احراز هویت | نشستِ خودِ مالک درِ پروفایلِ Edgeِ آزمایشِ پروژه (`%TEMP%\bors-ra365-probe-profile`). نه فرمِ ورودی پر شد، نه رمز/کوکی/token استخراج یا لاگ شد؛ ازِ توکن **فقط طولِ آن** (۶۳۲) ثبت شد (`_audit/ra365_meta.json` → `tokenLengthOnly`). |
| کنترلِ امنیتی/ضدربات | دور زده نشد. مسیرهایی که بدنهٔ HTMLِ ۸۲۴ بایتیِ ضدربات یا ۴۰۴ دادند همان‌طور **مرده** ثبت شدند (§۲-پ). |
| دیتابیسِ عملیاتی | بانکِ بازار درِ این مرحله اصلاً باز نشد (کاوش‌ها شبکه‌ای/DOM بودند). |
| اثباتِ مرورگری | هر ادعایِ مرجع یا خودی یا ازِ سورس با `file:line` است، یا ازِ DOM/APIِ واقعی با فایلِ شاهد. چیزی که دیده نشد `NOT OBSERVED` مانده، نه حدس. |

---

## ۱. گیتِ الزامی — هر دو پیش‌نیاز باز است

### ۱-الف. مأموریتِ Fundamental/CODAL: باز (بستۀ کامل نیست)

| شاهد | متن/عدد |
|---|---|
| `docs/MASTER-EXECUTION-ROADMAP.md:2461` | `## 15.12 Final Funnel milestone (owner mission 2026-10-08, §1-46) - IN PROGRESS` |
| `:2471` (X-7) | `**Frontend still runs its own judge**` → `OPEN - BLOCKING` |
| `:2492-2493` | `**FINAL STATUS of the milestone: NOT COMPLETE.**` |
| `:2370` (A0-2) | `ACCEPTED-PROVISIONAL` … `Pixel proof of 873 rendered rows: UNVERIFIED` |
| `:2398` (D-6) | `Live Codal rate-limit/quota check needs an Iranian egress; cdn.tsetmc.com returns 403 from this machine` → `EXTERNAL` |
| `:2411`،`:2412` (D-7،D-8) | `DISCOVERED` (آلودگیِ نامِ نماد `معيار `؛ رانشِ جهان ۸۷۳ ⇔ ۹۲۲) |
| `:2434` (F-3) | `PENDING does not exist in the backend` |
| `:2476` (X-12) | `TSE/TSETMC validation, browser validation, inspector` → `OPEN` |
| `docs/fts-notes/FUND_LIVE_AUDIT.md:36` و `:91` | دو «نکتۀ باز» که تصمیمِ مالک لازم دارد |

**واکاویِ کد، نه نقلِ جدول:** نیمۀ اوّلِ X-7 واقعاً بسته شده (`buildFunnel`/`techMark`/`fundMark` ازِ `frontend/src` بیرون رفته‌اند)، ولی نیمۀ دومِ همان سطر زنده است: `tapeFilterVerdict` درِ `frontend/src/features/market/lib/tapeAlgorithms.ts:411` هنوز همان داوریِ سمتِ مرورگرِ جدولِ تابلو است و ۱۲ مصرف‌کننده دارد (`MarketFilters.tsx:26,296,405`؛ `SuspiciousPanel.tsx:8,50,70,92`؛ `tapeBadges.ts:20,56,90,93,103,106,111,122`؛ `MarketPage.tsx:20,44`؛ `tapeStore.ts:9`). پس X-7 به‌ازایِ جدولِ تابلو **همچنان باز** است.

### ۱-ب. خطِ لولۀ Auto-Update کدال: باز (درِ عمل ساخته نشده)

| سنجه | نتیجهٔ اندازه‌گیری |
|---|---|
| زمان‌بند (scheduler) برایِ کدال | **هیچ**. نه `APScheduler`/`schedule`/`celery`/`croniter`/`huey`/`rq` درِ `requirements.txt`، نه `threading.Timer`/`asyncio.create_task` درِ `api/` یا `app.py`، نه `schedule:` درِ `.github/workflows/` (`guards.yml`، `market-data.yml`، `release.yml`؛ `market-data.yml:3-7` فقط `push` + `workflow_dispatch`) |
| حلقه‌هایِ پس‌زمینۀ `app.py` | فقط تابلو: `_board_refresh_loop:248` (۹۰s)، `_board_tick_loop:274` (۵s)، `_pulse_snapshot_loop:308` (۳۰۰s)، `_warm_screener:219`. تنها کدِ کدال درِ بوتِ برنامه مهاجرتِ schema است (`app.py:192-202`) |
| مسیرهایِ کدال | همه دستی و HTTP: `api/_sync_codal.py:30` `POST /api/sync/codal`، `:62 fts-refresh`، `:341 db-download`، `:362 db-status`، `:377 /api/sync/status`، `:463 diagnose`، `:570 POST /api/codal/control`؛ `api/fundamental.py:2334 fts-coverage`؛ `api/engine.py:22,30,37,44` delta/backfill/watchlist/full؛ `api/_pipeline.py:47,52`. سمتِ UI هم یک دکمه است: `frontend/src/features/fundamental/routes/FundamentalPage.tsx:65-68`؛ تنها `setInterval` آنجا (`:90`) پولینگِ وضعیتِ همان دانلود است، نه زمان‌بند |
| خاموش‌شدن درِ بیلدِ فریزشده | `api/_core.py:19` `codal_crawler_available()` → `return not bool(getattr(sys, "frozen", False))` (`:29`)، اعمال‌شده درِ `api/_sync_codal.py:42-48` (`status:"unavailable"`) و `:73-88` (`local_recompute`). چرخشِ IP هم خاموش: `codal_fetcher.py:1822 ADB_CONTROL_AVAILABLE` ⇔ `api/engine.py:16,54,60` (`"reason": "dev_only"`) |
| وضعیتِ «هر گام چه شد» | نیست؛ endpointِ وضعیت دارد ولی هیچِ اجرایِ زمان‌بندشدۀ ثبت‌شده‌ای ندارد که وضعیت بدهد |
| ریلانچرِ مرده | `_launch_codal_scan()` (`api/_sync_codal.py:517`) دستورِ `bash run_discovery.sh` می‌زند (`:541-546`) ولی `run_discovery.sh` درِ مخزن **وجود ندارد** → `POST /api/codal/control {"cmd":"resume"}` بی‌صدا `running:false` می‌دهد |
| تنها زمان‌بندِ واقعیِ پروژه | `scripts/schedule_live_audits.ps1:34-37` دو تسکِ ویندوز: `BorsFTSLiveAudit` → `tools/fts_live_audit.py`، `BorsTapeLiveAudit` → `tools/market_tape_live_audit.py` (`-Weekly … 08:45`). هیچ‌کدام خزندهٔ کدال نیستند و خودشان هم نبسته‌اند: `docs/SESSION-REPORT-1405-07-18.md:18` `PARTIAL`، `:230` «اجرایِ کاملِ زمان‌بندشده با کدِ جدید هنوز درِ نشستِ واقعی ندیده شده»، `docs/SESSION-REPORT-1405-07-19.md:98` «لاگوتايب Interactive only است» |

### ۱-پ. حکمِ گیت

**هر دو پیش‌نیاز باز است** (الف: `NOT COMPLETE` + `OPEN - BLOCKING`؛ ب: زمان‌بندِ کدال ساخته نشده). بر بنیادِ `docs/MASTER-EXECUTION-ROADMAP.md:9` («do not start the next item until the current item has been … explicitly accepted»)، `:2308-2310` («Until the Funnel is accepted, do not start unrelated new FTS chart-analysis modules») و `:2426-2428` — درِ این دور **هیچ** تغییرِ بزرگ یا تداخل‌زایِ چارت شروع نشد. مجوزِ استثنائیِ `:2324` (باگ/امنیت/فسادِ داده/رگرسیونِ بحرانی) هم صدق نمی‌کند: آنچه درِ §۴ پیدا شد نقصِ کارکردیِ UI است، نه خرابیِ داده یا امنیتی، و اصلاحش «تغییرِ تداخل‌زا» محسوب می‌شود. پس تحویلِ این دور = ممیزی + ماتریسِ شکاف + ثبتِ شواهد.

### ۱-ت. رفعِ یکِ تناقضِ مستندِ پیشین (اندازه‌گیری، نه نقل)

سه سندِ موجود سه چیزِ متفاوت می‌گویند و هیچ‌کدام با وضعِ فعلی یکی نیست:

| سند | ادعا | وضعِ واقعیِ اندازه‌گیری‌شده امروز |
|---|---|---|
| `docs/MASTER-EXECUTION-ROADMAP.md:2740-2744` | «four suites still red … `tape_filters_v1034` 214/2، `test_fts_technical_tristate` 32/37، `test_fts_roundj` ۱ سرخ، `chart_api_check_v95`» | هر چهار سوئیت امروز سبزند: `_audit/PHASE5-GATE-RUNALL-FINAL2.txt` سطر ۹۰ `221/221`، سطر ۴۶ `38/38`، سطر ۴۷ `rc=0`، سطر ۵ `18/18` |
| `docs/technical-indicators/reviewed/FTS-MISSION-CLOSURE-1405-07-20.md:36` | `python dev/run_all_tests.py` → `OK 114 · FAIL 0` | امروز **۱۲۳ سوئیت، همه OK، `ALL SUITES PASSED`، rc=0** (۹ سوئیت به شمارِ سوئیت‌ها افزوده شده، نه اینکه عدد عوض شود) |
| همین دور | — | همان ۱۲۳/۱۲۳، شاهدِ خام درِ مخزن: `_audit/PHASE5-GATE-RUNALL-FINAL2.txt` |

این سطرهایِ roadmap **کهنه**‌اند؛ اصلاحِ آن‌ها کارِ این دور نبود (سندِ مرجعِ مأموریتِ دیگری است) و درِ §۷ به‌عنوانِ یکِ درخواستِ روشن باقی مانده است.

---

## ۲. مرجعِ مشاهده‌شده — رهاورد ۳۶۵، با شاهد

### ۲-الف. متادیتایِ رسمی از API (قوی‌ترینِ شاهد؛ `_audit/ra365_meta.json`، هر دو endpoint HTTP 200)

| فیلد | مقدارِ مشاهده‌شده |
|---|---|
| `supported_resolutions` | `["1","5","10","15","30","45","60","120","240","D","W","M","3M","6M","12M"]` — ۱۵ مقدار، **۹ تایِ آن‌ها دقیقه‌ای/ساعتی** |
| `intraday_multipliers` | `["1","5","10","15","30","45","60","120","240"]` |
| `has_intraday` / `has_weekly_and_monthly` | هر دو دیده شدند (`keys` درِ پاسخِ `/api/v2/chart/symbols`) |
| `session` | `7;0900-1330:12347` (نشستِ ۹:۰۰–۱۳:۳۰، روزهایِ شنبه تا چهارشنبه) |
| `timezone` | `Asia/Tehran` |
| `pricescale` / `minmov` / `format` | هر سه درِ پاسخِ نماد (اعدادِ دقیقِ `minmov`/`format` درِ `interesting` ثبت نشد؛ §۲-د) |
| `configs` | کلیدها: `adjustments، price_types، symbols_types، calendar_type، timezone، supports_marks، supports_timescale_marks، supported_resolutions` |

**نکتۀ روش‌شناسی:** `configs.supported_resolutions` همان فهرست را معکوس می‌دهد — یعنی فهرستِ بازه‌ها **سورس-محور** است نه سلیقۀ UI. این عدد ثابت می‌کند مرجع رویِ این نمادِ خاص دیتایِ درون‌روز دارد؛ ولی اینکه آن دیتا **واقعتاً** تیک‌به‌تیکِ دقیقه‌ای است یا سمتِ سرور ازِ منبعی دیگر ساخته می‌شود، مشاهده نشد و ادعا نمی‌شود.

### ۲-ب. معماریِ نوارِ ابزار و ابزارهایِ رسم (DOM واقعی؛ `_audit/ra365_tools3.json`، بی‌کلیک و بی‌hover)

`total: 55` عنصرِ شناسایی‌شده درِ DOM، دسته‌بندی‌شده:

| دسته | آنچه دیده شد |
|---|---|
| ۸ گروهِ رسم | `linetool-group-cursors`، `-trend-line`، `-gann-and-fibonacci`، `-patterns`، `-prediction-and-measurement`، `-geometric-shapes`، `-annotation`، `-font-icons` |
| کنترل‌هایِ رسم (۱۲) | `measure` (Measure)، `magnet-button`، `lockAllDrawings` (Lock all drawings)، `hide-all`، `removeAllDrawingTools`، `showObjectsTree` (Show Object Tree)، `toolbar-drawing-toggle-button` (Hide Drawings Toolbar)، `drawginmode` (**Stay in Drawing Mode**)، `zoom` (Zoom In)، `legend-show-hide-action` (Hide)، `linetool-group-cursors`، `-prediction-and-measurement` |
| مقیاسِ محورِ قیمت (۴) | `auto` (Toggle Auto Scale)، `logarithm` (Toggle Log Scale)، `percentage` (Toggle Percentage)، `open-indicators-dialog` (Indicators & Strategies) |
| بازه/تایم‌زون (۱۱) | `date-ranges-tabs` = `5y 1y 6m 3m 1m 5d 1d`، هفت تبِ `date-range-tab-*` با توضیحِ «در بازهٔ X با فاصلهٔ Y» (مثلاً `1 week in 3 months intervals` ⇔ `date-range-tab-12M`)، `legend-source-interval` (Change interval)، `time-zone-menu` (Timezone)، `date-ranges-menu` (Date Range) |
| سایر | `go-to-date`، `header-toolbar-properties` (تنظیماتِ چارت)، `header-toolbar-quick-search`، `save-load-menu`، `open-indicators-dialog` |
| زیرمجموعۀ `save-load-menu` (`_audit/ra365_tools2.json`) | `…-save`، `…-rename`، `…-clone`، `…-load` — یعنی چهار فعلِ مجزا رویِ نقشۀِ چارت |
| زیرمجموعۀ `linetool-group-cursors` | `cursor`، `dot`، `arrow`، `eraser` (هر کدام با «Add to favorites») |

### ۲-پ. آنچه **NOT OBSERVED** ماند (و چرا) — مهم‌تر ازِ فهرستِ بالا

| مورد | وضعیت | دلیلِ ثبت‌شده |
|---|---|---|
| تک‌تکِ ابزارهایِ داخلِ ۷ گروه از ۸ گروه | **NOT OBSERVED** | flyout به‌صورتِ lazy render است: با بازکردنِ caret فقط `templates :: Templates` و `drawing-toolbar` درِ DOM آمد، نه آیتم‌ها (`ra365_tools2.json` → هر گروه: `items: 2`). خواندنِ آیتم‌ها نیازمندِ فعال‌کردنِ حالتِ رسم/انتخابِ ابزار است که رویِ چارتِ AutoSave‌دارِ مالک مجاز نیست |
| شمارِ واقعیِ ابزارهایِ مرجع | **NOT OBSERVED** | نتیجهٔ بالا |
| رفتارِ زوم/اسکرول/پنِ مرجع (شتابِ چرخ، کانونِ زوم زیرِ نشانگر، کشیدگیِ مقیاس، limitِ min/maxِ بار) | **NOT OBSERVED** | این‌ها با تعاملِ ماوسی رویِ بومِ همان چارتِ شخصی سنجیده می‌شوند و **خودِ همان تعامل** وضعیتِ layout (جایِ اسکرول، محدودهٔ دید) را عوض می‌کند؛ با AutoSave روشن یعنی نوشتن برِ چارتِ مالک. تا وقتی مالک یکِ layoutِ یک‌بارمصرف بسازد یا صریحاً اجازه دهد، این سطرهایِ ماتریس قابلِ اندازه‌گیری نیستند (نه اینکه اندازه‌گیری و پنهان شده باشد) |
| فهرستِ اندیکاتورهایِ مرجع | **NOT OBSERVED** | بازکردنِ `open-indicators-dialog` = کاوشِ بیشتر درِ اکانتِ مالک؛ درِ این دور انجام نشد. (۹ مطالعۀِ سبکِ مبننا ازِ قبل درِ Phaseهایِ پیش استخراج و درِ `lib/mabnaIndicators.ts` پیاده شده بود، نه درِ این دور) |
| `minmov`/`format`/`pricescale` عددی | بخشی | کلیدها درِ پاسخ دیدۀ شدند؛ برایِ دو تا ازِ سه‌تا مقدارِ عددی درِ خلاصۀ `interesting` آن اجرا ثبت نشد (دوباره‌گیریِ خواندنی لازم است، بی‌هیچِ اثرِ جانبی) |
| بی‌اثریِ کاوش رویِ چارتِ مالک | **ثبت شد، با حدِ صادقانه** | `_audit/ra365_tools4.json` → `health_before` = `health_after` = `{"legend":["فولاد مبارکه اصفهان- بورس تهران"], "activeDrawingish":[], "drawModeHints":[]}`، `clean: true`. اما «شمارِ شکل‌ها» به‌عنوانِ اثباتِ عددی **معتبر نبود**: دکمهٔ `removeAllDrawingTools` درِ این نسخه عددی درِ `title` ندارد، پس `null === null` بی‌معنا «بی‌تغییر» می‌داد؛ خودِ آن سنجش درِ `ra365_tools2.json` با `proof_meaningful: false` علامت‌گذاری شده و به‌عنوانِ اثبات استفاده نشده. اثباتِ واقعی = همان دو خوانشِ passivِ legend/active-tool |

---

## ۳. ماتریسِ شکافِ قابلیت — BorsTerminal در برابر مرجع

دو موتور درِ `frontend/src/features/technical/engine/registry.ts:17-43` ثبت شده‌اند (هر دو `production: true`؛ پیش‌فرض `klinecharts`، `:44`) و **وضعیتشان جدا نوشته می‌شود**، چون چارتِ زنده ازِ تراکنشِ موتور رد نمی‌شود: `KLineChartWrapper.tsx:3-4,955` مستقیم `klinecharts` را `init` می‌کند، و تراکنش‌ها فقط `FtsEngineChart.tsx` و `engine-lab/EnginePane.tsx` را می‌سازند (`routes/TechnicalPage.tsx:265-279` ⇔ `:293-314`).

«حکم» = وضعیتِ **BorsTerminal** (نه مرجع). مرجع = آنچه درِ §۲ دیده شد.

**راهنمایِ مسیرها (همه با `find` درِ همین مخزن تأیید شده‌اند):** نام‌هایِ کوتاهِ زیر همگی زیرِ `frontend/src/features/technical/`اند —
`KLineChartWrapper.tsx` / `DrawingToolbar.tsx` / `FtsToolbar.tsx` / `TradingViewIcons.tsx` = `nahayatnegar/components/…`؛
`lib/timeframe.ts` و `lib/axisScaleLock.ts` = `nahayatnegar/lib/…`؛
`lib/drawStore.ts`، `lib/drawingTools.ts`، `lib/tvToolList.ts`، `lib/ftsOverlays.ts`، `lib/mabnaIndicators.ts`، `lib/tvIndicatorCatalog.ts`، `lib/patternOverlays.ts`، `lib/engineFtsLayers.ts`، `lib/replay.ts`، `lib/resample.ts`، `lib/chartTypes.ts`، `lib/compareIndicator.ts` = `lib/…`؛
`stores/…`، `components/…` (به‌جزِ چهارتاىِ اول)، `routes/…`، `engine/…`، `styles/…` = همان دایرکتوری‌ها؛
`EnginePane.tsx` و `EngineLabPage.tsx` = `engine-lab/…`؛
`KLineChartsEngine.ts` = `engine/klinecharts/…` و `FastFinancialChartsEngine.ts` = `engine/ffc/…`؛
`tapeAlgorithms.ts`، `tapeBadges.ts`، `tapeStore.ts`، `MarketFilters.tsx`، `MarketPage.tsx`، `SuspiciousPanel.tsx` = `frontend/src/features/market/…`؛
`useMediaQuery.ts` = `frontend/src/shared/lib/…`، `Sidebar.tsx` = `frontend/src/app/components/…`، `vendor/klinecharts.d.ts` = `frontend/src/vendor/…`، `__tests__/…` = `frontend/src/__tests__/…`؛
`api/`، `docs/`، `dev/`، `_audit/`، `tools/`، `scripts/` و `frontend/index.html` نسبت‌به‌ریشۀِ مخزن، و `frontend/node_modules/@pairlens/fast-financial-charts/dist/esm/types/…` همان‌طور که نوشته شده.

### الف. ابزارهایِ رسم

| # | قابلیت | KLineCharts (زنده) | موتورِ دوم (ffc) | حکم | مرجع | شاهد |
|---|---|---|---|---|---|---|
| ۱ | ساختارِ گروهیِ نوارِ رسم | ۸ گروه، ۲۷ ابزارِ نهایی | ندارد | DONE | ۸ گروه | `DrawingToolbar.tsx:61-145` (شمارشِ سطرهایِ `items`)؛ `ra365_tools3.json.groups` |
| ۲ | انتخابِ ابزار → رسمِ واقعی رویِ چارت | `createOverlay({name, groupId:'fts-draw', …})` با رویدادهایِ draw/move | `beginDrawing` صدا زده نمی‌شود | DONE | مشاهدهٔ lazy (§۲-پ) | `KLineChartWrapper.tsx:2187-2281`؛ `:2227-2272`؛ `FastFinancialChartsEngine.ts:389-391` + نبودِ call site |
| ۳ | خط روند / پرتو / خط قیمت / افقی / عمودی / کانال موازی | همه موجود | ندارد | DONE | گروهِ `trend-line` | `DrawingToolbar.tsx:78-83` |
| ۴ | فیبوناچی بازگشتی/اکستنشن/بادبزن + نسخۀِ لگاریتمی | موجود، با سطوحِ سفارشی و سوئیچِ log | ندارد | DONE | گروهِ `gann-and-fibonacci` | `DrawingToolbar.tsx:91-93`؛ `lib/ftsOverlays.ts:405-457`؛ `KLineChartWrapper.tsx:2209-2211` |
| ۵ | جعبه/بادبزن گن، XABCD، امواجِ الیوت، اشکالِ هندسی، متن/برچسب، موقعیتِ خرید/فروش | موجود | ندارد | DONE | `-geometric-shapes`، `-annotation`، `-patterns`، `-prediction-and-measurement` | `DrawingToolbar.tsx:100-141`؛ `lib/tvToolList.ts:8-23` (۱۴ ابزارِ پیشرفته، رجیسترِ lazy درِ `:892-904`) |
| ۶ | **چنگالِ اندروز (Andrews Pitchfork)** | ندارد؛ سطرِ `pitchfork` درِ UI به `parallelChannel` می‌رود (برچسبِ غلط) | ندارد، درحالی‌که نوعش درِ vendor هست | NOT STARTED | گروه/ابزارِ مشخصِ مرجع دیده نشده (§۲-پ) | `DrawingToolbar.tsx:94`؛ آیکونِ بی‌مصرف `TradingViewIcons.tsx:273`؛ `frontend/node_modules/@pairlens/fast-financial-charts/dist/esm/types/drawings.d.ts` (`'pitchfork'`) |
| ۷ | **منطقۀِ زمانیِ فیبوناچی (Fib Time Zone)** | ندارد | ندارد (درِ انواعِ رسمِ vendor هم نیست) | NOT STARTED | NOT OBSERVED | نبودِ `fibTimeZone` درِ `frontend/src` و درِ فهرستِ ۵۴ نوعِ `drawings.d.ts` (تنها `'fibonacci'` هست) |
| ۸ | **نیم‌خطِ افقی/عمودی، خطِ بی‌نهایت، برچسبِ ساده** درِ UI | ندارد؛ فقط درِ ماژولِ مرده | ندارد، ولی `hline`/`hray`/`vline`/`xline` درِ انواعِ vendor هست | NOT STARTED | NOT OBSERVED | `lib/drawingTools.ts:19-31,57` (بدونِ importِ تولیدی)؛ `drawings.d.ts` |
| ۹ | الگویِ اندازه‌گیری‌شده (Drawn MVPS) به‌عنوانِ ابزارِ رسم | ندارد (فقط لایۀ تشخیصِ سمتِ سرور) | ندارد | NOT STARTED | NOT OBSERVED | `lib/patternOverlays.ts:18,31,49,402-410` |
| ۱۰ | گروهِ «آیکون/فونت» (font-icons) | ندارد | ندارد | NOT STARTED | `linetool-group-font-icons` **دیده شد** | `ra365_tools3.json.groups`؛ نبودِ همتا درِ `DrawingToolbar.tsx` |
| ۱۱ | درختِ اشیاء (Show Object Tree) | ندارد | ندارد | NOT STARTED | `showObjectsTree` **دیده شد** | `ra365_tools3.json.drawControls`؛ grep درِ `frontend/src`: هیچ |
| ۱۲ | «در حالتِ رسم بمان» (Stay in Drawing Mode) | ندارد | ندارد | NOT STARTED | `drawginmode` **دیده شد** | همان؛ grep: هیچ |
| ۱۳ | آهن‌ربا (مغناطیس)/قفلِ همه/پنهانِ رسم‌ها/حذفِ همه/اندازه‌گیر | همه موجود و متصل | ندارد | DONE | `magnet-button`, `lockAllDrawings`, `hide-all`, `removeAllDrawingTools`, `measure` | `DrawingToolbar.tsx:222-274` ⇔ `KLineChartWrapper.tsx:2509-2525`, `:2339-2347` |
| ۱۴ | ماندگاریِ رسم‌ها | localStorage به تفکیکِ نماد+تایم‌فریم + undo/redo + flush | ندارد | DONE (محلی) | «All changes saved» = سمتِ سرور | `lib/drawStore.ts:18-29,40-68,124-153,156-176`؛ اتصالش `KLineChartWrapper.tsx:742-870`, `:1886-1946` |
| ۱۵ | ماندگاریِ سمتِ سرور (endpoint/جدول) | ندارد | ندارد | NOT STARTED | همان | هیچ `CREATE TABLE` رسم/overlay درِ `*.py`؛ تنها `_audit/*` نه کدِ برنامه |
| ۱۶ | ذخیره/تغییرِ نام/کپی/بارگذاریِ نقشۀِ چارت | ذخیره و اعمالِ قالب (مطالعات + نمایش)؛ بی‌rename، بی‌clone، بی‌رسم‌ها | ندارد | PARTIAL | چهار فعلِ مجزا: save/rename/clone/load | `stores/chartTemplateStore.ts:19`؛ `KLineChartWrapper.tsx:1979-2021`, `:2828-2919` |

### ب. تعامل: ماوس، اسکرول، زوم، پن

| # | قابلیت | KLineCharts | ffc | حکم | مرجع | شاهد |
|---|---|---|---|---|---|---|
| ۱۷ | چرخِ ماوس = زوم، درگِ بوم = پن | رفتارِ پیش‌فرضِ کتابخانه، با سقف/کفِ عرضِ بار `barSpaceLimit:{min:2,max:40}` | `interaction.wheelZoom/dragPan` هرگز ست نمی‌شوند | DONE / PARTIAL | **NOT OBSERVED** (§۲-پ) | `KLineChartWrapper.tsx:957`؛ `FastFinancialChartsEngine.ts:290-292` |
| ۱۸ | خاموش/روشن‌کردنِ زوم | ممکن نیست | `setScrollEnabled` رویِ کلیدِ ناموجودِ vendor | NOT STARTED | — | `frontend/src/vendor/klinecharts.d.ts:114` فقط تایپ است، بی‌call site؛ کلیدهایِ واقعیِ vendor: `frontend/node_modules/@pairlens/fast-financial-charts/dist/esm/types/theme.d.ts:113-122` (`wheelZoom`، `dragPan`، `keyboardShortcuts`، `drawingSnap`، `drawingToolMode`، …) |
| ۱۹ | قفلِ مقیاس هنگامِ درگِ محور (محورِ عمودی تکان نخورد) | پیاده و متصل | ندارد | DONE | NOT OBSERVED | `KLineChartWrapper.tsx:1330-1332` + `lib/axisScaleLock.ts:60-103` (آستانه‌ها `:27,:49`) |
| ۲۰ | کنترلِ «قفلِ درگ محور» درِ تنظیمات | دکمه هست، **رفتار ندارد** | ندارد | NOT STARTED | `header-toolbar-properties` | `stores/ftsConfigStore.ts:39,96` ⇔ `ChartSettingsDialog.tsx:406-412`؛ هیچ مصرف‌کننده‌ای درِ کدِ چارت (§۴-D1) |
| ۲۱ | کلیدهایِ میان‌بر | فقط Esc/Delete/Backspace/Ctrl+Z/Ctrl+Y برایِ رسم‌ها | ندارد | PARTIAL | NOT OBSERVED | `KLineChartWrapper.tsx:824-863` |
| ۲۲ | منویِ راست‌کلیک رویِ چارت | ندارد | ندارد | NOT STARTED | NOT OBSERVED | grep `contextMenu|onContextMenu|rightClick`: هیچ درِ `frontend/src` |
| ۲۳ | رفتن به تاریخ (`Go to date`) | ندارد | ندارد | NOT STARTED | `go-to-date` **دیده شد** | `ra365_tools3.json.otherSample`؛ grep `goToDate|scrollToDateTime`: هیچ |
| ۲۴ | جابه‌جاییِ محدودهٔ دید (range buttons) | ۹ دکمهٔ `1D…All` + `scrollToRealTime` | `setVisibleRange` درِ اینترفیس ولی بی‌پیاده درِ هر دو آداپتور | DONE / NOT STARTED | `date-ranges-tabs` (۷ تب) | `lib/timeframe.ts:121,133-147` ⇔ `KLineChartWrapper.tsx:2717-2729`, `:540-550`؛ `engine/ChartEngine.ts:67` |
| ۲۵ | تمام‌صفحه و اسنپ‌شاتِ PNG | هست | ندارد | DONE | NOT OBSERVED | `KLineChartWrapper.tsx:2430-2440`, `:2404-2427` |
| ۲۶ | بازپخشِ کندل (Bar Replay) | هست (نوار + استور + سرعت‌ها) | ندارد | DONE | NOT OBSERVED | `components/ReplayBar.tsx`، `stores/replayStore.ts`، `lib/replay.ts` |

### پ. کراس‌هیر، محور و خوانش

| # | قابلیت | KLineCharts | ffc | حکم | مرجع | شاهد |
|---|---|---|---|---|---|---|
| ۲۷ | کراس‌هیر (سبک/خط‌چین/روشن‌خاموش) | هست، ازِ تنظیمات | `onMove` پیاده، ولی بی‌مشترک درِ پنل | DONE / NOT STARTED | NOT OBSERVED | `KLineChartWrapper.tsx:1242-1264`, `:1138-1141`, `:16-25`؛ `FastFinancialChartsEngine.ts:162,485-495`؛ تنها مصرف‌کننده `EnginePane.tsx:230-239` |
| ۲۸ | خوانشِ OHLC درِ وضعیت/tooltip | هست (`none|always|follow_cross`) + مقادیرِ اندیکاتور | ندارد | DONE | `legend-show-hide-action` | `KLineChartWrapper.tsx:1202-1208`, `:128-131`, `:1272-1282` |
| ۲۹ | مقیاسِ خطی/لگاریتمی/درصدی + دکمه‌هایِ `%`/`log`/`auto` | هر سه، با گاردِ دوباره‌تبدیلِ نکردنِ سریِ تعدیل‌شده | `priceScaleMode` | DONE | `auto`/`logarithm`/`percentage` **دیده شد** | `KLineChartWrapper.tsx:1316-1333`, `:120-121`, `:2669-2704`, `:2376-2387`؛ `FastFinancialChartsEngine.ts:299-301` |
| ۳۰ | معکوس/جایگاهِ محور (راست/چپ، داخل/خارج) | هست | آداپتور ندارد | DONE | NOT OBSERVED | `KLineChartWrapper.tsx:1285-1287`, `:956-959` ⇔ `ChartSettingsDialog.tsx:385-396` |
| ۳۱ | محورِ جلالی + تایم‌زونِ تهران | هست (formatters + `setTimezone`) | **صریحاً نه** (`jalaliAxis:false`) و به کاربر اعلام می‌شود | DONE / NOT STARTED | `time-zone-menu` **دیده شد** | `KLineChartWrapper.tsx:160-174`, `:961-964`, `:1312-1314`؛ `FastFinancialChartsEngine.ts:119-121` ⇔ `FtsEngineChart.tsx:238` |
| ۳۲ | گامِ برچسبِ محورِ قیمت (tick step / minmov) | فقط دقتِ اعشار (`pricePrecision`)؛ گامِ کنترل‌شده نیست | formatters دارد، گام نه | PARTIAL | `pricescale`/`minmov` درِ پاسخِ مرجع (§۲-الف) | `KLineChartWrapper.tsx:133-136`, `:994-998`, `:1363-1375` |
| ۳۳ | «حاشیۀ برچسبِ محورها» درِ تنظیمات | دکمه هست، **رفتار ندارد** | ندارد | NOT STARTED | — | `ftsConfigStore.ts:41` ⇔ `ChartSettingsDialog.tsx:420-426`؛ بی‌مصرف (§۴-D1) |
| ۳۴ | شکافِ نشستِ معاملاتی رویِ محور (session breaks) | ندارد | ندارد | NOT STARTED | `session:"7;0900-1330:12347"` یعنی مرجع نشست می‌داند؛ اینکه شکاف می‌گذارد یا نه **NOT OBSERVED** | نبودِ `sessionBreak`؛ آگاهیِ تقویمی فقط درِ باکت‌بندی (§۳-د ردیف ۴۱) |
| ۳۵ | واترمارک + «سایۀ خاکستری» | دکمه‌ها هست، **رفتار ندارد** | ندارد | NOT STARTED | — | `ftsConfigStore.ts:53,69,70` ⇔ `ChartSettingsDialog.tsx:473-480`, `:508-518`؛ `showWatermark`/`watermarkOpacity`/`wickGray` بی‌مصرف |

### ت. کندل، داده و تایم‌فریم

| # | قابلیت | KLineCharts | ffc | حکم | مرجع | شاهد |
|---|---|---|---|---|---|---|
| ۳۶ | نوعِ نمایش: توپر/توخالی/OHLC-bars/خط/سطح/Heiken-Ashi | ۵ گزینه درِ نوار، ۸ درِ تنظیمات | نگاشتِ ۵تایی | DONE | NOT OBSERVED (`default_chart_type_id` درِ پاسخِ نماد هست، مقدارش درِ این اجرا ثبت نشد) | `FtsToolbar.tsx:94-100` ⇔ `KLineChartWrapper.tsx:1949-1959`, `:1100-1110`؛ `ChartSettingsDialog.tsx:25-34`؛ `lib/chartTypes.ts:44-63` |
| ۳۷ | Renko / Kagi / PnF | ریاضی + تست دارد، **هیچ‌جا صدا نمی‌شود** | ندارد | NOT STARTED | NOT OBSERVED | `lib/chartTypes.ts:69-132,140-199` + `__tests__/technical-chart-types.spec.ts:85,102`؛ `KLineChartWrapper.tsx:531` فقط `heikin_ashi` را می‌گیرد |
| ۳۸ | Baseline (RGBaseline) | ندارد | ندارد | NOT STARTED | NOT OBSERVED | نبودِ `baseline` درِ `features/technical` |
| ۳۹ | کندلِ روزانۀِ درست (سقف/کف/باز/بستن، حجم، روزِ تعطیل، idempotency) | متصل به زنجیرۀِ canonical | همان سری را می‌گیرد | DONE | تطبیقِ زندهٔ type7/type0 درِ Phase 5 انجام شد | گیت `_audit/PHASE5-GATE-RUNALL-FINAL2.txt` سطرهایِ ۳۴-۴۲، ۷۷-۸۴؛ گزارشِ Phase 5 §۷-§۹ |
| ۴۰ | تعدیلِ عملکردی + مبنایِ قیمت (آخرین/پایانی) + اعلامِ صریحِ مبنا | `priceBasis`/`priceBasisRequested`/`priceBasisReason`/`lastDataTime`/`payloadAgeS` | ازِ همان payload | DONE (با بازمانده‌هایِ مستندِ §۱۳ Phase 5) | `configs.adjustments`/`price_types` **دیده شد** | `api/chart.py` `_stamp_data_time`/`_attach_live_bar`/`_chart_cache_key` (کامیت `415c82b`)؛ `api/market.py:1440-1462` |
| ۴۱ | تایم‌فریم: روزانه/هفتگی/ماهانه با باکتِ شنبه‌محور | `SUPPORTED_TIMEFRAMES=['D','W','M']` + تجمیعِ سمتِ کلاینت + `_fts_resample` سمتِ سرور | باکت‌هایِ آماده می‌گیرد | DONE | `D`,`W`,`M` و `3M/6M/12M` درِ مرجع | `lib/timeframe.ts:11,61-71,78-118` ⇔ `KLineChartWrapper.tsx:520-523`؛ `api/chart.py:1798-1838` (`:1824`)؛ duplicate: `lib/resample.ts:13-48` |
| ۴۲ | تایم‌فریمِ درون‌روز (۱…۲۴۰ دقیقه) | **ممکن نیست، صریح اعلام می‌شود** (`INTRADAY_CAPABILITY.supported:false` + fallback `D` + پیامِ UI) | همان قید | BLOCKED | ۹ بازۀِ دقیقه‌ای درِ مرجع، از APIِ خودِ مرجع (§۲-الف) | `lib/timeframe.ts:22-29,39-52` ⇔ `KLineChartWrapper.tsx:2553-2561`؛ `features/technical/engine/types.ts:84-88`. **سورسِ داده اندازه‌گیری شد:** `docs/fts-notes/LIVE_HOT_STATE.md:192` «نوزده مسیرِ آزموده‌شدۀ مرده» + اجرایِ مجددِ این دور `_audit/INTRADAY-SOURCE-PROBE-2026-10-14.txt` → ۹ نامزدِ تازه: هشت `200` با بدنهٔ HTMLِ ۸۲۴ بایتیِ ضدربات و یکِ `404`/`404`… نتیجه: **«زنده‌هایِ دقیقه‌ای: هیچ»**. دور زدنِ کنترلِ امنیتی مجاز نیست |
| ۴۳ | قاعدۀ «تحلیل رویِ روزانه/هفتگی، نه رویِ دقیقه» | حفظ شده | حفظ شده | DONE | — | `docs/MASTER-EXECUTION-ROADMAP.md:2405` (C-1، مالک)، `:2468` (X-4)؛ باکتِ شنبه درِ `timeframe.ts:66-71` |

### ث. اندیکاتورها و لایه‌هایِ تحلیلی

| # | قابلیت | KLineCharts | ffc | حکم | مرجع | شاهد |
|---|---|---|---|---|---|---|
| ۴۴ | منویِ اندیکاتور + افزودن/حذفِ واقعی | هست (pane/overlay)؛ منو فقط نام‌هایِ **واقعاً رجیسترشده** را می‌دهد | UI ندارد | DONE / NOT STARTED | `open-indicators-dialog` **دیده شد**، فهرستش NOT OBSERVED | `KLineChartWrapper.tsx:2350-2374`, `:388`, `:2800-2805`؛ `FastFinancialChartsEngine.ts:348-369` |
| ۴۵ | مطالعاتِ سبک TradingView + سبک رهاورد/مبننا | ۱۰ تا TV + ۹ تا Mabna، merge (نه replace) | ازِ همان spec | DONE | — | `lib/tvIndicatorCatalog.ts:15-27` (۱۰ نام)، `:38-49` (۹ نام)؛ رجیستری `KLineChartWrapper.tsx:916-943` |
| ۴۶ | پارامترهایِ اندیکاتور | مسیرِ زنده دارد | تک‌عدد → `{period}`، بقیه صریحاً رد + لاگ | PARTIAL | NOT OBSERVED | `FastFinancialChartsEngine.ts:501-508` (`indicator-params`) |
| ۴۷ | لایه‌هایِ FTS (فیب، موج، ساختار، نقطه، رویدادهایِ شرکتی) رویِ هر دو رندرر | متصل | `engineFtsLayers.applyOverlays` | DONE | — | `KLineChartWrapper.tsx:1452-1800` + `:188-282`؛ `lib/engineFtsLayers.ts:83+` ⇔ `FtsEngineChart.tsx:154-195` |
| ۴۸ | همسنجی (Compare) با نمادِ دوم | هست، با حالتِ «بدونِ بارِ مشترک» | ندارد | DONE | NOT OBSERVED | `FtsToolbar.tsx:273-344`؛ `lib/compareIndicator.ts` (headless درِ `:974-983`) |
| ۴۹ | هشدارِ قیمت (Alerts) | هست | ندارد | DONE | NOT OBSERVED | `FtsToolbar.tsx:425-451` |

### ج. موتورِ دوم و سازگاریِ RTL/ریسپانسیو

| # | قابلیت | KLineCharts | ffc | حکم | مرجع | شاهد |
|---|---|---|---|---|---|---|
| ۵۰ | نوارِ ابزار درِ موتورِ دوم | — | **هیچ نوارِ ابزاری ندارد**؛ فقط نوارِ وضعیت | NOT STARTED | مرجع تک‌موتوری است و این شکافِ ما است | `FtsEngineChart.tsx:222-250`؛ `TechnicalPage.tsx:265-279` |
| ۵۱ | تراکنشِ موتور برایِ چارتِ زنده | آداپتور نوشته شده ولی چارتِ زنده دورش می‌زند | استفاده می‌شود | PARTIAL | — | `engine/klinecharts/KLineChartsEngine.ts:503-555`, `:446-491` ⇔ `KLineChartWrapper.tsx:955` importِ مستقیم |
| ۵۲ | RTL سند + LTRِ عمدیِ بوم و ریلِ چپ | هست و قاعده‌مند | پنِ آزمایشگاه | DONE | مرجع RTL است (نوارهایِ فارسی) | `frontend/index.html:2`؛ `KLineChartWrapper.tsx:2496`؛ `styles/tvTheme.css:101-103,120`؛ `nahayatnegar/styles/nahayatNegarStyles.css:48,232-233,320-321,359` |
| ۵۳ | Breakpoint برایِ کرومِ چارت | فقط پنج `xl:/lg:/md:` Tailwindی؛ **صفر `@media`** درِ دو فایلِ CSSِ چارت؛ مدیریتِ سرریز با nowrap | همان | PARTIAL | ریسپانسیو/موبایلِ مرجع درِ این دور کاوش نشد | `TechnicalPage.tsx:256`؛ `FtsToolbar.tsx:138`؛ `EnginePane.tsx:403`؛ `EngineLabPage.tsx:248`؛ `PatternToggles.tsx:15`؛ `useMediaQuery.ts:20` تنها مصرف‌کننده‌اش `Sidebar.tsx:78` |
| ۵۴ | اندازه‌گیریِ دوبارۀِ ریزشِ چارت (resize/fullscreen) | `ResizeObserver` + دورِ دومِ ۲۲۰ms برایِ انیمیشنِ سایدبار | `KLineChartsEngine.ts:270-272,336-342` | DONE | — | `KLineChartWrapper.tsx:1022-1050` |
| ۵۵ | رفتارِ موبایل/تاچِ چارت | اندازه‌گیری نشد | — | UNVERIFIED | کاوش نشد | هارنس‌هایِ مرورگریِ این دور رویِ Edge دسکتاپ بودند؛ دستگاهِ واقعی درِ این دور وصل نبود |
| ۵۶ | مسیرِ fetch درِ حالتِ آفلاین/موبایل | `BASE` محلی؛ پاسخِ degraded علامت می‌خورد | همان | DONE | — | `"degraded": True` و `historyRepairScheduled` درِ `api/chart.py`؛ گیتِ `live candle … cache untouched` ۴۶/۴۶ |

**جمعِ ماتریس (۵۶ سطر؛ شمارشِ خودِ ستونِ «حکم» با اسکریپت، نه حدس):** DONE **۲۵** (شاملِ `DONE (محلی)` برایِ ماندگاریِ رسم‌ها و `DONE (با بازمانده‌هایِ §۱۳ Phase 5)` برایِ تعدیل) · NOT STARTED **۱۸** · PARTIAL **۶** · BLOCKED **۱** (#۴۲، سورسِ دقیقه‌ای) · UNVERIFIED **۱** (#۵۵، تاچ/موبایل) · سطرهایِ ترکیبی که درِ دو موتور فرق می‌کنند **۵** (`DONE / NOT STARTED` ×۴، `DONE / PARTIAL` ×۱). هیچ سطری با «حذفِ ادعا» بسته نشد؛ هیچِ عددی ازِ سندِ قدیم نقل نشد مگر با بازرسیِ کد یا DOM درِ همین دور.

---

## ۴. نقص‌هایِ واقعی که ممیزی پیدا کرد (کارِ این دور **نبود**، ثبت شد)

قیودِ مأموریت می‌گویند «هیچ دکمه یا ابزاری را به‌صورتِ mock و بدونِ رفتارِ واقعی تحویل نده» و «موتورِ تعدیل یا داده را صرفاً برایِ پاس‌شدنِ تست دست‌کاری نکن». شش موردِ اول نقضِ صریحِ بندِ اول‌اند:

| # | نقص | چرا نقص است | شاهد |
|---|---|---|---|
| D-1 | **۵ کنترلِ زنده درِ «تنظیماتِ چارت» هیچ رفتاری ندارند**: قفلِ درگِ محور، حاشیۀ برچسبِ محورها، سایۀ خاکستری، نمایشِ واترمارک، شفافیتِ واترمارک. مقدارشان ذخیره و درِ localStorage می‌نشیند، ولی هیچ‌جایِ کدِ چارت خوانده نمی‌شود. | دکمۀِ بی‌نتیجه = mock؛ کاربر فکر می‌کند اعمال شده. بدتر: برچسبِ خودِ ردیف می‌گوید «درِ موتورِ lightweight اعمال می‌شود» درحالی‌که آن موتور درِ `registry.ts` اصلاً وجود ندارد. | `ftsConfigStore.ts:39,41,53,69,70,96,97,108,124` ⇔ `ChartSettingsDialog.tsx:406-412,420-426,473-480,508-518`؛ بازرسیِ مصرف: `grep -rlE <نام>` فقط store+dialog را می‌دهد |
| D-2 | **۳ فیلدِ خوابیده درِ استور** (`showXAxis`، `showYAxis`، `splitLayout`) — نه مصرف‌کننده دارند نه حتی کنترلِ UI. | stateِ بی‌مصرف؛ ردیفِ «کنترلِ مرده» نیست ولی همان آلودگیِ قرارداد است. | `ftsConfigStore.ts:56,57,59,111,112,113` |
| D-3 | **چنگالِ اندروز عملاً وجود ندارد ولی درِ منو هست**: `id:'pitchfork'` ⇐ `overlayType:'parallelChannel'`. | اسمِ گمراه‌کننده؛ تطبیقِ مرجع را درِ گزارش‌هایِ بعدی غلط می‌کند. | `DrawingToolbar.tsx:94`؛ آیکونِ بی‌مصرف `TradingViewIcons.tsx:273` |
| D-4 | **سه فهرستِ ابزار درِ مخزن، یکی مرده**: `drawingTools.ts` (`DRAWING_CATALOG`، `buildDrawingGroups`، ذخیرۀِ presetها `fts.tool.defaults.v1`) فقط توسطِ سه specِ تست مصرف می‌شود؛ UIِ زنده `DrawingToolbar.tsx` را می‌سازد؛ سومی `tvToolList.ts` است. | دو منبعِ حقیقتِ موازی (ممنوع: «ازِ state موازیِ غیرضروری برایِ دو موتور اجتناب کن»)؛ تست‌ها رفتاری را سبز نگه می‌دارند که درِ محصول نیست. | `lib/drawingTools.ts:12-67,70,88,101-124`؛ مصرف‌کننده‌ها فقط `__tests__/technical-draw-catalog.spec.ts:4`, `technical-toolbar.spec.tsx:9`, `technical-tv-tools.spec.ts:5` |
| D-5 | **تراکنش‌هایِ ffc با صفر call site**: `beginDrawing`, `listDrawings`, `removeDrawing`, `updateDrawing`, `clearDrawings`, `onDrawingsChanged`, `FFC_DRAW_TOOLS`، و `setVisibleRange` که هیچ‌یک ازِ دو آداپتور پیادهش نکرده‌اند. `setScrollEnabled` هم کلیدی می‌نویسد که درِ تایپِ vendor آن (`wheelZoom/dragPan/…`) نیست → no-op خاموش. | API‌ای که وجود دارد ولی چیزی صدا نمی‌زند؛ بدترینش no-opِ **خاموش** است (هیچ خطایی نمی‌دهد). | `engine/ChartEngine.ts:67,93-98`؛ `FastFinancialChartsEngine.ts:290-292,382-391,518-520`؛ vendor: `frontend/node_modules/@pairlens/fast-financial-charts/dist/esm/types/theme.d.ts:113-122` |
| D-6 | **ناهمخوانیِ نامِ محورِ log بینِ دو مسیر**: چارتِ زنده `'logarithm'` می‌فرستد، آداپتورِ KLineCharts `'log'`. | آداپتورِ رجیستری با همان تنظیمِ کاربر رفتارِ چارتِ زنده را ندارد؛ یکی ازِ دو مسیر بی‌اثر است. | `KLineChartWrapper.tsx:1330,2385` ⇔ `engine/klinecharts/KLineChartsEngine.ts:360-369` |
| D-7 | **`rect` درِ UI به دو سرنوشتِ متفاوت می‌رود**: v10 overlayِ `rect` ندارد، پس یک `btsBand` دستِ خود و یک fallbackِ `priceChannelLine` ساخته شده؛ کار می‌کند چون `react-klinecharts-ui` قالبش را می‌دهد. | شکنندگیِ وابستگی؛ اگر قالبِ vendor بیاید، رفتارِ «مستطیل» عوض می‌شود. | `KLineChartWrapper.tsx:292-307`؛ `KLineChartsEngine.ts:41-84` |
| D-8 | **دیتایِ دقیقه‌ای: فقط قفلِ سورس، نه قفلِ UI** | حتی با UI، کندلِ دقیقه‌ای داده ندارد. §۳-ت ردیف ۴۲ (۱۹ + ۹ مسیرِ مرده، اندازه‌گیریِ امروز). | `LIVE_HOT_STATE.md:156,167,179,192`؛ `_audit/INTRADAY-SOURCE-PROBE-2026-10-14.txt` |
| D-9 | **تناقضِ شمارِ سوئیتِ گیت درِ دو سند** (§۱-ت) | گزارشگریِ عددی بدونِ بند کردن به شاهد؛ خودش نقضِ «هر ادعا یکِ کامیت/تست/اندازه» است. | `MASTER-EXECUTION-ROADMAP.md:2740-2744`؛ `FTS-MISSION-CLOSURE-1405-07-20.md:36` |

---

## ۵. آنچه عمداً **دست نخورد**

| مورد | چرا دست‌نخورده ماند |
|---|---|
| موتورِ تعدیلِ canonical، `adjustment_engine.py`، `corporate_ledger.py`، `api/chart.py` | Phase 5 همین حالا بست (`415c82b`)؛ هر تغییرِ دوباره باید با شاهدِ تازه باشد، نه با ذائقۀِ دورِ چارت |
| ابزارهایی که درِ مرجع ندیدیم ولی درِ ما هستند (گن، XABCD، الیوت، بادبزنِ فیبو، بازپخش، همسنجی، هشدار) | قیدِ مأموریت: «ابزارهایی که درِ رهاورد مشاهده نشده‌اند اما درِ BorsTerminal وجود دارند، حذف نکن». هیچ‌کدام حذف نشد |
| فهرستِ ۲۷ ابزارِ زنده و ۸ گروه | قید: «وجودِ خط روند/افقی/کانال/فیب/چنگال را از پیش قطعی فرض نکن» — برعکسش هم رعایت شد: چیزی که نبود را «هست» ثبت نکردیم، و چیزی که هست را برایِ شباهتِ ظاهری برنداشتیم |
| تایم‌فریمِ تحلیل (روزانه/هفتگی) | قاعدۀِ مالک (`roadmap:2405`, `:2468`)؛ افزودنِ دقیقه‌ای اگر روزی آزاد شود **نمی‌تواند** تایم‌فریمِ داوری را جابه‌جا کند |
| `app_log.txt`، `fts_v10_payloads.json`، `_audit/RA365-LEDGER-RULE…csv`، `_audit/RA365-PHASE3-DERIVE…csv` | محیط/متعلق به دورهایِ دیگر؛ stage یا پاک نشدند |

---

## ۶. آمادگیِ Stage 1 تا 10 — چه چیزی بدونِ مجوزِ جدید قابلِ ادامه است

| مرحلۀِ مأموریت | حکمِ این دور |
|---|---|
| ۱ (تطبیقِ صحتِ کندل/مقیاس/تعدیل) | قابلِ ادامه درِ همان چارت؛ اما Phase 5 همین را بست و رگرسیونش سبز است. درِ این دور فقط بازتأییدِ خواندنی شد (§۳-ت ۳۹-۴۰) |
| ۲ (فهرستِ ابزارهایِ مرجع، ریز) | **BLOCKED** تا یکِ layoutِ یک‌بارمصرف یا مجوزِ صریح (§۲-پ، §۷) |
| ۳ (تعاملِ ماوس/اسکرول/زوم/پن) | **BLOCKED** برایِ سمتِ مرجع (همان دلیل)؛ سمتِ خودی قابلِ اندازه‌گیری است (`bors_phase5_e2e.js` زیرِ pan/zoom را بی‌خطا سنجید) |
| ۴ (کراس‌هیر/محور/خوانش) | نیمه‌باز: سمتِ خودی اندازه‌گیری‌شدۀِ قبلی؛ سمتِ مرجع کاوشِ بیشتر می‌خواهد |
| ۵ (دقتِ کندل و types) | قابلِ ادامه؛ سه ردیفِ ماتریس (#۳۷،#۳۸،#۷) شکافِ واقعی‌اند |
| ۶ (اندیکاتورها/لایه‌ها) | قابلِ ادامه؛ `ffcParams` و نبودِ UIِ ffc (#۴۴،#۴۶،#۵۰) شکاف‌ها |
| ۷ (ریسپانسیو/RTL) | قابلِ ادامه؛ #۵۳،#۵۵ |
| ۸ (موتورِ دوم) | نیازمندِ تصمیمِ مالک: یا ffc کامل شود (نوارِ ابزار/رسم/کراس‌هیر) یا ازِ انتخابِ کاربر برداشته شود تا «موتورِ دومِ نصفه» تحویلِ کاربر نشود (#۵۰،#۵۱،D-5) |
| ۹ (گیت‌ها + تستِ مرورگریِ خودی) | آماده؛ الگویِ ثابت‌شده: `dev/phase5_isolated_server.py` + `_audit/bors_phase5_e2e.js` (۳۳ سنجه، بانکِ کپی) |
| ۱۰ (گزارش/کامیت) | همین سند |

---

## ۷. آنچه ازِ مالک می‌خواهم (بدونِ این‌ها، دورهایِ بعدی جعل می‌شوند)

1. **مجوزِ شروعِ کارِ تداخل‌زا رویِ چارت.** گیتِ `roadmap:9`/`:2310`/`:2426` تا بستۀ شدنِ Funnel (X-7) و Auto-Update کدال، جلویِ بازنویسیِ UI/تعاملِ چارت را می‌گیرد. یا بگویید «X-7/Auto-Update را فعلاً ازِ گیتِ این مأموریت مستثنا کن» تا Stages 2–8 اجرا شوند؛ یا اولِ آن دو را ببندیم.
2. **یکِ layoutِ یک‌بارمصرف درِ رهاورد ۳۶۵** (یا «اجازه داری جایِ اسکرولِ چارتِ فعلی عوض شود»). بدونِ این، فهرستِ ریزِ ابزارها و رفتارِ زوم/پن/اسکرولِ مرجع **هیچ‌وقت** اندازه‌گیری نمی‌شود و ماتریسِ §۲-پ تا ابد `NOT OBSERVED` می‌ماند. (AutoSave روشن است؛ «All changes saved» درِ نوارِ مرجع دیده شد.)
3. **تکلیفِ کندلِ دقیقه‌ای.** مرجع ۹ بازۀِ دقیقه‌ای دارد؛ TSETMC ازِ این ماشین هیچ‌کدام را نمی‌دهد (۲۸ مسیرِ مرده، جمعاً). سه راه: (الف) پذیرشِ «فقط D/W/M» و اصلاحِ ادعاها؛ (ب) خرید/اتصالِ سورسِ مجازِ دقیقه‌ای؛ (ج) استفاده از APIِ خودِ رهاورد به‌عنوانِ سورسِ داده که تصمیمِ تجاری/حقوقی است نه فنی. من هیچ‌کدام را خودسرانه انتخاب نمی‌کنم و کنترلِ امنیتی را هم دور نمی‌زنم.
4. **تکلیفِ موتورِ دوم (`ffc`).** کامل شود یا ازِ منویِ انتخابِ کاربر بیرون رود؟ (هم‌اکنون بی‌نوارِ ابزار، بی‌رسم، بی‌کراس‌هیر-خوانش و بی‌محورِ جلالی است؛ خودش صریح اعلام می‌کند.)
5. **تکلیفِ هفت کنترلِ بی‌رفتار (D-1،D-2،D-3).** رفتاری‌شان می‌کنم یا ردیفشان ازِ تنظیمات حذف می‌شود؟ (هیچ‌کدام را خودسرانه حذف نکردم: «قابلیت‌هایِ موجود را حذف نکن مگر…»)
6. **بستنِ تناقضِ شمارِ گیت (D-9).** سطرهایِ `roadmap:2740-2744` و `FTS-MISSION-CLOSURE…:36` را با شاهدِ امروز (`_audit/PHASE5-GATE-RUNALL-FINAL2.txt`: ۱۲۳/۱۲۳) هم‌خط کنم؟ (سندِ مأموریتِ دیگری است؛ خودسرانه عوضش نکردم.)
7. **مجوزِ push/merge/tag.** تا امروز هیچ‌کدام انجام نشده؛ branch `mission/fts-indicator-engineering` رَسِ `415c82b` است و ازِ `origin/main` ۳۶ کامیت جلوتر.

---

## ۸. حکمِ Stage 0

گیت بسته نشد: **Fundamental/CODAL** `NOT COMPLETE` است (X-7 `OPEN - BLOCKING`، که نیمۀ دومش — `tapeFilterVerdict:411` — همین حالا درِ کد زنده است) و **Auto-Update کدال** درِ عمل ساخته نشده (صفر زمان‌بند؛ خزنده درِ EXE با `api/_core.py:29` خاموش؛ ریلانچرش فایلِ `run_discovery.sh`ِ موجودنداشته را صدا می‌زند). بنابراین درِ این دور **هیچِ تغییرِ تداخل‌زایِ چارت شروع نشد** و تحویل، همین ممیزیِ خواندنی + ماتریسِ شکاف + دو هارنسِ کاوشِ غیرمخرب است.

ماتریس، ۵۶ سطرِ قابلیت با شاهدِ `file:line` یا فایلِ DOM/API، می‌گوید: نقطۀِ قوتِ ما ابزارهایِ رسمِ متصل و ماندگار (۲۷ ابزار درِ ۸ گروه، آهن‌ربا/قفل/پنهان/حذف/اندازه‌گیر، undo/redo، قالبها) و مقیاسِ log/percent و محورِ جلالی با تایم‌زونِ تهران و تعدیلِ شفاف است. نقاطِ شکافِ واقعی: (۱) تعاملِ قابلِ تنظیمِ زوم/اسکرول و نبودِ میان‌برها/راست‌کلیک/Go-to-date/درختِ اشیاء/Stay-in-drawing-mode؛ (۲) **هر** چیزی ازِ موتورِ دومِ چارت به‌جزِ رندرِ داده و لایه‌هایِ FTS؛ (۳) کندلِ دقیقه‌ای که نه UI دارد نه سورس؛ (۴) هفت کنترلِ بی‌رفتار و برچسبِ «چنگال»ِ گمراه‌کننده؛ (۵) سه فهرستِ ابزارِ موازی که یکی مرده است؛ (۶) ریسپانسیوِ کرومِ چارت که فقط پنج کلاسِ Tailwind است و صفر `@media`.

و یکِ اعترافِ روشنی: فهرستِ ریزِ ابزارهایِ مرجع و رفتارِ زوم/پنِ مرجع **دیده نشد**؛ چون دیدنشان یعنی دست‌زدن بهِ چارتِ AutoSave‌دارِ شما. عددِ «تطبیقِ UI» برایِ دورهایِ بعدی ازِ این سند **نمی‌آید**؛ ازِ اندازه‌گیریِ واقعی بعد ازِ مجوزِ §۷-۲ خواهد آمد.
