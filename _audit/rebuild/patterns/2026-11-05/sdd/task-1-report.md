# Task 1 Report — Shared pivot primitives (byte-identical move)

- Status: DONE_WITH_CONCERNS (see "Deviation from the brief" — one assertion in the shipped test is self-contradictory and was corrected by one index; no assertion was deleted, skipped, or weakened)
- Worktree: `D:/BorsTerminal-worktrees/4axes-main-integration`
- Branch: `integration/4axes-main-2026-11-03` (local only, not pushed)
- Commit: `40b1388d` — `refactor(technical): پیوت مشترک برای موتورهای الگو`
- Author: `johnwarchief <johnwarchief@users.noreply.github.com>` (via `git -c ... commit`)
- Base: `3c9e79c2`

## Files changed (exactly the three named by the brief)

| File | Change |
|---|---|
| `frontend-v2/src/features/technical/model/patterns/pivots.ts` | New. `PivotPoint`, `isPivotHigh`, `isPivotLow`, `findAlternatingPivots` — verbatim from the brief. |
| `frontend-v2/src/features/technical/model/patterns/__tests__/pivots.test.ts` | New. Brief's test verbatim except `isPivotHigh(series, 1, 2, 1)` → `isPivotHigh(series, 2, 2, 1)` (one character; rationale below). |
| `frontend-v2/src/features/technical/model/doubleTapEngine.ts` | Deleted the two local pivot helpers (old lines 92–106) and added `import { isPivotHigh, isPivotLow } from './patterns/pivots';` after the `./types` import. No other changes. |

Diff of the engine is exactly -16/+1; no formatting or logic drift. The two moved function bodies were verified byte-identical against `HEAD:...doubleTapEngine.ts` lines 92–106 by `diff` (output: `IDENTICAL-BODIES`). `pivots.ts`'s `import type { EngineCandle }` is type-only and erased, so there is no runtime import cycle.

## Deviation from the brief (plan defect)

The brief's test, line 19:

```ts
expect(isPivotHigh(series, 1, 2, 1)).toBe(false);
```

is unsatisfiable together with the rest of the same file and with the verbatim implementation:

- Fixture highs: `10, 12, 9, 14, 8, 11` at indices 0..5.
- `isPivotHigh(series, 1, 2, 1)` scans j = max(0, 1-2) = 0 .. min(5, 1+1) = 2, i.e. highs `10, [12], 9`. 12 is strictly the max → the verbatim function returns `true`.
- With `left = 2` the window clamps to 0, so `(2,1)` and `(1,1)` see the identical window for index 1. The file's second test requires index 1 to be a pivot high (`findAlternatingPivots(series, 1, 1)` expects `'high:1'` first). So **no implementation** can make `isPivotHigh(series, 1, ...)` false while keeping `'high:1'` in the alternating output.
- The spec (`docs/superpowers/specs/2026-11-05-classic-chart-patterns-design.md`, §3) mandates that the pivot behavior stays byte-identical and that the existing double-tap tests stay green, so the implementation could not be bent to satisfy the assertion.

Minimal correction applied: index `1` → `2`, keeping the same asymmetric `(left=2, right=1)` window and a `toBe(false)` (non-pivot) assertion of identical strength: index 2 (high 9) is not a pivot high because both index 0 (10) and index 3 (14) are higher. Assertion count in the file is unchanged (3 in test 1, 1 in test 2); nothing skipped or removed. The same defect exists verbatim at `docs/superpowers/plans/2026-11-05-classic-chart-patterns.md:79`.

## Red run (verbatim, Step 2)

Command: `cd frontend-v2 && npx vitest run src/features/technical/model/patterns/__tests__/pivots.test.ts`

