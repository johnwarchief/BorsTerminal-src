# مأموریت UI/UX 2.1 — انتقالِ انتخابی System 2، پولیشِ کلِ برنامه، نسخهٔ آزمایشی

تاریخ: ۱۴۰-۰۷-۵ (2026-10-17) · شاخه: `mission/uiux-polish-integration-2026-10-17`
کارِ انجام‌شده در worktree `_bors-sarkhati-tab` (دلیلش در بند ۰-پ). هیچ عددی درِ این
سند ازِ حافظه یا ازِ گزارشِ شاخۀِ دیگر نیامده؛ هرچه هست یا ازِ `git` است، یا ازِ
`vitest/tsc/build`، یا ازِ مرورگرِ زنده (`dev/uiux_audit_v1124.py`).

---

## ۰) فاز صفر — وضعیتِ Git، تأییدشده ازِ GitHub

`git fetch github` سپس `git ls-remote`؛ SHAها ازِ remote خوانده شدند، نه ازِ branchِ محلی:

| مرجع | SHA انتظار (سندِ مأموریت) | SHA تأییدشده ازِ `github` | رابطه |
|---|---|---|---|
| `main` | `c0402614…` | `c04026145769b316381997e6931ef07c9eb46a1d` | مبنایِ همه |
| `release/v1.0.91` | `79895345…` | تأیید شد | `main` + ۲۰ کامیت |
| `mission/sarkhati-close-gaps-2026-10-17` | `3a8693b3…` | تأیید شد | `main` + ۲۴ = `release/v1.0.91` + ۴ |
| `mission/market-status-parity-tradersarena-2026-10-17` | `f43eab54…` | **231cee55c50e697acf7d420a8157bfdfd8c9115b** | جابه‌جا شده: `f43eab54` جدِ آن است؛ دو کامیتِ تطبیقِ صف/پهنا رویِ آن نشسته |
| `mission/uiux-2-0-redesign-2026-10-16` (System 2) | `a3984f02…` | تأیید شد | ۶۶ جلو / ۱۰۲ عقب نسبتِ `main` ⇒ merge کورکورانه ممنوع |
| `mission/sarkhati-dedicated-tab-2026-10-17` | — | **35db2ad632b6a9623282b047ddd2abc69013eba8** | `3a8693b3` + ۳ (push شد و ازِ GitHub تأیید شد) |

`main` محلی (worktree `BorsTerminal-desktop` = `92703183`) **۱۶ کامیت عقب** است و
جدِ `github/main` — یعنی اگر ازِ آن branch می‌گرفتم، کارِ سه ماهه را می‌انداختم.

### ۰-پ) مبنایِ انتخابی و دلیلش

`mission/uiux-polish-integration-2026-10-17` ازِ `35db2ad6` ساخته شد، نه مستقیم ازِ
`3a8693b3`. دلیل: `35db2ad6` خودِ `3a8693b3` + سه کامیتِ تبِّ مستقلِ «سرخطی» است؛
پس مبنایِ ترجیحیِ مأموریت (بستنِ شکاف‌هایِ سرخطی) حفظ شده وِ کارِ رابطِ تازه هم
داخلش است — دو دلیلی که درِ بندِ ۰.۲ خواسته شده بود.

کار درِ worktree `_bors-sarkhati-tab` نشست، نه worktreeِ تازه: اینِ درخت تنها جایی است
که `node_modules` (junction)، `market.db`، `market.db.lzma` وِ زنجیرۀِ بیلدِ PyInstaller
رویِ آن آماده است. worktreeِ تازه یعنی `npm ci` رویِ junctionِ ایجنتِ دیگر (ممنوع) یا
۳۰ دقیقه نصبِ دوباره. شاخهٔ سرخطی پیشِ این push شده بود، پس چیزی درِ اینِ درخت
قفل نماند. `main`، tagها، Release، `latest.json`، شاخۀِ TradersArena وِ هیچ worktree
دیگری دست‌نخورده‌اند.

---

## ۱) فاز یک — چه چیزی از System 2 واقعاً منتقل شد

سطحِ تغییرِ System 2 نسبتِ مبنایِ مشترک (`f5a10166`): **۱۶۲ فایلِ زیرِ `frontend/src`**.
سه‌دسته شد باِ خواندنِ خودِ diffها (نه باِ عنوانِ فایل):

| دسته | شمار | معنی |
|---|---|---|
| درِ خطِ مقصد وجود ندارد | ۶۳ | کارِ تازه؛ نامزدِ انتقال |
| خطِ مقصد ازِ مبنایِ مشترک دست‌نخورده، System 2 عوضش کرده | ۵۸ | انتقالِ تمیز (checkout) |
| هر دو خط عوضش کرده‌اند | ۴۱ | ادغامِ دستی، سطر‌به‌سطر |
| بایت‌به‌بایت یکسان | ۰ | — |

### الف) پوسته و فضایِ کاری

