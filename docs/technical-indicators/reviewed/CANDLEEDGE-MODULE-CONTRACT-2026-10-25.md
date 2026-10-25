# قرارداد ماژول سیگنال‌های الگویی CandleEdge

**تاریخ:** 2026-10-25 (نسخهٔ دور ۲)
**وضعیت:** ماژول تحقیق/کشف الگو — نه سیگنال رسمی FTS، نه توصیهٔ معاملاتی
**مسیر:** `frontend/src/features/technical/signals/candleedge`
**مبنا:** `4a597278f4bf74c29430d2faa2f4ea01de7e37cc`
**منبع:** CandleEdge، کامیت `75761e26b23ccaf59b31365e1ec817374673d77b`، MIT

---

## ۱) هدف و مرز

این ماژول الگوهای کندلی و ساختاری را روی یک سری کندل **بسته و تعدیل‌شده** تشخیص می‌دهد
و برای هر رویداد، زمان تأیید و زمان قابل‌دانستن بودن شاهدها را صریح گزارش می‌کند.
کد تشخیص از CandleEdge (MIT) گرفته و به TypeScript منتقل شده است؛ جزئیات منبع و تفاوت‌ها در
`docs/technical-indicators/reviewed/CANDLEEDGE-REUSE-AUDIT-2026-10-25.md` و
`docs/technical-indicators/reviewed/CANDLEEDGE-REAL-MARKET-VALIDATION-2026-10-25.md` آمده است.

- جایگزین FTS نیست و هیچ رأی رسمی تولید نمی‌کند.
- هیچ منطق تعدیل، تجمیع تایم‌فریم، اندیکاتور یا رندر ندارد.
- هیچ وابستگی npm یا import بیرونی ندارد.
- پارامترها پارامترهای CandleEdge/پژوهش‌اند، نه قواعد جزوهٔ FTS.
- لایهٔ `research/` (آمار، سالینس، ارزیابی آینده‌نگر، هارنس واقعی) جدا از ماژول تشخیص است و
  رفتار `scanPatterns` را تغییر نمی‌دهد.

---

## ۲) ورودی

```ts
interface Candle {
  time: number | string;   // صعودی اکید
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;         // مصرف نمی‌شود
}
```

قواعد:

1. فقط کندل **بسته** بدهید. ماژول نمی‌تواند کندل در حال تشکیل را تشخیص دهد.
2. برای تحلیل روزمره، همان سری تعدیل‌شده‌ای را بدهید که چارت/پنل نمایش می‌دهد.
   تولید این سری وظیفهٔ `applyAdjustmentToCandles` است؛ ماژول دوباره تعدیل نمی‌کند.
3. هر چهار قیمت `open/high/low/close` مصرف می‌شوند؛ فقط close کافی نیست.
4. `time` باید اکیداً صعودی باشد؛ زمان تکراری یا نزولی پذیرفته نمی‌شود.
5. قیمت‌ها باید متناهی و مثبت باشند و `high ≥ max(open,close)` و `low ≤ min(open,close)`.

خطاها با `CandleEdgeInputError` و `index` و `reason` می‌آیند:
`candles-not-array`، `candle-not-object`، `time-invalid`، `ohlc-not-finite`،
`price-not-positive`، `high-below-body`، `low-above-body`، `time-type-mixed`،
`time-not-increasing`.

---

## ۳) خروجی

```ts
interface PatternAnchor {
  index: number;
  time: number | string;
  price: number;
  role: 'high' | 'low' | 'peak' | 'trough' | 'candle';
  confirmedAtIndex?: number;   // زمان قابل‌دانستن بودن لنگر
}

interface PatternEvent {
  key: string;                 // detector@confirmedAtIndex
  detector: DetectorId;        // ۲۰ شناسه
  family: 'candlestick' | 'chart_structure' | 'market_structure';
  bias: 'bullish' | 'bearish' | 'neutral';
  status: 'confirmed';         // رویداد فقط تأییدشده منتشر می‌شود
  confirmedAtIndex: number;    // کندلی که شاهد را کامل می‌کند
  confirmedAt: number | string;// time همان کندل
  startIndex: number;          // اولین anchor
  anchors: PatternAnchor[];    // همه با index ≤ confirmedAtIndex
  level?: number;              // سطح شکسته‌شده در BOS/Sweep
}

interface ScanResult {
  events: PatternEvent[];
  swings: { highs: SwingPoint[]; lows: SwingPoint[] };
  provisionalSwings: ProvisionalSwing[];
}
```

