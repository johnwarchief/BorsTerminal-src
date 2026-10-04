# UX-REDESIGN-RESEARCH — گزارش تحقیق و معماری پیشنهادی (پیش از هر refactor)

مبنای این سند: ممیزی کامل وضعیت فعلی (سه گزارش جدا با file:line)، تحقیق وب روی
۱۵+ محصول ممتاز، و قیدهای مالک: **حذف هیچ capability‌ای ممنوع؛ منطق FTS،
ودوی هفتگی، ساعت شنی، adjustment و معنای داده دست‌نخورده.**

فلسفۀ طراحی که از تحقیق بیرون آمد (نه کپی هیچ محصول):

> **Professional Financial Decision Workspace — quiet by default, powerful when
> needed.** ترتیب ذهنی در هر صفحه: Find → Understand → Analyze → Decide → Act.
> رنگ فقط زبانِ قیمت و وضعیت است؛ سلسله‌مراتب را تایپوگرافی می‌سازد، نه
> باکس و حاشیه؛ نماد، شهروند درجه‌یک است نه فیلترِ هر صفحه.

---

## A — محصولات بررسی‌شده

| # | محصول | چرا در این تحقیق |
|---|---|---|
| 1 | TradingView | مرجع مستقیم: workspace حول چارت، dock تب‌شده، watchlist به‌عنوان سوییچرِ context |
| 2 | Bloomberg Terminal | نوار ارجpersistent (topline)، بارِ فرمان <GO>، «یک ابزار، ده صفحهٔ لینک‌شده» |
| 3 | LSEG/Refinitiv Workspace | پیشخوان tile-based و خطر tile sprawl (anti-pattern) |
| 4 | Koyfin | صفحۀ entity-محور با تب (Overview/Financials/Charts) — نزدیک‌ترین آنالوگ وب مدرن |
| 5 | Finviz | اسکرینر متراکم + hover-preview؛ و شکست‌های خوانایی‌اش (anti-pattern) |
| 6 | TIKR / YCharts / Quartr | سلسله‌مراتب عدد→صورت‌حساب→یادداشت؛ «عددها ابرلینک‌اند» |
| 7 | Grafana | متغیر سراسری = مدل رسمیِ contextِ نماد مشترک بین پَنل‌ها |
| 8 | Trade Ideas / TrendSpider | قیف اسکن→واچ‌لیست→پلن با تحویلِ تک‌کلیکی و state پایدار |
| 9 | Linear | quiet UI، سلسله‌مراتب تایپوگرافیک، command menu سه‌لایه، copy-link با state |
| 10 | Raycast | launcher-first، parameterized actions، alias، رتبه‌بندی فراوانی |
| 11 | Notion | favorites/recent در بالای ناوبری، quick-find |
| 12 | Obsidian | quick switcher + multi-pane layout ذخیره‌شدنی |
| 13 | VS Code / Cursor | palette با keyhint اینلاین، breadcrumb، per-tab state |
| 14 | Figma | rail واکنش‌مند به انتخاب (content changes, placement never)؛ focus mode |
| 15 | Slack/Discord | quick switcher روی هزاران شیء؛ جداسازی signal از ambient |
| 16 | Spotify | نوار now-playing = درسِ persistent context strip |
| 17 | Arc/Dia | command bar به‌عنوان ورودی جهان‌شمول (و درسِ مرگ محصول/پیروزی الگو) |
| 18 | Things 3 / Apple (Liquid Glass) | hierarchy بدون chrome؛ هشدار اپل: شیشه روی سطحِ داده‌محور ممنوع |
| 19 | Vercel/Stripe Dashboard | state discipline: empty/error نام‌دار با دقیقاً یک CTA؛ skeleton به‌شکلِ layout |
| 20 | NN/g (دیتابل‌ها و empty state) | ستون هویت sticky، سه دانسیته، disclosure سه‌لایه |

## B — الگوهای برتر کشف‌شده (با منبع)

1. **Context سراسریِ یک‌جا (Grafana variable / TradingView)**: یک «نمادِ انتخابی»
   که همه پَنل‌ها از آن تغذیه می‌کنند؛ تغییرش رویدادِ ناوبری است نه دیالوگ.
2. **نوار ارجِ قیمت persistent (Bloomberg top-line / Spotify now-playing)**:
   نماد + قیمت + تغییر، همیشه در دید، زیر هر صفحه.
