# Round 9 — RA365 Parity Convergence (iteration log and measured state)

Date: 2026-10-21
Branch: `mission/ra365-round9-parity-convergence-2026-10-21`
Base: `ee54dfd6d37a5073c247e8588149115106988526` (Round 8)
Status: **PARTIAL — measurement corrected, several root causes fixed, one
DPS-backfill experiment is mixed.** No 100% claim.

## 1. Executive summary

Round 9 started by reproducing the Round 8 numbers and then checking whether
they were **production-path** numbers. They were not: the Round 8 C4 runner
patched existing product events in memory, but it did not add official DB
events. The production chart path (`api.chart._canonical_adjustment`) adds
fund and price-adjust rows, so its true parity is lower.

| Measurement | Factor exact | Factor ±1% | Functional | Normalized exact | Normalized ±1% |
|---|---:|---:|---:|---:|---:|
| Round 8 reported C4 harness | 50.8008% | 86.8274% | 51.6810% | 41.3119% | 82.4241% |
| **Round 9 production baseline** | **38.9343%** | **79.8020%** | **39.5054%** | **41.0532%** | **82.0007%** |
| Round 9 production + 52 DPS rows | 38.9204% | 79.7844% | 39.5157% | 41.3197% | 82.0775% |

The production baseline denominators are 462,518 / 1,187,945 exact dates,
948,004 near dates and 1,877,208 / 4,751,780 functional fields on 2,595
assets. The C4 harness measured 2,965 assets and a different denominator; the
two are not directly interchangeable. The Round 8 report is not retracted —
its C4 run is reproducible — but it must be read as a **harness** result, not
as the production chart path.

Round 9 independently found and fixed four root causes:

1. **Combined DPS + capital double-count**: a base gap that already contains
   `DPS × capital` was followed by a separate DPS. The merge now tests the
   combined hypothesis against the official share-change ratio and suppresses
   only the DPS already contained (حخزر 2026; بورس 2026 stays two events).
2. **Same-action tolerance with amount identity**: two official rows for the
   same DPS were rejected only within 0.1%; شسپا's two ratios differ by 1.44%
   (0.873257 vs 0.886040). The tolerance is now 2%, but it also requires the
   per-share amounts to match within 2% when both rows carry them. This keeps
   a fund DPS of 171 and a priceAdjust DPS of 5 one day apart as two events,
   while collapsing پالایش's two 18,540 rows (0.11% apart). A 24% capital
   event is still distinct.
3. **Effective dates across suspensions**: a base gap on 2023-06-24 and an
   official DPS mapped to 2023-07-08 were 14 days apart with no candle
   between; every event date now snaps to its first effective candle before
   merging.
4. **Fund residual rows**: دانيك and پالایش had two official rows for one
   action (0.35% and 0.11% apart); the same-action rule now removes the
   duplicate. هامرز's constant ~5.15% offset was diagnosed as a pre-2022
   history gap, not a formula error.

The 52-row DPS backfill is **mixed**: normalized exact +0.2665pp, normalized
±1% +0.0768pp, functional +0.0103pp, step mismatch 278→276, but absolute exact
−0.0139pp and absolute ±1% −0.0176pp. The shape improves while a few absolute
anchors move; this is reported, not hidden. The backfill is confined to the
isolated DB and is not claimed as an aggregate win.

## 2. Git, branch and database

- Branch `mission/ra365-round9-parity-convergence-2026-10-21` created from
  Round 8 `ee54dfd6`; Round 8 branch and `main` unchanged.
- Operational DB `.worktrees/rahavard-full-universe/market.db` stayed
  `fff358a78be74e8d21961251a727116e102df84cea70f87b4dcb7da198667004`
  (logical `cdb73c40…3fcd4`).
- Isolated copies:
  - `market_r9_base.db`: SHA-256 `e13c061fe3c27e2d737c72160d4c12f91719e552db8d1deb280e32350eb6e11a`
    (Round 8 fund events, no Round 9 DPS backfill).
  - `market_fundtest2.db`: same base + 52 official DPS rows; after the backfill.
- No operational DB backfill, migration or test write was performed.
- `main`, tags and releases were not changed. Push status is recorded in §10
  after the final gate.

## 3. Baseline reproduction

