# میزکار پیشرفته تکنیکال و کوانت — طرح اجرایی (S2 Technical Workspace)

تاریخ: ۲۰۲۶-۱۱-۰۱ · شاخه: `mission/4-axes-2026-10-10` · وضعیت: سند مشخصات فنی (Design Spec) طبق `superpowers-brainstorming`

---

## ۱. هدف

ارتقای بخش تکنیکال و نمودار در `frontend-v2` از یک نمایش‌دهنده ساده شمعی به یک **میزکار جامع تحلیلی و کوانت (Advanced Technical & Quant Workspace)** که شامل موارد زیر است:
1. **موتور نمودار چابک و تعاملی:** بهره‌گیری از `KLineCharts` v10.1.0 با استایل برنجی (`brass`)، پشتیبانی بومی از تقویم جلالی، و کاتالوگ ابزارهای رسم استاندارد (ترندلاین، چنگال اندروز، فیبوناچی، باکس گن و کانال رگرسیون بر پایه هندسه پروژه‌های معتبر `deepentropy` و رهاورد ۳۶۵).
2. **پیش‌بینی سری زمانی محلی با مدل‌های تخصصی کَندلی (Local AI Forecasting via Kronos & Chronos):**
   - استقرار محلی مدل پایه کندل‌های مالی **Kronos-mini** (۴ میلیون پارامتر، مبتنی بر ترنسفورمر کندلی آموزش‌دیده روی ۴۵ صرافی و بازار مالی جهانی) به همراه **Chronos-Bolt-Tiny** (۹٫۲ مگابایت کوانتیزه INT8) در بک‌اند Go (`backend-go/internal/prediction/`).
   - پیش‌بینی افق‌های زمانی ۱ تا ۱۲ کندل آینده با کان‌های احتمالاتی ۱۰٪، ۵۰٪ و ۹۰٪ و سناریوهای مونت‌کارلو (Upside Probability و Volatility Amplification) به صورت کاملاً آفلاین و محلی.
3. **پرایس‌اکشن الگوریتمی و لبه آماری کندل‌ها (Candle Edge & SMC):** پیاده‌سازی فرمول‌های برداری بدون ری‌پینت برای خلا نقدینگی (Fair Value Gap - FVG)، بلوک‌های سفارشات نهادی (Order Blocks)، شکست ساختار بازار (BOS/CHoCH) و شکار نقدینگی (Liquidity Sweeps) با الهام از معماری کلاینت‌ساید `michaelsboost/CandleEdge` و ترکیب با جریان سفارشات و تابلوخوانی بورس تهران (OBI و قدرت خریدار).
4. **موتورهای محاسباتی بومی و جاری (Streaming Indicators):**
   - در فرانت‌اند: کتابخانه تایپ‌اسکریپت `bennycode/trading-signals` برای محاسبات افزایشی تیک‌به‌تیک بدون بار محاسباتی اضافی روی رندر چارت.
   - در بک‌اند Go: ادغام کتابخانه بومی `sdcoffey/techan` در پکیج `backend-go/internal/indicators/` برای پردازش‌های سمت سرور و اسکرینرها.
5. **خط لوله مصرف اندیکاتورهای سفارشی کاربر (`docs/technical-indicators/`):** پذیرش، ممیزی ضد ری‌پینتینگ و کامپایل اندیکاتورهای جدید ارائه‌شده توسط کاربر در مسیر `docs/technical-indicators/inbox/` (مانند فرمت‌های MQL4/MQL5/Pine) به اورلی‌های بومی KLineCharts.
6. **سیستم حرکتی شتاب‌یافته و دسترس‌پذیر:** موشن‌های بهینه‌سازی‌شده برای پالس قیمت لحظه‌ای و ترنزیشن‌های پنل بدون درگیرسازی استیت ری‌اکت و با رعایت استاندارد `prefers-reduced-motion`.

---

## ۲. دامنه کار (Scope)

