# BorsTerminal — Master Roadmap & Migration Dependency Graph

**Snapshot:** 2026-11-14  
**Active implementation branch:** `go-main @ ef6a8ba503bd`  
**Migration audit:** `docs/migration-progress-audit-2026-11-14 @ c3dcf34abab8`  
**Purpose:** one living map for desktop/runtime migration, Phase 4.9.8, Chart/FTS, technical-engine completion, and local ML.

> The migration audit is a separate documentation branch. Its status snapshot describes `go-main @ ef6a8ba5`; it is not merged into `go-main`. Re-check live code, reports, CI and commits before changing any status.

## 1. Integrated master graph

```mermaid
flowchart TB
  subgraph MIG["A · Desktop / Go migration"]
    S1["Stage 1 · Python elimination<br/>ACCEPTED"] --> S2["Stage 2 · Production cutover + Rahavard parity<br/>ACCEPTED"]
    S2 --> S3["Stage 3 · Go data producers<br/>ACCEPTED"]
    S3 --> S4["Stage 4 · Production activation<br/>ACCEPTED"]
    OC["Opportunity Center P0–P6<br/>IN PROGRESS · 9/66"]
  end

  subgraph DB["B · Canonical technical DB · Phase 4.9.8"]
    DB06["DB-06 · 4.9.7 technical DB built<br/>COMPLETE as separate artifact only"] --> DB07["DB-07 · Global data validation<br/>OPEN"]
    DB06 --> DB08["DB-08 · Iranian-market scope manifest<br/>OPEN"]
    DB06 --> DB11["DB-11 · Explain DB size/schema<br/>OPEN"]
    DB07 --> DB09["DB-09 · Canonical schema + data contract<br/>OPEN"]
    DB08 --> DB09
    DB09 --> P08["PROD-08 · TSETMC incremental continuity<br/>OPEN"]
    DB09 --> DB10["DB-10 · PIT / walk-forward ML dataset v1<br/>OPEN"]
    DB09 --> DB12["DB-12 · Storage and performance benchmark<br/>OPEN"]
    DB07 --> E08["E2E-08 · Phase 4.9.8 acceptance / cutover<br/>OPEN · 19 gates"]
    DB08 --> E08
    DB09 --> E08
    P08 --> E08
    DB10 --> E08
    DB12 --> E08
  end

  subgraph CHART["C · Chart and FTS"]
    CH01["CHART-01 · KLineCharts integration<br/>PARTIAL"] --> CH03["CHART-03 · Drawing tools + persistence<br/>OPEN"]
    CH03 --> CH06["CHART-06 · Browser acceptance<br/>NOT MEASURED"]
    F01["FTS-01 · Canonical rule reconciliation / parity<br/>PARTIAL"] --> F03["FTS-03 · Canonical envelope / adapter<br/>OPEN"]
    F01 --> F06["FTS-06 · Golden vectors / config alignment<br/>OPEN"]
    F03 --> F06
    F06 --> UI06["UI-06 · FTS screener<br/>OPEN"]
    GO10["GO-10 · OC read models / registry<br/>PARTIAL"] --> UI16["UI-16 · Opportunity Lab / Today<br/>OPEN"]
    F03 --> UI16
    DB01["DB-01 · OC/research DB migrations<br/>PARTIAL"] --> E06["E2E-06 · OC P0 gate<br/>PARTIAL"]
    F01 --> E06
    GO09["GO-09 · Notification backend<br/>PARTIAL"] --> E06
    E06 --> E07["E2E-07 · OC P1–P6<br/>OPEN"]
    UI16 --> E07
  end

  subgraph TECH["D · Technical Engine Completion"]
    SRC["Inventory & reconcile sources<br/>docs/Indicator/ + technical-indicators/inbox/<br/>Telegram 64 + current TS/Go implementation"]
    SRC --> CAT["Prune active Telegram catalogue<br/>preserve original source assets"]
    CAT --> MAP["Map capabilities / reuse 26 PatternKinds<br/>detection · confluence · risk · display"]
    MAP --> GAP["Implement proven gaps only<br/>reuse-first · no parallel engine"]
    GAP --> TIME["Closed-bar / no-lookahead / prefix stability<br/>detected_at and available_at != anchor time"]
  end

  subgraph ML["E · Local learning · technical-first"]
    JOURNAL["Market Signal Journal"] --> STORE["PIT Feature Store + versioned outcome labels"]
    STORE --> PAT["1 · Pattern quality"]
    PAT --> REG["2 · Five-state market regime"]
    REG --> RISK["3 · Volatility / downside / liquidity risk"]
    RISK --> SEQ["4 · Candle-sequence forecasting<br/>Kronos remains first-class challenger"]
    SEQ --> RANK["5 · Opportunity Discovery / ranking · LAST"]
    RANK --> VALID["Purged walk-forward validation / calibration / paper research"]
    VALID --> INFER["Go inference only through validated versioned contract"]
  end

  subgraph ACCEPT["F · Final product acceptance"]
    UIREST["Portfolio / settings / workspaces / RTL / visual acceptance<br/>OPEN or NOT MEASURED"]
    BUILD["Build / installer / updater / security / observability<br/>PARTIAL / OPEN / NOT MEASURED"]
    E05["E2E-05 · Final product acceptance<br/>OPEN"]
    E09["E2E-09 · Owner production cutover acceptance<br/>BLOCKED"]
    UIREST --> E05
    BUILD --> E05
    E05 --> E09
    E08 --> E09
  end

  S4 --> OC
  S4 --> E05
  CH06 --> E05
  UI06 --> E05
  F01 --> E05
  TIME --> JOURNAL
  DB10 --> JOURNAL
  F06 --> JOURNAL
  E07 --> OC

  classDef done fill:#2e7d32,color:#fff,stroke:#1b5e20;
  classDef partial fill:#f9a825,color:#111,stroke:#8d6e00;
  classDef open fill:#9e9e9e,color:#111,stroke:#616161;
  classDef blocked fill:#c62828,color:#fff,stroke:#8e0000;
  classDef unmeasured fill:#6a1b9a,color:#fff,stroke:#38006b;
  classDef planned fill:#1565c0,color:#fff,stroke:#003c8f;
  class S1,S2,S3,S4,DB06 done;
  class CH01,F01,GO10,DB01,GO09,E06 partial;
  class DB07,DB08,DB09,DB10,DB11,DB12,P08,E08,CH03,F03,F06,UI06,UI16,E07,E05,UIREST,BUILD open;
  class E09 blocked;
  class CH06 unmeasured;
  class SRC,CAT,MAP,GAP,TIME,JOURNAL,STORE,PAT,REG,RISK,SEQ,RANK,VALID,INFER planned;
```

