# Task B1 report — Shell skeleton and store panel state

**Status:** complete (local only, no push)
**Commit:** `da0f42e19941a47ceaad2c42f736c2d57501ff80`
**Branch:** `integration/4axes-main-2026-11-03`
**Spec:** `docs/superpowers/specs/2026-11-05-technical-workspace-and-scanner-design.md` §3
**Brief:** `.superpowers/sdd/2026-11-05-technical-workspace-phase-b/task-b1-brief.md`

## Files

Create:

- `frontend-v2/src/features/technical/ui/workspace/WorkspaceShell.tsx` — grid contract `40px minmax(0,1fr) 280px` / `56px minmax(0,1fr) auto` / areas `topbar topbar topbar` / `activity chart rail` / `feed feed feed`; chart stage keeps `DrawingToolbar` + `ForecastControls` + `KLineChartWrapper`.
- `frontend-v2/src/features/technical/ui/workspace/WorkspaceTopbar.tsx` — symbol (store + hash), `TIMEFRAME_OPTIONS`, `adjustmentMode`, chart-type slot; 56px; Persian labels, `text-xs` (12px) minimum.
- `frontend-v2/src/features/technical/ui/workspace/ActivityBar.tsx` — 40px rail, four buttons `activity-panel-{events|top50|indicators|edge}`, SVG icons from `@app/shell/icons`; sets `activePanel`, opens/collapses the feed, and keeps `activeDrawerTab` in sync temporarily.
- `frontend-v2/src/features/technical/ui/workspace/InspectorRail.tsx` — 280px placeholder with `data-testid="workspace-rail"`; B3 moves layers/active-event card here.
- `frontend-v2/src/features/technical/ui/workspace/EventFeed.tsx` — collapsible feed with `data-testid="workspace-feed"`; hosts `WideWorkspaceDrawer` behind the temporary flag.
- `frontend-v2/src/features/technical/ui/workspace/__tests__/WorkspaceShell.test.tsx` — the brief's two specs, heavy children/queries/board mocked as in the existing workspace tests.

Modify:

- `frontend-v2/src/features/technical/ui/TechnicalWorkspace.tsx` — keeps query/effects/root `technical-workspace`; renders `WorkspaceShell` instead of the old flex layout. `DrawingToolbar`, `ForecastControls`, `KLineChartWrapper` imports moved into the shell.
- `frontend-v2/src/features/technical/model/types.ts` — `WorkspacePanel`, `TechnicalState.activePanel`, `toggleFeed`, `setActivePanel`.
- `frontend-v2/src/features/technical/model/technicalStore.ts` — `activePanel: 'events'` initial, `setActivePanel`, `toggleFeed` delegating to `toggleLeftDrawer` (R-PB-1), and read-through alias exports `selectFeedOpen` / `useFeedOpen` (no second flag).

## Red

First run (test file written before implementation, wrong relative store path in the test itself):

```
FAIL  src/features/technical/ui/workspace/__tests__/WorkspaceShell.test.tsx
Error: Failed to resolve import "../../model/technicalStore" ... Does the file exist?
Test Files  1 failed (1)
Tests  no tests
```

Fixed the test import to `../../../model/technicalStore`, re-ran before implementing (the intended red):

```
FAIL  src/features/technical/ui/workspace/__tests__/WorkspaceShell.test.tsx
 ❯ src/features/technical/ui/workspace/__tests__/WorkspaceShell.test.tsx:76:28
    expect(screen.getByTestId('workspace-topbar')).toBeTruthy();  // unable to find workspace-topbar
 ❯ src/features/technical/ui/workspace/__tests__/WorkspaceShell.test.tsx:82:28
    fireEvent.click(screen.getByTestId('activity-panel-top50'));  // unable to find activity-panel-top50
Test Files  1 failed (1)
Tests  2 failed (2)
```

Both brief specs were present verbatim; failure was the missing shell/store, as required.

## Green

```
npx vitest run src/features/technical/ui/workspace/__tests__/WorkspaceShell.test.tsx
✓ 2 tests passed

npx vitest run src/features/technical/ui/__tests__/TechnicalWorkspace.test.tsx
✓ 4 tests passed   (existing drawer open/close titles still honored)

npx vitest run src/features/technical
Test Files  37 passed (37)
Tests       349 passed (349)

npx vitest run
Test Files  88 passed (88)
Tests       746 passed (746)   (baseline 744 + 2 new)

npx tsc --noEmit
exit 0
```

