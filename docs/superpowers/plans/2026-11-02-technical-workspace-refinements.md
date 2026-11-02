# برنامه اجرایی ارتقای میزکار تکنیکال بورس‌ترمینال
## (تم روشن/تاریک، تایم‌فریم‌ها، آموزش الگوها، موتور تعدیل مستقل، و اتوماسیون Agent-Desktop)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** پیاده‌سازی و یکپارچه‌سازی ۴ محور اصلی ارتقای میزکار تکنیکال (همگام‌سازی تم روشن/تاریک با KLineCharts، نوار تایم‌فریم و تجمیع کندل‌های شنبه-چهارشنبه و ماه‌های شمسی، کارت راهنمای تعاملی معامله‌گر و کالبدشکافی الگوها، و موتور محاسباتی تعدیل عملکردی مستقل در بک‌اند Go) به همراه راستی‌آزمایی زنده از طریق Agent-Desktop.

**Architecture:** 
1. در فرانت‌اند (`frontend-v2/`): مدیریت استایل‌های پویا بر اساس استور UI در `KLineChartWrapper.tsx`، موتور تجمیع کندل‌ها در `timeframeAggregation.ts`، گلاسری و آموزش تعاملی معامله‌گر در `patternGlossary.ts` و `CandleEdgeCard.tsx`.
2. در بک‌اند (`backend-go/`): موتور تعدیل عملکردی و تفکیک رویدادهای مجمع در `adjust_engine.go` بر پایه جداول `market.db`، با پاسخ‌گویی به پارامتر `adjustment` (۰: بدون تعدیل، ۱: افزایش سرمایه، ۲: سود نقدی، ۳: عملکردی).
3. اعتبارسنجی: راستی‌آزمایی بلادرنگ دسکتاپ از طریق `agent-desktop` روی ویندوز.

**Tech Stack:** React 18, TypeScript 5.9, Zustand 5, KLineCharts v10, Go 1.23, SQLite (`market.db`), Vitest, Agent-Desktop CLI.

**Spec:** `docs/superpowers/specs/2026-11-02-technical-workspace-refinements-design.md`  
**Decisions & Base Plan:** `docs/BorsTerminal-Desktop-Migration-Decisions.md` و `docs/MIGRATION-REBUILD-PLAN-2026-10-27.md`

## Global Constraints

- گارد نویسه‌های فارسی: هیچ نویسه عربی (ي/ك) یا CJK وارد نشود؛ فایل‌ها باید با `python dev/persian_glyph_guard.py` پاس شوند.
- اعداد و ارقام فارسی: استفاده انحصاری از `toFaDigits` و کلاس `.num` (tabular-nums).
- شبکه و API: تمام درخواست‌های فرانت فقط از طریق `shared/api/http.ts`.
- یکپارچگی داده: دیتابیس `market.db` هرگز دستکاری یا بازنویسی نشود.
- سازگاری بک‌اند: تست‌های Go (`go test ./...`) و تست‌های فرانت (`npx vitest run`) در تمام مراحل ۱۰۰٪ سبز بمانند.

---

### Task 1: سیستم تم پویا در چارت کانواس KLineCharts (تاریک/روشن)

**Files:**
- Modify: `frontend-v2/src/features/technical/ui/KLineChartWrapper.tsx`
- Test: `frontend-v2/src/features/technical/ui/__tests__/KLineChartWrapper.test.tsx`

**Interfaces:**
- Consumes: `useUiStore.theme` (`'brass' | 'warm' | 'terminal' | 'cool'`)
- Produces: `LIGHT_CHART_STYLES`, `BRASS_CHART_STYLES`, واکنش آنی به تغییر تم با `chart.setStyles(...)`

- [x] **Step 1: نوشتن تست شکست‌خورده برای تغییر استایل چارت در تم روشن**
  - در `KLineChartWrapper.test.tsx` تستی اضافه شود که تغییر تم به `warm` را به `useUiStore` بفرستد و تأیید کند که `chart.setStyles` با رنگ‌های پالت روشن (`LIGHT_CHART_STYLES`) فراخوانی می‌شود.

- [x] **Step 2: اجرای تست برای اطمینان از شکست اولیه**
  - اجرای `npx vitest run frontend-v2/src/features/technical/ui/__tests__/KLineChartWrapper.test.tsx`.

- [x] **Step 3: پیاده‌سازی شیء `LIGHT_CHART_STYLES` و واکنش پویا در `KLineChartWrapper.tsx`**
  - تعریف `LIGHT_CHART_STYLES`:
    - پس‌زمینه روشن: `#fbf9f5`
    - خطوط گرید: `rgba(0, 0, 0, 0.06)`
    - برچسب‌های محورها: `#4d5a66`
    - کندل صعودی: `#0d7a45`، کندل نزولی: `#b02c37`
    - کراس‌هیر: خط تیره با برچسب‌های خوانا
  - اشتراک به `useUiStore((s) => s.theme)`
  - اجرای `chart.setStyles(isLight ? LIGHT_CHART_STYLES : BRASS_CHART_STYLES)` هنگام تغییر تم.

