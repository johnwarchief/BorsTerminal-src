# S4b — بستن دیدنی بنیادی: پلنِ اجرا

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** بستن تنظیمات آستانه‌های بنیادی، پنل P/NAV هلدینگ/بانک، و تفکیک N/A/فیلتر حذف در `frontend-v2` بدون تغییر فرمول‌ها یا قواعد FTS.

**Architecture:** تنظیمات با `GET/POST /api/fts/config` پایتون خوانده/نوشته می‌شود و در `fts_thresholds.json` می‌نشیند؛ کارت نماد از Go و جدول غربالگری در این برش از پایتون می‌آید تا کلید کش آستانه‌ها معتبر بماند. دراور تنظیمات در همان صفحه، پنل P/NAV در نمای نماد، و فیلتر حذف در جدول اضافه می‌شود.

**Tech Stack:** React 18/19 + TypeScript + Vite + TanStack Query + Zod + Vitest + Testing Library؛ Tailwind 4؛ `requestJson` تنها درِ شبکه.

**Spec:** `docs/superpowers/specs/2026-11-04-fundamental-s4b-settings-pnav-design.md`

## Global Constraints

- هیچ فرمول/آستانهٔ تازه ساخته نشود؛ فقط کلیدهای موجود `fts_thresholds.json` و پیش‌فرض‌های جزوه.
- هیچ نوشتنی در `market.db`/`user.db` انجام نشود؛ تنظیمات فقط `fts_thresholds.json`.
- فقط یک حلقهٔ زندهٔ TSETMC؛ آزمون‌های UI با `BORS_NO_FETCH_LOOPS=1` و دادهٔ جدا.
- `fetch` فقط در `frontend-v2/src/shared/api/http.ts`؛ هیچ کامپوننت مستقیم fetch نزند.
- ارقام فارسی فقط با `toFaDigits`/`faNum`/`fmt*`؛ رقم دست‌نویس در JSX ممنوع.
- متن UI فارسی RTL؛ حالت‌ها فقط با رنگ متمایز نشوند؛ Escape/فوکوس/backdrop دراور الزامی.
- بعد از هر تسک: `npm run typecheck` و `npm test` سبز؛ کامیت محلی با `-c user.name=johnwarchief -c user.email=johnwarchief@users.noreply.github.com`؛ بدون push.
- بعد از S4b: بازگشت به تکنیکال و بعد بازار (تصمیم مالک ۲۰۲۶-۱۱-۰۴).

---

### Task 1: قرارداد تنظیمات و منطق payload

**Files:**
- Create: `frontend-v2/src/features/fundamental/api/useFtsConfig.ts`
- Test: `frontend-v2/src/__tests__/fundamental-settings-api.spec.ts`

**Interfaces:**
- Produces: `FtsConfig`، `FtsConfigResponse`، `FtsSettingsDraft`، `FTS_BASIC_DEFAULTS`، `draftFromConfig(config)`، `buildFtsPayload(base, draft)`، `buildResetPayload(base)`، `useFtsConfig()`، `useSaveFtsConfig()`.

- [ ] **Step 1: نوشتن تست قرارداد و payload**

```ts
import { describe, expect, it } from 'vitest';
import {
  FTS_BASIC_DEFAULTS,
  buildFtsPayload,
  buildResetPayload,
  draftFromConfig,
} from '@features/fundamental/api/useFtsConfig';

const base = {
  ...FTS_BASIC_DEFAULTS,
  hourglass_rsi_period: 9,
  hourglass_rsi_oversold: 25,
  hourglass_ma52_position: 'above' as const,
};

describe('fts config payload', () => {
  it('keeps hourglass keys untouched when saving fundamental settings', () => {
    const draft = {
      ...draftFromConfig(base),
      growth_min: 60,
      volumeGate: false,
      epsGate: false,
      pricingGate: 'all' as const,
      insuranceGate: false,
      holdingsNa: false,
      pharmaExempt: true,
      baseMarketGate: false,
    };
    const payload = buildFtsPayload(base, draft);
    expect(payload.growth_min).toBe(60);
    expect(payload.hourglass_rsi_period).toBe(9);
    expect(payload.hourglass_rsi_oversold).toBe(25);
    expect(payload.hourglass_ma52_position).toBe('above');
    expect(payload.industry_mode).toBe('Rank_Only');
    expect(payload.v10_eps_years).toBe(1);
    expect(payload.v10_volume_breadth_min).toBe(0);
    expect(payload.reject_insurance).toBe(false);
    expect(payload.holdings_sales_na).toBe(false);
    expect(payload.pharma_margin_exempt_min).toBe(50);
    expect(payload.exclude_base_market).toBe(false);
    expect(payload.mandatory_sectors).toEqual(['خودرو', 'نیروگاه', 'لاستیک']);
  });

  it('reset only resets fundamental keys and preserves hourglass', () => {
    const payload = buildResetPayload(base);
    expect(payload.growth_min).toBe(40);
    expect(payload.margin_min).toBe(20);
    expect(payload.v10_sales_to_mcap_min).toBe(0.33);
    expect(payload.industry_mode).toBe('Exclude_Mandatory_Pricing');
    expect(payload.hourglass_rsi_period).toBe(9);
    expect(payload.hourglass_rsi_oversold).toBe(25);
    expect(payload.hourglass_ma52_position).toBe('above');
  });
});
```

- [ ] **Step 2: اجرای تست و دیدن شکست**

Run: `cd frontend-v2 && npx vitest run src/__tests__/fundamental-settings-api.spec.ts`
Expected: FAIL — ماژول `useFtsConfig` وجود ندارد.

- [ ] **Step 3: پیاده‌سازی قرارداد**

```ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { requestJson, getJson } from '@shared/api/http';

const Num = z.number().nullish();
const Str = z.string().nullish();
const Bool = z.boolean().nullish();

export const FtsConfigPayloadSchema = z.looseObject({
  growth_min: z.number(), eps_years: z.number(), margin_min: z.number(),
  margin_optimal: z.number(), sales_to_mcap_min: z.number(),
  profit_potential_min: z.number(), industry_mode: z.string(),
  watchlist_max: z.number(), mcap_min_hmt: z.number(),
  suspended_max_stale_sessions: z.number(), filter_m141: z.boolean(),
  min_trade_val: z.number(), mandatory_sectors: z.array(z.string()),
  free_sectors: z.array(z.string()), reject_insurance: Bool,
  include_industries: z.array(z.string()).nullish(),
  exclude_industries: z.array(z.string()).nullish(),
  v10_monetary_growth_min: Num, v10_volume_growth_min: Num,
  v10_volume_breadth_min: Num, v10_eps_years: Num, v10_margin_min: Num,
  v10_margin_ideal: Num, v10_sales_to_mcap_min: Num, v10_potential_min: Num,
  v10_inflation_basis: Num,
  hourglass_rsi_period: z.number(), hourglass_rsi_oversold: z.number(),
  hourglass_ma52_position: z.enum(['below', 'above', 'either']),
  holdings_sales_na: Bool, pharma_margin_exempt_min: Num,
  exclude_base_market: Bool, exclude_rejected_indicators: z.array(z.string()).nullish(),
});

export const FtsConfigResponseSchema = z.looseObject({
  status: z.string(),
  config: FtsConfigPayloadSchema.nullish(),
  message: Str,
  errors: z.record(z.string(), z.string()).nullish(),
});
export type FtsConfig = z.infer<typeof FtsConfigPayloadSchema>;
export type FtsConfigResponse = z.infer<typeof FtsConfigResponseSchema>;

export const FTS_BASIC_DEFAULTS = {
  growth_min: 40, eps_years: 3, margin_min: 20, margin_optimal: 30,
  sales_to_mcap_min: 0.33, profit_potential_min: 40,
  industry_mode: 'Exclude_Mandatory_Pricing', watchlist_max: 50,
  mcap_min_hmt: 0, suspended_max_stale_sessions: 3, filter_m141: false,
  min_trade_val: 0,
  mandatory_sectors: ['خودرو', 'نیروگاه', 'لاستیک'],
  free_sectors: ['سیمان', 'پتروشیمی', 'شیمیایی', 'فلزات', 'کانی', 'کاشی', 'سرامیک', 'شیشه', 'کانه', 'معادن', 'نفت', 'محصولات فلزی'],
  reject_insurance: true, include_industries: [], exclude_industries: [],
  v10_monetary_growth_min: 60, v10_volume_growth_min: 0,
  v10_volume_breadth_min: 0.6, v10_eps_years: 3, v10_margin_min: 20,
  v10_margin_ideal: 30, v10_sales_to_mcap_min: 0.33, v10_potential_min: 40,
  v10_inflation_basis: 60, hourglass_rsi_period: 7, hourglass_rsi_oversold: 30,
  hourglass_ma52_position: 'below' as const, holdings_sales_na: true,
  pharma_margin_exempt_min: 0, exclude_base_market: true,
  exclude_rejected_indicators: [],
};

export interface FtsSettingsDraft {
  growth_min: number; v10_monetary_growth_min: number; v10_inflation_basis: number;
  margin_min: number; v10_sales_to_mcap_min: number; profit_potential_min: number;
  suspended_max_stale_sessions: number; volumeGate: boolean; epsGate: boolean;
  pricingGate: 'free_only' | 'all'; insuranceGate: boolean; holdingsNa: boolean;
  pharmaExempt: boolean; baseMarketGate: boolean;
}

export function draftFromConfig(config: Partial<FtsConfig> | null | undefined): FtsSettingsDraft {
  const c = config ?? {};
  return {
    growth_min: c.growth_min ?? 40,
    v10_monetary_growth_min: c.v10_monetary_growth_min ?? 60,
    v10_inflation_basis: c.v10_inflation_basis ?? 60,
    margin_min: c.margin_min ?? 20,
    v10_sales_to_mcap_min: c.v10_sales_to_mcap_min ?? 0.33,
    profit_potential_min: c.profit_potential_min ?? 40,
    suspended_max_stale_sessions: c.suspended_max_stale_sessions ?? 3,
    volumeGate: (c.v10_volume_breadth_min ?? 0.6) > 0,
    epsGate: (c.v10_eps_years ?? 3) >= 3,
    pricingGate: c.industry_mode === 'Rank_Only' ? 'all' : 'free_only',
    insuranceGate: c.reject_insurance ?? true,
    holdingsNa: c.holdings_sales_na ?? true,
    pharmaExempt: (c.pharma_margin_exempt_min ?? 0) > 0,
    baseMarketGate: c.exclude_base_market ?? true,
  };
}

export function buildFtsPayload(base: Partial<FtsConfig>, draft: FtsSettingsDraft): Record<string, unknown> {
  const {
    volumeGate, epsGate, pricingGate, insuranceGate, holdingsNa,
    pharmaExempt, baseMarketGate, ...numbers
  } = draft;
  return {
    ...base,
    ...numbers,
    industry_mode: pricingGate === 'all' ? 'Rank_Only' : 'Exclude_Mandatory_Pricing',
    mandatory_sectors: [...FTS_BASIC_DEFAULTS.mandatory_sectors],
    reject_insurance: insuranceGate,
    v10_eps_years: epsGate ? 3 : 1,
    v10_volume_growth_min: 0,
    v10_volume_breadth_min: volumeGate ? 0.6 : 0,
    margin_optimal: Math.max(draft.margin_min, 30),
    v10_potential_min: draft.profit_potential_min,
    holdings_sales_na: holdingsNa,
    pharma_margin_exempt_min: pharmaExempt ? 50 : 0,
    exclude_base_market: baseMarketGate,
  };
}

export function buildResetPayload(base: Partial<FtsConfig>): Record<string, unknown> {
  return {
    ...base,
    ...FTS_BASIC_DEFAULTS,
    mandatory_sectors: [...FTS_BASIC_DEFAULTS.mandatory_sectors],
    hourglass_rsi_period: base.hourglass_rsi_period ?? 7,
    hourglass_rsi_oversold: base.hourglass_rsi_oversold ?? 30,
    hourglass_ma52_position: base.hourglass_ma52_position ?? 'below',
  };
}

export function useFtsConfig() {
  return useQuery({
    queryKey: ['fts-config'],
    queryFn: ({ signal }) => getJson('/api/fts/config', FtsConfigResponseSchema, signal),
    staleTime: 60_000,
  });
}

export function useSaveFtsConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      requestJson('/api/fts/config', FtsConfigResponseSchema, { method: 'POST', body: payload }),
    onSuccess: (res) => {
      if (res.status !== 'success') return;
      qc.invalidateQueries({ queryKey: ['screener-core'] });
      qc.invalidateQueries({ queryKey: ['fts-card'] });
      qc.invalidateQueries({ queryKey: ['fts-config'] });
    },
  });
}
```

