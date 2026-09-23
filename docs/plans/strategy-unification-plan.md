# طرح یکپارچه‌سازی استراتژی‌های پخش‌شده (فقط طرح — بدون تغییر کد)

> وضع فعلی: منطق «استراتژی/داوری FTS» بین چند موتور، چند استور و چند سطح UI پخش شده است.
> این سند نقشهٔ زمین، ریشهٔ تکرار، و یک مسیر فازیِ کم‌ریسک برای یکپارچه‌سازی می‌دهد.
> هیچ کدی در این مرحله تغییر نمی‌کند؛ تصمیم با شماست.

## ۰) چرا این کار لازم است (شواهد)

همین حالا برای «آیا بخریم؟» **سه** داوری موازی وجود دارد که هر سه در `MasterPage` هم‌زمان اجرا می‌شوند:

| موتور | فایل | مدل | مصرف‌کننده |
|---|---|---|---|
|Weighted + 3-gate | `features/master/lib/masterMath.ts` | میانگین وزنی + `runGatingPipeline` (3-گیت F/T/S) + `applyGateToAction` | MasterPage |
| 4-gate veto | `features/master/lib/strictGates.ts` | ماشین وتوی 4-گیت + `definiteDecision` + `isSuperFundamental` | MasterPage، StrategyTreePage، FtsPipelineBar |
| 4-step narrative | `features/master/lib/ftsPipelineEvaluator.ts` | خط لولهٔ روایتی S→T→F→M | MasterPage، StrategyTreePage، FtsPipelineBar |

سه تفسیر از «گیت‌ها» (سه‌گانه vs چهارگانه vs چهارگامی) = سه منبع حقیقت که می‌توانند با هم ناهم‌خوان شوند. باگِ ترازِ نمرهٔ بنیادی (که رفع شد) دقیقاً محصول همین پراکندگی بود: هر سه موتور «نمره بنیادی» را به شکل خود فرض می‌کردند.

## ۱) آمار تکرار (دِبتِ ساختاری)

- **لیست ستاپ‌ها** (`jet`/`fib`/`pullback`/`choch`/`double_bottom`/`point_hunt`) در ۵+ نقطه: `features/technical/signals/technicalSignals.ts`، `strictGates.ts`، `ftsPipelineEvaluator.ts`، `StrategyTreePage.tsx` (سه‌جای مختلف: type، `activeNodes`، `handleToggleCustomNode`)، `features/market/.../FtsScreenTable.tsx`.
- **«آیا ستاپ ورود مستقیم هست؟»** سه بار پیاده شده: `masterMath.hasEntrySetup`، `strictGates.hasDirectEntrySetup`، و منطق تکراری داخل `ftsPipelineEvaluator` (step2).
- **آستانهٔ عددیِ پخش‌شده:** `strictGates.WAR_EQUITY_CAP_MIN_PCT=10 / MAX=20` در برابر `strategyParamsStore.warConditionCapPct=15` (و `maxTotalPortfolioCapPct=70`). سه عدد، دو منبع، بدون هم‌خوانی.
- **`isSuperFundamental`** تا دیروز دو معنا داشت: «composite ≥ ۸۰» (strictGates) و «score === ۵» (سرصفحهٔ pipeline). هماکنون روی «۵ از ۵ و صعودی» یکسان شد؛ الگوی درست برای بقیه.
- **`features/technical/lib/ftsOverlays.ts`** یک همتای تقریباً تکراری دارد (تطبیق جزوهٔ چارت/نمودار) — داکیومنت‌شده در `DEAD_CODE_AUDIT.md`.

## ۲) استورها و پریست‌ها (چهار سامانهٔ جدا)

| پرنام | فایل | نگه می‌دارد | مصرف‌کننده |
|---|---|---|---|
| `strategyStore` | `shared/stores/strategyStore.ts` | افق سراسری (`horizon`) | FtsPipelineBar، MasterPage |
| `strategyParamsStore` | `features/master/stores/strategyParamsStore.ts` | **پارامترهای عددی FTS (منبع حقیقت، وفادار به جزوه)** | همهٔ موتورها (باید بشود) |
| `PresetMode` محلی | `StrategyTreePage.tsx` useState | swing/trend/hourglass/custom + custom* | فقط درخت |
| پریست غربال | `FtsScreenTable.tsx` | مجموعهٔ چهارمِ پیش‌فیلتر | جدول بنیادی |

