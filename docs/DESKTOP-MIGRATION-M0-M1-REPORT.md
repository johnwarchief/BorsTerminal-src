# BorsTerminal — Desktop Modernization & Migration (M0/M1)

Branch: `mission/desktop-migration-m0-m1` (based on `9d50f0a`, `main`)
Measurement window: 2026-10-23 17:00Z – 2026-10-24 11:30Z
Decision reference: `BorsTerminal-Desktop-Migration-Decisions.md` (`9d50f0a`)

## 1. Executive summary

The mission built and measured **real** market-board and technical pages against the
real FastAPI backend and `market.db`, under the same React bundle, data and API, in
three window shells:

| Shell | Launch → board usable (warm) | Shell RSS | JS heap | Shell artifact |
|---|---:|---:|---:|---:|
| Current shipped app (pywebview + bundled backend) | **36–57 s** (3 runs; median 46.7 s) | **955 MB** total (1 corrected run) | 26–42 MB | 15.2 MB EXE + 116 MB `_internal` + data |
| Prototype under pywebview | **13.8–14.7 s** (median 14.4 s) | 541–552 MB | 11.7–11.8 MB | dev harness (not packaged) |
| Prototype under Tauri v2 | **3.8–4.6 s** (median 4.5 s) | 450–461 MB | 11.5–12.1 MB | 21.5 MB EXE (GNU build, no backend) |
| Prototype under TinyJS 0.65 | **4.7–5.7 s** (median 5.3 s) | 408–423 MB | NOT_MEASURED (no CDP) | 6.9 MB (exe+launcher, no backend) |

The shell delta is real and large: the same UI starts roughly **3–4× faster** under
Tauri than under pywebview and uses ~80–100 MB less shell RAM. TinyJS is in the same
class as Tauri for startup and RAM, at one third of the artifact size.

That is **not sufficient to justify a migration now**:

1. The shipped app's 36–57 s is dominated by the Python backend and boot/preflight,
   not only by the window. Tauri and TinyJS still need that Python backend; they do
   not remove the dominant startup cost, the 116 MB Python runtime, or the 269 MB
   database.
2. Only 2 of the app's 10 user-facing destinations were prototyped. Fundamental/FTS,
   market-status, strategy tree, portfolio, sarkhati, watchlist, notifications and
   settings are not migrated.
3. The data path has unresolved, pre-existing correctness problems (board vs chart
   freshness, and a cache/revision inconsistency observed during this mission). A
   shell migration would preserve them while making them harder to see.
4. Tauri's current repo state has no Python sidecar, updater or installer path; the
   only Windows build proven here is the unofficial GNU toolchain, because this
   machine has no MSVC build tools. TinyJS has no CDP, no proven updater/packaging
   story, and a very young ecosystem.

**Recommendation:** keep pywebview 1.0.97 in production for now. Fix the data/cache
path and profile the backend startup first. If shell migration is still wanted
afterward, take **Tauri v2** as the only credible production path, with a native
sidecar/loopback proxy and MSVC signed build, and prototype at least market-status +
FTS/fundamental under the same harness before committing. TinyJS is a credible
lightweight fallback only if the product accepts remaining a URL wrapper with an
external backend and if observability/update/security gaps are closed.

## 2. Scope, constraints and branch

The mission followed the owner's decisions document and the executive prompt:

- Source was investigated at `main` (`9d50f0a`), not only at the older release.
  `main` reports `APP_VERSION 1.0.95`; the public portable artifact used for the
  shipped baseline is **1.0.97**. This source/release divergence is recorded, not
  “fixed” in this branch.
- The production loopback guard was **not weakened** and `Origin: null` is still
  rejected. The prototype serves its UI from the same loopback origin and proxies
  `/api` without adding CORS.
- One TSETMC fetcher at a time. The comparison backend ran with
  `BORS_NO_FETCH_LOOPS=1` and `BORS_CODAL_AUTO=0`; the technical endpoint's
  on-demand CDN read is documented separately. No second live instance was started.
- No mock market data: every screenshot and every number comes from the real
  `market.db`/FastAPI paths. Missing measurements are marked `NOT_MEASURED`.
- `main` was not modified or merged. Work is confined to this branch.