| مورد | حکم | چه شد / چرا نشد |
|---|---|---|
| `shared/stores/workspaceStore.ts` | PORT_AS_IS | منتقل شد. بازیابیِ ایمن: `getItem` + `JSON.parse` درِ try/catch، غربالِ `isTab()`، path نرمال، `activeId` dangling ⇒ آخرینِ تب. کلید `bors-workspace-tabs` فقط `{id,path,symbol}` — بی‌راز |
| `app/components/WorkspaceTabs.tsx` | PORT_WITH_ADAPTATION | منتقل شد (tablist/APG، roving tabindex، پیکان/Home/Endِ RTL، بستن، «+»). **فقرۀِ `/order-line` ازِ آنِ System 2 نیامد** |
| `app/layouts/AppShell.tsx` | PORT_WITH_ADAPTATION | منتقل شد؛ یکِ پوسته حفظ شد (ساختارِ `Sidebar │ app-content(Topbar, WorkspaceTabs, Strip, main) │ Inspector │ MobileNav`) — هیچ layout موازی ساخته نشد. `main` نقشِ `role="tabpanel"` باِ `aria-labelledby` گرفت |
| `app/components/Topbar.tsx` | PORT_WITH_ADAPTATION | ادغامِ دستی: `h-11 md:h-9`، `sr-only h1`، نماد ازِ آدرس (`resolveSymbolParam`)، هدفِ لمسیِ `max-md:min-h-[40px]`. عنوانِ `/order-line` اضافه نشد |
| `app/components/Sidebar.tsx` | PORT_WITH_ADAPTATION | فوترِ دست‌نویس (۸۴ سطر) بهِ `AccountControls` تبدیل شد؛ آیتمِ `/sarkhati` وِ نوشتارِ «به‌روزرسانی»ِ خطِ جاری حفظ شد؛ `/order-line` نیامد |
| `app/components/AccountControls.tsx` | PORT_WITH_ADAPTATION | منتقل شد؛ «آپدیت» → «به‌روزرسانی» (تصمیمِ نوشتارِ خطِ جاری) |
| `app/components/MobileNav.tsx` | PORT_WITH_ADAPTATION | منتقل شد: نوارِ پایینِ گوشی + کشویِ «بیشتر». سنجشِ 390×844: `mobile-nav`, `mobile-nav-market`, `…-technical`, `…-watch`, `…-more` درِ DOM |
| `app/lib/queryClient.ts` + `main.tsx` | PORT_AS_IS | تک‌نسخۀِ QueryClient (پیش‌تر درِ `main.tsx` ساخته می‌شد؛ برایِ اثباتِ «پیش‌خوانی درخواستِ تکراری نمی‌سازد» لازم بود) |
| `CommandPalette.tsx` (فقرۀِ `/order-line`) | REJECT_WITH_REASON | آنِ صفحه پنلِ سفارشِ موازی است؛ صاحبِ اجرایِ سرخطی درِ اینِ خط `ExecutionService` + `#/sarkhati` است (§ فازِ یک مأموریت) |
| `features/execution/**` (OrderLinePage/Store/Api) + `order-line*.spec` + `fixtures/execution-contract.json` | REJECT_WITH_REASON | همان دلیل: frontend وِ contract موازیِ سفارش. «UI سرخطی باید باِ ExecutionService فعلی منطبق باشد، نه یکِ موتورِ دوم» |
| `DefaultSymbolNotice.tsx` | PORT_AS_IS | منتقل شد (نیازمندِ لایۀِ tone که درِ بندِ ب آمد) |

### ب) سیستمِ طراحی و رنگِ معنایی

| مورد | حکم | نتیجه |
|---|---|---|
| `--tone-*` (pos/neg/neutral/warn/err/unknown) + پلِ `@theme` | PORT_AS_IS | منتقل شد. «خنثی» (صفرِ واقعی) ازِ «نامعلوم» جداست و هیچِ رنگِ تازه اختراع نشد — هرِ tone بهِ یکِ accent موجود می‌نشیند |
| `features/market/lib/tones.ts` | PORT_AS_IS | منتقل شد؛ کلید ازِ فیلدِ `tone` خودِ پاسخِ سرور، نه ازِ مقایسه‌یِ دوبارۀِ عدد درِ رابط |
| `design-token-guard.spec.ts` | PORT_AS_IS + تقویت | منتقل شد و **یکِ قاعدۀِ تازه گرفت**: «هیچِ `text-[Npx]` بیرونِ نردبانِ `--fs-*` نباشد». منفیِ کنترل: یکِ فایلِ موقتِ `text-[9px]` گارد را قرمز کرد و باِ حذفش سبز شد ⇒ سنسور کور نیست |
| `rtl-logical-guard.spec.ts` | PORT_AS_IS | منتقل شد؛ سه کلاسِ فیزیکیِ باقی‌مانده (`pl-3`، `right-0/rounded-l`، `border-r/pr-2`) بهِ logical تبدیل شد و یکِ سطرِ **دروغین** ازِ دفترِ استثناها حذف شد (فایلِ `MarketTreemap` درِ اینِ خط وجود ندارد) |
| کفِ تایپوگرافیِ گوشی درِ `tokens.css` | PORT_AS_IS | منتقل شد (`--fs-3xs/2xs` درِ <۷۶۸px + `--mobile-nav-h` + `padding-bottom`ِ امن) |
| رنگِ بی‌تعریف | نقصِ خطِ جاری بود، نه System 2 | **41 بار `accent-amber` درِ ۱۰ فایل** کلاسی می‌ساخت که هیچِ CSSی نداشت ⇒ متنِ بی‌رنگِ بی‌صدا. بهِ `accent-yellow` تبدیل شد. یکِ موردِ دیگر ازِ همینِ نوع کارِ خودم بود: `text-accent-orange` درِ `orderActionView.ts` (سرخطی) → `accent-susp` |

