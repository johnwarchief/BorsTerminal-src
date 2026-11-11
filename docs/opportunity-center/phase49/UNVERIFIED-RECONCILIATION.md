# Phase 4.9.1 - Unverified reconciliation

This file records what was reconciled, what was not, and what remains. It covers the 13
rule-book reconciliation categories, the baseline validity defect, the 5,185 zero-step rows,
the 1,358 baseline-unverified pack steps, the 339 unmapped capture symbols and the alias
duplicate dates.

Source keys used below:

| Key | Path | SHA-256 |
| --- | --- | --- |
| S1 | `_audit/phase49-full-verification/evidence/baseline.json` | `46c7e340d9f6f210e47d7596efaff471f36dcd16e84c8e94c11d41e8ec4c4300` |
| S3 | `_audit/phase49-full-verification/evidence/step-ledger-counts.json` | `e9d1077a2b2ea6cd6110e75ca2d8d42395bf536e7f1ac1bec5dfc4c142cf47aa` |
| S4 | `_audit/phase49-full-verification/evidence/symbol-ledger-counts.json` | `a7e21d45d8a86b1d479ac47ebf291a9680566f2677db21ade5ccefc9a80e4b47` |
| S5 | `_audit/phase49-full-verification/evidence/anomaly-counts.json` | `a9ce48b6f1e9e844a40a18a2ec63cf4868ec26d4979a3f6fe07c5fdaea8aa047` |
| S6 | `_audit/phase49-full-verification/evidence/post-backfill-anomalies.json` | `de9ea3a2a24bf971a5f80b0cfd534beea146cfc0117f8204a16fd0f17ec08fa6` |
| S7 | `_audit/phase49-full-verification/evidence/inventory-reconcile.json` | `af35b0968068b8feead3d1c5b3ee1e245e05f3790858b1df0a335f8a7bbca86f` |
| S10 | `_audit/phase49-full-verification/evidence/seed-integrity.json` | `59871182a89f13ff9fd81c26fd006bc7a2eefea67bb769b9ebbdede86d5d6f77` |
| S11 | `_audit/phase49-full-verification/evidence/ledger-counts.json` | `a638236db0ddf57d1443e9c450ae4dec9eb3a42414cd0c10b7844b02ca8015c3` |
| S12 | `_audit/phase49-full-verification/evidence/volana-rootcause.json` | `b3673e63157a36515ffc5a094e2fc0fb037f10c5b23d46963b52eb261f58fb3f` |
| S15 | `_audit/phase49-full-verification/evidence/backfill-idempotency.json` | `2461dea8f994fb6d30fcad3c72450f8f2077b659df9d511af8e22df14fb4f269` |
| S19 | `_audit/phase49-full-verification/evidence/local-gates.json` | `1a247d0272f3dc65f000c1b97599b6dc4f5e9fd5de130d6f7d9f1b5d112e65f9` |
| C1 | `_audit/phase49-full-verification/capture-plan/capture-plan.json` | `7dbe2a62073f73bb5beb38779be075914f8b178f954e7f728490922d9590cfd4` |
| L1 | `docs/opportunity-center/phase49/ADJUSTMENT-EVIDENCE-LEDGER.csv` | `c0ab45bf60ba8d95fa4f4f33d60d4fa6f465a62c07271053c8ca7781f5114a28` |
| L2 | `docs/opportunity-center/phase49/HISTORY-COVERAGE-LEDGER.csv` | `c3ad3741daaa55b849fb51aca7cc066ea859d0469de2eb85d82471988a69a650` |
| M1 | `docs/opportunity-center/phase49/FINAL-SEED-MANIFEST.json` | `6a930818b05f3ef180064e7c8c908830bac5a72d89b28111dd43fba9cb859aa7` |

## 1. The 13 reconciliation categories

The categories and their precedence are defined once in `dev/phase49_status_rules.json`
(SHA-256 `8397154f64e75aed1da455843a55e29c25c139dece95f134fa2a2767b02773b7`). B8 uses all
13; five carry B8 events and eight are zero in B8 for a stated reason, not by omission.
Two of the zero-in-B8 categories are still exercised by other stages (corporate actions by
the C4 audit, rounding by B6) [S5].

