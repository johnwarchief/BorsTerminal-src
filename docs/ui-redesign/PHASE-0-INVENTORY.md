# فاز صفر — انبارِ واقعیِ رابط (PHASE-0 INVENTORY)

**بیسِ سنجش:** `.worktrees/uiux-2-0` @ `mission/uiux-2-0-redesign-2026-10-16` = `ff6b2fb41a38b8e9acc2183d6ee7fa4e07a798d0` (۵۴ کامیت جلوتر ازِ `main`، صفرِ عقب‌مانده؛ `git rev-list --left-right --count main...HEAD` = `0 54`)
**تاریخ:** ۱۴۰۵-۰۷-۲۴ / ۲۰۲۶-۱۰-۱۶
**روش:** خواندنِ سورسِ فعلی. نسخۀِ پیشینِ اینِ سند رویِ اینِ ماشین وجود نداشت (رویِ ماشینِ PCMOD نوشته شده بود)، پس اینِ فایل **ازِ کدِ اینِ بیس** ساخته شده، نه ازِ بازخوانیِ آن.

> سطرِ «راستی‌آزمایی‌شدہ باِ اجرا» درِ اینِ سند **نداریم**: اینِ فاز فقطِ خواندن بود، بیِ bootِ Vite/FastAPI. حالت‌های loading/error/empty ازِ کد خوانده شده‌اند، نه ازِ رفتارِ دیدنی.

## ۱) ناوبریِ واقعی

`createHashRouter` (`main.tsx:18`) ⇒ همه‌چیز `#/<path>`. `routes.tsx` تنها `RouteObject[]` است.

| path | element | نماد درِ path | نکته |
|---|---|---|---|
| `''` | `<Navigate to="/master">` | — | redirect باِ رأیِ مالکِ ۱۴۰۵-۰۷-۱۷ |
| `market` | `MarketPage` | ✗ | تابلوخوانی/غربالگری |
| `market-status` | `MarketStatusPage` | ✗ | هشت بخشِ Binder1 |
| `notifications` | `NotificationsPage` | ✗ | ازِ ناوبری بیرون، ازِ زنگِ Topbar باز می‌شود |
| `fundamental/:symbol?` | `FundamentalPage` | ✓ | دو حالتِ بی‌نماد/باِنماد |
| `technical/:symbol?` | `TechnicalPage` | ✓ | سنگین‌ترین صفحۀِ برنامه |
| `engine-lab` | `EngineLabPage` | ✗ | ابزارِ توسعه، بی‌منو |
| `strategy-tree/:symbol?` | `StrategyTreePage` | **اعلامی وِ ناخوانده** | `routes.tsx:40` دربرابرِ فایلِ ۱۲ سطری |
| `portfolio` | `PortfolioPage` | **✗ وِ نداشتنش نقص است** | بلوکِ سیگنالِ نماد درِ `:248-265` باِ URL قابلِ دسترس نیست |
| `watch` | `WatchMarketWorkspace` | ✗ | یکِ *کامپوننت* به‌عنوانِ elementِ route |
| `master/:symbol?` | `MasterPage` | ✓ | پروندۀِ یکپارچۀِ نماد |
| `*` | not-found درون‌خطی | — | `routes.tsx:56-67` |

**صفرِ مسیرِ `execution`، `orders` یا `trade` درِ اینِ بیس** (`grep` + `find`؛ سندِ Antigravity آن‌ها را رویِ `c0402614` گزارش کرده وِ `api/execution.py`/`api/bot.py` درِ اینِ ماشین فقط درِ شاخۀِ `mission/windows-stable-release-2026-10-15` هستند).

## ۲) پوسته

`AppShell.tsx:63-82` = Sidebar + Topbar + SymbolContextStrip + `<Outlet>` + SymbolInspector + CommandPalette؛ دروازۀِ `LoginScreen` درِ `:57`. `FtsPipelineBar` کامل است ولی باِ `SHOW_FTS_PIPELINE_BAR = false` خاموش (`:21,:72`).

- Sidebar: ۳ گروه / ۷ مقصد (`Sidebar.tsx:36-73`)؛ `NAV_SECTIONS` ازِ همانِ فایل exported است تاِ آزمودنی باشد.
- Topbar: breadcrumb (`:53-58`) + سوییچرِ سریعِ pinned (`:63-81`) + زنگِ اعلان (`:116-131`).
- SymbolContextStrip: pin، نام/صنعت/وضعیت، قیمتِ زنده، قدرتِ خریدار، سهمِ حقیقی/حقوقی، ششِ پرش (`SymbolContextStrip.tsx:33-197`).

## ۳) حالتِ نماد — سه واگراییِ اثبات‌شدہ

منبعِ حقیقت: `useSymbolStore.symbol` (یکِ رشته) درِ `localStorage['bors-symbol']` (`symbolStore.ts:50-69`) باِ ۳۳ واردکننده + `recent(8)` + `pinned(16)`. یکِ store دومِ چندنمادی (`selectedSymbolsStore.ts`) فقط درِ دو اتمِ انتخاب مصرف می‌شود وِ contextِ صفحه نیست. کانالِ واقعیِ بینِ صفحۀ‌ای `signalStore`/`publishSignal` است (MasterPage `:111-113` به سیگنال‌هایِ tape/technical/fundamental/portfolio رأی می‌دهد).

