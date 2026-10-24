# RA365 Round 27 — Source closure, fresh full-history capture and CODAL evidence

**Date:** 2026-10-24  
**Branch:** `mission/ra365-round27-source-closure-2026-10-24` (based on `origin/main` = `2e42131a`; **not merged**, per the mission)  
**Contract:** `docs/RA365-ROUND26-PARITY-CONTRACT.md` v1.0 frozen; a separate metric-clarification **proposal** is in §4 (not applied).  
**Issue:** #12

## 0. Verdict summary

- **Track B executed:** fresh full-history product capture with the current engine core — **2,594 / 2,595** assets produced a payload (1 `EMPTY_PRODUCT`), D/W/M audited against the frozen reference.
- **Track A executed as an audit + shadow prototype:** no production source change; live Rahavard-primary capture is **BLOCKED** (no fresh authenticated capture/entitlement used); dual-source is a tested prototype only.
- **Track C partially executed:** bounded public CODAL retrieval ran without 429; one `NOT_FOUND`, two documents found but **no extractable amount/ratio** → `INCOMPLETE_DOCUMENT`. No event was promoted.
- **No production code behavior changed.** New read-only tools/tests/docs only.
- Full gate: **PENDING** (result appended in §7).

---

## 1. Phase 0 — baseline

- `origin/main` at start: `2e42131a` (Round 26 report); Round 25 commits `07413c32`, `3cfe2d16`, `bac580c4` are ancestors; working tree clean; dedicated branch created.
- Existing regression tests re-run green: R25 combined-DPS 6/6, share-leg 9/9; R24 feed-shrink 10/10; R23 live-DPS 5/5; R22 8/8, 7/7, 9/9; R21 13/13.
- Round 25 frozen baseline reproduced exactly: 14 56.33/56.51; 31 52.01/51.92; 50 55.18/54.71; holdout 62.17/60.95 (adjusted D/W).
- Frozen inputs (SHA-256): reference `ref_bars_v2.jsonl` `4b1ecb4c…` (231,604,461 B, 2026-10-20); pre-R18 product `product_live_final_v4.jsonl` `893b6d6a…` (641,759,990 B) — **not used as current-code evidence**; cohort manifest 277,500,847 B; TSETMC CSV cache 3,352 files / 377 MB (2026-10-22). Copies: `D:/BorsTerminal-tmp/r26_bench/frozen/` and `D:/BorsTerminal-tmp/r27_live/`.
- Protected DBs: `market.db` `e08d8062…`, promoted `8fb85f38…` — unchanged.

## 2. Track B — fresh full-history current-engine capture

### 2-1. Method
- `tools/ra365_round27_product_capture.py` replays each cached TSETMC daily CSV through the **current code path**: parser → base-gap discovery → ledger sharpening → unproven-gap filter → canonical adjustment (share-leg dedupe, combined DPS, long-gap share changes) → `factor(t)`. No network, no DB writes; SELECTs from an isolated DB copy (`r22_test`, which carries `price_adjust_event_rows`).
- Captured in 4 deterministic shards with checkpoints and a per-asset ledger; large payloads live outside Git at `D:/BorsTerminal-tmp/r27_live/product_shard0..3/` (2,594 files, 550,367,055 bytes; per-file SHA manifest `artifacts/ra365/r27/payload-manifest.sha256`).
- Full-history per asset, no live bar; provenance (CSV SHA, DB SHA, timestamp, code SHA) stored in each payload. This is an **engine-core replay**, not the live chart route; labelled as such.

### 2-2. Capture ledger
| State | Assets |
|---|---:|
| SUCCESS | 2,594 |
| EMPTY_PRODUCT | 1 (`حيان072`) |
| NO_TSETMC_CACHE | 0 |
| ERROR | 0 |

### 2-3. D/W/M audit (fresh capture vs frozen reference)
Reference W is the frozen weekly series; **monthly reference is derived** from complete daily reference bars with the frozen Jalali month-key rules and is labelled `derived:monthly`. Product factors are re-anchored at the last common date (comparison only); raw candles are untouched.

| TF | Raw literal row % | Raw widen-contract row % | Adjusted row % | Paired rows |
|---|---:|---:|---:|---:|
| D | **99.8482** | 87.6030 | **58.6631** | 1,194,446 |
| W | **98.9789** | 89.6967 | **59.5538** | 275,776 |
| M (derived ref) | **96.3259** | 88.5820 | **58.5682** | 69,268 |

