# طراحی میزکار ۲.۰، اسپاتلایت ۳D الگو، پورت‌های تلگرام و کرونوس

- تاریخ: 2026-11-06
- وضعیت: تصمیم‌های اصلی در چت تأیید شده؛ این سند مبنای پلن اجراست.
- پیش‌نیاز: فاز C (موتور رویداد) و فاز D (۳۹/۳۹ ردهٔ ۱، صفر جعلی) بسته شده‌اند.

## ۰. تصمیم‌های تأییدشده

1. **E0 اول**: audit کامل کانال تلگرام پیش از هر کد الگو؛ اگر اندیکاتور موجود است، اصلاح/پورت شود نه بازنویسی.
2. **دامنهٔ پورت E2**: p12 (Double Tap 3D) + p19 (Wedge & Channel) + p21 (S/R Retest Breakout).
3. **گرامر ۳D**: همهٔ الگوهای ردهٔ ۱ با یک زبان بصری؛ یک الگوی اصلی اسپاتلایت، بقیه برچسب فشرده.
4. **میزکار**: سه مود تحلیل/اسکن/پژوهش + داکینگ محدود ۴پنلی + چیدمان‌های نام‌دار ذخیره‌شدنی.
5. **اجرا**: E1 و E2 موازی با ساب‌ایجنت؛ کرونوس در پس‌زمینه از بعد از E0؛ اجرا با subagent-driven-development.
6. **کیفیت**: هر بخش با بهترین اسکیل موجود (unslop، web-animation-design، TDD، تست زنده، code review) و شاهد واقعی مرورگر.

## ۱. قیدهای الزام‌آور

- همهٔ محاسبات چارت روی سری **تعدیل عملکردی** همان چارت؛ حالت‌های تعدیل دیگر فقط با برچسب صریح.
- دروازهٔ فاز D نباید بشکند: ۳۹/۳۹ ردهٔ ۱، صفر جعلی، و قاعدهٔ ۱۵×۲.
- موتور موازی ممنوع: p19/p21 داخل `patterns/` و `events/` موجود ادغام می‌شوند، نه اورلی مستقل با منطق تکراری.
- هیچ آستانه‌ای بیرون `PATTERN_CONFIG`/`EVENT_CONFIG` نمی‌ماند؛ پارامترهای p19 در `patterns/config.ts` (`channelPivot`) و p21 در `events/config.ts` (`srRetest`) ثبت می‌شوند.
- unslop: کف متن ۱۲px، شبکهٔ ۴px، یک اکسنت UI، بدون گلو/هاله/پالس بی‌پایان در کروم؛ رنگ‌های معنایی بازار جدا از اکسنت. لایهٔ الگو می‌تواند پالت اشباع p12 را داشته باشد، اما بدون glow filter و بدون pulse.
- بدون WebGL/موتور سه‌بعدی؛ «۳D» با اکستروژن SVG/آفست و سایه پیاده می‌شود.
- فارسی/RTL، اعداد فارسی در UI، `prefers-reduced-motion` محترم.
- پورت باینری MT4/MT5 ممنوع؛ فقط سورس متنی با attribution.
- شاهد: ۱۳۶۶×۷۶۸ و ۱۹۲۰×۱۰۸۰، reduced-motion، و تست زندهٔ تعامل.
- هیچ commit/push بدون دستور مالک.

## ۲. E0 — audit تلگرام (اول)

### ۲.۱ منابع

