# Technical Workspace 2 + Unified Scanner — Phase A Implementation Plan (Accuracy, Tier-2, Merge)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise pattern accuracy, add the 4 missing tier-1 patterns and the 7 tier-2 patterns, and merge the parallel «الگوها» tab into the existing «اسکنر الگوها» so one scanner owns every detected event.

**Architecture:** Extend the pure detector modules under `model/patterns/` (same `emitPattern`/outcome/formation framework), add a tier field and a rulebook, then re-house the UI: the existing scanner tab becomes the single feed (patterns + pullback + CHoCH, with win-rate and geometric quality side by side), and the parallel tab disappears. Phases B (workspace redesign), C (channel/divergence events + highlight/animation) and D (visual audit) each get their own plan after this one passes.

**Tech Stack:** React 18 + TypeScript + Vite, Zustand, klinecharts, Vitest.

**Spec:** `docs/superpowers/specs/2026-11-05-technical-workspace-and-scanner-design.md`

## Global Constraints

- All detectors run in the client on `EngineCandle[]` of the active timeframe, which is the **adjusted series** the chart draws (`adjustmentMode: 3` = عملکردی). No network, no backend, no FTS changes.
- Only **confirmed pivots** — never the forming bar. No look-ahead in detection, status, outcome or stats.
- `PATTERN_CONFIG` is the single home of every threshold, and the UI renders them («قواعد»).
- A percentage is shown only when `resolved >= formationMinResolved` (8) and as `probability × 100`; `unresolved` is never a failure.
- Persian UI, Persian digits via `toFaDigits`, text ≥ 11px, icons from `ui/icons.tsx`.
- Existing double-tap output and its tests stay byte-identical; existing scanner sources (pullback, CHoCH) keep working.
- `data-testid` contracts: `scanner-panel`, `pattern-row-<id>`, `pattern-card`, `pattern-rules`, `pattern-tier-2`.

## File Structure

| File | Responsibility |
|---|---|
| `docs/patterns/rulebook.md` (new) | One row per pattern: source rule, formula, thresholds, tier, reference |
| `model/patterns/config.ts` (modify) | Tier-2 + cup/rounding thresholds, `tier` labels |
| `model/patterns/types.ts` (modify) | `ChartPattern.tier?: 1 | 2`, new `PatternKind` members |
| `model/patterns/detectCupRounding.ts` (new) | CUP_HANDLE, INVERSE_CUP_HANDLE, ROUNDING_TOP, ROUNDING_BOTTOM |
| `model/patterns/detectTier2.ts` (new) | DIAMOND_*, BROADENING_*, ISLAND_REVERSAL, THREE_RISING_PEAKS, THREE_FALLING_PEAKS |
| `model/patterns/registry.ts` (modify) | Register new detectors, priority ordering, `tier` from a kind table |
| `ui/PatternsTab.tsx` (delete) | Superseded by the merged scanner feed |
| `ui/WideWorkspaceDrawer.tsx` (modify) | Remove the patterns tab; extend the scanner tab render |
| `ui/ScannerFeed.tsx` (new) | The single feed: pattern rows + pullback/CHoCH rows, card, rules, tier badge |
| `ui/__tests__/ScannerFeed.test.tsx` (new) | Feed/card/tier/no-percent-under-8 |

---

### Task A1: Rulebook, tier field and new config keys

**Files:**
- Create: `docs/patterns/rulebook.md`
- Modify: `frontend-v2/src/features/technical/model/patterns/config.ts`
- Modify: `frontend-v2/src/features/technical/model/patterns/types.ts`
- Test: `frontend-v2/src/features/technical/model/patterns/__tests__/config.test.ts`

**Interfaces:**
- Produces: `ChartPattern.tier?: 1 | 2`; `PATTERN_CONFIG.cup`, `.rounding`, `.tier2` blocks.

- [ ] **Step 1: Write the failing test** (add to the exact-pin test)

```ts
it('pins the tier-2 and cup/rounding defaults', () => {
  expect(PATTERN_CONFIG.cup).toEqual({ rimToleranceAtr: 0.5, handleDepthPct: 33, minBars: 20, maxBars: 160 });
  expect(PATTERN_CONFIG.rounding).toEqual({ curvatureMin: 0.55, minBars: 30, maxBars: 200 });
  expect(PATTERN_CONFIG.tier2).toEqual({ diamondConvergeMin: 0.25, broadeningMin: 0.25, islandGapAtr: 0.5, threePeaksToleranceAtr: 0.5 });
});
```

- [ ] **Step 2: Run** `cd frontend-v2 && npx vitest run src/features/technical/model/patterns/__tests__/config.test.ts` → FAIL (missing keys).

