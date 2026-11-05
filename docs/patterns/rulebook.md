# کتاب قواعد الگوها — فاز A

**تاریخ:** ۲۰۲۶-۱۱-۰۵ · **دامنه:** Technical Workspace Phase A، تسک A1
**سند الزام‌آور:** `docs/superpowers/specs/2026-11-05-technical-workspace-and-scanner-design.md`

این سند یک ردیف برای هر نوع الگو دارد: ۲۶ نوع = ۱۹ ردهٔ ۱ + ۷ ردهٔ ۲.
ستون «آستانه‌ها» فقط مقادیر `PATTERN_CONFIG` در
`frontend-v2/src/features/technical/model/patterns/config.ts` را تکرار می‌کند؛ هیچ عدد تازه‌ای این‌جا ساخته نشده است.

- همهٔ تشخیص‌دهنده‌های پیوتی، علاوه بر کلیدهای ردیف، از `pivLeft=5`، `pivRight=4`، `atrPeriod=14` و
  `invalidationBufferAtr=0.5` استفاده می‌کنند.
- `AMBIGUOUS` در ستون قاعده یعنی تعریف کلاسیک در منبع، شکل یا خانوادهٔ الگو را یکتا مشخص نمی‌کند؛
  به‌جای آستانهٔ حدسی، همان ابهام ثبت شده است.
- دوقلوی سقف/کف از موتور موجود `doubleTapEngine` می‌آید و دروازه‌هایش در `DEFAULT_PRECISION_PARAMS`
  است (`tolAtr=0.45`، `minSpan=5`، `maxSpan=80`، `minHeightAtr=1.0`، `nonOverlapBars=10`).
  این موتور برای حفظ خروجی بیت‌به‌بیت دست‌نخورده می‌ماند و آستانه‌هایش خارج از `PATTERN_CONFIG` است.
- ثابت‌های امتیازدهی کیفیت و طول بلوک جزیره، دروازهٔ تشخیص نیستند و در این جدول نمی‌آیند؛
  هر دروازهٔ تشخیصی که هنوز در `PATTERN_CONFIG` نیست، بدهی تسک‌های A2/A3 است.

