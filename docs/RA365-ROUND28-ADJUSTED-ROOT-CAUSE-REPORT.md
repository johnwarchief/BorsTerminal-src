# RA365 Round 28 — Adjusted-parity root cause and high-impact closure

**Date:** 2026-10-25  
**Branch:** `mission/ra365-round28-adjusted-root-cause-2026-10-24` (from Round 27 head `24a01ed9`; **not merged**)  
**Contract:** Round 26 v1.0 frozen; no tolerance/denominator/cohort changes.  
**Production code:** **unchanged** this round (a candidate fix was prototyped and rejected; see §6).

## 1. Executive verdict

- The five named pilots and the broader **93-symbol / 119,219-row** class were reproduced exactly from the Round 27 artifacts.
- The largest single mechanism inside the class is a **real product defect**: an official share change inside a halt is dropped and the DPS leg is computed from the post-share close (**20 symbols / 29,380 rows**, including كنور and شپاكسا). Official share counts prove the leg.
- A two-part fix was prototyped. It corrects a **6.7× factor error** on شپاكسا, but the engine's merge of the CSV base gap, the DPS row and the share leg can double-apply or drop the combined gap; the tested variants did not produce a safe general fix. The adjusted **row-tolerance** metric also remains dominated by sub-percent precision residuals on high-priced symbols.
- The remaining classes are **fund distributions** (11 symbols / 12,347 rows) with reference omissions and per-event precision differences, and **62 symbols / 77,492 rows** of base-gap/DPS ratio precision without a precise official source.
- **No production change shipped.** The audit tooling and tests are the deliverable; the candidate fix is DEFERRED with the exact design needed.

## 2. P0 — audit inputs and semantics

See `docs/RA365-ROUND28-AUDIT-INTEGRITY.md`. Summary:
- Reference/product/cohort hashes and the 2,594-file payload manifest verified.
- The adjustment-event tables in `r22_test` are **identical** to the operational snapshot (fund 2,222 / PA 10,831 / share 3,493; rows 11,023 only in the isolated copy) → **no stale event input**.
- Reference factor at the last common date = **1.0 for all 2,593** paired assets; the audit re-anchors the product factor at the last common date (comparison normalization).
- Weekly/monthly aggregation and the new aligned chain debugger are covered by tests (11/11 and 4/4).

## 3. P1 — pilot cohort reproduced (D)

| Symbol | Rows | Raw literal % | Adjusted % | Category |
|---|---:|---:|---:|---|
| كنور | 1,463 | 99.9316 | **0.3418** | MISSED_SHARE_HALT_DPS |
| كمند | 1,617 | 99.8763 | **0.4947** | FUND_PORTAL |
| ارمغان | 1,616 | 99.6906 | **0.4950** | FUND_PORTAL |
| پارند | 1,614 | 99.5043 | **0.4957** | FUND_PORTAL |
| آكام | 780 | 100.0000 | **0.6410** | FUND_PORTAL |

- Universe inventory (raw ≥99%, adjusted <5%): **93 symbols / 119,219 rows**:
  - `MISSED_SHARE_HALT_DPS`: **20 / 29,380**;
  - `FUND_PORTAL`: **11 / 12,347**;
  - `OTHER_PRECISION`: **62 / 77,492**.
- Full ledger: `artifacts/ra365/r28/low-adjusted-classes.csv`; per-event chain tables: `artifacts/ra365/r28/chain/`.

## 4. P2 — per-event findings

### 4-1. شپاکسا (MISSING_EVENT + WRONG_EVENT_RATIO)
- Official share change **2022-03-16**: 1,080,000,000 → 9,221,398,000 shares (ratio **0.1171189**), inside a halt.
- Official DPS row 2022-03-13: `p_closing 15500 / p_notAdjusted 16200` (DPS 700, ratio **0.95679**); mapped to the reopening candle **2022-05-02**.
- Product applied **0.742078** (post-split close 2014 with pre-split DPS 700) and **no share leg**; reference step **0.1125379**.
- Prototype (official DPS ratio × share): 0.95679 × 0.1171189 = **0.112059**; the CSV base gap at the reopening is **0.112426** — both within 0.13–0.45% of the reference. The product was **6.6–6.7× too large** before 2022-05-02.
- Quick re-score of the prototype chain: adjusted row parity 1.91% → 2.67% (my scorer; R27 audit 3.01%) — the gross error is corrected but a residual 0.13–0.45% factor offset still fails the sub-rial tolerance on ~2,000-rial prices.

### 4-2. ارمغان (reference omission)
- All 83 fund-distribution steps were compared: product step at **2023-12-09** (DPS 206, ratio 0.979816) has **no reference step** (f_ref constant 0.443292); this single omission causes a **2.06%** offset on every earlier row. Other events differ by 0.005–0.8% (special 2020-05-05 DPS 988 vs ref-implied ~910).
- The product's event is supported by the official fund portal; removing it to match Rahavard would delete a valid distribution and is **rejected**.

