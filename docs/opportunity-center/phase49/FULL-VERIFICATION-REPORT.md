# Phase 4.9.1 - Full verification report

- Branch: `mission/phase49-full-verification-python-ci-2026-11-10`
- Mission base: `f7fc8e8a` (design spec section 1); baseline snapshot was taken at HEAD `b43b1a66`
- Working HEAD when this report was assembled: `19d3a885feb6f463ae36907caf43acd07092df7a`
- C7 local-gate revision: HEAD `748d8519` (evidence measured on tree `c8fa99a4`)
- Final CI commit: `ea179e3c` - **three workflows green**: `guards` 9/9 jobs success
  (including `zero-python-runtime` and the installer runtime proof), `python-tooling`
  `ALL SUITES PASSED` (36 suites), `python-legacy` report-only success with 30 visible
  legacy failures; run ids and per-job links are in `CI-FINAL-RESULTS.json`
- Verdict: **`PHASE49_PARTIAL_WITH_EXPLICIT_BLOCKERS`**

`PHASE49_PARTIAL_WITH_EXPLICIT_BLOCKERS` is the mission's verdict string. The design spec's
short form is `PARTIAL_WITH_EXPLICIT_BLOCKERS`; it names the same verdict, and the mission
string is kept here because it is the string the acceptance table and `stage11_deliverables.py`
check.

This report is written from evidence that already exists in the repository. The final CI
record was measured on `ea179e3c` and is linked by run id and job URL in
`CI-FINAL-RESULTS.json`; no run or job result is inferred. It does not claim that any
unverified row became verified because a label changed. Where a number is not measured, the
row says `NOT_MEASURED`.

## 1. Verdict and why

`PHASE49_COMPLETE_DATA_READY` is not claimed. The verification pipeline ran end to end and
produced a materially better, provenance-complete Seed Candidate, but several acceptance
criteria remain unresolved on evidence that this round does not have.

The verdict carries these blockers:

1. **Capture left 339 of 1,097 planned symbols unmapped.** The capture plan covers 1,097
   keys (1,130 raw spellings); 758 had an asset id and were captured, 339 did not and carry
   `NO_ASSET_ID` ([S4], [S2]).
2. **The verified group is not independently verified.** 1,137 of the 5,983 `VERIFIED_*`
   step rows have an independent witness; the other 4,846 are `VERIFIED_REFERENCE` rows whose
   ratio came from the same reference index, so they confirm the source, not the step
   ([S11]).
3. **1,358 pack steps were unverified at baseline; 1,179 still are.** The full-reference
   re-review leaves 1,179 of the 1,358 without a verified status: 916
   `INSUFFICIENT_EVIDENCE`, 118 `CONFLICT_RATIO`, 136 `PARTIAL_REFERENCE`, 5
   `PARTIAL_OFFICIAL` and 4 `RECONSTRUCTED_AUDITED`. The other 179 now carry a `VERIFIED_*`
   status: 45 `VERIFIED_MULTI_SOURCE` + 56 `VERIFIED_OFFICIAL` (101 independent) and 78
   `VERIFIED_REFERENCE` (reference-confirmed, not independent). `1,179 + 179 = 1,358`.
   Across all 8,308 rows the conflict totals are 223 `CONFLICT_RATIO`, 6
   `CONFLICT_DUPLICATE`, and 28 `INVALID_DROPPED` ([S3]).
4. **5,185 history symbols still have no reference window and no pack step.** Of the
   5,188 rows in the baseline validity defect, 3 acquired a full reference window (2 became
   `VERIFIED_NO_APPLICABLE_EVENT`, 1 stayed `INSUFFICIENT_EVIDENCE`); 5,185 have none
   ([S11], [S10]).
5. **The symbol ledger still reports 6,000 unverified history symbols** (5,910
   `INSUFFICIENT_EVIDENCE` + 90 `CONFLICT`), 1,468 with no instruments row, 444 halted and
   339 unmapped ([S4], [L2]).
6. **53,176 anomaly events on the new Seed are unresolved source gaps**, 50,489 pre-existing
   and 2,687 introduced by the 33,145 backfilled rows ([S5], [S6]).
7. **306 legacy invalid OHLC rows remain**: 12 with `open=0` and a valid shadow, 294 with
   `open=high=low=0` and a positive close outside that zero shadow. They are pre-existing
   `legacy-unknown` rows and none came from the new backfill ([S5], [S6]).
8. **Four new backfilled rows are unadjustable by the product chain**: شنفت 1995-07-26,
   طلا 2026-11-02, تپسي 2026-11-10 and غشان 2026-11-10. The reference type7 series shows
   the split, but the pack has no factor step at the boundary and no official event exists
   ([S6]).
9. **Three backfilled boundaries are `CORPORATE_ACTION_MISSING`** (شنفت 2014-06-17 and
   2021-10-26, لخزر 2023-02-20). The adjustment chain covers them; the boundary event row is
   absent. Non-blocking but recorded ([S6]).
10. **The Seed release gate blocks.** `seed_manifest.reference_derived_rows` = 105,367, so
    `scripts/check_seed_release.py` returns `SEED_RELEASE_BLOCKED` without owner approval
    for reference redistribution ([M1], [S10]).
11. **The data lane and the frontend gates are now measured in CI.** C7 installed
    `frontend-v2/node_modules` with `npm ci` and ran `tsc -b`, `vite build` and
    `npx vitest run` (verbose reporter, explicit 20 s per-test bound; the evidence file
    records the deviation): all pass, with 106/106 test files and 865/865 tests, including
    the chart-label assertion ([S19], commit `748d8519`). C8 then measured the data lane
    twice: locally with a FastAPI-capable venv (36 suites, `ALL SUITES PASSED`; the two
    skips are the named gitignored fixtures) and in CI on `ea179e3c`, where
    `python-tooling` also reports `ALL SUITES PASSED`. The earlier C7 local run's five
    FastAPI failures were environmental and are now resolved by measurement, not by a
    label change ([S19], `CI-FINAL-RESULTS.json`).
12. **The legacy Python lane stays visibly red by design.** On `ea179e3c`,
    `python-legacy` is report-only (`continue-on-error`): 30 of the 210 legacy suites fail
    and their job is marked `failure`, while the workflow run itself is green. (The runner
    reports 211 entries because it also counts the fixture-preparation step.) B2 moved from
    the blocking data lane to this lane in C8 because the retired Python mstat engine now
    emits legacy-only panels/fields that the Go port intentionally does not (regenerating
    the shared goldens breaks five Go tests); the Go tests that read the same fixture and
    goldens remain the live gate. This is an explicit divergence blocker, not a silent
    skip (`PYTHON-CI-MIGRATION.md`, `CI-FINAL-RESULTS.json`).