## Intentionally temporary (this task only)

1. **`TEMP_HOST_LEGACY_DRAWER_IN_FEED = true`** in `EventFeed` — while the feed is open, the full `WideWorkspaceDrawer` (all four tabs, portal, edge card) is mounted inside the feed body. B2/B3 move the panels and remove the flag.
2. **Old drawer toggle title** — the feed's closed-state toggle keeps `title="باز کردن سایدبار لبه آماری"` so the existing `TechnicalWorkspace` and drawer behaviors stay green; the open-state feed button uses a feed-specific title to avoid duplicate titles with the drawer.
3. **`InspectorRail` is a placeholder** — active event card, layer switches and rules stay in the drawer (reachable through the feed) until B3.
4. **Topbar duplicates symbol/timeframe/adjustment** that `ForecastControls` also renders; `ForecastControls` must stay mounted per controller ruling, so both exist for now.
5. **Chart type is a static chip** — `KLineChartWrapper` is candle-only today; the topbar reserves the §3 slot without inventing store state.
6. **ActivityBar ↔ drawer cross-wiring** — clicking a panel also sets `activeDrawerTab` (`events` → `scanner`) so the temporary drawer follows the activity rail; removed when the drawer retires (B4).
7. **Fixed 320px feed body** and drawer absolute positioning inside it; responsive polish is B5.
8. **Grid root is `dir="ltr"` with RTL regions** so the §3 literal areas render activity-left / chart-center / rail-right; `technical-workspace` root stays RTL.

## Residual risks

1. **"Drawer stays mounted" is satisfied as reachable, not always-in-DOM**: the drawer mounts only while `feedOpen`; the existing close test requires it to unmount (`queryByTestId('candle-edge-card')` null). If a later task expects the drawer permanently mounted, that conflicts with current test contracts.
2. **`feedOpen` is an alias by selector, not a state key**: `useFeedOpen` / `selectFeedOpen` read `isLeftDrawerOpen`; `toggleFeed` calls `toggleLeftDrawer`. B3/B4 must consume these exports and never add a second boolean (R-PB-1).
3. **ActivityBar mutates `activeDrawerTab`** as a temporary bridge; B4 must delete that mapping when the drawer is removed.
4. **Chart-type control is display-only**; if the topbar is expected to switch chart types before B5, a store field + `KLineChartWrapper` wiring are still missing.
5. **Feed height is fixed (320px)**; on short viewports the chart shrinks below the 60% width target only in width terms (width is unaffected), but vertical squeeze and overflow are untested until live acceptance in B5.
6. **No live/browser acceptance in B1** — no screenshots at 1366×768 / 1920×1080; B5 owns that gate.
7. **`useFeedOpen` has no in-tree consumer yet** (public API for B3/B4); typecheck cannot prove the future contract.
8. **Grid contract lives in inline styles + exported string constants**; B5 visual tests should read computed style, not class names.

## Fix round 1 — review R-PB-4 / R-PB-5 + minors

**Status:** complete (local only, no push)
**Commit:** `831a15c6c12c0ac20366e3c0047831a523701750`
**Branch:** `integration/4axes-main-2026-11-03`
**Scope:** `frontend-v2` only. Rulings: `.superpowers/sdd/2026-11-05-technical-workspace-phase-b/progress.md` (R-PB-4, R-PB-5).

### R-PB-4 — activity bar is the spec §3 rail, not feed tabs