| # | Category | Events | Real sample | Root cause | Effect | Fix / disposition | Regression test |
| ---: | --- | ---: | --- | --- | --- | --- | --- |
| 1 | `SOURCE_MISMATCH` | 0 | none (0 events) | Needs two sources for one row; `price_history` keeps one row per `(symbol,date)` with a writer tag (`src`), not a source pair [S5] | No row can emit it | Not applicable this round; cross-source comparison lives in the reference witness | `test_stage06_anomaly_ledger.py` |
| 2 | `PRICE_BASIS_DIFFERENCE` | 3 | كيمازي 2026-10-10: `last != close` and `p_last != p_closing` on the joined daily row [S5] | Last/closing basis differs between the history row and the daily row | 3 events; the filed row would be `VERIFIED_NO_EVENT` under the sibling `ins_code` | Kept as a basis event; join policy (ISIN/ins_code precedence) documented and unchanged | `test_stage06_anomaly_ledger.py`, `dev/test_price_basis_v1070.py` |
| 3 | `CORPORATE_ACTION_MISSING` | 0 in B8; 3 in the C4 audit | شنفت 2014-06-17: raw 35,221 -> 11,000/10,560; exact pack step 0.3090697336 verified [S6] | One-session drop at a corporate-action boundary whose event row is absent; B8's five candle kinds cannot see it [S6] | The adjusted type7 chain is continuous; only the boundary event row is missing | Recorded as non-blocking in the C4 audit; no chain change needed | `test_stage03_step_ledger.py`, `test_stage09_seed_build.py` (post-backfill checks) |
| 4 | `EVENT_DATE_MISMATCH` | 0 | none (0 events) | Event-chain finding owned by B5 (step dates vs official dates), not readable from a bare candle [S5] | Step-level date shifts appear in the step ledger (`STEP_DATE_SHIFT_MAX_DAYS=5`) | Handled by the step ledger: e.g. شنفت 2021-10-26 with a 1-day O1 shift [S6] | `test_stage03_step_ledger.py` |
| 5 | `EVENT_RATIO_MISMATCH` | 0 | none (0 events) | Ratio comparison is a step-ledger concern (B5/B6) | Ratio conflicts appear as `CONFLICT_RATIO` in the step ledger | 223 `CONFLICT_RATIO` rows stay in [L1] | `test_stage03_step_ledger.py`, `test_b11_ledger_counts.py` |
| 6 | `SYMBOL_IDENTITY_MISMATCH` | 0 in B8 | none (0 row events); the symbol ledger carries 1,468 `unresolved_no_instruments` rows [S4] | B7's identity join, not a candle event; 1,468 history symbols have no instruments row | They stay in the ledger as `INSUFFICIENT_EVIDENCE` with `SYMBOL_IDENTITY_MISMATCH`; 3 duplicate instrument keys are reported [S7] | Never guessed; ISIN-first resolution for the 3 duplicates; the rest are explicit | `test_stage05_symbol_ledger.py`, `dev/test_symbol_identity_v1090.py` |
| 7 | `MISSING_HISTORY` | 0 in B8 | none (0 row events) | Absence of rows is a symbol-ledger gap count, not a row event [S5] | B7 records 197,093 gap sessions across 4,542 symbols [S4] | Gaps are reported; no inference fills them | `test_stage05_symbol_ledger.py` |
| 8 | `CALENDAR_GAP` | 388 | تيپيكو 2026-02-28: flat 34,380, volume 0 on a whole-market no-session date [S5] (row read from the [S10] Seed DB) | No row in the DB traded on 2026-02-28; the same 194 zero-volume rows also produce 194 open-equals-prior-close events | 194 `ZERO_VOLUME` + 194 `OPEN_EQ_PREV_CLOSE`; excluded from the per-symbol no-trade residual | Session-calendar witness (7 dates) accepted; no per-symbol guess [S5] | `test_stage06_anomaly_ledger.py` |
| 9 | `SOURCE_REVISION` | 0 | none (0 events) | Needs two vintages of the same row; the DB keeps one row per key [S5] | No row can emit it | Not applicable this round | `test_stage06_anomaly_ledger.py` |
| 10 | `PRECISION_OR_ROUNDING` | 0 in B8; B6 uses it | Volana 2020-03-11 / 2025-07-20 / 2026-05-23: cumulative 0.198239% [S12] | Sub-threshold reference factor nature plus a cumulative double count; every compared price is bit-equal or clearly different [S5] | No B8 event; the Volana assessment is `PARTIAL_REFERENCE` and the ledger status stays `RECONSTRUCTED_AUDITED` | Root-caused, not relabelled [S12] | `test_stage04_volana_rootcause.py` |
| 11 | `INVALID_SOURCE_RECORD` | 308 | اپرداز 2025-12-09: open 0, high 3,390, low 3,290, close 3,358, `legacy-unknown` [S5]; row read from the [S10] Seed DB | 306 invalid OHLC rows (12 `open=0` with valid shadow, 294 `open=high=low=0` with close outside the zero shadow) + 2 non-flat zero-volume bars [S5] | The 306 rows are served as-is; 10 resolve to an instruments row and 0 have a same-day daily row, so there is no independent witness | Reported, not repaired; no new row from the backfill [S6] | `test_stage06_anomaly_ledger.py` |
| 12 | `VERIFIED_NO_EVENT` | 7,034 | ضهمن5025 2026-08-20: open 1,315 = prior close = `price_first`, close 1,315 [S5]; row read from the [S10] Seed DB | The first-trade print equals the open, so open-at-prior-close is a real traded open, not an adjustment gap | 7,034 rows removed from the gap population; 15 also carry a halt tag | Verified by the first-trade witness; no event emitted | `test_stage06_anomaly_ledger.py` |
| 13 | `UNRESOLVED_SOURCE_GAP` | 53,176 | شنفت 1991-12-10: open 42,400 against prior close 8,600 and same-bar high/low/close 8,600 [S6] | No basis, first-trade, halt or calendar witness for 50,680 open-equals-prior-close and 2,496 zero-volume rows [S5] | 50,489 pre-existing + 2,687 new backfill rows remain unresolved | Explicit residual; the source request is `daily_prices.price_first` over full history plus per-symbol halt snapshots [S5] | `test_stage06_anomaly_ledger.py`, `test_b11_ledger_counts.py` |

