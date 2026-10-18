# ممیزیِ قابلیت‌ها و برنامۀ بازطراحی «تابلوخوانی» — ۲۰۲۶-۱۰-۱۸

> این سند **فقط ممیزی و برنامه‌ریزی** است. هیچ کدی تغییر نکرده، هیچ کامیتی زده نشده،
> هیچ شاخه‌ای merge یا rebase نشده و هیچ ماکیاپی تولید نشده. همه‌چیز ازِ سورسِ
> واقعیِ همان ref خوانده شده و هر ادعا `path:line` یا `sha` دارد. هرچه دیده نشد
> صریحاً `NOT FOUND` یا `NOT_OBSERVED` علامت خورده است.

## ۰) خلاصۀ مدیریتی

1. صفحه‌ای که مالک «تابلوخوانی» می‌خواند `frontend/src/features/market/routes/MarketPage.tsx`
   است (route `market` درِ `frontend/src/routes.tsx:13`، برچسبِ سایدبار
   `frontend/src/app/components/Sidebar.tsx:44`). سه بلوکِ «وضعیت بازار»، «نبض» و
   «نمودارِ درونروز» **پیش‌تر** ازِ این صفحه بیرون رفته و تبِّ مستقلِ خودش را دارد
   (`MarketPage.tsx:235-237` باِ رأیِ صریحِ مالکِ ۱۴۰۵-۰۷-۲۲) — این مرز درِ بازطراحی
   باید حفظ شود.
2. جدولِ تابلو **از قبل مجازی‌سازی‌شده** است (`useVirtualizer`، ارتفاعِ ردیفِ ۴۰،
   `overscan: 12` — `TapeTable.tsx:344-349`) و دوازده ستونِ ثابت باِ `ROW_GRID`
   (`TapeTable.tsx:48-49`) و کفِ عرضِ `min-w-[1100px]` (:47).
3. فیلترها: هفت چیپِ تابلویی (`tapeStore.ts:15`) + منطق اشتراک/اجتماع
   (`screenFilterStore.ts:14`، کلیدِ `bors.screen.logic.v1`) + آستانۀِ تنظیم‌شدنیِ
   هر فیلتر (`TapeFilterSettingsModal.tsx`، `FilterConfigPopover.tsx`،
   `bors_tape_filter_config_v2`) + شمارشِ وابسته‌به‌نامزد (`MarketFilters.tsx:305-331`).
4. **مدیریت ستون (نمایش/پنهان/ترتیب/بازگردانی) درِ هیچ شاخه‌ای وجود ندارد**
   (`NOT FOUND`)؛ ولی *نیمۀِ زیرساختش* ساخته شده: `MicroBadge.tsx` و
   `tapeRowTone.ts` ازِ `TapeTable` جدا شده‌اند تا دو نما یکِ منبع داشته باشند.
5. **نمایِ کارتیِ گوشی + `tapeColumns.ts` درِ شاخۀ
   `integration/uiux-2-0-review-2026-10-16` وجود دارد و هیچ‌جا منتشر نشده** — سه
   کامیتِ مستقل (`a7ea0458`، `ba3d5f55`، `65080701`) باِ ۹ رفتارِ قفل‌شده درِ
   `market-mobile-view.spec.tsx`. پس «نمایِ دوم» از صفر ساختنی نیست، **پورتِ** کردنی است.
6. **نماهایِ ذخیره‌شدنی (saved views) وجود ندارد**؛ نزدیک‌ترین چیز `TAPE_PRESETS`
   (چهار پیش‌تنظیمِ آستانه: `scalp|jet_trend|sniper|smart_money`،
   `tapeAlgorithms.ts:143-160`) است که فقط آستانه‌ها را عوض می‌کند — نه ستون،
   نه ترتیب، نه مجموعه‌چیپ‌ها.
7. **تغییرِ اندازهٔ پنل/چیدمانِ آزاد درِ کلِ فرانت وجود ندارد** (`splitter`,
   `react-resizable`, `ResizablePanel` → صفر نتیجه درِ سه شاخه). تنها اهرمِ موجود
   عرضِ ثابتِ پنلِ جزئیات است: توکنِ `--inspector-w: 15rem`
   (`frontend/src/shared/styles/tokens.css:46`) باِ `padding-left`ِ همان مقدار
   (`frontend/src/index.css:512`).
8. **System 2 هیچ ربطی به تابلوخوانی ندارد**: کامیت‌هایش `market-status`،
   `mstat_panels.py`، `StatusShell/Treemap/GlanceCards` و کارِ موتورِ تعدیل/چارت
   است. ۶۰ ازِ ۶۱ کامیتش باِ `git cherry` درِ خطِ انتشار **نیست**. سه فایلِ مشترک
   دارد که باید باِ چشمِ باز تصمیم گرفته شود (§۳).
9. محدودیتِ عملکردی که هر بازطراحی باید رعایت کند درِ کد ثبت شده: بدنهٔ
   `/api/market` ~۴٫۲ مگابایت (gzip ~۵۶۵KB) درِ هر ~۵ ثانیه، و deltaِ ۱۵۸ بایتی
   وقتی چیزی عوض نشده (`shared/api/marketFeed.ts:13-14`، `shared/api/http.ts:48`).
10. پیشنهادِ شاخۀ هدف: **`release/1.0.91-strategy-fts` (0dc5d0be)** — تنها شاخه‌ای
    که هم *فرزندِ مستقیمِ* `github/main` است (۰ عقب، ۷۳ جلو) و هم نیمۀِ استخراج‌شدهٔ
    تابلو + تب‌هایِ فضای کاری را دارد (§۱).

---

## ۱) وضعیت Git و پیشنهادِ شاخۀ هدف

### الف) آنچه همین حالا اندازه گرفته شد

| ref | tip | نسبت باِ `github/main` | فایل درِ `features/market` | نمایِ کارتی؟ | `tapeColumns`؟ | `MicroBadge`/`tapeRowTone`؟ | تبِ فضای کاری؟ |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `github/main` | `f9cea521` | مرجع | ۴۱ | نه | نه | نه | نه |
| `release/v1.0.91` | `79895345` | ۹ درِ main بی‌این / ۲۰ درِ این بی‌main | — | — | — | — | — |
| `release/1.0.91-strategy-fts` | `0dc5d0be` | **۰ عقب / ۷۳ جلو** | ۴۶ | نه | نه | **بله** | **بله** |
| `mission/uiux-strategy-fts-2026-10-18` | `daf7b8f1` | ۰ عقب / ۷۴ جلو | ۴۶ | نه | نه | بله | بله |
| `integration/uiux-2-0-review-2026-10-16` | `65080701` | ۹ عقب / ۳ جلو | ۴۵ | **بله** | **بله** | بله | نه |
| `mission/uiux-2-0-redesign-2026-10-16` | `a3984f02` | ۱۱۱ عقب / ۶۶ جلو | ۶۲ | بله | بله | بله | بله |
| `github/mission/system2-perf-market-hours-2026-10-17` | `9594c7ff` | ۱۱۱ عقب / ۶۱ جلو | ۵۶ | نه | نه | **نه** | نه |

