# RA365 Round 30 — Full-universe adjusted parity recovery

**Date:** 2026-10-25  
**Branch:** `mission/ra365-round30-full-universe-parity-recovery-2026-10-25` from the verified Round 29 head `7e92ea79`  
**Code/tests head:** `e4a99458` (the tree the definitive gate ran on; this report/artifacts commit follows).
**Contract:** Round 26 v1.0 frozen; no tolerance/denominator/cohort/pairing change.  
**Verdict:** **PARTIAL / NOT_SHIP** — the +3.0pp D target was not reached on the canonical metric. Shipped on the branch: one independently proven **data** family (session-wide base-gap anomaly, +0.73pp D) and one production **routing** defect fix (no parity effect). Two candidate code families were measured and **rejected** because they regress the full universe or move controls without a safe evidence gate.

## 1. Stage A — baseline reproduced exactly

The canonical audit (`tools/ra365_round27_audit.py`) on the frozen reference and the R29 capture reproduces the required baseline and denominators:

| Metric | Baseline R30 run | Required R29 |
|---|---:|---:|
| D adjusted | **58.8564%** (1,194,446 rows) | 58.8564% |
| W adjusted | **59.7507%** (275,776) | 59.7507% |
| M adjusted (derived:monthly) | **58.7457%** (69,268) | 58.7457% |
| D / W / M raw literal | **99.8482 / 98.9789 / 96.3259** | same |

Reference SHA-256 `4b1ecb4c…`; coverage D 1,194,446 paired / 35,826 ref-only / 939,725 product-only; 1,989 paired assets. No pairing, cohort, tolerance or re-anchoring rule was changed.

## 2. Stage B — global attribution (all 1,989 paired assets)

`tools/ra365_round30_attribution.py` aligns the product and reference factor chains on every common daily date, classifies every differing step, and evaluates a one-step counterfactual for each failing row. Output: `artifacts/ra365/r30/attribution/` (`steps.csv`, `families.csv`, `assets.csv`, `summary.json`).

Totals: **6,770 mismatched steps**, **491,438 failing adjusted rows**, **74,483 rows** recoverable by correcting exactly one step. Top families by one-step recoverable rows:

| Class | Event signature | Error | Steps | Assets | One-step recoverable |
|---|---|---|---:|---:|---:|
| RATIO_DIFF | base gap | 0.1–1% | 297 | 223 | 18,302 |
| RATIO_DIFF | unproven gap (no source) | 0.1–1% | 135 | 77 | 7,680 |
| REF_ONLY | no product event | 0.1–1% | 231 | 118 | 7,106 |
| RATIO_DIFF | base gap | 0.01–0.1% | 171 | 132 | 7,015 |
| EXTRA | unproven gap | 0.1–1% | 14 | 13 | 4,797 |
| RATIO_DIFF | unproven gap | 0.01–0.1% | 149 | 85 | 4,745 |
| EXTRA | unproven gap | 1–10% | 39 | 31 | 2,529 |
| RATIO_DIFF | unproven gap | 1–10% | 30 | 26 | 2,145 |
| RATIO_DIFF | DPS + share | 1–10% | 13 | 13 | 1,767 |
| RATIO_DIFF | base gap | 1–10% | 32 | 29 | 1,655 |

The one-step counterfactual is an upper bound per family, not a claim that a fix is safe: many rows sit in assets with several wrong steps, and a locally correct ratio can worsen row parity until the other steps are corrected.

## 3. Stage C — family decisions

### 3-1. Session-wide base-gap anomaly — **SHIPPED as data, on an isolated DB**

Independently derived cross-sectional evidence (`tools/ra365_round30_gap_scan.py`, no reference used): on **2023-03-28**, **31 symbols** show a base/unproven gap, **32 steps**, **zero** official price-adjust/share/fund rows, median absolute deviation **0.015967**. The existing scanner rule (`official_symbols==0`, `product_only_steps>=10`, `mad<=0.02`) qualifies exactly this date; 2020-05-26 (45 symbols, mad 0.0234) and 2020-10-07 (10, mad 0.0280) do **not** qualify and were left untouched, including their possible real distributions.