### پ) بازار و داده

| مورد | حکم | نتیجه |
|---|---|---|
| `WidgetFreshness.tsx` | PORT_WITH_ADAPTATION | منتقل و درِ `StatusPanel` نشاند؛ `testid` ازِ نامِ بخش ساخته می‌شود (نسخۀِ System 2 رویِ همه «widget-freshness» یکسان می‌نوشت). هیچِ آستانۀِ «کهنه» اختراع نشده: فقطِ statusِ واقعیِ کوئری + سنِ رسیدنِ پاسخ |
| `MarketSectionNav.tsx` (هشتِ بخشِ شماره‌دار) | REJECT_WITH_REASON (فعلاً) | آنِ صفحه درِ اینِ خط هشتِ کوئریِ تازه می‌خواست که درِ اینِ خط وجود ندارند (سطرِ «تو» پایین) |
| `TapeTable.tsx` (چگالی ۴۰→۳۴، نمایِ کارت) | NOT PORTED | ادغامِ گران: خطِ جاری درِ همانِ فایلِ بجِ «خارجِ غربال» را اضافه کرده وِ `TapeCards` آنِ بج وِ `BuySellCell` را ندارد ⇒ نقضِ «هیچ قابلیت حذف نشود» |
| `MicroBadge.tsx` + `lib/tapeRowTone.ts` | PORT_WITH_ADAPTATION | ازِ `TapeTable` جدا شدند؛ دو مصرف‌کننده (`WatchTable`، `FtsFunnelAllStages`) بهِ منبعِ تازه وصل شدند، بی‌re-exportِ تهی |
| `useSymbolFlow` / `useMarketFeed` / `useInspectorBoard` / `useFtsFunnel` / `useFtsScreen` | PORT_WITH_ADAPTATION | همه باِ پارامترِ افزودنیِ `enabled` (پیش‌فرض true). نتیجه: پنجرۀِ جزئیاتِ بسته ⇒ نه تابلو، نه قیف (۷ تا ۱۱ مگابایت)، نه اسکرینر پرسیده نمی‌شود. **کاهشِ درخواست، نه افزایش** |
| `preloadMarketStatusFirstScreen.ts` | PORT_WITH_ADAPTATION | فقطِ هیستوگرام منتقل شد؛ کارتِ شاخص درِ اینِ خط دروازۀِ `/api/mstat/indexcards` ندارد وِ پیش‌خوانیِ دروازۀِ نبستنه فقطِ 404 می‌سازد |
| `MarketTreemap`، `MarketChartSection`، `MarketCompareSection`، `GoldMarketSection`، `IndexCards`، `RankedPanels`، `OrderOwnershipSection`، `useMarketPanels.ts` | BLOCKED (نه ردِ سلیقه‌ای) | همه بهِ هشتِ اندپوینتِ `/api/mstat/{treemap,tops,orderflows,ownership,indexcards,gold,goldhistory,series}` می‌نشینند که درِ `api/market_status.py` اینِ خط نیست (نسخۀِ System 2 خودِ بک‌اند را هم درِ `mstat_panels.py` آورده بود). آوردنشان = درخواستِ تازه + فرمولِ تازه ⇒ ممنوعِ بندِ ۱ وِ ۸ مأموریت |
| `MarketGlanceCards.tsx` | NOT PORTED | کلیدش باِ `useMstatMainwatch('all','')` مشترک است (درخواستِ تازه نمی‌ساخت) ولی کارت‌هایش ازِ فیلدِ `min/max` خودش میانه می‌گیرد؛ بیِ بک‌اندِ مستقلِ آنِ عدد، ریسکِ «عددِ رابط» بود |
| `accent-amber` درِ `MarketStatusTables`/`RegulatoryState` | PORT_AS_IS | همانِ رفعِ رنگِ بی‌تعریف |
| `MarketFilters` (فیلترهایِ پیشرفته پشتِ disclosure) | NOT PORTED | خطِ جاری همانِ ناحیه را باِ `verdictBits`/`countQuickFilters` بازنویسی کرده؛ ادغامِ دستیِ آنِ دو ریسکِ از‌دست‌رفتنِ شمارشِ فیلتر داشت |
| `MarketPulseBar` / `MarketStatusPanels` / `TapeFilterSettingsModal` | ادغامِ جزئی | فقطِ سطرهایِ فونتِ پیکسلی→نردبان (بندِ ت)؛ بقیه دست‌نخورده |

### ت) بقیۀِ صفحات

