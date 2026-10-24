# Phase C — current-shell startup baseline and evidence-based fix

Scope: current `main` application, latest mission branch
`mission/desktop-tinyjs-first-2026-10-24`. These are startup-stage measurements,
not a migration benchmark. No production behavior was changed for measurement;
the only production changes are the verified blockers/optimization described below.

## Host and measurement path

- Windows 10 x64, **2 logical / 1 physical CPU**, **3.9 GB RAM**.
- Backend: real FastAPI app from this commit, isolated `BORS_WORK_DIR` copy of
  `market.db` (+ `user.db`, `fts_thresholds.json`, `market.db.lzma`, baseline stamp).
- Network loops and the Codal worker are off (`BORS_NO_FETCH_LOOPS=1`,
  `BORS_CODAL_AUTO=0`) so no second TSETMC fetcher runs. The technical chart's
  on-demand CDN read remains enabled and produced a 200 with a real candle body.
- UI path: the application's **supported Edge app-window fallback**
  (`BORS_NATIVE_WINDOW=0` + `BORS_BROWSER_DEBUG_PORT`). The native pywebview
  WebView2 controller could not be used reliably in this agent session: a
  minimal pywebview window needed ~27–40 s for a static page, the full boot page
  arrived at 76–162 s, and one run failed with
  `WebView2 initialization failed (0x800700AA) The requested resource is in use`.
  Native-shell numbers are therefore recorded as observations, not as the
  baseline median. The Edge path exercises the same backend, boot page, SPA,
  login, market board, technical chart, and fundamental APIs.
- Login is client-side (`admin` / `bors123` in the isolated profile); the probe
  fills and submits it. `market ready` = first rendered `tape-row`;
  `chart ready` = chart canvas + successful `/api/chart` body + FTS freshness
  line with a real candle count; `fundamental ready` = FTS summary/P-NAV panel.
- **Cold** = fresh WORK_DIR copy and fresh Edge profile per run.
  **Warm** = one unrecorded warmup, then the same WORK_DIR/profile reused.
  The OS file cache is not purged; cold/warm differ in app/profile state only.
- Times are from Popen of `bors_entry.py` (process launch), not from the harness
  start. Medians over n=3; p95 is not reported because n<20.

Reproduce:
```
.venv/Scripts/python.exe tools/desktop-migration/phase_c_startup.py \
  --label baseline-browser-cold --mode cold --runs 3 --browser-fallback \
  --template %TEMP%/bors_phasec/template \
  --out-dir artifacts/desktop-migration/phase-c/baseline-browser-cold
```
The template is a copy of the operational `market.db` plus `market.db.lzma`,
`user.db`, `fts_thresholds.json`, and `market.db.baseline` (sha256 of the lzma).
Profiles/DB copies are created under `%TEMP%/bors_phasec/scratch-<label>`, never
in the repository.

## Baseline (before the startup fix)

Median milliseconds (n=3), cold | warm:

| Stage | Cold | Warm |
|---|---:|---:|
| Backend HTTP ready | 31,506 | 24,801 |
| App document ready (login visible) | 61,738 | 58,410 |
| First board publish (server) | 46,114 | 41,801 |
| First market board usable | **65,901** | **63,881** |
| First technical chart usable | **88,193** | **83,665** |
| First fundamental panel usable | **90,418** | **86,860** |

Peak process-tree RSS: 1,001–1,071 MB cold, 842–875 MB warm.
Idle RSS after fundamental: 903–932 MB cold, 835–852 MB warm.
CPU is effectively saturated on the single core through page load
(70–98% of one core in the idle sample of the same run).

The backend's own stages on the cold runs: preflight/library import ~19.6–29.4 s,
uvicorn HTTP ready ~25.8–34.7 s, first full board build ~41.6–48.0 s. The
remaining board time is SPA parse/render and the initial `/api/market` transfer
(0.77–0.95 s server response, ~1.2 MB gzip).

## Verified blockers fixed during Phase C

1. **Chart route was hijacked (origin/main `01ded7d`).** The
   `@router.get("/api/chart/{symbol}")` decorator sat on `_candle_closings`, so
   FastAPI treated its `candles` argument as a required input and every chart
   request returned **422**. The UI still painted a canvas and FTS text with
   "تعدادِ کندل اعلام نشده", so only an HTTP check exposed it. Fixed by moving
   the decorator to `get_chart_tsetmc`; guard `dev/chart_route_v1.py` (6 checks).
2. **Concurrent heavy imports crashed/stalled startup.** A manual launch died
   with `Fatal Python error: take_gil: PyCOND_WAIT(gil->cond) failed` while the
   preflight worker imported pandas and the main thread imported
   pywebview/edgechromium. The same race presented as 60–160 s boot-page delays.
   `_IMPORT_LOCK` serializes the two import sites; no behavior change when the
   imports are not concurrent.
3. **Startup screener warm competed with first paint.** On this 1-core host the
   scan runs for roughly 100 s. It is the dominant *controllable* backend
   contention, not the DB/build itself.

## Optimization and after-baseline

The screener warm now waits (bounded at 25 s) for the first published board
snapshot and runs at `THREAD_PRIORITY_LOWEST`. If the board is never opened, the
timeout still warms the cache for the fundamental tab. The scan itself is
unchanged; single-flight and cache semantics are untouched.

After medians (n=3), cold | warm:

| Stage | Cold | Warm |
|---|---:|---:|
| Backend HTTP ready | 23,782 | 19,690 |
| App document ready | 41,154 | 40,930 |
| First board publish | 36,094 | 29,274 |
| First market board usable | **45,928** | **45,975** |
| First technical chart usable | **67,045** | **64,728** |
| First fundamental panel usable | **69,143** | **67,314** |

Cold board −30%, chart −24%, fundamental −24%; warm board −28%, chart −23%,
fundamental −23% (descriptive, from the medians above). Peak RSS 989–1,017 MB
cold, 839–899 MB warm; idle 896–952 MB cold, 816–856 MB warm.

Diagnostics (n=1 each, same cold protocol; see `diagnostics.md`):
skipping the screener warm gave 44.0 s board, low priority alone 53.4 s,
low priority + first-board deferral 44.7 s. This is why the deferral is kept.

## Remaining risks / not measured

- Native pywebview/WebView2 startup on this host is an environment-level
  failure; a stable native cold median is **not measured**. The Edge fallback
  baseline is reproducible but is not the native shell's user path.
- CPU/RAM figures cover the backend and Edge process trees; GPU/compositor
  attribution is not measured.
- The full frontend suite (2,070 passed / 8 failed / 5 skipped) contains
  pre-existing failures. `funnel-row-symbol-visible`, `technical-symbol-race`,
  and `watch-dossier` fail identically on clean `origin/main` `b5f5f6c`;
  `m1-ux-integrity` and `inspector-glance-data` pass in isolation and failed
  only in the 99-minute single-core full run. No failure was introduced by the
  Phase B/C changes.
- Only startup was optimized; no migration candidate was measured here.
