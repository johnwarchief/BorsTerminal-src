# RA365 Round 29 — Safe share + DPS + base-gap merge redesign

**Date:** 2026-10-25  
**Branch:** `mission/ra365-round29-safe-share-dps-merge` from the verified Round 28 head `08b5271f`  
**Code/tests:** merge fix `47385235` + gate-hygiene `aa1dd307` (the tree the final gate ran on; this report/artifacts commit follows).
**Contract:** Round 26 v1.0 frozen; no tolerance/denominator/cohort change.  
**Verdict:** **SHIP** — verified defect corrected generally, 20-symbol class and 30 controls replayed, full-universe D/W/M improved with zero worsened symbols, full gate **214 OK / 0 FAIL / 1 documented skip** (`ALL SUITES PASSED`), protected DBs unchanged. Details in §8–§9.

## 1. Stage A — the scoring discrepancy is resolved

| Number | Scorer | Inputs / semantics |
|---|---|---|
| 1.91% → 2.67% (Round 28) | ad-hoc quick scorer | used the product's **official `close`** instead of the displayed basis, a single close-field row test, no weekly/monthly, no OHLC row/volume split |
| 3.0096% (Round 27 audit) | canonical R27 audit | product displayed basis (`last`), factors re-anchored at the last common date, OHLC row + volume separate, D/W/M |

The canonical baseline for شپاکسا is therefore **3.0096% D / 2.7356% W / 1.2658% M** over 1,462 D pairs; the Round 28 quick scorer is not comparable and is retired. All before/after numbers below use the canonical audit.

## 2. Stage B — the real event chain and the merge model

### 2-1. Observed chain (current production, شپاکسا)
1. CSV base gap at **2022-05-01**: **0.112426** — the observed reopening price adjustment.
2. Official DPS rows **2022-03-06** and **2022-03-13** (both DPS 700; source ratios 0.95858 and 0.95679) map to the reopening candle **2022-05-02**.
3. Official share change **2022-03-16**: 1.08B → 9.221398B (0.1171189).
4. Current merge dropped the observed gap via `_drop_base`'s "no share within 7 days" fallback and kept one official DPS row, recomputed on the post-share close: **0.742078** (6.6× the reference 0.1125379).

### 2-2. Model (implemented)
- The **observed base gap is the combined price effect** of the action at the reopening.
- A share change is considered part of that action when its date lies between the official row's **original date** and its **mapped reopening candle** (not only ±7 days around the reopening), and the gap equals `share_ratio × official_source_ratio` within `_SHARE_GAP_TOL` (0.5%).
- When the gap is claimed:
  - all official rows that are consistent with that same combined action are **suppressed as components** (reported `included-in-combined-base-gap`);
  - the observed gap is **kept and applied once**;
  - claimed rows are removed from `_drop_base`, so the gap cannot be dropped.
- Same-date duplicate rows with **no distinct original dates** keep the Round 15 neutrality (gap + one official row survive); materially different same-date legs stay ambiguous/kept.
- An unexplained base gap is **not** claimed; the legacy Round 7 behavior for the DPS window is preserved (an attempt to remove it caused a broad regression, §5).

**Economic invariant:** every adjustment is applied exactly once. When the observed gap contains the share/DPS legs, those legs are not multiplied again; when it does not match `share × source_ratio`, the legs and gap remain independent and the existing rules apply.

## 3. Stage C — tests

`dev/test_ra365_round29_combined_gap_merge_v1.py` (**6/6**):
1. شپاکسا-like combined gap: gap survives, both consistent DPS legs suppressed, exactly one event.
2. Ordinary DPS with no share: keeps the DPS row.
3. Share outside the official→mapped halt window: no combined claim.
4. Materially different same-date legs: ambiguous/kept.
5. Round 15 two-claim neutrality preserved (**21/21**).
6. Regression suites re-run: R21–R28 (13/13, 8/8, 7/7, 9/9, 5/5, 10/10, 8/8, 7/7, 9/9, 6/6, 4/4, 11/11, 8/8), `test_adjustment_phasea` 48 pass/0 fail/1 skip, unproven-base 10/10, R14 17/17, R15 21/21, R16 27/27, R17 8/8·8/8·9/9.