- [x] **Step 4: اجرای تست و تأیید سبزی**
  - اجرای `npx vitest run frontend-v2/src/features/technical/ui/__tests__/KLineChartWrapper.test.tsx`.

- [x] **Step 5: بررسی تایپ‌چک و گارد فارسی**
  - اجرای `npx tsc -b` در `frontend-v2` و `python dev/persian_glyph_guard.py`.

---

### Task 2: موتور تایم‌فریم و تجمیع کندل‌های بورس تهران (۱D, ۱W, ۱M)

**Files:**
- Create: `frontend-v2/src/features/technical/model/timeframeAggregation.ts`
- Test: `frontend-v2/src/features/technical/model/__tests__/timeframeAggregation.test.ts`
- Modify: `frontend-v2/src/features/technical/model/technicalStore.ts`
- Modify: `frontend-v2/src/features/technical/ui/ForecastControls.tsx`
- Modify: `frontend-v2/src/features/technical/ui/TechnicalWorkspace.tsx`
- Modify: `frontend-v2/src/features/technical/ui/KLineChartWrapper.tsx`
- Test: `frontend-v2/src/features/technical/ui/__tests__/ForecastControls.test.tsx`

**Interfaces:**
- Produces: `aggregateCandles(rawBars: KLineData[], timeframe: '1D' | '1W' | '1M'): KLineData[]`
- Produces: تایم‌فریم‌های `1D`, `1W`, `1M` در `technicalStore` و دکمه‌های انتخاب سریع در `ForecastControls`

- [x] **Step 1: نوشتن تست شکست‌خورده برای تجمیع هفتگی و ماهانه**
  - در `timeframeAggregation.test.ts` آزمودن کندل‌های یک هفته معاملاتی شنبه تا چهارشنبه (open از شنبه، close از چهارشنبه، high بیشینه، low کمینه، مجموع حجم) و ماه‌های شمسی.

- [x] **Step 2: اجرای تست برای اطمینان از شکست اولیه**
  - اجرای `npx vitest run timeframeAggregation.test.ts`.

- [x] **Step 3: پیاده‌سازی منطق تقویمی تجمیع در `timeframeAggregation.ts`**
  - پیاده‌سازی تابع خالص `aggregateCandles` برای تایم‌فریم‌های `1D` (بدون تغییر)، `1W` (هفته معاملاتی شنبه تا چهارشنبه ایران)، `1M` (ماه شمسی تقویم جلالی).

- [x] **Step 4: اضافه کردن نوار سگمنت تایم‌فریم در `ForecastControls.tsx`**
  - تعبیه دکمه‌های `[ روزانه (1D) | هفتگی (1W) | ماهانه (1M) ]` در کنار جستجوی نماد.
  - اعمال استایل یکپارچه متناسب با تم و اتصال به `setTimeframe` در استور.

- [x] **Step 5: یکپارچه‌سازی در `TechnicalWorkspace.tsx` و `KLineChartWrapper.tsx`**
  - اعمال `aggregateCandles` روی کندل‌های خام قبل از تغذیه به KLineCharts.

- [x] **Step 6: اجرای تست‌ها و تأیید سبزی**
  - اجرای تست‌های `timeframeAggregation.test.ts` و `ForecastControls.test.tsx`.

---

### Task 3: کارت راهنمای تعاملی معامله‌گر و کالبدشکافی الگوها

**Files:**
- Create: `frontend-v2/src/features/technical/model/patternGlossary.ts`
- Test: `frontend-v2/src/features/technical/model/__tests__/patternGlossary.test.ts`
- Modify: `frontend-v2/src/features/technical/ui/CandleEdgeCard.tsx`
- Test: `frontend-v2/src/features/technical/ui/__tests__/CandleEdgeCard.test.tsx`

**Interfaces:**
- Produces: `PATTERN_GLOSSARY` دیکشنری جامع مفاهیم و الگوها با توضیحات ساده فارسی
- Produces: پنل کشویی راهنمای معامله‌گر و راهنمای لحظه‌ای الگو در `CandleEdgeCard`

- [x] **Step 1: نوشتن تست‌های شکست‌خورده برای گلاسری الگوها و محتوای راهنما**
  - تست وجود توضیحات روان برای شهاب ثاقب، چکش، پوشای صعودی/نزولی و تعاریف آماری نرخ برد، فاکتور سود و ریسک/ریوارد.