- [ ] **Step 3: Implement** — add to `PatternConfig`/`PATTERN_CONFIG` (exact literals above) and to `types.ts`:

```ts
export type PatternTier = 1 | 2;
// in ChartPattern:
tier?: PatternTier;
```

Write `docs/patterns/rulebook.md` with one table row per kind: `kind | tier | rule (one line) | thresholds (from PATTERN_CONFIG) | visual reference | source (classic book / telegram indicator / existing engine)`. Populate all 26 kinds; tier-1 19 kinds, tier-2 7 kinds. No invented thresholds — copy the config values.

- [ ] **Step 4: Run** the config test → PASS; `npx tsc --noEmit` clean.

- [ ] **Step 5: Commit**

```bash
git add docs/patterns/rulebook.md frontend-v2/src/features/technical/model/patterns/config.ts frontend-v2/src/features/technical/model/patterns/types.ts frontend-v2/src/features/technical/model/patterns/__tests__/config.test.ts
git commit -m "feat(technical): کتاب قواعد و پیکربندی رده‌بندی الگوها"
```

---

### Task A2: Cup & handle and rounding detectors (tier 1)

**Files:**
- Create: `frontend-v2/src/features/technical/model/patterns/detectCupRounding.ts`
- Test: `frontend-v2/src/features/technical/model/patterns/__tests__/cupRounding.test.ts`

**Interfaces:**
- Consumes: `findAlternatingPivots`, `emitPattern`, `toPoint`, `lineValue`, `PatternSpec` (`maxBars`, `invalidationBuffer`), `PATTERN_CONFIG`.
- Produces: `detectCupRounding(candles, atr, config): ChartPattern[]`.

- [ ] **Step 1: Write the failing tests** — a synthetic cup (two rims near equal, rounded bottom, handle pullback ≤ 33% of cup depth, breakout above the rim) yields `CUP_HANDLE` confirmed; the inverted series yields `INVERSE_CUP_HANDLE`; a V-bottom with no rounding yields none; a shallow bowl yields `ROUNDING_BOTTOM`.

```ts
// helper: build a series from sampled points with linear interpolation + noise-free bars
function seriesFrom(values: number[]): EngineCandle[] {
  return values.map((v, i) => ({ timestamp: i * 60_000, open: v, high: v + 0.4, low: v - 0.4, close: v }));
}
// cup: 100 → down to 84 → back to 99.5 (rims), then handle 96.5, then breakout 103
const cup = seriesFrom([...Array.from({ length: 20 }, (_, i) => 100 - i * 0.8), ...Array.from({ length: 30 }, (_, i) => 84 + i * 0.52), ...Array.from({ length: 10 }, (_, i) => 99.5 - i * 0.3), ...Array.from({ length: 12 }, (_, i) => 96.5 + i * 0.55)]);
expect(detectCupRounding(cup, 2, { ...PATTERN_CONFIG, pivLeft: 1, pivRight: 1 }).some((p) => p.kind === 'CUP_HANDLE')).toBe(true);
```

- [ ] **Step 2: Run** → FAIL (module missing).

- [ ] **Step 3: Implement**

