# Stage 2 Execution Plan: Go Production Backend + Frontend V2 Integration

**Baseline:** `28c5146c771271beaf758ad9dc28c2272608d461`  
**Active Branch:** `mission/stage2-go-production-cutover-2026-11-07`  
**Architecture:** Go (`borsd`) Backend + React TypeScript (`frontend-v2`) + Tauri + Rust + SQLite.  
**Execution Mode:** Subagent-Driven Development (SDD) with independent implementer subagents and task reviewers.

---

## Global Constraints

1. **No Python in Production:** The final production runtime must not require Python interpreter, FastAPI, or Python dependencies.
2. **Single Writer SQLite:** `market.db` and `codal.db` are opened strictly `mode=ro` with `PRAGMA query_only = ON`. `user.db` is owned by Go; under `--read-only`, all writes to disk are refused.
3. **No Direct `sql.Open`:** All database handles must come exclusively from `internal/db` (`OpenRO`/`OpenRW`), strictly verified by AST guard.
4. **Honest Numerical & Analytical Parity:** No mocked 200 responses, no fabricated calculations, no fake passes. Differences are categorized scientifically.
5. **Preserve Capabilities:** Do not simplify or delete UI/chart/analytical capabilities.
6. **Continuous Delivery with Review Checks:** Each task produces working code, tested behavior, and passes spec & quality review.

---

## Task Matrix

| Task | Title | Scope | Deliverables |
| :--- | :--- | :--- | :--- |
| **Task 1** | **V2 API Contract Audit & Mapping** | Phase 2A, P2 Doc Alignment | Source scan of all call sites in `frontend-v2`, contract definitions, `docs/STAGE2-V2-API-CONTRACT.md` |
| **Task 2** | **Go CI Linux Portability Fixes** | P1 Portability | Fix `TestDataDirPrecedence` & `TestCalendarPath` for cross-platform Linux/Windows CI |
| **Task 3** | **Graceful Shutdown & Go-V2 Connection** | Phase 2B, P1 Shutdown | Hard-timeout 5s handling in `RunServer`, context cancellation, proxy & baseUrl config |
| **Task 4** | **Market Board & Mstat Vertical Integration** | Phase 2C (A, D) | End-to-end integration for Board, Delta, Sync-State, Tape-History, 10 Mstat panels |
| **Task 5** | **Technical & Fundamental Vertical Integration** | Phase 2C (B, C) | End-to-end integration for ChartDB, Indicators, KeyLevels, Patterns, Fundamental Cards |
| **Task 6** | **FTS Funnel, User Features & Persistence** | Phase 2C (E, F), Phase 2E | End-to-end integration for Funnel, Screener, Watchlist, Portfolio, `user.db` single-writer |
| **Task 7** | **Calculation Parity & Scientific Benchmark** | Phase 2D, P2 Benchmark | Parity test suite against 5 core symbols, fair benchmark calibration, `docs/STAGE2-PARITY-REPORT.md` |
| **Task 8** | **Tauri Desktop Shell & Final Milestones** | Phase 2F, Gate E | Tauri sidecar / lifecycle wiring, final deliverables (`STAGE2-INTEGRATION-STATUS.md`, `STAGE2-DECISIONS.md`), whole-branch review |

---

## SDD Workspace

- **Workspace Directory:** `.superpowers/sdd/stage2-go-production/`
- **Ledger:** `.superpowers/sdd/stage2-go-production/progress.md`
