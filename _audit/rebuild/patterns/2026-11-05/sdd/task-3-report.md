# Task 3 Report — Geometry helpers and the two-line emitter

- Status: DONE
- Worktree: `D:/BorsTerminal-worktrees/4axes-main-integration`
- Branch: `integration/4axes-main-2026-11-03` (local only, not pushed)
- Commit: `fa449ecd` — `feat(technical): هندسهٔ مشترک و سازندهٔ الگو`
- Author: `johnwarchief <johnwarchief@users.noreply.github.com>` (via `git -c ... commit`)
- Base: `ffe351e9`
- Controller ruling applied: **R-PAT-5** (`maxBars` on `PatternSpec`; per-family expiry)

## Files changed (exactly the two named by the brief)

| File | Change |
|---|---|
| `frontend-v2/src/features/technical/model/patterns/geometry.ts` | New. `toPoint`, `lineValue`, `lineSlope`, `touchCount`, `patternId`, `PatternSpec`, `emitPattern` — brief verbatim except the R-PAT-5 change. |
| `frontend-v2/src/features/technical/model/patterns/__tests__/geometry.test.ts` | New. Brief's two tests; the expiry test's spec now carries `maxBars: 3` per R-PAT-5. Assertions unchanged. |

No other file touched. `types.ts`, `config.ts`, `pivots.ts`, `_audit/`, `docs/`, and `backend-go/internal/fundamental/zz_tmp_dump_test.go` were left alone (verified via `git status` before staging).

## R-PAT-5 deviation from the brief (intentional, ordered by the controller)

- `PatternSpec` gained required `maxBars: number` (documented as the family window).
- In `emitPattern`, the brief's global window
  `Math.max(config.flag.maxBars, ... config.triple.maxBars)` was replaced by `const maxBars = spec.maxBars;`.
  Both expiry checks now use the pattern's own window.
- Consequence: `config` is unused inside `emitPattern`. It remains in the signature (callers in Tasks 4–5 pass it) and is renamed `_config` to satisfy `noUnusedParameters: true`; a comment in place records the reason. A typecheck with the literal name `config` failed with `TS6133: 'config' is declared but its value is never read`, hence the underscore.
- Test call passes `maxBars: 3` in the spec, as ruled. The `{ ...PATTERN_CONFIG, rectangle: { ...rectangle, maxBars: 3 } }` spread from the brief is kept verbatim.

## Expiry semantics implemented (as written in the brief, now per-spec)

1. Early drop: if `anchor.index < candles.length - maxBars - 1` **and** `spec.points.length < 5`, return `null`
   (young multi-point patterns beyond the window are discarded before scanning; 5+-point patterns are exempt here).
2. Scan from `anchor.index + 1` to the end for the first close beyond `upper`/`lower`:
   - directional break in the pattern's direction → `confirmed` + `breakoutIndex`;
   - opposite break → `invalidated` (kept, emitted).
   Neutral direction never confirms/invalidates in the scan (both branches are guarded by direction).
3. Post-scan: `forming` with `anchor.index < candles.length - maxBars` → `null` (expired forming pattern is dropped; confirmed/invalidated survive).
4. Quality is clamped/rounded to `[0, 100]`; `id` is `kind:anchorIndex:pointIndices...`.

## Red run (verbatim, Step 2)

Command: `cd frontend-v2 && npx vitest run src/features/technical/model/patterns/__tests__/geometry.test.ts`

The brief expected `FAIL with "Cannot find module '../geometry'"`; Vitest/Vite reports the same import-resolution failure in its own wording.

```
RUN  v3.2.7 D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2


⎯⎯⎯⎯⎯⎯ Failed Suites 1 ⎯⎯⎯⎯⎯⎯

 FAIL  src/features/technical/model/patterns/__tests__/geometry.test.ts [ src/features/technical/model/patterns/__tests__/geometry.test.ts ]
Error: Failed to resolve import "../geometry" from "src/features/technical/model/patterns/__tests__/geometry.test.ts". Does the file exist?
  Plugin: vite:import-analysis
  File: D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2/src/features/technical/model/patterns/__tests__/geometry.test.ts:3:50
  1  |  import { describe, expect, it } from "vitest";
  2  |  import { emitPattern, lineSlope, lineValue } from "../geometry";
     |                                                     ^
  3  |  import { PATTERN_CONFIG } from "../config";
  4  |  const candle = (high, low, close, i) => ({
 ❯ TransformPluginContext._formatError ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:49258:41
 ❯ TransformPluginContext.error ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:49253:16
 ❯ normalizeUrl ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:64307:23
 ❯ ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:64439:39
 ❯ TransformPluginContext.transform ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:64366:32
 ❯ PluginContainer.transform ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:49099:18
 ❯ loadAndTransform ../../4-axes/frontend-v2/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:51978:27

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/1]⎯


 Test Files  1 failed (1)
      Tests  no tests
   Start at  14:48:43
   Duration  3.48s (transform 47ms, setup 0ms, collect 0ms, tests 0ms, environment 2.40s, prepare 240ms)
```