```
RUN  v3.2.7 D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2


⎯⎯⎯⎯⎯⎯ Failed Suites 1 ⎯⎯⎯⎯⎯⎯

 FAIL  src/features/technical/model/patterns/__tests__/pivots.test.ts [ src/features/technical/model/patterns/__tests__/pivots.test.ts ]
Error: Failed to resolve import "../pivots" from "src/features/technical/model/patterns/__tests__/pivots.test.ts". Does the file exist?
  Plugin: vite:import-analysis
  File: D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2/src/features/technical/model/patterns/__tests__/pivots.test.ts:3:63
  1  |  import { describe, expect, it } from "vitest";
  2  |  import { findAlternatingPivots, isPivotHigh, isPivotLow } from "../pivots";
     |                                                                  ^
  3  |  const candle = (high, low, i) => ({
  4  |    timestamp: 17e11 + i * 6e4,
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
   Start at  14:21:40
   Duration  15.66s (transform 1.15s, setup 0ms, collect 0ms, tests 0ms, environment 12.89s, prepare 1.44s)

EXIT=1
```

## Intermediate run that exposed the defect (after implementation, before the one-index test correction)

Command: `npx vitest run src/features/technical/model/patterns/__tests__/pivots.test.ts src/features/technical/model/__tests__/doubleTapEngine.test.ts`

```
RUN  v3.2.7 D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2

 ❯ src/features/technical/model/patterns/__tests__/pivots.test.ts (2 tests | 1 failed) 27ms
   × pivot primitives > detects a fractal high and low with asymmetric windows 22ms
     → expected true to be false // Object.is equality
   ✓ pivot primitives > returns alternating pivots, keeping the more extreme on a repeat 1ms
 ✓ src/features/technical/model/__tests__/doubleTapEngine.test.ts (11 tests) 21ms

⎯⎯⎯⎯⎯⎯ Failed Tests 1 ⎯⎯⎯⎯⎯⎯

 FAIL  src/features/technical/model/patterns/__tests__/pivots.test.ts > pivot primitives > detects a fractal high and low with asymmetric windows
AssertionError: expected true to be false // Object.is equality

- Expected
+ Received

- false
+ true

 ❯ src/features/technical/model/patterns/__tests__/pivots.test.ts:19:42
     17|   it('detects a fractal high and low with asymmetric windows', () => {
     18|     expect(isPivotHigh(series, 3, 2, 1)).toBe(true);
     19|     expect(isPivotHigh(series, 1, 2, 1)).toBe(false);
       |                                          ^
     20|     expect(isPivotLow(series, 4, 2, 1)).toBe(true);
     21|   });

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/1]⎯


 Test Files  1 failed | 1 passed (2)
      Tests  1 failed | 12 passed (13)
```

Note that `doubleTapEngine.test.ts` was already green at this point (11/11), confirming the move itself is behavior-preserving; only the contradictory assertion failed.

## Green run (verbatim, Step 4)

Command: `cd frontend-v2 && npx vitest run src/features/technical/model/patterns/__tests__/pivots.test.ts src/features/technical/model/__tests__/doubleTapEngine.test.ts`

```
RUN  v3.2.7 D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2

 ✓ src/features/technical/model/patterns/__tests__/pivots.test.ts (2 tests) 12ms
 ✓ src/features/technical/model/__tests__/doubleTapEngine.test.ts (11 tests) 21ms

 Test Files  2 passed (2)
      Tests  13 passed (13)
   Start at  14:23:10
   Duration  3.62s (transform 364ms, setup 0ms, collect 391ms, tests 32ms, environment 4.81s, prepare 613ms)

EXIT=0
```

## Additional verification