- [x] **Step 2: اجرای تست برای اطمینان از شکست**
  - اجرای `npx vitest run patternGlossary.test.ts`.

- [x] **Step 3: پیاده‌سازی `patternGlossary.ts`**
  - شرح کامل و کاربردی روانشناسی بازار برای تک‌تک الگوها (شهاب ثاقب، چکش، پوشا، دوجی، ستاره صبحگاهی و شامگاهی).
  - شرح ساده مفهوم نرخ برد ۱، ۳ و ۵ کندل: «در کل تاریخچه این سهم، در چند درصد موارد پس از این الگو، معامله‌گر به سود نشسته است».
  - شرح فاکتور سود و نسبت ریسک به ریوارد.

- [x] **Step 4: به‌روزرسانی `CandleEdgeCard.tsx` با کارت آموزشی تاشو و راهنمای لحظه‌ای**
  - اضافه کردن دکمه `راهنمای مفاهیم (؟)` در بالای کارت.
  - باز شدن پنل آموزشی با کلیک کاربر حاوی تحلیل الگوی فعال، جدول تفسیر نرخ برد و مفهوم فاکتور سود.
  - آیکون‌های راهنما در کنار اعداد نرخ برد.

- [x] **Step 5: اجرای تست‌های `CandleEdgeCard.test.tsx` و تأیید سبزی**
  - اطمینان از پاس شدن تمام تست‌ها.

---

### Task 4: موتور تعدیل عملکردی مستقل و بومی در Go Backend

**Files:**
- Create: `backend-go/internal/chart/adjust_engine.go`
- Create: `backend-go/internal/chart/adjust_engine_test.go`
- Modify: `backend-go/internal/chart/chartdb.go`
- Modify: `backend-go/internal/chart/adjust.go`
- Test: `backend-go/internal/chart/chartdb_test.go`

**Interfaces:**
- Produces: `ComputeAdjustmentFactors(rows []map[string]any, events []CorporateEvent, mode int) []float64`
- Handles:
  - `adjustment=0`: بدون تعدیل (فاکتورها ۱.۰)
  - `adjustment=1`: فقط افزایش سرمایه
  - `adjustment=2`: فقط سود نقدی
  - `adjustment=3`: عملکردی (سود نقدی + افزایش سرمایه مطابق فرمول استاندارد رهاورد ۳۶۵)

- [x] **Step 1: نوشتن تست شکست‌خورده در Go برای حالات تعدیل مختلف**
  - در `adjust_engine_test.go` تست محاسبه فاکتورها برای حالت خام (همه ۱.۰)، افزایش سرمایه (بر مبنای نسبت سهام)، و تعدیل عملکردی تجمعی به عقب.

- [x] **Step 2: اجرای تست برای اطمینان از شکست اولیه**
  - اجرای `go test -C backend-go ./internal/chart/ -run TestAdjustmentEngine`.

- [x] **Step 3: پیاده‌سازی `adjust_engine.go` در Go**
  - پیاده‌سازی فرمول‌های تجمعی ضریب به عقب O(N+M) با دقت محاسباتی بالا.
  - تفکیک رویدادها بر پایه جداول `price_adjust_events`, `share_change_events`, و `adjust_events`.
  - یکپارچه‌سازی با خروجی متد `ChartDB` در `chartdb.go`.

- [x] **Step 4: اجرای تمام تست‌های پکیج chart در بک‌اند Go**
  - اجرای `go test -C backend-go ./internal/chart/ -v`.

---

### Task 5: راستی‌آزمایی جامع، دسکتاپ اتوماسیون (Agent-Desktop) و ثبت شواهد

**Files:**
- Run: `python tools/agent_desktop_runner.py`
- Run: `npx vitest run`
- Run: `go test -C backend-go ./...`
- Run: `python dev/persian_glyph_guard.py`

- [x] **Step 1: اجرای تست‌های کامل سیستم**
  - بررسی سبزی ۱۰۰٪ تمام تست‌های فرانت (بیش از ۴۰ فایل تست).
  - بررسی سبزی تمام پکیج‌های Go در `backend-go`.
  - اجرای گارد نویسه‌های فارسی `python dev/persian_glyph_guard.py`.

- [x] **Step 2: آزمون تعاملی دسکتاپ با Agent-Desktop**
  - پایش پنجره فعال کاربر (`brave.exe`).
  - تصویربرداری از تغییر تم به روشن و تاریک، سوییچ تایم‌فریم و باز شدن کارت آموزش معامله‌گر.
  - ثبت اسکرین‌شات‌ها در آرتیفکت‌های خروجی.

- [x] **Step 3: ارائه نتایج و گزارش به کاربر**
  - گزارش کامل کارایی و تغییرات انجام‌شده با لینک مستقیم و ارائه اسکرین‌شات‌های زنده.
