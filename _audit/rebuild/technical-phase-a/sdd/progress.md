# SDD ledger — plan: docs/superpowers/plans/2026-11-05-technical-workspace-phase-a.md

Spec: docs/superpowers/specs/2026-11-05-technical-workspace-and-scanner-design.md (binding).
Branch: integration/4axes-main-2026-11-03. Baseline: f3a7c857 (plan), 666 tests / 83 files green.

## Pre-flight scan

| Pair | Producer → Consumer | Finding |
|---|---|---|
| A1 → A2,A3,A4 | config keys, tier field | consistent |
| A2,A3 → A4 | detectCupRounding/detectTier2 → registry | consistent; A4 registers both |
| A3 → A4 | island single-point anchor | emitPattern may reject <5 points — A4 may extend it; no other rule relaxed |
| A4 → A5 | tier on ChartPattern | consistent |
| A5 → A6 | scanner feed | sequential; A6 captures the merged UI |
| A5 | deletes PatternsTab, changes DrawerTab | existing drawer test may pin the removed tab — in scope for A5 |

Per-task self-consistency:
- A1 rulebook must list 26 kinds (19 tier-1 + 7 tier-2); the plan's earlier "22" is corrected in the spec.
- A5's commit command uses `git add -A` — replaced by explicit staging (R-PA-1).
- A4's negative-fixture helpers are named but not body-specified — disclosed in the plan's self-review.

## Rulings