## 2. Run identity and inputs

| Item | Value | Source |
| --- | --- | --- |
| Branch | `mission/phase49-full-verification-python-ci-2026-11-10` | this tree |
| Mission base | `f7fc8e8a` | design spec section 1 |
| Baseline snapshot HEAD | `b43b1a66` (snapshot-time HEAD, not the commit that contains the file) | [S1] |
| Working HEAD | `19d3a885feb6f463ae36907caf43acd07092df7a` | `git rev-parse HEAD` |
| C5 measured tree | `fd8a7dd4` (evidence JSON `commit` fields) | [S8], [S9] |
| C7 local gates | measured on tree `c8fa99a4`, evidence committed in `748d8519` | [S19] |
| Final CI commit | `ea179e3c69aba0c7c9bc9648bfe480d214a790a7` | `CI-FINAL-RESULTS.json` |
| Correction pack | `ra365-phase49-rebuild-full-v2`, 8,280 steps, 951 symbols, `as_of` 2026-10-25 | [S1], [M1] |
| Pack manifest SHA-256 | `458cd5ebfdcc7a752c7eba9839eba75c13db1efefd4fcf572b41095ef936578c` | [S1], [S8], [M1] |
| Pack factors SHA-256 | `aa8e13fc2d172c3e3355e86bba1bd505b5070269d0a47baf0c3c2d59784ceb24` | [S1], [S8], [M1] |
| Pack raw OHLC SHA-256 | `b02e8859db53081a2b9f69c1a28cd513b54d968b53944363bfbd7932a399975a` | [S1], [S8], [M1] |
| Baseline Seed DB | `_audit/phase49-finalization/seed/market.db`, 511,139 rows, 6,103 symbols, SHA-256 `2ee662980ef0dcebbb06b0679f3c0e54282984a060f3b9da62e02f0b389deffc` | [S1] |
| Baseline validity | 35 `verified`, 880 `reconstructed_verified`, 5,188 `unverified` | [S1] |
| New Seed DB | 544,284 rows, 6,103 symbols, SHA-256 `57118e8fc99ff69c9e9812002f1d72571f357c23287fc1880a2f00b8292bbcb5` | [S10], [M1] |
| Reference index | 759 symbols, 2,101,752 factor days, 13,921 changes in 745 symbols, SHA-256 `83544012448fc19100e7b140dbcfc2e4d27eca317f667204c343f810acc92e1c` | [S11], [R1] |
| Reference bars | `captures/bars-all.ndjson.gz`, 5,240,964 merged bars, SHA-256 `272336c036d647ed7b2090853c84c3a2d3da6126a0bfae60e987198169b3b14a` | [S2], [S8] |
| Backfill runs | `phase49-c3fix-six-2026-11-11`, `phase49-c3fix-fresh-2026-11-11`, plus recorded reruns | [S13], [S14], [S15] |
| Seed build | `2026-11-11T02:57:57Z`, integrity `ok`, round-trip `true` | [M1], [S10] |

## 3. Evidence index

Every citation `[S#]` or `[L#]` below resolves to this table. SHA-256 is of the exact file
read for this report. A number that is derived from two cited files is marked in its row.

| Key | Path | SHA-256 |
| --- | --- | --- |
| S1 | `_audit/phase49-full-verification/evidence/baseline.json` | `46c7e340d9f6f210e47d7596efaff471f36dcd16e84c8e94c11d41e8ec4c4300` |
| S2 | `_audit/phase49-full-verification/evidence/capture-summary.json` | `6cbeb62811f42d143a9d6b5c10324e2eae57b6914e8f875a3ee0e50d6154da8b` |
| S3 | `_audit/phase49-full-verification/evidence/step-ledger-counts.json` | `e9d1077a2b2ea6cd6110e75ca2d8d42395bf536e7f1ac1bec5dfc4c142cf47aa` |
| S4 | `_audit/phase49-full-verification/evidence/symbol-ledger-counts.json` | `a7e21d45d8a86b1d479ac47ebf291a9680566f2677db21ade5ccefc9a80e4b47` |
| S5 | `_audit/phase49-full-verification/evidence/anomaly-counts.json` | `a9ce48b6f1e9e844a40a18a2ec63cf4868ec26d4979a3f6fe07c5fdaea8aa047` |
| S6 | `_audit/phase49-full-verification/evidence/post-backfill-anomalies.json` | `de9ea3a2a24bf971a5f80b0cfd534beea146cfc0117f8204a16fd0f17ec08fa6` |
| S7 | `_audit/phase49-full-verification/evidence/inventory-reconcile.json` | `af35b0968068b8feead3d1c5b3ee1e245e05f3790858b1df0a335f8a7bbca86f` |
| S8 | `_audit/phase49-full-verification/evidence/parity.json` | `38ac4bd1a4b9fceba88e8fc483c0284acbbc32270bb31e73963526ff15793a7d` |
| S9 | `_audit/phase49-full-verification/evidence/product-tests.json` | `5cf31de7613829aa2d92be01cf06718562477f16d618ea1dfdc70903c46a6c9c` |
| S10 | `_audit/phase49-full-verification/evidence/seed-integrity.json` | `59871182a89f13ff9fd81c26fd006bc7a2eefea67bb769b9ebbdede86d5d6f77` |
| S11 | `_audit/phase49-full-verification/evidence/ledger-counts.json` | `a638236db0ddf57d1443e9c450ae4dec9eb3a42414cd0c10b7844b02ca8015c3` |
| S12 | `_audit/phase49-full-verification/evidence/volana-rootcause.json` | `b3673e63157a36515ffc5a094e2fc0fb037f10c5b23d46963b52eb261f58fb3f` |
| S13 | `_audit/phase49-full-verification/evidence/backfill-six.json` | `17cef0316fa79debe27a41c5e2b67bb20fa0a53c2b499175bbeec9a7f2692993` |
| S14 | `_audit/phase49-full-verification/evidence/backfill-fresh.json` | `2ef444e4d39f5aec2ea5abbe3ead1b3399bc8291711a08038017f989c1877925` |
| S15 | `_audit/phase49-full-verification/evidence/backfill-idempotency.json` | `2461dea8f994fb6d30fcad3c72450f8f2077b659df9d511af8e22df14fb4f269` |
| S16 | `_audit/phase49-full-verification/evidence/backfill-price-basis.json` | `2fa944c8509b560f8ef95d397f8e99b3cede6a68f18832a80fc896f4bbd587b6` |
| S17 | `_audit/phase49-full-verification/evidence/backfill-availability.json` | `ce5207435ccfa980875d35dfd18675e58ba5e750eb20d63c9d6eef9ae11e2264` |
| S18 | `_audit/phase49-full-verification/evidence/ci-failures.json` | `39acd64c8e13815980b1f7231a0174a027493594b85da9ac8f12ed1889c87e22` |
| S19 | `_audit/phase49-full-verification/evidence/local-gates.json` | `1a247d0272f3dc65f000c1b97599b6dc4f5e9fd5de130d6f7d9f1b5d112e65f9` |
| S20 | `docs/opportunity-center/phase49/CI-FINAL-RESULTS.json` | `a53f428dd34fb8947c3ee8891673984e66843056c91c1e096ad92ded4e8d6e8e` |
| C1 | `_audit/phase49-full-verification/capture-plan/capture-plan.json` | `7dbe2a62073f73bb5beb38779be075914f8b178f954e7f728490922d9590cfd4` |
| L1 | `docs/opportunity-center/phase49/ADJUSTMENT-EVIDENCE-LEDGER.csv` (8,308 rows + header) | `c0ab45bf60ba8d95fa4f4f33d60d4fa6f465a62c07271053c8ca7781f5114a28` |
| L2 | `docs/opportunity-center/phase49/HISTORY-COVERAGE-LEDGER.csv` (6,103 rows + header) | `c3ad3741daaa55b849fb51aca7cc066ea859d0469de2eb85d82471988a69a650` |
| M1 | `docs/opportunity-center/phase49/FINAL-SEED-MANIFEST.json` | `6a930818b05f3ef180064e7c8c908830bac5a72d89b28111dd43fba9cb859aa7` |
| R1 | `_audit/phase49-full-verification/captures/reference-index-all.json` | `83544012448fc19100e7b140dbcfc2e4d27eca317f667204c343f810acc92e1c` |

