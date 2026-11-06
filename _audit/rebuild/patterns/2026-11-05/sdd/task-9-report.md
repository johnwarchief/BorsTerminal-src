# Task 9 report — Patterns tab (card, list, rule book)

- Worktree: `D:/BorsTerminal-worktrees/4axes-main-integration`
- Branch: `integration/4axes-main-2026-11-03` (local only, no push)
- Base: `2553769a` (Task 8 fix HEAD)
- Commit: `c51e8a707e071fea586aa326884ab37155edc97f` — `feat(technical): تب الگوها با کارت، فهرست و قواعد`
- Identity: `johnwarchief <johnwarchief@users.noreply.github.com>`
- Committed files (exactly these three):
  - `frontend-v2/src/features/technical/ui/PatternsTab.tsx` (new)
  - `frontend-v2/src/features/technical/ui/WideWorkspaceDrawer.tsx`
  - `frontend-v2/src/features/technical/ui/__tests__/PatternsTab.test.tsx` (new)

The pre-existing unstaged plan change and untracked audit/plan files were left untouched and uncommitted.

## What landed

- `PatternsTab.tsx`:
  - `pattern-card`: last `forming` pattern by `anchor.index` — Persian kind/status, formation percentage only when `formation.probability != null` (from `formation.probability`, never recomputed from `successes/resolved`), sample count `۱۴ از ۲۳ نمونه`, optional Wilson interval, 1/3/5-candle returns, and the disclosure «کندلِ در حال تشکیل ≠ تأییدشده؛ درصد از تاریخچهٔ همین نماد است، نه پیش‌بینی.»
  - `pattern-list`: rows capped at 20 (newest anchor first) with stable `pattern-row-<id>` testids and a labelled family select («فیلتر خانواده», `all|continuation|reversal`).
  - `pattern-rules`: every displayed number is read from `PATTERN_CONFIG` (no duplicated literals). Covers the brief's keys plus the nine added since: `touchToleranceAtr`, `flag.minLegBars`, `triangle.minSpan`, `expiryGraceBars`, `expiryMinPoints`, `reversal.minSpanBars`, `neutralMinTargetAtr`, `returnsMinSamples`, `overlapWindowBars`.
  - All digits through `toFaDigits`; smallest text is 12px (13px headings, 20px probability); no text under 11px.
- `WideWorkspaceDrawer.tsx` (minimal, 11 insertions / 1 deletion):
  - one import, one store selector (`detectedPatterns`), one `TABS` entry `{ id: 'patterns', labelFa: 'الگوها' }`, one render block before the `edge` panel. No restructuring; `ACTIVITY_TOOLS` untouched.

## TDD red (verbatim, before implementation)

```
$ npx vitest run src/features/technical/ui/__tests__/PatternsTab.test.tsx
 FAIL  src/features/technical/ui/__tests__/PatternsTab.test.tsx [ src/features/technical/ui/__tests__/PatternsTab.test.tsx ]
Error: Failed to resolve import "../PatternsTab" from "src/features/technical/ui/__tests__/PatternsTab.test.tsx". Does the file exist?
...
 Test Files  1 failed (1)
      Tests  no tests
```

