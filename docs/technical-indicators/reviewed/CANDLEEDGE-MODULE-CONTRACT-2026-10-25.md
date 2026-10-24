# قرارداد ماژول سیگنال‌های الگویی CandleEdge

**تاریخ:** ۱۴۰۵-۰۸-۰۳ / 2026-10-25
**وضعیت:** ماژول تحقیق/کشف الگو — نه سیگنال رسمی FTS، نه توصیهٔ معاملاتی
**مسیر:** `frontend/src/features/technical/signals/candleedge`
**مبنا:** `036cdfa917555d58530e8c79c52d7ae07e0a750f` · **کامیت کد:** `1ae91717adf54ec269b352b8661c8c79cda724b9`

---

## ۱) هدف و مرز

این ماژول الگوهای کندلی و ساختاری را روی یک سری کندل **بسته و تعدیل‌شده** تشخیص می‌دهد
و برای هر رویداد، زمان تأیید را صریح گزارش می‌کند. کد تشخیص از CandleEdge (MIT) گرفته شده
و به TypeScript منتقل شده است؛ جزئیات منبع و تفاوت‌ها در
`docs/technical-indicators/reviewed/CANDLEEDGE-REUSE-AUDIT-2026-10-25.md` آمده است.

- جایگزین FTS نیست و هیچ رأی رسمی تولید نمی‌کند.
- هیچ منطق تعدیل، تجمیع تایم‌فریم، اندیکاتور یا رندر ندارد.
- هیچ وابستگی npm یا import بیرونی ندارد.
- پارامترها پارامترهای CandleEdge هستند، نه قواعد جزوهٔ FTS.

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

---

## ۴) زمان‌بندی تشخیص

| الگو | تشکیل | تأیید | نکته |
|---|---|---|---|
| Doji | کندل i | i | body ≤ ۱۲٪ range |
| Engulfing | i-1 و i | i | تساوی مرزی پذیرفته می‌شود |
| Hammer/Shooting Star | i | i | روند ۲۰ کندلی + شکل کندل |
| Swing | پیوت i، پنجرهٔ ۳ | i+3 | پیوت‌های مساوی پذیرفته نمی‌شوند |
| HH/HL/LH/LL | دو پیوت آخر | تأیید پیوت دوم | رابطهٔ قیمتی ساده |
| BOS | پیوت جدید > قبلی با ۰٫۵٪ | تأیید پیوت جدید | مقایسهٔ نسبی |
| Sweep | کندل j سطح آخرین پیوت تأییدشده را می‌شکند و داخل برمی‌گردد | j | close باید داخل سطح باشد |
| Triangle/Wedge | دو سقف و دو کف تأییدشده | تأیید آخرین پیوت | فقط هندسهٔ کاندید؛ بدون تأیید شکست |
| Double Top/Bottom | دو اکسترمم با شرایط قیمت/فاصله/پولبک | تأیید اکسترمم دوم | یک بار منتشر می‌شود |

ساختار نموداری/بازار فقط پس از کندل ۴۱ و روی پنجرهٔ ۲۰۰ کندلی سنجیده می‌شود
(همان رفتار orchestrator منبع).

---

## ۵) استفاده

```ts
import { scanPatterns } from '@features/technical/signals/candleedge';

const result = scanPatterns(adjustedCandles);

for (const event of result.events) {
  // event.confirmedAtIndex زمان تصمیم است، نه event.startIndex
}
```

گزینه‌ها:

```ts
scanPatterns(candles, {
  swingWindow: 3,        // پیش‌فرض ۳
  extremumLookback: 5,   // پیش‌فرض ۵
  trendPeriod: 20,       // پیش‌فرض ۲۰
});
```

---

## ۶) تضمین‌ها

1. **بدون look-ahead:** هیچ رویداد/پیوتی پیش از `confirmedAtIndex` دیده نمی‌شود و
   تمام anchorها `index ≤ confirmedAtIndex` دارند.
2. **پایداری پیشوند:** اسکن `candles[0..L)` همان رویدادهای تأییدشدهٔ اجرای کامل را می‌دهد.
3. **عدم بازنویسی:** افزودن کندل آینده رویداد تأییدشدهٔ گذشته را تغییر نمی‌دهد.
4. **جدایی provisional:** اکسترمم تأییدنشده هرگز در `events` نمی‌آید.
5. **عدم تغییر ورودی:** ماژول آرایه و کندل‌ها را mutate نمی‌کند.
6. **قطعی‌بودن:** برای ورودی یکسان، خروجی یکسان است (بدون زمان، تصادف یا شبکه).

---

## ۷) غیراهداف

- تولید احتمال، نرخ موفقیت، امتیاز یا توصیهٔ معاملاتی.
- جایگزینی یا تغییر قواعد FTS، جزوه یا سیگنال رسمی.
- محاسبهٔ تعدیل، تجمیع هفتگی/ماهانه یا ساخت سری نمایش.
- رسم اورلی، اتصال به KLineCharts یا تغییر UI.
- Backtest، آمار تاریخی یا انتخاب افق بهینه.
- تشخیص «کندل در حال تشکیل».

---

## ۸) شرایط اتصال بعدی

پیش از اتصال به UI یا سیگنال رسمی:

1. مصرف‌کننده باید همان سری تعدیل‌شدهٔ نمایش را بدهد و فقط کندل بسته.
2. برای هر نماد/تایم‌فریم، کلید کش باید شامل سری و تنظیمات باشد؛ خروجی این ماژول
   نباید با سری نماد قبلی ترکیب شود.
3. `provisionalSwings` نباید به‌عنوان سیگنال اقدام نمایش داده شود.
4. لایهٔ سالینس/ادغام لازم است: در random walk ۲۰٬۰۰۰ کندلی، ۲۱٬۷۵۴ رویداد تولید شد.
5. هر استفاده در سیگنال رسمی یا نمایش «سیگنال معتبر» نیازمند رأی مالک است.
6. اتصال واقعی، رفتار تغییر نماد/تایم‌فریم و مقایسه با Rahavard تا آن زمان
   `NOT_MEASURED` بمانند.

---

## ۹) آزمون

```bash
cd frontend
CI=1 node node_modules/vitest/vitest.mjs run \
  src/features/technical/signals/candleedge/__tests__ --reporter=dot
```

۸ فایل، ۷۷ تست: الگوهای مثبت/منفی/مرزی، پیوت‌ها، provisional، پایداری پیشوند،
افزودن آینده، ورودی تعدیل‌شده از مسیر تولیدی، حالت خام و benchmark ۲۰٬۰۰۰ کندل.
