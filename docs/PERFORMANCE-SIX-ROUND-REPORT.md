# BorsTerminal — Six-Round Performance & Resource Report (2026-10-22)

Branch: `mission/coder3-performance-resource-2026-10-22`
Base: `784d9d8a` · Rounds: `1147447a`, `77d32d90`, `cf9c0048`, `e250b325`,
`e8bfcf07`, `941be7c0` · Harness correction: `98bc436a`
Machine: Windows 10 Pro 19045 x64, 8 GB RAM, Intel CPU
Runtime: portable CPython 3.12.10, Node 22.22.0, Edge Chromium, 1366×768
Data: verified `data-latest` release (`market.db` 280.9 MB, session 20261014,
6,022 board rows). Backend: `BORS_NO_FETCH_LOOPS=1`, gzip level 1, port 8000.
Market was closed for every measurement; live-session sync/polling is
**NOT_MEASURED** (see limitations).

## A. Executive result

The largest measurable problems were not in the chart engine. They were cache
stampedes, duplicated payloads, per-request schema work and an unbounded
frontend cache:

- **market-status first open**: 10,020 ms → 3,827 ms median (−61.8%, 3 cold
  servers + 3 fresh browser contexts). A cache stampede was rebuilding the
  same 260 ms snapshot up to 19 times; single-flight builds once, and a boot
  warm-up moves panel work off the click path.
- **notifications source health**: 342.9 ms → 22.3 ms p50 (−93.5%, n=30).
  Two full `codal_notices` scans per request became one content-keyed cache.
- **TEDPIX index series**: 171.2 ms → 43.9 ms p50 (n=30); repeat requests are
  now 5.4 ms / 0 bytes via a content ETag 304 (−96.8%). The response is
  produced by the same builder; the guard compares both bodies.
- **default landing payload**: 1,235 KiB → 43 KiB median encoded (−96.5%,
  n=3). The landing no longer downloads the 6.8 MB market board just to read a
  closing price, and the command palette no longer subscribes to that board
  while closed.
- **DB connection setup**: 2.03 s → 1.53 s CPU per 300 connections (−24.6%);
  p50 7.74 → 6.45 ms. Idempotent schema DDL now runs once per
  `(file, schema_version)` and still re-runs after an external ALTER.
- **post-idle market-status first open**: 7,043 ms → 4,333 ms (−38.5%) after
  the session-aware TTL and board-first warm-up. Live-session behavior is not
  claimed (data changes every sync, so the cache correctly invalidates).

No feature, indicator, chart capability, data field, freshness contract or
validation was removed. The market page still receives the same full board;
the closes map is a second, narrower read of the same row for consumers that
never needed the board.

## B. Before/after table

| Workflow | Baseline | Final | Δ | n | Notes |
|---|---:|---:|---:|---:|---|
| Market-status first open (cold server, fresh context) | 10,020 ms | 3,827 ms | −61.8% | 3 + 3 | median; first-open samples include external TEDPIX CDN variance |
| Market-status probe pass0 | 10,795 ms | 7,812 ms | −27.6% | 1 | single-flight only, before boot warm-up |
| Market-status first open after 60 s idle | 7,043 ms | 4,333 ms | −38.5% | 1 + 1 | expensive restart; labelled n=1 |
| Notifications source panel p50 | 342.9 ms | 22.3 ms | −93.5% | 30 | p95 1,105.8 → 327.7 ms (first call pays the cold query) |
| TEDPIX 200-path p50 | 171.2 ms | 43.9 ms | −74.4% | 30 | same bytes; direct ORJSON response |
| TEDPIX conditional p50 | n/a (no ETag) | 5.43 ms / 0 B | — | 30 | fresh cache only; expired cache never 304s |
| Landing encoded API bytes | 1,235 KiB | 43 KiB | −96.5% | 3 + 3 | `/api/market` gone from the landing request list |
| Closes map (replaces full board for prices) | 1,220,692 B gzip (board) | 31,130 B gzip | −97.5% | 30 | p50 41.9 ms; 304 p50 16.6 ms after first |
| get_db p50 / CPU per 300 connections | 7.74 ms / 2.03 s | 6.45 ms / 1.53 s | −24.6% CPU | 300 | isolated HEAD worktree vs current |
| Cold start FCP | 200–692 ms | 205–612 ms | flat | 3 | corrected harness; method differed |
| Market tab first open (corrected method) | 1,877 ms | — | not compared | 1 | below-fold sections unchanged |
| Fundamental tab rows | 1.9 s (corrected) | 1.9 s | flat | 1 | the earlier 6 s was Playwright actionability, not app time |
| Chart symbol switch | 4.4–5.9 s | 4.4–5.9 s | unchanged | 5 | **Coder2-owned**; CDN-bound |
| Heavy scroll/zoom/pan | zoom 508 ms, pan 481 ms; median frame 18 ms | zoom 452 ms, pan 429 ms; median frame 18 ms | within noise | 1 run | no regressions observed |

