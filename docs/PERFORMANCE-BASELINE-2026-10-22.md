# BorsTerminal — Performance Baseline (2026-10-22)

Branch: `mission/coder3-performance-resource-2026-10-22`
Baseline commit: `784d9d8a` (working branch created from this commit)
Environment: Windows 10 Pro 19045 x64 · Intel CPU · 8 GB RAM
Runtime: CPython 3.12.10 (local portable), Node 22.22.0
Data: `market.db` reconstructed from the verified `data-latest` release
(75.0 MB `.lzma` → 280.9 MB; `MAX(d_even)=20261014`, 6,022 board rows,
6,018 instruments, 129,577 daily-price rows, 8,723 financial statements).
Backend mode: `BORS_NO_FETCH_LOOPS=1` (no TSETMC polling/writes),
`BORS_GZIP_LEVEL=1`, `127.0.0.1:8000`.
Frontend: production `vite build`, real Edge (Chromium), 1366×768.

This baseline is read-only: no operational database writes were made by any
benchmark. The only startup writes are the application's normal idempotent
schema/candle maintenance, already present in the release data.

## 1. Methodology

| Tool | What it measures | Samples |
|---|---|---|
| `tools/performance/bench_api.py` | UI HTTP paths: cold call, min/p50/p95/max, raw/gzip bytes | 30 per light path, 10 per expensive path |
| `tools/performance/ui_probe.js` (derived from `_audit/perf/fe_probe.js`, `/master` marker corrected) | cold start, tab click→ready, long tasks/TBT, request fan-out, heap, zoom/pan | 3 runs |
| `_audit/perf/mstat_profile.py` | snapshot/panel CPU on a throwaway DB copy | 3 repetitions, median |
| `dev/mstat_snapshot_singleflight_v1.py` | concurrent cold snapshot builds | 8 simultaneous connections |

Server caches were cold at each browser run (process restart; screener warm
completed before measurements). Request-level timings are in the JSON
artifacts; this document summarises them.

Raw artifacts: `artifacts/performance/2026-10-22/`.

## 2. Backend baseline (warm server, 30 samples unless noted)

| Path | p50 | p95 | max | Body (raw / gzip) |
|---|---:|---:|---:|---:|
| `/api/market` | 132.6 ms | 240.5 ms | 360.4 ms | 6,814,415 / 1,220,692 B |
| `/api/market/delta` | 3.9 ms | 9.8 ms | 67.9 ms | 45 B |
| `/api/market/sync-state` (cold) | 3.6 ms (cold 2,270 ms) | 13.0 ms | 15.2 ms | 46 B |
| `/api/mstat/summary` | 14.1 ms | 37.0 ms | 91.4 ms | 3,725 / 1,441 B |
| `/api/mstat/smart-money` | 12.8 ms | 39.7 ms | 43.6 ms | 4,733 / 2,056 B |
| `/api/mstat/mainwatch` | 27.7 ms | 40.1 ms | 45.6 ms | 77,870 / 17,376 B |
| `/api/mstat/treemap` | 26.3 ms | 61.4 ms | 69.2 ms | 93,971 / 21,238 B |
| `/api/mstat/phases` | 14.4 ms | 21.4 ms | 23.6 ms | 474 B |
| `/api/mstat/board` (10) | 56.1 ms | 90.8 ms | 90.8 ms | 247,101 / 61,398 B |
| `/api/screener` (10) | 194.0 ms | 236.4 ms | 236.4 ms | 1,203,793 / 122,609 B |
| `/api/fundamental/فولاد` (10) | 187.2 ms | 338.7 ms | 338.7 ms | 20 KB response |
| `/api/fundamental/فولاد/quarters` (10) | 179.0 ms | 298.9 ms | 298.9 ms | 1.3 KB |
| `/api/funnel` (10) | 57.9 ms | 108.3 ms | 108.3 ms | 7,574,448 / 388,077 B |
| `/api/index/tedpix?limit=0` | 298.5 ms | 733.4 ms | 1,780.1 ms | 744,147 / 136,060 B |
| `/api/notifications/sources` | 342.9 ms | 1,105.8 ms | 1,139.9 ms | 398 B |
| `/api/notifications/feed` (cold browser) | — | — | 2,227 ms | 4,820 B gzip |
| `/api/chart/فولاد` (10) | 517.8 ms | 916.8 ms | 916.8 ms | 1,121,706 / 201,831 B |
| `/api/fts/فولاد` (10) | — | — | 1,146 ms warm browser | 28 KB |
| `/api/universe/live` | 177.6 ms | 239.9 ms | 296.7 ms | 383,332 / 27,117 B |

