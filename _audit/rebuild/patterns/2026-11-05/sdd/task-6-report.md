# Task 6 report — outcome and 1/3/5-bar returns

- Worktree: `D:/BorsTerminal-worktrees/4axes-main-integration`
- Branch: `integration/4axes-main-2026-11-03`
- Base: `53b67ff6` (Task 5 review-fix HEAD, all 11 detectors present)
- Commit: `02d95c8e` — `feat(technical): نتیجه و بازده ۱/۳/۵ کندلی الگوها`
- Committed files (only these two):
  - `frontend-v2/src/features/technical/model/patterns/outcome.ts`
  - `frontend-v2/src/features/technical/model/patterns/__tests__/outcome.test.ts`

## What landed

- `outcomeOf(pattern, candles, atr, config, horizon?): 'success' | 'failure' | 'unresolved'` — the three brief tests verbatim, plus the implementation exactly as embedded in the brief.
- `meanReturns(samples, candles, config): { h1; h3; h5 }` — identical to the brief's embedded code (three parameters; see residual risk 8 about the extra `atr` in the Produces line).
- Two added tests: the neutral/R-PAT-2 case and the `meanReturns` < 5-sample null case. No assertion from the brief was weakened; the null test additionally pins that five samples do produce a number, so the null result cannot be satisfied by an always-null implementation.

## Rulings applied

- **R-PAT-2**: the neutral test asserts both halves — first close above the upper boundary (106.5) sets bias up with `entry = 106`, then a close of 108 ≥ 106 + height/2 (height 2 → target 1) is `success`; the same first break followed by a close of 103 < lower − 0.5×atr (103.5) is `failure`.
- **R-PAT-3**: `meanReturns` filters `direction !== 'neutral'` before accumulating, so neutral returns stay `null` by construction.
- **R-PAT-4**: `outcomeOf` never returns a "forming"/pending value — anything past the window is `unresolved` and Task 7 drops it.
- **R-PAT-1**: not implemented here on purpose; `meanReturns` consumes whatever sample set it is handed, so family pooling stays Task 7's responsibility.

## TDD red (verbatim, before implementation)

```
RUN  v3.2.7 D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2


⎯⎯⎯⎯⎯⎯ Failed Suites 1 ⎯⎯⎯⎯⎯⎯⎯

 FAIL  src/features/technical/model/patterns/__tests__/outcome.test.ts [ src/features/technical/model/patterns/__tests__/outcome.test.ts ]
Error: Failed to resolve import "../outcome" from "src/features/technical/model/patterns/__tests__/outcome.test.ts". Does the file exist?
  Plugin: vite:import-analysis
  File: D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2/src/features/technical/model/patterns/__tests__/outcome.test.ts:3:39
  1  |  import { describe, expect, it } from "vitest";
  2  |  import { meanReturns, outcomeOf } from "../outcome";
     |                                          ^
  3  |  import { PATTERN_CONFIG } from "../config";
  4  |  const point = (index, price) => ({ index, price, timestamp: index * 6e4 });
 ❯ TransformPluginContext._formatError ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:49258:41
 ❯ TransformPluginContext.error ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:49253:16
 ❯ normalizeUrl ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:64307:23
 ❯ ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:64439:39
 ❯ TransformPluginContext.transform ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:64366:14
 ❯ PluginContainer.transform ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:49099:18
 ❯ loadAndTransform ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:51978:29

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/1]⎯


 Test Files  1 failed (1)
      Tests  no tests
   Start at  15:43:49
   Duration  3.63s (transform 43ms, setup 0ms, collect 0ms, tests 0ms, environment 2.59s, prepare 299ms)
```

## Green

Focused spec:

```
RUN  v3.2.7 D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2

 ✓ src/features/technical/model/patterns/__tests__/outcome.test.ts (5 tests) 11ms

 Test Files  1 passed (1)
      Tests  5 passed (5)
```