- Adjusted close exact: D 25.73%, W 25.98%, M 26.37%; volume exact: D 99.935%, W 98.833%, M 95.46%.
- Paired assets: **1,989 / 2,595**; 1 reference asset has no payload (`حيان072`, EMPTY_PRODUCT), 605 payloads have <10 common dates with the reference (short/alias histories) and are listed in the capture ledger rather than dropped silently.
- Coverage per timeframe (`artifacts/ra365/r27/audit-summary.json`): D paired 1,194,446 / ref-only 35,826 / product-only 939,725; W 275,776 / 8,174 / 240,337; M 69,268 / 2,068 / 62,573. Product-only rows include pre-reference history and extra sessions; they are counted, not deleted.
- `EMPTY_PRODUCT` (`حيان072`) is counted, not dropped.

### 2-4. Interpretation
- **Raw literal (Rahavard-facing) is 99.85% daily / 98.98% weekly / 96.33% monthly** — the remaining gap is source/revision/basis, not adjustment.
- The widen-contract row is **lower** (87.6%) because Rahavard type0 high/low are the session extremes, while `widen()` raises the product H/L to contain the body; this is a **metric clarification** (§4), not a regression.
- Adjusted full-universe current-engine rules produce **58.66 / 59.55 / 58.57** on this capture. This is higher than the 50-symbol R25 cohort (56.37) because the cohort contains the hardest symbols; it is the first full-universe current-code adjusted measurement with D/W/M.

### 2-5. Coverage ledger
- Manifest 2,595; payloads 2,594 (1 `EMPTY_PRODUCT`); paired 1,989; not-paired 605 (payload exists, <10 common dates); no reference asset other than `حيان072` lacks a payload.
- Coverage: D 1,194,446 paired / 35,826 ref-only / 939,725 product-only; W 275,776 / 8,174 / 240,337; M 69,268 / 2,068 / 62,573. Ref-only and product-only rows are retained in the denominator accounting.
- The unpaired 605 are dominated by short or alias histories; their capture-ledger states are in `artifacts/ra365/r27/capture-ledger.csv`.

## 3. Track A — source architecture

See `docs/RA365-ROUND27-SOURCE-MODE-REPORT.md`. Key facts:
- Current source: TSETMC CDN CSV, local fallback, basis-aware cache; **no source dimension in the cache key**.
- Shadow prototype `tools/ra365_source_shadow.py`: per-series, never per-field; explicit provenance; `UNAVAILABLE` when neither source has data; mixed series raise. Tests **8/8**.
- Rahavard-primary live capture **BLOCKED**: no fresh authenticated capture was used; source-native parity (reference vs itself) is not independent validation. Licensing/entitlement and rate limits are owner decisions.
- Recommendation: **keep TSETMC default; DEFER dual-source opt-in; BLOCKED for a production raw-source switch** pending licensing, a fresh reference store and user-visible semantics review.

## 4. Metric clarification proposal (separate from the frozen contract)

- **Observation:** with the same fresh capture, raw **literal** (`high_raw/low_raw`, close=last) is 99.85% D, while the **widen** contract is 87.60%. R26's "contractual 99.82% vs Rahavard" and today's widen metric are therefore not the same field set; the R19 contract's widen is appropriate for the **TSETMC oracle**, not for literal Rahavard type0 comparison.
- **Proposal v1.1 (not applied):** define the Rahavard-facing raw contract as `high_raw/low_raw`, `open`, `close_last`, volume separate; keep `widen()` for TSETMC-oracle checks. No threshold/denominator change; both metrics will be reported side by side until reviewed.
- The frozen v1.0 contract remains in force for this round.

## 5. Track C — CODAL evidence

Bounded public search (`search.codal.ir/api/search/v2/q`, Category 6, symbol + Jalali window), max 2 attempts/event, Retry-After honored, 3 s between events. No 429 occurred; no credentials used.

| Event | Search | Document | State |
|---|---|---|---|
| مارون 2025-07-28 | HTTP 200, no matching assembly letter | — | `NOT_FOUND` |
| وبانك 2023-08-08 | assembly decision letter found | decision page fetched; no extractable amount/ratio | `INCOMPLETE_DOCUMENT` |
| فولاد 2022-08-09 | assembly decision/registration letters found | attachment page fetched; no amount in extractable text | `INCOMPLETE_DOCUMENT` |

