# Task B4 report — retire the wide drawer, keep the pop-out

**Status:** complete (local only, no push)
**SHA:** `444d96cafa7228b056974aaa58741d91a9077d32`
**Branch:** `integration/4axes-main-2026-11-03`
**Parent:** `c2a13c1046a16d9160135b558687235067ad1319`
**Brief:** `.superpowers/sdd/2026-11-05-technical-workspace-phase-b/task-b4-brief.md`

## Task B4

### Files

Removed:

- `frontend-v2/src/features/technical/ui/WideWorkspaceDrawer.tsx` (444 lines) — the unreferenced wide drawer: its own tab strip, activity rail, resizer and portal host.
- `frontend-v2/src/features/technical/ui/__tests__/WideWorkspaceDrawer.test.tsx` (270 lines, 15 tests) — tests for the removed component; the parts that still matter (panel hosting, portal, collapse) now live in `EventFeed.test.tsx` / `WorkspaceShell.test.tsx` against the real shell.

Added: none.

Modified:

- `frontend-v2/src/features/technical/ui/workspace/EventFeed.tsx` — the drawer's `portal-modal-btn` and floating window were ported into the feed header. The portal renders the currently selected panel (all four, via one shared `renderPanel` used by feed body and portal), closes via its «✕ بستن» button (`portal-modal-close`) or Escape, focuses the close button on open and returns focus to the trigger on close. Collapse still only hides the body (`hidden`), so header, toggle and portal trigger stay usable. No legacy drawer markup/testids returned.
- `frontend-v2/src/features/technical/ui/workspace/ActivityBar.tsx` — no longer writes `activeDrawerTab` when opening a feed panel.
- `frontend-v2/src/features/technical/ui/workspace/panelMapping.ts` — only `PANEL_LABELS` remains.
- `frontend-v2/src/features/technical/model/types.ts` — removed `DrawerTab`, `activeDrawerTab`, `setActiveDrawerTab`, `leftDrawerWidth`, `setLeftDrawerWidth`; stale «سایدبار عریض» comments updated.
- `frontend-v2/src/features/technical/model/technicalStore.ts` — removed the same initial state and actions; `DrawerTab` import dropped.
- `frontend-v2/src/features/technical/ui/TechnicalWorkspace.tsx`, `ui/workspace/WorkspaceShell.tsx` — stale drawer-era header comments updated only.
- `frontend-v2/src/features/technical/ui/workspace/__tests__/EventFeed.test.tsx` — +7 cases: portal renders each of the four selected panels, close button, Escape, and collapse keeps the header toggle usable; stale `activeDrawerTab` assertion removed.
- `frontend-v2/src/features/technical/ui/workspace/__tests__/WorkspaceShell.test.tsx` — +3 cases: no legacy drawer testids, feed-header portal opens with the selected panel and Escape closes it, collapse hides the panel while activity bar + header toggle remain; two stale `activeDrawerTab` assertions removed.
- `frontend-v2/src/features/technical/model/__tests__/technicalStore.test.ts` — dropped drawer-width/tab assertions, kept channel/RSI/feed-flag coverage.

### Removal list (grep-first, nothing else read them)

1. `ui/WideWorkspaceDrawer.tsx` — deleted (only its own test imported it).
2. `ui/__tests__/WideWorkspaceDrawer.test.tsx` — deleted with the component.
3. `PANEL_BY_DRAWER_TAB` from `workspace/panelMapping.ts` — no readers (grep).
4. `DRAWER_TAB_BY_PANEL` from `workspace/panelMapping.ts` — only fed the now-deleted `activeDrawerTab` writes in `EventFeed`/`ActivityBar`.
5. `DrawerTab` type from `model/types.ts` — no readers after items 3–4.
6. `activeDrawerTab` state field (types + store `INITIAL_STATE`) — after the drawer died, only tests read it; writers in `EventFeed`/`ActivityBar` removed.
7. `setActiveDrawerTab` action (types + store) — same as item 6.
8. `leftDrawerWidth` state field + `setLeftDrawerWidth` action (types + store) — the resizer in the deleted drawer was the only reader (grep: store/tests only). Removed as dead drawer state; noted because the brief named only the tab fields.
9. Stale drawer-era comments in `TechnicalWorkspace.tsx` / `WorkspaceShell.tsx` / `panelMapping.ts`.

Retained intentionally: `isLeftDrawerOpen` / `setIsLeftDrawerOpen` / `toggleLeftDrawer` / `toggleFeed` — this flag is the feed's collapse state by R-PB-1 (renaming it is out of scope).

### Red (before implementation)

`cd frontend-v2 && npx vitest run src/features/technical/ui/workspace/__tests__ --reporter=dot`:

```
FAIL  EventFeed portal pop-out (B4) > renders the selected events panel inside the floating portal
FAIL  EventFeed portal pop-out (B4) > renders the selected top50 panel inside the floating portal
FAIL  EventFeed portal pop-out (B4) > renders the selected indicators panel inside the floating portal
FAIL  EventFeed portal pop-out (B4) > renders the selected edge panel inside the floating portal
FAIL  EventFeed portal pop-out (B4) > closes the portal with its close button
FAIL  EventFeed portal pop-out (B4) > closes the portal on Escape
FAIL  WorkspaceShell > feed header pop-out opens the portal with the selected panel and Escape closes it (B4)
 Test Files  2 failed | 2 passed (4)
      Tests  7 failed | 28 passed (35)
```