## 4. Measurement — 20-symbol heuristic class

The Round 28 `MISSED_SHARE_HALT_DPS` heuristic flagged 20 symbols. The merge claim requires the gap to equal `share × official`; only **3 symbols** actually trigger it:

| Symbol | Rows | Adjusted row before | after | P90 relative error before → after | Median before → after |
|---|---:|---:|---:|---|---|
| شپاكسا | 1,462 | 3.0096% | 3.0096% | **566.85% → 1.13%** | 1.129% → 1.129% |
| ساراب | 1,506 | 2.3240% | 2.3240% | 17.54% → 0.20% | **17.54% → 0.20%** |
| بورس | 1,421 | 4.1520% | 4.1520% | **550.60% → 0.64%** (P99 582.6% → 5.30%) | 0.189% → 0.189% |

- The other 17 heuristic hits do **not** meet the combined-gap identity → events unchanged (correct, no suppression).
- **Row-tolerance parity is unchanged** for all three: the corrected residual is now 0.1–5% rather than 500%+, but the sub-rial tolerance on high-priced symbols still fails. This is the known precision wall, not a remaining gross defect.
- **Error magnitude**: the gross factor errors are eliminated (P90/P99 from 500%+ to ≤5.3%).

## 5. Controls and the rejected broader change

- 30 controls (11 fund-class, 5 precision-class, 14 fixed-cohort): adjusted-row % and factors **completely unchanged** after the fix.
- A first variant also removed `_drop_base`'s Round 7 fallback (to avoid dropping unrelated gaps). It caused a **real regression**: لخزر 81.51% → 4.05%, ومعادن 47.49% → 45.42%, and factor changes in 7 controls. The fallback was **reverted**; the final fix is limited to the combined-gap claim and has no control regression. This is retained as a counterexample in the report.

## 6. Full-universe D/W/M recalc (fresh current-code recapture)

2,594 payloads recaptured in 6 shards (same manifest/denominators/reference), canonical audit:

| Metric | Before | After | Δ |
|---|---:|---:|---:|
| D raw literal / widen | 99.8482 / 87.6030 | 99.8482 / 87.6030 | 0 |
| D adjusted | 58.6631 | **58.8564** | **+0.1933** |
| W raw literal / widen | 98.9789 / 89.6967 | 98.9789 / 89.6967 | 0 |
| W adjusted | 59.5538 | **59.7507** | **+0.1969** |
| M (derived ref) raw / widen | 96.3259 / 88.5820 | 96.3259 / 88.5820 | 0 |
| M adjusted | 58.5682 | **58.7457** | **+0.1775** |

- Factor-changed symbols: **44**; error-magnitude **improved 29 / unchanged 15 / worsened 0**; row-tolerance **improved 5 / unchanged 39 / worsened 0**.
- The 5 row-improved symbols (all positive): حسیر 14.00→88.14, شلعاب 15.63→67.78, بهپاک 76.86→92.38, بمپنا 17.89→30.18, وبملت 46.57→51.63 (D adjusted row %).
- Largest magnitude corrections: كرازي P90 1011.5%→2.2%, بمپنا 921.0%→0.03%, فلوله 1237.1%→0.32%, وخارزم median 204.0%→0.45%.
- No raw/contract/denominator change; no symbol worsened.

## 7. Full-universe per-symbol ledger

`artifacts/ra365/r29/changed-symbols.csv` (44 rows: median/P90 before/after and direction). Controls (30) and the 17 non-triggering class symbols have identical factors and row parity.

## 8. Gate and protected DBs