## 3. Architecture and runtime map (M0)

```
pywebview (edgechromium/WebView2)
  └─ native window + boot page (bors_entry.py)
       └─ React SPA (hash router, default /master)
            └─ FastAPI app.py (same process for installed/portable)
                 ├─ loopback_guard (Host/Origin = 127.0.0.1/localhost/::1)
                 ├─ /api/market  ← market_watch (local snapshot)
                 ├─ /api/chart/* ← TSETMC CDN live read, local fallback, live-bar injection
                 └─ SQLite: market.db (42 tables), user.db, JSON status files
```

Confirmed facts that matter for migration:

- The actual deliverable is **PyInstaller onedir + Inno Setup**, with an in-app
  updater (`latest.json` + minisign). The EXE is 15.2 MB and `_internal` is 116 MB;
  the data directory carries a 269 MB `market.db` and a 76 MB `.lzma` bootstrap.
- Ports: dev 8000, installed 8001, portable 8101; the migration harness uses 8102
  for the backend and 8105 for the same-origin prototype server.
- No WebSocket/SSE. Market polling is 5 s (delta), 90 s and 300 s depending on the
  page; the prototype mirrors the 5 s delta contract.
- `frontend/src-tauri` in `main` is a scaffold with **no Python sidecar**; the
  release workflow says the Tauri job cannot launch the backend. A bundled Tauri
  frontend origin on Windows is `http://tauri.localhost`, which the production guard
  rejects with 403.
- TinyJS 0.65 is a txiki.js + WebView2 URL wrapper. It can load the loopback URL, so
  the guard passes, but it has no first-class Python integration.
- The technical endpoint (`/api/chart`) performs a live TSETMC CDN request even when
  `BORS_NO_FETCH_LOOPS=1` (only its history-repair helper is gated). The market
  board reads the local `market_watch` snapshot. This is why the chart can be newer
  than the board (section 8).
- There is no CORS configuration. The prototype proxy must therefore enforce the
  same loopback Host/Origin contract itself because it rewrites `Host` upstream
  (section 9).

## 4. Baseline methodology

### 4.1 Environment and data

| Item | Value |
|---|---|
| OS / CPU / RAM | Windows 10 Pro 19045 x64, Intel CPU, 8 GB |
| Display | 1280×1024 physical, DPI 96; CDP viewports used for 1366×768 and 1920×1080 |
| WebView2 | 155.0.4283.62 |
| Python / Node | CPython 3.12.10 / Node 22.22.0 |
| Backend | `127.0.0.1:8102`, `BORS_NO_FETCH_LOOPS=1`, `BORS_CODAL_AUTO=0` |
| Prototype server | `127.0.0.1:8105`, same-origin static + `/api` proxy |
| Data | `market.db` reconstructed from `data-latest`: 6,022 `market_watch` rows, 6,018 API rows, 129,577 daily rows, 445,681 price-history rows, 8,723 financial statements, `MAX(d_even)=20261014` |

### 4.2 Metrics and tools

| Metric | Tool / definition |
|---|---|
| Shell init | `bench_shell.mjs`: process start → CDP endpoint ready (`cdpMs`) |
| Shell ready | process start → login → prototype/react chrome visible (`shellReadyMs`) |
| Market ready | click market → ≥20 real rows rendered (`marketReadyMs`) |
| Technical ready | click technical → KLineCharts canvas present and `/api/chart` completed |
| RAM / CPU | process-tree `WorkingSetSize` / CPU seconds (PowerShell); TinyJS via psutil |
| JS heap | CDP `Performance.getMetrics` (`jsHeapAfterMB`) |
| Scroll | rAF frame intervals while scrolling the virtualized board for 2 s |
| API | `bench_proto_api.py`: warm-up + 10 samples, p50/p95, raw/gzip bytes |
| Visual | CDP screenshots at 1366×768 and 1920×1080; TinyJS via Win32 PrintWindow |
| Guard | `check_guard.py`: Host/Origin matrix against backend and proxy |

### 4.3 Fairness and confounders

- The three prototype shells use **the same URL, React bundle, backend, DB and API**.
  The only variable is the shell.
- The shipped app is reported separately because it bundles the backend, boot page
  and production UI. Its numbers cannot be used as a pure “shell” measurement.