## Green run (verbatim, Step 4; after adding `_config` for TS strictness)

Command: `cd frontend-v2 && npx vitest run src/features/technical/model/patterns/__tests__/geometry.test.ts`

```
RUN  v3.2.7 D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2

 ✓ src/features/technical/model/patterns/__tests__/geometry.test.ts (2 tests) 10ms

 Test Files  1 passed (1)
      Tests  2 passed (2)
   Start at  14:50:03
   Duration  3.61s (transform 115ms, setup 0ms, collect 114ms, tests 10ms, environment 2.54s, prepare 240ms)
```

No assertion was modified, added, or weakened. The only test edit versus the brief is the required `maxBars: 3` field in the spec literal (R-PAT-5).

## Additional verification

- `npx tsc --noEmit` in `frontend-v2`: exit 0, no output (after `_config` rename).
- Neighboring patterns folder, `npx vitest run src/features/technical/model/patterns`:

```
RUN  v3.2.7 D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2

 ✓ src/features/technical/model/patterns/__tests__/geometry.test.ts (2 tests) 8ms
 ✓ src/features/technical/model/patterns/__tests__/config.test.ts (1 test) 12ms
 ✓ src/features/technical/model/patterns/__tests__/pivots.test.ts (4 tests) 17ms

 Test Files  3 passed (3)
      Tests  7 passed (7)
   Start at  14:50:14
   Duration  4.29s
```

- `git show --stat fa449ecd`: 2 files changed, 134 insertions(+), both new files; nothing else staged.

## Residual risks

