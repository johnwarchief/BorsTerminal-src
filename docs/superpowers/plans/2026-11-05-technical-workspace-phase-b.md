# Technical Workspace 2 — Phase B Implementation Plan (TradingView-style shell + unslop)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the technical workspace shell into the approved TradingView-style layout — topbar, activity bar, chart stage, inspector rail, collapsible event feed — re-housing every existing tab without losing a feature, then apply the unslop craft pass to the new chrome.

**Architecture:** A new `ui/workspace/` shell composes existing pieces: `KLineChartWrapper` stays the chart, `DrawingToolbar` and `ForecastControls` keep their places, the wide drawer is decomposed into four panel components that move into the event feed, and the scanner feed gains a split between an active-event card (rail) and the event list (feed). State stays in `technicalStore`; `isLeftDrawerOpen` becomes the feed-open flag so no consumer breaks.

**Tech Stack:** React 18 + TypeScript + Vite, Zustand, Tailwind 4 tokens, Vitest.

**Spec:** `docs/superpowers/specs/2026-11-05-technical-workspace-and-scanner-design.md` (§3 layout, §8 display).

## Global Constraints

- Feature preservation: every tab and action that exists today (۵۰ نماد، اندیکاتورها و کانال، اسکنر، لبه آماری، پاپاوت پورتال، تنظیمات RSI/کانال، درخت لایه‌ها) must remain reachable after the move.
- No data or analysis change: no engine, registry, FTS or scanner logic edits in this phase.
- Unslop rules: 4px grid, 12px minimum text, SVG icons only, nested radii, one accent, no loops/pulses, `prefers-reduced-motion` respected.
- `data-testid` contracts survive: `technical-workspace`, `drawer-tab-scanner` (or its replacement documented), `scanner-panel`, `pattern-card`, `pattern-row-<id>`, `pattern-rules`, `scanner-event-<id>`.
- Layout targets: 1366×768 and 1920×1080, brass and warm; the chart keeps priority (no panel may shrink it below 60% width at 1366).
- Keep `WideWorkspaceDrawer.test.tsx` green until the drawer is removed; then the equivalent feed tests take over.

## File Structure

| File | Responsibility |
|---|---|
| `ui/workspace/WorkspaceShell.tsx` (new) | CSS-grid layout: topbar / activity / chart / rail / feed |
| `ui/workspace/WorkspaceTopbar.tsx` (new) | symbol, timeframe, adjustment, chart type (reads/writes the store) |
| `ui/workspace/ActivityBar.tsx` (new) | 40px icon rail; selects the feed tab and toggles the rail |
| `ui/workspace/InspectorRail.tsx` (new) | 280px: layer toggles + `ActiveEventCard` |
| `ui/workspace/EventFeed.tsx` (new) | collapsible bottom panel with tabs hosting the four panels |
| `ui/workspace/ActiveEventCard.tsx` (new) | extracted from `ScannerFeed`'s card (last forming + percent + quality + levels) |
| `ui/panels/Top50Panel.tsx` (new) | moved from `WideWorkspaceDrawer` (pure move) |
| `ui/panels/IndicatorsPanel.tsx` (new) | moved from `WideWorkspaceDrawer` (pure move) |
| `ui/panels/EdgePanel.tsx` (new) | moved from `WideWorkspaceDrawer` (pure move) |
| `ui/WideWorkspaceDrawer.tsx` (delete after move) | superseded |
| `ui/TechnicalWorkspace.tsx` (modify) | renders `WorkspaceShell` |
| `ui/ScannerFeed.tsx` (modify) | list-only; card extracted to `ActiveEventCard` |
| `model/types.ts` (modify) | `WorkspacePanel = 'events' | 'top50' | 'indicators' | 'edge'` |

---

### Task B1: Shell skeleton and store panel state

**Files:**
- Create: `ui/workspace/WorkspaceShell.tsx`, `ui/workspace/WorkspaceTopbar.tsx`, `ui/workspace/ActivityBar.tsx`, `ui/workspace/InspectorRail.tsx`, `ui/workspace/EventFeed.tsx`
- Modify: `ui/TechnicalWorkspace.tsx`, `model/types.ts`, `model/technicalStore.ts`
- Test: `ui/workspace/__tests__/WorkspaceShell.test.tsx`