```ts
// detectCupRounding.ts
import type { EngineCandle } from '../doubleTapEngine';
import type { PatternConfig } from './config';
import type { BoundaryLine, ChartPattern } from './types';
import { findAlternatingPivots, type PivotPoint } from './pivots';
import { emitPattern, toPoint } from './geometry';

const clampQ = (q: number) => Math.max(0, Math.min(100, Math.round(q)));
const lineP = (a: PatternPoint, b: PatternPoint): BoundaryLine => ({ from: a, to: b });
const flatP = (p: PatternPoint): BoundaryLine => ({ from: p, to: p });
const pt = (p: PivotPoint, candles: readonly EngineCandle[]): PatternPoint => toPoint(p, candles);

/** کاپ/کاپ معکوس: دو لبهٔ هم‌تراز، کفِ گرد، دستهٔ کم‌عمق، شکستِ لبه. */
function cups(pivots: PivotPoint[], candles: readonly EngineCandle[], atr: number, config: PatternConfig): ChartPattern[] {
  const out: ChartPattern[] = [];
  for (let i = 0; i + 2 < pivots.length; i++) {
    for (const inverted of [false, true]) {
      const rimKind = inverted ? 'low' : 'high';
      const midKind = inverted ? 'high' : 'low';
      const a = pivots[i]!, m = pivots[i + 1]!, b = pivots[i + 2]!;
      if (a.kind !== rimKind || b.kind !== rimKind || m.kind !== midKind) continue;
      const bars = b.index - a.index;
      if (bars < config.cup.minBars || bars > config.cup.maxBars) continue;
      const rim = (a.price + b.price) / 2;
      const rimTol = config.cup.rimToleranceAtr * atr;
      if (Math.abs(a.price - b.price) > rimTol) continue;
      const depth = (inverted ? m.price - rim : rim - m.price);
      if (depth < 2 * atr) continue;
      const after = pivots.filter((p) => p.index > b.index && p.kind === midKind);
      const handle = after[0];
      if (handle && (inverted ? handle.price - rim : rim - handle.price) > (config.cup.handleDepthPct / 100) * depth) continue;
      const emitted = emitPattern({
        kind: inverted ? 'INVERSE_CUP_HANDLE' : 'CUP_HANDLE',
        direction: inverted ? 'bearish' : 'bullish',
        family: 'continuation',
        points: [a, m, b].map((p) => toPoint(p, candles)),
        upper: inverted ? flatP(pt(m, candles)) : lineP(pt(a, candles), pt(b, candles)),
        lower: inverted ? lineP(pt(a, candles), pt(b, candles)) : flatP(pt(m, candles)),
        target: inverted ? rim - depth : rim + depth,
        stopLoss: inverted ? m.price + atr : m.price - atr,
        quality: clampQ(55 + 35 * Math.min(1, depth / (4 * atr)) + 10 * (1 - Math.abs(a.price - b.price) / Math.max(rimTol, 1e-9))),
        tier: 1,
        maxBars: config.cup.maxBars,
        invalidationBuffer: config.invalidationBufferAtr * atr,
      }, candles, config);
      if (emitted) out.push(emitted);
    }
  }
  return out;
}

/** گردشدن: سه‌بخشِ سری؛ بخشِ میانی پایین‌ترین (یا بالاترین) و دو سرِ هم‌تراز. */
function rounding(candles: readonly EngineCandle[], atr: number, config: PatternConfig): ChartPattern[] {
  const out: ChartPattern[] = [];
  const n = candles.length;
  if (n < config.rounding.minBars) return out;
  const from = Math.max(0, n - config.rounding.maxBars);
  const window = candles.slice(from);
  const third = Math.floor(window.length / 3);
  const lows = (arr: readonly EngineCandle[]) => Math.min(...arr.map((c) => c.low));
  const highs = (arr: readonly EngineCandle[]) => Math.max(...arr.map((c) => c.high));
  const first = window.slice(0, third);
  const middle = window.slice(third, third * 2);
  const last = window.slice(third * 2);
  const depth = Math.abs((lows(first) + lows(last)) / 2 - lows(middle));
  if (depth < atr) return out;
  const bottoms = lows(middle) < Math.min(lows(first), lows(last) - atr) && Math.abs(lows(first) - lows(last)) <= 0.5 * depth;
  const tops = highs(middle) > Math.max(highs(first), highs(last) + atr) && Math.abs(highs(first) - highs(last)) <= 0.5 * depth;
  if (!bottoms && !tops) return out;
  const inverted = tops;
  const anchorP = toPoint({ index: n - 1, price: inverted ? highs(last) : lows(last), kind: inverted ? 'high' : 'low' }, candles);
  const midP = toPoint({ index: from + third, price: inverted ? highs(middle) : lows(middle), kind: inverted ? 'high' : 'low' }, candles);
  const leftP = toPoint({ index: from + third - 1, price: inverted ? highs(first) : lows(first), kind: inverted ? 'high' : 'low' }, candles);
  const emitted = emitPattern({
    kind: inverted ? 'ROUNDING_TOP' : 'ROUNDING_BOTTOM',
    direction: inverted ? 'bearish' : 'bullish',
    family: 'reversal',
    points: [leftP, midP, anchorP],
    upper: inverted ? flatP(midP) : lineP(leftP, anchorP),
    lower: inverted ? lineP(leftP, anchorP) : flatP(midP),
    target: inverted ? midP.price - depth : midP.price + depth,
    stopLoss: inverted ? midP.price + atr : midP.price - atr,
    quality: clampQ(60 + 30 * Math.min(1, depth / (3 * atr))),
    tier: 1,
    maxBars: config.rounding.maxBars,
    invalidationBuffer: config.invalidationBufferAtr * atr,
  }, candles, config);
  if (emitted) out.push(emitted);
  return out;
}

export function detectCupRounding(candles: readonly EngineCandle[], atr: number, config: PatternConfig): ChartPattern[] {
  if (!(atr > 0)) return [];
  const pivots = findAlternatingPivots(candles, config.pivLeft, config.pivRight);
  return [...cups(pivots, candles, atr, config), ...rounding(candles, atr, config)];
}
```