1. **R-PAT-5 changed the public spec contract.** `PatternSpec.maxBars` is now required; Tasks 4–5 must pass their family window (e.g. `PATTERN_CONFIG.rectangle.maxBars`) or the code will not typecheck. `PatternConfig` is no longer consulted by `emitPattern`; the parameter survives only for call-site compatibility (`_config`). If a later task wants config-driven windows back, it must explicitly read `config` again.
2. **`anchor` is the last point of `spec.points`, which is not necessarily the latest swing.** Expiry is measured from that anchor. Detectors must order `points` so the last point is the true latest pivot of the formation, otherwise a stale earlier point could expire or keep a pattern alive incorrectly.
3. **Two-tier expiry is asymmetric.** Sub-5-point formations get an extra −1 bar of grace before the scan (`- maxBars - 1`), and 5+-point formations skip that early return entirely; only the post-scan `forming` check is uniform. This matches the brief, but a 5+-point pattern whose anchor is far in the past is only dropped if it never broke out; a stale confirmed breakout is still emitted (with an old `breakoutIndex`). Outcome/horizon handling is left to later tasks.
4. **Neutral-direction patterns can never leave `forming` in this emitter.** Triangles/rectangles/wedges rely on later confirmation or expiry; nothing here picks a breakout side. If Task 4–5 expects neutral patterns to confirm on either-side break, that logic must be added deliberately (and would change these semantics).
5. **Tolerance units are ATR-agnostic here.** `touchCount` compares absolute price distance to raw `tolerance`; callers must pre-multiply by ATR (`invalidationBufferAtr`-style). No validation of negative tolerance or inverted lines (`from.index > to.index`) — `Math.max(1, span)` silently treats them as flat/vertical; detectors should construct canonical left-to-right lines.
6. **Test coverage is narrow by design (the brief's two tests).** `toPoint`, `touchCount`, `patternId`, quality clamping, confirmed/invalidated paths, and breakout scanning are unexercised here; Tasks 4–5 detector tests are the first behavioral coverage. The expiry test would also pass via the early-return branch alone, so it does not isolate the post-scan check.
7. Not committed by design: this report; pre-existing modified `docs/superpowers/plans/2026-11-05-classic-chart-patterns.md` and untracked `_audit/rebuild/`, `docs/superpowers/plans/2026-11-05-fts-veto-honesty-and-unslop.md`, `docs/superpowers/plans/2026-11-05-technical-phase-gap-and-plan.md`, and `backend-go/internal/fundamental/zz_tmp_dump_test.go` were left untouched.

## Fix round 1

Review found two Important defects; both fixed with tests.

- Status: DONE
- Worktree: `D:/BorsTerminal-worktrees/4axes-main-integration`
- Branch: `integration/4axes-main-2026-11-03` (local only, not pushed)
- Commit: `5387764c` — `fix(technical): تأیید الگوهای خنثی و آستانه‌های نام‌دار انقضا`
- Author: `johnwarchief <johnwarchief@users.noreply.github.com>` (via `git -c ... commit`)
- Files committed (exactly four): `geometry.ts`, `config.ts`, `__tests__/geometry.test.ts`, `__tests__/config.test.ts`. No other file staged; pre-existing modified/untracked files were left as found.

### Important 1 — R-PAT-11: neutral patterns never resolved

The scan in `emitPattern` guarded both branches by direction, so `direction: 'neutral'` could only ever be `forming` and was then dropped by expiry. Now, for neutral specs, a close outside **either** boundary (`brokeUp || brokeDown`) sets `status = 'confirmed'`, `breakoutIndex = i`, and breaks. The emitted pattern keeps `direction: 'neutral'` (returns stay absent per R-PAT-3). The invalidated branch remains directional-only; neutral patterns are never invalidated by this scan.

Tests added in `geometry.test.ts` (shared `neutralSpec` helper, `maxBars: 8`, anchor at index 4):
- close `112` above the `110` upper line at index 6 → `status: 'confirmed'`, `breakoutIndex: 6`, `direction: 'neutral'`.
- close `98` below the `100` lower line at index 7 → `status: 'confirmed'`, `breakoutIndex: 7`, `direction: 'neutral'`.

### Important 2 — R-PAT-12: hidden thresholds

- `PatternConfig` / `PATTERN_CONFIG` gained `expiryGraceBars: 1` and `expiryMinPoints: 5` (placed after `formationMinResolved`).
- `emitPattern` now reads `config.expiryGraceBars` (replacing the literal `- 1`) and `config.expiryMinPoints` (replacing `< 5`) in the early-drop guard.
- The `_config` parameter is restored to `config` now that it is read.
- `config.test.ts` exact `toEqual` pin extended with both keys (would have failed without the rename of `_config` plus these values).

### Verification (verbatim)

`cd frontend-v2 && npx tsc --noEmit` → exit 0, no output.

`cd frontend-v2 && npx vitest run src/features/technical/model/patterns/__tests__/geometry.test.ts src/features/technical/model/patterns/__tests__/config.test.ts src/features/technical/model/__tests__/doubleTapEngine.test.ts`

```
RUN  v3.2.7 D:/BorsTerminal-worktrees/4axes-main-integration/frontend-v2

 ✓ src/features/technical/model/patterns/__tests__/config.test.ts (1 test) 13ms
 ✓ src/features/technical/model/patterns/__tests__/geometry.test.ts (4 tests) 13ms
 ✓ src/features/technical/model/__tests__/doubleTapEngine.test.ts (11 tests) 27ms

 Test Files  3 passed (3)
      Tests  16 passed (16)
   Start at  14:55:18
   Duration  4.33s (transform 413ms, setup 0ms, collect 638ms, tests 53ms, environment 8.96s, prepare 1.00s)
```

### Residual risks after fix round

1. Residual risk 4 from the original report is now closed: neutral patterns confirm on either-side break. Directional `invalidated` semantics are unchanged.
2. `expiryGraceBars`/`expiryMinPoints` are consulted only by `emitPattern`; detectors in Tasks 4–5 must keep passing their effective `maxBars` on the spec. `config` is read again, so `noUnusedParameters` stays satisfied.
3. The early-drop guard is still asymmetric (grace applies only to sub-`expiryMinPoints` formations) — unchanged from the brief and now named rather than literal.
4. This report itself remains uncommitted, as before.

