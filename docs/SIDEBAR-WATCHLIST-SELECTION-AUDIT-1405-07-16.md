# ممیزیِ انتخابِ نماد، واچ‌لیست، سایدبار و مجمع — ۱۴۰۵-۰۷-۱۶

Commit 1 از taskِ «Symbol Selection, Real Watchlist, Two-Page Sidebar, Quick Scan, Live
Assembly Status». این فایل **فقط** وضعِ موجود را با شاهدِ `file:line` ثبت می‌کند و
قصدِ کدِ جدید ندارد. ریشهٔ کار: worktree ‏`BorsTerminal-roadmap` ‏(شاخۀ `funnel-api-wip`)؛
هر ارجاعِ اندروید با برچسبِ `[android]` به worktree ‏`BorsTerminal-android` است.

---

## ۱) سه کشفی که نقشۀ کار را عوض می‌کند

**کشف ۱ — «واچ‌لیست واقعیِ کاربر» از قبل درِ بک‌اند هست، با CRUD، با کشِ ماندگار، و با
رجیسترِ بیلد — و رابطِ کاربری هیچ‌جا صداش نمی‌کند.**

- DDL: ‏`watchlist_store.py:31-39` →
  `user_watchlists(symbol_norm TEXT PRIMARY KEY, symbol, name, note, added_at)` + ایندکس `:45`
- فایلِ دیتابیس: ‏`USER_DB_PATH = WORK_DIR/user.db` در `bors_config.py:634`؛ بازکردن
  `api/_core.py:145 get_user_db()`؛ درِ وایت‌لیستِ جدول‌هایِ کاربر `bors_config.py:130`
- مسیرها: `GET /api/watchlist` (`api/watchlist.py:18`)، `POST` (`:33`)،
  `DELETE /api/watchlist/{symbol}` (`:70`)، `GET /api/watchlist/matrix?symbols=` (`:85`)
- سقف‌ها: `MAX_WATCHLIST=60` (`watchlist_store.py:27`)، `MAX_NOTE=200`، `MAX_NAME=120`؛
  clampِ نرم/سخت `api/watchlist.py:51-52`
- بیلد: ثبت‌شده در `api/__init__.py:12,16` و در `fts_terminal.spec:87` (`api.watchlist`) و
  `:90` (`watchlist_store`) و datas `:31`
- مصرف‌کنندۀ فرانت: **صفر**. جست‌وجوی `api/watchlist` در `roadmap/frontend/src` هیچ
  نتیجه‌ای ندارد. تنها مصرف‌کنندگانِ موجود در `archive/legacy_static/selection.js` و
  `mstat.js`‌اند (کدِ بازنویشی‌شدۀ قدیمی).

⇒ تصمیمِ این milestone: **ساختِ storageِ نو ممنوع.** رابط به همان `user_watchlists` وصل
می‌شود. هر طرحِ دیگری (localStorage، جدولِ تازه، فایلِ JSON) دومینِ منبعِ حقیقت می‌سازد
و با رأی‌هایِ قبلیِ مالک درِ «یک داور، یک منبعِ عدد» در تضاد است.

**کشف ۲ — نامِ `watchlist_max` یک کلیدِ پیکربندی است که دو معنایِ بی‌ربط را حمل می‌کند.**

| مصرف | محل |
| --- | --- |
| سقفِ واچ‌لیستِ کاربر | `api/watchlist.py:51`، `bors_config.py:669` |
| سقفِ غنی‌سازیِ اسکرینر/FTS (کارایی) | `api/screener.py:443-444,452,513`، `fts_engine.py:1933,2005`، `api/market.py:1248`، `funnel_engine.py:172`، `dev/funnel_engine_v1.py:298` |
| «دیده‌بان»ِ صرفاً نمایشیِ فرانت | `features/technical/api/useWatchlist.ts:12,39` (`slice(0, 60)`) |
| پرچمِ بولینِ ردیفِ اسکرینر | `useFtsScreen.ts:61` از `api/screener.py:443` |

⇒ بند ۴۱ِ task دقیقاً همین را می‌خواهد: تفکیکِ نام. پیشنهادِ نهایی درِ §۵ِ این فایل.