- Documents found are listed with title/publish date/URL in `artifacts/ra365/r27/trackC/codal-ledger-run1.jsonl` and `run2.jsonl`; hashes recorded for fetched pages.
- No `S`, DPS or ratio was inferred; no event was promoted. Counterfactual results remain those of R26 (top-40 net +10,979 rows, 23 positive / 5 negative) — a bound, not a fix.

## 6. Tests and gate

- New tests: timeframe audit **11/11** (Saturday buckets, Jalali months, OHLCV, re-anchoring, stamp-independent pairing); source modes **8/8** (no mixing, UNAVAILABLE, provenance).
- Registered in `dev/run_all_tests.py`.
- Full gate attempt 1: **187 OK / 2 FAILED** — `mstat_snapshot_singleflight_v1` (SQLite `database is locked`) and `fts_engine_paths_parity_v1076` (subprocess timeout); both pass standalone (4/4 and 7/7). Environment/timing failures, not code.
- Full gate attempt 2 (clean, no parallel load): running; definitive counts appended in §7.

## 7. Full gate result

- **Definitive attempt 2 (clean, no parallel load): 212 OK / 0 FAILED / 1 skipped** (`market.db.lzma` fixture), **158 suite counted + 54 silent**, **`ALL SUITES PASSED`**, `GATE_EXIT=0`, `PROTECTED_DB_UNCHANGED` (`logical_total=1d9bc9b4…`). Log `artifacts/ra365/r27/full-gate.log`, SHA `de33af16…`; attempt 1 log preserved as `full-gate-attempt1.log` (two environment/timing failures, both pass standalone: mstat 4/4, fts_engine_paths 7/7).

## 8. Verified / derived / counterfactual / unavailable

- **Verified:** capture ledger states; fresh full-history payloads; D/W/M literal and adjusted percentages; source-mode tests; CODAL search outcomes and document hashes; protected DB hashes.
- **Derived:** monthly reference bars (from daily, Jalali keys); product W/M aggregation from daily; factor re-anchoring for comparison.
- **Counterfactual:** R26 top-40 event corrections (net +10,979 rows) — not applied.
- **Unavailable:** live Rahavard-primary capture (entitlement/session/rate limits); CODAL amounts for the selected historical events (pages lack extractable numbers or are attachment shells); full-universe real monthly reference; independently validated reference freshness.

## 9. Decision table

| Proposed change | Decision | Evidence | User-visible consequence | Risks | Rollback |
|---|---|---|---|---|---|
| Production raw-source switch to Rahavard | **BLOCKED** | no fresh live capture/entitlement; source-native parity is not independent validation | prices/OHLC semantics change; historical revisions differ | licensing, vendor dependency, coverage | flag back to TSETMC |
| Dual-source opt-in (source dimension in cache/provenance) | **DEFER** | shadow prototype 8/8; no fresh reference store | only uncovered assets change | source disagreement, cache partitioning | remove flag; disjoint cache namespaces |
| Widen contract for Rahavard raw | **DEFER (metric proposal v1.1)** | literal 99.85% vs widen 87.60% | none on product | mislabeled parity if left unclarified | keep both metrics reported |
| Current TSETMC default | **SHIP (no change)** | no production code changed; Round 25/26 regressions green | none | none | n/a |
| Promote a CODAL-derived event/ratio | **BLOCKED** | `INCOMPLETE_DOCUMENT`; no amount/`S` evidence | none | wrong adjustment if guessed | n/a |
| Audit tooling/tests/docs | **SHIP** | tests green; read-only | none | none | revert commit |

## 10. Delivery state

- Branch only; **no push to `main`, no merge, no force-push**. Changes are review-ready on the mission branch.
- Evidence manifest: `artifacts/ra365/r27/evidence-sha256.txt`; payload manifest: `payload-manifest.sha256`; gate logs: attempt 1 and definitive attempt 2.
- Protected DBs unchanged: `market.db` `e08d8062…`, promoted `8fb85f38…`.

## 11. Next decisions required from the owner

1. Approve or reject a **Rahavard-primary/dual-source** direction, including licensing and the user-visible source policy.
2. Approve a fresh authenticated reference capture (D/W/M) and a monthly reference either direct or derived.
3. Provide or authorize access to the official historical notices/attachments that contain DPS/capital/`S` amounts (or accept `INCOMPLETE_DOCUMENT` for those events).
4. Review the metric-clarification proposal v1.1 before any change to the frozen contract.
