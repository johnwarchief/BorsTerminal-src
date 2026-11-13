# Migration Work Breakdown Structure

> **Snapshot:** branch `go-main` @ `ef6a8ba503bd` (2026-11-13) · snapshot date 2026-11-14 · generated 2026-11-13 21:36:39 UTC
> **Audit branch:** `docs/migration-progress-audit-2026-11-14` · live HEAD `ef6a8ba503bd`
> **Source of truth:** `MIGRATION-STATUS.json` · regenerate: `python docs/migration-progress/generate_progress.py`

هر Task شناسهٔ پایدار، شرح، وابستگی‌ها و شاهد پذیرش دارد. وضعیت‌ها فقط از شواهدِ قابل‌تکرار (کد/تست/کامیت/گزارش) گرفته شده‌اند؛ `DECIDED` به‌تنهایی `COMPLETE` نیست.

## WS1 — Architecture & Runtime (معماری و Runtime) — وضعیت کلی: نسبی

| ID | Task | وضعیت | ریسک | وابستگی | شاهد پذیرش |
|---|---|---|---|---|---|
| ARCH-01 | Target runtime architecture: borsd Go + frontend-v2 + Tauri v2 + SQLite, Python out of client runtime | COMPLETE | high | — | `backend-go/cmd/borsd/main.go`; `go test ./... = 55 pkgs ok @ ef6a8ba5`; `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.40.1` |
| ARCH-02 | Single-writer ownership per data domain (file lock, no parallel poller/writer) | COMPLETE | high | — | `backend-go/internal/instance/instance.go`; `backend-go/internal/tsetmc/lock_test.go`; `docs/STAGE3-GO-DATA-PRODUCERS-FINAL-REPORT.md#task10` |
| ARCH-03 | Process supervisor / lifecycle: single owner start-stop, readiness beyond /healthz, tray vs exit, no orphan backend 🔒مالک | PARTIAL | high | ARCH-01 | `backend-go/cmd/borsd/lifecycle.go`; `frontend/src-tauri/src/lib.rs (no borsd spawn/supervision)`; `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.40.5` |
| ARCH-04 | Generation resolver: serve active generation, atomic handle swap, rollback, pending_reload detection | COMPLETE | high | DB-04 | `backend-go/internal/generation/resolver.go`; `backend-go/cmd/borsd/app.go#DataStatus/Reload/Rollback`; `docs/opportunity-center/IMPLEMENTATION-ROADMAP.md#P0.1` |
| ARCH-05 | Multi-window / multi-instance core ownership (shared core, no parallel producer) | PARTIAL | medium | ARCH-02 | `backend-go/internal/instance/instance.go`; `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.11` |
| ARCH-06 | Research/Runtime separation: Python research-only, Go runtime, research.db outside producer data_dir | PARTIAL | medium | ARCH-01 | `backend-go/internal/researchdb/`; `docs/opportunity-center/adr/ADR-OC-001-runtime-research-split.md`; `docs/ML-ENGINE-ROADMAP.md#2` |

## WS2 — Backend Go (بک‌اند Go) — وضعیت کلی: نسبی

