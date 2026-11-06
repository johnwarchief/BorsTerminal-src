# Task 5 report — reversal detectors

- Worktree: `D:/BorsTerminal-worktrees/4axes-main-integration`
- Branch: `integration/4axes-main-2026-11-03`
- Base: `717bb514` (Task 4 review-fix HEAD)
- Commit: `e0a95ac2` — `feat(technical): دتکتورهای الگوهای بازگشتی`
- Committed files (only these two):
  - `frontend-v2/src/features/technical/model/patterns/detectReversal.ts`
  - `frontend-v2/src/features/technical/model/patterns/__tests__/reversal.test.ts`

## Rulings applied

- **R-PAT-4**: fixtures pass `FIXTURE_CONFIG = { ...PATTERN_CONFIG, pivLeft: 1, pivRight: 1 }`; every geometric threshold stays a `PATTERN_CONFIG` value and is read from `config` in production. No threshold was changed.
- **R-PAT-5**: every `emitPattern` spec now carries `maxBars` — `config.hs.maxBars` for `HEAD_SHOULDERS`/`INVERSE_HEAD_SHOULDERS`, `config.triple.maxBars` for `TRIPLE_TOP`/`TRIPLE_BOTTOM`.
- **R-PAT-15**: bearish targets below the neckline and stops above the highs; inverse variants mirrored (bullish targets above neckline, stops below the lows). Asserted in the H&S (bearish) and inverse H&S (bullish) tests, plus both triple tests.
- Ascending-order rule: shared `ascendingPoints()` sorts the five pivots by index before every `emitPattern` call; H&S test asserts point order and that `anchor` is the max index.

## TDD red (verbatim, before implementation)

```
RUN  v3.2.7 D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2


⎯⎯⎯⎯⎯⎯ Failed Suites 1 ⎯⎯⎯⎯⎯⎯⎯

 FAIL  src/features/technical/model/patterns/__tests__/reversal.test.ts [ src/features/technical/model/patterns/__tests__/reversal.test.ts ]
Error: Failed to resolve import "../detectReversal" from "src/features/technical/model/patterns/__tests__/reversal.test.ts". Does the file exist?
  Plugin: vite:import-analysis
  File: D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2/src/features/technical/model/patterns/__tests__/reversal.test.ts:3:31
  1  |  import { describe, expect, it } from "vitest";
  2  |  import { detectReversal } from "../detectReversal";
     |                                  ^
  3  |  import { PATTERN_CONFIG } from "../config";
  4  |  function zigzag(start, legs) {
 ❯ TransformPluginContext._formatError ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:49258:41
 ❯ TransformPluginContext.error ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:49253:16
 ❯ normalizeUrl ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:64307:23
 ❯ ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:64439:39
 ❯ TransformPluginContext.transform ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:64366:7
 ❯ PluginContainer.transform ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:49099:18
 ❯ loadAndTransform ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:51978:27

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/1]⎯


 Test Files  1 failed (1)
      Tests  no tests
   Start at  15:27:41
   Duration  3.69s (transform 39ms, setup 0ms, collect 0ms, tests 0ms, environment 2.67s, prepare 230ms)
```

No intermediate fixture-red run was needed: the first green run after implementation passed all five tests.

## Green

Focused spec:

```
 ✓ src/features/technical/model/patterns/__tests__/reversal.test.ts (5 tests) 16ms

 Test Files  1 passed (1)
      Tests  5 passed (5)
```

Whole patterns folder:

```
 ✓ src/features/technical/model/patterns/__tests__/config.test.ts (1 test) 11ms
 ✓ src/features/technical/model/patterns/__tests__/pivots.test.ts (4 tests) 17ms
 ✓ src/features/technical/model/patterns/__tests__/geometry.test.ts (4 tests) 14ms
 ✓ src/features/technical/model/patterns/__tests__/reversal.test.ts (5 tests) 18ms
 ✓ src/features/technical/model/patterns/__tests__/continuation.test.ts (13 tests) 34ms

 Test Files  5 passed (5)
      Tests  27 passed (27)
```

`npx tsc -b` exits 0.

## Kinds actually exercised by the fixtures

Probed with a temporary spec (deleted before commit); all intended patterns are `confirmed`:

| Fixture | Kinds produced |
|---|---|
| `headShouldersSeries` | `HEAD_SHOULDERS:confirmed` (breakout bar 25) |
| `inverseHeadShouldersSeries` | `INVERSE_HEAD_SHOULDERS:confirmed` (breakout bar 24) |
| `tripleTopSeries` | `TRIPLE_TOP:confirmed` (breakout bar 25) + `TRIPLE_BOTTOM:invalidated` from the preceding 5-pivot window |
| `tripleBottomSeries` | `TRIPLE_BOTTOM:confirmed` (breakout bar 25) + `TRIPLE_TOP:invalidated` from the preceding 5-pivot window |

Fixture note: the brief's literal arrays (12 bars, default pivots) never form five alternating pivots (only two are found even with 1/1 windows), so the fixtures were rebuilt as six-pivot zigzags in the style of `continuation.test.ts`. Bars were adjusted, thresholds were not.

## Residual risks