و یک سطح پنجم: **«مشاورهٔ تحلیلی» تب مستقل نیست** — همان ویجت سراسری `widgets/FtsPipelineBar.tsx` + `widgets/FtsAnalystModal.tsx` است. یعنی «داوری» هم‌زمان در ۴ سطح دیده می‌شود: تب ایجنت ارشد، تب درخت، نوار سراسری، و جدول غربال.

## ۳) مقصد مطلوب (یک مدل، یک واژگان، چند نما)

1. **تک‌مدل داوری:** یک تابعِ خالصِ مرجع `evaluateStrategy(symbol, signals, params) -> StrategyVerdict` که *یک‌بار* گیت‌ها را حساب کند و خروجی واحد بدهد: `{ gates: Gate[], action: FinalAction, persona, score, veto?, evidence }`. موتurreهای فعلی به **نمای خوانا** روی همین خروجی تقلیل یابند:
   - `masterMath` → لایهٔ وزنی/برآیند روی `StrategyVerdict`
   - `strictGates` → لایهٔ «ماشین وتو» روی `StrategyVerdict`
   - `ftsPipelineEvaluator` → لایهٔ **روایت/متن** روی `StrategyVerdict` (بدون محاسبهٔ مجدد گیت)
2. **تک‌واژگان (enums در `contracts`):** `SETUPS`، `GateId`، `Persona` ('swing'|'trend'|'hourglass'|'custom')، `FundTier` ('super'|'good'|'medium'|'weak')، `ftsScoreOf` (که اضافه شد). همهٔ فایل‌ها import کنند؛ حذفِ ۵ لیست تکراری.
3. **تک‌منبع پارامتر:** تمام ثابت‌های عددی (از جمله سقف جنگ، باند نمرهٔ بنیادی ۳/۴/۵، سطوح فیبو) از `strategyParamsStore.FTS_DEFAULT_PARAMS` خوانده شوند؛ اتمجیک در موتورها ممنوع. تعارض ۱۰/۱۵/۲۰ این‌جا حل می‌شود.
4. **تک‌پریست:** `persona` به `strategyStore` منتقل و **یک انتخابگر** شود که MasterPage، StrategyTreePage، FtsPipelineBar و FtsScreenTable همه از آن بخوانند/بنویسند (به‌جای چهار useState).
5. **نقش هر نما (IA روشن):**
   - تب‌های داده (Fundamental/Technical/Market) = جزئیات و ادله.
   - **MasterPage = موتور تصمیم** (تک‌مدل، کامل‌ترین).
   - **StrategyTreePage = نقشهٔ آموزشی/مسیر** + بَج وضعیتِ زنده (همین حالا اضافه شد).
   - **FtsPipelineBar = چکیدهٔ یک‌نگاه** (از همان تک‌مدل).
   هدف: یک حقیقت، سه بریدگی با عمق متفاوت — نه سه حقیقت.

## ۴) وتوی روند هفتگی — وضعیتِ فعلی (بازبینی ۱۴۰۵-۰۷-۰۱)

این بند قدیمی بود. داورِ روند هفتگی از قبل در بک‌اند هست و منتشر می‌شود:
`api/chart.py` ساختار پیوتِ هفتگی را به `up/down/range/na` می‌برد و
`trend.matrix.decision` را PERMITTED / REJECT / UNKNOWN می‌سازد؛ همان ستون‌ها
در خروجیِ اسکرینر (`tech_trend_w`، `tech_matrix_decision`) و `/api/fts/{symbol}`
می‌آیند. پس «اندپوینتِ هفتگی» ساخته نشدنی نبود، **اجرا نشدنِ رأی** بود:

- جدول بنیادی و بج‌ها وتو را *نمایش* می‌دادند ولی واچ‌لیستِ اسکرینر جای
  سهمِ نزولی/خنثی را نگه می‌داشت. این حالا در `api/screener.py` بسته شده:
  `decision == "REJECT"` ⇒ `watchlist = False` + `weekly_veto = True` + دلیل در
  `exclusion_reasons`. قفلش: `dev/weekly_veto_guard.py`.
- `na` (کمتر از دو پیوت کاملِ هفتگی) وتو **نیست**؛ قبلاً با «خنثی» یک‌جا REJECT
  می‌شد. بی‌داده ≠ قرمز.
- frontend دیگر نباید وتوی دوم بسازد. `EliteFunnelHub` با `=== 'buy'` مقدارِ
  هرگز-تولیدنشده را می‌سنجید (مرحلهٔ ۱۰نفره هیچ‌وقت از این راه رد نمی‌شد)؛
  به `PERMITTED`/`REJECT` واقعی وصل شد.