### ۲.۱. در دامنه (In Scope)
- **فرانت‌اند (`frontend-v2/src/features/technical/`):**
  - کامپوننت اصلی چارت `KLineChartWrapper.tsx` متصل به استور `technicalStore.ts`.
  - نوار ابزار رسم عمودی سمت چپ با ابزارهای: خط روند، خط افقی، فیبوناچی اصلاحی/گسترشی، چنگال اندروز، باکس گن، و مستطیل زون‌های عرضه/تقاضا.
  - اورلی‌های اختصاصی FTS: خطوط مقاومت/حمایت، میانگین متحرک وزنی، و کانال رگرسیون نماد.
  - اورلی کان پیش‌بینی هوش مصنوعی (`predictionConeOverlay`) با ترسیم باندهای صدک ۱۰، ۵۰ و ۹۰ و احتمال صعودی (Upside Probability).
  - اورلی زون‌های FVG و Order Block با قابلیت محو/پنهان‌سازی خودکار در زمان پر شدن ۵۰٪ زون (Mitigation).
  - پنل سایدبار راست: کارت تحلیل لبه آماری (Candle Edge Card) شامل وین‌ریت، امید ریاضی (Expectancy)، فاکتور سود (Profit Factor)، و وضعیت رژیم بازار (رونددار / رنج).
  - پیاده‌سازی کلاینت‌ساید شاخص‌ها با `bennycode/trading-signals`.
  - کنترل‌های تایم‌فریم و بازه تاریخی با پشتیبانی کامل از تاریخ شمسی.
- **بک‌اند Go (`backend-go/`):**
  - پکیج `internal/prediction/`: اجرای مدل‌های `Kronos-mini` و `Chronos-Bolt-Tiny` با خروجی کوانتیل‌های احتمالاتی.
  - پکیج `internal/candleedge/`: موتور محاسباتی تشخیص FVG، Order Block، BOS/CHoCH و متریک‌های لبه آماری کندل‌ها.
  - پکیج `internal/indicators/`: محاسبات تکنیکال سمت سرور با موتور بومی `sdcoffey/techan`.
  - اندپوینت‌های REST:
    - `GET /api/chart/{symbol}/forecast?horizon=12`
    - `GET /api/chart/{symbol}/edge`
    - `GET /api/chart/{symbol}/indicators`
  - فیلتر نقدشوندگی بازار: غیرفعال‌سازی پیش‌بینی هوش مصنوعی برای نمادهای با میانگین ارزش معاملات روزانه زیر ۵ میلیارد تومان یا قفل در صف بدون معامله جهت جلوگیری از خطای آماری.
- **گاردهای عملکرد و دسترس‌پذیری:**
  - تضمین نرخ نوسازی ۶۰ تا ۱۸۰ فریم بر ثانیه در زمان حرکت و زوم چارت روی بیش از ۴۰۰۰ کندل.
  - رعایت قانون `prefers-reduced-motion` در ترنزیشن‌ها.

### ۲.۲. خارج از دامنه (Out of Scope - YAGNI)
- مفسر سنگین زبان‌های MQL در زمان اجرا (اندیکاتورهای ورودی به صورت کد منبع مستقل پورت می‌شوند).
- رندرهای سه‌بعدی یا WebGL سنگین (رندر ۲D Canvas چندلایه‌ای برای بازدهی دسکتاپ برگزیده شده است).
- ارسال داده‌های قیمت به سرورها یا APIهای خارجی هوش مصنوعی (تمامی مدل‌ها ۱۰۰٪ محلی اجرا می‌شوند).

---

## ۳. قراردادها و ساختار داده‌ها (Data Contracts)

### ۳.۱. مدل پیش‌بینی سری زمانی (`prediction.ts` / `prediction.go`)

```go
// PredictionResponse ساختار پاسخ اندپوینت پیش‌بینی افق زمانی
type PredictionResponse struct {
    Symbol        string               `json:"symbol"`
    GeneratedAt   int64                `json:"generated_at"`
    Horizon       int                  `json:"horizon"`
    IsLiquid      bool                 `json:"is_liquid"`        // آیا نماد شرط نقدشوندگی ۵ میلیارد تومان را دارد؟
    LiquidityNote string               `json:"liquidity_note"`
    HistoricalEnd int64                `json:"historical_end"`
    ForecastSteps []ForecastStep       `json:"forecast_steps"`
}

type ForecastStep struct {
    StepIndex int     `json:"step_index"`
    Timestamp int64   `json:"timestamp"`
    P10       float64 `json:"p10"`       // کران پایین احتمالاتی (۱۰٪)
    P50       float64 `json:"p50"`       // میانه پیش‌بینی (۵۰٪)
    P90       float64 `json:"p90"`       // کران بالای احتمالاتی (۹۰٪)
}
```

