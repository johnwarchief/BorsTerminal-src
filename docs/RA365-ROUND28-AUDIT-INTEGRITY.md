# RA365 Round 28 — Audit integrity and metric semantics

**Date:** 2026-10-25  
**Branch:** `mission/ra365-round28-adjusted-root-cause-2026-10-24` (based on the unmerged Round 27 head `24a01ed9`)  
**Scope:** verify the inputs and comparison semantics used by the Round 27 full-universe audit before treating any residual as a production defect.

## 1. Inputs verified

| Artifact | SHA-256 / provenance | Status |
|---|---|---|
| Rahavard reference `ref_bars_v2.jsonl` | `4b1ecb4c…` (231,604,461 B; 2026-10-20; 10,388 series, HTTP 200) | unchanged |
| Pre-R18 product snapshot | `893b6d6a…` (641,759,990 B) | used only as historical context, **not** current code |
| Cohort manifest | 277,500,847 B; 2,595 assets | unchanged |
| Fresh current-engine payloads | 2,594 files, 550,367,055 B; per-file SHA in `artifacts/ra365/r27/payload-manifest.sha256` | verified |
| Protected DBs | `market.db` `e08d8062…`; promoted `8fb85f38…` | unchanged |

## 2. Adjustment-event ledger is current, not stale

The Round 27 capture used `D:/BorsTerminal-tmp/r22_test/market.db`. Its event tables are **identical** to the operational copy (`market.db`, `e08d8062…`):

| Table | r22_test | operational | max date |
|---|---:|---:|---|
| `fund_profit_events` | 2,222 | 2,222 | 2026-10-13 |
| `price_adjust_events` | 10,831 | 10,831 | 2026-10-21 |
| `share_change_events` | 3,493 | 3,493 | 2026-10-24 |
| `price_adjust_event_rows` | 11,023 | absent | 2026-10-21 |

The only difference is the multi-row table created by the Round 22 migration on the isolated copy. **Disproved hypothesis:** the residual is caused by a stale/incomplete event ledger for the captured period.

## 3. Basis and factor anchoring

- Product payload candle fields: `close` = official closing, `last` = last trade; the chart basis is `last`. Reference `type0.close` is the LAST-based raw close (Round 26 contract/R19 measurement). Literal raw comparisons use product `last`; the official-close variant is reported separately and is **not** the Rahavard-facing contract.
- Product factors are anchored at the product's own last candle (`factor=1`). Reference factor at the last common date is exactly **1.0 for all 2,593** paired assets. The audit re-anchors the product factor at the last common date for comparison (a comparison normalization, not a product change).
- Reference factor is inferred as `type7.close / type0.close`; it is reliable only where both closes exist and are non-zero (common-date pairing enforces this).

## 4. Aggregation and debugger tests

- Weekly buckets `(day-2)//7`; monthly Jalali keys (`jy*12+jm-1`), OHLCV order, stamp-independent pairing, and daily-adjusted aggregation are covered by `dev/test_ra365_round27_timeframe_audit_v1.py` (**11/11**).
- The new aligned chain debugger (`tools/ra365_round28_chain_debug.py`) classifies RATIO_DIFF/EXTRA/REF_ONLY on synthetic evidence: **4/4** (`dev/test_ra365_round28_chain_debug_v1.py`).

## 5. Confirmed audit issues and corrections

1. **Metric clarification (not a product bug):** the widen contract raises product H/L above Rahavard's raw extremes; Rahavard-facing raw literal (high_raw/low_raw + LAST) is 99.85% D, while widen is 87.60%. The Round 26 v1.0 contract remains frozen; the Round 27 proposal v1.1 (keep widen for the TSETMC oracle, literal for Rahavard) remains a proposal only.
2. **Anchor normalization:** product factors are anchored at a later date than the reference in some captures; the audit divides by the product factor at the last common date. Without this, a recent distribution would appear as a constant offset on all earlier rows (this explains part of the raw debugger offsets before normalization).

## 6. Disproved / unresolved

- **Disproved:** stale event input; reference anchor ≠ 1; monthly/weekly aggregation defects.
- **Unresolved:** none at the audit level. Production defects are analyzed separately in `docs/RA365-ROUND28-ADJUSTED-ROOT-CAUSE-REPORT.md`.