- `SwingPoint` شامل `index`، `price`، `time` و `confirmedAtIndex` است.
- `provisionalSwings` فقط اکسترمم‌های انتهای سری‌اند که پنجرهٔ راستشان کامل نیست؛
  `confirmedAtIndex: null` دارند و **نباید** مبنای اقدام قرار گیرند.
- ترتیب `events` بر اساس `confirmedAtIndex` سپس `detector` است؛ خروجی قطعی (deterministic) است.
- در رویدادهای ساختاری، لنگر سطح با ایندکس تأیید پیوت و لنگر کندل شکست/رویداد با ایندکس خودش
  ثبت می‌شود. لنگر سطح باید **پیش از** کندل رویداد تأیید شده باشد.

---

## ۴) زمان‌بندی تشخیص (نسخهٔ دور ۲)

| الگو | تشکیل | تأیید/اولین استفاده | نکته |
|---|---|---|---|
| Doji | کندل i | i | body/range ≤ ۱۲٪؛ دامنهٔ صفر رد می‌شود |
| Engulfing | i-1 و i | i | پوشش بدنه با مرز شامل؛ رنگ قبلی باید مخالف باشد |
| Hammer/Shooting Star | i | i | روند ۲۰ کندلی روی `i-1` (نه خود کندل الگو) + شکل کندل |
| Swing | پیوت i، پنجرهٔ ۳ | i+3 | پیوت‌های مساوی پذیرفته نمی‌شوند |
| اکسترمم دوقلو | پیوت i، پنجرهٔ ۵ | i+5 | مبنای دوقلوها |
| HH/HL/LH/LL | دو پیوت آخر | تأیید پیوت دوم | رابطهٔ قیمتی ساده؛ شکست نیست |
| BOS صعودی | close کندل j از آخرین سقف تأییدشده پیش از j عبور کند و close قبلی ≤ سطح باشد | j | رویداد در کندل شکست، نه تأیید پیوت؛ پیش‌فرض آستانه ۰ |
| BOS نزولی | آینهٔ مورد قبل با کف | j | همان |
| Sweep بالا | سایه از سطح سقفِ تأییدشده پیش از j عبور کند و close زیر سطح برگردد؛ close قبلی ≤ سطح | j | سطح باید پیش از j قابل دانستن باشد |
| Sweep پایین | آینهٔ مورد قبل با کف | j | همان |
| Triangle/Wedge | دو سقف و دو کف تأییدشده با هم‌پوشانی زمانی و خطوط غیرمتقاطع | تأیید آخرین پیوت | فقط هندسهٔ کاندید؛ بدون تأیید شکست |
| Double Top/Bottom | دو اکسترمم با اختلاف قیمت ≤۴٪، جدایی ≥۵ کندل، پولبک/جهش >۱٪ و بدون اکسترمم میانی ناقض | تأیید اکسترمم دوم | یک رویداد در هر تأیید؛ تکرار با لنگر اول مشترک ممکن است |

ساختار نموداری/بازار فقط پس از کندل ۴۱ و روی پنجرهٔ ۲۰۰ کندلی سنجیده می‌شود
(همان رفتار orchestrator منبع). BOS و Sweep در هر کندل بررسی می‌شوند؛ الگوهای خطی و دوقلو
هنگام تأیید پیوت مربوطه.

---

## ۵) استفاده

```ts
import { scanPatterns } from '@features/technical/signals/candleedge';

const result = scanPatterns(adjustedCandles);

for (const event of result.events) {
  // event.confirmedAtIndex زمان تصمیم است، نه event.startIndex
  // event.anchors[*].confirmedAtIndex زمان قابل‌دانستن بودن هر شاهد است
}
```

گزینه‌ها:

```ts
scanPatterns(candles, {
  swingWindow: 3,        // پیش‌فرض ۳
  extremumLookback: 5,   // پیش‌فرض ۵
  trendPeriod: 20,       // پیش‌فرض ۲۰
  bosThreshold: 0,       // پیش‌فرض پژوهش؛ 0.005 = آستانهٔ ۰٫۵٪ منبع
});
```

`bosThreshold` باید متناهی و ≥۰ باشد؛ مقدار منفی یا غیرعددی `RangeError` می‌دهد.
آستانه در هر دو جهت به‌صورت نسبی و متقارن مقایسه می‌شود.

