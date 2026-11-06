# SDD ledger — plan: docs/superpowers/plans/2026-11-04-fundamental-visual-redesign.md

Spec: docs/superpowers/specs/2026-11-04-fundamental-visual-redesign-design.md (committed a352b7a8)
Plan commit: cabd2c82
Worktree: D:/BorsTerminal-worktrees/4axes-main-integration
Branch: integration/4axes-main-2026-11-03
Model selection: live tool schema exposes no model parameter — session model inherited (recorded per Qoder integration rule).

## Preflight scan

Verified against current code (HEAD cabd2c82): useScreenerCore.ts, useFtsCard.ts, FundamentalPage.tsx, FundamentalScreenTable.tsx, FundamentalDetail.tsx, FundamentalCards.tsx, FundamentalSummary.tsx, exclusionFilter.ts, tableExport.ts, useSectorPe.ts, styles.css, vite.config.ts, api/fundamental.py, and the existing fundamental specs.

### Task pairs sharing a file or interface

| Pair | Produce → Consume | Finding |
|---|---|---|
| T1 → T2 | AxisStatus/AxisKey via axisMeta | consistent |
| T1 → T3 | AXES/statusOf/valueOf/thresholdOf/formatAxisValue/verdictFa + root thresholds | consistent; root thresholds must be added to ScreenerCoreSchema (T1 Step 6 second block) |
| T1 → T4 | thresholds for header/CSV meta | consistent |
| T1 → T5 | FtsCard history/metrics/indicator fields | consistent; backend already emits history (api/fundamental.py:2677), metrics (:2602), thresholds (:2696); details keys are Persian digits (:1718..:2023) |
| T2 → T3/T5 | Bullet/EpsBars/RegimeGlyph/AxisGlyph/PeDots/HistoryBars signatures | consistent |
| T3 → T4 | table rewritten then toolbar density/CSV added | consistent; T3 must not implement export (T4 owns it) |
| T3 → T7 | aria-sort/legend + keyboard rows | T3 code omits section E's aria-sort/columnheader; T7 test requires it → ruling R15 |
| T4 → T5 | page passes symbol/onBack only; detail rewritten | consistent |
| T5 → T6 | cardStatus/panels → consumer variants | cardStatus defined only in plan section B and reused by D → ruling R5 |
| T5 → old detail/holding specs | AxisDrilldown/quarterly/sector-pe removed | old specs would be red at T5 → ruling R4 |
| T4 → old page/exclusion specs | chips/legend/export columns change | old specs would be red at T4 → ruling R7 |
| T6 → old summary spec | Cards/Summary rewritten | old spec would be red at T6 → ruling R6 |
| T7 → T3/T5 | motion/focus/aria additions | consistent |
| T8/T9 | acceptance/report | consistent |

### Per-task self-consistency

| Task | Finding |
|---|---|
| T1 | PASS_KEYS typed over keyof ScreenerCoreRow cannot index ScreenerRowLike → R8; thresholdOf invents fallback thresholds → R2; row-level thresholds duplicated and unused → R10; formatAxisValue import mid-file (cosmetic) |
| T2 | PeDots/HistoryBars built but not tested → R13; .fd-chart-text uses undefined --font-code → R11 |
| T3 | test clicks button named /جستجو/ that the plan never renders → R1; section E aria-sort missing from code → R15 |
| T4 | CSV columns contain 'صنعت' twice → R9; old page/exclusion specs not in file list → R7 |
| T5 | React.ReactNode without React import → R3; mockedCard/holdingCard helper undefined in snippet (implementer defines); old detail/holding specs not in file list → R4 |
| T6 | Step 2 is incoherent staccato (repeats "the plan"); section D is authoritative → R12; old summary spec missing from file list → R6 |
| T7 | row accessible-name lookup may be brittle; fallback allowed → R14 |
| T8 | honest evidence gate: no PASS before owner visual vote (plan constraint) |
| T9 | report only |

## Rulings