| ID | Task | وضعیت | ریسک | وابستگی | شاهد پذیرش |
|---|---|---|---|---|---|
| GO-01 | borsd runtime binary + HTTP API server | COMPLETE | high | — | `backend-go/cmd/borsd/`; `go test ./... = 55 pkgs ok, 0 FAIL @ ef6a8ba5` |
| GO-02 | API route coverage vs legacy product (70-endpoint matrix; not-ported routes explicit 501) | PARTIAL | high | GO-01 | `docs/migration/python-elimination/03-baseline-and-acceptance-gates.md#70-endpoint-matrix`; `backend-go/internal/httpapi/server.go#L81-90 (watchlist/matrix, sync/codal/* still 501)` |
| GO-03 | API honesty job contract: job_id/status_url, no 200=started, explicit 501 when no job | COMPLETE | high | GO-01 | `backend-go/internal/sync/handlers.go#NewHandlerWithJobs/StartExclusive`; `backend-go/internal/jobs/`; `docs/opportunity-center/IMPLEMENTATION-ROADMAP.md#P0.6` |
| GO-04 | Full operational-path API honesty audit (Sync/Update/Refresh/Pause/Resume/Stop effect verification) | OPEN | medium | GO-03 | `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.40.9` |
| GO-05 | Read-only DB access enforcement: mode=ro symmetry, AST guard vs sql.Open, zero disk writes in read mode | COMPLETE | high | — | `backend-go/internal/db/arch_test.go`; `backend-go/internal/db/db_test.go`; `backend-go/internal/market/lifecycle_test.go`; `docs/migration/python-elimination/03-baseline-and-acceptance-gates.md#checklist` |
| GO-06 | Graceful shutdown with deadline + connection drain + --no-loops background restraint | COMPLETE | medium | GO-01 | `backend-go/cmd/borsd/lifecycle_test.go`; `docs/migration/python-elimination/03-baseline-and-acceptance-gates.md#checklist` |
| GO-07 | Adaptive cadence + circuit breaker + rate limit with Retry-After precedence | COMPLETE | medium | GO-01 | `backend-go/internal/worker/ratelimit_test.go`; `backend-go/internal/worker/cadence.go tests`; `docs/STAGE3-GO-DATA-PRODUCERS-FINAL-REPORT.md#task11-12` |
| GO-08 | FTS 5-axis Go recalculation engine (CPython round-half-even parity) + funnel | COMPLETE | high | GO-01 | `backend-go/internal/fundamental/`; `backend-go/internal/funnel/`; `docs/STAGE3-GO-DATA-PRODUCERS-FINAL-REPORT.md#task4` |
| GO-09 | Notification backend engine: classify/dedup/rate-limit/quiet-hours/outbox + long-poll feed | PARTIAL | medium | GO-01 | `backend-go/internal/notifications/ (classify/feed/handlers + tests)`; `backend-go/internal/ocnotify/ (store/handlers + tests)` |
| GO-10 | Opportunity Center read-models / registry backend (ocdb, ocdata) | PARTIAL | medium | GO-01, DB-01 | `backend-go/internal/ocdb/ (3 files, 1 test)`; `backend-go/internal/ocdata/handlers.go (0 tests)` |

## WS3 — Data Producers (تولیدکنندگان داده) — وضعیت کلی: نسبی

| ID | Task | وضعیت | ریسک | وابستگی | شاهد پذیرش |
|---|---|---|---|---|---|
| PROD-01 | bors-producer independent CLI binary + subcommands + security gate | COMPLETE | high | — | `backend-go/cmd/bors-producer/main.go`; `backend-go/cmd/bors-producer/main_test.go`; `docs/STAGE3-GO-DATA-PRODUCERS-FINAL-REPORT.md#task13` |
| PROD-02 | CODAL polite fetcher + discovery (Retry-After, backoff, circuit breaker, no IP-rotation-as-architecture) | COMPLETE | medium | PROD-01 | `backend-go/internal/codal/fetcher.go`; `backend-go/internal/codal fetcher tests (Retry-After seconds/HTTP-date)`; `docs/STAGE3-GO-DATA-PRODUCERS-FINAL-REPORT.md#task1` |
| PROD-03 | CODAL structured extractor + validator + unit normalization + quarantine | COMPLETE | high | PROD-02 | `backend-go/internal/codal/extractor_test.go`; `backend-go/internal/codal/validator.go, units.go`; `docs/STAGE3-GO-DATA-PRODUCERS-FINAL-REPORT.md#task2-3` |
| PROD-04 | CODAL central Producer/Client deployment: host, scheduling, signed snapshot distribution infra, key custody, SLA 🔒مالک | PARTIAL | high | PROD-01, DB-03 | `docs/STAGE4-PRODUCTION-ACTIVATION-FINAL-REPORT.md#WS-A (daemon 06:00 UTC schedule)`; `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.40.2 (OPEN deployment details)` |
| PROD-05 | TSETMC live market watch + real/legal client-type history | COMPLETE | high | PROD-01 | `backend-go/internal/tsetmc/marketwatch.go, clienttype.go`; `docs/STAGE3-GO-DATA-PRODUCERS-FINAL-REPORT.md#task8` |
| PROD-06 | TSETMC adjustment events + Rahavard parity adjustment engine (zero absolute diff on cohort) | COMPLETE | high | PROD-05 | `backend-go/internal/tsetmc/adjust_events.go`; `docs/STAGE3-GO-DATA-PRODUCERS-FINAL-REPORT.md#task9 (0.000000 diff)` |
| PROD-07 | Producer snapshot allowlist: only market.db/codal.db; research/oc_client/user never published | COMPLETE | high | PROD-01 | `backend-go/cmd/bors-producer/pipeline.go#L233-235 (explicit allowlist, P0.2)`; `docs/opportunity-center/IMPLEMENTATION-ROADMAP.md#P0.2` |
| PROD-08 | TSETMC incremental continuity into canonical technical.db: idempotent batches, conflict logging, session finalization, corporate-action producer | OPEN | high | DB-09, DB-07 | `attached 4.9.8 mission Task 5`; `docs/CANDLE-CONTRACT.md` |
| PROD-09 | Final production market.db writer selection & full operational validation (Go live feed vs legacy) 🔒مالک | PARTIAL | high | PROD-05, PROD-06 | `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.40.3 (OPEN final producer)` |