```ts
export interface ForecastStep {
  stepIndex: number;
  timestamp: number;
  p10: number;
  p50: number;
  p90: number;
}

export interface PredictionData {
  symbol: string;
  generatedAt: number;
  horizon: number;
  isLiquid: boolean;
  liquidityNote?: string;
  forecastSteps: ForecastStep[];
}
```

### ۳.۲. مدل پرایس‌اکشن و لبه آماری (`candleedge.ts` / `candleedge.go`)

```go
type MarketStructureType string
const (
    StructureBOS   MarketStructureType = "BOS"   // Break of Structure
    StructureCHoCH MarketStructureType = "CHoCH" // Change of Character
)

type ZoneType string
const (
    ZoneFVG        ZoneType = "FVG"         // Fair Value Gap
    ZoneOrderBlock ZoneType = "ORDER_BLOCK" // Order Block
)

type PriceZone struct {
    ID          string   `json:"id"`
    Type        ZoneType `json:"type"`
    IsBullish   bool     `json:"is_bullish"`
    Top         float64  `json:"top"`
    Bottom      float64  `json:"bottom"`
    Equilibrium float64  `json:"equilibrium"` // نقطه ۵۰٪ زون
    StartIndex  int      `json:"start_index"`
    StartTs     int64    `json:"start_ts"`
    Mitigated   bool     `json:"mitigated"`   // آیا حداقل ۵۰٪ زون مصرف شده؟
    MitigatedTs int64    `json:"mitigated_ts,omitempty"`
}

type CandleEdgeReport struct {
    Symbol            string      `json:"symbol"`
    PatternName       string      `json:"pattern_name"`       // الگوهای اخیر: Hammer, Engulfing, Pinbar
    WinRate1Bar       float64     `json:"win_rate_1bar"`      // درصد پیروزی در ۱ کندل بعدی
    WinRate3Bar       float64     `json:"win_rate_3bar"`      // درصد پیروزی در ۳ کندل بعدی
    WinRate5Bar       float64     `json:"win_rate_5bar"`      // درصد پیروزی در ۵ کندل بعدی
    ProfitFactor      float64     `json:"profit_factor"`      // فاکتور سود تاریخی
    RiskRewardRatio   float64     `json:"risk_reward_ratio"`  // نسبت سود به زیان میانگین
    SampleCount       int         `json:"sample_count"`       // تعداد نمونه‌های تاریخی بررسی‌شده
    MarketRegime      string      `json:"market_regime"`      // "TRENDING_BULL", "TRENDING_BEAR", "RANGING"
    ActiveZones       []PriceZone `json:"active_zones"`       // زون‌های مصرف‌نشده فعلی
    RecentStructures  []struct {
        Type      MarketStructureType `json:"type"`
        IsBullish bool                `json:"is_bullish"`
        Price     float64             `json:"price"`
        Timestamp int64               `json:"timestamp"`
    } `json:"recent_structures"`
}
```

---

## ۴. معماری ماژول‌های فرانت‌اند (`frontend-v2`)

چیدمان پوشه‌ها در مسیر `frontend-v2/src/features/technical/`:

```
frontend-v2/src/features/technical/
├── api/
│   ├── chartDataApi.ts          # دریافت کندل‌های تاریخی و زنده
│   ├── forecastApi.ts           # دریافت پیش‌بینی Chronos از بک‌اند Go
│   └── candleEdgeApi.ts         # دریافت تحلیل SMC و لبه آماری
├── model/
│   ├── technicalStore.ts        # Zustand استور مدیریت تایم‌فریم، ابزار رسم فعال، اورلی‌ها
│   ├── types.ts                 # تایپ‌های چارت، پیش‌بینی و پرایس‌اکشن
│   └── drawingCatalog.ts        # تنظیمات و نام‌گذاری فارسی ۸۶ ابزار رسم
├── overlays/
│   ├── ftsOverlays.ts           # اورلی‌های ۱۰گانه سیستم FTS با استایل brass
│   ├── predictionOverlay.ts     # اورلی کان احتمالاتی با گرادیان رنگی
│   └── smcOverlays.ts           # اورلی‌های زون FVG و Order Block با تست مصرف‌شدگی
└── ui/
    ├── TechnicalWorkspace.tsx   # کانتینر اصلی صفحه تکنیکال
    ├── KLineChartWrapper.tsx    # هسته تعامل با کانواس KLineCharts v10
    ├── DrawingToolbar.tsx       # نوار ابزارهای ترسیم سمت چپ با آیکون‌های SVG اختصاصی
    ├── CandleEdgeCard.tsx       # کارت لبه آماری و پرایس‌اکشن در سایدبار راست
    └── ForecastControls.tsx     # کلید فعال‌سازی پیش‌بینی و اسلایدر افق زمانی
```