- [ ] **Step 4: اجرای تست**

Run: `cd frontend-v2 && npx vitest run src/__tests__/fundamental-settings-api.spec.ts`
Expected: PASS.

- [ ] **Step 5: commit**

```bash
git add frontend-v2/src/features/fundamental/api/useFtsConfig.ts frontend-v2/src/__tests__/fundamental-settings-api.spec.ts
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(fundamental): قرارداد تنظیمات و payload کامل"
```

---

### Task 2: دراور تنظیمات و دکمهٔ آن

**Files:**
- Create: `frontend-v2/src/features/fundamental/lib/exclusionFilter.ts` (فقط store/برچسب‌ها؛ منطق فیلتر در Task 5)
- Create: `frontend-v2/src/features/fundamental/ui/FtsSettingsDrawer.tsx`
- Test: `frontend-v2/src/__tests__/fundamental-settings.spec.tsx`

**Interfaces:**
- Consumes: `useFtsConfig`، `useSaveFtsConfig`، `draftFromConfig`، `buildFtsPayload`، `buildResetPayload`، `FtsSettingsDraft`.
- Produces: `FtsSettingsTrigger({ open, onToggle })`، `FtsSettingsDrawer({ open, onClose })`.

- [ ] **Step 1: تست بازکردن، ذخیره، خطا و بازگردانی**

```tsx
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useFtsConfig, useSaveFtsConfig, FTS_BASIC_DEFAULTS } from '@features/fundamental/api/useFtsConfig';
import { FtsSettingsDrawer } from '@features/fundamental/ui/FtsSettingsDrawer';

vi.mock('@features/fundamental/api/useFtsConfig', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@features/fundamental/api/useFtsConfig')>();
  return { ...actual, useFtsConfig: vi.fn(), useSaveFtsConfig: vi.fn() };
});
const mockedCfg = vi.mocked(useFtsConfig);
const mockedSave = vi.mocked(useSaveFtsConfig);
const mutate = vi.fn();

beforeEach(() => {
  mutate.mockReset();
  mockedCfg.mockReturnValue({
    data: { status: 'success', config: { ...FTS_BASIC_DEFAULTS, growth_min: 40 } },
    isLoading: false, isError: false,
  } as unknown as ReturnType<typeof useFtsConfig>);
  mockedSave.mockReturnValue({ mutate, isPending: false, isSuccess: false, isError: false, data: undefined } as unknown as ReturnType<typeof useSaveFtsConfig>);
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe('fts settings drawer', () => {
  it('saves a full payload and keeps hourglass keys', () => {
    render(<FtsSettingsDrawer open onClose={vi.fn()} />);
    fireEvent.change(screen.getByTestId('fts-growth-min'), { target: { value: '60' } });
    fireEvent.click(screen.getByTestId('fts-settings-save'));
    expect(mutate).toHaveBeenCalledTimes(1);
    const payload = mutate.mock.calls[0]![0];
    expect(payload.growth_min).toBe(60);
    expect(payload.hourglass_rsi_period).toBe(7);
    expect(payload.mandatory_sectors).toEqual(['خودرو', 'نیروگاه', 'لاستیک']);
  });

  it('shows server validation errors and no success message', () => {
    mockedSave.mockReturnValue({
      mutate, isPending: false, isSuccess: true, isError: false,
      data: { status: 'error', message: 'برخی مقادیر معتبر نیستند', errors: { growth_min: 'عدد معتبر نیست' } },
    } as unknown as ReturnType<typeof useSaveFtsConfig>);
    render(<FtsSettingsDrawer open onClose={vi.fn()} />);
    expect(screen.getByTestId('fts-settings-error').textContent).toContain('عدد معتبر نیست');
    expect(screen.queryByTestId('fts-settings-success')).toBeNull();
  });

  it('closes on Escape', () => {
    const onClose = vi.fn();
    render(<FtsSettingsDrawer open onClose={onClose} />);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('reset sends fundamental defaults and preserves hourglass', () => {
    render(<FtsSettingsDrawer open onClose={vi.fn()} />);
    fireEvent.click(screen.getByTestId('fts-settings-reset'));
    const payload = mutate.mock.calls[0]![0];
    expect(payload.growth_min).toBe(40);
    expect(payload.hourglass_rsi_period).toBe(7);
  });
});
```

- [ ] **Step 2: اجرای تست و دیدن شکست**

Run: `cd frontend-v2 && npx vitest run src/__tests__/fundamental-settings.spec.tsx`
Expected: FAIL — کامپوننت وجود ندارد.

- [ ] **Step 3: پیاده‌سازی دراور**

`exclusionFilter.ts` (حداقلِ موردنیاز دراور؛ منطق فیلتر در Task 5):