| # | واگرایی | شاهد | پیامدِ دیدنی |
|---|---|---|---|
| ۱ | URL برندهٔ store است | `TechnicalPage.tsx:55`, `FundamentalPage.tsx:47`, `MasterPage.tsx:82` (`params.symbol ?? stored`) | `#/technical/شپنا` نمودارِ شپنا را نشان می‌دهد وِ strip همانِ نمادِ store را نام می‌برد |
| ۲ | نمادِ پیش‌فرضِ سخت‌کدشده | `TechnicalPage.tsx:59` `viewSymbol = symbol \|\| 'فولاد'` | بی‌انتخابِ کاربر، نمودارِ فولاد باِ legend فولاد رندر می‌شود؛ همینِ «مقدارِ ساختگی به‌جایِ نامعلوم» است که جزوه/قواعد رد می‌کنند |
| ۳ | `effective` ≠ store | `WatchMarketWorkspace.tsx:117-122` (`\|\| symbols[0]`) | خلاصه/دفترِ سفارش/پنلِ معامله نمادی را دنبال می‌کنند که strip آنِ را نگفته |

هیچِ دو-حالتیِ همزمانیِ نماد امروز ممکن نیست، چون یکِ رشتهٔ سراسری هست وِ تبی وجود ندارد.

## ۴) تبِ داخلی — داوری

**سیستمِ تبِ مرورگر-مانند وجود ندارد.** `shared/components/ui/tabs.tsx` (۱۱۰ سطر، `Tabs/TabsList/TabsTrigger/TabsContent`) **صفرِ مصرف‌کنندۀِ production** دارد (فقطِ `__tests__/vibafarsi-primitives.spec.tsx`)؛ `segmented-control.tsx` هم همین‌طور. سه الگویِ محلیِ بی‌ربط وجود دارد: تب‌هایِ FtsDock (پایینِ TechnicalPage)، زیرتب‌هایِ PortfolioPage (`useState`)، چرخشِ ۲صفحۀِ SymbolInspector؛ وِ `PageRotator.tsx` که خودکار می‌چرخد (فقطِ MarketStatusTicker). Sidebar یکِ ریلِ ناوبری است، نه تب. پس `tabs.tsx` یکِ **زیربنایِ آمادهٔ بی‌مصرف** است، ولیقرارداد آن (contextِ React + `value` رشته‌ای) برایِ تبِ چندمسیری کافی نیست (بیِ aria-controls، بیِ بسته‌شدن، بیِ roving tabindex).

## ۵) سیستمِ طراحی — چه هست وِ چه نیست

توکن = CSS custom properties + پلِ `@theme` تیلویند v4 (`index.css:9-72` ازِ `shared/styles/tokens.css`؛ بیِ `tailwind.config.js`). تم باِ `html[data-theme]` + `.dark/.light` (`uiStore.ts:23-32`)، override روشنِ رنگ‌ها `tokens.css:160-197`.

- رنگ: `--accent-blue/green/red/yellow/susp/susp-bg`، `--neon-cyan/red`، `--success/--warning/--destructive` (+ foregroundها)، `--hairline`، `--glass-*`.
- **واژگانِ «مثبت/منفی/خنثی/هشدار/خطا/نامعلوم» درِ سطحِ سیستم نیست.** تنها جزیش درِ `features/market/lib/tones.ts` است (`pos|neg|zero|nodata`)، آن‌جا هم دامنه‌اش «وضعیت بازار» وِ کلیدش ازِ پاسخِ سرور (`tone`) می‌آید. بقیه‌جایِ برنامه بی‌صدا ad-hoc است: `text-muted`، `Badge tone="gray"`، رشتهٔ «بدون داده»؛ `grep` برایِ `*-unknown` صفر.
- تایپوگرافی: `--fs-3xs…--fs-2xl` + `--text-nav`، Vazirmatn خودمیزبان (`index.html:7`)، `.num`/`.num-text` برایِ ارقامِ فارسی (`index.css:164,184`).
- گاردها: `dev/typography_guard.py` (درِ `run_all_tests.py:39`) وِ `dev/persian_glyph_guard.py` (`:380`)، وِ `__tests__/design-token-guard.spec.ts` که **فقطِ `accent-*`/`neon-*`** را می‌بیند ⇒ رنگِ بی‌تعریفِ هر خانوادۀِ دیگری silent غیب می‌ماند (تاریچۀِ باگِ `accent-amber`: ۳۳ مورد درِ ۸ فایل).
- RTL: `dir=rtl` یک‌بار درِ `index.html:2`. استفاده ازِ utilities منطقیِ غالب است (`ms-` ۸۳۵، `text-start` ۵۴، `end-` ۲۳) ولی ~۲۰ نشتِ فیزیکی مانده (`left-1`, `right-0`, `pl-3`, `ml-1`).