- Warm profile means the WebView2 profile is reused; cold means it is deleted before
  the run. Cold current-shell runs are `NOT_MEASURED` (CDP timeout while the boot
  page navigated); warm shipped runs are reported.
- Tauri was built with the **GNU/MinGW** toolchain (no MSVC/admin on this machine).
  The binary launched and exposed CDP, but this is not the officially supported
  Windows target. MSVC build/installer/updater are `NOT_MEASURED`.
- TinyJS does not forward `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS`; CDP is
  unavailable. Window/API timings, PrintWindow screenshots and process-tree RAM were
  measured externally; in-page heap, console errors and rAF are `NOT_MEASURED`.
- During the session the backend served different row-level `/api/market` snapshots
  while `rev` stayed `0` and `meta` was unchanged (section 8.4). The final three
  suites were run back-to-back after cache warm-up, but this is a backend caveat, not
  a shell difference.

## 5. Current shell and backend baseline

### 5.1 Shipped portable 1.0.97 (warm profile)

| Run | CDP ready | Page ready | Shell ready | Market ready | Technical ready | RSS (process tree) | Heap |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 46,852 ms | 50,454 ms | 52,633 ms | 4,648 ms | 18,222 ms | 476 MB* | 42.2 MB |
| 2 | 31,250 ms | 33,027 ms | 34,069 ms | 2,147 ms | 8,861 ms | 639 MB* | 25.6 MB |
| 3 | 40,985 ms | 42,887 ms | 44,469 ms | 2,254 ms | 10,704 ms | 660 MB* | 25.7 MB |
| corrected | 34,326 ms | 36,938 ms | 38,095 ms | 1,943 ms | 10,638 ms | **955 MB** | 28.7 MB |

`*` The warm runs' process snapshot missed the root `BorsTerminal_Ultimate.exe`
because of a harness bug fixed mid-mission. The corrected run includes root:
backend 313 MB + WebView2 642 MB = **955 MB**. Use 955 MB as the total; the lower
values are undercounts.

Scroll: p50 17.2–17.9 ms, p95 35.1–65.6 ms; 20–28 frames >33 ms in 2 s.
Cold start with a stock profile was **NOT_MEASURED**; an earlier fresh-profile run
timed out waiting for CDP after the boot page navigated. The documented baseline
(first launch) is ~3 minutes for data extraction, 8 s backend-to-port with warm
screener cache, and ~16 s server warm completion.

### 5.2 Source/dev pywebview (full app)

Early dev runs started at 28–45 s shell-ready and 4.5–7.9 s market-ready, but they
were taken during an uncontrolled cold-machine window; they are not used for the
final comparison. The shipped portable numbers above are the baseline of record.

### 5.3 Focused API probe (backend 8102, 10 samples)

| Path | p50 | p95 | Transfer (gzip) | Decoded |
|---|---:|---:|---:|---:|
| `/api/update/version` | 4.5 ms | 7.9 ms | <1 KB | <1 KB |
| `/api/market` | 136.0 ms | 171.7 ms | 1,192 KB | 6,655 KB |
| `/api/market/delta?since=rev` | 3.0 ms | 10.1 ms | <1 KB | <1 KB |
| `/api/market/row?symbol=فولاد` | 8.5 ms | 12.8 ms | 1 KB | 1 KB |
| `/api/chart/فولاد` | 593.8 ms | 732.0 ms | 197 KB | 1,095 KB |
| `/api/history/فولاد` (fallback) | 356.4 ms | 525.5 ms | 17 KB | 17 KB |

These are consistent with the 2026-10-22 baseline (`/api/market` 132.6/240.5 ms,
`/api/chart` 517.8/916.8 ms). The chart path is the dominant per-page cost and is
shared by every shell.

## 6. Real M1 prototype

### 6.1 What was built