```ts
import { useSyncExternalStore } from 'react';

export type ExcludeAxis = '1a' | '1b' | '2' | '3' | '4' | '5';
export const EXCLUDE_AXES: readonly ExcludeAxis[] = ['1a', '1b', '2', '3', '4', '5'];
export const EXCLUDE_LABEL: Record<ExcludeAxis, string> = {
  '1a': 'رشد ریالی (شاخص ۱الف)', '1b': 'رشد تولیدی (شاخص ۱ب)',
  '2': 'سابقهٔ سه‌سالهٔ EPS (شاخص ۲)', '3': 'حاشیهٔ ناخالص (شاخص ۳)',
  '4': 'فروش / ارزش بازار (شاخص ۴)', '5': 'دروازهٔ صنعت (شاخص ۵)',
};
export const NO_ROW_FLAG: Partial<Record<ExcludeAxis, string>> = {
  '1b': 'پاسخ غربالگری ستون تناژ فیزیکی ندارد؛ این گزینه هیچ ردیفی را حذف نمی‌کند.',
};
const STORAGE_KEY = 'fts:exclude-rejected-axes';
function isAxis(v: unknown): v is ExcludeAxis {
  return typeof v === 'string' && (EXCLUDE_AXES as readonly string[]).includes(v);
}
function normalize(list: readonly unknown[] | null | undefined): ExcludeAxis[] {
  if (!Array.isArray(list)) return [];
  return EXCLUDE_AXES.filter((a) => list.some((x) => isAxis(x) && x === a));
}
function readStorage(): ExcludeAxis[] {
  try {
    const raw = typeof localStorage === 'undefined' ? null : localStorage.getItem(STORAGE_KEY);
    return raw ? normalize(JSON.parse(raw) as unknown[]) : [];
  } catch { return []; }
}
let state: ExcludeAxis[] = readStorage();
const listeners = new Set<() => void>();
function emit() { for (const l of listeners) l(); }
export function getExcludeAxes(): ExcludeAxis[] { return state; }
export function setExcludeAxes(next: readonly ExcludeAxis[]) {
  const norm = normalize(next);
  const same = norm.length === state.length && norm.every((a, i) => a === state[i]);
  state = norm;
  try {
    if (typeof localStorage !== 'undefined') localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch { /* فقط همان نشست */ }
  if (!same) emit();
}
export function toggleExcludeAxis(axis: ExcludeAxis) {
  setExcludeAxes(state.includes(axis) ? state.filter((a) => a !== axis) : [...state, axis]);
}
export function resetExcludeAxes() { setExcludeAxes([]); }
function subscribe(cb: () => void) { listeners.add(cb); return () => listeners.delete(cb); }
export function useExcludeAxes(): ExcludeAxis[] {
  return useSyncExternalStore(subscribe, getExcludeAxes, getExcludeAxes);
}
```

ساختار کلیدی دراور:

```tsx
import { useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { faNum, toFaDigits } from '@shared/lib/fa';
import {
  FTS_BASIC_DEFAULTS, buildFtsPayload, buildResetPayload, draftFromConfig,
  useFtsConfig, useSaveFtsConfig, type FtsSettingsDraft,
} from '../api/useFtsConfig';
import { EXCLUDE_AXES, EXCLUDE_LABEL, NO_ROW_FLAG, useExcludeAxes, toggleExcludeAxis, resetExcludeAxes } from '../lib/exclusionFilter';

export function FtsSettingsTrigger({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  return (
    <span className="inline-flex" data-testid="fts-settings-trigger">
      <button type="button" data-testid="fts-settings-btn" aria-expanded={open} aria-haspopup="dialog"
        onClick={onToggle} className="tape-btn">تنظیمات</button>
      {open ? <FtsSettingsDrawer open onClose={onToggle} /> : null}
    </span>
  );
}
```

> **مهم:** دراور فقط وقتی `open` است mount می‌شود؛ وگرنه `useFtsConfig` در جدول/نمادِ بسته یک درخواست ناخواسته می‌زند و تست‌های موجودِ صفحه را می‌شکند.

`FtsSettingsDrawer`:
- `const cfg = useFtsConfig(); const save = useSaveFtsConfig();`
- `const [draft, setDraft] = useState<FtsSettingsDraft>(() => draftFromConfig(null));`
- `useEffect` sets draft from `cfg.data?.config`.
- `const panelRef = useRef<HTMLElement>(null); const uid = useId();`
- Escape/Tab trap effect when `open`.
- If `cfg.isLoading` → متن «در حال خواندن تنظیمات…».
- If `cfg.isError` → `data-testid="fts-settings-load-error"` + تلاش دوباره.
- Fields:
  - Range `fts-growth-min` (0..150 step 5), `fts-monetary-growth`, `fts-inflation-basis` (0..100 step 5), `fts-margin-min` (5..60), `fts-sales-to-mcap` (10..100), `fts-profit-potential` (0..100 step 5).
  - Switches `fts-volume-gate`, `fts-eps-gate`, `fts-insurance-gate`, `fts-holdings-na`, `fts-pharma-exempt`, `fts-base-market`, `fts-suspended`.
  - Radio `fts-pricing-all` / `fts-pricing-free`.
  - Exclusion switches `fts-exclude-${axis}`; `1b` disabled? Keep enabled but show `NO_ROW_FLAG` and no row hiding.
- Save `data-testid="fts-settings-save"` calls `save.mutate(buildFtsPayload(cfg.data!.config!, draft), { onSuccess: (res) => { if (res.status === 'success' && res.config) setDraft(draftFromConfig(res.config)); } })`.
- Reset `data-testid="fts-settings-reset"` calls `save.mutate(buildResetPayload(cfg.data!.config!))`.
- Error box `fts-settings-error`: network error or `save.data?.status === 'error'`; include `Object.values(errors).join(' · ')`.
- Success box `fts-settings-success` only when `save.isSuccess && save.data?.status === 'success'`.
- Backdrop `data-testid="fts-settings-backdrop"` onClick `onClose`.
- Panel `role="dialog" aria-modal="true" aria-label="پنل تنظیمات پیش‌شرط‌های FTS" data-testid="fts-settings-panel" tabIndex={-1}`; fixed right (RTL `start-0`), width 420 max 92vw, scroll-y.
- Use `createPortal(..., document.body)`.

- [ ] **Step 4: اجرای تست**

Run: `cd frontend-v2 && npx vitest run src/__tests__/fundamental-settings.spec.tsx`
Expected: PASS.

- [ ] **Step 5: commit**

```bash
git add frontend-v2/src/features/fundamental/ui/FtsSettingsDrawer.tsx frontend-v2/src/__tests__/fundamental-settings.spec.tsx
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(fundamental): دراور تنظیمات آستانه‌ها"
```

---

### Task 3: اتصال دکمهٔ تنظیمات به جدول و نمای نماد

**Files:**
- Modify: `frontend-v2/src/features/fundamental/routes/FundamentalPage.tsx`
- Modify: `frontend-v2/src/features/fundamental/ui/FundamentalScreenTable.tsx`
- Modify: `frontend-v2/src/features/fundamental/ui/FundamentalDetail.tsx`
- Test: `frontend-v2/src/__tests__/fundamental-settings.spec.tsx` (extend)

**Interfaces:**
- `FundamentalScreenTable` gets `settingsSlot?: ReactNode`.
- `FundamentalPage` owns `settingsOpen` for the table view.
- `FundamentalDetail` owns `settingsOpen` and renders the trigger in its header.

- [ ] **Step 1: تست وجود دکمه در جدول و نمای نماد**

