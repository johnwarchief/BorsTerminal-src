# بازطراحی بصری بنیادی — پلن اجرا

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** جدول پنج‌ستونهٔ بنیادی با دو حالت فشرده/راحت و کاکپیت تصویری پنج‌محور در نمای نماد، با سطح دادهٔ paper/ink، دو تم، حرکت مهارشده و حفظ کامل S4b.

**Architecture:** یک لایهٔ داده/متادیتای محور (`axisMeta`)، یک استور ترجیحات (`useFundamentalPrefs`)، توکن‌های سطح دادهٔ `--fd-*` روی صفحه، جدول مجازی پنج‌ستونه با مینی‌چارت‌های SVG، و نمای نماد مرکب از نوار پنجگانه + پنج پنل + تاریخچه + شواهد. جدول از `/api/screener` و کارت از `/api/fundamental/{symbol}` می‌آید؛ هیچ بک‌اندی تغییر نمی‌کند.

**Tech Stack:** React + TypeScript + Vite + TanStack Query/Virtual + Zustand + Zod + Tailwind 4 + Vitest/Testing Library؛ SVG درون‌خطی؛ بدون کتابخانهٔ نمودار جدید.

**Spec:** `docs/superpowers/specs/2026-11-04-fundamental-visual-redesign-design.md`

## Global Constraints

- هیچ فرمول/آستانهٔ تازه؛ همهٔ نمودارها نمایشِ فیلدهای موجود `screener`/`card` با آستانه‌های S4b.
- S4b حفظ شود: تنظیمات `FtsSettingsTrigger`، P/NAV `HoldingNavPanel`، حذف بر اساس شاخص، CSV، تقویم شرکتی و سلامت کدال.
- سطح دادهٔ پیش‌فرض `paper` (ترکیبی: پوستهٔ تم برنامه + دادهٔ روشن)؛ سطح `ink` اختیاری؛ سوییچ تم برنامه دست‌نخورده.
- `1366×768` و `1920×1080`؛ RTL و فارسی؛ ارقام با `toFaDigits/fmt*`؛ هیچ ایموجی؛ هیچ گرادیان/گلو/سایهٔ رنگی.
- رنگ تنها حامل وضعیت نیست؛ `null` بدون `na` = «نامشخص»، نه «رد».
- جدول پرتکرار: بدون entrance/loop برای ردیف‌ها؛ حرکت فقط برای توضیح تغییر حالت/نمودار.
- `fetch` فقط در `shared/api/http.ts`؛ هیچ وابستگی جدید؛ `tsc` صفر خطا و همهٔ تست‌ها سبز.
- بعد از هر تسک: `npm run typecheck` و تست‌های همان تسک؛ کامیت محلی با `-c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com"`؛ بدون push.
- Go دست‌نخورده می‌ماند؛ toolchain موجود `D:/BorsTerminal-tmp/go-toolchain/go/bin/go.exe` (1.27.3) و تست‌های `fundamental/screener/httpapi` سبزند.
- PASS بصری خوداعلام نمی‌شود؛ اسکرین‌شات دو وضوح/دو تم + رأی مالک.

---

### Task 1: متادیتای محورها، ترجیحات، اسکیما و توکن‌ها

**Files:**
- Create: `frontend-v2/src/features/fundamental/lib/axisMeta.ts`
- Create: `frontend-v2/src/features/fundamental/stores/prefs.ts`
- Modify: `frontend-v2/src/features/fundamental/api/useScreenerCore.ts`
- Modify: `frontend-v2/src/features/fundamental/api/useFtsCard.ts`
- Modify: `frontend-v2/src/app/styles.css`
- Test: `frontend-v2/src/__tests__/fundamental-axis-meta.spec.ts`
- Test: `frontend-v2/src/__tests__/fundamental-prefs.spec.ts`
- Test: `frontend-v2/src/__tests__/fundamental-schema.spec.ts`

**Interfaces:**
- Produces: `AxisKey = 'growth'|'eps'|'margin'|'sales'|'industry'`؛ `AxisStatus = 'pass'|'fail'|'na'|'unknown'`؛ `AXES`؛ `statusOf(row, axis)`؛ `valueOf(row, axis)`؛ `thresholdOf(thresholds, axis)`؛ `verdictFa(verdict)`؛ `formatAxisValue(value, axis)`؛ `useFundamentalPrefs` با `density/surface/sortKey/sortDir` و setterها.

- [ ] **Step 1: تست متادیتا و وضعیت‌ها را بنویس**

```ts
import { describe, expect, it } from 'vitest';
import { AXES, statusOf, thresholdOf, valueOf, verdictFa, type ScreenerRowLike } from '@features/fundamental/lib/axisMeta';

const row = {
  symbol: 'رنيك', score: 3, verdict: 'WATCH',
  i1_pass: false, i1_na: false, i2_pass: true, i2_na: false,
  i3_pass: false, i3_na: false, i4_pass: true, i4_na: false,
  i5_pass: true, i5_na: false,
  rev_growth: 45.9, eps_series: [1119, 1615, 1672], eps_years_available: 3,
  gross_margin: 11.5, sales_to_mcap: 1.15, profit_potential_pct: 13.2,
  pricing_mode: 'neutral',
} satisfies ScreenerRowLike;

const thresholds = { growth_min: 60, margin_min: 40, v10_sales_to_mcap_min: 0.33, profit_potential_min: 40, v10_eps_years: 3 };

describe('axis meta', () => {
  it('has the five axes in order', () => {
    expect(AXES.map((axis) => axis.key)).toEqual(['growth', 'eps', 'margin', 'sales', 'industry']);
    expect(AXES.map((axis) => axis.num)).toEqual(['۱', '۲', '۳', '۴', '۵']);
  });
  it('derives pass/fail/na/unknown from the row flags', () => {
    expect(statusOf(row, 'growth')).toBe('fail');
    expect(statusOf(row, 'eps')).toBe('pass');
    expect(statusOf({ ...row, i3_pass: null, i3_na: true }, 'margin')).toBe('na');
    expect(statusOf({ ...row, i2_pass: null, i2_na: false }, 'eps')).toBe('unknown');
  });
  it('reads the axis value and threshold', () => {
    expect(valueOf(row, 'growth')).toBe(45.9);
    expect(valueOf(row, 'eps')).toBe(1672);
    expect(valueOf(row, 'industry')).toBe('neutral');
    expect(thresholdOf(thresholds, 'growth')).toBe(60);
    expect(thresholdOf(thresholds, 'sales')).toBe(0.33);
  });
  it('localizes verdicts', () => {
    expect(verdictFa('STRONG')).toBe('قوی');
    expect(verdictFa('WATCH')).toBe('تحت نظر');
    expect(verdictFa('REJECT')).toBe('رد');
    expect(verdictFa('EXCLUDED')).toBe('خارج از غربال');
  });
});
```

- [ ] **Step 2: تست ترجیحات و اسکیما**

```ts
import { beforeEach, describe, expect, it } from 'vitest';
import { useFundamentalPrefs } from '@features/fundamental/stores/prefs';

beforeEach(() => {
  useFundamentalPrefs.setState({ density: 'comfortable', surface: 'paper', sortKey: 'score', sortDir: 'desc' });
});

describe('fundamental prefs', () => {
  it('defaults to comfortable/paper/score desc', () => {
    const s = useFundamentalPrefs.getState();
    expect([s.density, s.surface, s.sortKey, s.sortDir]).toEqual(['comfortable', 'paper', 'score', 'desc']);
  });
  it('updates density, surface and sort', () => {
    useFundamentalPrefs.getState().setDensity('compact');
    useFundamentalPrefs.getState().setSurface('ink');
    useFundamentalPrefs.getState().setSort('margin', 'asc');
    const s = useFundamentalPrefs.getState();
    expect([s.density, s.surface, s.sortKey, s.sortDir]).toEqual(['compact', 'ink', 'margin', 'asc']);
  });
});
```

```ts
import { describe, expect, it } from 'vitest';
import { ScreenerCoreSchema } from '@features/fundamental/api/useScreenerCore';

describe('screener schema', () => {
  it('accepts thresholds, eps series and timestamps', () => {
    const parsed = ScreenerCoreSchema.parse({
      status: 'success', count: 1, as_of: 1793789441,
      thresholds: { growth_min: 60, margin_min: 40, v10_sales_to_mcap_min: 0.33, profit_potential_min: 40 },
      data: [{ symbol: 'رنيك', eps_series: [1119, 1615, 1672], margin_tier: 'below', i1a_pass: true, i1b_pass: false, i4_na: false }],
    });
    expect(parsed.thresholds?.growth_min).toBe(60);
    expect(parsed.data[0]?.eps_series).toEqual([1119, 1615, 1672]);
  });
});
```

- [ ] **Step 3: اجرا و دیدن شکست**

Run: `cd frontend-v2 && npx vitest run src/__tests__/fundamental-axis-meta.spec.ts src/__tests__/fundamental-prefs.spec.ts src/__tests__/fundamental-schema.spec.ts`
Expected: FAIL — ماژول‌ها/فیلدها وجود ندارند.

- [ ] **Step 4: پیاده‌سازی axisMeta**

```ts
import type { ScreenerCoreRow } from '../api/useScreenerCore';

export type AxisKey = 'growth' | 'eps' | 'margin' | 'sales' | 'industry';
export type AxisStatus = 'pass' | 'fail' | 'na' | 'unknown';
export type ScreenerRowLike = Pick<ScreenerCoreRow,
  'symbol' | 'score' | 'verdict' | 'i1_pass' | 'i1_na' | 'i2_pass' | 'i2_na' |
  'i3_pass' | 'i3_na' | 'i4_pass' | 'i4_na' | 'i5_pass' | 'i5_na' |
  'rev_growth' | 'eps_series' | 'eps_years_available' | 'gross_margin' |
  'sales_to_mcap' | 'profit_potential_pct' | 'pricing_mode'
>;

export interface AxisThresholds {
  growth_min?: number | null; margin_min?: number | null; margin_optimal?: number | null;
  v10_sales_to_mcap_min?: number | null; profit_potential_min?: number | null; v10_eps_years?: number | null;
}

export const AXES = [
  { key: 'growth', num: '۱', label: 'رشد فروش', short: 'رشد', thresholdKey: 'growth_min' },
  { key: 'eps', num: '۲', label: 'سودآوری ۳ساله', short: 'سودآوری', thresholdKey: 'v10_eps_years' },
  { key: 'margin', num: '۳', label: 'حاشیهٔ ناخالص', short: 'حاشیه', thresholdKey: 'margin_min' },
  { key: 'sales', num: '۴', label: 'فروش / ارزش', short: 'فروش/ارزش', thresholdKey: 'v10_sales_to_mcap_min' },
  { key: 'industry', num: '۵', label: 'نرخ‌گذاری صنعت', short: 'صنعت', thresholdKey: null },
] as const;
export type AxisMeta = (typeof AXES)[number];

const PASS_KEYS: Record<AxisKey, [keyof ScreenerCoreRow, keyof ScreenerCoreRow]> = {
  growth: ['i1_pass', 'i1_na'], eps: ['i2_pass', 'i2_na'], margin: ['i3_pass', 'i3_na'],
  sales: ['i4_pass', 'i4_na'], industry: ['i5_pass', 'i5_na'],
};

export function statusOf(row: ScreenerRowLike, axis: AxisKey): AxisStatus {
  const [passKey, naKey] = PASS_KEYS[axis];
  const pass = row[passKey];
  if (pass === true) return 'pass';
  if (pass === false) return 'fail';
  if (row[naKey] === true) return 'na';
  return 'unknown';
}

export function valueOf(row: ScreenerRowLike, axis: AxisKey): number | string | null {
  switch (axis) {
    case 'growth': return row.rev_growth ?? null;
    case 'eps': return Array.isArray(row.eps_series) && row.eps_series.length ? row.eps_series[row.eps_series.length - 1] ?? null : null;
    case 'margin': return row.gross_margin ?? null;
    case 'sales': return row.sales_to_mcap ?? row.profit_potential_pct ?? null;
    case 'industry': return row.pricing_mode ?? null;
  }
}

export function thresholdOf(thresholds: AxisThresholds | null | undefined, axis: AxisKey): number | null {
  if (!thresholds) return null;
  if (axis === 'growth') return thresholds.growth_min ?? 40;
  if (axis === 'eps') return thresholds.v10_eps_years ?? 3;
  if (axis === 'margin') return thresholds.margin_min ?? 20;
  if (axis === 'sales') return thresholds.v10_sales_to_mcap_min ?? 0.33;
  return null;
}

export function verdictFa(verdict: string | null | undefined): string {
  return ({ STRONG: 'قوی', WATCH: 'تحت نظر', REJECT: 'رد', EXCLUDED: 'خارج از غربال' } as Record<string, string>)[verdict ?? ''] ?? '—';
}

import { toFaDigits } from '@shared/lib/fa';

export function formatAxisValue(value: number | string | null, axis: AxisKey): string {
  if (value == null) return '—';
  if (axis === 'industry') return ({ free: 'آزاد', neutral: 'خنثی', mandatory: 'دستوری' } as Record<string, string>)[String(value)] ?? '—';
  if (axis === 'eps') return toFaDigits(Math.round(Number(value)));
  if (axis === 'sales') return toFaDigits(Number(value).toFixed(2)).replace('.', '٫');
  const n = Number(value);
  const prefix = axis === 'growth' && n > 0 ? '+' : n < 0 ? '−' : '';
  return `${prefix}${toFaDigits(Math.abs(n).toFixed(1)).replace('.', '٫')}٪`;
}
```

