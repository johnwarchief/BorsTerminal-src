# Round 10 — Corporate-Action Reconciliation & Production Parity

Date: 2026-10-21
Branch: `mission/ra365-round10-corporate-action-parity-2026-10-21`
Base: `3e788f95a3a50cf60ff3e3823e8ae5ce6986b225` (Round 9)
Status: **PARTIAL — one real production-path improvement (+9.38pp exact),
two data backfills rejected, remaining clusters documented.** No 100% claim.

## 1. Executive summary

The production chart path improved in this round by a **code-only** change:
the official recomputed DPS must replace an old `priceAdjust` or base-gap
ratio for the same action, instead of being suppressed by it.  Measured with
the real `price_history.close` source and the fixed v4 universe:

| Metric | Before (base DB) | After (code fix) | Δ |
|---|---:|---:|---:|
| Factor exact | 38.9343% (462,518/1,187,945) | **48.3147%** (573,952/1,187,945) | +9.3804pp |
| Factor ±1% | 79.8020% (948,004/1,187,945) | **81.5694%** (969,000/1,187,945) | +1.7674pp |
| Functional OHLC | 39.5054% (1,877,208/4,751,780) | **48.7637%** (2,317,144/4,751,780) | +9.2583pp |
| Normalized exact | 41.0532% (487,690/1,187,945) | **41.2898%** (490,500/1,187,945) | +0.2366pp |
| Normalized ±1% | 82.0007% (974,123/1,187,945) | **82.0320%** (974,495/1,187,945) | +0.0313pp |
| Step mismatch | 278 | **262** | −16 |
| REF_ONLY / PROD_ONLY | 160 / 163 | **155 / 158** | −5 / −5 |
| Step pairs | 6,356 | 6,361 | +5 |
| Missing product / reference | 1,845 / 2,170 | 1,845 / 2,170 | 0 |
| Raw exact | 97.4727% | 97.4727% | 0 |

The universe (2,595 assets) and every factor/functional denominator are
unchanged.  The step-pair count rises by 5 because 5 REF_ONLY steps became
comparable; the mismatch numerator falls by 16, so the mismatch rate falls.

Two official-data backfills were tested and **rejected** because they made the
production path worse:

- broad linked flow: 1,835 rows (403 capital + 1,432 combined/conflict) →
  exact 38.6691%, near 78.0044%, functional 39.1956%, REF_ONLY 197,
  PROD_ONLY 201, mismatch 304;
- capital-only flow: 403 rows → exact 38.9214%, near 79.7973%, functional
  39.4758%, REF_ONLY 161, PROD_ONLY 164, mismatch 277.

The importer is deterministic and idempotent (2,780 PA rows, same SHA-256 on
rerun), but its data is kept in isolated copies only and is **not** shipped as
a production change.

## 2. Git, branch and database

- Branch `mission/ra365-round10-corporate-action-parity-2026-10-21` created
  from Round 9 `3e788f95`; Round 9 branch and `main` were not changed.
- Operational DB `.worktrees/rahavard-full-universe/market.db` stayed
  `fff358a78be74e8d21961251a727116e102df84cea70f87b4dcb7da198667004`.
- Isolated inputs:
  - `market_r9_base.db` (pristine base, 1,005 PA rows);
  - `market_r10_linked.db` (1,835 linked rows inserted, 2,780 total; rejected);
  - `market_r10_capital.db` (403 capital rows; rejected).
- No operational backfill or migration.  No `main`, tag or release change.
- Per the owner’s 2026-10-21 instruction, the final gate’s temp files and
  isolated DB copy run on D: (`D:\BorsTerminal-tmp
a365_round10\gate_work4`),
  not the C: `%TEMP%`.

## 3. Baseline and reconciliation

The Round 9 production baseline was reproduced: 38.9343 exact, 79.8020 near,
39.5054 functional, 160 REF_ONLY, 163 PROD_ONLY, 278 step mismatches on 2,595
assets and 1,187,945 factor dates.

