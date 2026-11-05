# طراحی — الگوهای کلاسیک چارت با نرخِ تشکیلِ تاریخی (مأموریت A)

**تاریخ:** ۲۰۲۶-۱۱-۰۵ · **مالک:** کاربر · **وضعیت:** تأییدشده («بله حله») · **شاخه:** `integration/4axes-main-2026-11-03`
**پیش‌نیاز:** افزایش ۱ فاز تکنیکال (`de63f882`: قرارداد تحلیل FTS) — بدونِ تغییرِ آن.

## ۱. هدف و غیرِهدف
**هدف:** ۱۱ دتکتورِ تازه کنارِ دوقلوی موجود (در مجموع ۱۲ الگو) که در کلاینتِ v2 روی کندل‌های
تعدیل‌شدهٔ تایم‌فریمِ فعال اجرا می‌شوند، هر کدام با «درصدِ تشکیلِ تاریخیِ همان نماد» (لاپلاس +
بازهٔ ویلسون)، بازدهِ ۱/۳/۵ کندل، و نمایشِ کم‌نویز روی چارت و پنل.
**غیرِهدف:** تغییرِ منطق/آستانه‌های FTS، تغییرِ بک‌اند یا System 1، اسکرینر/هشدار (مأموریت‌های بعد)،
بازطراحیِ میزکار (مأموریت B)، تلگرام و کرونوس (مأموریت‌های C و D).

## ۲. اصولِ ثابت
- منبعِ داده: همان `EngineCandle[]` چارت (تعدیل‌شده، تایم‌فریمِ فعال)؛ بدونِ درخواستِ شبکه.
- روشِ آماری دقیقاً همان دوقلو: `laplaceRate`، `wilsonInterval`، سبدِ کیفیت (ترسیل) و
  `FormationConfidence`؛ «نمونهٔ کافی نیست» جایِ عددِ ساختگی.
- `unresolved` هرگز شکست شمرده نمی‌شود.
- شناسه‌های الگو پایدار و قطعی‌اند (برای هویتِ overlay و تست).
- هیچ آستانهٔ پنهانی وجود ندارد: `PATTERN_CONFIG` تنها منبعِ اعداد است و در پنل «قواعد» نمایش داده می‌شود.

## ۳. مدلِ داده
```ts
export type PatternKind =
  | 'DOUBLE_TOP' | 'DOUBLE_BOTTOM'                     // موجود، دست‌نخورده
  | 'FLAG_BULL' | 'FLAG_BEAR' | 'PENNANT'
  | 'TRIANGLE_ASC' | 'TRIANGLE_DESC' | 'TRIANGLE_SYM'
  | 'RECTANGLE' | 'WEDGE_RISING' | 'WEDGE_FALLING'
  | 'HEAD_SHOULDERS' | 'INVERSE_HEAD_SHOULDERS'
  | 'TRIPLE_TOP' | 'TRIPLE_BOTTOM';

export type PatternStatus = 'forming' | 'confirmed' | 'invalidated';

export interface PatternPoint { index: number; price: number; timestamp: number }

export interface ChartPattern {
  id: string;                 // `${kind}:${anchorIndex}:${fingerprint}` — قطعی
  kind: PatternKind;
  direction: 'bullish' | 'bearish' | 'neutral';
  family: 'continuation' | 'reversal';
  anchor: PatternPoint;       // آخرین نقطهٔ سازنده
  points: PatternPoint[];     // قله/دره‌های سازنده به ترتیبِ زمان
  upper: { from: PatternPoint; to: PatternPoint; slope: number };  // خطِ مرزی بالا
  lower: { from: PatternPoint; to: PatternPoint; slope: number };  // خطِ مرزی پایین
  neckline?: { price: number; from: PatternPoint; to: PatternPoint };
  breakoutIndex?: number;
  target: number;
  stopLoss: number;
  quality: number;            // ۰–۱۰۰، هندسی؛ احتمال نیست
  status: PatternStatus;
  formation?: FormationEstimate; // همان نوعِ موجود؛ فقط برای forming
  returns?: { h1: number | null; h3: number | null; h5: number | null }; // بازدهِ تاریخیِ الگو
}
```
`FormationEstimate` موجود (probability, successes, failures, resolved, confidence, horizon, method,
qualityBucket, intervalLow/High) بدونِ تغییر استفاده می‌شود.

**پیوتِ مشترک:** توابعِ خصوصیِ `isPivotHigh`/`isPivotLow` از `doubleTapEngine.ts` به
`model/patterns/pivots.ts` منتقل می‌شوند و هر دو موتور از همان استفاده می‌کنند؛ رفتار باید
بایت‌به‌بایت یکسان بماند و تست‌های موجودِ دوقلو بدونِ تغییر سبز بمانند (این تنها بازآراییِ مجاز است).