- Migration: `artifacts/ra365/r30/session-anomalies.sql` (one row), produced from `tools/session_anomaly_scan.py`; applied **only** to `D:/BorsTerminal-tmp/r30_data/market.db`, a copy. The operational/promoted DBs were not modified.
- Recaptured the 31 affected assets with the current engine and the isolated DB; overlay on the unchanged baseline payloads for the full-universe audit.
- Result: **D 58.8564 → 59.5911 (+0.7347)**, **W 59.7507 → 60.4686 (+0.7179)**, **M 58.7457 → 59.4170 (+0.6713)**. Raw literal/contract and volume unchanged.
- Ledger: 31 factor-changed assets — **18 improved, 2 explained worsened, 11 unchanged**. Worsened: هجرت (47.70→15.02) and هرمز (9.58→5.29); both have additional unresolved precision steps, and removing the session artifact exposes (rather than creates) the remaining offset. The change itself is the documented market-wide session rule, not a per-symbol ratio.

This is a **code+data** result. The engine already reads `session_anomalies`; the missing piece was the table content. No test or contract threshold changed.

### 3-2. Share row inside a halt — **REJECTED after full-universe measurement**

Mechanism: a reopening base gap is close to one official share row inside the no-trade interval (مفاخر 2022: gap 0.201802, share 0.20264619, reference 0.20264608; حفارس 0.128023 vs 0.12779688; فلوله 0.074375 vs 0.07462687). A candidate sharpening rule was implemented test-first (7/7 + negative controls) and measured:

| Variant | Changed assets | Improved | Worsened | D result |
|---|---:|---:|---:|---:|
| 1% identity gate | 62 | 27 | 12 | 59.4826 (+0.6262) |
| 0.5% identity gate (`_SHARE_GAP_TOL`) | 6 | 4 | 2 | 58.7379 (**−0.1185**) |

The 1% variant fixes مفاخر (+34.1pp D), حفارس (+18.5), فلوله (+17.6), but falsely rewrites contribution capital increases whose observed price leg differs from the share ratio by **0.7–1.0%** (دپارس, شنفت, سخاش, ثپرديس, جم), with large row losses. The 0.5% gate removes those but still worsens two correct-share assets (وپاسار, خديزل) because their remaining precision steps dominate; the network effect is negative. **Without the official subscription price `S` (or an official PA ratio) there is no data-intrinsic way to distinguish a pure capitalization from a sub-1% contribution.** The code was reverted; the rejection is documented here and the diagnostic remains in `tools/ra365_round30_candidates.py`.

### 3-3. Base-gap precision with no official row — **BLOCKED**

543 base/unproven-gap steps / **19,166** one-step-recoverable rows have no official PA/share row within the window. The product gap is the observed base/previous-close ratio; the reference implies a slightly different ratio. Copying the reference ratio is forbidden, and no official precise ratio exists. The same limitation covers the `unproven gap` RATIO_DIFF families (≈14.6k recoverable). This is the largest remaining class and is a source-evidence limit, not a formula defect.

### 3-4. Reference-only steps — **BLOCKED**

378 of 380 reference-only steps / **10,564** recoverable rows have no official ledger row (share, PA or fund portal) near the step. Adding them would import reference-only events, which the frozen contract forbids. Two fund-portal matches were found but recovered no rows.

### 3-5. DPS / fund precision — **BLOCKED**