Raw samples: `artifacts/performance/2026-10-22/`; machine matrix:
`artifacts/performance/six-round-results.csv`.

## C. Resource table

| Resource | Baseline | Final / best evidence |
|---|---|---|
| Landing API transfer | ~1.2 MB encoded, 4–7 requests | ~43 KiB median, 4–7 requests; `/api/market` absent |
| Market-status first-open payload | 226 KiB encoded | 94 KiB (Round 1), 125 KiB after idle (Round 6) |
| Head-of-line fan-out | up to 19 snapshot builds for one cold tab | 1 build (8-way guard), panel caches warm at boot |
| get_db CPU | 2.03 s / 300 connections | 1.53 s / 300 (−24.6%) |
| DB DDL per request | CREATE/ALTER/PRAGMA table_info every time | once per (file, schema_version); external ALTER invalidates |
| Backend idle outside session | 0 % CPU (sampled 3 s) | 0.48 s renderer task time and one 31 KiB closes poll per 60 s (renderer CPU) |
| Sustained session (6 tab cycles) | heap 23.9 → 34.4 MB, nodes 4,278, listeners 844 | nodes/listeners flat; heap plateau ≈34 MB; no monotonic leak observed |
| Chart symbols (60 switches) | post-GC heap 27.8 → 28.2 MB | no leak observed; ETag cache bounded to 32 entries preventively |
| Frontend ETag cache | unbounded Map | 32-entry LRU; unit-tested eviction and hot-entry 304 |
| Server RSS after warm-up | ≈343 MB (baseline) | not re-measured after all rounds — **NOT_MEASURED** |
| Startup | port ready 8 s; screener warm 16 s (disk cache) | unchanged; mstat warm completes by 18 s |
| Live-session network/CPU | — | **NOT_MEASURED** (market closed; loops disabled) |

## D. Round-by-round history

### Round 1 — cache stampede on the market-status tab (`1147447a`)

Evidence: 19–20 panel requests take 3–9.5 s each on a cold process (10.8 s to
ready). `load_snapshot` read `_SNAP_CACHE` outside the build lock, so every
concurrent cold request rebuilt the same ~260 ms snapshot (plus ~164 ms of
duplicated `daily_prices` aggregation). Change: single-flight snapshot build
per bank-state key (waiters re-read the cache; a bounded wait falls back), plus
a boot warm-up that populates the exact panel keys the UI reads. Measured:
10,795 → 7,812 ms with single-flight alone; 10,020 → 3,827 ms median with the
warm-up. Guard: 8 concurrent cold loads build exactly once (was 8).

### Round 2 — notifications source health (`77d32d90`)

Evidence: a 398-byte body took 343 ms p50; the query did
`MAX(fetched_at)` (61 ms, no index) and `MAX(canonical publish_date)` (297 ms,
`replace()` per row) over 36 k notices on every request. Change: key the two
facts by `(DB file identity, COUNT(*), MAX(publish_date))`; inserts/replacements
change the key immediately, a 120 s ceiling bounds invisible in-place edits,
in-memory DBs remain uncached. Measured: 342.9 → 22.3 ms p50; direct warm call
4.4 ms vs 508 ms cold.

### Round 3 — TEDPIX series response (`cf9c0048`)

Evidence: the 4,311-candle / 744 KB index series was rebuilt and re-serialized
per request (171 ms p50 after full warm-up). Change: return an
`ORJSONResponse` directly (same bytes) and add a content ETag varied by limit
and price basis; fresh-cache conditional requests return 304 with no body.
Measured: 171.2 → 43.9 ms p50; conditional 5.43 ms / 0 B. Guard compares the
response body with `build_tedpix_payload` and verifies refresh/limit/expiry
invalidation. The same commit corrected the browser harness: Playwright's
actionability wait after the chart tab was being charged to the next tab
(6 s false Fundamental delay).