- `docs/technical-indicators/inbox/Indi 516.txt` — Double Tap 3D، Pine v6، ۶۲۹ خط؛ منبع p12.
- `docs/technical-indicators/inbox/Indi 407.txt` — Automatic Wedge & Channel، Pine؛ منبع p19. `Indi 228.txt` هم‌خانواده نیست (Candle Pressure Flip) و پورت نمی‌شود.
- `docs/technical-indicators/inbox/Indi 248.txt` — S/R Retest Breakout، Pine؛ منبع p21.
- کاتالوگ: `frontend-v2/src/features/technical/data/telegram-indicators.json` و `docs/technical-indicators/TELEGRAM-CATALOG-TRIAGE-2026-11-03.md` (تریاج قدیمی است؛ موتور الگوی فاز A–D را نمی‌بیند).
- پست‌های تازهٔ کانال (2026-11-06): MW Pattern، Pattern Recognition، Pattern_Recognition_Master_v3، Hammer & Shooting Star. همه `.ex4/.ex5`/ZIP/ویدئو → **مرجع فقط، پورت نمی‌شوند**.
- **انتساب/مجوز:** p19 و p21 خط مجوز MPL-2.0 و برند `@IndicatorsforTV` دارند؛ attribution در `evidence.source` و مستندات پورت حفظ می‌شود و واترمارک کپی نمی‌شود. p12 خط مجوز ندارد؛ فقط به‌عنوان مرجع داخلی/کانال مالک استفاده می‌شود، منبع و تاریخ در audit ثبت می‌شود و بازتوزیع عمومی بدون تعیین تکلیف مجوز انجام نمی‌شود.
- **خروجی E0 = `_audit/rebuild/telegram-e0/audit.md` + بخش ۲ همین سند** (جدول audit + ماتریس وفاداری p12 + نقشهٔ p19/p21 + تصمیم‌ها)؛ هیچ کد الگو در E0 نوشته نمی‌شود.

### ۲.۲ ماتریس وفاداری p12

| مورد | p12 (Indi 516) | پیاده‌سازی فعلی | تصمیم E2 |
|---|---|---|---|
| تشخیص | پیوت ۸/۵، tol 0.75 ATR، span 10–150، height 1.5 ATR، expiry 60 + منطق clean rim | `DEFAULT_PRECISION_PARAMS`: ۵/۴، 0.45، 5–80، 1.0 | پارامترهای فاز D حفظ؛ پروفایل p12 و منطق clean rim/جایگزینی فقط پس از A/B روی ۱۵×۲ و بدون شکستن دروازه |
| امتیاز | ۲۵ تطابق + ۲۰ واگرایی RSI + ۱۵ واگرایی حجم + ۱۵ ارتفاع + ۱۰ تقارن + ۱۵ روند قبلی | کیفیت ۴۰ تطابق + ۲۰ عمق + ۱۵ span + ۱۵ روند + ۱۰ شکست | افزودن `p12Score` و `scoreBreakdown`؛ quality فعلی برای رتبه‌بندی می‌ماند |
| گرید | A ≥ 75، B ≥ 55، C < 55 | ندارد | `grade` در مدل و برچسب |
| چرخه | forming → active → success/failed/timed out؛ BE بعد از TP1؛ expiry 60 | forming/confirmed/invalidated | گسترش statusها و نقشهٔ outcome؛ تست‌های حالت |
| ریسک | TP1 = neck ± height، TP2 = neck ± 1.618 height، SL = peaks ± 0.25 ATR | target1/2 و stopLoss در موتور | هم‌ترازی با p12 برای W/M |
| نمایش | اسلب سه‌بعدی خط گردن، سایهٔ پاها، تگ BREAK/LONG/SHORT، ریل TP1/TP2/SL، دشبورد آمار | خط ۲px + چیپ کوچک | لایهٔ `PatternSpotlightLayer` با گرامر p12؛ دشبورد فشرده در ریل |
| رنگ | تاپ #FF2079، بات #00F0FF، برد #39FF14، باخت #FF5F1F، TP #FFF01F، neck #BC13FE | maroon/jade ملایم | رنگ معنایی چارت مطابق p12؛ UI chrome همان اکسنت unslop |

مالکیت W/M: منبع W/M فقط `DoubleTap3D`/`detectDoubleTapPatterns` است؛ `ClassicPatterns` و اسپاتلایت عمومی از رسم دوبارهٔ `DOUBLE_TOP/DOUBLE_BOTTOM` خودداری می‌کنند. فید می‌تواند رویداد W/M را از همان منبع نشان دهد.