- **Intra-family overlap**: a six-pivot triple fixture also yields the opposite triple shape as `invalidated` from the overlapping first window. Harmless (invalidated, not confirmed) and consistent with `emitPattern` keeping invalidated patterns, but downstream consumers see both kinds for such inputs.
- **No cross-family suppression**: reversal detectors do not dedupe against continuation output (Task 4's R-PAT-14 was intra-continuation only); a shape can in principle be reported by both families.
- **Shared window guard**: the pre-filter uses `config.hs.maxBars` for both families (both 120 in `PATTERN_CONFIG`); per-family expiry is enforced correctly via `emitPattern`'s `maxBars`, but the pre-filter would diverge if the two maxBars values are ever set apart.
- **Fixture-only pivot override**: the fixtures set `pivLeft/pivRight = 1`; production behavior with `PATTERN_CONFIG`'s 5/4 windows is unexercised at unit level (same stance as Task 4).
- **Quality formula** is a heuristic score, not a detection gate; no test asserts a numeric quality band beyond `emitPattern` clamping.

## Fix round 1

Commit: `53b67ff6` — `fix(technical): اصلاح یافته‌های بازبینی دتکتورهای بازگشتی`

Committed files (only these four):

- `frontend-v2/src/features/technical/model/patterns/detectReversal.ts`
- `frontend-v2/src/features/technical/model/patterns/config.ts`
- `frontend-v2/src/features/technical/model/patterns/__tests__/reversal.test.ts`
- `frontend-v2/src/features/technical/model/patterns/__tests__/config.test.ts`

### Addressed

1. **IMPORTANT — hidden minimum span (R-PAT-16)**: `reversal: { minSpanBars: 6 }` added to `PatternConfig`/`PATTERN_CONFIG`; the literal `span < 6` is replaced with `span < config.reversal.minSpanBars` in the shared pre-filter, covering both H&S and triples. The exact-pin config test now includes `reversal: { minSpanBars: 6 }`, and a behavioral test proves the value is actually read: a five-pivot window with `span = 4` yields no `HEAD_SHOULDERS` under the default 6 and yields one when the fixture config overrides `minSpanBars: 4`.
2. **IMPORTANT — negative fixtures**: `shouldersApartSeries` (shoulder highs 111/109, 2 > 0.6×1.5 = 0.9), `shallowHeadSeries` (head 0.3 = 0.2×1.5 above the taller shoulder vs the 0.5 ATR gate) and `spreadTripleTopSeries` (peaks 111/111.5/112 at `atr = 1`) each assert none of the target kind. `headShouldersBrokenAboveHeadSeries` closes above the head (bar 26) before any neckline break and asserts the emitted H&S is `invalidated`, never `confirmed`.
3. **MINOR — quality constants**: `QUALITY_BASE = 55`, `QUALITY_HEADROOM = 35`, `QUALITY_FLOOR = 10`, `QUALITY_CEILING = 100`; the saturation `+10` is gone (it made 100 reachable at 1.2 ATR), so the live range is 55..90 inside a 10..100 clamp.
4. **MINOR — triples pre-filter**: the window cap is now `Math.max(config.hs.maxBars, config.triple.maxBars)` for both `span` and staleness (`e.index`), instead of `hs.maxBars`.
5. **MINOR — measured move**: heights for H&S, inverse H&S, triple top and triple bottom are measured from `lineValue(neck, e.index)` (the anchor/rightmost pivot), not `min`/`max` of the valleys, so target and the breakout line share one reference.
6. **MINOR — triple level equality**: `max(a,c,e) − min(a,c,e) <= tol` (new `levelSpread`) replaces the chained pairwise check for both triples; the `spreadTripleTopSeries` fixture is exactly the discriminating case — adjacent gaps 0.5 ≤ tol = 0.5 pass the old chain while total spread 1.0 > tol rejects.

### Verification

Red before implementation (config pin + triple spread + config-driven span): `Tests 3 failed | 8 passed (11)`. The old chained rule emitted a confirmed `TRIPLE_TOP` (quality 100, the saturation bug) for the 1 ATR spread fixture.

`cd frontend-v2 && npx tsc --noEmit` → exit 0 (no output).

Focused specs:

```
RUN  v3.2.7 D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2

 ✓ src/features/technical/model/patterns/__tests__/config.test.ts (1 test) 8ms
 ✓ src/features/technical/model/patterns/__tests__/reversal.test.ts (10 tests) 23ms

 Test Files  2 passed (2)
      Tests  11 passed (11)
   Start at  15:37:02
   Duration  4.31s (transform 599ms, setup 0ms, collect 681ms, tests 30ms, environment 5.42s, prepare 583ms)
```

Whole patterns folder:

```
 ✓ src/features/technical/model/patterns/__tests__/config.test.ts (1 test) 13ms
 ✓ src/features/technical/model/patterns/__tests__/pivots.test.ts (4 tests) 15ms
 ✓ src/features/technical/model/patterns/__tests__/geometry.test.ts (4 tests) 32ms
 ✓ src/features/technical/model/patterns/__tests__/continuation.test.ts (13 tests) 52ms
 ✓ src/features/technical/model/patterns/__tests__/reversal.test.ts (10 tests) 33ms

 Test Files  5 passed (5)
      Tests  32 passed (32)
```

### Residual notes

- Quality is now bounded to 55..90; `QUALITY_FLOOR`/`QUALITY_CEILING` are defensive clamps and never bind with the current constants.
- The measured move uses the neck extrapolated to the anchor index; confirmation still evaluates the same neck line at each candidate bar, so the two references coincide at the anchor but can differ downstream for steeply sloped necks (intended by finding 5).
- Negative fixtures cover the top/bearish forms; the mirrored inverse/triple-bottom gates share the same code paths but have no dedicated rejection fixtures.
- `reversal.minSpanBars` is one shared key for both families; diverging spans would need per-family config keys.
- Invalidated reversal patterns remain in detector output (unchanged `emitPattern` behavior), so consumers still see the invalidated H&S alongside confirmed siblings.