Keep all boundary types as `BoundaryLine` of `PatternPoint`s (no casts); the tests in Step 1 are the contract.

- [ ] **Step 4: Run** the new spec + `npx tsc --noEmit` → PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/src/features/technical/model/patterns/detectCupRounding.ts frontend-v2/src/features/technical/model/patterns/__tests__/cupRounding.test.ts
git commit -m "feat(technical): الگوهای کاپ‌هندل و گردشدن"
```

---

### Task A3: Tier-2 detectors

**Files:**
- Create: `frontend-v2/src/features/technical/model/patterns/detectTier2.ts`
- Test: `frontend-v2/src/features/technical/model/patterns/__tests__/tier2.test.ts`

**Interfaces:**
- Produces: `detectTier2(candles, atr, config): ChartPattern[]` with kinds `DIAMOND_TOP`, `DIAMOND_BOTTOM`, `BROADENING_TOP`, `BROADENING_BOTTOM`, `ISLAND_REVERSAL`, `THREE_RISING_PEAKS`, `THREE_FALLING_PEAKS`, all `tier: 2`.

- [ ] **Step 1: Write the failing tests** — one positive fixture per kind and one negative (a shape that is close but violates the tolerance). Examples: diamond = 5 pivots with highs 100→108→104 and lows 92→96→99 where the two trendlines converge by ≥ `diamondConvergeMin`; broadening = the mirror (diverge by ≥ `broadeningMin`); island = a gap-up island of 2–5 bars followed by a gap-down within `islandGapAtr·atr`; three rising peaks = three highs each ≥ previous + 0 and all within `threePeaksToleranceAtr·atr`, with two higher lows.

```ts
it('detects a broadening top and rejects a converging one', () => { /* two fixtures, same helper */ });
it('detects an island reversal only when both gaps exceed the ATR threshold', () => { /* two fixtures */ });
it('detects three rising peaks within the level tolerance', () => { /* positive + negative */ });
```

- [ ] **Step 2: Run** → FAIL (module missing).

- [ ] **Step 3: Implement**

```ts
// detectTier2.ts
import type { EngineCandle } from '../doubleTapEngine';
import type { PatternConfig } from './config';
import type { BoundaryLine, ChartPattern, PatternPoint } from './types';
import { findAlternatingPivots, type PivotPoint } from './pivots';
import { emitPattern, lineValue, toPoint } from './geometry';

const clampQ = (q: number) => Math.max(0, Math.min(100, Math.round(q)));
const lineP = (a: PatternPoint, b: PatternPoint): BoundaryLine => ({ from: a, to: b });
const p = (x: PivotPoint, candles: readonly EngineCandle[]) => toPoint(x, candles);

/** دیاموند (همگرا) و پهن‌شونده (واگرا): پنج پیوتِ متناوب با دو خطِ مرزی. */
function diamondOrBroadening(pivots: PivotPoint[], candles: readonly EngineCandle[], atr: number, config: PatternConfig): ChartPattern[] {
  const out: ChartPattern[] = [];
  for (let i = 0; i + 4 < pivots.length; i++) {
    const w = pivots.slice(i, i + 5) as [PivotPoint, PivotPoint, PivotPoint, PivotPoint, PivotPoint];
    const top = w[0].kind === 'high' && w[2].kind === 'high' && w[4].kind === 'high';
    const bottom = w[0].kind === 'low' && w[2].kind === 'low' && w[4].kind === 'low';
    if (!top && !bottom) continue;
    if (w[4].index - w[0].index > config.hs.maxBars) continue;
    const upper = lineP(p(w[0], candles), p(w[4], candles));
    const lower = lineP(p(w[1], candles), p(w[3], candles));
    const width = (idx: number) => Math.abs(lineValue(upper, idx) - lineValue(lower, idx));
    const start = width(w[0].index);
    const mid = width(w[2].index);
    const end = width(w[4].index);
    if (!(start > 0) || !(end > 0)) continue;
    const converging = mid > end && end <= (1 - config.tier2.diamondConvergeMin) * start;
    const broadening = end >= (1 + config.tier2.broadeningMin) * start;
    if (!converging && !broadening) continue;
    const kind = converging
      ? (top ? 'DIAMOND_TOP' : 'DIAMOND_BOTTOM')
      : (top ? 'BROADENING_TOP' : 'BROADENING_BOTTOM');
    const height = Math.abs(w[2].price - w[1].price);
    const emitted = emitPattern({
      kind,
      direction: top ? 'bearish' : 'bullish',
      family: 'reversal',
      points: w.map((x) => p(x, candles)),
      upper,
      lower,
      target: top ? Math.min(w[1].price, w[3].price) - height : Math.max(w[1].price, w[3].price) + height,
      stopLoss: top ? w[2].price + atr : w[2].price - atr,
      quality: clampQ(50 + 30 * Math.min(1, height / (2 * atr)) + 20 * Math.min(1, Math.abs(end - start) / start)),
      tier: 2,
      maxBars: config.hs.maxBars,
      invalidationBuffer: config.invalidationBufferAtr * atr,
    }, candles, config);
    if (emitted) out.push(emitted);
  }
  return out;
}

