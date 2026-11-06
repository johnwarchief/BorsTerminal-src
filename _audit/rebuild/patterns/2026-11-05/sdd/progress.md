# SDD ledger — plan: docs/superpowers/plans/2026-11-05-classic-chart-patterns.md

Spec: docs/superpowers/specs/2026-11-05-classic-chart-patterns-design.md (read; binding).
Branch: integration/4axes-main-2026-11-03 (isolated worktree, not main).
Baseline at start: 3c9e79c2, full suite 567/567 green (71 files).

## Pre-flight scan (before Task 1)

| Pair | Producer → Consumer | Finding |
|---|---|---|
| T1 → T4,T5 | pivots helpers | consistent names/signatures |
| T2 → T3..T9 | types/config | consistent |
| T3 → T4,T5,T6 | lineValue/emitPattern/toPoint | consistent |
| T4,T5 → T7 | detectContinuation/Reversal(candles, atr, config) | consistent |
| T6 → T7 | outcomeOf(pattern,candles,atr,config,horizon?) | consistent |
| T7 → T8,T10 | detectAllPatterns/selectFeaturedPatterns/fromDoubleTap | consistent |
| T8 → T9 | store detectedPatterns + DrawerTab 'patterns' | consistent |
| T1 vs T7 | both edit doubleTapEngine.ts | sequential; T7 only adds `export` to confidenceFor |
| T8 vs T10 | KLineChartWrapper vs TechnicalWorkspace candle source | GAP: no agreed candle interface |

Per-task self-consistency:
- T3: `emitPattern` drops by the global max window, but its own test expects a 3-bar rectangle to expire → PLAN DEFECT.
- T4/T5: fixtures are shorter than pivLeft+pivRight (5+4), so no pivots can form → PLAN DEFECT in test fixtures.
- T4: `lastIndex` unused → lint defect.
- T7: self-review notes the missing overlap filter but leaves it outside the code block → PLAN DEFECT (code must include it).

## Rulings (before execution)

Ruling: R-PAT-3 — the active candle series is published to the technical store (`chartCandles` slice, set by `KLineChartWrapper` on data change); Task 10 reads that slice instead of re-fetching. Why: one source of truth for the chart and the detectors. Cost if wrong: one extra store field to remove.
Ruling: R-PAT-4 — synthetic fixtures may pass a per-test config with `pivLeft: 1, pivRight: 1`; all geometric thresholds stay at `PATTERN_CONFIG` values and production always uses `PATTERN_CONFIG`. Why: a 12–30 bar fixture cannot contain pivots under a 5/4 confirmation window. Cost if wrong: tests exercise the same geometry with a shorter window; production unaffected.
Ruling: R-PAT-5 — `PatternSpec` gains `maxBars: number` and `emitPattern` uses that per-pattern window (not the global max). Why: the Task 3 test (rectangle maxBars=3) is otherwise unsatisfiable. Cost if wrong: each detector must pass its own window, already required.
Ruling: R-PAT-6 — the reversal-over-continuation overlap filter is part of Task 7's `detectAllPatterns` (`withoutOverlaps` before enrichment), as the plan's self-review already demands. Cost if wrong: fewer, cleaner patterns on the chart.
Ruling: R-PAT-7 — `detectContinuation` takes `(candles, atr, config)` only; the unused `lastIndex` parameter is dropped. Cost if wrong: none.