## 4. Acceptance criteria

| # | Criterion | Status | Basis |
| ---: | --- | --- | --- |
| 1 | Review all 1,358 baseline-unverified steps | `INSUFFICIENT_EVIDENCE` | All 1,358 carry a ledger status and evidence tier, so none is unreviewed. Outcome: 1,179 remain unverified (916 `INSUFFICIENT_EVIDENCE`, 118 `CONFLICT_RATIO`, 136 `PARTIAL_REFERENCE`, 5 `PARTIAL_OFFICIAL`, 4 `RECONSTRUCTED_AUDITED`) and 179 are now `VERIFIED_*` (45 + 56 independent, 78 reference-confirmed); `1,179 + 179 = 1,358` [S3]. 916 is the dominant status and no label was flipped. |
| 2 | Audit the 6,300 `reconstructed_verified` steps | `PASS_WITH_RESIDUAL` | The audit re-derived all 6,300 pack chains: 6,293 passed, 7 failed; reasons 22 duplicate-date, 1,651 missing-provenance, 2 ratio-out-of-range, 22 symbol-identity (a row can carry more than one reason, so the reason counts do not sum to 1,661) [S3]. The 7 residual rows are listed in section 6.5 with symbol, date, reason and final status; the criterion is not met for those 7 rows. Disclosure: the resulting `VERIFIED_REFERENCE` rows are reference-confirmed, not independent [S11]. |
| 3 | Determine the three Volana steps | `PARTIAL_FACTOR` | Three steps (2020-03-11, 2025-07-20, 2026-05-23) carry B6 assessment `PARTIAL_REFERENCE` at a measured cumulative error of 0.198239% (above 0.100%, below 1.000%); their ledger status stays `RECONSTRUCTED_AUDITED` [S12]. Root causes: a hidden 2019 double count, a dropped 2026-07-15 step, and the absorbed 2026-08-02 ratio [S12]. |
| 4 | Determine the status of the 6,328 no-evidence symbols and reconcile with 6,103 | `PASS` | All 6,103 history symbols carry one of six final statuses [L2]. 6,328 is reproduced exactly as 5,022 history symbols with neither evidence source + 1,306 instruments with no history; with the current pack the same definition gives 6,333 (5,027 + 1,306), a net +5 from 96 added and 8 dropped pack keys [S7]. 5,910 of the 6,103 remain `INSUFFICIENT_EVIDENCE` [S4]. |
| 5 | Review the 5,188 unverified validity rows | `INSUFFICIENT_EVIDENCE` | 3 now have a full reference window (2 `VERIFIED_NO_APPLICABLE_EVENT`, 1 `INSUFFICIENT_EVIDENCE` with `REFERENCE_FACTOR_CHANGES_WITHOUT_STEPS`); 5,185 still have no reference and no pack step; 1,467 of the 5,185 have no instruments row [S11], [S4]. |
| 6 | Backfill the six short-history symbols | `PASS` | All six present in the capture with raw daily bars; 19,540 rows inserted, 0 invalid, full reference date coverage (`missing_ref=0`) [S13], [S17], [S15]. |
| 7 | Determine identity/status of instruments without history and history outside instruments | `INSUFFICIENT_EVIDENCE` | 1,468 history symbols have no instruments row and stay `unresolved_no_instruments` + `SYMBOL_IDENTITY_MISMATCH`; 1,306 named instruments have no history; 3 duplicate instrument keys are reported, 2 inside history [S4], [S7]. The identity is explicitly unresolved, not guessed. |
| 8 | Root-cause important OHLC anomalies and gaps | `PASS` | Every emitted event has a measured root cause or the explicit residual `UNRESOLVED_SOURCE_GAP`; `uncategorized_events=0`, `unexplained_events=0`; each kind matches its independent SQL cross-check [S5]. 53,176 events still need a source this round does not have [S5]. |
| 9 | Settle Python CI and green Production Gates | `PASS` | Final CI on `ea179e3c`: `guards` success with 9/9 jobs (Go vet/ast-arch/unit tests, Go race, Go Windows 2022 + latest, frontend-v2 typecheck/vitest/build, data-integrity production suites, repo hygiene, `zero-python-runtime`, desktop delivery incl. installer runtime proof); `python-tooling` success, `ALL SUITES PASSED` for the 36-suite data lane (20 counted, 14 exit-code-only, 2 named gitignored-fixture skips); `python-legacy` report-only success, with its 30 legacy failures visible on the failed job. B2's move to the legacy lane is an explicit divergence blocker (see 1.12), not a hidden skip. Run ids, URLs and per-job conclusions are in `CI-FINAL-RESULTS.json` [S18], [S20]. |
| 10 | Verify the Seed Candidate for integrity/idempotency/provenance/Go parity | `PASS` | Integrity `ok`, duplicate pairs 0, XZ and gzip round-trips equal the DB SHA, manifest hashes match, 33,145 provenance rows with 0 wrong source/type and 0 changed seed rows, 30/30 engine parity and 12/12 product checks [S10], [S15], [S8], [S9]. Release remains blocked separately by the licensing gate [M1]. |

