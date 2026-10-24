# استفادهٔ واقعی از CandleEdge در سیگنال‌های تکنیکال — ممیزی، انتقال و آزمون

**تاریخ:** ۱۴۰۵-۰۸-۰۳ / 2026-10-25
**مخزن:** `johnwarchief/BorsTerminal-src`
**مبنا:** `036cdfa917555d58530e8c79c52d7ae07e0a750f` (همان SHA جاری `github/main` در شروع مأموریت)
**شاخه:** `mission/technical-signals-candleedge-reuse-2026-10-25`
**کامیت کد نهایی:** `1ae91717adf54ec269b352b8661c8c79cda724b9`
**worktree:** `C:\Users\PCMOD\Desktop\BorsTerminal-signals-CE-2026-10-25`

---

## ۰) حکم کوتاه

| پرسش | پاسخ | شاهد |
|---|---|---|
| آیا کد واقعی متن‌باز منتقل شد؟ | بله؛ ۲۰ تابع تشخیصی و ۸ تابع پشتیبان از `src/script.js` | بخش ۳ و `THIRD_PARTY-NOTICE.md` |
| آیا ماژول مستقل و تست‌پذیر است؟ | بله؛ `frontend/src/features/technical/signals/candleedge` با صفر وابستگی npm | بخش ۱۰ |
| آیا look-ahead مدیریت شده؟ | بله؛ هر رویداد `confirmedAtIndex` دارد و provisional از confirmed جداست | بخش ۴ |
| آیا روی کندل تعدیل‌شده کار می‌کند؟ | ورودی خالص OHLC + تست با تابع تعدیل تولیدی؛ اتصال UI `NOT_MEASURED` | بخش ۹ |
| آیا FTS، تعدیل یا چارت تغییر کرد؟ | نه؛ هیچ فایل ممنوعه‌ای ویرایش نشد | بخش ۱ |
| مجوز رعایت شد؟ | بله؛ MIT با copyright و commit منبع | `LICENSE-CANDLEEDGE` |
| آیا آمادهٔ «سیگنال رسمی» است؟ | نه؛ ماژول تحقیق/کشف الگوست و به FTS یا UI وصل نشده | بخش ۱۱ و ۱۲ |

---

## ۱) مبنا، شاخه و مرز مالکیت

- SHA جاری `github/main` پیش از شروع دوباره با `git ls-remote` خوانده شد و همان `036cdfa9…` بود.
- شاخهٔ اختصاصی و worktree جدا ساخته شد؛ `main` تغییر نکرد و merge نشد.
- فایل‌های ممنوعهٔ این مأموریت دست‌نخورده‌اند: `adjustment_engine.py`، `api/chart.py`، `candle_contract.py`،
  `nahayatnegar/lib/adjustments.ts`، `signals/technicalSignals.ts`، `ftsPipelineEvaluator.ts`،
  `KLineChartWrapper.tsx` و `shared/api/http.ts`.
- دو مسیر در دستور مأموریت با مسیر واقعی مخزن فرق داشت و بدون تغییر رها شدند:
  - `frontend/src/features/technical/lib/adjustments.ts` وجود ندارد؛ مسیر تولیدی
    `frontend/src/features/technical/nahayatnegar/lib/adjustments.ts` است و فقط import شد.
  - `frontend/src/features/technical/lib/technicalSignals.ts` وجود ندارد؛ فایل واقعی
    `frontend/src/features/technical/signals/technicalSignals.ts` است و دست‌نخورده ماند.
- هیچ وابستگی npm اضافه نشد؛ ماژول جدید هیچ import بیرونی ندارد.

---

## ۲) CandleEdge: هویت، مجوز و آنچه منتقل شد

| مورد | مقدار |
|---|---|
| مخزن | `https://github.com/michaelsboost/CandleEdge` |
| commit بررسی‌شده | `75761e26b23ccaf59b31365e1ec817374673d77b` (2026-05-25) |
| مجوز | MIT — Copyright (c) 2026 Michael Schwartz |
| فایل تحلیلی | `src/script.js` — ۱٬۵۴۷ خط |
| ساختار | اسکنر مرورگری ساختار بازار و الگو با آمار توصیفی روی دادهٔ بارگذاری‌شده |
| وابستگی تحلیلی | ندارد؛ توابع تشخیصی JavaScript خالص‌اند |
| آنچه کپی نشد | HTML، CSS/Tailwind، Alpine.js، websocket، lightweight-charts، PapaParse، service worker، CSV، تصاویر، `dist/` |

فایل مجوز کامل: `frontend/src/features/technical/signals/candleedge/LICENSE-CANDLEEDGE`
فهرست توابع و خطوط منبع: `frontend/src/features/technical/signals/candleedge/THIRD_PARTY-NOTICE.md`