- `frontend/prototype/` — a production Vite build of a real React prototype:
  - **Market board:** real `/api/market`, 6,018 rows, TanStack virtualizer (34 DOM
    rows at 1366×768), value/volume/queue/buyer-power/flags, filters, sort,
    5 s delta polling, connection/freshness/clock/theme/density chrome.
  - **Technical page:** real `/api/chart/فولاد` with `/api/history` fallback,
    KLineCharts 10.0.3, raw vs combined adjustment via server factors, weekly/
    monthly aggregation, MA/BOLL/RSI, three drawing tools, data-path panel, live
    board date vs last-candle date badge.
  - Login, loading/error/connection states, toasts and explicit “not migrated”
    placeholders for the other destinations.
- `tools/desktop-migration/serve_prototype.py` — same-origin static server + proxy;
  loopback guard enforced at the edge (post-fix).
- `tools/desktop-migration/launch_proto_pywebview.py` — thin pywebview shell.
- `prototypes/tauri-m1/` — Tauri v2 shell loading the same URL (no IPC/sidecar).
- `prototypes/tinyjs-m1/` — TinyJS wrapper source/config for the same URL.
- `tools/desktop-migration/bench_shell.mjs`, `bench_tinyjs.py`,
  `bench_proto_api.py`, `check_guard.py`, `ui_smoke.mjs` — repeatable measurement kit.

### 6.2 Final same-UI shell comparison (warm profile, 3 runs each)

| Metric | pywebview | Tauri v2 | TinyJS 0.65 |
|---|---:|---:|---:|
| CDP ready | 10,807–11,730 ms | **1,420–1,877 ms** | not exposed |
| Window visible | n/a (CDP) | n/a (CDP) | **2,187–2,979 ms** |
| Page navigation ready | 11,715–12,712 ms | 2,138–2,853 ms | 2,568–3,520 ms |
| Shell ready (after login) | 13,167–13,869 ms | **3,175–3,988 ms** | login→market 1,306–1,349 ms |
| Shell → board usable | **13.8–14.7 s** | **3.8–4.6 s** | **4.7–5.7 s** |
| Market render after click | 607–860 ms | 572–642 ms | not separable (API 151–243 ms) |
| Technical render after click | 3,293–4,949 ms | 2,592–3,289 ms | 1,115–2,161 ms* |
| Shell process-tree RSS | 541–552 MB | **450–461 MB** | **408–423 MB** |
| JS heap after technical | 11.7–11.8 MB | 11.5–12.1 MB | NOT_MEASURED |
| Scroll p50 / p95 | 17.3 (one 31.5 outlier) / 48.9–50.2 ms | 16.7–17.0 / 33.4–49.4 ms | NOT_MEASURED |
| Console errors | 0 | 0 | NOT_MEASURED |
| Shell artifact | dev Python harness | 21.5 MB | 6.9 MB |

`*` TinyJS's technical time is click → `/api/chart` response from the proxy log, not
click → first painted candle. It was also measured after earlier chart requests had
warmed the server cache; compare it only with that caveat.

Cold runs:

| Shell | Cold shell/window | Cold market | RSS |
|---|---:|---:|---:|
| pywebview (fresh profile) | 14,193 ms shell ready | 716 ms | 565 MB |
| Tauri (fresh profile, earlier suite) | 6,040 ms shell ready | 1,221 ms | 491 MB |
| TinyJS (fresh profile) | 3,302 ms window / 6,305 ms to market | included | 418 MB |
| shipped portable | **NOT_MEASURED** | — | — |

### 6.3 Visual and functional verification

- Screenshots at 1366×768 and 1920×1080 exist for pywebview and Tauri; TinyJS was
  captured at its 1,284×768 client area because the test display is 1280×1024 and
  the TinyJS launcher clamps window width to the work area. TinyJS at 1920 is
  `NOT_MEASURED`.
- Functional smoke (`ui_smoke.mjs`) on Tauri: market rows 34 ≥ 20; RSI adds an
  indicator pane (10 → 14 canvases); raw/combined switch active; weekly/monthly
  switch active; trend-line drawing marks the chart; **0 console/page errors**;
  result `ok: true` (`artifacts/desktop-migration/ui-smoke/result.json`).
- The technical page shows both dates explicitly when they differ:
  `کندل 2026-10-21 · تابلو 2026-10-14` with an amber badge. This is deliberate: the
  chart and board are not the same series.

## 7. Option comparison