## 5. Capture scope and coverage

| Measure | Value | Source |
| --- | ---: | --- |
| Capture-plan keys | 1,097 (1,130 raw spellings) | [S4] |
| Asset-map symbols | 828 | [S4] |
| Mapped and captured | 758 | [S4], [S2] |
| Unmapped (`NO_ASSET_ID`) | 339 | [S4] |
| Long-history planned | 854 | [S4] |
| Short-history six | 6 | [S4] |
| Capture batches | 16 | [S2] |
| Symbols captured per batch total | 758 | [S2] |
| Series captured | 3,032 | [S2] |
| Raw/normalized bars captured | 5,240,562 | [S2] |
| Extra 30-symbol capture merged | +402 bars, +1 new symbol (هانیکو) | [S2] |
| Merged bars | 5,240,964 | [S2] |
| Merged symbols | 759 | [S2], [R1] |
| Merged date range | 1991-03-23 to 2026-11-10 | [S2] |
| Bars by resolution | D 4,203,504; W 1,037,440; M 20 | [S2] |
| Bars by type | type0 2,620,482; type7 2,620,482 | [S2] |
| Reference index | 759 symbols; 2,101,752 factor days; 13,921 changes; 745 symbols with a change | [S11], [R1] |
| History symbols with a reference index | 759 of 6,103 | [S4] |
| Pack raw spellings with a reference index | 792 of 951 (83.3%); 756 of 915 keys | [S4] |

Interpretation: the capture did what the plan asked for every symbol that had an asset id.
The 339 unmapped keys are not captured and cannot be validated from the reference; they stay
in the symbol ledger as blockers rather than being silently dropped [S4]. Of the 339, 96 are
normalised keys that also carry unverified pack steps. The 1,358 baseline-unverified pack
steps cover
782 raw pack spellings, which normalise to 754 keys; 658 of those keys have an asset id and
96 do not. Those 96 keys are an explicit reference-coverage blocker, not a mapping success
[C1], [S4].

## 6. Adjustment chain - the step ledger

Source: [L1], 8,308 data rows, 951 raw symbols, 18 columns; counts in [S3].

### 6.1 Pack and ledger

| Measure | Value | Source |
| --- | ---: | --- |
| Pack steps (valid) | 8,280 | [S1], [S3] |
| Pack invalid dropped | 28 | [S1], [S3] |
| Ledger rows | 8,308 | [L1], [S3] |
| Ledger symbols | 951 raw (915 normalised keys, 36 alias spellings) | [S3], [S7] |
| Pre-2020 pack steps | 623 | [S1] |
| Merged factor steps used by the symbol ledger | 8,198 (8,280 - 82 duplicate alias dates) | [S4] |

### 6.2 Status distribution

| Final status | Rows | Source |
| --- | ---: | --- |
| `VERIFIED_REFERENCE` | 4,933 | [S3], [L1] |
| `VERIFIED_MULTI_SOURCE` | 955 | [S3], [L1] |
| `INSUFFICIENT_EVIDENCE` | 916 | [S3], [L1] |
| `RECONSTRUCTED_AUDITED` | 608 | [S3], [L1] |
| `PARTIAL_OFFICIAL` | 408 | [S3], [L1] |
| `CONFLICT_RATIO` | 223 | [S3], [L1] |
| `PARTIAL_REFERENCE` | 136 | [S3], [L1] |
| `VERIFIED_OFFICIAL` | 95 | [S3], [L1] |
| `INVALID_DROPPED` | 28 | [S3], [L1] |
| `CONFLICT_DUPLICATE` | 6 | [S3], [L1] |
| **Total** | **8,308** | [S3], [L1] |

The three `VERIFIED_*` statuses total 5,983. That number must never be reported as 5,983
independently verified rows:

| Component | Rows | Source |
| --- | ---: | --- |
| Independently evidenced | 1,137 = 955 `VERIFIED_MULTI_SOURCE` + 95 `VERIFIED_OFFICIAL` + 87 product-derived `VERIFIED_REFERENCE` | [S11] |
| Reference-derived confirmations | 4,846 (`method=multi_field_step_inference` or `reference-factor-step-v1` with ratio equal to the reference within 1e-12) | [S11] |
| Shifted primary witness | 956 (1-5 day shift); exact-date primary witness 181 | [S11] |
| Ratio-out-of-range but still listed | 2 (زملارد 2025-09-21, غمارگ 2025-10-06) | [S11] |

### 6.3 The 1,358 baseline-unverified pack steps

| Status within the 1,358 | Rows | Source |
| --- | ---: | --- |
| `INSUFFICIENT_EVIDENCE` | 916 | [S3] |
| `CONFLICT_RATIO` | 118 | [S3] |
| `PARTIAL_REFERENCE` | 136 | [S3] |
| `PARTIAL_OFFICIAL` | 5 | [S3] |
| `RECONSTRUCTED_AUDITED` | 4 | [S3] |
| `VERIFIED_MULTI_SOURCE` | 45 | [S3] |
| `VERIFIED_OFFICIAL` | 56 | [S3] |
| `VERIFIED_REFERENCE` | 78 | [S3] |
| **Total** | **1,358** | [S3] |

Of these 1,358 baseline-unverified rows, **1,179 are still unverified** after the full
reference (916 + 118 + 136 + 5 + 4) and **179 are now `VERIFIED_*`** (45 + 56 + 78);
`1,179 + 179 = 1,358`. Only 45 + 56 = 101 of the 179 have a multi-source or official
witness; the 78 `VERIFIED_REFERENCE` rows are reference-derived confirmations, not
independent evidence [S3], [S11]. Separately, the rerun moved 179 steps out of
`INSUFFICIENT_EVIDENCE` (75 to `VERIFIED_REFERENCE`, 100 to `PARTIAL_REFERENCE`, 4 to
`CONFLICT_RATIO`); that outflow is a different set of rows from the 179 currently carrying a
`VERIFIED_*` status and must not be added to it [S11]. The Seed's validity label for these
symbols did not change: they remain part of the 6,000 `unverified` rows [S10].

### 6.4 Volana

Source: [S12], `_audit/phase49-full-verification/evidence/volana-rootcause.json` - the Volana
evidence file for the three steps below.