R1: Drop the T3 test line `fireEvent.click(getByRole('button', {name:/جستجو/}))` — no such control exists in the plan's toolbar; keep search input + row-select assertions. Cost if wrong: one meaningless interaction untested; no functional impact.
R2: thresholdOf returns null when a threshold is absent; no invented 40/3/20/0.33 fallbacks. Global constraint forbids new thresholds. Cost if wrong: cells show '—' where backend threshold is absent — the intended unknown semantics.
R3: Use `import type { ReactNode } from 'react'` instead of `React.ReactNode` in Quintet/AxisPanel. Cost: typing-only; zero functional risk.
R4: Task 5 replaces/updates fundamental-detail.spec.tsx and fundamental-holding.spec.tsx in the same commit (remove useQuarters mock, quarterly-panel, sector-pe-panel→panel-industry). Cost: bigger T5 commit; prevents red suite between tasks.
R5: Extract cardStatus/CARD_KEY/CARD_NUM into frontend-v2/src/features/fundamental/lib/cardStatus.ts, shared by panels, Quintet, ScoreRibbon, consumers. Cost: one small extra file; prevents duplicated logic.
R6: Task 6 also updates fundamental-summary.spec.tsx and includes it in the commit. Cost: broader test diff; keeps full suite green.
R7: Task 4 updates fundamental-page.spec.tsx and fundamental-exclusion.spec.tsx in the same commit (cells/legend/export; chips→cells). Cost: broader test diff; keeps suite green.
R8: Type PASS_KEYS over keyof ScreenerRowLike, not keyof ScreenerCoreRow. Cost: typing only.
R9: CSV headers: sector column 'صنعت شرکت', axis column 'صنعت' (no duplicate header). Test arrayContaining still passes. Cost: CSV wording; avoids ambiguous duplicate column.
R10: Do not add row-level thresholds to ScreenerCoreRowSchema; thresholds only at root ScreenerCoreSchema. Cost: none; avoids dead schema.
R11: --font-code is undefined; .fd-chart-text uses font-family: inherit with tabular-nums. Cost: chart labels use app font; visual only.
R12: Task 6 staccato Step 2 is not executable; plan section D (FundamentalCards/FundamentalSummary variants) is authoritative. Cost: none.
R13: Add PeDots/HistoryBars assertions to fundamental-mini.spec.tsx in Task 2. Cost: two small tests; covers code the plan builds.
R14: If getByRole('row', {name:/رنيك/}) fails on accessible-name computation, fall back to getByTestId('fundamental-row-رنيك') while asserting tabIndex=0. Cost: none; test intent preserved.
R15: Task 3 implements section E's aria-sort on `<span role="columnheader" aria-sort=...>` (and a role="row" header container) immediately, so T7's test is not deferred. Cost: small markup addition; correct a11y.

## Progress

Task 1: implementer DONE (commit 71a599d1). Review: spec compliant ✅; Important 2 (axis-4 unit mismatch; R2 untested). Minors deferred: prefs defaults test tautological; schema spec runtime-vacuous under looseObject; formatAxisValue lacks finite guard/Intl grouping; thresholdKey mapping duplicated; CSS lacks unqualified paper fallback; threshold key types duplicated. Parked (reviewer wrong): claim that i*_na is unreachable — Python /api/screener supplies i3_na/i4_na (S4b bank rows); verify live in Task 8.

R16: Axis-4 display/sort use `sales_to_mcap` only; never fall back to `profit_potential_pct` for the value/threshold pair (0.33 ratio vs 40% have different units). Potential profit remains visible in SalesPanel rows/evidence. Cost if wrong: rows where only potential exists show '—' in the axis-4 cell while status may still pass/fail; a dual-line chart would need a data-model change out of scope.

Task 1: fix round 1/5 (2 addressed, 0 open — R16 fallback removed + R2 threshold tests added; commits 71a599d1..cebe6c6e)
Task 1: complete (commits cabd2c82..cebe6c6e, review clean)

Task 2: implementer DONE (commit b4c529cd). Review: spec ❌ (3 Important, all plan-mandated deviations from global constraints); minors deferred: EpsBars width degenerates for long series; null points render as tiny bars; Bullet max=0 NaN; PeDots negative P/E off-canvas/empty text node; AxisGlyph labels shorter than statuses; hardcoded 9px; test coverage gaps; report inaccuracies.

R17: Deviate from the brief's literal mini-chart markup to satisfy the global "color is not the sole status carrier" and "Persian digits" constraints: (a) add exported `statusFa`/`regimeFa` to axisMeta; (b) every chart's aria-label/title carries the Persian status word and Persian digits; (c) HistoryBars drops the inert inline color and gets `.fd-history-bar.is-*` CSS rules covering pass/fail/na/unknown (unknown = warn, not flat); (d) the active regime dot gets a non-color outline. Cost if wrong: slightly more CSS/DOM than the mock; no functional behavior change.

Task 2: fix round 1/5 (3 addressed, 0 open; commits b4c529cd..de7bb21a)
Task 2: complete (commits cebe6c6e..de7bb21a, review clean)
Task 2 minors deferred: RegimeGlyph null regime announces "— —"; fractional values keep ASCII decimal point; PeDots negative P/E uses ASCII hyphen; HistoryBars regression assertion checks only style.background.