| Dimension | Current pywebview + PyInstaller | Tauri v2 | TinyJS |
|---|---|---|---|
| Shell startup (same UI) | 13–15 s warm | **3–4 s** | **~4–6 s to board** |
| Shell RAM (same UI) | 541–552 MB | 450–461 MB | 408–423 MB |
| Shell artifact | 15 MB EXE + 116 MB runtime (incl. Python) | 21.5 MB (no backend) | 6.9 MB (no backend) |
| Native window / WebView2 | proven | proven in this prototype (GNU) | proven, young |
| Python backend integration | in-process, proven | needs sidecar/IPC/proxy (not built) | needs external backend/proxy |
| Origin guard compatibility | native | loopback external URL only; `tauri.localhost` → 403 | loopback URL; origin gate in `tinyjs.json` |
| Updater / installer / signing | proven Inno + minisign | Tauri updater/MSI possible, not built | unproven; no updater path |
| Observability / debugging | Python logs + CDP | CDP + Rust logs | no CDP; F12 only; weak |
| Size win in production | baseline | ~none (Python runtime remains) | ~8 MB at most (Python remains) |
| Maintenance risk | high Python packaging cost, but known | medium: sidecar + two toolchains | high: young runtime, third-party |

### 7.1 Feature coverage matrix

| Capability | Current app | M1 prototype | Status |
|---|---|---|---|
| Market board (dense tape, queues, buyer power, flags) | full | real read-only board + filters/sort/polling | **covered for shell test** |
| Technical chart (KLineCharts, indicators, drawing, raw/adjusted, periods) | full | real data, MA/BOLL/RSI, 3 tools, daily/weekly/monthly, raw/combined | **covered for shell test** |
| Market status / mstat panels | full | placeholder (`M1`) | not migrated |
| Fundamental / CODAL / quarters | full | placeholder | not migrated |
| FTS screening / master / funnel | full | placeholder | not migrated |
| Strategy tree | full | placeholder | not migrated |
| Portfolio | full | placeholder | not migrated |
| Sarkhati (order scheduling, dry-run) | full | placeholder; no execution | not migrated |
| Watchlist / live watch | full | placeholder | not migrated |
| Notifications | full | absent | not migrated |
| Settings / updates / tray | full | absent | not migrated |
| Local auth / user DB | full | simplified admin/bors123 only | not equivalent |

The M1 prototype proves the **shell**, not feature parity. A migration plan must
budget for the remaining eight destinations and their data contracts.

## 8. Market, technical and data-path findings

### 8.1 Units and displayed values

- `/api/market` `z_tot_tran` is in **million Rial**. The prototype multiplies by
  `1e6` before formatting (`marketValue`); the board KPI sums rows and displays
  `3.78 هزار میلیارد ریال` (3.780794e12 Rial) for the 6,018-row snapshot.
- `q_tot_tran` is shares; the chart volume is shares. Board and chart dates differ,
  so their volumes/prices must not be compared directly.
- `buyer_power` is a ratio; queue state is derived from `buy_q1_vol`/`sell_q1_vol`.

### 8.2 Board vs chart freshness (observed 2026-10-24T11:20Z)

| Source | Last data | Count | Notes |
|---|---|---:|---|
| `/api/market` meta | `d_even=20261014`, `last_sync=2026-10-14 16:03:04` | 6,018 | local `market_watch` snapshot; 3,614 live, 2,404 fossil |
| `/api/chart/فولاد` | `lastDataTime=2026-10-21` | 4,250 candles | live TSETMC CDN read; payload age ~19 min at capture |
| Board row فولاد | close 4,540 (2026-10-14) | — | `p_last=4,540`, value 13,401 million Rial |
| Chart last candle فولاد | close 4,230 (2026-10-21) | — | `priceBasis=last`; combined adjustment source `ledger+base-price-discontinuity` |

This is **not a prototype bug**: the board endpoint reads the local snapshot, while
the chart endpoint fetches the CDN even when fetch loops are disabled. The prototype
surfaces both dates. It does mean the “same data” claim must be stated per path: all
shells see the same board snapshot and the same chart cache, but they are not the
same trading session.

### 8.3 Technical payload