| Item | Value | Source |
| --- | --- | --- |
| Steps | 3 (2020-03-11, 2025-07-20, 2026-05-23) | [S12] |
| B6 assessment | `PARTIAL_REFERENCE` on all 3 | [S12] |
| Ledger status | `RECONSTRUCTED_AUDITED` on all 3 | [S12] |
| Max cumulative error | 0.198239% on 2016-08-03 | [S12] |
| Per-step ratio error | 0.0 | [S12] |
| Root causes | `HIDDEN_DOUBLE_COUNT_2019`, `DROPPED_2026_07_15`, `CONFLICT_2026_08_02` | [S12] |

The 0.198% is a cumulative chain effect, not a per-step ratio error. The assessment does not
promote the rows, so the ledger status stands. Fixing it requires restoring the dropped
2026-07-15 step and using single-step ratios, which is a pack change, not a ledger relabel
[S12].

### 6.5 The seven failed reconstruction audits

The audit re-derives every pack chain and does not read the reference, so the full-reference
rerun did not change these outcomes: 6,293 of the 6,300 `reconstructed_verified` rows pass
and 7 fail [S3]. The seven rows are listed here so the residual is not hidden behind the
6,293/6,300 aggregate. Criterion 2 is `PASS_WITH_RESIDUAL`: it is not met for these rows.

| Symbol | Date | Audit reason(s) | Final status | Source |
| --- | --- | --- | --- | --- |
| الكتروماد | 2026-07-07 | `duplicate-date`, `symbol-identity` | `CONFLICT_DUPLICATE` | [S3], [L1] |
| الكتروماد | 2026-07-26 | `duplicate-date`, `symbol-identity` | `CONFLICT_DUPLICATE` | [S3], [L1] |
| دبالك | 2025-01-18 | `duplicate-date`, `symbol-identity` | `CONFLICT_DUPLICATE` | [S3], [L1] |
| زملارد | 2025-09-21 | `ratio-out-of-range` | `VERIFIED_REFERENCE` | [S3], [L1] |
| غمارگ | 2025-10-06 | `ratio-out-of-range` | `VERIFIED_REFERENCE` | [S3], [L1] |
| كسعدي | 2020-05-26 | `duplicate-date`, `symbol-identity` | `CONFLICT_DUPLICATE` | [S3], [L1] |
| كسعدي | 2021-06-08 | `duplicate-date`, `symbol-identity` | `CONFLICT_RATIO` | [S3], [L1] |

The two `ratio-out-of-range` rows are the only `VERIFIED_REFERENCE` rows with an
out-of-range ratio; they stay listed and are not independent evidence [S11]. The five
`duplicate-date` / `symbol-identity` rows sit in the duplicate and conflict buckets and do
not become `VERIFIED_*`.

## 7. Symbol ledger and inventory reconciliation

Source: [L2], 6,103 data rows, 56 columns; counts in [S4], [S11].

### 7.1 Final status

| Final status | Symbols | Source |
| --- | ---: | --- |
| `INSUFFICIENT_EVIDENCE` | 5,910 | [S4], [L2] |
| `CONFLICT` | 90 | [S4], [L2] |
| `VERIFIED_WITH_EVENTS` | 55 | [S4], [L2] |
| `RECONSTRUCTED_VERIFIED` | 46 | [S4], [L2] |
| `VERIFIED_NO_APPLICABLE_EVENT` | 2 | [S4], [L2] |
| `BLOCKED_SOURCE` | 0 | [S4], [L2] |
| **Total** | **6,103** | [S4], [L2] |

Of the 5,910 + 90 = 6,000 unverified symbols, 5,186 are zero-step rows: 5,185 with no
reference and 1 that has a reference window but stays `INSUFFICIENT_EVIDENCE`. The other
814 carry steps (790 validity `reconstructed_verified` + 24 validity `verified`) and map to
`INSUFFICIENT_EVIDENCE` or `CONFLICT` at symbol level [L2], [S11], [S4].

### 7.2 Identity, staleness, blockers

| Measure | Value | Source |
| --- | ---: | --- |
| Identity resolved via instruments | 4,633 | [S4] |
| Ambiguous instrument identity | 2 | [S4] |
| No instruments row | 1,468 | [S4] |
| - of which no pack step and no reference | 1,467 | [S4] |
| Instruments rows | 5,944 (5,941 named; 3 duplicate-name rows) | [S7] |
| Named instruments with history | 4,635 | [S7] |
| Named instruments without history | 1,306 | [S7] |
| Duplicate instrument keys | 3 (`آواپارس`, `حیان072`, `کیمازی`); 2 in history | [S7] |
| Stale status | fresh 29; recent 2,034; stale 3,596; halted 444 | [S4], [L2] |
| Halted by instrument title | ممنوع 422; توقف 32 | [S4] |
| Baseline-unverified pack steps | 1,358 across 782 raw pack spellings = 754 normalised keys; 658 keys mapped, 96 unmapped | [S4], [C1] |

### 7.3 6,328 versus 6,103

The two numbers are different populations, and both are reproduced:

- 6,103 is the number of history symbols (price_history keys) and the number of
  `history_validity` rows.
- 6,328 is the recorded "no adjustment evidence" count under the legacy r32b pack:
  5,022 history symbols with neither an `adjust_events` row nor a pack step + 1,306
  instruments-only names. It is not a history count [S7].
- With the current pack the same definition gives 6,333 = 5,027 + 1,306. The pack adds 96
  keys (none without a product event) and drops 8 (5 without a product event), a net +5
  [S7].
- The union of history, instruments, pack and product symbols is 7,409 normalised keys
  (7,446 raw spellings); 37 raw spellings are alias spellings already inside the key set
  [S7].

### 7.4 Alias spellings

36 Persian/Arabic spelling pairs share a normalised key. They produce 82 duplicate effective
dates and 468 alias-only steps, which the symbol ledger merges under the history spelling.
`8,280 - 82 = 8,198` merged steps; the validity table holds 7,730 because 35 rows omit the
468 alias-only steps [S4], [S11]. The ledger labels those 35 rows `alias_steps_omitted`
instead of inflating their count [L2].

## 8. Anomalies on the new Seed

Source: [S5] and [S6]. The anomaly scan is row-level and rule-based; the category comes from
the measured witness, never from the anomaly kind.

| Category | Events | Source |
| --- | ---: | --- |
| `UNRESOLVED_SOURCE_GAP` | 53,176 | [S5] |
| `VERIFIED_NO_EVENT` | 7,034 | [S5] |
| `CALENDAR_GAP` | 388 | [S5] |
| `INVALID_SOURCE_RECORD` | 308 | [S5] |
| `PRICE_BASIS_DIFFERENCE` | 3 | [S5] |
| Other eight categories | 0 | [S5] |
| **Total** | **60,909** | [S5] |