Whole patterns folder:

```
 ✓ src/features/technical/model/patterns/__tests__/config.test.ts (1 test) 10ms
 ✓ src/features/technical/model/patterns/__tests__/geometry.test.ts (4 tests) 12ms
 ✓ src/features/technical/model/patterns/__tests__/pivots.test.ts (4 tests) 22ms
 ✓ src/features/technical/model/patterns/__tests__/outcome.test.ts (5 tests) 20ms
 ✓ src/features/technical/model/patterns/__tests__/reversal.test.ts (10 tests) 32ms
 ✓ src/features/technical/model/patterns/__tests__/continuation.test.ts (13 tests) 38ms

 Test Files  6 passed (6)
      Tests  37 passed (37)
```

`cd frontend-v2 && npx tsc --noEmit -p tsconfig.json` → exit 0 (no output).

## Residual risks

1. **`unresolved` is horizon-bounded, not data-bounded.** The loop covers exactly `horizon` bars after the anchor (`start = anchor.index + 1`, `end = min(candles.length, start + horizon)`). With `outcomeHorizon = 10`, a genuine breakout on bar 11+ is classified `unresolved` and therefore dropped by R-PAT-4 — it is not a "not yet" state that Task 7 can revisit later. Horizon length is the whole sensitivity knob for the formation rate.
2. **Right-edge truncation conflates "flat" with "no data".** When `candles.length < start + horizon`, the window silently shortens and the loop exits at the series end. Patterns in the last `outcomeHorizon` bars of the input are therefore biased toward `unresolved` and get dropped, which biases the Task 7 formation rate downward for recent history. Task 7 should either keep `outcomeHorizon` bars of padding in its series or exclude the tail.
3. **The `unresolved` unit test does not distinguish the two causes.** The brief's fixture has only 2 bars after the anchor, so it exits by data exhaustion before the horizon is reached. Behaviour is correct either way, but no test pins the horizon cut-off itself.
4. **Neutral bias is computed and then thrown away.** `outcomeOf` records `bias` only in a local; `ChartPattern` has no field for the inferred direction (R-PAT-2) and the function returns a bare string. Downstream (Task 7/8 overlay, target/label text, and any "which way did the rectangle resolve" copy) cannot tell an upside rectangle success from a downside one without re-walking the candles. `breakoutIndex` comes from `emitPattern` and only marks the first break bar, not the direction. If the UI needs the resolved side, either a direction field or a richer return type is needed — deliberately out of scope here.
5. **Neutral contributions are asymmetric across the two stats.** Neutral patterns count toward the Task 7 success/failure rate but are excluded from `meanReturns` (R-PAT-3), so a neutral-heavy sample set shows a rate with no matching return figure. This is the locked ruling, not a bug, but it makes the two numbers non-comparable.
6. **Same-bar precedence.** For the neutral branch the break bar `continue`s without checking the opposite boundary; for directional patterns `success` is tested before `failure` on each bar. With well-ordered lines this is harmless, but if `upper`/`lower` ever invert (crossed lines after a bad anchor, or a converging pattern whose lines have already met) a single close can satisfy both tests and `success` wins silently.
7. **Near-zero height makes neutral success trivial.** `heightOf` reads both boundaries at the anchor index. A neutral pattern anchored at (or near) a converged apex has height ≈ 0, so `target = height/2 ≈ 0` and the first break bar's close satisfies `close >= entry + 0` immediately. Neutral success rates for converging shapes (symmetric triangle) are therefore optimistic; a height floor is not in the brief.
8. **`meanReturns` ignores ATR and the Produces line lists one.** The interface line says `meanReturns(samples, candles, config, atr)` but the brief's locked code takes three parameters; I kept the code. Returns are plain percentages of the boundary value, not ATR-normalised, and Task 7's call site already matches (three args), so nothing breaks — but if a future revision wants ATR-scaled returns the signature must change. `tsconfig` has `noUnusedParameters`, so an unused `atr` could not simply be parked in the signature.
9. **Return denominators differ per horizon.** Samples with `triggerIndex + horizon >= candles.length` are skipped, so `h3`/`h5` can be `null` (or computed from fewer samples) while `h1` is populated even when the total sample count is ≥ 5. Entry price is the boundary value at the trigger bar, not that bar's close, so a gapped breakout is measured from the line rather than the fill.
10. **`breakoutIndex ?? anchor.index` fallback.** Samples that never confirmed fall back to the anchor bar as the entry. Task 7 filters by `outcomeOf`, so this is only reachable if a caller passes unconfirmed patterns — worth keeping in mind if Task 7 ever feeds `meanReturns` the raw detector output instead of the resolved subset.