## ۶) تفکیکِ نقص: بک‌اند پنهان / رابطِ ناقص / دادهٔ مفقود

**A) درِ بک‌اند هست، رابطِ ما آنِ را صدا نمی‌زند** (هر کدام باِ `grep` درِ `frontend/src` تأییدِ بی‌مصرف‌بودن شد):

| مسیر | فایل |
|---|---|
| `/api/notify/status`, `test-telegram`, `test-bale`, `test-all` | `api/notify.py:16,35,42,49` |
| کنسولِ داده/سینک: `sync/delta\|backfill\|watchlist\|full\|pipeline` | `api/engine.py:22,30,37,44,64`، `api/_sync_market.py:69`، `api/_pipeline.py:47,52`، `api/_sync_codal.py:30,62,377,463,570`، `api/adb.py:19,47` |
| `market/sync-state`, `universe/live`, `price-basis` (GET+POST) | `api/market.py:118,1353,1440,1452` |
| `/api/ma/{symbol}`, `/api/patterns/{symbol}` (محاسبۀِ سروری؛ رابطِ ما محلی دوباره حساب می‌کند) | `api/chart.py:1681,1840` |
| `/api/fundamental/sectors` | `api/fundamental.py:1862` |
| `/api/diagnostics/info`, `/log` (فقطِ `log/open` مصرف می‌شود) | `api/diagnostics.py:39,53` |
| **`/api/mstat/board` — هشت پنل درِ یکِ درخواست** | `api/market_status.py:368` (وِ `snapshot` POST `:389`) |

**B) رابطِ موجود ولی ناکامل/خاموش:** پنلِ معامله درِ `WatchSummaryPanel.tsx:104-198` باِ دکمه‌هایِ `disabled={!gate.canTrade}` وِ Kill Switchِ همیشه‌disabled (`:183`)؛ `strategy-tree/:symbol?` ناخوانده؛ `portfolio` بی‌`:symbol?`؛ `tabs.tsx`/`segmented-control.tsx` بی‌مصرف؛ `FtsPipelineBar` خاموش؛ toggleِ اعلانِ ویندوز بی‌مسیرِ ارسال (`NotificationsPage.tsx:11-13`)؛ `PHASE_LABEL`/`ORDER_PHASES` درِ `orderClient.ts:46-62` کدِ غیرقابل‌دسترس (چون `phase` هرگز ازِ `idle` تکان نمی‌خورد، `WatchSummaryPanel.tsx:35`)؛ ~۲۰ نشتِ RTL.

**C) واقعاً داده/سرویس ندارد:** سرویسِ اجرایِ سفارش (`api/execution.py` نیست ⇒ `orderClient.ts:147` آدرسِ بی‌وجود را می‌زند وِ `source:'absent'` می‌گیرد؛ `WatchSummaryPanel.tsx:9` درست «سرویسِ اجرا نیست» را نشان می‌دهد)؛ هیچِ `BotPanel.tsx`/`botClient.ts` درِ اینِ مخزن؛ موجودیِ نقدِ کارگزاری (`capabilities.balances` هیچ‌وقت true نمی‌شود ⇒ `:134-141` «بی‌داده» که درست است)؛ شاخصِ درون‌روزی (ازِ سندِ رهاورد، بندِ ۶.۳)؛ داراییِ غیربورسی (طلا/سکه/تتر/انس/فارکس)؛ «قیمت وزنی ارزشی» وِ «تأثیر بر شاخص» که فرمولِ مستند ندارند.

## ۷) آنچه درِ بازطراحی نباید بشکند

- منطقِ FTS مطابق `docs/جزوه FTS.pdf` (ترتیبِ روندِ هفتگی←روزانه، تایم‌فریمِ روزانۀِ تحلیل، فیبو به‌عنوانِ زمینه، jet رویِ کندلِ بسته، موتورِ تعدیلِ فاز ۵F) — هیچِ تغییری درِ قواعد باِ مجوزِ بازطراحیِ UI مجاز نیست.
- قراردادِ `price_basis.py` / `candle_contract.py` / `codal_periods.py` (frozen، درِ `hiddenimports`).
- `fetch` بیرونِ `shared/api/http.ts` ممنوع؛ ارقامِ فارسی باِ `toFaDigits`/`.num`؛ هر `api/*.py` تازه ⇒ `fts_terminal.spec` → `hiddenimports`.
- آزمودنی‌هایِ ناحیه (نام‌هایِ تأییدشده باِ `ls` درِ `frontend/src/__tests__`، که درِ مجموع ۱۶۶ فایلِ spec دارد): `design-token-guard.spec.ts` · `market-gold-compare-chart.spec.tsx` · `market-status-mainwatch.spec.tsx` · `market-status-page.spec.tsx` · `market-status-sections.spec.tsx` · `market-status-ticker.spec.tsx` · `market-treemap-layout.spec.ts` · `vibafarsi-primitives.spec.tsx`. `trading-nav.spec.tsx` درِ اینِ بیس **نیست** (متعلقِ به شاخۀِ ۱.۰.۹۰ است).