```tsx
it('shows the settings trigger in the table toolbar', () => {
  render(<MemoryRouter initialEntries={['/fundamental']}><FundamentalPage /></MemoryRouter>);
  expect(screen.getByTestId('fts-settings-btn')).toBeTruthy();
});
```

- [ ] **Step 2: اجرا و شکست**

Run: `cd frontend-v2 && npx vitest run src/__tests__/fundamental-settings.spec.tsx`
Expected: FAIL — دکمه وجود ندارد.

- [ ] **Step 3: پیاده‌سازی**

`FundamentalScreenTable`:
```tsx
interface Props { rows: readonly ScreenerCoreRow[]; onSelect: (symbol: string) => void; asOf?: string | null; settingsSlot?: ReactNode; }
// نوار موجود (جستجو/فیلتر صنعت/خروجی/شمارش/راهنما) دست‌نخورده می‌ماند؛ فقط
// انتهای همان div این خط اضافه می‌شود:
{settingsSlot ?? <span />}
```

`FundamentalPage`:
```tsx
const [settingsOpen, setSettingsOpen] = useState(false);
...
<FundamentalScreenTable ... settingsSlot={<FtsSettingsTrigger open={settingsOpen} onToggle={() => setSettingsOpen((v) => !v)} />} />
```

`FundamentalDetail` header:
```tsx
const [settingsOpen, setSettingsOpen] = useState(false);
...
<span className="ms-auto">
  <FtsSettingsTrigger open={settingsOpen} onToggle={() => setSettingsOpen((v) => !v)} />
</span>
```

- [ ] **Step 4: اجرا و سبز**

Run: `cd frontend-v2 && npm run typecheck && npx vitest run src/__tests__/fundamental-settings.spec.tsx src/__tests__/fundamental-page.spec.tsx src/__tests__/fundamental-detail.spec.tsx`
Expected: PASS.

- [ ] **Step 5: commit**

```bash
git add frontend-v2/src/features/fundamental/routes/FundamentalPage.tsx frontend-v2/src/features/fundamental/ui/FundamentalScreenTable.tsx frontend-v2/src/features/fundamental/ui/FundamentalDetail.tsx
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(fundamental): دکمهٔ تنظیمات در جدول و نمای نماد"
```

---

### Task 4: پنل P/NAV هلدینگ و بانک

**Files:**
- Create: `frontend-v2/src/features/fundamental/lib/assetScope.ts`
- Create: `frontend-v2/src/features/fundamental/ui/HoldingNavPanel.tsx`
- Modify: `frontend-v2/src/features/fundamental/api/useFtsCard.ts`
- Modify: `frontend-v2/src/features/fundamental/ui/FundamentalDetail.tsx`
- Test: `frontend-v2/src/__tests__/fundamental-holding.spec.tsx`

**Interfaces:**
- `isHoldingCard(card): boolean`، `isBankCard(card): boolean`؛ `HoldingNavPanel({ bankLike }: { bankLike: boolean })`.

- [ ] **Step 1: تست چهار حالت**

```tsx
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useFtsCard } from '@features/fundamental/api/useFtsCard';
import { useQuarters } from '@features/fundamental/api/useQuarters';
import { useSectorPe } from '@features/fundamental/api/useSectorPe';
import { useCodalHealth } from '@features/fundamental/api/useCodalHealth';
import { FundamentalDetail } from '@features/fundamental/ui/FundamentalDetail';

vi.mock('@features/fundamental/api/useFtsCard', () => ({ useFtsCard: vi.fn() }));
vi.mock('@features/fundamental/api/useQuarters', () => ({ useQuarters: vi.fn() }));
vi.mock('@features/fundamental/api/useSectorPe', () => ({ useSectorPe: vi.fn() }));
vi.mock('@features/fundamental/api/useCodalHealth', () => ({ useCodalHealth: vi.fn() }));
vi.mock('@features/fundamental/api/useCalendar', () => ({ useSymbolCalendar: () => ({ data: { status: 'ok', events: [] }, isLoading: false, isError: false }) }));

const card = (overrides: Record<string, unknown>) => ({
  data: { status: 'success', symbol: 'ویسا', sector: 'سرمایه‌گذاری‌ها', score: 3, verdict: 'WATCH',
    details: {}, freshness: { as_of: '2026-08-23', axes: {} }, ...overrides },
  isLoading: false, isError: false,
});

beforeEach(() => {
  vi.mocked(useQuarters).mockReturnValue({ data: { status: 'success', quarters: [] }, isLoading: false, isError: false } as never);
  vi.mocked(useSectorPe).mockReturnValue({ data: { pe: 5, median: 6, sector: 'سرمایه‌گذاری‌ها', peers: 3 }, isLoading: false, isError: false } as never);
  vi.mocked(useCodalHealth).mockReturnValue({ data: { status: 'success', queue: {}, dirty_symbols: 0, gap_flag: false }, isLoading: false, isError: false } as never);
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe('P/NAV holding panel', () => {
  it('holding replaces sector P/E with an explicit N/A panel', () => {
    vi.mocked(useFtsCard).mockReturnValue(card({ profile: { kind: 'holding', margin_class: 'holding', label: 'هلدینگ / سرمایه‌گذاری' }, indicators: { '4': { na: true, exempt: true } } }) as never);
    render(<FundamentalDetail symbol="ویسا" onBack={vi.fn()} />);
    expect(screen.getByTestId('holding-pnav-panel')).toBeTruthy();
    expect(screen.queryByTestId('sector-pe-panel')).toBeNull();
    expect(screen.getByTestId('holding-nav-na').textContent).toContain('NAV');
    expect(screen.queryByText(/P\/NAV ≈/)).toBeNull();
  });

  it('bank uses the bank wording', () => {
    vi.mocked(useFtsCard).mockReturnValue(card({ profile: { kind: 'holding', margin_class: 'bank', label: 'بانک / مؤسسهٔ اعتباری' }, indicators: { '4': { na: true, exempt: true } } }) as never);
    render(<FundamentalDetail symbol="وبملت" onBack={vi.fn()} />);
    expect(screen.getByTestId('holding-pnav-panel').textContent).toContain('بانک');
  });

  it('fund shows not applicable and no P/NAV panel', () => {
    vi.mocked(useFtsCard).mockReturnValue(card({ applicable: false, profile: { kind: 'fund' } }) as never);
    render(<FundamentalDetail symbol="صندوق" onBack={vi.fn()} />);
    expect(screen.getByTestId('fundamental-not-applicable')).toBeTruthy();
    expect(screen.queryByTestId('holding-pnav-panel')).toBeNull();
  });

  it('normal symbol keeps sector P/E', () => {
    vi.mocked(useFtsCard).mockReturnValue(card({ profile: { kind: 'production' }, indicators: { '4': { na: false } } }) as never);
    render(<FundamentalDetail symbol="فولاد" onBack={vi.fn()} />);
    expect(screen.getByTestId('sector-pe-panel')).toBeTruthy();
  });
});
```