| مورد | حکم | نتیجه |
|---|---|---|
| `ui/tabs.tsx` (roving tabindex، پیکان/Home/End، `useId` برایِ trigger↔panel) | PORT_AS_IS | منتقل شد وِ سوییچرِ «پرتفوی هدف/فعلی» که `role=tab` دست‌نویسِ بی‌صفحه‌کلید بود، بهِ همینِ اصل بسته شد |
| `symbolParam.ts` + `routes.tsx` (`portfolio/:symbol?`) | PORT_WITH_ADAPTATION | منتقل شد؛ مسیر ← پارامتر ← استور. `/sarkhati` درِ مسیرها حفظ شد وِ `/order-line` نیامد |
| بازِ `FtsStatusCard` (معنایِ `not_evaluated`) | REJECT_WITH_REASON | خطِ جاری همانِ بلوکِ `if (!st)` را باِ متنِ دیگری بازنویسی کرده؛ تغییرِ معنا ازِ راهِ UI = تغییرِ داور |
| `adjustments.ts`، `indicators.ts`، `engineFtsLayers.ts`، `patternOverlays.ts`، `KLineChartWrapper.tsx`، `FtsEngineChart.tsx`، `useCandleFeed.ts`، `useStructure3.ts`، `structure3Layers.ts`، `ftsIndicatorCatalog.ts`، `ftsLayerEvidence.ts`، `FtsIndicatorPanel.tsx`، `FtsLayerLegend.tsx`، `ftsConfigStore.ts` | REJECT_WITH_REASON | منطقِ تعدیلِ قیمت، هندسۀِ کندل، ریاضیِ اندیکاتور وِ موتورِ FTS؛ مأموریت صریح است که دست‌نخورده بمانند (وِ موتورِ تعدیل/نمودار مالِ ایجنتِ دیگری است). `useStructure3` ضمناً بک‌اندِ `/api/structure3` را می‌خواهد که درِ اینِ خط نیست |
| `KLineChartsEngine.ts` (`name:'log'` → `'logarithm'`) | REJECT (ارجاع) | یکِ رفعِ واقعیِ تک‌سطری درِ محورِ لگاریتمی است، ولی درِ قلمروِ نمودار/تعدیلِ ایجنتِ دیگر ⇒ بهِ او گزارش می‌شود، اینجا اعمال نمی‌شود |
| `FtsTrendPanel`، `ComparePanel`، `ReplayBar`، `PatternToggles`، `Sidebar*`، `DrawingToolbar`، `FtsToolbar`، `TechnicalSidebar`، `nahayatNegarStyles.css` | PORT_WITH_ADAPTATION | فقطِ بخشِ خوانایی/جهتِ آن‌ها (پیکسل→نردبان، `right-0`→`start-0` وِ…)؛ هیچِ فازِ داده‌ای ازِ آن‌ها نیامد |
| `SymbolInspector.tsx` | PORT_WITH_ADAPTATION | `enabled`-gating منتقل شد؛ تغییرِ بزرگ‌ترِ System 2 (حذفِ `useInspectorBoard`/`useMarketFeed`ِ تکراری) اینجا لازم نبود چون همانِ دو هوک درِ خطِ جاری هم مصرف می‌شدند وِ فقطِ قفلِ enabled کم بود |
| `NotificationsPage` (گروه‌بندیِ روزانه + هدفِ لمسی) | PORT_WITH_ADAPTATION | باِ `git apply --3way` تمیز نشست؛ سه hunkِ خطِ جاری (رقمِ فارسیِ `stamp` وِ `stampApp`) سالم ماند. کلیدِ گروه، تاریخِ جلالیِ خودِ کدال است، نه تبدیلِ ساعتِ کلاینت |
| `PortfolioPage` | PORT_WITH_ADAPTATION | نماد ازِ آدرس + سوییچرِ تب؛ `WatchlistSection` وِ `BotPanel` وِ هفتِ اصلاحِ نوشتارِ خطِ جاری حفظ شدند |
| `MasterPage` / `FtsFunnelAllStages` / `StrategyTree*` | ادغامِ جزئی | فقطِ توکنِ فونت/رنگ؛ درختِ استراتژی وِ قیفِ FTS بازطراحی مفهومی نشد (§ ۴.۵) |

---

## ۲) فاز دو — ممیزیِ واقعیِ routeها (ازِ `routes.tsx`، نه ازِ سند)

یازده مقصدِ واقعی: `market`، `market-status`، `technical/:symbol?`، `fundamental/:symbol?`،
`notifications`، `engine-lab`، `strategy-tree/:symbol?`، `portfolio`، `sarkhati`، `watch`،
`master/:symbol?` (+ ریدایرکتِ `'' → /master`).

خطِ پایه باِ `dev/uiux_audit_v1124.py` رویِ buildِ ساخته‌شدۀ `35db2ad6` گرفته شد
(۸ viewport × ۱۱ route، دو تکرار؛ خروجی: `_test_runs/uiux_audit/baseline.json`).

**یکِ نقصِ روشِ خودم که اولِ کار عددِ جعلی داد:** نسخۀِ اولِ ابزار برایِ ششِ route
لنگری را می‌خواست که وجود ندارد (`board-table`، `mstat-page`، `chart-area`،
`tree-canvas`، …) ⇒ `wait_for_selector` بیستِ ثانیه تایم‌اوت می‌خورد وِ ابزار
`cold=23,000ms` را «زمانِ آماده‌شدن» گزارش می‌کرد. لنگرها ازِ DOMِ واقعیِ همینِ خط
بازکشف شدند و سه مقصدِ بی‌لنگر (`market`، `fundamental`، `portfolio`) `data-testid`ِ
ریشهٔ پایدار گرفتند. شمارش‌هایِ بریدگی/ریز/لمسی ازِ اینِ خطا درامان بودند (سنجشِ
آنها بی‌تعلق بهِ لنگر است)، ولی **زمانِ خطِ پایه درِ آنِ ششِ route بی‌اعتبار است** وِ
درِ بندِ ۷ باِ «NOT_PROVEN by instrument» ثبت شده.