| Kind | Tier | Rule | Thresholds (from `PATTERN_CONFIG` unless marked) | Visual reference | Source |
|---|---|---|---|---|---|
| `DOUBLE_TOP` | 1 | دو سقفِ تأییدشدهٔ هم‌تراز با یک درهٔ میانی؛ خط گردن از دره می‌گذرد و شکست نزولی آن تأیید می‌کند. | موتور موجود: `tolAtr=0.45`، `minSpan=5`، `maxSpan=80`، `minHeightAtr=1.0`، `nonOverlapBars=10` (خارج از `PATTERN_CONFIG`) | دو قلهٔ هم‌ارتفاع با درهٔ میانی (M) | موتور موجود (`doubleTapEngine` → `fromDoubleTap`) + Murphy 1999، Major Reversal Patterns |
| `DOUBLE_BOTTOM` | 1 | دو کفِ تأییدشدهٔ هم‌تراز با یک قلهٔ میانی؛ خط گردن از قله می‌گذرد و شکست صعودی آن تأیید می‌کند. | موتور موجود: `tolAtr=0.45`، `minSpan=5`، `maxSpan=80`، `minHeightAtr=1.0`، `nonOverlapBars=10` (خارج از `PATTERN_CONFIG`) | دو درهٔ هم‌ارتفاع با قلهٔ میانی (W) | موتور موجود (`doubleTapEngine` → `fromDoubleTap`) + Murphy 1999، Major Reversal Patterns |
| `HEAD_SHOULDERS` | 1 | شانهٔ چپ، سرِ بالاتر، شانهٔ راستِ هم‌تراز با شانهٔ چپ؛ خط گردن از دو دره؛ شکست نزولی خط گردن. | `hs.headAboveShouldersAtr=0.50` · `hs.shouldersToleranceAtr=0.60` · `hs.maxBars=120` · `reversal.minSpanBars=6` | شانه – دره – سر – دره – شانه | موتور موجود (`detectReversal`) + Murphy 1999، Major Reversal Patterns |
| `INVERSE_HEAD_SHOULDERS` | 1 | آینهٔ سر و شانه: سرِ پایین‌تر، شانه‌های هم‌تراز، خط گردن از دو قله؛ شکست صعودی. | `hs.headAboveShouldersAtr=0.50` · `hs.shouldersToleranceAtr=0.60` · `hs.maxBars=120` · `reversal.minSpanBars=6` | شانه – قله – سرِ پایین‌تر – قله – شانه | موتور موجود (`detectReversal`) + Murphy 1999، Major Reversal Patterns |
| `TRIPLE_TOP` | 1 | سه سقفِ هم‌سطح با دو درهٔ میانی؛ خط گردن از دره‌ها؛ شکست نزولی. | `triple.levelToleranceAtr=0.50` · `triple.maxBars=120` · `reversal.minSpanBars=6` | سه قلهٔ هم‌سطح و دو درهٔ میانی | موتور موجود (`detectReversal`) + Murphy 1999، Major Reversal Patterns |
| `TRIPLE_BOTTOM` | 1 | سه کفِ هم‌سطح با دو قلهٔ میانی؛ خط گردن از قله‌ها؛ شکست صعودی. | `triple.levelToleranceAtr=0.50` · `triple.maxBars=120` · `reversal.minSpanBars=6` | سه درهٔ هم‌سطح و دو قلهٔ میانی | موتور موجود (`detectReversal`) + Murphy 1999، Major Reversal Patterns |
| `FLAG_BULL` | 1 | لگِ صعودیِ تند، سپس کانال موازیِ کوتاهِ نزولی (عرض محدود)، سپس شکست صعودی. | `flag.impulseLegAtrMin=3.0` · `flag.channelMaxWidthPct=35` · `flag.slopeOpposite=true` · `flag.maxBars=40` · `flag.minLegBars=3` · `minTouchesPerLine=2` · `touchToleranceAtr=0.5` | میلهٔ صعودی تند + پرچم کوچکِ نزولی + شکست | موتور موجود (`detectContinuation`) + Murphy 1999، Continuation Patterns |
| `FLAG_BEAR` | 1 | لگِ نزولیِ تند، سپس کانال موازیِ کوتاهِ صعودی، سپس شکست نزولی. | `flag.impulseLegAtrMin=3.0` · `flag.channelMaxWidthPct=35` · `flag.slopeOpposite=true` · `flag.maxBars=40` · `flag.minLegBars=3` · `minTouchesPerLine=2` · `touchToleranceAtr=0.5` | میلهٔ نزولی تند + پرچم کوچکِ صعودی + شکست | موتور موجود (`detectContinuation`) + Murphy 1999، Continuation Patterns |
| `PENNANT` | 1 | لگِ تند، سپس کانالِ کوچکِ همگرا؛ شکست هم‌جهت با لگ. | `pennant.impulseLegAtrMin=3.0` · `pennant.convergenceMin=0.35` · `pennant.maxBars=30` · `flag.minLegBars=3` · `minTouchesPerLine=2` · `touchToleranceAtr=0.5` | میلهٔ تند + پنانتِ همگرا + شکست | موتور موجود (`detectContinuation`) + Murphy 1999، Continuation Patterns |
| `TRIANGLE_ASC` | 1 | سقفِ افقی در تلورانسِ تخت و کفِ صعودی؛ عرض همگرا؛ شکست صعودی. | `triangle.flatToleranceAtr=0.35` · `triangle.convergenceMin=0.30` · `triangle.maxBars=60` · `triangle.minSpan=3` | سقف افقی، کف صعودی | موتور موجود (`detectContinuation`) + Murphy 1999، Continuation Patterns |
| `TRIANGLE_DESC` | 1 | سقفِ نزولی و کفِ افقی؛ عرض همگرا؛ شکست نزولی. | `triangle.flatToleranceAtr=0.35` · `triangle.convergenceMin=0.30` · `triangle.maxBars=60` · `triangle.minSpan=3` | سقف نزولی، کف افقی | موتور موجود (`detectContinuation`) + Murphy 1999، Continuation Patterns |
| `TRIANGLE_SYM` | 1 | سقف‌های پایین‌رونده و کف‌های بالارونده؛ عرض با `convergenceMin` کم می‌شود؛ شکست دوطرفه (خنثی). | `triangle.flatToleranceAtr=0.35` · `triangle.convergenceMin=0.30` · `triangle.maxBars=60` · `triangle.minSpan=3` | سقف نزولی، کف صعودی | موتور موجود (`detectContinuation`) + Murphy 1999، Continuation Patterns |
| `RECTANGLE` | 1 | هر دو مرز در تلورانسِ تخت؛ جعبهٔ رنج؛ شکست دوطرفه (خنثی). | `rectangle.flatToleranceAtr=0.50` · `rectangle.maxBars=80` · `triangle.minSpan=3` | جعبهٔ افقی | موتور موجود (`detectContinuation`) + Murphy 1999، Continuation Patterns |
| `WEDGE_RISING` | 1 | هر دو مرز صعودی و همگرا؛ سوگیری نزولی. | `wedge.convergenceMin=0.30` · `wedge.maxBars=60` · `triangle.minSpan=3` | دو خط صعودیِ همگرا | موتور موجود (`detectContinuation`) + Murphy 1999، Continuation Patterns |
| `WEDGE_FALLING` | 1 | هر دو مرز نزولی و همگرا؛ سوگیری صعودی. | `wedge.convergenceMin=0.30` · `wedge.maxBars=60` · `triangle.minSpan=3` | دو خط نزولیِ همگرا | موتور موجود (`detectContinuation`) + Murphy 1999، Continuation Patterns |
| `CUP_HANDLE` | 1 | کفِ Uشکل با دو لبهٔ هم‌تراز در تلورانسِ لبه؛ دسته حداکثر `handleDepthPct` از عمق کاپ؛ شکست صعودی لبه. | `cup.rimToleranceAtr=0.5` · `cup.handleDepthPct=33` · `cup.minBars=20` · `cup.maxBars=160` | کاپ Uشکل + دستهٔ کوچک نزدیک لبهٔ راست | کلاسیک: O'Neil، How to Make Money in Stocks؛ Bulkowski؛ تشخیص‌دهندهٔ A2 |
| `INVERSE_CUP_HANDLE` | 1 | آینهٔ کاپ: سقفِ ∩شکل با دو لبهٔ هم‌تراز؛ دسته حداکثر `handleDepthPct` از عمق؛ شکست نزولی لبه. | `cup.rimToleranceAtr=0.5` · `cup.handleDepthPct=33` · `cup.minBars=20` · `cup.maxBars=160` | کاپ معکوس ∩شکل + دستهٔ کوچک نزدیک لبهٔ راست | کلاسیک: O'Neil، How to Make Money in Stocks؛ Bulkowski؛ تشخیص‌دهندهٔ A2 |
| `ROUNDING_TOP` | 1 | سه‌بخشِ سری: بخش میانی بالاترین و دو سر هم‌تراز؛ گنبدِ گرد؛ شکست نزولی. | `rounding.curvatureMin=0.55` · `rounding.minBars=30` · `rounding.maxBars=200` | گنبد: تخت – سقفِ گرد – تخت | کلاسیک: Murphy 1999، Major Reversal Patterns (saucer)؛ تشخیص‌دهندهٔ A2 |
| `ROUNDING_BOTTOM` | 1 | سه‌بخشِ سری: بخش میانی پایین‌ترین و دو سر هم‌تراز؛ کاسهٔ گرد؛ شکست صعودی. | `rounding.curvatureMin=0.55` · `rounding.minBars=30` · `rounding.maxBars=200` | کاسه: تخت – کفِ گرد – تخت | کلاسیک: Murphy 1999، Major Reversal Patterns (saucer)؛ تشخیص‌دهندهٔ A2 |
| `DIAMOND_TOP` | 2 | پنج پیوتِ متناوب (سقف‌های ۱-۳-۵ و کف‌های ۲-۴)؛ عرضِ مرزها با `diamondConvergeMin` کم می‌شود. الماسِ کلاسیک ابتدا پهن و سپس همگرا می‌شود؛ این موتور فقط نیمهٔ همگرا را پیاده می‌کند و کل تعریف کلاسیک AMBIGUOUS است. | `tier2.diamondConvergeMin=0.25` · `hs.maxBars=120` | پنج پیوت متناوب؛ عرضِ مرزها کوچک‌شونده (نیمهٔ الماس) | کلاسیک: Murphy 1999 / Bulkowski؛ ردهٔ ۲ بهترین‌تلاش (A3) |
| `DIAMOND_BOTTOM` | 2 | آینهٔ الماسِ همگرا: پنج پیوت متناوب با سقف‌های میانی و کف‌های محیطی؛ عرض با `diamondConvergeMin` کم می‌شود. تعریف کلاسیک AMBIGUOUS است. | `tier2.diamondConvergeMin=0.25` · `hs.maxBars=120` | پنج پیوت متناوب؛ عرضِ مرزها کوچک‌شونده (نیمهٔ الماس) | کلاسیک: Murphy 1999 / Bulkowski؛ ردهٔ ۲ بهترین‌تلاش (A3) |
| `BROADENING_TOP` | 2 | پنج پیوتِ متناوب؛ عرضِ مرزها با `broadeningMin` بزرگ می‌شود؛ سوگیری نزولی. | `tier2.broadeningMin=0.25` · `hs.maxBars=120` | پنج پیوت متناوب؛ عرضِ مرزها بزرگ‌شونده (شیپور) | کلاسیک: Murphy 1999 / Bulkowski؛ ردهٔ ۲ بهترین‌تلاش (A3) |
| `BROADENING_BOTTOM` | 2 | پنج پیوتِ متناوب؛ عرضِ مرزها با `broadeningMin` بزرگ می‌شود؛ سوگیری صعودی. | `tier2.broadeningMin=0.25` · `hs.maxBars=120` | پنج پیوت متناوب؛ عرضِ مرزها بزرگ‌شونده (شیپور) | کلاسیک: Murphy 1999 / Bulkowski؛ ردهٔ ۲ بهترین‌تلاش (A3) |
| `ISLAND_REVERSAL` | 2 | گپِ ورود حداقل `islandGapAtr`، بلوکِ کوتاهِ جزیره، سپس گپِ خروج حداقل `islandGapAtr`؛ بازگشتی. | `tier2.islandGapAtr=0.5` · `invalidationBufferAtr=0.5` | گپ ورود – جزیرهٔ کوتاه – گپ خروج | کلاسیک: Murphy 1999 / Bulkowski؛ ردهٔ ۲ بهترین‌تلاش (A3) |
| `THREE_RISING_PEAKS` | 2 | سه سقفِ تأییدشده با اختلاف حداکثر `threePeaksToleranceAtr` و دو کفِ بالارونده میان آن‌ها؛ در کد فقط سقف سوم > سقف اول لازم است. نام «صعودی» و خانوادهٔ کلاسیک (بازگشتی در سقف) AMBIGUOUS است. | `tier2.threePeaksToleranceAtr=0.5` · `hs.maxBars=120` | سه سقفِ هم‌سطح با کف‌های بالارونده | کلاسیک: Bulkowski، Encyclopedia of Chart Patterns؛ ردهٔ ۲ بهترین‌تلاش (A3) |
| `THREE_FALLING_PEAKS` | 2 | سه کفِ تأییدشده با اختلاف حداکثر `threePeaksToleranceAtr` و دو سقفِ پایین‌رونده میان آن‌ها؛ در کد فقط کف سوم < کف اول لازم است. نام و خانوادهٔ کلاسیک (بازگشتی در سقف در برابر ادامه‌دهنده در کف) AMBIGUOUS است. | `tier2.threePeaksToleranceAtr=0.5` · `hs.maxBars=120` | سه کفِ هم‌سطح با سقف‌های پایین‌رونده | کلاسیک: Bulkowski، Encyclopedia of Chart Patterns؛ ردهٔ ۲ بهترین‌تلاش (A3) |

## جمع رده‌ها

| Tier | Count | Kinds |
|---|---|---|
| 1 | 19 | `DOUBLE_TOP`، `DOUBLE_BOTTOM`، `HEAD_SHOULDERS`، `INVERSE_HEAD_SHOULDERS`، `TRIPLE_TOP`، `TRIPLE_BOTTOM`، `FLAG_BULL`، `FLAG_BEAR`، `PENNANT`، `TRIANGLE_ASC`، `TRIANGLE_DESC`، `TRIANGLE_SYM`، `RECTANGLE`، `WEDGE_RISING`، `WEDGE_FALLING`، `CUP_HANDLE`، `INVERSE_CUP_HANDLE`، `ROUNDING_TOP`، `ROUNDING_BOTTOM` |
| 2 | 7 | `DIAMOND_TOP`، `DIAMOND_BOTTOM`، `BROADENING_TOP`، `BROADENING_BOTTOM`، `ISLAND_REVERSAL`، `THREE_RISING_PEAKS`، `THREE_FALLING_PEAKS` |