## WS4 — Database & Data Integrity (دیتابیس و صحت داده) — وضعیت کلی: نسبی

| ID | Task | وضعیت | ریسک | وابستگی | شاهد پذیرش |
|---|---|---|---|---|---|
| DB-01 | Schema versioning + migration runner + backup/rollback (PRAGMA user_version) for oc_client.db/research.db | PARTIAL | high | — | `backend-go/internal/migrate/ (2 files, 1 test)`; `docs/opportunity-center/IMPLEMENTATION-ROADMAP.md#P0.3`; `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.40.7 (OPEN schema details)` |
| DB-02 | Snapshot builder + unified manifest (LZMA2 + VACUUM) | COMPLETE | medium | — | `backend-go/internal/snapshot/builder.go, manifest.go`; `docs/STAGE3-GO-DATA-PRODUCERS-FINAL-REPORT.md#task5` |
| DB-03 | Minisign signer + publisher; tampered content/signature rejected | COMPLETE | high | DB-02 | `backend-go/internal/snapshot signer tests (tamper rejection)`; `docs/STAGE4-PRODUCTION-ACTIVATION-FINAL-REPORT.md#key-audit (KeyID 830BF752EF10076)` |
| DB-04 | Atomic Windows generation applier + rollback + open-file handling | COMPLETE | high | DB-02 | `backend-go/internal/snapshot/applier_test.go (lock simulation, rollback)`; `docs/STAGE3-GO-DATA-PRODUCERS-FINAL-REPORT.md#task7` |
| DB-05 | Client snapshot download/verify/apply + user.db byte-for-byte preservation + restart reload | COMPLETE | high | DB-03, DB-04 | `docs/STAGE4-PRODUCTION-ACTIVATION-FINAL-REPORT.md#WS-F (user.db SHA-256 identical, v1.0.98, 91,547,928 bytes)` |
| DB-06 | Phase 4.9.7 separated technical DB build + 5 validation gates (reference immutable) | COMPLETE | high | — | `D:/BorsTerminal-data/separation/technical.db (11,897,110,528 B; 69,180,503 rows)`; `mission/phase49-7-discovery:_audit/phase49-7/separation_validation.json (all_pass true)`; `commit 86d421fb (mission/phase49-7-discovery)` |
| DB-07 | Canonical DB comprehensive re-validation: global alias, candle geometry, historical coverage, adjustment numeric validity, representative-cohort Rahavard parity | OPEN | high | DB-06 | `attached 4.9.8 mission Task 2` |
| DB-08 | Iranian-market dataset scope manifest: included/excluded/quarantined per asset_class with counts/date ranges; usd_rate disposition 🔒مالک | OPEN | high | DB-06 | `attached 4.9.8 mission Task 3` |
| DB-09 | Canonical technical.db schema design + shared_metadata merge + data contract (price basis, provenance, ingestion batches, revisions) + workload indexes | OPEN | high | DB-07, DB-08 | `attached 4.9.8 mission Task 4`; `docs/CANDLE-CONTRACT.md` |
| DB-10 | ML dataset v1: point-in-time, walk-forward, survivorship-safe, reproducible manifest; batch read-only reads | OPEN | high | DB-09 | `attached 4.9.8 mission Task 7`; `docs/ML-ENGINE-ROADMAP.md#2 (DB-serving acceptance gate)` |
| DB-11 | Database size/schema audit: why 11.9 GB (page/freelist/dbstat, per-table/index sizes, mode semantics, vs legacy TSETMC DB) | OPEN | medium | DB-06 | `attached 4.9.8 mission Task 1` |
| DB-12 | Canonical DB performance & storage benchmark (open/connection, 1/5/10y queries, cohort, training window, RAM, index rebuild, ingestion latency) | OPEN | medium | DB-09 | `attached 4.9.8 mission Task 8` |
| DB-13 | Market.db corruption quarantine + separate-space rebuild + validated swap protocol | NOT_MEASURED | high | DB-04 | `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.12` |
| DB-14 | User-data backup/retention policy + real restore drill on independent copy | OPEN | high | DB-01 | `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.15`; `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.40.7` |