### ۴.۱. ویژگی‌های رابط کاربری و انیمیشن
1. **پالس زنده آخرین کندل:** تغییر قیمت آخرین کندل از طریق انیمیشن شتاب‌یافته CSS `transform: scale(1.02)` روی نشانگر قیمت در محور عمودی بدون رندر مجدد کامپوننت‌های والد ری‌اکت.
2. **پشتیبانی از `prefers-reduced-motion`:** در صورت فعال بودن تنظیمات کاهش حرکت در سیستم‌عامل کاربر، کلیه افکت‌های ضربانی و اسلاید زون‌ها به حالت ایستا تبدیل می‌شوند.
3. **رندر بهینه کان پیش‌بینی:** استفاده از لایه زیرین کانواس چارت با شفافیت ۰٫۱۵ برای باند ۱۰ تا ۹۰ درصد و خط نقطه‌چین طلایی برای باند ۵۰ درصد (میانه).

---

## ۵. معماری ماژول‌های بک‌اند Go (`backend-go`)

### ۵.۱. پکیج پیش‌بینی سری زمانی (`backend-go/internal/prediction/`)
- فایل `onnx_runtime.go`: تعامل امن با کتابخانه ران‌تایم محلی `onnxruntime.dll` و بارگذاری مدل `chronos-bolt-tiny.onnx`.
- اگر ران‌تایم ONNX در سیستم کاربر حاضر نباشد، موتور به صورت خودکار به مدل رگرسیون برداری سریع بومی (Fast Vector Holt-Winters / AutoRegressive) سوئیچ می‌کند تا برنامه هرگز متوقف نگردد.
- گارد نقدشوندگی: در صورت کمتر بودن ارزش معاملات از آستانه ۵ میلیارد تومان، فیلد `IsLiquid = false` بازگردانده شده و محاسبات سنگین استنتاج رد می‌شود.

### ۵.۲. پکیج لبه آماری و SMC (`backend-go/internal/candleedge/`)
- محاسبات برداری بدون ری‌پینت:
  - **FVG:** کندل $i$ دارای خلا نقدینگی صعودی است اگر $\text{Low}(i+1) > \text{High}(i-1)$ و میزان فاصله از ضریب $0.3 \times \text{ATR}(14)$ بیشتر باشد.
  - **Order Block:** آخرین کندل نزولی قبل از یک موج صعودی شتاب‌دار که ساختار سقف قبلی (BOS) را بشکند و با FVG تایید گردد.
  - **وین‌ریت تجربی:** ماتریس انتقال مارکوف بر روی ۲۰۰۰ کندل گذشته برای تخمین احتمال بسته شدن مثبت کندل پس از وقوع الگوی جاری.

---

## ۶. خط لوله پذیرش و مصرف اندیکاتورهای سفارشی کاربر (Custom User Indicators Pipeline)

با توجه به فایل‌های موجود در مخزن (`docs/technical-indicators/inbox/`) و اعلام کاربر مبنی بر قرار دادن اندیکاتورهای جدید در پوشه `docs/`، یک خط لوله نظام‌مند برای ورود، ارزیابی، بازپیاده‌سازی و اتصال این اندیکاتورها به چارت تعبیه می‌شود:

### ۶.۱. اندیکاتورهای فعلی آماده در صندوق ورودی (`inbox/`)
1. **Breakout Retest Pro EA** (`.mq4`): الگوی شکست و پولبک تاییدشده با ATR و حجم.
2. **SuperTrend(wHA)** (`.ex4` / منطق هیکن‌اشی): نسخه بهینه سوپرترند با فیلتر نویز کندل‌های Heikin Ashi جهت حذف نویز سهم‌های کم‌معامله.
3. **FiboRSI8_SingleShot** (`.ex5`): ترکیب سطوح فیبوناچی با نوسان‌گر RSI 8 کندلی برای صید نقاط برگشت تک‌شلیک.
4. **RSI MA Smooth (MTF + Alerts + Divergence)** (`.ex4`): آر‌اس‌آی نرم‌شده چندتایم‌فریمی به همراه ردیاب واگرایی‌های معمولی و مخفی.