- [ ] **Step 5: پیاده‌سازی پیکربندی**

```ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type Density = 'compact' | 'comfortable';
export type Surface = 'paper' | 'ink';
export type SortKey = 'score' | 'symbol' | 'growth' | 'eps' | 'margin' | 'sales' | 'industry';
export type SortDir = 'asc' | 'desc';

interface FundamentalPrefs {
  density: Density; surface: Surface; sortKey: SortKey; sortDir: SortDir;
  setDensity: (density: Density) => void;
  setSurface: (surface: Surface) => void;
  setSort: (sortKey: SortKey, sortDir: SortDir) => void;
}

export const useFundamentalPrefs = create<FundamentalPrefs>()(
  persist(
    (set) => ({
      density: 'comfortable', surface: 'paper', sortKey: 'score', sortDir: 'desc',
      setDensity: (density) => set({ density }),
      setSurface: (surface) => set({ surface }),
      setSort: (sortKey, sortDir) => set({ sortKey, sortDir }),
    }),
    { name: 'bors-fundamental-v1' },
  ),
);
```

- [ ] **Step 6: گسترش اسکیماها**

در `useScreenerCore.ts` به `ScreenerCoreRowSchema` اضافه کن:

```ts
thresholds: z.looseObject({
  growth_min: Num, margin_min: Num, margin_optimal: Num,
  v10_sales_to_mcap_min: Num, profit_potential_min: Num, v10_eps_years: Num,
}).nullish(),
eps_series: z.array(z.number().nullable()).nullish(),
eps_years_available: Num,
eps_data_gap: Bool,
margin_tier: Str,
i1a_pass: Bool, i1b_pass: Bool, i1b_applicable: Bool,
i4a_pass: Bool, i4b_pass: Bool, i4_na: Bool, i5_na: Bool,
rev_growth: Num, gross_margin: Num, sales_to_mcap: Num,
profit_potential_pct: Num, pricing_mode: Str,
```

و در `ScreenerCoreSchema`:

```ts
thresholds: z.looseObject({
  growth_min: Num, margin_min: Num, margin_optimal: Num,
  v10_sales_to_mcap_min: Num, profit_potential_min: Num, v10_eps_years: Num,
}).nullish(),
```

در `useFtsCard.ts` به `Axis2Schema` اضافه کن: `net_profit_series: z.array(z.number().nullable()).nullish(), period_ends: z.array(Str).nullish(), evidence: Str, consolidated_used: Bool, audited_only: Bool`؛ به `Axis3Schema`: `gross_profit_bt: Num, revenue_bt: Num, optimal_threshold: Num, na: Bool, reason: Str`؛ به `Axis4Schema`: `potential_pct: Num, potential_threshold: Num, annual_sales_bt: Num, months_used: Num, annualize_basis: Str, na: Bool, exempt: Bool`؛ به `Axis5Schema`: `verdict: Str, label: Str, sector: Str, market_share_pct: Num, outlook: Str, regime_label: Str, rule_ref: Str, pass: Bool`؛ و به شِما: `history: z.array(z.looseObject({ period_end: Str, fiscal_year: Str, revenue: Num, gross_profit: Num, net_profit: Num, eps: Num, audited: Bool, consolidated: Bool })).nullish()` و `metrics: z.looseObject({ mcap: Num, annual_sales_bt: Num, revenue: Num, sales_to_mcap: Num, ps: Num, gross_margin: Num, net_margin: Num, growth_pct: Num }).nullish()`.

- [ ] **Step 7: توکن‌های سطح داده**

در `styles.css` بعد از worldها اضافه کن:

```css
.fundamental-surface[data-fund-surface='paper'] {
  --fd-bg: #efece4; --fd-panel: #fbf9f5; --fd-panel-2: #f4f1e9; --fd-panel-3: #eae5da;
  --fd-line: #ddd6c8; --fd-line-strong: #c7bead; --fd-text: #1c1a16; --fd-text-2: #57524a; --fd-text-3: #6f695d;
  --fd-accent: #94651a; --fd-up: #0d7a45; --fd-down: #b02c37; --fd-warn: #8a5a08; --fd-flat: #6d675c;
  --fd-grid: rgba(109,103,92,.16);
}
.fundamental-surface[data-fund-surface='ink'] {
  --fd-bg: #101215; --fd-panel: #15181c; --fd-panel-2: #1a1e23; --fd-panel-3: #20252b;
  --fd-line: #2a2f36; --fd-line-strong: #363d46; --fd-text: #e2ddd2; --fd-text-2: #a9a396; --fd-text-3: #908a7e;
  --fd-accent: #c9a45c; --fd-up: #4fbd8c; --fd-down: #e07480; --fd-warn: #d3a04a; --fd-flat: #8f8a80;
  --fd-grid: rgba(154,160,168,.14);
}
.fundamental-surface .fd-status--pass { color: var(--fd-up); }
.fundamental-surface .fd-status--fail { color: var(--fd-down); }
.fundamental-surface .fd-status--na { color: var(--fd-flat); }
.fundamental-surface .fd-status--unknown { color: var(--fd-warn); }
.fundamental-surface .fd-chart-track { fill: color-mix(in srgb, var(--fd-text-3) 16%, transparent); }
.fundamental-surface .fd-chart-fill { fill: var(--fd-up); }
.fundamental-surface .fd-chart-fill.is-fail { fill: var(--fd-down); }
.fundamental-surface .fd-chart-fill.is-na { fill: var(--fd-flat); }
.fundamental-surface .fd-chart-fill.is-unknown { fill: var(--fd-warn); }
.fundamental-surface .fd-chart-bar { fill: var(--fd-up); }
.fundamental-surface .fd-chart-bar.is-fail { fill: var(--fd-down); }
.fundamental-surface .fd-chart-bar.is-na { fill: var(--fd-flat); }
.fundamental-surface .fd-chart-bar.is-unknown { fill: var(--fd-warn); }
.fundamental-surface .fd-th-line { stroke: var(--fd-accent); stroke-width: 1; stroke-dasharray: 2 2; opacity: .9; }
.fundamental-surface .fd-chart-tick { stroke: var(--fd-line-strong); stroke-width: .8; }
.fundamental-surface .fd-chart-text { fill: var(--fd-text-3); font-family: var(--font-code); }
.fundamental-surface .fd-regime-dot { background: var(--fd-line-strong); }
.fundamental-surface .fd-regime-dot.is-active.is-pass { background: var(--fd-up); }
.fundamental-surface .fd-regime-dot.is-active.is-fail { background: var(--fd-down); }
.fundamental-surface .fd-regime-dot.is-active.is-na { background: var(--fd-flat); }
.fundamental-surface .fd-regime-dot.is-active.is-unknown { background: var(--fd-warn); }
.fundamental-surface .fd-glyph span { background: var(--fd-line-strong); }
.fundamental-surface .fd-glyph span.is-pass { background: var(--fd-up); }
.fundamental-surface .fd-glyph span.is-fail { background: var(--fd-down); }
.fundamental-surface .fd-glyph span.is-na { background: var(--fd-flat); }
.fundamental-surface .fd-glyph span.is-unknown { background: var(--fd-warn); }
```

- [ ] **Step 8: اجرای تست‌ها و کامیت**

Run: `cd frontend-v2 && npm run typecheck && npx vitest run src/__tests__/fundamental-axis-meta.spec.ts src/__tests__/fundamental-prefs.spec.ts src/__tests__/fundamental-schema.spec.ts`
Expected: PASS.

```bash
git add frontend-v2/src/features/fundamental/lib/axisMeta.ts frontend-v2/src/features/fundamental/stores/prefs.ts frontend-v2/src/features/fundamental/api/useScreenerCore.ts frontend-v2/src/features/fundamental/api/useFtsCard.ts frontend-v2/src/app/styles.css frontend-v2/src/__tests__/fundamental-axis-meta.spec.ts frontend-v2/src/__tests__/fundamental-prefs.spec.ts frontend-v2/src/__tests__/fundamental-schema.spec.ts
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(fundamental): متادیتای پنج محور، ترجیحات و توکن‌های سطح داده"
```

---

### Task 2: مینی‌چارت‌ها و گلیف پنج‌محور

**Files:**
- Create: `frontend-v2/src/features/fundamental/ui/mini/Bullet.tsx`
- Create: `frontend-v2/src/features/fundamental/ui/mini/EpsBars.tsx`
- Create: `frontend-v2/src/features/fundamental/ui/mini/RegimeGlyph.tsx`
- Create: `frontend-v2/src/features/fundamental/ui/mini/AxisGlyph.tsx`
- Create: `frontend-v2/src/features/fundamental/ui/mini/PeDots.tsx`
- Create: `frontend-v2/src/features/fundamental/ui/mini/HistoryBars.tsx`
- Test: `frontend-v2/src/__tests__/fundamental-mini.spec.tsx`

**Interfaces:**
- Consumes: `AxisStatus` از Task 1.
- Produces: `Bullet({ value, max, threshold, status, height, label })`؛ `EpsBars({ series, status, height, label })`؛ `RegimeGlyph({ regime, status })`؛ `AxisGlyph({ statuses, labels })`؛ `PeDots({ pe, median, peers })`؛ `HistoryBars({ values, labels, status })`.

- [ ] **Step 1: تست مینی‌چارت‌ها**

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Bullet } from '@features/fundamental/ui/mini/Bullet';
import { EpsBars } from '@features/fundamental/ui/mini/EpsBars';
import { RegimeGlyph } from '@features/fundamental/ui/mini/RegimeGlyph';
import { AxisGlyph } from '@features/fundamental/ui/mini/AxisGlyph';

describe('mini charts', () => {
  it('renders a bullet with threshold and aria label', () => {
    render(<Bullet value={45.9} max={200} threshold={60} status="fail" label="رشد ۴۵٫۹ در برابر آستانهٔ ۶۰" />);
    const img = screen.getByRole('img', { name: /آستانه/ });
    expect(img).toBeTruthy();
    expect(img.querySelectorAll('rect').length).toBeGreaterThanOrEqual(2);
    expect(img.querySelector('.fd-th-line')).toBeTruthy();
  });
  it('renders three EPS bars', () => {
    render(<EpsBars series={[1119, 1615, 1672]} status="pass" label="سری EPS" />);
    expect(screen.getByRole('img', { name: 'سری EPS' }).querySelectorAll('rect').length).toBe(3);
  });
  it('renders three regime dots with the active one', () => {
    render(<RegimeGlyph regime="neutral" status="pass" />);
    expect(document.querySelectorAll('.fd-regime-dot').length).toBe(3);
    expect(document.querySelector('.fd-regime-dot.is-active')).toBeTruthy();
  });
  it('renders a five-bar glyph with status classes', () => {
    render(<AxisGlyph statuses={['pass', 'fail', 'na', 'unknown', 'pass']} labels={['رشد', 'EPS', 'حاشیه', 'فروش', 'صنعت']} />);
    expect(screen.getByRole('img', { name: /پنج محور/ }).querySelectorAll('span').length).toBe(5);
    expect(document.querySelectorAll('.is-fail').length).toBe(1);
  });
});
```

- [ ] **Step 2: اجرا و شکست**

Run: `cd frontend-v2 && npx vitest run src/__tests__/fundamental-mini.spec.tsx`
Expected: FAIL — ماژول‌ها وجود ندارند.

- [ ] **Step 3: پیاده‌سازی Bullet/EpsBars/RegimeGlyph/AxisGlyph**

```tsx
// Bullet.tsx
import type { AxisStatus } from '../../lib/axisMeta';

