# Task 8 report — store slice and chart overlay

- Worktree: `D:/BorsTerminal-worktrees/4axes-main-integration`
- Branch: `integration/4axes-main-2026-11-03` (local only, no push)
- Base: `9a712a77` (Task 7 HEAD, 624 tests green)
- Commit: `29a34d4f` — `feat(technical): اسلایس استور و رسم الگوها روی چارت`
- Identity: `johnwarchief <johnwarchief@users.noreply.github.com>`
- Committed files (exactly these six):
  - `frontend-v2/src/features/technical/model/types.ts`
  - `frontend-v2/src/features/technical/model/technicalStore.ts`
  - `frontend-v2/src/features/technical/overlays/patternOverlay.ts` (new)
  - `frontend-v2/src/features/technical/ui/KLineChartWrapper.tsx`
  - `frontend-v2/src/features/technical/model/__tests__/patternsStore.test.ts` (new)
  - `frontend-v2/src/features/technical/overlays/__tests__/patternOverlay.test.ts` (new)

The pre-existing unstaged change to `docs/superpowers/plans/2026-11-05-classic-chart-patterns.md` and the untracked plan/audit files were left untouched and uncommitted.

## What landed

- `DrawerTab` gains `'patterns'`.
- Store (R-PAT-3): `detectedPatterns: ChartPattern[]` + `setDetectedPatterns`, and `chartCandles: EngineCandle[]` (default `[]`) + `setChartCandles`. Both type imports are `import type` (`./patterns/types`, `./doubleTapEngine`) so no runtime edge is added and no cycle exists; verified by `tsc -b`.
- `patternOverlay.ts`:
  - `patternFigures(params, patterns)` draws upper/lower boundary lines (forming thicker), optional dashed neckline, and exactly one text label per pattern at the anchor.
  - `selectFeaturedPatterns(patterns, 6)` is the cap — never more than six patterns (controller ruling + brief).
  - Labels use Persian names (`KIND_FA`) and `toFaDigits`; the formation percentage (`تشکیل ۶۲٪`) is rendered only when `status === 'forming'` and `formation.probability != null`; otherwise forming shows `— در حال تشکیل`, confirmed shows the bare name.
  - `registerPatternOverlay()` registers the `ClassicPatterns` template idempotently (same try/register pattern as `doubleTapOverlay.ts`), reading `useTechnicalStore.getState().detectedPatterns` at draw time.
- `KLineChartWrapper.tsx`: `registerPatternOverlay()` called inside `ensureAllOverlaysRegistered()` next to `registerFTSOverlays()`.

## TDD red (verbatim, before implementation)

Focused command:

```
cd frontend-v2 && npx vitest run src/features/technical/model/__tests__/patternsStore.test.ts src/features/technical/overlays/__tests__/patternOverlay.test.ts
```

```
 Test Files  2 failed (2)
      Tests  3 failed (3)
```

Store failures:

```
 FAIL  src/features/technical/model/__tests__/patternsStore.test.ts > patterns store slice > defaults detected patterns and chart candles to empty arrays
AssertionError: expected undefined to deeply equal []

 FAIL  src/features/technical/model/__tests__/patternsStore.test.ts > patterns store slice > stores detected patterns
TypeError: useTechnicalStore.getState(...).setDetectedPatterns is not a function

 FAIL  src/features/technical/model/__tests__/patternsStore.test.ts > patterns store slice > publishes chart candles for the pattern engine
TypeError: useTechnicalStore.getState(...).setChartCandles is not a function
```

Overlay suite failure (missing module, run separately for the verbatim body):

```
 FAIL  src/features/technical/overlays/__tests__/patternOverlay.test.ts [ src/features/technical/overlays/__tests__/patternOverlay.test.ts ]
Error: Failed to resolve import "../patternOverlay" from "src/features/technical/overlays/__tests__/patternOverlay.test.ts". Does the file exist?
```

## Green

```
 ✓ src/features/technical/model/__tests__/patternsStore.test.ts (3 tests) 13ms
 ✓ src/features/technical/overlays/__tests__/patternOverlay.test.ts (7 tests) 20ms

 Test Files  2 passed (2)
      Tests  10 passed (10)
```

Full suite: `81 passed (81)`, `634 passed (634)` (624 pre-existing + 10 new; no regressions).
Typecheck: `npx tsc -b` exit 0 (after one test-only fix below).

Test coverage beyond the brief's two tests: one label per pattern; confirmed pattern omits `٪` even with formation present; forming without `formation` falls back to `در حال تشکیل`; `probability: null` treated as unknown; 10-pattern fixture yields `selectFeaturedPatterns(..., 6).length` labels and ≤ 6; invalidated pattern draws nothing; store defaults `[]` for both slices and round-trips a candle.

## Deviations and notes

- The 10-pattern cap test compares against `selectFeaturedPatterns(patterns, 6).length`; with only two families that selection is at most 4, so the ≤ 6 assertion is a regression guard rather than an exercised 6-boundary.
- `OverlayFigure['attrs']` is typed `unknown` in klinecharts 10.1, so the brief's `String(f.attrs.text)` does not compile. The test uses a local `textOf()` accessor that casts `attrs` to `{ text?: unknown }` — runtime assertion semantics are identical; `tsc -b` is clean.
- Store slices are not cleared in `setSelectedSymbol` (deliberate: lifecycle/publish belongs to Task 10 per R-PAT-3).

## Residual risks