| Kind | Events | Source |
| --- | ---: | --- |
| `OPEN_EQ_PREV_CLOSE` | 57,911 | [S5] |
| `ZERO_VOLUME` | 2,692 | [S5] |
| `INVALID_OHLC` | 306 | [S5] |
| `DUPLICATE_DATE` | 0 | [S5] |
| `ZERO_FIELDS` | 0 | [S5] |

Key splits:

- `UNRESOLVED_SOURCE_GAP` = 50,680 open-equals-prior-close + 2,496 zero-volume. Of the total
  53,176, 50,489 pre-existed in the old Seed and 2,687 are new rows from the backfill [S5],
  [S6].
- `OPEN_EQ_PREV_CLOSE` = 7,034 first-trade-verified + 50,680 unresolved + 194 market
  no-session + 3 basis difference. 15 rows additionally carry a halt tag; the first-trade
  equality decides them [S5].
- `ZERO_VOLUME` = 194 market no-session + 2,496 unresolved + 2 non-flat range bars
  (`INVALID_SOURCE_RECORD`); no zero-volume row has a halt snapshot on its exact date [S5].
- `INVALID_OHLC` = 306 rows, all `legacy-unknown`, 0 from the 33,145 new rows: 12 `open=0`
  with a valid shadow, 294 `open=high=low=0` with a positive close outside the zero shadow;
  10 resolve to an instruments row and 0 of those have a same-day `daily_prices` row [S5],
  [S6].
- The residual request is explicit: `daily_prices.price_first` for 1991-05-28..2026-11-10 and
  per-symbol halt snapshots; the present windows are daily_prices 2026-08-20..2026-10-11
  (32 sessions, 118,774 rows) and instrument_state 2026-10-05..2026-10-11 (5 snapshot days)
  [S5].
- 7 new one-session drops in the backfill are outside the five B8 kinds: 4
  `UNRESOLVED_SOURCE_GAP` (شنفت 1995-07-26; طلا 2026-11-02; تپسي 2026-11-10;
  غشان 2026-11-10) and 3 `CORPORATE_ACTION_MISSING` (شنفت 2014-06-17, 2021-10-26;
  لخزر 2023-02-20) [S6].
- The شنفت 1991-12-10 bar (open 42,400 against raw high/low/close 8,600, a 4.93x open) is a
  high-shadow widening accepted by `candle_contract.widen`; the correction log records five
  widened-open extremes in the six-symbol run, and the cross-run summary lists the top three
  [S13], [S15].

## 9. Backfill

| Measure | Six symbols | Freshness | Total | Source |
| --- | ---: | ---: | ---: | --- |
| Symbols planned | 6 | 644 | 650 | [S17] |
| Symbols available in capture | 6 | 644 | 650 | [S17] |
| Reference rows loaded | 22,029 | 14,263 | 36,292 | [S13], [S14] |
| Rows inserted | 19,540 | 13,605 | 33,145 | [S13], [S14] |
| Overlap with DB | 2,489 | 658 | 3,147 | [S13], [S14] |
| Skipped existing | 0 | 15 | 15 | [S13], [S14] |
| Invalid | 0 | 0 | 0 | [S13], [S14] |
| Existing rows changed | 0 | 0 | 0 | [S13], [S14] |
| Contract-widened rows | 644 | 2 | 646 | [S15] |
| Extreme widened opens | 5 recorded in the six run (max 4.93x) | 2 widened rows (both high-shadow; not counted as extremes) | - | [S13], [S14] |

- Row math: 511,139 + 19,540 + 13,605 = 544,284 [S15].
- Idempotency: both reruns inserted 0 and changed 0; the before/after digests are identical,
  and the row count did not move [S15].
- Reference coverage for the six is complete: `ref_dates_present` equals `ref_dates` for all
  six (`missing_ref=0`); local rows additionally carry 2 non-reference dates per symbol
  (مارون 129) [S15].
- Price basis: 2,489 common dates, median relative difference 0.00715, maximum 0.043364,
  0 rows above the 5% materiality threshold; verdict `OK` [S16].
- Provenance: 33,145 new provenance rows, 0 keys already in the Seed, 0 value mismatches,
  0 wrong `ref_type`/`adjust`/`resolution`, 0 duplicate keys, 0 seed rows changed or missing,
  0 freshness rows before 2026-10-11 [S15].
- The C3 fix converted 646 local geometry rejections (644 six-symbol + 2 freshness) into
  contract widenings. They had finite positive OHLCV and `high>=low`; they failed only the
  old tool's local `high<open`/`low>open` gate. `candle_contract.widen` accepts 646/646 and
  changes only the high/low shadow, never open/close [S15].

## 10. Seed Candidate

| Artifact | SHA-256 | Size (bytes) | Source |
| --- | --- | ---: | --- |
| `seed/market.db` | `57118e8fc99ff69c9e9812002f1d72571f357c23287fc1880a2f00b8292bbcb5` | 281,088,000 | [S10], [M1] |
| `seed/market.db.lzma` (xz preset 9-EXTREME) | `07e67f9c781abfe62ea7557b3a84ff25136ea63035f6949db30611db179e2aa3` | 64,131,004 | [S10], [M1] |
| `seed/market.db.gz` | `9512202b9854326838d15b7ade46ccf5db99d4467b686693866fd3e06ede5d31` | 103,211,107 | [S10], [M1] |

| Measure | Value | Source |
| --- | ---: | --- |
| `price_history` rows | 544,284 | [S10], [M1] |
| Symbols with history | 6,103 | [S10], [M1] |
| Rows added versus base | 33,145 | [S10], [M1] |
| `reference_derived_rows` | 105,367 (72,222 Phase 4.8 + 33,145 new) | [M1], [S10] |
| `history_validity` rows / columns | 6,103 / 18 | [S10] |
| Validity status counts | verified 57; reconstructed_verified 46; unverified 6,000 | [S10], [M1] |
| Duplicate `(symbol,date)` pairs | 0 | [S10] |
| `PRAGMA integrity_check` | ok | [S10], [M1] |
| XZ / gzip round-trip | both equal the DB SHA | [S10], [M1] |
| `adjust_pack_state` | `ra365-phase49-rebuild-full-v2`, 8,280 steps, 951 symbols | [M1] |
| Raw-history corrections | 3,105 rows across 11 symbols | [M1] |
| User data | preserved; `user_watchlists` 0 rows | [M1] |

The new DB SHA differs from the old seed SHA, so the candidate is a new artifact rather than
a relabelled old one [S1], [S10]. The seed manifest matches the seed-directory manifest
byte-for-byte (`6a930818...`, 5,468 bytes) [M1].

