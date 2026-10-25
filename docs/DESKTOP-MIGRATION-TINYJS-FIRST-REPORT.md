# BorsTerminal — TinyJS-First Desktop Migration Report (M1.5)

- **Date:** 2026-10-25
- **Mission branch:** `mission/desktop-tinyjs-first-2026-10-24`
- **Baseline:** `origin/main` at `b5f5f6c` (unchanged; no merge, rebase, tag or release)
- **Evidence commit before this report:** `a85b076`
- **Verdict:** **`TINYJS_ADVANCE`** — advance TinyJS to a bounded packaging/acceptance mission. This is **not** production-migration approval, and it is **not** a declaration that TinyJS is the final production winner.

## 1. Executive summary

TinyJS 0.65 passed the measured feasibility gates that can be closed on this host: it starts the same React/Python application, preserves the loopback Host/Origin guard, renders real market/FTS data, switches chart timeframe/adjustment/symbol, shows the corrected company name, survives startup failure with a user-visible error, closes cleanly, and leaves no sidecar or WebView2 processes after a shell crash. Its cold-run medians were 17.0 s to sidecar readiness, 21.9 s to a visible window, 39.1 s to a usable board, 77.3 s to a usable chart and 83.8 s to a usable fundamental page (n=3, single-core host; descriptive only).

Tauri 2.12.5 (GNU build) rendered the same screens with equal chart/FTS fidelity and comparable median timings. It did **not** clear the lifecycle gate: killing the shell after the board left 8 orphan processes and an open loopback port, and one of three graceful closes left 3 WebView2 processes behind. Its official Windows MSVC/NSIS/WiX packaging, signing and updater were never built or tested; the GNU executable is not an official Windows package.

Neither candidate has a production install story yet. Both prototypes still spawn a development `.venv` Python; neither bundles the Python runtime, and neither has a signed installer, updater/rollback, uninstall test, fixed WebView2 bootstrapper or a license audit. The candidate shell sizes (TinyJS 7.85 MB, Tauri 21.6 MB) are therefore **not** install footprints and are not compared as such. Those are the reasons the verdict advances TinyJS to the packaging stage rather than approving migration.

### Gate status at a glance

| Gate | Status | What remains / blocking condition |
|---|---|---|
| A — repo/baseline | PASS | none |
| B — market integrity | PASS | none in the tested scope |
| C — startup baseline/optimization | PASS | native pywebview cold startup `NOT_MEASURED`; Edge fallback used |
| D1 — TinyJS lifecycle/security | PASS | none in the tested scope |
| D2 — TinyJS startup/RAM/CPU | PASS, bounded | warm n=3 not measured; short CPU sample; no p95 |
| D3 — TinyJS chart/FTS | PASS | none in the tested scope |
| D4 — TinyJS packaging/diagnostics | **NOT_MEASURED** | installer, signing, updater/rollback, uninstall, Python bundling, WebView2 bootstrap, license audit |
| E1 — Tauri lifecycle/security | PARTIAL | 8 orphans + open port after shell crash; 3 WebView2 survivors in 1/3 graceful closes |
| E2 — Tauri startup/RAM/CPU | PASS, bounded | warm not measured; single-core contention |
| E3 — Tauri chart/FTS | PASS | none in the tested scope |
| E4 — Tauri official Windows packaging | **NOT_MEASURED** | MSVC/NSIS/WiX, signing, updater, uninstall, bundled Python |
| F — real-data acceptance | PARTIAL | market/FTS/switching/DB ownership pass; network interruption and mid-run backend death not run/measured; redundancy not measured |
| Full frontend suite | COMPLETED — not green | 2,074 pass / 11 fail / 5 skip (204 files); all 11 failures reproduce identically on clean `origin/main` `b5f5f6c` |

## 2. Scope, controls and non-claims