### ۲.۱ بررسی قابلیت‌های فهرست‌شده در دستور

| قابلیت | در CandleEdge هست؟ | محل | تصمیم |
|---|---|---|---|
| Engulfing، Hammer، Shooting Star، Doji | بله | `script.js:171-257` | هر پنج مورد منتقل شد |
| Double Top/Bottom | بله | `script.js:579-638` | منتقل شد |
| Triangle و Wedge | بله | `script.js:461-525` | پنج تشخیص منتقل شد |
| Higher High/Lower Low | بله | `script.js:967-1001` | چهار رابطه منتقل شد |
| Break of Structure | بله، اما شاخهٔ مرده | `script.js:929-947` | با آداپتور مستند اصلاح شد |
| Liquidity Sweep | بله، با خطای off-by-one | `script.js:949-965` | با آداپتور مستند اصلاح شد |
| Swing High/Low | بله | `script.js:409-436` | منتقل شد |
| اعتبارسنجی هندسه | جزئی | pullback/bounce و شیب | همان قواعد حفظ شد؛ کمبود آن مستند شد |
| آمار رفتار تاریخی | بله | `script.js:12-109` | بررسی شد، منتقل نشد |

الگوهای بیشتری در منبع هست (Morning Star، Harami، Kicker، Marubozu، Cup and Handle،
Head and Shoulders و…) که عمداً منتقل نشدند: خارج از حداقل درخواستی، بخشی بدون
اعتبارسنجی کافی، و افزودنشان بدون تست مرزی، سطح ریسک را بالا می‌برد.

---

## ۳) توابع منتقل‌شده و پارامترها

### ۳.۱ توابع تشخیصی (۲۰ شناسهٔ رویداد)

| گروه | تابع منبع | خطوط | فایل BorsTerminal | تغییر |
|---|---|---|---|---|
| کندلی | `isDoji` | 171-174 | `candlePatterns.ts` | تایپ و نگهبان مرز |
| کندلی | `isBullishEngulfing` | 197-202 | `candlePatterns.ts` | تایپ و نگهبان مرز |
| کندلی | `isBearishEngulfing` | 203-207 | `candlePatterns.ts` | تایپ و نگهبان مرز |
| کندلی | `isHammer` | 227-233 | `candlePatterns.ts` | پارامتر `trendPeriod` |
| کندلی | `isShootingStar` | 251-257 | `candlePatterns.ts` | پارامتر `trendPeriod` |
| ساختار | `detectAscendingTriangle` | 461-473 | `structurePatterns.ts` | شناسه/بایاس به‌جای نام/آیکن |
| ساختار | `detectDescendingTriangle` | 475-487 | `structurePatterns.ts` | همان |
| ساختار | `detectSymmetricalTriangle` | 489-501 | `structurePatterns.ts` | همان |
| ساختار | `detectRisingWedge` | 503-513 | `structurePatterns.ts` | همان |
| ساختار | `detectFallingWedge` | 515-525 | `structurePatterns.ts` | همان |
| دوقلو | `detectDoubleTop` | 579-609 | `structurePatterns.ts` | بهترین جفت، حذف تکرار |
| دوقلو | `detectDoubleBottom` | 611-638 | `structurePatterns.ts` | بهترین جفت، حذف تکرار |
| ساختار بازار | `detectHigherHigh` | 967-974 | `structurePatterns.ts` | تایپ |
| ساختار بازار | `detectLowerLow` | 976-983 | `structurePatterns.ts` | تایپ |
| ساختار بازار | `detectHigherLow` | 985-992 | `structurePatterns.ts` | تایپ |
| ساختار بازار | `detectLowerHigh` | 994-1001 | `structurePatterns.ts` | تایپ |
| ساختار بازار | `detectBOSBullish` | 929-937 | `structurePatterns.ts` | آداپتور زمان تأیید و آستانهٔ نسبی |
| ساختار بازار | `detectBOSBearish` | 939-947 | `structurePatterns.ts` | همان |
| نقدینگی | `detectLiquiditySweepHigh` | 949-956 | `structurePatterns.ts` | آخرین سطح تأییدشده |
| نقدینگی | `detectLiquiditySweepLow` | 958-965 | `structurePatterns.ts` | آخرین سطح تأییدشده |

### ۳.۲ توابع پشتیبان (۸ مورد) و یک آداپتور جدید