3. **بارِ فرمان/جستجوی جهان (Bloomberg <GO> + Raycast + Linear)**: یک ورودی، سه
   شیار نتیجه — نماد، صفحه، فرمان — با hintِ کلید اینلاین.
4. **Dock تب‌شده کنارِ انتیتی (TradingView right dock / Koyfin tabs)**: جزییات
   نماد در ستون ثابت با تب، نه در صفحه‌های جدا که context را می‌شکنند.
5. **تحویل تک‌کلیکی بین مراحل تصمیم (Trade Ideas)**: خروجی هر مرحله ورودی مرحله
   بعد است و نتایجِ اسکن بین نشست‌ها زنده می‌مانند (قیف ما این را با snapshot
   Round M/78 شروع کرده).
6. **عدد به‌عنوان ابرلینک (TIKR)**: هر عددِ داوری به ردیفِ منبعش (کدال/تابلو)
   لینک شود — همان ردیابی «بی‌دوره».
7. **Disclosure سه‌لایه (NN/g + Linear)**: بج + دلیلِ یک‌خطی همیشه؛ عوامل با
   hover/click؛ مدرک کامل با درخواست. صفحهٔ اول نباید شبیه لایهٔ سوم باشد.
8. **quiet UI و رنگِ معنا‌دار**: رنگ فقط برای جهت قیمت و وضعیت؛ جداسازی
   signal از ambient (Slack) — یک glyph (animate-pulse) نباید سه معنا داشته باشد.
9. **جدول متراکمِ RTL**: ستون هویت sticky در لبۀ راست، هدر منجمد، گروه‌های
   ستون تاشو، sparkline در سلول ≤۱۶px (درس‌های Finvizِ مثبت + منفی).
10. **State discipline (Stripe/Vercel)**: هیچ حالت خالی/خطا blanks نباشد؛ علت
    نام‌دار + یک CTA؛ skeleton به‌شکلِ خودِ محتوا.
11. **rail واکنش‌مند با جای ثابت (Figma)**: محتوای پنلِ انتخاب عوض می‌شود،
    محلش هرگز. (درسِ ضدِ 2025 Dev Mode فیگما: جابه‌جایی پنل = شورشِ کاربران.)
12. **favorites + recent در بالای ناوبری (Notion/TV)**: سوییچرِ context از
    لیستِ شخصیِ کاربر تغذیه شود.

## C/D — تطبیق الگو → مشکل فعلی (جدول اصلی)