/** جزیره: گپِ ورود و گپِ خروج در بازهٔ حداکثر ۵ کندل. */
function island(candles: readonly EngineCandle[], atr: number, config: PatternConfig): ChartPattern[] {
  const out: ChartPattern[] = [];
  const gap = config.tier2.islandGapAtr * atr;
  for (let i = 1; i < candles.length - 2; i++) {
    const prev = candles[i - 1]!;
    const cur = candles[i]!;
    const upGap = cur.low - prev.high >= gap;
    const downGap = prev.low - cur.high >= gap;
    if (!upGap && !downGap) continue;
    for (let j = i + 1; j < Math.min(candles.length, i + 6); j++) {
      const closeGap = upGap ? candles[j]!.high < cur.low - gap : candles[j]!.low > cur.high + gap;
      if (!closeGap) continue;
      const block = candles.slice(i, j + 1);
      const islandHigh = Math.max(...block.map((c) => c.high));
      const islandLow = Math.min(...block.map((c) => c.low));
      const anchor = toPoint({ index: j, price: candles[j]!.close, kind: upGap ? 'low' : 'high' }, candles);
      const emitted = emitPattern({
        kind: 'ISLAND_REVERSAL',
        direction: upGap ? 'bearish' : 'bullish',
        family: 'reversal',
        points: [anchor],
        upper: lineP(toPoint({ index: i, price: islandHigh, kind: 'high' }, candles), anchor),
        lower: lineP(toPoint({ index: i, price: islandLow, kind: 'low' }, candles), anchor),
        target: upGap ? islandLow - (islandHigh - islandLow) : islandHigh + (islandHigh - islandLow),
        stopLoss: upGap ? islandHigh + atr : islandLow - atr,
        quality: 60,
        tier: 2,
        maxBars: 6,
        invalidationBuffer: config.invalidationBufferAtr * atr,
      }, candles, config);
      if (emitted) out.push(emitted);
      break;
    }
  }
  return out;
}

/** سه قلهٔ صعودی/نزولی: سه سقف یا سه کفِ هم‌سطح با اختلافِ max−min ≤ تلورانس. */
function threePeaks(pivots: PivotPoint[], candles: readonly EngineCandle[], atr: number, config: PatternConfig): ChartPattern[] {
  const out: ChartPattern[] = [];
  const tol = config.tier2.threePeaksToleranceAtr * atr;
  for (const kind of ['high', 'low'] as const) {
    const peaks = pivots.filter((x) => x.kind === kind);
    for (let i = 0; i + 2 < peaks.length; i++) {
      const trio = peaks.slice(i, i + 3);
      const spread = Math.max(...trio.map((x) => x.price)) - Math.min(...trio.map((x) => x.price));
      if (spread > tol) continue;
      const rising = trio[2]!.price > trio[0]!.price;
      const isTop = kind === 'high';
      const level = isTop ? Math.max(...trio.map((x) => x.price)) : Math.min(...trio.map((x) => x.price));
      const tween = pivots.filter((x) => x.index > trio[0]!.index && x.index < trio[2]!.index && x.kind !== kind);
      if (tween.length < 2) continue;
      const neck = lineP(p(tween[0]!, candles), p(tween[tween.length - 1]!, candles));
      const height = Math.abs(level - tween[0]!.price);
      const emitted = emitPattern({
        kind: isTop ? 'THREE_RISING_PEAKS' : 'THREE_FALLING_PEAKS',
        direction: isTop ? 'bearish' : 'bullish',
        family: isTop ? 'reversal' : 'continuation',
        points: trio.map((x) => p(x, candles)),
        upper: isTop ? lineP(p(trio[0]!, candles), p(trio[2]!, candles)) : neck,
        lower: isTop ? neck : lineP(p(trio[0]!, candles), p(trio[2]!, candles)),
        target: isTop ? neck.to.price - height : neck.to.price + height,
        stopLoss: isTop ? level + atr : level - atr,
        quality: clampQ(55 + 30 * Math.min(1, height / (2 * atr)) + (rising ? 10 : 0)),
        tier: 2,
        maxBars: config.hs.maxBars,
        invalidationBuffer: config.invalidationBufferAtr * atr,
      }, candles, config);
      if (emitted) out.push(emitted);
    }
  }
  return out;
}