## WS5 — Tauri-Go Security (امنیت Tauri-Go) — وضعیت کلی: نسبی

| ID | Task | وضعیت | ریسک | وابستگی | شاهد پذیرش |
|---|---|---|---|---|---|
| SEC-01 | Local API guard: strict Host/Origin, closed CORS, per-launch token, CSRF for cookie writes | COMPLETE | high | GO-01 | `backend-go/internal/auth/guard.go, token.go`; `backend-go/cmd/borsd/main.go#L92-104 (wired)`; `backend-go/internal/auth/guard_test.go, token_test.go` |
| SEC-02 | Loopback-only shell URL enforcement in Tauri host | COMPLETE | high | — | `frontend/src-tauri/src/lib.rs#ensure_loopback_shell_url`; `frontend/src-tauri/src/lib.rs tests (non-loopback refused)` |
| SEC-03 | Minimal Tauri capabilities (core/updater/process only; no remote capability) | COMPLETE | medium | — | `frontend/src-tauri/capabilities/default.json`; `frontend/src-tauri/tauri.conf.json (CSP default-src self)` |
| SEC-04 | Tauri-Go threat model + executive security tests (CSRF, DNS rebinding, port squat, local process access, secret leakage) 🔒مالک | PARTIAL | high | SEC-01, SEC-02 | `backend-go/internal/auth/guard_test.go (Origin/CSRF)`; `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.40.4 (OPEN threat model)` |
| SEC-05 | Secrets in OS credential store (DPAPI/Credential Manager), fail-closed auth, no secrets in export | OPEN | high | — | `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.10` |
| SEC-06 | Code-signing chain + key separation (DATA/APP/APPROVAL/REGISTRY), offline approval, key rotation 🔒مالک | PARTIAL | high | DB-03 | `docs/STAGE4-PRODUCTION-ACTIVATION-FINAL-REPORT.md#key-audit (Minisign data key)`; `docs/opportunity-center/adr/ADR-OC-004-signed-bundles.md (OPEN key separation)` |
| SEC-07 | Real-order / AutoClicker authorization & safety design | DEFERRED | high | — | `docs/BorsTerminal-Desktop-Migration-Decisions.md#8 (deferred to its own mission)` |

## WS6 — Frontend & UI (فرانت‌اند و رابط) — وضعیت کلی: نسبی