- [ ] **Step 2: اجرا و شکست**

Run: `cd frontend-v2 && npx vitest run src/__tests__/fundamental-holding.spec.tsx`
Expected: FAIL — پنل وجود ندارد.

- [ ] **Step 3: پیاده‌سازی**

`useFtsCard.ts` اضافه‌ها:
```ts
profile: z.looseObject({ kind: Str, margin_class: Str, label: Str, volume_applicable: Bool }).nullish(),
```
و در `Axis4Schema`: `na: Bool, exempt: Bool, available: Bool`؛ در `Axis3Schema`: `na: Bool, margin_class: Str`.

`assetScope.ts`:
```ts
import type { FtsCard } from '../api/useFtsCard';
const BANK_RE = /بانک|بانك|اعتباری/;
export function isHoldingCard(card: FtsCard): boolean {
  const axis4 = card.indicators?.['4'];
  return card.profile?.kind === 'holding' || axis4?.na === true || axis4?.exempt === true;
}
export function isBankCard(card: FtsCard): boolean {
  return card.profile?.margin_class === 'bank'
    || BANK_RE.test(card.profile?.label ?? '')
    || BANK_RE.test(card.sector ?? '');
}
```

`HoldingNavPanel.tsx`:
```tsx
export function HoldingNavPanel({ bankLike }: { bankLike: boolean }) {
  return (
    <section data-testid="holding-pnav-panel" className="rounded-[var(--radius-sm)] border border-line bg-panel p-2 t-9">
      <div className="mb-1 flex items-center justify-between">
        <h3 className="t-10 font-bold text-text-2">{bankLike ? 'ارزش‌گذاری بانک' : 'ارزش‌گذاری هلدینگ'}</h3>
        <span className="rounded-[3px] border border-warn/40 bg-warn/10 px-1 text-warn">N/A</span>
      </div>
      <p data-testid="holding-nav-na" className="leading-relaxed text-text-2">
        {bankLike
          ? 'N/A — قابل ارزیابی نیست؛ این نماد بانک/مؤسسهٔ اعتباری است و P/NAV برای این طبقه تعریف نشده است.'
          : 'N/A — قابل ارزیابی نیست؛ این نماد سرمایه‌گذاری/هلدینگ است و در کدال ارزش خالص دارایی (NAV) منتشر نشده؛ بنابراین P/NAV محاسبه نمی‌شود و جای آن عددی گذاشته نمی‌شود.'}
      </p>
      <p className="mt-1 text-text-3">
        {bankLike ? 'بانک‌ها از شرط «نسبت فروش به ارزش بازار» (شاخص ۴) معاف‌اند.' : 'هلدینگ‌ها از شرط «نسبت فروش به ارزش بازار» (شاخص ۴) معاف‌اند.'}
      </p>
    </section>
  );
}
```

`FundamentalDetail.tsx`:
```tsx
const holding = card ? isHoldingCard(card) : false;
const bank = card ? isBankCard(card) : false;
const notApplicable = card?.applicable === false;
...
{holding ? <span data-testid="holding-class-badge" className="...">{bank ? 'بانک / مؤسسهٔ اعتباری' : 'هلدینگ / سرمایه‌گذاری'}</span> : null}
...
{notApplicable ? (
  <section data-testid="fundamental-not-applicable" className="...">FTS ندارد — این نماد صندوق/ابزار است و غربالگری پنج‌شاخص برای آن تعریف نشده است.</section>
) : holding ? (
  <HoldingNavPanel bankLike={bank} />
) : (
  <section data-testid="sector-pe-panel" className="rounded-[var(--radius-sm)] border border-line bg-panel p-2 t-9">
    <h3 className="mb-1 t-10 font-bold text-text-2">P/E صنعت</h3>
    <div className="flex flex-wrap items-baseline gap-1.5">
      <span className="text-text-3">این نماد</span>
      <b data-testid="sector-pe" className="num text-text">
        {sectorPe.data?.pe != null ? faNum(sectorPe.data.pe, 1) : '—'}
      </b>
      <span className="text-text-3">میانهٔ صنعت</span>
      <b data-testid="sector-pe-median" className="num text-text">
        {sectorPe.data?.median != null ? faNum(sectorPe.data.median, 1) : '—'}
      </b>
    </div>
    <p className="mt-1 text-text-3">
      {sectorPe.data?.sector ?? 'صنعت نامشخص'}
      {sectorPe.data?.peers != null ? ` · ${faNum(sectorPe.data.peers)} نماد با P/E مثبت` : ''}
    </p>
  </section>
)}
```

- [ ] **Step 4: اجرا و سبز**

Run: `cd frontend-v2 && npx vitest run src/__tests__/fundamental-holding.spec.tsx src/__tests__/fundamental-detail.spec.tsx`
Expected: PASS.

- [ ] **Step 5: commit**

```bash
git add frontend-v2/src/features/fundamental/lib/assetScope.ts frontend-v2/src/features/fundamental/ui/HoldingNavPanel.tsx frontend-v2/src/features/fundamental/api/useFtsCard.ts frontend-v2/src/features/fundamental/ui/FundamentalDetail.tsx frontend-v2/src/__tests__/fundamental-holding.spec.tsx
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(fundamental): پنل N/A هلدینگ و بانک"
```

---

### Task 5: فیلتر حذف بر اساس شاخص

**Files:**
- Modify: `frontend-v2/src/features/fundamental/lib/exclusionFilter.ts` (افزودن `rejectedFor`/`applyExcludeFilter`)
- Modify: `frontend-v2/src/features/fundamental/api/useScreenerCore.ts`
- Modify: `frontend-v2/src/features/fundamental/ui/FundamentalScreenTable.tsx`
- Modify: `frontend-v2/src/__tests__/fundamental-page.spec.tsx` (reset store در beforeEach)
- Test: `frontend-v2/src/__tests__/fundamental-exclusion.spec.tsx`