### ۲.۳ نقشهٔ پورت p19/p21

**p19 — Wedge & Channel**
- پارامترها: `autoPivotCount=5`، `autoLookbackBars=250`، `minAnchorSpacing=10`، طول خط ۲۰، `breakoutATR=0.30`، `breakoutConfirmBars=2`، `expireAfterBreakBars=10`، `reclaimBars=2`، `lateStageWidthATR=1.5`، `lateStageApexBars=15`، `touchTol=0.20 ATR`، `violationTol=0.35 ATR`، `minTouchSpacing=5`، عرض 1–20 ATR، `balancePenaltyStart=1.5`.
- امتیاز: touches (حداکثر ۳۵)، balance (۱۵)، violations (حداکثر ۲۵)، span (۱۰)، recency (۱۰)، width (۵)؛ کپ‌های ۵۹/۸۴ برای touches<2/<3 و جریمهٔ عدم‌توازن.
- طبقه‌بندی: موازی (`slopeDiff ≤ 0.10×maxAbsSlope`) → Channel؛ همگرا → Symmetric/Descending/Ascending/Wedge؛ واگرا → Expanding.
- چرخه: شکست با دو بستهٔ آخر خارج از خط ±0.30 ATR؛ reclaim دو بستهٔ داخل؛ expiry ۱۰ کندل بعد از شکست یا عبور از apex؛ freeze متریک‌ها هنگام شکست.
- محل: `patterns/detectChannelPivot.ts` + `events/channel.ts` (نوع `PIVOT_CHANNEL`)؛ بدون تکرار `MultiModeChannel`.
- اولین برش (۵ رفتار قابل‌تست):
  1. امتیاز جزء‌به‌جزء مطابق Pine تا 1e-9 + کپ‌ها.
  2. طبقه‌بندی موازی/همگرا + `apexIndex/barsToApex/convergencePct/lateStage`.
  3. شکست ۲×0.30 ATR + reclaim + expiry + متریک فریزشده؛ بدون look-ahead (افزودن کندل بعدی رویداد گذشته را عوض نکند).
  4. زون p21 با `stdev(close,40)×1.0`، ضخامت o/h/l/c و رد هم‌پوشانی.
  5. ماشین حالت p21: 0 → ±1 → ±2 → ±3؛ دقیقاً یک سیگنال ریتست در کندل مورد انتظار.
- ریسک: پیوت ۲۰ کندلی دیرتر تأیید می‌شود؛ ATR باید سری‌ای باشد (`scan.ts` دارد)؛ حجم LTF در دسترس نیست → `volumeBalanceAvailable=false` و پروکسی جهت کندل؛ آستانه‌ها برای TSE بازتنظیم شوند؛ attribution MPL-2.0 + `@IndicatorsforTV` حفظ شود.

**p21 — S/R Retest Breakout**
- زون: `pivothigh/low(7,7)`، `tolerance=stdev(close,40)×1.0`، دو سوئینگ هم‌سطح، ضخامت از o/h/l/c، رد هم‌پوشانی قیمتی/زمانی.
- حجم: `requestUpAndDownVolume` در Pine؛ در وب موجود نیست → پروکسی حجم/جهت با برچسب عدم‌دسترس‌پذیری.
- چرخه: 0 → ±1 (کل کندل خارج) → ±2 (بستهٔ عبور) → ±3 (ریتست)؛ شکست ناموفق بازگشت؛ expiry ۵۰۰ کندل؛ حداکثر ۱۵۰ زون.
- محل: `events/zone.ts` + نوع رویداد `SR_RETEST`؛ بدون تکرار `BreakoutRetestPro`/`ftsSupportResistance`.

**p17** (SMC OB Scorer) فعلاً خارج از دامنه؛ بعد از E2 و با سورس `Indi 476.txt` ارزیابی می‌شود.

## ۳. E2 — اسپاتلایت الگو و پورت‌ها

### ۳.۱ مدل مشترک