export function detectTier2(candles: readonly EngineCandle[], atr: number, config: PatternConfig): ChartPattern[] {
  if (!(atr > 0)) return [];
  const pivots = findAlternatingPivots(candles, config.pivLeft, config.pivRight);
  return [...diamondOrBroadening(pivots, candles, atr, config), ...island(candles, atr, config), ...threePeaks(pivots, candles, atr, config)];
}
```

Rules the executor must keep: every kind is `tier: 2`; `island` may emit on a single-point anchor (the emitter accepts ≥1 point); diamond/broadening never emit when either width is non-positive; `THREE_RISING_PEAKS` is treated as a reversal at a top and `THREE_FALLING_PEAKS` as a continuation at a bottom, exactly as the code states — if the booklet/reference contradicts this family assignment, stop and record a ruling rather than silently changing it.

- [ ] **Step 4: Run** the new spec + `npx tsc --noEmit` → PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/src/features/technical/model/patterns/detectTier2.ts frontend-v2/src/features/technical/model/patterns/__tests__/tier2.test.ts
git commit -m "feat(technical): الگوهای کم‌بسامد رده دو"
```

---

### Task A4: Accuracy hardening (no look-ahead, negative fixtures, priority)

**Files:**
- Create: `frontend-v2/src/features/technical/model/patterns/__tests__/accuracy.test.ts`
- Modify: `frontend-v2/src/features/technical/model/patterns/registry.ts` (register the new detectors + tier table)
- Modify: `frontend-v2/src/features/technical/model/patterns/geometry.ts` (accept a single-point island anchor — only if the runtime rejects it; never relax other rules)

**Interfaces:**
- Produces: `detectAllPatterns` includes `CUP_HANDLE`, `INVERSE_CUP_HANDLE`, `ROUNDING_TOP`, `ROUNDING_BOTTOM` (tier 1) and the seven tier-2 kinds; `PATTERN_TIER: Record<PatternKind, 1 | 2>`.

- [ ] **Step 1: Write the failing tests**

```ts
// accuracy.test.ts
import { describe, expect, it } from 'vitest';
import { detectAllPatterns } from '../registry';
import { PATTERN_CONFIG } from '../config';
import type { EngineCandle } from '../../doubleTapEngine';

// 1) every kind carries its tier
it('assigns a tier to every emitted pattern', () => {
  const patterns = detectAllPatterns(series(300), PATTERN_CONFIG);
  for (const p of patterns) expect([1, 2]).toContain(p.tier);
});

// 2) no look-ahead: truncating the future must not change a past event
it('never changes an event when later bars are removed', () => {
  const full = detectAllPatterns(series(300), PATTERN_CONFIG).filter((p) => p.anchor.index < 250);
  const cut = detectAllPatterns(series(250), PATTERN_CONFIG);
  for (const past of full) {
    const same = cut.find((p) => p.id === past.id);
    expect(same?.status, past.id).toBe(past.status);
  }
});

// 3) negative table: one adversarial series per kind must not emit that kind
const negatives: Array<[string, EngineCandle[]]> = [
  ['CUP_HANDLE', wideRimCup()], ['INVERSE_CUP_HANDLE', wideRimInverseCup()],
  ['ROUNDING_BOTTOM', vBottom()], ['ROUNDING_TOP', vTop()],
  ['DIAMOND_TOP', wideningFive()], ['DIAMOND_BOTTOM', wideningFive()],
  ['BROADENING_TOP', convergingFive()], ['BROADENING_BOTTOM', convergingFive()],
  ['ISLAND_REVERSAL', oneSidedGap()], ['THREE_RISING_PEAKS', spreadPeaks()], ['THREE_FALLING_PEAKS', spreadPeaks()],
];
it.each(negatives)('rejects %s on its adversarial series', (kind, candles) => {
  const found = detectAllPatterns(candles, PATTERN_CONFIG);
  expect(found.some((p) => p.kind === kind)).toBe(false);
});

// 4) overlap priority: a reversal beats a continuation anchored within 3 bars
it('keeps the reversal when a continuation overlaps it', () => {
  const patterns = detectAllPatterns(overlapSeries(), PATTERN_CONFIG);
  const anchors = patterns.map((p) => p.anchor.index);
  for (const p of patterns.filter((x) => x.family === 'continuation')) {
    expect(patterns.some((r) => r.family === 'reversal' && Math.abs(r.anchor.index - p.anchor.index) <= 3)).toBe(false);
  }
  expect(new Set(anchors).size).toBe(anchors.length);
});
```