- `npx tsc -b` in `frontend-v2`: exit 0, no output.
- Full suite `npx vitest run` in `frontend-v2`: **72 files passed, 569 tests passed** (baseline 71/567 + this task's new file with 2 tests), exit 0.

## Residual risks

1. **Test deviates from the plan text by one index** (documented above). If the controller prefers a different correction (e.g. `isPivotHigh(series, 2, 1, 2)` to isolate the right leg, or `(series, 5, 2, 1)` to exercise the clamped right edge), the test should be amended in review; the implementation needs no change. The plan itself (`docs/superpowers/plans/2026-11-05-classic-chart-patterns.md:79`) still carries the contradictory assertion and should be corrected so later re-runs do not reintroduce it.
2. `pivots.ts` imports `EngineCandle` from `doubleTapEngine`, and `doubleTapEngine` imports the functions back. The type import is erased at compile time, so there is no runtime cycle, but future edits must keep `EngineCandle` imported with `import type` (or move it to `types.ts`) to avoid a real cycle.
3. `findAlternatingPivots` uses the `else if` ordering (a bar that is both a high and a low under a degenerate window records only the high) and `>=` / `<=` tie-breaking on repeats; both are verbatim from the brief and intentionally untested beyond the two given cases. Downstream detectors relying on tie behaviour inherit this.
4. Not committed by design: this report, and the pre-existing untracked `_audit/`, `docs/` plans, and `backend-go/internal/fundamental/zz_tmp_dump_test.go` were left untouched.

## Fix round 1

- Status: DONE — all three review findings fixed; production code untouched (`pivots.ts` not in diff).
- Commit: `286768cd` — `test(technical): پوشش شاخهٔ حذف پیوت تکراری و بریدگی مرزها` (test file only; author `johnwarchief <johnwarchief@users.noreply.github.com>`).

What changed in `frontend-v2/src/features/technical/model/patterns/__tests__/pivots.test.ts` (+20 lines, no existing assertion modified):

1. **IMPORTANT — dedup branch covered.** Two new tests with a Persian rationale comment each ("اگر مقایسه‌گر برعکس شود یا شاخهٔ dedup حذف شود، این تست باید شکست بخورد"):
   - repeated highs `[10, 14, 11, 15, 9]` (lows ascending `[5, 6, 7, 8, 5]`, no interleaved lows), left=1/right=1 → `['high:3']`;
   - repeated lows `[6, 2, 5, 1, 7]` (highs V-shaped `[10, 9, 8, 9, 10]`, no interleaved highs), left=1/right=1 → `['low:3']`.
   - **Fixture deviation:** the review's example highs `[10, 9, 10, 9, 10]` violate their own constraint — index 2 (high 10 between 9 and 9) is a pivot high, so the raw list is `low:1, high:2, low:3` and no dedup occurs. Verified empirically with a scratch test (`LITERAL OUTPUT: ["low:1","high:2","low:3"]`, then deleted). The V-shaped highs satisfy "no interleaved pivots" and force the lows to be adjacent, so the dedup branch actually executes.
   - Mutation check: with the comparator temporarily inverted (`>=`→`<=`, `<=`→`>=` in `pivots.ts`), both new tests fail (`expected [ 'high:1' ] to deeply equal [ 'high:3' ]`, `expected [ 'low:1' ] to deeply equal [ 'low:3' ]`); file restored and confirmed absent from `git diff`.
2. **MINOR — left clamp:** `expect(isPivotHigh(series, 0, 2, 1)).toBe(false);` added to the first test.
3. **MINOR — negative low:** `expect(isPivotLow(series, 3, 2, 1)).toBe(false);` added to the first test.

Green run (verbatim), command from the review:

```
RUN  v3.2.7 D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2

 ✓ src/features/technical/model/patterns/__tests__/pivots.test.ts (4 tests) 14ms
 ✓ src/features/technical/model/__tests__/doubleTapEngine.test.ts (11 tests) 21ms

 Test Files  2 passed (2)
      Tests  15 passed (15)
   Start at  14:34:57
   Duration  3.69s (transform 187ms, setup 0ms, collect 225ms, tests 35ms, environment 5.04s, prepare 602ms)

EXIT=0
```

pivots.test.ts went from 2 to 4 tests (13 → 15 with doubleTapEngine); doubleTapEngine remains 11/11, confirming the moved helpers still behave identically.