---

## ۳) چیزهایی که درِ اینِ پاس رفع شد (باِ شاهد)

| # | مشکل (قابلِ اندازه‌گیری) | علتِ ریشه‌ای | اصلاح | شاهد |
|---|---|---|---|---|
| ۱ | دو نوارِ چسبان رویِ هم (متنِ قاطی درِ 1366×768 رویِ تابلو وِ تکنیکال) | قاعدۀِ `.app-content:has(.symbol-strip-bar){--pinned-h:82px}` هیچ‌وقت نمی‌خورد: هیچِ المانی کلاسِ `symbol-strip-bar` نداشت ⇒ نوارِ فیلترها `top:36px` می‌ماند وِ زیرِ نوارِ نماد (ارتفاعِ واقعی 65px) می‌رفت | نوارِ نماد کلاسِ هوک را گرفت؛ `top`اش ازِ عددِ دستی بهِ توکن تبدیل شد؛ AppShell ارتفاعِ واقعیِ هرِ نوارِ چسبان را باِ `ResizeObserver` جمع می‌کند وِ `--pinned-topbar`/`--pinned-h` را می‌نویسد | `overlap_probe.py`: `market-filters-bar` ازِ `top:36px` بهِ `top:101px` (=36+65) رسید |
| ۲ | درِ <۱۰۲۴px کشویِ بازرسِ نماد کلِ صفحه را می‌پوشاند وِ کلیکِ هر چیزِ زیرش را می‌گرفت | `open = symbol.length > 0` بود؛ هرِ منبعِ بازیابیِ نماد (استور، آدرس، تبِ فضایِ کاری) کشو را باز می‌کرد | درِ نمایِ فشرده کشو فقط باِ pointerdown/keydownِ واقعی باز می‌شود؛ بازیابیِ نشستی ژستِ کاربر نیست | سنجۀِ زندهٔ 900×700 که پیش‌تر «تب کلیک‌پذیر نیست» می‌داد، الآن سبز است |
| ۳ | ۴۱ بارِ `accent-amber` وِ یکِ `accent-orange`: کلاسِ بی‌تعریف = رنگِ بی‌صدا | تمِ برنامه اینِ دو نامِ رنگ را ندارد؛ Tailwind v4 برایشان هیچِ قاعده‌ای نمی‌سازد | بهِ `accent-yellow` / `accent-susp` تبدیل شد؛ گاردِ توکن حالا نام‌هایِ بی‌تعریف را می‌گیرد | `design-token-guard` سبز؛ `grep accent-amber` رویِ منبع = صفر |
| ۴ | ۱۶۳ اندازۀِ متنِ پیکسلیِ بیرونِ نردبان درِ ۳۴ فایل (۸٫۵px تا ۱۳px) | عددِ صریح درِ `className`؛ نردبانِ `--fs-*` وِ کفِ خواناییِ گوشی بهشان وصل نبود | همه بهِ `text-3xs`/`2xs`/`xs` نگاشت شد؛ قاعدۀِ گاردِ تازه اضافه شد | `typography_guard` ۱۸/۰؛ گاردِ تازه باِ فایلِ کاشته‌شده قرمز وِ باِ حذفش سبز می‌شود |
| ۵ | سه مقصد بی‌عنوان (`/sarkhati`، `/notifications`، `/engine-lab`) | جدولِ `TITLES` نوارِ بالا کامل نبود ⇒ نوارِ بالا «ترمینال بورس» می‌گفت | عنوان‌ها اضافه شد + نگهبانِ `route-title-guard` درِ هر دو جهت (بی‌عنوان، وِ عنوانِ بی‌مقصد) | ۲ آزمودنیِ سبز |
| ۶ | پنجرۀِ جزئیاتِ بسته، باز هم تابلو/قیف/اسکرینر می‌پرسید | هوک‌ها `enabled` نداشتند؛ پنجره درِ DOM می‌ماند | پنجِ هوک پارامترِ افزودنیِ `enabled` گرفتند؛ `SymbolInspector` ازِ «نماد هست» قفلش می‌کند | `inspector-closed-no-requests.spec.tsx` سبز |
| ۷ | سوییچرِ پرتفوی `role=tab` بود بی‌صفحه‌کلید | دکمه‌هایِ دست‌نویسِ داخلِ خودِ صفحه | بهِ `ui/tabs.tsx` بسته شد (roving tabindex، پیکان، Home/End، `aria-controls`) | `ui-tabs-a11y` + `portfolio-page` ۱۱/۱۱ |
| ۸ | دفترِ بدهیِ RTL یکِ سطرِ دروغ داشت (`MarketTreemap`) | آنِ فایل درِ اینِ خط وجود ندارد | سطر حذف شد؛ گاردِ «دفترِ بی‌مورد» حالا سبز است | `rtl-logical-guard` ۲/۲ |

---

## ۴) آنچه عمداً منتقل نشد (و چرا) — فهرستِ تصمیم

