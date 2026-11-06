# Task 2 Report — Pattern types and shared config

- Status: DONE
- Worktree: `D:/BorsTerminal-worktrees/4axes-main-integration`
- Branch: `integration/4axes-main-2026-11-03` (local only, not pushed)
- Commit: `1af66d14` — `feat(technical): انواع و پیکربندی الگوهای کلاسیک`
- Author: `johnwarchief <johnwarchief@users.noreply.github.com>` (via `git -c ... commit`)
- Base: `286768cd`

## Files changed (exactly the three named by the brief)

| File | Change |
|---|---|
| `frontend-v2/src/features/technical/model/patterns/types.ts` | New. `PatternKind`, `PatternStatus`, `PatternDirection`, `PatternFamily`, `PatternPoint`, `BoundaryLine`, `ChartPattern` — verbatim from the brief. |
| `frontend-v2/src/features/technical/model/patterns/config.ts` | New. `PatternConfig` interface and `PATTERN_CONFIG` — verbatim from the brief. |
| `frontend-v2/src/features/technical/model/patterns/__tests__/config.test.ts` | New. Brief's test verbatim. |

Verified by script: all three files are byte-identical (after CRLF normalization) to the corresponding code blocks in `task-2-brief.md` — output `IDENTICAL` for each. No existing file was modified. `pivots.ts`, `types.ts` (model-level), `_audit/`, `docs/`, and the backend-go scratch file were not touched.

## Red run (verbatim, Step 2)

Command: `cd frontend-v2 && npx vitest run src/features/technical/model/patterns/__tests__/config.test.ts`

The brief expected `FAIL with "Cannot find module '../config'"`; Vitest/Vite reports the same import-resolution failure with its own wording (`Failed to resolve import "../config" ... Does the file exist?`).

```
RUN  v3.2.7 D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2


⎯⎯⎯⎯⎯⎯ Failed Suites 1 ⎯⎯⎯⎯⎯⎯

 FAIL  src/features/technical/model/patterns/__tests__/config.test.ts [ src/features/technical/model/patterns/__tests__/config.test.ts ]
Error: Failed to resolve import "../config" from "src/features/technical/model/patterns/__tests__/config.test.ts". Does the file exist?
  Plugin: vite:import-analysis
  File: D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2/src/features/technical/model/patterns/__tests__/config.test.ts:3:31
  1  |  import { describe, expect, it } from "vitest";
  2  |  import { PATTERN_CONFIG } from "../config";
     |                                  ^
  3  |  describe("PATTERN_CONFIG", () => {
  4  |    it("keeps every window positive and every tolerance in ATR terms", () => {
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
   Start at  14:37:16
   Duration  3.16s (transform 38ms, setup 0ms, collect 0ms, tests 0ms, environment 2.23s, prepare 246ms)

EXIT_CODE=1
```

## Green run (verbatim, Step 4)

Command: `cd frontend-v2 && npx vitest run src/features/technical/model/patterns/__tests__/config.test.ts`

```
RUN  v3.2.7 D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2

 ✓ src/features/technical/model/patterns/__tests__/config.test.ts (1 test) 9ms

 Test Files  1 passed (1)
      Tests  1 passed (1)
   Start at  14:37:34
   Duration  3.70s (transform 115ms, setup 0ms, collect 101ms, tests 9ms, environment 2.58s, prepare 272ms)

EXIT_CODE=0
```

No assertion was modified, added, or weakened relative to the brief's test.

## Additional verification

- Whole patterns folder, `npx vitest run src/features/technical/model/patterns`:

```
RUN  v3.2.7 D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2

 ✓ src/features/technical/model/patterns/__tests__/config.test.ts (1 test) 10ms
 ✓ src/features/technical/model/patterns/__tests__/pivots.test.ts (4 tests) 10ms

 Test Files  2 passed (2)
      Tests  5 passed (5)
   Start at  14:37:45
   Duration  4.04s (transform 187ms, setup 0ms, collect 191ms, tests 20ms, environment 5.54s, prepare 725ms)

EXIT_CODE=0
```

- `npx tsc -b` in `frontend-v2`: exit 0, no output.
- Full suite `npx vitest run` in `frontend-v2`: **73 files passed, 572 tests passed**, exit 0 (baseline after Task 1: 72/571; +1 file, +1 test from this task). Tail:

