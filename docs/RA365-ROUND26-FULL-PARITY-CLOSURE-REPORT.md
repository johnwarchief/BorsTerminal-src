# RA365 Round 26 — Full Raw and Performance-Adjusted Parity Closure

**Date:** 2026-10-24  
**Branch:** `mission/ra365-round26-parity-closure-2026-10-24`  
**Start:** `main` = `b5f5f6c4` (Round 25 commits `07413c32`, `3cfe2d16`, `bac580c4` are ancestors)  
**Contract:** `docs/RA365-ROUND26-PARITY-CONTRACT.md` v1.0  
**Verdict:** **C — INCOMPLETE_EVIDENCE** (raw D/W is fully classified; full-universe current-code adjusted and full-universe monthly are not measurable with the available product/reference artifacts)

---

## 1. Repository verification

- `origin/main` at start: `b5f5f6c4`; the three Round 25 commits are in its ancestry (verified with `merge-base --is-ancestor`).
- Working tree clean; new branch created from `origin/main`; no force-push, no destructive reset, no merge of old migration branches.
- Round 25 helpers present and tested: `_drop_share_leg_of_observed_gap`, `_combined_dps_official_ratio` (4 occurrences in `api/chart.py`).
- Round 25 regression tests re-run green: combined-DPS 6/6, share-leg 9/9, feed-shrink 10/10, live-DPS 5/5, R22 8/8 · 7/7 · 9/9, R21 13/13.
- Round 25 frozen baseline reproduced exactly: 14 56.33/56.51; 31 52.01/51.92; 50 55.18/54.71; holdout 62.17/60.95 (adjusted D/W).

## 2. Frozen corpus and coverage (Phase B)

| Type | Res | Series | Assets | Bars | Empty | Range |
|---|---|---:|---:|---:|---:|---|
| type0 | D | 2,599 | 2,595 | 1,240,809 | 0 | 1993-04-25 … 2026-10-19 |
| type0 | W | 2,595 | 2,595 | 285,797 | 0 | 2017-12-30 … 2026-10-17 |
| type7 | D | 2,599 | 2,595 | 1,240,809 | 0 | 1993-04-25 … 2026-10-19 |
| type7 | W | 2,595 | 2,595 | 285,797 | 0 | 2017-12-30 … 2026-10-17 |

- All reference responses: HTTP 200.
- **Monthly full-universe reference does not exist in the frozen corpus.** Monthly is measured only for the 50-asset 2026-10-23 revision sample (`r23_ref_50`, 7,316 paired rows).
- Snapshots (SHA-256): reference `4b1ecb4c1effc4d5770c…` (231,604,461 bytes); product `893b6d6aa1059d51a83b…` (641,759,990 bytes); cohort manifest 277,500,847 bytes. Copies: `D:/BorsTerminal-tmp/r26_bench/frozen/`.
- Adjusted full-universe pairing: **1,964 / 2,595** reference assets have a matching product line; 631 are unmatched (aliases/delisted/coverage) and are excluded from pairing but counted here. Raw full-universe pairing: 2,595/2,595 via the cohort manifest.

## 3. Contract (summary — full text in `RA365-ROUND26-PARITY-CONTRACT.md`)

- Raw exact: `|d| ≤ 1e-9`; raw tolerance: price `max(0.5, 1e-6|ref|)`, volume 1.
- Contractual raw: FIRST open (clamped), `widen()` high/low, official closing and displayed basis separated; literal and contractual metrics reported separately.
- Weekly: Saturday buckets; monthly: Jalali month keys, pairing by key (stamp differs: product last trading day, reference first day of month).
- Adjusted: `factor(t)=∏ ratio` for events after `t`, last-candle anchor = 1; adjusted price = displayed raw × factor; exact/tolerance as raw.
- Denominator = paired rows; reference-only/product-only rows are counted, never deleted. Missing categories counted explicitly.

## 4. Raw discrepancy ledger (Phase A, full universe)

