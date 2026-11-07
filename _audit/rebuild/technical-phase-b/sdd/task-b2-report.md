# Task B2 report — Extract the drawer tab panels (pure move)

**Status:** complete (local only, no push)
**Commit:** `a912d26d5fde4e1bf06338189bd4f367b6635d55`
**Branch:** `integration/4axes-main-2026-11-03`
**Parent:** `831a15c6`
**Brief:** `.superpowers/sdd/2026-11-05-technical-workspace-phase-b/task-b2-brief.md`

## Files

Create:

- `frontend-v2/src/features/technical/ui/panels/Top50Panel.tsx` (383 lines) — the whole `top50` tab block verbatim: category chips `category-filter-*`, search box `top50-search-input`, table `top50-row-*` / `top50-signal-*`. Also moves `FALLBACK_TOP_SYMBOLS`, `AssetCategoryFilter`, `ASSET_FILTER_OPTIONS`, `SymbolSignalInfo`, `getSymbolSignal`, and a shared `useTop50Symbols()` hook; reads `detectedDoubleTap/Pullback/CHoCH` and theme from the stores.
- `frontend-v2/src/features/technical/ui/panels/IndicatorsPanel.tsx` (198 lines) — the `indicators` tab block verbatim plus the private `IndicatorRow` helper and the three blocks (advanced registry, user registry, `TelegramCatalogList`), with the same store selectors (`activeUserIndicators`, `toggleUserIndicator`, `channelMode`, `rsiVariant`, `doubleTapProfile`, `indicatorParams.DoubleTap3D.formationHorizon`, `setIndicatorParam`).
- `frontend-v2/src/features/technical/ui/panels/EdgePanel.tsx` (26 lines) — the edge wrapper `edge-tab-panel` that stays mounted and toggles `block p-3` / `hidden`, plus `CandleEdgeCard`.

Modify:

- `frontend-v2/src/features/technical/ui/WideWorkspaceDrawer.tsx` — 962 → 444 lines. Keeps only shell, header, tab strip, activity rail, resize handle, portal and `drawerContent`; the three inline blocks are replaced by `<Top50Panel … />`, `<IndicatorsPanel />`, `<EdgePanel … />`. Dead imports/selectors/helpers removed; no other markup touched.

Diff: 4 files changed, 625 insertions(+), 536 deletions(-).

## What moved and what was lifted

- Markup, copy, testids, class names and ordering are copied verbatim (checked below by normalized comparison against `HEAD~1`).
- `Top50Panel` props: `activeSymbol`, `onSelect` (the drawer's existing `handleSelectSymbol`, i.e. store write + hash navigation), plus `searchQuery` / `onSearchQueryChange` / `selectedCategory` / `onCategoryChange`. The two state values stay in the drawer (per the brief rule "if a block depends on local state in the drawer, pass it as a prop rather than duplicating state") so the search/category survive tab switches and are shared with the portal copy of `drawerContent`, exactly as before.
- `IndicatorsPanel` is prop-less; all toggles come from `useTechnicalStore` inside the panel.
- `EdgePanel` props: `symbol` and `active` (the brief's `EdgePanel()` was schematic; `CandleEdgeCard` needs the symbol, and the hidden/visible wrapper class must stay where the panel is rendered).
- The drawer keeps `useTop50Symbols()` for the two badges (`drawer-tab-top50`, `activity-bar-icon-top50`); the hook and the panel share the same `['board']` query.

## Unchanged-test evidence

The test file was not modified (`git status` shows only the drawer modified and the new `panels/` directory; `git diff HEAD~1 -- …/__tests__/WideWorkspaceDrawer.test.tsx` is empty).

```
npx vitest run src/features/technical/ui/__tests__/WideWorkspaceDrawer.test.tsx
 ✓ src/features/technical/ui/__tests__/WideWorkspaceDrawer.test.tsx (15 tests) 1464ms
 Test Files  1 passed (1)
      Tests  15 passed (15)

npx tsc --noEmit
exit 0

npx vitest run
 Test Files  88 passed (88)
      Tests  751 passed (751)
```

Normalized comparison of the moved JSX against `HEAD~1` (line-trimmed, blank lines dropped) shows only the expected identifier substitutions:

- TOP50: `onClick={() => row.symbol && handleSelectSymbol(row.symbol)}` → `… && onSelect(row.symbol)` (same function passed by the drawer).
- EDGE: `activeTab === 'edge' ? 'block p-3' : 'hidden'` → `active ? …`, and `<CandleEdgeCard symbol={activeSymbol} />` → `symbol={symbol}`.
- INDICATORS: no differences.

## Residual risks

1. **`useBoard` is called twice per render** (drawer badge + `Top50Panel` rows) instead of once. Both use the same TanStack Query key and dedupe to one request. Under a one-shot mock (the existing fallback test uses `mockReturnValueOnce`), the drawer badge computes from the fallback (۵۰) while the panel rows read the second mock return; the unchanged test only asserts the badge, and production reads one cache entry, so behavior is unchanged — but the double invocation is a deliberate trade-off of keeping the brief's `Top50Panel({ activeSymbol, onSelect })` shape while the badge lives in the drawer.
2. **`Top50Panel` has 6 props, not 2**: the extra four carry the drawer's pre-existing search/category state. Had the state moved into the panel, switching tabs (panel unmount) or opening the portal (second panel instance) would silently reset/share filters differently — a behavior change this pass avoided.
3. **If a later task remounts the drawer with a different `activeSymbol`**, `Top50Panel` re-renders identically; no lifecycle-sensitive logic was introduced.
4. **No live/browser acceptance in B2** — behavior preservation is argued from untouched tests, `tsc`, and textual identity of the moved JSX; the task is intentionally a pure move.
5. The report itself is not committed (the task commits only the four code files; `.superpowers/` is untracked/ignored).