**کشف ۳ — ادعایِ «کدِ اندروید درِ هیچ worktreeای نیست» نادرست بود.** یک ممیزِ اولْ این را
گفت؛ من دوباره وارسی کردم و غلط بود: کدِ اندروید درِ `[android]` **واقعاً وجود دارد**
(`scripts/build_mobile_snapshot.py` خط ۲۸۰، `frontend/src/shared/api/local/` با ۸ فایل،
`MobileBootstrap.tsx`، `capacitor.config.ts` +-project Gradle، `@capacitor/* ^8.5.2` در
`[android] frontend/package.json:16-19`، `workflows/mobile.yml`, `mobile.css`, هفت پروندۀ
تستِ موبایل). درِ `roadmap` هم واقعاً نیست. ⇒ بند ۳۵ِ task (اندروید) درِ `[android]`
انجام می‌شود، نه درِ این worktree.

---

## ۲) وضعِ «انتخابِ نماد» امروز

- تک‌نمادی، سراسری: `shared/stores/symbolStore.ts:39-47` (`symbol`, `recent[]`,
  `pinned[]`, `setSymbol/clearSymbol/togglePin`). هیچ `Set`ِ چندتایی‌ای درِ کلِ فرانت نیست.
- کلیکِ سطر = انتخاب: `TapeTable.tsx:294` → `MarketPage.tsx:78-79,213`؛
  `FtsScreenTable.tsx:302` → `FundamentalPage.tsx:45-46`.
- **هویت = رشتهٔ نمایشیِ فارسی.** `ins_code` فقط درِ `marketRow.ts:23` وجود دارد و مصرفش
  محدود است به: ایندکسِ دلتای فید (`shared/api/marketFeed.ts:59,79`) و watchِ حالتِ داغِ
  دفترِ اردر (`features/technical/api/useOrderBook.ts:51`).
- `FtsScreenRow` (‏`useFtsScreen.ts:9-88`) هیچ `ins_code` **ندارد** — فقط `symbol` و
  `symbol_norm` (`:11`). ⇒ هر انتخاب/واچ‌لیستِ هویت‌محوری درِ بنیادی یا باید `ins_code`
  را از بک‌اند بگیرد یا `symbol_norm` را canonical بشمارد؛ این یک شکافِ واقعی است.
- خطرِ شناخته‌شدۀ رشته‌ای: املایِ `ك/ي` و ZWNJ. پنج واریانتِ نرمال‌سازی درِ repo هست:
  `fts_engine.norm_fa:46` + `sym_in:142`، `funnel_tech_scan.norm_symbol:153`،
  `maketrans`هایِ درون‌خطی (`api/screener.py:173,460`، `api/chart.py:529,868,930`)،
  `codal_fetcher._NORM:322`، `dev/calendar_fetcher.py:152`، و فرانت:
  `shared/lib/normalizeFa.ts:18,34`، `features/market/lib/tapeFts.ts:94`.
  `watchlist_store.py:12-16` خودِ docsش می‌گوید ردیفِ تکراریِ هم‌نام از همین آمده.
  ⇒ **ششمینِ واریانت نمی‌سازیم**: canonical = `symbol_norm`ِ خودِ `watchlist_store`
  (چون کلیدِ همان جدول است) + `ins_code` هر جا درِ دسترس باشد.

---

## ۳) سایدبارِ چپِ امروز — inventoryِ کامل (بند ۳۱: هیچ فیلدی بی‌صدا جابه‌جا/حذف نشود)

`widgets/SymbolInspector.tsx`، دیتا بیشتر از `widgets/useInspectorBoard.ts` که **همان
کوئریِ مشترکِ `['market-feed']` را می‌خواند و درخواستِ تازه‌ای نمی‌زند** — این برایِ بند ۱۶
(سوییچِ بی‌fetch) خدمتِ ما است.