- Work stayed on the mission branch. `origin/main` remains `b5f5f6c`; no production application was migrated; no merge, tag or release was made.
- The production loopback guard was not weakened. Local Host and local Origin pass; foreign Host, foreign Origin and **`Origin: null` are rejected with 403** on `/api/*`. The guard test passes 11/11.
- Candidate runs used the same real SPA, the same FastAPI backend, the same `/api/chart/{symbol}` route and the same isolated SQLite snapshot. No mock market data was substituted.
- Background network fetch loops and the Codal worker were disabled for every candidate run (`BORS_NO_FETCH_LOOPS=1`, `BORS_CODAL_AUTO=0`). Runs were sequential; no two candidate runs overlapped, so no dual-fetcher condition was created. The board/status/FTS data is a real cached snapshot; the chart endpoint may perform its normal on-demand real read. No mock market data was substituted, and no board/FTS freshness is claimed as live.
- Every final measurement run was pinned to an isolated `BORS_DB`; the operational database was never intentionally used, but two pre-fix prototype dev runs did open it unintentionally. See the incident in §11.
- `p95` is not reported for n=3 (n<20). Cold/warm definitions and the WebView2-cache caveat are in §3. Timings are descriptive; no improvement percentage is claimed.
- "PASS" below means the gate was met inside the tested scope. It does not mean production acceptance.

## 3. Environment and measurement protocol

| Item | Value |
|---|---|
| Host | Windows 10 build 19045, 2 logical / 1 physical CPU, 3.88 GB RAM |
| WebView2 runtime | 155.0.4283.62 (present on host, not bootstrapped by either candidate) |
| Python | 3.12.10, repository `.venv` |
| TinyJS | 0.65.0, MIT; portable dist: `BorsTerminalM2TinyJS.exe` + `launcher.exe` |
| Tauri | 2.12.5, Apache-2.0 OR MIT; Rust 1.99.1, `x86_64-pc-windows-gnu` target |
| Shell under comparison | full app in each candidate shell; same backend/SPA/database snapshot |
| Cold run | fresh isolated work dir and shell profile per run |
| Candidate sample | cold n=3 normal runs per shell; D3 and startup-failure cold n=1 each; crash and restart warm n=1 each |
| Chart/FTS stage | timeframe W, raw adjustment, switch to `آباد`, real `/api/chart/آباد`, fundamental FTS card |
| Timestamps | launcher start → observed stage; median (min–max) |
| Memory/CPU | process-tree peak and one post-fundamental sample; short idle sample, not steady state |

Each cold run exercised the board, chart and FTS in one application session in that order. The stage medians are sequential user-path milestones, not isolated subsystem benchmarks; no simultaneous mixed load or drawing/settings save-restore was measured.

**Cold caveat:** the harness profile is fresh per run, but WebView2 keeps user data outside it (TinyJS: `%APPDATA%\com.borsterminal.m2tinyjs\WebView2`; Tauri: `%LOCALAPPDATA%\com.borsterminal.m2shell\EBWebView`). Those caches and OS file caches were not purged. These are cold application-state runs, not fully cold OS/WebView2 runs.

**Visible vs document-ready caveat:** Tauri creates its hidden WebView2 at startup and injects the probe before showing the window. Its "app document ready" can therefore precede "window visible"; TinyJS opens the window after HTTP verification. Compare stages with the same definition, not stage names across architectures.

## 4. Phase A — repository and baseline control

**Status: PASS.**

- Branch created from `origin/main` `b5f5f6c`; baseline worktree built and removed after verification.
- Final branch state before this report: 12 commits ahead of `b5f5f6c`, working tree clean, no `main` change, no merge/rebase/release/tag.
- Commits (oldest → newest): `59f2487` (ignore toolchains/build output), `c37a092` (market board gen), `402f7db` (board day/delta), `bd04bb7` (Phase B evidence), `8490a11` (chart route), `1fb74ba` (startup imports/screener deferral), `e702f23` (Phase C harness), `c1182dd` (chart company-name sync), `33ad682` (harness hardening + DB isolation), `4097e91` (TinyJS shell + evidence), `5c4dc9a` (Tauri shell + evidence), `a85b076` (stop tracking generated TinyJS build output).
- No benchmark database, operational user database or raw market payload was committed.