## Fix round 1

Base: `02d95c8e`. All four review findings applied with tests; residual risks 7 and 10 are superseded by this round.

- **Important 1 — no fabricated return entry.** `meanReturns` no longer falls back to `sample.anchor.index`: `const triggerIndex = sample.breakoutIndex; if (triggerIndex === undefined) continue;`. New test: five confirmed samples without `breakoutIndex` stay `{ h1: null, h3: null, h5: null }`; with the old fallback the same fixture produced `h1 ≈ 1.887`.
- **Important 2 — R-PAT-17 neutral target floor.** `PatternConfig`/`PATTERN_CONFIG` gain `neutralMinTargetAtr: 0.5`; the neutral branch now computes `const target = Math.max(height / 2, config.neutralMinTargetAtr * atr);`. New test: a converged neutral (upper = lower = 105, height 0, `atr = 1`) stays `unresolved` after a 0.3 follow-through and only succeeds at 0.6 ≥ 0.5·atr. The old code returned `success` at 0.3 (zero-height target).
- **Minor 3 — R-PAT-18 `returnsMinSamples`.** `PatternConfig`/`PATTERN_CONFIG` gain `returnsMinSamples: 5`; the literal `5` in `meanReturns` is replaced by `config.returnsMinSamples`.
- **Minor 4 — added tests.** Neutral down-bias: first break below 104, then a close of 102 with `atr = 4` (target `max(1, 2) = 2 = 0.5·atr`) is `success`. Bearish sample: five bearish samples with `breakoutIndex` 4 on a falling series report `h1 > 0` and exactly `(104 − 102) / 104 × 100`. The exact-pin config test now includes both new keys.

Red (before implementation; 3 failed | 7 passed):

```
 FAIL  src/features/technical/model/patterns/__tests__/config.test.ts > PATTERN_CONFIG > pins every default threshold and window exactly as specified in the brief
 FAIL  src/features/technical/model/patterns/__tests__/outcome.test.ts > outcome > floors the neutral target at half an ATR when the pattern has converged
       AssertionError: expected 'success' to be 'unresolved'
 FAIL  src/features/technical/model/patterns/__tests__/outcome.test.ts > outcome > skips samples without a breakout index instead of fabricating an entry
       AssertionError: expected { h1: 1.8867924528301887, h3: 3.7735849056603774, h5: 5.660377358490567 } to deeply equal { h1: null, h3: null, h5: null }

 Test Files  2 failed (2)
      Tests  3 failed | 7 passed (10)
```

Green:

```
RUN  v3.2.7 D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2

 ✓ src/features/technical/model/patterns/__tests__/config.test.ts (1 test) 12ms
 ✓ src/features/technical/model/patterns/__tests__/outcome.test.ts (9 tests) 18ms

 Test Files  2 passed (2)
      Tests  10 passed (10)
```

`cd frontend-v2 && npx tsc --noEmit` → exit 0 (no output). Whole patterns folder: 6 files, 41 tests passed.

Files touched: `outcome.ts`, `config.ts`, `__tests__/outcome.test.ts`, `__tests__/config.test.ts`.