| # | بلوک | خط | سرچشمه | طبقه‌بندیِ پیشنهادی |
| --- | --- | --- | --- | --- |
| ۱ | سرخط: نماد/نام/صنف + pin + بستن | ۲۸۷-۳۱۷ | store | Primary |
| ۲ | بنرِ خطایِ فید | ۳۲۲-۳۳۰ | feed | Primary (وقتی فعال است) |
| ۳ | ناوبریِ گام‌هایِ قیف FTS | ۳۳۴-۳۸۹ | `useFtsFunnel('custom')` (خط ۱۹۵) | Primary |
| ۴ | قیمت + تغییرِ روز | ۳۹۲-۴۱۱ | feedِ مشترک | Primary |
| ۵ | وضعیتِ نظارتی/توقف | ۴۱۵ (`RegulatoryState`) | ردیفِ خام | Primary |
| ۶ | گیج + بجِ «کاکپیت مستر» | ۴۲۱-۴۳۹ | `runStrictGates` درِ `signalStore` (بی‌درخواست) | Primary |
| ۷ | چهار چراغ: نمرۀ بنیادی / تکنیکال FTS / سرانۀ خریدار / پرتفوی | ۴۴۱-۴۶۷ | feed + screen کشیده | Primary |
| ۸ | **پنج مظنه (دفترِ اردر)** | ۴۶۹-۴۷۳ | `/api/order-book/{symbol}` | **Detail (page ۲)، تاشو — حذف نه** |
| ۹ | جریانِ حجمِ intraday | ۴۷۶ | کارتِ مستقل | Detail |
| ۱۰ | بجِ ممیزیِ FTS | ۴۷۹-۴۹۲ | feed | Secondary |
| ۱۱ | شبکهٔ اقدام: افزودن به سبد + لینک‌هایِ /master، /technical، /fundamental | ۴۹۴-۵۲۰ | store | Primary |

نکته‌هایِ معماریی که درِ طراحیِ دوصفحه‌ای اثر می‌گذارند:
- بلوک ۸ تنها بخشی است که **کوئریِ خودش** را دارد؛ `useOrderBook.ts:54-64` نماد‌محور و
  نشست‌آگاه poll می‌کند. ⇒ تاشدنش باید `enabled` را هم خاموش کند تا بی‌دلیل poll نکند،
  ولی داده از دست نمی‌رود (کوئری درِ کش می‌ماند).
- `SymbolInspector` از `widgets` چیزی درِ `@features/market/*` وارد می‌کند (خطوط ۲۵-۲۸)
  در حالی که `frontend/eslint.config.js:41` آن را برایِ `widgets` اجازه نمی‌دهد. ⇒ قبل از
  افزودنِ importِ marketِ بیشتر باید این تکلیف روشن شود (احتمالاً یک استثنا درِ config یا
  بالا بردنِ آن helper به `shared`). **این بدهیِ موجود است، نه محصولِ این milestone.**
- هیچ کامپوننتِ مشترکِ «سلولِ نماد» وجود ندارد؛ `TapeTable.tsx:307-310` و
  `FtsScreenTable.tsx:324-335` هر دو دست‌نویس‌اند. ⇒ بند ۲۱ («رفتارِ انتخاب درِ Market و
  Fundamental یکسان است») نیازِ یکِ کامپوننتِ مشترک درِ `shared` دارد.

---

## ۴) مجمع — شواهدِ زنده (بند ۲۶ تا ۳۰)

پروبِ واقعی درِ ۲۱:۵۰ به بعد، با ۱۴۲ فراخوانِ ثبت‌شده در
`_audit/tsetmc_assembly_probe_evidence.json` (URL + status + bytes + sha256 + نمونه).
**هیچ endpointی حدس زده نشده؛ هر چه پایین می‌آید یا ۲۰۰ گرفته یا صریح شکست است.**