| تابع | خطوط منبع | نقش |
|---|---|---|
| `candleParts` | 149-155 | body/range/upper/lower |
| `isUptrend` | 115-118 | روند ۲۰ کندلی بر مبنای close |
| `isDowntrend` | 120-123 | همان، نزولی |
| `findSwingPoints` | 409-422 | پیوت با پنجرهٔ دوطرفه |
| `findLocalExtrema` | 424-436 | اکسترمم ۵ کندلی برای دوقلوها |
| `percentSlope` | 442-446 | شیب درصدی خط روند |
| `hasValidPullbackBetweenPeaks` | 558-566 | پولبک بیش از ۱٪ بین دو سقف |
| `hasValidBounceBetweenTroughs` | 568-576 | جهش بیش از ۱٪ بین دو کف |
| `findProvisionalSwings` | — | آداپتور جدید برای اکسترمم‌های تأییدنشدهٔ انتهای سری |

### ۳.۳ پارامترها — همه از CandleEdge، هیچ‌کدام قاعدهٔ FTS نیست

| پارامتر | مقدار | جای استفاده |
|---|---|---|
| Doji | body ≤ ۱۲٪ range | `isDoji` |
| Hammer | lower wick > ۲×body، upper wick < ۰٫۵×body، روند نزولی ۲۰ کندلی | `isHammer` |
| Shooting Star | آینهٔ Hammer با روند صعودی | `isShootingStar` |
| پنجرهٔ پیوت | ۳ کندل چپ و راست، نابرابری اکید | `findSwingPoints` |
| lookback اکسترمم | ۵ کندل | `findLocalExtrema` |
| آستانهٔ خطوط | ۰٫۰۳٪ بر کندل برای «تخت» و «روند» | مثلث‌ها و گوه‌ها |
| Double Top/Bottom | اختلاف قیمت ≤ ۴٪، فاصله ≥ ۵ کندل، پولبک/جهش > ۱٪ | دوقلوها |
| پنجرهٔ تازگی دوقلو | ۱۵ کندل در تابع مستقیم؛ ۲۰ کندل در orchestrator منبع | دوقلوها |
| BOS | تغییر نسبی > ۰٫۵٪ | BOS |
| کف ساختار | فقط `index > 40` | کل ساختار نموداری/بازار |
| پنجرهٔ ساختار | ۲۰۰ کندل اخیر | سوئینگ‌ها و اکسترمم‌های ساختار |

> این اعداد پارامترهای CandleEdge هستند. نه قاعدهٔ جزوهٔ FTS‌اند، نه آستانهٔ پذیرفته‌شدهٔ
> BorsTerminal، و نه احتمال موفقیت. استفاده از آن‌ها در سیگنال رسمی نیازمند رأی مالک است.

---

## ۴) مدل زمانی و ضد look-ahead

### ۴.۱ تعریف‌ها

- **کندل تشکیل‌دهنده:** کندلی که شواهد الگو در آن دیده می‌شود.
- **کندل تأیید:** کندلی که با بسته‌شدنش، شاهد کافی برای قطعی‌شدن الگو کامل می‌شود.
- **زمان تأیید:** `candles[confirmedAtIndex].time` — هرگز زمان کندل تشکیل نیست، مگر الگویی که همان کندل کافی است.
- **ابطال:** این ماژول برای رویدادهای تأییدشده «ابطال گذشته» ندارد. رویداد مخالف می‌تواند بعداً بیاید، اما رویداد قبلی بازنویسی نمی‌شود.

### ۴.۲ زمان‌بندی هر خانواده

| خانواده | شاهد تشکیل | زمان تأیید | پس از تأیید |
|---|---|---|---|
| Doji | کندل i | همان i | تغییر نمی‌کند |
| Engulfing | کندل i-1 و i | همان i | تغییر نمی‌کند |
| Hammer/Shooting Star | شکل کندل i + روند ۲۰ کندلی | همان i | تغییر نمی‌کند |
| Swing High/Low | پیوت i با پنجرهٔ w دوطرفه | i + w | پیوت تأییدشده بازتعریف نمی‌شود |
| Higher High/Lower Low و مشابه | دو پیوت تأییدشدهٔ آخر | تأیید پیوت دوم | رابطه بازنویسی نمی‌شود |
| BOS | پیوت جدید > پیوت قبلی با ۰٫۵٪ | تأیید پیوت جدید | سطح شکسته‌شده ثابت می‌ماند |
| Liquidity Sweep | کندل j سطح آخرین پیوت تأییدشده را می‌شکند و داخل برمی‌گردد | همان j | رویداد j ثابت می‌ماند |
| Triangle/Wedge | دو سقف و دو کف تأییدشدهٔ آخر | تأیید آخرین پیوت از چهار پیوت | فقط هندسهٔ کاندید؛ شکست خط تأیید نشده |
| Double Top/Bottom | دو اکسترمم تأییدشده با شرایط قیمت/فاصله/پولبک | تأیید اکسترمم دوم | یک بار منتشر می‌شود؛ خط گردن محاسبه نمی‌شود |

