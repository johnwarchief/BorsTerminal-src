# میزکارِ نماد: سایدبارِ چپ و داکِ پایین — نقشهٔ پیاده‌سازی

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** صفحهٔ بازار سه ناحیهٔ ثابت بگیرد — سایدبارِ چپِ «یک‌نگاهِ نماد»، میزکارِ دوپنلی (تابلو + دیده‌بان)، و داکِ پایینِ چارت + پنج کارتِ بنیادی — با مرزهای کشیدنیِ ماندگار و حذفِ کاشیِ نماد.

**Architecture:** اندازه‌ها و وضعیتِ باز/بسته در همان store میزکار (`bors-workspace-v1`) ذخیره می‌شوند و نسخه به ۲ می‌رود. یک `LayoutResizer` عمومی سه مرز (سایدبار، داک، چارت) را می‌گرداند. سایدبار و داک هر دو از ردیفِ فعالِ تابلو تغذیه می‌شوند؛ هیچ محاسبهٔ دومی در رابط ساخته نمی‌شود: MA از `/api/ma`، احکامِ فیلتر از `tapeFilterVerdict`، پنج محور از `/api/fundamental`.

**Tech Stack:** React 18.3، TypeScript 5.9، Vite 5.4، Tailwind 4، Zustand 5، TanStack Query 5، Zod 4، klinecharts 10، Vitest 3 + Testing Library.

**Spec:** `docs/superpowers/specs/2026-10-28-symbol-dossier-design.md` (کامیت `6365cb9b`)

## Global Constraints

- همهٔ کارها در `frontend-v2/`؛ شاخه `mission/4-axes-2026-10-10` و هیچ Push به `main`.
- `fetch` بیرون از `frontend-v2/src/shared/api/http.ts` ممنوع؛ هر دو هوکِ تازه از `getJson` می‌خوانند.
- ایمپورت‌ها فقط با الیاس‌های `@app`, `@shared`, `@features`.
- هیچ عددِ غایب به صفر تبدیل نمی‌شود؛ `—` با دلیل در `title`.
- هیچ آستانه یا برچسبِ تازه‌ای اختراع نمی‌شود: چیپ‌ها از `tapeFilterVerdict`/`tapeFilterState`، محورها از `passes`، MA از بک‌اند.
- هیچ درخواستِ شبکه‌ای برای چیپ‌ها و آمار زده نمی‌شود؛ `/api/ma` و `/api/fundamental` فقط وقتی ردیفِ تابلو هست.
- ارقامِ نمایشی با `faNum`/`toFaDigits`؛ کلاسِ فونت فقط `t-*` (کلاسِ px ممنوع)؛ متنِ رابط فارسی و RTL.
- چارت فقط یک نمونه در هر لحظه: داک در حالتِ پهن، چارتِ درونِ سایدبار در حالتِ باریک؛ هرگز هم‌زمان.
- پس از هر تسک: `npx vitest run` سبز و `npx tsc -b` صفر خطا.
- کامیتِ فارسی با heredoc و بدونِ backtick؛ فقط فایل‌های همان تسک `git add` می‌شوند.
- `numpy==2.0.2`، `fts_terminal.spec` و بک‌اند دست نمی‌خورند؛ هیچ فایلِ `api/*.py` تازه‌ای ساخته نمی‌شود.
- PASS بصری اعلام نمی‌شود؛ اسکرین‌شات و اعداد به مالک داده می‌شود.

---

## ساختارِ فایل‌ها

| فایل | مسئولیت |
|---|---|
| `frontend-v2/src/shared/workspace/LayoutResizer.tsx` | مرزِ کشیدنیِ عمومی با دابل‌کلیک/Enter و کلید |
| `frontend-v2/src/shared/workspace/sizes.ts` | پیش‌فرض و حدِ `sideWidth`/`dockHeight`/`chartShare` |
| `frontend-v2/src/shared/workspace/store.ts` | کلیدهای اندازه و باز/بسته + مهاجرتِ نسخه ۲ |
| `frontend-v2/src/shared/workspace/types.ts` | `TilePanel` فقط `board|watch` و چیدمانِ پیش‌فرضِ دوپنلی |
| `frontend-v2/src/shared/workspace/TileFrame.tsx` | منوی «افزودنِ دیده‌بان»؛ حذفِ بجِ پیرو |
| `frontend-v2/src/shared/workspace/WorkspaceShell.tsx` | رندرِ درخت و `canAddWatch` |
| `frontend-v2/src/shared/workspace/shortcuts.ts` | `Alt+۱ و ۲` |
| `frontend-v2/src/features/market/api/useMa.ts` | قراردادِ `/api/ma` + خلاصهٔ تکنیکالِ سه‌حالته |
| `frontend-v2/src/features/market/components/TapeFilterChips.tsx` | هفت چیپِ داوریِ canonical |
| `frontend-v2/src/features/market/components/OrderBookFive.tsx` | بدونِ تغییر، مصرف در سایدبار |
| `frontend-v2/src/features/market/components/TapeHistoryPanel.tsx` | بدونِ تغییر، مصرف در سایدبار |
| `frontend-v2/src/features/fundamental/ui/FundamentalCards.tsx` | پنج کارتِ فشردهٔ ردیفی + `fundamentalFacts` |
| `frontend-v2/src/features/fundamental/ui/FundamentalSummary.tsx` | خطِ «X از ۵ محور قبول» |
| `frontend-v2/src/app/shell/SymbolGlance.tsx` | آمارِ کلیدی و نوارِ فشارِ خرید/فروش |
| `frontend-v2/src/app/shell/SymbolSidebar.tsx` | ستونِ چپ (و `variant="narrow"`)، ریلِ جمع‌شده، کلیدهای داک |
| `frontend-v2/src/app/shell/BottomDock.tsx` | چارت + پنج کارت، مرزِ داخلی، جمع‌شدن |
| `frontend-v2/src/features/market/routes/MarketPage.tsx` | چیدمانِ سه‌ناحیه‌ای + حالتِ باریک |
| `frontend-v2/src/features/market/panels/SymbolPanel.tsx` | **حذف** |
| `_audit/live-board-v2-20261028/dossier-check.mjs` | سنجشِ زندهٔ ناحیه‌های تازه |

> یادداشتِ انحراف از سند: سند برای چیپ‌ها `features/market/ui/TapeFilterChips.tsx` نوشته است؛ پوشهٔ `ui/` در `features/market` وجود ندارد و اجزای این فیچر در `components/` نشسته‌اند. همان الگوی موجود رعایت می‌شود.

---

## Task 1: مرزِ کشیدنیِ عمومی

**Files:**
- Create: `frontend-v2/src/shared/workspace/LayoutResizer.tsx`
- Test: `frontend-v2/src/__tests__/layout-resizer.spec.tsx`

**Interfaces:**
- Produces:
  - `LayoutResizerProps { orientation, value, min, max, step, defaultValue, label, testId, increaseKey, decreaseKey, fromPointer, onChange, measure? }`
  - `ResizeRect { left, top, width, height }`
  - `LayoutResizer(props)` — `role="separator"`، کشیدن با ماوس، دابل‌کلیک/Enter = پیش‌فرض، کلید = ±step

- [ ] **Step 1: Write the failing test**

```tsx
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { LayoutResizer } from '@shared/workspace/LayoutResizer';

const rect = { left: 0, top: 0, width: 1000, height: 600 };

function mount(patch: Partial<Parameters<typeof LayoutResizer>[0]> = {}) {
  const onChange = vi.fn();
  render(
    <LayoutResizer
      orientation="vertical"
      value={320}
      min={260}
      max={420}
      step={8}
      defaultValue={320}
      label="عرض سایدبار"
      testId="resize-test"
      increaseKey="ArrowRight"
      decreaseKey="ArrowLeft"
      fromPointer={(box, x) => x - box.left}
      measure={() => rect}
      onChange={onChange}
      {...patch}
    />,
  );
  return onChange;
}

afterEach(cleanup);

describe('LayoutResizer', () => {
  it('exposes separator semantics', () => {
    mount();
    const separator = screen.getByTestId('resize-test');
    expect(separator.getAttribute('role')).toBe('separator');
    expect(separator.getAttribute('aria-orientation')).toBe('vertical');
    expect(separator.getAttribute('aria-valuenow')).toBe('320');
    expect(separator.getAttribute('aria-valuemin')).toBe('260');
    expect(separator.getAttribute('aria-valuemax')).toBe('420');
  });

  it('reports the pointer-derived value while dragging', () => {
    const onChange = mount();
    const separator = screen.getByTestId('resize-test');
    fireEvent.mouseDown(separator, { clientX: 320, clientY: 100 });
    fireEvent.mouseMove(window, { clientX: 372, clientY: 100 });
    expect(onChange).toHaveBeenLastCalledWith(372);
  });

  it('clamps to the declared range', () => {
    const onChange = mount();
    const separator = screen.getByTestId('resize-test');
    fireEvent.mouseDown(separator, { clientX: 320 });
    fireEvent.mouseMove(window, { clientX: 900 });
    expect(onChange).toHaveBeenLastCalledWith(420);
    fireEvent.mouseMove(window, { clientX: 10 });
    expect(onChange).toHaveBeenLastCalledWith(260);
  });

  it('does not resize before a mouse down', () => {
    const onChange = mount();
    fireEvent.mouseMove(window, { clientX: 400 });
    expect(onChange).not.toHaveBeenCalled();
  });

  it('moves by keyboard and resets on double click and Enter', () => {
    const onChange = mount({ value: 340 });
    const separator = screen.getByTestId('resize-test');
    fireEvent.keyDown(separator, { key: 'ArrowRight' });
    expect(onChange).toHaveBeenLastCalledWith(348);
    fireEvent.keyDown(separator, { key: 'ArrowLeft' });
    expect(onChange).toHaveBeenLastCalledWith(332);
    fireEvent.doubleClick(separator);
    expect(onChange).toHaveBeenLastCalledWith(320);
    fireEvent.keyDown(separator, { key: 'Enter' });
    expect(onChange).toHaveBeenLastCalledWith(320);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd frontend-v2
npx vitest run src/__tests__/layout-resizer.spec.tsx
```

Expected: FAIL — `Failed to resolve import "@shared/workspace/LayoutResizer"`.

- [ ] **Step 3: Write the component**

```tsx
import { useEffect, useRef, useState } from 'react';
import clsx from 'clsx';

export interface ResizeRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface LayoutResizerProps {
  orientation: 'vertical' | 'horizontal';
  value: number;
  min: number;
  max: number;
  step: number;
  defaultValue: number;
  label: string;
  testId: string;
  increaseKey: 'ArrowLeft' | 'ArrowRight' | 'ArrowUp' | 'ArrowDown';
  decreaseKey: 'ArrowLeft' | 'ArrowRight' | 'ArrowUp' | 'ArrowDown';
  fromPointer: (rect: ResizeRect, clientX: number, clientY: number) => number;
  onChange: (value: number) => void;
  measure?: () => ResizeRect | null;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function LayoutResizer(props: LayoutResizerProps) {
  const {
    orientation, value, min, max, step, defaultValue, label, testId,
    increaseKey, decreaseKey, fromPointer, onChange, measure,
  } = props;
  const host = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    if (!dragging) return;
    const move = (event: MouseEvent) => {
      const rect = measure
        ? measure()
        : (host.current?.parentElement?.getBoundingClientRect() ?? null);
      if (!rect) return;
      onChange(clamp(fromPointer(rect, event.clientX, event.clientY), min, max));
    };
    const stop = () => setDragging(false);
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', stop);
    return () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', stop);
    };
  }, [dragging, measure, fromPointer, min, max, onChange]);

  return (
    <div
      ref={host}
      role="separator"
      aria-orientation={orientation}
      aria-label={label}
      aria-valuenow={Number(value.toFixed(2))}
      aria-valuemin={min}
      aria-valuemax={max}
      tabIndex={0}
      data-testid={testId}
      className={clsx(
        'group relative z-10 flex-none touch-none bg-line hover:bg-accent focus-visible:bg-accent focus-visible:outline-none',
        orientation === 'vertical' ? 'w-px cursor-col-resize' : 'h-px cursor-row-resize',
      )}
      onDoubleClick={() => onChange(defaultValue)}
      onKeyDown={(event) => {
        if (event.key === 'Enter') {
          event.preventDefault();
          onChange(defaultValue);
          return;
        }
        if (event.key === increaseKey) {
          event.preventDefault();
          onChange(clamp(value + step, min, max));
          return;
        }
        if (event.key === decreaseKey) {
          event.preventDefault();
          onChange(clamp(value - step, min, max));
        }
      }}
      onMouseDown={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
    >
      <span className={clsx(
        'absolute bg-transparent',
        orientation === 'vertical' ? 'inset-y-0 -start-1 -end-1' : 'inset-x-0 -top-1 -bottom-1',
      )} />
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
npx vitest run src/__tests__/layout-resizer.spec.tsx
npx tsc -b
```

Expected: 5/5 PASS، tsc صفر خطا.

- [ ] **Step 5: Commit**

```bash
cd /c/Users/PCMOD/Desktop/BorsTerminal
git add frontend-v2/src/shared/workspace/LayoutResizer.tsx frontend-v2/src/__tests__/layout-resizer.spec.tsx
git commit -m "$(cat <<'EOF'
feat(workspace): مرزِ کشیدنیِ مشترک برای سایدبار و داک
EOF
)"
```

---

## Task 2: قراردادِ MA و خلاصهٔ تکنیکال

**Files:**
- Create: `frontend-v2/src/features/market/api/useMa.ts`
- Test: `frontend-v2/src/__tests__/ma-summary.spec.ts`

**Interfaces:**
- Consumes: `GET /api/ma/{symbol}` → `{status:'ok', symbol, periods, ma:{ma5,ma20,ma50,ma120}, events, bars}` یا `{status:'error', message}`
- Produces:
  - `MaSeries = Partial<Record<'ma5'|'ma20'|'ma50'|'ma120', Array<[string, number|null]> | null>>`
  - `MaPayload`, `useMa(symbol: string | null | undefined)`
  - `technicalSummary(ma: MaSeries, price: number | null): TechnicalSummary`
  - `TechnicalSummary { price, ma20, ma50, slope5Pct, trend }`، `MaLevel { value, date, distancePct }`
  - `TREND_LABEL: Record<'up'|'down'|'neutral', string>`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, expect, it } from 'vitest';
import { technicalSummary, type MaSeries } from '@features/market/api/useMa';

const series = (values: Array<number | null>): Array<[string, number | null]> =>
  values.map((value, index) => [`2026-10-${String(index + 1).padStart(2, '0')}`, value]);