| مفهومِ خواستۀ مالک | حکم | شاهد |
| --- | --- | --- |
| `Instrument/IsInstrument?insCode=` | **۴۰۴، صفر بایت** رویِ هر ۸ نماد (هر دو شکلِ پارامتر) | evidence |
| کلیدهایِ تاریخیِ `maxam`/`lMaxam`/`devidDate`/`divCash`/`navmIC`/`statTakeh`/`memo` | **در هیچ پاسخِ ۲۰۰ی نیستند** (جست‌وجوی کلیدِ تخت) | evidence |
| `ClosingPrice/GetMarketWatch` | ۲۰۰، ۳۹۲۴ ردیف، ۴۴ کلید/ردیف — **صفر کلیدِ مجمع** | evidence |
| آگهیِ مجمع / تصمیمِ مجمع / نوعِ مجمع | **هست، اما فقط به‌صورتِ متنِ عنوانِ اطلاعیه** از `Codal/GetPreparedDataByInsCode/{n}/{insCode}` (۲۰۰، ۳۰–۶۰KB، ۱۱۱–۲۸۶ms) — نمونه: «آگهیِ ثبت تصمیماتِ مجمعِ عادیِ سالیانه» ذوب ۲۰۲۶-۰۹-۱۵. هیچ فیلدِ ساختارمندِ eventType/eventDate ندارد | evidence |
| وضعیتِ مجمع (توقف/بازگشایی) | **قابلِ استخراج**: `Msg/GetMsgByInsCode/{insCode}` (۲۰۰) متنِ «بازگشايي نماد … پس از برگزاری مجمع» + `MarketData/GetInstrumentState/{insCode}/{dEven}` با `cEtaval` ساختارمند (شتران = «IS» در ۲۰۲۶۱۰۰۷)، `underSupervision` | evidence |
| تاریخِ تصمیم | **نیست**؛ تنها proxy: `publishDateTime`ِ اطلاعیۀ «ثبت تصمیماتِ…» ⇒ باید برچسب‌دارِ proxy بماند | evidence |
| DPS | **نه از TSETMC نه از این پاسخ‌ها** (در `GetInstrumentInfo` فقط `eps`/`estimatedEPS`). عددِ DPS داخلِ PPT/HTMLِ ضمیمه است | evidence + absent |
| افزایشِ سرمایه | **ساختارمند و هست**: `Instrument/GetInstrumentShareChange/{insCode}` → `{dEven, numberOfShareOld, numberOfShareNew}` (فولاد ۱۲ ردیف، وساپا ۷) | evidence |
| تغییراتِ هیئت‌مدیره | فقط متنِ عنوان («معرفی/تغییر در ترکیبِ اعضایِ هیئت‌مدیره/مدیر عامل»، وبملت ۲۰۲۶-۰۹-۱۶)؛ دادهٔ ساختارمند: **نیست** | evidence |
| تازگی | preparedData زیرِ روز؛ `finalLastDate=20261007` درِ مسیرهایِ قیمت = پایانِ نشست؛ `dEven` درِ این API میلادیِ yyyyMMdd است (اثبات شد) | evidence |

**مدل‌هایِ شکستِ ثبت‌شده (این‌ها endpoint نیستند — تلاش‌اند):**
`Instrument/InstrumentInfo`، `InstrumentInfoFull`، `StaticData/GetInstrumentList`،
`Codal/GetStatementContentByInsCode`، `ClosingPrice/GetInstrumentCalendar` (شکلِ کوئری) →
۴۰۴/صفر بایت. `Dashboard/GetInstrumentInfo`، `Dashboard/GetDividendDatesByInsCode`,
`…BySymbol`, `News/GetNewsByInstrument`, `Karbasta/GetByInstrument`, `Meeting/GetMeetings`,
`Council/GetDecisions`, `Announcement/GetByInstrument` → **۲۰۰ با ۸۲۴ بایت HTMLِ همان
SPA** (یعنی fallback، نه داده) ⇒ **استفاده‌شدنی نیستند.**
`Fund/GetETFByInsCode/ثروت` → HTTP ۵۰۰. خطایِ TLS/DNS: هیچ.

**نرخِ درخواست:** ۱۰ فراخوانِ پشت‌سرهمِ بی‌توقف: `GetMarketWatch` ده‌بار ۲۰۰
(۵۳۸–۹۶۳ms، ۴٫۰MB هر بار)؛ `GetPreparedDataByInsCode` ده‌بار ۲۰۰ (۱۱۱–۲۸۶ms، ۳۰KB).
**هیچ ۴۰۳ و هیچ ۴۲۹ در هیچ شمارۀ فراخوانی.** ⇒ بازهٔ امن: نماد‌محور ≥ ۳۰ ثانیه،
کلِ تابلو ≥ ۶۰–۱۲۰ ثانیه، جارویِ سراسری چنددقیقه‌ای.

