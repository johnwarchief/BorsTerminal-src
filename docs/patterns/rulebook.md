# کتاب قواعد الگوها — فاز A

**تاریخ:** ۲۰۲۶-۱۱-۰۵ · **دامنه:** Technical Workspace Phase A، تسک A1
**سند الزام‌آور:** `docs/superpowers/specs/2026-11-05-technical-workspace-and-scanner-design.md`

آستانه‌های این سند از PATTERN_CONFIG خوانده می‌شوند؛ هر ردیف که دروازه‌اش هنوز پیاده نشده با «برنامه‌ریزی‌شده در A2/A3» علامت خورده است.

این سند یک ردیف برای هر نوع الگو دارد: ۲۶ نوع = ۱۹ ردهٔ ۱ + ۷ ردهٔ ۲.
ستون «آستانه‌ها» مقادیر `PATTERN_CONFIG` در
`frontend-v2/src/features/technical/model/patterns/config.ts` را تکرار می‌کند؛ هر مقدار خارج از آن در همان ردیف صریحاً علامت خورده است.

- همهٔ تشخیص‌دهنده‌های پیوتی، علاوه بر کلیدهای ردیف، از `pivLeft=5`، `pivRight=4`، `atrPeriod=14` و
  `invalidationBufferAtr=0.5` استفاده می‌کنند.
- `AMBIGUOUS` در ستون قاعده یعنی تعریف کلاسیک در منبع، شکل یا خانوادهٔ الگو را یکتا مشخص نمی‌کند؛
  به‌جای آستانهٔ حدسی، همان ابهام ثبت شده است.
- ستون Source یکی از سه منبع `existing-engine`، `classic` یا `telegram` است. اگر تشخیص‌دهندهٔ الگو هنوز
  نوشته نشده، نامِ تشخیص‌دهنده ذکر نمی‌شود و به‌جایش «پیاده‌سازی: A2» یا «پیاده‌سازی: A3» می‌آید؛
  همین یادداشت، علامت «برنامه‌ریزی‌شده در A2/A3» است.
- دوقلوی سقف/کف از موتور موجود `doubleTapEngine` می‌آید و دروازه‌هایش در `DEFAULT_PRECISION_PARAMS`
  است (`tolAtr=0.45`، `minSpan=5`، `maxSpan=80`، `minHeightAtr=1.0`، `nonOverlapBars=10`).
  این موتور برای حفظ خروجی بیت‌به‌بیت دست‌نخورده می‌ماند و آستانه‌هایش خارج از `PATTERN_CONFIG` است.
- ثابت‌های امتیازدهی کیفیت دروازهٔ تشخیص نیستند و در این جدول نمی‌آیند؛ دروازه‌های پیاده‌نشده (از جمله
  خروجِ جزیره در ۵ کندل و `maxBars=6`) در ردیف خودشان با «برنامه‌ریزی‌شده در A2/A3» علامت خورده‌اند.