## 2. Migration critical paths

**Product acceptance critical path (from the 2026-11-14 audit):**

`CHART-01 → CHART-03 → CHART-06 → E2E-05 → E2E-09`

**Phase 4.9.8 database path:**

`DB-06 → (DB-07 + DB-08) → DB-09 → (PROD-08 + DB-10 + DB-12) → E2E-08 → E2E-09`

**FTS path:**

`FTS-01 → FTS-03 → FTS-06 → UI-06 → E2E-05`

These tracks are related but not identical blockers. Chart drawing UX is required for final product acceptance, but must not by itself block offline technical-engine calculations or ML research once canonical data and point-in-time detector outputs are valid.

## 3. Migration baseline

| Stage / workstream | Status at audited baseline |
|---|---:|
| Stage 1 · Python-elimination baseline | ACCEPTED · 3/3 |
| Stage 2 · Production cutover + Rahavard parity | ACCEPTED · 14/14 |
| Stage 3 · Go data producers | ACCEPTED · 13/13 |
| Stage 4 · Production activation + client verification | ACCEPTED · 6/6 |
| Opportunity Center P0–P6 | IN PROGRESS · 9/66 (13.6%) |
| Phase 4.9.8 / P498 | OPEN · 1/9 (11.1%) |

Independent audit metrics (do not combine into one headline percentage):