### ۴.۳ تضمین‌ها و آزمون‌ها

- هیچ رویدادی پیش از `confirmedAtIndex` در خروجی نیست و همهٔ anchorها `index ≤ confirmedAtIndex` دارند.
- اجرای اسکن روی پیشوند `candles[0..L)` همان رویدادهای `confirmedAtIndex < L` اجرای کامل را می‌دهد.
- افزودن ۱۲۰ کندل آیندهٔ صعودی، رویداد `double_top@60` را بایت‌به‌بایت تغییر نمی‌دهد.
- الگوی کندلی در همان کندل ظاهر می‌شود و یک کندل قبل‌تر نه.
- اکسترمم انتهای سری فقط `provisional` است، `confirmedAtIndex: null` دارد و هرگز در `events` نمی‌آید.
- اسکن روی random walk ۴۰۰ کندلی، پایداری پیشوند را در سه طول مختلف نگه می‌دارد.
- ورودی «کندل در حال تشکیل» توسط ماژول قابل تشخیص نیست؛ قرارداد مصرف‌کننده این است که فقط کندل بسته بدهد.

آزمون‌ها: `__tests__/noLookAhead.spec.ts` و بخش scanner در `__tests__/scanner.spec.ts`.

---

## ۵) آداپتورها و تفاوت‌های عمدی با منبع

| # | موضوع | رفتار منبع | رفتار ماژول | دلیل |
|---|---|---|---|---|
| ۱ | BOS | شرط `recentHigh.index === idx` هرگز درست نمی‌شود؛ BOS عملاً صفر رویداد | تأیید در کندل تأیید پیوت جدید | شاخهٔ مرده را زنده کردیم؛ رفتار زمانی صریح شد |
| ۲ | آستانهٔ BOS | ضرب در `1 ± 0.005`؛ مرز دقیق به‌خاطر IEEE-754 یک‌طرفه می‌شود | تغییر نسبی > ۰٫۰۰۵ | مرز ۰٫۵٪ در دو جهت متقارن شد |
| ۳ | Liquidity Sweep | `swings.highs[length-2]` یعنی سطح یکی‌مانده‌به‌آخر | آخرین پیوت تأییدشده | سطح تازه‌تر که همان‌جا آزموده می‌شود نادیده می‌ماند |
| ۴ | دوقلوها | هر کندل داخل پنجرهٔ ۲۰ کندلی دوباره گزارش می‌شود | یک بار در کندل تأیید اکسترمم دوم | حذف رویداد تکراری |
| ۵ | نام و آیکن | `name`/`icon`/متن وضعیت انگلیسی | `detector`/`family`/`bias` | جداکردن تحلیل از متن رابط |
| ۶ | پیوت‌های برابر | نابرابری اکید؛ سقف مساوی پیوت نیست | همان | حفظ رفتار منبع؛ در تست قفل شد |
| ۷ | `range = high-low` با جایگزین یک در صورت صفر | کندل تخت، range=۱ واحد پول | همان | رفتار منبع حفظ شد؛ اثر مقیاس قیمت مستند است |
| ۸ | کف ۴۱ کندل | ساختار فقط `idx > 40` | همان | جلوگیری از تشخیص زودهنگام |
| ۹ | پنجرهٔ ۲۰۰ کندل | سوئینگ/اکسترمم فقط ۲۰۰ کندل اخیر | همان | نزدیک‌ترین رفتار به منبع |
| ۱۰ | provisional | ندارد | اسکن انتهای سری، جدا از رویداد | نیاز صریح مأموریت |

**تفاوت باقی‌مانده:** سوئینگ‌ها روی کل سری محاسبه و بعد به پنجرهٔ ۲۰۰ کندلی فیلتر می‌شوند،
در حالی که منبع همان پنجره را از نو اسکن می‌کند. بنابراین یک پیوت در فاصلهٔ یک پنجرهٔ
سوئینگ از لبهٔ چپ پنجره می‌تواند متفاوت باشد. این اثر در استفادهٔ عملی (پیوت‌های آخر)
ناچیز است، اما صریح ثبت می‌شود.

---

## ۶) اشکال‌هایی که در منبع پیدا شد