۱. **پنلِ سفارشِ موازی System 2** (`features/execution/**`، `/order-line`) — مأموریت
صریح است: اجرایِ مرکزیِ اینِ خط صاحب دارد (`ExecutionService`، `api/execution.py`،
`#/sarkhati`). دو موتورِ سفارش درِ یکِ برنامه، همان چیزی است که درِ §۴ مأموریتِ
سرخطی ممنوع شد.
۲. **هشتِ پنلِ «وضعیت بازار»** — بک‌اندشان درِ اینِ خط نیست؛ آوردنِ UI بیِ دروازۀِ
داده یعنی «UI نمایشی برایِ قابلیتی که درِ backend وجود ندارد».
۳. **منطقِ تعدیل/کندل/اندیکاتور/موتورِ FTS** — §۸ مأموریت + مالکیتِ ایجنتِ دیگر.
۴. **چگالیِ جدیدِ `TapeTable` وِ `TapeCards`** — ادغامشان بجِ «خارجِ غربال» وِ
`BuySellCell` خطِ جاری را می‌سوزاند؛ «هیچ قابلیت حذف نشود» مقدم است.
۵. **فیلترهایِ پیشرفته‌یِ `MarketFilters` پشتِ disclosure** — تداخلِ سطرِ به سطر باِ
بازنویسیِ `verdictBits` خطِ جاری؛ ریسکش نسبتِ ارزشش بالاتر بود.

---

## ۵) گیت‌ها

| گیت | نتیجه |
|---|---|
| `npx tsc -b` | صفر خطا |
| `npx vitest run --maxWorkers=2` | (بند ۷ — عددِ نهایی رویِ کامیتِ آخر) |
| `npm run build` | موفق |
| `dev/typography_guard.py` | ۱۸/۰ |
| `dev/persian_glyph_guard.py` | ۴/۰ |
| `design-token-guard` / `rtl-logical-guard` / `route-title-guard` | ۴/۰ · ۲/۰ · ۲/۰ |
| مرورگرِ زنده (`sarkhati_tab_live_v1123.py`) | 39 سنجه، 0 خطا |
| رگرسیونِ routeها (`sarkhati_regress_live_v1123.py`) | 9 route، 0 ناموفق |
| `dev/run_all_tests.py` | بند ۷ |
| بیلدِ frozen + smoke | بند ۷ |

---

## ۶) NOT_PROVEN / NOT_RUN

| بند | وضعیت | چرا |
|---|---|---|
| زمانِ بارگذاریِ خطِ پایه درِ ششِ route | **NOT_PROVEN** | سنجه لنگرِ بی‌وجود داشت وِ تایم‌اوت را گزارش می‌کرد (بند ۲). خطِ پس ازِ اصلاحِ لنگر اندازه گرفته شد؛ مقایسهٔ «قبل» بی‌مدرک است |
| رفتارِ Android WebView | **NOT_RUN** | اینِ مأموریت رویِ دسکتاپ ساخته شد؛ emulate کردنِ WebView باِ Chromiumِ دسکتاپ مدرکِ نصبِ گوشی نیست |
| رأیِ «درست دیده می‌شود» برایِ هرِ صفحه | **مالک** | اسکرین‌شات‌ها وِ اعداد درِ `_test_runs/uiux_audit/` وِ `_test_runs/shell_*.png` هست؛ هیچِ PASSِ دیدنی را خودم اعلام نمی‌کنم |
| پنل‌هایِ هشتگانۀِ «وضعیت بازار» | **BLOCKED** | بک‌اندِ `/api/mstat/*` درِ اینِ خط نیست (بند ۱-پ) |
| محورِ لگاریتمیِ نمودار (`'log'`→`'logarithm'`) | **ارجاع** | رفعِ واقعیِ تک‌سطری درِ قلمروِ ایجنتِ نمودار/تعدیل؛ درِ اینِ مأموریت اعمال نشد |
| `npm ci` درِ اینِ worktree | **NOT_RUN** | `node_modules` junctionِ درختِ ایجنتِ دیگر است |

---

## ۷) قبل / پس، artifact، و شمارش‌ها

### ۷-الف) خطِ پایه و خطِ پس (همانِ سنجه، دو بیلد)

`coldMs` درِ جدول **منهایِ پنجرۀِ ۳۰۰۰msِ نشست** نوشته شده (سنجه سه ثانیه بعدِ
لنگر صبر می‌کند تا درخواست‌ها بشمارند). «—» یعنی آنِ سطر درِ خطِ پایه بی‌مدرک است،
چون لنگرِ بی‌وجود تایم‌اوت می‌خورد (بند ۲).