`SpotlightModel` یک آداپتور خالص است که دو منبع را به یک شکل تبدیل می‌کند:
- W/M از `DoubleTapPattern` (شامل grade/score/formation/TP1/TP2/چرخه).
- بقیهٔ ردهٔ ۱ از `ChartPattern` (شامل kind/status/quality/points/upper/lower/neckline/target/stop/breakoutIndex).

`selectSpotlightPattern` یک الگوی اصلی انتخاب می‌کند: استخر کاندیدها الگوهای ردهٔ ۱ با anchor در ۲۵۰ کندل آخر (یا محدودهٔ دید) هستند؛ اولویت: forming با anchor در ۶۰ کندل آخر، سپس confirmed با anchor در ۱۲۰ کندل آخر، سپس بقیه؛ در هر گروه کیفیت و سپس تازگی anchor. اگر هیچ الگویی در این پنجره نبود، بالاترین کیفیت برجسته. بقیهٔ الگوهای برجسته با `ClassicPatterns` برچسب فشرده می‌گیرند. حداکثر یک اسپاتلایت.
`patternOverlay` از رسم `DOUBLE_TOP/DOUBLE_BOTTOM` خودداری می‌کند؛ منبع واحد W/M `DoubleTap3D` است. `PatternSpotlightLayer` هر دو منبع را از `SpotlightModel` می‌خواند.

### ۳.۲ گرامر بصری (از p12)

- پایهٔ ۳D: وجه جلو + وجه بالا/کنار به‌صورت polyline/polygon با آفست ۴ کندل و ۰.۶ ATR؛ سایهٔ پاها با آفست ۰.۱۸ ATR و شفافیت.
- رنگ‌های معنایی چارت: top #FF2079، bottom #00F0FF، win #39FF14، loss #FF5F1F، TP #FFF01F، neck #BC13FE؛ بدون گلو/پالس.
- برچسب اصلی: «DOUBLE TOP/BOTTOM · FORMING/ACTIVE/SUCCESS/FAILED» + «Grade A/B/C · score/100»؛ برای بقیهٔ الگوها: نام فارسی + وضعیت + گرید/کیفیت.
- تگ‌ها: BREAK در شکست، LONG/SHORT فقط اگر سیگنال معتبر (score/فیلترها)؛ TP1/TP2/SL با برچسب قیمت؛ BE بعد از TP1.
- برای الگوهای بدون neckline: slab روی مرز شکست/تریگر و ریل TP/SL از target/stopLoss همان الگو.
- دشبورد p12: فشرده در `InspectorRail` (TOPS/BOTTOMS، Detected، Breaks، Wins، TP2، Losses، Win Rate، Live Setup)؛ نه جدول بزرگ روی چارت.
- برچسب‌ها ≥۱۲px؛ متن فارسی/RTL؛ اعداد با `toFaDigits`.

### ۳.۳ انیمیشن

- یک‌باره در هر نماد/تایم‌فریم/الگوی اصلی: رسم مسیر ۷۰۰ms، slab/تگ ۲۰۰ms با stagger، برچسب ۱۵۰ms.
- `stroke-dashoffset` برای مسیر؛ opacity+translate برای slab/تگ؛ بدون loop/pulse.
- `prefers-reduced-motion`: همه static.
- تغییر نماد/تایم‌فریم اسپاتلایت قبلی را پاک و از نو اجرا می‌کند؛ همان identity دوباره اجرا نمی‌شود.

### ۳.۴ p12 score/lifecycle در موتور