| # | اشکال | شاهد | اثر | تصمیم |
|---|---|---|---|---|
| D1 | BOS هرگز فعال نمی‌شود | `script.js:1077-1078` پنجره را تا `idx` می‌برد؛ `findSwingPoints` حداکثر `idx-3` را می‌دهد (`:411`)؛ شرط `recentHigh.index === idx` (`:933`, `:943`) | تشخیص BOS مرده است | آداپتور + تست |
| D2 | Sweep سطح یکی‌مانده‌به‌آخر را می‌سنجد | `script.js:951`, `:960` | سطح تازه نادیده می‌ماند | آداپتور + تست |
| D3 | دوقلوها تا ۲۰ کندل تکرار می‌شوند | `script.js:1109-1110` + `isRecentlyConfirmed` | رویداد تکراری | یک‌بار در تأیید |
| D4 | مرز BOS نامتقارن | ضرب اعشاری `price * 1.005` | ۱۰۰٫۵ در سمت صعودی رد نمی‌شود | مقایسهٔ نسبی |
| D5 | `range` با جایگزین یک | `script.js:151` | Doji در کندل تخت به مقیاس قیمت وابسته است | حفظ و مستندسازی |
| D6 | مثلث/گوه بدون اعتبارسنجی هم‌پوشانی زمانی | `script.js:461-525` | دو خط ممکن است بازهٔ مشترک نداشته باشند | قاعدهٔ جدید اختراع نشد |
| D7 | آمار روی همان داده انتخاب و ارزیابی می‌شود | `script.js:80-89` | انتخاب بهترین افق، در-sample | منتقل نشد |
| D8 | کش آمار با تغییر دادهٔ میانی کهنه می‌ماند | `script.js:20`, `:51` | امضای داده فقط طول و اولین/آخرین زمان است | منتقل نشد |
| D9 | اسکن آمار ۲۰ کندل آخر را کنار می‌گذارد | `script.js:32` | نمونهٔ انتهایی وارد آمار نمی‌شود | منتقل نشد |

---

## ۷) موتور آمار CandleEdge: بررسی و تصمیم

`StatsEngine.computePatternStats` بررسی شد و **منتقل نشد**. دلایل:

1. **انتخاب افق روی همان نمونه:** بهترین افق از میان `[3,5,10,20]` با `weighted` انتخاب
   می‌شود (`script.js:80-89`) و همان forward returnها برای گزارش استفاده می‌شوند؛
   هیچ holdout یا تفکیک discovery/evaluation وجود ندارد.
2. **احتمال بدون هزینه:** بازده close-to-close است؛ کارمزد، اسلیپیج، نقدشوندگی و
   محدودیت حجم لحاظ نمی‌شود.
3. **تعریف احتمال ناقص:** حرکات صفر در هیچ‌کدام از شمارش‌ها نیستند اما در مخرج
   `sampleSize` هستند (`:75-77`).
4. **برچسب اطمینان بدون معنی آماری:** High فقط با `n ≥ 30` (`:94-96`)، بدون فاصلهٔ اطمینان.
5. **کش ناامن:** کلید فقط طول و اولین/آخرین زمان است (`:20`, `:51`)؛ تغییر دادهٔ میانی
   کش کهنه را برمی‌گرداند.
6. **پوشش نمونه گزارش نمی‌شود:** تعداد نماد، بازهٔ زمانی، رژیم بازار و نرخ پایه ثبت نمی‌شود.

اگر در آینده لازم شد، مسیر قابل‌دفاع این است: افق پیش از دیدن نتیجه تثبیت شود،
دورهٔ discovery و evaluation جدا باشد، هزینه و نقدشوندگی ثبت شود، تعداد نمونه و
پوشش نمادها گزارش شود، و هیچ عددی به‌عنوان «احتمال موفقیت» یا توصیهٔ معاملاتی نمایش داده نشود.
هیچ آستانهٔ تازه‌ای در این مأموریت اختراع نشد.

---

## ۸) مقایسهٔ گزینه‌های کتابخانه‌ای

| کتابخانه | مجوز | زبان/محیط | پوشش | به‌روزرسانی افزایشی | وابستگی | تصمیم |
|---|---|---|---|---|---|---|
| CandleEdge (commit `75761e2`) | MIT | JavaScript خالص | کندلی + ساختار نموداری + بازار + آمار توصیفی | ندارد؛ توابع batch | صفر برای تحلیل | انتخاب و انتقال گزینشی |
| technicalindicators `3.1.0` | MIT | JavaScript/TypeScript | اندیکاتورها + الگوهای کندلی محدود؛ بدون مثلث/BOS/دوقلو | `nextValue` دارد | `@types/node` | استفاده نشد |
| Hexital | MIT | Python | ۴۰+ اندیکاتور و الگوهای پایه (Doji، Hammer) | افزایشی و streaming | صفر | استفاده نشد |

