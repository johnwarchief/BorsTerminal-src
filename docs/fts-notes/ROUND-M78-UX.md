# Round M/۷۸ — باقی‌ماندۀ UX جهانی (بدونِ حذفِ هیچ capability)

این دور فقط بستنِ ده موردِ باقی‌ماندۀ Task #78 است: دیالوگ‌ها، کیبورد، تلاشِ
دوباره، وضعیتِ اتصال، درخت استراتژی، بازگشتِ قیف و واژگان. گیتِ هفتگی
(REJECT برای نزولی/خنثی)، ساعتِ شنی (MA52/RSI5 هفتگی) و adjustment
دست‌نخورده‌اند — پینِ انجماد `dev/test_roundm_freeze.py` بعد از این دور همان
اعدادِ دورِ قبل را می‌دهد: ۶ سبز / ۰ قرمز / ۱ skip، seen up=35 range=5،
decisions PERMITTED=35 REJECT=5.

## ۱) هوکِ مشترکِ دیالوگ — `shared/lib/useDialogA11y.ts`

Escape (capture روی window، چون رویداد می‌تواند بیرونِ پنل هدف بگیرد)، تلهٔ Tab
با چرخشِ دورِ پنل، focusِ اولیه، بازگردانی focus به تریگر، قفلِ شمارنده‌دارِ
scroll بدنه. پنل‌ها `overscroll-contain` می‌گیرند تا زنجیرۀ اسکرول به پشتِ
دیالوگ راه نیابد. وصل‌شده به: `Modal` مشترک، `FtsAnalystModal`،
`UserSettingsModal`، `UpdateManagerModal`، `ChartSettingsDialog`،
`TapeFilterSettingsModal`، `FtsSettingsDrawer`، `StrategyTreeDrawer`،
`CommandPalette`، `SymbolSearchModal`. `FilterConfigPopover` (پاپ‌اورِ
زیرِچیپ، با بستنِ خودکار روی اسکرول) فقط Escape گرفت — تلهٔ فوکوس برای popover
 قراردادِ خودش را می‌طلبد و عمداً اضافه نشد. `SymbolInspector` aside مقیم است،
نه dialog؛ `inert` موجودش حفظ شد.

نکتۀ زنده که با تستِ jsdom گرفته نمی‌شد: دراورِ بنیادی `transition-all` داشت و
Chromium مقدارِ گسستۀ `visibility` را تا میانهٔ ۲۰۰ms قدیمی نگه می‌دارد —
focusِ هم‌زمان با باز شدن بی‌صدا رد می‌شد. transition به
`transform/opacity` محدود شد + تلاشِ دوم در قابِ بعد درِ خودِ هوک
(`_audit/round78_live.json`، سنجشِ ۷).

## ۲) ردیف‌های کیبوردپذیر

`FtsScreenTable` (سطرِ نماد) و `PortfolioPage` (سطرِ holdings): `tabIndex=0` +
Enter/Space با `preventScroll`/`preventDefault` روی Space + `aria-label`. حلقۀ
focus از قاعدۀ سراسری `index.css:99` (`[tabindex]:focus-visible`) می‌آید.
سطرِ excluded درِ غربالگری اصلاً رندر نمی‌شود پس کیبورد هم نمی‌گیرد (تست ۲).

## ۳) تلاشِ دوباره — `shared/components/RetryAction.tsx`

الگوی TapeTable به پنج حالتِ بی‌دکمه رسید: غربالگری و کارتِ بنیادی
(`fund-screen-retry`, `fund-card-retry`؛ ۴۰۴ عمدتاً بی‌دکمه می‌ماند چون
«صورتِ مالی ندارد» با تلاشِ دوباره حل نمی‌شود)، سبدِ پرتفوی، صنایعِ سایدبار
(خطا از «بدون داده» جدا شد)، نشانِ تحلیل درِ تکنیکال (`fts-strip-retry`)، و
نتیجۀ FTS درِ Master. همه همان `refetch()` واقعیِ کوئری را صدا می‌زنند.

## ۴) وضعیتِ اتصال درِ Topbar

نقطۀ سبزِ hardcoded جایش را به خواندنِ `status/dataUpdatedAt`ِ کوئریِ
`MARKET_FEED_KEY` از کشِ TanStack داد (مشترکِ subscriber، بی‌observer و بی‌polling
تازه): خطا ⇒ قرمز «دادهٔ تابلو نمی‌رسد»، موفق ⇒ سبز «سیستم آنلاین و متصل»،
بی‌کوئری ⇒ خاکستری «در انتظار». ادعای آنلاین بی‌سیگنال ممکن نیست.

## ۵) درخت استراتژی

- **pan clamp**: کریدور با origin مرکزی — `W/2 ± (W/2)·z + pan` باید حداقل
  ۱۲۰px از نقشه در دید نگه دارد؛ هم روی drag و هم پسِ هر زوم (effect).