### ۶.۲. پروتکل پذیرش و تبدیل ۵مرحله‌ای (بر پایه `INDICATOR_INTAKE_TEMPLATE.md`)
1. **استخراج منطق و فرمول:** استخراج ورودی‌ها، دوره‌های هموارسازی، و منابع قیمت (Close, HLC3, OHLC4).
2. **آزمون گارد ضد ری‌پینت (No-Repaint / Look-Ahead Guard):** تضمین اینکه سیگنال‌ها و مقادیر فقط بر اساس کندل‌های قطعی و بسته‌شده محاسبه می‌شوند و هیچ متغیری از آینده (آفست منفی) در سری وارد نمی‌شود.
3. **رفتار در گپ و داده‌های ناقص بورس:** تعریف صریح رفتار شاخص در روزهای بسته بودن نماد، گپ‌های مجمع و سهم‌های قفل در صف.
4. **تولید اورلی بومی در KLineCharts یا ماژول Go:**
   - اندیکاتورهای نمایشی روی چارت: پورت مستقیم به عنوان اورلی سفارشی در `frontend-v2/src/features/technical/overlays/userIndicators.ts`.
   - اندیکاتورهای فیلتر و اسکرینر: پیاده‌سازی فرمول در پکیج Go با اتکا به محاسبات بومی `sdcoffey/techan`.
5. **تست هم‌ارزی و پارتی (Parity Verification):** ثبت تست مقایسه مقادیر محاسبه‌شده در برابر نرم‌افزار مرجع با خطای نسبی زیر $10^{-5}$ قبل از انتشار در رابط کاربری.

---

## ۷. گیت‌های آزمون و اعتبارسنجی (Testing & Verification)

1. **آزمون‌های واحد بک‌اند Go:**
   - تست دقت تشخیص FVG و Order Block با داده‌های ساختگی مرجع در `backend-go/internal/candleedge/smc_test.go`.
   - تست سرعت استنتاج مدل‌های Kronos-mini و Chronos در `backend-go/internal/prediction/prediction_test.go` (حداکثر زمان مجاز: ۳۰ میلی‌ثانیه برای افق ۱۲ کندلی).
   - تست صحت شاخص‌های محاسباتی `internal/indicators/` با داده‌های تاریخی واقعی بورس.
2. **آزمون‌های فرانت‌اند (`frontend-v2`):**
   - تست‌های تعاملی با Vitest برای استور `technicalStore` و افزودن/حذف اورلی‌ها و ابزارهای ترسیم.
   - تست صحت محاسبات استریمینگ `trading-signals` در مقیاس تیک‌به‌تیک.
   - تست تایپ‌چک کامل بدون خطا: `npx tsc -b`.
3. **سنجش زنده رندر و پیکسل‌ها:**
   - اجرای ابزار سنجش پیکسل زنده کانواس (`canvas-chart-live-pixel-check`) جهت اطمینان از رندر صحیح کان پیش‌بینی و زون‌های FVG روی محورهای مختصات.
   - بازرسی دسترسی‌پذیری و رابط دسکتاپ با `agent-desktop`.

---

## ۸. بازبینی و سوالات تاییدیه (Sign-Off Checkpoints)

- [x] تایید معماری پایه (KLineCharts v10 + پیش‌بینی محلی Kronos/Chronos + پرایس‌اکشن SMC).
- [x] فیلتر نقدشوندگی (۵ میلیارد تومان) برای تضمین دقت پیش‌بینی هوش مصنوعی.
- [x] رفتار خودکار محو/پنهان‌سازی زون‌های FVG مصرف‌شده جهت خوانایی بصری نمودار.
- [x] ادغام پروژه‌های معتبر ارائه‌شده توسط کاربر (`Kronos`, `CandleEdge`, `techan`, `trading-signals`, `ta`).
- [x] پروتکل خط لوله پذیرش و ممیزی اندیکاتورهای سفارشی از پوشه `docs/technical-indicators/`.
- [ ] شروع تدوین برنامه اجرایی مرحله‌به‌مرحله با اسکیل `writing-plans`.