- اطلاعات technicalindicators از npm registry و README همان نسخه؛ Hexital از GitHub API و README.
- **هیچ‌کدام از این دو نصب یا benchmark نشدند**؛ ادعای عملکرد یا پوشش دقیق‌تر از مستنداتشان
  در اینجا `NOT_MEASURED` است.
- دلیل نپذیرفتن technicalindicators: پوشش ساختاری لازم (BOS، مثلث، گوه، دوقلو، sweep) را ندارد
  و برای زیرمجموعه‌ای که دارد، افزودن وابستگی و کد چسبانده‌شده توجیه کافی نداشت.
- دلیل نپذیرفتن Hexital: Python است و در باندل TypeScript بدون پل Python یا بازنویسی
  قابل استفاده نیست؛ این کار مرز محاسبه را دوگانه و آزمون‌پذیری را بدتر می‌کرد.

---

## ۹) ورودی تعدیل‌شده و حالت خام

- ماژول فقط `Candle` با OHLC می‌گیرد و هیچ منطق تعدیلی ندارد؛ `open/high/low/close` همه مصرف می‌شوند.
- تست `adjustedInput.spec.ts` فیکسچر ۸۰ کندلی می‌سازد: قبل از رویداد ضریب ۰٫۵، بعد از آن ۱.
  - خام: سقف ۲۰۰ در برابر ۱۰۲ ⇒ اختلاف ۴۹٪ ⇒ Double Top ندارد.
  - تعدیل‌شده: سقف ۱۰۰ در برابر ۱۰۲ ⇒ اختلاف ۲٪ ⇒ Double Top در کندل ۶۰ دارد.
  - `high` و `low` تعدیل‌شده صریحاً بررسی می‌شوند؛ اگر فقط close تعدیل می‌شد، این رویداد پیدا نمی‌شد.
- تنظیم از `applyAdjustmentToCandles` در
  `frontend/src/features/technical/nahayatnegar/lib/adjustments.ts` گرفته می‌شود؛
  همان تابع تولیدی، بدون بازنویسی.
- حالت خام حذف نشد: فیکسچر خام بدون خطا اسکن می‌شود و الگوی کندلی خودش را دارد.
- **اتصال انتهابه‌انتها `NOT_MEASURED`:** ماژول به `KLineChartWrapper`، پنل سیگنال،
  `TechnicalPage` یا API وصل نشده است. سری تعدیل‌شدهٔ واقعی صفحه و رفتار تغییر نماد/تایم‌فریم
  تا زمانی که مالک آن بخش اتصال را نسازد، سنجیده نشده است.

---

## ۱۰) آزمون‌ها، نتایج و عملکرد

### ۱۰.۱ فرمان و نتیجه

```bash
cd frontend
CI=1 node node_modules/vitest/vitest.mjs run \
  src/features/technical/signals/candleedge/__tests__ --reporter=dot
```

- **۸ فایل تست، ۷۷ تست، ۷۷ سبز، ۰ قرمز.**
- `tsc` محدود به ماژول: **۰ خطا**.
- `eslint` روی ماژول: **۰ خطا**.
- `tsc -b` کامل به‌خاطر نبود `jev-ui` در `node_modules` قرض‌گرفته‌شده شکست می‌خورد؛
  این خطای محیطی است و در فایل‌های ماژول هیچ خطایی چاپ نشد (`grep candleedge` خروجی صفر).

### ۱۰.۲ Performance (اطلاعاتی، ورودی تکرارپذیر)

| مورد | مقدار |
|---|---|
| ورودی | random walk قطعی، ۲۰٬۰۰۰ کندل |
| تکرار | ۳ اجرای کامل |
| زمان | ۹۴٫۹ / ۶۳٫۳ / ۷۱٫۸ میلی‌ثانیه |
| رویداد | ۲۱٬۷۵۴ در هر سه اجرا (خروجی پایدار) |

توزیع رویدادها در همان اجرا: doji ۳٬۶۳۱، bullish engulfing ۲٬۵۲۷، bearish engulfing ۲٬۵۰۰،
liquidity sweep high ۲٬۲۸۳، sweep low ۲٬۱۰۴، double bottom ۱٬۰۱۰، double top ۹۷۷،
higher low ۹۴۱، higher high ۹۲۵، lower high ۸۶۸، lower low ۸۶۴، rising wedge ۶۵۸،
bos bullish ۵۶۵، falling wedge ۵۶۳، bos bearish ۵۱۷، ascending triangle ۲۹۶،
descending triangle ۲۸۹، symmetrical triangle ۲۳۶.

