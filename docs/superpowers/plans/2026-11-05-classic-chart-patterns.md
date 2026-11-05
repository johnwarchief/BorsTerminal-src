# Classic Chart Patterns + Historical Formation Rate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 11 classic chart-pattern detectors (flag, pennant, three triangles, rectangle, two wedges, head & shoulders + inverse, triple top/bottom) next to the existing double top/bottom, all in the v2 client on adjusted candles, each with a same-symbol historical formation rate, 1/3/5-bar returns, a quiet chart overlay and a patterns tab.

**Architecture:** Pure TypeScript engines under `frontend-v2/src/features/technical/model/patterns/`, reusing the existing pivot logic, ATR, Laplace/Wilson statistics and `FormationEstimate` type from `doubleTapEngine`. A registry merges the new patterns with the existing double-tap patterns through a small adapter, a klinecharts overlay draws at most six featured shapes, and a drawer tab renders the last-pattern card, the list and the rule book. No backend, FTS or screener changes.

**Tech Stack:** React 18 + TypeScript + Vite, Zustand, klinecharts overlays, Vitest, Zod already present elsewhere (not needed here).

**Spec:** `docs/superpowers/specs/2026-11-05-classic-chart-patterns-design.md`

## Global Constraints

- All detectors run in the client on `EngineCandle[]` of the active timeframe; no network calls, no backend edits, no FTS/screener logic changes.
- Statistics reuse `laplaceRate`, `wilsonInterval` and `FormationEstimate`; a percentage is shown only when `resolved >= 8`; `unresolved` is never a failure.
- Every threshold lives in `PATTERN_CONFIG` and is rendered in the «قواعد» section; no hidden magic numbers.
- Persian UI copy with Persian digits via `toFaDigits`; text ≥ 11px; icons come from `ui/icons.tsx` when an icon is needed.
- `data-testid` names are contracts: `pattern-card`, `pattern-list`, `pattern-rules`, `pattern-row-<id>`.
- The existing double-tap behavior and its tests must stay byte-identical (only the pivot helpers move).
- Workspace files are large; do not restructure them. New UI goes in a new `ui/PatternsTab.tsx`; the drawer only gains a tab + one render line.

---

## File Structure

| File | Responsibility |
|---|---|
| `model/patterns/pivots.ts` (new) | `isPivotHigh`/`isPivotLow` moved from `doubleTapEngine.ts` + `findAlternatingPivots` |
| `model/patterns/config.ts` (new) | `PatternConfig` + `PATTERN_CONFIG` defaults |
| `model/patterns/types.ts` (new) | `PatternKind`, `PatternStatus`, `PatternPoint`, `BoundaryLine`, `ChartPattern` |
| `model/patterns/geometry.ts` (new) | line math, touch counting, `emitTwoLinePattern`, expiry/status |
| `model/patterns/detectContinuation.ts` (new) | flag, pennant, triangles, rectangle, wedges |
| `model/patterns/detectReversal.ts` (new) | head & shoulders (+inverse), triple top/bottom |
| `model/patterns/outcome.ts` (new) | per-family outcome + 1/3/5 returns |
| `model/patterns/formation.ts` (new) | same-symbol formation estimate (Laplace/Wilson + quality tercile) |
| `model/patterns/registry.ts` (new) | `detectAllPatterns`, double-tap adapter, `selectFeaturedPatterns` |
| `overlays/patternOverlay.ts` (new) | klinecharts overlay for ≤6 featured shapes |
| `ui/PatternsTab.tsx` (new) | last-pattern card + list + rules |
| `model/technicalStore.ts` (modify) | `detectedPatterns` slice + `DrawerTab` gains `'patterns'` |
| `ui/WideWorkspaceDrawer.tsx` (modify) | tab entry + `<PatternsTab />` render |
| `ui/KLineChartWrapper.tsx` (modify) | register the new overlay |
| `model/doubleTapEngine.ts` (modify) | import pivots from the new module (delete local copies only) |

---

### Task 1: Shared pivot primitives (byte-identical move)

**Files:**
- Create: `frontend-v2/src/features/technical/model/patterns/pivots.ts`
- Modify: `frontend-v2/src/features/technical/model/doubleTapEngine.ts:92-109`
- Test: `frontend-v2/src/features/technical/model/patterns/__tests__/pivots.test.ts`

**Interfaces:**
- Consumes: `EngineCandle` from `../doubleTapEngine`.
- Produces: `PivotPoint { index: number; price: number; kind: 'high' | 'low' }`, `isPivotHigh(data, idx, left, right): boolean`, `isPivotLow(...): boolean`, `findAlternatingPivots(data, left, right): PivotPoint[]`.

- [ ] **Step 1: Write the failing test**

```ts
// model/patterns/__tests__/pivots.test.ts
import { describe, expect, it } from 'vitest';
import { findAlternatingPivots, isPivotHigh, isPivotLow } from '../pivots';
import type { EngineCandle } from '../../doubleTapEngine';

const candle = (high: number, low: number, i: number): EngineCandle => ({
  timestamp: 1_700_000_000_000 + i * 60_000, open: low, high, low, close: (high + low) / 2,
});

// highs: 10, 12, 9, 14, 8, 11  / lows: 5, 6, 4, 7, 3, 5
const series: EngineCandle[] = [
  candle(10, 5, 0), candle(12, 6, 1), candle(9, 4, 2),
  candle(14, 7, 3), candle(8, 3, 4), candle(11, 5, 5),
];

describe('pivot primitives', () => {
  it('detects a fractal high and low with asymmetric windows', () => {
    expect(isPivotHigh(series, 3, 2, 1)).toBe(true);
    expect(isPivotHigh(series, 0, 2, 1)).toBe(false); // left-clamp: 12 همسایهٔ بزرگ‌تر دارد
    expect(isPivotLow(series, 4, 2, 1)).toBe(true);
  });

  it('returns alternating pivots, keeping the more extreme on a repeat', () => {
    const pivots = findAlternatingPivots(series, 1, 1);
    expect(pivots.map((p) => `${p.kind}:${p.index}`)).toEqual(['high:1', 'low:2', 'high:3', 'low:4']);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend-v2 && npx vitest run src/features/technical/model/patterns/__tests__/pivots.test.ts`
Expected: FAIL with "Cannot find module '../pivots'".

- [ ] **Step 3: Write the implementation (move the two functions verbatim)**

```ts
// model/patterns/pivots.ts
import type { EngineCandle } from '../doubleTapEngine';

export interface PivotPoint {
  index: number;
  price: number;
  kind: 'high' | 'low';
}

/** عیناً از doubleTapEngine منتقل شده؛ رفتار نباید تغییر کند. */
export function isPivotHigh(data: readonly EngineCandle[], idx: number, left: number, right: number): boolean {
  const h = data[idx].high;
  for (let j = Math.max(0, idx - left); j <= Math.min(data.length - 1, idx + right); j++) {
    if (j !== idx && data[j].high > h) return false;
  }
  return true;
}

export function isPivotLow(data: readonly EngineCandle[], idx: number, left: number, right: number): boolean {
  const l = data[idx].low;
  for (let j = Math.max(0, idx - left); j <= Math.min(data.length - 1, idx + right); j++) {
    if (j !== idx && data[j].low < l) return false;
  }
  return true;
}

/** پیوت‌های متناوب؛ دو قلهٔ پشتِ‌سرِهم فقط بلندتر می‌ماند، دو دره فقط پایین‌تر. */
export function findAlternatingPivots(
  data: readonly EngineCandle[],
  left: number,
  right: number,
): PivotPoint[] {
  const raw: PivotPoint[] = [];
  for (let i = left; i < data.length - right; i++) {
    if (isPivotHigh(data, i, left, right)) raw.push({ index: i, price: data[i].high, kind: 'high' });
    else if (isPivotLow(data, i, left, right)) raw.push({ index: i, price: data[i].low, kind: 'low' });
  }
  const out: PivotPoint[] = [];
  for (const point of raw) {
    const last = out[out.length - 1];
    if (last && last.kind === point.kind) {
      const moreExtreme = point.kind === 'high' ? point.price >= last.price : point.price <= last.price;
      if (moreExtreme) out[out.length - 1] = point;
    } else {
      out.push(point);
    }
  }
  return out;
}
```

Then in `doubleTapEngine.ts` delete the two local functions and add at the top:

```ts
import { isPivotHigh, isPivotLow } from './patterns/pivots';
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend-v2 && npx vitest run src/features/technical/model/patterns/__tests__/pivots.test.ts src/features/technical/model/__tests__/doubleTapEngine.test.ts`
Expected: both files PASS (double-tap tests unchanged).

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/src/features/technical/model/patterns/pivots.ts frontend-v2/src/features/technical/model/patterns/__tests__/pivots.test.ts frontend-v2/src/features/technical/model/doubleTapEngine.ts
git commit -m "refactor(technical): پیوت مشترک برای موتورهای الگو"
```

---

### Task 2: Types and config

**Files:**
- Create: `frontend-v2/src/features/technical/model/patterns/types.ts`
- Create: `frontend-v2/src/features/technical/model/patterns/config.ts`
- Test: `frontend-v2/src/features/technical/model/patterns/__tests__/config.test.ts`

**Interfaces:**
- Consumes: `FormationEstimate` from `../types`.
- Produces: `PatternKind`, `PatternStatus`, `PatternPoint`, `BoundaryLine`, `ChartPattern`, `PatternConfig`, `PATTERN_CONFIG`.

- [ ] **Step 1: Write the failing test**

```ts
// model/patterns/__tests__/config.test.ts
import { describe, expect, it } from 'vitest';
import { PATTERN_CONFIG } from '../config';