- **Attempt 1** (`artifacts/ra365/r29/full-gate-attempt1-citations.log`): 158 suites counted, **213 OK / 1 FAIL / 1 skip**. The failure is the known citation class: the moved block added 30 lines to `api/chart.py`, so three `NAME:LINE` references in `docs/FTS-RULE-ALGORITHM-MAP.md` went stale (`_fts_analyze_candles` 5278→5308, `_fts_jet_setup` 4256→4286, `_fts_analyze_symbol` 5686→5716). Fixed with `_audit/fix_rule_map_lines.py --apply`; the guard is **11/11**. This is the same documented regression class as Round 21; no product behavior is involved.
- **Attempt 2** after the citation fix (`artifacts/ra365/r29/full-gate-attempt2-mstat-flake.log`): **213 OK / 1 FAIL / 1 skip** — `dev/mstat_snapshot_singleflight_v1.py` failed with SQLite `database is locked` on all 8 concurrent connections (the documented transient lock seen in R24/R27).
- **Root cause of the flake (measured):** the guard built a fresh rollback-journal DB and then had **eight connections concurrently run `PRAGMA journal_mode=WAL`**; SQLite refuses the simultaneous journal-mode upgrade with an immediate `database is locked` (no waiting can resolve the upgrade deadlock). Standalone reproduction: **8 pass / 2 fail** in 10 runs. The guard measures snapshot single-flight, not journal-mode negotiation, so the harness now sets WAL **once on the build connection**; all four assertions are unchanged. After the harness fix: **20/20 standalone passes** (`artifacts/ra365/r29/mstat-standalone-20.log`). Attempt 3 was stopped after reproducing the same flake on the pre-fix harness (`artifacts/ra365/r29/full-gate-attempt3-mstat-partial.log`).
- **Definitive run** on the fixed tree (isolated DB `D:/BorsTerminal-tmp/r29_gate4`, log `artifacts/ra365/r29/full-gate.log`): **214 OK / 0 FAIL / 1 skip**, **158 suites counted + 56 silent**, **`ALL SUITES PASSED`**, guard exit 0. The only skip is the documented missing fixture (`market.db.lzma`, R1/R2 housekeeping). The FTS citation guard is **11/11**; the mstat single-flight guard is **1/1**.
- Test-only harness change: `dev/mstat_snapshot_singleflight_v1.py` now sets WAL once on the build connection (no assertion or threshold changed). No production behavior is affected.
- Protected DBs: `market.db` file SHA-256 `e08d8062be33301551e672683106b87ea930825657ea6956e515bc7ac191a2a4`, gate logical total `1d9bc9b4…` before and after; promoted `D:/BorsTerminal-tmp/ra365_round17/market_r17_migrated.db` SHA-256 `8fb85f381317634430cae429bd9775eba0a364b692e0868b4d9b17dbbcc6c17f` — **`PROTECTED_DB_UNCHANGED`**.

## 9. Final verdict

**SHIP** — the merge-level algorithm corrects the verified defect generally, applies each economic adjustment exactly once, has focused and negative-control tests, improves the full-universe D/W/M adjusted parity (+0.19/+0.20/+0.18 pp) with **zero worsened symbols**, and leaves the raw/contract/denominators untouched. The final full gate on this tree is green (214 OK / 0 FAIL / 1 documented skip, `ALL SUITES PASSED`, exit 0), and both protected DBs are byte-identical before/after.

Branch contents: `api/chart.py` (merge fix), `dev/test_ra365_round29_combined_gap_merge_v1.py` (6 checks), `dev/run_all_tests.py` (registration), `dev/mstat_snapshot_singleflight_v1.py` (test-only WAL setup fix), `docs/FTS-RULE-ALGORITHM-MAP.md` (citation lines after the code move), this report, and `artifacts/ra365/r29/`.

The row-tolerance metric does not move for the three شپاکسا-class symbols because the remaining 0.1–5% precision residual still exceeds the sub-rial tolerance; that is the separately-tracked precision class, not this defect. The benefit is the elimination of 500%+ adjusted-price errors on 29 symbols and five row-parity gains, with no event loss or double application.

## 10. Remaining evidence

- The two شپاکسا DPS rows (same amount, consecutive dates) are treated as one combined action because the observed base gap and the reference both match `share × one DPS`; a CODAL document distinguishing two independent installments would be needed to revisit this. Until then, the observed gap is the empirical net adjustment.
- Fund-class reference omissions and base-gap precision remain as in Round 28 (separately tracked, not touched by this fix).