| ID | Task | وضعیت | ریسک | وابستگی | شاهد پذیرش |
|---|---|---|---|---|---|
| UI-01 | frontend-v2 app shell + collapsible sidebar navigation | PARTIAL | medium | ARCH-01 | `frontend-v2/src/app/shell/AppShell.tsx, Sidebar.tsx`; `vitest 107 files / 867 tests passed @ ef6a8ba5` |
| UI-02 | Market board page (filters, detail drawer, pulse bar, mini-chart, suspicious panel, export) | PARTIAL | medium | UI-01 | `frontend-v2/src/features/market/routes/MarketPage.tsx`; `docs/MIGRATION-GAP-MATRIX-2026-10-27.md#market (historical gap list)` |
| UI-03 | Market-status page (15+ metrics: histogram, thermometer, depth, real/legal, phase, industry, treemap, order flow) | PARTIAL | medium | UI-01 | `frontend-v2/src/features/market/routes/MarketStatusPage.tsx`; `docs/MIGRATION-GAP-MATRIX-2026-10-27.md#market-status` |
| UI-04 | Fundamental page (FTS card, drilldown, axis rail, screener table, settings, industry, seasonal, calendar) | PARTIAL | medium | UI-01, GO-08 | `frontend-v2/src/features/fundamental/routes/FundamentalPage.tsx` |
| UI-05 | Technical page / chart workspace | PARTIAL | medium | UI-01, CHART-01 | `frontend-v2/src/features/technical/routes/TechnicalPage.tsx` |
| UI-06 | FTS screener page (/fts-screen): funnel, gate, arbitration, dossier, screening table | OPEN | high | UI-01, FTS-01 | `frontend-v2/src/app/App.tsx (no /fts-screen route)`; `frontend-v2/src/app/shell/Sidebar.tsx#L20 (nav link present)` |
| UI-07 | Portfolio page (performance/risk/asset dashboard, link to technical/fundamental/FTS) | OPEN | medium | UI-01 | `frontend-v2/src/app/App.tsx (no /portfolio route)`; `frontend-v2/src/app/shell/Sidebar.tsx#L24 (nav link present)` |
| UI-08 | Watchlist management (add/remove + dedicated view) | PARTIAL | low | UI-02 | `frontend-v2/src/features/market/components/WatchlistButton.tsx`; `backend-go/internal/watchlist tests (ok)` |
| UI-09 | Settings page (user prefs, FTS config, notification settings /settings/notifications, start page, tray, autostart) 🔒مالک | OPEN | medium | UI-01 | `frontend-v2/src/app/App.tsx (no settings route)` |
| UI-10 | In-app notifications center page + unread badge + feed | COMPLETE | low | GO-09 | `frontend-v2/src/features/notifications/ui/NotificationsPage.tsx`; `frontend-v2/src/app/shell/AppShell.tsx (useNotificationsFeed, unreadCount)` |
| UI-11 | Strategy-tree (5-page FTS charts) migration | OPEN | medium | UI-06 | `docs/MIGRATION-GAP-MATRIX-2026-10-27.md#strategy-tree`; `docs/opportunity-center/DECISION-LOG.md#OC-D-018 (frozen)` |
| UI-12 | Engine-lab page (chart engine comparison: mountMs/fps/heap) | OPEN | low | CHART-07 | `docs/MIGRATION-GAP-MATRIX-2026-10-27.md#engine-lab` |
| UI-13 | Named workspaces: save/restore layout, per-panel symbol sync groups, adaptive layout, configurable start page | OPEN | medium | UI-01 | `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.32-12.34` |
| UI-14 | RTL/Persian-only UI + numeric alignment + dark/light themes + brand/semantic color separation | NOT_MEASURED | medium | UI-01 | `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.19, #12.36` |
| UI-15 | Command palette + discoverable/customizable keyboard shortcuts | OPEN | low | UI-01 | `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.18, #12.38.20` |
| UI-16 | Opportunity Lab / Today UI (P3.4 read model + P5.4 lab client, inspector, evidence states) | OPEN | medium | GO-10, FTS-03 | `docs/opportunity-center/IMPLEMENTATION-ROADMAP.md#P3.4, #P5.4`; `docs/opportunity-center/prototype (outside runtime)` |
| UI-17 | Visual acceptance at 1366x768 and 1920x1080 with real data (states: loading/error/stale/dense/multi-panel) | NOT_MEASURED | medium | UI-02, UI-05 | `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.36, #12.40.10` |

## WS7 — Chart & Technical Engine (نمودار و موتور تکنیکال) — وضعیت کلی: نسبی

| ID | Task | وضعیت | ریسک | وابستگی | شاهد پذیرش |
|---|---|---|---|---|---|
| CHART-01 | Chart engine integration (klinecharts v10) in frontend-v2 | PARTIAL | high | ARCH-01 | `frontend-v2/package.json (klinecharts ^10.1.0)`; `frontend-v2/src/features/chart/ (api/ui/__tests__, 1 test file)` |
| CHART-02 | Adjusted-candle priority + raw mode preserved + price-basis resolver | COMPLETE | high | — | `backend-go/internal/pricebasis/pricebasis.go`; `candle_contract.py`; `docs/STAGE2-FINAL-ACCEPTANCE-AND-STAGE3-READINESS.md#adjusted-parity` |
| CHART-03 | Drawing tools (fibonacci/channel/fork/measure/annotation) + save/restore + valid raw<->adjusted mapping | OPEN | high | CHART-01 | `frontend-v2/src/features/chart/ (no drawing/overlay/fibonacci code found)`; `docs/MIGRATION-GAP-MATRIX-2026-10-27.md#technical` |
| CHART-04 | Buy/sell queue, depth, replay, multi-chart compare, indicator panel, pattern toggles | OPEN | medium | CHART-01 | `docs/MIGRATION-GAP-MATRIX-2026-10-27.md#technical` |
| CHART-05 | Rahavard technical parity (OHLC/adjustment/indicators) on representative cohort | PARTIAL | high | CHART-02 | `docs/STAGE2-FINAL-ACCEPTANCE-AND-STAGE3-READINESS.md#5-symbol-parity (zero diff)`; `tools/parity/cases_b1..b7.json` |
| CHART-06 | Browser-level chart acceptance (roadmap gate D): real data, coordinate transforms, drawing persistence, visual comparison | NOT_MEASURED | high | CHART-01, CHART-03 | `docs/MASTER-EXECUTION-ROADMAP.md#D (browser-level evidence required)` |
| CHART-07 | Chart engine comparison / second-engine decision with vital-tool quality proof 🔒مالک | OPEN | medium | UI-12 | `docs/BorsTerminal-Desktop-Migration-Decisions.md#6` |
| CHART-08 | Kronos / candle-sequence forecast integration gate (official inference path, real OHLCV+amount, session timestamps, benchmarks) | DEFERRED | medium | DB-10 | `docs/ML-ENGINE-ROADMAP.md#4.4 (gate not accepted; Go calls legacy tools/kronos_inference.py)` |