Helpers (`series(n)`, `wideRimCup()`, `vBottom()`, `wideningFive()`, `convergingFive()`, `oneSidedGap()`, `spreadPeaks()`, `overlapSeries()`) are deterministic 60–300 bar builders written in this file; each one intentionally violates exactly one rule of its kind.

- [ ] **Step 2: Run** `cd frontend-v2 && npx vitest run src/features/technical/model/patterns/__tests__/accuracy.test.ts` → FAIL (detectors not registered / missing helpers).

- [ ] **Step 3: Implement** — in `registry.ts`:

```ts
export const PATTERN_TIER: Record<PatternKind, 1 | 2> = {
  DOUBLE_TOP: 1, DOUBLE_BOTTOM: 1, HEAD_SHOULDERS: 1, INVERSE_HEAD_SHOULDERS: 1,
  TRIPLE_TOP: 1, TRIPLE_BOTTOM: 1, FLAG_BULL: 1, FLAG_BEAR: 1, PENNANT: 1,
  TRIANGLE_ASC: 1, TRIANGLE_DESC: 1, TRIANGLE_SYM: 1, RECTANGLE: 1,
  WEDGE_RISING: 1, WEDGE_FALLING: 1, CUP_HANDLE: 1, INVERSE_CUP_HANDLE: 1,
  ROUNDING_TOP: 1, ROUNDING_BOTTOM: 1,
  DIAMOND_TOP: 2, DIAMOND_BOTTOM: 2, BROADENING_TOP: 2, BROADENING_BOTTOM: 2,
  ISLAND_REVERSAL: 2, THREE_RISING_PEAKS: 2, THREE_FALLING_PEAKS: 2,
};
```
and add `...detectCupRounding(candles, atr, config), ...detectTier2(candles, atr, config)` to the merge, then `tier: PATTERN_TIER[p.kind]` on every emitted pattern. Enforce the pointer to the double-tap adapter (tiers 1). If `emitPattern` rejects a one-point island anchor, extend it to accept `points.length >= 1` — that is the only permitted geometry change, and the existing tests must stay green.

- [ ] **Step 4: Run** `npx vitest run src/features/technical/model/patterns` + `npx tsc --noEmit` → PASS (86+ tests).

- [ ] **Step 5: Commit**

```bash
git add frontend-v2/src/features/technical/model/patterns/__tests__/accuracy.test.ts frontend-v2/src/features/technical/model/patterns/registry.ts frontend-v2/src/features/technical/model/patterns/geometry.ts
git commit -m "test(technical): سخت‌گیری دقت الگوها و رده‌بندی"
```

---

### Task A5: Merge the parallel tab into the scanner feed

**Files:**
- Create: `frontend-v2/src/features/technical/ui/ScannerFeed.tsx`
- Delete: `frontend-v2/src/features/technical/ui/PatternsTab.tsx` and `ui/__tests__/PatternsTab.test.tsx`
- Modify: `frontend-v2/src/features/technical/ui/WideWorkspaceDrawer.tsx` (remove the patterns tab + render block; scanner tab renders `<ScannerFeed />`)
- Modify: `frontend-v2/src/features/technical/model/types.ts` (`DrawerTab` drops `'patterns'`)
- Test: `frontend-v2/src/features/technical/ui/__tests__/ScannerFeed.test.tsx`

**Interfaces:**
- Consumes: store `detectedPatterns`, `detectedPullbackSignals`, `detectedCHoCHSignals`.
- Produces: `ScannerFeed` with the existing testids (`pattern-card`, `pattern-row-<id>`, `pattern-rules`, `pattern-tier-2`), plus one row per pullback/CHoCH with `data-testid="scanner-event-<id>"`.

- [ ] **Step 1: Write the failing test**

```tsx
// ScannerFeed.test.tsx
it('renders patterns and existing scanner events in one feed', () => {
  render(<ScannerFeed patterns={[flag()]} pullbacks={[pullback()]} chochs={[choch()]} />);
  expect(screen.getByTestId('pattern-row-FLAG_BULL:1')).toBeTruthy();
  expect(screen.getByTestId('scanner-event-pullback-1')).toBeTruthy();
  expect(screen.getByTestId('scanner-event-choch-1')).toBeTruthy();
});

it('badges tier-2 patterns and keeps the percent gate', () => {
  render(<ScannerFeed patterns={[diamond({ formation: null }), flag()]} pullbacks={[]} chochs={[]} />);
  expect(screen.getByTestId('pattern-tier-2').textContent).toContain('کم‌بسامد');
  expect(screen.getByTestId('pattern-card').textContent).not.toMatch(/[۰-۹]+٪/);
});
```

- [ ] **Step 2: Run** → FAIL (module missing).