The شنفت 1991-12-10 row is also the largest widened-open extreme in the backfill (4.93x);
`candle_contract.widen` raised the high shadow only, and open/close were not changed [S15].

## 2. The 5,188 validity defect

### 2.1 Before

The baseline Seed had 6,103 `history_validity` rows: 35 `verified`, 880
`reconstructed_verified`, 5,188 `unverified`. All 5,188 unverified rows had
`factor_steps=0`, while 782 pack symbols carried unverified steps and none of the 5,188
validity rows did. The table summed to 7,730 factor steps while the pack had 8,280 valid
steps [S1], [S4].

The cause is structural, not a bad count: the validity table is keyed by the history
spelling, while the pack is keyed by 951 raw spellings under 915 normalised keys. The 36
alias spellings carry 550 raw steps (82 duplicate dates + 468 alias-only steps) that the
table could not see. So the table's unverified total was 808 against the pack's 1,358
[S4].

### 2.2 After

The new ledger counts steps from the step ledger, not from the old validity table, and it
merges alias steps under the history spelling while labelling the 35 affected rows
`alias_steps_omitted` [L2]. The arithmetic is closed:

- `8,280` valid pack rows - `82` duplicate alias dates = `8,198` merged steps [S4].
- `8,198` = `7,730` validity-table steps + `468` alias-only steps [S4].
- `history_validity` unverified `808` + alias `550` = `1,358` pack unverified [S4].
- `history_validity` reconstructed `6,300` + verified `622` = pack `6,922` [S4].

The 5,188 rows are now accounted for as:

| Bucket | Rows | Source |
| --- | ---: | --- |
| Acquired a full reference window | 3 | [S11] |
| - became `VERIFIED_NO_APPLICABLE_EVENT` | 2 | [S11] |
| - stayed `INSUFFICIENT_EVIDENCE` (`REFERENCE_FACTOR_CHANGES_WITHOUT_STEPS`) | 1 | [S11] |
| Still have no reference and no pack step | 5,185 | [S11] |
| **Total** | **5,188** | [S11] |

The new Seed's status labels are rebuilt from the symbol ledger, not copied from the old
table: `verified` 57, `reconstructed_verified` 46, `unverified` 6,000 [S10], [M1]. The
6,000 is the mapped sum of `INSUFFICIENT_EVIDENCE` 5,910 + `CONFLICT` 90 [S4].

## 3. The 5,185 zero-step rows

These rows have a history but no factor step and no reference index. They are not a
"no-event" claim; they are unverifiable with the current sources.

| Split | Rows | Source |
| --- | ---: | --- |
| No reference, no pack step | 5,185 | [S11] |
| - identity resolved through instruments | 3,718 | [S11] (3,721 resolved in the 5,188 minus the 3 with reference) |
| - no instruments row | 1,467 | [S11], [S4] |
| - with any step row | 0 | [S4] |

Across the whole 5,188: 3 rows have an asset id, 3 have a reference, and 0 have any step
row [S4].