The Round 8 C4 run was reproduced exactly on the fixed v4 inputs:
50.8008 exact, 86.8274 near, 51.6810 functional, 41.3119 normalized exact,
82.4241 normalized ±1%, REF_ONLY 138, PROD_ONLY 139, step pairs 6,378,
step mismatch 217. The four input hashes are unchanged from Round 8.

The production-path baseline was then measured with the same corpus and a
preloaded DB (no per-symbol DB latency): 2,595 assets with a product record,
1,187,945 common factor dates, 462,518 exact (38.9343%), 948,004 near
(79.8020%), 1,877,208/4,751,780 functional (39.5054%), 160 REF_ONLY, 163
PROD_ONLY, 6,356 step pairs, 278 step mismatches, 1,845 missing product
candles and 2,170 missing reference candles. The difference from C4 is the
production path's added official DB events and the 2,595-vs-2,965 measured
population; it is a measurement correction, not a changed denominator inside
one metric.

## 4. Iterations performed

The full iteration ledger is `docs/audit/ra365-round9-loop-history.jsonl`.
Nine iterations were executed:

| # | Hypothesis | Result |
|---|---|---|
| 0 | C4 baseline reproducible | Exact reproduction |
| 1 | C4 = production | **No**; production is 38.9343% exact / 79.8020% near |
| 2 | CODAL AGM/rights notices accessible | Yes; حخزر 6300/2170, سپاها 2395/1380, S=1,000 for the 1402 rights issue; rate-limited after 2 symbols |
| 3 | TSETMC flow has full history | Yes; 12,894 rows 2008–2026 vs 1,005 in the DB |
| 4 | Marks-typed DPS can be backfilled | 52 DPS rows; پخش 2023 rejected (PA 758 vs marks 1,200) |
| 5 | Combined DPS+CC double-count | Fixed; حخزر 2026 single combined gap |
| 6 | Same-action rows can differ >0.1% | Fixed at 2%; شسپا, دانيك, پالایش |
| 7 | Event effective date across suspension | Fixed; every event snaps to the first candle |
| 8 | 52-row DPS backfill improves full universe | Mixed: shape +0.27pp, absolute exact −0.014pp |
| 9 | Chart basis/scale without owner login | Isolated Vitest 5/5; live UI remains UNVERIFIED |

## 5. Official DPS, rights issue and funds

### 5.1 CODAL (official)

The official search API is `https://search.codal.ir/api/search/v2/q` with
Jalali dates. The following were parsed from `Decision.aspx` letters:

- حخزر AGM 1401: **DPS 6,300**; AGM 1402: **DPS 2,170**.
- سپاها AGM 1402: **DPS 2,395**; AGM 1403: **DPS 1,380**.
- حخزر rights issue (1402/12/01): capital 1,080,000 → 3,600,000 million
  rials; 30,386,341 shares at **S = 1,000 rials** for public subscription.
- The search API returned HTTP 429 after the first two symbols. No captcha or
  rate limit was bypassed; the remaining symbols are `BLOCKED_RATE_LIMIT`.

### 5.2 Rights-issue formula

`price_ratio = pv/nw + (1−pv/nw) × (cp/100) × (S/P)`.

For حخزر 2023-10-15: `pv/nw = 0.30`, `S = 1,000`, reference ratio 0.314056;
the formula gives 0.314056 at `P = 49,800`. The nominal last close before the
suspension was 48,000, so `P = 49,800` is an **implied base**, not yet an
independent official observation. Status: **PARTIAL** — S official, P not
independently confirmed. The other contribution events (پخش, وبشهر, كلوند)
remain `UNVERIFIED` because their S notices were not obtained under the rate
limit.

### 5.3 Funds

- **هامز**: product/reference ratio is a constant 1.0515 for the first common
  date, falling to 1.0 at the end; the norm-near is 63.7% while the absolute
  near is 28%. This is a **pre-2022 history gap**, not a 2.5% formula. The
  remaining 2025 jumps (2.47%, 2.31%) need the missing pre-history and event
  amounts; `PARTIAL`.
- **پالایش**: duplicate official rows (0.11% apart) caused a 13.1% step; the
  same-action fix removes the duplicate. The annual schedule and the
  pre-2020 offset remain `PARTIAL`.
- **دانيك**: duplicate 2026-08-24 rows (0.35% apart) caused a 29% step; fixed
  by the same-action rule. The official portal is empty for earlier history;
  `BLOCKED`.