Ruling: R-PAT-8 — the brief's `isPivotHigh(series, 1, 2, 1)` assertion is unsatisfiable (index 1 is the max of its clamped window, and the same file requires `high:1`). The implementer's index 2 keeps equal strength; the plan line is corrected to index 0 (covers the left clamp and is genuinely false). Confirmed by the reviewer: spec ✅.
Task 1: review — spec ✅, quality Needs fixes: Important-1 dedup branch uncovered (deleting or inverting the comparator passes); Minors 2–3 add the left-clamp and a negative low case.
Task 1: fix round 1/5 (3 addressed, 0 open; commits 40b1388d..286768cd)
Task 1: complete (commits 3c9e79c2..286768cd, review clean)
Task 1: deferred minors: type-only import of EngineCandle (brief-mandated, no runtime cycle); left-clamp reachability comment; findAlternatingPivots has no production caller until Task 4.
Task 2: review — spec ✅, quality Needs fixes: Important-1 config test only range-checks (a typo'd threshold passes); Important-2 pennant.impulseLegAtrMin and wedge.convergenceMin are unread in Tasks 4/5.
Ruling: R-PAT-9 — Important-2 is a forward fix, not a Task 2 blocker: Task 4 must gate pennants with `pennant.impulseLegAtrMin` and detect wedges with `wedge.convergenceMin`; carried into the Task 4 dispatch. Cost if wrong: an unused config knob.
Task 2: deferred minors: BoundaryLine.slope / neckline.price from spec §3 are represented by from/to + lineSlope(); returns h1/h3/h5 hardcodes the horizons.
Task 2: fix round 1/5 (1 addressed, 0 open; commits 1af66d14..ffe351e9)
Task 2: complete (commits 286768cd..ffe351e9, review clean)
Task 3: review — spec ✅; quality Needs fixes: Important-1 neutral patterns can never leave `forming` (RECTANGLE/TRIANGLE_SYM dropped at expiry, R-PAT-2 unreachable); Important-2 expiry grace `5`/`-1` hard-coded in geometry.
Ruling: R-PAT-11 — neutral patterns confirm on the first close outside either boundary (direction stays `neutral` so R-PAT-3 returns remain null); the outcome function owns the break bias (R-PAT-2).
Ruling: R-PAT-12 — expiry grace and the sub-5-point exemption move into PATTERN_CONFIG as `expiryGraceBars: 1` and `expiryMinPoints: 5`; Task 9 renders both in «قواعد».
Task 3: fix round 1/5 (2 addressed, 0 open; commits fa449ecd..5387764c)
Task 3: complete (commits ffe351e9..5387764c, review clean)
Task 3: deferred minor: `emitPattern` has no non-test caller until Task 4.
Task 4: review — spec ✅; quality Needs fixes: Critical anchor/look-ahead (points end with lows[1] even when highs[1] is later; breakout can precede the last point); Important overlap (PENNANT + TRIANGLE_SYM co-fire), hidden thresholds, rectangle uses triangle.maxBars, tests miss FLAG_BEAR and status/breakout.
Ruling: R-PAT-13 — analytic thresholds move to PATTERN_CONFIG (`touchToleranceAtr: 0.5`, `flag.minLegBars: 3`, `triangle.minSpan: 3`); quality weights stay as named constants in the detector (scoring, not gates).
Ruling: R-PAT-14 — cross-kind continuation overlap is resolved by the boundary-pivot fingerprint (highs[1], lows[1]): a triangle/rectangle/wedge is dropped when a flag/pennant already used that pair; flags emit first.
Ruling: R-PAT-15 — bearish triangles/wedges get target = lower boundary − height and stop = upper boundary + atr; bullish mirrored (the brief's base was bullish-only).
Task 4: fix round 1/5 (6 addressed, 0 open; commits 4a1f42db..717bb514)
Task 4: complete (commits 5387764c..717bb514, review clean)
Task 4: deferred minor: bullish triangle/wedge target moved to upperEnd+height (unrequested but consistent); PENNANT fixture co-fire resolved by R-PAT-14.
Task 5: review — spec ✅; quality Needs fixes: Important-1 `span < 6` hidden (not in config/rules); Important-2 tests only positive (deleting the head/shoulder/triple guards keeps them green); Minors: unnamed saturated quality constants, triples pre-filtered with hs.maxBars, target height vs sloped neckline, chained tolerance allows 1.0 ATR spread.
Ruling: R-PAT-16 — add `reversal.minSpanBars: 6` to PATTERN_CONFIG (both families), named quality constants in the detector, and `max(peak)−min(peak) ≤ triple.levelToleranceAtr·atr` for triple level equality.
Task 5: fix round 1/5 (6 addressed, 0 open; commits e0a95ac2..53b67ff6)
Task 5: complete (commits 717bb514..53b67ff6, review clean; 1 new minor)
Task 5: deferred minor: neck extrapolated past the last pivot can make the measured height negative on steep necklines and invert the target → fix in the final wave with `max(height, 0.5*atr)`; no fixture covers it.
Task 6: review — spec ✅; quality Needs fixes: Important-1 meanReturns falls back to anchor when breakoutIndex is missing (unresolved/invalidated samples enter the average with a fabricated entry; doubles especially) and Task 7's adapter must copy breakoutIndex; Important-2 neutral target = height/2 fires on the first bar for converged patterns (needs a floor). Minors: hard-coded 5 samples, down-bias/returns sign untested.
Ruling: R-PAT-17 — add `neutralMinTargetAtr: 0.5`; neutral success target = max(height/2, 0.5*atr); render in «قواعد» (Task 9).
Ruling: R-PAT-18 — add `returnsMinSamples: 5` to config; render in «قواعد».
Ruling: R-PAT-19 — Task 7's `fromDoubleTap` must copy `breakoutIndex` from the double-tap pattern so reversal returns measure from the real breakout.
Task 6: fix round 1/5 (4 addressed, 0 open; commits 02d95c8e..53ff03f1)
Task 6: complete (commits 53b67ff6..53ff03f1, review clean)
Task 6: deferred minor: brief's Produces line lists a 4th `atr` arg for meanReturns; implementation is 3-arg (matches the code block).
Task 7: review — spec ✅; quality Needs fixes: Critical-1 fromDoubleTap sets upper=peak2/lower=neckline for DOUBLE_BOTTOM (troughs below the neckline → every double bottom "succeeds" and reversal rates inflate); Important-2 hidden `<=3` overlap and `>=8` literal; Important-3 §8 statistics tests thin; Important-4 estimateReturns includes unresolved-but-confirmed samples.
Ruling: R-PAT-20 — `overlapWindowBars: 3` moves to PATTERN_CONFIG (rendered in «قواعد», Task 9); tercile gates use `formationMinResolved`.
Ruling: R-PAT-21 — the double-tap adapter orders boundaries by direction: bullish (DOUBLE_BOTTOM) upper = neckline, lower = troughs; bearish upper = peaks, lower = neckline.
Ruling: R-PAT-22 — returns come only from samples whose outcome is resolved; the registry computes a resolved-id set and passes it to `estimateReturns`.
Task 7: fix round 1/5 (6 addressed, 0 open; commits fbea9474..9a712a77)
Task 7: complete (commits 53ff03f1..9a712a77, review clean)
Task 7: deferred minor: `outcomeOf` computed twice (registry and formation) — redundant, not wrong.
Task 8: review — spec ✅; quality Needs fixes: Important-1 neckline aliases the boundary (dashed overdraw) and several boundaries are zero-length (H&S upper, all double-tap lines) so they never render; Important-2 raw mid-tone hex labels fail contrast on the warm theme (≈2.6–3.6:1). Minors: size 10 + invalid `family:'inherit'`, thin tests.
Ruling: R-PAT-23 — the overlay skips zero-length lines and a neckline identical to a boundary; labels are theme-aware (mirror `smcOverlays` store read) with ≥4.5:1 on the panel, size 11 and a real font stack; Task 9's tab inherits the same palette facts.
Task 8: fix round 1/5 (4 addressed, 0 open; commits 29a34d4f..2553769a)
Task 8: complete (commits 9a712a77..2553769a, review clean)
Task 8: deferred minor: the ≤6 cap isn't exercised because selection yields at most 4 with two families; one shared mutable styles object across two figures.
Task 9: review — spec ✅; quality Needs fixes: Critical percentage unit (FormationEstimate.probability is 0..1; the card/overlay print 0.62 as «۱٪» while the interval is ×100 → self-contradictory card; fixtures hid it with 62); Important new tab label 9.5px (<11px rule); Minors duplicated KIND_FA, missing direction/click-to-focus.
Ruling: R-PAT-24 — `probability` stays 0..1 on the type; every surface multiplies by 100 at format time; fixtures must use 0.62 and assert «۶۲٪».
Ruling: R-PAT-25 — click-to-focus is deferred to Task 10 (the chart lives there); direction is added to the card now.
Task 9: fix round 1/5 (4 addressed, 0 open; commits c51e8a70..18f4c458)
Task 9: complete (commits 2553769a..18f4c458, review clean)
Task 9: deferred minors: the drawer still carries t-8/t-85/t-9 elsewhere; click-to-focus deferred (R-PAT-25).
Ruling: R-PAT-26 — detection runs where the series lives: `KLineChartWrapper` publishes `chartCandles` and calls `detectAllPatterns` in one effect after its `bars` memo, publishing `detectedPatterns`; the workspace stays unaware. Why: one owner for the series, no prop drilling, no duplicate fetch.
Task 10: complete (commits 18f4c458..1f339a5c, review clean; acceptance disclosed two unmet criteria)
Task 10: deferred minors: near-tautological regression test; measure.json dedupes 4xx (9 unique vs 18 responses); chartCandles has no reader yet.
Ruling: R-PAT-27 — the three technical-page 404s (`/api/chart/{symbol}/forecast|edge|indicators`) are pre-existing frontend/backend skew (routes absent in this checkout, called by TechnicalWorkspace before this wave); they do not block this mission, but zero-console-errors is reported as unmet, not passed. Cost if wrong: an unrelated API gap stays open.
Ruling: R-PAT-28 — the live formation card was never observed because none of the three tested series had a forming pattern; unit/UI tests cover the copy, live evidence remains unmet and is reported as such until a symbol with a forming pattern is found.
Final review: fix-first. Critical: the overlay is registered but never instantiated (no createOverlay) → the chart draws nothing (spec §7.2). Important: duplicate emissions (flag+pennant, rectangle+triAsc); emitter invalidates without the outcome buffer (status/outcome disagree); neck height can invert the target; rules omit nine config keys; click-to-focus missing; double-tap bounds are zero-length; triangles scan only the tail so they never contribute samples.
Final fix wave: commits 1f339a5c..998d3c7a (8/8 findings addressed; 666 tests / 83 files; live chart evidence shows the overlay and the tab).
Final review: SHIP after the fix wave (scoped re-review: no remaining Critical/Important; one minor: rules omit returnHorizons and flag.slopeOpposite).
Wave complete 2026-11-05. Unmet-but-disclosed: R-PAT-27 (three pre-existing technical-page 404s) and R-PAT-28 (no forming pattern in the tested series, so the live percentage card was never observed; covered by unit/UI tests).