What remains: 5,185 symbols still need either a reference index window or a pack step.
1,467 of them cannot even be identity-matched to an instruments row, so they cannot be
looked up in the reference until an identity source is supplied [S4]. The 1,468 total
no-instrument count is one higher than the 1,467 inside this remainder because فيروزه2
carries one pack step but no instruments row [S11].

## 4. The 1,358 baseline-unverified pack steps

All 1,358 were re-reviewed against the all-symbol reference index. No step was promoted by
changing a label. The group splits into 1,179 still unverified and 179 now verified:

| Group | Rows | Source |
| --- | ---: | --- |
| Still unverified (916 + 118 + 136 + 5 + 4) | 1,179 | [S3], [S11] |
| Now `VERIFIED_*` (45 + 56 + 78) | 179 | [S3], [S11] |
| **Total** | **1,358** | [S3] |

| Outcome within the 1,358 | Rows | Meaning | Source |
| --- | ---: | --- | --- |
| `INSUFFICIENT_EVIDENCE` | 916 | No O1/O2/R1 witness and no auditable reconstruction | [S3] |
| `CONFLICT_RATIO` | 118 | A witness exists and the ratio disagrees beyond `FACTOR_MATERIAL` | [S3] |
| `PARTIAL_REFERENCE` | 136 | Reference window exists but the step sits between `FACTOR_EXACT` and `FACTOR_MATERIAL`, or the witness is partial | [S3] |
| `PARTIAL_OFFICIAL` | 5 | Official witness is partial | [S3] |
| `RECONSTRUCTED_AUDITED` | 4 | Internal reconstruction is auditable but not independent | [S3] |
| `VERIFIED_MULTI_SOURCE` | 45 | At least two independent witnesses agree | [S3] |
| `VERIFIED_OFFICIAL` | 56 | An official event matches | [S3] |
| `VERIFIED_REFERENCE` | 78 | Reference ratio agrees; this is a reference-derived confirmation, not independent validation | [S3], [S11] |
| **Total** | **1,358** | | [S3] |

Net movement from the full reference: 179 steps left `INSUFFICIENT_EVIDENCE` (75 to
`VERIFIED_REFERENCE`, 100 to `PARTIAL_REFERENCE`, 4 to `CONFLICT_RATIO`). The remaining 916
`INSUFFICIENT_EVIDENCE` rows are the largest residual; together with the other four
non-verified statuses the still-unverified total is 1,179 [S11]. Separately, the 1,358 rows
now include 179 with a `VERIFIED_*` status: 101 independent (45 + 56) and 78
reference-confirmed. The outflow 179 and the verified 179 are different sets and must not be
added or equated [S3], [S11].

The reconstruction audit is a separate check that does not read the reference: of the 6,300
`reconstructed_verified` rows, 6,293 pass and 7 fail. The seven rows (symbol, date, reason,
final status) are listed in section 6.5 of `FULL-VERIFICATION-REPORT.md`; they are carried as
a residual, not closed by a label change [S3], [L1].

## 5. The 339 unmapped capture symbols

| Measure | Value | Source |
| --- | ---: | --- |
| Capture-plan keys | 1,097 | [S4] |
| Raw spellings in the plan | 1,130 | [S4] |
| Asset-map symbols | 828 | [S4] |
| Mapped | 758 | [S4] |
| Unmapped (`NO_ASSET_ID`) | 339 | [S4] |
| - of which pack-unverified keys | 96 (the 1,358 baseline-unverified steps cover 782 raw spellings = 754 keys: 658 mapped, 96 unmapped) | [C1] |
| History symbols with an asset id | 758 | [S4] |
| History symbols without an asset id | 5,345 | [S4] |

Why it matters: an unmapped symbol has no reference bars, so no step in it can acquire a
reference witness. It stays in the symbol ledger with its actual status; nothing is inferred.
What remains: the owner must supply an asset-id map for those 339 keys, or accept that they
are outside reference coverage this round. The 782 raw spellings carrying the 1,358
baseline-unverified steps collapse to 754 normalised keys; 658 of those keys mapped and carry the steps, while the
other 96 did not map and cannot acquire a reference witness. That 96-key gap is an explicit
blocker, not a mapping success [S4], [C1].

## 6. Alias duplicate dates

| Measure | Value | Source |
| --- | ---: | --- |
| Alias spelling pairs | 36 | [S4] |
| Raw alias symbols | 72 | [S4] |
| Duplicate effective dates | 82 | [S4] |
| Alias-only steps | 468 | [S4] |
| Validity rows omitting alias steps | 35 | [S4], [L2] |
| Validity rows matching step count | 6,068 | [S4] |
| Alias ratio conflicts / partials | 11 / 39 | [S4] |