- Architecture decisions closed: **24/26 = 92.3%**.
- Implementation tasks complete: **34/111 = 30.6%**; risk-weighted **32.7%**.
- Acceptance gates passed: **24/56 = 42.9%**; among measured gates **24/27 = 88.9%**.
- Task statuses: 34 COMPLETE, 33 PARTIAL, 33 OPEN, 1 BLOCKED, 8 NOT_MEASURED, 2 DEFERRED; 3 OUT_OF_SCOPE.

## 4. Phase 4.9.8 — remaining work

| ID | Task | Status | Depends on |
|---|---|---|---|
| DB-06 | Phase 4.9.7 technical DB build + initial validation | COMPLETE* | — |
| DB-07 | Global alias, candle geometry, coverage, adjustment numeric validity, representative Rahavard parity | OPEN | DB-06 |
| DB-08 | Iranian-market scope manifest; include/exclude/quarantine; USD-rate disposition | OPEN | DB-06 |
| DB-09 | Canonical schema, shared metadata, price-basis/provenance/ingestion/revision contract, workload indexes | OPEN | DB-07 + DB-08 |
| PROD-08 | TSETMC incremental continuity, idempotent batches, conflicts, session finalization, corporate actions | OPEN | DB-09 + DB-07 |
| DB-10 | PIT, walk-forward, survivorship-safe ML dataset v1 | OPEN | DB-09 |
| DB-11 | Explain 11.9 GB footprint, SQLite pages/freelist, per-table/index sizes and mode semantics | OPEN | DB-06 |
| DB-12 | Query / RAM / storage / index-build / ingestion benchmark | OPEN | DB-09 |
| E2E-08 | 19 Phase 4.9.8 validation and cutover gates | OPEN | DB-07/08/09/10/12 + PROD-08 |

`* DB-06 is complete as a separate artifact/mission branch (technical.db: 11,897,110,528 bytes; 69,180,503 rows; initial validation passed). It is NOT yet integrated into go-main or proven consumed by Go Runtime. Do not call it operationally integrated.`

Preserve Rahavard historical adjusted OHLC values unchanged. Never overwrite them with recomputed values or silently mix raw TSETMC prices into the adjusted series. Raw/adjusted basis, provenance, action lineage, timestamps and calendar must remain explicit.

## 5. Technical Engine Completion — owner-approved next workstream

This workstream is separate from the migration WBS snapshot and must now be tracked explicitly.

1. Inventory and reconcile **`docs/Indicator/`** (the exact GitHub folder specified by the owner), `docs/technical-indicators/inbox/`, the 64-row Telegram catalogue, existing frontend indicators/overlays, and Go indicator/candleedge modules.
2. Prune only the **active** Telegram catalogue. Preserve original source files and provenance.
3. Classify every relevant source: reuse-existing, import/adapt, detection primitive, context/confluence feature, risk/target feature, visualization-only, defer or reject. Check source file type and license; do not run EX4/EX5 binaries or blindly copy unknown/restrictive-license code.
4. Reuse the existing deterministic engine and its 26 PatternKinds/registry. Implement only genuine gaps; no parallel indicator or pattern engine.
5. Make accepted indicators contribute real computed values to pattern detection/features, not merely chart menu entries. Keep visualization separate from calculation semantics.
6. Enforce closed-bar/no-lookahead/prefix stability and distinguish `detected_at` / `available_at` from geometric anchor time. A pivot's right-bars delay must be reflected in when the event becomes knowable.
7. Do not start PatternQuality training until deterministic event outputs and point-in-time timestamps are valid.