## 5. Phase B — market snapshot/cache/revision/freshness integrity

**Status: PASS.**

Three defects were reproduced on the baseline before being fixed; evidence is under `artifacts/desktop-migration/phase-b/`.

1. **Static board changes were invisible to delta/row clients.**
   - Baseline evidence (`before-main-static-delta.txt`): two builds with the same `rev` produced different rows (`retail_buy_pct` 33.3 → 98.9); the full-body ETag changed, but `delta since old rev` returned `unchanged` with 0 rows.
   - Fix: a board generation (`gen`) bound to both full and delta responses; a stale generation forces `full/board-changed`; row ETag carries revision + generation. The full-body content ETag still returns a 0-byte `304` when unchanged.
   - Commits `c37a092`, `402f7db`. After-fix HTTP evidence: `after-fix-http.txt` (`stale gen → full`, matching gen → `unchanged`, matching row ETag → `304`).

2. **Concurrent full-board publishes could leave cache and mirror on different snapshots.**
   - Baseline evidence (`before-main-concurrent-publish.txt`): cache `ctv=33.3 rev=0`, mirror `ctv=98.9 rev=0`, `cache/mirror paired: False`.
   - Fix: the publish path is serialized and pairs the cache/mirror revision; a stale publish cannot move a newer snapshot backwards. The guard now passes 33 checks, including overlapping publishers and stale-snapshot rejection (`after-fix-guard.txt`).

3. **The `/api/chart/{symbol}` route was hijacked by `_candle_closings`, returning 422.**
   - The UI painted a canvas and FTS text without a candle count, so only an HTTP check exposed it.
   - Fix `8490a11`; guard `dev/chart_route_v1.py` passes 6/6 (exactly one chart route, correct GET endpoint, symbol parameter, no exposed internal route).

**Freshness labels:** the board day and the chart's last-candle day are now separately labelled. On this snapshot, the board is labelled `۱۴۰۵/۰۷/۲۲` while the chart's local candle source reaches `1405/08/02`; both are shown with their own source day rather than conflated (`chart-board-freshness.txt`). This is a truthful divergence, not proof of live freshness.

## 6. Phase C — startup-stage baseline and evidence-based optimization

**Status: PASS (native pywebview cold startup remains `NOT_MEASURED`).**

The current shell was measured through its supported Edge app-window fallback because native pywebview/WebView2 on this host repeatedly stalled (27–40 s for a static page; 76–162 s for the boot page; one `0x800700AA` initialization failure). That limitation is recorded, not hidden.

| Stage (median ms, n=3) | Cold baseline | Cold after fix | Warm baseline | Warm after fix |
|---|---:|---:|---:|---:|
| Backend HTTP ready | 31,506 | 23,782 | 24,801 | 19,690 |
| First market board usable | 65,901 | 45,928 | 63,881 | 45,975 |
| First technical chart usable | 88,193 | 67,045 | 83,665 | 64,728 |
| First fundamental panel usable | 90,418 | 69,143 | 86,860 | 67,314 |

Fixes were limited to verified startup contention: `_IMPORT_LOCK` serialized concurrent heavy imports (the baseline produced a `take_gil` fatal error), and the screener warm was deferred behind the first published board and run at lowest priority (`1fb74ba`). The scan itself was not changed. The shipped variant is within ~1 s of skipping the warm entirely (`phase-c/diagnostics.md`).

Full-suite baseline during Phase C: 2,070 passed / 8 failed / 5 skipped in ~99 minutes on this single-core host; failures were pre-existing or environment flakes (details §10). Native-shell cold startup is not claimed as measured.

## 7. Phase D — TinyJS integrated feasibility

### D1. Lifecycle and security — **PASS**

