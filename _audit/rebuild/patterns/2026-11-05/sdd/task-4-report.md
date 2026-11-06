# Task 4 report — continuation detectors

- Worktree: `D:/BorsTerminal-worktrees/4axes-main-integration`
- Branch: `integration/4axes-main-2026-11-03`
- Base: `5387764c` (Tasks 1–3)
- Commit: `4a1f42db` — `feat(technical): دتکتورهای الگوهای ادامه‌دهنده`
- Committed files (only these two):
  - `frontend-v2/src/features/technical/model/patterns/detectContinuation.ts`
  - `frontend-v2/src/features/technical/model/patterns/__tests__/continuation.test.ts`

## TDD red (verbatim, before implementation)

```
RUN  v3.2.7 D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2


⎯⎯⎯⎯⎯⎯ Failed Suites 1 ⎯⎯⎯⎯⎯⎯

 FAIL  src/features/technical/model/patterns/__tests__/continuation.test.ts [ src/features/technical/model/patterns/__tests__/continuation.test.ts ]
Error: Failed to resolve import "../detectContinuation" from "src/features/technical/model/patterns/__tests__/continuation.test.ts". Does the file exist?
  Plugin: vite:import-analysis
  File: D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2/src/features/technical/model/patterns/__tests__/continuation.test.ts:3:35
  1  |  import { describe, expect, it } from "vitest";
  2  |  import { detectContinuation } from "../detectContinuation";
     |                                      ^
  3  |  import { PATTERN_CONFIG } from "../config";
  4  |  function zigzag(start, legs) {
 ❯ TransformPluginContext._formatError ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:49258:41
 ❯ TransformPluginContext.error ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:49253:16
 ❯ normalizeUrl ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:64307:23
 ❯ ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:64439:39
 ❯ TransformPluginContext.transform ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:64366:7
 ❯ PluginContainer.transform ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:49099:18
 ❯ loadAndTransform ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:51978:27

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/1]⎯


 Test Files  1 failed (1)
      Tests  no tests
   Start at  15:04:25
   Duration  3.53s (transform 43ms, setup 0ms, collect 0ms, tests 0ms, environment 2.49s, prepare 267ms)
```

An intermediate run was also red (fixture geometry, not implementation thresholds): 7 passed / 3 failed (`FLAG_BULL`, `PENNANT`, `TRIANGLE_DESC` not produced). Fixture bars were reshaped (as the brief allows); no threshold was changed.

## Green

Focused spec (final):

```
 ✓ src/features/technical/model/patterns/__tests__/continuation.test.ts (10 tests) 25ms

 Test Files  1 passed (1)
      Tests  10 passed (10)
```

Whole patterns folder:

```
 ✓ src/features/technical/model/patterns/__tests__/config.test.ts (1 test) 11ms
 ✓ src/features/technical/model/patterns/__tests__/pivots.test.ts (4 tests) 15ms
 ✓ src/features/technical/model/patterns/__tests__/geometry.test.ts (4 tests) 11ms
 ✓ src/features/technical/model/patterns/__tests__/continuation.test.ts (10 tests) 25ms

 Test Files  4 passed (4)
      Tests  19 passed (19)
```

`npx tsc -b` exits 0.

## Detectors actually exercised by the fixtures

Probed with the final fixtures (each pattern status was `confirmed`):

| Fixture | Kinds produced |
|---|---|
| `flagSeries` | `FLAG_BULL` only |
| `pennantSeries` | `PENNANT` + `TRIANGLE_SYM` (inherent overlap; both read the same last two highs/lows) |
| `ascendingTriangleSeries` | `TRIANGLE_ASC` only |
| `descendingTriangleSeries` | `TRIANGLE_DESC` only |
| `symmetricTriangleSeries` | `TRIANGLE_SYM` only |
| `rectangleSeries` | `RECTANGLE` only |
| `risingWedgeSeries` | `WEDGE_RISING` only |
| `fallingWedgeSeries` | `WEDGE_FALLING` only |
| flat line | none |

All nine continuation kinds (`FLAG_BULL`, `PENNANT`, `TRIANGLE_ASC/DESC/SYM`, `RECTANGLE`, `WEDGE_RISING/FALLING`) are covered. `FLAG_BEAR` is not covered by a dedicated fixture (same code path as `FLAG_BULL`).

## Controller rulings applied

- **R-PAT-4** — tests use `{ ...PATTERN_CONFIG, pivLeft: 1, pivRight: 1 }` and ATR 2; all geometric thresholds remain `PATTERN_CONFIG` values. Production keeps `PATTERN_CONFIG`.
- **R-PAT-7** — `detectContinuation(candles, atr, config)` only; no `lastIndex` variable (recency check in `detectTriangleFamily` reads `candles.length - 1` directly).
- **R-PAT-9** — pennant gate uses `config.pennant.impulseLegAtrMin`; wedge convergence uses `config.wedge.convergenceMin` (triangle convergence kept for `TRIANGLE_SYM`).
- **R-PAT-5** — every `emitPattern` spec passes `maxBars`: `flag.maxBars`, `pennant.maxBars`, and per-kind `triangle`/`rectangle`/`wedge.maxBars`.

## Deviation from the brief (flagged for the controller)

The brief measured pennant convergence with the width at `legEnd.index` (the impulse end, i.e. *before* the consolidation) against the width at the first high. For genuinely converging lines (upper falling, lower rising) the width at `legEnd` is always larger, so that condition can never be true and `PENNANT` is unreachable. The implementation instead measures the consolidation's own start and end (`min(H1.index, L1.index)` vs `max(H2.index, L2.index)`) and applies the same `pennant.convergenceMin` threshold, mirroring the triangle-family measurement and the brief's own comment ("two converging lines"). No threshold changed. This was necessary to satisfy the task's stated goal of a pennant detector; if the controller prefers the literal formula, the branch can be reverted, but pennants will then never emit.