**Interfaces:**
- Produces: `WorkspacePanel`, store `activePanel` + `setActivePanel`, `feedOpen` (alias of `isLeftDrawerOpen`) + `toggleFeed`.
- Layout contract (grid): `grid-template-columns: 40px minmax(0,1fr) 280px; grid-template-rows: 56px minmax(0,1fr) auto;` areas `topbar topbar topbar / activity chart rail / feed feed feed`.

- [ ] **Step 1: failing test** — renders the shell with the chart and the three chrome regions:

```tsx
// ui/workspace/__tests__/WorkspaceShell.test.tsx
it('renders topbar, activity bar, chart stage, rail and feed', () => {
  renderShell();
  expect(screen.getByTestId('workspace-topbar')).toBeTruthy();
  expect(screen.getByTestId('workspace-activity')).toBeTruthy();
  expect(screen.getByTestId('kline-chart-wrapper')).toBeTruthy();
  expect(screen.getByTestId('workspace-rail')).toBeTruthy();
  expect(screen.getByTestId('workspace-feed')).toBeTruthy();
});
it('switches the feed panel from the activity bar', () => {
  renderShell();
  fireEvent.click(screen.getByTestId('activity-panel-top50'));
  expect(useTechnicalStore.getState().activePanel).toBe('top50');
});
```
Mock `KLineChartWrapper`, `DrawingToolbar`, `ForecastControls`, the queries, and the board hook as the existing workspace tests do.

- [ ] **Step 2: run** `cd frontend-v2 && npx vitest run src/features/technical/ui/workspace/__tests__/WorkspaceShell.test.tsx` → FAIL (missing modules).

- [ ] **Step 3: implement** — `WorkspaceShell` composes the regions with the grid above; `WorkspaceTopbar` reuses the same store fields the drawer header uses (symbol select, `TIMEFRAMES`, `adjustmentMode`, chart type); `ActivityBar` maps four buttons with `data-testid={'activity-panel-' + id}` and SVG icons from the existing icon set; `InspectorRail` and `EventFeed` render placeholders (`data-testid="workspace-rail"`, `workspace-feed`) plus the current `WideWorkspaceDrawer` content behind a flag for this task only. Add `activePanel`/`setActivePanel` to the store and `WorkspacePanel` to types.

- [ ] **Step 4: run** the new spec + `npx tsc --noEmit` → PASS.

- [ ] **Step 5: commit** `feat(technical): پوسته میزکار تازه با نوار فعالیت و ریل`

---

### Task B2: Move the four panels out of the drawer (pure moves)

**Files:**
- Create: `ui/panels/Top50Panel.tsx`, `ui/panels/IndicatorsPanel.tsx`, `ui/panels/EdgePanel.tsx`
- Modify: `ui/WideWorkspaceDrawer.tsx` (import the moved panels; delete inline markup)
- Test: reuse `WideWorkspaceDrawer.test.tsx` unchanged

**Interfaces:**
- `Top50Panel({ activeSymbol, onSelect })`, `IndicatorsPanel()`, `EdgePanel()`; each renders exactly the markup it rendered inside the drawer (same testids).

- [ ] **Step 1:** copy the JSX blocks from `WideWorkspaceDrawer.tsx` (the blocks under `activeTab === 'top50' | 'indicators' | 'edge'`) into the three components verbatim, lifting only the props they need.
- [ ] **Step 2:** replace the inline blocks with `<Top50Panel activeSymbol={activeSymbol} onSelect={selectSymbol} />`, `<IndicatorsPanel />`, `<EdgePanel />`.
- [ ] **Step 3: run** `npx vitest run src/features/technical/ui/__tests__/WideWorkspaceDrawer.test.tsx` → all existing tests PASS unchanged (this is the proof the move is behavior-preserving).
- [ ] **Step 4: commit** `refactor(technical): استخراج پنل‌های میزکار از کشو`

---

### Task B3: Host the panels in the feed and split the scanner card

**Files:**
- Create: `ui/workspace/ActiveEventCard.tsx`
- Modify: `ui/workspace/EventFeed.tsx`, `ui/ScannerFeed.tsx`, `ui/workspace/InspectorRail.tsx`, `model/technicalStore.ts`
- Test: `ui/workspace/__tests__/EventFeed.test.tsx`, `ui/__tests__/ScannerFeed.test.tsx` (adjust for the split)