- TinyJS spawns the Python sidecar hidden, reads the `PHASE_D_READY` line, verifies `GET /api/update/version`, and only then opens the app window. A startup failure shows a local error window with the sidecar tail; an unexpected sidecar exit after readiness also has an error path.
- On normal close it closes the sidecar stdin, waits for uvicorn's shutdown (bounded 15 s), then quits; it does not kill an in-flight database write early.
- Live security matrix, 5 cases × 3 cold runs = 15/15 pass: local Host 200; foreign Host 403; foreign Origin 403; **`Origin: null` 403**; local Origin 200.
- No production security code was changed to make the shell work. The sidecar binds `127.0.0.1` only.

### D2. Startup, RAM and CPU — **PASS, bounded**

| Metric (cold n=3) | TinyJS median (min–max) |
|---|---:|
| Sidecar ready | 17,036 ms (16,928–17,967) |
| Window visible | 21,967 ms (21,600–23,292) |
| HTTP verified | 19,409 ms (18,809–19,627) |
| App document ready | 30,116 ms (24,901–30,560) |
| Board usable | 39,107 ms (36,812–39,703) |
| Chart usable | 77,303 ms (74,845–83,913) |
| Fundamental usable | 83,826 ms (80,427–89,235) |
| Peak process-tree RSS | 887.9 MB (844.9–904.6) |
| Post-fundamental RSS | 761.8 MB (750.6–790.8) |
| Idle CPU sample (one core) | 65.0% (64.3–134.8) |
| Process count at sample | 12 |
| Clean exits / survivors | 3/3 exit 0; 0 survivors; port closed |

The "idle" CPU sample is short and taken while the SPA may still poll; it is not steady-state. One TinyJS run sampled 134.8% of one core, so the median is not an efficiency claim. Warm candidate runs were not measured.

### D3. Chart, timeframe, adjustment, symbol and FTS fidelity — **PASS**

On the real isolated snapshot, both TinyJS and Tauri showed:

- timeframe switch to **W** active, chart canvas 864×595;
- adjustment switch from `عملکردی (افزایش سرمایه و سود نقدی)` to `خام (بدون تعدیل)`, canvas 857×595;
- symbol switch to **آباد** with toolbar `آباد(توریستی و رفاهی آبادگران ایران)۱,۳۹۲+۲.۹۶%`;
- `GET /api/chart/آباد` → **200**, 4,159 candles, last candle `1405/08/02`, 189,953 bytes transferred / 1,091,684 decoded;
- fundamental FTS card: score **3/5**, verdict `مناسب برای زیر نظر گرفتن (واچ‌لیست)`, financial-statement age `۱۲۵ روز`;
- market-status page populated with real cached indices, breadth, queue and money-flow panels (not placeholders);
- screenshots for both shells in `artifacts/desktop-migration/phase-d/*-d3-iso/`.

The company name previously stayed stale after an external symbol change. Fix `c1182dd` keeps `currentName` synchronized with `initialName`; regression test `technical-nn-chart.spec.tsx` passes 12/12. This changed only the displayed company name; no formula, adjustment semantics, FTS rule or calculation source was changed.

**D3 scope limit:** both shells load the same KLineChart implementation and the same chart API. This establishes shell integration parity and real-data/API correctness; it is not an independent numerical or pixel-reference validation of every indicator drawing. The existing chart route guard (6/6) and the technical chart suite cover route/behavior, but a dedicated reference-image comparison was `NOT_MEASURED`.

### D4. Distribution, diagnostics, installer, WebView2, update, signing, crash, uninstall, licenses — **NOT_MEASURED (parts code-reviewed)**

| Item | Observed | Open gate |
|---|---|---|
| TinyJS shell | Portable exe 5,686,049 B + launcher 2,164,824 B = 7,850,873 B | No installer; no bundled Python; not an install footprint |
| Diagnostics | hidden sidecar console; `sidecar.log`; shell JSONL trace; local error HTML/window | no crash reporter, rotation, retention policy or user-visible export |
| WebView2 | host runtime 155.0.4283.62 used; app data under `%APPDATA%\com.borsterminal.m2tinyjs\WebView2` | no bootstrapper/fixed runtime test; cache not isolated in cold runs |
| Update/signing | TinyJS publish/update path exists in the toolchain; not configured or exercised | no signed update, no rollback test, no key management |
| Install/uninstall/user data | portable run only | install, upgrade, downgrade, uninstall, user-data retention/removal all untested |
| Licenses | TinyJS MIT; Python PSF; WebView2 proprietary | transitive JS/Rust/data licenses not audited |

