# Task A5 report — Merge the parallel tab into the scanner feed

**Status:** complete (local only, no push)
**Commit:** `1134d38a` (`1134d38aed75755775f05360e41efb5715c3fe93`, parent `62b65f6f`)
**Branch:** `integration/4axes-main-2026-11-03`

## Files

Added:

- `frontend-v2/src/features/technical/ui/ScannerFeed.tsx` — the merged feed: forming-pattern card, family-filtered pattern list, pullback/CHoCH event rows, rule book.
- `frontend-v2/src/features/technical/ui/__tests__/ScannerFeed.test.tsx` — 13 tests: the brief's two tests verbatim, the eight tests migrated from `PatternsTab.test.tsx`, a UI-side 8-sample gate test, and an event-row content test.

Removed:

- `frontend-v2/src/features/technical/ui/PatternsTab.tsx`
- `frontend-v2/src/features/technical/ui/__tests__/PatternsTab.test.tsx`

Modified:

- `frontend-v2/src/features/technical/ui/WideWorkspaceDrawer.tsx` — `{ id: 'patterns', labelFa: 'الگوها' }` removed from `TABS`; the patterns render block deleted; the scanner tab now renders `<ScannerFeed patterns={detectedPatterns} pullbacks={detectedPullbackSignals} chochs={detectedCHoCHSignals} />` inside `data-testid="scanner-panel"`.
- `frontend-v2/src/features/technical/model/types.ts` — `DrawerTab` is now `'top50' | 'indicators' | 'scanner' | 'edge'`.
- `frontend-v2/src/features/technical/ui/__tests__/WideWorkspaceDrawer.test.tsx` (R-PA-3) — the scanner test now seeds `detectedPatterns` + `detectedPullbackSignals` and asserts `pattern-row-flag-1`, `scanner-event-pullback-1` and `pattern-rules`; the tab-floor loop covers four tabs and asserts `drawer-tab-patterns` is gone.

Staging (R-PA-1): exactly those seven paths were staged explicitly; no `git add -A`. Git recorded the create/delete pairs as renames, which is the same tree content. Unrelated untracked files in the worktree were left untouched and uncommitted.

## Red (before implementation)

Command: `cd frontend-v2 && npx vitest run src/features/technical/ui/__tests__/ScannerFeed.test.tsx`

```
Error: Failed to resolve import "../ScannerFeed" from "src/features/technical/ui/__tests__/ScannerFeed.test.tsx". Does the file exist?
 Plugin: vite:import-analysis
 File: .../frontend-v2/src/features/technical/ui/__tests__/ScannerFeed.test.tsx:13:28
 Test Files  1 failed (1)
      Tests  no tests
```

## Green

```
npx vitest run src/features/technical/ui/__tests__/ScannerFeed.test.tsx \
               src/features/technical/ui/__tests__/WideWorkspaceDrawer.test.tsx
 Test Files  2 passed (2)
      Tests  28 passed (28)

npx vitest run src/features/technical
 Test Files  35 passed (35)
      Tests  341 passed (341)

npx vitest run                (frontend-v2, full suite)
 Test Files  86 passed (86)
      Tests  738 passed (738)   (734 at HEAD 62b65f6f; −9 old PatternsTab tests, +13 ScannerFeed tests)

npx tsc --noEmit
TSC_EXIT=0

grep -r "PatternsTab" frontend-v2/src
(no output; exit 1)
```

## How the pullback/CHoCH rows are sourced

- `WideWorkspaceDrawer` subscribes to `detectedPullbackSignals` and `detectedCHoCHSignals` in the Zustand technical store and passes them to `ScannerFeed` as `pullbacks`/`chochs`, alongside `detectedPatterns`.
- Those two store fields are written by the existing overlay engines in `frontend-v2/src/features/technical/overlays/advancedTradingIndicators.ts`: the SuperTrendPullback overlay calls `setDetectedPullbackSignals(...)` (≈line 431) and the AutoTrendlineCHoCH overlay calls `setDetectedCHoCHSignals(...)` (≈line 671). The feed does not rescan; it renders what the live overlays last confirmed.
- Each row shows kind, direction, bar index and a Jalali month/day from `signal.index` / `signal.timestamp`, and carries `data-testid={`scanner-event-${signal.id}`}`.
- Double-tap shapes are not lost: `detectedPatterns` already contains the `fromDoubleTap` adapters merged by `detectAllPatterns`, so they appear in the card/list. The old scanner's dedicated double-tap card list (fed by `detectedDoubleTapPatterns` from the overlay) is retired from the tab; that field still feeds the top-50 signal column and the activity-bar badge.

## Percentage gate and copy

- The card and every list row compute the percentage through `gatedProbability`: `probability != null && resolved >= PATTERN_CONFIG.formationMinResolved` (8). Below the gate they render «نمونهٔ کافی نیست» / «—», even if a probability leaks through with fewer resolved samples. The gate test pins this behaviour.
- The card keeps the exact copy «کندلِ در حال تشکیل ≠ تأییدشده؛ درصد از تاریخچهٔ همین نماد است، نه پیش‌بینی.» and the testids `pattern-card`, `pattern-row-<id>`, `pattern-list`, `pattern-rules`, plus the new `pattern-tier-2` (card badge «کم‌بسامد») and `scanner-event-<id>`. Tier-2 list rows also show a «کم‌بسامد» chip (no duplicate testid).

## Residual risks

1. **Double-tap detail rows retired.** The old scanner printed neckline, target1/2 and stop for each double tap; the merged feed lists double taps through the generic pattern row (kind, family, status, gated percent) and the chart overlay, so those levels are no longer in the drawer text. A follow-up row-detail could restore them.
2. **Tier-2 kinds still show raw enum names.** `KIND_FA` in `patterns/labels.ts` only covers 17 kinds; diamond/broadening/island/three-peaks fall back to the enum string. `labels.ts` was outside R-PA-1's staged file list, so it was left untouched (the «کم‌بسامد» badge still marks them).
3. **Gate is duplicated in the UI.** The engine already nulls `probability` under 8 resolved samples; the component re-checks `resolved >= formationMinResolved` for defence in depth. If the engine later changes its sample policy, both must move together (the test reads the key from `PATTERN_CONFIG`, no 8 literal in the test).
4. **Event rows carry no price.** Per the brief (kind, direction, index/date) the pullback price/quality and CHoCH level/broken price shown by the old scanner are not repeated in the merged feed; they remain on the chart overlays.
5. **The drawer test no longer exercises `detectedDoubleTapPatterns` rendering** in the scanner panel because that markup was deleted; double-tap detection coverage stays in the engine/overlay tests, and the field is still asserted indirectly through the drawer badge path.
6. **Jalali date uses UTC month/day only**, so the feed is deterministic across machines but a cross-year history could be ambiguous without the year.