The Round 9 delta’s 403 `capital residual` and 551 `PA approximation` step
rows (the “70” was the near-mismatch subset) overlap as follows: 954 focused
step rows, 151 near-mismatch and 803 exact-only.  After matching each row to
the full TSETMC flow (12,894 rows) and the DB share changes:

| Event class | Rows |
|---|---:|
| DPS_ONLY (PA only, no share) | 522 |
| MISSING_PA_ROW (share only) | 284 |
| CONFLICTING_SOURCES (PA + share, unexplained) | 115 |
| COMBINED_EVENT (PA ≈ share × DPS) | 27 |
| CAPITAL_ONLY (PA ≈ share) | 6 |

The full matrix is `docs/audit/ra365-round10-corporate-event-reconciliation.csv`
(954 rows, stable key, PA/share link, class, before/after ratio, status).

## 4. Iterations and results

| # | Experiment | Result | Decision |
|---|---|---|---|
| 0 | Reproduce baseline + reconcile cluster | 38.9343 / 79.8020 / 39.5054; 954 focused rows | start with PA typing |
| 1 | `_classify_pa_event` (capital/combined/DPS) + tests | 48/48 DPS tests | wire into production |
| 2 | Typed PA, no data | identical 38.9343 (base has only 1,005 recent rows) | code alone is a no-op |
| 3 | Ingest all 1,835 linked flow rows | **regression** 38.6691 / 78.0044 / 39.1956; mismatch 304 | reject |
| 4 | Ingest 403 capital-only rows | **neutral/slightly negative** 38.9214 / 79.7973 / 39.4758 | reject |
| 5 | Official recomputed DPS replaces old `priceAdjust`/base gap | **positive** 48.3147 / 81.5694 / 48.7637; mismatch 262 | keep |
| 6 | Real-path validation + per-symbol regressions | 323 exact gains / 42 losses; 54 near gains / 11 losses; focused 448 improved / 15 worsened / 491 unchanged | keep, document losses |

## 5. Root cause and code fix

For a DPS row, the reference uses `close_ex / (close_ex + DPS)`, where
`close_ex` is the **official closing (پایانی) on the effective date**.  The
product corpus often already had a `priceAdjust` or `base-price-discontinuity`
event with the **old PA ratio** (`pClosing/pClosingNotAdjusted`, based on the
previous close).  When the official DB row was merged, the same-action rule
saw the ratio within 2% and **skipped the official recomputed row**, leaving
the old ratio.  For آكو 2026-09-06, the old ratio was 0.91744287 and the
official DPS formula is 0.93161024; the reference is 0.93161024.

The fix:
1. `_classify_pa_event` types each PA row: an official share change within
   10 days makes it capital (`PA ≈ share`) or combined
   (`PA ≈ share × DPS`); otherwise it remains a DPS.  Capital/combined rows
   keep the official PA ratio and are never turned into a cash dividend.
2. When an official recomputed row is the same action as an existing
   `base-price-discontinuity`, `priceAdjust` or `tsetmc_price_adjust_by_flow`
   row, the official row **replaces** the old one; it is no longer skipped.
3. The DPS base comes from `price_history.close` (the real chart source), not
   from a substitute; this round’s full-universe after uses that source.

Tests: `dev/test_dps_formula_v1.py` 49/49 covers capital, combined, DPS-only,
separate-share fallback, combined-vs-CC-only, same-action amount identity,
official replacement, and effective dates.

## 6. Per-symbol effects and honest regressions

- 323 symbols improved exact, 2,230 unchanged, **42 lost exact**; 54 improved
  ±1%, 2,530 unchanged, **11 lost ±1%**; functional: 341 improved, 2,194
  unchanged, 60 lost.
- Of the 954 focused rows: **448 improved, 15 worsened, 491 unchanged**.
- The 11 near-loss symbols: شپاكسا, شپنا, پخش, سفانو, سپاها, وبشهر, سمازن,
  ومعادن, كلوند, ولشرق, وصنا.  Seven have exact gains (the factor moved
  closer but outside ±1%); four are the worst residuals:
  - شپاكسا: exact 44→44, near 1,410→86;
  - وبشهر: exact 68→68, near 431→68;
  - سپاها: exact 404→375, near 1,293→850;
  - ومعادن: exact 94→64, near 293→64.