- **اطلس**: the 2021 8.7%/8.4%/8.1% reference steps do not correspond to the
  official no-distribution portal; a different mechanism; `PARTIAL`.
- **ارزش مسكن**: two official rows; 2.5%/0.9% jumps remain; `PARTIAL`.

Fund REF_ONLY remains 10 (اطلس 3, دانيك 3, ارزش مسكن 2, هامرز 2).

## 6. Full-universe before/after (production path)

| Metric | Before (base DB) | After (52 DPS rows) | Δ |
|---|---:|---:|---:|
| Factor exact | 38.9343% (462,518/1,187,945) | 38.9204% (462,353/1,187,945) | −0.0139pp |
| Factor ±1% | 79.8020% (948,004/1,187,945) | 79.7844% (947,795/1,187,945) | −0.0176pp |
| Functional OHLC | 39.5054% (1,877,208/4,751,780) | 39.5157% (1,877,701/4,751,780) | +0.0103pp |
| Normalized exact | 41.0532% (487,690/1,187,945) | 41.3197% (490,855/1,187,945) | +0.2665pp |
| Normalized ±1% | 82.0007% (974,123/1,187,945) | 82.0775% (975,035/1,187,945) | +0.0768pp |
| Raw exact | 97.4727% | 97.4727% | 0 |
| REF_ONLY / PROD_ONLY | 160 / 163 | 160 / 163 | 0 |
| Step pairs | 6,356 | 6,356 | 0 |
| Step mismatch | 278 | 276 | −2 |
| Missing product / reference | 1,845 / 2,170 | 1,845 / 2,170 | 0 |

Per-symbol effects of the 52 rows (only these seven changed):

| Symbol | Factor exact | Factor ±1% | Functional |
|---|---:|---:|---:|
| حخزر | 59 → 59 | 1,499 → 1,499 (100%) | −5 |
| سپاها | 404 → 154 | 1,293 → **1,524** | −998 |
| شسپا | 59 → 59 | 1,078 → 407 | −1 |
| كلر | 65 → 65 | 1,258 → **1,489** | 0 |
| كلوند | 60 → **145** | 1,491 → 1,491 | **+1,497** |
| وبشهر | 68 → 68 | 431 → 431 | 0 |
| پخش | 78 → 78 | 1,503 → 1,503 | 0 |

The exact loss in سپاها and the near loss in شسپا are **exposed-compensation /
anchor** effects: their normalized shape improved (شسپا norm-near 1,247→1,425),
while an absolute offset moved outside ±1% or exact. They are not hidden.

## 7. Rights, funds and code fixes — tests

- `dev/test_dps_formula_v1.py`: **40/40** — DPS cases, marks cases, reserve CC,
  same-action duplicates (1%, 1.44%), different amounts (171 vs 5), matching
  amounts (18,540), combined-vs-CC-only, effective dates.
- `dev/test_fund_events_v1.py`: **10/10**.
- `dev/test_fund_ingest_v1.py`: **7/7**.
- `dev/test_fund_profit_and_backfill_v1.py`: **20/20** (the gate caught the
  171-vs-5 conflation; fixed and re-verified standalone).
- Frontend `src/__tests__/technical-basis-scale-matrix.spec.tsx`: **5/5** —
  the four basis×scale combinations, volume/timestamps unchanged; pixel/UI
  behavior remains `LIVE_UI_UNVERIFIED`.
- Full gate: see §9 (running after the 171-vs-5 fix).

## 8. Chart audit (research only)

- Matrix: `docs/CHART-MODES-FEATURE-MATRIX-2026-10-21.md`.
- Prototype: `docs/prototypes/chart-mode-controls-2026-10-21.html`.
- New isolated test proves the four combinations at the data/axis layer:
  raw/combined × linear/log. It does not prove pixel behavior, drawing
  conversion or reload persistence; those are `LIVE_UI_UNVERIFIED`.
- No chart UI/engine code was changed in Round 9. The `api/chart.py` changes
  are event-chain correctness fixes, not a chart redesign.

## 9. Tests and final gate

**Final result: 139 suite counted, 36 silent (exit-code only), 0 skipped
(fixture missing), 0 failed — ALL SUITES PASSED.** The new DPS/fund suites are
in the 36 silent list because they print custom counts; their standalone
results are 40/40 (DPS), 10/10 (fund events), 7/7 (importer) and 20/20
(fund profit + backfill). The gate caught the 171-vs-5 amount conflation; it
was fixed and the full gate was rerun. Protected DB logical fingerprint after
the gate: `cdb73c40a14f3fefbf6053bb65716e3cbc50f2af464b4dd2a1934ace2b73fcd4`
(unchanged; `PROTECTED_DB_UNCHANGED`).