Release gate: `python scripts/check_seed_release.py --db <candidate>` prints
`SEED_RELEASE_BLOCKED: 105367 reference-derived rows; owner approval for redistribution is
required` and exits 1. This is the designed behaviour, not a defect [M1].

## 11. Parity and product verification

| Check | Result | Evidence |
| --- | --- | --- |
| Python fixture parity, default interpreter | PASS, 76 passed / 0 failed | [S8] |
| Python fixture parity, tooling venv | PASS, 76 passed / 0 failed | [S8] |
| Go parity suite `TestPhase49ParityFixture` | PASS | [S8] |
| Go chart-db label tests (`ChartDB`) | PASS, 2 tests | [S8] |
| Engine parity, 30 symbols | PASS 30/30, `mismatches: []`; every symbol `go==py`, events equal, `factor_max_rel=0`, `candle_field_diffs=0` | [S8] |
| Product harness | PASS 12/12 checks | [S9] |
| Vitest chart labels | PASS locally: 106/106 test files, 865/865 tests (`npm ci`, then `npx vitest run`); reproduced in CI on `ea179e3c` by the `frontend v2` job | [S19], [S20] |

Product checks cover clean extraction (544,284 rows, 3,105 provenance rows, 6,103 validity
rows), chart-db reads (فولاد 3,689 bars, 2010-01-02..2026-11-09, 26 events), weekly 833 and
monthly 196 buckets, upgrade merge and user-data preservation, MA full history, and restart
idempotency (544,284 -> 544,284, 0 duplicate pairs) [S9].

One coverage caveat from the C5 report: the Go regex `-run 'TestPhase49|TestAdjustEngine'`
selects only `TestPhase49ParityFixture`; the adjustment-engine suite is named
`TestAdjustmentEngine_*` and was not selected by that command [S8]. The adjustment engine's
observable behavior is still covered by the 30-symbol Python-Go parity and the product
harness, but the named Go engine suite is not part of the recorded green set.

## 12. Python CI migration

The A4 document's reproduce line said 258 suites while the registry has 260. Two B suites
added later (`test_phase49_manifest.py` from B0b and `test_phase49_rules_guard.py` from B4)
were missing from the A4 table, so the document was regenerated with
`python dev/build_python_ci_migration_doc.py --write` and `--check` now passes. The generator
derives the count from the registry, so the line cannot go stale again. The current registry
is:

| Measure | Count |
| --- | ---: |
| Suites in the runner | 260 |
| A - live product/data contract | 17 |
| B - data / research / CI-tooling guard | 36 |
| C - legacy Python backend, API, UI or build surface | 207 |
| D - obsolete, checked code deleted | 0 |
| Legacy lane (`profile=legacy`) | 210 (207 C + 3 A) |
| KEEP / MIGRATE / DEPRECATE / REMOVE | 50 / 8 / 202 / 0 |

Workflows: `guards.yml` has 8 job definitions (`go-backend`, `go-race`, `go-windows`
matrix, `delivery-contract`, `data-integrity`, `zero-python-runtime`, `frontend-v2`,
`repo-hygiene`), which materialised as 9 jobs on `ea179e3c` because the Windows matrix
ran two versions; `python-tooling.yml` has `data-tooling`; `python-legacy.yml` has
`legacy-maintenance` and `legacy-static`. `python-legacy` is report-only by design.

Failure accounting in `PYTHON-CI-MIGRATION.md`: 24 rows = 17 `MEASURED_FAIL`,
2 `NAMED_SKIP`, 1 `FIXED_IN_A4`, 4 `FIXED_IN_C8` [S18]. Each row links a tracked excerpt
with its own SHA-256. The 177 suites that cannot execute locally for a missing third-party
package are never called passing; four of the previously `NOT_MEASURED` rows were measured
in CI in C8 and their errors record both the A3 local measurement and the C8 result.

C7 measured the two local runner profiles on this branch: `--profile production` passed
14/14 suites (13 with real counts, one exit-code-only, `PROTECTED_DB_UNCHANGED`), and
`--profile data` returned 30 PASS / 5 FAIL / 2 SKIP on the FastAPI-less host. C8 re-ran
the data lane with a FastAPI-capable venv (36 suites, `ALL SUITES PASSED`; two named
gitignored-fixture skips) and addressed the three real failures it exposed: B4's nine stale
`fund_*` goldens were regenerated from the oracle (the Go-consumed `sectors`, `quarters_*`
and `tape_*` goldens are byte-unchanged and `go test ./...` is green), B3's vector
freshness check now uses the Go parity 1e-9 numeric tolerance with exact keys and
non-numeric values, and B2 was reclassified to the legacy lane because the retired Python
engine's new legacy-only panels/fields cannot be the Go contract. The C8 CI data lane is
green [S18], [S19], [S20].