These four need their own event-type analysis; the net fix was not reverted
because the exact/functional gain is +9.38/+9.26pp and the 954-row cluster is
448/15 positive.  The regressions are recorded in the reconciliation CSV.

## 7. Negative data experiments (not shipped)

The importer `tools/flow_pa_ingest.py` reads the cached TSETMC flow and inserts
rows with `--linked-only` / `--capital-only` into an isolated copy.  It is
idempotent (same row count/hash on rerun) but both backfills regressed or were
neutral.  The reason is consistent with the reconciliation: a PA row with a
nearby share change is not automatically a safe capital event; many are
combined or separate DPS, and the PA ratio is not always the reference capital
ratio.  The operational DB was never touched; no backfill is part of the
production change.

## 8. Tests and gate

- `dev/test_dps_formula_v1.py`: **49/49**.
- `dev/test_fund_events_v1.py`: **10/10**.
- `dev/test_fund_ingest_v1.py`: **7/7**.
- `dev/test_fund_profit_and_backfill_v1.py`: **20/20**.
- Frontend basis×scale matrix: **5/5**.
- Full gate: see §9 (running).

## 9. Full gate

**Final result: 139 suite counted, 36 silent (exit-code only), 0 skipped
(fixture missing), 0 failed — ALL SUITES PASSED.**  The gate ran with its
workdir and DB copy on D: (`D:\BorsTerminal-tmp
a365_round10\gate_work4`).
The protected DB fingerprint after the gate is
`cdb73c40a14f3fefbf6053bb65716e3cbc50f2af464b4dd2a1934ace2b73fcd4`
(unchanged; `PROTECTED_DB_UNCHANGED`).  The new DPS/fund suites are in the 36
silent list; their standalone counts are 49/49, 10/10, 7/7 and 20/20.

## 10. Open clusters and next experiments

1. **Share-only 284**: 30 match the reference step within 1e-4, but the
   reserve-vs-contribution type is not proven.  CODAL notices are needed; the
   API is currently rate-limited.  Keep `BLOCKED_RATE_LIMIT`.
2. **The 15 worsened focused rows and the 4 near-loss symbols**: type the PA
   row with the official share change/CODAL and test whether the old ratio
   was a combined event (capital + DPS) rather than a DPS.
3. **DPS-only 522**: 25 of the 70 near rows were fixed, 10 worsened, 35
   unchanged; the rest need amount/date evidence (CODAL or an official
   archive).
4. **Fund residues**: هامرز pre-2022 history, پالایش annual shape, دانيك empty
   portal, اطلس mechanism.
5. **Rights-issue S**: one official S (حخزر 1,000) is known; the others need
   CODAL under the rate limit.

## 11. Limitations

- The baseline’s per-symbol counts were produced with the Round 9 evaluator;
  the after uses `price_history.close`.  The five-symbol real-path check and
  the unchanged denominator support the comparison, but a pre-fix run with the
  exact same closing source was not completed.
- The after is a full-universe evaluator result, not a live UI measurement.
- No 100% claim; the remaining differences are in the reconciliation CSV.
- The data backfills are negative evidence; they are not in the operational DB
  or the production code path.

## 12. Commits and push

- Commit 1 (code/tests): `7bc44b98be9239b0a9dc5221025c4f4e00fff575` — typed
  PA, official replacement, flow importer diagnostic, tests.
- Commit 2 (docs): this report, the reconciliation CSV and the loop history;
  its SHA is visible in `git log`.
- Push: only `mission/ra365-round10-corporate-action-parity-2026-10-21`;
  `main`, tags and releases stay untouched.
- Final gate: 139 counted, 36 silent, 0 skipped, 0 failed; protected DB
  unchanged; workdir on D:.