**Interfaces:**
- Produces: `EXCLUDE_AXES`، `EXCLUDE_LABEL`، `NO_ROW_FLAG`، `useExcludeAxes()`، `setExcludeAxes()`، `toggleExcludeAxis()`، `resetExcludeAxes()`، `rejectedFor(row, axis)`، `applyExcludeFilter(rows, axes)`.

- [ ] **Step 1: تست حذف و استثناها**

```tsx
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useScreenerCore, type ScreenerCoreRow } from '@features/fundamental/api/useScreenerCore';
import { FundamentalPage } from '@features/fundamental/routes/FundamentalPage';
import { resetExcludeAxes, setExcludeAxes } from '@features/fundamental/lib/exclusionFilter';

vi.mock('@features/fundamental/api/useScreenerCore', () => ({ useScreenerCore: vi.fn() }));

const rows: ScreenerCoreRow[] = [
  { symbol: 'فولاد', sector_name: 'فلزات', score: 5, verdict: 'قبول', i1_pass: true, i2_pass: true, i3_pass: true, i4_pass: true, i5_pass: true, i1_na: false, i2_na: false, i3_na: false, i4_na: false },
  { symbol: 'خساپا', sector_name: 'خودرو', score: 2, verdict: 'رد', i1_pass: false, i1_na: false, i2_pass: null, i2_na: true, i3_pass: null, i3_na: false, i4_pass: false, i4_na: false, i5_pass: false },
  { symbol: 'شپنا', sector_name: 'پالایش', score: 3, verdict: 'بررسی', i1_pass: true, i1_na: false, i2_pass: true, i2_na: false, i3_pass: null, i3_na: false, gross_margin: 12, i4_pass: true, i4_na: false, i5_pass: true },
];

beforeEach(() => {
  resetExcludeAxes();
  vi.mocked(useScreenerCore).mockReturnValue({ data: { status: 'success', count: 3, data: rows, as_of: '2026-11-03' }, isLoading: false, isError: false, refetch: vi.fn() } as never);
});
afterEach(() => { cleanup(); resetExcludeAxes(); vi.clearAllMocks(); });

describe('exclusion filter', () => {
  it('hides only rows rejected by an active axis', () => {
    setExcludeAxes(['1a']);
    render(<MemoryRouter initialEntries={['/fundamental']}><FundamentalPage /></MemoryRouter>);
    expect(screen.queryByTestId('fundamental-row-خساپا')).toBeNull();
    expect(screen.getByTestId('fundamental-row-فولاد')).toBeTruthy();
    expect(screen.getByTestId('fundamental-hidden-count').textContent).toContain('۱');
  });

  it('1b never hides rows', () => {
    setExcludeAxes(['1b']);
    render(<MemoryRouter initialEntries={['/fundamental']}><FundamentalPage /></MemoryRouter>);
    expect(screen.getByTestId('fundamental-row-خساپا')).toBeTruthy();
    expect(screen.queryByTestId('fundamental-hidden-count')).toBeNull();
  });

  it('hides incomplete axis data but keeps rows that have the data', () => {
    setExcludeAxes(['3']);
    render(<MemoryRouter initialEntries={['/fundamental']}><FundamentalPage /></MemoryRouter>);
    expect(screen.queryByTestId('fundamental-row-خساپا')).toBeNull();
    expect(screen.getByTestId('fundamental-row-شپنا')).toBeTruthy();
  });
});
```

- [ ] **Step 2: اجرا و شکست**

Run: `cd frontend-v2 && npx vitest run src/__tests__/fundamental-exclusion.spec.tsx`
Expected: FAIL — ماژول/فیلتر وجود ندارد.

- [ ] **Step 3: پیاده‌سازی**

`exclusionFilter.ts` — افزودن به فایل موجود (store/برچسب‌ها در Task 2 ساخته شد):
```ts
import type { ScreenerCoreRow } from '../api/useScreenerCore';

export function rejectedFor(row: ScreenerCoreRow, axis: ExcludeAxis): boolean | null {
  switch (axis) {
    case '1a': if (row.i1_pass === false) return true; if (row.i1_pass == null && row.rev_growth == null) return true; return row.i1_pass === true ? false : null;
    case '1b': return null;
    case '2': {
      if (row.i2_na === true) return null;
      if (row.i2_pass === false) return true;
      if (row.i2_pass === true) return false;
      const series = Array.isArray(row.eps_series) ? row.eps_series : [];
      const real = series.filter((v) => typeof v === 'number' && Number.isFinite(v)).length;
      const required = row.eps_years_required ?? 3;
      const available = Math.max(real, Math.min(Math.max(0, Math.trunc(row.eps_years_available ?? 0)), required));
      return available < required ? true : null;
    }
    case '3': if (row.i3_pass === false) return true; if (row.i3_pass == null && row.gross_margin == null) return true; return row.i3_pass === true ? false : null;
    case '4': if (row.i4_pass === false) return true; if (row.i4_pass == null && row.profit_potential_pct == null && row.sales_to_mcap == null) return true; return row.i4_pass === true ? false : null;
    case '5': if (row.i5_pass === false) return true; if (row.pricing_mode == null) return true; return row.i5_pass === true ? false : null;
    default: return null;
  }
}
export function applyExcludeFilter(rows: readonly ScreenerCoreRow[], axes: readonly ExcludeAxis[]) {
  const active = axes.filter((a) => EXCLUDE_AXES.includes(a) && !NO_ROW_FLAG[a]);
  if (active.length === 0) return { rows: [...rows], hidden: 0 };
  const kept = rows.filter((r) => !active.some((a) => rejectedFor(r, a) === true));
  return { rows: kept, hidden: rows.length - kept.length };
}
```

`useScreenerCore.ts` تایپ‌ها:
```ts
rev_growth: Num, eps_series: z.array(z.number().nullable()).nullish(),
eps_years_required: Num, eps_years_available: Num, gross_margin: Num,
profit_potential_pct: Num, sales_to_mcap: Num, pricing_mode: Str,
i1a_pass: Bool, i1b_applicable: Bool, i1b_data_gap: Bool,
```