## ۴. `PATTERN_CONFIG` (پیش‌فرض‌های قابلِ‌تنظیم، همه در ATR/درصد)
| کلید | مقدار | معنا |
|---|---|---|
| `pivLeft` / `pivRight` | ۵ / ۴ | همان تأییدِ نامتقارنِ پروفایلِ `precision` در دوقلو (`DEFAULT_PRECISION_PARAMS`) |
| `atrPeriod` | ۱۴ | همان `DEFAULT_PRECISION_PARAMS.atrPeriod` |
| `minTouchesPerLine` | ۲ | حداقلِ لمسِ هر خطِ مرزی |
| `flag.impulseLegAtrMin` | ۳٫۰ | لگِ قبل از پرچم حداقل ۳ ATR |
| `flag.channelMaxWidthPct` | ۳۵ | عرضِ کانال ≤ ۳۵٪ ارتفاعِ لگ |
| `flag.slopeOpposite` | true | شیبِ کانال خلافِ لگ (پرچمِ صحیح) |
| `pennant.convergenceMin` | ۰٫۳۵ | همگراییِ حداقلی |
| `triangle.flatToleranceAtr` | ۰٫۳۵ | تحملِ «تخت» بودنِ سقف/کف |
| `triangle.convergenceMin` | ۰٫۳۰ | همگراییِ حداقلی |
| `rectangle.flatToleranceAtr` | ۰٫۵۰ | تحملِ هم‌سطحیِ سقف و کف |
| `wedge.convergenceMin` | ۰٫۳۰ | همگرایی با شیبِ هم‌علامت |
| `hs.headAboveShouldersAtr` | ۰٫۵۰ | سر بالاتر از شانه‌ها |
| `hs.shouldersToleranceAtr` | ۰٫۶۰ | هم‌ترازیِ شانه‌ها |
| `triple.levelToleranceAtr` | ۰٫۵۰ | هم‌سطحیِ سه قله/دره |
| `maxBars` | flag ۴۰ · pennant ۳۰ · triangle/wedge ۶۰ · rectangle ۸۰ · hs/triple ۱۲۰ | پنجرهٔ جست‌وجو |
| `invalidationBufferAtr` | ۰٫۵۰ | همان دوقلو |
| `outcomeHorizon` | ۱۰ | همان دوقلو (برای نمونه‌های تاریخی) |
| `returnHorizons` | [۱، ۳، ۵] | بازدهِ گزارش‌شده |
| `formationMinResolved` | ۸ | زیرِ آن عدد نداریم |

## ۵. قواعدِ هندسی (خلاصهٔ تست‌پذیر)
- **پیوت:** قله/درهٔ فراکتال با `pivotStrength`؛ نقاط سازنده از پیوت‌های متوالی.
- **پرچم:** لگِ ایمپالس (≥ ۳ATR، بدونِ بازگشتِ > ۳۸٪)؛ سپس کانالِ موازیِ تنگ با شیبِ خلافِ لگ،
  ≥۲ لمس روی هر خط، عرض ≤ ۳۵٪ لگ. پنانت: همگرا (≤ ۳۵٪ عرضِ اولیه) بعد از همان لگ.
- **مثلثِ صعودی:** سقفِ تخت (انحراف ≤ ۰٫۳۵ATR) + کفِ بالارونده؛ نزولی آینه؛ متقارن: سقفِ پایین‌آینده
  + کفِ بالارونده با همگرایی ≥ ۰٫۳.
- **مستطیل:** سقف و کفِ تخت (≤ ۰٫۵ATR) با ≥۲ لمس روی هر کدام و بدونِ همگرایی.
- **گُوه:** دو خطِ هم‌علامت (هر دو صعودی یا هر دو نزولی) که همگرا می‌شوند (≥ ۰٫۳).
- **سر و شانه:** سه قله، وسط ≥ شانه‌ها + ۰٫۵ATR، شانه‌ها هم‌تراز (≤ ۰٫۶ATR)، خطِ گردن از دو دره؛
  معکوس آینه.
- **سه‌قلو:** سه قله/درهٔ هم‌سطح (≤ ۰٫۵ATR) با دو دره/قلهٔ میانی.
- مرزِ هر الگو با `maxBars` بسته می‌شود؛ الگوهای هم‌پوشانِ هم‌خانواده با قاعدهٔ `suppressOverlaps`
  موجود (فاصلهٔ عدمِ‌هم‌پوشانی) فیلتر می‌شوند.

## ۶. نتیجه (outcome) و درصد
```ts
outcome(pattern, candles, atr, horizon) -> 'success' | 'failure' | 'unresolved'
```
- **ادامه‌دهنده:** موفقیت = بسته‌شدن بیرونِ مرزِ جهت‌دار (شکست)؛ شکست = بسته‌شدن آن‌سوی مرزِ مخالف
  منهای/به‌علاوهٔ `invalidationBufferAtr`.