- افزودن `p12Score`, `grade`, `scoreBreakdown` به مدل W/M؛ واگرایی RSI/حجم، تقارن و روند قبلی از همان کندل‌ها. اگر `volume` در دسترس نباشد، سهم حجم مطابق p12 نیم‌امتیاز (7.5) می‌گیرد.
- منطق `clean rim` (نبود سقف/کف بالاتر بین دو قله/دره) و جایگزینی الگوی forming قدیمی با الگوی جدیدِ نشکسته، به‌عنوان بهبود اختیاری با A/B روی ۱۵×۲ پورت می‌شود؛ اگر دروازه را نشکند می‌ماند.
- گسترش statusها: `failed`, `timed_out` در کنار forming/active/tp1_hit/tp2_hit/invalidated؛ `patternOutcome` و formation تست شوند.
- TP1/TP2/SL و BE مطابق p12؛ `keepTags`/`maxHist` رفتار برچسب‌ها.
- پارامترهای تشخیص p12 به‌عنوان پروفایل اختیاری در config؛ پیش‌فرض همان فاز D تا A/B نتیجه دهد.

### ۳.۵ اسکن خودکار

effect فعلی `KLineChartWrapper` حفظ می‌شود؛ `adjustmentMode` به dependencyها اضافه می‌شود. اسکن روی ۵۰۰ کندل آخر با سری تعدیل عملکردی؛ نتیجه در `scanResult` و `detectedPatterns`؛ بدون look-ahead.

### ۳.۶ تست و شاهد E2

- فیکسچرهای مثبت/منفی/مرزی برای p12 score/lifecycle و p19/p21 (حداقل ۵ AC بالا).
- parity فرمول‌های Pine تا 1e-9 در توابع خالص.
- تست no-look-ahead: افزودن کندل‌های آینده رویداد/بازبینی گذشته را تغییر ندهد.
- تست reduced-motion و عدم رسم دوبارهٔ W/M.
- بازاجرای audit ۱۵×۲ ردهٔ ۱؛ دروازه: صفر جعلی.
- اسکرین‌شات ۱۳۶۶/۱۹۲۰ اسپاتلایت، slabها، تگ‌ها، ریل آمار؛ ویدئوی کوتاه/تصویر متوالی اختیاری.
- build/tsc/کل تست‌ها.

## ۴. E1 — میزکار ۲.۰

- مودها: تحلیل (چارت + بازرس + فید؛ چارت ≥۶۰٪ در ۱۳۶۶)، اسکن (۵۰ نماد + چارت فشرده + فید؛ پیش‌فرض ≥۵۵٪)، پژوهش (چارت + خلاصهٔ بنیادی + بازرس/فید؛ ≥۵۰٪). در چیدمان دستی، چارت حداقل ۴۸۰px و هشدار زیر ۴۵٪.
- کاتالوگ پنل: chart، inspector، event-feed، scanner/top50، fundamental-summary، indicators.
- داکینگ: split-tree موجود، حداکثر ۴ پنل، درگ/اسپلیت/سواپ/بستن، حداقل ۳۲۰px هر پنل و ۴۸۰px چارت؛ بدون پنجرهٔ شناور؛ یک نمونهٔ چارت (multi-chart خارج از دامنهٔ اولیه).
- چیدمان‌های نام‌دار per-mode با ذخیره/بازیابی/Undo؛ کلید persist جدا (`bors-technical-workspace-v2`)؛ استور بازار دست‌نخورده.
- بازیابی: نماد، تایم‌فریم، ست اندیکاتور، وضعیت پنل‌ها؛ ترسیمات روی چارت/نماد می‌مانند.
- `Ctrl+K`: نماد، مود، چیدمان، اکشن پنل.
- visual language: تراکم Bloomberg، کروم TradingView، ریل خودکارسازی TrendSpider؛ unslop ۱۲px/۴px/یک اکسنت؛ ۲۰۰ms ورود پنل، بدون loop.
- تست‌ها: layout/store/shell/keyboard، visual contract موجود، a11y/focus، اسکرین‌شات ۱۳۶۶ و ۱۹۲۰، تست زندهٔ ذخیره/بازیابی.

## ۵. کرونوس (پس‌زمینه → F)