### 4-1. Contractual parity (R19 frozen contract, ref vs frozen product)

- **Fields:** 7,141,465 / 7,149,276 = **99.8907%**
- **Rows:** 1,186,806 / 1,188,921 = **99.8221%**
- Residual rows: **2,115**, all classified:

| Cause | Assets | Dates/Rows |
|---|---:|---:|
| `SOURCE_DATA_DIVERGENCE` | 538 | 1,150 |
| `HISTORICAL_REVISION` | 368 | 549 |
| `PRECISION_OR_ROUNDING` | 219 | 298 |
| `CANDLE_GEOMETRY` | 41 | 62 |
| `PARSING_OR_TRANSFORM` | 48 | 56 |

Field-level mismatches (7,811 total, 0.1093% of compared fields): `FIELD_MAPPING` 2,923; `SOURCE_DATA_DIVERGENCE` 2,356; `HISTORICAL_REVISION` 1,488; `PRECISION_OR_ROUNDING` 641; `CANDLE_GEOMETRY` 335; `PARSING_OR_TRANSFORM` 63; `PRICE_SCALE_OR_UNIT` 5. **UNCLASSIFIED = 0.**

Row-level ledger: `rahavard-raw-ohlc-round19-adjudication.csv` (116 adjudicated rows, buckets P0) and `rahavard-raw-ohlc-field-mismatches.csv` (7,811 rows with symbol/date/field/ref/prod/diff/cause/note). Artifacts are committed at `4305ab58`; their current hashes differ from the Round 19 report table (stale table; text and taxonomy counts match the committed artifacts).

### 4-2. Literal raw parity (same 1,188,921 rows, no widen/basis contract)

| Field | Exact | Compared | % |
|---|---:|---:|---:|
| open | 1,190,907 | 1,192,071 | 99.9024 |
| high_raw | 1,191,146 | 1,192,071 | 99.9224 |
| low_raw | 1,191,383 | 1,192,071 | 99.9423 |
| last (vs type0 close) | 1,188,383 | 1,188,921 | 99.9547 |
| close_display | 1,188,579 | 1,192,071 | 99.7071 |
| volume | 1,191,067 | 1,192,071 | 99.9158 |
| **all-field row (literal)** | **1,041,615** | **1,188,921** | **87.6096** |

- Literal 100% raw equality is **not achieved**; the gap is dominated by close/basis semantics (`close_display` 99.71%) and by the contractual widen rule (literal rows vs contractual rows differ by ~12 pp).
- Current code vs **TSETMC oracle** under the contractual rule (independent of Rahavard): **99.9824% fields / 99.9678% rows** over 2,124,936 pairs — no product-side regression.

### 4-3. Coverage boundary

- Product-only outside reference history: 931,089; product-only inside: 2,170 (no-trade 204, tradable 1,966; reference omission 1,883, unverified 83).
- Reference-only outside reference history: 39,296; reference-only inside: 1,844 tradable + 1,345 date-shift + 499 product omission.
- These are coverage differences; they are not deleted from the denominator.

### 4-4. Source-contract boundary (A2)

- Deterministic samples reproduce the R19 adjudication: e.g., `FIELD_MAPPING` rows where the product's `last` basis matches TSETMC LAST but type0 close is the official closing; `SOURCE_DATA_DIVERGENCE` rows where the product equals the TSETMC CSV oracle but Rahavard type0 differs; `HISTORICAL_REVISION` rows where the frozen reference predates a TSETMC revision.
- A product correction cannot close these without changing the source values. The only paths to literal 100% are (a) switching the raw source to Rahavard, or (b) adding an explicit source-selection/dual-source mode. Neither was implemented; the owner's approval is required.

## 5. Adjusted discrepancy ledger (Phase C)

### 5-1. Full-universe frozen product (2026-10-20 snapshot; pre-R18 engine — labelled, not current code)