3,059 DPS steps; for the 2,822 with an official PA row the proven candle-close formula is exact against the reference on 2,739, while the official `pClosing/pNotAdjusted` ratio is better on only 47. A "mapped original date → official ratio" rule was prototyped and **rejected**: it rewrote hundreds of holiday-mapped DPS events where the formula was exact (e.g. مفاخر 2024–2026, شپارس 2021, تاصيكو 2023) and collapsed full-universe parity. Fund DPS amounts in the reference are 0.5–2.6% below the portal amount (كمند 272→265, ارمغان/پارند), with no consistent tax/rounding rule; guessing is forbidden.

### 3-6. Combined share+DPS residual — **PARTIALLY CLOSED (R29 preserved)**

R29's combined-gap claim remains active. The global audit still finds ≈3.4k one-step-recoverable rows in `DPS+share` ratio differences and ≈1.6k in `base gap+DPS`; these are large per-symbol errors (e.g. شپارس 2020 0.448 vs 0.676, كسعدي 2023 0.460 vs 0.501) but the correct leg cannot be chosen without official evidence for the omitted DPS/contribution. No new change was made.

## 4. Shipped code fix — live chart route wiring

The Round 29 base left `@router.get("/api/chart/{symbol}")` on the helper `_candle_closings(candles)`. OpenAPI therefore required a **`candles` query** and the market chart's `GET /api/chart/{symbol}` could never reach `get_chart_tsetmc`. The decorator was moved to the live handler; the new structural guard (`dev/test_ra365_round30_chart_route_v1.py`, **3/3**) checks the path parameter and that no candles query is required. This has **no effect on parity numbers**; it is a production correctness fix required by Stage D.

## 5. Stage E — canonical metrics, baseline vs shipped data arm

| Metric | Baseline R29 | After data arm | Δ |
|---|---:|---:|---:|
| D adjusted row | 58.8564 | **59.5911** | **+0.7347** |
| W adjusted row | 59.7507 | **60.4686** | **+0.7179** |
| M adjusted row | 58.7457 | **59.4170** | **+0.6713** |
| D / W / M raw literal | 99.8482 / 98.9789 / 96.3259 | same | 0 |
| D / W / M raw contractual (widen) | 87.6030 / 89.6967 / 88.5820 | same | 0 |
| Factor exact (daily dates) | 45.2230% | **45.7456%** | +0.5226 |
| Factor tolerance (1e-6) | 62.0488% | **62.7110%** | +0.6622 |
| Factor step exact | 99.7063% | **99.7088%** | +0.0025 |
| Adjusted volume exact D/W/M | 99.935 / 98.833 / 95.46 | same | 0 |

Adjusted field exact counts (baseline D): open 307,186; high 297,479; low 302,805; close 307,304 of 1,194,446. Target: 61.8564 / 61.7507 / 60.7457 — **not reached**; the shipped data arm recovers ≈8,774 of the required ≈35,833 daily rows (≈24.5% of the numeric target).

## 6. Controls and changed-symbol ledger

`artifacts/ra365/r30/compare-data/changed-symbols.csv`: 31 changed assets, 18 improved / 2 worsened / 11 unchanged. R29 controls: 2 touched — هجرت (worsened, same precision-step explanation) and ولانا (factor changed, row parity unchanged); both are on the session-anomaly date and are covered by the documented market-wide rule. No other control moved.

## 7. Stage D — live path validation (30 symbols)

Live payloads captured through the fixed handler with an isolated DB (`D:/BorsTerminal-tmp/r30_live2`), compared with the canonical replay (`artifacts/ra365/r30/live-check.csv`):

- 30/30 live responses `success`; **27/30 factor chains identical** to the replay.
- 3 differ only by feed revision: ساراب (factor max rel 2.30, 21 live-only/23 replay-only events), وتوسم (0.724, 14/18), پكوير (0.0078, 1/1). The live TSETMC CSV was fetched on 2026-10-25; the replay cache is 2026-10-22.
- No code path difference was found on the 27 identical series; the live handler and the replay share the same canonical adjustment engine.

## 8. Metric clarification — widened vs literal adjusted high/low