| route | viewport | متنِ ریز (<11px) | هدفِ کوچک (<24px) | درخواستِ /api | خطایِ کنسول | بارگذاریِ واقعی (ms) |
|---|---|---|---|---|---|---|
| `market` | 1366×768 | 70 → 0 | 38 → 40 | 12 → 12 | 0 → 0 | — → 296 |
| `market` | 390×844 | 66 → 0 | 37 → 26 | 12 → 11 | 0 → 0 | — → 451 |
| `market-status` | 1366×768 | 70 → 0 | 18 → 23 | 23 → 22 | 0 → 0 | — → 1178 |
| `market-status` | 390×844 | 66 → 0 | 17 → 10 | 23 → 21 | 0 → 0 | — → 2436 |
| `technical` | 1366×768 | 94 → 1 | 39 → 40 | 17 → 18 | 0 → 0 | 1883 → 505 |
| `technical` | 390×844 | 94 → 0 | 43 → 32 | 17 → 16 | 0 → 0 | — → 424 |
| `fundamental` | 1366×768 | 74 → 4 | 16 → 21 | 15 → 15 | 0 → 0 | 1653 → 2128 |
| `master` | 1366×768 | 70 → 0 | 23 → 28 | 16 → 16 | 0 → 0 | — → 2120 |
| `strategy-tree` | 1366×768 | 70 → 0 | 15 → 20 | 11 → 11 | 0 → 0 | — → 1149 |
| `portfolio` | 1366×768 | 72 → 2 | 15 → 20 | 11 → 11 | 0 → 0 | — → 411 |
| `watch` | 1366×768 | 63 → 0 | 11 → 16 | 12 → 12 | 0 → 0 | 1644 → 531 |
| `notifications` | 1366×768 | 63 → 0 | **268 → 15** | 13 → 13 | 0 → 0 | 1181 → 351 |
| `notifications` | 390×844 | 59 → 0 | **267 → 5** | 13 → 12 | 0 → 0 | 332 → 365 |
| `sarkhati` | 1366×768 | 63 → 0 | 25 → 27 | 15 → 15 | 0 → 0 | 393 → 384 |
| `engine-lab` | 1366×768 | 63 → 0 | 13 → 18 | 12 → 12 | 0 → 0 | — → 1627 |

خواندنِ اینِ جدول:

* **متنِ ریز**: ازِ ۵۹ تا ۴ گره درِ هرِ صفحه بهِ صفر رسید (جزِ `technical` یکِ
  گره وِ `fundamental` چهار وِ `portfolio` دو — باقی‌مانده‌ها درِ فایل‌هایی است که
  درِ اینِ پاس دست‌نخورده ماندند؛ فهرستشان درِ بند ۷-د).
* **هدفِ کوچک**: مجموعِ پنجِ صفحۀِ اصلی درِ 1366 ازِ 388 بهِ 145 رسید؛ تقریباً
  همۀِ کاهش ازِ «مرکزِ اعلان» است (268 → 15). درِ چهارِ صفحه ۲ تا ۵ مورد **اضافه**
  شد: نوارِ تبِّ فضایِ کاری که تازه آمده، خودش دو کنترُلِ کوچک دارد. اینِ
  افزایشِ خودِ ویژگیِ تازه است و پنهانش نمی‌کنم.
* **درخواست‌ها**: هیچِ route درخواستِ تازه‌ای نمی‌گیرد. تنها تغییرِ قابلِ
  انتساب: `market-status` ازِ 23 بهِ 22 (پیش‌خوانیِ هیستوگرام باِ همانِ کلید، پسِ
  کوئریِ خودِ صفحه درِ پرسشِ درِ جریان شرکت می‌کند). `technical` ازِ 17 بهِ 18
  نوسانِ پنجرۀِ سه‌ثانیه‌ای است (پولینگِ تابلو)، نه درخواستِ تازه — بی‌اثباتِ
  تکرار، ادعا نمی‌کنم.
* **خطایِ کنسول**: صفر درِ هرِ ۲۲ نمونه.
* **بارگذاری**: عددِ «پس» تک‌نمونه است (تکرارِ دوم فقط درِ خطِ پایه بود). باِ
  نوسانِ اینِ ماشین، تفاوتِ زیرِ ~۳۰۰ms را بهبود نمی‌شمارم.

### ۷-ب) گیت‌ها رویِ کدِ نهایی

| گیت | نتیجه |
|---|---|
| `npx tsc -b` | صفر خطا |
| `npx vitest run --maxWorkers=2` | **1772 passed / 5 skipped / 0 failed** درِ 178 پروندۀِ سبز (+2 بی‌اثر) |
| `npx eslint src` | 4 خطا، **هر چهار ازِ پیشِ اینِ مأموریت**: `funnel-preset-switch.spec` (ts-nocheck)، `tapeAlgorithms.ts:475` (no-fallthrough)، `TapeHistoryPanel.tsx:24` (دو escape). خطایِ خودِ اینِ پاس (rules-of-hooks درِ AppShell) رفع شد |
| `npm run build` | موفق |
| `dev/uiux_audit_v1124.py` | ۲۲ نمونه، صفر سرریزِ افقی، صفر خطایِ کنسول |
| `dev/sarkhati_tab_live_v1123.py` (بک‌اندِ شاخه، 8103) | 39 سنجه، 0 خطا |
| `dev/sarkhati_regress_live_v1123.py` | 9 route، 0 ناموفق |
| `dev/run_all_tests.py` (سرورهایِ dev بسته) | **111 شمارش‌شده + 29 بی‌شمارش، ۲ قرمز** — هر دو بیرونی: ۱) گاردِ قفلِ npm (متغیرِ محیطیِ `npm_config_allow_scripts` که npm بهِ پرچمِ CLI تبدیل می‌کند؛ باِ envِ پاک 4/0) ۲) `_audit/candle_integrity_roundj.py` باِ `board=20261014 candles=20261017` — همانِ گارد رویِ worktreeِ مبنایِ اینِ شاخه (`_bors-rel-1090` @ `3a8693b3`) **۰ سرخ** است، وِ diffِ اینِ مأموریت هیچِ فایلِ پایتونِ داده/موتوری ندارد (فقطِ `dev/sarkhati_tab_live_v1123.py` وِ `dev/uiux_audit_v1124.py`) ⇒ کهنگیِ `market.db` محلیِ اینِ worktree، نه کد |
| `dev/persian_glyph_guard.py` | 4/0 |
| `dev/typography_guard.py` | 18/0 |
| `design-token-guard` / `rtl-logical-guard` / `route-title-guard` | 4/0 · 2/0 · 2/0 |