### Round 4 — end-to-end landing data path (`e250b325`)

Evidence: `/master` fetched the full 6.8 MB board (≈1.2 MB gzip) because
`useMarketCloses` selected one closing price from the shared feed, and the
always-mounted command palette subscribed to the same feed while closed.
Change: `/api/market/closes` (two columns from the same `market_watch` row,
ETag over revision/day/hour/fetched_at), `useMarketCloses` reads that 31 KB map,
and the palette query is enabled only while open. Measured: 1,235 → 43 KiB
median encoded per landing, `/api/market` absent from the request list. Same
p_closing values (guard); vitest 33/33; tsc 0.

### Round 5 — per-connection CPU and memory (`e8bfcf07`)

Evidence: `get_db` spent 7.9 ms p50 / 2.17 s CPU per 300 connections re-running
idempotent CREATE/ALTER/PRAGMA checks. Change: run them once per
`(DB_PATH, PRAGMA schema_version)`; connection-local PRAGMAs and UDFs stay.
Also bound the frontend's per-URL ETag cache to 32 LRU entries. Measured:
p50 7.74 → 6.45 ms, CPU 2.03 → 1.53 s (−24.6%) in a clean HEAD-vs-current
A/B; external ALTER invalidates (guard). Sustained-session probes found no
monotonic leak (nodes/listeners flat; chart stress 27.8 → 28.2 MB), so the LRU
is reported as prevention, not a measured saving.

### Round 6 — durable panels outside session (`941be7c0`)

Evidence: a market-status first open 60 s after startup took 7.0 s even though
no data changed; the 45 s TTL had discarded every panel. Change: TTL is 45 s
during the session and 300 s outside; the cache key remains the four data
markers; boot warm-up builds the shared board first (history rebuild bumps
`static_rev`) and re-keys once if the state changes during warm-up. Measured:
7,043 → 4,333 ms and 258 → 125 KiB encoded for the post-idle open. An attempted
WAL-file signature was reverted (SQLite creates/deletes `-wal` per connection,
so the key changed every request); moving `journal_mode=WAL` out of the
per-request path showed no A/B benefit and was rejected.

## E. Rejected optimizations

1. **WAL file mtime in the mstat cache key** — made every connection produce a
   new key; cache never hit. Measured post-idle first open 8,549 ms
   (`first-open-r6-after.json`). Reverted inside Round 6.
2. **Moving `journal_mode=WAL` off the per-request path** — A/B p50 6.29 vs
   6.31 ms; no benefit. Not applied.
2b. **TTL-only without board-first warm-up** — 7,321 ms post-idle
   (`first-open-r6-after2.json`), because the warm-up key was captured before
   the board/history build changed `static_rev`. The final board-first warm-up
   brought it to 4,333 ms; the intermediate key-before-board run is
   `first-open-r6-after3.json` (5,798 ms).
3. **Deferring below-fold MarketStatus sections** — would change product
   behavior and break the "every section fetches its endpoint" contract test;
   not applied.
4. **Bounding chart-body caching with measured savings** — chart responses
   carry no ETag, so the bounded cache is preventive only; no heap win claimed.
5. **Wiring all status panels to `/api/mstat/board`** — the right next step,
   but it requires a cross-component data-source refactor; not attempted in
   this mission. The endpoint already exists and returns all 16 panels with a
   shared state.
6. **Full market-board payload trimming** — would require a field-by-field UI
   audit and risks removing information; not attempted.
7. **Live-session polling changes (funnel POST every 5/20 s)** — not measured
   in a live session; no change made without evidence.

## F. Safety and compatibility

Functional gates actually run (final state):

- Python: `mstat_snapshot_cache_v1` 10/10, `mstat_snapshot_singleflight_v1`
  4/4, `notifications_sources_cache_v1` 6/6, `test_notifications_v1` 30/30,
  `market_index_etag_v1` 8/8, `stale_wiring_v1073` 19/19,
  `market_closes_v1` 5/5, `get_db_schema_once_v1` 6/6,
  `mstat_cache_durability_v1` 4/4, `persian_glyph_guard` 4/4.
- `dev/mstat_status_panels_contract_v1.py`: **201/203**, two **PRE_EXISTING**
  failures (`free_float` expected by the guard; engine emits `official_impact`
  since `ef92c89c`; proven from HEAD, not from this mission).
- Frontend: `npx tsc -b` 0 errors; `npm run build` PASS; targeted Vitest
  39/39 (pipeline, palette, status page, conditional/LRU).