## Residual risks

1. **Anchor vs. latest point** — `detectTriangleFamily` anchors on `points[points.length - 1]` (`lows[1]`). When the latest global pivot is a high (e.g., a descending triangle ending on its second high), the anchor predates another pattern point and `emitPattern` starts scanning before the final point exists. Fixtures end on a low so this is untested and can mis-status production data.
2. **PENNANT/TRIANGLE_SYM overlap** — any trailing converging channel satisfies both; dedupe is by `id` only and does not suppress cross-kind duplicates. Downstream consumers may see two alerts for one formation.
3. **Only last two highs/lows per consolidation** — flags/pennants/wedges ignore earlier touches inside the window; a channel with a third touch or an interior swing is reduced to the last two pivots.
4. **Bearish fixtures need a bounce bar** — a close below a flat lower boundary immediately after the final low would make that low a non-pivot. The descending fixture encodes a one-bar bounce before the breakdown; real breakdowns behave similarly but this interaction is subtle and only synthetically tested.
5. **Generic targets/stops** — triangle/wedge specs keep the brief's `target: h1 + height`, `stopLoss: l1 - atr` regardless of direction (a bearish rising wedge gets an upward target). Kept as specified; not asserted.
6. **Recency window** — `detectTriangleFamily` uses `config.triangle.maxBars` (60) for the staleness guard of all families, so a rectangle/wedge could be admitted up to 60 bars even though its own `maxBars` is 80/60. `emitPattern` still applies the family-specific `maxBars` from R-PAT-5.
7. **Synthetic only** — no production-data or production pivot-window (5/4) run for these detectors; fixtures use 1/1 pivots per R-PAT-4.

## Fix round 1 (review findings)

Commit: `717bb514` — `fix(technical): اصلاح لنگر، هم‌پوشانی بین‌خانواده‌ای و آستانه‌های دتکتورهای ادامه‌دهنده`

### Addressed

1. **Critical — anchor/look-ahead**: both detector families sort `points` ascending by index before `emitPattern` (`sortPoints`), so `anchor` is always the max-index point even when the brief's arrays end with `lows[1]`. New `formingFlagSeries` consolidates to `highs[1]` at 22 while `lows[1]` is 19; the test asserts `anchor.index === Math.max(...points.index) === 22` and `breakoutIndex === undefined || breakoutIndex > anchor.index`.
2. **Important — cross-kind overlap (R-PAT-14)**: `boundaryFingerprint(highs[1].index, lows[1].index)` is recorded for every emitted flag/pennant; `detectTriangleFamily` drops triangle/rectangle/wedge for the same pair. `pennantSeries` now yields `PENNANT` only (test asserts no `TRIANGLE_SYM`).
3. **Important — hidden thresholds (R-PAT-13)**: `touchToleranceAtr: 0.5` (top level), `flag.minLegBars: 3`, `triangle.minSpan: 3` added to `PatternConfig`/`PATTERN_CONFIG` and the exact pin; literals replaced with `atr * config.touchToleranceAtr`, `legBars < config.flag.minLegBars`, `span < config.triangle.minSpan`. The quality width term now uses `flag.channelMaxWidthPct`; scoring weights stay as named constants (`QUALITY_BASE/WIDTH_WEIGHT/TOUCH_WEIGHT/TOUCH_FULL`, `PENNANT_QUALITY_PENALTY`, per-kind `TRIANGLE/SYMMETRIC/RECTANGLE/WEDGE_QUALITY`).
4. **Important — rectangle window**: the `triangle.maxBars` staleness guard is removed; each emission passes its own `maxBars` (rectangle 80, triangle 60, wedge 60) and `emitPattern` enforces it.
5. **Important — tests**: new `bearFlagSeries` (`FLAG_BEAR` confirmed), `wideChannelSeries` (channel 18 vs 35% of leg 34 → no FLAG/PENNANT), `formingFlagSeries` (forming, `breakoutIndex` undefined); bull/bear flag tests assert `status` and `breakoutIndex > anchor.index`.
6. **Minor — bearish targets (R-PAT-15)**: `target = lowerEnd − height`, `stopLoss = upperEnd + atr` for bearish; bullish mirrored; neutral (RECTANGLE/TRIANGLE_SYM) keeps the upward default. Descending-triangle and rising-wedge tests assert `target < entry < stopLoss`, as does the `FLAG_BEAR` test.

### Verification

`cd frontend-v2 && npx tsc --noEmit` → exit 0.

```
RUN  v3.2.7 D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2

 ✓ src/features/technical/model/patterns/__tests__/config.test.ts (1 test) 8ms
 ✓ src/features/technical/model/patterns/__tests__/geometry.test.ts (4 tests) 12ms
 ✓ src/features/technical/model/patterns/__tests__/continuation.test.ts (13 tests) 36ms

 Test Files  3 passed (3)
      Tests  18 passed (18)
   Start at  15:21:29
   Duration  4.20s (transform 511ms, setup 0ms, collect 740ms, tests 57ms, environment 8.72s, prepare 945ms)
```

### Residual notes

- Removing the triangle staleness guard means an already-confirmed triangle/rectangle/wedge older than `triangle.maxBars` but inside its own window can still surface; `emitPattern` still drops expired *forming* patterns via each spec's `maxBars`.
- Neutral patterns keep the upward target/stop default because R-PAT-15 defines only bearish/bullish; a downward breakout of a neutral pattern is not reflected in target/stop.
- `wideChannelSeries` produces no continuation pattern at all; the negative test asserts absence of FLAG_BULL/FLAG_BEAR/PENNANT, so another family appearing would not fail it.
