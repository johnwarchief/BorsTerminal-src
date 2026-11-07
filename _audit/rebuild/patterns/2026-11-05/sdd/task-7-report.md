# Task 7 report — formation estimate and registry

- Worktree: `D:/BorsTerminal-worktrees/4axes-main-integration`
- Branch: `integration/4axes-main-2026-11-03` (local only, no push)
- Base: `53ff03f1` (Task 6 review-fix HEAD)
- Commit: `fbea9474` — `feat(technical): نرخ تشکیل تاریخی و رجیستری الگوها`
- Committed files (only these five):
  - `frontend-v2/src/features/technical/model/patterns/formation.ts`
  - `frontend-v2/src/features/technical/model/patterns/registry.ts`
  - `frontend-v2/src/features/technical/model/patterns/__tests__/formation.test.ts`
  - `frontend-v2/src/features/technical/model/patterns/__tests__/registry.test.ts`
  - `frontend-v2/src/features/technical/model/doubleTapEngine.ts` (`export` added to `confidenceFor` only)

## What landed

- `estimatePatternFormation(current, all, candles, atr, config)` and `estimateReturns(current, all, candles, config)` — the brief's code verbatim (family pooling per R-PAT-1; probability only at `formationMinResolved`, Laplace rate + Wilson interval, quality tercile only when the bucket itself has 8+ resolved).
- `fromDoubleTap(p)` adapter, plus `detectAllPatterns` and `selectFeaturedPatterns` per the brief.
- `detectAllPatterns` applies the reversal-over-continuation overlap filter (`withoutOverlaps`) before enrichment and sorting, as the plan's self-review and R-PAT-6 require. The filtered pool is also what `estimatePatternFormation`/`estimateReturns` receive, so dropped continuations do not silently contribute to statistics.
- `fromDoubleTap` copies `breakoutIndex` per R-PAT-19, so `meanReturns` (Task 6) measures reversal returns from the real double-tap breakout instead of skipping/mis-anchoring. `breakoutTs` is not carried: `ChartPattern` has no such field and nothing downstream reads it.
- `confidenceFor` exported from `doubleTapEngine.ts`; the diff on that file is exactly the one-word `export` addition (verified by `git diff`).
- No `readonly EngineCandle[]` cast was needed: `calculateAtr` and `detectDoubleTapPatterns` already accept `readonly EngineCandle[]`.

## Test coverage

- (a) the two brief registry tests verbatim (merge with real double taps; featured cap of six).
- (b) the two brief formation tests verbatim (`probability === null` and `resolved < 8` under eight resolved; `null` for non-forming).
- (c) overlap filter: a synthetic continuation anchored at bar 10 and a reversal anchored at bar 12 (within 3 bars) — the near continuation is dropped, the reversal survives, a far continuation (bar 30) survives. The test injects synthetic detector output with `vi.mock` (`importOriginal` delegation); the delegates fall back to the real detectors whenever the synthetic pool is `null`, and an `afterEach` resets it, so the brief tests in the same file still run the real `detectContinuation`/`detectReversal`.
- (d) `fromDoubleTap` breakout: a `DoubleTapPattern` with `breakoutIndex: 26` (and `breakoutTs`) is adapted and `adapted.breakoutIndex === 26` is asserted, along with kind and family.
- No assertion from the brief was weakened or removed.

## TDD red (verbatim, before implementation)

```
RUN  v3.2.7 D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2


⎯⎯⎯⎯⎯⎯ Failed Suites 2 ⎯⎯⎯⎯⎯⎯⎯

 FAIL  src/features/technical/model/patterns/__tests__/formation.test.ts [ src/features/technical/model/patterns/__tests__/formation.test.ts ]
Error: Failed to resolve import "../formation" from "src/features/technical/model/patterns/__tests__/formation.test.ts". Does the file exist?
  Plugin: vite:import-analysis
  File: D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2/src/features/technical/model/patterns/__tests__/formation.test.ts:2:41
  1  |  import { describe, expect, it } from "vitest";
  2  |  import { estimatePatternFormation } from "../formation";
     |                                            ^
  3  |  import { PATTERN_CONFIG } from "../config";
  4  |  const point = (index, price) => ({ index, price, timestamp: index * 6e4 });

 FAIL  src/features/technical/model/patterns/__tests__/registry.test.ts [ src/features/technical/model/patterns/__tests__/registry.test.ts ]
Error: Failed to resolve import "../registry" from "src/features/technical/model/patterns/__tests__/registry.test.ts". Does the file exist?
  Plugin: vite:import-analysis
  File: D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2/src/features/technical/model/patterns/__tests__/registry.test.ts:2:0
  14 |    };
  15 |  });
  16 |  const __vi_import_0__ = await import("../registry");
     |                                       ^

 Test Files  2 failed (2)
      Tests  no tests
```