## WS8 — FTS & Fundamental (FTS و بنیادی) — وضعیت کلی: نسبی

| ID | Task | وضعیت | ریسک | وابستگی | شاهد پذیرش |
|---|---|---|---|---|---|
| FTS-01 | FTS source-of-truth reconciliation + parity harness (booklet/OWNER_RULINGS rule inventory; Python/Go/Chart conformance; golden vectors) | PARTIAL | high | GO-08 | `tools/parity/cases_b1..b7.json, compare_fundamental_10.py`; `docs/FTS-7-Phase-Progress.md`; `docs/opportunity-center/IMPLEMENTATION-ROADMAP.md#P0.5`; `docs/opportunity-center/OPEN-QUESTIONS.md#Q5 (technical gate OPEN, blocks P3)` |
| FTS-02 | FTS 5-axis evidence matrix (input/axis values/missing-data/reason/verdict independently verified) | PARTIAL | high | GO-08 | `docs/STAGE3-GO-DATA-PRODUCERS-FINAL-REPORT.md#task4`; `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.40.8 (OPEN matrix)` |
| FTS-03 | FTS Adapter/Envelope (fts.envelope/1, tri-state, NA kind, ruleset/config hash) consumed by Today/OC | OPEN | high | FTS-01 | `docs/opportunity-center/IMPLEMENTATION-ROADMAP.md#P3.1, #P3.2`; `docs/opportunity-center/adr/ADR-OC-008-fts-canonical-adapter.md` |
| FTS-04 | FTS preserved as independent canonical strategy (consumed, not reimplemented) | COMPLETE | high | — | `docs/opportunity-center/DECISION-LOG.md#OC-D-003`; `backend-go/internal/fundamental/ (separate engine)` |
| FTS-05 | FTS local-data execution + result freshness/data-version labeling + recompute on new valid data | PARTIAL | medium | GO-08 | `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.4, #12.24, #12.40.8` |
| FTS-06 | FTS golden vectors + Go/Python/Chart ruleset/config alignment; remove dual config from Approved path | OPEN | high | FTS-01, FTS-03 | `docs/opportunity-center/IMPLEMENTATION-ROADMAP.md#P3.2` |

## WS9 — Build & Installer (بیلد و نصاب) — وضعیت کلی: نسبی

| ID | Task | وضعیت | ریسک | وابستگی | شاهد پذیرش |
|---|---|---|---|---|---|
| BUILD-01 | Production package/process-tree proof: no Python/Uvicorn/FastAPI in client runtime (onedir contract) | COMPLETE | high | ARCH-01 | `docs/STAGE2-FINAL-ACCEPTANCE-AND-STAGE3-READINESS.md#onedir_contract_v11.py + live process test (Go 13.3 MB)` |
| BUILD-02 | Final Tauri production build chain: borsd + frontend-v2 dist + Tauri shell, machine-audited package contents, single updater owner 🔒مالک | PARTIAL | high | BUILD-01, SEC-03 | `frontend/src-tauri/tauri.conf.json (NSIS/MSI, createUpdaterArtifacts)`; `scripts/build_shell.py, scripts/build_installer_exe.py`; `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.40.6 (OPEN final chain)` |
| BUILD-03 | Installer hardening: per-user least privilege, silent upgrade, data boundary, Inno protections preserved/revalidated | PARTIAL | high | BUILD-02 | `installer/bors_setup.iss`; `docs/MASTER-EXECUTION-ROADMAP.md#F.4` |
| BUILD-04 | WebView2 runtime check + offline package + repair scenario + clear prerequisite failure | NOT_MEASURED | medium | BUILD-02 | `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.5, #12.8`; `docs/MASTER-EXECUTION-ROADMAP.md#F.3` |
| BUILD-05 | First-install/first-launch state machine + low-resource profile + first-launch acceptance | OPEN | high | BUILD-02 | `docs/MASTER-EXECUTION-ROADMAP.md#F.1` |
| BUILD-06 | Dependency license audit + notices + redistribution obligations before distributable package | OPEN | medium | BUILD-02 | `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.29` |
| BUILD-07 | Version anchor synchronization (11 anchors) guard | COMPLETE | low | — | `docs/STAGE4-PRODUCTION-ACTIVATION-FINAL-REPORT.md#WS-D (11/11 anchors, 0 failed)`; `dev/version_anchor_guard.py` |