| UX Problem | رفتار فعلی (شاهد) | مرجع | الگوی مرجع | راه‌حل پیشنهادی | فایده | پیچیدگی | اولویت |
|---|---|---|---|---|---|---|---|
| palette فقط نماد می‌شناسد و ۳ مقصد دارد | `CommandPalette.tsx:13-19,15-19` | Raycast/<GO>/Linear | سه شیار نتیجه + keyhint | Palette v2: نماد/صفحه/فرمان + اخیرها | یک کلید = هر مقصد | متوسط | **P0** |
| context نماد سه مدل دارد (store-only / URL-first / جعلی) | `MarketPage.tsx:78` vs `TechnicalPage.tsx:48` vs `TechnicalPage.tsx:52` (فولادِ جعلی بدون ستور) | Grafana / TV | یک متغیر سراسری، URL بازتابش | قاعده واحد: `params ?? stored` + نوشتن URL هنگام انتخاب؛ پیش‌فرضِ فولاد صادقانه برچسب بخورد | هیچ‌جا «نمادِ دیده‌شده» با «نمادِ انتخابی» نمی‌جنگد | متوسط | **P1** |
| تب‌های قیف «تب» نمی‌کنند | `FtsFunnelStages.tsx:821-840` فقط border می‌دهد | هر UI استاندارد | affordance = عمل | کلیک تب = اسکرول به کارتِ همان مرحله | پایانِ دروغِ affordance | کم | **P0** |
| پنجره‌های بی‌state: MicroCharts/تکنیکال/درخت/بازرس/داossier | `MicroChartsDrawer.tsx:86,118`؛ `TechnicalPage.tsx:208`؛ `StrategyTreePage.tsx:506-510`؛ `SymbolInspector` بی‌error؛ `MasterPage` placeholderِ «—» حین fetch | Stripe/NN/g | empty/loading/error نام‌دار + retry | تکمیل پنج سطحِ حالت (هم‌راستا با RetryAction موجود) | کاربر هیچ‌وقت «سکوت» نمی‌بیند | کم | **P0** |
| زنجیرۀ حکم ۴-۵ بار در یک صفحه با واژگانِ مختلف | `MasterPage.tsx:458-482` + GatePipeline + FtsDetails + Dossier + Inspector gauge (حداقل ۳ واژه برای یک حکم) | Linear (one truth per level) | سلسله‌مراتب disclosure: حکم یکی، ادله زیرش | Master: خلاصۀ یک‌حکم (داossier) بالا؛ حکم‌های فرعی/ایجنتی همه زیرِ Advanced؛ واژگانِ یکسان | حذفِ سردرگمی | کم (چیدمان) | **P1** |
| جدول تابلو زیرِ fold | `MarketPage.tsx:189-221` (۴ کارت pulse + drawer + فیلتر) | TV board | جدولِ اول، نبض به نوار جمع‌شونده | Pulse را به strip تک‌خطی تاشو تبدیل کن (باز/کم حالت ذخیره شود) | تابلو همان‌جا که هست می‌ماند | متوسط | P1 |
| تکرار سنجه‌ها (سرانه، صف، breadth، exit×۳، پنج‌مظنه×۲، قیمت×۴) | بخش (g) ممیزی هر صفحه | TV/Koyfin | یک سنجه، یک خانه؛ بقیه لینک | خانه‌دارکردنِ حلقه‌ها؛ حذف تکرارِ بصری با برچسبِ مشترک | noise کمتر، اعتماد بیشتر | کم→متوسط | P1 |
| chip/تب/هدرِ پنل ≈۴۰ واریانت دستی؛ tooltip=276 title بومی | ممیزی DS: 137 chip، 30 header row، 7 tab impl | Vercel/Linear DS | primitives داخلی | `Chip/Toggle`، `PanelHeader`، `Tabs`، `Tooltip` (custom، با keyboard) در shared | گرامرِ بصری یکی | متوسط | P1 |
| ایموجی به‌عنوان آیکونِ وضعیت (➖❓🎯⏳🚫✅❌⚙️✨) | `FundamentalPage.tsx:289`, `MasterFtsDetails.tsx:13-14` و… | Things/Linear | icon semantics یکتا | گسترش Icons.tsx (SVG) برای وضعیت‌ها؛ ✓/✗ جدول‌ها طبق الگوی «مقدار+نشان» بماند | خوانایی RTL + تم | کم | P2 |
| animate-pulse سه معنا (اتصال/هشدار/لودینگ) | ممیزی انیمیشن بند ۱۰ | Slack signal separation | هر glyph یک معنا | pulse فقط لودینگ؛ زنگاریِ warning رنگ/آیکونِ جدا | alarm fatigue کمتر | کم | P2 |
| Favorites وجود ندارد («دیده‌بان» = top-60 خودکار) | `useWatchlist.ts:11-12` | Notion/TV | pinned+recent سراسری | منتخب‌ها در symbolStore (localStorage فعلاً؛ API بعد) + بالای palette/سایدبار | سوییچرِ واقعی | کم→متوسط | **P0/P1** |
| ورودی واحدِ جستجو+فرمان | نبود <GO>-مانند | Bloomberg | یک فیلد، Enter = اجرا | همان Palette v2 با prefieldِ #/> اختیاری | سرعت حرفه‌ای | متوسط | **P0** |
| Technical: verdict یک پاراگراف درِ نوار ۲۸px | `FtsDock.tsx:8-18`, `TechnicalPage.tsx:294-302` | TV deepdive | حکم باید در railِ چارت دیده شود | تبِ وضعیت را پیش‌فرضِ بازِ rail بکن نه dock (یا strip حکم بالای چارت) | Understand از همین‌جا | کم | P1 |
| Strategy Tree: دیوارِ متن grid و دوبار-دیدن در حالت both | `StrategyTreePage.tsx:523-995` | flow editors | «مسیرِ این نماد» اول، سپس قواعد | حالت پیش‌فرض = مسیرِ نماد (highlight travel)، grid با progressive disclosure | Decide در درخت | متوسط | P2 |

## E — Information Architecture پیشنهادی

ساختار پنج‌ماژوله حفظ می‌شود (حذفِ تب برای زیبایی ممنوع — و تحقیق هم حذفی
نمی‌طلبد؛ ماژول‌ها درست‌اند، **context‌بندی** غلط بود):