Five tests were written first (the brief's four plus one asserting each newly added config key appears in `pattern-rules`); all failed only on the missing module.

## Green

```
 ✓ src/features/technical/ui/__tests__/PatternsTab.test.tsx (5 tests) 172ms

 Test Files  1 passed (1)
      Tests  5 passed (5)
```

- Full suite: `82 passed (82)`, `644 passed (644)` (639 pre-existing + 5 new; no regressions).
- Typecheck: `npx tsc --noEmit` exit 0.
- Not committed: this report and the pre-existing unrelated plan/audit files.

## Deviations and notes

- Local `faNum` trims trailing zeros (`Number(value.toFixed(digits))`) so tolerances render as «۰٫۵»، «۰٫۳۵» instead of «۰٫۵۰»، «۰٫۳۵۰». Same helper serves returns (1 decimal) and integer counts (0 decimals).
- New config keys are grouped into three labelled rule lines rather than a generic config dump; adding a future key still requires one rule line here (deliberate, matching the brief's editorial rule book).

## Residual risks

- **Probability units are inconsistent across the pattern stack.** `model/patterns/formation.ts` fills `formation.probability` from `laplaceRate` (0..1), and `PatternStoryOverlay` (double-tap path) multiplies by 100, but this brief's test/code treats `ChartPattern.formation.probability` as 0..100 (same convention as Task 8's `patternOverlay`, `probability: 62 → ۶۲٪`). The card follows the brief: with real 0..1 data it would show «۱٪» for 0.62 until Task 10 (or a controller ruling) normalizes the pipeline. The Wilson interval in the card is multiplied by 100 per the brief, so with raw engine data probability and interval currently use different scales — a cross-task fix, not changed here.
- A returns row renders even without `returns` (shows «—٪»), per the brief.
- No live acceptance or screenshots; `detectedPatterns` is still only published by tests, so the tab renders the empty card/list until Task 10 wires detection.
- The collapsed activity rail (`ACTIVITY_TOOLS`) has no «الگوها» icon — deliberately not added (brief: one TABS entry + one render block); the tab is reachable from the open drawer's header tabs only.
- `pattern-rules` is a static editorial mirror of `PATTERN_CONFIG`; it cannot go stale in value (read at render) but can go stale in coverage if new keys land without a rule line.

---

## Fix round 1 — R-PAT-24, tab label floor, shared labels, direction

- Worktree: `D:/BorsTerminal-worktrees/4axes-main-integration`
- Branch: `integration/4axes-main-2026-11-03` (local only, no push)
- Base: `c51e8a70` (Task 9 HEAD)
- Commit: `18f4c458b563d49d8e909335575a633248d86542` — `fix(technical): واحد درصد الگوها، برچسب تب ۱۱px و برچسب‌های مشترک`
- Identity: `johnwarchief <johnwarchief@users.noreply.github.com>`
- Committed files (exactly these seven):
  - `frontend-v2/src/features/technical/model/patterns/labels.ts` (new)
  - `frontend-v2/src/features/technical/ui/PatternsTab.tsx`
  - `frontend-v2/src/features/technical/ui/__tests__/PatternsTab.test.tsx`
  - `frontend-v2/src/features/technical/ui/WideWorkspaceDrawer.tsx`
  - `frontend-v2/src/features/technical/ui/__tests__/WideWorkspaceDrawer.test.tsx`
  - `frontend-v2/src/features/technical/overlays/patternOverlay.ts`
  - `frontend-v2/src/features/technical/overlays/__tests__/patternOverlay.test.ts`
- This report stays uncommitted: `.superpowers/sdd/.gitignore` ignores the whole directory (same as round 0).

### Changes

1. **CRITICAL — percentage unit (R-PAT-24).** `FormationEstimate.probability` is a 0..1 rate (`laplaceRate`), and `intervalLow/High` are the same rate (`wilsonInterval`). `faPct` in `PatternsTab.tsx` now takes the rate and multiplies by 100 once; the card headline and the interval call it with the raw values, so 0.62 + [0.48, 0.73] renders «۶۲٪» and «۴۸٪–۷۳٪» — one unit everywhere (list row included). `patternOverlay.ts` multiplies `pct` by 100 before `toFaDigits`. This matches `PatternStoryOverlay`, which already multiplied by 100. Fixtures changed from `probability: 62` to `0.62`; new tests: 0.5 → «۵۰٪» (both files) and direction/interval assertions.
2. **IMPORTANT — tab label size.** The tab-bar button class in `WideWorkspaceDrawer.tsx` changed from `t-95` (9.5px) to `text-[11px]`; one class covers all five tabs. New test asserts `text-[11px]` and no `t-95` on `drawer-tab-{top50,indicators,scanner,patterns,edge}`.
3. **MINOR — shared labels.** `KIND_FA` moved to `model/patterns/labels.ts` (with `DIRECTION_FA`); imported by `PatternsTab.tsx` and `patternOverlay.ts`. No local copies remain.
4. **MINOR — direction on the card.** The card header now shows the Persian direction («صعودی/نزولی/خنثی») next to the kind at 12px; test uses `neutral` → «خنثی» so it cannot pass on the kind label alone.

### TDD red (verbatim, before implementation)

```
 FAIL  .../PatternsTab.test.tsx > renders a 0.5 rate as ۵۰٪, not as ۱٪
Expected: "۵۰٪"  Received: "...۱٪..."
 FAIL  .../PatternsTab.test.tsx > shows the Persian direction next to the kind
 FAIL  .../patternOverlay.test.ts > draws both boundaries and one label for a forming pattern
 FAIL  .../patternOverlay.test.ts > renders a 0.5 formation rate as ۵۰٪
 FAIL  .../WideWorkspaceDrawer.test.tsx > keeps every tab label at the 11px floor

 Test Files  3 failed (3)
      Tests  6 failed | 29 passed (35)
```

(The interval test failed in the same run; tail trimmed to the last failures.)

### Green

```
$ npx vitest run src/features/technical/ui/__tests__/PatternsTab.test.tsx src/features/technical/overlays/__tests__/patternOverlay.test.ts src/features/technical/ui/__tests__/WideWorkspaceDrawer.test.tsx

 ✓ src/features/technical/overlays/__tests__/patternOverlay.test.ts (13 tests) 26ms
 ✓ src/features/technical/ui/__tests__/PatternsTab.test.tsx (7 tests) 283ms
 ✓ src/features/technical/ui/__tests__/WideWorkspaceDrawer.test.tsx (15 tests) 1577ms

 Test Files  3 passed (3)
      Tests  35 passed (35)
```

- Typecheck: `npx tsc --noEmit` exit 0.
- Full suite: `82 passed (82)`, `648 passed (648)` (644 prior + 4 new).

### Residual risks

- The tab badge inside the same tab bar still uses `t-85` (8.5px), and the rest of the drawer still contains `t-8`/`t-85`/`t-9` classes; only the tab label class was in scope. A drawer-wide typography pass is still open.
- `doubleTapOverlay.ts` compares `formation.probability` only for redraw equality — unit-agnostic, so the normalization does not affect it.
- No live acceptance; `detectedPatterns` is still published only by tests until Task 10 wires detection.