## WS10 — Update & Recovery (به‌روزرسانی و بازیابی) — وضعیت کلی: نسبی

| ID | Task | وضعیت | ریسک | وابستگی | شاهد پذیرش |
|---|---|---|---|---|---|
| UPD-01 | Tauri updater signed artifacts + embedded pubkey + endpoint configuration | PARTIAL | high | BUILD-02, DB-03 | `frontend/src-tauri/tauri.conf.json#plugins.updater (pubkey, latest.json endpoint)`; `docs/STAGE4-PRODUCTION-ACTIVATION-FINAL-REPORT.md (snapshot update proven)` |
| UPD-02 | Update compatibility: legacy-version fallback, delta rules, full-package fallback, supported-version policy | OPEN | high | UPD-01 | `docs/MASTER-EXECUTION-ROADMAP.md#F.2` |
| UPD-03 | Interrupted update / power-loss / locked-file / partial-download recovery matrix | PARTIAL | high | DB-04, UPD-01 | `backend-go/internal/snapshot/applier_test.go (rollback)`; `docs/MASTER-EXECUTION-ROADMAP.md#F.2 (full matrix pending)` |
| UPD-04 | User data preservation across update (user.db/settings/workspaces/drawings untouched) | COMPLETE | high | DB-05 | `docs/STAGE4-PRODUCTION-ACTIVATION-FINAL-REPORT.md#WS-F (user.db SHA-256 identical)` |
| UPD-05 | Update scheduling per user preference; no forced close/restart during market/sensitive ops | OPEN | medium | UPD-01 | `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.17` |
| UPD-06 | Uninstall keeps user/market data by default; explicit full-wipe with summary | OPEN | medium | BUILD-03 | `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.16` |
| UPD-07 | App-version rollback (not only DB generation) preserving data/settings; incompatible downgrade detected | PARTIAL | high | UPD-01, DB-01 | `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.31, #7 (rollback)` |

## WS11 — Observability & Reliability (پایش و تاب‌آوری) — وضعیت کلی: نسبی

| ID | Task | وضعیت | ریسک | وابستگی | شاهد پذیرش |
|---|---|---|---|---|---|
| OBS-01 | Health/readiness + data status (serving vs pointer, pending_reload, schema version) | COMPLETE | medium | ARCH-04 | `backend-go/cmd/borsd/app.go#DataStatus`; `backend-go/internal/ocdata/handlers.go (status endpoints)` |
| OBS-02 | Component health / limited restart with backoff / degraded mode / no stale-as-live | PARTIAL | high | ARCH-03, GO-07 | `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.6`; `backend-go/internal/worker/ratelimit.go (circuit breaker)` |
| OBS-03 | Structured local diagnostics (opt-in export, redaction, no default external send) | OPEN | medium | — | `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.3` |
| OBS-04 | Error UX: human-readable cause + suggested action + details drawer + severity separation + no false success | NOT_MEASURED | medium | UI-01 | `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.26` |
| OBS-05 | Per-domain data freshness indicators + stale labeling (board/candle/technical/FTS independent) | PARTIAL | medium | OBS-01 | `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.24, #12.38.18` |
| OBS-06 | OS native toast via tauri-plugin-notification + AUMID/shortcut + long-poll bridge + ack/click (P1.7/P4.8) | OPEN | medium | GO-09, SEC-03 | `frontend/src-tauri/Cargo.toml (NO tauri-plugin-notification)`; `docs/opportunity-center/IMPLEMENTATION-ROADMAP.md#P1.7, #P4.8`; `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.41.3 (verified: no plugin)` |
| OBS-07 | Notification center + settings full (filters/groups/read, sound/preview/quiet-hours, deep link) (P5.8) 🔒مالک | PARTIAL | medium | UI-10, UI-09 | `docs/opportunity-center/IMPLEMENTATION-ROADMAP.md#P5.8` |
| OBS-08 | OC observability: /api/oc/status, audit, health (no PII), job/status (P5.6) | PARTIAL | low | GO-10 | `backend-go/internal/ocdata/handlers.go` |
| OBS-09 | Performance baseline at this commit: cold/warm start, time-to-ready, RAM/CPU process tree, p95/p99 latency, dropped updates | NOT_MEASURED | high | ARCH-01 | `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.1, #12.27`; `docs/MIGRATION-PERF-BASELINE-2026-10-27.md (historical, not this commit)` |
| OBS-10 | Crash recovery / half-done operations policy (checkpoint, dedup ids, atomic txn resolution, no blind retry of external effects) | PARTIAL | high | DB-04, ARCH-02 | `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.6` |