R18: In Task 3 the table's `thresholds` prop is optional (`thresholds?: AxisThresholds | null`); FundamentalPage wires it in Task 4. Reason: Task 3's typecheck would otherwise fail on the unchanged page. Cost if wrong: header thresholds show '—' for one task only.
R19: Task 3 updates `fundamental-page.spec.tsx` to the new cell/testid DOM in the same commit; `fundamental-exclusion.spec.tsx` should pass unchanged. Cost: broader T3 diff; keeps the full suite green.
R20: Task 3 implements the final five-column CSV export (same testid/base and scan-time meta) so the page spec export test stays green; Task 4 verifies it and adds density/surface toggles. Cost: T4's table change shrinks; avoids a red suite between tasks.
R21: Axis headers are sort buttons inside `role="columnheader"` spans; remove the unused SORT_KEYS constant (or use it). Cost: small header markup; makes declared axis sort keys usable.
R22: CSV/display semantics per column: eps = `years_available/۳`, sales = `sales_to_mcap`, industry = Persian regime, growth/margin formatted values. Cost: CSV 2nd column carries years, matching the visible column and its 3-year threshold.
R23: AxisCell uses axisMeta helpers (`statusOf/valueOf/formatAxisValue/statusFa`) with the eps-years special case; no duplicated status maps. Cost: none.
R24: Visible header thresholds use Persian digits (and `٫` for sales); CSV threshold meta values stay Latin numerals because Task 4's mandated test expects '60'. Cost: mixed numeral style in CSV metadata only.
R25: Add `reasonOf(row, axis)` to axisMeta (i*_reason; eps falls back to eps_data_gap); the status span's title carries it, preserving S4b's "why" tooltip. Cost: tiny API addition.
R26: Preserve `fundamental-excluded-${symbol}` testid on the excluded badge. Cost: none.
R27: Table ARIA: wrapper `role="table"`, header `role="row"` with `role="columnheader"` + `aria-sort`, body rows `role="row"`, cells `role="gridcell"`, virtual wrapper `role="presentation"`; keyboard rows keep Enter/Space. Supersedes/expands R15. Cost: more markup; correct semantics.
R28: Extend the T3 table test to actually click an axis sort header and assert row order (the plan's test name claims sorting but only searched). Cost: one assertion.

Task 3: implementer DONE (commit f0b1ce83). Review: spec ❌ (2 Important: absent EPS years shown as ۰/۳; unmapped verdict shown as —); full suite 435 green. Minors deferred: threshold formatting duplicated; hardcoded ۳ سال//۳; Latin score in CSV; weak CSV/NA/compact/aria-sort/virtual assertions; role=gridcell non-conformant (R32 fixes); aria-sort on non-sortable headers; '#' header vs glyph; empty state bare p; duplicate scan time (R33 fixes); compact badge row heights; visible NA marker unasserted; lastEps duplicated.

R30: Absent `eps_years_available` renders '—/۳' in the cell and CSV, never '۰/۳'. A missing field is unknown, not zero. Add a fixture with the field omitted and assert it. Cost: a pass/fail row with missing years shows '—/۳'; honest.
R31: `verdictFa` falls back to the raw verdict string when unmapped (so 'FTS ندارد' stays visible instead of '—'); add a test for it. Cost: an unexpected English token could display raw; backend verdicts are known Persian/enum.
R32: Use `role="cell"` (not `gridcell`) inside `role="table"`; set `aria-sort` only on sortable columnheaders; label the first columnheader 'نمای پنج‌محور' (it renders AxisGlyph, not '#'). Cost: markup-only; ARIA-conformant.
R33: Remove the duplicate visible scan-time span from the table toolbar; the page header remains the single visible label (CSV meta still uses asOf). Cost: a table rendered without its page shows no scan time.
R34: Strengthen the table test: assert the NA cell's data-state, assert `.fd-axis-chart` is absent in compact, assert the active growth header's aria-sort value, and cover the R30/R31 fallbacks. Cost: small test additions.

Task 3: fix round 1/5 (5 addressed, 0 open — R30/R31/R32/R33/R34; commits f0b1ce83..d84eef0a)
Task 3: complete (commits de7bb21a..d84eef0a, review clean)
Task 3 minors deferred: raw unmapped verdict chip uses warn color; exclusionFilter still uses eps ?? 0 (S4b code, out of scope); table asOf now only feeds CSV; weak CSV assertions; compact badge row heights; threshold formatting duplication; hardcoded ۳ سال; lastEps duplication.

Task 4: implementer DONE_WITH_CONCERNS (commit 596d102f); full suite 443 green. Review: spec compliant ✅, 1 Important (toggle contrast on paper ~1.9:1/2.9:1); minors deferred: unconditional empty as-of span; implementation-coupled class assertions; loose token substrings; no group label for surface pair; Latin CSV meta (plan-consistent); no thresholds-null test.

R42: Controls inside the data surface must use surface tokens, not app-theme tokens. Add scoped CSS `.fundamental-surface .tape-btn` overrides (border `--fd-line-strong`, text `--fd-text-2`, background `--fd-panel`) plus hover/focus and `[aria-pressed='true']`/`[aria-expanded='true']` states using `--fd-accent`/`--fd-text`; keep the app shell untouched. Wrap the surface pair in `role="group" aria-label="سطح داده"`. Cost if wrong: S4b controls inside the fundamental surface get a slightly different look; improves contrast in both paper and ink.
R43: Keep the scan label conditional but reserve `ms-auto` alignment with a wrapper, so no empty span; add a no-as_of test asserting no 'زمان اسکن' text while controls still render. Cost: none.
R44: Drop raw class-string assertions; assert exact `--fd-*` text tokens on the loading/error nodes and containment within the page testid. Cost: tests become less coupled to class composition.
R45: Add a `thresholds: null` test: header/cell thresholds show '—' and CSV meta threshold values are '—'. Cost: one test.

Task 4: fix round 1/5 (4 addressed, 0 open; commits 596d102f..c68c1ebb)
Task 4: complete (commits d84eef0a..c68c1ebb, review clean)
Task 4 minors deferred: active paper toggle 4.4989:1 borderline (Task 7/8 tune); scoped tape-btn restyles the settings-drawer close chip; empty ms-auto wrapper; latent .count rule; raw class-free token test nuance.

R46: Task 5 deletes `QuarterlyTrend.tsx`, `useQuarters.ts`, and `fundamental-detail.spec.tsx` after Detail stops importing them; update `fundamental-holding.spec.tsx` (drop useQuarters mock; `sector-pe-panel`→`panel-industry`) in the same commit. No other consumers exist. Cost: removing S4b quarterly trend UI; the new HistoryPanel replaces it with reported annual history.
R47: Extract `cardStatus`/CARD_KEY/CARD_NUM into `frontend-v2/src/features/fundamental/lib/cardStatus.ts`, shared by panels, Quintet, ScoreRibbon, and later consumers (R5). Cost: one small file.
R48: Detail header uses Persian digits for score (`toFaDigits`) and formats a date-only `freshness.as_of` as Jalali via `jalaliFromYmd`; non-date strings stay raw. Cost: date display changes from ISO to Jalali.
R49: When `card.applicable === false` (funds/options), render `data-testid="fundamental-not-applicable"` with the S4b wording and skip Quintet/ScoreRibbon/five panels; keep header, calendar, health. Preserves the holding spec's fund case. Cost: no five-axis visualization for non-applicable instruments, by definition.
R50: EpsPanel/Quintet show '—/۳' when `years_available` is null; never '۰/۳'. Cost: honest unknown.
R51: Status colors in ScoreRibbon/Quintet/panels follow the table mapping: pass up, fail down, na flat, unknown warn; status words via `statusFa`. Cost: unknown is visually distinct from na.
R52: EvidencePanel subcheck React keys are prefixed with the axis digit (`${digit}-${sub.key}`) to avoid duplicate keys across axes. Cost: none.
R53: Holding/bank keep `HoldingNavPanel` with `holding-pnav-panel`/`holding-nav-na` testids (S4b); normal symbols use `panel-industry`. Keep `FtsSettingsTrigger`, `CorporateCalendar`, `CodalHealthStrip`. Cost: none.
R54: Task 5 runs cockpit + holding + calendar + settings specs and the full suite; old specs updated in the same commit. Cost: broader commit.
R55: `AxisPanel` uses `statusFa` for the header status word and keeps the formula/source `<details>`; panel values are Persian-formatted. Cost: none.

Task 5: implementer DONE (commit 907ed13b); full suite 448 green. Review: spec ❌ (2 Important: fabricated strongest/weakest ranking; Latin digits in history period_end); minors deferred: weak evidence-key/unknown-status tests; Quintet/AxisPanel formatter divergence (sales threshold ۰٫۳ vs ۰٫۳۳); status color re-encoded inline; consolidated false shown as '—'; IndustryPanel regime triplication; HistoryPanel EPS badge/formula duplication; long text overflow; evidence detail title-only; holding industry tile no-op + wasted sectorPe fetch.

R57: Remove the strongest/weakest labels from ScoreRibbon entirely; keep counts (pass/fail/abstain), verdict and score. Ranking by AXES order makes a factual claim the data does not support; ranking by threshold margin would be a new derived rating. Cost: less interpretation in the ribbon; no false claim.
R58: HistoryPanel formats `period_end` with `toFaDigits` for both chart labels and the «آخرین دوره» row; add a cockpit assertion that the Persian form is visible. Cost: none; fixes the last Latin-digit value in the surface.
R60: Add cockpit tests for the two status rules: passes key absent + `na:true` → «بی‌نظر»; passes key absent without `na` → «نامشخص» (never «رد»). Cost: two assertions on a modified fixture.

Task 5: fix round 1/5 (3 addressed, 0 open — R57/R58/R60; commits 907ed13b..a554150d)
Task 5: complete (commits c68c1ebb..a554150d, review clean)
Task 5 minors deferred: evidence-key test only checks text; Quintet/AxisPanel formatter divergence (sales threshold ۰٫۳ vs ۰٫۳۳); NaN guard; status color inline duplicate; consolidated false as '—'; IndustryPanel regime triplication; HistoryPanel badge/formula duplication; long-text overflow; evidence detail title-only; holding industry tile no-op + unnecessary sectorPe fetch. Out-of-scope: old FundamentalSummary still has a fabricated «ضعیف‌ترین» — Task 6 removes it.

R62: Delete `fundamental-summary.spec.tsx` (its behavior belongs to the replaced components); the new `fundamental-consumers.spec.tsx` covers the new Cards/Summary: 5 `[data-axis]` cards, status words, no formula text, count/statuses, toggle/static modes, loading/error/empty. Cost: fewer but relevant tests.
R63: `FundamentalSummary` preserves the S4b toggle: when `onToggle` is supplied render a button with `aria-expanded` and the expand/collapse hint; otherwise a static div. Cost: none.
R64: Preserve `data-testid="fund-summary-count"` on the «N از ۵» element so `symbol-sidebar.spec` stays green. Cost: none.
R65: Delete `ui/AxisDrilldown.tsx`; rewriting `FundamentalCards.tsx` removes the now-dead `QUALITY_WORD`/`fundamentalFacts`/`cardFacts`/`FundamentalFact`/`CardFact` exports (only the old Summary used them). Cost: none.
R66: Cards/Summary use `cardStatus`, `AXES`, `statusFa`, `--fd-*` tokens and `data-fund-surface`; unknown=warn; no fabricated weakest/ranking; compact cards show no charts/formulas. Cost: the dock loses the old notes/freshness badge; the detail header carries freshness.
R67: BottomDock/SymbolSidebar props stay unchanged; modify them only if a real prop mismatch appears. Cost: none.

Task 6: implementer DONE (commit 0b6f4278); full suite 444 green. Review: spec ❌ (1 Important: summary fd text tokens without fd background are near-invisible in the default brass/paper configuration); minors deferred: Cards loading/error same bg issue; data_gap/available pass:false regression untested; inert fd-status class on bars; per-axis status color-only.

R69: The summary root (button and static div) and the Cards loading/error messages must paint an fd background (`bg-[var(--fd-bg)]` or `bg-[var(--fd-panel)]`) whenever they use `--fd-text*` tokens, so paper text is never placed on the dark shell and ink text never on a light shell. Keep testids/data attributes. Cost: the sidebar summary becomes a paper/ink strip; readable in both themes.
R70: `cardStatus` precedence: `indicator.na === true` → na; else `indicator.available === false` or `indicator.data_gap === true` → unknown; else pass true/false; else unknown. This restores the S4b rule that an unavailable axis is never shown as a rejection. Add consumers tests for pass:false + available:false and pass:false + data_gap:true. Cost: a stale pass/fail on a data-gap axis shows «نامشخص» instead of a claim.
R71: Summary status bars carry `data-status`, a Persian `title`/`aria-label` with the axis label and `statusFa`, and the visual row is no longer `aria-hidden`; drop the inert `fd-status--*` class from the bar. Cost: per-axis status is available to AT; slightly more markup.

Task 6: fix round 1/5 (3 addressed, 0 open — R69/R70/R71; commits 0b6f4278..c627c1c3)
Task 6: complete (commits a554150d..c627c1c3, review clean)
Task 6 minors deferred: summary toggle's accessible name now includes five bar labels (consequence of R71); cockpit ScoreRibbon bars are still aria-hidden/color-only (Task 7 R72).

R72: Cockpit ScoreRibbon bars follow R71: `data-status`, Persian `title`/`aria-label`, no `aria-hidden`, no inert status class. Cost: consistent per-axis AT.
R73: Panel entry motion uses `.fd-in` (opacity + 3px translateY, 220ms ease-out) with CSS nth-child stagger 40ms; charts use `.fd-draw` (450ms ease-out, no layout properties). No row entrance/loop in the frequent table.
R74: Density/surface changes do not remount the table or animate height; a 160ms opacity transition on chart wrappers is the only effect. Surface crossfade on the cell content only.
R75: Quintet click scrolls the panel into view and moves focus to the panel header (`tabIndex=-1`); guard `scrollIntoView` for jsdom (R56) and test the focus with a spy.
R76: `@media (prefers-reduced-motion: reduce)` neutralizes `.fd-in`/`.fd-draw` to opacity-only (the global rule already shortens durations), and all new focus states use `--fd-accent` with `:focus-visible`.
R77: Add `fd-in` to AxisPanel/Quintet/ScoreRibbon/Evidence/Calendar wrappers; do not animate table rows. Cost: subtle entry motion on the detail only.

Task 7: implementer DONE (commit 05c98ab9); full suite 451 green. Review: spec ❌ (1 Important: density/surface crossfade is a dead rule and targets the table chart contrary to R77); minors: stagger stops at child 6; extra fd-in on Quintet/ribbon (R77-mandated; report inconsistency only); focus lands on panel root not header; reduced-motion scroll branch untested; grid-child coupling; ribbon data-status mapping untested.

R78: Implement the density/surface crossfade as a one-shot opacity dip on the table body: state-driven class for 160ms when density or surface changes (skip the initial mount), no remount, no height animation, instant under reduced motion; remove the dead `.fd-axis-chart` transition. Cost: a small timer/state in the table; a brief dip when the user toggles density/surface.
R79: Focus the panel header, not the panel root: give the AxisPanel `<h3>`/header `tabIndex={-1}` and an id (`panel-<axis>-title`), and focus it after scroll; update the a11y test's activeElement expectation. Cost: AT announces a short heading instead of the panel body.
R80: Use a dedicated `fd-enter` class on the nine detail grid wrappers for stagger (delays through child 9), keep `fd-in` only for Quintet/ScoreRibbon roots (R77), and make the a11y test assert `.fd-enter` count, not `.grid-cols-12` children. Cost: clearer motion ownership.
R81: A11y test: stub `matchMedia` for both modes and assert scroll `behavior` smooth vs auto; assert each ScoreRibbon bar's data-status maps to the expected axis. Cost: better regression coverage.

Task 7: fix round 1/5 (4 addressed, 0 open — R78/R79/R80/R81; commits 05c98ab9..e7eb489c)
Task 7: complete (commits c627c1c3..e7eb489c, review clean)
Task 7 minors deferred: fading can stick if reduced-motion flips mid-fade; focused panel header gets the generic ring; EvidencePanel has no id/tabIndex; pre-existing ForecastControls act warnings (unrelated, reproduced at HEAD).

## Task 8 live acceptance (in progress)

Evidence dir: _audit/rebuild/fundamental-redesign/
Servers: Python 8110 (BORS_WORK_DIR=D:/BorsTerminal-tmp/4axes-data, no fetch loops), Vite 7092 (7091 was another worktree). Served checkout verified via /@fs path and axisMeta statusFa.
Screener: 783 rows, as_of 1793789597, thresholds growth 60 / margin 40 / sales 0.33.
Table snapshot: five axis headers, 84-96 charts comfortable, 0 compact, paper/ink toggles work, 783/783, aria-sort descending. Dev-mode TBT scroll at 1920: 22 long tasks / 2000ms TBT / 197ms max / 72MB heap — investigate under production build.
Live bug found: `GET /api/fundamental/رنيك` returns 200 but the frontend detail shows the error state — `indicators['2'].evidence` is an array (`['audited_year_end', ...]`) while `Axis2Schema` requires a string. Fix now.

R82: `Axis2Schema.evidence` accepts a string OR an array of strings (union, nullish); EpsPanel joins arrays with '، '. Add a schema test with array evidence and a cockpit assertion. Cost: none; unblocks every symbol detail card (the schema failure currently fails the whole card).

Task 8 fix 1: commit d6ed358c (evidence array accepted; 457 tests green). Live detail now opens in ~2.3s.

R83: `freshness.as_of` sometimes arrives as an ISO datetime (`2026-06-30T18:50:20+03:30`), not just a date. Format any parseable ISO date/datetime to a Persian Jalali date via `Intl.DateTimeFormat('fa-IR-u-ca-persian', { dateStyle: 'medium', timeZone: 'Asia/Tehran' })`; unparseable strings stay raw. Cost: header shows a Jalali date instead of the raw timestamp; fixes the last Latin-digit value in the header.

Task 8 fix 2: commit 7b2a3261 (freshness Jalali; 459 tests green).

R84: Production scroll at 1920 (783 rows) measured 46 long tasks / 593ms TBT / 81ms max; 47 of 55 frames >50ms. Memoize `FundamentalAxisCell` (React.memo; row object/thresholds/axis are referentially stable during scroll) and reduce virtualizer overscan from 14 to 8. Keep behavior and tests unchanged. Cost: fewer offscreen rows under a fast fling (possible brief blank), much less per-frame reconciliation.
R85: Acceptance harness only: wait for a generic row before searching after route changes; measure cell contrast on the first visible cell rather than a specific symbol. Cost: none.

R86: Adopt TanStack Virtual's `directDomUpdates` mode for the table (installed react-virtual 3.14.23 supports it): item wrappers get `data-index` + `ref={virtualizer.measureElement}`, no `top` style; the inner container gets `ref={virtualizer.containerRef}` and no height style; options `directDomUpdates: true, useFlushSync: false`. This writes item positions/size directly to the DOM and re-renders React only when the visible range changes. Keep the memoized AxisCell (R84) and overscan 8. Cost: rows are measured (getBoundingClientRect) and direct-DOM styles bypass React; a fast fling may briefly blank until the range re-render lands. If the measurement worsens or breaks, fall back to the previous virtualization.
Task 8 fix 3/4: commits c5004b8b (memo+overscan), 9780d6f5 (directDomUpdates). Production TBT now 54/4/0ms comfortable and 0/0ms compact at 1920; 0 console errors.

## Visual acceptance findings (before owner vote)

From the 1366/1920 production screenshots:

R87: The first glyph columnheader has only an aria-label; show a visible `#` in the 38px header cell. Cost: 1 char.
R88: EPS evidence is an English token array; map known tokens (audited_year_end → سال‌پایانِ حسابرسی‌شده، annualized_interim_short → سال‌سازیِ میاندورهٔ کوتاه) and join with '، '; unknown tokens stay raw. Cost: none.
R89: Margin tier `below_floor` (and peers) render raw English in the margin panel; map below_floor → زیر کف، acceptable → قابل قبول، ideal → ایده‌آل; unknown stays raw. Cost: none.
R91: Growth values in the Quintet and GrowthPanel lack the `+`/`−` sign used by the table; use a signed percent formatter for growth only. Cost: consistency.
R92: Compact rows clip their content because the value+status+threshold stack exceeds 38px. In compact, hide the `.fd-axis-threshold` line (header/legend still show thresholds) and keep only value+status; add a test asserting no threshold line in compact. Cost: compact loses per-cell threshold text (available in the header).
R93: HistoryBars are invisible: each HTML bar's percentage height resolves against an auto-height flex column. Give each column `h-full` with a `flex-1` bar area so the percentage height resolves, keep the label below; assert the bars carry a non-empty inline height in the mini spec. Cost: none.
R94: ScoreRibbon's count spans run together visually («قبول۲ رد»); add `·` separators between the pass/fail/abstain counts. Cost: none.
Task 8 fix 5: commit f6032981 (R87-R94; 463 tests green). Production TBT 15/3/0ms comfortable, 0/0 compact; compact fits; history bars visible; growth signed; EPS evidence and margin tier Persian.

R95: Restyle the S4b panels that still use app-shell tokens — `HoldingNavPanel`, `CorporateCalendar`, `CodalHealthStrip` — with `--fd-*` surface tokens (panel bg/line, text-2/3, warn for N/A/feed gaps). They are used only inside the fundamental detail surface; preserve text/testids/behavior. Cost: the panels change appearance inside the new surface; they match paper/ink instead of rendering as dark shell blocks.
Task 8 fix 6: commit e57ee0f6 (S4b panels surface-skinned; 463 tests green).

Task 8 evidence (production build, Edge headless, 1366×768 + 1920×1080):
- 783/783 rows; five axis headers (#, نماد, 1-5, امتیاز, وضعیت); comfortable charts 60-96, compact 0; paper/ink + density measured by attribute/chart effects.
- Scroll TBT 1920 comfortable: 405ms first (warm-up), 0ms, 0ms; compact: 0ms, 0ms. Long tasks 30/0/0 and 0/0. Heap 22-45MB.
- Console errors 0; only `/api/sync/codal/pipeline` ERR_ABORTED due route navigation.
- Contrasts: cell value 14.72, cell status fail 5.45, panel title 16.52, panel status 6.12, surface toggle 4.50, count 4.61.
- Detail رنيك: 5 quintet axes, 7 panels, ribbon «۳ از ۵», Jalali freshness «۹ تیر ۱۴۰۵», settings/calendar present; ink surface works; holding/bank N/A explicit and no fake P/NAV; normal symbol has panel-industry.
- Keyboard Enter navigates; reduced-motion focus lands on `panel-margin-title`, animation fdFadeOnly.
- Full suite 67 files / 463 tests green; typecheck clean; working tree only untracked `_audit/rebuild/` and `zz_tmp_dump_test.go`.
Owner visual vote pending; no push; no PASS claim yet.

## Final whole-plan review (Needs fixes)

7 Important: (1) growth cockpit shows 1a with `monetary.threshold` (40) and omits 1b while table uses growth_min 60; (2) EPS cell shows 3/3 + threshold 3 years even when 234 live rows fail the trend gate; (3) EPS gate setting v10_eps_years hardcoded 3; (4) 160 exempt live rows labeled «بانک / N/A»; (5) freshness states/gap reasons fetched but unsurfaced; (6) detail loading/error lack fd background/back/settings; (7) live margin tiers/evidence tokens still English. Deferred-minor triage: EPS-gate hardcode must fix; holding industry tile dead if cockpit edited; other minors can remain.

R97: Growth cockpit aligns with the S4b gate. Parse `Axis1Schema.monetary.target_threshold/pass` and `volume.real_pct/volume_pct/pass/threshold/note/data_gap/basis`. GrowthPanel uses `target_threshold` (fallback threshold) for the big value/chart, shows 1a and 1b values with the 1b status word (N/A when `volume.applicable === false`), and reasons. Quintet uses `target_threshold` and the combined status. `cardStatus('growth')` treats `monetary.data_gap`/`volume.data_gap` as unknown before pass/fail. Cost: the growth tile threshold matches the table (60 in the live payload) and a 1a pass with a 1b fail is no longer hidden.
R98: EPS cell/panel/quintet show the last EPS plus a trend arrow (↑/↓/→ from the series), not `years/years` as the value. The denominator uses `eps_years_required`/`years_required` (configured), and the threshold line shows the configured years. Table EPS sorting uses the displayed last EPS. Compact keeps the arrow even though the threshold line is hidden. Cost: the EPS column no longer implies 3/3 should pass; the trend is the gate.
R99: The EPS gate setting is honored everywhere: table header/cell use `v10_eps_years`/`eps_years_required`; FtsCard parses root `thresholds.v10_eps_years`; EpsPanel/Quintet use `years_required` with that fallback. Add a test with `v10_eps_years: 1`. Cost: `/۱` and «۱ سال» when the setting changes.
R100: The table badge for `i4_na` reads «معاف / N/A» (not «بانک»), with `i4_reason` as title; keep the testid. Cost: holdings/financials are no longer mislabeled as banks.
R101: Surface freshness attention: if any `freshness.axes[].state` is stale/missing/quarantined, the detail header shows «N محور نیازمند بررسی» with the axis labels in `title`; each panel shows a visible reason row for na/unknown/data-gap axes (growth monetary/volume, EPS data_gap/reason, margin reason, sales reason). Cost: the why is visible instead of only a tooltip.
R102: Detail loading and error states use the same data surface (`data-fund-surface`, `fundamental-surface`, fd background/text) and render the back button, symbol title, and settings trigger; error keeps retry. Cost: no dark/light mismatch and no navigation loss while loading/error.
R103: Localize the live token set: margin tiers good/standard/floor (plus existing), EPS evidence consolidated_unaudited/consolidated_audited/annualized_interim, EvidencePanel digits/commas via toFaDigits + `٬`, CodalHealthStrip «sync» → «همگام‌سازی» with Persian digits in timestamps, and IndustryPanel market share with 2 decimals. Cost: no English/Latin values in the Persian surface.
Task 8 final fix 1: commit 92d8bc1d (R97-R103; full suite 484 green). Re-review: seven findings addressed; one introduced defect in GrowthPanel 1b data-gap + minors.

R104: GrowthPanel 1b status precedence: `applicable === false` → na; `data_gap === true` → unknown; pass true/fail; else unknown. Never «رد» for a data gap. Also for 1a monetary data_gap. Add a test with `volume.applicable:true, data_gap:true, pass:false` asserting «نامشخص». Cost: missing data is no longer reported as a rejection.
R105: EPS trend arrow must reflect the whole finite series (all consecutive diffs >0 → ↑, all <0 → ↓, otherwise →), not the last two points; `[1425,454,456]` must not show ↑. Add a test. Cost: the arrow cannot contradict the gate on a two-point bounce.
R106: EpsPanel's «آخرین EPS» row uses the same last finite value as the headline; parse/display `volume.reason` for 1b failures (fallback to note); EvidencePanel applies the same digit localization to `threshold` as to `value`. Cost: no internal contradiction.
R107: CSV meta includes `['آستانه EPS', String(thresholds?.v10_eps_years ?? '—')]`; the EPS column stays the display value (last EPS + arrow) with the gate visible in meta. Cost: exports carry the gate again.

Task 8 final fix 2: commit 53e2e1a9 (R104-R107). Re-review: all four findings ADDRESSED, no new Critical/Important. Full suite 489/489; typecheck clean.
Final production evidence (build after 53e2e1a9): 0 console errors; realistic scroll (2,000px/3.2s) 3× comfortable and 2× compact: 0 long tasks, 0 TBT, 194 frames each, max frame gap 23-29ms, 0 frames >50ms; full-fling (68,904px/3.2s) 88-405ms TBT across runs (latest saved 235ms). Screenshots refreshed; growth panel فولاد shows ۱الف ۵۶٪/کف ۶۰/۱ب −۲٫۵٪ · رد; EPS panel رنيك shows ۱۶۷۲ ↑ / ۳ سال; table وبملت badge «معاف / N/A».
Owner visual vote: APPROVED (2026-11-04) on this evidence (HEAD 53e2e1a9). No push.
Task 8: complete (commits cabd2c82..53e2e1a9, evidence in _audit/rebuild/fundamental-redesign).
Task 9: final report delivered in chat; S4c backlog: Go materializer + /api/fts/config port, DPS/Go card; deferred minors remain in this ledger.