export function Bullet({ value, max, threshold, status, height = 22, label }: {
  value: number | null; max: number; threshold: number | null; status: AxisStatus; height?: number; label: string;
}) {
  const ratio = value == null ? 0 : Math.max(0, Math.min(1, value / max));
  const th = threshold == null ? null : Math.max(0, Math.min(1, threshold / max));
  return (
    <svg viewBox={`0 0 100 ${height}`} preserveAspectRatio="none" role="img" aria-label={label} className="h-full w-full overflow-visible">
      <rect className="fd-chart-track" x="0" y={height / 2 - 4} width="100" height="8" rx="3" />
      <rect className={`fd-chart-fill is-${status}`} x="0" y={height / 2 - 4} width={ratio * 100} height="8" rx="3" />
      {th == null ? null : <line className="fd-th-line" x1={th * 100} y1={height / 2 - 7} x2={th * 100} y2={height / 2 + 7} />}
    </svg>
  );
}
```

```tsx
// EpsBars.tsx
import type { AxisStatus } from '../../lib/axisMeta';

export function EpsBars({ series, status, height = 24, label }: {
  series: readonly (number | null)[] | null | undefined; status: AxisStatus; height?: number; label: string;
}) {
  const values = Array.isArray(series) ? series : [];
  const max = Math.max(1, ...values.map((v) => Math.abs(v ?? 0)));
  const width = 100;
  const barWidth = values.length ? Math.min(18, (width - 6) / values.length - 4) : 12;
  const gap = values.length > 1 ? (width - 6 - barWidth * values.length) / (values.length - 1) : 0;
  return (
    <svg viewBox={`0 0 100 ${height}`} preserveAspectRatio="none" role="img" aria-label={label} className="h-full w-full overflow-visible">
      {values.map((v, i) => {
        const h = Math.max(2, (Math.abs(v ?? 0) / max) * (height - 4));
        return <rect key={i} className={`fd-chart-bar is-${status}`} x={3 + i * (barWidth + gap)} y={height - h} width={barWidth} height={h} rx="1.5"><title>{v == null ? '—' : String(v)}</title></rect>;
      })}
      <line className="fd-chart-tick" x1="0" y1={height - 1} x2="100" y2={height - 1} />
    </svg>
  );
}
```

```tsx
// RegimeGlyph.tsx
import type { AxisStatus } from '../../lib/axisMeta';
// status === 'pass' اگر رژیم رتبه دارد؛ برای رژیم فعال از is-pass/is-fail/is-unknown
export function RegimeGlyph({ regime, status }: { regime: string | null; status: AxisStatus }) {
  const order = ['free', 'neutral', 'mandatory'];
  const active = regime ? order.indexOf(regime) : -1;
  return (
    <div className="flex h-full items-center justify-center gap-1" role="img" aria-label={`رژیم ${regime ?? 'نامشخص'}`}>
      {order.map((key, i) => (
        <span key={key} className={`fd-regime-dot h-2 w-2 rounded-full ${i === active ? `is-active is-${status}` : ''}`} title={key} />
      ))}
    </div>
  );
}
```

```tsx
// AxisGlyph.tsx
import type { AxisStatus } from '../../lib/axisMeta';

export function AxisGlyph({ statuses, labels }: { statuses: AxisStatus[]; labels: string[] }) {
  return (
    <div className="fd-glyph flex h-full items-end justify-center gap-0.5" role="img" aria-label={`پنج محور: ${statuses.map((s, i) => `${labels[i]} ${s}`).join('، ')}`}>
      {statuses.map((status, i) => {
        const h = status === 'pass' ? 22 : status === 'fail' ? 16 : status === 'na' ? 8 : 12;
        return <span key={i} className={`w-1 rounded-sm is-${status}`} style={{ height: h }} title={`${labels[i]} — ${status}`} />;
      })}
    </div>
  );
}
```

`PeDots`/`HistoryBars` بعد از مینی‌چارت‌های بالا برای پنل‌ها در Task 5 استفاده می‌شوند؛ همین حالا با همان الگوی SVG بساز:

```tsx
// PeDots.tsx
export function PeDots({ pe, median, peers }: { pe: number | null | undefined; median: number | null | undefined; peers: number | null | undefined }) {
  const max = Math.max(pe ?? 0, median ?? 0, 1) * 1.2;
  const x = (v: number) => (v / max) * 100;
  return (
    <svg viewBox="0 0 100 18" role="img" aria-label={`P/E ${pe ?? '—'} در برابر میانهٔ ${median ?? '—'}`} className="h-full w-full overflow-visible">
      <line className="fd-chart-tick" x1="0" y1="9" x2="100" y2="9" />
      {median != null ? <line className="fd-th-line" x1={x(median)} y1="4" x2={x(median)} y2="14" /> : null}
      {pe != null ? <circle className="fd-chart-fill" cx={x(pe)} cy="9" r="3" /> : null}
      <text x="0" y="17" className="fd-chart-text" fontSize="4">{peers == null ? '' : `${peers} همتا`}</text>
    </svg>
  );
}
```

```tsx
// HistoryBars.tsx
import type { AxisStatus } from '../../lib/axisMeta';