```
 ✓ src/features/technical/model/patterns/__tests__/config.test.ts (1 test) 11ms
 ✓ src/features/technical/model/patterns/__tests__/pivots.test.ts (4 tests) 17ms

 Test Files  73 passed (73)
      Tests  572 passed (572)
   Start at  14:38:41
   Duration  90.74s (transform 14.36s, setup 0ms, collect 99.96s, tests 74.35s, environment 350.87s, prepare 34.36s)

EXIT_CODE=0
```

## Residual risks

1. **Test coverage is intentionally narrow (brief's test verbatim).** It asserts `maxBars > 2` for the seven pattern kinds, `0 < flag.channelMaxWidthPct <= 60`, `triangle.flatToleranceAtr > 0`, `outcomeHorizon === 10`, `returnHorizons === [1,3,5]`, and `formationMinResolved === 8`. Nothing pins `pivLeft`/`pivRight`/`atrPeriod`/`minTouchesPerLine`/`invalidationBufferAtr`, any `convergenceMin`, `rectangle.flatToleranceAtr`, or the `hs`/`triple` tolerances; a transcription error in those fields would pass the suite. Mitigated here by the byte-identity check against the brief; the detector tests in Tasks 4–7 are the first behavioral check of these values.
2. **Thresholds are uncalibrated constants.** The numeric geometry thresholds come from the brief and are not derivable from tests; if live acceptance (Task 10) shows too many/too few detections, tuning happens in `PATTERN_CONFIG` and may require re-baselining detector fixtures.
3. **`returnHorizons` is a mutable 3-tuple and `PATTERN_CONFIG` is not frozen.** `ChartPattern.returns` hardcodes `h1/h3/h5`; nothing in the type system keeps that shape in sync with `returnHorizons`, and a consumer could mutate the shared config at runtime. Future edits should treat `PATTERN_CONFIG` as read-only.
4. **`ChartPattern` shape is a contract for Tasks 3–7.** Fields like `anchor`, optional `neckline`/`breakoutIndex`, and `formation?: FormationEstimate` (`import type`, so no runtime cycle with `model/types.ts`) are fixed now; if a detector needs an extra field, the interface must be extended in the detector task without breaking already-committed consumers.
5. Not committed by design: this report; the pre-existing modified `docs/superpowers/plans/2026-11-05-classic-chart-patterns.md` and untracked `_audit/rebuild/`, `docs/superpowers/plans/2026-11-05-fts-veto-honesty-and-unslop.md`, `docs/superpowers/plans/2026-11-05-technical-phase-gap-and-plan.md`, and `backend-go/internal/fundamental/zz_tmp_dump_test.go` were left untouched (verified via `git status` after commit).

## Fix round 1

Review finding: the config test only range-checked values (`maxBars > 2`, `0 < channelMaxWidthPct <= 60`, etc.), so a typo'd threshold could still pass.

Change (test only, `config.ts` untouched): in `frontend-v2/src/features/technical/model/patterns/__tests__/config.test.ts`, replaced all loose assertions with a single exact deep-equality pin of the whole object — `expect(PATTERN_CONFIG).toEqual({ ...all 15 keys verbatim from the brief... })`. The former `returnHorizons`/`formationMinResolved`/`outcomeHorizon` assertions were removed as fully subsumed by the exact match. Renamed the `it` to `pins every default threshold and window exactly as specified in the brief`. Any changed, missing, or extra key now fails.

Command: `cd frontend-v2 && npx vitest run src/features/technical/model/patterns/__tests__/config.test.ts`

```
RUN  v3.2.7 D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2

 ✓ src/features/technical/model/patterns/__tests__/config.test.ts (1 test) 9ms

 Test Files  1 passed (1)
      Tests  1 passed (1)
   Start at  14:46:36
   Duration  3.30s (transform 83ms, setup 0ms, collect 74ms, tests 9ms, environment 2.29s, prepare 252ms)

EXIT_CODE=0
```

Commit: `ffe351e9130a063c2c78ee00e6fc5faa6a7892ef` — `test(technical): پین دقیق مقادیر پیش‌فرض پیکربندی الگوهای کلاسیک` (only the test file; author `johnwarchief <johnwarchief@users.noreply.github.com>`).
