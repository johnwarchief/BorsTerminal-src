# RA365 Round 27 — Track A: raw-source and dual-source decision

**Date:** 2026-10-24  
**Status:** architecture audit complete; live Rahavard-primary capture **BLOCKED** (no fresh authenticated capture used this round); shadow prototype implemented and tested (no production wiring).  
**Contract:** `docs/RA365-ROUND26-PARITY-CONTRACT.md` is frozen v1.0.

## 1. Current production path (verified in code)

| Stage | Where | Behaviour |
|---|---|---|
| Raw history acquisition | `api/chart.py:2516` `get_chart_tsetmc` | TSETMC CDN daily CSV `GetClosingPriceDailyListCSV` with 1.5s connect / 3s read timeouts |
| Offline fallback | `api/chart.py:2527` `_fallback_local`, `api/chart.py:3257` `get_chart_db` | local `price_history` series, marked degraded; `CDN_OFFLINE_UNTIL` (`api/chart.py:90`) suppresses CDN for 120s after a failure |
| Basis | `price_basis.py:137` `apply_basis` | `last` or `closing`; chart cache key `api/chart.py:3507` includes the basis |
| Contract H/L | `candle_contract.py:69` `widen` | displayed high/low contain the body; raw H/L kept separately |
| Identity | `symbol_identity.py` `pred`/`variants` | ISIN-backed aliases; board vs CODAL domains separated |
| Adjustment | `api/chart.py` canonical pipeline | CSV base gaps → official PA/share ledger → DPS formula → Round 21–25 dedupe/long-gap rules → `factor(t)` |
| Cache | `CHART_CACHE[_chart_cache_key(symbol)]` | **no source dimension**; a dual-source mode must partition it by source |

## 2. Source modes

### 2-1. TSETMC-primary (current default)
- Raw values are TSETMC-native: `open` = FIRST, `close` = official closing, `last` = last trade; basis decides displayed close.
- Independent reference for parity: Rahavard `type0`. Literal equality is limited by source divergence + basis/widen semantics (Round 26: 7,811 field mismatches; literal all-field row 87.61%).
- No licensing dependency; network is TSETMC CDN; fallback is local DB.

### 2-2. Rahavard-primary (evaluated, not enabled)
- Using the reference snapshot as the raw source makes **source-native parity 100% by definition**; this is not independent validation. Independent validation would require a second source (TSETMC) as oracle, i.e. the mirror image of today's measurement.
- Frozen corpus: 2,595 assets × type0/type7 × D/W (10,388 series, all HTTP 200); monthly reference is absent and must be derived from daily with the frozen Jalali rules (`derived:monthly`).
- **Live capture not performed this round.** It requires the owner's authenticated subscription session, entitlement/licensing review, rate-limit handling and a pinned store. No credentials or session tokens were read or stored. Therefore live freshness, latency, 429 behaviour and coverage for a fresh capture are **BLOCKED**.
- Operational implication: switching the chart's raw source would change user-visible prices/OHLC semantics (official close vs last, widen, historical revisions) and needs a product decision, not only a parity decision.

### 2-3. Dual-source (per-series, explicit provenance)
- Implemented as an isolated prototype: `tools/ra365_source_shadow.py`.
- Invariants (tested in `dev/test_ra365_round27_source_modes_v1.py`, 8/8):
  1. A series is served by exactly one source; mixed rows raise `SourceMixError`.
  2. Policy is `tsetmc_primary` per series; reference is used only when TSETMC has **no series at all** for that instrument.
  3. Missing on both sides is `UNAVAILABLE`, never a silent fallback.
  4. Every series carries provenance (`mode`, `source`, `snapshot`, `policy`, `mixed:false`).
- A production dual mode additionally needs: a `source` dimension in `_chart_cache_key`, a source field in API payloads, per-source cache namespaces and a source-aware fallback; none is wired in this round.

## 3. Measurements available without a fresh capture

| Metric | Value | Source |
|---|---|---|
| Reference series (D/W) | 2,595 assets × 2 types × 2 resolutions | frozen 2026-10-20 corpus |
| Reference monthly | **absent**; derived only (50-asset real M sample exists) | Round 26 report |
| TSETMC CSV cache | 3,352 files (2,595-asset manifest) | Round 18 cache, 2026-10-22 |
| Raw literal all-field rows | 87.6096% (147,306 / 1,188,921 differ) | Round 26 ledger |
| Raw contractual fields / rows | 99.8907% / 99.8221% | Round 26 ledger |
| Field mismatch classes | source 2,356; mapping 2,923; revision 1,488; precision 641; geometry 335; parsing 63; scale 5 | Round 26 ledger |
| Feed revision flips | 1,577↔1,576 rows per request | Rounds 24–25 |
| Fresh Rahavard capture | **BLOCKED** (no session used; licensing/entitlement) | this round |

## 4. Recommendation

1. **Keep TSETMC as the production default.** No production source change is justified by a parity percentage alone; the change would alter user-visible semantics and needs licensing/entitlement review.
2. **DEFER a dual-source opt-in** until the owner approves the user-visible policy (which source is canonical per asset, how provenance is displayed, what happens at source disagreement) and a fresh reference capture exists.
3. If literal 100% raw equality is a product requirement, the only paths are:
   - **Rahavard-primary** (reference store) with explicit licensing and a TSETMC oracle for independent checks; or
   - **Dual-source with reference-preferred** for the covered assets, with per-series provenance and no mixing.
   Both require an owner decision and a rollout/rollback plan (below).
4. **SHIP** nothing in the raw path this round; the shadow prototype and this document are the deliverable.

## 5. Rollout / rollback design (if a switch is later approved)

- Config: `BORS_RAW_SOURCE=tsetmc|rahavard|dual` (default `tsetmc`), read-only at startup; no silent per-request switching.
- Cache: key = `(symbol, basis, source)`; invalidate on source change; a series is never served from a different source.
- Payload: add `rawSource`, `rawSnapshot`, `fallbackReason` fields; frontend shows the source only when it is not the default.
- Persistence: reference snapshot store with SHA-256 + retrieval timestamp; no reference rows written into `price_history`.
- Rollback: set the flag back to `tsetmc`; cache namespaces are disjoint, so no data migration is needed. Monitor parity drift and error rates for one release before enabling by default.
- Licensing/security: reference data must be stored under the subscription terms; no cookies/tokens in logs or Git.

## 6. Decision table

| Proposed change | Decision | Evidence | User-visible effect | Risk | Rollback |
|---|---|---|---|---|---|
| Switch production raw source to Rahavard | **BLOCKED** | live capture/entitlement absent; source-native parity is not independent validation | prices/OHLC semantics change; historical revisions may differ | licensing, coverage, vendor dependency | flag back to TSETMC |
| Dual-source opt-in (reference fallback) | **DEFER** | prototype + no-mixing tests; no fresh reference store | only uncovered assets change; provenance shown | source disagreement, cache partitioning | remove flag; cache namespaces disjoint |
| Keep TSETMC default | **SHIP (no change)** | Round 26 contract metrics; no regression | none | none | n/a |
| Add source dimension to chart cache key | **DEFER** | required only if dual mode is approved | none until enabled | low | remove key dimension |