**سمتِ Codalِ ذخیره‌شده (read-only sqlite):** `codal.db` درِ ریشۀ worktree **نیست**
(فقط `_audit/codal_snapshot.db`). درِ `market.db → codal_notices` (۳۶٬۳۵۰ ردیف):
«مجمع» درِ عنوان = ۳۰۱ (۰٫۸٪)، «دعوت» = ۱۰۰، «مصوبات» = ۱، «بازگشایی» = ۱. هر ۳۰۱
تاریخِ انتشارِ `۱۴۰۵/۰۶/۰۱` دارند (یک دستهٔ یک‌روزه) و برایِ **هیچ‌کدام از ۸ نمادِ آزمونِ
من** ردیفِ مجمع‌دار نیست (تنها «ذوب»ِ جورآمده صندوقِ «ذوب سهام» است). تازه‌ترین
`publish_date`ِ کلی: ۱۴۰۵/۰۶/۱۳ (≈ ۴ روز کهنه).

⇒ **نتیجهٔ مهم:** feedِ Codalِ ذخیره‌شدۀ امروز **نمی‌تواند** برچسبِ مجمع را بدهد؛
دلیلش درِ کد هم هست: `codal_fetcher.py:77-79` با `SAVE_USEFUL_ONLY=True` و دروازه‌هایِ
`_positive_title` (`:1534`, `:1101,2514,2845,3332,3552`) عنوان‌هایِ «مجمع» را دور می‌ریزد،
و `dev/codal_fts_updater.py:22-27` پیشِ شبکه ردشان می‌کند. کامنتِ `codal_fetcher.py:3588-3590`
می‌گوید ذخیره می‌شوند — **کامنت با رفتارِ واقعی در تضاد است** و باید درِ همین milestone
اصلاح یا برداشته شود (نه با تغییرِ رفتارِ silent).
همان داده اما **سریع و زنده** از mirrorِ TSETMC CDN درِ دسترس است.

**مقایسه با مسیرهایِ موجودِ repo:** امروز تنها منبعِ «تقویمِ مجمع»
`static/calendar/cache.json` است که **بیرونِ اپ** با `dev/calendar_fetcher.py` (Codal search
v2، `Category=6`) هر ~۶ ساعت ساخته می‌شود؛ `app.py:6` فقط `/static` را mount می‌کند و هیچ
triggerِ درون‌اپی ندارد. خوانندگانِ آن: `api/chart.py:826-843` (`_cal_classify`)، `:866`،
`:894-905` (`_ASSEMBLY_FAMILY`, `ASSEMBLY_NEAR_DAYS=14`)، `:918`، `:966`، `:983`، endpointها
`:995` و `:1015`؛ از آن سو `api/screener.py:164-201` (`_apply_assembly_veto`، بیرونِ کشِ
`_SCREENER_CACHE_TTL=43200` → `:29`) و `funnel_engine.py:334-358,421-422,681-682`.
**طبقه‌بندی + افقِ ۱۴روزه + واژگانِ بجِ مجمع سه بار نوشته شده**: `api/chart.py:826/905/918`،
`features/fundamental/lib/assemblyEvent.ts` (regexها و روزهایِ خودش)،
`widgets/useSymbolVeto.ts` (توجه: مسیرِ درستِ این فایل `widgets/` است،
`features/master/api/` نیست). گاردهایِ موجود: `dev/assembly_veto_v1064.py` (۶ قاعده) و
`dev/test_calendar_v92.py` §۴ (برابریِ py≡ts).

⇒ بند ۲۹ («منطقِ مجمع را دوتایی نکن») از همین‌جا یک تکلیفِ روشن می‌گیرد: **یک**
`AssemblyEvent` درِ لایۀ canonical، با **یک** افقِ روز، با **یک** واژگانِ برچسب؛ TSETMC
mirror برایِ «سریع»، cache/Codal برایِ audit.

**اندروید:** `[android] scripts/build_mobile_snapshot.py:51-54` فقط
`RAW_TABLES = ("instruments","price_history")` را خام می‌پزد و
`:61-89` این کلیدها را bake می‌کند: screener، fts، fts_config، market، sectors،
mstat/…، index/tedpix، **`calendar/upcoming/{7,14,30,60,90}` و `calendar/{symbol}`**
(`:171-177`). `codal_notices` درِ هیچ snapshotی نیست. ⇒ برچسبِ مجمعِ آفلاین **از همان
پیکجِ bake شده قابلِ ساخت است** و لازم نیست مسیرِ شبکهٔ تازه‌ای باز شود؛ ولی اگر TSETMC
mirror منبعِ تازه شود، باید کلیدِ bake‌شدۀ خودش را درِ همان `baked` جدول بگیرد.