شمارش‌ها: `git ls-tree -r --name-only <ref> -- frontend/src/features/market | wc -l` و
`git rev-list --left-right --count github/main...<ref>`.

### ب) سه واقعیتِ مهمِ هم‌خانوادگی

- `release/1.0.91-strategy-fts` **فرزندِ مستقیمِ** `github/main` است (`main-ahead=0`)؛
  یعنی هرچیز درِ main هست را دارد و ۷۳ کامیتِ جلوتر است. `release/v1.0.91`
  چنین نیست (۹ عقب / ۲۰ عقبِ متقابل) — همان قانونِ شناخته‌شدۀ مخزن که «تگِ
  منتشرشده جدِ `main` نیست».
- نقطۀِ اشتراکِ `integration/uiux-2-0-review-2026-10-16` باِ خطِ انتشار
  `c0402614` است (=`mission/easytrader-adapter-2026-10-15`): شاخۀ review فقط
  **۳** کامیت دارد که خطِ انتشار ندارد، و خطِ انتشار **۸۲** کامیت دارد که review ندارد.
- `TapeTable.tsx` درِ **هر دو** خط ازِ یکِ پایه بازنویسی شده (خطِ انتشار ۶۷ خط
  کم کرده، review ۲۰۴ خط). پس `cherry-pick a7ea0458` قطعاً درِ همان فایل درگیر
  می‌شود؛ کارِ درست «بازنشانیِ محتوایِ تازه رویِ `TapeTable`ِ خطِ انتشار» است،
  نه merge.

### پ) شاخۀ هدفِ پیشنهادی و دلیل

**پیشنهاد: `release/1.0.91-strategy-fts` (0dc5d0be) به‌عنوانِ پایه، باِ یکِ
`mission/tape-workspace-…` تازه ازِ رویِ آن.**

دلیل‌ها، همه قابلِ بازسنجی:

1. تنها ref است که همۀ `main` را دارد و هم استخراج‌هایِ لازمِ بازطراحیِ تابلو
   (`MicroBadge` = پالتِ بج‌ها، `tapeRowTone` = رنگِ جهت + tooltipِ ردیف) را —
   دقیقاً همان دو چیزی که برایِ «دو نما، یکِ منبع» لازم است.
2. تب‌هایِ فضای کاری (`workspaceStore.ts` + `WorkspaceTabs.tsx`) اینجاست؛ هر
   بحثِ «چیدمانِ شخصی» بدونِ این، دوباره‌کاری است.
3. مالک درِ مأموریتِ پیشین همین ref را «شاخۀ مرجعِ انتشار» نامید و دستورِ
   دست‌نخورده‌بودنش را داد؛ پایه‌گذاری رویِ آن باِ آن رأی نمی‌جنگد.
4. اگر بازطراحی باید باِ «استراتژی FTSِ» تازه‌طراحی‌شده هم‌آزمون شود، جانشینِ
   طبیعیِ همان `mission/uiux-strategy-fts-2026-10-18` (daf7b8f1) است — یکِ
   کامیتِ جلوتر، فرزندِ همان پایه.

**با این دو قید:** (الف) `TapeCards`/`tapeColumns` را باید **منتقل** کرد (§۶، بستهٔ T‑۱)،
نه اینکه فرض کنیم وجود دارد؛ (ب) هیچ‌یک ازِ کامیت‌هایِ System 2 فرضِ واردشده
گرفته نمی‌شود (§۳).

### ت) آنچه بررسی **نشد** (صریح)

- `origin/*`: این remote به مسیرِ محلیِ `C:\Users\PCMOD\.cline\data\workspaces\chat\BorsTerminal`
  اشاره می‌کند که رویِ این ماشین وجود ندارد؛ پس `origin/main` یک refِ کهنهٔ محلی است
  و چیزی آن‌جا پنهان نیست (این بند تکرارِ یک واقعیتِ اندازه‌گیری‌شده است، نه بررسیِ زنده).
- وضعیتِ working tree درِ ۲۰+ worktree دیگر (فقط `git worktree list` دیدم؛ diffِ
  فایل‌هایِ دست‌نخوردهٔ آن‌ها را نسنجیدم).
- رفتارِ واقعیِ مرورگر درِ ۱۳۶۶×۷۶۸ برایِ این سند اجرا نشد — اعدادِ عرضِ ستون ازِ
  کامنت‌هایِ سنجش‌شدۀ درِ کد آمده (`TapeTable.tsx:38-46`)، نه ازِ اندازه‌گیریِ تازه.

---

## ۲) ماتریسِ قابلیت‌های فعلیِ تابلوخوانی

«کجا» = پیاده‌سازی؛ «منطق» = جایی که تصمیم گرفته می‌شود؛ «تست» = پرونده‌هایِ
`frontend/src/__tests__`. وضعیتِ شاخه: **M** = `github/main`، **R** =
`release/1.0.91-strategy-fts`، **V** = `integration/uiux-2-0-review-2026-10-16`،
**S** = `mission/system2-perf-market-hours-2026-10-17`.