`FundamentalScreenTable.tsx`:
```tsx
const excludeAxes = useExcludeAxes();
const excluded = useMemo(() => applyExcludeFilter(rows, excludeAxes), [rows, excludeAxes]);
...
const filtered = useMemo(() => excluded.rows.filter(...), [excluded.rows, query, sector]);
...
{excluded.hidden > 0 ? (
  <span data-testid="fundamental-hidden-count" title={excludeAxes.map((a) => EXCLUDE_LABEL[a]).join(' · ')} className="num t-9 text-warn">
    {fmtInt(excluded.hidden)} حذف‌شده
  </span>
) : null}
```
The count label uses `filtered.length` از `rows.length` (or `excluded.rows.length`); keep the total as `rows.length` and add the hidden chip.

- [ ] **Step 4: اجرا و سبز**

Run: `cd frontend-v2 && npx vitest run src/__tests__/fundamental-exclusion.spec.tsx src/__tests__/fundamental-page.spec.tsx`
Expected: PASS.

- [ ] **Step 5: commit**

```bash
git add frontend-v2/src/features/fundamental/lib/exclusionFilter.ts frontend-v2/src/features/fundamental/api/useScreenerCore.ts frontend-v2/src/features/fundamental/ui/FundamentalScreenTable.tsx frontend-v2/src/__tests__/fundamental-exclusion.spec.tsx
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(fundamental): فیلتر حذف بر اساس شاخص"
```

---

### Task 6: مسیر جدول و پاک‌سازی پراکسی

**Files:**
- Modify: `frontend-v2/vite.config.ts`
- Test: build/typecheck + یک بررسی زنده

- [ ] **Step 1: حذف `/api/screener` از `goProxy`**

```ts
const goProxy: Record<string, { target: string; changeOrigin: boolean }> = backendGo ? {
  '/api/fundamental': { target: backendGo, changeOrigin: false },
  // جدول غربالگری در S4b از پایتون می‌آید تا کلید کش آستانه‌ها معتبر بماند؛
  // S4c با materializer Go برمی‌گردد.
  '/api/market': { target: backendGo, changeOrigin: false },
  '/api/sync/codal': { target: backendGo, changeOrigin: false },
} : {};
```

- [ ] **Step 2: بررسی**

Run: `cd frontend-v2 && npm run typecheck && npm run build`
Expected: PASS.

- [ ] **Step 3: commit**

```bash
git add frontend-v2/vite.config.ts
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "fix(fundamental): جدول S4b از کش معتبر پایتون می‌خواند"
```

---

### Task 7: پذیرش زنده و شواهد

**Files:**
- Create evidence under `_audit/rebuild/S4b/` (screenshots/JSON; untracked).

- [ ] **Step 1: typecheck و کل تست‌ها**

Run: `cd frontend-v2 && npm run typecheck && npm test`
Expected: PASS.

- [ ] **Step 2: سرورهای آزمون**

- پایتون (دادهٔ جدا، بدون حلقهٔ شبکه): از ریشهٔ ریپو
  `BORS_WORK_DIR=D:/BorsTerminal-tmp/4axes-data BORS_NO_FETCH_LOOPS=1 python -m uvicorn app:app --host 127.0.0.1 --port 8110`.
- Go (همان پوشهٔ داده، خواندنی): `cd backend-go && go run ./cmd/borsd --db-dir D:/BorsTerminal-tmp/4axes-data --port 8103 --no-loops`.
- v2: `BORS_BACKEND=http://127.0.0.1:8110 BORS_BACKEND_GO=http://127.0.0.1:8103 BORS_VITE_PORT=5181 npm run dev`.
- اگر پورت‌ها اشغال‌اند، فقط پورت را عوض کن و همان env را به v2 بده؛ پوشهٔ داده را عوض نکن.

- [ ] **Step 3: اسکرین‌شات‌ها**

- `/fundamental` در ۱۳۶۶×۷۶۸ و ۱۹۲۰×۱۰۸۰.
- دراور باز، تغییر `growth_min`، ذخیره.
- نمای هلدینگ (ویسا) و بانک (وبملت) و نماد عادی.
- بدون خطای کنسول؛ ذخیره در `_audit/rebuild/S4b/`.

- [ ] **Step 4: آزمون سازگاری جدول/کارت**

```bash
# پیکربندی کامل را بخوان، فقط growth_min را عوض کن و کامل برگردان
python - <<'PY'
import json, urllib.request
base = 'http://127.0.0.1:8110'
cfg = json.load(urllib.request.urlopen(base + '/api/fts/config'))['config']
cfg['growth_min'] = 60
req = urllib.request.Request(base + '/api/fts/config',
                             data=json.dumps(cfg).encode('utf-8'),
                             headers={'Content-Type': 'application/json'},
                             method='POST')
print('save:', json.load(urllib.request.urlopen(req)).get('status'))
PY
curl -s "http://127.0.0.1:8110/api/screener" -o /tmp/screener.json
curl -s "http://127.0.0.1:8103/api/fundamental/%D9%81%D9%88%D9%84%D8%A7%D8%AF" -o /tmp/card.json
python - <<'PY'
import json
s = json.load(open('/tmp/screener.json'))
c = json.load(open('/tmp/card.json'))
print('screener as_of', s.get('as_of'), 'rows', s.get('count'))
print('card', c.get('symbol'), 'score', c.get('score'),
      'growth_min', (c.get('thresholds') or {}).get('growth_min'))
PY
```
Expected: `save: success`؛ جدول و کارت هر دو آستانه/امتیاز سازگار؛ اگر Go کارت را با آستانهٔ قدیم داد (مثلاً `growth_min` هنوز ۴۰)، آزمون شکست است و نباید موفق گزارش شود.

- [ ] **Step 5: commit شواهد متنی (اختیاری) و گزارش**

گزارش کوتاه با اعداد و مسیر اسکرین‌شات‌ها؛ بدون push.

---

### Task 8: بستن و بازگشت به تکنیکال

- [ ] **Step 1: `git status` تمیز (به‌جز فایل‌های محافظت‌شده)**

- [ ] **Step 2: گزارش نهایی:** چه ساخته شد، چه سنجیده شد، چه باز ماند (S4c).
- [ ] **Step 3: شروع فاز بعدی: تکنیکال، بعد بازار.**
