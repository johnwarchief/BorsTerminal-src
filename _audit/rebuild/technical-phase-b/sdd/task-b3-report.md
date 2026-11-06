# Task B3 report — feed hosts the panels; active event card moves to the rail

**Status:** complete (local only, no push)
**SHA:** `c2a13c1046a16d9160135b558687235067ad1319`
**Branch:** `integration/4axes-main-2026-11-03`
**Parent:** `a912d26d5fde4e1bf06338189bd4f367b6635d55`
**Brief:** `.superpowers/sdd/2026-11-05-technical-workspace-phase-b/task-b3-brief.md`

## Task B3

### Files

Create:

- `frontend-v2/src/features/technical/ui/workspace/ActiveEventCard.tsx` (79 lines) — the card section moved out of `ScannerFeed` with unchanged copy and testids (`pattern-card`, `pattern-quality`, `pattern-tier-2`), the shared `showPercent` / `PATTERN_CONFIG.formationMinResolved` gate, quality, target/stop, 1/3/5-bar returns, the «کندلِ در حال تشکیل ≠ تأییدشده» line and the empty state «الگوی در حال تشکیل نیست». Props `{ pattern?: ChartPattern }`.
- `frontend-v2/src/features/technical/model/patterns/format.ts` (30 lines) — `faPct` / `faNum` / `faDate` lifted verbatim from `ScannerFeed` so the card and the feed share one formatting source (not in the brief's file list; added to avoid duplicating the moved card's formatting).
- `frontend-v2/src/features/technical/ui/workspace/__tests__/ActiveEventCard.test.tsx` (129 lines) — all card cases moved from `ScannerFeed.test.tsx`, plus returns/caveat and empty-state cases.
- `frontend-v2/src/features/technical/ui/workspace/__tests__/InspectorRail.test.tsx` (85 lines) — store-driven card: latest `forming` anchor wins, percent/quality/levels/«کم‌بسامد» rendered, card precedes the layers section, empty state.
- `frontend-v2/src/features/technical/ui/workspace/__tests__/EventFeed.test.tsx` (95 lines) — events tab hosts `ScannerFeed` (no card), top50 tab hosts `Top50Panel`, edge tab toggles `EdgePanel`, and only the feed tab strip exists.

Modify:

- `frontend-v2/src/features/technical/ui/ScannerFeed.tsx` (229 → 156 lines) — card JSX, `lastForming`/`estimate`/`gated`, `DIRECTION_FA` and local formatters removed; list + scanner events + rules remain.
- `frontend-v2/src/features/technical/ui/workspace/EventFeed.tsx` (151 → 185 lines) — hosts panels per `activePanel` (`events` → `ScannerFeed` inside the `scanner-panel` container, `top50` → `Top50Panel`, `indicators` → `IndicatorsPanel`, `edge` → `EdgePanel`); the temporary `TEMP_HOST_LEGACY_DRAWER_IN_FEED` hosting and drawer-tab bridge are gone; `activePanel`/`activeDrawerTab` stay in sync (R-PB-5); top50 search/category state lives here and survives tab switches.
- `frontend-v2/src/features/technical/ui/workspace/InspectorRail.tsx` (165 lines) — reads `detectedPatterns`, picks the newest `forming` pattern, renders `<ActiveEventCard pattern={lastForming} />` above the layers placeholder; stale B1/B3 placeholder copy removed.
- `frontend-v2/src/features/technical/ui/__tests__/ScannerFeed.test.tsx` — card cases moved; list/rules/events cases kept; tier-2 is asserted on the list row; explicit no-card assertions.
- `frontend-v2/src/features/technical/ui/__tests__/TechnicalWorkspace.test.tsx` — drawer-close-title assertion re-expressed against `workspace-feed-toggle` and the feed body's `hidden` state; edge panel mount/unmount coverage kept.
- `frontend-v2/src/features/technical/ui/workspace/__tests__/WorkspaceShell.test.tsx` — full-shell test: exactly one `pattern-card`, inside `workspace-rail`, none in `workspace-feed`, including after a feed-tab switch.

`model/technicalStore.ts` needed no change: `activePanel` / `setActivePanel` / `detectedPatterns` already existed; `activeDrawerTab` is still written by the feed tabs for R-PB-5 compatibility.

### Red (before implementation)

`npx vitest run src/features/technical/ui/__tests__/ScannerFeed.test.tsx src/features/technical/ui/workspace/__tests__ --reporter=dot`:

```
FAIL  src/features/technical/ui/workspace/__tests__/ActiveEventCard.test.tsx (module not yet created)
FAIL  ScannerFeed > badges tier-2 patterns in the list and leaves the active card to the rail
FAIL  ScannerFeed > renders no active event card even when a formation estimate exists
FAIL  EventFeed panel hosting > renders the scanner list in the events tab and no active event card
FAIL  InspectorRail active event card > shows the last forming pattern with percent, quality and measured levels
FAIL  InspectorRail active event card > renders the card above the layers section
FAIL  InspectorRail active event card > keeps the card empty when no pattern is forming
FAIL  WorkspaceShell > renders exactly one active event card, inside the rail (B3)
 Test Files  5 failed (5)
      Tests  7 failed | 20 passed (27)
```

### Green (after implementation)

```
cd frontend-v2 && npx tsc --noEmit
exit 0

npx vitest run src/features/technical
 Test Files  40 passed (40)
      Tests  366 passed (366)

npx vitest run
 Test Files  91 passed (91)
      Tests  763 passed (763)
```

Baseline was 751 tests; net +12: `ScannerFeed.test.tsx` went 17 → 11 (7 card cases moved out, one explicit no-card case added), `ActiveEventCard.test.tsx` adds 10 (7 moved + returns/caveat, tier-2 and empty-state), plus 3 rail + 4 feed + 1 shell tests. No assertion was weakened.

### Residual risks

1. **`WideWorkspaceDrawer` is now unreferenced by the shell.** The brief said to keep the drawer out of this task, so the component and its 15 tests remain; it still renders its own tab strip and the card-free `ScannerFeed`. Until a retirement task deletes it, a future mount would resurrect the old tab UI.
2. **Layer toggles are still a placeholder in the rail.** The card sits above the «لایه‌ها و قواعد» box, but the actual layer switches/rules button from §3 are not implemented in B3 (they were already placeholders in B1).
3. **`EdgePanel` stays mounted whenever the feed body is open** (hidden on non-edge tabs), preserving the pre-B3 drawer behavior and the system tests; `CandleEdgeCard` therefore renders even when the edge tab is not selected.
4. **Two sources of navigation logic for now:** `Top50Panel`'s `onSelect` handling (store write + hash) is copied from the still-existing drawer into `EventFeed`; if the drawer is retired this becomes single-source.
5. **`faNum`/`faPct` moved to `model/patterns/format.ts`** (a file outside the brief's list) instead of being duplicated; behavior is byte-for-byte the same (including trailing-zero trimming).
6. **No live/browser acceptance in B3** — evidence is `tsc`, focused technical suite and the full 763-test suite; no visual check of the rail/feed at 1366/1920 was performed in this task.