TinyJS also relies on the app's Python backend for all data access; the shell itself does not open SQLite. That preserves one DB owner, but makes Python bundling a mandatory packaging task.

## 8. Phase E — direct Tauri v2 competitor

**Status: PARTIAL.** Tauri is fully comparable on rendering and performance shape, but not on official Windows packaging or crash cleanup.

### Build and packaging

- Built `x86_64-pc-windows-gnu` release with Rust 1.99.1. The build succeeded but warned `.rsrc merge failure: multiple non-default manifests`. The exe is 21,599,122 B.
- `bundle.active` is `false`; no MSVC build, NSIS/WiX installer, code signing, updater, rollback or uninstall was produced. A GNU build is not an official Windows success.
- The shell still spawns the repository `.venv` Python; Python, the database and WebView2 are not bundled.
- Tauri prototype CSP is `null` (`tauri.conf.json`). This is acceptable only for a local prototype and is a production security gate.

### E1. Lifecycle/security — **PARTIAL**

Startup failure works: error window titled `BorsTerminal — startup failed`, sidecar exit 42, shell exit 0, no survivors, no port. `CREATE_NO_WINDOW` prevents a stray Python console. The security matrix passes 15/15.

Failure under shell crash is not acceptable yet: terminating the shell root after the board left **8 survivors** (sidecar/WebView2 children) and an **open loopback port**; the harness had to kill them, after which the port closed. The orphaned sidecar still enforced the Host/Origin matrix (the crash run's security checks passed), but reachability and process ownership were not contained. Graceful close was clean in 2/3 cold runs; one run left 3 WebView2 processes that the harness cleaned. The shell's sidecar monitor is code-reviewed but killing the backend mid-run was not exercised.

A diagnostic quirk is recorded honestly: in the startup-failure run the shutdown trace says `timeout` because no child was stored; the error window and sidecar exit 42 are the actual behavior.

### E2. Startup/RAM/CPU — **PASS, bounded**

| Metric (cold n=3) | Tauri median (min–max) |
|---|---:|
| Sidecar ready | 22,491 ms (21,349–22,625) |
| Window visible | 25,503 ms (22,320–26,683) |
| App document ready | 23,709 ms (22,058–23,778) |
| Board usable | 44,023 ms (42,214–45,124) |
| Chart usable | 83,559 ms (77,751–88,835) |
| Fundamental usable | 91,494 ms (83,227–95,801) |
| Peak process-tree RSS | 885.5 MB (877.8–898.9) |
| Post-fundamental RSS | 784.0 MB (765.9–784.8) |
| Idle CPU sample (one core) | 143.2% (92.0–153.4) |
| Process count at sample | 10–11 |
| Clean exits | 3/3 exit 0; 2/3 no survivors |

Tauri creates a hidden WebView2 at startup before the Python preflight; on this single core that competes for CPU. The comparison is descriptive: TinyJS's medians were lower here, but n=3 on a noisy single-core host cannot establish a general framework order.

### E3. Chart/FTS fidelity — **PASS**

Same 4,159 candles, timeframe W, raw adjustment, `آباد` switch, FTS 3/5, 125-day card and populated market-status panels. Screenshots in `artifacts/desktop-migration/phase-d/tauri-d3-iso/`. The D3 text extractor for Tauri captured a transient FTS node once (`صورت مالی معتبر`) while the screenshot at the same step shows the same 125-day card as TinyJS. The DOM text is treated as a re-render race; the screenshot is authoritative.

### E4. Packaging/distribution — **NOT_MEASURED**

No MSVC/NSIS/WiX installer, signing, updater/rollback, uninstall, WebView2 bootstrapper or license audit. Do not read the 21.6 MB GNU exe as an installation size.

## 9. Phase F — bounded real-data acceptance slice

**Status: PARTIAL.** The core slice passes; the hostile-network and mid-run-failure parts were not run.

| Check | TinyJS | Tauri | Evidence / note |
|---|---|---|---|
| Market status (real snapshot) | PASS | PASS | indices/breadth/queue panels rendered; cached data |
| Fundamental/FTS card | PASS | PASS | score 3/5, watchlist verdict, 125-day age |
| Chart live route + symbol switch | PASS | PASS | `/api/chart/آباد` 200, 4,159 candles |
| Timeframe/adjustment switching | PASS | PASS | W and raw mode active |
| Freshness/error labels | PASS | PASS | board day, chart last candle, FTS age, market "report not received" |
| Startup failure state | PASS | PASS | error window + sidecar 42 + clean exit |
| Graceful shutdown | PASS | PARTIAL | Tauri left 3 WebView2 processes in 1/3 runs |
| Crash/orphan containment | PASS | **FAIL** | Tauri: 8 survivors + open port after shell kill |
| Crash/restart | PASS | PASS | both restart cleanly on the same port |
| Backend DB ownership | PASS | PASS | isolated `BORS_DB`; shell holds no SQLite handle; guard refuses mismatch |
| Redundant fetching | NOT_MEASURED | NOT_MEASURED | repeated `tedpix`/`delta` calls observed across route transitions; no same-view duplication measurement |
| Network interruption | NOT_RUN | NOT_RUN | intentionally skipped; would need host-level isolation while guaranteeing one fetcher |
| Mid-run backend death | NOT_MEASURED | NOT_MEASURED | error paths exist in code, but not exercised |

Freshness observations are deliberately modest: the board is closed and labelled with its own day; the chart is newer than the board by source date; FTS is 125 days old; market status says the live market-data report has not arrived. With fetch loops off, none of this is evidence of live freshness. It is evidence that stale/closed states are visible rather than silently replaced with fabricated data.

The request sequence included `/api/market/closes` once, `/api/market/delta` and `/api/index/tedpix` on multiple route lifecycle/poll points. No duplicate same-view fetch storm was established; redundancy remains `NOT_MEASURED`, not "fixed" or "proven".

## 10. Tests, gates and pre-existing failures

| Check | Result |
|---|---|
| Phase B market snapshot/gen guard | PASS — 33 checks (`phase-b/after-fix-guard.txt`) |
| Chart route guard | PASS — 6/6 (`phase-d/tests/chart-route.txt`) |
| Loopback Host/Origin guard | PASS — 11/11 (`phase-d/tests/loopback-guard.txt`) |
| Gate tests (`market-feed-delta`, `fundamental-page`, `fts-drilldown`, `fts-screen`, `fts-card-contract`) | PASS — 98/98, 5 files (`phase-d/tests/gates-b-f.txt`) |
| Company-name regression | PASS — 12/12 (`phase-d/tests/technical-nn-chart.txt`) |
| `technical-symbol-race.spec.tsx` | 1 failed / 4 passed on this branch **and identically on clean `origin/main` `b5f5f6c`**; pre-existing, not introduced (`phase-d/tests/current-technical-symbol-race.txt`, `baseline-origin-main-technical-symbol-race.txt`) |
| Full frontend suite | 204 files — 197 passed / 5 failed / 2 skipped; **2,090 tests — 2,074 passed / 11 failed / 5 skipped** in 1,913 s (31.9 min) on the final source state. The 5 failing files were re-run in isolation on this branch and on clean `origin/main` `b5f5f6c`: both produced the identical 11 failures / 9 passes. Raw log not committed; summary in `phase-d/tests/full-frontend-suite-summary.txt`. |
| Live security matrix | PASS — 15/15 per candidate (5 cases × 3 cold runs) |

The focused gate set intentionally excludes the known pre-existing race failure; the report does not claim a green entire suite. The 11 full-suite failures are confined to five files — `fundamental-codal-poll` (3), `funnel-request-dedup` (1), `funnel-row-symbol-visible` (4), `technical-symbol-race` (1) and `watch-dossier` (2) — and the exact same 11 tests fail on clean `origin/main` `b5f5f6c`. No changed-area gate test fails. The earlier Phase C full-suite baseline was 2,070 / 8 / 5 in ~99 min; full-suite counts are order/environment-sensitive, so the difference is not used as a quality claim. The summary file is the source of truth for the final run and is committed alongside this report.

## 11. Operational-database incident (must not be hidden)

Before the `BORS_DB` isolation door existed, two candidate development runs opened the repository's operational `market.db`. The cause was `bors_config._resolve_market_db()` preferring `exe_dir` over `BORS_WORK_DIR`; setting only `BORS_WORK_DIR` was insufficient.

Observed controlled audit (`phase-d/db-integrity/operational-db-audit.json`):

- Operational `market.db`: 281,276,416 bytes, SHA-256 `7cfefddd…`; WAL `9e9e9f0f…`.
- Compared with the template, 46 of 48 table row counts were identical. Only two adjustment-cache tables differed: `adjust_cache_meta` 50 vs 48 and `adjust_events` 12,716 vs 12,719.
- The operational main DB and WAL hashes were **unchanged** between 02:02 and 02:37 after `BORS_DB` was introduced.
- The operational DB was not restored or rewritten. The two cache-table deltas are real local state from the incident and are left for owner review.
- The fixed sidecar declares `db`/`user_db` at START and refuses to run if `BC.DB_PATH` does not equal `BORS_DB`. Isolated reruns wrote only to their work directories. No user data or operational DB was committed.

This is a self-caught process violation, not a successful isolation. It is reported as such.

## 12. Distribution, diagnostics and license inventory

| Area | TinyJS | Tauri | Status |
|---|---|---|---|
| Shell bytes | 7,850,873 | 21,599,122 (GNU) | shell only, not an installer |
| Python bundled | No (`.venv`) | No (`.venv`) | packaging gate open |
| Installer | not built | bundle disabled; no MSVC/NSIS/WiX | NOT_MEASURED |
| Signing | not tested | not tested | NOT_MEASURED |
| Updater/rollback | toolchain path exists, not configured | updater not configured | NOT_MEASURED |
| Uninstall/user data | not tested | not tested | NOT_MEASURED |
| WebView2 bootstrapper | not tested; runtime present | not tested; runtime present | NOT_MEASURED |
| Crash diagnostics | log + HTML/error window | log + error window | no crash reporter/retention/export |
| CSP | host webview policy not separately configured | `csp: null` in prototype | production security gate |
| Licenses | MIT / PSF / proprietary WebView2 | Apache-2.0 OR MIT / proprietary WebView2 | transitive audit NOT_MEASURED |

Reference only, the existing portable current shell occupies 575,404,348 B in this workspace; the main components are 15,526,539 B exe + 117,937,633 B `_internal` + 441,832,235 B data (575,296,407 B; the remainder is local logs/README). That includes data and a bundled Python environment; candidate shell bytes cannot be compared to it.

## 13. Risks and gates that remain open

1. **Packaging is unproven for both candidates.** No signed installer, updater/rollback, uninstall, WebView2 bootstrap or bundled Python. A 7.85 MB TinyJS shell is not a product footprint.
2. **Tauri crash containment fails on this host.** The shell must own the sidecar/WebView2 children with a Windows Job Object or equivalent; otherwise a crash can leave a backend and an open loopback port.
3. **Tauri's official Windows path is unbuilt.** MSVC/NSIS/WiX, signing, SmartScreen and updater remain `NOT_MEASURED`; the GNU exe is evidence of code portability only.
4. **Tauri prototype CSP is null.** It must be designed and tested before any production use.
5. **TinyJS graceful shutdown and error paths are measured only at startup/normal close.** Backend death mid-run, disk-full during write, and forced OS shutdown are `NOT_MEASURED`.
6. **Live freshness and network interruption are unproven.** The market is closed, fetch loops were off, and no interruption test was run. Do not interpret cached panels as live data.
7. **The cold protocol does not purge WebView2 caches.** Startup comparisons are application-state cold, not OS-cold.
8. **Operational DB state needs owner review.** Two cache tables changed before isolation; the main DB/WAL hashes were stable afterward.
9. **Full-suite history is not green.** The final run is 2,074 pass / 11 fail / 5 skip; all 11 failures reproduce identically on clean `origin/main` `b5f5f6c`, so they are pre-existing and not introduced by this branch. No changed-area gate test fails, but the full suite cannot be reported as green.
10. **Drawing/settings persistence and cross-version data migration were not measured.** The D3 run exercised chart interaction and switching, not save/restore across a shell restart or export/import of old user data.

## 14. Next bounded mission (not started)

Advance **TinyJS only** to a packaging/acceptance mission, with no production migration until it passes:

1. Bundle the Python sidecar and dependencies into one signed TinyJS distribution; measure installed size and cold/warm startup on a clean Windows 10 and a clean Windows 11 machine.
2. Build a signed installer, an update package with rollback, and an uninstaller; test user-data retention and removal.
3. Test WebView2 bootstrap (missing/old runtime), offline install, low-disk, non-admin install and multi-user behavior.
4. Add crash containment and a local diagnostic report (no silent upload), then run crash/restart, backend-kill, disk-full and OS-shutdown tests.
5. Re-run the real-data slice with controlled network interruption and an explicit one-fetcher guard; measure request redundancy per view.
6. Repeat cold/warm measurements at n≥10 and report distributions; keep the current pywebview application as the operational fallback and do not merge this branch into `main`.

## Appendix A — reproduce the candidate measurements

The harness creates a fresh work dir/profile under `%TEMP%\bors_phased`, sets `BORS_DB` to the run's isolated `market.db`, disables background loops and the Codal worker, and writes `progress.log`, incremental `partial-result.json`, and final summaries. Do not point `--template` or `--out-dir` at the operational database.

```bash
# TinyJS cold n=3
.venv/Scripts/python.exe tools/desktop-migration/phase_d_tinyjs.py \
  --label tinyjs-cold-iso --mode cold --runs 3 \
  --template "$TEMP/bors_phasec/template" \
  --exe prototypes/tinyjs-m2/dist/BorsTerminalM2TinyJS.exe \
  --out-dir artifacts/desktop-migration/phase-d/tinyjs-cold-iso

# Tauri cold n=3 (GNU build; not an official Windows package)
.venv/Scripts/python.exe tools/desktop-migration/phase_d_tinyjs.py \
  --label tauri-cold-iso --mode cold --runs 3 \
  --template "$TEMP/bors_phasec/template" \
  --exe prototypes/tauri-m2/src-tauri/target/x86_64-pc-windows-gnu/release/bors-m2-shell.exe \
  --out-dir artifacts/desktop-migration/phase-d/tauri-cold-iso

# D3 visual/fidelity run (n=1 per shell)
# append: --d3 --visual --runs 1 --mode cold

# Startup-failure fixture (BORS_FAIL_TEST=1)
# append: --scenario fail --runs 1 --mode cold

# Shell-crash/orphan fixture
# append: --crash --runs 1 --mode warm --warmup 1
```

The crash and failure fixtures are diagnostic, not statistical samples. Repeating the cold runs still does not purge WebView2 or OS caches; see §3.

## 15. Verdict

**`TINYJS_ADVANCE`**

TinyJS is the candidate to advance because it passed the measured lifecycle, security, real-data, chart/FTS and failure-recovery gates, and it contained a shell crash without orphaning the backend on this host. Tauri was not eliminated on rendering or performance, but its crash-orphan behavior and unbuilt official Windows packaging are unresolved; it remains a direct comparator for the packaging stage.

This verdict authorizes **only** the bounded packaging/acceptance work in §14. It does not authorize production migration, a merge into `main`, a release, a tag, or a claim that TinyJS is the final production winner. The operational pywebview application remains the control/fallback.