export function HistoryBars({ values, labels, status }: { values: Array<number | null>; labels: string[]; status: AxisStatus }) {
  const max = Math.max(1, ...values.map((v) => Math.abs(v ?? 0)));
  return (
    <div className="flex h-full items-end gap-1" role="img" aria-label="تاریخچهٔ گزارش‌ها">
      {values.map((v, i) => (
        <div key={i} className="flex min-w-0 flex-1 flex-col items-center justify-end gap-1" title={`${labels[i]} — ${v ?? '—'}`}>
          <span className={`w-full rounded-t-sm is-${status}`} style={{ height: `${Math.max(2, (Math.abs(v ?? 0) / max) * 100)}%`, background: `var(--fd-${status === 'pass' ? 'up' : status === 'fail' ? 'down' : 'flat'})` }} />
          <span className="truncate text-[9px] text-[var(--fd-text-3)]">{labels[i]}</span>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: تست و کامیت**

Run: `cd frontend-v2 && npm run typecheck && npx vitest run src/__tests__/fundamental-mini.spec.tsx`
Expected: PASS.

```bash
git add frontend-v2/src/features/fundamental/ui/mini frontend-v2/src/__tests__/fundamental-mini.spec.tsx
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(fundamental): مینی‌چارت‌ها و گلیف پنج‌محور"
```

---

### Task 3: جدول پنج‌ستونه، دو حالت و مجازی‌سازی

**Files:**
- Create: `frontend-v2/src/features/fundamental/ui/FundamentalAxisCell.tsx`
- Rewrite: `frontend-v2/src/features/fundamental/ui/FundamentalScreenTable.tsx`
- Test: `frontend-v2/src/__tests__/fundamental-table-visual.spec.tsx`

**Interfaces:**
- Consumes: `AXES`/`statusOf`/`valueOf`/`thresholdOf`/`formatAxisValue`/`verdictFa` (Task 1)، `Bullet`/`EpsBars`/`RegimeGlyph`/`AxisGlyph` (Task 2)، `useFundamentalPrefs` (Task 1)، `useExcludeAxes`/`applyExcludeFilter` (S4b).
- Produces: `FundamentalScreenTable({ rows, thresholds, onSelect, asOf, settingsSlot })`.

- [ ] **Step 1: تست جدول**

```tsx
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FundamentalScreenTable } from '@features/fundamental/ui/FundamentalScreenTable';
import { useFundamentalPrefs } from '@features/fundamental/stores/prefs';
import { resetExcludeAxes } from '@features/fundamental/lib/exclusionFilter';
import type { ScreenerCoreRow } from '@features/fundamental/api/useScreenerCore';

const rows: ScreenerCoreRow[] = [
  { symbol: 'رنيك', name: 'جنرال مکانیک', sector_name: 'خدمات فنی', score: 3, verdict: 'WATCH',
    i1_pass: false, i1_na: false, i2_pass: true, i2_na: false, i3_pass: false, i3_na: false,
    i4_pass: true, i4_na: false, i5_pass: true, i5_na: false,
    rev_growth: 45.9, eps_series: [1119, 1615, 1672], eps_years_available: 3,
    gross_margin: 11.5, sales_to_mcap: 1.15, profit_potential_pct: 13.2, pricing_mode: 'neutral' },
  { symbol: 'وبملت', name: 'بانک ملت', sector_name: 'بانک‌ها', score: 2, verdict: 'REJECT',
    i1_pass: true, i1_na: false, i2_pass: false, i2_na: false, i3_pass: null, i3_na: true,
    i4_pass: null, i4_na: true, i5_pass: true, i5_na: false,
    rev_growth: 83.5, eps_series: [1425, 454, 456], eps_years_available: 3,
    gross_margin: null, sales_to_mcap: null, profit_potential_pct: null, pricing_mode: 'free' },
];
const thresholds = { growth_min: 60, margin_min: 40, v10_sales_to_mcap_min: 0.33, profit_potential_min: 40, v10_eps_years: 3 };

beforeEach(() => {
  resetExcludeAxes();
  useFundamentalPrefs.setState({ density: 'comfortable', surface: 'paper', sortKey: 'score', sortDir: 'desc' });
});
afterEach(cleanup);

describe('fundamental table visual', () => {
  it('renders five axis headers and values', () => {
    render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf="۱۴۰۵/۰۸/۱۳" />);
    for (const name of ['رشد فروش', 'سودآوری ۳ساله', 'حاشیهٔ ناخالص', 'فروش / ارزش', 'نرخ‌گذاری صنعت']) expect(screen.getByText(name)).toBeTruthy();
    expect(screen.getByText('+۴۵٫۹٪')).toBeTruthy();
    expect(screen.getByText('۱٫۱۵')).toBeTruthy();
  });
  it('shows charts only in comfortable mode', () => {
    const { container, rerender } = render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    expect(container.querySelectorAll('svg[role="img"]').length).toBeGreaterThan(0);
    useFundamentalPrefs.setState({ density: 'compact' });
    rerender(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    expect(container.querySelectorAll('svg[role="img"]').length).toBe(0);
  });
  it('distinguishes N/A/unknown and bank badges', () => {
    render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    expect(screen.getByTestId('fundamental-bank-وبملت')).toBeTruthy();
    expect(document.querySelectorAll('.fd-status--na').length).toBeGreaterThan(0);
  });
  it('sorts by a header and calls onSelect', () => {
    const onSelect = vi.fn();
    render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={onSelect} asOf={null} />);
    fireEvent.click(screen.getByRole('button', { name: /جستجو/ }));
    fireEvent.change(screen.getByTestId('fundamental-search'), { target: { value: 'رنيك' } });
    fireEvent.click(screen.getByTestId('fundamental-row-رنيك'));
    expect(onSelect).toHaveBeenCalledWith('رنيك');
  });
});
```

- [ ] **Step 2: اجرا و شکست**

Run: `cd frontend-v2 && npx vitest run src/__tests__/fundamental-table-visual.spec.tsx`
Expected: FAIL — جدول فعلی پنج ستون/چارت/بانک ندارد.

- [ ] **Step 3: پیاده‌سازی AxisCell و جدول**

`FundamentalAxisCell.tsx`:

```tsx
import { useFundamentalPrefs } from '../stores/prefs';
import { AXES, formatAxisValue, statusOf, thresholdOf, type AxisKey, type AxisThresholds } from '../lib/axisMeta';
import { Bullet } from './mini/Bullet';
import { EpsBars } from './mini/EpsBars';
import { RegimeGlyph } from './mini/RegimeGlyph';
import type { ScreenerCoreRow } from '../api/useScreenerCore';

const STATUS_WORD = { pass: 'قبول', fail: 'رد', na: 'بی‌نظر', unknown: 'نامشخص' } as const;
const STATUS_ICON = { pass: '✓', fail: '✕', na: '−', unknown: '?' } as const;

export function FundamentalAxisCell({ row, axis, thresholds }: { row: ScreenerCoreRow; axis: AxisKey; thresholds: AxisThresholds | null | undefined }) {
  const density = useFundamentalPrefs((s) => s.density);
  const meta = AXES.find((a) => a.key === axis)!;
  const status = statusOf(row as never, axis);
  const value = axis === 'eps' ? `${row.eps_years_available ?? 0}/۳` : formatAxisValue(
    axis === 'growth' ? row.rev_growth ?? null : axis === 'margin' ? row.gross_margin ?? null : axis === 'sales' ? row.sales_to_mcap ?? row.profit_potential_pct ?? null : row.pricing_mode ?? null,
    axis,
  );
  const threshold = thresholdOf(thresholds, axis);
  return (
    <div className="fd-axis-cell flex min-w-0 flex-col gap-1 px-1.5 py-1" data-testid={`fundamental-cell-${row.symbol}-${axis}`}>
      <div className="flex items-baseline gap-1.5">
        <b className="fd-axis-value text-[12px] font-medium tabular-nums text-[var(--fd-text)]">{value}</b>
        <span className={`fd-status fd-status--${status} inline-flex items-center gap-0.5 text-[10px]`} title={STATUS_WORD[status]}>{STATUS_ICON[status]} {STATUS_WORD[status]}</span>
      </div>
      {density === 'comfortable' ? (
        <div className="fd-axis-chart h-[24px]">
          {axis === 'growth' ? <Bullet value={row.rev_growth ?? null} max={200} threshold={threshold} status={status} label={`${meta.label} ${value}`} /> : null}
          {axis === 'eps' ? <EpsBars series={row.eps_series} status={status} label="سری EPS" /> : null}
          {axis === 'margin' ? <Bullet value={row.gross_margin ?? null} max={60} threshold={threshold} status={status} label={`${meta.label} ${value}`} /> : null}
          {axis === 'sales' ? <Bullet value={row.sales_to_mcap ?? null} max={2} threshold={threshold} status={status} label={`${meta.label} ${value}`} /> : null}
          {axis === 'industry' ? <RegimeGlyph regime={row.pricing_mode ?? null} status={status} /> : null}
        </div>
      ) : null}
      <span className="fd-axis-threshold truncate text-[9.5px] text-[var(--fd-text-3)]">
        {axis === 'eps' ? '۳ سال' : axis === 'industry' ? row.sector_name ?? '—' : threshold == null ? '—' : `کف ${axis === 'sales' ? threshold.toFixed(2) : `${threshold}٪`}`}
      </span>
    </div>
  );
}
```

`FundamentalScreenTable.tsx` (ساختار کامل):

```tsx
import { useMemo, useRef, useState, type ReactNode } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { fmtInt } from '@shared/lib/fa';
import { useFundamentalPrefs, type SortKey } from '../stores/prefs';
import { AXES, statusOf, verdictFa, type AxisThresholds, type ScreenerCoreRowLike } from '../lib/axisMeta';
import { useExcludeAxes, applyExcludeFilter, EXCLUDE_LABEL } from '../lib/exclusionFilter';
import { FundamentalAxisCell } from './FundamentalAxisCell';
import { AxisGlyph } from './mini/AxisGlyph';
import type { ScreenerCoreRow } from '../api/useScreenerCore';

const COLUMNS = '38px 154px repeat(5, minmax(112px, 1fr)) 62px 88px';
const SORT_KEYS: SortKey[] = ['symbol', 'growth', 'eps', 'margin', 'sales', 'industry', 'score'];

function sortValue(row: ScreenerCoreRow, key: SortKey): number | string | null {
  if (key === 'symbol') return row.symbol;
  if (key === 'score') return row.score ?? null;
  if (key === 'growth') return row.rev_growth ?? null;
  if (key === 'eps') return row.eps_series?.length ? row.eps_series[row.eps_series.length - 1] ?? null : null;
  if (key === 'margin') return row.gross_margin ?? null;
  if (key === 'sales') return row.sales_to_mcap ?? row.profit_potential_pct ?? null;
  if (key === 'industry') return ({ free: 0, neutral: 1, mandatory: 2 } as Record<string, number>)[row.pricing_mode ?? ''] ?? null;
  return null;
}

export function FundamentalScreenTable({ rows, thresholds, onSelect, asOf, settingsSlot }: {
  rows: readonly ScreenerCoreRow[]; thresholds: AxisThresholds | null | undefined; onSelect: (symbol: string) => void; asOf?: string | null; settingsSlot?: ReactNode;
}) {
  const density = useFundamentalPrefs((s) => s.density);
  const sortKey = useFundamentalPrefs((s) => s.sortKey);
  const sortDir = useFundamentalPrefs((s) => s.sortDir);
  const setSort = useFundamentalPrefs((s) => s.setSort);
  const excludeAxes = useExcludeAxes();
  const [query, setQuery] = useState('');
  const [sector, setSector] = useState('');
  const parentRef = useRef<HTMLDivElement>(null);
  const excluded = useMemo(() => applyExcludeFilter(rows, excludeAxes), [rows, excludeAxes]);
  const filtered = useMemo(() => {
    const q = query.trim();
    return excluded.rows
      .filter((row) => (sector ? row.sector_name === sector : true))
      .filter((row) => (q ? row.symbol.includes(q) || (row.name ?? '').includes(q) : true))
      .slice()
      .sort((a, b) => {
        const av = sortValue(a, sortKey); const bv = sortValue(b, sortKey);
        if (av == null && bv == null) return 0; if (av == null) return 1; if (bv == null) return -1;
        const cmp = typeof av === 'string' ? av.localeCompare(String(bv), 'fa') : Number(av) - Number(bv);
        return sortDir === 'asc' ? cmp : -cmp;
      });
  }, [excluded.rows, query, sector, sortKey, sortDir]);
  const virtual = filtered.length > 80;
  const virtualizer = useVirtualizer({ count: filtered.length, getScrollElement: () => parentRef.current, estimateSize: () => (density === 'comfortable' ? 88 : 38), overscan: 14, enabled: virtual });
  const bodyHeight = virtual ? virtualizer.getTotalSize() : 0;
  const sectors = useMemo(() => [...new Set(rows.map((r) => r.sector_name).filter(Boolean))].sort((a, b) => String(a).localeCompare(String(b), 'fa')), [rows]);
  const sortButton = (key: SortKey, label: string) => (
    <button type="button" onClick={() => setSort(key, sortKey === key && sortDir === 'desc' ? 'asc' : 'desc')} aria-label={`مرتب‌سازی ${label}`} className="flex items-center gap-1 text-start">
      {label}<span aria-hidden>{sortKey === key ? (sortDir === 'desc' ? '↓' : '↑') : '↕'}</span>
    </button>
  );
  const renderRow = (row: ScreenerCoreRow) => (
    <div key={row.symbol} role="row" tabIndex={0} data-testid={`fundamental-row-${row.symbol}`}
      onClick={() => onSelect(row.symbol)}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(row.symbol); } }}
      className="fd-row grid items-center border-b border-[var(--fd-line)] hover:bg-[var(--fd-panel-2)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--fd-accent)]"
      style={{ gridTemplateColumns: COLUMNS, minHeight: density === 'comfortable' ? 88 : 38 }}
    >
      <div className="flex justify-center"><AxisGlyph statuses={AXES.map((a) => statusOf(row as never, a.key))} labels={AXES.map((a) => a.short)} /></div>
      <div className="min-w-0 px-2">
        <b className="block truncate text-[12px] font-medium text-[var(--fd-text)]">{row.symbol}</b>
        <span className="block truncate text-[9.5px] text-[var(--fd-text-3)]">{row.name ?? '—'} · {row.sector_name ?? '—'}</span>
        {row.i4_na ? <span data-testid={`fundamental-bank-${row.symbol}`} className="mt-0.5 inline-block rounded border border-[var(--fd-line-strong)] px-1 text-[9px] text-[var(--fd-text-3)]">بانک / N/A</span> : null}
        {row.excluded ? <span className="mt-0.5 inline-block rounded border border-[var(--fd-warn)] px-1 text-[9px] text-[var(--fd-warn)]">خارج از غربال</span> : null}
      </div>
      {AXES.map((a) => <FundamentalAxisCell key={a.key} row={row} axis={a.key} thresholds={thresholds} />)}
      <div className="text-center text-[12px] font-medium tabular-nums text-[var(--fd-text)]">{row.score == null ? '—' : `${row.score}/۵`}</div>
      <div className="flex justify-center"><span className={`rounded border px-1 text-[9px] ${row.verdict === 'STRONG' ? 'border-[var(--fd-up)] text-[var(--fd-up)]' : row.verdict === 'REJECT' || row.verdict === 'EXCLUDED' ? 'border-[var(--fd-down)] text-[var(--fd-down)]' : 'border-[var(--fd-warn)] text-[var(--fd-warn)]'}`}>{verdictFa(row.verdict)}</span></div>
    </div>
  );
  return (
    <div data-testid="fundamental-screen-table" className="flex min-h-0 flex-1 flex-col text-[var(--fd-text)]">
      <div className="flex flex-none flex-wrap items-center gap-2 border-b border-[var(--fd-line)] px-3 py-2">
        <input data-testid="fundamental-search" type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="جستجو در نماد یا نام…" aria-label="جستجوی بنیادی" className="h-[26px] min-w-[150px] flex-1 rounded border border-[var(--fd-line)] bg-[var(--fd-panel)] px-2 text-[11px] outline-none focus:border-[var(--fd-line-strong)]" />
        <select aria-label="فیلتر صنعت" value={sector} onChange={(e) => setSector(e.target.value)} className="h-[26px] max-w-[210px] rounded border border-[var(--fd-line)] bg-[var(--fd-panel)] px-1.5 text-[11px]"><option value="">همه صنایع</option>{sectors.map((s) => <option key={s} value={s}>{s}</option>)}</select>
        {settingsSlot ?? <span />}
        <span data-testid="fundamental-count" className="num t-9 text-[var(--fd-text-3)]">{fmtInt(filtered.length)} از {fmtInt(rows.length)}</span>
        {excluded.hidden > 0 ? <span data-testid="fundamental-hidden-count" title={excludeAxes.map((a) => EXCLUDE_LABEL[a]).join(' · ')} className="num t-9 text-[var(--fd-warn)]">{fmtInt(excluded.hidden)} حذف‌شده</span> : null}
        <span className="t-85 text-[var(--fd-text-3)]">{asOf ? `زمان اسکن: ${asOf}` : ''}</span>
      </div>
      <div className="grid flex-none items-center border-b border-[var(--fd-line-strong)] bg-[var(--fd-panel-2)] px-1.5 text-[10px] text-[var(--fd-text-3)]" style={{ gridTemplateColumns: COLUMNS, minHeight: 55 }}>
        <span className="text-center">#</span>
        <span>{sortButton('symbol', 'نماد')}<span className="block text-[9px]">نام · صنعت</span></span>
        {AXES.map((a) => <span key={a.key}><span className="block text-[11px] text-[var(--fd-text)]">{a.num} {a.label}</span><span className="block text-[9px]">{a.key === 'growth' ? `≥ ${thresholds?.growth_min ?? '—'}٪` : a.key === 'eps' ? '۳ سال' : a.key === 'margin' ? `≥ ${thresholds?.margin_min ?? '—'}٪` : a.key === 'sales' ? `≥ ${(thresholds?.v10_sales_to_mcap_min ?? 0).toFixed(2)}` : 'رژیم'}</span></span>)}
        <span className="text-center">{sortButton('score', 'امتیاز')}</span>
        <span className="text-center">وضعیت</span>
      </div>
      <div ref={parentRef} className="min-h-0 flex-1 overflow-auto">
        {filtered.length === 0 ? <p className="p-3 text-[11px] text-[var(--fd-text-3)]">ردیفی با این فیلتر نیست.</p> : virtual ? (
          <div style={{ height: bodyHeight, position: 'relative' }}>{virtualizer.getVirtualItems().map((item) => { const row = filtered[item.index]; return row ? <div key={item.key} style={{ position: 'absolute', insetInline: 0, top: item.start }}>{renderRow(row)}</div> : null; })}</div>
        ) : filtered.map(renderRow)}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: تست و کامیت**

Run: `cd frontend-v2 && npm run typecheck && npx vitest run src/__tests__/fundamental-table-visual.spec.tsx`
Expected: PASS (تست مرتب‌سازی/سرچ/رفتن به نماد).

```bash
git add frontend-v2/src/features/fundamental/ui/FundamentalAxisCell.tsx frontend-v2/src/features/fundamental/ui/FundamentalScreenTable.tsx frontend-v2/src/__tests__/fundamental-table-visual.spec.tsx
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(fundamental): جدول پنج‌ستونه با دو حالت و مجازی‌سازی"
```

---

### Task 4: صفحه، نوار ابزار، density/surface، CSV و حفظ S4b

**Files:**
- Modify: `frontend-v2/src/features/fundamental/routes/FundamentalPage.tsx`
- Modify: `frontend-v2/src/features/fundamental/ui/FundamentalScreenTable.tsx` (نوار ابزار density/surface/legend/CSV)
- Test: `frontend-v2/src/__tests__/fundamental-page-visual.spec.tsx`

**Interfaces:**
- Consumes: `useFundamentalPrefs` (Task 1)، `FundamentalScreenTable` (Task 3)، `FtsSettingsTrigger` (S4b)، `useScreenerCore` با `thresholds`.
- Produces: صفحهٔ سطح‌دار با `data-fund-surface`، سوییچ density/surface، CSV پنج‌ستونه.

- [ ] **Step 1: تست صفحه/سطح/CSV**

```tsx
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FundamentalPage } from '@features/fundamental/routes/FundamentalPage';
import { useScreenerCore } from '@features/fundamental/api/useScreenerCore';
import { useFundamentalPrefs } from '@features/fundamental/stores/prefs';
import { downloadCsvWithMeta } from '@shared/lib/tableExport';

vi.mock('@features/fundamental/api/useScreenerCore', () => ({ useScreenerCore: vi.fn() }));
vi.mock('@shared/lib/tableExport', async (importOriginal) => ({ ...(await importOriginal<typeof import('@shared/lib/tableExport')>()), downloadCsvWithMeta: vi.fn() }));
const rows = [{ symbol: 'رنيك', name: 'جنرال مکانیک', sector_name: 'خدمات فنی', score: 3, verdict: 'WATCH', i1_pass: false, i1_na: false, i2_pass: true, i2_na: false, i3_pass: false, i3_na: false, i4_pass: true, i4_na: false, i5_pass: true, i5_na: false, rev_growth: 45.9, eps_series: [1119, 1615, 1672], eps_years_available: 3, gross_margin: 11.5, sales_to_mcap: 1.15, profit_potential_pct: 13.2, pricing_mode: 'neutral' }];
beforeEach(() => {
  useFundamentalPrefs.setState({ density: 'comfortable', surface: 'paper', sortKey: 'score', sortDir: 'desc' });
  vi.mocked(useScreenerCore).mockReturnValue({ data: { status: 'success', count: 1, data: rows, as_of: 1793789441, thresholds: { growth_min: 60, margin_min: 40, v10_sales_to_mcap_min: 0.33, profit_potential_min: 40, v10_eps_years: 3 } }, isLoading: false, isFetching: false, isError: false, refetch: vi.fn() } as never);
});
afterEach(cleanup);
describe('fundamental page visual', () => {
  it('sets paper surface by default and switches to ink', () => {
    render(<MemoryRouter initialEntries={['/fundamental']}><FundamentalPage /></MemoryRouter>);
    const page = screen.getByTestId('fundamental-page');
    expect(page.getAttribute('data-fund-surface')).toBe('paper');
    fireEvent.click(screen.getByTestId('fundamental-surface-ink'));
    expect(useFundamentalPrefs.getState().surface).toBe('ink');
    expect(screen.getByTestId('fundamental-page').getAttribute('data-fund-surface')).toBe('ink');
  });
  it('exports five axis columns with threshold metadata', () => {
    render(<MemoryRouter initialEntries={['/fundamental']}><FundamentalPage /></MemoryRouter>);
    fireEvent.click(screen.getByTestId('fundamental-export'));
    const [, table, meta] = vi.mocked(downloadCsvWithMeta).mock.calls[0]!;
    expect(table.columns).toEqual(expect.arrayContaining(['نماد', 'رشد', 'سودآوری', 'حاشیه', 'فروش/ارزش', 'صنعت', 'امتیاز', 'وضعیت']));
    expect(meta).toEqual(expect.arrayContaining([['آستانه رشد', '60']]));
  });
});
```

- [ ] **Step 2: اجرا و شکست**

Run: `cd frontend-v2 && npx vitest run src/__tests__/fundamental-page-visual.spec.tsx`
Expected: FAIL — surface/CSV جدید نیست.

- [ ] **Step 3: پیاده‌سازی**

در `FundamentalPage`:
```tsx
const prefs = useFundamentalPrefs();
const scanLabel = scanTimeLabel(screener.data?.as_of);
return (
  <section data-testid="fundamental-page" data-fund-surface={prefs.surface} className="fundamental-surface flex min-h-0 flex-1 flex-col bg-[var(--fd-bg)] text-[var(--fd-text)]">
    <header className="flex flex-none flex-wrap items-baseline gap-2 border-b border-[var(--fd-line)] px-3 py-2">
      <b className="t-125 font-extrabold">بنیادی</b>
      <span className="t-9 text-[var(--fd-text-3)]">غربالگری پنج‌محور FTS — هر ستون یک محور</span>
      <span data-testid="fundamental-as-of" className="num ms-auto t-85 text-[var(--fd-text-3)]">{scanLabel ? `زمان اسکن: ${scanLabel}` : ''}</span>
      <button type="button" data-testid="fundamental-surface-paper" aria-pressed={prefs.surface === 'paper'} onClick={() => prefs.setSurface('paper')} className="...">کاغذی</button>
      <button type="button" data-testid="fundamental-surface-ink" aria-pressed={prefs.surface === 'ink'} onClick={() => prefs.setSurface('ink')} className="...">تیره</button>
    </header>
    {screener.isLoading ? ... : screener.isError ? ... : (
      <FundamentalScreenTable rows={screener.data.data} thresholds={screener.data.thresholds} asOf={scanLabel} onSelect={(s) => navigate(`/fundamental/${s}`)} settingsSlot={<FtsSettingsTrigger ... />} />
    )}
  </section>
);
```

در جدول، دکمه‌های density و CSV:
```tsx
<button data-testid="fundamental-density-compact" aria-pressed={density === 'compact'} onClick={() => setDensity('compact')}>فشرده</button>
<button data-testid="fundamental-density-comfortable" aria-pressed={density === 'comfortable'} onClick={() => setDensity('comfortable')}>راحت</button>
<button data-testid="fundamental-export" onClick={exportCsv} className="...">CSV</button>
```
`exportCsv` از `sorted` می‌سازد: ستون‌ها `['نماد','نام','صنعت','رشد','سودآوری','حاشیه','فروش/ارزش','صنعت','امتیاز','وضعیت']`؛ هر محور `formatAxisValue` + وضعیت فارسی؛ meta: `[['آستانه رشد', String(thresholds?.growth_min ?? '—')], ['آستانه حاشیه', String(thresholds?.margin_min ?? '—')], ['آستانه فروش/ارزش', String(thresholds?.v10_sales_to_mcap_min ?? '—')], ['زمان اسکن', asOf ?? '—']]`.

- [ ] **Step 4: تست/کامیت**

Run: `cd frontend-v2 && npm run typecheck && npx vitest run src/__tests__/fundamental-page-visual.spec.tsx src/__tests__/fundamental-settings.spec.tsx src/__tests__/fundamental-exclusion.spec.tsx`
Expected: PASS.

```bash
git add frontend-v2/src/features/fundamental/routes/FundamentalPage.tsx frontend-v2/src/features/fundamental/ui/FundamentalScreenTable.tsx frontend-v2/src/__tests__/fundamental-page-visual.spec.tsx
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(fundamental): سطح داده، density و CSV پنج‌ستونه"
```

---

### Task 5: کاکپیت نمای نماد

**Files:**
- Create: `frontend-v2/src/features/fundamental/ui/Quintet.tsx`
- Create: `frontend-v2/src/features/fundamental/ui/panels/GrowthPanel.tsx`
- Create: `frontend-v2/src/features/fundamental/ui/panels/EpsPanel.tsx`
- Create: `frontend-v2/src/features/fundamental/ui/panels/MarginPanel.tsx`
- Create: `frontend-v2/src/features/fundamental/ui/panels/SalesPanel.tsx`
- Create: `frontend-v2/src/features/fundamental/ui/panels/IndustryPanel.tsx`
- Create: `frontend-v2/src/features/fundamental/ui/panels/HistoryPanel.tsx`
- Create: `frontend-v2/src/features/fundamental/ui/panels/EvidencePanel.tsx`
- Rewrite: `frontend-v2/src/features/fundamental/ui/FundamentalDetail.tsx`
- Test: `frontend-v2/src/__tests__/fundamental-cockpit.spec.tsx`

**Interfaces:**
- Consumes: `FtsCard` (Task 1 schema), `Bullet/EpsBars/RegimeGlyph/AxisGlyph/PeDots/HistoryBars` (Task 2), `useFundamentalPrefs`، `HoldingNavPanel`، `CorporateCalendar`، `CodalHealthStrip`، `useSectorPe`، `assetScope`.
- Produces: `FundamentalDetail` با `data-fund-surface`، `Quintet({ card })`، پنل‌های تصویری.

- [ ] **Step 1: تست کاکپیت**

Fixture کارت را از `fundamental-detail.spec.tsx` بگیر و به آن فیلدهای واقعی اضافه کن:
```ts
const card = {
  status: 'success', symbol: 'رنيك', sector: 'خدمات فنی و مهندسی', score: 3, verdict: 'WATCH',
  passes: { '1_growth': false, '2_eps_trend': true, '3_gross_margin': false, '4_sales_to_mcap': true, '5_industry': true },
  indicators: {
    '1': { monetary: { monetary_pct: 45.9, threshold: 60, data_gap: false, reason: 'کف ۶۰٪' }, volume: { applicable: true } },
    '2': { eps_series: [1119, 1615, 1672], years_available: 3, years_required: 3, evidence: 'تلفیقی', consolidated_used: true },
    '3': { margin_pct: 11.5, threshold: 40, optimal_threshold: 30, margin_tier: 'below', gross_profit_bt: 12.4, revenue_bt: 107.8, na: false },
    '4': { sales_to_mcap: 1.15, sales_threshold: 0.33, potential_pct: 13.2, potential_threshold: 40, annual_sales_bt: 5.5, months_used: 6, available: true, na: false },
    '5': { verdict: 'neutral', label: 'خنثی', sector: 'خدمات فنی و مهندسی', market_share_pct: 4.2, outlook: 'نیازمند بررسی موردی', regime_label: 'خنثی', pass: true },
  },
  history: [{ period_end: '1404/12/29', fiscal_year: '1404', revenue: 82657, gross_profit: 10500, net_profit: 9125, eps: 1615, audited: true, consolidated: false }],
  details: { '۱': { title: 'رشد', formula: '...', source: 'کدال', calc: '+45.9', what: '...', subchecks: [{ key: '1a', label: 'رشد ریالی', state: 'fail', value: '+45.9٪', threshold: '≥ 60٪', detail: '...', verified: true, confidence: 'متوسط' }] } },
  freshness: { as_of: '2026-07-09', axes: { '1_growth': { state: 'fresh', source: 'کدال' } } },
  profile: { kind: 'production', margin_class: 'production' },
};
```

```tsx
it('renders quintet, five panels, history and evidence', () => {
  render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
  expect(screen.getByTestId('fundamental-quintet').querySelectorAll('[data-axis]').length).toBe(5);
  expect(screen.getByTestId('panel-growth')).toBeTruthy();
  expect(screen.getByTestId('panel-eps')).toBeTruthy();
  expect(screen.getByTestId('panel-margin')).toBeTruthy();
  expect(screen.getByTestId('panel-sales')).toBeTruthy();
  expect(screen.getByTestId('panel-industry')).toBeTruthy();
  expect(screen.getByTestId('panel-history')).toBeTruthy();
  expect(screen.getByTestId('panel-evidence')).toBeTruthy();
  expect(screen.getByTestId('fundamental-score-ribbon').textContent).toContain('۳ از ۵');
});
it('shows holding N/A and no fake P/NAV', () => {
  mockedCard.mockReturnValue(holdingCard());
  render(<FundamentalDetail symbol="ویسا" onBack={vi.fn()} />);
  expect(screen.getByTestId('holding-pnav-panel')).toBeTruthy();
  expect(screen.queryByText(/P\/NAV ≈/)).toBeNull();
});
```

- [ ] **Step 2: اجرا و شکست**

Run: `cd frontend-v2 && npx vitest run src/__tests__/fundamental-cockpit.spec.tsx`
Expected: FAIL — پنل‌ها/quintet وجود ندارند.

- [ ] **Step 3: پیاده‌سازی Quintet و پنل‌ها**

`Quintet.tsx`:
```tsx
import { AXES } from '../lib/axisMeta';
import { Bullet } from './mini/Bullet';
import { EpsBars } from './mini/EpsBars';
import { RegimeGlyph } from './mini/RegimeGlyph';

export function Quintet({ items }: { items: Array<{ axis: 'growth'|'eps'|'margin'|'sales'|'industry'; value: string; threshold: string; status: 'pass'|'fail'|'na'|'unknown'; chart: React.ReactNode; onFocus: () => void }> }) {
  return (
    <div data-testid="fundamental-quintet" className="grid grid-cols-5 gap-2 max-[1050px]:grid-cols-2">
      {items.map((item) => { const meta = AXES.find((a) => a.key === item.axis)!; return (
        <button key={item.axis} type="button" data-axis={item.axis} onClick={item.onFocus} className="flex flex-col gap-1 rounded-lg border border-[var(--fd-line)] bg-[var(--fd-panel)] p-2 text-start">
          <span className="flex items-center gap-1 text-[10.5px] text-[var(--fd-text-2)]"><span className="grid h-4 w-4 place-items-center rounded border border-[var(--fd-line-strong)] text-[9px]">{meta.num}</span>{meta.label}</span>
          <span className="flex items-baseline gap-1"><b className="text-[16px] font-medium tabular-nums text-[var(--fd-text)]">{item.value}</b><span className="text-[9px] text-[var(--fd-text-3)]">{item.threshold}</span></span>
          <span className="h-[18px]">{item.chart}</span>
          <span className={`text-[9px] ${item.status === 'pass' ? 'text-[var(--fd-up)]' : item.status === 'fail' ? 'text-[var(--fd-down)]' : 'text-[var(--fd-text-3)]'}`}>{item.status === 'pass' ? 'قبول' : item.status === 'fail' ? 'رد' : item.status === 'na' ? 'بی‌نظر' : 'نامشخص'}</span>
        </button>
      ); })}
    </div>
  );
}
```

`GrowthPanel` (نمونه؛ بقیهٔ پنل‌ها همان الگو با فیلدهای خودشان):
```tsx
export function GrowthPanel({ card }: { card: FtsCard }) {
  const monetary = card.indicators?.['1']?.monetary;
  const history = card.history ?? [];
  const status = card.passes?.['1_growth'] === true ? 'pass' : card.passes?.['1_growth'] === false ? 'fail' : monetary?.data_gap ? 'unknown' : 'na';
  return (
    <section data-testid="panel-growth" id="panel-growth" className="rounded-lg border border-[var(--fd-line)] bg-[var(--fd-panel)] p-2.5">
      <header className="mb-1 flex items-baseline gap-1.5"><span className="text-[9px] text-[var(--fd-text-3)]">۱</span><h3 className="text-[11.5px] font-medium">رشد فروش — ۱الف و ۱ب</h3><span className="ms-auto text-[10px]">{status === 'pass' ? 'قبول' : status === 'fail' ? 'رد' : status === 'na' ? 'بی‌نظر' : 'نامشخص'}</span></header>
      <div className="flex items-baseline gap-1.5"><b className="text-[19px] font-medium tabular-nums">{monetary?.monetary_pct == null ? '—' : `${monetary.monetary_pct.toFixed(1)}٪`}</b><span className="text-[10px] text-[var(--fd-text-3)]">کف {monetary?.threshold ?? '—'}٪</span></div>
      <div className="h-[32px]"><Bullet value={monetary?.monetary_pct ?? null} max={200} threshold={monetary?.threshold ?? null} status={status as never} label="رشد فروش" /></div>
      <div className="mt-1 grid grid-cols-2 gap-1 text-[9.5px] text-[var(--fd-text-3)]">
        <span>۱الف: <b className="text-[var(--fd-text)]">{monetary?.monetary_pct == null ? '—' : `${monetary.monetary_pct.toFixed(1)}٪`}</b></span>
        <span>۱ب: <b className="text-[var(--fd-text)]">{card.indicators?.['1']?.volume?.applicable === false ? 'N/A' : '—'}</b></span>
      </div>
      <div className="mt-1 h-[30px]"><HistoryBars values={history.map((h) => h.revenue ?? null)} labels={history.map((h) => h.period_end ?? '')} status="pass" /></div>
      <details className="mt-1"><summary className="cursor-pointer text-[9.5px] text-[var(--fd-text-3)]">فرمول و منبع</summary><p className="mt-1 text-[9.5px] leading-relaxed text-[var(--fd-text-3)]">{card.details?.['۱']?.formula ?? '—'} — {card.details?.['۱']?.source ?? '—'}</p></details>
    </section>
  );
}
```

`EpsPanel`/`MarginPanel`/`SalesPanel`/`IndustryPanel`/`HistoryPanel`/`EvidencePanel` با همین ساختار: مقدار از `indicators['2']`/`['3']`/`['4']`/`['5']`، وضعیت از `passes`/`na`، چارت از `EpsBars`/`Bullet`/`PeDots`/`HistoryBars`؛ شواهد از `details[digit].subchecks`؛ بانک/هلدینگ → `HoldingNavPanel` یا N/A در پنل صنعت.

`FundamentalDetail`:
```tsx
export function FundamentalDetail({ symbol, onBack }: Props) {
  const query = useFtsCard(symbol);
  const sectorPe = useSectorPe(symbol);
  const health = useCodalHealth();
  const prefs = useFundamentalPrefs();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const card = query.data;
  const holding = card ? isHoldingCard(card) : false;
  const bank = card ? isBankCard(card) : false;
  if (query.isLoading) return <section data-testid="fundamental-detail-loading" ...>...skeleton...</section>;
  if (query.isError || !card) return <section data-testid="fundamental-detail-error" ...>...retry...</section>;
  const focusAxis = (axis: string) => document.getElementById(`panel-${axis}`)?.scrollIntoView({ block: 'start', behavior: 'smooth' });
  return (
    <section data-testid="fundamental-detail" data-fund-surface={prefs.surface} className="fundamental-surface flex min-h-0 flex-1 flex-col bg-[var(--fd-bg)] text-[var(--fd-text)]">
      <header className="flex flex-none flex-wrap items-baseline gap-2 border-b border-[var(--fd-line)] px-3 py-2">
        <button type="button" data-testid="fundamental-back" onClick={onBack} className="tape-btn">→ جدول</button>
        <b data-testid="fundamental-title" className="t-125 font-extrabold">{symbol}</b>
        <span className="t-9 text-[var(--fd-text-3)]">{card.sector}</span>
        {holding ? <span data-testid="holding-class-badge" className="rounded border border-[var(--fd-accent)] px-1 text-[9px] text-[var(--fd-accent)]">{bank ? 'بانک / مؤسسهٔ اعتباری' : 'هلدینگ / سرمایه‌گذاری'}</span> : null}
        <span className="rounded border border-[var(--fd-line-strong)] px-1 text-[9px]">{verdictFa(card.verdict)}</span>
        <span className="num t-9">امتیاز {card.score ?? '—'}/۵</span>
        <span className="ms-auto text-[10px] text-[var(--fd-text-3)]">{card.freshness?.as_of ? `دادهٔ بنیادی تا ${card.freshness.as_of}` : 'تازگی نامشخص'}</span>
        <FtsSettingsTrigger open={settingsOpen} onToggle={() => setSettingsOpen((v) => !v)} />
      </header>
      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto p-2">
        <Quintet items={quintetItems(card, focusAxis)} />
        <ScoreRibbon card={card} />
        <div className="grid grid-cols-12 gap-2">
          <div className="col-span-7 max-[1050px]:col-span-12"><GrowthPanel card={card} /></div>
          <div className="col-span-5 max-[1050px]:col-span-12"><EpsPanel card={card} /></div>
          <div className="col-span-5 max-[1050px]:col-span-12"><MarginPanel card={card} /></div>
          <div className="col-span-7 max-[1050px]:col-span-12"><SalesPanel card={card} /></div>
          <div className="col-span-7 max-[1050px]:col-span-12">{holding ? <HoldingNavPanel bankLike={bank} /> : <IndustryPanel card={card} sectorPe={sectorPe.data} />}</div>
          <div className="col-span-5 max-[1050px]:col-span-12"><HistoryPanel card={card} /></div>
          <div className="col-span-12"><EvidencePanel card={card} /></div>
          <div className="col-span-12"><CorporateCalendar symbol={symbol} /></div>
          <div className="col-span-12"><CodalHealthStrip health={health.data} loading={health.isLoading} /></div>
        </div>
      </div>
    </section>
  );
}
```

`ScoreRibbon`: از `card.passes`/`indicators.*.na` پنج قطعه؛ «N از ۵»، رد/بی‌نظر، قوی‌ترین/ضعیف‌ترین؛ `data-testid="fundamental-score-ribbon"`.

- [ ] **Step 4: تست/کامیت**

Run: `cd frontend-v2 && npm run typecheck && npx vitest run src/__tests__/fundamental-cockpit.spec.tsx src/__tests__/fundamental-holding.spec.tsx`
Expected: PASS.

```bash
git add frontend-v2/src/features/fundamental/ui/Quintet.tsx frontend-v2/src/features/fundamental/ui/panels frontend-v2/src/features/fundamental/ui/FundamentalDetail.tsx frontend-v2/src/__tests__/fundamental-cockpit.spec.tsx
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(fundamental): کاکپیت پنج‌پنلی نمای نماد"
```

---

### Task 6: مصرف‌کننده‌های BottomDock/SymbolSidebar و بازنشستگی Drill-Down

**Files:**
- Modify: `frontend-v2/src/features/fundamental/ui/FundamentalCards.tsx`
- Modify: `frontend-v2/src/features/fundamental/ui/FundamentalSummary.tsx`
- Modify: `frontend-v2/src/app/shell/BottomDock.tsx` (در صورت نیاز به props)
- Modify: `frontend-v2/src/app/shell/SymbolSidebar.tsx` (در صورت نیاز به props)
- Delete: `frontend-v2/src/features/fundamental/ui/AxisDrilldown.tsx`
- Test: `frontend-v2/src/__tests__/fundamental-consumers.spec.tsx`
- Test: `frontend-v2/src/__tests__/bottom-dock.spec.tsx` (به‌روزرسانی)
- Test: `frontend-v2/src/__tests__/symbol-sidebar.spec.tsx` (به‌روزرسانی)

**Interfaces:**
- Consumes: `FtsCard`، `AXES`/`statusOf`/`fundamentalFacts` (در صورت نیاز).
- Produces: `FundamentalCards({ symbol })` با پنج کارت کوچک/گلیف؛ `FundamentalSummary({ symbol })` با «N از ۵» + وضعیت‌ها.

- [ ] **Step 1: تست مصرف‌کننده‌ها**

```tsx
it('renders five compact axis cards in the dock variant', () => {
  render(<FundamentalCards symbol="رنيك" />);
  expect(screen.getByTestId('fundamental-cards').querySelectorAll('[data-axis]').length).toBe(5);
  expect(screen.getByTestId('fundamental-cards').textContent).not.toContain('فرمول');
});
it('renders the summary with count and statuses', () => {
  render(<FundamentalSummary symbol="رنيك" />);
  expect(screen.getByTestId('symbol-fund-summary').textContent).toContain('از ۵');
});
```

- [ ] **Step 2: پیاده‌سازی variantهای کوچک**

`FundamentalCards`: `useFtsCard(symbol)`; the `card`; the five `AxisMiniCard` (the axis number/name/value/status; the mini chart in the dock? The dock is compact; use the glyph/values; no long notes); the `data-testid="fundamental-cards"`; the click? The dock's cards are read-only; the detail link? The current cards; the plan.
`FundamentalSummary`: the `useFtsCard`; the `passes`/`indicators`; the "N از ۵"; the five status dots/glyph; the weakest; the `symbol-fund-summary`; the `expanded`/`onToggle` props; the existing; the `FundamentalSummary` is used by the `SymbolSidebar`; the compact; the plan.
`AxisDrilldown` delete; the `FundamentalDetail` no import; the old `fundamental-detail.spec` is replaced by `fundamental-cockpit.spec`; the `fundamental-summary.spec` updated; the `fundamental-cards` no test? The `BottomDock` `FundamentalCards` test; the `SymbolSidebar` `FundamentalSummary` test; the `bottom-dock.spec`/`symbol-sidebar.spec` updates; the plan.

- [ ] **Step 3: اجرا/کامیت**

Run: `cd frontend-v2 && npm run typecheck && npx vitest run src/__tests__/fundamental-consumers.spec.tsx src/__tests__/bottom-dock.spec.tsx src/__tests__/symbol-sidebar.spec.tsx`
Expected: PASS.

```bash
git add frontend-v2/src/features/fundamental/ui/FundamentalCards.tsx frontend-v2/src/features/fundamental/ui/FundamentalSummary.tsx frontend-v2/src/app/shell/BottomDock.tsx frontend-v2/src/app/shell/SymbolSidebar.tsx frontend-v2/src/features/fundamental/ui/AxisDrilldown.tsx frontend-v2/src/__tests__/fundamental-consumers.spec.tsx frontend-v2/src/__tests__/bottom-dock.spec.tsx frontend-v2/src/__tests__/symbol-sidebar.spec.tsx
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(fundamental): variantهای BottomDock/SymbolSidebar و حذف Drill-Down متنی"
```

---

### Task 7: حرکت، دسترس‌پذیری و تم‌ها

**Files:**
- Modify: `frontend-v2/src/features/fundamental/ui/FundamentalScreenTable.tsx` (transitionهای density/سطح)
- Modify: `frontend-v2/src/features/fundamental/ui/FundamentalDetail.tsx` (ورود پنل‌ها، focus به پنل)
- Modify: `frontend-v2/src/app/styles.css` (`prefers-reduced-motion`، `fd-in`، `fd-draw`)
- Test: `frontend-v2/src/__tests__/fundamental-a11y.spec.tsx`

- [ ] **Step 1: تست دسترس‌پذیری/حرکت**

```tsx
it('exposes sort state and keyboard rows', () => {
  render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
  expect(screen.getByRole('row', { name: /رنيك/ })).toHaveAttribute('tabindex', '0');
  expect(document.querySelector('[aria-sort]')).toBeTruthy();
});
it('marks the surface on the detail root', () => {
  useFundamentalPrefs.setState({ surface: 'ink' });
  render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
  expect(screen.getByTestId('fundamental-detail').getAttribute('data-fund-surface')).toBe('ink');
});
```

- [ ] **Step 2: پیاده‌سازی**

- `@media (prefers-reduced-motion: reduce)` همهٔ `fd-draw/fd-in` و transitionهای جدول را خنثی کند؛ حرکت با opacity/transform، بدون height/top/margin.
- density/surface: crossfade `opacity 160ms ease-out` روی محتوای سلول؛ ارتفاع ردیف بدون layout animation.
- پنل‌های نمای نماد: کلاس `fd-in` (fade/translateY 3px، 220ms ease-out) با stagger 40ms در CSS؛ نمودارها `fd-draw` 450ms ease-out.
- focus: بعد از کلیک کاشی پنجگانه، `document.getElementById('panel-'+axis)?.scrollIntoView` + `focus()` روی هدر پنل با `tabIndex={-1}`؛ focus-visible.
- `aria-sort` روی سرستون فعال؛ `aria-label` روی نمودارها/گلیف؛ رنگ + واژه + آیکن.

- [ ] **Step 3: تست/کامیت**

Run: `cd frontend-v2 && npm run typecheck && npx vitest run src/__tests__/fundamental-a11y.spec.tsx`
Expected: PASS.

```bash
git add frontend-v2/src/app/styles.css frontend-v2/src/features/fundamental/ui/FundamentalScreenTable.tsx frontend-v2/src/features/fundamental/ui/FundamentalDetail.tsx frontend-v2/src/__tests__/fundamental-a11y.spec.tsx
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(fundamental): حرکت مهارشده و دسترس‌پذیری جدول/کاکپیت"
```

---

### Task 8: پذیرش زنده و شواهد

**Files:**
- Evidence: `_audit/rebuild/fundamental-redesign/` (screenshots/JSON؛ untracked).

- [ ] **Step 1: typecheck و کل تست‌ها**

Run: `cd frontend-v2 && npm run typecheck && npm test`
Expected: PASS (همهٔ تست‌های قدیمی/جدید).

- [ ] **Step 2: سرورهای آزمون**

- Python: `BORS_WORK_DIR=D:/BorsTerminal-tmp/4axes-data BORS_NO_FETCH_LOOPS=1 python -m uvicorn app:app --host 127.0.0.1 --port 8110` (از ریشهٔ ریپو).
- v2: `BORS_BACKEND=http://127.0.0.1:8110 npx vite --port <free> --strictPort` (پورت آزاد، `localhost`).
- Go اختیاری: `cd backend-go && /d/BorsTerminal-tmp/go-toolchain/go/bin/go.exe run ./cmd/borsd --db-dir D:/BorsTerminal-tmp/4axes-data --port 8103 --no-loops` و `BORS_BACKEND_GO` برای کارت.

- [ ] **Step 3: اسکرین‌شات‌ها**

- جدول فشرده/راحت، `1366×768` و `1920×1080`.
- نمای نماد `رنيك`، `ویسا` (هلدینگ), `وبملت` (بانک)؛ P/NAV.
- سطح paper/ink و تم ترکیبی/روشن/تیره.
- مقایسهٔ کنارِ هم با صفحهٔ فعلی (S4b)؛ صفر خطای کنسول.

- [ ] **Step 4: اندازه‌گیری**

- TBT اسکرول جدول ۷۸۳ ردیف در ۱۹۲۰؛ long tasks؛ RAM.
- کنتراست متن/وضعیت؛ keyboard/focus؛ reduced-motion.
- ترتیب: `fundamental-table`, `fundamental-cockpit`, `fundamental-a11y`, full suite.

- [ ] **Step 5: رأی مالک**

اسکرین‌شات‌ها + اعداد را ارائه بده؛ تا رأی بصری مالک، PASS اعلام نشود و کامیت نهایی/پوش انجام نشود.

---

### Task 9: گزارش نهایی و بازگشت به تکنیکال

- [ ] **Step 1: `git status` تمیز (به‌جز `zz_tmp_dump_test.go` و شواهد untracked).**
- [ ] **Step 2: گزارش:** چه ساخته شد، اعداد، چه چیزی باز ماند (S4c/Go materializer، DPS)، و اینکه بنیادی از نظر عملکردی و بصری بسته شد.
- [ ] **Step 3: فاز بعدی: تکنیکال، بعد بازار.**

---

## خودبازبینی — اصلاحات الزامی پیش از اجرا

این بخش جای «…»های تسک‌ها را پر می‌کند و همراه همان تسک اعمال می‌شود.

### A. تست‌های قدیمی که باید به‌روزرسانی/ادغام شوند

- `fundamental-detail.spec.tsx`: انتظار `axis-tab`/`quarter-row`/`sector-pe`/کارت‌ها/Drill-Down حذف؛ جایگزین با `fundamental-quintet`/`panel-*`/`fundamental-score-ribbon` (یا ادغام در `fundamental-cockpit.spec.tsx`).
- `fundamental-summary.spec.tsx`: انتظار «N از ۵» + وضعیت‌ها/ضعیف‌ترین؛ حذف انتظارهای متن قدیمی.
- `fundamental-page.spec.tsx`: `fundamental-chip-*`/legend قدیمی → `fundamental-cell-*`/`fundamental-legend` جدید؛ export/as_of/count حفظ.
- `fundamental-holding.spec.tsx`: `sector-pe-panel` → `panel-industry`؛ `holding-pnav-panel`/badge حفظ.
- `fundamental-exclusion.spec.tsx`: rows/hidden count حفظ؛ chipها حذف/به cell تغییر.
- `bottom-dock.spec.tsx`/`symbol-sidebar.spec.tsx`: `fundamental-cards`/`symbol-fund-summary` جدید.
- `fundamental-calendar.spec.tsx`/`fundamental-settings.spec.tsx`/`fundamental-settings-api.spec.ts`: رفتار حفظ؛ mockهای Detail به‌روز.
- `QuarterlyTrend.tsx`/`useQuarters.ts` اگر پس از حذف از Detail مصرفی ندارند، حذف شوند (کد مرده نگه داشته نشود).

### B. کد مشترک کاکپیت (جای GrowthPanel/«بقیهٔ پنل‌ها»)

```tsx
const CARD_KEY = { growth: '1_growth', eps: '2_eps_trend', margin: '3_gross_margin', sales: '4_sales_to_mcap', industry: '5_industry' } as const;
const CARD_NUM = { growth: '1', eps: '2', margin: '3', sales: '4', industry: '5' } as const;

export function cardStatus(card: FtsCard, axis: AxisKey): AxisStatus {
  const pass = card.passes?.[CARD_KEY[axis]];
  const indicator = card.indicators?.[CARD_NUM[axis]] as { na?: boolean; data_gap?: boolean } | undefined;
  if (pass === true) return 'pass';
  if (pass === false) return 'fail';
  if (indicator?.na === true) return 'na';
  return 'unknown';
}

function AxisPanel({ testId, axis, title, subtitle, status, value, threshold, chart, rows, details, children }: {
  testId: string; axis: string; title: string; subtitle: string; status: AxisStatus;
  value: string; threshold: string; chart: React.ReactNode;
  rows: Array<[string, string]>; details?: { formula?: string | null; source?: string | null } | null; children?: React.ReactNode;
}) {
  const meta = AXES.find((a) => a.key === axis)!;
  return (
    <section data-testid={testId} id={testId} tabIndex={-1} className="fd-panel flex flex-col gap-1.5 rounded-lg border border-[var(--fd-line)] bg-[var(--fd-panel)] p-2.5">
      <header className="flex items-baseline gap-1.5">
        <span className="grid h-4 w-4 place-items-center rounded border border-[var(--fd-line-strong)] text-[9px] text-[var(--fd-text-3)]">{meta.num}</span>
        <h3 className="text-[11.5px] font-medium text-[var(--fd-text)]">{title}</h3>
        <span className={`ms-auto text-[9.5px] fd-status--${status}`}>{status === 'pass' ? 'قبول' : status === 'fail' ? 'رد' : status === 'na' ? 'بی‌نظر' : 'نامشخص'}</span>
      </header>
      <p className="text-[9.5px] leading-relaxed text-[var(--fd-text-3)]">{subtitle}</p>
      <div className="flex items-baseline gap-1.5"><b className="text-[19px] font-medium tabular-nums text-[var(--fd-text)]">{value}</b><span className="text-[10px] text-[var(--fd-text-3)]">{threshold}</span></div>
      <div className="h-[32px]">{chart}</div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[9.5px] text-[var(--fd-text-3)]">
        {rows.map(([label, val]) => <span key={label} className="flex justify-between gap-1 border-b border-[var(--fd-line)] py-0.5"><span>{label}</span><b className="text-[var(--fd-text)]">{val}</b></span>)}
      </div>
      {children}
      <details className="border-t border-[var(--fd-line)] pt-1"><summary className="cursor-pointer text-[9.5px] text-[var(--fd-text-3)]">فرمول و منبع</summary><p className="mt-1 text-[9.5px] leading-relaxed text-[var(--fd-text-3)]">{details?.formula ?? '—'} — {details?.source ?? '—'}</p></details>
    </section>
  );
}

export function GrowthPanel({ card }: { card: FtsCard }) {
  const m = card.indicators?.['1']?.monetary;
  const status = cardStatus(card, 'growth');
  return <AxisPanel testId="panel-growth" axis="growth" title="رشد فروش — ۱الف و ۱ب" subtitle="رشد ریالی در برابر کف، و تأیید رشد واقعی/تناژ" status={status}
    value={m?.monetary_pct == null ? '—' : `${toFaDigits(m.monetary_pct.toFixed(1)).replace('.', '٫')}٪`} threshold={`کف ${toFaDigits(m?.threshold ?? '—')}٪`}
    chart={<Bullet value={m?.monetary_pct ?? null} max={200} threshold={m?.threshold ?? null} status={status} label="رشد فروش" />}
    rows={[['۱الف — رشد ریالی', m?.monetary_pct == null ? '—' : `${toFaDigits(m.monetary_pct.toFixed(1)).replace('.', '٫')}٪`], ['۱ب — رشد واقعی/تناژ', card.indicators?.['1']?.volume?.applicable === false ? 'N/A' : '—']]}
    details={card.details?.['۱']} />;
}

export function EpsPanel({ card }: { card: FtsCard }) {
  const i2 = card.indicators?.['2']; const status = cardStatus(card, 'eps');
  const series = i2?.eps_series ?? []; const last = series.length ? series[series.length - 1] : null;
  return <AxisPanel testId="panel-eps" axis="eps" title="سودآوری ۳ساله" subtitle="سابقهٔ EPS و روند سال‌به‌سال؛ «سنجیده‌نشده» از «رد» جدا است" status={status}
    value={`${toFaDigits(i2?.years_available ?? 0)}/۳`} threshold="سال" chart={<EpsBars series={series} status={status} label="سری EPS" />}
    rows={[['آخرین EPS', last == null ? '—' : toFaDigits(Math.round(last))], ['نیاز گیت', '۳ سال متوالی'], ['شواهد', i2?.evidence ?? '—']]} details={card.details?.['۲']} />;
}

export function MarginPanel({ card }: { card: FtsCard }) {
  const i3 = card.indicators?.['3']; const status = cardStatus(card, 'margin');
  return <AxisPanel testId="panel-margin" axis="margin" title="حاشیهٔ ناخالص" subtitle="فاصله تا کف/ایده‌آل؛ باندهای ۲۰/۳۰/۴۰" status={status}
    value={i3?.margin_pct == null ? '—' : `${toFaDigits(i3.margin_pct.toFixed(1)).replace('.', '٫')}٪`} threshold={`کف ${toFaDigits(i3?.threshold ?? '—')}٪`}
    chart={<Bullet value={i3?.margin_pct ?? null} max={60} threshold={i3?.threshold ?? null} status={status} label="حاشیهٔ ناخالص" />}
    rows={[['سود ناخالص', i3?.gross_profit_bt == null ? '—' : toFaDigits(i3.gross_profit_bt.toFixed(1))], ['درآمد', i3?.revenue_bt == null ? '—' : toFaDigits(i3.revenue_bt.toFixed(1))], ['طبقه', i3?.margin_tier ?? '—']]} details={card.details?.['۳']} />;
}

export function SalesPanel({ card }: { card: FtsCard }) {
  const i4 = card.indicators?.['4']; const status = cardStatus(card, 'sales');
  return <AxisPanel testId="panel-sales" axis="sales" title="فروش / ارزش بازار" subtitle="نسبت فروش سالانه‌شده و پتانسیل سود؛ مسیر OR" status={status}
    value={i4?.sales_to_mcap == null ? '—' : toFaDigits(i4.sales_to_mcap.toFixed(2)).replace('.', '٫')} threshold={`کف ${toFaDigits(i4?.sales_threshold ?? '—')}`}
    chart={<Bullet value={i4?.sales_to_mcap ?? null} max={2} threshold={i4?.sales_threshold ?? null} status={status} label="فروش/ارزش" />}
    rows={[['پتانسیل سود', i4?.potential_pct == null ? '—' : `${toFaDigits(i4.potential_pct.toFixed(1)).replace('.', '٫')}٪`], ['فروش سالانه', i4?.annual_sales_bt == null ? '—' : toFaDigits(i4.annual_sales_bt.toFixed(1))], ['ماه‌های سالانه‌سازی', i4?.months_used == null ? '—' : toFaDigits(i4.months_used)]]} details={card.details?.['۴']} />;
}

export function IndustryPanel({ card, sectorPe }: { card: FtsCard; sectorPe?: { pe?: number | null; median?: number | null; peers?: number | null; sector?: string | null } | null }) {
  const i5 = card.indicators?.['5']; const status = cardStatus(card, 'industry');
  return <AxisPanel testId="panel-industry" axis="industry" title="نرخ‌گذاری صنعت" subtitle={`${i5?.sector ?? card.sector ?? '—'} — رژیم ${i5?.regime_label ?? i5?.label ?? '—'}`} status={status}
    value={i5?.label ?? i5?.regime_label ?? '—'} threshold="رژیم" chart={<PeDots pe={sectorPe?.pe ?? null} median={sectorPe?.median ?? null} peers={sectorPe?.peers ?? null} />}
    rows={[['P/E این نماد', sectorPe?.pe == null ? '—' : toFaDigits(sectorPe.pe.toFixed(1)).replace('.', '٫')], ['میانهٔ صنعت', sectorPe?.median == null ? '—' : toFaDigits(sectorPe.median.toFixed(1)).replace('.', '٫')], ['همتاها', sectorPe?.peers == null ? '—' : toFaDigits(sectorPe.peers)], ['سهم بازار', i5?.market_share_pct == null ? '—' : `${toFaDigits(i5.market_share_pct.toFixed(1))}٪`]]} details={card.details?.['۵']} />;
}

export function HistoryPanel({ card }: { card: FtsCard }) {
  const history = card.history ?? [];
  const status = cardStatus(card, 'eps');
  return <AxisPanel testId="panel-history" axis="eps" title="تاریخچهٔ گزارش‌ها" subtitle="ارقام گزارش‌شده/تجمعی؛ برچسب فصلی ندارد" status={status}
    value={history.length ? `${toFaDigits(history.length)} گزارش` : '—'} threshold="EPS"
    chart={<HistoryBars values={history.map((h) => h.eps ?? null)} labels={history.map((h) => h.period_end ?? '')} status={status} />}
    rows={[['آخرین دوره', history[history.length - 1]?.period_end ?? '—'], ['تلفیقی', history.some((h) => h.consolidated) ? 'دارد' : '—'], ['حسابرسی‌شده', history.some((h) => h.audited) ? 'دارد' : '—']]} details={card.details?.['۲']} />;
}

export function EvidencePanel({ card }: { card: FtsCard }) {
  const rows = ['۱', '۲', '۳', '۴', '۵'].flatMap((digit) => card.details?.[digit]?.subchecks ?? []);
  return (
    <section data-testid="panel-evidence" className="rounded-lg border border-[var(--fd-line)] bg-[var(--fd-panel)] p-2.5">
      <h3 className="mb-1 text-[11.5px] font-medium text-[var(--fd-text)]">شواهد و پاسخ «چرا»</h3>
      <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 max-[700px]:grid-cols-1">
        {rows.map((sub) => <div key={sub.key} className="flex items-center gap-1.5 border-b border-[var(--fd-line)] py-0.5 text-[9.5px] text-[var(--fd-text-3)]"><span>{sub.label}</span><span className="ms-auto text-[var(--fd-text)]">{sub.value ?? '—'}</span></div>)}
      </div>
    </section>
  );
}
```

### C. نوار پنجگانه، روبان امتیاز و آیتم‌ها

```tsx
function quintetItems(card: FtsCard, focusAxis: (axis: string) => void) {
  const m = card.indicators?.['1']?.monetary; const i2 = card.indicators?.['2']; const i3 = card.indicators?.['3']; const i4 = card.indicators?.['4']; const i5 = card.indicators?.['5'];
  const val = (v: number | null | undefined, suffix = '٪') => v == null ? '—' : `${toFaDigits(v.toFixed(1)).replace('.', '٫')}${suffix}`;
  return [
    { axis: 'growth', value: val(m?.monetary_pct), threshold: `کف ${toFaDigits(m?.threshold ?? '—')}٪`, status: cardStatus(card, 'growth'), chart: <Bullet value={m?.monetary_pct ?? null} max={200} threshold={m?.threshold ?? null} status={cardStatus(card, 'growth')} label="رشد" />, onFocus: () => focusAxis('growth') },
    { axis: 'eps', value: `${toFaDigits(i2?.years_available ?? 0)}/۳`, threshold: 'سال', status: cardStatus(card, 'eps'), chart: <EpsBars series={i2?.eps_series} status={cardStatus(card, 'eps')} label="EPS" />, onFocus: () => focusAxis('eps') },
    { axis: 'margin', value: val(i3?.margin_pct), threshold: `کف ${toFaDigits(i3?.threshold ?? '—')}٪`, status: cardStatus(card, 'margin'), chart: <Bullet value={i3?.margin_pct ?? null} max={60} threshold={i3?.threshold ?? null} status={cardStatus(card, 'margin')} label="حاشیه" />, onFocus: () => focusAxis('margin') },
    { axis: 'sales', value: i4?.sales_to_mcap == null ? '—' : toFaDigits(i4.sales_to_mcap.toFixed(2)).replace('.', '٫'), threshold: 'کف ۰٫۳۳', status: cardStatus(card, 'sales'), chart: <Bullet value={i4?.sales_to_mcap ?? null} max={2} threshold={i4?.sales_threshold ?? null} status={cardStatus(card, 'sales')} label="فروش/ارزش" />, onFocus: () => focusAxis('sales') },
    { axis: 'industry', value: i5?.label ?? i5?.regime_label ?? '—', threshold: 'رژیم', status: cardStatus(card, 'industry'), chart: <RegimeGlyph regime={i5?.verdict ?? null} status={cardStatus(card, 'industry')} />, onFocus: () => focusAxis('industry') },
  ];
}

function ScoreRibbon({ card }: { card: FtsCard }) {
  const statuses = (['growth', 'eps', 'margin', 'sales', 'industry'] as AxisKey[]).map((a) => cardStatus(card, a));
  const passed = statuses.filter((s) => s === 'pass').length;
  const failed = statuses.filter((s) => s === 'fail').length;
  const abstained = statuses.filter((s) => s === 'na' || s === 'unknown').length;
  return (
    <div data-testid="fundamental-score-ribbon" className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--fd-line)] bg-[var(--fd-panel-2)] px-2.5 py-1.5 text-[10px] text-[var(--fd-text-3)]">
      <strong className="text-[var(--fd-text)]">{toFaDigits(passed)} از ۵ محور قبول</strong>
      <span className="flex gap-1">{statuses.map((s, i) => <span key={i} className={`h-1.5 w-6 rounded-full is-${s}`} style={{ background: `var(--fd-${s === 'pass' ? 'up' : s === 'fail' ? 'down' : 'flat'})` }} />)}</span>
      {failed ? <span>{toFaDigits(failed)} رد</span> : null}
      {abstained ? <span>{toFaDigits(abstained)} بی‌نظر/نامشخص</span> : null}
      <span className="ms-auto">{verdictFa(card.verdict)} · امتیاز {toFaDigits(card.score ?? 0)}/۵</span>
    </div>
  );
}
```

### D. variantهای مصرف‌کننده (BottomDock/SymbolSidebar)

```tsx
export function FundamentalCards({ symbol }: { symbol: string }) {
  const query = useFtsCard(symbol);
  const card = query.data;
  const surface = useFundamentalPrefs((s) => s.surface);
  if (!card) return <p className="p-2 text-[10px] text-[var(--fd-text-3)]">کارت بنیادی در دسترس نیست.</p>;
  return (
    <div data-testid="fundamental-cards" data-fund-surface={surface} className="fundamental-surface grid grid-cols-5 gap-1 p-1 max-[900px]:grid-cols-2">
      {(['growth', 'eps', 'margin', 'sales', 'industry'] as AxisKey[]).map((axis) => {
        const meta = AXES.find((a) => a.key === axis)!; const status = cardStatus(card, axis);
        return <div key={axis} data-axis={axis} className="rounded border border-[var(--fd-line)] bg-[var(--fd-panel)] p-1.5"><span className="text-[9px] text-[var(--fd-text-3)]">{meta.num} {meta.short}</span><b className={`block text-[11px] fd-status--${status}`}>{status === 'pass' ? 'قبول' : status === 'fail' ? 'رد' : status === 'na' ? 'بی‌نظر' : 'نامشخص'}</b></div>;
      })}
    </div>
  );
}

export function FundamentalSummary({ symbol, expanded, onToggle }: { symbol: string | null; expanded?: boolean; onToggle?: () => void }) {
  const query = useFtsCard(symbol);
  const card = query.data;
  const surface = useFundamentalPrefs((s) => s.surface);
  const statuses = card ? (['growth', 'eps', 'margin', 'sales', 'industry'] as AxisKey[]).map((a) => cardStatus(card, a)) : [];
  const passed = statuses.filter((s) => s === 'pass').length;
  const body = !symbol ? 'برای دیدن بنیادی، نمادی را از تابلو انتخاب کن.' : query.isLoading ? 'پنج محور در حال خواندن…' : query.isError || !card ? 'بنیادی این نماد در دسترس نیست.' : `${toFaDigits(passed)} از ۵ محور قبول`;
  return (
    <div data-testid="symbol-fund-summary" data-fund-surface={surface} className="fundamental-surface flex w-full flex-col gap-0.5 border-y border-[var(--fd-line)] px-2 py-1 text-start">
      <span className="text-[10.5px] text-[var(--fd-text)]">{body}</span>
      {card ? <span className="flex gap-1">{statuses.map((s, i) => <span key={i} className={`h-1 w-4 rounded-full is-${s}`} style={{ background: `var(--fd-${s === 'pass' ? 'up' : s === 'fail' ? 'down' : 'flat'})` }} />)}</span> : null}
    </div>
  );
}
```

### E. اصلاحات کوچک الزامی

- در `FundamentalScreenTable` سرستون هر محور را در `<span role="columnheader" aria-sort={sortKey === key ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}>` بگذار و `data-testid="fundamental-legend"` را به نوار/فوتر راهنما (پنج محور + وضعیت‌ها + خط آستانه) اضافه کن.
- در `FundamentalDetail` جای `...skeleton...`/`...retry...`:
  ```tsx
  if (query.isLoading) return <section data-testid="fundamental-detail-loading" className="p-3 text-[11px] text-[var(--fd-text-3)]">کارت پنج‌محور در حال خواندن…</section>;
  if (query.isError || !card) return <section data-testid="fundamental-detail-error" className="p-3 text-[11px] text-[var(--fd-text-3)]">کارت بنیادی در دسترس نیست. <button type="button" onClick={() => void query.refetch()} className="tape-btn">تلاش دوباره</button></section>;
  ```
- `formatAxisValue` و تست‌ها با ارقام فارسی/علامت رشد؛ `i4_na` تکراری در fixture حذف شد.
- `Quintet`/`ScoreRibbon`/`quintetItems`/`cardStatus` از بخش C در Task 5 استفاده شوند.
- `FundamentalCards`/`FundamentalSummary` از بخش D در Task 6 استفاده شوند.
- `aria-sort`/legend در Task 3/4؛ تست‌های قدیمی از بخش A در Task 6 به‌روزرسانی شوند.
- `CorporateCalendar`/`CodalHealthStrip`/`HoldingNavPanel` در Detail حفظ؛ `QuarterlyTrend`/`useQuarters` در صورت بی‌مصرف حذف.