## WS12 — End-to-End Acceptance (پذیرش انتهابه‌انتها) — وضعیت کلی: مسدود

| ID | Task | وضعیت | ریسک | وابستگی | شاهد پذیرش |
|---|---|---|---|---|---|
| E2E-01 | Stage 1 exit gate: Python-elimination baseline (110/110 suites, AST guard, 70-endpoint matrix) | COMPLETE | high | GO-05, GO-06 | `docs/migration/python-elimination/03-baseline-and-acceptance-gates.md (Stage 1 Complete, Hard Gate Enforced)` |
| E2E-02 | Stage 2 acceptance: production cutover + Rahavard adjustment parity + Stage 3 readiness | COMPLETE | high | E2E-01, BUILD-01, CHART-05 | `docs/STAGE2-FINAL-ACCEPTANCE-AND-STAGE3-READINESS.md (READY_FOR_STAGE3_WITH_PARALLEL_WORK)` |
| E2E-03 | Stage 3 acceptance: 15 producer tasks across workstreams A-F | COMPLETE | high | E2E-02, PROD-01, PROD-02, PROD-03, PROD-05, PROD-06, DB-02, DB-03, DB-04 | `docs/STAGE3-GO-DATA-PRODUCERS-FINAL-REPORT.md (15/15 PASS)` |
| E2E-04 | Stage 4 acceptance: production activation + Windows client verification | COMPLETE | high | E2E-03, DB-05, BUILD-07 | `docs/STAGE4-PRODUCTION-ACTIVATION-FINAL-REPORT.md (STAGE4_PRODUCTION_ACTIVATED_CLIENT_VERIFIED)`; `commit 11f4b128, tag v1.0.98, run 42508665247` |
| E2E-05 | Final product acceptance gate (12.40.10): clean install, process-tree no Python, all capabilities, fault/concurrency scenarios, parity, UI resolutions | OPEN | high | BUILD-02, UI-06, UI-07, UI-09, CHART-06, FTS-01, OBS-09, UPD-02 | `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.40.10` |
| E2E-06 | OC P0 gate: all P0 tests + NOT_MEASURED report (P0.1-P0.8) | PARTIAL | high | ARCH-04, PROD-07, SEC-01, GO-03, DB-01, FTS-01, GO-09 | `docs/opportunity-center/IMPLEMENTATION-ROADMAP.md#P0-Gate` |
| E2E-07 | OC P1-P6 delivery (contracts/registry, workbench, FTS adapter/Today, runtime/3-users, policy/compare/lab, generation/AI/GPU) 🔒مالک | OPEN | medium | E2E-06 | `docs/opportunity-center/IMPLEMENTATION-ROADMAP.md#P1-P6` |
| E2E-08 | Phase 4.9.8 validation & cutover gates (19 gates: reference_immutable ... rollback) | OPEN | high | DB-07, DB-08, DB-09, PROD-08, DB-10, DB-12 | `attached 4.9.8 mission Task 9 (19-gate table)` |
| E2E-09 | Owner acceptance for production cutover / legacy-version retirement 🔒مالک | BLOCKED | high | E2E-05, E2E-08 | `docs/BorsTerminal-Desktop-Migration-Decisions.md#9, #12.3, #12.40.10` |
| E2E-10 | Windows 11 reference acceptance + Windows 10 conditional compatibility proof | NOT_MEASURED | medium | E2E-05 | `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.13` |
| E2E-11 | Android canonical synchronization lane | OUT_OF_SCOPE | low | — | `docs/MASTER-EXECUTION-ROADMAP.md#C`; `docs/BorsTerminal-Desktop-Migration-Decisions.md#2 (no Android app yet)` |
| E2E-12 | Automatic cloud sync between computers | OUT_OF_SCOPE | low | — | `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.22 (local-first; cloud sync not in scope)` |
| E2E-13 | Commercial/public distribution & multi-language support infrastructure | OUT_OF_SCOPE | low | — | `docs/BorsTerminal-Desktop-Migration-Decisions.md#12.20 (personal project, limited distribution), #12.19 (Persian-only)` |