Ruling: R-PA-1 — A5 stages explicit files (`ScannerFeed.tsx`, its test, `WideWorkspaceDrawer.tsx`, `model/types.ts`, the deleted `PatternsTab*`), never `git add -A`. Cost if wrong: one stale untracked file.
Ruling: R-PA-2 — `emitPattern` may accept a single-point anchor for ISLAND_REVERSAL only if the runtime rejects it; all existing pattern/double-tap tests must stay green. Cost if wrong: an island pattern not emitted.
Ruling: R-PA-3 — updating `WideWorkspaceDrawer.test.tsx` (removed tab, five tabs) is part of A5, not a separate task. Cost if wrong: one failing drawer test at A5.
Task A1: review — spec ✅; quality Needs fixes (doc accuracy): rulebook claims a `rising` gate and triangle convergence gates that the code does not implement, island block misclassified, source column cites non-existent detectors. `rounding.curvatureMin` is pinned but A2 must consume it (carry).
Ruling: R-PA-4 — rulebook rows describe only gates that exist or are explicitly marked «برنامهریزیشده در A2/A3»; the three-peaks `rising` flag is quality-only, not a gate.
Task A1: fix round 1/5 (5 addressed, 0 open; commits 6c94099a..d5dbfaa5)
Task A1: complete (commits f3a7c857..d5dbfaa5, review clean)
Ruling: R-PA-5 — A2 must consume `rounding.curvatureMin` as a real gate (curvature fit ≥ the threshold), not just render it.
Ruling: R-PA-6 — no literal thresholds in the new detectors: A2 adds `cup.minDepthAtr: 2`, `rounding.minDepthAtr: 1`; A3 adds `tier2.islandMaxBlockBars: 5`, `tier2.islandMaxBars: 6`; the exact-pin config test grows with each.
Task A2: review — spec ✅; quality Needs fixes: Important-1 cup handle optional (handle-less U emits CUP_HANDLE); Important-2 literal gates (lows-last - atr, 0.5*depth) outside config; Important-3 rounding points fabricated and anchor at n-1 forces `forming` so the breakout never runs. Minors: target equals the rim, handle not bounded by cup.maxBars.
Ruling: R-PA-7 — CUP_HANDLE requires a real handle pivot with depth in (0, handleDepthPct%]; a handle-less U is not emitted.
Ruling: R-PA-8 — rounding anchors on the actual extreme bar and scans for the breakout after it; target = rim ± depth; add `rounding.minBulgeAtr: 1` and `rounding.endSkewPct: 50` to config and the exact pin.
Task A2: fix round 1/5 (5 addressed, 0 open; commits 22d57c21..64ebeea8)
Task A2: complete (commits d5dbfaa5..64ebeea8, review clean)
Task A2: deferred minor: rounding `points` are not chronological (nothing consumes them today; overlay uses anchor/boundaries).
Ruling: R-PA-9 — A3 adds `tier2.islandMaxBlockBars: 5` and `tier2.islandMaxBars: 6` to config (no literals); the three-peaks family assignment stays as planned and the rulebook keeps it AMBIGUOUS.
Task A3: review — spec ✅; quality Needs fixes: Critical bottom diamond/broadening boundaries swapped (lows line above highs line → bullish "confirm" inside the shape, and outcome scores it success, tests lock it); Important ATR finiteness guard; trio span unbounded. Minors: diamond without mid>start accepts a monotone wedge; island exit gap measured against the entry candle instead of the running block.
Ruling: R-PA-10 — for bottom shapes upper = highs line and lower = lows line (mirror cup); test must assert `forming` until a close above the highs line.
Ruling: R-PA-11 — `Number.isFinite(atr)` guard; three-peaks trio span ≤ hs.maxBars with the recency prefilter; diamond requires mid > start; island exit gap uses the running block min/max.
Task A3: fix round 1/5 (5 addressed, 0 open; commits 74ebc350..e7562c3a)
Task A3: complete (commits 64ebeea8..e7562c3a, review clean)
Task A3: deferred minor: trio recency uses hs.maxBars (equal to triple.maxBars today); island geometry still includes the exit bar in the block.
Ruling: R-PA-12 — diamond gate stays `midSpan > start width` (the literal `mid > start` is unreachable because line width is affine/convex); reviewer confirmed sound.
Task A4: review — spec ❌ (6/7 tier-2 kinds reachable: THREE_FALLING_PEAKS is dropped by R-PAT-6 in favour of TRIPLE_BOTTOM); Important: no-look-ahead test is vacuous (single event, no non-vacuity, one cut) and negative fixtures only catch sign inversion for diamond/broadening/island.
Ruling: R-PA-13 — the three-peaks detector operates on HIGHS only: THREE_RISING_PEAKS = three ascending highs (bearish reversal at a top), THREE_FALLING_PEAKS = three descending highs (bearish continuation). The brief's low-based mapping conflated peaks with valleys and collided with TRIPLE_BOTTOM. Rulebook rows and the registry table are updated accordingly.
Ruling: R-PA-14 — the no-look-ahead test must be non-vacuous (≥1 event), sweep at least four cut points, filter `anchor.index <= cut - pivRight`, and include a pivot within 3 bars of a cut; negative fixtures gain relaxed-key positive controls wherever the rule is expressible.
Task A4: fix round 1/5 (3 of 4 addressed; R-PA-13 still unreachable — 304/304 descending-high shapes are dropped by TRIPLE_TOP because the level-tolerance gate makes a "descending peaks" shape indistinguishable from a triple top).
Ruling: R-PA-15 — redefine the three-peaks gate: strict progression, not level equality. THREE_RISING_PEAKS requires h3 > h2 > h1 and THREE_FALLING_PEAKS requires h3 < h2 < h1, with a minimum total slope of `tier2.threePeaksSlopeAtr: 0.5` and ≥2 tween pivots; the level-tolerance gate stays only for triple tops/bottoms. This separates the tier-2 kinds from the triples and makes both reachable.
Task A4: fix round 2/5 (R-PA-15 applied; both three-peaks kinds reachable; non-vacuous no-look-ahead with tripwire; relaxed-key controls; 734 tests green; commits b8f4932f + 62b65f6f)
Task A4: complete (commits e7562c3a..62b65f6f, re-review clean)
Task A4: deferred minor: `tier2.threePeaksToleranceAtr` is now dead (kept in pin only) — clean up in a later wave.
Task A5: complete (commit 1134d38a; ScannerFeed merged into the scanner tab, PatternsTab deleted, DrawerTab drops 'patterns'; 738 tests green, tsc 0; `grep -r PatternsTab frontend-v2/src` empty).
Task A5: review — spec ✅; quality Needs fixes: Critical geometric quality vanished from the merged feed (spec §2.1/§3 wants win-rate + quality side by side) and 11 kinds render raw enum names in a Persian UI; Important the double-tap neckline/TP/SL text was lost and pullback/CHoCH rows are unbounded/oldest-first; Minors: the 8-sample gate is duplicated in three places, badge counts drift.
Ruling: R-PA-16 — the merge must not drop surfaces: quality (structure 0–100, labelled apart from %) on the card and rows, and target/stop levels on the last-forming card; labels.ts is in scope now for all 26 kinds.
Ruling: R-PA-17 — a single `showPercent(formation, minResolved)` helper decides the percent gate; the feed, card and any overlay use it.
Task A5: fix round 1/5 — the fix agent failed on infra after no edits; the controller executed the six fixes directly (disclosed): quality + target/stop restored, 11 Persian labels, events sorted/capped, single showPercent gate, badge aligned. Commit 5a7ea62e; 742 tests green, tsc clean, build ok.
Task A6: scan-budget test added (500 bars < 50ms, warm run) — 744 tests green; live capture of the merged scanner on فولاد/1D at 1366×768 brass+warm and 1920 (evidence _audit/rebuild/technical-phase-a/2026-11-06/). Live result: 20 pattern rows with Persian names, quality, tier badges; overlay drawn; no forming pattern so the historical % card stayed in its empty state (same disclosed gap as R-PAT-28); one pre-existing 404.
Phase A status: COMPLETE for code/tests/ui-merge; the 15-symbol × 2-timeframe visual audit (acceptance gate) remains open and is the entry check for Phase D.
