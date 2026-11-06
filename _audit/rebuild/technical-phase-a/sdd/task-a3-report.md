# Task A3 report — Tier-2 detectors

**Status:** complete (local only, no push)
**Commit:** `74ebc350` (parent `64ebeea8`)
**Branch:** `integration/4axes-main-2026-11-03`

## Files

- Create `frontend-v2/src/features/technical/model/patterns/detectTier2.ts` — `detectTier2(candles, atr, config)` with `diamondOrBroadening`, `island`, `threePeaks`. Every spec carries `tier: 2`, family `maxBars` (`hs.maxBars` for diamond/broadening and three peaks, `tier2.islandMaxBars` for island) and `invalidationBuffer: config.invalidationBufferAtr * atr`.
- Create `frontend-v2/src/features/technical/model/patterns/__tests__/tier2.test.ts` — 8 tests: positive + negative per kind (mirrors cover the bottom variants) plus an `islandMaxBlockBars` consumption proof.
- Modify `frontend-v2/src/features/technical/model/patterns/config.ts` — `tier2.islandMaxBlockBars: 5` and `tier2.islandMaxBars: 6` in the interface and `PATTERN_CONFIG` (R-PA-9).
- Modify `frontend-v2/src/features/technical/model/patterns/__tests__/config.test.ts` — exact pin updated in both places (whole-object and tier-2 block); no assertion weakened.

No existing detector, registry or geometry file was touched.

## R-PA-9 wiring

- Exit-gap window: `for (let j = i + 1; j <= Math.min(candles.length - 1, i + config.tier2.islandMaxBlockBars); j++)`. This is iteration-for-iteration identical to the brief's `j < Math.min(candles.length, i + 6)` (j − i ≤ 5), so the rulebook's "exit gap within at most 5 candles after entry" is preserved with no literal.
- Island `maxBars: config.tier2.islandMaxBars` (was the literal `6`).
- `ISLAND_LONG_CLOSES` proves the block key is consumed: exit at j − i = 5 passes with the default 5 and yields no island when the config is tightened to 4.

## Red

Command: `npx vitest run src/features/technical/model/patterns/__tests__/tier2.test.ts src/features/technical/model/patterns/__tests__/config.test.ts`

```
FAIL  src/features/technical/model/patterns/__tests__/tier2.test.ts [ src/features/technical/model/patterns/__tests__/tier2.test.ts ]
Error: Failed to resolve import "../detectTier2" from "src/features/technical/model/patterns/__tests__/tier2.test.ts". Does the file exist?
  Plugin: vite:import-analysis
  File: .../__tests__/tier2.test.ts:3:28
  1  |  import { describe, expect, it } from "vitest";
  2  |  import { detectTier2 } from "../detectTier2";
     |                               ^
...
 Test Files  1 failed (1)
      Tests  no tests
```

Config pin (same run, before `config.ts` changed):

```
FAIL  src/features/technical/model/patterns/__tests__/config.test.ts > PATTERN_CONFIG > pins the tier-2 and cup/rounding defaults
AssertionError: expected { diamondConvergeMin: 0.25, …(3) } to deeply equal { diamondConvergeMin: 0.25, …(5) }
  {
    "broadeningMin": 0.25,
    "diamondConvergeMin": 0.25,
    "islandGapAtr": 0.5,
-   "islandMaxBars": 6,
-   "islandMaxBlockBars": 5,
    "threePeaksToleranceAtr": 0.5,
  }
 Test Files  2 failed (2)
      Tests  2 failed (2)
```

## Green

```
npx vitest run src/features/technical/model/patterns/__tests__/tier2.test.ts src/features/technical/model/patterns/__tests__/config.test.ts
 ✓ config.test.ts (2 tests)
 ✓ tier2.test.ts (8 tests)
 Test Files  2 passed (2)
      Tests  10 passed (10)

npx vitest run src/features/technical/model/patterns
 Test Files  11 passed (11)
      Tests  91 passed (91)

npx vitest run          (frontend-v2, full suite)
 Test Files  85 passed (85)
      Tests  689 passed (689)

npx tsc --noEmit
exit 0
```

