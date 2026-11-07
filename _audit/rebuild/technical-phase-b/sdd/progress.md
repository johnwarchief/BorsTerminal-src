# SDD ledger — plan: docs/superpowers/plans/2026-11-05-technical-workspace-phase-b.md

Spec: docs/superpowers/specs/2026-11-05-technical-workspace-and-scanner-design.md (binding, §3/§8).
Branch: integration/4axes-main-2026-11-03. Baseline: 8981fadb (plan), 744 tests / 87 files green.

## Pre-flight scan

| Pair | Producer → Consumer | Finding |
|---|---|---|
| B1 → B3,B4 | WorkspacePanel + activePanel store | consistent |
| B2 → B3 | Top50Panel/IndicatorsPanel/EdgePanel | B3 hosts them; props fixed in B2 |
| B2,B3 → B4 | drawer deletion | drawer must keep passing tests until B3 lands |
| B3 | splits ScannerFeed's card | existing ScannerFeed tests reference the card — B3 updates them (declared in plan) |
| B4 | deletes WideWorkspaceDrawer + DrawerTab | `DrawerTab` may be used elsewhere — grep before deleting (R-PB-3) |
| B5 | unslop | after the shell is stable |

## Rulings

Ruling: R-PB-1 — `isLeftDrawerOpen` stays the single open/close flag; the feed reuses it (alias `feedOpen`) so no other consumer changes. Cost if wrong: one misleading name.
Ruling: R-PB-2 — the portal/pop-out feature is preserved in the feed header; removing it would be a feature loss against the decisions doc. Cost if wrong: a portal button to re-add.
Ruling: R-PB-3 — B4 deletes `DrawerTab` and any store field only after a repo-wide grep shows no readers; each removal is listed in the report. Cost if wrong: a dangling import caught by tsc.
Task B1: review — spec ✅; quality Needs fixes: Important-1 feed label (activePanel=events) mismatches the hosted drawer tab (activeDrawerTab default top50); Important-2 activity bar implements feed tabs instead of spec §3's chart|scanner|indicators|settings, which would duplicate B3's feed tabs. Minors: aria-controls target unmounted, aria-pressed vs aria-current, fixed 320px undocumented, two off-grid utilities.
Ruling: R-PB-4 — the activity bar follows spec §3 (chart, scanner, indicators, settings); the feed owns its own tab strip (رویدادها/۵۰ نماد/اندیکاتورها/لبه آماری).
Ruling: R-PB-5 — opening the feed or changing the activity section syncs the rendered panel so the label always matches the content.
Task B1: fix round 1/5 (2 of 2 Important addressed, 1 minor partial: some off-grid utilities remain for B5; commits da0f42e1..831a15c6)
Task B1: complete (commits 8981fadb..831a15c6, re-review clean on the Important items)
Task B2: review — spec ✅, quality Approved (pure move proven by the byte-identical drawer test; 751 tests). Minors: useTop50Symbols exported from a panel (shell→content direction), 6 props disclosed, badge fallback test no longer represents prod.
Task B2: complete (commits 831a15c6..a912d26d, review clean)
Task B3: review — spec ✅, quality Approved (card copy byte-identical, exactly one pattern-card, panel prop parity, format.ts clean lift; 763 tests). Minors: 11px/off-grid in card & list (B5), dead PANEL_BY_DRAWER_TAB (B4), missing tab-state-survival and open-title tests, portal unreachable until B4.
Task B3: complete (commits a912d26d..c2a13c10, review clean)
Task B4: review — spec ✅ (drawer deleted, portal moved, collapse keeps header, removals proven dead); quality Needs fixes: Important coverage regression (the deleted drawer test was the only test of top50 search/category/signal and indicator toggles); Minors: duplicated portal subtree (per-instance scanner family/CandleEdge tabs default), focus return untested, literal portal parity claim overstated.
Ruling: R-PB-6 — port the drawer's interaction cases into Top50Panel/IndicatorsPanel tests (or EventFeed with a non-empty board) before B4 is complete; render the feed body only when the portal is closed to avoid duplicate panels/state.
Task B4: fix round 1/5 (3 addressed; commits 444d96ca..fbd6f30e; 769 tests). Residual: Top50 row-click→selectedSymbol untested; pop-out resets ephemeral ScannerFeed family/CandleEdge tab state (accepted trade-off).
Task B4: complete (commits c2a13c10..fbd6f30e, re-review clean)
Task B5: complete (commit 71479436; unslop 12px/4px pass on chrome+feed+panels, responsive rail 240px ≤1440, visual/keyboard contract 8 cases; 777 tests; live Edge 1366/1920 × brass/warm: chart 61.2%/70.3%, no horizontal scroll, census min 12, only the three known chart-analysis 404s).
Task B5: review — spec ✅, quality Approved; verdict SHIP PHASE B. 777 tests, build ok; acceptance: chart 61.2% at 1366 and 70.3% at 1920, no horizontal scroll in 20/20 checks, 12px census 0 offenders, keyboard focus verified, 25 screenshots.
Task B5: complete (commits fbd6f30e..71479436, review clean with follow-ups)
Ruling: R-PB-7 — ForecastControls/DrawingToolbar still carry 8.5–10px pre-existing type; they predate this phase and sit outside the shell/feed/panel census. Queued for the next chart-scale pass rather than silently rewritten now. Cost if wrong: two old panels keep small text.
Ruling: R-PB-8 — the rail collapses to 240px below 1441px to keep the chart at 61.2% at 1366; 280px from 1441 up. This is a deliberate deviation from the spec's fixed 280px, flagged for owner sign-off. Cost if wrong: one width token to change.
Phase B status: COMPLETE (B1–B5) with the two follow-ups deferred; Phase C (channel/pullback/breakout/RSI-divergence events + smart highlight + 200ms entrance) is next and needs its own plan.