- **بازگشتی:** موفقیت = بسته‌شدن و تثبیت آن‌سوی خطِ گردن؛ شکست = عبور از سر/سه‌قلو + بافر.
- شروعِ سنجش: کندلِ بعد از `anchor`؛ پایان: `anchor+horizon` — مثل دوقلو.
- **درصد:** `laplaceRate(successes, failures)` با `wilsonInterval` وقتی `resolved ≥ 8`؛ سبدِ کیفیت
  وقتی ≥۸ نمونه در tercile؛ fallback کوهورت فقط با دادهٔ موجود (`doubletapCohort`) و برچسبِ method.
- **بازدهِ ۱/۳/۵:** میانگینِ بازدهِ بسته‌شدن نسبت به قیمتِ تریگر در همان افق‌ها، فقط روی نمونه‌های
  حل‌شده؛ `null` وقتی نمونه < ۵.

## ۷. سطوحِ نمایش
1. **کارتِ «الگوی آخر»** (بالای پنل الگوها): نوع، جهت، وضعیت، درصد + نمونه + بازه، بازدهِ ۱/۳/۵، و
   برچسبِ صریحِ «کندلِ در حال تشکیل ≠ تأییدشده» مطابقِ تصمیم ۶ سندِ تصمیم‌ها.
2. **چارت:** فقط آخرین «در حال تشکیل» و آخرین «تأییدشده» هر خانواده (سقفِ ۶ شکل) با یک لهجهٔ رنگی؛
   خطوطِ مرزی نازک، برچسبِ کوتاهِ فارسی، بدونِ انیمیشنِ loop.
3. **پنلِ فهرست:** مرتب بر زمان، فیلترِ نوع/خانواده، وضعیت، درصد؛ کلیک = فوکوس روی چارت.
4. **«قواعد»:** نمایشِ `PATTERN_CONFIG` به فارسی (شفافیتِ آستانه‌ها).
5. تایپو/آیکن/فاصله/حرکت دقیقاً روی مقیاسِ پاسِ unslop (۱۲px کف، SVG، ۴px، یک منحنی).

## ۸. تست
- **هندسه:** برای هر خانواده یک فیکسچرِ مثبت، یک منفی (شکلِ مشابه ولی رد) و یک مرزی (لمس/تحمل).
- **outcome:** سه مسیر success/failure/unresolved برای یک ادامه‌دهنده و یک بازگشتی.
- **آمار:** لاپلاس/ویلسون، آستانهٔ ۸، tercileِ کیفیت، `null` زیرِ آستانه، `unresolved` هرگز failure.
- **پایداری:** دو اجرای متوالی = همان `id`ها؛ تغییرِ تایم‌فریم = الگوهای تازه با idهای تازه.
- **رگرسیون:** خروجیِ `detectDoubleTapPatterns`/`estimateFormation` موجود بدونِ تغییر (تست‌های فعلی سبز بمانند).
- **UI:** کارت/پنل/overlay با fixture؛ «نمونهٔ کافی نیست» بدونِ عدد؛ درصد فقط روی `forming`.

## ۹. فازبندی
۱) types + config + پیوتِ مشترک + تست · ۲) دتکتورهای ادامه‌دهنده · ۳) بازگشتی‌ها ·
۴) outcome + formation + بازده · ۵) کارت/پنل/overlay + اسکرین‌شات ۱۳۶۶×۷۶۸ و ۱۹۲۰×۱۰۸۰ هر دو تم ·
۶) پذیرش: ۳ نماد × ۲ تایم‌فریم، شمارشِ الگوها، صفر خطای کنسول، و بازبینیِ دوقلو (بدونِ تغییر).

## ۱۰. ریسک‌ها و پاسخ
- **الگوهای زیاد/شلوغیِ چارت:** سقفِ ۶ شکل + فهرستِ جدا؛ چارت «کم‌نویز» می‌ماند.
- **نمونهٔ کمِ نمادهای کم‌معامله:** «نمونهٔ کافی نیست» صریح؛ هیچ عددی ساخته نمی‌شود.
- **هم‌پوشانیِ خانواده‌ها (مثلث/پرچم/گُوه):** اولویتِ ثبت: بازگشتی > ادامه‌دهندهٔ دارای لگ > بقیه؛
  الگوی هم‌پوشانِ ضعیف‌تر حذف می‌شود (قاعدهٔ موجودِ `suppressOverlaps`).
- **تعریفِ outcome برایِ بازگشتی‌ها:** خطِ گردن مبنایِ رسمی است؛ تستِ مسیرِ شکستِ دروغین اضافه می‌شود.