> حجم ۲۱٬۷۵۴ رویداد روی ۲۰٬۰۰۰ کندل یعنی این ماژول **فیلتر سالینس ندارد**.
> این عدد خروجی یک random walk مصنوعی است و نرخ واقعی نمادهای بازار نیست. پیش از
> نمایش در UI، لایهٔ انتخاب/ادغام/اولویت لازم است؛ این تصمیم محصولی است، نه بخشی از detector.

### ۱۰.۳ پوشش سناریوها

| گروه | مثبت | منفی | مرزی |
|---|---|---|---|
| Doji | body = ۱۲٪ | body > ۱۲٪ | range صفر و آستانهٔ inclusive |
| Engulfing (دو جهت) | پوشش کامل | بدنهٔ کوتاه/رنگ مخالف | تساوی دقیق open/close |
| Hammer/Shooting Star | شکل + روند درست | روند مخالف/کمبود تاریخچه | wick دقیقاً ۲×body |
| Swing/Extremum | پیوت اکید | سقف مساوی | پیوت تأییدنشده و provisional |
| Triangle/Wedge | پنج تشخیص | شیب ناسازگار | شیب مساوی و خطوط هم‌جهت |
| Double Top/Bottom | جفت معتبر | اختلاف > ۴٪/جهش ضعیف | مرز ۴٪، فاصلهٔ ۵، پولبک ۱٪، تازگی ۱۵ |
| HH/HL/LH/LL | رابطهٔ درست | قیمت مساوی | — |
| BOS | عبور > ۰٫۵٪ | پیش از تأیید پیوت | دقیقاً ۰٫۵٪ در دو جهت |
| Sweep | شکست و بازگشت | close بیرون/فقط لمس | high مساوی سطح و پیوت تأییدنشده |

### ۱۰.۴ ابزار تست

`node_modules` به‌صورت junction موقت از checkout دیگر استفاده شد. نسخهٔ `vitest` ۳٫۲٫۷،
`typescript` ۵٫۹٫۳ و `jsdom` ۳۰٫۰٫۱ دقیقاً با lock همین مبنا یکی است. تنها تفاوت
`package.json` دو checkout، نسخهٔ اپ و `jev-ui` است که هیچ تست این ماژول آن را import نمی‌کند.
junction پس از پایان تست‌ها حذف می‌شود و در Git نمی‌آید.

---

## ۱۱) ماتریس پذیرش این مأموریت

| ID | معیار | وضعیت | شاهد |
|---|---|---|---|
| CE-01 | کد تحلیلی واقعی از CandleEdge منتقل شد | `PASS` | ۲۰ detector + ۸ helper |
| CE-02 | commit و مجوز و copyright ثبت شد | `PASS` | `THIRD_PARTY-NOTICE.md`, `LICENSE-CANDLEEDGE` |
| CE-03 | پروژهٔ کامل/CSS/HTML/کتابخانهٔ نمودار کپی نشد | `PASS` | فقط فایل‌های تحلیلی |
| CE-04 | ماژول مستقل و بدون وابستگی npm | `PASS` | import بیرونی صفر |
| CE-05 | زمان تشکیل/تأیید/ابطال مستند و آزموده شد | `PASS` | بخش ۴ + `noLookAhead.spec.ts` |
| CE-06 | provisional از confirmed جدا شد | `PASS` | `provisionalSwings` + تست |
| CE-07 | افزودن آینده رویداد تأییدشده را بازنویسی نمی‌کند | `PASS` | تست appending future |
| CE-08 | ورودی تعدیل‌شده از مسیر تولیدی | `PASS` | `adjustedInput.spec.ts` |
| CE-09 | حالت خام حفظ شد | `PASS` | همان فایل، تست raw |
| CE-10 | نمونهٔ مثبت/منفی/مرزی برای هر detector | `PASS` | ۷۷ تست |
| CE-11 | عملکرد روی حجم مشخص measured | `PASS` | ۲۰٬۰۰۰ کندل، ۳ اجرا |
| CE-12 | اتصال UI و دادهٔ زنده | `NOT_MEASURED` | ماژول فقط خالص |
| CE-13 | مقایسه با Rahavard | `NOT_MEASURED` | snapshot مرجع در دسترس نبود |
| CE-14 | تغییر FTS/تعدیل/چارت | `PASS` (بدون تغییر) | git diff فقط ماژول جدید |
| CE-15 | استفاده به‌عنوان سیگنال رسمی | `NOT_APPLICABLE` | ماژول تحقیق؛ نیازمند رأی مالک |

---

## ۱۲) محدودیت‌ها و موارد باز

