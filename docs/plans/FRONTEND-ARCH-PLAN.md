# سند Plan — معماری ماژولار فرانت‌اند داشبورد تحلیلی بورس (۵ ایجنت)

تاریخ: ۱۴۰۵/۰۶/۲۱ (2026-09-12) · وضعیت: پیش‌نویس رسمی v1 · نویسنده: ایجنت برنامه‌ریزی

این سند نقشهٔ راه مهاجرت فرانت‌اند `BorsTerminal_Ultimate` از تک‌صفحهٔ Vanilla JS
(`static/index.html` + هفت فایل JS سراسری با `onclick` inline) به یک اپلیکیشن
**ماژولار، تایپ‌شده و Feature-Based** است که هر ایجنت تحلیلی را به‌صورت یک ماژول
مستقل با مرزهای مشخص ساپورت می‌کند. تمام متن این سند بدون نیم‌فاصله (ZWNJ) نوشته
شده است تا با قانون پروژه سازگار باشد.

---

## فهرست

1. [اصول و محدودیت‌های طراحی](#۱-اصول-و-محدودیتهای-طراحی)
2. [بخش ۱ — انتخاب فریمورک و پشتهٔ فنی](#بخش-۱--انتخاب-فریمورک-و-پشتهٔ-فنی)
3. [بخش ۲ — ساختار پوشه‌بندی Feature-Based](#بخش-۲--ساختار-پوشهبندی-feature-based)
4. [بخش ۳ — قرارداد مشترک داده (Agent Signal Contract)](#بخش-۳--قرارداد-مشترک-داده-agent-signal-contract)
5. [بخش ۴ — فازبندی گام‌به‌گام پیاده‌سازی](#بخش-۴--فازبندی-گامبهگام-پیادهسازی)
6. [بخش ۵ — ریسک‌ها و پروتکل‌های شکستن‌ناپذیر](#بخش-۵--ریسکها-و-پروتکلهای-شکستنناپذیر)

---

## ۱. اصول و محدودیت‌های طراحی

### ۱.۱ اصول

- **Feature-Based نه Layer-Based**: هر ایجنت یک پوشهٔ خودکفا با کامپوننت‌ها،
  state، API کلاینت و تایپ‌های خودش دارد. هیچ ایجنتی از پوشهٔ ایجنت دیگر import نمی‌کند.
- **قرارداد قبل از UI**: قبل از نوشتن هر کامپوننتی، تایپ و قرارداد داده در
  `frontend/src/contracts/` قفل می‌شود؛ UI فقط مصرف‌کنندهٔ قرارداد است.
- **دیتاستور یکپارچه**: یک فروشگاه واحد Zustand (بدون Redux) برای state مشترک
  (نماد انتخابی، دیتای بازار، تنظیمات) و فروشگاه‌های محلی کوچک در هر فیچر.
- **جدید کنار قدیم**: اپ React در `frontend/` ساخته می‌شود و پشت همان بک‌اند
  FastAPI روی مسیر `/app` سرو می‌شود؛ `static/` فعلی دست‌نخورده می‌ماند تا پایان
  فاز ۷ (بازنشست کامل) میزبان کاربران فعلی است.

### ۱.۲ محدودیت‌های سخت

1. بک‌اند FastAPI موجود دست نمی‌خورد؛ فقط یک route برای سرو اپ جدید اضافه می‌شود.
2. ZWNJ در هیچ فایل متنی جدیدی استفاده نمی‌شود (قانون پروژه).
3. هر فاز باید با تست‌های موجود (`python dev/run_all_tests.py` سبز) قابل
   ادغام باشد؛ هیچ فازی نباید بیش از ۲ هفته کاری طول بکشد.
4. Vazirmatn و KLineCharts موجود از `static/vendor` (به صورت local vendor)
  بازیافت می‌شوند؛ CDN ممنوع (محیط کاربر ممکن است فیلترشده باشد).
5. زبان UI فارسی و RTL است؛ `dir="rtl"` و `lang="fa"` در روت اپ.

---

## بخش ۱ — انتخاب فریمورک و پشتهٔ فنی

### ۱.۳ جدول تصمیم فریمورک

| معیار | وزن | React + Vite | Vue 3 + Vite | Svelte 5 |
|---|---|---|---|---|
| اکوسیستم کتابخانه‌های چارت مالی | ۰٫۳ | **۵** (lightweight-charts, TradingView clones) | ۳ | ۲ |
| تیم/ایجنت‌های همزمان روی کدبیس | ۰٫۲۵ | **۵** (مرزهای فیچر روشن) | ۴ | ۳ |
| تایپ‌شدن قرارداد داده (Zod/TS) | ۰٫۲ | **۵** | ۴ | ۴ |
| مهاجرت تدریجی از Vanilla JS | ۰٫۱۵ | ۴ | **۵** | ۳ |
| ماندگاری و پشتیبانی بلندمدت | ۰٫۱ | **۵** | ۴ | ۳ |

**انتخاب نهایی: React 18 + TypeScript + Vite 5** — امتیاز وزنی ۴٫۸/۵.

دلایل قطعی:

- **کتابخانه‌های چارت مالی درجه یک**: `lightweight-charts` (رسم کندل با پرفورمنس
  حرفه‌ای)، `klinecharts` (همان کتابخانهٔ فعلی پروژه — دارایی موجود!) و
  `@nivo` یا `recharts` برای نمودارهای تحلیلی.
- دارایی فعلی پروژه: `static/vendor/klinecharts.min.js` نسخهٔ v10 — می‌توان به
  صورت ES Module در React با wrapper تایپ‌شده بازیافتش کرد (فاز ۴).
- TypeScript قرارداد Signal (بخش ۳) را در سطح کامپایل قفل می‌کند.

### ۱.۴ پشتهٔ تکمیلی

| لایه | انتخاب | دلیل |
|---|---|---|
| Build / Dev | **Vite 5** + `@vitejs/plugin-react` | HMR فوری، پشتیبانی TS بومی، سازگاری با Node 24 |
| زبان | **TypeScript 5.x (strict)** | قفل قرارداد داده بین ۵ ایجنت |
| استایل | **Tailwind CSS 4** + CSS Variables موجود | کلاس‌های ابستریکت؛ متغیرهای تم فعلی (`--bg-primary`, `--accent-blue`, ...) مستقیماً به `@theme` منتقل می‌شوند تا تم Dark/Light فعلی حفظ شود |
| مدیریت State | **Zustand 5** (سلکتورمحور) + `immer` | سبک، بدون Provider hell، تست‌پذیر؛ state مشترک در `stores/` و state ایجنت‌ها در خود فیچر |
| دیتا / سوکت | **TanStack Query 5** (REST polling با `refetchInterval` هماهنگ اسلایدر فعلی ۱-۳۰ دقیقه) | کش، retry، invalidation؛ بعداً WebSocket در همین لایه جای می‌گیرد |
| اعتبارسنجی | **Zod 4** + `zod-to-ts` | اسکیمای Signal در حالت اجرا و کامپایل یکسان می‌ماند |
| روتر | **React Router 7** (declarative) | روت‌های فیچر: `/app/fundamental/:symbol`, `/app/master` و غیره |
| چارت کندل | **klinecharts v10** (vendor موجود) + wrapper TS | بدون بازنویسی موتور چارت؛ overlayها و ابزار رسم فعلی در فاز ۴ منتقل می‌شوند |
| چارت تحلیلی | **lightweight-charts 5** | برای رادار/مقایسه/هیتمپ ایجنت مستر |
| جدول‌ها | **TanStack Table 8** | جدول اسکرینر با сорتی/فیلتر/ستون قابل تنظیم (همان تجربهٔ فعلی) |
| تست | **Vitest** + `@testing-library/react` + `jsdom` | هم‌خانوادهٔ Vite؛ تست‌های DOM-ساختگی فعلی (`test_fts_v10_ui.js`) الگوی نگارش‌اند |
| Lint / Format | **ESLint 9 (flat)** + `typescript-eslint` + Prettier | گارد مرز فیچر با `eslint-plugin-boundaries` |

### ۱.۵ معیار پذیرش فاز ۰ (راه‌اندازی)

- [ ] `npm run dev` روی :5173 با پروکسی `/api` به :8012 بالا بیاید.
- [ ] `npm run build` خروجی را در `frontend/dist` بسازد.
- [ ] Route جدید `GET /app` در `app.py` (یا `api/`، بسته به محل مناسب) همان
      `frontend/dist/index.html` را سرو کند؛ بقیهٔ assetها از `/app/assets` سرو شوند.
- [ ] صفحهٔ فارسی RTL با فونت Vazirmatn (کپی‌شده از `static/vendor/fonts`).

---

## بخش ۲ — ساختار پوشه‌بندی Feature-Based

### ۲.۱ نمای کلی

```
BorsTerminal_Ultimate/
├── app.py · api/ · *.py          ← بک‌اند FastAPI (دست‌نخورده؛ فقط mount جدید)
├── static/                       ← فرانت‌اند قدیمی (تا فاز ۷ پابرجا)
├── dev/                          ← تست‌های موجود (پایتون) — دست‌نخورده
└── frontend/                     ★ اپ React جدید — تمام کد این سند
    ├── package.json
    ├── tsconfig.json             (strict · bundler resolution)
    ├── vite.config.ts            (proxy /api → :8012 · base /app)
    ├── index.html                (fa · rtl · فونت Vazirmatn local)
    ├── eslint.config.js
    ├── .env.example              (VITE_API_BASE=)
    │
    ├── public/
    │   └── fonts/vazirmatn/      ← کپی از static/vendor/fonts (خارج CDN)
    │
    ├── src/
    │   ├── main.tsx              ورود اپ + Router + QueryClient
    │   ├── App.tsx               Shell: سایدبار + هدر + <Outlet/>
    │   │
    │   ├── app/                  ★ فیچر: پوستهٔ مشترک (اسکلتون UI)
    │   │   ├── components/       Sidebar · Topbar · ThemeToggle · ToastHost
    │   │   ├── layouts/          AppShell.tsx · TabSyncBridge.tsx
    │   │   └── stores/           uiStore (تم، فونت‌اسکیل، سایدبار)
    │   │
    │   ├── shared/               ★ کد مشترک در سراسر فیچرها (نه منطق ایجنت!)
    │   │   ├── api/              http.ts (fetch wrapper + Zod parse + retry)
    │   │   ├── types/            Symbol.ts · MarketRow.ts · Candle.ts
    │   │   ├── stores/           symbolStore (نماد انتخابی سراسری) ·
    │   │   │                     marketStore (تابلو + polling)
    │   │   ├── components/       DataTable · Badge · Sparkline · EmptyState
    │   │   │                     ConfidenceDial · RiskGateChip · Modal
    │   │   ├── lib/              jalaali.ts (بازیافت jalaali-js) ·
    │   │   │                     fmt.ts (اعداد فارسی، همت) · time.ts
    │   │   └── styles/           tokens.css (متغیرهای تم فعلی)
    │   │
    │   ├── features/             ★★★ قلب معماری — هر پوشه = یک ایجنت
    │   │   ├── market/           ایجنت ۳: تابلوخوانی و جریان سفارشات
    │   │   │   ├── api/         useMarketFeed · useDepthChart
    │   │   │   ├── components/  TapeTable · OrdersFlow · SuspiciousPanel
    │   │   │   ├── hooks/       useTapeSignals (الگوی ساعت و...)
    │   │   │   ├── stores/      tapeStore (محلی)
    │   │   │   ├── signals/     tapeSignals.ts ← خروجی: AgentSignal[]
    │   │   │   └── routes.tsx   /app/market
    │   │   │
    │   │   ├── fundamental/      ایجنت ۱: تحلیل بنیادی
    │   │   │   ├── api/         useFtsCard(symbol) · useFtsCoverage
    │   │   │   ├── components/  FtsCard · LayerGrid · DataGapBanner ·
    │   │   │   │                RiskGatesPanel · EpsLadder · FundSettings
    │   │   │   ├── signals/     fundamentalSignals.ts ← AgentSignal[]
    │   │   │   └── routes.tsx   /app/fundamental/:symbol
    │   │   │
    │   │   ├── technical/        ایجنت ۲: تحلیل تکنیکال
    │   │   │   ├── api/         useCandles · useKeyLevels · usePatterns
    │   │   │   ├── components/  ChartHost (wrapper klinecharts v10) ·
    │   │   │   │                DrawingToolbar · IndicatorSettings · KeyLevels
    │   │   │   ├── lib/         indicators.ts (RSI/EMA/BOLL با دورهٔ تایم‌فریمی)
    │   │   │   ├── signals/     technicalSignals.ts ← AgentSignal[]
    │   │   │   └── routes.tsx   /app/technical/:symbol
    │   │   │
    │   │   ├── portfolio/        ایجنت ۴: مدیریت پرتفوی و ریسک
    │   │   │   ├── api/         usePortfolio · useDecisions (mutation)
    │   │   │   ├── components/  PortfolioBoard · DecisionModal ·
    │   │   │   │                StopLossLadder · TripleMatrix · WeightEditor
    │   │   │   ├── signals/     portfolioSignals.ts ← AgentSignal[]
    │   │   │   └── routes.tsx   /app/portfolio
    │   │   │
    │   │   └── master/          ایجنت ۵: ارشد — تجمیع ۴ ایجنت
    │   │       ├── aggregation/ masterEngine.ts (رتبه‌بندی و رأی‌گیری)
    │   │       │                dissent.ts (فاصلهٔ دیدگاه‌ها)
    │   │       ├── components/  MasterDashboard · SignalTimeline ·
    │   │       │                AgentRadar · DissentBoard · FinalVerdict
    │   │       ├── stores/      masterStore (سراسریِ فیچر)
    │   │       └── routes.tsx   /app/master
    │   │
    │   └── __tests__/            تست‌های واحد + قرارداد (Vitest)
    │
    ├── tests/                    تست E2E — Playwright (فاز ۶)
    │   └── e2e/                  smoke.spec.ts · master-aggregation.spec.ts
    │
    └── e2e-server.config.ts
```

### ۲.۲ قواعد مرزی (اجرا با ESLint)

| # | قاعده | ابزار اجرا |
|---|---|---|
| B1 | `features/X` اجازه ندارد از `features/Y` چیزی import کند (هیچ‌کس) | `eslint-plugin-boundaries` |
| B2 | `features/*` فقط از `shared/` و `contracts/` (پکیج shared) import می‌کند | `eslint-plugin-boundaries` |
| B3 | `shared/` اجازه ندارد چیزی از `features/*` یا `app/` import کند | `eslint-plugin-boundaries` |
| B4 | کامپوننت فیچر بیش از ۲۰۰ خط نشود؛ منطق در hooks/lib | code review + `eslint max-lines` |
| B5 | هیچ fetch بیرون از `api/` فیچر یا `shared/api/http.ts` زده نشود | ESLint `no-restricted-syntax` |
| B6 | قرارداد Signal فقط در `frontend/src/contracts/` تعریف می‌شود (توضیح بخش ۳) | مرور کد + CI |

به این ترتیب پنج ایجنت (چهار ساب‌ایجنت + ایجنت مستر) می‌توانند **به‌صورت
موازی و بدون merge-conflict ساختاری** کار کنند: هر ایجنت فقط پوشهٔ خودش و در
بدترین حالت `shared/` را لمس می‌کند.

### ۲.۳ نقشهٔ نگاشت ایجنت ← فیچر ← دادهٔ موجود

| ایجنت | فیچر | منابع دادهٔ بک‌اند موجود |
|---|---|---|
| ۱. بنیادی | `features/fundamental` | `/api/fts`, `/api/fundamental/{sym}`, `/api/screener`, `/api/fts/config` (GET/POST), `/api/sync/codal/fts-coverage` |
| ۲. تکنیکال | `features/technical` | `/api/chart/{sym}`, `/api/chart-db/{sym}`, `/api/chart/{sym}/key-levels`, `/api/patterns/{sym}` |
| ۳. تابلوخوانی | `features/market` | `/api/market`, `/api/market-status/*`, `/api/history/{sym}` |
| ۴. پرتفوی | `features/portfolio` | `/api/selection/portfolio`, `/api/selection/decision` (POST/DELETE), `/api/export` |
| ۵. مستر | `features/master` | خروجی ۴ فیچر دیگر (Signal Bus) + `/api/market-status/overview` برای بافت |

---

## بخش ۳ — قرارداد مشترک داده (Agent Signal Contract)

### ۳.۱ فلسفه

هر ایجنت تحلیلی خروجی خود را نه به‌صورت HTML یا رشته، بلکه به‌صورت
**آرایه‌ای از `AgentSignal`** منتشر می‌کند. ایجنت مستر این سیگنال‌ها را مصرف،
رتبه‌بندی و تجمیع می‌کند. این قرارداد قلب معماری است چون:

- **قفل کامپایلری**: با TypeScript، هر تغییر قرارداد بلافاصله خطای build در
  هر ۵ فیچر می‌شود.
- **قفل زمان اجرا**: با Zod، خروجی هر ایجنت قبل از انتشار validate می‌شود؛
  سیگنال خراب به مستر نمی‌رسد.
- **تست‌پذیری**: هر ایجنت با fixture ثابت قابل تست است بدون اجرای ایجنت‌های دیگر.
- **گسترش‌پذیری**: ایجنت ششم در آینده فقط یک تولیدکنندهٔ جدید است؛ مستر
  هیچ تغییری نمی‌خواهد.

### ۳.۲ محل قرارگیری قرارداد

```
frontend/src/contracts/        ← تنها منبع حقیقت قراردادها (B6)
├── signal.ts                  AgentSignal + انواع پایه
├── fundamental.ts            FundamentalPayload (بازتاب passes/details FTS v10)
├── technical.ts               TechnicalPayload (ستاپ‌ها، سطوح، اندیکاتورها)
├── tape.ts                    TapePayload (الگوی ساعت، حجم مشکوک، جریان)
├── portfolio.ts               PortfolioPayload (وضعیت تصمیم، وزن، حد ضرر)
├── master.ts                  MasterVerdict + AggregationSnapshot
└── index.ts                   barrel export
```

`contracts/` عمداً خارج از `features/` و خارج از `shared/` است تا:
هر دو قابل ارجاع باشند ولی خودش به هیچ‌یک وابسته نباشد (acyclic by design).

### ۳.۳ تایپ پایهٔ `AgentSignal` (definitive)

```ts
// frontend/src/contracts/signal.ts
import { z } from 'zod';

/** جهت سیگنال — کنوانسیون سراسری */
export const Direction = z.enum(['bullish', 'bearish', 'neutral']);
export type Direction = z.infer<typeof Direction>;

/** حالت اعتماد داده — با واژگان موتور FTS هم‌راستا (pass|warn|fail|nodata) */
export const Confidence = z.enum(['high', 'medium', 'low', 'nodata']);
export type Confidence = z.infer<typeof Confidence>;

/** هویت تولیدکنندهٔ سیگنال — تنها ۴ مقدار مجاز ساب‌ایجنت */
export const AgentId = z.enum(['fundamental', 'technical', 'tape', 'portfolio']);
export type AgentId = z.infer<typeof AgentId>;

/** پیکربندی (فیچر)‌ای که سیگنال از آن نشأت گرفت — برای deep-link UI */
export const SourceView = z.enum(['fundamental', 'technical', 'market', 'portfolio']);
export type SourceView = z.infer<typeof SourceView>;

/** اهمیت سیگنال در تصمیم نهایی مستر: مستقیم وزن‌دار است */
export const SignalWeight = z.enum(['critical', 'major', 'minor', 'info']);
export type SignalWeight = z.infer<typeof SignalWeight>;

/** پارامترهای عمومی سیگنال — پایهٔ مشترک همهٔ ایجنت‌ها */
export const BaseSignal = z.object({
  /** شناسهٔ یکتا: `${agentId}:${symbol}:${kind}:${ts}` */
  id: z.string().regex(/^(fundamental|technical|tape|portfolio):[A-Za-z0-9\u0600-\u06FF]+:[a-z0-9_]+:\d+$/),
  agentId: AgentId,
  symbol: z.string().min(1),              // نماد بورس (فارسی مجاز)
  ts: z.number().int().positive(),        // epoch ms — لحظهٔ صدور سیگنال
  direction: Direction,
  confidence: Confidence,
  weight: SignalWeight.default('major'),
  /** عنوان فارسی کوتاه برای UI: «نسبت P/E زیر میانگین صنعت» */
  title: z.string().min(2),
  /** توضیح کامل فارسی: استدلال، اعداد، منبع */
  rationale: z.string().min(4),
  /** عدد داورانه در صورت وجود (۱۰۰ = قوی‌ترین) — nil مجاز */
  score: z.number().min(0).max(100).nullable().default(null),
  /** عمق پشتیبان: ['fts:layer2', 'eps_ladder'] برای مسیریابی UI مستر */
  evidence: z.array(z.string()).default([]),
  /** لینک به فیچر مبدأ: '/app/fundamental/شپنا' */
  sourceView: SourceView,
  /** منبع دادهٔ پشتیبان سیگنال: ['API', 'Local', 'Derived'] */
  sourceRef: z.array(z.string()).default([]),
  /** ابطال خودکار: سیگنال‌های قدیمی‌تر از این مهلت در مستر کنار گذاشته می‌شوند */
  validForMs: z.number().int().positive().max(6 * 3600_000).default(3600_000),
});

export type BaseSignal = z.infer<typeof BaseSignal>;

/** سیگنال تکمیل‌شده با payload اختصاصی هر ایجنت */
export type AgentSignal<T = unknown> = BaseSignal & {
  /** payload تایپ‌شدهٔ هر ایجنت — در قرارداد همان ایجنت تعریف می‌شود */
  payload: T;
};

/** پیام رویداد انتشار سیگنال (Signal Bus — بخش ۳.۶) */
export const SignalEvent = z.object({
  kind: z.literal('signal'),
  signal: BaseSignal,
  /** شمارهٔ نسخهٔ قرارداد — برای هماهنگی آینده */
  v: z.literal(1),
});
export type SignalEvent = z.infer<typeof SignalEvent>;
```

### ۳.۴ قراردادهای payload هر ایجنت (خلاصهٔ فیلدهای کلیدی)

**`fundamental.ts`** — بازتاب مستقیم FTS v10 موجود در `api/fundamental.py`:

```ts
export const FundamentalPayload = z.object({
  kind: z.literal('fts_card'),
  score: z.number().min(0).max(5),          // امتیاز ۵ لایه
  passes: z.record(z.string(), z.boolean()), // '1a_monetary_growth' ...
  riskGates: z.array(RiskGate),              // m141 · mcap · liquidity · industry
  epsSeries: z.array(z.number().nullable()), // نردبان EPS (nullable = '-')
  dataGaps: z.array(z.object({ layer: z.string(), why: z.string(), fix: z.string() })),
});
```

**`technical.ts`** — از ستاپ‌های v9.7.4 (breakout/pullback/fibonacci/CHoCH/bearish_div):

```ts
export const TechnicalPayload = z.object({
  kind: z.literal('setup'),
  timeframe: z.enum(['daily', 'weekly', 'monthly']),
  setups: z.array(z.string()),              // 'breakout' | 'pullback' | ...
  stopLossRef: z.enum(['ma14', 'rising_low', 'swing_stop']).nullable(),
  keyLevels: z.array(z.object({ type: z.string(), price: z.number() })),
});
```

**`tape.ts`** — الگوی ساعت و جریان سفارشات:

```ts
export const TapePayload = z.object({
  kind: z.literal('tape_pattern'),
  pattern: z.enum(['closing_auction_pop', 'suspicious_volume', 'none']),
  lastVsClose: z.number(),                   // (آخرین − پایانی)/پایانی
  volumeMultiple: z.number().nullable(),      // نسبت حجم مشکوک
});
```

**`portfolio.ts`** — وضعیت تصمیم و ریسک:

```ts
export const PortfolioPayload = z.object({
  kind: z.literal('position_state'),
  decision: z.enum(['accept', 'reject', 'monitor', 'pending']),
  weightPct: z.number().min(0).max(100).nullable(),
  stopLoss: z.number().nullable(),
  alerts: z.array(z.string()),               // «وزن‌ها بیش از سقف ۲۰٪»
});
```

### ۳.۵ خروجی ایجنت مستر: `MasterVerdict`

```ts
export const MasterVerdict = z.object({
  symbol: z.string(),
  ts: z.number().int().positive(),
  /** نتیجهٔ رأی‌گیری وزنی سیگنال‌ها: -100 (خرسی کامل) تا +100 (صعودی کامل) */
  compositeScore: z.number().min(-100).max(100),
  finalAction: z.enum(['buy', 'hold', 'watch', 'reduce', 'sell', 'no_data']),
  /** سهم هر ایجنت در نتیجه — برای شفافیت و رادار UI */
  contributions: z.array(z.object({
    agentId: AgentId,
    score: z.number().min(-100).max(100),
    signalCount: z.number().int().nonnegative(),
    confidence: Confidence,
  })),
  /** سیگنال‌های ناسازگار که مستر نتوانست آشتی دهد */
  dissent: z.array(z.object({
    agents: z.tuple([AgentId, AgentId]),
    gap: z.number().min(0).max(200),
    note: z.string(),
  })),
  /** سیگنال‌های استفاده‌شده (id) برای trace کامل تصمیم */
  usedSignalIds: z.array(z.string()),
  /** سیگنال‌های ردشده به دلیل کهنگی (validForMs) یا اعتبار پایین */
  discardedSignalIds: z.array(z.string()),
});
```

### ۳.۶ جریان داده و Signal Bus

```
fundamental ─┐
technical  ─┤─ publish(AgentSignal) ─→ [Signal Bus (Zustand slice)] ─→ masterEngine ─→ MasterVerdict
tape       ─┤        (Zod validate)         (async, debounced 500ms)    (aggregation)
portfolio  ─┘
```

- **Signal Bus**: یک slice از `masterStore` به نام `signalBus`؛ هر فیچر پس از
  هر fetch/محاسبه موفق، سیگنال‌های خودش را `publish` می‌کند.
- **Validate در نقطهٔ انتشار**: تابع `publish()` در `contracts/` خودش Zod parse
  می‌کند؛ سیگنال نامعتبر هرگز وارد باس نمی‌شود (و در dev با console.error گزارش
  می‌شود).
- **Debounce تجمیع**: مستر با debounce 500ms سیگنال‌های تازه را تجمیع می‌کند تا
  در بارگذاری اولیهٔ همزمان ۴ ایجنت، ۴ بار رندر سنگین رخ ندهد.
- **Dedup و انقضا**: مستر سیگنال‌های تکراری (same id) و منقضی (`ts + validForMs < now`)
  را کنار می‌گذارد و در `discardedSignalIds` ثبت می‌کند.
- **وزن پیش‌فرض مصوب** (در فاز ۵ با تنظیمات UI قابل تغییر): بنیادی ۴، تکنیکال ۳،
  تابلو ۲، پرتفوی ۱. وزن کل سیگنال = `agentWeight × SignalWeight`.

---

## بخش ۴ — فازبندی گام‌به‌گام پیاده‌سازی

هر فاز: خروجی قابل تحویل، تعامل با بک‌اند، تست‌ها، و معیار «انجام شده».
فازها ترتیبی‌اند ولی داخل هر فاز مراحل موازی‌سازی‌پذیر برای ۵ ایجنت هستند.

### فاز ۰ — زیرساخت و Skeleton (۱ هفته) · `P0`

**هدف**: اپ React خالی و فارسی RTL که پشت بک‌اند فعلی سرو می‌شود.

مراحل:

1. `frontend/` با Vite + React + TS strict + Tailwind + ESLint (flat config,
   plugin-boundaries) + Vitest scaffolding شود.
2. فونت Vazirmatn و `klinecharts.min.js` و `drawing_math.js` از `static/vendor`
   به `frontend/public/vendor/` و `src/vendor/` کپی شوند (بدون CDN).
3. متغیرهای تم از `static/styles.css` به `src/shared/styles/tokens.css` منتقل
   شوند (نام‌ها حفظ: `--bg-primary`, `--accent-blue`, ...).
4. `AppShell` با سایدبار فارسی (۶ آیتم ناوبری فعلی + مستر) و روت‌های خالی.
5. بک‌اند: یک mount ساده — سرو `frontend/dist` از مسیر `/app` (در `app.py` یا
   `api/_static_app.py`؛ تصمیم نهایی در مرور کد فاز ۰) + fallback SPA.
6. `http.ts`: wrapper fetch با Zod parse + retry نمایی (الگوی `codal_fetcher`
   فعلی: backoff روی 429/403) + هدر `Accept: application/json`.

تحویل: `/app` بالا، سایدبار قابل کلیک، تم Dark یکسان با ترمینال فعلی.

تست: `npm run build` سبز؛ `python dev/run_all_tests.py` سبز (رگرسیون صفر)؛
Playwright smoke: `/app` عنوان فارسی و `dir=rtl` دارد.

معیار انجام: کاربر بتواند اپ جدید را کنار ترمینال قدیمی باز و مقایسه کند.

### فاز ۱ — قرارداد داده و Stores مشترک (۱ هفته) · `P1`

**هدف**: قرارداد Signal + تایپ‌های پایه + استورهای مشترک؛ هنوز UI جدیدی نیست.

مراحل:

1. `src/contracts/` کامل (بخش ۳) + تست‌های Zod در `__tests__/contracts.spec.ts`
   با fixture از پاسخ‌های واقعی API (بازیافت الگوی `make_fts_ui_fixture.py`).
2. `shared/api/http.ts` + `shared/stores/symbolStore` + `marketStore`
   (polling با `refetchInterval` پویا از تنظیمات — هم‌ارز اسلایدر ۱ث-۳۰دقیقه فعلی).
3. `shared/lib/`: jalaali (بازیافت `jalaali-js.min.js` با d.ts)، `fmt.ts`
   (اعداد فارسی، همت با `HEMMAT_RIAL = 10^13`، mcap تک‌منبع)، `time.ts`.
4. کامپوننت‌های پایه: DataTable (TanStack Table)، Badge، Modal، ConfidenceDial.
5. `eslint-plugin-boundaries` فعال: قواعد B1-B6 در CI.

تحویل: `contracts` قابل import از همه فیچرها؛ جدول تابلو بازار فعلی با DataTable
جدید در `/app/market` کار کند (پرواز اول data-fetch واقعی).

تست: واحد: قراردادها، fmt، jalaali؛ کامپوننت: DataTable رندر fixture.
معیار انجام: رندر ۲۵۲۰ نماد (سقف فعلی بازار) زیر ۱ ثانیه در جدول مجازی‌شده.

### فاز ۲ — فیچر Market (تابلوخوانی، ایجنت ۳) (۱ هفته) · `P2`

**هدف**: نمای تابلو + پنل‌های جریان سفارش + اولین تولیدکنندهٔ سیگنال.

مراحل:

1. `useMarketFeed` (TanStack Query روی `/api/market`) + فیلترهای نوع دارایی
   (همان ۱۱ chip فعلی: سهام، پایه، تسهیلات، ...) + جستجوی نماد.
2. جدول تابلو مجازی‌شده (virtualization با TanStack Virtual) با ستون‌های قابل
   تنظیم و مرتب‌سازی — هم‌ارز رفتار فعلی.
3. `useDepthChart`: نمودار عمق سفارشات از `/api/history/{sym}` + محاسبهٔ
   نسبت خرید حقیقی/حقوقی در `hooks/` (بازیافت منطق `mstat.js`).
4. SuspiciousPanel: «الگوی ساعت» — `(آخرین − پایانی)/پایانی ≥ +۱٪` + حجم
   مشکوک ≥ ۳ برابر (همان قواعد v9.7.4؛ فقط هشدار).
5. `signals/tapeSignals.ts`: تبدیل قواعد بالا به `AgentSignal<TapePayload>[]`
   و انتشار در Signal Bus.

تحویل: `/app/market` کامل؛ اولین سیگنال‌های live در باس قابل مشاهده در
DevTools (پنل debug مستر).

تست: واحد: tapeSignals با fixture بازار واقعی (۰ سیگنال در روز عادی، سیگنال
در fixture دستکاری‌شده)؛ کامپوننت: رندر جدول ۲۵۲۰ سطری.

### فاز ۳ — فیچر Fundamental (ایجنت ۱) (۱ هفته) · `P3`

**هدف**: کارت بنیادی FTS v10 + پنل تنظیمات + سیگنال بنیادی.

مراحل:

1. `useFtsCard(symbol)` روی `/api/fundamental/{sym}` — تایپ کامل payload
   (passes · details · data_gaps · risk_gates · eps_series · period_slots ·
   market_cap_src/stale ...).
2. `FtsCard`: شش سلول خلاصه (۱الف/۱ب/۲/۳/۴+پتانسیل/۵) با حالت‌های خاکستری
   (داده نیست) و قرمز (مردود) — هم‌ارز `fundamental_ui.js` فعلی.
3. `DataGapBanner` (why + fix) و `EpsLadder` (سطر ناقص = «-»، قرمز، بدون حذف —
   قاعدهٔ v9.9.0 حفظ شود).
4. `RiskGatesPanel`: چهار دروازه (m141 · کف مارکت‌کپ · نقدشوندگی · صنایع).
5. `FundSettings`: پنل تنظیمات CODAL v10 — اعتبارسنجی محلی، POST
   `/api/fts/config`، رفتار بی‌reload (هم‌ارز `test_fts_settings_ui.js`).
6. `signals/fundamentalSignals.ts`: هر لایهٔ pass/fail/warn ⇒ سیگنال با
   rationale از `details[i].subchecks`.

تحویل: `/app/fundamental/شپنا` کارت کامل با تمامی حالت‌های لبه.

تست: پاریتی با `dev/test_fts_v10_ui.js` — همان ۳ سناریو (کامل / ۲-دوره /
بدون داده) در Vitest بازتولید شود؛ واحد: fundamentalSignals.

### فاز ۴ — فیچر Technical (ایجنت ۲) (۱.۵ هفته) · `P4`

**هدف**: چارت زندهٔ KLineCharts v10 داخل React با ابزارهای رسم + سیگنال تکنیکال.

مراحل:

1. `ChartHost`: wrapper تایپ‌شدهٔ klinecharts v10 (نسخهٔ vendor موجود) — lifecycle
   React (create in useEffect، destroy in cleanup) بدون re-create در هر رندر.
2. انتقال `tech_tools.js` (ابزارهای ترسیم ۱۲۹ دکمه‌ای، پنل شناور) به
   React components — این سنگین‌ترین مرحلهٔ پروژه است؛ اول راه‌اندازی، بعد مهاجرت
   ابزار به ابزار.
3. `tech_365.js` (تنظیمات بورس‌ایجنت 365: تعدیل/نوع قیمت/مقیاس) به
   `IndicatorSettings` — با اصلاحات v9.7.1 (بدهی‌های حل‌شده: logScale، دورهٔ
   اندیکاتور بر پایهٔ تایم‌فریم RSI روزانه ۱۴ / هفتگی ۷ / EMA 20-50-200 / BOLL 20-2).
4. `useCandles` (CDN-پس از `/api/chart` با فالبک `/api/chart-db`) + `useKeyLevels`
   + `usePatterns` → overlayها با `createOverlay`.
5. `signals/technicalSignals.ts`: ستاپ‌های v9.7.4 (breakout/pullback/fibonacci/
   CHoCH/bearish_div) + مرجع حد ضرر (ma14/rising_low/swing_stop).

تحویل: `/app/technical/فولاد` با چارت تعاملی کامل؛ رگرسیون رفتاری صفر نسبت به
`tech_rtv.js` (چک‌لیست دستی ۲۰ مورد رفتار).

تست: واحد: indicators.ts (RSI/EMA/BOLL) در برابر مقادیر مرجع؛ کامپوننت:
ChartHost mount/unmount بدون نشت (تست با `getComputedStyle` هم‌ارز گارد
سرریز v9.7.1)؛ `chart_api_check_v95.py` سبز بماند.

### فاز ۵ — فیچر Portfolio (ایجنت ۴) + Signal Bus کامل (۱ هفته) · `P5`

**هدف**: کارتابل سبد + ثبت تصمیم + مستر تجمیعی نسخهٔ اول.

مراحل:

1. `usePortfolio` + `useDecisions` (POST/DELETE `/api/selection/decision`).
2. `PortfolioBoard` (کارت‌های Accept/Reject/Monitor/Pending) + `WeightEditor`
   (سقف ۲۰٪ و ۵-۷ نماد — قواعد `limits` فعلی) + `StopLossLadder` (نردبان حد ضرر).
3. `TripleMatrix`: ماتریس تایید سه‌گانه (سه ستون pass|warn|fail|nodata) —
   مصرف از `/api/selection/portfolio` (back-end موجود) + رندر `conf_reasons`.
4. Signal Bus فعال‌سازی کامل: هر ۴ فیچر publish می‌کنند (بنیادی از فاز ۳،
   تکنیکال از فاز ۴، تابلو از فاز ۲، پرتفوی همین‌جا).
5. `signals/portfolioSignals.ts`: وضعیت تصمیم‌ها و هشدارهای ریسک سبد.
6. **شروع ایجنت مستر**: `masterEngine.ts` (رأی‌گیری وزنی + compositeScore) +
   `MasterDashboard` اولیه (جدول verdict نمادهای واچ‌لیست).

تحویل: `/app/portfolio` کامل؛ `/app/master` نسخهٔ MVP (جدول + contributions).

تست: واحد: masterEngine با ۴ fixture سیگنال (توافق کامل / اختلاف شدید /
سیگنال منقضی / سیگنال خراب → discarded)؛ e2e: مسیر ثبت تصمیم تا رفرش.

### فاز ۶ — ایجنت مستر کامل (۱.۵ هفته) · `P6`

**هدف**: داشبورد تحلیلی نهایی با رادار، تایم‌لاین، Dissent Board و تنظیم وزن‌ها.

مراحل:

1. `AgentRadar` (lightweight-charts): نمودار راداری سهم ۴ ایجنت در compositeScore.
2. `SignalTimeline`: خط زمانی سیگنال‌های امروز با فیلتر ایجنت/نماد/جهت.
3. `DissentBoard`: نمادهای با `dissent.gap > 80` — کارت اختلاف با لینک به
   هر دو فیچر مبدأ (deep-link از `sourceView`).
4. `FinalVerdict`: کارت نهایی هر نماد با `usedSignalIds` قابل بازکردن (trace
   تصمیم — شفافیت کامل).
5. پنل تنظیمات مستر: وزن ۴ ایجنت + آستانه‌های finalAction (ذخیره در
   localStorage + mirror به `fts_thresholds.json` فقط برای کلیدهای مستر).
6. Playwright E2E کامل: `smoke.spec.ts` + `master-aggregation.spec.ts`
   (چرخهٔ کامل: باز کردن نماد → سیگنال ۴ ایجنت → verdict → تغییر وزن → تغییر verdict).

تحویل: داشبورد مستر production-ready با قابلیت توجیه هر تصمیم.

تست: e2e سبز روی سرور واقعی :8012؛ واحد: dissent با fixture اختلافی.

### فاز ۷ — مهاجرت و سانائه (۱ هفته) · `P7`

**هدف**: تکلیف `static/` قدیمی.

مراحل:

1. Feature-parity audit: چک‌لیست کامل قابلیت‌ها (از REPO_MAP بخش ۳) در اپ جدید.
2. ریدایرکت: `/` → `/app` (با پذیرش صریح کاربر و نگه‌داشتن `?legacy=1` برای
   rollback سریع در نسخهٔ اول).
3. حذف تدریجی `static/*.js` (فقط پس از تایید کاربر) و انتقال تست‌های JS قدیمی
   به معادل‌های Vitest.
4. به‌روزرسانی `REPO_MAP.md` و `CHANGELOG.md` (بدون ZWNJ).

تحویل: یک ترمینال واحد. اپ React به‌صورت پیش‌فرض، قدیمی پشت پرچم.

---

### ۴.۱ گانت خلاصه (۱۶-۱۷ هفته مجموع، با همپوشانی پذیر)

```
هفته:      1    2    3    4    5    6    7    8    9    10   11   12   13
P0 skeleton ████
P1 contracts     ████
P2 market             ████
P3 fundamental             ████
P4 technical                    ██████
P5 portfolio+bus                        ████
P6 master                                    ██████
P7 migration                                         ████
```

نکته: P2 و P3 قابل جابه‌جایی‌اند (هر دو فقط به P1 وابسته‌اند) و در صورت
کار موازی دو ایجنت، مسیر بحرانی به ~۱۰ هفته کوتاه می‌شود.

---

## بخش ۵ — ریسک‌ها و پروتکل‌های شکستن‌ناپذیر

### ۵.۱ ریسک‌های اصلی

| ریسک | احتمال | اثر | پاسخ |
|---|---|---|---|
| رگرسیون رفتاری چارت (P4) | بالا | بالا | چک‌لیست رفتاری ۲۰ موردی + `chart_api_check_v95.py` به‌عنوان گارد |
| تغییر payload بک‌اند | متوسط | بالا | Zod parse در `http.ts` خطای واضح می‌دهد؛ fixtureها در CI زودهنگام می‌شکنند |
| ZWNJ در فایل‌های فارسی | بالا | کم (قاعدهٔ سبکی) | ESLint rule سفارشی یا pre-commit grep (همان روش چک این سند) |
| پرفورمنس جدول ۲۵۲۰ نماد | متوسط | متوسط | TanStack Virtual + virtualization از P2 (نه در پایان) |
| کپی vendor بدون نسخهٔ درست | کم | متوسط | cache-buster `?v=` در importها حفظ شود؛ گارد «همهٔ ارجاع‌ها یک نسخه» فعلی الگو است |

### ۵.۲ پروتکل‌های شکستن‌ناپذیر (وارث REPO_MAP)

1. **`test_tsetmc.py` تست نیست** — در هیچ فازی لمس نمی‌شود؛ تشخیص «sync در حال
   اجرا» به نام پروسهٔ آن وابسته است.
2. **`market.db` در CWD می‌ماند** — پوشهٔ `data/` ساخته نمی‌شود؛ بک‌اند فقط
   mount سرو اضافه می‌گیرد.
3. **JSONهای وضعیت چند-نویسنده** (`sync_summary.json` و ...) دست نمی‌خورند.
4. **واژگان وضعیت‌ها قفل است**: `pass|warn|fail|nodata` (FTS) و
   `accept|reject|monitor|pending` (selection) — قراردادهای بخش ۳ دقیقاً همین
   واژگان را بازتاب می‌دهند تا گاردهای `watchlist_matrix_v973.py` و
   `confidence_engine_v973.py` معتبر بمانند.
5. **cache-buster یکدست**: هر تغییر asset در `frontend/` باید نسخه‌بندی
   build (hash Vite) داشته باشد؛ الگوی «همهٔ ارجاع‌ها یک نسخه» از
   `chart_api_check_v95.py` به ESLint/CI منتقل می‌شود.
6. **بدون CDN**: همهٔ وابستگی‌ها local (فونت، klinecharts، آیکون) — شبکهٔ
   کاربر فیلترشده است.

---

## پیوست A — کلیدهای تصمیم در یک نگاه

| پرسش | پاسخ | مادهٔ قانون |
|---|---|---|
| فریمورک؟ | React 18 + TS strict + Vite 5 | بخش ۱.۳ |
| استایل؟ | Tailwind 4 + توکن‌های تم فعلی | ۱.۴ |
| چارت کندل؟ | klinecharts v10 (vendor موجود) در wrapper React | ۱.۴ · فاز ۴ |
| State؟ | Zustand (سراسری: نماد/بازار؛ محلی: هر فیچر) | ۱.۴ |
| دیتا؟ | TanStack Query (polling) → بعداً WS | ۱.۴ |
| ساختار؟ | Feature-Based با قواعد مرزی B1-B6 | ۲.۲ |
| قرارداد؟ | `src/contracts/` — Zod + TS، نسخه v1 | ۳.۲ · ۳.۳ |
| مستر چگونه تجمیع می‌کند؟ | Signal Bus + رأی‌گیری وزنی + dissent | ۳.۵ · ۳.۶ |
| فازها؟ | P0→P7، ۱۶-۱۷ هفته، بحرانی ~۱۰ با موازی‌سازی | ۴.۱ |

---

*پایان سند — نسخهٔ 1.0.0 — همهٔ بخش‌ها بدون نیم‌فاصله (ZWNJ) نوشته شده‌اند.*