- **برچسبِ فارسی**: اندازه‌گیری با canvas (fallback تخمینی بی‌canvas) و شکستن
  تا سه خط؛ قدِ سطرِ تک‌خطی دقیقاً همان ۳۳/۱۹ همیشگی است، سطرِ چندخطی
  ۱۴/۱۲px اضافه می‌گیرد. `LEAF_W/HEAD_W/ZONE_W` و ریل‌ها دست‌نخورده.
- **RTL**: هندسۀ راست‌به‌چپِ موجود (بدونِ `scaleX(-1)`) حفظ شد؛
  `map_geometry_probe` پنج سنجشِ سبز می‌دهد (برچسب از کارت بیرون نمی‌زند،
  slotها ۰..۳ راست‌به‌چپ).

## ۶) بازگشتِ قیف

پیشِ رفتن از سطر به Master، `{stage, scroll}` درِ `sessionStorage` ثبت می‌شود؛
پس از بازگشت مرحلۀ فعال برمی‌گردد و اسکرول وقتی محتوا قدِ لازم را یافت (چند
رندرِ پولینگ) یک‌بار اعمال و snapshot پاک می‌شود. بی‌store سراسری؛ چیپ‌ها و
کف‌ها همان جایِ قبلی‌شان (`funnelPrefsStore`) ماندند. دو نقصِ زنده که همین
سنجش بیرون کشید: (الف) اسکرول‌کنندهٔ واقعی گاهی خودِ سند است نه `.app-content`
— هر دو نامزد می‌شوند؛ (ب) دکمۀ عقبِ مرورگر به‌خاطر `params.symbol ?? stored`
قیف را نمی‌نشاند — MasterPage با نشانهٔ `popstate` + snapshot دست‌نخورده،
نمادِ استور را رها می‌کند تا قیف رسم شود.

## ۷) «ذخیره و اعمال بر الگوریتم»

grep کامل (فرانت + `api/*.py` + موتورها): هیچ consumer برای
`fts.strategy.tree.config.v1` نبود و `MasterPage` هم `onApplyTree` نمی‌داد.
دکمه به «ذخیرهٔ برنامۀ شخصی» و زیرعنوان به «حکمِ موتور را تغییر نمی‌دهد»
تغییر کرد؛ prop مرده حذف شد. موتور و وتوی هفتگی عمداً بی‌تغییر ماندند —
«وصل‌کردنِ» این پنل به موتور یعنی ساختنِ آستانهٔ کاربر-ساخته، که خارج از
قیدهای این دور است.

## ۸) واژگان

REJECT درِ خلاصه ⇒ «رد»؛ سطرهای WEEKLY/DAILY/SETUP ⇒ «روند هفتگی/روند
روزانه/ستاپ»؛ STAGE_LABEL و بخش‌های S/T/F ⇒ فارسی؛ «پشتیبان»⇒«حمایت»؛
«بی‌اعتباری»⇒«شرط ابطال»؛ STATUS_LABEL ⇒ «تأیید/رد/در انتظار/داده در دسترس
نیست»؛ pending پرتفوی ⇒ «در انتظار»؛ tooltipهای انگلیسیِ GatePipeline ⇒
فارسی؛ کدهای `exit_engine.verdict`/`stop_basis`/`trend.matrix.setup` با
dictionary درِ همان کارگزارِ ترجمه (متن‌هایِ prose خودِ موتور —
`status.text`/`matrix.desc` — هنوز عیناً نشان داده می‌شوند، قراردادِ Round L)؛
«ریجکت»⇒«رد»، «پرست»⇒«پیش‌تنظیم»؛ ⇒/➔ درِ چند جمله به «؛ پس» تبدیل شد.

## آنچه زنده اثبات **نشد**

- سطرِ چندخطیِ برچسب درِ حالتِ واقعی (همۀ برچسب‌های موجود تک‌خطی‌اند؛
  geometry probe بی‌برچسبِ بلند سبز بود — مسیرِ wrap فقط با کد و تستِ واحد دیدۀ
  شد، نه درِ نقشۀ زنده).
- نیمۀ داوریِ دوجانبه: `tools/pilot_ctl.py` درِ این نشست سه بار با
  `read operation timed out` از سرویسِ TypeSafe Jev رد شد — قضاوتِ pilot برای
  این دور **راستی‌آزمایی نشده** است.
- ردیف‌های grid درِ `StrategyTreePage` (دها `div onClick`) کیبورد نگرفتند —
  خارج از دو موردِ اعلام‌شدۀ Task #78؛ برایِ دورِ بعد یادداشت شد.

## فرمان‌ها

`npx tsc -b` صفر · `npx eslint .` صفر · `vitest run` ۱۴۱۴ سبز/۱ skip ·
`npm run build` سبز · `python _audit/cjk_scan.py` → ۰ ·
`python dev/run_all_tests.py` → ALL SUITES PASSED ·
`python dev/test_roundm_freeze.py` → 6/0/1 با همان شمارشِ دورِ قبل ·
`node tools/round78_live_probe.mts --url http://127.0.0.1:8002/` → ۸/۰
(بیلدِ سورس روی ۸۰۰۲؛ href/bodyText قبل از نتیجه خوانده شد).