- Paired assets 1,964; paired rows 1,189,336.
- Raw (display basis): **99.7182%**; factor exact: **26.4572%**; adjusted: **31.2432%**.
- Mismatched factor steps: `RATIO_DIFF` **3,814**, `REF_ONLY` **709**, `EXTRA` **122**.
- Failing adjusted rows attributed: `RATIO_DIFF` 743,019; `REF_ONLY` 48,145; `EXTRA` 18,318; raw/basis 2,694; unattributed 5,573.
- This snapshot is **not** the current engine: it predates the Round 18–25 fixes. It is used only as the full-universe event ledger, not as the current parity number.
- **Current rules on the same frozen event base** (`tools/ra365_round26_current_rules.py`, R25 dedupe + combined-DPS applied, factors recomputed): 2,595 assets, 1,192,071 rows, adjusted **31.3889%**; step counts unchanged (3,814 / 709 / 122). The R25 rules add only +0.15 pp at full-universe scale because the frozen event base predates their discovery step and the dominant 3,814 ratio-diff steps remain. This isolates rules from event discovery.

### 5-2. Current code, 50-symbol frozen cohort (R25, exact same contract)

| Metric | Before R25 | After R25 |
|---|---:|---:|
| 50 D / W adjusted | 55.18 / 54.71 | **56.37 / 55.83** |
| 14 D / W | 56.33 / 56.51 | 56.48 / 56.64 |
| 31 D / W | 52.01 / 51.92 | 52.07 / 51.98 |
| Holdout D / W | 62.17 / 60.95 | **65.83 / 64.42** |
| Monthly adjusted (50) | 53.50 | **54.40** |
| Code-only 14 D / W | 52.83 / 52.84 | 52.86 / 52.77 |

### 5-3. Counterfactual event attribution (C1)

- Top 40 residual steps (by attributed rows), corrected/removed/added one at a time with the same factor chain and tolerance:
  - **11,834 rows fixed, 855 rows broken, net +10,979** (of 126,961 rows → an upper bound of +8.65 pp if every correction were justified).
  - 23 events positive, 5 negative.
  - Largest positives: فولاد 2022-08-09 (+1,970), مبين 2023-12-04 (+1,942), فخاس 2022-12-05 (+1,049), سغرب 2024-11-20 (+1,037), فولاژ 2024-03-24 (+948).
  - Negatives: ومعادن 2025-02-22 (−452), شنفت 2019-01-07 (−181), حخزر 2023-10-15 (−88), مارون 2025-07-28 (−78), کمرجان 2023-09-02 (−56).
- This proves the remaining gap is not one single defect and that "correcting to the reference step" is not automatically a valid production fix (some corrections break more rows than they fix). The per-event counterfactual is a potential bound, not a promoted change.
- `REF_ONLY`/`EXTRA`: the full ledger is in the full-universe audit; each event carries identity/date/class. No reference event is imported; each lacks independent official evidence or is a coverage/date-mapping artifact.

## 6. Historical evidence and CODAL (Phase D)

- Local CODAL cache: 36,537 notices, **1399+ only**. For the pre-1399 composite actions (2013–2020) there is no notice in the cache.
- Statuses: `UNAVAILABLE_IN_CACHE` for historical notices; `RATE_LIMITED` remains possible for live retrieval; `INCOMPLETE_DOCUMENT` not observed in this round because no fetch was attempted.
- The verified evidence for the Round 25 fixes is the official TSETMC `price_adjust_event_rows` (p_closing/p_not_adjusted) and `share_change_events` (shares_old/new); no CODAL document was fabricated.
- `timescale_marks` 403 outside the authenticated context remains a blocker for a marks-based re-derivation; the frozen `_audit` corpus includes marks for 29 assets only.
- Minimal next step: prioritized CODAL archive fetch for the top residual events (post-1399 first), with checkpoints, `Retry-After`, and `VERIFIED`/`RATE_LIMITED` states; subscription `S` cannot be guessed.

## 7. Production fixes (Phase E)