---

## ۵) تصمیم‌هایِ طراحی (به‌جای سؤال‌هایِ لوله‌کشی)

1. **نام‌ها (§۴۱):** `user_watchlist` (همان `user_watchlists`) /
   `market_enrichment_limit` (سقفِ غنی‌سازیِ اسکرینر) / `display_top_n` (برش‌هایِ نمایشیِ
   فرانت). `watchlist_max` فقط برایِ معنایِ اول می‌ماند و معنایِ دوم با aliasِ جدید و
   fallbackِ خواندنِ کلیدِ قدیمی جایگزین می‌شود (تا پیکربندیِ کاربرانِ موجود نشکند).
2. **هویت:** کلیدِ canonical = `symbol_norm` (همان منطقِ `watchlist_store.py:12-16`) و
   `ins_code` درِ هر جا که هست ثبت می‌شود؛ برایِ بنیادی که `ins_code` ندارد،
   `ins_code` باید از بک‌اند درِ همان `/api/screener` اضافه شود (یک ستونِ transport، نه
   داوری) — تا انتخاب درِ دو جدولِ Market و Fundamental یکِ هویت داشته باشد (§۲۲، §۲۳).
3. **انتخاب:** storeِ مشترک درِ `src/shared/stores/selectedSymbolsStore.ts`
   (`Set<symbol_norm>` + `ins_code` + `added_at`)؛ چون ESLint برایِ `features/*` فقط
   `shared` و `contracts` را می‌پذیرد (`eslint.config.js:40`)، همان‌جا تنها جایِ درست است.
4. **واچ‌لیست UI:** به `GET/POST/DELETE /api/watchlist` وصل می‌شود، optimistic، و
   markerِ `★` درِ یکِ کامپوننتِ مشترکِ سلولِ نماد که Market/Fundamental/Funnel هر سه
   استفاده‌اش می‌کنند (نه چهارِ کپی).
5. **سایدبار:** دو page با toggleِ محلی و stateِ حفظ‌شده؛ داده دوباره fetch نمی‌شود
   چون همه از کوئریِ مشترک `['market-feed']` می‌آیند (§۱۵، §۱۶). پنج مظنه به page ۲ و
   تاشو، با `enabled`ِ کوئری که موقعِ بسته بودن خاموش می‌شود.
6. **Quick Scan:** هدفمندِ تک‌نمادی، از همان `funnel_engine`ِ canonical (بدونِ جارویِ
   کلِ جامعه) — §۱۸؛ این milestone هیچ scanِ سراسری را عوض نمی‌کند.

---

## ۶) قمریِ کامیت‌ها (با گاردی که هر کامیت را ثابت می‌کند)

| کامیت | کار | گارد/شاهد |
| --- | --- | --- |
| ۱ (این) | ممیزی | این فایل + `_audit/tsetmc_assembly_*` |
| ۲ | `selectedSymbolsStore` + سلولِ مشترکِ نماد + checkbox درِ Market و Fundamental | تستِ جدید + `npx tsc -b` + `vitest` |
| ۳ | وصلِ UI به `user_watchlists` (add/remove/refresh/sort)، persistenceِ موجود | تستِ persistence + `dev/run_all_tests.py` |
| ۴ | markerِ `★` درِ Market/Fundamental/Funnel/Quick-Scan/search | تستِ رندر + walkِ زنده |
| ۵ | Sidebar page ۱ (یک نگاه) | inventoryِ §۳ به‌عنوان checklistِ «هیچ فیلدی گم نشود» + screenshot |
| ۶ | Sidebar page ۲ + پنج مظنۀ تاشو | تستِ collapse + `useOrderBook` enabled-gating |
| ۷ | Quick Scanِ انتخاب‌شده‌ها (چند نماد با concurrencyِ محدود) | تستِ targeted (اثباتِ «جارویِ سراسری اجرا نمی‌شود» با شمارشِ درخواست) |
| ۸ | `AssemblyEvent`ِ canonical + منبعِ TSETMC mirror + Codal audit | گاردِ جدیدِ `dev/assembly_source_v1.py` (mappingِ ثابت + null-honesty) و گسترشِ `dev/assembly_veto_v1064.py` |
| ۹ | برچسبِ زندهٔ مجمع درِ Market/sidebar | walkِ زنده + evidence JSON |
| ۱۰ | `[android]`: checkbox، star، واچ‌لیست، page ۱/۲ درِ drawer، portrait/landscape | `workflows/mobile.yml` + `tools/mobile_boot_probe.mts` |
| ۱۱ | cross-platform + performance + responsive matrix (§۳۹) | `_audit/` + جدولِ پذیرش |