| قابلیت | هست؟ | کجا / منطق | تست | M | R | V | S |
| --- | --- | --- | --- | --- | --- | --- | --- |
| جستجوی نماد/نام (باِ نرمال‌سازیِ فارسی) | بله | `MarketFilters.tsx:601-610` → `tapeStore.query` (debounce ۲۲۰ms، :510-517)؛ تطبیق درِ `MarketPage.tsx:47` باِ `matchFa` | `market-filters.spec.tsx`، `normalize-fa-search.spec.ts` | ✓ | ✓ | ✓ | ✓ |
| چیپ‌هایِ هفتگانۀ فیلتر تابلو | بله | `QUICK_FILTERS` (`tapeStore.ts:15`)، `SplitFilterChip` (`MarketFilters.tsx:76-171`)؛ داوری درِ `tapeAlgorithms.tapeFilterVerdict:411` و پرچمِ بک‌اند `tape_flags.apply_tape_flags` (`api/market.py:1229-1237`) | `tape-badge-chip-parity.spec.ts`، `tape-unevaluated-display.spec.ts` | ✓ | ✓ | ✓ | ✓ |
| اشتراک/اجتماع (AND/OR) | بله | `screenFilterStore.logic` (`:14`)؛ مصرفِ جدول `MarketPage.tsx:50-55`؛ مصرفِ قیف `api/funnel.py:226-236` | `fts-toolbar-1405-07-21.spec.tsx` | ✓ | ✓ | ✓ | ✓ |
| آستانۀِ شخصیِ هر فیلتر + پیش‌تنظیم | بله | `TapeFilterSettingsModal.tsx` (پرسشِ `parseNum` برایِ ارقامِ فارسی)، `TAPE_PRESETS` (`tapeAlgorithms.ts:143-160`)، ذخیره `bors_tape_filter_config_v2` (`tapeStore.ts:119`) | `tape-algorithms-settings.spec.tsx` | ✓ | ✓ | ✓ | ✓ |
| فیلتر بازار/ابزار، صنعت، فقط‌زنده، جهت، حجم/ماه، پسوندِ عددی | بله | `MarketFilters.tsx:212-258` (منویِ ابزارها)، `:553` (صنعت)، `:619` `live-only-toggle`، `:641` `numeric-suffix-toggle`؛ منطق `tapeStore:45-89` + `MarketPage.applyFilters` | `market-asset-filter.spec.tsx` | ✓ | ✓ | ✓ | ✓ |
| مرتب‌سازی | بله، **محلیِ صرف** | `TapeTable.tsx:325-342` (`useState` + `useMemo`)؛ هیچ sortِ سمتِ سرور نیست | `tape-sort-bench.spec.tsx` | ✓ | ✓ | ✓ | ✓ |
| جدولِ مجازی | بله | `useVirtualizer` `TapeTable.tsx:344-349`، ردیفِ memoیزه :189 | `tape-sort-bench`، `tape-row-flash.spec.tsx` | ✓ | ✓ | ✓ | ✓ |
| دوازده ستونِ ثابت | بله | `HEADERS` `TapeTable.tsx:55-100`، `ROW_GRID` :48-49 | `market-components.spec.tsx` | ✓ | ✓ | ✓ | ✓ |
| **نمایش/پنهانِ ستون** | **نه** | `NOT FOUND` درِ هر چهار شاخه | — | ✗ |  | ✗ |  |
| **ترتیبِ ستون + بازگردانیِ پیش‌فرض** | **نه** | `NOT FOUND` (ساختارِ `HEADERS` ثابت است) | — | ✗ | ✗ | ✗ | ✗ |
| **ستونِ واحدِ مرجع (استخراج)** | ناقص | `tapeColumns.ts` فقط درِ V (۹۸ خط: `HEADERS` + `sortVal` + `SortKey`)؛ R تنها `tapeRowTone`/`MicroBadge` را جدا کرده | `market-mobile-view.spec.tsx:102` | ✗ | ✗ | ✓ | ✗ |
| **نمایِ کارتیِ گوشی** | ناقص | `TapeCards.tsx` (۱۷۲ خط) + سوئیچِ `useMediaQuery(MEDIA_MOBILE)` داخلِ `TapeTable.tsx:186,294-300` درِ V | `market-mobile-view.spec.tsx` (۹ رفتار) | ✗ | ✗ | ✓ | ✗ |
| **نمایِ کاریِ ذخیره‌شدنی (saved view)** | **نه** | `NOT FOUND`؛ نزدیک‌ترین: `TAPE_PRESETS` (فقط آستانه) و `bors-workspace-tabs` (فقط مسیرِ تب) | — | ✗ | ✗ | ✗ | ✗ |
| **غربالگریِ عددیِ دلخواه رویِ فیلدها** | **نه** | فقط `vol_ratio` (`VOL_RATIO_MIN/MAX/DEFAULT` `tapeStore.ts:27-29`) و `LIMIT_PCT` و `direction`؛ هیچ بازۀِ عددیِ عمومی رویِ `q_tot_cap`/`tvol`/`z_tot_tran` نیست | `tape-store.spec.ts` | ✗ |  | ✗ |  |
| ستارهٔ دیده‌بان (سرور) | بله | `WatchlistStar.tsx` درِ ردیف (`TapeTable.tsx:234`) → `shared/api/userWatchlist.ts:49-121` (`/api/watchlist`) | `user-watchlist.spec.tsx` | ✓ | ✓ | ✓ | ✓ |
| انتخابِ چندگانه (☑) | بله | `SymbolSelectBox` داخلِ ستونِ نماد (`TapeTable.tsx:232`)، `selectedSymbolsStore.ts:19` | `market-basket-action.spec.tsx` | ✓ | ✓ | ✓ | ✓ |
| کشویِ «دیده‌بان‌ها» (ساعت/حجم مشکوک/صنایع داغ) | بله | `WatchDrawer.tsx:13-17` → `SuspiciousPanel.tsx`، `IndustryScreener.tsx`؛ هیچ‌چیز ذخیره نمی‌کند | `market-watch.spec.tsx` | ✓ | ✓ | ✓ | ✓ |
| تازگیِ فید و اتصال | بله | `feedFreshness.ts:64-127` (اتصال ≠ تازگی، هشت برچسبِ فارسی)، `FreshnessBadge.tsx` درِ `Topbar.tsx:59` | `m1-ux-integrity.spec.tsx` (درِ S) | ✓ | ✓ | ✓ | ✓+ |
| باژۀِ بازخوانیِ فید (retry/pause/poll) | بله | `MarketFilters.tsx:672-713` (`filters-retry`، `filters-loading`، انتخابِ بازه)؛ `marketStore.ts:5-7,23` (`bors-poll-ms`) | `market-hours-poll.spec.ts` | ✓ | ✓ | ✓ | ✓ |
| انتخابِ نماد باِ کلیک/کیبورد | بله | `TapeTable.tsx:213-222` → `useSymbolStore.setSymbol` | `market-components.spec.tsx` | ✓ | ✓ | ✓ | ✓ |
| پرشِ نماد به تکنیکال/بنیادی/FTS/درخت | بله، **یکی آن‌طرف‌تر** | `SymbolContextStrip.tsx:37-43,175-188` و `CommandPalette.tsx:17-35,51-54` (Ctrl+K)؛ **رویِ خودِ ردیف هیچ لینکی نیست** (`NOT FOUND`) | `symbol-url-param.spec.ts`، `command-palette`آزمونِ مرتبط | ✓ | ✓ | ✓ | ✓ |
| پنلِ جزئیاتِ نماد | بله، سراسری | `widgets/SymbolInspector.tsx` (۱۰۱۳ خط) درِ `AppShell.tsx:152`؛ عرضِ ثابت `--inspector-w` | `inspector-sidebar-stage.spec.tsx` | ✓ | ✓ | ✓ | ✓ |
| تغییرِ اندازهٔ پنل/چیدمانِ آزاد | **نه** | `NOT FOUND` (هیچ splitter/react-resizable درِ فرانت) | — | ✗ |  | ✗ | ✗ |
| تب‌هایِ فضای کاری (چندنمایی) | بله درِ R | `workspaceStore.ts:21` (`bors-workspace-tabs`) + `WorkspaceTabs.tsx:139-155` (Ctrl+T/W/Tab/۱…۹)؛ صراحتاً «نه scroll، نه back، نه split-view» (:3-7) | `workspace-tabs.spec.tsx` (۱۲ رفتارِ قفل‌شده) | ✗ | ✓ | ✗ | ✗ |
| شمارشِ «سنجیده نشد» درِ چیپ | بله | `countUnevaluated`/`verdictBits` (`MarketFilters.tsx:283-295,349+`) | `tape-unevaluated-display.spec.ts` | ✓ | ✓ | ✓ | ✓ |
| علتِ جدولِ خالی (نامِ درها) | بله | `MarketPage.tsx:197-217` (`emptyNote`) | `market-asset-filter.spec.tsx` | ✓ | ✓ | ✓ | ✓ |