### 4-3. كنور (base-gap precision + a small extra gap)
- 5 differing steps: one EXTRA small base gap (0.997169, 2020-05-26) and four base-gap ratio differences (0.06–0.47%). No official PA rows near them; official share ratios differ from the price adjustment by 5–10% (contribution effect), so the share ledger cannot sharpen them.

### 4-4. كمند / آكام (fund DPS precision)
- Per-event ratio differences are tiny (0.015–0.07% for كمند; 0.042–0.062% for آكام) but compound to 0.49% / 0.14% offsets. The reference-implied DPS is consistently ~0.1–2% below the portal DPS (e.g., آكام 255 → ~249–250); no official precise source distinguishes the definitions. A candle-close candidate improves ارمغان/پارند but worsens كمند/آكام → **no general rule**.

## 5. P4 — full-universe baseline and counterfactual

- Full-universe audit on the unchanged branch (2,594 payloads, 1,989 paired; monthly ref derived):
  - D: raw literal **99.8482%**, widen-contract 87.6030%, adjusted **58.6631%** (1,194,446 paired rows);
  - W: **98.9789 / 89.6967 / 59.5538**; M (derived): **96.3259 / 88.5820 / 58.5682**.
- No production change → candidate equals baseline; no denominator or semantic change.
- Counterfactual results (not shipped):
  - **Missed-share/DPS class (20 symbols):** prototype corrects large factor errors (شپاکسا 6.7×) but the merge interaction (base gap vs official DPS vs share leg) is unresolved: variant 1 double-applied the DPS, variant 2 dropped the combined base gap. Row-tolerance gain remains limited by precision residuals.
  - **Fund class (11 symbols):** candle-close base is mixed (improves two, worsens two) → rejected.
  - **Reference omissions:** aligning to the reference would require deleting official distributions → rejected.

## 6. P3 — why no production fix shipped

The verified defect is real, but a safe fix needs a **merge-level redesign**, not a local threshold:
1. The CSV base gap at the reopening already equals share × DPS (0.1124); applying the official DPS or the share leg separately double-counts.
2. The engine's `_sharpen_share_gaps` / `_apply_long_gap_share_changes` / `_merge_official_price_adjust` stages currently interact such that the combined base gap can be consumed while the share leg is skipped.
3. Any fix must be tested on the full 20-symbol class and a representative control set, not only شپاکسا. This round produced the debugger and the evidence but did not land the redesign.

## 7. P5 — tests and gate

- New: aligned chain debugger test **4/4**; Round 27 timeframe tests **11/11**; source-mode tests **8/8**; existing R21–R27 regressions re-run.
- Full gate on the Round 28 branch (production code unchanged; new test registered): **213 OK / 0 FAIL / 1 skipped** (`market.db.lzma` fixture), 158 suite counted + 55 silent, **`ALL SUITES PASSED`**, `GATE_EXIT=0`, `PROTECTED_DB_UNCHANGED`; log `artifacts/ra365/r28/full-gate.log`, SHA `33378e79…`.
- Protected DBs unchanged (`e08d8062…` / `8fb85f38…`).

## 8. Decision table

| Proposed change | Decision | Evidence | User-visible effect | Risk | Rollback |
|---|---|---|---|---|---|
| Merge-level fix for share+DPS across a halt | **DEFER** | 20 symbols/29,380 rows; شپاکسا 6.7× corrected in prototype; merge interaction unresolved | corrects large adjusted-price errors for halted capital increases | double-counting / dropping the combined gap; needs full class re-capture | revert commit; no data change |
| Fund candle-close base | **REJECT** | mixed: improves 2, worsens 2 pilots | none | fits the reference, not a proven rule | n/a |
| Remove product fund events absent in reference | **REJECT/BLOCKED** | official portal distributions; reference omissions (ارمغان 2023-12-09) | would delete valid total-return adjustments | wrong user-visible series | n/a |
| Precision-only base-gap tuning | **BLOCKED** | no official precise ratio for کنور et al.; share ratios differ 5–10% | none | guessing | n/a |
| Audit tooling/tests/docs | **SHIP** | tests green; read-only | none | none | revert commit |
| Production raw source / contract | **NO CHANGE** | contract frozen; source decision Round 27 | none | none | n/a |

## 9. Exact residual gap

- Adjusted row tolerance remains **58.66 / 59.55 / 58.57** (D/W/M) over the comparable full-universe capture.
- The 93-symbol low-adjusted class (119,219 rows) is fully classified: 20 missed-share/DPS, 11 fund-portal, 62 precision. Closing it requires (a) the merge redesign above, (b) exact official ratios/`S` where missing, and (c) a decision on reference omissions (they cannot be matched without deleting valid product adjustments).