**Invariantsِ شکست‌پذیر که این milestone لمس می‌کند:** `fetch` بیرونِ
`shared/api/http.ts`/`features/*/api/` ممنوع؛ ترتیبِ `api_router()` پیشِ catch-all؛
هر `api/*.py`ِ نو درِ `hiddenimports`؛ `numpy==2.0.2`; `market.db.lzma` کنارِ EXE؛
دو آپدیت‌کنندۀ جدا؛ گاردهایِ `dev/`؛ استثنایِ `!app.py.bak` درِ `.gitignore`.
**Lockstep:** اگر کامیت ۲–۸ فایلی درِ `api/` افزود، `fts_terminal.spec:87-90`؛ اگر
featureِ جدید ساخت، `eslint.config.js:22-31`؛ اگر رفتارِ مجمع عوض شد،
`dev/assembly_veto_v1064.py` و `dev/test_calendar_v92.py` §۴.
**Rollback:** هر کامیت کوچک و مستقل؛ بازگشت با revertِ همان کامیت (نه `git checkout --`؛
درِ این repo سابقاً fixِ واقعی را هم نابود کرده است).

---

## ۷) سؤال‌هایی که رأیِ مالک می‌خواهد (فوریاتی آخرِ کار)

- **Q-A (DPS):** عددِ DPS درِ هیچ‌کدام از پاسخ‌هایِ TSETMC نیست و فقط داخلِ PDF/HTMLِ
  ضمیمه است. می‌خواهید (۱) DPS را «بدون داده» بگذاریم و بی‌صدا نسازیم، (۲) ضمیمه‌ها را
  واکشی/تجزیه کنیم (کارِ تازه، وابسته به Codal)، یا (۳) از `codal.db`ِ موجود بخوانیم
  هر جا عددِ DPS ثبت شده؟
- **Q-B (تاریخِ تصمیم):** تنها شاهدِ موجود، `publishDateTime`ِ اطلاعیهٔ «ثبت تصمیمات» است
  (proxy). برچسبش را صریح «تاریخِ انتشارِ اطلاعیه» بنویسیم یا ستونِ «تاریخِ تصمیم» را
  خالی بگذاریم؟
- **Q-C (واژگانِ عنوان):** «تصمیم مجمع» را از regexِ عنوانِ اطلاعیه می‌سازیم. اگر عنوان
  فیلترِ جدیدِ من را رد کند، بهتر است خالی بماند یا با برچسبِ «عنوانِ اطلاعیه»؟
- **Q-D (کامنتِ دروغین):** `codal_fetcher.py:3588-3590` می‌گوید اطلاعیه‌هایِ مجمع ذخیره
  می‌شوند در حالی که whitelist ردشان می‌کند. کامنت را بردارم، یا رفتار را عوض کنم که
  ذخیره شوند (تأثیرِ اندازه/تازگی رویِ `codal.db.lzma` و آپدیتِ دیتابیس دارد)؟
- **Q-E (سقفِ کاربر):** `MAX_WATCHLIST=60` بماند یا با تعریفِ «رصدِ روزهایِ بعد» به
  مثلاً ۱۰۰ برسد؟ (عددِ ۶۰ درِ `api/watchlist.py:51-52` سخت clamp می‌کند.)

هیچ موردی درِ این سند «راستی‌آزمایی‌شده» خوانده نشده مگر شاهدِ `file:line` یا
statusِ ثبت‌شده درِ `_audit/tsetmc_assembly_probe_evidence.json` داشته باشد.