| Kind | Tier | Rule | Thresholds (from `PATTERN_CONFIG` unless marked) | Visual reference | Source |
|---|---|---|---|---|---|
| `DOUBLE_TOP` | 1 | دو سقفِ تأییدشدهٔ هم‌تراز با یک درهٔ میانی؛ خط گردن از دره می‌گذرد و شکست نزولی آن تأیید می‌کند. | موتور موجود: `tolAtr=0.45`، `minSpan=5`، `maxSpan=80`، `minHeightAtr=1.0`، `nonOverlapBars=10` (خارج از `PATTERN_CONFIG`) | دو قلهٔ هم‌ارتفاع با درهٔ میانی (M) | `existing-engine` (`doubleTapEngine` → `fromDoubleTap`) + Murphy 1999، Major Reversal Patterns |
| `DOUBLE_BOTTOM` | 1 | دو کفِ تأییدشدهٔ هم‌تراز با یک قلهٔ میانی؛ خط گردن از قله می‌گذرد و شکست صعودی آن تأیید می‌کند. | موتور موجود: `tolAtr=0.45`، `minSpan=5`، `maxSpan=80`، `minHeightAtr=1.0`، `nonOverlapBars=10` (خارج از `PATTERN_CONFIG`) | دو درهٔ هم‌ارتفاع با قلهٔ میانی (W) | `existing-engine` (`doubleTapEngine` → `fromDoubleTap`) + Murphy 1999، Major Reversal Patterns |
| `HEAD_SHOULDERS` | 1 | شانهٔ چپ، سرِ بالاتر، شانهٔ راستِ هم‌تراز با شانهٔ چپ؛ خط گردن از دو دره؛ شکست نزولی خط گردن. | `hs.headAboveShouldersAtr=0.50` · `hs.shouldersToleranceAtr=0.60` · `hs.maxBars=120` · `reversal.minSpanBars=6` | شانه – دره – سر – دره – شانه | `existing-engine` (`detectReversal`) + Murphy 1999، Major Reversal Patterns |
| `INVERSE_HEAD_SHOULDERS` | 1 | آینهٔ سر و شانه: سرِ پایین‌تر، شانه‌های هم‌تراز، خط گردن از دو قله؛ شکست صعودی. | `hs.headAboveShouldersAtr=0.50` · `hs.shouldersToleranceAtr=0.60` · `hs.maxBars=120` · `reversal.minSpanBars=6` | شانه – قله – سرِ پایین‌تر – قله – شانه | `existing-engine` (`detectReversal`) + Murphy 1999، Major Reversal Patterns |
| `TRIPLE_TOP` | 1 | سه سقفِ هم‌سطح با دو درهٔ میانی؛ خط گردن از دره‌ها؛ شکست نزولی. | `triple.levelToleranceAtr=0.50` · `triple.maxBars=120` · `reversal.minSpanBars=6` | سه قلهٔ هم‌سطح و دو درهٔ میانی | `existing-engine` (`detectReversal`) + Murphy 1999، Major Reversal Patterns |
| `TRIPLE_BOTTOM` | 1 | سه کفِ هم‌سطح با دو قلهٔ میانی؛ خط گردن از قله‌ها؛ شکست صعودی. | `triple.levelToleranceAtr=0.50` · `triple.maxBars=120` · `reversal.minSpanBars=6` | سه درهٔ هم‌سطح و دو قلهٔ میانی | `existing-engine` (`detectReversal`) + Murphy 1999، Major Reversal Patterns |
| `FLAG_BULL` | 1 | لگِ صعودیِ تند، سپس کانال موازیِ کوتاهِ نزولی (عرض محدود)، سپس شکست صعودی. | `flag.impulseLegAtrMin=3.0` · `flag.channelMaxWidthPct=35` · `flag.slopeOpposite=true` · `flag.maxBars=40` · `flag.minLegBars=3` · `minTouchesPerLine=2` · `touchToleranceAtr=0.5` | میلهٔ صعودی تند + پرچم کوچکِ نزولی + شکست | `existing-engine` (`detectContinuation`) + Murphy 1999، Continuation Patterns |
| `FLAG_BEAR` | 1 | لگِ نزولیِ تند، سپس کانال موازیِ کوتاهِ صعودی، سپس شکست نزولی. | `flag.impulseLegAtrMin=3.0` · `flag.channelMaxWidthPct=35` · `flag.slopeOpposite=true` · `flag.maxBars=40` · `flag.minLegBars=3` · `minTouchesPerLine=2` · `touchToleranceAtr=0.5` | میلهٔ نزولی تند + پرچم کوچکِ صعودی + شکست | `existing-engine` (`detectContinuation`) + Murphy 1999، Continuation Patterns |
| `PENNANT` | 1 | لگِ تند، سپس کانالِ کوچکِ همگرا؛ شکست هم‌جهت با لگ. | `pennant.impulseLegAtrMin=3.0` · `pennant.convergenceMin=0.35` · `pennant.maxBars=30` · `flag.minLegBars=3` · `minTouchesPerLine=2` · `touchToleranceAtr=0.5` | میلهٔ تند + پنانتِ همگرا + شکست | `existing-engine` (`detectContinuation`) + Murphy 1999، Continuation Patterns |
| `TRIANGLE_ASC` | 1 | سقفِ افقی در تلورانسِ `triangle.flatToleranceAtr` و کفِ صعودی (`l2 > l1`)؛ شکست صعودی. عرضِ همگرا دروازهٔ این الگو نیست. | `triangle.flatToleranceAtr=0.35` · `triangle.maxBars=60` · `triangle.minSpan=3` | سقف افقی، کف صعودی | `existing-engine` (`detectContinuation`) + Murphy 1999، Continuation Patterns |
| `TRIANGLE_DESC` | 1 | کفِ افقی در تلورانسِ `triangle.flatToleranceAtr` و سقفِ نزولی (`h2 < h1`)؛ شکست نزولی. عرضِ همگرا دروازهٔ این الگو نیست. | `triangle.flatToleranceAtr=0.35` · `triangle.maxBars=60` · `triangle.minSpan=3` | سقف نزولی، کف افقی | `existing-engine` (`detectContinuation`) + Murphy 1999، Continuation Patterns |
| `TRIANGLE_SYM` | 1 | سقف‌های پایین‌رونده و کف‌های بالارونده؛ عرضِ فشرده‌سازی با `triangle.convergenceMin` کم می‌شود (تنها ردیفِ مثلث که این کلید را می‌خواند)؛ شکست دوطرفه (خنثی). | `triangle.convergenceMin=0.30` · `triangle.maxBars=60` · `triangle.minSpan=3` | سقف نزولی، کف صعودی | `existing-engine` (`detectContinuation`) + Murphy 1999، Continuation Patterns |
| `RECTANGLE` | 1 | هر دو مرز در تلورانسِ تخت؛ جعبهٔ رنج؛ شکست دوطرفه (خنثی). | `rectangle.flatToleranceAtr=0.50` · `rectangle.maxBars=80` · `triangle.minSpan=3` | جعبهٔ افقی | `existing-engine` (`detectContinuation`) + Murphy 1999، Continuation Patterns |
| `WEDGE_RISING` | 1 | هر دو مرز صعودی و همگرا؛ سوگیری نزولی. | `wedge.convergenceMin=0.30` · `wedge.maxBars=60` · `triangle.minSpan=3` | دو خط صعودیِ همگرا | `existing-engine` (`detectContinuation`) + Murphy 1999، Continuation Patterns |
| `WEDGE_FALLING` | 1 | هر دو مرز نزولی و همگرا؛ سوگیری صعودی. | `wedge.convergenceMin=0.30` · `wedge.maxBars=60` · `triangle.minSpan=3` | دو خط نزولیِ همگرا | `existing-engine` (`detectContinuation`) + Murphy 1999، Continuation Patterns |
| `CUP_HANDLE` | 1 | کفِ Uشکل با دو لبهٔ هم‌تراز در تلورانسِ لبه؛ دسته حداکثر `handleDepthPct` از عمق کاپ؛ شکست صعودی لبه. | `cup.rimToleranceAtr=0.5` · `cup.handleDepthPct=33` · `cup.minBars=20` · `cup.maxBars=160` | کاپ Uشکل + دستهٔ کوچک نزدیک لبهٔ راست | `classic` (O'Neil، How to Make Money in Stocks؛ Bulkowski) · پیاده‌سازی: A2 |
| `INVERSE_CUP_HANDLE` | 1 | آینهٔ کاپ: سقفِ ∩شکل با دو لبهٔ هم‌تراز؛ دسته حداکثر `handleDepthPct` از عمق؛ شکست نزولی لبه. | `cup.rimToleranceAtr=0.5` · `cup.handleDepthPct=33` · `cup.minBars=20` · `cup.maxBars=160` | کاپ معکوس ∩شکل + دستهٔ کوچک نزدیک لبهٔ راست | `classic` (O'Neil، How to Make Money in Stocks؛ Bulkowski) · پیاده‌سازی: A2 |
| `ROUNDING_TOP` | 1 | سه‌بخشِ سری: بخش میانی بالاترین و دو سر هم‌تراز؛ گنبدِ گرد؛ شکست نزولی. | `rounding.curvatureMin=0.55` · `rounding.minBars=30` · `rounding.maxBars=200` | گنبد: تخت – سقفِ گرد – تخت | `classic` (Murphy 1999، Major Reversal Patterns (saucer)؛ Bulkowski) · پیاده‌سازی: A2 |
| `ROUNDING_BOTTOM` | 1 | سه‌بخشِ سری: بخش میانی پایین‌ترین و دو سر هم‌تراز؛ کاسهٔ گرد؛ شکست صعودی. | `rounding.curvatureMin=0.55` · `rounding.minBars=30` · `rounding.maxBars=200` | کاسه: تخت – کفِ گرد – تخت | `classic` (Murphy 1999، Major Reversal Patterns (saucer)؛ Bulkowski) · پیاده‌سازی: A2 |
| `DIAMOND_TOP` | 2 | پنج پیوتِ متناوب (سقف‌های ۱-۳-۵ و کف‌های ۲-۴)؛ عرضِ مرزها با `diamondConvergeMin` کم می‌شود. الماسِ کلاسیک ابتدا پهن و سپس همگرا می‌شود؛ این موتور فقط نیمهٔ همگرا را پیاده می‌کند و کل تعریف کلاسیک AMBIGUOUS است. | `tier2.diamondConvergeMin=0.25` · `hs.maxBars=120` | پنج پیوت متناوب؛ عرضِ مرزها کوچک‌شونده (نیمهٔ الماس) | `classic` (Murphy 1999 / Bulkowski) · پیاده‌سازی: A3 (ردهٔ ۲، بهترین‌تلاش) |
| `DIAMOND_BOTTOM` | 2 | آینهٔ الماسِ همگرا: پنج پیوت متناوب با سقف‌های میانی و کف‌های محیطی؛ عرض با `diamondConvergeMin` کم می‌شود. تعریف کلاسیک AMBIGUOUS است. | `tier2.diamondConvergeMin=0.25` · `hs.maxBars=120` | پنج پیوت متناوب؛ عرضِ مرزها کوچک‌شونده (نیمهٔ الماس) | `classic` (Murphy 1999 / Bulkowski) · پیاده‌سازی: A3 (ردهٔ ۲، بهترین‌تلاش) |
| `BROADENING_TOP` | 2 | پنج پیوتِ متناوب؛ عرضِ مرزها با `broadeningMin` بزرگ می‌شود؛ سوگیری نزولی. | `tier2.broadeningMin=0.25` · `hs.maxBars=120` | پنج پیوت متناوب؛ عرضِ مرزها بزرگ‌شونده (شیپور) | `classic` (Murphy 1999 / Bulkowski) · پیاده‌سازی: A3 (ردهٔ ۲، بهترین‌تلاش) |
| `BROADENING_BOTTOM` | 2 | پنج پیوتِ متناوب؛ عرضِ مرزها با `broadeningMin` بزرگ می‌شود؛ سوگیری صعودی. | `tier2.broadeningMin=0.25` · `hs.maxBars=120` | پنج پیوت متناوب؛ عرضِ مرزها بزرگ‌شونده (شیپور) | `classic` (Murphy 1999 / Bulkowski) · پیاده‌سازی: A3 (ردهٔ ۲، بهترین‌تلاش) |
| `ISLAND_REVERSAL` | 2 | گپِ ورود ≥ `islandGapAtr`، سپس گپِ خروج ≥ `islandGapAtr` در حداکثر `islandMaxBlockBars` کندل پس از ورود؛ بازگشتی. گپِ خروج از اکسترممِ جاریِ بلوک سنجیده می‌شود، نه فقط کندلِ ورود (R-PA-11). | `tier2.islandGapAtr=0.5` · `tier2.islandMaxBlockBars=5` · `tier2.islandMaxBars=6` · `invalidationBufferAtr=0.5` | گپ ورود – جزیرهٔ کوتاه – گپ خروج | `classic` (Murphy 1999 / Bulkowski) · پیاده‌سازی: A3 (ردهٔ ۲، بهترین‌تلاش) |
| `THREE_RISING_PEAKS` | 2 | سه سقفِ تأییدشدهٔ هم‌سطح با گسترهٔ max−min ≤ `threePeaksToleranceAtr` و حداقل دو کفِ میانی؛ سقف سوم بالاتر از سقف اول (صعودی)، خانوادهٔ بازگشتیِ نزولی. R-PA-13: هر دو گونهٔ سه‌قله فقط از **سقف‌ها** ساخته می‌شوند و مقایسهٔ سقف اول/سوم گونه را تعیین می‌کند (سقف‌های هم‌ارتفاع «صعودی» شمرده می‌شوند)؛ همین مقایسه ۱۰ امتیاز کیفیت هم می‌دهد. نام و خانواده در منبع کلاسیک AMBIGUOUS است. | `tier2.threePeaksToleranceAtr=0.5` · `hs.maxBars=120` | سه سقفِ هم‌سطحِ صعودی با دو کفِ میانی | `classic` (Bulkowski، Encyclopedia of Chart Patterns) · پیاده‌سازی: A3 · بازبینی: A4 (R-PA-13) |
| `THREE_FALLING_PEAKS` | 2 | سه سقفِ تأییدشدهٔ هم‌سطح با گسترهٔ max−min ≤ `threePeaksToleranceAtr` و حداقل دو کفِ میانی؛ سقف سوم پایین‌تر از سقف اول (نزولی)، خانوادهٔ **ادامه‌دهندهٔ نزولی**. R-PA-13: کف‌ها هیچ گونه‌ای نمی‌سازند؛ نگاشتِ قبلیِ کف→این گونه با `TRIPLE_BOTTOM` هم‌پوشان می‌شد و در فیلترِ اولویت (R-PAT-6) همیشه حذف می‌شد. خانواده در منبع کلاسیک AMBIGUOUS است. | `tier2.threePeaksToleranceAtr=0.5` · `hs.maxBars=120` | سه سقفِ هم‌سطحِ نزولی با دو کفِ میانی | `classic` (Bulkowski، Encyclopedia of Chart Patterns) · پیاده‌سازی: A3 · بازبینی: A4 (R-PA-13) |

## جمع رده‌ها

| Tier | Count | Kinds |
|---|---|---|
| 1 | 19 | `DOUBLE_TOP`، `DOUBLE_BOTTOM`، `HEAD_SHOULDERS`، `INVERSE_HEAD_SHOULDERS`، `TRIPLE_TOP`، `TRIPLE_BOTTOM`، `FLAG_BULL`، `FLAG_BEAR`، `PENNANT`، `TRIANGLE_ASC`، `TRIANGLE_DESC`، `TRIANGLE_SYM`، `RECTANGLE`، `WEDGE_RISING`، `WEDGE_FALLING`، `CUP_HANDLE`، `INVERSE_CUP_HANDLE`، `ROUNDING_TOP`، `ROUNDING_BOTTOM` |
| 2 | 7 | `DIAMOND_TOP`، `DIAMOND_BOTTOM`، `BROADENING_TOP`، `BROADENING_BOTTOM`، `ISLAND_REVERSAL`، `THREE_RISING_PEAKS`، `THREE_FALLING_PEAKS` |