### الف) وابستگی‌هایِ داده‌ای که سقفِ طراحی‌اند

| قید | شاهد |
| --- | --- |
| `/api/market` تنها یکِ خواننده دارد و شش مصرف‌کننده | `shared/api/marketFeed.ts:1-8` («تنها خوانندۀ /api/market درِ کلِ برنامه») |
| حجمِ بدنه: ۷٫۵MB → ۴٫۲MB باِ حذفِ ۲۶ کلید؛ gzip ۹۱۳KB → ۵۶۵KB | `shared/types/marketRow.ts:6-12` |
| deltaِ ۲۰۰ نمادی = ۱۴۲KB (gzip ۱۷KB)؛ «چیزی عوض نشده» = **۱۵۸ بایت** | `shared/api/marketFeed.ts:13-14` |
| کشِ اعتبارسنجیِ کلید‌دار (URL + هویتِ اسکیما) و ۳۰۴ | `shared/api/http.ts:46-64` (باِ postmortemِ ۱۴۰۵-۰۷-۰۶) |
| پولینگِ ۵ ثانیه درِ ساعتِ بسته ~۷۵٪ یکِ هسته CPU می‌خورد ⇒ `CLOSED_POLL_MS=5min` | `shared/lib/marketHours.ts:3-6,29-31` |
| افزودنِ یکِ فرزندِ مستقیمِ grid، `ROW_GRID` را ازِ جا می‌زند | `TapeTable.tsx:230-231`، `shared/components/SymbolSelectBox.tsx:8-11` |
| پنلِ جزئیات بی‌باز شدن، هیچ پرسشی نمی‌زند (قیف ۷ تا ۱۱ مگابایت) | `SymbolInspector.tsx:200-202` |
| گاردِ ضدِ کلاسِ ma-jجور: `design-token-guard.spec.ts` (درِ S) | `acd56866` — هر کلاسِ رنگِ تازه باید توکنِ واقعی داشته باشد |

---

## ۳) ممیزیِ تغییراتِ System 2 (و چرا «تابلو» نیست)

`github/mission/system2-perf-market-hours-2026-10-17` = `9594c7ff`؛ ۶۱ کامیتِ
منحصربه‌فرد ازِ `merge-base = f5a10166`؛ `git cherry release/1.0.91-strategy-fts github/mission/system2-…` → ازِ ۶۱ کامیت، ۶۰ تا «+» و صفر «-» (شصت‌ویکم یکِ merge است که `git cherry` نمی‌شمارد)؛ یعنی **هیچ‌کدام** باِ patch-id درِ خطِ انتشار نیست.

| کامیت | چی می‌آورد | فایل‌ها | ربط به تابلوخوانی؟ |
| --- | --- | --- | --- |
| `3e8b917d` | feedsِ فقط‌خواندنیِ پنل‌هایِ وضعیت | `mstat_panels.py` (+۷۳۷ تازه)، `api/market_status.py`، `mstat_engine.py` | نه |
| `ff1b87b8` | فیدِ دسته‌ای + گاردِ قراردادِ پنل | `dev/mstat_status_panels_contract_v1.py` (+۲۹۹) | نه |
| `944bcf47` | بازسازیِ تبِّ وضعیت به هشت بخش (Binder1) | `StatusShell.tsx`، `MarketSectionNav.tsx`، `MarketTreemap.tsx` (+۳۴)، `OrderOwnershipSection.tsx`، `RankedPanels.tsx`، `Sparkline.tsx`، `MarketGlanceCards.tsx`، `tones.ts`، `treemapLayout.ts`، `MarketStatusPage.tsx` (+۲۰۸) — ۲۲ فایل، +۴۳۲۱ | **نه** (همۀ فایل‌ها `market-status`/وضعیت‌اند) |
| `0d0b76fe` | کلیدِ کشِ اسنپ‌شات بر پایهٔ وضعیتِ بانک | `api/market_status.py`، `mstat_engine.py`، `dev/mstat_snapshot_cache_v1.py` (+۱۹۳) | نه |
| `4074f2d9` | «تابلویِ نشستِ پیشین کهنه است» | `MarketStatusPanel.tsx`، **`shared/components/FreshnessBadge.tsx`**، **`shared/lib/feedFreshness.ts`**، `m1-ux-integrity.spec.tsx` | **بله — مشترک**: همان بجی که بالایِ تابلو است |
| `acd56866` | رفعِ کلاسِ ma-jورِ بی‌رنگ + گاردِ توکن | `design-token-guard.spec.ts` (+۱۰۴)، و ۸ فایل از جمله **`WatchlistStar.tsx`**، **`SymbolInspector.tsx`**، `Topbar.tsx` | **بله — مشترک**: سه فایلِ دست‌خورده‌اش درِ مسیرِ تابلو هستند |

**سه تصمیمِ جدا که خودسرانه گرفته نمی‌شود:**

1. `feedFreshness`/`FreshnessBadge` (4074f2d9): اصلاحِ صادق بودنِ «تازه» درِ **هر دو**
   تب. خطِ انتشار هم رویِ همین فایل‌ها رفته (`WidgetFreshness.tsx` +۱۸۳،
   `preloadMarketStatusFirstScreen.ts` +۲۹) → **تعارضِ محتمل**، نه صرفِ افزوده.
2. `design-token-guard` (acd56866): یکِ گاردِ CI تازه که هر بازطراحیِ تابلو را
   ملزم می‌کند ازِ توکن‌هایِ `tokens.css` بیرون نزند. ارزشِ افزوده‌اش برایِ این
   مأموریت زیاد است؛ ولی گارد را نباید درِ میانهٔ کارِ دیگران وارد کرد.
3. هشت‌بخشیِ «وضعیت بازار»: مالک صریح گفته این صفحه نقشِ مستقلِ خودش را حفظ کند
   (§۵) — پس آوردنش به تابلو **ممنوع** است و تصمیمِ merge آن جدا ازِ این مأموریت است.