- Full `python dev/run_all_tests.py` (both dev servers closed):
  **NOT_COMPLETED / BLOCKED_BY_TIME**. The runner has 170 suites; after the
  session's 10-minute background cap it was at `dev/test_fts_asof_cutoff.py`
  (~30th suite) with no observed failure, but its stdout is buffered and no
  pass/fail summary exists. It is not relabelled as passing. Targeted guards
  for every changed subsystem all passed (above).
- Full `npx vitest run`: **NOT_COMPLETED** — stopped at 122 of 201 test files
  after ~20+ minutes; no failure appeared in the emitted output. Targeted
  Vitest (the files covering changed code) passed 39/39. Exact summary:
  `artifacts/performance/2026-10-22/final-validation.json`.
- `dev/version_anchor_guard.py` 6/6 PASS; `dev/struct_check.py` PASS.
- No data removal: closes map values equal the same `market_watch` row
  (guard); TEDPIX response candles equal `build_tedpix_payload` (guard);
  market feed for the market page is unchanged; notification source values
  and invalidation are guarded.
- No schema migrations or data writes: all measurements read-only; the
  `get_db` DDL is the pre-existing idempotent maintenance, now once per
  schema version.
- UI: browser probes at 1366×768, production build; no visual layout change
  in Rounds 2–6. 1366×1080 was not separately screenshot-verified.
- A console-only pageerror `TypeError: Cannot read properties of undefined
  (reading 'bar')` appeared in some full tab-cycle runs (technical page) but
  did not reproduce in isolated technical/market-status/fundamental probes.
  It is reported under remaining issues; no chart code was touched.

## G. Remaining bottlenecks

1. **MarketStatusPage fan-out**: 21 requests in four Chrome connection waves;
   `/api/mstat/board` exists precisely to collapse them. Highest-value next
   frontend change, requiring a cross-component data-source refactor.
2. **Live-session funnel polling**: the default landing can POST a 7.5 MB
   funnel payload every 5–20 s while the market is open (server body cache and
   gzip, but the client still parses it). Not measured live; next resource
   target, with a lightweight revision check or GET conditional path.
3. **Chart endpoint** `/api/chart/<symbol>`: 0.5–5 s, external CDN-dependent;
   **Coder2-owned** (`api/chart.py`, `frontend/src/features/technical/**`).
4. **FTS per-symbol endpoint**: ≈1 s warm; shared FTS engine, adjacent to
   Coder2's technical path; coordinate before changing.
5. **FTS caches keyed by `id(conn)`** (`fts_engine._SECTOR_CACHE`,
   `_MCAP_CACHE`, `_FTS_RESULTS_CACHE`): ineffective across HTTP connections
   and a reuse-after-close correctness risk. Left untouched (shared engine
   semantics; owner review recommended).
6. **Full board payload** for the market page: 6.8 MB raw / 1.2 MB gzip on
   first load; reducing it needs a UI field audit.
7. **TEDPIX first fetch** remains external-source bound (0.1–6 s variance);
   ETag only helps repeats.
8. **Cold startup without screener disk cache** still ≈3 minutes of warm-up;
   subsequent starts use the 16 s disk-cache path.
9. **Console pageerror** on the technical page in some full cycles; not
   reproduced isolated, likely chart lifecycle/Coder2.
10. **1366×1080** rendering was not separately screenshot-verified.

## H. Git status

- Branch: `mission/coder3-performance-resource-2026-10-22` (created from
  `784d9d8a`); no merge to `main`, nothing pushed.
- Commits: `1147447a`, `77d32d90`, `cf9c0048`, `e250b325`, `e8bfcf07`,
  `941be7c0`; harness methodology `98bc436a`; reports/evidence in the final
  documentation commit (see `git log -1` on this file).
- Working tree: reports, CSV and this document are committed together; raw
  `.log` files are intentionally gitignored. The temporary HEAD worktree used
  for A/B measurements is removed after validation.
- Classification: Round 1/2/3/4/5 GET_DB results `VERIFIED`; Round 5 LRU
  `IMPLEMENTED_AND_TESTED` (preventive, no heap win claimed); Round 6
  post-idle result `IMPLEMENTED_AND_TESTED` (n=1 each); live-session behavior
  and 1366×1080 visuals `NOT_MEASURED`; chart/FTS remaining bottlenecks
  `BLOCKED` by ownership or scope.