Final CI on `ea179e3c` is recorded in `CI-FINAL-RESULTS.json` with real run ids, URLs and
per-job conclusions: `guards` [42985995885](https://github.com/johnwarchief/BorsTerminal-src/actions/runs/42985995885)
- success, 9/9 jobs including `zero-python-runtime` and the installer runtime proof;
`python-tooling` [42985995514](https://github.com/johnwarchief/BorsTerminal-src/actions/runs/42985995514)
- success, data lane `ALL SUITES PASSED`; `python-legacy`
[42985995569](https://github.com/johnwarchief/BorsTerminal-src/actions/runs/42985995569)
- success by design with the `legacy Python maintenance (report-only)` job marked
`failure` and 30 red legacy suites, all visible in the UI. The legacy job failure is not
hidden and does not block the release lane.

## 13. Product defects and anomaly resolutions

| Item | Resolution | Source |
| --- | --- | --- |
| 646 reference bars rejected by the old local geometry gate | Fixed in the tool; inserted via `candle_contract.widen`; invalid 0 | [S15] |
| 5,188 validity rows with `factor_steps=0` while 782 symbols had unverified pack steps | The count is rebuilt from the step ledger, not from the old validity table; the 35 alias rows are merged and labelled; 5,188 -> 3 with reference + 5,185 without | [S4], [S11], [S10] |
| 6,328 no-evidence symbols | Reproduced under r32b (5,022 history + 1,306 instruments-only) and reconciled with 6,103; current pack 6,333 | [S7] |
| 306 invalid legacy OHLC | Classified `INVALID_SOURCE_RECORD` with row values; no new rows; no independent witness in this Seed | [S5] |
| 53,176 unresolved gaps | Separated into measured root causes and an explicit source request; not relabelled | [S5] |
| 7 new backfill drops | 3 corporate-action-covered, 4 explicit product-chain blockers | [S6] |
| Volana 3 steps | Root-caused to a cumulative double count; ledger status unchanged | [S12] |
| Python CI's 24 failure rows | Root-caused; 15 deprecated, 2 migrated, 7 kept; three-lane split | [S18] |

## 14. Solved versus unsolved

Solved in this round:

- Six short-history symbols now have full raw history (19,540 rows), and 644 freshness
  symbols received 13,605 missing rows; idempotency is proven [S13], [S14], [S15].
- The 646 previously rejected reference bars are inserted with contract widenings, and
  invalid is 0 [S15].
- A new Seed Candidate exists with 544,284 rows, integrity ok, 0 duplicate pairs, matching
  XZ/gzip round-trips, complete provenance and 105,367 reference-derived rows counted [S10],
  [M1].
- The ledgers are rebuilt against the full reference: 8,308 step rows and 6,103 symbol rows,
  with alias merging and independence disclosure [S3], [S4], [S11].
- The 6,300 reconstructed steps were audited (6,293 pass) [S3].
- Volana and the 7 new drops are root-caused and recorded [S12], [S6].
- The 6,328/6,103 inventory discrepancy is explained [S7].
- Python-Go engine parity (30/30) and 12/12 product checks pass [S8], [S9].
- The frontend gates pass locally under C7: `npm ci`, `tsc -b`, `vite build` and
  865/865 vitest tests in 106 files, including the chart-label assertion [S19].
- Python CI is split into three lanes with a 260-suite registry and 24 failures root-caused
  [S18]; the final CI on `ea179e3c` is green (`guards` 9/9 jobs including the
  zero-Python runtime and installer proofs, `python-tooling` `ALL SUITES PASSED`), and the
  report-only legacy lane keeps its 30 failures visible.

Not solved / explicit blockers:

- 339 unmapped capture symbols; 1,179 still-unverified pack steps (916 IE); 179 of the 1,358
  now `VERIFIED_*` (101 independent, 78 reference-confirmed); 5,185 zero-step rows
  without reference; 6,000 unverified history symbols; 1,468 no-instrument symbols; 444
  halted symbols [S4], [S3], [S11].
- 4,846 reference-confirmed steps counted inside the verified group, not independently
  validated; 2 ratio-out-of-range reference rows remain [S11].
- 53,176 unresolved anomaly events; 306 legacy invalid OHLC; 4 unadjustable new backfill
  rows; 3 corporate-action-missing boundaries; widened-open extremes [S5], [S6], [S13].
- Seed release blocked by the reference-redistribution gate (105,367 rows) [M1].
- B2 (mstat fixture oracle) is a legacy divergence: the retired Python engine emits
  legacy-only panels/fields the Go port intentionally does not, so its goldens cannot be
  the Go contract; the suite is report-only and red, with the Go tests on the same fixture
  and goldens as the live gate [S18].
- The legacy lane stays visibly red (30 suites) by design; it never blocks a release.

## 15. Owner decisions required

1. **Reference redistribution approval.** The Seed cannot be released while
   `reference_derived_rows` is 105,367. The owner must approve or replace the licensed
   footprint; the gate is already enforcing this [M1].
2. **Backfill source for the four unresolved splits.** شنفت 1995-07-26 and the 2026-11-10
   rows for طلا/تپسي/غشان need a pack step or an official corporate-action row; no local
   source can close them [S6].
3. **Historical first-trade/halt tape.** 53,176 anomalies need `daily_prices.price_first`
   over full history and per-symbol halt snapshots; the present windows are too narrow [S5].
4. **339 unmapped symbols.** Either provide an asset-id map or accept that these symbols
   remain outside the reference coverage [S4].
5. **Volana pack correction.** Restoring the dropped 2026-07-15 step and using single-step
   ratios is a pack change with downstream ledger effects; it needs an owner decision [S12].

## 16. Reproduction commands

```bash
# Ledgers (full reference)
python _audit/phase49-full-verification/stage03_step_ledger.py \
  --db _audit/phase49-finalization/seed/market.db \
  --pack data/ra365_corrections/ra365-phase49-rebuild-full-v2 \
  --reference _audit/phase49-full-verification/captures/reference-index-all.json \
  --rules dev/phase49_status_rules.json \
  --out _audit/phase49-full-verification/ledgers/ADJUSTMENT-EVIDENCE-LEDGER.csv
python _audit/phase49-full-verification/stage05_symbol_ledger.py \
  --db _audit/phase49-finalization/seed/market.db \
  --steps _audit/phase49-full-verification/ledgers/ADJUSTMENT-EVIDENCE-LEDGER.csv \
  --reference _audit/phase49-full-verification/captures/reference-index-all.json \
  --asset-map _audit/phase49-full-verification/capture-plan/symbols.json \
  --capture-plan _audit/phase49-full-verification/capture-plan/capture-plan.json \
  --step-counts _audit/phase49-full-verification/evidence/step-ledger-counts.json \
  --out _audit/phase49-full-verification/ledgers/HISTORY-COVERAGE-LEDGER.csv

# Anomalies on the new Seed
python _audit/phase49-full-verification/stage06_anomaly_ledger.py \
  --db _audit/phase49-full-verification/seed/market.db \
  --out _audit/phase49-full-verification/ledgers/anomaly-ledger.csv

# Seed release gate (expected BLOCKED without the owner flag)
python scripts/check_seed_release.py --db _audit/phase49-full-verification/seed/market.db

# Parity and product checks
python dev/test_phase49_correction_parity_v1.py
python _audit/phase49-full-verification/stageE_engine_parity_new.py
python _audit/phase49-full-verification/stageE_product_tests_new.py

# CI migration document freshness
python dev/suite_registry_guard.py
python dev/build_python_ci_migration_doc.py --check

# Deliverable assembly and SHA manifest
python _audit/phase49-full-verification/stage11_deliverables.py
```

The frontend gates and both runner profiles are reproducible from this machine state (C7 ran
them, and C8 re-ran the data profile with a FastAPI-capable venv). The final CI record was
fetched through the GitHub REST API because `gh` is absent locally; the record itself is
committed in `CI-FINAL-RESULTS.json`:

```bash
cd frontend-v2 && npm ci && npx vitest run   # C7 PASS: 106 files / 865 tests [S19]
python dev/run_all_tests.py --profile data   # C8 (FastAPI venv): ALL SUITES PASSED, 36 suites
python dev/build_python_ci_migration_doc.py --check
```

The final CI evidence (run 42985995885 `guards`, 42985995514 `python-tooling`, 42985995569
`python-legacy`) is verifiable at
`https://github.com/johnwarchief/BorsTerminal-src/actions/runs/<id>` for commit `ea179e3c`.