- `ActivityBar` now lists exactly `chart | scanner | indicators | settings` with Persian labels (چارت/اسکنر/اندیکاتورها/تنظیمات), testids `activity-section-*`. The old `activity-panel-*` feed-tab ids are gone; feed tabs live only in `EventFeed`.
- Behavior: `chart` collapses the open feed; `scanner` opens the feed on the events panel (`activePanel=events`, `activeDrawerTab=scanner`); `indicators` opens it on the indicators panel; `settings` keeps the feed as-is and switches `InspectorRail` to the settings view.
- `settings`: no technical settings drawer/portal exists in the repo (`FtsSettingsDrawer` is the fundamental feature and out of scope), so per the review note this is a rail tab showing the settings content. It introduces **no new store field or input** — it surfaces the toggles the chart/toolbar already consume (`isLogScale`, `isAutoScale`, `isMagnetMode`, lock/hide drawings, corporate events, SMC zones, prediction cone).
- New store: `activeSection: WorkspaceSection` + `setActiveSection` (`WorkspaceSection = 'chart' | 'scanner' | 'indicators' | 'settings'`). SVG icons still come from `@app/shell/icons` (added the missing `sliders` glyph); 12px text floor kept.
- Test: section ids render, `aria-current` (not `aria-pressed`) marks the active section; scanner/indicators open the matching panel; chart closes the feed; settings shows `workspace-settings-panel` and clicking `settings-toggle-log-scale` flips `isLogScale`.

### R-PB-5 — label/content sync

- The feed owns its tab strip: `feed-tab-events|top50|indicators|edge` = رویدادها | ۵۰ نماد | اندیکاتورها | لبه آماری. Every click writes `activePanel` **and** `activeDrawerTab` atomically (`ui/workspace/panelMapping.ts` is the single panel↔tab↔label map).
- `WideWorkspaceDrawer` gained an optional controlled mode (`activeTab`, `onTabChange`, `hideTabs`; defaults unchanged). The feed passes `activeTab={DRAWER_TAB_BY_PANEL[activePanel]}` so the hosted panel is derived from the same state as the selected tab and `workspace-feed-active-panel` label — they cannot diverge. The drawer's legacy internal strip is hidden only while hosted (`hideTabs`); direct drawer tests keep the old strip.
- Test: open via `activity-section-scanner` → `scanner-panel` (events panel today) renders and label is «رویدادها»; click `feed-tab-top50` → `top50-panel` renders, `scanner-panel` is gone, label is «۵۰ نماد», and store is `activePanel=top50` / `activeDrawerTab=top50`.

### Minors

- `aria-controls="workspace-feed-body"` now always resolves: the body stays mounted and toggles with `hidden`; drawer content still unmounts when closed (existing close test unchanged).
- Active section uses `aria-current="true"`; `aria-pressed` removed from the rail.
- 320px feed body documented in code (`h-80`, B1 acceptance size; responsiveness deferred to B5).
- 4px scale: `gap-1.5 → gap-2`, `px-2.5 → px-2`, `h-7 → h-8`; the two topbar `p-1` groups grew `h-9 → h-10` so the 32px controls fit without overflow (no off-scale utilities remain in `ui/workspace`).

### Red → green

Red, new specs against the old shell:

```
FAIL src/features/technical/ui/workspace/__tests__/WorkspaceShell.test.tsx
  Unable to find an element by: [data-testid="activity-section-chart"]
  ...
 Test Files  1 failed | 1 passed (2)
      Tests  6 failed | 5 passed (11)
```

Green:

```
npx tsc --noEmit; echo "tsc exit=$?"
tsc exit=0

npx vitest run src/features/technical/ui/workspace src/features/technical/ui/__tests__/TechnicalWorkspace.test.tsx
 ✓ src/features/technical/ui/__tests__/TechnicalWorkspace.test.tsx (4 tests) 814ms
 ✓ src/features/technical/ui/workspace/__tests__/WorkspaceShell.test.tsx (7 tests) 851ms
 Test Files  2 passed (2)
      Tests  11 passed (11)

npx vitest run src/features/technical
 Test Files  37 passed (37)
      Tests  354 passed (354)

npx vitest run
 Test Files  88 passed (88)
      Tests  751 passed (751)   (baseline 746 + 5 net new)
```

### Residual notes (fix round)

1. **Feed strip vs drawer strip**: both existed after the fix; the drawer's internal strip is hidden while hosted (`hideTabs`) to avoid two competing tab UIs. B4 deletes the drawer and the prop.
2. **`activeSection` ≠ `activePanel`**: `top50`/`edge` are feed tabs and intentionally have no activity section; opening the feed via its own toggle does not change the rail's section, only the rendered panel.
3. **`settings` is a rail view, not a modal**: if a technical settings drawer/portal appears later, the `settings` branch in `ActivityBar` is the single place to switch to it.
4. **Events panel is the drawer's scanner tab today**: B2/B3 replace it with the real feed panels; the mapping in `panelMapping.ts` is the seam.