The canonical audit multiplies the product's **widened** high/low (`high`/`low`) for adjusted rows, while the reference type7 high/low are literal extremes. Under the same audit with literal `high_raw/low_raw` the baseline becomes **D 64.5905 / W 63.8787 / M 62.0936** (vs 58.8564 / 59.7507 / 58.7457). This is a **field-set clarification**, not a product fix: the product chart displays widened H/L by design, and the R26 contract §4 refers to the literal field rules. It is reported side by side and **not adopted**; the acceptance numbers above remain on the canonical widen metric. If the owner approves a v1.1+ contract clarification for adjusted H/L, the stated R30 target is already exceeded by the baseline, which would make the target definition rather than the engine the decisive issue.

## 9. Gate and protected databases

- **Definitive gate** on the delivered tree (`e4a99458`; isolated DB `D:/BorsTerminal-tmp/r30_gate2`, log `artifacts/ra365/r30/full-gate.log`): **214 OK / 0 FAIL / 2 skip**, **157 suites counted + 57 silent**, **`ALL SUITES PASSED`**, shell exit 0. Skips: the Phase-4 fixture `_audit/ra365_ref_bars.json` and `market.db.lzma` (documented missing fixtures). The Round 30 route guard is counted in the silent list.
- Attempt 1 (`full-gate-attempt1-node_modules.log`) failed only `dev/chart_api_check_v95.py` because the fresh worktree lacked `frontend/node_modules`; `npm ci` was run and the gate re-run. This is an environment prerequisite, not a code failure, and is reported transparently.
- Protected DBs: `market.db` SHA-256 `e08d8062be33301551e672683106b87ea930825657ea6956e515bc7ac191a2a4`; promoted `D:/BorsTerminal-tmp/ra365_round17/market_r17_migrated.db` `8fb85f381317634430cae429bd9775eba0a364b692e0868b4d9b17dbbcc6c17f` — both unchanged. The applied `session_anomalies` row exists only in the isolated copy `D:/BorsTerminal-tmp/r30_data/market.db` (SHA-256 `d9da8671…`).

## 10. Verdict and next evidence

**PARTIAL / NOT_SHIP on the canonical metric.** Proven and shipped: session-wide base-gap anomaly data (+0.7347 D / +0.7179 W / +0.6713 M) and the live chart route fix. Rejected after measurement: share-in-halt sharpening (both gates), mapped-DPS official ratio. Blocked with exact counts: base-gap precision without an official ratio (19,166 rows), reference-only events (10,564), DPS/fund precision (≈4.5k plus fund amounts), combined-leg residuals (≈5k).

The +3.0pp target is not safely reachable with the available evidence: ≈68.4k failing daily rows are the widened-vs-literal H/L presentation difference (a contract decision, not a fix), ≈33k are base-gap/unproven precision without an official ratio, and ≈10.6k are reference-only events. The next decisions needed are: (a) an official `S`/PA ratio source or CODAL evidence for the precision families, (b) a policy for reference-only events, and (c) an owner decision on the adjusted H/L field-set clarification.

## 11. Evidence and commits

- Global attribution: `artifacts/ra365/r30/attribution/`; candidate audit: `artifacts/ra365/r30/candidates/`; cross-section evidence: `cross-section-gaps.csv`, `session-anomaly-scan.csv`, `session-anomalies.sql`.
- Audits: `baseline-audit/`, `audit-data-final/`, `audit-baseline-literal-hl/`; factor parity: `factor-baseline.json`, `factor-data.json`; live: `live-check.csv`.
- Ledger: `compare-data/changed-symbols.csv`; controls: `artifacts/ra365/r29/controls-after-per-asset.csv`.
- Code: `api/chart.py` (route only), `dev/test_ra365_round30_chart_route_v1.py`, `dev/run_all_tests.py`; tools `ra365_round30_*.py`.
- Evidence hashes: `artifacts/ra365/r30/evidence-sha256.txt` (generated after the gate).