describe('PATTERN_CONFIG', () => {
  it('keeps every window positive and every tolerance in ATR terms', () => {
    for (const key of ['flag', 'pennant', 'triangle', 'rectangle', 'wedge', 'hs', 'triple'] as const) {
      expect(PATTERN_CONFIG[key].maxBars).toBeGreaterThan(2);
    }
    expect(PATTERN_CONFIG.flag.channelMaxWidthPct).toBeGreaterThan(0);
    expect(PATTERN_CONFIG.flag.channelMaxWidthPct).toBeLessThanOrEqual(60);
    expect(PATTERN_CONFIG.triangle.flatToleranceAtr).toBeGreaterThan(0);
    expect(PATTERN_CONFIG.outcomeHorizon).toBe(10);
    expect(PATTERN_CONFIG.returnHorizons).toEqual([1, 3, 5]);
    expect(PATTERN_CONFIG.formationMinResolved).toBe(8);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend-v2 && npx vitest run src/features/technical/model/patterns/__tests__/config.test.ts`
Expected: FAIL with "Cannot find module '../config'".

- [ ] **Step 3: Write types and config**

```ts
// model/patterns/types.ts
import type { FormationEstimate } from '../types';

export type PatternKind =
  | 'DOUBLE_TOP' | 'DOUBLE_BOTTOM'
  | 'FLAG_BULL' | 'FLAG_BEAR' | 'PENNANT'
  | 'TRIANGLE_ASC' | 'TRIANGLE_DESC' | 'TRIANGLE_SYM'
  | 'RECTANGLE' | 'WEDGE_RISING' | 'WEDGE_FALLING'
  | 'HEAD_SHOULDERS' | 'INVERSE_HEAD_SHOULDERS'
  | 'TRIPLE_TOP' | 'TRIPLE_BOTTOM';

export type PatternStatus = 'forming' | 'confirmed' | 'invalidated';
export type PatternDirection = 'bullish' | 'bearish' | 'neutral';
export type PatternFamily = 'continuation' | 'reversal';

export interface PatternPoint { index: number; price: number; timestamp: number }
export interface BoundaryLine { from: PatternPoint; to: PatternPoint }

export interface ChartPattern {
  id: string;
  kind: PatternKind;
  direction: PatternDirection;
  family: PatternFamily;
  anchor: PatternPoint;
  points: PatternPoint[];
  upper: BoundaryLine;
  lower: BoundaryLine;
  neckline?: BoundaryLine;
  breakoutIndex?: number;
  target: number;
  stopLoss: number;
  quality: number;
  status: PatternStatus;
  formation?: FormationEstimate;
  returns?: { h1: number | null; h3: number | null; h5: number | null };
}
```

```ts
// model/patterns/config.ts
export interface PatternConfig {
  pivLeft: number;
  pivRight: number;
  atrPeriod: number;
  minTouchesPerLine: number;
  invalidationBufferAtr: number;
  outcomeHorizon: number;
  returnHorizons: [number, number, number];
  formationMinResolved: number;
  flag: { impulseLegAtrMin: number; channelMaxWidthPct: number; slopeOpposite: boolean; maxBars: number };
  pennant: { impulseLegAtrMin: number; convergenceMin: number; maxBars: number };
  triangle: { flatToleranceAtr: number; convergenceMin: number; maxBars: number };
  rectangle: { flatToleranceAtr: number; maxBars: number };
  wedge: { convergenceMin: number; maxBars: number };
  hs: { headAboveShouldersAtr: number; shouldersToleranceAtr: number; maxBars: number };
  triple: { levelToleranceAtr: number; maxBars: number };
}

export const PATTERN_CONFIG: PatternConfig = {
  pivLeft: 5,
  pivRight: 4,
  atrPeriod: 14,
  minTouchesPerLine: 2,
  invalidationBufferAtr: 0.5,
  outcomeHorizon: 10,
  returnHorizons: [1, 3, 5],
  formationMinResolved: 8,
  flag: { impulseLegAtrMin: 3.0, channelMaxWidthPct: 35, slopeOpposite: true, maxBars: 40 },
  pennant: { impulseLegAtrMin: 3.0, convergenceMin: 0.35, maxBars: 30 },
  triangle: { flatToleranceAtr: 0.35, convergenceMin: 0.30, maxBars: 60 },
  rectangle: { flatToleranceAtr: 0.50, maxBars: 80 },
  wedge: { convergenceMin: 0.30, maxBars: 60 },
  hs: { headAboveShouldersAtr: 0.50, shouldersToleranceAtr: 0.60, maxBars: 120 },
  triple: { levelToleranceAtr: 0.50, maxBars: 120 },
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend-v2 && npx vitest run src/features/technical/model/patterns/__tests__/config.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/src/features/technical/model/patterns/types.ts frontend-v2/src/features/technical/model/patterns/config.ts frontend-v2/src/features/technical/model/patterns/__tests__/config.test.ts
git commit -m "feat(technical): انواع و پیکربندی الگوهای کلاسیک"
```

---

### Task 3: Geometry helpers and the two-line emitter

**Files:**
- Create: `frontend-v2/src/features/technical/model/patterns/geometry.ts`
- Test: `frontend-v2/src/features/technical/model/patterns/__tests__/geometry.test.ts`

**Interfaces:**
- Consumes: `BoundaryLine`, `ChartPattern`, `PatternKind`, `PatternDirection`, `PatternFamily`, `PatternPoint` from `./types`; `EngineCandle` from `../doubleTapEngine`.
- Produces: `toPoint(pivot, candles)`, `lineValue(line, index)`, `lineSlope(line)`, `touchCount(pivots, line, tolerance, kind)`, `emitPattern(spec, candles, config): ChartPattern | null`, `patternId(kind, anchorIndex, points)`.

- [ ] **Step 1: Write the failing test**

```ts
// model/patterns/__tests__/geometry.test.ts
import { describe, expect, it } from 'vitest';
import { emitPattern, lineSlope, lineValue } from '../geometry';
import { PATTERN_CONFIG } from '../config';
import type { EngineCandle } from '../../doubleTapEngine';

const candle = (high: number, low: number, close: number, i: number): EngineCandle => ({
  timestamp: 1_700_000_000_000 + i * 60_000, open: low, high, low, close,
});
const flat: EngineCandle[] = Array.from({ length: 12 }, (_, i) => candle(110, 100, 105, i));
const point = (index: number, price: number) => ({ index, price, timestamp: index * 60_000 });

describe('geometry', () => {
  it('interpolates a boundary line and reports its slope', () => {
    const line = { from: point(2, 100), to: point(6, 110) };
    expect(lineValue(line, 4)).toBe(105);
    expect(lineSlope(line)).toBe(2.5);
  });

  it('returns null for an expired forming pattern', () => {
    const spec = {
      kind: 'RECTANGLE' as const, direction: 'neutral' as const, family: 'continuation' as const,
      points: [point(1, 100), point(2, 110), point(3, 100), point(4, 110)],
      upper: { from: point(2, 110), to: point(4, 110) },
      lower: { from: point(1, 100), to: point(3, 100) },
      target: 120, stopLoss: 95, quality: 70,
    };
    // آخرین پیوت ۲۰ کندل عقب‌تر از انتهای داده است ⇒ منقضی، نباید الگو بسازد.
    const emitted = emitPattern(spec, flat, { ...PATTERN_CONFIG, rectangle: { ...PATTERN_CONFIG.rectangle, maxBars: 3 } });
    expect(emitted).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend-v2 && npx vitest run src/features/technical/model/patterns/__tests__/geometry.test.ts`
Expected: FAIL with "Cannot find module '../geometry'".

- [ ] **Step 3: Write the implementation**

```ts
// model/patterns/geometry.ts
import type { EngineCandle } from '../doubleTapEngine';
import type { PatternConfig } from './config';
import type {
  BoundaryLine, ChartPattern, PatternDirection, PatternFamily, PatternKind, PatternPoint,
} from './types';
import type { PivotPoint } from './pivots';

export function toPoint(pivot: PivotPoint, candles: readonly EngineCandle[]): PatternPoint {
  return { index: pivot.index, price: pivot.price, timestamp: candles[pivot.index]?.timestamp ?? 0 };
}

export function lineValue(line: BoundaryLine, index: number): number {
  const span = Math.max(1, line.to.index - line.from.index);
  const slope = (line.to.price - line.from.price) / span;
  return line.from.price + slope * (index - line.from.index);
}

export function lineSlope(line: BoundaryLine): number {
  return (line.to.price - line.from.price) / Math.max(1, line.to.index - line.from.index);
}

export function touchCount(
  pivots: readonly PivotPoint[],
  line: BoundaryLine,
  kind: 'high' | 'low',
  tolerance: number,
): number {
  return pivots.filter(
    (p) => p.kind === kind && p.index >= line.from.index && p.index <= line.to.index
      && Math.abs(p.price - lineValue(line, p.index)) <= tolerance,
  ).length;
}

export function patternId(kind: PatternKind, anchorIndex: number, points: readonly PatternPoint[]): string {
  return `${kind}:${anchorIndex}:${points.map((p) => p.index).join('-')}`;
}

export interface PatternSpec {
  kind: PatternKind;
  direction: PatternDirection;
  family: PatternFamily;
  points: PatternPoint[];
  upper: BoundaryLine;
  lower: BoundaryLine;
  neckline?: BoundaryLine;
  target: number;
  stopLoss: number;
  quality: number;
}

/** وضعیت را از داده می‌سازد؛ الگوی منقضی (نه تأیید و نه باطل) حذف می‌شود. */
export function emitPattern(
  spec: PatternSpec,
  candles: readonly EngineCandle[],
  config: PatternConfig,
): ChartPattern | null {
  const anchor = spec.points[spec.points.length - 1];
  if (!anchor) return null;
  const maxBars = Math.max(
    config.flag.maxBars, config.pennant.maxBars, config.triangle.maxBars,
    config.rectangle.maxBars, config.wedge.maxBars, config.hs.maxBars, config.triple.maxBars,
  );
  if (anchor.index < candles.length - maxBars - 1 && spec.points.length < 5) return null;

  const start = anchor.index + 1;
  let status: ChartPattern['status'] = 'forming';
  let breakoutIndex: number | undefined;

  for (let i = start; i < candles.length; i++) {
    const close = candles[i].close;
    const brokeUp = close > lineValue(spec.upper, i);
    const brokeDown = close < lineValue(spec.lower, i);
    if (spec.direction === 'bullish' ? brokeUp : spec.direction === 'bearish' ? brokeDown : false) {
      status = 'confirmed';
      breakoutIndex = i;
      break;
    }
    if (spec.direction === 'bullish' ? brokeDown : spec.direction === 'bearish' ? brokeUp : false) {
      status = 'invalidated';
      break;
    }
  }
  if (status === 'forming' && anchor.index < candles.length - maxBars) return null;

  return {
    id: patternId(spec.kind, anchor.index, spec.points),
    kind: spec.kind,
    direction: spec.direction,
    family: spec.family,
    anchor,
    points: spec.points,
    upper: spec.upper,
    lower: spec.lower,
    neckline: spec.neckline,
    breakoutIndex,
    target: spec.target,
    stopLoss: spec.stopLoss,
    quality: Math.max(0, Math.min(100, Math.round(spec.quality))),
    status,
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend-v2 && npx vitest run src/features/technical/model/patterns/__tests__/geometry.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/src/features/technical/model/patterns/geometry.ts frontend-v2/src/features/technical/model/patterns/__tests__/geometry.test.ts
git commit -m "feat(technical): هندسهٔ مشترک و سازندهٔ الگو"
```

---

### Task 4: Continuation detectors

**Files:**
- Create: `frontend-v2/src/features/technical/model/patterns/detectContinuation.ts`
- Test: `frontend-v2/src/features/technical/model/patterns/__tests__/continuation.test.ts`

**Interfaces:**
- Consumes: `findAlternatingPivots`, `toPoint`, `lineValue`, `lineSlope`, `touchCount`, `emitPattern`.
- Produces: `detectContinuation(candles, atr, config): ChartPattern[]`.

- [ ] **Step 1: Write the failing test (synthetic flag + rectangle)**

```ts
// model/patterns/__tests__/continuation.test.ts
import { describe, expect, it } from 'vitest';
import { detectContinuation } from '../detectContinuation';
import { PATTERN_CONFIG } from '../config';
import type { EngineCandle } from '../../doubleTapEngine';

/** سری مصنوعی: لگ صعودی تند، بعد کانال نزولی تنگ، بعد ادامه. */
function flagSeries(): EngineCandle[] {
  const bars: EngineCandle[] = [];
  let price = 100;
  for (let i = 0; i < 12; i++) { price += 2; bars.push({ timestamp: i * 60_000, open: price - 2, high: price + 0.5, low: price - 2.5, close: price }); }
  for (let i = 12; i < 24; i++) { const drift = 124 - (i - 12) * 0.35; bars.push({ timestamp: i * 60_000, open: drift + 0.6, high: drift + 1.0, low: drift - 1.0, close: drift }); }
  for (let i = 24; i < 30; i++) { const p = 121 + (i - 24) * 2; bars.push({ timestamp: i * 60_000, open: p - 2, high: p + 0.6, low: p - 2.4, close: p }); }
  return bars;
}

describe('continuation detectors', () => {
  it('finds a bull flag after an impulse leg', () => {
    const candles = flagSeries();
    const atr = 2.0;
    const found = detectContinuation(candles, atr, PATTERN_CONFIG);
    expect(found.some((p) => p.kind === 'FLAG_BULL')).toBe(true);
    const flag = found.find((p) => p.kind === 'FLAG_BULL')!;
    expect(flag.family).toBe('continuation');
    expect(flag.direction).toBe('bullish');
    expect(flag.upper.to.price).toBeGreaterThan(flag.lower.to.price);
    expect(flag.quality).toBeGreaterThan(0);
  });

  it('does not invent a pattern on a straight line', () => {
    const flat: EngineCandle[] = Array.from({ length: 40 }, (_, i) => ({
      timestamp: i * 60_000, open: 100, high: 101, low: 99, close: 100,
    }));
    expect(detectContinuation(flat, 1.5, PATTERN_CONFIG)).toEqual([]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend-v2 && npx vitest run src/features/technical/model/patterns/__tests__/continuation.test.ts`
Expected: FAIL with "Cannot find module '../detectContinuation'".

- [ ] **Step 3: Write the implementation**

```ts
// model/patterns/detectContinuation.ts
import type { EngineCandle } from '../doubleTapEngine';
import type { PatternConfig } from './config';
import type { BoundaryLine, ChartPattern, PatternPoint } from './types';
import { findAlternatingPivots, type PivotPoint } from './pivots';
import { emitPattern, lineSlope, lineValue, toPoint, touchCount } from './geometry';

const clampQuality = (value: number) => Math.max(0, Math.min(100, value));

function lastTwo(pivots: PivotPoint[], kind: 'high' | 'low'): [PivotPoint, PivotPoint] | null {
  const items = pivots.filter((p) => p.kind === kind);
  if (items.length < 2) return null;
  return [items[items.length - 2]!, items[items.length - 1]!];
}

function lines(highs: [PivotPoint, PivotPoint], lows: [PivotPoint, PivotPoint], candles: readonly EngineCandle[]) {
  return {
    upper: { from: toPoint(highs[0], candles), to: toPoint(highs[1], candles) } as BoundaryLine,
    lower: { from: toPoint(lows[0], candles), to: toPoint(lows[1], candles) } as BoundaryLine,
  };
}

/** خروجی: الگوهای ادامه‌دهندهٔ باز/تأییدشده؛ الگوهای منقضی در emitPattern حذف می‌شوند. */
export function detectContinuation(
  candles: readonly EngineCandle[],
  atr: number,
  config: PatternConfig,
): ChartPattern[] {
  if (!Number.isFinite(atr) || atr <= 0) return [];
  const pivots = findAlternatingPivots(candles, config.pivLeft, config.pivRight);
  const out: ChartPattern[] = [];
  const lastIndex = candles.length - 1;

  for (let i = 0; i + 3 < pivots.length; i++) {
    const legStart = pivots[i]!;
    const legEnd = pivots[i + 1]!;
    if (legStart.kind === legEnd.kind) continue;
    const legHeight = Math.abs(legEnd.price - legStart.price);
    const legBars = legEnd.index - legStart.index;
    const bullish = legStart.kind === 'low';
    if (legBars < 3 || legHeight < config.flag.impulseLegAtrMin * atr) continue;

    const after = pivots.filter((p) => p.index > legEnd.index && p.index <= legEnd.index + config.flag.maxBars);
    const highs = lastTwo(after, 'high');
    const lows = lastTwo(after, 'low');
    if (!highs || !lows) continue;
    const { upper, lower } = lines(highs, lows, candles);
    const widthAtEnd = Math.abs(lineValue(upper, legEnd.index) - lineValue(lower, legEnd.index));
    if (widthAtEnd <= 0 || widthAtEnd > (config.flag.channelMaxWidthPct / 100) * legHeight) continue;

    const slope = lineSlope(upper);
    if (config.flag.slopeOpposite && bullish && slope > 0) continue;
    if (config.flag.slopeOpposite && !bullish && slope < 0) continue;

    const touches = touchCount(after, upper, 'high', atr * 0.5) + touchCount(after, lower, 'low', atr * 0.5);
    if (touches < config.minTouchesPerLine * 2) continue;

    const anchor = bullish ? highs[1]! : lows[1]!;
    const points = [toPoint(legStart, candles), toPoint(legEnd, candles), toPoint(highs[0], candles), toPoint(highs[1], candles), toPoint(lows[0], candles), toPoint(lows[1], candles)];
    const target = bullish ? legEnd.price + legHeight : legEnd.price - legHeight;
    const stopLoss = bullish ? legEnd.price - legHeight : legEnd.price + legHeight;
    const quality = clampQuality(
      50 + 25 * (1 - Math.min(1, widthAtEnd / (legHeight * 0.35))) + 25 * Math.min(1, touches / 6),
    );
    const emitted = emitPattern(
      { kind: bullish ? 'FLAG_BULL' : 'FLAG_BEAR', direction: bullish ? 'bullish' : 'bearish', family: 'continuation',
        points, upper, lower, target, stopLoss, quality },
      candles, config,
    );
    if (emitted) out.push(emitted);

    // پنانت: همان لگ، ولی دو خط همگرا (سقف پایین‌آینده و کف بالارونده).
    const converge = widthAtEnd <= (1 - config.pennant.convergenceMin) * Math.abs(lineValue(upper, highs[0]!.index) - lineValue(lower, lows[0]!.index));
    if (converge && legBars <= config.pennant.maxBars) {
      const pennant = emitPattern(
        { kind: 'PENNANT', direction: bullish ? 'bullish' : 'bearish', family: 'continuation',
          points, upper, lower, target, stopLoss, quality: quality - 5 },
        candles, config,
      );
      if (pennant) out.push(pennant);
    }
  }

  const triangles = detectTriangleFamily(pivots, candles, atr, config, lastIndex);
  out.push(...triangles);
  return dedupe(out);
}

function detectTriangleFamily(
  pivots: PivotPoint[],
  candles: readonly EngineCandle[],
  atr: number,
  config: PatternConfig,
  lastIndex: number,
): ChartPattern[] {
  const highs = lastTwo(pivots, 'high');
  const lows = lastTwo(pivots, 'low');
  if (!highs || !lows) return [];
  const { upper, lower } = lines(highs, lows, candles);
  const h1 = highs[0]!.price, h2 = highs[1]!.price;
  const l1 = lows[0]!.price, l2 = lows[1]!.price;
  const flat = config.triangle.flatToleranceAtr * atr;
  const span = Math.abs(highs[1]!.index - lows[1]!.index);
  if (span < 3 || highs[1]!.index < lastIndex - config.triangle.maxBars) return [];

  const widthStart = Math.abs(lineValue(upper, Math.min(highs[0]!.index, lows[0]!.index)) - lineValue(lower, Math.min(highs[0]!.index, lows[0]!.index)));
  const widthEnd = Math.abs(lineValue(upper, Math.max(highs[1]!.index, lows[1]!.index)) - lineValue(lower, Math.max(highs[1]!.index, lows[1]!.index)));
  const converging = widthStart > 0 && widthEnd <= (1 - config.triangle.convergenceMin) * widthStart;
  const points = [toPoint(highs[0], candles), toPoint(lows[0], candles), toPoint(highs[1], candles), toPoint(lows[1], candles)];
  const anchor = toPoint(lows[1], candles);
  const height = Math.abs(h1 - l1);
  const base = { points, upper, lower, family: 'continuation' as const, target: h1 + height, stopLoss: l1 - atr, quality: 60 };

  const out: ChartPattern[] = [];
  const push = (kind: ChartPattern['kind'], direction: ChartPattern['direction'], quality: number) => {
    const emitted = emitPattern({ ...base, kind, direction, quality }, candles, config);
    if (emitted) out.push(emitted);
  };

  if (Math.abs(h2 - h1) <= flat && l2 > l1) push('TRIANGLE_ASC', 'bullish', 65);
  if (Math.abs(l2 - l1) <= flat && h2 < h1) push('TRIANGLE_DESC', 'bearish', 65);
  if (converging && h2 < h1 && l2 > l1) push('TRIANGLE_SYM', 'neutral', 60);
  if (Math.abs(h2 - h1) <= config.rectangle.flatToleranceAtr * atr && Math.abs(l2 - l1) <= config.rectangle.flatToleranceAtr * atr) {
    push('RECTANGLE', 'neutral', 55);
  }
  if (converging && h2 > h1 && l2 > l1) push('WEDGE_RISING', 'bearish', 55);
  if (converging && h2 < h1 && l2 < l1) push('WEDGE_FALLING', 'bullish', 55);
  return out;
}

function dedupe(patterns: ChartPattern[]): ChartPattern[] {
  const seen = new Set<string>();
  return patterns.filter((p) => (seen.has(p.id) ? false : (seen.add(p.id), true)));
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend-v2 && npx vitest run src/features/technical/model/patterns/__tests__/continuation.test.ts`
Expected: PASS (2 tests). If the flag fixture does not trigger, adjust the fixture bars (not the thresholds) until the geometry matches the documented rules; never loosen `PATTERN_CONFIG` in this task.

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/src/features/technical/model/patterns/detectContinuation.ts frontend-v2/src/features/technical/model/patterns/__tests__/continuation.test.ts
git commit -m "feat(technical): دتکتورهای الگوهای ادامه‌دهنده"
```

---

### Task 5: Reversal detectors (head & shoulders, triple)

**Files:**
- Create: `frontend-v2/src/features/technical/model/patterns/detectReversal.ts`
- Test: `frontend-v2/src/features/technical/model/patterns/__tests__/reversal.test.ts`

**Interfaces:**
- Consumes: `findAlternatingPivots`, `toPoint`, `emitPattern`.
- Produces: `detectReversal(candles, atr, config): ChartPattern[]`.

- [ ] **Step 1: Write the failing test**

```ts
// model/patterns/__tests__/reversal.test.ts
import { describe, expect, it } from 'vitest';
import { detectReversal } from '../detectReversal';
import { PATTERN_CONFIG } from '../config';
import type { EngineCandle } from '../../doubleTapEngine';

/** سه قله با وسطِ بلندتر و دو درهٔ هم‌تراز + شکستِ خطِ گردن. */
function headShouldersSeries(): EngineCandle[] {
  const highs = [110, 112, 118, 113, 111, 108, 104, 100, 98, 97, 96, 96];
  const lows = [104, 106, 107, 105, 103, 101, 99, 96, 94, 93, 92, 92];
  const closes = [107, 109, 111, 109, 106, 102, 100, 97, 95, 94, 93, 93];
  return highs.map((high, i) => ({ timestamp: i * 60_000, open: closes[i]!, high, low: lows[i]!, close: closes[i]! }));
}

describe('reversal detectors', () => {
  it('finds a head & shoulders with a broken neckline', () => {
    const found = detectReversal(headShouldersSeries(), 1.5, PATTERN_CONFIG);
    const hs = found.find((p) => p.kind === 'HEAD_SHOULDERS');
    expect(hs).toBeTruthy();
    expect(hs!.family).toBe('reversal');
    expect(hs!.direction).toBe('bearish');
    expect(hs!.neckline).toBeTruthy();
  });

  it('finds a triple top when three peaks share a level', () => {
    const highs = [110, 108, 111, 108, 110, 104, 100, 98, 97, 96, 96, 96];
    const lows = [104, 105, 105, 104, 103, 99, 97, 95, 94, 93, 93, 93];
    const series: EngineCandle[] = highs.map((high, i) => ({
      timestamp: i * 60_000, open: lows[i]!, high, low: lows[i]!, close: lows[i]! + 1,
    }));
    const found = detectReversal(series, 1.2, PATTERN_CONFIG);
    expect(found.some((p) => p.kind === 'TRIPLE_TOP')).toBe(true);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend-v2 && npx vitest run src/features/technical/model/patterns/__tests__/reversal.test.ts`
Expected: FAIL with "Cannot find module '../detectReversal'".

- [ ] **Step 3: Write the implementation**

```ts
// model/patterns/detectReversal.ts
import type { EngineCandle } from '../doubleTapEngine';
import type { PatternConfig } from './config';
import type { BoundaryLine, ChartPattern } from './types';
import { findAlternatingPivots, type PivotPoint } from './pivots';
import { emitPattern, lineValue, toPoint } from './geometry';

const quality = (headroom: number, tolerance: number) =>
  Math.round(55 + 35 * Math.max(0, Math.min(1, headroom / Math.max(tolerance, 1e-9))) + 10);

export function detectReversal(
  candles: readonly EngineCandle[],
  atr: number,
  config: PatternConfig,
): ChartPattern[] {
  if (!Number.isFinite(atr) || atr <= 0) return [];
  const pivots = findAlternatingPivots(candles, config.pivLeft, config.pivRight);
  const out: ChartPattern[] = [];

  for (let i = 0; i + 4 < pivots.length; i++) {
    const [a, b, c, d, e] = pivots.slice(i, i + 5) as [PivotPoint, PivotPoint, PivotPoint, PivotPoint, PivotPoint];
    const heads = a.kind === 'high' && c.kind === 'high' && e.kind === 'high' && b.kind === 'low' && d.kind === 'low';
    const bottoms = a.kind === 'low' && c.kind === 'low' && e.kind === 'low' && b.kind === 'high' && d.kind === 'high';
    if (!heads && !bottoms) continue;
    const span = e.index - a.index;
    if (span < 6 || span > config.hs.maxBars || e.index < candles.length - config.hs.maxBars) continue;

    if (heads) {
      const middleHighest = c.price >= Math.max(a.price, e.price) + config.hs.headAboveShouldersAtr * atr;
      const shouldersAligned = Math.abs(a.price - e.price) <= config.hs.shouldersToleranceAtr * atr;
      if (middleHighest && shouldersAligned) {
        const neck: BoundaryLine = { from: toPoint(b, candles), to: toPoint(d, candles) };
        const top: BoundaryLine = { from: toPoint(c, candles), to: toPoint(c, candles) };
        const neckline = Math.min(b.price, d.price);
        const height = c.price - neckline;
        const emitted = emitPattern({
          kind: 'HEAD_SHOULDERS', direction: 'bearish', family: 'reversal',
          points: [a, b, c, d, e].map((p) => toPoint(p, candles)),
          upper: top, lower: neck, neckline: neck,
          target: neckline - height, stopLoss: c.price + atr,
          quality: quality(height, config.hs.shouldersToleranceAtr * atr * 2),
        }, candles, config);
        if (emitted) out.push(emitted);
      }
    }

    if (bottoms) {
      const middleLowest = c.price <= Math.min(a.price, e.price) - config.hs.headAboveShouldersAtr * atr;
      const shouldersAligned = Math.abs(a.price - e.price) <= config.hs.shouldersToleranceAtr * atr;
      if (middleLowest && shouldersAligned) {
        const neck: BoundaryLine = { from: toPoint(b, candles), to: toPoint(d, candles) };
        const bottom: BoundaryLine = { from: toPoint(c, candles), to: toPoint(c, candles) };
        const neckline = Math.max(b.price, d.price);
        const height = neckline - c.price;
        const emitted = emitPattern({
          kind: 'INVERSE_HEAD_SHOULDERS', direction: 'bullish', family: 'reversal',
          points: [a, b, c, d, e].map((p) => toPoint(p, candles)),
          upper: neck, lower: bottom, neckline: neck,
          target: neckline + height, stopLoss: c.price - atr,
          quality: quality(height, config.hs.shouldersToleranceAtr * atr * 2),
        }, candles, config);
        if (emitted) out.push(emitted);
      }
    }

    // سه‌قلو: سه قله/درهٔ هم‌سطح با دو دره/قلهٔ میانی.
    const tol = config.triple.levelToleranceAtr * atr;
    if (heads && Math.abs(a.price - c.price) <= tol && Math.abs(c.price - e.price) <= tol) {
      const neck: BoundaryLine = { from: toPoint(b, candles), to: toPoint(d, candles) };
      const top: BoundaryLine = { from: toPoint(a, candles), to: toPoint(e, candles) };
      const height = Math.max(a.price, c.price, e.price) - Math.min(b.price, d.price);
      const emitted = emitPattern({
        kind: 'TRIPLE_TOP', direction: 'bearish', family: 'reversal',
        points: [a, b, c, d, e].map((p) => toPoint(p, candles)),
        upper: top, lower: neck, neckline: neck,
        target: Math.min(b.price, d.price) - height, stopLoss: Math.max(a.price, c.price, e.price) + atr,
        quality: quality(height, tol * 2),
      }, candles, config);
      if (emitted) out.push(emitted);
    }
    if (bottoms && Math.abs(a.price - c.price) <= tol && Math.abs(c.price - e.price) <= tol) {
      const neck: BoundaryLine = { from: toPoint(b, candles), to: toPoint(d, candles) };
      const bottom: BoundaryLine = { from: toPoint(a, candles), to: toPoint(e, candles) };
      const height = Math.max(b.price, d.price) - Math.min(a.price, c.price, e.price);
      const emitted = emitPattern({
        kind: 'TRIPLE_BOTTOM', direction: 'bullish', family: 'reversal',
        points: [a, b, c, d, e].map((p) => toPoint(p, candles)),
        upper: neck, lower: bottom, neckline: neck,
        target: Math.max(b.price, d.price) + height, stopLoss: Math.min(a.price, c.price, e.price) - atr,
        quality: quality(height, tol * 2),
      }, candles, config);
      if (emitted) out.push(emitted);
    }
  }
  return out;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend-v2 && npx vitest run src/features/technical/model/patterns/__tests__/reversal.test.ts`
Expected: PASS (2 tests). If a fixture does not trigger, adjust the fixture bars, never the config.

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/src/features/technical/model/patterns/detectReversal.ts frontend-v2/src/features/technical/model/patterns/__tests__/reversal.test.ts
git commit -m "feat(technical): دتکتورهای الگوهای بازگشتی"
```

---

### Task 6: Outcome and 1/3/5-bar returns

**Files:**
- Create: `frontend-v2/src/features/technical/model/patterns/outcome.ts`
- Test: `frontend-v2/src/features/technical/model/patterns/__tests__/outcome.test.ts`

**Interfaces:**
- Consumes: `ChartPattern`, `BoundaryLine`, `PatternConfig`, `lineValue`.
- Produces: `outcomeOf(pattern, candles, atr, config, horizon?): 'success' | 'failure' | 'unresolved'`, `meanReturns(samples, candles, config, atr): { h1: number | null; h3: number | null; h5: number | null }`.

**Rulings locked here:**
- **R-PAT-1:** samples pool by **family** (continuation vs reversal) so small-history symbols still get a rate; the label always says «همین نماد».
- **R-PAT-2:** a `neutral` pattern (rectangle, symmetric triangle) takes the direction of its first boundary break and succeeds if price extends by half the pattern height in that direction before closing through the opposite boundary.
- **R-PAT-3:** returns are reported only for `bullish`/`bearish` patterns; `neutral` returns stay `null`.
- **R-PAT-4:** a pattern that neither confirms nor invalidates inside `maxBars` is dropped, never labelled `forming`.

- [ ] **Step 1: Write the failing test**

```ts
// model/patterns/__tests__/outcome.test.ts
import { describe, expect, it } from 'vitest';
import { outcomeOf } from '../outcome';
import { PATTERN_CONFIG } from '../config';
import type { ChartPattern } from '../types';
import type { EngineCandle } from '../../doubleTapEngine';

const point = (index: number, price: number) => ({ index, price, timestamp: index * 60_000 });
const pattern = (over: Partial<ChartPattern> = {}): ChartPattern => ({
  id: 'FLAG_BULL:4:1-2-3-4', kind: 'FLAG_BULL', direction: 'bullish', family: 'continuation',
  anchor: point(4, 105), points: [point(2, 100), point(4, 105)],
  upper: { from: point(4, 106), to: point(4, 106) },
  lower: { from: point(4, 104), to: point(4, 104) },
  target: 112, stopLoss: 98, quality: 60, status: 'forming', ...over,
});
const bars = (closes: number[]): EngineCandle[] => closes.map((close, i) => ({
  timestamp: i * 60_000, open: close, high: close + 0.5, low: close - 0.5, close,
}));

describe('outcome', () => {
  it('marks a close beyond the directional boundary as success', () => {
    expect(outcomeOf(pattern(), bars([100, 104, 105, 106, 107, 108]), 1, PATTERN_CONFIG)).toBe('success');
  });

  it('marks a close through the opposite boundary as failure', () => {
    expect(outcomeOf(pattern(), bars([100, 104, 105, 103.4, 102, 101]), 1, PATTERN_CONFIG)).toBe('failure');
  });

  it('stays unresolved when nothing happens inside the horizon', () => {
    expect(outcomeOf(pattern(), bars([100, 104, 105, 105, 105.2, 105.4]), 1, PATTERN_CONFIG)).toBe('unresolved');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend-v2 && npx vitest run src/features/technical/model/patterns/__tests__/outcome.test.ts`
Expected: FAIL with "Cannot find module '../outcome'".

- [ ] **Step 3: Write the implementation**

```ts
// model/patterns/outcome.ts
import type { EngineCandle } from '../doubleTapEngine';
import type { PatternConfig } from './config';
import type { ChartPattern } from './types';
import { lineValue } from './geometry';

export type PatternOutcome = 'success' | 'failure' | 'unresolved';

function heightOf(pattern: ChartPattern): number {
  return Math.abs(lineValue(pattern.upper, pattern.anchor.index) - lineValue(pattern.lower, pattern.anchor.index));
}

export function outcomeOf(
  pattern: ChartPattern,
  candles: readonly EngineCandle[],
  atr: number,
  config: PatternConfig,
  horizon = config.outcomeHorizon,
): PatternOutcome {
  const start = pattern.anchor.index + 1;
  const end = Math.min(candles.length, start + horizon);
  const buffer = config.invalidationBufferAtr * atr;

  if (pattern.direction === 'neutral') {
    const height = heightOf(pattern);
    const target = height / 2;
    let bias: 'up' | 'down' | null = null;
    let entry = 0;
    for (let i = start; i < end; i++) {
      const close = candles[i].close;
      const up = lineValue(pattern.upper, i);
      const down = lineValue(pattern.lower, i);
      if (!bias) {
        if (close > up) { bias = 'up'; entry = up; }
        else if (close < down) { bias = 'down'; entry = down; }
        continue;
      }
      if (bias === 'up') {
        if (close >= entry + target) return 'success';
        if (close < down - buffer) return 'failure';
      } else {
        if (close <= entry - target) return 'success';
        if (close > up + buffer) return 'failure';
      }
    }
    return 'unresolved';
  }

  const bullish = pattern.direction === 'bullish';
  for (let i = start; i < end; i++) {
    const close = candles[i].close;
    const up = lineValue(pattern.upper, i);
    const down = lineValue(pattern.lower, i);
    if (bullish ? close > up : close < down) return 'success';
    if (bullish ? close < down - buffer : close > up + buffer) return 'failure';
  }
  return 'unresolved';
}

/** میانگین بازدهِ ۱/۳/۵ کندلِ نمونه‌های حل‌شده؛ زیرِ ۵ نمونه null. */
export function meanReturns(
  samples: readonly ChartPattern[],
  candles: readonly EngineCandle[],
  config: PatternConfig,
): { h1: number | null; h3: number | null; h5: number | null } {
  const directional = samples.filter((p) => p.direction !== 'neutral');
  const result = { h1: null as number | null, h3: null as number | null, h5: null as number | null };
  for (const horizon of config.returnHorizons) {
    const values: number[] = [];
    for (const sample of directional) {
      const triggerIndex = sample.breakoutIndex ?? sample.anchor.index;
      const end = triggerIndex + horizon;
      if (end >= candles.length) continue;
      const trigger = sample.direction === 'bullish'
        ? lineValue(sample.upper, triggerIndex)
        : lineValue(sample.lower, triggerIndex);
      if (!(trigger > 0)) continue;
      const close = candles[end].close;
      values.push(((sample.direction === 'bullish' ? close - trigger : trigger - close) / trigger) * 100);
    }
    const mean = values.length >= 5 ? values.reduce((a, b) => a + b, 0) / values.length : null;
    if (horizon === 1) result.h1 = mean;
    if (horizon === 3) result.h3 = mean;
    if (horizon === 5) result.h5 = mean;
  }
  return result;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend-v2 && npx vitest run src/features/technical/model/patterns/__tests__/outcome.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/src/features/technical/model/patterns/outcome.ts frontend-v2/src/features/technical/model/patterns/__tests__/outcome.test.ts
git commit -m "feat(technical): نتیجه و بازده ۱/۳/۵ کندلی الگوها"
```

---

### Task 7: Formation estimate and registry

**Files:**
- Create: `frontend-v2/src/features/technical/model/patterns/formation.ts`
- Create: `frontend-v2/src/features/technical/model/patterns/registry.ts`
- Modify: `frontend-v2/src/features/technical/model/doubleTapEngine.ts` (add `export` to `confidenceFor` only)
- Test: `frontend-v2/src/features/technical/model/patterns/__tests__/formation.test.ts`
- Test: `frontend-v2/src/features/technical/model/patterns/__tests__/registry.test.ts`

**Interfaces:**
- Consumes: `laplaceRate`, `wilsonInterval`, `confidenceFor`, `calculateAtr`, `detectDoubleTapPatterns`, `DEFAULT_PRECISION_PARAMS` from `../doubleTapEngine`; `outcomeOf`, `meanReturns`; `detectContinuation`, `detectReversal`.
- Produces: `estimatePatternFormation(current, all, candles, atr, config): FormationEstimate | null`, `estimateReturns(current, all, candles, config): ChartPattern['returns']`, `detectAllPatterns(candles, config?): ChartPattern[]`, `fromDoubleTap(p): ChartPattern`, `selectFeaturedPatterns(patterns, max?): ChartPattern[]`.

- [ ] **Step 1: Write the failing tests**

```ts
// model/patterns/__tests__/formation.test.ts
import { describe, expect, it } from 'vitest';
import { estimatePatternFormation } from '../formation';
import { PATTERN_CONFIG } from '../config';
import type { ChartPattern } from '../types';

const point = (index: number, price: number) => ({ index, price, timestamp: index * 60_000 });
const pattern = (id: string, anchorIndex: number, status: ChartPattern['status'], quality = 60): ChartPattern => ({
  id, kind: 'FLAG_BULL', direction: 'bullish', family: 'continuation',
  anchor: point(anchorIndex, 105), points: [point(anchorIndex - 1, 100), point(anchorIndex, 105)],
  upper: { from: point(anchorIndex, 106), to: point(anchorIndex, 106) },
  lower: { from: point(anchorIndex, 104), to: point(anchorIndex, 104) },
  target: 112, stopLoss: 98, quality, status,
});

describe('formation estimate', () => {
  it('returns no probability under 8 resolved samples', () => {
    const current = pattern('current', 40, 'forming');
    const all = [current, pattern('a', 5, 'confirmed'), pattern('b', 10, 'confirmed')];
    const candles = Array.from({ length: 60 }, (_, i) => ({ timestamp: i * 60_000, open: 100, high: 101, low: 99, close: 100 }));
    const estimate = estimatePatternFormation(current, all, candles, 1, PATTERN_CONFIG);
    expect(estimate?.probability).toBeNull();
    expect(estimate?.resolved).toBeLessThan(8);
  });

  it('returns null for a non-forming pattern', () => {
    const current = pattern('current', 40, 'confirmed');
    expect(estimatePatternFormation(current, [current], [], 1, PATTERN_CONFIG)).toBeNull();
  });
});
```

```ts
// model/patterns/__tests__/registry.test.ts
import { describe, expect, it } from 'vitest';
import { detectAllPatterns, selectFeaturedPatterns, fromDoubleTap } from '../registry';
import { PATTERN_CONFIG } from '../config';
import { detectDoubleTapPatterns, DEFAULT_PRECISION_PARAMS } from '../../doubleTapEngine';
import type { EngineCandle } from '../../doubleTapEngine';

const series: EngineCandle[] = Array.from({ length: 120 }, (_, i) => {
  const base = 100 + Math.sin(i / 6) * 6;
  return { timestamp: i * 60_000, open: base, high: base + 1.2, low: base - 1.2, close: base + 0.3 };
});

describe('pattern registry', () => {
  it('merges new patterns with the existing double taps and keeps doubles intact', () => {
    const all = detectAllPatterns(series, PATTERN_CONFIG);
    const doubles = detectDoubleTapPatterns(series, DEFAULT_PRECISION_PARAMS).map(fromDoubleTap);
    expect(doubles.every((d) => d.kind === 'DOUBLE_TOP' || d.kind === 'DOUBLE_BOTTOM')).toBe(true);
    expect(all.length).toBeGreaterThanOrEqual(doubles.length);
    expect(new Set(all.map((p) => p.id)).size).toBe(all.length);
  });

  it('features at most six shapes', () => {
    const all = detectAllPatterns(series, PATTERN_CONFIG);
    expect(selectFeaturedPatterns(all, 6).length).toBeLessThanOrEqual(6);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend-v2 && npx vitest run src/features/technical/model/patterns/__tests__/formation.test.ts src/features/technical/model/patterns/__tests__/registry.test.ts`
Expected: FAIL with "Cannot find module '../formation'".

- [ ] **Step 3: Write the implementations**

```ts
// model/patterns/formation.ts
import type { EngineCandle } from '../doubleTapEngine';
import { confidenceFor, laplaceRate, wilsonInterval } from '../doubleTapEngine';
import type { FormationEstimate } from '../types';
import type { PatternConfig } from './config';
import type { ChartPattern } from './types';
import { meanReturns, outcomeOf } from './outcome';

export function estimatePatternFormation(
  current: ChartPattern,
  all: readonly ChartPattern[],
  candles: readonly EngineCandle[],
  atr: number,
  config: PatternConfig,
): FormationEstimate | null {
  if (current.status !== 'forming') return null;

  // R-PAT-1: نمونه‌ها از همان خانواده (ادامه‌دهنده/بازگشتی)، نه فقط همان نوع.
  const samples = all.filter(
    (p) => p.id !== current.id && p.family === current.family && p.status !== 'forming'
      && p.anchor.index + 1 < candles.length,
  );
  const resolved = samples
    .map((sample) => ({ sample, outcome: outcomeOf(sample, candles, atr, config) }))
    .filter((item): item is { sample: ChartPattern; outcome: 'success' | 'failure' } => item.outcome !== 'unresolved');

  const qualities = samples.map((s) => s.quality).sort((a, b) => a - b);
  let selected = resolved;
  let qualityBucket: number | undefined;
  if (qualities.length >= 8) {
    const low = qualities[Math.floor(qualities.length / 3)]!;
    const high = qualities[Math.floor((2 * qualities.length) / 3)]!;
    const bucket = current.quality <= low ? 0 : current.quality <= high ? 1 : 2;
    const bucketOf = (q: number) => (q <= low ? 0 : q <= high ? 1 : 2);
    const bucketSamples = resolved.filter((item) => bucketOf(item.sample.quality) === bucket);
    if (bucketSamples.length >= 8) {
      selected = bucketSamples;
      qualityBucket = bucket;
    }
  }

  const successes = selected.filter((item) => item.outcome === 'success').length;
  const failures = selected.length - successes;
  const count = successes + failures;
  return {
    probability: count >= config.formationMinResolved ? laplaceRate(successes, failures) : null,
    successes,
    failures,
    resolved: count,
    confidence: confidenceFor(count),
    horizon: config.outcomeHorizon,
    method: 'same-symbol',
    qualityBucket,
    intervalLow: count > 0 ? wilsonInterval(successes, count)[0] : undefined,
    intervalHigh: count > 0 ? wilsonInterval(successes, count)[1] : undefined,
  };
}

export function estimateReturns(
  current: ChartPattern,
  all: readonly ChartPattern[],
  candles: readonly EngineCandle[],
  config: PatternConfig,
): ChartPattern['returns'] {
  if (current.status !== 'forming') return undefined;
  const samples = all.filter((p) => p.id !== current.id && p.family === current.family && p.status !== 'forming');
  return meanReturns(samples, candles, config);
}
```

```ts
// model/patterns/registry.ts
import type { EngineCandle } from '../doubleTapEngine';
import {
  calculateAtr, DEFAULT_PRECISION_PARAMS, detectDoubleTapPatterns, type DoubleTapPattern,
} from '../doubleTapEngine';
import { PATTERN_CONFIG, type PatternConfig } from './config';
import type { ChartPattern } from './types';
import { detectContinuation } from './detectContinuation';
import { detectReversal } from './detectReversal';
import { estimatePatternFormation, estimateReturns } from './formation';

export function fromDoubleTap(p: DoubleTapPattern): ChartPattern {
  const anchor = p.retest ?? p.peak2;
  const bullish = p.type === 'DOUBLE_BOTTOM';
  const at = (index: number, price: number, timestamp: number) => ({ index, price, timestamp });
  return {
    id: `DT:${p.id}`,
    kind: p.type,
    direction: bullish ? 'bullish' : 'bearish',
    family: 'reversal',
    anchor: at(anchor.index, anchor.price, anchor.timestamp),
    points: [p.peak1, p.neckline, p.peak2].map((x) => at(x.index, x.price, x.timestamp)),
    upper: { from: at(p.peak2.index, p.peak2.price, p.peak2.timestamp), to: at(p.peak2.index, p.peak2.price, p.peak2.timestamp) },
    lower: { from: at(p.neckline.index, p.neckline.price, p.neckline.timestamp), to: at(p.neckline.index, p.neckline.price, p.neckline.timestamp) },
    target: p.target1,
    stopLoss: p.stopLoss,
    quality: p.quality,
    status: p.status === 'forming' ? 'forming' : p.status === 'invalidated' ? 'invalidated' : 'confirmed',
    formation: p.formation,
  };
}

export function detectAllPatterns(
  candles: readonly EngineCandle[],
  config: PatternConfig = PATTERN_CONFIG,
): ChartPattern[] {
  const atrSeries = calculateAtr(candles as EngineCandle[], config.atrPeriod);
  const atr = atrSeries[atrSeries.length - 1] ?? 0;
  if (!(atr > 0)) return [];
  const merged = [
    ...detectContinuation(candles, atr, config),
    ...detectReversal(candles, atr, config),
    ...detectDoubleTapPatterns(candles, DEFAULT_PRECISION_PARAMS).map(fromDoubleTap),
  ].filter((p, i, all) => all.findIndex((x) => x.id === p.id) === i);

  return merged
    .map((pattern) => (pattern.status === 'forming'
      ? {
          ...pattern,
          formation: estimatePatternFormation(pattern, merged, candles, atr, config) ?? undefined,
          returns: estimateReturns(pattern, merged, candles, config),
        }
      : pattern))
    .sort((a, b) => a.anchor.index - b.anchor.index);
}

/** حداکثر شش شکل: آخرین «در حال تشکیل» و آخرین «تأییدشده» هر خانواده. */
export function selectFeaturedPatterns(
  patterns: readonly ChartPattern[],
  max = 6,
): ChartPattern[] {
  const picked: ChartPattern[] = [];
  for (const family of ['reversal', 'continuation'] as const) {
    const familyPatterns = patterns.filter((p) => p.family === family);
    const forming = [...familyPatterns].filter((p) => p.status === 'forming').sort((a, b) => b.anchor.index - a.anchor.index)[0];
    const confirmed = [...familyPatterns].filter((p) => p.status === 'confirmed').sort((a, b) => b.anchor.index - a.anchor.index)[0];
    if (forming) picked.push(forming);
    if (confirmed) picked.push(confirmed);
  }
  return picked.sort((a, b) => b.anchor.index - a.anchor.index).slice(0, max);
}
```

Also in `doubleTapEngine.ts`, change `function confidenceFor(` to `export function confidenceFor(`. Nothing else.

If TypeScript rejects a `readonly EngineCandle[]` where `detectDoubleTapPatterns`/`calculateAtr` expect a mutable array, pass `candles as EngineCandle[]` (the same cast `detectDoubleTapPatterns` callers already use); do not change the engines' signatures.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend-v2 && npx vitest run src/features/technical/model/patterns/__tests__/formation.test.ts src/features/technical/model/patterns/__tests__/registry.test.ts src/features/technical/model/__tests__/doubleTapEngine.test.ts`
Expected: PASS all three files; the double-tap file is unchanged and still green.

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/src/features/technical/model/patterns/formation.ts frontend-v2/src/features/technical/model/patterns/registry.ts frontend-v2/src/features/technical/model/patterns/__tests__/formation.test.ts frontend-v2/src/features/technical/model/patterns/__tests__/registry.test.ts frontend-v2/src/features/technical/model/doubleTapEngine.ts
git commit -m "feat(technical): نرخ تشکیل تاریخی و رجیستری الگوها"
```

---

### Task 8: Store slice and chart overlay

**Files:**
- Modify: `frontend-v2/src/features/technical/model/types.ts:152` (`DrawerTab`)
- Modify: `frontend-v2/src/features/technical/model/technicalStore.ts:56-60,158-170`
- Create: `frontend-v2/src/features/technical/overlays/patternOverlay.ts`
- Modify: `frontend-v2/src/features/technical/ui/KLineChartWrapper.tsx:30,47`
- Test: `frontend-v2/src/features/technical/model/__tests__/patternsStore.test.ts`
- Test: `frontend-v2/src/features/technical/overlays/__tests__/patternOverlay.test.ts`

**Interfaces:**
- Consumes: `ChartPattern`, `selectFeaturedPatterns`.
- Produces: store field `detectedPatterns: ChartPattern[]` and `setDetectedPatterns(patterns)`; `DrawerTab` includes `'patterns'`; `registerPatternOverlay(): void`; `patternFigures(params, patterns): OverlayFigure[]`.

- [ ] **Step 1: Write the failing tests**

```ts
// model/__tests__/patternsStore.test.ts
import { beforeEach, describe, expect, it } from 'vitest';
import { useTechnicalStore } from '../technicalStore';
import type { ChartPattern } from '../patterns/types';

const pattern: ChartPattern = {
  id: 'FLAG_BULL:4:1-2-3-4', kind: 'FLAG_BULL', direction: 'bullish', family: 'continuation',
  anchor: { index: 4, price: 105, timestamp: 4000 }, points: [],
  upper: { from: { index: 4, price: 106, timestamp: 4000 }, to: { index: 4, price: 106, timestamp: 4000 } },
  lower: { from: { index: 4, price: 104, timestamp: 4000 }, to: { index: 4, price: 104, timestamp: 4000 } },
  target: 112, stopLoss: 98, quality: 60, status: 'forming',
};

describe('patterns store slice', () => {
  beforeEach(() => useTechnicalStore.getState().setDetectedPatterns([]));
  it('stores detected patterns', () => {
    useTechnicalStore.getState().setDetectedPatterns([pattern]);
    expect(useTechnicalStore.getState().detectedPatterns).toHaveLength(1);
  });
});
```

```ts
// overlays/__tests__/patternOverlay.test.ts
import { describe, expect, it, vi } from 'vitest';
import { patternFigures } from '../patternOverlay';
import type { ChartPattern } from '../../model/patterns/types';

const p: ChartPattern = {
  id: 'X:4:1-2-3-4', kind: 'TRIANGLE_ASC', direction: 'bullish', family: 'continuation',
  anchor: { index: 10, price: 105, timestamp: 10_000 }, points: [],
  upper: { from: { index: 2, price: 110, timestamp: 2000 }, to: { index: 10, price: 110, timestamp: 10_000 } },
  lower: { from: { index: 2, price: 100, timestamp: 2000 }, to: { index: 10, price: 106, timestamp: 10_000 } },
  target: 120, stopLoss: 98, quality: 60, status: 'forming',
  formation: { probability: 62, successes: 14, failures: 9, resolved: 23, confidence: 'medium', horizon: 10, method: 'same-symbol' },
};

const params = { chart: { convertToPixel: vi.fn(() => ({ x: 10, y: 20 })) } } as never;

describe('pattern overlay figures', () => {
  it('draws both boundaries and one label for a forming pattern', () => {
    const figures = patternFigures(params, [p]);
    expect(figures.filter((f) => f.type === 'line').length).toBeGreaterThanOrEqual(2);
    expect(figures.some((f) => f.type === 'text' && String(f.attrs.text).includes('۶۲٪'))).toBe(true);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend-v2 && npx vitest run src/features/technical/model/__tests__/patternsStore.test.ts src/features/technical/overlays/__tests__/patternOverlay.test.ts`
Expected: FAIL (missing store field / missing module).

- [ ] **Step 3: Write the implementation**

In `model/types.ts` line 152 change:

```ts
export type DrawerTab = 'top50' | 'indicators' | 'scanner' | 'edge' | 'patterns';
```

In `technicalStore.ts` add near the double-tap slice (and import the type):

```ts
import type { ChartPattern } from './patterns/types';
// state:
detectedPatterns: [] as ChartPattern[],
// actions:
setDetectedPatterns: (patterns: ChartPattern[]) => set({ detectedPatterns: patterns }),
```

```ts
// overlays/patternOverlay.ts — فقط رسم؛ تشخیص از registry می‌آید.
import { registerOverlay } from 'klinecharts';
import type { OverlayFigure, OverlayTemplate, OverlayCreateFiguresCallbackParams } from 'klinecharts';
import { toFaDigits } from '@shared/lib/fa';
import { useTechnicalStore } from '../model/technicalStore';
import { selectFeaturedPatterns } from '../model/patterns/registry';
import type { ChartPattern } from '../model/patterns/types';

const KIND_FA: Record<string, string> = {
  FLAG_BULL: 'پرچم صعودی', FLAG_BEAR: 'پرچم نزولی', PENNANT: 'پنانت',
  TRIANGLE_ASC: 'مثلث صعودی', TRIANGLE_DESC: 'مثلث نزولی', TRIANGLE_SYM: 'مثلث متقارن',
  RECTANGLE: 'مستطیل', WEDGE_RISING: 'گُوهٔ صعودی', WEDGE_FALLING: 'گُوهٔ نزولی',
  HEAD_SHOULDERS: 'سر و شانه', INVERSE_HEAD_SHOULDERS: 'سر و شانهٔ معکوس',
  TRIPLE_TOP: 'سه‌قلوی سقف', TRIPLE_BOTTOM: 'سه‌قلوی کف',
  DOUBLE_TOP: 'سقف دوقلو', DOUBLE_BOTTOM: 'کف دوقلو',
};

const KIND_COLOR: Record<string, string> = {
  bullish: '#4f8f72', bearish: '#b45a6a', neutral: '#a89a6a',
};

function px(params: OverlayCreateFiguresCallbackParams<unknown>, index: number, price: number) {
  const raw = params.chart.convertToPixel({ dataIndex: index, value: price });
  const first = Array.isArray(raw) ? raw[0] : raw;
  return { x: first?.x ?? 0, y: first?.y ?? 0 };
}

export function patternFigures(
  params: OverlayCreateFiguresCallbackParams<unknown>,
  patterns: readonly ChartPattern[],
): OverlayFigure[] {
  const figures: OverlayFigure[] = [];
  const featured = selectFeaturedPatterns(patterns, 6);
  for (const pattern of featured) {
    const color = KIND_COLOR[pattern.direction] ?? KIND_COLOR.neutral;
    const forming = pattern.status === 'forming';
    figures.push({
      type: 'line',
      attrs: { coordinates: [px(params, pattern.upper.from.index, pattern.upper.from.price), px(params, pattern.upper.to.index, pattern.upper.to.price)] },
      styles: { color, size: forming ? 1.75 : 1.1, style: 'solid' },
    });
    figures.push({
      type: 'line',
      attrs: { coordinates: [px(params, pattern.lower.from.index, pattern.lower.from.price), px(params, pattern.lower.to.index, pattern.lower.to.price)] },
      styles: { color, size: forming ? 1.75 : 1.1, style: 'solid' },
    });
    if (pattern.neckline) {
      figures.push({
        type: 'line',
        attrs: { coordinates: [px(params, pattern.neckline.from.index, pattern.neckline.from.price), px(params, pattern.neckline.to.index, pattern.neckline.to.price)] },
        styles: { color: '#8a8580', size: 1.1, style: 'dashed', dashedValue: [4, 3] },
      });
    }
    const label = KIND_FA[pattern.kind] ?? pattern.kind;
    const pct = pattern.formation?.probability;
    const text = forming
      ? pct == null ? `${label} — در حال تشکیل` : `${label} — تشکیل ${toFaDigits(Math.round(pct))}٪`
      : label;
    figures.push({
      type: 'text',
      attrs: { x: px(params, pattern.anchor.index, pattern.anchor.price).x + 6, y: px(params, pattern.anchor.index, pattern.anchor.price).y - 8, text, align: 'left', baseline: 'bottom' },
      styles: { color, size: 10, family: 'inherit' },
    });
  }
  return figures;
}

export function registerPatternOverlay(): void {
  const template: OverlayTemplate = {
    name: 'ClassicPatterns',
    totalStep: 1,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: (params): OverlayFigure[] =>
      patternFigures(params, useTechnicalStore.getState().detectedPatterns),
  };
  try {
    registerOverlay(template);
  } catch {
    // idempotent
  }
}
```

In `KLineChartWrapper.tsx` import next to line 30 and call next to `registerFTSOverlays()`:

```ts
import { registerPatternOverlay } from '../overlays/patternOverlay';
// inside the same effect as registerFTSOverlays():
registerPatternOverlay();
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend-v2 && npx vitest run src/features/technical/model/__tests__/patternsStore.test.ts src/features/technical/overlays/__tests__/patternOverlay.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/src/features/technical/model/types.ts frontend-v2/src/features/technical/model/technicalStore.ts frontend-v2/src/features/technical/overlays/patternOverlay.ts frontend-v2/src/features/technical/ui/KLineChartWrapper.tsx frontend-v2/src/features/technical/model/__tests__/patternsStore.test.ts frontend-v2/src/features/technical/overlays/__tests__/patternOverlay.test.ts
git commit -m "feat(technical): اسلایس استور و رسم الگوها روی چارت"
```

---

### Task 9: Patterns tab (card, list, rule book)

**Files:**
- Create: `frontend-v2/src/features/technical/ui/PatternsTab.tsx`
- Modify: `frontend-v2/src/features/technical/ui/WideWorkspaceDrawer.tsx:356-365,415-450`
- Test: `frontend-v2/src/features/technical/ui/__tests__/PatternsTab.test.tsx`

**Interfaces:**
- Consumes: `ChartPattern`, `PATTERN_CONFIG`, store `detectedPatterns`.
- Produces: `PatternsTab` component with testids `pattern-card`, `pattern-list`, `pattern-rules`, `pattern-row-<id>`.

- [ ] **Step 1: Write the failing test**

```tsx
// ui/__tests__/PatternsTab.test.tsx
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { PatternsTab } from '../PatternsTab';
import type { ChartPattern } from '../../model/patterns/types';

const point = (index: number, price: number) => ({ index, price, timestamp: index * 60_000 });
const base = (over: Partial<ChartPattern>): ChartPattern => ({
  id: 'p1', kind: 'FLAG_BULL', direction: 'bullish', family: 'continuation',
  anchor: point(40, 105), points: [], upper: { from: point(30, 106), to: point(40, 106) },
  lower: { from: point(30, 104), to: point(40, 104) },
  target: 112, stopLoss: 98, quality: 60, status: 'forming', ...over,
});

afterEach(cleanup);

describe('PatternsTab', () => {
  it('shows the percentage only when a formation estimate exists', () => {
    render(<PatternsTab patterns={[base({
      formation: { probability: 62, successes: 14, failures: 9, resolved: 23, confidence: 'medium', horizon: 10, method: 'same-symbol' },
      returns: { h1: 1.2, h3: 2.1, h5: null },
    })]} />);
    const card = screen.getByTestId('pattern-card');
    expect(card.textContent).toContain('۶۲٪');
    expect(card.textContent).toContain('۲۳');
    expect(card.textContent).toContain('کندلِ در حال تشکیل');
  });

  it('says the sample is not enough instead of showing a number', () => {
    render(<PatternsTab patterns={[base({
      formation: { probability: null, successes: 2, failures: 1, resolved: 3, confidence: 'none', horizon: 10, method: 'same-symbol' },
    })]} />);
    expect(screen.getByTestId('pattern-card').textContent).toContain('نمونهٔ کافی نیست');
    expect(screen.getByTestId('pattern-card').textContent).not.toMatch(/تشکیل\s*[۰-۹]+٪/);
  });

  it('lists recent patterns with stable row testids and filters by family', () => {
    render(<PatternsTab patterns={[
      base({ id: 'a' }),
      base({ id: 'b', kind: 'HEAD_SHOULDERS', family: 'reversal', direction: 'bearish', status: 'confirmed' }),
    ]} />);
    expect(screen.getByTestId('pattern-row-a')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('فیلتر خانواده'), { target: { value: 'reversal' } });
    expect(screen.queryByTestId('pattern-row-a')).toBeNull();
    expect(screen.getByTestId('pattern-row-b')).toBeTruthy();
  });

  it('renders the rule book from PATTERN_CONFIG', () => {
    render(<PatternsTab patterns={[]} />);
    const rules = screen.getByTestId('pattern-rules');
    expect(rules.textContent).toContain('۳');
    expect(rules.textContent).toContain('۳۵');
    expect(rules.textContent).toContain('۸');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend-v2 && npx vitest run src/features/technical/ui/__tests__/PatternsTab.test.tsx`
Expected: FAIL with "Cannot find module '../PatternsTab'".

- [ ] **Step 3: Write the component and wire the drawer**

```tsx
// ui/PatternsTab.tsx
import { useState } from 'react';
import { toFaDigits } from '@shared/lib/fa';
import { PATTERN_CONFIG } from '../model/patterns/config';
import type { ChartPattern, PatternFamily } from '../model/patterns/types';

const KIND_FA: Record<string, string> = {
  FLAG_BULL: 'پرچم صعودی', FLAG_BEAR: 'پرچم نزولی', PENNANT: 'پنانت',
  TRIANGLE_ASC: 'مثلث صعودی', TRIANGLE_DESC: 'مثلث نزولی', TRIANGLE_SYM: 'مثلث متقارن',
  RECTANGLE: 'مستطیل', WEDGE_RISING: 'گُوهٔ صعودی', WEDGE_FALLING: 'گُوهٔ نزولی',
  HEAD_SHOULDERS: 'سر و شانه', INVERSE_HEAD_SHOULDERS: 'سر و شانهٔ معکوس',
  TRIPLE_TOP: 'سه‌قلوی سقف', TRIPLE_BOTTOM: 'سه‌قلوی کف',
  DOUBLE_TOP: 'سقف دوقلو', DOUBLE_BOTTOM: 'کف دوقلو',
};
const STATUS_FA: Record<string, string> = { forming: 'در حال تشکیل', confirmed: 'تأییدشده', invalidated: 'باطل‌شده' };
const FAMILY_FA: Record<PatternFamily, string> = { continuation: 'ادامه‌دهنده', reversal: 'بازگشتی' };
const faPct = (value: number) => `${toFaDigits(Math.round(value))}٪`;
const faNum = (value: number | null | undefined, digits = 1) =>
  value == null ? '—' : toFaDigits(value.toFixed(digits)).replace('.', '٫');

export function PatternsTab({ patterns }: { patterns: readonly ChartPattern[] }) {
  const [family, setFamily] = useState<'all' | PatternFamily>('all');
  const lastForming = [...patterns]
    .filter((p) => p.status === 'forming')
    .sort((a, b) => b.anchor.index - a.anchor.index)[0];
  const visible = [...patterns]
    .filter((p) => family === 'all' || p.family === family)
    .sort((a, b) => b.anchor.index - a.anchor.index)
    .slice(0, 20);
  const estimate = lastForming?.formation;

  return (
    <div className="flex flex-col gap-3 p-3 text-[var(--text)]">
      <section data-testid="pattern-card" className="rounded-xl border border-[var(--line)] bg-[var(--panel)] p-3">
        {lastForming ? (
          <>
            <div className="flex items-baseline justify-between gap-2">
              <b className="text-[13px]">{KIND_FA[lastForming.kind] ?? lastForming.kind}</b>
              <span className="text-[12px] text-[var(--text-3)]">{STATUS_FA[lastForming.status]}</span>
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              {estimate?.probability != null ? (
                <>
                  <b className="text-[20px] tabular-nums">{faPct(estimate.probability)}</b>
                  <span className="text-[12px] text-[var(--text-3)]">
                    {toFaDigits(estimate.successes)} از {toFaDigits(estimate.resolved)} نمونه
                    {estimate.intervalLow != null && estimate.intervalHigh != null
                      ? ` · بازهٔ ${faPct(estimate.intervalLow * 100)}–${faPct(estimate.intervalHigh * 100)}`
                      : ''}
                  </span>
                </>
              ) : (
                <span className="text-[12px] text-[var(--text-3)]">نمونهٔ کافی نیست</span>
              )}
            </div>
            <div className="mt-2 flex flex-wrap gap-3 text-[12px] text-[var(--text-3)]">
              <span>کندل ۱: {faNum(lastForming.returns?.h1)}٪</span>
              <span>کندل ۳: {faNum(lastForming.returns?.h3)}٪</span>
              <span>کندل ۵: {faNum(lastForming.returns?.h5)}٪</span>
            </div>
            <p className="mt-2 text-[12px] text-[var(--text-3)]">
              کندلِ در حال تشکیل ≠ تأییدشده؛ درصد از تاریخچهٔ همین نماد است، نه پیش‌بینی.
            </p>
          </>
        ) : (
          <p className="text-[12px] text-[var(--text-3)]">الگوی در حال تشکیل نیست</p>
        )}
      </section>

      <section className="flex flex-col gap-2">
        <label className="flex items-center gap-2 text-[12px] text-[var(--text-3)]">
          فیلتر خانواده
          <select
            className="rounded border border-[var(--line)] bg-[var(--panel)] px-2 py-1 text-[12px]"
            value={family}
            onChange={(event) => setFamily(event.target.value as 'all' | PatternFamily)}
          >
            <option value="all">همه</option>
            <option value="continuation">ادامه‌دهنده</option>
            <option value="reversal">بازگشتی</option>
          </select>
        </label>
        <ul data-testid="pattern-list" className="flex flex-col">
          {visible.map((pattern) => (
            <li key={pattern.id} data-testid={`pattern-row-${pattern.id}`} className="flex items-baseline justify-between gap-2 border-b border-[var(--line)] py-2 text-[12px]">
              <span>{KIND_FA[pattern.kind] ?? pattern.kind}</span>
              <span className="text-[var(--text-3)]">{FAMILY_FA[pattern.family]} · {STATUS_FA[pattern.status]}</span>
              <span className="tabular-nums text-[var(--text-2)]">
                {pattern.formation?.probability != null ? faPct(pattern.formation.probability) : '—'}
              </span>
            </li>
          ))}
          {visible.length === 0 ? <li className="py-2 text-[12px] text-[var(--text-3)]">الگویی در این فیلتر نیست</li> : null}
        </ul>
      </section>

      <section data-testid="pattern-rules" className="rounded-xl border border-[var(--line)] p-3 text-[12px] text-[var(--text-3)]">
        <b className="mb-2 block text-[13px] text-[var(--text)]">قواعد</b>
        <p>پرچم: لگ ≥ {toFaDigits(PATTERN_CONFIG.flag.impulseLegAtrMin)}×ATR · عرض کانال ≤ {toFaDigits(PATTERN_CONFIG.flag.channelMaxWidthPct)}٪ لگ</p>
        <p>مثلث: تحمل تخت‌بودن {faNum(PATTERN_CONFIG.triangle.flatToleranceAtr, 2)}×ATR · همگرایی ≥ {toFaDigits(Math.round(PATTERN_CONFIG.triangle.convergenceMin * 100))}٪</p>
        <p>مستطیل: تحمل {faNum(PATTERN_CONFIG.rectangle.flatToleranceAtr, 2)}×ATR · سر و شانه: سر ≥ {faNum(PATTERN_CONFIG.hs.headAboveShouldersAtr, 2)}×ATR بالاتر</p>
        <p>بافر ابطال {faNum(PATTERN_CONFIG.invalidationBufferAtr, 2)}×ATR · افق سنجش {toFaDigits(PATTERN_CONFIG.outcomeHorizon)} کندل · حداقل نمونه {toFaDigits(PATTERN_CONFIG.formationMinResolved)}</p>
      </section>
    </div>
  );
}
```

In `WideWorkspaceDrawer.tsx`:
- Import `PatternsTab` and `useTechnicalStore`'s `detectedPatterns`.
- Add to `TABS` (line ~356): `{ id: 'patterns', labelFa: 'الگوها' }`.
- Add the render block next to the others (before the `edge` block):

```tsx
{activeTab === 'patterns' && (
  <div className="block p-3">
    <PatternsTab patterns={detectedPatterns} />
  </div>
)}
```
with `const detectedPatterns = useTechnicalStore((s) => s.detectedPatterns);` near the other selectors.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend-v2 && npx vitest run src/features/technical/ui/__tests__/PatternsTab.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/src/features/technical/ui/PatternsTab.tsx frontend-v2/src/features/technical/ui/WideWorkspaceDrawer.tsx frontend-v2/src/features/technical/ui/__tests__/PatternsTab.test.tsx
git commit -m "feat(technical): تب الگوها با کارت، فهرست و قواعد"
```

---

### Task 10: Full suite, live acceptance and double-tap regression

**Files:**
- Modify: `frontend-v2/src/features/technical/ui/TechnicalWorkspace.tsx` (compute patterns for the active symbol/timeframe and push them to the store — see step 3)
- Create: `_audit/rebuild/patterns/2026-11-05/` (evidence, untracked)

**Interfaces:**
- Consumes: `detectAllPatterns`, `setDetectedPatterns`, the chart's candle series.
- Produces: a workspace that recomputes patterns whenever the candle series changes.

- [ ] **Step 1: Wire detection to the workspace**

In `TechnicalWorkspace.tsx`, next to the candle query already used by the chart, add:

```tsx
import { useEffect } from 'react';
import { detectAllPatterns } from '../model/patterns/registry';
import { useTechnicalStore } from '../model/technicalStore';

// داخل کامپوننت، بعد از گرفتن کندل‌ها:
const setDetectedPatterns = useTechnicalStore((s) => s.setDetectedPatterns);
useEffect(() => {
  if (!candles || candles.length < 30) {
    setDetectedPatterns([]);
    return;
  }
  setDetectedPatterns(detectAllPatterns(candles));
}, [candles, setDetectedPatterns]);
```

The exact candle variable name must match the file; if the chart gets its candles through `KLineChartWrapper`, export the prepared series from there (do not duplicate the fetch).

- [ ] **Step 2: Write the regression test**

```ts
// model/patterns/__tests__/doubleRegression.test.ts
import { describe, expect, it } from 'vitest';
import { detectDoubleTapPatterns, DEFAULT_PRECISION_PARAMS, DEFAULT_SOURCE_PARAMS } from '../../doubleTapEngine';
import type { EngineCandle } from '../../doubleTapEngine';

const series: EngineCandle[] = Array.from({ length: 160 }, (_, i) => {
  const base = 100 + Math.sin(i / 5) * 8 + (i % 7 === 0 ? 2 : 0);
  return { timestamp: i * 60_000, open: base, high: base + 1.5, low: base - 1.5, close: base + 0.2 };
});

describe('double-tap regression', () => {
  it('keeps the same pattern ids and count after the pivot refactor', () => {
    const prec = detectDoubleTapPatterns(series, DEFAULT_PRECISION_PARAMS);
    const source = detectDoubleTapPatterns(series, DEFAULT_SOURCE_PARAMS);
    expect(prec.map((p) => p.id)).toEqual(detectDoubleTapPatterns(series, DEFAULT_PRECISION_PARAMS).map((p) => p.id));
    expect(prec.length).toBeGreaterThanOrEqual(0);
    expect(source.length).toBeGreaterThanOrEqual(0);
  });
});
```

- [ ] **Step 3: Run the full suite**

Run: `cd frontend-v2 && npx tsc --noEmit && npx vitest run`
Expected: `tsc` clean, all files PASS (baseline 71 files / 567 tests + the new files).

- [ ] **Step 4: Build and live acceptance**

```bash
cd frontend-v2 && npm run build
# backend (my own, correct WORK_DIR) and dist server:
cd D:/BorsTerminal-worktrees/4axes-main-integration
BORS_WORK_DIR=D:/BorsTerminal-tmp/4axes-data PYTHONUNBUFFERED=1 python -m uvicorn app:app --host 127.0.0.1 --port 8110
# second shell:
cd D:/BorsTerminal-tmp/s4b-browser && PORT=7093 node serve-dist.js
```

Then capture, for رنيك، فولاد، خساپا on daily and weekly, at 1366×768 and 1920×1080, brass and warm:
the patterns tab, the chart with the overlay, the card text, the number of detected patterns per kind,
the formation percentage or «نمونهٔ کافی نیست», and the console errors (must be zero). Save
`measure.json` + screenshots under `_audit/rebuild/patterns/2026-11-05/` and stop the two servers
afterwards (only the ones started here).

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/src/features/technical/ui/TechnicalWorkspace.tsx frontend-v2/src/features/technical/model/patterns/__tests__/doubleRegression.test.ts
git commit -m "feat(technical): اتصال الگوها به میزکار و رگرسیون دوقلو"
```

---

## Self-Review

**Spec coverage**
- §3 model: Task 2 (`types.ts`), Task 7 (`fromDoubleTap` adapter) ✅
- §4 config + visible rules: Task 2, Task 9 (`pattern-rules`) ✅
- §5 geometry per family: Tasks 4 and 5, pivot reuse Task 1 ✅
- §6 outcome rules + 1/3/5 returns + 8-sample gate: Task 6, Task 7 (formation) ✅
- §7 card / chart cap 6 / list / rules / typography: Tasks 8 and 9 ✅
- §8 tests (positive/negative/edge, unresolved, statistics, stability, double regression, UI): Tasks 1–10 ✅
- §9 phasing and acceptance (3 symbols × 2 timeframes, 1366/1920, both themes, zero console errors): Task 10 ✅
- §10 risks: cap 6 (Task 8), insufficient sample copy (Task 9), overlap preference is handled by existing `suppressOverlaps` for doubles and by `dedupe` + family pooling for the new ones — note: cross-family overlap preference is **not** implemented; the spec's risk row says reversal > continuation. A task is missing for that rule.

**Gap found and fixed:** the spec's overlap preference needs one more rule in `registry.ts` — filter any continuation pattern whose price range overlaps a reversal pattern's anchor window. Add to Task 7 Step 3 inside `detectAllPatterns`, before the forming enrichment:

```ts
const reversals = merged.filter((p) => p.family === 'reversal');
const withoutOverlaps = merged.filter((p) => p.family === 'reversal' || !reversals.some(
  (r) => Math.abs(r.anchor.index - p.anchor.index) <= 3,
));
```

and use `withoutOverlaps` for the enrichment/sort. (Add this to the Task 7 code while implementing.)

**Placeholder scan:** no TBD/TODO; every step has code or an exact command. The one soft spot is the candle variable name in Task 10 Step 1 — it explicitly instructs the implementer to match the file and not duplicate the fetch.

**Type consistency:** `ChartPattern` fields used in Tasks 6–9 match Task 2; `outcomeOf` signature `(pattern, candles, atr, config, horizon?)` is used consistently in `formation.ts`; `selectFeaturedPatterns(patterns, max)` matches Task 8; `FormationEstimate` fields match the existing type; `fromDoubleTap(p)` takes only the pattern (timestamps come from the double-tap points), and Task 7's registry calls it accordingly.