همچنین `mission/market-status-parity-tradersarena-2026-10-17` (`7d9d0e4f`) کارِ
تطبیقِ همان صفحه با TradersArena است (تسک #۱۵/#۱۷ باز) — سه‌ام درِ همین سند نیست.

---

## ۴) ماتریسِ تصمیمِ محصول

پنج دسته: **حفظ** / **بهبود** / **افزودن** / **ادغام-انتقال** / **حذف**.
اولویت: P۰ (بدونِ آن بازطراحی ناقص است) … P۳ (بعداً). «عدمقطعیت» یعنی رأیِ مالک لازم است.

| # | مورد | تصمیم | اولویت | شواهد و دلیلِ محصولی | وابستگی | معیارِ پذیرش |
| --- | --- | --- | --- | --- | --- | --- |
| ۱ | هفت چیپ + AND/OR + آستانه‌ها | **حفظِ بی‌تغییرِ منطق** | P۰ | `tapeStore.ts:15`، `MarketPage.tsx:50-55`، `api/funnel.py:226-236`؛ مالک خودِ «هفت فیلتر» را می‌شمارد و فرمول‌ها جزوه‌ای‌اند | — | هیچ عددِ چیپ و هیچ ردیفی باِ بازطراحی جابه‌جا نشود (سنجشِ قبل/بعد رویِ همان فید) |
| ۲ | شمارشِ وابسته‌به‌نامزد + «سنجیده نشد» + علتِ جدولِ خالی | **حفظ** | P۰ | `MarketFilters.tsx:283-331`، `MarketPage.tsx:197-217`؛ این‌ها پاسخِ سه شکایتِ واقعیِ مالک‌اند | — | رفتارِ فعلی مو‌به‌مو درِ تست‌هایِ موجود بماند |
| ۳ | مرجعِ واحدِ ستون/ترتیب (`tapeColumns.ts`) | **بهبود (پورت ازِ V)** | P۰ | درِ V هست (۹۸ خط) و `TapeTable`ِ R هنوز `HEADERS` را درِ خودش دارد (`TapeTable.tsx:55-100`)؛ بدونِ آن، هر فیچرِ ستون دو نسخه می‌شود | ۱ | `TapeTable` و `TapeCards` وِ هر منویِ ستون ازِ یکِ `HEADERS` بخوانند؛ `market-mobile-view.spec.tsx:102` سبز بماند |
| ۴ | نمایش/پنهانِ ستون + ترتیب + بازگردانی | **افزودن** | P۰ | `NOT FOUND` درِ هر چهار شاخه؛ Webull هم همین سه کنش را می‌دهد (ستون‌ها، ترتیب، بازنشانی) نه بیشتر | ۳، ۸ | ستونِ پنهان ازِ DOM بیرون می‌رود (نه `display:none`)، `ROW_GRID` باِ ستونهایِ مانده بازمحاسبه می‌شود، «بازگردانیِ پیش‌فرض» به همان دوازده ستون برمی‌گردد، و refresh صفحه حالت را نگه می‌دارد |
| ۵ | نماهایِ کاریِ ذخیره‌شدنی (فیلتر+AND/OR+مرتب‌سازی+ستون‌ها) | **افزودن** | P۱ | هیچ saved view نیست؛ `TAPE_PRESETS` فقط آستانه است (`tapeAlgorithms.ts:143-160`)؛ `bors-workspace-tabs` فقط مسیرِ تب است (`workspaceStore.ts:3-7`) | ۴، ۸ | ذخیره/بارگذاری/حذفِ نما؛ نامِ پیش‌فرضِ روشن؛ خرابیِ رکوردِ ذخیره‌شده صفحه را سفید نمی‌کند (الگویِ `workspaceStore.ts:65-84`) |
| ۶ | نماهایِ آماده (نوسانِ روزانه / پولِ هوشمند / نقدشوندگی / صف‌ها) | **افزودن، باِ علامت عدمقطعیت** | P۲ | هیچ کاتالوگِ «نما» درِ مخزن نیست؛ نزدیک‌ترین: `ASSET_QUICK_PRESETS` (`tapeStore.ts:92-98`) و `TAPE_PRESETS`. **تعریفِ نام‌ها و مجموعۀِ هر نما رأیِ مالک است، نه تصمیمِ من** (قاعده: آستانه و دروازۀ روش را من نمی‌سازم) | ۵ | بعد ازِ تعیینِ نام‌ها: هر نما یکِ دکمه + یکِ رکوردِ ذخیره‌شده؛ بدونِ عددِ ساختگی |
| ۷ | غربالگریِ عددیِ ترکیبی رویِ فیلدهایِ واقعی | **افزودن** | P۱ | امروز فقط `vol_ratio` و `LIMIT_PCT` وِ `direction` عددی‌اند (`tapeStore.ts:24-29,45-63`)؛ هیچ بازۀِ دلخواهی رویِ `tvol`/`q_tot_cap`/`z_tot_tran`/`p_last` نیست. دامنه‌شان ازِ `MarketRowSchema` خوانده می‌شود (`marketRow.ts:27-182`) — پس «فیلدی که داده‌اش نیست» قابلِ پیشنهاد نیست | ۵، ۹ | هر شرطِ تازه فقط رویِ ستونی ساخته شود که درِ پاسخِ سرور `null`-پذیرِ مستند دارد؛ صفحۀ خالی باِ «علتِ درها» کار کند (`emptyNote`) |
| ۸ | پایداریِ تنظیماتِ شخصی (محلِ ذخیره + نسخه) | **بهبود** | P۰ | امروز ده‌ها کلیدِ localStorage باِ **چهار** قراردادِ نام‌گذاریِ جدا (`bors-x`، `bors_x_v1`، `bors:x:y:v1`، `fts.x.v1`) و بدونِ `migrate()`؛ تنها مهاجرتِ واقعی `ftsConfigStore.ts:153-154,214`. تصمیمِ فنی: برایِ «نماها» یکِ store باِ یکِ کلیدِ `…v1` و یکِ envelope باِ `version` | — | رکوردِ ناشناخته ⇒ بی‌سروصدا به پیش‌فرض، نه کرش؛ bumpِ نسخه باِ تستِ round-trip (الگویِ `workspace-tabs.spec.tsx:145-159`) |
| ۹ | ستون/فیلدِ تازه‌ای که داده‌اش نیست | **حذفِ پیشنهاد — افزودنِ مشروط** | P۰ | قاعدهٔ مخزن: غایب ⇒ «سنجیده نشد»، نه صفر (`tape-unevaluated-display.spec.ts`)؛ `f_smart`/`f_legal` عمداً چرخدنده ندارند (`MarketFilters.tsx:74`) | ۷ | هیچ کنترلِ تازه‌ای بدونِ ستونِ واقعی درِ `MarketRowSchema` ساخته نشود |
| ۱۰ | پرشِ سریعِ نماد ازِ خودِ ردیف به تکنیکال/بنیادی/FTS/دیده‌بان | **افزودن** | P۱ | امروز ردیف فقط `onSelect` دارد (`TapeTable.tsx:213-222`)؛ لینک‌ها یکی آن‌طرف‌تر درِ inspector‌اند (`SymbolInspector.tsx:978-1000`) یا درِ stripِ بالایِ صفحه (`SymbolContextStrip.tsx:175-188`) | — | یکِ کنشِ واضح رویِ ردیف (مثلاً ➦) که باِ همان `useNavigate` وِ `SYMBOL_ROUTES` برود؛ کلیکِ معمولیِ ردیف دست‌نخورده بماند؛ هیچ درخواستِ تازه‌ای درِ hover نرود |
| ۱۱ | رفتارِ پنلِ جزئیات درِ عرض‌هایِ مختلف | **بهبود** | P۱ | پنل سراسری است باِ عرضِ ثابتِ `--inspector-w: 15rem` (`tokens.css:46`) و `padding-left`ِ همان (`index.css:512`)؛ زیرِ ۱۰۲۴px نیاز به ژستِ کاربر دارد (`SymbolInspector.tsx:326-352`)؛ `max-w-[88vw]` (:428) | ۱۲ | سه رفتارِ مشخص: دسکتاپِ عریض = کنارِ ثابت؛ ۱۳۶۶ = بدونِ بلعیدنِ عرضِ جدول؛ گوشی = overlayِ کامل. هیچ‌کدام باِ تغییرِ منطقِ داده همراه نباشد |
| ۱۲ | تغییرِ اندازهٔ پنل‌ها (resize/splitter) | **افزودن — باِ ارزیابیِ فنیِ اول** | P۲ | `NOT FOUND` درِ کلِ فرانت؛ یعنی کتابخانه‌ای درِ `package.json` نیست و `ROW_GRID` ثابت است. ارزیابیِ فنیِ لازم: هزینهٔ reflow درِ جدولِ مجازی + تعاملِ `--inspector-w` باِ `padding-left` | ۱۱ | ابتدا سندِ کوتاهِ «چطور و باِ چه هزینه‌ای»، سپس پیاده‌سازی؛ drag باِ ماوس و کیبورد هر دو کار کنند |
| ۱۳ | چیدمانِ آزادِ پیشرفته (drag-drop پنل‌ها) | **افزودنِ مشروط / فعلاً نه** | P۳ | هیچ زیرساختی نیست؛ و مالک درِ `workspaceStore.ts:3-7` صریح نوشته «برایِ شبیه‌سازیِ مرورگر state manager پیچیده نساز» و split-view را رد کرده | ۱۲ | تا وقتی مالک نخواهد، درِ بک‌لاگ هم به‌عنوانِ «کارِ باز» ثبت نمی‌شود؛ فقط «قابلِ افزودن بعد ازِ ۱۲» علامت می‌خورد |
| ۱۴ | نمایِ کارتیِ گوشی (`TapeCards`) | **حفظِ بیرونِ خط + پورت** | P۱ | فقط درِ V؛ ۹ رفتارِ قفل‌شده درِ `market-mobile-view.spec.tsx`؛ باِ «تکراری نساز» (§۵) نمی‌جنگد چون برایِ همان داده، نمایِ فشرده است نه بلوکِ تازه | ۳ | پورت رویِ R بدونِ تغییرِ رفتارِ دسکتاپ (`market-mobile-view.spec.tsx:125` این را قفل می‌کند) |
| ۱۵ | سه «دیده‌بانِ» هم‌زمان (سرور / `bors-portfolio-watch` / `bors-selected-symbols-v1`) + pin | **ادغامِ واژگانی، نه حذفِ داده** | P۲ | `WatchlistStar.tsx:3-6` خودِ تفکیک را مستند کرده؛ `watchSymbolsStore.ts:3-9` می‌گوید آن store سرور نیست؛ `symbolStore.ts:7-9` چهارمی را اضافه می‌کند. حذفِ هرکدام = حذفِ قابلیتِ واقعی | — | یکِ مسیرِ روشن برایِ «کجا ذخیره می‌شود» درِ رابط؛ هیچ store‌ای بی‌رأیِ مالک حذف نشود |
| ۱۶ | بلوک‌هایِ وضعیتِ بازار/نبض رویِ `/market` | **حذف‌شده — بازنگرداندن نه** | P۰ | رأیِ صریحِ مالک درِ `MarketPage.tsx:235-237`؛ تبِّ مستقل `market-status` (`routes.tsx:16-19`) | — | بازطراحی هیچ «خلاصۀ بازار» تکراری به تابلو برنگرداند |
| ۱۷ | ستون‌هایِ معاملاتیِ موجود (سرانهٔ خرید/فروش، اختلاف٪، حجم/ماه) | **حفظ** | P۰ | `HEADERS:55-100` باِ hint‌هایِ TSETMC (`pcp`/`plp`/`tno`/`q_tot_cap`)؛ این‌ها همان چیزی‌اند که جزوه می‌گوید | ۴ | هیچ‌کدام درِ «پیش‌فرضِ تازه» پنهان نشوند؛ حذفِ فقط باِ انتخابِ کاربر درِ منویِ ستون |

---

## ۵) محدودیت‌هایِ طراحی (قیدهایی که کد تحمیل می‌کند)

1. **تکرارِ ممنوع**: «وضعیت بازار»، «نبض» و «نمودارِ درونروز» صفحهٔ مستقلِ خودش را
   دارد (`routes.tsx:16-19`، `MarketStatusPage.tsx`) و رأیِ مالک درِ
   `MarketPage.tsx:235-237` ثبت شده. بازطراحیِ تابلو مجاز به آوردنِ دوباره‌شان نیست.
2. **حذفِ قابلیت برایِ خلوتی ممنوع**: هر ۱۲ ستون و هر ۷ چیپ پشتِ یکِ سطرِ کدِ
   مستندند (`TapeTable.tsx:38-46` توضیحِ سنجشِ عرض؛ `MarketFilters.tsx:72-74` توضیحِ
   «چرخدندۀ بیمحتوا دکمۀِ جعلی است»). اگر جایی شلوغ است، پاسخ «مدیریتِ ستون +
   نما» است، نه حذف.
3. **منطقِ فیلتر/فرمول/داده درِ این مرحله دست‌نخورده**: `tapeAlgorithms.ts`،
   `tape_flags.py`، `api/market.py:1229-1237`، `api/funnel.py:226-236`. بازطراحی
   فقط *نمایش* و *انتخاب* را می‌سازد؛ داوری را نه.
4. **عملکرد**: هر فیچرِ تازهٔ ردیف‌محور باید باِ `overscan:12` و ارتفاعِ ثابتِ ۴۰
   بسازد؛ `ROW_GRID` literal است و افزودنِ فرزندِ grid آن را می‌شکند
   (`TapeTable.tsx:230-231`)؛ هیچ پرسشِ تازهای نباید به‌ازایِ ردیف زده شود
   (فید، ۴٫۲ مگابایت، `marketFeed.ts:1-8`).
5. **خوانایی درِ ۱۳۶۶×۷۶۸**: کفِ عرضِ جدول `min-w-[1100px]` است و ارتفاعش
   `calc(100dvh-260px)` (`TapeTable.tsx:47,430`)؛ پنلِ جزئیات `15rem` ازِ همان
   عرضِ ۱۳۶۶ را برمی‌دارد (`tokens.css:46` + `index.css:512`) — پس «پنلِ عریضِ
   پیش‌فرض» خودش یکِ تصمیمِ طراحی است، نه جزئیات.
6. **صفحه‌هایِ بزرگ**: تنها اهرمِ امروز `max-w-none` ریشۀِ `/market`
   (`MarketPage.tsx:234`) است؛ هیچ چیدمانِ چندستونه‌ای درِ سطحِ صفحه نیست.
7. **زبانِ رابط**: کوتاه + واژگانِ جزوه (قاعدهٔ مخزن درِ `AGENTS.md`)؛ هیچ استعاره‌ای
   درِ متنِ دیدنی نه. برچسب‌هایِ ستون عمداً کوتاه‌اند و واحد درِ `title` مانده
   (`TapeTable.tsx:56-59`).
8. **توکن‌ها**: اگر گاردِ `design-token-guard` (ازِ System 2) اضافه شود، هیچ کلاسِ
   رنگِ تازه بدونِ توکن رد می‌شود — بهتر است زودتر تصمیم گرفته شود تا اینکه ۲۰ فایلِ
   تازه بسازد.

---

## ۶) بک‌لاگِ پیشنهادی (بسته‌هایِ کوچک، باِ ترتیب)

هر بسته یکِ واحدِ قابلِ آزمون است و بی‌مجوزِ مالک کد نمی‌نویسد.

| بسته | کار | وابستگی | معیارِ پذیرش | ریسک |
| --- | --- | --- | --- | --- |
| **T‑۰** | سندِ پایه: عکسِ وضعیتِ امروز درِ ۱۳۶۶ و ۱۹۲ + شمارشِ ردیف/ستونِ دیده‌شده + ثبتِ عددِ `cardHeight`/`tableHeight` | — | عددِ قبل/بعد برایِ هر بندِ بعدی آماده باشد | پایین |
| **T‑۱** | پورتِ `tapeColumns.ts` رویِ پایه (استخراجِ `HEADERS`/`sortVal`/`SortKey` ازِ `TapeTable`) وِ هم‌راستاسازیِ `TapeTable` باِ آن | T‑۰، §۴‑۳ | هیچ تغییرِ رفتاری؛ `market-components`، `tape-sort-bench`، `tape-row-flash` سبز؛ `HEADERS` تنها ازِ یکِ فایل خوانده شود | متوسط (تعارضِ بازنویسیِ یکِ فایل) |
| **T‑۲** | پورتِ `TapeCards.tsx` + سوئیچِ `useMediaQuery(MEDIA_MOBILE)` + `market-mobile-view.spec.tsx` | T‑۱ | ۹ رفتارِ قفل‌شدۀ V درِ پایه سبز؛ دسکتاپ بی‌تغییر | متوسط |
| **T‑۳** | منویِ ستون: نمایش/پنهان + ترتیب + بازگردانیِ پیش‌فرض (ذخیره درِ کلیدِ نسخه‌دار) | T‑۱، T‑۵ | ستونِ پنهان ازِ DOM بیرون؛ `ROW_GRID` بازمحاسبه؛ refresh حفظ کند؛ بی‌مقدارِ ساختگی درِ ستونِ خالی | بالا (چیدمانِ grid) |
| **T‑۴** | کنشِ پرشِ سریع رویِ ردیف (➦ → تکنیکال/بنیادی/FTS/دیده‌بان) | — | کلیکِ ردیف دست‌نخورده؛ بی‌درخواستِ hover؛ مسیرها ازِ `SYMBOL_ROUTES` | پایین |
| **T‑۵** | storeِ تنظیماتِ شخصیِ تابلو (یکِ store، یکِ کلید، envelope باِ `version`، ردِّ رکوردِ خراب) | — | تستِ round-trip + تستِ رکوردِ خراب؛ هیچ store دیگری حذف نشود | پایین |
| **T‑۶** | نماهایِ ذخیره‌شدنی (ساخت/ذخیره/بارگذاری/حذف) رویِ T‑۳..T‑۵ | T‑۳، T‑۴، T‑۵ | نما چهار چیز را برمی‌گرداند: چیپ‌ها، AND/OR، مرتب‌سازی، ستون‌ها؛ «نمایِ فعلی» همیشه روشن است | متوسط |
| **T‑۷** | غربالگریِ عددیِ ترکیبی رویِ فیلدهایِ مستندِ `MarketRowSchema` | T‑۵، (T‑۶ اختیاری) | هیچ فیلدی بدونِ ستونِ واقعی پیشنهاد نشود؛ «سنجیده نشد» ≠ «رد» | متوسط (وسوسۀ افزودنِ آستانهٔ ساختگی — خطِ سرخِ مالک) |
| **T‑۸** | رفتارِ پنلِ جزئیات درِ سه عرض + تصمیمِ `--inspector-w` | T‑۲ | ۱۳۶۶ بدونِ اسکرولِ افقیِ اضافه؛ گوشی overlayِ کامل | متوسط |
| **T‑۹** | ارزیابیِ فنیِ resize/splitter (سند، نه کد) + تصمیمِ مالک | T‑۸ | هزینه/فایده باِ عدد؛ اگر رد شد، T‑۱۰ ساخته نمی‌شود | — |
| **T‑۱۰** | (مشروط) تغییرِ اندازهٔ پنل‌ها | T‑۹ | فقط بعد ازِ رأیِ مثبتِ مالک | بالا |

**ترتیبِ اجرا:** T‑۰ → T‑۱ → T‑۲ → T‑۵ → T‑۳ → T‑۴ → T‑۶ → T‑۷ → T‑۸ → T‑۹ (→ T‑۱۰).
دو بسته می‌توانند موازی بروند: T‑۴ مستقلِ همه است؛ T‑۵ فقط باید پیش ازِ T‑۳ تمام شود.

---

## ۷) تست‌هایِ لازم برایِ جلوگیری ازِ رگرسیون

| لایه | تست | چرا |
| --- | --- | --- |
| داده/منطق | `tape-badge-chip-parity.spec.ts`، `tape-screening-reconcile.spec.tsx`، `tape-fuzz-parity.spec.ts` | عددِ چیپ، بجِ ردیف و رأیِ قیف باید هم‌خوان بمانند؛ هیچ بازطراحیِ نمایشی نباید رأی را عوض کند |
| داده | `tape-unevaluated-display.spec.ts`، `market-asset-filter.spec.tsx` | «سنجیده نشد» ≠ «رد»؛ علتِ جدولِ خالی باید بماند |
| شمارش | `fts-toolbar-1405-07-21.spec.tsx` | شمارشِ وابسته‌به‌نامزد و AND/OR قفل‌هایِ صریحِ مالک‌اند |
| تعامل | `market-components.spec.tsx`، `market-filters.spec.tsx`، `market-filter-popover.spec.tsx`، `tape-algorithms-settings.spec.tsx` | کلیک/کیبورد/پاپاور/مدال |
| تازه (ستون) | `tape-columns.spec.tsx` (ساختنی) | پنهان‌کردنِ ستون نباید ترتیبِ بقیه را به‌هم بریزد؛ «بازگردانی» باید به همان دوازده برگردد؛ ستونِ پنهان نباید درِ DOM بماند |
| تازه (نما) | `tape-views.spec.tsx` (ساختنی) | round-trip ذخیره/بارگذاری؛ رکوردِ خراب ⇒ پیش‌فرضِ بی‌سروصدا؛ بی‌عددِ ساختگی |
| عملکرد | `tape-sort-bench.spec.tsx` + یکِ سنجهٔ زمانِ رندر رویِ ۵٬۸۰۰ ردیف | جدولِ مجازی نباید باِ منویِ ستون به reflowِ کامل بیفتد؛ مبنایِ عددیِ امروز درِ `CommandPalette.tsx:39-40` (۵٬۸۰۰ ردیف) ثبت شده |
| شبکه | `market-feed-delta.spec.ts`، `market-hours-poll.spec.ts` | delta/304 و ریتمِ پولینگ نباید باِ فیچرِ تازه بشکند (۱۵۸ بایت درِ حالتِ بی‌تغییری) |
| responsive | `market-mobile-view.spec.tsx` (پورتی) + `ui-tabs-a11y.spec.tsx` + `inspector-sidebar-stage.spec.tsx` | گوشی/دسکتاپ/کیبورد/ARIA |
| زندهٔ مرورگر | `tools/jev_ui_check.mts` رویِ `#/market` درِ ۱۳۶۶×۷۶۸ و ۱۹۲۰×۱۰۸۰ + کاوشگرِ ارتفاعِ کارت (الگویِ `tools/broker_connect_ui_check.mts`) | قاعدهٔ مخزن: سبزبودنِ jsdom اثباتِ UI واقعی نیست؛ رأیِ «PASSِ بصری» باِ مالک است، نه من |
| گارد | `dev/run_all_tests.py` کامل + سه قرمزِ ازپیش‌موجود (`npm_lock_v1040`، `candle_integrity…`، `db_housekeeping…`) باِ تفکیکِ صریح | ادعای «سبز» بی‌سبزکردنِ قرمزهایِ بی‌ربط |

---

## ۸) پرسش‌هایِ مسدودکننده (بدونِ رأیِ مالک حل نمی‌شوند)

1. **پایه کدام باشد؟** `release/1.0.91-strategy-fts` (پیشنهادِ من) یا
   `mission/uiux-strategy-fts-2026-10-18` (اگر بازطراحیِ تبِّ استراتژی FTS باید درِ
   همان بازطراحی دیده شود) یا `github/main` (که هیچ‌کدام ازِ استخراج‌ها را ندارد)؟
2. **نماهایِ آماده:** نام‌ها و مجموعۀِ هر نما رأیِ جزوه‌ای است. من هیچ آستانه‌ای
   نمی‌سازم؛ بگویید چند نما، باِ چه نام‌ها و هرکدام کدام چیپ/آستانه/ستون‌ها.
3. **پنلِ جزئیات:** درِ ۱۳۶۶ باید چسبیده بماند (۲۴۰px ازِ عرضِ جدول می‌خورد) یا
   رویِ جدول overlay شود؟ پاسخ، تصمیمِ T‑۸ و T‑۹ را عوض می‌کند.
4. **resize:** می‌خواهید؟ اگر بله، فقط پنلِ جزئیات یا هر بلوکِ صفحه؟ (قبلاً
   split-view درِ `workspaceStore.ts:3-7` رد شده است.)
5. **سه «دیده‌بان»:** ادغامِ واژگانی درِ رابط می‌خواهم (بدونِ حذفِ داده) یا سه‌تا
   بمانند؟
6. **System 2:** سه موردِ مشترک (`feedFreshness`، `design-token-guard`،
   `WatchlistStar`/`SymbolInspector`) را اول merge می‌کنیم یا بازطراحیِ تابلو را
   رویِ پایهٔ فعلی می‌بریم و بعداً جمع می‌زنیم؟
7. **ستون‌هایِ پیشنهادیِ تازه:** هیچ‌کدام را «موجود» فرض نمی‌کنم. اگر ستونی
   می‌خواهید که درِ `MarketRowSchema` نیست، باید اول منبعِ TSETMC/codal آن ثابت شود.

---

## ۹) ارجاع‌هایِ کلیدی (برایِ بازبینیِ سریع)

- `frontend/src/features/market/routes/MarketPage.tsx:24-65` (applyFilters)،
  `:197-217` (emptyNote)، `:233-265` (چیدمانِ سه‌بلوکیِ فعلی)
- `frontend/src/features/market/components/TapeTable.tsx:48-100` (ستون‌ها)،
  `:325-349` (مرتب‌سازی + مجازی‌سازی)، `:430` (ارتفاعِ جدول)
- `frontend/src/features/market/components/MarketFilters.tsx:76-171` (چیپ)،
  `:283-331` (شمارش)، `:535-720` (نوارِ کنترل)
- `frontend/src/features/market/stores/tapeStore.ts:15-131` (حالتِ فیلترها)
- `frontend/src/shared/stores/screenFilterStore.ts:14`،
  `frontend/src/shared/stores/workspaceStore.ts:3-24`
- `frontend/src/shared/api/marketFeed.ts:1-24,126-174`،
  `frontend/src/shared/types/marketRow.ts:6-12,194-234`
- `frontend/src/widgets/SymbolInspector.tsx:200-202,428-431,978-1000`
- `integration/uiux-2-0-review-2026-10-16` → `frontend/src/features/market/lib/tapeColumns.ts`،
  `components/TapeCards.tsx`، `src/__tests__/market-mobile-view.spec.tsx`
- `github/mission/system2-perf-market-hours-2026-10-17` → `mstat_panels.py`،
  `components/StatusShell.tsx`، `components/MarketTreemap.tsx`،
  `src/__tests__/design-token-guard.spec.ts`