---

## ۶) تضمین‌ها

1. **بدون look-ahead:** هیچ رویداد/پیوتی پیش از `confirmedAtIndex` دیده نمی‌شود و
   تمام anchorها `index ≤ confirmedAtIndex` دارند.
2. **سطحِ قابل‌دانستن:** در BOS/Sweep، لنگر سطح `index < confirmedAtIndex` و
   `confirmedAtIndex(سطح) < confirmedAtIndex(رویداد)` دارد.
3. **پایداری پیشوند:** اسکن `candles[0..L)` همان رویدادهای تأییدشدهٔ اجرای کامل را می‌دهد.
4. **عدم بازنویسی:** افزودن کندل آینده رویداد تأییدشدهٔ گذشته را تغییر نمی‌دهد.
5. **جدایی provisional:** اکسترمم تأییدنشده هرگز در `events` نمی‌آید.
6. **عدم تغییر ورودی:** ماژول آرایه و کندل‌ها را mutate نمی‌کند.
7. **قطعی‌بودن:** برای ورودی یکسان، خروجی یکسان است (بدون زمان، تصادف یا شبکه).
8. **اعتبارسنجی واقعی:** در ۲۱۰٬۴۹۴ خط دفتر رویداد، صفر نقض لنگر/زمان/سطح ثبت شد.

---

## ۷) غیراهداف

- تولید احتمال، نرخ موفقیت، امتیاز یا توصیهٔ معاملاتی.
- جایگزینی یا تغییر قواعد FTS، جزوه یا سیگنال رسمی.
- محاسبهٔ تعدیل، تجمیع هفتگی/ماهانه یا ساخت سری نمایش.
- رسم اورلی، اتصال به KLineCharts یا تغییر UI.
- Backtest سوددهی، انتخاب افق بهینه یا انتخاب پارامتر روی دادهٔ نهایی.
- تشخیص «کندل در حال تشکیل».

لایهٔ `research/` آمار و ارزیابی **تشخیصی** تولید می‌کند؛ خروجی آن نیز سیگنال رسمی نیست.

---

## ۸) شرایط اتصال بعدی

پیش از اتصال به UI یا سیگنال رسمی:

1. مصرف‌کننده باید همان سری تعدیل‌شدهٔ نمایش را بدهد و فقط کندل بسته.
2. برای هر نماد/تایم‌فریم، کلید کش باید شامل سری و تنظیمات باشد؛ خروجی این ماژول
   نباید با سری نماد قبلی ترکیب شود.
3. `provisionalSwings` نباید به‌عنوان سیگنال اقدام نمایش داده شود.
4. لایهٔ سالینس/ادغام لازم است: در ۲٬۳۱۶ سری واقعی، ۳۸٬۴۷۰ گروه چندرویدادی و ۸۱٬۴۶۷
   رویداد تک‌نفره تولید شد. قاعدهٔ فعلی: لنگر مشترک + فاصلهٔ تأیید ≤۵ کندل.
5. آستانه‌های BOS/Sweep و رفتار دوقلوهای تکراری تصمیم مالک است، نه پیش‌فرض پنهان.
6. هر استفاده در سیگنال رسمی یا نمایش «سیگنال معتبر» نیازمند رأی مالک است.
7. مقایسه با رهاورد تا دسترسی تازهٔ مجاز `NOT_MEASURED` بماند.

---

## ۹) آزمون

```bash
cd frontend
CI=1 node node_modules/vitest/vitest.mjs run \
  src/features/technical/signals/candleedge/__tests__ --reporter=dot
```

۹ فایل، ۹۱ تست: الگوهای مثبت/منفی/مرزی، پیوت‌ها، provisional، پایداری پیشوند،
افزودن آینده، ورودی تعدیل‌شده از مسیر تولیدی، حالت خام و benchmark ۲۰٬۰۰۰ کندل.

آزمون‌های لایهٔ پژوهش جداگانه‌اند:

```bash
CI=1 node node_modules/vitest/vitest.mjs run \
  src/features/technical/signals/candleedge/research/__tests__ --reporter=dot
```

هارنس واقعی با متغیرهای `CANDLEEDGE_NDJSON` و `CANDLEEDGE_OUT` اجرا می‌شود؛ بدون آن‌ها
تست سنگین skip می‌شود. جزئیات در گزارش اعتبارسنجی دور ۲.