describe('technicalSummary', () => {
  it('calls an uptrend when price sits above a rising MA20', () => {
    const ma: MaSeries = {
      ma20: series([10, 11, 12, 13, 14, 15]),
      ma50: series([9, 9, 9, 9, 9, 9]),
    };
    const out = technicalSummary(ma, 16);
    expect(out.trend).toBe('up');
    expect(out.ma20?.value).toBe(15);
    expect(out.ma20?.date).toBe('2026-10-06');
    expect(out.ma20?.distancePct).toBeCloseTo((1 / 15) * 100, 6);
    expect(out.slope5Pct).toBeCloseTo(50, 6);
  });

  it('calls a downtrend only when both the position and the slope point down', () => {
    const out = technicalSummary({ ma20: series([20, 19, 18, 17, 16, 15]) }, 14);
    expect(out.trend).toBe('down');
    expect(out.slope5Pct).toBeCloseTo(-25, 6);
  });

  it('stays neutral when the position and the slope disagree', () => {
    expect(technicalSummary({ ma20: series([10, 11, 12, 13, 14, 15]) }, 14).trend).toBe('neutral');
    expect(technicalSummary({ ma20: series([20, 19, 18, 17, 16, 15]) }, 16).trend).toBe('neutral');
  });

  it('refuses a trend without six MA20 points or without a price', () => {
    expect(technicalSummary({ ma20: series([10, 11, 12, 13, 14]) }, 16).trend).toBeNull();
    expect(technicalSummary({ ma20: series([10, 11, 12, 13, 14, 15]) }, null).trend).toBeNull();
    expect(technicalSummary({}, 16)).toEqual({
      price: 16, ma20: null, ma50: null, slope5Pct: null, trend: null,
    });
  });

  it('skips null points at the end of a series', () => {
    const out = technicalSummary({
      ma20: [...series([10, 11, 12, 13, 14, 15]), ['2026-10-07', null]],
    }, 15);
    expect(out.ma20?.value).toBe(15);
    expect(out.slope5Pct).toBeCloseTo(50, 6);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
npx vitest run src/__tests__/ma-summary.spec.ts
```

Expected: FAIL — `Failed to resolve import "@features/market/api/useMa"`.

- [ ] **Step 3: Write the hook and the pure summary**

```ts
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { getJson } from '@shared/api/http';

const PointSchema = z.tuple([z.string(), z.number().nullable()]);
const SeriesSchema = z.array(PointSchema);

const OkSchema = z.looseObject({
  status: z.literal('ok'),
  symbol: z.string(),
  periods: z.array(z.number()).nullish(),
  ma: z.looseObject({
    ma5: SeriesSchema.nullish(),
    ma20: SeriesSchema.nullish(),
    ma50: SeriesSchema.nullish(),
    ma120: SeriesSchema.nullish(),
  }),
  bars: z.number().nullish(),
});

const ErrorSchema = z.looseObject({
  status: z.literal('error'),
  message: z.string().nullish(),
});

export const MaSchema = z.union([OkSchema, ErrorSchema]);
export type MaPayload = z.infer<typeof MaSchema>;
export type MaSeries = Partial<Record<'ma5' | 'ma20' | 'ma50' | 'ma120',
  Array<[string, number | null]> | null>>;

export function useMa(symbol: string | null | undefined) {
  return useQuery<MaPayload>({
    queryKey: ['ma', symbol],
    queryFn: ({ signal }) => getJson(`/api/ma/${encodeURIComponent(String(symbol))}`, MaSchema, signal),
    enabled: Boolean(symbol),
    staleTime: 5 * 60_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
  });
}

export interface MaLevel {
  value: number;
  date: string;
  distancePct: number | null;
}

export interface TechnicalSummary {
  price: number | null;
  ma20: MaLevel | null;
  ma50: MaLevel | null;
  slope5Pct: number | null;
  trend: 'up' | 'down' | 'neutral' | null;
}

export const TREND_LABEL = { up: 'صعودی', down: 'نزولی', neutral: 'خنثی' } as const;

function lastFinite(series: MaSeries[keyof MaSeries]): [string, number] | null {
  const points = series ?? [];
  for (let index = points.length - 1; index >= 0; index -= 1) {
    const point = points[index];
    const value = point?.[1];
    if (value != null && Number.isFinite(value)) return [point![0], value];
  }
  return null;
}

function level(series: MaSeries[keyof MaSeries], price: number | null): MaLevel | null {
  const last = lastFinite(series);
  if (!last) return null;
  const [date, value] = last;
  return {
    date,
    value,
    distancePct: price == null || value === 0 ? null : ((price - value) / value) * 100,
  };
}

function slopePct(series: MaSeries[keyof MaSeries], steps: number): number | null {
  const values = (series ?? [])
    .map((point) => point[1])
    .filter((value): value is number => value != null && Number.isFinite(value));
  if (values.length < steps + 1) return null;
  const last = values[values.length - 1]!;
  const first = values[values.length - 1 - steps]!;
  if (first === 0) return null;
  return ((last - first) / first) * 100;
}

export function technicalSummary(ma: MaSeries, price: number | null): TechnicalSummary {
  const ma20 = level(ma.ma20, price);
  const ma50 = level(ma.ma50, price);
  const slope5Pct = slopePct(ma.ma20, 5);
  let trend: TechnicalSummary['trend'] = null;
  if (price != null && ma20 && slope5Pct != null) {
    if (price > ma20.value && slope5Pct > 0) trend = 'up';
    else if (price < ma20.value && slope5Pct < 0) trend = 'down';
    else trend = 'neutral';
  }
  return { price, ma20, ma50, slope5Pct, trend };
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
npx vitest run src/__tests__/ma-summary.spec.ts
npx tsc -b
```

Expected: 5/5 PASS، tsc صفر خطا.

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/src/features/market/api/useMa.ts frontend-v2/src/__tests__/ma-summary.spec.ts
git commit -m "$(cat <<'EOF'
feat(market): قراردادِ MA و خلاصهٔ تکنیکالِ سه‌حالته
EOF
)"
```

---

## Task 3: چیپ‌های فیلترِ تابلو

**Files:**
- Create: `frontend-v2/src/features/market/components/TapeFilterChips.tsx`
- Test: `frontend-v2/src/__tests__/tape-filter-chips.spec.tsx`

**Interfaces:**
- Consumes: `TAPES` از `../lib/tapeFilters`، `tapeFilterVerdict`/`tapeFilterState`/`DEFAULT_TAPE_FILTER_CONFIG` از `../lib/tapeAlgorithms`
- Produces: `TapeFilterChips({ row: MarketRow | null })` — هفت `span`ِ فقط‌نمایشی، `data-on="true|false"`، `data-state="pass|fail|unevaluated"`، `title` با دلیل

- [ ] **Step 1: Write the failing test**

```tsx
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { MarketRow } from '@shared/types/market';
import { TapeFilterChips } from '@features/market/components/TapeFilterChips';

const row = {
  symbol: 'الف', ins_code: '10', is_live: true,
  f_smart: true, f_legal: false, f_susp: null,
} as MarketRow;

afterEach(cleanup);

describe('TapeFilterChips', () => {
  it('renders all seven canonical filters as display-only chips', () => {
    render(<TapeFilterChips row={row} />);
    expect(screen.getAllByTestId(/^symbol-tape-/)).toHaveLength(7);
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('takes pass, fail and unevaluated straight from the canonical verdict', () => {
    render(<TapeFilterChips row={row} />);
    expect(screen.getByTestId('symbol-tape-f_smart').getAttribute('data-on')).toBe('true');
    expect(screen.getByTestId('symbol-tape-f_legal').getAttribute('data-on')).toBe('false');
    expect(screen.getByTestId('symbol-tape-f_susp').getAttribute('data-state')).toBe('unevaluated');
    expect(screen.getByTestId('symbol-tape-f_susp').getAttribute('title')).toContain('سنجش');
  });

  it('renders nothing without a row', () => {
    render(<TapeFilterChips row={null} />);
    expect(screen.queryByTestId('symbol-tapes')).toBeNull();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
npx vitest run src/__tests__/tape-filter-chips.spec.tsx
```

Expected: FAIL — import resolve.

- [ ] **Step 3: Write the component**

```tsx
import clsx from 'clsx';
import type { MarketRow } from '@shared/types/market';
import {
  DEFAULT_TAPE_FILTER_CONFIG, tapeFilterState, tapeFilterVerdict,
} from '../lib/tapeAlgorithms';
import { TAPES } from '../lib/tapeFilters';

const REASON = {
  pass: 'روشن',
  fail: 'زیرِ آستانه یا بی‌داده',
  unevaluated: 'داده برای سنجش نیست',
} as const;

export function TapeFilterChips({ row }: { row: MarketRow | null }) {
  if (!row) return null;
  return (
    <div data-testid="symbol-tapes" aria-label="فیلترهای تابلوی این نماد"
      className="flex flex-wrap gap-1 border-t border-line px-2 py-1">
      {TAPES.map((tape) => {
        const on = tapeFilterVerdict(row, tape.key, DEFAULT_TAPE_FILTER_CONFIG);
        const state = on ? 'pass' : tapeFilterState(row, tape.key, DEFAULT_TAPE_FILTER_CONFIG);
        return (
          <span
            key={tape.key}
            data-testid={`symbol-tape-${tape.key}`}
            data-on={on ? 'true' : 'false'}
            data-state={state}
            title={`${tape.label} — ${REASON[state]}`}
            className={clsx(
              'inline-flex items-center gap-1 rounded-full border px-1.5 t-85',
              on
                ? 'border-accent/60 bg-accent/10 font-bold text-accent'
                : 'border-line text-text-3',
            )}
          >
            <span className={clsx('h-1 w-1 rounded-full', on ? 'bg-accent' : 'bg-text-3/50')} />
            {tape.short}
          </span>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
npx vitest run src/__tests__/tape-filter-chips.spec.tsx
npx tsc -b
```

Expected: 3/3 PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/src/features/market/components/TapeFilterChips.tsx frontend-v2/src/__tests__/tape-filter-chips.spec.tsx
git commit -m "$(cat <<'EOF'
feat(market): چیپ‌های فیلترِ تابلوی نماد
EOF
)"
```

---

## Task 4: آمارِ کلیدی و فشارِ خرید

**Files:**
- Create: `frontend-v2/src/app/shell/SymbolGlance.tsx`
- Test: `frontend-v2/src/__tests__/symbol-glance.spec.tsx`

**Interfaces:**
- Consumes: `changePct`, `tone`, `fmtInt`, `fmtMcap`, `fmtPe`, `fmtShare`, `fmtVolume`, `faNum` از `@shared/lib/fa`
- Produces: `SymbolGlance({ row: MarketRow | null })` با `symbol-price`، `symbol-pct`، `symbol-pressure`، `pressure-retail`، `pressure-legal`، شش `symbol-stat-{value,volume,trades,pe,mcap,range}`

- [ ] **Step 1: Write the failing test**

```tsx
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { MarketRow } from '@shared/types/market';
import { SymbolGlance } from '@app/shell/SymbolGlance';

afterEach(cleanup);

describe('SymbolGlance', () => {
  it('never turns a missing number into zero', () => {
    render(<SymbolGlance row={{ symbol: 'الف', ins_code: '10' } as MarketRow} />);
    expect(screen.getByTestId('symbol-price').textContent).toBe('—');
    expect(screen.getByTestId('symbol-stat-pe').textContent).toContain('—');
    expect(screen.getByTestId('symbol-stat-range').textContent).toContain('—');
    expect(screen.queryByTestId('symbol-pressure')).toBeNull();
  });

  it('shows a buy-pressure bar only for the percentages that exist', () => {
    const row = {
      symbol: 'الف', ins_code: '10', p_last: 112, p_closing: 110, percent_change: 1.8,
      retail_buy_pct: 62.4, legal_buy_pct: null,
    } as MarketRow;
    render(<SymbolGlance row={row} />);
    expect(screen.getByTestId('pressure-retail').textContent).toContain('۶۲٫۴');
    expect(screen.queryByTestId('pressure-legal')).toBeNull();
    expect(screen.getByTestId('symbol-pct').textContent).toContain('۱٫۸');
  });

  it('keeps the six key stats in one compact grid', () => {
    const row = {
      symbol: 'الف', ins_code: '10', p_last: 1030, p_closing: 1000, percent_change: 2,
      q_tot_cap: 4_000_000, q_tot_tran: 4000, z_tot_tran: 100,
      pe: 7.4, mcap: 1.2e12, p_min: 990, p_max: 1040,
    } as MarketRow;
    render(<SymbolGlance row={row} />);
    expect(screen.getAllByTestId(/^symbol-stat-/)).toHaveLength(6);
    expect(screen.getByTestId('symbol-stat-trades').textContent).toContain('۱۰۰');
    expect(screen.getByTestId('symbol-stat-pe').textContent).toContain('۷٫۴');
    expect(screen.getByTestId('symbol-stat-range').textContent).toContain('۹۹۰');
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
npx vitest run src/__tests__/symbol-glance.spec.tsx
```

Expected: FAIL — import resolve.

- [ ] **Step 3: Write the component**

```tsx
import clsx from 'clsx';
import {
  changePct, faNum, fmtInt, fmtMcap, fmtPe, fmtShare, fmtVolume, tone,
} from '@shared/lib/fa';
import type { MarketRow } from '@shared/types/market';

const TONE = { up: 'text-up', down: 'text-down', flat: 'text-flat' } as const;

function value(input: number | null | undefined, format: (n: number) => string): string {
  return input == null || !Number.isFinite(input) ? '—' : format(input);
}

interface Stat {
  key: string;
  label: string;
  value: string;
  hint: string;
}

function statsOf(row: MarketRow): Stat[] {
  return [
    { key: 'value', label: 'ارزش معاملات', value: value(row.q_tot_cap, (n) => `${fmtMcap(n)} همت`), hint: 'ارزش معاملات امروز (q_tot_cap) به همت' },
    { key: 'volume', label: 'حجم', value: value(row.q_tot_tran, fmtVolume), hint: 'حجم معاملات امروز (q_tot_tran)' },
    { key: 'trades', label: 'تعداد معاملات', value: value(row.z_tot_tran, fmtInt), hint: 'تعداد دفعات معاملهٔ امروز (z_tot_tran)' },
    { key: 'pe', label: 'P/E', value: value(row.pe, fmtPe), hint: 'نسبت قیمت به سود هر سهم (pe)' },
    { key: 'mcap', label: 'ارزش بازار', value: value(row.mcap, (n) => `${fmtMcap(n)} همت`), hint: 'ارزش بازار (mcap) به همت' },
    {
      key: 'range',
      label: 'کف/سقف امروز',
      value: row.p_min == null && row.p_max == null
        ? '—'
        : `${value(row.p_min, fmtInt)} / ${value(row.p_max, fmtInt)}`,
      hint: 'کمترین و بیشترین قیمت امروز (p_min / p_max)',
    },
  ];
}

function pressureOf(row: MarketRow): Array<{ key: 'retail' | 'legal'; label: string; buy: number }> {
  const out: Array<{ key: 'retail' | 'legal'; label: string; buy: number }> = [];
  if (row.retail_buy_pct != null && Number.isFinite(row.retail_buy_pct)) {
    out.push({ key: 'retail', label: 'حقیقی', buy: row.retail_buy_pct });
  }
  if (row.legal_buy_pct != null && Number.isFinite(row.legal_buy_pct)) {
    out.push({ key: 'legal', label: 'حقوقی', buy: row.legal_buy_pct });
  }
  return out;
}

export function SymbolGlance({ row }: { row: MarketRow | null }) {
  if (!row) return null;
  const price = row.p_last ?? row.p_closing ?? null;
  const pct = changePct(row.percent_change, row.price_change, row.price_yesterday);
  const pressure = pressureOf(row);

  return (
    <div data-testid="symbol-glance" className="flex flex-col gap-1">
      <div className="flex items-baseline gap-2 px-2 pt-1">
        <b data-testid="symbol-price" className="num t-125 font-extrabold text-text">{value(price, fmtInt)}</b>
        <span data-testid="symbol-pct"
          className={clsx('num t-95', pct == null ? 'text-text-3' : TONE[tone(pct)])}>
          {pct == null ? '—' : `${pct > 0 ? '▲' : pct < 0 ? '▼' : '•'} ${faNum(Math.abs(pct), 1)}٪`}
        </span>
        <span className="ms-auto t-85 text-text-3" title="این ناحیه همیشه ردیفِ فعالِ تابلو را نشان می‌دهد">
          پیروِ تابلو
        </span>
      </div>

      {pressure.length > 0 ? (
        <div data-testid="symbol-pressure" className="flex flex-col gap-1 px-2 py-0.5">
          {pressure.map((item) => {
            const buy = Math.min(100, Math.max(0, item.buy));
            return (
              <div key={item.key} data-testid={`pressure-${item.key}`}
                title={`سهمِ خریدِ ${item.label} از کلِ معاملاتِ ${item.label}`}>
                <div className="flex justify-between t-85 text-text-3">
                  <span>{item.label}</span>
                  <span className="num">{fmtShare(buy)} خرید · {fmtShare(100 - buy)} فروش</span>
                </div>
                <div className="flex h-1.5 overflow-hidden rounded-full bg-panel-3">
                  <span className="bg-up" style={{ width: `${buy}%` }} />
                  <span className="bg-down" style={{ width: `${100 - buy}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-x-3 gap-y-[2px] px-2 t-9">
        {statsOf(row).map((stat) => (
          <span key={stat.key} data-testid={`symbol-stat-${stat.key}`} title={stat.hint}
            className="flex justify-between gap-1">
            <span className="truncate text-text-3">{stat.label}</span>
            <b className="num shrink-0 text-text-2">{stat.value}</b>
          </span>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
npx vitest run src/__tests__/symbol-glance.spec.tsx
npx tsc -b
```

Expected: 3/3 PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/src/app/shell/SymbolGlance.tsx frontend-v2/src/__tests__/symbol-glance.spec.tsx
git commit -m "$(cat <<'EOF'
feat(symbol): بلوکِ آمارِ کلیدی و فشارِ خرید
EOF
)"
```

---

## Task 5: پنج کارتِ ردیفی و خلاصهٔ بنیادی

**Files:**
- Modify: `frontend-v2/src/features/fundamental/ui/FundamentalCards.tsx` (کل فایل جایگزین می‌شود)
- Create: `frontend-v2/src/features/fundamental/ui/FundamentalSummary.tsx`
- Test: `frontend-v2/src/__tests__/fundamental-summary.spec.tsx`

**Interfaces:**
- Consumes: `useFtsCard` و `FtsCard` از `../api/useFtsCard`
- Produces:
  - `fundamentalFacts(card: FtsCard): FundamentalFact[]` (همان منطقِ پنج محور؛ `pass == null` ⇒ `quality: 'na'`)
  - `QUALITY_WORD: Record<'ideal'|'ok'|'below'|'na', string>`
  - `FundamentalCards({ symbol })` — ردیفِ پنج کارتِ فشرده با `fundamental-card-{key}`
  - `FundamentalSummary({ symbol, expanded?, onToggle? })` — `symbol-fund-summary`، `fund-summary-count`، `fund-summary-weakest`، `symbol-fund-unavailable`

- [ ] **Step 1: Write the failing test**

```tsx
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { FtsCard } from '@features/fundamental/api/useFtsCard';
import { useFtsCard } from '@features/fundamental/api/useFtsCard';
import { FundamentalCards } from '@features/fundamental/ui/FundamentalCards';
import { FundamentalSummary } from '@features/fundamental/ui/FundamentalSummary';

vi.mock('@features/fundamental/api/useFtsCard', () => ({ useFtsCard: vi.fn() }));

const card = {
  status: 'success',
  symbol: 'فولاد',
  sector: 'فلزات اساسی',
  passes: {
    '1_growth': true,
    '2_eps_trend': true,
    '3_gross_margin': null,
    '4_sales_to_mcap': false,
    '5_industry': true,
  },
  indicators: {
    '1': { monetary: { monetary_pct: 24, threshold: 10, data_gap: false } },
    '2': { eps_series: [10, 12, 14], years_available: 3, years_required: 3 },
    '3': { margin_pct: 18, threshold: 15, band: 'ok', optimal: false },
    '4': { sales_to_mcap: 0.42, sales_threshold: 0.3, available: true, data_gap: false },
    '5': { label: 'رونق', sector: 'فلزات اساسی' },
  },
} as unknown as FtsCard;

beforeEach(() => {
  vi.mocked(useFtsCard).mockReturnValue({
    data: card, isLoading: false, isError: false, error: null,
  } as never);
});

afterEach(cleanup);

describe('FundamentalSummary', () => {
  it('counts pass, reject and abstention without inventing a verdict', () => {
    render(<FundamentalSummary symbol="فولاد" expanded onToggle={() => undefined} />);
    const summary = screen.getByTestId('symbol-fund-summary');
    expect(screen.getByTestId('fund-summary-count').textContent).toContain('۳ از ۵');
    expect(summary.textContent).toContain('۱ بینظر');
    expect(summary.textContent).toContain('۱ رد');
    expect(screen.getByTestId('fund-summary-weakest').textContent).toContain('۴. پتانسیل سود');
    expect(summary.getAttribute('aria-expanded')).toBe('true');
  });

  it('renders a static block when no dock toggle is supplied', () => {
    render(<FundamentalSummary symbol="فولاد" />);
    expect(screen.queryByRole('button')).toBeNull();
    expect(screen.getByTestId('symbol-fund-summary')).toBeTruthy();
  });

  it('says the fundamental data is unavailable without breaking the sidebar', () => {
    vi.mocked(useFtsCard).mockReturnValue({
      data: undefined, isLoading: false, isError: true, error: new Error('x'),
    } as never);
    render(<FundamentalSummary symbol="فولاد" />);
    expect(screen.getByTestId('symbol-fund-unavailable').textContent).toContain('در دسترس نیست');
  });
});

describe('FundamentalCards', () => {
  it('shows five compact cards and keeps a null verdict as بینظر', () => {
    render(<FundamentalCards symbol="فولاد" />);
    expect(screen.getAllByTestId(/^fundamental-card-/)).toHaveLength(5);
    const axis3 = screen.getByTestId('fundamental-card-3_gross_margin');
    expect(axis3.textContent).toContain('بینظر');
    expect(axis3.textContent).not.toContain('رد');
    expect(axis3.getAttribute('title')).toContain('۳. حاشیه سود ناخالص');
  });

  it('keeps the chart and board untouched when the request fails', () => {
    vi.mocked(useFtsCard).mockReturnValue({
      data: undefined, isLoading: false, isError: true, error: new Error('x'),
    } as never);
    render(<FundamentalCards symbol="فولاد" />);
    expect(screen.getByTestId('fundamental-error').textContent).toContain('چارت و تابلو');
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
npx vitest run src/__tests__/fundamental-summary.spec.tsx
```

Expected: FAIL — `fundamentalFacts`/`FundamentalSummary` وجود ندارند.

- [ ] **Step 3: Rewrite `FundamentalCards.tsx`**

```tsx
import clsx from 'clsx';
import { faNum, fmtInt, fmtPct, toFaDigits } from '@shared/lib/fa';
import { useFtsCard, type FtsCard } from '../api/useFtsCard';

type Quality = 'ideal' | 'ok' | 'below' | 'na';

export const QUALITY_WORD: Record<Quality, string> = {
  ideal: 'ایده‌آل',
  ok: 'قبول',
  below: 'رد',
  na: 'بینظر',
};

const CHIP: Record<Quality, { word: string; tone: string }> = {
  ideal: { word: QUALITY_WORD.ideal, tone: 'text-cyan-300' },
  ok: { word: QUALITY_WORD.ok, tone: 'text-up' },
  below: { word: QUALITY_WORD.below, tone: 'text-down' },
  na: { word: QUALITY_WORD.na, tone: 'text-text-3' },
};

export interface FundamentalFact {
  key: string;
  label: string;
  value: string;
  quality: Quality;
  note: string;
}

function qualityOf(pass: boolean | null | undefined, ideal = false): Quality {
  if (pass == null) return 'na';
  if (pass && ideal) return 'ideal';
  return pass ? 'ok' : 'below';
}

function signedPct(input: number | null | undefined): string {
  if (input == null || !Number.isFinite(input)) return '—';
  return `${input >= 0 ? '+' : '−'}${faNum(Math.abs(input), 1)}٪`;
}

function ratioPct(input: number | null | undefined): string {
  if (input == null || !Number.isFinite(input)) return '—';
  return `${toFaDigits((input * 100).toFixed(1))}٪`;
}

export function fundamentalFacts(card: FtsCard): FundamentalFact[] {
  const passes = card.passes ?? {};
  const indicators = card.indicators ?? {};
  const out: FundamentalFact[] = [];

  const one = indicators['1'];
  const monetary = one?.monetary;
  const pass1 = monetary?.data_gap ? null : passes['1_growth'];
  out.push({
    key: '1_growth',
    label: '۱. رشد فروش کدال',
    value: signedPct(monetary?.monetary_pct),
    quality: qualityOf(pass1),
    note: pass1 == null
      ? (monetary?.reason || 'رشد ریالی سنجیده نشد')
      : monetary?.threshold == null
        ? (one?.volume?.applicable === false ? 'رشد تولیدی بر این شرکت اعمال نمی‌شود' : 'رشد ریالی فروش')
        : `کفِ ${faNum(monetary.threshold)}٪`,
  });

  const two = indicators['2'];
  const series = two?.eps_series ?? null;
  const lastEps = series?.length ? series[series.length - 1] : null;
  const pass2 = passes['2_eps_trend'];
  out.push({
    key: '2_eps_trend',
    label: '۲. سودآوری ۳ ساله',
    value: lastEps == null ? '—' : fmtInt(lastEps),
    quality: qualityOf(pass2),
    note: pass2 == null
      ? 'سابقهٔ سه‌سالۀ کامل نیست'
      : two?.years_available == null
        ? 'سه سالِ متوالیِ حسابرسی‌شده'
        : `${faNum(two.years_available)}${two.years_required == null ? '' : `/${faNum(two.years_required)}`} سال`,
  });

  const three = indicators['3'];
  const pass3 = passes['3_gross_margin'];
  const ideal3 = three?.band === 'ideal' || three?.optimal === true;
  out.push({
    key: '3_gross_margin',
    label: '۳. حاشیه سود ناخالص',
    value: three?.margin_pct == null ? '—' : fmtPct(three.margin_pct),
    quality: qualityOf(pass3, ideal3),
    note: pass3 == null
      ? 'حاشیۀ ناخالص ثبت نشده'
      : three?.threshold == null
        ? 'حاشیهٔ ناخالص ÷ درآمد عملیاتی'
        : `≥ ${toFaDigits(three.threshold)}٪`,
  });

  const four = indicators['4'];
  const pass4 = four?.available === false || four?.data_gap ? null : passes['4_sales_to_mcap'];
  out.push({
    key: '4_sales_to_mcap',
    label: '۴. پتانسیل سود تا آخر سال',
    value: ratioPct(four?.sales_to_mcap),
    quality: qualityOf(pass4),
    note: pass4 == null
      ? (four?.gap_cause || four?.reason || 'فروش سالانه یا ارزش بازار نداشت')
      : four?.sales_threshold == null
        ? 'فروش ÷ ارزش بازار'
        : `≥ ${ratioPct(four.sales_threshold)}`,
  });

  const five = indicators['5'];
  const pass5 = passes['5_industry'];
  const regime = five?.label ?? five?.regime_label ?? null;
  out.push({
    key: '5_industry',
    label: '۵. رژیم صنعت',
    value: regime == null || regime === '' ? '—' : String(regime),
    quality: qualityOf(pass5),
    note: pass5 == null
      ? 'صنعت یا نرخ‌گذاری معلوم نیست'
      : (five?.sector ?? card.sector ?? 'رژیم قیمت‌گذاری صنعت'),
  });

  return out;
}

export function FundamentalCards({ symbol }: { symbol: string }) {
  const query = useFtsCard(symbol);

  if (query.isLoading) {
    return <p data-testid="fundamental-loading" className="p-2 t-95 text-text-3">پنج شاخصِ بنیادی در حال خواندن…</p>;
  }
  if (query.isError || !query.data) {
    return (
      <p data-testid="fundamental-error" className="p-2 t-95 leading-relaxed text-text-3">
        بنیادیِ این نماد در دسترس نیست؛ چارت و تابلو دست‌نخورده‌اند.
      </p>
    );
  }

  return (
    <div data-testid="fundamental-cards" className="flex min-h-0 gap-1 overflow-x-auto p-1">
      {fundamentalFacts(query.data).map((fact) => {
        const chip = CHIP[fact.quality];
        return (
          <div
            key={fact.key}
            data-testid={`fundamental-card-${fact.key}`}
            title={`${fact.label} — ${fact.note}`}
            className="flex min-h-0 min-w-[84px] flex-1 flex-col justify-between gap-0.5 rounded-[var(--radius-sm)] border border-line bg-panel-2 px-1.5 py-1"
          >
            <div className="flex items-center justify-between gap-1">
              <span className="grid h-4 w-4 flex-none place-items-center rounded-full bg-panel-3 t-85 text-text-3">
                {toFaDigits(fact.key.slice(0, 1))}
              </span>
              <span className={clsx('truncate t-85 font-bold', chip.tone)}>{chip.word}</span>
            </div>
            <b className="num truncate t-115 font-extrabold text-text">{fact.value}</b>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Create `FundamentalSummary.tsx`**

```tsx
import type { ReactNode } from 'react';
import { faNum } from '@shared/lib/fa';
import { useFtsCard } from '../api/useFtsCard';
import { fundamentalFacts } from './FundamentalCards';

interface Props {
  symbol: string | null;
  expanded?: boolean;
  onToggle?: () => void;
}

export function FundamentalSummary({ symbol, expanded, onToggle }: Props) {
  const query = useFtsCard(symbol);

  let body: ReactNode;
  if (!symbol) {
    body = <span className="t-95 text-text-3">برای دیدنِ بنیادی، نمادی را از تابلو انتخاب کن.</span>;
  } else if (query.isLoading) {
    body = <span className="t-95 text-text-3">پنج محورِ بنیادی در حال خواندن…</span>;
  } else if (query.isError || !query.data) {
    body = <span data-testid="symbol-fund-unavailable" className="t-95 text-text-3">بنیادیِ این نماد در دسترس نیست.</span>;
  } else {
    const facts = fundamentalFacts(query.data);
    const accepted = facts.filter((fact) => fact.quality === 'ideal' || fact.quality === 'ok').length;
    const rejected = facts.filter((fact) => fact.quality === 'below').length;
    const abstained = facts.filter((fact) => fact.quality === 'na').length;
    const weakest = facts.find((fact) => fact.quality === 'below')
      ?? facts.find((fact) => fact.quality === 'na')
      ?? null;
    body = (
      <>
        <span className="flex flex-wrap items-baseline gap-1">
          <b data-testid="fund-summary-count" className="num t-105 font-extrabold text-text">
            {faNum(accepted)} از ۵ محور قبول
          </b>
          {abstained > 0 ? <span className="t-9 text-text-3">· {faNum(abstained)} بینظر</span> : null}
          {rejected > 0 ? <span className="t-9 text-down">· {faNum(rejected)} رد</span> : null}
        </span>
        <span data-testid="fund-summary-weakest" className="t-9 text-text-3">
          {weakest ? `ضعیف‌ترین: ${weakest.label}` : 'هر پنج محور قبول‌اند.'}
        </span>
      </>
    );
  }

  const className = 'flex w-full flex-col gap-0.5 border-y border-line px-2 py-1 text-start';
  if (!onToggle) {
    return <div data-testid="symbol-fund-summary" className={className}>{body}</div>;
  }
  return (
    <button
      type="button"
      data-testid="symbol-fund-summary"
      aria-expanded={Boolean(expanded)}
      onClick={onToggle}
      className={`${className} hover:bg-panel-2`}
    >
      {body}
      <span className="t-85 text-text-3">
        {expanded ? 'بستنِ کارت‌های بنیادی' : 'باز کردنِ کارت‌های بنیادی'}
      </span>
    </button>
  );
}
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
npx vitest run src/__tests__/fundamental-summary.spec.tsx
npx tsc -b
```

Expected: 5/5 PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend-v2/src/features/fundamental/ui/FundamentalCards.tsx frontend-v2/src/features/fundamental/ui/FundamentalSummary.tsx frontend-v2/src/__tests__/fundamental-summary.spec.tsx
git commit -m "$(cat <<'EOF'
feat(fundamental): خلاصهٔ پنج محور و کارت‌های ردیفی
EOF
)"
```

---

## Task 6: اندازه‌های ماندگار در store

**Files:**
- Create: `frontend-v2/src/shared/workspace/sizes.ts`
- Modify: `frontend-v2/src/shared/workspace/store.ts`
- Test: `frontend-v2/src/__tests__/workspace-store.spec.ts` (مرحلهٔ نخست)

**Interfaces:**
- Produces:
  - `SIDE_WIDTH {min:260,max:420,default:320}`، `DOCK_HEIGHT {min:160,max:360,default:200}`، `CHART_SHARE {min:0.3,max:0.6,default:0.45}`
  - `Workspace` با `fundamentalsOpen`, `sideCollapsed`, `sideWidth`, `dockHeight`, `chartShare`
  - `setFundamentalsOpen`, `setSideCollapsed`, `setSideWidth`, `setDockHeight`, `setChartShare`
  - نسخهٔ ذخیره `۲` و `migrate` عبوری (نرمال‌سازی فقط در `merge`)

- [ ] **Step 1: Write the failing tests (add to `workspace-store.spec.ts`)**

```ts
import { SIDE_WIDTH } from '@shared/workspace/sizes';

// داخل describe:
it('starts with the default sizes and open groups', () => {
  const ws = useWorkspace.getState().workspaces[0];
  expect([ws.sideWidth, ws.dockHeight, ws.chartShare]).toEqual([320, 200, 0.45]);
  expect(ws.fundamentalsOpen).toBe(true);
  expect(ws.sideCollapsed).toBe(false);
});

it('clamps every persisted size', () => {
  useWorkspace.getState().setSideWidth(100);
  expect(useWorkspace.getState().workspaces[0].sideWidth).toBe(SIDE_WIDTH.min);
  useWorkspace.getState().setSideWidth(900);
  expect(useWorkspace.getState().workspaces[0].sideWidth).toBe(SIDE_WIDTH.max);
  useWorkspace.getState().setDockHeight(10);
  expect(useWorkspace.getState().workspaces[0].dockHeight).toBe(160);
  useWorkspace.getState().setChartShare(0.9);
  expect(useWorkspace.getState().workspaces[0].chartShare).toBe(0.6);
  useWorkspace.getState().setFundamentalsOpen(false);
  useWorkspace.getState().setSideCollapsed(true);
  expect(useWorkspace.getState().workspaces[0].fundamentalsOpen).toBe(false);
  expect(useWorkspace.getState().workspaces[0].sideCollapsed).toBe(true);
});

it('fills the new keys for a version-1 payload and rejects an unknown version', () => {
  const ws = sanitizeWorkspace({
    version: 1,
    workspaces: [{ layout: DEFAULT_LAYOUT, slots: DEFAULT_SLOTS }],
  });
  expect(ws?.sideWidth).toBe(320);
  expect(ws?.dockHeight).toBe(200);
  expect(ws?.chartShare).toBe(0.45);
  expect(ws?.fundamentalsOpen).toBe(true);
  expect(ws?.sideCollapsed).toBe(false);
  expect(sanitizeWorkspace({ version: 3, workspaces: [{ layout: DEFAULT_LAYOUT }] })).toBeNull();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
npx vitest run src/__tests__/workspace-store.spec.ts
```

Expected: FAIL — `@shared/workspace/sizes` وجود ندارد و کلیدها `undefined`اند.

- [ ] **Step 3: Create `sizes.ts`**

```ts
export const SIDE_WIDTH = { min: 260, max: 420, default: 320 } as const;
export const DOCK_HEIGHT = { min: 160, max: 360, default: 200 } as const;
export const CHART_SHARE = { min: 0.3, max: 0.6, default: 0.45 } as const;
```

- [ ] **Step 4: Modify `store.ts`**

بالای فایل:

```ts
import { CHART_SHARE, DOCK_HEIGHT, SIDE_WIDTH } from './sizes';
```

`Workspace`:

```ts
export interface Workspace {
  id: string;
  name: string;
  layout: LayoutNode;
  slots: CardId[];
  chartOpen: boolean;
  fundamentalsOpen: boolean;
  sideCollapsed: boolean;
  sideWidth: number;
  dockHeight: number;
  chartShare: number;
  updatedAt: number;
}
```

`WorkspaceStore`:

```ts
interface WorkspaceStore {
  version: 2;
  activeWorkspaceId: string;
  activeSymbol: string | null;
  pinned: Record<string, string | null>;
  workspaces: Workspace[];
  history: LayoutNode[];
  undo: () => void;
  split: (tileId: string, dir: SplitDir, panel: TilePanel) => void;
  close: (tileId: string) => void;
  swap: (tileId: string, dir: MoveDir) => void;
  setRatio: (splitId: string, ratio: number, width: number, height: number) => void;
  setSlots: (slots: CardId[]) => void;
  setActiveSymbol: (key: string | null) => void;
  setChartOpen: (open: boolean) => void;
  setFundamentalsOpen: (open: boolean) => void;
  setSideCollapsed: (collapsed: boolean) => void;
  setSideWidth: (width: number) => void;
  setDockHeight: (height: number) => void;
  setChartShare: (share: number) => void;
  toggleFollow: (tileId: string) => void;
  resetLayout: () => void;
}
```

کمکی‌ها و پیش‌فرض:

```ts
function clampNumber(value: unknown, min: number, max: number, fallback: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(max, Math.max(min, parsed));
}

const DEFAULT_WORKSPACE: Workspace = {
  id: 'ws-tablo', name: 'تابلوخوانی', layout: DEFAULT_LAYOUT,
  slots: DEFAULT_SLOTS, chartOpen: true,
  fundamentalsOpen: true, sideCollapsed: false,
  sideWidth: SIDE_WIDTH.default, dockHeight: DOCK_HEIGHT.default,
  chartShare: CHART_SHARE.default,
  updatedAt: 0,
};
```

`readPinned`:

```ts
function readPinned(value: unknown): Record<string, string | null> {
  const pinned: Record<string, string | null> = {};
  if (value && typeof value === 'object') {
    for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
      if (typeof item === 'string') pinned[key] = item;
    }
  }
  return pinned;
}
```

`sanitizeWorkspace`:

```ts
export function sanitizeWorkspace(persisted: unknown): Workspace | null {
  if (!persisted || typeof persisted !== 'object') return null;
  const persistedVersion = Number((persisted as { version?: unknown }).version ?? 1);
  if (persistedVersion !== 1 && persistedVersion !== 2) return null;
  const raw = persisted as { workspaces?: unknown };
  const list = Array.isArray(raw.workspaces) ? raw.workspaces : [];
  const first = list[0] as Partial<Workspace> | undefined;
  if (!first || !isValidLayout(first.layout)) return null;
  const slots = cleanSlots(first.slots);
  return {
    id: typeof first.id === 'string' ? first.id : 'ws-tablo',
    name: typeof first.name === 'string' ? first.name : 'تابلوخوانی',
    layout: first.layout,
    slots: slots.length >= 3 ? slots : DEFAULT_SLOTS,
    chartOpen: first.chartOpen !== false,
    fundamentalsOpen: first.fundamentalsOpen !== false,
    sideCollapsed: first.sideCollapsed === true,
    sideWidth: clampNumber(first.sideWidth, SIDE_WIDTH.min, SIDE_WIDTH.max, SIDE_WIDTH.default),
    dockHeight: clampNumber(first.dockHeight, DOCK_HEIGHT.min, DOCK_HEIGHT.max, DOCK_HEIGHT.default),
    chartShare: clampNumber(first.chartShare, CHART_SHARE.min, CHART_SHARE.max, CHART_SHARE.default),
    updatedAt: Number(first.updatedAt ?? 0),
  };
}
```

`update` و setterها (کنار `patch` و `setChartOpen`):

```ts
const update = (extra: Partial<Workspace>) => {
  const ws = get().workspaces[0];
  set({ workspaces: [{ ...ws, ...extra, updatedAt: Date.now() }] });
};
```

```ts
version: 2,
```

پیادهٔ فعلیِ `setChartOpen` را با این بلوک جایگزین کن (نه اضافه):

```ts
setChartOpen: (chartOpen) => update({ chartOpen }),
setFundamentalsOpen: (fundamentalsOpen) => update({ fundamentalsOpen }),
setSideCollapsed: (sideCollapsed) => update({ sideCollapsed }),
setSideWidth: (sideWidth) => update({
  sideWidth: clampNumber(sideWidth, SIDE_WIDTH.min, SIDE_WIDTH.max, SIDE_WIDTH.default),
}),
setDockHeight: (dockHeight) => update({
  dockHeight: clampNumber(dockHeight, DOCK_HEIGHT.min, DOCK_HEIGHT.max, DOCK_HEIGHT.default),
}),
setChartShare: (chartShare) => update({
  chartShare: clampNumber(chartShare, CHART_SHARE.min, CHART_SHARE.max, CHART_SHARE.default),
}),
```

`persist`:

```ts
{
  name: 'bors-workspace-v1',
  version: 2,
  // تنها نرمال‌ساز merge() است؛ این فقط پیامِ ناسازگاریِ نسخه را خاموش می‌کند.
  migrate: (persisted) => persisted as never,
  partialize: (state) => ({
    version: state.version,
    activeWorkspaceId: state.activeWorkspaceId,
    activeSymbol: state.activeSymbol,
    pinned: state.pinned,
    workspaces: state.workspaces,
  }),
  merge: (persisted, current) => {
    const raw = (persisted ?? {}) as { activeSymbol?: unknown; pinned?: unknown };
    const activeSymbol = typeof raw.activeSymbol === 'string' ? raw.activeSymbol : null;
    const pinned = readPinned(raw.pinned);
    const ws = sanitizeWorkspace(persisted);
    if (!ws) return { ...current, activeSymbol, pinned };
    return {
      ...current,
      activeWorkspaceId: ws.id,
      workspaces: [ws],
      activeSymbol,
      pinned,
    };
  },
}
```

> این `merge` انتخابِ کاربر را حتی وقتی چیدمان نامعتبر است نگه می‌دارد؛ تبدیلِ چیدمانِ قدیمی در Task 9 با محدودشدنِ `isValidLayout` کامل می‌شود.

- [ ] **Step 5: Run the tests to verify they pass**

```bash
npx vitest run src/__tests__/workspace-store.spec.ts
npx tsc -b
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend-v2/src/shared/workspace/sizes.ts frontend-v2/src/shared/workspace/store.ts frontend-v2/src/__tests__/workspace-store.spec.ts
git commit -m "$(cat <<'EOF'
feat(workspace): اندازه‌های ماندگارِ سایدبار و داک
EOF
)"
```

---

## Task 7: سایدبارِ چپِ نماد

**Files:**
- Create: `frontend-v2/src/app/shell/SymbolSidebar.tsx`
- Test: `frontend-v2/src/__tests__/symbol-sidebar.spec.tsx`
- Note: `BoardPanel`، `WatchPanel` و `OrderBookFive` دست‌نخورده می‌مانند.

**Interfaces:**
- Consumes: `SymbolGlance`، `TapeFilterChips`، `useMa`+`technicalSummary`+`TREND_LABEL`، `FundamentalSummary`، `OrderBookFive`، `TapeHistoryPanel`، `WatchlistButton`، `ChartPanel`
- Produces: `SymbolSidebarProps { row, symbolKey, boardDay, variant?, chartOpen, fundamentalsOpen, collapsed?, onToggleChart, onToggleFundamentals, onToggleCollapsed? }` با:
  - `symbol-sidebar` + `data-variant="wide|narrow"`، `symbol-rail`/`symbol-rail-open` در حالتِ جمع‌شده
  - `symbol-title`, `symbol-not-in-board`, `symbol-collapse`
  - `dock-toggle-chart`, `dock-toggle-fundamental` (فقط wide، با `aria-expanded`)
  - `symbol-chart-toggle` (فقط narrow) و چارتِ ۱۵۰px
  - `symbol-tab-book` / `symbol-tab-history`

- [ ] **Step 1: Write the failing test**

```tsx
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { FtsCard } from '@features/fundamental/api/useFtsCard';
import { useFtsCard } from '@features/fundamental/api/useFtsCard';
import { useMa } from '@features/market/api/useMa';
import type { MarketRow } from '@shared/types/market';
import { SymbolSidebar } from '@app/shell/SymbolSidebar';

vi.mock('@features/market/api/useMa', async (original) => {
  const mod = await original<typeof import('@features/market/api/useMa')>();
  return { ...mod, useMa: vi.fn() };
});
vi.mock('@features/fundamental/api/useFtsCard', () => ({ useFtsCard: vi.fn() }));
vi.mock('@features/chart/ui/ChartPanel', () => ({
  ChartPanel: ({ symbol }: { symbol: string }) => <div data-testid="chart-stub">{symbol}</div>,
}));
vi.mock('@features/market/components/OrderBookFive', () => ({
  OrderBookFive: ({ symbol }: { symbol: string }) => <div data-testid="book-stub">{symbol}</div>,
}));
vi.mock('@features/market/components/TapeHistoryPanel', () => ({
  TapeHistoryPanel: ({ symbol }: { symbol: string }) => <div data-testid="history-stub">{symbol}</div>,
}));
vi.mock('@features/market/components/WatchlistButton', () => ({
  WatchlistButton: () => <button type="button">واچ‌لیست</button>,
}));

const row = {
  symbol: 'الف', ins_code: '10', name: 'شرکت الف',
  p_last: 112, p_closing: 110, percent_change: 1.8,
  q_tot_cap: 6e9, q_tot_tran: 2e6, z_tot_tran: 1200,
  pe: 7.4, mcap: 1.2e12, p_min: 100, p_max: 115,
  retail_buy_pct: 62.4,
  f_smart: true, f_legal: false,
} as MarketRow;

const series = (values: number[]): Array<[string, number | null]> =>
  values.map((value, index) => [`2026-10-0${index + 1}`, value]);

const card = {
  status: 'success', symbol: 'الف',
  passes: { '1_growth': true, '2_eps_trend': true, '3_gross_margin': null, '4_sales_to_mcap': false, '5_industry': true },
  indicators: {
    '1': { monetary: { monetary_pct: 20, threshold: 10, data_gap: false } },
    '2': { eps_series: [10, 12, 14], years_available: 3, years_required: 3 },
    '3': { margin_pct: 18 },
    '4': { sales_to_mcap: 0.4, available: true, data_gap: false },
    '5': { label: 'رونق' },
  },
} as unknown as FtsCard;

beforeEach(() => {
  vi.mocked(useMa).mockReturnValue({
    data: { status: 'ok', symbol: 'الف', ma: { ma20: series([100, 101, 102, 103, 104, 105]), ma50: series([90, 90, 90, 90, 90, 90]) } },
    isLoading: false, isError: false, error: null,
  } as never);
  vi.mocked(useFtsCard).mockReturnValue({
    data: card, isLoading: false, isError: false, error: null,
  } as never);
});

afterEach(cleanup);

function mount(patch: Partial<Parameters<typeof SymbolSidebar>[0]> = {}) {
  return render(
    <SymbolSidebar
      row={row}
      symbolKey="10"
      boardDay={20261028}
      chartOpen
      fundamentalsOpen
      onToggleChart={() => undefined}
      onToggleFundamentals={() => undefined}
      {...patch}
    />,
  );
}

describe('SymbolSidebar', () => {
  it('shows the honest empty state without asking for data', () => {
    mount({ symbolKey: null, row: null });
    expect(screen.getByTestId('symbol-sidebar').textContent).toContain('نمادی');
    expect(vi.mocked(useMa)).not.toHaveBeenCalled();
  });

  it('separates a symbol that is absent from the board from a missing selection', () => {
    mount({ symbolKey: '99', row: null });
    expect(screen.getByTestId('symbol-not-in-board').textContent).toContain('در تابلو نیست');
    expect(vi.mocked(useMa)).not.toHaveBeenCalled();
  });

  it('renders the at-a-glance page: stats, seven chips, technical and fundamental summaries', () => {
    mount();
    expect(screen.getByTestId('symbol-title').textContent).toContain('الف');
    expect(screen.getByTestId('symbol-price').textContent).toContain('۱۱۲');
    expect(screen.getAllByTestId(/^symbol-stat-/)).toHaveLength(6);
    expect(screen.getAllByTestId(/^symbol-tape-/)).toHaveLength(7);
    expect(screen.getByTestId('tech-ma20').textContent).toContain('۱۰۵');
    expect(screen.getByTestId('tech-trend').textContent).toContain('صعودی');
    expect(screen.getByTestId('fund-summary-count').textContent).toContain('۳ از ۵');
    expect(screen.getByTestId('book-stub')).toBeTruthy();
  });

  it('says the technical block is unavailable without hiding the rest', () => {
    vi.mocked(useMa).mockReturnValue({
      data: { status: 'error', message: 'x' }, isLoading: false, isError: false, error: null,
    } as never);
    mount();
    expect(screen.getByTestId('tech-unavailable').textContent).toContain('در دسترس نیست');
    expect(screen.getAllByTestId(/^symbol-tape-/)).toHaveLength(7);
  });

  it('switches between the depth and history tabs', () => {
    mount();
    fireEvent.click(screen.getByTestId('symbol-tab-history'));
    expect(screen.getByTestId('history-stub')).toBeTruthy();
  });

  it('hands the dock toggles to the caller and reports their state', () => {
    const onToggleChart = vi.fn();
    const onToggleFundamentals = vi.fn();
    mount({ chartOpen: false, onToggleChart, onToggleFundamentals });
    const chart = screen.getByTestId('dock-toggle-chart');
    expect(chart.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(chart);
    fireEvent.click(screen.getByTestId('dock-toggle-fundamental'));
    expect(onToggleChart).toHaveBeenCalledTimes(1);
    expect(onToggleFundamentals).toHaveBeenCalledTimes(1);
  });

  it('collapses to a rail with one open button', () => {
    const onToggleCollapsed = vi.fn();
    mount({ collapsed: true, onToggleCollapsed });
    expect(screen.queryByTestId('symbol-title')).toBeNull();
    fireEvent.click(screen.getByTestId('symbol-rail-open'));
    expect(onToggleCollapsed).toHaveBeenCalledTimes(1);
  });

  it('keeps the chart inside the narrow variant and drops the dock keys', () => {
    const onToggleChart = vi.fn();
    const view = mount({ variant: 'narrow', chartOpen: false, onToggleChart });
    expect(screen.queryByTestId('dock-toggle-chart')).toBeNull();
    expect(screen.queryByTestId('chart-stub')).toBeNull();
    fireEvent.click(screen.getByTestId('symbol-chart-toggle'));
    expect(onToggleChart).toHaveBeenCalledTimes(1);
    view.rerender(
      <SymbolSidebar row={row} symbolKey="10" boardDay={null} variant="narrow"
        chartOpen fundamentalsOpen onToggleChart={() => undefined} onToggleFundamentals={() => undefined} />,
    );
    expect(screen.getByTestId('chart-stub').textContent).toBe('الف');
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
npx vitest run src/__tests__/symbol-sidebar.spec.tsx
```

Expected: FAIL — import resolve.

- [ ] **Step 3: Write the component**

```tsx
import { useState } from 'react';
import clsx from 'clsx';
import { faNum, fmtInt, fmtPct } from '@shared/lib/fa';
import { jalaliFromYmd } from '@shared/lib/jalali';
import type { MarketRow } from '@shared/types/market';
import { ChartPanel } from '@features/chart/ui/ChartPanel';
import { FundamentalSummary } from '@features/fundamental/ui/FundamentalSummary';
import { useMa, technicalSummary, TREND_LABEL } from '@features/market/api/useMa';
import { OrderBookFive } from '@features/market/components/OrderBookFive';
import { TapeFilterChips } from '@features/market/components/TapeFilterChips';
import { TapeHistoryPanel } from '@features/market/components/TapeHistoryPanel';
import { WatchlistButton } from '@features/market/components/WatchlistButton';
import { SymbolGlance } from './SymbolGlance';

type SideTab = 'book' | 'history';

const TREND_TONE = { up: 'text-up', down: 'text-down', neutral: 'text-flat' } as const;

function faDate(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return value;
  return jalaliFromYmd(Number(match[1]) * 10000 + Number(match[2]) * 100 + Number(match[3]));
}

function positionText(distancePct: number | null): string {
  if (distancePct == null) return '';
  if (distancePct > 0) return `بالای آن ${faNum(Math.abs(distancePct), 1)}٪`;
  if (distancePct < 0) return `زیرِ آن ${faNum(Math.abs(distancePct), 1)}٪`;
  return 'روی آن';
}

function levelTone(distancePct: number | null): string {
  if (distancePct == null || distancePct === 0) return 'text-text-3';
  return distancePct > 0 ? 'text-up' : 'text-down';
}

function TechnicalBlock({ row }: { row: MarketRow }) {
  const query = useMa(row.symbol);
  const price = row.p_last ?? row.p_closing ?? null;
  const ma = query.data?.status === 'ok' ? query.data.ma : null;
  const summary = ma ? technicalSummary(ma, price) : null;

  if (query.isLoading) {
    return <p data-testid="tech-loading" className="border-t border-line px-2 py-1 t-9 text-text-3">تکنیکال در حالِ خواندن…</p>;
  }
  if (!summary || (!summary.ma20 && !summary.ma50)) {
    return <p data-testid="tech-unavailable" className="border-t border-line px-2 py-1 t-9 text-text-3">تکنیکال در دسترس نیست.</p>;
  }

  return (
    <div data-testid="symbol-tech" className="flex flex-col gap-0.5 border-t border-line px-2 py-1 t-9">
      <div className="flex justify-between t-85 text-text-3">
        <span>تحلیل تکنیکال</span>
        <span title="میانگین‌ها از /api/ma؛ فاصله با آخرین قیمتِ ردیفِ تابلو">MA · یک نگاه</span>
      </div>
      {summary.ma20 ? (
        <span data-testid="tech-ma20" className="flex justify-between gap-1"
          title={`میانگینِ متحرکِ ۲۰روزه تا ${faDate(summary.ma20.date)}`}>
          <span className="text-text-3">MA20</span>
          <b className="num">{fmtInt(summary.ma20.value)}{' '}
            <span className={levelTone(summary.ma20.distancePct)}>{positionText(summary.ma20.distancePct)}</span>
          </b>
        </span>
      ) : null}
      {summary.ma50 ? (
        <span data-testid="tech-ma50" className="flex justify-between gap-1"
          title={`میانگینِ متحرکِ ۵۰روزه تا ${faDate(summary.ma50.date)}`}>
          <span className="text-text-3">MA50</span>
          <b className="num">{fmtInt(summary.ma50.value)}{' '}
            <span className={levelTone(summary.ma50.distancePct)}>{positionText(summary.ma50.distancePct)}</span>
          </b>
        </span>
      ) : null}
      {summary.slope5Pct != null ? (
        <span data-testid="tech-slope" className="flex justify-between gap-1"
          title="درصدِ تغییرِ MA20 در پنج نشستِ آخر">
          <span className="text-text-3">شیبِ MA20 (۵ روز)</span>
          <b className={clsx('num', TREND_TONE[
            summary.slope5Pct > 0 ? 'up' : summary.slope5Pct < 0 ? 'down' : 'neutral'
          ])}>{fmtPct(summary.slope5Pct, 1)}</b>
        </span>
      ) : null}
      <span data-testid="tech-range" className="flex justify-between gap-1"
        title="کمترین و بیشترین قیمتِ امروز (p_min / p_max)">
        <span className="text-text-3">کف/سقف امروز</span>
        <b className="num">
          {row.p_min == null ? '—' : fmtInt(row.p_min)} / {row.p_max == null ? '—' : fmtInt(row.p_max)}
        </b>
      </span>
      {summary.trend ? (
        <span data-testid="tech-trend" data-trend={summary.trend} className="flex justify-between gap-1">
          <span className="text-text-3">روندِ کوتاه</span>
          <b className={TREND_TONE[summary.trend]}>{TREND_LABEL[summary.trend]}</b>
        </span>
      ) : (
        <span data-testid="tech-trend-unknown" className="t-85 text-text-3">
          روندِ کوتاه سنجیده نشد: شیبِ پنج‌روزه یا قیمت در دسترس نیست.
        </span>
      )}
    </div>
  );
}

export interface SymbolSidebarProps {
  row: MarketRow | null;
  symbolKey: string | null;
  boardDay: number | null;
  variant?: 'wide' | 'narrow';
  chartOpen: boolean;
  fundamentalsOpen: boolean;
  collapsed?: boolean;
  onToggleChart: () => void;
  onToggleFundamentals: () => void;
  onToggleCollapsed?: () => void;
}

export function SymbolSidebar(props: SymbolSidebarProps) {
  const {
    row, symbolKey, boardDay, variant = 'wide', chartOpen, fundamentalsOpen,
    collapsed = false, onToggleChart, onToggleFundamentals, onToggleCollapsed,
  } = props;
  const [tab, setTab] = useState<SideTab>('book');

  if (collapsed) {
    return (
      <div data-testid="symbol-rail"
        className="flex h-full w-12 flex-none flex-col items-center gap-2 border-s border-line bg-panel py-2">
        <button type="button" data-testid="symbol-rail-open" aria-label="باز کردنِ سایدبارِ نماد"
          onClick={onToggleCollapsed}
          className="grid h-6 w-6 place-items-center rounded-[var(--radius-xs)] border border-line text-text-2 hover:border-accent hover:text-accent">
          ›
        </button>
        <span className="max-h-[60%] overflow-hidden text-ellipsis whitespace-nowrap t-95 font-bold text-text-2"
          style={{ writingMode: 'vertical-rl' }}>
          {row?.symbol ?? 'نماد'}
        </span>
      </div>
    );
  }

  if (!symbolKey) {
    return (
      <div data-testid="symbol-sidebar" data-variant={variant}
        className="flex h-full min-h-0 flex-col items-center justify-center gap-1 px-2 text-text-3">
        <b className="t-105 text-text-2">نمادی انتخاب نشده</b>
        <span className="t-9">روی ردیفِ تابلو کلیک کن.</span>
      </div>
    );
  }

  if (!row) {
    return (
      <div data-testid="symbol-sidebar" data-variant={variant} className="flex h-full min-h-0 flex-col">
        <div data-testid="symbol-not-in-board" className="grid flex-1 place-items-center px-2 text-center t-95 text-text-3">
          این نماد در تابلو نیست.
        </div>
      </div>
    );
  }

  return (
    <div data-testid="symbol-sidebar" data-variant={variant} className="flex h-full min-h-0 flex-col">
      <div className="flex flex-none items-center gap-1.5 border-b border-line px-2 py-1">
        <b data-testid="symbol-title" className="t-115 font-extrabold text-text">{row.symbol}</b>
        <span className="min-w-0 truncate t-9 text-text-3">{row.name ?? ''}</span>
        {variant === 'wide' && onToggleCollapsed ? (
          <button type="button" data-testid="symbol-collapse" aria-label="جمع کردنِ سایدبارِ نماد"
            onClick={onToggleCollapsed}
            className="ms-auto grid h-5 w-5 flex-none place-items-center rounded-[var(--radius-xs)] text-text-3 hover:bg-panel-3 hover:text-text">
            ‹
          </button>
        ) : null}
      </div>

      <div className="flex-none px-2 py-1">
        <WatchlistButton symbol={row.symbol} name={row.name ?? undefined} />
      </div>

      {variant === 'wide' ? (
        <div className="grid flex-none grid-cols-2 gap-1 border-y border-line px-2 py-1">
          <button type="button" data-testid="dock-toggle-chart" aria-expanded={chartOpen} onClick={onToggleChart}
            className={clsx('rounded-[var(--radius-sm)] border px-1.5 py-0.5 t-95',
              chartOpen ? 'border-accent/60 bg-accent/10 font-bold text-accent' : 'border-line text-text-3 hover:text-text-2')}>
            {chartOpen ? 'چارت روشن' : 'چارت خاموش'}
          </button>
          <button type="button" data-testid="dock-toggle-fundamental" aria-expanded={fundamentalsOpen} onClick={onToggleFundamentals}
            className={clsx('rounded-[var(--radius-sm)] border px-1.5 py-0.5 t-95',
              fundamentalsOpen ? 'border-accent/60 bg-accent/10 font-bold text-accent' : 'border-line text-text-3 hover:text-text-2')}>
            {fundamentalsOpen ? 'بنیادی روشن' : 'بنیادی خاموش'}
          </button>
        </div>
      ) : null}

      <div className="min-h-0 flex-1 overflow-y-auto">
        <SymbolGlance row={row} />
        <TapeFilterChips row={row} />
        <TechnicalBlock row={row} />
        <FundamentalSummary
          symbol={row.symbol}
          expanded={fundamentalsOpen}
          onToggle={variant === 'wide' ? onToggleFundamentals : undefined}
        />

        {variant === 'narrow' ? (
          <div className="flex-none border-y border-line">
            <button type="button" data-testid="symbol-chart-toggle" aria-expanded={chartOpen} onClick={onToggleChart}
              className="flex w-full items-center justify-between px-2 py-0.5 t-9 text-text-2 hover:bg-panel-2">
              <span>چارت</span>
              <span className="text-text-3">{chartOpen ? 'بستن' : 'باز کردن'}</span>
            </button>
            {chartOpen ? <div className="h-[150px] border-t border-line"><ChartPanel symbol={row.symbol} /></div> : null}
          </div>
        ) : null}

        <div className="flex flex-none items-center gap-1 border-b border-line px-2 py-0.5" role="tablist">
          {(['book', 'history'] as const).map((id) => (
            <button key={id} type="button" role="tab" aria-selected={tab === id}
              data-testid={`symbol-tab-${id}`} onClick={() => setTab(id)}
              className={clsx('tape-btn', tab === id && 'is-on')}>
              {id === 'book' ? 'عمق' : 'تاریخچه تابلو'}
            </button>
          ))}
        </div>
        <div className="min-h-[160px] flex-none">
          {tab === 'book'
            ? <OrderBookFive symbol={row.symbol} insCode={row.ins_code} boardDay={boardDay} />
            : <TapeHistoryPanel symbol={row.symbol} insCode={row.ins_code} />}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
npx vitest run src/__tests__/symbol-sidebar.spec.tsx
npx tsc -b
```

Expected: 8/8 PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/src/app/shell/SymbolSidebar.tsx frontend-v2/src/__tests__/symbol-sidebar.spec.tsx
git commit -m "$(cat <<'EOF'
feat(symbol): سایدبارِ چپ با نگاهِ یک‌نگاهی
EOF
)"
```

---

## Task 8: داکِ پایینِ چارت و پنج کارت

**Files:**
- Create: `frontend-v2/src/app/shell/BottomDock.tsx`
- Test: `frontend-v2/src/__tests__/bottom-dock.spec.tsx`

**Interfaces:**
- Consumes: `LayoutResizer`، `ChartPanel`، `FundamentalCards`، `CHART_SHARE`/`DOCK_HEIGHT`
- Produces: `BottomDock({ symbol, chartOpen, fundamentalsOpen, height, chartShare, onToggleChart, onToggleFundamentals, onHeightChange, onChartShareChange })` با:
  - `bottom-dock` (ارتفاعِ inline)، `resize-dock`، `resize-chart`، `dock-chart`، `dock-fundamentals`
  - `dock-collapsed` + `dock-open-chart`/`dock-open-fundamental` وقتی هر دو خاموش‌اند
  - `dock-chart-empty` / `dock-fundamentals-empty` بدونِ نماد

- [ ] **Step 1: Write the failing test**

```tsx
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { BottomDock } from '@app/shell/BottomDock';

vi.mock('@features/chart/ui/ChartPanel', () => ({
  ChartPanel: ({ symbol }: { symbol: string }) => <div data-testid="chart-stub">{symbol}</div>,
}));
vi.mock('@features/fundamental/ui/FundamentalCards', () => ({
  FundamentalCards: ({ symbol }: { symbol: string }) => <div data-testid="cards-stub">{symbol}</div>,
}));

afterEach(cleanup);

function mount(patch: Partial<Parameters<typeof BottomDock>[0]> = {}) {
  return render(
    <BottomDock
      symbol="فولاد"
      chartOpen
      fundamentalsOpen
      height={200}
      chartShare={0.45}
      onToggleChart={() => undefined}
      onToggleFundamentals={() => undefined}
      onHeightChange={() => undefined}
      onChartShareChange={() => undefined}
      {...patch}
    />,
  );
}

describe('BottomDock', () => {
  it('splits the open dock into a chart on the right and the five cards beside it', () => {
    mount();
    expect(screen.getByTestId('bottom-dock').getAttribute('style')).toContain('height: 200px');
    expect(screen.getByTestId('chart-stub').textContent).toBe('فولاد');
    expect(screen.getByTestId('cards-stub').textContent).toBe('فولاد');
    expect(screen.getByTestId('dock-chart').getAttribute('style')).toContain('width: 45%');
    expect(screen.getAllByRole('separator')).toHaveLength(2);
  });

  it('gives the whole width to the single open group', () => {
    mount({ fundamentalsOpen: false });
    expect(screen.getByTestId('dock-chart').getAttribute('style')).toBeNull();
    expect(screen.queryByTestId('dock-fundamentals')).toBeNull();
    expect(screen.getAllByRole('separator')).toHaveLength(1);
  });

  it('collapses to two chips when both groups are closed', () => {
    const onToggleChart = vi.fn();
    const onToggleFundamentals = vi.fn();
    mount({ chartOpen: false, fundamentalsOpen: false, onToggleChart, onToggleFundamentals });
    expect(screen.queryByTestId('bottom-dock')).toBeNull();
    fireEvent.click(screen.getByTestId('dock-open-chart'));
    fireEvent.click(screen.getByTestId('dock-open-fundamental'));
    expect(onToggleChart).toHaveBeenCalledTimes(1);
    expect(onToggleFundamentals).toHaveBeenCalledTimes(1);
  });

  it('keeps an honest empty message for each group without a symbol', () => {
    mount({ symbol: null });
    expect(screen.getByTestId('dock-chart-empty')).toBeTruthy();
    expect(screen.getByTestId('dock-fundamentals-empty')).toBeTruthy();
    expect(screen.queryByTestId('chart-stub')).toBeNull();
    expect(screen.queryByTestId('cards-stub')).toBeNull();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
npx vitest run src/__tests__/bottom-dock.spec.tsx
```

Expected: FAIL — import resolve.

- [ ] **Step 3: Write the component**

```tsx
import { useRef } from 'react';
import { ChartPanel } from '@features/chart/ui/ChartPanel';
import { FundamentalCards } from '@features/fundamental/ui/FundamentalCards';
import { LayoutResizer } from '@shared/workspace/LayoutResizer';
import { CHART_SHARE, DOCK_HEIGHT } from '@shared/workspace/sizes';

export interface BottomDockProps {
  symbol: string | null;
  chartOpen: boolean;
  fundamentalsOpen: boolean;
  height: number;
  chartShare: number;
  onToggleChart: () => void;
  onToggleFundamentals: () => void;
  onHeightChange: (height: number) => void;
  onChartShareChange: (share: number) => void;
}

export function BottomDock(props: BottomDockProps) {
  const {
    symbol, chartOpen, fundamentalsOpen, height, chartShare,
    onToggleChart, onToggleFundamentals, onHeightChange, onChartShareChange,
  } = props;
  const host = useRef<HTMLElement>(null);

  if (!chartOpen && !fundamentalsOpen) {
    return (
      <div data-testid="dock-collapsed"
        className="flex h-6 flex-none items-center gap-1 border-t border-line bg-panel px-2">
        <span className="t-85 text-text-3">داک بسته است</span>
        <button type="button" data-testid="dock-open-chart" className="tape-btn" onClick={onToggleChart}>چارت</button>
        <button type="button" data-testid="dock-open-fundamental" className="tape-btn" onClick={onToggleFundamentals}>بنیادی</button>
      </div>
    );
  }

  return (
    <section ref={host} data-testid="bottom-dock" style={{ height }}
      className="relative flex min-h-0 flex-none flex-col border-t border-line bg-panel">
      <LayoutResizer
        orientation="horizontal"
        value={height}
        min={DOCK_HEIGHT.min}
        max={DOCK_HEIGHT.max}
        step={8}
        defaultValue={DOCK_HEIGHT.default}
        label="ارتفاع داک پایین"
        testId="resize-dock"
        increaseKey="ArrowUp"
        decreaseKey="ArrowDown"
        fromPointer={(rect, _x, y) => rect.bottom - y}
        measure={() => host.current?.getBoundingClientRect() ?? null}
        onChange={onHeightChange}
      />

      <div className="flex min-h-0 flex-1">
        {chartOpen ? (
          <div
            data-testid="dock-chart"
            style={fundamentalsOpen ? { width: `${Number((chartShare * 100).toFixed(2))}%` } : undefined}
            className={fundamentalsOpen ? 'min-h-0 min-w-0 flex-none' : 'min-h-0 min-w-0 flex-1'}
          >
            {symbol ? <ChartPanel symbol={symbol} /> : (
              <p data-testid="dock-chart-empty" className="grid h-full place-items-center px-2 t-95 text-text-3">
                برای چارت، نمادی را از تابلو انتخاب کن.
              </p>
            )}
          </div>
        ) : null}

        {chartOpen && fundamentalsOpen ? (
          <LayoutResizer
            orientation="vertical"
            value={chartShare}
            min={CHART_SHARE.min}
            max={CHART_SHARE.max}
            step={0.02}
            defaultValue={CHART_SHARE.default}
            label="عرض چارت"
            testId="resize-chart"
            increaseKey="ArrowLeft"
            decreaseKey="ArrowRight"
            fromPointer={(rect, x) => (rect.right - x) / Math.max(1, rect.width)}
            measure={() => host.current?.getBoundingClientRect() ?? null}
            onChange={onChartShareChange}
          />
        ) : null}

        {fundamentalsOpen ? (
          <div data-testid="dock-fundamentals" className="min-h-0 min-w-0 flex-1 overflow-x-auto">
            {symbol ? <FundamentalCards symbol={symbol} /> : (
              <p data-testid="dock-fundamentals-empty" className="grid h-full place-items-center px-2 t-95 text-text-3">
                برای کارت‌های بنیادی، نمادی را از تابلو انتخاب کن.
              </p>
            )}
          </div>
        ) : null}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
npx vitest run src/__tests__/bottom-dock.spec.tsx
npx tsc -b
```

Expected: 4/4 PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/src/app/shell/BottomDock.tsx frontend-v2/src/__tests__/bottom-dock.spec.tsx
git commit -m "$(cat <<'EOF'
feat(symbol): داکِ پایینِ چارت و پنج کارت
EOF
)"
```

---

## Task 9: میزکارِ سه‌ناحیه‌ای و حذفِ کاشیِ نماد

**Files:**
- Modify: `frontend-v2/src/shared/workspace/types.ts`
- Modify: `frontend-v2/src/shared/workspace/layout.ts`
- Modify: `frontend-v2/src/shared/workspace/TileFrame.tsx`
- Modify: `frontend-v2/src/shared/workspace/WorkspaceShell.tsx`
- Modify: `frontend-v2/src/shared/workspace/shortcuts.ts`
- Modify: `frontend-v2/src/features/market/routes/MarketPage.tsx`
- Delete: `frontend-v2/src/features/market/panels/SymbolPanel.tsx`
- Delete: `frontend-v2/src/__tests__/symbol-panel.spec.tsx`
- Test: `frontend-v2/src/__tests__/workspace-layout.spec.ts`
- Test: `frontend-v2/src/__tests__/workspace-shell.spec.tsx`
- Test: `frontend-v2/src/__tests__/workspace-keyboard.spec.tsx`
- Test: `frontend-v2/src/__tests__/workspace-store.spec.ts`
- Test: `frontend-v2/src/__tests__/market-workspace.spec.tsx`
- Test: `frontend-v2/src/__tests__/board-views-export.spec.tsx`
- Test: `frontend-v2/src/__tests__/board-watch-symbol.spec.tsx`

**Interfaces:**
- Consumes: `SymbolSidebar`، `BottomDock`، `LayoutResizer`، `SIDE_WIDTH`
- Produces:
  - `TilePanel = 'board' | 'watch'`، `DEFAULT_LAYOUT` دوپنلی (`s-root` 0.7، `t-board`/`t-watch`)، `PANEL_MIN.watch.w = 220`، `MAX_TILES = 2`
  - `isValidLayout` فقط `board|watch` را می‌پذیرد؛ هر چیدمانِ ذخیره‌شده با `symbol`/`chart` در rehydrate به پیش‌فرضِ دوپنلی می‌افتد و انتخابِ فعال حفظ می‌شود
  - `WorkspaceShellProps` بدونِ `onToggleFollow`؛ `TileFrame` با `canAddWatch` و `tile-add-watch`

- [ ] **Step 1: Replace `types.ts`**

```ts
export type TilePanel = 'board' | 'watch';
export type SplitDir = 'row' | 'col';
export type MoveDir = 'left' | 'right' | 'up' | 'down';

export type LayoutNode =
  | { kind: 'tile'; id: string; panel: TilePanel; follow: boolean }
  | { kind: 'split'; id: string; dir: SplitDir; ratio: number;
      first: LayoutNode; second: LayoutNode };

export const PANEL_LABEL: Record<TilePanel, string> = {
  board: 'تابلو',
  watch: 'دیده‌بان‌ها',
};

export const PANEL_MIN: Record<TilePanel, { w: number; h: number }> = {
  board: { w: 520, h: 240 },
  watch: { w: 220, h: 180 },
};

export const MAX_DEPTH = 3;
export const MAX_TILES = 2;

export const DEFAULT_LAYOUT: LayoutNode = {
  kind: 'split', id: 's-root', dir: 'row', ratio: 0.7,
  first: { kind: 'tile', id: 't-board', panel: 'board', follow: false },
  second: { kind: 'tile', id: 't-watch', panel: 'watch', follow: false },
};
```

- [ ] **Step 2: Tighten `isValidLayout` in `layout.ts`**

Replace the panel whitelist and the tile cap inside `isValidLayout`:

```ts
    if (item.kind === 'tile') {
      total += 1;
      if (!['board', 'watch'].includes(String(item.panel))) return false;
      if (item.panel === 'board') board += 1;
      return typeof item.id === 'string' && typeof item.follow === 'boolean';
    }
```

```ts
  return walk(node, 1) && board === 1 && total <= MAX_TILES;
```

- [ ] **Step 3: Update `shortcuts.ts`**

```ts
  { id: 'panels', keys: 'Alt+۱ و ۲', label: 'رفتن به پنل' },
```

- [ ] **Step 4: Replace `TileFrame.tsx`**

```tsx
import { useEffect, useState, type ReactNode } from 'react';
import clsx from 'clsx';
import { PANEL_LABEL, PANEL_MIN, type MoveDir, type SplitDir, type TilePanel } from './layout';

interface Props {
  id: string;
  panel: TilePanel;
  focused: boolean;
  canAddWatch: boolean;
  onFocus: (id: string) => void;
  onClose: (id: string) => void;
  onSplit: (id: string, dir: SplitDir, panel: TilePanel) => void;
  onSwap: (id: string, dir: MoveDir) => void;
  children: ReactNode;
}

export function TileFrame(props: Props) {
  const { id, panel, focused, canAddWatch, onFocus, onClose, onSplit, onSwap, children } = props;
  const [menu, setMenu] = useState(false);

  useEffect(() => {
    if (!menu) return;
    const close = () => setMenu(false);
    window.addEventListener('click', close);
    return () => window.removeEventListener('click', close);
  }, [menu]);

  return (
    <div
      data-tile-id={id}
      data-tile-focused={focused ? 'true' : 'false'}
      data-testid={`tile-${id}`}
      style={{ minWidth: PANEL_MIN[panel].w, minHeight: PANEL_MIN[panel].h }}
      className={clsx('relative flex h-full min-h-0 w-full min-w-0 flex-col bg-panel',
        focused && 'outline outline-1 outline-accent')}
    >
      <div
        data-tile-header
        tabIndex={0}
        role="group"
        aria-label={PANEL_LABEL[panel]}
        data-testid={`tile-header-${id}`}
        onFocus={() => onFocus(id)}
        onMouseDown={() => onFocus(id)}
        onKeyDown={(event) => {
          if (event.key === 'ArrowLeft') { event.preventDefault(); onSwap(id, 'left'); }
          if (event.key === 'ArrowRight') { event.preventDefault(); onSwap(id, 'right'); }
          if (event.key === 'ArrowUp') { event.preventDefault(); onSwap(id, 'up'); }
          if (event.key === 'ArrowDown') { event.preventDefault(); onSwap(id, 'down'); }
        }}
        className="flex h-7 flex-none items-center gap-1.5 border-b border-line bg-panel-2 px-2 t-10 text-text-2"
      >
        <span className="font-bold">{PANEL_LABEL[panel]}</span>
        {focused ? (
          <span data-testid={`tile-hint-${id}`} className="t-9 text-text-3">
            با ←→↑↓ جابه‌جا کن
          </span>
        ) : null}
        <div className="ms-auto flex items-center gap-1">
          {canAddWatch ? (
            <button
              type="button"
              data-testid={`tile-menu-${id}`}
              aria-label="کارهای پنل"
              className="grid h-5 w-5 place-items-center rounded-[var(--radius-xs)] hover:bg-panel-3"
              onClick={(event) => { event.stopPropagation(); setMenu((open) => !open); }}
            >
              ⋯
            </button>
          ) : null}
          {panel !== 'board' ? (
            <button
              type="button"
              data-testid={`tile-close-${id}`}
              aria-label="بستنِ پنل"
              className="grid h-5 w-5 place-items-center rounded-[var(--radius-xs)] hover:bg-panel-3"
              onClick={() => onClose(id)}
            >
              ×
            </button>
          ) : null}
        </div>
      </div>

      {menu && canAddWatch ? (
        <div className="absolute z-20 mt-7 rounded-[var(--radius-sm)] border border-line bg-panel p-1 t-9"
          onClick={(event) => event.stopPropagation()}>
          <button
            type="button"
            data-testid="tile-add-watch"
            className="block w-full rounded-[var(--radius-xs)] px-2 py-1 text-start hover:bg-panel-2"
            onClick={() => { setMenu(false); onSplit(id, 'col', 'watch'); }}
          >
            افزودنِ دیده‌بان
          </button>
        </div>
      ) : null}

      <div className="min-h-0 flex-1 overflow-hidden">{children}</div>
    </div>
  );
}
```

- [ ] **Step 5: Replace `WorkspaceShell.tsx`**

```tsx
import { useRef, useState, type ReactNode } from 'react';
import { Splitter } from './Splitter';
import { TileFrame } from './TileFrame';
import { panelsInOrder, type LayoutNode, type MoveDir, type SplitDir, type TilePanel } from './layout';

export interface WorkspaceShellProps {
  layout: LayoutNode;
  renderPanel: (panel: TilePanel) => ReactNode;
  onClose: (id: string) => void;
  onSplit: (id: string, dir: SplitDir, panel: TilePanel) => void;
  onSwap: (id: string, dir: MoveDir) => void;
  onRatio: (splitId: string, ratio: number, width: number, height: number) => void;
}

export function WorkspaceShell(props: WorkspaceShellProps) {
  const { layout, renderPanel, onClose, onSplit, onSwap, onRatio } = props;
  const [focused, setFocused] = useState<string | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const canAddWatch = !panelsInOrder(layout).some((item) => item.panel === 'watch');

  function node(item: LayoutNode): ReactNode {
    if (item.kind === 'tile') {
      return (
        <TileFrame
          key={item.id}
          id={item.id}
          panel={item.panel}
          focused={focused === item.id}
          canAddWatch={canAddWatch}
          onFocus={setFocused}
          onClose={onClose}
          onSplit={onSplit}
          onSwap={onSwap}
        >
          {renderPanel(item.panel)}
        </TileFrame>
      );
    }

    const resize = (ratio: number) => {
      const rect = root.current?.getBoundingClientRect();
      onRatio(item.id, ratio, rect?.width ?? 0, rect?.height ?? 0);
    };

    return (
      <div
        key={item.id}
        className={item.dir === 'row' ? 'flex h-full min-h-0 min-w-0' : 'flex h-full min-h-0 min-w-0 flex-col'}
      >
        <div className="min-h-0 min-w-0" style={{ flex: `${item.ratio} 1 0%` }}>{node(item.first)}</div>
        <Splitter dir={item.dir} container={root} onRatio={resize} />
        <div className="min-h-0 min-w-0" style={{ flex: `${1 - item.ratio} 1 0%` }}>{node(item.second)}</div>
      </div>
    );
  }

  return <div ref={root} data-testid="workspace-shell" className="h-full min-h-0 w-full min-w-0">{node(layout)}</div>;
}
```

- [ ] **Step 6: Replace `MarketPage.tsx`**

```tsx
import { useMemo, useState } from 'react';
import type { MarketRow } from '@shared/types/market';
import { useMediaQuery } from '@shared/lib/useMediaQuery';
import { useWorkspace } from '@shared/workspace/store';
import { SIDE_WIDTH } from '@shared/workspace/sizes';
import { useTileKeyboard } from '@shared/workspace/useTileKeyboard';
import { WorkspaceShell } from '@shared/workspace/WorkspaceShell';
import { LayoutResizer } from '@shared/workspace/LayoutResizer';
import type { TilePanel } from '@shared/workspace/layout';
import { SymbolSidebar } from '@app/shell/SymbolSidebar';
import { BottomDock } from '@app/shell/BottomDock';
import { useBoard } from '../api/useBoard';
import { useMarketSnapshot } from '../api/useMarketSnapshot';
import { SnapshotStrip } from '../components/SnapshotStrip';
import { BoardPanel } from '../panels/BoardPanel';
import { WatchPanel } from '../panels/WatchPanel';
import { DEFAULT_TAPE_FILTER_CONFIG } from '../lib/tapeAlgorithms';
import { useMarketPrefs } from '../stores/prefs';

type Tab = 'symbol' | 'watch';

function identityOf(row: MarketRow): string {
  return row.ins_code?.trim() || row.symbol;
}

export function MarketPage() {
  const layout = useWorkspace((state) => state.workspaces[0].layout);
  const chartOpen = useWorkspace((state) => state.workspaces[0].chartOpen);
  const fundamentalsOpen = useWorkspace((state) => state.workspaces[0].fundamentalsOpen);
  const sideCollapsed = useWorkspace((state) => state.workspaces[0].sideCollapsed);
  const sideWidth = useWorkspace((state) => state.workspaces[0].sideWidth);
  const dockHeight = useWorkspace((state) => state.workspaces[0].dockHeight);
  const chartShare = useWorkspace((state) => state.workspaces[0].chartShare);
  const activeSymbol = useWorkspace((state) => state.activeSymbol);
  const setActiveSymbol = useWorkspace((state) => state.setActiveSymbol);
  const setChartOpen = useWorkspace((state) => state.setChartOpen);
  const setFundamentalsOpen = useWorkspace((state) => state.setFundamentalsOpen);
  const setSideCollapsed = useWorkspace((state) => state.setSideCollapsed);
  const setSideWidth = useWorkspace((state) => state.setSideWidth);
  const setDockHeight = useWorkspace((state) => state.setDockHeight);
  const setChartShare = useWorkspace((state) => state.setChartShare);
  const split = useWorkspace((state) => state.split);
  const close = useWorkspace((state) => state.close);
  const swap = useWorkspace((state) => state.swap);
  const setRatio = useWorkspace((state) => state.setRatio);

  const pollMs = useMarketPrefs((state) => state.pollMs);
  const setFilters = useMarketPrefs((state) => state.setFilters);
  const board = useBoard(pollMs);
  const snapshot = useMarketSnapshot(pollMs);
  const rows = useMemo(() => board.data?.data ?? [], [board.data]);
  const [boardDay, setBoardDay] = useState<number | null>(null);
  const [tab, setTab] = useState<Tab>('symbol');
  const narrow = useMediaQuery('(max-width: 1279px)');

  useTileKeyboard(layout);

  const symbolRow = useMemo(() => {
    if (!activeSymbol) return null;
    return rows.find((row) => identityOf(row) === activeSymbol) ?? null;
  }, [rows, activeSymbol]);

  function selectRow(row: MarketRow, day: number | null) {
    setBoardDay(day);
    setActiveSymbol(identityOf(row));
  }

  function selectWatchRow(insCode: string) {
    setActiveSymbol(insCode);
  }

  function renderPanel(panel: TilePanel) {
    if (panel === 'watch') {
      return (
        <WatchPanel
          rows={rows}
          filterConfig={DEFAULT_TAPE_FILTER_CONFIG}
          onSelect={selectWatchRow}
          onPickSector={(sector) => setFilters({ sector })}
        />
      );
    }
    return <BoardPanel selectedKey={activeSymbol} onSelect={selectRow} onActivate={selectRow} />;
  }

  const toggleChart = () => setChartOpen(!chartOpen);
  const toggleFundamentals = () => setFundamentalsOpen(!fundamentalsOpen);

  if (narrow) {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <SnapshotStrip rows={rows} snapshot={snapshot.data} />
        <div className="flex min-h-0 flex-1">
          <div className="flex min-h-0 min-w-0 flex-1 flex-col">
            <BoardPanel selectedKey={activeSymbol} onSelect={selectRow} onActivate={selectRow} />
          </div>
          {activeSymbol ? (
            <div className="flex min-h-0 w-[340px] flex-none flex-col border-s border-line">
              <div className="flex flex-none gap-1 border-b border-line px-2 py-1" role="tablist">
                {([['symbol', 'نماد'], ['watch', 'دیده‌بان‌ها']] as const).map(([id, label]) => (
                  <button key={id} type="button" role="tab" aria-selected={tab === id}
                    data-testid={`narrow-tab-${id}`} onClick={() => setTab(id)} className="tape-btn">
                    {label}
                  </button>
                ))}
              </div>
              <div className="min-h-0 flex-1">
                {tab === 'symbol' ? (
                  <SymbolSidebar
                    variant="narrow"
                    row={symbolRow}
                    symbolKey={activeSymbol}
                    boardDay={boardDay}
                    chartOpen={chartOpen}
                    fundamentalsOpen={fundamentalsOpen}
                    onToggleChart={toggleChart}
                    onToggleFundamentals={toggleFundamentals}
                  />
                ) : (
                  <WatchPanel
                    rows={rows}
                    filterConfig={DEFAULT_TAPE_FILTER_CONFIG}
                    onSelect={selectWatchRow}
                    onPickSector={(sector) => setFilters({ sector })}
                  />
                )}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <SnapshotStrip rows={rows} snapshot={snapshot.data} />
      <div className="flex min-h-0 flex-1">
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1">
            <WorkspaceShell
              layout={layout}
              renderPanel={renderPanel}
              onClose={close}
              onSplit={split}
              onSwap={swap}
              onRatio={setRatio}
            />
          </div>
          <BottomDock
            symbol={symbolRow?.symbol ?? null}
            chartOpen={chartOpen}
            fundamentalsOpen={fundamentalsOpen}
            height={dockHeight}
            chartShare={chartShare}
            onToggleChart={toggleChart}
            onToggleFundamentals={toggleFundamentals}
            onHeightChange={setDockHeight}
            onChartShareChange={setChartShare}
          />
        </div>
        {sideCollapsed ? (
          <SymbolSidebar
            collapsed
            row={symbolRow}
            symbolKey={activeSymbol}
            boardDay={boardDay}
            chartOpen={chartOpen}
            fundamentalsOpen={fundamentalsOpen}
            onToggleChart={toggleChart}
            onToggleFundamentals={toggleFundamentals}
            onToggleCollapsed={() => setSideCollapsed(false)}
          />
        ) : (
          <>
            <LayoutResizer
              orientation="vertical"
              value={sideWidth}
              min={SIDE_WIDTH.min}
              max={SIDE_WIDTH.max}
              step={8}
              defaultValue={SIDE_WIDTH.default}
              label="عرض سایدبار نماد"
              testId="resize-sidebar"
              increaseKey="ArrowRight"
              decreaseKey="ArrowLeft"
              fromPointer={(rect, x) => x - rect.left}
              onChange={setSideWidth}
            />
            <div style={{ width: sideWidth }} className="flex min-h-0 flex-none flex-col border-s border-line bg-panel">
              <SymbolSidebar
                row={symbolRow}
                symbolKey={activeSymbol}
                boardDay={boardDay}
                chartOpen={chartOpen}
                fundamentalsOpen={fundamentalsOpen}
                onToggleChart={toggleChart}
                onToggleFundamentals={toggleFundamentals}
                onToggleCollapsed={() => setSideCollapsed(true)}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Delete the symbol tile and its spec**

```bash
rm frontend-v2/src/features/market/panels/SymbolPanel.tsx
rm frontend-v2/src/__tests__/symbol-panel.spec.tsx
```

- [ ] **Step 8: Rewrite `workspace-layout.spec.ts`**

```ts
import { describe, expect, it } from 'vitest';
import {
  DEFAULT_LAYOUT, clampRatio, closeTile, findTile, isValidLayout, neighborOf,
  panelsInOrder, ratioFromPointer, splitTile, swapWithNeighbor, type LayoutNode,
} from '@shared/workspace/layout';

const ids = (root: LayoutNode) => panelsInOrder(root).map((item) => item.panel);

describe('layout tree', () => {
  it('reads panels right-to-left', () => {
    expect(ids(DEFAULT_LAYOUT)).toEqual(['board', 'watch']);
  });

  it('refuses a duplicate panel and allows adding watch once it is closed', () => {
    expect(splitTile(DEFAULT_LAYOUT, 't-board', 'col', 'watch', () => 't-x')).toBeNull();
    const closed = closeTile(DEFAULT_LAYOUT, 't-watch')!;
    const next = splitTile(closed, 't-board', 'col', 'watch', () => 't-new');
    expect(next).not.toBeNull();
    expect(ids(next!).sort()).toEqual(['board', 'watch']);
  });

  it('closes a tile, collapses its parent and refuses to close the board', () => {
    expect(ids(closeTile(DEFAULT_LAYOUT, 't-watch')!)).toEqual(['board']);
    expect(closeTile(DEFAULT_LAYOUT, 't-board')).toBeNull();
  });

  it('finds the visual neighbour in RTL', () => {
    expect(neighborOf(DEFAULT_LAYOUT, 't-board', 'left')).toBe('t-watch');
    expect(neighborOf(DEFAULT_LAYOUT, 't-watch', 'right')).toBe('t-board');
    expect(neighborOf(DEFAULT_LAYOUT, 't-board', 'down')).toBeNull();
  });

  it('swaps payloads and keeps tree ids stable', () => {
    const moved = swapWithNeighbor(DEFAULT_LAYOUT, 't-board', 'left')!;
    expect(moved.movedTo).toBe('t-watch');
    expect(findTile(moved.root, 't-board')?.panel).toBe('watch');
    expect(findTile(moved.root, 't-watch')?.panel).toBe('board');
  });

  it('clamps ratio by pixel minimums and refuses impossible splits', () => {
    expect(clampRatio(DEFAULT_LAYOUT, 0.95, 1000, 700)).toBeCloseTo(0.78, 5);
    expect(clampRatio(DEFAULT_LAYOUT, 0.7, 700, 700)).toBeNull();
  });

  it('maps pointer position to ratio from the start edge', () => {
    expect(ratioFromPointer({ left: 0, top: 0, width: 1000, height: 600 }, 'row', 300, 0)).toBeCloseTo(0.7);
    expect(ratioFromPointer({ left: 0, top: 0, width: 1000, height: 600 }, 'col', 0, 300)).toBeCloseTo(0.5);
  });

  it('rejects a legacy symbol panel and accepts the two-pane default', () => {
    const legacy: LayoutNode = { kind: 'tile', id: 'x', panel: 'symbol' as never, follow: false };
    expect(isValidLayout(legacy)).toBe(false);
    expect(isValidLayout(DEFAULT_LAYOUT)).toBe(true);
  });
});
```

- [ ] **Step 9: Rewrite `workspace-shell.spec.tsx`**

```tsx
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { DEFAULT_LAYOUT, type LayoutNode } from '@shared/workspace/layout';
import { WorkspaceShell } from '@shared/workspace/WorkspaceShell';

const boardOnly: LayoutNode = { kind: 'tile', id: 't-board', panel: 'board', follow: false };

afterEach(cleanup);

function mount(overrides: Partial<Parameters<typeof WorkspaceShell>[0]> = {}) {
  return render(
    <WorkspaceShell
      layout={DEFAULT_LAYOUT}
      renderPanel={(panel) => <div data-testid={`body-${panel}`}>{panel}</div>}
      onClose={() => {}}
      onSplit={() => {}}
      onSwap={() => {}}
      onRatio={() => {}}
      {...overrides}
    />,
  );
}

describe('WorkspaceShell', () => {
  it('renders the board and the watch tile', () => {
    mount();
    expect(screen.getByTestId('body-board')).toBeTruthy();
    expect(screen.getByTestId('body-watch')).toBeTruthy();
    expect(screen.getByText('تابلو')).toBeTruthy();
    expect(screen.getByText('دیده‌بان‌ها')).toBeTruthy();
  });

  it('keeps the board unclosable and closes the watch tile', () => {
    const onClose = vi.fn();
    mount({ onClose });
    expect(screen.queryByTestId('tile-close-t-board')).toBeNull();
    fireEvent.click(screen.getByTestId('tile-close-t-watch'));
    expect(onClose).toHaveBeenCalledWith('t-watch');
  });

  it('offers the watch split only while the watch tile is absent', () => {
    const onSplit = vi.fn();
    const view = mount({ layout: boardOnly, onSplit });
    expect(screen.queryByTestId('tile-menu-t-board')).toBeTruthy();
    fireEvent.click(screen.getByTestId('tile-menu-t-board'));
    fireEvent.click(screen.getByTestId('tile-add-watch'));
    expect(onSplit).toHaveBeenCalledWith('t-board', 'col', 'watch');
    view.unmount();
    mount();
    expect(screen.queryByTestId('tile-menu-t-board')).toBeNull();
  });

  it('marks the focused tile and exposes the arrow hint', () => {
    mount();
    const header = screen.getByTestId('tile-header-t-watch');
    fireEvent.focus(header);
    expect(screen.getByTestId('tile-t-watch').getAttribute('data-tile-focused')).toBe('true');
    expect(screen.getByTestId('tile-hint-t-watch').textContent).toContain('جابه‌جا');
  });

  it('renders one separator for the board/watch split', () => {
    mount();
    expect(screen.getAllByRole('separator')).toHaveLength(1);
  });
});
```

- [ ] **Step 10: Update `workspace-keyboard.spec.tsx`**

```tsx
import { cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { DEFAULT_LAYOUT } from '@shared/workspace/layout';
import { SHORTCUTS } from '@shared/workspace/shortcuts';
import { useWorkspace } from '@shared/workspace/store';
import { useTileKeyboard } from '@shared/workspace/useTileKeyboard';

afterEach(cleanup);

beforeEach(() => {
  localStorage.clear();
  useWorkspace.setState(useWorkspace.getInitialState(), true);
});

function Harness() {
  useTileKeyboard(DEFAULT_LAYOUT);
  return (
    <div>
      <div data-tile-id="t-board"><div data-tile-header tabIndex={0} data-testid="h-board" /></div>
      <div data-tile-id="t-watch"><div data-tile-header tabIndex={0} data-testid="h-watch" /></div>
    </div>
  );
}

describe('tile keyboard', () => {
  it('lists the approved shortcuts in one registry', () => {
    expect(SHORTCUTS.map((item) => item.keys)).toEqual(['Alt+۱ و ۲', '←→↑↓', 'Ctrl+K', 'Ctrl+Z', 'Esc']);
  });

  it('focuses panels by their reading order with Alt+Digit', () => {
    render(<Harness />);
    fireEvent.keyDown(window, { key: '1', code: 'Digit1', altKey: true });
    expect(document.activeElement?.getAttribute('data-testid')).toBe('h-board');
    fireEvent.keyDown(window, { key: '2', code: 'Digit2', altKey: true });
    expect(document.activeElement?.getAttribute('data-testid')).toBe('h-watch');
  });

  it('undoes the last layout change with Ctrl+Z', () => {
    render(<Harness />);
    useWorkspace.getState().close('t-watch');
    expect(JSON.stringify(useWorkspace.getState().workspaces[0].layout)).not.toContain('"watch"');
    fireEvent.keyDown(window, { key: 'z', code: 'KeyZ', ctrlKey: true });
    expect(useWorkspace.getState().workspaces[0].layout).toEqual(DEFAULT_LAYOUT);
  });
});
```

- [ ] **Step 11: Rewrite `market-workspace.spec.tsx`**

```tsx
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MarketPage } from '@features/market/routes/MarketPage';
import { useWorkspace } from '@shared/workspace/store';

vi.mock('@features/market/panels/BoardPanel', () => ({
  BoardPanel: ({ onSelect }: { onSelect: (row: unknown, day: number) => void }) => (
    <button type="button" data-testid="board-stub"
      onClick={() => onSelect({ symbol: 'الف', ins_code: '10', name: 'الف' }, 20261028)}>
      تابلو
    </button>
  ),
}));
vi.mock('@features/market/panels/WatchPanel', () => ({
  WatchPanel: () => <div data-testid="watch-stub">دیده‌بان</div>,
}));
vi.mock('@app/shell/SymbolSidebar', () => ({
  SymbolSidebar: ({ row, symbolKey }: { row: { symbol: string } | null; symbolKey: string | null }) => (
    <div data-testid="sidebar-stub">{row?.symbol ?? symbolKey ?? 'خالی'}</div>
  ),
}));
vi.mock('@app/shell/BottomDock', () => ({
  BottomDock: ({ symbol }: { symbol: string | null }) => (
    <div data-testid="dock-stub">{symbol ?? 'خالی'}</div>
  ),
}));
vi.mock('@features/market/components/SnapshotStrip', () => ({
  SnapshotStrip: () => <div data-testid="strip-stub" />,
}));
vi.mock('@features/market/api/useBoard', () => ({
  useBoard: () => ({
    data: { data: [{ symbol: 'الف', ins_code: '10', name: 'الف' }], meta: { d_even: 20261028 } },
    isLoading: false, isError: false,
  }),
}));
vi.mock('@features/market/api/useMarketSnapshot', () => ({
  useMarketSnapshot: () => ({ data: undefined, isLoading: false, isError: false }),
}));

beforeEach(() => {
  localStorage.clear();
  useWorkspace.setState(useWorkspace.getInitialState(), true);
});

afterEach(cleanup);

describe('market workspace', () => {
  it('renders the board, watch, sidebar and dock', () => {
    render(<MarketPage />);
    expect(screen.getByTestId('board-stub')).toBeTruthy();
    expect(screen.getByTestId('watch-stub')).toBeTruthy();
    expect(screen.getByTestId('sidebar-stub')).toBeTruthy();
    expect(screen.getByTestId('dock-stub')).toBeTruthy();
    expect(screen.getByTestId('strip-stub')).toBeTruthy();
    expect(screen.queryByText('نماد')).toBeNull();
  });

  it('feeds the active row to the sidebar and the dock without navigating', () => {
    render(<MarketPage />);
    fireEvent.click(screen.getByTestId('board-stub'));
    expect(useWorkspace.getState().activeSymbol).toBe('10');
    expect(screen.getByTestId('sidebar-stub').textContent).toBe('الف');
    expect(screen.getByTestId('dock-stub').textContent).toBe('الف');
  });

  it('closes the watch tile and adds it back from the board menu', () => {
    render(<MarketPage />);
    fireEvent.click(screen.getByTestId('tile-close-t-watch'));
    expect(screen.queryByTestId('watch-stub')).toBeNull();
    fireEvent.click(screen.getByTestId('tile-menu-t-board'));
    fireEvent.click(screen.getByTestId('tile-add-watch'));
    expect(screen.getByTestId('watch-stub')).toBeTruthy();
  });
});
```

- [ ] **Step 12: Bring the `workspace-store.spec.ts` action tests onto the two-pane layout**

`findTile` را کنارِ ایمپورت‌های موجود اضافه کن:

```ts
import { DEFAULT_LAYOUT, findTile } from '@shared/workspace/layout';
```

این دو تست را جایگزینِ تست‌های فعلیِ «splits, closes and swaps» و «resets» کن:

```ts
it('closes, splits and swaps through actions', () => {
  const store = useWorkspace.getState();
  store.close('t-watch');
  expect(JSON.stringify(useWorkspace.getState().workspaces[0].layout)).not.toContain('"watch"');
  store.split('t-board', 'col', 'watch');
  expect(findTile(useWorkspace.getState().workspaces[0].layout, 't-watch')).not.toBeNull();
  store.swap('t-board', 'left');
  const root = useWorkspace.getState().workspaces[0].layout;
  expect(findTile(root, 't-board')?.panel).toBe('watch');
  expect(useWorkspace.getState().history).toHaveLength(3);
});

it('resets to the default layout', () => {
  useWorkspace.getState().close('t-watch');
  useWorkspace.getState().resetLayout();
  expect(useWorkspace.getState().workspaces[0].layout).toEqual(DEFAULT_LAYOUT);
});
```

سپس تستِ مهاجرت را اضافه کن:

```ts
it('converts a stored symbol layout to the two-pane default on rehydrate', async () => {
  localStorage.setItem('bors-workspace-v1', JSON.stringify({
    version: 1,
    state: {
      version: 1,
      activeWorkspaceId: 'ws-tablo',
      activeSymbol: '10',
      pinned: {},
      workspaces: [{
        id: 'ws-tablo', name: 'تابلوخوانی', slots: DEFAULT_SLOTS, chartOpen: true, updatedAt: 1,
        layout: {
          kind: 'split', id: 's-root', dir: 'row', ratio: 0.68,
          first: { kind: 'tile', id: 't-board', panel: 'board', follow: false },
          second: { kind: 'tile', id: 't-symbol', panel: 'symbol', follow: true },
        },
      }],
    },
  }));
  await useWorkspace.persist.rehydrate();
  expect(useWorkspace.getState().workspaces[0].layout).toEqual(DEFAULT_LAYOUT);
  expect(useWorkspace.getState().activeSymbol).toBe('10');
  expect(useWorkspace.getState().workspaces[0].sideWidth).toBe(320);
});
```

- [ ] **Step 13: Update `board-views-export.spec.tsx`**

Add the import and the two hook mocks beside the existing mocks:

```tsx
import { useWorkspace } from '@shared/workspace/store';

vi.mock('@features/market/api/useMa', async (original) => {
  const mod = await original<typeof import('@features/market/api/useMa')>();
  return { ...mod, useMa: () => ({ data: undefined, isLoading: false, isError: true, error: new Error('x') }) };
});
vi.mock('@features/fundamental/api/useFtsCard', async (original) => {
  const mod = await original<typeof import('@features/fundamental/api/useFtsCard')>();
  return { ...mod, useFtsCard: () => ({ data: undefined, isLoading: false, isError: true, error: new Error('x') }) };
});
```

In `beforeEach`, next to `useMarketPrefs` reset:

```tsx
  useWorkspace.setState(useWorkspace.getInitialState(), true);
```

Replace the three `tile-t-symbol` waits:

```tsx
    await waitFor(() => expect(screen.getByTestId('symbol-title')).toBeTruthy());
```

```tsx
    const sidebar = await waitFor(() => screen.getByTestId('symbol-sidebar'));
    expect(sidebar.textContent).toContain('قدیمی');
    expect(sidebar.textContent).not.toContain('تازه');
```

(The third occurrence becomes the same `symbol-title` wait as the first.)

- [ ] **Step 14: Update `board-watch-symbol.spec.tsx`**

Add the imports (و ایمپورتِ `SymbolPanel` را بردار):

```tsx
import { useFtsCard } from '@features/fundamental/api/useFtsCard';
import { useMa } from '@features/market/api/useMa';
import { SymbolSidebar } from '@app/shell/SymbolSidebar';
```

Add the mocks beside the existing ones:

```tsx
vi.mock('@features/market/api/useMa', async (original) => {
  const mod = await original<typeof import('@features/market/api/useMa')>();
  return { ...mod, useMa: () => ({ data: undefined, isLoading: false, isError: true, error: new Error('x') }) };
});
vi.mock('@features/fundamental/api/useFtsCard', async (original) => {
  const mod = await original<typeof import('@features/fundamental/api/useFtsCard')>();
  return { ...mod, useFtsCard: () => ({ data: undefined, isLoading: false, isError: true, error: new Error('x') }) };
});
```

Replace both `SymbolPanel` mounts with:

```tsx
    render(withClient(
      <SymbolSidebar
        row={row()}
        symbolKey="1"
        boardDay={null}
        chartOpen={false}
        fundamentalsOpen
        onToggleChart={() => undefined}
        onToggleFundamentals={() => undefined}
      />,
    ));
```

In the workflow test, replace the two fundamental-tab lines with:

```tsx
    expect(screen.getByTestId('symbol-fund-summary')).toBeTruthy();
    expect(screen.getByTestId('symbol-fund-unavailable').textContent).toContain('در دسترس نیست');
```

Keep the history-tab assertion (`symbol-tab-history`) and the two watchlist role assertions unchanged.

- [ ] **Step 15: Run the affected tests**

```bash
cd frontend-v2
npx vitest run src/__tests__/workspace-layout.spec.ts src/__tests__/workspace-shell.spec.tsx src/__tests__/workspace-keyboard.spec.tsx src/__tests__/workspace-store.spec.ts src/__tests__/market-workspace.spec.tsx src/__tests__/market-page.spec.tsx src/__tests__/board-views-export.spec.tsx src/__tests__/board-watch-symbol.spec.tsx
npx tsc -b
```

Expected: همه PASS؛ tsc صفر خطا.

- [ ] **Step 16: Run the full suite**

```bash
npx vitest run
```

Expected: همهٔ پرونده‌ها سبز (تعدادِ نهایی در گزارشِ تسک ثبت می‌شود).

- [ ] **Step 17: Commit**

```bash
cd /c/Users/PCMOD/Desktop/BorsTerminal
git add frontend-v2/src/shared/workspace/types.ts frontend-v2/src/shared/workspace/layout.ts \
  frontend-v2/src/shared/workspace/TileFrame.tsx frontend-v2/src/shared/workspace/WorkspaceShell.tsx \
  frontend-v2/src/shared/workspace/shortcuts.ts frontend-v2/src/features/market/routes/MarketPage.tsx \
  frontend-v2/src/features/market/panels/SymbolPanel.tsx frontend-v2/src/__tests__/symbol-panel.spec.tsx \
  frontend-v2/src/__tests__/workspace-layout.spec.ts frontend-v2/src/__tests__/workspace-shell.spec.tsx \
  frontend-v2/src/__tests__/workspace-keyboard.spec.tsx frontend-v2/src/__tests__/workspace-store.spec.ts \
  frontend-v2/src/__tests__/market-workspace.spec.tsx frontend-v2/src/__tests__/board-views-export.spec.tsx \
  frontend-v2/src/__tests__/board-watch-symbol.spec.tsx
git commit -m "$(cat <<'EOF'
feat(market): میزکارِ سه‌ناحیه‌ای و حذفِ کاشیِ نماد
EOF
)"
```

---

## Task 10: راستی‌آزماییِ زنده و مدرک

**Files:**
- Create: `_audit/live-board-v2-20261028/dossier-check.mjs`
- Output (کامیت می‌شود): `_audit/live-board-v2-20261028/dossier-check.json`
- Output (gitignored): `_audit/live-board-v2-20261028/ws-1366-dossier.png`، `ws-1920-dossier.png`، `ws-2560-dossier.png`، `ws-1279-dossier.png`

**Interfaces:**
- Consumes: Vite روی `127.0.0.1:5180` با پروکسی به بک‌اندِ `127.0.0.1:8101`
- Produces: گزارشِ JSON با `checks[]` و `console[]`

- [ ] **Step 1: Confirm the servers**

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8101/api/market
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5180/
```

هر دو باید `200` بدهند. اگر بک‌اند خاموش بود (بدونِ نوشتن روی بانکِ عملیاتی):

```bash
cd /c/Users/PCMOD/Desktop/BorsTerminal
BORS_NO_FETCH_LOOPS=1 python -m uvicorn app:app --host 127.0.0.1 --port 8101
```

اگر Vite خاموش بود:

```bash
cd frontend-v2
BORS_BACKEND=http://127.0.0.1:8101 npx vite --port 5180 --strictPort
```

فقط PIDهایی که خودت بالا آورده‌ای در پایان بسته می‌شوند.

- [ ] **Step 2: Write the harness**

```js
import { writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const PW = 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package/node_modules/playwright/index.mjs';
const CHROME = 'C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const { chromium } = await import(pathToFileURL(PW).href);

const OUT = dirname(fileURLToPath(import.meta.url));
const BASE = 'http://127.0.0.1:5180/';
const report = { base: BASE, route: '#/market', checks: [], console: [], shots: [], started: new Date().toISOString() };

function record(name, ok, detail) {
  report.checks.push({ name, ok: Boolean(ok), detail });
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${ok ? '' : ` ${JSON.stringify(detail)}`}`);
}

async function shot(page, name) {
  const path = join(OUT, name);
  await page.screenshot({ path, fullPage: false });
  report.shots.push(path);
}

const browser = await chromium.launch({ executablePath: CHROME, headless: true });
const context = await browser.newContext({ viewport: { width: 1366, height: 768 } });
const consoleErrors = [];
const page = await context.newPage();
page.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
page.on('pageerror', (error) => consoleErrors.push(String(error)));

try {
  await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="board-row"]', { timeout: 40_000 });
  await page.waitForSelector('[data-testid="snapshot-strip"]', { timeout: 20_000 });
  await page.waitForTimeout(1000);

  const sidebarCount = await page.locator('[data-testid="symbol-sidebar"]').count();
  const dockCount = await page.locator('[data-testid="bottom-dock"]').count();
  const watchTiles = await page.locator('[data-testid="tile-t-watch"]').count();
  const symbolTiles = await page.locator('[data-testid="tile-t-symbol"]').count();
  const chartTiles = await page.locator('[data-testid="tile-t-chart"]').count();
  record('left sidebar and bottom dock exist and the symbol/chart tiles are gone',
    sidebarCount === 1 && dockCount === 1 && watchTiles === 1 && symbolTiles === 0 && chartTiles === 0,
    { sidebarCount, dockCount, watchTiles, symbolTiles, chartTiles });

  await page.click('[data-testid="board-row"]');
  await page.waitForSelector('[data-testid="symbol-title"]', { timeout: 20_000 });
  await page.waitForTimeout(700);
  const title = await page.locator('[data-testid="symbol-title"]').innerText();
  const price = await page.locator('[data-testid="symbol-price"]').innerText();
  const stats = await page.locator('[data-testid^="symbol-stat-"]').count();
  const chips = await page.locator('[data-testid^="symbol-tape-"]').count();
  record('sidebar shows the symbol at a glance: price, six stats and seven tape chips',
    title.length > 0 && price.length > 0 && stats === 6 && chips === 7,
    { title, price, stats, chips });

  await page.waitForFunction(
    () => !document.querySelector('[data-testid="tech-loading"]'),
    null,
    { timeout: 25_000 },
  ).catch(() => null);
  await page.waitForFunction(() => {
    const node = document.querySelector('[data-testid="symbol-fund-summary"]');
    return node && (node.textContent.includes('محور قبول') || node.textContent.includes('در دسترس نیست'));
  }, null, { timeout: 25_000 }).catch(() => null);
  const tech = await page.locator('[data-testid="symbol-tech"], [data-testid="tech-unavailable"]').count();
  const techTrend = await page.locator('[data-testid="tech-trend"], [data-testid="tech-trend-unknown"]').count();
  const fund = await page.locator('[data-testid="symbol-fund-summary"]').innerText();
  record('technical and fundamental summaries render with honest fallbacks',
    tech === 1 && techTrend === 1 && (fund.includes('محور قبول') || fund.includes('در دسترس نیست')),
    { tech, techTrend, fund: fund.slice(0, 160) });

  await page.waitForSelector('[data-testid="chart-panel"]', { timeout: 20_000 }).catch(() => null);
  await page.waitForSelector('[data-testid="fundamental-card-1_growth"], [data-testid="fundamental-error"]', { timeout: 25_000 }).catch(() => null);
  const charts = await page.locator('[data-testid="chart-panel"]').count();
  const cards = await page.locator('[data-testid^="fundamental-card-"]').count();
  const cardErrors = await page.locator('[data-testid="fundamental-error"]').count();
  record('bottom dock holds one chart and the five fundamental cards (or their honest error)',
    charts === 1 && (cards === 5 || cardErrors === 1), { charts, cards, cardErrors });
  await shot(page, 'ws-1366-dossier.png');

  for (const [width, height, name] of [[1920, 1080, 'ws-1920-dossier.png'], [2560, 1440, 'ws-2560-dossier.png']]) {
    await page.setViewportSize({ width, height });
    await page.waitForTimeout(600);
    await shot(page, name);
  }
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.waitForTimeout(500);

  const sideBefore = await page.locator('[data-testid="symbol-sidebar"]').boundingBox();
  const sideSep = await page.locator('[data-testid="resize-sidebar"]').boundingBox();
  if (sideBefore && sideSep) {
    await page.mouse.move(sideSep.x + 1, sideSep.y + 20);
    await page.mouse.down();
    await page.mouse.move(sideSep.x + 49, sideSep.y + 20, { steps: 8 });
    await page.mouse.up();
    await page.waitForTimeout(300);
    const sideAfter = await page.locator('[data-testid="symbol-sidebar"]').boundingBox();
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForSelector('[data-testid="symbol-title"]', { timeout: 40_000 });
    await page.waitForTimeout(900);
    const sideReload = await page.locator('[data-testid="symbol-sidebar"]').boundingBox();
    const drift = sideAfter && sideReload ? Math.abs(sideAfter.width - sideReload.width) : 99;
    record('sidebar resize widens the column and survives reload',
      sideAfter != null && sideAfter.width > sideBefore.width + 20 && drift <= 2,
      { before: sideBefore.width, after: sideAfter?.width, reload: sideReload?.width });
  } else {
    record('sidebar resize widens the column and survives reload', false, { sideBefore, sideSep });
  }

  const dockBefore = await page.locator('[data-testid="bottom-dock"]').boundingBox();
  const dockSep = await page.locator('[data-testid="resize-dock"]').boundingBox();
  if (dockBefore && dockSep) {
    await page.mouse.move(dockSep.x + 40, dockSep.y + 1);
    await page.mouse.down();
    await page.mouse.move(dockSep.x + 40, dockSep.y - 49, { steps: 8 });
    await page.mouse.up();
    await page.waitForTimeout(300);
    const dockAfter = await page.locator('[data-testid="bottom-dock"]').boundingBox();
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForSelector('[data-testid="bottom-dock"]', { timeout: 40_000 });
    await page.waitForTimeout(900);
    const dockReload = await page.locator('[data-testid="bottom-dock"]').boundingBox();
    const drift = dockAfter && dockReload ? Math.abs(dockAfter.height - dockReload.height) : 99;
    record('dock resize grows the panel and survives reload',
      dockAfter != null && dockAfter.height > dockBefore.height + 20 && drift <= 2,
      { before: dockBefore.height, after: dockAfter?.height, reload: dockReload?.height });
  } else {
    record('dock resize grows the panel and survives reload', false, { dockBefore, dockSep });
  }

  await page.click('[data-testid="dock-toggle-fundamental"]');
  await page.waitForTimeout(300);
  const cardsOff = await page.locator('[data-testid="dock-fundamentals"]').count();
  const chartStays = await page.locator('[data-testid="chart-panel"]').count();
  await page.click('[data-testid="dock-toggle-fundamental"]');
  await page.waitForTimeout(300);
  const cardsOn = await page.locator('[data-testid="dock-fundamentals"]').count();
  await page.click('[data-testid="dock-toggle-chart"]');
  await page.waitForTimeout(300);
  const chartOff = await page.locator('[data-testid="dock-chart"]').count();
  const cardsStill = await page.locator('[data-testid="dock-fundamentals"]').count();
  await page.click('[data-testid="dock-toggle-chart"]');
  await page.waitForTimeout(300);
  record('each dock toggle hides only its own group',
    cardsOff === 0 && chartStays === 1 && cardsOn === 1 && chartOff === 0 && cardsStill === 1,
    { cardsOff, chartStays, cardsOn, chartOff, cardsStill });

  await page.click('[data-testid="tile-close-t-watch"]');
  await page.waitForTimeout(200);
  const closed = await page.locator('[data-testid="tile-t-watch"]').count();
  await page.keyboard.press('Control+z');
  await page.waitForTimeout(300);
  const restored = await page.locator('[data-testid="tile-t-watch"]').count();
  record('closing the watch tile is undone with Ctrl+Z', closed === 0 && restored === 1, { closed, restored });

  await page.setViewportSize({ width: 1279, height: 800 });
  await page.waitForTimeout(700);
  const narrowTabs = await page.locator('[data-testid="narrow-tab-symbol"]').count();
  const wideSidebar = await page.locator('[data-testid="symbol-sidebar"][data-variant="wide"]').count();
  const narrowDock = await page.locator('[data-testid="bottom-dock"]').count();
  await page.click('[data-testid="narrow-tab-symbol"]');
  await page.waitForTimeout(500);
  const narrowSidebar = await page.locator('[data-testid="symbol-sidebar"][data-variant="narrow"]').count();
  await shot(page, 'ws-1279-dossier.png');
  record('narrow width drops the wide sidebar and dock and uses the narrow sidebar',
    narrowTabs === 1 && wideSidebar === 0 && narrowDock === 0 && narrowSidebar === 1,
    { narrowTabs, wideSidebar, narrowDock, narrowSidebar });

  await page.setViewportSize({ width: 1366, height: 768 });
  await page.waitForTimeout(700);
  const backSidebar = await page.locator('[data-testid="symbol-sidebar"][data-variant="wide"]').count();
  const backDock = await page.locator('[data-testid="bottom-dock"]').count();
  record('returning to wide restores the saved sidebar and dock', backSidebar === 1 && backDock === 1,
    { backSidebar, backDock });

  record('no console errors', consoleErrors.length === 0, { consoleErrors: consoleErrors.slice(0, 6) });
} catch (error) {
  record('harness completed', false, { error: String(error) });
} finally {
  report.console = consoleErrors;
  report.finished = new Date().toISOString();
  writeFileSync(join(OUT, 'dossier-check.json'), JSON.stringify(report, null, 2), 'utf8');
  await browser.close();
}
```

- [ ] **Step 3: Run the harness**

```bash
cd /c/Users/PCMOD/Desktop/BorsTerminal
node _audit/live-board-v2-20261028/dossier-check.mjs
```

Expected: همهٔ بندها `PASS`، `console` خالی.

اگر بندی `FAIL` شد، ابتدا علت را از `dossier-check.json` و اسکرین‌شات بخوان و همان نقص را در کدِ همان تسک برطرف کن؛ سنجه را ضعیف نکن.

- [ ] **Step 4: Read the numbers and hand the screenshots to the owner**

فایل `dossier-check.json` را بخوان و در گزارشِ نهایی این‌ها را عیناً بیاور: عرضِ سایدبار قبل/بعد/reload، ارتفاعِ داک قبل/بعد/reload، تعدادِ چیپ‌ها، تعدادِ کارت‌ها، و وضعیتِ تکنیکال/بنیادی. اسکرین‌شات‌های ۱۳۶۶/۱۹۲۰/۲۵۶۰/۱۲۷۹ را معرفی کن؛ PASS بصری فقط با رأیِ مالک.

- [ ] **Step 5: Commit and push the mission branch**

```bash
git add _audit/live-board-v2-20261028/dossier-check.mjs _audit/live-board-v2-20261028/dossier-check.json
git commit -m "$(cat <<'EOF'
test(market): راستی‌آزماییِ زندهٔ میزکارِ نماد
EOF
)"
git push github mission/4-axes-2026-10-10
```

---

## خودبازبینیِ نقشه

- پوششِ سند: سایدبارِ چپ (§۴) = Task 7؛ داکِ پایین (§۵) = Task 8؛ میزکارِ دوپنلی (§۶) = Task 9؛ حالتِ باریک (§۷) = Task 9؛ اندازه‌ها و مهاجرت (§۹) = Task 6 + Task 9؛ الهامِ چهار برنامه (§۲) = نوارِ فشار (Task 4)، آمارِ Koyfin (Task 4)، مرزِ Kraken (Task 8)، ماندگاری/دابل‌کلیکِ Quantower (Task 1) و نشانِ «پیروِ تابلو» (Task 4).
- هیچ `TBD` یا گامِ بدونِ کد نمانده است.
- نام‌ها یکدست‌اند: `symbol-fund-summary`، `dock-toggle-fundamental`، `resize-sidebar|dock|chart`، `symbol-tape-{key}`، `fund-summary-count`.
- فقط `ChartPanel` یک نمونه در هر لحظه mount می‌شود (شرطِ `variant` و `narrow` در `MarketPage`).