## Green

Focused (brief Step 4 command):

```
RUN  v3.2.7 D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2

 ✓ src/features/technical/model/__tests__/doubleTapEngine.test.ts (11 tests) 25ms
 ✓ src/features/technical/model/patterns/__tests__/formation.test.ts (2 tests) 11ms
 ✓ src/features/technical/model/patterns/__tests__/registry.test.ts (4 tests) 26ms

 Test Files  3 passed (3)
      Tests  17 passed (17)
```

Whole patterns folder plus the engine spec: 9 files, 58 tests passed.

Full suite: `npx vitest run` → `Test Files 79 passed (79)`, `Tests 614 passed (614)`.

Typecheck: `npx tsc --noEmit -p tsconfig.json` → exit 0 (no output). First run caught that `DoubleTapPattern` is not re-exported from `doubleTapEngine`; fixed by importing the type from `../types` in the test and in `registry.ts` (the brief's import list was the only deviation).

## Residual risks

1. **Overlap window is a literal 3, not config.** R-PAT-6/the plan fix the half-width at `<= 3` bars; changing it later means touching `registry.ts` (and no test drives any other window). It is also asymmetric: a continuation is always dropped in favour of any reversal in range, regardless of quality or confinement.
2. **Overlap exclusion also shrinks the statistics pool.** Because the enrichment receives `withoutOverlaps` (the plan's wording), dropped continuations do not count as formation/return samples. This is defensible (they are not displayed) but it can push continuation samples below the 8/5 thresholds on series where overlaps are dense.
3. **Formation math beyond the brief is untested.** The two formation tests pin the `< 8` null gate and the non-forming null, but not `laplaceRate` inputs, the quality-tercile switch, or Wilson bounds; those rest on code copied from the brief and on Task 6-tested primitives. The registry tests are shape/count assertions (the brief's) and cannot catch a detector regression beyond double-tap integrity — that is Task 10's regression job.
4. **Overlap test relies on module mocking.** `vi.mock` + `importOriginal` is only valid as long as `detectAllPatterns` keeps the named imports; a refactor to dynamic imports would silently fall back to real detectors and the test would fail loudly rather than pass vacuously (the synthetic ids are absent from real output), but the failure mode is test infrastructure, not production code.
5. **Returns for forming patterns remain mostly `null` early.** `estimateReturns` passes the whole non-forming family pool to `meanReturns`, which now requires `breakoutIndex`; reversal samples adapted from doubles only contribute after `fromDoubleTap` copies the breakout. Pre-breakout doubles contribute nothing by design (R-PAT-19 + Task 6 Important 1), so `returns` may lag `formation` even when `formation.resolved >= 8`.
6. **Right-edge truncation bias persists.** `estimatePatternFormation` keeps samples with `anchor.index + 1 < candles.length`, but `outcomeOf` still marks anything without `outcomeHorizon` bars after the anchor `unresolved`, so the most recent `outcomeHorizon` bars of history are underrepresented in every rate (inherited from Task 6 residual risk 2).
7. **Quality bucket uses sample qualities, not resolved qualities.** Terciles are computed over all non-forming family samples (`qualities`), then applied to `resolved`; when many samples are unresolved the bucket can straddle unused qualities. Matches the brief; flagged because it interacts with risk 6.
8. **`confidenceFor` levels are sample-count only.** The exported `'none' | 'low' | 'medium' | 'high'` ignores interval width; a bucket with 8 same-way outcomes reports `'low'` with a narrow Wilson interval, which the UI (Task 9) may need to temper.

## Fix round 1 (review findings)

- Base: `fbea9474`
- Commit: `9a712a77` — `fix(technical): اصلاح مرزهای دوقلوی کف و آستانه‌های پنهان الگوها`
- Files touched (all committed; this report is git-ignored, so it is not part of the commit):
  - `frontend-v2/src/features/technical/model/patterns/config.ts`
  - `frontend-v2/src/features/technical/model/patterns/formation.ts`
  - `frontend-v2/src/features/technical/model/patterns/registry.ts`
  - `frontend-v2/src/features/technical/model/patterns/__tests__/config.test.ts`
  - `frontend-v2/src/features/technical/model/patterns/__tests__/formation.test.ts`
  - `frontend-v2/src/features/technical/model/patterns/__tests__/registry.test.ts`

### What changed

1. **R-PAT-21 (Critical) — boundary order in `fromDoubleTap`.** Boundaries are now chosen by direction: bullish (`DOUBLE_BOTTOM`) → `upper = neckline`, `lower = peak2`; bearish (`DOUBLE_TOP`) → `upper = peak2`, `lower = neckline`, so `upper.price > lower.price` always holds. Tests: a double-bottom adapter test pins `upper = 100` (neckline), `lower = 91` (trough) and `upper > lower`; an `outcomeOf` test shows a close of 95 (above the trough, below the neckline) is `unresolved`, and only 100.5 (above the neckline) is `success`.
2. **R-PAT-20 (Important) — hidden thresholds.** `overlapWindowBars: 3` added to `PatternConfig`/`PATTERN_CONFIG` (exact-pin config test updated) and used by `detectAllPatterns`; both `8` tercile gates in `formation.ts` are now `config.formationMinResolved`. Tests: the overlap test pins distance 2 dropped / distance 3 dropped / distance 4 kept, and a `{ ...PATTERN_CONFIG, overlapWindowBars: 2 }` run keeps the distance-3 neighbour (fails on the old hard-coded `3`); the 7→8 test also runs `formationMinResolved: 7`, where 7 resolved yields a probability (fails on the old literal `8`).
3. **Spec §8 (Important) — statistics tests.** Added: exact `laplaceRate(6, 4)` / `wilsonInterval(6, 10)` equality from a 6-success/4-failure estimate; the 7→8 gate (7 → `null`, 8 → `laplaceRate(8, 0)`); quality-tercile switch (overall 10/20 vs bucket 10/0 for a q=100 current and 0/20 for q=10); unresolved samples never counted as failures (3 failures + 5 unresolved → `resolved = 3`, `failures = 3`); family pooling (a continuation current sees only the continuation sample, a reversal current only the reversal sample).
4. **R-PAT-22 (Important) — resolved-only returns.** `detectAllPatterns` computes `outcomeOf` once per surviving sample into a map, derives `resolvedIds: ReadonlySet<string>`, and `estimateReturns(..., resolvedIds)` keeps only those samples. Test: five on-time breakouts give non-null returns, and adding a confirmed sample whose breakout sits at `anchor + 15` (> `outcomeHorizon` 10, hence unresolved) leaves the returns object unchanged (on `fbea9474` h1 moved from 1.0020 to 0.6734).
5. **Minor — resolved-only terciles.** Terciles are now computed from `resolved` qualities instead of all sample qualities. Test: 24 resolved (8×q100 win, 8×q50 loss, 8×q10 loss) + 8 unresolved (q=0); for a q=10 current the bucket now covers both loss groups → 16 failures (old code returned 8 because unresolved qualities polluted the tertile cut points).
6. **Minor — status mapping.** Test pins `active → confirmed` and `invalidated → invalidated`.

### Red proof (new tests against `fbea9474` code)

Only the three implementation files were temporarily stashed; the four focused files then ran against the old implementation:

```
 Test Files  3 failed | 1 passed (4)
      Tests  6 failed | 22 passed (28)
```

Failures were exactly the new assertions: config pin (missing `overlapWindowBars`), resolved terciles (8 vs 16), double-bottom `upper` (91 vs 100), neckline outcome (`success` vs `unresolved`), narrow overlap window (distance-3 neighbour missing), late-breakout returns (h1 0.6734 vs 1.0020). The stash was popped afterwards; no changes were lost.

### Green

Typecheck: `npx tsc --noEmit` → exit 0 (no output).

```
RUN  v3.2.7 D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2

 ✓ src/features/technical/model/patterns/__tests__/config.test.ts (1 test) 10ms
 ✓ src/features/technical/model/__tests__/doubleTapEngine.test.ts (11 tests) 25ms
 ✓ src/features/technical/model/patterns/__tests__/formation.test.ts (8 tests) 22ms
 ✓ src/features/technical/model/patterns/__tests__/registry.test.ts (8 tests) 35ms

 Test Files  4 passed (4)
      Tests  28 passed (28)
```

Whole patterns folder: 8 files, 57 tests passed.

### Notes

- Residual risk 1 (overlap literal) and risk 7 (terciles over all samples) above are closed; risk 3 is partly covered by the new statistics tests.
- `estimatePatternFormation` still runs its own `outcomeOf` pass because it needs the success/failure split; `detectAllPatterns` computes the outcomes once for the R-PAT-22 resolved set. Passing the map into formation would need a signature change the review did not request.
- Tercile cut points keep the `<=` semantics, so a sample exactly at `low` falls in bucket 0 and adjacent buckets can merge; the new tercile test pins this behaviour.
- The overlap filter remains asymmetric (any reversal beats a nearby continuation regardless of quality); unchanged from Task 7.