Cold cache misses (first call per process):
`mstat board` 2,655 ms, `mstat summary` 1,338 ms, `screener` 1,488 ms,
`market sync-state` 2,270 ms, `index/tedpix` 1,905 ms.

## 3. Browser baseline (real Edge, production build)

| Scenario | Result |
|---|---|
| Cold start FCP | 200–692 ms |
| Cold start first usable (`/master` funnel) | 1,382 / 1,593 / 2,493 ms (3 runs) |
| Cold API payload | 1.20–1.58 MiB encoded |
| Market tab first open | 2,621 ms (later passes 907–924 ms) |
| Fundamental tab (corrected method) | rows appear ≈1.9 s after a direct click; the earlier 6.0 s figure was Playwright actionability on the sidebar link, fixed in `98bc436a` |
| Market-status tab first open | **10,795 ms** (20 requests, 227 KiB, TBT 270 ms) |
| Market-status later passes | 1,265–1,297 ms |
| Technical tab first open | 2,852 ms (chart symbol switch 3.3–4.8 s, Coder2-owned) |
| Strategy FTS tab | 902–1,422 ms |
| Chart zoom / pan | 508 ms / 481 ms; median frame 18 ms; no >100 ms frames |
| JS heap across tab cycle | 27 → 90 MB, no monotonic leak observed in this window |
| Console errors | 0 in this run; a chart-only `reading 'bar'` pageerror appeared in later full tab cycles but not in isolated probes (see final report) |

**Dominant confirmed bottleneck (outside protected ownership):** the first
market-status open fans out to 19–20 panel requests. With a cold process,
every request built its own mstat snapshot because the snapshot cache was read
outside the build lock. Measured profile on a DB copy: one snapshot build
≈262 ms plus ≈164 ms of repeated `daily_prices` aggregation, while all 16 warm
panels together cost ≈914 ms on one connection. The resulting stampede is
visible as 3–9.5 s per request and 10.8 s to a usable tab.

## 4. Resource baseline

| Metric | Value |
|---|---|
| Backend RSS after warm-up | ≈343 MB (Python + SQLite page cache) |
| Idle CPU after warm-up | 0 % (sampled 3 s; no background work in `BORS_NO_FETCH_LOOPS=1`) |
| Backend startup to port ready | 8 s (warm screener disk cache) |
| Server warm completion (screener) | 16 s |
| Browser JS heap after tab cycle | 27–90 MB (see above) |
| API request volume, market-status first open | 19–20 requests / ≈227 KiB encoded |

CPU-seconds for the baseline are **NOT_MEASURED** for the full six-round
workload; Round 5 introduces a dedicated sustained-session sampler. The
baseline cold-start figure (first launch with no screener disk cache) was
≈3 minutes of one-core warm-up; subsequent starts use the disk cache (16 s).

## 4b. Methodology correction (applied during Round 3, commit 98bc436a)

The first browser probe clicked sidebar links with Playwright's actionability
wait. After the technical/chart tab that wait lasted ~6 s and was charged to
the *next* tab's click→ready time, so Fundamental appeared to take 6 s on every
visit. `tools/performance/readiness_diag.js` isolated the cause; a direct DOM
click shows the route change starting immediately and the screen rows arriving
in ≈1.9 s. All later browser numbers use the direct-click method. Baseline
numbers from the old method are kept only where the effect is negligible
(market-status first open was dominated by its 19 cold requests).

## 5. Known pre-existing issues captured at baseline

- `dev/mstat_status_panels_contract_v1.py`: 201/203 checks pass; the two
  failures expect a `free_float` blocker while the current engine emits
  `official_impact` after commit `ef92c89c`. Unrelated to this mission's
  changes; recorded as `PRE_EXISTING`.
- `/api/chart/<missing-symbol>` spends ≈2.3 s before returning a 200 error
  body (Coder2-owned chart path).
- `/api/notifications/sources` scans `codal_notices` with `replace()`-wrapped
  `MAX()` on every request (343 ms p50 for a 398-byte body).
- A console-only `TypeError: Cannot read properties of undefined (reading 'bar')`
  appeared during full tab-cycle runs after Round 1 but not in isolated page
  probes; status `INVESTIGATING` (Round 3).