```text
Find     → Palette v2 / تابلو / قیف غربالگری
Understand → Symbol Context Strip (بالای هر صفحه) + SymbolInspector
Analyze  → Technical (chart-first) / Fundamental (dossier-first)
Decide   → Master Dossier (حکم→چرا→جریان→درها→جزئیات→پیشرفته)
Act      → Portfolio + TradeBlueprint (تحویل تک‌کلیکی از هر حکم)
```

مدل انتیتی: **hybridِ ماژول‌به‌نماد** — همان Grafana-variable: انتخاب نماد در هر
صفحه، در همه‌جا ساری و حکم‌دار می‌ماند؛ عمق از هر نماد ≤۲ کلیک. «Symbol
Workspace» تک‌صفحه‌ای (تبِ چارت+بنیادی+FTS زیر یک سقف) عمداً پیشنهاد **نمی‌شود**:
صفحه‌های فعلی هرکدام چیدمانِ متخصص دارند و ادغام‌شان یا card explosion می‌سازد
یا حذفِ capability؛ جای درستِ «همه‌چیزِ یک نماد» همان SymbolInspector است که
باید کامل‌تر شود (و strip بالای صفحه).

## F — Navigation پیشنهادی

- **ساختار فعلی (سایدبارِ ۶‌تایی + Topbar) می‌ماند** — Figma-lesson: جای پنل
  ناوبری را عوض نکن. سایدبار + favorites/recent اضافه می‌شود (P1).
- **Symbol Context Strip** (درس Bloomberg top-line + Spotify): تک‌خط در Topbar
  وقتی نمادی انتخاب است: نماد، آخرین، تغییر٪، بجِ حکم، و کلیدِ جابه‌جایی سریع
  (Ctrl+K، کلیدهای ↑/↓ بین منتخب‌ها؟ P2). جای Topbar فعلی (عنوانِ صفحه) حفظ.
- **Palette v2** (Ctrl+K): سه شیار — نماد (با رتبه‌بندیِ فراوانی + اخیرها)،
  صفحه/تب، فرمان‌های واقعیِ این‌جا (تغییر تم، پاک‌کردن نماد، بازِ قیف، برو به
  درخت/سبد) با hintِ راست. انتخابِ مقصدِ نماد = deep-link همان صفحه.
- breadcrumb جهانی نه؛ فقط همان مسیرِ Master که ساخته شده (§Round M).
- Back: الگوی Master (پاک‌کردن context با popstate-marker) به‌عنوان قراردادِ
  همه‌چیزِ symbol-context ثبت شود.

## G — Design System پیشنهادی (بدون کتابخانۀ خارجی)

تحقیق arch فعلی را سالم یافت (توکن واحد + تایپ‌اسکیل + .num bidi). سه کار،
همه در `shared/`:
1. `Chip` تعاملی + `Tabs` + `PanelHeader` + `Tooltip` (با فوکوس/کیبورد، چون
   title بومی روی موبایل/کیبورد معلوم نمی‌ماند) — جای ≈۴۰ واریانت دستی،
   مصرف‌تدریجی (هر کامپوننتی که دست می‌خورد).
2. بستنِ نشتی‌ها: ۱۵۷ `text-[Npx]` → توکنِ type scale؛ رنگ‌های خام Tailwind در
   درخت/پالس → توکنِ accent؛ `mr-auto`/`padding-left` فیزیکی → logical.
3. قانونِ معنا: رنگ=فقط قیمت/وضعیت؛ هر glyph یک معنا؛ انیمیشن ورود فقط برای
   page-mount (panel-in دوبلِ AppShell+tabb‌ها اصلاح شود).

## H — ساختار پیشنهادی صفحه‌به‌صفحه (prototype متنی)

- **Market**: Top: stripِ نبض تک‌خط (توضیح در popover) ← Primary: جدولِ تابلو
  (تمام‌قد) ← Secondary: drawers (دیده‌بان/میکروتیتر) ← Actions: چیپ فیلتر +
  پالت. (تابلو بالا می‌آید؛ pulse جمع‌شونده و ذخیره‌شدۀ حالت.)
- **Technical**: chart-first می‌ماند؛ rail راست = نمادِ انتخابی: وضعیتِ FTS
  (حکم+تریگر) پیش‌فرضِ باز، سپس ترازها/پنج‌مظنه/دیده‌بان در تب؛ dock پایین
  بی‌تغییر؛ نوارِ بالا همان stripِ context.
- **Fundamental**: بی‌نماد = ماتریس (همان، با تب‌های زندهٔ شاخص‌ها)؛ نماد =
  بنرِ تک‌حکم (واژگانِ یکسان با بج) → پنج کارت → drill (همان‌ها با disclosure
  لایه‌بندی‌شده، آیکونِ SVG بجای ایموجی).