`/api/chart/فولاد` returns 4,250 candles (newest first), 4,250 factors, 28 adjust
events, 14 corporate events, `adjustSource="ledger+base-price-discontinuity"`,
`priceBasis="last"`. `adjustCapability.functional_available=false`; only the
combined (ledger + base-price discontinuity) method is available. No mock data is
inserted; the chart fallback path is `/api/history`.

### 8.4 Backend cache/revision inconsistency (pre-existing, needs owner review)

During the window, `/api/market` returned **different row-level snapshots with the
same `rev=0` and the same meta** (`d_even=20261014`, `last_sync=2026-10-14`):

- Shell pages (pywebview/Tauri/TinyJS final screenshots) showed a top value of
  ~5.8–8.8 میلیارد for the first sorted row.
- A direct fresh `/api/market` call at 11:20Z returned تاصیکو with
  `z_tot_tran=89,609` (≈89.6 میلیارد) and a total sum of 3,780,794 million Rial;
  `rev` was still 0.
- Delta polling returned `{"status":"unchanged","rev":0}` for that same endpoint.

The exact root cause was not established. The ETag/revision contract is built from
`(revision, d_even, h_even, fetched_at)` and therefore cannot represent row-level
changes; that is consistent with a client keeping an older body, but it does not
prove the mechanism. This is outside the shell migration and was **not introduced
by the prototype**, but it blocks any trustworthy “same snapshot” visual comparison
and needs backend-owner review before a migration decision. It is recorded as a
backend data-path risk, not as a shell result.

### 8.5 Data-path conclusion

The API is fast enough for both prototype pages at warm cache (`/api/market`
136 ms p50; `/api/chart` 594 ms p50). The user-visible slowness is dominated by
(a) shell/backend startup, (b) the first chart build/render, and (c) board breadth
(6,018 rows; 1.19 MB gzip). Changing the shell does not change (b) or (c).

## 9. Security and compatibility

### 9.1 Loopback guard contract (post-fix, `check_guard.py`)

| Case | Backend 8102 | Prototype proxy 8105 |
|---|---|---|
| No Origin, loopback Host | 200 | 200 |
| localhost Host + loopback Origin | 200 | 200 |
| External Origin (`http://evil.example`) | 403 | 403 |
| `Origin: null` | 403 | 403 |
| `Origin: http://tauri.localhost` | 403 | 403 |
| External Host (`evil.example`) | 403 | 403 |

The production backend was never modified. The prototype proxy initially
**rewrote Host without validating it**, so an external Host reached the backend as
200; this was found and fixed inside `serve_prototype.py` before the final runs.
The fix enforces the same loopback Host/Origin rule at the proxy edge. Evidence:
`artifacts/desktop-migration/security-guard-2026-10-24.json`.

### 9.2 Origin consequences for the shells

- **Tauri:** loading a bundled frontend from `http://tauri.localhost` is rejected by
  the guard. The prototype therefore loads `http://127.0.0.1:8105/` (external URL).
  That preserves the guard but requires a separately running same-origin server;
  production needs a native proxy or a sidecar serving the UI on loopback.
- **TinyJS:** the wrapper loads the loopback URL; `tinyjs.json` pins the origin and
  disables every native API except window controls. No guard weakening was needed.
- **pywebview:** the existing app already serves from its own loopback and passes.
- No CORS rule was added; `Origin: null` was never allowed. The prototype server
  binds `127.0.0.1` only and is a measurement tool, not a production server.

## 10. Stability, installation, update and maintenance

- **pywebview (current):** proven installer/updater/portable flows, graceful close,
  boot page, DPI and GPU fallbacks. Costs: 10–13 s shell init, ~540 MB shell RSS,
  Python packaging, and a boot-page state machine that complicates CDP/automation.
- **Tauri:** the GNU build finished in 41m31s with a linker warning
  “multiple non-default manifests”; the EXE launched, rendered both pages and
  exposed CDP. Official MSVC build, signed installer, updater, single-instance,
  tray and sidecar are **NOT_MEASURED/not built**. The repo scaffold has no
  backend wiring; adding it is a real engineering project, not a packaging tweak.
- **TinyJS:** 5.87 MB app + 1.0 MB launcher; fastest small-shell option. No CDP,
  no in-page diagnostics, no proven updater/installer/code-signing path, limited
  native API, and a young 0.65 runtime. The wrapper is a URL host; all app logic
  stays in the existing web app and Python backend.