- **No new production code fix was justified by this round.** The full-universe audit found no generic product defect beyond the already-shipped Round 18–25 fixes; the residual is source/contract/data-bound.
- No threshold, denominator, cohort or tolerance was changed; no reference event was imported; no synthetic data was created.
- New read-only tools added: `tools/ra365_round26_full_universe_audit.py` (full-universe raw/adjusted ledger) and `tools/ra365_round26_counterfactual.py` (per-event counterfactual).
- Tests: all existing adjustment tests re-run green; the two new tools are read-only and covered by their frozen-input runs (no new production behavior to regression-test).

## 8. Full validation and gate (Phase F)

- Raw: D/W full universe measured and classified; monthly full universe not measurable (no reference).
- Adjusted: 50-symbol current code fully measured D/W/M; full-universe current code not measurable (no current-code full-history product snapshot; the frozen product predates R18–25).
- Full gate on the Round 26 branch (same code as `b5f5f6c4`; only read-only tools/docs added): **210 OK / 0 FAIL / 1 skip** (skip = missing `market.db.lzma` fixture), **158 suite counted + 52 silent**, **`ALL SUITES PASSED`**, `GATE_EXIT=0`, `PROTECTED_DB_UNCHANGED` (`logical_total=1d9bc9b4…`). Log: `artifacts/ra365/r26/full-gate.log`, SHA `5fb02f0d…`.
- Protected databases: `market.db` `e08d8062…` and promoted `8fb85f38…` unchanged (source fingerprints checked; gate runs on an isolated copy).

## 9. Verdict and remaining gaps

**C — INCOMPLETE_EVIDENCE.** Raw D/W is fully measured and every residual is classified; adjusted is fully measured on the 50-symbol current-code corpus; but the following prevent an A/B completion:

1. **Full-universe monthly reference** does not exist (only 50 assets).
2. **Full-universe current-code adjusted** cannot be produced: the 2026-10-20 product snapshot predates R18–25, and the operational DB's `price_history` covers only 2024-08 onward, so a full-history re-run is not possible without a new full-history capture.
3. **631 reference assets** lack a matching product line (aliases/delisted/coverage).
4. **Historical CODAL evidence** (pre-1399) is unavailable in the cache; subscription `S` remains unknown for several contribution actions.

**Owner decision required:** (a) approve or reject a raw-source switch / dual-source mode for literal 100% raw equality; (b) authorize a current-code full-history product capture for the 2,595 assets and a full-universe monthly reference capture; (c) authorize a targeted CODAL archive retrieval for the top residual events.

## 10. Precise answers

- **What became exactly equal?** Nothing new at the 100% level; the current-code 50-symbol cohort improved (50: 55.18→56.37 D, 54.71→55.83 W; holdout 62.17→65.83; monthly 53.50→54.40) but remains below 100%.
- **What became tolerance-equal?** The same 50-symbol rows; raw 50 exact 99.56/99.06; raw full-universe contractual 99.8907% fields / 99.8221% rows (R19 contract).
- **What remains different?** Raw literal rows: 147,306 of 1,188,921 (12.39%) — dominated by close/basis semantics and widen; adjusted: source/event/ratio gaps across the full universe (31.24% frozen product, 31.39% with current rules on the frozen event base, 56.37% current 50-symbol end-to-end).
- **Full universe and all timeframes?** Raw D/W: yes (2,595 assets). Monthly: no (50 assets only). Adjusted current-code full universe: no.
- **Can the remaining raw gap be fixed under the TSETMC source contract?** No — it is source divergence + basis/contract semantics; only a source switch or dual-source mode closes literal equality.
- **Is adjusted parity blocked by missing S/events/marks or a product defect?** Blocked by event-data/reference differences and missing official historical evidence (`S`, pre-1399 CODAL), not by a remaining proven product defect. The full-universe current-rules run (31.39%) shows the R25 rules alone do not close the residual.
- **Measurable improvements/regressions:** R25 fixes remain positive and regression-free on the 50-symbol cohort; no new code change, so no new regression surface.