- Nothing creates a `ClassicPatterns` overlay instance on the chart yet; the wrapper only registers the template. Until Task 10 wires create/remove + publishes `detectedPatterns`/`chartCandles`, the overlay renders nothing in the app — expected by the brief, but no live visual acceptance happened for this task.
- If Task 10 forgets to republish/clear on symbol or timeframe change, stale patterns (or stale `chartCandles`) can linger; this task intentionally does not alter `setSelectedSymbol`.
- Label placement (`anchor + 6/-8`) can collide with candles or the double-tap overlay; no collision handling or screenshot evidence.
- Overlay colors are fixed hex constants (mirroring `doubleTapOverlay`), not theme-aware; light-theme contrast is unverified.
- The "six shapes" cap counts featured patterns; total klinecharts figures can reach 6 patterns × up to 3 lines + 1 label each (by design, per brief wording).

## Fix round 1

Commit: `2553769a` — `fix(technical): اصلاح خطوط صفرطول و کنتراست برچسب الگوها`
(only `frontend-v2/src/features/technical/overlays/patternOverlay.ts` and its test; the plan/audit files and this report stay uncommitted, as before).

### 1. Zero-length lines (Important) — fixed

- `pushBoundary()` now skips any boundary whose `from` and `to` agree on **both** index and price. Two real shapes are affected: the `HEAD_SHOULDERS` `upper` line (`top` is the head point repeated twice) and every double-tap boundary (`fromDoubleTap` emits `from === to` for both `upper` and `lower`).
- The dashed neckline is skipped when its `from`/`to` equal the upper or lower boundary endpoints. In the current detectors `neckline` is the very same `neck` object as `lower` (H&S, triple top) or `upper` (inverse H&S), so the dashed duplicate no longer draws; a genuinely distinct neckline still renders dashed.
- Tests: H&S fixture (zero-length upper + neckline identical to lower) → exactly 1 solid line; double-tap fixture → 0 lines + 1 label; distinct-neckline fixture → 3 lines, exactly 1 dashed.

### 2. Label contrast (Important) — fixed

Label color is resolved per draw from `useUiStore.getState().theme` exactly like `smcOverlays.getIsLight()` (`warm`/`cool` = light, safe fallback = dark) — no new store. Boundary line colors are unchanged; only the text palette is theme-aware. Measured WCAG ratios against each theme's `--panel` token (`src/app/styles.css`):

| Label | Theme / panel | Ratio |
|---|---|---|
| bullish `#7fc4a0` | brass `#15181c` | 8.74:1 |
| bullish `#7fc4a0` | terminal `#0a110d` | 9.38:1 |
| bearish `#e79aa7` | brass `#15181c` | 8.12:1 |
| bearish `#e79aa7` | terminal `#0a110d` | 8.72:1 |
| neutral `#d8c98d` | brass `#15181c` | 10.73:1 |
| neutral `#d8c98d` | terminal `#0a110d` | 11.52:1 |
| bullish `#2f6b52` | warm `#fbf9f5` | 5.97:1 |
| bullish `#2f6b52` | cool `#fafcfd` | 6.10:1 |
| bearish `#8f3f4f` | warm `#fbf9f5` | 6.68:1 |
| bearish `#8f3f4f` | cool `#fafcfd` | 6.82:1 |
| neutral `#6f6132` | warm `#fbf9f5` | 5.82:1 |
| neutral `#6f6132` | cool `#fafcfd` | 5.95:1 |

Minimum across the twelve combinations: **5.82:1** (neutral on warm), i.e. above the 4.5:1 floor in both themes. For reference, the old fixed label colors fail on the light panel: bullish `#4f8f72` 3.63:1, bearish `#b45a6a` 4.33:1, neutral `#a89a6a` 2.66:1. The test recomputes the WCAG ratio from the drawn figure's `styles.color` against the panel tokens for 3 directions × 4 themes and asserts ≥ 4.5.

### 3. Label size and family (Minor) — fixed

`styles: { size: 11, family: 'Vazirmatn, sans-serif' }` (was `size: 10`, `family: 'inherit'`), asserted by test.

### 4. Tests (Minor) — added

- Neckline presence: a pattern with a distinct neckline draws 3 lines with exactly one dashed; the identical-neckline case draws one line only.
- Cap: 7 eligible patterns (mixed family/status, forming + confirmed) yield at most 6 labels. Caveat unchanged from the original report: `selectFeaturedPatterns` picks at most 2 per family, so today's worst case is 4 — the ≤ 6 assertion guards the documented cap.
- Overlay suite grew from 7 to 12 tests; store suite unchanged (3) = 15 focused tests.

### Verification (on the committed state)

```
$ npx tsc --noEmit
tsc exit 0
```

```
 ✓ src/features/technical/model/__tests__/patternsStore.test.ts (3 tests) 18ms
 ✓ src/features/technical/overlays/__tests__/patternOverlay.test.ts (12 tests) 33ms

 Test Files  2 passed (2)
      Tests  15 passed (15)
```

### Residual notes

- Boundary line colors remain the fixed `KIND_COLOR` palette; only label text became theme-aware (the finding was scoped to label contrast). Lines remain an unverified 3:1 non-text contrast on light panels.
- Contrast is computed against the panel tokens, not sampled from live pixels; no screenshot acceptance was done in this round.
- Because real H&S/triple necklines are endpoint-identical to a boundary, the dashed neckline will not appear for those shapes — that is the intended consequence of finding 1, not a regression.