- **Install size:** replacing pywebview with Tauri or TinyJS does **not** remove
  the 116 MB Python runtime, 269 MB DB or 76 MB bootstrap. The shell itself is a
  small part of the installed footprint; a 6.9 MB TinyJS shell cannot be compared
  to a 131 MB “current shell” that includes Python.
- **Update/rollback:** Tauri/TinyJS prototypes have no updater. The current
  minisign/Inno flow must be preserved or reimplemented; this is an M1 gate, not a
  detail.
- **Live fetching:** the comparison backend ran with loops disabled; only the chart
  endpoint's on-demand CDN read occurred (one backend, no loop). A full-market live
  refresh test was not run, so live board freshness/latency is `NOT_MEASURED`.

## 11. NOT_MEASURED

- Shipped current shell **cold** start from a fresh profile (boot-page CDP timeout).
- TinyJS in-page JS heap, console/page errors, rAF frame timing, 1920×1080 layout
  (no CDP; physical display is 1280×1024 and TinyJS clamps width).
- Tauri MSVC build, signed installer, updater, tray, single-instance, sidecar,
  crash recovery (no MSVC/admin; prototype has none of these).
- Full-market live TSETMC refresh latency/freshness (loops disabled; chart CDN only).
- Full six-round CPU-seconds workload; only 3 s idle CPU samples.
- Disk I/O, GPU counters, long-session memory-leak behavior.
- Feature parity for the eight destinations not migrated in M1.
- Auto-update and rollback for both candidate shells.

## 12. Recommendation and next steps

**Decision: do not migrate the production shell in this cycle.** Keep pywebview
1.0.97 as the shipping shell; keep the Tauri/TinyJS prototypes as measurement
branches, not deliverables.

Why:

1. The current app's user-visible startup (36–57 s) is not a shell-only problem.
   Tauri removes ~9–10 s of shell initialization but still needs the Python backend;
   the backend/boot path remains the dominant term. TinyJS saves more shell time but
   has the same backend dependency and weaker production infrastructure.
2. Data correctness/freshness is the higher-priority risk: board 2026-10-14 vs
   chart 2026-10-21, and a same-`rev` cache inconsistency. Fix these before changing
   the window around them.
3. Feature parity is far from complete; migration would freeze or fork eight
   destinations and the updater/installer contract.
4. Tauri is the only candidate with a credible native sidecar/updater path. TinyJS
   is viable only as a deliberately thin URL wrapper with an external backend and a
   closed observability/update gap.

Recommended sequence:

1. Backend/data path: make the market revision/ETag reflect row changes (or disable
   the cached 200 body in favor of a consistent snapshot), single-flight the
   snapshot build, and decide the live-market refresh contract. Then re-run the
   three-shell suite on one frozen snapshot.
2. Startup: profile the installed app's boot stages (data extraction, screener warm,
   uvicorn, WebView2) and reduce the dominant stage. A 10 s shell win is not worth a
   migration if the backend costs 30 s; a backend win may be worth more than either
   shell.
3. If shell migration is still desired: Tauri v2 with MSVC, a Python sidecar that
   starts/stops with the window, a native loopback proxy (no CORS, no guard
   weakening), updater/signing, and prototypes of market-status + FTS/fundamental
   under the same harness. Only then open an M2 gate.
4. TinyJS: keep as a benchmark/fallback, not a production candidate, until it has
   CDP/diagnostics, updater, signing and a maintenance plan.

## 13. Reproduction

```bash
# backend (read-only benchmark mode)
BORS_NO_FETCH_LOOPS=1 BORS_CODAL_AUTO=0 .venv/Scripts/python.exe \
  -m uvicorn app:app --host 127.0.0.1 --port 8102

# prototype build + same-origin proxy
cd frontend && ../_tools/node/node.exe node_modules/vite/bin/vite.js build --config prototype/vite.config.mjs
cd .. && .venv/Scripts/python.exe tools/desktop-migration/serve_prototype.py \
  --root frontend/prototype/dist --backend http://127.0.0.1:8102 --port 8105

# shell benchmarks
_tools/node/node.exe tools/desktop-migration/bench_shell.mjs ...   # pywebview/Tauri
.venv/Scripts/python.exe tools/desktop-migration/bench_tinyjs.py --runs 3
.venv/Scripts/python.exe tools/desktop-migration/bench_proto_api.py --base http://127.0.0.1:8102 --reps 10
.venv/Scripts/python.exe tools/desktop-migration/check_guard.py
_tools/node/node.exe tools/desktop-migration/ui_smoke.mjs --cdp 9810
```