**Interfaces:**
- `ActiveEventCard({ pattern })` — the card markup and testids (`pattern-card`, `pattern-quality`, percent gate) move out of `ScannerFeed` unchanged.
- `EventFeed` tabs: `رویدادها | ۵۰ نماد | اندیکاتورها | لبه آماری`, driven by `activePanel`.
- `InspectorRail` renders `<ActiveEventCard pattern={lastForming} />` above the layer toggles.
- `ScannerFeed` becomes list + rules only; `scanner-panel` testid moves to the feed's events tab container.

- [ ] **Step 1:** failing tests — feed shows the scanner list on the events tab; rail shows the card with percent/quality/levels; switching tabs swaps panels; no duplicate `pattern-card` in the DOM.
- [ ] **Step 2: run** → FAIL.
- [ ] **Step 3:** implement the split and the tab host; delete the card from `ScannerFeed`; keep the rules inside the events tab; update `ScannerFeed.test.tsx` to render the list-only component and move card tests to `ActiveEventCard.test.tsx`.
- [ ] **Step 4: run** the three specs + `npx tsc --noEmit` → PASS.
- [ ] **Step 5: commit** `feat(technical): فید رویدادها و کارت رویداد فعال در ریل`

---

### Task B4: Retire the wide drawer and preserve the portal

**Files:**
- Modify: `ui/TechnicalWorkspace.tsx`, `ui/workspace/EventFeed.tsx`, `ui/workspace/WorkspaceShell.tsx`, `model/types.ts` (drop `DrawerTab` if unused), delete `ui/WideWorkspaceDrawer.tsx` + its test
- Test: new `ui/workspace/__tests__/WorkspaceShell.test.tsx` additions

**Interfaces:**
- Feed header keeps the popout button (`data-testid="portal-modal-btn"`) that opens the same portal content (the moved panels) in a floating window; feed collapse uses `feedOpen`.

- [ ] **Step 1:** failing test — the old drawer testids (`wide-workspace-drawer`) are gone; `portal-modal-btn` still opens the portal; collapsing the feed hides the panel but keeps the activity bar.
- [ ] **Step 2: run** → FAIL.
- [ ] **Step 3:** remove the drawer from the shell, delete the component and its test, move the portal trigger into the feed header, and delete dead store fields only if nothing else reads them (grep first; report each).
- [ ] **Step 4: run** `grep -r "WideWorkspaceDrawer\|wide-workspace-drawer" frontend-v2/src` → empty; full technical suite green.
- [ ] **Step 5: commit** `refactor(technical): بازنشستگی کشوی عریض و حفظ پاپ‌اوت`

---

### Task B5: Unslop pass on the new chrome + acceptance

**Files:**
- Modify: `ui/workspace/*`, `app/styles.css` (only workspace-scoped tokens if needed)
- Test: `ui/workspace/__tests__/WorkspaceVisual.test.tsx`

- [ ] **Step 1:** audit the new chrome against the unslop signs (spacing 4px, text ≥ 12px, SVG icons, radii 12/8/4, one accent, no loops). Write the failing test:
  - every workspace chrome text node has `font-size >= 12px`;
  - no `font-extrabold|font-bold` in `ui/workspace/**`;
  - activity buttons and feed tabs have `focus-visible` styles;
  - keyboard: `Tab` reaches the activity bar, feed tabs and rail card.
- [ ] **Step 2:** fix the failures (classes, spacing, icons, focus rings, aria).
- [ ] **Step 3: run** the visual spec + full suite + `npm run build`.
- [ ] **Step 4: live acceptance** — 1366×768 and 1920×1080, brass and warm: screenshot the shell, the open feed on each tab, the rail card, the portal; verify the chart keeps ≥ 60% width at 1366 and no horizontal scrollbar appears; record a feature-preservation checklist (each tab opened, portal opened, drawing toolbar still visible, forecast controls still visible).
- [ ] **Step 5: commit** `feat(technical): پاس unslop و پذیرش بصری میزکار`

---

## Self-Review

**Spec coverage:** layout zones (§3) in B1; feature preservation in B2/B3/B4 (existing tests are the gate); unslop rules and both viewports (§8) in B5; the scanner card split keeps §2.1's dual metric (historical % + geometric quality) in the rail.
**Placeholder scan:** B2 is a pure move whose contract is the unchanged drawer test; B3/B4 carry concrete testids and test intent; B5's audit list is explicit. No TBD.
**Type consistency:** `WorkspacePanel` is introduced in B1 and consumed by the feed in B3; `ActiveEventCard` props match the `ChartPattern` used by `ScannerFeed`; `feedOpen` aliases the existing `isLeftDrawerOpen` so the store keeps one flag.