## Fixtures → kind

ATR = 2 in every fixture, `pivLeft = pivRight = 1`; thresholds stay at `PATTERN_CONFIG` defaults.

| Fixture | Shape | Asserts |
|---|---|---|
| `DIAMOND_CLOSES` (35 bars) | pivots high 100@4 → low 92@10 → high 108@16 → low 96@22 → high 103@28; boundary width 10 → 7.5 → 5 (≤ 0.75×10 = 7.5) | `DIAMOND_TOP`, confirmed, bearish, reversal, tier 2 |
| mirrored `DIAMOND_CLOSES` | same geometry inverted | `DIAMOND_BOTTOM`, confirmed, bullish, tier 2 |
| `DIAMOND_SHALLOW_CLOSES` | last high 106 instead of 103; width 10 → 9 → 8 (8 > 7.5) | no `DIAMOND_TOP`; mirror emits no `DIAMOND_BOTTOM` |
| `BROADENING_CLOSES` (35 bars) | high 100@4 → low 92@10 → high 108@16 → low 90@22 → high 106@28; width 7 → 12 → 17 (≥ 1.25×7 = 8.75) | `BROADENING_TOP`, bearish, reversal, tier 2 |
| mirrored `BROADENING_CLOSES` | same geometry inverted | `BROADENING_BOTTOM`, bullish, tier 2 |
| `BROADENING_NARROW_CLOSES` | last low 91.5, last high 100.5; width 7.75 → 8.5 → 9.25 (< 9.6875) | no `BROADENING_TOP`; mirror emits no `BROADENING_BOTTOM` |
| `DIAMOND_CLOSES` as broadening negative | converging boundaries | no `BROADENING_TOP` (plan's "rejects a converging one") |
| `ISLAND_CLOSES` (14 bars) | gap-up 1.6 (> 0.5×ATR = 1) at bar 5, 3-candle island, gap-down at bar 7 (j − i = 2); then decline | `ISLAND_REVERSAL`, confirmed, bearish, reversal, tier 2, single-point anchor at 7 |
| mirrored `ISLAND_CLOSES` | gap-down island | `ISLAND_REVERSAL` bullish, tier 2 |
| `ISLAND_SMALL_EXIT_CLOSES` | exit gap 0.5 < 1 | no `ISLAND_REVERSAL` |
| `ISLAND_SMALL_ENTRY_CLOSES` | entry gap 0.6 < 1 (exit gap 2.2) | no `ISLAND_REVERSAL` |
| `ISLAND_LONG_CLOSES` (17 bars) | gap-out at j − i = 5 | emitted with `islandMaxBlockBars: 5`, none with 4 |
| `RISING_CLOSES` (23 bars) | highs 100@4, 100.3@10, 100.6@16 (spread 0.6 ≤ 1) with higher lows 97@7, 98@13 | `THREE_RISING_PEAKS`, bearish, reversal, tier 2, 3 points |
| mirrored `RISING_CLOSES` | three lows 100/99.7/99.4 with lower highs | `THREE_FALLING_PEAKS`, bullish, continuation, tier 2 |
| `RISING_SPREAD_CLOSES` | third high 101.2 → spread 1.2 > 1 | no `THREE_RISING_PEAKS`; mirror emits no `THREE_FALLING_PEAKS` |

## Family assignment (ruling)

`THREE_RISING_PEAKS` is emitted at a top as `reversal`/`bearish`; `THREE_FALLING_PEAKS` at a bottom as `continuation`/`bullish`, exactly as the plan's code states. The detector comment records that the rulebook/reference definition is AMBIGUOUS and does not cite a booklet source for this family choice.

## Residual risks

- Not registered yet: A4 owns the `detectAllPatterns` wiring, so the seven kinds are invisible to the app until then.
- `tier2.islandMaxBars` is passed to `emitPattern` and exact-pinned, but no behavioral test isolates it (an old single-point island is dropped by the `maxBars + expiryGraceBars` expiry path, which would need a >120-bar fixture). Only `islandMaxBlockBars` has a direct consumption test.
- Island patterns are single-point and found only at recent bars (that is the `emitPattern` expiry contract); there is no historical island sweep, so islands older than `islandMaxBars + expiryGraceBars` never surface.
- Island `upper`/`lower` are diagonal lines from entry to the exit anchor and can cross after the anchor; geometry follows the brief, but a chart renderer should not assume `upper > lower` for this kind.
- Broadening fixtures emit `forming` (price never crosses the lower boundary in the fixture); only diamond and island positives assert `confirmed`.
- `RISING_CLOSES` also emits `DIAMOND_TOP`: near-flat highs with rising lows satisfy the convergence gate. The test selects by kind, so it is unaffected, but the fixture does not isolate one kind.
- `detectTier2` keeps the plan's guard `if (!(atr > 0)) return []`; NaN/0/negative are rejected, `Infinity` is not (the other detectors additionally use `Number.isFinite`). No fixture covers non-finite ATR.
- Thresholds are exercised only through synthetic, noise-free fixtures; real-market false-positive rates for the seven tier-2 kinds remain unmeasured until the scanner feed lands (A5/A6).
- Fixture margins are deliberately narrow (`8` vs `7.5` for diamond, `9.25` vs `9.6875` for broadening); later numeric edits to fixtures must re-check those ratios.

## Fix round 1

**Status:** complete (local only, no push)
**Commit:** `e7562c3a` (parent `74ebc350`)
**Scope:** `detectTier2.ts` + `__tests__/tier2.test.ts` only; config, registry and geometry untouched (the config pin still passes).

### Findings → fixes

| # | Finding | Fix | Covering test(s) |
|---|---|---|---|
| 1 | CRITICAL — bottom diamond/broadening boundaries swapped: for a bottom `upper` was built from the lows (w[0], w[4]), sat below the highs line, and a close inside the shape "confirmed" a bullish breakout | R-PA-10: bottoms build `upper` through the highs (w[1], w[3]) and `lower` through the lows (w[0], w[4]); tops keep the old order | `keeps bottom shapes forming inside the highs line and confirms only above it` (DIAMOND_BOTTOM and BROADENING_BOTTOM: forming inside, confirmed only on a close above the highs line); both diamond positives now pin `upper`/`lower` endpoints to the high/low pivots |
| 2 | IMPORTANT — ATR guard accepted `Infinity` | `if (!Number.isFinite(atr) || atr <= 0) return []` | `rejects a non-finite ATR` (`Infinity` → `[]`) |
| 3 | IMPORTANT — three-peaks trio span unbounded and stale trios still emitted | skip `trio[2].index - trio[0].index > config.hs.maxBars`; skip `trio[2].index < candles.length - config.hs.maxBars` (same recency prefilter as `detectReversal`) | `rejects a three-peaks trio whose span exceeds hs.maxBars` (highs at 4/74/144, span 140 > 120), `rejects a trio older than the hs.maxBars recency window` (span 70, last peak 74 < 199−120) |
| 4 | MINOR — a monotone narrowing wedge was accepted as a diamond | converging additionally requires the middle-pivot excursion to the opposite boundary (`midSpan`) to exceed the start width; the existing `mid > end` and `end ≤ 0.75·start` gates are unchanged | `rejects a monotone narrowing wedge as a diamond (mid > start)` (`WEDGE_CLOSES`, widths 16 → 9 → 2, middle high below the start high) |
| 5 | MINOR — island exit gap was measured only against the entry candle | the exit-gap test now uses the running block extreme (max high / min low of island bars so far); emission geometry is unchanged | `measures the island exit gap against the running block extreme, not the entry candle` |

### Ruling — literal `mid > start`

The literal `width(w[2].index) > width(w[0].index)` cannot be satisfied together with `width(w[4].index) ≤ (1 − diamondConvergeMin)·width(w[0].index)`: `width(x)` is the difference of two straight lines, hence affine in `x`; `mid > start` implies `end > mid > start`, i.e. `end > start`, contradicting the end gate. A literal implementation makes `DIAMOND_TOP`/`DIAMOND_BOTTOM` undetectable and contradicts fix 1's DIAMOND_BOTTOM forming→confirmed requirement. Implemented instead: `midSpan` — the middle pivot's excursion to the opposite boundary (`w[2].price − lower(w[2])` for tops, `upper(w[2]) − w[2].price` for bottoms) — must exceed `start`. That is the geometric "middle wider than the start" and is exercised by the monotone-wedge negative. The original `mid > end` width check is kept.

### Fixtures added

| Fixture | Shape | Asserts |
|---|---|---|
| `DIAMOND_BOTTOM_INSIDE_CLOSES` | mirror of `DIAMOND_CLOSES` with a tail 98 → 99.6 that stays under the highs line (101.67 → 100) | `DIAMOND_BOTTOM` `forming` |
| `BROADENING_BOTTOM_CLOSES` | mirror broadening (widths 7 → 12 → 17) + 109/112/115 tail; only 115 clears the highs line (112.5) at 37 | `BROADENING_BOTTOM` `confirmed`, `breakoutIndex` 37, close above `upper` |
| `WEDGE_CLOSES` | highs 106/104/100, lows 92/96; widths 16 → 9 → 2, middle high below the start high | no `DIAMOND_TOP` |
| `ISLAND_SPIKE_INSIDE_CLOSES` | gap-up 1.6 at 5; bar 6 lowers the block low to 100.1; bar 7 high 99.9 passes the entry-based gap (100.6) but not the running one (99.1) | no `ISLAND_REVERSAL` |
| `THREE_PEAKS_LONG_CLOSES` (150 bars) | three highs 100/100.3/100.6 at 4/74/144 (span 140) | no `THREE_RISING_PEAKS` |
| `THREE_PEAKS_STALE_CLOSES` (200 bars) | three highs at 4/40/74 (span 70), confirmed at 80, tail to 199 | no `THREE_RISING_PEAKS` |

### Red (before the implementation)

```
npx vitest run src/features/technical/model/patterns/__tests__/tier2.test.ts
 FAIL  ... > keeps bottom shapes forming inside the highs line and confirms only above it
AssertionError: expected 'confirmed' to be 'forming'
...
 Test Files  1 failed (1)
      Tests  5 failed | 8 passed (13)
```

The bottom forming fixture is the direct mirror-bug witness: with swapped lines the close *inside* the shape confirmed the pattern.

### Green

```
npx tsc --noEmit
TSC_EXIT=0

npx vitest run src/features/technical/model/patterns/__tests__/tier2.test.ts src/features/technical/model/patterns/__tests__/config.test.ts
 ✓ config.test.ts (2 tests)
 ✓ tier2.test.ts (14 tests)
 Test Files  2 passed (2)
      Tests  16 passed (16)

npx vitest run src/features/technical/model/patterns
 Test Files  11 passed (11)
      Tests  97 passed (97)

npx vitest run          (frontend-v2, full suite)
 Test Files  85 passed (85)
      Tests  695 passed (695)
```

### Residual risks (fix round)

- `midSpan > start` is the satisfiable reading of "mid > start" (see ruling). A literal width comparison would make diamonds unreachable, so it would need an explicit spec change, not a code tweak.
- Island `upper`/`lower`/target still use `slice(i, j + 1)` (exit bar included); only the gap gate uses the running extreme. Switching the geometry too would flip the existing `ISLAND_CLOSES` confirmation to `invalidated`, so it was left untouched by design.
- The two new three-peaks fixtures are long synthetic ramps (150/200 bars); the stale one is observable only because it confirms before expiry (`emitPattern` would drop a *forming* stale trio anyway).
- Diamond positives are unchanged (middle high/low already exceeds the start width: 108 vs 100 and 92 vs 100); they now also pin the boundary endpoints.
- `detectTier2` is still unregistered (A4 owns the `detectAllPatterns` wiring).