- **Master**: (دossier canonical دست‌نخورده) — Advanced همه زیرِ toggle می‌ماند
  ولی واژگانِ حکم‌ها یکی می‌شود و شمارنده‌های تکراری (رای‌گیری chips vs tabs)
  یکی از منبع تغذیه می‌کند.
- **Funnel**: تب‌ها اسکرول می‌کنند (P0)؛ خطِ شمارشِ تکراری با سرآمدِ کارت ادغام
  (P2).
- **StrategyTree**: حالت پیش‌فرضِ جدید «مسیرِ نماد» (P2)؛ grid با disclosure.
- **Portfolio**: Primary = جدولِ سبد بالا؛ آیکونِ وضعیت + «نیاز به اقدام» strip
  یک‌خطی (P1)؛ donutها/دلتا زیرِ fold؛ دو شمارنده یکی.

## I — اولویت‌ها

- **P0 (همین دور):** Palette v2 (+recent/pinned ساده)، تب قیفِ واقعی، تکمیل
  پنج حالتِ گمشده، favorite/recents در symbolStore.
- **P1:** Symbol Context Strip در Topbar؛ قاعده واحد context + URL-writing؛
  Market hierarchy (pulse collapsible)؛ primitives (Chip/Tabs/PanelHeader/Tooltip)؛
  واژگانِ واحدِ حکم؛ railِ تکنیکال.
- **P2:** SVG icon pass؛ قانونِ animate-pulse؛ text-[px] migration؛ مسیرِ نماد
  در درخت؛ hover-preview کارت در اسکرینر.

## J — هرچه عمداً تغییر **نمی‌کند**

منطق FTS/ودوی هفتگی/ساعت شنی/adjustment/معنای داده · هر capability فعلی ·
انیمیشن‌های معنادار (FLIP قیف، flash ارقام، comet درخت) با گیت‌های
reduced-motion/idle/perf · چیدمان جایِ سایدبار/دراور/بازرس · متنِ عینیِ موتور
(Round L contract) · پنجرۀ MasterDossier canonical · پنج ماژول ناوبری.

## P0 اجراشده در همین نشست

- symbolStore: `recent` (۸تایی، با هر انتخاب واقعی) و `pinned` + `togglePin`؛
  دکمۀ «سنجاق» در هدرِ SymbolInspector.
- CommandPalette v2: سه شیار نماد/صفحه/فرمان؛ سنجاق‌ها و اخیرها در صدرِ حالت
  بی‌کوئری (حتی پیش از رسیدن فید)؛ مقصدِ نماد به پنج صفحه گسترده شد
  (مستر/تکنیکال/بنیادی/درخت/تابلو)؛ سه فرمانِ واقعی: تغییر پوسته، پاک کردن
  نماد، باز کردن قیف. (`ux-round79.spec.tsx` + `tools/round79_live_probe.mts` ۴/۰)
- تب قیف: کلیک = مرحلۀ فعال + اسکرولِ کارت به دید (respect reduced-motion).
- حالت‌های پنج‌گانۀ گمشده: نوار خطا+retry در MicroChartsDrawer («تایم‌لاین
  نمی‌رسد»)، سطح خطای خوراکِ کندل درِ Technical (با refetch)، «فهرستِ نمادها
  نمی‌رسد» و «وضعیتِ FTS نمی‌رسد» درِ StrategyTree، نوارِ خطای تابلو درِ
  SymbolInspector، و نوار «در حال دریافت برآیند FTS» بالای داossier حین
  fetchِ نخست.

باقی P0/P1/P2 طبق جدول بخش I دست‌نخورده برای دورهای بعد ماند.

## منابع (گزیده)

Linear Quiet UI · Raycast docs · Notion Quick Find · Obsidian Workspaces ·
VS Code command palette · Figma UI refresh + backlash (forum) · Stripe empty
states · NN/g data tables + empty states · TradingView layouts/watchlists docs ·
Bloomberg getting-started + UXMag teardown · LSEG quick-start · Koyfin ·
Finviz reviews · TIKR · Grafana variables/annotations · Trade Ideas compare ·
Apple Liquid Glass guidance. (جزئیات در گزارش‌های نشست؛ مواردی که فقط از وبلاژ
ثانویه بود در گزارش چت «راستی‌آزمایی‌نشده» علامت خورده است.)