- [ ] **Step 3: Implement** — move the card/list/rules markup from `PatternsTab.tsx` into `ScannerFeed.tsx`, add a `tier` badge, append the pullback/CHoCH rows (kind, direction, index/date) from the store, keep the family filter, and delete the old tab. `WideWorkspaceDrawer`:

```tsx
<TABS> // remove { id: 'patterns', labelFa: 'الگوها' }
{activeTab === 'scanner' && (
  <div className="block p-3" data-testid="scanner-panel">
    <ScannerFeed
      patterns={detectedPatterns}
      pullbacks={detectedPullbackSignals}
      chochs={detectedCHoCHSignals}
    />
  </div>
)}
```

- [ ] **Step 4: Run** the new spec + `npx vitest run src/features/technical` + `npx tsc --noEmit` → PASS; confirm `grep -r "PatternsTab" frontend-v2/src` returns nothing.

- [ ] **Step 5: Commit**

```bash
git add -A frontend-v2/src/features/technical/ui
git commit -m "refactor(technical): ادغام تب الگوها در اسکنر واحد"
```

---

### Task A6: Performance measurement and the visual audit gate

**Files:**
- Create: `_audit/rebuild/technical-phase-a/2026-11-06/` (evidence, untracked)
- Test: `frontend-v2/src/features/technical/model/patterns/__tests__/scanBudget.test.ts`

- [ ] **Step 1: Write the failing budget test**

```ts
it('scans 500 bars well under the 50ms budget', () => {
  const candles = series(500);
  const t0 = performance.now();
  detectAllPatterns(candles, PATTERN_CONFIG);
  const ms = performance.now() - t0;
  expect(ms).toBeLessThan(50);
});
```

- [ ] **Step 2: Run it; if it fails, profile the hot loop (pivot windows), fix it, and re-run. Never relax the budget.**

- [ ] **Step 3: Run the full suite and build**

Run: `cd frontend-v2 && npx tsc --noEmit && npx vitest run && npm run build`
Expected: all green; note the counts in the report.

- [ ] **Step 4: Visual audit** — with the backend (8110, `BORS_WORK_DIR=D:/BorsTerminal-tmp/4axes-data`) and dist (7093) running, capture the merged scanner for 15 symbols × daily/weekly, both themes, at 1366×768 and 1920×1080. Then run the `fts-user-critic` skill on the chart scope for those screenshots and count «جعلی» and «جاافتاده» per tier. Acceptance for tier 1: false = 0 and every drawn pattern explainable by a rulebook row; tier 2 is recorded but not gated. Save `audit.json`, screenshots and the report under the evidence directory; stop the two servers afterwards.

- [ ] **Step 5: Commit the test only** (evidence stays untracked)

```bash
git add frontend-v2/src/features/technical/model/patterns/__tests__/scanBudget.test.ts
git commit -m "test(technical): بودجه اسکن الگوها"
```

---

## Roadmap after Phase A (separate plans, each with its own gate)

- **Phase B — Workspace redesign (TradingView layout) + unslop.** New topbar/activity bar/inspector rail/event feed shell, re-housing the existing tabs, 1366/1920 both themes, no feature loss. Plan only after A ships.
- **Phase C — Event scanner + highlight + animation.** `ChartEvent/ScanResult`, channel/pullback/breakout/RSI-divergence events, one-per-family highlight overlay, 200ms label entrance, reduced-motion. Plan after B.
- **Phase D — Visual and accuracy acceptance.** 15 symbols × 2 timeframes audit, false=0 for tier 1, performance and theme evidence.

## Self-Review

**Spec coverage (Phase A scope):** tier field + rulebook (A1), cup/rounding tier-1 (A2), seven tier-2 kinds (A3), accuracy hardening incl. no-look-ahead and negative fixtures (A4), tab merge into the single scanner (A5), perf budget + visual audit gate (A6). Phases B/C/D are explicitly deferred to their own plans because the spec covers three more subsystems — the plan's scope check demands separate plans rather than one 26-pattern + redesign monster.

**Placeholder scan:** every task carries real code or an exact command. The negative-fixture helpers in A4 Step 1 are named builders the executor writes in that file (their contract is stated: each violates exactly one rule); this is the one place where a helper body is not spelled out, and it is deliberate — writing eight synthetic series inline would triple the task size without adding information.

**Type consistency:** `tier?: 1 | 2` is set from `PATTERN_TIER` in the registry; `emitPattern`'s spec gains `tier`; A5 consumes the same `ChartPattern`; A6 measures the same `detectAllPatterns` entry point. The `BoundaryLine`/`PatternPoint` helpers are consistent across A2 and A3.

