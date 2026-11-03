# پلن اجرایی: دقت الگوی دوقلو W/M، احتمال تشکیل، و unslop میزکار

> **For agentic workers:** اجرا به‌صورت inline در همین نشست. هر تسک چرخهٔ تست خودش را دارد. مرجع: `docs/superpowers/specs/2026-11-03-double-pattern-precision-and-technical-workspace-design.md`

**Goal:** الگوی دوقلو W/M دقیق‌تر و قابل‌فهم‌تر شود؛ فقط الگوی آخرِ در حال تشکیل تارگت و درصدِ ترکیبی با نمونه بگیرد؛ میزکار تکنیکال چارت‌محور و unslop شود.

**Architecture:** موتور تشخیص از اورلی جدا می‌شود (`model/doubleTapEngine.ts`) و هر دو لایهٔ canvas و SVG از همان خروجی می‌خوانند. لایهٔ SVG به یک انیمیشن یک‌بارهٔ توضیحی تبدیل می‌شود. کشوی کاتالوگ پیش‌فرض بسته و در حالت باز overlay می‌شود.

**Tech Stack:** React 18، TypeScript 5.9، Zustand 5، KLineCharts 10، Vitest 3، Testing Library، Tailwind 4.

**Spec:** `docs/superpowers/specs/2026-11-03-double-pattern-precision-and-technical-workspace-design.md`

## Global Constraints

- فقط شاخهٔ `mission/4-axes-2026-10-10`؛ push بدون تأیید مالک ممنوع.
- هیچ آستانه/فرمولی از خود ساخته نمی‌شود؛ مقادیر از spec می‌آید.
- درصد فقط برای آخرین الگوی `forming`؛ نمونهٔ کمتر از ۸ ⇒ بدون درصد.
- اعداد فارسی فقط با `toFaDigits`.
- `tsc -b` صفر خطا؛ `vitest run` سبز؛ `npm run build` سبز.
- PASS بصری با مالک است؛ اسکرین‌شات + عدد ارائه می‌شود.

---

### Task 1: موتور خالص W/M + کیفیت + احتمال

**Files:**
- Create: `frontend-v2/src/features/technical/model/doubleTapEngine.ts`
- Modify: `frontend-v2/src/features/technical/model/types.ts`
- Test: `frontend-v2/src/features/technical/model/__tests__/doubleTapEngine.test.ts`

**Interfaces:**
- `detectDoubleTapPatterns(candles: Candle[], params?: Partial<DoubleTapParams>): DoubleTapPattern[]`
- `estimateFormation(patterns, candles, atr, currentId, horizon): FormationEstimate | null`
- Types: `DoubleTapParams`, `FormationEstimate { probability: number | null; successes; failures; resolved; confidence: 'none'|'low'|'medium'|'high'; horizon; method: 'same-symbol'; qualityBucket?: number }`

- [x] تست‌های نزولی/صعودی: M معتبر، W معتبر، الگوی نامعتبر (اختلاف قله‌ها > tolerance)، پیوت تأییدنشده.
- [x] تست تارگت: TP1 = neckline ∓ height، TP2 = 1.618×height، SL = peak ± 0.25 ATR.
- [x] تست احتمال: سری مصنوعی با ۳ موفق و ۱ ناموفق ⇒ `(3+1)/(4+2)`؛ نمونهٔ < ۸ ⇒ `probability=null` و `confidence='none'`.
- [x] تست آخرین الگو: فقط بزرگ‌ترین `peak2.index`؛ اگر active باشد، `estimateFormation` برایش null.
- [x] اجرای تست‌ها، سپس پیاده‌سازی minimal، سپس سبز.

### Task 2: اورلی canvas بدون نئون + تارگت فقط برای الگوی آخر

**Files:**
- Modify: `frontend-v2/src/features/technical/overlays/advancedTradingIndicators.ts` (بخش DoubleTap)
- Modify: `frontend-v2/src/features/technical/model/types.ts`
- Test: `frontend-v2/src/features/technical/overlays/__tests__/advancedTradingIndicators.test.ts` (به‌روزرسانی)

- [x] اورلی از `detectDoubleTapPatterns` بخواند؛ رسم الگوهای تاریخی کم‌رنگ و بدون برچسب درصد.
- [x] الگوی آخر: خط نازک، خط گردن dashed، TP1/TP2/SL با برچسب‌های کوچک؛ بدون `filter/drop-shadow`.
- [x] حذف `score٪` از برچسب‌ها؛ متن وضعیت «در حال تشکیل»/«تأییدشده».
- [x] تست: رسم بدون رنگ نئون؛ تارگت‌ها فقط برای آخرین الگو.

### Task 3: لایهٔ SVG توضیحی یک‌باره

**Files:**
- Create: `frontend-v2/src/features/technical/ui/PatternStoryOverlay.tsx`
- Delete: `frontend-v2/src/features/technical/ui/AnimatedPatternOverlay.tsx` (یا نگه‌داشتن نام با بازنویسی)
- Modify: `frontend-v2/src/features/technical/ui/KLineChartWrapper.tsx`
- Test: `frontend-v2/src/features/technical/ui/__tests__/PatternStoryOverlay.test.tsx`

- [x] فقط آخرین الگو را رندر کند.
- [x] انیمیشن یک‌باره: path 700ms، neckline/target 250ms، chip 150ms؛ کلاس‌های بدون `infinite`.
- [x] چیپ: «در حال تشکیل · احتمال ۶۲٪ · ۱۸ نمونه · اطمینان متوسط»؛ اگر نمونه کم: «نمونهٔ کافی نیست».
- [x] `prefers-reduced-motion` ⇒ بدون انیمیشن.
- [x] حذف CSS نئون از `KLineChartWrapper` و mount لایهٔ جدید.
- [x] تست: فقط یک الگو، بدون `filter`، بدون `infinite`، چیپ درست.

### Task 4: unslop چیدمان و کاتالوگ

**Files:**
- Modify: `frontend-v2/src/features/technical/model/technicalStore.ts`
- Modify: `frontend-v2/src/features/technical/ui/TechnicalWorkspace.tsx`
- Modify: `frontend-v2/src/features/technical/ui/WideWorkspaceDrawer.tsx`
- Test: `frontend-v2/src/features/technical/ui/__tests__/WideWorkspaceDrawer.test.tsx` (به‌روزرسانی)

- [x] `isLeftDrawerOpen: false` پیش‌فرض؛ `maxDrawnPatterns: 1`.
- [x] کشو در حالت باز overlay شود (نه shrink چارت)؛ دکمهٔ بستن واضح.
- [x] تب کاتالوگ: ردیف‌های ۳۶px، عنوان یک‌خطی + توضیح ۱۱px، سوییچ در یک ستون، حذف بج «پیش‌فرض».
- [x] تست: پیش‌فرض بسته؛ کاتالوگ ردیف‌های قابل‌کلیک؛ بدون بج رنگی.

### Task 5: سنجش و پذیرش

- [x] `npx tsc -b` صفر خطا.
- [x] `npx vitest run` سبز.
- [x] `npm run build` سبز.
- [x] اجرای زنده با Computer Use: باز کردن `#/technical/فولاد`، روشن‌کردن Double Tap، اسکرین‌شات ۱۳۶۶ و ۱۹۲۰.
- [x] اندازه‌گیری عرض چارت ≥ ۷۰٪، overflow افقی = ۰، خطای کنسول = ۰ (Playwright/CDP).
- [x] اجرای پروفایل `precision` و `source` روی فولاد و ثبت تعداد M/W/forming.
- [x] commit نهایی روی شاخه؛ بدون push.