- سیاست «حذف‌نشدنِ هیچ سهمی از دید کاربر» در *ماتریسِ تاییدِ سه‌گانهٔ داشبورد*
  دست‌نخورده می‌ماند (dev/soft_warnings_v974.py) — آنجا ضعف هفتگی warn است.
  وتوی سختهفتگی در مرحلهٔ **انتخاب** اعمال می‌شود، نه در مرحلهٔ **نمایش**.

## ۵) مسیر فازی (کم‌ریسک، با گیت تست)

هر فاز جدا قابل ادغام/واگرد است؛ ترتیب از کم‌ریسک‌ترین:

- **فاز ۰ — وتوی هفتگی:** انجام شد (بند ۴). رأی در بک‌اند ساخته و در انتخابِ واچ‌لیست اجرا می‌شود.
- **فاز ۱ — واژگان مشترک:** افزودن enumها و `ftsScoreOf` به `contracts`؛ **جابه‌جایی نصّی** جایگزینی لیست‌های تکراری با import. بدون تغییر منطق. گیت: `npm test` + `npm run lint` سبز.
- **فاز ۲ — پارامتر واحد:** همهٔ اتمجیک‌های عددی موتور → `strategyParamsStore`؛ حل تعارض سقف جنگ. گیت: تست‌های `strictGates`/`masterMath`.
- **فاز ۳ — تک‌پریست:** `persona` به `strategyStore`؛ اتصال چهار نما به یک انتخابگر.
- **فاز ۴ — تک‌مدل:** استخراج `StrategyVerdict` مشترک؛ سه موتور را روی آن بازنویسی/نازک کن. پرریسک‌ترین فاز — پیش از آن حتماً `dev/` guard و تست‌های ارجاع (golden) برای خروجی فعلی بگیر تا واگرد داشته باشی.

## ۶) قفل‌های هم‌زمان (باید با هر فاز عوض شوند)

- `fts_terminal.spec → hiddenimports`: اگر فایل/ماژول `api/*` یا `features/*` جدید ساخته شد (مثلاً اندپوینت هفتگی) اضافه شود، وگرنه EXE در اولین درخواست می‌میرد.
- `frontend/eslint.config.js` مرزهای `boundaries/element-types`: enumهای جدید در `contracts` مجازند؛ اما اگر `features/x` بخواهد از `features/y` بخواند باید صریح مجاز شود.
- هر فاز: اجرای `dev/run_all_tests.py` + گاردهای مرتبط. گیت قرمز **یافته است نه لزوماً نقص** — اول دادهٔ خام را ببین.

## ۷) واگرد

پروژه الگوی «جابه‌جایی نصّی + سابقه» را دارد (`MIGRATED_LINES.txt`، `app.py.bak`). هر فاز یک کامیت اتمیک + تگ؛ فاز ۴ پیش از شروع، خروجی `golden` فعلی سه موتور را در یک fixture ثبت کن تا بتوان diff داد.

## ۸) آنچه همین حالا انجام شد (خارج از این طرح)

- رفع باگ ترازِ نمرهٔ بنیادی (`ftsScoreOf` در `contracts`؛ ۵ نقطهٔ استخراج + `isSuperFundamental` روی «۵ از ۵»). ۹۰۷ تست سبز.
- زنده‌سازی تب درخت: نوار «وضعیت واقعی نماد» از خروجی `evaluateFtsPipeline` روی هر ۴ سرستون (F/T/S/M) با رنگ سبز/زرد/قرمز + حذف ۵ خطای lintِ مرده در آن فایل.

## ۹) تصمیمات باز (نظر شما)

1. در فاز ۴ کدام موتور «ستون فقرات» شود: `strictGates` (ماشین وتو، دقیق‌ترین به جزوه) یا `masterMath` (وزنی، برای برآیند عددی)؟ پیشنهاد: `strictGates` به‌عنوان حقیقتِ گیت‌ها، `masterMath` فقط برآیند وزنی.
2. `PresetMode` درخت و پریست جدول غربال: ادغام در تک‌persona یا حفظ به‌عنوان «فیلتر نمایشی» جدا؟
3. تکلیف `FtsPipelineBar`/`FtsAnalystModal`: بماند به‌عنوان چکیدهٔ سراسری، یا تب مستقل «مشاورهٔ تحلیلی» ساخته شود؟