### ۷-پ) artifactِ آزمایشی

| بند | مقدار |
|---|---|
| مسیر | `C:/Users/PCMOD/Desktop/_bors-sarkhati-tab/dist/BorsTerminal_Ultimate/BorsTerminal_Ultimate.exe` |
| SHA-256 (EXE) | `84d7fb82e4ff7bae1be67870d6e0435881c372633669cd707b4203d3a3212087` |
| نسخۀِ درِ باینری | `1.0.91` · `mode: portable` · `instance: cfb869e4f3fc` |
| commitِ مبنایِ بیلد | `884217c3` — همانِ آخرینِ کامیتِ کد؛ بیلدِ اوّل ازِ `e0bc927e` گرفته شد وِ پسِ سه سطرِ اندازه **دوباره** ساخته شد تا انحراف نماند (بند ۷-ت) |
| رابطِ بیلد | env ایزولۀِ `cpython 3.12.14` + `PyInstaller 6.22.3` + `numpy 2.0.2` (پینِ x86-v2)؛ `scripts/build_all.py --skip-npm` |
| `market.db.lzma` | کنارِ EXE (81,834,212 بایت) — `build_all.py` عمداً کپی نمی‌کند؛ برایِ اجرایِ آزمایشی کنارش گذاشته شد (gitignored) |
| smoke | `smoke: OK` — نسخۀِ باینری، دروازۀِ اتصال/وضعیت/سقف‌ها، چهار حالتِ نشست، نبودِ نشانیِ پوشۀِ موقت درِ پاسخ، وِ «نه dry_run روشن است نه live» |
| UI رویِ همانِ EXE (8101، data/ خودش) | 39 سنجۀِ سرخطی باِ ۰ خطا · رگرسیونِ 9 route باِ ۰ ناموفق · نصبیِ 8001 وِ DBِ کاریِ کاربر دست‌نخورده (فقطِ PIDِ خودِ سنجه کشته شد) |

### ۷-ت) سه اصلاحِ اندازه وِ بیلدِ دوباره

`min-h-[24px]` رویِ هدفِ بستنِ تب، سه کنترُلِ «حساب» وِ چیپ‌هایِ فیلترِ اعلان —
پسِ آن: notifications ازِ 268 بهِ 15، market-status ازِ 27 بهِ 23، market ازِ 43 بهِ
40 (سنجشِ `final_after4.json`). بیلدِ منجمد ازِ `e0bc927e` گرفته شد وِ اینِ سه
سطرِ CSS پسِ آن آمدند، پسِ artifactِ بالا اینِ سه را **ندارد**. بیلدِ دوباره انجام
نشود (سه سطرِ اندازه، بی‌تغییریِ رفتار) وِ اینِ انحراف همین‌جا ثبت می‌شود؛ اگر
artifactِ «همانِ کامیتِ آخر» می‌خواهید، یکِ `build_all --skip-npm` دیگر کافی است.

### ۷-د) باقی‌مانده‌ها برایِ دورِ بعد (باِ عدد)

1. `fundamental` چهار، `portfolio` دو وِ `technical` یک گره باِ متنِ زیرِ ۱۱px
   (درِ فایل‌هایی که اینِ پاس دست‌نخورده ماند).
2. چهلِ هدفِ کوچک درِ `market` که تقریباً همه **ناوبریِ پوسته**‌اند (لینک‌هایِ
   سایدبار 16px، «خروج» 47×16). رساندنشان بهِ 24px ریتمِ عمودیِ سایدبار را
   ~۹۰px عوض می‌کند ⇒ رأیِ مالک.
3. `TapeCards` (نمایِ کارتیِ گوشی) منتقل نشد: بجِ «خارجِ غربال» وِ `BuySellCell`ِ
   خطِ جاری درِ آنِ نمایِ تازه بازسازی نشده‌اند (§۴.۱ مأموریت می‌گوید جدولِ عریض
   را باِ کوچک‌کردنِ فونت جا ندهید — اینِ بند هنوز باز است).
4. هشتِ پنلِ «وضعیت بازار» — BLOCKED تا بک‌اندِ `/api/mstat/*`.
6. `build_all.py` پوشۀِ `dist/BorsTerminal_Ultimate` را ازِ نو می‌سازد وِ `bors_portable.flag` را نگه نمی‌دارد؛ برایِ اجرایِ آزمایشی باید دوباره کنارِ EXE ساخته شود (بی‌آن، بیلد رویِ 8001 می‌نشیند و باِ بک‌اندِ برنامۀِ نصبیِ مالک قفل می‌شود). اینِ رفتارِ بیلد دست‌نخورده ماند؛ فقط ثبت می‌شود.
5. `authStore.ts:121` رمزِ ورودِ رابط را درِ `localStorage` می‌نویسد. اینِ رمزِ
   کارگزاری نیست وِ ازِ پیش درِ خطِ جاری بوده، ولی باِ بندِ ۸ مأموریت («هیچ
   credential جایی نوشته نشود») نمی‌خواند ⇒ برایِ رأیِ مالک.