The duplicate dates are real duplicates: the same effective date appears under two
spellings of one instrument. The ledger collapses each pair with the history spelling as
the primary witness and records the merge in `alias_duplicate_dates` / `alias_only_steps`
[L1], [L2]. The alternative - counting both - would inflate the chain and make the step
counts disagree with the pack.

## 7. Other reconciliations closed this round

| Reconciliation | Result | Source |
| --- | --- | --- |
| 6,328 no-evidence symbols vs 6,103 history | 6,328 = 5,022 history + 1,306 instruments-only under r32b; current pack gives 6,333 = 5,027 + 1,306; both are reproduced | [S7] |
| Instruments rows vs named instruments | 5,944 rows - 3 duplicate-name rows = 5,941 named keys; 4,635 with history, 1,306 without | [S7] |
| Union universes | 7,409 normalised keys / 7,446 raw spellings; 37 raw alias spellings double-count keys | [S7] |
| Duplicate instrument keys | 3 (`آواپارس`, `حیان072`, `کیمازی`); 2 in history; resolved ISIN-first | [S7] |
| `adjust_events` | 12,829 rows, 1,087 raw symbols (1,051 keys); 890 pack keys with product events, 25 pack without, 161 product without pack | [S7] |
| 646 geometry rejections | 646/646 accepted by `candle_contract.widen`; 0 invalid | [S15] |
| Backfill rows | 511,139 + 19,540 + 13,605 = 544,284 | [S15] |
| Anomaly delta | 58,222 -> 60,909 (+2,687), all `OPEN_EQ_PREV_CLOSE` on new rows; 0 new invalid OHLC | [S5], [S6] |

## 8. What remains

| Open item | Count | Why it is open | Required source or decision |
| --- | ---: | --- | --- |
| Still-unverified baseline pack steps | 1,179 = 916 `INSUFFICIENT_EVIDENCE` + 118 `CONFLICT_RATIO` + 136 `PARTIAL_REFERENCE` + 5 `PARTIAL_OFFICIAL` + 4 `RECONSTRUCTED_AUDITED` | No verified witness for these rows | A reference or official witness, or an explicit owner acceptance |
| `CONFLICT_RATIO` pack steps across all rows | 223 (118 inside the 1,358) | Witness ratio disagrees | Resolve the pack/event ratio conflict |
| Unverified history symbols | 6,000 = 5,910 `INSUFFICIENT_EVIDENCE` + 90 `CONFLICT` | Symbol-level aggregation of the step statuses | Reference, official witness or identity source |
| Zero-step rows without reference | 5,185 | No reference window and no pack step | Reference index or asset id |
| Reference-confirmed steps inside the verified group | 4,846 (not independent) | The ratio came from the same reference index | An independent witness (official event or second source) |
| Failed reconstruction audits | 7 of 6,300 `reconstructed_verified` | Chain audit failed on 2 ratio-out-of-range and 5 duplicate/identity rows | Pack correction; listed row by row in the report section 6.5 |
| Halted symbols | 444 | Instrument state is halted | Halt snapshot or owner decision |
| No-instrument history symbols | 1,468 | Identity cannot be resolved from `instruments` | Identity source (ISIN/ins_code) |
| Unmapped capture symbols | 339 | No asset id | Asset-id map |
| Unresolved anomaly events | 53,176 | No full-history first-trade/halt tape | `daily_prices.price_first` and halt snapshots |
| Legacy invalid OHLC | 306 | Row fields contradict themselves; no witness | Source correction or explicit acceptance |
| New unadjustable backfill drops | 4 | No pack factor and no official event at the boundary | Pack step or official corporate action |
| Volana cumulative error | 3 steps | Dropped 2026-07-15 step and absorbed ratios | Pack correction decision |
| Seed release | 105,367 reference-derived rows | Licensing gate | Owner approval |
| Vitest chart labels | 1 test file | Local run PASS: 106 files / 865 tests [S19]; reproduced in CI by the `frontend v2` job on `ea179e3c` | Closed in final CI (`CI-FINAL-RESULTS.json`) |
| Final CI | 3 workflows | Complete on `ea179e3c`: `guards` 9/9 jobs success, `python-tooling` `ALL SUITES PASSED`, `python-legacy` report-only success with 30 legacy failures visible | Recorded in `CI-FINAL-RESULTS.json` |

No item above is closed by a label change. Each one either has a witness or stays in the
list.