## 10. Commits and push

- Commit 1 (code/tests): `5deddd4e8285720f430e4a418173c465a72db008` — combined
  DPS/capital suppression, amount-aware same-action, effective dates, tests.
- Commit 2 (docs): the commit adding this report, the delta CSV and the loop
  history; its SHA is visible in `git log`.
- Push: only `mission/ra365-round9-parity-convergence-2026-10-21`; `main`,
  tags and releases stay untouched.
- Final gate: 139 counted, 36 silent, 0 skipped, 0 failed; protected DB
  unchanged.

## 10.1 Delta composition (5,275 rows)

- Step near-mismatch (>1%): **278**; exact-only mismatch (5e-4–1%): **2,401**.
- Cause candidates in `ra365-round9-parity-delta.csv`:
  - 1,641 step mismatches with no DB event within 10 days (source/rounding/
    reference gap, not yet a proven event);
  - 551 official PA approximation (DPS/CC ratio not exact);
  - 403 capital-event residual;
  - 84 fund residual;
  - 53 tiny reference steps (`TINY_REF_STEP`);
  - 35 official event present but not applied; 72 no official event;
  - the rest are per-symbol factor/functional deficits and PROD_ONLY rows.
- Every row has a stable key, symbol/asset id, date/kind, before value, after
  value (where changed), cause status and evidence.
- The 278 near-mismatches split as: 123 `NO_DB_EVENT_NEAR`, 81
  `CAPITAL_EVENT_RESIDUAL`, 70 `OFFICIAL_PA_APPROXIMATION`, 4
  `FUND_RESIDUAL`. Top symbols: كگل 6, اعتلا 5, وهامون 5, شتوكا 4,
  پكوير 4, then many with 3.
- A share-change merge diagnostic found only 31 of the 403 capital rows match
  the reference step within 1e-4; most capital steps also contain a DPS or a
  mixed rights component. This is not a one-line merge; it needs the official
  S/P decomposition per event.

## 11. Open clusters and next experiments (in priority order)

1. **Type every `price_adjust_events` row (top cluster)**: the production path
   currently treats any row with `pNA > pC` as a DPS. If a share change
   matches its ratio, it is a capital event and must use the official PA ratio
   (or `pv/nw` for reserve-only); if both a DPS and a share change exist, use
   one combined event; if neither is proven, keep it `UNVERIFIED`. The delta
   has 403 capital residuals and 70 PA approximations; this is the single
   largest explainable cluster after the 123 no-event rows.
2. **Official share-change merge**: `share_change_events` has 3,490 rows from
   2008; use reserve `pv/nw` for capital-only events and the official PA ratio
   for mixed events, with duplicate/type tests. Only 31 of the 403 capital
   rows match the reference step within 1e-4 alone, so the typed PA row is
   required before a merge can help.
3. **Full DPS classification/backfill**: CODAL per-symbol once the 429 resets,
   or marks-typed official PA rows with provenance; do not ship marks-typed
   rows as official.
4. **Fund residuals**: هامرز pre-2022 archive, پالایش annual shape, دانيك
   empty portal, اطلس mechanism, ارزش مسكن jumps.
5. **Production REF_ONLY 160 / PROD_ONLY 163 / mismatch 278**: classify with
   the delta CSV; many are production-only base gaps or reference rounding.
6. **Rights-issue S** for پخش/وبشهر/كلوند/حخزر-1403: official notices under
   the rate limit.
7. **Absolute anchor policy** for DPS backfills: decide whether to compare on
   normalized factors for assets with pre-history gaps, without changing the
   metric for assets that have full history.

## 12. Honest limitations

- The C4 harness number is not the production path; the production baseline
  must be used for future rounds.
- 52 DPS rows are a small, marks-typed subset; the aggregate is mixed.
- CODAL is rate-limited; no bypass.
- The rights `P` is implied; S is official only for one event.
- Interactive chart behavior is not verified; only isolated Vitest.
- No 100% claim. The remaining differences are counted in
  `docs/audit/ra365-round9-parity-delta.csv` (5,275 rows).