All seven failed on the missing `portal-modal-btn` (`getByTestId` unable to find); the drawer-gone and collapse guards were already green and remain as regression guards.

### Green (after implementation)

```
cd frontend-v2 && npx tsc --noEmit
exit 0

npx vitest run src/features/technical
 Test Files  39 passed (39)
      Tests  361 passed (361)

npx vitest run
 Test Files  90 passed (90)
      Tests  758 passed (758)

grep -r "WideWorkspaceDrawer\|wide-workspace-drawer\|activeDrawerTab" frontend-v2/src
  → only 3 intentional negative assertions in EventFeed.test.tsx / WorkspaceShell.test.tsx
grep -r "DrawerTab\|leftDrawerWidth\|DRAWER_TAB_BY_PANEL\|PANEL_BY_DRAWER_TAB" frontend-v2/src
  → no matches
```

Count math: baseline 763 − 15 retired drawer tests + 10 new B4 tests = 758.

### Residual risks

1. **Portal duplicates the active panel subtree while open.** The feed body keeps rendering behind the backdrop, so with `activePanel === 'edge'` two `edge-tab-panel` instances exist (one hidden behind the overlay, one in the portal), and `scanner-panel`/`top50-panel` similarly duplicate when their tab is active. Tests scope queries with `within(portal)`; normal UI is unaffected. Avoiding this would require hiding the feed body while the portal is open (not done, to preserve the old drawer behavior).
2. **The floating window is not a full focus trap.** Escape and the close button both close it, the close button is auto-focused, and focus returns to the trigger; tab can still move to controls behind the backdrop (no `inert`/trap), same limitation as the old drawer.
3. **`isLeftDrawerOpen` naming survives.** The feed collapse state still uses the drawer-era store name for compatibility (R-PB-1); only the dead tab/width state was removed.
4. **`leftDrawerWidth` removal went slightly beyond the named list** (brief authorized deleting dead store fields after grep). Nothing outside the deleted drawer and store tests referenced it.
5. **No live/browser acceptance in B4** — evidence is `tsc`, the focused technical suite and the full 758-test suite; no visual check of the floating window at 1366/1920.

## Fix round 1

Follow-up on review of `444d96ca`: restore the interaction coverage lost with the drawer test (R-PB-6), remove the duplicated portal subtree, and pin focus behavior.

### Changes

- `frontend-v2/src/features/technical/ui/panels/__tests__/Top50Panel.test.tsx` (new, 4 tests) — ports the retired drawer cases with the same `useBoard` fixture/QueryClient: search filters rows (`top50-search-input`), category chips filter the list (`category-filter-*`, including empty «حق تقدم»), signal column header + badge from the board row (`top50-signal-*`), and the selected symbol's pullback signal from the store overriding the neutral board signal.
- `frontend-v2/src/features/technical/ui/panels/__tests__/IndicatorsPanel.test.tsx` (new, 4 tests) — same `reset()` + `enableDefaultIndicators()` setup as the drawer test: smart-indicator toggles (`toggle-indicator-*`) and channel-mode buttons (`channel-mode-btn-*`) now assert the selected mode/toggle in `useTechnicalStore` (`channelMode`, `activeUserIndicators`) and the conditional channel UI, not just presence.
- `frontend-v2/src/features/technical/ui/workspace/EventFeed.tsx` — the feed body now renders only when `feedOpen && !isPortalOpen`. Header, tab strip and pop-out trigger stay visible; while the portal is open exactly one panel instance exists in the DOM.
- `frontend-v2/src/features/technical/ui/workspace/__tests__/EventFeed.test.tsx` — portal cases assert `getAllByTestId(panel)` length 1 before/during open and that `workspace-feed-body` does not contain the panel; the tab strip/trigger remain. +3 focus tests: opening focuses `portal-modal-close`; closing via the close button and via Escape returns focus to `portal-modal-btn`.
- `frontend-v2/src/features/technical/ui/workspace/__tests__/WorkspaceShell.test.tsx` — shell-level pop-out case asserts a single `top50-panel` before, during and after the portal.

### Evidence

```
cd frontend-v2
npx tsc --noEmit            → exit 0
npx vitest run src/features/technical
 Test Files  41 passed (41)
      Tests  372 passed (372)      # 361 + 11 new
npx vitest run
 Test Files  92 passed (92)
      Tests  769 passed (769)      # baseline 758 + 11 new
```

### Behavior notes

1. **Body unmounts while the portal is open.** Closing the portal remounts the body panel, so `ScannerFeed`'s family filter and `CandleEdgeCard`'s internal tab reset; `Top50Panel` search/category live in `EventFeed` and survive. This is the deliberate trade-off for guaranteeing one instance (state duplication was the reported bug). If filter persistence across pop-out is wanted, lift those states into `EventFeed`/the store rather than re-mounting.
2. **`edge-tab-panel` leaves the body while the portal is open** (body is null); tests locate it inside the portal. The "edge panel stays mounted hidden while another feed tab is active" behavior is unchanged when the portal is closed.
3. **Focus:** autoFocus on the close button plus synchronous focus return in `closePortal` are now pinned by tests; still no full focus trap (`inert`/Tab cycling), unchanged from B4.