Existing Telegram triage names three candidate gaps (S/R retest-breakout, wedge/channel detection, order-block quality scoring). They are candidates only: check `docs/Indicator/` and current code before implementing anything.

## 6. ML and model sequence

`Canonical DB → deterministic technical engine + FTS correctness → Market Signal Journal → PIT Feature Store + versioned labels → PatternQuality → five-state regime → volatility/risk → candle-sequence forecasting → Opportunity Discovery/ranking`

- First model is **pattern quality/outcome scoring**, not image-based pattern recognition. The deterministic engine detects/describes patterns; ML estimates conditional outcomes.
- Begin with a calibrated, interpretable/logistic baseline; compare LightGBM/CatBoost only where out-of-sample evidence justifies them.
- Labels start after actual event availability/confirmation time, not retrospective anchor time. Unresolved/timeout remains distinct from failure.
- Use chronological purged walk-forward validation, embargo, survivorship controls, trading cost/queue assumptions, calibration and paper research.
- FTS remains deterministic and authoritative. ML never overrides a canonical FTS veto.
- Python is research/training only. Go runtime consumes model outputs only through an explicit validated, versioned inference contract.

## 7. Daily roadmap maintenance rules

- Before every update, fetch the live `go-main` HEAD and inspect task-relevant code, commits, CI and evidence. Also inspect the latest migration-audit branch if one exists; do not assume yesterday's status remains true.
- Keep the active implementation base on `go-main`; never use legacy `main` as the base.
- Update task status only with fresh evidence. A commit/report by itself is not proof of runtime integration or acceptance. Keep COMPLETE, PARTIAL, OPEN, BLOCKED, DEFERRED and NOT_MEASURED distinct.
- Preserve accepted Stage 1–4. Do not reopen them absent contradictory new evidence.
- Keep Phase 4.9.8, Technical Engine Completion, Chart/FTS, Opportunity Center and ML as linked but separately trackable streams.
- Identify today's completed work, remaining blockers, parallelizable tasks, critical path changes and next concrete tasks.
- Update this file only for roadmap status/graph changes; do not modify application code, data assets, DBs or other roadmap files as part of the daily sync.
- A daily sync may commit this documentation file directly to `go-main` only. Do not merge branches, force-push, publish releases/tags, change production behavior, overwrite archives/databases, or make owner decisions.
- If no verified status changes occurred, do not create a no-op commit; still deliver the daily status report and explicitly say no change was verified.

## 8. Source documents

- [Migration audit branch](https://github.com/johnwarchief/BorsTerminal-src/tree/docs/migration-progress-audit-2026-11-14/docs/migration-progress)
- [Migration dependency graph](https://github.com/johnwarchief/BorsTerminal-src/blob/docs/migration-progress-audit-2026-11-14/docs/migration-progress/MIGRATION-DEPENDENCIES.mmd)
- [Migration progress dashboard](https://github.com/johnwarchief/BorsTerminal-src/blob/docs/migration-progress-audit-2026-11-14/docs/migration-progress/MIGRATION-PROGRESS.md)
- [Master execution roadmap](https://github.com/johnwarchief/BorsTerminal-src/blob/go-main/docs/MASTER-EXECUTION-ROADMAP.md)
- [ML engine roadmap](https://github.com/johnwarchief/BorsTerminal-src/blob/go-main/docs/ML-ENGINE-ROADMAP.md)
- [Local algorithmic learning architecture](https://github.com/johnwarchief/BorsTerminal-src/blob/go-main/docs/research/LOCAL-ALGORITHMIC-LEARNING-ARCHITECTURE.md)
- [Telegram indicator triage](https://github.com/johnwarchief/BorsTerminal-src/blob/go-main/docs/technical-indicators/TELEGRAM-CATALOG-TRIAGE-2026-11-03.md)
- [Indicator source folder](https://github.com/johnwarchief/BorsTerminal-src/tree/go-main/docs/Indicator)