- **بدون سالینس:** حجم رویداد بالا؛ نیاز به لایهٔ اولویت/ادغام پیش از UI.
- **بدون تأیید شکست:** مثلث/گوه فقط هندسهٔ کاندید است؛ شکست خط، بازگشت و حجم سنجیده نمی‌شود.
- **بدون آمار:** هیچ احتمال، نرخ موفقیت یا توصیهٔ معاملاتی تولید نمی‌شود.
- **بدون volume:** حجم در الگوها نقشی ندارد؛ تنها OHLC مصرف می‌شود.
- **بدون تایم‌فریم چندگانه:** ورودی یک سری است؛ تجمیع هفتگی/ماهانه وظیفهٔ مصرف‌کننده است.
- **بدون کندل در حال تشکیل:** قرارداد مصرف‌کننده «فقط کندل بسته» است؛ ماژول نمی‌تواند آن را تشخیص دهد.
- **پارامترها مال CandleEdge‌اند:** هر تغییری در آستانه‌ها یا استفادهٔ رسمی نیازمند رأی مالک است.
- **عملکرد فقط روی دادهٔ مصنوعی:** دادهٔ واقعی، حافظه و بار هم‌زمان `NOT_MEASURED`.
- **بدون اتصال:** `KLineChartWrapper`، صفحهٔ تکنیکال، پنل سیگنال و FTS دست نخوردند.

---

## ۱۳) اشکال‌های خارج از دامنه

| # | مورد | مسیر | چرا در این مأموریت اصلاح نشد |
|---|---|---|---|
| O1 | BOS منبع هرگز فعال نمی‌شد | `CandleEdge src/script.js:929-947` | منبع بیرونی است؛ در نسخهٔ منتقل‌شده اصلاح و مستند شد، upstream تغییر نکرد |
| O2 | Sweep منبع سطح آخر را جا می‌اندازد | `CandleEdge src/script.js:949-965` | همان؛ آداپتور مستند شد |
| O3 | آمار in-sample و بدون هزینه | `CandleEdge src/script.js:12-109` | نیاز به پروتکل discovery/evaluation و رأی مالک؛ منتقل نشد |
| O4 | مثلث/گوه بدون هم‌پوشانی زمانی | `CandleEdge src/script.js:461-525` | افزودن قاعدهٔ هندسی تازه، اختراع معیار است؛ فقط مستند شد |
| O5 | سیگنال‌های رسمی هنوز از FTS می‌آیند | `frontend/src/features/technical/signals/technicalSignals.ts` | فایل ممنوعه؛ اتصال این ماژول به سیگنال رسمی نیازمند رأی مالک |
| O6 | هیچ مصرف‌کنندهٔ UI برای ماژول نیست | `KLineChartWrapper.tsx`, `TechnicalPage.tsx` | فایل‌های ممنوعه و خارج از دامنه؛ `NOT_MEASURED` |
| O7 | `tsc -b` کامل به‌خاطر `jev-ui` شکست می‌خورد | `frontend/node_modules` قرضی | محیط تست، نه کد این مأموریت؛ `tsc` محدود صفر خطا داد |

---

## ۱۴) پیوست: فایل‌ها و فرمان‌ها

### ۱۴.۱ فایل‌های جدید

```
frontend/src/features/technical/signals/candleedge/
  types.ts
  validation.ts
  candleMath.ts
  candlePatterns.ts
  swings.ts
  structurePatterns.ts
  scanner.ts
  index.ts
  LICENSE-CANDLEEDGE
  THIRD_PARTY-NOTICE.md
  __tests__/
    helpers.ts
    validation.spec.ts
    candlePatterns.spec.ts
    swings.spec.ts
    structurePatterns.spec.ts
    scanner.spec.ts
    noLookAhead.spec.ts
    adjustedInput.spec.ts
    performance.spec.ts
```

### ۱۴.۲ فرمان‌های راستی‌آزمایی

```bash
# تست ماژول
cd frontend
CI=1 node node_modules/vitest/vitest.mjs run \
  src/features/technical/signals/candleedge/__tests__ --reporter=dot

# تایپ‌چک محدود (فایل موقت، سپس حذف)
node node_modules/typescript/bin/tsc -p tsconfig.candleedge.json --noEmit

# lint
node node_modules/eslint/bin/eslint.js \
  src/features/technical/signals/candleedge
```

### ۱۴.۳ منابع بیرونی بررسی‌شده

- CandleEdge: `https://github.com/michaelsboost/CandleEdge` در commit `75761e26b23ccaf59b31365e1ec817374673d77b`، مجوز MIT.
- technicalindicators: npm `technicalindicators@3.1.0` و README همان نسخه، مجوز MIT.
- Hexital: `https://github.com/MerlinR/Hexital` (API گیت‌هاب و README)، مجوز MIT، زبان Python.