- دانلود `NeoQuasar/Kronos-mini` (4.1M) + tokenizer در `models/kronos`.
- اجرای CPU با `tools/kronos_inference.py`؛ اندازه‌گیری latency/حافظه؛ صحت horizon/quantiles.
- اتصال از مسیر موجود Go prediction و `forecastApi`/`ForecastControls`؛ مدل mini/small/base، کش، بودجهٔ تأخیر.
- برچسب صادقانه: مدل واقعی/fallback، بازهٔ اطمینان، محدودیت داده؛ بدون پیش‌بینی جعلی.
- اگر دانلود/اجرا ممکن نشد، گزارش دیوار دقیق + fallback برچسب‌دار؛ ادعای موفقیت بدون شاهد ممنوع.

## ۶. اجرا با ساب‌ایجنت‌ها

| فاز | مالکیت فایل | خروجی |
|---|---|---|
| E0 | audit فقط؛ `docs/technical-indicators/` و `_audit/rebuild/telegram-e0/` | `audit.md` + ماتریس p12 + نقشهٔ p19/p21 |
| E1 | `WorkspaceShell`, `Topbar`, `ActivityBar`, `EventFeed` host, store جدید، تست‌ها | مودها/داکینگ/چیدمان + شاهد |
| E2 | `KLineChartWrapper` فقط نقطهٔ mount، `PatternStoryOverlay`→`PatternSpotlightLayer`, `patternOverlay`/`eventOverlay`, `doubleTapEngine`/`doubleTapOverlay`, `detectChannelPivot`, `events/zone`, تست‌ها | اسپاتلایت ۳D + پورت‌ها + شاهد |
| Kronos | `tools/`, `backend-go/internal/prediction`, `models/kronos` | بنچمارک + گزارش |

- E0 اول؛ بعد E1/E2 موازی با دو ساب‌ایجنت و مالکیت بالا؛ کرونوس پس‌زمینه از بعد E0.
- مرز مشترک: `KLineChartWrapper` فقط در نقطهٔ mount توسط E2؛ E1 پوسته/پنل را می‌سازد و به درون چارت دست نمی‌زند. در صورت نیاز به تغییر مشترک، checkpoint ادغام.
- اسکیل‌ها: `unslop` (E1/E2 design)، `web-animation-design` (E2 animation)، `test-driven-development` (همه)، `verification-before-completion`، `requesting-code-review`، `subagent-driven-development`؛ تست زنده با browser-use/computer-use.
- ادغام: tsc + کل تست‌ها + audit دقت + اسکرین‌شات‌ها؛ هر ساب‌ایجنت قبل از ادعای موفقیت شاهد بیاورد.

## ۷. پذیرش

- E0: audit مستند، تصمیم reuse/fix/port/reject برای همهٔ ردیف‌های مرتبط، p12 fidelity و نقشهٔ p19/p21.
- E2: W/M وفادار به p12 (گرید/اسلب/تگ/TP/SL/چرخه)؛ همهٔ ردهٔ ۱ یک گرامر با یک الگوی اصلی؛ p19/p21 با ۵ AC؛ صفر جعلی ردهٔ ۱؛ reduced-motion؛ بدون رسم دوبارهٔ W/M.
- E1: مودها/داکینگ/چیدمان؛ چارت ≥۶۰٪ تحلیل؛ `Ctrl+K`؛ ذخیره/بازیابی؛ ۱۳۶۶/۱۹۲۰.
- Kronos: اجرای واقعی CPU با شاهد latency/حافظه یا گزارش صریح بن‌بست؛ fallback برچسب‌دار.
- کل تست‌ها/build سبز؛ هیچ رگرسیونی در فاز C/D.

## ۸. خارج از دامنه

- پورت باینری‌های MT4/MT5 (MW Pattern، Pattern Recognition و…)؛ فقط مرجع.
- WebGL/موتور سه‌بعدی واقعی؛ چند نمونهٔ چارت هم‌زمان؛ داکینگ آزاد نامحدود/پنجرهٔ شناور.
- p17/SMC OB Scorer تا بعد از E2؛ تغییر معماری بک‌اند یا موتور تعدیل.
- commit/push بدون دستور مالک.