Tauri build (GNU, this machine):

```bash
export PATH="$PWD/_tools/rust/cargo/bin:$PWD/_tools/mingw/mingw64/bin:$PATH"
export CARGO_HOME="$PWD/_tools/rust/cargo" RUSTUP_HOME="$PWD/_tools/rust/rustup"
cargo build --release --manifest-path prototypes/tauri-m1/src-tauri/Cargo.toml
```

TinyJS build: `_tools/tinyjs/tinyjs.cmd build` from `_tools/tinyjs-site`
(source/config mirrored in `prototypes/tinyjs-m1/`).

## 14. Evidence and commit trail

Final evidence:

- `artifacts/desktop-migration/2026-10-23T22-24-55-111Z-portable-warm/` — shipped 1.0.97 warm baseline (3 runs)
- `artifacts/desktop-migration/2026-10-23T22-29-45-852Z-portable-rss/` — corrected total RSS (955 MB)
- `artifacts/desktop-migration/2026-10-24T11-24-02-837Z-proto-pywebview-final/` — final pywebview (3 runs + screenshots)
- `artifacts/desktop-migration/2026-10-24T11-26-19-450Z-proto-tauri-final/` — final Tauri (3 runs + screenshots)
- `artifacts/desktop-migration/2026-10-24T11-27-54Z-tinyjs/` — final TinyJS (3 runs + PrintWindow screenshots)
- `artifacts/desktop-migration/2026-10-24T11-29-43-772Z-proto-pywebview-cold-final/` — cold pywebview
- `artifacts/desktop-migration/api-proto-2026-10-24.json` — focused API probe
- `artifacts/desktop-migration/data-freshness-2026-10-24.json` — board/chart freshness
- `artifacts/desktop-migration/security-guard-2026-10-24.json` — Host/Origin matrix
- `artifacts/desktop-migration/ui-smoke/` — functional technical checks

Branch: `mission/desktop-migration-m0-m1`, based on `9d50f0a` (`main`). The branch
contains only migration tooling, the prototype, the shells and this report; `main`
is untouched. Mission commit `6957050` carries the tooling, prototypes, final
evidence and this report; later report-only edits, if any, are listed by
`git log mission/desktop-migration-m0-m1`.

## Appendix A — raw per-run summaries

### pywebview final (warm)

| Run | CDP | Page | Shell | Market | Technical | RSS | Heap | Scroll p50/p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 11,139 | 12,512 | 13,869 | 619 | 3,463 | 547 | 11.7 | 17.3 / 50.0 |
| 2 | 10,807 | 11,715 | 13,167 | 860 | 4,949 | 541 | 11.8 | 31.5 / 50.2 |
| 3 | 11,730 | 12,712 | 13,820 | 607 | 3,293 | 552 | 11.8 | 17.5 / 48.9 |

### Tauri final (warm)

| Run | CDP | Page | Shell | Market | Technical | RSS | Heap | Scroll p50/p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1,877 | 2,804 | 3,988 | 589 | 2,816 | 450 | 11.5 | 17.0 / 49.4 |
| 2 | 1,420 | 2,138 | 3,175 | 572 | 3,289 | 460 | 12.1 | 16.9 / 34.1 |
| 3 | 1,633 | 2,853 | 3,903 | 642 | 2,592 | 461 | 12.1 | 16.7 / 33.4 |

### TinyJS final (warm)

| Run | Window | Page | Login→market | Launch→market | Technical | RSS |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 2,979 | 3,520 | 1,342 | 5,686 | 1,213 | 408 |
| 2 | 2,711 | 3,105 | 1,349 | 5,304 | 2,161 | 423 |
| 3 | 2,187 | 2,568 | 1,306 | 4,704 | 1,115 | 408 |
